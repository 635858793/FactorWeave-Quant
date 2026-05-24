"""
统一策略管理对话框

整合了以下三个对话框的功能：
1. enhanced_strategy_manager_dialog.py (V2) - 基础策略管理、回测、优化、性能分析
2. enhanced_strategy_manager_dialog_v3.py (V3) - 现代化UI组件、侧边栏导航、工作区管理
3. ai_strategy_management_dialog.py - AI策略模板管理、策略编辑器、配置验证

主要功能模块：
- 首页：统计卡片、性能趋势、策略排行榜、快捷操作
- 策略库：策略CRUD、导入导出、批量操作、搜索筛选
- 回测实验室：回测配置、运行回测、结果展示、图表分析
- 参数优化：优化算法、参数范围、优化曲线、最佳参数
- 性能分析：性能指标、策略对比、性能图表
- AI策略：AI策略模板、策略编辑器、配置验证
- 代码编辑器：策略代码编辑与执行
- 开发工作流：策略开发流程引导

作者: Hikyuu-UI Team
版本: 4.0
"""

import sys
import json
import uuid
import re
import time
import asyncio
from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import asdict
from enum import Enum

import pandas as pd
import numpy as np

from loguru import logger

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
    Qt, pyqtSignal, QThread, QTimer, QDateTime, QThreadPool,
    QRunnable, QMetaObject, Q_ARG, QSettings, QMimeData, QPropertyAnimation,
    QEasingCurve, QRect
)
from PyQt5.QtGui import (
    QFont, QPixmap, QIcon, QColor, QPalette, QPainter, QBrush, QDrag,
    QLinearGradient, QPen
)

from core.services.strategy_service import StrategyService, StrategyConfig, BacktestStatus, OptimizationStatus
from core.strategy_extensions import (
    StrategyContext, StandardMarketData, TimeFrame, AssetType,
    StrategyType, RiskLevel, ParameterDef, TradingPerformanceMetrics
)
from core.events.event_bus import get_event_bus
from core.events.types import ThemeChangedEvent
from core.events import (
    StrategyStartedEvent, StrategyStoppedEvent, StrategyErrorEvent,
    SignalGeneratedEvent, EventType, EventPriority, EventFilter
)

from gui.components.modern_ui_components import (
    ModernSidebarNavigation, EnhancedStatCard, CollapsiblePanel,
    QuickActionPanel, RealtimeIndicator, WorkspaceManager,
    FINANCIAL_COLORS, STATUS_COLORS
)
from .base_dialog import BaseDialog


try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    from utils.matplotlib_font_config import configure_matplotlib_chinese_font
    configure_matplotlib_chinese_font()
    MATPLOTLIB_AVAILABLE = True
except ImportError as e:
    MATPLOTLIB_AVAILABLE = False
    plt = None
    FigureCanvas = None
    Figure = None
    mdates = None
    logger.warning(f"matplotlib 不可用: {e}")


try:
    THEME_MANAGER_AVAILABLE = True
    from utils.theme import get_theme_manager, Theme
except ImportError as e:
    THEME_MANAGER_AVAILABLE = False
    get_theme_manager = None
    Theme = None
    logger.warning(f"主题管理器不可用: {e}")


try:
    from core.services.database_service import DatabaseService
    from core.containers.service_container import get_service_container
    CORE_AVAILABLE = True
except ImportError as e:
    CORE_AVAILABLE = False
    logger.warning(f"核心服务不可用: {e}")


class StrategyTemplateManager:
    """AI策略模板管理器"""

    TEMPLATES = {
        "aggressive_growth": {
            "name": "激进成长策略",
            "description": "追求高收益的成长策略，适合风险承受能力强的投资者",
            "strategy_type": "growth",
            "parameters": {"revenue_growth_threshold": 0.3, "earnings_growth_threshold": 0.25, "pe_ratio_max": 30},
            "weight_config": {"equal_weight": False, "custom_weights": {"revenue_growth": 0.4, "earnings_growth": 0.3, "pe_ratio": 0.2, "other": 0.1}},
            "risk_config": {"max_position_size": 0.15, "max_drawdown": 0.2, "volatility_limit": 0.3}
        },
        "conservative_value": {
            "name": "稳健价值策略",
            "description": "注重安全的价值策略，适合稳健型投资者",
            "strategy_type": "value",
            "parameters": {"pe_threshold": 15, "pb_threshold": 2.0, "dividend_yield_threshold": 0.03},
            "weight_config": {"equal_weight": True},
            "risk_config": {"max_position_size": 0.08, "max_drawdown": 0.1, "volatility_limit": 0.15}
        },
        "technical_momentum": {
            "name": "技术动量策略",
            "description": "基于技术指标和价格动量的选股策略",
            "strategy_type": "technical",
            "parameters": {"indicators": ["MA", "MACD", "RSI", "KDJ"], "lookback_period": 20, "momentum_threshold": 0.05},
            "weight_config": {"equal_weight": True},
            "risk_config": {"max_position_size": 0.1, "max_drawdown": 0.15, "volatility_limit": 0.2}
        },
        "quality_focus": {
            "name": "质量优选策略",
            "description": "基于财务质量指标的选股策略",
            "strategy_type": "quality",
            "parameters": {"roe_threshold": 0.15, "debt_to_equity_threshold": 0.5, "current_ratio_threshold": 1.5},
            "weight_config": {"equal_weight": False, "custom_weights": {"roe": 0.4, "debt_ratio": 0.3, "current_ratio": 0.2, "other": 0.1}},
            "risk_config": {"max_position_size": 0.1, "max_drawdown": 0.12, "volatility_limit": 0.18}
        },
        "dividend_income": {
            "name": "股息收益策略",
            "description": "基于股息收益的选股策略，适合追求稳定收益的投资者",
            "strategy_type": "dividend",
            "parameters": {"dividend_yield_threshold": 0.04, "payout_ratio_threshold": 0.6, "dividend_growth_threshold": 0.05},
            "weight_config": {"equal_weight": True},
            "risk_config": {"max_position_size": 0.08, "max_drawdown": 0.1, "volatility_limit": 0.12}
        }
    }

    @classmethod
    def get_template_names(cls) -> List[str]:
        return list(cls.TEMPLATES.keys())

    @classmethod
    def get_template(cls, template_name: str) -> Optional[Dict[str, Any]]:
        return cls.TEMPLATES.get(template_name)

    @classmethod
    def get_template_display_names(cls) -> Dict[str, str]:
        return {"aggressive_growth": "激进成长策略", "conservative_value": "稳健价值策略",
                "technical_momentum": "技术动量策略", "quality_focus": "质量优选策略", "dividend_income": "股息收益策略"}


class StrategyConfigValidator:
    """策略配置验证器"""

    @staticmethod
    def validate_parameters(strategy_type: str, parameters: Dict) -> Tuple[bool, List[str]]:
        errors = []
        if strategy_type == "technical":
            if "indicators" not in parameters:
                errors.append("技术分析策略必须包含indicators参数")
            elif not isinstance(parameters["indicators"], list):
                errors.append("indicators参数必须是列表")
            elif len(parameters["indicators"]) == 0:
                errors.append("indicators参数不能为空")
        elif strategy_type == "value":
            if "pe_threshold" in parameters and parameters["pe_threshold"] <= 0:
                errors.append("pe_threshold必须大于0")
            if "pb_threshold" in parameters and parameters["pb_threshold"] <= 0:
                errors.append("pb_threshold必须大于0")
        elif strategy_type == "growth":
            if "revenue_growth_threshold" in parameters and not (0 <= parameters["revenue_growth_threshold"] <= 1):
                errors.append("revenue_growth_threshold必须在0和1之间")
            if "earnings_growth_threshold" in parameters and not (0 <= parameters["earnings_growth_threshold"] <= 1):
                errors.append("earnings_growth_threshold必须在0和1之间")
        elif strategy_type == "quality":
            if "roe_threshold" in parameters and not (0 <= parameters["roe_threshold"] <= 1):
                errors.append("roe_threshold必须在0和1之间")
            if "debt_to_equity_threshold" in parameters and not (0 <= parameters["debt_to_equity_threshold"] <= 1):
                errors.append("debt_to_equity_threshold必须在0和1之间")
        elif strategy_type == "dividend":
            if "dividend_yield_threshold" in parameters and not (0 <= parameters["dividend_yield_threshold"] <= 1):
                errors.append("dividend_yield_threshold必须在0和1之间")
            if "payout_ratio_threshold" in parameters and not (0 <= parameters["payout_ratio_threshold"] <= 1):
                errors.append("payout_ratio_threshold必须在0和1之间")
        return len(errors) == 0, errors

    @staticmethod
    def validate_weight_config(weight_config: Dict) -> Tuple[bool, List[str]]:
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
        errors = []
        for key in ["max_position_size", "max_drawdown", "volatility_limit"]:
            if key in risk_config and not (0 < risk_config[key] <= 1):
                errors.append(f"{key}必须在0和1之间")
        return len(errors) == 0, errors


class StrategyEditorWidget(QWidget):
    """策略编辑组件"""

    strategy_changed = pyqtSignal(dict)

    def __init__(self, strategy_data: Optional[Dict] = None, parent=None):
        super().__init__(parent)
        self.strategy_data = strategy_data or {}
        self._setup_ui()
        self._load_strategy_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

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
        self.strategy_type_combo.addItems(["technical", "momentum", "value", "growth", "quality", "dividend", "quantitative", "hybrid"])
        basic_layout.addRow("策略类型:", self.strategy_type_combo)
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("标签（逗号分隔）")
        basic_layout.addRow("标签:", self.tags_edit)
        scroll_layout.addWidget(basic_group)

        params_group = QGroupBox("参数配置")
        params_layout = QVBoxLayout(params_group)
        self.params_edit = QTextEdit()
        self.params_edit.setPlaceholderText('{"indicators": ["MA", "MACD"], "lookback_period": 20}')
        self.params_edit.setMaximumHeight(150)
        params_layout.addWidget(self.params_edit)
        scroll_layout.addWidget(params_group)

        weight_group = QGroupBox("权重配置")
        weight_layout = QVBoxLayout(weight_group)
        self.equal_weight_check = QCheckBox("等权重分配")
        self.equal_weight_check.setChecked(True)
        self.equal_weight_check.toggled.connect(self._on_equal_weight_toggled)
        weight_layout.addWidget(self.equal_weight_check)
        self.weight_edit = QTextEdit()
        self.weight_edit.setPlaceholderText('{"MA": 0.3, "MACD": 0.3, "RSI": 0.2, "KDJ": 0.2}')
        self.weight_edit.setMaximumHeight(100)
        self.weight_edit.setEnabled(False)
        weight_layout.addWidget(self.weight_edit)
        scroll_layout.addWidget(weight_group)

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

        button_layout = QHBoxLayout()
        self.validate_btn = QPushButton("验证配置")
        self.validate_btn.clicked.connect(self._validate_config)
        button_layout.addWidget(self.validate_btn)
        self.apply_btn = QPushButton("应用更改")
        self.apply_btn.clicked.connect(self._apply_changes)
        button_layout.addWidget(self.apply_btn)
        scroll_layout.addLayout(button_layout)
        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

    def _load_strategy_data(self):
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

    def _on_equal_weight_toggled(self, checked: bool):
        self.weight_edit.setEnabled(not checked)

    def _validate_config(self):
        try:
            strategy_type = self.strategy_type_combo.currentText()
            parameters = json.loads(self.params_edit.toPlainText())
            weight_config = json.loads(self.weight_edit.toPlainText()) if not self.equal_weight_check.isChecked() else {'equal_weight': True}
            risk_config = {"max_position_size": self.max_position_spin.value(), "max_drawdown": self.max_drawdown_spin.value(), "volatility_limit": self.volatility_spin.value()}
            errors = []
            valid, param_errors = StrategyConfigValidator.validate_parameters(strategy_type, parameters)
            if not valid: errors.extend(param_errors)
            valid, weight_errors = StrategyConfigValidator.validate_weight_config(weight_config)
            if not valid: errors.extend(weight_errors)
            valid, risk_errors = StrategyConfigValidator.validate_risk_config(risk_config)
            if not valid: errors.extend(risk_errors)
            if errors:
                QMessageBox.warning(self, "配置验证失败", "\n".join(errors))
            else:
                QMessageBox.information(self, "配置验证成功", "策略配置验证通过！")
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON解析错误", f"JSON格式错误: {e}")

    def _apply_changes(self):
        try:
            strategy_data = {
                'name': self.name_edit.text(), 'description': self.description_edit.toPlainText(),
                'strategy_type': self.strategy_type_combo.currentText(), 'tags': self.tags_edit.text(),
                'parameters': json.loads(self.params_edit.toPlainText()),
                'weight_config': {'equal_weight': self.equal_weight_check.isChecked(),
                                  'custom_weights': json.loads(self.weight_edit.toPlainText()) if not self.equal_weight_check.isChecked() else {}},
                'risk_config': {'max_position_size': self.max_position_spin.value(),
                                'max_drawdown': self.max_drawdown_spin.value(),
                                'volatility_limit': self.volatility_spin.value()}
            }
            self.strategy_data = strategy_data
            self.strategy_changed.emit(strategy_data)
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON解析错误", f"JSON格式错误: {e}")


class _StrategyConfigDialog(QDialog):
    """策略配置对话框"""

    def __init__(self, parent=None, strategy_config=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.strategy_config = strategy_config
        self.setWindowTitle("策略配置" if not strategy_config else "编辑策略配置")
        self.resize(700, 800)
        self._setup_ui()
        if self.strategy_config:
            self._load_strategy_config()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        basic_group = QGroupBox("基本信息")
        basic_layout = QFormLayout(basic_group)
        self.strategy_id_edit = QLineEdit()
        self.strategy_id_edit.setPlaceholderText("策略唯一标识符")
        self.strategy_name_edit = QLineEdit()
        self.strategy_name_edit.setPlaceholderText("策略显示名称")
        self.plugin_type_combo = QComboBox()
        self.plugin_type_combo.addItems(["momentum", "mean_reversion", "trend_following", "arbitrage", "statistical", "custom"])
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        basic_layout.addRow("策略ID:", self.strategy_id_edit)
        basic_layout.addRow("策略名称:", self.strategy_name_edit)
        basic_layout.addRow("插件类型:", self.plugin_type_combo)
        basic_layout.addRow("描述:", self.description_edit)
        scroll_layout.addWidget(basic_group)

        param_group = QGroupBox("策略参数")
        param_layout = QVBoxLayout(param_group)
        self.param_table = QTableWidget()
        self.param_table.setColumnCount(3)
        self.param_table.setHorizontalHeaderLabels(["参数名", "参数值", "类型"])
        self.param_table.horizontalHeader().setStretchLastSection(True)
        param_layout.addWidget(self.param_table)
        add_btn = QPushButton("添加参数")
        add_btn.clicked.connect(self._add_parameter)
        param_layout.addWidget(add_btn)
        scroll_layout.addWidget(param_group)

        metadata_group = QGroupBox("元数据")
        metadata_layout = QFormLayout(metadata_group)
        self.default_account_edit = QLineEdit()
        self.default_account_edit.setPlaceholderText("默认账号ID（可选）")
        metadata_layout.addRow("默认账号:", self.default_account_edit)
        scroll_layout.addWidget(metadata_group)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        button_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def _add_parameter(self):
        row = self.param_table.rowCount()
        self.param_table.insertRow(row)
        self.param_table.setItem(row, 0, QTableWidgetItem(""))
        self.param_table.setItem(row, 1, QTableWidgetItem(""))
        self.param_table.setItem(row, 2, QTableWidgetItem("float"))

    def _load_strategy_config(self):
        self.strategy_id_edit.setText(self.strategy_config.strategy_id)
        self.strategy_id_edit.setEnabled(False)
        self.strategy_name_edit.setText(self.strategy_config.metadata.get('name', ''))
        self.plugin_type_combo.setCurrentText(self.strategy_config.plugin_type)
        self.description_edit.setPlainText(self.strategy_config.metadata.get('description', ''))
        self.default_account_edit.setText(self.strategy_config.metadata.get('default_account_id', ''))
        self.param_table.setRowCount(0)
        for name, value in self.strategy_config.parameters.items():
            row = self.param_table.rowCount()
            self.param_table.insertRow(row)
            self.param_table.setItem(row, 0, QTableWidgetItem(name))
            self.param_table.setItem(row, 1, QTableWidgetItem(str(value)))
            self.param_table.setItem(row, 2, QTableWidgetItem(type(value).__name__))

    def get_config_data(self):
        parameters = {}
        for row in range(self.param_table.rowCount()):
            name = self.param_table.item(row, 0).text().strip() if self.param_table.item(row, 0) else ""
            value = self.param_table.item(row, 1).text().strip() if self.param_table.item(row, 1) else ""
            ptype = self.param_table.item(row, 2).text().strip() if self.param_table.item(row, 2) else "float"
            if name:
                try:
                    if ptype == "int":
                        parameters[name] = int(value)
                    elif ptype == "float":
                        parameters[name] = float(value)
                    elif ptype == "bool":
                        parameters[name] = value.lower() in ("true", "1", "yes")
                    else:
                        parameters[name] = value
                except ValueError:
                    parameters[name] = value
        metadata = {'name': self.strategy_name_edit.text(), 'description': self.description_edit.toPlainText()}
        if self.default_account_edit.text():
            metadata['default_account_id'] = self.default_account_edit.text()
        return {'strategy_id': self.strategy_id_edit.text(), 'plugin_type': self.plugin_type_combo.currentText(),
                'parameters': parameters, 'metadata': metadata}


class _BatchUpdateDefaultAccountDialog(QDialog):
    """批量修改默认账号对话框"""

    def __init__(self, parent=None, strategy_ids=None, strategy_service=None, account_manager=None):
        super().__init__(parent)
        self.strategy_ids = strategy_ids or []
        self.strategy_service = strategy_service
        self.account_manager = account_manager
        self.setWindowTitle("批量修改默认账号")
        self.resize(500, 350)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"已选择 {len(self.strategy_ids)} 个策略"))
        account_group = QGroupBox("选择目标账号")
        account_layout = QVBoxLayout(account_group)
        self.account_combo = QComboBox()
        self.account_combo.addItem("系统默认", "default")
        if self.account_manager:
            try:
                accounts = self.account_manager.get_all_accounts()
                for acc in accounts:
                    self.account_combo.addItem(acc.account_id, acc.account_id)
            except Exception as e:
                logger.error(f"加载账号列表失败: {e}")
        account_layout.addWidget(self.account_combo)
        layout.addWidget(account_group)
        strategy_list = QListWidget()
        strategy_list.addItems(self.strategy_ids)
        layout.addWidget(QLabel("策略列表:"))
        layout.addWidget(strategy_list)
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("确认修改")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def get_selected_account(self):
        return self.account_combo.currentData()


class _OptimizationParamDialog(QDialog):
    """优化参数配置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加优化参数")
        self.resize(400, 250)
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)
        self.name_edit = QLineEdit()
        self.min_edit = QLineEdit()
        self.max_edit = QLineEdit()
        self.step_edit = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["int", "float"])
        layout.addRow("参数名:", self.name_edit)
        layout.addRow("最小值:", self.min_edit)
        layout.addRow("最大值:", self.max_edit)
        layout.addRow("步长:", self.step_edit)
        layout.addRow("类型:", self.type_combo)
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addRow(button_layout)

    def get_param_config(self):
        return {'name': self.name_edit.text(), 'min': self.min_edit.text(),
                'max': self.max_edit.text(), 'step': self.step_edit.text(), 'type': self.type_combo.currentText()}


class _StrategyCompareDialog(QDialog):
    """策略对比对话框"""

    def __init__(self, parent=None, strategy_service=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.strategy_service = strategy_service
        self.setWindowTitle("策略对比")
        self.resize(800, 600)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("策略1:"))
        self.strategy1_combo = QComboBox()
        toolbar.addWidget(self.strategy1_combo)
        toolbar.addWidget(QLabel("策略2:"))
        self.strategy2_combo = QComboBox()
        toolbar.addWidget(self.strategy2_combo)
        compare_btn = QPushButton("对比")
        compare_btn.clicked.connect(self._compare)
        toolbar.addWidget(compare_btn)
        layout.addLayout(toolbar)
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(3)
        self.result_table.setHorizontalHeaderLabels(["指标", "策略1", "策略2"])
        self.result_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.result_table)
        self._load_strategies()

    def _load_strategies(self):
        if self.strategy_service:
            strategies = self.strategy_service.get_all_strategy_configs()
            for s in strategies:
                self.strategy1_combo.addItem(s.strategy_id, s.strategy_id)
                self.strategy2_combo.addItem(s.strategy_id, s.strategy_id)

    def _compare(self):
        QMessageBox.information(self, "提示", "策略对比功能需要回测结果数据支持")


class StrategyManagerDialog(BaseDialog):
    """
    统一策略管理对话框 V4

    整合了V2基础策略管理、V3现代化UI组件和AI策略管理功能。

    功能模块：
    - 首页：统计卡片、性能趋势、策略排行榜、快捷操作
    - 策略库：策略CRUD、导入导出、批量操作、搜索筛选
    - 回测实验室：回测配置、运行回测、结果展示、图表分析
    - 参数优化：优化算法、参数范围、优化曲线、最佳参数
    - 性能分析：性能指标、策略对比、性能图表
    - AI策略：AI策略模板、策略编辑器、配置验证
    - 代码编辑器：策略代码编辑与执行
    - 开发工作流：策略开发流程引导
    """

    strategy_selected = pyqtSignal(str)
    strategy_started = pyqtSignal(str)
    strategy_stopped = pyqtSignal(str)
    strategy_updated = pyqtSignal(str)

    def __init__(self, parent=None, strategy_service=None, database_service=None):
        super().__init__(
            parent,
            title="策略管理器 - 专业版",
            size=(1600, 1000),
            settings_key="StrategyManagerDialog",
            modal=False
        )

        self.theme_manager = self._init_theme_manager()
        self._setup_services(strategy_service, database_service)

        self.current_strategy_id = None
        self.current_view = 'home'
        self._cached_charts = []
        self._async_tasks = set()
        self.current_backtest_id = None
        self.current_batch_backtest_ids = []
        self.current_optimization_id = None
        self.backtest_start_time = None
        self.backtest_timeout = 600
        self.optimization_start_time = None
        self.optimization_timeout = 1800

        if self.theme_manager:
            self.theme_manager.theme_changed.connect(self._on_theme_changed)

        self._setup_ui()
        self._apply_theme()
        self._subscribe_strategy_events()
        self._load_data()

    def _init_theme_manager(self):
        if THEME_MANAGER_AVAILABLE:
            try:
                return get_theme_manager()
            except Exception as e:
                logger.warning(f"获取主题管理器失败: {e}")
        return None

    def _setup_services(self, strategy_service, database_service):
        try:
            if CORE_AVAILABLE:
                self.service_container = get_service_container()
            else:
                self.service_container = None
        except Exception as e:
            logger.warning(f"无法获取服务容器: {e}")
            self.service_container = None

        self.strategy_service = strategy_service if strategy_service else (self.service_container.resolve(StrategyService) if self.service_container else None)
        self.database_service = database_service if database_service else (self.service_container.resolve(DatabaseService) if CORE_AVAILABLE and self.service_container else None)
        self.workspace_manager = WorkspaceManager()
        self._strategy_event_handler = None
        logger.info(f"服务初始化完成: strategy_service={self.strategy_service is not None}, database_service={self.database_service is not None}")

    def _subscribe_strategy_events(self):
        try:
            event_bus = get_event_bus()
            def handler(event):
                try: self._on_strategy_event(event)
                except Exception as e: logger.error(f"策略事件处理器执行失败: {e}")
            self._strategy_event_handler = handler
            event_bus.subscribe(StrategyStartedEvent, handler, priority=0)
            event_bus.subscribe(StrategyStoppedEvent, handler, priority=0)
            event_bus.subscribe(SignalGeneratedEvent, handler, priority=0)
            event_bus.subscribe(StrategyErrorEvent, handler, priority=0)
            logger.info("策略事件订阅已注册")
        except Exception as e:
            logger.warning(f"注册策略事件订阅失败: {e}")

    def _on_strategy_event(self, event):
        if isinstance(event, StrategyStartedEvent):
            self._update_strategy_status(event.strategy_id, "running")
        elif isinstance(event, StrategyStoppedEvent):
            self._update_strategy_status(event.strategy_id, "stopped")
            if hasattr(event, 'performance') and event.performance:
                self._show_performance_notification(event.performance)
        elif isinstance(event, SignalGeneratedEvent):
            if hasattr(event, 'signals') and event.signals:
                self._update_signal_counter(len(event.signals))
        elif isinstance(event, StrategyErrorEvent):
            self._show_error_notification(event.strategy_id, event.error_message)

    def _update_strategy_status(self, strategy_id: str, status: str):
        if status == "running":
            if hasattr(self, 'backtest_status_label'): self.backtest_status_label.setText(f"回测运行中: {strategy_id}")
            if hasattr(self, 'backtest_progress_bar'): self.backtest_progress_bar.setRange(0, 0)
        elif status == "stopped":
            if hasattr(self, 'backtest_status_label'): self.backtest_status_label.setText(f"回测完成: {strategy_id}")
            if hasattr(self, 'backtest_progress_bar'): self.backtest_progress_bar.setRange(0, 100); self.backtest_progress_bar.setValue(100)

    def _show_performance_notification(self, performance):
        try:
            if hasattr(self, 'total_return_card') and performance:
                value_label = getattr(self.total_return_card, 'value_label', None)
                if value_label:
                    total_return = performance.total_return
                    if hasattr(total_return, 'iloc'): total_return = float(total_return.iloc[0]) if len(total_return) > 0 else 0.0
                    elif total_return is not None: total_return = float(total_return)
                    else: total_return = 0.0
                    value_label.setText(f"{total_return*100:.2f}%")
        except Exception as e:
            logger.warning(f"更新性能指标失败: {e}")

    def _update_signal_counter(self, count: int):
        if hasattr(self, 'backtest_status_label'): self.backtest_status_label.setText(f"已生成 {count} 个交易信号")

    def _show_error_notification(self, strategy_id: str, error: str):
        if hasattr(self, 'backtest_status_label'): self.backtest_status_label.setText(f"错误: {error}")
        if hasattr(self, 'backtest_progress_bar'): self.backtest_progress_bar.setRange(0, 100)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        header = self._create_header()
        main_layout.addWidget(header)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)
        self.sidebar = self._create_sidebar()
        splitter.addWidget(self.sidebar)
        content_widget = self._create_content_area()
        splitter.addWidget(content_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

    def _create_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(40)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        title = QLabel("策略管理器")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        layout.addStretch()
        self.realtime_indicator = RealtimeIndicator(theme_manager=self.theme_manager)
        layout.addWidget(self.realtime_indicator)
        return header

    def _create_sidebar(self) -> ModernSidebarNavigation:
        sidebar = ModernSidebarNavigation(theme_manager=self.theme_manager)
        nav_items = [('home', '首页', '🏠', 'Ctrl+H'), ('library', '策略库', '📚', 'Ctrl+L'),
                     ('backtest', '回测实验室', '📊', 'Ctrl+B'), ('optimization', '参数优化', '⚙️', 'Ctrl+O'),
                     ('performance', '性能分析', '📈', 'Ctrl+P'), ('ai_strategy', 'AI策略', '🤖', 'Ctrl+A'),
                     ('editor', '代码编辑器', '💻', 'Ctrl+E'), ('workflow', '开发工作流', '🔄', 'Ctrl+W')]
        for name, label, icon, shortcut in nav_items:
            sidebar.add_nav_item(name, label, icon, shortcut)
        sidebar.add_quick_action("新建策略", "➕", self._create_strategy)
        sidebar.add_quick_action("快速回测", "🚀", self._quick_backtest)
        sidebar.nav_changed.connect(self._on_nav_changed)
        sidebar.set_current_nav('home')
        return sidebar

    def _create_content_area(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        self.content_stack = QStackedWidget()
        self.home_view = self._create_home_view()
        self.content_stack.addWidget(self.home_view)
        self.library_view = self._create_library_view()
        self.content_stack.addWidget(self.library_view)
        self.backtest_view = self._create_backtest_view()
        self.content_stack.addWidget(self.backtest_view)
        self.optimization_view = self._create_optimization_view()
        self.content_stack.addWidget(self.optimization_view)
        self.performance_view = self._create_performance_view()
        self.content_stack.addWidget(self.performance_view)
        self.ai_strategy_view = self._create_ai_strategy_view()
        self.content_stack.addWidget(self.ai_strategy_view)
        self.editor_view = self._create_editor_view()
        self.content_stack.addWidget(self.editor_view)
        self.workflow_view = self._create_workflow_view()
        self.content_stack.addWidget(self.workflow_view)
        layout.addWidget(self.content_stack)
        return content

    def _on_nav_changed(self, nav_name: str):
        self._switch_view(nav_name)

    def _switch_view(self, view_name: str):
        self.current_view = view_name
        view_map = {'home': self.home_view, 'library': self.library_view, 'backtest': self.backtest_view,
                    'optimization': self.optimization_view, 'performance': self.performance_view,
                    'ai_strategy': self.ai_strategy_view, 'editor': self.editor_view, 'workflow': self.workflow_view}
        if view_name in view_map:
            self.content_stack.setCurrentWidget(view_map[view_name])
            self.sidebar.set_current_nav(view_name)

    def _on_quick_action(self, action_id: str):
        action_map = {'create': self._create_strategy, 'backtest': self._quick_backtest,
                      'optimize': lambda: self._switch_view('optimization'), 'import': self._import_strategy}
        if action_id in action_map: action_map[action_id]()

    # ===================== Home View =====================

    def _create_home_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        self.total_strategy_card = EnhancedStatCard(title="策略总数", value="0", color=FINANCIAL_COLORS['primary'], theme_manager=self.theme_manager)
        self.total_strategy_card.clicked.connect(lambda: self._switch_view('library'))
        stats_layout.addWidget(self.total_strategy_card)
        self.running_strategy_card = EnhancedStatCard(title="运行中", value="0", color=STATUS_COLORS['running'], theme_manager=self.theme_manager)
        stats_layout.addWidget(self.running_strategy_card)
        self.configured_strategy_card = EnhancedStatCard(title="已配置", value="0", color=STATUS_COLORS['configured'], theme_manager=self.theme_manager)
        stats_layout.addWidget(self.configured_strategy_card)
        self.error_strategy_card = EnhancedStatCard(title="错误", value="0", color=STATUS_COLORS['error'], theme_manager=self.theme_manager)
        stats_layout.addWidget(self.error_strategy_card)
        layout.addLayout(stats_layout)
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._create_home_left_panel())
        splitter.addWidget(self._create_home_right_panel())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        return view

    def _create_home_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        trend_panel = CollapsiblePanel("性能趋势（最近30天）", theme_manager=self.theme_manager)
        trend_panel.set_content(self._create_trend_chart())
        layout.addWidget(trend_panel)
        ranking_panel = CollapsiblePanel("策略性能排行榜", theme_manager=self.theme_manager)
        ranking_panel.set_content(self._create_ranking_table())
        layout.addWidget(ranking_panel)
        return panel

    def _create_home_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        quick_action_panel = QuickActionPanel(theme_manager=self.theme_manager)
        quick_action_panel.action_triggered.connect(self._on_quick_action)
        layout.addWidget(quick_action_panel)
        layout.addStretch()
        return panel

    def _create_trend_chart(self) -> QWidget:
        widget = QWidget()
        widget.setMinimumHeight(300)
        layout = QVBoxLayout(widget)
        if MATPLOTLIB_AVAILABLE:
            canvas = FigureCanvas(Figure(figsize=(10, 4)))
            self._cached_charts.append(canvas)
            if self.theme_manager: self.theme_manager.apply_chart_theme(canvas.figure)
            ax = canvas.figure.add_subplot(111)
            ax.set_title("性能趋势（最近30天）", fontsize=12, fontweight='bold')
            ax.set_xlabel("日期", fontsize=10)
            ax.set_ylabel("收益率 (%)", fontsize=10)
            ax.grid(True, alpha=0.3)
            ax.text(0.5, 0.5, '暂无数据', transform=ax.transAxes, ha='center', va='center', fontsize=12, alpha=0.5)
            canvas.draw()
            layout.addWidget(canvas)
        else:
            label = QLabel("图表功能需要安装 matplotlib 库")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #6B7280; font-size: 14px;")
            layout.addWidget(label)
        return widget

    def _create_ranking_table(self) -> QWidget:
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["排名", "策略名称", "收益率", "夏普比率", "操作"])
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setRowCount(1)
        table.setItem(0, 0, QTableWidgetItem("-"))
        table.setItem(0, 1, QTableWidgetItem("暂无数据"))
        table.setItem(0, 2, QTableWidgetItem("-"))
        table.setItem(0, 3, QTableWidgetItem("-"))
        btn = QPushButton("查看")
        btn.setEnabled(False)
        table.setCellWidget(0, 4, btn)
        return table

    # ===================== Library View =====================

    def _create_library_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(self._create_library_toolbar())
        self.strategy_table = self._create_strategy_table()
        self.strategy_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.strategy_table)
        return widget

    def _create_library_toolbar(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        create_btn = QPushButton("新建策略"); create_btn.clicked.connect(self._create_strategy)
        import_btn = QPushButton("导入"); import_btn.clicked.connect(self._import_strategy)
        export_btn = QPushButton("导出"); export_btn.clicked.connect(self._export_strategy)
        batch_update_btn = QPushButton("批量修改默认账号"); batch_update_btn.clicked.connect(self._batch_update_default_account)
        refresh_btn = QPushButton("刷新"); refresh_btn.clicked.connect(self._load_strategies)
        self.search_edit = QLineEdit(); self.search_edit.setPlaceholderText("搜索策略..."); self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.status_filter = QComboBox(); self.status_filter.addItems(["全部状态", "已配置", "运行中", "错误"]); self.status_filter.currentTextChanged.connect(self._on_status_filter_changed)
        self.account_filter = QComboBox(); self.account_filter.addItem("全部账号", "all"); self.account_filter.addItem("系统默认", "default"); self.account_filter.currentTextChanged.connect(self._on_account_filter_changed)
        layout.addWidget(create_btn); layout.addWidget(import_btn); layout.addWidget(export_btn); layout.addWidget(batch_update_btn); layout.addWidget(refresh_btn)
        layout.addSpacing(20)
        layout.addWidget(QLabel("搜索:")); layout.addWidget(self.search_edit)
        layout.addWidget(QLabel("状态:")); layout.addWidget(self.status_filter)
        layout.addWidget(QLabel("默认账号:")); layout.addWidget(self.account_filter)
        layout.addStretch()
        return widget

    def _create_strategy_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels(["选择", "策略ID", "策略名称", "框架", "类型", "默认账号", "状态", "最后更新", "操作"])
        header = table.horizontalHeader()
        self.select_all_checkbox = QCheckBox()
        self.select_all_checkbox.stateChanged.connect(self._on_select_all_changed)
        select_all_widget = QWidget()
        select_all_layout = QHBoxLayout(select_all_widget)
        select_all_layout.setContentsMargins(0, 0, 0, 0)
        select_all_layout.setAlignment(Qt.AlignCenter)
        select_all_layout.addWidget(self.select_all_checkbox)
        header.setIndexWidget(header.model().index(0, 0), select_all_widget)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.ExtendedSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)
        table.itemDoubleClicked.connect(self._on_strategy_double_clicked)
        table.itemSelectionChanged.connect(self._on_strategy_selection_changed)
        table.itemChanged.connect(self._on_item_changed)
        return table

    # ===================== Backtest View =====================

    def _create_backtest_view(self) -> QWidget:
        view = QWidget()
        layout = QHBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        config_scroll = QScrollArea(); config_scroll.setWidgetResizable(True); config_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        config_panel = self._create_backtest_config_panel()
        config_scroll.setWidget(config_panel)
        layout.addWidget(config_scroll, 1)
        result_panel = self._create_backtest_result_panel()
        result_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(result_panel, 2)
        return view

    def _create_backtest_config_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        strategy_group = QGroupBox("策略选择")
        strategy_layout = QFormLayout(strategy_group)
        self.backtest_strategy_combo = QComboBox()
        strategy_layout.addRow("策略：", self.backtest_strategy_combo)
        layout.addWidget(strategy_group)
        config_group = QGroupBox("回测配置")
        config_layout = QFormLayout(config_group)
        self.backtest_start_date = QDateEdit(); self.backtest_start_date.setDate(QDateTime.currentDateTime().addDays(-365).date()); self.backtest_start_date.setCalendarPopup(True)
        self.backtest_end_date = QDateEdit(); self.backtest_end_date.setDate(QDateTime.currentDateTime().date()); self.backtest_end_date.setCalendarPopup(True)
        self.backtest_initial_capital = QDoubleSpinBox(); self.backtest_initial_capital.setRange(1000, 10000000); self.backtest_initial_capital.setValue(100000); self.backtest_initial_capital.setSuffix(" 元")
        self.backtest_commission_rate = QDoubleSpinBox(); self.backtest_commission_rate.setRange(0, 0.01); self.backtest_commission_rate.setValue(0.0003); self.backtest_commission_rate.setDecimals(4); self.backtest_commission_rate.setSuffix(" %")
        self.backtest_timeframe_combo = QComboBox()
        self.backtest_timeframe_combo.addItem("日线", TimeFrame.DAY_1); self.backtest_timeframe_combo.addItem("1小时", TimeFrame.HOUR_1)
        self.backtest_timeframe_combo.addItem("30分钟", TimeFrame.MINUTE_30); self.backtest_timeframe_combo.addItem("15分钟", TimeFrame.MINUTE_15)
        self.backtest_timeframe_combo.addItem("5分钟", TimeFrame.MINUTE_5); self.backtest_timeframe_combo.addItem("1分钟", TimeFrame.MINUTE_1)
        self.backtest_timeframe_combo.setCurrentIndex(0)
        config_layout.addRow("开始日期：", self.backtest_start_date); config_layout.addRow("结束日期：", self.backtest_end_date)
        config_layout.addRow("时间周期：", self.backtest_timeframe_combo); config_layout.addRow("初始资金：", self.backtest_initial_capital)
        config_layout.addRow("手续费率：", self.backtest_commission_rate)
        layout.addWidget(config_group)
        button_layout = QHBoxLayout()
        self.run_backtest_button = QPushButton("开始回测"); self.run_backtest_button.clicked.connect(self._run_backtest)
        self.batch_backtest_button = QPushButton("批量回测"); self.batch_backtest_button.clicked.connect(self._batch_backtest)
        self.parameter_scan_button = QPushButton("参数扫描"); self.parameter_scan_button.clicked.connect(self._parameter_scan)
        button_layout.addWidget(self.run_backtest_button); button_layout.addWidget(self.batch_backtest_button); button_layout.addWidget(self.parameter_scan_button)
        layout.addLayout(button_layout)
        layout.addStretch()
        return panel

    def _create_backtest_result_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.backtest_progress_group = QGroupBox("回测进度")
        progress_layout = QVBoxLayout(self.backtest_progress_group)
        self.backtest_progress_bar = QProgressBar(); self.backtest_progress_bar.setRange(0, 100)
        self.backtest_status_label = QLabel("等待开始..."); self.backtest_status_label.setAlignment(Qt.AlignCenter)
        self.cancel_backtest_button = QPushButton("取消"); self.cancel_backtest_button.clicked.connect(self._cancel_backtest); self.cancel_backtest_button.setEnabled(False)
        progress_layout.addWidget(self.backtest_progress_bar); progress_layout.addWidget(self.backtest_status_label); progress_layout.addWidget(self.cancel_backtest_button)
        layout.addWidget(self.backtest_progress_group)
        self.backtest_metrics_group = QGroupBox("性能指标")
        metrics_layout = QGridLayout(self.backtest_metrics_group)
        self.total_return_card = self._create_metric_card("总收益率", "N/A", 'return')
        self.sharpe_ratio_card = self._create_metric_card("夏普比率", "N/A", 'sharpe')
        self.max_drawdown_card = self._create_metric_card("最大回撤", "N/A", 'drawdown')
        self.win_rate_card = self._create_metric_card("胜率", "N/A", 'win_rate')
        metrics_layout.addWidget(self.total_return_card, 0, 0); metrics_layout.addWidget(self.sharpe_ratio_card, 0, 1)
        metrics_layout.addWidget(self.max_drawdown_card, 0, 2); metrics_layout.addWidget(self.win_rate_card, 0, 3)
        layout.addWidget(self.backtest_metrics_group)
        self.backtest_chart_tabs = QTabWidget()
        if MATPLOTLIB_AVAILABLE:
            self.equity_chart = self._create_chart_widget("策略权益曲线", "日期", "累计收益率", '%m-%d')
            self.backtest_chart_tabs.addTab(self.equity_chart, "权益曲线")
            self.drawdown_chart = self._create_chart_widget("策略回撤分析", "日期", "回撤比例", '%m-%d')
            self.backtest_chart_tabs.addTab(self.drawdown_chart, "回撤分析")
            self.trades_chart = self._create_chart_widget("交易记录分析", "交易序号", "盈亏金额")
            self.backtest_chart_tabs.addTab(self.trades_chart, "交易记录")
        else:
            self.backtest_chart_tabs.addTab(QLabel("图表功能需要安装 matplotlib 库"), "图表")
        layout.addWidget(self.backtest_chart_tabs)
        return panel

    def _create_metric_card(self, title: str, value: str, metric_type: str) -> QWidget:
        gradients = {'return': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #10B981, stop:1 #059669)',
                     'sharpe': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3B82F6, stop:1 #1E40AF)',
                     'drawdown': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EF4444, stop:1 #B91C1C)',
                     'win_rate': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706)'}
        card = QFrame(); card.setMinimumHeight(80); card.setMinimumWidth(150); card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout = QVBoxLayout(card); layout.setAlignment(Qt.AlignCenter); layout.setSpacing(4); layout.setContentsMargins(12, 8, 12, 8)
        title_label = QLabel(title); title_label.setAlignment(Qt.AlignCenter); title_label.setObjectName("card_title")
        value_label = QLabel(value); value_label.setAlignment(Qt.AlignCenter); value_label.setObjectName("value_label")
        layout.addWidget(title_label); layout.addWidget(value_label)
        card.value_label = value_label; card.title_label = title_label; card._gradient_type = metric_type
        gradient = gradients.get(metric_type, gradients['return'])
        card.setStyleSheet(f"QFrame {{ background: {gradient}; border-radius: 8px; padding: 12px; }} QLabel {{ color: white; }} QLabel#value_label {{ font-size: 20px; font-weight: bold; }}")
        return card

    def _create_chart_widget(self, title: str, xlabel: str, ylabel: str, date_fmt: str = None) -> QWidget:
        if not MATPLOTLIB_AVAILABLE: return QLabel("图表不可用")
        widget = FigureCanvas(Figure(figsize=(10, 6))); self._cached_charts.append(widget)
        if self.theme_manager: self.theme_manager.apply_chart_theme(widget.figure)
        ax = widget.figure.add_subplot(111)
        ax.set_title(title, fontsize=14, fontweight='bold'); ax.set_xlabel(xlabel, fontsize=12); ax.set_ylabel(ylabel, fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.text(0.5, 0.5, '等待回测完成...', transform=ax.transAxes, ha='center', va='center', fontsize=14, alpha=0.5)
        ax.legend()
        if date_fmt: ax.xaxis.set_major_formatter(mdates.DateFormatter(date_fmt))
        return widget

    # ===================== Optimization View =====================

    def _create_optimization_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        strategy_selection_widget = QWidget()
        strategy_selection_layout = QHBoxLayout(strategy_selection_widget)
        strategy_selection_layout.setContentsMargins(0, 0, 0, 10)
        strategy_label = QLabel("选择策略:"); strategy_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        strategy_selection_layout.addWidget(strategy_label)
        self.optimization_strategy_combo = QComboBox(); self.optimization_strategy_combo.setMinimumWidth(300)
        strategy_selection_layout.addWidget(self.optimization_strategy_combo); strategy_selection_layout.addStretch()
        layout.addWidget(strategy_selection_widget)
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._create_optimization_config_panel())
        splitter.addWidget(self._create_optimization_result_panel())
        splitter.setStretchFactor(0, 1); splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        self._load_optimization_strategies()
        self.optimization_strategy_combo.currentIndexChanged.connect(self._on_optimization_strategy_changed)
        return widget

    def _create_optimization_config_panel(self) -> QWidget:
        panel = QGroupBox("优化配置")
        layout = QVBoxLayout(panel)
        config_group = QGroupBox("算法配置")
        config_layout = QFormLayout(config_group)
        self.opt_algorithm_combo = QComboBox(); self.opt_algorithm_combo.addItems(['grid_search', 'random_search', 'bayesian'])
        self.opt_target_metric_combo = QComboBox(); self.opt_target_metric_combo.addItems(['total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate'])
        self.opt_max_iterations = QSpinBox(); self.opt_max_iterations.setRange(10, 1000); self.opt_max_iterations.setValue(100)
        self.opt_timeframe_combo = QComboBox()
        self.opt_timeframe_combo.addItem("日线", TimeFrame.DAY_1); self.opt_timeframe_combo.addItem("1小时", TimeFrame.HOUR_1)
        self.opt_timeframe_combo.addItem("30分钟", TimeFrame.MINUTE_30); self.opt_timeframe_combo.addItem("15分钟", TimeFrame.MINUTE_15)
        self.opt_timeframe_combo.addItem("5分钟", TimeFrame.MINUTE_5); self.opt_timeframe_combo.addItem("1分钟", TimeFrame.MINUTE_1)
        self.opt_timeframe_combo.setCurrentIndex(0)
        config_layout.addRow("优化算法：", self.opt_algorithm_combo); config_layout.addRow("目标指标：", self.opt_target_metric_combo)
        config_layout.addRow("最大迭代：", self.opt_max_iterations); config_layout.addRow("时间周期：", self.opt_timeframe_combo)
        layout.addWidget(config_group)
        param_group = QGroupBox("参数范围")
        param_layout = QVBoxLayout(param_group)
        self.opt_param_table = QTableWidget()
        self.opt_param_table.setColumnCount(5); self.opt_param_table.setHorizontalHeaderLabels(["参数名", "最小值", "最大值", "步长", "类型"])
        self.opt_param_table.horizontalHeader().setStretchLastSection(True)
        params = [("lookback_period", "5", "60", "5", "int"), ("threshold", "0.01", "0.1", "0.01", "float"),
                  ("stop_loss", "0.02", "0.1", "0.01", "float"), ("take_profit", "0.05", "0.2", "0.01", "float")]
        self.opt_param_table.setRowCount(len(params))
        for row, (name, min_val, max_val, step, param_type) in enumerate(params):
            self.opt_param_table.setItem(row, 0, QTableWidgetItem(name)); self.opt_param_table.setItem(row, 1, QTableWidgetItem(min_val))
            self.opt_param_table.setItem(row, 2, QTableWidgetItem(max_val)); self.opt_param_table.setItem(row, 3, QTableWidgetItem(step))
            self.opt_param_table.setItem(row, 4, QTableWidgetItem(param_type))
        param_layout.addWidget(self.opt_param_table)
        button_layout = QHBoxLayout()
        add_param_btn = QPushButton("添加参数"); add_param_btn.clicked.connect(self._add_optimization_param)
        import_btn = QPushButton("导入范围"); import_btn.clicked.connect(self._import_optimization_ranges)
        export_btn = QPushButton("导出范围"); export_btn.clicked.connect(self._export_optimization_ranges)
        button_layout.addWidget(add_param_btn); button_layout.addWidget(import_btn); button_layout.addWidget(export_btn)
        param_layout.addLayout(button_layout)
        layout.addWidget(param_group)
        start_layout = QHBoxLayout()
        self.start_optimization_button = QPushButton("开始优化"); self.start_optimization_button.clicked.connect(self._start_optimization)
        self.opt_scan_button = QPushButton("参数扫描"); self.opt_scan_button.clicked.connect(self._parameter_scan)
        self.opt_sensitivity_button = QPushButton("敏感性分析"); self.opt_sensitivity_button.clicked.connect(self._sensitivity_analysis)
        start_layout.addWidget(self.start_optimization_button); start_layout.addWidget(self.opt_scan_button); start_layout.addWidget(self.opt_sensitivity_button)
        layout.addLayout(start_layout)
        return panel

    def _create_optimization_result_panel(self) -> QWidget:
        panel = QGroupBox("优化结果")
        layout = QVBoxLayout(panel)
        self.opt_progress_group = QGroupBox("优化进度")
        progress_layout = QVBoxLayout(self.opt_progress_group)
        self.opt_progress_bar = QProgressBar(); self.opt_progress_bar.setRange(0, 100)
        self.opt_iteration_label = QLabel("当前迭代：0/100"); self.opt_iteration_label.setAlignment(Qt.AlignCenter)
        self.opt_best_value_label = QLabel("最佳值：0.0000"); self.opt_best_value_label.setAlignment(Qt.AlignCenter)
        self.cancel_optimization_button = QPushButton("取消"); self.cancel_optimization_button.clicked.connect(self._cancel_optimization); self.cancel_optimization_button.setEnabled(False)
        progress_layout.addWidget(self.opt_progress_bar); progress_layout.addWidget(self.opt_iteration_label)
        progress_layout.addWidget(self.opt_best_value_label); progress_layout.addWidget(self.cancel_optimization_button)
        layout.addWidget(self.opt_progress_group)
        if MATPLOTLIB_AVAILABLE:
            self.optimization_chart = self._create_chart_widget("优化曲线", "迭代次数", "目标指标")
            layout.addWidget(self.optimization_chart)
        else:
            layout.addWidget(QLabel("图表功能需要安装 matplotlib 库"))
        best_param_group = QGroupBox("最佳参数")
        best_param_layout = QVBoxLayout(best_param_group)
        self.best_param_table = QTableWidget()
        self.best_param_table.setColumnCount(4); self.best_param_table.setHorizontalHeaderLabels(["参数名", "最佳值", "当前值", "改进"])
        best_param_layout.addWidget(self.best_param_table)
        apply_button = QPushButton("应用最佳参数"); apply_button.clicked.connect(self._apply_best_parameters)
        save_button = QPushButton("保存配置"); save_button.clicked.connect(self._save_optimization_config)
        btn_layout = QHBoxLayout(); btn_layout.addWidget(apply_button); btn_layout.addWidget(save_button)
        best_param_layout.addLayout(btn_layout)
        layout.addWidget(best_param_group)
        return panel

    # ===================== Performance View =====================

    def _create_performance_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QWidget(); scroll_layout = QVBoxLayout(scroll_content); scroll_layout.setContentsMargins(0, 0, 0, 0); scroll_layout.setSpacing(15)
        overview_group = QGroupBox("性能概览")
        overview_layout = QGridLayout(overview_group)
        self.performance_metric_labels = {}
        metrics_definitions = [("total_return", "总收益率", FINANCIAL_COLORS['profit']), ("annual_return", "年化收益率", FINANCIAL_COLORS['profit']),
                               ("sharpe_ratio", "夏普比率", FINANCIAL_COLORS['primary']), ("max_drawdown", "最大回撤", FINANCIAL_COLORS['loss']),
                               ("win_rate", "胜率", FINANCIAL_COLORS['warning']), ("profit_loss_ratio", "盈亏比", FINANCIAL_COLORS['auxiliary_1']),
                               ("avg_holding_days", "平均持仓天数", FINANCIAL_COLORS['auxiliary_2'])]
        for i, (metric_key, name, color) in enumerate(metrics_definitions):
            label = QLabel(f"{name}:"); value_label = QLabel("--"); value_label.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
            self.performance_metric_labels[metric_key] = value_label
            row, col = divmod(i, 4)
            overview_layout.addWidget(label, row, col * 2); overview_layout.addWidget(value_label, row, col * 2 + 1)
        load_perf_btn = QPushButton("加载性能数据"); load_perf_btn.clicked.connect(self._load_performance_data)
        overview_layout.addWidget(load_perf_btn, 2, 4)
        scroll_layout.addWidget(overview_group)
        comparison_group = QGroupBox("策略对比")
        comparison_layout = QVBoxLayout(comparison_group)
        toolbar_layout = QHBoxLayout()
        toolbar_layout.addWidget(QLabel("选择策略进行对比："))
        self.compare_strategy_combo1 = QComboBox(); self.compare_strategy_combo1.setMinimumWidth(200)
        self.compare_strategy_combo2 = QComboBox(); self.compare_strategy_combo2.setMinimumWidth(200)
        self.compare_button = QPushButton("开始对比"); self.compare_button.clicked.connect(self._compare_strategies)
        toolbar_layout.addWidget(self.compare_strategy_combo1); toolbar_layout.addWidget(QLabel("vs")); toolbar_layout.addWidget(self.compare_strategy_combo2)
        toolbar_layout.addWidget(self.compare_button); toolbar_layout.addStretch()
        comparison_layout.addLayout(toolbar_layout)
        self.comparison_table = QTableWidget()
        self.comparison_table.setColumnCount(3); self.comparison_table.setHorizontalHeaderLabels(["指标", "策略1", "策略2"])
        self.comparison_table.horizontalHeader().setStretchLastSection(True); self.comparison_table.setAlternatingRowColors(True)
        comparison_layout.addWidget(self.comparison_table)
        scroll_layout.addWidget(comparison_group)
        chart_group = QGroupBox("性能图表")
        chart_layout = QVBoxLayout(chart_group)
        if MATPLOTLIB_AVAILABLE:
            self.performance_chart = self._create_chart_widget("策略性能分析", "时间", "收益率 (%)", '%m')
            chart_layout.addWidget(self.performance_chart)
        else:
            chart_layout.addWidget(QLabel("图表功能需要安装 matplotlib 库"))
        scroll_layout.addWidget(chart_group)
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        self._load_comparison_strategies()
        return widget

    # ===================== AI Strategy View =====================

    def _create_ai_strategy_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        toolbar_layout = QHBoxLayout()
        create_btn = QPushButton("创建AI策略"); create_btn.clicked.connect(self._create_ai_strategy)
        edit_btn = QPushButton("编辑策略"); edit_btn.clicked.connect(self._edit_ai_strategy)
        duplicate_btn = QPushButton("复制策略"); duplicate_btn.clicked.connect(self._duplicate_ai_strategy)
        delete_btn = QPushButton("删除策略"); delete_btn.clicked.connect(self._delete_ai_strategy)
        refresh_btn = QPushButton("刷新"); refresh_btn.clicked.connect(self._load_ai_strategies)
        toolbar_layout.addWidget(create_btn); toolbar_layout.addWidget(edit_btn); toolbar_layout.addWidget(duplicate_btn)
        toolbar_layout.addWidget(delete_btn); toolbar_layout.addStretch(); toolbar_layout.addWidget(refresh_btn)
        layout.addLayout(toolbar_layout)
        splitter = QSplitter(Qt.Horizontal)
        left_widget = QWidget(); left_layout = QVBoxLayout(left_widget)
        list_group = QGroupBox("AI策略列表"); list_layout = QVBoxLayout(list_group)
        self.ai_strategy_table = QTableWidget(); self.ai_strategy_table.setAlternatingRowColors(True)
        self.ai_strategy_table.setSelectionBehavior(QTableWidget.SelectRows); self.ai_strategy_table.setSelectionMode(QTableWidget.SingleSelection)
        self.ai_strategy_table.itemSelectionChanged.connect(self._on_ai_strategy_selection_changed)
        columns = ["策略ID", "策略名称", "策略类型", "状态", "创建时间", "版本"]
        self.ai_strategy_table.setColumnCount(len(columns)); self.ai_strategy_table.setHorizontalHeaderLabels(columns)
        header = self.ai_strategy_table.horizontalHeader(); header.setStretchLastSection(True)
        list_layout.addWidget(self.ai_strategy_table); left_layout.addWidget(list_group)
        splitter.addWidget(left_widget)
        right_widget = QWidget(); right_layout = QVBoxLayout(right_widget)
        detail_group = QGroupBox("策略详情"); detail_layout = QVBoxLayout(detail_group)
        self.ai_strategy_editor = StrategyEditorWidget(); self.ai_strategy_editor.strategy_changed.connect(self._on_ai_strategy_data_changed)
        detail_layout.addWidget(self.ai_strategy_editor); right_layout.addWidget(detail_group)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1); splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)
        self.ai_status_label = QLabel("就绪")
        layout.addWidget(self.ai_status_label)
        self._load_ai_strategies()
        return widget

    # ===================== Editor View =====================

    def _create_editor_view(self) -> QWidget:
        try:
            from gui.widgets.strategy_code_editor import StrategyCodeEditor
            widget = QWidget(); layout = QVBoxLayout(widget); layout.setContentsMargins(0, 0, 0, 0)
            self.code_editor = StrategyCodeEditor()
            self.code_editor.code_saved.connect(self._on_code_saved)
            self.code_editor.code_executed.connect(self._on_code_executed)
            layout.addWidget(self.code_editor)
            return widget
        except ImportError:
            widget = QWidget(); layout = QVBoxLayout(widget)
            layout.addWidget(QLabel("代码编辑器组件不可用"))
            return widget

    def _on_code_saved(self, file_path: str):
        logger.info(f"策略代码已保存: {file_path}")
        self._load_strategies()

    def _on_code_executed(self, code: str):
        logger.info("策略代码执行请求")
        try:
            import tempfile, os
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f: f.write(code); temp_file = f.name
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("temp_strategy", temp_file)
                module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
                for name in dir(module):
                    obj = getattr(module, name)
                    if isinstance(obj, type) and hasattr(obj, 'generate_signals'):
                        logger.info(f"发现策略类: {name}")
                        QMessageBox.information(self, "执行成功", f"策略代码执行成功\n发现策略类: {name}")
                        break
            finally: os.unlink(temp_file)
        except Exception as e:
            logger.error(f"策略代码执行失败: {e}")
            QMessageBox.critical(self, "执行失败", f"策略代码执行失败:\n{str(e)}")

    # ===================== Workflow View =====================

    def _create_workflow_view(self) -> QWidget:
        try:
            from gui.widgets.strategy_development_workflow import StrategyDevelopmentWorkflow
            widget = QWidget(); layout = QVBoxLayout(widget); layout.setContentsMargins(0, 0, 0, 0)
            self.workflow = StrategyDevelopmentWorkflow()
            self.workflow.workflow_completed.connect(self._on_workflow_completed)
            layout.addWidget(self.workflow)
            return widget
        except ImportError:
            widget = QWidget(); layout = QVBoxLayout(widget)
            layout.addWidget(QLabel("开发工作流组件不可用"))
            return widget

    def _on_workflow_completed(self, workflow_data: Dict):
        logger.info(f"策略开发工作流完成: {workflow_data.get('name', 'Unknown')}")
        self._load_strategies()
        QMessageBox.information(self, "工作流完成", f"策略 '{workflow_data.get('name', 'Unknown')}' 已成功创建并保存！")

    # ===================== Theme & Data Loading =====================

    def _apply_theme(self):
        if self.theme_manager: self.theme_manager.apply_theme(self)

    def _load_data(self):
        self._load_strategies()
        self._update_stat_cards()

    def _update_stat_cards(self):
        for card in [self.total_strategy_card, self.running_strategy_card, self.configured_strategy_card, self.error_strategy_card]:
            card.set_value("0", trend_percent=0, trend_data=[0] * 7)

    def _load_strategies(self):
        if self.strategy_service:
            try:
                strategies = self.strategy_service.get_all_strategy_configs()
                self._populate_strategy_table(strategies)
                self._update_combo_with_strategies(self.backtest_strategy_combo, strategies)
                if hasattr(self, 'optimization_strategy_combo'): self._update_combo_with_strategies(self.optimization_strategy_combo, strategies)
                self._update_home_stats(strategies)
                logger.info(f"加载了 {len(strategies)} 个策略")
            except Exception as e: logger.error(f"加载策略失败: {e}")

    def _populate_strategy_table(self, strategies: List[StrategyConfig]):
        if not hasattr(self, 'strategy_table'): return
        self.strategy_table.blockSignals(True)
        current_ids = set()
        for row in range(self.strategy_table.rowCount()):
            item = self.strategy_table.item(row, 1)
            if item: current_ids.add(item.text())
        new_ids = {s.strategy_id for s in strategies}
        to_remove = current_ids - new_ids; to_add = new_ids - current_ids; to_update = current_ids & new_ids
        strategy_map = {s.strategy_id: s for s in strategies}
        rows_to_remove = []
        for row in range(self.strategy_table.rowCount()):
            item = self.strategy_table.item(row, 1)
            if item and item.text() in to_remove: rows_to_remove.append(row)
        for row in sorted(rows_to_remove, reverse=True): self.strategy_table.removeRow(row)
        for row in range(self.strategy_table.rowCount()):
            item = self.strategy_table.item(row, 1)
            if item and item.text() in to_update:
                strategy = strategy_map.get(item.text())
                if strategy: self._update_strategy_row(row, strategy)
        for sid in to_add:
            strategy = strategy_map.get(sid)
            if strategy: self._add_strategy_row(self.strategy_table.rowCount(), strategy)
        self.strategy_table.blockSignals(False)
        self._update_select_all_checkbox_state()

    def _update_strategy_row(self, row: int, strategy: StrategyConfig):
        strategy_name = strategy.metadata.get('name', strategy.strategy_id)
        name_item = self.strategy_table.item(row, 2)
        if name_item: name_item.setText(strategy_name)
        plugin_item = self.strategy_table.item(row, 3)
        if plugin_item: plugin_item.setText(strategy.plugin_type)
        strategy_type = strategy.metadata.get('type', 'unknown')
        type_item = self.strategy_table.item(row, 4)
        if type_item: type_item.setText(self._get_strategy_type_text(strategy_type))
        default_account_id = strategy.metadata.get('default_account_id', 'default')
        account_item = self.strategy_table.item(row, 5)
        if account_item: account_item.setText("系统默认" if default_account_id == 'default' else default_account_id)
        last_updated = strategy.updated_at
        if last_updated:
            try: last_updated = last_updated.strftime('%Y-%m-%d %H:%M')
            except Exception as e: logger.warning(f"格式化更新时间失败: {e}")
        updated_item = self.strategy_table.item(row, 7)
        if updated_item: updated_item.setText(last_updated)

    def _add_strategy_row(self, row: int, strategy: StrategyConfig):
        checkbox_item = QTableWidgetItem(); checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled); checkbox_item.setCheckState(Qt.Unchecked)
        self.strategy_table.setItem(row, 0, checkbox_item)
        self.strategy_table.setItem(row, 1, QTableWidgetItem(strategy.strategy_id))
        strategy_name = strategy.metadata.get('name', strategy.strategy_id)
        self.strategy_table.setItem(row, 2, QTableWidgetItem(strategy_name))
        self.strategy_table.setItem(row, 3, QTableWidgetItem(strategy.plugin_type))
        strategy_type = strategy.metadata.get('type', 'unknown')
        self.strategy_table.setItem(row, 4, QTableWidgetItem(self._get_strategy_type_text(strategy_type)))
        default_account_id = strategy.metadata.get('default_account_id', 'default')
        self.strategy_table.setItem(row, 5, QTableWidgetItem("系统默认" if default_account_id == 'default' else default_account_id))
        status = "已配置"; status_item = QTableWidgetItem(status); status_item.setForeground(QColor(STATUS_COLORS.get('configured', '#6B7280')))
        self.strategy_table.setItem(row, 6, status_item)
        last_updated = strategy.updated_at
        if last_updated:
            try: last_updated = last_updated.strftime('%Y-%m-%d %H:%M')
            except Exception as e: logger.warning(f"格式化更新时间失败: {e}")
        self.strategy_table.setItem(row, 7, QTableWidgetItem(last_updated))
        button_widget = QWidget(); button_layout = QHBoxLayout(button_widget); button_layout.setContentsMargins(2, 2, 2, 2); button_layout.setSpacing(5)
        edit_button = QPushButton("编辑"); edit_button.clicked.connect(lambda checked, sid=strategy.strategy_id: self._edit_strategy(sid))
        delete_button = QPushButton("删除"); delete_button.clicked.connect(lambda checked, sid=strategy.strategy_id: self._delete_strategy(sid))
        button_layout.addWidget(edit_button); button_layout.addWidget(delete_button)
        self.strategy_table.setCellWidget(row, 8, button_widget)

    def _update_combo_with_strategies(self, combo: QComboBox, strategies: List[StrategyConfig]):
        if not combo: return
        current_selection = combo.currentData()
        current_ids = {combo.itemData(i) for i in range(combo.count())}
        new_ids = {s.strategy_id for s in strategies}
        strategy_map = {s.strategy_id: s for s in strategies}
        for i in range(combo.count() - 1, -1, -1):
            if combo.itemData(i) not in new_ids: combo.removeItem(i)
        for sid in new_ids - current_ids:
            strategy = strategy_map.get(sid)
            if strategy: combo.addItem(f"{strategy.strategy_id}", strategy.strategy_id)
        if current_selection:
            index = combo.findData(current_selection)
            if index >= 0: combo.setCurrentIndex(index)

    def _get_strategy_type_text(self, strategy_type: str) -> str:
        type_map = {'momentum': '动量策略', 'mean_reversion': '均值回归', 'trend_following': '趋势跟踪',
                    'arbitrage': '套利策略', 'statistical': '统计套利', 'custom': '自定义策略', 'unknown': '未知'}
        return type_map.get(strategy_type, strategy_type)

    def _update_home_stats(self, strategies: List[StrategyConfig] = None):
        try:
            if strategies is None and self.strategy_service: strategies = self.strategy_service.get_all_strategy_configs()
            if not strategies: strategies = []
            total_count = len(strategies); running_count = 0; configured_count = 0; error_count = 0
            if self.strategy_service:
                try:
                    backtest_tasks = self.strategy_service.get_all_backtest_tasks()
                    for task_id, task in backtest_tasks.items():
                        if task.status.value == 'running': running_count += 1
                        if task.status.value == 'failed': error_count += 1
                except Exception as e: logger.warning(f"获取回测任务状态失败: {e}")
            for strategy in strategies:
                if strategy.metadata.get('default_account_id'): configured_count += 1
            self._update_card_value(self.total_strategy_card, str(total_count))
            self._update_card_value(self.running_strategy_card, str(running_count))
            self._update_card_value(self.configured_strategy_card, str(configured_count))
            self._update_card_value(self.error_strategy_card, str(error_count))
        except Exception as e: logger.error(f"更新首页统计失败: {e}")

    def _update_card_value(self, card: QWidget, value: str):
        try:
            if card is None: return
            value_label = card.findChild(QLabel, "value_label")
            if value_label: value_label.setText(value)
        except Exception as e: logger.warning(f"更新卡片值失败: {e}")

    def _on_theme_changed(self, theme):
        logger.info(f"主题已切换: {theme}")
        if self.theme_manager: self._update_chart_themes()

    def _update_chart_themes(self):
        if not self.theme_manager: return
        try:
            for chart in self._cached_charts:
                if chart and hasattr(chart, 'figure'): self.theme_manager.apply_chart_theme(chart.figure); chart.draw()
        except Exception as e: logger.error(f"更新图表主题失败: {e}")

    def _load_accounts_for_filter(self, account_filter: QComboBox):
        try:
            if not self.service_container: return
            from core.trading.account_manager import AccountManager
            account_manager = self.service_container.resolve(AccountManager)
            if account_manager:
                for account in account_manager.get_all_accounts(): account_filter.addItem(account.account_id, account.account_id)
        except Exception as e: logger.error(f"加载账号列表失败: {e}")

    def _load_comparison_strategies(self):
        if not self.strategy_service or not hasattr(self, 'compare_strategy_combo1'): return
        try:
            strategies = self.strategy_service.get_all_strategy_configs()
            self.compare_strategy_combo1.clear(); self.compare_strategy_combo2.clear()
            for strategy in strategies:
                display_text = f"{strategy.strategy_id} - {strategy.metadata.get('name', '')}"
                self.compare_strategy_combo1.addItem(display_text, strategy.strategy_id)
                self.compare_strategy_combo2.addItem(display_text, strategy.strategy_id)
        except Exception as e: logger.error(f"加载对比策略列表失败: {e}")

    def _load_optimization_strategies(self):
        try:
            from core.strategy.strategy_engine import get_strategy_engine
            strategy_engine = get_strategy_engine()
            strategies = strategy_engine.get_available_strategies()
            if hasattr(self, 'optimization_strategy_combo'):
                self.optimization_strategy_combo.clear()
                for strategy in strategies: self.optimization_strategy_combo.addItem(strategy['name'], strategy['id'])
        except Exception as e:
            logger.warning(f"加载优化策略列表失败：{e}")
            if hasattr(self, 'optimization_strategy_combo'):
                self.optimization_strategy_combo.clear()
                for i, name in enumerate(["MA 策略", "MACD 策略", "RSI 策略", "KDJ 策略", "布林带策略"]):
                    self.optimization_strategy_combo.addItem(name, f"strategy_{i}")

    def _on_optimization_strategy_changed(self, index: int):
        pass

    def _load_ai_strategies(self):
        if not self.database_service or not hasattr(self, 'ai_strategy_table'): return
        try:
            strategies = self.database_service.get_all_ai_strategies()
            self._populate_ai_strategy_table(strategies)
            if hasattr(self, 'ai_status_label'): self.ai_status_label.setText(f"已加载 {len(strategies)} 个AI策略")
        except Exception as e:
            if hasattr(self, 'ai_status_label'): self.ai_status_label.setText(f"加载失败: {e}")
            logger.error(f"加载AI策略失败: {e}")

    def _populate_ai_strategy_table(self, strategies: List[Dict]):
        if not hasattr(self, 'ai_strategy_table'): return
        self.ai_strategy_table.setRowCount(0)
        for strategy in strategies:
            row = self.ai_strategy_table.rowCount(); self.ai_strategy_table.insertRow(row)
            self.ai_strategy_table.setItem(row, 0, QTableWidgetItem(strategy.get('id', '')))
            self.ai_strategy_table.setItem(row, 1, QTableWidgetItem(strategy.get('name', '')))
            self.ai_strategy_table.setItem(row, 2, QTableWidgetItem(strategy.get('strategy_type', '')))
            self.ai_strategy_table.setItem(row, 3, QTableWidgetItem(strategy.get('status', '')))
            self.ai_strategy_table.setItem(row, 4, QTableWidgetItem(str(strategy.get('created_at', ''))))
            self.ai_strategy_table.setItem(row, 5, QTableWidgetItem(str(strategy.get('version', 1))))

    def _on_ai_strategy_selection_changed(self):
        selected_items = self.ai_strategy_table.selectedItems()
        if not selected_items: return
        row = selected_items[0].row()
        self.current_strategy_id = self.ai_strategy_table.item(row, 0).text()
        self._load_ai_strategy_detail(self.current_strategy_id)

    def _load_ai_strategy_detail(self, strategy_id: str):
        if not self.database_service or not hasattr(self, 'ai_strategy_editor'): return
        try:
            strategy = self.database_service.get_ai_strategy(strategy_id)
            if strategy: self.ai_strategy_editor.strategy_data = strategy; self.ai_strategy_editor._load_strategy_data()
        except Exception as e: logger.error(f"加载AI策略详情失败: {e}")

    def _on_ai_strategy_data_changed(self, strategy_data: Dict):
        if not self.current_strategy_id or not self.database_service: return
        try:
            self.database_service.update_ai_strategy(self.current_strategy_id, strategy_data)
            if hasattr(self, 'ai_status_label'): self.ai_status_label.setText(f"策略已更新: {self.current_strategy_id}")
            self.strategy_updated.emit(self.current_strategy_id); self._load_ai_strategies()
        except Exception as e: logger.error(f"更新AI策略失败: {e}")

    def _create_ai_strategy(self):
        if not self.database_service: QMessageBox.warning(self, "警告", "数据库服务不可用"); return
        dialog = QDialog(self); dialog.setWindowTitle("创建AI策略"); dialog.resize(600, 400)
        layout = QVBoxLayout(dialog)
        template_group = QGroupBox("选择模板"); template_layout = QFormLayout(template_group)
        template_combo = QComboBox()
        for name in StrategyTemplateManager.get_template_names():
            template_combo.addItem(StrategyTemplateManager.get_template_display_names().get(name, name), name)
        template_layout.addRow("策略模板:", template_combo); layout.addWidget(template_group)
        button_box = QHBoxLayout()
        create_btn = QPushButton("从模板创建"); create_btn.clicked.connect(lambda: self._create_ai_from_template(dialog, template_combo.currentData()))
        blank_btn = QPushButton("空白策略"); blank_btn.clicked.connect(lambda: self._create_ai_blank(dialog))
        cancel_btn = QPushButton("取消"); cancel_btn.clicked.connect(dialog.reject)
        button_box.addWidget(create_btn); button_box.addWidget(blank_btn); button_box.addWidget(cancel_btn)
        layout.addLayout(button_box); dialog.exec_()

    def _create_ai_from_template(self, dialog: QDialog, template_name: str):
        if not self.database_service: return
        try:
            template = StrategyTemplateManager.get_template(template_name)
            if not template: QMessageBox.warning(self, "警告", "模板不存在"); return
            strategy_id = self.database_service.create_ai_strategy(template)
            QMessageBox.information(self, "成功", f"策略已创建: {strategy_id}"); dialog.accept(); self._load_ai_strategies()
        except Exception as e: QMessageBox.critical(self, "错误", f"创建策略失败: {e}"); logger.error(f"创建AI策略失败: {e}")

    def _create_ai_blank(self, dialog: QDialog):
        if not self.database_service: return
        try:
            strategy_data = {'name': '新策略', 'description': '请填写策略描述', 'strategy_type': 'technical',
                             'parameters': {}, 'weight_config': {'equal_weight': True},
                             'risk_config': {'max_position_size': 0.1, 'max_drawdown': 0.15, 'volatility_limit': 0.2}}
            strategy_id = self.database_service.create_ai_strategy(strategy_data)
            QMessageBox.information(self, "成功", f"策略已创建: {strategy_id}"); dialog.accept(); self._load_ai_strategies()
        except Exception as e: QMessageBox.critical(self, "错误", f"创建策略失败: {e}")

    def _edit_ai_strategy(self):
        if not self.current_strategy_id: QMessageBox.warning(self, "警告", "请先选择一个策略"); return
        if not self.database_service: QMessageBox.warning(self, "警告", "数据库服务不可用"); return
        try:
            strategy = self.database_service.get_ai_strategy(self.current_strategy_id)
            if not strategy: QMessageBox.warning(self, "警告", "策略不存在"); return
            if hasattr(self, 'ai_status_label'): self.ai_status_label.setText(f"正在编辑策略: {self.current_strategy_id}")
            strategy_editor = StrategyEditorWidget(strategy_data=strategy, parent=self)
            strategy_editor.strategy_changed.connect(self._on_ai_strategy_data_changed)
            dialog = QDialog(self); dialog.setWindowTitle(f"编辑策略: {strategy.get('name', '')}"); dialog.resize(800, 600)
            layout = QVBoxLayout(dialog); layout.addWidget(strategy_editor)
            button_box = QHBoxLayout()
            save_btn = QPushButton("保存"); save_btn.clicked.connect(lambda: self._save_ai_edited_strategy(dialog, strategy_editor))
            cancel_btn = QPushButton("取消"); cancel_btn.clicked.connect(dialog.reject)
            button_box.addWidget(save_btn); button_box.addWidget(cancel_btn); layout.addLayout(button_box)
            dialog.exec_()
        except Exception as e: QMessageBox.critical(self, "错误", f"编辑策略失败: {e}")

    def _save_ai_edited_strategy(self, dialog: QDialog, editor: StrategyEditorWidget):
        try:
            if not self.current_strategy_id: QMessageBox.warning(self, "警告", "策略ID不存在"); return
            strategy_data = {'name': editor.name_edit.text(), 'description': editor.description_edit.toPlainText(),
                             'strategy_type': editor.strategy_type_combo.currentText(), 'tags': editor.tags_edit.text(),
                             'parameters': json.loads(editor.params_edit.toPlainText()),
                             'weight_config': {'equal_weight': editor.equal_weight_check.isChecked(),
                                               'custom_weights': json.loads(editor.weight_edit.toPlainText()) if not editor.equal_weight_check.isChecked() else {}},
                             'risk_config': {'max_position_size': editor.max_position_spin.value(),
                                             'max_drawdown': editor.max_drawdown_spin.value(),
                                             'volatility_limit': editor.volatility_spin.value()}}
            self.database_service.update_ai_strategy(self.current_strategy_id, strategy_data)
            QMessageBox.information(self, "成功", "策略已更新"); dialog.accept(); self._load_ai_strategies()
        except json.JSONDecodeError as e: QMessageBox.critical(self, "JSON解析错误", f"JSON格式错误: {e}")
        except Exception as e: QMessageBox.critical(self, "错误", f"保存策略失败: {e}")

    def _duplicate_ai_strategy(self):
        if not self.current_strategy_id: QMessageBox.warning(self, "警告", "请先选择一个策略"); return
        if not self.database_service: QMessageBox.warning(self, "警告", "数据库服务不可用"); return
        try:
            strategy = self.database_service.get_ai_strategy(self.current_strategy_id)
            if not strategy: QMessageBox.warning(self, "警告", "策略不存在"); return
            new_strategy = strategy.copy(); new_strategy['id'] = str(uuid.uuid4()); new_strategy['name'] = f"{strategy['name']} (副本)"; new_strategy['created_by'] = 'user'
            new_id = self.database_service.create_ai_strategy(new_strategy)
            QMessageBox.information(self, "成功", f"策略已复制: {new_id}"); self._load_ai_strategies()
        except Exception as e: QMessageBox.critical(self, "错误", f"复制策略失败: {e}")

    def _delete_ai_strategy(self):
        if not self.current_strategy_id: QMessageBox.warning(self, "警告", "请先选择一个策略"); return
        reply = QMessageBox.question(self, "确认删除", f"确定要删除策略 {self.current_strategy_id} 吗？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if not self.database_service: QMessageBox.warning(self, "警告", "数据库服务不可用"); return
            try:
                self.database_service.delete_ai_strategy(self.current_strategy_id)
                QMessageBox.information(self, "成功", "策略已删除"); self.current_strategy_id = None; self._load_ai_strategies()
            except Exception as e: QMessageBox.critical(self, "错误", f"删除策略失败: {e}")

    # ===================== Filter & Search =====================

    def _on_search_text_changed(self, text: str):
        try: self._filter_strategies(text, self._get_current_status_filter(), self._get_current_account_filter())
        except Exception as e: logger.error(f"搜索失败: {e}")

    def _on_status_filter_changed(self, text: str):
        try: self._filter_strategies(self._get_current_search_text(), text, self._get_current_account_filter())
        except Exception as e: logger.error(f"状态筛选失败: {e}")

    def _on_account_filter_changed(self, text: str):
        try: self._filter_strategies(self._get_current_search_text(), self._get_current_status_filter(), self._get_current_account_filter())
        except Exception as e: logger.error(f"账号筛选失败: {e}")

    def _filter_strategies(self, search_text: str, status_filter: str, account_filter: str = "all"):
        if not self.strategy_service or not hasattr(self, 'strategy_table'): return
        try:
            self.strategy_table.blockSignals(True)
            all_strategies = self.strategy_service.get_all_strategy_configs()
            filtered = []
            for strategy in all_strategies:
                if search_text:
                    search_lower = search_text.lower()
                    if search_lower not in strategy.strategy_id.lower() and search_lower not in strategy.metadata.get('name', '').lower(): continue
                if status_filter and status_filter != "全部状态":
                    status_map = {"已配置": "configured", "运行中": "running", "错误": "error"}
                    filter_status = status_map.get(status_filter, "")
                    if filter_status and getattr(strategy, 'status', 'stopped') != filter_status: continue
                if account_filter and account_filter != "all":
                    if strategy.metadata.get('default_account_id', 'default') != account_filter: continue
                filtered.append(strategy)
            self.strategy_table.setRowCount(len(filtered))
            for row, strategy in enumerate(filtered): self._add_strategy_row(row, strategy)
            self.strategy_table.blockSignals(False); self._update_select_all_checkbox_state()
        except Exception as e: logger.error(f"筛选策略失败: {e}")
        finally: self.strategy_table.blockSignals(False)

    def _get_current_search_text(self) -> str: return self.search_edit.text() if hasattr(self, 'search_edit') else ""
    def _get_current_status_filter(self) -> str: return self.status_filter.currentText() if hasattr(self, 'status_filter') else ""
    def _get_current_account_filter(self) -> str: return self.account_filter.currentData() if hasattr(self, 'account_filter') else "all"

    # ===================== Table Events =====================

    def _on_strategy_double_clicked(self, item):
        try:
            row = item.row(); strategy_id_item = self.strategy_table.item(row, 1)
            if strategy_id_item: self._edit_strategy(strategy_id_item.text())
        except Exception as e: logger.error(f"打开策略详情失败: {e}")

    def _on_strategy_selection_changed(self):
        try:
            selected_items = self.strategy_table.selectedItems()
            if not selected_items: return
            row = selected_items[0].row(); strategy_id_item = self.strategy_table.item(row, 1)
            if strategy_id_item: self.current_strategy_id = strategy_id_item.text(); self.strategy_selected.emit(self.current_strategy_id)
        except Exception as e: logger.error(f"策略选择失败: {e}")

    def _on_select_all_changed(self, state: int):
        try:
            for row in range(self.strategy_table.rowCount()):
                checkbox_item = self.strategy_table.item(row, 0)
                if checkbox_item: checkbox_item.setCheckState(Qt.CheckState(state))
        except Exception as e: logger.error(f"全选操作失败: {e}")

    def _on_item_changed(self, item: QTableWidgetItem):
        try:
            if item.column() == 0: self._update_select_all_checkbox_state()
        except Exception as e: logger.error(f"表格项变化处理失败: {e}")

    def _update_select_all_checkbox_state(self):
        if not hasattr(self, 'select_all_checkbox'): return
        total_rows = self.strategy_table.rowCount()
        if total_rows == 0: self.select_all_checkbox.setCheckState(Qt.Unchecked); return
        checked_count = 0
        for row in range(total_rows):
            checkbox_item = self.strategy_table.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.Checked: checked_count += 1
        if checked_count == 0: self.select_all_checkbox.setCheckState(Qt.Unchecked)
        elif checked_count == total_rows: self.select_all_checkbox.setCheckState(Qt.Checked)
        else: self.select_all_checkbox.setCheckState(Qt.PartiallyChecked)

    # ===================== Strategy CRUD =====================

    def _quick_backtest(self):
        if hasattr(self, 'backtest_view'): self._switch_view('backtest')

    def _create_strategy(self):
        try:
            if not self.strategy_service: QMessageBox.warning(self, "警告", "策略服务未初始化"); return
            dialog = _StrategyConfigDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                config_data = dialog.get_config_data()
                strategy_id = config_data.get('strategy_id', '').strip()
                if not strategy_id: QMessageBox.warning(self, "警告", "策略ID不能为空"); return
                if not re.match(r'^[a-zA-Z0-9_-]+$', strategy_id): QMessageBox.warning(self, "警告", "策略ID只能包含字母、数字、下划线和连字符"); return
                strategy_name = config_data.get('metadata', {}).get('name', '').strip()
                if not strategy_name: QMessageBox.warning(self, "警告", "策略名称不能为空"); return
                existing = self.strategy_service.get_strategy_config(strategy_id)
                if existing: QMessageBox.warning(self, "警告", f"策略ID '{strategy_id}' 已存在"); return
                success = self.strategy_service.create_strategy_config(strategy_id=strategy_id, plugin_type=config_data['plugin_type'],
                                                                      parameters=config_data.get('parameters', {}), metadata=config_data.get('metadata', {}))
                if success: QMessageBox.information(self, "成功", f"策略创建成功！\n策略ID: {strategy_id}"); self._load_strategies()
                else: QMessageBox.warning(self, "警告", "策略创建失败")
        except Exception as e: logger.error(f"创建策略失败: {e}"); QMessageBox.critical(self, "错误", f"创建策略失败: {str(e)}")

    def _import_strategy(self):
        try:
            if not self.strategy_service: QMessageBox.warning(self, "警告", "策略服务未初始化"); return
            file_path, _ = QFileDialog.getOpenFileName(self, "导入策略", "", "策略文件 (*.json);;所有文件 (*.*)")
            if not file_path: return
            with open(file_path, 'r', encoding='utf-8') as f: strategy_data = json.load(f)
            if not isinstance(strategy_data, dict): QMessageBox.warning(self, "警告", "策略文件格式错误：必须是JSON对象"); return
            required_fields = ['strategy_id', 'plugin_type']
            missing = [f for f in required_fields if f not in strategy_data]
            if missing: QMessageBox.warning(self, "警告", f"缺少必需字段: {', '.join(missing)}"); return
            strategy_id = strategy_data.get('strategy_id', '').strip()
            if not strategy_id or not re.match(r'^[a-zA-Z0-9_-]+$', strategy_id): QMessageBox.warning(self, "警告", "策略ID格式不正确"); return
            if not strategy_data.get('plugin_type', '').strip(): QMessageBox.warning(self, "警告", "插件类型不能为空"); return
            parameters = strategy_data.get('parameters', {})
            if not isinstance(parameters, dict): QMessageBox.warning(self, "警告", "参数格式错误"); return
            metadata = strategy_data.get('metadata', {})
            if not isinstance(metadata, dict): QMessageBox.warning(self, "警告", "元数据格式错误"); return
            existing = self.strategy_service.get_strategy_config(strategy_id)
            if existing:
                reply = QMessageBox.question(self, "确认", f"策略ID '{strategy_id}' 已存在，是否覆盖？", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No: return
            success = self.strategy_service.create_strategy_config(strategy_id=strategy_id, plugin_type=strategy_data['plugin_type'],
                                                                  parameters=parameters, metadata=metadata)
            if success: QMessageBox.information(self, "成功", f"策略导入成功！\n策略ID: {strategy_id}"); self._load_strategies()
            else: QMessageBox.warning(self, "警告", "策略导入失败")
        except json.JSONDecodeError as e: QMessageBox.critical(self, "错误", f"JSON解析失败: {e}")
        except Exception as e: logger.error(f"导入策略失败: {e}"); QMessageBox.critical(self, "错误", f"导入策略失败: {str(e)}")

    def _export_strategy(self):
        try:
            selected_rows = self._get_selected_strategy_rows()
            if not selected_rows: QMessageBox.warning(self, "警告", "请先选择要导出的策略"); return
            if len(selected_rows) > 1: QMessageBox.warning(self, "警告", "请只选择一个策略进行导出"); return
            row = selected_rows[0]; strategy_id_item = self.strategy_table.item(row, 1)
            strategy_id = strategy_id_item.text() if strategy_id_item else None
            if not strategy_id: QMessageBox.warning(self, "警告", "无法获取策略ID"); return
            strategy_config = self.strategy_service.get_strategy_config(strategy_id)
            if strategy_config:
                strategy_data = {'strategy_id': strategy_config.strategy_id, 'plugin_type': strategy_config.plugin_type,
                                 'parameters': strategy_config.parameters, 'enabled': strategy_config.enabled, 'metadata': strategy_config.metadata}
                file_path, _ = QFileDialog.getSaveFileName(self, "导出策略", f"{strategy_id}.json", "策略文件 (*.json);;所有文件 (*.*)")
                if file_path:
                    with open(file_path, 'w', encoding='utf-8') as f: json.dump(strategy_data, f, indent=2, ensure_ascii=False, default=str)
                    QMessageBox.information(self, "成功", f"策略导出成功！\n保存路径: {file_path}")
            else: QMessageBox.warning(self, "警告", "无法获取策略配置")
        except Exception as e: logger.error(f"导出策略失败: {e}"); QMessageBox.critical(self, "错误", f"导出策略失败: {str(e)}")

    def _edit_strategy(self, strategy_id: str):
        try:
            strategy_config = self.strategy_service.get_strategy_config(strategy_id)
            if not strategy_config: QMessageBox.warning(self, "警告", "无法获取策略配置"); return
            dialog = _StrategyConfigDialog(self, strategy_config)
            if dialog.exec_() == QDialog.Accepted:
                config_data = dialog.get_config_data()
                success = self.strategy_service.update_strategy_config(strategy_id=strategy_id, plugin_type=config_data['plugin_type'],
                                                                      parameters=config_data['parameters'], metadata=config_data.get('metadata', {}))
                if success: QMessageBox.information(self, "成功", "策略更新成功"); self._load_strategies()
                else: QMessageBox.warning(self, "警告", "策略更新失败")
        except Exception as e: logger.error(f"编辑策略失败: {e}"); QMessageBox.critical(self, "错误", f"编辑策略失败: {str(e)}")

    def _delete_strategy(self, strategy_id: str):
        reply = QMessageBox.question(self, "确认删除", f"确定要删除策略 '{strategy_id}' 吗？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes and self.strategy_service:
            success = self.strategy_service.delete_strategy_config(strategy_id)
            if success: QMessageBox.information(self, "成功", "策略删除成功"); self._load_strategies()
            else: QMessageBox.warning(self, "失败", "策略删除失败")

    def _get_selected_strategy_rows(self):
        selected_rows = set()
        for item in self.strategy_table.selectedItems(): selected_rows.add(item.row())
        return sorted(list(selected_rows))

    def _batch_update_default_account(self):
        try:
            selected_strategy_ids = []
            for row in range(self.strategy_table.rowCount()):
                checkbox_item = self.strategy_table.item(row, 0)
                if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                    strategy_id_item = self.strategy_table.item(row, 1)
                    if strategy_id_item: selected_strategy_ids.append(strategy_id_item.text())
            if not selected_strategy_ids: QMessageBox.warning(self, "提示", "请先选择要修改的策略"); return
            account_manager = None
            try:
                if self.service_container:
                    from core.trading.account_manager import AccountManager
                    account_manager = self.service_container.resolve(AccountManager)
            except Exception as e: logger.error(f"获取账号管理器失败: {e}")
            dialog = _BatchUpdateDefaultAccountDialog(self, strategy_ids=selected_strategy_ids, strategy_service=self.strategy_service, account_manager=account_manager)
            if dialog.exec_() == QDialog.Accepted:
                selected_account = dialog.get_selected_account()
                success_count = 0; failed_count = 0
                for strategy_id in selected_strategy_ids:
                    try:
                        strategy_config = self.strategy_service.get_strategy_config(strategy_id)
                        if strategy_config:
                            strategy_config.metadata['default_account_id'] = selected_account
                            if self.strategy_service.update_strategy_config(strategy_config): success_count += 1
                            else: failed_count += 1
                        else: failed_count += 1
                    except Exception as e: logger.error(f"更新策略 {strategy_id} 失败: {e}"); failed_count += 1
                self._load_strategies()
                if failed_count == 0: QMessageBox.information(self, "成功", f"成功更新 {success_count} 个策略的默认账号")
                else: QMessageBox.warning(self, "部分成功", f"成功更新 {success_count} 个策略，失败 {failed_count} 个策略")
        except Exception as e: logger.error(f"批量修改默认账号失败: {e}"); QMessageBox.critical(self, "错误", f"批量修改默认账号失败: {e}")

    # ===================== Backtest Operations =====================

    def _get_real_market_data(self, start_date: str, end_date: str, timeframe: TimeFrame, symbol: str = '000001') -> Optional[StandardMarketData]:
        try:
            from core.services.unified_data_manager import UnifiedDataManager
            data_manager = UnifiedDataManager()
            timeframe_map = {TimeFrame.DAY_1: 'D', TimeFrame.HOUR_1: '60', TimeFrame.MINUTE_30: '30',
                             TimeFrame.MINUTE_15: '15', TimeFrame.MINUTE_5: '5', TimeFrame.MINUTE_1: '1'}
            period = timeframe_map.get(timeframe, 'D')
            df = data_manager.get_kdata_from_source(stock_code=symbol, period=period, start_date=start_date, end_date=end_date, count=365)
            if df is None or df.empty: df = data_manager.get_kdata_from_source(stock_code='000001', period=period, count=365)
            if df is not None and not df.empty: return StandardMarketData.from_dataframe(df, symbol=symbol)
            return None
        except Exception as e: logger.error(f"获取真实市场数据失败: {e}"); return None

    def _run_backtest(self):
        try:
            strategy_id = self.backtest_strategy_combo.currentData()
            if not strategy_id: QMessageBox.warning(self, "警告", "请选择策略"); return
            start_date = self.backtest_start_date.date().toString("yyyy-MM-dd")
            end_date = self.backtest_end_date.date().toString("yyyy-MM-dd")
            initial_capital = self.backtest_initial_capital.value()
            commission_rate = self.backtest_commission_rate.value()
            timeframe = self.backtest_timeframe_combo.currentData()
            market_data = self._get_real_market_data(start_date, end_date, timeframe)
            if market_data is None: QMessageBox.warning(self, "警告", "无法获取历史数据，请检查数据源配置"); return
            context = StrategyContext(symbol='000001', timeframe=timeframe, start_date=start_date, end_date=end_date, initial_capital=initial_capital, commission_rate=commission_rate)
            self.backtest_progress_bar.setValue(0); self.backtest_status_label.setText("正在初始化回测..."); self.cancel_backtest_button.setEnabled(True); self.run_backtest_button.setEnabled(False)
            if self.strategy_service:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        task = asyncio.create_task(self._run_backtest_async(strategy_id, market_data, context))
                        self._async_tasks.add(task)
                        task.add_done_callback(lambda t: self._async_tasks.discard(t)); task.add_done_callback(lambda t: self._handle_async_task_error(t, "回测任务"))
                    else:
                        backtest_id = loop.run_until_complete(self.strategy_service.run_backtest(strategy_id, market_data, context))
                        if backtest_id: self.current_backtest_id = backtest_id; self.backtest_status_label.setText(f"回测已启动 (ID: {backtest_id})"); self._monitor_backtest_progress(backtest_id)
                        else: QMessageBox.warning(self, "警告", "回测启动失败"); self._reset_backtest_ui()
                except RuntimeError as e: logger.error(f"事件循环错误: {e}"); self._reset_backtest_ui()
            else: self._reset_backtest_ui()
        except Exception as e: logger.error(f"运行回测失败: {e}"); self._reset_backtest_ui()

    async def _run_backtest_async(self, strategy_id: str, market_data: StandardMarketData, context: StrategyContext):
        try:
            backtest_id = await self.strategy_service.run_backtest(strategy_id, market_data, context)
            if backtest_id: self.current_backtest_id = backtest_id; self.backtest_status_label.setText(f"回测已启动 (ID: {backtest_id})"); self._monitor_backtest_progress(backtest_id)
            else: self._reset_backtest_ui()
        except Exception as e: logger.error(f"异步回测失败: {e}"); self._reset_backtest_ui()

    def _handle_async_task_error(self, task, task_name: str = "异步任务"):
        try:
            if task.exception(): logger.error(f"{task_name}执行失败: {task.exception()}"); self._reset_backtest_ui()
        except Exception as e: logger.error(f"处理{task_name}错误失败: {e}")

    def _batch_backtest(self):
        try:
            selected_rows = self._get_selected_strategy_rows()
            if not selected_rows: QMessageBox.warning(self, "警告", "请先选择要回测的策略"); return
            start_date = self.backtest_start_date.date().toString("yyyy-MM-dd")
            end_date = self.backtest_end_date.date().toString("yyyy-MM-dd")
            initial_capital = self.backtest_initial_capital.value()
            commission_rate = self.backtest_commission_rate.value()
            timeframe = self.backtest_timeframe_combo.currentData()
            market_data = self._get_real_market_data(start_date, end_date, timeframe)
            if market_data is None: QMessageBox.warning(self, "警告", "无法获取历史数据"); return
            context = StrategyContext(symbol='000001', timeframe=timeframe, start_date=start_date, end_date=end_date, initial_capital=initial_capital, commission_rate=commission_rate)
            self.backtest_progress_bar.setValue(0); self.backtest_status_label.setText(f"正在启动 {len(selected_rows)} 个回测任务..."); self.cancel_backtest_button.setEnabled(True)
            backtest_ids = []
            if self.strategy_service:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        task = asyncio.create_task(self._run_batch_backtest_async(selected_rows, market_data, context))
                        self._async_tasks.add(task)
                        task.add_done_callback(lambda t: self._async_tasks.discard(t)); task.add_done_callback(lambda t: self._handle_async_task_error(t, "批量回测任务"))
                    else:
                        for row in selected_rows:
                            strategy_id_item = self.strategy_table.item(row, 1)
                            if strategy_id_item:
                                try:
                                    bid = loop.run_until_complete(self.strategy_service.run_backtest(strategy_id_item.text(), market_data, context))
                                    if bid: backtest_ids.append(bid)
                                except Exception as e: logger.error(f"启动回测失败: {strategy_id_item.text()}")
                        if backtest_ids: self.current_batch_backtest_ids = backtest_ids; self.backtest_status_label.setText(f"批量回测已启动 ({len(backtest_ids)} 个任务)"); self._monitor_batch_backtest_progress(backtest_ids)
                        else: self._reset_backtest_ui()
                except RuntimeError: self._reset_backtest_ui()
        except Exception as e: logger.error(f"批量回测失败: {e}"); self._reset_backtest_ui()

    async def _run_batch_backtest_async(self, selected_rows: List[int], market_data: StandardMarketData, context: StrategyContext):
        backtest_ids = []
        try:
            for row in selected_rows:
                item = self.strategy_table.item(row, 1)
                if item:
                    try: bid = await self.strategy_service.run_backtest(item.text(), market_data, context)
                    except Exception as e: logger.error(f"启动回测失败: {item.text()}")
                    if 'bid' in dir() and bid: backtest_ids.append(bid)
            if backtest_ids: self.current_batch_backtest_ids = backtest_ids; self.backtest_status_label.setText(f"批量回测已启动 ({len(backtest_ids)} 个任务)"); self._monitor_batch_backtest_progress(backtest_ids)
        except Exception as e: logger.error(f"异步批量回测失败: {e}")

    def _monitor_backtest_progress(self, backtest_id: str):
        try:
            if not hasattr(self, 'backtest_timer'): self.backtest_timer = QTimer(); self.backtest_timer.timeout.connect(self._check_backtest_status)
            self.current_backtest_id = backtest_id; self.backtest_start_time = time.time(); self.backtest_timer.start(1000)
        except Exception as e: logger.error(f"监控回测进度失败: {e}")

    def _check_backtest_status(self):
        try:
            if not hasattr(self, 'current_backtest_id') or not self.current_backtest_id: return
            if hasattr(self, 'backtest_start_time') and hasattr(self, 'backtest_timeout'):
                elapsed = time.time() - self.backtest_start_time
                if elapsed > self.backtest_timeout: self.backtest_status_label.setText("回测超时"); self._reset_backtest_ui(); self.backtest_timer.stop(); return
            if self.strategy_service:
                status_info = self.strategy_service.get_backtest_status(self.current_backtest_id)
                if status_info:
                    progress = status_info.get('progress', 0); self.backtest_progress_bar.setValue(int(progress * 100))
                    status = status_info.get('status', 'running')
                    if status == 'running':
                        elapsed = int(time.time() - self.backtest_start_time) if hasattr(self, 'backtest_start_time') else 0
                        self.backtest_status_label.setText(f"回测进行中... {int(progress * 100)}% (已运行{elapsed}秒)")
                    elif status == 'completed':
                        self.backtest_status_label.setText("回测完成"); self.backtest_progress_bar.setValue(100); self._reset_backtest_ui(); self._load_backtest_results(self.current_backtest_id); self.backtest_timer.stop()
                    elif status in ('error', 'failed'): self.backtest_status_label.setText("回测失败"); self._reset_backtest_ui(); self.backtest_timer.stop()
        except Exception as e: logger.error(f"检查回测状态失败: {e}")

    def _monitor_batch_backtest_progress(self, backtest_ids: List[str]):
        try:
            if not hasattr(self, 'batch_backtest_timer'): self.batch_backtest_timer = QTimer(); self.batch_backtest_timer.timeout.connect(self._check_batch_backtest_status)
            self.current_batch_backtest_ids = backtest_ids; self.batch_backtest_timer.start(1000)
        except Exception as e: logger.error(f"监控批量回测进度失败: {e}")

    def _check_batch_backtest_status(self):
        try:
            if not hasattr(self, 'current_batch_backtest_ids') or not self.current_batch_backtest_ids: return
            if self.strategy_service:
                status_list = self.strategy_service.get_batch_backtest_status(self.current_batch_backtest_ids)
                if status_list:
                    total_progress = sum(s.get('progress', 0) for s in status_list) / len(status_list); self.backtest_progress_bar.setValue(int(total_progress * 100))
                    completed = sum(1 for s in status_list if s.get('status') == 'completed')
                    running = sum(1 for s in status_list if s.get('status') == 'running')
                    errors = sum(1 for s in status_list if s.get('status') in ('failed', 'cancelled'))
                    self.backtest_status_label.setText(f"批量回测进度: {completed}/{len(status_list)} 完成, {running} 运行中, {errors} 错误")
                    if completed + errors == len(status_list): self._reset_backtest_ui(); self.batch_backtest_timer.stop()
                    QMessageBox.information(self, "完成", f"批量回测完成！\n成功: {completed}, 失败: {errors}")
        except Exception as e: logger.error(f"检查批量回测状态失败: {e}")

    def _load_backtest_results(self, backtest_id: str):
        try:
            if self.strategy_service:
                result = self.strategy_service.get_backtest_result(backtest_id)
                if result:
                    results = {'total_return': result.total_return, 'sharpe_ratio': result.sharpe_ratio,
                               'max_drawdown': result.max_drawdown, 'win_rate': result.win_rate,
                               'equity_curve': self._convert_equity_curve(result), 'drawdown_curve': self._convert_drawdown_curve(result),
                               'trades': self._convert_trades(result)}
                    self._update_backtest_metrics(results); self._update_backtest_charts(results)
        except Exception as e: logger.error(f"加载回测结果失败: {e}")

    def _convert_equity_curve(self, result) -> List[Dict[str, Any]]:
        try:
            equity_curve = []
            if hasattr(result, 'equity_curve') and result.equity_curve is not None:
                base_date = datetime(2024, 1, 1)
                for i, value in enumerate(result.equity_curve): equity_curve.append({'date': (base_date + timedelta(days=i)).strftime('%Y-%m-%d'), 'value': value})
            return equity_curve
        except Exception as e: logger.error(f"转换权益曲线数据失败: {e}"); return []

    def _convert_drawdown_curve(self, result) -> List[Dict[str, Any]]:
        try:
            drawdown_curve = []
            if hasattr(result, 'drawdown_curve') and result.drawdown_curve is not None:
                base_date = datetime(2024, 1, 1)
                for i, value in enumerate(result.drawdown_curve): drawdown_curve.append({'date': (base_date + timedelta(days=i)).strftime('%Y-%m-%d'), 'value': value})
            return drawdown_curve
        except Exception as e: logger.error(f"转换回撤曲线数据失败: {e}"); return []

    def _convert_trades(self, result) -> List[Dict[str, Any]]:
        try:
            trades = []
            if hasattr(result, 'trades') and result.trades is not None:
                for trade in result.trades: trades.append({'date': trade.entry_time.strftime('%Y-%m-%d') if hasattr(trade, 'entry_time') else '2024-01-01', 'pnl': trade.pnl if hasattr(trade, 'pnl') else 0})
            return trades
        except Exception as e: logger.error(f"转换交易记录数据失败: {e}"); return []

    def _update_backtest_metrics(self, results: Dict[str, Any]):
        try:
            self._update_metric_card(self.total_return_card, f"{results.get('total_return', 0):.2f}%")
            self._update_metric_card(self.sharpe_ratio_card, f"{results.get('sharpe_ratio', 0):.2f}")
            self._update_metric_card(self.max_drawdown_card, f"{results.get('max_drawdown', 0):.2f}%")
            self._update_metric_card(self.win_rate_card, f"{results.get('win_rate', 0):.2f}%")
        except Exception as e: logger.error(f"更新回测指标失败: {e}")

    def _update_metric_card(self, card: QWidget, value: str):
        try:
            value_label = card.findChild(QLabel, "value_label")
            if value_label: value_label.setText(value)
        except Exception as e: logger.error(f"更新指标卡片失败: {e}")

    def _update_backtest_charts(self, results: Dict[str, Any]):
        try:
            equity_curve = results.get('equity_curve', []); drawdown_curve = results.get('drawdown_curve', []); trades = results.get('trades', [])
            if equity_curve and hasattr(self, 'equity_chart'): self._update_equity_chart(equity_curve)
            if drawdown_curve and hasattr(self, 'drawdown_chart'): self._update_drawdown_chart(drawdown_curve)
            if trades and hasattr(self, 'trades_chart'): self._update_trades_chart(trades)
        except Exception as e: logger.error(f"更新回测图表失败: {e}")

    def _update_equity_chart(self, equity_curve: List[Dict[str, Any]]):
        try:
            if not MATPLOTLIB_AVAILABLE: return
            ax = self.equity_chart.figure.axes[0]; ax.clear()
            dates = pd.to_datetime([d['date'] for d in equity_curve]); values = [d['value'] for d in equity_curve]
            ax.plot(dates, values, color=FINANCIAL_COLORS['profit'], linewidth=1, label='策略收益')
            ax.axhline(y=values[0], color=FINANCIAL_COLORS['primary'], linestyle='--', alpha=0.5, label='基准线')
            ax.set_title("策略权益曲线", fontsize=14, fontweight='bold'); ax.set_xlabel("日期", fontsize=12); ax.set_ylabel("累计收益率", fontsize=12)
            ax.grid(True, alpha=0.3); ax.legend(); self.equity_chart.draw()
        except Exception as e: logger.error(f"更新权益曲线图失败: {e}")

    def _update_drawdown_chart(self, drawdown_curve: List[Dict[str, Any]]):
        try:
            if not MATPLOTLIB_AVAILABLE: return
            ax = self.drawdown_chart.figure.axes[0]; ax.clear()
            dates = pd.to_datetime([d['date'] for d in drawdown_curve]); values = [d['value'] for d in drawdown_curve]
            ax.fill_between(dates, values, 0, color=FINANCIAL_COLORS['loss'], alpha=0.3)
            ax.plot(dates, values, color=FINANCIAL_COLORS['loss'], linewidth=1, label='回撤')
            ax.set_title("回撤分析", fontsize=14, fontweight='bold'); ax.set_xlabel("日期", fontsize=12); ax.set_ylabel("回撤率 (%)", fontsize=12)
            ax.grid(True, alpha=0.3); ax.legend(); self.drawdown_chart.draw()
        except Exception as e: logger.error(f"更新回撤分析图失败: {e}")

    def _update_trades_chart(self, trades: List[Dict[str, Any]]):
        try:
            if not MATPLOTLIB_AVAILABLE: return
            ax = self.trades_chart.figure.axes[0]; ax.clear()
            dates = pd.to_datetime([t['date'] for t in trades]); pnl = [t['pnl'] for t in trades]
            colors = [FINANCIAL_COLORS['profit'] if p >= 0 else FINANCIAL_COLORS['loss'] for p in pnl]
            ax.bar(dates, pnl, color=colors, alpha=0.7)
            ax.set_title("交易记录", fontsize=14, fontweight='bold'); ax.set_xlabel("日期", fontsize=12); ax.set_ylabel("盈亏", fontsize=12)
            ax.grid(True, alpha=0.3); ax.axhline(y=0, color=FINANCIAL_COLORS['primary'], linestyle='-', alpha=0.5)
            self.trades_chart.draw()
        except Exception as e: logger.error(f"更新交易记录图失败: {e}")

    def _cancel_backtest(self):
        try:
            if hasattr(self, 'current_backtest_id') and self.current_backtest_id:
                if self.strategy_service:
                    if self.strategy_service.cancel_backtest(self.current_backtest_id):
                        self.backtest_status_label.setText("回测已取消"); self._reset_backtest_ui()
                        if hasattr(self, 'backtest_timer'): self.backtest_timer.stop()
                        QMessageBox.information(self, "成功", "回测已取消")
                    else: QMessageBox.warning(self, "警告", "取消回测失败")
            elif hasattr(self, 'current_batch_backtest_ids') and self.current_batch_backtest_ids:
                if self.strategy_service:
                    if self.strategy_service.cancel_batch_backtest(self.current_batch_backtest_ids):
                        self.backtest_status_label.setText("批量回测已取消"); self._reset_backtest_ui()
                        if hasattr(self, 'batch_backtest_timer'): self.batch_backtest_timer.stop()
                        QMessageBox.information(self, "成功", "批量回测已取消")
                    else: QMessageBox.warning(self, "警告", "取消批量回测失败")
            else: QMessageBox.warning(self, "警告", "没有正在运行的回测任务")
        except Exception as e: logger.error(f"取消回测失败: {e}")

    def _reset_backtest_ui(self):
        if hasattr(self, 'run_backtest_button'): self.run_backtest_button.setEnabled(True)
        if hasattr(self, 'cancel_backtest_button'): self.cancel_backtest_button.setEnabled(False)

    # ===================== Optimization Operations =====================

    def _start_optimization(self):
        try:
            strategy_id = self.optimization_strategy_combo.currentData() if hasattr(self, 'optimization_strategy_combo') else None
            if not strategy_id:
                strategy_id = self.opt_strategy_combo.currentData() if hasattr(self, 'opt_strategy_combo') else None
            if not strategy_id: QMessageBox.warning(self, "警告", "请选择策略"); return
            algorithm = self.opt_algorithm_combo.currentText(); target_metric = self.opt_target_metric_combo.currentText()
            max_iterations = self.opt_max_iterations.value(); timeframe = self.opt_timeframe_combo.currentData()
            param_ranges = self._get_optimization_param_ranges()
            if not param_ranges: QMessageBox.warning(self, "警告", "请至少配置一个参数范围"); return
            market_data = self._get_real_market_data('2023-01-01', '2024-01-01', timeframe)
            if market_data is None: QMessageBox.warning(self, "警告", "无法获取历史数据"); return
            context = StrategyContext(symbol='000001', timeframe=timeframe, start_date='2023-01-01', end_date='2024-01-01', initial_capital=100000, commission_rate=0.0003)
            optimization_params = {'algorithm': algorithm, 'target_metric': target_metric, 'max_iterations': max_iterations, 'param_ranges': param_ranges}
            self.opt_progress_bar.setValue(0); self.opt_iteration_label.setText(f"当前迭代：0/{max_iterations}")
            self.opt_best_value_label.setText("最佳值：0.0000"); self.cancel_optimization_button.setEnabled(True); self.start_optimization_button.setEnabled(False)
            if self.strategy_service:
                loop = asyncio.get_event_loop()
                optimization_id = loop.run_until_complete(self.strategy_service.run_optimization(strategy_id, optimization_params, market_data, context))
                if optimization_id: self.current_optimization_id = optimization_id; self.opt_iteration_label.setText(f"优化已启动 (ID: {optimization_id})"); self._monitor_optimization_progress(optimization_id)
                else: self._reset_optimization_ui()
            else: self._reset_optimization_ui()
        except Exception as e: logger.error(f"启动参数优化失败: {e}"); self._reset_optimization_ui()

    def _get_optimization_param_ranges(self) -> List[Dict[str, Any]]:
        param_ranges = []
        for row in range(self.opt_param_table.rowCount()):
            name_item = self.opt_param_table.item(row, 0); min_item = self.opt_param_table.item(row, 1)
            max_item = self.opt_param_table.item(row, 2); step_item = self.opt_param_table.item(row, 3); type_item = self.opt_param_table.item(row, 4)
            if name_item and min_item and max_item and step_item and type_item:
                param_ranges.append({'name': name_item.text(), 'min': float(min_item.text()), 'max': float(max_item.text()), 'step': float(step_item.text()), 'type': type_item.text()})
        return param_ranges

    def _monitor_optimization_progress(self, optimization_id: str):
        try:
            if not hasattr(self, 'optimization_timer'): self.optimization_timer = QTimer(); self.optimization_timer.timeout.connect(self._check_optimization_status)
            self.current_optimization_id = optimization_id; self.optimization_start_time = time.time(); self.optimization_timer.start(1000)
        except Exception as e: logger.error(f"监控优化进度失败: {e}")

    def _check_optimization_status(self):
        try:
            if not hasattr(self, 'current_optimization_id') or not self.current_optimization_id: return
            if hasattr(self, 'optimization_start_time') and hasattr(self, 'optimization_timeout'):
                elapsed = time.time() - self.optimization_start_time
                if elapsed > self.optimization_timeout: self.opt_iteration_label.setText("优化超时"); self._reset_optimization_ui(); self.optimization_timer.stop(); return
            if self.strategy_service:
                status_info = self.strategy_service.get_optimization_status(self.current_optimization_id)
                if status_info:
                    progress = status_info.get('progress', 0); self.opt_progress_bar.setValue(int(progress * 100))
                    iterations = status_info.get('iterations_completed', 0); elapsed = int(time.time() - self.optimization_start_time) if hasattr(self, 'optimization_start_time') else 0
                    self.opt_iteration_label.setText(f"已完成迭代：{iterations} (已运行{elapsed}秒)")
                    best = status_info.get('best_performance', 0)
                    if best: self.opt_best_value_label.setText(f"最佳值：{best:.4f}")
                    status = status_info.get('status', 'running')
                    if status == 'completed': self.opt_iteration_label.setText("优化完成"); self.opt_progress_bar.setValue(100); self._reset_optimization_ui(); self._load_optimization_results(self.current_optimization_id); self.optimization_timer.stop()
                    elif status in ('error', 'failed'): self.opt_iteration_label.setText("优化失败"); self._reset_optimization_ui(); self.optimization_timer.stop()
        except Exception as e: logger.error(f"检查优化状态失败: {e}")

    def _load_optimization_results(self, optimization_id: str):
        try:
            if self.strategy_service:
                result = self.strategy_service.get_optimization_result(optimization_id)
                if result: self._update_best_params_table({'best_params': result.get('best_parameters', {}), 'current_params': {}, 'strategy_id': self.current_optimization_id.split('_')[0]})
        except Exception as e: logger.error(f"加载优化结果失败: {e}")

    def _update_best_params_table(self, results: Dict[str, Any]):
        try:
            best_params = results.get('best_params', {}); current_params = results.get('current_params', {})
            self.best_param_table.setRowCount(len(best_params))
            for row, (param_name, best_value) in enumerate(best_params.items()):
                current_value = current_params.get(param_name, 'N/A'); improvement = "N/A"
                if isinstance(best_value, (int, float)) and isinstance(current_value, (int, float)) and current_value != 0:
                    improvement_pct = ((best_value - current_value) / abs(current_value)) * 100; improvement = f"{improvement_pct:+.1f}%"
                self.best_param_table.setItem(row, 0, QTableWidgetItem(param_name)); self.best_param_table.setItem(row, 1, QTableWidgetItem(str(best_value)))
                self.best_param_table.setItem(row, 2, QTableWidgetItem(str(current_value)))
                improvement_item = QTableWidgetItem(improvement)
                if improvement.startswith('+'): improvement_item.setForeground(QColor(FINANCIAL_COLORS['profit']))
                elif improvement.startswith('-'): improvement_item.setForeground(QColor(FINANCIAL_COLORS['loss']))
                self.best_param_table.setItem(row, 3, improvement_item)
        except Exception as e: logger.error(f"更新最佳参数表格失败: {e}")

    def _add_optimization_param(self):
        try:
            dialog = _OptimizationParamDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                param_config = dialog.get_param_config(); row = self.opt_param_table.rowCount(); self.opt_param_table.insertRow(row)
                self.opt_param_table.setItem(row, 0, QTableWidgetItem(param_config['name'])); self.opt_param_table.setItem(row, 1, QTableWidgetItem(str(param_config['min'])))
                self.opt_param_table.setItem(row, 2, QTableWidgetItem(str(param_config['max']))); self.opt_param_table.setItem(row, 3, QTableWidgetItem(str(param_config['step'])))
                self.opt_param_table.setItem(row, 4, QTableWidgetItem(param_config['type']))
        except Exception as e: logger.error(f"添加优化参数失败: {e}")

    def _import_optimization_ranges(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, "导入优化范围", "", "JSON文件 (*.json);;所有文件 (*.*)")
            if not file_path: return
            with open(file_path, 'r', encoding='utf-8') as f: param_ranges = json.load(f)
            self.opt_param_table.setRowCount(0)
            for param_range in param_ranges:
                row = self.opt_param_table.rowCount(); self.opt_param_table.insertRow(row)
                self.opt_param_table.setItem(row, 0, QTableWidgetItem(param_range.get('name', ''))); self.opt_param_table.setItem(row, 1, QTableWidgetItem(str(param_range.get('min', ''))))
                self.opt_param_table.setItem(row, 2, QTableWidgetItem(str(param_range.get('max', '')))); self.opt_param_table.setItem(row, 3, QTableWidgetItem(str(param_range.get('step', ''))))
                self.opt_param_table.setItem(row, 4, QTableWidgetItem(param_range.get('type', 'float')))
        except Exception as e: logger.error(f"导入优化范围失败: {e}")

    def _export_optimization_ranges(self):
        try:
            param_ranges = self._get_optimization_param_ranges()
            if not param_ranges: QMessageBox.warning(self, "警告", "没有可导出的参数范围"); return
            file_path, _ = QFileDialog.getSaveFileName(self, "导出优化范围", "optimization_ranges.json", "JSON文件 (*.json);;所有文件 (*.*)")
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f: json.dump(param_ranges, f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "成功", f"优化范围已导出到: {file_path}")
        except Exception as e: logger.error(f"导出优化范围失败: {e}")

    def _cancel_optimization(self):
        try:
            if hasattr(self, 'current_optimization_id') and self.current_optimization_id:
                if self.strategy_service:
                    if self.strategy_service.cancel_optimization(self.current_optimization_id):
                        self.opt_iteration_label.setText("优化已取消"); self._reset_optimization_ui()
                        if hasattr(self, 'optimization_timer'): self.optimization_timer.stop()
                        QMessageBox.information(self, "成功", "优化已取消")
                    else: QMessageBox.warning(self, "警告", "取消优化失败")
            else: QMessageBox.warning(self, "警告", "没有正在运行的优化任务")
        except Exception as e: logger.error(f"取消优化失败: {e}")

    def _reset_optimization_ui(self):
        if hasattr(self, 'start_optimization_button'): self.start_optimization_button.setEnabled(True)
        if hasattr(self, 'cancel_optimization_button'): self.cancel_optimization_button.setEnabled(False)

    def _apply_best_parameters(self):
        try:
            if not hasattr(self, 'best_param_table'): return
            best_params = {}
            for row in range(self.best_param_table.rowCount()):
                name_item = self.best_param_table.item(row, 0); value_item = self.best_param_table.item(row, 1)
                if name_item and value_item:
                    name = name_item.text(); value = value_item.text()
                    try: best_params[name] = float(value)
                    except ValueError: best_params[name] = value
            if best_params:
                QMessageBox.information(self, "应用参数", f"最佳参数已应用:\n{json.dumps(best_params, indent=2, ensure_ascii=False)}")
        except Exception as e: logger.error(f"应用最佳参数失败: {e}")

    def _save_optimization_config(self):
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, "保存优化配置", "optimization_config.json", "JSON文件 (*.json);;所有文件 (*.*)")
            if file_path:
                config = {'algorithm': self.opt_algorithm_combo.currentText(), 'target_metric': self.opt_target_metric_combo.currentText(),
                          'max_iterations': self.opt_max_iterations.value(), 'param_ranges': self._get_optimization_param_ranges()}
                with open(file_path, 'w', encoding='utf-8') as f: json.dump(config, f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "成功", f"优化配置已保存: {file_path}")
        except Exception as e: logger.error(f"保存优化配置失败: {e}")

    def _parameter_scan(self):
        QMessageBox.information(self, "提示", "参数扫描功能需要策略引擎支持，当前版本暂不可用")

    def _sensitivity_analysis(self):
        QMessageBox.information(self, "提示", "敏感性分析功能需要策略引擎支持，当前版本暂不可用")

    # ===================== Performance Operations =====================

    def _load_performance_data(self):
        QMessageBox.information(self, "提示", "性能数据加载需要回测结果支持")

    def _compare_strategies(self):
        try:
            strategy_id1 = self.compare_strategy_combo1.currentData(); strategy_id2 = self.compare_strategy_combo2.currentData()
            if not strategy_id1 or not strategy_id2: QMessageBox.warning(self, "警告", "请选择两个策略进行对比"); return
            dialog = _StrategyCompareDialog(self, self.strategy_service)
            dialog.exec_()
        except Exception as e: logger.error(f"策略对比失败: {e}")

    def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'backtest_timer') and self.backtest_timer: self.backtest_timer.stop()
            if hasattr(self, 'batch_backtest_timer') and self.batch_backtest_timer: self.batch_backtest_timer.stop()
            if hasattr(self, 'optimization_timer') and self.optimization_timer: self.optimization_timer.stop()
            try: event_bus = get_event_bus()
            except Exception: event_bus = None
            if event_bus and self._strategy_event_handler:
                try:
                    event_bus.unsubscribe(StrategyStartedEvent, self._strategy_event_handler)
                    event_bus.unsubscribe(StrategyStoppedEvent, self._strategy_event_handler)
                    event_bus.unsubscribe(SignalGeneratedEvent, self._strategy_event_handler)
                    event_bus.unsubscribe(StrategyErrorEvent, self._strategy_event_handler)
                except Exception as e: logger.warning(f"取消事件订阅失败: {e}")
            logger.info("StrategyManagerDialog资源已清理")
        except Exception as e: logger.error(f"清理资源失败: {e}")

    def closeEvent(self, event):
        """关闭事件"""
        self.cleanup()
        super().closeEvent(event)
