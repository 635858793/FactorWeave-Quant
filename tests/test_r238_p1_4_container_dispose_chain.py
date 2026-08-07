"""
R238-P1-4 TDD 测试: 容器 dispose 链断裂修复 (TradingEngine/TradingController)

测试目标:
1. _dispose_instance 支持 cleanup 方法 (修复前仅认 dispose/close)
2. _dispose_instance 支持 shutdown 方法
3. _dispose_instance 按序调用所有存在的清理方法
4. 调用失败仅记录日志不抛异常 (R78 幂等防御)
5. classmethod 清理方法正确调用 (R222-B-2 6 路径矩阵)

关联铁律:
- R233 §13.4 业务核心 Service 4 链 dispose P0 必修
- R234 子组件释放 4 步法 (dispose → close → shutdown → 失败仅 warning)
- R78 dispose 幂等模板
- TDD RED-GREEN-REFACTOR 闭环 (R219 强制)
"""

import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent


class TestR238P14DisposeChain:
    """R238-P1-4: 容器 _dispose_instance 清理链."""

    def _make_container(self):
        from core.containers.service_container import ServiceContainer
        return ServiceContainer()

    def test_p14_1_cleanup_method_is_called(self):
        """_dispose_instance 调用仅有 cleanup 方法的实例 (修复前忽略 cleanup)."""
        container = self._make_container()

        class CleanupOnly:
            def __init__(self):
                self.cleaned = False
                self.disposed = False
                self.closed = False
                self.shutdown_called = False

            def cleanup(self):
                self.cleaned = True

        inst = CleanupOnly()
        container._dispose_instance(inst)
        assert inst.cleaned, "cleanup 方法应被调用"
        assert not inst.disposed and not inst.closed, "不应调用不存在的 dispose/close"

    def test_p14_2_shutdown_method_is_called(self):
        """_dispose_instance 调用仅有 shutdown 方法的实例."""
        container = self._make_container()

        class ShutdownOnly:
            def __init__(self):
                self.shutdown_called = False

            def shutdown(self):
                self.shutdown_called = True

        inst = ShutdownOnly()
        container._dispose_instance(inst)
        assert inst.shutdown_called, "shutdown 方法应被调用"

    def test_p14_3_dispose_preferred_first(self):
        """_dispose_instance 按序调用: dispose 优先, 之后仍调用 cleanup."""
        container = self._make_container()

        class Both:
            def __init__(self):
                self.calls = []

            def dispose(self):
                self.calls.append('dispose')

            def cleanup(self):
                self.calls.append('cleanup')

        inst = Both()
        container._dispose_instance(inst)
        assert inst.calls == ['dispose', 'cleanup'], f"应按序调用 dispose+cleanup, 实际 {inst.calls}"

    def test_p14_4_exception_in_method_does_not_propagate(self):
        """清理方法抛异常时仅记录日志, 不向调用方传播."""
        container = self._make_container()

        class Failing:
            def dispose(self):
                raise RuntimeError("dispose failed")

            def cleanup(self):
                raise RuntimeError("cleanup failed")

        inst = Failing()
        # 不应抛异常 (R78 幂等防御: 失败仅 warning)
        container._dispose_instance(inst)

    def test_p14_5_exception_in_first_still_calls_next(self):
        """第一个方法抛异常后, 继续尝试后续清理方法."""
        container = self._make_container()

        class FailFirst:
            def __init__(self):
                self.calls = []

            def dispose(self):
                self.calls.append('dispose')
                raise RuntimeError("boom")

            def cleanup(self):
                self.calls.append('cleanup')

        inst = FailFirst()
        container._dispose_instance(inst)
        assert 'dispose' in inst.calls and 'cleanup' in inst.calls, \
            f"异常后应继续调用后续方法, 实际 {inst.calls}"

    def test_p14_6_classmethod_dispose_is_called(self):
        """classmethod 清理方法正确调用 (R222-B-2 descriptor 处理)."""
        container = self._make_container()

        class ClassMethodCleanup:
            cleaned = False

            @classmethod
            def cleanup(cls):
                cls.cleaned = True

        inst = ClassMethodCleanup()
        container._dispose_instance(inst)
        assert ClassMethodCleanup.cleaned, "classmethod cleanup 应被调用"

    def test_p14_7_trading_engine_cleanup_wiring(self):
        """端到端: TradingEngine 只有 cleanup, 容器 dispose 后其资源被清理."""
        from core.trading_engine import TradingEngine
        from core.containers.service_container import ServiceContainer

        container = ServiceContainer()
        engine = TradingEngine.__new__(TradingEngine)
        engine.positions = {'000001': object()}
        engine.signals = []

        container._instances['TradingEngine'] = engine
        container.dispose()

        assert hasattr(TradingEngine, 'cleanup'), "TradingEngine 应保留 cleanup 方法"
        assert engine.positions == {}, "TradingEngine.cleanup 后 positions 应清空"
