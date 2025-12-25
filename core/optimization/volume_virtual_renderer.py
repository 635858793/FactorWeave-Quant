#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
成交量虚拟滚动渲染器

专门优化的成交量图表虚拟滚动渲染器，基于VirtualScrollRenderer实现高效的成交量数据可视化

作者: FactorWeave-Quant团队
版本: 1.0
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from dataclasses import dataclass
from PyQt5.QtCore import QObject, pyqtSignal, QRectF, QPointF, QTimer
from PyQt5.QtWidgets import QWidget
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
    ViewportState
)

@dataclass
class VolumeRenderStyle:
    """成交量渲染样式配置"""
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
    min_visible_volume: float = 0.0  # 最小可见成交量

class VolumeVirtualRenderer(QObject):
    """成交量虚拟滚动渲染器"""
    
    # 信号定义
    volume_rendered = pyqtSignal(object, object)  # ax, RenderChunk
    rendering_progress = pyqtSignal(float)  # 进度百分比
    performance_warning = pyqtSignal(str, float)  # 警告信息, 数值
    virtual_scroll_enabled = pyqtSignal(bool)  # 虚拟滚动状态变化
    
    def __init__(self, 
                 config: Optional[VirtualizationConfig] = None,
                 style: Optional[VolumeRenderStyle] = None):
        super().__init__()
        
        # 配置和样式
        self.config = config or self._create_optimized_config()
        self.style = style or VolumeRenderStyle()
        
        # 虚拟滚动渲染器
        self.virtual_renderer = VirtualScrollRenderer(self.config)
        self.virtual_renderer.data_rendered.connect(self._on_chunk_rendered)
        self.virtual_renderer.performance_warning.connect(self.performance_warning.emit)
        
        # 成交量数据缓存
        self.volume_data = None
        self.volume_axis = None
        
        # 渲染状态
        self.is_enabled = True
        self.total_data_points = 0
        self.rendered_chunks = {}
        
        # 性能统计
        self.render_stats = {
            'total_render_time_ms': 0.0,
            'chunks_rendered': 0,
            'data_points_processed': 0,
            'memory_usage_estimate_mb': 0.0
        }
        
        logger.info("成交量虚拟滚动渲染器初始化完成")
    
    def _create_optimized_config(self) -> VirtualizationConfig:
        """创建优化的虚拟滚动配置"""
        return VirtualizationConfig(
            # 针对成交量数据优化的配置
            chunk_size=2000,  # 更大的块大小适合成交量数据
            overlap_size=200,  # 适中的重叠区域
            max_visible_chunks=3,  # 只显示3个块
            
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
            preload_distance=500
        )
    
    def enable_virtual_scrolling(self, enabled: bool):
        """启用/禁用虚拟滚动"""
        self.is_enabled = enabled
        self.virtual_scroll_enabled.emit(enabled)
        
        if not enabled:
            # 禁用时清理所有缓存
            self.virtual_renderer.cleanup()
            self.rendered_chunks.clear()
        
        logger.info(f"成交量虚拟滚动{'启用' if enabled else '禁用'}")
    
    def set_volume_data(self, volume_data: pd.DataFrame, volume_axis):
        """设置成交量数据和轴"""
        self.volume_data = volume_data
        self.volume_axis = volume_axis
        
        if volume_data is not None and len(volume_data) > 0:
            self.total_data_points = len(volume_data)
            
            # 为虚拟滚动设置数据源
            if self.is_enabled:
                volumes = volume_data['volume'].values
                self.virtual_renderer.set_data_source(volumes)
                
                logger.info(f"成交量虚拟滚动数据已设置: {self.total_data_points}个数据点")
            else:
                logger.info(f"成交量数据已设置: {self.total_data_points}个数据点 (虚拟滚动已禁用)")
    
    def render_volume_with_virtual_scroll(self, ax, data: pd.DataFrame, 
                                        style: Dict[str, Any] = None,
                                        x: np.ndarray = None, 
                                        use_datetime_axis: bool = True) -> bool:
        """使用虚拟滚动渲染成交量"""
        if not self.is_enabled or self.volume_data is None:
            # 降级到常规渲染
            return self._render_volume_regular(ax, data, style, x, use_datetime_axis)
        
        try:
            start_time = time.time()
            
            logger.debug(f"使用虚拟滚动渲染成交量: {len(data)}个数据点")
            
            # 更新视口信息
            visible_rect = self._get_visible_rect(ax)
            self.virtual_renderer.update_viewport(visible_rect)
            
            # 检查数据量是否需要虚拟滚动
            if self.total_data_points < self.config.chunk_size * 2:
                # 数据量不大，使用常规渲染
                return self._render_volume_regular(ax, data, style, x, use_datetime_axis)
            
            # 使用虚拟滚动渲染
            success = self._render_volume_virtual(ax, data, style, x, use_datetime_axis)
            
            render_time = time.time() - start_time
            self.render_stats['total_render_time_ms'] += render_time * 1000
            self.render_stats['data_points_processed'] += len(data)
            
            logger.debug(f"✅ 虚拟滚动成交量渲染完成: {render_time*1000:.2f}ms")
            return success
            
        except Exception as e:
            logger.error(f"虚拟滚动成交量渲染失败: {e}")
            # 降级到常规渲染
            return self._render_volume_regular(ax, data, style, x, use_datetime_axis)
    
    def _render_volume_regular(self, ax, data: pd.DataFrame, 
                              style: Dict[str, Any] = None,
                              x: np.ndarray = None, 
                              use_datetime_axis: bool = True) -> bool:
        """常规渲染（降级方案）"""
        try:
            start_time = time.time()
            
            if ax and len(data) > 0:
                from matplotlib.collections import PolyCollection
                
                # 获取数据
                x_values = x if x is not None else np.arange(len(data))
                volumes = data['volume'].values
                
                # 样式处理
                current_style = self.style
                if style:
                    current_style = VolumeRenderStyle(**{**current_style.__dict__, **style})
                
                # 创建柱子顶点
                verts = []
                colors = []
                
                for x_val, volume in zip(x_values, volumes):
                    if volume > current_style.min_visible_volume:
                        left = x_val - current_style.width / 2
                        right = x_val + current_style.width / 2
                        
                        verts.append([
                            (left, 0), (left, volume), (right, volume), (right, 0)
                        ])
                        
                        # 处理颜色
                        if callable(current_style.color):
                            normalized_volume = volume / max(volumes) if max(volumes) > 0 else 0
                            colors.append(current_style.color(normalized_volume))
                        else:
                            colors.append(current_style.color)
                
                if verts:
                    # 创建PolyCollection
                    collection = PolyCollection(
                        verts, 
                        facecolors=colors if colors else current_style.color,
                        edgecolors=current_style.edge_color,
                        linewidths=current_style.edge_width,
                        alpha=current_style.alpha
                    )
                    
                    ax.add_collection(collection)
                    
                    if current_style.show_chunks:
                        self._render_chunk_boundaries(ax)
                    
                    ax.autoscale_view()
                    
                    render_time = time.time() - start_time
                    logger.debug(f"✅ 常规成交量渲染完成: {len(verts)}个柱子，耗时 {render_time*1000:.2f}ms")
            
            return True
            
        except Exception as e:
            logger.error(f"常规成交量渲染失败: {e}")
            return False
    
    def _render_volume_virtual(self, ax, data: pd.DataFrame, 
                              style: Dict[str, Any] = None,
                              x: np.ndarray = None, 
                              use_datetime_axis: bool = True) -> bool:
        """虚拟滚动渲染"""
        try:
            # 更新样式
            current_style = self.style
            if style:
                current_style = VolumeRenderStyle(**{**current_style.__dict__, **style})
            
            # 获取当前可见的渲染块
            visible_rect = self._get_visible_rect(ax)
            chunk_start = max(0, int(visible_rect.y() / self.config.chunk_size) - 1)
            chunk_end = int((visible_rect.y() + visible_rect.height()) / self.config.chunk_size) + 1
            
            rendered_any = False
            
            # 渲染可见的块
            for chunk_id in range(chunk_start, chunk_end + 1):
                # 这里需要从虚拟渲染器获取块数据
                # 由于虚拟渲染器的复杂性，这里提供一个简化的实现
                
                chunk_data = self._get_chunk_data(chunk_id)
                if chunk_data is not None:
                    success = self._render_chunk(ax, chunk_data, current_style, chunk_id)
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
            
            return rendered_any
            
        except Exception as e:
            logger.error(f"虚拟滚动成交量渲染失败: {e}")
            return False
    
    def _get_chunk_data(self, chunk_id: int) -> Optional[np.ndarray]:
        """获取指定块的成交量数据"""
        if self.volume_data is None:
            return None
        
        chunk_size = self.config.chunk_size
        start_idx = max(0, chunk_id * chunk_size)
        end_idx = min(len(self.volume_data), start_idx + chunk_size)
        
        if start_idx >= end_idx:
            return None
        
        return self.volume_data.iloc[start_idx:end_idx]['volume'].values
    
    def _render_chunk(self, ax, chunk_data: np.ndarray, 
                     style: VolumeRenderStyle, chunk_id: int) -> bool:
        """渲染单个数据块"""
        try:
            from matplotlib.collections import PolyCollection
            
            if len(chunk_data) == 0:
                return False
            
            # 创建该块的柱子
            chunk_size = self.config.chunk_size
            base_index = chunk_id * chunk_size
            
            verts = []
            colors = []
            
            for i, volume in enumerate(chunk_data):
                if volume > style.min_visible_volume:
                    x_val = base_index + i
                    left = x_val - style.width / 2
                    right = x_val + style.width / 2
                    
                    verts.append([
                        (left, 0), (left, volume), (right, volume), (right, 0)
                    ])
                    
                    # 颜色处理
                    if callable(style.color):
                        normalized_volume = volume / max(chunk_data) if max(chunk_data) > 0 else 0
                        colors.append(style.color(normalized_volume))
                    else:
                        colors.append(style.color)
            
            if verts:
                collection = PolyCollection(
                    verts, 
                    facecolors=colors if colors else style.color,
                    edgecolors=style.edge_color,
                    linewidths=style.edge_width,
                    alpha=style.alpha
                )
                
                ax.add_collection(collection)
                
                # 调试模式下显示块边界
                if style.show_chunks:
                    self._draw_chunk_boundary(ax, base_index, len(chunk_data), 
                                            style.chunk_border_color, 
                                            style.chunk_border_width)
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"渲染块 {chunk_id} 失败: {e}")
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
                (start_index - 0.5, 0),
                length + 1,
                max(ax.get_ylim()) if ax.get_ylim()[1] > 0 else 100,
                linewidth=width,
                edgecolor=color,
                facecolor='none',
                alpha=0.3
            )
            ax.add_patch(rect)
            
        except Exception as e:
            logger.warning(f"绘制块边界失败: {e}")
    
    def _on_chunk_rendered(self, chunk_id: int, chunk: RenderChunk):
        """处理虚拟滚动块渲染完成事件"""
        logger.debug(f"虚拟滚动块 {chunk_id} 渲染完成，包含 {len(chunk.data_points)} 个数据点")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        stats = self.render_stats.copy()
        
        # 添加虚拟滚动统计
        if hasattr(self.virtual_renderer, 'get_performance_stats'):
            virtual_stats = self.virtual_renderer.get_performance_stats()
            stats.update(virtual_stats)
        
        # 添加总体统计
        stats.update({
            'total_data_points': self.total_data_points,
            'virtual_scrolling_enabled': self.is_enabled,
            'rendered_chunks_count': len(self.rendered_chunks),
            'memory_estimate_mb': len(self.rendered_chunks) * 0.1  # 估算
        })
        
        return stats
    
    def cleanup(self):
        """清理资源"""
        if self.is_enabled and hasattr(self.virtual_renderer, 'cleanup'):
            self.virtual_renderer.cleanup()
        
        self.rendered_chunks.clear()
        self.volume_data = None
        self.volume_axis = None
        
        logger.info("成交量虚拟滚动渲染器资源已清理")

# 便捷函数
def create_volume_virtual_renderer(data: pd.DataFrame, 
                                 ax,
                                 config: Optional[VirtualizationConfig] = None,
                                 style: Optional[VolumeRenderStyle] = None) -> VolumeVirtualRenderer:
    """创建成交量虚拟滚动渲染器"""
    renderer = VolumeVirtualRenderer(config, style)
    renderer.set_volume_data(data, ax)
    return renderer

def optimize_volume_config_for_data_size(data_size: int) -> VirtualizationConfig:
    """根据数据大小优化成交量虚拟滚动配置"""
    if data_size > 1_000_000:  # 100万数据点
        return VirtualizationConfig(
            chunk_size=1000,
            overlap_size=100,
            max_visible_chunks=2,
            quality_levels=[1, 4, 8, 16, 32]
        )
    elif data_size > 100_000:  # 10万数据点
        return VirtualizationConfig(
            chunk_size=2000,
            overlap_size=200,
            max_visible_chunks=3,
            quality_levels=[1, 2, 4, 8, 16]
        )
    else:  # 小于10万数据点
        return VirtualizationConfig(
            chunk_size=5000,
            overlap_size=500,
            max_visible_chunks=2,
            quality_levels=[1, 2, 4, 8]
        )