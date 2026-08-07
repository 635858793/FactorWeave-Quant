"""
主窗口协调器

负责协调主窗口的所有UI面板和业务服务的交互。
这是整个应用的中央协调器，替代原来的TradingGUI类。
"""

from loguru import logger
from typing import Dict, Any, Optional, List, Union
import asyncio
import traceback
import sys
import os
import re
from datetime import datetime
import pandas as pd

from PyQt5.QtWidgets import (
    QFileDialog, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QMenuBar, QMessageBox, QDockWidget, QLabel, QPushButton, QFrame,
    QApplication, QSizePolicy
)
from PyQt5.QtCore import QThread, QTimer, Qt, pyqtSignal, QEvent
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot


class ResponsiveMainWindow(QMainWindow):
    """支持响应式布局的主窗口"""
    
    resize_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        self.resize_requested.emit()

from core.performance.unified_monitor import PerformanceAutoTuner
from core.plugin_manager import PluginManager
from gui.dialogs.converter_dialog import ConverterDialog
from gui.dialogs.data_quality_dialog import DataQualityDialog
from gui.dialogs.data_usage_terms_dialog import DataUsageTermsDialog
from gui.tools.currency_converter import CurrencyConverter

from core.coordinators.base_coordinator import BaseCoordinator
from core.events import (
    EventBus, StockSelectedEvent, AssetSelectedEvent, ChartUpdateEvent, AnalysisCompleteEvent,
    DataUpdateEvent, ErrorEvent, UIUpdateEvent, ThemeChangedEvent, UIDataReadyEvent, AssetDataReadyEvent
)
from core.plugin_types import AssetType
from core.containers import ServiceContainer
from core.services import (
    StockService, ChartService, AnalysisService,
    ConfigService, UnifiedDataManager
)
from optimization.optimization_dashboard import create_optimization_dashboard
from gui.widgets.modern_performance_widget import ModernUnifiedPerformanceWidget

from core.performance import measure_performance
from gui.menu_bar import MainMenuBar
from core.coordinators.panel_coordinator import PanelCoordinator
from core.coordinators.event_coordinator import EventCoordinator
from core.coordinators.dialog_coordinator import DialogCoordinator
from core.coordinators.theme_coordinator import ThemeCoordinator



class MainWindowCoordinator(BaseCoordinator):
    """
    主窗口协调器

    负责：
    1. 管理主窗口的生命周期
    2. 协调各个UI面板的交互
    3. 处理全局事件
    4. 管理服务依赖
    """

    def __init__(self,
                 service_container: ServiceContainer,
                 event_bus: EventBus,
                 parent: Optional[QWidget] = None):
        """
        初始化主窗口协调器

        Args:
            service_container: 服务容器
            event_bus: 事件总线
            parent: 父窗口（可选）
        """
        super().__init__(service_container, event_bus)

        # 创建主窗口 - 使用响应式窗口
        self._main_window = ResponsiveMainWindow(parent)
        self._main_window.setWindowTitle("FactorWeave-Quant  2.0 多资产分析系统")
        self._main_window.setGeometry(100, 100, 1400, 900)
        self._main_window.setMinimumSize(1200, 800)

        # 连接窗口大小改变信号（防抖处理）
        self._resize_debounce_timer = QTimer(self._main_window)
        self._resize_debounce_timer.setSingleShot(True)
        self._resize_debounce_timer.timeout.connect(self._update_responsive_layout)
        self._main_window.resize_requested.connect(self._on_resize_requested)

        # 状态栏消息队列
        self._message_queue: list = []
        self._message_timer = QTimer(self._main_window)
        self._message_timer.setSingleShot(True)
        self._message_timer.timeout.connect(self._process_message_queue)

        # 面板协调器（负责所有UI面板管理）
        self._panel_coordinator: Optional[PanelCoordinator] = None
        
        # 事件协调器（负责所有事件订阅和处理）
        self._event_coordinator: Optional[EventCoordinator] = None
        
        # 对话框协调器（负责所有对话框管理）
        self._dialog_coordinator: Optional[DialogCoordinator] = None
        
        # 主题协调器（负责主题管理和样式应用）
        self._theme_coordinator: Optional[ThemeCoordinator] = None
        
        # UI面板（向后兼容，实际由PanelCoordinator管理）
        self._panels: Dict[str, Any] = {}
        self._optimization_dashboard = None
        self._toolbar = None

        # 窗口状态
        self._window_state = {
            'title': 'FactorWeave-Quant 2.0 多资产分析系统',
            'geometry': (100, 100, 1400, 900),
            'min_size': (1200, 800),
            'is_maximized': False
        }

        # 布局配置（向后兼容，实际由PanelCoordinator管理）
        self._layout_config = {
            'left_panel_width': 300,
            'right_panel_width': 350,
            'bottom_panel_height': 200,
        }

        # 中央数据状态（支持多资产类型）
        self._current_symbol: Optional[str] = None
        self._current_asset_name: Optional[str] = None
        self._current_asset_type: AssetType = AssetType.STOCK_A
        self._current_market: Optional[str] = None
        self._current_asset_data: Dict[str, Any] = {}
        self._is_loading = False

    @property
    def _current_stock_code(self) -> Optional[str]:
        return self._current_symbol

    @_current_stock_code.setter
    def _current_stock_code(self, value: Optional[str]):
        self._current_symbol = value

    @property
    def _current_stock_data(self) -> Dict[str, Any]:
        return self._current_asset_data

    @_current_stock_data.setter
    def _current_stock_data(self, value: Dict[str, Any]):
        self._current_asset_data = value

    def _do_initialize(self) -> None:
        """初始化协调器"""
        import time
        start_time = time.time()

        try:
            # 获取服务
            service_start = time.time()
            self._stock_service = self.service_container.resolve(StockService)
            self._chart_service = self.service_container.resolve(ChartService)
            self._analysis_service = self.service_container.resolve(
                AnalysisService)
            # 使用ThemeManager替代ThemeService
            # 修复: 先 resolve ConfigService 再初始化主题管理器（原顺序颠倒，_config_service 恒为 None）
            self._config_service = self.service_container.resolve(
                ConfigService)
            from utils.theme import get_theme_manager
            self._theme_manager = get_theme_manager(self._config_service)
            self._data_manager = self.service_container.resolve(
                UnifiedDataManager)
            service_time = time.time() - service_start
            logger.info(f"服务解析耗时: {service_time:.3f}秒")

            # 获取资产服务（TET模式）
            try:
                from core.services.asset_service import AssetService
                if self.service_container.is_registered(AssetService):
                    self._asset_service = self.service_container.resolve(AssetService)
                    logger.info("AssetService解析成功")
                else:
                    self._asset_service = None
                    logger.warning("AssetService未在容器中注册")
            except Exception as e:
                logger.warning(f"AssetService初始化失败: {e}")
                self._asset_service = None

            # 初始化窗口
            window_start = time.time()
            self._setup_window()
            window_time = time.time() - window_start
            logger.info(f"窗口设置耗时: {window_time:.3f}秒")

            # 初始化面板协调器并创建UI面板
            panels_start = time.time()
            self._panel_coordinator = PanelCoordinator(
                main_window_coordinator=self,
                service_container=self.service_container,
                event_bus=self.event_bus
            )
            self._panel_coordinator.initialize_panels()
            # 向后兼容：同步面板引用
            self._panels = self._panel_coordinator.get_all_panels()
            self._layout_config = self._panel_coordinator.get_layout_config()
            panels_time = time.time() - panels_start
            logger.info(f"面板创建耗时: {panels_time:.3f}秒")

            # 初始化事件协调器并订阅所有事件
            events_coord_start = time.time()
            self._event_coordinator = EventCoordinator(
                main_window_coordinator=self,
                service_container=self.service_container,
                event_bus=self.event_bus
            )
            self._event_coordinator.subscribe_all_events()
            events_coord_time = time.time() - events_coord_start
            logger.info(f"事件协调器初始化耗时: {events_coord_time:.3f}秒")

            # 初始化对话框协调器
            dialog_coord_start = time.time()
            self._dialog_coordinator = DialogCoordinator(
                main_window_coordinator=self,
                main_window=self._main_window
            )
            dialog_coord_time = time.time() - dialog_coord_start
            logger.info(f"对话框协调器初始化耗时: {dialog_coord_time:.3f}秒")

            # 初始化主题协调器
            theme_coord_start = time.time()
            self._theme_coordinator = ThemeCoordinator(
                main_window_coordinator=self,
                main_window=self._main_window,
                service_container=self.service_container,
                event_bus=self.event_bus,
                theme_manager=self._theme_manager if hasattr(self, '_theme_manager') else None
            )
            theme_coord_time = time.time() - theme_coord_start
            logger.info(f"主题协调器初始化耗时: {theme_coord_time:.3f}秒")

            # 设置布局
            layout_start = time.time()
            self._setup_layout()
            layout_time = time.time() - layout_start
            logger.info(f"布局设置耗时: {layout_time:.3f}秒")

            # 应用主题
            theme_start = time.time()
            self._apply_theme()
            theme_time = time.time() - theme_start
            logger.info(f"主题应用耗时: {theme_time:.3f}秒")

            # 加载配置
            config_start = time.time()
            self._load_window_config()
            config_time = time.time() - config_start
            logger.info(f"配置加载耗时: {config_time:.3f}秒")

            # 设置所有表格为只读
            # self._set_all_tables_readonly()

            # 检查数据使用条款
            terms_start = time.time()
            self._check_data_usage_terms()
            terms_time = time.time() - terms_start
            logger.info(f"条款检查耗时: {terms_time:.3f}秒")

            # 延迟初始化增强UI组件，避免阻塞主初始化流程
            # 使用QTimer在事件循环中异步初始化
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, self._initialize_enhanced_ui_components_async)

            # 连接全局字体大小变更信号
            from gui.utils.global_font_manager import get_global_font_manager
            font_mgr = get_global_font_manager()
            font_mgr.font_size_changed.connect(self._on_font_size_changed)
            logger.info("全局字体大小变更信号已连接")

            # R245: 全局启动定时导入任务执行器（事件循环就绪后异步执行，不阻塞启动）
            QTimer.singleShot(0, self._start_scheduled_executor_globally)

            total_time = time.time() - start_time
            logger.info(f"Main window coordinator initialized successfully, 总耗时: {total_time:.3f}秒")

        except Exception as e:
            logger.error(f"Failed to initialize main window coordinator: {e}")
            raise

    def _start_scheduled_executor_globally(self) -> None:
        """R245: 全局启动定时导入任务执行器

        原实现仅在打开「K线专业数据导入」窗口时才启动执行器，导致未打开过该窗口时
        配置的定时任务永远不执行。此处改为应用启动即全局启动；执行器内部支持无引擎懒加载
        （scheduled_task_executor.py _execute_task 自动创建 DataImportExecutionEngine）。
        """
        try:
            from core.services.scheduled_task_executor import start_scheduled_task_executor
            start_scheduled_task_executor()
            logger.info("定时任务执行器全局启动完成")
        except Exception as e:
            logger.warning(f"定时任务执行器全局启动失败（降级处理，不影响应用运行）: {e}")

    def _setup_window(self) -> None:
        """设置主窗口"""
        try:
            # 设置窗口图标
            try:
                icon_path = "icons/logo.png"
                self._main_window.setWindowIcon(QIcon(icon_path))
            except Exception as e:
                logger.debug(f"设置窗口图标失败: {e}")

            # 设置状态栏
            self._status_bar = QStatusBar()
            self._main_window.setStatusBar(self._status_bar)

            # 添加状态信息标签
            self._status_label = QLabel("就绪")
            self._status_bar.addWidget(self._status_label)

            # 添加永久小部件到右侧
            self._status_bar.addPermanentWidget(QFrame())  # 弹性空间

            # 数据时间标签
            self._data_time_label = QLabel("")
            self._data_time_label.setToolTip("当前数据的最新时间")
            self._data_time_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self._status_bar.addPermanentWidget(self._data_time_label)

            # 创建日志显示/隐藏按钮
            self._log_toggle_btn = QPushButton("隐藏日志")
            self._log_toggle_btn.setToolTip("隐藏/显示日志面板")
            self._log_toggle_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self._log_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: 1px solid #c0c0c0;
                    border-radius: 2px;
                    padding: 2px 8px;
                    color: #505050;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
                QPushButton:pressed {
                    background-color: #d0d0d0;
                }
            """)
            self._log_toggle_btn.clicked.connect(self._toggle_log_panel)
            self._status_bar.addPermanentWidget(self._log_toggle_btn)

            # 设置菜单栏 - 使用MainMenuBar
            self._setup_menu_bar()

            # 设置工具栏
            self._setup_toolbar()

            logger.info("Main window setup completed")

        except Exception as e:
            logger.error(f"Failed to setup main window: {e}")
            raise

    def _setup_menu_bar(self) -> None:
        """设置菜单栏 - 使用MainMenuBar"""
        try:
            # 创建MainMenuBar实例，传入coordinator引用
            menu_bar = MainMenuBar(coordinator=self, parent=self._main_window)
            self._main_window.setMenuBar(menu_bar)
            self._menu_bar = menu_bar

            logger.info("Menu bar (MainMenuBar) setup completed")

        except Exception as e:
            logger.error(f"Failed to setup menu bar: {e}")
            raise

    def _setup_toolbar(self) -> None:
        """设置工具栏"""
        try:
            from gui.tool_bar import MainToolBar

            main_window = self._main_window
            main_window.analyze_current_stock = self.analyze_current_stock
            main_window.show_analysis = self.show_analysis
            main_window.run_backtest = self.run_backtest
            main_window.show_backtest = self.show_backtest
            main_window.optimize_strategy = self.optimize_strategy
            main_window.show_optimization = self.show_optimization
            main_window.search_stock = self.search_stock
            main_window.on_search = self.on_search

            toolbar = MainToolBar(main_window)
            main_window.addToolBar(toolbar)
            self._toolbar = toolbar

            logger.info("ToolBar setup completed")
        except Exception as e:
            logger.error(f"Failed to setup toolbar: {e}")

    def _register_event_handlers(self) -> None:
        """注册事件处理器 - 在_setup_layout中实现"""
        pass  # 实际订阅在_setup_layout中

    def _setup_layout(self) -> None:
        """设置布局"""
        # 布局已在_create_panels中设置
        logger.info("布局设置完成（事件订阅已迁移到EventCoordinator）")

    def _apply_theme(self) -> None:
        """应用主题"""
        try:
            # 使用ThemeManager获取当前主题
            if hasattr(self, '_theme_manager') and self._theme_manager:
                current_theme = self._theme_manager.current_theme
                is_qss = self._theme_manager.is_qss_theme()

                logger.info(f"Theme applied: {current_theme}, Type: {'QSS' if is_qss else 'JSON'}")

                # 如果是JSON主题，需要手动通知各个面板更新
                if not is_qss:
                    self._notify_panels_theme_change()
            else:
                logger.warning("ThemeManager not available")

        except Exception as e:
            logger.error(f"Failed to apply theme: {e}")

    def _notify_panels_theme_change(self) -> None:
        """面板主题通知已迁移到 PanelCoordinator"""
        if self._panel_coordinator:
            self._panel_coordinator._notify_panels_theme_change()

    def _load_window_config(self) -> None:
        """加载窗口配置"""
        try:
            # 从配置服务加载窗口设置
            window_config = self._config_service.get('window', {})

            # 应用窗口配置
            if 'geometry' in window_config:
                geometry = window_config['geometry']
                self._main_window.setGeometry(*geometry)

            if 'maximized' in window_config and window_config['maximized']:
                self._main_window.showMaximized()

            logger.info("Window configuration loaded")

        except Exception as e:
            logger.error(f"Failed to load window configuration: {e}")

    def _save_window_config(self) -> None:
        """保存窗口配置"""
        try:
            # 获取当前窗口状态
            geometry = self._main_window.geometry()
            window_config = {
                'geometry': (geometry.x(), geometry.y(), geometry.width(), geometry.height()),
                'maximized': self._main_window.isMaximized()
            }

            # 保存到配置服务
            self._config_service.set('window', window_config)

            logger.info("Window configuration saved")

        except Exception as e:
            logger.error(f"Failed to save window configuration: {e}")

    @property
    def event_coordinator(self) -> Optional[EventCoordinator]:
        """获取事件协调器实例"""
        return self._event_coordinator

    @property
    def panel_coordinator(self) -> Optional[PanelCoordinator]:
        """获取面板协调器实例"""
        return self._panel_coordinator

    def get_main_window(self) -> QMainWindow:
        """获取主窗口"""
        return self._main_window

    def get_panel(self, panel_name: str) -> Optional[QWidget]:
        """获取面板 - 代理到 PanelCoordinator"""
        if self._panel_coordinator:
            return self._panel_coordinator.get_panel(panel_name)
        return self._panels.get(panel_name)

    def show_message(self, message: str, level: str = 'info') -> None:
        """显示消息（使用队列，每条消息至少显示2秒）"""
        self._message_queue.append(message)
        if not self._message_timer.isActive():
            self._process_message_queue()

    def _process_message_queue(self):
        """处理消息队列"""
        if self._message_queue:
            message = self._message_queue.pop(0)
            self._status_label.setText(f"  {message}")
            if self._message_queue:
                self._message_timer.start(2000)

    def _on_resize_requested(self):
        """窗口大小改变请求（防抖150ms）"""
        self._resize_debounce_timer.start(150)

    def center_dialog(self, dialog, parent=None, offset_y=50):
        """居中显示对话框"""
        try:
            if parent is None:
                parent = self._main_window

            # 获取父窗口的几何信息
            parent_rect = parent.geometry()

            # 计算对话框的位置
            x = parent_rect.x() + (parent_rect.width() - dialog.width()) // 2
            y = parent_rect.y() + (parent_rect.height() - dialog.height()) // 2 - offset_y

            # 确保对话框不会超出屏幕边界
            from PyQt5.QtWidgets import QApplication
            screen = QApplication.desktop().screenGeometry()
            x = max(0, min(x, screen.width() - dialog.width()))
            y = max(0, min(y, screen.height() - dialog.height()))

            dialog.move(x, y)

        except Exception as e:
            logger.error(f"居中对话框失败: {e}")

    def run(self) -> None:
        """运行主窗口"""
        try:
            # 显示主窗口
            self._main_window.show()

            logger.info("Main window is now running")

        except Exception as e:
            logger.error(f"Failed to run main window: {e}")
            raise

    def _cleanup_dialogs(self) -> None:
        """清理对话框引用，防止内存泄漏"""
        dialog_attrs = [
            '_plugin_manager_dialog',
            '_intelligent_model_selection_dialog',
            '_strategy_manager_dialog',
            '_trading_monitor_window',
            '_order_management_dialog',
            '_account_management_dialog',
            '_data_management_dialog',
            'enhanced_import_window',
        ]
        
        for attr in dialog_attrs:
            if hasattr(self, attr):
                dialog = getattr(self, attr)
                if dialog is not None:
                    try:
                        # 断开信号连接
                        try:
                            dialog.disconnect()
                        except Exception as e:
                            logger.debug(f"对话框断开信号失败: {e}")
                        
                        # 关闭并删除对话框
                        dialog.close()
                        dialog.deleteLater()
                    except Exception as e:
                        logger.warning(f"清理对话框 {attr} 异常: {e}")
                setattr(self, attr, None)

    def _do_dispose(self) -> None:
        """清理资源"""
        try:
            if hasattr(self, '_resize_debounce_timer'):
                self._resize_debounce_timer.stop()
            if hasattr(self, '_message_timer'):
                self._message_timer.stop()

            if self._event_coordinator:
                self._event_coordinator.dispose()
                self._event_coordinator = None

            self._cleanup_dialogs()
            if self._dialog_coordinator:
                self._dialog_coordinator.dispose()
                self._dialog_coordinator = None

            if self._panel_coordinator:
                self._panel_coordinator.dispose()
                self._panel_coordinator = None

            if self._theme_coordinator:
                self._theme_coordinator.dispose()
                self._theme_coordinator = None

            if 'performance_dashboard' in self._panels:
                self._panels['performance_dashboard'].dispose()

            if self._optimization_dashboard is not None:
                try:
                    self._optimization_dashboard.close()
                    self._optimization_dashboard.deleteLater()
                except Exception as e:
                    logger.warning(f"清理优化仪表盘异常: {e}")
                self._optimization_dashboard = None

            self._save_window_config()

            if self._main_window:
                self._main_window.close()

            logger.info("Main window coordinator disposed")

        except Exception as e:
            logger.error(f"Failed to dispose main window coordinator: {e}")

    # 文件菜单方法
    def _on_new_file(self) -> None:
        """新建文件"""
        logger.info("新建文件功能待实现")
        self.show_message("新建文件功能待实现")

    def _on_open_file(self) -> None:
        """打开文件"""
        logger.info("打开文件功能待实现")
        self.show_message("打开文件功能待实现")

    def _on_save_file(self) -> None:
        """保存文件"""
        logger.info("保存文件功能待实现")
        self.show_message("保存文件功能待实现")

    def _on_exit(self) -> None:
        """退出应用程序"""
        self._main_window.close()

    # 编辑菜单方法
    def _on_undo(self) -> None:
        """撤销操作"""
        logger.info("撤销功能待实现")
        self.show_message("撤销功能待实现")

    def _on_redo(self) -> None:
        """重做操作"""
        logger.info("重做功能待实现")
        self.show_message("重做功能待实现")

    def _on_copy(self) -> None:
        """复制操作"""
        logger.info("复制功能待实现")
        self.show_message("复制功能待实现")

    def _on_paste(self) -> None:
        """粘贴操作"""
        logger.info("粘贴功能待实现")
        self.show_message("粘贴功能待实现")

    # 视图菜单方法
    def _on_refresh(self) -> None:
        """刷新数据 - 代理到 PanelCoordinator"""
        try:
            self._panel_coordinator.refresh_panel_data('left')
            self.show_message("数据已刷新")
            logger.info("Data refreshed")

        except Exception as e:
            logger.error(f"Failed to refresh data: {e}")
            self.show_message(f"刷新失败: {e}")

    def _on_increase_font(self) -> None:
        """增大字体"""
        try:
            from gui.utils.global_font_manager import get_global_font_manager
            font_manager = get_global_font_manager()
            font_manager.increase_font_size()
            self.show_message(f"字体大小: {font_manager.get_font_size()}")
            logger.info(f"字体大小已增大: {font_manager.get_font_size()}")
        except Exception as e:
            logger.error(f"增大字体失败: {e}")
            self.show_message(f"增大字体失败: {e}")

    def _on_decrease_font(self) -> None:
        """减小字体"""
        try:
            from gui.utils.global_font_manager import get_global_font_manager
            font_manager = get_global_font_manager()
            font_manager.decrease_font_size()
            self.show_message(f"字体大小: {font_manager.get_font_size()}")
            logger.info(f"字体大小已减小: {font_manager.get_font_size()}")
        except Exception as e:
            logger.error(f"减小字体失败: {e}")
            self.show_message(f"减小字体失败: {e}")

    def _on_reset_font(self) -> None:
        """重置字体"""
        try:
            from gui.utils.global_font_manager import get_global_font_manager
            font_manager = get_global_font_manager()
            font_manager.reset_font_size()
            self.show_message(f"字体大小已重置: {font_manager.get_font_size()}")
            logger.info(f"字体大小已重置: {font_manager.get_font_size()}")
        except Exception as e:
            logger.error(f"重置字体失败: {e}")
            self.show_message(f"重置字体失败: {e}")

    def _on_font_size_changed(self, size: float) -> None:
        """全局字体大小变更通知所有面板"""
        try:
            logger.info(f"全局字体大小变更为: {size}，通知所有面板更新")
            for name, panel in self._panels.items():
                try:
                    if hasattr(panel, 'apply_font_size'):
                        panel.apply_font_size(size)
                except Exception as e:
                    logger.warning(f"面板 {name} 应用字体大小失败: {e}")
        except Exception as e:
            logger.error(f"处理字体大小变更失败: {e}")

    # 工具菜单方法
    def _on_data_export(self) -> None:
        """数据导出（别名方法）"""
        self._on_export_data()

    def _on_settings(self) -> None:
        """系统设置"""
        try:
            from gui.dialogs.settings_dialog import SettingsDialog

            dialog = SettingsDialog(
                parent=self._main_window,
                theme_manager=self._theme_manager if hasattr(self, '_theme_manager') else None,
                config_service=self._config_service
            )

            # 连接设置应用信号
            dialog.settings_applied.connect(self._on_settings_applied)
            dialog.theme_changed.connect(self._on_theme_changed)

            self.center_dialog(dialog)
            dialog.exec_()

        except Exception as e:
            logger.error(f"系统设置失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开系统设置对话框失败: {str(e)}")

    def _on_feature_control(self) -> None:
        """功能控制面板"""
        try:
            from gui.widgets.feature_control_widget import FeatureControlWidget
            from PyQt5.QtWidgets import QDialog, QVBoxLayout

            dialog = QDialog(self._main_window)
            dialog.setWindowTitle("功能控制")
            dialog.resize(900, 700)

            layout = QVBoxLayout(dialog)
            widget = FeatureControlWidget()
            layout.addWidget(widget)

            self.center_dialog(dialog)
            dialog.exec_()

        except Exception as e:
            logger.error(f"打开功能控制失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开功能控制失败: {str(e)}")

    def _on_settings_applied(self, settings: dict) -> None:
        """处理设置应用事件"""
        try:
            # 保存设置到配置服务
            if self._config_service:
                for key, value in settings.items():
                    self._config_service.set(key, value)

            # 应用相关设置
            if 'font_size' in settings:
                # 应用字体大小变化
                font = self._main_window.font()
                font.setPointSize(settings['font_size'])
                self._main_window.setFont(font)

            logger.info("设置已应用")
            self.show_message("设置已保存并应用")

        except Exception as e:
            logger.error(f"应用设置失败: {e}")
            QMessageBox.critical(self._main_window, "错误", f"应用设置失败: {str(e)}")

    # 帮助菜单方法
    def _on_help(self) -> None:
        """帮助文档"""
        try:
            from gui.dialogs.help_viewer_dialog import HelpViewerDialog
            from pathlib import Path
            project_root = Path(__file__).resolve().parents[2]
            dialog = HelpViewerDialog(
                self._main_window,
                title="帮助文档",
                md_path=str(project_root / "README.md"),
            )
            self.center_dialog(dialog)
            dialog.exec_()
            logger.info("打开帮助文档")
        except Exception as e:
            logger.error(f"帮助文档失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法打开帮助文档: {e}")

    def _on_shortcuts(self) -> None:
        """快捷键说明"""
        from PyQt5.QtWidgets import QMessageBox
        shortcuts_text = """
常用快捷键：

文件操作：
Ctrl+N - 新建
Ctrl+O - 打开
Ctrl+S - 保存
Ctrl+Q - 退出

编辑操作：
Ctrl+Z - 撤销
Ctrl+Y - 重做
Ctrl+C - 复制
Ctrl+V - 粘贴

视图操作：
F5 - 刷新数据

工具操作：
Ctrl+E - 数据导出
Ctrl+, - 系统设置

帮助：
F1 - 用户手册
Ctrl+F1 - 快捷键说明
Ctrl+F12 - 关于
        """
        QMessageBox.information(
            self._main_window, "快捷键说明", shortcuts_text.strip())

    def _on_about(self) -> None:
        """关于对话框"""
        about_text = """
FactorWeave-Quant  2.0 (重构版本)

基于FactorWeave-Quant量化框架的股票分析工具

主要功能：
 股票数据查看和分析
 技术指标计算和显示
 策略回测和优化
 投资组合管理
 数据质量检查

版本：2.0
作者：FactorWeave-Quant开发团队
        """
        QMessageBox.about(self._main_window, "关于 FactorWeave-Quant ",
                          about_text.strip())

    # 高级功能菜单方法（保持原有实现）
    def _on_node_management(self) -> None:
        """节点管理（分布式节点监控）"""
        try:
            # 使用新的真实数据UI
            from gui.dialogs.distributed_node_monitor_dialog import DistributedNodeMonitorDialog
            from core.containers import get_service_container

            # 获取分布式服务
            container = get_service_container()
            distributed_service = container.get('distributed_service')

            if not distributed_service:
                QMessageBox.warning(
                    self._main_window,
                    "警告",
                    "分布式服务未初始化，请检查系统配置"
                )
                logger.warning("分布式服务未初始化")
                return

            dialog = DistributedNodeMonitorDialog(distributed_service, self._main_window)
            self.center_dialog(dialog)
            dialog.exec_()

        except Exception as e:
            logger.error(f"节点管理失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开分布式节点监控失败: {str(e)}")

    def _on_cloud_api(self) -> None:
        """云端API管理"""
        try:
            from gui.dialogs.cloud_api_dialog import CloudApiDialog

            dialog = CloudApiDialog(self._main_window)
            self.center_dialog(dialog)
            dialog.exec_()

        except Exception as e:
            logger.error(f"云端API管理失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开云端API管理对话框失败: {str(e)}")

    def _on_plugin_manager(self, tab_name: str = None) -> None:
        """增强版插件管理器 - 统一的插件管理界面

        Args:
            tab_name: 可选，目标 tab 文本子串（如"数据源管理"/"已安装插件"/"插件市场"），
                      用于菜单项定位到对应 tab（R245 修复: 原 4 个插件菜单项打开同一 tab）
        """
        # 防止重复打开 - 检查是否已有插件管理对话框实例
        if hasattr(self, '_plugin_manager_dialog') and self._plugin_manager_dialog is not None:
            if self._plugin_manager_dialog.isVisible():
                self._plugin_manager_dialog.raise_()
                self._plugin_manager_dialog.activateWindow()
                logger.info("插件管理对话框已存在，激活现有窗口")
                return
            else:
                self._plugin_manager_dialog = None

        try:
            from gui.dialogs.plugin_manager_dialog_unified import PluginManagerDialogUnified
            from core.plugin_manager import PluginManager

            # 智能获取插件管理器实例
            plugin_manager = None

            # 确保从正确的service_container获取
            service_container = self._service_container
            if not service_container:
                # 如果没有，尝试从全局获取
                from core.containers import get_service_container
                service_container = get_service_container()

            # 方法1：尝试从服务容器获取（主要方法）
            if service_container and service_container.is_registered(PluginManager):
                try:
                    plugin_manager = service_container.resolve(PluginManager)
                    logger.info("从服务容器获取插件管理器成功")

                    # 验证插件管理器是否已初始化
                    if plugin_manager and hasattr(plugin_manager, 'enhanced_plugins'):
                        all_plugins = plugin_manager.get_all_plugins()
                        logger.info(f" 插件管理器已初始化，包含 {len(all_plugins)} 个插件")
                    else:
                        logger.warning("插件管理器未完全初始化，尝试重新初始化")
                        if plugin_manager and hasattr(plugin_manager, 'initialize'):
                            plugin_manager.initialize()

                except Exception as e:
                    logger.error(f" 从服务容器获取插件管理器失败: {e}")
                    logger.error(traceback.format_exc())
                    plugin_manager = None
            else:
                logger.warning("PluginManager未在服务容器中注册")

            # 方法2：如果方法1失败，尝试创建并初始化新实例
            if not plugin_manager:
                try:
                    logger.info("创建新的插件管理器实例...")

                    # 获取必要的依赖
                    from utils.config_manager import ConfigManager
                    config_manager = None

                    if service_container and service_container.is_registered(ConfigManager):
                        config_manager = service_container.resolve(ConfigManager)
                    else:
                        config_manager = ConfigManager()

                    # 创建并初始化插件管理器
                    plugin_manager = PluginManager(
                        plugin_dir="plugins",
                        main_window=self._main_window,
                        data_manager=None,
                        config_manager=config_manager,
                        # log_manager已迁移到Loguru
                    )

                    # 初始化插件管理器
                    plugin_manager.initialize()
                    logger.info("插件管理器实例创建并初始化成功")

                    # 将新实例注册到服务容器（如果可能）
                    if service_container:
                        try:
                            service_container.register_instance(PluginManager, plugin_manager)
                            logger.info("新插件管理器实例已注册到服务容器")
                        except Exception as reg_e:
                            logger.warning(f" 注册新插件管理器实例失败: {reg_e}")

                except Exception as e:
                    logger.error(f" 创建插件管理器实例失败: {e}")
                    logger.error(traceback.format_exc())
                    # 继续执行，允许dialog处理空的plugin_manager

            # 情绪数据服务已删除（功能已整合到热点分析）
            sentiment_service = None

            # 显示插件管理器状态
            plugin_status = "可用" if plugin_manager else "不可用"
            logger.info(f" 插件管理器状态: {plugin_status}")

            # 创建并显示增强版对话框
            self._plugin_manager_dialog = PluginManagerDialogUnified(
                plugin_manager,
                self._main_window
            )

            # 设置对话框属性
            self._plugin_manager_dialog.setWindowTitle("FactorWeave-Quant 插件管理器")
            self._plugin_manager_dialog.setMinimumSize(1000, 700)

            # 连接对话框的关闭信号
            self._plugin_manager_dialog.finished.connect(self._on_plugin_manager_dialog_closed)

            # 居中显示
            if hasattr(self, 'center_dialog'):
                self.center_dialog(self._plugin_manager_dialog)

            # R245: 按菜单项定位到指定 tab（menu_bar 4 个插件菜单项传入不同 tab_name）
            if tab_name and hasattr(self._plugin_manager_dialog, 'tab_widget'):
                tab_widget = self._plugin_manager_dialog.tab_widget
                for i in range(tab_widget.count()):
                    if tab_name in tab_widget.tabText(i):
                        tab_widget.setCurrentIndex(i)
                        break

            # 显示对话框
            self._plugin_manager_dialog.show()
            logger.info("插件管理器对话框已显示")

        except ImportError as e:
            error_msg = f"插件管理器模块导入失败: {e}"
            logger.error(error_msg)
            QMessageBox.critical(
                self._main_window,
                "模块错误",
                f"{error_msg}\n\n请检查插件系统是否正确安装。"
            )
        except Exception as e:
            error_msg = f"打开插件管理器失败: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            QMessageBox.critical(
                self._main_window,
                "错误",
                f"{error_msg}\n\n请查看日志获取详细信息。"
            )
            # 清理可能的无效引用
            if hasattr(self, '_plugin_manager_dialog'):
                self._plugin_manager_dialog = None

    def _on_plugin_manager_dialog_closed(self):
        """插件管理对话框关闭时的回调"""
        logger.info("插件管理对话框已关闭，清理引用")
        if hasattr(self, '_plugin_manager_dialog'):
            self._plugin_manager_dialog = None

    def _on_plugin_market(self) -> None:
        """插件市场"""
        try:
            from gui.dialogs.enhanced_plugin_market_dialog import EnhancedPluginMarketDialog

            # 获取插件管理器
            plugin_manager = self._service_container.resolve(PluginManager)

            dialog = EnhancedPluginMarketDialog(
                plugin_manager, self._main_window)
            self.center_dialog(dialog)
            dialog.exec_()

        except Exception as e:
            logger.error(f"插件市场失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开插件市场对话框失败: {str(e)}")

    def _on_indicator_market(self) -> None:
        """指标市场"""
        try:
            from gui.dialogs.indicator_market_dialog import IndicatorMarketDialog

            dialog = IndicatorMarketDialog(self._main_window)
            self.center_dialog(dialog)
            dialog.exec_()

        except Exception as e:
            logger.error(f"指标市场失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开指标市场对话框失败: {str(e)}")

    def _on_batch_analysis(self) -> None:
        """批量分析"""
        try:
            # 尝试激活右侧面板的批量分析功能
            right_panel = self._panels.get('right')
            if right_panel and hasattr(right_panel, '_analysis_tools_panel'):
                analysis_panel = right_panel._analysis_tools_panel
                if hasattr(analysis_panel, 'start_enhanced_batch_analysis'):
                    # 激活右侧面板并开始批量分析
                    # 修复: 原代码调用不存在的 activate_batch_tab()（enhanced_batch_analysis_methods.py 无此方法），
                    # 实际应调用 start_enhanced_batch_analysis()（L177）
                    if hasattr(right_panel, 'show'):
                        right_panel.show()
                    analysis_panel.start_enhanced_batch_analysis()
                    logger.info("已激活右侧面板批量分析功能")
                    return
            
            # 如果面板方法不可用，尝试创建批量分析对话框
            try:
                from gui.dialogs.batch_analysis_dialog import BatchAnalysisDialog
                dialog = BatchAnalysisDialog(self._main_window)
                self.center_dialog(dialog)
                dialog.exec_()
            except ImportError:
                # 对话框不存在，显示提示（修复: 原文案误导，此时右侧面板同样不可用）
                QMessageBox.information(
                    self._main_window, 
                    "批量分析", 
                    "批量分析功能当前不可用，请确认数据分析组件已正确加载"
                )
                logger.info("批量分析功能不可用（右侧面板与对话框均不可用）")

        except Exception as e:
            logger.error(f"批量分析失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开批量分析功能失败: {str(e)}")

    def _on_intelligent_model_selection(self) -> None:
        """智能模型选择"""
        # 防止重复打开 - 检查是否已有智能模型选择对话框实例
        if hasattr(self, '_intelligent_model_selection_dialog') and self._intelligent_model_selection_dialog is not None:
            if self._intelligent_model_selection_dialog.isVisible():
                self._intelligent_model_selection_dialog.raise_()
                self._intelligent_model_selection_dialog.activateWindow()
                logger.info("智能模型选择对话框已存在，激活现有窗口")
                return
            else:
                self._intelligent_model_selection_dialog = None

        try:
            from gui.dialogs.intelligent_model_selection_dialog import IntelligentModelSelectionDialog

            # 创建智能模型选择对话框实例并保存引用
            self._intelligent_model_selection_dialog = IntelligentModelSelectionDialog(
                self._main_window, 
                service_container=self.service_container
            )

            # 连接对话框的关闭信号
            self._intelligent_model_selection_dialog.finished.connect(self._on_intelligent_model_selection_dialog_closed)

            # 设置对话框居中显示
            self.center_dialog(self._intelligent_model_selection_dialog)

            # 显示对话框
            self._intelligent_model_selection_dialog.exec_()

        except ImportError as e:
            # 如果对话框不存在，尝试使用控制面板直接创建
            logger.warning(f"智能模型选择对话框导入失败: {e}，尝试使用控制面板")
            self._show_intelligent_model_selection_panel()
        except Exception as e:
            logger.error(f"智能模型选择失败: {e}")
            logger.error(traceback.format_exc())
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开智能模型选择失败: {str(e)}")

    def _show_intelligent_model_selection_panel(self) -> None:
        """显示智能模型选择面板"""
        try:
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox
            from gui.widgets.intelligent_model_selection.control_panel import IntelligentModelControlPanel
            from core.ai.intelligent_selection import IntelligentModelSelector

            # 创建对话框
            dialog = QDialog(self._main_window)
            dialog.setWindowTitle("智能模型选择")
            dialog.setMinimumSize(500, 700)
            
            # 创建布局
            layout = QVBoxLayout(dialog)
            
            # 创建智能模型选择控制面板
            control_panel = IntelligentModelControlPanel()
            layout.addWidget(control_panel)
            
            # 尝试创建智能选择器
            try:
                # R244 修复: 原 IntelligentSelector 未定义，应使用 L1156 已导入的 IntelligentModelSelector
                intelligent_selector = IntelligentModelSelector()
                control_panel.set_intelligent_selector(intelligent_selector)
                logger.info("智能选择器创建成功")
            except Exception as e:
                logger.warning(f"智能选择器创建失败: {e}")
            
            # 创建按钮框
            button_box = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel
            )
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            # 设置对话框居中显示
            self.center_dialog(dialog)
            
            # 显示对话框
            dialog.exec_()

        except Exception as e:
            logger.error(f"显示智能模型选择面板失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开智能模型选择面板失败: {str(e)}")

    def _on_intelligent_model_selection_dialog_closed(self):
        """智能模型选择对话框关闭时的回调"""
        logger.info("智能模型选择对话框已关闭，清理引用")
        if hasattr(self, '_intelligent_model_selection_dialog'):
            self._intelligent_model_selection_dialog = None

    def _on_strategy_management(self) -> None:
        """策略管理"""
        if hasattr(self, '_strategy_manager_dialog') and self._strategy_manager_dialog is not None:
            if self._strategy_manager_dialog.isVisible():
                self._strategy_manager_dialog.raise_()
                self._strategy_manager_dialog.activateWindow()
                logger.info("策略管理对话框已存在，激活现有窗口")
                return
            else:
                self._strategy_manager_dialog = None

        try:
            from gui.dialogs.strategy_manager_dialog import StrategyManagerDialog

            self._strategy_manager_dialog = StrategyManagerDialog(self._main_window)

            self._strategy_manager_dialog.finished.connect(self._on_strategy_manager_dialog_closed)

            self.center_dialog(self._strategy_manager_dialog)
            self._strategy_manager_dialog.show()

        except ImportError as e:
            logger.error(f"StrategyManagerDialog不可用: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"策略管理功能不可用: {str(e)}")
            if hasattr(self, '_strategy_manager_dialog'):
                self._strategy_manager_dialog = None
        except Exception as e:
            logger.error(f"策略管理失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开策略管理对话框失败: {str(e)}")
            if hasattr(self, '_strategy_manager_dialog'):
                self._strategy_manager_dialog = None

    def _on_strategy_manager_dialog_closed(self):
        """策略管理对话框关闭时的回调"""
        logger.info("策略管理对话框已关闭，清理引用")
        if hasattr(self, '_strategy_manager_dialog'):
            self._strategy_manager_dialog = None

    def _on_trading_monitor(self) -> None:
        """交易监控"""
        try:
            # 检查是否已经创建了交易监控窗口
            if not hasattr(self, '_trading_monitor_window') or self._trading_monitor_window is None:
                from gui.widgets.enhanced_trading_monitor_widget import EnhancedTradingMonitorWidget
                from core.services.trading_service import TradingService
                from core.services.strategy_service import StrategyService

                # 从服务容器获取服务
                trading_service = None
                strategy_service = None

                try:
                    trading_service = self.service_container.resolve(TradingService)
                except Exception as e:
                    logger.warning(f"无法获取TradingService: {e}")

                try:
                    strategy_service = self.service_container.resolve(StrategyService)
                except Exception as e:
                    logger.warning(f"无法获取StrategyService: {e}")

                # 创建交易监控窗口
                self._trading_monitor_window = EnhancedTradingMonitorWidget(
                    parent=None,  # 独立窗口
                    trading_service=trading_service,
                    strategy_service=strategy_service
                )

                # 设置窗口属性
                self._trading_monitor_window.setWindowTitle("交易监控")
                self._trading_monitor_window.resize(1200, 800)

                # 设置窗口不置顶
                self._trading_monitor_window.setWindowFlags(
                    self._trading_monitor_window.windowFlags() & ~Qt.WindowStaysOnTopHint
                )

                # 连接窗口关闭事件
                def on_window_closed():
                    self._trading_monitor_window = None

                def close_event_handler(event):
                    on_window_closed()
                    event.accept()

                self._trading_monitor_window.closeEvent = close_event_handler

            # 显示窗口
            self._trading_monitor_window.show()
            self._trading_monitor_window.activateWindow()
            self._trading_monitor_window.raise_()

            logger.info("交易监控窗口已打开")

        except Exception as e:
            logger.error(f"打开交易监控窗口失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开交易监控窗口失败: {str(e)}")

    def _on_order_management(self) -> None:
        """订单管理"""
        try:
            from gui.dialogs.order_management_dialog import OrderManagementDialog

            # 检查是否已经创建了订单管理窗口
            if not hasattr(self, '_order_management_dialog') or self._order_management_dialog is None:
                # 创建订单管理窗口
                self._order_management_dialog = OrderManagementDialog(parent=self._main_window)

                # 设置窗口属性
                self._order_management_dialog.setWindowTitle("订单管理")

                # 设置窗口不置顶
                self._order_management_dialog.setWindowFlags(
                    self._order_management_dialog.windowFlags() & ~Qt.WindowStaysOnTopHint
                )

                # 连接窗口关闭事件
                def on_window_closed():
                    self._order_management_dialog = None

                def close_event_handler(event):
                    on_window_closed()
                    event.accept()

                self._order_management_dialog.closeEvent = close_event_handler

            # 显示窗口
            self._order_management_dialog.show()
            self._order_management_dialog.activateWindow()
            self._order_management_dialog.raise_()

            logger.info("订单管理窗口已打开")

        except Exception as e:
            logger.error(f"打开订单管理窗口失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开订单管理窗口失败: {str(e)}")

    def _on_account_management(self) -> None:
        """账户管理"""
        try:
            from gui.dialogs.account_management_dialog import AccountManagementDialog

            # 检查是否已经创建了账户管理窗口
            if not hasattr(self, '_account_management_dialog') or self._account_management_dialog is None:
                # 创建账户管理窗口
                self._account_management_dialog = AccountManagementDialog(parent=self._main_window)

                # 设置窗口属性
                self._account_management_dialog.setWindowTitle("账户管理")
                self._account_management_dialog.resize(1200, 800)

                # 设置窗口不置顶
                self._account_management_dialog.setWindowFlags(
                    self._account_management_dialog.windowFlags() & ~Qt.WindowStaysOnTopHint
                )

                # 连接窗口关闭事件
                def on_window_closed():
                    self._account_management_dialog = None

                def close_event_handler(event):
                    on_window_closed()
                    event.accept()

                self._account_management_dialog.closeEvent = close_event_handler

            # 显示窗口
            self._account_management_dialog.show()
            self._account_management_dialog.activateWindow()
            self._account_management_dialog.raise_()

            logger.info("账户管理窗口已打开")

        except Exception as e:
            logger.error(f"打开账户管理窗口失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开账户管理窗口失败: {str(e)}")

    def _on_portfolio_management(self) -> None:
        """投资组合管理"""
        try:
            if hasattr(self, '_portfolio_dialog') and self._portfolio_dialog is not None:
                if self._portfolio_dialog.isVisible():
                    self._portfolio_dialog.raise_()
                    self._portfolio_dialog.activateWindow()
                    logger.info("投资组合管理对话框已存在，激活现有窗口")
                    return
                else:
                    self._portfolio_dialog = None

            from gui.dialogs.portfolio_dialog import PortfolioDialog

            self._portfolio_dialog = PortfolioDialog(self._main_window)
            self._portfolio_dialog.setWindowTitle("投资组合管理")
            self._portfolio_dialog.resize(1100, 800)

            def on_portfolio_closed():
                self._portfolio_dialog = None

            def close_event_handler(event):
                on_portfolio_closed()
                event.accept()

            self._portfolio_dialog.closeEvent = close_event_handler

            self._portfolio_dialog.show()
            self._portfolio_dialog.activateWindow()
            self._portfolio_dialog.raise_()

            logger.info("投资组合管理对话框已打开")

        except Exception as e:
            logger.error(f"打开投资组合管理对话框失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开投资组合管理对话框失败: {str(e)}")

    def _on_optimization_dashboard(self) -> None:
        """显示优化仪表板"""
        try:
            if self._optimization_dashboard is None:
                self._optimization_dashboard = create_optimization_dashboard(
                    self.event_bus)

            self._optimization_dashboard.show()
            self._optimization_dashboard.activateWindow()
            self._optimization_dashboard.raise_()
        except Exception as e:
            logger.error(f"打开优化仪表板失败: {e}")
            self.show_message(f"打开优化仪表板失败: {str(e)}", level='error')

    def _on_one_click_optimization(self) -> None:
        """一键优化"""
        try:
            from PyQt5.QtWidgets import QProgressDialog
            from optimization.auto_tuner import AlgorithmAutoTuner
            from PyQt5.QtCore import QThread, pyqtSignal

            # 创建进度对话框
            progress = QProgressDialog(
                "正在执行一键优化...", "取消", 0, 100, self._main_window)
            progress.setWindowTitle("一键优化")
            progress.setModal(True)
            progress.show()

            # 创建优化线程
            class OptimizationThread(QThread):
                progress_updated = pyqtSignal(int)
                optimization_completed = pyqtSignal(dict)
                error_occurred = pyqtSignal(str)

                def run(self):
                    try:
                        auto_tuner = AlgorithmAutoTuner(debug_mode=True)

                        # 模拟优化过程
                        for i in range(101):
                            if self.isInterruptionRequested():
                                return
                            self.progress_updated.emit(i)
                            self.msleep(50)

                        # 执行实际优化
                        result = auto_tuner.one_click_optimize()
                        self.optimization_completed.emit(result)

                    except Exception as e:
                        self.error_occurred.emit(str(e))

            def on_progress_updated(value):
                progress.setValue(value)

            def on_optimization_completed(result):
                progress.close()
                # 一键优化返回 report dict（auto_tuner.py _generate_optimization_report），
                # 形态数量位于 details 列表（修复: 原 len(result) 恒等于键数）
                details = result.get('details', []) if isinstance(result, dict) else []
                QMessageBox.information(self._main_window, "成功",
                                        f"一键优化完成！\n优化了 {len(details)} 个形态")
                logger.info(f"一键优化完成: {result}")

            def on_error_occurred(error):
                progress.close()
                QMessageBox.critical(
                    self._main_window, "错误", f"一键优化失败: {error}")
                logger.error(f"一键优化失败: {error}")

            def on_canceled():
                optimization_thread.requestInterruption()
                optimization_thread.wait()
                logger.info("一键优化已取消")

            # 创建并启动线程
            optimization_thread = OptimizationThread()
            optimization_thread.progress_updated.connect(on_progress_updated)
            optimization_thread.optimization_completed.connect(
                on_optimization_completed)
            optimization_thread.error_occurred.connect(on_error_occurred)

            progress.canceled.connect(on_canceled)

            optimization_thread.start()

        except Exception as e:
            logger.error(f"启动一键优化失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"启动一键优化失败: {str(e)}")

    def _on_intelligent_optimization(self) -> None:
        """智能优化"""
        try:
            from PyQt5.QtWidgets import QInputDialog, QProgressDialog

            # 获取优化参数
            performance_threshold, ok1 = QInputDialog.getDouble(
                self._main_window, "智能优化", "性能阈值 (0.0-1.0):", 0.8, 0.0, 1.0, 2
            )
            if not ok1:
                return

            improvement_target, ok2 = QInputDialog.getDouble(
                self._main_window, "智能优化", "改进目标 (0.0-1.0):", 0.1, 0.0, 1.0, 2
            )
            if not ok2:
                return

            # 创建进度对话框
            progress = QProgressDialog(
                "正在执行智能优化...", "取消", 0, 100, self._main_window)
            progress.setWindowTitle("智能优化")
            progress.setModal(True)
            progress.show()

            # 创建智能优化线程
            class SmartOptimizationThread(QThread):
                progress_updated = pyqtSignal(int)
                optimization_completed = pyqtSignal(dict)
                error_occurred = pyqtSignal(str)

                def __init__(self, perf_threshold, improve_target):
                    super().__init__()
                    self.performance_threshold = perf_threshold
                    self.improvement_target = improve_target

                @measure_performance("SmartOptimizationThread.run")
                def run(self):
                    try:
                        # 模拟智能优化过程
                        for i in range(101):
                            if self.isInterruptionRequested():
                                return
                            self.progress_updated.emit(i)
                            self.msleep(80)

                        # 执行实际智能优化
                        # R244 修复: 原 PerformanceAutoTuner(unified_monitor.py L588)
                        # 无 debug_mode 参数且无 smart_optimize 方法，改用
                        # AlgorithmAutoTuner(auto_tuner.py L40) 的 smart_optimize(L117)
                        from optimization.auto_tuner import AlgorithmAutoTuner
                        auto_tuner = AlgorithmAutoTuner(debug_mode=True)
                        result = auto_tuner.smart_optimize(
                            performance_threshold=self.performance_threshold,
                            improvement_target=self.improvement_target
                        )
                        self.optimization_completed.emit(result)

                    except Exception as e:
                        self.error_occurred.emit(str(e))

            def on_progress_updated(value):
                progress.setValue(value)

            def on_optimization_completed(result):
                progress.close()
                # 智能优化返回 report dict（auto_tuner.py _generate_smart_optimization_report），
                # 改进形态数与总体改进需从 summary 读取（修复: 原键 improved_patterns/total_improvement 不存在，恒为 0）
                summary = result.get('summary') or {}
                improved_count = summary.get('successful_tasks', 0)
                total_improvement = (summary.get('average_improvement', 0) or 0) / 100.0
                QMessageBox.information(self._main_window, "成功",
                                        f"智能优化完成！\n改进了 {improved_count} 个形态\n总体改进: {total_improvement:.2%}")
                logger.info(f"智能优化完成: {result}")

            def on_error_occurred(error):
                progress.close()
                QMessageBox.critical(
                    self._main_window, "错误", f"智能优化失败: {error}")
                logger.error(f"智能优化失败: {error}")

            def on_canceled():
                smart_thread.requestInterruption()
                smart_thread.wait()
                logger.info("智能优化已取消")

            # 创建并启动线程
            smart_thread = SmartOptimizationThread(
                performance_threshold, improvement_target)
            smart_thread.progress_updated.connect(on_progress_updated)
            smart_thread.optimization_completed.connect(
                on_optimization_completed)
            smart_thread.error_occurred.connect(on_error_occurred)

            progress.canceled.connect(on_canceled)

            smart_thread.start()

        except Exception as e:
            logger.error(f"启动智能优化失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"启动智能优化失败: {str(e)}")

    def _on_performance_evaluation(self):
        """性能评估"""
        try:
            # 使用现有的性能评估器
            from core.performance import get_performance_monitor as create_performance_evaluator
            from gui.dialogs.performance_evaluation_dialog import PerformanceEvaluationDialog

            # 创建性能评估器
            evaluator = create_performance_evaluator()

            # 显示性能评估对话框
            dialog = PerformanceEvaluationDialog(self._main_window)
            dialog.set_evaluator(evaluator)
            dialog.exec_()

        except ImportError as e:
            self.logger.error(f"性能评估模块导入失败: {e}")
            # 使用备用的策略性能评估器
            try:
                from optimization.algorithm_optimizer import PerformanceEvaluator
                evaluator = PerformanceEvaluator()
                dialog = PerformanceEvaluationDialog(self._main_window)
                dialog.set_evaluator(evaluator)
                dialog.exec_()

            except Exception as e2:
                self.logger.error(f"备用性能评估也失败: {e2}")
                QMessageBox.warning(
                    self._main_window,
                    "性能评估",
                    f"性能评估功能暂时不可用：{e2}"
                )
        except Exception as e:
            self.logger.error(f"启动性能评估失败: {e}")
            QMessageBox.warning(
                self._main_window,
                "性能评估",
                f"启动性能评估失败：{e}"
            )

    def _on_version_management(self) -> None:
        """版本管理"""
        try:
            from gui.dialogs.version_manager_dialog import VersionManagerDialog

            dialog = VersionManagerDialog(self._main_window)
            self.center_dialog(dialog)
            dialog.exec_()

        except Exception as e:
            logger.error(f"版本管理失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开版本管理对话框失败: {str(e)}")

    def _on_single_stock_quality_check(self) -> None:
        """单股质量检查"""
        try:
            from gui.dialogs.data_quality_dialog import DataQualityDialog

            # DataQualityDialog 接受 stock_code 参数，不是 mode 参数
            dialog = DataQualityDialog(self._main_window, stock_code=None)
            self.center_dialog(dialog)
            dialog.exec_()

        except Exception as e:
            logger.error(f"单股质量检查失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开单股质量检查对话框失败: {str(e)}")

    def _on_batch_quality_check(self) -> None:
        """批量质量检查"""
        try:
            from gui.dialogs.data_quality_dialog import DataQualityDialog

            # 批量质量检查也使用相同的对话框
            dialog = DataQualityDialog(self._main_window, stock_code=None)
            self.center_dialog(dialog)
            dialog.exec_()

        except Exception as e:
            logger.error(f"批量质量检查失败: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"打开批量质量检查对话框失败: {str(e)}")

    # 缓存管理方法
    def _on_clear_data_cache(self) -> None:
        """清理数据缓存"""
        try:
            # 清理统一缓存服务
            try:
                from core.services.cache_service import CacheService
                cache_service = self.service_container.get_service(CacheService)
                if cache_service:
                    namespaces = cache_service.list_namespaces()
                    for ns in namespaces:
                        cache_service.clear_namespace(ns)
                    logger.info("统一缓存已清理")
            except Exception as e:
                logger.warning(f"清理统一缓存失败: {e}")

            # 获取股票服务
            stock_service = self.service_container.get_service(StockService)
            if stock_service:
                stock_service.clear_cache('data')

            # 获取图表服务
            chart_service = self.service_container.get_service(ChartService)
            if chart_service:
                chart_service.clear_cache()

            # 获取分析服务
            analysis_service = self.service_container.get_service(
                AnalysisService)
            # R244 修复: AnalysisService 未继承 CacheableService(analysis_service.py L153
            # 继承 BaseService)，无 clear_cache 方法，加防御避免 AttributeError 假失败
            if analysis_service and hasattr(analysis_service, 'clear_cache'):
                analysis_service.clear_cache()

            QMessageBox.information(self._main_window, "成功", "数据缓存已清理")
            logger.info("Data cache cleared")

        except Exception as e:
            logger.error(f"Failed to clear data cache: {e}")
            QMessageBox.critical(self._main_window, "错误", f"清理数据缓存失败: {e}")

    def _on_clear_negative_cache(self) -> None:
        """清理负缓存"""
        try:
            # 获取股票服务
            stock_service = self.service_container.get_service(StockService)
            if stock_service:
                stock_service.clear_cache('negative')

            # 清理左侧面板的负缓存
            left_panel = self._panels.get('left')
            if left_panel and hasattr(left_panel, '_no_data_cache'):
                left_panel._no_data_cache.clear()

            QMessageBox.information(self._main_window, "成功", "负缓存已清理")
            logger.info("Negative cache cleared")

        except Exception as e:
            logger.error(f"Failed to clear negative cache: {e}")
            QMessageBox.critical(self._main_window, "错误", f"清理负缓存失败: {e}")

    def _on_clear_all_cache(self) -> None:
        """清理所有缓存"""
        try:
            # 清理数据缓存
            self._on_clear_data_cache()

            # 清理负缓存
            self._on_clear_negative_cache()

            QMessageBox.information(self._main_window, "成功", "所有缓存已清理")
            logger.info("All cache cleared")

        except Exception as e:
            logger.error(f"Failed to clear all cache: {e}")
            QMessageBox.critical(self._main_window, "错误", f"清理所有缓存失败: {e}")

    def _on_startup_guides(self) -> None:
        """显示启动向导"""
        try:
            from gui.dialogs.startup_guides_dialog import StartupGuidesDialog

            dialog = StartupGuidesDialog(self._main_window)
            self.center_dialog(dialog)
            dialog.exec_()

        except ImportError as e:
            logger.warning(f"启动向导对话框导入失败: {e}")
            # 如果启动向导对话框不存在，创建一个简单的消息框
            QMessageBox.information(
                self._main_window,
                "启动向导",
                "欢迎使用FactorWeave-Quant 2.0！\n\n"
                "主要功能：\n"
                "1. 股票数据查看和分析\n"
                "2. 技术指标计算和显示\n"
                "3. 策略回测和优化\n"
                "4. 插件扩展和市场\n"
                "5. 分布式计算支持\n\n"
                "如需帮助，请查看帮助文档。"
            )
        except Exception as e:
            logger.error(f"显示启动向导失败: {e}")
            QMessageBox.critical(self._main_window, "错误", f"显示启动向导失败: {e}")

    def _on_database_admin(self) -> None:
        """数据库管理"""
        try:
            logger.info("打开数据库管理界面")

            from gui.dialogs.data_management_dialog_unified import UnifiedDataManagementDialog

            dialog = UnifiedDataManagementDialog(self._main_window)
            self.center_dialog(dialog)
            dialog.exec_()

        except ImportError:
            QMessageBox.information(
                self._main_window,
                "数据库管理",
                "数据库管理功能包括：\n\n"
                "1. 数据库文件自动扫描和选择\n"
                "2. 数据表维护和查询\n"
                "3. 数据导入导出和批量操作\n"
                "4. 权限管理和云端同步\n"
                "5. 表结构管理和数据统计\n"
                "6. 慢SQL记录和性能监控\n\n"
                "数据库管理功能正在开发中..."
            )
        except Exception as e:
            logger.error(f"打开数据库管理失败: {e}")
            QMessageBox.critical(self._main_window, "错误", f"打开数据库管理失败: {e}")

    def _on_calculator(self) -> None:
        """打开计算器"""
        try:
            from gui.dialogs.calculator_dialog import CalculatorDialog

            dialog = CalculatorDialog(self._main_window)
            self.center_dialog(dialog)
            dialog.exec_()

        except Exception as e:
            logger.error(f"打开计算器失败: {e}")
            QMessageBox.critical(self._main_window, "错误", f"打开计算器失败: {e}")

    def _on_converter(self) -> None:
        """智能转换器选择 - 提供多种转换器选项"""
        try:
            # 创建转换器选择对话框
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel

            choice_dialog = QDialog(self._main_window)
            choice_dialog.setWindowTitle("选择转换器类型")
            choice_dialog.setModal(True)
            choice_dialog.resize(300, 200)

            layout = QVBoxLayout(choice_dialog)

            # 标题
            title_label = QLabel("请选择要使用的转换器类型：")
            title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px;")
            layout.addWidget(title_label)

            # 通用单位转换器按钮
            unit_btn = QPushButton("通用单位转换器")

            unit_btn.setToolTip("长度、重量、温度、面积等物理单位转换")
            unit_btn.clicked.connect(lambda: self._open_unit_converter(choice_dialog))
            layout.addWidget(unit_btn)

            # 汇率转换器按钮
            currency_btn = QPushButton("汇率转换器")

            currency_btn.setToolTip("主要货币之间的汇率转换")
            currency_btn.clicked.connect(lambda: self._open_currency_converter(choice_dialog))
            layout.addWidget(currency_btn)

            # 取消按钮
            cancel_btn = QPushButton("取消")
            cancel_btn.clicked.connect(choice_dialog.reject)
            layout.addWidget(cancel_btn)

            choice_dialog.exec_()

        except Exception as e:
            logger.error(f"打开转换器选择失败: {e}")
            # 降级到通用转换器
            try:
                from gui.dialogs.converter_dialog import ConverterDialog
                dialog = ConverterDialog(self._main_window)
                self.center_dialog(dialog)
                dialog.exec_()
            except Exception as e2:
                logger.error(f"打开通用转换器失败: {e2}")
                QMessageBox.critical(self._main_window, "错误", f"打开转换器失败: {e2}")

    def _open_unit_converter(self, parent_dialog):
        """打开通用单位转换器"""
        try:
            parent_dialog.accept()
            dialog = ConverterDialog(self._main_window)
            self.center_dialog(dialog)
            dialog.exec_()
            logger.info("打开通用单位转换器")
        except Exception as e:
            logger.error(f"打开通用单位转换器失败: {e}")
            QMessageBox.critical(self._main_window, "错误", f"打开通用单位转换器失败: {e}")

    def _open_currency_converter(self, parent_dialog):
        """打开汇率转换器"""
        try:
            parent_dialog.accept()
            from gui.tools.currency_converter import CurrencyConverter
            dialog = CurrencyConverter(self._main_window)
            self.center_dialog(dialog)
            dialog.exec_()
            logger.info("打开汇率转换器")
        except Exception as e:
            logger.error(f"打开汇率转换器失败: {e}")
            QMessageBox.critical(self._main_window, "错误", f"打开汇率转换器失败: {e}")

    def _on_commission_calculator(self) -> None:
        """打开费率计算器"""
        try:
            from gui.tools.commission_calculator import CommissionCalculator

            CommissionCalculator.show_calculator(self._main_window)

        except Exception as e:
            logger.error(f"打开费率计算器失败: {e}")
            QMessageBox.critical(self._main_window, "错误", f"打开费率计算器失败: {e}")

    def _on_currency_converter(self) -> None:
        """打开汇率转换器"""
        try:

            CurrencyConverter.show_converter(self._main_window)

        except Exception as e:
            logger.error(f"打开汇率转换器失败: {e}")
            QMessageBox.critical(self._main_window, "错误", f"打开汇率转换器失败: {e}")

    def _on_system_optimizer(self) -> None:
        """打开系统维护工具"""
        try:
            from gui.dialogs import show_system_optimizer_dialog
            show_system_optimizer_dialog(self._main_window)
        except Exception as e:
            logger.error(f"打开系统维护工具失败: {e}")
            QMessageBox.critical(self._main_window, "错误", f"打开系统维护工具失败: {e}")

    def _check_data_usage_terms(self) -> None:
        """检查数据使用条款"""
        try:
            from gui.dialogs import DataUsageManager

            # 创建数据使用管理器
            usage_manager = DataUsageManager()

            # 检查用户是否已同意条款
            if not usage_manager.check_and_request_agreement(self._main_window):
                # 用户不同意条款，显示警告并退出
                QMessageBox.warning(
                    self._main_window,
                    "使用条款",
                    "您必须同意数据使用条款才能使用FactorWeave-Quant 系统。\n程序将退出。"
                )
                # 延迟退出，让用户看到消息
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(2000, self._main_window.close)
            else:
                logger.info("用户已同意数据使用条款")

        except Exception as e:
            logger.error(f"检查数据使用条款失败: {e}")
            # 如果检查失败，显示默认条款
            try:
                from gui.dialogs import DataUsageTermsDialog
                DataUsageTermsDialog.show_terms(self._main_window)
            except Exception as e:
                logger.warning(f"显示数据使用条款对话框失败: {e}")

    def _on_show_data_usage_terms(self) -> None:
        """显示数据使用条款"""
        try:
            DataUsageTermsDialog.show_terms(self._main_window)
        except Exception as e:
            logger.error(f"Failed to show data usage terms: {e}")
            QMessageBox.critical(self._main_window, "错误",
                                 f"无法显示数据使用条款: {str(e)}")

    # _toggle_performance_panel 方法已删除 - 根据用户要求移除性能仪表板

    def _on_performance_center(self):
        """打开性能监控中心"""
        try:
            from gui.widgets.modern_performance_widget import show_modern_performance_monitor

            # 显示现代化性能监控界面
            performance_widget = show_modern_performance_monitor(self._main_window)

            if performance_widget is not None:
                performance_widget.setWindowTitle("FactorWeave-Quant 性能监控中心 - Professional Edition")
                performance_widget.show()
                logger.info("性能监控中心已打开")
            else:
                logger.error("性能监控中心创建失败，返回None")
                QMessageBox.warning(self._main_window, "错误", "无法创建性能监控中心窗口")

        except Exception as e:
            logger.error(f"打开性能监控中心失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法打开性能监控中心: {e}")

    def _on_system_performance(self):
        """显示系统性能监控"""
        try:
            from gui.widgets.modern_performance_widget import show_modern_performance_monitor
            performance_widget = show_modern_performance_monitor(self._main_window)

            if performance_widget is not None:
                performance_widget.tab_widget.setCurrentIndex(0)  # 切换到系统监控tab
                performance_widget.show()
            else:
                logger.error("系统性能监控窗口创建失败，返回None")
                QMessageBox.warning(self._main_window, "错误", "无法创建系统性能监控窗口")
            logger.info("系统性能监控已打开")
        except Exception as e:
            logger.error(f"打开系统性能监控失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法打开系统性能监控: {e}")

    def _on_ui_performance(self):
        """显示UI性能优化"""
        try:
            from gui.widgets.modern_performance_widget import show_modern_performance_monitor
            performance_widget = show_modern_performance_monitor(self._main_window)
            # 无独立UI优化tab，回退到系统监控tab（tab顺序: 0系统监控/1策略性能/2算法优化/3风险控制/4执行监控/5数据质量）
            performance_widget.tab_widget.setCurrentIndex(0)
            performance_widget.show()
            logger.info("UI性能优化已打开")
        except Exception as e:
            logger.error(f"打开UI性能优化失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法打开UI性能优化: {e}")

    def _on_strategy_performance(self):
        """显示策略性能监控"""
        try:
            from gui.widgets.modern_performance_widget import show_modern_performance_monitor
            performance_widget = show_modern_performance_monitor(self._main_window)
            performance_widget.tab_widget.setCurrentIndex(1)  # 切换到策略性能tab（index 1=策略性能）
            performance_widget.show()
            logger.info("策略性能监控已打开")
        except Exception as e:
            logger.error(f"打开策略性能监控失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法打开策略性能监控: {e}")

    def _on_algorithm_performance(self):
        """显示算法性能监控"""
        try:
            from gui.widgets.modern_performance_widget import show_modern_performance_monitor
            performance_widget = show_modern_performance_monitor(self._main_window)
            performance_widget.tab_widget.setCurrentIndex(2)  # 切换到算法性能tab（index 2=算法优化）
            performance_widget.show()
            logger.info("算法性能监控已打开")
        except Exception as e:
            logger.error(f"打开算法性能监控失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法打开算法性能监控: {e}")

    def _on_auto_tuning(self):
        """显示自动调优"""
        try:
            from gui.widgets.modern_performance_widget import show_modern_performance_monitor
            performance_widget = show_modern_performance_monitor(self._main_window)
            # 自动调优已合并入算法优化tab（index 2）
            performance_widget.tab_widget.setCurrentIndex(2)
            performance_widget.show()
            logger.info("自动调优已打开")
        except Exception as e:
            logger.error(f"打开自动调优失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法打开自动调优: {e}")

    def _on_performance_report(self):
        """生成性能报告"""
        try:
            from core.performance import get_performance_monitor
            from PyQt5.QtWidgets import QFileDialog

            monitor = get_performance_monitor()

            # 选择保存位置
            filepath, _ = QFileDialog.getSaveFileName(
                self._main_window,
                "导出性能报告",
                f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "JSON Files (*.json);;All Files (*)"
            )

            if filepath:
                report = monitor.export_report(filepath)
                QMessageBox.information(
                    self._main_window,
                    "成功",
                    f"性能报告已导出到:\n{filepath}"
                )
                logger.info(f"性能报告已导出: {filepath}")
        except Exception as e:
            logger.error(f"导出性能报告失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法导出性能报告: {e}")

    def _toggle_log_panel(self):
        """切换日志面板的显示/隐藏状态 - 代理到 PanelCoordinator"""
        if self._panel_coordinator:
            self._panel_coordinator.toggle_log_panel()

    def _set_all_tables_readonly(self):
        """设置所有表格为只读"""
        try:
            logger.info("设置所有表格为只读模式...")

            def set_tables_readonly(widget):
                from PyQt5.QtWidgets import QTableWidget, QTableView

                if isinstance(widget, QTableWidget):
                    widget.setEditTriggers(QTableWidget.NoEditTriggers)
                    logger.debug(f"设置 QTableWidget 为只读: {widget.objectName()}")
                elif isinstance(widget, QTableView):
                    widget.setEditTriggers(QTableView.NoEditTriggers)
                    logger.debug(f"设置 QTableView 为只读: {widget.objectName()}")

                for child in widget.findChildren(QWidget):
                    set_tables_readonly(child)

            set_tables_readonly(self._main_window)
            logger.info("所有表格已设置为只读模式")

        except Exception as e:
            logger.error(f"设置表格只读模式失败: {e}")

    def toggle_log_panel(self) -> None:
        """切换日志面板显示/隐藏 - 菜单专用版本 - 代理到 PanelCoordinator"""
        try:
            if self._panel_coordinator:
                self._panel_coordinator.toggle_log_panel()
        except Exception as e:
            logger.error(f"切换日志面板失败: {e}")

    def _on_optimization_status(self) -> None:
        """显示优化系统状态"""
        try:
            # 检查优化系统状态
            status_info = {
                "系统状态": "运行中",
                "活跃优化任务": 0,
                "已完成任务": 0,
                "系统健康度": "良好"
            }

            # 构建状态消息
            message = " 优化系统状态\n\n"
            for key, value in status_info.items():
                message += f" {key}: {value}\n"

            QMessageBox.information(self._main_window, "优化系统状态", message)
            logger.info("查看优化系统状态")

        except Exception as e:
            logger.error(f"获取优化状态失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法获取优化状态: {e}")

    def _on_create_strategy(self) -> None:
        """创建新策略"""
        try:
            # 使用已有的策略管理功能
            self._on_strategy_management()
            logger.info("打开策略创建功能")
        except Exception as e:
            logger.error(f"创建策略失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法创建策略: {e}")

    def _on_import_strategy(self) -> None:
        """导入策略"""
        try:
            from core.services.strategy_service import StrategyService

            file_path, _ = QFileDialog.getOpenFileName(
                self._main_window,
                "导入策略文件",
                "",
                "策略文件 (*.json);;所有文件 (*)"
            )
            if file_path:
                import json
                from datetime import datetime

                with open(file_path, 'r', encoding='utf-8') as f:
                    strategy_data = json.load(f)

                strategy_service = None
                try:
                    strategy_service = self.service_container.resolve(StrategyService)
                except Exception as e:
                    logger.warning(f"无法获取StrategyService: {e}")

                if strategy_service is None:
                    QMessageBox.warning(self._main_window, "错误", "策略服务不可用")
                    return

                strategy_id = strategy_data.get('strategy_id')
                plugin_type = strategy_data.get('plugin_type')
                parameters = strategy_data.get('parameters', {})
                metadata = strategy_data.get('metadata', {})

                if not strategy_id or not plugin_type:
                    QMessageBox.warning(self._main_window, "错误", "策略文件格式错误，缺少必要字段")
                    return

                strategy_config = strategy_service.create_strategy_config(
                    strategy_id=strategy_id,
                    plugin_type=plugin_type,
                    parameters=parameters,
                    metadata=metadata
                )

                if strategy_config:
                    QMessageBox.information(self._main_window, "成功", f"策略导入成功: {strategy_id}")
                    logger.info(f"策略导入成功: {file_path} -> {strategy_id}")
                else:
                    QMessageBox.warning(self._main_window, "错误", "策略导入失败")

        except json.JSONDecodeError as e:
            logger.error(f"策略文件JSON解析失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"策略文件格式错误: {e}")
        except Exception as e:
            logger.error(f"导入策略失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法导入策略: {e}")

    def _on_export_strategy(self) -> None:
        """导出策略"""
        try:
            from core.services.strategy_service import StrategyService

            strategy_service = None
            try:
                strategy_service = self.service_container.resolve(StrategyService)
            except Exception as e:
                logger.warning(f"无法获取StrategyService: {e}")

            if strategy_service is None:
                QMessageBox.warning(self._main_window, "错误", "策略服务不可用")
                return

            all_configs = strategy_service.get_all_strategy_configs()

            if not all_configs:
                QMessageBox.information(self._main_window, "提示", "没有可导出的策略")
                return

            strategy_list = []
            for config in all_configs:
                strategy_list.append({
                    'strategy_id': config.strategy_id,
                    'plugin_type': config.plugin_type,
                    'parameters': config.parameters,
                    'metadata': config.metadata,
                    'enabled': config.enabled,
                    'created_at': config.created_at.isoformat() if config.created_at else None,
                    'updated_at': config.updated_at.isoformat() if config.updated_at else None
                })

            file_path, _ = QFileDialog.getSaveFileName(
                self._main_window,
                "导出策略文件",
                "",
                "策略文件 (*.json);;所有文件 (*)"
            )
            if file_path:
                import json

                export_data = {
                    'version': '1.0',
                    'export_time': datetime.now().isoformat(),
                    'strategies': strategy_list
                }

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)

                QMessageBox.information(self._main_window, "成功", f"策略导出成功，共导出{len(strategy_list)}个策略")
                logger.info(f"策略导出成功: {file_path}, 导出数量: {len(strategy_list)}")

        except Exception as e:
            logger.error(f"导出策略失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法导出策略: {e}")

    def _on_strategy_backtest(self) -> None:
        """策略回测"""
        try:
            # 使用增强版策略管理对话框V2（包含完整回测功能）
            try:
                from gui.dialogs.strategy_manager_dialog import StrategyManagerDialog
                dialog = StrategyManagerDialog(self._main_window)
                # 直接切换到回测视图
                if hasattr(dialog, 'current_view'):
                    dialog.current_view = 'backtest'
                    dialog._switch_view('backtest')
                dialog.exec_()
                logger.info("启动增强版策略回测对话框V2")
            except ImportError as e:
                logger.error(f"增强版策略回测V2不可用: {e}")
                QMessageBox.warning(self._main_window, "错误", f"策略回测功能不可用: {e}")
        except Exception as e:
            logger.error(f"策略回测失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法启动策略回测: {e}")

    def _on_strategy_optimize(self) -> None:
        """策略优化 - 打开独立参数编辑器对话框"""
        try:
            from gui.widgets.parameter_editor import ParameterEditorWidget
            from core.strategy.strategy_engine import get_strategy_engine
            from core.trading.trading_mode import ModeContext, TradingMode
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QComboBox, QLabel, QHBoxLayout, QMessageBox
            from PyQt5.QtCore import Qt

            # 创建独立对话框
            dialog = QDialog(self._main_window)
            dialog.setWindowTitle("⚡ 策略参数优化")
            dialog.resize(800, 900)
            dialog.setMinimumSize(700, 600)

            # 主布局
            main_layout = QVBoxLayout(dialog)

            # 策略选择区域
            strategy_selection_widget = QWidget()
            strategy_selection_layout = QHBoxLayout(strategy_selection_widget)
            strategy_selection_layout.setContentsMargins(0, 0, 0, 0)

            strategy_label = QLabel("选择策略:")
            strategy_label.setStyleSheet("font-weight: bold; font-size: 12px;")
            strategy_selection_layout.addWidget(strategy_label)

            strategy_combo = QComboBox()
            strategy_combo.setMinimumWidth(300)
            strategy_selection_layout.addWidget(strategy_combo)
            strategy_selection_layout.addStretch()

            # 加载策略列表
            try:
                strategy_engine = get_strategy_engine()
                strategies = strategy_engine.get_available_strategies()
                for strategy in strategies:
                    strategy_combo.addItem(strategy['name'], strategy['id'])
            except Exception as e:
                logger.warning(f"加载策略列表失败，使用默认列表: {e}")
                # 添加默认策略
                default_strategies = ["MA策略", "MACD策略", "RSI策略", "KDJ策略", "布林带策略"]
                for i, name in enumerate(default_strategies):
                    strategy_combo.addItem(name, f"strategy_{i}")

            main_layout.addWidget(strategy_selection_widget)

            # 创建参数编辑器
            parameter_editor = ParameterEditorWidget(parent=dialog)
            main_layout.addWidget(parameter_editor)

            # 策略选择变化时加载参数
            current_strategy = None

            def load_strategy_parameters():
                nonlocal current_strategy
                strategy_name = strategy_combo.currentText()
                strategy_id = strategy_combo.currentData()

                try:
                    strategy_engine = get_strategy_engine()
                    strategy = strategy_engine.get_strategy_instance(strategy_name)

                    # 创建 mode_context
                    mode_context = ModeContext.create_backtest()
                    strategy.set_mode_context(mode_context)

                    # 更新参数编辑器
                    parameter_editor.strategy = strategy
                    parameter_editor.mode_context = mode_context

                    # 重新加载参数 UI
                    parameter_editor._load_strategy_parameters()

                    current_strategy = strategy
                    logger.info(f"已加载策略参数: {strategy_name}")

                except Exception as e:
                    logger.error(f"加载策略参数失败: {e}")

            # 连接信号
            strategy_combo.currentIndexChanged.connect(load_strategy_parameters)

            # 初始加载
            if strategy_combo.count() > 0:
                load_strategy_parameters()

            # 添加底部按钮
            button_layout = QHBoxLayout()
            button_layout.addStretch()

            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.close)
            button_layout.addWidget(close_btn)

            main_layout.addLayout(button_layout)

            # 显示对话框
            dialog.exec_()

            logger.info("策略参数优化对话框已关闭")

        except ImportError as e:
            logger.error(f"参数优化组件不可用: {e}")
            QMessageBox.warning(self._main_window, "错误", f"参数优化功能不可用: {e}")
        except Exception as e:
            logger.error(f"策略优化失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法打开参数优化: {e}")

    def _on_import_data(self) -> None:
        """导入数据"""
        try:
            from core.services.database_service import DatabaseService
            import pandas as pd

            file_path, _ = QFileDialog.getOpenFileName(
                self._main_window,
                "导入数据文件",
                "",
                "数据文件 (*.csv *.xlsx);;所有文件 (*)"
            )
            if file_path:
                db_service = None
                try:
                    db_service = self.service_container.resolve(DatabaseService)
                except Exception as e:
                    logger.warning(f"无法获取DatabaseService: {e}")

                try:
                    table_name = "imported_data"

                    if file_path.endswith('.csv'):
                        if db_service:
                            csv_cols = pd.read_csv(file_path, nrows=0).columns.tolist()
                            for col in csv_cols:
                                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', str(col)):
                                    raise ValueError(f"无效列名: {col}")
                            with db_service.get_connection("analytics_duckdb") as conn:
                                safe_path = file_path.replace("'", "''")
                                conn.execute(f"""
                                    CREATE OR REPLACE TABLE {table_name} AS
                                    SELECT row_number() OVER () - 1 AS idx, *
                                    FROM read_csv_auto('{safe_path}', header=true, all_varchar=false)
                                """)
                                result = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table_name}")
                                row_count = result[0]['cnt'] if result else 0
                                cols_result = conn.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table_name}'")
                                columns = [r['column_name'] for r in cols_result] if cols_result else []
                            QMessageBox.information(self._main_window, "成功", f"数据导入成功: {row_count}行")
                            logger.info(f"数据导入成功: {file_path}, {row_count}行, 列: {columns}")
                        else:
                            df = pd.read_csv(file_path)
                            QMessageBox.information(self._main_window, "提示", f"数据加载成功: {len(df)}行，但数据库服务不可用")
                    elif file_path.endswith('.xlsx'):
                        df = pd.read_excel(file_path)
                        columns = df.columns.tolist()
                        for col in columns:
                            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', str(col)):
                                raise ValueError(f"无效列名: {col}")
                        logger.info(f"导入数据: {file_path}, 行数: {len(df)}, 列: {columns}")

                        if db_service:
                            with db_service.get_connection("analytics_duckdb") as conn:
                                conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (idx INTEGER)")
                                for col in columns:
                                    col_safe = col.replace(' ', '_').replace('(', '').replace(')', '').replace('"', '""')
                                    try:
                                        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS \"{col_safe}\" TEXT")
                                    except Exception as e:
                                        logger.debug(f"添加列失败: {e}")

                                # 批量插入: register DataFrame + 单条 INSERT ... SELECT
                                conn.register('_import_temp', df)
                                col_names = ', '.join(f'"{col}"' for col in df.columns)
                                conn.execute(f"INSERT INTO {table_name} ({col_names}) SELECT {col_names} FROM _import_temp")
                                conn.unregister('_import_temp')

                            QMessageBox.information(self._main_window, "成功", f"数据导入成功: {len(df)}行")
                            logger.info(f"数据导入成功: {file_path}, {len(df)}行")
                        else:
                            QMessageBox.information(self._main_window, "提示", f"数据加载成功: {len(df)}行，但数据库服务不可用")
                    else:
                        QMessageBox.warning(self._main_window, "错误", "不支持的文件格式")
                        return

                except Exception as e:
                    logger.error(f"数据导入失败: {e}")
                    QMessageBox.warning(self._main_window, "错误", f"数据导入失败: {e}")

        except Exception as e:
            logger.error(f"导入数据失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法导入数据: {e}")

    def _on_data_quality_check(self) -> None:
        """数据质量检查"""
        try:
            # 使用已有的数据质量检查功能
            self._on_single_stock_quality_check()
            logger.info("启动数据质量检查")
        except Exception as e:
            logger.error(f"数据质量检查失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法启动数据质量检查: {e}")

    def _on_data_management_center(self) -> None:
        """打开数据管理中心"""
        try:
            from gui.dialogs.data_management_dialog_unified import UnifiedDataManagementDialog

            # 检查是否已经打开了数据管理中心
            if hasattr(self, '_data_management_dialog') and self._data_management_dialog:
                # 如果已经存在，就激活窗口
                self._data_management_dialog.raise_()
                self._data_management_dialog.activateWindow()
                return

            # 创建数据管理中心对话框
            self._data_management_dialog = UnifiedDataManagementDialog(self._main_window)

            # R244 修复: UnifiedDataManagementDialog 只有 data_imported/data_exported/
            # database_updated 信号(data_management_dialog_unified.py L197-199)，
            # 原 data_downloaded/source_configured 信号已不存在，删除无效连接。

            # 显示对话框
            self._data_management_dialog.show()

            logger.info("数据管理中心已打开")

        except Exception as e:
            logger.error(f"打开数据管理中心失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法打开数据管理中心: {e}")

    def _on_data_downloaded_from_center(self, symbol: str, source: str):
        """处理从数据管理中心下载的数据"""
        try:
            logger.info(f"数据下载完成: {symbol} (来源: {source})")
            # 可以在这里添加数据下载后的处理逻辑
            # 比如刷新图表、更新状态等
        except Exception as e:
            logger.error(f"处理下载数据失败: {e}")

    def _on_source_configured_from_center(self, source_name: str, config: dict):
        """处理从数据管理中心配置的数据源"""
        try:
            logger.info(f"数据源配置更新: {source_name}")
            # 可以在这里添加数据源配置更新后的处理逻辑
        except Exception as e:
            logger.error(f"处理数据源配置失败: {e}")

    # ==================== DuckDB专业数据导入功能 ====================

    def _on_duckdb_import(self) -> None:
        """打开DuckDB专业数据导入界面（重定向到增强版）"""
        try:
            # 重定向到增强版数据导入系统
            from gui.enhanced_data_import_launcher import EnhancedDataImportMainWindow

            # 创建增强版数据导入窗口
            self.enhanced_import_window = EnhancedDataImportMainWindow()
            self.enhanced_import_window.show()

            logger.info("打开增强版DuckDB专业数据导入系统")

        except ImportError as e:
            QMessageBox.warning(
                self._main_window,
                "功能不可用",
                f"增强版数据导入UI组件加载失败:\n{str(e)}\n\n请确保所有依赖项已正确安装。"
            )
            logger.error(f"增强版数据导入UI组件加载失败: {e}")

        except Exception as e:
            QMessageBox.critical(
                self._main_window,
                "错误",
                f"启动增强版数据导入系统失败:\n{str(e)}"
            )
            logger.error(f"启动增强版数据导入系统失败: {e}")

    def _on_enhanced_import(self) -> None:
        """打开增强版数据导入系统"""
        try:
            # 启动增强版数据导入系统
            from gui.enhanced_data_import_launcher import EnhancedDataImportMainWindow

            # 创建增强版数据导入窗口
            self.enhanced_import_window = EnhancedDataImportMainWindow()
            self.enhanced_import_window.show()

            logger.info("启动增强版数据导入系统")

        except ImportError as e:
            QMessageBox.warning(
                self._main_window,
                "功能不可用",
                f"增强版数据导入UI组件加载失败:\n{str(e)}\n\n请确保所有依赖项已正确安装。"
            )
            logger.error(f"增强版数据导入UI组件加载失败: {e}")

        except Exception as e:
            QMessageBox.critical(
                self._main_window,
                "错误",
                f"启动增强版数据导入系统失败:\n{str(e)}"
            )
            logger.error(f"启动增强版数据导入系统失败: {e}")

    def _on_batch_import(self) -> None:
        """批量数据导入（重定向到增强版任务管理）"""
        try:
            # 批量导入功能已集成到增强版数据导入系统的任务管理中
            from gui.enhanced_data_import_launcher import EnhancedDataImportMainWindow

            # 创建增强版数据导入窗口
            self.enhanced_import_window = EnhancedDataImportMainWindow()
            self.enhanced_import_window.show()

            # 提示用户使用任务管理功能
            QMessageBox.information(
                self._main_window,
                "功能整合",
                "批量导入功能已整合到增强版数据导入系统的任务管理中。\n\n请使用'任务管理'选项卡进行批量任务创建和管理。"
            )

            logger.info("重定向到增强版数据导入系统的任务管理功能")

        except Exception as e:
            logger.error(f"启动增强版数据导入系统失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法启动增强版数据导入系统: {e}")

    def _on_scheduled_import(self) -> None:
        """定时导入任务管理"""
        try:
            from gui.dialogs.scheduled_task_dialog import ScheduledTaskDialog
            from core.importdata.import_config_manager import ImportConfigManager

            config_manager = ImportConfigManager()
            dialog = ScheduledTaskDialog(
                config_manager=config_manager,
                parent=self._main_window
            )
            self.center_dialog(dialog)
            dialog.exec_()

            logger.info("打开定时任务配置对话框")

        except ImportError as e:
            logger.error(f"导入定时任务对话框失败: {e}")
            QMessageBox.information(self._main_window, "提示", "定时任务配置功能不可用")
        except Exception as e:
            logger.error(f"打开定时任务配置失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法打开定时任务配置: {e}")

    def _on_import_history(self) -> None:
        """查看导入历史记录"""
        try:
            from gui.dialogs.data_management_dialog_unified import UnifiedDataManagementDialog

            dialog = UnifiedDataManagementDialog(self._main_window)
            self.center_dialog(dialog)
            dialog.exec_()

            logger.info("查看导入历史记录")

        except ImportError:
            # 如果对话框不存在，显示开发中提示
            QMessageBox.information(self._main_window, "提示", "导入历史记录功能正在开发中")
            logger.info("导入历史记录功能正在开发中")
        except Exception as e:
            logger.error(f"查看导入历史记录失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法查看导入历史记录: {e}")

    def _on_export_data(self) -> None:
        """导出数据"""
        try:
            from gui.dialogs.data_management_dialog_unified import UnifiedDataManagementDialog

            # R244 修复: 原 _manage_dialog 方法不存在(data_management_dialog_unified.py 已提供
            # 统一对话框)，改为直接创建并显示，与 _on_database_admin 保持一致
            dialog = UnifiedDataManagementDialog(self._main_window)
            self.center_dialog(dialog)
            dialog.show()
            logger.info("启动数据导出")

        except ImportError:
            # 如果对话框不存在，使用简单的文件保存对话框
            file_path, _ = QFileDialog.getSaveFileName(
                self._main_window,
                "导出数据",
                "",
                "CSV文件 (*.csv);;Excel文件 (*.xlsx);;JSON文件 (*.json);;所有文件 (*)"
            )
            if file_path:
                QMessageBox.information(self._main_window, "提示", "数据导出功能正在开发中")
                logger.info(f"导出数据到: {file_path}")
        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法导出数据: {e}")

    def _on_check_update(self) -> None:
        """检查更新"""
        try:
            # R245: 实现版本比对（本地 v2.0 vs GitHub releases 最新版），断网时优雅降级
            local_version = "2.0"
            remote_url = "https://api.github.com/repos/factorweave/FactorWeave-Quant/releases/latest"
            try:
                import requests
                resp = requests.get(remote_url, timeout=5)
                resp.raise_for_status()
                remote_version = (resp.json().get("tag_name") or "").lstrip("v")
            except Exception as e:
                logger.warning(f"检查更新网络请求失败（降级提示）: {e}")
                QMessageBox.information(
                    self._main_window,
                    "检查更新",
                    f"当前版本: FactorWeave-Quant  v{local_version}\n\n暂无法连接更新服务器，请稍后重试。"
                )
                return

            if remote_version and remote_version != local_version:
                QMessageBox.information(
                    self._main_window,
                    "检查更新",
                    f"发现新版本: v{remote_version}（当前 v{local_version}）\n\n请访问项目页面获取最新版本。"
                )
            else:
                QMessageBox.information(
                    self._main_window,
                    "检查更新",
                    f"当前已是最新版本: v{local_version}"
                )
            logger.info("检查软件更新")
        except Exception as e:
            logger.error(f"检查更新失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法检查更新: {e}")

    def _on_theme_changed(self, theme_name: str) -> None:
        """切换主题（统一入口，R244 修复: 委托 ThemeManager.set_theme）"""
        try:
            from utils.theme import get_theme_manager
            theme_manager = self._theme_manager if hasattr(self, '_theme_manager') and self._theme_manager else get_theme_manager()
            if theme_manager is None:
                raise RuntimeError("ThemeManager 不可用")
            if hasattr(theme_manager, 'set_theme'):
                theme_manager.set_theme(theme_name)
            elif hasattr(theme_manager, 'apply_theme'):
                theme_manager.apply_theme(theme_name)
            else:
                raise RuntimeError("ThemeManager 缺少 set_theme/apply_theme 方法")
            logger.info(f"主题已切换: {theme_name}")
        except Exception as e:
            logger.error(f"切换主题失败: {e}")
            raise

    def _on_default_theme(self) -> None:
        """切换到默认主题"""
        try:
            self._on_theme_changed('default')
            logger.info("切换到默认主题")
        except Exception as e:
            logger.error(f"切换默认主题失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法切换主题: {e}")

    def _on_light_theme(self) -> None:
        """切换到浅色主题"""
        try:
            self._on_theme_changed('light')
            logger.info("切换到浅色主题")
        except Exception as e:
            logger.error(f"切换浅色主题失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法切换主题: {e}")

    def _on_dark_theme(self) -> None:
        """切换到深色主题"""
        try:
            self._on_theme_changed('dark')
            logger.info("切换到深色主题")
        except Exception as e:
            logger.error(f"切换深色主题失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法切换主题: {e}")

    def _on_analyze(self) -> None:
        """启动分析功能"""
        try:
            # 检查是否有分析面板
            if hasattr(self, '_analysis_widget') and self._analysis_widget:
                self._analysis_widget.refresh_current_tab()
                logger.info("启动分析功能")
            else:
                # R244 备注: 项目存在真实分析面板 AnalysisWidget（gui/widgets/analysis_widget.py L91），
                # 但其中模块级导入链包含 xtquant/XTP（已实测触发 0xC0000005 进程崩溃，R241 环境预存问题），
                # 在环境问题解决前保持安全降级，避免挂载后崩溃。挂载方案列入高价值待开发清单。
                QMessageBox.information(
                    self._main_window,
                    "分析功能",
                    "分析功能模块加载受限（依赖环境问题未解决），敬请期待！"
                )
        except Exception as e:
            logger.error(f"启动分析失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法启动分析: {e}")

    def _on_backtest(self) -> None:
        """智能启动回测功能 - 根据当前活跃标签页启动相应回测"""
        try:
            # 优先检查分析widget是否存在且有当前标签
            if hasattr(self, '_analysis_widget') and self._analysis_widget:
                current_tab = self._analysis_widget.currentWidget()
                if current_tab and hasattr(current_tab, 'start_backtest'):
                    # 如果当前标签页有start_backtest方法，直接调用
                    current_tab.start_backtest()
                    logger.info(f"从{current_tab.__class__.__name__}启动回测功能")
                    return

            # 检查是否有专门的回测面板
            if hasattr(self, '_backtest_widget') and self._backtest_widget:
                # 创建默认回测参数
                default_params = {
                    'professional_level': 'PROFESSIONAL',
                    'engine_type': 'unified',
                    'use_vectorized_engine': True,
                    'auto_select_engine': True,
                    'monitoring_level': 'STANDARD'
                }
                self._backtest_widget.start_backtest(default_params)
                logger.info("从专用回测面板启动回测功能")
                return

            # 检查是否有形态分析标签页
            if hasattr(self, '_analysis_widget') and self._analysis_widget:
                # 尝试获取形态分析标签页
                for i in range(self._analysis_widget.count()):
                    tab = self._analysis_widget.widget(i)
                    if tab and hasattr(tab, 'start_backtest'):
                        tab_name = self._analysis_widget.tabText(i)
                        if '形态' in tab_name or 'pattern' in tab_name.lower():
                            self._analysis_widget.setCurrentIndex(i)
                            tab.start_backtest()
                            logger.info(f"切换到{tab_name}标签页并启动回测")
                            return

                # 如果找到任何有回测功能的标签页，使用第一个
                for i in range(self._analysis_widget.count()):
                    tab = self._analysis_widget.widget(i)
                    if tab and hasattr(tab, 'start_backtest'):
                        self._analysis_widget.setCurrentIndex(i)
                        tab.start_backtest()
                        tab_name = self._analysis_widget.tabText(i)
                        logger.info(f"切换到{tab_name}标签页并启动回测")
                        return

            # 如果没有找到任何回测功能，提供选择
            reply = QMessageBox.question(
                self._main_window,
                "智能回测选择",
                "未找到当前活跃的回测界面。\n\n请选择回测方式：\n\n• 是：打开专业回测功能\n• 否：打开策略回测功能",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                # 启动专业回测功能
                self._on_professional_backtest()
            elif reply == QMessageBox.No:
                # 启动策略回测功能（原策略菜单功能）
                self._on_strategy_backtest()
            # Cancel 则不执行任何操作

            logger.info("智能回测：用户选择了回测方式")

        except Exception as e:
            logger.error(f"启动回测失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法启动回测: {e}")

    def _on_professional_backtest(self) -> None:
        """启动专业回测功能（直接打开独立浮动窗口）"""
        try:
            # 直接创建独立浮动窗口，支持放大缩小和关闭
            self._create_standalone_backtest_window()
            logger.info("专业回测独立窗口已启动")

        except Exception as e:
            logger.error(f"启动专业回测功能失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法启动专业回测功能: {e}")

    def _create_standalone_backtest_window(self) -> None:
        """创建独立的专业回测浮动窗口（支持放大缩小和关闭）"""
        try:
            from gui.widgets.backtest_widget import ProfessionalBacktestWidget
            from PyQt5.QtWidgets import QMainWindow
            from PyQt5.QtCore import Qt
            from PyQt5.QtGui import QIcon

            # 检查是否已有独立窗口存在
            if hasattr(self, '_standalone_backtest_window') and self._standalone_backtest_window:
                # 检查 Qt 对象是否有效
                try:
                    # 尝试访问窗口属性，验证对象是否有效
                    if self._standalone_backtest_window.isVisible() or self._standalone_backtest_window.isHidden():
                        self._standalone_backtest_window.show()
                        self._standalone_backtest_window.raise_()
                        self._standalone_backtest_window.activateWindow()
                        logger.info("专业回测独立窗口已激活")
                        return
                except RuntimeError as e:
                    # Qt 对象已删除，清理引用
                    logger.warning(f"检测到已删除的窗口引用，将创建新窗口：{e}")
                    try:
                        del self._standalone_backtest_window
                    except Exception as e:
                        logger.debug(f"清理旧窗口引用失败: {e}")

            # 创建新的独立浮动窗口
            self._standalone_backtest_window = QMainWindow()

            # 设置窗口标题和图标
            self._standalone_backtest_window.setWindowTitle("FactorWeave-Quant 专业回测系统")

            # 设置窗口大小和位置（居中显示）
            screen = QApplication.desktop().screenGeometry()
            window_width = 1400
            window_height = 900
            x = (screen.width() - window_width) // 2
            y = (screen.height() - window_height) // 2
            self._standalone_backtest_window.setGeometry(x, y, window_width, window_height)

            # 设置最小窗口大小
            self._standalone_backtest_window.setMinimumSize(1000, 800)

            # 设置窗口标志，支持放大缩小和关闭
            self._standalone_backtest_window.setWindowFlags(
                Qt.Window |                    # 独立窗口
                Qt.WindowTitleHint |          # 显示标题栏
                Qt.WindowSystemMenuHint |     # 显示系统菜单
                Qt.WindowMinimizeButtonHint |  # 显示最小化按钮
                Qt.WindowMaximizeButtonHint |  # 显示最大化按钮
                Qt.WindowCloseButtonHint      # 显示关闭按钮
            )

            # 创建专业回测组件
            backtest_widget = ProfessionalBacktestWidget(parent=self._standalone_backtest_window)
            self._standalone_backtest_window.setCentralWidget(backtest_widget)

            # 设置窗口样式
            self._standalone_backtest_window.setStyleSheet("""
                QMainWindow {
                    background-color: #0e1117;
                    color: white;
                }
            """)

            # 设置窗口属性：关闭时删除窗口
            self._standalone_backtest_window.setAttribute(Qt.WA_DeleteOnClose, True)

            # 连接关闭事件
            def on_window_close():
                try:
                    if hasattr(self, '_standalone_backtest_window') and self._standalone_backtest_window:
                        backtest_widget = self._standalone_backtest_window.centralWidget()
                        if backtest_widget and hasattr(backtest_widget, '_cleanup_before_close'):
                            backtest_widget._cleanup_before_close()
                except Exception as e:
                    logger.error(f"关闭时清理回测窗口失败：{e}")
                finally:
                    # 确保总是删除引用
                    if hasattr(self, '_standalone_backtest_window'):
                        try:
                            del self._standalone_backtest_window
                        except Exception as e:
                            logger.debug(f"删除独立回测窗口引用失败: {e}")
                    logger.info("专业回测独立窗口已关闭并清理")

            # 重写关闭事件：允许窗口正常关闭（WA_DeleteOnClose 会处理删除）
            def close_event(event):
                logger.info("专业回测独立窗口收到关闭事件")
                on_window_close()  # 执行清理操作
                event.accept()  # 接受关闭事件，让 Qt 正常关闭窗口
            self._standalone_backtest_window.closeEvent = close_event

            # 显示窗口
            self._standalone_backtest_window.show()
            self._standalone_backtest_window.raise_()
            self._standalone_backtest_window.activateWindow()

            logger.info("专业回测独立浮动窗口创建成功")

        except Exception as e:
            logger.error(f"创建独立回测窗口失败: {e}")
            QMessageBox.critical(self._main_window, "错误", f"无法创建专业回测窗口: {e}")

    def _on_toggle_backtest_panel(self) -> None:
        """切换专业回测面板的显示/隐藏 - 代理到 PanelCoordinator"""
        try:
            if self._panel_coordinator:
                self._panel_coordinator.toggle_backtest_panel()
        except Exception as e:
            logger.error(f"切换专业回测面板失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法切换专业回测面板: {e}")

    def _on_optimize(self) -> None:
        """启动优化功能"""
        try:
            # 使用已有的优化功能
            self._on_one_click_optimization()
            logger.info("启动优化功能")
        except Exception as e:
            logger.error(f"启动优化失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法启动优化: {e}")

    def analyze_current_stock(self) -> None:
        """分析当前股票（ToolBar委托）"""
        self._on_analyze()

    def show_analysis(self) -> None:
        """显示分析面板（ToolBar委托）"""
        self._on_analyze()

    def run_backtest(self) -> None:
        """运行回测（ToolBar委托）"""
        self._on_backtest()

    def show_backtest(self) -> None:
        """显示回测面板（ToolBar委托）"""
        self._on_backtest()

    def optimize_strategy(self) -> None:
        """优化策略（ToolBar委托）"""
        self._on_optimize()

    def show_optimization(self) -> None:
        """显示优化面板（ToolBar委托）"""
        self._on_optimize()

    def search_stock(self, query: str) -> None:
        """搜索股票（ToolBar委托）"""
        self._search_stock(query)

    def on_search(self, query: str) -> None:
        """搜索股票（ToolBar委托别名）"""
        self._search_stock(query)

    def _search_stock(self, query: str) -> None:
        """内部搜索股票实现"""
        try:
            if query and query.strip():
                self.event_bus.publish(StockSelectedEvent(
                    symbol=query.strip(),
                    source="toolbar_search"
                ))
                logger.info(f"搜索股票: {query}")
        except Exception as e:
            logger.error(f"搜索股票失败: {e}")

    def _on_gpu_config(self) -> None:
        """配置GPU加速"""
        try:
            from gui.dialogs.settings_dialog import SettingsDialog
            
            # 使用ThemeManager
            theme_manager = self._theme_manager
            
            # 打开设置对话框并跳转到GPU配置标签页（索引3）
            dialog = SettingsDialog(
                parent=self._main_window,
                theme_manager=theme_manager,
                config_service=self.service_container.get_service(ConfigService),
                initial_tab_index=3  # GPU配置标签页
            )
            dialog.exec_()
            logger.info("打开GPU配置")
        except Exception as e:
            logger.error(f"打开GPU配置失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法打开GPU配置: {e}")

    def _on_save_as_file(self) -> None:
        """另存为文件"""
        try:
            QMessageBox.information(
                self._main_window,
                "另存为",
                "另存为功能正在开发中，敬请期待！"
            )
            logger.info("执行另存为功能")
        except Exception as e:
            logger.error(f"另存为失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法另存为: {e}")

    def _on_close_file(self) -> None:
        """关闭文件"""
        try:
            QMessageBox.information(
                self._main_window,
                "关闭文件",
                "关闭文件功能正在开发中，敬请期待！"
            )
            logger.info("执行关闭文件功能")
        except Exception as e:
            logger.error(f"关闭文件失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法关闭文件: {e}")

    def _on_cut(self) -> None:
        """剪切操作"""
        try:
            # 尝试获取当前焦点的widget并执行剪切
            focused_widget = self._main_window.focusWidget()
            if focused_widget and hasattr(focused_widget, 'cut'):
                focused_widget.cut()
                logger.info("执行剪切操作")
            else:
                QMessageBox.information(
                    self._main_window,
                    "剪切",
                    "当前焦点不支持剪切操作"
                )
        except Exception as e:
            logger.error(f"剪切操作失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法执行剪切: {e}")

    def _on_select_all(self) -> None:
        """全选操作"""
        try:
            # 尝试获取当前焦点的widget并执行全选
            focused_widget = self._main_window.focusWidget()
            if focused_widget and hasattr(focused_widget, 'selectAll'):
                focused_widget.selectAll()
                logger.info("执行全选操作")
            else:
                QMessageBox.information(
                    self._main_window,
                    "全选",
                    "当前焦点不支持全选操作"
                )
        except Exception as e:
            logger.error(f"全选操作失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法执行全选: {e}")

    def _on_find(self) -> None:
        """查找功能"""
        try:
            QMessageBox.information(
                self._main_window,
                "查找",
                "查找功能正在开发中，敬请期待！"
            )
            logger.info("执行查找功能")
        except Exception as e:
            logger.error(f"查找功能失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法执行查找: {e}")

    def _on_replace(self) -> None:
        """替换功能"""
        try:
            QMessageBox.information(
                self._main_window,
                "替换",
                "替换功能正在开发中，敬请期待！"
            )
            logger.info("执行替换功能")
        except Exception as e:
            logger.error(f"替换功能失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法执行替换: {e}")

    def _on_zoom_in(self) -> None:
        """放大显示"""
        try:
            QMessageBox.information(
                self._main_window,
                "放大显示",
                "放大显示功能正在开发中，敬请期待！"
            )
            logger.info("执行放大显示")
        except Exception as e:
            logger.error(f"放大显示失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法放大显示: {e}")

    def _on_zoom_out(self) -> None:
        """缩小显示"""
        try:
            QMessageBox.information(
                self._main_window,
                "缩小显示",
                "缩小显示功能正在开发中，敬请期待！"
            )
            logger.info("执行缩小显示")
        except Exception as e:
            logger.error(f"缩小显示失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法缩小显示: {e}")

    def _on_fullscreen(self) -> None:
        """全屏模式切换"""
        try:
            if self._main_window.isFullScreen():
                self._main_window.showNormal()
                logger.info("退出全屏模式")
            else:
                self._main_window.showFullScreen()
                logger.info("进入全屏模式")
        except Exception as e:
            logger.error(f"全屏模式切换失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法切换全屏模式: {e}")

    def _on_update_data(self) -> None:
        """更新数据"""
        try:
            QMessageBox.information(
                self._main_window,
                "更新数据",
                "数据更新功能正在开发中，敬请期待！"
            )
            logger.info("执行数据更新")
        except Exception as e:
            logger.error(f"数据更新失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法更新数据: {e}")

    def _on_risk_calculator(self) -> None:
        """风险计算器"""
        try:
            QMessageBox.information(
                self._main_window,
                "风险计算器",
                "风险计算器功能正在开发中，敬请期待！"
            )
            logger.info("打开风险计算器")
        except Exception as e:
            logger.error(f"风险计算器失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法打开风险计算器: {e}")

    def _on_distributed_computing(self) -> None:
        """分布式计算"""
        try:
            QMessageBox.information(
                self._main_window,
                "分布式计算",
                "分布式计算功能正在开发中，敬请期待！"
            )
            logger.info("启动分布式计算")
        except Exception as e:
            logger.error(f"分布式计算失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法启动分布式计算: {e}")

    def _on_log_viewer(self) -> None:
        """日志查看器"""
        try:
            QMessageBox.information(
                self._main_window,
                "日志查看器",
                "日志查看器功能正在开发中，敬请期待！"
            )
            logger.info("打开日志查看器")
        except Exception as e:
            logger.error(f"日志查看器失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法打开日志查看器: {e}")

    def _on_memory_usage(self) -> None:
        """内存使用情况"""
        try:
            import psutil
            memory_info = psutil.virtual_memory()
            message = f""" 内存使用情况

 总内存: {memory_info.total / (1024**3):.1f} GB
 已使用: {memory_info.used / (1024**3):.1f} GB
 可用内存: {memory_info.available / (1024**3):.1f} GB
 使用率: {memory_info.percent:.1f}%
"""
            QMessageBox.information(self._main_window, "内存使用情况", message)
            logger.info("查看内存使用情况")
        except ImportError:
            QMessageBox.information(
                self._main_window,
                "内存使用情况",
                "内存监控功能需要安装psutil库"
            )
        except Exception as e:
            logger.error(f"查看内存使用失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法查看内存使用: {e}")

    def _on_user_manual(self) -> None:
        """用户手册"""
        try:
            from gui.dialogs.help_viewer_dialog import HelpViewerDialog
            from pathlib import Path
            project_root = Path(__file__).resolve().parents[2]
            dialog = HelpViewerDialog(
                self._main_window,
                title="用户手册",
                md_path=str(project_root / "回测UI详细使用说明.md"),
            )
            self.center_dialog(dialog)
            dialog.exec_()
            logger.info("打开用户手册")
        except Exception as e:
            logger.error(f"用户手册失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法打开用户手册: {e}")

    def _on_data_usage_terms(self) -> None:
        """数据使用条款"""
        try:
            from gui.dialogs import DataUsageTermsDialog
            DataUsageTermsDialog.show_terms(self._main_window)
            logger.info("查看数据使用条款")
        except Exception as e:
            logger.error(f"数据使用条款失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法查看数据使用条款: {e}")

    def _on_toggle_toolbar(self, checked=None) -> None:
        """切换工具栏显示/隐藏"""
        try:
            toolbar = self._main_window.toolBar()
            if toolbar:
                if checked is not None:
                    # 从复选框菜单项调用，使用传入的状态
                    toolbar.setVisible(checked)
                    logger.info(f"工具栏已{'显示' if checked else '隐藏'}")
                else:
                    # 直接调用，切换当前状态
                    is_visible = toolbar.isVisible()
                    toolbar.setVisible(not is_visible)
                    logger.info(f"工具栏已{'隐藏' if is_visible else '显示'}")
            else:
                logger.warning("工具栏不存在")
        except Exception as e:
            logger.error(f"切换工具栏失败: {e}")

    def _on_toggle_statusbar(self, checked=None) -> None:
        """切换状态栏显示/隐藏"""
        try:
            statusbar = self._main_window.statusBar()
            if statusbar:
                if checked is not None:
                    # 从复选框菜单项调用，使用传入的状态
                    statusbar.setVisible(checked)
                    logger.info(f"状态栏已{'显示' if checked else '隐藏'}")
                else:
                    # 直接调用，切换当前状态
                    is_visible = statusbar.isVisible()
                    statusbar.setVisible(not is_visible)
                    logger.info(f"状态栏已{'隐藏' if is_visible else '显示'}")
            else:
                logger.warning("状态栏不存在")
        except Exception as e:
            logger.error(f"切换状态栏失败: {e}")

    def toolBar(self):
        """获取工具栏 - 兼容方法"""
        return self._main_window.toolBar() if self._main_window else None

    def statusBar(self):
        """获取状态栏 - 兼容方法"""
        return self._main_window.statusBar() if self._main_window else None

    def _initialize_realtime_components(self):
        """初始化实时数据组件"""
        try:
            from core.services.enhanced_realtime_data_manager import EnhancedRealtimeDataManager
            from core.services.realtime_compute_engine import RealtimeComputeEngine
            from core.data_standardization_engine import DataStandardizationEngine
            from core.data_validator import DataValidator

            logger.info("开始初始化实时数据组件...")

            # 创建实时计算引擎（初始化已在构造函数中完成）
            self._realtime_compute_engine = RealtimeComputeEngine(self._event_bus)
            logger.info("RealtimeComputeEngine 初始化完成")

            # 获取数据标准器和验证器
            try:
                data_standardizer = DataStandardizationEngine()
                data_validator = DataValidator()
            except Exception as e:
                logger.warning(f"创建数据标准器/验证器失败，使用默认实现: {e}")
                data_standardizer = None
                data_validator = None

            # 创建实时数据管理器
            self._realtime_manager = EnhancedRealtimeDataManager(
                event_bus=self._event_bus,
                data_standardizer=data_standardizer,
                data_validator=data_validator,
                uni_plugin_manager=self._data_manager._uni_plugin_manager if hasattr(self._data_manager, '_uni_plugin_manager') else None
            )
            logger.info("EnhancedRealtimeDataManager 初始化完成")

            # 注册所有实时数据插件到实时数据管理器（同步方式，避免 Qt 事件循环冲突）
            if hasattr(self._data_manager, '_uni_plugin_manager'):
                plugin_center = self._data_manager._uni_plugin_manager.plugin_center
                
                # 定义需要注册的实时数据插件列表
                realtime_plugin_ids = [
                    'data_sources.stock.miniqmt_plugin',      # MiniQMT 实时数据
                    'data_sources.stock.level2_realtime_plugin'  # Level-2 实时数据
                ]
                
                for plugin_id in realtime_plugin_ids:
                    if plugin_id in plugin_center.data_source_plugins:
                        try:
                            # 同步方式注册插件，确保注册完成后才继续
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                # Qt 事件循环运行时，使用 run_until_complete 同步等待注册完成
                                # 这是安全的，因为 register_realtime_plugin 是轻量级操作
                                import concurrent.futures
                                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                                    future = executor.submit(
                                        loop.run_until_complete,
                                        self._realtime_manager.register_realtime_plugin(
                                            plugin_id,
                                            plugin_center.data_source_plugins[plugin_id]
                                        )
                                    )
                                    try:
                                        future.result(timeout=5.0)  # 5 秒超时
                                        logger.info(f"实时数据插件 {plugin_id} 已同步注册到实时数据管理器")
                                    except concurrent.futures.TimeoutError:
                                        logger.error(f"实时数据插件 {plugin_id} 注册超时")
                            else:
                                loop.run_until_complete(self._realtime_manager.register_realtime_plugin(
                                    plugin_id,
                                    plugin_center.data_source_plugins[plugin_id]
                                ))
                                logger.info(f"实时数据插件 {plugin_id} 已注册到实时数据管理器")
                        except Exception as e:
                            logger.error(f"实时数据插件 {plugin_id} 注册失败：{e}")
                            # 同步注册失败时，直接添加到插件字典
                            self._realtime_manager.realtime_plugins[plugin_id] = plugin_center.data_source_plugins[plugin_id]
                            logger.info(f"实时数据插件 {plugin_id} 已强制同步注册到实时数据管理器")
                    else:
                        logger.info(f"实时数据插件 {plugin_id} 未在 plugin_center 中发现，可能未启用")

            logger.info("实时数据组件初始化完成")

        except Exception as e:
            logger.error(f"初始化实时数据组件失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self._realtime_manager = None
            self._realtime_compute_engine = None

    def _initialize_enhanced_ui_components_async(self):
        """异步初始化增强UI组件（在事件循环中执行，避免阻塞主初始化流程）"""
        import time
        start_time = time.time()

        try:
            logger.info("开始异步初始化增强UI组件...")

            # 导入增强UI组件
            import_start = time.time()
            from gui.widgets.enhanced_ui import (
                Level2DataPanel, OrderBookWidget, FundamentalAnalysisTab, SmartRecommendationPanel
            )
            # 导入AI选股面板
            try:
                from components.ai_stock_selection import AIStockSelectionPanel
                AI_STOCK_AVAILABLE = True
            except ImportError as e:
                logger.warning(f"无法导入AIStockSelectionPanel: {e}")
                AI_STOCK_AVAILABLE = False
            import_time = time.time() - import_start
            logger.info(f"模块导入耗时: {import_time:.3f}秒")

            # 存储增强组件引用
            self._enhanced_components = {}

            # 初始化实时数据组件
            self._initialize_realtime_components()

            # 创建Level-2数据面板
            level2_start = time.time()
            self._enhanced_components['level2_panel'] = Level2DataPanel(
                parent=self._main_window,
                event_bus=self._event_bus,
                realtime_manager=self._realtime_manager
            )
            level2_time = time.time() - level2_start
            logger.info(f"Level2DataPanel创建耗时: {level2_time:.3f}秒")

            # 创建订单簿组件
            orderbook_start = time.time()
            self._enhanced_components['order_book_widget'] = OrderBookWidget(
                parent=self._main_window,
                event_bus=self._event_bus
            )
            orderbook_time = time.time() - orderbook_start
            logger.info(f"OrderBookWidget创建耗时: {orderbook_time:.3f}秒")

            # 创建基本面分析标签页
            fundamental_start = time.time()
            self._enhanced_components['fundamental_analysis_tab'] = FundamentalAnalysisTab(
                parent=self._main_window
            )
            fundamental_time = time.time() - fundamental_start
            logger.info(f"FundamentalAnalysisTab创建耗时: {fundamental_time:.3f}秒")

            # 创建智能推荐面板
            recommendation_start = time.time()
            try:
                from core.containers import get_service_container
                from core.services.recommendation_model_trainer import RecommendationModelTrainer
                from core.services.smart_recommendation_engine import SmartRecommendationEngine
                
                container = get_service_container()
                recommendation_engine = None
                model_trainer = None
                
                try:
                    recommendation_engine = container.resolve(SmartRecommendationEngine)
                except Exception:
                    logger.warning("无法获取SmartRecommendationEngine服务")
                
                try:
                    model_trainer = container.resolve(RecommendationModelTrainer)
                except Exception:
                    logger.warning("无法获取RecommendationModelTrainer服务")
                
                self._enhanced_components['smart_recommendation_panel'] = SmartRecommendationPanel(
                    parent=self._main_window,
                    recommendation_engine=recommendation_engine,
                    model_trainer=model_trainer
                )
            except Exception as e:
                logger.error(f"创建SmartRecommendationPanel时出错: {e}")
                logger.error(traceback.format_exc())
                self._enhanced_components['smart_recommendation_panel'] = SmartRecommendationPanel(
                    parent=self._main_window
                )
            recommendation_time = time.time() - recommendation_start
            logger.info(f"SmartRecommendationPanel创建耗时: {recommendation_time:.3f}秒")

            # 创建AI选股面板
            if AI_STOCK_AVAILABLE:
                ai_stock_start = time.time()
                self._enhanced_components['ai_stock_selection'] = AIStockSelectionPanel(
                    parent=self._main_window
                )
                ai_stock_time = time.time() - ai_stock_start
                logger.info(f"AIStockSelectionPanel创建耗时: {ai_stock_time:.3f}秒")

            # 集成增强组件到UI
            integration_start = time.time()
            self._integrate_enhanced_components_to_ui()
            integration_time = time.time() - integration_start
            logger.info(f"增强组件UI集成耗时: {integration_time:.3f}秒")

            total_time = time.time() - start_time
            logger.info(f"成功异步初始化 {len(self._enhanced_components)} 个增强UI组件, 总耗时: {total_time:.3f}秒")

        except Exception as e:
            logger.error(f"异步初始化增强UI组件失败: {e}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            self._enhanced_components = {}

    def _initialize_enhanced_ui_components(self):
        """初始化增强UI组件（同步版本，保留用于向后兼容）"""
        # 重定向到异步版本
        self._initialize_enhanced_ui_components_async()

    def _integrate_enhanced_components_to_ui(self):
        """将增强组件集成到UI中"""
        import time
        start_time = time.time()

        try:
            if not hasattr(self, '_enhanced_components') or not self._enhanced_components:
                logger.warning("增强组件未初始化，跳过UI集成")
                return

            logger.info("开始集成增强UI组件到主界面...")

            # 修复：将技术分析面板与增强组件组合在一起，默认在右侧
            # 首先创建技术分析面板的 QDockWidget（如果尚未创建）
            right_dock = None
            if 'right_dock' in self._panels:
                right_dock = self._panels['right_dock']
                logger.info("技术分析面板 QDockWidget 已存在")
            else:
                logger.warning("技术分析面板 QDockWidget 未找到，跳过组合")

            # 修复：存储所有需要组合到右侧的 QDockWidget
            right_area_docks = []

            # 将技术分析面板作为第一个（如果存在）
            if right_dock:
                right_area_docks.append(right_dock)
                logger.info("技术分析面板已添加到右侧组合列表")

            # 修复：将所有增强组件组合到右侧，与技术分析面板形成标签页组
            # 添加Level-2数据面板作为停靠窗口（组合到右侧）
            if 'level2_panel' in self._enhanced_components:
                level2_dock = QDockWidget("Level-2 数据", self._main_window)
                level2_dock.setWidget(self._enhanced_components['level2_panel'])
                level2_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
                # 修复：如果已有技术分析面板，直接组合；否则先添加到右侧
                if right_area_docks:
                    # 技术分析面板已存在，直接组合
                    self._main_window.tabifyDockWidget(right_area_docks[0], level2_dock)
                    right_area_docks.append(level2_dock)
                    logger.info("Level-2数据面板已与技术分析面板组合为标签页（右侧）")
                else:
                    # 技术分析面板不存在，先添加到右侧
                    self._main_window.addDockWidget(Qt.RightDockWidgetArea, level2_dock)
                    right_area_docks.append(level2_dock)
                    logger.info("Level-2数据面板已添加到右侧停靠区域")

            # 添加订单簿组件作为停靠窗口（组合到右侧）
            if 'order_book_widget' in self._enhanced_components:
                orderbook_dock = QDockWidget("订单簿深度", self._main_window)
                orderbook_dock.setWidget(self._enhanced_components['order_book_widget'])
                orderbook_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
                # 修复：组合到右侧（与技术分析面板或Level-2面板组合）
                if right_area_docks:
                    # 已有其他面板在右侧，直接组合
                    self._main_window.tabifyDockWidget(right_area_docks[0], orderbook_dock)
                    right_area_docks.append(orderbook_dock)
                    logger.info("订单簿组件已与其他面板组合为标签页（右侧）")
                else:
                    # 没有其他面板，先添加到右侧
                    self._main_window.addDockWidget(Qt.RightDockWidgetArea, orderbook_dock)
                    right_area_docks.append(orderbook_dock)
                    logger.info("订单簿组件已添加到右侧停靠区域")

            # 添加智能推荐面板作为停靠窗口（组合到右侧）
            if 'smart_recommendation_panel' in self._enhanced_components:
                recommendation_dock = QDockWidget("智能推荐", self._main_window)
                recommendation_dock.setWidget(self._enhanced_components['smart_recommendation_panel'])
                recommendation_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
                # 修复：组合到右侧（与技术分析面板或其他面板组合）
                if right_area_docks:
                    # 已有其他面板在右侧，直接组合
                    self._main_window.tabifyDockWidget(right_area_docks[0], recommendation_dock)
                    right_area_docks.append(recommendation_dock)
                    logger.info("智能推荐面板已与其他面板组合为标签页（右侧）")
                else:
                    # 没有其他面板，先添加到右侧
                    self._main_window.addDockWidget(Qt.RightDockWidgetArea, recommendation_dock)
                    right_area_docks.append(recommendation_dock)
                    logger.info("智能推荐面板已添加到右侧停靠区域")

            # 添加增强AI选股面板作为停靠窗口（组合到右侧）
            if 'ai_stock_selection' in self._enhanced_components:
                ai_stock_dock = QDockWidget("增强AI选股", self._main_window)
                ai_stock_dock.setWidget(self._enhanced_components['ai_stock_selection'])
                ai_stock_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
                # 修复：组合到右侧（与技术分析面板或其他面板组合）
                if right_area_docks:
                    # 已有其他面板在右侧，直接组合
                    self._main_window.tabifyDockWidget(right_area_docks[0], ai_stock_dock)
                    right_area_docks.append(ai_stock_dock)
                    logger.info("增强AI选股面板已与其他面板组合为标签页（右侧）")
                else:
                    # 没有其他面板，先添加到右侧
                    self._main_window.addDockWidget(Qt.RightDockWidgetArea, ai_stock_dock)
                    right_area_docks.append(ai_stock_dock)
                    logger.info("增强AI选股面板已添加到右侧停靠区域")

            # 修复：将所有右侧组合的 QDockWidget 的标签页位置设置为顶部
            if right_area_docks:
                # 确保第一个 dock（技术分析面板）可见并激活
                right_area_docks[0].setVisible(True)
                right_area_docks[0].raise_()
                logger.info(f"所有右侧 QDockWidget 已组合在一起（共{len(right_area_docks)}个面板）")

            # 修复：存储底部区域的 QDockWidget（用于标签页位置设置）
            bottom_area_docks = []

            # 修复：将所有组合的 QDockWidget 的标签页位置设置为顶部
            # 注意：对于 QDockWidget 组合后的标签页，需要通过查找 QTabBar 来设置位置
            all_docks = right_area_docks + bottom_area_docks
            if all_docks:
                # 查找所有 QTabBar 并设置标签页位置为顶部
                from PyQt5.QtWidgets import QTabBar
                tab_bars = self._main_window.findChildren(QTabBar)
                for tab_bar in tab_bars:
                    # QTabBar.RoundedNorth 表示标签页在顶部（圆角，顶部）
                    # 注意：需要检查 tab_bar 是否属于 QDockWidget 的标签页
                    try:
                        tab_bar.setShape(QTabBar.RoundedNorth)
                        logger.debug(f"已将标签页位置设置为顶部: {tab_bar}")
                    except Exception as e:
                        logger.warning(f"设置标签页位置失败: {e}")

                logger.info(f"所有 QDockWidget 的标签页位置已设置为顶部（右侧{len(right_area_docks)}个，底部{len(bottom_area_docks)}个）")

            # 如果存在分析标签页，将基本面分析添加到其中
            if hasattr(self, '_analysis_tabs') and 'fundamental_analysis_tab' in self._enhanced_components:
                self._analysis_tabs.addTab(
                    self._enhanced_components['fundamental_analysis_tab'],
                    " 基本面分析"
                )
                logger.info("基本面分析标签页已添加到分析区域")

            total_time = time.time() - start_time
            logger.info(f"增强UI组件集成完成, 耗时: {total_time:.3f}秒")

        except Exception as e:
            logger.error(f"集成增强UI组件失败: {e}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")

    def get_enhanced_component(self, component_name: str):
        """获取增强组件实例"""
        if hasattr(self, '_enhanced_components'):
            return self._enhanced_components.get(component_name)
        return None

    # ==================== 增强功能菜单事件处理 ====================

    def _on_toggle_level2_panel(self):
        """切换Level-2数据面板显示/隐藏 - 代理到 PanelCoordinator"""
        try:
            if self._panel_coordinator:
                self._panel_coordinator.toggle_level2_panel()
        except Exception as e:
            logger.error(f"切换Level-2数据面板失败: {e}")

    def _on_toggle_orderbook_panel(self):
        """切换订单簿面板显示/隐藏 - 代理到 PanelCoordinator"""
        try:
            if self._panel_coordinator:
                self._panel_coordinator.toggle_orderbook_panel()
        except Exception as e:
            logger.error(f"切换订单簿面板失败: {e}")

    def _on_toggle_fundamental_panel(self):
        """切换基本面分析面板显示/隐藏 - 代理到 PanelCoordinator"""
        try:
            if self._panel_coordinator:
                self._panel_coordinator.toggle_fundamental_panel()
        except Exception as e:
            logger.error(f"切换基本面分析面板失败: {e}")

    def _on_toggle_smart_recommendation_panel(self):
        """切换智能推荐面板显示/隐藏 - 代理到 PanelCoordinator"""
        try:
            if self._panel_coordinator:
                self._panel_coordinator.toggle_smart_recommendation_panel()
        except Exception as e:
            logger.error(f"切换智能推荐面板失败: {e}")

    def _update_responsive_layout(self):
        """更新响应式布局 - 代理到 PanelCoordinator"""
        try:
            if self._panel_coordinator:
                self._panel_coordinator.update_responsive_layout()
            else:
                logger.warning("PanelCoordinator 未初始化，无法更新响应式布局")
        except Exception as e:
            logger.error(f"更新响应式布局失败: {e}")
