#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
现代化性能监控窗口
重构后的入口文件，提供向后兼容性
"""

from loguru import logger
from gui.widgets.performance.unified_performance_widget import ModernUnifiedPerformanceWidget


def show_modern_performance_monitor_with_import_monitoring():
    """显示包含数据导入监控的现代性能监控器"""
    try:
        # 创建主窗口
        main_window = ModernUnifiedPerformanceWidget()

        # 添加数据导入监控选项卡 (暂时注释，类不存在)
        # import_monitor = DataImportMonitoringWidget()
        # main_window.tab_widget.addTab(import_monitor, "数据导入监控")

        # 设置窗口属性
        main_window.setWindowTitle("FactorWeave-Quant 智能性能监控中心 (含数据导入)")
        main_window.resize(1400, 800)
        main_window.show()

        return main_window

    except Exception as e:
        logger.error(f"创建性能监控窗口失败: {e}")
        return None


def show_modern_performance_monitor(parent=None):
    """显示现代化性能监控窗口"""
    try:
        health_checker = None
        event_bus = None

        try:
            from core.containers import get_service_container
            from core.events import get_event_bus
            from analysis.system_health_checker import SystemHealthChecker
            from core.metrics.aggregation_service import MetricsAggregationService
            from core.metrics.repository import MetricsRepository

            service_container = get_service_container()
            event_bus = get_event_bus()

            # 获取依赖服务，使用 try_resolve 避免服务未注册时抛出异常
            aggregation_service = service_container.try_resolve(MetricsAggregationService)
            metrics_repository = service_container.try_resolve(MetricsRepository)

            if aggregation_service and metrics_repository:
                # 创建健康检查器
                health_checker = SystemHealthChecker(
                    aggregation_service=aggregation_service,
                    repository=metrics_repository
                )
                logger.info("健康检查器创建成功")
            else:
                logger.warning("无法获取依赖服务，健康检查器将为空")

        except Exception as e:
            logger.warning(f"创建健康检查器失败: {e}")

        # 创建性能监控窗口
        # 注意：parent 参数应该是 QWidget 或其子类，如果传入的是 QApplication，则设为 None
        if parent is not None and not hasattr(parent, 'setWindowTitle'):
            parent = None
            
        widget = ModernUnifiedPerformanceWidget(
            parent=parent,
            health_checker=health_checker,
            event_bus=event_bus
        )
        widget.show()
        return widget

    except Exception as e:
        logger.error(f"创建性能监控窗口失败: {e}")
        return None


# 向后兼容性导出
__all__ = [
    'show_modern_performance_monitor',
    'show_modern_performance_monitor_with_import_monitoring',
    'ModernUnifiedPerformanceWidget'
]
