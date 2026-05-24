"""
市场状态检测模块

提供波动率分析、趋势强度分析、市场体制分类和流动性状态评估功能
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from .config.selector_config import MarketDetectionConfig

class VolatilityState(Enum):
    """波动率状态"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class TrendStrengthState(Enum):
    """趋势强度状态"""
    WEAK = "weak"
    NORMAL = "normal"
    STRONG = "strong"


class MarketRegime(Enum):
    """市场体制"""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"
    STABLE = "stable"


class LiquidityState(Enum):
    """流动性状态"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass
class VolatilityAnalysis:
    """波动率分析结果"""
    level: VolatilityState
    historical_volatility: float
    realized_volatility: float
    volatility_ratio: float
    timestamp: datetime


@dataclass
class TrendStrengthAnalysis:
    """趋势强度分析结果"""
    level: TrendStrengthState
    strength: float
    direction: str  # up, down, sideways
    confidence: float
    timestamp: datetime


@dataclass
class MarketRegimeAnalysis:
    """市场体制分析结果"""
    regime: MarketRegime
    confidence: float
    duration: int  # 天数
    characteristics: Dict[str, Any]
    timestamp: datetime


@dataclass
class LiquidityAnalysis:
    """流动性分析结果"""
    level: LiquidityState
    score: float
    factors: Dict[str, float]
    timestamp: datetime


@dataclass
class MarketState:
    """市场状态综合信息"""
    volatility: VolatilityAnalysis
    trend_strength: TrendStrengthAnalysis
    market_regime: MarketRegimeAnalysis
    liquidity: LiquidityAnalysis
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'volatility': {
                'level': self.volatility.level.value,
                'historical_volatility': self.volatility.historical_volatility,
                'realized_volatility': self.volatility.realized_volatility,
                'volatility_ratio': self.volatility.volatility_ratio
            },
            'trend_strength': {
                'level': self.trend_strength.level.value,
                'strength': self.trend_strength.strength,
                'direction': self.trend_strength.direction,
                'confidence': self.trend_strength.confidence
            },
            'market_regime': {
                'regime': self.market_regime.regime.value,
                'confidence': self.market_regime.confidence,
                'duration': self.market_regime.duration,
                'characteristics': self.market_regime.characteristics
            },
            'liquidity': {
                'level': self.liquidity.level.value,
                'score': self.liquidity.score,
                'factors': self.liquidity.factors
            },
            'timestamp': self.timestamp.isoformat()
        }


class VolatilityAnalyzer:
    """波动率分析器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.high_threshold = config.get('high_vol_threshold', 0.25)
        self.low_threshold = config.get('low_vol_threshold', 0.05)
        self.window_size = config.get('window_size', 20)
    
    def analyze(self, kdata: pd.DataFrame) -> VolatilityAnalysis:
        """分析波动率状态"""
        try:
            if len(kdata) < self.window_size:
                return self._get_default_analysis()
            
            # 计算收益率
            returns = kdata['close'].pct_change().dropna()
            
            # 计算历史波动率
            historical_vol = returns.std() * np.sqrt(252)
            
            # 计算实现波动率（短期）
            realized_vol = returns.tail(self.window_size).std() * np.sqrt(252)
            
            # 波动率状态分类
            if historical_vol > self.high_threshold:
                level = VolatilityState.HIGH
            elif historical_vol < self.low_threshold:
                level = VolatilityState.LOW
            else:
                level = VolatilityState.NORMAL
            
            return VolatilityAnalysis(
                level=level,
                historical_volatility=historical_vol,
                realized_volatility=realized_vol,
                volatility_ratio=realized_vol / historical_vol if historical_vol > 0 else 1.0,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"波动率分析失败: {e}")
            return self._get_default_analysis()
    
    def _get_default_analysis(self) -> VolatilityAnalysis:
        """获取默认分析结果"""
        return VolatilityAnalysis(
            level=VolatilityState.NORMAL,
            historical_volatility=0.15,
            realized_volatility=0.15,
            volatility_ratio=1.0,
            timestamp=datetime.now()
        )


class TrendStrengthAnalyzer:
    """趋势强度分析器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.strong_threshold = config.get('strong_threshold', 0.8)
        self.weak_threshold = config.get('weak_threshold', 0.2)
        self.lookback_period = config.get('lookback_period', 50)
    
    def analyze(self, kdata: pd.DataFrame, market_data: Dict[str, Any]) -> TrendStrengthAnalysis:
        """分析趋势强度"""
        try:
            if len(kdata) < self.lookback_period:
                return self._get_default_analysis()
            
            close_prices = kdata['close']
            
            # 计算线性回归斜率
            x = np.arange(len(close_prices))
            y = close_prices.values
            slope, intercept = np.polyfit(x, y, 1)
            
            # 标准化斜率
            normalized_slope = slope / close_prices.mean()
            
            # 计算趋势强度
            strength = abs(normalized_slope)
            
            # 判断趋势方向
            if slope > 0:
                direction = 'up'
            elif slope < 0:
                direction = 'down'
            else:
                direction = 'sideways'
            
            # 趋势强度分类
            if strength > self.strong_threshold:
                level = TrendStrengthState.STRONG
            elif strength < self.weak_threshold:
                level = TrendStrengthState.WEAK
            else:
                level = TrendStrengthState.NORMAL
            
            # 计算置信度
            correlation = np.corrcoef(x, y)[0, 1]
            confidence = abs(correlation) if not np.isnan(correlation) else 0.5
            
            return TrendStrengthAnalysis(
                level=level,
                strength=strength,
                direction=direction,
                confidence=confidence,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"趋势强度分析失败: {e}")
            return self._get_default_analysis()
    
    def _get_default_analysis(self) -> TrendStrengthAnalysis:
        """获取默认分析结果"""
        return TrendStrengthAnalysis(
            level=TrendStrengthState.NORMAL,
            strength=0.5,
            direction='sideways',
            confidence=0.5,
            timestamp=datetime.now()
        )


class MarketRegimeClassifier:
    """市场体制分类器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.classification_period = config.get('classification_period', 30)
    
    def classify(self, kdata: pd.DataFrame, 
                volatility_analysis: VolatilityAnalysis,
                trend_analysis: TrendStrengthAnalysis) -> MarketRegimeAnalysis:
        """分类市场体制"""
        try:
            if len(kdata) < self.classification_period:
                return self._get_default_analysis()
            
            close_prices = kdata['close']
            
            # 计算总收益率
            total_return = (close_prices.iloc[-1] - close_prices.iloc[0]) / close_prices.iloc[0]
            
            # 分析特征
            characteristics = {
                'volatility_level': volatility_analysis.level.value,
                'trend_strength': trend_analysis.strength,
                'trend_direction': trend_analysis.direction,
                'total_return': total_return,
                'realized_vol': volatility_analysis.realized_volatility
            }
            
            # 体制分类逻辑
            if total_return > 0.1 and trend_analysis.direction == 'up':
                regime = MarketRegime.BULL
                confidence = min(0.9, 0.5 + abs(total_return) * 2)
            elif total_return < -0.1 and trend_analysis.direction == 'down':
                regime = MarketRegime.BEAR
                confidence = min(0.9, 0.5 + abs(total_return) * 2)
            elif volatility_analysis.level == VolatilityState.HIGH:
                regime = MarketRegime.VOLATILE
                confidence = min(0.8, 0.6 + volatility_analysis.realized_volatility)
            elif abs(total_return) < 0.05:
                regime = MarketRegime.SIDEWAYS
                confidence = 0.7
            else:
                regime = MarketRegime.STABLE
                confidence = 0.6
            
            return MarketRegimeAnalysis(
                regime=regime,
                confidence=confidence,
                duration=self.classification_period,
                characteristics=characteristics,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"市场体制分类失败: {e}")
            return self._get_default_analysis()
    
    def _get_default_analysis(self) -> MarketRegimeAnalysis:
        """获取默认分析结果"""
        return MarketRegimeAnalysis(
            regime=MarketRegime.STABLE,
            confidence=0.5,
            duration=30,
            characteristics={},
            timestamp=datetime.now()
        )


class LiquidityStateAssessor:
    """流动性状态评估器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.low_threshold = config.get('low_threshold', 0.3)
    
    def assess(self, market_data: Dict[str, Any]) -> LiquidityAnalysis:
        """评估流动性状态"""
        try:
            factors = {}
            score = 0.5  # 默认分数
            
            # 基于成交量的评估
            if 'volume' in market_data:
                volume = market_data['volume']
                if isinstance(volume, (list, np.ndarray)) and len(volume) > 0:
                    avg_volume = np.mean(volume)
                    recent_volume = volume[-1] if len(volume) > 0 else avg_volume
                    
                    volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
                    volume_score = min(volume_ratio, 2.0) / 2.0  # 归一化到0-1
                    factors['volume_ratio'] = volume_ratio
                    score = score * 0.7 + volume_score * 0.3
            
            # 基于价差的评估（如果有相关数据）
            if 'spread' in market_data:
                spread = market_data['spread']
                spread_score = max(0, 1 - spread * 10)  # 假设价差越小流动性越好
                factors['spread_score'] = spread_score
                score = score * 0.8 + spread_score * 0.2
            
            # 流动性状态分类
            if score < self.low_threshold:
                level = LiquidityState.LOW
            elif score > 0.7:
                level = LiquidityState.HIGH
            else:
                level = LiquidityState.NORMAL
            
            return LiquidityAnalysis(
                level=level,
                score=score,
                factors=factors,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"流动性评估失败: {e}")
            return self._get_default_analysis()
    
    def _get_default_analysis(self) -> LiquidityAnalysis:
        """获取默认分析结果"""
        return LiquidityAnalysis(
            level=LiquidityState.NORMAL,
            score=0.5,
            factors={},
            timestamp=datetime.now()
        )


class MarketStateDetector:
    """市场状态检测器"""
    
    def __init__(self, config: MarketDetectionConfig):
        self.config = config
        
        # 获取各组件的配置字典
        volatility_config = config.volatility if config.volatility else {}
        trend_config = config.trend if config.trend else {}
        regime_config = config.regime if config.regime else {}
        liquidity_config = config.liquidity if config.liquidity else {}
        
        self.volatility_analyzer = VolatilityAnalyzer(volatility_config)
        self.trend_analyzer = TrendStrengthAnalyzer(trend_config)
        self.regime_classifier = MarketRegimeClassifier(regime_config)
        self.liquidity_assessor = LiquidityStateAssessor(liquidity_config)
        
        logger.info("市场状态检测器初始化完成")
    
    def detect_market_state(self, 
                          kdata: pd.DataFrame,
                          market_data: Dict[str, Any]) -> MarketState:
        """综合检测市场状态"""
        try:
            # 波动率分析
            volatility = self.volatility_analyzer.analyze(kdata)
            
            # 趋势强度分析  
            trend_strength = self.trend_analyzer.analyze(kdata, market_data)
            
            # 市场体制分类
            market_regime = self.regime_classifier.classify(
                kdata, volatility, trend_strength
            )
            
            # 流动性状态评估
            liquidity = self.liquidity_assessor.assess(market_data)
            
            market_state = MarketState(
                volatility=volatility,
                trend_strength=trend_strength,
                market_regime=market_regime,
                liquidity=liquidity,
                timestamp=datetime.now()
            )
            
            logger.debug(f"市场状态检测完成: {market_regime.regime.value}, "
                        f"波动率: {volatility.level.value}, "
                        f"趋势强度: {trend_strength.level.value}")
            
            return market_state
            
        except Exception as e:
            logger.error(f"市场状态检测失败: {e}")
            return self._get_default_market_state()
    
    def _get_default_market_state(self) -> MarketState:
        """获取默认市场状态"""
        default_volatility = VolatilityAnalysis(
            level=VolatilityState.NORMAL,
            historical_volatility=0.15,
            realized_volatility=0.15,
            volatility_ratio=1.0,
            timestamp=datetime.now()
        )
        
        default_trend = TrendStrengthAnalysis(
            level=TrendStrengthState.NORMAL,
            strength=0.5,
            direction='sideways',
            confidence=0.5,
            timestamp=datetime.now()
        )
        
        default_regime = MarketRegimeAnalysis(
            regime=MarketRegime.STABLE,
            confidence=0.5,
            duration=30,
            characteristics={},
            timestamp=datetime.now()
        )
        
        default_liquidity = LiquidityAnalysis(
            level=LiquidityState.NORMAL,
            score=0.5,
            factors={},
            timestamp=datetime.now()
        )
        
        return MarketState(
            volatility=default_volatility,
            trend_strength=default_trend,
            market_regime=default_regime,
            liquidity=default_liquidity,
            timestamp=datetime.now()
        )