"""
事件总线模块

提供事件总线的实现，负责事件的发布、订阅和分发。
"""

from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from .event_handler import EventHandler, AsyncEventHandler
from loguru import logger
import asyncio
import inspect
import threading
import weakref
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union
from .types import BaseEvent, EventPriority, EventFilter, RealtimeDataEvent, TickDataEvent, OrderBookEvent

Event = BaseEvent

class SimpleEventHandler:
    """简单的事件处理器包装"""

    def __init__(self, handler: Callable, name: str, priority: int = 0):
        self.handler = handler
        self.name = name
        self.priority = priority

class EventBus:
    """
    事件总线

    功能：
    1. 事件发布和订阅
    2. 异步事件处理
    3. 错误处理和恢复
    4. 性能监控和统计
    5. 事件去重机制
    6. 优先级支持
    7. 事件过滤
    8. 事件历史
    """

    def __init__(self, async_execution: bool = False, max_workers: int = 4, deduplication_window: float = 0.5,
                 enable_history: bool = True, max_history_size: int = 1000):
        """
        初始化事件总线

        Args:
            async_execution: 是否异步执行事件处理器
            max_workers: 异步执行时的最大工作线程数
            deduplication_window: 事件去重时间窗口（秒）
            enable_history: 是否启用事件历史
            max_history_size: 最大历史事件数量
        """
        self._handlers: Dict[str, List[SimpleEventHandler]] = {}
        self._global_handlers: List[SimpleEventHandler] = []
        self._lock = Lock()
        self._stats_lock = Lock()  # R238-P1-2: 统计专用锁 (R100-F "锁独立" 铁律), 禁止与其他锁嵌套

        self._async_execution = async_execution
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers) if async_execution else None
        self._active_futures = set()
        self._futures_lock = Lock()

        self._deduplication_window = deduplication_window
        self._recent_events: Dict[str, float] = {}
        self._dedup_lock = Lock()

        self._stats = {
            'events_published': 0,
            'events_handled': 0,
            'events_deduplicated': 0,
            'handlers_registered': 0,
            'errors': 0
        }

        self._enable_history = enable_history
        self._max_history_size = max_history_size
        self._event_history: deque = deque(maxlen=max_history_size)
        self._history_lock = Lock()

        self._error_recursion_depth = 0
        self._max_error_recursion = 3
        self._event_key_cache: Dict[str, Set[str]] = defaultdict(set)

        self._cleanup_counter = 0
        self._CLEANUP_INTERVAL = 200
        self._orphan_removed_total = 0

        # R238-NEW-P0-C 修复 (2026-08-01): 重建事件类型注册基座
        # Why: R222/R234-G/R236-D 声称的 register_event_type() 在 EventBus 中从未存在
        #      (R157 曾实现后物理删除), R8 §8.1 铁律 #1 双轨注册失去落地基础
        # Fix: 重建 _event_types 注册表 + register_event_type() + publish 未注册 warning
        # TDD: tests/test_r238_a_eventbus_register_event_type.py
        self._event_types: Set[str] = set()
        self._event_types_lock = threading.Lock()

        logger.info(
            f"Event bus initialized (async={async_execution}, dedup_window={deduplication_window}s, history={enable_history})")

    def _get_event_key(self, event: Union[BaseEvent, str], **kwargs) -> str:
        """生成事件的唯一键，用于去重（优化版本）"""
        if isinstance(event, str):
            event_name = event
            key_parts = [event_name]
            for k, v in sorted(kwargs.items()):
                if isinstance(v, (str, int, float, bool, type(None))):
                    key_parts.append(f"{k}={v}")
                elif hasattr(v, 'shape'):
                    key_parts.append(f"{k}=DataFrame({v.shape})")
                else:
                    key_parts.append(f"{k}={type(v).__name__}")
            return ":".join(key_parts)
        else:
            event_name = event.__class__.__name__
            key_parts = [event_name]

            stock_code = getattr(event, 'stock_code', None)
            if stock_code:
                key_parts.append(f"s:{stock_code}")

            chart_type = getattr(event, 'chart_type', None)
            if chart_type:
                key_parts.append(f"c:{chart_type}")

            period = getattr(event, 'period', None)
            if period:
                key_parts.append(f"p:{period}")

            # 去重键增加 time_range 维度:
            # 原 key 不含 time_range, 同一股票同周期但不同时间范围的请求
            # 在 0.5s 窗口内会互相误伤被去重丢弃
            time_range = getattr(event, 'time_range', None)
            if time_range:
                key_parts.append(f"t:{time_range}")

            analysis_type = getattr(event, 'analysis_type', None)
            if analysis_type:
                key_parts.append(f"a:{analysis_type}")

            # R243-B-003 (2026-08-04): 资源告警去重键增加 alert_id 维度
            # Why: ResourceAlertEvent 事件仅含 alert 属性, 无 stock_code/chart_type/period/
            #      analysis_type, key 恒为 "ResourceAlertEvent" -> 同轮多资源超阈值
            #      (CPU/MEMORY/DISK, resource_monitor.py:262-272) 在 0.5s 去重窗口内互相误伤
            # Fix: 从 event.alert.alert_id 提取唯一键维度
            alert = getattr(event, 'alert', None)
            alert_id = getattr(alert, 'alert_id', None)
            if alert_id:
                key_parts.append(f"alert_id:{alert_id}")

            # R282: 通用去重指纹（可选）——事件定义 dedup_fingerprint 属性时参与去重键。
            # 用于 IndicatorChangedEvent：改参后的指标事件带不同指纹，0.5s 窗口内不被
            # 同类型事件误吞；未定义该属性的既有事件 getattr 默认 None，行为完全不变。
            fingerprint = getattr(event, 'dedup_fingerprint', None)
            if fingerprint:
                key_parts.append(f"fp:{fingerprint}")

            return ":".join(key_parts)

    def _should_deduplicate(self, event_key: str) -> bool:
        """检查事件是否应该被去重"""
        deduplicate = False
        with self._dedup_lock:
            current_time = time.time()
            expired_threshold = current_time - self._deduplication_window

            if self._recent_events.get(event_key, 0) > expired_threshold:
                deduplicate = True
            else:
                self._recent_events[event_key] = current_time

                if len(self._recent_events) > 2000:
                    self._recent_events = {
                        k: v for k, v in self._recent_events.items()
                        if v > expired_threshold
                    }

        # R238-P1-2: 统计写点移出 _dedup_lock, 归 _stats_lock 域 (避免锁嵌套)
        if deduplicate:
            self._increment_stat('events_deduplicated')
        return deduplicate

    def _add_to_history(self, event: BaseEvent) -> None:
        """添加事件到历史记录"""
        if not self._enable_history:
            return

        with self._history_lock:
            self._event_history.append({
                'event': event,
                'timestamp': datetime.now(),
                'event_type': event.__class__.__name__
            })

    def _filter_event(self, event: BaseEvent, event_filter: Optional[EventFilter] = None) -> bool:
        """检查事件是否匹配过滤器"""
        if event_filter is None:
            return True

        return event_filter.matches(event)

    def _handle_async_task_exception(self, future):
        """处理异步任务的异常回调"""
        try:
            if future.exception():
                exc = future.exception()
                logger.error(f"Async event handler failed: {exc}")
                self._stats['errors'] += 1
                
                if self._error_recursion_depth < self._max_error_recursion:
                    try:
                        self._error_recursion_depth += 1
                        error_event = type('ErrorEvent', (), {
                            'error': exc,
                            'original_event': None,
                            'handler_name': 'async_task'
                        })()
                        self.publish(error_event)
                    except Exception as inner_e:
                        logger.error(f"Failed to publish error event: {inner_e}")
                    finally:
                        self._error_recursion_depth = max(0, self._error_recursion_depth - 1)
        except Exception as e:
            logger.error(f"Error in async task exception handler: {e}")

    def _handle_threadpool_exception(self, future):
        """处理线程池任务的异常回调"""
        try:
            exc = future.exception()
            if exc:
                logger.error(f"Threadpool event handler failed: {exc}")
                self._increment_stat('errors')

                if self._error_recursion_depth < self._max_error_recursion:
                    try:
                        self._error_recursion_depth += 1
                        error_event = type('ErrorEvent', (), {
                            'error': exc,
                            'original_event': None,
                            'handler_name': 'threadpool_task'
                        })()
                        self.publish(error_event)
                    except Exception as inner_e:
                        logger.error(f"Failed to publish error event: {inner_e}")
                    finally:
                        self._error_recursion_depth = max(0, self._error_recursion_depth - 1)
        except Exception as e:
            logger.error(f"Error in threadpool exception handler: {e}")

    def _cleanup_completed_futures(self):
        """清理已完成的任务，防止内存泄漏"""
        with self._futures_lock:
            completed = {f for f in self._active_futures if f.done()}
            self._active_futures -= completed

    def cleanup_orphan_handlers(self) -> int:
        """
        清理已销毁组件的孤儿回调处理器

        当订阅了事件的GUI组件被销毁后，其绑定的回调方法不再有效。
        此方法检测并移除这些孤儿处理器，防止内存泄漏。

        Returns:
            移除的孤儿处理器数量
        """
        removed = 0
        with self._lock:
            for event_name in list(self._handlers.keys()):
                kept = []
                for h in self._handlers[event_name]:
                    try:
                        if hasattr(h.handler, '__self__') and h.handler.__self__ is not None:
                            wr = weakref.ref(h.handler.__self__)
                            if wr() is None:
                                removed += 1
                                continue
                    except Exception:
                        pass
                    kept.append(h)
                if kept:
                    self._handlers[event_name] = kept
                else:
                    del self._handlers[event_name]

            global_kept = []
            for h in self._global_handlers:
                try:
                    if hasattr(h.handler, '__self__') and h.handler.__self__ is not None:
                        wr = weakref.ref(h.handler.__self__)
                        if wr() is None:
                            removed += 1
                            continue
                except Exception:
                    pass
                global_kept.append(h)
            self._global_handlers = global_kept

        self._orphan_removed_total += removed
        if removed > 0:
            logger.debug(f"孤儿处理器清理完成: 移除 {removed} 个 (累计 {self._orphan_removed_total})")
        return removed

    def _execute_handler(self, handler: Callable, event: BaseEvent) -> None:
        """在线程池中执行事件处理器"""
        try:
            sig = inspect.signature(handler)
            params = list(sig.parameters.values())
            
            if not params:
                handler()
            elif any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params):
                handler(**getattr(event, '__dict__', {}))
            else:
                handler(event)
        except (ValueError, TypeError) as e:
            try:
                handler(event)
            except Exception as fallback_error:
                logger.error(f"Error executing event handler: {fallback_error}")
        except Exception as e:
            logger.error(f"Error executing event handler: {e}")

    def _increment_stat(self, key: str) -> None:
        """线程安全递增统计计数 (R238-P1-2: 全部统计写点统一归 _stats_lock 域).

        修复前 _stats['...'] += 1 分散于 _lock/_dedup_lock/无锁 3 种域,
        读-改-写非原子 → 并发计数丢失, 且锁域不一致.
        """
        with self._stats_lock:
            self._stats[key] = self._stats.get(key, 0) + 1

    def _sort_handlers_by_priority(self, handlers: List[SimpleEventHandler]) -> List[SimpleEventHandler]:
        """按优先级排序处理器（优先级数值越小越先执行）"""
        return sorted(handlers, key=lambda h: getattr(h, 'priority', 0))

    def register_event_type(self, event_type: Union[Type[BaseEvent], str], source: str = 'manual') -> bool:
        """注册事件类型 (R8 §8.1 铁律 #1 双轨注册)

        R238-NEW-P0-C 重建 (2026-08-01):
        Why: R222 治理声称的双轨注册 (EventType 枚举名 + BaseEvent 子类名) 基座缺失,
             本方法恢复 EventBus 事件注册能力, publish 时对未注册事件告警.
        Fix: 支持 3 种输入 (BaseEvent 类 / 类名 str / 事件名字符串), 幂等注册.

        Args:
            event_type: BaseEvent 子类 / 类名字符串 / 事件名字符串
            source: 注册来源标识 (默认 'manual')

        Returns:
            bool: True 为新注册, False 为已存在 (幂等)
        """
        # 解析注册名: 类 → 类名, str → 原样
        if isinstance(event_type, type):
            if not (issubclass(event_type, BaseEvent) or hasattr(event_type, 'event_type')):
                logger.warning(f"register_event_type: {event_type} 不是 BaseEvent 子类, 跳过")
                return False
            type_name: str = event_type.__name__
        else:
            type_name = str(event_type)

        with self._event_types_lock:
            if type_name in self._event_types:
                return False
            self._event_types.add(type_name)
            logger.debug(f"EventBus.register_event_type: type='{type_name}' source='{source}' (total types={len(self._event_types)})")
            return True

    def subscribe(self, event_type: Union[Type[BaseEvent], str], handler: Callable[[BaseEvent], None],
                  priority: int = 0, event_filter: Optional[EventFilter] = None) -> None:
        """
        订阅事件

        Args:
            event_type: 事件类型或事件名称字符串
            handler: 事件处理函数
            priority: 处理器优先级（数值越小优先级越高）
            event_filter: 事件过滤器
        """
        with self._lock:
            if isinstance(event_type, str):
                event_name = event_type
            else:
                event_name = event_type.__name__

            if event_name not in self._handlers:
                self._handlers[event_name] = []

            handler_wrapper = SimpleEventHandler(
                handler, getattr(handler, '__name__', str(handler)), priority)
            self._handlers[event_name].append(handler_wrapper)

            logger.debug(f"Subscribed {handler_wrapper.name} to {event_name} (priority={priority})")

        # R242-A-001 修复 (2026-08-04): subscribe 自动注册事件类型
        # Why: R238-NEW-P0-C publish 未注册 warning (L487-493) 落地后, 全项目业务代码
        #      register_event_type() 零调用 → 所有有订阅者的事件 (SystemResourceUpdated 等)
        #      每次 publish 均误报 warning, 日志噪音
        # Fix: 订阅即代表业务方认可该事件类型, subscribe 时自动注册, 消除系统性误报;
        #      显式 register_event_type() 仍保留, 用于无订阅者的纯发布事件
        self.register_event_type(event_name, source='subscribe_auto')

        # R238-P1-2: 统计写点在 _lock 块外, 归 _stats_lock 域 (避免锁嵌套)
        self._increment_stat('handlers_registered')

    def subscribe_global(self, handler: Callable[[BaseEvent], None], priority: int = 0) -> None:
        """
        全局订阅所有事件

        Args:
            handler: 事件处理器
            priority: 优先级
        """
        with self._lock:
            handler_wrapper = SimpleEventHandler(
                handler, getattr(handler, '__name__', str(handler)), priority)
            self._global_handlers.append(handler_wrapper)

            logger.debug(f"Subscribed {handler_wrapper.name} to all events")

    def unsubscribe(self, event_type: Union[Type[BaseEvent], str], handler: Callable[[BaseEvent], None]) -> bool:
        """
        取消订阅事件

        Args:
            event_type: 事件类型或事件名称字符串
            handler: 事件处理函数

        Returns:
            是否成功取消订阅
        """
        with self._lock:
            if isinstance(event_type, str):
                event_name = event_type
            else:
                event_name = event_type.__name__

            if event_name in self._handlers:
                original_count = len(self._handlers[event_name])
                self._handlers[event_name] = [
                    h for h in self._handlers[event_name]
                    if h.handler != handler
                ]

                if not self._handlers[event_name]:
                    del self._handlers[event_name]

                handler_name = getattr(handler, '__name__', str(handler))
                logger.debug(f"Unsubscribed {handler_name} from {event_name}")
                return len(self._handlers.get(event_name, [])) < original_count

            return False

    def unsubscribe_global(self, handler: Callable[[BaseEvent], None]) -> bool:
        """
        取消全局订阅

        Args:
            handler: 事件处理器

        Returns:
            是否成功取消订阅
        """
        with self._lock:
            original_count = len(self._global_handlers)
            self._global_handlers = [
                h for h in self._global_handlers
                if h.handler != handler
            ]
            removed = len(self._global_handlers) < original_count
            if removed:
                handler_name = getattr(handler, '__name__', str(handler))
                logger.debug(f"Unsubscribed {handler_name} from all events")
            return removed

    def publish(self, event: Union[BaseEvent, str], **kwargs) -> None:
        """
        发布事件

        Args:
            event: 事件实例或事件名称字符串
            **kwargs: 事件参数（当event为字符串时使用）
        """
        event_key = self._get_event_key(event, **kwargs)
        if self._should_deduplicate(event_key):
            # _should_deduplicate 命中时内部已自增 events_deduplicated，
            # 此处直接输出当前累计值，避免 +1 显示偏差
            logger.warning(
                f"Event deduplicated and skipped: {event_key} "
                f"(window={self._deduplication_window}s, total_deduplicated={self._stats['events_deduplicated']})"
            )
            return

        handlers_to_execute = []
        event_obj = None
        event_name = None
        event_filter = kwargs.pop('_event_filter', None)

        with self._lock:
            if isinstance(event, str):
                event_name = event
                # kwargs 必须为实例属性 (而非类属性), 否则 event_obj.__dict__ 为空,
                # **kwargs 签名 handler (R238-P0-1) 将无法读取事件参数
                event_obj = type('Event', (), {})()
                for k, v in kwargs.items():
                    setattr(event_obj, k, v)
                event_obj.event_type = event_name
                event_obj.priority = getattr(event_obj, 'priority', EventPriority.NORMAL)
            else:
                event_name = event.__class__.__name__
                event_obj = event

            # R238-NEW-P0-C 修复 (2026-08-01): 未注册事件 warning (R8 §8.1 铁律 #1)
            # Why: R74/R79 教训 — 未注册事件 publish 触发 warning 噪音, 帮助发现 ORPHAN_PUB
            # Fix: 仅 warning 不阻断 (与 R8 §8.1 兼容), 自动注册误报则由业务方显式注册消除
            # R240-P1-3: 锁域统一 — 写 _event_types 用 _event_types_lock (L341),
            # 读 (L485) 原在 _lock 域内 → 同一数据两把锁 (子智能体 C/D 确认 P2)
            with self._event_types_lock:
                event_registered = event_name in self._event_types
            if not event_registered:
                logger.warning(
                    f"[EventBus] 未注册事件 publish: {event_name!r} — "
                    f"请用 register_event_type() 显式注册 (R8 §8.1 铁律 #1, R238-NEW-P0-C)"
                )

            handlers_to_execute = self._handlers.get(event_name, []).copy()
            handlers_to_execute.extend(self._global_handlers)

        # R238-P1-2: 统计写点在 _lock 块外, 归 _stats_lock 域 (避免锁嵌套)
        self._increment_stat('events_published')

        handlers_to_execute = self._sort_handlers_by_priority(handlers_to_execute)

        self._add_to_history(event_obj)

        if not handlers_to_execute:
            logger.debug(f"Event {event_name} published but has no registered handlers (orphan event)")

        for handler_wrapper in handlers_to_execute:
            if event_filter and not self._filter_event(event_obj, event_filter):
                continue

            try:
                if asyncio.iscoroutinefunction(handler_wrapper.handler):
                    try:
                        loop = asyncio.get_running_loop()
                        task = asyncio.create_task(handler_wrapper.handler(event_obj))
                        task.add_done_callback(self._handle_async_task_exception)
                        with self._futures_lock:
                            self._active_futures.add(task)
                    except RuntimeError:
                        _ = handler_wrapper.handler(event_obj)
                elif self._async_execution and self._executor:
                    future = self._executor.submit(self._execute_handler, handler_wrapper.handler, event_obj)
                    future.add_done_callback(self._handle_threadpool_exception)
                    with self._futures_lock:
                        self._active_futures.add(future)
                else:
                    # 同步路径: 签名适配 (R238-P0-1)
                    # 兼容 **kwargs 签名 handler (如 AccountManager 持仓同步 handler),
                    # 修复前直接 handler(event_obj) 位置调用 → TypeError → 业务静默失效
                    sig = inspect.signature(handler_wrapper.handler)
                    params = list(sig.parameters.values())
                    if not params:
                        handler_wrapper.handler()
                    elif any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params):
                        handler_wrapper.handler(**getattr(event_obj, '__dict__', {}))
                    else:
                        handler_wrapper.handler(event_obj)

                # R238-P1-2: 统计写点归 _stats_lock 域
                self._increment_stat('events_handled')

            except Exception as e:
                logger.error(
                    f"Error in event handler {handler_wrapper.name}: {e}")
                self._increment_stat('errors')

                if event_name != 'error' and self._error_recursion_depth < self._max_error_recursion:
                    try:
                        self._error_recursion_depth += 1
                        error_event = type('ErrorEvent', (), {
                            'error': e,
                            'original_event': event_obj,
                            'handler_name': handler_wrapper.name
                        })()
                        self.publish(error_event)
                    except Exception as inner_e:
                        logger.error(f"Failed to publish error event: {inner_e}")
                    finally:
                        self._error_recursion_depth = max(0, self._error_recursion_depth - 1)

        self._cleanup_completed_futures()

        self._cleanup_counter += 1
        if self._cleanup_counter % self._CLEANUP_INTERVAL == 0:
            self.cleanup_orphan_handlers()
            self._cleanup_completed_futures()

    def publish_with_filter(self, event: BaseEvent, event_filter: EventFilter) -> None:
        """
        发布带过滤器的事件

        Args:
            event: 事件实例
            event_filter: 事件过滤器
        """
        self.publish(event, _event_filter=event_filter)

    def publish_with_priority(self, event: BaseEvent, priority: EventPriority) -> None:
        """
        发布带优先级的事件

        Args:
            event: 事件实例
            priority: 事件优先级
        """
        event.priority = priority
        self.publish(event)

    def get_history(self, event_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取事件历史

        Args:
            event_type: 事件类型过滤（可选）
            limit: 最大返回数量

        Returns:
            事件历史列表
        """
        with self._history_lock:
            if event_type:
                filtered_history = [
                    h for h in self._event_history
                    if h['event_type'] == event_type
                ]
                return list(filtered_history)[-limit:]
            return list(self._event_history)[-limit:]

    def clear_history(self) -> None:
        """清空事件历史"""
        with self._history_lock:
            self._event_history.clear()
            logger.debug("Event history cleared")

    async def publish_async(self, event: BaseEvent) -> None:
        """异步发布事件（在线程池中执行以避免阻塞事件循环）"""
        import asyncio as _asyncio
        loop = _asyncio.get_running_loop()
        await loop.run_in_executor(self._executor, self.publish, event)

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """等待所有异步事件处理完成"""
        if not self._async_execution or not self._executor:
            return True

        try:
            with self._futures_lock:
                futures_snapshot = list(self._active_futures)
            import concurrent.futures
            for future in futures_snapshot:
                if isinstance(future, concurrent.futures.Future):
                    future.result(timeout=timeout)
            return True

        except Exception as e:
            logger.error(f"Error waiting for event completion: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        # R238-P1-2: 统计读点归 _stats_lock 域, 不再 _lock 内嵌套 _futures_lock (锁独立铁律)
        with self._stats_lock:
            stats_snapshot = dict(self._stats)
        with self._futures_lock:
            active_count = len(self._active_futures) if self._async_execution else 0
        with self._lock:
            active_handlers = sum(len(handlers) for handlers in self._handlers.values())
            global_handlers = len(self._global_handlers)
            event_types = len(self._handlers)
        return {
            **stats_snapshot,
            'active_handlers': active_handlers,
            'global_handlers': global_handlers,
            'event_types': event_types,
            'active_futures': active_count,
            'history_size': len(self._event_history),
            'orphan_removed_total': self._orphan_removed_total,
            'cleanup_interval': self._CLEANUP_INTERVAL,
            'cleanup_counter': self._cleanup_counter,
        }

    def clear_stats(self) -> None:
        """清空统计信息"""
        with self._stats_lock:
            self._stats = {
                'events_published': 0,
                'events_handled': 0,
                'events_deduplicated': 0,
                'handlers_registered': 0,
                'errors': 0
            }

    def dispose(self) -> None:
        """释放资源"""
        try:
            if self._async_execution:
                self.wait_for_completion(timeout=5.0)

            if self._executor:
                self._executor.shutdown(wait=True)

            with self._lock:
                self._handlers.clear()
                self._global_handlers.clear()

            with self._history_lock:
                self._event_history.clear()

            logger.info("Event bus disposed")

        except Exception as e:
            logger.error(f"Error disposing event bus: {e}")

    def __len__(self) -> int:
        """返回已注册的处理器总数"""
        with self._lock:
            return sum(len(handlers) for handlers in self._handlers.values()) + len(self._global_handlers)

    def __bool__(self) -> bool:
        """事件总线对象恒为有效引用 (R242-B-004 修复, 2026-08-04)

        Why: 存在 __len__ 而无 __bool__ 时, Python 真值语义取 len()!=0.
             总线刚创建 (0 订阅者) 时 bool(bus)==False → 全项目 30+ 处
             `if self.event_bus:` (初始化期订阅/发布判断) 全部失效,
             服务订阅从未注册 (如 aggregation_service.py:59). P0 级系统性 bug.
        Fix: 显式 __bool__ 返回 True, 使真值判断恢复为"对象是否非 None".
        """
        return True

    def __repr__(self) -> str:
        """返回事件总线的字符串表示"""
        return f"EventBus(handlers={len(self)}, async={self._async_execution}, history={self._enable_history})"

_global_event_bus: Optional[EventBus] = None
_bus_lock = threading.Lock()

def get_event_bus(name: str = "default", async_execution: bool = False, max_workers: int = 4) -> EventBus:
    """
    获取事件总线实例

    Args:
        name: 事件总线名称
        async_execution: 是否启用异步执行（默认False，同步模式保证UI更新顺序）
        max_workers: 异步执行时的最大工作线程数

    Returns:
        事件总线实例
    """
    global _global_event_bus

    with _bus_lock:
        if _global_event_bus is None:
            _global_event_bus = EventBus(
                async_execution=async_execution,
                max_workers=max_workers
            )
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
