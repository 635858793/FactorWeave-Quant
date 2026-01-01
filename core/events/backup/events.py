"""
事件定义模块

定义系统中使用的各种事件类型，所有事件都继承自BaseEvent。
"""

from enum import Enum
from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Union
import uuid

from ..plugin_types import AssetType


class EventType(Enum):
    """事件类型枚举"""
    # 图表相关事件
    CHART_CREATED = "chart_created"
    CHART_UPDATED = "chart_updated"
    CHART_DATA_UPDATED = "chart_data_updated"
    CHART_REMOVED = "chart_removed"
    CHART_RESIZED = "chart_resized"
    
    # 数据相关事件
    DATA_LOADED = "data_loaded"
    DATA_UPDATED = "data_updated"
    DATA_ERROR = "data_error"
    REAL_TIME_DATA = "real_time_data"
    
    # 性能相关事件
    PERFORMANCE_OPTIMIZED = "performance_optimized"
    PERFORMANCE_DEGRADED = "performance_degraded"
    PERFORMANCE_METRICS_UPDATED = "performance_metrics_updated"
    
    # UI相关事件
    UI_UPDATE = "ui_update"
    THEME_CHANGED = "theme_changed"
    ASSET_SELECTED = "asset_selected"
    
    # 交易相关事件
    TRADE_EXECUTED = "trade_executed"
    ORDER_PLACED = "order_placed"
    POSITION_UPDATED = "position_updated"
    
    # AI/ML相关事件
    MODEL_TRAINED = "model_trained"
    PREDICTION_MADE = "prediction_made"
    ACCURACY_UPDATED = "accuracy_updated"
    
    # 系统事件
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"
    SYSTEM_INFO = "system_info"


@dataclass
class BaseEvent(ABC):
    """
    事件基类

    所有系统事件都应该继承此类。
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """事件创建后的初始化处理"""
        if not self.source:
            self.source = self.__class__.__name__


@dataclass
class AssetSelectedEvent(BaseEvent):
    """
    资产选择事件（通用）

    当用户选择任意类型资产时触发，支持股票、加密货币、期货等。
    """
    symbol: str = ""                        # 交易代码
    name: str = ""                          # 资产名称
    asset_type: AssetType = AssetType.STOCK_A  # 资产类型（默认A股）
    market: str = ""                        # 市场
    period: str = ""                        # 周期：日线、周线、月线等
    time_range: str = ""                    # 时间范围：最近7天、最近30天等
    chart_type: str = ""                    # 图表类型：K线图、分时图等
    kline_data: Optional[Any] = None        # ✅ 优化：可选的K线数据（避免重复查询）

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'symbol': self.symbol,
            'name': self.name,
            'asset_type': self.asset_type.value if isinstance(self.asset_type, AssetType) else self.asset_type,
            'market': self.market,
            'period': self.period,
            'time_range': self.time_range,
            'chart_type': self.chart_type,
            # 注意：kline_data不序列化到data字典，避免内存问题
            'has_kline_data': self.kline_data is not None
        })


@dataclass
class StockSelectedEvent(AssetSelectedEvent):
    """
    股票选择事件（向后兼容）

    继承自AssetSelectedEvent，保持与现有代码的兼容性。
    """
    stock_code: str = ""  # 向后兼容属性
    stock_name: str = ""  # 向后兼容属性

    def __init__(self, stock_code: str = "", stock_name: str = "",
                 market: str = "", period: str = "", time_range: str = "",
                 chart_type: str = "", kline_data: Optional[Any] = None, **kwargs):
        # ✅ 优化：接受kline_data参数，避免重复查询
        # 使用父类构造函数，映射股票特定字段到通用字段
        super().__init__(
            symbol=stock_code,
            name=stock_name,
            asset_type=AssetType.STOCK_A,
            market=market,
            period=period,
            time_range=time_range,
            chart_type=chart_type,
            kline_data=kline_data,
            **kwargs
        )

        # 保持向后兼容的属性
        self.stock_code = stock_code
        self.stock_name = stock_name

    def __post_init__(self):
        super().__post_init__()
        # 确保向后兼容的数据字段
        self.data.update({
            'stock_code': self.stock_code,
            'stock_name': self.stock_name
        })


@dataclass
class AssetDataReadyEvent(BaseEvent):
    """
    资产数据就绪事件（通用）

    当任意类型资产的数据加载完成时触发。
    """
    symbol: str = ""
    name: str = ""
    asset_type: AssetType = AssetType.STOCK_A
    market: str = ""
    data_type: str = "kline"
    data: Any = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if not isinstance(self.data, dict):
            self.data = {'raw_data': self.data}
        
        BaseEvent.__post_init__(self)
        self.data.update({
            'symbol': self.symbol,
            'name': self.name,
            'asset_type': self.asset_type.value if isinstance(self.asset_type, AssetType) else self.asset_type,
            'market': self.market,
            'data_type': self.data_type
        })


@dataclass
class UIDataReadyEvent(AssetDataReadyEvent):
    """
    UI数据就绪事件（向后兼容）

    继承自AssetDataReadyEvent，保持与现有UI代码的兼容性。
    """
    stock_code: str = ""
    stock_name: str = ""
    kline_data: Any = None
    ui_data: Dict[str, Any] = field(default_factory=dict)

    def __init__(self, stock_code: str = "", stock_name: str = "",
                 kline_data: Any = None, market: str = "", ui_data: Dict[str, Any] = None, **kwargs):
        self.stock_code = stock_code
        self.stock_name = stock_name
        self.kline_data = kline_data
        self.ui_data = ui_data or {}
        
        _data = kline_data
        if _data is None or not isinstance(_data, dict):
            _data = {'raw_data': _data} if _data is not None else {}
        
        AssetDataReadyEvent.__init__(
            self,
            symbol=stock_code,
            name=stock_name,
            asset_type=AssetType.STOCK_A,
            market=market,
            data_type="kline",
            data=_data,
            **kwargs
        )

    def __post_init__(self):
        if self.data is None:
            self.data = {}
        self.data.update({
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'kline_data': self.kline_data,
            'ui_data': self.ui_data
        })


@dataclass
class ChartUpdateEvent(BaseEvent):
    """
    图表更新事件

    当图表需要更新时触发。
    """
    stock_code: str = ""
    chart_type: str = ""
    period: str = ""
    indicators: list = field(default_factory=list)
    time_range: int = -365

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'stock_code': self.stock_code,
            'chart_type': self.chart_type,
            'period': self.period,
            'indicators': self.indicators,
            'time_range': self.time_range
        })


@dataclass
class AnalysisCompleteEvent(BaseEvent):
    """
    分析完成事件

    当股票分析完成时触发。
    """
    stock_code: str = ""
    analysis_type: str = ""
    results: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'stock_code': self.stock_code,
            'analysis_type': self.analysis_type,
            'results': self.results
        })


@dataclass
class DataUpdateEvent(BaseEvent):
    """
    数据更新事件

    当数据发生更新时触发。
    """
    data_type: str = ""
    stock_code: str = ""
    update_info: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'data_type': self.data_type,
            'stock_code': self.stock_code,
            'update_info': self.update_info
        })


@dataclass
class ErrorEvent(BaseEvent):
    """
    错误事件

    当系统发生错误时触发。
    """
    error_type: str = ""
    error_message: str = ""
    error_traceback: str = ""
    severity: str = "error"  # error, warning, info

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'error_type': self.error_type,
            'error_message': self.error_message,
            'error_traceback': self.error_traceback,
            'severity': self.severity
        })


@dataclass
class UIUpdateEvent(BaseEvent):
    """
    UI更新事件

    当UI需要更新时触发。
    """
    component: str = ""
    action: str = ""
    update_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'component': self.component,
            'action': self.action,
            'update_data': self.update_data
        })


@dataclass
class ThemeChangedEvent(BaseEvent):
    """
    主题变更事件

    当系统主题发生变更时触发。
    """
    theme_name: str = ""
    theme_config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'theme_name': self.theme_name,
            'theme_config': self.theme_config
        })


@dataclass
class PerformanceUpdateEvent(BaseEvent):
    """
    性能更新事件

    当系统性能指标更新时触发。
    """
    metrics: Dict[str, Union[int, float, str]] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'metrics': self.metrics
        })


@dataclass
class IndicatorChangedEvent(BaseEvent):
    """
    指标变化事件

    当用户选择或取消选择指标时触发。
    """
    selected_indicators: list = field(default_factory=list)
    indicator_params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'selected_indicators': self.selected_indicators,
            'indicator_params': self.indicator_params
        })


@dataclass
class MultiScreenToggleEvent(BaseEvent):
    """
    多屏模式切换事件

    当系统在单屏模式和多屏模式之间切换时触发。
    """
    is_multi_screen: bool = False

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'is_multi_screen': self.is_multi_screen
        })


@dataclass
class TradeExecutedEvent(BaseEvent):
    """
    交易执行事件

    当交易（买入/卖出）执行完成时触发。
    """
    trade_record: Any = None  # TradeRecord object

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'trade_record': self.trade_record
        })


@dataclass
class PositionUpdatedEvent(BaseEvent):
    """
    持仓更新事件

    当持仓信息发生变化时触发。
    """
    portfolio: Any = None  # Portfolio object
    updated_positions: list = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'portfolio': self.portfolio,
            'updated_positions': self.updated_positions
        })


@dataclass
class PatternSignalsDisplayEvent(BaseEvent):
    """
    形态信号显示事件

    当用户在形态分析表中点击某一行时触发，通知图表显示和高亮相关信号。
    """
    pattern_name: str = ""
    all_signal_indices: list = field(default_factory=list)
    highlighted_signal_index: int = -1

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'pattern_name': self.pattern_name,
            'all_signal_indices': self.all_signal_indices,
            'highlighted_signal_index': self.highlighted_signal_index
        })

# 告警相关事件


class AlertLevel(Enum):
    """告警级别枚举"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ResourceAlert(BaseEvent):
    """
    资源告警事件

    当系统资源（CPU、内存、磁盘等）超过阈值时触发
    """
    level: AlertLevel = AlertLevel.WARNING
    category: str = "系统资源"
    message: str = ""
    metric_name: str = ""
    current_value: float = 0.0
    threshold: float = 0.0
    unit: str = "%"

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'level': self.level.value,
            'category': self.category,
            'message': self.message,
            'metric_name': self.metric_name,
            'current_value': self.current_value,
            'threshold': self.threshold,
            'unit': self.unit
        })


@dataclass
class ApplicationAlert(BaseEvent):
    """
    应用告警事件

    当应用指标（响应时间、错误率等）超过阈值时触发
    """
    level: AlertLevel = AlertLevel.WARNING
    category: str = "应用性能"
    message: str = ""
    operation_name: str = ""
    metric_name: str = ""
    current_value: float = 0.0
    threshold: float = 0.0
    unit: str = ""

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'level': self.level.value,
            'category': self.category,
            'message': self.message,
            'operation_name': self.operation_name,
            'metric_name': self.metric_name,
            'current_value': self.current_value,
            'threshold': self.threshold,
            'unit': self.unit
        })

# 实时数据相关事件


@dataclass
class RealtimeDataEvent(BaseEvent):
    """
    实时数据事件

    当接收到实时行情数据时触发
    """
    realtime_data: Dict[str, Any] = field(default_factory=dict)
    symbol: str = ""
    data_type: str = "realtime"

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'realtime_data': self.realtime_data,
            'symbol': self.symbol,
            'data_type': self.data_type
        })


@dataclass
class TickDataEvent(BaseEvent):
    """
    Tick数据事件

    当接收到Tick数据时触发
    """
    tick_data: Dict[str, Any] = field(default_factory=dict)
    symbol: str = ""

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'tick_data': self.tick_data,
            'symbol': self.symbol
        })


@dataclass
class OrderBookEvent(BaseEvent):
    """
    订单簿数据事件

    当接收到订单簿数据时触发
    """
    order_book_data: Dict[str, Any] = field(default_factory=dict)
    symbol: str = ""

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'order_book_data': self.order_book_data,
            'symbol': self.symbol
        })


@dataclass
class ComputedIndicatorEvent(BaseEvent):
    """
    计算指标事件

    当实时计算引擎完成指标计算时触发
    """
    computed_indicators: Dict[str, Any] = field(default_factory=dict)
    symbol: str = ""

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'computed_indicators': self.computed_indicators,
            'symbol': self.symbol
        })


# ==================== 增量下载相关事件 ====================

@dataclass
class DataIntegrityEvent(BaseEvent):
    """
    数据完整性事件

    当数据完整性检查完成时触发
    """
    symbol: str = ""
    completeness: float = 0.0
    missing_count: int = 0
    total_count: int = 0

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'symbol': self.symbol,
            'completeness': self.completeness,
            'missing_count': self.missing_count,
            'total_count': self.total_count
        })


@dataclass
class DataAnalysisEvent(BaseEvent):
    """
    数据分析事件

    当数据分析操作完成时触发
    """
    symbol: str = ""
    analysis_type: str = ""
    total_symbols: int = 0
    symbols_to_download: int = 0
    symbols_to_skip: int = 0
    estimated_records: int = 0
    strategy: str = ""

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'symbol': self.symbol,
            'analysis_type': self.analysis_type,
            'total_symbols': self.total_symbols,
            'symbols_to_download': self.symbols_to_download,
            'symbols_to_skip': self.symbols_to_skip,
            'estimated_records': self.estimated_records,
            'strategy': self.strategy
        })


@dataclass
class UpdateHistoryEvent(BaseEvent):
    """
    更新历史事件

    当更新任务状态发生变化时触发
    """
    task_id: str = ""
    task_name: str = ""
    update_type: str = ""
    action: str = ""  # created, started, progress, completed, failed
    progress: float = 0.0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    actual_records: int = 0
    estimated_time: Optional[float] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'task_id': self.task_id,
            'task_name': self.task_name,
            'update_type': self.update_type,
            'action': self.action,
            'progress': self.progress,
            'success_count': self.success_count,
            'failed_count': self.failed_count,
            'skipped_count': self.skipped_count,
            'actual_records': self.actual_records,
            'estimated_time': self.estimated_time,
            'error_message': self.error_message
        })


@dataclass
class TrainingTaskCreatedEvent(BaseEvent):
    """
    训练任务创建事件
    
    当创建新的训练任务时触发
    """
    task_id: str = ""
    task_name: str = ""
    model_type: str = ""
    config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'task_id': self.task_id,
            'task_name': self.task_name,
            'model_type': self.model_type,
            'config': self.config
        })


@dataclass
class TrainingTaskStatusChangedEvent(BaseEvent):
    """
    训练任务状态变更事件
    
    当训练任务状态发生变化时触发
    """
    task_id: str = ""
    old_status: str = ""
    new_status: str = ""
    progress: Optional[float] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'task_id': self.task_id,
            'old_status': self.old_status,
            'new_status': self.new_status,
            'progress': self.progress,
            'error_message': self.error_message
        })


@dataclass
class TrainingProgressUpdatedEvent(BaseEvent):
    """
    训练进度更新事件
    
    当训练进度更新时触发
    """
    task_id: str = ""
    progress: float = 0.0
    epoch: Optional[int] = None
    loss: Optional[float] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'task_id': self.task_id,
            'progress': self.progress,
            'epoch': self.epoch,
            'loss': self.loss,
            'metrics': self.metrics
        })


@dataclass
class ModelVersionCreatedEvent(BaseEvent):
    """
    模型版本创建事件
    
    当创建新的模型版本时触发
    """
    version_id: str = ""
    version_number: str = ""
    model_type: str = ""
    model_file_path: str = ""
    training_task_id: Optional[str] = None

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'version_id': self.version_id,
            'version_number': self.version_number,
            'model_type': self.model_type,
            'model_file_path': self.model_file_path,
            'training_task_id': self.training_task_id
        })


@dataclass
class ModelVersionCurrentChangedEvent(BaseEvent):
    """
    模型当前版本变更事件
    
    当设置新的当前版本时触发
    """
    version_id: str = ""
    version_number: str = ""
    model_type: str = ""

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'version_id': self.version_id,
            'version_number': self.version_number,
            'model_type': self.model_type
        })


@dataclass
class ModelVersionRolledBackEvent(BaseEvent):
    """
    模型版本回滚事件
    
    当回滚到历史版本时触发
    """
    version_id: str = ""
    version_number: str = ""
    previous_version_id: Optional[str] = None

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'version_id': self.version_id,
            'version_number': self.version_number,
            'previous_version_id': self.previous_version_id
        })


@dataclass
class PredictionRecordedEvent(BaseEvent):
    """
    预测记录事件
    
    当记录新的预测结果时触发
    """
    record_id: str = ""
    model_version_id: str = ""
    prediction_type: str = ""
    confidence: float = 0.0

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'record_id': self.record_id,
            'model_version_id': self.model_version_id,
            'prediction_type': self.prediction_type,
            'confidence': self.confidence
        })


@dataclass
class PredictionAccuracyUpdatedEvent(BaseEvent):
    """
    预测准确性更新事件
    
    当更新预测准确性时触发
    """
    record_id: str = ""
    accuracy: float = 0.0
    model_version_id: str = ""
    prediction_type: str = ""

    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'record_id': self.record_id,
            'accuracy': self.accuracy,
            'model_version_id': self.model_version_id,
            'prediction_type': self.prediction_type
        })


# 策略配置相关事件
@dataclass
class StrategyConfigCreatedEvent(BaseEvent):
    """
    策略配置创建事件
    
    当创建新的策略配置时触发
    """
    strategy_id: str = ""
    plugin_type: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'strategy_id': self.strategy_id,
            'plugin_type': self.plugin_type,
            'parameters': self.parameters
        })


@dataclass
class StrategyConfigUpdatedEvent(BaseEvent):
    """
    策略配置更新事件
    
    当更新策略配置时触发
    """
    strategy_id: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'strategy_id': self.strategy_id,
            'parameters': self.parameters,
            'enabled': self.enabled,
            'metadata': self.metadata
        })


@dataclass
class StrategyConfigDeletedEvent(BaseEvent):
    """
    策略配置删除事件
    
    当删除策略配置时触发
    """
    strategy_id: str = ""
    
    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'strategy_id': self.strategy_id
        })


@dataclass
class StrategyConfigsLoadedEvent(BaseEvent):
    """
    策略配置加载完成事件
    
    当从数据库加载完所有策略配置时触发
    """
    config_count: int = 0
    
    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'config_count': self.config_count
        })


# 为兼容性提供Event别名
Event = BaseEvent