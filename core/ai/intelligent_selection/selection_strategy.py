"""
动态选择策略模块

提供多标准决策分析、动态权重调整、约束条件处理和最优模型组合选择功能
"""

import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from .market_detector import MarketState
from .performance_evaluator import ModelPerformance
from .config.model_profiles import ModelType, MarketCondition
from .config.selector_config import SelectionStrategyConfig

class DecisionMethod(Enum):
    """决策方法"""
    AHP = "ahp"  # Analytic Hierarchy Process
    TOPSIS = "topsis"  # Technique for Order Preference by Similarity to Ideal Solution
    SAW = "saw"  # Simple Additive Weighting
    PROMETHEE = "promethee"  # Preference Ranking Organization Method


class ConstraintType(Enum):
    """约束类型"""
    MAX_ACCURACY = "max_accuracy"
    MIN_ACCURACY = "min_accuracy"
    MAX_LATENCY = "max_latency"
    MIN_THROUGHPUT = "min_throughput"
    MAX_MEMORY = "max_memory"
    MAX_MODELS = "max_models"


@dataclass
class SelectionCriteria:
    """选择标准"""
    prediction_type: str
    market_state: Dict[str, Any]
    data_quality: str
    latency_requirement: int  # 毫秒
    accuracy_requirement: float
    available_models: List[str]
    ensemble_size: int = 3


@dataclass
class ModelSelection:
    """模型选择结果"""
    model_type: str
    confidence: float
    weight: float
    selection_reason: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'model_type': self.model_type,
            'confidence': self.confidence,
            'weight': self.weight,
            'selection_reason': self.selection_reason,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class RankedOption:
    """排名选项"""
    option_id: str
    total_score: float
    confidence: float
    rank: int
    criteria_scores: Dict[str, float]


class ConstraintHandler:
    """约束条件处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.constraints = config.get('constraints', {})
    
    def apply_constraints(self, options: List[Dict[str, Any]], 
                         criteria: SelectionCriteria) -> List[Dict[str, Any]]:
        """应用约束条件"""
        try:
            filtered_options = []
            
            for option in options:
                if self._check_constraints(option, criteria):
                    filtered_options.append(option)
            
            logger.debug(f"约束筛选后剩余{len(filtered_options)}个选项")
            return filtered_options
            
        except Exception as e:
            logger.error(f"约束条件处理失败: {e}")
            return options
    
    def _check_constraints(self, option: Dict[str, Any], 
                          criteria: SelectionCriteria) -> bool:
        """检查单个选项是否满足约束条件"""
        
        # 准确性约束
        if 'max_accuracy' in self.constraints:
            if option.get('accuracy_score', 0) > self.constraints['max_accuracy']:
                return False
        
        if 'min_accuracy' in self.constraints:
            if option.get('accuracy_score', 0) < self.constraints['min_accuracy']:
                return False
        
        # 延迟约束
        if 'max_latency' in self.constraints:
            latency = option.get('latency', 0)
            if latency > self.constraints['max_latency']:
                return False
        
        # 吞吐量约束
        if 'min_throughput' in self.constraints:
            throughput = option.get('throughput', 0)
            if throughput < self.constraints['min_throughput']:
                return False
        
        # 内存约束
        if 'max_memory' in self.constraints:
            memory = option.get('memory_usage', 0)
            if memory > self.constraints['max_memory']:
                return False
        
        # 最大模型数量约束
        if len(option.get('model_types', [])) > self.constraints.get('max_models', 5):
            return False
        
        return True


class MultiCriteriaDecisionMatrix:
    """多标准决策矩阵"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.method = DecisionMethod(config.get('method', 'ahp'))
        self.criteria_weights = config.get('criteria_weights', {
            'accuracy': 0.3,
            'speed': 0.25,
            'stability': 0.2,
            'market_fit': 0.15,
            'resource_usage': 0.1
        })
    
    def rank_options(self, options: List[Dict[str, Any]]) -> List[RankedOption]:
        """对选项进行排名"""
        try:
            if not options:
                return []
            
            # 根据选择的方法进行排名
            if self.method == DecisionMethod.AHP:
                return self._ahp_ranking(options)
            elif self.method == DecisionMethod.TOPSIS:
                return self._topsis_ranking(options)
            elif self.method == DecisionMethod.SAW:
                return self._saw_ranking(options)
            else:
                return self._simple_ranking(options)
                
        except Exception as e:
            logger.error(f"多标准决策排名失败: {e}")
            return self._simple_ranking(options)
    
    def _ahp_ranking(self, options: List[Dict[str, Any]]) -> List[RankedOption]:
        """AHP方法排名"""
        if len(options) <= 1:
            return [RankedOption(
                option_id=options[0]['model_type'],
                total_score=options[0].get('composite_score', 0.5),
                confidence=options[0].get('confidence', 0.5),
                rank=1,
                criteria_scores=options[0]
            )] if options else []
        
        # 构建决策矩阵
        criteria_names = list(self.criteria_weights.keys())
        decision_matrix = []
        
        for option in options:
            row = []
            for criterion in criteria_names:
                score = option.get(f'{criterion}_score', 0.5)
                row.append(score)
            decision_matrix.append(row)
        
        decision_matrix = np.array(decision_matrix)
        
        # 标准化矩阵
        normalized_matrix = self._normalize_matrix(decision_matrix)
        
        # 计算加权得分
        weights = np.array(list(self.criteria_weights.values()))
        weighted_scores = np.dot(normalized_matrix, weights)
        
        # 创建排名结果
        ranked_options = []
        for i, option in enumerate(options):
            total_score = weighted_scores[i]
            confidence = option.get('confidence', 0.5)
            
            ranked_option = RankedOption(
                option_id=option['model_type'],
                total_score=total_score,
                confidence=confidence,
                rank=i + 1,
                criteria_scores={criteria_names[j]: normalized_matrix[i][j] 
                               for j in range(len(criteria_names))}
            )
            ranked_options.append(ranked_option)
        
        # 按总分排序
        ranked_options.sort(key=lambda x: x.total_score, reverse=True)
        
        # 更新排名
        for i, option in enumerate(ranked_options):
            option.rank = i + 1
        
        return ranked_options
    
    def _normalize_matrix(self, matrix: np.ndarray) -> np.ndarray:
        """标准化决策矩阵"""
        norms = np.sqrt(np.sum(matrix ** 2, axis=0))
        norms = np.where(norms == 0, 1.0, norms)
        return matrix / norms
    
    def _topsis_ranking(self, options: List[Dict[str, Any]]) -> List[RankedOption]:
        """TOPSIS方法排名"""
        # 简化实现，使用AHP结果
        return self._ahp_ranking(options)
    
    def _saw_ranking(self, options: List[Dict[str, Any]]) -> List[RankedOption]:
        """SAW方法排名"""
        # 简化实现，使用AHP结果
        return self._ahp_ranking(options)
    
    def _simple_ranking(self, options: List[Dict[str, Any]]) -> List[RankedOption]:
        """简单排名"""
        # 按综合得分排序
        sorted_options = sorted(options, 
                              key=lambda x: x.get('composite_score', 0.5), 
                              reverse=True)
        
        ranked_options = []
        for i, option in enumerate(sorted_options):
            ranked_option = RankedOption(
                option_id=option['model_type'],
                total_score=option.get('composite_score', 0.5),
                confidence=option.get('confidence', 0.5),
                rank=i + 1,
                criteria_scores=option
            )
            ranked_options.append(ranked_option)
        
        return ranked_options


class EnsembleBuilder:
    """集成构建器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.method = config.get('method', 'weighted_average')
        self.confidence_threshold = config.get('confidence_threshold', 0.7)
    
    def build_ensemble(self, ranked_options: List[RankedOption], 
                      criteria: SelectionCriteria) -> List[ModelSelection]:
        """构建集成模型"""
        try:
            if not ranked_options:
                return []
            
            # 限制模型数量
            max_models = min(criteria.ensemble_size, len(ranked_options))
            selected_options = ranked_options[:max_models]
            
            selections = []
            for i, option in enumerate(selected_options):
                # 计算权重
                weight = self._calculate_weight(option, selected_options, i)
                
                # 计算置信度
                confidence = option.confidence
                
                selection = ModelSelection(
                    model_type=option.option_id,
                    confidence=confidence,
                    weight=weight,
                    selection_reason=f"基于多标准决策分析排名第{option.rank}位",
                    timestamp=datetime.now()
                )
                selections.append(selection)
            
            # 归一化权重
            self._normalize_weights(selections)
            
            logger.info(f"构建集成模型完成，包含{len(selections)}个模型")
            return selections
            
        except Exception as e:
            logger.error(f"集成构建失败: {e}")
            return []
    
    def _calculate_weight(self, option: RankedOption, 
                         all_options: List[RankedOption], 
                         index: int) -> float:
        """计算模型权重"""
        if self.method == 'weighted_average':
            return self._weighted_average_weight(option, all_options, index)
        elif self.method == 'confidence_weighted':
            return self._confidence_weighted_weight(option)
        elif self.method == 'rank_weighted':
            return self._rank_weighted_weight(option, index)
        else:
            # 平均权重
            return 1.0 / len(all_options)
    
    def _weighted_average_weight(self, option: RankedOption, 
                                all_options: List[RankedOption], 
                                index: int) -> float:
        """加权平均权重"""
        # 结合总分和排名
        score_weight = option.total_score
        rank_weight = 1.0 / (index + 1)  # 排名越高权重越大
        confidence_weight = option.confidence
        
        # 综合权重
        combined_weight = (score_weight * 0.5 + 
                          rank_weight * 0.3 + 
                          confidence_weight * 0.2)
        
        return combined_weight
    
    def _confidence_weighted_weight(self, option: RankedOption) -> float:
        """基于置信度的权重"""
        return option.confidence
    
    def _rank_weighted_weight(self, option: RankedOption, index: int) -> float:
        """基于排名的权重"""
        return 1.0 / (index + 1)
    
    def _normalize_weights(self, selections: List[ModelSelection]):
        """归一化权重"""
        if not selections:
            return
        
        total_weight = sum(s.weight for s in selections)
        if total_weight > 0:
            for selection in selections:
                selection.weight = selection.weight / total_weight


class ModelSelectionStrategy:
    """模型选择策略"""
    
    def __init__(self, config: SelectionStrategyConfig):
        self.config = config
        self.performance_evaluator = None  # 将在外部设置
        
        # 策略配置
        decision_matrix_config = config.decision_matrix if config.decision_matrix else {}
        constraints_config = config.constraints if config.constraints else {}
        ensemble_config = config.ensemble if config.ensemble else {}
        
        self.decision_matrix = MultiCriteriaDecisionMatrix(decision_matrix_config)
        self.constraint_handler = ConstraintHandler(constraints_config)
        self.ensemble_builder = EnsembleBuilder(ensemble_config)
        
        logger.info("模型选择策略初始化完成")
    
    def select_optimal_models(self, criteria: SelectionCriteria) -> List[ModelSelection]:
        """选择最优模型组合"""
        
        try:
            # 1. 获取历史性能数据
            historical_performance = self._get_historical_performance(criteria.available_models)
            
            # 2. 构建决策矩阵
            decision_matrix = self._build_decision_matrix(
                criteria, historical_performance
            )
            
            # 3. 应用约束条件
            constrained_options = self.constraint_handler.apply_constraints(
                decision_matrix, criteria
            )
            
            if not constrained_options:
                logger.warning("应用约束条件后没有可用选项")
                return self._get_fallback_selection(criteria)
            
            # 4. 多标准决策分析
            ranked_options = self.decision_matrix.rank_options(constrained_options)
            
            if not ranked_options:
                logger.warning("多标准决策分析失败")
                return self._get_fallback_selection(criteria)
            
            # 5. 构建最优组合
            optimal_selection = self.ensemble_builder.build_ensemble(
                ranked_options, criteria
            )
            
            if not optimal_selection:
                logger.warning("集成构建失败")
                return self._get_fallback_selection(criteria)
            
            logger.info(f"模型选择完成，选择了{len(optimal_selection)}个模型")
            return optimal_selection
            
        except Exception as e:
            logger.error(f"模型选择失败: {e}")
            return self._get_fallback_selection(criteria)
    
    def _get_historical_performance(self, available_models: List[str]) -> Dict[str, ModelPerformance]:
        """获取历史性能数据"""
        if not self.performance_evaluator:
            return {}
        
        performance_data = {}
        for model_type in available_models:
            try:
                summary = self.performance_evaluator.get_performance_summary(model_type)
                if summary.get('available', False):
                    # 创建模拟的ModelPerformance对象
                    performance_data[model_type] = ModelPerformance(
                        model_type=model_type,
                        metrics=self._create_default_metrics(),
                        composite_score=summary['composite_score']['current'],
                        reliability_score=summary['reliability']['current'],
                        sample_size=summary['sample_size']['recent'],
                        evaluation_timestamp=datetime.now()
                    )
            except Exception as e:
                logger.warning(f"获取{model_type}性能数据失败: {e}")
        
        return performance_data
    
    def _create_default_metrics(self):
        """创建默认指标"""
        from .performance_evaluator import ModelMetrics
        return ModelMetrics(
            accuracy=0.6,
            precision=0.6,
            recall=0.6,
            f1_score=0.6,
            mape=0.4,
            sharpe_ratio=0.0,
            timestamp=datetime.now()
        )
    
    def _build_decision_matrix(self,
                             criteria: SelectionCriteria,
                             performance_data: Dict[str, ModelPerformance]) -> List[Dict[str, Any]]:
        """构建决策矩阵"""
        
        matrix = []
        
        for model_type in criteria.available_models:
            if model_type in performance_data:
                performance = performance_data[model_type]
                
                # 计算各项评分
                accuracy_score = self._normalize_score(performance.metrics.accuracy)
                speed_score = self._calculate_speed_score(model_type, criteria)
                stability_score = performance.reliability_score
                market_fit_score = self._calculate_market_fit_score(
                    model_type, criteria.market_state
                )
                resource_score = self._calculate_resource_score(model_type)
                
                decision_option = {
                    'model_type': model_type,
                    'accuracy_score': accuracy_score,
                    'speed_score': speed_score,
                    'stability_score': stability_score,
                    'market_fit_score': market_fit_score,
                    'resource_usage_score': resource_score,
                    'composite_score': performance.composite_score,
                    'confidence': performance.reliability_score,
                    'latency': self._estimate_latency(model_type),
                    'throughput': self._estimate_throughput(model_type),
                    'memory_usage': self._estimate_memory_usage(model_type)
                }
                
                matrix.append(decision_option)
        
        return matrix
    
    def _normalize_score(self, score: float) -> float:
        """标准化评分"""
        return max(0, min(1, score))
    
    def _calculate_speed_score(self, model_type: str, criteria: SelectionCriteria) -> float:
        """计算速度评分"""
        # 基于模型类型和延迟要求的评分
        latency = self._estimate_latency(model_type)
        
        if criteria.latency_requirement <= 0:
            return 1.0
        
        speed_ratio = criteria.latency_requirement / max(latency, 1)
        return min(1.0, speed_ratio)
    
    def _calculate_market_fit_score(self, model_type: str, market_state: Dict[str, Any]) -> float:
        """计算市场适应性评分"""
        try:
            # 基于市场状态评估模型适应性
            volatility_level = market_state.get('volatility', {}).get('level', 'normal')
            trend_strength = market_state.get('trend_strength', {}).get('level', 'normal')
            market_regime = market_state.get('market_regime', {}).get('regime', 'stable')
            
            fit_score = 0.5  # 基准分数
            
            # 根据模型类型和市场状态调整分数
            if model_type == 'lstm':
                if volatility_level == 'high' or trend_strength == 'strong':
                    fit_score = 0.8
                elif volatility_level == 'low':
                    fit_score = 0.6
            elif model_type == 'xgboost':
                if market_regime == 'volatile':
                    fit_score = 0.9
                elif volatility_level == 'normal':
                    fit_score = 0.8
            elif model_type == 'linear_regression':
                if market_regime == 'stable':
                    fit_score = 0.8
                elif volatility_level == 'low':
                    fit_score = 0.7
            
            return fit_score
            
        except Exception as e:
            logger.error(f"市场适应性评分计算失败: {e}")
            return 0.5
    
    def _calculate_resource_score(self, model_type: str) -> float:
        """计算资源使用评分"""
        memory_usage = self._estimate_memory_usage(model_type)
        max_reasonable_memory = 1024  # MB
        
        if memory_usage <= 0:
            return 1.0
        
        resource_ratio = max_reasonable_memory / memory_usage
        return min(1.0, resource_ratio)
    
    def _estimate_latency(self, model_type: str) -> int:
        """估算模型延迟（毫秒）"""
        latencies = {
            'linear_regression': 10,
            'random_forest': 50,
            'xgboost': 100,
            'gru': 200,
            'lstm': 500,
            'ensemble': 800
        }
        return latencies.get(model_type, 300)
    
    def _estimate_throughput(self, model_type: str) -> int:
        """估算模型吞吐量（每秒预测次数）"""
        throughputs = {
            'linear_regression': 1000,
            'random_forest': 200,
            'xgboost': 100,
            'gru': 50,
            'lstm': 20,
            'ensemble': 10
        }
        return throughputs.get(model_type, 50)
    
    def _estimate_memory_usage(self, model_type: str) -> int:
        """估算内存使用（MB）"""
        memory_usage = {
            'linear_regression': 8,
            'random_forest': 32,
            'xgboost': 64,
            'gru': 128,
            'lstm': 256,
            'ensemble': 512
        }
        return memory_usage.get(model_type, 128)
    
    def _get_fallback_selection(self, criteria: SelectionCriteria) -> List[ModelSelection]:
        """获取后备选择"""
        # 选择最简单的模型作为后备
        fallback_models = ['linear_regression', 'random_forest']
        
        selections = []
        for i, model_type in enumerate(fallback_models[:criteria.ensemble_size]):
            weight = 1.0 / min(len(fallback_models), criteria.ensemble_size)
            
            selection = ModelSelection(
                model_type=model_type,
                confidence=0.5,
                weight=weight,
                selection_reason="后备模型选择",
                timestamp=datetime.now()
            )
            selections.append(selection)
        
        return selections