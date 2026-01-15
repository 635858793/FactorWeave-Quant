#!/usr/bin/env python3
"""
指标选择对话框

提供用户友好的指标选择界面，支持：
- 按类别显示指标
- 指标搜索功能
- 指标预览功能
- 批量选择支持
- 指标后端选择
- 参数配置
"""

from core.indicator_extensions import IndicatorCategory, ParameterType
import sys
import os
from typing import Dict, List, Any, Optional, Tuple
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTreeWidget, QTreeWidgetItem, QLineEdit, QTextEdit,
    QPushButton, QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QGroupBox, QSplitter, QTabWidget, QScrollArea,
    QFrame, QMessageBox, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QPalette

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


class IndicatorPreviewThread(QThread):
    """指标预览计算线程"""
    preview_ready = pyqtSignal(str, object)  # indicator_name, result_data
    preview_error = pyqtSignal(str, str)     # indicator_name, error_message

    def __init__(self, service, indicator_name, sample_data, params):
        super().__init__()
        self.service = service
        self.indicator_name = indicator_name
        self.sample_data = sample_data
        self.params = params

    def run(self):
        try:
            result_df, metadata = self.service.calculate_indicator_enhanced(
                self.indicator_name, self.sample_data, self.params
            )
            self.preview_ready.emit(self.indicator_name, {
                'data': result_df,
                'metadata': metadata
            })
        except Exception as e:
            self.preview_error.emit(self.indicator_name, str(e))


class ParameterWidget(QFrame):
    """参数配置组件"""

    def __init__(self, param_def, parent=None):
        super().__init__(parent)
        self.param_def = param_def
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # 参数名称标签
        name_label = QLabel(f"{self.param_def.name}:")
        name_label.setMinimumWidth(100)
        layout.addWidget(name_label)

        # 根据参数类型创建输入控件
        if self.param_def.type == ParameterType.INTEGER:
            self.input_widget = QSpinBox()
            if self.param_def.min_value is not None:
                self.input_widget.setMinimum(int(self.param_def.min_value))
            if self.param_def.max_value is not None:
                self.input_widget.setMaximum(int(self.param_def.max_value))
            self.input_widget.setValue(int(self.param_def.default_value))

        elif self.param_def.type == ParameterType.FLOAT:
            self.input_widget = QDoubleSpinBox()
            self.input_widget.setDecimals(4)
            if self.param_def.min_value is not None:
                self.input_widget.setMinimum(float(self.param_def.min_value))
            if self.param_def.max_value is not None:
                self.input_widget.setMaximum(float(self.param_def.max_value))
            self.input_widget.setValue(float(self.param_def.default_value))

        elif self.param_def.type == ParameterType.BOOLEAN:
            self.input_widget = QCheckBox()
            self.input_widget.setChecked(bool(self.param_def.default_value))

        elif self.param_def.type == ParameterType.STRING:
            self.input_widget = QLineEdit()
            self.input_widget.setText(str(self.param_def.default_value))

        elif self.param_def.type == ParameterType.ENUM:
            self.input_widget = QComboBox()
            if hasattr(self.param_def, 'options') and self.param_def.options:
                for option in self.param_def.options:
                    self.input_widget.addItem(str(option))
                # 设置默认值
                default_index = self.input_widget.findText(str(self.param_def.default_value))
                if default_index >= 0:
                    self.input_widget.setCurrentIndex(default_index)

        else:
            # 默认使用文本输入
            self.input_widget = QLineEdit()
            self.input_widget.setText(str(self.param_def.default_value))

        layout.addWidget(self.input_widget)

        # 描述标签
        if self.param_def.description:
            desc_label = QLabel(f"({self.param_def.description})")
            desc_label.setStyleSheet("color: gray; font-size: 10px;")
            layout.addWidget(desc_label)

        layout.addStretch()

    def get_value(self):
        """获取参数值"""
        if isinstance(self.input_widget, QSpinBox):
            return self.input_widget.value()
        elif isinstance(self.input_widget, QDoubleSpinBox):
            return self.input_widget.value()
        elif isinstance(self.input_widget, QCheckBox):
            return self.input_widget.isChecked()
        elif isinstance(self.input_widget, QLineEdit):
            return self.input_widget.text()
        elif isinstance(self.input_widget, QComboBox):
            return self.input_widget.currentText()
        else:
            return None

    def set_value(self, value):
        """设置参数值"""
        if isinstance(self.input_widget, QSpinBox):
            self.input_widget.setValue(int(value))
        elif isinstance(self.input_widget, QDoubleSpinBox):
            self.input_widget.setValue(float(value))
        elif isinstance(self.input_widget, QCheckBox):
            self.input_widget.setChecked(bool(value))
        elif isinstance(self.input_widget, QLineEdit):
            self.input_widget.setText(str(value))
        elif isinstance(self.input_widget, QComboBox):
            index = self.input_widget.findText(str(value))
            if index >= 0:
                self.input_widget.setCurrentIndex(index)


class IndicatorSelectionDialog(QDialog):
    """指标选择对话框"""

    def __init__(self, parent=None, service=None, sample_data=None):
        super().__init__(parent)
        self.service = service or UnifiedIndicatorServiceEnhanced()
        self.sample_data = sample_data
        self.selected_indicators = []
        self.parameter_widgets = {}
        self.preview_thread = None

        self.setup_ui()
        self.load_indicators()
        self.setup_connections()

    def setup_ui(self):
        """设置用户界面"""
        self.setWindowTitle("指标选择器")
        self.setMinimumSize(1000, 700)

        # 主布局
        main_layout = QVBoxLayout(self)

        # 顶部工具栏
        toolbar_layout = QHBoxLayout()

        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索指标...")
        toolbar_layout.addWidget(QLabel("搜索:"))
        toolbar_layout.addWidget(self.search_edit)

        # 后端选择
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["所有后端", "FactorWeave-Quant", "TA-Lib", "自定义"])
        toolbar_layout.addWidget(QLabel("后端:"))
        toolbar_layout.addWidget(self.backend_combo)

        # 类别筛选
        self.category_combo = QComboBox()
        self.category_combo.addItem("所有类别")
        for category in IndicatorCategory:
            self.category_combo.addItem(category.value.title())
        toolbar_layout.addWidget(QLabel("类别:"))
        toolbar_layout.addWidget(self.category_combo)

        toolbar_layout.addStretch()
        main_layout.addLayout(toolbar_layout)

        # 主要内容区域
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：指标树
        left_widget = QGroupBox("可用指标")
        left_layout = QVBoxLayout(left_widget)

        self.indicator_tree = QTreeWidget()
        self.indicator_tree.setHeaderLabels(["指标名称", "类别", "后端", "描述"])
        self.indicator_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        left_layout.addWidget(self.indicator_tree)

        # 指标操作按钮
        indicator_buttons_layout = QHBoxLayout()
        self.add_button = QPushButton("添加选中")
        self.preview_button = QPushButton("预览")
        self.info_button = QPushButton("详细信息")
        indicator_buttons_layout.addWidget(self.add_button)
        indicator_buttons_layout.addWidget(self.preview_button)
        indicator_buttons_layout.addWidget(self.info_button)
        indicator_buttons_layout.addStretch()
        left_layout.addLayout(indicator_buttons_layout)

        splitter.addWidget(left_widget)

        # 右侧：选中的指标和参数配置
        right_widget = QGroupBox("已选指标")
        right_layout = QVBoxLayout(right_widget)

        # 选中指标列表
        self.selected_table = QTableWidget()
        self.selected_table.setColumnCount(4)
        self.selected_table.setHorizontalHeaderLabels(["指标名称", "后端", "参数", "操作"])
        self.selected_table.horizontalHeader().setStretchLastSection(True)
        right_layout.addWidget(self.selected_table)

        # 参数配置区域
        params_group = QGroupBox("参数配置")
        params_layout = QVBoxLayout(params_group)

        self.params_scroll = QScrollArea()
        self.params_widget = QFrame()
        self.params_layout = QVBoxLayout(self.params_widget)
        self.params_scroll.setWidget(self.params_widget)
        self.params_scroll.setWidgetResizable(True)
        params_layout.addWidget(self.params_scroll)

        right_layout.addWidget(params_group)

        # 预览区域
        preview_group = QGroupBox("指标预览")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_text = QTextEdit()
        self.preview_text.setMaximumHeight(150)
        self.preview_text.setReadOnly(True)
        preview_layout.addWidget(self.preview_text)

        self.preview_progress = QProgressBar()
        self.preview_progress.setVisible(False)
        preview_layout.addWidget(self.preview_progress)

        right_layout.addWidget(preview_group)

        splitter.addWidget(right_widget)
        splitter.setSizes([400, 600])

        main_layout.addWidget(splitter)

        # 底部按钮
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        self.reset_button = QPushButton("重置")

        button_layout.addStretch()
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)

        main_layout.addLayout(button_layout)

    def setup_connections(self):
        """设置信号连接"""
        self.search_edit.textChanged.connect(self.filter_indicators)
        self.backend_combo.currentTextChanged.connect(self.filter_indicators)
        self.category_combo.currentTextChanged.connect(self.filter_indicators)

        self.indicator_tree.itemSelectionChanged.connect(self.on_indicator_selection_changed)
        self.indicator_tree.itemDoubleClicked.connect(self.add_selected_indicators)

        self.add_button.clicked.connect(self.add_selected_indicators)
        self.preview_button.clicked.connect(self.preview_selected_indicator)
        self.info_button.clicked.connect(self.show_indicator_info)

        self.selected_table.itemSelectionChanged.connect(self.on_selected_indicator_changed)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.reset_button.clicked.connect(self.reset_selection)

    def load_indicators(self):
        """加载可用指标"""
        self.indicator_tree.clear()

        try:
            # 获取所有注册的插件
            registered_plugins = self.service.get_registered_plugins()
            print(f"已注册插件: {registered_plugins}")

            # 按类别组织指标
            category_items = {}

            for plugin_id in registered_plugins:
                try:
                    plugin_adapter = self.service._indicator_plugins[plugin_id]
                    supported_indicators = plugin_adapter.get_supported_indicators()
                    print(f"插件 {plugin_id} 支持的指标数量: {len(supported_indicators)}")

                    for indicator_name in supported_indicators:
                        try:
                            metadata = plugin_adapter.get_indicator_metadata(indicator_name)
                            if metadata:
                                # 获取或创建类别节点
                                category_name = metadata.category.value.title()
                                if category_name not in category_items:
                                    category_item = QTreeWidgetItem([category_name])
                                    category_item.setFont(0, QFont("", -1, QFont.Bold))
                                    self.indicator_tree.addTopLevelItem(category_item)
                                    category_items[category_name] = category_item

                                # 创建指标节点
                                indicator_item = QTreeWidgetItem([
                                    metadata.display_name,
                                    category_name,
                                    plugin_id,
                                    metadata.description
                                ])
                                indicator_item.setData(0, Qt.UserRole, {
                                    'name': indicator_name,
                                    'plugin_id': plugin_id,
                                    'metadata': metadata
                                })
                                category_items[category_name].addChild(indicator_item)
                            else:
                                # 当metadata为None时，创建一个基本的指标节点
                                print(f"指标 {indicator_name} 元数据缺失，创建基本节点")
                                # 使用默认类别
                                default_category = "其他"
                                if default_category not in category_items:
                                    category_item = QTreeWidgetItem([default_category])
                                    category_item.setFont(0, QFont("", -1, QFont.Bold))
                                    self.indicator_tree.addTopLevelItem(category_item)
                                    category_items[default_category] = category_item

                                # 创建基本指标节点
                                indicator_item = QTreeWidgetItem([
                                    indicator_name,
                                    default_category,
                                    plugin_id,
                                    "无描述"
                                ])
                                indicator_item.setData(0, Qt.UserRole, {
                                    'name': indicator_name,
                                    'plugin_id': plugin_id,
                                    'metadata': None
                                })
                                category_items[default_category].addChild(indicator_item)

                        except Exception as e:
                            print(f"加载指标元数据失败 {indicator_name}: {e}")
                            continue

                except Exception as e:
                    print(f"加载插件指标失败 {plugin_id}: {e}")
                    continue

            # 展开所有类别
            self.indicator_tree.expandAll()

            # 调整列宽
            for i in range(self.indicator_tree.columnCount()):
                self.indicator_tree.resizeColumnToContents(i)

        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载指标失败: {e}")

    def filter_indicators(self):
        """筛选指标"""
        search_text = self.search_edit.text().lower()
        backend_filter = self.backend_combo.currentText()
        category_filter = self.category_combo.currentText()

        # 遍历所有项目并设置可见性
        for i in range(self.indicator_tree.topLevelItemCount()):
            category_item = self.indicator_tree.topLevelItem(i)
            category_visible = False

            for j in range(category_item.childCount()):
                indicator_item = category_item.child(j)
                data = indicator_item.data(0, Qt.UserRole)

                # 检查搜索文本
                text_match = (search_text == "" or
                              search_text in indicator_item.text(0).lower() or
                              search_text in indicator_item.text(3).lower())

                # 检查后端筛选
                backend_match = (backend_filter == "所有后端" or
                                 backend_filter == indicator_item.text(2))

                # 检查类别筛选
                category_match = (category_filter == "所有类别" or
                                  category_filter == indicator_item.text(1))

                visible = text_match and backend_match and category_match
                indicator_item.setHidden(not visible)

                if visible:
                    category_visible = True

            category_item.setHidden(not category_visible)

    def on_indicator_selection_changed(self):
        """指标选择改变"""
        selected_items = self.indicator_tree.selectedItems()

        # 更新按钮状态
        has_selection = len(selected_items) > 0 and all(item.data(0, Qt.UserRole) for item in selected_items)
        self.add_button.setEnabled(has_selection)
        self.preview_button.setEnabled(len(selected_items) == 1 and selected_items[0].data(0, Qt.UserRole))
        self.info_button.setEnabled(len(selected_items) == 1 and selected_items[0].data(0, Qt.UserRole))

    def add_selected_indicators(self):
        """添加选中的指标"""
        selected_items = self.indicator_tree.selectedItems()

        for item in selected_items:
            data = item.data(0, Qt.UserRole)
            if data:
                indicator_name = data['name']
                plugin_id = data['plugin_id']
                metadata = data['metadata']

                # 检查是否已经添加
                if any(ind['name'] == indicator_name for ind in self.selected_indicators):
                    continue

                # 添加到选中列表
                indicator_info = {
                    'name': indicator_name,
                    'display_name': metadata.display_name,
                    'plugin_id': plugin_id,
                    'metadata': metadata,
                    'parameters': {param.name: param.default_value for param in metadata.parameters}
                }

                self.selected_indicators.append(indicator_info)

        self.update_selected_table()

    def update_selected_table(self):
        """更新选中指标表格"""
        self.selected_table.setRowCount(len(self.selected_indicators))

        for i, indicator in enumerate(self.selected_indicators):
            # 指标名称
            name_item = QTableWidgetItem(indicator['display_name'])
            name_item.setData(Qt.UserRole, indicator)
            self.selected_table.setItem(i, 0, name_item)

            # 后端
            backend_item = QTableWidgetItem(indicator['plugin_id'])
            self.selected_table.setItem(i, 1, backend_item)

            # 参数
            param_count = len(indicator['parameters'])
            param_item = QTableWidgetItem(f"{param_count} 个参数")
            self.selected_table.setItem(i, 2, param_item)

            # 操作按钮
            remove_button = QPushButton("移除")
            remove_button.clicked.connect(lambda checked, idx=i: self.remove_indicator(idx))
            self.selected_table.setCellWidget(i, 3, remove_button)

    def remove_indicator(self, index):
        """移除指标"""
        if 0 <= index < len(self.selected_indicators):
            self.selected_indicators.pop(index)
            self.update_selected_table()

    def on_selected_indicator_changed(self):
        """选中指标改变，更新参数配置界面"""
        current_row = self.selected_table.currentRow()

        # 清空现有参数界面
        for widget in self.parameter_widgets.values():
            widget.setParent(None)
        self.parameter_widgets.clear()

        if current_row >= 0 and current_row < len(self.selected_indicators):
            indicator = self.selected_indicators[current_row]
            metadata = indicator['metadata']

            # 创建参数配置界面
            for param_def in metadata.parameters:
                param_widget = ParameterWidget(param_def)
                param_widget.set_value(indicator['parameters'].get(param_def.name, param_def.default_value))

                # 连接值改变信号
                if hasattr(param_widget.input_widget, 'valueChanged'):
                    param_widget.input_widget.valueChanged.connect(
                        lambda: self.update_parameter_value(current_row, param_def.name, param_widget.get_value())
                    )
                elif hasattr(param_widget.input_widget, 'textChanged'):
                    param_widget.input_widget.textChanged.connect(
                        lambda: self.update_parameter_value(current_row, param_def.name, param_widget.get_value())
                    )
                elif hasattr(param_widget.input_widget, 'toggled'):
                    param_widget.input_widget.toggled.connect(
                        lambda: self.update_parameter_value(current_row, param_def.name, param_widget.get_value())
                    )
                elif hasattr(param_widget.input_widget, 'currentTextChanged'):
                    param_widget.input_widget.currentTextChanged.connect(
                        lambda: self.update_parameter_value(current_row, param_def.name, param_widget.get_value())
                    )

                self.params_layout.addWidget(param_widget)
                self.parameter_widgets[param_def.name] = param_widget

            # 添加弹性空间
            self.params_layout.addStretch()

    def update_parameter_value(self, indicator_index, param_name, value):
        """更新参数值"""
        if 0 <= indicator_index < len(self.selected_indicators):
            self.selected_indicators[indicator_index]['parameters'][param_name] = value

    def preview_selected_indicator(self):
        """预览选中的指标"""
        selected_items = self.indicator_tree.selectedItems()
        if len(selected_items) != 1:
            return

        item = selected_items[0]
        data = item.data(0, Qt.UserRole)
        if not data or not self.sample_data:
            QMessageBox.information(self, "提示", "无法预览：缺少样本数据")
            return

        indicator_name = data['name']
        metadata = data['metadata']

        # 使用默认参数
        params = {param.name: param.default_value for param in metadata.parameters}

        # 显示进度条
        self.preview_progress.setVisible(True)
        self.preview_progress.setRange(0, 0)  # 不确定进度
        self.preview_text.setText("正在计算预览...")

        # 启动预览线程
        self.preview_thread = IndicatorPreviewThread(
            self.service, indicator_name, self.sample_data, params
        )
        self.preview_thread.preview_ready.connect(self.on_preview_ready)
        self.preview_thread.preview_error.connect(self.on_preview_error)
        self.preview_thread.start()

    def on_preview_ready(self, indicator_name, result):
        """预览计算完成"""
        self.preview_progress.setVisible(False)

        data = result['data']
        metadata = result['metadata']

        # 显示预览结果
        preview_text = f"指标: {indicator_name}\n"
        preview_text += f"后端: {metadata.get('selected_plugin', 'Unknown')}\n"
        preview_text += f"计算时间: {metadata.get('calculation_time_ms', 0):.2f}ms\n"
        preview_text += f"数据点数: {len(data)}\n"

        # 显示新增的列
        original_columns = ['open', 'high', 'low', 'close', 'volume', 'amount']
        new_columns = [col for col in data.columns if col not in original_columns]
        if new_columns:
            preview_text += f"新增列: {', '.join(new_columns)}\n"

            # 显示最后几个值
            for col in new_columns[:3]:  # 最多显示3列
                last_values = data[col].dropna().tail(5)
                if not last_values.empty:
                    preview_text += f"{col} 最后5个值: {list(last_values.round(4))}\n"

        self.preview_text.setText(preview_text)

    def on_preview_error(self, indicator_name, error_message):
        """预览计算错误"""
        self.preview_progress.setVisible(False)
        self.preview_text.setText(f"预览失败: {error_message}")

    def show_indicator_info(self):
        """显示指标详细信息"""
        selected_items = self.indicator_tree.selectedItems()
        if len(selected_items) != 1:
            return

        item = selected_items[0]
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        metadata = data['metadata']

        info_text = f"指标名称: {metadata.display_name}\n"
        info_text += f"内部名称: {data['name']}\n"
        info_text += f"类别: {metadata.category.value}\n"
        info_text += f"后端: {data['plugin_id']}\n"
        info_text += f"描述: {metadata.description}\n"
        info_text += f"作者: {metadata.author}\n"
        info_text += f"版本: {metadata.version}\n"

        if metadata.parameters:
            info_text += "\n参数:\n"
            for param in metadata.parameters:
                info_text += f"  {param.name} ({param.type.value}): {param.description}\n"
                info_text += f"    默认值: {param.default_value}\n"
                if param.min_value is not None or param.max_value is not None:
                    info_text += f"    范围: [{param.min_value}, {param.max_value}]\n"

        if metadata.output_columns:
            info_text += f"\n输出列: {', '.join(metadata.output_columns)}\n"

        if metadata.tags:
            info_text += f"标签: {', '.join(metadata.tags)}\n"

        QMessageBox.information(self, "指标信息", info_text)

    def reset_selection(self):
        """重置选择"""
        self.selected_indicators.clear()
        self.update_selected_table()

        # 清空参数界面
        for widget in self.parameter_widgets.values():
            widget.setParent(None)
        self.parameter_widgets.clear()

        # 清空预览
        self.preview_text.clear()

    def get_selected_indicators(self):
        """获取选中的指标配置"""
        return self.selected_indicators.copy()


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta

    app = QApplication(sys.argv)

    # 创建样本数据
    dates = pd.date_range(start=datetime.now() - timedelta(days=100), periods=100, freq='D')
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(100) * 0.5)

    sample_data = pd.DataFrame({
        'open': prices * (1 + np.random.uniform(-0.02, 0.02, 100)),
        'high': prices * (1 + np.random.uniform(0, 0.05, 100)),
        'low': prices * (1 - np.random.uniform(0, 0.05, 100)),
        'close': prices,
        'volume': np.random.uniform(1000000, 10000000, 100),
        'amount': prices * np.random.uniform(1000000, 10000000, 100)
    }, index=dates)

    # 创建对话框
    dialog = IndicatorSelectionDialog(sample_data=sample_data)

    if dialog.exec_() == QDialog.Accepted:
        selected = dialog.get_selected_indicators()
        print(f"选中了 {len(selected)} 个指标:")
        for indicator in selected:
            print(f"  {indicator['display_name']} ({indicator['plugin_id']})")
            print(f"    参数: {indicator['parameters']}")

    sys.exit(app.exec_())
