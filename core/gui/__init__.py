#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Core GUI 模块

提供核心GUI组件和性能优化功能，支持UI性能监控和优化。

作者: FactorWeave-Quant团队
版本: 1.0
"""

from loguru import logger
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class UIPerformanceLevel(Enum):
    """UI性能级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"


@dataclass
class UIPerformanceMetrics:
    """UI性能指标"""
    render_time: float = 0.0
    memory_usage: int = 0
    update_frequency: float = 0.0
    component_count: int = 0
    event_queue_size: int = 0
    last_update: datetime = field(default_factory=datetime.now)


class UIPerformanceMonitor:
    """UI性能监控器"""

    def __init__(self):
        self.metrics = UIPerformanceMetrics()
        self.performance_level = UIPerformanceLevel.MEDIUM
        self.callbacks: List[Callable] = []

    def start_monitoring(self):
        """开始性能监控"""
        logger.info("UI性能监控已启动")

    def stop_monitoring(self):
        """停止性能监控"""
        logger.info("UI性能监控已停止")

    def get_metrics(self) -> UIPerformanceMetrics:
        """获取性能指标"""
        return self.metrics

    def set_performance_level(self, level: UIPerformanceLevel):
        """设置性能级别"""
        self.performance_level = level
        logger.info(f"UI性能级别设置为: {level.value}")

    def add_callback(self, callback: Callable):
        """添加性能回调"""
        self.callbacks.append(callback)

    def remove_callback(self, callback: Callable):
        """移除性能回调"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)


# 全局性能监控器实例
_performance_monitor = None


def get_ui_performance_monitor() -> UIPerformanceMonitor:
    """获取UI性能监控器实例"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = UIPerformanceMonitor()
    return _performance_monitor


def init_ui_performance():
    """初始化UI性能监控"""
    monitor = get_ui_performance_monitor()
    monitor.start_monitoring()
    return monitor


# 导出的公共接口
__all__ = [
    'UIPerformanceLevel',
    'UIPerformanceMetrics',
    'UIPerformanceMonitor',
    'get_ui_performance_monitor',
    'init_ui_performance'
]
