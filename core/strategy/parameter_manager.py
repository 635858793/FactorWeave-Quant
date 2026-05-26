from loguru import logger
"""
策略参数管理器 - 高性能参数验证、优化和管理

提供参数验证、优化建议、批量管理等功能，注重性能和准确性
"""

import copy
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from datetime import datetime
import json
import threading
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
import warnings

from scipy.optimize import differential_evolution

from .base_strategy import BaseStrategy, StrategyParameter

class ParameterOptimizationMethod(Enum):
    """参数优化方法"""
    GRID_SEARCH = "grid_search"          # 网格搜索
    RANDOM_SEARCH = "random_search"      # 随机搜索
    BAYESIAN = "bayesian"                # 贝叶斯优化
    GENETIC = "genetic"                  # 遗传算法
    PARTICLE_SWARM = "particle_swarm"    # 粒子群优化

@dataclass
class ParameterRange:
    """参数范围定义"""
    min_value: Union[int, float]
    max_value: Union[int, float]
    step: Optional[Union[int, float]] = None
    values: Optional[List[Any]] = None
    distribution: str = "uniform"  # uniform, normal, log_uniform

    def generate_values(self, count: int = 10) -> List[Any]:
        """生成参数值列表"""
        if self.values:
            return self.values

        if self.distribution == "uniform":
            if isinstance(self.min_value, int) and isinstance(self.max_value, int):
                return list(np.random.randint(self.min_value, self.max_value + 1, count))
            else:
                return list(np.random.uniform(self.min_value, self.max_value, count))
        elif self.distribution == "normal":
            mean = (self.min_value + self.max_value) / 2
            std = (self.max_value - self.min_value) / 6
            values = np.random.normal(mean, std, count)
            return list(np.clip(values, self.min_value, self.max_value))
        elif self.distribution == "log_uniform":
            log_min = np.log(max(self.min_value, 1e-10))
            log_max = np.log(self.max_value)
            log_values = np.random.uniform(log_min, log_max, count)
            return list(np.exp(log_values))

        return []

@dataclass
class ParameterOptimizationResult:
    """参数优化结果"""
    best_parameters: Dict[str, Any]
    best_score: float
    optimization_history: List[Dict[str, Any]] = field(default_factory=list)
    total_evaluations: int = 0
    optimization_time: float = 0.0
    convergence_info: Dict[str, Any] = field(default_factory=dict)

class ParameterValidator:
    """高性能参数验证器"""

    def __init__(self):
        """初始化验证器"""
        self._validation_cache: Dict[str, bool] = {}
        self._cache_lock = threading.RLock()
        self._validation_stats = {
            'total_validations': 0,
            'cache_hits': 0,
            'validation_errors': 0
        }

    def validate_parameter(self, param: StrategyParameter, value: Any,
                           use_cache: bool = True) -> Tuple[bool, str]:
        """验证单个参数

        Args:
            param: 参数定义
            value: 参数值
            use_cache: 是否使用缓存

        Returns:
            (是否有效, 错误信息)
        """
        # 生成缓存键
        cache_key = None
        if use_cache:
            cache_key = self._generate_cache_key(param, value)
            with self._cache_lock:
                if cache_key in self._validation_cache:
                    self._validation_stats['cache_hits'] += 1
                    return self._validation_cache[cache_key], ""

        self._validation_stats['total_validations'] += 1

        try:
            # 基本类型检查
            if not self._validate_type(param, value):
                error_msg = f"Type mismatch: expected {param.param_type.__name__}, got {type(value).__name__}"
                self._cache_result(cache_key, False, use_cache)
                return False, error_msg

            # 范围检查
            if not self._validate_range(param, value):
                error_msg = f"Value {value} out of range [{param.min_value}, {param.max_value}]"
                self._cache_result(cache_key, False, use_cache)
                return False, error_msg

            # 选择检查
            if not self._validate_choices(param, value):
                error_msg = f"Value {value} not in allowed choices {param.choices}"
                self._cache_result(cache_key, False, use_cache)
                return False, error_msg

            # 自定义验证
            if not self._validate_custom(param, value):
                error_msg = f"Custom validation failed for value {value}"
                self._cache_result(cache_key, False, use_cache)
                return False, error_msg

            self._cache_result(cache_key, True, use_cache)
            return True, ""

        except Exception as e:
            self._validation_stats['validation_errors'] += 1
            error_msg = f"Validation error: {str(e)}"
            self._cache_result(cache_key, False, use_cache)
            return False, error_msg

    def validate_parameters_batch(self, parameters: Dict[str, StrategyParameter],
                                  values: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
        """批量验证参数"""
        errors = {}

        for param_name, param in parameters.items():
            if param_name in values:
                valid, error = self.validate_parameter(
                    param, values[param_name])
                if not valid:
                    errors[param_name] = error
            elif param.required:
                errors[param_name] = f"Required parameter '{param_name}' is missing"

        return len(errors) == 0, errors

    def _validate_type(self, param: StrategyParameter, value: Any) -> bool:
        """验证类型"""
        if param.param_type == type(None) and value is None:
            return True

        if param.param_type in (int, float) and isinstance(value, (int, float)):
            return True

        return isinstance(value, param.param_type)

    def _validate_range(self, param: StrategyParameter, value: Any) -> bool:
        """验证范围"""
        if param.min_value is not None and value < param.min_value:
            return False
        if param.max_value is not None and value > param.max_value:
            return False
        return True

    def _validate_choices(self, param: StrategyParameter, value: Any) -> bool:
        """验证选择"""
        if param.choices is not None and value not in param.choices:
            return False
        return True

    def _validate_custom(self, param: StrategyParameter, value: Any) -> bool:
        """自定义验证 - 可扩展"""
        # 这里可以添加更复杂的验证逻辑
        return True

    def _generate_cache_key(self, param: StrategyParameter, value: Any) -> str:
        """生成缓存键"""
        key_data = f"{param.name}_{param.param_type.__name__}_{value}_{param.min_value}_{param.max_value}"
        return hashlib.md5(key_data.encode()).hexdigest()[:16]

    def _cache_result(self, cache_key: str, result: bool, use_cache: bool):
        """缓存验证结果"""
        if use_cache and cache_key:
            with self._cache_lock:
                self._validation_cache[cache_key] = result

    def clear_cache(self):
        """清空缓存"""
        with self._cache_lock:
            self._validation_cache.clear()

    def get_validation_stats(self) -> Dict[str, Any]:
        """获取验证统计"""
        stats = self._validation_stats.copy()
        total = stats['total_validations']
        if total > 0:
            stats['cache_hit_rate'] = stats['cache_hits'] / total
            stats['error_rate'] = stats['validation_errors'] / total
        else:
            stats['cache_hit_rate'] = 0.0
            stats['error_rate'] = 0.0

        with self._cache_lock:
            stats['cache_size'] = len(self._validation_cache)

        return stats

class StrategyParameterManager:
    """策略参数管理器 - 高性能参数管理和优化"""

    def __init__(self, max_workers: int = os.cpu_count() * 2):
        """初始化参数管理器

        Args:
            max_workers: 最大工作线程数
        """
        self.validator = ParameterValidator()
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # 参数模板和预设
        self._parameter_templates: Dict[str, Dict[str, StrategyParameter]] = {}
        self._parameter_presets: Dict[str, Dict[str, Any]] = {}

        # 优化历史
        self._optimization_history: List[ParameterOptimizationResult] = []

        # 线程安全锁
        self._lock = threading.RLock()

        # 性能统计
        self._stats = {
            'optimizations_run': 0,
            'parameters_validated': 0,
            'templates_created': 0,
            'presets_saved': 0
        }

    def register_parameter_template(self, template_name: str,
                                    parameters: Dict[str, StrategyParameter]):
        """注册参数模板"""
        with self._lock:
            self._parameter_templates[template_name] = parameters.copy()
            self._stats['templates_created'] += 1

    def get_parameter_template(self, template_name: str) -> Optional[Dict[str, StrategyParameter]]:
        """获取参数模板"""
        with self._lock:
            return self._parameter_templates.get(template_name)

    def save_parameter_preset(self, preset_name: str, parameters: Dict[str, Any]):
        """保存参数预设"""
        with self._lock:
            self._parameter_presets[preset_name] = parameters.copy()
            self._stats['presets_saved'] += 1

    def load_parameter_preset(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """加载参数预设"""
        with self._lock:
            return self._parameter_presets.get(preset_name)

    def validate_strategy_parameters(self, strategy: BaseStrategy,
                                     parameters: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
        """验证策略参数"""
        self._stats['parameters_validated'] += 1
        # 添加防御性编程，检查strategy是否有parameters属性
        if hasattr(strategy, 'parameters'):
            return self.validator.validate_parameters_batch(strategy.parameters, parameters)
        # 如果strategy是字典类型，直接使用parameters参数
        return self.validator.validate_parameters_batch({}, parameters)

    def optimize_parameters(self, strategy: BaseStrategy,
                            data: pd.DataFrame,
                            parameter_ranges: Dict[str, ParameterRange],
                            objective_function: Callable,
                            method: ParameterOptimizationMethod = ParameterOptimizationMethod.GRID_SEARCH,
                            max_evaluations: int = 100,
                            parallel: bool = True) -> ParameterOptimizationResult:
        """优化策略参数

        Args:
            strategy: 策略实例
            data: 历史数据
            parameter_ranges: 参数范围定义
            objective_function: 目标函数
            method: 优化方法
            max_evaluations: 最大评估次数
            parallel: 是否并行执行

        Returns:
            优化结果
        """
        start_time = datetime.now()
        self._stats['optimizations_run'] += 1

        try:
            if method == ParameterOptimizationMethod.GRID_SEARCH:
                result = self._grid_search_optimization(
                    strategy, data, parameter_ranges, objective_function,
                    max_evaluations, parallel
                )
            elif method == ParameterOptimizationMethod.RANDOM_SEARCH:
                result = self._random_search_optimization(
                    strategy, data, parameter_ranges, objective_function,
                    max_evaluations, parallel
                )
            elif method == ParameterOptimizationMethod.BAYESIAN:
                result = self._bayesian_optimization(
                    strategy, data, parameter_ranges, objective_function,
                    max_evaluations, parallel
                )
            elif method == ParameterOptimizationMethod.GENETIC:
                result = self._genetic_algorithm(
                    strategy, data, parameter_ranges, objective_function,
                    max_evaluations, parallel
                )
            elif method == ParameterOptimizationMethod.PARTICLE_SWARM:
                result = self._particle_swarm(
                    strategy, data, parameter_ranges, objective_function,
                    max_evaluations, parallel
                )
            else:
                result = self._grid_search_optimization(
                    strategy, data, parameter_ranges, objective_function,
                    max_evaluations, parallel
                )

            # 记录优化时间
            result.optimization_time = (
                datetime.now() - start_time).total_seconds()

            # 保存优化历史
            with self._lock:
                self._optimization_history.append(result)

            return result

        except Exception as e:
            # 返回错误结果
            return ParameterOptimizationResult(
                best_parameters={},
                best_score=float('-inf'),
                total_evaluations=0,
                optimization_time=(datetime.now() - start_time).total_seconds()
            )

    def _grid_search_optimization(self, strategy: BaseStrategy, data: pd.DataFrame,
                                  parameter_ranges: Dict[str, ParameterRange],
                                  objective_function: Callable,
                                  max_evaluations: int, parallel: bool) -> ParameterOptimizationResult:
        """网格搜索优化"""
        # 生成参数组合
        param_combinations = self._generate_parameter_combinations(
            parameter_ranges, max_evaluations)

        best_score = float('-inf')
        best_params = {}
        evaluation_history = []

        if parallel and len(param_combinations) > 1:
            # 并行评估
            futures = []
            for params in param_combinations:
                future = self.executor.submit(
                    self._evaluate_parameters, strategy, data, params, objective_function
                )
                futures.append((future, params))

            for future, params in futures:
                try:
                    score = future.result(timeout=30)  # 30秒超时
                    evaluation_history.append(
                        {'parameters': params, 'score': score})

                    if score > best_score:
                        best_score = score
                        best_params = params.copy()
                except Exception as e:
                    warnings.warn(f"Parameter evaluation failed: {e}")
        else:
            # 串行评估
            for params in param_combinations:
                try:
                    score = self._evaluate_parameters(
                        strategy, data, params, objective_function)
                    evaluation_history.append(
                        {'parameters': params, 'score': score})

                    if score > best_score:
                        best_score = score
                        best_params = params.copy()
                except Exception as e:
                    warnings.warn(f"Parameter evaluation failed: {e}")

        return ParameterOptimizationResult(
            best_parameters=best_params,
            best_score=best_score,
            optimization_history=evaluation_history,
            total_evaluations=len(evaluation_history)
        )

    def _random_search_optimization(self, strategy: BaseStrategy, data: pd.DataFrame,
                                    parameter_ranges: Dict[str, ParameterRange],
                                    objective_function: Callable,
                                    max_evaluations: int, parallel: bool) -> ParameterOptimizationResult:
        """随机搜索优化"""
        param_combinations = []

        for _ in range(max_evaluations):
            params = {}
            for param_name, param_range in parameter_ranges.items():
                values = param_range.generate_values(1)
                if values:
                    params[param_name] = values[0]
            param_combinations.append(params)

        best_score = float('-inf')
        best_params = {}
        evaluation_history = []

        if parallel and len(param_combinations) > 1:
            futures = []
            for params in param_combinations:
                future = self.executor.submit(
                    self._evaluate_parameters, strategy, data, params, objective_function
                )
                futures.append((future, params))

            for future, params in futures:
                try:
                    score = future.result(timeout=30)
                    evaluation_history.append({'parameters': params, 'score': score})
                    if score > best_score:
                        best_score = score
                        best_params = params.copy()
                except Exception as e:
                    warnings.warn(f"Parameter evaluation failed: {e}")
        else:
            for params in param_combinations:
                try:
                    score = self._evaluate_parameters(strategy, data, params, objective_function)
                    evaluation_history.append({'parameters': params, 'score': score})
                    if score > best_score:
                        best_score = score
                        best_params = params.copy()
                except Exception as e:
                    warnings.warn(f"Parameter evaluation failed: {e}")

        return ParameterOptimizationResult(
            best_parameters=best_params,
            best_score=best_score,
            optimization_history=evaluation_history,
            total_evaluations=len(evaluation_history)
        )

    def _bayesian_optimization(self, strategy: BaseStrategy, data: pd.DataFrame,
                               parameter_ranges: Dict[str, ParameterRange],
                               objective_function: Callable,
                               max_evaluations: int, parallel: bool) -> ParameterOptimizationResult:
        """基于统一 BayesianOptimizer 模块的贝叶斯优化（GP+UCB, kappa=2.576）"""
        from core.optimization import BayesianOptimizer, ParameterSpec, OptParameterType, AcquisitionFunction

        param_names = list(parameter_ranges.keys())
        n_params = len(param_names)
        if n_params == 0:
            return ParameterOptimizationResult(
                best_parameters={}, best_score=float('-inf'),
                optimization_history=[], total_evaluations=0
            )

        specs = []
        for name in param_names:
            pr = parameter_ranges[name]
            is_int = isinstance(pr.min_value, int) and isinstance(pr.max_value, int)
            if pr.values:
                specs.append(ParameterSpec(name, OptParameterType.ORDINAL, values=pr.values))
            elif is_int:
                specs.append(ParameterSpec(name, OptParameterType.DISCRETE,
                             bounds=(int(pr.min_value), int(pr.max_value))))
            else:
                specs.append(ParameterSpec(name, OptParameterType.CONTINUOUS,
                             bounds=(float(pr.min_value), float(pr.max_value))))

        evaluation_history = []

        def wrapped_objective(**kwargs):
            score = float(self._evaluate_parameters(strategy, data, kwargs, objective_function))
            evaluation_history.append({'parameters': kwargs.copy(), 'score': score})
            return score

        n_initial = max(5, n_params * 2)

        optimizer = BayesianOptimizer(
            specs,
            acquisition=AcquisitionFunction.UCB,
            kappa_ucb=2.576,
            random_state=42,
        )

        result = optimizer.optimize(
            wrapped_objective,
            n_calls=max_evaluations,
            n_initial_points=n_initial,
            n_candidates_per_iter=min(5000, 1000 * n_params),
            maximize=True,
        )

        return ParameterOptimizationResult(
            best_parameters=result.best_params,
            best_score=result.best_score,
            optimization_history=evaluation_history,
            total_evaluations=len(evaluation_history),
            convergence_info={'method': 'gaussian_process_bayesian', 'n_initial': n_initial,
                            'n_iter': max(1, max_evaluations - n_initial)}
        )

    def _genetic_algorithm(self, strategy: BaseStrategy, data: pd.DataFrame,
                           parameter_ranges: Dict[str, ParameterRange],
                           objective_function: Callable,
                           max_evaluations: int, parallel: bool) -> ParameterOptimizationResult:
        """基于scipy.optimize.differential_evolution的遗传算法（差分进化）优化"""
        param_names = list(parameter_ranges.keys())
        if not param_names:
            return ParameterOptimizationResult(
                best_parameters={}, best_score=float('-inf'),
                optimization_history=[], total_evaluations=0
            )

        bounds = []
        int_mask = []
        for name in param_names:
            pr = parameter_ranges[name]
            bounds.append((float(pr.min_value), float(pr.max_value)))
            int_mask.append(isinstance(pr.min_value, int) and isinstance(pr.max_value, int))

        evaluation_history = []
        best_score_val = float('-inf')
        best_params_val = {}

        def obj_func(x):
            params = {}
            for i, name in enumerate(param_names):
                raw_val = float(x[i])
                params[name] = int(round(raw_val)) if int_mask[i] else raw_val

            score = float(self._evaluate_parameters(strategy, data, params, objective_function))
            evaluation_history.append({'parameters': params.copy(), 'score': score})

            nonlocal best_score_val, best_params_val
            if score > best_score_val:
                best_score_val = score
                best_params_val = params.copy()

            return -score

        pop_size = min(15, max(5, len(param_names) * 3))
        max_iter = max(1, int(max_evaluations / pop_size))

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _ = differential_evolution(
                obj_func,
                bounds,
                maxiter=max_iter,
                popsize=pop_size,
                mutation=(0.5, 1.0),
                recombination=0.7,
                seed=None,
                polish=False,
                workers=1
            )

        return ParameterOptimizationResult(
            best_parameters=best_params_val,
            best_score=best_score_val,
            optimization_history=evaluation_history,
            total_evaluations=len(evaluation_history),
            convergence_info={'method': 'differential_evolution', 'pop_size': pop_size,
                            'max_iter': max_iter}
        )

    def _particle_swarm(self, strategy: BaseStrategy, data: pd.DataFrame,
                         parameter_ranges: Dict[str, ParameterRange],
                         objective_function: Callable,
                         max_evaluations: int, parallel: bool) -> ParameterOptimizationResult:
        """粒子群优化"""
        param_names = list(parameter_ranges.keys())
        if not param_names:
            return ParameterOptimizationResult(
                best_parameters={}, best_score=float('-inf'),
                optimization_history=[], total_evaluations=0
            )

        n_particles = max(5, min(15, max_evaluations // 10))
        w = 0.7
        c1 = 1.5
        c2 = 2.0
        evaluation_history = []

        def _random_params():
            params = {}
            for pn, pr in parameter_ranges.items():
                vals = pr.generate_values(1)
                if vals:
                    params[pn] = float(vals[0])
            return params

        def _random_velocity():
            velocity = {}
            for pn, pr in parameter_ranges.items():
                scale = float(pr.max_value - pr.min_value) * 0.1
                velocity[pn] = np.random.uniform(-scale, scale)
            return velocity

        def _clip_params(params):
            clipped = {}
            for pn, pr in parameter_ranges.items():
                clipped[pn] = float(np.clip(params[pn], pr.min_value, pr.max_value))
            return clipped

        def _evaluate_particle(params):
            int_params = {}
            for pn, pr in parameter_ranges.items():
                if isinstance(pr.min_value, int):
                    int_params[pn] = int(round(params[pn]))
                else:
                    int_params[pn] = params[pn]
            score = self._evaluate_parameters(strategy, data, int_params, objective_function)
            evaluation_history.append({'parameters': int_params, 'score': score})
            return score

        particles = [_random_params() for _ in range(n_particles)]
        velocities = [_random_velocity() for _ in range(n_particles)]
        personal_best = [p.copy() for p in particles]
        personal_best_scores = []

        for i, p in enumerate(particles):
            try:
                personal_best_scores.append(_evaluate_particle(p))
            except Exception as e:
                warnings.warn(f"PSO initial evaluation failed: {e}")
                personal_best_scores.append(float('-inf'))

        best_idx = int(np.argmax(personal_best_scores))
        global_best = particles[best_idx].copy()
        global_best_score = personal_best_scores[best_idx]

        iterations = max(1, (max_evaluations - n_particles) // n_particles)
        for _ in range(iterations):
            for i in range(n_particles):
                for pn in param_names:
                    r1, r2 = np.random.random(), np.random.random()
                    velocities[i][pn] = (
                        w * velocities[i][pn]
                        + c1 * r1 * (personal_best[i][pn] - particles[i][pn])
                        + c2 * r2 * (global_best[pn] - particles[i][pn])
                    )
                    particles[i][pn] = particles[i][pn] + velocities[i][pn]

                particles[i] = _clip_params(particles[i])

            for i, p in enumerate(particles):
                try:
                    score = _evaluate_particle(p)
                except Exception as e:
                    warnings.warn(f"PSO iteration evaluation failed: {e}")
                    continue

                if score > personal_best_scores[i]:
                    personal_best_scores[i] = score
                    personal_best[i] = p.copy()

                if score > global_best_score:
                    global_best_score = score
                    global_best = p.copy()

        best = max(evaluation_history, key=lambda x: x['score']) if evaluation_history else {'parameters': {}, 'score': float('-inf')}

        return ParameterOptimizationResult(
            best_parameters=best['parameters'],
            best_score=best['score'],
            optimization_history=evaluation_history,
            total_evaluations=len(evaluation_history)
        )

    def _generate_parameter_combinations(self, parameter_ranges: Dict[str, ParameterRange],
                                         max_combinations: int) -> List[Dict[str, Any]]:
        """生成参数组合"""
        combinations = []
        param_names = list(parameter_ranges.keys())

        if not param_names:
            return [{}]

        # 计算每个参数的值数量
        values_per_param = max(
            1, int(max_combinations ** (1.0 / len(param_names))))

        # 生成每个参数的值列表
        param_values = {}
        for param_name, param_range in parameter_ranges.items():
            param_values[param_name] = param_range.generate_values(
                values_per_param)

        # 生成组合（简化版，避免笛卡尔积过大）
        import itertools

        value_lists = [param_values[name] for name in param_names]
        for combination in itertools.product(*value_lists):
            if len(combinations) >= max_combinations:
                break

            param_dict = dict(zip(param_names, combination))
            combinations.append(param_dict)

        return combinations[:max_combinations]

    def _evaluate_parameters(self, strategy: BaseStrategy, data: pd.DataFrame,
                             parameters: Dict[str, Any], objective_function: Callable) -> float:
        """评估参数组合"""
        strategy_copy = copy.deepcopy(strategy)

        for param_name, param_value in parameters.items():
            strategy_copy.set_parameter(param_name, param_value)

        signals = strategy_copy.generate_signals(data)

        score = objective_function(signals, data)

        return float(score)

    def get_optimization_history(self) -> List[ParameterOptimizationResult]:
        """获取优化历史"""
        with self._lock:
            return self._optimization_history.copy()

    def clear_optimization_history(self):
        """清空优化历史"""
        with self._lock:
            self._optimization_history.clear()

    def export_parameters(self, filepath: Union[str, Path],
                          parameters: Dict[str, Any]) -> bool:
        """导出参数到文件"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(parameters, f, indent=2,
                          ensure_ascii=False, default=str)
            return True
        except Exception as e:
            warnings.warn(f"Failed to export parameters: {e}")
            return False

    def import_parameters(self, filepath: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """从文件导入参数"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            warnings.warn(f"Failed to import parameters: {e}")
            return None

    def get_manager_stats(self) -> Dict[str, Any]:
        """获取管理器统计"""
        stats = self._stats.copy()
        stats.update(self.validator.get_validation_stats())

        with self._lock:
            stats['optimization_history_size'] = len(
                self._optimization_history)
            stats['parameter_templates'] = len(self._parameter_templates)
            stats['parameter_presets'] = len(self._parameter_presets)

        return stats

    def shutdown(self):
        """关闭管理器"""
        self.executor.shutdown(wait=True)
        self.validator.clear_cache()

    def __del__(self):
        """析构函数"""
        try:
            self.shutdown()
        except Exception as e:
            logger.debug(f"参数管理器shutdown失败: {e}")

# 全局参数管理器实例
_parameter_manager: Optional[StrategyParameterManager] = None
_manager_lock = threading.RLock()

def get_parameter_manager() -> StrategyParameterManager:
    """获取全局参数管理器实例

    Returns:
        参数管理器实例
    """
    global _parameter_manager

    with _manager_lock:
        if _parameter_manager is None:
            _parameter_manager = StrategyParameterManager()

        return _parameter_manager

def initialize_parameter_manager() -> StrategyParameterManager:
    """初始化参数管理器

    Returns:
        参数管理器实例
    """
    global _parameter_manager

    with _manager_lock:
        _parameter_manager = StrategyParameterManager()
        return _parameter_manager
