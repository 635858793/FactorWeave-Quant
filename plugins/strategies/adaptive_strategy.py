from loguru import logger
#!/usr/bin/env python3
"""
自适应策略模块

完全脱离 hikyuu 依赖，基于 pandas 的纯 Python 自适应交易策略
支持止损止盈、趋势识别、波动率调整等功能
"""

import numpy as np
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime, timedelta

# 移除 hikyuu 依赖，纯 pandas 实现
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    logger.warning("TA-Lib 不可用，将使用内置指标计算")

# 导入统一策略管理系统
from core.strategy.base_strategy import BaseStrategy, StrategySignal, SignalType, StrategyType
from core.strategy import register_strategy
from core.stop_loss import AdaptiveStopLoss
from core.take_profit import AdaptiveTakeProfit


@register_strategy("AdaptivePandas", metadata={
    "description": "完全基于pandas的自适应止损止盈策略",
    "author": "FactorWeave-Quant 团队",
    "version": "3.0.0",
    "category": "adaptive",
    "dependencies": ["pandas", "numpy"],
    "hikyuu_free": True
})
class AdaptivePandasStrategy(BaseStrategy):
    """基于pandas的自适应策略，无需外部依赖"""

    def __init__(self, name: str = "AdaptivePandas"):
        super().__init__(name, StrategyType.CUSTOM)
        self._init_default_parameters()
        self._ta_lib_available = TALIB_AVAILABLE
        self._calculation_history = []
        
        # 添加plugin_info属性以实现IStrategyPlugin接口
        self._plugin_info = {
            "name": "AdaptivePandasStrategy",
            "display_name": "自适应止损止盈策略",
            "description": "基于pandas的自适应交易策略，支持止损止盈、趋势识别、波动率调整等功能",
            "version": "3.0.0",
            "author": "FactorWeave-Quant 团队",
            "strategy_type": "adaptive",
            "supported_assets": ["stock"],
            "risk_level": "medium",
            "tags": ["adaptive", "stop_loss", "take_profit", "pandas"],
            "dependencies": ["pandas", "numpy"],
            "hikyuu_free": True
        }

    @property
    def plugin_info(self) -> Dict[str, Any]:
        """获取插件基本信息"""
        return self._plugin_info

    def _init_default_parameters(self):
        """初始化默认参数"""
        # 资金管理参数
        self.add_parameter("init_cash", 100000, int, "初始资金", 10000, 1000000)
        self.add_parameter("fixed_count", 100, int, "固定股数", 10, 1000)

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

    def generate_signals(self, data: pd.DataFrame) -> List[StrategySignal]:
        """
        生成交易信号

        完全基于pandas实现的自适应策略信号生成
        """
        signals = []
        
        if len(data) < 50:
            return signals
        
        try:
            # 计算技术指标
            indicators = self._calculate_technical_indicators(data)
            
            # 生成基于多指标共振的信号
            for i in range(max(20, indicators['ma_20'].notna().sum()), len(data)):
                current_idx = data.index[i]
                current_price = data['close'].iloc[i]
                
                # 获取当前指标值
                current_ma = indicators['ma_20'].iloc[i]
                current_atr = indicators['atr_14'].iloc[i]
                current_rsi = indicators['rsi_14'].iloc[i]
                current_macd = indicators['macd'].iloc[i]
                
                if pd.isna([current_ma, current_atr, current_rsi]).any():
                    continue
                
                # 计算自适应止损止盈
                stop_loss_pct = self._calculate_adaptive_stop_loss(
                    current_atr, current_price)
                take_profit_pct = self._calculate_adaptive_take_profit(
                    current_rsi, current_macd)
                
                # 信号条件判断
                signal_conditions = self._evaluate_signal_conditions(
                    data.iloc[:i+1], indicators.iloc[:i+1], i)
                
                if signal_conditions['buy_signal']:
                    confidence = min(signal_conditions['confidence'] * 1.2, 0.95)
                    signals.append(StrategySignal(
                        timestamp=current_idx,
                        signal_type=SignalType.BUY,
                        price=current_price,
                        confidence=confidence,
                        strategy_name=self.name,
                        reason=f"多指标共振买入: {signal_conditions['reason']}",
                        stop_loss=current_price * (1 - stop_loss_pct),
                        take_profit=current_price * (1 + take_profit_pct)
                    ))
                    
                elif signal_conditions['sell_signal']:
                    confidence = min(signal_conditions['confidence'] * 1.2, 0.95)
                    signals.append(StrategySignal(
                        timestamp=current_idx,
                        signal_type=SignalType.SELL,
                        price=current_price,
                        confidence=confidence,
                        strategy_name=self.name,
                        reason=f"多指标共振卖出: {signal_conditions['reason']}",
                        stop_loss=current_price * (1 + stop_loss_pct),
                        take_profit=current_price * (1 - take_profit_pct)
                    ))
            
            self._calculation_history.append({
                'timestamp': datetime.now(),
                'signals_generated': len(signals),
                'data_points': len(data),
                'ta_lib_used': self._ta_lib_available
            })
            
            # 发布信号生成事件
            if signals:
                self._trigger_signal_generated_event(signals)
            
        except Exception as e:
            logger.error(f"pandas自适应策略信号生成失败: {e}")
            
        return signals

    def _calculate_technical_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        indicators = pd.DataFrame(index=data.index)
        
        try:
            if self._ta_lib_available:
                # 使用TA-Lib计算指标
                close = data['close'].values
                high = data['high'].values
                low = data['low'].values
                volume = data['volume'].values if 'volume' in data.columns else np.zeros(len(data))
                
                indicators['ma_20'] = pd.Series(talib.SMA(close, timeperiod=20), index=data.index)
                indicators['ma_50'] = pd.Series(talib.SMA(close, timeperiod=50), index=data.index)
                indicators['ema_12'] = pd.Series(talib.EMA(close, timeperiod=12), index=data.index)
                indicators['ema_26'] = pd.Series(talib.EMA(close, timeperiod=26), index=data.index)
                indicators['rsi_14'] = pd.Series(talib.RSI(close, timeperiod=14), index=data.index)
                indicators['atr_14'] = pd.Series(talib.ATR(high, low, close, timeperiod=14), index=data.index)
                indicators['macd'], indicators['macd_signal'], indicators['macd_hist'] = [
                    pd.Series(x, index=data.index) for x in talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
                ]
                indicators['boll_upper'] = pd.Series(talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)[0], index=data.index)
                indicators['boll_middle'] = pd.Series(talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)[1], index=data.index)
                indicators['boll_lower'] = pd.Series(talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)[2], index=data.index)
            else:
                # 使用内置pandas计算指标
                close = data['close']
                high = data['high']
                low = data['low']
                
                indicators['ma_20'] = close.rolling(window=20).mean()
                indicators['ma_50'] = close.rolling(window=50).mean()
                indicators['ema_12'] = close.ewm(span=12).mean()
                indicators['ema_26'] = close.ewm(span=26).mean()
                
                # RSI计算
                delta = close.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                indicators['rsi_14'] = 100 - (100 / (1 + rs))
                
                # ATR计算
                tr1 = high - low
                tr2 = (high - close.shift(1)).abs()
                tr3 = (low - close.shift(1)).abs()
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                indicators['atr_14'] = tr.rolling(window=14).mean()
                
                # MACD计算
                ema12 = close.ewm(span=12).mean()
                ema26 = close.ewm(span=26).mean()
                indicators['macd'] = ema12 - ema26
                indicators['macd_signal'] = indicators['macd'].ewm(span=9).mean()
                indicators['macd_hist'] = indicators['macd'] - indicators['macd_signal']
                
                # 布林带
                indicators['boll_middle'] = close.rolling(window=20).mean()
                boll_std = close.rolling(window=20).std()
                indicators['boll_upper'] = indicators['boll_middle'] + (boll_std * 2)
                indicators['boll_lower'] = indicators['boll_middle'] - (boll_std * 2)
                
        except Exception as e:
            logger.error(f"技术指标计算失败: {e}")
            # 返回基本指标
            indicators['ma_20'] = data['close'].rolling(window=20).mean()
            indicators['rsi_14'] = pd.Series(50, index=data.index)  # 默认RSI
            indicators['atr_14'] = pd.Series(data['close'] * 0.02, index=data.index)  # 默认ATR
            
        return indicators

    def _calculate_adaptive_stop_loss(self, atr: float, price: float) -> float:
        """计算自适应止损百分比"""
        try:
            atr_pct = atr / price if price > 0 else 0.02
            atr_multiplier = self.get_parameter("atr_multiplier", 2.0)
            volatility_factor = self.get_parameter("volatility_factor", 0.5)
            
            adaptive_stop = min(
                max(atr_pct * atr_multiplier, self.get_parameter("min_stop_loss", 0.01)),
                self.get_parameter("max_stop_loss", 0.1)
            )
            
            return adaptive_stop * (1 + volatility_factor)
            
        except Exception as e:
            logger.error(f"自适应止损计算失败: {e}")
            return self.get_parameter("fixed_stop_loss", 0.05)

    def _calculate_adaptive_take_profit(self, rsi: float, macd: float) -> float:
        """计算自适应止盈百分比"""
        try:
            base_take_profit = self.get_parameter("min_take_profit", 0.05)
            max_take_profit = self.get_parameter("max_take_profit", 0.2)
            
            # 基于RSI调整
            rsi_factor = 1.0
            if rsi < 30:  # 超卖情况，预期反弹更大
                rsi_factor = 1.5
            elif rsi > 70:  # 超买情况，预期上涨空间较小
                rsi_factor = 0.8
                
            # 基于MACD调整
            macd_factor = 1.0
            if macd > 0:  # MACD为正，上涨趋势
                macd_factor = 1.2
            else:  # MACD为负，下跌趋势
                macd_factor = 0.9
                
            adaptive_take_profit = base_take_profit * rsi_factor * macd_factor
            return min(adaptive_take_profit, max_take_profit)
            
        except Exception as e:
            logger.error(f"自适应止盈计算失败: {e}")
            return self.get_parameter("min_take_profit", 0.05)

    def _evaluate_signal_conditions(self, data: pd.DataFrame, indicators: pd.DataFrame, index: int) -> Dict[str, Any]:
        """评估信号条件"""
        try:
            if index < 20:
                return {'buy_signal': False, 'sell_signal': False, 'confidence': 0.0, 'reason': '数据不足'}
                
            current_ma = indicators['ma_20'].iloc[index]
            prev_ma = indicators['ma_20'].iloc[index-1] if index > 0 else current_ma
            current_price = data['close'].iloc[index]
            current_rsi = indicators['rsi_14'].iloc[index]
            current_macd = indicators['macd'].iloc[index]
            current_macd_signal = indicators['macd_signal'].iloc[index]
            current_boll_upper = indicators['boll_upper'].iloc[index]
            current_boll_lower = indicators['boll_lower'].iloc[index]
            
            # 移动平均线趋势信号
            ma_trend_bull = current_price > current_ma and current_ma > prev_ma
            ma_trend_bear = current_price < current_ma and current_ma < prev_ma
            
            # MACD信号
            macd_bull = current_macd > current_macd_signal and (index < 1 or indicators['macd'].iloc[index-1] <= indicators['macd_signal'].iloc[index-1])
            macd_bear = current_macd < current_macd_signal and (index < 1 or indicators['macd'].iloc[index-1] >= indicators['macd_signal'].iloc[index-1])
            
            # RSI信号
            rsi_oversold = current_rsi < 30
            rsi_overbought = current_rsi > 70
            
            # 布林带信号
            boll_breakout_upper = current_price > current_boll_upper
            boll_breakout_lower = current_price < current_boll_lower
            
            # 综合信号判断
            buy_conditions = []
            sell_conditions = []
            confidence_score = 0.0
            
            # 买入条件
            if ma_trend_bull:
                buy_conditions.append("MA趋势向上")
                confidence_score += 0.25
            if macd_bull:
                buy_conditions.append("MACD金叉")
                confidence_score += 0.25
            if rsi_oversold:
                buy_conditions.append("RSI超卖反弹")
                confidence_score += 0.2
            if boll_breakout_lower:
                buy_conditions.append("布林带反弹")
                confidence_score += 0.15
                
            # 卖出条件
            if ma_trend_bear:
                sell_conditions.append("MA趋势向下")
                confidence_score += 0.25
            if macd_bear:
                sell_conditions.append("MACD死叉")
                confidence_score += 0.25
            if rsi_overbought:
                sell_conditions.append("RSI超买回调")
                confidence_score += 0.2
            if boll_breakout_upper:
                sell_conditions.append("布林带突破")
                confidence_score += 0.15
            
            # 信号阈值
            signal_threshold = 0.6
            
            buy_signal = len(buy_conditions) >= 2 and confidence_score >= signal_threshold
            sell_signal = len(sell_conditions) >= 2 and confidence_score >= signal_threshold
            
            return {
                'buy_signal': buy_signal,
                'sell_signal': sell_signal,
                'confidence': confidence_score,
                'reason': '+'.join(buy_conditions) if buy_signal else '+'.join(sell_conditions) if sell_signal else '信号不足'
            }
            
        except Exception as e:
            logger.error(f"信号条件评估失败: {e}")
            return {'buy_signal': False, 'sell_signal': False, 'confidence': 0.0, 'reason': '计算错误'}

    def calculate_confidence(self, data: pd.DataFrame, signal_index: int) -> float:
        """计算信号置信度"""
        try:
            if len(data) < 20 or signal_index < 0 or signal_index >= len(data):
                return 0.5
                
            indicators = self._calculate_technical_indicators(data)
            conditions = self._evaluate_signal_conditions(data, indicators, signal_index)
            return conditions['confidence']
            
        except Exception as e:
            logger.error(f"置信度计算失败: {e}")
            return 0.5

    def get_required_columns(self) -> List[str]:
        return ['open', 'high', 'low', 'close', 'volume']

    def initialize_strategy(self, context, parameters=None):

        try:
            if parameters:
                for param_name, param_value in parameters.items():
                    if param_name in self.parameters:
                        self.set_parameter(param_name, param_value)
            
            logger.info(f"策略初始化成功: {self.name}")
            return True
        except Exception as e:
            logger.error(f"策略初始化失败: {e}")
            return False

    def get_strategy_info(self):
        """获取策略信息"""
        from core.strategy_extensions import StrategyInfo, ParameterDef
        
        # 调用父类方法获取 StrategyInfo 对象
        strategy_info = super().get_strategy_info()
        
        # 如果返回的是 StrategyInfo 对象，则创建新的对象并添加额外信息
        if isinstance(strategy_info, StrategyInfo):
            # 创建新的参数定义列表，添加额外的元数据
            parameter_defs = list(strategy_info.parameters)
            
            # 添加技术指标相关的参数
            parameter_defs.append(
                ParameterDef(
                    name="ta_lib_available",
                    type=bool,
                    default_value=self._ta_lib_available,
                    description="TA-Lib 是否可用",
                    required=False
                )
            )
            
            # 扩展标签列表
            extended_tags = list(strategy_info.tags) if strategy_info.tags else []
            extended_tags.extend(["technical_indicators", "adaptive_features"])
            
            # 创建新的 StrategyInfo 对象
            new_strategy_info = StrategyInfo(
                name=strategy_info.name,
                display_name=strategy_info.display_name,
                description=strategy_info.description,
                version=strategy_info.version,
                author=strategy_info.author,
                strategy_type=strategy_info.strategy_type,
                parameters=parameter_defs,
                supported_assets=strategy_info.supported_assets,
                time_frames=strategy_info.time_frames,
                risk_level=strategy_info.risk_level,
                tags=extended_tags,
                created_at=strategy_info.created_at,
                updated_at=strategy_info.updated_at
            )
            
            # 将额外信息存储在 metadata 字段中（通过 tags 传递）
            return new_strategy_info
        else:
            # 如果返回的是字典（向后兼容），则更新字典
            strategy_info.update({
                "ta_lib_available": self._ta_lib_available,
                "technical_indicators": [
                    "MA", "EMA", "RSI", "MACD", "ATR", "Bollinger Bands"
                ],
                "signal_components": {
                    "trend_analysis": "MA Trend",
                    "momentum_analysis": "MACD Cross",
                    "oscillator_analysis": "RSI Levels",
                    "volatility_analysis": "Bollinger Bands"
                },
                "adaptive_features": {
                    "stop_loss": "ATR-based adaptive",
                    "take_profit": "RSI+MACD adaptive",
                    "signal_confidence": "Multi-indicator scoring"
                }
            })
            return strategy_info


def create_adaptive_strategy():
    """创建自适应pandas策略（向后兼容函数）"""
    strategy = AdaptivePandasStrategy()
    return strategy


def create_adaptive_pandas_strategy(name: str = "AdaptivePandas", **kwargs) -> AdaptivePandasStrategy:
    """创建自适应pandas策略实例"""
    strategy = AdaptivePandasStrategy(name)

    # 设置参数
    for param_name, param_value in kwargs.items():
        if strategy.get_parameter(param_name) is not None:
            strategy.set_parameter(param_name, param_value)

    return strategy


# 已废弃：create_adaptive_hikyuu_strategy函数已被移除，请使用create_adaptive_pandas_strategy
