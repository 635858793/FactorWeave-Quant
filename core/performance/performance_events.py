#!/usr/bin/env python3
"""
性能监控事件定义

定义性能监控相关的事件类型，用于事件驱动的数据更新机制
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum, auto
from loguru import logger

from core.events.types import BaseEvent


class PerformanceEventType(Enum):
    """性能事件类型"""
    # 系统监控事件
    SYSTEM_METRICS_UPDATED = auto()  # 系统指标更新
    SYSTEM_ALERT = auto()  # 系统告警

    # 策略性能事件
    STRATEGY_PERFORMANCE_UPDATED = auto()  # 策略性能更新
    STRATEGY_ALERT = auto()  # 策略告警

    # 算法优化事件
    ALGORITHM_METRICS_UPDATED = auto()  # 算法指标更新
    JIT_STATUS_UPDATED = auto()  # JIT状态更新

    # 风险控制事件
    RISK_METRICS_UPDATED = auto()  # 风险指标更新
    RISK_ALERT = auto()  # 风险告警

    # 交易执行事件
    TRADE_METRICS_UPDATED = auto()  # 交易指标更新
    ORDER_STATUS_UPDATED = auto()  # 订单状态更新

    # 系统健康事件
    HEALTH_CHECK_COMPLETED = auto()  # 健康检查完成
    HEALTH_ALERT = auto()  # 健康告警

    # 数据质量事件
    DATA_QUALITY_UPDATED = auto()  # 数据质量更新
    DATA_QUALITY_ALERT = auto()  # 数据质量告警

    # 资源监控事件
    RESOURCE_USAGE_UPDATED = auto()  # 资源使用更新
    RESOURCE_ALERT = auto()  # 资源告警

    # 通用事件
    DATA_REFRESH_REQUESTED = auto()  # 数据刷新请求
    DATA_REFRESH_COMPLETED = auto()  # 数据刷新完成


@dataclass
class SystemMetricsUpdatedEvent(BaseEvent):
    """系统指标更新事件"""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    network_sent: float = 0.0
    network_recv: float = 0.0
    gc_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': PerformanceEventType.SYSTEM_METRICS_UPDATED.name,
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'disk_percent': self.disk_percent,
            'network_sent': self.network_sent,
            'network_recv': self.network_recv,
            'gc_count': self.gc_count,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class StrategyPerformanceUpdatedEvent(BaseEvent):
    """策略性能更新事件"""
    strategy_name: str = ""
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    trade_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': PerformanceEventType.STRATEGY_PERFORMANCE_UPDATED.name,
            'strategy_name': self.strategy_name,
            'total_return': self.total_return,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'trade_count': self.trade_count,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class AlgorithmMetricsUpdatedEvent(BaseEvent):
    """算法指标更新事件"""
    algorithm_name: str = ""
    execution_time: float = 0.0
    jit_compiled: bool = False
    optimization_level: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': PerformanceEventType.ALGORITHM_METRICS_UPDATED.name,
            'algorithm_name': self.algorithm_name,
            'execution_time': self.execution_time,
            'jit_compiled': self.jit_compiled,
            'optimization_level': self.optimization_level,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class RiskMetricsUpdatedEvent(BaseEvent):
    """风险指标更新事件"""
    position_value: float = 0.0
    exposure: float = 0.0
    var: float = 0.0
    leverage: float = 0.0
    margin_level: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': PerformanceEventType.RISK_METRICS_UPDATED.name,
            'position_value': self.position_value,
            'exposure': self.exposure,
            'var': self.var,
            'leverage': self.leverage,
            'margin_level': self.margin_level,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class TradeMetricsUpdatedEvent(BaseEvent):
    """交易指标更新事件"""
    total_orders: int = 0
    pending_orders: int = 0
    filled_orders: int = 0
    cancelled_orders: int = 0
    rejected_orders: int = 0
    avg_execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': PerformanceEventType.TRADE_METRICS_UPDATED.name,
            'total_orders': self.total_orders,
            'pending_orders': self.pending_orders,
            'filled_orders': self.filled_orders,
            'cancelled_orders': self.cancelled_orders,
            'rejected_orders': self.rejected_orders,
            'avg_execution_time': self.avg_execution_time,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class HealthCheckCompletedEvent(BaseEvent):
    """健康检查完成事件"""
    component_name: str = ""
    status: str = "healthy"  # 'healthy', 'warning', 'error'
    check_time: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': PerformanceEventType.HEALTH_CHECK_COMPLETED.name,
            'component_name': self.component_name,
            'status': self.status,
            'check_time': self.check_time,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class DataQualityUpdatedEvent(BaseEvent):
    """数据质量更新事件"""
    data_source: str = ""
    completeness: float = 0.0
    accuracy: float = 0.0
    timeliness: float = 0.0
    consistency: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': PerformanceEventType.DATA_QUALITY_UPDATED.name,
            'data_source': self.data_source,
            'completeness': self.completeness,
            'accuracy': self.accuracy,
            'timeliness': self.timeliness,
            'consistency': self.consistency,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ResourceUsageUpdatedEvent(BaseEvent):
    """资源使用更新事件"""
    resource_type: str = ""  # 'cpu', 'memory', 'disk', 'network'
    value: float = 0.0
    unit: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': PerformanceEventType.RESOURCE_USAGE_UPDATED.name,
            'resource_type': self.resource_type,
            'value': self.value,
            'unit': self.unit,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class DataRefreshRequestedEvent(BaseEvent):
    """数据刷新请求事件"""
    tab_name: str = ""
    refresh_type: str = "full"  # 'full', 'incremental'
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': PerformanceEventType.DATA_REFRESH_REQUESTED.name,
            'tab_name': self.tab_name,
            'refresh_type': self.refresh_type,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class DataRefreshCompletedEvent(BaseEvent):
    """数据刷新完成事件"""
    tab_name: str = ""
    refresh_type: str = "full"  # 'full', 'incremental'
    success: bool = True
    error_message: Optional[str] = None
    refresh_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': PerformanceEventType.DATA_REFRESH_COMPLETED.name,
            'tab_name': self.tab_name,
            'refresh_type': self.refresh_type,
            'success': self.success,
            'error_message': self.error_message,
            'refresh_time': self.refresh_time,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class PerformanceAlertEvent(BaseEvent):
    """性能告警事件"""
    alert_type: str = ""  # 'system', 'strategy', 'risk', 'trade', 'health', 'data_quality', 'resource'
    severity: str = "info"  # 'info', 'warning', 'error', 'critical'
    metric_name: str = ""
    current_value: float = 0.0
    threshold_value: float = 0.0
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': 'PERFORMANCE_ALERT',
            'alert_type': self.alert_type,
            'severity': self.severity,
            'metric_name': self.metric_name,
            'current_value': self.current_value,
            'threshold_value': self.threshold_value,
            'message': self.message,
            'timestamp': self.timestamp.isoformat()
        }
