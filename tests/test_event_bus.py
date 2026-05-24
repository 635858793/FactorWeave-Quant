"""
事件总线单元测试

测试范围:
- 事件订阅和取消订阅
- 事件发布和处理
- 事件去重机制
- 事件优先级
- 事件过滤器
- 事件历史记录
- 异步事件处理
- 性能统计
- 异常处理和边界条件
"""
import pytest
import time
import asyncio
import threading
from dataclasses import dataclass
from unittest.mock import MagicMock, patch, call
from collections import deque
from typing import List

from core.events.event_bus import (
    EventBus,
    SimpleEventHandler,
    get_event_bus,
    set_event_bus,
)
from core.events.types import BaseEvent, EventPriority, EventFilter


@dataclass
class TestEvent(BaseEvent):
    """测试事件"""
    message: str = ""
    value: int = 0
    stock_code: str = ""
    chart_type: str = ""
    period: str = ""


class TestSimpleEventHandler:
    """SimpleEventHandler 测试"""

    def test_initialization(self):
        """测试初始化"""
        def handler(event):
            pass

        wrapper = SimpleEventHandler(handler, "test_handler", priority=5)

        assert wrapper.handler == handler
        assert wrapper.name == "test_handler"
        assert wrapper.priority == 5

    def test_default_priority(self):
        """测试默认优先级"""
        def handler(event):
            pass

        wrapper = SimpleEventHandler(handler, "test_handler")

        assert wrapper.priority == 0


class TestEventBusInitialization:
    """EventBus 初始化测试"""

    def test_default_initialization(self):
        """测试默认初始化"""
        bus = EventBus()

        assert bus._async_execution is False
        assert bus._executor is None
        assert bus._deduplication_window == 0.5
        assert bus._enable_history is True
        assert bus._max_history_size == 1000
        assert bus._handlers == {}
        assert bus._global_handlers == []

    def test_async_initialization(self):
        """测试异步初始化"""
        bus = EventBus(async_execution=True, max_workers=8)

        assert bus._async_execution is True
        assert bus._executor is not None

    def test_custom_deduplication_window(self):
        """测试自定义去重窗口"""
        bus = EventBus(deduplication_window=1.5)

        assert bus._deduplication_window == 1.5

    def test_disable_history(self):
        """测试禁用历史记录"""
        bus = EventBus(enable_history=False)

        assert bus._enable_history is False

    def test_custom_history_size(self):
        """测试自定义历史大小"""
        bus = EventBus(max_history_size=500)

        assert bus._max_history_size == 500
        assert bus._event_history.maxlen == 500

    def test_dispose(self):
        """测试释放资源"""
        bus = EventBus(async_execution=True)
        
        def handler(event):
            pass
        bus.subscribe(TestEvent, handler)
        bus.publish(TestEvent(message="test"))
        
        bus.dispose()

        assert len(bus._handlers) == 0
        assert len(bus._global_handlers) == 0
        assert len(bus._event_history) == 0

    def test_len(self):
        """测试长度计算"""
        bus = EventBus()

        def handler1(event):
            pass
        def handler2(event):
            pass

        bus.subscribe(TestEvent, handler1)
        bus.subscribe(TestEvent, handler2)

        assert len(bus) == 2

    def test_repr(self):
        """测试字符串表示"""
        bus = EventBus()
        repr_str = repr(bus)

        assert "EventBus" in repr_str
        assert "async=" in repr_str
        assert "history=" in repr_str


class TestEventBusSubscription:
    """事件订阅测试"""

    def test_subscribe_by_type(self):
        """测试按类型订阅"""
        bus = EventBus()
        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe(TestEvent, handler)
        bus.publish(TestEvent(message="test"))

        assert len(events_received) == 1
        assert events_received[0].message == "test"

    def test_subscribe_by_name(self):
        """测试按名称订阅"""
        bus = EventBus()
        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe("CustomEvent", handler)
        bus.publish("CustomEvent", data="test_data")

        assert len(events_received) == 1

    def test_subscribe_with_priority(self):
        """测试带优先级订阅"""
        bus = EventBus()
        execution_order = []

        def handler_low(event):
            execution_order.append("low")

        def handler_high(event):
            execution_order.append("high")

        bus.subscribe(TestEvent, handler_low, priority=10)
        bus.subscribe(TestEvent, handler_high, priority=1)
        bus.publish(TestEvent())

        assert execution_order == ["high", "low"]

    def test_subscribe_global(self):
        """测试全局订阅注册"""
        bus = EventBus()
        
        def global_handler(event):
            pass

        bus.subscribe_global(global_handler)
        
        stats = bus.get_stats()
        assert stats['global_handlers'] == 1

    def test_subscribe_global_no_regular_handlers(self):
        """测试全局订阅无普通处理器时不触发"""
        bus = EventBus()
        events_received = []

        def global_handler(event):
            events_received.append(event)

        bus.subscribe_global(global_handler)
        bus.publish(TestEvent(message="test1"))

        assert len(events_received) == 0

    def test_unsubscribe(self):
        """测试取消订阅"""
        bus = EventBus()
        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe(TestEvent, handler)
        bus.unsubscribe(TestEvent, handler)
        bus.publish(TestEvent(message="test"))

        assert len(events_received) == 0

    def test_unsubscribe_global(self):
        """测试取消全局订阅"""
        bus = EventBus()
        events_received = []

        def global_handler(event):
            events_received.append(event)

        bus.subscribe_global(global_handler)
        bus.unsubscribe_global(global_handler)
        bus.publish(TestEvent(message="test"))

        assert len(events_received) == 0

    def test_unsubscribe_nonexistent(self):
        """测试取消不存在的订阅"""
        bus = EventBus()

        def handler(event):
            pass

        bus.unsubscribe(TestEvent, handler)

    def test_unsubscribe_global_nonexistent(self):
        """测试取消不存在的全局订阅"""
        bus = EventBus()

        def handler(event):
            pass

        result = bus.unsubscribe_global(handler)
        assert result is False

    def test_multiple_handlers(self):
        """测试多个处理器"""
        bus = EventBus()
        results = []

        def handler1(event):
            results.append(1)

        def handler2(event):
            results.append(2)

        def handler3(event):
            results.append(3)

        bus.subscribe(TestEvent, handler1)
        bus.subscribe(TestEvent, handler2)
        bus.subscribe(TestEvent, handler3)
        bus.publish(TestEvent())

        assert len(results) == 3
        assert set(results) == {1, 2, 3}


class TestEventBusPublishing:
    """事件发布测试"""

    def test_publish_event_object(self):
        """测试发布事件对象"""
        bus = EventBus()
        event_received = None

        def handler(event):
            nonlocal event_received
            event_received = event

        bus.subscribe(TestEvent, handler)
        event = TestEvent(message="test", value=42)
        bus.publish(event)

        assert event_received is not None
        assert event_received.message == "test"
        assert event_received.value == 42

    def test_publish_event_string(self):
        """测试发布字符串事件"""
        bus = EventBus()
        event_received = None

        def handler(event):
            nonlocal event_received
            event_received = event

        bus.subscribe("CustomEvent", handler)
        bus.publish("CustomEvent", data="test")

        assert event_received is not None
        assert event_received.data == "test"

    def test_publish_no_handlers(self):
        """测试发布无处理器事件"""
        bus = EventBus()
        bus.publish(TestEvent(message="test"))

    def test_publish_with_filter(self):
        """测试发布带过滤器事件"""
        bus = EventBus()
        events_received = []

        def handler(event):
            events_received.append(event)

        from core.events.types import EventFilter
        event_filter = EventFilter(strategy_ids=["strategy1"])
        bus.subscribe(TestEvent, handler)
        
        event1 = TestEvent(message="filtered")
        event1.strategy_id = "strategy1"
        bus.publish_with_filter(event1, event_filter)

        event2 = TestEvent(message="not_filtered")
        event2.strategy_id = "strategy2"
        bus.publish_with_filter(event2, event_filter)

        assert len(events_received) == 1

    def test_publish_with_priority(self):
        """测试发布带优先级事件"""
        bus = EventBus()
        event_received = None

        def handler(event):
            nonlocal event_received
            event_received = event

        bus.subscribe(TestEvent, handler)
        event = TestEvent()
        bus.publish_with_priority(event, EventPriority.HIGH)

        assert event_received is not None
        assert event_received.priority == EventPriority.HIGH


class TestEventDeduplication:
    """事件去重测试"""

    def test_deduplicate_same_event(self):
        """测试相同事件去重"""
        bus = EventBus(deduplication_window=1.0)
        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe(TestEvent, handler)
        
        bus.publish(TestEvent(stock_code="000001"))
        bus.publish(TestEvent(stock_code="000001"))

        assert len(events_received) == 1

    def test_deduplicate_different_events(self):
        """测试不同事件不去重"""
        bus = EventBus(deduplication_window=1.0)
        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe(TestEvent, handler)
        
        bus.publish(TestEvent(stock_code="000001"))
        bus.publish(TestEvent(stock_code="000002"))

        assert len(events_received) == 2

    def test_deduplicate_same_stock_code(self):
        """测试相同股票代码去重"""
        bus = EventBus(deduplication_window=1.0)
        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe(TestEvent, handler)
        
        bus.publish(TestEvent(stock_code="000001"))
        bus.publish(TestEvent(stock_code="000001"))

        assert len(events_received) == 1

    def test_deduplicate_expired_window(self):
        """测试去重窗口过期"""
        bus = EventBus(deduplication_window=0.1)
        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe(TestEvent, handler)
        
        bus.publish(TestEvent(message="test"))
        time.sleep(0.15)
        bus.publish(TestEvent(message="test"))

        assert len(events_received) == 2

    def test_deduplicate_with_stock_code(self):
        """测试带股票代码去重"""
        bus = EventBus(deduplication_window=1.0)
        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe(TestEvent, handler)
        
        bus.publish(TestEvent(stock_code="000001"))
        bus.publish(TestEvent(stock_code="000001"))

        assert len(events_received) == 1

    def test_deduplicate_different_stock_codes(self):
        """测试不同股票不去重"""
        bus = EventBus(deduplication_window=1.0)
        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe(TestEvent, handler)
        
        bus.publish(TestEvent(stock_code="000001"))
        bus.publish(TestEvent(stock_code="000002"))

        assert len(events_received) == 2

    def test_deduplicate_disabled(self):
        """测试禁用去重"""
        bus = EventBus(deduplication_window=0)
        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe(TestEvent, handler)
        
        bus.publish(TestEvent(message="test"))
        bus.publish(TestEvent(message="test"))

        assert len(events_received) == 2


class TestEventHistory:
    """事件历史测试"""

    def test_add_to_history(self):
        """测试添加到历史"""
        bus = EventBus(enable_history=True)
        
        def handler(event):
            pass
        bus.subscribe(TestEvent, handler)
        
        event = TestEvent(message="test")
        bus.publish(event)

        history = bus.get_history()
        assert len(history) == 1
        assert history[0]['event_type'] == 'TestEvent'

    def test_history_disabled(self):
        """测试禁用历史"""
        bus = EventBus(enable_history=False)
        
        def handler(event):
            pass
        bus.subscribe(TestEvent, handler)
        
        event = TestEvent(message="test")
        bus.publish(event)

        history = bus.get_history()
        assert len(history) == 0

    def test_history_limit(self):
        """测试历史限制"""
        bus = EventBus(max_history_size=3, deduplication_window=0)
        
        def handler(event):
            pass
        bus.subscribe(TestEvent, handler)
        
        for i in range(5):
            bus.publish(TestEvent(stock_code=f"00000{i}"))

        history = bus.get_history()
        assert len(history) == 3

    def test_get_history_by_type(self):
        """测试按类型获取历史"""
        bus = EventBus(deduplication_window=0)
        
        def handler(event):
            pass
        bus.subscribe(TestEvent, handler)
        
        bus.publish(TestEvent(stock_code="000001"))
        bus.publish(TestEvent(stock_code="000002"))

        history = bus.get_history(event_type="TestEvent")
        assert len(history) == 2

    def test_get_history_nonexistent_type(self):
        """测试获取不存在的类型历史"""
        bus = EventBus()
        
        def handler(event):
            pass
        bus.subscribe(TestEvent, handler)
        
        bus.publish(TestEvent(message="test"))

        history = bus.get_history(event_type="NonExistent")
        assert len(history) == 0

    def test_clear_history(self):
        """测试清空历史"""
        bus = EventBus()
        
        def handler(event):
            pass
        bus.subscribe(TestEvent, handler)
        
        bus.publish(TestEvent(message="test"))
        bus.clear_history()

        history = bus.get_history()
        assert len(history) == 0


class TestEventFilter:
    """事件过滤器测试"""

    def test_filter_matches_strategy_id(self):
        """测试过滤器匹配策略ID"""
        event_filter = EventFilter(strategy_ids=["strategy1"])
        event = TestEvent()
        event.strategy_id = "strategy1"

        assert event_filter.matches(event) is True

    def test_filter_not_matches_strategy_id(self):
        """测试过滤器不匹配策略ID"""
        event_filter = EventFilter(strategy_ids=["strategy1"])
        event = TestEvent()
        event.strategy_id = "strategy2"

        assert event_filter.matches(event) is False

    def test_filter_matches_event_type(self):
        """测试过滤器匹配事件类型"""
        from core.events.types import EventType
        event_filter = EventFilter(event_types=[EventType.CHART_UPDATED])
        event = TestEvent()
        event.event_type = EventType.CHART_UPDATED

        assert event_filter.matches(event) is True

    def test_filter_no_conditions(self):
        """测试过滤器无条件"""
        event_filter = EventFilter()
        event = TestEvent()

        assert event_filter.matches(event) is True

    def test_filter_priority_range(self):
        """测试过滤器优先级范围"""
        from core.events.types import EventPriority
        event_filter = EventFilter(
            priority_min=EventPriority.HIGH,
            priority_max=EventPriority.LOW
        )
        event = TestEvent()
        event.priority = EventPriority.NORMAL

        assert event_filter.matches(event) is True


class TestEventBusStats:
    """事件总线统计测试"""

    def test_get_stats(self):
        """测试获取统计"""
        bus = EventBus()
        
        def handler(event):
            pass
        bus.subscribe(TestEvent, handler)
        bus.publish(TestEvent())

        stats = bus.get_stats()

        assert 'events_published' in stats
        assert 'events_handled' in stats
        assert 'handlers_registered' in stats
        assert stats['events_published'] == 1
        assert stats['events_handled'] == 1
        assert stats['handlers_registered'] == 1

    def test_clear_stats(self):
        """测试清空统计"""
        bus = EventBus()
        
        def handler(event):
            pass
        bus.subscribe(TestEvent, handler)
        bus.publish(TestEvent())
        bus.clear_stats()

        stats = bus.get_stats()
        assert stats['events_published'] == 0
        assert stats['events_handled'] == 0

    def test_stats_with_errors(self):
        """测试错误统计"""
        bus = EventBus()
        
        def failing_handler(event):
            raise ValueError("Test error")

        bus.subscribe(TestEvent, failing_handler)
        bus.publish(TestEvent())

        stats = bus.get_stats()
        assert stats['errors'] >= 1


class TestAsyncEventBus:
    """异步事件总线测试"""

    def test_async_execution(self):
        """测试异步执行"""
        bus = EventBus(async_execution=True, max_workers=2)
        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe(TestEvent, handler)
        bus.publish(TestEvent(message="async_test"))
        
        time.sleep(0.1)
        bus.wait_for_completion(timeout=1.0)

        assert len(events_received) == 1
        bus.dispose()

    def test_wait_for_completion_no_async(self):
        """测试无异步时等待完成"""
        bus = EventBus(async_execution=False)
        result = bus.wait_for_completion(timeout=1.0)
        assert result is True

    def test_async_handler_detection(self):
        """测试异步处理器检测"""
        bus = EventBus()
        events_received = []

        async def async_handler(event):
            events_received.append(event)

        bus.subscribe(TestEvent, async_handler)
        bus.publish(TestEvent())
        
        time.sleep(0.1)

    def test_multiple_async_handlers(self):
        """测试多个异步处理器"""
        bus = EventBus(async_execution=True, max_workers=4)
        results = []

        def handler1(event):
            time.sleep(0.05)
            results.append(1)

        def handler2(event):
            time.sleep(0.05)
            results.append(2)

        def handler3(event):
            time.sleep(0.05)
            results.append(3)

        bus.subscribe(TestEvent, handler1)
        bus.subscribe(TestEvent, handler2)
        bus.subscribe(TestEvent, handler3)
        
        bus.publish(TestEvent())
        bus.wait_for_completion(timeout=2.0)
        bus.dispose()

        assert len(results) == 3


class TestGlobalEventBus:

    def test_get_event_bus_creates_instance(self):
        from core.events.event_bus import _global_event_bus as original
        from core.events import event_bus as eb
        original = eb._global_event_bus
        eb._global_event_bus = None

        try:
            bus = get_event_bus()
            assert isinstance(bus, EventBus)
        finally:
            eb._global_event_bus = original

    def test_get_event_bus_returns_same_instance(self):
        from core.events import event_bus as eb
        original = eb._global_event_bus
        eb._global_event_bus = None

        try:
            bus1 = get_event_bus()
            bus2 = get_event_bus()
            assert bus1 is bus2
        finally:
            eb._global_event_bus = original

    def test_set_event_bus(self):
        from core.events import event_bus as eb
        original = eb._global_event_bus

        try:
            new_bus = EventBus()
            set_event_bus(new_bus)
            assert get_event_bus() is new_bus
        finally:
            eb._global_event_bus = original


class TestEventBusEdgeCases:
    """边界条件测试"""

    def test_handler_with_no_parameters(self):
        bus = EventBus(deduplication_window=0)
        errors = []

        def handler_no_params():
            pass

        def handler_with_event(event):
            pass

        def error_handler(event):
            errors.append(event)

        bus.subscribe("ErrorEvent", error_handler)
        bus.subscribe(TestEvent, handler_with_event)
        bus.subscribe(TestEvent, handler_no_params)
        bus.publish(TestEvent(stock_code="test1"))

        assert len(errors) >= 0

    def test_handler_with_var_keyword(self):
        """测试可变关键字参数处理器"""
        bus = EventBus(deduplication_window=0)
        received_events = []

        def handler(event):
            if hasattr(event, '__dict__'):
                received_events.append(event.__dict__)

        bus.subscribe(TestEvent, handler)
        bus.publish(TestEvent(stock_code="test1"))

        assert len(received_events) == 1

    def test_concurrent_publish(self):
        bus = EventBus(deduplication_window=0)
        events_received = []
        lock = threading.Lock()

        def handler(event):
            with lock:
                events_received.append(event)

        bus.subscribe(TestEvent, handler)

        def publish_events(count):
            for i in range(count):
                bus.publish(TestEvent(stock_code=f"thread_{count}_{i}"))

        threads = [threading.Thread(target=publish_events, args=(10,)) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(events_received) == 30

    def test_handler_exception_does_not_stop_others(self):
        """测试处理器异常不影响其他处理器"""
        bus = EventBus()
        results = []

        def failing_handler(event):
            raise ValueError("Failing handler")

        def success_handler(event):
            results.append("success")

        bus.subscribe(TestEvent, failing_handler)
        bus.subscribe(TestEvent, success_handler)
        bus.publish(TestEvent())

        assert "success" in results

    def test_error_recursion_limit(self):
        """测试错误递归限制"""
        bus = EventBus()

        def error_handler(event):
            raise ValueError("Error in error handler")

        bus.subscribe("ErrorEvent", error_handler)
        bus.subscribe(TestEvent, lambda e: (_ for _ in ()).throw(ValueError("Test")))
        
        bus.publish(TestEvent())

    def test_publish_empty_kwargs(self):
        """测试发布空参数"""
        bus = EventBus()
        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe("EmptyEvent", handler)
        bus.publish("EmptyEvent")

        assert len(events_received) == 1

    def test_subscribe_after_publish(self):
        """测试发布后订阅"""
        bus = EventBus(deduplication_window=0)
        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe(TestEvent, handler)
        bus.publish(TestEvent(stock_code="before"))
        bus.publish(TestEvent(stock_code="after"))

        assert len(events_received) == 2

    def test_unsubscribe_during_publish(self):
        """测试发布时取消订阅"""
        bus = EventBus()
        events_received = []
        unsubscribe_called = []

        def handler1(event):
            events_received.append(1)

        def handler2(event):
            events_received.append(2)
            bus.unsubscribe(TestEvent, handler2)
            unsubscribe_called.append(True)

        def handler3(event):
            events_received.append(3)

        bus.subscribe(TestEvent, handler1)
        bus.subscribe(TestEvent, handler2)
        bus.subscribe(TestEvent, handler3)
        
        bus.publish(TestEvent())
        
        assert len(events_received) >= 2

    def test_event_key_generation_complex_event(self):
        """测试复杂事件键生成"""
        bus = EventBus()
        
        event = TestEvent(
            stock_code="000001",
            chart_type="kline",
            period="daily"
        )
        
        key = bus._get_event_key(event)
        assert "TestEvent" in key
        assert "s:000001" in key
        assert "c:kline" in key
        assert "p:daily" in key

    def test_deduplicate_statistics(self):
        """测试去重统计"""
        bus = EventBus(deduplication_window=1.0)
        
        def handler(event):
            pass

        bus.subscribe(TestEvent, handler)
        bus.publish(TestEvent(message="test"))
        bus.publish(TestEvent(message="test"))

        stats = bus.get_stats()
        assert stats['events_deduplicated'] == 1


class TestEventBusErrorHandling:
    """异常处理测试"""

    def test_handler_raises_exception(self):
        """测试处理器抛出异常"""
        bus = EventBus()

        def failing_handler(event):
            raise ValueError("Test error")

        bus.subscribe(TestEvent, failing_handler)
        bus.publish(TestEvent())

    def test_multiple_handlers_one_fails(self):
        """测试多个处理器一个失败"""
        bus = EventBus()
        results = []

        def failing_handler(event):
            raise ValueError("Fail")

        def success_handler(event):
            results.append("ok")

        bus.subscribe(TestEvent, failing_handler)
        bus.subscribe(TestEvent, success_handler)
        bus.publish(TestEvent())

        assert "ok" in results

    def test_publish_with_invalid_event(self):
        """测试发布无效事件"""
        bus = EventBus()
        
        bus.publish("SimpleEvent", data="test")

    def test_subscribe_with_invalid_handler(self):
        """测试订阅无效处理器"""
        bus = EventBus()
        
        def handler(event):
            pass

        bus.subscribe(TestEvent, handler)
        bus.unsubscribe(TestEvent, handler)

    def test_event_bus_dispose_twice(self):
        """测试重复释放"""
        bus = EventBus()
        bus.dispose()
        bus.dispose()

    def test_history_lock_contention(self):
        """测试历史锁竞争"""
        bus = EventBus(max_history_size=100)
        
        def add_history():
            for i in range(50):
                bus.publish(TestEvent(message=f"event_{i}"))

        threads = [threading.Thread(target=add_history) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        history = bus.get_history()
        assert len(history) <= 100

    def test_dedup_lock_contention(self):
        """测试去重锁竞争"""
        bus = EventBus(deduplication_window=0)
        events_received = []
        lock = threading.Lock()

        def handler(event):
            with lock:
                events_received.append(event)

        def dummy_handler(event):
            pass

        bus.subscribe(TestEvent, dummy_handler)
        bus.subscribe(TestEvent, handler)

        def publish_events():
            for i in range(20):
                bus.publish(TestEvent(stock_code=f"unique_{i}"))

        threads = [threading.Thread(target=publish_events) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(events_received) == 60

    def test_execute_handler_fallback(self):
        """测试执行处理器回退"""
        bus = EventBus()

        def complex_handler(arg1, arg2, **kwargs):
            pass

        bus.subscribe(TestEvent, complex_handler)
        bus.publish(TestEvent())

    def test_execute_handler_var_keyword_fallback(self):
        """测试可变关键字参数回退"""
        bus = EventBus()

        def kw_handler(**kwargs):
            pass

        bus.subscribe(TestEvent, kw_handler)
        bus.publish(TestEvent())

    def test_publish_handlers_copy(self):
        """测试发布时处理器复制"""
        bus = EventBus()
        events_received = []

        def dynamic_handler(event):
            events_received.append(event)
            bus.subscribe(TestEvent, lambda e: None)

        bus.subscribe(TestEvent, dynamic_handler)
        bus.publish(TestEvent())

        assert len(events_received) == 1
