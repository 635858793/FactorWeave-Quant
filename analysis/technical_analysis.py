from loguru import logger
"""
Technical Analysis Module for Trading System
Provides various technical analysis tools and indicators
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime
import pandas as pd
try:
    import talib as ta
    TALIB_AVAILABLE = True
except ImportError:
    ta = None
    TALIB_AVAILABLE = False
from core.services.unified_data_manager import get_unified_data_manager

class TechnicalAnalyzer:
    """Technical analysis tools for trading system"""

    def __init__(self):
        self.cache = {}

    def analyze(self, kdata) -> Dict[str, Any]:
        """
        执行全面的技术分析

        Args:
            kdata: KData对象或DataFrame

        Returns:
            包含所有技术分析结果的字典
        """
        if isinstance(kdata, pd.DataFrame):
            df = kdata
        else:
            # 暂时保留转换逻辑，后续会被DataStandardizer替代
            data_manager = get_unified_data_manager()
            df = data_manager.kdata_to_df(kdata)

        trend_analysis = self.analyze_trend(df)
        momentum_analysis = self.analyze_momentum(df)
        support_resistance_analysis = self.analyze_support_resistance(df)

        return {
            **trend_analysis,
            **momentum_analysis,
            **support_resistance_analysis
        }

    def analyze_trend(self, data: pd.DataFrame) -> Dict[str, Any]:
        """分析趋势"""
        try:
            if 'close' not in data.columns:
                return {'trend_direction': 'NEUTRAL', 'trend_strength': 0.0}

            # 使用多个移动平均线判断趋势
            ma_short = data['close'].rolling(20).mean()
            ma_medium = data['close'].rolling(50).mean()
            ma_long = data['close'].rolling(200).mean()

            current_price = data['close'].iloc[-1]

            # 趋势方向判断
            if current_price > ma_short.iloc[-1] > ma_medium.iloc[-1] > ma_long.iloc[-1]:
                trend_direction = 'STRONG_UPTREND'
                trend_strength = 0.8
            elif current_price > ma_short.iloc[-1] > ma_medium.iloc[-1]:
                trend_direction = 'UPTREND'
                trend_strength = 0.6
            elif current_price < ma_short.iloc[-1] < ma_medium.iloc[-1] < ma_long.iloc[-1]:
                trend_direction = 'STRONG_DOWNTREND'
                trend_strength = -0.8
            elif current_price < ma_short.iloc[-1] < ma_medium.iloc[-1]:
                trend_direction = 'DOWNTREND'
                trend_strength = -0.6
            else:
                trend_direction = 'SIDEWAYS'
                trend_strength = 0.0

            # ADX趋势强度
            if 'adx' in data.columns:
                adx_value = data['adx'].iloc[-1]
                if adx_value > 25:
                    trend_strength *= (adx_value / 50)

            return {
                'trend_direction': trend_direction,
                'trend_strength': trend_strength,
                'ma_alignment': {
                    'ma20': ma_short.iloc[-1],
                    'ma50': ma_medium.iloc[-1],
                    'ma200': ma_long.iloc[-1]
                }
            }

        except Exception as e:
            # logger.error(f"趋势分析失败: {e}") # 假设没有logger
            return {'trend_direction': 'NEUTRAL', 'trend_strength': 0.0}

    def analyze_support_resistance(self, data: pd.DataFrame, window: int = 20) -> Dict[str, List[float]]:
        """寻找支撑阻力位"""
        try:
            if 'high' not in data.columns or 'low' not in data.columns:
                return {'support_levels': [], 'resistance_levels': []}

            support_levels = []
            resistance_levels = []

            highs = data['high'].rolling(window, center=False).max()
            lows = data['low'].rolling(window, center=False).min()

            window_slice = slice(window, len(data) - window) if len(data) > 2 * window else slice(0, 0)
            data_slice = data.iloc[window_slice]
            highs_slice = highs.iloc[window_slice]
            lows_slice = lows.iloc[window_slice]

            resistance_levels = data_slice.loc[data_slice['high'] == highs_slice, 'high'].tolist()
            support_levels = data_slice.loc[data_slice['low'] == lows_slice, 'low'].tolist()

            support_levels = sorted(list(set(support_levels)))[-5:]
            resistance_levels = sorted(list(set(resistance_levels)), reverse=True)[:5]

            return {
                'support_levels': support_levels,
                'resistance_levels': resistance_levels
            }

        except Exception as e:
            # logger.error(f"支撑阻力分析失败: {e}")
            return {'support_levels': [], 'resistance_levels': []}

    def analyze_momentum(self, kdata) -> Dict:
        """Analyze price momentum using various indicators
        Args:
            kdata: KData对象或DataFrame
        Returns:
            Dict containing momentum analysis results
        """
        try:
            if isinstance(kdata, pd.DataFrame):
                if 'close' not in kdata.columns:
                    return {'rsi': 0, 'macd': 0, 'macd_signal': 0, 'macd_histogram': 0, 'roc': 0.0, 'momentum_score': 0.0}
                closes = kdata['close'].values
                rsi = ta.RSI(closes, timeperiod=14)
                macd, macd_signal, macd_hist = ta.MACD(closes, fastperiod=12, slowperiod=26, signalperiod=9)
            else:
                closes = np.array([float(k.close) for k in kdata])
                rsi = ta.RSI(closes, timeperiod=14)
                macd, macd_signal, macd_hist = ta.MACD(closes, fastperiod=12, slowperiod=26, signalperiod=9)
            
            roc = np.diff(closes) / closes[:-1] * 100
            roc_value = float(roc[-1]) if len(roc) > 0 else 0.0
            return {
                'rsi': rsi[-1] if len(rsi) > 0 else 0,
                'macd': macd[-1] if len(macd) > 0 else 0,
                'macd_signal': macd_signal[-1] if len(macd_signal) > 0 else 0,
                'macd_histogram': macd_hist[-1] if len(macd_hist) > 0 else 0,
                'roc': roc_value,
                'momentum_score': self._calculate_momentum_score(rsi, macd, roc, closes)
            }
        except Exception as e:
            raise Exception(f"Momentum analysis failed: {str(e)}")

    def _calculate_momentum_score(self, rsi, macd, roc, closes) -> float:
        """Calculate overall momentum score

        Args:
            rsi: RSI indicator values
            macd: MACD indicator values
            roc: Rate of change values
            closes: Close prices

        Returns:
            Float value representing momentum score
        """
        try:
            # Handle NaN values and get last valid values
            rsi_val = rsi[-1] if len(rsi) > 0 and not np.isnan(rsi[-1]) else 50
            macd_val = macd[-1] if len(macd) > 0 and not np.isnan(macd[-1]) else 0
            
            # Normalize indicators
            rsi_norm = (rsi_val - 50) / 50  # Center around 0
            
            # Calculate MACD normalization using recent values
            macd_recent = macd[-10:] if len(macd) >= 10 else macd
            macd_recent = macd_recent[~np.isnan(macd_recent)]  # Remove NaN values
            if len(macd_recent) > 0:
                macd_norm = (macd_val - np.mean(macd_recent)) / (np.std(macd_recent) + 1e-8)
            else:
                macd_norm = 0
            
            # Normalize ROC
            if len(roc) > 0:
                roc_recent = roc[-10:] if len(roc) >= 10 else roc
                roc_recent = roc_recent[~np.isnan(roc_recent)]  # Remove NaN values
                if len(roc_recent) > 0:
                    roc_norm = (roc[-1] - np.mean(roc_recent)) / (np.std(roc_recent) + 1e-8)
                else:
                    roc_norm = 0
            else:
                roc_norm = 0

            # Calculate weighted score
            score = (0.4 * rsi_norm +
                     0.4 * macd_norm +
                     0.2 * roc_norm)

            return np.clip(score, -1, 1)  # Limit to [-1, 1] range

        except Exception as e:
            raise Exception(f"Momentum score calculation failed: {str(e)}")
