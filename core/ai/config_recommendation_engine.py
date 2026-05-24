#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
基于历史数据的配置推荐引擎

基于历史性能数据和机器学习算法，为数据导入任务提供智能配置推荐：
1. 历史数据分析和模式识别
2. 配置效果预测和优化建议
3. 多维度配置优化策略
4. 配置推荐置信度评估
5. 动态配置调优建议
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import sqlite3
import threading
from pathlib import Path
from loguru import logger
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import warnings
from ..database.unified_sqlite_access import UnifiedSQLiteAccess
warnings.filterwarnings('ignore')

from ..importdata.import_config_manager import ImportTaskConfig, DataFrequency, ImportMode
from ..services.ai_prediction_service import AIPredictionService

class RecommendationStrategy(Enum):
    """推荐策略类型"""
    PERFORMANCE_FIRST = "performance_first"    # 性能优先
    STABILITY_FIRST = "stability_first"        # 稳定性优先
    RESOURCE_EFFICIENT = "resource_efficient"  # 资源效率优先
    BALANCED = "balanced"                       # 平衡策略
    CONSERVATIVE = "conservative"               # 保守策略
    AGGRESSIVE = "aggressive"                   # 激进策略

class OptimizationObjective(Enum):
    """优化目标"""
    MINIMIZE_TIME = "minimize_time"             # 最小化执行时间
    MAXIMIZE_THROUGHPUT = "maximize_throughput" # 最大化吞吐量
    MINIMIZE_ERROR_RATE = "minimize_error_rate" # 最小化错误率
    MAXIMIZE_SUCCESS_RATE = "maximize_success_rate" # 最大化成功率
    MINIMIZE_RESOURCE_USAGE = "minimize_resource_usage" # 最小化资源使用

@dataclass
class ConfigRecommendation:
    """配置推荐结果"""
    recommended_config: Dict[str, Any]
    confidence_score: float
    expected_performance: Dict[str, float]
    optimization_rationale: str
    alternative_configs: List[Dict[str, Any]] = field(default_factory=list)
    risk_assessment: Dict[str, float] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class PerformanceFeatures:
    """性能特征"""
    data_source: str
    asset_type: str
    frequency: str
    symbols_count: int
    max_workers: int
    batch_size: int
    cpu_cores: int
    memory_gb: float
    network_latency: float
    data_volume_mb: float
    time_of_day: int
    is_business_hours: bool

@dataclass
class PerformanceTarget:
    """性能目标"""
    execution_time: float
    success_rate: float
    error_rate: float
    throughput: float
    cpu_utilization: float
    memory_utilization: float

class ConfigRecommendationEngine:
    """
    基于历史数据的配置推荐引擎
    
    使用机器学习算法分析历史性能数据，为数据导入任务提供智能配置推荐
    """

    def __init__(self, db_path: str = "data/factorweave_system.sqlite", model_cache_dir: str = "cache/ml_models"):
        self.db_path = db_path
        self.model_cache_dir = Path(model_cache_dir)
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)

        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        self.label_encoders: Dict[str, LabelEncoder] = {}
        
        self.historical_data: Optional[pd.DataFrame] = None
        self.feature_importance: Dict[str, Dict[str, float]] = {}
        
        self.recommendation_cache: Dict[str, ConfigRecommendation] = {}
        self.cache_ttl: int = 3600
        
        self._model_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        
        self._init_models()
        self._load_historical_data()
        
        logger.info("配置推荐引擎初始化完成")

    def _get_db(self) -> UnifiedSQLiteAccess:
        return UnifiedSQLiteAccess.get_instance(self.db_path)

    def _init_models(self):
        """初始化机器学习模型"""
        try:
            # 执行时间预测模型
            self.models['execution_time'] = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            )
            
            # 成功率预测模型
            self.models['success_rate'] = RandomForestRegressor(
                n_estimators=100,
                max_depth=8,
                random_state=42
            )
            
            # 错误率预测模型
            self.models['error_rate'] = GradientBoostingRegressor(
                n_estimators=80,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
            
            # 吞吐量预测模型
            self.models['throughput'] = RandomForestRegressor(
                n_estimators=120,
                max_depth=10,
                random_state=42
            )
            
            # 资源利用率预测模型
            self.models['cpu_utilization'] = RandomForestRegressor(
                n_estimators=80,
                max_depth=6,
                random_state=42
            )
            
            self.models['memory_utilization'] = RandomForestRegressor(
                n_estimators=80,
                max_depth=6,
                random_state=42
            )
            
            # 初始化标准化器和编码器
            for target in self.models.keys():
                self.scalers[target] = StandardScaler()
            
            self.label_encoders = {
                'data_source': LabelEncoder(),
                'asset_type': LabelEncoder(),
                'frequency': LabelEncoder()
            }
            
            logger.info(f"初始化 {len(self.models)} 个机器学习模型")
            
        except Exception as e:
            logger.error(f"初始化机器学习模型失败: {e}")

    def _load_historical_data(self):
        """加载历史性能数据"""
        try:
            db = self._get_db()
            with db.get_connection() as conn:
                # 加载配置性能历史数据
                query = """
                    SELECT 
                        config_hash,
                        performance_data,
                        execution_time,
                        success_rate,
                        error_rate,
                        throughput,
                        created_at
                    FROM config_performance_history
                    WHERE created_at >= datetime('now', '-90 days')
                    ORDER BY created_at DESC
                """
                
                self.historical_data = pd.read_sql_query(query, conn)
                
                if len(self.historical_data) > 0:
                    # 解析性能数据JSON
                    perf_json = self.historical_data['performance_data'].apply(
                        lambda x: json.loads(x) if isinstance(x, str) else x
                    )
                    perf_df = pd.json_normalize(perf_json)
                    valid_mask = perf_json.notna()
                    if valid_mask.any():
                        perf_df = perf_df[valid_mask].reset_index(drop=True)
                        perf_cols = ['execution_time', 'success_rate', 'error_rate', 'throughput', 'created_at']
                        extra = self.historical_data.loc[valid_mask, perf_cols].reset_index(drop=True)
                        self.historical_data = pd.concat([perf_df, extra], axis=1)
                        logger.info(f"加载历史性能数据: {len(self.historical_data)} 条记录")
                        self._train_models()
                    else:
                        logger.warning("历史性能数据解析失败")
                        self.historical_data = pd.DataFrame()
                else:
                    logger.warning("未找到历史性能数据")
                    self.historical_data = pd.DataFrame()
                    
        except Exception as e:
            logger.error(f"加载历史性能数据失败: {e}")
            self.historical_data = pd.DataFrame()

    def _prepare_features(self, data: pd.DataFrame) -> Tuple[np.ndarray, Dict[str, Any]]:
        """准备机器学习特征"""
        try:
            # 基础特征
            features = []
            feature_names = []
            
            # 数值特征
            numeric_features = ['max_workers', 'batch_size', 'symbols_count']
            for feature in numeric_features:
                if feature in data.columns:
                    features.append(data[feature].fillna(0).values.reshape(-1, 1))
                    feature_names.append(feature)
            
            # 分类特征编码
            categorical_features = ['data_source', 'asset_type', 'frequency']
            for feature in categorical_features:
                if feature in data.columns:
                    if feature not in self.label_encoders:
                        self.label_encoders[feature] = LabelEncoder()
                    
                    # 处理未见过的类别
                    unique_values = data[feature].dropna().unique()
                    try:
                        encoded_values = self.label_encoders[feature].transform(data[feature].fillna('unknown'))
                    except ValueError:
                        # 处理新类别
                        all_classes = list(self.label_encoders[feature].classes_) + list(unique_values)
                        self.label_encoders[feature].fit(all_classes)
                        encoded_values = self.label_encoders[feature].transform(data[feature].fillna('unknown'))
                    
                    features.append(encoded_values.reshape(-1, 1))
                    feature_names.append(feature)
            
            # 时间特征
            if 'created_at' in data.columns:
                timestamps = pd.to_datetime(data['created_at'])
                hour_of_day = timestamps.dt.hour.values.reshape(-1, 1)
                day_of_week = timestamps.dt.dayofweek.values.reshape(-1, 1)
                is_business_hours = ((timestamps.dt.hour >= 9) & (timestamps.dt.hour <= 17)).astype(int).values.reshape(-1, 1)
                
                features.extend([hour_of_day, day_of_week, is_business_hours])
                feature_names.extend(['hour_of_day', 'day_of_week', 'is_business_hours'])
            
            # 组合特征
            if len(features) >= 2:
                # 工作线程与批次大小的比例
                if 'max_workers' in feature_names and 'batch_size' in feature_names:
                    worker_idx = feature_names.index('max_workers')
                    batch_idx = feature_names.index('batch_size')
                    worker_batch_ratio = (features[worker_idx] / (features[batch_idx] + 1)).reshape(-1, 1)
                    features.append(worker_batch_ratio)
                    feature_names.append('worker_batch_ratio')
            
            if features:
                X = np.hstack(features)
                feature_info = {
                    'feature_names': feature_names,
                    'n_features': X.shape[1]
                }
                return X, feature_info
            else:
                return np.array([]).reshape(0, 0), {'feature_names': [], 'n_features': 0}
                
        except Exception as e:
            logger.error(f"准备机器学习特征失败: {e}")
            return np.array([]).reshape(0, 0), {'feature_names': [], 'n_features': 0}

    def _train_models(self):
        """训练机器学习模型"""
        if self.historical_data is None or (hasattr(self.historical_data, 'empty') and self.historical_data.empty):
            logger.warning("历史数据为空，无法训练模型，将使用回退推荐")
            return
        
        with self._model_lock:
            try:
                logger.info("开始训练配置推荐模型...")
                
                # 准备特征
                X, feature_info = self._prepare_features(self.historical_data)
                
                if X.shape[0] < 10:
                    logger.warning("历史数据不足，无法训练可靠的模型")
                    return
                
                # 训练各个目标的预测模型
                targets = ['execution_time', 'success_rate', 'error_rate', 'throughput']
                
                for target in targets:
                    if target not in self.historical_data.columns:
                        continue
                    
                    try:
                        y = self.historical_data[target].fillna(0).values
                        
                        # 过滤异常值
                        valid_indices = ~np.isnan(y) & ~np.isinf(y)
                        if target in ['success_rate', 'error_rate']:
                            valid_indices &= (y >= 0) & (y <= 1)
                        elif target == 'execution_time':
                            valid_indices &= (y > 0) & (y < 3600)  # 小于1小时
                        elif target == 'throughput':
                            valid_indices &= (y > 0) & (y < 100000)  # 合理的吞吐量范围
                        
                        X_valid = X[valid_indices]
                        y_valid = y[valid_indices]
                        
                        if len(y_valid) < 5:
                            logger.warning(f"目标 {target} 的有效数据不足")
                            continue
                        
                        # 标准化特征
                        X_scaled = self.scalers[target].fit_transform(X_valid)
                        
                        # 训练模型
                        if target in self.models:
                            if self.models[target] is not None:
                                self.models[target].fit(X_scaled, y_valid)
                            else:
                                logger.warning(f"模型 {target} 未初始化，跳过训练")
                            
                            # 计算特征重要性
                            if hasattr(self.models[target], 'feature_importances_'):
                                importances = self.models[target].feature_importances_
                                self.feature_importance[target] = dict(zip(
                                    feature_info['feature_names'][:len(importances)],
                                    importances
                                ))
                            
                            # 交叉验证评估
                            if len(y_valid) >= 10:
                                cv_scores = cross_val_score(
                                    self.models[target], X_scaled, y_valid, 
                                    cv=min(5, len(y_valid)//2), scoring='r2'
                                )
                                logger.info(f"模型 {target} 交叉验证 R² 分数: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
                        
                    except Exception as e:
                        logger.error(f"训练模型 {target} 失败: {e}")
                
                # 保存模型
                self._save_models()
                
                logger.info("配置推荐模型训练完成")
                
            except Exception as e:
                logger.error(f"训练机器学习模型失败: {e}")

    def _save_models(self):
        """保存训练好的模型"""
        try:
            model_file = self.model_cache_dir / "config_recommendation_models.pkl"
            
            model_data = {
                'models': self.models,
                'scalers': self.scalers,
                'label_encoders': self.label_encoders,
                'feature_importance': self.feature_importance,
                'trained_at': datetime.now().isoformat()
            }
            
            joblib.dump(model_data, model_file)
            logger.info(f"模型保存到: {model_file}")
            
        except Exception as e:
            logger.error(f"保存模型失败: {e}")

    def _load_models(self) -> bool:
        """加载已训练的模型"""
        try:
            model_file = self.model_cache_dir / "config_recommendation_models.pkl"
            
            if not model_file.exists():
                return False
            
            model_data = joblib.load(model_file)
            
            self.models = model_data.get('models', {})
            self.scalers = model_data.get('scalers', {})
            self.label_encoders = model_data.get('label_encoders', {})
            self.feature_importance = model_data.get('feature_importance', {})
            
            trained_at = model_data.get('trained_at')
            if trained_at:
                trained_time = datetime.fromisoformat(trained_at)
                if (datetime.now() - trained_time).days > 7:  # 模型超过7天，需要重新训练
                    logger.info("模型已过期，将重新训练")
                    return False
            
            logger.info(f"加载已训练的模型: {len(self.models)} 个")
            return True
            
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return False

    def recommend_config(self,
                        base_config: ImportTaskConfig,
                        strategy: RecommendationStrategy = RecommendationStrategy.BALANCED,
                        objective: OptimizationObjective = OptimizationObjective.MAXIMIZE_SUCCESS_RATE,
                        constraints: Optional[Dict[str, Any]] = None) -> ConfigRecommendation:
        """
        推荐配置
        
        Args:
            base_config: 基础配置
            strategy: 推荐策略
            objective: 优化目标
            constraints: 约束条件
            
        Returns:
            配置推荐结果
        """
        try:
            # 检查缓存
            cache_key = self._generate_cache_key(base_config, strategy, objective, constraints)
            
            with self._cache_lock:
                if cache_key in self.recommendation_cache:
                    cached_rec = self.recommendation_cache[cache_key]
                    cache_time = datetime.fromisoformat(cached_rec.created_at)
                    if (datetime.now() - cache_time).seconds < self.cache_ttl:
                        logger.info("返回缓存的配置推荐")
                        return cached_rec
            
            # 生成推荐
            recommendation = self._generate_recommendation(base_config, strategy, objective, constraints)
            
            # 缓存结果
            with self._cache_lock:
                self.recommendation_cache[cache_key] = recommendation
            
            logger.info(f"生成配置推荐完成，置信度: {recommendation.confidence_score:.3f}")
            return recommendation
            
        except Exception as e:
            logger.error(f"推荐配置失败: {e}")
            # 返回基础推荐
            return self._generate_fallback_recommendation(base_config)

    def _generate_recommendation(self,
                                base_config: ImportTaskConfig,
                                strategy: RecommendationStrategy,
                                objective: OptimizationObjective,
                                constraints: Optional[Dict[str, Any]]) -> ConfigRecommendation:
        """生成配置推荐"""
        try:
            # 定义搜索空间
            search_space = self._define_search_space(base_config, constraints)
            
            # 生成候选配置
            candidate_configs = self._generate_candidate_configs(base_config, search_space, strategy)
            
            # 预测性能
            performance_predictions = []
            for config in candidate_configs:
                prediction = self._predict_performance(config)
                performance_predictions.append(prediction)
            
            # 根据目标选择最佳配置
            best_config, best_performance = self._select_best_config(
                candidate_configs, performance_predictions, objective
            )
            
            # 计算置信度
            confidence_score = self._calculate_confidence(best_config, best_performance)
            
            # 生成优化理由
            rationale = self._generate_rationale(base_config, best_config, best_performance, strategy, objective)
            
            # 风险评估
            risk_assessment = self._assess_risks(best_config, best_performance)
            
            # 生成备选配置
            alternative_configs = self._generate_alternatives(
                candidate_configs, performance_predictions, best_config, 3
            )
            
            return ConfigRecommendation(
                recommended_config=best_config,
                confidence_score=confidence_score,
                expected_performance=best_performance,
                optimization_rationale=rationale,
                alternative_configs=alternative_configs,
                risk_assessment=risk_assessment
            )
            
        except Exception as e:
            logger.error(f"生成配置推荐失败: {e}")
            return self._generate_fallback_recommendation(base_config)

    def _define_search_space(self, base_config: ImportTaskConfig, constraints: Optional[Dict[str, Any]]) -> Dict[str, List[int]]:
        """定义配置搜索空间"""
        # 默认搜索空间
        search_space = {
            'max_workers': list(range(1, 17)),  # 1-16个工作线程
            'batch_size': [100, 200, 500, 1000, 1500, 2000, 3000, 5000]  # 常用批次大小
        }
        
        # 应用约束
        if constraints:
            if 'max_workers_range' in constraints:
                min_w, max_w = constraints['max_workers_range']
                search_space['max_workers'] = list(range(min_w, max_w + 1))
            
            if 'batch_size_range' in constraints:
                min_b, max_b = constraints['batch_size_range']
                search_space['batch_size'] = [b for b in search_space['batch_size'] if min_b <= b <= max_b]
        
        # 基于系统资源调整搜索空间
        try:
            import psutil
            cpu_count = psutil.cpu_count()
            memory_gb = psutil.virtual_memory().total / (1024**3)
            
            # 限制最大工作线程数
            search_space['max_workers'] = [w for w in search_space['max_workers'] if w <= cpu_count * 2]
            
            # 基于内存限制批次大小
            if memory_gb < 8:
                search_space['batch_size'] = [b for b in search_space['batch_size'] if b <= 2000]
            elif memory_gb < 16:
                search_space['batch_size'] = [b for b in search_space['batch_size'] if b <= 3000]
        except Exception as e:
            logger.debug(f"内存检查失败，使用默认搜索空间: {e}")
        
        return search_space

    def _generate_candidate_configs(self,
                                   base_config: ImportTaskConfig,
                                   search_space: Dict[str, List[int]],
                                   strategy: RecommendationStrategy) -> List[Dict[str, Any]]:
        """生成候选配置"""
        candidates = []
        
        # 基础配置特征
        base_features = {
            'data_source': base_config.data_source,
            'asset_type': base_config.asset_type,
            'frequency': base_config.frequency.value,
            'symbols_count': len(base_config.symbols)
        }
        
        # 根据策略调整搜索范围
        if strategy == RecommendationStrategy.CONSERVATIVE:
            # 保守策略：较小的配置值
            max_workers_candidates = [w for w in search_space['max_workers'] if w <= 4]
            batch_size_candidates = [b for b in search_space['batch_size'] if b <= 1000]
        elif strategy == RecommendationStrategy.AGGRESSIVE:
            # 激进策略：较大的配置值
            max_workers_candidates = [w for w in search_space['max_workers'] if w >= 4]
            batch_size_candidates = [b for b in search_space['batch_size'] if b >= 1000]
        else:
            # 其他策略：使用完整搜索空间
            max_workers_candidates = search_space['max_workers']
            batch_size_candidates = search_space['batch_size']
        
        # 生成配置组合
        for max_workers in max_workers_candidates:
            for batch_size in batch_size_candidates:
                config = base_features.copy()
                config.update({
                    'max_workers': max_workers,
                    'batch_size': batch_size
                })
                candidates.append(config)
        
        # 限制候选数量
        if len(candidates) > 50:
            # 随机采样
            import random
            candidates = random.sample(candidates, 50)
        
        return candidates

    def _predict_performance(self, config: Dict[str, Any]) -> Dict[str, float]:
        """预测配置性能"""
        try:
            # 准备单个配置的特征
            config_df = pd.DataFrame([config])
            X, _ = self._prepare_features(config_df)
            
            if X.shape[0] == 0:
                # 返回默认预测
                return {
                    'execution_time': 60.0,
                    'success_rate': 0.9,
                    'error_rate': 0.1,
                    'throughput': 1000.0,
                    'cpu_utilization': 0.5,
                    'memory_utilization': 0.4
                }
            
            predictions = {}
            
            for target, model in self.models.items():
                try:
                    if target in self.scalers and hasattr(model, 'predict') and model is not None:
                        X_scaled = self.scalers[target].transform(X)
                        pred = model.predict(X_scaled)[0]
                        
                        # 后处理预测结果
                        if target == 'success_rate':
                            pred = max(0.0, min(1.0, pred))
                        elif target == 'error_rate':
                            pred = max(0.0, min(1.0, pred))
                        elif target == 'execution_time':
                            pred = max(1.0, pred)
                        elif target == 'throughput':
                            pred = max(0.0, pred)
                        
                        predictions[target] = float(pred)
                except Exception as e:
                    logger.warning(f"预测 {target} 失败: {e}")
                    # 使用默认值
                    default_values = {
                        'execution_time': 60.0,
                        'success_rate': 0.9,
                        'error_rate': 0.1,
                        'throughput': 1000.0,
                        'cpu_utilization': 0.5,
                        'memory_utilization': 0.4
                    }
                    predictions[target] = default_values.get(target, 0.5)
            
            return predictions
            
        except Exception as e:
            logger.error(f"预测性能失败: {e}")
            return {
                'execution_time': 60.0,
                'success_rate': 0.9,
                'error_rate': 0.1,
                'throughput': 1000.0,
                'cpu_utilization': 0.5,
                'memory_utilization': 0.4
            }

    def _select_best_config(self,
                           candidate_configs: List[Dict[str, Any]],
                           performance_predictions: List[Dict[str, float]],
                           objective: OptimizationObjective) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """根据优化目标选择最佳配置"""
        if not candidate_configs or not performance_predictions:
            raise ValueError("候选配置或性能预测为空")
        
        scores = []
        
        for i, (config, perf) in enumerate(zip(candidate_configs, performance_predictions)):
            if objective == OptimizationObjective.MINIMIZE_TIME:
                score = -perf.get('execution_time', 60.0)  # 负值，越小越好
            elif objective == OptimizationObjective.MAXIMIZE_THROUGHPUT:
                score = perf.get('throughput', 1000.0)
            elif objective == OptimizationObjective.MINIMIZE_ERROR_RATE:
                score = -perf.get('error_rate', 0.1)
            elif objective == OptimizationObjective.MAXIMIZE_SUCCESS_RATE:
                score = perf.get('success_rate', 0.9)
            elif objective == OptimizationObjective.MINIMIZE_RESOURCE_USAGE:
                cpu_util = perf.get('cpu_utilization', 0.5)
                mem_util = perf.get('memory_utilization', 0.4)
                score = -(cpu_util + mem_util) / 2  # 负值，越小越好
            else:
                # 默认综合评分
                success_rate = perf.get('success_rate', 0.9)
                error_rate = perf.get('error_rate', 0.1)
                exec_time = perf.get('execution_time', 60.0)
                throughput = perf.get('throughput', 1000.0)
                
                # 归一化并加权
                score = (success_rate * 0.3 + 
                        (1 - error_rate) * 0.3 + 
                        (1 / max(exec_time, 1)) * 0.2 + 
                        throughput / 10000 * 0.2)
            
            scores.append(score)
        
        # 选择最高分的配置
        best_idx = np.argmax(scores)
        return candidate_configs[best_idx], performance_predictions[best_idx]

    def _calculate_confidence(self, config: Dict[str, Any], performance: Dict[str, float]) -> float:
        """计算推荐置信度"""
        try:
            confidence_factors = []
            
            # 基于历史数据量的置信度
            if self.historical_data is not None and not self.historical_data.empty:
                data_confidence = min(1.0, len(self.historical_data) / 100)  # 100条数据为满分
                confidence_factors.append(data_confidence)
            else:
                confidence_factors.append(0.3)  # 无历史数据时的基础置信度
            
            # 基于模型性能的置信度
            model_confidence = 0.7  # 默认模型置信度
            if hasattr(self, 'model_scores'):
                avg_score = np.mean(list(self.model_scores.values()))
                model_confidence = max(0.3, min(1.0, avg_score))
            confidence_factors.append(model_confidence)
            
            # 基于配置合理性的置信度
            config_confidence = self._assess_config_reasonableness(config)
            confidence_factors.append(config_confidence)
            
            # 基于预测结果合理性的置信度
            prediction_confidence = self._assess_prediction_reasonableness(performance)
            confidence_factors.append(prediction_confidence)
            
            # 综合置信度
            overall_confidence = np.mean(confidence_factors)
            return max(0.1, min(1.0, overall_confidence))
            
        except Exception as e:
            logger.error(f"计算置信度失败: {e}")
            return 0.5

    def _assess_config_reasonableness(self, config: Dict[str, Any]) -> float:
        """评估配置合理性"""
        try:
            score = 1.0
            
            max_workers = config.get('max_workers', 4)
            batch_size = config.get('batch_size', 1000)
            
            # 工作线程数合理性
            if max_workers < 1 or max_workers > 32:
                score *= 0.5
            elif max_workers > 16:
                score *= 0.8
            
            # 批次大小合理性
            if batch_size < 10 or batch_size > 10000:
                score *= 0.5
            elif batch_size > 5000:
                score *= 0.8
            
            # 工作线程与批次大小的匹配性
            if max_workers > 8 and batch_size < 500:
                score *= 0.7  # 高并发但小批次可能不高效
            
            return max(0.1, score)
            
        except Exception as e:
            logger.error(f"评估配置合理性失败: {e}")
            return 0.5

    def _assess_prediction_reasonableness(self, performance: Dict[str, float]) -> float:
        """评估预测结果合理性"""
        try:
            score = 1.0
            
            success_rate = performance.get('success_rate', 0.9)
            error_rate = performance.get('error_rate', 0.1)
            execution_time = performance.get('execution_time', 60.0)
            throughput = performance.get('throughput', 1000.0)
            
            # 成功率和错误率的一致性
            if abs((success_rate + error_rate) - 1.0) > 0.2:
                score *= 0.7
            
            # 执行时间合理性
            if execution_time < 1 or execution_time > 3600:
                score *= 0.5
            
            # 吞吐量合理性
            if throughput < 0 or throughput > 100000:
                score *= 0.5
            
            # 成功率合理性
            if success_rate < 0 or success_rate > 1:
                score *= 0.3
            
            return max(0.1, score)
            
        except Exception as e:
            logger.error(f"评估预测合理性失败: {e}")
            return 0.5

    def _generate_rationale(self,
                           base_config: ImportTaskConfig,
                           recommended_config: Dict[str, Any],
                           performance: Dict[str, float],
                           strategy: RecommendationStrategy,
                           objective: OptimizationObjective) -> str:
        """生成优化理由"""
        try:
            rationale_parts = []
            
            # 策略说明
            strategy_desc = {
                RecommendationStrategy.PERFORMANCE_FIRST: "性能优先策略",
                RecommendationStrategy.STABILITY_FIRST: "稳定性优先策略",
                RecommendationStrategy.RESOURCE_EFFICIENT: "资源效率优先策略",
                RecommendationStrategy.BALANCED: "平衡策略",
                RecommendationStrategy.CONSERVATIVE: "保守策略",
                RecommendationStrategy.AGGRESSIVE: "激进策略"
            }
            rationale_parts.append(f"采用{strategy_desc.get(strategy, '平衡策略')}")
            
            # 目标说明
            objective_desc = {
                OptimizationObjective.MINIMIZE_TIME: "最小化执行时间",
                OptimizationObjective.MAXIMIZE_THROUGHPUT: "最大化吞吐量",
                OptimizationObjective.MINIMIZE_ERROR_RATE: "最小化错误率",
                OptimizationObjective.MAXIMIZE_SUCCESS_RATE: "最大化成功率",
                OptimizationObjective.MINIMIZE_RESOURCE_USAGE: "最小化资源使用"
            }
            rationale_parts.append(f"优化目标为{objective_desc.get(objective, '综合优化')}")
            
            # 配置变化说明
            base_workers = base_config.max_workers
            base_batch = base_config.batch_size
            rec_workers = recommended_config.get('max_workers', base_workers)
            rec_batch = recommended_config.get('batch_size', base_batch)
            
            if rec_workers != base_workers:
                change_desc = "增加" if rec_workers > base_workers else "减少"
                rationale_parts.append(f"{change_desc}工作线程数从{base_workers}到{rec_workers}")
            
            if rec_batch != base_batch:
                change_desc = "增加" if rec_batch > base_batch else "减少"
                rationale_parts.append(f"{change_desc}批次大小从{base_batch}到{rec_batch}")
            
            # 预期效果说明
            success_rate = performance.get('success_rate', 0.9)
            execution_time = performance.get('execution_time', 60.0)
            
            rationale_parts.append(f"预期成功率{success_rate:.1%}，执行时间{execution_time:.1f}秒")
            
            return "，".join(rationale_parts) + "。"
            
        except Exception as e:
            logger.error(f"生成优化理由失败: {e}")
            return "基于历史数据分析和机器学习模型的智能推荐。"

    def _assess_risks(self, config: Dict[str, Any], performance: Dict[str, float]) -> Dict[str, float]:
        """评估配置风险"""
        try:
            risks = {}
            
            max_workers = config.get('max_workers', 4)
            batch_size = config.get('batch_size', 1000)
            success_rate = performance.get('success_rate', 0.9)
            error_rate = performance.get('error_rate', 0.1)
            
            # 资源过载风险
            if max_workers > 8:
                risks['resource_overload'] = min(1.0, (max_workers - 8) / 8)
            else:
                risks['resource_overload'] = 0.0
            
            # 内存不足风险
            if batch_size > 3000:
                risks['memory_shortage'] = min(1.0, (batch_size - 3000) / 2000)
            else:
                risks['memory_shortage'] = 0.0
            
            # 性能不稳定风险
            if success_rate < 0.8:
                risks['performance_instability'] = 1.0 - success_rate
            else:
                risks['performance_instability'] = 0.0
            
            # 错误率过高风险
            if error_rate > 0.2:
                risks['high_error_rate'] = error_rate
            else:
                risks['high_error_rate'] = 0.0
            
            # 配置过于激进风险
            if max_workers > 12 and batch_size > 2000:
                risks['overly_aggressive'] = 0.7
            else:
                risks['overly_aggressive'] = 0.0
            
            return risks
            
        except Exception as e:
            logger.error(f"评估配置风险失败: {e}")
            return {'unknown_risk': 0.3}

    def _generate_alternatives(self,
                              candidate_configs: List[Dict[str, Any]],
                              performance_predictions: List[Dict[str, float]],
                              best_config: Dict[str, Any],
                              num_alternatives: int = 3) -> List[Dict[str, Any]]:
        """生成备选配置"""
        try:
            alternatives = []
            
            # 按综合得分排序
            scored_configs = []
            for config, perf in zip(candidate_configs, performance_predictions):
                if config == best_config:
                    continue
                
                # 计算综合得分
                success_rate = perf.get('success_rate', 0.9)
                error_rate = perf.get('error_rate', 0.1)
                exec_time = perf.get('execution_time', 60.0)
                throughput = perf.get('throughput', 1000.0)
                
                score = (success_rate * 0.3 + 
                        (1 - error_rate) * 0.3 + 
                        (1 / max(exec_time, 1)) * 0.2 + 
                        throughput / 10000 * 0.2)
                
                scored_configs.append((config, perf, score))
            
            # 按得分排序并选择前几个
            scored_configs.sort(key=lambda x: x[2], reverse=True)
            
            for config, perf, score in scored_configs[:num_alternatives]:
                alternative = {
                    'config': config,
                    'expected_performance': perf,
                    'score': score
                }
                alternatives.append(alternative)
            
            return alternatives
            
        except Exception as e:
            logger.error(f"生成备选配置失败: {e}")
            return []

    def _generate_fallback_recommendation(self, base_config: ImportTaskConfig) -> ConfigRecommendation:
        """生成回退推荐"""
        try:
            # 基于经验的简单推荐
            symbols_count = len(base_config.symbols)
            
            # 根据数据量调整配置
            if symbols_count <= 10:
                recommended_workers = 2
                recommended_batch = 500
            elif symbols_count <= 100:
                recommended_workers = 4
                recommended_batch = 1000
            elif symbols_count <= 1000:
                recommended_workers = 6
                recommended_batch = 1500
            else:
                recommended_workers = 8
                recommended_batch = 2000
            
            recommended_config = {
                'data_source': base_config.data_source,
                'asset_type': base_config.asset_type,
                'frequency': base_config.frequency.value,
                'symbols_count': symbols_count,
                'max_workers': recommended_workers,
                'batch_size': recommended_batch
            }
            
            # 估算性能
            expected_performance = {
                'execution_time': 60.0,
                'success_rate': 0.9,
                'error_rate': 0.1,
                'throughput': symbols_count * 10,
                'cpu_utilization': recommended_workers * 0.1,
                'memory_utilization': recommended_batch * 0.0001
            }
            
            return ConfigRecommendation(
                recommended_config=recommended_config,
                confidence_score=0.6,  # 中等置信度
                expected_performance=expected_performance,
                optimization_rationale="基于经验规则的配置推荐，建议收集更多历史数据以提高推荐准确性。",
                alternative_configs=[],
                risk_assessment={'data_insufficient': 0.5}
            )
            
        except Exception as e:
            logger.error(f"生成回退推荐失败: {e}")
            # 最基础的推荐
            return ConfigRecommendation(
                recommended_config={
                    'max_workers': 4,
                    'batch_size': 1000
                },
                confidence_score=0.3,
                expected_performance={
                    'execution_time': 60.0,
                    'success_rate': 0.8,
                    'error_rate': 0.2,
                    'throughput': 1000.0
                },
                optimization_rationale="默认配置推荐。",
                alternative_configs=[],
                risk_assessment={'unknown': 0.7}
            )

    def _generate_cache_key(self,
                           base_config: ImportTaskConfig,
                           strategy: RecommendationStrategy,
                           objective: OptimizationObjective,
                           constraints: Optional[Dict[str, Any]]) -> str:
        """生成缓存键"""
        import hashlib
        
        key_data = {
            'data_source': base_config.data_source,
            'asset_type': base_config.asset_type,
            'frequency': base_config.frequency.value,
            'symbols_count': len(base_config.symbols),
            'strategy': strategy.value,
            'objective': objective.value,
            'constraints': constraints or {}
        }
        
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get_feature_importance(self, target: str = 'success_rate') -> Dict[str, float]:
        """获取特征重要性"""
        return self.feature_importance.get(target, {})

    def get_model_performance(self) -> Dict[str, Dict[str, float]]:
        """获取模型性能指标"""
        performance = {}
        
        if self.historical_data is not None and not self.historical_data.empty:
            try:
                X, _ = self._prepare_features(self.historical_data)
                
                for target, model in self.models.items():
                    if target not in self.historical_data.columns:
                        continue
                    
                    y = self.historical_data[target].fillna(0).values
                    valid_indices = ~np.isnan(y) & ~np.isinf(y)
                    
                    if np.sum(valid_indices) < 5:
                        continue
                    
                    X_valid = X[valid_indices]
                    y_valid = y[valid_indices]
                    
                    if target in self.scalers:
                        X_scaled = self.scalers[target].transform(X_valid)
                        y_pred = model.predict(X_scaled)
                        
                        mse = mean_squared_error(y_valid, y_pred)
                        r2 = r2_score(y_valid, y_pred)
                        
                        performance[target] = {
                            'mse': float(mse),
                            'r2': float(r2),
                            'samples': len(y_valid)
                        }
            except Exception as e:
                logger.error(f"计算模型性能失败: {e}")
        
        return performance

    def retrain_models(self):
        """重新训练模型"""
        logger.info("开始重新训练配置推荐模型...")
        self._load_historical_data()
        if not self.historical_data.empty:
            self._train_models()
            logger.info("模型重新训练完成")
        else:
            logger.warning("无历史数据，无法重新训练模型")

    def clear_cache(self):
        """清空推荐缓存"""
        with self._cache_lock:
            self.recommendation_cache.clear()
        logger.info("推荐缓存已清空")

def main():
    """测试配置推荐引擎"""
    from ..importdata.import_config_manager import DataFrequency, ImportMode
    
    # 创建推荐引擎
    engine = ConfigRecommendationEngine()
    
    # 创建测试配置
    test_config = ImportTaskConfig(
        task_id="recommendation_test_001",
        name="配置推荐测试",
        data_source="tongdaxin",
        asset_type="stock",
        data_type="kline",
        symbols=["000001", "000002", "000858", "000300", "000016"],
        frequency=DataFrequency.DAILY,
        mode=ImportMode.BATCH,
        max_workers=4,
        batch_size=1000
    )
    
    # 测试不同策略的推荐
    strategies = [
        RecommendationStrategy.BALANCED,
        RecommendationStrategy.PERFORMANCE_FIRST,
        RecommendationStrategy.STABILITY_FIRST,
        RecommendationStrategy.CONSERVATIVE
    ]
    
    objectives = [
        OptimizationObjective.MAXIMIZE_SUCCESS_RATE,
        OptimizationObjective.MINIMIZE_TIME,
        OptimizationObjective.MAXIMIZE_THROUGHPUT
    ]
    
    for strategy in strategies:
        for objective in objectives:
            logger.info(f"\n=== 测试策略: {strategy.value}, 目标: {objective.value} ===")
            
            recommendation = engine.recommend_config(
                base_config=test_config,
                strategy=strategy,
                objective=objective
            )
            
            logger.info(f"推荐配置: {recommendation.recommended_config}")
            logger.info(f"置信度: {recommendation.confidence_score:.3f}")
            logger.info(f"预期性能: {recommendation.expected_performance}")
            logger.info(f"优化理由: {recommendation.optimization_rationale}")
            logger.info(f"风险评估: {recommendation.risk_assessment}")
            logger.info(f"备选方案数量: {len(recommendation.alternative_configs)}")
    
    # 测试约束条件
    logger.info("\n=== 测试约束条件 ===")
    constraints = {
        'max_workers_range': (2, 6),
        'batch_size_range': (500, 2000)
    }
    
    constrained_recommendation = engine.recommend_config(
        base_config=test_config,
        strategy=RecommendationStrategy.BALANCED,
        objective=OptimizationObjective.MAXIMIZE_SUCCESS_RATE,
        constraints=constraints
    )
    
    logger.info(f"约束推荐配置: {constrained_recommendation.recommended_config}")
    logger.info(f"约束推荐置信度: {constrained_recommendation.confidence_score:.3f}")
    
    # 获取特征重要性
    logger.info("\n=== 特征重要性 ===")
    for target in ['success_rate', 'execution_time', 'throughput']:
        importance = engine.get_feature_importance(target)
        if importance:
            logger.info(f"{target} 特征重要性: {importance}")
    
    # 获取模型性能
    logger.info("\n=== 模型性能 ===")
    model_performance = engine.get_model_performance()
    for target, metrics in model_performance.items():
        logger.info(f"{target} 模型性能: R²={metrics['r2']:.3f}, MSE={metrics['mse']:.3f}, 样本数={metrics['samples']}")

if __name__ == "__main__":
    main()
