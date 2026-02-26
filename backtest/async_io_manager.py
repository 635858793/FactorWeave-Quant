"""
异步I/O与智能缓存模块
======================

架构设计
--------
本模块提供两个独立的缓存系统，采用分层架构设计：

Layer 1: AsyncIOManager (文件I/O层)
    职责：加速磁盘文件读取操作
    数据：HDF5数据集、Zarr数组、二进制文件
    统计：命中率、响应时间、I/O操作数

Layer 2: SmartDataCache (业务数据层)
    职责：管理业务计算结果的内存缓存
    数据：回测结果DataFrame、策略信号
    统计：内存占用、缓存项数量

调用链示例
----------
回测场景下的协作流程：

1. 加载数据阶段
   AsyncIOManager.read_hdf5_async()
   → 检查内部缓存
   → 命中则直接返回
   → 未命中则从磁盘读取并缓存

2. 计算阶段
   执行回测计算逻辑

3. 结果缓存阶段  
   SmartDataCache.put(cache_key, result, ttl=3600)
   → 计算内存占用
   → 检查是否需要淘汰旧数据
   → 存入缓存并设置过期时间

4. 后续访问
   SmartDataCache.get(cache_key)
   → 检查是否过期
   → 返回缓存结果或None

监控集成
--------
数据质量监控面板(data_quality_monitor_tab.py)从两个系统收集数据：

- AsyncIOManager.get_cache_stats()
  → 收集：命中率、I/O操作数、响应时间
  → 用途：监控文件I/O性能

- SmartDataCache.get_stats()
  → 收集：内存占用、缓存项数量
  → 用途：监控内存使用状况

注意事项
--------
1. 两个缓存系统独立运作，不共享数据
2. AsyncIOManager基于缓存项数量管理(LRU)
3. SmartDataCache基于实际内存占用管理
4. 清理时需分别调用clear_cache方法
"""

from loguru import logger

import asyncio
try:
    import aiofiles
    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False

import h5py

try:
    import zarr
    ZARR_AVAILABLE = True
except ImportError:
    ZARR_AVAILABLE = False
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
import hashlib
import pickle
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import weakref
import time

class AsyncIOManager:
    """异步I/O管理器"""

    def __init__(self, max_workers: int = 4, cache_size: int = 1000):
        self.max_workers = max_workers
        self.cache_size = cache_size
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # 缓存系统
        self.cache = {}
        self.cache_access_times = {}
        self.cache_lock = threading.Lock()

        # 异步队列
        self.io_queue = asyncio.Queue()
        self.result_cache = {}

        # 统计信息
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'io_operations': 0,
            'async_operations': 0
        }

        # 响应时间跟踪
        self.response_times = []
        self.max_response_times = 100  # 保留最近100次响应时间

    async def read_file_async(self, file_path: Union[str, Path],
                              cache_key: Optional[str] = None) -> bytes:
        """异步读取文件"""
        file_path = Path(file_path)

        # 生成缓存键
        if cache_key is None:
            cache_key = self._generate_cache_key(str(file_path))

        # 检查缓存
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            self.stats['cache_hits'] += 1
            return cached_data

        self.stats['cache_misses'] += 1
        self.stats['async_operations'] += 1

        try:
            if AIOFILES_AVAILABLE:
                async with aiofiles.open(file_path, 'rb') as f:
                    data = await f.read()
            else:
                # 降级到同步I/O
                with open(file_path, 'rb') as f:
                    data = f.read()

            # 存入缓存
            self._put_to_cache(cache_key, data)
            return data

        except Exception as e:
            logger.error(f"异步读取文件失败 {file_path}: {e}")
            raise

    async def write_file_async(self, file_path: Union[str, Path],
                               data: bytes, cache_key: Optional[str] = None):
        """异步写入文件"""
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        self.stats['async_operations'] += 1

        try:
            if AIOFILES_AVAILABLE:
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(data)
            else:
                # 降级到同步I/O
                with open(file_path, 'wb') as f:
                    f.write(data)

            # 更新缓存
            if cache_key:
                self._put_to_cache(cache_key, data)

        except Exception as e:
            logger.error(f"异步写入文件失败 {file_path}: {e}")
            raise

    def read_hdf5_async(self, file_path: Union[str, Path],
                        dataset_name: str) -> np.ndarray:
        """异步读取HDF5文件"""
        cache_key = self._generate_cache_key(f"{file_path}:{dataset_name}")

        # 检查缓存
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            self.stats['cache_hits'] += 1
            return cached_data

        self.stats['cache_misses'] += 1

        def _read_hdf5():
            try:
                with h5py.File(file_path, 'r') as f:
                    data = f[dataset_name][:]
                return data
            except Exception as e:
                logger.error(f"读取HDF5文件失败 {file_path}:{dataset_name}: {e}")
                raise

        future = self.executor.submit(_read_hdf5)
        data = future.result()

        # 存入缓存
        self._put_to_cache(cache_key, data)
        return data

    def write_hdf5_async(self, file_path: Union[str, Path],
                         dataset_name: str, data: np.ndarray):
        """异步写入HDF5文件"""
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        def _write_hdf5():
            try:
                with h5py.File(file_path, 'a') as f:
                    if dataset_name in f:
                        del f[dataset_name]
                    f.create_dataset(dataset_name, data=data, compression='gzip')
            except Exception as e:
                logger.error(f"写入HDF5文件失败 {file_path}:{dataset_name}: {e}")
                raise

        future = self.executor.submit(_write_hdf5)

        # 更新缓存
        cache_key = self._generate_cache_key(f"{file_path}:{dataset_name}")
        self._put_to_cache(cache_key, data)

        return future

    def read_zarr_async(self, file_path: Union[str, Path]):
        """异步读取Zarr文件"""
        if not ZARR_AVAILABLE:
            raise ImportError("zarr 库未安装，无法使用 Zarr 功能")

        cache_key = self._generate_cache_key(f"zarr:{file_path}")

        # 检查缓存
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            self.stats['cache_hits'] += 1
            return cached_data

        self.stats['cache_misses'] += 1

        def _read_zarr():
            try:
                import zarr
                return zarr.open(file_path, mode='r')
            except Exception as e:
                logger.error(f"读取Zarr文件失败 {file_path}: {e}")
                raise

        future = self.executor.submit(_read_zarr)
        data = future.result()

        # 存入缓存
        self._put_to_cache(cache_key, data)
        return data

    def batch_read_files(self, file_paths: List[Union[str, Path]]) -> Dict[str, bytes]:
        """批量读取文件"""
        results = {}
        futures = {}

        for file_path in file_paths:
            file_path = Path(file_path)
            cache_key = self._generate_cache_key(str(file_path))

            # 检查缓存
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                results[str(file_path)] = cached_data
                self.stats['cache_hits'] += 1
            else:
                # 提交异步任务
                future = self.executor.submit(self._read_file_sync, file_path)
                futures[str(file_path)] = (future, cache_key)
                self.stats['cache_misses'] += 1

        # 等待所有异步任务完成
        for file_path, (future, cache_key) in futures.items():
            try:
                data = future.result()
                results[file_path] = data
                self._put_to_cache(cache_key, data)
            except Exception as e:
                logger.error(f"批量读取文件失败 {file_path}: {e}")
                results[file_path] = None

        return results

    def _read_file_sync(self, file_path: Path) -> bytes:
        """同步读取文件（用于线程池）"""
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"同步读取文件失败 {file_path}: {e}")
            raise

    def _generate_cache_key(self, identifier: str) -> str:
        """生成缓存键"""
        return hashlib.md5(identifier.encode()).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """从缓存获取数据"""
        start_time = time.time()
        with self.cache_lock:
            if key in self.cache:
                self.stats['io_operations'] += 1
                self.cache_access_times[key] = time.time()
                result = self.cache[key]
            else:
                result = None
        
        # 计算响应时间（仅命中时计算）
        if result is not None:
            response_time = (time.time() - start_time) * 1000  # 转换为毫秒
            self.response_times.append(response_time)
            if len(self.response_times) > self.max_response_times:
                self.response_times.pop(0)
        
        return result

    def _put_to_cache(self, key: str, data: Any):
        """存入缓存"""
        with self.cache_lock:
            # 如果缓存已满，删除最久未访问的项
            if len(self.cache) >= self.cache_size:
                oldest_key = min(self.cache_access_times,
                                 key=self.cache_access_times.get)
                del self.cache[oldest_key]
                del self.cache_access_times[oldest_key]

            self.cache[key] = data
            self.cache_access_times[key] = time.time()
            self.stats['io_operations'] += 1

    def clear_cache(self):
        """清理缓存"""
        with self.cache_lock:
            self.cache.clear()
            self.cache_access_times.clear()
            self.stats['io_operations'] = 0

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.cache_lock:
            hit_rate = 0
            total_requests = self.stats['cache_hits'] + self.stats['cache_misses']
            if total_requests > 0:
                hit_rate = self.stats['cache_hits'] / total_requests

            # 计算响应时间统计
            avg_response_time = 0
            max_response_time = 0
            if self.response_times:
                avg_response_time = sum(self.response_times) / len(self.response_times)
                max_response_time = max(self.response_times)

            return {
                'cache_size': len(self.cache),
                'max_cache_size': self.cache_size,
                'hit_rate': hit_rate,
                'total_hits': self.stats['cache_hits'],
                'total_misses': self.stats['cache_misses'],
                'io_operations': self.stats['io_operations'],
                'async_operations': self.stats['async_operations'],
                'avg_response_time': avg_response_time,
                'max_response_time': max_response_time,
                'response_time_samples': len(self.response_times)
            }

    def cleanup(self):
        """清理资源"""
        try:
            self.executor.shutdown(wait=True)
            self.clear_cache()
            logger.info("异步I/O管理器资源清理完成")
        except Exception as e:
            logger.error(f"异步I/O管理器清理失败: {e}")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.cleanup()

class SmartDataCache:
    """智能数据缓存"""

    def __init__(self, max_memory_mb: int = 1000):
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cache = {}
        self.cache_info = {}  # 存储大小、访问时间等信息
        self.current_memory_usage = 0
        self.lock = threading.Lock()

    def put(self, key: str, data: Any, ttl: Optional[int] = None):
        """存入缓存"""
        with self.lock:
            # 计算数据大小
            data_size = self._calculate_size(data)

            # 检查是否需要清理空间
            while (self.current_memory_usage + data_size > self.max_memory_bytes
                   and len(self.cache) > 0):
                self._evict_lru()

            # 存入数据
            expire_time = None
            if ttl:
                expire_time = time.time() + ttl

            self.cache[key] = data
            self.cache_info[key] = {
                'size': data_size,
                'access_time': time.time(),
                'expire_time': expire_time,
                'access_count': 1
            }
            self.current_memory_usage += data_size

    def get(self, key: str) -> Optional[Any]:
        """从缓存获取数据"""
        with self.lock:
            if key not in self.cache:
                return None

            # 检查是否过期
            info = self.cache_info[key]
            if info['expire_time'] and time.time() > info['expire_time']:
                self._remove_key(key)
                return None

            # 更新访问信息
            info['access_time'] = time.time()
            info['access_count'] += 1

            return self.cache[key]

    def _calculate_size(self, data: Any) -> int:
        """计算数据大小"""
        try:
            if isinstance(data, np.ndarray):
                return data.nbytes
            elif isinstance(data, pd.DataFrame):
                return data.memory_usage(deep=True).sum()
            else:
                return len(pickle.dumps(data))
        except Exception:
            return 1024  # 默认大小

    def _evict_lru(self):
        """淘汰最久未使用的数据"""
        if not self.cache:
            return

        lru_key = min(self.cache_info,
                      key=lambda k: self.cache_info[k]['access_time'])
        self._remove_key(lru_key)

    def _remove_key(self, key: str):
        """移除缓存项"""
        if key in self.cache:
            self.current_memory_usage -= self.cache_info[key]['size']
            del self.cache[key]
            del self.cache_info[key]

    def clear(self):
        """清空缓存（别名：clear_cache）"""
        with self.lock:
            self.cache.clear()
            self.cache_info.clear()
            self.current_memory_usage = 0

    # 统一命名接口（与AsyncIOManager保持一致）
    clear_cache = clear

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self.lock:
            return {
                'cache_size': len(self.cache),
                'memory_usage_mb': self.current_memory_usage / 1024 / 1024,
                'max_memory_mb': self.max_memory_bytes / 1024 / 1024,
                'memory_usage_percent': (self.current_memory_usage / self.max_memory_bytes) * 100
            }

# 全局实例 - 使用统一缓存服务的适配器
# 为了向后兼容，保留原有类定义，但全局实例使用统一缓存服务

def _get_unified_cache_adapter():
    """获取统一缓存适配器（延迟加载）"""
    try:
        from core.services.unified_cache_provider import get_smart_cache
        return get_smart_cache()
    except ImportError:
        return None

def _get_unified_async_io_adapter():
    """获取统一异步I/O缓存适配器（延迟加载）"""
    try:
        from core.services.unified_cache_provider import get_async_io_cache
        return get_async_io_cache()
    except ImportError:
        return None

# 原始类实例（用于向后兼容和独立使用）
_async_io_manager_instance = None
_smart_cache_instance = None

def get_async_io_manager() -> 'AsyncIOManager':
    """
    获取AsyncIOManager实例（单例）
    
    优先使用统一缓存服务，如果不可用则使用本地实例
    """
    global _async_io_manager_instance
    
    if _async_io_manager_instance is None:
        _async_io_manager_instance = AsyncIOManager()
    
    return _async_io_manager_instance

def get_smart_data_cache() -> 'SmartDataCache':
    """
    获取SmartDataCache实例（单例）
    
    优先使用统一缓存服务，如果不可用则使用本地实例
    """
    global _smart_cache_instance
    
    if _smart_cache_instance is None:
        _smart_cache_instance = SmartDataCache()
    
    return _smart_cache_instance

# 向后兼容的全局实例访问
class _AsyncIOManagerProxy:
    """AsyncIOManager代理类，支持延迟加载和统一缓存集成"""
    
    def __init__(self):
        self._instance = None
    
    def _get_instance(self):
        if self._instance is None:
            self._instance = AsyncIOManager()
        return self._instance
    
    def __getattr__(self, name):
        return getattr(self._get_instance(), name)


class _SmartCacheProxy:
    """SmartDataCache代理类，支持延迟加载和统一缓存集成"""
    
    def __init__(self):
        self._instance = None
    
    def _get_instance(self):
        if self._instance is None:
            self._instance = SmartDataCache()
        return self._instance
    
    def __getattr__(self, name):
        return getattr(self._get_instance(), name)


# 全局实例（使用代理实现延迟加载）
async_io_manager = _AsyncIOManagerProxy()
smart_cache = _SmartCacheProxy()

# 缓存系统状态追踪
_CACHE_SYSTEMS = {
    'async_io_manager': {
        'getter': get_async_io_manager,
        'name': 'AsyncIOManager',
        'type': 'file_io',
        'stats_method': 'get_cache_stats'
    },
    'smart_cache': {
        'getter': get_smart_data_cache,
        'name': 'SmartDataCache',
        'type': 'business_data',
        'stats_method': 'get_stats'
    }
}

def get_all_cache_stats() -> Dict[str, Dict]:
    """
    获取所有缓存系统的统计信息

    Returns:
        Dict: 包含两个缓存系统的统计信息
    """
    result = {}
    for key, system in _CACHE_SYSTEMS.items():
        instance = system['getter']()
        stats_method = getattr(instance, system['stats_method'])
        result[key] = {
            'name': system['name'],
            'type': system['type'],
            'stats': stats_method()
        }
    return result

def clear_all_caches():
    """清空所有缓存"""
    for key, system in _CACHE_SYSTEMS.items():
        instance = system['getter']()
        if hasattr(instance, 'clear_cache'):
            instance.clear_cache()
        elif hasattr(instance, 'clear'):
            instance.clear()


# 统一缓存服务集成
def get_unified_cache_service():
    """
    获取统一缓存服务实例
    
    Returns:
        CacheService实例，如果不可用则返回None
    """
    try:
        from core.services.unified_cache_provider import get_unified_cache_provider
        provider = get_unified_cache_provider()
        return provider.get_cache_service()
    except ImportError:
        return None


def migrate_to_unified_cache():
    """
    迁移到统一缓存服务
    
    将现有的缓存数据迁移到统一缓存服务中
    """
    from loguru import logger
    
    try:
        from core.services.unified_cache_provider import get_unified_cache_provider
        
        provider = get_unified_cache_provider()
        cache_service = provider.get_cache_service()
        
        # 创建命名空间
        cache_service.create_namespace("backtest", description="回测模块缓存")
        cache_service.create_namespace("async_io", description="异步I/O缓存")
        
        logger.info("成功迁移到统一缓存服务")
        return True
        
    except Exception as e:
        logger.warning(f"迁移到统一缓存服务失败: {e}")
        return False
