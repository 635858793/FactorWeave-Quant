#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
智能缓存策略升级

基于机器学习的智能缓存系统，提供LRU缓存、数据预加载、预测性缓存等功能

作者: FactorWeave-Quant团队
版本: 1.0
"""

import numpy as np
import pandas as pd
import time
import threading
import pickle
from utils.safe_pickle import safe_load
import hashlib
from typing import Any, Dict, List, Optional, Callable, Union, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import OrderedDict, defaultdict, deque
from datetime import datetime, timedelta
from loguru import logger
import json
import os
from concurrent.futures import ThreadPoolExecutor
import weakref

class CacheLevel(Enum):
    """缓存层级"""
    L1_MEMORY = "memory"           # L1内存缓存（最快）
    L2_DISK = "disk"              # L2磁盘缓存（中等）
    L3_NETWORK = "network"        # L3网络缓存（较慢）

class PredictionStrategy(Enum):
    """预测策略"""
    FREQUENCY_BASED = "frequency"     # 基于频率
    TIME_BASED = "time"              # 基于时间
    SEQUENCE_BASED = "sequence"      # 基于序列
    ML_BASED = "ml"                  # 机器学习

@dataclass
class CacheMetrics:
    """缓存指标"""
    hit_count: int = 0
    miss_count: int = 0
    hit_rate: float = 0.0
    avg_access_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    disk_usage_mb: float = 0.0
    prediction_accuracy: float = 0.0
    preload_hits: int = 0
    level_stats: Dict[CacheLevel, Dict[str, Any]] = field(default_factory=dict)

@dataclass
class AccessPattern:
    """访问模式"""
    key: str
    access_time: float
    access_count: int = 1
    data_size: int = 0
    access_type: str = "read"
    user_context: Dict[str, Any] = field(default_factory=dict)

class MLPredictor:
    """机器学习预测器"""
    
    def __init__(self):
        self.patterns = {}
        self.weights = {}
        self.access_history = defaultdict(deque)
        self.feature_extractors = []
        
    def extract_features(self, access_pattern: AccessPattern) -> List[float]:
        """提取特征"""
        features = []
        
        # 时间特征
        features.append(access_pattern.access_time)
        
        # 频率特征
        key = access_pattern.key
        recent_accesses = len(self.access_history[key])
        features.append(recent_accesses)
        
        # 大小特征
        features.append(access_pattern.data_size)
        
        # 用户上下文特征
        context_features = list(access_pattern.user_context.values())
        if isinstance(context_features[0], (int, float)):
            features.extend(context_features)
        else:
            features.append(hash(str(context_features)) % 1000)
        
        return features
    
    def predict_next_access(self, recent_keys: List[str]) -> List[Tuple[str, float]]:
        """预测下次访问"""
        predictions = []
        
        for key in recent_keys:
            if key not in self.patterns:
                continue
                
            # 基于历史访问模式计算概率
            pattern = self.patterns[key]
            
            # 简化的概率计算
            score = 0.0
            
            # 访问频率权重
            score += pattern.get('frequency_score', 0.0)
            
            # 时间权重
            time_score = self._calculate_time_score(pattern)
            score += time_score
            
            # 序列权重
            sequence_score = self._calculate_sequence_score(recent_keys, key)
            score += sequence_score
            
            predictions.append((key, score))
        
        # 按概率排序
        predictions.sort(key=lambda x: x[1], reverse=True)
        return predictions[:10]  # 返回前10个预测
    
    def _calculate_time_score(self, pattern: Dict[str, Any]) -> float:
        """计算时间相关性分数"""
        if 'last_access' not in pattern:
            return 0.0
        
        time_since_access = time.time() - pattern['last_access']
        
        # 使用指数衰减
        decay_factor = np.exp(-time_since_access / 3600)  # 1小时半衰期
        return pattern.get('access_count', 0) * decay_factor
    
    def _calculate_sequence_score(self, recent_keys: List[str], target_key: str) -> float:
        """计算序列相关性分数"""
        if len(recent_keys) < 2:
            return 0.0
        
        # 计算目标键在最近访问中的出现模式
        positions = []
        for i, key in enumerate(recent_keys):
            if key == target_key:
                positions.append(i)
        
        if not positions:
            return 0.0
        
        # 简单序列预测：出现在序列末尾的键有更高概率再次出现
        score = 0.0
        for pos in positions:
            if pos == len(recent_keys) - 1:
                score += 1.0
            elif pos == len(recent_keys) - 2:
                score += 0.5
        
        return score
    
    def update_pattern(self, access_pattern: AccessPattern):
        """更新访问模式"""
        key = access_pattern.key
        
        # 记录访问历史
        self.access_history[key].append(access_pattern.access_time)
        
        if len(self.access_history[key]) > 1000:  # 限制历史长度
            self.access_history[key].popleft()
        
        # 更新模式
        if key not in self.patterns:
            self.patterns[key] = {
                'access_count': 0,
                'last_access': access_pattern.access_time,
                'total_size': 0,
                'frequency_score': 0.0,
                'time_buckets': defaultdict(int)
            }
        
        pattern = self.patterns[key]
        pattern['access_count'] += 1
        pattern['last_access'] = access_pattern.access_time
        pattern['total_size'] += access_pattern.data_size
        pattern['frequency_score'] = pattern['access_count'] / max(1, time.time() - pattern['last_access'] + 1)
        
        # 更新时间桶
        hour = datetime.fromtimestamp(access_pattern.access_time).hour
        pattern['time_buckets'][hour] += 1

class L1MemoryCache:
    """L1内存缓存"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.lock = threading.RLock()
        self.stats = {'hits': 0, 'misses': 0, 'evictions': 0}
        
    def get(self, key: str) -> Optional[Any]:
        """获取缓存项"""
        with self.lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                
                # 检查TTL
                if time.time() - timestamp < self.ttl_seconds:
                    # 更新访问顺序
                    self.cache.move_to_end(key)
                    self.stats['hits'] += 1
                    return value
                else:
                    # 过期，删除
                    del self.cache[key]
            
            self.stats['misses'] += 1
            return None
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """设置缓存项"""
        with self.lock:
            if len(self.cache) >= self.max_size and key not in self.cache:
                # 淘汰最久未使用的项
                self.cache.popitem(last=False)
                self.stats['evictions'] += 1
            
            ttl = ttl_seconds or self.ttl_seconds
            self.cache[key] = (value, time.time())
            self.cache.move_to_end(key)
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            total = self.stats['hits'] + self.stats['misses']
            hit_rate = self.stats['hits'] / total if total > 0 else 0.0
            
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'hit_rate': hit_rate,
                'evictions': self.stats['evictions'],
                'level': CacheLevel.L1_MEMORY.value
            }

class L2DiskCache:
    """L2磁盘缓存"""
    
    def __init__(self, cache_dir: str = ".cache_l2", max_size_mb: int = 1024):
        self.cache_dir = cache_dir
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.lock = threading.RLock()
        self.stats = {'hits': 0, 'misses': 0, 'evictions': 0}
        self.index_file = os.path.join(cache_dir, ".index")
        self.index = self._load_index()
        
        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)
    
    def _load_index(self) -> Dict[str, Dict[str, Any]]:
        """加载索引"""
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载索引失败: {e}")
        return {}
    
    def _save_index(self):
        """保存索引"""
        try:
            with open(self.index_file, 'w') as f:
                json.dump(self.index, f)
        except Exception as e:
            logger.error(f"保存索引失败: {e}")
    
    def _get_file_path(self, key: str) -> str:
        """获取文件路径"""
        hashed_key = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{hashed_key}.cache")
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存项"""
        with self.lock:
            file_path = self._get_file_path(key)
            
            if key in self.index and os.path.exists(file_path):
                try:
                    with open(file_path, 'rb') as f:
                        data = safe_load(f)
                    
                    # 检查TTL
                    timestamp = self.index[key].get('timestamp', 0)
                    if time.time() - timestamp < self.index[key].get('ttl', 3600):
                        self.stats['hits'] += 1
                        return data['value']
                    else:
                        # 过期，删除
                        self._remove_key(key)
                        
                except Exception as e:
                    logger.warning(f"读取缓存失败 {key}: {e}")
                    self._remove_key(key)
            
            self.stats['misses'] += 1
            return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = 3600):
        """设置缓存项"""
        with self.lock:
            file_path = self._get_file_path(key)
            
            try:
                # 检查磁盘空间
                if self._get_cache_size() > self.max_size_bytes:
                    self._evict_oldest()
                
                # 写入数据
                data = {
                    'value': value,
                    'timestamp': time.time(),
                    'size': len(pickle.dumps(value))
                }
                
                with open(file_path, 'wb') as f:
                    pickle.dump(data, f)
                
                # 更新索引
                self.index[key] = {
                    'timestamp': time.time(),
                    'ttl': ttl_seconds,
                    'file_path': file_path
                }
                
                self._save_index()
                
            except Exception as e:
                logger.error(f"写入缓存失败 {key}: {e}")
    
    def _remove_key(self, key: str):
        """删除缓存项"""
        if key in self.index:
            file_path = self._get_file_path(key)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.warning(f"删除缓存文件失败: {e}")
            del self.index[key]
    
    def _get_cache_size(self) -> int:
        """获取缓存大小"""
        total_size = 0
        for key, meta in self.index.items():
            file_path = self._get_file_path(key)
            if os.path.exists(file_path):
                total_size += os.path.getsize(file_path)
        return total_size
    
    def _evict_oldest(self):
        """淘汰最老的项"""
        if not self.index:
            return
        
        # 按时间戳排序
        sorted_keys = sorted(
            self.index.keys(),
            key=lambda k: self.index[k]['timestamp']
        )
        
        # 删除最老的几个项
        for key in sorted_keys[:10]:  # 删除10个最老的项
            self._remove_key(key)
            self.stats['evictions'] += 1
        
        self._save_index()
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            for key in list(self.index.keys()):
                self._remove_key(key)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            total = self.stats['hits'] + self.stats['misses']
            hit_rate = self.stats['hits'] / total if total > 0 else 0.0
            
            return {
                'size': len(self.index),
                'cache_size_mb': self._get_cache_size() / (1024 * 1024),
                'max_size_mb': self.max_size_bytes / (1024 * 1024),
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'hit_rate': hit_rate,
                'evictions': self.stats['evictions'],
                'level': CacheLevel.L2_DISK.value
            }

class IntelligentCache:
    """智能缓存主类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # 默认配置
        default_config = {
            'l1_max_size': 1000,
            'l1_ttl': 3600,
            'l2_cache_dir': '.cache_l2',
            'l2_max_size_mb': 1024,
            'prediction_strategy': PredictionStrategy.ML_BASED,
            'preload_enabled': True,
            'preload_batch_size': 50,
            'ml_model_enabled': True,
            'cleanup_interval': 300  # 5分钟清理一次
        }
        
        self.config = {**default_config, **(config or {})}
        
        # 初始化缓存层级
        self.l1_cache = L1MemoryCache(
            max_size=self.config['l1_max_size'],
            ttl_seconds=self.config['l1_ttl']
        )
        self.l2_cache = L2DiskCache(
            cache_dir=self.config['l2_cache_dir'],
            max_size_mb=self.config['l2_max_size_mb']
        )
        
        # 初始化ML预测器
        self.ml_predictor = MLPredictor() if self.config['ml_model_enabled'] else None
        
        # 预加载相关
        self.preload_enabled = self.config['preload_enabled']
        self.preload_batch_size = self.config['preload_batch_size']
        self.preload_workers = ThreadPoolExecutor(max_workers=2)
        self.preload_queue = deque()
        self.preload_stats = {'hits': 0, 'preloads': 0, 'skipped': 0}
        
        # 统计信息
        self.metrics = CacheMetrics()
        self.access_times = deque(maxlen=1000)
        
        # 启动后台任务
        self._start_background_tasks()
        
    def _start_background_tasks(self):
        """启动后台任务"""
        def cleanup_task():
            while True:
                try:
                    time.sleep(self.config['cleanup_interval'])
                    self._cleanup_expired()
                except Exception as e:
                    logger.error(f"缓存清理任务错误: {e}")
        
        # 启动清理线程
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
        
        # 启动预加载任务
        if self.preload_enabled:
            preload_thread = threading.Thread(target=self._preload_loop, daemon=True)
            preload_thread.start()
    
    def get(self, key: str) -> Tuple[Optional[Any], str]:
        """获取缓存项"""
        start_time = time.time()
        
        # 尝试L1缓存
        value = self.l1_cache.get(key)
        if value is not None:
            access_time = (time.time() - start_time) * 1000
            self._record_access(key, "hit_l1", access_time)
            return value, CacheLevel.L1_MEMORY.value
        
        # 尝试L2缓存
        value = self.l2_cache.get(key)
        if value is not None:
            access_time = (time.time() - start_time) * 1000
            self._record_access(key, "hit_l2", access_time)
            
            # 提升到L1缓存
            self.l1_cache.set(key, value)
            return value, CacheLevel.L2_DISK.value
        
        # 缓存未命中
        access_time = (time.time() - start_time) * 1000
        self._record_access(key, "miss", access_time)
        return None, "none"
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None,
            preload_hints: Optional[List[str]] = None):
        """设置缓存项"""
        # 计算数据大小
        data_size = len(pickle.dumps(value))
        
        # 设置到L1缓存
        self.l1_cache.set(key, value, ttl_seconds)
        
        # 设置到L2缓存
        self.l2_cache.set(key, value, ttl_seconds or 3600)
        
        # 更新ML模型
        if self.ml_predictor:
            access_pattern = AccessPattern(
                key=key,
                access_time=time.time(),
                data_size=data_size
            )
            self.ml_predictor.update_pattern(access_pattern)
        
        # 预加载提示
        if preload_hints and self.preload_enabled:
            for hint_key in preload_hints:
                self._add_preload_hint(key, hint_key)
    
    def _record_access(self, key: str, access_type: str, access_time_ms: float):
        """记录访问"""
        self.access_times.append({
            'key': key,
            'access_type': access_type,
            'access_time_ms': access_time_ms,
            'timestamp': time.time()
        })
        
        # 更新指标
        if access_type.startswith('hit'):
            self.metrics.hit_count += 1
            self.metrics.preload_hits += 1 if access_type == 'preload_hit' else 0
        else:
            self.metrics.miss_count += 1
        
        # 计算平均访问时间
        total_accesses = len(self.access_times)
        if total_accesses > 0:
            avg_time = sum(a['access_time_ms'] for a in self.access_times) / total_accesses
            self.metrics.avg_access_time_ms = avg_time
        
        # 计算命中率
        total_requests = self.metrics.hit_count + self.metrics.miss_count
        if total_requests > 0:
            self.metrics.hit_rate = self.metrics.hit_count / total_requests
    
    def predict_and_preload(self, recent_keys: List[str]) -> List[str]:
        """预测并预加载数据"""
        if not self.ml_predictor:
            return []
        
        try:
            # 获取预测结果
            predictions = self.ml_predictor.predict_next_access(recent_keys)
            
            predicted_keys = []
            for key, score in predictions:
                # 检查是否已经在缓存中
                if self.get(key)[0] is None:
                    predicted_keys.append(key)
            
            # 添加到预加载队列
            for key in predicted_keys[:self.preload_batch_size]:
                self.preload_queue.append(key)
                self.preload_stats['preloads'] += 1
            
            return predicted_keys
            
        except Exception as e:
            logger.error(f"预加载预测失败: {e}")
            return []
    
    def _preload_loop(self):
        """预加载循环"""
        while True:
            try:
                if not self.preload_queue:
                    time.sleep(1)
                    continue
                
                # 从队列中获取预加载项
                preload_keys = []
                for _ in range(min(self.preload_batch_size, len(self.preload_queue))):
                    if self.preload_queue:
                        preload_keys.append(self.preload_queue.popleft())
                
                # 执行预加载（这里应该调用数据获取函数）
                for key in preload_keys:
                    self._execute_preload(key)
                
                time.sleep(0.1)  # 短暂休息
                
            except Exception as e:
                logger.error(f"预加载循环错误: {e}")
                time.sleep(1)
    
    def _execute_preload(self, key: str):
        """执行预加载"""
        try:
            logger.debug(f"预加载数据: {key}")

            logger.warning(
                f"预加载功能尚未实现真实数据加载器，键 '{key}' 存入了空占位标记。"
                "请根据实际业务逻辑实现具体的数据获取逻辑。"
            )
            self.l1_cache.set(key, None, ttl_seconds=1800)
            self.preload_stats['hits'] += 1

        except Exception as e:
            logger.error(f"预加载失败 {key}: {e}")
            self.preload_stats['skipped'] += 1
    
    def _add_preload_hint(self, current_key: str, hint_key: str):
        """添加预加载提示"""
        # 基于访问模式的智能提示
        if self.ml_predictor:
            # 记录访问关系
            hint_pattern = f"{current_key}->{hint_key}"
            # 这里可以扩展更复杂的模式识别逻辑
    
    def _cleanup_expired(self):
        """清理过期缓存"""
        # L1缓存的清理由其内部TTL机制处理
        # L2缓存的清理也需要定期触发
        logger.debug("执行缓存清理")
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """获取全面统计信息"""
        l1_stats = self.l1_cache.get_stats()
        l2_stats = self.l2_cache.get_stats()
        
        # 合并统计信息
        comprehensive_stats = {
            'overall': {
                'total_hit_rate': self.metrics.hit_rate,
                'avg_access_time_ms': self.metrics.avg_access_time_ms,
                'total_requests': self.metrics.hit_count + self.metrics.miss_count
            },
            'l1_cache': l1_stats,
            'l2_cache': l2_stats,
            'preload': {
                'enabled': self.preload_enabled,
                'hits': self.preload_stats['hits'],
                'preloads': self.preload_stats['preloads'],
                'skipped': self.preload_stats['skipped'],
                'queue_size': len(self.preload_queue)
            },
            'ml_prediction': {
                'enabled': self.ml_predictor is not None,
                'patterns_count': len(self.ml_predictor.patterns) if self.ml_predictor else 0
            }
        }
        
        return comprehensive_stats
    
    def invalidate_key(self, key: str):
        """使缓存键失效"""
        # 从所有层级删除
        if key in self.l1_cache.cache:
            del self.l1_cache.cache[key]
        
        self.l2_cache._remove_key(key)
        
        # 从ML模式中删除
        if self.ml_predictor and key in self.ml_predictor.patterns:
            del self.ml_predictor.patterns[key]
    
    def clear_all(self):
        """清空所有缓存"""
        self.l1_cache.clear()
        self.l2_cache.clear()
        self.preload_queue.clear()
        
        # 重置ML模型
        if self.ml_predictor:
            self.ml_predictor.patterns.clear()
    
    def export_stats(self, file_path: str):
        """导出统计信息"""
        stats = self.get_comprehensive_stats()
        with open(file_path, 'w') as f:
            json.dump(stats, f, indent=2, default=str)
        
        logger.info(f"缓存统计已导出到: {file_path}")

# 便捷函数
def create_intelligent_cache(**kwargs) -> IntelligentCache:
    """创建智能缓存实例"""
    return IntelligentCache(kwargs)

def create_performance_cache() -> IntelligentCache:
    """创建性能优化缓存"""
    config = {
        'l1_max_size': 2000,
        'l1_ttl': 7200,  # 2小时
        'l2_max_size_mb': 2048,  # 2GB
        'preload_enabled': True,
        'preload_batch_size': 100,
        'ml_model_enabled': True,
        'cleanup_interval': 600  # 10分钟清理一次
    }
    return IntelligentCache(config)