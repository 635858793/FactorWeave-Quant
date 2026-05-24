from loguru import logger
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from itertools import product
import random
import math

from core.strategy_extensions import TradingPerformanceMetrics


class OptimizationMethod(Enum):
    """参数优化方法"""
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    BAYESIAN = "bayesian"


class OptimizationObjective(Enum):
    """优化目标"""
    MAXIMIZE_SHARPE = "sharpe_ratio"
    MAXIMIZE_RETURN = "total_return"
    MINIMIZE_DRAWDOWN = "max_drawdown"
    MAXIMIZE_WIN_RATE = "win_rate"


@dataclass
class OptimizationResult:
    """单次优化结果"""
    parameters: Dict[str, Any]
    metrics: TradingPerformanceMetrics
    score: float
    rank: int


@dataclass
class OptimizationConfig:
    """优化配置"""
    method: OptimizationMethod = OptimizationMethod.GRID_SEARCH
    objective: OptimizationObjective = OptimizationObjective.MAXIMIZE_SHARPE
    max_iterations: int = 100
    n_jobs: int = 1
    cv_folds: int = 1
    early_stopping_rounds: int = 10
    random_seed: int = 42
    verbose: bool = True


@dataclass
class OptimizationRun:
    """优化运行状态"""
    run_id: str
    config: OptimizationConfig
    start_time: datetime
    status: str = "pending"
    progress: float = 0.0
    current_iteration: int = 0
    total_iterations: int = 0
    best_result: Optional[OptimizationResult] = None
    results: List[OptimizationResult] = field(default_factory=list)
    error_message: Optional[str] = None
    overfitting_result: Optional[dict] = None



@dataclass
class WalkForwardWindow:
    """Walk-Forward Analysis 单个窗口结果"""
    window_index: int
    train_start: Any
    train_end: Any
    test_start: Any
    test_end: Any
    best_params: Dict[str, Any]
    train_metrics: Any
    test_metrics: Dict[str, Any]
    train_score: float = 0.0
    test_score: float = 0.0

class ParameterGrid:
    """参数网格生成器"""
    
    def __init__(self, param_grid: Dict[str, Any]):
        self.param_grid = param_grid
    
    def generate(self) -> List[Dict[str, Any]]:
        """生成所有参数组合"""
        keys = list(self.param_grid.keys())
        values = [self._expand(v) for v in self.param_grid.values()]
        
        combinations = list(product(*values))
        
        param_list = []
        for combo in combinations:
            param_dict = {}
            for i, key in enumerate(keys):
                param_dict[key] = combo[i]
            param_list.append(param_dict)
        
        return param_list
    
    def _expand(self, value):
        """展开参数值"""
        if isinstance(value, list):
            return value
        elif isinstance(value, range):
            return list(value)
        elif isinstance(value, dict):
            if 'start' in value and 'end' in value and 'step' in value:
                return list(range(
                    value['start'],
                    value['end'],
                    value.get('step', 1)
                ))
            elif 'values' in value:
                return value['values']
        return [value]


class StrategyParameterOptimizer:
    """
    策略参数优化器
    
    支持多种优化方法:
    - 网格搜索 (Grid Search)
    - 随机搜索 (Random Search)
    - 贝叶斯优化 (Bayesian Optimization)
    """
    
    def __init__(self):
        self.logger = logger.bind(module=self.__class__.__name__)
        self._current_run: Optional[OptimizationRun] = None
    
    def optimize(
        self,
        objective_function: Callable[[Dict[str, Any]], Tuple[TradingPerformanceMetrics, float]],
        param_grid: Dict[str, Any],
        config: Optional[OptimizationConfig] = None,
        train_bars: int = 0,
        n_params: int = 0,
        walk_forward_result: Optional[dict] = None
    ) -> OptimizationRun:
        """
        执行参数优化
        
        Args:
            objective_function: 目标函数，输入参数，返回(性能指标, 得分)
            param_grid: 参数网格
            config: 优化配置
            train_bars: 训练集K线数量，用于过拟合检测
            n_params: 优化参数数量，用于过拟合检测
            walk_forward_result: Walk-Forward结果，用于过拟合IS/OOS对比
            
        Returns:
            OptimizationRun: 优化结果
        """
        if config is None:
            config = OptimizationConfig()
        
        run_id = f"opt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        run = OptimizationRun(
            run_id=run_id,
            config=config,
            start_time=datetime.now(),
            status="running"
        )
        
        self._current_run = run
        
        try:
            random.seed(config.random_seed)
            
            if config.method == OptimizationMethod.GRID_SEARCH:
                results = self._grid_search(objective_function, param_grid, run)
            elif config.method == OptimizationMethod.RANDOM_SEARCH:
                results = self._random_search(objective_function, param_grid, config, run)
            elif config.method == OptimizationMethod.BAYESIAN:
                results = self._bayesian_optimization(objective_function, param_grid, config, run)
            else:
                raise ValueError(f"不支持的优化方法: {config.method}")
            
            run.results = results
            run.status = "completed"
            run.progress = 1.0
            
            if results:
                if config.objective in (
                    OptimizationObjective.MINIMIZE_DRAWDOWN,
                ):
                    run.best_result = min(results, key=lambda x: x.score)
                else:
                    run.best_result = max(results, key=lambda x: x.score)
            
            self.logger.info(f"优化完成: {len(results)} 个组合, 最佳得分: {run.best_result.score if run.best_result else 'N/A'}")

            if run.best_result and run.best_result.metrics:
                train_result = {
                    'sharpe_ratio': run.best_result.metrics.sharpe_ratio,
                    'train_bars': train_bars,
                    'n_params': n_params,
                }
                run.overfitting_result = self._check_overfitting(train_result, walk_forward_result)
                if run.overfitting_result.get('is_overfit'):
                    self.logger.warning(f"过拟合风险检测: {run.overfitting_result['warnings']}")
                elif run.overfitting_result.get('warnings'):
                    self.logger.info(f"过拟合提示: {run.overfitting_result['warnings']}")
            
        except Exception as e:
            run.status = "failed"
            run.error_message = str(e)
            self.logger.error(f"优化失败: {e}")
        
        return run
    
    def _grid_search(
        self,
        objective_function: Callable,
        param_grid: Dict[str, Any],
        run: OptimizationRun
    ) -> List[OptimizationResult]:
        """网格搜索"""
        grid = ParameterGrid(param_grid)
        param_combinations = grid.generate()
        
        run.total_iterations = len(param_combinations)
        results = []
        
        for i, params in enumerate(param_combinations):
            try:
                metrics, score = objective_function(params)
                
                result = OptimizationResult(
                    parameters=params.copy(),
                    metrics=metrics,
                    score=score,
                    rank=i + 1
                )
                results.append(result)
                
                run.current_iteration = i + 1
                run.progress = (i + 1) / len(param_combinations)
                
                if run.config.verbose:
                    self.logger.info(f"网格搜索 [{i+1}/{len(param_combinations)}]: score={score:.4f}")
                    
            except Exception as e:
                self.logger.warning(f"参数组合 {params} 执行失败: {e}")
        
        return results
    
    def _random_search(
        self,
        objective_function: Callable,
        param_grid: Dict[str, Any],
        config: OptimizationConfig,
        run: OptimizationRun
    ) -> List[OptimizationResult]:
        """随机搜索"""
        param_combinations = self._generate_random_params(param_grid, config.max_iterations)
        
        run.total_iterations = len(param_combinations)
        results = []
        
        for i, params in enumerate(param_combinations):
            try:
                metrics, score = objective_function(params)
                
                result = OptimizationResult(
                    parameters=params.copy(),
                    metrics=metrics,
                    score=score,
                    rank=i + 1
                )
                results.append(result)
                
                run.current_iteration = i + 1
                run.progress = (i + 1) / len(param_combinations)
                
                if run.config.verbose:
                    self.logger.info(f"随机搜索 [{i+1}/{len(param_combinations)}]: score={score:.4f}")
                    
            except Exception as e:
                self.logger.warning(f"参数组合 {params} 执行失败: {e}")
        
        return results
    
    def _generate_random_params(
        self,
        param_grid: Dict[str, Any],
        n_samples: int
    ) -> List[Dict[str, Any]]:
        """生成随机参数组合"""
        results = []
        expanded_grid = ParameterGrid(param_grid).generate()
        
        if len(expanded_grid) <= n_samples:
            return expanded_grid
        
        indices = random.sample(range(len(expanded_grid)), n_samples)
        return [expanded_grid[i] for i in indices]
    
    def _params_to_vector(self, params: Dict[str, Any], param_grid: Dict[str, Any]) -> 'np.ndarray':
        """将参数字典转换为数值向量"""
        import numpy as np
        vec = []
        for name, values in param_grid.items():
            val = params[name]
            if isinstance(val, (int, float)):
                vec.append(float(val))
            else:
                vec.append(float(values.index(val)))
        return np.array(vec)

    def _idx_to_vector(self, idx: int, param_names: list, param_values: list) -> 'np.ndarray':
        """将扁平索引直接转换为数值向量（跳过中间参数字典）"""
        import numpy as np
        remaining = idx
        vec_reversed = []
        for name, values in zip(reversed(param_names), reversed(param_values)):
            ordinal = remaining % len(values)
            val = values[ordinal]
            if isinstance(val, (int, float)):
                vec_reversed.append(float(val))
            else:
                vec_reversed.append(float(ordinal))
            remaining //= len(values)
        return np.array(list(reversed(vec_reversed)))

    def _bayesian_optimization(
        self,
        objective_function: Callable,
        param_grid: Dict[str, Any],
        config: OptimizationConfig,
        run: OptimizationRun
    ) -> List[OptimizationResult]:
        """贝叶斯优化：GP代理模型在真实多维参数空间上拟合，不可用时回退到最近邻启发式"""
        import numpy as np

        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        n_combinations = int(np.prod([len(v) for v in param_values]))
        n_iterations = min(config.max_iterations, n_combinations)
        n_initial = min(10, n_combinations)
        n_dims = len(param_names)

        np.random.seed(config.random_seed if config.random_seed is not None else 42)

        _gp_available = False
        _GaussianProcessRegressor = None
        _Matern = None
        _WhiteKernel = None
        _ConstantKernel = None
        try:
            from sklearn.gaussian_process import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import Matern, WhiteKernel, ConstantKernel
            _GaussianProcessRegressor = GaussianProcessRegressor
            _Matern = Matern
            _WhiteKernel = WhiteKernel
            _ConstantKernel = ConstantKernel
            _gp_available = True
            _gp_fail_count = 0
            _GP_RESET_INTERVAL = 5
            self.logger.info("贝叶斯优化: 使用真实高斯过程 (GaussianProcessRegressor) 作为代理模型（多维参数空间）")
        except ImportError:
            self.logger.warning("贝叶斯优化: sklearn.gaussian_process 不可用，回退到最近邻启发式代理模型")

        _norm_available = False
        try:
            from scipy.stats import norm
            _norm_available = True
        except ImportError:
            pass

        all_indices = list(range(n_combinations))
        initial_indices = list(np.random.choice(n_combinations, size=n_initial, replace=False))

        X_evaluated = []
        y_evaluated = []
        results = []

        for idx in initial_indices:
            params = self._idx_to_params(idx, param_names, param_values)
            params_vec = self._idx_to_vector(idx, param_names, param_values)
            metrics, score = objective_function(params)
            result = OptimizationResult(
                parameters=params.copy(),
                metrics=metrics,
                score=score,
                rank=len(results) + 1
            )
            results.append(result)
            X_evaluated.append(params_vec)
            y_evaluated.append(score)

        X_evaluated = np.array(X_evaluated)
        y_evaluated = np.array(y_evaluated)

        if config.objective == OptimizationObjective.MINIMIZE_DRAWDOWN:
            best_score = y_evaluated.min()
        else:
            best_score = y_evaluated.max()

        no_improvement_count = 0
        xi = 0.01

        remaining = [i for i in all_indices if i not in initial_indices]

        for _ in range(n_iterations - n_initial):
            if not remaining:
                break

            n_candidates = min(1000, len(remaining))
            candidate_indices = list(np.random.choice(remaining, size=n_candidates, replace=False))
            X_candidates = np.array([self._idx_to_vector(ci, param_names, param_values)
                                     for ci in candidate_indices])

            best_ei = -np.inf
            best_candidate = None

            if _gp_available and len(X_evaluated) >= 5:
                try:
                    kernel = (_ConstantKernel(1.0, constant_value_bounds=(1e-3, 1e3))
                              * _Matern(length_scale=1.0, length_scale_bounds=(1e-3, 1e3), nu=2.5)
                              + _WhiteKernel(noise_level=0.01, noise_level_bounds=(1e-5, 1.0)))
                    gp = _GaussianProcessRegressor(
                        kernel=kernel,
                        n_restarts_optimizer=5,
                        random_state=config.random_seed,
                        normalize_y=True
                    )
                    gp.fit(X_evaluated, y_evaluated)
                    mu, sigma = gp.predict(X_candidates, return_std=True)

                    for j, candidate_idx in enumerate(candidate_indices):
                        if config.objective == OptimizationObjective.MINIMIZE_DRAWDOWN:
                            improvement = -(mu[j] - best_score + xi)
                        else:
                            improvement = mu[j] - best_score - xi

                        if sigma[j] > 1e-9 and _norm_available:
                            Z = improvement / sigma[j]
                            from scipy.stats import norm
                            ei = improvement * norm.cdf(Z) + sigma[j] * norm.pdf(Z)
                        else:
                            ei = max(0.0, improvement)

                        if ei > best_ei:
                            best_ei = ei
                            best_candidate = candidate_idx

                    _gp_fail_count = 0
                except Exception as e:
                    _gp_fail_count += 1
                    self.logger.warning(f"高斯过程拟合失败: {e}，回退到最近邻启发式（连续失败 {_gp_fail_count}/{_GP_RESET_INTERVAL}）")
                    _gp_available = False
                    if _gp_fail_count >= _GP_RESET_INTERVAL:
                        self.logger.info(f"GP代理模型已连续失败 {_gp_fail_count} 次，尝试重新启用GP")
                        _gp_available = True
                        _gp_fail_count = 0

            if not _gp_available or best_candidate is None:
                best_ei = -1.0
                best_candidate = None
                for candidate_idx in candidate_indices:
                    candidate_vec = self._idx_to_vector(candidate_idx, param_names, param_values)
                    distances = np.sqrt(np.sum((X_evaluated - candidate_vec) ** 2, axis=1))
                    nearest_idx = int(np.argmin(distances))
                    mu = y_evaluated[nearest_idx]

                    if config.objective == OptimizationObjective.MINIMIZE_DRAWDOWN:
                        ei_value = max(0.0, -(mu - best_score + xi))
                    else:
                        ei_value = max(0.0, mu - best_score + xi)

                    if ei_value > best_ei:
                        best_ei = ei_value
                        best_candidate = candidate_idx

            if best_candidate is None:
                break

            remaining.remove(best_candidate)

            best_vec = self._idx_to_vector(best_candidate, param_names, param_values)
            params = self._idx_to_params(best_candidate, param_names, param_values)
            metrics, score = objective_function(params)

            result = OptimizationResult(
                parameters=params.copy(),
                metrics=metrics,
                score=score,
                rank=len(results) + 1
            )
            results.append(result)
            X_evaluated = np.vstack([X_evaluated, best_vec])
            y_evaluated = np.append(y_evaluated, score)

            run.current_iteration = len(results)
            run.progress = len(results) / n_iterations

            if config.objective == OptimizationObjective.MINIMIZE_DRAWDOWN:
                improved = score < best_score
            else:
                improved = score > best_score

            if improved:
                best_score = score
                no_improvement_count = 0
            else:
                no_improvement_count += 1

            if no_improvement_count >= run.config.early_stopping_rounds:
                self.logger.info(f"早停: 连续 {no_improvement_count} 次无改进")
                break

            if run.config.verbose:
                model_label = "GP" if _gp_available else "最近邻"
                self.logger.info(f"贝叶斯优化[{model_label}] [{len(results)}/{n_iterations}]: score={score:.4f}")

        return results

    def _idx_to_params(self, idx: int, param_names: list, param_values: list) -> Dict[str, Any]:
        """将扁平索引映射回参数组合"""
        params = {}
        remaining = idx
        for name, values in zip(reversed(param_names), reversed(param_values)):
            n = len(values)
            params[name] = values[remaining % n]
            remaining //= n
        return params
    
    def get_best_parameters(self, n_top: int = 5) -> List[Dict[str, Any]]:
        """获取最佳参数组合"""
        if not self._current_run or not self._current_run.results:
            return []
        
        sorted_results = sorted(
            self._current_run.results,
            key=lambda x: x.score,
            reverse=True
        )
        
        return [r.parameters for r in sorted_results[:n_top]]
    
    def get_optimization_report(self) -> Optional[Dict[str, Any]]:
        """获取优化报告"""
        if not self._current_run:
            return None
        
        run = self._current_run
        
        report = {
            'run_id': run.run_id,
            'method': run.config.method.value,
            'objective': run.config.objective.value,
            'status': run.status,
            'total_iterations': run.total_iterations,
            'completed_iterations': run.current_iteration,
            'progress': run.progress,
            'duration_seconds': (datetime.now() - run.start_time).total_seconds(),
        }
        
        if run.best_result:
            report['best_score'] = run.best_result.score
            report['best_parameters'] = run.best_result.parameters
            report['best_metrics'] = {
                'total_return': run.best_result.metrics.total_return,
                'sharpe_ratio': run.best_result.metrics.sharpe_ratio,
                'max_drawdown': run.best_result.metrics.max_drawdown,
                'win_rate': run.best_result.metrics.win_rate,
            }
        
        if run.error_message:
            report['error'] = run.error_message
        
        return report

    def walk_forward_optimization(
        self,
        data,
        param_grid: Dict[str, Any],
        objective_function_factory: Callable,
        train_size: int = 252,
        test_size: int = 63,
        step_size: int = 63,
        anchored: bool = True,
        config: Optional[OptimizationConfig] = None
    ) -> Dict[str, Any]:
        if config is None:
            config = OptimizationConfig()

        results: Dict[str, Any] = {
            "windows": [],
            "oos_performance": [],
            "optimized_params": [],
            "aggregate_metrics": {}
        }

        total_bars = len(data)
        start_idx = 0
        window_index = 0

        while start_idx + train_size + test_size <= total_bars:
            if anchored:
                train_data = data.iloc[:start_idx + train_size]
            else:
                train_data = data.iloc[start_idx:start_idx + train_size]

            test_data = data.iloc[start_idx + train_size:start_idx + train_size + test_size]

            train_objective = objective_function_factory(train_data)
            train_run = self.optimize(train_objective, param_grid, config)

            if train_run.best_result is None:
                self.logger.warning(f"窗口 {window_index}: 训练段优化未找到有效结果，跳过")
                start_idx += step_size
                continue

            best_params = train_run.best_result.parameters
            train_score = train_run.best_result.score

            test_objective = objective_function_factory(test_data)
            test_metrics, test_score = test_objective(best_params)

            oos_result = {
                "sharpe": test_metrics.sharpe_ratio,
                "total_return": test_metrics.total_return,
                "max_drawdown": test_metrics.max_drawdown,
                "win_rate": test_metrics.win_rate,
                "score": test_score
            }

            train_data_index = train_data.index
            test_data_index = test_data.index

            window = WalkForwardWindow(
                window_index=window_index,
                train_start=train_data_index[0],
                train_end=train_data_index[-1],
                test_start=test_data_index[0],
                test_end=test_data_index[-1],
                best_params=best_params.copy(),
                train_metrics=train_run.best_result.metrics,
                test_metrics=oos_result.copy(),
                train_score=train_score,
                test_score=test_score
            )

            results["windows"].append(window)
            results["oos_performance"].append(oos_result)
            results["optimized_params"].append(best_params.copy())

            self.logger.info(
                f"窗口 {window_index}: "
                f"训练={train_data_index[0]}~{train_data_index[-1]} "
                f"测试={test_data_index[0]}~{test_data_index[-1]} "
                f"训练得分={train_score:.4f} OOS得分={test_score:.4f}"
            )

            start_idx += step_size
            window_index += 1

        if results["windows"]:
            results["aggregate_metrics"] = self._calculate_aggregate_metrics(results)

        return results

    def evaluate_with_params(
        self,
        objective_function: Callable[[Dict[str, Any]], Tuple[TradingPerformanceMetrics, float]],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        metrics, score = objective_function(params)
        return {
            "sharpe": metrics.sharpe_ratio,
            "total_return": metrics.total_return,
            "max_drawdown": metrics.max_drawdown,
            "win_rate": metrics.win_rate,
            "score": score
        }

    def _calculate_aggregate_metrics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        windows = results.get("windows", [])
        if not windows:
            return {}

        total_windows = len(windows)
        profitable_windows = sum(
            1 for w in windows if w.test_metrics.get("total_return", 0) > 0
        )

        sharpe_values = [w.test_metrics.get("sharpe", 0) for w in windows]
        return_values = [w.test_metrics.get("total_return", 0) for w in windows]
        max_dd_values = [w.test_metrics.get("max_drawdown", 0) for w in windows]
        win_rate_values = [w.test_metrics.get("win_rate", 0) for w in windows]

        avg_sharpe = sum(sharpe_values) / total_windows if total_windows > 0 else 0
        avg_return = sum(return_values) / total_windows if total_windows > 0 else 0
        avg_max_dd = sum(max_dd_values) / total_windows if total_windows > 0 else 0
        avg_win_rate = sum(win_rate_values) / total_windows if total_windows > 0 else 0

        return {
            "total_windows": total_windows,
            "profitable_windows": profitable_windows,
            "profitable_ratio": profitable_windows / total_windows if total_windows > 0 else 0,
            "avg_sharpe": avg_sharpe,
            "avg_total_return": avg_return,
            "avg_max_drawdown": avg_max_dd,
            "avg_win_rate": avg_win_rate,
            "min_sharpe": min(sharpe_values) if sharpe_values else 0,
            "max_sharpe": max(sharpe_values) if sharpe_values else 0,
            "min_return": min(return_values) if return_values else 0,
            "max_return": max(return_values) if return_values else 0,
            "sharpe_std": self._calculate_std(sharpe_values),
            "return_std": self._calculate_std(return_values),
        }

    def _calculate_std(self, values: List[float]) -> float:
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return variance ** 0.5

    def _check_overfitting(self, train_result: dict, walk_forward_result: dict = None) -> dict:
        warnings = []
        is_overfit = False

        train_sharpe = train_result.get('sharpe_ratio', 0)

        if train_sharpe > 3.0:
            warnings.append(f'训练集Sharpe={train_sharpe:.2f}异常高，可能过拟合')
            is_overfit = True

        train_bars = train_result.get('train_bars', 0)
        n_params = train_result.get('n_params', 0)
        if train_bars > 0 and n_params > 0 and train_bars / n_params < 30:
            warnings.append(f'数据点/参数比={train_bars/n_params:.1f}<30，过拟合风险高')
            is_overfit = True

        if walk_forward_result:
            oos_sharpe = walk_forward_result.get('aggregate_metrics', {}).get('sharpe_ratio', 0)
            if train_sharpe > 0 and oos_sharpe > 0:
                degradation = (train_sharpe - oos_sharpe) / train_sharpe
                if degradation > 0.5:
                    warnings.append(f'样本外Sharpe退化{degradation:.0%}，严重过拟合')
                    is_overfit = True
                elif degradation > 0.3:
                    warnings.append(f'样本外Sharpe退化{degradation:.0%}，可能存在过拟合')

        return {'is_overfit': is_overfit, 'warnings': warnings}



def create_objective_function(
    strategy_service,
    strategy_id: str,
    market_data,
    context,
    objective: OptimizationObjective = OptimizationObjective.MAXIMIZE_SHARPE
) -> Callable[[Dict[str, Any]], Tuple[TradingPerformanceMetrics, float]]:
    """创建目标函数"""
    
    def objective_function(params: Dict[str, Any]) -> Tuple[TradingPerformanceMetrics, float]:
        try:
            result = strategy_service.run_backtest_with_params(
                strategy_id, market_data, context, params
            )
            
            if result and result.get('status') == 'completed':
                metrics = result.get('metrics')
                if metrics is None:
                    return TradingPerformanceMetrics(0, 0, 0, 0, 0, 0, 0), float('-inf')
                
                if objective == OptimizationObjective.MAXIMIZE_SHARPE:
                    score = metrics.sharpe_ratio
                elif objective == OptimizationObjective.MAXIMIZE_RETURN:
                    score = metrics.total_return
                elif objective == OptimizationObjective.MINIMIZE_DRAWDOWN:
                    score = -metrics.max_drawdown
                elif objective == OptimizationObjective.MAXIMIZE_WIN_RATE:
                    score = metrics.win_rate
                else:
                    score = metrics.sharpe_ratio
                
                return metrics, score
            else:
                return TradingPerformanceMetrics(0, 0, 0, 0, 0, 0, 0), float('-inf')
                
        except Exception as e:
            logger.error(f"目标函数执行失败: {e}")
            return TradingPerformanceMetrics(0, 0, 0, 0, 0, 0, 0), float('-inf')
    
    return objective_function
