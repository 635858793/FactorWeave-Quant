#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
图表性能优化器

专门优化图表渲染性能，包括数据缓冲、渲染频率控制、内存管理等

作者: FactorWeave-Quant团队
版本: 1.0
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import threading
import time
from loguru import logger

from .pyqtgraph_engine import PyQtGraphEngine, PyQtGraphChartWidget
from ...events.event_bus import EventBus
from ...events.types import Event, EventType


class OptimizationStrategy(Enum):
    """优化策略枚举"""
    LAZY_LOADING = "lazy_loading"
    DATA_SAMPLING = "data_sampling"
    FREQUENCY_CONTROL = "frequency_control"
    MEMORY_MANAGEMENT = "memory_management"
    BATCH_UPDATES = "batch_updates"
    CACHE_OPTIMIZATION = "cache_optimization"


@dataclass
class PerformanceConfig:
    """性能配置"""
    # 渲染优化
    max_fps: int = 30  # 最大帧率
    render_throttle_ms: int = 33  # 渲染节流时间(毫秒)
    
    # 数据优化
    max_data_points: int = 10000  # 最大数据点
    sampling_rate: float = 1.0  # 采样率
    batch_size: int = 100  # 批处理大小
    
    # 内存优化
    memory_limit_mb: int = 512  # 内存限制(MB)
    cleanup_threshold: float = 0.8  # 清理阈值
    
    # 缓存优化
    enable_caching: bool = True
    cache_size: int = 1000  # 缓存大小
    cache_ttl_seconds: int = 300  # 缓存生存时间
    
    # 实时优化
    realtime_buffer_size: int = 1000  # 实时缓冲大小
    adaptive_quality: bool = True  # 自适应质量


@dataclass 
class OptimizationMetrics:
    """优化指标"""
    avg_render_time: float = 0.0
    fps: float = 0.0
    memory_usage_mb: float = 0.0
    data_points_count: int = 0
    cache_hit_rate: float = 0.0
    optimization_level: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


class DataBuffer:
    """数据缓冲器"""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.RLock()
        self.stats = {
            'add_count': 0,
            'remove_count': 0,
            'overflow_count': 0
        }
        
    def add(self, data: Any):
        """添加数据"""
        with self.lock:
            try:
                # 检查是否需要移除旧数据
                if len(self.buffer) >= self.max_size:
                    self.buffer.popleft()
                    self.stats['remove_count'] += 1
                    
                self.buffer.append(data)
                self.stats['add_count'] += 1
                
            except Exception as e:
                logger.error(f"数据缓冲器添加数据失败: {e}")
                self.stats['overflow_count'] += 1
                
    def get_all(self) -> List[Any]:
        """获取所有数据"""
        with self.lock:
            return list(self.buffer)
            
    def clear(self):
        """清空缓冲器"""
        with self.lock:
            self.buffer.clear()
            
    def size(self) -> int:
        """获取缓冲器大小"""
        with self.lock:
            return len(self.buffer)
            
    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return self.stats.copy()


class ChartPerformanceOptimizer:
    """图表性能优化器"""
    
    def __init__(self, config: Optional[PerformanceConfig] = None, event_bus: Optional[EventBus] = None):
        self.config = config or PerformanceConfig()
        self.event_bus = event_bus
        
        # 性能状态
        self.is_enabled = True
        self.current_strategy = OptimizationStrategy.FREQUENCY_CONTROL
        self.last_render_time = 0.0
        self.frame_count = 0
        self.fps_start_time = time.time()
        
        # 数据缓冲
        self.data_buffers: Dict[str, DataBuffer] = {}
        self.cache: Dict[str, Any] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        
        # 优化指标
        self.metrics = OptimizationMetrics()
        
        # 线程安全
        self.lock = threading.RLock()
        
        # 性能监控线程
        self.monitoring_thread = None
        self.is_monitoring = False
        
        logger.info("图表性能优化器初始化完成")
        
    def enable_optimization(self, strategy: Optional[OptimizationStrategy] = None):
        """启用优化"""
        try:
            self.is_enabled = True
            if strategy:
                self.current_strategy = strategy
                
            # 启动性能监控
            self._start_monitoring()
            
            logger.info(f"性能优化已启用，策略: {self.current_strategy.value}")
            
        except Exception as e:
            logger.error(f"启用性能优化失败: {e}")
            
    def disable_optimization(self):
        """禁用优化"""
        try:
            self.is_enabled = False
            self._stop_monitoring()
            logger.info("性能优化已禁用")
            
        except Exception as e:
            logger.error(f"禁用性能优化失败: {e}")
            
    def optimize_chart_data(self, chart_id: str, data: Any) -> Any:
        """优化图表数据"""
        try:
            if not self.is_enabled:
                return data
                
            with self.lock:
                # 1. 数据采样
                if self.current_strategy == OptimizationStrategy.DATA_SAMPLING:
                    data = self._apply_sampling(data)
                    
                # 2. 批处理优化
                elif self.current_strategy == OptimizationStrategy.BATCH_UPDATES:
                    data = self._apply_batch_optimization(chart_id, data)
                    
                # 3. 缓存优化
                elif self.current_strategy == OptimizationStrategy.CACHE_OPTIMIZATION:
                    data = self._apply_cache_optimization(chart_id, data)
                    
                # 4. 懒加载优化
                elif self.current_strategy == OptimizationStrategy.LAZY_LOADING:
                    data = self._apply_lazy_loading(chart_id, data)
                    
                # 5. 内存管理
                elif self.current_strategy == OptimizationStrategy.MEMORY_MANAGEMENT:
                    data = self._apply_memory_management(data)
                    
            return data
            
        except Exception as e:
            logger.error(f"优化图表数据失败 {chart_id}: {e}")
            return data
            
    def should_render(self, chart_id: str) -> bool:
        """判断是否应该渲染"""
        try:
            if not self.is_enabled:
                return True
                
            current_time = time.time() * 1000  # 毫秒
            time_since_last = current_time - self.last_render_time
            
            # 频率控制
            if self.current_strategy == OptimizationStrategy.FREQUENCY_CONTROL:
                min_interval = 1000.0 / self.config.max_fps
                if time_since_last < min_interval:
                    return False
                    
            self.last_render_time = current_time
            self.frame_count += 1
            
            # 计算FPS
            if time.time() - self.fps_start_time >= 1.0:  # 每秒更新一次
                self.metrics.fps = self.frame_count / (time.time() - self.fps_start_time)
                self.frame_count = 0
                self.fps_start_time = time.time()
                
            return True
            
        except Exception as e:
            logger.error(f"判断渲染条件失败: {e}")
            return True
            
    def get_optimization_level(self) -> int:
        """获取优化级别"""
        try:
            # 基于性能指标计算优化级别
            if not self.is_enabled:
                return 0
                
            level = 0
            
            # 根据FPS调整
            if self.metrics.fps < 15:  # 低FPS
                level += 3
            elif self.metrics.fps < 25:
                level += 2
            elif self.metrics.fps < 30:
                level += 1
                
            # 根据内存使用调整
            memory_usage_pct = self.metrics.memory_usage_mb / (self.config.memory_limit_mb * 1024)
            if memory_usage_pct > 0.9:
                level += 2
            elif memory_usage_pct > 0.7:
                level += 1
                
            self.metrics.optimization_level = min(level, 5)  # 最大5级
            return self.metrics.optimization_level
            
        except Exception as e:
            logger.error(f"获取优化级别失败: {e}")
            return 0
            
    def get_buffer_size(self, chart_id: str) -> int:
        """获取图表数据缓冲大小"""
        try:
            if chart_id in self.data_buffers:
                return self.data_buffers[chart_id].size()
            return 0
            
        except Exception as e:
            logger.error(f"获取缓冲大小失败: {e}")
            return 0
            
    def clear_chart_buffer(self, chart_id: str):
        """清空图表数据缓冲"""
        try:
            if chart_id in self.data_buffers:
                self.data_buffers[chart_id].clear()
                logger.debug(f"清空图表缓冲成功: {chart_id}")
                
        except Exception as e:
            logger.error(f"清空图表缓冲失败 {chart_id}: {e}")
            
    def get_performance_metrics(self) -> OptimizationMetrics:
        """获取性能指标"""
        return self.metrics
        
    def apply_adaptive_optimization(self):
        """应用自适应优化"""
        try:
            if not self.config.adaptive_quality:
                return
                
            optimization_level = self.get_optimization_level()
            
            if optimization_level >= 4:
                # 高优化级别：增加采样率，减少数据点
                self.config.sampling_rate = max(0.1, self.config.sampling_rate * 0.8)
                self.config.max_data_points = max(1000, int(self.config.max_data_points * 0.8))
                logger.info("应用高级优化策略")
                
            elif optimization_level >= 2:
                # 中等优化级别：轻微调整
                self.config.sampling_rate = max(0.5, self.config.sampling_rate * 0.9)
                
            elif optimization_level <= 1:
                # 低优化级别：可以降低采样率
                self.config.sampling_rate = min(2.0, self.config.sampling_rate * 1.1)
                self.config.max_data_points = min(20000, int(self.config.max_data_points * 1.1))
                
        except Exception as e:
            logger.error(f"应用自适应优化失败: {e}")
            
    def _apply_sampling(self, data: Any) -> Any:
        """应用数据采样"""
        try:
            if not isinstance(data, (list, np.ndarray, pd.DataFrame)):
                return data
                
            if isinstance(data, list):
                step = max(1, int(1 / self.config.sampling_rate))
                return data[::step]
                
            elif isinstance(data, np.ndarray):
                step = max(1, int(1 / self.config.sampling_rate))
                return data[::step]
                
            elif isinstance(data, pd.DataFrame):
                step = max(1, int(1 / self.config.sampling_rate))
                return data.iloc[::step]
                
            return data
            
        except Exception as e:
            logger.error(f"应用数据采样失败: {e}")
            return data
            
    def _apply_batch_optimization(self, chart_id: str, data: Any) -> Any:
        """应用批处理优化"""
        try:
            if chart_id not in self.data_buffers:
                self.data_buffers[chart_id] = DataBuffer(self.config.batch_size)
                
            self.data_buffers[chart_id].add(data)
            
            # 检查是否达到批处理大小
            if self.data_buffers[chart_id].size() >= self.config.batch_size:
                batch_data = self.data_buffers[chart_id].get_all()
                self.data_buffers[chart_id].clear()
                return batch_data
                
            return None  # 暂不渲染，等待批处理
            
        except Exception as e:
            logger.error(f"应用批处理优化失败: {e}")
            return data
            
    def _apply_cache_optimization(self, chart_id: str, data: Any) -> Any:
        """应用缓存优化"""
        try:
            cache_key = f"{chart_id}_{hash(str(data))}"
            
            # 检查缓存
            if cache_key in self.cache:
                # 更新缓存时间戳
                self.cache_timestamps[cache_key] = datetime.now()
                self.metrics.cache_hit_rate = min(1.0, self.metrics.cache_hit_rate + 0.01)
                return self.cache[cache_key]
                
            # 添加到缓存
            if len(self.cache) >= self.config.cache_size:
                self._cleanup_cache()
                
            self.cache[cache_key] = data
            self.cache_timestamps[cache_key] = datetime.now()
            
            return data
            
        except Exception as e:
            logger.error(f"应用缓存优化失败: {e}")
            return data
            
    def _apply_lazy_loading(self, chart_id: str, data: Any) -> Any:
        """应用懒加载"""
        try:
            # 只加载可见区域的数据
            if isinstance(data, (list, pd.DataFrame)) and len(data) > self.config.max_data_points:
                # 计算合适的采样
                step = len(data) // self.config.max_data_points
                step = max(1, step)
                
                if isinstance(data, list):
                    return data[::step]
                else:
                    return data.iloc[::step]
                    
            return data
            
        except Exception as e:
            logger.error(f"应用懒加载失败: {e}")
            return data
            
    def _apply_memory_management(self, data: Any) -> Any:
        """应用内存管理"""
        try:
            import psutil
            import os
            
            # 获取当前进程内存使用
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            self.metrics.memory_usage_mb = memory_mb
            
            # 检查内存使用率
            memory_usage_pct = memory_mb / (self.config.memory_limit_mb * 1024)
            
            if memory_usage_pct > self.config.cleanup_threshold:
                # 清理缓存
                self._cleanup_cache()
                
                # 清理数据缓冲
                for buffer in self.data_buffers.values():
                    if buffer.size() > self.config.realtime_buffer_size // 2:
                        # 保留一半数据
                        remaining_data = buffer.get_all()[-self.config.realtime_buffer_size//2:]
                        buffer.clear()
                        for item in remaining_data:
                            buffer.add(item)
                            
                logger.info(f"内存使用过高({memory_mb:.1f}MB)，已执行清理")
                
            return data
            
        except ImportError:
            # 如果没有psutil，跳过内存管理
            return data
        except Exception as e:
            logger.error(f"应用内存管理失败: {e}")
            return data
            
    def _cleanup_cache(self):
        """清理缓存"""
        try:
            current_time = datetime.now()
            expired_keys = []
            
            # 查找过期缓存
            for key, timestamp in self.cache_timestamps.items():
                age_seconds = (current_time - timestamp).total_seconds()
                if age_seconds > self.config.cache_ttl_seconds:
                    expired_keys.append(key)
                    
            # 清理过期缓存
            for key in expired_keys:
                self.cache.pop(key, None)
                self.cache_timestamps.pop(key, None)
                
            # 如果缓存仍然过大，清理最旧的
            if len(self.cache) > self.config.cache_size // 2:
                sorted_keys = sorted(
                    self.cache_timestamps.items(), 
                    key=lambda x: x[1]
                )
                
                # 清理一半最旧的
                keys_to_remove = [key for key, _ in sorted_keys[:len(sorted_keys)//2]]
                for key in keys_to_remove:
                    self.cache.pop(key, None)
                    self.cache_timestamps.pop(key, None)
                    
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")
            
    def _start_monitoring(self):
        """启动性能监控"""
        try:
            if not self.is_monitoring:
                self.is_monitoring = True
                self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
                self.monitoring_thread.start()
                
        except Exception as e:
            logger.error(f"启动性能监控失败: {e}")
            
    def _stop_monitoring(self):
        """停止性能监控"""
        try:
            self.is_monitoring = False
            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=1.0)
                
        except Exception as e:
            logger.error(f"停止性能监控失败: {e}")
            
    def _monitoring_loop(self):
        """监控循环"""
        try:
            while self.is_monitoring:
                # 更新性能指标
                self._update_performance_metrics()
                
                # 应用自适应优化
                self.apply_adaptive_optimization()
                
                # 发送性能事件
                self._emit_performance_event()
                
                time.sleep(1.0)  # 每秒检查一次
                
        except Exception as e:
            logger.error(f"性能监控循环异常: {e}")
            
    def _update_performance_metrics(self):
        """更新性能指标"""
        try:
            # 更新平均渲染时间
            if hasattr(self, '_render_times'):
                recent_times = self._render_times[-10:]  # 最近10次渲染时间
                self.metrics.avg_render_time = sum(recent_times) / len(recent_times)
                
            self.metrics.last_updated = datetime.now()
            
        except Exception as e:
            logger.error(f"更新性能指标失败: {e}")
            
    def _emit_performance_event(self):
        """发送性能事件"""
        try:
            if self.event_bus:
                event = Event(
                    type=EventType.PERFORMANCE_OPTIMIZED,
                    data={
                        'metrics': {
                            'fps': self.metrics.fps,
                            'memory_usage_mb': self.metrics.memory_usage_mb,
                            'optimization_level': self.metrics.optimization_level,
                            'cache_hit_rate': self.metrics.cache_hit_rate
                        },
                        'config': {
                            'sampling_rate': self.config.sampling_rate,
                            'max_data_points': self.config.max_data_points,
                            'current_strategy': self.current_strategy.value
                        }
                    }
                )
                self.event_bus.publish(event)
                
        except Exception as e:
            logger.error(f"发送性能事件失败: {e}")


# 导出的公共接口
__all__ = [
    'ChartPerformanceOptimizer',
    'PerformanceConfig',
    'OptimizationMetrics',
    'OptimizationStrategy',
    'DataBuffer'
]