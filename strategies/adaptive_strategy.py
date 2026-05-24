#!/usr/bin/env python3
"""
自适应策略模块

使用统一的策略管理系统框架，完全基于pandas和TA-Lib实现，无hikyuu依赖
"""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime
from loguru import logger

# 导入统一策略管理系统
from core.strategy.base_strategy import BaseStrategy, StrategySignal, SignalType, StrategyType
from core.strategy import register_strategy
from core.stop_loss import AdaptiveStopLoss
from core.take_profit import AdaptiveTakeProfit

# 技术指标库
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    talib = None
    TALIB_AVAILABLE = False

logger = logger.bind(module=__name__)


@register_strategy("AdaptiveFactorWeave", metadata={
    "description": "基于FactorWeave框架的自适应止损止盈策略",
    "author": "FactorWeave 团队",
    "version": "3.0.0",
    "category": "adaptive",
    "dependencies": ["talib", "pandas"]
})
class AdaptiveFactorWeaveStrategy(BaseStrategy):
    """自适应FactorWeave策略（无hikyuu依赖版本）"""

    def __init__(self, name: str = "AdaptiveFactorWeave"):
        super().__init__(name, StrategyType.CUSTOM)
        self._init_default_parameters()
        self._signal_cache = {}  # 信号缓存

    def _init_default_parameters(self):
        """初始化默认参数"""
        # 资金管理参数
        self.add_parameter("init_cash", 100000, int, "初始资金", 10000, 1000000)
        self.add_parameter("position_size", 100, int, "仓位大小", 10, 1000)

        # 止损参数
        self.add_parameter("atr_period", 14, int, "ATR周期", 5, 30)
        self.add_parameter("atr_multiplier", 2.0, float, "ATR倍数", 1.0, 5.0)
        self.add_parameter("volatility_factor", 0.5, float, "波动率因子", 0.1, 1.0)
        self.add_parameter("trend_factor", 0.3, float, "趋势因子", 0.1, 1.0)
        self.add_parameter("market_factor", 0.2, float, "市场因子", 0.1, 1.0)
        self.add_parameter("min_stop_loss", 0.02, float, "最小止损", 0.01, 0.1)
        self.add_parameter("max_stop_loss", 0.1, float, "最大止损", 0.05, 0.2)
        self.add_parameter("fixed_stop_loss", 0.05, float, "固定止损", 0.02, 0.1)

        # 止盈参数
        self.add_parameter("ma_period", 20, int, "移动平均周期", 5, 50)
        self.add_parameter("volatility_period", 20, int, "波动率周期", 5, 50)
        self.add_parameter("min_take_profit", 0.05, float, "最小止盈", 0.02, 0.2)
        self.add_parameter("max_take_profit", 0.2, float, "最大止盈", 0.1, 0.5)
        self.add_parameter("trailing_profit", 0.03, float, "跟踪止盈", 0.01, 0.1)
        self.add_parameter("profit_lock", 0.05, float, "利润锁定", 0.02, 0.1)

        # 滑点参数
        self.add_parameter("slippage_percent", 0.01,
                           float, "滑点百分比", 0.001, 0.05)

        # 风险管理参数
        self.add_parameter("max_risk_per_trade", 0.02, float, "每笔最大风险", 0.01, 0.1)

    def generate_signals(self, data: pd.DataFrame) -> List[StrategySignal]:
        """
        生成交易信号（基于TA-Lib技术指标）
        """
        signals = []

        if data is None or data.empty or len(data) < 50:
            return signals

        try:
            # 数据预处理
            clean_data = self._prepare_data(data)
            if clean_data is None:
                return signals

            # 获取参数
            ma_period = self.get_parameter("ma_period")
            atr_period = self.get_parameter("atr_period")
            atr_multiplier = self.get_parameter("atr_multiplier")
            volatility_factor = self.get_parameter("volatility_factor")

            # 计算技术指标
            indicators = self._calculate_indicators(clean_data, ma_period, atr_period)

            if indicators is None:
                return signals

            # 生成信号
            signals = self._generate_adaptive_signals(clean_data, indicators, atr_multiplier, volatility_factor)

        except Exception as e:
            logger.error(f"自适应策略信号生成失败: {e}")

        return signals

    def _prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """数据预处理和验证"""
        try:
            # 复制数据
            clean_data = data.copy()
            
            # 确保必要的列存在
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in clean_data.columns]
            if missing_cols:
                logger.warning(f"缺少必要的数据列: {missing_cols}")
                return None

            # 处理缺失值
            clean_data = clean_data.fillna(method='ffill')
            
            # 确保数据类型正确
            for col in required_cols:
                clean_data[col] = pd.to_numeric(clean_data[col], errors='coerce')
            
            # 移除无效数据
            clean_data = clean_data.dropna()
            
            if len(clean_data) < 50:
                logger.warning(f"有效数据不足，需要至少50条记录，当前只有{len(clean_data)}条")
                return None
                
            return clean_data
            
        except Exception as e:
            logger.error(f"数据预处理失败: {e}")
            return None

    def _calculate_indicators(self, data: pd.DataFrame, ma_period: int, atr_period: int) -> Dict:
        """计算技术指标"""
        try:
            indicators = {}
            
            # 移动平均线
            indicators['sma'] = talib.SMA(data['close'].values, timeperiod=ma_period)
            indicators['ema'] = talib.EMA(data['close'].values, timeperiod=ma_period)
            
            # ATR指标
            indicators['atr'] = talib.ATR(data['high'].values, data['low'].values, 
                                       data['close'].values, timeperiod=atr_period)
            
            # MACD指标
            indicators['macd'], indicators['macd_signal'], indicators['macd_hist'] = talib.MACD(
                data['close'].values, fastperiod=12, slowperiod=26, signalperiod=9)
            
            # RSI指标
            indicators['rsi'] = talib.RSI(data['close'].values, timeperiod=14)
            
            # 布林带
            indicators['bb_upper'], indicators['bb_middle'], indicators['bb_lower'] = talib.BBANDS(
                data['close'].values, timeperiod=20, nbdevup=2, nbdevdn=2)
            
            return indicators
            
        except Exception as e:
            logger.error(f"技术指标计算失败: {e}")
            return None

    def _generate_adaptive_signals(self, data: pd.DataFrame, indicators: Dict,
                                 atr_multiplier: float, volatility_factor: float) -> List[StrategySignal]:
        """生成自适应交易信号（优先使用向量化，失败回退到循环）"""
        try:
            signals = self._generate_adaptive_signals_vectorized(
                data, indicators, atr_multiplier, volatility_factor)
            return signals
        except Exception as e:
            logger.warning(f"向量化信号生成失败，回退到循环模式: {e}")
            return self._generate_adaptive_signals_loop(
                data, indicators, atr_multiplier, volatility_factor)

    def _generate_adaptive_signals_vectorized(self, data: pd.DataFrame, indicators: Dict,
                                              atr_multiplier: float, volatility_factor: float) -> List[StrategySignal]:
        """向量化生成自适应交易信号（numpy批量计算替代逐行循环）"""
        signals = []

        try:
            n = len(data)
            start_idx = max(20, 50)

            # 提取numpy数组向量化计算
            close = data['close'].values
            sma = indicators['sma']
            rsi = indicators['rsi']
            macd = indicators['macd']
            macd_signal = indicators['macd_signal']
            fixed_stop_loss = self.get_parameter("fixed_stop_loss")
            min_take_profit = self.get_parameter("min_take_profit")

            # ---- 买入条件向量化 ----
            # 价格突破SMA: close > sma AND prev_close <= prev_sma
            prev_close = np.roll(close, 1)
            prev_sma = np.roll(sma, 1)
            prev_close[0] = close[0]
            prev_sma[0] = sma[0]
            buy_cross_sma = (close > sma) & (prev_close <= prev_sma)

            # RSI在合理区间
            rsi_zone = (rsi > 30) & (rsi < 70)

            # MACD金叉: macd > macd_signal AND prev_macd <= prev_macd_signal
            prev_macd = np.roll(macd, 1)
            prev_macd_sig = np.roll(macd_signal, 1)
            prev_macd[0] = macd[0]
            prev_macd_sig[0] = macd_signal[0]
            macd_golden = (macd > macd_signal) & (prev_macd <= prev_macd_sig)

            buy_mask = buy_cross_sma & rsi_zone & macd_golden

            # ---- 卖出条件向量化 ----
            # 价格跌破SMA: close < sma AND prev_close >= prev_sma
            sell_cross_sma = (close < sma) & (prev_close >= prev_sma)
            # RSI超买
            rsi_overbought = rsi > 80
            # MACD死叉: macd < macd_signal AND prev_macd >= prev_macd_signal
            macd_death = (macd < macd_signal) & (prev_macd >= prev_macd_sig)

            sell_mask = sell_cross_sma | rsi_overbought | macd_death

            # ---- 生成信号（仅遍历命中索引） ----
            buy_indices = np.where(buy_mask)[0]
            sell_indices = np.where(sell_mask)[0]

            for i in buy_indices:
                if i < start_idx:
                    continue
                if np.isnan(sma[i]) or np.isnan(rsi[i]) or np.isnan(macd[i]):
                    continue
                current_price = close[i]
                confidence = self._calculate_dynamic_confidence(indicators, i, volatility_factor)
                stop_loss_price = current_price * (1 - fixed_stop_loss)
                take_profit_price = current_price * (1 + min_take_profit)

                signals.append(StrategySignal(
                    timestamp=data.index[i],
                    signal_type=SignalType.BUY,
                    price=current_price,
                    confidence=confidence,
                    strategy_name=self.name,
                    reason=f"SMA突破 + MACD金叉，RSI:{rsi[i]:.2f}",
                    stop_loss=stop_loss_price,
                    take_profit=take_profit_price
                ))

            for i in sell_indices:
                if i < start_idx:
                    continue
                if np.isnan(sma[i]) or np.isnan(rsi[i]) or np.isnan(macd[i]):
                    continue
                current_price = close[i]
                confidence = self._calculate_dynamic_confidence(indicators, i, volatility_factor)
                stop_loss_price = current_price * (1 - fixed_stop_loss)
                take_profit_price = current_price * (1 + min_take_profit)

                signals.append(StrategySignal(
                    timestamp=data.index[i],
                    signal_type=SignalType.SELL,
                    price=current_price,
                    confidence=confidence,
                    strategy_name=self.name,
                    reason=f"SMA跌破或超买信号，RSI:{rsi[i]:.2f}",
                    stop_loss=stop_loss_price,
                    take_profit=take_profit_price
                ))

        except Exception as e:
            logger.error(f"向量化信号生成失败: {e}")
            raise

        return signals

    def _generate_adaptive_signals_loop(self, data: pd.DataFrame, indicators: Dict,
                                        atr_multiplier: float, volatility_factor: float) -> List[StrategySignal]:
        """生成自适应交易信号（原始循环版本，作为向量化失败时的fallback）"""
        signals = []

        try:
            # 从指标周期之后开始生成信号
            start_idx = max(20, 50)

            for i in range(start_idx, len(data)):
                current_data = data.iloc[i]
                prev_data = data.iloc[i-1] if i > 0 else current_data

                # 跳过缺失指标值的索引
                current_sma = indicators['sma'][i]
                current_rsi = indicators['rsi'][i]
                current_macd = indicators['macd'][i]
                current_macd_signal = indicators['macd_signal'][i]
                current_atr = indicators['atr'][i]

                if np.isnan(current_sma) or np.isnan(current_rsi) or np.isnan(current_macd):
                    continue

                # 自适应止损价格
                stop_loss_price = current_data['close'] * (1 - self.get_parameter("fixed_stop_loss"))
                take_profit_price = current_data['close'] * (1 + self.get_parameter("min_take_profit"))

                # 动态置信度计算
                confidence = self._calculate_dynamic_confidence(
                    indicators, i, volatility_factor)

                # 买入信号逻辑
                buy_signal = (
                    current_data['close'] > current_sma and
                    prev_data['close'] <= indicators['sma'][i-1] if i > 0 else False and
                    30 < current_rsi < 70 and
                    current_macd > current_macd_signal and
                    (indicators['macd'][i-1] <= indicators['macd_signal'][i-1] if i > 0 else False)
                )

                if buy_signal:
                    signals.append(StrategySignal(
                        timestamp=current_data.name if hasattr(current_data, 'name') else i,
                        signal_type=SignalType.BUY,
                        price=current_data['close'],
                        confidence=confidence,
                        strategy_name=self.name,
                        reason=f"SMA突破 + MACD金叉，RSI:{current_rsi:.2f}",
                        stop_loss=stop_loss_price,
                        take_profit=take_profit_price
                    ))

                # 卖出信号逻辑
                sell_signal = (
                    (current_data['close'] < current_sma and
                     prev_data['close'] >= indicators['sma'][i-1] if i > 0 else False) or
                    current_rsi > 80 or
                    (current_macd < current_macd_signal and
                     indicators['macd'][i-1] >= indicators['macd_signal'][i-1] if i > 0 else False)
                )

                if sell_signal:
                    signals.append(StrategySignal(
                        timestamp=current_data.name if hasattr(current_data, 'name') else i,
                        signal_type=SignalType.SELL,
                        price=current_data['close'],
                        confidence=confidence,
                        strategy_name=self.name,
                        reason=f"SMA跌破或超买信号，RSI:{current_rsi:.2f}",
                        stop_loss=stop_loss_price,
                        take_profit=take_profit_price
                    ))

        except Exception as e:
            logger.error(f"循环信号生成失败: {e}")

        return signals

    def _calculate_dynamic_confidence(self, indicators: Dict, index: int, volatility_factor: float) -> float:
        """动态计算信号置信度"""
        try:
            base_confidence = 0.6
            
            # 基于RSI调整置信度
            rsi = indicators['rsi'][index]
            if not np.isnan(rsi):
                if 30 <= rsi <= 70:  # 正常范围
                    rsi_factor = 1.0
                else:  # 超买超卖
                    rsi_factor = 0.8
            else:
                rsi_factor = 0.7
            
            # 基于ATR(波动率)调整置信度
            atr = indicators['atr'][index]
            if not np.isnan(atr) and len(indicators['atr']) > 20:
                avg_atr = np.nanmean(indicators['atr'][max(0, index-20):index])
                if avg_atr > 0:
                    atr_ratio = atr / avg_atr
                    if atr_ratio < 1.2:  # 较低波动率，置信度较高
                        atr_factor = 1.1
                    elif atr_ratio > 2.0:  # 高波动率，置信度较低
                        atr_factor = 0.8
                    else:
                        atr_factor = 1.0
                else:
                    atr_factor = 1.0
            else:
                atr_factor = 1.0
            
            # 合成置信度
            confidence = base_confidence * rsi_factor * atr_factor * volatility_factor
            return max(0.1, min(0.95, confidence))
            
        except Exception as e:
            logger.error(f"置信度计算失败: {e}")
            return 0.5

    def _calculate_position_size(self, data: pd.DataFrame, atr: np.ndarray) -> float:
        """基于ATR和风险参数计算仓位大小"""
        try:
            # 获取参数
            init_cash = self.get_parameter("init_cash")
            fixed_stop_loss = self.get_parameter("fixed_stop_loss")
            max_risk_per_trade = self.get_parameter("max_risk_per_trade", 0.02)  # 2%最大风险
            
            if data.empty or len(atr) == 0:
                return 1.0  # 默认1手
            
            current_atr = atr[-1]
            current_price = data['close'].iloc[-1]
            
            if np.isnan(current_atr) or current_atr <= 0 or current_price <= 0:
                return 1.0
            
            # 基于ATR计算风险
            atr_risk = current_atr * self.get_parameter("atr_multiplier", 2.0)
            risk_amount = current_price * atr_risk
            
            # 基于资金管理计算仓位
            max_risk_amount = init_cash * max_risk_per_trade
            position_size = max_risk_amount / risk_amount if risk_amount > 0 else 1.0
            
            # 确保仓位在合理范围内
            position_size = max(0.1, min(10.0, position_size))
            
            return position_size
            
        except Exception as e:
            logger.error(f"仓位大小计算失败: {e}")
            return 1.0

    def _calculate_stop_loss(self, data: pd.DataFrame, atr: np.ndarray, is_long: bool) -> float:
        """计算止损价格"""
        try:
            current_price = data['close'].iloc[-1]
            current_atr = atr[-1]
            
            if np.isnan(current_atr) or current_atr <= 0:
                # 如果没有ATR数据，使用固定百分比
                fixed_stop_loss = self.get_parameter("fixed_stop_loss")
                return current_price * (1 - fixed_stop_loss) if is_long else current_price * (1 + fixed_stop_loss)
            
            atr_multiplier = self.get_parameter("atr_multiplier", 2.0)
            atr_stop = current_atr * atr_multiplier
            
            if is_long:
                return current_price - atr_stop
            else:
                return current_price + atr_stop
                
        except Exception as e:
            logger.error(f"止损价格计算失败: {e}")
            return data['close'].iloc[-1] * 0.95  # 默认5%止损

    def _calculate_take_profit(self, data: pd.DataFrame, atr: np.ndarray, stop_loss: float, is_long: bool) -> float:
        """计算止盈价格"""
        try:
            current_price = data['close'].iloc[-1]
            min_take_profit = self.get_parameter("min_take_profit")
            max_take_profit = self.get_parameter("max_take_profit")
            
            # 基于最小和最大盈利目标计算
            if is_long:
                min_profit = current_price * (1 + min_take_profit)
                max_profit = current_price * (1 + max_take_profit)
            else:
                min_profit = current_price * (1 - min_take_profit)
                max_profit = current_price * (1 - max_take_profit)
            
            # 基于ATR动态调整
            if not np.isnan(atr[-1]) and atr[-1] > 0:
                atr_profit = atr[-1] * self.get_parameter("atr_multiplier", 2.0)
                if is_long:
                    atr_target = current_price + atr_profit
                else:
                    atr_target = current_price - atr_profit
                
                # 在固定目标和ATR目标之间选择合适的
                final_target = max(min_profit, atr_target) if is_long else min(min_profit, atr_target)
            else:
                final_target = min_profit
            
            return final_target
            
        except Exception as e:
            logger.error(f"止盈价格计算失败: {e}")
            current_price = data['close'].iloc[-1]
            return current_price * 1.05 if is_long else current_price * 0.95

    def calculate_confidence(self, data: pd.DataFrame, signal_index: int) -> float:
        """计算信号置信度"""
        # 基于系统参数的复杂度计算置信度
        return 0.7  # 固定置信度，可以根据实际情况调整

    def get_required_columns(self) -> List[str]:
        """获取所需的数据列"""
        return ['open', 'high', 'low', 'close', 'volume']

    def get_strategy_info(self) -> Dict[str, Any]:
        """获取策略信息（基于TA-Lib无hikyuu版本）"""
        info = super().get_strategy_info()
        info.update({
            "version": "3.0.0",
            "dependencies": ["pandas", "numpy", "talib"],
            "indicators": ["SMA", "EMA", "ATR", "MACD", "RSI", "Bollinger Bands"],
            "signal_generation": "基于多指标组合的自适应信号生成",
            "risk_management": "基于ATR的动态止损止盈",
            "confidence_calculation": "基于RSI和ATR波动的动态置信度",
            "no_hikyuu_dependency": True,
            "signal_cache": "已从系统实例缓存改为信号缓存"
        })
        return info


def create_adaptive_strategy():
    """创建自适应策略（无hikyuu版本）"""
    return AdaptiveFactorWeaveStrategy()


# 已废弃：create_adaptive_hikyuu_strategy函数已被移除，请使用create_adaptive_strategy