"""
预测结果融合引擎

提供多种融合策略对多个模型的预测结果进行综合处理。
"""

from loguru import logger
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

from .config.selector_config import FusionConfig
from .config.model_profiles import ModelProfile

class FusionMethod(Enum):
    """融合方法枚举"""
    WEIGHTED_AVERAGE = "weighted_average"
    VOTING = "voting"
    STACKING = "stacking"
    DYNAMIC_WEIGHT = "dynamic_weight"
    CONFIDENCE_BASED = "confidence_based"
    ADAPTIVE_FUSION = "adaptive_fusion"


@dataclass
class ModelPrediction:
    """模型预测结果"""
    model_type: str
    prediction_value: float
    confidence: float
    timestamp: datetime
    metadata: Dict[str, Any] = None


@dataclass
class EnsemblePredictionResult:
    """集成预测结果"""
    final_prediction: float
    confidence: float
    contributing_models: List[str]
    fusion_method: str
    individual_predictions: List[ModelPrediction]
    timestamp: datetime
    metadata: Dict[str, Any] = None


class WeightedAverageFusion:
    """加权平均融合策略"""
    
    def __init__(self, config: FusionConfig):
        self.config = config
        self.weight_calculator = DynamicWeightCalculator(config)
    
    def fuse_predictions(self, predictions: List[ModelPrediction]) -> EnsemblePredictionResult:
        """加权平均融合"""
        try:
            if not predictions:
                raise ValueError("没有预测结果可融合")
            
            # 计算动态权重
            weights = self.weight_calculator.calculate_weights(predictions)
            
            # 加权平均
            total_weight = sum(weights.values())
            if total_weight == 0:
                # 如果权重总和为0，使用等权重
                weights = {pred.model_type: 1.0 for pred in predictions}
                total_weight = len(predictions)
            
            weighted_sum = sum(
                pred.prediction_value * weights.get(pred.model_type, 0.0)
                for pred in predictions
            )
            missing_weights = [p.model_type for p in predictions if p.model_type not in weights]
            if missing_weights:
                logger.warning(f"以下模型在权重计算中缺失，将获得0权重: {missing_weights}")
            final_prediction = weighted_sum / total_weight
            
            # 计算综合置信度
            confidence = self._calculate_confidence(predictions, weights)
            
            # 贡献模型列表
            contributing_models = [pred.model_type for pred in predictions]
            
            return EnsemblePredictionResult(
                final_prediction=final_prediction,
                confidence=confidence,
                contributing_models=contributing_models,
                fusion_method=FusionMethod.WEIGHTED_AVERAGE.value,
                individual_predictions=predictions,
                timestamp=datetime.now(),
                metadata={
                    'weights': weights,
                    'method_specific': {
                        'total_weight': total_weight,
                        'prediction_count': len(predictions)
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"加权平均融合失败: {e}")
            # 返回默认融合结果
            return self._get_fallback_result(predictions)
    
    def _calculate_confidence(self, predictions: List[ModelPrediction], 
                            weights: Dict[str, float]) -> float:
        """计算融合后的置信度"""
        try:
            # 基于模型置信度和权重计算综合置信度
            weighted_confidences = [
                pred.confidence * weights.get(pred.model_type, 0.0)
                for pred in predictions
            ]
            
            total_weight = sum(weights.values())
            if total_weight == 0:
                return 0.5
            
            confidence = sum(weighted_confidences) / total_weight
            return min(max(confidence, 0.0), 1.0)  # 限制在[0,1]范围内
            
        except Exception as e:
            logger.warning(f"计算融合置信度失败: {e}")
            return 0.5
    
    def _get_fallback_result(self, predictions: List[ModelPrediction]) -> EnsemblePredictionResult:
        """获取融合失败时的默认结果"""
        if not predictions:
            return EnsemblePredictionResult(
                final_prediction=0.0,
                confidence=0.0,
                contributing_models=[],
                fusion_method=FusionMethod.WEIGHTED_AVERAGE.value,
                individual_predictions=[],
                timestamp=datetime.now()
            )
        
        # 使用简单平均
        avg_prediction = np.mean([p.prediction_value for p in predictions])
        avg_confidence = np.mean([p.confidence for p in predictions])
        
        return EnsemblePredictionResult(
            final_prediction=avg_prediction,
            confidence=avg_confidence,
            contributing_models=[p.model_type for p in predictions],
            fusion_method=FusionMethod.WEIGHTED_AVERAGE.value + "_fallback",
            individual_predictions=predictions,
            timestamp=datetime.now(),
            metadata={'fallback': True}
        )


class VotingFusion:
    """投票融合策略"""
    
    def __init__(self, config: FusionConfig):
        self.config = config
    
    def fuse_predictions(self, predictions: List[ModelPrediction]) -> EnsemblePredictionResult:
        """投票融合"""
        try:
            if not predictions:
                raise ValueError("没有预测结果可融合")
            
            # 基于置信度进行加权投票
            weighted_votes = {}
            total_weight = 0
            
            for pred in predictions:
                weight = pred.confidence
                weighted_votes[pred.prediction_value] = \
                    weighted_votes.get(pred.prediction_value, 0) + weight
                total_weight += weight
            
            if total_weight == 0:
                # 如果总权重为0，使用等权重
                for pred in predictions:
                    weighted_votes[pred.prediction_value] = \
                        weighted_votes.get(pred.prediction_value, 0) + 1
                total_weight = len(predictions)
            
            # 选择得票最多的预测值
            final_prediction = max(weighted_votes.items(), key=lambda x: x[1])[0]
            
            # 计算置信度（基于获胜预测的得票比例）
            winning_votes = weighted_votes[final_prediction]
            confidence = winning_votes / total_weight if total_weight > 0 else 0.5
            
            return EnsemblePredictionResult(
                final_prediction=final_prediction,
                confidence=confidence,
                contributing_models=[p.model_type for p in predictions],
                fusion_method=FusionMethod.VOTING.value,
                individual_predictions=predictions,
                timestamp=datetime.now(),
                metadata={
                    'vote_counts': weighted_votes,
                    'total_weight': total_weight,
                    'winning_votes': winning_votes
                }
            )
            
        except Exception as e:
            logger.error(f"投票融合失败: {e}")
            return self._get_fallback_result(predictions)
    
    def _get_fallback_result(self, predictions: List[ModelPrediction]) -> EnsemblePredictionResult:
        """获取融合失败时的默认结果"""
        if not predictions:
            return EnsemblePredictionResult(
                final_prediction=0.0,
                confidence=0.0,
                contributing_models=[],
                fusion_method=FusionMethod.VOTING.value,
                individual_predictions=[],
                timestamp=datetime.now()
            )
        
        # 使用多数预测值
        predictions_by_value = {}
        for pred in predictions:
            predictions_by_value[pred.prediction_value] = \
                predictions_by_value.get(pred.prediction_value, 0) + 1
        
        final_prediction = max(predictions_by_value.items(), key=lambda x: x[1])[0]
        confidence = predictions_by_value[final_prediction] / len(predictions)
        
        return EnsemblePredictionResult(
            final_prediction=final_prediction,
            confidence=confidence,
            contributing_models=[p.model_type for p in predictions],
            fusion_method=FusionMethod.VOTING.value + "_fallback",
            individual_predictions=predictions,
            timestamp=datetime.now(),
            metadata={'fallback': True}
        )


class DynamicWeightCalculator:
    """动态权重计算器"""
    
    def __init__(self, config: FusionConfig):
        self.config = config
        self.historical_performance = {}  # 缓存历史性能数据
    
    def calculate_weights(self, predictions: List[ModelPrediction]) -> Dict[str, float]:
        """基于历史性能动态计算权重"""
        try:
            weights = {}
            
            for pred in predictions:
                # 获取模型历史性能
                performance_score = self._get_model_performance(pred.model_type)
                
                # 结合当前预测置信度
                confidence_weight = pred.confidence
                
                # 综合权重
                weight = performance_score * confidence_weight
                weights[pred.model_type] = weight
            
            # 归一化权重
            total_weight = sum(weights.values())
            if total_weight > 0:
                weights = {k: v / total_weight for k, v in weights.items()}
            else:
                # 如果总权重为0，使用等权重
                weights = {pred.model_type: 1.0 / len(predictions) 
                          for pred in predictions}
            
            return weights
            
        except Exception as e:
            logger.warning(f"动态权重计算失败: {e}")
            # 返回等权重
            return {pred.model_type: 1.0 / len(predictions) 
                   for pred in predictions}
    
    def _get_model_performance(self, model_type: str) -> float:
        """获取模型性能评分"""
        try:
            if model_type in self.historical_performance:
                return self.historical_performance[model_type]
            
            # 实际应用中，这里应该从数据库或缓存中获取历史性能数据
            # 现在使用默认性能评分
            default_performance = self._get_default_performance(model_type)
            self.historical_performance[model_type] = default_performance
            return default_performance
            
        except Exception as e:
            logger.warning(f"获取模型{model_type}性能失败: {e}")
            return 0.5
    
    def _get_default_performance(self, model_type: str) -> float:
        """获取默认性能评分"""
        # 基于模型类型的默认性能评分
        default_performances = {
            'linear_regression': 0.6,
            'random_forest': 0.7,
            'svm': 0.65,
            'neural_network': 0.75,
            'lstm': 0.8,
            'xgboost': 0.85
        }
        return default_performances.get(model_type, 0.5)


class PredictionFusionEngine:
    """预测结果融合引擎"""
    
    def __init__(self, config: FusionConfig = None):
        self.config = config or FusionConfig()
        self.fusion_strategies = {
            FusionMethod.WEIGHTED_AVERAGE: WeightedAverageFusion(self.config),
            FusionMethod.VOTING: VotingFusion(self.config)
        }
        self.fusion_history = []  # 缓存融合历史
    
    def fuse_predictions(self, 
                        predictions: List[ModelPrediction],
                        method: FusionMethod = FusionMethod.WEIGHTED_AVERAGE) -> EnsemblePredictionResult:
        """融合预测结果"""
        try:
            if not predictions:
                logger.warning("没有预测结果可融合")
                return EnsemblePredictionResult(
                    final_prediction=0.0,
                    confidence=0.0,
                    contributing_models=[],
                    fusion_method=method.value,
                    individual_predictions=[],
                    timestamp=datetime.now()
                )
            
            if len(predictions) == 1:
                # 只有一个预测结果，直接返回
                pred = predictions[0]
                return EnsemblePredictionResult(
                    final_prediction=pred.prediction_value,
                    confidence=pred.confidence,
                    contributing_models=[pred.model_type],
                    fusion_method=method.value + "_single",
                    individual_predictions=predictions,
                    timestamp=datetime.now()
                )
            
            # 选择融合策略
            if method in self.fusion_strategies:
                strategy = self.fusion_strategies[method]
                result = strategy.fuse_predictions(predictions)
            else:
                logger.warning(f"未知的融合方法: {method}，使用默认方法")
                result = self.fusion_strategies[FusionMethod.WEIGHTED_AVERAGE].fuse_predictions(predictions)
            
            # 添加到历史记录
            self.fusion_history.append(result)
            
            # 限制历史记录大小
            if len(self.fusion_history) > self.config.max_history_size:
                self.fusion_history.pop(0)
            
            logger.info(f"预测融合完成: 方法={method.value}, "
                       f"模型数量={len(predictions)}, "
                       f"最终预测={result.final_prediction:.4f}, "
                       f"置信度={result.confidence:.3f}")
            
            return result
            
        except Exception as e:
            logger.error(f"预测融合失败: {e}")
            return EnsemblePredictionResult(
                final_prediction=0.0,
                confidence=0.0,
                contributing_models=[],
                fusion_method=method.value + "_error",
                individual_predictions=predictions,
                timestamp=datetime.now(),
                metadata={'error': str(e)}
            )
    
    def add_fusion_strategy(self, method: FusionMethod, strategy):
        """添加新的融合策略"""
        self.fusion_strategies[method] = strategy
        logger.info(f"添加融合策略: {method.value}")
    
    def get_fusion_history(self, limit: int = 10) -> List[EnsemblePredictionResult]:
        """获取融合历史记录"""
        return self.fusion_history[-limit:] if self.fusion_history else []
    
    def get_fusion_statistics(self) -> Dict[str, Any]:
        """获取融合统计信息"""
        if not self.fusion_history:
            return {'total_fusions': 0}
        
        confidences = [result.confidence for result in self.fusion_history]
        method_counts = {}
        
        for result in self.fusion_history:
            method = result.fusion_method
            method_counts[method] = method_counts.get(method, 0) + 1
        
        return {
            'total_fusions': len(self.fusion_history),
            'average_confidence': np.mean(confidences),
            'confidence_std': np.std(confidences),
            'method_distribution': method_counts,
            'latest_fusion': self.fusion_history[-1].timestamp.isoformat() if self.fusion_history else None
        }