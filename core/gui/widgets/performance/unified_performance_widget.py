#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一性能Widget

提供统一的性能监控和显示widget接口。

作者: FactorWeave-Quant团队
版本: 1.0
"""

from loguru import logger
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

@dataclass
class PerformanceData:
    """性能数据"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_io: float = 0.0
    response_time: float = 0.0

class UnifiedPerformanceWidget:
    """统一性能Widget"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.data = PerformanceData()
        self.is_active = True
        self.callbacks: List = []

    def update_data(self, data: Dict[str, Any]):
        """更新性能数据"""
        try:
            self.data.cpu_usage = data.get('cpu_usage', 0.0)
            self.data.memory_usage = data.get('memory_usage', 0.0)
            self.data.disk_usage = data.get('disk_usage', 0.0)
            self.data.network_io = data.get('network_io', 0.0)
            self.data.response_time = data.get('response_time', 0.0)

            # 通知回调
            for callback in self.callbacks:
                try:
                    callback(self.data)
                except Exception as e:
                    logger.error(f"性能widget回调失败: {e}")

        except Exception as e:
            logger.error(f"更新性能数据失败: {e}")

    def add_callback(self, callback):
        """添加回调函数"""
        self.callbacks.append(callback)

    def remove_callback(self, callback):
        """移除回调函数"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def get_current_data(self) -> PerformanceData:
        """获取当前性能数据"""
        return self.data

    def reset(self):
        """重置性能数据"""
        self.data = PerformanceData()

# 全局实例
_unified_widget = None

def get_unified_performance_widget() -> UnifiedPerformanceWidget:
    """获取统一性能Widget实例"""
    global _unified_widget
    if _unified_widget is None:
        _unified_widget = UnifiedPerformanceWidget()
    return _unified_widget

class ModernUnifiedPerformanceWidget(UnifiedPerformanceWidget):
    """现代化统一性能Widget"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.theme = "modern"
        self.animations_enabled = True

    def set_theme(self, theme: str):
        """设置主题"""
        self.theme = theme

    def enable_animations(self, enabled: bool = True):
        """启用/禁用动画"""
        self.animations_enabled = enabled

# 导出的公共接口
__all__ = [
    'PerformanceData',
    'UnifiedPerformanceWidget',
    'ModernUnifiedPerformanceWidget',
    'get_unified_performance_widget'
]
