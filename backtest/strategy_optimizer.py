from loguru import logger
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from itertools import product
import random
import math

from core.strategy_extensions import PerformanceMetrics


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
    metrics: PerformanceMetrics
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
        objective_function: Callable[[Dict[str, Any]], Tuple[PerformanceMetrics, float]],
        param_grid: Dict[str, Any],
        config: Optional[OptimizationConfig] = None
    ) -> OptimizationRun:
        """
        执行参数优化
        
        Args:
            objective_function: 目标函数，输入参数，返回(性能指标, 得分)
            param_grid: 参数网格
            config: 优化配置
            
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
                run.best_result = min(results, key=lambda x: x.score)
            
            self.logger.info(f"优化完成: {len(results)} 个组合, 最佳得分: {run.best_result.score if run.best_result else 'N/A'}")
            
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
    
    def _bayesian_optimization(
        self,
        objective_function: Callable,
        param_grid: Dict[str, Any],
        config: OptimizationConfig,
        run: OptimizationRun
    ) -> List[OptimizationResult]:
        """贝叶斯优化（简化版）"""
        param_combinations = ParameterGrid(param_grid).generate()
        
        if len(param_combinations) > config.max_iterations:
            param_combinations = random.sample(
                param_combinations,
                config.max_iterations
            )
        
        run.total_iterations = len(param_combinations)
        results = []
        best_score = float('-inf')
        no_improvement_count = 0
        
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
                
                if score > best_score:
                    best_score = score
                    no_improvement_count = 0
                else:
                    no_improvement_count += 1
                
                if no_improvement_count >= run.config.early_stopping_rounds:
                    self.logger.info(f"早停: 连续 {no_improvement_count} 次无改进")
                    break
                
                if run.config.verbose:
                    self.logger.info(f"贝叶斯优化 [{i+1}/{len(param_combinations)}]: score={score:.4f}")
                    
            except Exception as e:
                self.logger.warning(f"参数组合 {params} 执行失败: {e}")
        
        return results
    
    def get_best_parameters(self, n_top: int = 5) -> List[Dict[str, Any]]:
        """获取最佳参数组合"""
        if not self._current_run or not self._current_run.results:
            return []
        
        sorted_results = sorted(
            self._current_run.results,
            key=lambda x: x.score
        )[:n_top]
        
        return [r.parameters for r in sorted_results]
    
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


def create_objective_function(
    strategy_service,
    strategy_id: str,
    market_data,
    context,
    objective: OptimizationObjective = OptimizationObjective.MAXIMIZE_SHARPE
) -> Callable[[Dict[str, Any]], Tuple[PerformanceMetrics, float]]:
    """创建目标函数"""
    
    def objective_function(params: Dict[str, Any]) -> Tuple[PerformanceMetrics, float]:
        try:
            result = strategy_service.run_backtest_with_params(
                strategy_id, market_data, context, params
            )
            
            if result and result.get('status') == 'completed':
                metrics = result.get('metrics', PerformanceMetrics(
                    total_return=0, sharpe_ratio=0, max_drawdown=0,
                    win_rate=0, total_trades=0, profitable_trades=0, losing_trades=0
                ))
                
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
                return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0), float('-inf')
                
        except Exception as e:
            logger.error(f"目标函数执行失败: {e}")
            return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0), float('-inf')
    
    return objective_function
