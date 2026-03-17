from loguru import logger
"""
专业级回测性能优化器模块
提供向量化计算、并行处理、内存优化等高性能回测功能
对标行业专业软件标准
"""

import numpy as np
import pandas as pd
import numba
from numba import jit, prange, njit
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import multiprocessing
from functools import wraps
import psutil
import gc
import warnings
from dataclasses import dataclass
from enum import Enum
from core.performance_optimizer import ProfessionalPerformanceOptimizer, OptimizationLevel

class BacktestOptimizationLevel(Enum):
    """回测优化级别枚举"""
    BASIC = "basic"              # 基础优化
    STANDARD = "standard"        # 标准优化
    AGGRESSIVE = "aggressive"    # 激进优化
    PROFESSIONAL = "professional"  # 专业级优化

@dataclass
class BacktestPerformanceMetrics:
    """回测性能指标数据类"""
    execution_time: float
    memory_usage: float
    cpu_usage: float
    vectorization_ratio: float
    parallel_efficiency: float
    optimization_level: BacktestOptimizationLevel
    timestamp: datetime

class VectorizedBacktestEngine:
    """
    向量化回测引擎
    使用NumPy向量化操作和Numba JIT编译提升性能
    """

    def __init__(self, optimization_level: BacktestOptimizationLevel = BacktestOptimizationLevel.PROFESSIONAL):
        self.optimization_level = optimization_level
        self.logger = logger

    @staticmethod
    @jit(nopython=True, parallel=True, cache=True, fastmath=True)  # 启用并行、缓存和快速数学
    def _vectorized_backtest_core(prices: np.ndarray, signals: np.ndarray,
                                  initial_capital: float, position_size: float,
                                  commission_pct: float, slippage_pct: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        向量化回测核心计算（Numba JIT编译）

        Args:
            prices: 价格数组
            signals: 信号数组
            initial_capital: 初始资金
            position_size: 仓位大小
            commission_pct: 手续费比例
            slippage_pct: 滑点比例

        Returns:
            Tuple: (持仓数组, 资金数组, 收益数组)
        """
        n = len(prices)
        positions = np.zeros(n)
        capital = np.zeros(n)
        returns = np.zeros(n)

        capital[0] = initial_capital
        current_position = 0.0
        current_capital = initial_capital

        for i in range(1, n):  # 修复：使用range而不是prange
            signal = signals[i]
            price = prices[i]

            # 处理交易信号（简化逻辑）
            if signal == 1 and current_position == 0:  # 买入信号且无持仓
                # 计算交易成本
                trade_cost = price * (commission_pct + slippage_pct)
                shares = (current_capital * position_size) / (price + trade_cost)
                current_position = shares
                current_capital -= shares * (price + trade_cost)
            elif signal == -1 and current_position > 0:  # 卖出信号且有持仓
                # 计算交易成本
                trade_cost = price * (commission_pct + slippage_pct)
                current_capital += current_position * (price - trade_cost)
                current_position = 0

            positions[i] = current_position

            # 计算当前权益
            if current_position > 0:
                equity = current_capital + current_position * price
            elif current_position < 0:
                equity = current_capital - current_position * price
            else:
                equity = current_capital

            capital[i] = equity

            # 计算收益率
            if i > 0 and capital[i-1] != 0:
                returns[i] = (capital[i] - capital[i-1]) / capital[i-1]

        return positions, capital, returns

    @staticmethod
    @njit(cache=True, fastmath=True)
    def _vectorized_backtest_with_risk(
        prices: np.ndarray, signals: np.ndarray,
        initial_capital: float, position_size: float,
        commission_pct: float, slippage_pct: float,
        stop_loss_pct: float, take_profit_pct: float,
        max_holding_periods: int
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        向量化回测核心计算（支持止损/止盈/持有期）- JIT编译

        Args:
            prices: 价格数组
            signals: 信号数组
            initial_capital: 初始资金
            position_size: 仓位大小
            commission_pct: 手续费比例
            slippage_pct: 滑点比例
            stop_loss_pct: 止损比例 (-1表示不启用)
            take_profit_pct: 止盈比例 (-1表示不启用)
            max_holding_periods: 最大持有期 (-1表示不启用)

        Returns:
            Tuple: (持仓数组, 资金数组, 收益数组, 退出原因数组, 持有期数组)
        """
        n = len(prices)
        positions = np.zeros(n)
        capital = np.zeros(n)
        returns = np.zeros(n)
        exit_reasons = np.zeros(n)
        holding_periods = np.zeros(n, dtype=np.int64)

        capital[0] = initial_capital
        current_position = 0.0
        current_capital = initial_capital
        entry_price = 0.0
        holding_days = 0

        use_stop_loss = stop_loss_pct >= 0
        use_take_profit = take_profit_pct >= 0
        use_max_holding = max_holding_periods >= 0

        for i in range(1, n):
            price = prices[i]
            signal = signals[i]
            exit_reason = 0

            if current_position != 0:
                holding_days += 1
                holding_periods[i] = holding_days
            else:
                holding_days = 0
                holding_periods[i] = 0

            if current_position > 0:
                if use_stop_loss and price <= entry_price * (1 - stop_loss_pct):
                    exit_reason = 1
                    current_capital += current_position * price * (1 - commission_pct - slippage_pct)
                    current_position = 0
                elif use_take_profit and price >= entry_price * (1 + take_profit_pct):
                    exit_reason = 2
                    current_capital += current_position * price * (1 - commission_pct - slippage_pct)
                    current_position = 0
                elif use_max_holding and holding_days >= max_holding_periods:
                    exit_reason = 3
                    current_capital += current_position * price * (1 - commission_pct - slippage_pct)
                    current_position = 0
            elif current_position < 0:
                if use_stop_loss and price >= entry_price * (1 + stop_loss_pct):
                    exit_reason = 1
                    current_capital += abs(current_position) * price * (1 - commission_pct - slippage_pct)
                    current_position = 0
                elif use_take_profit and price <= entry_price * (1 - take_profit_pct):
                    exit_reason = 2
                    current_capital += abs(current_position) * price * (1 - commission_pct - slippage_pct)
                    current_position = 0
                elif use_max_holding and holding_days >= max_holding_periods:
                    exit_reason = 3
                    current_capital += abs(current_position) * price * (1 - commission_pct - slippage_pct)
                    current_position = 0

            # 如果没有退出，检查交易信号
            if current_position == 0:
                if signal == 1:
                    trade_cost = price * (commission_pct + slippage_pct)
                    shares = (current_capital * position_size) / (price + trade_cost)
                    current_position = shares
                    current_capital -= shares * (price + trade_cost)
                    entry_price = price + trade_cost
                    holding_days = 0
                elif signal == -1:
                    trade_cost = price * (commission_pct + slippage_pct)
                    shares = (current_capital * position_size) / (price + trade_cost)
                    current_position = -shares
                    current_capital -= shares * (price + trade_cost)
                    entry_price = price + trade_cost
                    holding_days = 0

            positions[i] = current_position

            # 计算当前权益
            if current_position > 0:
                equity = current_capital + current_position * price
            elif current_position < 0:
                equity = current_capital - current_position * price
            else:
                equity = current_capital

            capital[i] = equity
            exit_reasons[i] = exit_reason

            # 计算收益率
            if i > 0 and capital[i-1] != 0:
                returns[i] = (capital[i] - capital[i-1]) / capital[i-1]

        return positions, capital, returns, exit_reasons, holding_periods

    def run_vectorized_backtest_with_risk(
        self, data: pd.DataFrame, signal_col: str = 'signal',
        price_col: str = 'close', initial_capital: float = 100000,
        position_size: float = 1.0, commission_pct: float = 0.001,
        slippage_pct: float = 0.001, stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        max_holding_periods: Optional[int] = None
    ) -> pd.DataFrame:
        """
        运行支持止损/止盈/持有期的向量化回测

        Args:
            data: 回测数据
            signal_col: 信号列名
            price_col: 价格列名
            initial_capital: 初始资金
            position_size: 仓位大小
            commission_pct: 手续费比例
            slippage_pct: 滑点比例
            stop_loss_pct: 止损比例
            take_profit_pct: 止盈比例
            max_holding_periods: 最大持有期

        Returns:
            pd.DataFrame: 回测结果
        """
        try:
            prices = data[price_col].astype(float).values
            signals = data[signal_col].astype(float).values

            if np.any(np.isnan(prices)) or np.any(np.isinf(prices)):
                raise ValueError("价格数据包含NaN或无穷大值")
            if np.any(np.isnan(signals)) or np.any(np.isinf(signals)):
                raise ValueError("信号数据包含NaN或无穷大值")

            sl_pct = -1.0 if stop_loss_pct is None else float(stop_loss_pct)
            tp_pct = -1.0 if take_profit_pct is None else float(take_profit_pct)
            max_hp = -1 if max_holding_periods is None else int(max_holding_periods)

            positions, capital, returns, exit_reasons, holding_periods = self._vectorized_backtest_with_risk(
                prices, signals, initial_capital, position_size,
                commission_pct, slippage_pct, sl_pct, tp_pct, max_hp
            )

            result = data.copy()
            result['position'] = positions
            result['capital'] = capital
            result['returns'] = returns
            result['exit_reason'] = exit_reasons
            result['holding_periods'] = holding_periods
            result['cumulative_returns'] = (1 + pd.Series(returns)).cumprod() - 1

            return result

        except Exception as e:
            self.logger.error(f"带风控的向量化回测失败: {e}")
            raise

    def run_vectorized_backtest(self, data: pd.DataFrame, signal_col: str = 'signal',
                                price_col: str = 'close', initial_capital: float = 100000,
                                position_size: float = 1.0, commission_pct: float = 0.001,
                                slippage_pct: float = 0.001) -> pd.DataFrame:
        """
        运行向量化回测

        Args:
            data: 回测数据
            signal_col: 信号列名
            price_col: 价格列名
            initial_capital: 初始资金
            position_size: 仓位大小
            commission_pct: 手续费比例
            slippage_pct: 滑点比例

        Returns:
            pd.DataFrame: 回测结果
        """
        try:
            # 提取数据为NumPy数组，确保数据类型正确
            prices = data[price_col].astype(float).values
            signals = data[signal_col].astype(float).values

            # 检查数据有效性
            if np.any(np.isnan(prices)) or np.any(np.isinf(prices)):
                raise ValueError("价格数据包含NaN或无穷大值")
            if np.any(np.isnan(signals)) or np.any(np.isinf(signals)):
                raise ValueError("信号数据包含NaN或无穷大值")

            # 运行向量化回测
            # 使用优化的JIT函数
            from .jit_optimizer import jit_optimizer, optimized_backtest_core

            # 尝试使用预编译函数，如果失败则使用原始函数
            try:
                jit_func = jit_optimizer.get_function('backtest_core')
                if jit_func:
                    positions, capital, returns = jit_func(
                        prices, signals, initial_capital, position_size,
                        commission_pct, slippage_pct
                    )
                else:
                    positions, capital, returns = optimized_backtest_core(
                        prices, signals, initial_capital, position_size,
                        commission_pct, slippage_pct
                    )
            except Exception as jit_error:
                self.logger.warning(f"JIT优化函数失败，使用原始函数: {jit_error}")
                positions, capital, returns = self._vectorized_backtest_core(
                    prices, signals, initial_capital, position_size, commission_pct, slippage_pct
                )

            # 构建结果DataFrame
            result = data.copy()
            result['position'] = positions
            result['capital'] = capital
            result['returns'] = returns
            result['cumulative_returns'] = (
                1 + pd.Series(returns)).cumprod() - 1

            return result

        except Exception as e:
            self.logger.error(f"向量化回测失败: {e}")
            raise

class ParallelBacktestEngine:
    """
    并行回测引擎
    支持多策略、多参数、多股票的并行回测
    """

    def __init__(self, max_workers: Optional[int] = None,
                 optimization_level: BacktestOptimizationLevel = BacktestOptimizationLevel.PROFESSIONAL):
        self.max_workers = max_workers or min(
            32, (multiprocessing.cpu_count() or 1) + 4)
        self.optimization_level = optimization_level
        self.logger = logger
        self.vectorized_engine = VectorizedBacktestEngine(optimization_level)

    def run_parallel_backtest(self, data_dict: Dict[str, pd.DataFrame],
                              strategy_func: Callable, param_combinations: List[Dict],
                              use_processes: bool = False) -> Dict[str, Any]:
        """
        运行并行回测

        Args:
            data_dict: {股票代码: 数据} 字典
            strategy_func: 策略函数
            param_combinations: 参数组合列表
            use_processes: 是否使用多进程

        Returns:
            Dict: 回测结果字典
        """
        try:
            self.logger.info(
                f"开始并行回测 - 股票数: {len(data_dict)}, 参数组合数: {len(param_combinations)}")

            # 生成任务列表
            tasks = []
            for stock_code, data in data_dict.items():
                for params in param_combinations:
                    tasks.append((stock_code, data, strategy_func, params))

            # 选择执行器
            executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor

            results = {}
            with executor_class(max_workers=self.max_workers) as executor:
                # 提交任务
                future_to_task = {
                    executor.submit(self._run_single_backtest, task): task
                    for task in tasks
                }

                # 收集结果
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    stock_code, _, _, params = task

                    try:
                        result = future.result()
                        key = f"{stock_code}_{hash(str(params))}"
                        results[key] = {
                            'stock_code': stock_code,
                            'params': params,
                            'result': result
                        }
                    except Exception as e:
                        self.logger.error(f"回测任务失败 {stock_code}: {e}")

            self.logger.info(f"并行回测完成 - 成功任务数: {len(results)}")
            return results

        except Exception as e:
            self.logger.error(f"并行回测失败: {e}")
            raise

    def _run_single_backtest(self, task: Tuple) -> pd.DataFrame:
        """运行单个回测任务"""
        stock_code, data, strategy_func, params = task

        try:
            # 应用策略生成信号
            data_with_signals = strategy_func(data, **params)

            # 运行向量化回测
            result = self.vectorized_engine.run_vectorized_backtest(
                data_with_signals, **params.get('backtest_params', {})
            )

            return result

        except Exception as e:
            self.logger.error(f"单个回测任务失败 {stock_code}: {e}")
            raise

    def optimize_strategy_parameters(self, data: pd.DataFrame, strategy_func: Callable,
                                     param_grid: Dict[str, List], optimization_metric: str = 'sharpe_ratio',
                                     cv_folds: int = 5) -> Dict[str, Any]:
        """
        策略参数优化

        Args:
            data: 回测数据
            strategy_func: 策略函数
            param_grid: 参数网格
            optimization_metric: 优化指标
            cv_folds: 交叉验证折数

        Returns:
            Dict: 优化结果
        """
        try:
            from itertools import product

            # 生成参数组合
            param_names = list(param_grid.keys())
            param_values = list(param_grid.values())
            param_combinations = [
                dict(zip(param_names, combo))
                for combo in product(*param_values)
            ]

            self.logger.info(f"开始参数优化 - 参数组合数: {len(param_combinations)}")

            # 时间序列交叉验证
            fold_size = len(data) // cv_folds
            optimization_results = []

            for params in param_combinations:
                fold_scores = []

                for fold in range(cv_folds):
                    # 划分训练和测试集
                    start_idx = fold * fold_size
                    end_idx = start_idx + fold_size * 2  # 使用两个fold的数据

                    if end_idx > len(data):
                        break

                    fold_data = data.iloc[start_idx:end_idx]

                    try:
                        # 运行回测
                        data_with_signals = strategy_func(fold_data, **params)
                        result = self.vectorized_engine.run_vectorized_backtest(
                            data_with_signals)

                        # 计算评估指标
                        score = self._calculate_optimization_metric(
                            result, optimization_metric)
                        fold_scores.append(score)

                    except Exception as e:
                        self.logger.warning(
                            f"参数组合 {params} 在fold {fold} 失败: {e}")
                        continue

                if fold_scores:
                    avg_score = np.mean(fold_scores)
                    std_score = np.std(fold_scores)

                    optimization_results.append({
                        'params': params,
                        'score': avg_score,
                        'score_std': std_score,
                        'fold_scores': fold_scores
                    })

            # 排序并返回最佳参数
            optimization_results.sort(key=lambda x: x['score'], reverse=True)

            best_result = optimization_results[0] if optimization_results else None

            return {
                'best_params': best_result['params'] if best_result else None,
                'best_score': best_result['score'] if best_result else None,
                'all_results': optimization_results,
                'optimization_metric': optimization_metric
            }

        except Exception as e:
            self.logger.error(f"参数优化失败: {e}")
            raise

    def _calculate_optimization_metric(self, result: pd.DataFrame, metric: str) -> float:
        """计算优化指标"""
        try:
            if 'returns' not in result.columns:
                return 0.0

            returns = result['returns'].dropna()

            if len(returns) == 0:
                return 0.0

            if metric == 'sharpe_ratio':
                return returns.mean() / returns.std() * np.sqrt(252) if returns.std() != 0 else 0.0
            elif metric == 'total_return':
                return (1 + returns).prod() - 1
            elif metric == 'max_drawdown':
                cumulative = (1 + returns).cumprod()
                running_max = cumulative.cummax()
                drawdown = (cumulative - running_max) / running_max
                return -drawdown.min()  # 返回负值，因为我们要最大化
            elif metric == 'calmar_ratio':
                total_return = (1 + returns).prod() - 1
                cumulative = (1 + returns).cumprod()
                running_max = cumulative.cummax()
                drawdown = (cumulative - running_max) / running_max
                max_drawdown = abs(drawdown.min())
                return total_return / max_drawdown if max_drawdown != 0 else 0.0
            else:
                return 0.0

        except Exception as e:
            self.logger.error(f"计算优化指标失败: {e}")
            return 0.0

class MemoryOptimizedBacktestEngine:
    """
    内存优化回测引擎
    针对大数据集和长时间序列的内存优化
    """

    def __init__(self, chunk_size: int = 10000,
                 optimization_level: BacktestOptimizationLevel = BacktestOptimizationLevel.PROFESSIONAL):
        self.chunk_size = chunk_size
        self.optimization_level = optimization_level
        self.logger = logger

    def run_chunked_backtest(self, data: pd.DataFrame, strategy_func: Callable,
                             **kwargs) -> pd.DataFrame:
        """
        分块运行回测，适用于大数据集

        Args:
            data: 回测数据
            strategy_func: 策略函数
            **kwargs: 其他参数

        Returns:
            pd.DataFrame: 回测结果
        """
        # 导入资源管理器
        from .resource_manager import managed_backtest_resources, global_data_manager

        with managed_backtest_resources() as resource_manager:
            try:
                self.logger.info(
                    f"开始分块回测 - 数据长度: {len(data)}, 块大小: {self.chunk_size}")

                # 初始化结果列表
                result_chunks = []

                # 分块处理
                for i in range(0, len(data), self.chunk_size):
                    chunk_end = min(i + self.chunk_size, len(data))

                    # 使用智能数据复制策略
                    chunk_data = global_data_manager.get_data_copy(
                        data.iloc[i:chunk_end], copy_strategy='smart'
                    )

                    # 应用策略
                    chunk_with_signals = strategy_func(chunk_data, **kwargs)

                    # 运行回测
                    vectorized_engine = VectorizedBacktestEngine(
                        self.optimization_level)

                    # 注册引擎到资源管理器
                    resource_manager.register_resource(
                        vectorized_engine,
                        cleanup_func=lambda x: setattr(x, '_cleanup_flag', True)
                    )

                    chunk_result = vectorized_engine.run_vectorized_backtest(
                        chunk_with_signals)

                    result_chunks.append(chunk_result)

                    # 显式清理变量（资源管理器会确保彻底清理）
                    del chunk_data, chunk_with_signals, vectorized_engine

                    # 每处理10个块进行一次内存检查
                    if (i // self.chunk_size) % 10 == 0:
                        memory_info = resource_manager.get_memory_usage()
                        if memory_info['percentage'] > 85:  # 内存使用超过85%
                            self.logger.warning(f"内存使用率过高: {memory_info['percentage']:.1f}%")
                            # 强制垃圾回收
                            import gc
                            gc.collect()

                # 合并结果
                final_result = pd.concat(result_chunks, ignore_index=True)

                # 重新计算累积指标
                final_result = self._recalculate_cumulative_metrics(final_result)

                self.logger.info("分块回测完成")
                return final_result

            except Exception as e:
                self.logger.error(f"分块回测失败: {e}")
                raise

    def _recalculate_cumulative_metrics(self, result: pd.DataFrame) -> pd.DataFrame:
        """重新计算累积指标"""
        try:
            if 'returns' in result.columns:
                result['cumulative_returns'] = (
                    1 + result['returns']).cumprod() - 1

            if 'capital' in result.columns:
                # 确保资金连续性
                for i in range(1, len(result)):
                    if pd.isna(result.loc[i, 'capital']) or result.loc[i, 'capital'] == 0:
                        result.loc[i, 'capital'] = result.loc[i-1, 'capital']

            return result

        except Exception as e:
            self.logger.error(f"重新计算累积指标失败: {e}")
            return result

class ProfessionalBacktestOptimizer:
    """
    专业级回测优化器
    整合向量化、并行处理、内存优化等功能
    """

    def __init__(self, optimization_level: BacktestOptimizationLevel = BacktestOptimizationLevel.PROFESSIONAL):
        self.optimization_level = optimization_level
        # 纯Loguru架构，移除log_manager依赖

        # 初始化各个引擎
        self.vectorized_engine = VectorizedBacktestEngine(optimization_level)
        self.parallel_engine = ParallelBacktestEngine(
            optimization_level=optimization_level)
        self.memory_engine = MemoryOptimizedBacktestEngine(
            optimization_level=optimization_level)

        # 性能监控
        self.performance_optimizer = ProfessionalPerformanceOptimizer(
            OptimizationLevel.PROFESSIONAL
        )

    def optimize_backtest_execution(self, data: pd.DataFrame, strategy_func: Callable,
                                    auto_select_engine: bool = True, **kwargs) -> Tuple[pd.DataFrame, BacktestPerformanceMetrics]:
        """
        优化回测执行

        Args:
            data: 回测数据
            strategy_func: 策略函数
            auto_select_engine: 是否自动选择引擎
            **kwargs: 其他参数

        Returns:
            Tuple: (回测结果, 性能指标)
        """
        try:
            self.performance_optimizer.start_monitoring()

            # 自动选择最优引擎
            if auto_select_engine:
                engine = self._select_optimal_engine(data)
            else:
                engine = self.vectorized_engine

            logger.info(
                f"使用引擎: {type(engine).__name__}")

            # 执行回测
            if isinstance(engine, VectorizedBacktestEngine):
                data_with_signals = strategy_func(data, **kwargs)
                result = engine.run_vectorized_backtest(data_with_signals)
            elif isinstance(engine, MemoryOptimizedBacktestEngine):
                result = engine.run_chunked_backtest(
                    data, strategy_func, **kwargs)
            else:
                raise ValueError(f"不支持的引擎类型: {type(engine)}")

            # 停止性能监控
            perf_metrics = self.performance_optimizer.stop_monitoring()

            # 构建回测性能指标
            backtest_metrics = BacktestPerformanceMetrics(
                execution_time=perf_metrics.execution_time,
                memory_usage=perf_metrics.memory_usage,
                cpu_usage=perf_metrics.cpu_usage,
                vectorization_ratio=self._calculate_vectorization_ratio(
                    result),
                parallel_efficiency=1.0,  # 单线程执行
                optimization_level=self.optimization_level,
                timestamp=datetime.now()
            )

            return result, backtest_metrics

        except Exception as e:
            logger.error(f"优化回测执行失败: {e}")
            raise

    def _select_optimal_engine(self, data: pd.DataFrame) -> Any:
        """自动选择最优引擎"""
        data_size = len(data)
        memory_usage = psutil.virtual_memory().percent

        # 基于数据大小和内存使用情况选择引擎
        if data_size > 100000 or memory_usage > 80:
            logger.info("选择内存优化引擎")
            return self.memory_engine
        else:
            logger.info("选择向量化引擎")
            return self.vectorized_engine

    def _calculate_vectorization_ratio(self, result: pd.DataFrame) -> float:
        """计算向量化比率"""
        try:
            # 简化计算：基于结果数据的完整性
            if len(result) == 0:
                return 0.0

            # 检查关键列的完整性
            key_columns = ['position', 'capital', 'returns']
            complete_ratio = sum(
                1 for col in key_columns
                if col in result.columns and not result[col].isna().all()
            ) / len(key_columns)

            return complete_ratio

        except Exception:
            return 0.0

    def run_batch_optimization(self, data_dict: Dict[str, pd.DataFrame],
                               strategy_func: Callable, param_combinations: List[Dict],
                               max_workers: Optional[int] = None) -> Dict[str, Any]:
        """
        批量优化回测

        Args:
            data_dict: {股票代码: 数据} 字典
            strategy_func: 策略函数
            param_combinations: 参数组合列表
            max_workers: 最大工作线程数

        Returns:
            Dict: 批量优化结果
        """
        try:
            logger.info(
                f"开始批量优化 - 股票数: {len(data_dict)}, 参数组合数: {len(param_combinations)}")

            # 设置并行引擎的工作线程数
            if max_workers:
                self.parallel_engine.max_workers = max_workers

            # 运行并行回测
            results = self.parallel_engine.run_parallel_backtest(
                data_dict, strategy_func, param_combinations, use_processes=True
            )

            # 分析结果
            analysis = self._analyze_batch_results(results)

            return {
                'results': results,
                'analysis': analysis,
                'total_combinations': len(param_combinations) * len(data_dict),
                'successful_runs': len(results)
            }

        except Exception as e:
            logger.error(f"批量优化失败: {e}")
            raise

    def _analyze_batch_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """分析批量结果"""
        try:
            if not results:
                return {}

            # 提取性能指标
            performance_metrics = []
            for key, result_data in results.items():
                result = result_data['result']
                if 'returns' in result.columns:
                    returns = result['returns'].dropna()
                    if len(returns) > 0:
                        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() != 0 else 0
                        total_return = (1 + returns).prod() - 1

                        performance_metrics.append({
                            'key': key,
                            'stock_code': result_data['stock_code'],
                            'params': result_data['params'],
                            'sharpe_ratio': sharpe,
                            'total_return': total_return
                        })

            # 排序并分析
            performance_metrics.sort(
                key=lambda x: x['sharpe_ratio'], reverse=True)

            return {
                'best_performance': performance_metrics[0] if performance_metrics else None,
                'worst_performance': performance_metrics[-1] if performance_metrics else None,
                'avg_sharpe': np.mean([m['sharpe_ratio'] for m in performance_metrics]) if performance_metrics else 0,
                'avg_return': np.mean([m['total_return'] for m in performance_metrics]) if performance_metrics else 0,
                'total_analyzed': len(performance_metrics)
            }

        except Exception as e:
            logger.error(f"分析批量结果失败: {e}")
            return {}

# 装饰器函数

def optimize_backtest_performance(optimization_level: BacktestOptimizationLevel = BacktestOptimizationLevel.PROFESSIONAL):
    """回测性能优化装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            optimizer = ProfessionalBacktestOptimizer(optimization_level)

            # 如果第一个参数是DataFrame，则进行优化
            if args and isinstance(args[0], pd.DataFrame):
                data = args[0]

                # 内存优化
                optimized_data = optimizer.performance_optimizer.optimize_dataframe(
                    data)
                args = (optimized_data) + args[1:]

            return func(*args, **kwargs)
        return wrapper
    return decorator

# 便捷函数

def create_backtest_optimizer(optimization_level: BacktestOptimizationLevel = BacktestOptimizationLevel.PROFESSIONAL) -> ProfessionalBacktestOptimizer:
    """创建回测优化器实例"""
    return ProfessionalBacktestOptimizer(optimization_level=optimization_level)

def run_optimized_backtest(data: pd.DataFrame, strategy_func: Callable,
                           optimization_level: BacktestOptimizationLevel = BacktestOptimizationLevel.PROFESSIONAL,
                           **kwargs) -> Tuple[pd.DataFrame, BacktestPerformanceMetrics]:
    """运行优化回测"""
    optimizer = create_backtest_optimizer(optimization_level)
    return optimizer.optimize_backtest_execution(data, strategy_func, **kwargs)
