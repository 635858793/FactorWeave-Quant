"""
优化版智能信号计算器
添加缓存机制和线程安全
"""

from typing import Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
import threading
from functools import lru_cache

from .pattern_base import SignalType


class IntelligentSignalCalculatorOptimized:
    """优化版智能信号计算器 - 带缓存和线程安全"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.trend_period = 20
        self.support_resistance_period = 50
        self._cache_lock = threading.Lock()
        self._trend_cache: Dict[str, Dict] = {}
        self._position_cache: Dict[str, Dict] = {}
        self._initialized = True
    
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
        动态计算形态信号（优化版）
        
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
        try:
            if not self._validate_input(kdata, index):
                return base_signal, confidence, "输入数据无效，使用原始信号"
            
            if trend_info is None:
                cache_key = self._get_cache_key(kdata, index)
                trend_info = self._get_cached_trend(cache_key, kdata, index)
            
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
            
        except Exception as e:
            return base_signal, confidence, f"信号计算异常: {str(e)}"
    
    def _validate_input(self, kdata: pd.DataFrame, index: int) -> bool:
        """验证输入数据"""
        if kdata is None or kdata.empty:
            return False
        if index < 0 or index >= len(kdata):
            return False
        required_columns = ['open', 'high', 'low', 'close']
        if not all(col in kdata.columns for col in required_columns):
            return False
        if kdata[required_columns].isnull().any().any():
            return False
        return True
    
    def _get_cache_key(self, kdata: pd.DataFrame, index: int) -> str:
        """生成缓存键"""
        try:
            if hasattr(kdata.index, '__getitem__'):
                date_str = str(kdata.index[index])
            else:
                date_str = str(index)
            
            close_hash = hash(tuple(kdata['close'].iloc[max(0, index-20):index+1].values))
            return f"{date_str}_{close_hash}"
        except:
            return str(index)
    
    def _get_cached_trend(self, cache_key: str, kdata: pd.DataFrame, index: int) -> Dict:
        """获取缓存的趋势信息"""
        with self._cache_lock:
            if cache_key in self._trend_cache:
                return self._trend_cache[cache_key]
        
        trend_info = self._analyze_trend(kdata, index)
        
        with self._cache_lock:
            self._trend_cache[cache_key] = trend_info
            
            if len(self._trend_cache) > 1000:
                keys = list(self._trend_cache.keys())[:500]
                for key in keys:
                    del self._trend_cache[key]
        
        return trend_info
    
    def _analyze_trend(self, kdata: pd.DataFrame, index: int) -> Dict[str, Any]:
        """分析趋势（优化版）"""
        if index < self.trend_period:
            return {'trend': 'unknown', 'strength': 0.0, 'direction': 'sideways'}
        
        try:
            recent_data = kdata.iloc[index-self.trend_period:index+1]
            close = recent_data['close'].values
            
            if len(close) == 0 or np.any(np.isnan(close)):
                return {'trend': 'unknown', 'strength': 0.0, 'direction': 'sideways'}
            
            sma20 = float(np.mean(close))
            
            sma60 = sma20
            if index >= 60:
                sma60_data = kdata['close'].iloc[max(0, index-60):index+1].values
                if len(sma60_data) > 0 and not np.any(np.isnan(sma60_data)):
                    sma60 = float(np.mean(sma60_data))
            
            x = np.arange(len(close))
            if len(x) > 1:
                slope = float(np.polyfit(x, close, 1)[0])
            else:
                slope = 0.0
            
            max_price = float(np.max(close))
            min_price = float(np.min(close))
            price_range = max_price - min_price
            
            if price_range > 0:
                strength = min(abs(slope) / price_range * 10, 1.0)
            else:
                strength = 0.0
            
            current_price = float(close[-1])
            
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
            
            if current_price > sma20 * (1 + atr_multiplier) and slope > 0:
                trend = 'uptrend'
                direction = 'up'
            elif current_price < sma20 * (1 - atr_multiplier) and slope < 0:
                trend = 'downtrend'
                direction = 'down'
            else:
                trend = 'sideways'
                direction = 'sideways'
            
            return {
                'trend': trend,
                'direction': direction,
                'strength': strength,
                'slope': slope,
                'sma20': sma20,
                'sma60': sma60,
                'current_price': current_price
            }
            
        except Exception as e:
            return {'trend': 'unknown', 'strength': 0.0, 'direction': 'sideways'}
    
    def _analyze_position(self, kdata: pd.DataFrame, index: int) -> Dict[str, Any]:
        """分析形态出现的位置（优化版）"""
        if index < self.support_resistance_period:
            return {'position': 'unknown', 'near_support': False, 'near_resistance': False}
        
        try:
            recent_data = kdata.iloc[index-self.support_resistance_period:index+1]
            high = recent_data['high'].values
            low = recent_data['low'].values
            close = recent_data['close'].values
            
            if len(high) == 0 or len(low) == 0 or len(close) == 0:
                return {'position': 'unknown', 'near_support': False, 'near_resistance': False}
            
            if np.any(np.isnan(high)) or np.any(np.isnan(low)) or np.any(np.isnan(close)):
                return {'position': 'unknown', 'near_support': False, 'near_resistance': False}
            
            resistance = float(np.max(high))
            support = float(np.min(low))
            current_price = float(close[-1])
            
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
            
        except Exception as e:
            return {'position': 'unknown', 'near_support': False, 'near_resistance': False}
    
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
                    adjusted_confidence = min(adjusted_confidence * 1.2, 1.0)
                    reasons.append("趋势+位置共振，信号增强")
                else:
                    reasons.append("看跌形态出现在上升趋势中")
                    adjusted_confidence = adjusted_confidence * 0.8
                    reasons.append("与趋势相反，信号减弱")
            elif trend == 'downtrend':
                reasons.append("看跌形态出现在下降趋势中")
                adjusted_confidence = min(adjusted_confidence * 1.1, 1.0)
                reasons.append("顺应趋势，信号增强")
            else:
                if near_resistance:
                    reasons.append("看跌形态出现在横盘震荡的阻力位")
                    adjusted_confidence = min(adjusted_confidence * 1.1, 1.0)
                else:
                    reasons.append("看跌形态出现在横盘震荡中")
        
        elif pattern_signal == SignalType.BUY:
            if trend == 'downtrend':
                if near_support:
                    reasons.append("看涨形态出现在下降趋势的支撑位附近")
                    adjusted_confidence = min(adjusted_confidence * 1.2, 1.0)
                    reasons.append("趋势+位置共振，信号增强")
                else:
                    reasons.append("看涨形态出现在下降趋势中")
                    adjusted_confidence = adjusted_confidence * 0.8
                    reasons.append("与趋势相反，信号减弱")
            elif trend == 'uptrend':
                reasons.append("看涨形态出现在上升趋势中")
                adjusted_confidence = min(adjusted_confidence * 1.1, 1.0)
                reasons.append("顺应趋势，信号增强")
            else:
                if near_support:
                    reasons.append("看涨形态出现在横盘震荡的支撑位")
                    adjusted_confidence = min(adjusted_confidence * 1.1, 1.0)
                else:
                    reasons.append("看涨形态出现在横盘震荡中")
        
        else:
            reasons.append("中性形态，需结合其他指标判断")
            if trend == 'uptrend' and near_support:
                final_signal = SignalType.BUY
                adjusted_confidence = adjusted_confidence * 0.7
                reasons.append("中性形态在上升趋势支撑位，倾向买入")
            elif trend == 'downtrend' and near_resistance:
                final_signal = SignalType.SELL
                adjusted_confidence = adjusted_confidence * 0.7
                reasons.append("中性形态在下降趋势阻力位，倾向卖出")
        
        adjusted_confidence = min(1.0, max(0.1, adjusted_confidence))
        
        reason_text = "; ".join(reasons) if reasons else "基于形态特征和上下文综合判断"
        
        return final_signal, adjusted_confidence, reason_text
    
    def clear_cache(self):
        """清空缓存"""
        with self._cache_lock:
            self._trend_cache.clear()
            self._position_cache.clear()


def create_intelligent_signal_calculator():
    """创建智能信号计算器实例（单例）"""
    return IntelligentSignalCalculatorOptimized()
