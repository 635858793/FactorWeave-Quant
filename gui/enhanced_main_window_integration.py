#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Main Window Integration
增强主窗口集成模块

本模块提供了将增强UI组件集成到现有主窗口的功能，
确保新功能能够无缝融入现有系统，避免重复建设和功能缺失。

主要功能：
1. 将Level-2数据面板集成到图表区域
2. 将基本面分析标签页添加到分析区域
3. 添加数据质量监控功能
4. 集成智能推荐系统
5. 提供订单簿深度分析

设计原则：
- 最小化对现有代码的修改
- 保持现有UI风格和交互逻辑
- 支持渐进式功能启用
- 提供完整的错误处理和回退机制
"""

from typing import Dict, Any, Optional, List
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QSplitter, QDockWidget, QMainWindow, QMenuBar,
                             QMenu, QAction, QMessageBox, QProgressBar, QLabel)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt5.QtGui import QIcon
from loguru import logger

# 导入增强UI组件
from gui.widgets.enhanced_ui import (
    Level2DataPanel, OrderBookWidget, FundamentalAnalysisTab,
    SmartRecommendationPanel,
    integrate_enhanced_components, get_component_info
)

# 导入核心服务（假设这些已经存在）
try:
    from core.services.enhanced_realtime_data_manager import EnhancedRealtimeDataManager
    from core.services.fundamental_data_manager import FundamentalDataManager
    from core.services.enhanced_data_quality_monitor import EnhancedDataQualityMonitor
    from core.services.smart_recommendation_engine import SmartRecommendationEngine
    from core.events.event_bus import EventBus
except ImportError as e:
    logger.warning(f"部分核心服务导入失败: {e}")


class EnhancedMainWindowIntegrator:
    """
    增强主窗口集成器

    负责将新的UI增强组件集成到现有主窗口中，
    提供渐进式的功能启用和完整的错误处理。
    """

    def __init__(self, main_window: QMainWindow):
        """
        初始化集成器

        Args:
            main_window: 现有的主窗口实例
        """
        self.main_window = main_window
        self.enhanced_components: Dict[str, QWidget] = {}
        self.dock_widgets: Dict[str, QDockWidget] = {}
        self.integration_status: Dict[str, bool] = {}
        self.managers: Dict[str, Any] = {}

        logger.info("EnhancedMainWindowIntegrator 初始化完成")

    def set_managers(self, **managers):
        """
        设置各种管理器实例

        Args:
            **managers: 管理器实例字典
                - event_bus: 事件总线
                - realtime_manager: 实时数据管理器
                - fundamental_manager: 基本面数据管理器
                - quality_monitor: 数据质量监控器
                - recommendation_engine: 推荐引擎
                - announcement_parser: 公告解析器
                - report_generator: 报告生成器
                - model_trainer: 模型训练器
        """
        self.managers.update(managers)
        logger.info(f"已设置 {len(managers)} 个管理器实例")

    def integrate_all_components(self) -> Dict[str, bool]:
        """
        集成所有增强组件

        Returns:
            Dict[str, bool]: 各组件的集成状态
        """
        logger.info("开始集成所有增强UI组件...")

        integration_methods = [
            ("level2_panel", self._integrate_level2_panel),
            ("order_book", self._integrate_order_book_widget),
            ("fundamental_analysis", self._integrate_fundamental_analysis),
            ("smart_recommendation", self._integrate_smart_recommendation),
            ("enhanced_menu", self._integrate_enhanced_menu)
        ]

        for component_name, integration_method in integration_methods:
            try:
                success = integration_method()
                self.integration_status[component_name] = success
                if success:
                    logger.info(f"{component_name} 集成成功")
                else:
                    logger.warning(f" {component_name} 集成失败")
            except Exception as e:
                logger.error(f"[ERROR] {component_name} 集成异常: {e}")
                self.integration_status[component_name] = False

        successful_count = sum(self.integration_status.values())
        total_count = len(self.integration_status)
        logger.info(f"UI增强组件集成完成: {successful_count}/{total_count} 成功")

        return self.integration_status

    def _integrate_level2_panel(self) -> bool:
        """集成Level-2数据面板"""
        try:
            if not self.managers.get('event_bus') or not self.managers.get('realtime_manager'):
                logger.warning("Level-2面板集成跳过: 缺少必要的管理器")
                return False

            # 创建Level-2数据面板
            level2_panel = Level2DataPanel(
                parent=self.main_window,
                event_bus=self.managers['event_bus'],
                realtime_manager=self.managers['realtime_manager']
            )

            # 创建停靠窗口
            dock_widget = QDockWidget("Level-2 行情", self.main_window)
            dock_widget.setWidget(level2_panel)
            dock_widget.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)

            # 添加到主窗口
            self.main_window.addDockWidget(Qt.RightDockWidgetArea, dock_widget)

            # 存储引用
            self.enhanced_components['level2_panel'] = level2_panel
            self.dock_widgets['level2_panel'] = dock_widget

            return True

        except Exception as e:
            logger.error(f"Level-2面板集成失败: {e}")
            return False

    def _integrate_order_book_widget(self) -> bool:
        """集成订单簿组件"""
        try:
            if not self.managers.get('event_bus'):
                logger.warning("订单簿组件集成跳过: 缺少事件总线")
                return False

            # 创建订单簿组件
            order_book_widget = OrderBookWidget(
                parent=self.main_window,
                event_bus=self.managers['event_bus']
            )

            # 创建停靠窗口
            dock_widget = QDockWidget("订单簿深度", self.main_window)
            dock_widget.setWidget(order_book_widget)
            dock_widget.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)

            # 添加到主窗口
            self.main_window.addDockWidget(Qt.RightDockWidgetArea, dock_widget)

            # 存储引用
            self.enhanced_components['order_book_widget'] = order_book_widget
            self.dock_widgets['order_book_widget'] = dock_widget

            return True

        except Exception as e:
            logger.error(f"订单簿组件集成失败: {e}")
            return False

    def _integrate_fundamental_analysis(self) -> bool:
        """集成基本面分析标签页"""
        try:
            if not self.managers.get('fundamental_manager'):
                logger.warning("基本面分析集成跳过: 缺少基本面数据管理器")
                return False

            # 创建基本面分析标签页
            fundamental_tab = FundamentalAnalysisTab(
                parent=self.main_window,
                fundamental_manager=self.managers['fundamental_manager'],
                announcement_parser=self.managers.get('announcement_parser')
            )

            # 尝试添加到现有的分析组件中
            if hasattr(self.main_window, 'analysis_widget') and hasattr(self.main_window.analysis_widget, 'tab_widget'):
                self.main_window.analysis_widget.tab_widget.addTab(fundamental_tab, "基本面")
                logger.info("基本面分析标签页已添加到现有分析组件")
            else:
                # 如果没有现有分析组件，创建停靠窗口
                dock_widget = QDockWidget("基本面分析", self.main_window)
                dock_widget.setWidget(fundamental_tab)
                dock_widget.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
                self.main_window.addDockWidget(Qt.BottomDockWidgetArea, dock_widget)
                self.dock_widgets['fundamental_analysis'] = dock_widget
                logger.info("基本面分析已作为独立停靠窗口添加")

            # 存储引用
            self.enhanced_components['fundamental_tab'] = fundamental_tab

            return True

        except Exception as e:
            logger.error(f"基本面分析集成失败: {e}")
            return False

    def _integrate_smart_recommendation(self) -> bool:
        """集成智能推荐面板"""
        try:
            if not self.managers.get('recommendation_engine'):
                logger.warning("智能推荐集成跳过: 缺少推荐引擎")
                return False

            # 创建智能推荐面板
            recommendation_panel = SmartRecommendationPanel(
                parent=self.main_window,
                recommendation_engine=self.managers['recommendation_engine'],
                model_trainer=self.managers.get('model_trainer')
            )

            # 创建停靠窗口
            dock_widget = QDockWidget("智能推荐", self.main_window)
            dock_widget.setWidget(recommendation_panel)
            dock_widget.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)

            # 添加到主窗口
            self.main_window.addDockWidget(Qt.RightDockWidgetArea, dock_widget)

            # 存储引用
            self.enhanced_components['recommendation_panel'] = recommendation_panel
            self.dock_widgets['smart_recommendation'] = dock_widget

            return True

        except Exception as e:
            logger.error(f"智能推荐集成失败: {e}")
            return False

    def _integrate_enhanced_menu(self) -> bool:
        """集成增强菜单"""
        try:
            # 获取或创建菜单栏
            menubar = self.main_window.menuBar()

            # 创建"增强功能"菜单
            enhanced_menu = menubar.addMenu("增强功能(&E)")

            # Level-2数据菜单项
            if 'level2_panel' in self.dock_widgets:
                level2_action = enhanced_menu.addAction("Level-2 行情")
                level2_action.setCheckable(True)
                level2_action.setChecked(True)
                level2_action.triggered.connect(
                    lambda checked: self.dock_widgets['level2_panel'].setVisible(checked)
                )

            # 订单簿菜单项
            if 'order_book_widget' in self.dock_widgets:
                orderbook_action = enhanced_menu.addAction("订单簿深度")
                orderbook_action.setCheckable(True)
                orderbook_action.setChecked(True)
                orderbook_action.triggered.connect(
                    lambda checked: self.dock_widgets['order_book_widget'].setVisible(checked)
                )

            enhanced_menu.addSeparator()

            # 智能推荐菜单项
            if 'smart_recommendation' in self.dock_widgets:
                recommendation_action = enhanced_menu.addAction("智能推荐")
                recommendation_action.setCheckable(True)
                recommendation_action.setChecked(True)
                recommendation_action.triggered.connect(
                    lambda checked: self.dock_widgets['smart_recommendation'].setVisible(checked)
                )

            enhanced_menu.addSeparator()

            # 组件信息菜单项
            info_action = enhanced_menu.addAction("组件信息")
            info_action.triggered.connect(self._show_component_info)

            return True

        except Exception as e:
            logger.error(f"增强菜单集成失败: {e}")
            return False

    def _show_component_info(self):
        """显示组件信息对话框"""
        try:
            info = get_component_info()

            msg = QMessageBox(self.main_window)
            msg.setWindowTitle("增强UI组件信息")
            msg.setIcon(QMessageBox.Information)

            info_text = f"""
<h3>Enhanced UI Components v{info['version']}</h3>
<p><b>作者:</b> {info['author']}</p>
<p><b>集成状态:</b></p>
<ul>
"""

            for component, status in self.integration_status.items():
                status_icon = "[SUCCESS]" if status else "[ERROR]"
                info_text += f"<li>{status_icon} {component}</li>"

            info_text += """
</ul>
<p><b>主要功能:</b></p>
<ul>
<li>Level-2实时行情数据</li>
<li>订单簿深度分析</li>
<li>基本面数据分析</li>
<li>数据质量监控</li>
<li>智能推荐系统</li>
</ul>
"""

            msg.setText(info_text)
            msg.exec_()

        except Exception as e:
            logger.error(f"显示组件信息失败: {e}")

    def get_component(self, component_name: str) -> Optional[QWidget]:
        """
        获取指定的增强组件

        Args:
            component_name: 组件名称

        Returns:
            组件实例或None
        """
        return self.enhanced_components.get(component_name)

    def toggle_component_visibility(self, component_name: str, visible: bool):
        """
        切换组件可见性

        Args:
            component_name: 组件名称
            visible: 是否可见
        """
        if component_name in self.dock_widgets:
            self.dock_widgets[component_name].setVisible(visible)
        elif component_name in self.enhanced_components:
            self.enhanced_components[component_name].setVisible(visible)

    def get_integration_status(self) -> Dict[str, bool]:
        """
        获取集成状态

        Returns:
            集成状态字典
        """
        return self.integration_status.copy()


def integrate_enhanced_ui_to_main_window(main_window: QMainWindow, **managers) -> EnhancedMainWindowIntegrator:
    """
    便捷函数：将增强UI组件集成到主窗口

    Args:
        main_window: 主窗口实例
        **managers: 各种管理器实例

    Returns:
        集成器实例
    """
    integrator = EnhancedMainWindowIntegrator(main_window)
    integrator.set_managers(**managers)
    integrator.integrate_all_components()

    return integrator

# 示例使用代码


def example_integration():
    """
    示例：如何在现有主窗口中集成增强UI组件

    这个函数展示了如何在现有的FactorWeave-Quant主窗口中
    集成新的增强UI组件。
    """

    # 假设这是现有的主窗口实例
    # main_window = existing_main_window

    # 从服务容器获取管理器实例
    try:
        from core.containers import get_service_container
        from core.services.recommendation_model_trainer import RecommendationModelTrainer
        from core.services.smart_recommendation_engine import SmartRecommendationEngine
        
        container = get_service_container()
        
        managers = {
            # 'event_bus': event_bus_instance,
            # 'realtime_manager': realtime_manager_instance,
            # 'fundamental_manager': fundamental_manager_instance,
            # 'quality_monitor': quality_monitor_instance,
            'recommendation_engine': container.resolve(SmartRecommendationEngine) if container.is_registered(SmartRecommendationEngine) else None,
            # 'announcement_parser': announcement_parser_instance,
            # 'report_generator': report_generator_instance,
            'model_trainer': container.resolve(RecommendationModelTrainer) if container.is_registered(RecommendationModelTrainer) else None
        }
    except Exception as e:
        from loguru import logger
        logger.error(f"从服务容器获取管理器失败: {e}")
        managers = {}

    # 集成增强UI组件
    # integrator = integrate_enhanced_ui_to_main_window(main_window, **managers)

    # 检查集成状态
    # status = integrator.get_integration_status()
    # logger.info(f"UI增强组件集成状态: {status}")

    # 获取特定组件
    # level2_panel = integrator.get_component('level2_panel')
    # if level2_panel:
    #     logger.info("Level-2面板集成成功，可以开始使用")

    logger.info("示例集成代码已准备就绪")


if __name__ == "__main__":
    # 运行示例
    example_integration()
