#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
虚拟滚动优化器

专门针对大数据量图表渲染的虚拟滚动技术，提供高效的数据可视化和交互性能

作者: FactorWeave-Quant团队
版本: 1.0
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Union, Callable, Protocol, TypeVar
from dataclasses import dataclass
from enum import Enum
from PyQt5.QtCore import QObject, pyqtSignal, QRectF, QPointF, QTimer
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem
from loguru import logger
import time
from collections import deque, OrderedDict
import threading

# 通用类型定义
T = TypeVar('T')  # 数据点类型

class ViewportState(Enum):
    """视口状态枚举"""
    IDLE = "idle"
    SCROLLING = "scrolling"
    ZOOMING = "zooming"
    LOADING = "loading"

@dataclass
class RenderChunk:
    """渲染块数据结构"""
    start_index: int
    end_index: int
    data_points: np.ndarray
    bounding_rect: QRectF
    render_time: float
    is_visible: bool = True
    quality_level: int = 1  # 当前渲染质量级别

@dataclass
class VirtualizationConfig:
    """虚拟滚动配置"""
    # 基础配置
    chunk_size: int = 1000  # 每个渲染块的数据点数量
    overlap_size: int = 100  # 块之间的重叠数据点数量
    max_visible_chunks: int = 5  # 最大可见块数量
    
    # 性能配置
    max_render_time_ms: float = 16.67  # 最大渲染时间（60fps）
    memory_threshold_mb: int = 100  # 内存阈值
    cleanup_threshold: float = 0.8  # 清理阈值（80%内存使用）
    
    # 质量配置
    adaptive_quality: bool = True  # 自适应质量
    min_quality: float = 0.3  # 最小质量（0.3-1.0）
    quality_levels: List[int] = None  # 质量级别对应的数据抽样
    
    # 交互配置
    scroll_threshold: int = 50  # 滚动阈值
    preload_distance: int = 200  # 预加载距离
    
    # 缓存配置
    cache_size: int = 100  # 最大缓存块数量
    cache_policy: str = "lru"  # 缓存策略：lru, lfu, fifo
    
    def __post_init__(self):
        if self.quality_levels is None:
            self.quality_levels = [1, 2, 4, 8, 16]  # 抽样级别：1=全部数据，2=抽样一半等

@dataclass
class VirtualRenderStyle:
    """通用虚拟滚动渲染样式配置"""
    # 基础样式
    color: Union[str, Callable] = '#1f77b4'
    alpha: float = 0.7
    edge_color: str = '#000000'
    edge_width: float = 0.5
    width: float = 0.8
    
    # 虚拟滚动样式
    show_chunks: bool = False  # 是否显示渲染块边界（调试用）
    chunk_border_color: str = '#ff0000'
    chunk_border_width: float = 1.0
    
    # 性能优化
    enable_gradient_colors: bool = True  # 启用渐变色
    min_visible_value: float = 0.0  # 最小可见值
    
    # 特定图表类型样式（可选）
    candle_up_color: str = '#ff0000'  # K线阳线颜色
    candle_down_color: str = '#00ff00'  # K线阴线颜色
    candle_limit_up_color: str = '#FF9800'  # K线涨停颜色（橙色）
    candle_limit_down_color: str = '#AB47BC'  # K线跌停颜色（紫色）

    # 成交量四色（R292：涨红/跌绿/涨停橙/跌停紫，与 K 线判定一致）
    # volume_* 专属键优先，未设置时回退到 K 线同款 up/down 键
    up_color: str = '#ff0000'  # 涨（红）
    down_color: str = '#00ff00'  # 跌（绿）
    limit_up_color: str = '#FF9800'  # 涨停（橙）
    limit_down_color: str = '#AB47BC'  # 跌停（紫）
    volume_up_color: Optional[str] = None  # 成交量专属涨色，None 时回退 up_color
    volume_down_color: Optional[str] = None  # 成交量专属跌色，None 时回退 down_color

    line_style: str = '-'  # 折线图线条样式
    point_size: float = 2.0  # 散点图点大小

class IVirtualRenderer(Protocol):
    """通用虚拟滚动渲染器接口"""
    
    # 信号定义（如果是QObject子类）
    data_rendered: pyqtSignal = None
    rendering_progress: pyqtSignal = None
    performance_warning: pyqtSignal = None
    virtual_scroll_enabled: pyqtSignal = None
    
    def enable_virtual_scrolling(self, enabled: bool) -> None:
        """启用/禁用虚拟滚动"""
        ...
    
    def set_data_source(self, data: Union[np.ndarray, pd.DataFrame, pd.Series]) -> None:
        """设置数据源"""
        ...
    
    def render_with_virtual_scroll(self, ax, data: Union[np.ndarray, pd.DataFrame, pd.Series],
                                 style: Optional[Dict[str, Any]] = None,
                                 x: Optional[np.ndarray] = None,
                                 use_datetime_axis: bool = True) -> bool:
        """使用虚拟滚动渲染"""
        ...
    
    def update_viewport(self, visible_rect: QRectF) -> None:
        """更新视口信息"""
        ...
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        ...
    
    def cleanup(self) -> None:
        """清理资源"""
        ...
    
    @property
    def is_enabled(self) -> bool:
        """虚拟滚动是否启用"""
        ...
    
    @property
    def total_data_points(self) -> int:
        """总数据点数量"""
        ...

class VirtualRenderManager:
    """统一渲染管理器，管理不同图表类型的虚拟滚动渲染"""
    
    def __init__(self):
        self._renderers: Dict[str, IVirtualRenderer] = {}  # 图表类型 -> 渲染器实例
        self._configs: Dict[str, VirtualizationConfig] = {}  # 图表类型 -> 配置
        self._performance_stats: Dict[str, Dict[str, Any]] = {}  # 图表类型 -> 性能统计
        self._lock = threading.Lock()
        
        logger.info("虚拟滚动渲染管理器初始化完成")
    
    def register_renderer(self, chart_type: str, renderer: IVirtualRenderer, 
                         config: Optional[VirtualizationConfig] = None) -> None:
        """注册渲染器
        
        Args:
            chart_type: 图表类型，如 'volume', 'candle', 'line', 'bar'
            renderer: 渲染器实例
            config: 虚拟滚动配置，可选
        """
        with self._lock:
            self._renderers[chart_type] = renderer
            self._configs[chart_type] = config or VirtualizationConfig()
            self._performance_stats[chart_type] = {}
            
            logger.info(f"📋 已注册{chart_type}图表的虚拟滚动渲染器")
    
    def get_renderer(self, chart_type: str) -> Optional[IVirtualRenderer]:
        """获取指定图表类型的渲染器
        
        Args:
            chart_type: 图表类型
            
        Returns:
            渲染器实例或None
        """
        with self._lock:
            renderer = self._renderers.get(chart_type)
            if renderer:
                logger.debug(f"🔍 已获取{chart_type}图表的虚拟滚动渲染器")
            return renderer
    
    def enable_virtual_scrolling(self, chart_type: str, enabled: bool) -> bool:
        """启用/禁用指定图表类型的虚拟滚动
        
        Args:
            chart_type: 图表类型
            enabled: 是否启用
            
        Returns:
            是否操作成功
        """
        renderer = self.get_renderer(chart_type)
        if renderer:
            renderer.enable_virtual_scrolling(enabled)
            logger.info(f"⚙️ {chart_type}图表虚拟滚动已{'启用' if enabled else '禁用'}")
            return True
        logger.warning(f"❌ 无法找到{chart_type}图表的虚拟滚动渲染器")
        return False
    
    def set_data_source(self, chart_type: str, data: Union[np.ndarray, pd.DataFrame, pd.Series]) -> bool:
        """为指定图表类型设置数据源
        
        Args:
            chart_type: 图表类型
            data: 数据源
            
        Returns:
            是否操作成功
        """
        renderer = self.get_renderer(chart_type)
        if renderer:
            renderer.set_data_source(data)
            logger.info(f"已为{chart_type}图表设置数据源，包含{len(data)}个数据点")
            return True
        logger.warning(f"❌ 无法找到{chart_type}图表的虚拟滚动渲染器")
        return False
    
    def render(self, chart_type: str, ax, data: Union[np.ndarray, pd.DataFrame, pd.Series],
              style: Optional[Dict[str, Any]] = None,
              x: Optional[np.ndarray] = None,
              use_datetime_axis: bool = True) -> bool:
        """渲染指定类型的图表
        
        Args:
            chart_type: 图表类型
            ax: 坐标轴实例
            data: 渲染数据
            style: 样式配置
            x: X轴数据
            use_datetime_axis: 是否使用日期时间轴
            
        Returns:
            是否渲染成功
        """
        renderer = self.get_renderer(chart_type)
        if renderer:
            start_time = time.time()
            result = renderer.render_with_virtual_scroll(ax, data, style, x, use_datetime_axis)
            render_time = time.time() - start_time
            
            # 更新性能统计
            with self._lock:
                stats = renderer.get_performance_stats()
                stats['last_render_time_ms'] = render_time * 1000
                self._performance_stats[chart_type] = stats
            
            logger.info(f"{chart_type}图表虚拟滚动渲染{'成功' if result else '失败'}，耗时{render_time*1000:.2f}ms")
            return result
        logger.warning(f"❌ 无法找到{chart_type}图表的虚拟滚动渲染器，渲染失败")
        return False
    
    def update_viewport(self, chart_type: str, visible_rect: QRectF) -> bool:
        """更新指定图表类型的视口
        
        Args:
            chart_type: 图表类型
            visible_rect: 可见区域
            
        Returns:
            是否操作成功
        """
        renderer = self.get_renderer(chart_type)
        if renderer:
            renderer.update_viewport(visible_rect)
            logger.debug(f"已更新{chart_type}图表的视口信息")
            return True
        return False
    
    def get_performance_stats(self, chart_type: Optional[str] = None) -> Dict[str, Any]:
        """获取性能统计信息
        
        Args:
            chart_type: 图表类型，None表示获取所有图表类型的统计
            
        Returns:
            性能统计信息
        """
        with self._lock:
            if chart_type:
                return self._performance_stats.get(chart_type, {})
            return self._performance_stats.copy()
    
    def cleanup(self, chart_type: Optional[str] = None) -> None:
        """清理资源
        
        Args:
            chart_type: 图表类型，None表示清理所有图表类型的资源
        """
        with self._lock:
            if chart_type:
                if chart_type in self._renderers:
                    renderer = self._renderers[chart_type]
                    renderer.cleanup()
                    logger.debug(f"已清理{chart_type}图表虚拟滚动渲染器资源")
            else:
                for chart_type, renderer in self._renderers.items():
                    renderer.cleanup()
                    logger.debug(f"已清理{chart_type}图表虚拟滚动渲染器资源")
                self._performance_stats.clear()
    
    def get_supported_chart_types(self) -> List[str]:
        """获取支持的图表类型
        
        Returns:
            支持的图表类型列表
        """
        with self._lock:
            return list(self._renderers.keys())

class DataAggregator:
    """数据聚合器"""
    
    def __init__(self, config: VirtualizationConfig):
        self.config = config
        self._lock = threading.Lock()
        
    def aggregate_chunk(self, data: np.ndarray, start_idx: int, end_idx: int, 
                       quality_level: int = 1) -> np.ndarray:
        """聚合数据块"""
        try:
            if quality_level <= 1:
                return data[start_idx:end_idx]
                
            chunk_data = data[start_idx:end_idx]
            chunk_size = len(chunk_data)
            
            # 基于质量级别进行数据聚合
            step = quality_level
            if step >= chunk_size:
                # 如果抽样步长大于块大小，返回平均聚合
                return np.array([np.mean(chunk_data)])
            
            # 重采样聚合
            aggregated = []
            for i in range(0, chunk_size, step):
                end_i = min(i + step, chunk_size)
                window = chunk_data[i:end_i]
                
                # 对于时间序列，使用适当的聚合方法
                if i == 0 and len(window) > 1:
                    # 第一个窗口包含头部数据，需要特殊处理
                    aggregated.append(window[0])  # 头部值
                elif len(window) > 0:
                    # 普通窗口使用平均值
                    aggregated.append(np.mean(window))
            
            return np.array(aggregated)
            
        except Exception as e:
            logger.error(f"数据聚合失败: {e}")
            return data[start_idx:end_idx] if end_idx > start_idx else np.array([])
    
    def adaptive_aggregate(self, data: np.ndarray, start_idx: int, end_idx: int,
                          frame_time_ms: float) -> Tuple[np.ndarray, int]:
        """自适应数据聚合，基于CPU/GPU负载和帧时间"""
        with self._lock:
            # 集成系统资源监控
            cpu_usage = 0.0
            try:
                import psutil
                # 获取CPU使用率
                cpu_usage = psutil.cpu_percent(interval=0.01)
                # 获取内存使用率
                memory_usage = psutil.virtual_memory().percent
                
                logger.debug(f"系统资源状态 - CPU: {cpu_usage:.1f}%, 内存: {memory_usage:.1f}%, 帧时间: {frame_time_ms:.2f}ms")
                
                # 结合系统资源和帧时间动态调整质量级别
                total_load = frame_time_ms / self.config.max_render_time_ms + cpu_usage / 100
                
                if total_load > 2.0:
                    # 高负载，大幅降低质量
                    quality_level = min(16, int(total_load * 3))
                elif total_load > 1.5:
                    # 中等负载，适度降低质量
                    quality_level = min(8, int(total_load * 2))
                elif total_load > 1.0:
                    # 轻度负载，轻微降低质量
                    quality_level = min(4, int(total_load * 1.5))
                else:
                    # 低负载，最高质量
                    quality_level = 1
                    
            except Exception as e:
                logger.warning(f"获取系统资源失败: {e}")
                # 仅基于帧时间调整
                if frame_time_ms > self.config.max_render_time_ms:
                    quality_level = min(8, int(frame_time_ms / self.config.max_render_time_ms) + 1)
                else:
                    quality_level = 1
            
            # 聚合数据
            aggregated_data = self.aggregate_chunk(data, start_idx, end_idx, quality_level)
            
            logger.debug(f"自适应聚合完成 - 数据范围: {start_idx}-{end_idx}, 质量级别: {quality_level}, 聚合后大小: {len(aggregated_data)}")
            
            return aggregated_data, quality_level

class ViewportTracker:
    """视口追踪器"""
    
    def __init__(self, config: VirtualizationConfig):
        self.config = config
        self.state = ViewportState.IDLE
        self.last_visible_rect = QRectF()
        self.scroll_velocity = 0.0
        self.last_update_time = time.time()
        
        # 滚动预测
        self._scroll_history = deque(maxlen=10)
        self._last_scroll_event = None
        
    def update_viewport(self, visible_rect: QRectF):
        """更新视口信息"""
        now = time.time()
        dt = now - self.last_update_time
        
        self.last_visible_rect = visible_rect
        self.last_update_time = now
        
        # 计算滚动速度
        if dt > 0:
            self.scroll_velocity = abs(visible_rect.y() - self.last_visible_rect.y()) / dt
        
        # 记录滚动历史
        self._scroll_history.append({
            'time': now,
            'velocity': self.scroll_velocity,
            'rect': visible_rect
        })
        
    def predict_next_position(self) -> QRectF:
        """预测下一帧位置"""
        if len(self._scroll_history) < 2:
            return self.last_visible_rect
            
        # 简单的线性预测
        recent_scrolls = list(self._scroll_history)[-3:]  # 最近3次滚动
        if len(recent_scrolls) < 2:
            return self.last_visible_rect
            
        avg_velocity = np.mean([s['velocity'] for s in recent_scrolls])
        predicted_y = self.last_visible_rect.y() + avg_velocity * 0.016  # 预测下一帧（60fps）
        
        return QRectF(
            self.last_visible_rect.x(),
            predicted_y,
            self.last_visible_rect.width(),
            self.last_visible_rect.height()
        )
    
    def is_scrolling_fast(self) -> bool:
        """判断是否在快速滚动"""
        return self.scroll_velocity > self.config.scroll_threshold

class ChunkRenderer:
    """渲染块管理器"""
    
    def __init__(self, config: VirtualizationConfig, data_aggregator: DataAggregator):
        self.config = config
        self.aggregator = data_aggregator
        self.chunks: Dict[int, RenderChunk] = {}
        self._render_queue = deque()
        self._lock = threading.Lock()
        
    def request_chunk(self, chunk_id: int, data: np.ndarray, 
                     viewport_rect: QRectF) -> Optional[RenderChunk]:
        """请求渲染块"""
        with self._lock:
            # 计算块边界
            chunk_size = self.config.chunk_size
            overlap = self.config.overlap_size
            start_idx = max(0, chunk_id * chunk_size - overlap)
            end_idx = min(len(data), (chunk_id + 1) * chunk_size + overlap)
            
            # 检查是否需要渲染
            if not self._should_render_chunk(chunk_id, viewport_rect):
                return None
            
            # 创建渲染块
            chunk = self._create_render_chunk(chunk_id, data, start_idx, end_idx)
            if chunk:
                self.chunks[chunk_id] = chunk
                
            return chunk
    
    def _should_render_chunk(self, chunk_id: int, viewport_rect: QRectF) -> bool:
        """判断是否需要渲染该块"""
        chunk_y = chunk_id * self.config.chunk_size
        
        # 检查块是否在视口附近
        viewport_top = viewport_rect.y()
        viewport_bottom = viewport_rect.y() + viewport_rect.height()
        
        chunk_top = chunk_y - self.config.preload_distance
        chunk_bottom = chunk_y + self.config.chunk_size + self.config.preload_distance
        
        return not (chunk_bottom < viewport_top or chunk_top > viewport_bottom)
    
    def _create_render_chunk(self, chunk_id: int, data: np.ndarray,
                            start_idx: int, end_idx: int) -> Optional[RenderChunk]:
        """创建渲染块"""
        try:
            # 计算质量级别（基于内存压力）
            memory_usage = self._get_memory_usage()
            if memory_usage > self.config.cleanup_threshold:
                quality_level = min(8, int(memory_usage * 10))
            else:
                quality_level = 1
            
            # 聚合数据
            aggregated_data, actual_quality = self.aggregator.aggregate_chunk(
                data, start_idx, end_idx, quality_level)
            
            # 创建渲染块
            chunk = RenderChunk(
                start_index=start_idx,
                end_index=end_idx,
                data_points=aggregated_data,
                bounding_rect=QRectF(
                    0, chunk_id * self.config.chunk_size,
                    100, len(aggregated_data)
                ),
                render_time=0.0,
                is_visible=True
            )
            
            return chunk
            
        except Exception as e:
            logger.error(f"创建渲染块失败 (chunk_id={chunk_id}): {e}")
            return None
    
    def cleanup_chunks(self, visible_chunks: List[int]):
        """清理不可见的块"""
        with self._lock:
            chunks_to_remove = []
            for chunk_id in self.chunks.keys():
                if chunk_id not in visible_chunks:
                    chunks_to_remove.append(chunk_id)
            
            for chunk_id in chunks_to_remove:
                del self.chunks[chunk_id]
    
    def _get_memory_usage(self) -> float:
        """获取内存使用率"""
        try:
            # 集成实际的内存监控
            import psutil
            memory = psutil.virtual_memory()
            usage = memory.percent / 100  # 转换为0-1范围
            logger.debug(f"当前内存使用率: {usage*100:.1f}%")
            return usage
        except Exception as e:
            logger.warning(f"获取内存使用率失败: {e}")
            # 返回默认值
            return 0.5

class VirtualScrollRenderer(QObject):
    """虚拟滚动渲染器主类（集成WebGPU加速），实现IVirtualRenderer接口"""
    
    # 信号定义
    data_rendered = pyqtSignal(int, object)  # chunk_id, RenderChunk
    rendering_progress = pyqtSignal(float)  # 进度百分比
    performance_warning = pyqtSignal(str, float)  # 警告信息, 数值
    gpu_acceleration_toggled = pyqtSignal(bool)  # GPU加速启用/禁用状态
    virtual_scroll_enabled = pyqtSignal(bool)  # 虚拟滚动状态变化
    
    def __init__(self, config: Optional[VirtualizationConfig] = None):
        super().__init__()
        self.config = config or VirtualizationConfig()
        self.data_source = None  # 数据源（DataFrame或ndarray）
        self.viewport_tracker = ViewportTracker(self.config)
        self.data_aggregator = DataAggregator(self.config)
        self.chunk_renderer = ChunkRenderer(self.config, self.data_aggregator)
        
        # 虚拟滚动状态
        self._is_enabled = True
        self._total_data_points = 0
        
        # 智能缓存策略
        self._chunk_cache = OrderedDict()  # 基于LRU的块缓存
        self._cache_hit_count = 0
        self._cache_miss_count = 0
        
        # WebGPU渲染器集成
        try:
            from core.webgpu import GPURendererConfig, WebGPURenderer
            self.webgpu_renderer = WebGPURenderer(GPURendererConfig(
                preferred_backend="moderngl"  # 尝试使用ModernGL后端
            ))
            # 尝试初始化WebGPU渲染器
            self.gpu_acceleration_enabled = self.webgpu_renderer.initialize()
            self.gpu_acceleration_toggled.emit(self.gpu_acceleration_enabled)
            
            if self.gpu_acceleration_enabled:
                logger.info("WebGPU渲染器集成成功，将使用GPU加速渲染")
            else:
                logger.warning("⚠️ WebGPU渲染器初始化失败，将使用CPU渲染")
        except Exception as e:
            logger.warning(f"WebGPU渲染器集成失败: {e}")
            self.gpu_acceleration_enabled = False
        
        # 性能监控
        self.render_times = deque(maxlen=100)
        self.frame_times = deque(maxlen=60)  # 最近60帧的渲染时间
        self.last_frame_time = time.time()
        
        # 渲染状态
        self.is_rendering = False
        self.quality_level = 1
        self.adaptive_quality_enabled = True
        
        # WebGPU统计
        self.gpu_performance_stats = {
            'rendered_chunks_count': 0,
            'total_vertices_count': 0,
            'gpu_utilization': 0.0,  # 0.0-1.0
            'batch_processing': False
        }
        
        # 定时器用于渲染循环
        self.render_timer = QTimer()
        self.render_timer.timeout.connect(self._render_loop)
        self.render_timer.start(16)  # 60fps渲染
        
        logger.info("虚拟滚动渲染器初始化完成，配置: {}".format({
            'chunk_size': self.config.chunk_size,
            'adaptive_quality': self.config.adaptive_quality,
            'gpu_acceleration': self.gpu_acceleration_enabled
        }))
        
    def enable_virtual_scrolling(self, enabled: bool):
        """启用/禁用虚拟滚动"""
        self._is_enabled = enabled
        self.virtual_scroll_enabled.emit(enabled)
        
        if not enabled:
            # 禁用时清理所有缓存
            self.cleanup()
        
        logger.info(f"虚拟滚动{'启用' if enabled else '禁用'}")
    
    def set_data_source(self, data: Union[np.ndarray, pd.DataFrame, pd.Series]):
        """设置数据源"""
        if isinstance(data, pd.DataFrame):
            # 取第一列作为Y轴数据
            y_data = data.iloc[:, 1].values if len(data.columns) > 1 else data.iloc[:, 0].values
        elif isinstance(data, pd.Series):
            y_data = data.values
        else:
            y_data = data
        
        self.data_source = y_data
        self._total_data_points = len(y_data)
        self.chunk_renderer.chunks.clear()  # 清除旧的渲染块
        self._clear_cache()  # 清除缓存
        
        logger.info(f"虚拟滚动数据源已设置，数据点数量: {self._total_data_points}")
    
    def update_viewport(self, visible_rect: QRectF):
        """更新视口"""
        self.viewport_tracker.update_viewport(visible_rect)
        
        # 根据滚动状态调整渲染策略
        if self.viewport_tracker.is_scrolling_fast():
            self._set_quality_level(3)  # 快速滚动时降低质量
            logger.debug(f"快速滚动检测，降低质量级别到{self.quality_level}")
        else:
            self._set_quality_level(1)  # 静止时最高质量
            logger.debug(f"正常滚动检测，设置质量级别到{self.quality_level}")
    
    def render_with_virtual_scroll(self, ax, data: Union[np.ndarray, pd.DataFrame, pd.Series],
                                 style: Optional[Dict[str, Any]] = None,
                                 x: Optional[np.ndarray] = None,
                                 use_datetime_axis: bool = True) -> bool:
        """使用虚拟滚动渲染
        
        注意：这是一个通用接口方法，具体渲染逻辑需要在子类中实现
        或通过回调函数提供
        """
        logger.warning("VirtualScrollRenderer.render_with_virtual_scroll是通用接口，建议在子类中实现具体渲染逻辑")
        return False
    
    @property
    def is_enabled(self) -> bool:
        """虚拟滚动是否启用"""
        return self._is_enabled
    
    @property
    def total_data_points(self) -> int:
        """总数据点数量"""
        return self._total_data_points
    
    def _get_chunk_from_cache(self, chunk_id: int) -> Optional[RenderChunk]:
        """从缓存获取渲染块"""
        if chunk_id in self._chunk_cache:
            # LRU策略：将访问的块移到末尾
            chunk = self._chunk_cache.pop(chunk_id)
            self._chunk_cache[chunk_id] = chunk
            self._cache_hit_count += 1
            logger.debug(f"缓存命中: 块ID {chunk_id}")
            return chunk
        self._cache_miss_count += 1
        return None
    
    def _add_chunk_to_cache(self, chunk_id: int, chunk: RenderChunk) -> None:
        """添加渲染块到缓存"""
        # 检查缓存大小
        if len(self._chunk_cache) >= self.config.cache_size:
            # 移除最久未使用的块
            oldest_chunk_id, _ = self._chunk_cache.popitem(last=False)
            logger.debug(f"缓存已满，移除最久未使用的块: {oldest_chunk_id}")
        
        self._chunk_cache[chunk_id] = chunk
        logger.debug(f"缓存添加: 块ID {chunk_id}，缓存大小: {len(self._chunk_cache)}")
    
    def _clear_cache(self) -> None:
        """清除缓存"""
        cache_size = len(self._chunk_cache)
        if cache_size > 0:
            self._chunk_cache.clear()
            logger.debug(f"缓存已清除，共移除 {cache_size} 个块")
    
    def _get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_accesses = self._cache_hit_count + self._cache_miss_count
        hit_rate = self._cache_hit_count / total_accesses if total_accesses > 0 else 0.0
        
        return {
            'cache_size': len(self._chunk_cache),
            'cache_hit_count': self._cache_hit_count,
            'cache_miss_count': self._cache_miss_count,
            'cache_hit_rate': hit_rate,
            'max_cache_size': self.config.cache_size
        }
    
    def _render_loop(self):
        """渲染循环"""
        if self.data_source is None:
            return
        
        frame_start_time = time.time()
        
        # 计算当前视口应该渲染的块
        visible_rect = self.viewport_tracker.last_visible_rect
        predicted_rect = self.viewport_tracker.predict_next_position()
        
        # 获取需要渲染的块列表
        chunk_start = max(0, int(predicted_rect.y() / self.config.chunk_size) - 1)
        chunk_end = int((predicted_rect.y() + predicted_rect.height()) / self.config.chunk_size) + 1
        
        visible_chunks = []
        for chunk_id in range(chunk_start, chunk_end + 1):
            chunk = self.chunk_renderer.request_chunk(chunk_id, self.data_source, predicted_rect)
            if chunk:
                visible_chunks.append(chunk_id)
                self.data_rendered.emit(chunk_id, chunk)
        
        # 清理不可见的块
        self.chunk_renderer.cleanup_chunks(visible_chunks)
        
        # 更新性能统计
        frame_time = (time.time() - frame_start_time) * 1000
        self.frame_times.append(frame_time)
        self.render_times.append(frame_time)
        
        # 自适应质量调整
        if self.adaptive_quality_enabled:
            self._adaptive_quality_adjustment()
        
        # 性能监控
        avg_frame_time = np.mean(self.frame_times)
        if avg_frame_time > self.config.max_render_time_ms:
            self.performance_warning.emit(
                f"平均帧时间过长: {avg_frame_time:.1f}ms", avg_frame_time)
    
    def _adaptive_quality_adjustment(self):
        """自适应质量调整"""
        if len(self.frame_times) < 10:  # 至少10帧数据
            return
        
        avg_frame_time = np.mean(self.frame_times)
        
        if avg_frame_time > self.config.max_render_time_ms * 1.5:
            # 性能严重不达标，大幅降低质量
            self.quality_level = min(16, self.quality_level * 2)
        elif avg_frame_time < self.config.max_render_time_ms * 0.5:
            # 性能很好，可以提升质量
            self.quality_level = max(1, self.quality_level // 2)
    
    def _set_quality_level(self, level: int):
        """设置质量级别"""
        if level != self.quality_level:
            self.quality_level = level
            self.chunk_renderer.cleanup_chunks([])  # 强制重新渲染
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计，包括缓存统计信息"""
        stats = {
            'avg_render_time_ms': np.mean(self.render_times) if self.render_times else 0.0,
            'max_render_time_ms': max(self.render_times) if self.render_times else 0.0,
            'min_render_time_ms': min(self.render_times) if self.render_times else 0.0,
            'current_quality_level': self.quality_level,
            'rendered_chunks_count': len(self.chunk_renderer.chunks),
            'adaptive_quality_enabled': self.adaptive_quality_enabled,
            'total_data_points': self._total_data_points,
            'virtual_scrolling_enabled': self._is_enabled,
            'gpu_acceleration_enabled': self.gpu_acceleration_enabled,
            'frame_rate': 1.0 / (np.mean(self.frame_times) / 1000.0) if self.frame_times else 0.0
        }
        
        # 添加缓存统计
        stats.update(self._get_cache_stats())
        
        # 添加WebGPU统计
        if self.gpu_acceleration_enabled:
            stats.update({
                'gpu_rendered_chunks_count': self.gpu_performance_stats['rendered_chunks_count'],
                'gpu_total_vertices_count': self.gpu_performance_stats['total_vertices_count'],
                'gpu_utilization': self.gpu_performance_stats['gpu_utilization']
            })
        
        return stats
    
    def enable_adaptive_quality(self, enabled: bool):
        """启用/禁用自适应质量"""
        self.adaptive_quality_enabled = enabled
        logger.debug(f"自适应质量调整已{'启用' if enabled else '禁用'}")
    
    def cleanup(self):
        """清理资源"""
        logger.info("正在清理虚拟滚动渲染器资源")
        
        self.render_timer.stop()
        self.chunk_renderer.chunks.clear()
        self.render_times.clear()
        self.frame_times.clear()
        self._clear_cache()  # 清除缓存
        
        # 清理WebGPU资源
        if hasattr(self, 'webgpu_renderer') and self.webgpu_renderer:
            try:
                self.webgpu_renderer.cleanup()
                logger.debug("WebGPU资源已清理")
            except Exception as e:
                logger.warning(f"清理WebGPU资源失败: {e}")
        
        logger.info("虚拟滚动渲染器资源清理完成")

# 便捷函数
def create_virtual_scroll_renderer(data: Union[np.ndarray, pd.DataFrame],
                                 config: Optional[VirtualizationConfig] = None) -> VirtualScrollRenderer:
    """创建虚拟滚动渲染器"""
    renderer = VirtualScrollRenderer(config)
    renderer.set_data_source(data)
    return renderer

def optimize_for_large_dataset(data_size: int) -> VirtualizationConfig:
    """根据数据集大小优化配置"""
    if data_size > 1_000_000:  # 100万数据点
        return VirtualizationConfig(
            chunk_size=500,
            overlap_size=50,
            max_visible_chunks=3,
            quality_levels=[1, 4, 8, 16, 32]
        )
    elif data_size > 100_000:  # 10万数据点
        return VirtualizationConfig(
            chunk_size=1000,
            overlap_size=100,
            max_visible_chunks=4,
            quality_levels=[1, 2, 4, 8, 16]
        )
    else:
        return VirtualizationConfig()  # 默认配置
