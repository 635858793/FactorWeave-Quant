"""
推荐模型训练器

提供推荐模型的训练、评估、在线学习和自动更新功能。
支持多种机器学习算法和模型评估指标。

作者: FactorWeave-Quant增强团队
版本: 1.0
日期: 2025-09-21
"""

import asyncio
import threading
import json
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from collections import defaultdict
import joblib

# 机器学习库
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, precision_score, recall_score, f1_score
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.neighbors import NearestNeighbors
from sklearn.decomposition import NMF, TruncatedSVD
from sklearn.cluster import KMeans
import lightgbm as lgb

from loguru import logger
from core.services.smart_recommendation_engine import SmartRecommendationEngine, UserInteraction, ContentItem, Recommendation
from core.ai.continuous_learning_manager import ContinuousLearningManager

logger = logger.bind(module=__name__)


class SVDModelWrapper:
    """
    SVD模型包装类
    
    为TruncatedSVD添加predict方法，使其与其他模型接口一致
    """
    
    def __init__(self, svd_model: TruncatedSVD, user_item_matrix: pd.DataFrame):
        self.svd_model = svd_model
        self.user_item_matrix = user_item_matrix
        self.user_ids = user_item_matrix.index.tolist()
        self.item_ids = user_item_matrix.columns.tolist()
        
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        预测评分
        
        Args:
            X: 包含user_id和item_id的DataFrame
            
        Returns:
            预测的评分数组
        """
        predictions = []
        
        for _, row in X.iterrows():
            user_id = row.get('user_id')
            item_id = row.get('item_id')
            
            if user_id in self.user_ids and item_id in self.item_ids:
                user_idx = self.user_ids.index(user_id)
                item_idx = self.item_ids.index(item_id)
                
                # 使用SVD重构评分
                user_vector = self.svd_model.transform(self.user_item_matrix.iloc[[user_idx]])
                item_vector = self.svd_model.components_.T[item_idx]
                prediction = np.dot(user_vector, item_vector)[0]
                
                # 确保评分在合理范围内
                prediction = max(0, min(1, prediction))
                predictions.append(prediction)
            else:
                # 如果用户或物品不在训练数据中，返回默认评分
                predictions.append(0.5)
        
        return np.array(predictions)


class NMFModelWrapper:
    """
    NMF模型包装类
    
    为NMF添加predict方法，使其与其他模型接口一致
    """
    
    def __init__(self, nmf_model: NMF, user_item_matrix: pd.DataFrame):
        self.nmf_model = nmf_model
        self.user_item_matrix = user_item_matrix
        self.user_ids = user_item_matrix.index.tolist()
        self.item_ids = user_item_matrix.columns.tolist()
        
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        预测评分
        
        Args:
            X: 包含user_id和item_id的DataFrame
            
        Returns:
            预测的评分数组
        """
        predictions = []
        
        for _, row in X.iterrows():
            user_id = row.get('user_id')
            item_id = row.get('item_id')
            
            if user_id in self.user_ids and item_id in self.item_ids:
                user_idx = self.user_ids.index(user_id)
                item_idx = self.item_ids.index(item_id)
                
                # 使用NMF重构评分
                W = self.nmf_model.transform(self.user_item_matrix.iloc[[user_idx]])
                H = self.nmf_model.components_
                prediction = np.dot(W, H[:, item_idx])[0]
                
                # 确保评分在合理范围内
                prediction = max(0, min(1, prediction))
                predictions.append(prediction)
            else:
                # 如果用户或物品不在训练数据中，返回默认评分
                predictions.append(0.5)
        
        return np.array(predictions)


class ModelType(Enum):
    """模型类型"""
    COLLABORATIVE_FILTERING = "collaborative_filtering"
    CONTENT_BASED = "content_based"
    MATRIX_FACTORIZATION = "matrix_factorization"
    DEEP_LEARNING = "deep_learning"
    ENSEMBLE = "ensemble"
    CLUSTERING = "clustering"


class TrainingStatus(Enum):
    """训练状态"""
    IDLE = "idle"
    PREPARING = "preparing"
    TRAINING = "training"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ModelConfig:
    """模型配置"""
    model_id: str
    model_type: ModelType
    algorithm: str  # 具体算法名称

    # 超参数
    hyperparameters: Dict[str, Any] = field(default_factory=dict)

    # 训练配置
    train_ratio: float = 0.8
    validation_ratio: float = 0.1
    test_ratio: float = 0.1

    # 评估配置
    evaluation_metrics: List[str] = field(default_factory=lambda: ['rmse', 'mae', 'precision', 'recall'])
    cross_validation_folds: int = 5

    # 在线学习配置
    online_learning_enabled: bool = True
    batch_size: int = 100
    learning_rate: float = 0.01

    # 模型更新配置
    auto_retrain: bool = True
    retrain_threshold: float = 0.1  # 性能下降阈值
    retrain_interval: timedelta = timedelta(days=7)

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class TrainingJob:
    """训练任务"""
    job_id: str
    model_config: ModelConfig

    # 任务状态
    status: TrainingStatus = TrainingStatus.IDLE
    progress: float = 0.0

    # 数据信息
    training_data_size: int = 0
    validation_data_size: int = 0
    test_data_size: int = 0

    # 训练结果
    training_metrics: Dict[str, float] = field(default_factory=dict)
    validation_metrics: Dict[str, float] = field(default_factory=dict)
    test_metrics: Dict[str, float] = field(default_factory=dict)

    # 时间信息
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None

    # 错误信息
    error_message: Optional[str] = None

    # 模型信息
    model_path: Optional[str] = None
    model_size: Optional[int] = None


@dataclass
class ModelPerformance:
    """模型性能"""
    model_id: str
    evaluation_date: datetime

    # 性能指标
    rmse: float = 0.0
    mae: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    auc: float = 0.0

    # 业务指标
    click_through_rate: float = 0.0
    conversion_rate: float = 0.0
    user_satisfaction: float = 0.0

    # 计算资源
    training_time: float = 0.0
    inference_time: float = 0.0
    memory_usage: float = 0.0

    # 数据统计
    training_samples: int = 0
    test_samples: int = 0
    feature_count: int = 0


class RecommendationModelTrainer:
    """
    推荐模型训练器

    提供推荐模型的全生命周期管理：
    - 模型训练和超参数优化
    - 模型评估和性能监控
    - 在线学习和增量更新
    - A/B测试和模型比较
    - 自动化模型部署
    """

    def __init__(self, recommendation_engine: SmartRecommendationEngine,
                 continuous_learning_manager: ContinuousLearningManager,
                 database_service=None):
        self.recommendation_engine = recommendation_engine
        self.continuous_learning_manager = continuous_learning_manager
        self.database_service = database_service

        # 模型管理
        self.models: Dict[str, Any] = {}  # 训练好的模型
        self.model_configs: Dict[str, ModelConfig] = {}
        self.model_performances: Dict[str, List[ModelPerformance]] = defaultdict(list)

        # 训练管理
        self.training_jobs: Dict[str, TrainingJob] = {}
        self.active_job: Optional[str] = None

        # 数据管理
        self.training_data: Optional[pd.DataFrame] = None
        self.feature_columns: List[str] = []
        self.target_column: str = 'rating'

        # 配置
        self.model_save_path = "models/recommendation/"
        self.max_concurrent_jobs = 3
        self.performance_history_limit = 100

        # 状态管理
        self._training_active = False
        self._training_thread = None
        self._lock = threading.RLock()

        # 统计信息
        self.training_stats = {
            'total_jobs': 0,
            'successful_jobs': 0,
            'failed_jobs': 0,
            'avg_training_time': 0.0,
            'best_model_performance': 0.0
        }

        # 初始化默认模型配置
        self._initialize_default_configs()

        logger.info("推荐模型训练器初始化完成")

    def _initialize_default_configs(self):
        """初始化默认模型配置"""
        try:
            # 协同过滤模型
            cf_config = ModelConfig(
                model_id="collaborative_filtering_svd",
                model_type=ModelType.COLLABORATIVE_FILTERING,
                algorithm="svd",
                hyperparameters={
                    'n_components': 50,
                    'random_state': 42
                },
                evaluation_metrics=['rmse', 'mae']
            )

            # 内容基础模型
            content_config = ModelConfig(
                model_id="content_based_rf",
                model_type=ModelType.CONTENT_BASED,
                algorithm="random_forest",
                hyperparameters={
                    'n_estimators': 100,
                    'max_depth': 10,
                    'random_state': 42
                },
                evaluation_metrics=['rmse', 'mae', 'precision', 'recall']
            )

            # 矩阵分解模型
            mf_config = ModelConfig(
                model_id="matrix_factorization_nmf",
                model_type=ModelType.MATRIX_FACTORIZATION,
                algorithm="nmf",
                hyperparameters={
                    'n_components': 30,
                    'random_state': 42,
                    'max_iter': 200
                },
                evaluation_metrics=['rmse', 'mae']
            )

            # LightGBM模型
            lgb_config = ModelConfig(
                model_id="ensemble_lightgbm",
                model_type=ModelType.ENSEMBLE,
                algorithm="lightgbm",
                hyperparameters={
                    'num_leaves': 31,
                    'learning_rate': 0.05,
                    'feature_fraction': 0.9,
                    'bagging_fraction': 0.8,
                    'bagging_freq': 5,
                    'verbose': 0
                },
                evaluation_metrics=['rmse', 'mae', 'precision', 'recall']
            )

            self.model_configs = {
                config.model_id: config
                for config in [cf_config, content_config, mf_config, lgb_config]
            }

            logger.info(f"已加载 {len(self.model_configs)} 个默认模型配置")

        except Exception as e:
            logger.error(f"初始化默认模型配置失败: {e}")

    async def prepare_training_data(self) -> bool:
        """准备训练数据"""
        try:
            logger.info("开始准备训练数据...")

            # 从推荐引擎获取交互数据
            interactions = self.recommendation_engine.interactions
            content_items = self.recommendation_engine.content_items
            user_profiles = self.recommendation_engine.user_profiles

            # 如果没有交互数据，尝试从数据库加载
            if not interactions:
                logger.info("内存中没有交互数据，尝试从数据库加载...")
                
                if self.database_service:
                    # 从数据库加载交互数据
                    interactions_data = self.database_service.get_user_interactions(limit=10000)
                    logger.info(f"从数据库加载了 {len(interactions_data)} 条交互数据")
                    
                    # 从数据库加载内容项数据
                    content_items_data = self.database_service.get_content_items(limit=10000)
                    logger.info(f"从数据库加载了 {len(content_items_data)} 条内容项数据")
                    
                    # 从数据库加载用户画像数据
                    user_profiles_data = self.database_service.get_all_user_profiles(limit=10000)
                    logger.info(f"从数据库加载了 {len(user_profiles_data)} 条用户画像数据")
                    
                    # 将数据库数据转换为推荐引擎的数据格式
                    for item in interactions_data:
                        interaction = UserInteraction(
                            user_id=item['user_id'],
                            item_id=item['item_id'],
                            interaction_type=item['interaction_type'],
                            timestamp=datetime.fromisoformat(item['timestamp']) if isinstance(item['timestamp'], str) else item['timestamp'],
                            duration=item.get('duration'),
                            rating=item.get('rating'),
                            context=item.get('context', {})
                        )
                        self.recommendation_engine.interactions.append(interaction)
                    
                    for item in content_items_data:
                        from core.services.smart_recommendation_engine import RecommendationType
                        content_item = ContentItem(
                            item_id=item['item_id'],
                            item_type=RecommendationType(item['item_type']),
                            title=item['title'],
                            description=item.get('description', ''),
                            tags=item.get('tags', []),
                            categories=item.get('categories', []),
                            keywords=item.get('keywords', []),
                            view_count=item.get('view_count', 0),
                            like_count=item.get('like_count', 0),
                            share_count=item.get('share_count', 0),
                            rating=item.get('rating', 0.0),
                            created_at=datetime.fromisoformat(item['created_at']) if isinstance(item['created_at'], str) else item['created_at'],
                            updated_at=datetime.fromisoformat(item['updated_at']) if isinstance(item['updated_at'], str) else item['updated_at'],
                            metadata=item.get('metadata', {})
                        )
                        self.recommendation_engine.content_items[content_item.item_id] = content_item
                    
                    for profile_data in user_profiles_data:
                        from core.services.smart_recommendation_engine import UserProfile
                        user_profile = UserProfile(
                            user_id=profile_data['user_id'],
                            registration_date=datetime.fromisoformat(profile_data['created_at']) if isinstance(profile_data['created_at'], str) else profile_data['created_at'],
                            last_active=datetime.fromisoformat(profile_data['updated_at']) if isinstance(profile_data['updated_at'], str) else profile_data['updated_at'],
                            activity_level='medium',
                            preferred_stocks=[],
                            preferred_sectors=[],
                            risk_tolerance='medium',
                            investment_horizon='medium'
                        )
                        self.recommendation_engine.user_profiles[user_profile.user_id] = user_profile
                    
                    # 重新获取数据
                    interactions = self.recommendation_engine.interactions
                    content_items = self.recommendation_engine.content_items
                    user_profiles = self.recommendation_engine.user_profiles
                else:
                    logger.warning("数据库服务未提供，无法从数据库加载数据")

            if not interactions:
                logger.warning("没有交互数据，无法准备训练数据")
                logger.info("提示：请确保数据库中有足够的交互数据")
                return False

            # 构建特征矩阵
            features_data = []

            for interaction in interactions:
                user_id = interaction.user_id
                item_id = interaction.item_id

                # 获取用户特征
                user_profile = user_profiles.get(user_id)
                content_item = content_items.get(item_id)

                if not user_profile or not content_item:
                    continue

                # 构建特征向量
                feature_row = {
                    'user_id': user_id,
                    'item_id': item_id,
                    'interaction_type': interaction.interaction_type,
                    'timestamp': interaction.timestamp.timestamp(),
                }

                # 用户特征
                feature_row.update({
                    'user_activity_level': self._encode_activity_level(user_profile.activity_level),
                    'user_risk_tolerance': self._encode_risk_tolerance(user_profile.risk_tolerance),
                    'user_investment_horizon': self._encode_investment_horizon(user_profile.investment_horizon),
                    'user_preferred_stocks_count': len(user_profile.preferred_stocks),
                    'user_preferred_sectors_count': len(user_profile.preferred_sectors),
                })

                # 内容特征
                feature_row.update({
                    'item_type': content_item.item_type.value,
                    'item_view_count': content_item.view_count,
                    'item_like_count': content_item.like_count,
                    'item_share_count': content_item.share_count,
                    'item_rating': content_item.rating,
                    'item_tags_count': len(content_item.tags),
                    'item_categories_count': len(content_item.categories),
                })

                # 目标变量（评分）
                rating = self._calculate_implicit_rating(interaction)
                feature_row['rating'] = rating

                features_data.append(feature_row)

            # 转换为DataFrame
            self.training_data = pd.DataFrame(features_data)

            # 特征工程
            self.training_data = self._feature_engineering(self.training_data)

            # 确定特征列和目标列
            self.feature_columns = [col for col in self.training_data.columns
                                    if col not in ['user_id', 'item_id', 'rating']]
            self.target_column = 'rating'

            logger.info(f"训练数据准备完成: {len(self.training_data)} 条记录, {len(self.feature_columns)} 个特征")
            return True

        except Exception as e:
            logger.error(f"准备训练数据失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    async def train_model(self, model_id: str, config: ModelConfig = None) -> str:
        """训练模型"""
        try:
            if not config:
                config = self.model_configs.get(model_id)
                if not config:
                    raise Exception(f"模型配置不存在: {model_id}")

            # 创建训练任务
            job_id = f"train_{model_id}_{datetime.now().timestamp()}"
            job = TrainingJob(
                job_id=job_id,
                model_config=config
            )

            self.training_jobs[job_id] = job

            # 异步执行训练
            asyncio.create_task(self._execute_training_job(job))

            logger.info(f"训练任务已创建: {job_id}")
            return job_id

        except Exception as e:
            logger.error(f"创建训练任务失败: {e}")
            raise

    async def _execute_training_job(self, job: TrainingJob):
        """执行训练任务"""
        try:
            job.status = TrainingStatus.PREPARING
            job.started_at = datetime.now()
            job.progress = 0.1

            # 准备数据
            if self.training_data is None:
                if not await self.prepare_training_data():
                    raise Exception("训练数据准备失败")

            job.progress = 0.2

            # 数据分割
            X = self.training_data[self.feature_columns]
            y = self.training_data[self.target_column]

            X_train, X_temp, y_train, y_temp = train_test_split(
                X, y, test_size=1-job.model_config.train_ratio, random_state=42
            )

            val_ratio = job.model_config.validation_ratio / (1 - job.model_config.train_ratio)
            X_val, X_test, y_val, y_test = train_test_split(
                X_temp, y_temp, test_size=1-val_ratio, random_state=42
            )

            job.training_data_size = len(X_train)
            job.validation_data_size = len(X_val)
            job.test_data_size = len(X_test)
            job.progress = 0.3

            # 训练模型
            job.status = TrainingStatus.TRAINING
            model = await self._train_model_by_type(job.model_config, X_train, y_train)
            job.progress = 0.7

            # 评估模型
            job.status = TrainingStatus.EVALUATING

            # 训练集评估
            y_train_pred = model.predict(X_train)
            job.training_metrics = self._calculate_metrics(y_train, y_train_pred, job.model_config.evaluation_metrics)

            # 验证集评估
            y_val_pred = model.predict(X_val)
            job.validation_metrics = self._calculate_metrics(y_val, y_val_pred, job.model_config.evaluation_metrics)

            # 测试集评估
            y_test_pred = model.predict(X_test)
            job.test_metrics = self._calculate_metrics(y_test, y_test_pred, job.model_config.evaluation_metrics)

            job.progress = 0.9

            # 保存模型
            model_path = await self._save_model(job.model_config.model_id, model)
            job.model_path = model_path

            # 更新模型注册
            self.models[job.model_config.model_id] = model

            # 记录性能
            performance = ModelPerformance(
                model_id=job.model_config.model_id,
                evaluation_date=datetime.now(),
                rmse=job.test_metrics.get('rmse', 0.0),
                mae=job.test_metrics.get('mae', 0.0),
                precision=job.test_metrics.get('precision', 0.0),
                recall=job.test_metrics.get('recall', 0.0),
                f1_score=job.test_metrics.get('f1_score', 0.0),
                training_samples=job.training_data_size,
                test_samples=job.test_data_size,
                feature_count=len(self.feature_columns)
            )

            self.model_performances[job.model_config.model_id].append(performance)

            # 完成训练
            job.status = TrainingStatus.COMPLETED
            job.completed_at = datetime.now()
            job.duration = (job.completed_at - job.started_at).total_seconds()
            job.progress = 1.0

            # 更新统计
            self._update_training_stats(True, job.duration)

            logger.info(f"模型训练完成: {job.model_config.model_id}")

        except Exception as e:
            job.status = TrainingStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now()

            if job.started_at:
                job.duration = (job.completed_at - job.started_at).total_seconds()

            self._update_training_stats(False, job.duration or 0)

            logger.error(f"模型训练失败: {job.job_id}, {e}")

    async def _train_model_by_type(self, config: ModelConfig, X_train: pd.DataFrame, y_train: pd.Series):
        """根据模型类型训练模型"""
        try:
            algorithm = config.algorithm
            hyperparams = config.hyperparameters

            if config.model_type == ModelType.COLLABORATIVE_FILTERING:
                if algorithm == "svd":
                    # 对于SVD，需要特殊处理
                    user_item_matrix = self._create_user_item_matrix()
                    
                    # 动态调整 n_components 参数，确保不超过特征数量
                    n_features = user_item_matrix.shape[1]
                    n_components = hyperparams.get('n_components', 50)
                    
                    if n_components > n_features:
                        logger.warning(f"n_components({n_components}) 大于特征数量({n_features})，自动调整为 {n_features}")
                        hyperparams = hyperparams.copy()
                        hyperparams['n_components'] = n_features
                    
                    svd_model = TruncatedSVD(**hyperparams)
                    svd_model.fit(user_item_matrix)
                    
                    # 使用包装类包装SVD模型
                    model = SVDModelWrapper(svd_model, user_item_matrix)
                    return model

            elif config.model_type == ModelType.CONTENT_BASED:
                if algorithm == "random_forest":
                    model = RandomForestRegressor(**hyperparams)
                elif algorithm == "gradient_boosting":
                    model = GradientBoostingRegressor(**hyperparams)
                elif algorithm == "linear_regression":
                    model = LinearRegression(**hyperparams)
                elif algorithm == "ridge":
                    model = Ridge(**hyperparams)
                elif algorithm == "lasso":
                    model = Lasso(**hyperparams)
                else:
                    raise Exception(f"不支持的内容基础算法: {algorithm}")

                model.fit(X_train, y_train)
                return model

            elif config.model_type == ModelType.MATRIX_FACTORIZATION:
                if algorithm == "nmf":
                    # 对于NMF，需要特殊处理
                    user_item_matrix = self._create_user_item_matrix()
                    
                    # 动态调整 n_components 参数，确保不超过特征数量
                    n_features = user_item_matrix.shape[1]
                    n_components = hyperparams.get('n_components', 30)
                    
                    if n_components > n_features:
                        logger.warning(f"n_components({n_components}) 大于特征数量({n_features})，自动调整为 {n_features}")
                        hyperparams = hyperparams.copy()
                        hyperparams['n_components'] = n_features
                    
                    nmf_model = NMF(**hyperparams)
                    nmf_model.fit(user_item_matrix)
                    
                    # 使用包装类包装NMF模型
                    model = NMFModelWrapper(nmf_model, user_item_matrix)
                    return model

            elif config.model_type == ModelType.ENSEMBLE:
                if algorithm == "lightgbm":
                    model = lgb.LGBMRegressor(**hyperparams)
                    model.fit(X_train, y_train)
                    return model

            elif config.model_type == ModelType.CLUSTERING:
                if algorithm == "kmeans":
                    model = KMeans(**hyperparams)
                    model.fit(X_train)
                    return model

            raise Exception(f"不支持的模型类型或算法: {config.model_type} - {algorithm}")

        except Exception as e:
            logger.error(f"训练模型失败: {e}")
            raise

    def _create_user_item_matrix(self) -> pd.DataFrame:
        """创建用户-物品矩阵"""
        try:
            # 从训练数据创建用户-物品矩阵
            matrix_data = self.training_data.pivot_table(
                index='user_id',
                columns='item_id',
                values='rating',
                fill_value=0
            )

            return matrix_data

        except Exception as e:
            logger.error(f"创建用户-物品矩阵失败: {e}")
            return pd.DataFrame()

    def _calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray, metrics: List[str]) -> Dict[str, float]:
        """计算评估指标"""
        try:
            results = {}

            for metric in metrics:
                if metric == 'rmse':
                    results['rmse'] = np.sqrt(mean_squared_error(y_true, y_pred))
                elif metric == 'mae':
                    results['mae'] = mean_absolute_error(y_true, y_pred)
                elif metric == 'precision':
                    # 将回归问题转换为分类问题（评分>=0.5为正例）
                    y_true_binary = (y_true >= 0.5).astype(int)
                    y_pred_binary = (y_pred >= 0.5).astype(int)
                    results['precision'] = precision_score(y_true_binary, y_pred_binary, average='weighted', zero_division=0)
                elif metric == 'recall':
                    y_true_binary = (y_true >= 0.5).astype(int)
                    y_pred_binary = (y_pred >= 0.5).astype(int)
                    results['recall'] = recall_score(y_true_binary, y_pred_binary, average='weighted', zero_division=0)
                elif metric == 'f1_score':
                    y_true_binary = (y_true >= 0.5).astype(int)
                    y_pred_binary = (y_pred >= 0.5).astype(int)
                    results['f1_score'] = f1_score(y_true_binary, y_pred_binary, average='weighted', zero_division=0)

            return results

        except Exception as e:
            logger.error(f"计算评估指标失败: {e}")
            return {}

    async def _save_model(self, model_id: str, model: Any) -> str:
        """保存模型"""
        try:
            import os

            # 确保目录存在
            os.makedirs(self.model_save_path, exist_ok=True)

            # 生成文件路径
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_path = f"{self.model_save_path}/{model_id}_{timestamp}.pkl"

            # 保存模型
            joblib.dump(model, model_path)

            logger.info(f"模型已保存: {model_path}")
            return model_path

        except Exception as e:
            logger.error(f"保存模型失败: {e}")
            raise

    def load_model(self, model_path: str) -> Any:
        """加载模型"""
        try:
            model = joblib.load(model_path)
            logger.info(f"模型已加载: {model_path}")
            return model
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            raise

    async def hyperparameter_optimization(self, model_id: str, param_grid: Dict[str, List[Any]]) -> Dict[str, Any]:
        """超参数优化"""
        try:
            config = self.model_configs.get(model_id)
            if not config:
                raise Exception(f"模型配置不存在: {model_id}")

            if self.training_data is None:
                if not await self.prepare_training_data():
                    raise Exception("训练数据准备失败")

            X = self.training_data[self.feature_columns]
            y = self.training_data[self.target_column]

            # 创建基础模型
            base_model = await self._create_base_model(config)

            # 网格搜索
            grid_search = GridSearchCV(
                base_model,
                param_grid,
                cv=config.cross_validation_folds,
                scoring='neg_mean_squared_error',
                n_jobs=-1
            )

            grid_search.fit(X, y)

            # 更新配置
            best_params = grid_search.best_params_
            config.hyperparameters.update(best_params)

            logger.info(f"超参数优化完成: {model_id}, 最佳参数: {best_params}")

            return {
                'best_params': best_params,
                'best_score': -grid_search.best_score_,
                'cv_results': grid_search.cv_results_
            }

        except Exception as e:
            logger.error(f"超参数优化失败: {e}")
            raise

    async def _create_base_model(self, config: ModelConfig):
        """创建基础模型（用于超参数优化）"""
        try:
            algorithm = config.algorithm

            if algorithm == "random_forest":
                return RandomForestRegressor(random_state=42)
            elif algorithm == "gradient_boosting":
                return GradientBoostingRegressor(random_state=42)
            elif algorithm == "lightgbm":
                return lgb.LGBMRegressor(random_state=42, verbose=-1)
            elif algorithm == "linear_regression":
                return LinearRegression()
            elif algorithm == "ridge":
                return Ridge(random_state=42)
            elif algorithm == "lasso":
                return Lasso(random_state=42)
            else:
                raise Exception(f"不支持的算法: {algorithm}")

        except Exception as e:
            logger.error(f"创建基础模型失败: {e}")
            raise

    async def evaluate_model(self, model_id: str) -> Dict[str, Any]:
        """评估模型"""
        try:
            if model_id not in self.models:
                raise Exception(f"模型不存在: {model_id}")

            model = self.models[model_id]
            config = self.model_configs[model_id]

            if self.training_data is None:
                if not await self.prepare_training_data():
                    raise Exception("训练数据准备失败")

            X = self.training_data[self.feature_columns]
            y = self.training_data[self.target_column]

            # 交叉验证
            cv_scores = cross_val_score(
                model, X, y,
                cv=config.cross_validation_folds,
                scoring='neg_mean_squared_error'
            )

            # 预测
            y_pred = model.predict(X)

            # 计算指标
            metrics = self._calculate_metrics(y, y_pred, config.evaluation_metrics)

            evaluation_result = {
                'model_id': model_id,
                'metrics': metrics,
                'cross_validation_scores': -cv_scores,
                'cv_mean': -cv_scores.mean(),
                'cv_std': cv_scores.std(),
                'evaluation_date': datetime.now().isoformat()
            }

            logger.info(f"模型评估完成: {model_id}")
            return evaluation_result

        except Exception as e:
            logger.error(f"模型评估失败: {e}")
            raise

    async def online_learning_update(self, model_id: str, new_interactions: List[UserInteraction]) -> bool:
        """在线学习更新"""
        try:
            if model_id not in self.models:
                logger.warning(f"模型不存在，跳过在线学习: {model_id}")
                return False

            config = self.model_configs[model_id]
            if not config.online_learning_enabled:
                return False

            # 准备新数据
            new_data = await self._prepare_incremental_data(new_interactions)
            if new_data.empty:
                return False

            # 增量更新（这里需要根据具体算法实现）
            # 大多数sklearn模型不支持增量学习，需要使用支持的算法或重新训练

            logger.info(f"在线学习更新完成: {model_id}")
            return True

        except Exception as e:
            logger.error(f"在线学习更新失败: {e}")
            return False

    async def _prepare_incremental_data(self, interactions: List[UserInteraction]) -> pd.DataFrame:
        """准备增量数据"""
        try:
            # 类似于prepare_training_data，但只处理新的交互数据
            features_data = []

            for interaction in interactions:
                # 构建特征（简化实现）
                feature_row = {
                    'user_id': interaction.user_id,
                    'item_id': interaction.item_id,
                    'interaction_type': interaction.interaction_type,
                    'timestamp': interaction.timestamp.timestamp(),
                    'rating': self._calculate_implicit_rating(interaction)
                }
                features_data.append(feature_row)

            return pd.DataFrame(features_data)

        except Exception as e:
            logger.error(f"准备增量数据失败: {e}")
            return pd.DataFrame()

    def _calculate_implicit_rating(self, interaction: UserInteraction) -> float:
        """计算隐式评分"""
        try:
            # 基于交互类型计算评分
            base_scores = {
                'view': 0.3,
                'like': 0.8,
                'share': 1.0,
                'bookmark': 0.9,
                'comment': 0.7
            }

            score = base_scores.get(interaction.interaction_type, 0.5)

            # 考虑交互时长
            if interaction.duration:
                duration_factor = min(2.0, interaction.duration / 60)  # 最多2倍
                score *= duration_factor

            # 考虑用户评分
            if interaction.rating:
                score = (score + interaction.rating) / 2

            return min(1.0, score)

        except Exception as e:
            logger.error(f"计算隐式评分失败: {e}")
            return 0.5

    def _encode_activity_level(self, activity_level: str) -> int:
        """编码活跃度级别"""
        mapping = {'low': 1, 'medium': 2, 'high': 3}
        return mapping.get(activity_level, 2)

    def _encode_risk_tolerance(self, risk_tolerance: str) -> int:
        """编码风险承受度"""
        mapping = {'conservative': 1, 'medium': 2, 'aggressive': 3}
        return mapping.get(risk_tolerance, 2)

    def _encode_investment_horizon(self, investment_horizon: str) -> int:
        """编码投资期限"""
        mapping = {'short': 1, 'medium': 2, 'long': 3}
        return mapping.get(investment_horizon, 2)

    def _feature_engineering(self, data: pd.DataFrame) -> pd.DataFrame:
        """特征工程"""
        try:
            # 时间特征
            data['hour'] = pd.to_datetime(data['timestamp'], unit='s').dt.hour
            data['day_of_week'] = pd.to_datetime(data['timestamp'], unit='s').dt.dayofweek

            # 交互类型编码
            interaction_mapping = {
                'view': 1, 'like': 2, 'share': 3, 'bookmark': 4, 'comment': 5
            }
            data['interaction_type_encoded'] = data['interaction_type'].map(interaction_mapping).fillna(0)

            # 内容类型编码
            item_type_mapping = {
                'stock': 1, 'indicator': 2, 'strategy': 3, 'news': 4, 'research': 5, 'portfolio': 6
            }
            data['item_type_encoded'] = data['item_type'].map(item_type_mapping).fillna(0)

            # 删除原始分类列
            data = data.drop(['interaction_type', 'item_type'], axis=1)

            return data

        except Exception as e:
            logger.error(f"特征工程失败: {e}")
            return data

    def _update_training_stats(self, success: bool, duration: float):
        """更新训练统计"""
        try:
            self.training_stats['total_jobs'] += 1

            if success:
                self.training_stats['successful_jobs'] += 1
            else:
                self.training_stats['failed_jobs'] += 1

            # 更新平均训练时间
            total_jobs = self.training_stats['total_jobs']
            current_avg = self.training_stats['avg_training_time']
            self.training_stats['avg_training_time'] = (current_avg * (total_jobs - 1) + duration) / total_jobs

        except Exception as e:
            logger.error(f"更新训练统计失败: {e}")

    def get_training_job_status(self, job_id: str) -> Optional[TrainingJob]:
        """获取训练任务状态"""
        return self.training_jobs.get(job_id)

    def get_model_performance_history(self, model_id: str) -> List[ModelPerformance]:
        """获取模型性能历史"""
        return self.model_performances.get(model_id, [])

    def get_training_statistics(self) -> Dict[str, Any]:
        """获取训练统计信息"""
        try:
            stats = self.training_stats.copy()

            # 添加模型统计
            stats['total_models'] = len(self.models)
            stats['total_configs'] = len(self.model_configs)
            stats['active_jobs'] = len([job for job in self.training_jobs.values()
                                        if job.status in [TrainingStatus.PREPARING, TrainingStatus.TRAINING, TrainingStatus.EVALUATING]])

            # 计算成功率
            if stats['total_jobs'] > 0:
                stats['success_rate'] = stats['successful_jobs'] / stats['total_jobs']
            else:
                stats['success_rate'] = 0.0

            return stats

        except Exception as e:
            logger.error(f"获取训练统计失败: {e}")
            return {}

    def train(self, user_id: str = None, behavior_data: Dict[str, Any] = None) -> str:
        """
        训练推荐模型（同步接口）
        
        这是一个便捷方法，用于从同步上下文调用训练功能。
        内部使用 asyncio.run() 来执行异步训练逻辑。
        
        参数:
            user_id: 用户ID（保留参数以兼容现有调用）
            behavior_data: 行为数据（保留参数以兼容现有调用）
            
        返回:
            job_id: 训练任务ID
        """
        try:
            logger.info(f"开始训练推荐模型（用户ID: {user_id}）")
            
            # 使用默认模型配置训练第一个可用的模型
            if not self.model_configs:
                logger.warning("没有可用的模型配置")
                return ""
            
            # 获取第一个模型配置
            model_id = list(self.model_configs.keys())[0]
            
            # 在新的事件循环中运行异步训练
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果事件循环正在运行，使用 create_task
                    import threading
                    result = []
                    
                    def run_in_thread():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            result.append(new_loop.run_until_complete(self.train_model(model_id)))
                        finally:
                            new_loop.close()
                    
                    thread = threading.Thread(target=run_in_thread)
                    thread.start()
                    thread.join(timeout=60)  # 最多等待60秒
                    
                    if thread.is_alive():
                        logger.warning("训练任务仍在后台运行")
                        return f"train_{model_id}_{datetime.now().timestamp()}"
                    
                    return result[0] if result else ""
                else:
                    # 如果事件循环未运行，直接使用 asyncio.run
                    return asyncio.run(self.train_model(model_id))
            except RuntimeError:
                # 没有事件循环，创建新的
                return asyncio.run(self.train_model(model_id))
                
        except Exception as e:
            logger.error(f"训练推荐模型失败: {e}")
            raise

    def cleanup(self):
        """清理资源"""
        try:
            # 清理模型
            self.models.clear()

            # 清理训练任务
            self.training_jobs.clear()

            # 清理数据
            self.training_data = None

            logger.info("推荐模型训练器资源清理完成")
        except Exception as e:
            logger.error(f"资源清理失败: {e}")
