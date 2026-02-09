#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced UI Components Package
专业量化平台UI增强组件包

本包提供了一系列专业的UI增强组件，用于提升FactorWeave-Quant系统的用户体验和功能完整性。
这些组件基于现有的ChartWidget和AnalysisWidget设计风格，保持了系统的一致性。

主要组件：
- Level2DataPanel: Level-2行情数据面板
- OrderBookWidget: 订单簿深度分析组件
- FundamentalAnalysisTab: 基本面分析标签页
- DataQualityMonitorTab: 数据质量监控标签页
- SmartRecommendationPanel: 智能推荐面板

设计原则：
1. 复用现有UI组件和设计风格
2. 集成现有事件总线和数据管理系统
3. 提供专业级的数据展示和交互功能
4. 支持实时数据更新和用户交互
5. 遵循现有的错误处理和日志记录规范
"""

from .level2_data_panel import Level2DataPanel
from .order_book_widget import OrderBookWidget
from .fundamental_analysis_tab import FundamentalAnalysisTab
from .smart_recommendation_panel import SmartRecommendationPanel, RecommendationCard

__version__ = "1.0.0"
__author__ = "FactorWeave-Quant Team"

# 导出所有主要组件
__all__ = [
    # 主要UI组件
    "Level2DataPanel",
    "OrderBookWidget",
    "FundamentalAnalysisTab",
    "SmartRecommendationPanel",

    # 辅助组件
    "RecommendationCard",

    # 工具函数
    "create_enhanced_chart_widget",
    "create_enhanced_analysis_widget",
    "integrate_enhanced_components"
]


def create_enhanced_chart_widget(parent=None, **kwargs):
    """
    创建增强的图表组件

    在现有ChartWidget基础上集成Level-2数据面板和订单簿组件

    Args:
        parent: 父组件
        **kwargs: 其他参数

    Returns:
        增强的图表组件实例
    """
    from PyQt5.QtWidgets import QWidget, QHBoxLayout, QSplitter
    from PyQt5.QtCore import Qt

    # 创建容器组件
    enhanced_widget = QWidget(parent)
    layout = QHBoxLayout(enhanced_widget)

    # 创建分割器
    splitter = QSplitter(Qt.Horizontal)

    # 主图表区域（这里应该是现有的ChartWidget）
    # 由于我们不修改现有的ChartWidget，这里作为占位
    main_chart_placeholder = QWidget()
    main_chart_placeholder.setMinimumWidth(600)
    splitter.addWidget(main_chart_placeholder)

    # Level-2数据面板
    level2_panel = Level2DataPanel(
        event_bus=kwargs.get('event_bus'),
        realtime_manager=kwargs.get('realtime_manager')
    )
    splitter.addWidget(level2_panel)

    # 设置分割比例
    splitter.setSizes([600, 300])
    layout.addWidget(splitter)

    # 存储子组件引用
    enhanced_widget.level2_panel = level2_panel
    enhanced_widget.main_chart = main_chart_placeholder

    return enhanced_widget


def create_enhanced_analysis_widget(parent=None, **kwargs):
    """
    创建增强的分析组件

    在现有AnalysisWidget基础上集成基本面分析和智能推荐功能

    Args:
        parent: 父组件
        **kwargs: 其他参数

    Returns:
        增强的分析组件实例
    """
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget

    # 创建容器组件
    enhanced_widget = QWidget(parent)
    layout = QVBoxLayout(enhanced_widget)

    # 创建标签页组件
    tab_widget = QTabWidget()

    # 基本面分析标签页
    fundamental_tab = FundamentalAnalysisTab(
        fundamental_manager=kwargs.get('fundamental_manager'),
        announcement_parser=kwargs.get('announcement_parser')
    )
    tab_widget.addTab(fundamental_tab, "基本面分析")

    # 智能推荐标签页
    recommendation_panel = SmartRecommendationPanel(
        recommendation_engine=kwargs.get('recommendation_engine'),
        model_trainer=kwargs.get('model_trainer')
    )
    tab_widget.addTab(recommendation_panel, "智能推荐")

    layout.addWidget(tab_widget)

    # 存储子组件引用
    enhanced_widget.fundamental_tab = fundamental_tab
    enhanced_widget.recommendation_panel = recommendation_panel

    return enhanced_widget


def integrate_enhanced_components(main_window, **managers):
    """
    将增强组件集成到主窗口

    这个函数帮助将新的UI组件集成到现有的主窗口中，
    而不需要大幅修改现有代码结构。

    Args:
        main_window: 主窗口实例
        **managers: 各种管理器实例
            - event_bus: 事件总线
            - realtime_manager: 实时数据管理器
            - fundamental_manager: 基本面数据管理器
            - quality_monitor: 数据质量监控器
            - recommendation_engine: 推荐引擎
            等等

    Returns:
        Dict: 集成的组件字典
    """
    integrated_components = {}

    try:
        # 如果主窗口有chart_widget属性，为其添加Level-2面板
        if hasattr(main_window, 'chart_widget'):
            level2_panel = Level2DataPanel(
                parent=main_window,
                event_bus=managers.get('event_bus'),
                realtime_manager=managers.get('realtime_manager')
            )
            integrated_components['level2_panel'] = level2_panel

        # 如果主窗口有analysis_widget属性，为其添加基本面分析
        if hasattr(main_window, 'analysis_widget'):
            fundamental_tab = FundamentalAnalysisTab(
                parent=main_window,
                fundamental_manager=managers.get('fundamental_manager'),
                announcement_parser=managers.get('announcement_parser')
            )
            integrated_components['fundamental_tab'] = fundamental_tab

        # 添加智能推荐面板
        recommendation_panel = SmartRecommendationPanel(
            parent=main_window,
            recommendation_engine=managers.get('recommendation_engine'),
            model_trainer=managers.get('model_trainer')
        )
        integrated_components['recommendation_panel'] = recommendation_panel

        # 添加订单簿组件
        order_book_widget = OrderBookWidget(
            parent=main_window,
            event_bus=managers.get('event_bus')
        )
        integrated_components['order_book_widget'] = order_book_widget

        from loguru import logger
        logger.info(f"成功集成 {len(integrated_components)} 个增强UI组件")

    except Exception as e:
        from loguru import logger
        logger.error(f"集成增强UI组件失败: {e}")

    return integrated_components


def get_component_info():
    """
    获取组件信息

    Returns:
        Dict: 组件信息字典
    """
    return {
        "package_name": "enhanced_ui",
        "version": __version__,
        "author": __author__,
        "components": {
            "Level2DataPanel": {
                "description": "Level-2行情数据实时显示面板",
                "features": ["实时Level-2数据", "Tick数据流", "订单簿深度", "统计分析"],
                "dependencies": ["EnhancedRealtimeDataManager", "EventBus"]
            },
            "OrderBookWidget": {
                "description": "订单簿深度分析组件",
                "features": ["订单簿可视化", "深度分析", "价格影响计算", "流动性评估"],
                "dependencies": ["EventBus"]
            },
            "FundamentalAnalysisTab": {
                "description": "基本面分析标签页",
                "features": ["财务报表分析", "公司公告解析", "分析师评级", "综合评估"],
                "dependencies": ["FundamentalDataManager", "AnnouncementParser"]
            },
            "DataQualityMonitorTab": {
                "description": "数据质量监控标签页",
                "features": ["实时质量监控", "异常检测", "质量报告", "配置管理"],
                "dependencies": ["EnhancedDataQualityMonitor", "QualityReportGenerator"]
            },
            "SmartRecommendationPanel": {
                "description": "智能推荐面板",
                "features": ["个性化推荐", "用户画像", "行为分析", "反馈管理"],
                "dependencies": ["SmartRecommendationEngine", "RecommendationModelTrainer"]
            }
        },
        "integration_notes": [
            "所有组件都基于现有UI设计风格",
            "完全兼容现有事件总线系统",
            "支持异步数据更新和实时交互",
            "遵循现有错误处理和日志记录规范",
            "可以独立使用或集成到现有组件中"
        ]
    }

# 版本兼容性检查


def check_compatibility():
    """
    检查组件兼容性

    Returns:
        bool: 是否兼容
    """
    try:
        # 检查必要的依赖
        from PyQt5.QtWidgets import QWidget
        from PyQt5.QtCore import pyqtSignal
        from loguru import logger
        import matplotlib.pyplot as plt
        import pandas as pd
        import numpy as np

        return True

    except ImportError as e:
        from loguru import logger
        logger.error(f"依赖检查失败: {e}")
        return False


# 初始化时进行兼容性检查
if not check_compatibility():
    from loguru import logger
    logger.warning("Enhanced UI组件包存在依赖问题，部分功能可能不可用")
