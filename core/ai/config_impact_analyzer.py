#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置变更影响分析器

分析配置变更对系统性能和稳定性的潜在影响：
1. 配置变更影响预测和评估
2. 风险识别和等级评估
3. 变更建议和回滚策略
4. 配置依赖关系分析
5. 变更时机优化建议
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import threading
from pathlib import Path
from loguru import logger
import warnings
warnings.filterwarnings('ignore')

from ..database.unified_sqlite_access import UnifiedSQLiteAccess
from ..importdata.import_config_manager import ImportTaskConfig, DataFrequency, ImportMode

class ImpactSeverity(Enum):
    """影响严重程度"""
    MINIMAL = "minimal"        # 最小影响
    LOW = "low"               # 低影响
    MEDIUM = "medium"         # 中等影响
    HIGH = "high"             # 高影响
    CRITICAL = "critical"     # 严重影响

class RiskCategory(Enum):
    """风险类别"""
    PERFORMANCE = "performance"           # 性能风险
    STABILITY = "stability"              # 稳定性风险
    RESOURCE = "resource"                # 资源风险
    DATA_QUALITY = "data_quality"        # 数据质量风险
    OPERATIONAL = "operational"          # 运营风险
    SECURITY = "security"                # 安全风险

class ChangeType(Enum):
    """变更类型"""
    PARAMETER_INCREASE = "parameter_increase"    # 参数增加
    PARAMETER_DECREASE = "parameter_decrease"    # 参数减少
    CONFIGURATION_ADD = "configuration_add"     # 配置新增
    CONFIGURATION_REMOVE = "configuration_remove" # 配置移除
    STRATEGY_CHANGE = "strategy_change"         # 策略变更
    DEPENDENCY_CHANGE = "dependency_change"     # 依赖变更

@dataclass
class ConfigChange:
    """配置变更"""
    change_id: str
    change_type: ChangeType
    parameter_name: str
    old_value: Any
    new_value: Any
    change_ratio: float = 0.0  # 变更比例
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class ImpactPrediction:
    """影响预测"""
    metric_name: str
    current_value: float
    predicted_value: float
    change_percentage: float
    confidence: float
    impact_severity: ImpactSeverity

@dataclass
class RiskAssessment:
    """风险评估"""
    risk_id: str
    risk_category: RiskCategory
    risk_description: str
    probability: float  # 风险发生概率
    impact_score: float  # 影响分数
    risk_level: ImpactSeverity
    mitigation_strategies: List[str] = field(default_factory=list)

@dataclass
class ConfigImpactAnalysis:
    """配置影响分析结果"""
    analysis_id: str
    original_config: Dict[str, Any]
    target_config: Dict[str, Any]
    changes: List[ConfigChange]
    impact_predictions: List[ImpactPrediction]
    risk_assessments: List[RiskAssessment]
    overall_risk_score: float
    overall_impact_severity: ImpactSeverity
    recommendations: List[str]
    rollback_strategy: Dict[str, Any]
    optimal_change_time: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

class ConfigImpactAnalyzer:
    """
    配置变更影响分析器
    
    分析配置变更对系统的潜在影响，提供风险评估和变更建议
    """

    def __init__(self, db_path: str = "data/factorweave_system.sqlite"):
        self.db_path = db_path
        self._db_instance = UnifiedSQLiteAccess.get_instance(self.db_path)
        
        # 历史数据缓存
        self.historical_performance: Optional[pd.DataFrame] = None
        self.historical_changes: List[Dict[str, Any]] = []
        
        # 影响模型参数
        self.impact_models: Dict[str, Dict[str, float]] = {}
        self.risk_thresholds: Dict[str, Dict[str, float]] = {}
        
        # 依赖关系图
        self.dependency_graph: Dict[str, Set[str]] = {}
        
        # 分析缓存
        self.analysis_cache: Dict[str, ConfigImpactAnalysis] = {}
        self.cache_ttl: int = 1800  # 30分钟缓存
        
        # 线程锁
        self._analysis_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        
        # 初始化
        self._init_impact_models()
        self._init_risk_thresholds()
        self._load_historical_data()
        self._build_dependency_graph()
        
        logger.info("配置变更影响分析器初始化完成")

    def _init_impact_models(self):
        """初始化影响模型"""
        try:
            # 性能影响模型参数
            self.impact_models['performance'] = {
                'max_workers_coefficient': 0.15,      # 工作线程数对性能的影响系数
                'batch_size_coefficient': 0.08,       # 批次大小对性能的影响系数
                'memory_threshold': 0.8,               # 内存使用阈值
                'cpu_threshold': 0.9,                  # CPU使用阈值
                'network_latency_factor': 0.05,       # 网络延迟影响因子
                'concurrency_efficiency': 0.7         # 并发效率系数
            }
            
            # 稳定性影响模型参数
            self.impact_models['stability'] = {
                'error_rate_base': 0.02,               # 基础错误率
                'overload_threshold': 0.85,            # 过载阈值
                'resource_contention_factor': 0.12,   # 资源竞争影响因子
                'failure_cascade_probability': 0.3,   # 故障级联概率
                'recovery_time_factor': 1.5            # 恢复时间因子
            }
            
            # 资源影响模型参数
            self.impact_models['resource'] = {
                'memory_per_worker': 256,              # 每个工作线程内存使用(MB)
                'memory_per_batch_item': 0.1,          # 每个批次项内存使用(MB)
                'cpu_per_worker': 0.1,                 # 每个工作线程CPU使用
                'network_bandwidth_per_worker': 10,   # 每个工作线程网络带宽(MB/s)
                'disk_io_factor': 0.05                 # 磁盘IO影响因子
            }
            
            logger.info("影响模型初始化完成")
            
        except Exception as e:
            logger.error(f"初始化影响模型失败: {e}")

    def _init_risk_thresholds(self):
        """初始化风险阈值"""
        try:
            # 性能风险阈值
            self.risk_thresholds['performance'] = {
                'execution_time_increase': {
                    'low': 0.1,      # 10%增加为低风险
                    'medium': 0.25,  # 25%增加为中等风险
                    'high': 0.5,     # 50%增加为高风险
                    'critical': 1.0  # 100%增加为严重风险
                },
                'throughput_decrease': {
                    'low': 0.1,
                    'medium': 0.2,
                    'high': 0.4,
                    'critical': 0.6
                },
                'success_rate_decrease': {
                    'low': 0.02,
                    'medium': 0.05,
                    'high': 0.1,
                    'critical': 0.2
                }
            }
            
            # 稳定性风险阈值
            self.risk_thresholds['stability'] = {
                'error_rate_increase': {
                    'low': 0.01,
                    'medium': 0.03,
                    'high': 0.08,
                    'critical': 0.15
                },
                'failure_probability': {
                    'low': 0.05,
                    'medium': 0.1,
                    'high': 0.2,
                    'critical': 0.4
                }
            }
            
            # 资源风险阈值
            self.risk_thresholds['resource'] = {
                'memory_utilization': {
                    'low': 0.7,
                    'medium': 0.8,
                    'high': 0.9,
                    'critical': 0.95
                },
                'cpu_utilization': {
                    'low': 0.7,
                    'medium': 0.8,
                    'high': 0.9,
                    'critical': 0.95
                }
            }
            
            logger.info("风险阈值初始化完成")
            
        except Exception as e:
            logger.error(f"初始化风险阈值失败: {e}")

    def _load_historical_data(self):
        """加载历史数据"""
        try:
            with self._db_instance.get_connection() as conn:
                # 加载历史性能数据
                performance_query = """
                    SELECT 
                        config_hash,
                        performance_data,
                        execution_time,
                        success_rate,
                        error_rate,
                        throughput,
                        created_at
                    FROM config_performance_history
                    WHERE created_at >= datetime('now', '-30 days')
                    ORDER BY created_at DESC
                """
                
                self.historical_performance = pd.read_sql_query(performance_query, conn)
                
                # 加载历史配置变更数据
                try:
                    change_query = """
                        SELECT 
                            config_id,
                            optimization_type,
                            original_config,
                            optimized_config,
                            performance_improvement,
                            success,
                            created_at
                        FROM auto_optimization_logs
                        WHERE created_at >= datetime('now', '-30 days')
                        ORDER BY created_at DESC
                    """
                    
                    change_df = pd.read_sql_query(change_query, conn)
                    self.historical_changes = change_df.to_dict('records')
                    
                except Exception:
                    # 表不存在时的处理
                    self.historical_changes = []
                
                logger.info(f"加载历史数据: 性能记录{len(self.historical_performance)}条, 变更记录{len(self.historical_changes)}条")
                
        except Exception as e:
            logger.error(f"加载历史数据失败: {e}")
            self.historical_performance = pd.DataFrame()
            self.historical_changes = []

    def _build_dependency_graph(self):
        """构建配置依赖关系图"""
        try:
            # 定义配置参数之间的依赖关系
            self.dependency_graph = {
                'max_workers': {'batch_size', 'memory_usage', 'cpu_usage'},
                'batch_size': {'memory_usage', 'network_bandwidth', 'processing_time'},
                'data_source': {'network_latency', 'rate_limit', 'connection_pool'},
                'frequency': {'data_volume', 'update_interval'},
                'symbols_count': {'memory_usage', 'processing_time', 'network_requests'},
                'timeout': {'network_latency', 'retry_count'},
                'retry_count': {'error_rate', 'total_time'}
            }
            
            logger.info(f"构建依赖关系图: {len(self.dependency_graph)}个节点")
            
        except Exception as e:
            logger.error(f"构建依赖关系图失败: {e}")
            self.dependency_graph = {}

    def analyze_config_change_impact(self,
                                   original_config: ImportTaskConfig,
                                   target_config: ImportTaskConfig,
                                   context: Optional[Dict[str, Any]] = None) -> ConfigImpactAnalysis:
        """
        分析配置变更影响
        
        Args:
            original_config: 原始配置
            target_config: 目标配置
            context: 上下文信息
            
        Returns:
            配置影响分析结果
        """
        try:
            # 检查缓存
            cache_key = self._generate_cache_key(original_config, target_config)
            
            with self._cache_lock:
                if cache_key in self.analysis_cache:
                    cached_analysis = self.analysis_cache[cache_key]
                    cache_time = datetime.fromisoformat(cached_analysis.created_at)
                    if (datetime.now() - cache_time).seconds < self.cache_ttl:
                        logger.info("返回缓存的影响分析结果")
                        return cached_analysis
            
            with self._analysis_lock:
                # 生成分析ID
                analysis_id = f"impact_analysis_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # 识别配置变更
                changes = self._identify_config_changes(original_config, target_config)
                
                # 预测影响
                impact_predictions = self._predict_impacts(original_config, target_config, changes, context)
                
                # 评估风险
                risk_assessments = self._assess_risks(changes, impact_predictions, context)
                
                # 计算整体风险分数
                overall_risk_score = self._calculate_overall_risk_score(risk_assessments)
                overall_impact_severity = self._determine_overall_severity(risk_assessments)
                
                # 生成建议
                recommendations = self._generate_recommendations(changes, risk_assessments, context)
                
                # 制定回滚策略
                rollback_strategy = self._create_rollback_strategy(original_config, target_config, changes)
                
                # 确定最佳变更时机
                optimal_change_time = self._determine_optimal_change_time(risk_assessments, context)
                
                # 分析依赖关系
                dependencies = self._analyze_dependencies(changes)
                
                # 创建分析结果
                analysis = ConfigImpactAnalysis(
                    analysis_id=analysis_id,
                    original_config=original_config.to_dict(),
                    target_config=target_config.to_dict(),
                    changes=changes,
                    impact_predictions=impact_predictions,
                    risk_assessments=risk_assessments,
                    overall_risk_score=overall_risk_score,
                    overall_impact_severity=overall_impact_severity,
                    recommendations=recommendations,
                    rollback_strategy=rollback_strategy,
                    optimal_change_time=optimal_change_time,
                    dependencies=dependencies
                )
                
                # 缓存结果
                with self._cache_lock:
                    self.analysis_cache[cache_key] = analysis
                
                logger.info(f"配置变更影响分析完成: {analysis_id}, 整体风险分数: {overall_risk_score:.3f}")
                return analysis
                
        except Exception as e:
            logger.error(f"分析配置变更影响失败: {e}")
            return self._create_fallback_analysis(original_config, target_config)

    def _identify_config_changes(self, original: ImportTaskConfig, target: ImportTaskConfig) -> List[ConfigChange]:
        """识别配置变更"""
        changes = []
        change_counter = 0
        
        try:
            # 比较关键配置参数
            config_params = {
                'max_workers': (original.max_workers, target.max_workers),
                'batch_size': (original.batch_size, target.batch_size),
                'data_source': (original.data_source, target.data_source),
                'asset_type': (original.asset_type, target.asset_type),
                'frequency': (original.frequency.value, target.frequency.value),
                'symbols_count': (len(original.symbols), len(target.symbols)),
                'mode': (original.mode.value, target.mode.value)
            }
            
            for param_name, (old_val, new_val) in config_params.items():
                if old_val != new_val:
                    change_counter += 1
                    
                    # 确定变更类型
                    if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
                        if new_val > old_val:
                            change_type = ChangeType.PARAMETER_INCREASE
                            change_ratio = (new_val - old_val) / old_val if old_val != 0 else 1.0
                        else:
                            change_type = ChangeType.PARAMETER_DECREASE
                            change_ratio = (old_val - new_val) / old_val if old_val != 0 else 1.0
                    else:
                        change_type = ChangeType.STRATEGY_CHANGE
                        change_ratio = 1.0  # 策略变更视为100%变更
                    
                    # 生成变更描述
                    description = f"{param_name}从{old_val}变更为{new_val}"
                    
                    change = ConfigChange(
                        change_id=f"change_{change_counter:03d}",
                        change_type=change_type,
                        parameter_name=param_name,
                        old_value=old_val,
                        new_value=new_val,
                        change_ratio=change_ratio,
                        description=description
                    )
                    
                    changes.append(change)
            
            logger.info(f"识别配置变更: {len(changes)}项")
            return changes
            
        except Exception as e:
            logger.error(f"识别配置变更失败: {e}")
            return []

    def _predict_impacts(self,
                        original: ImportTaskConfig,
                        target: ImportTaskConfig,
                        changes: List[ConfigChange],
                        context: Optional[Dict[str, Any]]) -> List[ImpactPrediction]:
        """预测配置变更影响"""
        predictions = []
        
        try:
            # 获取当前性能基线
            baseline_performance = self._get_performance_baseline(original, context)
            
            # 预测各项性能指标的变化
            metrics_to_predict = [
                'execution_time',
                'success_rate',
                'error_rate',
                'throughput',
                'cpu_utilization',
                'memory_utilization'
            ]
            
            for metric in metrics_to_predict:
                current_value = baseline_performance.get(metric, 0.0)
                predicted_value = self._predict_metric_change(metric, changes, current_value, context)
                
                if current_value != 0:
                    change_percentage = (predicted_value - current_value) / current_value
                else:
                    change_percentage = 0.0
                
                # 计算预测置信度
                confidence = self._calculate_prediction_confidence(metric, changes, context)
                
                # 确定影响严重程度
                impact_severity = self._determine_impact_severity(metric, change_percentage)
                
                prediction = ImpactPrediction(
                    metric_name=metric,
                    current_value=current_value,
                    predicted_value=predicted_value,
                    change_percentage=change_percentage,
                    confidence=confidence,
                    impact_severity=impact_severity
                )
                
                predictions.append(prediction)
            
            logger.info(f"生成影响预测: {len(predictions)}项")
            return predictions
            
        except Exception as e:
            logger.error(f"预测配置影响失败: {e}")
            return []

    def _get_performance_baseline(self, config: ImportTaskConfig, context: Optional[Dict[str, Any]]) -> Dict[str, float]:
        """获取性能基线"""
        try:
            logger.debug(f"获取性能基线: data_source={getattr(config, 'data_source', 'unknown')}")
            # 从历史数据中查找相似配置的性能
            if self.historical_performance is not None and not self.historical_performance.empty:
                # 筛选相似配置
                similar_configs = self.historical_performance[
                    (self.historical_performance['performance_data'].str.contains(config.data_source, na=False)) &
                    (self.historical_performance['performance_data'].str.contains(config.asset_type, na=False))
                ]
                
                if not similar_configs.empty:
                    return {
                        'execution_time': similar_configs['execution_time'].median(),
                        'success_rate': similar_configs['success_rate'].median(),
                        'error_rate': similar_configs['error_rate'].median(),
                        'throughput': similar_configs['throughput'].median(),
                        'cpu_utilization': 0.5,  # 默认值
                        'memory_utilization': 0.4  # 默认值
                    }
            
            # 使用默认基线
            return {
                'execution_time': 60.0,
                'success_rate': 0.9,
                'error_rate': 0.1,
                'throughput': 1000.0,
                'cpu_utilization': 0.5,
                'memory_utilization': 0.4
            }
            
        except Exception as e:
            logger.error(f"获取性能基线失败: {e}")
            return {
                'execution_time': 60.0,
                'success_rate': 0.9,
                'error_rate': 0.1,
                'throughput': 1000.0,
                'cpu_utilization': 0.5,
                'memory_utilization': 0.4
            }

    def _predict_metric_change(self,
                              metric: str,
                              changes: List[ConfigChange],
                              current_value: float,
                              context: Optional[Dict[str, Any]]) -> float:
        """预测单个指标的变化"""
        try:
            predicted_value = current_value
            
            for change in changes:
                impact_factor = self._calculate_change_impact_factor(metric, change, context)
                
                if change.change_type == ChangeType.PARAMETER_INCREASE:
                    if metric in ['execution_time', 'error_rate', 'cpu_utilization', 'memory_utilization']:
                        # 这些指标可能随参数增加而增加
                        predicted_value *= (1 + impact_factor * change.change_ratio)
                    elif metric in ['success_rate', 'throughput']:
                        # 这些指标可能随参数增加而改善（但有上限）
                        improvement = impact_factor * change.change_ratio
                        if metric == 'success_rate':
                            predicted_value = min(1.0, predicted_value * (1 + improvement))
                        else:
                            predicted_value *= (1 + improvement)
                
                elif change.change_type == ChangeType.PARAMETER_DECREASE:
                    if metric in ['execution_time', 'error_rate', 'cpu_utilization', 'memory_utilization']:
                        # 这些指标可能随参数减少而减少
                        predicted_value *= (1 - impact_factor * change.change_ratio)
                    elif metric in ['success_rate', 'throughput']:
                        # 这些指标可能随参数减少而恶化
                        degradation = impact_factor * change.change_ratio
                        predicted_value *= (1 - degradation)
                        if metric == 'success_rate':
                            predicted_value = max(0.0, predicted_value)
            
            # 应用合理性约束
            predicted_value = self._apply_metric_constraints(metric, predicted_value)
            
            return predicted_value
            
        except Exception as e:
            logger.error(f"预测指标变化失败 {metric}: {e}")
            return current_value

    def _calculate_change_impact_factor(self,
                                       metric: str,
                                       change: ConfigChange,
                                       context: Optional[Dict[str, Any]]) -> float:
        """计算变更对指标的影响因子"""
        try:
            param_name = change.parameter_name
            
            # 基于影响模型计算影响因子
            if metric == 'execution_time':
                if param_name == 'max_workers':
                    return self.impact_models['performance']['max_workers_coefficient']
                elif param_name == 'batch_size':
                    return self.impact_models['performance']['batch_size_coefficient']
                elif param_name == 'symbols_count':
                    return 0.1  # 数据量对执行时间的影响
            
            elif metric == 'success_rate':
                if param_name == 'max_workers':
                    return 0.05  # 并发对成功率的影响
                elif param_name == 'batch_size':
                    return 0.03  # 批次大小对成功率的影响
            
            elif metric == 'error_rate':
                if param_name == 'max_workers':
                    return 0.08  # 高并发可能增加错误率
                elif param_name == 'batch_size':
                    return 0.04  # 大批次可能增加错误率
            
            elif metric == 'throughput':
                if param_name == 'max_workers':
                    return 0.2   # 并发对吞吐量的显著影响
                elif param_name == 'batch_size':
                    return 0.15  # 批次大小对吞吐量的影响
            
            elif metric == 'cpu_utilization':
                if param_name == 'max_workers':
                    return 0.25  # 工作线程数对CPU使用的直接影响
                elif param_name == 'batch_size':
                    return 0.05  # 批次大小对CPU使用的间接影响
            
            elif metric == 'memory_utilization':
                if param_name == 'max_workers':
                    return 0.1   # 工作线程数对内存使用的影响
                elif param_name == 'batch_size':
                    return 0.2   # 批次大小对内存使用的显著影响
            
            # 默认影响因子
            return 0.05
            
        except Exception as e:
            logger.error(f"计算影响因子失败: {e}")
            return 0.05

    def _apply_metric_constraints(self, metric: str, value: float) -> float:
        """应用指标约束"""
        try:
            if metric == 'success_rate':
                return max(0.0, min(1.0, value))
            elif metric == 'error_rate':
                return max(0.0, min(1.0, value))
            elif metric == 'execution_time':
                return max(1.0, value)  # 执行时间至少1秒
            elif metric == 'throughput':
                return max(0.0, value)
            elif metric in ['cpu_utilization', 'memory_utilization']:
                return max(0.0, min(1.0, value))
            else:
                return max(0.0, value)
                
        except Exception as e:
            logger.error(f"应用指标约束失败: {e}")
            return value

    def _calculate_prediction_confidence(self,
                                        metric: str,
                                        changes: List[ConfigChange],
                                        context: Optional[Dict[str, Any]]) -> float:
        """计算预测置信度"""
        try:
            confidence_factors = []
            
            # 基于历史数据的置信度
            if self.historical_performance is not None and not self.historical_performance.empty:
                data_confidence = min(1.0, len(self.historical_performance) / 50)
                confidence_factors.append(data_confidence)
            else:
                confidence_factors.append(0.3)
            
            # 基于变更复杂度的置信度
            complexity_confidence = max(0.3, 1.0 - len(changes) * 0.1)
            confidence_factors.append(complexity_confidence)
            
            # 基于参数类型的置信度
            param_confidence = 0.8  # 数值参数的预测置信度较高
            for change in changes:
                if change.change_type == ChangeType.STRATEGY_CHANGE:
                    param_confidence *= 0.7  # 策略变更的预测置信度较低
            confidence_factors.append(param_confidence)
            
            # 综合置信度
            overall_confidence = np.mean(confidence_factors)
            return max(0.1, min(1.0, overall_confidence))
            
        except Exception as e:
            logger.error(f"计算预测置信度失败: {e}")
            return 0.5

    def _determine_impact_severity(self, metric: str, change_percentage: float) -> ImpactSeverity:
        """确定影响严重程度"""
        try:
            abs_change = abs(change_percentage)
            
            # 根据指标类型和变化幅度确定严重程度
            if metric in ['execution_time', 'error_rate']:
                # 对于这些指标，增加是负面影响
                if change_percentage > 0:  # 增加
                    if abs_change < 0.1:
                        return ImpactSeverity.LOW
                    elif abs_change < 0.25:
                        return ImpactSeverity.MEDIUM
                    elif abs_change < 0.5:
                        return ImpactSeverity.HIGH
                    else:
                        return ImpactSeverity.CRITICAL
                else:  # 减少是正面影响
                    return ImpactSeverity.MINIMAL
            
            elif metric in ['success_rate', 'throughput']:
                # 对于这些指标，减少是负面影响
                if change_percentage < 0:  # 减少
                    if abs_change < 0.05:
                        return ImpactSeverity.LOW
                    elif abs_change < 0.15:
                        return ImpactSeverity.MEDIUM
                    elif abs_change < 0.3:
                        return ImpactSeverity.HIGH
                    else:
                        return ImpactSeverity.CRITICAL
                else:  # 增加是正面影响
                    return ImpactSeverity.MINIMAL
            
            else:
                # 其他指标的通用判断
                if abs_change < 0.1:
                    return ImpactSeverity.MINIMAL
                elif abs_change < 0.2:
                    return ImpactSeverity.LOW
                elif abs_change < 0.4:
                    return ImpactSeverity.MEDIUM
                elif abs_change < 0.7:
                    return ImpactSeverity.HIGH
                else:
                    return ImpactSeverity.CRITICAL
                    
        except Exception as e:
            logger.error(f"确定影响严重程度失败: {e}")
            return ImpactSeverity.MEDIUM

    def _assess_risks(self,
                     changes: List[ConfigChange],
                     predictions: List[ImpactPrediction],
                     context: Optional[Dict[str, Any]]) -> List[RiskAssessment]:
        """评估风险"""
        risk_assessments = []
        risk_counter = 0
        
        try:
            # 基于预测结果评估风险
            for prediction in predictions:
                if prediction.impact_severity in [ImpactSeverity.HIGH, ImpactSeverity.CRITICAL]:
                    risk_counter += 1
                    
                    # 确定风险类别
                    if prediction.metric_name in ['execution_time', 'throughput']:
                        risk_category = RiskCategory.PERFORMANCE
                    elif prediction.metric_name in ['success_rate', 'error_rate']:
                        risk_category = RiskCategory.STABILITY
                    elif prediction.metric_name in ['cpu_utilization', 'memory_utilization']:
                        risk_category = RiskCategory.RESOURCE
                    else:
                        risk_category = RiskCategory.OPERATIONAL
                    
                    # 计算风险概率和影响分数
                    probability = self._calculate_risk_probability(prediction, changes, context)
                    impact_score = self._calculate_impact_score(prediction)
                    
                    # 确定风险等级
                    risk_level = prediction.impact_severity
                    
                    # 生成风险描述
                    risk_description = self._generate_risk_description(prediction, changes)
                    
                    # 生成缓解策略
                    mitigation_strategies = self._generate_mitigation_strategies(prediction, changes)
                    
                    risk_assessment = RiskAssessment(
                        risk_id=f"risk_{risk_counter:03d}",
                        risk_category=risk_category,
                        risk_description=risk_description,
                        probability=probability,
                        impact_score=impact_score,
                        risk_level=risk_level,
                        mitigation_strategies=mitigation_strategies
                    )
                    
                    risk_assessments.append(risk_assessment)
            
            # 评估配置变更特定的风险
            config_risks = self._assess_config_specific_risks(changes, context)
            risk_assessments.extend(config_risks)
            
            logger.info(f"风险评估完成: {len(risk_assessments)}项风险")
            return risk_assessments
            
        except Exception as e:
            logger.error(f"评估风险失败: {e}")
            return []

    def _calculate_risk_probability(self,
                                   prediction: ImpactPrediction,
                                   changes: List[ConfigChange],
                                   context: Optional[Dict[str, Any]]) -> float:
        """计算风险发生概率"""
        try:
            base_probability = 0.1  # 基础概率
            
            # 基于预测置信度调整概率
            confidence_factor = prediction.confidence
            probability = base_probability + (1 - confidence_factor) * 0.3
            
            # 基于变更幅度调整概率
            for change in changes:
                if change.change_ratio > 0.5:  # 大幅变更
                    probability += 0.2
                elif change.change_ratio > 0.2:  # 中等变更
                    probability += 0.1
            
            # 基于历史经验调整概率
            if self.historical_changes:
                similar_changes = [c for c in self.historical_changes if not c.get('success', True)]
                if similar_changes:
                    failure_rate = len(similar_changes) / len(self.historical_changes)
                    probability += failure_rate * 0.3
            
            return max(0.01, min(1.0, probability))
            
        except Exception as e:
            logger.error(f"计算风险概率失败: {e}")
            return 0.3

    def _calculate_impact_score(self, prediction: ImpactPrediction) -> float:
        """计算影响分数"""
        try:
            # 基于影响严重程度的分数
            severity_scores = {
                ImpactSeverity.MINIMAL: 0.1,
                ImpactSeverity.LOW: 0.3,
                ImpactSeverity.MEDIUM: 0.5,
                ImpactSeverity.HIGH: 0.8,
                ImpactSeverity.CRITICAL: 1.0
            }
            
            base_score = severity_scores.get(prediction.impact_severity, 0.5)
            
            # 基于变化幅度调整分数
            change_magnitude = abs(prediction.change_percentage)
            magnitude_factor = min(1.0, change_magnitude)
            
            impact_score = base_score * (0.7 + 0.3 * magnitude_factor)
            
            return max(0.0, min(1.0, impact_score))
            
        except Exception as e:
            logger.error(f"计算影响分数失败: {e}")
            return 0.5

    def _generate_risk_description(self, prediction: ImpactPrediction, changes: List[ConfigChange]) -> str:
        """生成风险描述"""
        try:
            metric_name = prediction.metric_name
            change_pct = prediction.change_percentage * 100
            
            # 指标中文名称映射
            metric_names = {
                'execution_time': '执行时间',
                'success_rate': '成功率',
                'error_rate': '错误率',
                'throughput': '吞吐量',
                'cpu_utilization': 'CPU使用率',
                'memory_utilization': '内存使用率'
            }
            
            metric_cn = metric_names.get(metric_name, metric_name)
            
            if change_pct > 0:
                direction = "增加"
            else:
                direction = "减少"
                change_pct = abs(change_pct)
            
            description = f"配置变更可能导致{metric_cn}{direction}{change_pct:.1f}%"
            
            # 添加相关变更信息
            relevant_changes = [c for c in changes if c.parameter_name in ['max_workers', 'batch_size']]
            if relevant_changes:
                change_desc = ", ".join([f"{c.parameter_name}变更{c.change_ratio*100:.1f}%" for c in relevant_changes])
                description += f"，主要由于{change_desc}"
            
            return description
            
        except Exception as e:
            logger.error(f"生成风险描述失败: {e}")
            return "配置变更存在潜在风险"

    def _generate_mitigation_strategies(self, prediction: ImpactPrediction, changes: List[ConfigChange]) -> List[str]:
        """生成缓解策略"""
        try:
            strategies = []
            
            metric_name = prediction.metric_name
            
            if metric_name == 'execution_time' and prediction.change_percentage > 0:
                strategies.extend([
                    "考虑分阶段实施变更，逐步调整参数",
                    "在低峰时段进行变更以减少影响",
                    "准备回滚方案，监控执行时间变化",
                    "考虑优化其他参数以补偿性能损失"
                ])
            
            elif metric_name == 'success_rate' and prediction.change_percentage < 0:
                strategies.extend([
                    "增加监控和告警，及时发现问题",
                    "准备降级方案，确保服务可用性",
                    "考虑增加重试机制和容错处理",
                    "在测试环境充分验证后再实施"
                ])
            
            elif metric_name == 'error_rate' and prediction.change_percentage > 0:
                strategies.extend([
                    "加强错误监控和日志记录",
                    "准备快速回滚机制",
                    "考虑降低变更幅度，分步实施",
                    "增加健康检查和自动恢复机制"
                ])
            
            elif metric_name in ['cpu_utilization', 'memory_utilization'] and prediction.change_percentage > 0:
                strategies.extend([
                    "监控系统资源使用情况",
                    "准备资源扩容方案",
                    "考虑在资源充足时进行变更",
                    "设置资源使用告警阈值"
                ])
            
            # 通用缓解策略
            if prediction.impact_severity in [ImpactSeverity.HIGH, ImpactSeverity.CRITICAL]:
                strategies.extend([
                    "建议在维护窗口期间进行变更",
                    "准备完整的回滚计划和程序",
                    "进行充分的测试和验证",
                    "通知相关团队和用户"
                ])
            
            return strategies[:5]  # 限制策略数量
            
        except Exception as e:
            logger.error(f"生成缓解策略失败: {e}")
            return ["建议谨慎实施变更，做好监控和回滚准备"]

    def _assess_config_specific_risks(self, changes: List[ConfigChange], context: Optional[Dict[str, Any]]) -> List[RiskAssessment]:
        """评估配置特定风险"""
        risks = []
        risk_counter = len([c for c in changes if c.change_type in [ChangeType.PARAMETER_INCREASE, ChangeType.PARAMETER_DECREASE]])
        
        try:
            # 检查资源过载风险
            worker_changes = [c for c in changes if c.parameter_name == 'max_workers' and c.change_type == ChangeType.PARAMETER_INCREASE]
            if worker_changes:
                for change in worker_changes:
                    if change.new_value > 8:  # 高并发风险
                        risk_counter += 1
                        risk = RiskAssessment(
                            risk_id=f"risk_{risk_counter:03d}",
                            risk_category=RiskCategory.RESOURCE,
                            risk_description=f"工作线程数增加到{change.new_value}可能导致资源竞争和系统过载",
                            probability=0.6,
                            impact_score=0.7,
                            risk_level=ImpactSeverity.HIGH,
                            mitigation_strategies=[
                                "监控系统资源使用情况",
                                "考虑分批增加工作线程数",
                                "准备资源扩容方案",
                                "设置资源使用告警"
                            ]
                        )
                        risks.append(risk)
            
            # 检查内存不足风险
            batch_changes = [c for c in changes if c.parameter_name == 'batch_size' and c.change_type == ChangeType.PARAMETER_INCREASE]
            if batch_changes:
                for change in batch_changes:
                    if change.new_value > 3000:  # 大批次风险
                        risk_counter += 1
                        risk = RiskAssessment(
                            risk_id=f"risk_{risk_counter:03d}",
                            risk_category=RiskCategory.RESOURCE,
                            risk_description=f"批次大小增加到{change.new_value}可能导致内存不足",
                            probability=0.5,
                            impact_score=0.6,
                            risk_level=ImpactSeverity.MEDIUM,
                            mitigation_strategies=[
                                "监控内存使用情况",
                                "考虑分阶段增加批次大小",
                                "准备内存扩容方案",
                                "优化内存使用效率"
                            ]
                        )
                        risks.append(risk)
            
            # 检查配置不匹配风险
            worker_increase = any(c.parameter_name == 'max_workers' and c.change_type == ChangeType.PARAMETER_INCREASE for c in changes)
            batch_decrease = any(c.parameter_name == 'batch_size' and c.change_type == ChangeType.PARAMETER_DECREASE for c in changes)
            
            if worker_increase and batch_decrease:
                risk_counter += 1
                risk = RiskAssessment(
                    risk_id=f"risk_{risk_counter:03d}",
                    risk_category=RiskCategory.PERFORMANCE,
                    risk_description="同时增加工作线程数和减少批次大小可能导致性能不匹配",
                    probability=0.4,
                    impact_score=0.5,
                    risk_level=ImpactSeverity.MEDIUM,
                    mitigation_strategies=[
                        "重新评估参数配置的匹配性",
                        "考虑保持参数比例平衡",
                        "进行性能测试验证",
                        "监控整体性能指标"
                    ]
                )
                risks.append(risk)
            
            return risks
            
        except Exception as e:
            logger.error(f"评估配置特定风险失败: {e}")
            return []

    def _calculate_overall_risk_score(self, risk_assessments: List[RiskAssessment]) -> float:
        """计算整体风险分数"""
        try:
            if not risk_assessments:
                return 0.0
            
            # 计算加权风险分数
            total_weighted_score = 0.0
            total_weight = 0.0
            
            for risk in risk_assessments:
                # 风险权重基于概率和影响分数
                weight = risk.probability * risk.impact_score
                weighted_score = weight * self._get_severity_score(risk.risk_level)
                
                total_weighted_score += weighted_score
                total_weight += weight
            
            if total_weight > 0:
                overall_score = total_weighted_score / total_weight
            else:
                overall_score = 0.0
            
            return max(0.0, min(1.0, overall_score))
            
        except Exception as e:
            logger.error(f"计算整体风险分数失败: {e}")
            return 0.5

    def _get_severity_score(self, severity: ImpactSeverity) -> float:
        """获取严重程度分数"""
        severity_scores = {
            ImpactSeverity.MINIMAL: 0.1,
            ImpactSeverity.LOW: 0.3,
            ImpactSeverity.MEDIUM: 0.5,
            ImpactSeverity.HIGH: 0.8,
            ImpactSeverity.CRITICAL: 1.0
        }
        return severity_scores.get(severity, 0.5)

    def _determine_overall_severity(self, risk_assessments: List[RiskAssessment]) -> ImpactSeverity:
        """确定整体影响严重程度"""
        try:
            if not risk_assessments:
                return ImpactSeverity.MINIMAL
            
            # 取最高风险等级
            max_severity = ImpactSeverity.MINIMAL
            severity_order = [
                ImpactSeverity.MINIMAL,
                ImpactSeverity.LOW,
                ImpactSeverity.MEDIUM,
                ImpactSeverity.HIGH,
                ImpactSeverity.CRITICAL
            ]
            
            for risk in risk_assessments:
                if severity_order.index(risk.risk_level) > severity_order.index(max_severity):
                    max_severity = risk.risk_level
            
            return max_severity
            
        except Exception as e:
            logger.error(f"确定整体严重程度失败: {e}")
            return ImpactSeverity.MEDIUM

    def _generate_recommendations(self,
                                 changes: List[ConfigChange],
                                 risk_assessments: List[RiskAssessment],
                                 context: Optional[Dict[str, Any]]) -> List[str]:
        """生成变更建议"""
        try:
            recommendations = []
            
            # 基于风险等级生成建议
            high_risks = [r for r in risk_assessments if r.risk_level in [ImpactSeverity.HIGH, ImpactSeverity.CRITICAL]]
            
            if high_risks:
                recommendations.append("检测到高风险变更，建议：")
                recommendations.append("1. 在测试环境充分验证变更效果")
                recommendations.append("2. 选择低峰时段进行变更")
                recommendations.append("3. 准备完整的回滚计划")
                recommendations.append("4. 加强监控和告警")
            
            # 基于变更类型生成建议
            large_changes = [c for c in changes if c.change_ratio > 0.5]
            if large_changes:
                recommendations.append("检测到大幅度参数变更，建议分阶段实施")
            
            multiple_changes = len(changes) > 3
            if multiple_changes:
                recommendations.append("同时变更多个参数，建议逐个验证变更效果")
            
            # 基于配置组合生成建议
            worker_changes = [c for c in changes if c.parameter_name == 'max_workers']
            batch_changes = [c for c in changes if c.parameter_name == 'batch_size']
            
            if worker_changes and batch_changes:
                recommendations.append("同时调整并发和批次参数，建议保持合理比例")
            
            # 通用建议
            if not recommendations:
                recommendations.append("变更风险较低，建议正常实施")
            
            recommendations.append("建议在变更后持续监控系统性能指标")
            
            return recommendations[:8]  # 限制建议数量
            
        except Exception as e:
            logger.error(f"生成变更建议失败: {e}")
            return ["建议谨慎实施配置变更"]

    def _create_rollback_strategy(self,
                                 original: ImportTaskConfig,
                                 target: ImportTaskConfig,
                                 changes: List[ConfigChange]) -> Dict[str, Any]:
        """创建回滚策略"""
        try:
            rollback_strategy = {
                'rollback_config': original.to_dict(),
                'rollback_steps': [],
                'rollback_triggers': [],
                'rollback_time_estimate': 0,
                'validation_checks': []
            }
            
            # 生成回滚步骤
            for change in changes:
                step = f"将{change.parameter_name}从{change.new_value}回滚到{change.old_value}"
                rollback_strategy['rollback_steps'].append(step)
            
            # 定义回滚触发条件
            rollback_strategy['rollback_triggers'] = [
                "执行时间增加超过50%",
                "错误率超过20%",
                "成功率低于80%",
                "系统资源使用率超过90%",
                "出现严重错误或异常"
            ]
            
            # 估算回滚时间
            rollback_strategy['rollback_time_estimate'] = len(changes) * 2  # 每个变更2分钟
            
            # 定义验证检查
            rollback_strategy['validation_checks'] = [
                "验证配置参数已正确回滚",
                "检查系统性能指标恢复正常",
                "确认无遗留错误或异常",
                "验证数据完整性",
                "确认服务可用性"
            ]
            
            return rollback_strategy
            
        except Exception as e:
            logger.error(f"创建回滚策略失败: {e}")
            return {
                'rollback_config': original.to_dict(),
                'rollback_steps': ["恢复原始配置"],
                'rollback_triggers': ["出现严重问题时"],
                'rollback_time_estimate': 5,
                'validation_checks': ["验证系统恢复正常"]
            }

    def _determine_optimal_change_time(self, risk_assessments: List[RiskAssessment], context: Optional[Dict[str, Any]]) -> Optional[str]:
        """确定最佳变更时机"""
        try:
            high_risk_count = len([r for r in risk_assessments if r.risk_level in [ImpactSeverity.HIGH, ImpactSeverity.CRITICAL]])
            
            if high_risk_count == 0:
                return "任何时间（低风险变更）"
            elif high_risk_count <= 2:
                return "建议在低峰时段（如凌晨2-6点）进行"
            else:
                return "建议在维护窗口期间进行，并通知相关团队"
                
        except Exception as e:
            logger.error(f"确定最佳变更时机失败: {e}")
            return "建议在低峰时段进行"

    def _analyze_dependencies(self, changes: List[ConfigChange]) -> List[str]:
        """分析配置依赖关系"""
        try:
            dependencies = []
            
            for change in changes:
                param_name = change.parameter_name
                if param_name in self.dependency_graph:
                    dependent_params = self.dependency_graph[param_name]
                    for dep_param in dependent_params:
                        dependency_desc = f"{param_name}变更可能影响{dep_param}"
                        if dependency_desc not in dependencies:
                            dependencies.append(dependency_desc)
            
            return dependencies
            
        except Exception as e:
            logger.error(f"分析配置依赖关系失败: {e}")
            return []

    def _create_fallback_analysis(self, original: ImportTaskConfig, target: ImportTaskConfig) -> ConfigImpactAnalysis:
        """创建回退分析结果"""
        try:
            analysis_id = f"fallback_analysis_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # 简单的变更识别
            changes = []
            if original.max_workers != target.max_workers:
                changes.append(ConfigChange(
                    change_id="change_001",
                    change_type=ChangeType.PARAMETER_INCREASE if target.max_workers > original.max_workers else ChangeType.PARAMETER_DECREASE,
                    parameter_name="max_workers",
                    old_value=original.max_workers,
                    new_value=target.max_workers,
                    description=f"工作线程数从{original.max_workers}变更为{target.max_workers}"
                ))
            
            if original.batch_size != target.batch_size:
                changes.append(ConfigChange(
                    change_id="change_002",
                    change_type=ChangeType.PARAMETER_INCREASE if target.batch_size > original.batch_size else ChangeType.PARAMETER_DECREASE,
                    parameter_name="batch_size",
                    old_value=original.batch_size,
                    new_value=target.batch_size,
                    description=f"批次大小从{original.batch_size}变更为{target.batch_size}"
                ))
            
            # 基础风险评估
            risk_assessment = RiskAssessment(
                risk_id="risk_001",
                risk_category=RiskCategory.OPERATIONAL,
                risk_description="配置变更存在不确定性风险",
                probability=0.3,
                impact_score=0.5,
                risk_level=ImpactSeverity.MEDIUM,
                mitigation_strategies=["建议在测试环境验证", "准备回滚方案", "加强监控"]
            )
            
            return ConfigImpactAnalysis(
                analysis_id=analysis_id,
                original_config=original.to_dict(),
                target_config=target.to_dict(),
                changes=changes,
                impact_predictions=[],
                risk_assessments=[risk_assessment],
                overall_risk_score=0.5,
                overall_impact_severity=ImpactSeverity.MEDIUM,
                recommendations=["建议谨慎实施配置变更", "做好监控和回滚准备"],
                rollback_strategy={
                    'rollback_config': original.to_dict(),
                    'rollback_steps': ["恢复原始配置"],
                    'rollback_triggers': ["出现问题时立即回滚"],
                    'rollback_time_estimate': 5,
                    'validation_checks': ["验证系统恢复正常"]
                },
                optimal_change_time="建议在低峰时段进行",
                dependencies=[]
            )
            
        except Exception as e:
            logger.error(f"创建回退分析失败: {e}")
            # 返回最基础的分析结果
            return ConfigImpactAnalysis(
                analysis_id="fallback_basic",
                original_config={},
                target_config={},
                changes=[],
                impact_predictions=[],
                risk_assessments=[],
                overall_risk_score=0.5,
                overall_impact_severity=ImpactSeverity.MEDIUM,
                recommendations=["建议谨慎实施变更"],
                rollback_strategy={'rollback_config': {}},
                dependencies=[]
            )

    def _generate_cache_key(self, original: ImportTaskConfig, target: ImportTaskConfig) -> str:
        """生成缓存键"""
        import hashlib
        
        key_data = {
            'original': {
                'max_workers': original.max_workers,
                'batch_size': original.batch_size,
                'data_source': original.data_source,
                'asset_type': original.asset_type,
                'frequency': original.frequency.value
            },
            'target': {
                'max_workers': target.max_workers,
                'batch_size': target.batch_size,
                'data_source': target.data_source,
                'asset_type': target.asset_type,
                'frequency': target.frequency.value
            }
        }
        
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get_analysis_summary(self, analysis: ConfigImpactAnalysis) -> Dict[str, Any]:
        """获取分析摘要"""
        try:
            summary = {
                'analysis_id': analysis.analysis_id,
                'total_changes': len(analysis.changes),
                'high_risk_count': len([r for r in analysis.risk_assessments if r.risk_level in [ImpactSeverity.HIGH, ImpactSeverity.CRITICAL]]),
                'overall_risk_score': analysis.overall_risk_score,
                'overall_impact_severity': analysis.overall_impact_severity.value,
                'key_recommendations': analysis.recommendations[:3],
                'rollback_time_estimate': analysis.rollback_strategy.get('rollback_time_estimate', 0),
                'optimal_change_time': analysis.optimal_change_time,
                'created_at': analysis.created_at
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"获取分析摘要失败: {e}")
            return {'error': str(e)}

    def clear_cache(self):
        """清空分析缓存"""
        with self._cache_lock:
            self.analysis_cache.clear()
        logger.info("影响分析缓存已清空")

def main():
    """测试配置变更影响分析器"""
    from ..importdata.import_config_manager import DataFrequency, ImportMode
    
    # 创建影响分析器
    analyzer = ConfigImpactAnalyzer()
    
    # 创建原始配置
    original_config = ImportTaskConfig(
        task_id="impact_test_001",
        name="影响分析测试",
        data_source="tongdaxin",
        asset_type="stock",
        data_type="kline",
        symbols=["000001", "000002", "000858"],
        frequency=DataFrequency.DAILY,
        mode=ImportMode.BATCH,
        max_workers=4,
        batch_size=1000
    )
    
    # 创建目标配置（进行一些变更）
    target_config = ImportTaskConfig(
        task_id="impact_test_001",
        name="影响分析测试",
        data_source="tongdaxin",
        asset_type="stock",
        data_type="kline",
        symbols=["000001", "000002", "000858", "000300", "000016"],  # 增加股票
        frequency=DataFrequency.DAILY,
        mode=ImportMode.BATCH,
        max_workers=8,    # 增加工作线程
        batch_size=2000   # 增加批次大小
    )
    
    # 进行影响分析
    logger.info("=== 开始配置变更影响分析 ===")
    analysis = analyzer.analyze_config_change_impact(original_config, target_config)
    
    # 输出分析结果
    logger.info(f"分析ID: {analysis.analysis_id}")
    logger.info(f"配置变更数量: {len(analysis.changes)}")
    
    for change in analysis.changes:
        logger.info(f"变更: {change.description} (变更比例: {change.change_ratio:.2f})")
    
    logger.info(f"影响预测数量: {len(analysis.impact_predictions)}")
    for prediction in analysis.impact_predictions:
        logger.info(f"预测: {prediction.metric_name} 从 {prediction.current_value:.3f} 变为 {prediction.predicted_value:.3f} "
                   f"(变化: {prediction.change_percentage:.1%}, 置信度: {prediction.confidence:.3f}, "
                   f"严重程度: {prediction.impact_severity.value})")
    
    logger.info(f"风险评估数量: {len(analysis.risk_assessments)}")
    for risk in analysis.risk_assessments:
        logger.info(f"风险: {risk.risk_description} "
                   f"(类别: {risk.risk_category.value}, 概率: {risk.probability:.3f}, "
                   f"影响: {risk.impact_score:.3f}, 等级: {risk.risk_level.value})")
    
    logger.info(f"整体风险分数: {analysis.overall_risk_score:.3f}")
    logger.info(f"整体影响严重程度: {analysis.overall_impact_severity.value}")
    
    logger.info("变更建议:")
    for i, rec in enumerate(analysis.recommendations, 1):
        logger.info(f"{i}. {rec}")
    
    logger.info(f"最佳变更时机: {analysis.optimal_change_time}")
    
    logger.info("回滚策略:")
    logger.info(f"  回滚步骤数: {len(analysis.rollback_strategy['rollback_steps'])}")
    logger.info(f"  预计回滚时间: {analysis.rollback_strategy['rollback_time_estimate']}分钟")
    
    if analysis.dependencies:
        logger.info("依赖关系:")
        for dep in analysis.dependencies:
            logger.info(f"  {dep}")
    
    # 获取分析摘要
    logger.info("\n=== 分析摘要 ===")
    summary = analyzer.get_analysis_summary(analysis)
    for key, value in summary.items():
        logger.info(f"{key}: {value}")
    
    # 测试不同类型的变更
    logger.info("\n=== 测试减少参数的变更 ===")
    reduced_config = ImportTaskConfig(
        task_id="impact_test_002",
        name="减少参数测试",
        data_source="tongdaxin",
        asset_type="stock",
        data_type="kline",
        symbols=["000001"],  # 减少股票数量
        frequency=DataFrequency.DAILY,
        mode=ImportMode.BATCH,
        max_workers=2,    # 减少工作线程
        batch_size=500    # 减少批次大小
    )
    
    reduced_analysis = analyzer.analyze_config_change_impact(original_config, reduced_config)
    logger.info(f"减少参数变更的整体风险分数: {reduced_analysis.overall_risk_score:.3f}")
    logger.info(f"减少参数变更的影响严重程度: {reduced_analysis.overall_impact_severity.value}")

if __name__ == "__main__":
    main()
