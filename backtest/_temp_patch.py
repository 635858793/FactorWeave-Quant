import os

filepath = r'D:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\backtest\strategy_optimizer.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Insert 1: WalkForwardWindow dataclass before 'class ParameterGrid:'
# Find the line index
param_grid_idx = None
for i, line in enumerate(lines):
    if line.startswith('class ParameterGrid:'):
        param_grid_idx = i
        break

walkforward_code = '''
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

'''

# Insert 2: New methods at the end of class StrategyParameterOptimizer
# Find the end of get_optimization_report (return report)
report_idx = None
for i, line in enumerate(lines):
    if line.rstrip() == '        return report':
        report_idx = i
        break

new_methods_code = '''
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

'''

# Apply inserts (in reverse order to preserve indices)
new_lines = lines[:report_idx + 1] + [new_methods_code] + lines[report_idx + 1:]
new_lines = new_lines[:param_grid_idx] + [walkforward_code] + new_lines[param_grid_idx:]

# Flatten
result_lines = []
for item in new_lines:
    if isinstance(item, str):
        if '\n' in item and item != '\n':
            for sub in item.splitlines(True):
                result_lines.append(sub)
        else:
            result_lines.append(item)
    else:
        result_lines.append(str(item))

# Write to temp file first, then replace
temp_path = filepath + '.tmp'
with open(temp_path, 'w', encoding='utf-8') as f:
    f.writelines(result_lines)

os.replace(temp_path, filepath)

print(f'Original: {len(lines)} lines')
print(f'New: {len(result_lines)} lines')
print('Done!')