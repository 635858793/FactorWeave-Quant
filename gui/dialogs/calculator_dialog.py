"""
计算器对话框模块
"""
import re

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from typing import Optional
from loguru import logger

from .base_dialog import BaseDialog

logger = logger

class CalculatorDialog(BaseDialog):
    """计算器对话框，优化UI和功能"""

    def __init__(self, parent=None):
        super().__init__(
            parent,
            title="计算器",
            settings_key="CalculatorDialog"
        )
        
        self.setStyleSheet("""
            CalculatorDialog {
                font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                background-color: #f0f0f0;
            }
            QLineEdit {
                font-family: 'Consolas', 'Microsoft YaHei', monospace;
                font-size: 20px;
                padding: 10px;
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 5px;
            }
            QPushButton {
                font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                font-size: 16px;
                padding: 10px;
                background-color: #e0e0e0;
                border: 1px solid #cccccc;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
        """)

        self.setup_ui()
        self.add_shadow_effect()

    def setup_ui(self):
        """设置UI界面"""
        main_layout = QVBoxLayout(self)

        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignRight)
        self.display.setStyleSheet("font-size: 20px;")
        main_layout.addWidget(self.display)

        grid = QGridLayout()
        main_layout.addLayout(grid)

        buttons = [
            '7', '8', '9', '/',
            '4', '5', '6', '*',
            '1', '2', '3', '-',
            '0', '.', '=', '+'
        ]

        for i, text in enumerate(buttons):
            button = QPushButton(text)
            button.setStyleSheet("font-size: 16px;")
            button.clicked.connect(
                lambda checked, t=text: self.calculator_button_clicked(t))
            grid.addWidget(button, i // 4, i % 4)

        clear_button = QPushButton("C")
        clear_button.setStyleSheet("font-size: 16px;")
        clear_button.clicked.connect(lambda: self.display.clear())
        grid.addWidget(clear_button, 4, 0, 1, 2)

        backspace_button = QPushButton("←")
        backspace_button.setStyleSheet("font-size: 16px;")
        backspace_button.clicked.connect(lambda: self.display.setText(self.display.text()[:-1]))
        grid.addWidget(backspace_button, 4, 2, 1, 2)

    def calculator_button_clicked(self, text: str) -> None:
        """处理计算器按钮点击事件，优化UI刷新机制"""
        try:
            logger.debug(f"计算器按钮点击: {text}")

            if text == "=":
                try:
                    expression = self.display.text()
                    if not re.match(r'^[0-9+\-*/.()\s]*$', expression):
                        self.display.setText("非法输入")
                        return
                    result = eval(expression, {"__builtins__": {}}, {})
                    self.display.setText(str(result))
                except Exception:
                    self.display.setText("错误")
            elif text == "C":
                self.display.clear()
            else:
                self.display.insert(text)

        except Exception as e:
            logger.error(f"计算器操作失败: {str(e)}")
