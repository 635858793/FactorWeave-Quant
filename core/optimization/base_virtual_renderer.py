#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
虚拟滚动渲染器公共基类

提取 candle/line/bar/volume 四个虚拟渲染器的公共代码，
减少约80%的代码重复。

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

from core.optimization.render_utils import (
    get_visible_rect,
    draw_chunk_boundary,
    compute_performance_stats,
)


class BaseVirtualRenderer(QObject):
    """虚拟滚动渲染器基类

    提取四个子渲染器（Candle/Line/Bar/Volume）的公共代码，
    子类只需覆盖与具体图表类型相关的方法。
    """

    data_rendered = pyqtSignal(int, object)
    rendering_progress = pyqtSignal(float)
    performance_warning = pyqtSignal(str, float)
    virtual_scroll_enabled = pyqtSignal(bool)

    # ---- 子类必须覆盖的属性 ----
    _chart_type_name: str = "图表"
    _data_attr_name: str = "_data"
    _default_chunk_size: int = 2000
    _default_overlap_size: int = 200
    _default_max_visible_chunks: int = 3

    def __init__(self,
                 config: Optional[VirtualizationConfig] = None,
                 style: Optional[VirtualRenderStyle] = None):
        super().__init__()

        self.config = config or self._create_optimized_config()
        self.style = style or VirtualRenderStyle()

        self.virtual_renderer = VirtualScrollRenderer(self.config)
        self.virtual_renderer.data_rendered.connect(self.data_rendered.emit)
        self.virtual_renderer.performance_warning.connect(self.performance_warning.emit)

        self._is_enabled = True
        self._total_data_points = 0
        self.rendered_chunks: Dict[int, Any] = {}

        self.render_stats = {
            'total_render_time_ms': 0.0,
            'chunks_rendered': 0,
            'data_points_processed': 0,
            'memory_usage_estimate_mb': 0.0
        }

        logger.info(f"{self._chart_type_name}虚拟滚动渲染器初始化完成，配置: {dict(chunk_size=self.config.chunk_size, adaptive_quality=self.config.adaptive_quality, cache_size=self.config.cache_size)}")

    def _create_optimized_config(self) -> VirtualizationConfig:
        """创建优化的虚拟滚动配置，子类可通过属性覆盖参数"""
        return VirtualizationConfig(
            chunk_size=self._default_chunk_size,
            overlap_size=self._default_overlap_size,
            max_visible_chunks=self._default_max_visible_chunks,
            max_render_time_ms=8.33,
            memory_threshold_mb=50,
            cleanup_threshold=0.7,
            adaptive_quality=True,
            min_quality=0.5,
            quality_levels=[1, 2, 4, 8],
            scroll_threshold=30,
            preload_distance=500,
            cache_size=50,
            cache_policy="lru"
        )

    def enable_virtual_scrolling(self, enabled: bool):
        """启用/禁用虚拟滚动"""
        self._is_enabled = enabled
        self.virtual_scroll_enabled.emit(enabled)
        self.virtual_renderer.enable_virtual_scrolling(enabled)

        if not enabled:
            self.cleanup()

        logger.info(f"{self._chart_type_name}虚拟滚动{'启用' if enabled else '禁用'}")

    def set_data_source(self, data: Union[np.ndarray, pd.DataFrame, pd.Series]):
        """设置数据源 - 子类可覆盖以处理特定数据类型"""
        setattr(self, self._data_attr_name, data)
        self._set_data_source_impl(data)

    def _set_data_source_impl(self, data):
        """默认数据源处理逻辑：处理 Series/DataFrame/ndarray"""
        if isinstance(data, pd.Series):
            self._total_data_points = len(data)
            self.virtual_renderer.set_data_source(data.values)
            logger.info(f"{self._chart_type_name}虚拟滚动数据源已设置: {self._total_data_points}个数据点")
        elif isinstance(data, pd.DataFrame):
            self._total_data_points = len(data)
            y_data = data.iloc[:, 0].values
            self.virtual_renderer.set_data_source(y_data)
            logger.info(f"{self._chart_type_name}虚拟滚动数据源已设置: {self._total_data_points}个数据点")
        elif isinstance(data, np.ndarray):
            self._total_data_points = len(data)
            self.virtual_renderer.set_data_source(data)
            logger.info(f"{self._chart_type_name}虚拟滚动数据源已设置: {self._total_data_points}个数据点")
        else:
            self._total_data_points = 0
            logger.warning(f"无效的{self._chart_type_name}数据源类型: {type(data)}")

    def _check_data_ready(self) -> bool:
        """检查数据是否已就绪"""
        data = getattr(self, self._data_attr_name, None)
        return self._is_enabled and data is not None

    def _should_use_regular_render(self, data) -> bool:
        """判断是否应该使用常规渲染（数据量小）"""
        if data is not None and hasattr(data, '__len__'):
            total = len(data) if not isinstance(data, (pd.Series, pd.DataFrame)) else self._total_data_points
            return self._total_data_points < self.config.chunk_size * 2
        return False

    def _apply_style_overrides(self, style: Optional[Dict[str, Any]] = None):
        """应用样式覆盖"""
        if style:
            for key, value in style.items():
                if hasattr(self.style, key):
                    setattr(self.style, key, value)

    def render_with_virtual_scroll(self, ax, data,
                                   style: Dict[str, Any] = None,
                                   x: np.ndarray = None,
                                   use_datetime_axis: bool = True) -> bool:
        """使用虚拟滚动渲染，实现IVirtualRenderer接口

        子类需要实现 _render_regular() 和 _render_virtual() 两个方法。
        """
        if not self._check_data_ready():
            logger.info(f"{self._chart_type_name}虚拟滚动未启用或数据源为空，降级到常规渲染")
            return self._render_regular(ax, data, style, x, use_datetime_axis)

        try:
            start_time = time.time()
            logger.info(f"开始使用虚拟滚动渲染{self._chart_type_name}: {len(data)}个数据点")

            visible_rect = self._get_visible_rect(ax)
            self.virtual_renderer.update_viewport(visible_rect)

            if self._should_use_regular_render(data):
                logger.info(f"{self._chart_type_name}数据量较小({len(data)} < {self.config.chunk_size * 2})，使用常规渲染")
                return self._render_regular(ax, data, style, x, use_datetime_axis)

            success = self._render_virtual(ax, data, style, x, use_datetime_axis)

            render_time = time.time() - start_time
            self.render_stats['total_render_time_ms'] += render_time * 1000
            self.render_stats['data_points_processed'] += len(data)

            logger.info(f"{self._chart_type_name}虚拟滚动渲染完成: {render_time*1000:.2f}ms, 渲染块数量: {len(self.rendered_chunks)}")
            return success

        except Exception as e:
            logger.error(f"虚拟滚动{self._chart_type_name}渲染失败: {e}")
            return self._render_regular(ax, data, style, x, use_datetime_axis)

    def _render_regular(self, ax, data, style, x, use_datetime_axis) -> bool:
        """常规渲染（降级方案）- 子类必须覆盖"""
        raise NotImplementedError(f"{self.__class__.__name__} 必须实现 _render_regular 方法")

    def _render_virtual(self, ax, data, style, x, use_datetime_axis) -> bool:
        """虚拟滚动渲染 - 子类必须覆盖"""
        raise NotImplementedError(f"{self.__class__.__name__} 必须实现 _render_virtual 方法")

    def _get_visible_rect(self, ax) -> QRectF:
        """获取视口的可见矩形区域"""
        return get_visible_rect(ax)

    def _render_chunk_boundaries(self, ax):
        """渲染块边界"""
        draw_chunk_boundary(ax, self.config)

    def cleanup(self):
        """清理资源"""
        self.virtual_renderer.cleanup()
        self.rendered_chunks.clear()
        self._total_data_points = 0

    def get_render_stats(self) -> Dict[str, Any]:
        """获取渲染统计信息"""
        stats = compute_performance_stats(
            total_render_time_ms=self.render_stats['total_render_time_ms'],
            chunks_rendered=self.render_stats['chunks_rendered'],
            data_points_processed=self.render_stats['data_points_processed'],
            memory_usage_estimate_mb=self.render_stats['memory_usage_estimate_mb'],
        )
        return stats