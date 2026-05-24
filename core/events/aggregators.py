#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
事件聚合器模块

提供事件聚合功能，用于合并高频同类事件，减少系统负载。

核心功能：
1. 时间窗口聚合 - 在指定时间窗口内合并同类事件
2. 数量阈值聚合 - 达到指定数量时触发处理
3. 条件聚合 - 满足特定条件时触发
4. 策略信号聚合 - 针对交易信号的专用聚合器

适用场景：
- 多个策略同时发出信号，需要合并展示
- 高频市场数据流需要节流处理
- UI更新需要限制频率
"""

import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Type, Generic, TypeVar
from collections import defaultdict, deque
from enum import Enum
from loguru import logger

from .types import BaseEvent, EventType

T = TypeVar('T', bound=BaseEvent)


class AggregationStrategy(Enum):
    """聚合策略"""
    TIME_WINDOW = "time_window"       # 时间窗口聚合
    COUNT_THRESHOLD = "count"         # 数量阈值聚合
    TIME_OR_COUNT = "time_or_count"   # 时间或数量任一满足即触发
    TIME_AND_COUNT = "time_and_count" # 时间和数量都满足才触发
    CONDITIONAL = "conditional"       # 条件聚合


@dataclass
class AggregationConfig:
    """聚合配置"""
    strategy: AggregationStrategy = AggregationStrategy.TIME_OR_COUNT
    window_ms: int = 100              # 聚合窗口(毫秒)
    max_count: int = 10               # 最大事件数量
    flush_on_unsubscribe: bool = True # 取消订阅时刷新
    drop_extra: bool = False          # 超量时是否丢弃多余的
    condition: Optional[Callable[[T], bool]] = None  # 条件函数


@dataclass
class AggregatedResult(Generic[T]):
    """聚合结果"""
    events: List[T]
    aggregation_key: str
    duration_ms: float
    count: int
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_empty(self) -> bool:
        return len(self.events) == 0

    @property
    def first_event(self) -> Optional[T]:
        return self.events[0] if self.events else None

    @property
    def last_event(self) -> Optional[T]:
        return self.events[-1] if self.events else None


class BaseAggregator(ABC, Generic[T]):
    """事件聚合器基类"""

    def __init__(self, config: Optional[AggregationConfig] = None):
        self.config = config or AggregationConfig()
        self._events: deque = deque(maxlen=self.config.max_count + 1)
        self._first_timestamp: Optional[float] = None
        self._last_flush: float = time.time()
        self._lock = threading.RLock()
        self._handler: Optional[Callable[[AggregatedResult[T]], None]] = None
        self._enabled = True
        self._stats = {
            'total_events': 0,
            'total_batches': 0,
            'total_flushes': 0,
            'dropped_events': 0
        }

    @property
    def is_empty(self) -> bool:
        with self._lock:
            return len(self._events) == 0

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._events)

    def set_handler(self, handler: Callable[[AggregatedResult[T]], None]) -> None:
        """设置事件批处理 handler"""
        self._handler = handler

    def add(self, event: T) -> Optional[AggregatedResult[T]]:
        """添加事件，返回聚合结果（如有）"""
        if not self._enabled:
            return None

        with self._lock:
            self._stats['total_events'] += 1

            if self._first_timestamp is None:
                self._first_timestamp = time.time()

            self._events.append(event)

            result = self._check_aggregation()
            if result:
                self._stats['total_batches'] += 1
                self._events.clear()
                self._first_timestamp = None

            return result

    def flush(self) -> Optional[AggregatedResult[T]]:
        """强制刷新当前聚合的事件"""
        with self._lock:
            if len(self._events) == 0:
                return None

            self._stats['total_flushes'] += 1
            duration_ms = (time.time() - self._first_timestamp) * 1000 if self._first_timestamp else 0
            result = AggregatedResult(
                events=list(self._events),
                aggregation_key=self._get_key(),
                duration_ms=duration_ms,
                count=len(self._events)
            )
            self._events.clear()
            self._first_timestamp = None
            return result

    def get_stats(self) -> Dict[str, Any]:
        """获取聚合统计"""
        with self._lock:
            return {
                'total_events': self._stats['total_events'],
                'total_batches': self._stats['total_batches'],
                'total_flushes': self._stats['total_flushes'],
                'dropped_events': self._stats['dropped_events'],
                'current_buffer': len(self._events),
                'aggregation_rate': (
                    self._stats['total_batches'] / self._stats['total_events']
                    if self._stats['total_events'] > 0 else 0
                )
            }

    def reset_stats(self) -> None:
        """重置统计"""
        with self._lock:
            self._stats = {
                'total_events': 0,
                'total_batches': 0,
                'total_flushes': 0,
                'dropped_events': 0
            }

    def enable(self) -> None:
        """启用聚合器"""
        self._enabled = True

    def disable(self) -> None:
        """禁用聚合器"""
        self._enabled = False

    def shutdown(self) -> None:
        """关闭聚合器，刷新剩余事件"""
        self._enabled = False
        result = self.flush()
        if result and self._handler:
            try:
                self._handler(result)
            except Exception as e:
                logger.error(f"聚合器关闭时处理事件失败: {e}")

    def _check_aggregation(self) -> Optional[AggregatedResult[T]]:
        """检查是否满足聚合条件"""
        if len(self._events) == 0:
            return None

        current_time = time.time()
        duration_ms = (current_time - self._first_timestamp) * 1000 if self._first_timestamp else 0

        should_flush = False
        reason = ""

        if self.config.strategy == AggregationStrategy.TIME_WINDOW:
            should_flush = duration_ms >= self.config.window_ms
            reason = "时间窗口达到" if should_flush else ""

        elif self.config.strategy == AggregationStrategy.COUNT_THRESHOLD:
            should_flush = len(self._events) >= self.config.max_count
            reason = "数量达到阈值" if should_flush else ""

        elif self.config.strategy == AggregationStrategy.TIME_OR_COUNT:
            should_flush = (
                duration_ms >= self.config.window_ms or
                len(self._events) >= self.config.max_count
            )
            reason = "时间或数量条件满足" if should_flush else ""

        elif self.config.strategy == AggregationStrategy.TIME_AND_COUNT:
            should_flush = (
                duration_ms >= self.config.window_ms and
                len(self._events) >= self.config.max_count
            )
            reason = "时间和数量条件都满足" if should_flush else ""

        elif self.config.strategy == AggregationStrategy.CONDITIONAL:
            if self.config.condition:
                last_event = self._events[-1]
                if self.config.condition(last_event):
                    should_flush = True
                    reason = "条件满足"
            else:
                should_flush = len(self._events) >= self.config.max_count
                reason = "默认数量阈值" if should_flush else ""

        if should_flush:
            return AggregatedResult(
                events=list(self._events),
                aggregation_key=self._get_key(),
                duration_ms=duration_ms,
                count=len(self._events)
            )

        return None

    def _get_key(self) -> str:
        """获取聚合键（用于标识聚合批次）"""
        return f"{datetime.now().isoformat()}_{id(self)}"

    def _extract_key_fields(self, event: T) -> Dict[str, Any]:
        """从事件中提取用于分组的字段（子类可重写）"""
        return {}


class EventAggregator(BaseAggregator[T]):
    """通用事件聚合器"""

    def __init__(
        self,
        event_type: Type[T],
        config: Optional[AggregationConfig] = None,
        key_extractor: Optional[Callable[[T], str]] = None
    ):
        super().__init__(config)
        self.event_type = event_type
        self.key_extractor = key_extractor
        self._keyed_events: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

    def add(self, event: T) -> Optional[List[AggregatedResult[T]]]:
        """添加事件，按key分组聚合"""
        if not self._enabled or not isinstance(event, self.event_type):
            return None

        with self._lock:
            self._stats['total_events'] += 1

            key = self.key_extractor(event) if self.key_extractor else self._default_key(event)

            if self._first_timestamp is None:
                self._first_timestamp = time.time()

            self._keyed_events[key].append(event)

            results = self._check_aggregation_for_key(key)
            return results if results else None

    def flush(self, key: Optional[str] = None) -> Optional[AggregatedResult[T]]:
        """刷新指定key的事件"""
        with self._lock:
            if key:
                events = self._keyed_events.get(key, deque())
                if len(events) == 0:
                    return None

                duration_ms = (time.time() - self._first_timestamp) * 1000 if self._first_timestamp else 0
                result = AggregatedResult(
                    events=list(events),
                    aggregation_key=key,
                    duration_ms=duration_ms,
                    count=len(events)
                )
                self._keyed_events[key].clear()
                return result
            else:
                return super().flush()

    def _default_key(self, event: T) -> str:
        """默认key提取"""
        if hasattr(event, 'strategy_id'):
            return str(event.strategy_id)
        elif hasattr(event, 'event_type'):
            return event.event_type.value
        return "default"

    def _check_aggregation_for_key(self, key: str) -> List[AggregatedResult[T]]:
        """检查指定key的聚合条件"""
        events = self._keyed_events[key]
        if len(events) == 0:
            return []

        current_time = time.time()
        first_ts = getattr(self, '_first_timestamps', {}).get(key, current_time)
        duration_ms = (current_time - first_ts) * 1000

        should_flush = False
        if self.config.strategy == AggregationStrategy.TIME_OR_COUNT:
            should_flush = (
                duration_ms >= self.config.window_ms or
                len(events) >= self.config.max_count
            )
        elif self.config.strategy == AggregationStrategy.COUNT_THRESHOLD:
            should_flush = len(events) >= self.config.max_count
        elif self.config.strategy == AggregationStrategy.TIME_WINDOW:
            should_flush = duration_ms >= self.config.window_ms

        if should_flush:
            self._stats['total_batches'] += 1
            result = AggregatedResult(
                events=list(events),
                aggregation_key=key,
                duration_ms=duration_ms,
                count=len(events)
            )
            self._keyed_events[key].clear()
            return [result]

        return []

    def get_key_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取每个key的统计"""
        with self._lock:
            return {
                key: {
                    'count': len(events),
                    'first_timestamp': getattr(self, '_first_timestamps', {}).get(key, None)
                }
                for key, events in self._keyed_events.items()
            }


class SignalAggregator(BaseAggregator):
    """策略信号聚合器 - 专用于交易信号事件

    功能：
    - 按策略ID分组聚合信号
    - 支持按信号类型细分
    - 自动合并同类信号
    - 提供信号统计信息
    """

    def __init__(
        self,
        window_ms: int = 200,
        max_signals: int = 5,
        merge_similar: bool = True
    ):
        config = AggregationConfig(
            strategy=AggregationStrategy.TIME_OR_COUNT,
            window_ms=window_ms,
            max_count=max_signals
        )
        super().__init__(config)
        self.merge_similar = merge_similar
        self._signal_groups: Dict[str, List] = defaultdict(list)
        self._strategy_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            'buy': 0, 'sell': 0, 'hold': 0, 'total': 0
        })

    def add_signal(self, signal_event) -> Optional[AggregatedResult]:
        """添加信号事件

        Args:
            signal_event: 信号事件（包含 signals 属性）

        Returns:
            聚合结果（如有）
        """
        if not self._enabled:
            return None

        with self._lock:
            self._stats['total_events'] += 1

            signals = getattr(signal_event, 'signals', [signal_event])
            strategy_id = getattr(signal_event, 'strategy_id', 'unknown')

            if self._first_timestamp is None:
                self._first_timestamp = time.time()

            if self.merge_similar:
                for signal in signals:
                    self._merge_signal(signal, strategy_id)
            else:
                self._signal_groups[strategy_id].extend(signals)

            return self._check_aggregation()

    def _merge_signal(self, signal, strategy_id: str) -> None:
        """合并相似信号"""
        group = self._signal_groups[strategy_id]

        for i, existing in enumerate(group):
            if self._are_similar(existing, signal):
                if hasattr(existing, 'confidence') and hasattr(signal, 'confidence'):
                    if signal.confidence > existing.confidence:
                        group[i] = signal
                return

        group.append(signal)
        self._update_stats(signal, strategy_id)

    def _are_similar(self, s1, s2) -> bool:
        """判断两个信号是否相似"""
        if not hasattr(s1, 'signal_type') or not hasattr(s2, 'signal_type'):
            return False
        return s1.signal_type == s2.signal_type

    def _update_stats(self, signal, strategy_id: str) -> None:
        """更新统计"""
        stats = self._strategy_stats[strategy_id]
        stats['total'] += 1

        signal_type = getattr(signal, 'signal_type', 'unknown')
        if hasattr(signal_type, 'value'):
            signal_type = signal_type.value

        if signal_type in ('buy', 'BUY', 'long'):
            stats['buy'] += 1
        elif signal_type in ('sell', 'SELL', 'short', 'close_long'):
            stats['sell'] += 1
        else:
            stats['hold'] += 1

    def get_signal_stats(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """获取信号统计"""
        with self._lock:
            if strategy_id:
                stats = self._strategy_stats.get(strategy_id, {})
                return {
                    'strategy_id': strategy_id,
                    'buy_count': stats.get('buy', 0),
                    'sell_count': stats.get('sell', 0),
                    'hold_count': stats.get('hold', 0),
                    'total_count': stats.get('total', 0),
                    'aggregation_stats': self.get_stats()
                }

            return {
                'strategies': dict(self._strategy_stats),
                'aggregation_stats': self.get_stats()
            }

    def flush(self) -> Optional[AggregatedResult]:
        """刷新所有聚合的信号"""
        with self._lock:
            if not self._signal_groups:
                return None

            self._stats['total_flushes'] += 1
            all_signals = []
            for signals in self._signal_groups.values():
                all_signals.extend(signals)

            duration_ms = (time.time() - self._first_timestamp) * 1000 if self._first_timestamp else 0
            result = AggregatedResult(
                events=all_signals,
                aggregation_key="signals",
                duration_ms=duration_ms,
                count=len(all_signals)
            )

            self._signal_groups.clear()
            self._first_timestamp = None
            return result

    def _get_key(self) -> str:
        return f"signal_aggregation_{id(self)}"


class MarketDataAggregator(BaseAggregator):
    """市场数据聚合器 - 专用于K线/行情数据

    功能：
    - 聚合Tick数据到K线
    - 支持多周期聚合
    - 自动合成OHLCV数据
    """

    def __init__(
        self,
        window_ms: int = 1000,
        max_ticks: int = 100
    ):
        super().__init__(AggregationConfig(
            strategy=AggregationStrategy.TIME_OR_COUNT,
            window_ms=window_ms,
            max_count=max_ticks
        ))
        self._tick_data: Dict[str, List[Dict]] = defaultdict(list)

    def add_tick(self, symbol: str, tick_data: Dict) -> Optional[AggregatedResult]:
        """添加Tick数据"""
        if not self._enabled:
            return None

        with self._lock:
            self._stats['total_events'] += 1
            self._tick_data[symbol].append(tick_data)

            if self._first_timestamp is None:
                self._first_timestamp = time.time()

            return self._check_aggregation()

    def get_ohlcv(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取指定symbol的OHLCV数据"""
        with self._lock:
            ticks = self._tick_data.get(symbol, [])
            if not ticks:
                return None

            open_val = None
            high_val = None
            low_val = None
            close_val = None
            vol_sum = 0

            for t in ticks:
                price = t.get('price', 0)
                o = t.get('open', price)
                h = t.get('high', price)
                l = t.get('low', price)
                c = t.get('close', price)
                v = t.get('volume', 0)

                if open_val is None:
                    open_val = o
                if high_val is None or h > high_val:
                    high_val = h
                if low_val is None or l < low_val:
                    low_val = l
                close_val = c
                vol_sum += v

            return {
                'symbol': symbol,
                'open': open_val if open_val is not None else 0,
                'high': high_val if high_val is not None else 0,
                'low': low_val if low_val is not None else 0,
                'close': close_val if close_val is not None else 0,
                'volume': vol_sum,
                'tick_count': len(ticks),
                'timestamp': datetime.now().isoformat()
            }

    def flush(self, symbol: Optional[str] = None) -> AggregatedResult:
        """刷新数据"""
        with self._lock:
            if symbol:
                ticks = self._tick_data.get(symbol, [])
                self._tick_data[symbol] = []
            else:
                ticks = []
                for s in self._tick_data:
                    ticks.extend(self._tick_data[s])
                    self._tick_data[s] = []

            duration_ms = (time.time() - self._first_timestamp) * 1000 if self._first_timestamp else 0
            return AggregatedResult(
                events=ticks,
                aggregation_key=f"market_data_{symbol or 'all'}",
                duration_ms=duration_ms,
                count=len(ticks)
            )


class AggregationManager:
    """聚合器管理器 - 管理和复用多个聚合器"""

    def __init__(self):
        self._aggregators: Dict[str, BaseAggregator] = {}
        self._lock = threading.RLock()

    def create_aggregator(
        self,
        name: str,
        aggregator_type: Type[BaseAggregator],
        **kwargs
    ) -> BaseAggregator:
        """创建并注册聚合器"""
        with self._lock:
            if name in self._aggregators:
                logger.warning(f"聚合器 {name} 已存在，将被替换")
                old = self._aggregators[name]
                old.shutdown()

            aggregator = aggregator_type(**kwargs)
            self._aggregators[name] = aggregator
            return aggregator

    def get_aggregator(self, name: str) -> Optional[BaseAggregator]:
        """获取聚合器"""
        with self._lock:
            return self._aggregators.get(name)

    def remove_aggregator(self, name: str) -> bool:
        """移除聚合器"""
        with self._lock:
            if name in self._aggregators:
                self._aggregators[name].shutdown()
                del self._aggregators[name]
                return True
            return False

    def shutdown_all(self) -> None:
        """关闭所有聚合器"""
        with self._lock:
            for aggregator in self._aggregators.values():
                aggregator.shutdown()
            self._aggregators.clear()

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有聚合器统计"""
        with self._lock:
            return {
                name: agg.get_stats()
                for name, agg in self._aggregators.items()
            }
