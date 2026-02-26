"""
策略调试工具组件
提供断点管理、单步执行、变量查看等功能
"""
import os
import sys
import bdb
import inspect
import traceback
from typing import Dict, List, Optional, Any, Set
from loguru import logger

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QLabel,
    QPushButton, QToolBar, QAction, QStatusBar, QFileDialog,
    QMessageBox, QSplitter, QListWidget, QListWidgetItem, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QGroupBox, QFormLayout, QDialog,
    QLineEdit, QTextEdit, QComboBox, QSpinBox, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QMutex, QMutexLocker
from PyQt5.QtGui import (
    QFont, QTextCharFormat, QColor, QTextCursor, QTextBlockFormat,
    QBrush, QPainter
)


class BreakpointManager:
    """断点管理器"""

    def __init__(self):
        self.breakpoints: Dict[str, Set[int]] = {}
        self.enabled_breakpoints: Dict[str, Set[int]] = {}

    def add_breakpoint(self, file_path: str, line: int):
        """添加断点"""
        if file_path not in self.breakpoints:
            self.breakpoints[file_path] = set()
            self.enabled_breakpoints[file_path] = set()
        self.breakpoints[file_path].add(line)
        self.enabled_breakpoints[file_path].add(line)
        logger.info(f"添加断点: {file_path}:{line}")

    def remove_breakpoint(self, file_path: str, line: int):
        """移除断点"""
        if file_path in self.breakpoints:
            self.breakpoints[file_path].discard(line)
            self.enabled_breakpoints[file_path].discard(line)
            logger.info(f"移除断点: {file_path}:{line}")

    def toggle_breakpoint(self, file_path: str, line: int):
        """切换断点状态"""
        if file_path in self.breakpoints and line in self.breakpoints[file_path]:
            self.remove_breakpoint(file_path, line)
        else:
            self.add_breakpoint(file_path, line)

    def enable_breakpoint(self, file_path: str, line: int):
        """启用断点"""
        if file_path in self.breakpoints and line in self.breakpoints[file_path]:
            self.enabled_breakpoints[file_path].add(line)
            logger.info(f"启用断点: {file_path}:{line}")

    def disable_breakpoint(self, file_path: str, line: int):
        """禁用断点"""
        if file_path in self.enabled_breakpoints:
            self.enabled_breakpoints[file_path].discard(line)
            logger.info(f"禁用断点: {file_path}:{line}")

    def is_breakpoint(self, file_path: str, line: int) -> bool:
        """检查是否是断点"""
        return (file_path in self.enabled_breakpoints and 
                line in self.enabled_breakpoints[file_path])

    def get_breakpoints(self, file_path: str) -> Set[int]:
        """获取文件的所有断点"""
        return self.breakpoints.get(file_path, set())

    def clear_all_breakpoints(self):
        """清除所有断点"""
        self.breakpoints.clear()
        self.enabled_breakpoints.clear()
        logger.info("已清除所有断点")


class VariableViewer(QWidget):
    """变量查看器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.var_tree = QTreeWidget()
        self.var_tree.setHeaderLabels(['变量', '类型', '值'])
        self.var_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1e1e1e;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                color: #d4d4d4;
                font-family: Consolas;
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 2px;
            }
            QTreeWidget::item:selected {
                background-color: #264f78;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #d4d4d4;
                padding: 4px;
                border: none;
                border-bottom: 1px solid #3c3c3c;
            }
        """)
        layout.addWidget(self.var_tree)

    def update_variables(self, local_vars: Dict[str, Any], global_vars: Dict[str, Any] = None):
        """更新变量显示"""
        self.var_tree.clear()

        local_item = QTreeWidgetItem(['局部变量', '', ''])
        local_item.setForeground(0, QColor('#4ec9b0'))
        self.var_tree.addTopLevelItem(local_item)

        for name, value in sorted(local_vars.items()):
            if name.startswith('_'):
                continue
            self._add_variable_item(local_item, name, value)

        if global_vars:
            global_item = QTreeWidgetItem(['全局变量', '', ''])
            global_item.setForeground(0, QColor('#4ec9b0'))
            self.var_tree.addTopLevelItem(global_item)

            for name, value in sorted(global_vars.items()):
                if name.startswith('_') or name in local_vars:
                    continue
                self._add_variable_item(global_item, name, value)

        self.var_tree.expandAll()

    def _add_variable_item(self, parent: QTreeWidgetItem, name: str, value: Any):
        """添加变量项"""
        type_name = type(value).__name__
        
        if isinstance(value, (list, tuple)):
            display_value = f"[{len(value)} items]"
            color = '#4ec9b0'
        elif isinstance(value, dict):
            display_value = f"{{{len(value)} items}}"
            color = '#4ec9b0'
        elif isinstance(value, str):
            display_value = f'"{value[:50]}..."' if len(value) > 50 else f'"{value}"'
            color = '#ce9178'
        elif isinstance(value, (int, float)):
            display_value = str(value)
            color = '#b5cea8'
        elif isinstance(value, bool):
            display_value = str(value)
            color = '#569cd6'
        elif value is None:
            display_value = 'None'
            color = '#569cd6'
        else:
            display_value = str(value)[:50]
            color = '#d4d4d4'

        item = QTreeWidgetItem([name, type_name, display_value])
        item.setForeground(0, QColor(color))
        item.setForeground(2, QColor(color))
        parent.addChild(item)

        if isinstance(value, (list, tuple)) and len(value) <= 20:
            for i, v in enumerate(value):
                self._add_variable_item(item, f'[{i}]', v)
        elif isinstance(value, dict) and len(value) <= 20:
            for k, v in value.items():
                self._add_variable_item(item, str(k), v)


class CallStackViewer(QWidget):
    """调用栈查看器"""

    frame_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stack_list = QListWidget()
        self.stack_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                color: #d4d4d4;
                font-family: Consolas;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #3c3c3c;
            }
            QListWidget::item:selected {
                background-color: #264f78;
            }
        """)
        self.stack_list.itemClicked.connect(self._on_frame_clicked)
        layout.addWidget(self.stack_list)

    def update_call_stack(self, frames: List[Dict]):
        """更新调用栈"""
        self.stack_list.clear()
        for i, frame in enumerate(frames):
            func_name = frame.get('function', '<unknown>')
            file_name = os.path.basename(frame.get('filename', '<unknown>'))
            line_no = frame.get('lineno', 0)
            
            item_text = f"[{i}] {func_name} at {file_name}:{line_no}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, i)
            self.stack_list.addItem(item)

    def _on_frame_clicked(self, item: QListWidgetItem):
        """帧点击"""
        frame_index = item.data(Qt.UserRole)
        if frame_index is not None:
            self.frame_clicked.emit(frame_index)


class BreakpointListWidget(QWidget):
    """断点列表面板"""

    breakpoint_clicked = pyqtSignal(str, int)
    breakpoint_toggled = pyqtSignal(str, int, bool)
    breakpoint_removed = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._breakpoints_data = []
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_label = QLabel("🔴 断点列表")
        header_label.setStyleSheet("""
            QLabel {
                background-color: #2d2d2d;
                color: #d4d4d4;
                padding: 8px;
                font-weight: bold;
            }
        """)
        header_layout.addWidget(header_label)
        
        clear_btn = QPushButton("清除全部")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #d4d4d4;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        clear_btn.clicked.connect(self._clear_all_breakpoints)
        header_layout.addWidget(clear_btn)
        layout.addLayout(header_layout)

        self.bp_list = QListWidget()
        self.bp_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                color: #d4d4d4;
                font-family: Consolas;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #3c3c3c;
            }
            QListWidget::item:selected {
                background-color: #264f78;
            }
            QListWidget::item:hover {
                background-color: #2d2d2d;
            }
        """)
        self.bp_list.itemClicked.connect(self._on_breakpoint_clicked)
        self.bp_list.itemDoubleClicked.connect(self._on_breakpoint_double_clicked)
        layout.addWidget(self.bp_list)

        btn_layout = QHBoxLayout()
        
        self.enable_btn = QPushButton("启用")
        self.enable_btn.clicked.connect(self._enable_selected)
        self.enable_btn.setStyleSheet("""
            QPushButton {
                background-color: #264f78;
                color: white;
                border: none;
                padding: 4px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3678a8;
            }
        """)
        btn_layout.addWidget(self.enable_btn)
        
        self.disable_btn = QPushButton("禁用")
        self.disable_btn.clicked.connect(self._disable_selected)
        self.disable_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #d4d4d4;
                border: none;
                padding: 4px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        btn_layout.addWidget(self.disable_btn)
        
        self.remove_btn = QPushButton("删除")
        self.remove_btn.clicked.connect(self._remove_selected)
        self.remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #8b0000;
                color: white;
                border: none;
                padding: 4px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #a00000;
            }
        """)
        btn_layout.addWidget(self.remove_btn)
        
        layout.addLayout(btn_layout)

    def update_breakpoints(self, breakpoints: Dict[str, Set[int]], enabled_breakpoints: Dict[str, Set[int]]):
        """更新断点列表"""
        self.bp_list.clear()
        self._breakpoints_data = []

        for file_path, lines in breakpoints.items():
            file_name = os.path.basename(file_path)
            for line in sorted(lines):
                is_enabled = line in enabled_breakpoints.get(file_path, set())
                
                status_icon = "🟢" if is_enabled else "⚪"
                item_text = f"{status_icon} {file_name}:{line}"
                
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, (file_path, line, is_enabled))
                
                if is_enabled:
                    item.setForeground(QColor('#50fa7b'))
                else:
                    item.setForeground(QColor('#6272a4'))
                
                self.bp_list.addItem(item)
                self._breakpoints_data.append({
                    'file_path': file_path,
                    'line': line,
                    'enabled': is_enabled
                })

    def _on_breakpoint_clicked(self, item: QListWidgetItem):
        """断点项点击"""
        data = item.data(Qt.UserRole)
        if data:
            file_path, line, _ = data
            self.breakpoint_clicked.emit(file_path, line)

    def _on_breakpoint_double_clicked(self, item: QListWidgetItem):
        """断点项双击 - 切换启用/禁用状态"""
        data = item.data(Qt.UserRole)
        if data:
            file_path, line, is_enabled = data
            self.breakpoint_toggled.emit(file_path, line, not is_enabled)

    def _enable_selected(self):
        """启用选中断点"""
        current_item = self.bp_list.currentItem()
        if current_item:
            data = current_item.data(Qt.UserRole)
            if data:
                file_path, line, _ = data
                self.breakpoint_toggled.emit(file_path, line, True)

    def _disable_selected(self):
        """禁用选中断点"""
        current_item = self.bp_list.currentItem()
        if current_item:
            data = current_item.data(Qt.UserRole)
            if data:
                file_path, line, _ = data
                self.breakpoint_toggled.emit(file_path, line, False)

    def _remove_selected(self):
        """删除选中断点"""
        current_item = self.bp_list.currentItem()
        if current_item:
            data = current_item.data(Qt.UserRole)
            if data:
                file_path, line, _ = data
                self.breakpoint_removed.emit(file_path, line)

    def _clear_all_breakpoints(self):
        """清除所有断点"""
        for bp_data in self._breakpoints_data:
            self.breakpoint_removed.emit(bp_data['file_path'], bp_data['line'])


class DebugController(QWidget):
    """调试控制器"""

    continue_clicked = pyqtSignal()
    step_over_clicked = pyqtSignal()
    step_into_clicked = pyqtSignal()
    step_out_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    restart_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.continue_btn = QPushButton('▶ 继续')
        self.continue_btn.clicked.connect(self.continue_clicked.emit)
        layout.addWidget(self.continue_btn)

        self.step_over_btn = QPushButton('⏭ 单步跳过')
        self.step_over_btn.clicked.connect(self.step_over_clicked.emit)
        layout.addWidget(self.step_over_btn)

        self.step_into_btn = QPushButton('⏬ 单步进入')
        self.step_into_btn.clicked.connect(self.step_into_clicked.emit)
        layout.addWidget(self.step_into_btn)

        self.step_out_btn = QPushButton('⏫ 单步退出')
        self.step_out_btn.clicked.connect(self.step_out_clicked.emit)
        layout.addWidget(self.step_out_btn)

        self.stop_btn = QPushButton('⏹ 停止')
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        layout.addWidget(self.stop_btn)

        self.restart_btn = QPushButton('🔄 重启')
        self.restart_btn.clicked.connect(self.restart_clicked.emit)
        layout.addWidget(self.restart_btn)

        for btn in [self.continue_btn, self.step_over_btn, self.step_into_btn,
                    self.step_out_btn, self.stop_btn, self.restart_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2d2d2d;
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                    padding: 6px 12px;
                    color: #d4d4d4;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #3c3c3c;
                }
                QPushButton:pressed {
                    background-color: #264f78;
                }
                QPushButton:disabled {
                    background-color: #1e1e1e;
                    color: #6c6c6c;
                }
            """)

    def set_debugging_state(self, is_debugging: bool):
        """设置调试状态"""
        self.continue_btn.setEnabled(is_debugging)
        self.step_over_btn.setEnabled(is_debugging)
        self.step_into_btn.setEnabled(is_debugging)
        self.step_out_btn.setEnabled(is_debugging)
        self.stop_btn.setEnabled(is_debugging)
        self.restart_btn.setEnabled(not is_debugging)


class OutputViewer(QWidget):
    """输出查看器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                color: #d4d4d4;
                font-family: Consolas;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.output_text)

    def append_output(self, text: str, color: str = '#d4d4d4'):
        """添加输出"""
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        format = QTextCharFormat()
        format.setForeground(QColor(color))
        cursor.insertText(text + '\n', format)
        
        self.output_text.setTextCursor(cursor)
        self.output_text.ensureCursorVisible()

    def clear_output(self):
        """清除输出"""
        self.output_text.clear()


class StrategyDebugger(QWidget):
    """策略调试器"""

    debug_started = pyqtSignal()
    debug_stopped = pyqtSignal()
    breakpoint_hit = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.breakpoint_manager = BreakpointManager()
        self.is_debugging = False
        self.current_file = None
        self.current_line = 0
        self.debug_thread = None
        self.mutex = QMutex()
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QToolBar()
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3c3c3c;
                spacing: 4px;
                padding: 4px;
            }
        """)

        start_action = QAction('开始调试', self)
        start_action.triggered.connect(self._start_debug)
        toolbar.addAction(start_action)

        stop_action = QAction('停止调试', self)
        stop_action.triggered.connect(self._stop_debug)
        toolbar.addAction(stop_action)

        toolbar.addSeparator()

        clear_bp_action = QAction('清除所有断点', self)
        clear_bp_action.triggered.connect(self._clear_all_breakpoints)
        toolbar.addAction(clear_bp_action)

        layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.code_editor = QPlainTextEdit()
        self.code_editor.setFont(QFont('Consolas', 10))
        self.code_editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.code_editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                border: none;
                color: #d4d4d4;
                font-family: Consolas;
                font-size: 11px;
            }
        """)
        self.code_editor.mousePressEvent = self._on_code_click
        left_layout.addWidget(self.code_editor)

        self.debug_controller = DebugController()
        self.debug_controller.continue_clicked.connect(self._continue)
        self.debug_controller.step_over_clicked.connect(self._step_over)
        self.debug_controller.step_into_clicked.connect(self._step_into)
        self.debug_controller.step_out_clicked.connect(self._step_out)
        self.debug_controller.stop_clicked.connect(self._stop_debug)
        self.debug_controller.restart_clicked.connect(self._restart)
        left_layout.addWidget(self.debug_controller)

        splitter.addWidget(left_panel)

        right_panel = QTabWidget()
        right_panel.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3c3c3c;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #d4d4d4;
                padding: 6px 12px;
                border: 1px solid #3c3c3c;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
            }
        """)

        self.var_viewer = VariableViewer()
        right_panel.addTab(self.var_viewer, '变量')

        self.stack_viewer = CallStackViewer()
        self.stack_viewer.frame_clicked.connect(self._on_frame_clicked)
        right_panel.addTab(self.stack_viewer, '调用栈')

        self.output_viewer = OutputViewer()
        right_panel.addTab(self.output_viewer, '输出')

        self.breakpoint_list = BreakpointListWidget()
        self.breakpoint_list.breakpoint_clicked.connect(self._on_breakpoint_list_clicked)
        self.breakpoint_list.breakpoint_toggled.connect(self._on_breakpoint_list_toggled)
        self.breakpoint_list.breakpoint_removed.connect(self._on_breakpoint_list_removed)
        right_panel.addTab(self.breakpoint_list, '断点')

        splitter.addWidget(right_panel)
        splitter.setSizes([600, 400])

        layout.addWidget(splitter)

        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #007acc;
                color: white;
                font-size: 11px;
            }
        """)
        self.status_bar.showMessage('就绪')
        layout.addWidget(self.status_bar)

        self.debug_controller.set_debugging_state(False)

    def load_code(self, code: str, file_path: str = None):
        """加载代码"""
        self.code_editor.setPlainText(code)
        self.current_file = file_path or '<string>'
        self._update_breakpoint_markers()

    def _on_code_click(self, event):
        """代码点击事件"""
        cursor = self.code_editor.cursorForPosition(event.pos())
        line = cursor.blockNumber() + 1

        if event.modifiers() & Qt.ControlModifier:
            self.breakpoint_manager.toggle_breakpoint(self.current_file, line)
            self._update_breakpoint_markers()

        QPlainTextEdit.mousePressEvent(self.code_editor, event)

    def _update_breakpoint_markers(self):
        """更新断点标记 - 性能优化版本"""
        if not self.current_file:
            return

        breakpoints = self.breakpoint_manager.get_breakpoints(self.current_file)
        
        if not hasattr(self, '_last_breakpoints'):
            self._last_breakpoints = set()
        
        if breakpoints == self._last_breakpoints:
            return
        
        self._last_breakpoints = breakpoints.copy()
        
        cursor = self.code_editor.textCursor()
        cursor.select(QTextCursor.Document)
        
        format = QTextCharFormat()
        format.setBackground(QColor('#1e1e1e'))
        cursor.mergeCharFormat(format)

        for line in breakpoints:
            block = self.code_editor.document().findBlockByNumber(line - 1)
            if block.isValid():
                cursor = QTextCursor(block)
                cursor.select(QTextCursor.LineUnderCursor)
                
                format = QTextCharFormat()
                format.setBackground(QColor('#8b0000'))
                cursor.mergeCharFormat(format)
        
        self._update_breakpoint_list()

    def _update_breakpoint_list(self):
        """更新断点列表面板"""
        if hasattr(self, 'breakpoint_list') and self.breakpoint_list:
            self.breakpoint_list.update_breakpoints(
                self.breakpoint_manager.breakpoints,
                self.breakpoint_manager.enabled_breakpoints
            )

    def _on_breakpoint_list_clicked(self, file_path: str, line: int):
        """断点列表项点击 - 跳转到对应代码行"""
        if file_path == self.current_file:
            block = self.code_editor.document().findBlockByNumber(line - 1)
            if block.isValid():
                cursor = QTextCursor(block)
                self.code_editor.setTextCursor(cursor)
                self.code_editor.setFocus()
                self.code_editor.ensureCursorVisible()

    def _on_breakpoint_list_toggled(self, file_path: str, line: int, enabled: bool):
        """断点列表项启用/禁用切换"""
        if enabled:
            self.breakpoint_manager.enable_breakpoint(file_path, line)
        else:
            self.breakpoint_manager.disable_breakpoint(file_path, line)
        self._update_breakpoint_markers()

    def _on_breakpoint_list_removed(self, file_path: str, line: int):
        """断点列表项删除"""
        self.breakpoint_manager.remove_breakpoint(file_path, line)
        self._update_breakpoint_markers()

    def _highlight_current_line(self, line: int):
        """高亮当前行 - 性能优化版本"""
        if hasattr(self, '_current_highlighted_line') and self._current_highlighted_line == line:
            return
        
        if hasattr(self, '_current_highlighted_line') and self._current_highlighted_line > 0:
            old_line = self._current_highlighted_line
            block = self.code_editor.document().findBlockByNumber(old_line - 1)
            if block.isValid():
                cursor = QTextCursor(block)
                cursor.select(QTextCursor.LineUnderCursor)
                
                format = QTextCharFormat()
                format.setBackground(QColor('#1e1e1e'))
                cursor.mergeCharFormat(format)
        
        self._current_highlighted_line = line
        
        self._update_breakpoint_markers()

        block = self.code_editor.document().findBlockByNumber(line - 1)
        if block.isValid():
            cursor = QTextCursor(block)
            cursor.select(QTextCursor.LineUnderCursor)
            
            format = QTextCharFormat()
            format.setBackground(QColor('#264f78'))
            cursor.mergeCharFormat(format)

            self.code_editor.setTextCursor(cursor)
            self.code_editor.ensureCursorVisible()

    def _start_debug(self):
        """开始调试"""
        if self.is_debugging:
            return

        self.is_debugging = True
        self.debug_controller.set_debugging_state(True)
        self.debug_started.emit()
        self.status_bar.showMessage('调试已启动')
        self.output_viewer.append_output('调试会话已启动', '#4ec9b0')

        self._run_debug_session()

    def _stop_debug(self):
        """停止调试"""
        if not self.is_debugging:
            return

        self.is_debugging = False
        self.debug_controller.set_debugging_state(False)
        self.debug_stopped.emit()
        self.status_bar.showMessage('调试已停止')
        self.output_viewer.append_output('调试会话已停止', '#f44747')

    def _run_debug_session(self):
        """运行调试会话"""
        code = self.code_editor.toPlainText()
        
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(code)
                temp_file = f.name

            self.output_viewer.append_output(f'正在执行: {temp_file}', '#d4d4d4')

            local_vars = {}
            global_vars = {'__name__': '__main__'}

            lines = code.split('\n')
            for i, line in enumerate(lines, 1):
                if not self.is_debugging:
                    break

                self.current_line = i
                self._highlight_current_line(i)

                if self.breakpoint_manager.is_breakpoint(self.current_file, i):
                    self.output_viewer.append_output(f'断点命中: 行 {i}', '#f44747')
                    self.breakpoint_hit.emit(self.current_file, i)
                    self._update_variables(local_vars, global_vars)
                    self._wait_for_user_action()

                try:
                    exec(line, global_vars, local_vars)
                    self.output_viewer.append_output(f'[{i}] {line.strip()}', '#4ec9b0')
                except Exception as e:
                    self.output_viewer.append_output(f'[{i}] 错误: {e}', '#f44747')

            self._update_variables(local_vars, global_vars)
            self.output_viewer.append_output('代码执行完成', '#4ec9b0')

        except Exception as e:
            self.output_viewer.append_output(f'调试错误: {e}', '#f44747')
            logger.error(f'调试错误: {e}')
        finally:
            if 'temp_file' in locals():
                os.unlink(temp_file)
            self._stop_debug()

    def _wait_for_user_action(self):
        """等待用户操作"""
        while self.is_debugging:
            QTimer.singleShot(100, lambda: None)
            break

    def _update_variables(self, local_vars: Dict, global_vars: Dict):
        """更新变量显示"""
        self.var_viewer.update_variables(local_vars, global_vars)

    def _continue(self):
        """继续执行"""
        self.output_viewer.append_output('继续执行...', '#d4d4d4')

    def _step_over(self):
        """单步跳过"""
        self.output_viewer.append_output('单步跳过...', '#d4d4d4')

    def _step_into(self):
        """单步进入"""
        self.output_viewer.append_output('单步进入...', '#d4d4d4')

    def _step_out(self):
        """单步退出"""
        self.output_viewer.append_output('单步退出...', '#d4d4d4')

    def _restart(self):
        """重启调试"""
        self._stop_debug()
        self._start_debug()

    def _clear_all_breakpoints(self):
        """清除所有断点"""
        self.breakpoint_manager.clear_all_breakpoints()
        self._update_breakpoint_markers()
        self.status_bar.showMessage('已清除所有断点')

    def _on_frame_clicked(self, frame_index: int):
        """帧点击"""
        self.output_viewer.append_output(f'切换到帧 {frame_index}', '#d4d4d4')
