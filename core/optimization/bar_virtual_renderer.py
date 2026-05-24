#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
柱状图虚拟滚动渲染器

专门优化的柱状图虚拟滚动渲染器，基于VirtualScrollRenderer实现高效的柱状数据可视化
实现IVirtualRenderer通用接口，支持统一管理和扩展

作者: FactorWeave-Quant团队
版本: 1.1
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from PyQt5.QtCore import QRectF
from loguru import logger
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.advanced_optimization.performance.virtualization import (
    VirtualizationConfig,
    RenderChunk,
    VirtualRenderStyle
)

from core.optimization.render_utils import normalize_value
from core.optimization.base_virtual_renderer import BaseVirtualRenderer


class BarVirtualRenderer(BaseVirtualRenderer):
    """柱状图虚拟滚动渲染器，继承自BaseVirtualRenderer"""

    _chart_type_name: str = "柱状图"
    _data_attr_name: str = "bar_data"
    _default_chunk_size: int = 2000
    _default_overlap_size: int = 200
    _default_max_visible_chunks: int = 3

    def __init__(self,
                 config: Optional[VirtualizationConfig] = None,
                 style: Optional[VirtualRenderStyle] = None):
        self.bar_data = None
        self.bar_axis = None
        super().__init__(config=config, style=style)
    
    def set_data_source(self, data: Union[np.ndarray, pd.DataFrame, pd.Series]):
        """设置数据源，实现IVirtualRenderer接口"""
        self.bar_data = data
        
        # 处理不同类型的数据源
        if isinstance(data, pd.Series):
            self._total_data_points = len(data)
            self.virtual_renderer.set_data_source(data.values)
            logger.info(f"柱状图虚拟滚动数据源已设置: {self._total_data_points}个数据点")
        elif isinstance(data, pd.DataFrame):
            # 取第一列作为柱状数据
            self._total_data_points = len(data)
            y_data = data.iloc[:, 0].values
            self.virtual_renderer.set_data_source(y_data)
            logger.info(f"柱状图虚拟滚动数据源已设置: {self._total_data_points}个数据点")
        elif isinstance(data, np.ndarray):
            self._total_data_points = len(data)
            self.virtual_renderer.set_data_source(data)
            logger.info(f"柱状图虚拟滚动数据源已设置: {self._total_data_points}个数据点")
        else:
            self._total_data_points = 0
            logger.warning(f"无效的柱状图数据源类型: {type(data)}")
    
    def set_bar_data(self, bar_data: Union[pd.DataFrame, pd.Series, np.ndarray], bar_axis):
        """兼容接口，设置柱状数据和轴"""
        self.bar_data = bar_data
        self.bar_axis = bar_axis
        self.set_data_source(bar_data)

    def render_with_virtual_scroll(self, ax, data: Union[pd.DataFrame, pd.Series, np.ndarray],
                                        style: Dict[str, Any] = None,
                                        x: np.ndarray = None,
                                        use_datetime_axis: bool = True) -> bool:
        """使用虚拟滚动渲染柱状图，实现IVirtualRenderer接口"""
        return super().render_with_virtual_scroll(ax, data, style=style, x=x, use_datetime_axis=use_datetime_axis)

    def _render_regular(self, ax, data, style, x, use_datetime_axis) -> bool:
        return self._render_bar_regular(ax, data, style, x, use_datetime_axis)

    def _render_virtual(self, ax, data, style, x, use_datetime_axis) -> bool:
        return self._render_bar_virtual(ax, data, style, x, use_datetime_axis)
    
    def _render_bar_regular(self, ax, data: Union[pd.DataFrame, pd.Series, np.ndarray], 
                              style: Dict[str, Any] = None,
                              x: np.ndarray = None, 
                              use_datetime_axis: bool = True) -> bool:
        """常规渲染（降级方案）"""
        try:
            start_time = time.time()
            
            if ax and len(data) > 0:
                from matplotlib.collections import PolyCollection
                
                # 准备数据
                if isinstance(data, pd.Series):
                    y_values = data.values
                elif isinstance(data, pd.DataFrame):
                    y_values = data.iloc[:, 0].values
                else:
                    y_values = data
                
                x_values = x if x is not None else np.arange(len(y_values))
                
                # 样式处理
                current_style = self.style
                if style:
                    # 使用字典更新样式
                    for key, value in style.items():
                        if hasattr(current_style, key):
                            setattr(current_style, key, value)
                
                # 创建PolyCollection
                verts = []
                colors = []
                
                for x_val, y_val in zip(x_values, y_values):
                    if y_val > current_style.min_visible_value:
                        left = x_val - 0.3
                        right = x_val + 0.3
                        
                        verts.append([
                            (left, 0), (left, y_val), (right, y_val), (right, 0)
                        ])
                        
                        if callable(current_style.color):
                            normalized_value = y_val / max(y_values) if max(y_values) > 0 else 0
                            colors.append(current_style.color(normalized_value))
                        else:
                            colors.append(current_style.color)
                
                if verts:
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
                    logger.debug(f"常规柱状图渲染完成: {len(verts)}个柱子，耗时 {render_time*1000:.2f}ms")
            
            return True
            
        except Exception as e:
            logger.error(f"常规柱状图渲染失败: {e}")
            return False
    
    def _render_bar_virtual(self, ax, data: Union[pd.DataFrame, pd.Series, np.ndarray], 
                              style: Dict[str, Any] = None,
                              x: np.ndarray = None, 
                              use_datetime_axis: bool = True) -> bool:
        """虚拟滚动渲染柱状图"""
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
            chunk_start = max(0, int(visible_rect.x() / self.config.chunk_size) - 1)
            chunk_end = int((visible_rect.x() + visible_rect.width()) / self.config.chunk_size) + 1
            
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
            logger.error(f"虚拟滚动柱状图渲染失败: {e}")
            return False
    
    def _get_chunk_data(self, chunk_id: int) -> Optional[np.ndarray]:
        """获取指定块的柱状数据"""
        if self.bar_data is None:
            return None
        
        chunk_size = self.config.chunk_size
        start_idx = max(0, chunk_id * chunk_size)
        end_idx = min(len(self.bar_data), start_idx + chunk_size)
        
        if start_idx >= end_idx:
            return None
        
        # 准备块数据
        if isinstance(self.bar_data, pd.Series):
            chunk_data = self.bar_data.iloc[start_idx:end_idx].values
        elif isinstance(self.bar_data, pd.DataFrame):
            chunk_data = self.bar_data.iloc[start_idx:end_idx].iloc[:, 0].values
        else:
            chunk_data = self.bar_data[start_idx:end_idx]
        
        # 创建RenderChunk并添加到缓存
        chunk = RenderChunk(
            start_index=start_idx,
            end_index=end_idx,
            data_points=chunk_data,
            bounding_rect=QRectF(start_idx, 0, len(chunk_data), max(chunk_data) if len(chunk_data) > 0 else 100),
            render_time=0.0,
            quality_level=self.virtual_renderer.quality_level
        )
        
        self.virtual_renderer._add_chunk_to_cache(chunk_id, chunk)
        
        return chunk_data
    
    def _render_chunk(self, ax, chunk_data: np.ndarray, 
                     style: VirtualRenderStyle, chunk_id: int, 
                     x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """渲染单个柱状图块"""
        try:
            from matplotlib.collections import PolyCollection
            
            if len(chunk_data) == 0:
                return False
            
            # 创建该块的柱状
            chunk_size = self.config.chunk_size
            base_index = chunk_id * chunk_size
            
            # 准备X轴数据
            if x is not None and len(x) > base_index + len(chunk_data):
                # 使用提供的X轴数据
                chunk_x = x[base_index:base_index + len(chunk_data)]
            else:
                # 使用默认的X轴数据
                chunk_x = np.arange(base_index, base_index + len(chunk_data))
            
            # 准备柱状数据
            verts = []
            colors = []
            
            for x_val, y_val in zip(chunk_x, chunk_data):
                if y_val > style.min_visible_value:
                    left = x_val - 0.3
                    right = x_val + 0.3
                    
                    verts.append([
                        (left, 0), (left, y_val), (right, y_val), (right, 0)
                    ])
                    
                    if callable(style.color):
                        normalized_value = normalize_value(y_val, max(chunk_data))
                        colors.append(style.color(normalized_value))
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
            logger.error(f"渲染柱状图块 {chunk_id} 失败: {e}")
            return False
    
    def _get_visible_rect(self, ax) -> QRectF:
        return super()._get_visible_rect(ax)

    def _draw_chunk_boundary(self, ax, start_index: int, length: int,
                           color: str, width: float):
        from core.optimization.render_utils import draw_chunk_boundary
        draw_chunk_boundary(ax, start_index, length, color, width)

    def cleanup(self):
        """清理资源"""
        logger.info("清理柱状图虚拟滚动渲染器资源")
        self.bar_data = None
        self.bar_axis = None
        super().cleanup()
        logger.info("柱状图虚拟滚动渲染器资源清理完成")
    
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

# 便捷函数
def create_bar_virtual_renderer(data: Union[pd.DataFrame, pd.Series, np.ndarray], 
                                 ax,
                                 config: Optional[VirtualizationConfig] = None,
                                 style: Optional[VirtualRenderStyle] = None) -> BarVirtualRenderer:
    """创建柱状图虚拟滚动渲染器"""
    renderer = BarVirtualRenderer(config, style)
    renderer.set_bar_data(data, ax)
    return renderer

def optimize_bar_config_for_data_size(data_size: int) -> VirtualizationConfig:
    """根据数据大小优化柱状图虚拟滚动配置"""
    if data_size > 1_000_000:  # 100万数据点
        return VirtualizationConfig(
            chunk_size=3000,
            overlap_size=300,
            max_visible_chunks=2,
            quality_levels=[1, 4, 8, 16, 32],
            cache_size=100
        )
    elif data_size > 100_000:  # 10万数据点
        return VirtualizationConfig(
            chunk_size=2000,
            overlap_size=200,
            max_visible_chunks=3,
            quality_levels=[1, 2, 4, 8, 16],
            cache_size=50
        )
    else:  # 小于10万数据点
        return VirtualizationConfig(
            chunk_size=5000,
            overlap_size=500,
            max_visible_chunks=2,
            quality_levels=[1, 2, 4, 8],
            cache_size=20
        )
