#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI选股策略管理对话框

提供AI选股策略的完整管理功能：
- 策略列表展示
- 策略创建、编辑、删除
- 策略模板选择
- 策略配置验证
- 策略性能监控

作者: FactorWeave-Quant团队
版本: 1.0
"""

import sys
import json
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import asdict

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QLabel, QTextEdit, QLineEdit,
    QGroupBox, QFormLayout, QPushButton, QScrollArea, QSplitter,
    QHeaderView, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QFileDialog, QMessageBox, QProgressDialog, QInputDialog,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QProgressBar, QFrame, QGridLayout, QSlider, QDateEdit,
    QApplication, QMenu, QAction, QSizePolicy, QToolButton,
    QStackedWidget, QButtonGroup, QRadioButton
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QTimer, QThread, QDateTime, QSettings, QMimeData
)
from PyQt5.QtGui import (
    QFont, QColor, QPalette, QPixmap, QIcon, QPainter, QBrush, QDrag
)

try:
    from core.services.database_service import DatabaseService
    from core.containers.service_container import get_service_container
    from loguru import logger
    CORE_AVAILABLE = True
except ImportError as e:
    logger = None
    CORE_AVAILABLE = False
    print(f"核心服务不可用: {e}")

logger = logger.bind(module=__name__) if logger else None


class StrategyTemplateManager:
    """策略模板管理器"""

    TEMPLATES = {
        "aggressive_growth": {
            "name": "激进成长策略",
            "description": "追求高收益的成长策略，适合风险承受能力强的投资者",
            "strategy_type": "growth",
            "parameters": {
                "revenue_growth_threshold": 0.3,
                "earnings_growth_threshold": 0.25,
                "pe_ratio_max": 30
            },
            "weight_config": {
                "equal_weight": False,
                "custom_weights": {
                    "revenue_growth": 0.4,
                    "earnings_growth": 0.3,
                    "pe_ratio": 0.2,
                    "other": 0.1
                }
            },
            "risk_config": {
                "max_position_size": 0.15,
                "max_drawdown": 0.2,
                "volatility_limit": 0.3
            }
        },
        "conservative_value": {
            "name": "稳健价值策略",
            "description": "注重安全的价值策略，适合稳健型投资者",
            "strategy_type": "value",
            "parameters": {
                "pe_threshold": 15,
                "pb_threshold": 2.0,
                "dividend_yield_threshold": 0.03
            },
            "weight_config": {
                "equal_weight": True
            },
            "risk_config": {
                "max_position_size": 0.08,
                "max_drawdown": 0.1,
                "volatility_limit": 0.15
            }
        },
        "technical_momentum": {
            "name": "技术动量策略",
            "description": "基于技术指标和价格动量的选股策略",
            "strategy_type": "technical",
            "parameters": {
                "indicators": ["MA", "MACD", "RSI", "KDJ"],
                "lookback_period": 20,
                "momentum_threshold": 0.05
            },
            "weight_config": {
                "equal_weight": True
            },
            "risk_config": {
                "max_position_size": 0.1,
                "max_drawdown": 0.15,
                "volatility_limit": 0.2
            }
        },
        "quality_focus": {
            "name": "质量优选策略",
            "description": "基于财务质量指标的选股策略",
            "strategy_type": "quality",
            "parameters": {
                "roe_threshold": 0.15,
                "debt_to_equity_threshold": 0.5,
                "current_ratio_threshold": 1.5
            },
            "weight_config": {
                "equal_weight": False,
                "custom_weights": {
                    "roe": 0.4,
                    "debt_ratio": 0.3,
                    "current_ratio": 0.2,
                    "other": 0.1
                }
            },
            "risk_config": {
                "max_position_size": 0.1,
                "max_drawdown": 0.12,
                "volatility_limit": 0.18
            }
        },
        "dividend_income": {
            "name": "股息收益策略",
            "description": "基于股息收益的选股策略，适合追求稳定收益的投资者",
            "strategy_type": "dividend",
            "parameters": {
                "dividend_yield_threshold": 0.04,
                "payout_ratio_threshold": 0.6,
                "dividend_growth_threshold": 0.05
            },
            "weight_config": {
                "equal_weight": True
            },
            "risk_config": {
                "max_position_size": 0.08,
                "max_drawdown": 0.1,
                "volatility_limit": 0.12
            }
        }
    }

    @classmethod
    def get_template_names(cls) -> List[str]:
        """获取所有模板名称"""
        return list(cls.TEMPLATES.keys())

    @classmethod
    def get_template(cls, template_name: str) -> Optional[Dict[str, Any]]:
        """获取策略模板"""
        return cls.TEMPLATES.get(template_name)

    @classmethod
    def get_template_display_names(cls) -> Dict[str, str]:
        """获取模板显示名称映射"""
        return {
            "aggressive_growth": "激进成长策略",
            "conservative_value": "稳健价值策略",
            "technical_momentum": "技术动量策略",
            "quality_focus": "质量优选策略",
            "dividend_income": "股息收益策略"
        }


class StrategyConfigValidator:
    """策略配置验证器"""

    @staticmethod
    def validate_parameters(strategy_type: str, parameters: Dict) -> Tuple[bool, List[str]]:
        """验证策略参数"""
        errors = []

        if strategy_type == "technical":
            if "indicators" not in parameters:
                errors.append("技术分析策略必须包含indicators参数")
            elif not isinstance(parameters["indicators"], list):
                errors.append("indicators参数必须是列表")
            elif len(parameters["indicators"]) == 0:
                errors.append("indicators参数不能为空")

        elif strategy_type == "value":
            if "pe_threshold" in parameters:
                if parameters["pe_threshold"] <= 0:
                    errors.append("pe_threshold必须大于0")
            if "pb_threshold" in parameters:
                if parameters["pb_threshold"] <= 0:
                    errors.append("pb_threshold必须大于0")

        elif strategy_type == "growth":
            if "revenue_growth_threshold" in parameters:
                if not (0 <= parameters["revenue_growth_threshold"] <= 1):
                    errors.append("revenue_growth_threshold必须在0和1之间")
            if "earnings_growth_threshold" in parameters:
                if not (0 <= parameters["earnings_growth_threshold"] <= 1):
                    errors.append("earnings_growth_threshold必须在0和1之间")

        elif strategy_type == "quality":
            if "roe_threshold" in parameters:
                if not (0 <= parameters["roe_threshold"] <= 1):
                    errors.append("roe_threshold必须在0和1之间")
            if "debt_to_equity_threshold" in parameters:
                if not (0 <= parameters["debt_to_equity_threshold"] <= 1):
                    errors.append("debt_to_equity_threshold必须在0和1之间")

        elif strategy_type == "dividend":
            if "dividend_yield_threshold" in parameters:
                if not (0 <= parameters["dividend_yield_threshold"] <= 1):
                    errors.append("dividend_yield_threshold必须在0和1之间")
            if "payout_ratio_threshold" in parameters:
                if not (0 <= parameters["payout_ratio_threshold"] <= 1):
                    errors.append("payout_ratio_threshold必须在0和1之间")

        return len(errors) == 0, errors

    @staticmethod
    def validate_weight_config(weight_config: Dict) -> Tuple[bool, List[str]]:
        """验证权重配置"""
        errors = []

        if "custom_weights" in weight_config:
            custom_weights = weight_config["custom_weights"]
            if not isinstance(custom_weights, dict):
                errors.append("custom_weights必须是字典")
            else:
                total_weight = sum(custom_weights.values())
                if abs(total_weight - 1.0) > 0.01:
                    errors.append(f"权重总和必须为1.0，当前为{total_weight:.2f}")

        return len(errors) == 0, errors

    @staticmethod
    def validate_risk_config(risk_config: Dict) -> Tuple[bool, List[str]]:
        """验证风险配置"""
        errors = []

        if "max_position_size" in risk_config:
            if not (0 < risk_config["max_position_size"] <= 1):
                errors.append("max_position_size必须在0和1之间")

        if "max_drawdown" in risk_config:
            if not (0 < risk_config["max_drawdown"] <= 1):
                errors.append("max_drawdown必须在0和1之间")

        if "volatility_limit" in risk_config:
            if not (0 < risk_config["volatility_limit"] <= 1):
                errors.append("volatility_limit必须在0和1之间")

        return len(errors) == 0, errors


class StrategyEditorWidget(QWidget):
    """策略编辑组件"""

    strategy_changed = pyqtSignal(dict)

    def __init__(self, strategy_data: Optional[Dict] = None, parent=None):
        super().__init__(parent)
        self.strategy_data = strategy_data or {}
        self.setup_ui()
        self.load_strategy_data()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # 基础信息组
        basic_group = QGroupBox("基础信息")
        basic_layout = QFormLayout(basic_group)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("策略名称")
        basic_layout.addRow("策略名称:", self.name_edit)

        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("策略描述")
        basic_layout.addRow("策略描述:", self.description_edit)

        self.strategy_type_combo = QComboBox()
        self.strategy_type_combo.addItems([
            "technical", "momentum", "value", "growth", "quality", "dividend", "quantitative", "hybrid"
        ])
        self.strategy_type_combo.currentTextChanged.connect(self.on_strategy_type_changed)
        basic_layout.addRow("策略类型:", self.strategy_type_combo)

        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("标签（逗号分隔）")
        basic_layout.addRow("标签:", self.tags_edit)

        scroll_layout.addWidget(basic_group)

        # 参数配置组
        params_group = QGroupBox("参数配置")
        params_layout = QVBoxLayout(params_group)

        self.params_edit = QTextEdit()
        self.params_edit.setPlaceholderText('{"indicators": ["MA", "MACD"], "lookback_period": 20}')
        self.params_edit.setMaximumHeight(150)
        params_layout.addWidget(self.params_edit)

        scroll_layout.addWidget(params_group)

        # 权重配置组
        weight_group = QGroupBox("权重配置")
        weight_layout = QVBoxLayout(weight_group)

        self.equal_weight_check = QCheckBox("等权重分配")
        self.equal_weight_check.setChecked(True)
        self.equal_weight_check.toggled.connect(self.on_equal_weight_toggled)
        weight_layout.addWidget(self.equal_weight_check)

        self.weight_edit = QTextEdit()
        self.weight_edit.setPlaceholderText('{"MA": 0.3, "MACD": 0.3, "RSI": 0.2, "KDJ": 0.2}')
        self.weight_edit.setMaximumHeight(100)
        self.weight_edit.setEnabled(False)
        weight_layout.addWidget(self.weight_edit)

        scroll_layout.addWidget(weight_group)

        # 风险配置组
        risk_group = QGroupBox("风险配置")
        risk_layout = QFormLayout(risk_group)

        self.max_position_spin = QDoubleSpinBox()
        self.max_position_spin.setRange(0.01, 1.0)
        self.max_position_spin.setSingleStep(0.01)
        self.max_position_spin.setValue(0.1)
        risk_layout.addRow("最大仓位比例:", self.max_position_spin)

        self.max_drawdown_spin = QDoubleSpinBox()
        self.max_drawdown_spin.setRange(0.01, 1.0)
        self.max_drawdown_spin.setSingleStep(0.01)
        self.max_drawdown_spin.setValue(0.15)
        risk_layout.addRow("最大回撤:", self.max_drawdown_spin)

        self.volatility_spin = QDoubleSpinBox()
        self.volatility_spin.setRange(0.01, 1.0)
        self.volatility_spin.setSingleStep(0.01)
        self.volatility_spin.setValue(0.2)
        risk_layout.addRow("波动率限制:", self.volatility_spin)

        scroll_layout.addWidget(risk_group)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.validate_btn = QPushButton("验证配置")
        self.validate_btn.clicked.connect(self.validate_config)
        button_layout.addWidget(self.validate_btn)

        self.apply_btn = QPushButton("应用更改")
        self.apply_btn.clicked.connect(self.apply_changes)
        button_layout.addWidget(self.apply_btn)

        scroll_layout.addLayout(button_layout)
        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

    def load_strategy_data(self):
        """加载策略数据"""
        if not self.strategy_data:
            return

        self.name_edit.setText(self.strategy_data.get('name', ''))
        self.description_edit.setPlainText(self.strategy_data.get('description', ''))
        self.strategy_type_combo.setCurrentText(self.strategy_data.get('strategy_type', 'technical'))
        self.tags_edit.setText(self.strategy_data.get('tags', ''))

        if 'parameters' in self.strategy_data:
            params = self.strategy_data['parameters']
            if isinstance(params, dict):
                self.params_edit.setPlainText(json.dumps(params, indent=2, ensure_ascii=False))
            else:
                self.params_edit.setPlainText(str(params))

        if 'weight_config' in self.strategy_data:
            weight_config = self.strategy_data['weight_config']
            self.equal_weight_check.setChecked(weight_config.get('equal_weight', True))
            if 'custom_weights' in weight_config:
                self.weight_edit.setPlainText(json.dumps(weight_config['custom_weights'], indent=2, ensure_ascii=False))

        if 'risk_config' in self.strategy_data:
            risk_config = self.strategy_data['risk_config']
            self.max_position_spin.setValue(risk_config.get('max_position_size', 0.1))
            self.max_drawdown_spin.setValue(risk_config.get('max_drawdown', 0.15))
            self.volatility_spin.setValue(risk_config.get('volatility_limit', 0.2))

    def on_strategy_type_changed(self, strategy_type: str):
        """策略类型改变"""
        pass

    def on_equal_weight_toggled(self, checked: bool):
        """等权重切换"""
        self.weight_edit.setEnabled(not checked)

    def validate_config(self):
        """验证配置"""
        try:
            strategy_type = self.strategy_type_combo.currentText()
            parameters = json.loads(self.params_edit.toPlainText())
            weight_config = json.loads(self.weight_edit.toPlainText())
            risk_config = {
                "max_position_size": self.max_position_spin.value(),
                "max_drawdown": self.max_drawdown_spin.value(),
                "volatility_limit": self.volatility_spin.value()
            }

            errors = []

            valid, param_errors = StrategyConfigValidator.validate_parameters(strategy_type, parameters)
            if not valid:
                errors.extend(param_errors)

            valid, weight_errors = StrategyConfigValidator.validate_weight_config(weight_config)
            if not valid:
                errors.extend(weight_errors)

            valid, risk_errors = StrategyConfigValidator.validate_risk_config(risk_config)
            if not valid:
                errors.extend(risk_errors)

            if errors:
                QMessageBox.warning(self, "配置验证失败", "\n".join(errors))
            else:
                QMessageBox.information(self, "配置验证成功", "策略配置验证通过！")

        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON解析错误", f"JSON格式错误: {e}")

    def apply_changes(self):
        """应用更改"""
        try:
            strategy_data = {
                'name': self.name_edit.text(),
                'description': self.description_edit.toPlainText(),
                'strategy_type': self.strategy_type_combo.currentText(),
                'tags': self.tags_edit.text(),
                'parameters': json.loads(self.params_edit.toPlainText()),
                'weight_config': {
                    'equal_weight': self.equal_weight_check.isChecked(),
                    'custom_weights': json.loads(self.weight_edit.toPlainText()) if not self.equal_weight_check.isChecked() else {}
                },
                'risk_config': {
                    'max_position_size': self.max_position_spin.value(),
                    'max_drawdown': self.max_drawdown_spin.value(),
                    'volatility_limit': self.volatility_spin.value()
                }
            }

            self.strategy_data = strategy_data
            self.strategy_changed.emit(strategy_data)

        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON解析错误", f"JSON格式错误: {e}")


class AIStrategyManagementDialog(QDialog):
    """AI选股策略管理对话框"""

    strategy_selected = pyqtSignal(str)  # 策略ID
    strategy_updated = pyqtSignal(str)    # 策略ID

    def __init__(self, parent=None, database_service=None):
        super().__init__(parent)

        if CORE_AVAILABLE and database_service is None:
            try:
                container = get_service_container()
                self.database_service = container.resolve(DatabaseService)
            except Exception as e:
                if logger:
                    logger.warning(f"无法从服务容器获取DatabaseService: {e}")
                self.database_service = None
        else:
            self.database_service = database_service

        self.current_strategy_id = None
        self.setup_ui()
        self.load_strategies()

    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("AI选股策略管理")
        self.resize(1400, 900)

        layout = QVBoxLayout(self)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        create_btn = QPushButton("创建策略")
        create_btn.clicked.connect(self.create_strategy)
        toolbar_layout.addWidget(create_btn)

        edit_btn = QPushButton("编辑策略")
        edit_btn.clicked.connect(self.edit_strategy)
        toolbar_layout.addWidget(edit_btn)

        duplicate_btn = QPushButton("复制策略")
        duplicate_btn.clicked.connect(self.duplicate_strategy)
        toolbar_layout.addWidget(duplicate_btn)

        delete_btn = QPushButton("删除策略")
        delete_btn.clicked.connect(self.delete_strategy)
        toolbar_layout.addWidget(delete_btn)

        toolbar_layout.addStretch()

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.load_strategies)
        toolbar_layout.addWidget(refresh_btn)

        layout.addLayout(toolbar_layout)

        # 主内容区域
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：策略列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        list_group = QGroupBox("策略列表")
        list_layout = QVBoxLayout(list_group)

        self.strategy_table = QTableWidget()
        self.strategy_table.setAlternatingRowColors(True)
        self.strategy_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.strategy_table.setSelectionMode(QTableWidget.SingleSelection)
        self.strategy_table.itemSelectionChanged.connect(self.on_strategy_selection_changed)

        columns = ["策略ID", "策略名称", "策略类型", "状态", "创建时间", "版本"]
        self.strategy_table.setColumnCount(len(columns))
        self.strategy_table.setHorizontalHeaderLabels(columns)

        header = self.strategy_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        list_layout.addWidget(self.strategy_table)
        left_layout.addWidget(list_group)

        splitter.addWidget(left_widget)

        # 右侧：策略详情
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        detail_group = QGroupBox("策略详情")
        detail_layout = QVBoxLayout(detail_group)

        self.strategy_editor = StrategyEditorWidget()
        self.strategy_editor.strategy_changed.connect(self.on_strategy_data_changed)
        detail_layout.addWidget(self.strategy_editor)

        right_layout.addWidget(detail_group)

        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

        # 状态栏
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)

    def load_strategies(self):
        """加载所有策略"""
        if not self.database_service:
            QMessageBox.warning(self, "警告", "数据库服务不可用")
            return

        try:
            strategies = self.database_service.get_all_ai_strategies()
            self.populate_strategy_table(strategies)
            self.status_label.setText(f"已加载 {len(strategies)} 个策略")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载策略失败: {e}")
            if logger:
                logger.error(f"加载策略失败: {e}")

    def populate_strategy_table(self, strategies: List[Dict]):
        """填充策略表格"""
        self.strategy_table.setRowCount(0)

        for strategy in strategies:
            row = self.strategy_table.rowCount()
            self.strategy_table.insertRow(row)

            self.strategy_table.setItem(row, 0, QTableWidgetItem(strategy.get('id', '')))
            self.strategy_table.setItem(row, 1, QTableWidgetItem(strategy.get('name', '')))
            self.strategy_table.setItem(row, 2, QTableWidgetItem(strategy.get('strategy_type', '')))
            self.strategy_table.setItem(row, 3, QTableWidgetItem(strategy.get('status', '')))
            self.strategy_table.setItem(row, 4, QTableWidgetItem(str(strategy.get('created_at', ''))))
            self.strategy_table.setItem(row, 5, QTableWidgetItem(str(strategy.get('version', 1))))

    def on_strategy_selection_changed(self):
        """策略选择改变"""
        selected_items = self.strategy_table.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        strategy_id = self.strategy_table.item(row, 0).text()
        self.current_strategy_id = strategy_id

        self.load_strategy_detail(strategy_id)

    def load_strategy_detail(self, strategy_id: str):
        """加载策略详情"""
        if not self.database_service:
            return

        try:
            strategy = self.database_service.get_ai_strategy(strategy_id)
            if strategy:
                self.strategy_editor.strategy_data = strategy
                self.strategy_editor.load_strategy_data()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载策略详情失败: {e}")
            if logger:
                logger.error(f"加载策略详情失败: {e}")

    def create_strategy(self):
        """创建策略"""
        dialog = QDialog(self)
        dialog.setWindowTitle("创建策略")
        dialog.resize(600, 400)

        layout = QVBoxLayout(dialog)

        template_group = QGroupBox("选择模板")
        template_layout = QFormLayout(template_group)

        template_combo = QComboBox()
        template_names = StrategyTemplateManager.get_template_names()
        display_names = StrategyTemplateManager.get_template_display_names()
        for name in template_names:
            template_combo.addItem(display_names.get(name, name), name)

        template_layout.addRow("策略模板:", template_combo)
        layout.addWidget(template_group)

        button_box = QHBoxLayout()
        create_btn = QPushButton("从模板创建")
        create_btn.clicked.connect(lambda: self.create_from_template(dialog, template_combo.currentData()))
        button_box.addWidget(create_btn)

        blank_btn = QPushButton("空白策略")
        blank_btn.clicked.connect(lambda: self.create_blank_strategy(dialog))
        button_box.addWidget(blank_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        button_box.addWidget(cancel_btn)

        layout.addLayout(button_box)

        dialog.exec_()

    def create_from_template(self, dialog: QDialog, template_name: str):
        """从模板创建策略"""
        if not self.database_service:
            QMessageBox.warning(self, "警告", "数据库服务不可用")
            return

        try:
            template = StrategyTemplateManager.get_template(template_name)
            if not template:
                QMessageBox.warning(self, "警告", "模板不存在")
                return

            strategy_id = self.database_service.create_ai_strategy(template)
            QMessageBox.information(self, "成功", f"策略已创建: {strategy_id}")
            dialog.accept()
            self.load_strategies()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建策略失败: {e}")
            if logger:
                logger.error(f"创建策略失败: {e}")

    def create_blank_strategy(self, dialog: QDialog):
        """创建空白策略"""
        if not self.database_service:
            QMessageBox.warning(self, "警告", "数据库服务不可用")
            return

        try:
            strategy_data = {
                'name': '新策略',
                'description': '请填写策略描述',
                'strategy_type': 'technical',
                'parameters': {},
                'weight_config': {'equal_weight': True},
                'risk_config': {
                    'max_position_size': 0.1,
                    'max_drawdown': 0.15,
                    'volatility_limit': 0.2
                }
            }

            strategy_id = self.database_service.create_ai_strategy(strategy_data)
            QMessageBox.information(self, "成功", f"策略已创建: {strategy_id}")
            dialog.accept()
            self.load_strategies()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建策略失败: {e}")
            if logger:
                logger.error(f"创建策略失败: {e}")

    def edit_strategy(self):
        """编辑策略"""
        if not self.current_strategy_id:
            QMessageBox.warning(self, "警告", "请先选择一个策略")
            return

        if not self.database_service:
            QMessageBox.warning(self, "警告", "数据库服务不可用")
            return

        try:
            strategy = self.database_service.get_ai_strategy(self.current_strategy_id)
            if not strategy:
                QMessageBox.warning(self, "警告", "策略不存在")
                return

            self.status_label.setText(f"正在编辑策略: {self.current_strategy_id}")
            
            strategy_editor = StrategyEditorWidget(strategy_data=strategy, parent=self)
            strategy_editor.strategy_changed.connect(self.on_strategy_data_changed)
            
            dialog = QDialog(self)
            dialog.setWindowTitle(f"编辑策略: {strategy.get('name', '')}")
            dialog.resize(800, 600)
            
            layout = QVBoxLayout(dialog)
            layout.addWidget(strategy_editor)
            
            button_box = QHBoxLayout()
            save_btn = QPushButton("保存")
            save_btn.clicked.connect(lambda: self.save_edited_strategy(dialog, strategy_editor))
            button_box.addWidget(save_btn)
            
            cancel_btn = QPushButton("取消")
            cancel_btn.clicked.connect(dialog.reject)
            button_box.addWidget(cancel_btn)
            
            layout.addLayout(button_box)
            
            dialog.exec_()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"编辑策略失败: {e}")
            if logger:
                logger.error(f"编辑策略失败: {e}")

    def save_edited_strategy(self, dialog: QDialog, editor: StrategyEditorWidget):
        """保存编辑的策略"""
        try:
            if not self.current_strategy_id:
                QMessageBox.warning(self, "警告", "策略ID不存在")
                return

            strategy_data = {
                'name': editor.name_edit.text(),
                'description': editor.description_edit.toPlainText(),
                'strategy_type': editor.strategy_type_combo.currentText(),
                'tags': editor.tags_edit.text(),
                'parameters': json.loads(editor.params_edit.toPlainText()),
                'weight_config': {
                    'equal_weight': editor.equal_weight_check.isChecked(),
                    'custom_weights': json.loads(editor.weight_edit.toPlainText()) if not editor.equal_weight_check.isChecked() else {}
                },
                'risk_config': {
                    'max_position_size': editor.max_position_spin.value(),
                    'max_drawdown': editor.max_drawdown_spin.value(),
                    'volatility_limit': editor.volatility_spin.value()
                }
            }

            self.database_service.update_ai_strategy(self.current_strategy_id, strategy_data)
            QMessageBox.information(self, "成功", "策略已更新")
            dialog.accept()
            self.load_strategies()

        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON解析错误", f"JSON格式错误: {e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存策略失败: {e}")
            if logger:
                logger.error(f"保存策略失败: {e}")

    def duplicate_strategy(self):
        """复制策略"""
        if not self.current_strategy_id:
            QMessageBox.warning(self, "警告", "请先选择一个策略")
            return

        if not self.database_service:
            QMessageBox.warning(self, "警告", "数据库服务不可用")
            return

        try:
            strategy = self.database_service.get_ai_strategy(self.current_strategy_id)
            if not strategy:
                QMessageBox.warning(self, "警告", "策略不存在")
                return

            new_strategy = strategy.copy()
            new_strategy['id'] = str(uuid.uuid4())
            new_strategy['name'] = f"{strategy['name']} (副本)"
            new_strategy['created_by'] = 'user'

            new_id = self.database_service.create_ai_strategy(new_strategy)
            QMessageBox.information(self, "成功", f"策略已复制: {new_id}")
            self.load_strategies()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"复制策略失败: {e}")
            if logger:
                logger.error(f"复制策略失败: {e}")

    def delete_strategy(self):
        """删除策略"""
        if not self.current_strategy_id:
            QMessageBox.warning(self, "警告", "请先选择一个策略")
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除策略 {self.current_strategy_id} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if not self.database_service:
                QMessageBox.warning(self, "警告", "数据库服务不可用")
                return

            try:
                self.database_service.delete_ai_strategy(self.current_strategy_id)
                QMessageBox.information(self, "成功", "策略已删除")
                self.current_strategy_id = None
                self.load_strategies()

            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除策略失败: {e}")
                if logger:
                    logger.error(f"删除策略失败: {e}")

    def on_strategy_data_changed(self, strategy_data: Dict):
        """策略数据改变"""
        if not self.current_strategy_id:
            return

        if not self.database_service:
            QMessageBox.warning(self, "警告", "数据库服务不可用")
            return

        try:
            self.database_service.update_ai_strategy(self.current_strategy_id, strategy_data)
            self.status_label.setText(f"策略已更新: {self.current_strategy_id}")
            self.strategy_updated.emit(self.current_strategy_id)
            self.load_strategies()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"更新策略失败: {e}")
            if logger:
                logger.error(f"更新策略失败: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = AIStrategyManagementDialog()
    dialog.show()
    sys.exit(app.exec_())
