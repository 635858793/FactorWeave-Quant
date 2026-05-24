#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
渲染器共享工具函数

提供颜色映射、数据归一化、坐标变换等公共函数，
供 bar/candle/line/volume 虚拟渲染器复用。

作者: FactorWeave-Quant团队
版本: 1.0
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Union
from PyQt5.QtCore import QRectF
from loguru import logger


def get_visible_rect(ax) -> QRectF:
    if ax is None:
        return QRectF(0, 0, 100, 100)

    try:
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        return QRectF(xlim[0], ylim[0], xlim[1] - xlim[0], ylim[1] - ylim[0])
    except Exception as e:
        logger.warning(f"获取可见区域失败: {e}")
        return QRectF(0, 0, 100, 100)


def draw_chunk_boundary(ax, start_index: int, length: int,
                        color: str, width: float, y_min: float = None):
    try:
        import matplotlib.patches as patches

        y_bottom = y_min if y_min is not None else ax.get_ylim()[0]
        y_height = ax.get_ylim()[1] - y_bottom

        rect = patches.Rectangle(
            (start_index - 0.5, y_bottom),
            length + 1,
            y_height,
            linewidth=width,
            edgecolor=color,
            facecolor='none',
            alpha=0.3
        )
        ax.add_patch(rect)
    except Exception as e:
        logger.warning(f"绘制块边界失败: {e}")


def compute_performance_stats(
    render_stats: Dict[str, Any],
    virtual_renderer,
    total_data_points: int,
    is_enabled: bool,
    rendered_chunks: dict
) -> Dict[str, Any]:
    stats = render_stats.copy()

    if hasattr(virtual_renderer, 'get_performance_stats'):
        virtual_stats = virtual_renderer.get_performance_stats()
        stats.update(virtual_stats)

    stats.update({
        'total_data_points': total_data_points,
        'virtual_scrolling_enabled': is_enabled,
        'rendered_chunks_count': len(rendered_chunks),
        'memory_estimate_mb': len(rendered_chunks) * 0.1
    })

    return stats


def normalize_value(value: float, max_value: float) -> float:
    if max_value > 0:
        return value / max_value
    return 0.0


def normalize_array(values: np.ndarray) -> np.ndarray:
    max_val = np.max(values)
    if max_val > 0:
        return values / max_val
    return np.zeros_like(values)


def extract_y_values(data: Union[np.ndarray, pd.DataFrame, pd.Series]) -> np.ndarray:
    if isinstance(data, pd.Series):
        return data.values
    elif isinstance(data, pd.DataFrame):
        return data.iloc[:, 0].values
    return np.asarray(data)


def prepare_x_values(x: Optional[np.ndarray], base_index: int,
                     chunk_len: int, total_len: int = None) -> np.ndarray:
    if x is not None and (total_len is None or len(x) > base_index + chunk_len):
        return x[base_index:base_index + chunk_len]
    return np.arange(base_index, base_index + chunk_len)


COLOR_MAP_HEAT = {
    'cold': '#2166AC',
    'neutral': '#F7F7F7',
    'warm': '#D6604D',
    'hot': '#B2182B',
    'up': '#DC143C',
    'down': '#228B22',
    'line': '#1f77b4',
    'bar': '#2E86AB',
    'volume_up': '#DC143C',
    'volume_down': '#228B22',
}


PREDEFINED_COLORMAPS = {
    'blues': lambda x: (0.1 + 0.9 * x, 0.2 + 0.4 * x, 0.6 + 0.4 * x, 1.0),
    'reds': lambda x: (0.6 + 0.4 * x, 0.1 + 0.3 * x, 0.1 + 0.3 * x, 1.0),
    'greens': lambda x: (0.1 + 0.3 * x, 0.4 + 0.5 * x, 0.1 + 0.3 * x, 1.0),
}