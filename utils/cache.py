"""
统一缓存模块（支持本地/分布式/异步）
"""
from typing import Any, Dict, Optional, Union
import threading
from loguru import logger

# 本地缓存（多进程多线程安全）
try:
    import diskcache
    DISKCACHE_AVAILABLE = True
except ImportError:
    diskcache = None
    DISKCACHE_AVAILABLE = False

# 分布式缓存（同步/异步均官方支持）- 使用惰性导入避免启动延迟
# 注意：redis 导入会导致长时间的 DNS 解析延迟，因此我们延迟导入
redis = None
aioredis = None
REDIS_AVAILABLE = False

def _ensure_redis_imported():
    """确保 redis 已导入（惰性导入）"""
    global redis, aioredis, REDIS_AVAILABLE
    if REDIS_AVAILABLE:
        return True
    try:
        import redis
        import redis.asyncio as aioredis
        REDIS_AVAILABLE = True
        return True
    except ImportError:
        REDIS_AVAILABLE = False
        return False


class Cache:
    """
    统一缓存类，支持本地/分布式/异步
    - 默认本地模式(diskcache)，多进程多线程安全，适合绝大多数桌面/服务端场景。
    - 分布式(redis)和异步(redis.asyncio)可选，适合大规模分布式部署。
    backend: "diskcache"（默认）或 "redis"
    async_mode: 是否异步（仅redis/aioredis支持）
    """

    def __init__(self, cache_dir: str = ".cache", size_limit: int = 1024*1024*1024,
                 default_ttl: int = 1800, backend: str = "diskcache",
                 redis_url: str = "redis://localhost:6379/0", async_mode: bool = False):
        # 确保default_ttl是有效的数值
        if not isinstance(default_ttl, (int, float)):
            logger.warning(f"Invalid default_ttl type: {type(default_ttl)}, using 1800")
            default_ttl = 1800

        self._default_ttl = default_ttl
        self._backend = backend
        self._async_mode = async_mode
        self._lock = threading.Lock()
        self._memory_cache = False
        if backend == "diskcache":
            if not DISKCACHE_AVAILABLE:
                # 使用内存缓存作为回退
                logger.warning("WARNING: diskcache 不可用，使用内存缓存")
                self.cache = {}
                self._memory_cache = True
            else:
                # diskcache官方文档：多进程多线程安全，推荐本地缓存首选
                self.cache = diskcache.Cache(cache_dir, size_limit=size_limit)
                self._memory_cache = False
        elif backend == "redis":
            if not _ensure_redis_imported():
                logger.warning("WARNING: redis 不可用，回退到内存缓存")
                self.cache = {}
                self._memory_cache = True
            else:
                try:
                    if async_mode and aioredis:
                        self.cache = aioredis.from_url(redis_url)
                    else:
                        self.cache = redis.StrictRedis.from_url(redis_url)
                    self._memory_cache = False
                except Exception as e:
                    logger.warning(f"WARNING: redis 连接失败，回退到内存缓存: {e}")
                    self.cache = {}
                    self._memory_cache = True
        else:
            raise ValueError("Unsupported backend or missing dependency")

    def get(self, key: str) -> Optional[Any]:
        if self._backend == "diskcache":
            if self._memory_cache:
                return self.cache.get(key)
            else:
                return self.cache.get(key, default=None)
        elif self._backend == "redis":
            if self._async_mode and aioredis:
                raise RuntimeError(
                    "Use await cache.get_async(key) in async mode")
            else:
                value = self.cache.get(key)
                return value
        return None

    async def get_async(self, key: str) -> Optional[Any]:
        if self._backend == "redis" and self._async_mode and aioredis:
            value = await self.cache.get(key)
            return value
        raise RuntimeError("Async mode not enabled or backend not supported")

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        expire = ttl if ttl is not None else self._default_ttl

        # 确保expire是有效的数值类型
        if not isinstance(expire, (int, float)):
            logger.warning(f"Invalid expire type: {type(expire)}, using default {self._default_ttl}")
            expire = self._default_ttl

        if self._backend == "diskcache":
            if self._memory_cache:
                self.cache[key] = value  # 简单内存缓存，忽略TTL
            else:
                self.cache.set(key, value, expire=expire)
        elif self._backend == "redis":
            if self._async_mode and aioredis:
                raise RuntimeError(
                    "Use await cache.set_async(key, value, ttl) in async mode")
            else:
                self.cache.setex(key, expire, value)

    async def set_async(self, key: str, value: Any, ttl: Optional[int] = None):
        expire = ttl if ttl is not None else self._default_ttl
        if self._backend == "redis" and self._async_mode and aioredis:
            await self.cache.set(key, value, ex=expire)
        else:
            raise RuntimeError(
                "Async mode not enabled or backend not supported")

    def delete(self, key: str):
        if self._backend == "diskcache":
            if self._memory_cache:
                self.cache.pop(key, None)
            else:
                self.cache.pop(key, None)
        elif self._backend == "redis":
            self.cache.delete(key)

    def clear(self):
        if self._backend == "diskcache":
            if self._memory_cache:
                self.cache.clear()
            else:
                self.cache.clear()
        elif self._backend == "redis":
            self.cache.flushdb()

    def get_stats(self) -> Dict[str, Any]:
        if self._backend == "diskcache":
            if self._memory_cache:
                return {
                    'size': len(self.cache),
                    'hits': 0,
                    'misses': 0,
                    'volume': 0,
                    'backend': 'memory'
                }
            else:
                stats = self.cache.stats()
                # diskcache.stats()返回tuple (hits, misses)
                if isinstance(stats, tuple) and len(stats) >= 2:
                    hits, misses = stats[0], stats[1]
                else:
                    hits, misses = 0, 0
                return {
                    'size': len(self.cache),
                    'hits': hits,
                    'misses': misses,
                    'volume': self.cache.volume(),
                    'backend': 'diskcache'
                }
        elif self._backend == "redis":
            return self.cache.info()
        return {}

    def get_keys(self):
        if self._backend == "diskcache":
            if self._memory_cache:
                return list(self.cache.keys())
            else:
                return list(self.cache.iterkeys())
        elif self._backend == "redis":
            return self.cache.keys()
        return []

    def get_size(self):
        if self._backend == "diskcache":
            return len(self.cache)
        elif self._backend == "redis":
            return self.cache.dbsize()
        return 0

    def exists(self, key: str) -> bool:
        if self._backend == "diskcache":
            return key in self.cache
        elif self._backend == "redis":
            return self.cache.exists(key)
        return False

    def set_default_ttl(self, ttl: int):
        """设置默认TTL，带类型检查"""
        if not isinstance(ttl, (int, float)):
            logger.warning(f"Invalid default_ttl type: {type(ttl)}, ignored")
            return
        self._default_ttl = ttl

    def set_size_limit(self, size_limit: int):
        if self._backend == "diskcache" and not self._memory_cache:
            self.cache.size_limit = size_limit
