from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from .event_handler import EventHandler, AsyncEventHandler
from loguru import logger
"""
事件总线模块

提供事件总线的实现，负责事件的发布、订阅和分发。
"""

import asyncio
import threading
import weakref
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union
from .events import BaseEvent, RealtimeDataEvent, TickDataEvent, OrderBookEvent, ComputedIndicatorEvent

# 为兼容性提供Event别名
Event = BaseEvent

class SimpleEventHandler:
    """简单的事件处理器包装"""

    def __init__(self, handler: Callable, name: str):
        self.handler = handler
        self.name = name

class EventBus:
    """
    事件总线

    功能：
    1. 事件发布和订阅
    2. 异步事件处理
    3. 错误处理和恢复
    4. 性能监控和统计
    5. 事件去重机制
    """

    def __init__(self, async_execution: bool = False, max_workers: int = 4, deduplication_window: float = 0.5):
        """
        初始化事件总线

        Args:
            async_execution: 是否异步执行事件处理器
            max_workers: 异步执行时的最大工作线程数
            deduplication_window: 事件去重时间窗口（秒）
        """
        self._handlers: Dict[str, List[SimpleEventHandler]] = {}
        self._global_handlers: List[SimpleEventHandler] = []
        self._lock = Lock()

        # 异步执行配置
        self._async_execution = async_execution
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers) if async_execution else None
        self._active_futures = set()

        # 事件去重机制
        self._deduplication_window = deduplication_window
        self._recent_events: Dict[str, float] = {}  # 事件键 -> 时间戳
        self._dedup_lock = Lock()

        # 性能统计
        self._stats = {
            'events_published': 0,
            'events_handled': 0,
            'events_deduplicated': 0,
            'handlers_registered': 0,
            'errors': 0
        }

        logger.info(
            f"Event bus initialized (async={async_execution}, dedup_window={deduplication_window}s)")

    def _get_event_key(self, event: Union[BaseEvent, str], **kwargs) -> str:
        """
        生成事件的唯一键，用于去重

        Args:
            event: 事件实例或事件名称
            **kwargs: 事件参数

        Returns:
            事件的唯一键
        """
        if isinstance(event, str):
            event_name = event
            # 对于字符串事件，使用事件名称和主要参数生成键
            key_parts = [event_name]
            if 'stock_code' in kwargs:
                key_parts.append(f"stock:{kwargs['stock_code']}")
            if 'chart_type' in kwargs:
                key_parts.append(f"chart:{kwargs['chart_type']}")
            return "_".join(key_parts)
        else:
            event_name = event.__class__.__name__
            key_parts = [event_name]

            # 根据事件类型添加关键属性
            if hasattr(event, 'stock_code'):
                key_parts.append(f"stock:{event.stock_code}")
            if hasattr(event, 'chart_type'):
                key_parts.append(f"chart:{event.chart_type}")
            if hasattr(event, 'period'):
                key_parts.append(f"period:{event.period}")
            if hasattr(event, 'analysis_type'):
                key_parts.append(f"analysis:{event.analysis_type}")

            return "_".join(key_parts)

    def _should_deduplicate(self, event_key: str) -> bool:
        """
        检查事件是否应该被去重

        Args:
            event_key: 事件键

        Returns:
            是否应该去重
        """
        with self._dedup_lock:
            current_time = time.time()

            # 清理过期的事件记录
            expired_keys = []
            for key, timestamp in self._recent_events.items():
                if current_time - timestamp > self._deduplication_window:
                    expired_keys.append(key)

            for key in expired_keys:
                del self._recent_events[key]

            # 检查当前事件是否在去重窗口内
            if event_key in self._recent_events:
                time_diff = current_time - self._recent_events[event_key]
                if time_diff < self._deduplication_window:
                    logger.debug(
                        f"Event {event_key} deduplicated (time_diff: {time_diff:.3f}s)")
                    self._stats['events_deduplicated'] += 1
                    return True

            # 记录当前事件
            self._recent_events[event_key] = current_time
            return False

    def subscribe(self, event_type: Union[Type[BaseEvent], str], handler: Callable[[BaseEvent], None]) -> None:
        """
        订阅事件

        Args:
            event_type: 事件类型或事件名称字符串
            handler: 事件处理函数
        """
        with self._lock:
            # 处理字符串类型的事件名称
            if isinstance(event_type, str):
                event_name = event_type
            else:
                event_name = event_type.__name__

            if event_name not in self._handlers:
                self._handlers[event_name] = []

            # 创建处理器包装
            handler_wrapper = SimpleEventHandler(
                handler, getattr(handler, '__name__', str(handler)))
            self._handlers[event_name].append(handler_wrapper)

            self._stats['handlers_registered'] += 1
            logger.debug(f"Subscribed {handler_wrapper.name} to {event_name}")

    def subscribe_global(self,
                         handler: Callable[[BaseEvent], None],
                         priority: int = 0) -> None:
        """
        全局订阅所有事件

        Args:
            handler: 事件处理器
            priority: 优先级
        """
        with self._lock:
            handler_wrapper = SimpleEventHandler(
                handler, getattr(handler, '__name__', str(handler)))
            self._global_handlers.append(handler_wrapper)

            logger.debug(f"Subscribed {handler_wrapper.name} to all events")

    def unsubscribe(self, event_type: Union[Type[BaseEvent], str], handler: Callable[[BaseEvent], None]) -> None:
        """
        取消订阅事件

        Args:
            event_type: 事件类型或事件名称字符串
            handler: 事件处理函数
        """
        with self._lock:
            # 处理字符串类型的事件名称
            if isinstance(event_type, str):
                event_name = event_type
            else:
                event_name = event_type.__name__

            if event_name in self._handlers:
                # 移除匹配的处理器
                self._handlers[event_name] = [
                    h for h in self._handlers[event_name]
                    if h.handler != handler
                ]

                # 如果没有处理器了，删除事件类型
                if not self._handlers[event_name]:
                    del self._handlers[event_name]

                handler_name = getattr(handler, '__name__', str(handler))
                logger.debug(f"Unsubscribed {handler_name} from {event_name}")

    def unsubscribe_global(self, handler: Callable[[BaseEvent], None]) -> bool:
        """
        取消全局订阅

        Args:
            handler: 事件处理器

        Returns:
            是否成功取消订阅
        """
        with self._lock:
            for h in self._global_handlers:
                if h.handler == handler:
                    self._global_handlers.remove(h)
                    logger.debug(f"Unsubscribed {h.name} from all events")
                    return True
            return False

    def publish(self, event: Union[BaseEvent, str], **kwargs) -> None:
        """
        发布事件

        Args:
            event: 事件实例或事件名称字符串
            **kwargs: 事件参数（当event为字符串时使用）
        """
        # 生成事件键并检查是否需要去重
        event_key = self._get_event_key(event, **kwargs)
        if self._should_deduplicate(event_key):
            return

        # 在锁内准备事件和处理器列表
        handlers_to_execute = []
        event_obj = None
        event_name = None

        with self._lock:
            # 处理字符串类型的事件名称
            if isinstance(event, str):
                event_name = event
                # 创建一个简单的事件对象
                event_obj = type('Event', (), kwargs)()
                event_obj.event_type = event_name
            else:
                event_name = event.__class__.__name__
                event_obj = event

            if event_name not in self._handlers:
                # logger.debug(f"No handlers for event: {event_name}") # 注释掉，避免过多日志
                return

            # 获取处理器列表的副本，避免在迭代时修改
            handlers_to_execute = self._handlers[event_name].copy()

            self._stats['events_published'] += 1
            # logger.debug(f"Publishing {event_name} to {len(handlers_to_execute)} handlers")

        # 在锁外执行所有处理器，避免死锁
        for handler_wrapper in handlers_to_execute:
            try:
                # 检查处理器是否是异步函数
                if asyncio.iscoroutinefunction(handler_wrapper.handler):
                    # 如果是协程，使用asyncio.create_task在事件循环中调度
                    asyncio.create_task(handler_wrapper.handler(event_obj))
                else:
                    # 否则，同步执行
                    handler_wrapper.handler(event_obj)

                self._stats['events_handled'] += 1

            except Exception as e:
                logger.error(
                    f"Error in event handler {handler_wrapper.name}: {e}")
                self._stats['errors'] += 1

                # 发布错误事件
                if event_name != 'error':  # 避免无限递归
                    try:
                        error_event = type('ErrorEvent', (), {
                            'error': e,
                            'original_event': event_obj,
                            'handler_name': handler_wrapper.name
                        })()
                        # 递归调用时也要避免死锁
                        self.publish(error_event)
                    except:
                        pass  # 忽略错误事件发布失败

    async def publish_async(self, event: BaseEvent) -> List[Any]:
        """
        异步发布事件

        Args:
            event: 要发布的事件

        Returns:
            所有处理器的处理结果列表
        """
        # 暂时使用同步实现
        return self.publish(event)

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        等待所有异步事件处理完成

        Args:
            timeout: 超时时间（秒）

        Returns:
            是否所有事件都处理完成
        """
        if not self._async_execution or not self._executor:
            return True

        try:
            # 等待所有活跃的future完成
            for future in list(self._active_futures):
                future.result(timeout=timeout)
            return True

        except Exception as e:
            logger.error(f"Error waiting for event completion: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        获取性能统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            return {
                **self._stats,
                'active_handlers': sum(len(handlers) for handlers in self._handlers.values()),
                'global_handlers': len(self._global_handlers),
                'event_types': len(self._handlers),
                'active_futures': len(self._active_futures) if self._async_execution else 0
            }

    def clear_stats(self) -> None:
        """清空统计信息"""
        with self._lock:
            self._stats = {
                'events_published': 0,
                'events_handled': 0,
                'handlers_registered': 0,
                'errors': 0
            }

    def dispose(self) -> None:
        """释放资源"""
        try:
            # 等待所有异步任务完成
            if self._async_execution:
                self.wait_for_completion(timeout=5.0)

            # 关闭线程池
            if self._executor:
                self._executor.shutdown(wait=True)

            # 清空处理器
            with self._lock:
                self._handlers.clear()
                self._global_handlers.clear()

            logger.info("Event bus disposed")

        except Exception as e:
            logger.error(f"Error disposing event bus: {e}")

    def __len__(self) -> int:
        """返回已注册的处理器总数"""
        with self._lock:
            return sum(len(handlers) for handlers in self._handlers.values()) + len(self._global_handlers)

    def __repr__(self) -> str:
        """返回事件总线的字符串表示"""
        return f"EventBus(handlers={len(self)}, async={self._async_execution})"

# 全局事件总线实例
_global_event_bus: Optional[EventBus] = None
_bus_lock = threading.Lock()

def get_event_bus(name: str = "default") -> EventBus:
    """
    获取事件总线实例

    Args:
        name: 事件总线名称

    Returns:
        事件总线实例
    """
    global _global_event_bus

    with _bus_lock:
        if _global_event_bus is None:
            _global_event_bus = EventBus()
        return _global_event_bus

def set_event_bus(event_bus: EventBus) -> None:
    """
    设置全局事件总线

    Args:
        event_bus: 事件总线实例
    """
    global _global_event_bus

    with _bus_lock:
        _global_event_bus = event_bus
