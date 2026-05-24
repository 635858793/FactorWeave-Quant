#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图表渲染管理器
"""

from loguru import logger

# 图表渲染器集成代码
from gui.widgets.chart_renderer import ChartRenderer
from optimization.chart_renderer import ChartRenderer as OptimizedChartRenderer, RenderPriority
from optimization.webgpu_chart_renderer import WebGPUChartRenderer


class ChartRenderingManager:
    """图表渲染管理器"""

    def __init__(self):
        self.renderers = {}
        self._initialize_renderers()

    def _initialize_renderers(self):
        """初始化图表渲染器"""
        try:
            # 尝试使用优化的渲染器
            self.renderers['optimized'] = OptimizedChartRenderer()
            logger.info("优化图表渲染器初始化成功")
        except Exception as e:
            logger.warning(f"优化图表渲染器初始化失败: {e}")

        try:
            # 基础渲染器作为后备
            self.renderers['basic'] = ChartRenderer()
            logger.info("基础图表渲染器初始化成功")
        except Exception as e:
            logger.error(f"基础图表渲染器初始化失败: {e}")

        try:
            # WebGPU渲染器（如果可用）
            self.renderers['webgpu'] = WebGPUChartRenderer()
            logger.info("WebGPU图表渲染器初始化成功")
        except Exception as e:
            logger.info(f"WebGPU图表渲染器不可用: {e}")

    def get_best_renderer(self, data_size: int = 1000):
        """获取最佳渲染器"""
        # 根据数据大小选择最佳渲染器
        if data_size > 10000 and 'webgpu' in self.renderers:
            return self.renderers['webgpu']
        elif data_size > 1000 and 'optimized' in self.renderers:
            return self.renderers['optimized']
        elif 'basic' in self.renderers:
            return self.renderers['basic']
        else:
            logger.error("没有可用的图表渲染器")
            return None

    def render_candlesticks(self, ax, data, style=None, renderer_type='auto'):
        """渲染蜡烛图"""
        if renderer_type == 'auto':
            renderer = self.get_best_renderer(len(data))
        else:
            renderer = self.renderers.get(renderer_type)

        if renderer and hasattr(renderer, 'render_candlesticks'):
            return renderer.render_candlesticks(ax, data, style)
        else:
            logger.warning("渲染器不支持蜡烛图渲染，使用简单实现")
            return self._simple_candlestick_fallback(ax, data, style)

    def render_ohlc(self, ax, data, style=None, renderer_type='auto'):
        """渲染OHLC图"""
        if renderer_type == 'auto':
            renderer = self.get_best_renderer(len(data))
        else:
            renderer = self.renderers.get(renderer_type)

        if renderer and hasattr(renderer, 'render_ohlc'):
            return renderer.render_ohlc(ax, data, style)
        else:
            logger.warning("渲染器不支持OHLC渲染，使用简单实现")
            return self._simple_ohlc_fallback(ax, data, style)

    def _simple_candlestick_fallback(self, ax, data, style):
        """简单蜡烛图后备实现"""
        try:
            import numpy as np
            if data is None or len(data) == 0:
                logger.warning("后备渲染: 无有效K线数据")
                return False
            x = np.arange(len(data))
            colors = np.where(data.close >= data.open, 'red', 'green')
            ax.bar(x, data.close - data.open, bottom=data.open,
                   color=colors, width=0.8, align='center')
            ax.plot(x, data.high, color='black', linewidth=0.5)
            ax.plot(x, data.low, color='black', linewidth=0.5)
            logger.info("使用简单蜡烛图后备实现完成")
            return True
        except Exception as e:
            logger.error(f"后备蜡烛图渲染失败: {e}")
            return False

    def _simple_ohlc_fallback(self, ax, data, style):
        """简单OHLC图后备实现"""
        try:
            import numpy as np
            if data is None or len(data) == 0:
                logger.warning("后备渲染: 无有效OHLC数据")
                return False
            x = np.arange(len(data))
            colors = np.where(data.close >= data.open, 'red', 'green')
            ax.bar(x, data.close - data.open, bottom=data.open,
                   color=colors, width=0.6, align='center')
            logger.info("使用简单OHLC图后备实现完成")
            return True
        except Exception as e:
            logger.error(f"后备OHLC图渲染失败: {e}")
            return False


# 全局图表渲染管理器实例
_chart_rendering_manager = None


def get_chart_rendering_manager():
    """获取全局图表渲染管理器"""
    global _chart_rendering_manager
    if _chart_rendering_manager is None:
        _chart_rendering_manager = ChartRenderingManager()
    return _chart_rendering_manager
