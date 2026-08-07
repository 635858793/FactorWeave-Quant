"""
R239-P0 dispose 链修复测试 (2026-08-02)

覆盖 (R238 交叉验证 100% 确认的 P0 资源泄漏):
1. BacktestResultManager: 容器注册服务, DuckDB 连接永不关闭 (HVD-239-P0-003)
2. PerformanceMonitor: QObject, 2 个 QTimer 永不停 (HVD-239-P0-004)
3. graceful_shutdown EventBus.dispose 兜底 (HVD-239-P1-005)

TDD 要求: RED (本测试先于修复) → GREEN (实施修复后通过)
"""
import sys
import os
import pytest

# 确保项目根目录可导入
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from loguru import logger
logger.disable("hikyuu")


# ---------------------------------------------------------------
# 1. BacktestResultManager dispose 链
# ---------------------------------------------------------------
class TestBacktestResultManagerDispose:

    def test_dispose_method_exists(self):
        """dispose() 方法必须存在 (R78 4 链标准)"""
        from core.services.backtest_result_manager import BacktestResultManager
        assert hasattr(BacktestResultManager, 'dispose'), \
            "BacktestResultManager 缺 dispose() (R239-P0 资源泄漏)"

    def test_dispose_sets_disposed_flag(self):
        """dispose 后 _disposed 标志位为 True"""
        from core.services.backtest_result_manager import BacktestResultManager
        mgr = BacktestResultManager.__new__(BacktestResultManager)
        mgr._results = {}
        mgr._disposed = False
        mgr.dispose()
        assert mgr._disposed is True

    def test_dispose_idempotent(self):
        """重复 dispose 不抛错 (R78 幂等铁律)"""
        from core.services.backtest_result_manager import BacktestResultManager
        mgr = BacktestResultManager.__new__(BacktestResultManager)
        mgr._results = {}
        mgr._disposed = False
        mgr.dispose()
        mgr.dispose()  # 第二次调用不抛错
        assert mgr._disposed is True

    def test_dispose_clears_results(self):
        """dispose 清空内存结果字典"""
        from core.services.backtest_result_manager import BacktestResultManager
        mgr = BacktestResultManager.__new__(BacktestResultManager)
        mgr._results = {"000001": ["fake"]}
        mgr._disposed = False
        mgr.dispose()
        assert len(mgr._results) == 0


# ---------------------------------------------------------------
# 2. PerformanceMonitor dispose 链
# ---------------------------------------------------------------
@pytest.fixture
def qt_app():
    """PyQt5 QTimer 需要 QCoreApplication"""
    from PyQt5.QtCore import QCoreApplication
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


class TestPerformanceMonitorDispose:

    def _make_monitor(self, monkeypatch, qt_app):
        """真实实例化 PerformanceMonitor (monkeypatch 掉告警引擎依赖)"""
        import core.monitoring.performance_monitor as pm_mod
        monkeypatch.setattr(
            pm_mod.PerformanceMonitor, '_connect_alert_system', lambda self: None)
        mon = pm_mod.PerformanceMonitor(config={'auto_report': False})
        mon.performance_callbacks = []
        return mon

    def test_dispose_method_exists(self):
        """dispose() 方法必须存在"""
        from core.monitoring.performance_monitor import PerformanceMonitor
        assert hasattr(PerformanceMonitor, 'dispose'), \
            "PerformanceMonitor 缺 dispose() (R239-P0 QTimer 泄漏)"

    def test_dispose_disables_monitoring(self, monkeypatch, qt_app):
        """dispose 后 monitoring_enabled=False"""
        mon = self._make_monitor(monkeypatch, qt_app)
        assert mon.monitoring_enabled is True
        mon.dispose()
        assert mon.monitoring_enabled is False

    def test_dispose_stops_timer(self, monkeypatch, qt_app):
        """dispose 停止 monitoring_timer"""
        mon = self._make_monitor(monkeypatch, qt_app)
        assert mon.monitoring_timer.isActive() is True
        mon.dispose()
        assert mon.monitoring_timer.isActive() is False

    def test_dispose_idempotent(self, monkeypatch, qt_app):
        """重复 dispose 不抛错"""
        mon = self._make_monitor(monkeypatch, qt_app)
        mon.dispose()
        mon.dispose()
        assert mon.monitoring_enabled is False

    def test_dispose_clears_callbacks(self, monkeypatch, qt_app):
        """dispose 清空性能回调"""
        mon = self._make_monitor(monkeypatch, qt_app)
        mon.performance_callbacks = [lambda: None]
        mon.dispose()
        assert len(mon.performance_callbacks) == 0


# ---------------------------------------------------------------
# 3. graceful_shutdown EventBus.dispose 兜底
# ---------------------------------------------------------------
class TestGracefulShutdownEventBusFallback:

    def test_register_event_bus_handler_exists(self):
        """GracefulShutdownManager 必须有 register_event_bus_cleanup 方法或等效机制"""
        from core.graceful_shutdown import GracefulShutdownManager
        mgr = GracefulShutdownManager.__new__(GracefulShutdownManager)
        mgr._cleanup_handlers = []
        mgr._shutdown_lock = None
        assert hasattr(GracefulShutdownManager, 'register_event_bus_cleanup'), \
            "GracefulShutdownManager 缺 EventBus.dispose 兜底注册方法 (HVD-239-P1-005)"

    def test_register_appends_handler(self):
        """register_event_bus_cleanup 追加 handler 到清理列表"""
        from core.graceful_shutdown import GracefulShutdownManager
        mgr = GracefulShutdownManager.__new__(GracefulShutdownManager)
        mgr._cleanup_handlers = []
        mgr._shutdown_lock = None
        mgr.register_event_bus_cleanup()
        assert len(mgr._cleanup_handlers) == 1
        name, handler = mgr._cleanup_handlers[0]
        assert callable(handler)
        assert "event_bus" in name.lower()
