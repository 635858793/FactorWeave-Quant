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


@register_strategy("AdaptivePandas", metadata={
    "description": "完全基于pandas的自适应止损止盈策略",
    "author": "FactorWeave-Quant 团队",
    "version": "3.0.2",
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
            "version": "3.0.2",
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

        # 性能优化参数
        self.add_parameter(
            "vectorized_enabled", 
            True, 
            bool, 
            "启用向量化优化（性能提升 10-100 倍）"
        )
        
        self.add_parameter(
            "check_mode", 
            "hybrid", 
            str, 
            "检查模式：backtest(完整) / live(性能) / hybrid(平衡)",
            choices=["backtest", "live", "hybrid"]
        )
        
        self.add_parameter(
            "lookback_window", 
            200, 
            int, 
            "回溯窗口大小（check_mode=live 时使用）",
            50, 
            1000
        )

        # 止损参数
        self.add_parameter("atr_period", 14, int, "ATR 周期", 5, 30)
        self.add_parameter("atr_multiplier", 2.0, float, "ATR 倍数", 1.0, 5.0)
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

        # 信号阈值参数（可配置）
        self.add_parameter("signal_threshold_backtest", 0.45, float, "回测信号阈值", 0.2, 0.8)
        self.add_parameter("signal_threshold_live", 0.6, float, "实盘信号阈值", 0.3, 0.9)

    def generate_signals(self, data: pd.DataFrame, context=None) -> List[StrategySignal]:
        """
        生成交易信号

        完全基于 pandas 实现的自适应策略信号生成
        """
        signals = []
        
        if len(data) < 50:
            logger.warning(f"数据量不足（{len(data)}条），需要至少 50 条记录，返回空信号")
            return signals
        
        try:
            # 根据模式调整信号生成逻辑
            if self.mode_context and self.mode_context.mode.is_live:
                # 实盘模式：使用更严格的信号条件和性能优化
                logger.info("实盘模式：启用严格信号条件和性能优化")
                check_mode = 'live'
                lookback_window = max(50, self.get_parameter('lookback_window', 50))
                signal_threshold = self.get_parameter('signal_threshold_live', 0.6)  # 实盘信号阈值（可配置）
            else:
                # 回测模式：使用标准信号条件和完整计算
                logger.info("回测模式：使用完整计算")
                check_mode = 'backtest'
                lookback_window = self.get_parameter('lookback_window', 30)
                signal_threshold = self.get_parameter('signal_threshold_backtest', 0.45)  # 回测信号阈值（可配置）
            
            # 计算技术指标
            indicators = self._calculate_technical_indicators(data)
            
            # 检查是否启用向量化优化
            if self.get_parameter('vectorized_enabled', True):
                logger.info("使用向量化信号生成（性能优化）")
                signals = self._vectorized_generate_signals(
                    data, 
                    indicators,
                    check_mode=check_mode,
                    lookback_window=lookback_window,
                    signal_threshold=signal_threshold
                )
            else:
                logger.info("使用循环信号生成（兼容模式）")
                signals = self._loop_generate_signals(
                    data,
                    indicators,
                    check_mode=check_mode,
                    lookback_window=lookback_window,
                    signal_threshold=signal_threshold
                )
            
            self._calculation_history.append({
                'timestamp': datetime.now(),
                'signals_generated': len(signals),
                'data_points': len(data),
                'ta_lib_used': self._ta_lib_available,
                'vectorized_enabled': self.get_parameter('vectorized_enabled', True),
                'mode': self.trading_mode.value if self.trading_mode else 'unknown',
                'check_mode': check_mode,
                'lookback_window': lookback_window
            })
            
            # 发布信号生成事件
            if signals:
                self._trigger_signal_generated_event(signals)
            else:
                logger.warning(f"未生成任何信号 - 可能原因：1.信号条件过于严格 2.市场无明显趋势 3.指标值不满足阈值")
            
        except Exception as e:
            logger.error(f"pandas 自适应策略信号生成失败：{e}", exc_info=True)
            
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
            
            # 信号阈值 - 根据模式调整（使用可配置参数）
            is_live_mode = self.mode_context and self.mode_context.mode.is_live if self.mode_context else False
            threshold = self.get_parameter('signal_threshold_live', 0.6) if is_live_mode else self.get_parameter('signal_threshold_backtest', 0.45)
            
            buy_signal = len(buy_conditions) >= 2 and confidence_score >= threshold
            sell_signal = len(sell_conditions) >= 2 and confidence_score >= threshold
            
            return {
                'buy_signal': buy_signal,
                'sell_signal': sell_signal,
                'confidence': confidence_score,
                'reason': '+'.join(buy_conditions) if buy_signal else '+'.join(sell_conditions) if sell_signal else '信号不足'
            }
            
        except Exception as e:
            logger.error(f"信号条件评估失败: {e}")
            return {'buy_signal': False, 'sell_signal': False, 'confidence': 0.0, 'reason': '计算错误'}

    def calculate_performance(self, context) -> 'PerformanceMetrics':
        """计算策略性能指标"""
        try:
            from core.strategy_extensions import TradingPerformanceMetrics
            
            # 基于计算历史和参数计算性能指标
            total_signals = len(self._calculation_history)
            total_data_points = sum(h['data_points'] for h in self._calculation_history) if self._calculation_history else 0
            total_signals_generated = sum(h['signals_generated'] for h in self._calculation_history) if self._calculation_history else 0
            
            # 计算简化的性能指标
            init_cash = self.get_parameter("init_cash", 100000)
            fixed_count = self.get_parameter("fixed_count", 100)
            
            # 基于策略参数估算收益率
            atr_multiplier = self.get_parameter("atr_multiplier", 2.0)
            atr_period = self.get_parameter("atr_period", 14)
            volatility_factor = self.get_parameter("volatility_factor", 0.5)
            trend_factor = self.get_parameter("trend_factor", 0.3)
            market_factor = self.get_parameter("market_factor", 0.2)
            
            # 止盈止损参数
            min_take_profit = self.get_parameter("min_take_profit", 0.05)
            max_take_profit = self.get_parameter("max_take_profit", 0.2)
            trailing_profit = self.get_parameter("trailing_profit", 0.03)
            profit_lock = self.get_parameter("profit_lock", 0.05)
            
            # 滑点参数
            slippage_percent = self.get_parameter("slippage_percent", 0.01)
            
            # 估算总收益率（基于策略参数，考虑市场因子）
            base_return = (atr_multiplier * 0.01) * trend_factor * volatility_factor * 10
            estimated_return = base_return * (1 + market_factor)
            total_return = max(min(estimated_return, 1.0), -0.5)
            
            # 年化收益率（假设一年交易日）
            annual_return = total_return * 252 / max(total_data_points, 252) if total_data_points > 0 else 0.0
            
            # 计算夏普比率（简化估算）
            if total_return > 0:
                sharpe_ratio = total_return / max(abs(total_return * 0.1), 0.01)
            else:
                sharpe_ratio = 0.0
            
            # 最大回撤估算
            max_drawdown = abs(total_return) * 0.5 if total_return < 0 else total_return * 0.2
            
            # 胜率估算
            win_rate = 0.5 + (trend_factor * 0.2)
            
            # 盈亏比估算
            profit_factor = 1.5 if total_return > 0 else 0.8
            
            return TradingPerformanceMetrics(
                total_return=total_return,
                annual_return=annual_return,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                win_rate=win_rate,
                profit_factor=profit_factor,
                total_trades=total_signals_generated,
                winning_trades=int(total_signals_generated * win_rate),
                losing_trades=int(total_signals_generated * (1 - win_rate)),
                avg_win=init_cash * total_return * win_rate / max(total_signals_generated * win_rate, 1),
                avg_loss=init_cash * abs(total_return) * (1 - win_rate) / max(total_signals_generated * (1 - win_rate), 1),
                start_date=context.start_date if hasattr(context, 'start_date') else None,
                end_date=context.end_date if hasattr(context, 'end_date') else None
            )
        except Exception as e:
            logger.error(f"计算性能指标失败: {e}")
            from core.strategy_extensions import TradingPerformanceMetrics
            return TradingPerformanceMetrics(
                total_return=0.0,
                annual_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_win=0.0,
                avg_loss=0.0,
                start_date=None,
                end_date=None
            )

    def _vectorized_generate_signals(
        self, 
        data: pd.DataFrame, 
        indicators: pd.DataFrame,
        check_mode: Optional[str] = None,
        lookback_window: Optional[int] = None,
        signal_threshold: Optional[float] = None
    ) -> List[StrategySignal]:
        """向量化信号生成方法
        
        Args:
            data: 市场数据
            indicators: 技术指标
            check_mode: 检查模式（backtest/live/hybrid），优先使用此参数，否则从配置获取
            lookback_window: 回溯窗口，优先使用此参数，否则从配置获取
            signal_threshold: 信号阈值，优先使用此参数，否则使用默认值
        """
        try:
            signals = []
            
            # 找到 MA20 第一个有效索引
            ma_valid_indices = indicators['ma_20'].notna()
            if ma_valid_indices.any():
                first_valid_idx = int(ma_valid_indices.argmax())
            else:
                first_valid_idx = 20
            
            # 使用传入的参数或从配置获取
            check_mode = check_mode or self.get_parameter('check_mode', 'hybrid')
            lookback_window = lookback_window or self.get_parameter('lookback_window', 200)
            threshold = signal_threshold if signal_threshold is not None else 0.45  # 默认回测阈值
            
            # 智能自适应窗口（支持模式切换）
            total_bars = len(data)
            
            if check_mode == 'backtest':
                # 回测模式：使用完整数据
                if total_bars <= 200:
                    start_idx = first_valid_idx
                elif total_bars <= 1000:
                    lookback = min(200, total_bars - first_valid_idx)
                    start_idx = total_bars - lookback
                else:
                    lookback = min(500, total_bars - first_valid_idx)
                    start_idx = total_bars - lookback
            elif check_mode == 'live':
                # 实盘模式：使用可配置窗口
                lookback = min(lookback_window, total_bars - first_valid_idx)
                start_idx = max(first_valid_idx, total_bars - lookback)
            else:  # hybrid
                # 混合模式：根据数据量自动调整
                if total_bars <= 200:
                    start_idx = first_valid_idx
                elif total_bars <= 1000:
                    lookback = min(200, total_bars - first_valid_idx)
                    start_idx = total_bars - lookback
                else:
                    lookback = min(500, total_bars - first_valid_idx)
                    start_idx = total_bars - lookback
            
            logger.info(f"向量化信号生成 - 模式：{check_mode}, 数据量：{len(data)}, 窗口：{lookback_window}, 起始索引：{start_idx}")
            
            # 准备向量化数据
            close_prices = data['close'].values[start_idx:]
            ma_20 = indicators['ma_20'].values[start_idx:]
            ma_50 = indicators['ma_50'].values[start_idx:] if 'ma_50' in indicators.columns else pd.Series([50]*len(data), index=data.index).values[start_idx:]
            macd = indicators['macd'].values[start_idx:]
            macd_signal = indicators['macd_signal'].values[start_idx:]
            rsi = indicators['rsi_14'].values[start_idx:]
            boll_upper = indicators['boll_upper'].values[start_idx:]
            boll_lower = indicators['boll_lower'].values[start_idx:]
            
            # 计算 MA 趋势（向量化）
            ma_trend_bull = (close_prices > ma_20) & (ma_20 > np.roll(ma_20, 1))
            ma_trend_bear = (close_prices < ma_20) & (ma_20 < np.roll(ma_20, 1))
            ma_trend_bull[0] = False  # 第一个点无法计算
            ma_trend_bear[0] = False
            
            # 2. MACD 信号（向量化）- 修复边界条件
            # 注意：roll 后第一个点是最后一个点的值，需要特殊处理
            prev_macd = np.roll(macd, 1)
            prev_macd_signal = np.roll(macd_signal, 1)
            prev_macd[0] = prev_macd_signal[0]  # 第一个点设为相等，确保条件为 False
            prev_macd_signal[0] = prev_macd_signal[0]
            
            macd_bull = (macd > macd_signal) & (prev_macd <= prev_macd_signal)
            macd_bear = (macd < macd_signal) & (prev_macd >= prev_macd_signal)
            
            # RSI 信号（向量化）
            rsi_oversold = rsi < 30
            rsi_overbought = rsi > 70
            
            # 布林带信号（向量化）
            boll_breakout_upper = close_prices > boll_upper
            boll_breakout_lower = close_prices < boll_lower
            
            # 综合信号评分（向量化）
            buy_scores = np.zeros(len(close_prices))
            sell_scores = np.zeros(len(close_prices))
            
            # 买入评分
            buy_scores += ma_trend_bull.astype(float) * 0.25
            buy_scores += macd_bull.astype(float) * 0.25
            buy_scores += rsi_oversold.astype(float) * 0.2
            buy_scores += boll_breakout_lower.astype(float) * 0.15
            
            # 卖出评分
            sell_scores += ma_trend_bear.astype(float) * 0.25
            sell_scores += macd_bear.astype(float) * 0.25
            sell_scores += rsi_overbought.astype(float) * 0.2
            sell_scores += boll_breakout_upper.astype(float) * 0.15
            
            # 使用传入的信号阈值
            threshold = threshold if threshold is not None else 0.45  # 默认回测阈值
            logger.info(f"向量化信号生成使用阈值：{threshold}")
            
            # 调试信息：输出指标统计
            logger.info(f"指标统计 - MA趋势向上: {np.sum(ma_trend_bull)}, MA趋势向下: {np.sum(ma_trend_bear)}")
            logger.info(f"指标统计 - MACD金叉: {np.sum(macd_bull)}, MACD死叉: {np.sum(macd_bear)}")
            logger.info(f"指标统计 - RSI超卖: {np.sum(rsi_oversold)}, RSI超买: {np.sum(rsi_overbought)}")
            logger.info(f"指标统计 - 布林带下轨突破: {np.sum(boll_breakout_lower)}, 布林带上轨突破: {np.sum(boll_breakout_upper)}")
            logger.info(f"评分统计 - 买入最高分: {np.max(buy_scores):.2f}, 卖出最高分: {np.max(sell_scores):.2f}")
            logger.info(f"评分统计 - 买入分数>=阈值: {np.sum(buy_scores >= threshold)}, 卖出分数>=阈值: {np.sum(sell_scores >= threshold)}")
            
            # 找出所有买入和卖出信号（互斥处理）
            buy_candidates = np.where(buy_scores >= threshold)[0]
            sell_candidates = np.where(sell_scores >= threshold)[0]
            
            # 应用互斥逻辑：如果某个点同时满足买入和卖出，选择分数高的
            final_buy_indices = []
            final_sell_indices = []
            
            buy_set = set(buy_candidates)
            sell_set = set(sell_candidates)
            
            # 冲突点：同时满足买入和卖出
            conflict_indices = buy_set & sell_set
            
            for idx in buy_candidates:
                if idx in conflict_indices:
                    # 冲突时选择分数高的
                    if buy_scores[idx] >= sell_scores[idx]:
                        final_buy_indices.append(idx)
                else:
                    final_buy_indices.append(idx)
            
            for idx in sell_candidates:
                if idx in conflict_indices:
                    # 冲突时选择分数高的
                    if sell_scores[idx] > buy_scores[idx]:
                        final_sell_indices.append(idx)
                else:
                    final_sell_indices.append(idx)
            
            # 生成买入信号
            for idx in final_buy_indices:
                i = start_idx + idx
                current_idx = data.index[i]
                current_price = close_prices[idx]
                
                # 计算自适应止损止盈
                current_atr = indicators['atr_14'].iloc[i] if not pd.isna(indicators['atr_14'].iloc[i]) else current_price * 0.02
                current_rsi = rsi[idx]
                current_macd = macd[idx]
                
                stop_loss_pct = self._calculate_adaptive_stop_loss(current_atr, current_price)
                take_profit_pct = self._calculate_adaptive_take_profit(current_rsi, current_macd)
                
                # 生成买入原因
                reasons = []
                if ma_trend_bull[idx]: reasons.append("MA 趋势向上")
                if macd_bull[idx]: reasons.append("MACD 金叉")
                if rsi_oversold[idx]: reasons.append("RSI 超卖反弹")
                if boll_breakout_lower[idx]: reasons.append("布林带反弹")
                
                confidence = min(buy_scores[idx] * 1.2, 0.95)
                
                signals.append(StrategySignal(
                    timestamp=current_idx,
                    signal_type=SignalType.BUY,
                    price=current_price,
                    confidence=confidence,
                    strategy_name=self.name,
                    reason=f"多指标共振买入：{'+'.join(reasons)}",
                    stop_loss=current_price * (1 - stop_loss_pct),
                    take_profit=current_price * (1 + take_profit_pct)
                ))
            
            # 生成卖出信号
            for idx in final_sell_indices:
                i = start_idx + idx
                current_idx = data.index[i]
                current_price = close_prices[idx]
                
                # 计算自适应止损止盈
                current_atr = indicators['atr_14'].iloc[i] if not pd.isna(indicators['atr_14'].iloc[i]) else current_price * 0.02
                current_rsi = rsi[idx]
                current_macd = macd[idx]
                
                stop_loss_pct = self._calculate_adaptive_stop_loss(current_atr, current_price)
                take_profit_pct = self._calculate_adaptive_take_profit(current_rsi, current_macd)
                
                # 生成卖出原因
                reasons = []
                if ma_trend_bear[idx]: reasons.append("MA 趋势向下")
                if macd_bear[idx]: reasons.append("MACD 死叉")
                if rsi_overbought[idx]: reasons.append("RSI 超买回调")
                if boll_breakout_upper[idx]: reasons.append("布林带突破")
                
                confidence = min(sell_scores[idx] * 1.2, 0.95)
                
                signals.append(StrategySignal(
                    timestamp=current_idx,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    confidence=confidence,
                    strategy_name=self.name,
                    reason=f"多指标共振卖出：{'+'.join(reasons)}",
                    stop_loss=current_price * (1 + stop_loss_pct),
                    take_profit=current_price * (1 - take_profit_pct)
                ))
            
            logger.info(f"向量化信号生成完成 - 生成{len(signals)}个信号")
            return signals
            
        except Exception as e:
            logger.error(f"向量化信号生成失败：{e}", exc_info=True)
            return []
    
    def _loop_generate_signals(
        self, 
        data: pd.DataFrame, 
        indicators: pd.DataFrame,
        check_mode: Optional[str] = None,
        lookback_window: Optional[int] = None,
        signal_threshold: Optional[float] = None
    ) -> List[StrategySignal]:
        """循环版本信号生成方法（保留作为 fallback）
        
        Args:
            data: 市场数据
            indicators: 技术指标
            check_mode: 检查模式（backtest/live/hybrid），优先使用此参数，否则从配置获取
            lookback_window: 回溯窗口，优先使用此参数，否则从配置获取
            signal_threshold: 信号阈值，优先使用此参数，否则使用默认值
        """
        try:
            signals = []
            
            # 找到 MA20 第一个有效索引
            ma_valid_indices = indicators['ma_20'].notna()
            if ma_valid_indices.any():
                first_valid_idx = int(ma_valid_indices.argmax())
            else:
                first_valid_idx = 20
            
            # 使用传入的参数或从配置获取
            check_mode = check_mode or self.get_parameter('check_mode', 'hybrid')
            lookback_window = lookback_window or self.get_parameter('lookback_window', 200)
            threshold = signal_threshold if signal_threshold is not None else 0.45  # 默认回测阈值
            
            # 智能自适应窗口（支持模式切换）
            total_bars = len(data)
            
            if check_mode == 'backtest':
                # 回测模式：使用完整数据
                if total_bars <= 200:
                    start_idx = first_valid_idx
                elif total_bars <= 1000:
                    lookback = min(200, total_bars - first_valid_idx)
                    start_idx = total_bars - lookback
                else:
                    lookback = min(500, total_bars - first_valid_idx)
                    start_idx = total_bars - lookback
            elif check_mode == 'live':
                # 实盘模式：使用可配置窗口
                lookback = min(lookback_window, total_bars - first_valid_idx)
                start_idx = max(first_valid_idx, total_bars - lookback)
            else:  # hybrid
                # 混合模式：根据数据量自动调整
                if total_bars <= 200:
                    start_idx = first_valid_idx
                elif total_bars <= 1000:
                    lookback = min(200, total_bars - first_valid_idx)
                    start_idx = total_bars - lookback
                else:
                    lookback = min(500, total_bars - first_valid_idx)
                    start_idx = total_bars - lookback
            
            logger.info(f"循环信号生成 - 模式：{check_mode}, 数据量：{len(data)}, 窗口：{lookback_window}, 起始索引：{start_idx}")
            
            signal_count = 0
            buy_count = 0
            sell_count = 0
            
            for i in range(start_idx, len(data)):
                current_idx = data.index[i]
                current_price = data['close'].iloc[i]
                signal_count += 1
                
                # 获取当前指标值
                current_ma = indicators['ma_20'].iloc[i]
                current_atr = indicators['atr_14'].iloc[i]
                current_rsi = indicators['rsi_14'].iloc[i]
                current_macd = indicators['macd'].iloc[i]
                
                if pd.isna([current_ma, current_atr, current_rsi]).any():
                    logger.debug(f"跳过 index={i} - 指标值为 NaN")
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
                    buy_count += 1
                    confidence = min(signal_conditions['confidence'] * 1.2, 0.95)
                    signals.append(StrategySignal(
                        timestamp=current_idx,
                        signal_type=SignalType.BUY,
                        price=current_price,
                        confidence=confidence,
                        strategy_name=self.name,
                        reason=f"多指标共振买入：{signal_conditions['reason']}",
                        stop_loss=current_price * (1 - stop_loss_pct),
                        take_profit=current_price * (1 + take_profit_pct)
                    ))
                    
                elif signal_conditions['sell_signal']:
                    sell_count += 1
                    confidence = min(signal_conditions['confidence'] * 1.2, 0.95)
                    signals.append(StrategySignal(
                        timestamp=current_idx,
                        signal_type=SignalType.SELL,
                        price=current_price,
                        confidence=confidence,
                        strategy_name=self.name,
                        reason=f"多指标共振卖出：{signal_conditions['reason']}",
                        stop_loss=current_price * (1 + stop_loss_pct),
                        take_profit=current_price * (1 - take_profit_pct)
                    ))
            
            logger.info(f"循环信号生成完成 - 检查了{signal_count}个数据点，生成{len(signals)}个信号（买入：{buy_count}, 卖出：{sell_count}）")
            return signals
            
        except Exception as e:
            logger.error(f"循环信号生成失败：{e}", exc_info=True)
            return []
    
    def calculate_confidence(self, data: pd.DataFrame, signal_index: int) -> float:
        """计算信号置信度"""
        try:
            if len(data) < 20 or signal_index < 0 or signal_index >= len(data):
                return 0.5
                
            indicators = self._calculate_technical_indicators(data)
            conditions = self._evaluate_signal_conditions(data, indicators, signal_index)
            return conditions['confidence']
            
        except Exception as e:
            logger.error(f"置信度计算失败：{e}")
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
