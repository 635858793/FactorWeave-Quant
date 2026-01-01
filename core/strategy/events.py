"""
策略事件模块

定义策略相关的事件类型和便捷函数。

功能：
- 策略生命周期事件
- 信号生成事件
- 事件指标统计
- 便捷发布函数

此模块与 core.events 集成，策略相关事件应使用此模块。
"""

from loguru import logger
from typing import Dict, List, Any, Optional
from datetime import datetime
import threading

from core.events import (
    EventPriority,
    EventType,
    EventFilter,
    BaseEvent,
    StrategyStartedEvent,
    StrategyStoppedEvent,
    StrategyPausedEvent,
    StrategyResumedEvent,
    SignalGeneratedEvent,
    PerformanceUpdatedEvent,
    StrategyErrorEvent,
    get_event_bus,
)

_event_metrics: Dict[str, int] = {
    'strategy_starts': 0,
    'strategy_stops': 0,
    'signals_generated': 0,
    'trades_executed': 0,
    'errors_occurred': 0
}
_metrics_lock: Optional[threading.Lock] = None

def _get_lock() -> threading.Lock:
    global _metrics_lock
    if _metrics_lock is None:
        _metrics_lock = threading.Lock()
    return _metrics_lock

def publish_strategy_event(event: BaseEvent) -> None:
    """发布策略事件的便捷函数"""
    try:
        bus = get_event_bus()
        if bus:
            bus.publish(event)
            _update_metrics(event)
    except Exception as e:
        logger.warning(f"发布策略事件失败: {e}")

def _update_metrics(event: BaseEvent) -> None:
    """更新事件指标"""
    lock = _get_lock()
    with lock:
        if hasattr(event, 'strategy_id'):
            if hasattr(event, 'signals'):
                _event_metrics['signals_generated'] += len(getattr(event, 'signals', []))
            if hasattr(event, 'trade_result'):
                _event_metrics['trades_executed'] += 1
            if hasattr(event, 'error_message'):
                _event_metrics['errors_occurred'] += 1

def get_event_metrics() -> Dict[str, Any]:
    """获取事件指标的便捷函数"""
    lock = _get_lock()
    with lock:
        return {
            'strategy_starts': _event_metrics['strategy_starts'],
            'strategy_stops': _event_metrics['strategy_stops'],
            'signals_generated': _event_metrics['signals_generated'],
            'trades_executed': _event_metrics['trades_executed'],
            'errors_occurred': _event_metrics['errors_occurred']
        }

def reset_event_metrics() -> None:
    """重置事件指标"""
    global _event_metrics
    lock = _get_lock()
    with lock:
        _event_metrics = {
            'strategy_starts': 0,
            'strategy_stops': 0,
            'signals_generated': 0,
            'trades_executed': 0,
            'errors_occurred': 0
        }

def create_strategy_started_event(
    strategy_id: str,
    strategy_name: str,
    parameters: Dict[str, Any] = None
) -> StrategyStartedEvent:
    """创建策略启动事件"""
    return StrategyStartedEvent(
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        parameters=parameters or {}
    )

def create_strategy_stopped_event(
    strategy_id: str,
    reason: str = "",
    performance: Dict[str, Any] = None
) -> StrategyStoppedEvent:
    """创建策略停止事件"""
    return StrategyStoppedEvent(
        strategy_id=strategy_id,
        reason=reason,
        performance=performance
    )

def create_signal_generated_event(
    strategy_id: str,
    strategy_name: str,
    signals: List[Dict[str, Any]],
    symbol: str = ""
) -> SignalGeneratedEvent:
    """创建信号生成事件"""
    return SignalGeneratedEvent(
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        signals=signals,
        symbol=symbol
    )

def create_strategy_error_event(
    strategy_id: str,
    error_message: str,
    error: Exception = None,
    stack_trace: str = None
) -> StrategyErrorEvent:
    """创建策略错误事件"""
    return StrategyErrorEvent(
        strategy_id=strategy_id,
        error_message=error_message,
        error=error,
        stack_trace=stack_trace
    )

def get_strategy_event_types() -> List[EventType]:
    """获取所有策略相关的事件类型"""
    return [
        EventType.STRATEGY_STARTED,
        EventType.STRATEGY_STOPPED,
        EventType.STRATEGY_PAUSED,
        EventType.STRATEGY_RESUMED,
        EventType.STRATEGY_ERROR,
        EventType.SIGNAL_GENERATED,
        EventType.PERFORMANCE_UPDATED,
    ]
