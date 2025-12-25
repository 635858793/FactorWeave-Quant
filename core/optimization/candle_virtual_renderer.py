#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
K线图虚拟滚动渲染器

专门优化的K线图虚拟滚动渲染器，基于VirtualScrollRenderer实现高效的K线数据可视化
实现IVirtualRenderer通用接口，支持统一管理和扩展

作者: FactorWeave-Quant团队
版本: 1.0
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from PyQt5.QtCore import QObject, pyqtSignal, QRectF, QPointF, QTimer
from loguru import logger
import time
from collections import deque
import threading
# 导入虚拟滚动模块
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.advanced_optimization.performance.virtualization import (
    VirtualScrollRenderer, 
    VirtualizationConfig, 
    RenderChunk,
    ViewportState,
    IVirtualRenderer,
    VirtualRenderStyle
)

class CandleVirtualRenderer(QObject):
    """K线图虚拟滚动渲染器，实现IVirtualRenderer接口"""
    
    # 信号定义
    data_rendered = pyqtSignal(int, object)  # chunk_id, RenderChunk
    rendering_progress = pyqtSignal(float)  # 进度百分比
    performance_warning = pyqtSignal(str, float)  # 警告信息, 数值
    virtual_scroll_enabled = pyqtSignal(bool)  # 虚拟滚动状态变化
    
    def __init__(self, 
                 config: Optional[VirtualizationConfig] = None,
                 style: Optional[VirtualRenderStyle] = None):
        super().__init__()
        
        # 配置和样式
        self.config = config or self._create_optimized_config()
        self.style = style or VirtualRenderStyle()
        
        # 虚拟滚动渲染器
        self.virtual_renderer = VirtualScrollRenderer(self.config)
        self.virtual_renderer.data_rendered.connect(self.data_rendered.emit)
        self.virtual_renderer.performance_warning.connect(self.performance_warning.emit)
        
        # K线数据缓存
        self.candle_data = None
        self.candle_axis = None
        
        # 渲染状态
        self._is_enabled = True
        self._total_data_points = 0
        self.rendered_chunks = {}
        
        # 性能统计
        self.render_stats = {
            'total_render_time_ms': 0.0,
            'chunks_rendered': 0,
            'data_points_processed': 0,
            'memory_usage_estimate_mb': 0.0
        }
        
        logger.info("K线图虚拟滚动渲染器初始化完成，配置: {}".format({
            'chunk_size': self.config.chunk_size,
            'adaptive_quality': self.config.adaptive_quality,
            'cache_size': self.config.cache_size
        }))
    
    def _create_optimized_config(self) -> VirtualizationConfig:
        """创建优化的虚拟滚动配置"""
        return VirtualizationConfig(
            # 针对K线数据优化的配置
            chunk_size=1000,  # K线图块大小适中
            overlap_size=100,  # 适中的重叠区域
            max_visible_chunks=4,  # 显示4个块
            
            # 性能配置
            max_render_time_ms=8.33,  # 120fps目标
            memory_threshold_mb=50,   # 50MB内存限制
            cleanup_threshold=0.7,    # 70%内存使用率时清理
            
            # 质量配置
            adaptive_quality=True,
            min_quality=0.5,
            quality_levels=[1, 2, 4, 8],  # 4个质量级别
            
            # 交互配置
            scroll_threshold=30,
            preload_distance=500,
            
            # 缓存配置
            cache_size=50,  # 缓存50个块
            cache_policy="lru"  # LRU缓存策略
        )
    
    def enable_virtual_scrolling(self, enabled: bool):
        """启用/禁用虚拟滚动"""
        self._is_enabled = enabled
        self.virtual_scroll_enabled.emit(enabled)
        self.virtual_renderer.enable_virtual_scrolling(enabled)
        
        if not enabled:
            # 禁用时清理所有缓存
            self.cleanup()
        
        logger.info(f"K线图虚拟滚动{'启用' if enabled else '禁用'}")
    
    def set_data_source(self, data: Union[np.ndarray, pd.DataFrame, pd.Series]):
        """设置数据源，实现IVirtualRenderer接口"""
        self.candle_data = data
        
        if isinstance(data, pd.DataFrame) and len(data) > 0:
            self._total_data_points = len(data)
            
            # 验证K线数据是否包含必要的列
            required_columns = ['open', 'high', 'low', 'close']
            missing_columns = [col for col in required_columns if col not in data.columns]
            if missing_columns:
                logger.warning(f"K线数据缺少必要列: {missing_columns}")
                self._total_data_points = 0
                return
            
            # 将K线数据转换为适合虚拟滚动的格式
            # 这里简化处理，实际项目中可以根据需要进行数据转换
            self.virtual_renderer.set_data_source(data)
            
            logger.info(f"K线图虚拟滚动数据源已设置: {self._total_data_points}个数据点")
        else:
            self._total_data_points = 0
            logger.warning(f"无效的K线图数据源，数据点数量: {self._total_data_points}")
    
    def set_candle_data(self, candle_data: pd.DataFrame, candle_axis):
        """兼容接口，设置K线数据和轴"""
        self.candle_data = candle_data
        self.candle_axis = candle_axis
        self.set_data_source(candle_data)
    
    def render_with_virtual_scroll(self, ax, data: pd.DataFrame, 
                                        style: Dict[str, Any] = None,
                                        x: np.ndarray = None, 
                                        use_datetime_axis: bool = True) -> bool:
        """使用虚拟滚动渲染K线图，实现IVirtualRenderer接口"""
        if not self._is_enabled or self.candle_data is None:
            # 降级到常规渲染
            logger.info(f"K线图虚拟滚动未启用或数据源为空，降级到常规渲染")
            return self._render_candle_regular(ax, data, style, x, use_datetime_axis)
        
        try:
            start_time = time.time()
            
            logger.info(f"开始使用虚拟滚动渲染K线图: {len(data)}个数据点")
            
            # 更新视口信息
            visible_rect = self._get_visible_rect(ax)
            self.virtual_renderer.update_viewport(visible_rect)
            
            # 检查数据量是否需要虚拟滚动
            if self._total_data_points < self.config.chunk_size * 2:
                # 数据量不大，使用常规渲染
                logger.info(f"K线图数据量较小({self._total_data_points} < {self.config.chunk_size * 2})，使用常规渲染")
                return self._render_candle_regular(ax, data, style, x, use_datetime_axis)
            
            # 使用虚拟滚动渲染
            success = self._render_candle_virtual(ax, data, style, x, use_datetime_axis)
            
            render_time = time.time() - start_time
            self.render_stats['total_render_time_ms'] += render_time * 1000
            self.render_stats['data_points_processed'] += len(data)
            
            logger.info(f"✅ K线图虚拟滚动渲染完成: {render_time*1000:.2f}ms, 渲染块数量: {len(self.rendered_chunks)}")
            return success
            
        except Exception as e:
            logger.error(f"虚拟滚动K线图渲染失败: {e}")
            # 降级到常规渲染
            return self._render_candle_regular(ax, data, style, x, use_datetime_axis)
    
    def _render_candle_regular(self, ax, data: pd.DataFrame, 
                              style: Dict[str, Any] = None,
                              x: np.ndarray = None, 
                              use_datetime_axis: bool = True) -> bool:
        """常规渲染（降级方案）"""
        try:
            start_time = time.time()
            
            if ax and len(data) > 0:
                from matplotlib.collections import PolyCollection, LineCollection
                
                # 获取数据
                x_values = x if x is not None else np.arange(len(data))
                
                # 验证必要的列是否存在
                required_columns = ['open', 'high', 'low', 'close']
                missing_columns = [col for col in required_columns if col not in data.columns]
                if missing_columns:
                    logger.warning(f"K线数据缺少必要列: {missing_columns}")
                    return False
                
                opens = data['open'].values
                highs = data['high'].values
                lows = data['low'].values
                closes = data['close'].values
                
                # 样式处理
                current_style = self.style
                if style:
                    # 使用字典更新样式
                    for key, value in style.items():
                        if hasattr(current_style, key):
                            setattr(current_style, key, value)
                
                # 准备K线数据
                verts_up = []  # 阳线（上涨）
                verts_down = []  # 阴线（下跌）
                segments_up = []  # 上涨影线
                segments_down = []  # 下跌影线
                
                for i, (x_val, open_price, high, low, close) in enumerate(zip(x_values, opens, highs, lows, closes)):
                    left = x_val - 0.3
                    right = x_val + 0.3
                    
                    if close >= open_price:
                        # 阳线
                        verts_up.append([
                            (left, open_price), (left, close), (right, close), (right, open_price)
                        ])
                        segments_up.append([(x_val, low), (x_val, high)])
                    else:
                        # 阴线
                        verts_down.append([
                            (left, open_price), (left, close), (right, close), (right, open_price)
                        ])
                        segments_down.append([(x_val, low), (x_val, high)])
                
                # 绘制K线
                if verts_up:
                    collection_up = PolyCollection(
                        verts_up, 
                        facecolor='none',  # 阳线空心
                        edgecolor=current_style.candle_up_color,
                        linewidth=1,
                        alpha=current_style.alpha
                    )
                    ax.add_collection(collection_up)
                
                if verts_down:
                    collection_down = PolyCollection(
                        verts_down, 
                        facecolor=current_style.candle_down_color,  # 阴线实心
                        edgecolor=current_style.candle_down_color,
                        linewidth=0.5,
                        alpha=current_style.alpha
                    )
                    ax.add_collection(collection_down)
                
                # 绘制影线
                if segments_up:
                    line_collection_up = LineCollection(
                        segments_up, 
                        colors=current_style.candle_up_color,
                        linewidth=0.5,
                        alpha=current_style.alpha
                    )
                    ax.add_collection(line_collection_up)
                
                if segments_down:
                    line_collection_down = LineCollection(
                        segments_down, 
                        colors=current_style.candle_down_color,
                        linewidth=0.5,
                        alpha=current_style.alpha
                    )
                    ax.add_collection(line_collection_down)
                
                if current_style.show_chunks:
                    self._render_chunk_boundaries(ax)
                
                ax.autoscale_view()
                
                render_time = time.time() - start_time
                logger.debug(f"✅ 常规K线图渲染完成: {len(data)}个K线，耗时 {render_time*1000:.2f}ms")
            
            return True
            
        except Exception as e:
            logger.error(f"常规K线图渲染失败: {e}")
            return False
    
    def _render_candle_virtual(self, ax, data: pd.DataFrame, 
                              style: Dict[str, Any] = None,
                              x: np.ndarray = None, 
                              use_datetime_axis: bool = True) -> bool:
        """虚拟滚动渲染K线图"""
        try:
            # 更新样式
            current_style = self.style
            if style:
                # 使用字典更新样式
                for key, value in style.items():
                    if hasattr(current_style, key):
                        setattr(current_style, key, value)
            
            # 获取当前可见的渲染块
            visible_rect = self._get_visible_rect(ax)
            chunk_start = max(0, int(visible_rect.y() / self.config.chunk_size) - 1)
            chunk_end = int((visible_rect.y() + visible_rect.height()) / self.config.chunk_size) + 1
            
            rendered_any = False
            
            # 渲染可见的块
            for chunk_id in range(chunk_start, chunk_end + 1):
                # 尝试从缓存获取块数据
                cached_chunk = self.virtual_renderer._get_chunk_from_cache(chunk_id)
                if cached_chunk:
                    # 使用缓存的块数据
                    chunk_data = cached_chunk.data_points
                    logger.debug(f"使用缓存的块数据，块ID: {chunk_id}")
                else:
                    # 从数据源获取块数据
                    chunk_data = self._get_chunk_data(chunk_id)
                    
                if chunk_data is not None:
                    success = self._render_chunk(ax, chunk_data, current_style, chunk_id, x, use_datetime_axis)
                    if success:
                        rendered_any = True
                        self.rendered_chunks[chunk_id] = chunk_data
                        
                        # 记录统计信息
                        self.render_stats['chunks_rendered'] += 1
            
            # 清理不可见的块
            chunks_to_remove = []
            for chunk_id in self.rendered_chunks.keys():
                if chunk_id < chunk_start - 1 or chunk_id > chunk_end + 1:
                    chunks_to_remove.append(chunk_id)
            
            for chunk_id in chunks_to_remove:
                del self.rendered_chunks[chunk_id]
                logger.debug(f"清理不可见的块: {chunk_id}")
            
            return rendered_any
            
        except Exception as e:
            logger.error(f"虚拟滚动K线图渲染失败: {e}")
            return False
    
    def _get_chunk_data(self, chunk_id: int) -> Optional[pd.DataFrame]:
        """获取指定块的K线数据"""
        if self.candle_data is None:
            return None
        
        chunk_size = self.config.chunk_size
        start_idx = max(0, chunk_id * chunk_size)
        end_idx = min(len(self.candle_data), start_idx + chunk_size)
        
        if start_idx >= end_idx:
            return None
        
        chunk_data = self.candle_data.iloc[start_idx:end_idx]
        
        # 创建RenderChunk并添加到缓存
        # 注意：这里简化处理，实际项目中可以根据需要创建更完整的RenderChunk
        chunk = RenderChunk(
            start_index=start_idx,
            end_index=end_idx,
            data_points=chunk_data,
            bounding_rect=QRectF(start_idx, 0, len(chunk_data), 100),  # 简化的边界矩形
            render_time=0.0,
            quality_level=self.virtual_renderer.quality_level
        )
        
        self.virtual_renderer._add_chunk_to_cache(chunk_id, chunk)
        
        return chunk_data
    
    def _render_chunk(self, ax, chunk_data: pd.DataFrame, 
                     style: VirtualRenderStyle, chunk_id: int, 
                     x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """渲染单个K线图块"""
        try:
            from matplotlib.collections import PolyCollection, LineCollection
            
            if len(chunk_data) == 0:
                return False
            
            # 创建该块的K线
            chunk_size = self.config.chunk_size
            base_index = chunk_id * chunk_size
            
            # 准备X轴数据
            if x is not None and len(x) > base_index + len(chunk_data):
                # 使用提供的X轴数据
                chunk_x = x[base_index:base_index + len(chunk_data)]
            else:
                # 使用默认的X轴数据
                chunk_x = np.arange(base_index, base_index + len(chunk_data))
            
            # 验证必要的列是否存在
            required_columns = ['open', 'high', 'low', 'close']
            missing_columns = [col for col in required_columns if col not in chunk_data.columns]
            if missing_columns:
                logger.warning(f"K线数据块缺少必要列: {missing_columns}")
                return False
            
            opens = chunk_data['open'].values
            highs = chunk_data['high'].values
            lows = chunk_data['low'].values
            closes = chunk_data['close'].values
            
            # 准备K线数据
            verts_up = []  # 阳线（上涨）
            verts_down = []  # 阴线（下跌）
            segments_up = []  # 上涨影线
            segments_down = []  # 下跌影线
            
            for i, (x_val, open_price, high, low, close) in enumerate(zip(chunk_x, opens, highs, lows, closes)):
                left = x_val - 0.3
                right = x_val + 0.3
                
                if close >= open_price:
                    # 阳线
                    verts_up.append([
                        (left, open_price), (left, close), (right, close), (right, open_price)
                    ])
                    segments_up.append([(x_val, low), (x_val, high)])
                else:
                    # 阴线
                    verts_down.append([
                        (left, open_price), (left, close), (right, close), (right, open_price)
                    ])
                    segments_down.append([(x_val, low), (x_val, high)])
            
            # 绘制K线
            if verts_up:
                collection_up = PolyCollection(
                    verts_up, 
                    facecolor='none',  # 阳线空心
                    edgecolor=style.candle_up_color,
                    linewidth=0.8,
                    alpha=style.alpha
                )
                ax.add_collection(collection_up)
            
            if verts_down:
                collection_down = PolyCollection(
                    verts_down, 
                    facecolor='none',  # 阴线空心
                    edgecolor=style.candle_down_color,
                    linewidth=0.8,
                    alpha=style.alpha
                )
                ax.add_collection(collection_down)
            
            # 绘制影线
            if segments_up:
                line_collection_up = LineCollection(
                    segments_up, 
                    colors=style.candle_up_color,
                    linewidth=0.8,
                    alpha=style.alpha
                )
                ax.add_collection(line_collection_up)
            
            if segments_down:
                line_collection_down = LineCollection(
                    segments_down, 
                    colors=style.candle_down_color,
                    linewidth=0.8,
                    alpha=style.alpha
                )
                ax.add_collection(line_collection_down)
            
            # 调试模式下显示块边界
            if style.show_chunks:
                self._draw_chunk_boundary(ax, base_index, len(chunk_data), 
                                        style.chunk_border_color, 
                                        style.chunk_border_width)
            
            return True
            
        except Exception as e:
            logger.error(f"渲染K线图块 {chunk_id} 失败: {e}")
            return False
    
    def _get_visible_rect(self, ax) -> QRectF:
        """获取当前可见区域"""
        if ax is None:
            return QRectF(0, 0, 100, 100)
        
        try:
            # 获取当前轴的显示范围
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            
            return QRectF(xlim[0], ylim[0], xlim[1] - xlim[0], ylim[1] - ylim[0])
            
        except Exception as e:
            logger.warning(f"获取可见区域失败: {e}")
            return QRectF(0, 0, 100, 100)
    
    def _draw_chunk_boundary(self, ax, start_index: int, length: int, 
                           color: str, width: float):
        """绘制块边界（调试用）"""
        try:
            import matplotlib.patches as patches
            
            rect = patches.Rectangle(
                (start_index - 0.5, ax.get_ylim()[0]),
                length + 1,
                ax.get_ylim()[1] - ax.get_ylim()[0],
                linewidth=width,
                edgecolor=color,
                facecolor='none',
                alpha=0.3
            )
            ax.add_patch(rect)
            
        except Exception as e:
            logger.warning(f"绘制块边界失败: {e}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息，实现IVirtualRenderer接口"""
        stats = self.render_stats.copy()
        
        # 添加虚拟滚动统计
        if hasattr(self.virtual_renderer, 'get_performance_stats'):
            virtual_stats = self.virtual_renderer.get_performance_stats()
            stats.update(virtual_stats)
        
        # 添加总体统计
        stats.update({
            'total_data_points': self._total_data_points,
            'virtual_scrolling_enabled': self._is_enabled,
            'rendered_chunks_count': len(self.rendered_chunks),
            'memory_estimate_mb': len(self.rendered_chunks) * 0.1  # 估算
        })
        
        return stats
    
    def cleanup(self):
        """清理资源，实现IVirtualRenderer接口"""
        logger.info("清理K线图虚拟滚动渲染器资源")
        
        if self._is_enabled and hasattr(self.virtual_renderer, 'cleanup'):
            self.virtual_renderer.cleanup()
        
        self.rendered_chunks.clear()
        self.candle_data = None
        self.candle_axis = None
        
        logger.info("K线图虚拟滚动渲染器资源清理完成")
    
    def update_viewport(self, visible_rect: QRectF):
        """更新视口，实现IVirtualRenderer接口"""
        self.virtual_renderer.update_viewport(visible_rect)
    
    @property
    def is_enabled(self) -> bool:
        """虚拟滚动是否启用，实现IVirtualRenderer接口"""
        return self._is_enabled
    
    @property
    def total_data_points(self) -> int:
        """总数据点数量，实现IVirtualRenderer接口"""
        return self._total_data_points
    
    def _render_chunk_boundaries(self, ax):
        """渲染所有块边界（调试用）"""
        # 简化实现，实际项目中可以根据需要实现
        pass

# 便捷函数
def create_candle_virtual_renderer(data: pd.DataFrame, 
                                 ax,
                                 config: Optional[VirtualizationConfig] = None,
                                 style: Optional[VirtualRenderStyle] = None) -> CandleVirtualRenderer:
    """创建K线图虚拟滚动渲染器"""
    renderer = CandleVirtualRenderer(config, style)
    renderer.set_candle_data(data, ax)
    return renderer

def optimize_candle_config_for_data_size(data_size: int) -> VirtualizationConfig:
    """根据数据大小优化K线图虚拟滚动配置"""
    if data_size > 1_000_000:  # 100万数据点
        return VirtualizationConfig(
            chunk_size=1500,
            overlap_size=150,
            max_visible_chunks=3,
            quality_levels=[1, 4, 8, 16, 32],
            cache_size=100
        )
    elif data_size > 100_000:  # 10万数据点
        return VirtualizationConfig(
            chunk_size=1000,
            overlap_size=100,
            max_visible_chunks=4,
            quality_levels=[1, 2, 4, 8, 16],
            cache_size=50
        )
    else:  # 小于10万数据点
        return VirtualizationConfig(
            chunk_size=2000,
            overlap_size=200,
            max_visible_chunks=3,
            quality_levels=[1, 2, 4, 8],
            cache_size=20
        )
