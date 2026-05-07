"""
形态识别基础框架
定义统一的形态识别接口和抽象基类
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
from datetime import datetime

# 将别名列表定义为模块级别的常量，以避免与Enum的元编程冲突
_CANDLESTICK_ALIASES = [
    'k线形态', 'candle', 'candlesticks',
    'rising_three_methods', 'falling_three_methods'
]

_COMPLEX_ALIASES = ['复杂形态', 'complex', 'chart_pattern', 'chart pattern']
_TREND_ALIASES = ['趋势形态', 'trend']
_VOLUME_ALIASES = ['价量形态', 'volume']
_GAPS_ALIASES = ['缺口形态', 'gap']
_CONTINUATION_ALIASES = ['持续形态', 'continuation', 'continuation_pattern']

class SignalType(Enum):
    """信号类型枚举
    
    统一信号类型定义，包含以下成员：
    - BUY/SELL: 基础买入/卖出信号
    - HOLD: 持有信号
    - NEUTRAL: 中性信号（无方向）
    - STRONG_BUY/STRONG_SELL: 强烈买入/卖出信号
    - CLOSE_LONG/CLOSE_SHORT: 平多/平空信号
    """
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    NEUTRAL = "neutral"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"

    @classmethod
    def from_string(cls, s) -> 'SignalType':
        """从字符串或枚举转换为 SignalType"""
        if s is None:
            return cls.NEUTRAL
        if isinstance(s, cls):
            return s
        if not isinstance(s, str):
            s = str(s)
        s_lower = s.lower()
        for member in cls:
            if member.value == s_lower:
                return member
        return cls.NEUTRAL

    def to_string(self) -> str:
        """转换为字符串"""
        return self.value

    @property
    def is_buy(self) -> bool:
        """是否为买入信号"""
        return self in (self.BUY, self.STRONG_BUY)

    @property
    def is_sell(self) -> bool:
        """是否为卖出信号"""
        return self in (self.SELL, self.STRONG_SELL, self.CLOSE_LONG, self.CLOSE_SHORT)

    @property
    def is_strong(self) -> bool:
        """是否为强烈信号"""
        return self in (self.STRONG_BUY, self.STRONG_SELL)

@dataclass
class PatternResult:
    """形态识别结果"""
    pattern_type: str
    pattern_name: str
    pattern_category: str
    signal_type: SignalType
    confidence: float
    confidence_level: str
    index: int
    datetime_val: Optional[str]
    price: float
    start_index: Optional[int] = None
    end_index: Optional[int] = None
    extra_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            'type': self.pattern_type,
            'pattern_name': self.pattern_name,
            'pattern_category': self.pattern_category,
            'signal': self.signal_type.value,
            'signal_type': self.signal_type.value,
            'confidence': self.confidence,
            'confidence_level': self.confidence_level,
            'index': self.index,
            'datetime': self.datetime_val,
            'price': self.price,
            'start_index': self.start_index,
            'end_index': self.end_index,
        }
        if self.extra_data:
            result.update(self.extra_data)
        return result

@dataclass
class PatternConfig:
    """形态配置"""
    id: int
    name: str
    english_name: str
    category: str
    signal_type: SignalType
    description: str
    min_periods: int
    max_periods: int
    confidence_threshold: float
    algorithm_code: str
    parameters: Dict[str, Any]
    is_active: bool
    success_rate: Optional[float] = None  # 默认None表示无历史数据
    risk_level: str = 'medium'  # 默认风险级别

class BasePatternRecognizer(ABC):
    """形态识别器基类"""

    def __init__(self, config: 'PatternConfig'):
        if not isinstance(config, PatternConfig):
            raise TypeError("config必须是PatternConfig的实例")
        self.config = config
        self.parameters = config.parameters or {}

    @abstractmethod
    def recognize(self, kdata: pd.DataFrame) -> List[PatternResult]:
        """
        识别形态

        Args:
            kdata: K线数据DataFrame

        Returns:
            识别结果列表
        """
        pass

    def validate_data(self, kdata: pd.DataFrame) -> bool:
        """
        验证数据有效性

        Args:
            kdata: K线数据

        Returns:
            是否有效
        """
        if kdata is None or len(kdata) == 0:
            return False

        required_columns = ['open', 'high', 'low', 'close']
        if not all(col in kdata.columns for col in required_columns):
            return False

        if len(kdata) < self.config.min_periods:
            return False

        return True

    def calculate_confidence_level(self, confidence: float) -> str:
        """计算置信度等级"""
        if confidence >= 0.8:
            return '高'
        elif confidence >= 0.5:
            return '中'
        else:
            return '低'

    def analyze_trend(self, kdata: pd.DataFrame, period: int = 20) -> Dict[str, Any]:
        """
        分析趋势 - 识别当前趋势方向和强度
        
        Args:
            kdata: K线数据
            period: 分析周期，默认20根K线
            
        Returns:
            趋势信息字典: {
                'trend': 'uptrend'|'downtrend'|'sideways',  # 趋势方向
                'strength': float,  # 趋势强度 0-1
                'slope': float,  # 斜率
                'sma20': float,  # 20日均线
                'sma60': float,  # 60日均线(如果有)
            }
        """
        if kdata is None or len(kdata) < period:
            return {'trend': 'sideways', 'strength': 0.0, 'slope': 0.0, 'sma20': 0.0, 'sma60': 0.0}
        
        close = kdata['close'].values
        
        sma20 = np.mean(close[-period:]) if len(close) >= period else np.mean(close)
        
        sma60 = np.mean(close[-60:]) if len(close) >= 60 else sma20
        
        slope = 0.0
        if len(close) >= period:
            x = np.arange(period)
            y = close[-period:]
            slope = np.polyfit(x, y, 1)[0]
        
        max_price = np.max(close[-period:])
        min_price = np.min(close[-period:])
        price_range = max_price - min_price
        strength = abs(slope) / price_range if price_range > 0 else 0.0
        
        current_price = close[-1]
        
        atr_multiplier = 0.015
        if len(kdata) >= 20:
            high = kdata['high'].values
            low = kdata['low'].values
            close_vals = kdata['close'].values
            
            tr = np.maximum(
                high[1:] - low[1:],
                np.maximum(
                    np.abs(high[1:] - close_vals[:-1]),
                    np.abs(low[1:] - close_vals[:-1])
                )
            )
            atr = np.mean(tr[-20:]) if len(tr) >= 20 else np.mean(tr)
            atr_multiplier = (atr / sma20) if sma20 > 0 else 0.015
        
        if current_price > sma20 * (1 + atr_multiplier):
            trend = 'uptrend'
        elif current_price < sma20 * (1 - atr_multiplier):
            trend = 'downtrend'
        else:
            trend = 'sideways'
        
        return {
            'trend': trend,
            'strength': min(strength * 10, 1.0),
            'slope': slope,
            'sma20': sma20,
            'sma60': sma60,
            'current_price': current_price
        }

    def is_trend_compatible(self, pattern_signal: str, trend: Dict[str, Any]) -> Tuple[bool, str, float]:
        """
        判断形态信号是否与当前趋势兼容
        
        Args:
            pattern_signal: 形态信号类型 ('buy', 'sell', 'bullish', 'bearish', 'neutral')
            trend: 趋势分析结果
            
        Returns:
            (是否保留, 原因, 置信度调整系数)
            - 置信度调整系数 > 1.0 表示信号增强
            - 置信度调整系数 < 1.0 表示信号减弱
            - 返回 False 表示完全过滤（不建议）
        """
        pattern_signal = pattern_signal.lower().strip()
        trend_type = trend.get('trend', 'sideways')
        trend_strength = trend.get('strength', 0.5)
        
        bullish_patterns = ['buy', 'bullish', '上升', '看涨']
        bearish_patterns = ['sell', 'bearish', '下降', '看跌']
        
        if pattern_signal in bullish_patterns:
            if trend_type == 'uptrend':
                return True, '形态出现在上涨趋势中，符合顺势买入', 1.1
            elif trend_type == 'downtrend':
                return True, '形态出现在下跌趋势中，是潜在的反转买入信号', 1.3
            else:
                return True, '形态出现在横盘震荡中', 1.0
        
        if pattern_signal in bearish_patterns:
            if trend_type == 'downtrend':
                return True, '形态出现在下跌趋势中，符合顺势卖出', 1.1
            elif trend_type == 'uptrend':
                return True, '形态出现在上涨趋势中，是潜在的反转卖出信号', 1.3
            else:
                return True, '形态出现在横盘震荡中', 1.0
        
        return True, '中性形态无需趋势判断', 1.0

    def create_result(self, pattern_type: str, signal_type: SignalType,
                      confidence: float, index: int, price: float,
                      datetime_val: Optional[str] = None,
                      start_index: Optional[int] = None,
                      end_index: Optional[int] = None,
                      extra_data: Optional[Dict[str, Any]] = None) -> PatternResult:
        """创建识别结果"""
        return PatternResult(
            pattern_type=pattern_type,
            pattern_name=self.config.name,
            pattern_category=self.config.category,
            signal_type=signal_type,
            confidence=confidence,
            confidence_level=self.calculate_confidence_level(confidence),
            index=index,
            datetime_val=datetime_val,
            price=price,
            start_index=start_index,
            end_index=end_index,
            extra_data=extra_data
        )

class PatternAlgorithmFactory:
    """形态算法工厂 - 优化版，统一使用DatabaseAlgorithmRecognizer"""

    _recognizers = {}

    @classmethod
    def register(cls, recognizer_type: str, recognizer_class):
        """注册算法"""
        cls._recognizers[recognizer_type] = recognizer_class

    @classmethod
    def create(cls, config: 'PatternConfig') -> 'BasePatternRecognizer':
        from .pattern_recognition import PatternRecognizer
        
        recognizer_type = getattr(config, 'recognizer_type', 'default')
        recognizer_class = cls._recognizers.get(recognizer_type)

        if recognizer_class is None:
            if recognizer_type == 'default' or recognizer_type == 'basic':
                return PatternRecognizer(config)
            raise ValueError(f"找不到识别器类型 '{recognizer_type}'")

        return recognizer_class(config)

    @classmethod
    def get_available_algorithms(cls) -> List[str]:
        """获取可用算法列表"""
        return list(cls._recognizers.keys())

def register_pattern_algorithm(pattern_type: str):
    """装饰器：注册形态算法"""
    def decorator(cls):
        PatternAlgorithmFactory.register(pattern_type, cls)
        return cls
    return decorator

# 工具函数 - 性能优化版
def calculate_body_ratio(open_price: float, close_price: float, high_price: float, low_price: float) -> float:
    """计算实体比例 - 优化版"""
    body_size = abs(close_price - open_price)
    total_range = high_price - low_price
    return body_size / total_range if total_range > 0 else 0.0

def calculate_shadow_ratios(open_price: float, close_price: float, high_price: float, low_price: float) -> Tuple[float, float]:
    """计算上下影线比例 - 优化版"""
    total_range = high_price - low_price
    if total_range <= 0:
        return 0.0, 0.0

    upper_shadow = high_price - max(open_price, close_price)
    lower_shadow = min(open_price, close_price) - low_price

    upper_ratio = upper_shadow / total_range
    lower_ratio = lower_shadow / total_range

    return upper_ratio, lower_ratio

def is_bullish_candle(open_price: float, close_price: float) -> bool:
    """判断是否为阳线"""
    return close_price > open_price

def is_bearish_candle(open_price: float, close_price: float) -> bool:
    """判断是否为阴线"""
    return close_price < open_price

def find_local_extremes(prices: np.ndarray, window: int = 5) -> Tuple[List[int], List[int]]:
    """
    寻找局部极值点 - 性能优化版

    Args:
        prices: 价格数组
        window: 窗口大小

    Returns:
        (peaks, troughs) 峰值和谷值的索引列表
    """
    if len(prices) < 2 * window + 1:
        return [], []

    peaks = []
    troughs = []

    # 使用向量化操作提升性能
    for i in range(window, len(prices) - window):
        # 检查是否为峰值
        left_max = np.max(prices[i-window:i])
        right_max = np.max(prices[i+1:i+window+1])
        if prices[i] >= left_max and prices[i] >= right_max:
            peaks.append(i)

        # 检查是否为谷值
        left_min = np.min(prices[i-window:i])
        right_min = np.min(prices[i+1:i+window+1])
        if prices[i] <= left_min and prices[i] <= right_min:
            troughs.append(i)

    return peaks, troughs

def calculate_trend_strength(prices: np.ndarray, window: int = 20) -> float:
    """
    计算趋势强度 - 性能优化版

    Args:
        prices: 价格数组
        window: 计算窗口

    Returns:
        趋势强度 (-1到1之间，正值表示上升趋势，负值表示下降趋势)
    """
    if len(prices) < window:
        return 0.0

    # 使用最近的数据窗口
    recent_prices = prices[-window:]

    # 使用numpy的线性回归计算趋势
    x = np.arange(len(recent_prices))

    # 计算线性回归系数
    coeffs = np.polyfit(x, recent_prices, 1)
    slope = coeffs[0]

    # 标准化斜率
    price_range = np.ptp(recent_prices)  # 使用ptp获取范围，性能更好
    if price_range > 0:
        normalized_slope = slope / price_range * window
        return np.clip(normalized_slope, -1.0, 1.0)

    return 0.0

def calculate_volatility(prices: np.ndarray, window: int = 20) -> float:
    """
    计算价格波动率 - 新增性能优化函数

    Args:
        prices: 价格数组
        window: 计算窗口

    Returns:
        波动率 (标准差/均值)
    """
    if len(prices) < window:
        return 0.0

    recent_prices = prices[-window:]
    mean_price = np.mean(recent_prices)

    if mean_price > 0:
        std_price = np.std(recent_prices)
        return std_price / mean_price

    return 0.0

def calculate_momentum(prices: np.ndarray, period: int = 10) -> float:
    """
    计算价格动量 - 新增性能优化函数

    Args:
        prices: 价格数组
        period: 计算周期

    Returns:
        动量值 (当前价格相对于period前价格的变化率)
    """
    if len(prices) < period + 1:
        return 0.0

    current_price = prices[-1]
    past_price = prices[-period-1]

    if past_price > 0:
        return (current_price - past_price) / past_price

    return 0.0

def calculate_rsi(prices: np.ndarray, period: int = 14) -> float:
    """
    计算RSI指标 - 新增性能优化函数

    Args:
        prices: 价格数组
        period: 计算周期

    Returns:
        RSI值 (0-100)
    """
    if len(prices) < period + 1:
        return 50.0

    # 计算价格变化
    price_changes = np.diff(prices[-period-1:])

    # 分离上涨和下跌
    gains = np.where(price_changes > 0, price_changes, 0)
    losses = np.where(price_changes < 0, -price_changes, 0)

    # 计算平均收益和损失
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi
