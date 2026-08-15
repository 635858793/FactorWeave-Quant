"""
指标参数管理对话框

用于管理技术指标的参数设置，包括参数修改、保存和恢复默认值等功能。
"""

from loguru import logger
import sys
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QTabWidget, QWidget, QScrollArea,
    QGroupBox, QMessageBox, QDialogButtonBox, QFormLayout,
    QSlider, QTextEdit, QSplitter, QFrame, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor

from .base_dialog import BaseDialog

logger = logger.bind(module=__name__)

class IndicatorParamWidget(QWidget):
    """单个指标参数设置小部件"""

    # indicator_name, param_name, value
    param_changed = pyqtSignal(str, str, object)

    def __init__(self, indicator_name: str, param_config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.indicator_name = indicator_name
        self.param_config = param_config
        self.param_widgets = {}
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout()

        # 指标名称标签
        title_label = QLabel(f"<b>{self.indicator_name}</b>")
        title_label.setStyleSheet(
            "color: #2196F3; font-size: 14px; margin-bottom: 10px;")
        layout.addRow(title_label)

        # 参数设置
        for param_name, param_info in self.param_config.items():
            param_widget = self._create_param_widget(param_name, param_info)
            if param_widget:
                self.param_widgets[param_name] = param_widget
                layout.addRow(
                    QLabel(f"{param_info.get('label', param_name)}:"), param_widget)

        self.setLayout(layout)

    def _create_param_widget(self, param_name: str, param_info: Dict[str, Any]) -> QWidget:
        """创建参数控件"""
        param_type = param_info.get('type', 'int')
        default_value = param_info.get('default', 0)
        min_value = param_info.get('min', 0)
        max_value = param_info.get('max', 100)

        if param_type == 'int':
            widget = QSpinBox()
            widget.setRange(min_value, max_value)
            widget.setValue(default_value)
            widget.valueChanged.connect(
                lambda v: self.param_changed.emit(
                    self.indicator_name, param_name, v)
            )
            return widget

        elif param_type == 'float':
            widget = QDoubleSpinBox()
            widget.setRange(min_value, max_value)
            widget.setValue(default_value)
            widget.setDecimals(param_info.get('decimals', 2))
            widget.valueChanged.connect(
                lambda v: self.param_changed.emit(
                    self.indicator_name, param_name, v)
            )
            return widget

        elif param_type == 'bool':
            widget = QCheckBox()
            widget.setChecked(default_value)
            widget.toggled.connect(
                lambda v: self.param_changed.emit(
                    self.indicator_name, param_name, v)
            )
            return widget

        elif param_type == 'str':
            widget = QLineEdit()
            widget.setText(str(default_value))
            widget.textChanged.connect(
                lambda v: self.param_changed.emit(
                    self.indicator_name, param_name, v)
            )
            return widget

        elif param_type == 'choice':
            widget = QComboBox()
            choices = param_info.get('choices', [])
            widget.addItems(choices)
            if default_value in choices:
                widget.setCurrentText(str(default_value))
            widget.currentTextChanged.connect(
                lambda v: self.param_changed.emit(
                    self.indicator_name, param_name, v)
            )
            return widget

        return None

    def get_params(self) -> Dict[str, Any]:
        """获取当前参数值"""
        params = {}
        for param_name, widget in self.param_widgets.items():
            if isinstance(widget, QSpinBox):
                params[param_name] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                params[param_name] = widget.value()
            elif isinstance(widget, QCheckBox):
                params[param_name] = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                params[param_name] = widget.text()
            elif isinstance(widget, QComboBox):
                # R245: matype 类参数转换为 TA-Lib int 索引（与 technical_tab get_current_params 一致）
                value = widget.currentText()
                if 'matype' in param_name.lower():
                    ma_type_map = {"SMA": 0, "EMA": 1, "WMA": 2, "DEMA": 3,
                                   "TEMA": 4, "TRIMA": 5, "KAMA": 6, "MAMA": 7, "T3": 8}
                    params[param_name] = ma_type_map.get(value, 0)
                else:
                    params[param_name] = value
        return params

    def set_params(self, params: Dict[str, Any]):
        """设置参数值"""
        for param_name, value in params.items():
            if param_name in self.param_widgets:
                widget = self.param_widgets[param_name]
                if isinstance(widget, QSpinBox):
                    widget.setValue(int(value))
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(value))
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(value))
                elif isinstance(widget, QComboBox):
                    widget.setCurrentText(str(value))

    def reset_to_default(self):
        """重置为默认值"""
        for param_name, param_info in self.param_config.items():
            if param_name in self.param_widgets:
                widget = self.param_widgets[param_name]
                default_value = param_info.get('default', 0)

                if isinstance(widget, QSpinBox):
                    widget.setValue(int(default_value))
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(default_value))
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(default_value))
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(default_value))
                elif isinstance(widget, QComboBox):
                    widget.setCurrentText(str(default_value))

class IndicatorParamsDialog(BaseDialog):
    """指标参数管理对话框"""

    params_changed = pyqtSignal(dict)  # 参数变化信号

    def __init__(self, selected_indicators: List[str] = None, parent=None):
        super().__init__(
            parent,
            title="指标参数设置",
            min_size=(800, 600),
            settings_key="IndicatorParamsDialog"
        )
        self.selected_indicators = selected_indicators or []
        self.indicator_params = {}
        self.param_widgets = {}
        self._init_ui()
        self._load_indicator_configs()

    def _init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout()

        # 标题
        title_label = QLabel("指标参数设置")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title_label)

        # 创建选项卡
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 按钮区域
        button_layout = QHBoxLayout()

        # 重置按钮
        self.reset_button = QPushButton("重置为默认值")
        self.reset_button.clicked.connect(self._reset_all_params)
        button_layout.addWidget(self.reset_button)

        # 预设按钮
        self.preset_button = QPushButton("加载预设")
        self.preset_button.clicked.connect(self._load_preset)
        button_layout.addWidget(self.preset_button)

        # 保存预设按钮
        self.save_preset_button = QPushButton("保存预设")
        self.save_preset_button.clicked.connect(self._save_preset)
        button_layout.addWidget(self.save_preset_button)

        button_layout.addStretch()

        # 确定取消按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal
        )
        button_box.accepted.connect(self._accept)
        button_box.rejected.connect(self.reject)
        button_layout.addWidget(button_box)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)


    def _load_indicator_configs(self):
        """加载指标配置 - R245: 动态读取统一参数注册表（TA-Lib 参数名），
        替代原硬编码 period/fast_period 等错误命名（与 technical_tab 共用 get_indicator_params_config）
        R282: 无参数配置指标（如 OBV/AD/BOP）不再跳过，创建"无参数"占位 tab，
        保证对话框覆盖全部选中指标（含 KAMA/MAMA/TEMA 等 DB 未种子指标）"""
        from core.indicator_adapter import get_indicator_params_config, get_indicator_english_name

        # 为每个选中的指标创建参数设置页面
        for indicator_name in self.selected_indicators:
            try:
                english_name = get_indicator_english_name(indicator_name)
                config = get_indicator_params_config(english_name)
                if not config or not config.get('params'):
                    # R282: 无参数配置 → 占位 tab（"该指标无可配置参数"），不跳过
                    logger.debug(f"指标 {indicator_name} 无参数配置，创建占位 tab")
                    self._create_placeholder_tab(indicator_name)
                    continue

                # 转换为 IndicatorParamWidget 控件格式 {param_name: {type, default, min, max, label, choices}}
                widget_config = {}
                for param_name, param_info in config['params'].items():
                    param_type = param_info.get('type', 'int')
                    item = {
                        'type': param_type,
                        'default': param_info.get('default', 0),
                        'label': param_info.get('desc', param_name),
                    }
                    if param_info.get('min') is not None:
                        item['min'] = param_info['min']
                    if param_info.get('max') is not None:
                        item['max'] = param_info['max']
                    if param_info.get('choices'):
                        item['choices'] = param_info['choices']
                    widget_config[param_name] = item

                self._create_indicator_tab(indicator_name, widget_config)
            except Exception as e:
                logger.warning(f"加载指标 {indicator_name} 参数配置失败: {e}")
                self._create_placeholder_tab(indicator_name)

    def _create_placeholder_tab(self, indicator_name: str):
        """创建无参数指标占位 tab（R282）"""
        from PyQt5.QtWidgets import QWidget
        try:
            from core.indicator_adapter import get_talib_chinese_name
            chinese_name = get_talib_chinese_name(indicator_name)
        except Exception:
            chinese_name = indicator_name
        placeholder = QWidget()
        ph_layout = QVBoxLayout(placeholder)
        info_label = QLabel(f"「{indicator_name} ({chinese_name})」无可用参数配置\n该指标使用默认参数渲染。")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("color: #888; font-size: 13px;")
        ph_layout.addWidget(info_label)
        self.tab_widget.addTab(placeholder, indicator_name)

    def _create_indicator_tab(self, indicator_name: str, config: Dict[str, Any]):
        """创建指标参数设置选项卡"""
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        # 创建参数设置小部件
        param_widget = IndicatorParamWidget(indicator_name, config)
        param_widget.param_changed.connect(self._on_param_changed)

        scroll_area.setWidget(param_widget)

        # 添加到选项卡
        self.tab_widget.addTab(scroll_area, indicator_name)
        self.param_widgets[indicator_name] = param_widget

    def _on_param_changed(self, indicator_name: str, param_name: str, value: Any):
        """处理参数变化"""
        if indicator_name not in self.indicator_params:
            self.indicator_params[indicator_name] = {}

        self.indicator_params[indicator_name][param_name] = value
        logger.debug(
            f"Parameter changed: {indicator_name}.{param_name} = {value}")

    def _reset_all_params(self):
        """重置所有参数为默认值"""
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要将所有参数重置为默认值吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                for widget in self.param_widgets.values():
                    if hasattr(widget, 'reset_to_default'):
                        widget.reset_to_default()
                    elif hasattr(widget, 'widget') and hasattr(widget.widget(), 'reset_to_default'):
                        # 处理可能被QScrollArea包装的情况
                        widget.widget().reset_to_default()
                self.indicator_params.clear()
                QMessageBox.information(self, "成功", "所有参数已重置为默认值")
            except Exception as e:
                logger.error(f"重置参数失败: {e}")
                QMessageBox.warning(self, "警告", f"部分参数重置失败: {e}")

    def _load_preset(self):
        """加载预设参数"""
        try:
            import os
            import json
            from PyQt5.QtWidgets import QFileDialog

            # 选择预设文件
            preset_dir = "configs/indicator_presets"
            if not os.path.exists(preset_dir):
                os.makedirs(preset_dir, exist_ok=True)

            filepath, _ = QFileDialog.getOpenFileName(
                self,
                "选择指标预设文件",
                preset_dir,
                "JSON文件 (*.json)"
            )

            if not filepath:
                return

            # 加载预设
            with open(filepath, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)

            # 应用预设参数
            self.set_params(preset_data.get('parameters', {}))

            QMessageBox.information(
                self, "成功", f"预设 '{preset_data.get('name', '未命名')}' 已加载")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载预设失败: {str(e)}")

    def _save_preset(self):
        """保存当前参数为预设"""
        try:
            from datetime import datetime
            from PyQt5.QtWidgets import QInputDialog

            # 输入预设名称
            name, ok = QInputDialog.getText(self, "保存预设", "请输入预设名称:")
            if not ok or not name.strip():
                return

            # 创建预设目录
            preset_dir = "configs/indicator_presets"
            os.makedirs(preset_dir, exist_ok=True)

            # 构建预设数据
            preset_data = {
                'name': name.strip(),
                'description': f"指标参数预设 - {', '.join(self.selected_indicators)}",
                'created_time': datetime.now().isoformat(),
                'parameters': self.get_params()
            }

            # 保存到文件
            filename = f"{name.strip().replace(' ', '_')}.json"
            filepath = os.path.join(preset_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, ensure_ascii=False, indent=2)

            QMessageBox.information(self, "成功", f"预设 '{name}' 已保存")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存预设失败: {str(e)}")

    def _accept(self):
        """确认并关闭对话框"""
        try:
            # 收集所有参数，使用已修复的get_params方法
            all_params = self.get_params()

            # 发送参数变化信号
            self.params_changed.emit(all_params)

            logger.info(f"Indicator parameters updated: {all_params}")
            self.accept()
        except Exception as e:
            logger.error(f"确认参数设置失败: {e}")
            QMessageBox.warning(self, "警告", f"确认参数设置失败: {e}")

    def get_params(self) -> Dict[str, Dict[str, Any]]:
        """获取所有参数"""
        params = {}
        for indicator_name, widget in self.param_widgets.items():
            try:
                if hasattr(widget, 'get_params'):
                    params[indicator_name] = widget.get_params()
                elif hasattr(widget, 'widget') and hasattr(widget.widget(), 'get_params'):
                    # 处理可能被QScrollArea包装的情况
                    params[indicator_name] = widget.widget().get_params()
            except Exception as e:
                logger.error(f"获取参数失败 {indicator_name}: {e}")
        return params

    def set_params(self, params: Dict[str, Dict[str, Any]]):
        """设置参数"""
        for indicator_name, indicator_params in params.items():
            if indicator_name in self.param_widgets:
                try:
                    widget = self.param_widgets[indicator_name]
                    if hasattr(widget, 'set_params'):
                        widget.set_params(indicator_params)
                    elif hasattr(widget, 'widget') and hasattr(widget.widget(), 'set_params'):
                        # 处理可能被QScrollArea包装的情况
                        widget.widget().set_params(indicator_params)
                except Exception as e:
                    logger.error(f"设置参数失败 {indicator_name}: {e}")

def main():
    """测试函数"""
    app = QApplication(sys.argv)

    # 测试指标参数对话框
    selected_indicators = ['MA', 'MACD', 'RSI', 'BOLL']
    dialog = IndicatorParamsDialog(selected_indicators)

    def on_params_changed(params):
        print("参数变化:", params)

    dialog.params_changed.connect(on_params_changed)
    dialog.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
