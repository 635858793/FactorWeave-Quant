"""
智能模型选择器主模块

提供完整的智能模型选择功能，整合市场状态检测、模型性能评估、
动态选择策略和预测结果融合。
"""

from loguru import logger
import time
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

from .market_detector import MarketStateDetector, MarketState
from .performance_evaluator import ModelPerformanceEvaluator, ModelPerformance
from .enhanced_model_evaluator import EnhancedModelEvaluator, EnhancedModelMetrics, EnhancedModelPerformance
from .selection_strategy import ModelSelectionStrategy, ModelSelection, SelectionCriteria
from .fusion_engine import (
    PredictionFusionEngine, ModelPrediction, EnsemblePredictionResult,
    FusionMethod
)
from .config.selector_config import IntelligentSelectorConfig
from .config.model_profiles import ModelProfile, MarketCondition

TF_DL_AVAILABLE = False
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import Dense, Dropout, LSTM as TFLSTM, GRU as TFGRU
    from tensorflow.keras.callbacks import EarlyStopping
    from tensorflow.keras.optimizers import Adam
    TF_DL_AVAILABLE = True
except ImportError:
    pass


class TFDeepLearningWrapper:

    def __init__(self, model_type='lstm', hidden_layer_sizes=(64, 128), learning_rate=0.001,
                 sequence_length=10, batch_size=32, epochs=50, random_state=42):
        self.model_type = model_type
        self.hidden_layer_sizes = hidden_layer_sizes
        self.learning_rate = learning_rate
        self.sequence_length = sequence_length
        self.batch_size = batch_size
        self.epochs = epochs
        self.random_state = random_state
        self._model = None
        self.is_fitted = False
        self._input_features = None

    def _build_tf_model(self, n_features, n_outputs=1):
        tf.random.set_seed(self.random_state)
        model = Sequential()
        rnn_layer = TFLSTM if self.model_type == 'lstm' else TFGRU

        if len(self.hidden_layer_sizes) == 1:
            model.add(rnn_layer(self.hidden_layer_sizes[0], input_shape=(self.sequence_length, n_features)))
        else:
            model.add(rnn_layer(self.hidden_layer_sizes[0], input_shape=(self.sequence_length, n_features),
                                return_sequences=True))
            for units in self.hidden_layer_sizes[1:-1]:
                model.add(rnn_layer(units, return_sequences=True))
            model.add(rnn_layer(self.hidden_layer_sizes[-1]))

        model.add(Dense(32, activation='relu'))
        model.add(Dense(n_outputs))
        model.compile(optimizer=Adam(learning_rate=self.learning_rate), loss='mse')
        return model

    def _reshape_to_sequences(self, X):
        X = np.asarray(X, dtype=np.float32)
        n_samples = X.shape[0]
        n_features = X.shape[1]
        seq_len = min(self.sequence_length, n_samples)

        sequences = []
        for i in range(n_samples - seq_len + 1):
            sequences.append(X[i:i + seq_len])
        return np.array(sequences, dtype=np.float32)

    def fit(self, X, y, verbose=False):
        if not TF_DL_AVAILABLE:
            raise RuntimeError("TensorFlow not available")

        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=np.float32)

        if y.ndim == 1:
            y = y.reshape(-1, 1)

        self._input_features = X.shape[1]
        X_seq = self._reshape_to_sequences(X)

        if X_seq.shape[0] == 0:
            X_seq = X[:1].reshape(1, 1, -1)
            y = y[:1]

        y_seq = y[self.sequence_length - 1:X_seq.shape[0] + self.sequence_length - 1]

        self._model = self._build_tf_model(X_seq.shape[2], y_seq.shape[1])
        self._model.fit(
            X_seq, y_seq,
            epochs=self.epochs, batch_size=self.batch_size,
            verbose=1 if verbose else 0,
            validation_split=0.1,
            callbacks=[EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)]
        )
        self.is_fitted = True
        return self

    def predict(self, X):
        X = np.asarray(X, dtype=np.float32)
        n_features = X.shape[1]
        X_seq = self._reshape_to_sequences(X)

        if X_seq.shape[0] == 0:
            fallback_val = np.mean(self._model.predict(
                np.zeros((1, self.sequence_length, n_features), dtype=np.float32), verbose=0
            ))
            return np.full(len(X), fallback_val)

        predictions = self._model.predict(X_seq, verbose=0)

        full_preds = np.full(len(X), np.nan)
        start_idx = self.sequence_length - 1
        for i in range(len(predictions)):
            full_preds[start_idx + i] = predictions[i]

        valid_preds = predictions.flatten()
        full_preds[:start_idx] = valid_preds[0]

        return full_preds

    def get_model_info(self):
        return {
            'model_type': f'tensorflow_{self.model_type}',
            'hidden_layer_sizes': self.hidden_layer_sizes,
            'framework': 'tensorflow'
        }


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
        self.enhanced_evaluator = EnhancedModelEvaluator(self.performance_evaluator)
        self.selection_strategy = ModelSelectionStrategy(self.config.selection_strategy)
        self.fusion_engine = PredictionFusionEngine(self.config.fusion)
        
        # 模型档案管理
        self.model_profiles = self._load_model_profiles()
        
        # 已初始化模型缓存
        self.initialized_models: Dict[str, Any] = {}
        self.model_initialization_status: Dict[str, Dict[str, Any]] = {}
        
        # 缓存和统计
        self._using_fallback_model = False
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
        hyperparameters = profile.hyperparameters

        hidden_units_raw = hyperparameters.get('hidden_units', [64, 128])
        hidden_layer_sizes = tuple(hidden_units_raw)
        learning_rate = hyperparameters.get('learning_rate', 0.001)
        lr = learning_rate[0] if isinstance(learning_rate, list) else learning_rate

        if TF_DL_AVAILABLE:
            try:
                model = TFDeepLearningWrapper(
                    model_type=model_type,
                    hidden_layer_sizes=hidden_layer_sizes,
                    learning_rate=lr,
                    sequence_length=hyperparameters.get('sequence_length', 10),
                    batch_size=hyperparameters.get('batch_size', 32),
                    epochs=hyperparameters.get('epochs', 50)
                )
                logger.info(f"使用 TensorFlow {model_type.upper()} 创建真实深度学习模型: "
                            f"hidden_layer_sizes={hidden_layer_sizes}")
                return model
            except Exception as e:
                logger.warning(f"TensorFlow {model_type.upper()} 创建失败: {e}，"
                               f"降级到 sklearn.MLPRegressor")

        logger.warning(f"TensorFlow 不可用，{model_type.upper()} 降级为 sklearn.MLPRegressor "
                       f"(非真实{model_type.upper()}，不包含循环结构)")

        try:
            from sklearn.neural_network import MLPRegressor

            model = MLPRegressor(
                hidden_layer_sizes=hidden_layer_sizes,
                activation='relu',
                solver='adam',
                learning_rate_init=lr,
                max_iter=200,
                random_state=42,
                early_stopping=True,
                validation_fraction=0.1
            )
            logger.info(f"使用 sklearn.MLPRegressor 创建 {model_type} 降级模型")
            return model

        except ImportError:
            logger.warning(f"sklearn 不可用，无法创建 {model_type} 神经网络模型")
            return self._create_fallback_model(model_type, profile)
        except Exception as e:
            logger.error(f"创建 {model_type} 降级模型失败: {e}")
            return self._create_fallback_model(model_type, profile)
    
    def _create_xgboost_model(self, profile: ModelProfile) -> Any:
        """
        创建XGBoost/梯度提升模型
        """
        hyperparameters = profile.hyperparameters

        try:
            n_estimators = hyperparameters.get('n_estimators', [100, 200])
            max_depth = hyperparameters.get('max_depth', [3, 6])
            learning_rate = hyperparameters.get('learning_rate', [0.05, 0.1])
            subsample = hyperparameters.get('subsample', 0.8)

            n_est = n_estimators[0] if isinstance(n_estimators, list) else n_estimators
            md = max_depth[0] if isinstance(max_depth, list) else max_depth
            lr = learning_rate[0] if isinstance(learning_rate, list) else learning_rate

            try:
                import xgboost as xgb
                model = xgb.XGBRegressor(
                    n_estimators=n_est,
                    max_depth=md,
                    learning_rate=lr,
                    subsample=subsample,
                    random_state=42,
                    n_jobs=-1,
                    verbosity=0
                )
                logger.info(f"使用 xgboost.XGBRegressor 创建模型: n_estimators={n_est}")
                return model
            except ImportError:
                from sklearn.ensemble import GradientBoostingRegressor
                model = GradientBoostingRegressor(
                    n_estimators=n_est,
                    max_depth=md,
                    learning_rate=lr,
                    subsample=subsample,
                    random_state=42
                )
                logger.info(f"使用 sklearn.GradientBoostingRegressor 创建模型: n_estimators={n_est}")
                return model

        except ImportError:
            logger.warning("sklearn/xgboost 不可用，无法创建梯度提升模型")
            return self._create_fallback_model(model_type='xgboost', profile=profile)
        except Exception as e:
            logger.error(f"创建梯度提升模型失败: {e}")
            return self._create_fallback_model(model_type='xgboost', profile=profile)
    
    def _create_random_forest_model(self, profile: ModelProfile) -> Any:
        """
        创建随机森林模型
        """
        hyperparameters = profile.hyperparameters

        try:
            from sklearn.ensemble import RandomForestRegressor

            n_estimators = hyperparameters.get('n_estimators', [50, 100])
            max_depth = hyperparameters.get('max_depth', [5, 10])
            min_samples_split = hyperparameters.get('min_samples_split', 5)
            max_features = hyperparameters.get('max_features', 'sqrt')

            n_est = n_estimators[0] if isinstance(n_estimators, list) else n_estimators
            md = max_depth[0] if isinstance(max_depth, list) else max_depth

            model = RandomForestRegressor(
                n_estimators=n_est,
                max_depth=md,
                min_samples_split=min_samples_split,
                max_features=max_features,
                random_state=42,
                n_jobs=-1
            )
            logger.info(f"使用 sklearn.RandomForestRegressor 创建模型: n_estimators={n_est}")
            return model

        except ImportError:
            logger.warning("sklearn 不可用，无法创建随机森林模型")
            return self._create_fallback_model(model_type='random_forest', profile=profile)
        except Exception as e:
            logger.error(f"创建随机森林模型失败: {e}")
            return self._create_fallback_model(model_type='random_forest', profile=profile)
    
    def _create_linear_regression_model(self, profile: ModelProfile) -> Any:
        """
        创建线性回归模型
        """
        hyperparameters = profile.hyperparameters

        try:
            from sklearn.linear_model import LinearRegression

            fit_intercept = hyperparameters.get('fit_intercept', True)
            normalize = hyperparameters.get('normalize', False)

            model = LinearRegression(fit_intercept=fit_intercept)
            logger.info(f"使用 sklearn.LinearRegression 创建模型")
            return model

        except ImportError:
            logger.warning("sklearn 不可用，无法创建线性回归模型")
            return self._create_fallback_model(model_type='linear_regression', profile=profile)
        except Exception as e:
            logger.error(f"创建线性回归模型失败: {e}")
            return self._create_fallback_model(model_type='linear_regression', profile=profile)
    
    def _create_ensemble_model(self, profile: ModelProfile) -> Any:
        """
        创建集成模型
        """
        hyperparameters = profile.hyperparameters

        try:
            from sklearn.ensemble import VotingRegressor
            from sklearn.linear_model import LinearRegression
            from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
            from sklearn.neural_network import MLPRegressor

            base_models_config = hyperparameters.get('base_models', ['lstm', 'xgboost', 'gru'])
            fusion_method = hyperparameters.get('fusion_method', 'weighted_average')

            estimators = []
            for bm_type in base_models_config:
                if bm_type in ['lstm', 'gru']:
                    if TF_DL_AVAILABLE:
                        try:
                            dl_model = TFDeepLearningWrapper(
                                model_type=bm_type,
                                hidden_layer_sizes=(64, 32),
                                sequence_length=10,
                                batch_size=32,
                                epochs=30
                            )
                            estimators.append((bm_type, dl_model))
                            continue
                        except Exception as e:
                            logger.warning(f"集成模型中 TensorFlow {bm_type} 创建失败: {e}，降级 MLP")
                    estimators.append((bm_type, MLPRegressor(
                        hidden_layer_sizes=(64, 32), max_iter=100, random_state=42
                    )))
                elif bm_type == 'xgboost':
                    estimators.append((bm_type, GradientBoostingRegressor(
                        n_estimators=100, max_depth=3, random_state=42
                    )))
                elif bm_type == 'random_forest':
                    estimators.append((bm_type, RandomForestRegressor(
                        n_estimators=100, random_state=42, n_jobs=-1
                    )))
                elif bm_type == 'linear_regression':
                    estimators.append((bm_type, LinearRegression()))

            if not estimators:
                logger.warning("无有效子模型，回退到默认随机森林")
                estimators = [('rf', RandomForestRegressor(n_estimators=50, random_state=42))]

            model = VotingRegressor(estimators=estimators)
            logger.info(f"使用 sklearn.VotingRegressor 创建集成模型: {len(estimators)} 个子模型")
            return model

        except ImportError:
            logger.warning("sklearn 不可用，无法创建集成模型")
            return self._create_fallback_model(model_type='ensemble', profile=profile)
        except Exception as e:
            logger.error(f"创建集成模型失败: {e}")
            return self._create_fallback_model(model_type='ensemble', profile=profile)
    
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
                    if hasattr(X, '__len__') and len(X) > 0:
                        x_arr = np.asarray(X)
                        self._last_value = float(np.mean(x_arr[-min(10, len(x_arr)):]))
                        self._trend = 0.0
                    return self
                
                def predict(self, steps):
                    """预测未来值"""
                    if not self.is_fitted:
                        return np.zeros(steps)
                    last_val = getattr(self, '_last_value', 0.0)
                    trend = getattr(self, '_trend', 0.0)
                    return np.array([last_val + trend * (i + 1) for i in range(steps)])
                
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

        当所有模型加载失败时使用的最小化实现，
        基于 sklearn.dummy.DummyRegressor(strategy='mean') 提供有意义的预测。
        """
        try:
            from sklearn.dummy import DummyRegressor

            model = DummyRegressor(strategy='mean')
            model.model_type = model_type
            model.profile = profile
            model.is_fitted = False
            model._original_fit = model.fit
            model._original_predict = model.predict

            def fit_wrapper(X, y, verbose=False):
                result = model._original_fit(X, y)
                model.is_fitted = True
                if verbose:
                    logger.info(f"[FallbackModel] {model_type} 已用 DummyRegressor(mean) 训练, "
                                f"样本数={len(y) if hasattr(y, '__len__') else 1}")
                return result

            def predict_wrapper(X):
                if not model.is_fitted:
                    logger.warning(f"[FallbackModel] {model_type} 未训练，返回零预测")
                    return np.zeros(len(X) if hasattr(X, '__len__') else 1)
                return model._original_predict(X)

            def get_model_info():
                return {
                    'model_type': model.model_type,
                    'name': model.profile.name if model.profile else model_type,
                    'status': 'fallback_dummy_regressor',
                    'strategy': 'mean'
                }

            model.fit = fit_wrapper
            model.predict = predict_wrapper
            model.get_model_info = get_model_info

            logger.info(f"[FallbackModel] {model_type} 使用 DummyRegressor(strategy='mean') "
                        f"替代零预测 fallback")
            return model

        except ImportError:
            logger.warning(f"[FallbackModel] sklearn 不可用，{model_type} 使用零预测兜底")

            class FallbackModel:
                def __init__(self, model_type, profile):
                    self.model_type = model_type
                    self.profile = profile
                    self.is_fitted = False

                def fit(self, X, y, verbose=False):
                    self.is_fitted = True
                    self._y_mean = float(np.mean(y)) if hasattr(y, '__len__') else float(y)
                    return self

                def predict(self, X):
                    if not self.is_fitted:
                        return np.zeros(len(X) if hasattr(X, '__len__') else 1)
                    return np.full(len(X) if hasattr(X, '__len__') else 1, self._y_mean)

                def get_model_info(self):
                    return {
                        'model_type': self.model_type,
                        'name': self.profile.name if self.profile else model_type,
                        'status': 'fallback_pure_python'
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
                performance = self._simulate_performance_evaluation(
                    model_type, market_state, request
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
                                       market_state: MarketState,
                                       request: SelectionRequest = None) -> ModelPerformance:
        """模型性能评估

        优先使用真实评估路径：
        1. performance_evaluator 的历史评估数据
        2. 已初始化模型的交叉验证评分
        3. 仅在完全无数据时才降级为启发式评分并记录 warning。
        """
        try:
            # 路径 1: 尝试从 performance_evaluator 获取缓存评估
            if self.performance_evaluator is not None:
                cached_eval = self._try_get_cached_evaluation(model_type)
                if cached_eval is not None:
                    logger.info(f"[性能评估] {model_type} 使用 performance_evaluator 缓存评估 "
                                f"score={cached_eval.composite_score:.4f}")
                    return cached_eval

            # 路径 2: 尝试用已初始化模型做交叉验证
            model_instance = self.initialized_models.get(model_type)
            if model_instance is not None and hasattr(model_instance, 'predict') and request is not None:
                X = self._extract_features_from_request(request)
                y = self._extract_target_from_request(request)
                if X is not None and y is not None and len(X) > 0 and len(y) > 0:
                    try:
                        from sklearn.model_selection import cross_val_score
                        min_len = min(len(X), len(y))
                        X_cv = X[:min_len]
                        y_cv = y[:min_len]
                        n_splits = min(3, len(X_cv) - 1)
                        if n_splits >= 2:
                            scores = cross_val_score(
                                model_instance, X_cv, y_cv,
                                cv=n_splits, scoring='neg_mean_squared_error'
                            )
                            performance_score = float(np.mean(scores))
                            adjusted_score = max(0.0, min(1.0, 1.0 / (1.0 + abs(performance_score))))
                            logger.info(f"[性能评估] {model_type} 使用 cross_val_score, "
                                        f"n_splits={n_splits}, raw_score={performance_score:.4f}, "
                                        f"adjusted={adjusted_score:.4f}")
                            real_metrics = ModelMetrics(
                                accuracy=adjusted_score,
                                precision=0.0,
                                recall=0.0,
                                f1_score=0.0,
                                mape=0.0,
                                sharpe_ratio=0.0,
                                timestamp=datetime.now()
                            )
                            return ModelPerformance(
                                model_type=model_type,
                                metrics=real_metrics,
                                composite_score=adjusted_score,
                                reliability_score=min(adjusted_score * 1.1, 1.0),
                                sample_size=len(X_cv),
                                evaluation_timestamp=datetime.now()
                            )
                    except ImportError:
                        logger.debug(f"[性能评估] sklearn.model_selection 不可用，降级到启发式")
                    except Exception as cv_err:
                        logger.warning(f"[性能评估] {model_type} 交叉验证失败: {cv_err}，降级到启发式")

            logger.warning(
                f"[性能评估] {model_type} 无可用的真实评估数据，"
                f"无法进行有效评估，返回空结果"
            )
            return None

        except Exception as e:
            logger.warning(f"{model_type} 性能评估失败: {e}")
            return None

    def _try_get_cached_evaluation(self, model_type: str) -> Optional[ModelPerformance]:
        """尝试从 performance_evaluator 获取缓存的评估结果"""
        try:
            if not hasattr(self.performance_evaluator, '_recent_evaluations'):
                return None
            recent = getattr(self.performance_evaluator, '_recent_evaluations', None)
            if recent is None:
                return None
            for evaluation in reversed(list(recent)):
                if hasattr(evaluation, 'model_type') and evaluation.model_type == model_type:
                    return evaluation
            return None
        except Exception:
            return None
    
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
        logger.warning("_create_mock_metrics 不再生成假指标，模型不可用")
        return None
    
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
            predictions = self._generate_real_predictions(selected_models, request)

            fusion_result = self.fusion_engine.fuse_predictions(
                predictions, FusionMethod.WEIGHTED_AVERAGE
            )

            return fusion_result

        except Exception as e:
            logger.warning(f"预测融合失败: {e}")
            return None
    
    def _generate_real_predictions(self, selected_models: List[ModelSelection],
                                request: SelectionRequest) -> List[ModelPrediction]:
        """使用真实模型链路生成预测结果

        优先使用已初始化的子模型进行预测；若子模型不可用，
        则通过 _create_fallback_model 训练后再预测。
        仅当连特征数据都不可用时才返回零预测并记录 warning。
        """
        predictions = []

        X = self._extract_features_from_request(request)
        y = self._extract_target_from_request(request)

        if X is None or len(X) == 0:
            logger.warning(
                f"[融合] 无可用的特征数据（{len(selected_models)} 个模型），"
                f"所有预测值设为 0.0"
            )
            for model_selection in selected_models:
                predictions.append(ModelPrediction(
                    model_type=model_selection.model_type,
                    prediction_value=0.0,
                    confidence=model_selection.confidence,
                    timestamp=datetime.now(),
                    metadata={
                        'selection_weight': model_selection.weight,
                        'selection_confidence': model_selection.confidence,
                        'is_real': False,
                        'reason': 'no_feature_data'
                    }
                ))
            return predictions

        self._using_fallback_model = False

        for model_selection in selected_models:
            model_type = model_selection.model_type
            try:
                model_instance = self.initialized_models.get(model_type)
                use_fallback = False

                if model_instance is not None and hasattr(model_instance, 'predict'):
                    pred_values = model_instance.predict(X)
                else:
                    profile = self.model_profiles.get(model_type)
                    model_instance = self._create_fallback_model(model_type, profile) if profile else self._create_fallback_model(model_type, None)
                    if y is not None and len(y) > 0:
                        model_instance.fit(X, y)
                    use_fallback = True
                    self._using_fallback_model = True
                    pred_values = model_instance.predict(X)

                pred_values = np.atleast_1d(np.asarray(pred_values, dtype=np.float64))
                if len(pred_values) == 0:
                    pred_value = 0.0
                else:
                    pred_value = float(np.mean(pred_values[-1:]))

                predictions.append(ModelPrediction(
                    model_type=model_type,
                    prediction_value=pred_value,
                    confidence=model_selection.confidence,
                    timestamp=datetime.now(),
                    metadata={
                        'selection_weight': model_selection.weight,
                        'selection_confidence': model_selection.confidence,
                        'is_real': True,
                        'using_fallback': use_fallback
                    }
                ))

                if use_fallback:
                    logger.info(f"[融合] {model_type} 使用 fallback 模型生成预测 "
                                f"value={pred_value:.4f}")
                else:
                    logger.debug(f"[融合] {model_type} 使用已初始化模型生成预测 "
                                 f"value={pred_value:.4f}")
            except Exception as exc:
                logger.warning(f"[融合] {model_type} 预测失败: {exc}，使用零值")
                predictions.append(ModelPrediction(
                    model_type=model_type,
                    prediction_value=0.0,
                    confidence=model_selection.confidence,
                    timestamp=datetime.now(),
                    metadata={
                        'selection_weight': model_selection.weight,
                        'selection_confidence': model_selection.confidence,
                        'is_real': False,
                        'reason': f'prediction_error: {exc}'
                    }
                ))

        return predictions

    def _extract_features_from_request(self, request: SelectionRequest) -> Optional[np.ndarray]:
        """从 SelectionRequest 中提取特征矩阵 X"""
        try:
            if request.kline_data:
                fields = ['open', 'high', 'low', 'close', 'volume']
                values = []
                for f in fields:
                    v = request.kline_data.get(f)
                    if v is not None:
                        if hasattr(v, '__len__') and not isinstance(v, str):
                            values.append(np.atleast_1d(np.asarray(v, dtype=np.float64)))
                        else:
                            values.append(np.full(1, float(v), dtype=np.float64))
                if values:
                    X = np.column_stack([v.reshape(-1, 1) if v.ndim == 1 else v for v in values])
                    return X

            if request.market_data:
                numeric_values = []
                for v in request.market_data.values():
                    try:
                        numeric_values.append(float(v))
                    except (TypeError, ValueError):
                        pass
                if numeric_values:
                    return np.array(numeric_values, dtype=np.float64).reshape(1, -1)

            return None
        except Exception as e:
            logger.warning(f"[融合] 特征提取失败: {e}")
            return None

    def _extract_target_from_request(self, request: SelectionRequest) -> Optional[np.ndarray]:
        """从 SelectionRequest 中提取目标变量 y"""
        try:
            if request.kline_data:
                for field in ('close', 'price', 'target', 'y', 'label'):
                    v = request.kline_data.get(field)
                    if v is not None:
                        y = np.atleast_1d(np.asarray(v, dtype=np.float64))
                        return y

            if request.market_data:
                for field in ('close', 'price', 'target', 'y', 'label'):
                    v = request.market_data.get(field)
                    if v is not None:
                        try:
                            return np.array([float(v)], dtype=np.float64)
                        except (TypeError, ValueError):
                            pass

            return None
        except Exception as e:
            logger.warning(f"[融合] 目标变量提取失败: {e}")
            return None
    
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

    def predict(self, features: np.ndarray) -> np.ndarray:
        t_start = time.perf_counter()

        if features is None or not isinstance(features, np.ndarray):
            logger.error("[AI预测] 输入特征为 None 或非 numpy 数组")
            return self._fallback_predict(np.atleast_2d(features) if features is not None else np.zeros((1, 1)))

        features = np.atleast_2d(features).astype(np.float32)
        n_samples = features.shape[0]
        logger.info(f"[AI预测] 开始 | 特征={features.shape} | 样本数={n_samples}")

        if np.any(np.isnan(features)) or np.any(np.isinf(features)):
            logger.warning("[AI预测] 输入包含 NaN 或 Inf，已替换为 0")
            features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)

        if self.initialized_models:
            preds = []
            for name, model in self.initialized_models.items():
                if hasattr(model, 'predict'):
                    try:
                        p = model.predict(features)
                        p = np.atleast_1d(np.asarray(p, dtype=np.float32))
                        if len(p) != n_samples:
                            logger.warning(f"[AI预测] {name} 输出形状 {p.shape} 与输入样本数 {n_samples} 不匹配，已截断/填充至一致")
                            if len(p) > n_samples:
                                p = p[:n_samples]
                            else:
                                p = np.pad(p, (0, n_samples - len(p)), 'edge')
                        preds.append(p)
                    except Exception as exc:
                        logger.warning(f"[AI预测] 模型 {name} 预测失败: {exc}")
            if preds:
                predictions = np.mean(np.column_stack(preds), axis=1)
            else:
                predictions = self._fallback_predict(features)
        else:
            predictions = self._fallback_predict(features)

        logger.info(f"[AI预测] 完成 | 耗时={time.perf_counter()-t_start:.4f}s | range=[{predictions.min():.4f}, {predictions.max():.4f}]")

        return predictions

    def _fallback_predict(self, features: np.ndarray) -> np.ndarray:
        if features.ndim == 2:
            weights = np.ones(features.shape[1]) / features.shape[1]
            return np.clip(features @ weights * 0.1, -1, 1)
        return np.zeros(len(features))

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
        t_start = time.perf_counter()
        logger.info(f"[AI预测] 开始 | 预测类型={prediction_type} | 数据字段数={len(data)}")
        
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
            predictions = self._generate_real_predictions(
                selection_result.selected_models, request
            )
            
            if not predictions:
                logger.warning("所有模型预测失败，使用后备策略")
                return self._fallback_prediction(prediction_type, data)
            
            # 7. 融合预测结果
            if self.config.enable_fusion and len(predictions) > 1:
                t_fusion = time.perf_counter()
                from .fusion_engine import FusionMethod
                final_prediction = self.fusion_engine.fuse_predictions(
                    predictions,
                    FusionMethod.WEIGHTED_AVERAGE
                )
                elapsed = time.perf_counter() - t_fusion
                logger.info(f"[AI融合] 模型数={len(predictions)} | 耗时={elapsed:.4f}s | "
                           f"方法=weighted_average")
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
            
            elapsed_total = time.perf_counter() - t_start
            logger.info(f"[AI预测] 完成 | 总耗时={elapsed_total:.4f}s | 预测类型={prediction_type}")
            return final_prediction
            
        except Exception as e:
            logger.error(f"智能预测失败: {e}")
            self.statistics['failed_predictions'] += 1
            self.statistics['total_predictions'] += 1
            return self._fallback_prediction(prediction_type, data)
    
    def _preprocess_data(self, data: Dict[str, Any], prediction_type: str) -> Optional[Dict[str, Any]]:
        """预处理输入数据"""
        t_pre = time.perf_counter()
        try:
            processed = data.copy()
            
            # 验证必要字段
            if prediction_type in ['price_prediction', 'trend_prediction']:
                if 'kline_data' not in processed and 'kline_data' not in data:
                    if 'market_data' in processed:
                        logger.warning("K线数据不可用，无法生成真实K线数据。跳过数据预处理。")
                        return None
            
            elapsed = time.perf_counter() - t_pre
            logger.debug(f"[AI预处理] 耗时={elapsed:.4f}s | 预测类型={prediction_type}")
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
        predictions = []
        
        for selection in selected_models:
            try:
                prediction = self._simulate_model_prediction(selection.model_type, data)
                if prediction is not None:
                    predictions.append(prediction)
            except Exception as e:
                logger.warning(f"模型 {selection.model_type} 预测失败: {e}")
                continue
        
        return predictions
    
    def _simulate_model_prediction(self, model_type: str, data: Dict[str, Any]) -> Optional[ModelPrediction]:
        logger.warning(f"[AI预测] _simulate_model_prediction 已弃用，模型 {model_type} 未训练，不返回假预测值")
        return None
    
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
        logger.warning("AI预测引擎不可用，无法生成真实预测。返回空结果。")
        return {
            'prediction': None,
            'confidence': 0.0,
            'model_type': 'none',
            'strategy': 'unavailable',
            'timestamp': datetime.now(),
            'note': 'AI预测引擎不可用，无法生成预测。请配置预测模型以获取真实预测。',
            'explainability': {
                'methodology': '预测引擎不可用',
                'confidence_level': 'none',
                'feature_importance': {},
                'market_factors': {},
                'recommendation': '建议配置AI预测模型以启用预测功能'
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
            trend_dir = self._safe_get_market_attr(market_state, 'trend_direction', '未知')
            if confidence >= 0.85:
                level = 'very_high'
                level_text = '非常高'
                reason_parts = [
                    f"模型置信度 {confidence:.2%} 处于较高水平",
                    f"基于{model_type}模型的稳定表现",
                    f"当前市场状态（{trend_dir}趋势）较为明确"
                ]
            elif confidence >= 0.70:
                level = 'high'
                level_text = '高'
                reason_parts = [
                    f"模型置信度 {confidence:.2%} 达到预期水平",
                    f"{model_type}模型在该场景下表现良好",
                    f"市场趋势（{trend_dir}）提供了有效的参考依据"
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
                    f"当前市场状态（{trend_dir}趋势）可能存在波动",
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
            
            vol_level = self._safe_get_market_attr(market_state, 'volatility_level', 'normal')
            liq_level = self._safe_get_market_attr(market_state, 'liquidity_level', 'normal')
            if vol_level == 'high':
                reason_parts.append("市场波动性较高，增加了预测的不确定性")
            elif vol_level == 'low':
                reason_parts.append("市场波动性较低，预测相对稳定")
            
            if liq_level == 'high':
                reason_parts.append("市场流动性充足，预测结果更可靠")
            elif liq_level == 'low':
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
                'value': self._safe_get_market_attr(market_state, 'trend_direction', 'unknown'),
                'impact': self._get_trend_impact(self._safe_get_market_attr(market_state, 'trend_direction', 'unknown')),
                'description': f'当前市场呈现{self._safe_get_market_attr(market_state, "trend_direction", "unknown")}趋势'
            }
            factors['trend'] = trend_factor
            
            volatility_factor = {
                'name': '波动性因素',
                'value': self._safe_get_market_attr(market_state, 'volatility_level', 'normal'),
                'impact': self._get_volatility_impact(self._safe_get_market_attr(market_state, 'volatility_level', 'normal')),
                'description': f'市场波动性{self._safe_get_market_attr(market_state, "volatility_level", "normal")}'
            }
            factors['volatility'] = volatility_factor
            
            liquidity_factor = {
                'name': '流动性因素',
                'value': self._safe_get_market_attr(market_state, 'liquidity_level', 'normal'),
                'impact': self._get_liquidity_impact(self._safe_get_market_attr(market_state, 'liquidity_level', 'normal')),
                'description': f'市场流动性{self._safe_get_market_attr(market_state, "liquidity_level", "normal")}'
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
    

    def _safe_get_market_attr(self, market_state: MarketState, attr_name: str, default: str = 'normal') -> str:
        try:
            if hasattr(market_state, 'volatility') and hasattr(market_state.volatility, 'level'):
                if attr_name == 'volatility_level':
                    return market_state.volatility.level.value
            if hasattr(market_state, 'liquidity') and hasattr(market_state.liquidity, 'level'):
                if attr_name == 'liquidity_level':
                    return market_state.liquidity.level.value
            if hasattr(market_state, 'trend_strength') and hasattr(market_state.trend_strength, 'direction'):
                if attr_name == 'trend_direction':
                    return market_state.trend_strength.direction
            if hasattr(market_state, 'trend_strength') and hasattr(market_state.trend_strength, 'level'):
                if attr_name == 'trend_level':
                    return market_state.trend_strength.level.value
            logger.warning(f'无法获取MarketState属性 {attr_name}，使用默认值 {default}')
            return default
        except Exception as e:
            logger.warning(f'获取MarketState属性 {attr_name} 失败: {e}')
            return default

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
    
    def evaluate_model_performance_enhanced(
        self,
        model_type: str,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_pred_proba: Optional[np.ndarray] = None,
        task_type: str = 'classification'
    ) -> EnhancedModelPerformance:
        """
        使用增强评估器评估模型性能
        
        Args:
            model_type: 模型类型
            y_true: 真实标签
            y_pred: 预测标签
            y_pred_proba: 预测概率（仅用于分类任务）
            task_type: 任务类型 ('classification' 或 'regression')
            
        Returns:
            增强模型性能数据
        """
        try:
            logger.info(f"开始增强模型性能评估: {model_type}")
            
            enhanced_performance = self.enhanced_evaluator.evaluate_model_performance(
                model_type=model_type,
                y_true=y_true,
                y_pred=y_pred,
                y_pred_proba=y_pred_proba,
                task_type=task_type
            )
            
            logger.info(f"增强模型性能评估完成: {model_type}")
            
            return enhanced_performance
            
        except Exception as e:
            logger.error(f"增强模型性能评估失败: {e}")
            return self.enhanced_evaluator._get_default_enhanced_performance(model_type)
    
    def visualize_model_performance(
        self,
        model_type: str,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_pred_proba: Optional[np.ndarray] = None,
        task_type: str = 'classification',
        save_dir: Optional[str] = None,
        feature_names: Optional[List[str]] = None,
        feature_importance: Optional[np.ndarray] = None
    ) -> Dict[str, Optional[str]]:
        """
        可视化模型性能
        
        Args:
            model_type: 模型类型
            y_true: 真实标签
            y_pred: 预测标签
            y_pred_proba: 预测概率（仅用于分类任务）
            task_type: 任务类型 ('classification' 或 'regression')
            save_dir: 保存目录，如果为None则显示图表
            feature_names: 特征名称列表（用于特征重要性图）
            feature_importance: 特征重要性分数
            
        Returns:
            生成的图表路径字典 {chart_type: file_path}
        """
        try:
            logger.info(f"开始可视化模型性能: {model_type}")
            
            chart_paths = {}
            
            if task_type == 'classification':
                # 混淆矩阵
                confusion_path = None
                if save_dir:
                    confusion_path = f"{save_dir}/{model_type}_confusion_matrix.png"
                result = self.enhanced_evaluator.plot_confusion_matrix(
                    y_true=y_true,
                    y_pred=y_pred,
                    title=f"{model_type} - Confusion Matrix",
                    save_path=confusion_path
                )
                chart_paths['confusion_matrix'] = result
                
                # ROC曲线
                if y_pred_proba is not None:
                    roc_path = None
                    if save_dir:
                        roc_path = f"{save_dir}/{model_type}_roc_curve.png"
                    result = self.enhanced_evaluator.plot_roc_curve(
                        y_true=y_true,
                        y_pred_proba=y_pred_proba,
                        title=f"{model_type} - ROC Curve",
                        save_path=roc_path
                    )
                    chart_paths['roc_curve'] = result
                    
                    # PR曲线
                    pr_path = None
                    if save_dir:
                        pr_path = f"{save_dir}/{model_type}_pr_curve.png"
                    result = self.enhanced_evaluator.plot_pr_curve(
                        y_true=y_true,
                        y_pred_proba=y_pred_proba,
                        title=f"{model_type} - Precision-Recall Curve",
                        save_path=pr_path
                    )
                    chart_paths['pr_curve'] = result
                
                # 特征重要性
                if feature_names is not None and feature_importance is not None:
                    importance_path = None
                    if save_dir:
                        importance_path = f"{save_dir}/{model_type}_feature_importance.png"
                    result = self.enhanced_evaluator.plot_feature_importance(
                        feature_names=feature_names,
                        importance_scores=feature_importance,
                        title=f"{model_type} - Feature Importance",
                        save_path=importance_path
                    )
                    chart_paths['feature_importance'] = result
                    
            elif task_type == 'regression':
                # 预测误差图
                error_path = None
                if save_dir:
                    error_path = f"{save_dir}/{model_type}_prediction_error.png"
                result = self.enhanced_evaluator.plot_prediction_error(
                    y_true=y_true,
                    y_pred=y_pred,
                    title=f"{model_type} - Prediction Error",
                    save_path=error_path
                )
                chart_paths['prediction_error'] = result
                
                # 残差图
                residuals_path = None
                if save_dir:
                    residuals_path = f"{save_dir}/{model_type}_residuals.png"
                result = self.enhanced_evaluator.plot_residuals(
                    y_true=y_true,
                    y_pred=y_pred,
                    title=f"{model_type} - Residual Plot",
                    save_path=residuals_path
                )
                chart_paths['residuals'] = result
            
            logger.info(f"模型性能可视化完成: {model_type}, 生成图表: {len(chart_paths)}")
            
            return chart_paths
            
        except Exception as e:
            logger.error(f"可视化模型性能失败: {e}")
            return {}
    
    def evaluate_and_visualize_model(
        self,
        model_type: str,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_pred_proba: Optional[np.ndarray] = None,
        task_type: str = 'classification',
        save_dir: Optional[str] = None,
        feature_names: Optional[List[str]] = None,
        feature_importance: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        评估并可视化模型性能（便捷方法）
        
        Args:
            model_type: 模型类型
            y_true: 真实标签
            y_pred: 预测标签
            y_pred_proba: 预测概率（仅用于分类任务）
            task_type: 任务类型 ('classification' 或 'regression')
            save_dir: 保存目录
            feature_names: 特征名称列表
            feature_importance: 特征重要性分数
            
        Returns:
            包含评估结果和可视化路径的字典
        """
        try:
            # 评估模型性能
            performance = self.evaluate_model_performance_enhanced(
                model_type=model_type,
                y_true=y_true,
                y_pred=y_pred,
                y_pred_proba=y_pred_proba,
                task_type=task_type
            )
            
            # 可视化模型性能
            chart_paths = self.visualize_model_performance(
                model_type=model_type,
                y_true=y_true,
                y_pred=y_pred,
                y_pred_proba=y_pred_proba,
                task_type=task_type,
                save_dir=save_dir,
                feature_names=feature_names,
                feature_importance=feature_importance
            )
            
            return {
                'performance': performance,
                'chart_paths': chart_paths,
                'model_type': model_type,
                'task_type': task_type
            }
            
        except Exception as e:
            logger.error(f"评估并可视化模型失败: {e}")
            return {
                'error': str(e),
                'model_type': model_type,
                'task_type': task_type
            }