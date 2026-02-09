"""
遗留缓存适配器
将utils.cache.Cache包装为符合ICache接口的实现，用于渐进式迁移，避免破坏现有代码
"""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from core.interfaces.cache import ICache, CacheLevel, CacheStats, CacheError


class LegacyCacheAdapter(ICache):
    """
    遗留缓存适配器
    
    将utils.cache.Cache包装为符合ICache接口的实现
    支持同步和异步操作
    """
    
    def __init__(self, legacy_cache, level: CacheLevel = CacheLevel.L3_DISK):
        """
        初始化适配器
        
        Args:
            legacy_cache: utils.cache.Cache实例
            level: 缓存级别
        """
        self._legacy_cache = legacy_cache
        self._level = level
        self._stats = CacheStats(
            max_size=legacy_cache.get_size() if hasattr(legacy_cache, 'get_size') else 1000
        )
        
    @property
    def level(self) -> CacheLevel:
        """缓存级别"""
        return self._level
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            value = self._legacy_cache.get(key)
            if value is not None:
                self._stats.hits += 1
            else:
                self._stats.misses += 1
            return value
        except Exception as e:
            raise CacheError(f"Failed to get cache value: {e}", self._level)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        try:
            self._legacy_cache.set(key, value, ttl)
            self._stats.sets += 1
            self._stats.current_size = self._legacy_cache.get_size()
            return True
        except Exception as e:
            raise CacheError(f"Failed to set cache value: {e}", self._level)
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            self._legacy_cache.delete(key)
            self._stats.deletes += 1
            self._stats.current_size = self._legacy_cache.get_size()
            return True
        except Exception as e:
            raise CacheError(f"Failed to delete cache value: {e}", self._level)
    
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            return self._legacy_cache.exists(key)
        except Exception as e:
            raise CacheError(f"Failed to check cache existence: {e}", self._level)
    
    async def clear(self) -> bool:
        """清空缓存"""
        try:
            self._legacy_cache.clear()
            self._stats.current_size = 0
            return True
        except Exception as e:
            raise CacheError(f"Failed to clear cache: {e}", self._level)
    
    async def get_stats(self) -> CacheStats:
        """获取缓存统计信息"""
        try:
            legacy_stats = self._legacy_cache.get_stats()
            
            # 处理diskcache.stats()返回的tuple (hits, misses)
            hits = self._stats.hits
            misses = self._stats.misses
            size = self._stats.current_size
            
            if isinstance(legacy_stats, dict):
                hits = legacy_stats.get('hits', hits)
                misses = legacy_stats.get('misses', misses)
                size = legacy_stats.get('size', size)
            elif isinstance(legacy_stats, tuple) and len(legacy_stats) >= 2:
                # diskcache.stats()返回 (hits, misses)
                hits = legacy_stats[0]
                misses = legacy_stats[1]
                size = self._legacy_cache.get_size()
            
            stats = CacheStats(
                hits=hits,
                misses=misses,
                sets=self._stats.sets,
                deletes=self._stats.deletes,
                current_size=size,
                max_size=self._stats.max_size,
                start_time=self._stats.start_time,
                last_reset_time=self._stats.last_reset_time
            )
            
            return stats
        except Exception as e:
            raise CacheError(f"Failed to get cache stats: {e}", self._level)
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存值"""
        try:
            result = {}
            for key in keys:
                value = self._legacy_cache.get(key)
                if value is not None:
                    result[key] = value
                    self._stats.hits += 1
                else:
                    self._stats.misses += 1
            return result
        except Exception as e:
            raise CacheError(f"Failed to get multiple cache values: {e}", self._level)
    
    async def set_many(self, items: Dict[str, Any], ttl: Optional[int] = None) -> int:
        """批量设置缓存值"""
        try:
            success_count = 0
            for key, value in items.items():
                self._legacy_cache.set(key, value, ttl)
                success_count += 1
                self._stats.sets += 1
            self._stats.current_size = self._legacy_cache.get_size()
            return success_count
        except Exception as e:
            raise CacheError(f"Failed to set multiple cache values: {e}", self._level)
    
    async def delete_many(self, keys: List[str]) -> int:
        """批量删除缓存"""
        try:
            success_count = 0
            for key in keys:
                self._legacy_cache.delete(key)
                success_count += 1
                self._stats.deletes += 1
            self._stats.current_size = self._legacy_cache.get_size()
            return success_count
        except Exception as e:
            raise CacheError(f"Failed to delete multiple cache values: {e}", self._level)
    
    async def get_ttl(self, key: str) -> Optional[int]:
        """获取缓存TTL"""
        try:
            if hasattr(self._legacy_cache, 'get_ttl'):
                return self._legacy_cache.get_ttl(key)
            return None
        except Exception as e:
            raise CacheError(f"Failed to get cache TTL: {e}", self._level)
    
    async def expire(self, key: str, ttl: int) -> bool:
        """设置缓存过期时间"""
        try:
            if hasattr(self._legacy_cache, 'expire'):
                self._legacy_cache.expire(key, ttl)
                return True
            else:
                value = self._legacy_cache.get(key)
                if value is not None:
                    self._legacy_cache.set(key, value, ttl)
                    return True
            return False
        except Exception as e:
            raise CacheError(f"Failed to set cache expire: {e}", self._level)


class AsyncLegacyCacheAdapter(ICache):
    """
    异步遗留缓存适配器
    
    将utils.cache.Cache包装为符合ICache接口的实现
    支持异步操作
    """
    
    def __init__(self, legacy_cache, level: CacheLevel = CacheLevel.L3_DISK):
        """
        初始化适配器
        
        Args:
            legacy_cache: utils.cache.Cache实例（异步模式）
            level: 缓存级别
        """
        self._legacy_cache = legacy_cache
        self._level = level
        self._stats = CacheStats(
            max_size=legacy_cache.get_size() if hasattr(legacy_cache, 'get_size') else 1000
        )
        
    @property
    def level(self) -> CacheLevel:
        """缓存级别"""
        return self._level
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            value = await self._legacy_cache.get_async(key)
            if value is not None:
                self._stats.hits += 1
            else:
                self._stats.misses += 1
            return value
        except Exception as e:
            raise CacheError(f"Failed to get cache value: {e}", self._level)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        try:
            await self._legacy_cache.set_async(key, value, ttl)
            self._stats.sets += 1
            self._stats.current_size = await self._get_size_async()
            return True
        except Exception as e:
            raise CacheError(f"Failed to set cache value: {e}", self._level)
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            self._legacy_cache.delete(key)
            self._stats.deletes += 1
            self._stats.current_size = await self._get_size_async()
            return True
        except Exception as e:
            raise CacheError(f"Failed to delete cache value: {e}", self._level)
    
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            return self._legacy_cache.exists(key)
        except Exception as e:
            raise CacheError(f"Failed to check cache existence: {e}", self._level)
    
    async def clear(self) -> bool:
        """清空缓存"""
        try:
            self._legacy_cache.clear()
            self._stats.current_size = 0
            return True
        except Exception as e:
            raise CacheError(f"Failed to clear cache: {e}", self._level)
    
    async def get_stats(self) -> CacheStats:
        """获取缓存统计信息"""
        try:
            legacy_stats = self._legacy_cache.get_stats()
            
            # 处理diskcache.stats()返回的tuple (hits, misses)
            hits = self._stats.hits
            misses = self._stats.misses
            size = self._stats.current_size
            
            if isinstance(legacy_stats, dict):
                hits = legacy_stats.get('hits', hits)
                misses = legacy_stats.get('misses', misses)
                size = legacy_stats.get('size', size)
            elif isinstance(legacy_stats, tuple) and len(legacy_stats) >= 2:
                # diskcache.stats()返回 (hits, misses)
                hits = legacy_stats[0]
                misses = legacy_stats[1]
                size = await self._get_size_async()
            
            stats = CacheStats(
                hits=hits,
                misses=misses,
                sets=self._stats.sets,
                deletes=self._stats.deletes,
                current_size=size,
                max_size=self._stats.max_size,
                start_time=self._stats.start_time,
                last_reset_time=self._stats.last_reset_time
            )
            
            return stats
        except Exception as e:
            raise CacheError(f"Failed to get cache stats: {e}", self._level)
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存值"""
        try:
            result = {}
            for key in keys:
                value = await self._legacy_cache.get_async(key)
                if value is not None:
                    result[key] = value
                    self._stats.hits +=1
                else:
                    self._stats.misses += 1
            return result
        except Exception as e:
            raise CacheError(f"Failed to get multiple cache values: {e}", self._level)
    
    async def set_many(self, items: Dict[str, Any], ttl: Optional[int] = None) -> int:
        """批量设置缓存值"""
        try:
            success_count = 0
            for key, value in items.items():
                await self._legacy_cache.set_async(key, value, ttl)
                success_count += 1
                self._stats.sets += 1
            self._stats.current_size = await self._get_size_async()
            return success_count
        except Exception as e:
            raise CacheError(f"Failed to set multiple cache values: {e}", self._level)
    
    async def delete_many(self, keys: List[str]) -> int:
        """批量删除缓存"""
        try:
            success_count = 0
            for key in keys:
                self._legacy_cache.delete(key)
                success_count += 1
                self._stats.deletes += 1
                self._stats.current_size = await self._get_size_async()
            return success_count
        except Exception as e:
            raise CacheError(f"Failed to delete multiple cache values: {e}", self._level)
    
    async def get_ttl(self, key: str) -> Optional[int]:
        """获取缓存TTL"""
        try:
            if hasattr(self._legacy_cache, 'get_ttl'):
                return self._legacy_cache.get_ttl(key)
            return None
        except Exception as e:
            raise CacheError(f"Failed to get cache TTL: {e}", self._level)
    
    async def expire(self, key: str, ttl: int) -> bool:
        """设置缓存过期时间"""
        try:
            if hasattr(self._legacy_cache, 'expire'):
                self._legacy_cache.expire(key, ttl)
                return True
            else:
                value = await self._legacy_cache.get_async(key)
                if value is not None:
                    await self._legacy_cache.set_async(key, value, ttl)
                    return True
            return False
        except Exception as e:
            raise CacheError(f"Failed to set cache expire: {e}", self._level)
    
    async def _get_size_async(self) -> int:
        """异步获取缓存大小"""
        try:
            if hasattr(self._legacy_cache, 'get_size'):
                return self._legacy_cache.get_size()
            return 0
        except Exception:
            return 0


def create_legacy_cache_adapter(legacy_cache, async_mode: bool = False, 
                                level: CacheLevel = CacheLevel.L3_DISK) -> ICache:
    """
    创建遗留缓存适配器
    
    Args:
        legacy_cache: utils.cache.Cache实例
        async_mode: 是否为异步模式
        level: 缓存级别
    
    Returns:
        ICache: 缓存适配器实例
    """
    if async_mode:
        return AsyncLegacyCacheAdapter(legacy_cache, level)
    else:
        return LegacyCacheAdapter(legacy_cache, level)
