"""
智能信号计算器
基于市场上下文动态计算形态信号
"""

from typing import Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

from .pattern_base import SignalType


class IntelligentSignalCalculator:
    """智能信号计算器 - 基于市场上下文动态计算信号"""
    
    def __init__(self):
        self.trend_period = 20
        self.support_resistance_period = 50
    
    def calculate_signal(
        self,
        pattern_name: str,
        pattern_category: str,
        base_signal: SignalType,
        kdata: pd.DataFrame,
        index: int,
        confidence: float,
        trend_info: Optional[Dict] = None
    ) -> Tuple[SignalType, float, str]:
        """
        动态计算形态信号
        
        Args:
            pattern_name: 形态名称
            pattern_category: 形态类别
            base_signal: 基础信号类型（来自配置）
            kdata: K线数据
            index: 形态出现位置
            confidence: 基础置信度
            trend_info: 趋势信息（可选）
        
        Returns:
            (信号类型, 调整后置信度, 信号原因说明)
        """
        if trend_info is None:
            trend_info = self._analyze_trend(kdata, index)
        
        position_info = self._analyze_position(kdata, index)
        
        pattern_signal = self._get_pattern_intrinsic_signal(pattern_name, pattern_category)
        
        final_signal, adjusted_confidence, reason = self._synthesize_signal(
            pattern_signal=pattern_signal,
            base_signal=base_signal,
            trend_info=trend_info,
            position_info=position_info,
            confidence=confidence
        )
        
        return final_signal, adjusted_confidence, reason
    
    def _analyze_trend(self, kdata: pd.DataFrame, index: int) -> Dict[str, Any]:
        """分析趋势"""
        if index < self.trend_period:
            return {'trend': 'unknown', 'strength': 0.0, 'direction': 'sideways'}
        
        recent_data = kdata.iloc[index-self.trend_period:index+1]
        close = recent_data['close'].values
        
        sma20 = np.mean(close)
        sma60 = np.mean(kdata['close'].iloc[max(0, index-60):index+1].values) if index >= 60 else sma20
        
        x = np.arange(len(close))
        slope = np.polyfit(x, close, 1)[0]
        
        max_price = np.max(close)
        min_price = np.min(close)
        price_range = max_price - min_price
        strength = abs(slope) / price_range if price_range > 0 else 0.0
        
        current_price = close[-1]
        
        if current_price > sma20 * 1.02 and slope > 0:
            trend = 'uptrend'
            direction = 'up'
        elif current_price < sma20 * 0.98 and slope < 0:
            trend = 'downtrend'
            direction = 'down'
        else:
            trend = 'sideways'
            direction = 'sideways'
        
        return {
            'trend': trend,
            'direction': direction,
            'strength': min(strength * 10, 1.0),
            'slope': slope,
            'sma20': sma20,
            'sma60': sma60,
            'current_price': current_price
        }
    
    def _analyze_position(self, kdata: pd.DataFrame, index: int) -> Dict[str, Any]:
        """分析形态出现的位置"""
        if index < self.support_resistance_period:
            return {'position': 'unknown', 'near_support': False, 'near_resistance': False}
        
        recent_data = kdata.iloc[index-self.support_resistance_period:index+1]
        high = recent_data['high'].values
        low = recent_data['low'].values
        close = recent_data['close'].values
        
        resistance = np.max(high)
        support = np.min(low)
        current_price = close[-1]
        
        price_range = resistance - support
        threshold = price_range * 0.1
        
        near_resistance = abs(current_price - resistance) < threshold
        near_support = abs(current_price - support) < threshold
        
        if near_resistance:
            position = 'near_resistance'
        elif near_support:
            position = 'near_support'
        else:
            mid_point = (resistance + support) / 2
            if current_price > mid_point:
                position = 'upper_half'
            else:
                position = 'lower_half'
        
        return {
            'position': position,
            'near_support': near_support,
            'near_resistance': near_resistance,
            'resistance': resistance,
            'support': support,
            'current_price': current_price
        }
    
    def _get_pattern_intrinsic_signal(self, pattern_name: str, pattern_category: str) -> SignalType:
        """获取形态的内在信号属性"""
        pattern_lower = pattern_name.lower()
        
        bearish_keywords = [
            '顶', '头肩顶', '双顶', '三重顶', 'm顶', '圆弧顶',
            '射击', '上吊', '流星', '黄昏', '乌云', '覆盖',
            'top', 'head_shoulders_top', 'double_top', 'triple_top',
            'shooting', 'hanging', 'evening', 'dark_cloud'
        ]
        
        bullish_keywords = [
            '底', '头肩底', '双底', '三重底', 'w底', '圆弧底',
            '锤子', '启明星', '刺透', '孕线', '看涨',
            'bottom', 'head_shoulders_bottom', 'double_bottom', 'triple_bottom',
            'hammer', 'morning', 'piercing', 'bullish'
        ]
        
        for keyword in bearish_keywords:
            if keyword in pattern_lower:
                return SignalType.SELL
        
        for keyword in bullish_keywords:
            if keyword in pattern_lower:
                return SignalType.BUY
        
        return SignalType.NEUTRAL
    
    def _synthesize_signal(
        self,
        pattern_signal: SignalType,
        base_signal: SignalType,
        trend_info: Dict,
        position_info: Dict,
        confidence: float
    ) -> Tuple[SignalType, float, str]:
        """综合各种因素生成最终信号"""
        reasons = []
        adjusted_confidence = confidence
        
        trend = trend_info.get('trend', 'sideways')
        trend_strength = trend_info.get('strength', 0.0)
        
        position = position_info.get('position', 'unknown')
        near_support = position_info.get('near_support', False)
        near_resistance = position_info.get('near_resistance', False)
        
        final_signal = pattern_signal
        
        if pattern_signal == SignalType.SELL:
            if trend == 'uptrend':
                if near_resistance:
                    reasons.append("看跌形态出现在上升趋势的阻力位附近")
                    adjusted_confidence *= 1.2
                    reasons.append("趋势+位置共振，信号增强")
                else:
                    reasons.append("看跌形态出现在上升趋势中")
                    adjusted_confidence *= 0.8
                    reasons.append("与趋势相反，信号减弱")
            elif trend == 'downtrend':
                reasons.append("看跌形态出现在下降趋势中")
                adjusted_confidence *= 1.1
                reasons.append("顺应趋势，信号增强")
            else:
                if near_resistance:
                    reasons.append("看跌形态出现在横盘震荡的阻力位")
                    adjusted_confidence *= 1.1
                else:
                    reasons.append("看跌形态出现在横盘震荡中")
        
        elif pattern_signal == SignalType.BUY:
            if trend == 'downtrend':
                if near_support:
                    reasons.append("看涨形态出现在下降趋势的支撑位附近")
                    adjusted_confidence *= 1.2
                    reasons.append("趋势+位置共振，信号增强")
                else:
                    reasons.append("看涨形态出现在下降趋势中")
                    adjusted_confidence *= 0.8
                    reasons.append("与趋势相反，信号减弱")
            elif trend == 'uptrend':
                reasons.append("看涨形态出现在上升趋势中")
                adjusted_confidence *= 1.1
                reasons.append("顺应趋势，信号增强")
            else:
                if near_support:
                    reasons.append("看涨形态出现在横盘震荡的支撑位")
                    adjusted_confidence *= 1.1
                else:
                    reasons.append("看涨形态出现在横盘震荡中")
        
        else:
            reasons.append("中性形态，需结合其他指标判断")
            if trend == 'uptrend' and near_support:
                final_signal = SignalType.BUY
                adjusted_confidence *= 0.7
                reasons.append("中性形态在上升趋势支撑位，倾向买入")
            elif trend == 'downtrend' and near_resistance:
                final_signal = SignalType.SELL
                adjusted_confidence *= 0.7
                reasons.append("中性形态在下降趋势阻力位，倾向卖出")
        
        adjusted_confidence = min(1.0, max(0.1, adjusted_confidence))
        
        reason_text = "; ".join(reasons) if reasons else "基于形态特征和上下文综合判断"
        
        return final_signal, adjusted_confidence, reason_text


def create_intelligent_signal_calculator():
    """创建智能信号计算器实例"""
    return IntelligentSignalCalculator()
