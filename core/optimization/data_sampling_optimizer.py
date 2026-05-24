#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据采样和聚合策略优化器

实现智能数据采样和聚合策略，优化大数据集渲染性能

作者: FactorWeave-Quant团队
版本: 2.0
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
from loguru import logger
import time
from concurrent.futures import ThreadPoolExecutor
import threading

class SamplingStrategy(Enum):
    """数据采样策略"""
    NO_SAMPLING = "no_sampling"          # 不采样（保留所有数据）
    FIXED_STEP = "fixed_step"            # 固定步长采样
    LTTB = "lttb"                        # Largest-Triangle-Three-Buckets算法
    ADAPTIVE = "adaptive"                # 自适应采样
    VIEWPORT_BASED = "viewport_based"    # 基于视口的采样

class AggregationMethod(Enum):
    """数据聚合方法"""
    FIRST = "first"                      # 第一个值
    LAST = "last"                        # 最后一个值
    MIN = "min"                          # 最小值
    MAX = "max"                          # 最大值
    MEAN = "mean"                        # 平均值
    SUM = "sum"                          # 总和
    OHLC = "ohlc"                        # 开盘、最高、最低、收盘（适用于股价数据）
    WEIGHTED = "weighted"                # 加权平均

@dataclass
class SamplingConfig:
    """数据采样配置"""
    # 采样策略
    strategy: SamplingStrategy = SamplingStrategy.ADAPTIVE
    aggregation_method: AggregationMethod = AggregationMethod.MEAN
    
    # 阈值设置
    max_points_displayed: int = 5000     # 最大显示点数
    min_sample_ratio: float = 0.001      # 最小采样比例
    max_sample_ratio: float = 1.0        # 最大采样比例
    
    # 性能优化
    enable_threaded_sampling: bool = True
    chunk_size: int = 10000              # 分块处理大小
    cache_enabled: bool = True
    
    # 自适应参数
    performance_threshold_ms: float = 50.0  # 性能阈值（毫秒）
    quality_boost_factor: float = 0.8       # 质量提升因子

class DataChunk:
    """数据块"""
    def __init__(self, data: pd.DataFrame, start_idx: int, end_idx: int):
        self.data = data
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.aggregated = False
    
    def __len__(self):
        return len(self.data)

class DataAggregator:
    """数据聚合器"""
    
    def __init__(self, config: SamplingConfig):
        self.config = config
        self.executor = ThreadPoolExecutor(max_workers=4) if config.enable_threaded_sampling else None
        self._cache = {}
        self._cache_lock = threading.Lock()
    
    def aggregate_data(self, data: pd.DataFrame, target_points: int = None) -> pd.DataFrame:
        """聚合数据"""
        if len(data) == 0:
            return data

        if target_points is not None and target_points <= 0:
            logger.warning(f"无效的目标点数 {target_points}，使用默认值")
            target_points = None
        
        start_time = time.time()
        
        # 缓存检查
        cache_key = self._generate_cache_key(data, target_points)
        if self.config.cache_enabled:
            with self._cache_lock:
                if cache_key in self._cache:
                    logger.debug("使用缓存的聚合数据")
                    return self._cache[cache_key]
        
        # 目标点数
        if target_points is None:
            target_points = min(self.config.max_points_displayed, len(data))
        
        # 选择采样策略
        if self.config.strategy == SamplingStrategy.NO_SAMPLING or len(data) <= target_points:
            result = data
        elif self.config.strategy == SamplingStrategy.FIXED_STEP:
            result = self._fixed_step_sampling(data, target_points)
        elif self.config.strategy == SamplingStrategy.LTTB:
            result = self._lttb_sampling(data, target_points)
        elif self.config.strategy == SamplingStrategy.VIEWPORT_BASED:
            result = self._viewport_based_sampling(data, target_points)
        else:  # ADAPTIVE
            result = self._adaptive_sampling(data, target_points)
        
        # 缓存结果
        if self.config.cache_enabled and len(result) < len(data):
            with self._cache_lock:
                self._cache[cache_key] = result
        
        process_time = time.time() - start_time
        logger.debug(f"数据聚合完成: {len(data)} -> {len(result)} 个数据点，耗时 {process_time*1000:.2f}ms")
        
        return result
    
    def _fixed_step_sampling(self, data: pd.DataFrame, target_points: int) -> pd.DataFrame:
        """固定步长采样"""
        step = max(1, len(data) // target_points)
        return data.iloc[::step].reset_index(drop=True)
    
    def _lttb_sampling(self, data: pd.DataFrame, target_points: int) -> pd.DataFrame:
        """Largest-Triangle-Three-Buckets (LTTB) 降采样算法

        将数据点按target_points分桶，每个桶内选择能形成最大三角形面积的点保留。
        相比等距采样，LTTB能更好地保留数据的视觉特征（峰值、谷值、趋势变化）。

        算法复杂度: O(n)
        参考: Steinarsson, 2013, "Downsampling Time Series for Visual Representation"
        """
        n = len(data)
        if n <= target_points:
            return data

        if target_points < 3:
            return self._fixed_step_sampling(data, target_points)

        value_col = data.select_dtypes(include=[np.number]).columns[0]
        y = data[value_col].values.astype(np.float64)
        x = np.arange(n, dtype=np.float64)

        threshold = target_points - 2
        bucket_size = (n - 2) / threshold

        sampled = np.empty(target_points, dtype=np.int64)
        sampled[0] = 0
        sampled[target_points - 1] = n - 1

        a = 0
        for i in range(threshold):
            bucket_start = int(np.floor((i + 1) * bucket_size)) + 1
            bucket_end = int(np.floor((i + 2) * bucket_size)) + 1
            bucket_end = min(bucket_end, n - 1)

            next_bucket_start = bucket_end
            next_bucket_end = int(np.floor((i + 3) * bucket_size)) + 1
            next_bucket_end = min(next_bucket_end, n)

            avg_x = np.mean(x[next_bucket_start:next_bucket_end])
            avg_y = np.mean(y[next_bucket_start:next_bucket_end])

            max_area = -1.0
            max_area_idx = bucket_start

            prev_x = x[a]
            prev_y = y[a]

            for j in range(bucket_start, bucket_end):
                area = abs(
                    (prev_x - avg_x) * (y[j] - prev_y) -
                    (prev_x - x[j]) * (avg_y - prev_y)
                ) * 0.5

                if area > max_area:
                    max_area = area
                    max_area_idx = j

            sampled[i + 1] = max_area_idx
            a = max_area_idx

        return data.iloc[sampled].reset_index(drop=True)
    
    def _viewport_based_sampling(self, data: pd.DataFrame, target_points: int) -> pd.DataFrame:
        """基于视口的采样"""
        # 这里应该根据当前视口范围进行采样
        # 目前实现一个简化版本
        return self._fixed_step_sampling(data, target_points)
    
    def _adaptive_sampling(self, data: pd.DataFrame, target_points: int) -> pd.DataFrame:
        """自适应采样"""
        data_size = len(data)
        
        # 根据数据大小动态调整采样策略
        if data_size <= target_points:
            # 数据不大，全部保留
            return data
        elif data_size <= target_points * 2:
            # 数据适中，使用中等采样密度
            return self._fixed_step_sampling(data, target_points)
        elif data_size <= target_points * 10:
            # 数据较大，使用较高采样密度
            return self._lttb_sampling(data, target_points)
        else:
            # 数据非常大，使用高密度采样
            return self._lttb_sampling(data, target_points // 2)
    
    def _generate_cache_key(self, data: pd.DataFrame, target_points: int) -> str:
        """生成缓存键"""
        # 基于数据的内容哈希和目标点数生成缓存键
        try:
            content_hash = hash(str(data.values.tobytes()))
            return f"{content_hash}_{target_points}"
        except Exception:
            return f"{id(data)}_{target_points}"
    
    def _aggregate_chunk(self, chunk: DataChunk) -> pd.DataFrame:
        """聚合单个数据块"""
        if len(chunk) <= 1:
            return chunk.data
        
        method = self.config.aggregation_method
        
        try:
            if method == AggregationMethod.FIRST:
                result = chunk.data.iloc[[0]]
            elif method == AggregationMethod.LAST:
                result = chunk.data.iloc[[-1]]
            elif method == AggregationMethod.MIN:
                result = pd.DataFrame([chunk.data.min()])
            elif method == AggregationMethod.MAX:
                result = pd.DataFrame([chunk.data.max()])
            elif method == AggregationMethod.MEAN:
                result = pd.DataFrame([chunk.data.mean()])
            elif method == AggregationMethod.SUM:
                result = pd.DataFrame([chunk.data.sum()])
            elif method == AggregationMethod.OHLC and 'open' in chunk.data.columns:
                # OHLC聚合（适用于股价数据）
                result = pd.DataFrame({
                    'open': [chunk.data['open'].iloc[0]],
                    'high': [chunk.data['high'].max()],
                    'low': [chunk.data['low'].min()],
                    'close': [chunk.data['close'].iloc[-1]],
                    'volume': [chunk.data['volume'].sum()]
                })
            else:
                # 默认使用平均值
                result = pd.DataFrame([chunk.data.mean()])
            
            # 保留索引信息
            result.index = [chunk.start_idx]
            return result
            
        except Exception as e:
            logger.warning(f"数据块聚合失败: {e}")
            return chunk.data.head(1)
    
    def cleanup(self):
        """清理资源"""
        if self.executor:
            self.executor.shutdown(wait=True)
        
        with self._cache_lock:
            self._cache.clear()

class AdaptiveDataOptimizer:
    """自适应数据优化器"""
    
    def __init__(self, config: SamplingConfig = None):
        self.config = config or SamplingConfig()
        self.aggregator = DataAggregator(self.config)
        
        # 性能历史记录
        self.render_times = []
        self.optimization_stats = {
            'total_samples_taken': 0,
            'total_data_points_processed': 0,
            'avg_compression_ratio': 0.0,
            'last_optimization_time': 0.0
        }
    
    def optimize_for_performance(self, data: pd.DataFrame, render_time_target: float = None) -> pd.DataFrame:
        """根据性能目标优化数据"""
        if render_time_target is None:
            render_time_target = self.config.performance_threshold_ms
        elif render_time_target <= 0:
            logger.warning(f"无效的渲染时间目标 {render_time_target}，使用默认值")
            render_time_target = self.config.performance_threshold_ms
        
        # 记录原始数据大小
        original_size = len(data)
        self.optimization_stats['total_data_points_processed'] += original_size
        
        # 基于性能历史调整采样参数
        if len(self.render_times) > 0:
            recent_avg_time = np.mean(self.render_times[-10:])
            if recent_avg_time > render_time_target * 1.2:
                # 性能不足，增加采样
                self.config.max_points_displayed = max(1000, int(self.config.max_points_displayed * 0.8))
                logger.info(f"性能不足，调整最大显示点数为: {self.config.max_points_displayed}")
            elif recent_avg_time < render_time_target * 0.8:
                # 性能良好，可以提高质量
                self.config.max_points_displayed = min(self.config.max_points_displayed * 1.2, original_size)
                logger.info(f"性能良好，调整最大显示点数为: {self.config.max_points_displayed}")
        
        # 执行数据优化
        start_time = time.time()
        optimized_data = self.aggregator.aggregate_data(data)
        optimization_time = time.time() - start_time
        
        # 更新统计信息
        if original_size > 0:
            compression_ratio = len(optimized_data) / original_size
        else:
            compression_ratio = 0.0
        self.optimization_stats['total_samples_taken'] += len(optimized_data)
        if self.optimization_stats['total_samples_taken'] > 0:
            self.optimization_stats['avg_compression_ratio'] = (
                (self.optimization_stats['avg_compression_ratio'] * (self.optimization_stats['total_samples_taken'] - len(optimized_data)) +
                 compression_ratio * len(optimized_data)) / self.optimization_stats['total_samples_taken']
            )
        else:
            self.optimization_stats['avg_compression_ratio'] = 0.0
        self.optimization_stats['last_optimization_time'] = optimization_time
        
        logger.info(f"数据优化完成: {original_size} -> {len(optimized_data)} "
                   f"(压缩比: {compression_ratio:.2%}, 耗时: {optimization_time*1000:.2f}ms)")
        
        return optimized_data
    
    def record_render_time(self, render_time_ms: float):
        """记录渲染时间"""
        self.render_times.append(render_time_ms)
        
        # 保持最近100次的记录
        if len(self.render_times) > 100:
            self.render_times = self.render_times[-100:]
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """获取优化统计信息"""
        stats = self.optimization_stats.copy()
        stats.update({
            'current_max_points': self.config.max_points_displayed,
            'recent_avg_render_time': np.mean(self.render_times[-10:]) if self.render_times else 0.0,
            'cache_size': len(self.aggregator._cache)
        })
        return stats
    
    def cleanup(self):
        """清理资源"""
        self.aggregator.cleanup()

# 便捷函数
def create_data_optimizer(data_size: int = None, performance_requirement: str = "balanced") -> AdaptiveDataOptimizer:
    """创建数据优化器"""
    valid_requirements = {"high_quality", "high_speed", "balanced"}
    if performance_requirement not in valid_requirements:
        logger.warning(f"无效的性能需求 '{performance_requirement}'，使用默认值 'balanced'")
        performance_requirement = "balanced"

    if performance_requirement == "high_quality":
        config = SamplingConfig(
            strategy=SamplingStrategy.ADAPTIVE,
            max_points_displayed=8000 if data_size else 8000,
            performance_threshold_ms=80.0
        )
    elif performance_requirement == "high_speed":
        config = SamplingConfig(
            strategy=SamplingStrategy.FIXED_STEP,
            max_points_displayed=2000 if data_size else 2000,
            performance_threshold_ms=30.0
        )
    else:  # balanced
        config = SamplingConfig(
            strategy=SamplingStrategy.ADAPTIVE,
            max_points_displayed=5000 if data_size else 5000,
            performance_threshold_ms=50.0
        )
    
    return AdaptiveDataOptimizer(config)