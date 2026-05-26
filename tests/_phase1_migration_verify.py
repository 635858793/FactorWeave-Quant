"""Phase1 迁移端到端功能验证"""
import numpy as np
from backtest.strategy_optimizer import (
    StrategyParameterOptimizer,
    OptimizationConfig,
    OptimizationMethod,
    OptimizationObjective,
    OptimizationResult,
)

class MockMetrics:
    def __init__(self, sharpe=1.0, total_return=10.0, max_drawdown=5.0, win_rate=0.6):
        self.sharpe_ratio = sharpe
        self.total_return = total_return
        self.max_drawdown = max_drawdown
        self.win_rate = win_rate

def mock_objective(params):
    """模拟目标函数：参数越接近目标值，分数越高"""
    period = params.get('period', 10)
    mode = params.get('mode', 'fast')
    base_score = -abs(period - 20) * 2
    if mode == 'slow':
        base_score += 5
    metrics = MockMetrics(sharpe=base_score / 10)
    return metrics, base_score

print("=" * 60)
print("Test 1: BAYESIAN mode with DISCRETE+ORDINAL params")
print("=" * 60)

optimizer = StrategyParameterOptimizer()
config = OptimizationConfig(
    method=OptimizationMethod.BAYESIAN,
    objective=OptimizationObjective.MAXIMIZE_SHARPE,
    max_iterations=20,
    random_seed=42,
)

param_grid = {
    'period': [5, 10, 15, 20, 25, 30, 40, 50],
    'mode': ['fast', 'slow'],
}

run = optimizer.optimize(mock_objective, param_grid, config)
print(f"Status: {run.status}")
print(f"Results count: {len(run.results)}")
print(f"Best result: {run.best_result}")
if run.best_result:
    print(f"  Best params: {run.best_result.parameters}")
    print(f"  Best score: {run.best_result.score:.4f}")
    print(f"  Best metrics.sharpe: {run.best_result.metrics.sharpe_ratio:.4f}")

assert run.status == "completed", f"Expected 'completed', got '{run.status}'"
assert len(run.results) > 0, "Expected at least 1 result"
assert run.best_result is not None, "Expected best_result"
assert isinstance(run.results[0], OptimizationResult), f"Wrong type: {type(run.results[0])}"
print("PASS: BAYESIAN mode works correctly\n")

print("=" * 60)
print("Test 2: MINIMIZE_DRAWDOWN mode")
print("=" * 60)
config2 = OptimizationConfig(
    method=OptimizationMethod.BAYESIAN,
    objective=OptimizationObjective.MINIMIZE_DRAWDOWN,
    max_iterations=15,
    random_seed=123,
)
run2 = optimizer.optimize(mock_objective, param_grid, config2)
print(f"Status: {run2.status}")
print(f"Results count: {len(run2.results)}")
if run2.best_result:
    print(f"  Best params: {run2.best_result.parameters}")
    print(f"  Best score: {run2.best_result.score:.4f}")
assert run2.status == "completed"
assert len(run2.results) > 0
print("PASS: MINIMIZE_DRAWDOWN mode works correctly\n")

print("=" * 60)
print("Test 3: GRID_SEARCH still works (non-Bayesian path)")
print("=" * 60)
config3 = OptimizationConfig(
    method=OptimizationMethod.GRID_SEARCH,
    max_iterations=100,
)
run3 = optimizer.optimize(mock_objective, param_grid, config3)
print(f"Status: {run3.status}")
print(f"Results count: {len(run3.results)}")
assert run3.status == "completed"
assert len(run3.results) > 0
print("PASS: GRID_SEARCH still works\n")

print("=" * 60)
print("Test 4: RANDOM_SEARCH still works (non-Bayesian path)")
print("=" * 60)
config4 = OptimizationConfig(
    method=OptimizationMethod.RANDOM_SEARCH,
    max_iterations=10,
    random_seed=42,
)
run4 = optimizer.optimize(mock_objective, param_grid, config4)
print(f"Status: {run4.status}")
print(f"Results count: {len(run4.results)}")
assert run4.status == "completed"
assert len(run4.results) > 0
print("PASS: RANDOM_SEARCH still works\n")

print("=" * 60)
print("Test 5: get_best_parameters / get_optimization_report")
print("=" * 60)
best = optimizer.get_best_parameters(n_top=3)
print(f"Top 3 params: {best}")
assert len(best) > 0
report = optimizer.get_optimization_report()
print(f"Report method: {report['method']}")
print(f"Report status: {report['status']}")
print("PASS: Report methods work correctly\n")

print("=" * 60)
print("ALL PHASE1 MIGRATION TESTS PASSED")
print("=" * 60)