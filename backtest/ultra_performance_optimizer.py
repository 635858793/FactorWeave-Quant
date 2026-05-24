from loguru import logger
"""
超高性能回测优化器
使用GPU加速、分布式计算、内存映射等最新优化技术
对标顶级量化平台的性能标准
"""

import numpy as np
import pandas as pd
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import mmap
import os
import psutil
import gc
import time
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import hashlib  # 哈希计算
# 纯Loguru架构，移除旧的日志导入

# 可选依赖 - GPU和分布式计算
try:
    import numba
    from numba import cuda, jit, njit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    logger.warning("Numba未安装，GPU加速功能不可用")
    NUMBA_AVAILABLE = False
    # 创建dummy装饰器

    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if not args else decorator(args[0])
    njit = jit
    prange = range

try:
    import cupy as cp
    CUPY_AVAILABLE = True
except ImportError:
    logger.debug("CuPy未安装，GPU数组计算不可用")
    CUPY_AVAILABLE = False
    cp = None

try:
    import dask.dataframe as dd
    import dask.array as da
    from dask.distributed import Client, as_completed
    DASK_AVAILABLE = True
except ImportError:
    logger.debug("Dask未安装，分布式计算不可用")
    DASK_AVAILABLE = False
    dd = None
    da = None
    Client = None

try:
    import ray
    RAY_AVAILABLE = True
except ImportError:
    logger.debug("Ray未安装，分布式框架不可用")
    RAY_AVAILABLE = False
    ray = None

try:
    import h5py
    H5PY_AVAILABLE = True
except ImportError:
    logger.debug("h5py未安装，HDF5存储不可用")
    H5PY_AVAILABLE = False
    h5py = None

try:
    import zarr
    ZARR_AVAILABLE = True
except ImportError:
    logger.debug("Zarr未安装，云原生存储不可用")
    ZARR_AVAILABLE = False
    zarr = None


class PerformanceLevel(Enum):
    """性能级别"""
    STANDARD = "standard"        # 标准性能
    HIGH = "high"               # 高性能
    ULTRA = "ultra"             # 超高性能
    EXTREME = "extreme"         # 极致性能


class ComputeBackend(Enum):
    """计算后端"""
    CPU = "cpu"                 # CPU计算
    GPU = "gpu"                 # GPU计算
    DISTRIBUTED = "distributed"  # 分布式计算
    HYBRID = "hybrid"           # 混合计算


@dataclass
class PerformanceMetrics:
    """性能指标"""
    execution_time: float
    throughput: float  # 每秒处理的数据点数
    memory_usage: float
    cpu_utilization: float
    cache_hit_rate: float
    parallel_efficiency: float
    optimization_level: str


class UltraPerformanceOptimizer:
    """
    超高性能回测优化器
    集成多种最新优化技术
    """

    def __init__(self,
                 performance_level: PerformanceLevel = PerformanceLevel.ULTRA,
                 compute_backend: ComputeBackend = ComputeBackend.HYBRID):
        """
        初始化超高性能优化器

        Args:
            performance_level: 性能级别
            compute_backend: 计算后端
            # log_manager: 已迁移到Loguru日志系统
        """
        self.performance_level = performance_level
        self.compute_backend = compute_backend
        # 纯Loguru架构，移除log_manager依赖

        # 系统信息
        self.cpu_count = mp.cpu_count()
        self.memory_total = psutil.virtual_memory().total
        self.gpu_available = self._check_gpu_availability()

        # 性能配置
        self.config = self._initialize_performance_config()

        # 缓存系统
        self.cache = {}
        self.cache_stats = {"hits": 0, "misses": 0}
        self._cache_lock = threading.Lock()

        # 分布式客户端
        self.dask_client = None
        self.ray_initialized = False
        self._compute_env_initialized = False

        # 延迟初始化计算环境（避免Windows多进程问题）
        # self._initialize_compute_environment()  # 改为按需初始化

    def _check_gpu_availability(self) -> bool:
        """检查GPU可用性"""
        if not CUPY_AVAILABLE:
            logger.debug("CuPy未安装，GPU加速不可用")
            return False

        try:
            # 检查GPU设备
            cp.cuda.Device(0).compute_capability
            logger.info("CuPy GPU可用")
            return True
        except Exception as e:
            logger.debug(f"GPU检测失败: {e}")
            return False

    def _initialize_performance_config(self) -> Dict[str, Any]:
        """初始化性能配置"""
        base_config = {
            "chunk_size": 10000,
            "max_workers": self.cpu_count,
            "memory_limit": self.memory_total * 0.8,
            "cache_size": 1000,
            "gpu_memory_fraction": 0.8,
            "prefetch_factor": 2
        }

        if self.performance_level == PerformanceLevel.STANDARD:
            return base_config
        elif self.performance_level == PerformanceLevel.HIGH:
            base_config.update({
                "chunk_size": 50000,
                "max_workers": self.cpu_count * 2,
                "cache_size": 5000,
                "prefetch_factor": 4
            })
        elif self.performance_level == PerformanceLevel.ULTRA:
            base_config.update({
                "chunk_size": 100000,
                "max_workers": self.cpu_count * 4,
                "cache_size": 10000,
                "prefetch_factor": 8,
                "use_memory_mapping": True,
                "use_vectorization": True
            })
        else:  # EXTREME
            base_config.update({
                "chunk_size": 500000,
                "max_workers": self.cpu_count * 8,
                "cache_size": 50000,
                "prefetch_factor": 16,
                "use_memory_mapping": True,
                "use_vectorization": True,
                "use_gpu_acceleration": self.gpu_available,
                "use_distributed_computing": True
            })

        return base_config

    def _ensure_compute_environment(self):
        """确保计算环境已初始化（延迟加载）"""
        if self._compute_env_initialized:
            return

        try:
            self._initialize_compute_environment()
            self._compute_env_initialized = True
        except Exception as e:
            logger.warning(f"计算环境初始化失败: {e}，将使用基础模式")

    def _initialize_compute_environment(self):
        """初始化计算环境（内部方法，由_ensure_compute_environment调用）"""
        try:
            # 初始化Dask分布式客户端
            if self.compute_backend in [ComputeBackend.DISTRIBUTED, ComputeBackend.HYBRID]:
                try:
                    self.dask_client = Client(
                        n_workers=self.config["max_workers"],
                        threads_per_worker=2,
                        memory_limit=f"{self.config['memory_limit'] // self.config['max_workers']}B"
                    )
                    logger.info(
                        f"Dask客户端已初始化: {self.dask_client.dashboard_link}")
                except Exception as e:
                    logger.warning(f"Dask初始化失败: {e}")

            # 初始化Ray
            if self.performance_level == PerformanceLevel.EXTREME:
                try:
                    if not ray.is_initialized():
                        ray.init(
                            num_cpus=self.cpu_count,
                            object_store_memory=int(
                                self.config['memory_limit'] * 0.3)
                        )
                        self.ray_initialized = True
                        logger.info("Ray已初始化")
                except Exception as e:
                    logger.warning(f"Ray初始化失败: {e}")

        except Exception as e:
            logger.error(f"计算环境初始化失败: {e}")

    @staticmethod
    @njit(cache=True, fastmath=True)
    def _ultra_fast_backtest_core(prices: np.ndarray,
                                  signals: np.ndarray,
                                  initial_capital: float,
                                  position_size: float,
                                  commission_pct: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        超高速回测核心（Numba优化）
        使用快速数学运算
        """
        n = len(prices)
        positions = np.zeros(n, dtype=np.float64)
        capital = np.zeros(n, dtype=np.float64)
        returns = np.zeros(n, dtype=np.float64)

        capital[0] = initial_capital

        # 向量化计算持仓和收益
        current_position = 0.0
        current_cash = initial_capital

        for i in range(1, n):
            signal = signals[i]
            price = prices[i]

            # 处理交易信号
            if signal != 0 and signal != positions[i-1]:
                if signal == 1:  # 买入
                    shares = (current_cash * position_size) / price
                    cost = shares * price * (1 + commission_pct)
                    if cost <= current_cash:
                        current_position = shares
                        current_cash -= cost
                elif signal == -1:  # 卖出
                    if current_position > 0:
                        proceeds = current_position * \
                            price * (1 - commission_pct)
                        current_cash += proceeds
                        current_position = 0

            positions[i] = current_position

            # 计算总权益
            market_value = current_position * price
            total_equity = current_cash + market_value
            capital[i] = total_equity

            # 计算收益率
            if capital[i-1] != 0:
                returns[i] = (capital[i] - capital[i-1]) / capital[i-1]

        return positions, capital, returns

    def _gpu_accelerated_backtest(self, data: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """GPU加速回测"""
        try:
            if not self.gpu_available:
                raise RuntimeError("GPU不可用")

            # 将数据转移到GPU
            prices_gpu = cp.asarray(data['close'].values, dtype=cp.float64)
            signals_gpu = cp.asarray(data['signal'].values, dtype=cp.float64)

            # GPU核函数
            @cp.fuse()
            def gpu_backtest_kernel(prices, signals, initial_capital, position_size, commission_pct):
                n = len(prices)
                positions = cp.zeros(n, dtype=cp.float64)
                capital = cp.zeros(n, dtype=cp.float64)
                returns = cp.zeros(n, dtype=cp.float64)

                capital[0] = initial_capital
                current_position = 0.0
                current_cash = initial_capital

                for i in range(1, n):
                    signal = signals[i]
                    price = prices[i]

                    if signal != 0:
                        if signal == 1 and current_position <= 0:
                            shares = (current_cash * position_size) / price
                            cost = shares * price * (1 + commission_pct)
                            if cost <= current_cash:
                                current_position = shares
                                current_cash -= cost
                        elif signal == -1 and current_position > 0:
                            proceeds = current_position * \
                                price * (1 - commission_pct)
                            current_cash += proceeds
                            current_position = 0

                    positions[i] = current_position
                    market_value = current_position * price
                    capital[i] = current_cash + market_value

                    if capital[i-1] != 0:
                        returns[i] = (capital[i] - capital[i-1]) / capital[i-1]

                return positions, capital, returns

            # 执行GPU计算
            positions_gpu, capital_gpu, returns_gpu = gpu_backtest_kernel(
                prices_gpu, signals_gpu,
                kwargs.get('initial_capital', 100000),
                kwargs.get('position_size', 1.0),
                kwargs.get('commission_pct', 0.001)
            )

            # 将结果转回CPU
            result = data.copy()
            result['position'] = cp.asnumpy(positions_gpu)
            result['capital'] = cp.asnumpy(capital_gpu)
            result['returns'] = cp.asnumpy(returns_gpu)
            result['cumulative_returns'] = (
                1 + result['returns']).cumprod() - 1

            return result

        except Exception as e:
            logger.error(f"GPU加速回测失败: {e}")
            # 回退到CPU计算
            return self._cpu_optimized_backtest(data, **kwargs)

    def _cpu_optimized_backtest(self, data: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """CPU优化回测"""
        try:
            # 提取数组数据
            prices = data['close'].values.astype(np.float64)
            signals = data['signal'].values.astype(np.float64)

            # 调用优化的核心函数
            positions, capital, returns = self._ultra_fast_backtest_core(
                prices, signals,
                kwargs.get('initial_capital', 100000),
                kwargs.get('position_size', 1.0),
                kwargs.get('commission_pct', 0.001)
            )

            # 构建结果
            result = data.copy()
            result['position'] = positions
            result['capital'] = capital
            result['returns'] = returns
            result['cumulative_returns'] = (
                1 + pd.Series(returns)).cumprod() - 1

            return result

        except Exception as e:
            logger.error(f"CPU优化回测失败: {e}")
            raise

    def _distributed_backtest(self, data: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """分布式回测"""
        try:
            if self.dask_client is None:
                raise RuntimeError("Dask客户端未初始化")

            # 将数据转换为Dask DataFrame
            dask_data = dd.from_pandas(
                data, npartitions=self.config["max_workers"])

            # 定义分布式计算函数
            def distributed_backtest_partition(partition):
                return self._cpu_optimized_backtest(partition, **kwargs)

            # 执行分布式计算
            result_dask = dask_data.map_partitions(
                distributed_backtest_partition,
                meta=data
            )

            # 收集结果
            result = result_dask.compute()

            return result

        except Exception as e:
            logger.error(f"分布式回测失败: {e}")
            # 回退到CPU计算
            return self._cpu_optimized_backtest(data, **kwargs)

    @ray.remote
    def _ray_backtest_worker(self, data_chunk: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """Ray分布式工作器"""
        return self._cpu_optimized_backtest(data_chunk, **kwargs)

    def _ray_distributed_backtest(self, data: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """Ray分布式回测"""
        try:
            if not self.ray_initialized:
                raise RuntimeError("Ray未初始化")

            # 分割数据
            chunk_size = len(data) // self.config["max_workers"]
            chunks = [data.iloc[i:i+chunk_size]
                      for i in range(0, len(data), chunk_size)]

            # 提交任务
            futures = [self._ray_backtest_worker.remote(
                self, chunk, **kwargs) for chunk in chunks]

            # 收集结果
            results = ray.get(futures)

            # 合并结果
            final_result = pd.concat(results, ignore_index=True)

            return final_result

        except Exception as e:
            logger.error(f"Ray分布式回测失败: {e}")
            return self._cpu_optimized_backtest(data, **kwargs)

    def _memory_mapped_backtest(self, data: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """内存映射回测（处理大数据集）"""
        from .resource_manager import managed_backtest_resources
        from core.services.unified_cache_provider import get_smart_cache, get_async_io_cache

        smart_cache = get_smart_cache()
        async_io_cache = get_async_io_cache()

        with managed_backtest_resources() as resource_manager:
            try:
                data_hash = hashlib.md5(str(data.values.tobytes()).encode()).hexdigest()
                cache_key = f"backtest_data_{data_hash}"

                cached_result = smart_cache.get(cache_key)
                if cached_result is not None:
                    logger.info("使用缓存的回测数据")
                    return cached_result

                temp_file = Path("temp/backtest_data.h5")
                temp_file.parent.mkdir(exist_ok=True)

                resource_manager.register_temp_file(temp_file)

                prices_data = data['close'].values.astype(np.float64)
                signals_data = data['signal'].values.astype(np.float64)

                future_write = async_io_cache.write_hdf5_async(temp_file, 'prices', prices_data)
                future_write.result()

                future_write = async_io_cache.write_hdf5_async(temp_file, 'signals', signals_data)
                future_write.result()

                prices = async_io_cache.read_hdf5_async(temp_file, 'prices')
                signals = async_io_cache.read_hdf5_async(temp_file, 'signals')

                # 执行回测
                positions, capital, returns = self._ultra_fast_backtest_core(
                    prices, signals,
                    kwargs.get('initial_capital', 100000),
                    kwargs.get('position_size', 1.0),
                    kwargs.get('commission_pct', 0.001)
                )

                # 构建结果（使用智能复制策略）
                from .resource_manager import global_data_manager
                result = global_data_manager.get_data_copy(data, copy_strategy='smart')
                result['position'] = positions
                result['capital'] = capital
                result['returns'] = returns
                result['cumulative_returns'] = (
                    1 + pd.Series(returns)).cumprod() - 1

                # 缓存结果
                smart_cache.put(cache_key, result, ttl=3600)  # 缓存1小时

                return result

            except Exception as e:
                logger.error(f"内存映射回测失败: {e}")
                return self._cpu_optimized_backtest(data, **kwargs)

    def optimize_backtest(self, data: pd.DataFrame, **kwargs) -> Tuple[pd.DataFrame, PerformanceMetrics]:
        """
        优化回测执行

        Args:
            data: 回测数据
            **kwargs: 回测参数

        Returns:
            Tuple: (回测结果, 性能指标)
        """
        # 确保计算环境已初始化（延迟加载）
        self._ensure_compute_environment()

        start_time = time.time()
        start_memory = psutil.virtual_memory().used

        try:
            logger.info(
                f"开始超高性能回测 - 级别: {self.performance_level.value}, 后端: {self.compute_backend.value}")

            # 数据预处理
            processed_data = self._preprocess_data(data)

            # 选择最优计算方法
            if self.compute_backend == ComputeBackend.GPU and self.gpu_available:
                result = self._gpu_accelerated_backtest(
                    processed_data, **kwargs)
            elif self.compute_backend == ComputeBackend.DISTRIBUTED and self.dask_client:
                result = self._distributed_backtest(processed_data, **kwargs)
            elif self.compute_backend == ComputeBackend.HYBRID:
                # 根据数据大小选择最优方法
                if len(data) > 1000000 and self.gpu_available:
                    result = self._gpu_accelerated_backtest(
                        processed_data, **kwargs)
                elif len(data) > 500000 and self.dask_client:
                    result = self._distributed_backtest(
                        processed_data, **kwargs)
                elif len(data) > 100000:
                    result = self._memory_mapped_backtest(
                        processed_data, **kwargs)
                else:
                    result = self._cpu_optimized_backtest(
                        processed_data, **kwargs)
            else:
                result = self._cpu_optimized_backtest(processed_data, **kwargs)

            # 计算性能指标
            execution_time = time.time() - start_time
            end_memory = psutil.virtual_memory().used
            memory_usage = (end_memory - start_memory) / 1024 / 1024  # MB

            throughput = len(data) / \
                execution_time if execution_time > 0 else 0
            cache_hit_rate = self.cache_stats["hits"] / (self.cache_stats["hits"] + self.cache_stats["misses"]
                                                         ) if (self.cache_stats["hits"] + self.cache_stats["misses"]) > 0 else 0

            performance_metrics = PerformanceMetrics(
                execution_time=execution_time,
                throughput=throughput,
                memory_usage=memory_usage,
                cpu_utilization=psutil.cpu_percent(),
                cache_hit_rate=cache_hit_rate,
                parallel_efficiency=self._calculate_parallel_efficiency(
                    execution_time, len(data)),
                optimization_level=self.performance_level.value
            )

            logger.info(
                f"超高性能回测完成 - 耗时: {execution_time:.3f}秒, 吞吐量: {throughput:.0f}点/秒")

            return result, performance_metrics

        except Exception as e:
            logger.error(f"超高性能回测失败: {e}")
            raise

    def _preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """数据预处理"""
        try:
            # 检查缓存
            data_hash = hash(str(data.values.tobytes()))
            with self._cache_lock:
                if data_hash in self.cache:
                    self.cache_stats["hits"] += 1
                    return self.cache[data_hash]
                self.cache_stats["misses"] += 1

            # 数据清理和优化
            processed = data.copy()

            # 确保数据类型优化
            for col in ['close', 'signal']:
                if col in processed.columns:
                    processed[col] = pd.to_numeric(
                        processed[col], errors='coerce', downcast='float')

            # 移除缺失值
            processed = processed.dropna()

            # 缓存结果
            with self._cache_lock:
                if len(self.cache) < self.config["cache_size"]:
                    self.cache[data_hash] = processed

            return processed

        except Exception as e:
            logger.error(f"数据预处理失败: {e}")
            return data



    def _calculate_parallel_efficiency(self, execution_time: float, data_size: int) -> float:
        """计算并行效率"""
        try:
            # 估算单线程执行时间
            estimated_single_thread_time = data_size / 10000  # 假设单线程处理10000点/秒

            # 理论最优时间
            theoretical_optimal_time = estimated_single_thread_time / \
                self.config["max_workers"]

            # 并行效率
            efficiency = theoretical_optimal_time / \
                execution_time if execution_time > 0 else 0

            return min(efficiency, 1.0)  # 效率不能超过100%

        except Exception:
            return 0.0

    def benchmark_performance(self, data_sizes: List[int] = None) -> Dict[str, Any]:
        """性能基准测试"""
        try:
            if data_sizes is None:
                data_sizes = [1000, 10000, 100000, 1000000]

            benchmark_results = {}

            for size in data_sizes:
                # 生成测试数据
                test_data = pd.DataFrame({
                    'close': np.random.randn(size).cumsum() + 100,
                    'signal': np.random.choice([-1, 0, 1], size)
                })

                # 测试不同后端
                for backend in ComputeBackend:
                    if backend == ComputeBackend.GPU and not self.gpu_available:
                        continue
                    if backend == ComputeBackend.DISTRIBUTED and not self.dask_client:
                        continue

                    original_backend = self.compute_backend
                    self.compute_backend = backend

                    try:
                        start_time = time.time()
                        result, metrics = self.optimize_backtest(test_data)

                        benchmark_results[f"{backend.value}_{size}"] = {
                            "execution_time": metrics.execution_time,
                            "throughput": metrics.throughput,
                            "memory_usage": metrics.memory_usage,
                            "parallel_efficiency": metrics.parallel_efficiency
                        }

                    except Exception as e:
                        benchmark_results[f"{backend.value}_{size}"] = {
                            "error": str(e)}

                    finally:
                        self.compute_backend = original_backend

            logger.error("性能基准测试完成")
            return benchmark_results

        except Exception as e:
            logger.info(f"性能基准测试失败: {e}")
            return {}

    def cleanup(self):
        """清理资源"""
        try:
            # 清理Dask客户端
            if self.dask_client:
                self.dask_client.close()
                self.dask_client = None

            # 清理Ray
            if self.ray_initialized:
                ray.shutdown()
                self.ray_initialized = False

            # 清理缓存
            with self._cache_lock:
                self.cache.clear()

            # 强制垃圾回收
            gc.collect()

            logger.info("资源清理完成")

        except Exception as e:
            logger.error(f"资源清理失败: {e}")

    def __del__(self):
        """析构函数"""
        try:
            self.cleanup()
        except Exception as e:
            logger.error(f"析构函数清理失败: {e}")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.cleanup()

# 便捷函数


def create_ultra_optimizer(
        performance_level: PerformanceLevel = PerformanceLevel.ULTRA,
        compute_backend: ComputeBackend = ComputeBackend.HYBRID) -> UltraPerformanceOptimizer:
    """创建超高性能优化器"""
    return UltraPerformanceOptimizer(performance_level, compute_backend)


def run_ultra_fast_backtest(
    data: pd.DataFrame,
    performance_level: PerformanceLevel = PerformanceLevel.ULTRA,
    **kwargs
) -> Tuple[pd.DataFrame, PerformanceMetrics]:
    """运行超高速回测"""
    optimizer = create_ultra_optimizer(performance_level)
    try:
        return optimizer.optimize_backtest(data, **kwargs)
    finally:
        optimizer.cleanup()


def benchmark_all_backends(
        data: pd.DataFrame) -> Dict[str, Any]:
    """基准测试所有后端"""
    optimizer = create_ultra_optimizer(
        PerformanceLevel.EXTREME, ComputeBackend.HYBRID)
    try:
        return optimizer.benchmark_performance([len(data)])
    finally:
        optimizer.cleanup()
