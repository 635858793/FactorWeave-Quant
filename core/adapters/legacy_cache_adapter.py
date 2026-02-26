"""
遗留缓存适配器模块

为现有缓存实现提供适配器，使其可以透明地使用统一的CacheService。
支持平滑迁移，保持向后兼容性。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from datetime import timedelta
import threading
import time

from loguru import logger

from core.services.cache_service import CacheService


class LegacyCacheAdapter(ABC):
    """
    遗留缓存适配器基类
    
    提供统一的适配器接口，将遗留缓存实现桥接到CacheService。
    """

    def __init__(self, cache_service: CacheService, namespace: str):
        """
        初始化适配器
        
        Args:
            cache_service: 统一缓存服务实例
            namespace: 命名空间（用于隔离不同模块的缓存）
        """
        self._cache_service = cache_service
        self._namespace = namespace
        self._lock = threading.RLock()
        
        if not self._cache_service:
            raise ValueError("CacheService instance is required")
        
        if not self._namespace:
            raise ValueError("Namespace is required")

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        pass

    @abstractmethod
    def put(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值"""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除缓存值"""
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空缓存"""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        pass


class SmartDataCacheAdapter(LegacyCacheAdapter):
    """
    SmartDataCache适配器
    
    将SmartDataCache接口适配到CacheService。
    保持与原SmartDataCache完全兼容的接口。
    """

    def __init__(self, cache_service: CacheService, 
                 namespace: str = "backtest",
                 max_memory_mb: int = 1000):
        """
        初始化SmartDataCache适配器
        
        Args:
            cache_service: 统一缓存服务实例
            namespace: 命名空间（默认backtest）
            max_memory_mb: 最大内存（MB），用于兼容性，实际由CacheService管理
        """
        super().__init__(cache_service, namespace)
        self._max_memory_mb = max_memory_mb
        self._stats = {
            'hits': 0,
            'misses': 0,
            'puts': 0,
            'deletes': 0
        }

    def get(self, key: str) -> Optional[Any]:
        """
        从缓存获取数据
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值或None
        """
        with self._lock:
            value = self._cache_service.get(key, namespace=self._namespace)
            
            if value is not None:
                self._stats['hits'] += 1
            else:
                self._stats['misses'] += 1
            
            return value

    def put(self, key: str, data: Any, ttl: Optional[int] = None):
        """
        存入缓存
        
        Args:
            key: 缓存键
            data: 缓存数据
            ttl: 过期时间（秒）
        """
        with self._lock:
            ttl_delta = timedelta(seconds=ttl) if ttl else None
            
            self._cache_service.set(
                key, data, 
                ttl=ttl_delta, 
                namespace=self._namespace,
                group="smart_cache"
            )
            self._stats['puts'] += 1

    def delete(self, key: str) -> bool:
        """
        删除缓存项
        
        Args:
            key: 缓存键
            
        Returns:
            是否删除成功
        """
        with self._lock:
            result = self._cache_service.delete(key, namespace=self._namespace)
            if result:
                self._stats['deletes'] += 1
            return result

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache_service.clear_namespace(self._namespace)
            self._stats = {'hits': 0, 'misses': 0, 'puts': 0, 'deletes': 0}

    clear_cache = clear

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计
        
        Returns:
            统计信息字典
        """
        with self._lock:
            ns_stats = self._cache_service.get_namespace_stats(self._namespace)
            
            return {
                'cache_size': ns_stats.get('key_count', 0),
                'memory_usage_mb': 0,
                'max_memory_mb': self._max_memory_mb,
                'memory_usage_percent': 0,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'puts': self._stats['puts'],
                'deletes': self._stats['deletes'],
                'hit_rate': self._stats['hits'] / (self._stats['hits'] + self._stats['misses']) 
                    if (self._stats['hits'] + self._stats['misses']) > 0 else 0
            }


class StrategyCacheAdapter(LegacyCacheAdapter):
    """
    StrategyCache适配器
    
    将StrategyCache接口适配到CacheService。
    支持策略分组和优先级管理。
    """

    def __init__(self, cache_service: CacheService,
                 namespace: str = "strategy",
                 max_size: int = 1000,
                 ttl_seconds: int = 3600):
        """
        初始化StrategyCache适配器
        
        Args:
            cache_service: 统一缓存服务实例
            namespace: 命名空间（默认strategy）
            max_size: 最大缓存条目数（兼容性）
            ttl_seconds: 默认TTL（秒）
        """
        super().__init__(cache_service, namespace)
        self._max_size = max_size
        self._default_ttl = ttl_seconds
        self._strategy_groups: Dict[str, List[str]] = {}
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            value = self._cache_service.get(key, namespace=self._namespace)
            
            if value is not None:
                self._stats['hits'] += 1
            else:
                self._stats['misses'] += 1
            
            return value

    def put(self, key: str, value: Any, ttl: Optional[int] = None,
            strategy_name: str = None, priority: int = 5) -> None:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
            strategy_name: 策略名称（用于分组）
            priority: 优先级（0-10）
        """
        with self._lock:
            ttl_delta = timedelta(seconds=ttl or self._default_ttl)
            group = strategy_name if strategy_name else None
            
            self._cache_service.set(
                key, value,
                ttl=ttl_delta,
                namespace=self._namespace,
                group=group,
                priority=priority
            )
            
            if strategy_name:
                if strategy_name not in self._strategy_groups:
                    self._strategy_groups[strategy_name] = []
                if key not in self._strategy_groups[strategy_name]:
                    self._strategy_groups[strategy_name].append(key)

    def delete(self, key: str) -> bool:
        """删除缓存值"""
        with self._lock:
            return self._cache_service.delete(key, namespace=self._namespace)

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache_service.clear_namespace(self._namespace)
            self._strategy_groups.clear()
            self._stats = {'hits': 0, 'misses': 0, 'evictions': 0}

    def clear_strategy(self, strategy_name: str) -> int:
        """
        清空指定策略的缓存
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            清除的条目数
        """
        with self._lock:
            return self._cache_service.clear_group(self._namespace, strategy_name)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            ns_stats = self._cache_service.get_namespace_stats(self._namespace)
            
            return {
                'cache_size': ns_stats.get('key_count', 0),
                'max_size': self._max_size,
                'strategy_count': len(self._strategy_groups),
                'strategies': list(self._strategy_groups.keys()),
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'evictions': self._stats['evictions'],
                'hit_rate': self._stats['hits'] / (self._stats['hits'] + self._stats['misses'])
                    if (self._stats['hits'] + self._stats['misses']) > 0 else 0
            }

    def get_strategy_stats(self, strategy_name: str) -> Dict[str, Any]:
        """
        获取指定策略的统计信息
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            统计信息
        """
        with self._lock:
            group_data = self._cache_service.get_by_group(self._namespace, strategy_name)
            
            return {
                'strategy_name': strategy_name,
                'key_count': len(group_data),
                'keys': list(group_data.keys())
            }


class AsyncIOManagerAdapter:
    """
    AsyncIOManager适配器
    
    为AsyncIOManager提供缓存相关的适配。
    主要适配HDF5异步读写功能，缓存部分使用CacheService。
    """

    def __init__(self, cache_service: CacheService,
                 namespace: str = "async_io"):
        """
        初始化AsyncIOManager适配器
        
        Args:
            cache_service: 统一缓存服务实例
            namespace: 命名空间
        """
        self._cache_service = cache_service
        self._namespace = namespace
        self._lock = threading.RLock()
        self._stats = {
            'reads': 0,
            'writes': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }

    def get_cached_data(self, key: str) -> Optional[Any]:
        """
        获取缓存数据
        
        Args:
            key: 缓存键
            
        Returns:
            缓存数据或None
        """
        with self._lock:
            value = self._cache_service.get(key, namespace=self._namespace)
            
            if value is not None:
                self._stats['cache_hits'] += 1
            else:
                self._stats['cache_misses'] += 1
            
            return value

    def cache_data(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """
        缓存数据
        
        Args:
            key: 缓存键
            data: 数据
            ttl: 过期时间（秒）
        """
        with self._lock:
            ttl_delta = timedelta(seconds=ttl) if ttl else None
            
            self._cache_service.set(
                key, data,
                ttl=ttl_delta,
                namespace=self._namespace,
                group="async_io_cache"
            )
            self._stats['writes'] += 1

    def invalidate_cache(self, key: str) -> bool:
        """
        使缓存失效
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功
        """
        with self._lock:
            return self._cache_service.delete(key, namespace=self._namespace)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            ns_stats = self._cache_service.get_namespace_stats(self._namespace)
            
            return {
                'cache_size': ns_stats.get('key_count', 0),
                'reads': self._stats['reads'],
                'writes': self._stats['writes'],
                'cache_hits': self._stats['cache_hits'],
                'cache_misses': self._stats['cache_misses'],
                'hit_rate': self._stats['cache_hits'] / (self._stats['cache_hits'] + self._stats['cache_misses'])
                    if (self._stats['cache_hits'] + self._stats['cache_misses']) > 0 else 0
            }

    def read_hdf5_async(self, file_path, dataset_name):
        """
        异步读取HDF5文件
        
        Args:
            file_path: 文件路径
            dataset_name: 数据集名称
            
        Returns:
            numpy数组
        """
        import hashlib
        from pathlib import Path
        
        cache_key = hashlib.md5(f"{file_path}:{dataset_name}".encode()).hexdigest()
        
        cached_data = self.get_cached_data(cache_key)
        if cached_data is not None:
            return cached_data
        
        try:
            import h5py
            import numpy as np
            
            with h5py.File(file_path, 'r') as f:
                data = f[dataset_name][:]
            
            self.cache_data(cache_key, data, ttl=3600)
            self._stats['reads'] += 1
            return data
            
        except Exception as e:
            logger.error(f"读取HDF5文件失败 {file_path}: {e}")
            raise

    def write_hdf5_async(self, file_path, dataset_name, data):
        """
        异步写入HDF5文件
        
        Args:
            file_path: 文件路径
            dataset_name: 数据集名称
            data: 数据
            
        Returns:
            Future对象
        """
        from concurrent.futures import Future
        from pathlib import Path
        import hashlib
        
        def _write():
            try:
                import h5py
                
                Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                
                with h5py.File(file_path, 'a') as f:
                    if dataset_name in f:
                        del f[dataset_name]
                    f.create_dataset(dataset_name, data=data)
                
                cache_key = hashlib.md5(f"{file_path}:{dataset_name}".encode()).hexdigest()
                self.cache_data(cache_key, data, ttl=3600)
                self._stats['writes'] += 1
                
                return True
                
            except Exception as e:
                logger.error(f"写入HDF5文件失败 {file_path}: {e}")
                raise
        
        future = Future()
        try:
            result = _write()
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        
        return future


def create_smart_cache_adapter(cache_service: CacheService, 
                                namespace: str = "backtest",
                                **kwargs) -> SmartDataCacheAdapter:
    """
    创建SmartDataCache适配器的工厂函数
    
    Args:
        cache_service: 统一缓存服务实例
        namespace: 命名空间
        **kwargs: 额外参数
        
    Returns:
        SmartDataCacheAdapter实例
    """
    return SmartDataCacheAdapter(cache_service, namespace, **kwargs)


def create_strategy_cache_adapter(cache_service: CacheService,
                                   namespace: str = "strategy",
                                   **kwargs) -> StrategyCacheAdapter:
    """
    创建StrategyCache适配器的工厂函数
    
    Args:
        cache_service: 统一缓存服务实例
        namespace: 命名空间
        **kwargs: 额外参数
        
    Returns:
        StrategyCacheAdapter实例
    """
    return StrategyCacheAdapter(cache_service, namespace, **kwargs)


def create_async_io_adapter(cache_service: CacheService,
                             namespace: str = "async_io",
                             **kwargs) -> AsyncIOManagerAdapter:
    """
    创建AsyncIOManager适配器的工厂函数
    
    Args:
        cache_service: 统一缓存服务实例
        namespace: 命名空间
        **kwargs: 额外参数
        
    Returns:
        AsyncIOManagerAdapter实例
    """
    return AsyncIOManagerAdapter(cache_service, namespace, **kwargs)
