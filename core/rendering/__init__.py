"""
核心渲染模块

提供统一的图表渲染接口和实现，支持多种渲染后端。
"""

from .interfaces import IChartRenderer
from .base_renderer import BaseChartRenderer

__all__ = [
    'IChartRenderer',
    'BaseChartRenderer',
]

__version__ = '1.0.0'
__author__ = 'Hikyuu UI Team'
