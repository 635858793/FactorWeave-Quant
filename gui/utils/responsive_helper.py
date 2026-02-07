"""
响应式计算辅助函数模块
提供基于 DPI 的尺寸计算函数，支持 UI 元素等比缩放
"""

import logging
from typing import Optional, Tuple
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt

logger = logging.getLogger(__name__)

class ResponsiveHelper:
    """响应式计算辅助类"""
    
    def __init__(self):
        self._cached_dpr: Optional[float] = None
        self._cache_valid = False
    
    def get_device_pixel_ratio(self) -> float:
        """
        获取设备像素比
        
        Returns:
            设备像素比，默认为 1.0
        """
        if not self._cache_valid or self._cached_dpr is None:
            try:
                app = QApplication.instance()
                if app:
                    self._cached_dpr = app.devicePixelRatio()
                else:
                    self._cached_dpr = 1.0
                self._cache_valid = True
            except Exception as e:
                logger.warning(f"获取设备像素比失败: {e}")
                self._cached_dpr = 1.0
                self._cache_valid = True
        
        return self._cached_dpr
    
    def invalidate_cache(self):
        """使缓存失效"""
        self._cache_valid = False
        self._cached_dpr = None
    
    def calculate_spacing(self, base_value: int) -> int:
        """
        基于 DPI 计算间距
        
        Args:
            base_value: 基础间距值（像素）
        
        Returns:
            调整后的间距值
        """
        dpr = self.get_device_pixel_ratio()
        result = int(base_value * dpr)
        
        if result < 1:
            result = 1
        
        logger.debug(f"间距计算: {base_value} -> {result} (DPR={dpr})")
        return result
    
    def calculate_margin(self, base_value: int) -> int:
        """
        基于 DPI 计算边距
        
        Args:
            base_value: 基础边距值（像素）
        
        Returns:
            调整后的边距值
        """
        return self.calculate_spacing(base_value)
    
    def calculate_margins(self, top: int, right: int, bottom: int, left: int) -> Tuple[int, int, int, int]:
        """
        基于 DPI 计算四个方向的边距
        
        Args:
            top: 上边距
            right: 右边距
            bottom: 下边距
            left: 左边距
        
        Returns:
            调整后的边距元组 (top, right, bottom, left)
        """
        dpr = self.get_device_pixel_ratio()
        return (
            int(top * dpr),
            int(right * dpr),
            int(bottom * dpr),
            int(left * dpr)
        )
    
    def calculate_percentage_height(self, parent_widget: QWidget, percentage: float) -> int:
        """
        计算父窗口高度的百分比
        
        Args:
            parent_widget: 父窗口组件
            percentage: 百分比值（0.0 - 1.0）
        
        Returns:
            计算后的高度值
        """
        if not parent_widget:
            logger.warning("父窗口组件为空，返回默认值 100")
            return 100
        
        if percentage <= 0 or percentage > 1:
            logger.warning(f"百分比值无效: {percentage}，使用默认值 0.5")
            percentage = 0.5
        
        parent_height = parent_widget.height()
        result = int(parent_height * percentage)
        
        if result < 50:
            result = 50
        
        logger.debug(f"百分比高度计算: {parent_height} * {percentage} = {result}")
        return result
    
    def calculate_percentage_width(self, parent_widget: QWidget, percentage: float) -> int:
        """
        计算父窗口宽度的百分比
        
        Args:
            parent_widget: 父窗口组件
            percentage: 百分比值（0.0 - 1.0）
        
        Returns:
            计算后的宽度值
        """
        if not parent_widget:
            logger.warning("父窗口组件为空，返回默认值 200")
            return 200
        
        if percentage <= 0 or percentage > 1:
            logger.warning(f"百分比值无效: {percentage}，使用默认值 0.5")
            percentage = 0.5
        
        parent_width = parent_widget.width()
        result = int(parent_width * percentage)
        
        if result < 100:
            result = 100
        
        logger.debug(f"百分比宽度计算: {parent_width} * {percentage} = {result}")
        return result
    
    def calculate_font_size(self, base_size: int) -> int:
        """
        基于 DPI 计算字体大小
        
        Args:
            base_size: 基础字体大小（像素）
        
        Returns:
            调整后的字体大小
        """
        dpr = self.get_device_pixel_ratio()
        result = int(base_size * dpr)
        
        if result < 8:
            result = 8
        
        logger.debug(f"字体大小计算: {base_size} -> {result} (DPR={dpr})")
        return result
    
    def calculate_icon_size(self, base_size: int) -> int:
        """
        基于 DPI 计算图标大小
        
        Args:
            base_size: 基础图标大小（像素）
        
        Returns:
            调整后的图标大小
        """
        dpr = self.get_device_pixel_ratio()
        result = int(base_size * dpr)
        
        if result < 16:
            result = 16
        
        logger.debug(f"图标大小计算: {base_size} -> {result} (DPR={dpr})")
        return result
    
    def calculate_table_row_height(self, base_height: int = 30, row_count: int = 5) -> int:
        """
        计算表格高度
        
        Args:
            base_height: 基础行高（像素）
            row_count: 行数
        
        Returns:
            计算后的表格高度
        """
        dpr = self.get_device_pixel_ratio()
        base_height_scaled = int(base_height * dpr)
        result = base_height_scaled * row_count
        
        if result < 100:
            result = 100
        
        logger.debug(f"表格高度计算: {base_height} * {row_count} * {dpr} = {result}")
        return result
    
    def calculate_border_radius(self, base_radius: int) -> int:
        """
        基于 DPI 计算边框圆角
        
        Args:
            base_radius: 基础圆角值（像素）
        
        Returns:
            调整后的圆角值
        """
        dpr = self.get_device_pixel_ratio()
        result = int(base_radius * dpr)
        
        if result < 1:
            result = 1
        
        logger.debug(f"边框圆角计算: {base_radius} -> {result} (DPR={dpr})")
        return result
    
    def get_em_value(self, base_font_size: int = 16) -> int:
        """
        获取 em 单位的像素值
        
        Args:
            base_font_size: 基础字体大小（像素），默认为 16
        
        Returns:
            em 单位的像素值
        """
        return self.calculate_font_size(base_font_size)


_global_helper: Optional[ResponsiveHelper] = None

def get_responsive_helper() -> ResponsiveHelper:
    """
    获取全局响应式辅助实例
    
    Returns:
        ResponsiveHelper 实例
    """
    global _global_helper
    if _global_helper is None:
        _global_helper = ResponsiveHelper()
    return _global_helper


def calculate_spacing(base_value: int) -> int:
    """
    便捷函数：基于 DPI 计算间距
    
    Args:
        base_value: 基础间距值（像素）
    
    Returns:
        调整后的间距值
    """
    return get_responsive_helper().calculate_spacing(base_value)


def calculate_margins(top: int, right: int, bottom: int, left: int) -> Tuple[int, int, int, int]:
    """
    便捷函数：基于 DPI 计算四个方向的边距
    
    Args:
        top: 上边距
        right: 右边距
        bottom: 下边距
        left: 左边距
    
    Returns:
        调整后的边距元组 (top, right, bottom, left)
    """
    return get_responsive_helper().calculate_margins(top, right, bottom, left)


def calculate_percentage_height(parent_widget: QWidget, percentage: float) -> int:
    """
    便捷函数：计算父窗口高度的百分比
    
    Args:
        parent_widget: 父窗口组件
        percentage: 百分比值（0.0 - 1.0）
    
    Returns:
        计算后的高度值
    """
    return get_responsive_helper().calculate_percentage_height(parent_widget, percentage)


def calculate_font_size(base_size: int) -> int:
    """
    便捷函数：基于 DPI 计算字体大小
    
    Args:
        base_size: 基础字体大小（像素）
    
    Returns:
        调整后的字体大小
    """
    return get_responsive_helper().calculate_font_size(base_size)


def get_device_pixel_ratio() -> float:
    """
    便捷函数：获取设备像素比
    
    Returns:
        设备像素比，默认为 1.0
    """
    return get_responsive_helper().get_device_pixel_ratio()
