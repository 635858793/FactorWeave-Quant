"""
统一缓存接口定义

本模块定义了FactorWeave-Quant系统中缓存组件的统一接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from enum import Enum


class CacheLevel(Enum):
    """缓存级别枚举"""
    L1_MEMORY = "l1_memory"
    L2_REDIS = "l2_redis"
    L3_DISK = "l3_disk"


@dataclass
class CacheConfig:
    """缓存配置"""

    # 基础配置
    max_size: int = 1000
    default_ttl: int = 300  # 默认TTL(秒)

    # 淘汰策略
    eviction_policy: str = "lru"  # lru, lfu, fifo

    # 序列化配置
    serializer: str = "pickle"  # pickle, json, msgpack
    compression: bool = False

    # 性能配置
    async_write: bool = True
    batch_size: int = 100

    # 扩展配置
    extra_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheStats:
    """缓存统计信息"""

    # 基础统计
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0

    # 容量统计
    current_size: int = 0
    max_size: int = 0

    # 性能统计
    avg_get_time: float = 0.0
    avg_set_time: float = 0.0

    # 时间统计
    start_time: datetime = field(default_factory=datetime.now)
    last_reset_time: datetime = field(default_factory=datetime.now)

    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def usage_rate(self) -> float:
        """使用率"""
        return self.current_size / self.max_size if self.max_size > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        from dataclasses import asdict
        result = asdict(self)
        result['hit_rate'] = self.hit_rate
        result['usage_rate'] = self.usage_rate
        result['start_time'] = self.start_time.isoformat()
        result['last_reset_time'] = self.last_reset_time.isoformat()
        return result


class ICache(ABC):
    """统一缓存接口"""

    @property
    @abstractmethod
    def level(self) -> CacheLevel:
        """缓存级别"""
        pass

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值

        Args:
            key: 缓存键

        Returns:
            Optional[Any]: 缓存值，不存在时返回None
        """
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 生存时间(秒)，None使用默认TTL

        Returns:
            bool: 设置是否成功
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除缓存

        Args:
            key: 缓存键

        Returns:
            bool: 删除是否成功
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在

        Args:
            key: 缓存键

        Returns:
            bool: 是否存在
        """
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """清空缓存

        Returns:
            bool: 清空是否成功
        """
        pass

    @abstractmethod
    async def get_stats(self) -> CacheStats:
        """获取缓存统计信息

        Returns:
            CacheStats: 统计信息
        """
        pass

    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存值

        Args:
            keys: 缓存键列表

        Returns:
            Dict[str, Any]: 键值对字典
        """
        result = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        return result

    async def set_many(self, items: Dict[str, Any], ttl: Optional[int] = None) -> int:
        """批量设置缓存值

        Args:
            items: 键值对字典
            ttl: 生存时间(秒)

        Returns:
            int: 成功设置的数量
        """
        success_count = 0
        for key, value in items.items():
            if await self.set(key, value, ttl):
                success_count += 1
        return success_count

    async def delete_many(self, keys: List[str]) -> int:
        """批量删除缓存

        Args:
            keys: 缓存键列表

        Returns:
            int: 成功删除的数量
        """
        success_count = 0
        for key in keys:
            if await self.delete(key):
                success_count += 1
        return success_count

    async def get_ttl(self, key: str) -> Optional[int]:
        """获取缓存TTL

        Args:
            key: 缓存键

        Returns:
            Optional[int]: TTL(秒)，不存在或永久缓存时返回None
        """
        # 默认实现，子类可以重写
        return None

    async def expire(self, key: str, ttl: int) -> bool:
        """设置缓存过期时间

        Args:
            key: 缓存键
            ttl: 生存时间(秒)

        Returns:
            bool: 设置是否成功
        """
        # 默认实现，子类可以重写
        value = await self.get(key)
        if value is not None:
            return await self.set(key, value, ttl)
        return False


class CacheError(Exception):
    """缓存异常基类"""

    def __init__(self, message: str, cache_level: Optional[CacheLevel] = None):
        super().__init__(message)
        self.message = message
        self.cache_level = cache_level


class CacheConnectionError(CacheError):
    """缓存连接异常"""
    pass


class CacheSerializationError(CacheError):
    """缓存序列化异常"""
    pass


class CacheCapacityError(CacheError):
    """缓存容量异常"""
    pass
