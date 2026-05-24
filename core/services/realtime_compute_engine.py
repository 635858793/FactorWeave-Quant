"""
实时计算引擎

提供流式数据处理、技术指标计算、自定义公式计算等功能。
支持高频数据流处理和实时指标更新。

作者: FactorWeave-Quant增强团队
版本: 1.0
日期: 2025-09-21
"""

import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from collections import deque, defaultdict
from loguru import logger

# 尝试导入talib，如果失败则使用内置计算
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False
    logger.warning("talib未安装，将使用内置技术指标计算")
from core.events.event_bus import EventBus, TickDataEvent, RealtimeDataEvent

logger = logger.bind(module=__name__)


class IndicatorType(Enum):
    """技术指标类型"""
    MA = "ma"                    # 移动平均线
    EMA = "ema"                  # 指数移动平均线
    MACD = "macd"                # MACD
    RSI = "rsi"                  # 相对强弱指数
    BOLL = "boll"                # 布林带
    KDJ = "kdj"                  # KDJ随机指标
    VOLUME_MA = "volume_ma"      # 成交量移动平均
    VWAP = "vwap"                # 成交量加权平均价
    ATR = "atr"                  # 平均真实波幅
    CUSTOM = "custom"            # 自定义指标


@dataclass
class IndicatorConfig:
    """指标配置"""
    indicator_type: IndicatorType
    symbol: str
    params: Dict[str, Any] = field(default_factory=dict)

    # 计算配置
    window_size: int = 100       # 数据窗口大小
    update_frequency: int = 1    # 更新频率（每N个tick更新一次）

    # 输出配置
    output_fields: List[str] = field(default_factory=list)
    precision: int = 4           # 精度

    # 自定义公式（仅用于CUSTOM类型）
    formula: Optional[str] = None
    formula_func: Optional[Callable] = None


@dataclass
class IndicatorValue:
    """指标值"""
    symbol: str
    indicator_type: IndicatorType
    timestamp: datetime
    values: Dict[str, float] = field(default_factory=dict)

    # 元数据
    params: Dict[str, Any] = field(default_factory=dict)
    calculation_time: Optional[datetime] = None


class StreamProcessor:
    """流处理器基类"""

    def __init__(self, symbol: str, window_size: int = 100):
        self.symbol = symbol
        self.window_size = window_size
        self.data_buffer = deque(maxlen=window_size)
        self.last_update = None

    def add_data(self, data: Dict[str, Any]):
        """添加数据到缓冲区"""
        self.data_buffer.append(data)
        self.last_update = datetime.now()

    def get_dataframe(self) -> pd.DataFrame:
        """获取DataFrame格式的数据"""
        if not self.data_buffer:
            return pd.DataFrame()

        return pd.DataFrame(list(self.data_buffer))

    def calculate(self) -> Optional[Dict[str, float]]:
        """计算指标值（子类实现）"""
        raise NotImplementedError


class MAProcessor(StreamProcessor):
    """移动平均线处理器"""

    def __init__(self, symbol: str, period: int = 20, window_size: int = 100):
        super().__init__(symbol, window_size)
        self.period = period

    def calculate(self) -> Optional[Dict[str, float]]:
        try:
            if len(self.data_buffer) < self.period:
                return None

            df = self.get_dataframe()
            if 'price' not in df.columns:
                return None

            prices = df['price'].astype(float)
            ma_value = prices.tail(self.period).mean()

            return {'ma': round(ma_value, 4)}

        except Exception as e:
            logger.error(f"MA计算失败: {self.symbol}, {e}")
            return None


class EMAProcessor(StreamProcessor):
    """指数移动平均线处理器"""

    def __init__(self, symbol: str, period: int = 20, window_size: int = 100):
        super().__init__(symbol, window_size)
        self.period = period
        self.alpha = 2.0 / (period + 1)
        self.ema_value = None

    def calculate(self) -> Optional[Dict[str, float]]:
        try:
            if not self.data_buffer:
                return None

            current_price = float(self.data_buffer[-1].get('price', 0))

            if self.ema_value is None:
                # 初始化EMA
                if len(self.data_buffer) >= self.period:
                    df = self.get_dataframe()
                    prices = df['price'].astype(float)
                    self.ema_value = prices.tail(self.period).mean()
                else:
                    return None
            else:
                # 更新EMA
                self.ema_value = self.alpha * current_price + (1 - self.alpha) * self.ema_value

            return {'ema': round(self.ema_value, 4)}

        except Exception as e:
            logger.error(f"EMA计算失败: {self.symbol}, {e}")
            return None


class MACDProcessor(StreamProcessor):
    """MACD处理器"""

    def __init__(self, symbol: str, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9, window_size: int = 100):
        super().__init__(symbol, window_size)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def calculate(self) -> Optional[Dict[str, float]]:
        try:
            if len(self.data_buffer) < max(self.slow_period, self.signal_period) + 10:
                return None

            df = self.get_dataframe()
            if 'price' not in df.columns:
                return None

            prices = df['price'].astype(float).values

            # 使用talib计算MACD
            macd_line, macd_signal, macd_histogram = talib.MACD(
                prices,
                fastperiod=self.fast_period,
                slowperiod=self.slow_period,
                signalperiod=self.signal_period
            )

            if np.isnan(macd_line[-1]) or np.isnan(macd_signal[-1]) or np.isnan(macd_histogram[-1]):
                return None

            return {
                'macd': round(macd_line[-1], 4),
                'signal': round(macd_signal[-1], 4),
                'histogram': round(macd_histogram[-1], 4)
            }

        except Exception as e:
            logger.error(f"MACD计算失败: {self.symbol}, {e}")
            return None


class RSIProcessor(StreamProcessor):
    """RSI处理器"""

    def __init__(self, symbol: str, period: int = 14, window_size: int = 100):
        super().__init__(symbol, window_size)
        self.period = period

    def calculate(self) -> Optional[Dict[str, float]]:
        try:
            if len(self.data_buffer) < self.period + 10:
                return None

            df = self.get_dataframe()
            if 'price' not in df.columns:
                return None

            prices = df['price'].astype(float).values
            rsi_values = talib.RSI(prices, timeperiod=self.period)

            if np.isnan(rsi_values[-1]):
                return None

            return {'rsi': round(rsi_values[-1], 2)}

        except Exception as e:
            logger.error(f"RSI计算失败: {self.symbol}, {e}")
            return None


class BOLLProcessor(StreamProcessor):
    """布林带处理器"""

    def __init__(self, symbol: str, period: int = 20, std_dev: float = 2.0, window_size: int = 100):
        super().__init__(symbol, window_size)
        self.period = period
        self.std_dev = std_dev

    def calculate(self) -> Optional[Dict[str, float]]:
        try:
            if len(self.data_buffer) < self.period:
                return None

            df = self.get_dataframe()
            if 'price' not in df.columns:
                return None

            prices = df['price'].astype(float).values

            # 使用talib计算布林带
            upper_band, middle_band, lower_band = talib.BBANDS(
                prices,
                timeperiod=self.period,
                nbdevup=self.std_dev,
                nbdevdn=self.std_dev
            )

            if np.isnan(upper_band[-1]) or np.isnan(middle_band[-1]) or np.isnan(lower_band[-1]):
                return None

            return {
                'upper': round(upper_band[-1], 4),
                'middle': round(middle_band[-1], 4),
                'lower': round(lower_band[-1], 4)
            }

        except Exception as e:
            logger.error(f"BOLL计算失败: {self.symbol}, {e}")
            return None


class VWAPProcessor(StreamProcessor):
    """成交量加权平均价处理器"""

    def __init__(self, symbol: str, window_size: int = 100):
        super().__init__(symbol, window_size)

    def calculate(self) -> Optional[Dict[str, float]]:
        try:
            if len(self.data_buffer) < 10:
                return None

            df = self.get_dataframe()
            if not all(col in df.columns for col in ['price', 'volume']):
                return None

            prices = df['price'].astype(float)
            volumes = df['volume'].astype(float)

            # 计算VWAP
            total_pv = (prices * volumes).sum()
            total_volume = volumes.sum()

            if total_volume == 0:
                return None

            vwap = total_pv / total_volume

            return {'vwap': round(vwap, 4)}

        except Exception as e:
            logger.error(f"VWAP计算失败: {self.symbol}, {e}")
            return None


class CustomFormulaProcessor(StreamProcessor):
    """自定义公式处理器"""

    def __init__(self, symbol: str, formula_func: Callable, window_size: int = 100):
        super().__init__(symbol, window_size)
        self.formula_func = formula_func

    def calculate(self) -> Optional[Dict[str, float]]:
        try:
            if not self.data_buffer:
                return None

            df = self.get_dataframe()
            result = self.formula_func(df)

            if isinstance(result, dict):
                return result
            elif isinstance(result, (int, float)):
                return {'value': round(float(result), 4)}
            else:
                return None

        except Exception as e:
            logger.error(f"自定义公式计算失败: {self.symbol}, {e}")
            return None


class RealtimeComputeEngine:
    """
    实时计算引擎

    提供实时数据流处理功能：
    - 技术指标实时计算
    - 自定义公式支持
    - 流式数据处理
    - 事件驱动更新
    - 多股票并行计算
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        # 处理器管理
        self.processors: Dict[str, Dict[str, StreamProcessor]] = defaultdict(dict)  # symbol -> indicator_id -> processor
        self.indicator_configs: Dict[str, IndicatorConfig] = {}  # indicator_id -> config

        # 计算状态
        self._computing_active = False
        self._compute_thread = None
        self._lock = threading.RLock()

        # 性能统计
        self.compute_stats = {
            'total_calculations': 0,
            'successful_calculations': 0,
            'failed_calculations': 0,
            'avg_compute_time': 0.0
        }

        # 订阅事件
        self._subscribe_to_events()

        logger.info("实时计算引擎初始化完成")

    def _subscribe_to_events(self):
        """订阅相关事件"""
        try:
            # 订阅tick数据事件
            self.event_bus.subscribe(TickDataEvent, self._handle_tick_data)

            # 订阅实时行情事件
            self.event_bus.subscribe(RealtimeDataEvent, self._handle_realtime_data)

            logger.info("实时计算引擎事件订阅完成")

        except Exception as e:
            logger.error(f"订阅事件失败: {e}")

    def add_indicator(self, indicator_id: str, config: IndicatorConfig) -> bool:
        """添加技术指标"""
        try:
            with self._lock:
                self.indicator_configs[indicator_id] = config

                # 创建对应的处理器
                processor = self._create_processor(config)
                if processor:
                    if config.symbol not in self.processors:
                        self.processors[config.symbol] = {}
                    self.processors[config.symbol][indicator_id] = processor

                    logger.info(f"技术指标已添加: {indicator_id} - {config.indicator_type.value} - {config.symbol}")
                    return True
                else:
                    logger.error(f"创建指标处理器失败: {indicator_id}")
                    return False

        except Exception as e:
            logger.error(f"添加技术指标失败: {indicator_id}, {e}")
            return False

    def remove_indicator(self, indicator_id: str) -> bool:
        """移除技术指标"""
        try:
            with self._lock:
                if indicator_id not in self.indicator_configs:
                    logger.warning(f"指标不存在: {indicator_id}")
                    return False

                config = self.indicator_configs[indicator_id]
                symbol = config.symbol

                # 移除处理器
                if symbol in self.processors and indicator_id in self.processors[symbol]:
                    del self.processors[symbol][indicator_id]

                    # 如果该股票没有其他指标，移除整个条目
                    if not self.processors[symbol]:
                        del self.processors[symbol]

                # 移除配置
                del self.indicator_configs[indicator_id]

                logger.info(f"技术指标已移除: {indicator_id}")
                return True

        except Exception as e:
            logger.error(f"移除技术指标失败: {indicator_id}, {e}")
            return False

    def _create_processor(self, config: IndicatorConfig) -> Optional[StreamProcessor]:
        """创建指标处理器"""
        try:
            indicator_type = config.indicator_type
            symbol = config.symbol
            params = config.params
            window_size = config.window_size

            if indicator_type == IndicatorType.MA:
                period = params.get('period', 20)
                return MAProcessor(symbol, period, window_size)

            elif indicator_type == IndicatorType.EMA:
                period = params.get('period', 20)
                return EMAProcessor(symbol, period, window_size)

            elif indicator_type == IndicatorType.MACD:
                fast_period = params.get('fast_period', 12)
                slow_period = params.get('slow_period', 26)
                signal_period = params.get('signal_period', 9)
                return MACDProcessor(symbol, fast_period, slow_period, signal_period, window_size)

            elif indicator_type == IndicatorType.RSI:
                period = params.get('period', 14)
                return RSIProcessor(symbol, period, window_size)

            elif indicator_type == IndicatorType.BOLL:
                period = params.get('period', 20)
                std_dev = params.get('std_dev', 2.0)
                return BOLLProcessor(symbol, period, std_dev, window_size)

            elif indicator_type == IndicatorType.VWAP:
                return VWAPProcessor(symbol, window_size)

            elif indicator_type == IndicatorType.CUSTOM:
                formula_func = config.formula_func
                if formula_func:
                    return CustomFormulaProcessor(symbol, formula_func, window_size)
                else:
                    logger.error(f"自定义指标缺少公式函数: {config}")
                    return None

            else:
                logger.error(f"不支持的指标类型: {indicator_type}")
                return None

        except Exception as e:
            logger.error(f"创建指标处理器失败: {config}, {e}")
            return None

    async def _handle_tick_data(self, event: TickDataEvent):
        """处理tick数据事件"""
        try:
            tick_data = event.tick_data
            symbol = tick_data.get('symbol')

            if not symbol:
                return

            # 准备数据
            data_point = {
                'timestamp': tick_data.get('timestamp', datetime.now()),
                'price': float(tick_data.get('price', 0)),
                'volume': float(tick_data.get('volume', 0)),
                'type': tick_data.get('type', 'unknown')
            }

            # 更新相关指标
            await self._update_indicators_for_symbol(symbol, data_point)

        except Exception as e:
            logger.error(f"处理tick数据事件失败: {e}")

    async def _handle_realtime_data(self, event: RealtimeDataEvent):
        """处理实时行情事件"""
        try:
            realtime_data = event.realtime_data
            symbol = realtime_data.get('symbol')

            if not symbol:
                return

            # 准备数据
            data_point = {
                'timestamp': realtime_data.get('timestamp', datetime.now()),
                'price': float(realtime_data.get('last_price', 0)),
                'volume': float(realtime_data.get('total_volume', 0)),
                'bid_price': float(realtime_data.get('bid_price1', 0)),
                'ask_price': float(realtime_data.get('ask_price1', 0))
            }

            # 更新相关指标
            await self._update_indicators_for_symbol(symbol, data_point)

        except Exception as e:
            logger.error(f"处理实时行情事件失败: {e}")

    async def _update_indicators_for_symbol(self, symbol: str, data_point: Dict[str, Any]):
        """更新指定股票的所有指标"""
        try:
            with self._lock:
                if symbol not in self.processors:
                    return

                symbol_processors = self.processors[symbol]

            # 并行计算所有指标
            tasks = []
            for indicator_id, processor in symbol_processors.items():
                task = self._calculate_indicator(indicator_id, processor, data_point)
                tasks.append(task)

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"更新股票指标失败: {symbol}, {e}")

    async def _calculate_indicator(self, indicator_id: str, processor: StreamProcessor, data_point: Dict[str, Any]):
        """计算单个指标"""
        start_time = datetime.now()

        try:
            # 添加数据到处理器
            processor.add_data(data_point)

            # 计算指标值
            result = processor.calculate()

            if result:
                # 创建指标值对象
                config = self.indicator_configs[indicator_id]
                indicator_value = IndicatorValue(
                    symbol=processor.symbol,
                    indicator_type=config.indicator_type,
                    timestamp=data_point.get('timestamp', datetime.now()),
                    values=result,
                    params=config.params,
                    calculation_time=datetime.now()
                )

                # 发布指标更新事件
                event = IndicatorUpdateEvent(
                    indicator_id=indicator_id,
                    indicator_value=indicator_value
                )
                await self.event_bus.publish(event)

                # 更新统计
                compute_time = (datetime.now() - start_time).total_seconds()
                self._update_compute_stats(True, compute_time)

                logger.debug(f"指标计算完成: {indicator_id} - {processor.symbol} - {result}")

        except Exception as e:
            compute_time = (datetime.now() - start_time).total_seconds()
            self._update_compute_stats(False, compute_time)
            logger.error(f"指标计算失败: {indicator_id}, {e}")

    def _update_compute_stats(self, success: bool, compute_time: float):
        """更新计算统计"""
        try:
            self.compute_stats['total_calculations'] += 1

            if success:
                self.compute_stats['successful_calculations'] += 1
            else:
                self.compute_stats['failed_calculations'] += 1

            # 更新平均计算时间
            total_calcs = self.compute_stats['total_calculations']
            current_avg = self.compute_stats['avg_compute_time']
            self.compute_stats['avg_compute_time'] = (current_avg * (total_calcs - 1) + compute_time) / total_calcs

        except Exception as e:
            logger.error(f"更新计算统计失败: {e}")

    def get_indicator_value(self, indicator_id: str) -> Optional[IndicatorValue]:
        """获取指标当前值"""
        try:
            with self._lock:
                if indicator_id not in self.indicator_configs:
                    return None

                config = self.indicator_configs[indicator_id]
                symbol = config.symbol

                if symbol not in self.processors or indicator_id not in self.processors[symbol]:
                    return None

                processor = self.processors[symbol][indicator_id]
                result = processor.calculate()

                if result:
                    return IndicatorValue(
                        symbol=symbol,
                        indicator_type=config.indicator_type,
                        timestamp=datetime.now(),
                        values=result,
                        params=config.params,
                        calculation_time=datetime.now()
                    )

                return None

        except Exception as e:
            logger.error(f"获取指标值失败: {indicator_id}, {e}")
            return None

    def get_all_indicators(self, symbol: str = None) -> Dict[str, IndicatorValue]:
        """获取所有指标值"""
        try:
            results = {}

            with self._lock:
                for indicator_id, config in self.indicator_configs.items():
                    if symbol and config.symbol != symbol:
                        continue

                    indicator_value = self.get_indicator_value(indicator_id)
                    if indicator_value:
                        results[indicator_id] = indicator_value

            return results

        except Exception as e:
            logger.error(f"获取所有指标值失败: {e}")
            return {}

    def get_compute_stats(self) -> Dict[str, Any]:
        """获取计算统计"""
        try:
            stats = self.compute_stats.copy()

            # 计算成功率
            total_calcs = stats['total_calculations']
            if total_calcs > 0:
                stats['success_rate'] = stats['successful_calculations'] / total_calcs
                stats['failure_rate'] = stats['failed_calculations'] / total_calcs
            else:
                stats['success_rate'] = 0.0
                stats['failure_rate'] = 0.0

            return stats

        except Exception as e:
            logger.error(f"获取计算统计失败: {e}")
            return {}

    def create_custom_formula(self, formula_code: str) -> Optional[Callable]:
        """创建自定义公式函数"""
        try:
            forbidden_words = ['import', 'exec', 'eval', 'open', '__', 'class',
                             'lambda', 'def ', 'global', 'nonlocal', 'del ', 'yield']
            code_lower = formula_code.lower()
            for word in forbidden_words:
                if word in code_lower:
                    logger.warning(f"公式包含禁用关键词: {word}")
                    return None

            if len(formula_code) > 500:
                logger.warning("公式代码过长")
                return None
            # 安全的命名空间，只包含必要的函数和模块
            safe_namespace = {
                'pd': pd,
                'np': np,
                'talib': talib,
                'abs': abs,
                'max': max,
                'min': min,
                'sum': sum,
                'len': len,
                'round': round,
                'float': float,
                'int': int
            }

            # 编译公式代码
            compiled_code = compile(formula_code, '<formula>', 'eval')

            def formula_func(df: pd.DataFrame) -> Union[float, Dict[str, float]]:
                # 将DataFrame添加到命名空间
                namespace = safe_namespace.copy()
                namespace['df'] = df

                # 添加常用的列别名
                if 'price' in df.columns:
                    namespace['price'] = df['price']
                if 'volume' in df.columns:
                    namespace['volume'] = df['volume']
                if 'open' in df.columns:
                    namespace['open'] = df['open']
                if 'high' in df.columns:
                    namespace['high'] = df['high']
                if 'low' in df.columns:
                    namespace['low'] = df['low']
                if 'close' in df.columns:
                    namespace['close'] = df['close']

                # 执行公式
                result = eval(compiled_code, {"__builtins__": {}}, namespace)
                return result

            return formula_func

        except Exception as e:
            logger.error(f"创建自定义公式失败: {e}")
            return None

    def cleanup(self):
        """清理资源"""
        try:
            if self.event_bus:
                try:
                    self.event_bus.unsubscribe(TickDataEvent, self._handle_tick_data)
                    self.event_bus.unsubscribe(RealtimeDataEvent, self._handle_realtime_data)
                except Exception as e:
                    logger.warning(f"取消事件订阅失败: {e}")

            with self._lock:
                self.processors.clear()
                self.indicator_configs.clear()

            logger.info("实时计算引擎资源清理完成")

        except Exception as e:
            logger.error(f"资源清理失败: {e}")
