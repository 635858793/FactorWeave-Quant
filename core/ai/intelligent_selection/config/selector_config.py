"""
智能模型选择器配置管理
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class MarketDetectionConfig:
    """市场状态检测配置"""
    volatility: Dict[str, Any] = None
    trend: Dict[str, Any] = None
    regime: Dict[str, Any] = None
    liquidity: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.volatility is None:
            self.volatility = {
                'high_vol_threshold': 0.25,
                'low_vol_threshold': 0.05,
                'window_size': 20
            }
        
        if self.trend is None:
            self.trend = {
                'strong_threshold': 0.8,
                'weak_threshold': 0.2,
                'lookback_period': 50
            }
        
        if self.regime is None:
            self.regime = {
                'classification_period': 30
            }
        
        if self.liquidity is None:
            self.liquidity = {
                'low_threshold': 0.3
            }


@dataclass
class PerformanceEvaluationConfig:
    """性能评估配置"""
    metric_weights: Dict[str, float] = None
    database: Dict[str, Any] = None
    evaluation_window: int = 100
    
    def __post_init__(self):
        if self.metric_weights is None:
            self.metric_weights = {
                'accuracy': 0.3,
                'precision': 0.2,
                'recall': 0.2,
                'f1_score': 0.15,
                'mse': 0.1,
                'mae': 0.05
            }
        
        if self.database is None:
            self.database = {
                'type': 'sqlite',
                'path': 'data/performance.sqlite'
            }


@dataclass
class SelectionStrategyConfig:
    """选择策略配置"""
    decision_matrix: Dict[str, Any] = None
    constraints: Dict[str, Any] = None
    ensemble: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.decision_matrix is None:
            self.decision_matrix = {
                'method': 'ahp',  # Analytic Hierarchy Process
                'normalize': True
            }
        
        if self.constraints is None:
            self.constraints = {
                'max_models': 5,
                'min_accuracy': 0.6,
                'max_latency': 2000,
                'required_models': []
            }
        
        if self.ensemble is None:
            self.ensemble = {
                'method': 'weighted_average',
                'confidence_threshold': 0.7,
                'min_contributors': 1
            }


@dataclass
class FusionConfig:
    """融合引擎配置"""
    max_history_size: int = 100
    enable_adaptive_weights: bool = True
    confidence_threshold: float = 0.5
    
    # 各种融合策略的配置
    weighted_average: Dict[str, Any] = None
    voting: Dict[str, Any] = None
    stacking: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.weighted_average is None:
            self.weighted_average = {
                'normalize_weights': True,
                'confidence_weight': 0.3,
                'performance_weight': 0.7
            }
        
        if self.voting is None:
            self.voting = {
                'method': 'soft',
                'weight_by_confidence': True
            }
        
        if self.stacking is None:
            self.stacking = {
                'meta_learner': 'linear',
                'validation_split': 0.2
            }


@dataclass
class IntelligentSelectorConfig:
    """智能模型选择器主配置"""
    
    # 版本信息
    version: str = "1.0.0"
    
    # 缓存配置
    enable_cache: bool = True
    max_cache_size: int = 1000
    cache_ttl: int = 300  # 5分钟
    
    # 融合配置
    enable_fusion: bool = True
    max_ensemble_size: int = 3
    
    # 性能阈值
    performance_thresholds: Dict[str, float] = None
    
    # 各组件配置
    market_detection: MarketDetectionConfig = None
    performance_evaluation: PerformanceEvaluationConfig = None
    selection_strategy: SelectionStrategyConfig = None
    fusion: FusionConfig = None
    
    def __post_init__(self):
        if self.performance_thresholds is None:
            self.performance_thresholds = {
                'accuracy_low': 0.60,
                'accuracy_high': 0.95,
                'latency_max': 1000,  # 毫秒
                'memory_max': 512,   # MB
                'throughput_min': 10  # 每秒预测次数
            }
        
        # 初始化各组件配置
        if self.market_detection is None:
            self.market_detection = MarketDetectionConfig()
        
        if self.performance_evaluation is None:
            self.performance_evaluation = PerformanceEvaluationConfig()
        
        if self.selection_strategy is None:
            self.selection_strategy = SelectionStrategyConfig()
        
        if self.fusion is None:
            self.fusion = FusionConfig()
    
    @classmethod
    def load_from_file(cls, config_path: str) -> 'IntelligentSelectorConfig':
        """从配置文件加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            return cls(**config_data)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return cls()
    
    def save_to_file(self, config_path: str):
        """保存配置到文件"""
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def update(self, **kwargs):
        """更新配置参数"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def get_config_dict(self) -> Dict[str, Any]:
        """获取配置字典"""
        return asdict(self)