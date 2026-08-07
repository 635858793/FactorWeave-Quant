"""R240-P0-B: ModelTrainingService._do_dispose + 容器 4 链复用测试

验证 (全部来自 R240-B 子智能体审计 + 主智能体交叉验证):
- ModelTrainingService: 4 RLock (L211/215/219/223) + training_thread (L871-878)
  → 继承 BaseService.dispose 默认 _do_dispose 空实现 → 线程/引用永不释放
- 容器 unified_service_container.py:399 只认 dispose() → cleanup 孤儿方法不执行
  (ConfigService.cleanup L312 保存配置+关闭 db_conn, 容器关闭时永不调用)
- 底层 service_container.py:472-480 已支持 4 链 (dispose/close/shutdown/cleanup)
- TDD: RED → GREEN
"""
import threading

import pytest


@pytest.fixture
def training_service(monkeypatch):
    """真实实例化 ModelTrainingService (monkeypatch get_service_container)"""
    from core.events import get_event_bus
    from core.services import model_training_service as mts

    class FakeContainer:
        def is_registered(self, *a, **kw):
            return False

        def resolve(self, *a, **kw):
            return None

    monkeypatch.setattr(mts, "get_service_container", lambda: FakeContainer())
    svc = mts.ModelTrainingService(service_container=None, event_bus=get_event_bus())
    yield svc


class TestModelTrainingDispose:
    """ModelTrainingService dispose 链 (R240-P0-B)"""

    def test_do_dispose_method_exists(self, training_service):
        assert hasattr(training_service, "_do_dispose"), "ModelTrainingService 缺少 _do_dispose"

    def test_dispose_clears_threads_and_tasks(self, training_service):
        """dispose 后训练线程/任务/版本/日志全部清空"""
        # 模拟运行中的训练资源
        training_service._training_threads["task_1"] = threading.Thread(target=lambda: None)
        training_service._training_tasks["task_1"] = {"status": "running"}
        training_service._training_logs.append("log-entry")
        training_service._model_versions["v1"] = {"version": "1"}

        training_service.dispose()

        assert training_service._disposed is True
        assert training_service._training_threads == {}, "训练线程未清空"
        assert training_service._training_tasks == {}, "训练任务未清空"
        assert training_service._training_logs == [], "训练日志未清空"
        assert training_service._model_versions == {}, "模型版本未清空"

    def test_dispose_idempotent(self, training_service):
        """R78 幂等: 二次 dispose 安全"""
        training_service.dispose()
        training_service.dispose()  # 不应抛异常


class TestContainer4Chain:
    """容器 shutdown_all_services 支持 dispose/close/shutdown/cleanup 4 链 (R240-P1-A)"""

    def _make_container(self):
        from core.containers.service_container import ServiceScope
        from core.containers.unified_service_container import UnifiedServiceContainer
        return UnifiedServiceContainer(), ServiceScope

    def _register_and_resolve(self, container, scope, cls, instance):
        """注册服务并强制实例化进 _instances"""
        container.register(service_type=cls, implementation=cls, scope=scope.SINGLETON)
        # 注入预构建实例, 绕过构造依赖
        container._instances[cls] = instance
        return instance

    def test_shutdown_calls_cleanup_only_service(self):
        """注册仅含 cleanup 的服务 (如 ConfigService), 关闭后 cleanup 必须被调用"""
        calls = []

        class FakeCleanupOnlyService:
            def cleanup(self):
                calls.append("cleanup")

        container, scope = self._make_container()
        self._register_and_resolve(container, scope, FakeCleanupOnlyService, FakeCleanupOnlyService())

        container.shutdown_all_services()

        assert "cleanup" in calls, "容器未调用 cleanup-only 服务的清理方法 (L399 只认 dispose)"

    def test_shutdown_calls_close_only_service(self):
        """注册仅含 close 的服务, 关闭后 close 必须被调用"""
        calls = []

        class FakeCloseOnlyService:
            def close(self):
                calls.append("close")

        container, scope = self._make_container()
        self._register_and_resolve(container, scope, FakeCloseOnlyService, FakeCloseOnlyService())

        container.shutdown_all_services()

        assert "close" in calls, "容器未调用 close-only 服务的清理方法"

    def test_shutdown_calls_dispose_precedence(self):
        """同时有 dispose+cleanup 时按 4 链顺序执行 (dispose → cleanup)"""
        calls = []

        class FakeMultiService:
            def dispose(self):
                calls.append("dispose")

            def cleanup(self):
                calls.append("cleanup")

        container, scope = self._make_container()
        self._register_and_resolve(container, scope, FakeMultiService, FakeMultiService())

        container.shutdown_all_services()

        assert calls == ["dispose", "cleanup"], f"4 链顺序错误: {calls}"
