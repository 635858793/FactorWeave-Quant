#!/usr/bin/env python3
"""
自适应缓存策略系统

建立基于AI预测的自适应缓存策略系统，支持缓存策略的自动学习和调整
实现智能化的缓存管理，通过机器学习优化缓存性能
"""

import time
import threading
import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Callable, Union, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import contextmanager
from enum import Enum
from loguru import logger

# 导入AI预测服务
try:
    from ..services.ai_prediction_service import AIPredictionService, PredictionType
    AI_PREDICTION_AVAILABLE = True
except ImportError:
    AI_PREDICTION_AVAILABLE = False
    logger.warning("AI预测服务不可用，自适应缓存将使用简化策略")

# 导入缓存相关组件
try:
    from core.services.cache_service import (
        CacheStrategy, CacheType, CachePriority,
        CacheConfiguration, CacheMetrics, CacheRecommendation
    )
    CACHE_SERVICE_AVAILABLE = True
except ImportError:
    CACHE_SERVICE_AVAILABLE = False
    CacheStrategy = None
    CacheType = None
    CachePriority = None
    CacheConfiguration = None
    CacheMetrics = None
    CacheRecommendation = None
    logger.warning("CacheService 不可用，自适应缓存将使用简化模式")

# 简化的 CacheAccessPattern（不需要 ICC）
class CacheAccessPattern:
    """简化的缓存访问模式（无需 ICC）"""
    def __init__(self):
        self.hot_keys = []
        self.cold_keys = []
        self.access_frequency = {}

# 机器学习库
try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.metrics import mean_squared_error, r2_score
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("机器学习库不可用，自适应缓存将使用规则基础策略")

class AdaptiveMode(Enum):
    """自适应模式"""
    LEARNING = "learning"        # 学习模式
    OPTIMIZING = "optimizing"    # 优化模式
    STABLE = "stable"           # 稳定模式
    FALLBACK = "fallback"       # 回退模式

class LearningPhase(Enum):
    """学习阶段"""
    INITIALIZATION = "initialization"  # 初始化阶段
    DATA_COLLECTION = "data_collection"  # 数据收集阶段
    MODEL_TRAINING = "model_training"    # 模型训练阶段
    VALIDATION = "validation"            # 验证阶段
    DEPLOYMENT = "deployment"            # 部署阶段

@dataclass
class AdaptiveConfig:
    """自适应配置"""
    # 学习配置
    learning_rate: float = 0.01          # 学习率
    min_samples_for_training: int = 100   # 最小训练样本数
    training_interval_hours: int = 6      # 训练间隔（小时）
    validation_split: float = 0.2        # 验证集比例
    
    # 性能阈值
    min_improvement_threshold: float = 0.05  # 最小改进阈值
    performance_window_size: int = 50        # 性能窗口大小
    stability_threshold: float = 0.95        # 稳定性阈值
    
    # 策略配置
    strategy_switch_cooldown_minutes: int = 30  # 策略切换冷却时间
    max_concurrent_strategies: int = 3           # 最大并发策略数
    enable_ensemble_strategies: bool = True      # 启用集成策略
    
    # 安全配置
    enable_fallback_protection: bool = True     # 启用回退保护
    max_performance_degradation: float = 0.1    # 最大性能下降容忍度
    emergency_fallback_threshold: float = 0.5   # 紧急回退阈值

@dataclass
class PerformanceSnapshot:
    """性能快照"""
    timestamp: datetime
    cache_name: str
    strategy: CacheStrategy
    hit_rate: float
    avg_access_time_ms: float
    cache_efficiency: float
    memory_usage_mb: float
    total_requests: int
    
    # 环境特征
    hour_of_day: int
    day_of_week: int
    request_rate: float  # 请求频率（请求/秒）
    data_size_avg: float  # 平均数据大小
    
    def to_feature_vector(self) -> List[float]:
        """转换为特征向量"""
        return [
            self.hit_rate,
            self.avg_access_time_ms,
            self.cache_efficiency,
            self.memory_usage_mb,
            self.total_requests,
            self.hour_of_day,
            self.day_of_week,
            self.request_rate,
            self.data_size_avg
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class StrategyPerformance:
    """策略性能记录"""
    strategy: CacheStrategy
    performance_history: List[float] = field(default_factory=list)
    avg_performance: float = 0.0
    std_performance: float = 0.0
    usage_count: int = 0
    last_used: Optional[datetime] = None
    
    def update_performance(self, performance: float):
        """更新性能记录"""
        self.performance_history.append(performance)
        if len(self.performance_history) > 100:  # 保持最近100条记录
            self.performance_history = self.performance_history[-100:]
        
        self.avg_performance = np.mean(self.performance_history)
        self.std_performance = np.std(self.performance_history)
        self.usage_count += 1
        self.last_used = datetime.now()

class MLCachePredictor:
    """机器学习缓存预测器"""
    
    def __init__(self, config: AdaptiveConfig):
        self.config = config
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        self.label_encoders: Dict[str, LabelEncoder] = {}
        self.training_data: List[PerformanceSnapshot] = []
        self._lock = threading.RLock()
        
        # 初始化模型
        if ML_AVAILABLE:
            self._initialize_models()
    
    def _initialize_models(self):
        """初始化机器学习模型"""
        try:
            # 性能预测模型
            self.models['performance_predictor'] = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            
            # 策略选择模型
            self.models['strategy_selector'] = GradientBoostingRegressor(
                n_estimators=100,
                learning_rate=self.config.learning_rate,
                max_depth=8,
                random_state=42
            )
            
            # 初始化预处理器
            self.scalers['features'] = StandardScaler()
            self.label_encoders['strategy'] = LabelEncoder()
            
            logger.info("机器学习模型初始化完成")
            
        except Exception as e:
            logger.error(f"机器学习模型初始化失败: {e}")
    
    def add_training_sample(self, snapshot: PerformanceSnapshot):
        """添加训练样本"""
        with self._lock:
            self.training_data.append(snapshot)
            
            # 限制训练数据大小
            if len(self.training_data) > 10000:
                self.training_data = self.training_data[-5000:]  # 保留最近5000条
    
    def train_models(self) -> bool:
        """训练模型"""
        if not ML_AVAILABLE or len(self.training_data) < self.config.min_samples_for_training:
            logger.warning(f"训练数据不足: {len(self.training_data)}/{self.config.min_samples_for_training}")
            return False
        
        try:
            with self._lock:
                # 准备训练数据
                features = []
                performance_targets = []
                strategy_targets = []
                
                for snapshot in self.training_data:
                    features.append(snapshot.to_feature_vector())
                    performance_targets.append(snapshot.cache_efficiency)
                    strategy_targets.append(snapshot.strategy.value)
                
                X = np.array(features)
                y_performance = np.array(performance_targets)
                y_strategy = np.array(strategy_targets)
                
                # 数据预处理
                X_scaled = self.scalers['features'].fit_transform(X)
                y_strategy_encoded = self.label_encoders['strategy'].fit_transform(y_strategy)
                
                # 分割训练集和验证集
                X_train, X_val, y_perf_train, y_perf_val, y_strat_train, y_strat_val = train_test_split(
                    X_scaled, y_performance, y_strategy_encoded,
                    test_size=self.config.validation_split,
                    random_state=42
                )
                
                # 训练性能预测模型
                self.models['performance_predictor'].fit(X_train, y_perf_train)
                perf_score = self.models['performance_predictor'].score(X_val, y_perf_val)
                
                # 训练策略选择模型
                self.models['strategy_selector'].fit(X_train, y_strat_train)
                strat_score = self.models['strategy_selector'].score(X_val, y_strat_val)
                
                logger.info(f"模型训练完成 - 性能预测R²: {perf_score:.3f}, 策略选择R²: {strat_score:.3f}")
                return True
                
        except Exception as e:
            logger.error(f"模型训练失败: {e}")
            return False
    
    def predict_performance(self, features: List[float], strategy: CacheStrategy) -> Optional[float]:
        """预测性能"""
        if not ML_AVAILABLE or 'performance_predictor' not in self.models:
            return None
        
        try:
            # 添加策略特征
            strategy_encoded = self._encode_strategy(strategy)
            if strategy_encoded is None:
                return None
            
            extended_features = features + [strategy_encoded]
            
            # 预处理
            X = np.array([extended_features])
            if hasattr(self.scalers['features'], 'transform'):
                X_scaled = self.scalers['features'].transform(X)
            else:
                X_scaled = X
            
            # 预测
            prediction = self.models['performance_predictor'].predict(X_scaled)[0]
            return max(0.0, min(1.0, prediction))  # 限制在[0,1]范围内
            
        except Exception as e:
            logger.error(f"性能预测失败: {e}")
            return None
    
    def suggest_best_strategy(self, features: List[float]) -> Optional[CacheStrategy]:
        """建议最佳策略"""
        if not ML_AVAILABLE:
            return None
        
        try:
            best_strategy = None
            best_performance = -1
            
            # 测试所有策略
            for strategy in CacheStrategy:
                predicted_perf = self.predict_performance(features, strategy)
                if predicted_perf is not None and predicted_perf > best_performance:
                    best_performance = predicted_perf
                    best_strategy = strategy
            
            return best_strategy
            
        except Exception as e:
            logger.error(f"策略建议失败: {e}")
            return None
    
    def _encode_strategy(self, strategy: CacheStrategy) -> Optional[float]:
        """编码策略"""
        try:
            if hasattr(self.label_encoders['strategy'], 'transform'):
                return float(self.label_encoders['strategy'].transform([strategy.value])[0])
            else:
                # 简单映射
                strategy_map = {
                    CacheStrategy.LRU: 0,
                    CacheStrategy.LFU: 1,
                    CacheStrategy.FIFO: 2,
                    CacheStrategy.ADAPTIVE: 3,
                    CacheStrategy.PREDICTIVE: 4,
                    CacheStrategy.INTELLIGENT: 5
                }
                return float(strategy_map.get(strategy, 0))
        except Exception:
            return None
    
    def save_models(self, filepath: str) -> bool:
        """保存模型"""
        if not ML_AVAILABLE:
            return False
        
        try:
            model_data = {
                'models': self.models,
                'scalers': self.scalers,
                'label_encoders': self.label_encoders,
                'config': asdict(self.config)
            }
            
            joblib.dump(model_data, filepath)
            logger.info(f"模型已保存: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"模型保存失败: {e}")
            return False
    
    def load_models(self, filepath: str) -> bool:
        """加载模型"""
        if not ML_AVAILABLE:
            return False
        
        try:
            model_data = joblib.load(filepath)
            
            self.models = model_data['models']
            self.scalers = model_data['scalers']
            self.label_encoders = model_data['label_encoders']
            
            logger.info(f"模型已加载: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            return False

class AdaptiveCacheStrategy:
    """
    自适应缓存策略
    
    功能特性：
    1. 基于AI预测的策略选择
    2. 自动学习和调整
    3. 性能监控和优化
    4. 多策略集成
    5. 安全回退机制
    6. 实时适应性调整
    """
    
    def __init__(self, cache_name: str, config: Optional[AdaptiveConfig] = None):
        """
        初始化自适应缓存策略
        
        Args:
            cache_name: 缓存名称
            config: 自适应配置
        """
        self.cache_name = cache_name
        self.config = config or AdaptiveConfig()
        
        # 状态管理
        self.current_mode = AdaptiveMode.LEARNING
        self.current_phase = LearningPhase.INITIALIZATION
        self.current_strategy = CacheStrategy.LRU  # 默认策略
        
        # 性能跟踪
        self.performance_history: deque = deque(maxlen=self.config.performance_window_size)
        self.strategy_performances: Dict[CacheStrategy, StrategyPerformance] = {}
        self.last_strategy_switch = datetime.now()
        
        # 机器学习组件
        self.ml_predictor: Optional[MLCachePredictor] = None
        if ML_AVAILABLE:
            self.ml_predictor = MLCachePredictor(self.config)
        
        # AI预测服务
        self.ai_service: Optional[AIPredictionService] = None
        if AI_PREDICTION_AVAILABLE:
            try:
                from core.containers import get_service_container
                container = get_service_container()
                self.ai_service = container.resolve(AIPredictionService)
            except Exception as e:
                logger.warning(f"AI预测服务初始化失败: {e}")
        
        # 线程管理
        self._lock = threading.RLock()
        self._running = False
        self._learning_thread: Optional[threading.Thread] = None
        
        # 统计信息
        self._stats = {
            'total_adaptations': 0,
            'successful_adaptations': 0,
            'fallback_activations': 0,
            'model_training_count': 0,
            'last_training_time': None,
            'current_performance': 0.0
        }
        
        # 初始化策略性能记录
        for strategy in CacheStrategy:
            self.strategy_performances[strategy] = StrategyPerformance(strategy=strategy)
        
        logger.info(f"自适应缓存策略初始化完成: {cache_name}")
    
    def start(self) -> bool:
        """启动自适应策略"""
        with self._lock:
            if self._running:
                return False
            
            try:
                self._running = True
                
                # 启动学习线程
                self._learning_thread = threading.Thread(
                    target=self._learning_loop,
                    name=f"AdaptiveCache-{self.cache_name}",
                    daemon=True
                )
                self._learning_thread.start()
                
                # 设置初始阶段
                self.current_phase = LearningPhase.DATA_COLLECTION
                
                logger.info(f"自适应缓存策略已启动: {self.cache_name}")
                return True
                
            except Exception as e:
                self._running = False
                logger.error(f"启动自适应策略失败: {e}")
                return False
    
    def stop(self) -> bool:
        """停止自适应策略"""
        with self._lock:
            if not self._running:
                return True
            
            try:
                self._running = False
                
                # 等待学习线程结束
                if self._learning_thread and self._learning_thread.is_alive():
                    self._learning_thread.join(timeout=5)
                
                logger.info(f"自适应缓存策略已停止: {self.cache_name}")
                return True
                
            except Exception as e:
                logger.error(f"停止自适应策略失败: {e}")
                return False
    
    def record_performance(self, metrics: CacheMetrics, access_pattern: CacheAccessPattern):
        """记录性能数据"""
        try:
            # 创建性能快照
            now = datetime.now()
            
            # 计算请求频率
            recent_requests = len([
                access for access in access_pattern.access_history
                if (now - access['timestamp']).total_seconds() <= 60  # 最近1分钟
            ])
            request_rate = recent_requests / 60.0  # 请求/秒
            
            # 估算平均数据大小（简化实现）
            data_size_avg = 1024.0  # 默认1KB
            
            snapshot = PerformanceSnapshot(
                timestamp=now,
                cache_name=self.cache_name,
                strategy=self.current_strategy,
                hit_rate=metrics.hit_rate,
                avg_access_time_ms=metrics.avg_access_time_ms,
                cache_efficiency=metrics.cache_efficiency,
                memory_usage_mb=metrics.memory_usage_mb,
                total_requests=metrics.total_requests,
                hour_of_day=now.hour,
                day_of_week=now.weekday(),
                request_rate=request_rate,
                data_size_avg=data_size_avg
            )
            
            # 添加到历史记录
            with self._lock:
                self.performance_history.append(snapshot)
                
                # 更新策略性能
                if self.current_strategy in self.strategy_performances:
                    self.strategy_performances[self.current_strategy].update_performance(
                        metrics.cache_efficiency
                    )
                
                # 添加到机器学习训练数据
                if self.ml_predictor:
                    self.ml_predictor.add_training_sample(snapshot)
                
                # 更新统计信息
                self._stats['current_performance'] = metrics.cache_efficiency
            
            logger.debug(f"记录性能数据: {self.cache_name} - 效率: {metrics.cache_efficiency:.3f}")
            
        except Exception as e:
            logger.error(f"记录性能数据失败: {e}")
    
    def get_recommended_strategy(self, current_metrics: CacheMetrics) -> CacheStrategy:
        """获取推荐策略"""
        try:
            # 检查是否在冷却期
            if self._is_in_cooldown():
                return self.current_strategy
            
            # 根据当前模式选择策略
            if self.current_mode == AdaptiveMode.LEARNING:
                return self._get_learning_strategy()
            elif self.current_mode == AdaptiveMode.OPTIMIZING:
                return self._get_optimizing_strategy(current_metrics)
            elif self.current_mode == AdaptiveMode.STABLE:
                return self._get_stable_strategy()
            else:  # FALLBACK
                return self._get_fallback_strategy()
            
        except Exception as e:
            logger.error(f"获取推荐策略失败: {e}")
            return self.current_strategy
    
    def _is_in_cooldown(self) -> bool:
        """检查是否在冷却期"""
        cooldown_duration = timedelta(minutes=self.config.strategy_switch_cooldown_minutes)
        return datetime.now() - self.last_strategy_switch < cooldown_duration
    
    def _get_learning_strategy(self) -> CacheStrategy:
        """获取学习阶段策略"""
        # 在学习阶段，轮换使用不同策略以收集数据
        strategies = list(CacheStrategy)
        
        # 基于时间选择策略，确保每种策略都有机会被测试
        hour = datetime.now().hour
        strategy_index = hour % len(strategies)
        
        return strategies[strategy_index]
    
    def _get_optimizing_strategy(self, current_metrics: CacheMetrics) -> CacheStrategy:
        """获取优化阶段策略"""
        try:
            # 使用机器学习预测最佳策略
            if self.ml_predictor and len(self.performance_history) > 0:
                latest_snapshot = self.performance_history[-1]
                features = latest_snapshot.to_feature_vector()
                
                suggested_strategy = self.ml_predictor.suggest_best_strategy(features)
                if suggested_strategy:
                    return suggested_strategy
            
            # 回退到基于历史性能的策略选择
            return self._get_best_performing_strategy()
            
        except Exception as e:
            logger.error(f"优化策略选择失败: {e}")
            return self._get_best_performing_strategy()
    
    def _get_stable_strategy(self) -> CacheStrategy:
        """获取稳定阶段策略"""
        # 在稳定阶段，使用表现最好的策略
        return self._get_best_performing_strategy()
    
    def _get_fallback_strategy(self) -> CacheStrategy:
        """获取回退策略"""
        # 回退到最安全的LRU策略
        return CacheStrategy.LRU
    
    def _get_best_performing_strategy(self) -> CacheStrategy:
        """获取历史表现最佳的策略"""
        try:
            best_strategy = CacheStrategy.LRU
            best_performance = 0.0
            
            with self._lock:
                for strategy, perf_record in self.strategy_performances.items():
                    if (perf_record.usage_count > 5 and  # 至少使用过5次
                        perf_record.avg_performance > best_performance):
                        best_performance = perf_record.avg_performance
                        best_strategy = strategy
            
            return best_strategy
            
        except Exception as e:
            logger.error(f"获取最佳策略失败: {e}")
            return CacheStrategy.LRU
    
    def apply_strategy(self, new_strategy: CacheStrategy) -> bool:
        """应用新策略"""
        try:
            if new_strategy == self.current_strategy:
                return True
            
            with self._lock:
                old_strategy = self.current_strategy
                self.current_strategy = new_strategy
                self.last_strategy_switch = datetime.now()
                
                # 更新统计
                self._stats['total_adaptations'] += 1
            
            logger.info(f"策略切换: {self.cache_name} {old_strategy.value} -> {new_strategy.value}")
            return True
            
        except Exception as e:
            logger.error(f"应用策略失败: {e}")
            return False
    
    def _learning_loop(self):
        """学习循环"""
        logger.info(f"自适应学习循环已启动: {self.cache_name}")
        
        while self._running:
            try:
                # 检查学习阶段转换
                self._check_phase_transition()
                
                # 执行当前阶段的任务
                if self.current_phase == LearningPhase.DATA_COLLECTION:
                    self._collect_data()
                elif self.current_phase == LearningPhase.MODEL_TRAINING:
                    self._train_models()
                elif self.current_phase == LearningPhase.VALIDATION:
                    self._validate_models()
                elif self.current_phase == LearningPhase.DEPLOYMENT:
                    self._deploy_models()
                
                # 检查模式转换
                self._check_mode_transition()
                
                # 等待下次循环
                time.sleep(300)  # 5分钟间隔
                
            except Exception as e:
                logger.error(f"学习循环错误: {e}")
                time.sleep(60)  # 出错后等待1分钟
    
    def _check_phase_transition(self):
        """检查学习阶段转换"""
        try:
            if self.current_phase == LearningPhase.DATA_COLLECTION:
                # 检查是否有足够的数据进行训练
                if len(self.performance_history) >= self.config.min_samples_for_training:
                    self.current_phase = LearningPhase.MODEL_TRAINING
                    logger.info(f"阶段转换: {self.cache_name} -> MODEL_TRAINING")
            
            elif self.current_phase == LearningPhase.MODEL_TRAINING:
                # 训练完成后进入验证阶段
                self.current_phase = LearningPhase.VALIDATION
                logger.info(f"阶段转换: {self.cache_name} -> VALIDATION")
            
            elif self.current_phase == LearningPhase.VALIDATION:
                # 验证完成后进入部署阶段
                self.current_phase = LearningPhase.DEPLOYMENT
                logger.info(f"阶段转换: {self.cache_name} -> DEPLOYMENT")
            
            elif self.current_phase == LearningPhase.DEPLOYMENT:
                # 部署完成后回到数据收集阶段
                self.current_phase = LearningPhase.DATA_COLLECTION
                logger.info(f"阶段转换: {self.cache_name} -> DATA_COLLECTION")
            
        except Exception as e:
            logger.error(f"阶段转换检查失败: {e}")
    
    def _check_mode_transition(self):
        """检查模式转换"""
        try:
            current_performance = self._calculate_recent_performance()
            
            if self.current_mode == AdaptiveMode.LEARNING:
                # 学习模式 -> 优化模式
                if (len(self.performance_history) >= self.config.min_samples_for_training * 2 and
                    current_performance > 0.6):
                    self.current_mode = AdaptiveMode.OPTIMIZING
                    logger.info(f"模式转换: {self.cache_name} -> OPTIMIZING")
            
            elif self.current_mode == AdaptiveMode.OPTIMIZING:
                # 优化模式 -> 稳定模式 或 回退模式
                if current_performance > self.config.stability_threshold:
                    self.current_mode = AdaptiveMode.STABLE
                    logger.info(f"模式转换: {self.cache_name} -> STABLE")
                elif current_performance < self.config.emergency_fallback_threshold:
                    self.current_mode = AdaptiveMode.FALLBACK
                    self._stats['fallback_activations'] += 1
                    logger.warning(f"模式转换: {self.cache_name} -> FALLBACK")
            
            elif self.current_mode == AdaptiveMode.STABLE:
                # 稳定模式 -> 优化模式 或 回退模式
                if current_performance < self.config.stability_threshold - 0.1:
                    self.current_mode = AdaptiveMode.OPTIMIZING
                    logger.info(f"模式转换: {self.cache_name} -> OPTIMIZING")
                elif current_performance < self.config.emergency_fallback_threshold:
                    self.current_mode = AdaptiveMode.FALLBACK
                    self._stats['fallback_activations'] += 1
                    logger.warning(f"模式转换: {self.cache_name} -> FALLBACK")
            
            elif self.current_mode == AdaptiveMode.FALLBACK:
                # 回退模式 -> 学习模式
                if current_performance > self.config.emergency_fallback_threshold + 0.1:
                    self.current_mode = AdaptiveMode.LEARNING
                    logger.info(f"模式转换: {self.cache_name} -> LEARNING")
            
        except Exception as e:
            logger.error(f"模式转换检查失败: {e}")
    
    def _calculate_recent_performance(self) -> float:
        """计算最近的性能"""
        try:
            if not self.performance_history:
                return 0.0
            
            recent_snapshots = list(self.performance_history)[-10:]  # 最近10个快照
            if not recent_snapshots:
                return 0.0
            
            avg_efficiency = np.mean([s.cache_efficiency for s in recent_snapshots])
            return float(avg_efficiency)
            
        except Exception as e:
            logger.error(f"计算最近性能失败: {e}")
            return 0.0
    
    def _collect_data(self):
        """收集数据阶段任务"""
        # 数据收集在record_performance中进行，这里只是日志记录
        logger.debug(f"数据收集中: {self.cache_name} - 样本数: {len(self.performance_history)}")
    
    def _train_models(self):
        """训练模型阶段任务"""
        try:
            if self.ml_predictor:
                success = self.ml_predictor.train_models()
                if success:
                    self._stats['model_training_count'] += 1
                    self._stats['last_training_time'] = datetime.now()
                    logger.info(f"模型训练完成: {self.cache_name}")
                else:
                    logger.warning(f"模型训练失败: {self.cache_name}")
            
        except Exception as e:
            logger.error(f"模型训练阶段失败: {e}")
    
    def _validate_models(self):
        """验证模型阶段任务"""
        try:
            # 简单的验证：检查模型是否能正常预测
            if self.ml_predictor and len(self.performance_history) > 0:
                latest_snapshot = self.performance_history[-1]
                features = latest_snapshot.to_feature_vector()
                
                prediction = self.ml_predictor.predict_performance(features, self.current_strategy)
                if prediction is not None:
                    logger.info(f"模型验证成功: {self.cache_name} - 预测值: {prediction:.3f}")
                else:
                    logger.warning(f"模型验证失败: {self.cache_name}")
            
        except Exception as e:
            logger.error(f"模型验证阶段失败: {e}")
    
    def _deploy_models(self):
        """部署模型阶段任务"""
        try:
            # 模型已经在内存中，这里只是标记部署完成
            logger.info(f"模型部署完成: {self.cache_name}")
            
        except Exception as e:
            logger.error(f"模型部署阶段失败: {e}")
    
    def get_current_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        with self._lock:
            return {
                'cache_name': self.cache_name,
                'current_mode': self.current_mode.value,
                'current_phase': self.current_phase.value,
                'current_strategy': self.current_strategy.value,
                'performance_samples': len(self.performance_history),
                'recent_performance': self._calculate_recent_performance(),
                'statistics': self._stats.copy(),
                'strategy_performances': {
                    strategy.value: {
                        'avg_performance': perf.avg_performance,
                        'usage_count': perf.usage_count,
                        'last_used': perf.last_used.isoformat() if perf.last_used else None
                    }
                    for strategy, perf in self.strategy_performances.items()
                }
            }
    
    def get_recommendations(self) -> List[CacheRecommendation]:
        """获取自适应建议"""
        recommendations = []
        
        try:
            current_performance = self._calculate_recent_performance()
            
            # 基于当前模式生成建议
            if self.current_mode == AdaptiveMode.LEARNING:
                recommendations.append(CacheRecommendation(
                    cache_name=self.cache_name,
                    recommendation_type='strategy_change',
                    description=f"学习模式中，当前性能: {current_performance:.2%}，继续收集数据",
                    impact_score=0.3,
                    implementation_cost='low',
                    expected_improvement='持续学习优化'
                ))
            
            elif self.current_mode == AdaptiveMode.OPTIMIZING:
                best_strategy = self._get_best_performing_strategy()
                if best_strategy != self.current_strategy:
                    recommendations.append(CacheRecommendation(
                        cache_name=self.cache_name,
                        recommendation_type='strategy_change',
                        description=f"建议切换到表现更好的策略: {best_strategy.value}",
                        impact_score=0.7,
                        implementation_cost='medium',
                        expected_improvement='提升10-20%性能'
                    ))
            
            elif self.current_mode == AdaptiveMode.FALLBACK:
                recommendations.append(CacheRecommendation(
                    cache_name=self.cache_name,
                    recommendation_type='strategy_change',
                    description=f"回退模式激活，性能: {current_performance:.2%}，建议检查系统负载",
                    impact_score=0.9,
                    implementation_cost='high',
                    expected_improvement='恢复正常性能'
                ))
            
        except Exception as e:
            logger.error(f"生成自适应建议失败: {e}")
        
        return recommendations
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

# 全局自适应策略管理器
_adaptive_strategies: Dict[str, AdaptiveCacheStrategy] = {}
_strategies_lock = threading.RLock()

def get_adaptive_strategy(cache_name: str, config: Optional[AdaptiveConfig] = None) -> AdaptiveCacheStrategy:
    """获取自适应策略实例"""
    global _adaptive_strategies
    
    with _strategies_lock:
        if cache_name not in _adaptive_strategies:
            _adaptive_strategies[cache_name] = AdaptiveCacheStrategy(cache_name, config)
            _adaptive_strategies[cache_name].start()
        
        return _adaptive_strategies[cache_name]

def remove_adaptive_strategy(cache_name: str) -> bool:
    """移除自适应策略实例"""
    global _adaptive_strategies
    
    with _strategies_lock:
        if cache_name in _adaptive_strategies:
            _adaptive_strategies[cache_name].stop()
            del _adaptive_strategies[cache_name]
            return True
        return False

def get_all_adaptive_strategies() -> Dict[str, AdaptiveCacheStrategy]:
    """获取所有自适应策略"""
    with _strategies_lock:
        return _adaptive_strategies.copy()
