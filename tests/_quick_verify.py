import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

results = []

# Test 1: core.optimization imports
try:
    from core.optimization import BayesianOptimizer, ParameterSpec, OptParameterType, AcquisitionFunction
    results.append(("PASS", "core.optimization imports"))
except Exception as e:
    results.append(("FAIL", f"core.optimization imports: {e}"))

# Test 2: strategy_optimizer imports
try:
    from backtest.strategy_optimizer import StrategyParameterOptimizer, OptimizationConfig, OptimizationMethod
    results.append(("PASS", "strategy_optimizer imports"))
except Exception as e:
    results.append(("FAIL", f"strategy_optimizer imports: {e}"))

# Test 3: parameter_manager imports
try:
    from core.strategy.parameter_manager import StrategyParameterManager, ParameterRange
    results.append(("PASS", "parameter_manager imports"))
except Exception as e:
    results.append(("FAIL", f"parameter_manager imports: {e}"))

# Test 4: strategy_service imports
try:
    from core.services.strategy_service import StrategyService
    results.append(("PASS", "strategy_service imports"))
except Exception as e:
    results.append(("FAIL", f"strategy_service imports: {e}"))

# Test 5: BayesianOptimizer basic run (minimal)
try:
    from core.optimization import BayesianOptimizer, ParameterSpec, OptParameterType, AcquisitionFunction
    specs = [ParameterSpec("x", OptParameterType.CONTINUOUS, bounds=(0, 10))]
    opt = BayesianOptimizer(specs, acquisition=AcquisitionFunction.EI, random_state=42, verbose=False)
    def f(**kw): return -(kw["x"] - 5)**2 + 10
    result = opt.optimize(f, n_calls=10, maximize=True)
    results.append(("PASS", f"BayesianOptimizer basic: best_score={result.best_score:.2f}"))
except Exception as e:
    results.append(("FAIL", f"BayesianOptimizer basic: {e}"))

# Test 6: strategy_optimizer BAYESIAN
try:
    from backtest.strategy_optimizer import StrategyParameterOptimizer, OptimizationConfig, OptimizationMethod, OptimizationObjective

    class M: pass
    mm = M()
    mm.sharpe_ratio = 1.0; mm.total_return = 10.0; mm.max_drawdown = 5.0; mm.win_rate = 0.6

    def mf(params):
        p = params.get('period', 10)
        m = params.get('mode', 'fast')
        s = -abs(p - 20)*2 + (5 if m == 'slow' else 0)
        return mm, s

    opt = StrategyParameterOptimizer()
    cfg = OptimizationConfig(method=OptimizationMethod.BAYESIAN, objective=OptimizationObjective.MAXIMIZE_SHARPE, max_iterations=15, random_seed=42)
    run = opt.optimize(mf, {'period': [5,10,15,20,25], 'mode': ['fast','slow']}, cfg)
    assert run.status == 'completed' and len(run.results) > 0
    results.append(("PASS", f"strategy_optimizer BAYESIAN: {len(run.results)} results, best={run.best_result.score:.2f}"))
except Exception as e:
    results.append(("FAIL", f"strategy_optimizer BAYESIAN: {e}"))

# Test 7: parameter_manager BAYESIAN
try:
    from core.strategy.parameter_manager import StrategyParameterManager, ParameterRange
    mgr = StrategyParameterManager()
    pr = {'a': ParameterRange(5, 30), 'b': ParameterRange(20, 60)}
    class MS:
        def __init__(self):
            self._params = {}
        def set_parameter(self, name, value):
            self._params[name] = value
        def generate_signals(self, data):
            return self._params.copy()
    def fn(signals, data):
        a = signals.get('a', 10)
        b = signals.get('b', 30)
        return -abs(a - 10) - abs(b - 30) + 100
    result = mgr._bayesian_optimization(MS(), None, pr, fn, max_evaluations=15, parallel=False)
    assert result.total_evaluations > 0
    results.append(("PASS", f"parameter_manager BAYESIAN: {result.total_evaluations} evals, best={result.best_score:.2f}"))
except Exception as e:
    import traceback
    results.append(("FAIL", f"parameter_manager BAYESIAN: {e}\n{traceback.format_exc()}"))

# Test 8: No old GP code residuals
import subprocess
out = subprocess.check_output(
    ['python', '-c', 'import ast, sys; t=open(sys.argv[1]).read(); ast.parse(t); print("SYNTAX_OK")', 
     os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backtest', 'strategy_optimizer.py')],
    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), stderr=subprocess.STDOUT, text=True
)
results.append(("PASS", f"strategy_optimizer.py syntax check"))

# Test 9: OptParameterType vs ParameterType
try:
    from core.optimization import OptParameterType
    assert OptParameterType.CONTINUOUS.value == 'continuous'
    assert OptParameterType.DISCRETE.value == 'discrete'
    assert OptParameterType.ORDINAL.value == 'ordinal'
    results.append(("PASS", "OptParameterType enum values correct"))
except Exception as e:
    results.append(("FAIL", f"OptParameterType: {e}"))

# Test 10: ParameterSpec normalize/denormalize
try:
    from core.optimization import ParameterSpec, OptParameterType
    c = ParameterSpec("c", OptParameterType.CONTINUOUS, bounds=(0, 10))
    assert abs(c.normalize(5) - 0.5) < 0.01
    assert abs(c.denormalize(0.5) - 5) < 0.01
    d = ParameterSpec("d", OptParameterType.DISCRETE, bounds=(1, 10))
    assert d.denormalize(d.normalize(5)) == 5
    results.append(("PASS", "ParameterSpec roundtrip correct"))
except Exception as e:
    results.append(("FAIL", f"ParameterSpec: {e}"))

# Write results
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_test_results.txt'), 'w') as f:
    for status, msg in results:
        f.write(f"[{status}] {msg}\n")
    passed = sum(1 for s, _ in results if s == 'PASS')
    failed = sum(1 for s, _ in results if s == 'FAIL')
    f.write(f"\nTOTAL: {passed} PASS, {failed} FAIL\n")

print(f"Results written: {sum(1 for s,_ in results if s=='PASS')} PASS, {sum(1 for s,_ in results if s=='FAIL')} FAIL")