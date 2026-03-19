from loguru import logger
"""
Tool bar for the trading system

This module contains the tool bar implementation for the trading system.
"""

from PyQt5.QtWidgets import (
    QToolBar, QAction, QToolButton, QMenu,
    QFileDialog, QMessageBox, QDialog, QVBoxLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox, QComboBox,
    QHBoxLayout, QGroupBox, QFormLayout, QDialogButtonBox, QSizePolicy, QWidget
)
from PyQt5.QtCore import Qt, QSize, QKeySequence
from PyQt5.QtGui import QIcon
import os
import traceback
from gui.widgets.log_widget import LogWidget

# 延迟导入主题管理器，避免在模块级别导入时崩溃
THEME_MANAGER_AVAILABLE = False
get_theme_manager = None

def _import_theme_manager():
    """延迟导入主题管理器"""
    global THEME_MANAGER_AVAILABLE, get_theme_manager
    if not THEME_MANAGER_AVAILABLE:
        try:
            from utils.theme import get_theme_manager as _get_theme_manager
            get_theme_manager = _get_theme_manager
            THEME_MANAGER_AVAILABLE = True
            logger.info("主题管理器模块导入成功")
        except Exception as e:
            logger.warning(f"导入主题管理器失败：{e}")
# log_structured 已替换为直接的 logger 调用

class MainToolBar(QToolBar):
    """主工具栏"""

    def __init__(self, parent=None):
        """初始化工具栏

        Args:
            parent: 父窗口
        """
        try:
            super().__init__(parent)

            # 初始化缩放级别
            self._zoom_level = 1.0
            self._zoom_history = []
            self._max_zoom_history = 10

            # 初始化日志管理器
            if True:  # 使用 Loguru 日志
                # log_manager 已迁移到 Loguru
                pass
            else:
                # 纯 Loguru 架构，移除 log_manager 依赖
                pass

            # 延迟导入并初始化主题管理器
            _import_theme_manager()
            self.theme_manager = None
            if THEME_MANAGER_AVAILABLE:
                try:
                    self.theme_manager = get_theme_manager()
                except Exception as e:
                    logger.warning(f"获取 ThemeManager 失败：{e}")

            # 初始化 UI
            self.init_ui()

            logger.info("toolbar_init", status="success")

        except Exception as e:
            logger.info(f"初始化工具栏失败：{str(e)}")
            if True:  # 使用 Loguru 日志
                logger.error(f"初始化工具栏失败：{str(e)}")
                logger.error(traceback.format_exc())

    def init_ui(self):
        """Initialize the UI"""
        try:
            # 设置工具栏属性
            self.setMovable(False)
            self.setIconSize(QSize(24, 24))
            self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

            # 创建工具栏按钮
            self.create_actions()

        except Exception as e:
            logger.error(f"初始化工具栏失败：{str(e)}")

    def create_actions(self):
        """创建工具栏按钮"""
        # 文件操作
        self.new_action = QAction(QIcon("icons/new.png"), "新建", self)
        self.new_action.setStatusTip("创建新的策略")
        self.new_action.setShortcut("Ctrl+N")
        self.addAction(self.new_action)

        self.open_action = QAction(QIcon("icons/open.png"), "打开", self)
        self.open_action.setStatusTip("打开策略文件")
        self.open_action.setShortcut("Ctrl+O")
        self.addAction(self.open_action)

        self.save_action = QAction(QIcon("icons/save.png"), "保存", self)
        self.save_action.setStatusTip("保存当前策略")
        self.save_action.setShortcut("Ctrl+S")
        self.addAction(self.save_action)

        self.addSeparator()

        # 分析工具
        self.analyze_action = QAction(QIcon("icons/analyze.png"), "分析", self)
        self.analyze_action.setStatusTip("分析当前股票")
        self.analyze_action.setShortcut("F5")
        self.addAction(self.analyze_action)

        self.backtest_action = QAction(QIcon("icons/backtest.png"), "回测", self)
        self.backtest_action.setStatusTip("回测当前策略")
        self.backtest_action.setShortcut("F6")
        self.addAction(self.backtest_action)

        self.optimize_action = QAction(QIcon("icons/optimize.png"), "优化", self)
        self.optimize_action.setStatusTip("优化策略参数")
        self.optimize_action.setShortcut("F7")
        self.addAction(self.optimize_action)

        self.addSeparator()

        # 缩放工具
        self.zoom_in_action = QAction(QIcon("icons/zoom_in.png"), "放大", self)
        self.zoom_in_action.setStatusTip("放大图表")
        self.zoom_in_action.setShortcut(QKeySequence("Ctrl+="))
        self.zoom_in_action.triggered.connect(self.zoom_in)
        self.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction(QIcon("icons/zoom_out.png"), "缩小", self)
        self.zoom_out_action.setStatusTip("缩小图表")
        self.zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        self.zoom_out_action.triggered.connect(self.zoom_out)
        self.addAction(self.zoom_out_action)

        self.reset_zoom_action = QAction(
            QIcon("icons/reset_zoom.png"), "重置缩放", self)
        self.reset_zoom_action.setStatusTip("重置图表缩放")
        self.reset_zoom_action.setShortcut(QKeySequence("Ctrl+0"))
        self.reset_zoom_action.triggered.connect(self.reset_zoom)
        self.addAction(self.reset_zoom_action)

        self.undo_zoom_action = QAction(QIcon("icons/undo.png"), "撤销缩放", self)
        self.undo_zoom_action.setStatusTip("撤销上一次缩放操作")
        self.undo_zoom_action.setShortcut(QKeySequence("Ctrl+Z"))
        self.undo_zoom_action.triggered.connect(self.undo_zoom)
        self.addAction(self.undo_zoom_action)

        self.addSeparator()

        # 常用工具
        self.calculator_action = QAction(
            QIcon("icons/calculator.png"), "计算器", self)
        self.calculator_action.setStatusTip("打开计算器")
        self.calculator_action.setShortcut("Ctrl+K")
        self.addAction(self.calculator_action)

        self.converter_action = QAction(
            QIcon("icons/converter.png"), "单位转换", self)
        self.converter_action.setStatusTip("打开单位转换器")
        self.converter_action.setShortcut("Ctrl+U")
        self.addAction(self.converter_action)

        self.settings_action = QAction(QIcon("icons/settings.png"), "设置", self)
        self.settings_action.setStatusTip("打开设置对话框")
        self.settings_action.setShortcut("Ctrl+,")
        self.addAction(self.settings_action)

        # 策略参数优化（快捷入口）
        self.parameter_optimizer_action = QAction(
            QIcon("icons/optimize.png"), "⚡ 参数优化", self)
        self.parameter_optimizer_action.setStatusTip("打开策略参数优化器（支持参数扫描、预设管理和智能推荐）")
        self.parameter_optimizer_action.setShortcut("Ctrl+Shift+O")
        self.parameter_optimizer_action.triggered.connect(self.show_parameter_optimizer)
        self.addAction(self.parameter_optimizer_action)

        # 搜索框
        self.addSeparator()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索股票代码或名称...")
        self.search_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.addWidget(self.search_box)

    def log_message(self, message: str, level: str = "info") -> None:
        """记录日志消息，统一调用主窗口或日志管理器"""
        try:
            parent = self.parentWidget()
            if parent and hasattr(parent, 'log_message'):
                parent.log_message(message, level)
            elif True:  # 使用 Loguru 日志
                level = level.upper()
                if level == "ERROR":
                    logger.error(message)
                elif level == "WARNING":
                    logger.warning(message)
                elif level == "DEBUG":
                    logger.debug(message)
                else:
                    logger.info(message)
            else:
                logger.info(f"[LOG][{level}] {message}")
        except Exception as e:
            logger.info(f"记录日志失败：{str(e)}")
            if True:  # 使用 Loguru 日志
                logger.error(f"记录日志失败：{str(e)}")
                logger.error(traceback.format_exc())

    def new_file(self):
        """Create a new file"""
        try:
            # Create a new empty file
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "新建文件",
                "",
                "All Files (*);;Python Files (*.py);;Text Files (*.txt)"
            )

            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("")
                msg_box = QMessageBox.information(self, "成功", "文件创建成功")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建文件失败：{str(e)}")

    def open_file(self):
        """Open a file"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "打开文件",
                "",
                "All Files (*);;Python Files (*.py);;Text Files (*.txt)"
            )

            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # TODO: Process file content
                msg_box = QMessageBox.information(self, "成功", "文件打开成功")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开文件失败：{str(e)}")

    def save_file(self):
        """Save current file"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存文件",
                "",
                "All Files (*);;Python Files (*.py);;Text Files (*.txt)"
            )

            if file_path:
                # TODO: Get current content and save
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("")
                QMessageBox.information(self, "成功", "文件保存成功")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存文件失败：{str(e)}")

    def show_settings(self):
        """Show settings dialog"""
        try:
            if hasattr(self.parent(), 'show_settings'):
                self.parent().show_settings()
        except Exception as e:
            logger.error(f"显示设置对话框失败：{str(e)}")

    def show_calculator(self):
        """Show calculator"""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("计算器")
            dialog.setMinimumSize(300, 400)

            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(10)

            # Add calculator display
            display = QLineEdit()
            display.setReadOnly(True)
            display.setAlignment(Qt.AlignRight)
            layout.addWidget(display)

            # Add calculator buttons
            buttons = [
                ['7', '8', '9', '/'],
                ['4', '5', '6', '*'],
                ['1', '2', '3', '-'],
                ['0', '.', '=', '+']
            ]

            for row in buttons:
                button_row = QHBoxLayout()
                for text in row:
                    button = QPushButton(text)
                    button.setMinimumSize(50, 50)
                    button_row.addWidget(button)
                layout.addLayout(button_row)

            # 显示对话框并居中
            dialog.show()
            LogWidget().center_dialog(dialog, self)
            dialog.exec_()

        except Exception as e:
            logger.error(f"显示计算器失败：{str(e)}")

    def show_converter(self):
        """Show unit converter"""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("单位转换器")
            dialog.setMinimumSize(400, 300)

            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(10)

            # Add input fields
            input_group = QGroupBox("输入")
            input_layout = QFormLayout(input_group)

            input_value = QLineEdit()
            input_value.setAlignment(Qt.AlignRight)
            input_unit = QComboBox()
            input_unit.addItems(["元", "美元", "欧元", "英镑"])
            input_layout.addRow("数值:", input_value)
            input_layout.addRow("单位:", input_unit)

            layout.addWidget(input_group)

            # Add output fields
            output_group = QGroupBox("输出")
            output_layout = QFormLayout(output_group)

            output_value = QLineEdit()
            output_value.setReadOnly(True)
            output_value.setAlignment(Qt.AlignRight)
            output_unit = QComboBox()
            output_unit.addItems(["元", "美元", "欧元", "英镑"])
            output_layout.addRow("数值:", output_value)
            output_layout.addRow("单位:", output_unit)

            layout.addWidget(output_group)

            # Add convert button
            convert_button = QPushButton("转换")
            layout.addWidget(convert_button)

            # 显示对话框并居中
            dialog.show()
            LogWidget().center_dialog(dialog, self)
            dialog.exec_()

        except Exception as e:
            logger.error(f"显示单位转换器失败：{str(e)}")

    def resizeEvent(self, event):
        """窗口大小改变事件处理"""
        super().resizeEvent(event)
        self._update_responsive_layout()

    def _update_responsive_layout(self):
        """更新响应式布局"""
        try:
            window_width = self.width()

            logger.debug(f"MainToolBar 响应式布局更新：{window_width}")

            # 更新搜索框宽度
            if hasattr(self, 'search_box'):
                search_width = max(150, int(window_width * 0.15))
                self.search_box.setMinimumWidth(search_width)
                self.search_box.setMaximumWidth(int(window_width * 0.25))

        except Exception as e:
            logger.error(f"更新响应式布局失败：{e}")

    def zoom_in(self):
        """放大图表"""
        try:
            logger.info(f"执行放大操作，当前缩放级别：{self._zoom_level}")
            
            # 保存当前缩放级别到历史记录
            self._zoom_history.append(self._zoom_level)
            if len(self._zoom_history) > self._max_zoom_history:
                self._zoom_history.pop(0)
            
            # 增加缩放级别
            self._zoom_level = min(self._zoom_level + 0.1, 3.0)
            logger.info(f"放大后缩放级别：{self._zoom_level}")
            
            # 通知父窗口更新缩放
            self._notify_zoom_change()
            
        except Exception as e:
            logger.error(f"放大操作失败：{e}")

    def zoom_out(self):
        """缩小图表"""
        try:
            logger.info(f"执行缩小操作，当前缩放级别：{self._zoom_level}")
            
            # 保存当前缩放级别到历史记录
            self._zoom_history.append(self._zoom_level)
            if len(self._zoom_history) > self._max_zoom_history:
                self._zoom_history.pop(0)
            
            # 减小缩放级别
            self._zoom_level = max(self._zoom_level - 0.1, 0.5)
            logger.info(f"缩小后缩放级别：{self._zoom_level}")
            
            # 通知父窗口更新缩放
            self._notify_zoom_change()
            
        except Exception as e:
            logger.error(f"缩小操作失败：{e}")

    def reset_zoom(self):
        """重置缩放"""
        try:
            logger.info(f"执行重置缩放操作，当前缩放级别：{self._zoom_level}")
            
            # 保存当前缩放级别到历史记录
            self._zoom_history.append(self._zoom_level)
            if len(self._zoom_history) > self._max_zoom_history:
                self._zoom_history.pop(0)
            
            # 重置缩放级别
            self._zoom_level = 1.0
            logger.info(f"重置后缩放级别：{self._zoom_level}")
            
            # 通知父窗口更新缩放
            self._notify_zoom_change()
            
        except Exception as e:
            logger.error(f"重置缩放操作失败：{e}")

    def undo_zoom(self):
        """撤销缩放"""
        try:
            if not self._zoom_history:
                logger.info("没有可撤销的缩放操作")
                return
            
            # 从历史记录中恢复上一个缩放级别
            self._zoom_level = self._zoom_history.pop()
            logger.info(f"撤销缩放操作，恢复缩放级别：{self._zoom_level}")
            
            # 通知父窗口更新缩放
            self._notify_zoom_change()
            
        except Exception as e:
            logger.error(f"撤销缩放操作失败：{e}")

    def _notify_zoom_change(self):
        """通知父窗口缩放级别改变"""
        try:
            parent = self.parentWidget()
            if parent and hasattr(parent, 'on_zoom_changed'):
                parent.on_zoom_changed(self._zoom_level)
            else:
                logger.debug("父窗口不支持缩放通知")
        except Exception as e:
            logger.error(f"通知缩放改变失败：{e}")

    def show_parameter_optimizer(self):
        """显示参数优化器"""
        try:
            from gui.widgets.parameter_editor import ParameterEditorWidget
            from core.strategy.strategy_engine import get_strategy_engine
            from core.trading.trading_mode import ModeContext

            # 创建独立对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("⚡ 策略参数优化")
            dialog.resize(800, 900)
            dialog.setMinimumSize(700, 600)

            # 主布局
            main_layout = QVBoxLayout(dialog)

            # 策略选择区域
            strategy_selection_widget = QWidget()
            strategy_selection_layout = QHBoxLayout(strategy_selection_widget)
            strategy_selection_layout.setContentsMargins(10, 10, 10, 10)

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
                logger.warning(f"加载策略列表失败，使用默认列表：{e}")
                # 添加默认策略
                default_strategies = ["MA 策略", "MACD 策略", "RSI 策略", "KDJ 策略", "布林带策略"]
                for i, name in enumerate(default_strategies):
                    strategy_combo.addItem(name, f"strategy_{i}")

            main_layout.addWidget(strategy_selection_widget)

            # 创建参数编辑器
            parameter_editor = ParameterEditorWidget(parent=dialog)
            main_layout.addWidget(parameter_editor)

            # 策略选择变化时加载参数
            def load_strategy_parameters():
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

                    logger.info(f"已加载策略参数：{strategy_name}")

                except Exception as e:
                    logger.error(f"加载策略参数失败：{e}")

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
            logger.error(f"参数优化组件不可用：{e}")
            QMessageBox.warning(self, "错误", f"参数优化功能不可用：{e}")
        except Exception as e:
            logger.error(f"策略优化失败：{e}")
            QMessageBox.warning(self, "错误", f"无法打开参数优化：{e}")
