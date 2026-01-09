"""
智能模型选择机制模块

提供基于市场状态检测、模型性能评估、动态选择策略和预测结果融合的智能模型选择功能。
"""

from .intelligent_selector import IntelligentModelSelector
from .market_detector import MarketStateDetector, MarketState
from .performance_evaluator import ModelPerformanceEvaluator, ModelPerformance
from .enhanced_model_evaluator import EnhancedModelEvaluator, EnhancedModelMetrics, EnhancedModelPerformance
from .selection_strategy import ModelSelectionStrategy, ModelSelection, SelectionCriteria
from .fusion_engine import PredictionFusionEngine, EnsemblePredictionResult

__all__ = [
    'IntelligentModelSelector',
    'MarketStateDetector',
    'MarketState',
    'ModelPerformanceEvaluator',
    'ModelPerformance',
    'EnhancedModelEvaluator',
    'EnhancedModelMetrics',
    'EnhancedModelPerformance',
    'ModelSelectionStrategy',
    'ModelSelection',
    'SelectionCriteria',
    'PredictionFusionEngine',
    'EnsemblePredictionResult'
]

__version__ = '1.0.0'