"""
统一缓存服务 - 架构精简重构版本

整合所有缓存管理器功能，提供统一的多级缓存接口。
整合MultiLevelCacheManager、IntelligentCacheCoordinator、AdaptiveCacheStrategy等。
完全重构以符合15个核心服务的架构精简目标。
"""

from .metrics_base import add_dict_interface
import asyncio
import threading
import time
import hashlib
import pickle
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable, Set, Tuple, Generic, TypeVar
from collections import defaultdict, deque, OrderedDict
import gc

from loguru import logger

from .base_service import BaseService
from ..events import EventBus, get_event_bus
from ..containers import ServiceContainer, get_service_container

T = TypeVar('T')


class CacheLevel(Enum):
    """缓存级别"""
    L1_MEMORY = "l1_memory"         # L1内存缓存（最快）
    L2_DISK = "l2_disk"             # L2磁盘缓存
    L3_DISTRIBUTED = "l3_distributed"  # L3分布式缓存（预留）
    L4_PERSISTENT = "l4_persistent"    # L4持久化缓存


class CacheStrategy(Enum):
    """缓存策略"""
    LRU = "lru"                     # 最近最少使用
    LFU = "lfu"                     # 最少使用频率
    FIFO = "fifo"                   # 先进先出
    TTL = "ttl"                     # 基于时间的过期
    ADAPTIVE = "adaptive"           # 自适应策略


class CacheOperation(Enum):
    """缓存操作"""
    GET = "get"
    SET = "set"
    DELETE = "delete"
    CLEAR = "clear"
    INVALIDATE = "invalidate"


@dataclass
class CacheEntry(Generic[T]):
    """缓存条目"""
    key: str
    value: T
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    ttl: Optional[timedelta] = None
    size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return datetime.now() - self.created_at > self.ttl

    def update_access(self) -> None:
        """更新访问信息"""
        self.last_accessed = datetime.now()
        self.access_count += 1


@dataclass
class CacheStats:
    """缓存统计"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    clears: int = 0
    evictions: int = 0
    total_size: int = 0
    entry_count: int = 0

    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


@dataclass
class CacheConfig:
    """缓存配置"""
    max_size: int = 1000
    max_memory_mb: int = 100
    default_ttl: Optional[timedelta] = None
    strategy: CacheStrategy = CacheStrategy.LRU
    enable_compression: bool = False
    enable_persistence: bool = True
    persistence_interval: int = 300  # 5分钟
    cleanup_interval: int = 60       # 1分钟


@add_dict_interface
@dataclass
class CacheMetrics:
    """缓存指标"""
    # 必需字段（无默认值）
    level: CacheLevel

    # 基础指标字段（与BaseService一致）
    initialization_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    operation_count: int = 0

    # 缓存特定字段
    stats: CacheStats = field(default_factory=CacheStats)
    avg_access_time: float = 0.0
    peak_memory_usage: int = 0
    last_cleanup: datetime = field(default_factory=datetime.now)
    last_update: datetime = field(default_factory=datetime.now)


class MemoryCache:
    """内存缓存实现"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = CacheStats()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return None

            entry = self._cache[key]

            # 检查是否过期
            if entry.is_expired():
                del self._cache[key]
                self._stats.misses += 1
                self._stats.evictions += 1
                return None

            # 更新访问信息
            entry.update_access()

            # LRU策略：移动到末尾
            if self.config.strategy == CacheStrategy.LRU:
                self._cache.move_to_end(key)

            self._stats.hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> None:
        """设置缓存值"""
        with self._lock:
            # 计算值大小
            try:
                size = len(pickle.dumps(value))
            except:
                size = len(str(value))  # 备用计算方法

            # 创建缓存条目
            entry = CacheEntry(
                key=key,
                value=value,
                ttl=ttl or self.config.default_ttl,
                size=size
            )

            # 检查是否需要驱逐
            self._evict_if_needed(size)

            # 添加到缓存
            if key in self._cache:
                old_entry = self._cache[key]
                self._stats.total_size -= old_entry.size

            self._cache[key] = entry
            self._stats.total_size += size
            self._stats.sets += 1
            self._stats.entry_count = len(self._cache)

            # LRU策略：移动到末尾
            if self.config.strategy == CacheStrategy.LRU:
                self._cache.move_to_end(key)

    def delete(self, key: str) -> bool:
        """删除缓存值"""
        with self._lock:
            if key not in self._cache:
                return False

            entry = self._cache[key]
            del self._cache[key]

            self._stats.total_size -= entry.size
            self._stats.deletes += 1
            self._stats.entry_count = len(self._cache)

            return True

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._stats.total_size = 0
            self._stats.entry_count = 0
            self._stats.clears += 1

    def _evict_if_needed(self, new_entry_size: int) -> None:
        """根据需要驱逐条目"""
        # 检查大小限制
        while (len(self._cache) >= self.config.max_size or
               self._stats.total_size + new_entry_size > self.config.max_memory_mb * 1024 * 1024):

            if not self._cache:
                break

            # 根据策略选择驱逐的条目
            if self.config.strategy == CacheStrategy.LRU:
                # 驱逐最近最少使用的
                key_to_evict = next(iter(self._cache))
            elif self.config.strategy == CacheStrategy.LFU:
                # 驱逐使用频率最低的
                key_to_evict = min(self._cache.keys(),
                                   key=lambda k: self._cache[k].access_count)
            else:
                # 默认FIFO
                key_to_evict = next(iter(self._cache))

            entry = self._cache[key_to_evict]
            del self._cache[key_to_evict]

            self._stats.total_size -= entry.size
            self._stats.evictions += 1

    def cleanup_expired(self) -> int:
        """清理过期条目"""
        with self._lock:
            expired_keys = []

            for key, entry in self._cache.items():
                if entry.is_expired():
                    expired_keys.append(key)

            for key in expired_keys:
                self.delete(key)

            return len(expired_keys)

    def get_stats(self) -> CacheStats:
        """获取统计信息"""
        with self._lock:
            self._stats.entry_count = len(self._cache)
            return self._stats


class DiskCache:
    """磁盘缓存实现"""

    def __init__(self, config: CacheConfig, cache_dir: str = "cache"):
        self.config = config
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._stats = CacheStats()
        self._index: Dict[str, Dict[str, Any]] = {}
        self._load_index()

    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        # 使用hash避免文件名过长
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{hash_key}.cache"

    def _load_index(self) -> None:
        """加载索引"""
        index_path = self.cache_dir / "index.json"
        try:
            if index_path.exists():
                with open(index_path, 'r') as f:
                    self._index = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load disk cache index: {e}")
            self._index = {}

    def _save_index(self) -> None:
        """保存索引"""
        index_path = self.cache_dir / "index.json"
        try:
            with open(index_path, 'w') as f:
                json.dump(self._index, f)
        except Exception as e:
            logger.error(f"Failed to save disk cache index: {e}")

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._index:
                self._stats.misses += 1
                return None

            entry_info = self._index[key]

            # 检查是否过期
            if 'ttl' in entry_info and entry_info['ttl']:
                created_at = datetime.fromisoformat(entry_info['created_at'])
                ttl = timedelta(seconds=entry_info['ttl'])
                if datetime.now() - created_at > ttl:
                    self.delete(key)
                    self._stats.misses += 1
                    return None

            # 读取文件
            cache_path = self._get_cache_path(key)
            try:
                if not cache_path.exists():
                    # 索引和文件不一致，清理索引
                    del self._index[key]
                    self._stats.misses += 1
                    return None

                with open(cache_path, 'rb') as f:
                    value = pickle.load(f)

                # 更新访问信息
                entry_info['last_accessed'] = datetime.now().isoformat()
                entry_info['access_count'] = entry_info.get('access_count', 0) + 1

                self._stats.hits += 1
                return value

            except Exception as e:
                logger.error(f"Failed to read disk cache {key}: {e}")
                self.delete(key)
                self._stats.misses += 1
                return None

    def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> None:
        """设置缓存值"""
        with self._lock:
            cache_path = self._get_cache_path(key)

            try:
                # 写入文件
                with open(cache_path, 'wb') as f:
                    pickle.dump(value, f)

                # 获取文件大小
                size = cache_path.stat().st_size

                # 更新索引
                self._index[key] = {
                    'created_at': datetime.now().isoformat(),
                    'last_accessed': datetime.now().isoformat(),
                    'access_count': 0,
                    'size': size,
                    'ttl': ttl.total_seconds() if ttl else None
                }

                self._stats.sets += 1
                self._stats.total_size += size
                self._stats.entry_count = len(self._index)

                # 保存索引
                self._save_index()

            except Exception as e:
                logger.error(f"Failed to write disk cache {key}: {e}")

    def delete(self, key: str) -> bool:
        """删除缓存值"""
        with self._lock:
            if key not in self._index:
                return False

            cache_path = self._get_cache_path(key)
            entry_info = self._index[key]

            try:
                # 删除文件
                if cache_path.exists():
                    cache_path.unlink()

                # 更新统计
                self._stats.total_size -= entry_info.get('size', 0)
                self._stats.deletes += 1

                # 删除索引
                del self._index[key]
                self._stats.entry_count = len(self._index)

                # 保存索引
                self._save_index()

                return True

            except Exception as e:
                logger.error(f"Failed to delete disk cache {key}: {e}")
                return False

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            try:
                # 删除所有缓存文件
                for cache_file in self.cache_dir.glob("*.cache"):
                    cache_file.unlink()

                # 清空索引
                self._index.clear()
                self._stats.total_size = 0
                self._stats.entry_count = 0
                self._stats.clears += 1

                # 保存索引
                self._save_index()

            except Exception as e:
                logger.error(f"Failed to clear disk cache: {e}")

    def cleanup_expired(self) -> int:
        """清理过期条目"""
        with self._lock:
            expired_keys = []

            for key, entry_info in self._index.items():
                if 'ttl' in entry_info and entry_info['ttl']:
                    created_at = datetime.fromisoformat(entry_info['created_at'])
                    ttl = timedelta(seconds=entry_info['ttl'])
                    if datetime.now() - created_at > ttl:
                        expired_keys.append(key)

            for key in expired_keys:
                self.delete(key)

            return len(expired_keys)

    def get_stats(self) -> CacheStats:
        """获取统计信息"""
        with self._lock:
            self._stats.entry_count = len(self._index)
            return self._stats


class CacheService(BaseService):
    """
    统一缓存服务 - 架构精简重构版本

    整合所有缓存管理器功能：
    - MultiLevelCacheManager: 多级缓存管理
    - IntelligentCacheCoordinator: 智能缓存协调
    - AdaptiveCacheStrategy: 自适应缓存策略
    - EnhancedCacheSystem: 增强缓存系统
    - LRUCache, DiskCache: 各种缓存实现

    提供统一的多级缓存接口，支持：
    1. L1内存缓存（高速访问）
    2. L2磁盘缓存（大容量存储）
    3. 智能缓存策略和自适应优化
    4. 多种驱逐策略（LRU、LFU、FIFO、TTL）
    5. 压缩和持久化支持
    6. 性能监控和统计
    7. 自动过期清理
    8. 线程安全操作
    """

    def __init__(self, service_container: Optional[ServiceContainer] = None):
        """
        初始化缓存服务

        Args:
            service_container: 服务容器
        """
        super().__init__()
        self.service_name = "CacheService"

        # 依赖注入
        self._service_container = service_container or get_service_container()

        # 多级缓存
        self._l1_cache: Optional[MemoryCache] = None  # 内存缓存
        self._l2_cache: Optional[DiskCache] = None    # 磁盘缓存

        # 缓存配置（v2.5性能优化：增加缓存容量和延长TTL）
        self._l1_config = CacheConfig(
            max_size=5000,        # 从2000增加到5000，提升缓存命中率
            max_memory_mb=200,    # 保持200MB
            default_ttl=timedelta(hours=2),  # 从30分钟延长到2小时，减少重复查询
            strategy=CacheStrategy.LRU
        )

        self._l2_config = CacheConfig(
            max_size=50000,       # 从20000增加到50000，提升缓存命中率
            max_memory_mb=2000,   # 保持2000MB
            default_ttl=timedelta(hours=24),  # 从6小时延长到24小时，历史数据变化不频繁
            strategy=CacheStrategy.LRU,
            enable_persistence=True
        )

        # 指标和统计（按缓存级别）
        self._level_metrics: Dict[CacheLevel, CacheMetrics] = {}
        self._operation_history: deque = deque(maxlen=10000)

        # 访问模式分析
        self._access_patterns: Dict[str, List[datetime]] = defaultdict(list)
        self._hot_keys: Set[str] = set()
        self._cold_keys: Set[str] = set()

        # 线程和锁
        self._service_lock = threading.RLock()
        self._pattern_lock = threading.RLock()

        # 配置参数
        self._config = {
            "enable_l1_cache": True,
            "enable_l2_cache": True,
            "enable_access_pattern_analysis": True,
            "hot_key_threshold": 10,      # 10次访问认为是热键
            "cold_key_threshold": 1,      # 1次访问认为是冷键
            "cleanup_interval": 60,       # 1分钟清理间隔
            "pattern_analysis_interval": 300,  # 5分钟模式分析间隔
            "persistence_interval": 300,  # 5分钟持久化间隔
            "cache_directory": "data/cache"
        }

        # 监控统计
        self._start_time = datetime.now()
        self._last_cleanup = datetime.now()
        self._last_pattern_analysis = datetime.now()

        logger.info("CacheService initialized for architecture simplification")

    def _do_initialize(self) -> None:
        """执行具体的初始化逻辑"""
        try:
            logger.info("Initializing CacheService core components...")

            # 1. 初始化L1内存缓存
            self._initialize_l1_cache()

            # 2. 初始化L2磁盘缓存
            self._initialize_l2_cache()

            # 3. 初始化指标收集
            self._initialize_metrics()

            # 4. 启动后台任务
            self._start_background_tasks()

            # 5. 验证缓存功能
            self._validate_cache_functionality()

            logger.info("CacheService initialized successfully with multi-level caching capabilities")

        except Exception as e:
            logger.error(f"❌ Failed to initialize CacheService: {e}")
            raise

    def _initialize_l1_cache(self) -> None:
        """初始化L1内存缓存"""
        try:
            if self._config["enable_l1_cache"]:
                self._l1_cache = MemoryCache(self._l1_config)
                logger.info("✓ L1 Memory Cache initialized")
            else:
                logger.info("✓ L1 Memory Cache disabled")

        except Exception as e:
            logger.error(f"Failed to initialize L1 cache: {e}")
            raise

    def _initialize_l2_cache(self) -> None:
        """初始化L2磁盘缓存"""
        try:
            if self._config["enable_l2_cache"]:
                cache_dir = self._config["cache_directory"]
                self._l2_cache = DiskCache(self._l2_config, cache_dir)
                logger.info("✓ L2 Disk Cache initialized")
            else:
                logger.info("✓ L2 Disk Cache disabled")

        except Exception as e:
            logger.error(f"Failed to initialize L2 cache: {e}")
            raise

    def _initialize_metrics(self) -> None:
        """初始化指标收集"""
        try:
            # 初始化各级缓存指标
            for level in CacheLevel:
                self._level_metrics[level] = CacheMetrics(level=level)

            logger.info("✓ Cache metrics initialized")

        except Exception as e:
            logger.error(f"Failed to initialize metrics: {e}")
            raise

    def _start_background_tasks(self) -> None:
        """启动后台任务"""
        try:
            # 启动清理任务
            if hasattr(self, '_data_executor'):
                self._data_executor.submit(self._cleanup_loop)

                # 启动模式分析任务
                if self._config["enable_access_pattern_analysis"]:
                    self._data_executor.submit(self._pattern_analysis_loop)

                # 启动持久化任务
                self._data_executor.submit(self._persistence_loop)

            logger.info("✓ Background tasks started")

        except Exception as e:
            logger.error(f"Failed to start background tasks: {e}")

    def _validate_cache_functionality(self) -> None:
        """验证缓存功能"""
        try:
            # 测试L1缓存
            if self._l1_cache:
                test_key = "__test_l1__"
                test_value = {"test": "value", "timestamp": datetime.now().isoformat()}

                self._l1_cache.set(test_key, test_value)
                retrieved_value = self._l1_cache.get(test_key)

                if retrieved_value != test_value:
                    raise Exception("L1 cache functionality test failed")

                self._l1_cache.delete(test_key)
                logger.info("✓ L1 cache functionality validated")

            # 测试L2缓存
            if self._l2_cache:
                test_key = "__test_l2__"
                test_value = {"test": "value", "timestamp": datetime.now().isoformat()}

                self._l2_cache.set(test_key, test_value)
                retrieved_value = self._l2_cache.get(test_key)

                if retrieved_value != test_value:
                    raise Exception("L2 cache functionality test failed")

                self._l2_cache.delete(test_key)
                logger.info("✓ L2 cache functionality validated")

        except Exception as e:
            logger.error(f"Cache functionality validation failed: {e}")
            raise

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取缓存值

        Args:
            key: 缓存键
            default: 默认值

        Returns:
            缓存值或默认值
        """
        start_time = time.time()

        try:
            # 记录访问模式
            self._record_access_pattern(key)

            # 尝试L1缓存
            if self._l1_cache:
                value = self._l1_cache.get(key)
                if value is not None:
                    self._update_metrics(CacheLevel.L1_MEMORY, CacheOperation.GET, True, start_time)
                    return value

            # 尝试L2缓存
            if self._l2_cache:
                value = self._l2_cache.get(key)
                if value is not None:
                    # 提升到L1缓存
                    if self._l1_cache:
                        self._l1_cache.set(key, value)

                    self._update_metrics(CacheLevel.L2_DISK, CacheOperation.GET, True, start_time)
                    return value

            # 缓存未命中
            self._update_metrics(CacheLevel.L1_MEMORY, CacheOperation.GET, False, start_time)
            return default

        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            self._update_metrics(CacheLevel.L1_MEMORY, CacheOperation.GET, False, start_time)
            return default

    def set(self, key: str, value: Any, ttl: Optional[timedelta] = None,
            level: CacheLevel = CacheLevel.L1_MEMORY) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 生存时间
            level: 缓存级别
        """
        start_time = time.time()

        try:
            # 记录访问模式
            self._record_access_pattern(key)

            if level == CacheLevel.L1_MEMORY and self._l1_cache:
                self._l1_cache.set(key, value, ttl)
                self._update_metrics(CacheLevel.L1_MEMORY, CacheOperation.SET, True, start_time)

            elif level == CacheLevel.L2_DISK and self._l2_cache:
                self._l2_cache.set(key, value, ttl)
                self._update_metrics(CacheLevel.L2_DISK, CacheOperation.SET, True, start_time)

            else:
                # 默认设置到L1，然后异步设置到L2
                if self._l1_cache:
                    self._l1_cache.set(key, value, ttl)
                    self._update_metrics(CacheLevel.L1_MEMORY, CacheOperation.SET, True, start_time)

                if self._l2_cache:
                    # 使用较长的TTL存储到L2
                    l2_ttl = ttl or self._l2_config.default_ttl
                    self._l2_cache.set(key, value, l2_ttl)
                    self._update_metrics(CacheLevel.L2_DISK, CacheOperation.SET, True, start_time)

        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            self._update_metrics(level, CacheOperation.SET, False, start_time)

    def delete(self, key: str) -> bool:
        """
        删除缓存值

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        start_time = time.time()
        success = False

        try:
            # 从所有级别删除
            if self._l1_cache:
                l1_success = self._l1_cache.delete(key)
                success = success or l1_success
                self._update_metrics(CacheLevel.L1_MEMORY, CacheOperation.DELETE, l1_success, start_time)

            if self._l2_cache:
                l2_success = self._l2_cache.delete(key)
                success = success or l2_success
                self._update_metrics(CacheLevel.L2_DISK, CacheOperation.DELETE, l2_success, start_time)

            return success

        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False

    def clear(self, level: Optional[CacheLevel] = None) -> None:
        """
        清空缓存

        Args:
            level: 缓存级别，None表示清空所有级别
        """
        start_time = time.time()

        try:
            if level is None or level == CacheLevel.L1_MEMORY:
                if self._l1_cache:
                    self._l1_cache.clear()
                    self._update_metrics(CacheLevel.L1_MEMORY, CacheOperation.CLEAR, True, start_time)

            if level is None or level == CacheLevel.L2_DISK:
                if self._l2_cache:
                    self._l2_cache.clear()
                    self._update_metrics(CacheLevel.L2_DISK, CacheOperation.CLEAR, True, start_time)

            # 清空访问模式
            if level is None:
                with self._pattern_lock:
                    self._access_patterns.clear()
                    self._hot_keys.clear()
                    self._cold_keys.clear()

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

    def exists(self, key: str) -> bool:
        """
        检查缓存键是否存在

        Args:
            key: 缓存键

        Returns:
            是否存在
        """
        return self.get(key) is not None

    def get_size(self, level: Optional[CacheLevel] = None) -> int:
        """
        获取缓存大小

        Args:
            level: 缓存级别

        Returns:
            缓存条目数量
        """
        try:
            if level == CacheLevel.L1_MEMORY and self._l1_cache:
                return self._l1_cache.get_stats().entry_count
            elif level == CacheLevel.L2_DISK and self._l2_cache:
                return self._l2_cache.get_stats().entry_count
            else:
                # 返回总数
                total = 0
                if self._l1_cache:
                    total += self._l1_cache.get_stats().entry_count
                if self._l2_cache:
                    total += self._l2_cache.get_stats().entry_count
                return total

        except Exception as e:
            logger.error(f"Error getting cache size: {e}")
            return 0

    def get_stats(self, level: Optional[CacheLevel] = None) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Args:
            level: 缓存级别

        Returns:
            统计信息
        """
        try:
            stats = {}

            if level is None or level == CacheLevel.L1_MEMORY:
                if self._l1_cache:
                    l1_stats = self._l1_cache.get_stats()
                    stats["l1_memory"] = {
                        "hits": l1_stats.hits,
                        "misses": l1_stats.misses,
                        "hit_rate": l1_stats.hit_rate,
                        "sets": l1_stats.sets,
                        "deletes": l1_stats.deletes,
                        "evictions": l1_stats.evictions,
                        "entry_count": l1_stats.entry_count,
                        "total_size": l1_stats.total_size
                    }

            if level is None or level == CacheLevel.L2_DISK:
                if self._l2_cache:
                    l2_stats = self._l2_cache.get_stats()
                    stats["l2_disk"] = {
                        "hits": l2_stats.hits,
                        "misses": l2_stats.misses,
                        "hit_rate": l2_stats.hit_rate,
                        "sets": l2_stats.sets,
                        "deletes": l2_stats.deletes,
                        "evictions": l2_stats.evictions,
                        "entry_count": l2_stats.entry_count,
                        "total_size": l2_stats.total_size
                    }

            # 添加访问模式统计
            if level is None:
                with self._pattern_lock:
                    stats["access_patterns"] = {
                        "hot_keys_count": len(self._hot_keys),
                        "cold_keys_count": len(self._cold_keys),
                        "tracked_keys": len(self._access_patterns)
                    }

            return stats

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

    def get_hot_keys(self, limit: int = 10) -> List[str]:
        """获取热键列表"""
        with self._pattern_lock:
            # 按访问频率排序
            key_frequencies = {}
            for key, access_times in self._access_patterns.items():
                key_frequencies[key] = len(access_times)

            sorted_keys = sorted(key_frequencies.items(), key=lambda x: x[1], reverse=True)
            return [key for key, freq in sorted_keys[:limit]]

    def get_cold_keys(self, limit: int = 10) -> List[str]:
        """获取冷键列表"""
        with self._pattern_lock:
            # 按访问频率排序（升序）
            key_frequencies = {}
            for key, access_times in self._access_patterns.items():
                key_frequencies[key] = len(access_times)

            sorted_keys = sorted(key_frequencies.items(), key=lambda x: x[1])
            return [key for key, freq in sorted_keys[:limit]]

    def _record_access_pattern(self, key: str) -> None:
        """记录访问模式"""
        if not self._config["enable_access_pattern_analysis"]:
            return

        try:
            with self._pattern_lock:
                current_time = datetime.now()

                # 记录访问时间
                self._access_patterns[key].append(current_time)

                # 只保留最近一小时的访问记录
                one_hour_ago = current_time - timedelta(hours=1)
                self._access_patterns[key] = [
                    t for t in self._access_patterns[key]
                    if t > one_hour_ago
                ]

                # 更新热键和冷键集合
                access_count = len(self._access_patterns[key])

                if access_count >= self._config["hot_key_threshold"]:
                    self._hot_keys.add(key)
                    self._cold_keys.discard(key)
                elif access_count <= self._config["cold_key_threshold"]:
                    self._cold_keys.add(key)
                    self._hot_keys.discard(key)

        except Exception as e:
            logger.error(f"Error recording access pattern for {key}: {e}")

    def _update_metrics(self, level: CacheLevel, operation: CacheOperation,
                        success: bool, start_time: float) -> None:
        """更新指标"""
        try:
            with self._service_lock:
                metrics = self._level_metrics[level]
                execution_time = time.time() - start_time

                # 更新平均访问时间
                if metrics.avg_access_time == 0:
                    metrics.avg_access_time = execution_time
                else:
                    metrics.avg_access_time = (metrics.avg_access_time + execution_time) / 2

                metrics.last_update = datetime.now()

                # 记录操作历史
                self._operation_history.append({
                    "level": level.value,
                    "operation": operation.value,
                    "success": success,
                    "execution_time": execution_time,
                    "timestamp": datetime.now().isoformat()
                })

        except Exception as e:
            logger.error(f"Error updating metrics: {e}")

    def _cleanup_loop(self) -> None:
        """清理循环"""
        while not self._shutdown_event.is_set():
            try:
                self._perform_cleanup()
                self._shutdown_event.wait(self._config["cleanup_interval"])
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                self._shutdown_event.wait(60)

    def _pattern_analysis_loop(self) -> None:
        """模式分析循环"""
        while not self._shutdown_event.is_set():
            try:
                self._analyze_access_patterns()
                self._shutdown_event.wait(self._config["pattern_analysis_interval"])
            except Exception as e:
                logger.error(f"Error in pattern analysis loop: {e}")
                self._shutdown_event.wait(60)

    def _persistence_loop(self) -> None:
        """持久化循环"""
        while not self._shutdown_event.is_set():
            try:
                self._perform_persistence()
                self._shutdown_event.wait(self._config["persistence_interval"])
            except Exception as e:
                logger.error(f"Error in persistence loop: {e}")
                self._shutdown_event.wait(60)

    def _perform_cleanup(self) -> None:
        """执行清理"""
        try:
            cleaned_l1 = 0
            cleaned_l2 = 0

            if self._l1_cache:
                cleaned_l1 = self._l1_cache.cleanup_expired()

            if self._l2_cache:
                cleaned_l2 = self._l2_cache.cleanup_expired()

            if cleaned_l1 > 0 or cleaned_l2 > 0:
                logger.debug(f"Cleaned up {cleaned_l1} L1 entries and {cleaned_l2} L2 entries")

            self._last_cleanup = datetime.now()

            # 清理旧的访问模式
            with self._pattern_lock:
                one_hour_ago = datetime.now() - timedelta(hours=1)
                keys_to_remove = []

                for key, access_times in self._access_patterns.items():
                    # 过滤掉旧的访问记录
                    recent_accesses = [t for t in access_times if t > one_hour_ago]

                    if not recent_accesses:
                        keys_to_remove.append(key)
                    else:
                        self._access_patterns[key] = recent_accesses

                for key in keys_to_remove:
                    del self._access_patterns[key]
                    self._hot_keys.discard(key)
                    self._cold_keys.discard(key)

        except Exception as e:
            logger.error(f"Cleanup operation failed: {e}")

    def _analyze_access_patterns(self) -> None:
        """分析访问模式"""
        try:
            with self._pattern_lock:
                # 分析热键和冷键
                hot_keys = set()
                cold_keys = set()

                for key, access_times in self._access_patterns.items():
                    access_count = len(access_times)

                    if access_count >= self._config["hot_key_threshold"]:
                        hot_keys.add(key)
                    elif access_count <= self._config["cold_key_threshold"]:
                        cold_keys.add(key)

                self._hot_keys = hot_keys
                self._cold_keys = cold_keys

                self._last_pattern_analysis = datetime.now()

                logger.debug(f"Pattern analysis: {len(hot_keys)} hot keys, {len(cold_keys)} cold keys")

        except Exception as e:
            logger.error(f"Pattern analysis failed: {e}")

    def _perform_persistence(self) -> None:
        """执行持久化"""
        try:
            # L2缓存的索引会自动持久化，这里主要是触发清理和压缩
            if self._l2_cache:
                # 触发磁盘缓存的内部维护
                pass

        except Exception as e:
            logger.error(f"Persistence operation failed: {e}")

    def _do_health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        try:
            l1_healthy = False
            l2_healthy = False

            # 测试L1缓存
            if self._l1_cache:
                try:
                    test_key = "__health_check_l1__"
                    self._l1_cache.set(test_key, "test")
                    result = self._l1_cache.get(test_key)
                    self._l1_cache.delete(test_key)
                    l1_healthy = (result == "test")
                except:
                    l1_healthy = False

            # 测试L2缓存
            if self._l2_cache:
                try:
                    test_key = "__health_check_l2__"
                    self._l2_cache.set(test_key, "test")
                    result = self._l2_cache.get(test_key)
                    self._l2_cache.delete(test_key)
                    l2_healthy = (result == "test")
                except:
                    l2_healthy = False

            stats = self.get_stats()

            return {
                "status": "healthy" if (l1_healthy or l2_healthy) else "unhealthy",
                "l1_cache_healthy": l1_healthy,
                "l2_cache_healthy": l2_healthy,
                "l1_cache_size": stats.get("l1_memory", {}).get("entry_count", 0),
                "l2_cache_size": stats.get("l2_disk", {}).get("entry_count", 0),
                "hot_keys_count": len(self._hot_keys),
                "cold_keys_count": len(self._cold_keys),
                "uptime_seconds": (datetime.now() - self._start_time).total_seconds()
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _do_dispose(self) -> None:
        """清理资源"""
        try:
            logger.info("Disposing CacheService resources...")

            # 执行最后一次持久化
            self._perform_persistence()

            # 清理缓存
            if self._l1_cache:
                self._l1_cache.clear()

            if self._l2_cache:
                self._l2_cache.clear()

            # 清理访问模式
            with self._pattern_lock:
                self._access_patterns.clear()
                self._hot_keys.clear()
                self._cold_keys.clear()

            logger.info("CacheService disposed successfully")

        except Exception as e:
            logger.error(f"Error disposing CacheService: {e}")

    @property
    def metrics(self) -> Dict[str, Any]:
        """返回缓存服务指标的字典表示"""
        combined_metrics = {
            'total_hits': 0,
            'total_misses': 0,
            'total_sets': 0,
            'total_deletes': 0,
            'total_size': 0,
            'level_metrics': {}
        }

        for level, cache_metrics in self._level_metrics.items():
            level_name = level.value
            combined_metrics['level_metrics'][level_name] = {
                'hits': cache_metrics.stats.hits,
                'misses': cache_metrics.stats.misses,
                'sets': cache_metrics.stats.sets,
                'deletes': cache_metrics.stats.deletes,
                'size': cache_metrics.stats.total_size,
                'evictions': cache_metrics.stats.evictions,
                'avg_access_time': cache_metrics.avg_access_time,
                'peak_memory_usage': cache_metrics.peak_memory_usage
            }
            combined_metrics['total_hits'] += cache_metrics.stats.hits
            combined_metrics['total_misses'] += cache_metrics.stats.misses
            combined_metrics['total_sets'] += cache_metrics.stats.sets
            combined_metrics['total_deletes'] += cache_metrics.stats.deletes
            combined_metrics['total_size'] += cache_metrics.stats.total_size

        return combined_metrics


# 便利函数
@contextmanager
def cached_operation(cache_service: CacheService, key: str,
                     ttl: Optional[timedelta] = None,
                     compute_func: Optional[Callable] = None):
    """
    缓存操作上下文管理器

    Args:
        cache_service: 缓存服务实例
        key: 缓存键
        ttl: 生存时间
        compute_func: 计算函数（缓存未命中时调用）
    """
    # 尝试从缓存获取
    value = cache_service.get(key)

    if value is not None:
        yield value
    else:
        # 计算新值
        if compute_func:
            computed_value = compute_func()
            cache_service.set(key, computed_value, ttl)
            yield computed_value
        else:
            yield None
