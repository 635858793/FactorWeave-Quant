"""
单位转换器对话框模块
"""
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from typing import Optional, Dict, Any
from loguru import logger

from .base_dialog import BaseDialog

class ConverterDialog(BaseDialog):
    """单位转换器对话框，优化UI和功能"""

    def __init__(self, parent=None):
        super().__init__(
            parent,
            title="单位转换器",
            settings_key="ConverterDialog"
        )
        self.setStyleSheet("""
            QDialog {
                font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                background-color: #f0f0f0;
            }
            QComboBox, QDoubleSpinBox, QLineEdit {
                font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                font-size: 14px;
                padding: 5px;
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 5px;
            }
            QLabel {
                font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                font-size: 14px;
            }
        """)

        self.setup_ui()
        self.add_shadow_effect()

    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)

        # 创建类型选择
        self.type_combo = QComboBox()
        self.type_combo.addItems(["长度", "重量", "面积", "体积", "温度"])
        layout.addWidget(self.type_combo)

        # 创建输入区域
        input_layout = QHBoxLayout()
        self.input_value = QDoubleSpinBox()
        self.input_value.setRange(-1000000, 1000000)
        self.input_value.setDecimals(6)
        self.input_unit = QComboBox()
        input_layout.addWidget(self.input_value)
        input_layout.addWidget(self.input_unit)
        layout.addLayout(input_layout)

        # 创建输出区域
        output_layout = QHBoxLayout()
        self.output_value = QLineEdit()
        self.output_value.setReadOnly(True)
        self.output_unit = QComboBox()
        output_layout.addWidget(self.output_value)
        output_layout.addWidget(self.output_unit)
        layout.addLayout(output_layout)

        # 连接信号
        self.type_combo.currentTextChanged.connect(self.update_units)
        self.input_value.valueChanged.connect(self.convert)
        self.input_unit.currentTextChanged.connect(self.convert)
        self.output_unit.currentTextChanged.connect(self.convert)

        # 初始化单位列表
        self.update_units()

    def update_units(self):
        """更新单位列表"""
        units = {
            "长度": ["米", "千米", "厘米", "毫米", "英寸", "英尺", "码", "英里"],
            "重量": ["克", "千克", "吨", "磅", "盎司"],
            "面积": ["平方米", "平方千米", "公顷", "亩", "平方英尺", "平方英里"],
            "体积": ["立方米", "升", "毫升", "加仑", "品脱", "夸脱"],
            "温度": ["摄氏度", "华氏度", "开尔文"]
        }

        current_type = self.type_combo.currentText()
        self.input_unit.clear()
        self.output_unit.clear()
        self.input_unit.addItems(units[current_type])
        self.output_unit.addItems(units[current_type])

    def convert(self):
        """转换函数"""
        try:
            value = self.input_value.value()
            from_unit = self.input_unit.currentText()
            to_unit = self.output_unit.currentText()

            # 检查输入有效性
            if not from_unit or not to_unit:
                self.output_value.setText("请选择单位")
                return

            if value == 0 and from_unit == to_unit:
                self.output_value.setText("0.000000")
                return

            # 转换系数
            factors = {
                "长度": {
                    "米": 1,
                    "千米": 1000,
                    "厘米": 0.01,
                    "毫米": 0.001,
                    "英寸": 0.0254,
                    "英尺": 0.3048,
                    "码": 0.9144,
                    "英里": 1609.344
                },
                "重量": {
                    "克": 1,
                    "千克": 1000,
                    "吨": 1000000,
                    "磅": 453.592,
                    "盎司": 28.3495
                },
                "面积": {
                    "平方米": 1,
                    "平方千米": 1000000,
                    "公顷": 10000,
                    "亩": 666.667,
                    "平方英尺": 0.092903,
                    "平方英里": 2589988.11
                },
                "体积": {
                    "立方米": 1,
                    "升": 0.001,
                    "毫升": 0.000001,
                    "加仑": 0.003785,
                    "品脱": 0.000473,
                    "夸脱": 0.000946
                },
                "温度": {
                    "摄氏度": "celsius",
                    "华氏度": "fahrenheit",
                    "开尔文": "kelvin"
                }
            }

            current_type = self.type_combo.currentText()

            if not current_type or current_type not in factors:
                self.output_value.setText("未知类型")
                return

            if current_type == "温度":
                # 温度转换需要特殊处理
                result = self.convert_temperature(value, from_unit, to_unit)
            else:
                # 其他单位转换
                if from_unit == to_unit:
                    result = value
                else:
                    # 检查单位是否存在
                    if from_unit not in factors[current_type] or to_unit not in factors[current_type]:
                        self.output_value.setText("单位不存在")
                        return

                    # 先转换为基准单位，再转换为目标单位
                    base_value = value * factors[current_type][from_unit]
                    result = base_value / factors[current_type][to_unit]

            self.output_value.setText(f"{result:.6f}")

        except Exception as e:
            error_msg = str(e) if str(e) else "转换计算错误"
            logger.error(f"单位转换失败: {error_msg}")
            self.output_value.setText("转换错误")

    def convert_temperature(self, value: float, from_unit: str, to_unit: str) -> float:
        """温度转换"""
        # 先转换为摄氏度
        if from_unit == "华氏度":
            celsius = (value - 32) * 5/9
        elif from_unit == "开尔文":
            celsius = value - 273.15
        else:  # 摄氏度
            celsius = value

        # 再转换为目标单位
        if to_unit == "华氏度":
            return celsius * 9/5 + 32
        elif to_unit == "开尔文":
            return celsius + 273.15
        else:  # 摄氏度
            return celsius

