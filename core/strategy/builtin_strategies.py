from loguru import logger
"""
内置策略实现 - 常用的技术指标策略

提供标准的技术分析策略实现
"""

from analysis.pattern_recognition import PatternRecognizer
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from datetime import datetime

from .base_strategy import BaseStrategy, StrategySignal, StrategyType, SignalType
from .strategy_registry import register_strategy
from core.indicators.indicators_algorithm import calc_kdj

@register_strategy("MA策略", {
    "category": "技术分析",
    "description": "基于移动平均线的趋势跟踪策略"
})
class MAStrategy(BaseStrategy):
    """移动平均线策略"""

    def __init__(self, name: str = "MA策略"):
        super().__init__(name, StrategyType.TECHNICAL)

    def _init_default_parameters(self):
        """初始化默认参数"""
        self.add_parameter("short_period", 5, int, "短期均线周期", 1, 100)
        self.add_parameter("long_period", 20, int, "长期均线周期", 1, 200)
        self.add_parameter("min_confidence", 0.6, float, "最小置信度", 0.0, 1.0)

    def generate_signals(self, data: pd.DataFrame) -> List[StrategySignal]:
        """生成移动平均线信号"""
        signals = []

        short_period = self.get_parameter("short_period")
        long_period = self.get_parameter("long_period")
        min_confidence = self.get_parameter("min_confidence")

        if len(data) < long_period:
            return signals

        # 计算移动平均线
        data = data.copy()
        data['ma_short'] = data['close'].rolling(window=short_period).mean()
        data['ma_long'] = data['close'].rolling(window=long_period).mean()

        # 计算信号
        data['signal'] = 0
        data.loc[data['ma_short'] > data['ma_long'], 'signal'] = 1
        data.loc[data['ma_short'] < data['ma_long'], 'signal'] = -1

        # 信号变化点
        data['signal_change'] = data['signal'].diff()

        buy_mask = data['signal_change'] == 2
        sell_mask = data['signal_change'] == -2
        signal_indices = data.index[buy_mask | sell_mask]
        if len(signal_indices) == 0:
            return signals

        for idx in signal_indices:
            i = data.index.get_loc(idx)
            if i < long_period:
                continue
            row = data.iloc[i]
            sc = row['signal_change']
            confidence = self.calculate_confidence(data, i)
            if confidence < min_confidence:
                continue
            if sc == 2:
                signals.append(StrategySignal(
                    timestamp=idx, signal_type=SignalType.BUY, price=row['close'],
                    confidence=confidence, strategy_name=self.name,
                    reason=f"短期MA({short_period})上穿长期MA({long_period})",
                    stop_loss=row['close'] * 0.95, take_profit=row['close'] * 1.1))
            elif sc == -2:
                signals.append(StrategySignal(
                    timestamp=idx, signal_type=SignalType.SELL, price=row['close'],
                    confidence=confidence, strategy_name=self.name,
                    reason=f"短期MA({short_period})下穿长期MA({long_period})",
                    stop_loss=row['close'] * 1.05, take_profit=row['close'] * 0.9))

        return signals

    def calculate_confidence(self, data: pd.DataFrame, signal_index: int) -> float:
        """计算信号置信度"""
        if signal_index < 10:
            return 0.5

        # 基于价格趋势强度和成交量计算置信度
        recent_data = data.iloc[signal_index-10:signal_index+1]

        # 价格变化幅度
        price_change = abs(recent_data['close'].iloc[-1] -
                           recent_data['close'].iloc[0]) / recent_data['close'].iloc[0]

        # 成交量变化
        volume_ratio = recent_data['volume'].iloc[-1] / \
            recent_data['volume'].mean(
        ) if recent_data['volume'].mean() > 0 else 1

        # 均线分离度
        ma_separation = abs(recent_data['ma_short'].iloc[-1] -
                            recent_data['ma_long'].iloc[-1]) / recent_data['ma_long'].iloc[-1]

        # 综合置信度
        confidence = min(
            0.9, max(0.1, (price_change * 2 + volume_ratio * 0.3 + ma_separation * 5) / 3))

        return confidence

@register_strategy("MACD策略", {
    "category": "技术分析",
    "description": "基于MACD指标的金叉死叉策略"
})
class MACDStrategy(BaseStrategy):
    """MACD策略"""

    def __init__(self, name: str = "MACD策略"):
        super().__init__(name, StrategyType.TECHNICAL)

    def _init_default_parameters(self):
        """初始化默认参数"""
        self.add_parameter("fast_period", 12, int, "快线周期", 1, 50)
        self.add_parameter("slow_period", 26, int, "慢线周期", 1, 100)
        self.add_parameter("signal_period", 9, int, "信号线周期", 1, 30)
        self.add_parameter("min_confidence", 0.6, float, "最小置信度", 0.0, 1.0)

    def generate_signals(self, data: pd.DataFrame) -> List[StrategySignal]:
        """生成MACD信号"""
        signals = []

        fast_period = self.get_parameter("fast_period")
        slow_period = self.get_parameter("slow_period")
        signal_period = self.get_parameter("signal_period")
        min_confidence = self.get_parameter("min_confidence")

        if len(data) < slow_period + signal_period:
            return signals

        # 计算MACD
        data = data.copy()
        exp1 = data['close'].ewm(span=fast_period).mean()
        exp2 = data['close'].ewm(span=slow_period).mean()
        data['macd'] = exp1 - exp2
        data['signal_line'] = data['macd'].ewm(span=signal_period).mean()
        data['histogram'] = data['macd'] - data['signal_line']

        # 计算信号
        data['macd_signal'] = 0
        data.loc[data['macd'] > data['signal_line'], 'macd_signal'] = 1
        data.loc[data['macd'] < data['signal_line'], 'macd_signal'] = -1

        # 信号变化点
        data['signal_change'] = data['macd_signal'].diff()

        buy_mask = data['signal_change'] == 2
        sell_mask = data['signal_change'] == -2
        signal_indices = data.index[buy_mask | sell_mask]
        if len(signal_indices) == 0:
            return signals

        start_pos = slow_period + signal_period
        for idx in signal_indices:
            i = data.index.get_loc(idx)
            if i < start_pos:
                continue
            row = data.iloc[i]
            sc = row['signal_change']
            confidence = self.calculate_confidence(data, i)
            if confidence < min_confidence:
                continue
            if sc == 2:
                signals.append(StrategySignal(
                    timestamp=idx, signal_type=SignalType.BUY, price=row['close'],
                    confidence=confidence, strategy_name=self.name,
                    reason="MACD金叉", stop_loss=row['close'] * 0.95,
                    take_profit=row['close'] * 1.1))
            elif sc == -2:
                signals.append(StrategySignal(
                    timestamp=idx, signal_type=SignalType.SELL, price=row['close'],
                    confidence=confidence, strategy_name=self.name,
                    reason="MACD死叉", stop_loss=row['close'] * 1.05,
                    take_profit=row['close'] * 0.9))

        return signals

    def calculate_confidence(self, data: pd.DataFrame, signal_index: int) -> float:
        """计算信号置信度"""
        if signal_index < 10:
            return 0.5

        recent_data = data.iloc[signal_index-10:signal_index+1]

        # MACD强度
        macd_strength = abs(
            recent_data['macd'].iloc[-1]) / recent_data['close'].iloc[-1]

        # 柱状图趋势
        histogram_trend = recent_data['histogram'].iloc[-1] - \
            recent_data['histogram'].iloc[-5]

        # 价格确认
        price_trend = (recent_data['close'].iloc[-1] -
                       recent_data['close'].iloc[-5]) / recent_data['close'].iloc[-5]

        # 综合置信度
        confidence = min(0.9, max(0.1, (macd_strength * 100 +
                         abs(histogram_trend) * 10 + abs(price_trend) * 2) / 3))

        return confidence

@register_strategy("RSI策略", {
    "category": "技术分析",
    "description": "基于RSI指标的超买超卖策略"
})
class RSIStrategy(BaseStrategy):
    """RSI策略"""

    def __init__(self, name: str = "RSI策略"):
        super().__init__(name, StrategyType.TECHNICAL)

    def _init_default_parameters(self):
        """初始化默认参数"""
        self.add_parameter("period", 14, int, "RSI周期", 1, 50)
        self.add_parameter("oversold", 30, float, "超卖阈值", 10, 40)
        self.add_parameter("overbought", 70, float, "超买阈值", 60, 90)
        self.add_parameter("min_confidence", 0.6, float, "最小置信度", 0.0, 1.0)

    def generate_signals(self, data: pd.DataFrame) -> List[StrategySignal]:
        """生成RSI信号"""
        signals = []

        period = self.get_parameter("period")
        oversold = self.get_parameter("oversold")
        overbought = self.get_parameter("overbought")
        min_confidence = self.get_parameter("min_confidence")

        if len(data) < period + 1:
            return signals

        # 计算RSI
        data = data.copy()
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        data['rsi'] = 100 - (100 / (1 + rs))

        data['prev_rsi'] = data['rsi'].shift(1)
        buy_mask = (data['prev_rsi'] <= oversold) & (data['rsi'] > oversold)
        sell_mask = (data['prev_rsi'] >= overbought) & (data['rsi'] < overbought)
        signal_indices = data.index[buy_mask | sell_mask]
        if len(signal_indices) == 0:
            return signals

        start_pos = period + 2
        for idx in signal_indices:
            i = data.index.get_loc(idx)
            if i < start_pos:
                continue
            row = data.iloc[i]
            confidence = self.calculate_confidence(data, i)
            if confidence < min_confidence:
                continue
            prev_rsi = data.iloc[i-1]['rsi']
            if prev_rsi <= oversold:
                signals.append(StrategySignal(
                    timestamp=idx, signal_type=SignalType.BUY, price=row['close'],
                    confidence=confidence, strategy_name=self.name,
                    reason=f"RSI从超卖区({oversold})反弹",
                    stop_loss=row['close'] * 0.95, take_profit=row['close'] * 1.1))
            else:
                signals.append(StrategySignal(
                    timestamp=idx, signal_type=SignalType.SELL, price=row['close'],
                    confidence=confidence, strategy_name=self.name,
                    reason=f"RSI从超买区({overbought})回落",
                    stop_loss=row['close'] * 1.05, take_profit=row['close'] * 0.9))

        return signals

    def calculate_confidence(self, data: pd.DataFrame, signal_index: int) -> float:
        """计算信号置信度"""
        if signal_index < 10:
            return 0.5

        recent_data = data.iloc[signal_index-10:signal_index+1]

        # RSI极值程度
        current_rsi = recent_data['rsi'].iloc[-1]
        rsi_extreme = min(current_rsi, 100 - current_rsi) / 50  # 越接近极值置信度越高

        # 价格确认
        price_change = (recent_data['close'].iloc[-1] -
                        recent_data['close'].iloc[-3]) / recent_data['close'].iloc[-3]

        # 成交量确认
        volume_ratio = recent_data['volume'].iloc[-1] / \
            recent_data['volume'].mean(
        ) if recent_data['volume'].mean() > 0 else 1

        # 综合置信度
        confidence = min(
            0.9, max(0.1, (rsi_extreme + abs(price_change) * 2 + volume_ratio * 0.2) / 3))

        return confidence

@register_strategy("KDJ策略", {
    "category": "技术分析",
    "description": "基于KDJ指标的金叉死叉策略"
})
class KDJStrategy(BaseStrategy):
    """KDJ策略"""

    def __init__(self, name: str = "KDJ策略"):
        super().__init__(name, StrategyType.TECHNICAL)

    def _init_default_parameters(self):
        """初始化默认参数"""
        self.add_parameter("period", 9, int, "KDJ周期", 1, 30)
        self.add_parameter("k_period", 3, int, "K值平滑周期", 1, 10)
        self.add_parameter("d_period", 3, int, "D值平滑周期", 1, 10)
        self.add_parameter("oversold", 20, float, "超卖阈值", 10, 30)
        self.add_parameter("overbought", 80, float, "超买阈值", 70, 90)
        self.add_parameter("min_confidence", 0.6, float, "最小置信度", 0.0, 1.0)

    def generate_signals(self, data: pd.DataFrame) -> List[StrategySignal]:
        """生成KDJ信号"""
        signals = []

        period = self.get_parameter("period")
        k_period = self.get_parameter("k_period")
        d_period = self.get_parameter("d_period")
        oversold = self.get_parameter("oversold")
        overbought = self.get_parameter("overbought")
        min_confidence = self.get_parameter("min_confidence")

        if len(data) < period + k_period + d_period:
            return signals

        # 计算KDJ
        data = data.copy()
        data['k'], data['d'], data['j'] = calc_kdj(data['high'], data['low'], data['close'], n=period, m1=k_period, m2=d_period)

        data['prev_k'] = data['k'].shift(1)
        data['prev_d'] = data['d'].shift(1)
        buy_mask = (data['prev_k'] <= data['prev_d']) & (data['k'] > data['d']) & (data['k'] < oversold + 10)
        sell_mask = (data['prev_k'] >= data['prev_d']) & (data['k'] < data['d']) & (data['k'] > overbought - 10)
        signal_indices = data.index[buy_mask | sell_mask]
        if len(signal_indices) == 0:
            return signals

        start_pos = period + k_period + d_period + 2
        for idx in signal_indices:
            i = data.index.get_loc(idx)
            if i < start_pos:
                continue
            row = data.iloc[i]
            confidence = self.calculate_confidence(data, i)
            if confidence < min_confidence:
                continue
            prev_k = data.iloc[i-1]['k']
            prev_d = data.iloc[i-1]['d']
            if prev_k <= prev_d:
                signals.append(StrategySignal(
                    timestamp=idx, signal_type=SignalType.BUY, price=row['close'],
                    confidence=confidence, strategy_name=self.name,
                    reason="KDJ金叉且处于超卖区",
                    stop_loss=row['close'] * 0.95, take_profit=row['close'] * 1.1))
            else:
                signals.append(StrategySignal(
                    timestamp=idx, signal_type=SignalType.SELL, price=row['close'],
                    confidence=confidence, strategy_name=self.name,
                    reason="KDJ死叉且处于超买区",
                    stop_loss=row['close'] * 1.05, take_profit=row['close'] * 0.9))

        return signals

    def calculate_confidence(self, data: pd.DataFrame, signal_index: int) -> float:
        """计算信号置信度"""
        if signal_index < 10:
            return 0.5

        recent_data = data.iloc[signal_index-10:signal_index+1]

        # KD值分离度
        kd_separation = abs(
            recent_data['k'].iloc[-1] - recent_data['d'].iloc[-1]) / 100

        # J值极值程度
        j_extreme = min(
            abs(recent_data['j'].iloc[-1]), abs(100 - recent_data['j'].iloc[-1])) / 50

        # 价格确认
        price_trend = (recent_data['close'].iloc[-1] -
                       recent_data['close'].iloc[-5]) / recent_data['close'].iloc[-5]

        # 综合置信度
        confidence = min(
            0.9, max(0.1, (kd_separation * 2 + j_extreme + abs(price_trend) * 2) / 3))

        return confidence

@register_strategy("布林带策略", {
    "category": "技术分析",
    "description": "基于布林带的突破策略"
})
class BollingerBandsStrategy(BaseStrategy):
    """布林带策略"""

    def __init__(self, name: str = "布林带策略"):
        super().__init__(name, StrategyType.TECHNICAL)

    def _init_default_parameters(self):
        """初始化默认参数"""
        self.add_parameter("period", 20, int, "布林带周期", 5, 50)
        self.add_parameter("std_dev", 2.0, float, "标准差倍数", 1.0, 3.0)
        self.add_parameter("min_confidence", 0.6, float, "最小置信度", 0.0, 1.0)

    def generate_signals(self, data: pd.DataFrame) -> List[StrategySignal]:
        """生成布林带信号"""
        signals = []

        period = self.get_parameter("period")
        std_dev = self.get_parameter("std_dev")
        min_confidence = self.get_parameter("min_confidence")

        if len(data) < period:
            return signals

        # 计算布林带
        data = data.copy()
        data['bb_middle'] = data['close'].rolling(window=period).mean()
        data['bb_std'] = data['close'].rolling(window=period).std()
        data['bb_upper'] = data['bb_middle'] + (data['bb_std'] * std_dev)
        data['bb_lower'] = data['bb_middle'] - (data['bb_std'] * std_dev)

        data['prev_close'] = data['close'].shift(1)
        data['prev_bb_upper'] = data['bb_upper'].shift(1)
        data['prev_bb_lower'] = data['bb_lower'].shift(1)
        buy_mask = (data['prev_close'] <= data['prev_bb_lower']) & (data['close'] > data['bb_lower'])
        sell_mask = (data['prev_close'] >= data['prev_bb_upper']) & (data['close'] < data['bb_upper'])
        signal_indices = data.index[buy_mask | sell_mask]
        if len(signal_indices) == 0:
            return signals

        start_pos = period + 2
        for idx in signal_indices:
            i = data.index.get_loc(idx)
            if i < start_pos:
                continue
            row = data.iloc[i]
            close_price = row['close']
            confidence = self.calculate_confidence(data, i)
            if confidence < min_confidence:
                continue
            prev_close = row['prev_close']
            prev_bb_lower = row['prev_bb_lower']
            if prev_close <= prev_bb_lower:
                signals.append(StrategySignal(
                    timestamp=idx, signal_type=SignalType.BUY, price=close_price,
                    confidence=confidence, strategy_name=self.name,
                    reason="价格从下轨反弹",
                    stop_loss=row['bb_lower'] * 0.98, take_profit=row['bb_middle']))
            else:
                signals.append(StrategySignal(
                    timestamp=idx, signal_type=SignalType.SELL, price=close_price,
                    confidence=confidence, strategy_name=self.name,
                    reason="价格从上轨回落",
                    stop_loss=row['bb_upper'] * 1.02, take_profit=row['bb_middle']))

        return signals

    def calculate_confidence(self, data: pd.DataFrame, signal_index: int) -> float:
        """计算信号置信度"""
        if signal_index < 10:
            return 0.5

        recent_data = data.iloc[signal_index-10:signal_index+1]

        # 布林带宽度（波动率）
        bb_width = (recent_data['bb_upper'].iloc[-1] -
                    recent_data['bb_lower'].iloc[-1]) / recent_data['bb_middle'].iloc[-1]

        # 价格位置
        price_position = (recent_data['close'].iloc[-1] - recent_data['bb_lower'].iloc[-1]) / \
            (recent_data['bb_upper'].iloc[-1] -
             recent_data['bb_lower'].iloc[-1])

        # 成交量确认
        volume_ratio = recent_data['volume'].iloc[-1] / \
            recent_data['volume'].mean(
        ) if recent_data['volume'].mean() > 0 else 1

        # 综合置信度
        confidence = min(0.9, max(
            0.1, (bb_width * 5 + abs(0.5 - price_position) * 2 + volume_ratio * 0.3) / 3))

        return confidence

@register_strategy("形态分析策略", {
    "category": "形态识别",
    "description": "基于K线形态识别的策略"
})
class PatternAnalysisStrategy(BaseStrategy):
    """形态分析策略"""

    def __init__(self, name: str = "形态分析策略"):
        super().__init__(name, StrategyType.PATTERN)
        self.recognizer = PatternRecognizer()

    def _init_default_parameters(self):
        """形态分析策略无额外参数"""
        pass

    def generate_signals(self, data: pd.DataFrame) -> List[StrategySignal]:
        """生成形态分析信号"""
        signals = []
        if 'code' not in data.columns:
            # 尝试从其他地方获取股票代码，但这应该是数据准备阶段的工作
            # logger.warning("K线数据缺少'code'列，形态分析可能不准确")
            # 假设一个默认代码或跳过
            return signals

        pattern_results = self.recognizer.recognize_all(data)

        for result in pattern_results:
            end_date = result['end_date']
            signals.append(StrategySignal(
                timestamp=end_date,
                signal_type=SignalType.BUY if result['signal'] == 'buy' else SignalType.SELL if result['signal'] == 'sell' else SignalType.HOLD,
                price=data.loc[end_date, 'close'],
                confidence=result.get('confidence', 0.5),
                strategy_name=self.name,
                reason=result.get('pattern_name', '未知形态')))

        return signals
