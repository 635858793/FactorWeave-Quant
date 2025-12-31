from loguru import logger
"""
底部面板模块 - 日志显示和系统状态
"""
from typing import Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLineEdit, QPushButton, QComboBox, QLabel,
    QSplitter, QFrame, QCheckBox, QSpinBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QTextCursor

from .base_panel import BasePanel
import re
import sys
from datetime import datetime


class LogHandler:
    """自定义日志处理器，将Loguru日志输出到UI（已迁移到Loguru）"""

    def __init__(self, log_widget):
        self.log_widget = log_widget
        # 注册到Loguru作为自定义sink
        self.current_level = "INFO"
        self.handler_id = logger.add(self._loguru_sink, level="INFO")

    def _loguru_sink(self, message):
        """Loguru自定义sink"""
        try:
            # 解析Loguru消息
            record = message.record
            log_level = record["level"].name
            msg = record["message"]
            timestamp = record["time"].strftime("%H:%M:%S.%f")[:-3]

            # 发送到UI
            if hasattr(self.log_widget, 'add_log'):
                self.log_widget.add_log(timestamp, log_level, msg)
            elif hasattr(self.log_widget, 'append_log'):
                self.log_widget.append_log(msg, log_level)
        except Exception as e:
            logger.error(f"UI日志处理错误: {e}")

    def remove_handler(self):
        """移除处理器"""
        try:
            logger.remove(self.handler_id)
        except:
            pass

    def update_level(self, level: str):
        """更新日志级别"""
        if level != self.current_level:
            # 移除旧的handler
            try:
                logger.remove(self.handler_id)
            except:
                pass

            # 添加新的handler with new level
            self.current_level = level
            self.handler_id = logger.add(self._loguru_sink, level=level)
            logger.debug(f"UI日志处理器级别已更新为: {level}")


class LogWidget(QTextEdit):
    """日志显示组件"""

    # 添加信号用于线程安全的日志追加
    log_appended = pyqtSignal(str, str)  # 参数: formatted_msg, level

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        # 使用document()来设置最大块数，兼容性更好
        try:
            self.document().setMaximumBlockCount(1000)  # 限制最大行数
        except AttributeError:
            # 如果方法不存在，使用替代方案
            pass

        # 设置字体
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)

        # 日志级别颜色
        self.level_colors = {
            'DEBUG': '#888888',
            # 'INFO': '#000000',
            'WARNING': '#FF8C00',
            'ERROR': '#FF0000',
            'CRITICAL': '#8B0000'
        }

        # 连接信号到槽
        self.log_appended.connect(self._append_log_safe)

    def append_log(self, message: str, level: str = 'INFO'):
        """添加日志消息 - 线程安全版本，通过信号/槽机制确保在主线程中执行"""
        color = self.level_colors.get(level, self.palette().text().color().name())
        formatted_msg = f'<span style="color: {color};">[{level}] {message}</span>'
        # 发射信号而不是直接操作UI
        self.log_appended.emit(formatted_msg, level)

    @pyqtSlot(str, str)
    def _append_log_safe(self, formatted_msg: str, level: str):
        """在主线程中安全地追加日志 - 由信号触发"""
        # 追加格式化的消息
        self.append(formatted_msg)

        # 自动滚动到底部
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)

    def add_log(self, timestamp: str, level: str, message: str):
        """为LogHandler兼容性提供的方法"""
        formatted_message = f"[{timestamp}] {message}"
        self.append_log(formatted_message, level)


class BottomPanel(BasePanel):
    """底部面板 - 日志显示和系统状态"""

    # 信号
    log_level_changed = pyqtSignal(str)
    log_cleared = pyqtSignal()
    panel_hidden = pyqtSignal()  # 新增：面板隐藏信号

    def __init__(self, parent, coordinator, **kwargs):
        """
        初始化底部面板

        Args:
            parent: 父窗口组件
            coordinator: 主窗口协调器
            **kwargs: 其他参数
        """
        self.log_handler: Optional[LogHandler] = None
        self.auto_scroll = True
        self.max_lines = 1000

        super().__init__(parent, coordinator, **kwargs)

        # 在父类初始化完成后设置日志系统
        self._setup_logging()

    def _create_widgets(self) -> None:
        """创建UI组件（实现抽象方法）"""
        # 创建主布局
        main_layout = QVBoxLayout(self._root_frame)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # 创建工具栏
        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)

        # 创建日志显示区域
        self.log_widget = LogWidget()
        main_layout.addWidget(self.log_widget)

        # 设置初始大小
        self._root_frame.setMinimumHeight(150)
        self._root_frame.setMaximumHeight(400)

        # 保存组件引用
        self.add_widget('toolbar', toolbar)
        self.add_widget('log_widget', self.log_widget)

        # 面板状态
        self.is_panel_visible = True

    def _create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QFrame()
        toolbar.setFrameStyle(QFrame.StyledPanel)
        toolbar.setMaximumHeight(35)

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 2, 5, 2)

        # 日志级别选择
        layout.addWidget(QLabel("日志级别:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(
            ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
        self.level_combo.setCurrentText('INFO')
        self.level_combo.currentTextChanged.connect(self._on_level_changed)
        layout.addWidget(self.level_combo)

        layout.addWidget(QFrame())  # 分隔符

        # 搜索框
        layout.addWidget(QLabel("搜索:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入关键词搜索日志...")
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        layout.addWidget(self.search_edit)

        # 搜索按钮
        search_btn = QPushButton("搜索")
        search_btn.clicked.connect(self._search_logs)
        layout.addWidget(search_btn)

        layout.addWidget(QFrame())  # 分隔符

        # 自动滚动复选框
        self.auto_scroll_cb = QCheckBox("自动滚动")
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.toggled.connect(self._on_auto_scroll_toggled)
        layout.addWidget(self.auto_scroll_cb)

        # 最大行数设置
        layout.addWidget(QLabel("最大行数:"))
        self.max_lines_spin = QSpinBox()
        self.max_lines_spin.setRange(100, 10000)
        self.max_lines_spin.setValue(1000)
        self.max_lines_spin.valueChanged.connect(self._on_max_lines_changed)
        layout.addWidget(self.max_lines_spin)

        layout.addWidget(QFrame())  # 分隔符

        # 清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._clear_logs)
        layout.addWidget(clear_btn)

        # 导出按钮
        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self._export_logs)
        layout.addWidget(export_btn)

        layout.addStretch()  # 添加弹性空间

        return toolbar

    def _setup_logging(self):
        """设置日志系统"""
        # 确保log_widget已经创建
        if not hasattr(self, 'log_widget') or self.log_widget is None:
            return

        # 创建日志处理器
        self.log_handler = LogHandler(self.log_widget)

        # Loguru配置在core.loguru_config中统一管理
        # 不需要单独的格式化器和处理器设置
        # root_        # root_logger.addHandler(self.log_handler)
        # root_# Loguru自动管理日志级别

        # 添加一些测试日志
        self._add_welcome_logs()

    def _add_welcome_logs(self):
        """添加欢迎日志"""
        logger.info("FactorWeave-Quant  2.0 系统启动成功")
        logger.info("日志系统已初始化")
        logger.debug("调试模式已启用")

    def _on_level_changed(self, level: str):
        """日志级别改变"""
        if self.log_handler:
            # level_value = getattr(logging, level)
            # self.log_handler  # Loguru自动管理日志级别
            # # Loguru自动管理日志级别  # Loguru不支持setLevel
            pass

        self.log_level_changed.emit(level)

        logger.info(f"日志级别已设置为: {level}")

    def _on_search_text_changed(self, text: str):
        """搜索文本改变"""
        if not text:
            # 清空搜索，恢复所有日志
            self._restore_all_logs()

    def _search_logs(self):
        """搜索日志"""
        search_text = self.search_edit.text().strip()
        if not search_text:
            return

        # 简单的文本搜索实现
        cursor = self.log_widget.textCursor()

        # 移动到文档开始
        cursor.movePosition(QTextCursor.Start)
        self.log_widget.setTextCursor(cursor)

        # 查找文本
        found = self.log_widget.find(search_text)
        if not found:

            logger.warning(f"未找到包含 '{search_text}' 的日志")

    def _restore_all_logs(self):
        """恢复所有日志显示"""
        # 清除搜索高亮
        cursor = self.log_widget.textCursor()
        cursor.clearSelection()
        self.log_widget.setTextCursor(cursor)

    def _on_auto_scroll_toggled(self, checked: bool):
        """自动滚动切换"""
        self.auto_scroll = checked

        logger.info(f"自动滚动已{'启用' if checked else '禁用'}")

    def _on_max_lines_changed(self, value: int):
        """最大行数改变"""
        self.max_lines = value
        try:
            self.log_widget.document().setMaximumBlockCount(value)
        except AttributeError:
            # 如果方法不存在，忽略
            pass

        logger.info(f"最大日志行数已设置为: {value}")

    def _clear_logs(self):
        """清空日志"""
        self.log_widget.clear()
        self.log_cleared.emit()

        logger.info("日志已清空")

    def _export_logs(self):
        """导出日志"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            from datetime import datetime

            # 获取保存路径
            default_filename = f"factorweave_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filename, _ = QFileDialog.getSaveFileName(
                self._root_frame,
                "导出日志",
                default_filename,
                "文本文件 (*.txt);;所有文件 (*)"
            )

            if filename:
                # 获取日志内容
                log_content = self.log_widget.toPlainText()

                # 写入文件
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(log_content)

                logger.info(f"日志已导出到: {filename}")

        except Exception as e:

            logger.error(f"导出日志失败: {e}")

    def add_log(self, message: str, level: str = 'INFO'):
        """添加日志（公共接口）"""
        self.log_widget.append_log(message, level)

    def set_log_level(self, level: str):
        """设置日志级别（公共接口）"""
        self.level_combo.setCurrentText(level)

    def get_log_level(self) -> str:
        """获取当前日志级别"""
        return self.level_combo.currentText()

    def clear_logs(self):
        """清空日志（公共接口）"""
        self._clear_logs()

    def closeEvent(self, event):
        """关闭事件处理"""
        # 清理日志处理器
        if self.log_handler:
            logger.removeHandler(self.log_handler)
        event.accept()

    def _toggle_panel(self) -> None:
        """切换面板显示/隐藏状态"""
        if self.is_panel_visible:
            self._hide_panel()
        else:
            self._show_panel()

        self.is_panel_visible = not self.is_panel_visible

    def _hide_panel(self) -> None:
        """隐藏面板"""
        if self._root_frame:
            # 隐藏日志部分和工具栏
            self.log_widget.setVisible(False)
            self.get_widget('toolbar').setVisible(False)

            # 调整面板大小为最小高度
            self._root_frame.setFixedHeight(0)

            # 发送隐藏信号
            self.panel_hidden.emit()

            logger.debug("日志面板已隐藏")

    def _show_panel(self) -> None:
        """显示面板"""
        if self._root_frame:
            # 显示日志部分和工具栏
            self.log_widget.setVisible(True)
            self.get_widget('toolbar').setVisible(True)

            # 恢复面板大小
            self._root_frame.setMinimumHeight(150)
            self._root_frame.setMaximumHeight(800)

            # 取消固定高度限制
            self._root_frame.setFixedHeight(200)  # 设置一个合适的默认高度
