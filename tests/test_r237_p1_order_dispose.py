"""
R237-P1 TDD 测试: OrderService / OrderMonitor dispose 链治理 (R78 铁律 + R233 §13.4)

发现来源 (R237 4 子智能体交叉验证 + 主智能体独立验证):
- OrderMonitor (core/trading/order_monitor.py:58): 7 个事件订阅 (L104-110) 无 dispose,
  stop_monitoring (L119-132) 有 unsubscribe 但 dispose 路径缺失, _alerts/_order_create_times 内存不清空
- OrderService (core/trading/order_service.py:26): 2 个事件订阅 (L46-49) 无 dispose,
  _order_locks (L40) 不清理, 子组件 monitor/executor/analyzer 无统一释放

修复目标 (RED → GREEN):
1. OrderMonitor.dispose(): _disposed 标志幂等短路 + unsubscribe 7 事件 + 清空 _alerts/_order_create_times
2. OrderService.dispose(): _disposed 标志幂等短路 + unsubscribe 2 事件 + 清空 _order_locks + 子组件 dispose

遵循铁律:
- R78 §8.1 #6 dispose 路径必须幂等 (_disposed flag 短路)
- R233 §13.4 业务核心 Service 0 dispose 链 P0 必修 (4 源验证)
- R234 强化: 业务数据清空 + 失败仅 warning 不抛 (R117-HVD-69 P1 模板)
- R237-B 模板: test_r237_b_6services_p2_dispose.py 9-9-9 TDD 结构
"""
import sys
from unittest.mock import MagicMock
from threading import Lock
from datetime import datetime

import pytest

# 确保项目根可导入
sys.path.insert(0, ".")

from core.trading.order_monitor import OrderMonitor, OrderAlert, AlertLevel
from core.trading.order_service import OrderService


class TestOrderMonitorDispose:
    """OrderMonitor dispose 链 TDD (R233 §13.4)"""

    def _make_monitor(self):
        """构造 OrderMonitor 实例 (绕过 __init__ 依赖)"""
        mon = OrderMonitor.__new__(OrderMonitor)
        mon.service_container = MagicMock()
        mon.event_bus = MagicMock()
        mon.repository = MagicMock()
        mon._alerts = [MagicMock(spec=OrderAlert)]
        mon._order_create_times = {"order_1": datetime.now()}
        mon._monitoring_enabled = True
        mon._check_interval = 300
        mon._last_check_time = datetime.now()
        mon._config = {
            'pending_timeout': 300,
            'submitted_timeout': 600,
            'partial_fill_timeout': 900,
        }
        # 记录订阅的回调 (模拟真实 EventBus 行为)
        mon._subscribed = {
            'order_created': mon._on_order_created,
            'order_submitted': mon._on_order_submitted,
            'order_filled': mon._on_order_filled,
            'order_partially_filled': mon._on_order_partially_filled,
            'order_cancelled': mon._on_order_cancelled,
            'order_submitted_failed': mon._on_order_submitted_failed,
            'order_updated': mon._on_order_updated,
        }
        mon.event_bus.unsubscribe.side_effect = lambda name, cb: None
        return mon

    def test_T01_has_dispose_method(self):
        """OrderMonitor 必须存在 dispose 方法 (R233 §13.4)"""
        mon = self._make_monitor()
        assert hasattr(mon, 'dispose'), "OrderMonitor 缺少 dispose 方法 (P0 业务核心)"
        assert callable(mon.dispose)

    def test_T02_dispose_has_short_circuit(self):
        """dispose 必须 _disposed 标志幂等短路 (R78 铁律 #6)"""
        mon = self._make_monitor()
        assert hasattr(mon, '_disposed'), "OrderMonitor 缺少 _disposed 标志"
        # 第一次 dispose
        mon.dispose()
        assert mon._disposed is True, "dispose 后 _disposed 必须为 True"
        # 第二次 dispose 不得抛错 (幂等)
        mon.dispose()  # 不应抛异常

    def test_T03_repeated_dispose_idempotent(self):
        """重复 dispose 必须幂等 (R78 铁律 #6, R235-D 教训)"""
        mon = self._make_monitor()
        mon.dispose()
        mon.dispose()  # 第二次调用不得抛错
        mon.dispose()  # 第三次调用不得抛错

    def test_T04_unsubscribes_all_events(self):
        """dispose 必须 unsubscribe 全部 7 个订阅事件 (R8 §8.1 铁律 #1)"""
        mon = self._make_monitor()
        mon.dispose()
        expected_events = [
            'order_created', 'order_submitted', 'order_filled',
            'order_partially_filled', 'order_cancelled',
            'order_submitted_failed', 'order_updated',
        ]
        # 验证所有事件都被 unsubscribe
        for evt in expected_events:
            mon.event_bus.unsubscribe.assert_any_call(evt, mon._subscribed[evt])

    def test_T05_clears_business_data(self):
        """dispose 必须清空业务数据 _alerts / _order_create_times"""
        mon = self._make_monitor()
        assert len(mon._alerts) == 1
        assert len(mon._order_create_times) == 1
        mon.dispose()
        assert len(mon._alerts) == 0, "dispose 后 _alerts 必须清空 (内存泄漏防御)"
        assert len(mon._order_create_times) == 0, "dispose 后 _order_create_times 必须清空"

    def test_T06_dispose_failure_no_raise(self):
        """dispose 失败仅 warning 不抛 (R117-HVD-69 P1 模板, R78)"""
        mon = self._make_monitor()
        # 让 unsubscribe 抛异常, dispose 不得向上抛
        mon.event_bus.unsubscribe.side_effect = RuntimeError("bus 已关闭")
        mon.dispose()  # 不应抛异常


class TestOrderServiceDispose:
    """OrderService dispose 链 TDD (R233 §13.4)"""

    def _make_service(self):
        """构造 OrderService 实例 (绕过 __init__ 依赖)"""
        svc = OrderService.__new__(OrderService)
        svc.service_container = MagicMock()
        svc.event_bus = MagicMock()
        svc.validator = MagicMock()
        svc.repository = MagicMock()
        svc.executor = MagicMock()
        svc.monitor = MagicMock(spec=OrderMonitor)
        svc.analyzer = MagicMock()
        svc._order_locks = {"order_1": Lock(), "order_2": Lock()}
        svc._lock_manager_lock = Lock()
        svc._subscribed = {
            'order_terminal_state': svc._on_order_terminal_state,
            'order_validation_failed': svc._on_order_validation_failed,
        }
        return svc

    def test_T01_has_dispose_method(self):
        """OrderService 必须存在 dispose 方法 (R233 §13.4)"""
        svc = self._make_service()
        assert hasattr(svc, 'dispose'), "OrderService 缺少 dispose 方法 (P0 业务核心)"
        assert callable(svc.dispose)

    def test_T02_dispose_has_short_circuit(self):
        """dispose 必须 _disposed 标志幂等短路 (R78 铁律 #6)"""
        svc = self._make_service()
        assert hasattr(svc, '_disposed'), "OrderService 缺少 _disposed 标志"
        svc.dispose()
        assert svc._disposed is True
        svc.dispose()  # 幂等, 不得抛错

    def test_T03_repeated_dispose_idempotent(self):
        """重复 dispose 必须幂等 (R78 铁律 #6)"""
        svc = self._make_service()
        svc.dispose()
        svc.dispose()
        svc.dispose()  # 多次调用不得抛错

    def test_T04_unsubscribes_all_events(self):
        """dispose 必须 unsubscribe 全部 2 个订阅事件 (R8 §8.1 铁律 #1)"""
        svc = self._make_service()
        svc.dispose()
        svc.event_bus.unsubscribe.assert_any_call(
            'order_terminal_state', svc._subscribed['order_terminal_state'])
        svc.event_bus.unsubscribe.assert_any_call(
            'order_validation_failed', svc._subscribed['order_validation_failed'])

    def test_T05_clears_order_locks(self):
        """dispose 必须清空 _order_locks (内存泄漏防御)"""
        svc = self._make_service()
        assert len(svc._order_locks) == 2
        svc.dispose()
        assert len(svc._order_locks) == 0, "dispose 后 _order_locks 必须清空"

    def test_T06_disposes_sub_components(self):
        """dispose 必须释放子组件 monitor (R234 子组件释放 4 步法)"""
        svc = self._make_service()
        svc.dispose()
        svc.monitor.dispose.assert_called_once(), "OrderService.dispose 必须调用 monitor.dispose"

    def test_T07_dispose_failure_no_raise(self):
        """dispose 失败仅 warning 不抛 (R117-HVD-69 P1 模板)"""
        svc = self._make_service()
        svc.monitor.dispose.side_effect = RuntimeError("monitor 已销毁")
        svc.dispose()  # 不应抛异常


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    sys.exit(pytest.main([__file__, "-v"]))
