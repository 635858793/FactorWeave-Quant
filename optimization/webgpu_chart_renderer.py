from loguru import logger
"""
WebGPU集成图表渲染器

继承现有的ChartRenderer，添加WebGPU硬件加速支持。
保持与现有系统的完全兼容性，同时提供显著的性能提升。
"""

import threading
import time
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
import os

# 导入现有渲染器
from .chart_renderer import ChartRenderer as BaseChartRenderer
from core.webgpu import get_webgpu_manager, WebGPUConfig, RenderBackend

logger = logger

class WebGPUChartRenderer(BaseChartRenderer):
    """
    WebGPU集成图表渲染器

    继承原有ChartRenderer，添加WebGPU硬件加速支持。
    完全向后兼容，自动降级到原有matplotlib实现。
    """

    # 移除了复杂的监控信号

    def __init__(self, max_workers: int = os.cpu_count(), enable_progressive: bool = True,
                 enable_webgpu: bool = True):
        """
        初始化WebGPU图表渲染器

        Args:
            max_workers: 最大工作线程数
            enable_progressive: 是否启用渐进式渲染
            enable_webgpu: 是否启用WebGPU（用于测试和兼容性）
        """
        # 调用父类初始化
        super().__init__(max_workers, enable_progressive)

        self.enable_webgpu = enable_webgpu
        self._webgpu_manager = None
        self._webgpu_initialized = False
        self._current_backend = "matplotlib"  # 默认后端
        self._webgpu_lock = threading.Lock()

        # 移除复杂的性能统计

        # 初始化WebGPU
        if self.enable_webgpu:
            self._initialize_webgpu()

    def _initialize_webgpu(self):
        """初始化WebGPU管理器"""
        try:
            with self._webgpu_lock:
                logger.info("初始化WebGPU图表渲染器...")

                # 简化的WebGPU配置
                webgpu_config = WebGPUConfig(
                    auto_initialize=True,
                    enable_fallback=True,
                    auto_fallback_on_error=True
                )

                # 获取WebGPU管理器
                self._webgpu_manager = get_webgpu_manager(webgpu_config)

                # 简化的初始化检查
                if self._webgpu_manager._initialized:
                    self._webgpu_initialized = True
                    # 获取实际的后端类型
                    self._current_backend = self._webgpu_manager.current_backend
                    logger.info(f"WebGPU初始化成功，当前后端: {self._current_backend}")
                else:
                    logger.warning("WebGPU初始化失败，使用matplotlib后备")

        except Exception as e:
            logger.error(f"WebGPU初始化异常: {e}")
            self._webgpu_initialized = False

    def _on_webgpu_initialized(self, success: bool):
        """WebGPU初始化回调"""
        self._webgpu_initialized = success
        if success:
            logger.info("WebGPU管理器初始化成功")
        else:
            logger.warning("WebGPU管理器初始化失败")

    def _on_webgpu_fallback(self):
        """WebGPU降级回调"""
        if self._webgpu_manager:
            logger.info(f"WebGPU后端切换到matplotlib")
            self._current_backend = "matplotlib"

    def _on_webgpu_error(self, error_msg: str):
        """WebGPU错误回调"""
        logger.error(f"WebGPU错误: {error_msg}")

    def render_candlesticks(self, ax, data: pd.DataFrame, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True):
        """
        渲染K线图 - WebGPU加速版本

        Args:
            ax: matplotlib轴对象  
            data: K线数据
            style: 样式字典
            x: 可选，X轴数据（可以是datetime数组或数字索引）
            use_datetime_axis: 是否使用datetime X轴（如果数据包含datetime列）
        """
        # 首先检查数据有效性
        if data is None or data.empty:
            logger.warning("K线数据为空，跳过渲染")
            return

        # 尝试WebGPU渲染
        webgpu_success = False
        if self._should_use_webgpu():
            # 记录WebGPU渲染前的状态
            initial_collections = len(ax.collections) if hasattr(ax, 'collections') else 0
            
            webgpu_success = self._try_webgpu_render('candlesticks', ax, data, style, x, use_datetime_axis)
            
            # 检查WebGPU渲染是否真正生效
            if webgpu_success and hasattr(ax, 'collections'):
                final_collections = len(ax.collections)
                if final_collections <= initial_collections:
                    logger.info("WebGPU渲染返回成功但轴上无内容，降级到matplotlib")
                    webgpu_success = False

        # 如果WebGPU渲染失败或未使用，调用父类matplotlib实现
        if not webgpu_success:
            # 修复：传递use_datetime_axis参数给父类
            super().render_candlesticks(ax, data, style, x, use_datetime_axis)

    def render_volume(self, ax, data: pd.DataFrame, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True):
        """
        渲染成交量 - WebGPU加速版本

        Args:
            ax: matplotlib轴对象
            data: 数据
            style: 样式字典  
            x: 可选，X轴数据（可以是datetime数组或数字索引）
            use_datetime_axis: 是否使用datetime X轴（如果数据包含datetime列）
        """
        # 首先检查数据有效性
        if data is None or data.empty:
            logger.warning("成交量数据为空，跳过渲染")
            return

        # 尝试WebGPU渲染
        webgpu_success = False
        if self._should_use_webgpu():
            # 记录WebGPU渲染前的状态
            initial_collections = len(ax.collections) if hasattr(ax, 'collections') else 0
            
            webgpu_success = self._try_webgpu_render('volume', ax, data, style, x, use_datetime_axis)
            
            # 检查WebGPU渲染是否真正生效
            if webgpu_success and hasattr(ax, 'collections'):
                final_collections = len(ax.collections)
                if final_collections <= initial_collections:
                    logger.info("WebGPU渲染返回成功但轴上无内容，降级到matplotlib")
                    webgpu_success = False

        # 如果WebGPU渲染失败或未使用，调用父类matplotlib实现
        if not webgpu_success:
            # 直接使用原有matplotlib实现
            super().render_volume(ax, data, style, x, use_datetime_axis)

    def render_line(self, ax, data: pd.Series, style: Dict[str, Any] = None):
        """
        渲染线图 - WebGPU加速版本

        Args:
            ax: matplotlib轴对象
            data: 数据序列
            style: 样式字典
        """
        # 首先检查数据有效性
        if data is None or data.empty:
            logger.warning("线图数据为空，跳过渲染")
            return

        # 尝试WebGPU渲染
        webgpu_success = False
        if self._should_use_webgpu():
            # 记录WebGPU渲染前的状态
            initial_collections = len(ax.collections) if hasattr(ax, 'collections') else 0
            
            webgpu_success = self._try_webgpu_render('line', ax, data, style)
            
            # 检查WebGPU渲染是否真正生效
            if webgpu_success and hasattr(ax, 'collections'):
                final_collections = len(ax.collections)
                if final_collections <= initial_collections:
                    logger.info("WebGPU渲染返回成功但轴上无内容，降级到matplotlib")
                    webgpu_success = False

        # 如果WebGPU渲染失败或未使用，调用父类matplotlib实现
        if not webgpu_success:
            # 直接使用原有matplotlib实现
            super().render_line(ax, data, style)

    def _should_use_webgpu(self) -> bool:
        """判断是否应该使用WebGPU"""
        return (self.enable_webgpu and
                self._webgpu_initialized and
                self._webgpu_manager and
                self._current_backend != "matplotlib")

    def _try_webgpu_render(self, render_type: str, ax, data, style: Dict[str, Any], x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """
        尝试WebGPU渲染

        Args:
            render_type: 渲染类型 ('candlesticks', 'volume', 'line')
            ax: matplotlib轴对象
            data: 渲染数据
            style: 样式设置
            x: 可选，X轴数据
            use_datetime_axis: 是否使用datetime轴

        Returns:
            是否成功使用WebGPU渲染
        """
        if not self._webgpu_manager:
            return False

        try:
            # 调用WebGPU管理器进行渲染
            if render_type == 'candlesticks':
                success = self._webgpu_manager.render_candlesticks(ax, data, style, x, use_datetime_axis)
            elif render_type == 'volume':
                success = self._webgpu_manager.render_volume(ax, data, style, x, use_datetime_axis)
            elif render_type == 'line':
                success = self._webgpu_manager.render_line(ax, data, style)
            else:
                logger.warning(f"不支持的WebGPU渲染类型: {render_type}")
                return False

            return success

        except Exception as e:
            logger.error(f"WebGPU渲染异常: {e}")
            return False


# WebGPU图表渲染器工厂函数 - 单例模式实现
_instance = None


def get_webgpu_chart_renderer(enable_webgpu: bool = True, 
                             enable_progressive: bool = True,
                             max_workers: int = None) -> WebGPUChartRenderer:
    """
    获取WebGPU图表渲染器实例（单例模式）
    
    这是系统中缺失的关键工厂函数，解决了WebGPU渲染器无法实例化的问题。
    实现单例模式避免重复初始化，支持配置参数。
    
    Args:
        enable_webgpu: 是否启用WebGPU硬件加速
        enable_progressive: 是否启用渐进式渲染
        max_workers: 最大工作线程数，默认为CPU核心数
        
    Returns:
        WebGPUChartRenderer: 配置好的WebGPU渲染器实例
        
    Raises:
        RuntimeError: 当WebGPU渲染器初始化失败时抛出
    """
    global _instance
    
    # 设置默认线程数
    if max_workers is None:
        max_workers = os.cpu_count()
    
    def _create_renderer():
        """创建新的WebGPU渲染器实例"""
        logger.info(f"创建WebGPU图表渲染器实例: enable_webgpu={enable_webgpu}, "
                   f"enable_progressive={enable_progressive}, max_workers={max_workers}")
        
        try:
            renderer = WebGPUChartRenderer(
                max_workers=max_workers,
                enable_progressive=enable_progressive,
                enable_webgpu=enable_webgpu
            )
            
            # 检查初始化状态
            if renderer._webgpu_initialized:
                logger.info("WebGPU渲染器初始化成功")
            else:
                logger.warning("WebGPU渲染器初始化失败，将使用matplotlib后备")
            
            return renderer
            
        except Exception as e:
            logger.error(f"创建WebGPU渲染器实例失败: {e}")
            raise RuntimeError(f"WebGPU渲染器初始化失败: {e}")
    
    # 单例检查和创建
    if _instance is None:
        logger.info("首次创建WebGPU渲染器实例")
        _instance = _create_renderer()
    elif (hasattr(_instance, 'enable_webgpu') and 
          _instance.enable_webgpu != enable_webgpu):
        logger.info(f"WebGPU配置发生变化 (从{_instance.enable_webgpu}到{enable_webgpu})，创建新实例")
        _instance = _create_renderer()
    else:
        logger.debug("复用现有的WebGPU渲染器实例")
    
    return _instance


def reset_webgpu_renderer():
    """
    重置WebGPU渲染器实例
    
    主要用于测试和配置更改后的重置操作。
    """
    global _instance
    if _instance is not None:
        logger.info("重置WebGPU渲染器实例")
        _instance = None
    else:
        logger.debug("WebGPU渲染器实例已经是None，无需重置")


def get_renderer_info():
    """
    获取渲染器状态信息
    
    Returns:
        dict: 包含渲染器配置和状态信息的字典
    """
    global _instance
    
    if _instance is None:
        return {
            "instance_exists": False,
            "message": "WebGPU渲染器实例尚未创建"
        }
    
    return {
        "instance_exists": True,
        "enable_webgpu": getattr(_instance, 'enable_webgpu', None),
        "webgpu_initialized": getattr(_instance, '_webgpu_initialized', False),
        "current_backend": getattr(_instance, '_current_backend', 'unknown'),
        "max_workers": getattr(_instance, 'max_workers', None)
    }
