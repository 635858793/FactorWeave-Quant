#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DEPRECATED: 此模块已被 cache_service.CacheService 取代。
所有缓存操作请使用 from core.services.cache_service import CacheService。
本模块保留仅用于向后兼容，将在未来版本中移除。

原文档：
Enhanced Cache System
增强缓存系统

本模块提供高性能、多层级的缓存系统，支持多种缓存策略、自动过期、
分布式缓存、缓存预热、性能监控等功能。

主要特性：
1. 多层级缓存（内存、磁盘、分布式）
2. 多种缓存策略（LRU、LFU、TTL、自适应）
3. 缓存预热和预加载
4. 缓存性能监控和统计
5. 缓存一致性保证
6. 异步缓存操作
7. 缓存压缩和序列化
8. 智能缓存淘汰
"""

import asyncio
import threading
import time
import pickle
from utils.safe_pickle import safe_load, safe_loads
import gzip
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import weakref

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from loguru import logger

logger = logger.bind(module=__name__)

class CacheStrategy(Enum):
    """缓存策略枚举"""
    LRU = "lru"          # 最近最少使用
    LFU = "lfu"          # 最少使用频率
    TTL = "ttl"          # 基于时间过期
    FIFO = "fifo"        # 先进先出
    ADAPTIVE = "adaptive"  # 自适应策略

class CacheLevel(Enum):
    """缓存层级枚举"""
    L1_MEMORY = "l1_memory"      # L1内存缓存
    L2_DISK = "l2_disk"          # L2磁盘缓存
    L3_DISTRIBUTED = "l3_distributed"  # L3分布式缓存

@dataclass
class CacheItem:
    """缓存项数据类"""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    ttl: Optional[float] = None
    size: int = 0
    compressed: bool = False

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def touch(self):
        """更新访问时间和次数"""
        self.last_accessed = time.time()
        self.access_count += 1

    def age(self) -> float:
        """获取缓存项年龄（秒）"""
        return time.time() - self.created_at

@dataclass
class CacheStats:
    """缓存统计数据类"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    memory_usage: int = 0
    avg_access_time: float = 0.0
    hit_rate: float = 0.0

    def update_hit_rate(self):
        """更新命中率"""
        total = self.hits + self.misses
        self.hit_rate = self.hits / total if total > 0 else 0.0

class CacheMonitor:
    """缓存监控器"""

    def __init__(self):
        self.stats = defaultdict(CacheStats)
        self.performance_history = defaultdict(list)
        self.alert_thresholds = {
            'hit_rate_min': 0.7,
            'memory_usage_max': 0.9,
            'avg_access_time_max': 0.1
        }
        self.alert_callbacks = []

    def record_hit(self, cache_name: str, access_time: float):
        """记录缓存命中"""
        stats = self.stats[cache_name]
        stats.hits += 1
        stats.avg_access_time = (stats.avg_access_time * (stats.hits - 1) + access_time) / stats.hits
        stats.update_hit_rate()

        self._check_alerts(cache_name, stats)

    def record_miss(self, cache_name: str):
        """记录缓存未命中"""
        stats = self.stats[cache_name]
        stats.misses += 1
        stats.update_hit_rate()

        self._check_alerts(cache_name, stats)

    def record_eviction(self, cache_name: str):
        """记录缓存淘汰"""
        self.stats[cache_name].evictions += 1

    def update_size(self, cache_name: str, size: int, memory_usage: int):
        """更新缓存大小和内存使用"""
        stats = self.stats[cache_name]
        stats.size = size
        stats.memory_usage = memory_usage

    def get_stats(self, cache_name: str) -> CacheStats:
        """获取缓存统计"""
        return self.stats[cache_name]

    def get_all_stats(self) -> Dict[str, CacheStats]:
        """获取所有缓存统计"""
        return dict(self.stats)

    def add_alert_callback(self, callback: Callable[[str, str, Any], None]):
        """添加告警回调"""
        self.alert_callbacks.append(callback)

    def _check_alerts(self, cache_name: str, stats: CacheStats):
        """检查告警条件"""
        alerts = []

        if stats.hit_rate < self.alert_thresholds['hit_rate_min']:
            alerts.append(('low_hit_rate', stats.hit_rate))

        if stats.avg_access_time > self.alert_thresholds['avg_access_time_max']:
            alerts.append(('high_access_time', stats.avg_access_time))

        for alert_type, value in alerts:
            for callback in self.alert_callbacks:
                try:
                    callback(cache_name, alert_type, value)
                except Exception as e:
                    logger.error(f"缓存告警回调执行失败: {e}")

class LRUCache:
    """LRU缓存实现"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache = OrderedDict()
        self.lock = threading.RLock()

    def get(self, key: str) -> Optional[CacheItem]:
        """获取缓存项"""
        with self.lock:
            if key in self.cache:
                item = self.cache[key]
                if not item.is_expired():
                    # 移动到末尾（最近使用）
                    self.cache.move_to_end(key)
                    item.touch()
                    return item
                else:
                    # 过期，删除
                    del self.cache[key]
            return None

    def put(self, key: str, item: CacheItem) -> Optional[CacheItem]:
        """存储缓存项"""
        with self.lock:
            evicted_item = None

            if key in self.cache:
                # 更新现有项
                self.cache[key] = item
                self.cache.move_to_end(key)
            else:
                # 新增项
                if len(self.cache) >= self.max_size:
                    # 淘汰最久未使用的项
                    oldest_key, evicted_item = self.cache.popitem(last=False)

                self.cache[key] = item

            return evicted_item

    def remove(self, key: str) -> bool:
        """删除缓存项"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()

    def size(self) -> int:
        """获取缓存大小"""
        return len(self.cache)

    def keys(self) -> List[str]:
        """获取所有键"""
        with self.lock:
            return list(self.cache.keys())

class LFUCache:
    """LFU缓存实现"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache = {}
        self.frequencies = defaultdict(int)
        self.freq_to_keys = defaultdict(set)
        self.min_freq = 0
        self.lock = threading.RLock()

    def get(self, key: str) -> Optional[CacheItem]:
        """获取缓存项"""
        with self.lock:
            if key not in self.cache:
                return None

            item = self.cache[key]
            if item.is_expired():
                self._remove_key(key)
                return None

            # 更新频率
            self._update_freq(key)
            item.touch()
            return item

    def put(self, key: str, item: CacheItem) -> Optional[CacheItem]:
        """存储缓存项"""
        with self.lock:
            evicted_item = None

            if key in self.cache:
                # 更新现有项
                self.cache[key] = item
                self._update_freq(key)
            else:
                # 新增项
                if len(self.cache) >= self.max_size:
                    evicted_item = self._evict_lfu()

                self.cache[key] = item
                self.frequencies[key] = 1
                self.freq_to_keys[1].add(key)
                self.min_freq = 1

            return evicted_item

    def _update_freq(self, key: str):
        """更新键的访问频率"""
        freq = self.frequencies[key]
        self.freq_to_keys[freq].remove(key)

        if freq == self.min_freq and not self.freq_to_keys[freq]:
            self.min_freq += 1

        self.frequencies[key] = freq + 1
        self.freq_to_keys[freq + 1].add(key)

    def _evict_lfu(self) -> Optional[CacheItem]:
        """淘汰最少使用频率的项"""
        if not self.freq_to_keys[self.min_freq]:
            return None

        key_to_remove = self.freq_to_keys[self.min_freq].pop()
        evicted_item = self.cache[key_to_remove]
        self._remove_key(key_to_remove)
        return evicted_item

    def _remove_key(self, key: str):
        """删除键"""
        if key in self.cache:
            freq = self.frequencies[key]
            self.freq_to_keys[freq].discard(key)
            del self.frequencies[key]
            del self.cache[key]

    def remove(self, key: str) -> bool:
        """删除缓存项"""
        with self.lock:
            if key in self.cache:
                self._remove_key(key)
                return True
            return False

    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.frequencies.clear()
            self.freq_to_keys.clear()
            self.min_freq = 0

    def size(self) -> int:
        """获取缓存大小"""
        return len(self.cache)

class AdaptiveCache:
    """自适应缓存实现"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.lru_cache = LRUCache(max_size // 2)
        self.lfu_cache = LFUCache(max_size // 2)
        self.access_pattern = defaultdict(list)
        self.strategy_weights = {'lru': 0.5, 'lfu': 0.5}
        self.lock = threading.RLock()

        # 自适应参数
        self.adaptation_window = 1000  # 适应窗口大小
        self.adaptation_counter = 0

    def get(self, key: str) -> Optional[CacheItem]:
        """获取缓存项"""
        with self.lock:
            # 记录访问模式
            self.access_pattern[key].append(time.time())
            self._trim_access_pattern(key)

            # 尝试从两个缓存中获取
            item = self.lru_cache.get(key)
            if item:
                return item

            item = self.lfu_cache.get(key)
            if item:
                return item

            return None

    def put(self, key: str, item: CacheItem) -> Optional[CacheItem]:
        """存储缓存项"""
        with self.lock:
            self.adaptation_counter += 1

            # 根据访问模式选择缓存策略
            if self._should_use_lru(key):
                evicted = self.lru_cache.put(key, item)
            else:
                evicted = self.lfu_cache.put(key, item)

            # 定期调整策略权重
            if self.adaptation_counter % self.adaptation_window == 0:
                self._adapt_strategy()

            return evicted

    def _should_use_lru(self, key: str) -> bool:
        """判断是否应该使用LRU策略"""
        access_times = self.access_pattern.get(key, [])

        if len(access_times) < 2:
            # 新键，根据权重随机选择
            return self.strategy_weights['lru'] > self.strategy_weights['lfu']

        # 分析访问模式
        recent_accesses = len([t for t in access_times if time.time() - t < 300])  # 5分钟内
        total_accesses = len(access_times)

        # 如果最近访问频繁，使用LRU；如果总体访问频繁，使用LFU
        recency_ratio = recent_accesses / total_accesses if total_accesses > 0 else 0

        return recency_ratio > 0.5

    def _trim_access_pattern(self, key: str):
        """修剪访问模式记录"""
        access_times = self.access_pattern[key]
        # 只保留最近1小时的访问记录
        cutoff_time = time.time() - 3600
        self.access_pattern[key] = [t for t in access_times if t > cutoff_time]

    def _adapt_strategy(self):
        """自适应调整策略权重"""
        # 简化的自适应逻辑，实际可以更复杂
        lru_hit_rate = self._calculate_hit_rate(self.lru_cache)
        lfu_hit_rate = self._calculate_hit_rate(self.lfu_cache)

        total_rate = lru_hit_rate + lfu_hit_rate
        if total_rate > 0:
            self.strategy_weights['lru'] = lru_hit_rate / total_rate
            self.strategy_weights['lfu'] = lfu_hit_rate / total_rate

    def _calculate_hit_rate(self, cache) -> float:
        """计算缓存命中率（简化实现）"""
        # 这里需要实际的统计数据，简化为固定值
        return 0.5

    def remove(self, key: str) -> bool:
        """删除缓存项"""
        with self.lock:
            removed1 = self.lru_cache.remove(key)
            removed2 = self.lfu_cache.remove(key)
            if key in self.access_pattern:
                del self.access_pattern[key]
            return removed1 or removed2

    def clear(self):
        """清空缓存"""
        with self.lock:
            self.lru_cache.clear()
            self.lfu_cache.clear()
            self.access_pattern.clear()

    def size(self) -> int:
        """获取缓存大小"""
        return self.lru_cache.size() + self.lfu_cache.size()

class DiskCache:
    """磁盘缓存实现"""

    def __init__(self, cache_dir: str, max_size_mb: int = 1000):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.index_file = self.cache_dir / "cache_index.json"
        self.index = {}
        self.lock = threading.RLock()

        self._load_index()

    def _load_index(self):
        """加载缓存索引"""
        try:
            if self.index_file.exists():
                with open(self.index_file, 'r') as f:
                    self.index = json.load(f)
        except Exception as e:
            logger.warning(f"加载磁盘缓存索引失败: {e}")
            self.index = {}

    def _save_index(self):
        """保存缓存索引"""
        try:
            with open(self.index_file, 'w') as f:
                json.dump(self.index, f)
        except Exception as e:
            logger.error(f"保存磁盘缓存索引失败: {e}")

    def _get_file_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        # 使用哈希避免文件名冲突
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"

    def get(self, key: str) -> Optional[CacheItem]:
        """获取缓存项"""
        with self.lock:
            if key not in self.index:
                return None

            file_path = self._get_file_path(key)
            if not file_path.exists():
                # 文件不存在，清理索引
                del self.index[key]
                self._save_index()
                return None

            try:
                with open(file_path, 'rb') as f:
                    data = f.read()

                # 检查是否压缩
                if self.index[key].get('compressed', False):
                    data = gzip.decompress(data)

                item = safe_loads(data)

                if item.is_expired():
                    self.remove(key)
                    return None

                # 更新访问时间
                item.touch()
                self.index[key]['last_accessed'] = item.last_accessed
                self._save_index()

                return item

            except Exception as e:
                logger.error(f"读取磁盘缓存失败 {key}: {e}")
                self.remove(key)
                return None

    def put(self, key: str, item: CacheItem, compress: bool = True) -> bool:
        """存储缓存项"""
        with self.lock:
            try:
                # 序列化数据
                data = pickle.dumps(item)

                # 压缩数据
                if compress:
                    data = gzip.compress(data)
                    item.compressed = True

                file_path = self._get_file_path(key)

                # 检查磁盘空间
                if not self._check_disk_space(len(data)):
                    self._cleanup_old_files()
                    if not self._check_disk_space(len(data)):
                        logger.warning("磁盘缓存空间不足")
                        return False

                # 写入文件
                with open(file_path, 'wb') as f:
                    f.write(data)

                # 更新索引
                self.index[key] = {
                    'size': len(data),
                    'created_at': item.created_at,
                    'last_accessed': item.last_accessed,
                    'ttl': item.ttl,
                    'compressed': compress
                }
                self._save_index()

                return True

            except Exception as e:
                logger.error(f"写入磁盘缓存失败 {key}: {e}")
                return False

    def remove(self, key: str) -> bool:
        """删除缓存项"""
        with self.lock:
            if key not in self.index:
                return False

            file_path = self._get_file_path(key)
            try:
                if file_path.exists():
                    file_path.unlink()
                del self.index[key]
                self._save_index()
                return True
            except Exception as e:
                logger.error(f"删除磁盘缓存失败 {key}: {e}")
                return False

    def clear(self):
        """清空缓存"""
        with self.lock:
            try:
                for key in list(self.index.keys()):
                    self.remove(key)
            except Exception as e:
                logger.error(f"清空磁盘缓存失败: {e}")

    def _check_disk_space(self, new_size: int) -> bool:
        """检查磁盘空间"""
        current_size = sum(item['size'] for item in self.index.values())
        return current_size + new_size <= self.max_size_bytes

    def _cleanup_old_files(self):
        """清理旧文件"""
        # 按最后访问时间排序，删除最旧的文件
        sorted_items = sorted(
            self.index.items(),
            key=lambda x: x[1]['last_accessed']
        )

        # 删除最旧的25%文件
        cleanup_count = len(sorted_items) // 4
        for key, _ in sorted_items[:cleanup_count]:
            self.remove(key)

    def size(self) -> int:
        """获取缓存项数量"""
        return len(self.index)

    def disk_usage(self) -> int:
        """获取磁盘使用量（字节）"""
        return sum(item['size'] for item in self.index.values())

class DistributedCache:
    """分布式缓存实现（基于Redis）"""

    def __init__(self, redis_config: Dict[str, Any]):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis not available. Install redis-py to use distributed cache.")

        self.redis_client = redis.Redis(**redis_config)
        self.key_prefix = redis_config.get('key_prefix', 'factorweave_cache:')
        self.default_ttl = redis_config.get('default_ttl', 3600)

        try:
            self.redis_client.ping()
            logger.info("Redis连接成功")
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            raise

    def get(self, key: str) -> Optional[CacheItem]:
        """获取缓存项"""
        try:
            redis_key = self.key_prefix + key
            data = self.redis_client.get(redis_key)

            if data is None:
                return None

            # 反序列化
            item = safe_loads(data)

            if item.is_expired():
                self.remove(key)
                return None

            item.touch()
            return item

        except Exception as e:
            logger.error(f"Redis获取缓存失败 {key}: {e}")
            return None

    def put(self, key: str, item: CacheItem) -> bool:
        """存储缓存项"""
        try:
            redis_key = self.key_prefix + key
            data = pickle.dumps(item)

            # 设置TTL
            ttl = item.ttl or self.default_ttl

            result = self.redis_client.setex(redis_key, int(ttl), data)
            return result

        except Exception as e:
            logger.error(f"Redis存储缓存失败 {key}: {e}")
            return False

    def remove(self, key: str) -> bool:
        """删除缓存项"""
        try:
            redis_key = self.key_prefix + key
            result = self.redis_client.delete(redis_key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis删除缓存失败 {key}: {e}")
            return False

    def clear(self):
        """清空缓存"""
        try:
            pattern = self.key_prefix + "*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis清空缓存失败: {e}")

    def size(self) -> int:
        """获取缓存项数量"""
        try:
            pattern = self.key_prefix + "*"
            return len(self.redis_client.keys(pattern))
        except Exception as e:
            logger.error(f"Redis获取缓存大小失败: {e}")
            return 0

class EnhancedCacheSystem:
    """增强缓存系统主类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.caches = {}
        self.monitor = CacheMonitor()
        self.preloader = None
        self.lock = threading.RLock()

        # 初始化缓存层级
        self._init_caches()

        # 设置监控告警
        self.monitor.add_alert_callback(self._handle_cache_alert)

        logger.info("增强缓存系统初始化完成")

    def _init_caches(self):
        """初始化缓存层级"""
        # L1内存缓存
        l1_config = self.config.get('l1_memory', {})
        strategy = CacheStrategy(l1_config.get('strategy', 'lru'))
        max_size = l1_config.get('max_size', 10000)

        if strategy == CacheStrategy.LRU:
            self.caches[CacheLevel.L1_MEMORY] = LRUCache(max_size)
        elif strategy == CacheStrategy.LFU:
            self.caches[CacheLevel.L1_MEMORY] = LFUCache(max_size)
        elif strategy == CacheStrategy.ADAPTIVE:
            self.caches[CacheLevel.L1_MEMORY] = AdaptiveCache(max_size)
        else:
            self.caches[CacheLevel.L1_MEMORY] = LRUCache(max_size)

        # L2磁盘缓存
        l2_config = self.config.get('l2_disk', {})
        if l2_config.get('enabled', False):
            cache_dir = l2_config.get('cache_dir', './cache')
            max_size_mb = l2_config.get('max_size_mb', 1000)
            self.caches[CacheLevel.L2_DISK] = DiskCache(cache_dir, max_size_mb)

        # L3分布式缓存
        l3_config = self.config.get('l3_distributed', {})
        if l3_config.get('enabled', False) and REDIS_AVAILABLE:
            try:
                redis_config = l3_config.get('redis', {})
                self.caches[CacheLevel.L3_DISTRIBUTED] = DistributedCache(redis_config)
            except Exception as e:
                logger.warning(f"分布式缓存初始化失败: {e}")

    async def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值"""
        start_time = time.time()

        try:
            # 按层级顺序查找
            for level in [CacheLevel.L1_MEMORY, CacheLevel.L2_DISK, CacheLevel.L3_DISTRIBUTED]:
                if level not in self.caches:
                    continue

                cache = self.caches[level]
                item = cache.get(key)

                if item is not None:
                    # 缓存命中，提升到上层缓存
                    await self._promote_to_upper_levels(key, item, level)

                    access_time = time.time() - start_time
                    self.monitor.record_hit(level.value, access_time)

                    return item.value

            # 缓存未命中
            for level in self.caches:
                self.monitor.record_miss(level.value)

            return default

        except Exception as e:
            logger.error(f"缓存获取失败 {key}: {e}")
            return default

    async def put(self, key: str, value: Any, ttl: Optional[float] = None,
                  levels: Optional[List[CacheLevel]] = None) -> bool:
        """存储缓存值"""
        try:
            # 创建缓存项
            item = CacheItem(
                key=key,
                value=value,
                ttl=ttl,
                size=self._estimate_size(value)
            )

            # 确定存储层级
            if levels is None:
                levels = list(self.caches.keys())

            success = True
            for level in levels:
                if level not in self.caches:
                    continue

                cache = self.caches[level]
                evicted_item = cache.put(key, item)

                if evicted_item:
                    self.monitor.record_eviction(level.value)

                # 更新统计
                self.monitor.update_size(level.value, cache.size(), self._get_memory_usage(cache))

            return success

        except Exception as e:
            logger.error(f"缓存存储失败 {key}: {e}")
            return False

    async def remove(self, key: str) -> bool:
        """删除缓存项"""
        success = False
        for cache in self.caches.values():
            if cache.remove(key):
                success = True
        return success

    async def clear(self, levels: Optional[List[CacheLevel]] = None):
        """清空缓存"""
        if levels is None:
            levels = list(self.caches.keys())

        for level in levels:
            if level in self.caches:
                self.caches[level].clear()

    async def preload(self, preload_func: Callable[[], Dict[str, Any]],
                      ttl: Optional[float] = None):
        """预加载缓存"""
        try:
            logger.info("开始缓存预加载...")
            data = preload_func()

            for key, value in data.items():
                await self.put(key, value, ttl)

            logger.info(f"缓存预加载完成，加载 {len(data)} 项")

        except Exception as e:
            logger.error(f"缓存预加载失败: {e}")

    async def warm_up(self, keys: List[str], loader_func: Callable[[str], Any]):
        """缓存预热"""
        try:
            logger.info(f"开始缓存预热，预热 {len(keys)} 个键...")

            for key in keys:
                if await self.get(key) is None:
                    value = loader_func(key)
                    if value is not None:
                        await self.put(key, value)

            logger.info("缓存预热完成")

        except Exception as e:
            logger.error(f"缓存预热失败: {e}")

    def get_stats(self) -> Dict[str, CacheStats]:
        """获取缓存统计"""
        return self.monitor.get_all_stats()

    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        stats = self.get_stats()

        report = {
            'timestamp': datetime.now().isoformat(),
            'cache_levels': {},
            'overall_performance': {}
        }

        total_hits = 0
        total_misses = 0
        total_size = 0

        for level_name, stat in stats.items():
            report['cache_levels'][level_name] = {
                'hit_rate': stat.hit_rate,
                'hits': stat.hits,
                'misses': stat.misses,
                'evictions': stat.evictions,
                'size': stat.size,
                'memory_usage': stat.memory_usage,
                'avg_access_time': stat.avg_access_time
            }

            total_hits += stat.hits
            total_misses += stat.misses
            total_size += stat.size

        # 整体性能指标
        total_requests = total_hits + total_misses
        overall_hit_rate = total_hits / total_requests if total_requests > 0 else 0

        report['overall_performance'] = {
            'overall_hit_rate': overall_hit_rate,
            'total_requests': total_requests,
            'total_hits': total_hits,
            'total_misses': total_misses,
            'total_cache_size': total_size
        }

        return report

    async def _promote_to_upper_levels(self, key: str, item: CacheItem, current_level: CacheLevel):
        """将缓存项提升到上层缓存"""
        levels = [CacheLevel.L1_MEMORY, CacheLevel.L2_DISK, CacheLevel.L3_DISTRIBUTED]
        current_index = levels.index(current_level)

        # 提升到所有上层缓存
        for i in range(current_index):
            level = levels[i]
            if level in self.caches:
                cache = self.caches[level]
                cache.put(key, item)

    def _estimate_size(self, value: Any) -> int:
        """估算值的大小"""
        try:
            return len(pickle.dumps(value))
        except Exception:
            return 0

    def _get_memory_usage(self, cache) -> int:
        """获取缓存内存使用量"""
        # 简化实现，实际可以更精确
        return cache.size() * 1024  # 假设每项平均1KB

    def _handle_cache_alert(self, cache_name: str, alert_type: str, value: Any):
        """处理缓存告警"""
        logger.warning(f"缓存告警 - {cache_name}: {alert_type} = {value}")

        # 可以在这里实现自动优化策略
        if alert_type == 'low_hit_rate':
            logger.info(f"缓存 {cache_name} 命中率过低，考虑调整缓存策略")
        elif alert_type == 'high_access_time':
            logger.info(f"缓存 {cache_name} 访问时间过长，考虑优化存储")

# 缓存装饰器
def cached(ttl: Optional[float] = None, key_func: Optional[Callable] = None):
    """缓存装饰器"""
    def decorator(func):
        cache_system = None

        def wrapper(*args, **kwargs):
            nonlocal cache_system

            # 获取全局缓存系统实例
            if cache_system is None:
                cache_system = get_global_cache_system()

            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__module__}.{func.__name__}:{hash((args, tuple(kwargs.items())))}"

            from utils.async_utils import run_async_blocking

            cached_result = run_async_blocking(cache_system.get(cache_key))
            if cached_result is not None:
                return cached_result

            result = func(*args, **kwargs)
            run_async_blocking(cache_system.put(cache_key, result, ttl))

            return result

        return wrapper
    return decorator

# 全局缓存系统实例
_global_cache_system = None

def get_global_cache_system() -> EnhancedCacheSystem:
    """获取全局缓存系统实例"""
    global _global_cache_system

    if _global_cache_system is None:
        # 默认配置
        default_config = {
            'l1_memory': {
                'strategy': 'adaptive',
                'max_size': 10000
            },
            'l2_disk': {
                'enabled': True,
                'cache_dir': './cache',
                'max_size_mb': 1000
            },
            'l3_distributed': {
                'enabled': False
            }
        }
        _global_cache_system = EnhancedCacheSystem(default_config)

    return _global_cache_system

def init_global_cache_system(config: Dict[str, Any]):
    """初始化全局缓存系统"""
    global _global_cache_system
    _global_cache_system = EnhancedCacheSystem(config)
    logger.info("全局缓存系统已初始化")

if __name__ == "__main__":
    # 测试代码
    async def test_cache_system():
        config = {
            'l1_memory': {
                'strategy': 'adaptive',
                'max_size': 1000
            },
            'l2_disk': {
                'enabled': True,
                'cache_dir': './test_cache',
                'max_size_mb': 100
            }
        }

        cache_system = EnhancedCacheSystem(config)

        # 测试基本操作
        await cache_system.put('test_key', 'test_value', ttl=60)
        value = await cache_system.get('test_key')
        print(f"缓存值: {value}")

        # 测试性能报告
        report = cache_system.get_performance_report()
        print(f"性能报告: {json.dumps(report, indent=2)}")

        # 清理
        await cache_system.clear()

    asyncio.run(test_cache_system())
