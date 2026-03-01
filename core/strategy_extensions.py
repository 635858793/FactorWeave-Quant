from loguru import logger
"""
策略插件扩展模块

定义统一的策略插件接口和相关数据结构，支持多种策略框架的插件化。

================================================================================
IStrategyPlugin 接口使用指南
================================================================================

一、接口概述
-----------
IStrategyPlugin 是系统统一的策略插件接口，提供完整的策略生命周期管理、
事件驱动支持、性能监控等功能。

二、与 plugins/plugin_interface.py 中 IStrategyPlugin 的区别
------------------------------------------------------------
- 此处 IStrategyPlugin: 完整的策略接口，支持生命周期管理、事件系统
- plugins.plugin_interface.IStrategyPlugin: 数据源级别的轻量级接口

推荐:
- 新策略开发: 使用 core.strategy_extensions.IStrategyPlugin
- 数据源内置简单策略: 使用 plugins.plugin_interface.IStrategyPlugin

三、快速开始
------------
1. 创建策略类继承 IStrategyPlugin
2. 实现所有抽象方法
3. 在 StrategyService 中注册插件工厂
4. 调用 run_backtest() 执行回测

四、事件系统集成
----------------
策略运行过程中会自动发布以下事件:
- StrategyStartedEvent: 策略启动时
- StrategyStoppedEvent: 策略停止时
- SignalGeneratedEvent: 生成交易信号时
- StrategyErrorEvent: 发生错误时

也可以在策略中手动发布事件:
    from core.strategy.events import publish_strategy_event, SignalGeneratedEvent
    event = SignalGeneratedEvent(timestamp=..., strategy_id=..., signals=...)
    publish_strategy_event(event)

五、示例代码
------------
    from core.strategy_extensions import IStrategyPlugin, StrategyInfo, StrategyContext, Signal
    
    class MyStrategyPlugin(IStrategyPlugin):
        def __init__(self):
            self._initialized = False
        
        @property
        def plugin_info(self) -> Dict[str, Any]:
            return {
                "name": "my_strategy",
                "version": "1.0.0",
                "author": "Developer",
                "description": "我的策略"
            }
        
        def get_strategy_info(self) -> StrategyInfo:
            return StrategyInfo(
                name="my_strategy",
                display_name="我的策略",
                description="简单的均线交叉策略",
                version="1.0.0",
                author="Developer",
                strategy_type=StrategyType.TREND_FOLLOWING,
                parameters=[...]
            )
        
        def initialize_strategy(self, context, parameters) -> bool:
            self._initialized = True
            return True
        
        def generate_signals(self, market_data, context) -> List[Signal]:
            signals = []
            # 实现信号生成逻辑
            return signals
        
        def execute_trade(self, signal, context) -> TradeResult:
            pass
        
        def update_position(self, trade_result, context) -> Position:
            pass
        
        def calculate_performance(self, context) -> PerformanceMetrics:
            pass
        
        def cleanup(self) -> None:
            self._initialized = False

六、最佳实践
------------
1. 参数验证: 使用 validate_parameters() 方法验证参数
2. 错误处理: 在各方法中添加 try-except 捕获异常
3. 资源清理: 在 cleanup() 方法中释放资源
4. 事件发布: 生成信号后发布 SignalGeneratedEvent
5. 日志记录: 使用 loguru 记录关键操作日志
"""

import pandas as pd
import numpy as np
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# Import AssetType from plugin_types instead of redefining it
from .plugin_types import AssetType


class StrategyType(Enum):
    """策略类型"""
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    ARBITRAGE = "arbitrage"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    QUANTITATIVE = "quantitative"
    MACHINE_LEARNING = "machine_learning"
    MULTI_FACTOR = "multi_factor"
    HIGH_FREQUENCY = "high_frequency"
    CUSTOM = "custom"

class SignalType(Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"

class TradeAction(Enum):
    """交易动作"""
    OPEN_LONG = "open_long"
    OPEN_SHORT = "open_short"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    ADJUST = "adjust"

class TradeStatus(Enum):
    """交易状态"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    ERROR = "error"

class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"

class TimeFrame(Enum):
    """时间周期"""
    TICK = "tick"
    SECOND_1 = "1s"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"

@dataclass
class ParameterDef:
    """策略参数定义"""
    name: str
    type: type
    default_value: Any
    description: str
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    choices: Optional[List[Any]] = None
    required: bool = True

@dataclass
class StrategyInfo:
    """策略信息"""
    name: str
    display_name: str
    description: str
    version: str
    author: str
    strategy_type: StrategyType
    parameters: List[ParameterDef] = field(default_factory=list)
    supported_assets: List[AssetType] = field(default_factory=list)
    time_frames: List[TimeFrame] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    tags: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class Signal:
    """交易信号"""
    symbol: str
    signal_type: SignalType
    strength: float
    timestamp: datetime
    price: float
    volume: Optional[int] = None
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: Optional[float] = None
    confidence: float = 1.0

@dataclass
class Position:
    """持仓信息"""
    symbol: str
    quantity: float
    avg_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TradeResult:
    """交易结果"""
    trade_id: str
    symbol: str
    action: TradeAction
    quantity: float
    price: float
    timestamp: datetime
    commission: float
    status: TradeStatus
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PerformanceMetrics:
    """性能指标"""
    total_return: float
    annual_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    start_date: datetime
    end_date: datetime
    equity_curve: Optional[pd.Series] = None
    drawdown_curve: Optional[pd.Series] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TradingPerformanceMetrics:
    """交易性能指标（用于算法优化）"""
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    accuracy: float = 0.0
    execution_time: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    signal_quality: float = 0.0
    confidence_avg: float = 0.0
    confidence_std: float = 0.0
    patterns_found: int = 0
    robustness_score: float = 0.0
    parameter_sensitivity: float = 0.0
    overall_score: float = 0.0
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    equity_curve: Optional[pd.Series] = None
    drawdown_curve: Optional[pd.Series] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StandardMarketData:
    """标准化市场数据格式，支持20字段标准"""
    symbol: str
    datetime: pd.Series
    open: pd.Series
    high: pd.Series
    low: pd.Series
    close: pd.Series
    volume: pd.Series
    amount: Optional[pd.Series] = None
    # 20字段标准扩展字段
    adj_close: Optional[pd.Series] = None        # 复权收盘价（回测必需）
    adj_factor: Optional[pd.Series] = None       # 复权因子
    vwap: Optional[pd.Series] = None            # 成交量加权均价
    turnover_rate: Optional[pd.Series] = None    # 换手率
    data_source: Optional[str] = None           # 数据来源
    # 其他20字段标准字段
    open_interest: Optional[pd.Series] = None    # 持仓量（期货）
    pre_close: Optional[pd.Series] = None        # 前收盘价
    change: Optional[pd.Series] = None          # 涨跌额
    pct_change: Optional[pd.Series] = None       # 涨跌幅
    avg_price: Optional[pd.Series] = None        # 平均价格
    total_value: Optional[pd.Series] = None      # 总市值
    circ_value: Optional[pd.Series] = None       # 流通市值
    total_share: Optional[pd.Series] = None      # 总股本
    circ_share: Optional[pd.Series] = None       # 流通股本
    trade_date: Optional[pd.Series] = None       # 交易日期
    list_date: Optional[str] = None             # 上市日期

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame, symbol: str = "unknown") -> 'StandardMarketData':
        """从DataFrame创建StandardMarketData，支持20字段标准"""
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame index must be DatetimeIndex")

        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"Missing required columns: {', '.join(set(required_cols) - set(df.columns))}")

        return cls(
            symbol=symbol,
            datetime=df.index.to_series(),
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            volume=df['volume'],
            amount=df.get('amount'),
            # 20字段标准扩展字段
            adj_close=df.get('adj_close'),
            adj_factor=df.get('adj_factor'),
            vwap=df.get('vwap'),
            turnover_rate=df.get('turnover_rate'),
            data_source=df.get('data_source'),
            open_interest=df.get('open_interest'),
            pre_close=df.get('pre_close'),
            change=df.get('change'),
            pct_change=df.get('pct_change'),
            avg_price=df.get('avg_price'),
            total_value=df.get('total_value'),
            circ_value=df.get('circ_value'),
            total_share=df.get('total_share'),
            circ_share=df.get('circ_share'),
            trade_date=df.get('trade_date'),
            list_date=df.get('list_date')
        )

    def to_dataframe(self) -> pd.DataFrame:
        """转换为DataFrame，包含20字段标准"""
        data = {
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }
        
        # 添加可选字段
        optional_fields = [
            'amount', 'adj_close', 'adj_factor', 'vwap', 'turnover_rate',
            'open_interest', 'pre_close', 'change', 'pct_change', 'avg_price',
            'total_value', 'circ_value', 'total_share', 'circ_share', 'trade_date'
        ]
        
        for field in optional_fields:
            value = getattr(self, field)
            if value is not None:
                data[field] = value
        
        df = pd.DataFrame(data, index=self.datetime)
        
        # 如果有data_source，添加到DataFrame的属性中
        if self.data_source:
            df.attrs['data_source'] = self.data_source
        if self.list_date:
            df.attrs['list_date'] = self.list_date
            df.attrs['symbol'] = self.symbol
        
        return df

@dataclass
class StrategyContext:
    """策略执行上下文"""
    symbol: str
    timeframe: TimeFrame
    start_date: datetime
    end_date: datetime
    initial_capital: float = 100000.0
    commission_rate: float = 0.001
    slippage: float = 0.001
    benchmark: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class IStrategyPlugin(ABC):
    """
    策略插件接口
    
    定义策略插件的标准化接口，支持多种策略框架的插件化管理。
    所有策略插件必须实现此接口以与系统集成。
    
    事件集成:
    - 策略启动时: 触发 StrategyStartedEvent
    - 策略停止时: 触发 StrategyStoppedEvent
    - 信号生成时: 触发 SignalGeneratedEvent
    - 策略错误时: 触发 StrategyErrorEvent
    
    生命周期方法调用顺序:
    1. get_plugin_info() - 获取插件基本信息
    2. get_strategy_info() - 获取策略详细信息
    3. get_parameters() / get_config_schema() - 获取参数定义
    4. validate_parameters() - 验证参数有效性
    5. initialize_strategy() - 初始化策略
    6. generate_signals() - 生成交易信号
    7. execute_trade() - 执行交易
    8. update_position() - 更新持仓
    9. calculate_performance() - 计算性能
    10. cleanup() - 清理资源
    """

    @property
    @abstractmethod
    def plugin_info(self) -> Dict[str, Any]:
        """
        获取插件基本信息
        
        Returns:
            Dict[str, Any]: 包含以下字段的字典:
                - name: 插件名称
                - version: 版本号
                - author: 作者
                - description: 描述
                - strategy_type: 策略类型
        """
        pass

    @abstractmethod
    def get_strategy_info(self) -> StrategyInfo:
        """
        获取策略详细信息
        
        Returns:
            StrategyInfo: 包含策略完整信息的对象，包括参数定义
        """
        pass

    @abstractmethod
    def initialize_strategy(self, context: StrategyContext, parameters: Dict[str, Any]) -> bool:
        """
        初始化策略
        
        Args:
            context: 策略执行上下文，包含交易标的、时间范围、初始资金等信息
            parameters: 策略参数字典，应与 get_strategy_info().parameters 定义一致
        
        Returns:
            bool: 初始化是否成功
        
        Events:
            成功时发布 StrategyStartedEvent
            失败时发布 StrategyErrorEvent
        """
        pass

    @abstractmethod
    def generate_signals(self, market_data: StandardMarketData, context: StrategyContext) -> List[Signal]:
        """
        生成交易信号
        
        Args:
            market_data: 标准市场数据对象，包含20字段标准数据
            context: 策略执行上下文
        
        Returns:
            List[Signal]: 交易信号列表
        
        Events:
            生成信号后发布 SignalGeneratedEvent
        """
        pass

    @abstractmethod
    def execute_trade(self, signal: Signal, context: StrategyContext) -> TradeResult:
        """
        执行交易
        
        Args:
            signal: 待执行的交易信号
            context: 策略执行上下文
        
        Returns:
            TradeResult: 交易执行结果
        """
        pass

    @abstractmethod
    def update_position(self, trade_result: TradeResult, context: StrategyContext) -> Position:
        """
        更新持仓
        
        Args:
            trade_result: 交易结果
            context: 策略执行上下文
        
        Returns:
            Position: 更新后的持仓信息
        """
        pass

    @abstractmethod
    def calculate_performance(self, context: StrategyContext) -> PerformanceMetrics:
        """
        计算策略性能指标
        
        Args:
            context: 策略执行上下文
        
        Returns:
            PerformanceMetrics: 性能指标对象，包含收益率、夏普比率等
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """
        清理资源
        
        在策略生命周期结束时调用，用于释放资源、关闭连接等。
        建议在此方法中发布 StrategyStoppedEvent。
        """
        pass

    def validate_parameters(self, parameters: Dict[str, Any]) -> Tuple[bool, str]:
        """
        验证策略参数
        
        Args:
            parameters: 待验证的参数字典
        
        Returns:
            Tuple[bool, str]: (验证是否通过, 错误信息)
        """
        strategy_info = self.get_strategy_info()

        for param_def in strategy_info.parameters:
            param_name = param_def.name

            if param_def.required and param_name not in parameters:
                return False, f"Missing required parameter: {param_name}"

            if param_name in parameters:
                value = parameters[param_name]

                # 类型检查
                if not isinstance(value, param_def.type):
                    try:
                        value = param_def.type(value)
                    except (ValueError, TypeError):
                        return False, f"Parameter '{param_name}' must be of type {param_def.type.__name__}"

                # 范围检查
                if param_def.min_value is not None and value < param_def.min_value:
                    return False, f"Parameter '{param_name}' must be >= {param_def.min_value}"
                if param_def.max_value is not None and value > param_def.max_value:
                    return False, f"Parameter '{param_name}' must be <= {param_def.max_value}"

                # 选择检查
                if param_def.choices is not None and value not in param_def.choices:
                    return False, f"Parameter '{param_name}' must be one of {param_def.choices}"

        return True, ""

class StrategyPluginAdapter:
    def __init__(self):
        self.logger = logger.bind(module=self.__class__.__name__)

    """策略插件适配器"""

    def __init__(self, plugin: IStrategyPlugin, plugin_id: str):
        self.plugin = plugin
        self.plugin_id = plugin_id

        # 性能统计
        self._signal_count = 0
        self._trade_count = 0
        self._total_signal_time = 0.0
        self._total_trade_time = 0.0
        self._error_count = 0
        self._last_activity = None
    
    @property
    def logger(self):
        """获取日志记录器"""
        return logger

    def get_strategy_info(self) -> StrategyInfo:
        """获取策略信息"""
        try:
            return self.plugin.get_strategy_info()
        except Exception as e:
            self.logger.error(f"获取策略信息失败: {e}")
            raise

    def initialize_strategy(self, context: StrategyContext, parameters: Dict[str, Any]) -> bool:
        """初始化策略"""
        try:
            # 验证参数
            is_valid, error_msg = self.plugin.validate_parameters(parameters)
            if not is_valid:
                self.logger.error(f"参数验证失败: {error_msg}")
                return False

            # 初始化策略
            result = self.plugin.initialize_strategy(context, parameters)
            self._last_activity = datetime.now()
            return result
        except Exception as e:
            self._error_count += 1
            self.logger.error(f"策略初始化失败: {e}")
            return False

    def generate_signals(self, market_data: StandardMarketData, context: StrategyContext) -> List[Signal]:
        """生成交易信号"""
        start_time = time.time()
        try:
            signals = self.plugin.generate_signals(market_data, context)

            # 更新统计
            self._signal_count += len(signals)
            self._total_signal_time += (time.time() - start_time) * 1000
            self._last_activity = datetime.now()

            return signals
        except Exception as e:
            self._error_count += 1
            self.logger.error(f"信号生成失败: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """获取插件统计信息"""
        avg_signal_time = (self._total_signal_time / self._signal_count
                           if self._signal_count > 0 else 0.0)
        avg_trade_time = (self._total_trade_time / self._trade_count
                          if self._trade_count > 0 else 0.0)

        return {
            'plugin_id': self.plugin_id,
            'signal_count': self._signal_count,
            'trade_count': self._trade_count,
            'avg_signal_time_ms': avg_signal_time,
            'avg_trade_time_ms': avg_trade_time,
            'error_count': self._error_count,
            'last_activity': self._last_activity.isoformat() if self._last_activity else None
        }

def validate_strategy_plugin_interface(plugin_instance) -> bool:
    """验证插件是否实现了必要的IStrategyPlugin接口"""
    required_methods = [
        'get_strategy_info', 'initialize_strategy', 'generate_signals',
        'execute_trade', 'update_position', 'calculate_performance', 'cleanup'
    ]

    # 检查plugin_info属性
    if not hasattr(plugin_instance, 'plugin_info'):
        logger.error("策略插件缺少plugin_info属性")
        return False

    plugin_info = getattr(plugin_instance, 'plugin_info')
    if callable(plugin_info):
        try:
            plugin_info()
        except Exception as e:
            logger.error(f"策略插件plugin_info方法调用失败: {e}")
            return False
    elif not isinstance(plugin_info, dict):
        logger.error("策略插件plugin_info必须是字典或返回字典的方法")
        return False

    # 检查必要方法
    for method_name in required_methods:
        if not hasattr(plugin_instance, method_name):
            logger.error(f"策略插件缺少必要方法: {method_name}")
            return False

        method = getattr(plugin_instance, method_name)
        if not callable(method):
            logger.error(f"策略插件方法不可调用: {method_name}")
            return False

    return True
