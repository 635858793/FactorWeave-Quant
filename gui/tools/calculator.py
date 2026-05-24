from loguru import logger
"""
计算器工具

提供基本的数学计算功能。
"""

from typing import Optional
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLineEdit, QPushButton, QWidget
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

logger = logger

class Calculator(QDialog):
    """计算器对话框"""

    def __init__(self, parent: Optional[QWidget] = None):
        """
        初始化计算器

        Args:
            parent: 父窗口组件
        """
        super().__init__(parent)
        self.setWindowTitle("计算器")
        self.setFixedSize(300, 400)

        # 设置样式
        self._setup_styles()

        # 创建UI
        self._create_widgets()

        # 连接信号
        self._connect_signals()

    def _setup_styles(self) -> None:
        """设置样式表"""
        self.setStyleSheet("""
            QDialog {
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
                text-align: right;
            }
            QPushButton {
                font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                font-size: 16px;
                padding: 10px;
                background-color: #e0e0e0;
                border: 1px solid #cccccc;
                border-radius: 5px;
                min-height: 40px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
            QPushButton[objectName="operator"] {
                background-color: #007bff;
                color: white;
            }
            QPushButton[objectName="operator"]:hover {
                background-color: #0056b3;
            }
            QPushButton[objectName="operator"]:pressed {
                background-color: #004085;
            }
            QPushButton[objectName="clear"] {
                background-color: #dc3545;
                color: white;
            }
            QPushButton[objectName="clear"]:hover {
                background-color: #c82333;
            }
            QPushButton[objectName="clear"]:pressed {
                background-color: #bd2130;
            }
        """)

    def _create_widgets(self) -> None:
        """创建UI组件"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 创建显示框
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignRight)
        self.display.setText("0")
        main_layout.addWidget(self.display)

        # 创建按钮网格
        grid_layout = QGridLayout()
        main_layout.addLayout(grid_layout)

        # 按钮配置 (text, row, col, rowspan, colspan, object_name)
        button_configs = [
            ('C', 0, 0, 1, 2, 'clear'),
            ('←', 0, 2, 1, 1, 'clear'),
            ('/', 0, 3, 1, 1, 'operator'),
            ('7', 1, 0, 1, 1, 'number'),
            ('8', 1, 1, 1, 1, 'number'),
            ('9', 1, 2, 1, 1, 'number'),
            ('*', 1, 3, 1, 1, 'operator'),
            ('4', 2, 0, 1, 1, 'number'),
            ('5', 2, 1, 1, 1, 'number'),
            ('6', 2, 2, 1, 1, 'number'),
            ('-', 2, 3, 1, 1, 'operator'),
            ('1', 3, 0, 1, 1, 'number'),
            ('2', 3, 1, 1, 1, 'number'),
            ('3', 3, 2, 1, 1, 'number'),
            ('+', 3, 3, 1, 1, 'operator'),
            ('0', 4, 0, 1, 2, 'number'),
            ('.', 4, 2, 1, 1, 'number'),
            ('=', 4, 3, 1, 1, 'operator'),
        ]

        # 创建按钮
        self.buttons = {}
        for text, row, col, rowspan, colspan, obj_name in button_configs:
            button = QPushButton(text)
            button.setObjectName(obj_name)
            button.clicked.connect(
                lambda checked, t=text: self._on_button_clicked(t))
            grid_layout.addWidget(button, row, col, rowspan, colspan)
            self.buttons[text] = button

    def _connect_signals(self) -> None:
        """连接信号"""
        # 键盘事件
        self.setFocusPolicy(Qt.StrongFocus)

    def _on_button_clicked(self, text: str) -> None:
        """处理按钮点击事件"""
        try:
            current_text = self.display.text()

            if text == "C":
                # 清除显示
                self.display.setText("0")
            elif text == "←":
                # 退格
                if len(current_text) > 1:
                    self.display.setText(current_text[:-1])
                else:
                    self.display.setText("0")
            elif text == "=":
                # 计算结果
                try:
                    if current_text and current_text != "0":
                        # 安全的表达式求值
                        result = self._safe_eval(current_text)
                        self.display.setText(str(result))
                    else:
                        self.display.setText("0")
                except Exception:
                    self.display.setText("错误")
                    logger.warning(f"计算错误: {current_text}")
            else:
                # 添加数字或运算符
                if current_text == "0" and text.isdigit():
                    self.display.setText(text)
                elif current_text == "错误":
                    if text.isdigit() or text == ".":
                        self.display.setText(text)
                    else:
                        self.display.setText("0")
                else:
                    self.display.setText(current_text + text)

        except Exception as e:
            logger.error(f"计算器操作失败: {e}")
            self.display.setText("错误")

    def _safe_eval(self, expression: str) -> float:
        """安全的表达式求值"""
        # 只允许基本的数学运算
        allowed_chars = set('0123456789+-*/.() ')
        if not all(c in allowed_chars for c in expression):
            raise ValueError("包含非法字符")

        # 替换运算符为Python语法
        expression = expression.replace('×', '*').replace('÷', '/')

        # 使用eval进行计算（在受控环境中）
        try:
            result = eval(expression, {"__builtins__": {}}, {})
            return float(result)
        except Exception as e:
            raise ValueError(f"计算错误: {e}")

    def keyPressEvent(self, event):
        """处理键盘事件"""
        key = event.text()

        # 数字和运算符
        if key in '0123456789+-*/.':
            self._on_button_clicked(key)
        elif key == '\r' or key == '\n':  # Enter键
            self._on_button_clicked('=')
        elif event.key() == Qt.Key_Backspace:
            self._on_button_clicked('←')
        elif event.key() == Qt.Key_Escape:
            self._on_button_clicked('C')

        super().keyPressEvent(event)

    @staticmethod
    def show_calculator(parent: Optional[QWidget] = None) -> None:
        """显示计算器对话框"""
        calculator = Calculator(parent)
        calculator.exec_()

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    Calculator.show_calculator()
    sys.exit(app.exec_())
