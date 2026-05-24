#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Core GUI Performance Widgets 模块

提供性能相关的GUI组件和性能监控widget。

作者: FactorWeave-Quant团队
版本: 1.0
"""

from loguru import logger
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class PerformanceWidgetConfig:
    """性能Widget配置"""
    update_interval: int = 1000  # 更新间隔(毫秒)
    max_data_points: int = 100   # 最大数据点数
    enable_animations: bool = True
    auto_scale: bool = True

class PerformanceWidgetManager:
    """性能Widget管理器"""

    def __init__(self):
        self.config = PerformanceWidgetConfig()
        self.widgets: Dict[str, Any] = {}
        self.is_active = True

    def register_widget(self, widget_id: str, widget) -> bool:
        """注册性能widget"""
        try:
            self.widgets[widget_id] = widget
            logger.debug(f"性能widget注册成功: {widget_id}")
            return True
        except Exception as e:
            logger.error(f"注册性能widget失败: {e}")
            return False

    def unregister_widget(self, widget_id: str) -> bool:
        """注销性能widget"""
        try:
            if widget_id in self.widgets:
                del self.widgets[widget_id]
                logger.debug(f"性能widget注销成功: {widget_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"注销性能widget失败: {e}")
            return False

    def get_widget_count(self) -> int:
        """获取widget数量"""
        return len(self.widgets)

    def update_all_widgets(self, data: Dict[str, Any]):
        """更新所有widgets"""
        for widget_id, widget in self.widgets.items():
            try:
                if hasattr(widget, 'update_data'):
                    widget.update_data(data)
            except Exception as e:
                logger.error(f"更新widget失败 {widget_id}: {e}")

# 全局管理器实例
_widget_manager = None

def get_performance_widget_manager() -> PerformanceWidgetManager:
    """获取性能Widget管理器实例"""
    global _widget_manager
    if _widget_manager is None:
        _widget_manager = PerformanceWidgetManager()
    return _widget_manager

# 导出的公共接口
__all__ = [
    'PerformanceWidgetConfig',
    'PerformanceWidgetManager',
    'get_performance_widget_manager'
]
