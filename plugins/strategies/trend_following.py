from loguru import logger
#!/usr/bin/env python3
"""
趋势跟踪策略模块

实现多种趋势跟踪策略，包括：
- 移动平均趋势策略
- 突破策略
- 动量策略
- 自适应趋势策略

使用统一的策略管理系统框架
"""

from core.strategy import register_strategy
from core.strategy.base_strategy import BaseStrategy, StrategySignal, SignalType, StrategyType
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

# 导入统一策略管理系统

class TrendDirection(Enum):
    """趋势方向"""
    UP = "up"           # 上升趋势
    DOWN = "down"       # 下降趋势
    SIDEWAYS = "sideways"  # 横盘趋势

@register_strategy("MovingAverageTrend", metadata={
    "description": "基于移动平均线的趋势跟踪策略",
    "author": "FactorWeave 团队",
    "version": "2.0.0",
    "category": "trend_following"
})
class MovingAverageTrendStrategy(BaseStrategy):
    """移动平均趋势策略"""

    def __init__(self, name: str = "MovingAverageTrend"):
        super().__init__(name, StrategyType.TREND_FOLLOWING)
        self._init_default_parameters()

    def _init_default_parameters(self):
        """初始化默认参数"""
        self.add_parameter("short_period", 20, int, "短期移动平均周期", 5, 50)
        self.add_parameter("long_period", 50, int, "长期移动平均周期", 20, 200)
        self.add_parameter("signal_period", 10, int, "信号确认周期", 3, 20)

    def generate_signals(self, data: pd.DataFrame) -> List[StrategySignal]:
        """
        生成交易信号

        Args:
            data: 包含OHLCV数据的DataFrame

        Returns:
            交易信号列表
        """
        short_period = self.get_parameter("short_period")
        long_period = self.get_parameter("long_period")

        if len(data) < long_period:
            return []

        close = data['close']
        ma_short = close.rolling(window=short_period).mean()
        ma_long = close.rolling(window=long_period).mean()

        signal = np.where(ma_short.values > ma_long.values, 1,
                          np.where(ma_short.values < ma_long.values, -1, 0))
        signal_change = np.diff(signal, prepend=signal[0])

        buy_indices = np.where(signal_change == 2)[0]
        sell_indices = np.where(signal_change == -2)[0]

        signals = [
            StrategySignal(
                timestamp=data.index[i],
                signal_type=SignalType.BUY,
                price=float(close.iloc[i]),
                confidence=self.calculate_confidence(data, i),
                strategy_name=self.name,
                reason=f"短期MA({short_period})上穿长期MA({long_period})",
                stop_loss=float(close.iloc[i]) * 0.95,
                take_profit=float(close.iloc[i]) * 1.1
            )
            for i in buy_indices if i >= long_period
        ]
        signals += [
            StrategySignal(
                timestamp=data.index[i],
                signal_type=SignalType.SELL,
                price=float(close.iloc[i]),
                confidence=self.calculate_confidence(data, i),
                strategy_name=self.name,
                reason=f"短期MA({short_period})下穿长期MA({long_period})",
                stop_loss=float(close.iloc[i]) * 1.05,
                take_profit=float(close.iloc[i]) * 0.9
            )
            for i in sell_indices if i >= long_period
        ]

        return signals

    def calculate_confidence(self, data: pd.DataFrame, signal_index: int) -> float:
        """计算信号置信度"""
        signal_period = self.get_parameter("signal_period")
        start_idx = max(0, signal_index - signal_period)
        recent_data = data.iloc[start_idx:signal_index + 1]

        if len(recent_data) < 2:
            return 0.5

        # 基于价格趋势强度计算置信度
        price_change = (recent_data['close'].iloc[-1] -
                        recent_data['close'].iloc[0]) / recent_data['close'].iloc[0]
        volatility = recent_data['close'].std() / recent_data['close'].mean()

        # 趋势强度
        trend_strength = abs(price_change) / (volatility + 0.01)
        confidence = min(0.9, max(0.1, trend_strength / 2))

        return confidence

    def get_required_columns(self) -> List[str]:
        """获取所需的数据列"""
        return ['open', 'high', 'low', 'close', 'volume']

@register_strategy("Breakout", metadata={
    "description": "基于价格突破的趋势策略",
    "author": "FactorWeave 团队",
    "version": "2.0.0",
    "category": "trend_following"
})
class BreakoutStrategy(BaseStrategy):
    """突破策略"""

    def __init__(self, name: str = "Breakout"):
        super().__init__(name, StrategyType.TREND_FOLLOWING)
        self._init_default_parameters()

    def _init_default_parameters(self):
        """初始化默认参数"""
        self.add_parameter("lookback_period", 20, int, "回看周期", 10, 50)
        self.add_parameter("volume_threshold", 1.5, float, "成交量阈值倍数", 1.0, 3.0)
        self.add_parameter("min_breakout_pct", 0.02,
                           float, "最小突破幅度", 0.01, 0.1)

    def generate_signals(self, data: pd.DataFrame) -> List[StrategySignal]:
        """生成突破信号"""
        lookback_period = self.get_parameter("lookback_period")
        volume_threshold = self.get_parameter("volume_threshold")
        min_breakout_pct = self.get_parameter("min_breakout_pct")

        if len(data) < lookback_period:
            return []

        close = data['close']
        high = data['high']
        low = data['low']
        volume = data['volume']

        resistance = high.rolling(window=lookback_period).max()
        support = low.rolling(window=lookback_period).min()
        avg_volume = volume.rolling(window=lookback_period).mean()

        c_vals = close.values
        r_vals = resistance.values
        s_vals = support.values
        v_vals = volume.values
        a_vals = avg_volume.values

        n = len(data)
        signals = []

        for i in range(lookback_period, n):
            c = c_vals[i]
            prev_r = r_vals[i-1]
            prev_s = s_vals[i-1]
            prev_avg_v = a_vals[i-1]

            if (c > prev_r
                and (c - prev_r) / prev_r > min_breakout_pct
                and v_vals[i] > prev_avg_v * volume_threshold):
                signals.append(StrategySignal(
                    timestamp=data.index[i],
                    signal_type=SignalType.BUY,
                    price=c,
                    confidence=self.calculate_confidence(data, i),
                    strategy_name=self.name,
                    reason=f"向上突破阻力位{prev_r:.3f}，成交量放大",
                    stop_loss=prev_r * 0.98,
                    take_profit=c * 1.15
                ))
            elif (c < prev_s
                  and (prev_s - c) / prev_s > min_breakout_pct
                  and v_vals[i] > prev_avg_v * volume_threshold):
                signals.append(StrategySignal(
                    timestamp=data.index[i],
                    signal_type=SignalType.SELL,
                    price=c,
                    confidence=self.calculate_confidence(data, i),
                    strategy_name=self.name,
                    reason=f"向下突破支撑位{prev_s:.3f}，成交量放大",
                    stop_loss=prev_s * 1.02,
                    take_profit=c * 0.85
                ))

        return signals

    def calculate_confidence(self, data: pd.DataFrame, signal_index: int) -> float:
        """计算突破置信度"""
        recent_data = data.iloc[max(0, signal_index-5):signal_index+1]

        if len(recent_data) < 2:
            return 0.5

        # 基于成交量和价格变化计算置信度
        volume_ratio = recent_data['volume'].iloc[-1] / \
            recent_data['volume'].mean()
        price_change = abs(recent_data['close'].iloc[-1] -
                           recent_data['close'].iloc[0]) / recent_data['close'].iloc[0]

        confidence = min(0.9, max(0.1, (volume_ratio * price_change) / 3))
        return confidence

    def get_required_columns(self) -> List[str]:
        """获取所需的数据列"""
        return ['open', 'high', 'low', 'close', 'volume']

@register_strategy("Momentum", metadata={
    "description": "基于动量指标的趋势策略",
    "author": "FactorWeave 团队",
    "version": "2.0.0",
    "category": "momentum"
})
class MomentumStrategy(BaseStrategy):
    """动量策略"""

    def __init__(self, name: str = "Momentum"):
        super().__init__(name, StrategyType.MOMENTUM)
        self._init_default_parameters()

    def _init_default_parameters(self):
        """初始化默认参数"""
        self.add_parameter("momentum_period", 14, int, "动量周期", 5, 30)
        self.add_parameter("rsi_period", 14, int, "RSI周期", 5, 30)
        self.add_parameter("rsi_oversold", 30.0, float, "RSI超卖阈值", 20.0, 40.0)
        self.add_parameter("rsi_overbought", 70.0,
                           float, "RSI超买阈值", 60.0, 80.0)

    def generate_signals(self, data: pd.DataFrame) -> List[StrategySignal]:
        """生成动量信号"""
        momentum_period = self.get_parameter("momentum_period")
        rsi_period = self.get_parameter("rsi_period")
        rsi_oversold = self.get_parameter("rsi_oversold")
        rsi_overbought = self.get_parameter("rsi_overbought")

        min_period = max(momentum_period, rsi_period)
        if len(data) < min_period:
            return []

        close = data['close']
        momentum = close.pct_change(momentum_period)
        rsi = self._calculate_rsi(close, rsi_period)

        m_vals = momentum.values
        r_vals = rsi.values
        c_vals = close.values

        signals = [
            StrategySignal(
                timestamp=data.index[i],
                signal_type=SignalType.BUY,
                price=c_vals[i],
                confidence=self.calculate_confidence(data, i),
                strategy_name=self.name,
                reason=f"动量向上({m_vals[i]:.3f})且RSI超卖({r_vals[i]:.1f})",
                stop_loss=c_vals[i] * 0.95,
                take_profit=c_vals[i] * 1.1
            )
            for i in range(min_period, len(data))
            if m_vals[i] > 0 and r_vals[i] < rsi_oversold
        ] + [
            StrategySignal(
                timestamp=data.index[i],
                signal_type=SignalType.SELL,
                price=c_vals[i],
                confidence=self.calculate_confidence(data, i),
                strategy_name=self.name,
                reason=f"动量向下({m_vals[i]:.3f})且RSI超买({r_vals[i]:.1f})",
                stop_loss=c_vals[i] * 1.05,
                take_profit=c_vals[i] * 0.9
            )
            for i in range(min_period, len(data))
            if m_vals[i] < 0 and r_vals[i] > rsi_overbought
        ]

        return signals

    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_confidence(self, data: pd.DataFrame, signal_index: int) -> float:
        """计算动量置信度"""
        recent_data = data.iloc[max(0, signal_index-5):signal_index+1]

        if len(recent_data) < 2:
            return 0.5

        # 基于动量强度和RSI极值计算置信度
        momentum_strength = abs(recent_data['momentum'].iloc[-1])
        rsi_extreme = min(recent_data['rsi'].iloc[-1],
                          100 - recent_data['rsi'].iloc[-1]) / 50

        confidence = min(0.9, max(0.1, (momentum_strength + rsi_extreme) / 2))
        return confidence

    def get_required_columns(self) -> List[str]:
        """获取所需的数据列"""
        return ['open', 'high', 'low', 'close', 'volume']

@register_strategy("AdaptiveTrend", metadata={
    "description": "自适应趋势跟踪策略",
    "author": "FactorWeave 团队",
    "version": "2.0.0",
    "category": "trend_following"
})
class AdaptiveTrendStrategy(BaseStrategy):
    """自适应趋势策略"""

    def __init__(self, name: str = "AdaptiveTrend"):
        super().__init__(name, StrategyType.TREND_FOLLOWING)
        self._init_default_parameters()

    def _init_default_parameters(self):
        """初始化默认参数"""
        self.add_parameter("volatility_period", 20, int, "波动率周期", 10, 50)
        self.add_parameter("trend_strength_period", 14, int, "趋势强度周期", 5, 30)

    def generate_signals(self, data: pd.DataFrame) -> List[StrategySignal]:
        """生成自适应趋势信号"""
        signals = []
        volatility_period = self.get_parameter("volatility_period")
        trend_strength_period = self.get_parameter("trend_strength_period")

        if len(data) < max(volatility_period, trend_strength_period):
            return signals

        # 计算自适应指标
        data = data.copy()
        data['volatility'] = data['close'].rolling(
            window=volatility_period).std()
        data['trend_strength'] = self._calculate_trend_strength(data)
        data['adaptive_ma'] = self._calculate_adaptive_ma(data)

        for i in range(max(volatility_period, trend_strength_period), len(data)):
            current = data.iloc[i]
            prev = data.iloc[i-1]

            # 识别趋势方向
            trend_direction = self._identify_trend(data.iloc[i-5:i+1])

            # 生成信号
            if (trend_direction == TrendDirection.UP and
                current['close'] > current['adaptive_ma'] and
                    prev['close'] <= prev['adaptive_ma']):

                confidence = self.calculate_confidence(data, i)

                signals.append(StrategySignal(
                    timestamp=data.index[i],
                    signal_type=SignalType.BUY,
                    price=current['close'],
                    confidence=confidence,
                    strategy_name=self.name,
                    reason=f"上升趋势确认，价格突破自适应均线",
                    stop_loss=current['adaptive_ma'] * 0.98,
                    take_profit=current['close'] * 1.12
                ))

            elif (trend_direction == TrendDirection.DOWN and
                  current['close'] < current['adaptive_ma'] and
                  prev['close'] >= prev['adaptive_ma']):

                confidence = self.calculate_confidence(data, i)

                signals.append(StrategySignal(
                    timestamp=data.index[i],
                    signal_type=SignalType.SELL,
                    price=current['close'],
                    confidence=confidence,
                    strategy_name=self.name,
                    reason=f"下降趋势确认，价格跌破自适应均线",
                    stop_loss=current['adaptive_ma'] * 1.02,
                    take_profit=current['close'] * 0.88
                ))

        return signals

    def _calculate_trend_strength(self, data: pd.DataFrame) -> pd.Series:
        """计算趋势强度"""
        period = self.get_parameter("trend_strength_period")
        return data['close'].rolling(window=period).apply(
            lambda x: (x.iloc[-1] - x.iloc[0]) / x.iloc[0] if len(x) > 0 else 0
        )

    def _calculate_adaptive_ma(self, data: pd.DataFrame) -> pd.Series:
        """计算自适应移动平均"""
        # 基于波动率调整移动平均周期
        base_period = 20
        volatility_factor = data['volatility'] / \
            data['volatility'].rolling(window=50).mean()
        adaptive_period = (
            base_period / volatility_factor).fillna(base_period).clip(5, 50)

        # 计算自适应移动平均
        adaptive_ma = pd.Series(index=data.index, dtype=float)
        for i in range(len(data)):
            period = int(adaptive_period.iloc[i])
            start_idx = max(0, i - period + 1)
            adaptive_ma.iloc[i] = data['close'].iloc[start_idx:i+1].mean()

        return adaptive_ma

    def _identify_trend(self, recent_data: pd.DataFrame) -> TrendDirection:
        """识别趋势方向"""
        if len(recent_data) < 3:
            return TrendDirection.SIDEWAYS

        # 计算价格变化趋势
        price_trend = (recent_data['close'].iloc[-1] -
                       recent_data['close'].iloc[0]) / recent_data['close'].iloc[0]

        if price_trend > 0.02:
            return TrendDirection.UP
        elif price_trend < -0.02:
            return TrendDirection.DOWN
        else:
            return TrendDirection.SIDEWAYS

    def calculate_confidence(self, data: pd.DataFrame, signal_index: int) -> float:
        """计算自适应置信度"""
        recent_data = data.iloc[max(0, signal_index-5):signal_index+1]

        if len(recent_data) < 2:
            return 0.5

        # 基于趋势强度和一致性计算置信度
        trend_strength = abs(recent_data['trend_strength'].iloc[-1])
        trend_consistency = self._calculate_trend_consistency(recent_data)

        confidence = min(
            0.9, max(0.1, (trend_strength + trend_consistency) / 2))
        return confidence

    def _calculate_trend_consistency(self, data: pd.DataFrame) -> float:
        """计算趋势一致性"""
        if len(data) < 3:
            return 0.5

        # 计算价格变化方向的一致性
        price_changes = data['close'].diff().dropna()
        if len(price_changes) == 0:
            return 0.5

        positive_changes = (price_changes > 0).sum()
        total_changes = len(price_changes)

        # 一致性得分：偏向一个方向的程度
        consistency = abs(positive_changes / total_changes - 0.5) * 2
        return consistency

    def get_required_columns(self) -> List[str]:
        """获取所需的数据列"""
        return ['open', 'high', 'low', 'close', 'volume']

class TrendFollowingManager:
    """趋势跟踪策略管理器（向后兼容）"""

    def __init__(self):
        """初始化管理器"""
        # 导入统一策略管理系统
        from core.strategy import get_strategy_engine, get_strategy_factory

        self.engine = get_strategy_engine()
        self.factory = get_strategy_factory()

        # 注册策略
        self.strategies = {
            "MovingAverageTrend": MovingAverageTrendStrategy,
            "Breakout": BreakoutStrategy,
            "Momentum": MomentumStrategy,
            "AdaptiveTrend": AdaptiveTrendStrategy
        }

    def generate_all_signals(self, data: pd.DataFrame) -> Dict[str, List[StrategySignal]]:
        """生成所有策略信号"""
        all_signals = {}

        for strategy_name in self.strategies.keys():
            try:
                result = self.engine.execute_strategy(strategy_name, data)
                if result.success:
                    all_signals[strategy_name] = result.signals
                else:
                    all_signals[strategy_name] = []
            except Exception as e:
                logger.info(f"策略 {strategy_name} 执行失败: {e}")
                all_signals[strategy_name] = []

        return all_signals

    def get_consensus_signals(self, data: pd.DataFrame, min_agreement: int = 2) -> List[StrategySignal]:
        """获取一致性信号"""
        all_signals = self.generate_all_signals(data)
        consensus_signals = []

        # 简化的一致性逻辑
        signal_counts = {}
        for strategy_name, signals in all_signals.items():
            for signal in signals:
                key = (signal.timestamp, signal.signal_type)
                if key not in signal_counts:
                    signal_counts[key] = []
                signal_counts[key].append(signal)

        # 选择达到最小一致性要求的信号
        for key, signals in signal_counts.items():
            if len(signals) >= min_agreement:
                # 使用第一个信号作为代表，平均置信度
                representative_signal = signals[0]
                avg_confidence = sum(
                    s.confidence for s in signals) / len(signals)
                representative_signal.confidence = avg_confidence
                representative_signal.reason = f"多策略一致性信号({len(signals)}个策略)"
                consensus_signals.append(representative_signal)

        return consensus_signals

def create_trend_following_manager() -> TrendFollowingManager:
    """创建趋势跟踪管理器（向后兼容函数）"""
    return TrendFollowingManager()

if __name__ == "__main__":
    # 测试代码
    # EXCLUSION: np.random usage in if __name__ block for local testing only
    import matplotlib.pyplot as plt

    # 生成模拟数据
    dates = pd.date_range('2023-01-01', periods=200, freq='D')
    np.random.seed(42)

    # 模拟价格数据（带趋势）
    trend = np.linspace(100, 120, 200)
    noise = np.random.normal(0, 2, 200)
    prices = trend + noise + np.sin(np.arange(200) * 0.1) * 3

    data = pd.DataFrame({
        'open': prices * 0.99,
        'high': prices * 1.02,
        'low': prices * 0.98,
        'close': prices,
        'volume': np.random.lognormal(10, 0.5, 200)
    }, index=dates)

    # 创建策略管理器
    manager = create_trend_following_manager()

    # 生成信号
    all_signals = manager.generate_all_signals(data)
    consensus_signals = manager.get_consensus_signals(data)

    logger.info("趋势跟踪策略测试结果:")
    logger.info("=" * 50)

    for strategy_name, signals in all_signals.items():
        logger.info(f"{strategy_name}: {len(signals)} 个信号")
        if signals:
            avg_confidence = np.mean([s.confidence for s in signals])
            logger.info(f"  平均置信度: {avg_confidence:.3f}")

    logger.info(f"\n一致性信号: {len(consensus_signals)} 个")
    if consensus_signals:
        avg_confidence = np.mean([s.confidence for s in consensus_signals])
        logger.info(f"平均置信度: {avg_confidence:.3f}")

        logger.info("\n一致性信号详情:")
        for signal in consensus_signals[:5]:  # 显示前5个信号
            logger.info(f"  {signal.timestamp.date()}: {signal.signal_type.value} @ {signal.price:.3f} (置信度: {signal.confidence:.3f})")
