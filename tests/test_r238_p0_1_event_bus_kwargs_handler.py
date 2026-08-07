"""
R238-P0-1 TDD 测试: EventBus 同步 handler 签名不兼容修复

测试目标:
1. 同步模式 (async_execution=False, 默认) 下, **kwargs 签名 handler 能正确收到字符串事件 kwargs
   (修复前: event_bus.py:456 位置调用 handler(event_obj) → TypeError → 持仓同步静默失效)
2. 普通 (event) 签名 handler 不回归
3. 无参数 handler 不回归
4. 字符串事件 kwargs 通过实例属性传递 (修复前: type('Event', (), kwargs)() 是类属性, __dict__ 为空)
5. async_execution=True 线程池路径下 **kwargs handler 同样能收到 kwargs

关联铁律:
- R104 §12 #1 R+1 round 二次验证
- R85 §10 假修复鉴别 4 步法
- TDD RED-GREEN-REFACTOR 闭环 (R219 强制)
"""

import time
import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent


def make_kwargs_handler(captured):
    """构造 **kwargs 签名 handler (模拟 account_manager.py:1078 等)."""

    def _handler(**kwargs):
        captured.append(kwargs)

    return _handler


class TestR238P01SyncKwargsHandler:
    """R238-P0-1: 同步模式 **kwargs handler 正确接收字符串事件 kwargs."""

    def test_p01_1_kwargs_handler_receives_kwargs(self):
        """同步模式: **kwargs handler 收到 account_id 等 kwargs (修复前 TypeError)."""
        from core.events.event_bus import EventBus

        bus = EventBus(async_execution=False)
        captured = []
        bus.subscribe("order_submitted_success", make_kwargs_handler(captured))

        bus.publish("order_submitted_success", order_id="ORD-1", account_id="ACC-1", asset_type="stock")

        assert len(captured) == 1, f"handler 应被调用 1 次, 实际 {len(captured)}"
        assert captured[0].get("account_id") == "ACC-1", f"account_id 未传递: {captured[0]}"
        assert captured[0].get("order_id") == "ORD-1", f"order_id 未传递: {captured[0]}"
        assert captured[0].get("asset_type") == "stock", f"asset_type 未传递: {captured[0]}"

    def test_p01_2_errors_counter_not_incremented(self):
        """同步模式: **kwargs handler 调用后 errors 计数不增加 (无 TypeError)."""
        from core.events.event_bus import EventBus

        bus = EventBus(async_execution=False)
        captured = []
        bus.subscribe("order_submitted_success", make_kwargs_handler(captured))

        bus.publish("order_submitted_success", account_id="ACC-1")

        stats = bus.get_stats()
        assert stats["errors"] == 0, f"errors 计数应保持 0, 实际 {stats['errors']}"
        assert stats["events_handled"] == 1, f"events_handled 应为 1, 实际 {stats['events_handled']}"

    def test_p01_3_positional_event_handler_no_regression(self):
        """同步模式: 普通 (event) 签名 handler 仍收到 event 对象 (不回归)."""
        from core.events.event_bus import EventBus

        bus = EventBus(async_execution=False)
        received = []

        def _handler(event):
            received.append(event)

        bus.subscribe("stock_selected", _handler)
        bus.publish("stock_selected", stock_code="000001", period="day")

        assert len(received) == 1, "普通签名 handler 应被调用"
        assert received[0].stock_code == "000001", "事件对象属性应可访问"

    def test_p01_4_no_arg_handler_no_regression(self):
        """同步模式: 无参数 handler 仍能调用 (不回归)."""
        from core.events.event_bus import EventBus

        bus = EventBus(async_execution=False)
        called = []

        def _handler():
            called.append(True)

        bus.subscribe("some_event", _handler)
        bus.publish("some_event", value=1)

        assert len(called) == 1, "无参数 handler 应被调用"

    def test_p01_5_string_event_obj_instance_dict(self):
        """字符串事件: kwargs 应为实例属性 (event_obj.__dict__ 非空), 供 **kwargs 与 kwargs 签名读取."""
        from core.events.event_bus import EventBus

        bus = EventBus(async_execution=False)
        captured = []
        bus.subscribe("kline_updated", make_kwargs_handler(captured))

        bus.publish("kline_updated", stock_code="600000", period="day", count=100)

        assert len(captured) == 1
        assert captured[0].get("stock_code") == "600000"
        assert captured[0].get("period") == "day"
        assert captured[0].get("count") == 100

    def test_p01_6_async_execution_kwargs_handler(self):
        """线程池路径 (async_execution=True): **kwargs handler 也收到 kwargs."""
        from core.events.event_bus import EventBus

        bus = EventBus(async_execution=True, max_workers=2)
        captured = []
        bus.subscribe("order_submitted_success", make_kwargs_handler(captured))

        bus.publish("order_submitted_success", account_id="ACC-ASYNC", order_id="ORD-ASYNC")
        bus.wait_for_completion(timeout=5.0)

        assert len(captured) >= 1, "线程池 handler 应被调用"
        assert captured[0].get("account_id") == "ACC-ASYNC", f"account_id 未传递: {captured[0]}"
        assert captured[0].get("order_id") == "ORD-ASYNC", f"order_id 未传递: {captured[0]}"
        bus.dispose()

    def test_p01_7_account_manager_position_sync_chain(self):
        """端到端: order_executor 发布 order_submitted_success → AccountManager._on_order_submitted 被触发."""
        from core.events.event_bus import EventBus

        bus = EventBus(async_execution=False)
        captured = []

        # 模拟 AccountManager._on_order_submitted (同签名)
        def _on_order_submitted(**kwargs):
            captured.append(kwargs)

        bus.subscribe("order_submitted_success", _on_order_submitted)
        bus.publish("order_submitted_success", order_id="ORD-777", account_id="ACC-777")

        assert len(captured) == 1, "持仓同步 handler 未被触发 (P0 静默失效)"
        assert captured[0].get("account_id") == "ACC-777", "account_id 未传给持仓同步 handler"
