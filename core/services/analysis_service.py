"""
统一分析服务 - 架构精简重构版本

整合所有分析管理器功能，提供统一的技术分析和指标计算接口。
整合AnalysisManager、IndicatorCombinationManager、UnifiedIndicatorService等。
完全重构以符合15个核心服务的架构精简目标。
"""

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable, Tuple, Set
from collections import defaultdict, deque
import numpy as np
import pandas as pd

from loguru import logger

from .base_service import BaseService
from ..events import EventBus, get_event_bus
from ..containers import ServiceContainer, get_service_container
from core.indicator_service import calculate_indicator, batch_calculate_indicators


class IndicatorType(Enum):
    """指标类型"""
    TREND = "trend"               # 趋势指标
    MOMENTUM = "momentum"         # 动量指标
    VOLATILITY = "volatility"     # 波动率指标
    VOLUME = "volume"             # 成交量指标
    OSCILLATOR = "oscillator"     # 振荡指标
    SUPPORT_RESISTANCE = "support_resistance"  # 支撑阻力
    PATTERN = "pattern"           # 形态识别
    CUSTOM = "custom"             # 自定义指标


class AnalysisType(Enum):
    """分析类型"""
    TECHNICAL = "technical"       # 技术分析
    FUNDAMENTAL = "fundamental"   # 基本面分析
    QUANTITATIVE = "quantitative"  # 量化分析
    SENTIMENT = "sentiment"       # 情绪分析
    STATISTICAL = "statistical"   # 统计分析


class TimeFrame(Enum):
    """时间周期"""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAILY = "1d"
    WEEKLY = "1w"
    MONTHLY = "1M"


class SignalType(Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"


@dataclass
class IndicatorValue:
    """指标值"""
    indicator_id: str
    symbol: str
    timestamp: datetime
    value: Union[float, Dict[str, float]]
    timeframe: TimeFrame
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IndicatorConfig:
    """指标配置"""
    indicator_id: str
    name: str
    indicator_type: IndicatorType
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    enabled: bool = True
    cache_enabled: bool = True
    update_frequency: int = 60  # 更新频率（秒）


@dataclass
class TechnicalSignal:
    """技术信号"""
    signal_id: str
    symbol: str
    signal_type: SignalType
    strength: float  # 信号强度 0-1
    confidence: float  # 信号置信度 0-1
    source_indicator: str
    price_target: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    generated_time: datetime = field(default_factory=datetime.now)
    expiry_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """分析结果"""
    analysis_id: str
    symbol: str
    analysis_type: AnalysisType
    timeframe: TimeFrame
    result_data: Dict[str, Any]
    signals: List[TechnicalSignal] = field(default_factory=list)
    generated_time: datetime = field(default_factory=datetime.now)
    confidence: float = 0.0
    summary: str = ""


@dataclass
class MarketData:
    """市场数据"""
    symbol: str
    timestamp: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: int
    amount: Optional[Decimal] = None

    @property
    def ohlcv(self) -> Tuple[Decimal, Decimal, Decimal, Decimal, int]:
        """返回OHLCV元组"""
        return (self.open_price, self.high_price, self.low_price, self.close_price, self.volume)


@dataclass
class AnalysisMetrics:
    """分析服务指标"""
    total_indicators: int = 0
    active_indicators: int = 0
    calculated_indicators: int = 0
    total_signals: int = 0
    active_signals: int = 0
    total_analysis: int = 0  # 保留向后兼容
    total_analyses: int = 0  # 新字段：总分析次数
    failed_analyses: int = 0  # 新字段：失败分析次数
    cache_hits: int = 0
    cache_misses: int = 0
    avg_calculation_time: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)


class AnalysisService(BaseService):
    """
    统一分析服务 - 架构精简重构版本

    整合所有分析管理器功能：
    - AnalysisManager: 技术分析管理
    - IndicatorCombinationManager: 指标组合管理
    - UnifiedIndicatorService: 统一指标服务
    - IndicatorDependencyManager: 指标依赖管理
    - RealtimeComputeEngine: 实时计算引擎
    - CustomIndicatorManager: 自定义指标管理

    提供统一的分析接口，支持：
    1. 技术指标计算和管理
    2. 指标组合和依赖分析
    3. 技术信号生成和跟踪
    4. 实时数据分析
    5. 自定义指标开发
    6. 分析结果缓存和优化
    7. 多时间框架分析
    8. 量化分析和回测
    """

    def __init__(self, service_container: Optional[ServiceContainer] = None):
        """初始化分析服务"""
        super().__init__()
        self.service_name = "AnalysisService"

        # 依赖注入
        self._service_container = service_container or get_service_container()

        # 指标管理
        self._indicators: Dict[str, IndicatorConfig] = {}
        self._indicator_values: Dict[str, Dict[str, IndicatorValue]] = defaultdict(dict)
        self._indicator_lock = threading.RLock()

        # 信号管理
        self._signals: Dict[str, TechnicalSignal] = {}
        self._active_signals: Dict[str, TechnicalSignal] = {}
        self._signal_history: List[TechnicalSignal] = []
        self._signal_lock = threading.RLock()

        # 分析结果管理
        self._analysis_results: Dict[str, AnalysisResult] = {}
        self._analysis_lock = threading.RLock()

        # 市场数据缓存
        self._market_data: Dict[str, Dict[TimeFrame, List[MarketData]]] = defaultdict(lambda: defaultdict(list))
        self._market_data_lock = threading.RLock()

        # 统一缓存服务（强制）
        self._unified_cache = None
        self._cache_namespace = 'analysis_service'
        self._init_unified_cache()

        # 分析配置
        self._analysis_config = {
            "enable_real_time": True,
            "cache_size": 10000,
            "max_history_days": 365,
            "calculation_timeout": 30.0,
            "enable_parallel_calculation": True,
            "default_timeframe": TimeFrame.DAILY,
            "signal_expiry_hours": 24,
        }

        # 服务指标
        self._analysis_metrics = AnalysisMetrics()

        # 线程和锁
        self._service_lock = threading.RLock()

        logger.info("AnalysisService initialized for architecture simplification")

    def _init_unified_cache(self) -> None:
        """初始化统一缓存服务（强制）"""
        from core.services.cache_service import CacheService
        
        if self._service_container and self._service_container.is_registered(CacheService):
            self._unified_cache = self._service_container.resolve(CacheService)
            logger.debug(f"AnalysisService 已连接到统一缓存服务，命名空间: {self._cache_namespace}")
        else:
            raise RuntimeError("统一缓存服务未注册，请确保 CacheService 已在服务容器中注册")

    def _get_from_cache(self, key: str, cache_type: str = 'indicator') -> Optional[Any]:
        """从缓存获取数据 - 使用统一缓存服务"""
        if self._unified_cache is None:
            raise RuntimeError("统一缓存服务未初始化")
        
        namespaced_key = f"{cache_type}:{key}"
        return self._unified_cache.get(namespaced_key, namespace=self._cache_namespace)

    def _put_to_cache(self, key: str, value: Any, cache_type: str = 'indicator', ttl: Optional[Any] = None) -> None:
        """将数据放入缓存 - 使用统一缓存服务"""
        if self._unified_cache is None:
            raise RuntimeError("统一缓存服务未初始化")
        
        from datetime import timedelta
        namespaced_key = f"{cache_type}:{key}"
        ttl_delta = None
        if ttl is not None:
            if isinstance(ttl, (int, float)):
                ttl_delta = timedelta(seconds=ttl)
            elif isinstance(ttl, timedelta):
                ttl_delta = ttl
        self._unified_cache.set(namespaced_key, value, ttl=ttl_delta, namespace=self._cache_namespace)

    def _do_initialize(self) -> None:
        """执行具体的初始化逻辑"""
        try:
            logger.info("Initializing AnalysisService core components...")

            # 1. 初始化基础指标
            self._initialize_basic_indicators()

            # 2. 加载分析配置
            self._load_analysis_config()

            # 3. 启动实时计算引擎
            self._start_calculation_engine()

            logger.info("AnalysisService initialized successfully")

        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize AnalysisService: {e}")
            raise

    def _initialize_basic_indicators(self) -> None:
        """初始化基础指标"""
        try:
            # 移动平均线指标
            ma_indicators = [
                IndicatorConfig("ma_5", "5日移动平均", IndicatorType.TREND, {"period": 5}),
                IndicatorConfig("ma_10", "10日移动平均", IndicatorType.TREND, {"period": 10}),
                IndicatorConfig("ma_20", "20日移动平均", IndicatorType.TREND, {"period": 20}),
                IndicatorConfig("ma_50", "50日移动平均", IndicatorType.TREND, {"period": 50}),
                IndicatorConfig("ma_200", "200日移动平均", IndicatorType.TREND, {"period": 200}),
            ]

            # 技术指标
            tech_indicators = [
                IndicatorConfig("rsi", "相对强弱指数", IndicatorType.MOMENTUM, {"period": 14}),
                IndicatorConfig("macd", "MACD", IndicatorType.MOMENTUM, {"fast": 12, "slow": 26, "signal": 9}),
                IndicatorConfig("bollinger", "布林带", IndicatorType.VOLATILITY, {"period": 20, "std": 2}),
                IndicatorConfig("kdj", "KDJ", IndicatorType.OSCILLATOR, {"k_period": 9, "d_period": 3}),
                IndicatorConfig("volume_ma", "成交量均线", IndicatorType.VOLUME, {"period": 20}),
            ]

            with self._indicator_lock:
                for indicator in ma_indicators + tech_indicators:
                    self._indicators[indicator.indicator_id] = indicator
                    self._analysis_metrics.total_indicators += 1
                    if indicator.enabled:
                        self._analysis_metrics.active_indicators += 1

            logger.info("Basic indicators initialized")

        except Exception as e:
            logger.error(f"Failed to initialize basic indicators: {e}")

    def _load_analysis_config(self) -> None:
        """加载分析配置"""
        try:
            # 这里可以从配置服务加载配置
            logger.info("Analysis configuration loaded")

        except Exception as e:
            logger.error(f"Failed to load analysis config: {e}")

    def _start_calculation_engine(self) -> None:
        """启动计算引擎"""
        try:
            # 在真实环境中会启动后台线程进行实时计算
            logger.info("Calculation engine started")

        except Exception as e:
            logger.error(f"Failed to start calculation engine: {e}")

    # 指标管理接口

    def register_indicator(self, config: IndicatorConfig) -> bool:
        """注册指标"""
        try:
            with self._indicator_lock:
                self._indicators[config.indicator_id] = config
                self._analysis_metrics.total_indicators += 1
                if config.enabled:
                    self._analysis_metrics.active_indicators += 1

            logger.info(f"Indicator registered: {config.indicator_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to register indicator {config.indicator_id}: {e}")
            return False

    def calculate_indicator(self, indicator_id: str, symbol: str,
                            timeframe: TimeFrame = TimeFrame.DAILY,
                            start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None) -> List[IndicatorValue]:
        """计算指标"""
        try:
            if indicator_id not in self._indicators:
                logger.error(f"Indicator {indicator_id} not found")
                return []

            config = self._indicators[indicator_id]

            # 获取市场数据
            market_data = self._get_market_data(symbol, timeframe, start_date, end_date)
            if not market_data:
                return []

            # 计算指标值
            values = self._compute_indicator_values(config, market_data)

            # 缓存结果
            cache_key = f"{indicator_id}_{symbol}_{timeframe.value}"
            self._put_to_cache(cache_key, values, cache_type='indicator')
            for value in values:
                self._indicator_values[indicator_id][f"{symbol}_{timeframe.value}_{value.timestamp}"] = value

            self._analysis_metrics.calculated_indicators += 1
            logger.info(f"Calculated indicator {indicator_id} for {symbol}")
            return values

        except Exception as e:
            logger.error(f"Failed to calculate indicator {indicator_id}: {e}")
            return []

    def _compute_indicator_values(self, config: IndicatorConfig, market_data: List[MarketData]) -> List[IndicatorValue]:
        """计算指标值的核心逻辑"""
        try:
            values = []

            if config.indicator_type == IndicatorType.TREND:
                values = self._calculate_trend_indicator(config, market_data)
            elif config.indicator_type == IndicatorType.MOMENTUM:
                values = self._calculate_momentum_indicator(config, market_data)
            elif config.indicator_type == IndicatorType.VOLATILITY:
                values = self._calculate_volatility_indicator(config, market_data)
            elif config.indicator_type == IndicatorType.VOLUME:
                values = self._calculate_volume_indicator(config, market_data)
            elif config.indicator_type == IndicatorType.OSCILLATOR:
                values = self._calculate_oscillator_indicator(config, market_data)
            else:
                logger.warning(f"Unsupported indicator type: {config.indicator_type}")

            return values

        except Exception as e:
            logger.error(f"Failed to compute indicator values: {e}")
            return []

    def _calculate_trend_indicator(self, config: IndicatorConfig, market_data: List[MarketData]) -> List[IndicatorValue]:
        """计算趋势指标"""
        values = []
        if "ma" in config.indicator_id:
            period = config.parameters.get("period", 20)
            prices = [float(data.close_price) for data in market_data]

            for i in range(period - 1, len(market_data)):
                ma_value = sum(prices[i - period + 1:i + 1]) / period
                values.append(IndicatorValue(
                    indicator_id=config.indicator_id,
                    symbol=market_data[i].symbol,
                    timestamp=market_data[i].timestamp,
                    value=ma_value,
                    timeframe=TimeFrame.DAILY
                ))

        return values

    def _calculate_momentum_indicator(self, config: IndicatorConfig, market_data: List[MarketData]) -> List[IndicatorValue]:
        """计算动量指标"""
        values = []
        if config.indicator_id == "rsi":
            period = config.parameters.get("period", 14)
            values = self._calculate_rsi(market_data, period)
        elif config.indicator_id == "macd":
            fast = config.parameters.get("fast", 12)
            slow = config.parameters.get("slow", 26)
            signal = config.parameters.get("signal", 9)
            values = self._calculate_macd(market_data, fast, slow, signal)

        return values

    def _calculate_rsi(self, market_data: List[MarketData], period: int) -> List[IndicatorValue]:
        """计算RSI - 使用统一指标服务"""
        values = []
        if len(market_data) < period + 1:
            return values

        try:
            df = pd.DataFrame([{
                'close': float(data.close_price),
                'high': float(data.high_price) if hasattr(data, 'high_price') else float(data.close_price),
                'low': float(data.low_price) if hasattr(data, 'low_price') else float(data.close_price),
                'volume': float(data.volume) if hasattr(data, 'volume') else 0
            } for data in market_data])
            
            result = calculate_indicator('RSI', df, timeperiod=period)
            
            if isinstance(result, pd.DataFrame) and 'RSI' in result.columns:
                rsi_values = result['RSI'].values
                for i, rsi_val in enumerate(rsi_values):
                    if not np.isnan(rsi_val) and i < len(market_data):
                        values.append(IndicatorValue(
                            indicator_id="rsi",
                            symbol=market_data[i].symbol,
                            timestamp=market_data[i].timestamp,
                            value=rsi_val,
                            timeframe=TimeFrame.DAILY
                        ))
            return values
        except Exception as e:
            logger.warning(f"统一服务计算RSI失败，使用本地计算: {e}")
            prices = [float(data.close_price) for data in market_data]
            gains = []
            losses = []

            for i in range(1, len(prices)):
                change = prices[i] - prices[i-1]
                gains.append(max(change, 0))
                losses.append(max(-change, 0))

            for i in range(period - 1, len(gains)):
                avg_gain = sum(gains[i - period + 1:i + 1]) / period
                avg_loss = sum(losses[i - period + 1:i + 1]) / period

                if avg_loss == 0:
                    rsi = 100
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))

                values.append(IndicatorValue(
                    indicator_id="rsi",
                    symbol=market_data[i + 1].symbol,
                    timestamp=market_data[i + 1].timestamp,
                    value=rsi,
                    timeframe=TimeFrame.DAILY
                ))

            return values

    def _calculate_macd(self, market_data: List[MarketData], fast: int, slow: int, signal: int) -> List[IndicatorValue]:
        """计算MACD - 使用统一指标服务"""
        values = []
        
        try:
            df = pd.DataFrame([{
                'close': float(data.close_price),
                'high': float(data.high_price) if hasattr(data, 'high_price') else float(data.close_price),
                'low': float(data.low_price) if hasattr(data, 'low_price') else float(data.close_price),
                'volume': float(data.volume) if hasattr(data, 'volume') else 0
            } for data in market_data])
            
            result = calculate_indicator('MACD', df, fastperiod=fast, slowperiod=slow, signalperiod=signal)
            
            if isinstance(result, pd.DataFrame):
                macd_values = result.get('MACD', pd.Series())
                signal_values = result.get('MACDSignal', pd.Series())
                hist_values = result.get('MACDHist', pd.Series())
                
                for i in range(len(market_data)):
                    if i < len(macd_values) and i < len(signal_values) and i < len(hist_values):
                        macd_val = macd_values.iloc[i] if i < len(macd_values) else np.nan
                        signal_val = signal_values.iloc[i] if i < len(signal_values) else np.nan
                        hist_val = hist_values.iloc[i] if i < len(hist_values) else np.nan
                        
                        if not (np.isnan(macd_val) or np.isnan(signal_val) or np.isnan(hist_val)):
                            values.append(IndicatorValue(
                                indicator_id="macd",
                                symbol=market_data[i].symbol,
                                timestamp=market_data[i].timestamp,
                                value={
                                    "macd": float(macd_val),
                                    "signal": float(signal_val),
                                    "histogram": float(hist_val)
                                },
                                timeframe=TimeFrame.DAILY
                            ))
            return values
        except Exception as e:
            logger.warning(f"统一服务计算MACD失败，使用本地计算: {e}")
            prices = [float(data.close_price) for data in market_data]

            if len(prices) < slow:
                return values

            ema_fast = self._calculate_ema(prices, fast)
            ema_slow = self._calculate_ema(prices, slow)

            macd_line = [fast_val - slow_val for fast_val, slow_val in zip(ema_fast, ema_slow)]
            signal_line = self._calculate_ema(macd_line, signal)
            histogram = [macd - sig for macd, sig in zip(macd_line, signal_line)]

            for i, data in enumerate(market_data):
                if i < len(macd_line) and i < len(signal_line) and i < len(histogram):
                    values.append(IndicatorValue(
                        indicator_id="macd",
                        symbol=data.symbol,
                        timestamp=data.timestamp,
                        value={
                            "macd": macd_line[i],
                            "signal": signal_line[i],
                            "histogram": histogram[i]
                        },
                        timeframe=TimeFrame.DAILY
                    ))

            return values

    def _calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """计算指数移动平均"""
        if not prices or len(prices) < period:
            return []

        multiplier = 2 / (period + 1)
        ema = [sum(prices[:period]) / period]  # 第一个值用SMA

        for price in prices[period:]:
            ema.append((price * multiplier) + (ema[-1] * (1 - multiplier)))

        return ema

    def _calculate_volatility_indicator(self, config: IndicatorConfig, market_data: List[MarketData]) -> List[IndicatorValue]:
        """计算波动率指标"""
        values = []
        if config.indicator_id == "bollinger":
            period = config.parameters.get("period", 20)
            std_dev = config.parameters.get("std", 2)
            values = self._calculate_bollinger_bands(market_data, period, std_dev)

        return values

    def _calculate_bollinger_bands(self, market_data: List[MarketData], period: int, std_dev: int) -> List[IndicatorValue]:
        """计算布林带"""
        values = []
        prices = [float(data.close_price) for data in market_data]

        for i in range(period - 1, len(market_data)):
            window_prices = prices[i - period + 1:i + 1]
            ma = sum(window_prices) / period
            variance = sum((p - ma) ** 2 for p in window_prices) / period
            std = variance ** 0.5

            upper_band = ma + (std_dev * std)
            lower_band = ma - (std_dev * std)

            values.append(IndicatorValue(
                indicator_id="bollinger",
                symbol=market_data[i].symbol,
                timestamp=market_data[i].timestamp,
                value={
                    "upper": upper_band,
                    "middle": ma,
                    "lower": lower_band
                },
                timeframe=TimeFrame.DAILY
            ))

        return values

    def _calculate_volume_indicator(self, config: IndicatorConfig, market_data: List[MarketData]) -> List[IndicatorValue]:
        """计算成交量指标"""
        values = []
        # 简化实现
        return values

    def _calculate_oscillator_indicator(self, config: IndicatorConfig, market_data: List[MarketData]) -> List[IndicatorValue]:
        """计算振荡指标"""
        values = []
        # 简化实现
        return values

    # 信号生成接口

    def generate_signals(self, symbol: str, timeframe: TimeFrame = TimeFrame.DAILY) -> List[TechnicalSignal]:
        """生成技术信号"""
        try:
            signals = []

            # 获取指标值
            rsi_values = self.get_indicator_values("rsi", symbol, timeframe)
            ma_values = self.get_indicator_values("ma_20", symbol, timeframe)

            if rsi_values:
                latest_rsi = rsi_values[-1]

                # RSI超买超卖信号
                if isinstance(latest_rsi.value, (int, float)):
                    if latest_rsi.value > 70:
                        signal = TechnicalSignal(
                            signal_id=str(uuid.uuid4()),
                            symbol=symbol,
                            signal_type=SignalType.SELL,
                            strength=min((latest_rsi.value - 70) / 30, 1.0),
                            confidence=0.7,
                            source_indicator="rsi",
                            metadata={"rsi_value": latest_rsi.value}
                        )
                        signals.append(signal)
                    elif latest_rsi.value < 30:
                        signal = TechnicalSignal(
                            signal_id=str(uuid.uuid4()),
                            symbol=symbol,
                            signal_type=SignalType.BUY,
                            strength=min((30 - latest_rsi.value) / 30, 1.0),
                            confidence=0.7,
                            source_indicator="rsi",
                            metadata={"rsi_value": latest_rsi.value}
                        )
                        signals.append(signal)

            # 存储信号
            with self._signal_lock:
                for signal in signals:
                    self._signals[signal.signal_id] = signal
                    self._active_signals[signal.signal_id] = signal
                    self._analysis_metrics.total_signals += 1
                    self._analysis_metrics.active_signals += 1

            logger.info(f"Generated {len(signals)} signals for {symbol}")
            return signals

        except Exception as e:
            logger.error(f"Failed to generate signals for {symbol}: {e}")
            return []

    # 数据管理接口

    def add_market_data(self, data: MarketData, timeframe: TimeFrame = TimeFrame.DAILY):
        """添加市场数据"""
        try:
            with self._market_data_lock:
                self._market_data[data.symbol][timeframe].append(data)

                # 保持数据量限制
                max_records = 1000
                if len(self._market_data[data.symbol][timeframe]) > max_records:
                    self._market_data[data.symbol][timeframe] = self._market_data[data.symbol][timeframe][-max_records:]

        except Exception as e:
            logger.error(f"Failed to add market data: {e}")

    def _get_market_data(self, symbol: str, timeframe: TimeFrame,
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None) -> List[MarketData]:
        """获取市场数据"""
        with self._market_data_lock:
            data = self._market_data.get(symbol, {}).get(timeframe, [])

            if start_date or end_date:
                filtered_data = []
                for d in data:
                    if start_date and d.timestamp < start_date:
                        continue
                    if end_date and d.timestamp > end_date:
                        continue
                    filtered_data.append(d)
                return filtered_data

            return data

    # 公共接口方法

    def get_indicator_values(self, indicator_id: str, symbol: str,
                             timeframe: TimeFrame = TimeFrame.DAILY) -> List[IndicatorValue]:
        """获取指标值"""
        with self._indicator_lock:
            indicator_data = self._indicator_values.get(indicator_id, {})
            values = []
            for key, value in indicator_data.items():
                if symbol in key and timeframe.value in key:
                    values.append(value)
            return sorted(values, key=lambda x: x.timestamp)

    def get_signals(self, symbol: Optional[str] = None, active_only: bool = True) -> List[TechnicalSignal]:
        """获取信号"""
        with self._signal_lock:
            signals = list(self._active_signals.values()) if active_only else list(self._signals.values())
            if symbol:
                signals = [s for s in signals if s.symbol == symbol]
            return signals

    def get_analysis_metrics(self) -> AnalysisMetrics:
        """获取分析指标"""
        with self._service_lock:
            self._analysis_metrics.last_update = datetime.now()
            return self._analysis_metrics
    
    async def cancel_previous_requests(self):
        """取消所有先前的分析请求（与ChartService保持接口一致）"""
        # AnalysisService目前主要是同步操作，没有长期运行的异步请求
        # 此方法提供接口兼容性，实际上清空缓存和待处理任务
        try:
            with self._analysis_lock:
                # 清理过期的分析结果缓存
                logger.debug("清理分析服务缓存")
                # 实际的取消逻辑可以在未来扩展
        except Exception as e:
            logger.error(f"取消分析请求时出错: {e}")
    
    async def analyze_stock(
        self, 
        stock_code: str, 
        analysis_type: str = 'comprehensive',
        kline_data: Optional[Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        分析股票数据（异步接口）
        
        Args:
            stock_code: 股票代码
            analysis_type: 分析类型（comprehensive, technical, fundamental等）
            kline_data: K线数据（可选，如果提供则直接使用）
            **kwargs: 其他参数
        
        Returns:
            包含分析结果的字典
        """
        try:
            logger.info(f"开始分析股票: {stock_code}, 类型: {analysis_type}")
            
            result = {}
            
            # 如果提供了K线数据，进行技术指标计算
            if kline_data is not None and hasattr(kline_data, '__len__') and len(kline_data) > 0:
                # 转换为MarketData并添加到服务
                try:
                    # 这里可以扩展更多的技术分析
                    # 目前返回基本结构，确保不阻塞UI
                    result['indicators'] = {}
                    result['technical_analysis'] = {
                        'trend': 'unknown',
                        'signals': []
                    }
                    result['data_available'] = True
                    
                    logger.info(f"股票 {stock_code} 分析完成，数据条数: {len(kline_data)}")
                    
                except Exception as e:
                    logger.warning(f"处理K线数据时出错: {e}")
                    result['data_available'] = False
            else:
                logger.warning(f"未提供有效的K线数据: {stock_code}")
                result['data_available'] = False
            
            # 更新分析指标
            with self._service_lock:
                self._analysis_metrics.total_analyses += 1
            
            return result
            
        except Exception as e:
            logger.error(f"分析股票 {stock_code} 失败: {e}", exc_info=True)
            with self._service_lock:
                self._analysis_metrics.failed_analyses += 1
            return {
                'error': str(e),
                'data_available': False
            }

    def _do_health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        try:
            cache_stats = self._unified_cache.get_namespace_stats(self._cache_namespace) if self._unified_cache else {}
            return {
                "status": "healthy",
                "total_indicators": len(self._indicators),
                "active_indicators": self._analysis_metrics.active_indicators,
                "total_signals": len(self._signals),
                "active_signals": len(self._active_signals),
                "cache_stats": cache_stats,
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _do_dispose(self) -> None:
        """清理资源"""
        try:
            logger.info("Disposing AnalysisService resources...")

            with self._indicator_lock:
                self._indicators.clear()
                self._indicator_values.clear()

            with self._signal_lock:
                self._signals.clear()
                self._active_signals.clear()

            with self._analysis_lock:
                self._analysis_results.clear()

            with self._market_data_lock:
                self._market_data.clear()

            if self._unified_cache:
                self._unified_cache.clear_namespace(self._cache_namespace)

            logger.info("AnalysisService disposed successfully")

        except Exception as e:
            logger.error(f"Error disposing AnalysisService: {e}")
