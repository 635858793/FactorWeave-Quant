#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一性能监控组件（重构版）- 待完善暂时搁置
使用统一管理器替代独立的定时器和线程池，采用事件驱动架构。
"""

import json
from datetime import datetime
from typing import Dict
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QToolBar, QLabel, QTabWidget, QStatusBar,
    QSizePolicy, QFileDialog, QFrame
)
from PyQt5.QtCore import Qt, QDateTime, pyqtSlot, QTimer
from PyQt5.QtGui import QIcon
from loguru import logger

# 导入统一管理器
try:
    from core.events import get_event_bus
    from core.performance import (
        initialize_performance_managers,
        shutdown_performance_managers,
        get_performance_managers,
        get_data_update_manager,
        UpdateStrategy
    )
    UNIFIED_MANAGERS_AVAILABLE = True
except ImportError:
    UNIFIED_MANAGERS_AVAILABLE = False
    logger.warning("统一管理器不可用，unified_performance_widget将使用传统方式")

from core.performance.unified_monitor import get_performance_monitor
from gui.widgets.performance.tabs.system_monitor_tab_refactored import ModernSystemMonitorTab
from gui.widgets.performance.tabs.strategy_performance_tab import ModernStrategyPerformanceTab
from gui.widgets.performance.tabs.algorithm_optimization_tab import ModernAlgorithmOptimizationTab
from gui.widgets.performance.tabs.risk_control_center_tab import ModernRiskControlCenterTab
from gui.widgets.performance.tabs.trading_execution_monitor_tab import ModernTradingExecutionMonitorTab
from gui.widgets.enhanced_ui.data_quality_monitor_tab import DataQualityMonitorTab
from gui.widgets.performance.tabs.system_health_tab import ModernSystemHealthTab

# 深度优化模块导入
try:
    from core.advanced_optimization.unified_optimization_service import UnifiedOptimizationService
    from core.containers.service_container import ServiceContainer
    DEEP_OPTIMIZATION_AVAILABLE = True
except ImportError:
    DEEP_OPTIMIZATION_AVAILABLE = False
    logger.warning("深度优化模块不可用")


class ModernUnifiedPerformanceWidget(QWidget):
    """现代化统一性能监控组件（重构版）"""

    def __init__(self, event_bus=None, health_checker=None, parent=None):
        super().__init__(parent)

        # 设置窗口标志
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint |
                            Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)

        self.monitor = get_performance_monitor()
        self._event_bus = event_bus or (get_event_bus() if UNIFIED_MANAGERS_AVAILABLE else None)
        self._health_checker = health_checker
        self.current_tab_index = 0

        # 性能优化相关变量
        self._is_dragging = False
        self._update_paused = False
        self._last_mouse_move_time = 0

        # 初始化统一管理器
        self.data_update_manager = None
        self.timer_manager = None
        self.thread_pool_manager = None
        self.resource_monitor = None

        if UNIFIED_MANAGERS_AVAILABLE:
            try:
                # 初始化所有性能管理器
                initialize_performance_managers(event_bus=self._event_bus)
                managers = get_performance_managers()

                self.data_update_manager = managers['data_update_manager']
                self.timer_manager = managers['timer_manager']
                self.thread_pool_manager = managers['thread_pool_manager']
                self.resource_monitor = managers['resource_monitor']

                logger.info("统一性能管理器初始化成功")
            except Exception as e:
                logger.error(f"初始化统一性能管理器失败: {e}")

        # 初始化深度优化服务
        self.optimization_service = None

        # 缓存外部服务实例，避免重复创建
        self._trading_controller_cache = None
        self._data_manager_cache = None

        self.init_ui()

        # 注册各标签页到数据更新管理器
        self._register_tabs_to_data_update_manager()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 设置objectName，用于样式选择器
        self.setObjectName("main_window")

        # 现代化工具栏
        self.toolbar = self._create_modern_toolbar()
        layout.addWidget(self.toolbar)

        # 主要内容标签页
        self.tab_widget = self._create_modern_tabs()
        layout.addWidget(self.tab_widget, 1)

        # 现代化状态栏
        self.status_bar = self._create_modern_status_bar()
        layout.addWidget(self.status_bar)

    def _create_modern_toolbar(self):
        """创建现代化工具栏"""
        toolbar = QToolBar()

        # 添加弹性空间
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        toolbar.setFixedHeight(50)

        # 状态指示器
        self.connection_status = QLabel("实时连接")
        self.connection_status.setStyleSheet("""
            color: #27ae60;
            font-weight: bold;
            font-size: 12px;
            padding: 8px 12px;
            background: rgba(39, 174, 96, 0.1);
            border-radius: 4px;
            margin: 4px;
        """)
        toolbar.addWidget(self.connection_status)

        return toolbar

    def _create_modern_tabs(self):
        """创建现代化标签页"""
        tab_widget = QTabWidget()

        # 添加tab切换监听
        tab_widget.currentChanged.connect(self.on_tab_changed)

        # 1. 系统监控 - 基础设施监控
        self.system_tab = ModernSystemMonitorTab()
        tab_widget.addTab(self.system_tab, "🖥️ 系统监控")

        # 2. 策略性能 - 量化策略核心指标
        self.strategy_tab = ModernStrategyPerformanceTab()
        tab_widget.addTab(self.strategy_tab, "策略性能")

        # 3. 算法优化 - 合并算法性能和自动调优
        self.algorithm_optimization_tab = ModernAlgorithmOptimizationTab()
        tab_widget.addTab(self.algorithm_optimization_tab, "算法优化")

        # 4. 风险控制中心 - 升级版告警配置，专注风险管理
        self.risk_control_tab = ModernRiskControlCenterTab()
        tab_widget.addTab(self.risk_control_tab, "🛡️ 风险控制")

        # 5. 交易执行监控 - 量化交易专用，监控执行质量
        self.execution_monitor_tab = ModernTradingExecutionMonitorTab()
        tab_widget.addTab(self.execution_monitor_tab, "执行监控")

        # 6. 数据质量监控 - 量化交易数据质量保障
        self.data_quality_tab = DataQualityMonitorTab()
        tab_widget.addTab(self.data_quality_tab, "数据质量")

        # 7. 系统健康检查 - 系统诊断和健康状态
        self.health_tab = ModernSystemHealthTab(self._health_checker)
        tab_widget.addTab(self.health_tab, "健康检查")

        # 8. 深度优化控制面板 - 集成已注册的深度优化模块
        if DEEP_OPTIMIZATION_AVAILABLE:
            try:
                from gui.widgets.performance.tabs.deep_optimization_tab import DeepOptimizationTab
                self.deep_optimization_tab = DeepOptimizationTab(
                    self.optimization_service,
                    event_bus=self._event_bus
                )
                tab_widget.addTab(self.deep_optimization_tab, "🚀 深度优化")
                logger.info("深度优化标签页添加成功")
            except ImportError as e:
                logger.warning(f"无法创建深度优化标签页: {e}")

        return tab_widget

    def _create_modern_status_bar(self):
        """创建现代化状态栏"""
        status_bar = QStatusBar()
        status_bar.setStyleSheet("""
            QStatusBar {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #34495e, stop: 1 #2c3e50);
                border-top: 1px solid #1a252f;
                color: #bdc3c7;
                font-size: 10px;
                padding: 4px;
            }
            QStatusBar::item {
                border: none;
            }
        """)

        self.status_message = QLabel("就绪")
        status_bar.addWidget(self.status_message)

        status_bar.addPermanentWidget(QLabel("｜"))

        self.data_update_time = QLabel("数据更新: " +
                                       QDateTime.currentDateTime().toString("hh:mm:ss"))
        status_bar.addPermanentWidget(self.data_update_time)

        return status_bar

    def _register_tabs_to_data_update_manager(self):
        """注册各标签页到数据更新管理器"""
        if not self.data_update_manager:
            logger.warning("数据更新管理器不可用，跳过注册")
            return

        try:
            # 系统监控标签页 - 已在内部注册
            # 策略性能标签页 - 5秒更新
            self.data_update_manager.register_tab(
                tab_name="strategy_performance",
                data_collector=self._collect_strategy_performance_data,
                update_interval=5.0,
                update_strategy=UpdateStrategy.EVENT_DRIVEN,
                enabled=True
            )

            # 算法优化标签页 - 10秒更新
            self.data_update_manager.register_tab(
                tab_name="algorithm_optimization",
                data_collector=self._collect_algorithm_optimization_data,
                update_interval=10.0,
                update_strategy=UpdateStrategy.EVENT_DRIVEN,
                enabled=True
            )

            # 风险控制标签页 - 5秒更新
            self.data_update_manager.register_tab(
                tab_name="risk_control",
                data_collector=self._collect_risk_control_data,
                update_interval=5.0,
                update_strategy=UpdateStrategy.EVENT_DRIVEN,
                enabled=True
            )

            # 交易执行监控标签页 - 2秒更新
            self.data_update_manager.register_tab(
                tab_name="execution_monitor",
                data_collector=self._collect_execution_monitor_data,
                update_interval=2.0,
                update_strategy=UpdateStrategy.EVENT_DRIVEN,
                enabled=True
            )

            # 数据质量监控标签页 - 5秒更新
            self.data_update_manager.register_tab(
                tab_name="data_quality",
                data_collector=self._collect_data_quality_data,
                update_interval=5.0,
                update_strategy=UpdateStrategy.EVENT_DRIVEN,
                enabled=True
            )

            # 连接数据更新信号
            self.data_update_manager.data_updated.connect(self._on_data_updated)
            self.data_update_manager.update_error.connect(self._on_update_error)

            logger.info("所有标签页已注册到数据更新管理器")

        except Exception as e:
            logger.error(f"注册标签页到数据更新管理器失败: {e}")

    def _collect_strategy_performance_data(self) -> Dict[str, Any]:
        """收集策略性能数据"""
        try:
            # 这里应该调用策略性能监控接口
            # 暂时返回空字典
            return {}
        except Exception as e:
            logger.error(f"收集策略性能数据失败: {e}")
            return {}

    def _collect_algorithm_optimization_data(self) -> Dict[str, Any]:
        """收集算法优化数据"""
        try:
            # 这里应该调用算法优化监控接口
            # 暂时返回空字典
            return {}
        except Exception as e:
            logger.error(f"收集算法优化数据失败: {e}")
            return {}

    def _collect_risk_control_data(self) -> Dict[str, Any]:
        """收集风险控制数据"""
        try:
            # 这里应该调用风险控制监控接口
            # 暂时返回空字典
            return {}
        except Exception as e:
            logger.error(f"收集风险控制数据失败: {e}")
            return {}

    def _collect_execution_monitor_data(self) -> Dict[str, Any]:
        """收集交易执行监控数据"""
        try:
            # 这里应该调用交易执行监控接口
            # 暂时返回空字典
            return {}
        except Exception as e:
            logger.error(f"收集交易执行监控数据失败: {e}")
            return {}

    def _collect_data_quality_data(self) -> Dict[str, Any]:
        """收集数据质量监控数据"""
        try:
            # 这里应该调用数据质量监控接口
            # 暂时返回空字典
            return {}
        except Exception as e:
            logger.error(f"收集数据质量监控数据失败: {e}")
            return {}

    def _on_data_updated(self, tab_name: str, data_type: str, data: Dict[str, Any]):
        """数据更新回调"""
        try:
            # 更新状态栏时间
            self.data_update_time.setText("数据更新: " +
                                         QDateTime.currentDateTime().toString("hh:mm:ss"))

            # 根据标签页名称更新对应的数据
            if tab_name == "strategy_performance" and hasattr(self, 'strategy_tab'):
                self.strategy_tab.update_data(data)
            elif tab_name == "algorithm_optimization" and hasattr(self, 'algorithm_optimization_tab'):
                self.algorithm_optimization_tab.update_data(data)
            elif tab_name == "risk_control" and hasattr(self, 'risk_control_tab'):
                self.risk_control_tab.update_data(data)
            elif tab_name == "execution_monitor" and hasattr(self, 'execution_monitor_tab'):
                self.execution_monitor_tab.update_data(data)
            elif tab_name == "data_quality" and hasattr(self, 'data_quality_tab'):
                self.data_quality_tab.update_data(data)

        except Exception as e:
            logger.error(f"处理数据更新失败: {e}")

    def _on_update_error(self, tab_name: str, data_type: str, error: str):
        """更新错误回调"""
        logger.error(f"数据更新失败: {tab_name}, {data_type}, {error}")

    def on_tab_changed(self, index: int):
        """标签页切换回调"""
        self.current_tab_index = index
        logger.debug(f"切换到标签页: {index}")

    def cleanup(self):
        """清理资源"""
        try:
            # 注销所有标签页
            if self.data_update_manager:
                tab_names = [
                    "system_monitor",
                    "strategy_performance",
                    "algorithm_optimization",
                    "risk_control",
                    "execution_monitor",
                    "data_quality"
                ]
                for tab_name in tab_names:
                    try:
                        self.data_update_manager.unregister_tab(tab_name)
                    except Exception as e:
                        logger.debug(f"注销标签页失败: {tab_name}, {e}")

            logger.debug("统一性能监控组件已清理")

        except Exception as e:
            logger.error(f"清理统一性能监控组件失败: {e}")

    def closeEvent(self, event):
        """关闭事件"""
        self.cleanup()
        super().closeEvent(event)
