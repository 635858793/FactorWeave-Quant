"""
面板协调器

负责管理主窗口的所有UI面板，包括面板创建、布局管理、显示/隐藏控制、
数据刷新和面板间的协调。

从 MainWindowCoordinator 提取，遵循单一职责原则。
"""

from loguru import logger
from typing import Dict, Any, Optional, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QDockWidget,
    QSizePolicy, QMessageBox
)
from PyQt5.QtCore import Qt

from core.coordinators.base_coordinator import BaseCoordinator
from core.containers import ServiceContainer
from core.events import EventBus

if TYPE_CHECKING:
    from core.coordinators.main_window_coordinator import MainWindowCoordinator


class PanelCoordinator(BaseCoordinator):
    """
    面板协调器

    负责：
    1. 创建和管理所有UI面板（左侧、中间、右侧、底部）
    2. 面板布局管理（分割器、尺寸比例）
    3. 面板显示/隐藏控制
    4. 面板数据刷新
    5. 面板间的信号连接和协调
    6. 响应式布局更新
    7. 面板主题变更通知

    设计原则：
    - 单一职责：只负责面板管理
    - 依赖注入：通过构造函数接收 main_window_coordinator
    - 接口清晰：提供 initialize_panels() 和 get_panel() 等统一接口
    """

    def __init__(self,
                 main_window_coordinator: 'MainWindowCoordinator',
                 service_container: ServiceContainer,
                 event_bus: EventBus):
        """
        初始化面板协调器

        Args:
            main_window_coordinator: 主窗口协调器实例
            service_container: 服务容器
            event_bus: 事件总线
        """
        super().__init__(service_container, event_bus)

        self._main_window_coordinator = main_window_coordinator
        self._main_window = main_window_coordinator.get_main_window()
        self._panels: Dict[str, Any] = {}

        self._layout_config = {
            'left_panel_width': 300,
            'right_panel_width': 350,
            'bottom_panel_height': 200,
        }

        self._backtest_widget = None
        self._backtest_dock = None

    @property
    def main_window(self):
        """获取主窗口实例"""
        return self._main_window

    def get_panel(self, panel_name: str) -> Optional[QWidget]:
        """
        获取面板实例

        Args:
            panel_name: 面板名称（'left', 'middle', 'right', 'bottom', 'backtest' 等）

        Returns:
            面板实例或None
        """
        return self._panels.get(panel_name)

    def get_all_panels(self) -> Dict[str, Any]:
        """获取所有面板字典"""
        return self._panels.copy()

    def initialize_panels(self) -> None:
        """
        统一初始化所有面板

        按照顺序：创建面板 -> 设置布局 -> 连接信号
        """
        self._create_panels()
        self._connect_panel_signals()
        logger.info("All UI panels initialized successfully")

    def _create_panels(self) -> None:
        """创建所有UI面板"""
        try:
            central_widget = QWidget()
            self._main_window.setCentralWidget(central_widget)

            main_layout = QVBoxLayout(central_widget)
            main_layout.setContentsMargins(5, 5, 5, 5)
            main_layout.setSpacing(5)

            vertical_splitter = QSplitter(Qt.Vertical)
            main_layout.addWidget(vertical_splitter)

            horizontal_splitter = QSplitter(Qt.Horizontal)
            vertical_splitter.addWidget(horizontal_splitter)

            from core.ui.panels.left_panel import LeftPanel
            from core.ui.panels.middle_panel import MiddlePanel
            from core.ui.panels.right_panel import RightPanel

            stock_service = self._main_window_coordinator._stock_service
            data_manager = self._main_window_coordinator._data_manager

            left_panel = LeftPanel(
                stock_service=stock_service,
                data_manager=data_manager,
                parent=self._main_window,
                coordinator=self._main_window_coordinator
            )
            left_panel._root_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            horizontal_splitter.addWidget(left_panel._root_frame)
            self._panels['left'] = left_panel

            middle_panel = MiddlePanel(
                parent=self._main_window,
                coordinator=self._main_window_coordinator
            )
            middle_panel._root_frame.setMinimumWidth(800)
            middle_panel._root_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            horizontal_splitter.addWidget(middle_panel._root_frame)
            self._panels['middle'] = middle_panel

            right_panel = RightPanel(
                parent=self._main_window,
                coordinator=self._main_window_coordinator,
                width=self._layout_config['right_panel_width']
            )

            right_dock = QDockWidget("技术分析", self._main_window)
            right_dock.setWidget(right_panel._root_frame)
            right_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
            right_dock.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            self._main_window.addDockWidget(Qt.RightDockWidgetArea, right_dock)

            self._panels['right'] = right_panel
            self._panels['right_dock'] = right_dock
            logger.info("右侧技术分析面板已创建为 QDockWidget")

            horizontal_splitter.setSizes([250, 1200])

            from core.ui.panels.bottom_panel import BottomPanel
            bottom_panel = BottomPanel(
                parent=self._main_window,
                coordinator=self._main_window_coordinator
            )
            vertical_splitter.addWidget(bottom_panel._root_frame)
            self._panels['bottom'] = bottom_panel

            vertical_splitter.setSizes([700, 200])

            self._create_professional_backtest_widget()

            logger.info("All UI panels and components created successfully")

        except Exception as e:
            logger.error(f"Failed to create UI panels: {e}")
            raise

    def _create_professional_backtest_widget(self) -> None:
        """创建专业回测组件作为停靠窗口"""
        try:
            from gui.widgets.backtest_widget import ProfessionalBacktestWidget

            self._backtest_widget = ProfessionalBacktestWidget(parent=self._main_window)

            backtest_dock = QDockWidget("专业回测系统", self._main_window)
            backtest_dock.setWidget(self._backtest_widget)
            backtest_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
            self._main_window.addDockWidget(Qt.RightDockWidgetArea, backtest_dock)
            backtest_dock.hide()

            self._panels['backtest_dock'] = backtest_dock
            self._panels['backtest'] = self._backtest_widget

            self._backtest_widget.error_occurred.connect(self._on_backtest_error)
            self._backtest_widget.backtest_completed.connect(self._on_backtest_completed)

            logger.info("专业回测组件创建成功")

        except Exception as e:
            logger.error(f"创建专业回测组件失败: {e}")
            self._backtest_widget = None

    def _connect_panel_signals(self) -> None:
        """连接面板间的信号"""
        try:
            bottom_panel = self._panels.get('bottom')
            if bottom_panel and hasattr(bottom_panel, 'panel_hidden'):
                bottom_panel.panel_hidden.connect(self._on_bottom_panel_hidden)

            logger.debug("Panel signals connected successfully")

        except Exception as e:
            logger.error(f"Failed to connect panel signals: {e}")
            raise

    def _on_bottom_panel_hidden(self) -> None:
        """处理底部面板隐藏事件"""
        try:
            central_widget = self._main_window.centralWidget()
            if not central_widget:
                return

            vertical_splitter = None
            for child in central_widget.children():
                if isinstance(child, QSplitter) and child.orientation() == Qt.Vertical:
                    vertical_splitter = child
                    break

            if vertical_splitter:
                sizes = vertical_splitter.sizes()
                if len(sizes) >= 2:
                    bottom_panel = self._panels.get('bottom')
                    bottom_height = 30 if bottom_panel else 0
                    new_sizes = [sizes[0] + sizes[1] - bottom_height, bottom_height]
                    vertical_splitter.setSizes(new_sizes)
                    logger.debug(f"调整垂直分割器大小: {sizes} -> {new_sizes}")

            self._update_bottom_panel_menu_item(False)

        except Exception as e:
            logger.error(f"处理底部面板隐藏事件失败: {e}")

    def _update_bottom_panel_menu_item(self, is_visible: bool) -> None:
        """更新底部面板菜单项"""
        try:
            menu_bar = self._main_window.menuBar()
            view_menu = None
            for action in menu_bar.actions():
                if action.text() == '视图(&V)':
                    view_menu = action.menu()
                    break

            if view_menu:
                bottom_panel_action = None
                for action in view_menu.actions():
                    if action.text() == '显示日志面板':
                        bottom_panel_action = action
                        break

                if not bottom_panel_action and not is_visible:
                    bottom_panel_action = view_menu.addAction('显示日志面板')
                    bottom_panel_action.triggered.connect(self._show_bottom_panel)
                elif bottom_panel_action and is_visible:
                    view_menu.removeAction(bottom_panel_action)

        except Exception as e:
            logger.error(f"更新底部面板菜单项失败: {e}")

    def _show_bottom_panel(self) -> None:
        """显示底部面板"""
        try:
            bottom_panel = self._panels.get('bottom')
            if bottom_panel:
                if hasattr(bottom_panel, '_show_panel'):
                    bottom_panel._show_panel()
                elif hasattr(bottom_panel, '_root_frame'):
                    bottom_panel._root_frame.setVisible(True)

            central_widget = self._main_window.centralWidget()
            if not central_widget:
                return

            vertical_splitter = None
            for child in central_widget.children():
                if isinstance(child, QSplitter) and child.orientation() == Qt.Vertical:
                    vertical_splitter = child
                    break

            if vertical_splitter:
                sizes = vertical_splitter.sizes()
                if len(sizes) >= 2:
                    total_height = sum(sizes)
                    new_sizes = [int(total_height * 0.8), int(total_height * 0.2)]
                    vertical_splitter.setSizes(new_sizes)
                    logger.debug(f"调整垂直分割器大小: {sizes} -> {new_sizes}")

            self._update_bottom_panel_menu_item(True)

        except Exception as e:
            logger.error(f"显示底部面板失败: {e}")

    def _notify_panels_theme_change(self) -> None:
        """通知所有面板主题变化（用于JSON主题）"""
        try:
            for panel_name, panel in self._panels.items():
                try:
                    if hasattr(panel, '_on_theme_changed'):
                        from utils.theme import get_theme_manager
                        theme_manager = get_theme_manager()
                        panel._on_theme_changed(theme_manager.current_theme)
                    elif hasattr(panel, 'update_theme'):
                        panel.update_theme()

                    if hasattr(panel, 'update'):
                        panel.update()

                except Exception as e:
                    logger.warning(f"Panel {panel_name} theme update failed: {e}")

            logger.info("Notified all panels of theme change")

        except Exception as e:
            logger.error(f"Failed to notify panels: {e}")

    def toggle_log_panel(self) -> None:
        """切换日志面板显示/隐藏"""
        try:
            bottom_panel = self._panels.get('bottom')
            if bottom_panel:
                if hasattr(bottom_panel, '_toggle_panel'):
                    bottom_panel._toggle_panel()
                elif hasattr(bottom_panel, '_root_frame'):
                    is_visible = bottom_panel._root_frame.isVisible()
                    bottom_panel._root_frame.setVisible(not is_visible)
                    if not is_visible:
                        if hasattr(bottom_panel, 'on_show'):
                            bottom_panel.on_show()
                    else:
                        if hasattr(bottom_panel, 'on_hide'):
                            bottom_panel.on_hide()

        except Exception as e:
            logger.error(f"切换日志面板失败: {e}")

    def toggle_backtest_panel(self) -> None:
        """切换专业回测面板的显示/隐藏"""
        try:
            backtest_dock = self._panels.get('backtest_dock')
            if backtest_dock:
                if backtest_dock.isVisible():
                    backtest_dock.hide()
                    logger.info("专业回测面板已隐藏")
                else:
                    backtest_dock.show()
                    backtest_dock.raise_()
                    logger.info("专业回测面板已显示")
            else:
                self._create_professional_backtest_widget()
                backtest_dock = self._panels.get('backtest_dock')
                if backtest_dock:
                    backtest_dock.show()
                    backtest_dock.raise_()
                    logger.info("专业回测面板已创建并显示")

        except Exception as e:
            logger.error(f"切换专业回测面板失败: {e}")
            QMessageBox.warning(self._main_window, "错误", f"无法切换专业回测面板: {e}")

    def _on_backtest_error(self, error_msg: str):
        """处理回测错误信号"""
        try:
            logger.error(f"回测错误: {error_msg}")
            QMessageBox.warning(self._main_window, "回测错误", error_msg)
        except Exception as e:
            logger.error(f"处理回测错误信号失败: {e}")

    def _on_backtest_completed(self, results: dict):
        """处理回测完成信号"""
        try:
            total_return = results.get('total_return', 0)
            trade_count = results.get('trade_count', 0)
            logger.info(f"回测已完成: 收益率={total_return:.2%}, 交易次数={trade_count}")
        except Exception as e:
            logger.error(f"处理回测完成信号失败: {e}")

    def toggle_level2_panel(self) -> None:
        """切换Level-2数据面板显示/隐藏"""
        try:
            dock_widgets = self._main_window.findChildren(QDockWidget)
            for dock in dock_widgets:
                if dock.windowTitle() == "Level-2 数据":
                    dock.setVisible(not dock.isVisible())
                    logger.info(f"Level-2数据面板已{'显示' if dock.isVisible() else '隐藏'}")
                    return
            logger.warning("Level-2数据面板未找到")
        except Exception as e:
            logger.error(f"切换Level-2数据面板失败: {e}")

    def toggle_orderbook_panel(self) -> None:
        """切换订单簿面板显示/隐藏"""
        try:
            dock_widgets = self._main_window.findChildren(QDockWidget)
            for dock in dock_widgets:
                if dock.windowTitle() == "订单簿深度":
                    dock.setVisible(not dock.isVisible())
                    logger.info(f"订单簿面板已{'显示' if dock.isVisible() else '隐藏'}")
                    return
            logger.warning("订单簿面板未找到")
        except Exception as e:
            logger.error(f"切换订单簿面板失败: {e}")

    def toggle_fundamental_panel(self) -> None:
        """切换基本面分析面板显示/隐藏"""
        try:
            if hasattr(self._main_window_coordinator, '_analysis_tabs'):
                analysis_tabs = self._main_window_coordinator._analysis_tabs
                for i in range(analysis_tabs.count()):
                    if analysis_tabs.tabText(i) == " 基本面分析":
                        analysis_tabs.setCurrentIndex(i)
                        logger.info("基本面分析标签页已激活")
                        return
            logger.warning("基本面分析标签页未找到")
        except Exception as e:
            logger.error(f"切换基本面分析面板失败: {e}")

    def toggle_smart_recommendation_panel(self) -> None:
        """切换智能推荐面板显示/隐藏"""
        try:
            dock_widgets = self._main_window.findChildren(QDockWidget)
            for dock in dock_widgets:
                if dock.windowTitle() == "智能推荐":
                    dock.setVisible(not dock.isVisible())
                    logger.info(f"智能推荐面板已{'显示' if dock.isVisible() else '隐藏'}")
                    return
            logger.warning("智能推荐面板未找到")
        except Exception as e:
            logger.error(f"切换智能推荐面板失败: {e}")

    def update_responsive_layout(self) -> None:
        """更新响应式布局"""
        try:
            if not self._main_window:
                return

            window_width = self._main_window.width()
            window_height = self._main_window.height()

            logger.debug(f"PanelCoordinator 响应式布局更新: {window_width}x{window_height}")

            if hasattr(self._main_window_coordinator, '_data_time_label'):
                label_width = max(120, int(window_width * 0.1))
                self._main_window_coordinator._data_time_label.setMinimumWidth(label_width)
                self._main_window_coordinator._data_time_label.setMaximumWidth(int(window_width * 0.15))

            if hasattr(self._main_window_coordinator, '_log_toggle_btn'):
                btn_width = max(70, int(window_width * 0.06))
                self._main_window_coordinator._log_toggle_btn.setMinimumWidth(btn_width)
                self._main_window_coordinator._log_toggle_btn.setMaximumWidth(int(window_width * 0.1))

            if 'left' in self._panels:
                left_panel = self._panels['left']
                if hasattr(left_panel, '_root_frame'):
                    panel_width = max(200, int(window_width * 0.2))
                    left_panel._root_frame.setMinimumWidth(panel_width)
                    left_panel._root_frame.setMaximumWidth(int(window_width * 0.3))

            if 'middle' in self._panels:
                middle_panel = self._panels['middle']
                if hasattr(middle_panel, '_root_frame'):
                    panel_width = max(500, int(window_width * 0.4))
                    middle_panel._root_frame.setMinimumWidth(panel_width)

        except Exception as e:
            logger.error(f"更新响应式布局失败: {e}")

    def refresh_panel_data(self, panel_name: str) -> None:
        """
        刷新指定面板的数据

        Args:
            panel_name: 面板名称
        """
        try:
            panel = self._panels.get(panel_name)
            if panel and hasattr(panel, '_on_refresh_clicked'):
                panel._on_refresh_clicked()
                logger.info(f"面板 {panel_name} 数据已刷新")
            else:
                logger.warning(f"面板 {panel_name} 不支持刷新或不存在")
        except Exception as e:
            logger.error(f"刷新面板 {panel_name} 数据失败: {e}")

    def get_layout_config(self) -> Dict[str, Any]:
        """获取布局配置"""
        return self._layout_config.copy()

    def set_layout_config(self, config: Dict[str, Any]) -> None:
        """
        设置布局配置

        Args:
            config: 布局配置字典
        """
        self._layout_config.update(config)
        logger.info(f"布局配置已更新: {config}")

    def create_professional_backtest_widget(self) -> None:
        """创建专业回测组件作为停靠窗口（公共接口）"""
        self._create_professional_backtest_widget()

    def on_bottom_panel_hidden(self) -> None:
        """处理底部面板隐藏事件（公共接口）"""
        self._on_bottom_panel_hidden()

    def update_bottom_panel_menu_item(self, is_visible: bool) -> None:
        """
        更新底部面板菜单项（公共接口）

        Args:
            is_visible: 底部面板是否可见
        """
        self._update_bottom_panel_menu_item(is_visible)

    def show_bottom_panel(self) -> None:
        """显示底部面板（公共接口）"""
        self._show_bottom_panel()

    def notify_panels_theme_change(self) -> None:
        """通知所有面板主题变化（公共接口，用于JSON主题）"""
        self._notify_panels_theme_change()

    def _do_dispose(self) -> None:
        """清理面板资源"""
        try:
            for panel_name, panel in list(self._panels.items()):
                try:
                    if panel_name in ('right_dock', 'backtest_dock'):
                        continue
                    if hasattr(panel, 'dispose'):
                        panel.dispose()
                        logger.debug(f"Panel '{panel_name}' disposed via dispose()")
                    elif hasattr(panel, 'deleteLater'):
                        panel.deleteLater()
                        logger.debug(f"Panel '{panel_name}' released via deleteLater()")
                except Exception as e:
                    logger.warning(f"Failed to dispose panel '{panel_name}': {e}")

            if hasattr(self, '_backtest_widget') and self._backtest_widget is not None:
                try:
                    if hasattr(self._backtest_widget, 'dispose'):
                        self._backtest_widget.dispose()
                    if hasattr(self._backtest_widget, 'deleteLater'):
                        self._backtest_widget.deleteLater()
                    self._backtest_widget = None
                    logger.debug("Backtest widget properly released")
                except Exception as e:
                    logger.warning(f"Failed to release backtest widget: {e}")

            if hasattr(self, '_backtest_dock') and self._backtest_dock is not None:
                try:
                    if hasattr(self._backtest_dock, 'deleteLater'):
                        self._backtest_dock.deleteLater()
                    self._backtest_dock = None
                except Exception as e:
                    logger.warning(f"Failed to release backtest dock: {e}")

            for dock_name in ('right_dock',):
                if dock_name in self._panels:
                    dock = self._panels[dock_name]
                    try:
                        if hasattr(dock, 'deleteLater'):
                            dock.deleteLater()
                    except Exception as e:
                        logger.warning(f"Failed to release {dock_name}: {e}")

            self._panels.clear()
            self._main_window_coordinator = None
            self._main_window = None
            self._layout_config.clear()
            logger.info("Panel coordinator disposed successfully")

        except Exception as e:
            logger.error(f"Failed to dispose panel coordinator: {e}")
