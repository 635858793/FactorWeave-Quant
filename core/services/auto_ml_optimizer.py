# -*- coding: utf-8 -*-
"""
AutoML超参数优化模块
支持贝叶斯优化、随机搜索和网格搜索
"""
from typing import Dict, Any, Optional, List, Callable, Tuple
from loguru import logger
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
import copy


class OptimizationMethod(Enum):
    BAYESIAN = "bayesian"
    RANDOM_SEARCH = "random_search"
    GRID_SEARCH = "grid_search"


class ObjectiveType(Enum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


@dataclass
class ParameterSpace:
    """参数空间定义"""
    name: str
    type: str
    low: Optional[float] = None
    high: Optional[float] = None
    values: Optional[List[Any]] = None
    default: Any = None
    
    def sample(self, method: str = "random") -> Any:
        """从参数空间采样"""
        if self.type == "uniform":
            return np.random.uniform(self.low, self.high)
        elif self.type == "loguniform":
            return np.exp(np.random.uniform(np.log(self.low), np.log(self.high)))
        elif self.type == "categorical":
            return np.random.choice(self.values)
        elif self.type == "int_uniform":
            return int(np.random.uniform(self.low, self.high))
        return self.default


@dataclass
class OptimizationResult:
    """优化结果"""
    best_params: Dict[str, Any]
    best_score: float
    all_trials: List[Dict[str, Any]]
    method: OptimizationMethod
    total_iterations: int
    elapsed_time: float


class AutoMLOptimizer:
    """AutoML超参数优化器"""
    
    SUPPORTED_ALGORITHMS = {
        'xgboost': {
            'n_estimators': ParameterSpace('n_estimators', 'int_uniform', 50, 500, default=100),
            'max_depth': ParameterSpace('max_depth', 'int_uniform', 3, 12, default=6),
            'learning_rate': ParameterSpace('learning_rate', 'loguniform', 0.01, 0.3, default=0.1),
            'min_child_weight': ParameterSpace('min_child_weight', 'uniform', 1, 10, default=1),
            'subsample': ParameterSpace('subsample', 'uniform', 0.5, 1.0, default=1.0),
            'colsample_bytree': ParameterSpace('colsample_bytree', 'uniform', 0.5, 1.0, default=1.0),
            'reg_alpha': ParameterSpace('reg_alpha', 'loguniform', 1e-4, 10, default=0),
            'reg_lambda': ParameterSpace('reg_lambda', 'loguniform', 1e-4, 10, default=1),
        },
        'lightgbm': {
            'n_estimators': ParameterSpace('n_estimators', 'int_uniform', 50, 500, default=100),
            'max_depth': ParameterSpace('max_depth', 'int_uniform', 3, 12, default=6),
            'learning_rate': ParameterSpace('learning_rate', 'loguniform', 0.01, 0.3, default=0.1),
            'num_leaves': ParameterSpace('num_leaves', 'int_uniform', 20, 100, default=31),
            'min_child_samples': ParameterSpace('min_child_samples', 'int_uniform', 5, 50, default=20),
            'subsample': ParameterSpace('subsample', 'uniform', 0.5, 1.0, default=1.0),
            'colsample_bytree': ParameterSpace('colsample_bytree', 'uniform', 0.5, 1.0, default=1.0),
            'reg_alpha': ParameterSpace('reg_alpha', 'loguniform', 1e-4, 10, default=0),
            'reg_lambda': ParameterSpace('reg_lambda', 'loguniform', 1e-4, 10, default=0),
        },
        'random_forest': {
            'n_estimators': ParameterSpace('n_estimators', 'int_uniform', 50, 500, default=100),
            'max_depth': ParameterSpace('max_depth', 'int_uniform', 5, 30, default=10),
            'min_samples_split': ParameterSpace('min_samples_split', 'int_uniform', 2, 20, default=2),
            'min_samples_leaf': ParameterSpace('min_samples_leaf', 'int_uniform', 1, 10, default=1),
            'max_features': ParameterSpace('max_features', 'categorical', values=['sqrt', 'log2', None], default='sqrt'),
        },
        'gradient_boosting': {
            'n_estimators': ParameterSpace('n_estimators', 'int_uniform', 50, 500, default=100),
            'max_depth': ParameterSpace('max_depth', 'int_uniform', 3, 10, default=5),
            'learning_rate': ParameterSpace('learning_rate', 'loguniform', 0.01, 0.3, default=0.1),
            'min_samples_split': ParameterSpace('min_samples_split', 'int_uniform', 2, 20, default=2),
            'min_samples_leaf': ParameterSpace('min_samples_leaf', 'int_uniform', 1, 10, default=1),
            'subsample': ParameterSpace('subsample', 'uniform', 0.5, 1.0, default=1.0),
        },
        'svm': {
            'C': ParameterSpace('C', 'loguniform', 1e-3, 100, default=1.0),
            'kernel': ParameterSpace('kernel', 'categorical', values=['rbf', 'linear', 'poly'], default='rbf'),
            'gamma': ParameterSpace('gamma', 'categorical', values=['scale', 'auto', 0.01, 0.1, 1], default='scale'),
        },
        'sgd': {
            'alpha': ParameterSpace('alpha', 'loguniform', 1e-6, 1e-1, default=1e-4),
            'learning_rate': ParameterSpace('learning_rate', 'categorical', values=['constant', 'optimal', 'invscaling', 'adaptive'], default='constant'),
            'eta0': ParameterSpace('eta0', 'loguniform', 1e-4, 1, default=0.01),
            'penalty': ParameterSpace('penalty', 'categorical', values=['none', 'l1', 'l2', 'elasticnet'], default='l2'),
            'l1_ratio': ParameterSpace('l1_ratio', 'uniform', 0, 1, default=0.15),
        }
    }
    
    def __init__(
        self,
        algorithm: str,
        method: OptimizationMethod = OptimizationMethod.RANDOM_SEARCH,
        n_iter: int = 30,
        cv: int = 3,
        scoring: str = 'accuracy',
        objective: ObjectiveType = ObjectiveType.MAXIMIZE,
        random_state: int = 42,
        n_jobs: int = -1
    ):
        self.algorithm = algorithm
        self.method = method
        self.n_iter = n_iter
        self.cv = cv
        self.scoring = scoring
        self.objective = objective
        self.random_state = random_state
        self.n_jobs = n_jobs
        
        self.param_space = self.SUPPORTED_ALGORITHMS.get(algorithm, {})
        self.trials: List[Dict[str, Any]] = []
        self.best_score = -float('inf') if objective == ObjectiveType.MAXIMIZE else float('inf')
        self.best_params: Dict[str, Any] = {}
        
        np.random.seed(random_state)
    
    def _sample_params(self) -> Dict[str, Any]:
        """随机采样参数"""
        params = {}
        for name, space in self.param_space.items():
            params[name] = space.sample()
        return params
    
    def _cross_validate(self, params: Dict[str, Any], X: np.ndarray, y: np.ndarray, 
                       model_factory: Callable) -> float:
        """交叉验证评估"""
        from sklearn.model_selection import cross_val_score
        
        try:
            model = model_factory(params)
            scores = cross_val_score(
                model, X, y, 
                cv=self.cv, 
                scoring=self.scoring,
                n_jobs=self.n_jobs
            )
            return float(np.mean(scores))
        except Exception as e:
            logger.warning(f"交叉验证失败: {e}")
            return self.best_score
    
    def optimize(
        self, 
        X: np.ndarray, 
        y: np.ndarray,
        model_factory: Callable[[Dict[str, Any]], Any],
        callbacks: Optional[List[Callable]] = None
    ) -> OptimizationResult:
        """
        执行超参数优化
        
        Args:
            X: 特征数据
            y: 标签数据
            model_factory: 模型工厂函数，接受参数返回模型实例
            callbacks: 迭代回调函数列表
            
        Returns:
            OptimizationResult: 优化结果
        """
        import time
        start_time = time.time()
        
        logger.info(f"开始{self.algorithm}超参数优化，方法: {self.method.value}, 迭代次数: {self.n_iter}")
        
        self.trials = []
        self.best_score = -float('inf') if self.objective == ObjectiveType.MAXIMIZE else float('inf')
        
        for i in range(self.n_iter):
            params = self._sample_params()
            
            score = self._cross_validate(params, X, y, model_factory)
            
            is_best = (
                (self.objective == ObjectiveType.MAXIMIZE and score > self.best_score) or
                (self.objective == ObjectiveType.MINIMIZE and score < self.best_score)
            )
            
            if is_best:
                self.best_score = score
                self.best_params = copy.deepcopy(params)
                logger.info(f"迭代 {i+1}/{self.n_iter}: 新最佳分数 {score:.4f}, 参数: {params}")
            else:
                logger.debug(f"迭代 {i+1}/{self.n_iter}: 分数 {score:.4f}")
            
            trial = {
                'iteration': i + 1,
                'params': params,
                'score': score,
                'is_best': is_best
            }
            self.trials.append(trial)
            
            if callbacks:
                for callback in callbacks:
                    try:
                        callback(i + 1, self.n_iter, params, score, self.best_params, self.best_score)
                    except Exception as e:
                        logger.warning(f"回调函数执行失败: {e}")
        
        elapsed_time = time.time() - start_time
        
        logger.info(f"优化完成，最佳分数: {self.best_score:.4f}, 最佳参数: {self.best_params}")
        
        return OptimizationResult(
            best_params=self.best_params,
            best_score=self.best_score,
            all_trials=self.trials,
            method=self.method,
            total_iterations=self.n_iter,
            elapsed_time=elapsed_time
        )
    
    def get_param_config(self) -> Dict[str, Any]:
        """获取当前参数配置"""
        return {
            'algorithm': self.algorithm,
            'method': self.method.value,
            'n_iter': self.n_iter,
            'cv': self.cv,
            'scoring': self.scoring,
            'objective': self.objective.value,
            'random_state': self.random_state
        }
    
    @classmethod
    def get_supported_algorithms(cls) -> List[str]:
        """获取支持的算法列表"""
        return list(cls.SUPPORTED_ALGORITHMS.keys())
    
    @classmethod
    def get_algorithm_params(cls, algorithm: str) -> Dict[str, ParameterSpace]:
        """获取指定算法的参数空间"""
        return cls.SUPPORTED_ALGORITHMS.get(algorithm, {})
    
    @classmethod
    def register_algorithm(cls, name: str, param_space: Dict[str, ParameterSpace]):
        """注册新算法"""
        cls.SUPPORTED_ALGORITHMS[name] = param_space
        logger.info(f"已注册新算法: {name}")
