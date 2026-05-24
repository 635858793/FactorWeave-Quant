"""
Wave Analysis Module for Trading System
Provides Elliott Wave and Gann analysis tools
"""

import importlib
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import pandas as pd
from core.services.unified_data_manager import get_unified_data_manager
from scipy.signal import argrelextrema
try:
    from talib import HT_TRENDLINE, MA
    TALIB_AVAILABLE = True
except ImportError:
    HT_TRENDLINE = None
    MA = None
    TALIB_AVAILABLE = False
    import warnings
    warnings.warn("talib not available, wave analysis will use numpy fallback")
try:
    talib = importlib.import_module('talib')
except ImportError:
    talib = None

class WaveAnalyzer:
    """Wave analysis tools for trading system"""

    def __init__(self):
        self.cache = {}

    def analyze_elliott_waves(self, kdata, period: int = 20,
                              sensitivity: float = 0.01) -> Dict:
        """Analyze Elliott Wave patterns (双向检测：上升5浪 + 下跌5浪)

        Args:
            kdata: KData对象或DataFrame
            period: Period for analysis
            sensitivity: Sensitivity threshold

        Returns:
            Dict containing Elliott Wave analysis results
            Keys: trend, peaks, troughs, waves, bullish_waves, bearish_waves, fibonacci_levels
        """
        try:
            if isinstance(kdata, pd.DataFrame):
                closes = kdata['close'].values
                highs = kdata['high'].values
                lows = kdata['low'].values
            else:
                closes = np.array([float(k.close) for k in kdata])
                highs = np.array([float(k.high) for k in kdata])
                lows = np.array([float(k.low) for k in kdata])

            trend = talib.HT_TRENDLINE(closes)

            # 波峰使用最高价，波谷使用最低价
            peak_indices = argrelextrema(highs, np.greater, order=period)[0]
            trough_indices = argrelextrema(lows, np.less, order=period)[0]

            peaks_raw = [(int(i), float(highs[i]), 'peak') for i in peak_indices]
            troughs_raw = [(int(i), float(lows[i]), 'trough') for i in trough_indices]

            # 向后兼容的peaks/troughs格式
            peaks = [(p[0], p[1]) for p in peaks_raw]
            troughs = [(t[0], t[1]) for t in troughs_raw]

            # 合并极值点并按时间排序，用于5浪结构检测
            all_extrema = sorted(peaks_raw + troughs_raw, key=lambda x: x[0])

            # 双向波浪检测
            bullish_waves = self._detect_bullish_waves(all_extrema)
            bearish_waves = self._detect_bearish_waves(all_extrema)

            # 斐波那契回撤水平（基于整个价格区间）
            fib_levels = self._calc_fibonacci_levels(highs, lows)

            # 合并所有波浪（保持向后兼容）
            all_waves = bullish_waves + bearish_waves

            return {
                'trend': trend,
                'peaks': peaks,
                'troughs': troughs,
                'waves': all_waves,
                'bullish_waves': bullish_waves,
                'bearish_waves': bearish_waves,
                'fibonacci_levels': fib_levels
            }

        except Exception as e:
            raise Exception(f"Elliott Wave analysis failed: {str(e)}")

    def _detect_bullish_waves(self, extrema: List[Tuple[int, float, str]]) -> List[Dict]:
        """检测上升5浪驱动浪

        上升5浪结构: 谷(浪1起点) → 峰(浪1终点) → 谷(浪2终点) → 峰(浪3终点) → 谷(浪4终点) → 峰(浪5终点)

        Args:
            extrema: 按时间排序的极值点列表 [(index, price, type), ...]

        Returns:
            检测到的上升5浪列表
        """
        waves = []
        for i in range(len(extrema) - 5):
            seq = extrema[i:i + 6]
            if not all(
                seq[j][2] == tp
                for j, tp in enumerate(['trough', 'peak', 'trough', 'peak', 'trough', 'peak'])
            ):
                continue
            points = [(p[0], p[1]) for p in seq]
            if self._validate_wave_rules(points, 'bullish'):
                wave_amplitudes = [
                    points[1][1] - points[0][1],
                    points[1][1] - points[2][1],
                    points[3][1] - points[2][1],
                    points[3][1] - points[4][1],
                    points[5][1] - points[4][1],
                ]
                fib_info = self._calc_wave_fibonacci(points)
                waves.append({
                    'start_idx': points[0][0],
                    'end_idx': points[5][0],
                    'trend': 'bullish',
                    'waves': wave_amplitudes,
                    'points': points,
                    'fibonacci': fib_info
                })
        return waves

    def _detect_bearish_waves(self, extrema: List[Tuple[int, float, str]]) -> List[Dict]:
        """检测下跌5浪驱动浪

        下跌5浪结构: 峰(浪1起点) → 谷(浪1终点) → 峰(浪2终点) → 谷(浪3终点) → 峰(浪4终点) → 谷(浪5终点)

        Args:
            extrema: 按时间排序的极值点列表 [(index, price, type), ...]

        Returns:
            检测到的下跌5浪列表
        """
        waves = []
        for i in range(len(extrema) - 5):
            seq = extrema[i:i + 6]
            if not all(
                seq[j][2] == tp
                for j, tp in enumerate(['peak', 'trough', 'peak', 'trough', 'peak', 'trough'])
            ):
                continue
            points = [(p[0], p[1]) for p in seq]
            if self._validate_wave_rules(points, 'bearish'):
                wave_amplitudes = [
                    points[0][1] - points[1][1],
                    points[2][1] - points[1][1],
                    points[2][1] - points[3][1],
                    points[4][1] - points[3][1],
                    points[4][1] - points[5][1],
                ]
                fib_info = self._calc_wave_fibonacci(points)
                waves.append({
                    'start_idx': points[0][0],
                    'end_idx': points[5][0],
                    'trend': 'bearish',
                    'waves': wave_amplitudes,
                    'points': points,
                    'fibonacci': fib_info
                })
        return waves

    def _validate_wave_rules(self, points: List[Tuple[int, float]], trend: str = 'bullish') -> bool:
        """验证艾略特波浪理论核心三规则

        规则1: 浪2回撤 < 100%浪1（浪2不能完全回吐浪1）
        规则2: 浪4不进入浪1价格区域
        规则3: 浪3不是最短的驱动浪（浪3 >= min(浪1, 浪5)）

        Args:
            points: 6个极值点 [(index, price), ...]
            trend: 'bullish'上升趋势 或 'bearish'下跌趋势

        Returns:
            是否通过规则验证
        """
        if len(points) != 6:
            return False

        if trend == 'bullish':
            wave1 = points[1][1] - points[0][1]
            wave2_retrace = points[1][1] - points[2][1]
            wave3 = points[3][1] - points[2][1]
            wave4_retrace = points[3][1] - points[4][1]
            wave5 = points[5][1] - points[4][1]

            if wave1 <= 0 or wave3 <= 0 or wave5 <= 0:
                return False

            if wave2_retrace >= wave1:
                return False

            if points[4][1] <= points[1][1]:
                return False

            if wave3 < min(wave1, wave5):
                return False

            return True
        else:
            wave1 = points[0][1] - points[1][1]
            wave2_retrace = points[2][1] - points[1][1]
            wave3 = points[2][1] - points[3][1]
            wave4_retrace = points[4][1] - points[3][1]
            wave5 = points[4][1] - points[5][1]

            if wave1 <= 0 or wave3 <= 0 or wave5 <= 0:
                return False

            if wave2_retrace >= wave1:
                return False

            if points[4][1] >= points[1][1]:
                return False

            if wave3 < min(wave1, wave5):
                return False

            return True

    def _calc_wave_fibonacci(self, points: List[Tuple[int, float]]) -> Dict:
        """计算单个5浪结构的斐波那契回撤与扩展位

        回撤位(.382/.5/.618): 从浪1终点向浪1起点方向计算
        扩展位(1.0/1.382/1.618): 从浪1起点沿浪1方向计算

        Args:
            points: 6个极值点 [(index, price), ...]

        Returns:
            {'retracement': {ratio: price}, 'extension': {ratio: price}, 'wave1_range': float}
        """
        retrace_ratios = [0.382, 0.5, 0.618]
        extend_ratios = [1.0, 1.382, 1.618]
        wave1_range = abs(points[1][1] - points[0][1])

        if points[0][1] < points[1][1]:
            retracement = {
                f'{r:.1%}': round(points[1][1] - wave1_range * r, 2)
                for r in retrace_ratios
            }
            extension = {
                f'{r:.1%}': round(points[0][1] + wave1_range * r, 2)
                for r in extend_ratios
            }
        else:
            retracement = {
                f'{r:.1%}': round(points[1][1] + wave1_range * r, 2)
                for r in retrace_ratios
            }
            extension = {
                f'{r:.1%}': round(points[0][1] - wave1_range * r, 2)
                for r in extend_ratios
            }

        return {
            'retracement': retracement,
            'extension': extension,
            'wave1_range': round(wave1_range, 2)
        }

    def _calc_fibonacci_levels(self, highs: np.ndarray, lows: np.ndarray) -> Dict:
        """计算整体价格区间的斐波那契回撤水平

        基于整个数据集的最高价和最低价，计算 0% / 23.6% / 38.2% /
        50% / 61.8% / 78.6% / 100% 七个关键回撤位。

        Args:
            highs: 最高价数组
            lows: 最低价数组

        Returns:
            {'high': float, 'low': float, 'levels': {ratio: price}}
        """
        high = float(np.max(highs))
        low = float(np.min(lows))
        diff = high - low

        fib_ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        levels = {
            f'{r:.1%}': round(high - diff * r, 2)
            for r in fib_ratios
        }

        return {
            'high': high,
            'low': low,
            'levels': levels
        }

    def analyze_gann(self, kdata, period: int = 20,
                     sensitivity: float = 0.01) -> Dict:
        """Analyze using Gann methods

        Args:
            kdata: KData对象或DataFrame
            period: Period for analysis
            sensitivity: Sensitivity threshold

        Returns:
            Dict containing Gann analysis results
        """
        try:
            if isinstance(kdata, pd.DataFrame):
                # 直接使用DataFrame进行分析
                closes = kdata['close'].values
                highs = kdata['high'].values
                lows = kdata['low'].values
            else:
                # 假设kdata是其他格式，转换为numpy数组
                closes = np.array([float(k.close) for k in kdata])
                highs = np.array([float(k.high) for k in kdata])
                lows = np.array([float(k.low) for k in kdata])

            # Calculate Gann angles
            angles = [15, 30, 45, 60, 75]  # Main Gann angles
            gann_lines = {}

            # Get starting point
            start_price = closes[0]
            end_price = closes[-1]
            price_range = end_price - start_price

            for angle in angles:
                # Calculate angle lines
                rad = np.radians(angle)
                x = np.arange(len(closes))
                y = start_price + x * np.tan(rad) * sensitivity
                gann_lines[angle] = y

            # Calculate Gann square of nine
            price_levels = []
            time_levels = []

            # Price divisions
            price_min = np.min(lows)
            price_max = np.max(highs)
            price_range = price_max - price_min

            for i in range(9):
                level = price_min + (price_range / 8) * i
                price_levels.append(level)

            # Time divisions
            for i in range(9):
                level = int(len(closes) / 8 * i)
                time_levels.append(level)

            # Find support/resistance levels
            support_resistance = []
            for price in price_levels:
                # Count price touches
                touches = np.sum(np.abs(closes - price) < price_range * 0.01)
                if touches >= 3:  # Minimum 3 touches for valid level
                    support_resistance.append({
                        'price': price,
                        'touches': touches
                    })

            return {
                'gann_lines': gann_lines,
                'price_levels': price_levels,
                'time_levels': time_levels,
                'support_resistance': support_resistance
            }

        except Exception as e:
            raise Exception(f"Gann analysis failed: {str(e)}")

    def get_wave_signals(self, kdata) -> List[Dict]:
        """Get trading signals based on wave analysis

        Args:
            kdata: KData对象或DataFrame

        Returns:
            List of trading signals
        """
        try:
            if isinstance(kdata, pd.DataFrame):
                # DataStandardizer已经提供DataFrame原生支持，不需要转换
                pass  # 直接使用DataFrame进行分析
            # Get Elliott Wave analysis
            elliott = self.analyze_elliott_waves(kdata)

            # Get Gann analysis
            gann = self.analyze_gann(kdata)

            signals = []

            for wave in elliott['waves']:
                trend = wave.get('trend', 'bullish')

                if trend == 'bullish':
                    signals.append({
                        'type': 'elliott',
                        'signal': 'buy',
                        'price': wave['points'][0][1],
                        'index': wave['points'][0][0],
                        'strength': 0.8
                    })
                    signals.append({
                        'type': 'elliott',
                        'signal': 'sell',
                        'price': wave['points'][-1][1],
                        'index': wave['points'][-1][0],
                        'strength': 0.8
                    })
                else:
                    signals.append({
                        'type': 'elliott',
                        'signal': 'sell',
                        'price': wave['points'][0][1],
                        'index': wave['points'][0][0],
                        'strength': 0.8
                    })
                    signals.append({
                        'type': 'elliott',
                        'signal': 'buy',
                        'price': wave['points'][-1][1],
                        'index': wave['points'][-1][0],
                        'strength': 0.8
                    })

            # Generate Gann signals
            for level in gann['support_resistance']:
                if level['touches'] >= 5:  # Strong level
                    current_close = kdata.iloc[-1]['close'] if isinstance(kdata, pd.DataFrame) else kdata[-1].close
                    signals.append({
                        'type': 'gann',
                        'signal': 'support' if level['price'] < current_close else 'resistance',
                        'price': level['price'],
                        'touches': level['touches'],
                        'strength': level['touches'] / 10
                    })

            return signals

        except Exception as e:
            raise Exception(f"Wave signal generation failed: {str(e)}")
