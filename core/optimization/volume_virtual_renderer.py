#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
成交量虚拟滚动渲染器

专门优化的成交量图表虚拟滚动渲染器，基于VirtualScrollRenderer实现高效的成交量数据可视化
实现IVirtualRenderer通用接口，支持统一管理和扩展

作者: FactorWeave-Quant团队
版本: 2.1
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


class VolumeVirtualRenderer(BaseVirtualRenderer):
    """成交量虚拟滚动渲染器，继承自BaseVirtualRenderer"""

    _chart_type_name: str = "成交量"
    _data_attr_name: str = "volume_data"
    _default_chunk_size: int = 2000
    _default_overlap_size: int = 200
    _default_max_visible_chunks: int = 3

    def __init__(self,
                 config: Optional[VirtualizationConfig] = None,
                 style: Optional[VirtualRenderStyle] = None):
        self.volume_data = None
        self.volume_axis = None
        super().__init__(config=config, style=style)
    
    def set_data_source(self, data: Union[np.ndarray, pd.DataFrame, pd.Series]):
        """设置数据源，实现IVirtualRenderer接口"""
        self.volume_data = data
        # 数据源更新后清掉旧数据渲染的块记录，避免切周期/刷行情后渲染过期数据
        self.rendered_chunks.clear()

        if isinstance(data, pd.DataFrame) and len(data) > 0:
            self._total_data_points = len(data)
            if 'volume' in data.columns:
                volumes = data['volume'].values
                self.virtual_renderer.set_data_source(volumes)
            else:
                volumes = data.iloc[:, 0].values
                self.virtual_renderer.set_data_source(volumes)
                logger.warning("DataFrame没有'volume'列，使用第一列作为成交量数据")

            logger.info(f"成交量虚拟滚动数据源已设置: {self._total_data_points}个数据点")
        elif isinstance(data, pd.Series):
            self._total_data_points = len(data)
            self.virtual_renderer.set_data_source(data.values)
            logger.info(f"成交量虚拟滚动数据源已设置: {self._total_data_points}个数据点")
        elif isinstance(data, np.ndarray):
            self._total_data_points = len(data)
            self.virtual_renderer.set_data_source(data)
            logger.info(f"成交量虚拟滚动数据源已设置: {self._total_data_points}个数据点")
        else:
            self._total_data_points = 0
            logger.warning(f"无效的成交量数据源，数据点数量: {self._total_data_points}")
    
    def set_volume_data(self, volume_data: pd.DataFrame, volume_axis):
        """兼容旧接口，设置成交量数据和轴"""
        self.volume_data = volume_data
        self.volume_axis = volume_axis
        self.rendered_chunks.clear()
        self.set_data_source(volume_data)

    def _resolve_volume_colors(self, style) -> Tuple[str, str, str, str]:
        """解析成交量四色：volume_* 专属键优先，未设置回退 K 线同款 up/down 键。

        Returns:
            (up_color, down_color, limit_up_color, limit_down_color)
        """
        up_color = getattr(style, 'volume_up_color', None) or getattr(style, 'up_color', '#ff0000')
        down_color = getattr(style, 'volume_down_color', None) or getattr(style, 'down_color', '#00ff00')
        limit_up_color = getattr(style, 'limit_up_color', '#FF9800')
        limit_down_color = getattr(style, 'limit_down_color', '#AB47BC')
        return up_color, down_color, limit_up_color, limit_down_color

    def _classify_volume_colors(self, data) -> Optional[np.ndarray]:
        """按涨跌/涨跌停分类成交量柱子颜色类别（与 K 线四色判定一致）。

        类别编码：0=跌绿 1=涨红 2=涨停橙 3=跌停紫。
        数据非 DataFrame 或缺 open/close 列时返回 None（调用方降级单色/两色，不报错）。
        """
        if data is None or not hasattr(data, 'columns') or len(data) == 0:
            return None
        if 'open' not in data.columns or 'close' not in data.columns:
            return None
        closes = data['close'].values.astype(np.float64)
        opens = data['open'].values.astype(np.float64)
        categories = np.where(closes >= opens, 1, 0).astype(np.int8)
        if 'high' in data.columns and 'low' in data.columns:
            from core.rendering.limit_price import classify_limit_up_down, extract_symbol
            # R292-HV：列优先读取 limit 掩码（与 optimization/chart_renderer.py
            # K线/成交量一致）。'limit_up'/'limit_down' 列由上游在降采样前按全量数据
            # 计算并随切片保留；降采样后重判的"昨收"会错位导致与K线颜色不一致。
            if 'limit_up' in data.columns and 'limit_down' in data.columns:
                is_limit_up = data['limit_up'].to_numpy(dtype=bool)
                is_limit_down = data['limit_down'].to_numpy(dtype=bool)
            else:
                highs = data['high'].values.astype(np.float64)
                lows = data['low'].values.astype(np.float64)
                is_limit_up, is_limit_down = classify_limit_up_down(
                    closes, highs, lows, extract_symbol(data))
            # 优先级：涨停 → limit_up_color、跌停 → limit_down_color，与 K 线一致
            categories = np.where(is_limit_down, 3, np.where(is_limit_up, 2, categories))
        return categories

    def render_with_virtual_scroll(self, ax, data: pd.DataFrame,
                                        style: Dict[str, Any] = None,
                                        x: np.ndarray = None,
                                        use_datetime_axis: bool = True) -> bool:
        """使用虚拟滚动渲染成交量，实现IVirtualRenderer接口"""
        return super().render_with_virtual_scroll(ax, data, style=style, x=x, use_datetime_axis=use_datetime_axis)

    def _render_regular(self, ax, data, style, x, use_datetime_axis) -> bool:
        return self._render_volume_regular(ax, data, style, x, use_datetime_axis)

    def _render_virtual(self, ax, data, style, x, use_datetime_axis) -> bool:
        return self._render_volume_virtual(ax, data, style, x, use_datetime_axis)
    
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
                    # 使用字典更新样式
                    for key, value in style.items():
                        if hasattr(current_style, key):
                            setattr(current_style, key, value)
                
                # 创建柱子顶点
                verts = []
                colors = []

                # R292 四色：涨红/跌绿/涨停橙/跌停紫（数据含 open/close 时生效，判定与 K 线一致）
                up_color, down_color, limit_up_color, limit_down_color = \
                    self._resolve_volume_colors(current_style)
                # 类别编码 0=跌 1=涨 2=涨停 3=跌停（与 _classify_volume_colors / _render_chunk 一致）
                category_colors = (down_color, up_color, limit_up_color, limit_down_color)
                categories = self._classify_volume_colors(data)

                for i, (x_val, volume) in enumerate(zip(x_values, volumes)):
                    if volume > current_style.min_visible_value:
                        left = x_val - current_style.width / 2
                        right = x_val + current_style.width / 2
                        
                        verts.append([
                            (left, 0), (left, volume), (right, volume), (right, 0)
                        ])
                        
                        # 处理颜色：有 open/close 列 → 四色；否则保持原 callable/单色逻辑
                        if categories is not None and not callable(current_style.color):
                            colors.append(category_colors[int(categories[i])])
                        elif callable(current_style.color):
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
                    logger.debug(f"常规成交量渲染完成: {len(verts)}个柱子，耗时 {render_time*1000:.2f}ms")
            
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
            logger.error(f"虚拟滚动成交量渲染失败: {e}")
            return False
    
    def _get_chunk_data(self, chunk_id: int) -> Optional[Union[np.ndarray, pd.DataFrame]]:
        """获取指定块的数据（DataFrame 时保留 open/close 等列供四色判定）"""
        if self.volume_data is None:
            return None
        
        chunk_size = self.config.chunk_size
        start_idx = max(0, chunk_id * chunk_size)
        end_idx = min(len(self.volume_data), start_idx + chunk_size)
        
        if start_idx >= end_idx:
            return None
        
        # 切片 DataFrame 子集（含 volume 及 open/close/high/low/symbol 列），
        # 供 _render_chunk 做四色分类；无 open/close 列时等价旧行为（仅 volume）
        if isinstance(self.volume_data, pd.DataFrame):
            chunk_data = self.volume_data.iloc[start_idx:end_idx]
            if 'volume' in chunk_data.columns:
                volume_col = chunk_data['volume'].values.astype(np.float64)
            else:
                volume_col = chunk_data.iloc[:, 0].values.astype(np.float64)
        else:
            chunk_data = np.asarray(self.volume_data[start_idx:end_idx], dtype=np.float64)
            volume_col = chunk_data
        
        max_vol = float(volume_col.max()) if len(volume_col) > 0 else 0.0
        
        # 创建RenderChunk并添加到缓存
        chunk = RenderChunk(
            start_index=start_idx,
            end_index=end_idx,
            data_points=chunk_data,
            bounding_rect=QRectF(start_idx, 0, len(volume_col), max_vol),
            render_time=0.0,
            quality_level=self.virtual_renderer.quality_level
        )
        
        self.virtual_renderer._add_chunk_to_cache(chunk_id, chunk)
        
        return chunk_data
    
    def _render_chunk(self, ax, chunk_data, 
                     style: VirtualRenderStyle, chunk_id: int, 
                     x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """渲染单个数据块（兼容 DataFrame 切片与 ndarray 两种 chunk 数据）"""
        try:
            from matplotlib.collections import PolyCollection
            
            if chunk_data is None or len(chunk_data) == 0:
                logger.debug(f"跳过空数据块渲染: {chunk_id}")
                return False
            
            render_start = time.time()
            
            # 创建该块的柱子
            chunk_size = self.config.chunk_size
            base_index = chunk_id * chunk_size
            
            # 提取成交量列：DataFrame 优先取 volume 列，ndarray 即成交量数组
            if isinstance(chunk_data, pd.DataFrame):
                if 'volume' in chunk_data.columns:
                    volumes = chunk_data['volume'].values.astype(np.float64)
                else:
                    volumes = chunk_data.iloc[:, 0].values.astype(np.float64)
            else:
                volumes = np.asarray(chunk_data, dtype=np.float64)
            
            # 准备X轴数据
            if x is not None and len(x) > base_index + len(volumes):
                # 使用提供的X轴数据
                chunk_x = x[base_index:base_index + len(volumes)]
            else:
                # 使用默认的X轴数据
                chunk_x = np.arange(base_index, base_index + len(volumes))
            
            verts = []
            colors = []
            
            # R292 四色：涨红/跌绿/涨停橙/跌停紫（chunk 带 open/close 列时生效）
            up_color, down_color, limit_up_color, limit_down_color = \
                self._resolve_volume_colors(style)
            # 索引与 _classify_volume_colors 类别编码一致：0=跌 1=涨 2=涨停 3=跌停
            category_colors = (down_color, up_color, limit_up_color, limit_down_color)
            categories = self._classify_volume_colors(chunk_data)
            
            for i, (x_val, volume) in enumerate(zip(chunk_x, volumes)):
                if volume > style.min_visible_value:
                    left = x_val - style.width / 2
                    right = x_val + style.width / 2
                    
                    verts.append([
                        (left, 0), (left, volume), (right, volume), (right, 0)
                    ])
                    
                    # 处理颜色：有 open/close 列 → 四色；否则保持原 callable/单色逻辑
                    if categories is not None and not callable(style.color):
                        colors.append(category_colors[int(categories[i])])
                    elif callable(style.color):
                        normalized_volume = normalize_value(volume, max(volumes))
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
                    self._draw_chunk_boundary(ax, base_index, len(volumes), 
                                            style.chunk_border_color, 
                                            style.chunk_border_width)
                
                render_time = (time.time() - render_start) * 1000
                logger.debug(f"块渲染完成: ID={chunk_id}, 数据点={len(volumes)}, 柱子数={len(verts)}, 耗时={render_time:.2f}ms")
                
                return True
            
            logger.debug(f"块渲染无可见元素: ID={chunk_id}, 数据点={len(volumes)}")
            return False
            
        except Exception as e:
            logger.error(f"渲染块 {chunk_id} 失败: {e}")
            return False
    
    def _get_visible_rect(self, ax) -> QRectF:
        return super()._get_visible_rect(ax)

    def _draw_chunk_boundary(self, ax, start_index: int, length: int,
                           color: str, width: float):
        from core.optimization.render_utils import draw_chunk_boundary
        draw_chunk_boundary(ax, start_index, length, color, width, y_min=0)

    def cleanup(self):
        """清理资源"""
        logger.info("清理成交量虚拟滚动渲染器资源")
        self.volume_data = None
        self.volume_axis = None
        super().cleanup()
        logger.info("成交量虚拟滚动渲染器资源清理完成")
    
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
def create_volume_virtual_renderer(data: pd.DataFrame, 
                                 ax,
                                 config: Optional[VirtualizationConfig] = None,
                                 style: Optional[VirtualRenderStyle] = None) -> VolumeVirtualRenderer:
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