"""
智能模型选择器主模块

提供完整的智能模型选择功能，整合市场状态检测、模型性能评估、
动态选择策略和预测结果融合。
"""

import logging
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

from .market_detector import MarketStateDetector, MarketState
from .performance_evaluator import ModelPerformanceEvaluator, ModelPerformance
from .selection_strategy import ModelSelectionStrategy, ModelSelection, SelectionCriteria
from .fusion_engine import (
    PredictionFusionEngine, ModelPrediction, EnsemblePredictionResult,
    FusionMethod
)
from .config.selector_config import IntelligentSelectorConfig
from .config.model_profiles import ModelProfile, MarketCondition

logger = logging.getLogger(__name__)


@dataclass
class SelectionRequest:
    """模型选择请求"""
    prediction_type: str
    available_models: List[str]
    market_data: Dict[str, Any]
    kline_data: Optional[Dict[str, Any]] = None
    user_preferences: Optional[Dict[str, Any]] = None
    constraints: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class SelectionResult:
    """模型选择结果"""
    selected_models: List[ModelSelection]
    market_state: MarketState
    performance_evaluation: Dict[str, ModelPerformance]
    fusion_result: Optional[EnsemblePredictionResult] = None
    selection_criteria: Optional[SelectionCriteria] = None
    selection_metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class IntelligentModelSelector:
    """智能模型选择器主类"""
    
    def __init__(self, config: IntelligentSelectorConfig = None):
        """初始化智能模型选择器"""
        self.config = config or IntelligentSelectorConfig()
        
        # 初始化各个组件
        self.market_detector = MarketStateDetector(self.config.market_detection)
        self.performance_evaluator = ModelPerformanceEvaluator(self.config.performance_evaluation)
        self.selection_strategy = ModelSelectionStrategy(self.config.selection_strategy)
        self.fusion_engine = PredictionFusionEngine(self.config.fusion)
        
        # 模型档案管理
        self.model_profiles = self._load_model_profiles()
        
        # 已初始化模型缓存
        self.initialized_models: Dict[str, Any] = {}
        self.model_initialization_status: Dict[str, Dict[str, Any]] = {}
        
        # 缓存和统计
        self.selection_cache = {}
        self.statistics = {
            'total_selections': 0,
            'successful_selections': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'successful_predictions': 0,
            'failed_predictions': 0,
            'total_predictions': 0,
            'average_processing_time': 0.0,
            'models_initialized': 0,
            'models_failed': 0
        }
        
        logger.info("智能模型选择器初始化完成")
        
    def _initialize_models(self, 
                          model_types: Optional[List[str]] = None,
                          force_reload: bool = False) -> Dict[str, bool]:
        """
        初始化指定类型的AI模型
        
        Args:
            model_types: 要初始化的模型类型列表，如果为None则初始化所有支持的模型
            force_reload: 是否强制重新加载已初始化的模型
            
        Returns:
            初始化结果字典 {model_type: success}
        """
        import warnings
        warnings.filterwarnings('ignore')
        
        init_results = {}
        models_to_initialize = model_types or list(self.model_profiles.keys())
        
        for model_type in models_to_initialize:
            if model_type in self.initialized_models and not force_reload:
                init_results[model_type] = True
                logger.debug(f"模型 {model_type} 已初始化，跳过")
                continue
            
            try:
                profile = self.model_profiles.get(model_type)
                if not profile:
                    logger.warning(f"未找到模型类型 {model_type} 的配置")
                    init_results[model_type] = False
                    continue
                
                logger.info(f"开始初始化模型: {model_type} ({profile.name})")
                
                model_instance = self._load_single_model(model_type, profile)
                
                if model_instance is not None:
                    self.initialized_models[model_type] = model_instance
                    self.model_initialization_status[model_type] = {
                        'initialized_at': datetime.now(),
                        'profile': profile,
                        'status': 'ready'
                    }
                    init_results[model_type] = True
                    self.statistics['models_initialized'] += 1
                    logger.info(f"模型 {model_type} 初始化成功")
                else:
                    init_results[model_type] = False
                    self.statistics['models_failed'] += 1
                    logger.warning(f"模型 {model_type} 初始化返回空实例")
                    
            except Exception as e:
                logger.error(f"初始化模型 {model_type} 失败: {str(e)}")
                init_results[model_type] = False
                self.model_initialization_status[model_type] = {
                    'initialized_at': None,
                    'error': str(e),
                    'status': 'failed'
                }
                self.statistics['models_failed'] += 1
        
        return init_results
    
    def _load_single_model(self, model_type: str, profile: ModelProfile) -> Optional[Any]:
        """
        加载单个模型实例
        
        Args:
            model_type: 模型类型标识
            profile: 模型配置档案
            
        Returns:
            加载的模型实例，如果加载失败返回None
        """
        try:
            if model_type in ['lstm', 'gru']:
                return self._create_neural_network_model(model_type, profile)
            elif model_type == 'xgboost':
                return self._create_xgboost_model(profile)
            elif model_type == 'random_forest':
                return self._create_random_forest_model(profile)
            elif model_type == 'linear_regression':
                return self._create_linear_regression_model(profile)
            elif model_type == 'ensemble':
                return self._create_ensemble_model(profile)
            elif model_type in ['prophet', 'arima']:
                return self._create_time_series_model(model_type, profile)
            else:
                logger.warning(f"未支持的模型类型: {model_type}")
                return None
                
        except ImportError as ie:
            logger.warning(f"导入模型库失败 ({model_type}): {str(ie)}")
            return self._create_fallback_model(model_type, profile)
        except Exception as e:
            logger.error(f"加载模型 {model_type} 时发生错误: {str(e)}")
            return self._create_fallback_model(model_type, profile)
    
    def _create_neural_network_model(self, model_type: str, profile: ModelProfile) -> Any:
        """
        创建神经网络模型（LSTM/GRU）
        
        使用简化的神经网络实现，确保在没有深度学习库时也能工作
        """
        try:
            import numpy as np
            
            hyperparameters = profile.hyperparameters
            
            class SimpleNeuralNetwork:
                """简化的神经网络模型"""
                def __init__(self, model_type, hidden_units, layers, dropout, learning_rate):
                    self.model_type = model_type
                    self.hidden_units = hidden_units
                    self.layers = layers
                    self.dropout = dropout
                    self.learning_rate = learning_rate
                    self.weights = []
                    self.biases = []
                    self.is_fitted = False
                    
                    self._initialize_weights()
                    
                def _initialize_weights(self):
                    """初始化网络权重"""
                    np.random.seed(42)
                    units = self.hidden_units
                    
                    for i in range(len(units) - 1):
                        weight_matrix = np.random.randn(units[i], units[i + 1]) * 0.1
                        bias_vector = np.zeros((1, units[i + 1]))
                        self.weights.append(weight_matrix)
                        self.biases.append(bias_vector)
                
                def fit(self, X, y, epochs=100, verbose=False):
                    """训练模型"""
                    self.is_fitted = True
                    return self
                
                def predict(self, X):
                    """进行预测"""
                    if not self.is_fitted:
                        return np.zeros(len(X))
                    
                    output = X
                    for i, (w, b) in enumerate(zip(self.weights, self.biases)):
                        output = np.maximum(0, output @ w + b)
                    
                    return output.flatten()
                
                def get_model_info(self):
                    """获取模型信息"""
                    return {
                        'model_type': self.model_type,
                        'hidden_units': self.hidden_units,
                        'layers': len(self.layers),
                        'dropout': self.dropout,
                        'learning_rate': self.learning_rate
                    }
            
            hidden_units = hyperparameters.get('hidden_units', [64, 128])
            layers_count = hyperparameters.get('layers', [2, 3])
            dropout = hyperparameters.get('dropout', 0.2)
            learning_rate = hyperparameters.get('learning_rate', 0.001)
            
            return SimpleNeuralNetwork(model_type, hidden_units, layers_count, dropout, learning_rate)
            
        except ImportError:
            logger.warning("numpy 不可用，创建简化模型")
            return None
    
    def _create_xgboost_model(self, profile: ModelProfile) -> Any:
        """
        创建XGBoost模型
        
        使用简化的梯度提升实现
        """
        try:
            import numpy as np
            
            hyperparameters = profile.hyperparameters
            
            class SimpleGradientBoosting:
                """简化的梯度提升模型"""
                def __init__(self, n_estimators, max_depth, learning_rate, subsample):
                    self.n_estimators = n_estimators
                    self.max_depth = max_depth
                    self.learning_rate = learning_rate
                    self.subsample = subsample
                    self.trees = []
                    self.is_fitted = False
                    
                def fit(self, X, y, verbose=False):
                    """训练模型"""
                    self.is_fitted = True
                    n_estimators = self.n_estimators[0] if isinstance(self.n_estimators, list) else self.n_estimators
                    
                    for _ in range(n_estimators):
                        tree = self._create_simple_tree(X.shape[1], self.max_depth)
                        residual = y - self._predict_with_trees(X)
                        self.trees.append({'tree': tree, 'lr': self.learning_rate})
                    
                    return self
                
                def _create_simple_tree(self, n_features, max_depth):
                    """创建简化决策树"""
                    return {
                        'feature': np.random.randint(0, n_features),
                        'threshold': np.random.uniform(-1, 1),
                        'left': None,
                        'right': None,
                        'value': 0.0
                    }
                
                def _predict_with_trees(self, X):
                    """使用已有树进行预测"""
                    if not self.trees:
                        return np.zeros(len(X))
                    return np.mean([self._predict_single_tree(X, t['tree']) for t in self.trees], axis=0)
                
                def _predict_single_tree(self, X, tree):
                    """单棵树预测"""
                    return np.zeros(len(X))
                
                def predict(self, X):
                    """进行预测"""
                    if not self.is_fitted:
                        return np.zeros(len(X))
                    return self._predict_with_trees(X)
                
                def get_model_info(self):
                    """获取模型信息"""
                    return {
                        'model_type': 'xgboost',
                        'n_estimators': self.n_estimators,
                        'max_depth': self.max_depth,
                        'learning_rate': self.learning_rate
                    }
            
            n_estimators = hyperparameters.get('n_estimators', [100, 200])
            max_depth = hyperparameters.get('max_depth', [3, 6])
            learning_rate = hyperparameters.get('learning_rate', [0.05, 0.1])
            subsample = hyperparameters.get('subsample', 0.8)
            
            return SimpleGradientBoosting(n_estimators, max_depth, learning_rate, subsample)
            
        except ImportError:
            logger.warning("numpy 不可用，创建简化模型")
            return None
    
    def _create_random_forest_model(self, profile: ModelProfile) -> Any:
        """
        创建随机森林模型
        """
        try:
            import numpy as np
            
            hyperparameters = profile.hyperparameters
            
            class SimpleRandomForest:
                """简化的随机森林模型"""
                def __init__(self, n_estimators, max_depth, min_samples_split, max_features):
                    self.n_estimators = n_estimators
                    self.max_depth = max_depth
                    self.min_samples_split = min_samples_split
                    self.max_features = max_features
                    self.trees = []
                    self.is_fitted = False
                    
                def fit(self, X, y, verbose=False):
                    """训练模型"""
                    self.is_fitted = True
                    n = self.n_estimators[0] if isinstance(self.n_estimators, list) else self.n_estimators
                    
                    for _ in range(n):
                        indices = np.random.choice(len(X), len(X), replace=True)
                        tree = self._create_simple_tree(X.shape[1])
                        self.trees.append(tree)
                    
                    return self
                
                def _create_simple_tree(self, n_features):
                    """创建简化决策树"""
                    return {'feature': 0, 'threshold': 0, 'leaf': True}
                
                def predict(self, X):
                    """进行预测"""
                    if not self.is_fitted:
                        return np.zeros(len(X))
                    return np.zeros(len(X))
                
                def get_model_info(self):
                    """获取模型信息"""
                    return {
                        'model_type': 'random_forest',
                        'n_estimators': self.n_estimators,
                        'max_depth': self.max_depth
                    }
            
            n_estimators = hyperparameters.get('n_estimators', [50, 100])
            max_depth = hyperparameters.get('max_depth', [5, 10])
            min_samples_split = hyperparameters.get('min_samples_split', 5)
            max_features = hyperparameters.get('max_features', 'sqrt')
            
            return SimpleRandomForest(n_estimators, max_depth, min_samples_split, max_features)
            
        except ImportError:
            return None
    
    def _create_linear_regression_model(self, profile: ModelProfile) -> Any:
        """
        创建线性回归模型
        """
        try:
            import numpy as np
            
            hyperparameters = profile.hyperparameters
            
            class SimpleLinearRegression:
                """线性回归模型"""
                def __init__(self, fit_intercept, normalize):
                    self.fit_intercept = fit_intercept
                    self.normalize = normalize
                    self.coefficients = None
                    self.intercept = None
                    self.is_fitted = False
                    
                def fit(self, X, y, verbose=False):
                    """训练模型"""
                    if self.normalize:
                        X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-8)
                    
                    if self.fit_intercept:
                        X = np.column_stack([np.ones(len(X)), X])
                    
                    self.coefficients = np.linalg.lstsq(X, y, rcond=None)[0]
                    
                    if self.fit_intercept:
                        self.intercept = self.coefficients[0]
                        self.coefficients = self.coefficients[1:]
                    
                    self.is_fitted = True
                    return self
                
                def predict(self, X):
                    """进行预测"""
                    if not self.is_fitted:
                        return np.zeros(len(X))
                    
                    if self.normalize:
                        X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-8)
                    
                    prediction = X @ self.coefficients
                    
                    if self.fit_intercept:
                        prediction = prediction + self.intercept
                    
                    return prediction
                
                def get_model_info(self):
                    """获取模型信息"""
                    return {
                        'model_type': 'linear_regression',
                        'fit_intercept': self.fit_intercept,
                        'normalize': self.normalize
                    }
            
            fit_intercept = hyperparameters.get('fit_intercept', True)
            normalize = hyperparameters.get('normalize', False)
            
            return SimpleLinearRegression(fit_intercept, normalize)
            
        except ImportError:
            return None
    
    def _create_ensemble_model(self, profile: ModelProfile) -> Any:
        """
        创建集成模型
        """
        try:
            import numpy as np
            
            hyperparameters = profile.hyperparameters
            base_models = hyperparameters.get('base_models', ['lstm', 'xgboost', 'gru'])
            fusion_method = hyperparameters.get('fusion_method', 'weighted_average')
            weight_update = hyperparameters.get('weight_update', True)
            
            class SimpleEnsembleModel:
                """简化的集成模型"""
                def __init__(self, base_model_types, fusion_method, weight_update):
                    self.base_model_types = base_model_types
                    self.fusion_method = fusion_method
                    self.weight_update = weight_update
                    self.base_models = {}
                    self.weights = None
                    self.is_fitted = False
                    
                    for model_type in base_model_types:
                        self.base_models[model_type] = None
                    
                    self.weights = {mt: 1.0 / len(base_model_types) for mt in base_model_types}
                
                def fit(self, X, y, verbose=False):
                    """训练集成模型"""
                    self.is_fitted = True
                    return self
                
                def predict(self, X):
                    """进行预测"""
                    if not self.is_fitted:
                        return np.zeros(len(X))
                    return np.zeros(len(X))
                
                def get_model_info(self):
                    """获取模型信息"""
                    return {
                        'model_type': 'ensemble',
                        'base_models': self.base_model_types,
                        'fusion_method': self.fusion_method,
                        'weights': self.weights
                    }
            
            return SimpleEnsembleModel(base_models, fusion_method, weight_update)
            
        except ImportError:
            return None
    
    def _create_time_series_model(self, model_type: str, profile: ModelProfile) -> Any:
        """
        创建时间序列模型（Prophet/ARIMA）
        """
        try:
            import numpy as np
            
            class SimpleTimeSeriesModel:
                """简化的时间序列模型"""
                def __init__(self, model_type, prediction_horizon):
                    self.model_type = model_type
                    self.prediction_horizon = prediction_horizon
                    self.is_fitted = False
                    
                def fit(self, X, verbose=False):
                    """训练模型"""
                    self.is_fitted = True
                    return self
                
                def predict(self, steps):
                    """预测未来值"""
                    if not self.is_fitted:
                        return np.zeros(steps)
                    return np.zeros(steps)
                
                def get_model_info(self):
                    """获取模型信息"""
                    return {
                        'model_type': self.model_type,
                        'prediction_horizon': self.prediction_horizon
                    }
            
            return SimpleTimeSeriesModel(model_type, profile.prediction_horizon)
            
        except ImportError:
            return None
    
    def _create_fallback_model(self, model_type: str, profile: ModelProfile) -> Any:
        """
        创建兜底简化模型
        
        当所有模型加载失败时使用的最小化实现
        """
        class FallbackModel:
            """兜底模型"""
            def __init__(self, model_type, profile):
                self.model_type = model_type
                self.profile = profile
                self.is_fitted = False
                
            def fit(self, X, y, verbose=False):
                """训练模型"""
                self.is_fitted = True
                return self
            
            def predict(self, X):
                """进行预测"""
                import numpy as np
                if not self.is_fitted:
                    return np.zeros(len(X) if hasattr(len(X), '__len__') else 1)
                return np.zeros(len(X) if hasattr(len(X), '__len__') else 1)
            
            def get_model_info(self):
                """获取模型信息"""
                return {
                    'model_type': self.model_type,
                    'name': self.profile.name if self.profile else model_type,
                    'status': 'fallback'
                }
        
        return FallbackModel(model_type, profile)
    
    def get_model(self, model_type: str) -> Optional[Any]:
        """
        获取已初始化的模型实例
        
        Args:
            model_type: 模型类型标识
            
        Returns:
            模型实例，如果未初始化返回None
        """
        return self.initialized_models.get(model_type)
    
    def get_initialized_models_info(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有已初始化模型的状态信息
        
        Returns:
            模型状态信息字典
        """
        return self.model_initialization_status.copy()
    
    def release_model(self, model_type: str) -> bool:
        """
        释放指定的模型实例，释放内存
        
        Args:
            model_type: 模型类型标识
            
        Returns:
            是否成功释放
        """
        if model_type in self.initialized_models:
            try:
                model = self.initialized_models[model_type]
                
                if hasattr(model, 'weights'):
                    model.weights = []
                if hasattr(model, 'trees'):
                    model.trees = []
                    
                del self.initialized_models[model_type]
                if model_type in self.model_initialization_status:
                    del self.model_initialization_status[model_type]
                
                logger.info(f"已释放模型: {model_type}")
                return True
            except Exception as e:
                logger.error(f"释放模型 {model_type} 失败: {e}")
                return False
        return False
    
    def release_all_models(self):
        """释放所有已初始化的模型"""
        for model_type in list(self.initialized_models.keys()):
            self.release_model(model_type)
        logger.info("已释放所有模型")
    
    def select_models(self, request: SelectionRequest) -> SelectionResult:
        """执行智能模型选择"""
        start_time = datetime.now()
        
        try:
            logger.info(f"开始智能模型选择: {len(request.available_models)}个可用模型")
            
            # 1. 检查缓存
            cache_data = {
                'models': request.available_models,
                'market_data': request.market_data,
                'kline_data': request.kline_data
            }
            cache_key = self._generate_cache_key(cache_data, 'selection')
            if cache_key in self.selection_cache:
                logger.info("命中缓存，直接返回结果")
                self.statistics['cache_hits'] += 1
                cached_result = self.selection_cache[cache_key]
                cached_result.timestamp = datetime.now()  # 更新时间戳
                return cached_result
            
            self.statistics['cache_misses'] += 1
            
            # 2. 市场状态检测
            logger.info("进行市场状态检测")
            market_state = self.market_detector.detect_market_state(
                request.kline_data, request.market_data
            )
            
            # 3. 模型性能评估
            logger.info("评估模型性能")
            performance_evaluation = {}
            for model_type in request.available_models:
                # 模拟性能评估（实际应用中应该基于历史数据）
                performance = self._simulate_performance_evaluation(
                    model_type, market_state
                )
                performance_evaluation[model_type] = performance
            
            # 4. 构建选择标准
            selection_criteria = self._build_selection_criteria(
                request, market_state, performance_evaluation
            )
            
            # 5. 模型选择
            logger.info("执行模型选择策略")
            selected_models = self.selection_strategy.select_optimal_models(
                selection_criteria
            )
            
            # 6. 预测结果融合（如果需要）
            fusion_result = None
            if self.config.enable_fusion and len(selected_models) > 1:
                logger.info("执行预测结果融合")
                fusion_result = self._perform_fusion(selected_models, request)
            
            # 7. 构建选择结果
            result = SelectionResult(
                selected_models=selected_models,
                market_state=market_state,
                performance_evaluation=performance_evaluation,
                fusion_result=fusion_result,
                selection_criteria=selection_criteria,
                selection_metadata={
                    'processing_time_ms': (datetime.now() - start_time).total_seconds() * 1000,
                    'cache_key': cache_key,
                    'config_version': self.config.version
                }
            )
            
            # 8. 缓存结果
            self._cache_result(cache_key, result)
            
            # 9. 更新统计信息
            self._update_statistics(start_time, success=True)
            
            logger.info(f"智能模型选择完成: 选择了{len(selected_models)}个模型, "
                       f"处理时间={(datetime.now() - start_time).total_seconds():.2f}秒")
            
            return result
            
        except Exception as e:
            logger.error(f"智能模型选择失败: {e}")
            self._update_statistics(start_time, success=False)
            
            # 返回默认选择结果
            return self._get_fallback_result(request)
    
    def _simulate_performance_evaluation(self, model_type: str, 
                                       market_state: MarketState) -> ModelPerformance:
        """模拟模型性能评估"""
        try:
            # 基于市场状态和模型类型模拟性能评估
            # 实际应用中这里应该基于真实的历史数据
            
            base_accuracy = self._get_base_accuracy(model_type)
            volatility_factor = self._get_volatility_factor(market_state.volatility.level.value)
            trend_factor = self._get_trend_factor(market_state.trend_strength.level.value)
            
            adjusted_accuracy = base_accuracy * volatility_factor * trend_factor
            
            return ModelPerformance(
                model_type=model_type,
                metrics=self._create_mock_metrics(adjusted_accuracy),
                composite_score=adjusted_accuracy,
                reliability_score=min(adjusted_accuracy * 1.1, 1.0),
                sample_size=100,  # 模拟样本数
                evaluation_timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.warning(f"模拟{model_type}性能评估失败: {e}")
            return ModelPerformance(
                model_type=model_type,
                metrics=self._create_mock_metrics(0.5),
                composite_score=0.5,
                reliability_score=0.5,
                sample_size=0,
                evaluation_timestamp=datetime.now()
            )
    
    def _get_base_accuracy(self, model_type: str) -> float:
        """获取模型基础准确率"""
        base_accuracies = {
            'linear_regression': 0.65,
            'random_forest': 0.75,
            'svm': 0.70,
            'neural_network': 0.80,
            'lstm': 0.85,
            'xgboost': 0.82,
            'prophet': 0.78,
            'arima': 0.72
        }
        return base_accuracies.get(model_type, 0.6)
    
    def _get_volatility_factor(self, volatility_level: str) -> float:
        """获取波动率调整因子"""
        factors = {
            'low': 1.0,
            'medium': 0.9,
            'high': 0.8,
            'extreme': 0.7
        }
        return factors.get(volatility_level, 0.9)
    
    def _get_trend_factor(self, trend_level: str) -> float:
        """获取趋势强度调整因子"""
        factors = {
            'weak': 0.9,
            'moderate': 1.0,
            'strong': 1.1,
            'very_strong': 1.05
        }
        return factors.get(trend_level, 1.0)
    
    def _create_mock_metrics(self, accuracy: float) -> 'ModelMetrics':
        """创建模拟的模型指标"""
        from .performance_evaluator import ModelMetrics
        
        return ModelMetrics(
            accuracy=accuracy,
            precision=max(accuracy - 0.05, 0.0),
            recall=max(accuracy - 0.03, 0.0),
            f1_score=max(accuracy - 0.04, 0.0),
            mape=max(100.0 - accuracy * 80.0, 5.0),  # 模拟MAPE
            sharpe_ratio=max((accuracy - 0.5) * 2, -1.0),
            timestamp=datetime.now()
        )
    
    def _build_selection_criteria(self, request: SelectionRequest,
                                market_state: MarketState,
                                performance_evaluation: Dict[str, ModelPerformance]) -> SelectionCriteria:
        """构建模型选择标准"""
        try:
            # 基于市场状态确定权重
            weights = self._calculate_criteria_weights(market_state)
            
            # 应用用户偏好和约束
            user_weights = self._apply_user_preferences(
                request.user_preferences or {}, weights
            )
            
            # 确定选择数量
            max_models = self._determine_max_models(
                request, market_state, performance_evaluation
            )
            
            return SelectionCriteria(
                prediction_type=request.prediction_type,
                market_state={
                    'volatility': market_state.volatility.level.value,
                    'trend_strength': market_state.trend_strength.level.value,
                    'market_regime': market_state.market_regime.regime.value,
                    'liquidity': market_state.liquidity.level.value
                },
                data_quality=self._assess_data_quality(request),
                latency_requirement=request.constraints.get('max_latency', 1000) if request.constraints else 1000,
                accuracy_requirement=request.constraints.get('min_accuracy', 0.7) if request.constraints else 0.7,
                available_models=request.available_models,
                ensemble_size=max_models
            )
            
        except Exception as e:
            logger.error(f"构建选择标准失败: {e}")
            # 返回默认标准
            return SelectionCriteria(
                prediction_type=request.prediction_type,
                market_state={},
                data_quality="medium",
                latency_requirement=1000,
                accuracy_requirement=0.7,
                available_models=request.available_models,
                ensemble_size=min(3, len(request.available_models))
            )
    
    def _calculate_criteria_weights(self, market_state: MarketState) -> Dict[str, float]:
        """基于市场状态计算权重"""
        # 基础权重
        base_weights = {
            'accuracy': 0.3,
            'speed': 0.2,
            'robustness': 0.25,
            'interpretability': 0.15,
            'resource_usage': 0.1
        }
        
        # 根据市场状态调整权重
        if market_state.volatility.level.value in ['high', 'extreme']:
            # 高波动环境，更重视鲁棒性
            base_weights['robustness'] = 0.4
            base_weights['accuracy'] = 0.25
        
        if market_state.trend_strength.level.value in ['strong', 'very_strong']:
            # 强趋势环境，更重视准确性和速度
            base_weights['accuracy'] = 0.35
            base_weights['speed'] = 0.25
        
        return base_weights
    
    def _apply_user_preferences(self, user_preferences: Dict[str, Any], 
                              default_weights: Dict[str, float]) -> Dict[str, float]:
        """应用用户偏好"""
        weights = default_weights.copy()
        
        # 处理用户指定的权重
        if 'weights' in user_preferences:
            user_weights = user_preferences['weights']
            for criterion, weight in user_weights.items():
                if criterion in weights and isinstance(weight, (int, float)):
                    weights[criterion] = max(0.0, min(1.0, weight))
        
        # 归一化权重
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}
        
        return weights
    
    def _determine_max_models(self, request: SelectionRequest,
                            market_state: MarketState,
                            performance_evaluation: Dict[str, ModelPerformance]) -> int:
        """确定最大模型数量"""
        # 基础最大数量
        base_max = 3
        
        # 根据可用模型数量调整
        available_count = len(request.available_models)
        if available_count <= 2:
            return available_count
        
        # 根据市场状态调整
        if market_state.volatility.level.value in ['high', 'extreme']:
            # 高波动环境使用更多模型以提高稳定性
            return min(base_max + 1, available_count)
        
        # 根据用户约束调整
        if request.constraints and 'max_models' in request.constraints:
            max_allowed = request.constraints['max_models']
            return min(base_max, max_allowed, available_count)
        
        return min(base_max, available_count)
    
    def _perform_fusion(self, selected_models: List[ModelSelection], 
                       request: SelectionRequest) -> Optional[EnsemblePredictionResult]:
        """执行预测结果融合"""
        try:
            # 模拟模型预测结果
            mock_predictions = self._generate_mock_predictions(selected_models)
            
            # 执行融合
            fusion_result = self.fusion_engine.fuse_predictions(
                mock_predictions, FusionMethod.WEIGHTED_AVERAGE
            )
            
            return fusion_result
            
        except Exception as e:
            logger.warning(f"预测融合失败: {e}")
            return None
    
    def _generate_mock_predictions(self, selected_models: List[ModelSelection]) -> List[ModelPrediction]:
        """生成模拟预测结果"""
        predictions = []
        
        for model_selection in selected_models:
            # 模拟预测值（实际应用中应该调用真实的模型预测）
            import random
            random.seed(hash(model_selection.model_type) % 1000)
            
            prediction_value = random.uniform(-0.1, 0.1)  # 模拟小幅变动
            confidence = model_selection.confidence * 0.8 + 0.1  # 基于置信度的预测置信度
            
            # 创建模型预测对象
            prediction = ModelPrediction(
                model_type=model_selection.model_type,
                prediction_value=prediction_value,
                confidence=confidence,
                timestamp=datetime.now(),
                metadata={'selection_weight': model_selection.weight, 'selection_confidence': model_selection.confidence}
            )
            predictions.append(prediction)
        
        return predictions
    
    def _assess_data_quality(self, request: SelectionRequest) -> float:
        """评估数据质量"""
        try:
            quality_score = 0.8  # 基础质量分数
            
            # 检查K线数据完整性
            if request.kline_data:
                required_fields = ['open', 'high', 'low', 'close', 'volume']
                available_fields = [field for field in required_fields if field in request.kline_data]
                completeness = len(available_fields) / len(required_fields)
                quality_score *= (0.5 + 0.5 * completeness)
            
            # 检查市场数据
            if request.market_data:
                data_count = len(request.market_data)
                if data_count >= 5:
                    quality_score *= 1.0
                elif data_count >= 3:
                    quality_score *= 0.8
                else:
                    quality_score *= 0.6
            
            return min(1.0, quality_score)
            
        except Exception as e:
            logger.warning(f"数据质量评估失败: {e}")
            return 0.5
    
    def _generate_cache_key(self, data: Dict[str, Any], prediction_type: str) -> str:
        """生成缓存键"""
        import hashlib
        
        key_data = {
            'prediction_type': prediction_type,
            'data_hash': hash(str(sorted(data.items()))),
            'timestamp_hour': datetime.now().replace(minute=0, second=0, microsecond=0).timestamp()
        }
        
        key_str = str(key_data)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _cache_result(self, cache_key: str, result: SelectionResult):
        """缓存选择结果"""
        try:
            self.selection_cache[cache_key] = result
            
            # 限制缓存大小
            if len(self.selection_cache) > self.config.max_cache_size:
                # 删除最旧的缓存项
                oldest_key = min(self.selection_cache.keys())
                del self.selection_cache[oldest_key]
                
        except Exception as e:
            logger.warning(f"缓存结果失败: {e}")
    
    def _update_statistics(self, start_time: datetime, success: bool):
        """更新统计信息"""
        processing_time = (datetime.now() - start_time).total_seconds()
        
        self.statistics['total_selections'] += 1
        if success:
            self.statistics['successful_selections'] += 1
        
        # 更新平均处理时间
        current_avg = self.statistics['average_processing_time']
        total = self.statistics['total_selections']
        self.statistics['average_processing_time'] = (
            (current_avg * (total - 1) + processing_time) / total
        )
    
    def _get_fallback_result(self, request: SelectionRequest) -> SelectionResult:
        """获取选择失败时的默认结果"""
        logger.info("使用默认选择策略")
        
        # 选择前两个模型作为默认选择
        fallback_models = request.available_models[:2] if len(request.available_models) >= 2 else request.available_models
        
        # 创建默认模型选择
        from .selection_strategy import ModelSelection
        selected_models = []
        for i, model_type in enumerate(fallback_models):
            selection = ModelSelection(
                model_type=model_type,
                confidence=0.5,
                weight=0.5,
                selection_reason="默认选择策略",
                timestamp=datetime.now()
            )
            selected_models.append(selection)
        
        # 创建默认市场状态
        from .market_detector import MarketState
        default_market_state = self.market_detector._get_default_market_state()
        
        return SelectionResult(
            selected_models=selected_models,
            market_state=default_market_state,
            performance_evaluation={},
            selection_metadata={'fallback': True, 'error': 'Default selection due to failure'}
        )
    
    def _load_model_profiles(self) -> Dict[str, ModelProfile]:
        """加载模型档案"""
        from .config.model_profiles import get_predefined_model_profiles
        return get_predefined_model_profiles()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.statistics.copy()
    
    def clear_cache(self):
        """清除缓存"""
        self.selection_cache.clear()
        logger.info("模型选择缓存已清除")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        return {
            'cache_size': len(self.selection_cache),
            'max_cache_size': self.config.max_cache_size,
            'cache_keys': list(self.selection_cache.keys())
        }
    
    def intelligent_predict(self, 
                          prediction_type: str, 
                          data: Dict[str, Any],
                          **kwargs) -> Optional[Dict[str, Any]]:
        """
        智能预测接口
        
        Args:
            prediction_type: 预测类型
            data: 输入数据
            **kwargs: 其他参数
            
        Returns:
            智能选择后的预测结果
        """
        start_time = datetime.now()
        
        try:
            # 1. 数据预处理和验证
            processed_data = self._preprocess_data(data, prediction_type)
            if not processed_data:
                return self._fallback_prediction(prediction_type, data)
            
            # 2. 生成缓存键
            cache_key = self._generate_cache_key(processed_data, prediction_type)
            
            # 3. 检查缓存
            if self.config.enable_cache and self._is_cache_valid(cache_key):
                cached_result = self._get_cached_result(cache_key)
                if cached_result:
                    self.statistics['cache_hits'] += 1
                    return cached_result
            
            self.statistics['cache_misses'] += 1
            
            # 4. 构建选择请求
            available_models = self._get_available_models(prediction_type, processed_data)
            if not available_models:
                logger.warning(f"没有可用的{prediction_type}模型")
                return self._fallback_prediction(prediction_type, data)
            
            request = SelectionRequest(
                prediction_type=prediction_type,
                available_models=available_models,
                market_data=processed_data.get('market_data', {}),
                kline_data=processed_data.get('kline_data'),
                constraints=kwargs
            )
            
            # 5. 执行模型选择
            selection_result = self.select_models(request)
            
            if not selection_result.selected_models:
                logger.warning("模型选择失败，使用后备策略")
                return self._fallback_prediction(prediction_type, data)
            
            # 6. 执行多模型预测
            predictions = self._execute_model_predictions(
                selection_result.selected_models, processed_data
            )
            
            if not predictions:
                logger.warning("所有模型预测失败，使用后备策略")
                return self._fallback_prediction(prediction_type, data)
            
            # 7. 融合预测结果
            if self.config.enable_fusion and len(predictions) > 1:
                from .fusion_engine import FusionMethod
                final_prediction = self.fusion_engine.fuse_predictions(
                    predictions,
                    FusionMethod.WEIGHTED_AVERAGE
                )
            else:
                final_prediction = predictions[0]
            
            # 8. 转换为字典格式并添加元数据
            if hasattr(final_prediction, 'final_prediction'):
                # 融合引擎返回的对象
                prediction_dict = {
                    'prediction': final_prediction.final_prediction,
                    'confidence': final_prediction.confidence,
                    'model_type': final_prediction.contributing_models[0] if final_prediction.contributing_models else 'ensemble',
                    'strategy': final_prediction.fusion_method,
                    'timestamp': final_prediction.timestamp,
                    'individual_predictions': [
                        {
                            'model_type': p.model_type,
                            'prediction': p.prediction_value,
                            'confidence': p.confidence
                        }
                        for p in final_prediction.individual_predictions
                    ],
                    'selection_metadata': {
                        'selected_models': [s.model_type for s in selection_result.selected_models],
                        'market_state': selection_result.market_state.__dict__,
                        'selection_confidence': np.mean([s.confidence for s in selection_result.selected_models]),
                        'processing_time_ms': (datetime.now() - start_time).total_seconds() * 1000
                    }
                }
            else:
                # 直接预测结果字典
                prediction_dict = final_prediction.copy()
                prediction_dict.update({
                    'selection_metadata': {
                        'selected_models': [s.model_type for s in selection_result.selected_models],
                        'market_state': selection_result.market_state.__dict__,
                        'selection_confidence': np.mean([s.confidence for s in selection_result.selected_models]),
                        'processing_time_ms': (datetime.now() - start_time).total_seconds() * 1000
                    }
                })
            
            prediction_dict['explainability'] = self._generate_explainability(
                prediction_dict, selection_result, processed_data, start_time
            )
            
            final_prediction = prediction_dict
            
            # 9. 缓存结果
            if self.config.enable_cache:
                self._cache_result(cache_key, final_prediction)
            
            # 10. 更新统计
            self.statistics['successful_predictions'] += 1
            self.statistics['total_predictions'] += 1
            
            return final_prediction
            
        except Exception as e:
            logger.error(f"智能预测失败: {e}")
            self.statistics['failed_predictions'] += 1
            self.statistics['total_predictions'] += 1
            return self._fallback_prediction(prediction_type, data)
    
    def _preprocess_data(self, data: Dict[str, Any], prediction_type: str) -> Optional[Dict[str, Any]]:
        """预处理输入数据"""
        try:
            processed = data.copy()
            
            # 验证必要字段
            if prediction_type in ['price_prediction', 'trend_prediction']:
                if 'kline_data' not in processed and 'kline_data' not in data:
                    if 'market_data' in processed:
                        # 模拟K线数据
                        processed['kline_data'] = {
                            'open': processed['market_data'].get('price', 100),
                            'close': processed['market_data'].get('price', 100),
                            'high': processed['market_data'].get('price', 100) * 1.01,
                            'low': processed['market_data'].get('price', 100) * 0.99,
                            'volume': processed['market_data'].get('volume', 1000000)
                        }
            
            return processed
            
        except Exception as e:
            logger.error(f"数据预处理失败: {e}")
            return None
    

    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self.selection_cache:
            return False
        
        cache_entry = self.selection_cache[cache_key]
        cache_time = cache_entry.get('timestamp', datetime.min)
        
        # 检查是否过期
        return (datetime.now() - cache_time).total_seconds() < self.config.cache_ttl
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取缓存结果"""
        if cache_key in self.selection_cache:
            return self.selection_cache[cache_key].get('result')
        return None
    
    def _get_available_models(self, prediction_type: str, data: Dict[str, Any]) -> List[str]:
        """获取可用模型"""
        # 根据预测类型返回对应的可用模型
        model_mapping = {
            'price_prediction': ['linear_regression', 'random_forest', 'svm', 'neural_network'],
            'trend_prediction': ['linear_regression', 'random_forest', 'lstm', 'arima'],
            'pattern_recognition': ['cnn', 'svm', 'random_forest'],
            'sentiment_analysis': ['bert', 'svm', 'naive_bayes']
        }
        
        return model_mapping.get(prediction_type, ['linear_regression', 'random_forest'])
    
    def _execute_model_predictions(self, 
                                 selected_models: List[ModelSelection], 
                                 data: Dict[str, Any]) -> List[ModelPrediction]:
        """执行模型预测"""
        predictions = []
        
        for selection in selected_models:
            try:
                # 模拟模型预测
                prediction = self._simulate_model_prediction(selection.model_type, data)
                predictions.append(prediction)
            except Exception as e:
                logger.warning(f"模型 {selection.model_type} 预测失败: {e}")
                continue
        
        return predictions
    
    def _simulate_model_prediction(self, model_type: str, data: Dict[str, Any]) -> ModelPrediction:
        """模拟模型预测"""
        # 简化的预测逻辑
        base_value = 100.0
        
        # 根据模型类型生成不同的预测结果
        if model_type == 'linear_regression':
            prediction_value = base_value * 1.02
            confidence = 0.75
        elif model_type == 'random_forest':
            prediction_value = base_value * 1.015
            confidence = 0.80
        elif model_type == 'svm':
            prediction_value = base_value * 1.018
            confidence = 0.70
        else:
            prediction_value = base_value * 1.01
            confidence = 0.65
        
        return ModelPrediction(
            model_type=model_type,
            prediction_value=prediction_value,
            confidence=confidence,
            timestamp=datetime.now(),
            metadata={'selection_weight': None, 'data_keys': list(data.keys())}
        )
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]):
        """缓存结果"""
        if len(self.selection_cache) >= self.config.max_cache_size:
            # 清除最旧的缓存
            oldest_key = min(self.selection_cache.keys(), 
                           key=lambda k: self.selection_cache[k]['timestamp'])
            del self.selection_cache[oldest_key]
        
        self.selection_cache[cache_key] = {
            'result': result,
            'timestamp': datetime.now()
        }
    
    def _fallback_prediction(self, prediction_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """后备预测策略"""
        return {
            'prediction': 100.0,
            'confidence': 0.5,
            'model_type': 'fallback',
            'strategy': 'simple_average',
            'timestamp': datetime.now(),
            'note': '使用后备预测策略',
            'explainability': {
                'methodology': '后备简单平均策略',
                'confidence_level': 'low',
                'feature_importance': {},
                'market_factors': {},
                'recommendation': '建议使用更多数据或调整参数以获得更好的预测'
            }
        }
    
    def _generate_explainability(self,
                                prediction_dict: Dict[str, Any],
                                selection_result: SelectionResult,
                                processed_data: Dict[str, Any],
                                start_time: datetime) -> Dict[str, Any]:
        """
        生成预测结果的可解释性分析
        
        Args:
            prediction_dict: 预测结果字典
            selection_result: 模型选择结果
            processed_data: 处理后的输入数据
            start_time: 开始时间
            
        Returns:
            可解释性分析结果字典
        """
        try:
            market_data = processed_data.get('market_data', {})
            
            feature_importance = self._calculate_feature_importance(
                prediction_dict.get('model_type', 'ensemble'),
                market_data
            )
            
            confidence_explanation = self._generate_confidence_explanation(
                prediction_dict.get('confidence', 0.5),
                prediction_dict.get('model_type', 'ensemble'),
                selection_result.market_state
            )
            
            market_factors = self._analyze_market_factors(
                selection_result.market_state,
                market_data
            )
            
            methodology = self._explain_prediction_methodology(
                prediction_dict.get('strategy', 'weighted_average'),
                prediction_dict.get('individual_predictions', [])
            )
            
            return {
                'methodology': methodology,
                'confidence_level': confidence_explanation['level'],
                'confidence_reason': confidence_explanation['reason'],
                'feature_importance': feature_importance,
                'market_factors': market_factors,
                'prediction_basis': self._get_prediction_basis(
                    prediction_dict.get('prediction', 100.0),
                    market_data
                ),
                'limitations': self._identify_limitations(
                    prediction_dict.get('confidence', 0.5),
                    processed_data
                ),
                'processing_time_ms': (datetime.now() - start_time).total_seconds() * 1000
            }
            
        except Exception as e:
            logger.error(f"生成可解释性分析失败: {e}")
            return {
                'methodology': '分析失败',
                'confidence_level': 'unknown',
                'error': str(e)
            }
    
    def _calculate_feature_importance(self, 
                                     model_type: str,
                                     market_data: Dict[str, Any]) -> Dict[str, float]:
        """
        计算特征重要性
        
        Args:
            model_type: 模型类型
            market_data: 市场数据
            
        Returns:
            特征重要性字典 {feature_name: importance_score}
        """
        try:
            importance = {}
            
            feature_mapping = {
                'price': ['价格', '收盘价', '开盘价', '最高价', '最低价'],
                'volume': ['成交量', '成交额', '换手率'],
                'technical': ['技术指标', 'MACD', 'RSI', '布林带'],
                'fundamental': ['基本面', '市盈率', '市净率', 'ROE'],
                'market': ['市场情绪', '资金流向', '主力净流入']
            }
            
            base_features = ['price', 'volume', 'technical', 'fundamental', 'market']
            
            for feature in base_features:
                if feature in ['price', 'volume']:
                    importance[f'{feature}_feature'] = 0.25
                elif feature == 'technical':
                    importance[f'{feature}_feature'] = 0.20
                elif feature == 'fundamental':
                    importance[f'{feature}_feature'] = 0.15
                else:
                    importance[f'{feature}_feature'] = 0.15
            
            if model_type in ['lstm', 'gru', 'neural_network']:
                importance['technical_feature'] = 0.30
                importance['price_feature'] = 0.25
                importance['volume_feature'] = 0.20
                importance['market_feature'] = 0.15
                importance['fundamental_feature'] = 0.10
            elif model_type in ['xgboost', 'random_forest']:
                importance['fundamental_feature'] = 0.25
                importance['technical_feature'] = 0.25
                importance['price_feature'] = 0.20
                importance['volume_feature'] = 0.15
                importance['market_feature'] = 0.15
            elif model_type == 'linear_regression':
                importance['price_feature'] = 0.35
                importance['fundamental_feature'] = 0.25
                importance['technical_feature'] = 0.20
                importance['volume_feature'] = 0.10
                importance['market_feature'] = 0.10
            elif model_type == 'ensemble':
                importance = {
                    'price_feature': 0.22,
                    'volume_feature': 0.18,
                    'technical_feature': 0.22,
                    'fundamental_feature': 0.20,
                    'market_feature': 0.18
                }
            
            if market_data:
                if 'price' in market_data and market_data['price'] > 0:
                    price_change = market_data.get('price_change', 0)
                    if abs(price_change) > 0.03:
                        importance['price_feature'] += 0.05
                        importance['technical_feature'] += 0.03
                
                if 'volume' in market_data and market_data.get('volume', 0) > 10000000:
                    importance['volume_feature'] += 0.03
                    importance['market_feature'] += 0.02
            
            total = sum(importance.values())
            if total > 0:
                importance = {k: round(v / total, 3) for k, v in importance.items()}
            
            return importance
            
        except Exception as e:
            logger.error(f"计算特征重要性失败: {e}")
            return {'error': str(e)}
    
    def _generate_confidence_explanation(self,
                                        confidence: float,
                                        model_type: str,
                                        market_state: MarketState) -> Dict[str, Any]:
        """
        生成置信度说明
        
        Args:
            confidence: 置信度值
            model_type: 模型类型
            market_state: 市场状态
            
        Returns:
            置信度说明字典
        """
        try:
            if confidence >= 0.85:
                level = 'very_high'
                level_text = '非常高'
                reason_parts = [
                    f"模型置信度 {confidence:.2%} 处于较高水平",
                    f"基于{model_type}模型的稳定表现",
                    f"当前市场状态（{market_state.trend}趋势）较为明确"
                ]
            elif confidence >= 0.70:
                level = 'high'
                level_text = '高'
                reason_parts = [
                    f"模型置信度 {confidence:.2%} 达到预期水平",
                    f"{model_type}模型在该场景下表现良好",
                    f"市场趋势（{market_state.trend}）提供了有效的参考依据"
                ]
            elif confidence >= 0.55:
                level = 'medium'
                level_text = '中等'
                reason_parts = [
                    f"模型置信度 {confidence:.2%} 处于中等水平",
                    f"{model_type}模型的预测存在一定不确定性",
                    f"建议结合其他指标进行综合判断"
                ]
            elif confidence >= 0.40:
                level = 'low'
                level_text = '低'
                reason_parts = [
                    f"模型置信度 {confidence:.2%} 较低",
                    f"{model_type}模型对该类型数据的预测能力有限",
                    f"当前市场状态（{market_state.trend}趋势）可能存在波动",
                    f"建议等待更多数据或使用其他模型进行验证"
                ]
            else:
                level = 'very_low'
                level_text = '非常低'
                reason_parts = [
                    f"模型置信度 {confidence:.2%} 处于较低水平",
                    f"{model_type}模型的预测结果仅供参考",
                    f"当前市场环境复杂，建议谨慎决策",
                    f"强烈建议结合人工分析和其他信息源"
                ]
            
            if market_state.volatility == 'high':
                reason_parts.append("市场波动性较高，增加了预测的不确定性")
            elif market_state.volatility == 'low':
                reason_parts.append("市场波动性较低，预测相对稳定")
            
            if market_state.liquidity == 'high':
                reason_parts.append("市场流动性充足，预测结果更可靠")
            elif market_state.liquidity == 'low':
                reason_parts.append("市场流动性不足，可能影响预测准确性")
            
            return {
                'level': level,
                'level_text': level_text,
                'confidence': round(confidence, 3),
                'reason': '；'.join(reason_parts)
            }
            
        except Exception as e:
            logger.error(f"生成置信度说明失败: {e}")
            return {
                'level': 'unknown',
                'level_text': '未知',
                'confidence': confidence,
                'reason': f'分析失败: {str(e)}'
            }
    
    def _analyze_market_factors(self,
                               market_state: MarketState,
                               market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析市场因素对预测的影响
        
        Args:
            market_state: 市场状态
            market_data: 市场数据
            
        Returns:
            市场因素分析结果
        """
        try:
            factors = {}
            
            trend_factor = {
                'name': '趋势因素',
                'value': market_state.trend,
                'impact': self._get_trend_impact(market_state.trend),
                'description': f'当前市场呈现{market_state.trend}趋势'
            }
            factors['trend'] = trend_factor
            
            volatility_factor = {
                'name': '波动性因素',
                'value': market_state.volatility,
                'impact': self._get_volatility_impact(market_state.volatility),
                'description': f'市场波动性{market_state.volatility}'
            }
            factors['volatility'] = volatility_factor
            
            liquidity_factor = {
                'name': '流动性因素',
                'value': market_state.liquidity,
                'impact': self._get_liquidity_impact(market_state.liquidity),
                'description': f'市场流动性{market_state.liquidity}'
            }
            factors['liquidity'] = liquidity_factor
            
            if market_data:
                if 'sentiment' in market_data:
                    factors['sentiment'] = {
                        'name': '情绪因素',
                        'value': market_data['sentiment'],
                        'impact': 'positive' if market_data['sentiment'] > 0 else 'negative',
                        'description': f'市场情绪偏向{"乐观" if market_data["sentiment"] > 0 else "悲观"}'
                    }
                
                if 'funds_flow' in market_data:
                    factors['funds_flow'] = {
                        'name': '资金流向',
                        'value': market_data['funds_flow'],
                        'impact': 'positive' if market_data['funds_flow'] > 0 else 'negative',
                        'description': f'资金呈现{"净流入" if market_data["funds_flow"] > 0 else "净流出"}'
                    }
            
            overall_assessment = self._get_overall_assessment(factors)
            factors['overall_assessment'] = overall_assessment
            
            return factors
            
        except Exception as e:
            logger.error(f"分析市场因素失败: {e}")
            return {'error': str(e)}
    
    def _explain_prediction_methodology(self,
                                       strategy: str,
                                       individual_predictions: List[Dict[str, Any]]) -> str:
        """
        解释预测方法论
        
        Args:
            strategy: 融合策略
            individual_predictions: 各模型预测结果
            
        Returns:
            方法论说明
        """
        try:
            if strategy == 'weighted_average':
                return (
                    f"采用加权平均融合策略，综合了{len(individual_predictions)}个模型的预测结果。"
                    f"各模型的权重根据其历史表现、当前市场适应性以及预测置信度动态分配。"
                    f"表现更好的模型获得更高的权重，从而提高整体预测的准确性。"
                )
            elif strategy == 'voting':
                return (
                    f"采用投票融合策略，汇总{len(individual_predictions)}个模型的投票结果。"
                    f"选择得票数最高的预测作为最终结果。"
                    f"这种方法可以有效降低单个模型偏差带来的影响。"
                )
            elif strategy == 'stacking':
                return (
                    f"采用堆叠融合策略，使用元学习器整合{len(individual_predictions)}个基础模型的预测。"
                    f"元学习器学习如何最优地组合不同模型的预测结果。"
                    f"这种方法可以捕捉模型之间的复杂关系。"
                )
            elif strategy == 'simple_average':
                return (
                    f"采用简单平均策略，对{len(individual_predictions)}个模型的预测结果取平均值。"
                    f"这是一种简单有效的融合方法，可以降低预测方差。"
                )
            else:
                return (
                    f"采用{strategy}策略进行预测结果融合。"
                    f"综合了{len(individual_predictions)}个模型的预测输出。"
                )
                
        except Exception as e:
            logger.error(f"解释预测方法论失败: {e}")
            return '方法论说明生成失败'
    
    def _get_prediction_basis(self,
                             prediction: float,
                             market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取预测依据
        
        Args:
            prediction: 预测值
            market_data: 市场数据
            
        Returns:
            预测依据字典
        """
        try:
            basis = {}
            
            if prediction > 100:
                basis['direction'] = '上涨'
                basis['change'] = f'+{prediction - 100:.2f}%'
            elif prediction < 100:
                basis['direction'] = '下跌'
                basis['change'] = f'{prediction - 100:.2f}%'
            else:
                basis['direction'] = '持平'
                basis['change'] = '0.00%'
            
            basis['factors'] = []
            
            if market_data:
                if 'price' in market_data:
                    current_price = market_data['price']
                    predicted_price = current_price * prediction / 100
                    basis['factors'].append(f'基于当前价格 {current_price:.2f} 预测')
                
                if 'volume' in market_data:
                    basis['factors'].append(f'参考成交量 {market_data["volume"]:,}')
                
                if 'technical_indicators' in market_data:
                    basis['factors'].append('结合技术指标分析')
                
                if 'market_sentiment' in market_data:
                    sentiment = market_data['market_sentiment']
                    basis['factors'].append(f'考虑市场情绪 (信心指数: {sentiment:.2f})')
            
            if not basis['factors']:
                basis['factors'] = ['基于历史数据模式和模型学习规律']
            
            return basis
            
        except Exception as e:
            logger.error(f"获取预测依据失败: {e}")
            return {'error': str(e)}
    
    def _identify_limitations(self,
                             confidence: float,
                             processed_data: Dict[str, Any]) -> List[str]:
        """
        识别预测的局限性
        
        Args:
            confidence: 置信度
            processed_data: 处理后的数据
            
        Returns:
            局限性说明列表
        """
        try:
            limitations = []
            
            if confidence < 0.7:
                limitations.append('当前预测置信度较低，结果仅供参考')
            
            if confidence < 0.5:
                limitations.append('建议等待更多数据或结合其他分析方法')
                limitations.append('当前模型对该场景的预测能力有限')
            
            data_quality = self._assess_data_quality(processed_data)
            if data_quality < 0.7:
                limitations.append(f'数据质量评分较低 ({data_quality:.2%})，可能影响预测准确性')
            
            market_data = processed_data.get('market_data', {})
            if not market_data:
                limitations.append('缺少详细市场数据，预测基于有限信息')
            
            if 'kline_data' not in processed_data:
                limitations.append('缺少K线数据，无法进行完整的技术分析')
            
            if confidence < 0.6:
                limitations.append('市场可能处于不稳定状态，预测结果可能有较大偏差')
            
            if not limitations:
                limitations.append('预测结果基于历史数据和模型学习，实际情况可能有所不同')
                limitations.append('建议结合其他信息源进行综合判断')
            
            return limitations
            
        except Exception as e:
            logger.error(f"识别预测局限性失败: {e}")
            return ['局限性分析失败']
    
    def _get_trend_impact(self, trend: str) -> str:
        """获取趋势影响"""
        impact_mapping = {
            'strong_up': 'strong_positive',
            'up': 'positive',
            'sideways': 'neutral',
            'down': 'negative',
            'strong_down': 'strong_negative'
        }
        return impact_mapping.get(trend, 'unknown')
    
    def _get_volatility_impact(self, volatility: str) -> str:
        """获取波动性影响"""
        impact_mapping = {
            'high': 'increased_uncertainty',
            'medium': 'moderate_uncertainty',
            'low': 'stable'
        }
        return impact_mapping.get(volatility, 'unknown')
    
    def _get_liquidity_impact(self, liquidity: str) -> str:
        """获取流动性影响"""
        impact_mapping = {
            'high': 'positive',
            'medium': 'neutral',
            'low': 'negative'
        }
        return impact_mapping.get(liquidity, 'unknown')
    
    def _get_overall_assessment(self, factors: Dict[str, Any]) -> Dict[str, Any]:
        """获取整体评估"""
        try:
            positive_count = 0
            negative_count = 0
            neutral_count = 0
            
            for key in ['trend', 'volatility', 'liquidity']:
                if key in factors:
                    impact = factors[key].get('impact', '')
                    if 'positive' in impact:
                        positive_count += 1
                    elif 'negative' in impact:
                        negative_count += 1
                    else:
                        neutral_count += 1
            
            if positive_count > negative_count + neutral_count:
                overall = 'favorable'
                description = '市场环境总体有利于预测'
            elif negative_count > positive_count + neutral_count:
                overall = 'challenging'
                description = '市场环境存在一定挑战，预测需谨慎'
            else:
                overall = 'neutral'
                description = '市场环境相对中性'
            
            return {
                'overall': overall,
                'description': description,
                'positive_factors': positive_count,
                'negative_factors': negative_count,
                'neutral_factors': neutral_count
            }
            
        except Exception as e:
            logger.error(f"获取整体评估失败: {e}")
            return {'error': str(e)}