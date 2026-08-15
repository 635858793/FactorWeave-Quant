#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
K线图虚拟滚动渲染器

专门优化的K线图虚拟滚动渲染器，基于VirtualScrollRenderer实现高效的K线数据可视化
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

from core.optimization.base_virtual_renderer import BaseVirtualRenderer
# R292 涨跌停精确判定（按板块计算涨/跌停价，替代固定 4.8% 阈值）
from core.rendering.limit_price import classify_limit_up_down, extract_symbol


class CandleVirtualRenderer(BaseVirtualRenderer):
    """K线图虚拟滚动渲染器，继承自BaseVirtualRenderer"""

    _chart_type_name: str = "K线图"
    _data_attr_name: str = "candle_data"
    _default_chunk_size: int = 1000
    _default_overlap_size: int = 100
    _default_max_visible_chunks: int = 4

    def __init__(self,
                 config: Optional[VirtualizationConfig] = None,
                 style: Optional[VirtualRenderStyle] = None):
        self.candle_data = None
        self.candle_axis = None
        super().__init__(config=config, style=style)
    
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
            self.virtual_renderer.set_data_source(data)

            logger.info(f"K线图虚拟滚动数据源已设置: {self._total_data_points}个数据点")
        elif isinstance(data, (np.ndarray, pd.Series)):
            self._total_data_points = 0
            logger.warning(f"K线图需要DataFrame类型的OHLC数据，不支持{type(data).__name__}类型")
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
        return super().render_with_virtual_scroll(ax, data, style=style, x=x, use_datetime_axis=use_datetime_axis)

    def _render_regular(self, ax, data, style, x, use_datetime_axis) -> bool:
        return self._render_candle_regular(ax, data, style, x, use_datetime_axis)

    def _render_virtual(self, ax, data, style, x, use_datetime_axis) -> bool:
        return self._render_candle_virtual(ax, data, style, x, use_datetime_axis)
    
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
                
                # R292 精确判定：按板块涨/跌停价（与各渲染路径共用
                # core/rendering/limit_price.py，替代固定 4.8% 阈值）
                is_limit_up, is_limit_down = classify_limit_up_down(
                    closes, highs, lows, extract_symbol(data))
                
                # 准备K线数据
                verts_up = []  # 阳线（上涨，红色）
                verts_down = []  # 阴线（下跌，绿色）
                verts_limit_up = []  # 涨停（橙色）
                verts_limit_down = []  # 跌停（紫色）
                segments_up = []  # 上涨影线
                segments_down = []  # 下跌影线
                segments_limit_up = []  # 涨停影线
                segments_limit_down = []  # 跌停影线
                
                # 增加蜡烛宽度从0.3到0.45，使蜡烛更宽更清晰
                candle_half_width = 0.45
                for i, (x_val, open_price, high, low, close) in enumerate(zip(x_values, opens, highs, lows, closes)):
                    left = x_val - candle_half_width
                    right = x_val + candle_half_width
                    
                    if is_limit_up[i]:
                        # 涨停（橙色）
                        verts_limit_up.append([
                            (left, open_price), (left, close), (right, close), (right, open_price)
                        ])
                        segments_limit_up.append([(x_val, low), (x_val, high)])
                    elif is_limit_down[i]:
                        # 跌停（紫色）
                        verts_limit_down.append([
                            (left, open_price), (left, close), (right, close), (right, open_price)
                        ])
                        segments_limit_down.append([(x_val, low), (x_val, high)])
                    elif close >= open_price:
                        # 阳线（上涨）
                        verts_up.append([
                            (left, open_price), (left, close), (right, close), (right, open_price)
                        ])
                        segments_up.append([(x_val, low), (x_val, high)])
                    else:
                        # 阴线（下跌）
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
                
                if verts_limit_up:
                    collection_limit_up = PolyCollection(
                        verts_limit_up,
                        facecolor=current_style.candle_limit_up_color,  # 涨停实心（橙色）
                        edgecolor=current_style.candle_limit_up_color,
                        linewidth=1.2,
                        alpha=current_style.alpha
                    )
                    ax.add_collection(collection_limit_up)
                
                if verts_limit_down:
                    collection_limit_down = PolyCollection(
                        verts_limit_down,
                        facecolor=current_style.candle_limit_down_color,  # 跌停实心（紫色）
                        edgecolor=current_style.candle_limit_down_color,
                        linewidth=1.2,
                        alpha=current_style.alpha
                    )
                    ax.add_collection(collection_limit_down)
                
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
                
                if segments_limit_up:
                    line_collection_limit_up = LineCollection(
                        segments_limit_up,
                        colors=current_style.candle_limit_up_color,
                        linewidth=0.8,
                        alpha=current_style.alpha
                    )
                    ax.add_collection(line_collection_limit_up)
                
                if segments_limit_down:
                    line_collection_limit_down = LineCollection(
                        segments_limit_down,
                        colors=current_style.candle_limit_down_color,
                        linewidth=0.8,
                        alpha=current_style.alpha
                    )
                    ax.add_collection(line_collection_limit_down)
                
                if current_style.show_chunks:
                    self._render_chunk_boundaries(ax)
                
                ax.autoscale_view()
                
                render_time = time.time() - start_time
                logger.debug(f"常规K线图渲染完成: {len(data)}个K线，耗时 {render_time*1000:.2f}ms")
            
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
        viewport_height = 100.0
        if self.candle_axis is not None:
            try:
                ylim = self.candle_axis.get_ylim()
                viewport_height = float(ylim[1] - ylim[0])
            except Exception:
                if self.candle_data is not None and not self.candle_data.empty:
                    viewport_height = float(self.candle_data['high'].max() - self.candle_data['low'].min())
        chunk = RenderChunk(
            start_index=start_idx,
            end_index=end_idx,
            data_points=chunk_data,
            bounding_rect=QRectF(start_idx, 0, len(chunk_data), viewport_height),
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
            
            # R292 精确判定：按板块涨/跌停价（与各渲染路径共用
            # core/rendering/limit_price.py，替代固定 4.8% 阈值）。
            # 跨块边界用全量数据计算保证准确，再按块切片。
            if self.candle_data is not None and hasattr(self.candle_data, 'columns') \
                    and 'close' in self.candle_data.columns:
                all_closes = self.candle_data['close'].values
                all_highs = self.candle_data['high'].values
                all_lows = self.candle_data['low'].values
                all_lu, all_ld = classify_limit_up_down(
                    all_closes, all_highs, all_lows,
                    extract_symbol(self.candle_data))
                end_idx = base_index + len(closes)
                is_limit_up = all_lu[base_index:end_idx]
                is_limit_down = all_ld[base_index:end_idx]
            else:
                is_limit_up, is_limit_down = classify_limit_up_down(
                    closes, highs, lows, extract_symbol(chunk_data))
            
            # 准备K线数据
            verts_up = []  # 阳线（上涨，红色）
            verts_down = []  # 阴线（下跌，绿色）
            verts_limit_up = []  # 涨停（橙色）
            verts_limit_down = []  # 跌停（紫色）
            segments_up = []  # 上涨影线
            segments_down = []  # 下跌影线
            segments_limit_up = []  # 涨停影线
            segments_limit_down = []  # 跌停影线
            
            # 增加蜡烛宽度从0.3到0.45，使蜡烛更宽更清晰
            candle_half_width = 0.45
            for i, (x_val, open_price, high, low, close) in enumerate(zip(chunk_x, opens, highs, lows, closes)):
                left = x_val - candle_half_width
                right = x_val + candle_half_width
                
                if is_limit_up[i]:
                    # 涨停（橙色）
                    verts_limit_up.append([
                        (left, open_price), (left, close), (right, close), (right, open_price)
                    ])
                    segments_limit_up.append([(x_val, low), (x_val, high)])
                elif is_limit_down[i]:
                    # 跌停（紫色）
                    verts_limit_down.append([
                        (left, open_price), (left, close), (right, close), (right, open_price)
                    ])
                    segments_limit_down.append([(x_val, low), (x_val, high)])
                elif close >= open_price:
                    # 阳线（上涨）
                    verts_up.append([
                        (left, open_price), (left, close), (right, close), (right, open_price)
                    ])
                    segments_up.append([(x_val, low), (x_val, high)])
                else:
                    # 阴线（下跌）
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
                    facecolor=style.candle_down_color,  # 阴线实心
                    edgecolor=style.candle_down_color,
                    linewidth=0.8,
                    alpha=style.alpha
                )
                ax.add_collection(collection_down)
            
            if verts_limit_up:
                collection_limit_up = PolyCollection(
                    verts_limit_up,
                    facecolor=style.candle_limit_up_color,  # 涨停实心（橙色）
                    edgecolor=style.candle_limit_up_color,
                    linewidth=1.2,
                    alpha=style.alpha
                )
                ax.add_collection(collection_limit_up)
            
            if verts_limit_down:
                collection_limit_down = PolyCollection(
                    verts_limit_down,
                    facecolor=style.candle_limit_down_color,  # 跌停实心（紫色）
                    edgecolor=style.candle_limit_down_color,
                    linewidth=1.2,
                    alpha=style.alpha
                )
                ax.add_collection(collection_limit_down)
            
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
            
            if segments_limit_up:
                line_collection_limit_up = LineCollection(
                    segments_limit_up,
                    colors=style.candle_limit_up_color,
                    linewidth=1.0,
                    alpha=style.alpha
                )
                ax.add_collection(line_collection_limit_up)
            
            if segments_limit_down:
                line_collection_limit_down = LineCollection(
                    segments_limit_down,
                    colors=style.candle_limit_down_color,
                    linewidth=1.0,
                    alpha=style.alpha
                )
                ax.add_collection(line_collection_limit_down)
            
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
        return super()._get_visible_rect(ax)

    def _draw_chunk_boundary(self, ax, start_index: int, length: int,
                           color: str, width: float):
        from core.optimization.render_utils import draw_chunk_boundary
        draw_chunk_boundary(ax, start_index, length, color, width)

    def cleanup(self):
        """清理资源"""
        logger.info("清理K线图虚拟滚动渲染器资源")
        self.candle_data = None
        self.candle_axis = None
        super().cleanup()
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
