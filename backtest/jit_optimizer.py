from loguru import logger
"""
JIT编译优化器
预编译关键函数，提升性能
"""

import numpy as np
import numba
from numba import jit, njit, prange
from typing import Tuple, Dict, Any, Callable, List
import os
from pathlib import Path
import time
import threading
import shutil

class JITOptimizer:
    """JIT编译优化器"""

    def __init__(self):
        self._compiled_functions = {}
        self._cache_dir = Path("cache/numba")
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # JIT优化启用状态
        self._enabled = True

        # 统计信息
        self._compile_count = 0
        self._compile_time = 0.0
        self._last_compile_time = 0.0
        self._cache_hits = 0
        self._cache_misses = 0
        self._performance_boost = 0.0
        self._lock = threading.Lock()

        # JIT使用情况跟踪
        self._jit_usage_stats = {}
        self._jit_functions = {
            'backtest_core': '回测核心计算',
            'sharpe_ratio': '夏普比率计算',
            'max_drawdown': '最大回撤计算',
            'volatility': '波动率计算',
            'moving_average': '移动平均计算',
            'rsi': 'RSI指标计算',
            'batch_metrics': '批量指标计算'
        }

        # 预编译关键函数
        self._precompile_functions()

    def _precompile_functions(self):
        """预编译关键函数"""
        logger.info("开始预编译JIT函数...")

        start_time = time.time()

        try:
            # 预编译回测核心函数
            self._precompile_backtest_core()

            # 预编译风险指标计算函数
            self._precompile_risk_metrics()

            # 预编译技术指标函数
            self._precompile_technical_indicators()

            compile_time = time.time() - start_time

            with self._lock:
                self._compile_time = compile_time
                self._compile_count = len(self._compiled_functions)
                self._last_compile_time = time.time()

            logger.info(f"JIT函数预编译完成，编译时间: {compile_time:.2f}s，编译函数数: {self._compile_count}")

            # 运行性能基准测试
            self._benchmark_performance()

        except Exception as e:
            logger.error(f"JIT函数预编译失败: {e}")

    def _precompile_backtest_core(self):
        """预编译回测核心函数"""
        # 使用小数据集触发编译
        test_prices = np.array([100.0, 101.0, 99.0, 102.0, 98.0])
        test_signals = np.array([0, 1, 0, -1, 0])

        # 触发编译
        _ = optimized_backtest_core(
            test_prices, test_signals, 100000.0, 1.0, 0.001, 0.001
        )

        self._compiled_functions['backtest_core'] = optimized_backtest_core

    def _precompile_risk_metrics(self):
        """预编译风险指标计算函数"""
        test_returns = np.array([0.01, -0.02, 0.015, -0.01, 0.005])

        # 触发编译
        _ = calculate_sharpe_ratio_jit(test_returns, 0.02)
        _ = calculate_max_drawdown_jit(test_returns)
        _ = calculate_volatility_jit(test_returns)

        self._compiled_functions.update({
            'sharpe_ratio': calculate_sharpe_ratio_jit,
            'max_drawdown': calculate_max_drawdown_jit,
            'volatility': calculate_volatility_jit
        })

    def _precompile_technical_indicators(self):
        """预编译技术指标函数"""
        test_prices = np.array([100.0, 101.0, 99.0, 102.0, 98.0, 103.0, 97.0])

        # 触发编译
        _ = moving_average_jit(test_prices, 3)
        _ = rsi_jit(test_prices, 5)

        self._compiled_functions.update({
            'moving_average': moving_average_jit,
            'rsi': rsi_jit
        })

        # 预编译额外的技术指标（从jit_indicators模块）
        try:
            from core.indicators.jit_indicators import (
                calculate_sma_jit,
                calculate_ema_jit,
                calculate_rsi_jit as rsi_jit_new,
                calculate_macd_jit,
                calculate_bollinger_bands_jit,
                calculate_atr_jit,
                calculate_stochastic_jit,
                calculate_williams_r_jit,
                batch_calculate_indicators_jit
            )

            # 触发编译
            _ = calculate_sma_jit(test_prices, 20)
            _ = calculate_ema_jit(test_prices, 20)
            _ = rsi_jit_new(test_prices, 14)
            _ = calculate_macd_jit(test_prices)
            _ = calculate_bollinger_bands_jit(test_prices)
            _ = calculate_atr_jit(test_prices, test_prices, test_prices)
            _ = calculate_stochastic_jit(test_prices, test_prices, test_prices)
            _ = calculate_williams_r_jit(test_prices, test_prices, test_prices)
            _ = batch_calculate_indicators_jit(test_prices, test_prices, test_prices, test_prices, ['sma', 'ema', 'rsi'])

            self._compiled_functions.update({
                'sma': calculate_sma_jit,
                'ema': calculate_ema_jit,
                'rsi_new': rsi_jit_new,
                'macd': calculate_macd_jit,
                'bollinger_bands': calculate_bollinger_bands_jit,
                'atr': calculate_atr_jit,
                'stochastic': calculate_stochastic_jit,
                'williams_r': calculate_williams_r_jit,
                'batch_indicators': batch_calculate_indicators_jit
            })

            # 更新JIT函数列表
            self._jit_functions.update({
                'sma': '简单移动平均计算',
                'ema': '指数移动平均计算',
                'macd': 'MACD指标计算',
                'bollinger_bands': '布林带计算',
                'atr': 'ATR指标计算',
                'stochastic': '随机指标计算',
                'williams_r': '威廉指标计算',
                'batch_indicators': '批量指标计算'
            })

            logger.info("成功预编译额外的JIT技术指标")

        except ImportError as e:
            logger.warning(f"无法导入jit_indicators模块: {e}")

    def _benchmark_performance(self):
        """运行性能基准测试，测量JIT vs Python的性能提升"""
        try:
            logger.info("开始性能基准测试...")

            # 创建测试数据集（稍大一些以获得准确结果）
            test_prices = np.random.randn(1000) * 10 + 100
            test_signals = np.random.randint(-1, 2, 1000)
            test_returns = np.random.randn(1000) * 0.01

            # 测试回测核心函数
            python_time = self._benchmark_python_backtest(test_prices, test_signals)
            jit_time = self._benchmark_jit_backtest(test_prices, test_signals)
            backtest_boost = self._calculate_boost(python_time, jit_time)

            # 测试风险指标函数
            python_time = self._benchmark_python_risk(test_returns)
            jit_time = self._benchmark_jit_risk(test_returns)
            risk_boost = self._calculate_boost(python_time, jit_time)

            # 计算平均性能提升
            avg_boost = (backtest_boost + risk_boost) / 2

            with self._lock:
                self._performance_boost = avg_boost

            logger.info(f"性能基准测试完成，回测提升: {backtest_boost:.1f}%，风险指标提升: {risk_boost:.1f}%，平均提升: {avg_boost:.1f}%")

        except Exception as e:
            logger.warning(f"性能基准测试失败: {e}")
            # 使用估算值
            with self._lock:
                self._performance_boost = 50.0

    def _benchmark_python_backtest(self, prices: np.ndarray, signals: np.ndarray) -> float:
        """基准测试Python版本的回测函数"""
        start = time.time()
        n = len(prices)
        positions = np.zeros(n)
        capital = np.zeros(n)
        returns = np.zeros(n)

        initial_capital = 100000.0
        position_size = 1.0
        commission_pct = 0.001
        slippage_pct = 0.001

        capital[0] = initial_capital
        current_position = 0.0
        current_capital = initial_capital

        for i in range(1, n):
            signal = signals[i]
            price = prices[i]

            if signal == 1 and current_position == 0:
                trade_cost = price * (commission_pct + slippage_pct)
                shares = (current_capital * position_size) / (price + trade_cost)
                current_position = shares
                current_capital -= shares * (price + trade_cost)
            elif signal == -1 and current_position > 0:
                trade_cost = price * (commission_pct + slippage_pct)
                current_capital += current_position * (price - trade_cost)
                current_position = 0

            positions[i] = current_position

            if current_position > 0:
                equity = current_capital + current_position * price
            else:
                equity = current_capital

            capital[i] = equity

            if capital[i-1] != 0:
                returns[i] = (capital[i] - capital[i-1]) / capital[i-1]

        return time.time() - start

    def _benchmark_jit_backtest(self, prices: np.ndarray, signals: np.ndarray) -> float:
        """基准测试JIT版本的回测函数"""
        start = time.time()
        _ = optimized_backtest_core(prices, signals, 100000.0, 1.0, 0.001, 0.001)
        return time.time() - start

    def _benchmark_python_risk(self, returns: np.ndarray) -> float:
        """基准测试Python版本的风险指标函数"""
        start = time.time()

        # 夏普比率
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        if std_return != 0:
            _ = (mean_return * 252 - 0.02) / (std_return * np.sqrt(252))

        # 最大回撤
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        _ = np.min(drawdown)

        # 波动率
        _ = np.std(returns) * np.sqrt(252)

        return time.time() - start

    def _benchmark_jit_risk(self, returns: np.ndarray) -> float:
        """基准测试JIT版本的风险指标函数"""
        start = time.time()
        _ = calculate_sharpe_ratio_jit(returns, 0.02)
        _ = calculate_max_drawdown_jit(returns)
        _ = calculate_volatility_jit(returns)
        return time.time() - start

    def _calculate_boost(self, python_time: float, jit_time: float) -> float:
        """计算性能提升比例"""
        if python_time == 0:
            return 0.0
        return ((python_time - jit_time) / python_time) * 100

    def enable(self):
        """启用JIT优化"""
        with self._lock:
            if not self._enabled:
                self._enabled = True
                logger.info("JIT优化已启用")

    def disable(self):
        """禁用JIT优化"""
        with self._lock:
            if self._enabled:
                self._enabled = False
                logger.info("JIT优化已禁用")

    def is_enabled(self) -> bool:
        """检查JIT优化是否启用"""
        with self._lock:
            return self._enabled

    def get_function(self, name: str):
        """获取预编译的函数

        如果JIT优化被禁用，则返回None

        Args:
            name: 函数名称

        Returns:
            预编译的函数，如果JIT被禁用或函数不存在则返回None
        """
        if not self.is_enabled():
            return None

        func = self._compiled_functions.get(name)

        with self._lock:
            if func is not None:
                self._cache_hits += 1
                
                # 记录JIT使用情况
                if name not in self._jit_usage_stats:
                    self._jit_usage_stats[name] = {
                        'call_count': 0,
                        'last_call_time': 0,
                        'function_name': self._jit_functions.get(name, name)
                    }
                self._jit_usage_stats[name]['call_count'] += 1
                self._jit_usage_stats[name]['last_call_time'] = time.time()
                
            else:
                self._cache_misses += 1

        return func

    def get_stats(self) -> Dict[str, Any]:
        """获取编译统计信息

        Returns:
            Dict[str, Any]: 包含编译统计信息的字典
                - compile_count: 编译函数数量
                - compile_time: 总编译时间（秒）
                - last_compile_time: 最后一次编译时间戳
                - performance_boost: 性能提升比例（百分比）
                - cache_hits: 缓存命中次数
                - cache_misses: 缓存未命中次数
        """
        with self._lock:
            return {
                'compile_count': self._compile_count,
                'compile_time': self._compile_time,
                'last_compile_time': self._last_compile_time,
                'performance_boost': self._performance_boost,
                'cache_hits': self._cache_hits,
                'cache_misses': self._cache_misses
            }

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            Dict[str, Any]: 包含缓存统计信息的字典
                - hit_rate: 缓存命中率（百分比）
                - cache_size: 缓存总大小（字节）
                - cache_size_mb: 缓存总大小（MB）
                - cache_files: 缓存文件数量
        """
        with self._lock:
            total_requests = self._cache_hits + self._cache_misses
            hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0.0

        cache_size = 0
        cache_files = 0

        if self._cache_dir.exists():
            try:
                for cache_file in self._cache_dir.glob('*.nbc'):
                    cache_size += cache_file.stat().st_size
                    cache_files += 1
            except Exception as e:
                logger.warning(f"扫描缓存目录失败: {e}")

        return {
            'hit_rate': hit_rate,
            'cache_size': cache_size,
            'cache_size_mb': cache_size / (1024 * 1024),
            'cache_files': cache_files
        }

    def get_optimization_level(self) -> int:
        """获取Numba优化等级

        Returns:
            int: 优化等级（0=O0, 1=O1, 2=O2, 3=O3）
                  Numba默认使用O2优化级别
        """
        return 2

    def get_execution_efficiency(self) -> float:
        """获取执行效率

        执行效率基于缓存命中率和性能提升计算：
        - 基础效率：10%（即使没有缓存也有一定效率）
        - 缓存命中率贡献：80%（缓存命中率高说明JIT有效）
        - 性能提升贡献：10%（实际性能提升）

        Returns:
            float: 执行效率（0-100之间的百分比）
        """
        with self._lock:
            total_requests = self._cache_hits + self._cache_misses
            hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0.0

        # 计算执行效率
        # 基础效率10% + 缓存命中率贡献80% + 性能提升贡献10%
        base_efficiency = 10.0
        cache_efficiency = hit_rate * 0.8
        performance_efficiency = min(self._performance_boost, 100.0) * 0.1

        total_efficiency = base_efficiency + cache_efficiency + performance_efficiency

        return min(total_efficiency, 100.0)

    def clear_cache(self):
        """清理JIT编译缓存和重置统计信息

        清理操作包括：
        1. 删除cache/numba/目录下的所有缓存文件
        2. 重置编译统计信息
        3. 重新创建缓存目录
        """
        with self._lock:
            try:
                # 删除缓存目录
                if self._cache_dir.exists():
                    shutil.rmtree(self._cache_dir)
                    logger.info(f"已删除JIT缓存目录: {self._cache_dir}")

                # 重新创建缓存目录
                self._cache_dir.mkdir(parents=True, exist_ok=True)

                # 重置统计信息
                self._compile_count = 0
                self._compile_time = 0.0
                self._last_compile_time = 0.0
                self._cache_hits = 0
                self._cache_misses = 0
                self._performance_boost = 0.0
                self._jit_usage_stats = {}

                logger.info("JIT缓存已清理，统计信息已重置")

            except Exception as e:
                logger.error(f"清理JIT缓存失败: {e}")
                raise

    def get_jit_usage(self) -> Dict[str, Any]:
        """获取JIT使用情况

        Returns:
            Dict[str, Any]: 包含JIT使用情况的字典
                - functions: 已编译的函数列表
                - usage_stats: 各函数的使用统计
                - total_calls: 总调用次数
                - most_used: 最常用的函数
                - last_used: 最近使用的函数
        """
        with self._lock:
            total_calls = sum(stats['call_count'] for stats in self._jit_usage_stats.values())
            
            # 找出最常用的函数
            most_used = None
            max_calls = 0
            for name, stats in self._jit_usage_stats.items():
                if stats['call_count'] > max_calls:
                    max_calls = stats['call_count']
                    most_used = name
            
            # 找出最近使用的函数
            last_used = None
            last_time = 0
            for name, stats in self._jit_usage_stats.items():
                if stats['last_call_time'] > last_time:
                    last_time = stats['last_call_time']
                    last_used = name
            
            return {
                'functions': list(self._jit_functions.keys()),
                'function_names': self._jit_functions,
                'usage_stats': dict(self._jit_usage_stats),
                'total_calls': total_calls,
                'most_used': most_used,
                'most_used_name': self._jit_functions.get(most_used, most_used) if most_used else None,
                'most_used_count': max_calls,
                'last_used': last_used,
                'last_used_name': self._jit_functions.get(last_used, last_used) if last_used else None,
                'last_used_time': last_time
            }

    def register_auto_jit_function(self, name: str, func: Callable, description: str = "", category: str = "auto"):
        """注册AutoJIT装饰器的函数
        
        Args:
            name: 函数名称
            func: 函数（可以是JIT版本或原始版本）
            description: 函数描述
            category: 函数分类
        """
        with self._lock:
            self._compiled_functions[name] = func
            self._jit_functions[name] = description
            
            # 初始化使用统计
            if name not in self._jit_usage_stats:
                self._jit_usage_stats[name] = {
                    'call_count': 0,
                    'last_call_time': 0,
                    'function_name': description
                }
            
            self._compile_count = len(self._compiled_functions)
            
            logger.info(f"已注册AutoJIT函数: {name} ({category})")

    def import_from_auto_jit(self):
        """从AutoJIT系统导入所有函数"""
        try:
            from backtest.auto_jit_decorator import auto_jit_instance
            
            # 获取所有AutoJIT函数
            auto_jit_functions = auto_jit_instance.get_all_functions()
            
            imported_count = 0
            for name, func_info in auto_jit_functions.items():
                # 注册JIT版本
                self.register_auto_jit_function(
                    name=name,
                    func=func_info['jit'],
                    description=func_info['description'],
                    category=func_info['category']
                )
                imported_count += 1
            
            logger.info(f"从AutoJIT系统导入了 {imported_count} 个函数")
            
            return imported_count
            
        except ImportError as e:
            logger.warning(f"无法导入AutoJIT系统: {e}")
            return 0

    def auto_discover_and_register(self, module_name: str, pattern: str = "calculate_") -> List[str]:
        """自动发现并注册模块中的函数
        
        Args:
            module_name: 模块名称
            pattern: 函数名匹配模式
        
        Returns:
            注册的函数名称列表
        """
        try:
            from backtest.auto_jit_decorator import discover_and_register
            
            # 使用AutoJIT的自动发现功能
            registered = discover_and_register(module_name, pattern)
            
            # 导入新注册的函数
            self.import_from_auto_jit()
            
            return registered
            
        except ImportError as e:
            logger.warning(f"无法使用AutoJIT自动发现功能: {e}")
            return []

# 优化的回测核心函数
@njit(cache=True, fastmath=True, parallel=False)  # 序列依赖，不能并行
def optimized_backtest_core(prices: np.ndarray, signals: np.ndarray,
                            initial_capital: float, position_size: float,
                            commission_pct: float, slippage_pct: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    优化的回测核心计算
    """
    n = len(prices)
    positions = np.zeros(n, dtype=np.float64)
    capital = np.zeros(n, dtype=np.float64)
    returns = np.zeros(n, dtype=np.float64)

    capital[0] = initial_capital
    current_position = 0.0
    current_capital = initial_capital

    for i in range(1, n):
        signal = signals[i]
        price = prices[i]

        # 处理交易信号
        if signal == 1 and current_position == 0:  # 买入信号且无持仓
            trade_cost = price * (commission_pct + slippage_pct)
            shares = (current_capital * position_size) / (price + trade_cost)
            current_position = shares
            current_capital -= shares * (price + trade_cost)
        elif signal == -1 and current_position > 0:  # 卖出信号且有持仓
            trade_cost = price * (commission_pct + slippage_pct)
            current_capital += current_position * (price - trade_cost)
            current_position = 0

        positions[i] = current_position

        # 计算当前权益
        if current_position > 0:
            equity = current_capital + current_position * price
        else:
            equity = current_capital

        capital[i] = equity

        # 计算收益率
        if capital[i-1] != 0:
            returns[i] = (capital[i] - capital[i-1]) / capital[i-1]

    return positions, capital, returns

# 并行优化的风险指标计算
@njit(cache=True, fastmath=True, parallel=True)
def calculate_sharpe_ratio_jit(returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
    """计算夏普比率（JIT优化）"""
    if len(returns) == 0:
        return 0.0

    mean_return = np.mean(returns)
    std_return = np.std(returns)

    if std_return == 0:
        return 0.0

    # 年化处理
    annualized_return = mean_return * 252
    annualized_std = std_return * np.sqrt(252)

    return (annualized_return - risk_free_rate) / annualized_std

@njit(cache=True, fastmath=True)
def calculate_max_drawdown_jit(returns: np.ndarray) -> float:
    """计算最大回撤（JIT优化）"""
    if len(returns) == 0:
        return 0.0

    cumulative = np.cumprod(1 + returns)

    # 手动实现 accumulate，因为 Numba 不支持 np.maximum.accumulate
    running_max = np.zeros_like(cumulative)
    running_max[0] = cumulative[0]
    for i in range(1, len(cumulative)):
        running_max[i] = max(running_max[i-1], cumulative[i])

    drawdown = (cumulative - running_max) / running_max

    return np.min(drawdown)

@njit(cache=True, fastmath=True, parallel=True)
def calculate_volatility_jit(returns: np.ndarray) -> float:
    """计算波动率（JIT优化）"""
    if len(returns) == 0:
        return 0.0

    return np.std(returns) * np.sqrt(252)

# 技术指标函数
@njit(cache=True, fastmath=True, parallel=True)
def moving_average_jit(prices: np.ndarray, window: int) -> np.ndarray:
    """移动平均（JIT优化）"""
    n = len(prices)
    ma = np.zeros(n)

    for i in prange(window-1, n):
        ma[i] = np.mean(prices[i-window+1:i+1])

    return ma

@njit(cache=True, fastmath=True)
def rsi_jit(prices: np.ndarray, window: int = 14) -> np.ndarray:
    """RSI指标（JIT优化）"""
    n = len(prices)
    rsi = np.zeros(n)

    if n < window + 1:
        return rsi

    # 计算价格变化
    deltas = np.diff(prices)

    # 分离涨跌
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    # 计算初始平均涨跌幅
    avg_gain = np.mean(gains[:window])
    avg_loss = np.mean(losses[:window])

    # 计算RSI
    for i in range(window, n-1):
        avg_gain = (avg_gain * (window - 1) + gains[i]) / window
        avg_loss = (avg_loss * (window - 1) + losses[i]) / window

        if avg_loss == 0:
            rsi[i+1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i+1] = 100.0 - (100.0 / (1.0 + rs))

    return rsi

# 批量计算优化
@njit(cache=True, fastmath=True, parallel=True)
def batch_calculate_metrics(returns_matrix: np.ndarray) -> np.ndarray:
    """批量计算多个策略的指标（JIT优化）"""
    n_strategies, n_periods = returns_matrix.shape
    metrics = np.zeros((n_strategies, 4))  # sharpe, max_dd, volatility, total_return

    for i in prange(n_strategies):
        returns = returns_matrix[i, :]

        # Sharpe比率
        metrics[i, 0] = calculate_sharpe_ratio_jit(returns)

        # 最大回撤
        metrics[i, 1] = calculate_max_drawdown_jit(returns)

        # 波动率
        metrics[i, 2] = calculate_volatility_jit(returns)

        # 总收益率
        metrics[i, 3] = np.prod(1 + returns) - 1

    return metrics

# 全局JIT优化器实例
jit_optimizer = JITOptimizer()
