"""贝叶斯优化统一模块 - 全面覆盖测试"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

PASS_COUNT = 0
FAIL_COUNT = 0

def test(name):
    def decorator(fn):
        def wrapper():
            global PASS_COUNT, FAIL_COUNT
            try:
                fn()
                PASS_COUNT += 1
                print(f"  PASS: {name}")
            except Exception as e:
                FAIL_COUNT += 1
                print(f"  FAIL: {name} -> {e}")
        return wrapper
    return decorator

# ======================================================================
# 模块1: BayesianOptimizer 基础功能测试
# ======================================================================
print("=" * 60)
print("Module 1: BayesianOptimizer 基础功能")
print("=" * 60)

@test("sklearn GP + EI + CONTINUOUS params")
def test_gp_ei_continuous():
    from core.optimization import BayesianOptimizer, ParameterSpec, OptParameterType, AcquisitionFunction

    specs = [
        ParameterSpec("x", OptParameterType.CONTINUOUS, bounds=(-5.0, 5.0)),
        ParameterSpec("y", OptParameterType.CONTINUOUS, bounds=(-5.0, 5.0)),
    ]
    opt = BayesianOptimizer(specs, acquisition=AcquisitionFunction.EI, random_state=42)

    def rosenbrock(**kwargs):
        x, y = kwargs["x"], kwargs["y"]
        return -((1 - x) ** 2 + 100 * (y - x ** 2) ** 2)

    result = opt.optimize(rosenbrock, n_calls=30, maximize=True)
    assert result.best_score is not None
    assert len(result.trials) >= 10
    assert abs(result.best_params["x"] - 1.0) < 2.0 or abs(result.best_params["y"] - 1.0) < 2.0

@test("sklearn GP + UCB + DISCRETE params")
def test_gp_ucb_discrete():
    from core.optimization import BayesianOptimizer, ParameterSpec, OptParameterType, AcquisitionFunction

    specs = [
        ParameterSpec("a", OptParameterType.DISCRETE, bounds=(1, 20)),
        ParameterSpec("b", OptParameterType.DISCRETE, bounds=(5, 50)),
    ]
    opt = BayesianOptimizer(specs, acquisition=AcquisitionFunction.UCB, kappa_ucb=2.576, random_state=42)

    def objective(**kwargs):
        a, b = kwargs["a"], kwargs["b"]
        return -abs(a - 10) - abs(b - 30) + 100

    result = opt.optimize(objective, n_calls=25, maximize=True)
    assert result.best_score > 80
    assert isinstance(result.best_params["a"], (int, np.integer))
    assert isinstance(result.best_params["b"], (int, np.integer))

@test("sklearn GP + PI + ORDINAL params")
def test_gp_pi_ordinal():
    from core.optimization import BayesianOptimizer, ParameterSpec, OptParameterType, AcquisitionFunction

    specs = [
        ParameterSpec("mode", OptParameterType.ORDINAL, values=["slow", "medium", "fast"]),
        ParameterSpec("type", OptParameterType.ORDINAL, values=["A", "B", "C"]),
    ]
    opt = BayesianOptimizer(specs, acquisition=AcquisitionFunction.PI, random_state=42)

    def objective(**kwargs):
        m, t = kwargs["mode"], kwargs["type"]
        score = 0
        if m == "fast":
            score += 50
        if t == "B":
            score += 50
        return score

    result = opt.optimize(objective, n_calls=15, maximize=True)
    assert result.best_score >= 50
    assert result.best_params["mode"] in ["slow", "medium", "fast"]
    assert result.best_params["type"] in ["A", "B", "C"]

@test("MIXED params (CONTINUOUS + DISCRETE + ORDINAL)")
def test_mixed_params():
    from core.optimization import BayesianOptimizer, ParameterSpec, OptParameterType, AcquisitionFunction

    specs = [
        ParameterSpec("lr", OptParameterType.CONTINUOUS, bounds=(0.001, 0.1)),
        ParameterSpec("depth", OptParameterType.DISCRETE, bounds=(3, 15)),
        ParameterSpec("act", OptParameterType.ORDINAL, values=["relu", "tanh", "sigmoid"]),
    ]
    opt = BayesianOptimizer(specs, acquisition=AcquisitionFunction.EI, random_state=42)

    def objective(**kwargs):
        lr, d, a = kwargs["lr"], kwargs["depth"], kwargs["act"]
        score = d * 2
        if a == "relu":
            score += 10
        return score - abs(lr - 0.01) * 200

    result = opt.optimize(objective, n_calls=20, maximize=True)
    assert result.best_score is not None
    assert 3 <= result.best_params["depth"] <= 15

@test("EARLY_STOPPING triggers correctly")
def test_early_stopping():
    from core.optimization import BayesianOptimizer, ParameterSpec, OptParameterType, AcquisitionFunction

    specs = [ParameterSpec("x", OptParameterType.CONTINUOUS, bounds=(0, 10))]
    opt = BayesianOptimizer(specs, acquisition=AcquisitionFunction.EI, random_state=42)

    def flat(**kwargs):
        return 1.0

    result = opt.optimize(flat, n_calls=50, maximize=True, early_stopping_rounds=5)
    assert len(result.trials) < 50

@test("Single param optimization works")
def test_single_param():
    from core.optimization import BayesianOptimizer, ParameterSpec, OptParameterType, AcquisitionFunction

    specs = [ParameterSpec("x", OptParameterType.DISCRETE, bounds=(1, 100))]
    opt = BayesianOptimizer(specs, acquisition=AcquisitionFunction.EI, random_state=42)

    def objective(**kwargs):
        x = kwargs["x"]
        return -abs(x - 77) + 100

    result = opt.optimize(objective, n_calls=20, maximize=True)
    assert result.best_score > 80
    assert abs(result.best_params["x"] - 77) < 30

@test("MINIMIZE mode (maximize=False)")
def test_minimize():
    from core.optimization import BayesianOptimizer, ParameterSpec, OptParameterType, AcquisitionFunction

    specs = [ParameterSpec("x", OptParameterType.CONTINUOUS, bounds=(-10, 10))]
    opt = BayesianOptimizer(specs, acquisition=AcquisitionFunction.EI, random_state=42)

    def objective(**kwargs):
        x = kwargs["x"]
        return x ** 2

    result = opt.optimize(objective, n_calls=25, maximize=False)
    assert result.best_score < 2.0

@test("ParameterSpec normalize/denormalize correctness")
def test_param_spec():
    from core.optimization import ParameterSpec, OptParameterType

    c = ParameterSpec("c", OptParameterType.CONTINUOUS, bounds=(0, 10))
    assert abs(c.normalize(5) - 0.5) < 0.01
    assert abs(c.denormalize(0.5) - 5) < 0.01

    d = ParameterSpec("d", OptParameterType.DISCRETE, bounds=(1, 10))
    n = d.normalize(5)
    assert d.denormalize(n) == 5

    o = ParameterSpec("o", OptParameterType.ORDINAL, values=["a", "b", "c"])
    assert o.denormalize(o.normalize("b")) == "b"

# ======================================================================
# 模块2: strategy_optimizer.py 迁移验证
# ======================================================================
print("=" * 60)
print("Module 2: strategy_optimizer.py 迁移验证")
print("=" * 60)

class MockMetrics2:
    def __init__(self, sharpe=1.0, total_return=10.0, max_drawdown=5.0, win_rate=0.6):
        self.sharpe_ratio = sharpe
        self.total_return = total_return
        self.max_drawdown = max_drawdown
        self.win_rate = win_rate

def mock_obj2(params):
    period = params.get('period', 10)
    mode = params.get('mode', 'fast')
    score = -abs(period - 20) * 2
    if mode == 'slow':
        score += 5
    return MockMetrics2(sharpe=score / 10), score

@test("strategy_optimizer BAYESIAN completes with Valid results")
def test_so_bayesian():
    from backtest.strategy_optimizer import (
        StrategyParameterOptimizer, OptimizationConfig,
        OptimizationMethod, OptimizationObjective,
    )
    optimizer = StrategyParameterOptimizer()
    config = OptimizationConfig(
        method=OptimizationMethod.BAYESIAN,
        objective=OptimizationObjective.MAXIMIZE_SHARPE,
        max_iterations=20,
        random_seed=42,
    )
    param_grid = {'period': [5, 10, 15, 20, 25, 30], 'mode': ['fast', 'slow']}
    run = optimizer.optimize(mock_obj2, param_grid, config)
    assert run.status == "completed"
    assert len(run.results) > 0
    assert run.best_result is not None

@test("strategy_optimizer GRID_SEARCH unaffected")
def test_so_grid():
    from backtest.strategy_optimizer import (
        StrategyParameterOptimizer, OptimizationConfig,
        OptimizationMethod,
    )
    optimizer = StrategyParameterOptimizer()
    config = OptimizationConfig(method=OptimizationMethod.GRID_SEARCH, max_iterations=100)
    param_grid = {'period': [10, 20, 30], 'mode': ['fast']}
    run = optimizer.optimize(mock_obj2, param_grid, config)
    assert run.status == "completed"
    assert len(run.results) == 3

@test("strategy_optimizer RANDOM_SEARCH unaffected")
def test_so_random():
    from backtest.strategy_optimizer import (
        StrategyParameterOptimizer, OptimizationConfig,
        OptimizationMethod,
    )
    optimizer = StrategyParameterOptimizer()
    config = OptimizationConfig(method=OptimizationMethod.RANDOM_SEARCH, max_iterations=5, random_seed=42)
    param_grid = {'period': [5, 10, 15, 20, 25]}
    run = optimizer.optimize(mock_obj2, param_grid, config)
    assert run.status == "completed"
    assert len(run.results) <= 5

@test("strategy_optimizer MINIMIZE_DRAWDOWN mode")
def test_so_minimize():
    from backtest.strategy_optimizer import (
        StrategyParameterOptimizer, OptimizationConfig,
        OptimizationMethod, OptimizationObjective,
    )
    optimizer = StrategyParameterOptimizer()
    config = OptimizationConfig(
        method=OptimizationMethod.BAYESIAN,
        objective=OptimizationObjective.MINIMIZE_DRAWDOWN,
        max_iterations=15, random_seed=42
    )
    param_grid = {'period': [10, 20, 30, 40]}
    run = optimizer.optimize(mock_obj2, param_grid, config)
    assert run.status == "completed"
    assert len(run.results) > 0

@test("strategy_optimizer: _param_grid_to_specs conversion")
def test_so_param_grid_to_specs():
    from backtest.strategy_optimizer import StrategyParameterOptimizer
    opt = StrategyParameterOptimizer()
    pg = {'period': [5, 10, 15], 'mode': ['fast', 'slow'], 'factor': {'start': 0.5, 'end': 2.0, 'step': 0.5}}
    specs = opt._param_grid_to_specs(pg)
    assert len(specs) == 3
    from core.optimization import OptParameterType
    assert specs[0].type == OptParameterType.DISCRETE
    assert specs[1].type == OptParameterType.ORDINAL

# ======================================================================
# 模块3: parameter_manager.py 迁移验证
# ======================================================================
print("=" * 60)
print("Module 3: parameter_manager.py 迁移验证")
print("=" * 60)

@test("parameter_manager imports compile correctly")
def test_pm_import():
    from core.strategy.parameter_manager import (
        StrategyParameterManager, ParameterRange,
        ParameterOptimizationMethod, ParameterOptimizationResult
    )
    assert StrategyParameterManager is not None

@test("parameter_manager BAYESIAN optimization basic")
def test_pm_bayesian():
    from core.strategy.parameter_manager import (
        StrategyParameterManager, ParameterRange,
        ParameterOptimizationMethod
    )
    mgr = StrategyParameterManager()
    param_ranges = {
        'fast_period': ParameterRange(min_value=5, max_value=30),
        'slow_period': ParameterRange(min_value=20, max_value=60),
    }

    class MockStrategy:
        pass

    def objective_fn(strategy, data, params):
        fast = params.get('fast_period', 10)
        slow = params.get('slow_period', 30)
        return -abs(fast - 10) - abs(slow - 30) + 100

    result = mgr._bayesian_optimization(
        MockStrategy(), None, param_ranges, objective_fn, max_evaluations=20, parallel=False
    )
    assert result.best_score is not None
    assert result.total_evaluations > 0
    assert len(result.optimization_history) > 0

@test("parameter_manager empty param_ranges")
def test_pm_empty():
    from core.strategy.parameter_manager import (
        StrategyParameterManager, ParameterOptimizationResult
    )
    mgr = StrategyParameterManager()

    class MockStrategy:
        pass

    result = mgr._bayesian_optimization(
        MockStrategy(), None, {}, lambda s, d, p: 0, max_evaluations=10, parallel=False
    )
    assert result.best_parameters == {}
    assert result.total_evaluations == 0

@test("parameter_manager with ORDINAL values")
def test_pm_ordinal():
    from core.strategy.parameter_manager import (
        StrategyParameterManager, ParameterRange
    )
    mgr = StrategyParameterManager()
    param_ranges = {
        'mode': ParameterRange(min_value=0, max_value=1, values=['aggressive', 'conservative']),
    }

    class MockStrategy:
        pass

    def objective_fn(strategy, data, params):
        mode = params.get('mode', 'conservative')
        return 100 if mode == 'aggressive' else 50

    result = mgr._bayesian_optimization(
        MockStrategy(), None, param_ranges, objective_fn, max_evaluations=15, parallel=False
    )
    assert result.best_score > 0
    assert result.best_parameters['mode'] in ['aggressive', 'conservative']

@test("parameter_manager GP_RESET recovery")
def test_pm_gp_reset():
    from core.strategy.parameter_manager import (
        StrategyParameterManager, ParameterRange
    )
    mgr = StrategyParameterManager()
    param_ranges = {
        'x': ParameterRange(min_value=0.0, max_value=10.0),
        'y': ParameterRange(min_value=0.0, max_value=10.0),
    }

    class MockStrategy:
        pass

    def objective_fn(strategy, data, params):
        x, y = params.get('x', 0), params.get('y', 0)
        return 100 - (x - 5) ** 2 - (y - 5) ** 2

    result = mgr._bayesian_optimization(
        MockStrategy(), None, param_ranges, objective_fn, max_evaluations=30, parallel=False
    )
    assert result.best_score > 80

# ======================================================================
# 模块4: strategy_service.py 迁移验证（导入与编译级别）
# ======================================================================
print("=" * 60)
print("Module 4: strategy_service.py 迁移验证")
print("=" * 60)

@test("strategy_service module imports correctly")
def test_ss_import():
    from core.services.strategy_service import StrategyService
    assert StrategyService is not None

@test("strategy_service _bayesian_optimization exists")
def test_ss_method():
    from core.services.strategy_service import StrategyService
    assert hasattr(StrategyService, '_bayesian_optimization')

@test("strategy_service legacy helpers still present")
def test_ss_legacy_helpers():
    from core.services.strategy_service import StrategyService
    assert hasattr(StrategyService, '_normalize_params')
    assert hasattr(StrategyService, '_denormalize_params')
    assert hasattr(StrategyService, '_generate_random_parameters')

# ======================================================================
# 模块5: 交叉模块一致性
# ======================================================================
print("=" * 60)
print("Module 5: 交叉模块一致性")
print("=" * 60)

@test("All modules import from same core.optimization")
def test_cross_import_uniformity():
    from core.optimization import (
        BayesianOptimizer, ParameterSpec, OptParameterType,
        AcquisitionFunction, OptimizationResult
    )
    assert BayesianOptimizer is not None
    assert OptParameterType.CONTINUOUS.value == "continuous"
    assert AcquisitionFunction.EI.value == "ei"
    assert AcquisitionFunction.UCB.value == "ucb"
    assert AcquisitionFunction.PI.value == "pi"

@test("OptParameterType distinct from indicator_extensions.ParameterType")
def test_opt_param_type_distinct():
    from core.optimization import OptParameterType
    try:
        from core.indicator_extensions import ParameterType as IndParamType
        assert OptParameterType.__name__ != IndParamType.__name__
        assert OptParameterType.CONTINUOUS.value != getattr(IndParamType, 'INTEGER', None)
    except ImportError:
        pass

# ======================================================================
# 总结
# ======================================================================
print("=" * 60)
print(f"RESULTS: {PASS_COUNT} passed, {FAIL_COUNT} failed, {PASS_COUNT + FAIL_COUNT} total")
print("=" * 60)

if FAIL_COUNT > 0:
    sys.exit(1)
else:
    print("ALL COMPREHENSIVE TESTS PASSED!")