#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
纯Loguru日志面板模块
直接集成Loguru日志系统的日志面板
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from loguru import logger

from .base_panel import BasePanel
from gui.widgets.log_widget_loguru import LoguruLogWidget

class LoguruLogPanel(BasePanel):
    """纯Loguru日志面板类"""

    def __init__(self, parent, coordinator):
        super().__init__(parent, coordinator)
        self.log_widget = None
        logger.info("LoguruLogPanel 初始化开始")

    def _create_widgets(self):
        """创建UI组件"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建纯Loguru日志组件
        self.log_widget = LoguruLogWidget()
        layout.addWidget(self.log_widget)

        if self._root_frame:
            self._root_frame.setLayout(layout)
        
        logger.info("LoguruLogPanel UI组件创建完成")

    def _bind_events(self):
        """绑定事件"""
        # 由于使用纯Loguru系统，不需要订阅额外的事件
        # 日志会直接通过Loguru的sink机制显示
        logger.debug("LoguruLogPanel 事件绑定完成")

    def add_log(self, level: str, message: str):
        """添加日志（向后兼容接口）"""
        if self.log_widget:
            self.log_widget.add_log(level, message)

    def clear_logs(self):
        """清空日志"""
        if self.log_widget:
            self.log_widget.clear_logs()

    def export_logs(self, file_path: str):
        """导出日志"""
        if self.log_widget:
            self.log_widget.export_logs()

    def get_log_widget(self) -> LoguruLogWidget:
        """获取日志组件"""
        return self.log_widget

