#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
帮助文档查看对话框模块

提供一个只读的帮助文档查看对话框，支持 Markdown 渲染：
- 优先使用 markdown 库将 Markdown 转换为 HTML 渲染
- 若 markdown 库不可用，则回退为纯文本显示

作者: Hikyuu-UI Team
版本: 1.0
"""

from pathlib import Path

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton
)
from PyQt5.QtGui import QFont

from loguru import logger

from .base_dialog import BaseDialog


class HelpViewerDialog(BaseDialog):
    """帮助文档查看对话框"""

    def __init__(self, parent=None, title="帮助文档", md_path=""):
        """
        初始化帮助文档查看对话框

        Args:
            parent: 父窗口组件
            title: 对话框标题
            md_path: 帮助文档（Markdown）文件路径
        """
        super().__init__(
            parent,
            title=title,
            min_size=(800, 600),
            settings_key="HelpViewerDialog"
        )
        self.md_path = md_path
        self.setup_ui()
        self.load_content()

    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)

        # 文档内容显示区域（只读）
        self.doc_text = QTextEdit()
        self.doc_text.setReadOnly(True)
        self.doc_text.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(self.doc_text)

        # 关闭按钮
        button_layout = QHBoxLayout()
        close_button = QPushButton("关闭")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        close_button.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

    def load_content(self):
        """加载帮助文档内容"""
        try:
            if not self.md_path:
                self.doc_text.setPlainText("未指定帮助文档路径")
                return

            md_file = Path(self.md_path)
            if not md_file.exists():
                self.doc_text.setPlainText(f"文档不存在: {self.md_path}")
                return

            with open(md_file, 'r', encoding='utf-8') as f:
                text = f.read()

            try:
                import markdown
                html = markdown.markdown(text)
                self.doc_text.setHtml(html)
            except ImportError:
                # markdown 库不可用，回退为纯文本显示
                self.doc_text.setPlainText(text)

        except Exception as e:
            logger.error(f"加载帮助文档失败: {e}")
            self.doc_text.setPlainText(f"加载帮助文档失败: {e}")
