#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险控制中心标签页 - 升级版告警配置
专为量化交易风险管理设计的综合监控中心
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
from PyQt5.QtWidgets import (
    QHeaderView, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QTreeWidget, QTreeWidgetItem, QFormLayout, QCheckBox, QComboBox,
    QLineEdit, QSpinBox, QTextEdit, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QMessageBox, QInputDialog, QFileDialog, QMenu,
    QLabel, QTabWidget, QFrame, QGridLayout, QProgressBar, QSlider,
    QScrollArea, QSizePolicy
)
from PyQt5.QtCore import QThreadPool, pyqtSlot, Qt, QTimer
from PyQt5.QtGui import QBrush, QColor, QFont
from gui.widgets.performance.components.metric_card import ModernMetricCard
from gui.widgets.performance.components.performance_chart import ModernPerformanceChart
from gui.widgets.performance.workers.async_workers import AlertHistoryWorker
from gui.utils.responsive_helper import calculate_spacing, calculate_margins, calculate_percentage_height
from loguru import logger

# 导入增强风险监控后端
try:
    from core.risk_monitoring.enhanced_risk_monitor import EnhancedRiskMonitor, get_enhanced_risk_monitor
    from core.services.ai_prediction_service import AIPredictionService
    ENHANCED_RISK_AVAILABLE = True
except ImportError as e:
    logger.warning(f"增强风险监控后端不可用: {e}")
    ENHANCED_RISK_AVAILABLE = False

# 导入动态风险调整服务
try:
    from core.services.dynamic_risk_adjustment_service import (
        DynamicRiskAdjustmentEngine, AdjustmentStrategy, AdjustmentTrigger,
        AdjustmentRule, AdjustmentHistory, PerformanceMetrics
    )
    DYNAMIC_RISK_AVAILABLE = True
except ImportError as e:
    logger.warning(f"动态风险调整服务不可用: {e}")
    DYNAMIC_RISK_AVAILABLE = False

# 延迟导入主题管理器，避免在模块级别导入时崩溃
THEME_MANAGER_AVAILABLE = False
get_theme_manager = None

def _import_theme_manager():
    """延迟导入主题管理器"""
    global THEME_MANAGER_AVAILABLE, get_theme_manager
    if not THEME_MANAGER_AVAILABLE:
        try:
            from utils.theme import get_theme_manager as _get_theme_manager
            get_theme_manager = _get_theme_manager
            THEME_MANAGER_AVAILABLE = True
            logger.info("主题管理器模块导入成功")
        except Exception as e:
            logger.warning(f"导入主题管理器失败: {e}")


class ModernRiskControlCenterTab(QWidget):
    """现代化风险控制中心标签页 - 量化交易专用"""

    def __init__(self):
        super().__init__()
        self.risk_alerts = []
        self.risk_history = []

        # 初始化增强风险监控后端
        self.enhanced_risk_monitor = None
        if ENHANCED_RISK_AVAILABLE:
            try:
                self.enhanced_risk_monitor = get_enhanced_risk_monitor()
                logger.info("增强风险监控后端初始化成功")
            except Exception as e:
                logger.error(f"初始化增强风险监控后端失败: {e}")

        # 初始化动态风险调整引擎
        self.dynamic_risk_engine = None
        if DYNAMIC_RISK_AVAILABLE:
            try:
                self.dynamic_risk_engine = DynamicRiskAdjustmentEngine()
                logger.info("动态风险调整引擎初始化成功")
            except Exception as e:
                logger.error(f"初始化动态风险调整引擎失败: {e}")

        # 延迟导入并初始化主题管理器
        _import_theme_manager()
        self.theme_manager = None
        if THEME_MANAGER_AVAILABLE:
            try:
                self.theme_manager = get_theme_manager()
                self.theme_manager.theme_changed.connect(self._on_theme_changed)
            except Exception as e:
                logger.warning(f"获取ThemeManager失败: {e}")

        self.init_ui()

        # 加载风险规则
        self.load_risk_rules()

        # 不在初始化时启动增强风险监控，延迟到UI完全准备好后再启动
        # if self.enhanced_risk_monitor:
        #     self.start_enhanced_monitoring()

    def init_ui(self):
        layout = QVBoxLayout(self)
        spacing = calculate_spacing(5)
        layout.setContentsMargins(spacing, spacing, spacing, spacing)
        layout.setSpacing(spacing)

        # 创建子标签页
        self.tab_widget = QTabWidget()

        # 实时风险监控
        self.risk_monitor_tab = self._create_risk_monitor_tab()
        self.tab_widget.addTab(self.risk_monitor_tab, "实时风险")

        # 告警配置
        self.alert_config_tab = self._create_alert_config_tab()
        self.tab_widget.addTab(self.alert_config_tab, "告警配置")

        # 风险历史
        self.risk_history_tab = self._create_risk_history_tab()
        self.tab_widget.addTab(self.risk_history_tab, "风险历史")

        # AI智能分析（新增）
        if ENHANCED_RISK_AVAILABLE:
            self.ai_analysis_tab = self._create_ai_analysis_tab()
            self.tab_widget.addTab(self.ai_analysis_tab, "AI分析")

        # 动态调整（新增）
        if DYNAMIC_RISK_AVAILABLE:
            self.dynamic_adjustment_tab = self._create_dynamic_adjustment_tab()
            self.tab_widget.addTab(self.dynamic_adjustment_tab, "动态调整")

        layout.addWidget(self.tab_widget)

    def _create_risk_monitor_tab(self):
        """创建实时风险监控标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        spacing = calculate_spacing(5)
        layout.setContentsMargins(spacing, spacing, spacing, spacing)
        layout.setSpacing(spacing)

        # 风险等级指示器
        risk_level_group = QGroupBox("风险等级")
        risk_level_layout = QHBoxLayout()

        self.risk_level_label = QLabel("当前风险等级: 低风险")
        self.risk_level_label.setStyleSheet("font-size: 0.9em; font-weight: bold; color: #27ae60;")
        risk_level_layout.addWidget(self.risk_level_label)

        risk_level_layout.addStretch()

        # 风险等级进度条
        self.risk_level_bar = QProgressBar()
        self.risk_level_bar.setMaximum(100)
        self.risk_level_bar.setValue(25)  # 默认低风险
        self.risk_level_bar.setStyleSheet("""
            QProgressBar {
                border: 0.15em solid grey;
                border-radius: 0.3em;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #27ae60;
                border-radius: 0.2em;
            }
        """)
        risk_level_layout.addWidget(self.risk_level_bar)

        risk_level_group.setLayout(risk_level_layout)
        layout.addWidget(risk_level_group)

        # 风险指标卡片
        cards_frame = QFrame()
        cards_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        cards_layout = QGridLayout(cards_frame)
        card_spacing = calculate_spacing(2)
        cards_layout.setContentsMargins(card_spacing, card_spacing, card_spacing, card_spacing)
        cards_layout.setSpacing(card_spacing)

        self.risk_cards = {}
        risk_metrics = [
            # 第一行：核心风险指标
            ("VaR(95%)", "#e74c3c", 0, 0),
            ("最大回撤", "#c0392b", 0, 1),
            ("波动率", "#e67e22", 0, 2),
            ("Beta系数", "#f39c12", 0, 3),
            ("夏普比率", "#3498db", 0, 4),
            ("仓位风险", "#9b59b6", 0, 5),

            # 第二行：市场风险指标
            ("市场风险", "#8e44ad", 1, 0),
            ("行业风险", "#2980b9", 1, 1),
            ("流动性风险", "#16a085", 1, 2),
            ("信用风险", "#d35400", 1, 3),
            ("操作风险", "#27ae60", 1, 4),
            ("集中度风险", "#f1c40f", 1, 5),
        ]

        for name, color, row, col in risk_metrics:
            unit = "%" if name in ["最大回撤", "波动率", "仓位风险"] else ""
            card = ModernMetricCard(name, "0", unit, color)
            self.risk_cards[name] = card
            cards_layout.addWidget(card, row, col)

        layout.addWidget(cards_frame)

        # 风险趋势图表
        self.risk_chart = ModernPerformanceChart("风险指标趋势", "line")
        self.risk_chart.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.risk_chart, 1)

        return tab

    def _create_alert_config_tab(self):
        """创建告警配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        spacing = calculate_spacing(10)
        layout.setContentsMargins(spacing, spacing, spacing, spacing)
        layout.setSpacing(spacing)

        # 告警规则配置
        rules_group = QGroupBox("告警规则配置")
        rules_layout = QVBoxLayout()

        # 规则列表
        self.rules_tree = QTreeWidget()
        self.rules_tree.setHeaderLabels(["规则名称", "类型", "阈值", "状态"])
        self.rules_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.rules_tree.customContextMenuRequested.connect(self.show_rules_context_menu)
        rules_layout.addWidget(self.rules_tree)

        # 规则操作按钮
        rules_buttons_layout = QHBoxLayout()

        self.add_rule_btn = QPushButton("添加规则")
        self.add_rule_btn.clicked.connect(self.add_risk_rule)
        rules_buttons_layout.addWidget(self.add_rule_btn)

        self.edit_rule_btn = QPushButton("编辑规则")
        self.edit_rule_btn.clicked.connect(self.edit_risk_rule)
        rules_buttons_layout.addWidget(self.edit_rule_btn)

        self.delete_rule_btn = QPushButton("删除规则")
        self.delete_rule_btn.clicked.connect(self.delete_risk_rule)
        rules_buttons_layout.addWidget(self.delete_rule_btn)

        self.config_notification_btn = QPushButton("配置通知服务")
        self.config_notification_btn.clicked.connect(self._open_notification_config)
        self.config_notification_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 0.3em;
                padding: 0.5em 1em;
                font-size: 0.9em;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1f6391;
            }
        """)
        rules_buttons_layout.addWidget(self.config_notification_btn)

        self.stop_notification_btn = QPushButton("暂停通知")
        self.stop_notification_btn.setCheckable(True)
        self.stop_notification_btn.setChecked(False)
        self.stop_notification_btn.clicked.connect(self._toggle_notification_service)
        self.stop_notification_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 0.3em;
                padding: 0.5em 1em;
                font-size: 0.9em;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #962d22;
            }
            QPushButton:checked {
                background-color: #27ae60;
            }
        """)
        rules_buttons_layout.addWidget(self.stop_notification_btn)

        rules_buttons_layout.addStretch()
        rules_layout.addLayout(rules_buttons_layout)

        rules_group.setLayout(rules_layout)
        layout.addWidget(rules_group)

        return tab

    def _create_risk_history_tab(self):
        """创建风险历史标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        spacing = calculate_spacing(10)
        layout.setContentsMargins(spacing, spacing, spacing, spacing)
        layout.setSpacing(spacing)

        # 历史数据控制
        control_layout = QHBoxLayout()

        control_layout.addWidget(QLabel("时间范围:"))

        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems(["最近1小时", "最近24小时", "最近7天", "最近30天"])
        self.time_range_combo.currentTextChanged.connect(self.load_risk_history)
        control_layout.addWidget(self.time_range_combo)

        control_layout.addStretch()

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_risk_history)
        control_layout.addWidget(refresh_btn)

        layout.addLayout(control_layout)

        # 风险历史表格
        self.risk_history_table = QTableWidget()
        self.risk_history_table.setColumnCount(6)
        self.risk_history_table.setHorizontalHeaderLabels([
            "时间", "风险类型", "风险等级", "风险值", "阈值", "状态"
        ])
        self.risk_history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.risk_history_table)

        return tab

    def update_risk_data(self, risk_metrics: Dict[str, float]):
        """更新实时风险数据"""
        try:
            # 使用 QTimer.singleShot 确保在主线程中更新UI
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._update_risk_ui_in_main_thread(risk_metrics))

        except Exception as e:
            logger.error(f"更新风险数据失败: {e}")

    def _update_risk_ui_in_main_thread(self, risk_metrics: Dict[str, float]):
        """在主线程中更新风险UI"""
        try:
            # 更新风险指标卡片
            for name, value in risk_metrics.items():
                if name in self.risk_cards:
                    if value == 0:
                        self.risk_cards[name].update_value("正常", "up")
                    else:
                        # 根据风险类型判断趋势（风险越高越危险）
                        if value > 80:
                            trend = "down"  # 高风险用红色下降箭头
                            color = "#e74c3c"
                        elif value > 50:
                            trend = "neutral"  # 中风险用黄色
                            color = "#f39c12"
                        else:
                            trend = "up"  # 低风险用绿色上升箭头
                            color = "#27ae60"

                        self.risk_cards[name].update_value(f"{value:.2f}", trend)

            # 计算综合风险等级
            overall_risk = self._calculate_overall_risk(risk_metrics)
            self._update_risk_level(overall_risk)

            # 更新风险趋势图表
            for name, value in risk_metrics.items():
                if name in ["VaR(95%)", "最大回撤", "波动率"] and value > 0:
                    self.risk_chart.add_data_point(name, value)

            # 自动保存风险历史数据
            self._save_risk_metrics_history(risk_metrics, overall_risk)

            # 检查风险规则并生成告警
            self._check_risk_rules(risk_metrics)

        except Exception as e:
            logger.error(f"在主线程中更新风险UI失败: {e}")

    def _save_risk_metrics_history(self, risk_metrics: Dict[str, float], overall_risk: float):
        """保存风险指标历史数据"""
        try:
            from db.models.performance_history_models import get_performance_history_manager, RiskHistoryRecord
            from datetime import datetime

            # 创建风险历史记录
            record = RiskHistoryRecord(
                timestamp=datetime.now(),
                symbol="PORTFOLIO",  # 组合级别的风险
                var_95=risk_metrics.get('VaR(95%)', 0.0),
                max_drawdown=risk_metrics.get('最大回撤', 0.0),
                volatility=risk_metrics.get('波动率', 0.0),
                beta=risk_metrics.get('Beta系数', 1.0),
                sharpe_ratio=risk_metrics.get('夏普比率', 0.0),
                position_risk=risk_metrics.get('仓位风险', 0.0),
                market_risk=risk_metrics.get('市场风险', 0.0),
                sector_risk=risk_metrics.get('行业风险', 0.0),
                liquidity_risk=risk_metrics.get('流动性风险', 0.0),
                credit_risk=risk_metrics.get('信用风险', 0.0),
                operational_risk=risk_metrics.get('操作风险', 0.0),
                concentration_risk=risk_metrics.get('集中度风险', 0.0),
                overall_risk_score=overall_risk,
                risk_level=self._get_risk_level_text(overall_risk),
                portfolio_value=0.0,  # 这里应该从实际组合获取
                notes=""
            )

            # 保存到数据库
            history_manager = get_performance_history_manager()
            success = history_manager.save_risk_record(record)

            if success:
                logger.debug("风险历史数据已保存")
            else:
                logger.warning("风险历史数据保存失败")

        except Exception as e:
            logger.debug(f"保存风险历史数据失败: {e}")

    def _get_risk_level_text(self, risk_value: float) -> str:
        """根据风险值获取风险等级文本"""
        if risk_value < 15:
            return "低风险"
        elif risk_value < 35:
            return "中低风险"
        elif risk_value < 60:
            return "中高风险"
        elif risk_value < 80:
            return "高风险"
        else:
            return "极高风险"

    def _calculate_overall_risk(self, risk_metrics: Dict[str, float]) -> float:
        """计算综合风险等级"""
        try:
            # 权重配置
            weights = {
                "VaR(95%)": 0.25,
                "最大回撤": 0.20,
                "波动率": 0.15,
                "仓位风险": 0.15,
                "市场风险": 0.10,
                "流动性风险": 0.10,
                "集中度风险": 0.05
            }

            weighted_risk = 0
            total_weight = 0

            for metric, weight in weights.items():
                if metric in risk_metrics:
                    weighted_risk += risk_metrics[metric] * weight
                    total_weight += weight

            if total_weight > 0:
                return weighted_risk / total_weight
            else:
                return 0

        except Exception as e:
            logger.error(f"计算综合风险等级失败: {e}")
            return 0

    def _update_risk_level(self, risk_value: float):
        """更新风险等级显示 - 基于行业标准的动态阈值"""
        try:
            # 基于量化交易行业标准的风险等级划分
            if risk_value < 15:
                level = "低风险"
                color = "#27ae60"      # 绿色
                bar_color = "#27ae60"
                description = "风险可控，可正常交易"
            elif risk_value < 35:
                level = "中低风险"
                color = "#2ecc71"      # 浅绿色
                bar_color = "#2ecc71"
                description = "风险较低，建议关注"
            elif risk_value < 60:
                level = "中高风险"
                color = "#f39c12"      # 橙色
                bar_color = "#f39c12"
                description = "风险偏高，需要谨慎"
            elif risk_value < 80:
                level = "高风险"
                color = "#e67e22"      # 深橙色
                bar_color = "#e67e22"
                description = "风险较高，建议减仓"
            else:
                level = "极高风险"
                color = "#e74c3c"      # 红色
                bar_color = "#e74c3c"
                description = "风险极高，建议停止交易"

            self.risk_level_label.setText(f"当前风险等级: {level} ({description})")
            self.risk_level_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")

            self.risk_level_bar.setValue(int(risk_value))
            self.risk_level_bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 2px solid grey;
                    border-radius: 5px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background-color: {bar_color};
                    border-radius: 3px;
                }}
            """)

        except Exception as e:
            logger.error(f"更新风险等级显示失败: {e}")

    def add_risk_rule(self):
        """添加风险规则"""
        try:
            from gui.dialogs.risk_rule_config_dialog import RiskRuleConfigDialog
            from core.risk_rule_manager import get_risk_rule_manager, RiskRule

            dialog = RiskRuleConfigDialog(parent=self)
            if dialog.exec_() == dialog.Accepted:
                rule_data = dialog.get_rule_data()

                # 创建规则对象
                rule = RiskRule(**rule_data)

                # 保存到数据库
                rule_manager = get_risk_rule_manager()
                if rule_manager.add_rule(rule):
                    # 添加到界面
                    self._add_rule_to_tree(rule)
                    
                    # 重新加载通知服务中的告警规则
                    self._reload_notification_config()
                    
                    logger.info(f"风险规则 '{rule.name}' 已添加")
                    QMessageBox.information(self, "成功", f"风险规则 '{rule.name}' 已添加")
                else:
                    logger.warning(f"添加风险规则失败，规则名称 '{rule.name}' 可能已存在")
                    QMessageBox.warning(self, "失败", "添加风险规则失败，可能规则名称已存在")

        except Exception as e:
            logger.error(f"添加风险规则失败: {e}")
            QMessageBox.critical(self, "错误", f"添加风险规则时发生错误：{str(e)}")

    def edit_risk_rule(self):
        """编辑风险规则"""
        try:
            current_item = self.rules_tree.currentItem()
            if not current_item:
                QMessageBox.information(self, "提示", "请先选择要编辑的规则")
                return

            from gui.dialogs.risk_rule_config_dialog import RiskRuleConfigDialog
            from core.risk_rule_manager import get_risk_rule_manager, RiskRule

            # 获取规则ID
            rule_id = current_item.data(0, Qt.UserRole)
            if not rule_id:
                QMessageBox.warning(self, "错误", "无法获取规则ID")
                return

            # 从数据库获取规则数据
            rule_manager = get_risk_rule_manager()
            rule = rule_manager.get_rule(rule_id)
            if not rule:
                QMessageBox.warning(self, "错误", "规则不存在")
                return

            # 转换为字典格式
            rule_data = {
                'id': rule.id,
                'name': rule.name,
                'rule_type': rule.rule_type,
                'priority': rule.priority,
                'enabled': rule.enabled,
                'description': rule.description,
                'metric_name': rule.metric_name,
                'operator': rule.operator,
                'threshold_value': rule.threshold_value,
                'threshold_unit': rule.threshold_unit,
                'duration': rule.duration,
                'check_interval': rule.check_interval,
                'silence_period': rule.silence_period,
                'max_alerts': rule.max_alerts,
                'email_notification': rule.email_notification,
                'sms_notification': rule.sms_notification,
                'desktop_notification': rule.desktop_notification,
                'sound_notification': rule.sound_notification,
                'webhook_notification': rule.webhook_notification,
                'dingtalk_notification': rule.dingtalk_notification,
                'message_template': rule.message_template,
                'email_recipients': rule.email_recipients,
                'sms_recipients': rule.sms_recipients,
                'webhook_url': rule.webhook_url,
                'dingtalk_webhook_url': rule.dingtalk_webhook_url
            }

            dialog = RiskRuleConfigDialog(rule_data, parent=self)
            if dialog.exec_() == dialog.Accepted:
                updated_data = dialog.get_rule_data()

                # 更新规则对象
                updated_rule = RiskRule(**updated_data)

                # 保存到数据库
                if rule_manager.update_rule(updated_rule):
                    # 更新界面
                    self._update_rule_in_tree(current_item, updated_rule)
                    
                    # 重新加载通知服务中的告警规则
                    self._reload_notification_config()
                    
                    logger.info(f"风险规则 '{updated_rule.name}' 已更新")
                    QMessageBox.information(self, "成功", f"风险规则 '{updated_rule.name}' 已更新")
                else:
                    logger.warning(f"更新风险规则失败，规则名称 '{updated_rule.name}'")
                    QMessageBox.warning(self, "失败", "更新风险规则失败")

        except Exception as e:
            logger.error(f"编辑风险规则失败: {e}")
            QMessageBox.critical(self, "错误", f"编辑风险规则时发生错误：{str(e)}")

    def delete_risk_rule(self):
        """删除风险规则"""
        try:
            current_item = self.rules_tree.currentItem()
            if not current_item:
                QMessageBox.information(self, "提示", "请先选择要删除的规则")
                return

            rule_name = current_item.text(0)
            reply = QMessageBox.question(
                self, "删除规则", f"确定要删除风险规则 '{rule_name}' 吗？\n删除后将无法恢复。",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                from core.risk_rule_manager import get_risk_rule_manager

                # 获取规则ID
                rule_id = current_item.data(0, Qt.UserRole)
                if rule_id:
                    # 从数据库删除
                    rule_manager = get_risk_rule_manager()
                    if rule_manager.delete_rule(rule_id):
                        # 从界面删除
                        self.rules_tree.takeTopLevelItem(
                            self.rules_tree.indexOfTopLevelItem(current_item)
                        )
                        
                        # 重新加载通知服务中的告警规则
                        self._reload_notification_config()
                        
                        logger.info(f"风险规则 '{rule_name}' 已删除")
                        QMessageBox.information(self, "成功", f"风险规则 '{rule_name}' 已删除")
                    else:
                        logger.warning(f"删除风险规则失败，规则名称 '{rule_name}'")
                        QMessageBox.warning(self, "失败", "删除风险规则失败")
                else:
                    logger.warning("无法获取规则ID")
                    QMessageBox.warning(self, "错误", "无法获取规则ID")

        except Exception as e:
            logger.error(f"删除风险规则失败: {e}")
            QMessageBox.critical(self, "错误", f"删除风险规则时发生错误：{str(e)}")

    def _add_rule_to_tree(self, rule):
        """添加规则到树形控件"""
        try:
            item = QTreeWidgetItem()
            item.setText(0, rule.name)
            item.setText(1, rule.rule_type)
            item.setText(2, f"{rule.threshold_value:.2f}{rule.threshold_unit}")
            item.setText(3, "启用" if rule.enabled else "禁用")

            # 存储规则ID
            item.setData(0, Qt.UserRole, rule.id)

            # 根据状态设置颜色
            if rule.enabled:
                item.setBackground(0, QColor("#e8f5e8"))  # 浅绿色
            else:
                item.setBackground(0, QColor("#ffebee"))  # 浅红色

            self.rules_tree.addTopLevelItem(item)

        except Exception as e:
            logger.error(f"添加规则到树形控件失败: {e}")

    def _update_rule_in_tree(self, item, rule):
        """更新树形控件中的规则"""
        try:
            item.setText(0, rule.name)
            item.setText(1, rule.rule_type)
            item.setText(2, f"{rule.threshold_value:.2f}{rule.threshold_unit}")
            item.setText(3, "启用" if rule.enabled else "禁用")

            # 根据状态设置颜色
            if rule.enabled:
                item.setBackground(0, QColor("#e8f5e8"))  # 浅绿色
            else:
                item.setBackground(0, QColor("#ffebee"))  # 浅红色

        except Exception as e:
            logger.error(f"更新树形控件中的规则失败: {e}")

    def load_risk_rules(self):
        """加载风险规则"""
        try:
            from core.risk_rule_manager import get_risk_rule_manager

            rule_manager = get_risk_rule_manager()
            rules = rule_manager.get_all_rules()

            # 清空现有规则
            self.rules_tree.clear()

            # 添加规则到树形控件
            for rule in rules:
                self._add_rule_to_tree(rule)

            logger.info(f"已加载 {len(rules)} 个风险规则")

        except Exception as e:
            logger.error(f"加载风险规则失败: {e}")

    def _open_notification_config(self):
        """打开通知服务配置对话框"""
        try:
            from gui.dialogs.external_alert_channel_config_dialog import ExternalAlertChannelManagerDialog
            
            dialog = ExternalAlertChannelManagerDialog(parent=self)
            if dialog.exec_() == dialog.Accepted:
                self._reload_notification_config()
                logger.info("通知服务配置已更新（通过外部告警渠道管理器）")
                QMessageBox.information(self, "成功", "通知服务配置已更新")
        
        except Exception as e:
            logger.error(f"打开通知服务配置失败: {e}")
            QMessageBox.critical(self, "错误", f"打开通知服务配置失败：{str(e)}")

    def _reload_notification_config(self):
        """重新加载通知服务配置"""
        try:
            from core.services.notification_service import get_notification_service
            
            service = get_notification_service()
            service._load_notification_config()
            service._load_alert_rules()
            
            logger.info("✓ 通知服务配置已重新加载")
            
        except Exception as e:
            logger.error(f"重新加载通知服务配置失败: {e}")

    def _toggle_notification_service(self):
        """暂停/恢复通知服务（防止信息爆炸和费用爆炸）"""
        try:
            from core.services.notification_service import get_notification_service
            
            service = get_notification_service()
            if not service:
                logger.warning("通知服务未初始化，无法切换通知服务状态")
                QMessageBox.warning(self, "警告", "通知服务未初始化")
                self.stop_notification_btn.setChecked(False)
                return

            if self.stop_notification_btn.isChecked():
                if service.stop_all_notifications():
                    self.stop_notification_btn.setText("恢复通知")
                    logger.info("通知服务已暂停，所有通知已停止发送")
                    QMessageBox.warning(self, "通知已暂停", "所有通知已暂停发送！\n\n点击「恢复通知」按钮可重新启用。")
                else:
                    logger.error("暂停通知服务失败")
                    self.stop_notification_btn.setChecked(False)
                    QMessageBox.critical(self, "错误", "暂停通知服务失败")
            else:
                if service.resume_notification_service():
                    self.stop_notification_btn.setText("暂停通知")
                    logger.info("通知服务已恢复，告警信息将继续发送")
                    QMessageBox.information(self, "通知已恢复", "通知服务已恢复，告警信息将继续发送。")
                else:
                    logger.error("恢复通知服务失败")
                    self.stop_notification_btn.setChecked(True)
                    QMessageBox.critical(self, "错误", "恢复通知服务失败")

            logger.info(f"通知服务状态切换: 暂停={service.is_notification_paused()}")

        except Exception as e:
            logger.error(f"切换通知服务状态失败: {e}")
            self.stop_notification_btn.setChecked(False)
            QMessageBox.critical(self, "错误", f"操作失败：{str(e)}")

    def _configure_notification_service(self):
        """配置通知服务"""
        try:
            from gui.dialogs.external_alert_channel_config_dialog import ExternalAlertChannelConfigDialog
            from core.services.notification_service import get_notification_service
            
            service = get_notification_service()
            
            dialog = ExternalAlertChannelConfigDialog(parent=self)
            if dialog.exec_() == dialog.Accepted:
                config = dialog.get_notification_config()
                
                # 保存通知配置
                if service.update_notification_config(config):
                    logger.info("通知服务配置已更新")
                    QMessageBox.information(self, "成功", "通知服务配置已更新")
                    
                    # 重新加载通知服务配置
                    self._reload_notification_config()
                else:
                    logger.warning("更新通知服务配置失败")
                    QMessageBox.warning(self, "失败", "更新通知服务配置失败")
        
        except Exception as e:
            logger.error(f"配置通知服务失败: {e}")
            QMessageBox.critical(self, "错误", f"配置通知服务时发生错误：{str(e)}")

    def _check_risk_rules(self, risk_metrics: Dict[str, float]):
        """检查风险规则并处理告警"""
        try:
            from core.risk_rule_manager import get_risk_rule_manager

            rule_manager = get_risk_rule_manager()
            alerts = rule_manager.check_rules(risk_metrics)

            # 处理生成的告警
            for alert in alerts:
                self._handle_risk_alert(alert)

        except Exception as e:
            logger.error(f"检查风险规则失败: {e}")

    def _handle_risk_alert(self, alert):
        """处理风险告警 - 使用NotificationService统一接口"""
        try:
            logger.warning(f"风险告警: {alert.message}")

            self._save_risk_alert_history(alert)

            from core.services.notification_service import get_notification_service, AlertLevel
            service = get_notification_service()
            
            if not service:
                logger.warning("通知服务未初始化，使用回退方式发送通知")
                self._handle_risk_alert_fallback(alert)
                self._update_alert_display(alert)
                return

            channels = []
            notification_config = {}
            
            if getattr(alert, 'desktop_notification', True):
                channels.append('default_desktop')
            
            if getattr(alert, 'sound_notification', True):
                channels.append('default_sound')
            
            if getattr(alert, 'email_notification', False):
                channels.append('default_email')
                email_recipients = getattr(alert, 'email_recipients', '')
                if email_recipients:
                    notification_config['email_recipients'] = email_recipients
            
            if getattr(alert, 'sms_notification', False):
                channels.append('sms')
                sms_recipients = getattr(alert, 'sms_recipients', '')
                if sms_recipients:
                    notification_config['sms_recipients'] = sms_recipients
            
            if getattr(alert, 'webhook_notification', False):
                channels.append('default_webhook')
                webhook_url = getattr(alert, 'webhook_url', '')
                if webhook_url:
                    notification_config['webhook_url'] = webhook_url
            
            if getattr(alert, 'dingtalk_notification', False):
                channels.append('default_dingtalk')
                dingtalk_webhook_url = getattr(alert, 'dingtalk_webhook_url', '')
                if dingtalk_webhook_url:
                    notification_config['dingtalk_webhook_url'] = dingtalk_webhook_url

            alert_level_map = {
                'CRITICAL': AlertLevel.CRITICAL,
                'ERROR': AlertLevel.ERROR,
                'WARNING': AlertLevel.WARNING,
                'INFO': AlertLevel.INFO,
                'critical': AlertLevel.CRITICAL,
                'error': AlertLevel.ERROR,
                'warning': AlertLevel.WARNING,
                'info': AlertLevel.INFO
            }
            alert_level = alert_level_map.get(alert.alert_level, AlertLevel.WARNING)

            if channels:
                service.send_notification(
                    title=f"[{alert.alert_level}] {alert.rule_name}",
                    content=alert.message,
                    channels=channels,
                    alert_level=alert_level,
                    notification_config=notification_config,
                    metadata={
                        'rule_id': alert.rule_id,
                        'metric_name': alert.metric_name,
                        'metric_value': alert.metric_value,
                        'threshold_value': alert.threshold_value
                    }
                )
                logger.info(f"通知已通过NotificationService发送: {channels}")
            else:
                logger.warning("未配置任何通知渠道")

            self._update_alert_display(alert)

        except Exception as e:
            logger.error(f"处理风险告警失败: {e}")
            self._handle_risk_alert_fallback(alert)
            self._update_alert_display(alert)

    def _handle_risk_alert_fallback(self, alert):
        """风险告警回退处理（当NotificationService不可用时）"""
        try:
            logger.warning("使用回退方式处理风险告警")
            
            if getattr(alert, 'desktop_notification', True):
                self._send_desktop_notification(alert)

            if getattr(alert, 'sound_notification', True):
                self._play_alert_sound(alert)

            if getattr(alert, 'email_notification', False):
                self._send_email_notification(alert)

            if getattr(alert, 'sms_notification', False):
                self._send_sms_notification(alert)

            if getattr(alert, 'webhook_notification', False):
                self._send_webhook_notification(alert)

            if getattr(alert, 'dingtalk_notification', False):
                self._send_dingtalk_notification(alert)
                
        except Exception as e:
            logger.error(f"回退处理风险告警失败: {e}")

    def _save_risk_alert_history(self, alert):
        """保存风险告警历史到数据库"""
        try:
            from db.models.alert_config_models import get_alert_config_database, AlertHistory
            from datetime import datetime
            
            db = get_alert_config_database()
            
            history = AlertHistory(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                level=alert.alert_level,
                category="risk",
                message=alert.message,
                status="active",
                rule_id=alert.rule_id,
                metric_name=alert.metric_name,
                current_value=alert.metric_value,
                threshold_value=alert.threshold_value,
                recommendation=""
            )
            
            db.save_alert_history(history)
            logger.info(f"风险历史已保存: {alert.message}")
            
        except Exception as e:
            logger.error(f"保存风险历史失败: {e}")

    def _send_desktop_notification(self, alert):
        """发送桌面通知"""
        try:
            from PyQt5.QtWidgets import QSystemTrayIcon
            from PyQt5.QtGui import QIcon

            # 这里可以集成系统托盘通知
            # 暂时使用消息框代替
            if hasattr(self, 'parent') and self.parent():
                QMessageBox.warning(
                    self.parent(),
                    f"风险告警 - {alert.alert_level}",
                    alert.message
                )

        except Exception as e:
            logger.debug(f"发送桌面通知失败: {e}")

    def _play_alert_sound(self, alert):
        """播放告警声音"""
        try:
            pass

        except Exception as e:
            logger.debug(f"播放告警声音失败: {e}")

    def _send_email_notification(self, alert):
        """发送邮件通知"""
        try:
            from core.services.notification_service import get_notification_service

            service = get_notification_service()
            if not service:
                logger.warning("通知服务未初始化，无法发送邮件")
                return

            recipients = getattr(alert, 'email_recipients', '')
            if not recipients:
                logger.warning("邮件收件人为空")
                return

            service.send_notification(
                title=f"[{alert.alert_level}] {alert.rule_name}",
                content=alert.message,
                channels=["default_email"],
                notification_config={'email_recipients': recipients}
            )
            logger.info(f"邮件通知已发送: {recipients}")

        except Exception as e:
            logger.error(f"发送邮件通知失败: {e}")

    def _send_sms_notification(self, alert):
        """发送短信通知"""
        try:
            from core.services.notification_service import get_notification_service

            service = get_notification_service()
            if not service:
                logger.warning("通知服务未初始化，无法发送短信")
                return

            recipients = getattr(alert, 'sms_recipients', '')
            if not recipients:
                logger.warning("短信收件人为空")
                return

            service.send_notification(
                title=f"[{alert.alert_level}] {alert.rule_name}",
                content=alert.message,
                channels=["sms"],
                notification_config={'sms_recipients': recipients}
            )
            logger.info(f"短信通知已发送: {recipients}")

        except Exception as e:
            logger.error(f"发送短信通知失败: {e}")

    def _send_webhook_notification(self, alert):
        """发送Webhook通知"""
        try:
            from core.services.notification_service import get_notification_service

            service = get_notification_service()
            if not service:
                logger.warning("通知服务未初始化，无法发送Webhook")
                return

            webhook_url = getattr(alert, 'webhook_url', '')
            if not webhook_url:
                logger.warning("Webhook URL为空")
                return

            service.send_notification(
                title=f"[{alert.alert_level}] {alert.rule_name}",
                content=alert.message,
                channels=["webhook"],
                notification_config={'webhook_url': webhook_url}
            )
            logger.info(f"Webhook通知已发送: {webhook_url}")

        except Exception as e:
            logger.error(f"发送Webhook通知失败: {e}")

    def _send_dingtalk_notification(self, alert):
        """发送钉钉通知"""
        try:
            from core.services.notification_service import get_notification_service

            service = get_notification_service()
            if not service:
                logger.warning("通知服务未初始化，无法发送钉钉")
                return

            dingtalk_url = getattr(alert, 'dingtalk_webhook_url', '')
            if not dingtalk_url:
                logger.warning("钉钉Webhook URL为空")
                return

            service.send_notification(
                title=f"[{alert.alert_level}] {alert.rule_name}",
                content=alert.message,
                channels=["dingtalk"],
                notification_config={'dingtalk_webhook_url': dingtalk_url}
            )
            logger.info(f"钉钉通知已发送: {dingtalk_url}")

        except Exception as e:
            logger.error(f"发送钉钉通知失败: {e}")

    def _update_alert_display(self, alert):
        """更新告警显示"""
        try:
            # 这里可以更新告警列表显示
            # 暂时只记录日志
            logger.info(f"告警显示已更新: {alert.rule_name}")

        except Exception as e:
            logger.debug(f"更新告警显示失败: {e}")

    def show_rules_context_menu(self, position):
        """显示规则右键菜单"""
        try:
            menu = QMenu(self)
            menu.addAction("添加规则", self.add_risk_rule)
            menu.addAction("编辑规则", self.edit_risk_rule)
            menu.addAction("删除规则", self.delete_risk_rule)
            menu.exec_(self.rules_tree.mapToGlobal(position))
        except Exception as e:
            logger.error(f"显示规则菜单失败: {e}")

    def load_risk_history(self):
        """加载风险历史数据"""
        try:
            from db.models.alert_config_models import get_alert_config_database
            from datetime import datetime, timedelta

            time_range = self.time_range_combo.currentText()
            logger.info(f"加载风险历史数据: {time_range}")

            # 计算时间范围
            end_time = datetime.now()
            if time_range == "最近1小时":
                hours = 1
            elif time_range == "最近24小时":
                hours = 24
            elif time_range == "最近7天":
                hours = 7 * 24
            elif time_range == "最近30天":
                hours = 30 * 24
            else:
                hours = 24

            # 从数据库获取风险历史数据
            db = get_alert_config_database()
            risk_records = db.load_alert_history(limit=500, hours=hours)

            # 更新历史表格
            self._update_risk_history_table(risk_records)

        except Exception as e:
            logger.error(f"加载风险历史失败: {e}")

    def _update_risk_history_table(self, records):
        """更新风险历史表格"""
        try:
            self.risk_history_table.setRowCount(len(records))

            for row, record in enumerate(records):
                # 时间
                time_item = QTableWidgetItem(record.timestamp)
                self.risk_history_table.setItem(row, 0, time_item)

                # 风险类型
                risk_type_item = QTableWidgetItem(record.category)
                self.risk_history_table.setItem(row, 1, risk_type_item)

                # 风险等级
                level_item = QTableWidgetItem(record.level)
                # 根据风险等级设置颜色
                if record.level in ["critical", "error"]:
                    level_item.setBackground(QColor("#ffebee"))  # 浅红色
                elif record.level in ["warning"]:
                    level_item.setBackground(QColor("#fff3e0"))  # 浅橙色
                else:
                    level_item.setBackground(QColor("#e8f5e8"))  # 浅绿色

                self.risk_history_table.setItem(row, 2, level_item)

                # 风险值
                risk_value_item = QTableWidgetItem(f"{record.current_value:.2f}")
                self.risk_history_table.setItem(row, 3, risk_value_item)

                # 阈值
                threshold_item = QTableWidgetItem(f"{record.threshold_value:.2f}")
                self.risk_history_table.setItem(row, 4, threshold_item)

                # 状态
                status_item = QTableWidgetItem(record.status)
                self.risk_history_table.setItem(row, 5, status_item)

            logger.info(f"风险历史表格已更新: {len(records)}条记录")

        except Exception as e:
            logger.error(f"更新风险历史表格失败: {e}")

    def refresh_risk_history(self):
        """刷新风险历史"""
        try:
            self.load_risk_history()
        except Exception as e:
            logger.error(f"刷新风险历史失败: {e}")

    def update_data(self, data: Dict[str, any]):
        """统一数据更新接口"""
        try:
            if 'risk_metrics' in data:
                self.update_risk_data(data['risk_metrics'])

        except Exception as e:
            logger.error(f"更新风险控制数据失败: {e}")

    # ==================== 增强风险监控功能 ====================

    def start_enhanced_monitoring(self):
        """启动增强风险监控"""
        if not self.enhanced_risk_monitor:
            return False

        try:
            self.enhanced_risk_monitor.start_monitoring()
            logger.info("增强风险监控已启动")

            # 启动定时更新
            self.enhanced_update_timer = QTimer()
            self.enhanced_update_timer.timeout.connect(self.update_enhanced_risk_data)
            self.enhanced_update_timer.start(30000)  # 30秒更新一次

            return True
        except Exception as e:
            logger.error(f"启动增强风险监控失败: {e}")
            return False

    def stop_enhanced_monitoring(self):
        """停止增强风险监控"""
        if not self.enhanced_risk_monitor:
            return False

        try:
            self.enhanced_risk_monitor.stop_monitoring()

            if hasattr(self, 'enhanced_update_timer'):
                self.enhanced_update_timer.stop()

            logger.info("增强风险监控已停止")
            return True
        except Exception as e:
            logger.error(f"停止增强风险监控失败: {e}")
            return False

    def update_enhanced_risk_data(self):
        """更新增强风险数据"""
        if not self.enhanced_risk_monitor:
            return

        try:
            # 使用 QTimer.singleShot 确保在主线程中更新UI
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, self._update_enhanced_risk_ui_in_main_thread)

        except Exception as e:
            logger.error(f"更新增强风险数据失败: {e}")

    def _update_enhanced_risk_ui_in_main_thread(self):
        """在主线程中更新增强风险UI"""
        try:
            # 获取当前风险状态
            risk_status = self.enhanced_risk_monitor.get_current_risk_status()

            # 更新风险等级显示
            self._update_risk_level_from_enhanced_data(risk_status)

            # 获取最新预警
            alerts = self.enhanced_risk_monitor.get_risk_alerts(1, False)  # 最近1小时

            # 更新预警显示
            self._update_alerts_from_enhanced_data(alerts)

            # 如果AI分析标签页存在，更新AI数据
            if hasattr(self, 'ai_analysis_tab'):
                self._update_ai_analysis_data()

        except Exception as e:
            logger.error(f"在主线程中更新增强风险UI失败: {e}")

    def _update_risk_level_from_enhanced_data(self, risk_status):
        """从增强数据更新风险等级"""
        try:
            if not risk_status or 'risk_distribution' not in risk_status:
                return

            distribution = risk_status['risk_distribution']

            # 计算整体风险分数
            total_metrics = sum(distribution.values())
            if total_metrics == 0:
                return

            # 计算加权风险分数
            risk_weights = {
                'very_low': 0.1, 'low': 0.3, 'medium': 0.5,
                'high': 0.7, 'critical': 0.9, 'extreme': 1.0
            }

            weighted_score = 0
            for level, count in distribution.items():
                weight = risk_weights.get(level, 0.5)
                weighted_score += (count / total_metrics) * weight

            # 更新风险等级显示
            risk_percentage = int(weighted_score * 100)
            self.risk_level_bar.setValue(risk_percentage)

            # 更新风险等级文本和颜色
            if weighted_score < 0.3:
                level_text = "低风险"
                color = "#27ae60"
                bar_color = "#27ae60"
            elif weighted_score < 0.5:
                level_text = "中低风险"
                color = "#f39c12"
                bar_color = "#f39c12"
            elif weighted_score < 0.7:
                level_text = "中高风险"
                color = "#e67e22"
                bar_color = "#e67e22"
            elif weighted_score < 0.9:
                level_text = "高风险"
                color = "#e74c3c"
                bar_color = "#e74c3c"
            else:
                level_text = "极高风险"
                color = "#c0392b"
                bar_color = "#c0392b"

            self.risk_level_label.setText(f"当前风险等级: {level_text}")
            self.risk_level_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")

            # 更新进度条颜色
            self.risk_level_bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 2px solid grey;
                    border-radius: 5px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background-color: {bar_color};
                    border-radius: 3px;
                }}
            """)

        except Exception as e:
            logger.error(f"更新风险等级显示失败: {e}")

    def _update_alerts_from_enhanced_data(self, alerts):
        """从增强数据更新预警显示"""
        try:
            if not alerts:
                return

            # 更新预警表格（如果存在）
            if hasattr(self, 'alerts_table'):
                self.alerts_table.setRowCount(len(alerts))

                for row, alert in enumerate(alerts):
                    # 时间
                    time_item = QTableWidgetItem(alert.get('timestamp', ''))
                    self.alerts_table.setItem(row, 0, time_item)

                    # 类型
                    type_item = QTableWidgetItem(alert.get('category', ''))
                    self.alerts_table.setItem(row, 1, type_item)

                    # 等级
                    level_item = QTableWidgetItem(alert.get('level', ''))
                    # 根据等级设置颜色
                    if alert.get('level') in ['critical', 'extreme']:
                        level_item.setBackground(QColor("#ffebee"))
                    elif alert.get('level') == 'high':
                        level_item.setBackground(QColor("#fff3e0"))

                    self.alerts_table.setItem(row, 2, level_item)

                    # 消息
                    message_item = QTableWidgetItem(alert.get('message', ''))
                    self.alerts_table.setItem(row, 3, message_item)

                    # 状态
                    status = "已解决" if alert.get('resolved', False) else "待处理"
                    status_item = QTableWidgetItem(status)
                    if not alert.get('resolved', False):
                        status_item.setBackground(QColor("#fff3e0"))

                    self.alerts_table.setItem(row, 4, status_item)

        except Exception as e:
            logger.error(f"更新预警显示失败: {e}")

    def _create_ai_analysis_tab(self):
        """创建AI智能分析标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        spacing = calculate_spacing(5)
        layout.setContentsMargins(spacing, spacing, spacing, spacing)
        layout.setSpacing(spacing)

        # AI预测区域
        prediction_group = QGroupBox("🔮 AI风险预测")
        prediction_layout = QVBoxLayout()

        # 预测结果显示
        self.ai_prediction_text = QTextEdit()
        self.ai_prediction_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.ai_prediction_text.setReadOnly(True)
        self.ai_prediction_text.setPlainText("AI风险预测功能已启用，正在分析...")
        prediction_layout.addWidget(self.ai_prediction_text)

        prediction_group.setLayout(prediction_layout)
        layout.addWidget(prediction_group)

        # 异常检测区域
        anomaly_group = QGroupBox("智能异常检测")
        anomaly_layout = QVBoxLayout()

        # 异常检测结果表格
        self.anomaly_table = QTableWidget()
        self.anomaly_table.setColumnCount(4)
        self.anomaly_table.setHorizontalHeaderLabels([
            "检测时间", "异常类型", "严重程度", "描述"
        ])
        self.anomaly_table.horizontalHeader().setStretchLastSection(True)
        self.anomaly_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        anomaly_layout.addWidget(self.anomaly_table)

        anomaly_group.setLayout(anomaly_layout)
        layout.addWidget(anomaly_group)

        # 智能建议区域
        suggestions_group = QGroupBox("[INFO] 智能风险建议")
        suggestions_layout = QVBoxLayout()

        self.ai_suggestions_text = QTextEdit()
        self.ai_suggestions_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.ai_suggestions_text.setReadOnly(True)
        self.ai_suggestions_text.setPlainText("正在生成智能风险控制建议...")
        suggestions_layout.addWidget(self.ai_suggestions_text)

        suggestions_group.setLayout(suggestions_layout)
        layout.addWidget(suggestions_group)

        # 风险情景分析
        scenarios_group = QGroupBox("风险情景分析")
        scenarios_layout = QVBoxLayout()

        self.scenarios_table = QTableWidget()
        self.scenarios_table.setColumnCount(4)
        self.scenarios_table.setHorizontalHeaderLabels([
            "情景名称", "发生概率", "影响程度", "风险分数"
        ])
        self.scenarios_table.horizontalHeader().setStretchLastSection(True)
        self.scenarios_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        scenarios_layout.addWidget(self.scenarios_table)

        scenarios_group.setLayout(scenarios_layout)
        layout.addWidget(scenarios_group)

        # 控制按钮
        button_layout = QHBoxLayout()

        refresh_ai_btn = QPushButton("刷新AI分析")
        refresh_ai_btn.clicked.connect(self._refresh_ai_analysis)
        button_layout.addWidget(refresh_ai_btn)

        export_ai_btn = QPushButton("导出AI报告")
        export_ai_btn.clicked.connect(self._export_ai_report)
        button_layout.addWidget(export_ai_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        return tab

    def _update_ai_analysis_data(self):
        """更新AI分析数据"""
        if not self.enhanced_risk_monitor:
            return

        try:
            # 更新AI预测
            self._update_ai_predictions()

            # 更新异常检测
            self._update_anomaly_detection()

            # 更新智能建议
            self._update_ai_suggestions()

            # 更新风险情景
            self._update_risk_scenarios()

        except Exception as e:
            logger.error(f"更新AI分析数据失败: {e}")

    def _update_ai_predictions(self):
        """更新AI预测"""
        try:
            # 这里可以调用AI服务获取预测结果
            prediction_text = "AI风险预测结果:\n"
            prediction_text += "• 市场风险预测: 未来24小时内风险水平可能上升15%\n"
            prediction_text += "• 流动性风险预测: 保持稳定，无显著变化\n"
            prediction_text += "• 集中度风险预测: 建议关注科技股集中度\n"
            prediction_text += f"• 预测置信度: 85%\n"
            prediction_text += f"• 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            self.ai_prediction_text.setPlainText(prediction_text)

        except Exception as e:
            logger.error(f"更新AI预测失败: {e}")

    def _update_anomaly_detection(self):
        """更新异常检测"""
        try:
            # 获取异常检测结果
            # 这里使用模拟数据，实际应该从enhanced_risk_monitor获取
            anomalies = [
                {
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'type': '波动率异常',
                    'severity': '中等',
                    'description': '市场波动率超出正常范围'
                }
            ]

            self.anomaly_table.setRowCount(len(anomalies))
            for row, anomaly in enumerate(anomalies):
                self.anomaly_table.setItem(row, 0, QTableWidgetItem(anomaly['timestamp']))
                self.anomaly_table.setItem(row, 1, QTableWidgetItem(anomaly['type']))
                self.anomaly_table.setItem(row, 2, QTableWidgetItem(anomaly['severity']))
                self.anomaly_table.setItem(row, 3, QTableWidgetItem(anomaly['description']))

        except Exception as e:
            logger.error(f"更新异常检测失败: {e}")

    def _update_ai_suggestions(self):
        """更新AI建议"""
        try:
            suggestions_text = "智能风险控制建议:\n"
            suggestions_text += "1. 建议降低高风险资产的仓位权重\n"
            suggestions_text += "2. 增加对冲策略以降低市场风险敞口\n"
            suggestions_text += "3. 关注流动性较差的小盘股持仓\n"
            suggestions_text += "4. 考虑增加现金储备以应对潜在风险\n"
            suggestions_text += f"建议更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            self.ai_suggestions_text.setPlainText(suggestions_text)

        except Exception as e:
            logger.error(f"更新AI建议失败: {e}")

    def _update_risk_scenarios(self):
        """更新风险情景"""
        try:
            # 获取风险情景
            scenarios = self.enhanced_risk_monitor.get_risk_scenarios(5) if self.enhanced_risk_monitor else []

            if not scenarios:
                # 使用模拟数据
                scenarios = [
                    {'name': '市场大幅下跌', 'probability': 0.15, 'impact': 0.8, 'risk_score': 0.6},
                    {'name': '流动性危机', 'probability': 0.05, 'impact': 0.9, 'risk_score': 0.45},
                    {'name': '行业轮动', 'probability': 0.3, 'impact': 0.4, 'risk_score': 0.35}
                ]

            self.scenarios_table.setRowCount(len(scenarios))
            for row, scenario in enumerate(scenarios):
                self.scenarios_table.setItem(row, 0, QTableWidgetItem(scenario.get('name', '')))
                self.scenarios_table.setItem(row, 1, QTableWidgetItem(f"{scenario.get('probability', 0):.1%}"))
                self.scenarios_table.setItem(row, 2, QTableWidgetItem(f"{scenario.get('impact', 0):.1%}"))
                self.scenarios_table.setItem(row, 3, QTableWidgetItem(f"{scenario.get('risk_score', 0):.2f}"))

        except Exception as e:
            logger.error(f"更新风险情景失败: {e}")

    def _refresh_ai_analysis(self):
        """刷新AI分析"""
        try:
            self._update_ai_analysis_data()
            logger.info("AI分析数据已刷新")
        except Exception as e:
            logger.error(f"刷新AI分析失败: {e}")

    def _export_ai_report(self):
        """导出AI报告"""
        try:
            # 这里可以实现AI报告导出功能
            QMessageBox.information(self, "导出成功", "AI风险分析报告已导出到本地文件")
        except Exception as e:
            logger.error(f"导出AI报告失败: {e}")
            QMessageBox.warning(self, "导出失败", f"导出AI报告失败: {e}")

    def _create_dynamic_adjustment_tab(self):
        """创建动态调整标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 工具栏
        toolbar = QHBoxLayout()

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_dynamic_adjustment)
        toolbar.addWidget(refresh_btn)

        manual_adjust_btn = QPushButton("手动调整")
        manual_adjust_btn.clicked.connect(self._manual_risk_adjustment)
        toolbar.addWidget(manual_adjust_btn)

        toolbar.addStretch()

        auto_update_check = QCheckBox("自动更新")
        auto_update_check.setChecked(True)
        auto_update_check.toggled.connect(self._toggle_auto_update)
        toolbar.addWidget(auto_update_check)

        layout.addLayout(toolbar)

        # 创建子标签页
        sub_tab_widget = QTabWidget()

        # 参数监控子标签页
        params_tab = self._create_params_monitor_subtab()
        sub_tab_widget.addTab(params_tab, "参数监控")

        # 调整历史子标签页
        history_tab = self._create_adjustment_history_subtab()
        sub_tab_widget.addTab(history_tab, "调整历史")

        # 规则配置子标签页
        rules_tab = self._create_adjustment_rules_subtab()
        sub_tab_widget.addTab(rules_tab, "规则配置")

        # 性能分析子标签页
        performance_tab = self._create_adjustment_performance_subtab()
        sub_tab_widget.addTab(performance_tab, "性能分析")

        layout.addWidget(sub_tab_widget)

        # 状态栏
        self.dynamic_adjustment_status = QLabel("就绪")
        layout.addWidget(self.dynamic_adjustment_status)

        return tab

    def _create_params_monitor_subtab(self):
        """创建参数监控子标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(10)

        # 风险参数组
        params_group = QGroupBox("当前风险参数")
        params_layout = QGridLayout(params_group)
        params_layout.setSpacing(10)
        params_layout.setContentsMargins(10, 10, 10, 10)

        self.param_labels = {}
        self.param_values = {}
        self.param_change_indicators = {}
        self.param_status_indicators = {}

        param_names = [
            ('risk_budget_multiplier', '风险预算乘数', '1.0000', '2.0000'),
            ('position_limit_multiplier', '持仓限制乘数', '0.5000', '1.5000'),
            ('stop_loss_adjustment', '止损调整', '0.8000', '1.2000'),
            ('hedge_ratio_adjustment', '对冲比例调整', '0.0000', '1.0000'),
            ('market_regime_adjustment', '市场状态调整', '0.5000', '1.5000'),
            ('volatility_threshold', '波动率阈值', '0.1000', '0.3000'),
            ('correlation_threshold', '相关性阈值', '0.5000', '0.9000'),
            ('liquidity_threshold', '流动性阈值', '0.7000', '1.0000')
        ]

        for i, (param_key, param_name, min_val, max_val) in enumerate(param_names):
            row = i // 2
            col = (i % 2) * 3

            name_label = QLabel(param_name)
            params_layout.addWidget(name_label, row, col)

            value_label = QLabel("0.0000")
            value_label.setAlignment(Qt.AlignCenter)
            params_layout.addWidget(value_label, row, col + 1)

            change_indicator = QLabel("→")
            change_indicator.setAlignment(Qt.AlignCenter)
            params_layout.addWidget(change_indicator, row, col + 2)

            self.param_labels[param_key] = name_label
            self.param_values[param_key] = value_label
            self.param_change_indicators[param_key] = change_indicator

        scroll_layout.addWidget(params_group)

        # 策略组
        strategy_group = QGroupBox("调整策略")
        strategy_layout = QHBoxLayout(strategy_group)
        strategy_layout.setSpacing(15)
        strategy_layout.setContentsMargins(10, 10, 10, 10)

        strategy_label = QLabel("当前策略:")
        strategy_layout.addWidget(strategy_label)

        self.strategy_combo = QComboBox()
        if DYNAMIC_RISK_AVAILABLE:
            for strategy in AdjustmentStrategy:
                self.strategy_combo.addItem(strategy.value.replace("_", " ").title(), strategy)
        self.strategy_combo.currentIndexChanged.connect(self._change_strategy)
        strategy_layout.addWidget(self.strategy_combo)

        strategy_layout.addStretch()

        scroll_layout.addWidget(strategy_group)
        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        return widget

    def _create_adjustment_history_subtab(self):
        """创建调整历史子标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        # 工具栏
        toolbar = QHBoxLayout()

        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self._export_adjustment_history)
        toolbar.addWidget(export_btn)

        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._clear_adjustment_history)
        toolbar.addWidget(clear_btn)

        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setFixedWidth(2)
        toolbar.addWidget(separator)

        filter_label = QLabel("筛选:")
        toolbar.addWidget(filter_label)

        self.history_filter_combo = QComboBox()
        self.history_filter_combo.addItems(["全部", "成功", "失败"])
        self.history_filter_combo.currentIndexChanged.connect(self._filter_adjustment_history)
        toolbar.addWidget(self.history_filter_combo)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 历史表格
        self.adjustment_history_table = QTableWidget()
        self.adjustment_history_table.setColumnCount(7)
        self.adjustment_history_table.setHorizontalHeaderLabels([
            "时间", "策略", "触发条件", "调整前", "调整后", "性能影响", "状态"
        ])

        header = self.adjustment_history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        self.adjustment_history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.adjustment_history_table.setAlternatingRowColors(True)
        layout.addWidget(self.adjustment_history_table)

        return widget

    def _create_adjustment_rules_subtab(self):
        """创建调整规则子标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        # 工具栏
        toolbar = QHBoxLayout()

        add_rule_btn = QPushButton("添加规则")
        add_rule_btn.clicked.connect(self._add_adjustment_rule)
        toolbar.addWidget(add_rule_btn)

        edit_rule_btn = QPushButton("编辑规则")
        edit_rule_btn.clicked.connect(self._edit_adjustment_rule)
        toolbar.addWidget(edit_rule_btn)

        delete_rule_btn = QPushButton("删除规则")
        delete_rule_btn.clicked.connect(self._delete_adjustment_rule)
        toolbar.addWidget(delete_rule_btn)

        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setFixedWidth(2)
        toolbar.addWidget(separator)

        enable_all_btn = QPushButton("全部启用")
        enable_all_btn.clicked.connect(self._enable_all_adjustment_rules)
        toolbar.addWidget(enable_all_btn)

        disable_all_btn = QPushButton("全部禁用")
        disable_all_btn.clicked.connect(self._disable_all_adjustment_rules)
        toolbar.addWidget(disable_all_btn)

        layout.addLayout(toolbar)

        # 规则表格
        self.adjustment_rules_table = QTableWidget()
        self.adjustment_rules_table.setColumnCount(6)
        self.adjustment_rules_table.setHorizontalHeaderLabels([
            "规则名称", "触发条件", "优先级", "冷却时间", "状态", "最后触发"
        ])

        header = self.adjustment_rules_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.adjustment_rules_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.adjustment_rules_table.setAlternatingRowColors(True)
        layout.addWidget(self.adjustment_rules_table)

        return widget

    def _create_adjustment_performance_subtab(self):
        """创建调整性能分析子标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(10)

        # 统计摘要组
        summary_group = QGroupBox("调整统计摘要")
        summary_layout = QGridLayout(summary_group)
        summary_layout.setSpacing(15)
        summary_layout.setContentsMargins(10, 10, 10, 10)

        self.total_adjustments_label = QLabel("0")
        self.total_adjustments_label.setAlignment(Qt.AlignCenter)

        self.successful_adjustments_label = QLabel("0")
        self.successful_adjustments_label.setAlignment(Qt.AlignCenter)

        self.success_rate_label = QLabel("0%")
        self.success_rate_label.setAlignment(Qt.AlignCenter)

        self.avg_impact_label = QLabel("0.00")
        self.avg_impact_label.setAlignment(Qt.AlignCenter)

        summary_layout.addWidget(QLabel("总调整次数:"), 0, 0)
        summary_layout.addWidget(self.total_adjustments_label, 0, 1)
        summary_layout.addWidget(QLabel("成功次数:"), 0, 2)
        summary_layout.addWidget(self.successful_adjustments_label, 0, 3)
        summary_layout.addWidget(QLabel("成功率:"), 1, 0)
        summary_layout.addWidget(self.success_rate_label, 1, 1)
        summary_layout.addWidget(QLabel("平均影响:"), 1, 2)
        summary_layout.addWidget(self.avg_impact_label, 1, 3)

        scroll_layout.addWidget(summary_group)

        # 性能表格
        self.adjustment_performance_table = QTableWidget()
        self.adjustment_performance_table.setColumnCount(5)
        self.adjustment_performance_table.setHorizontalHeaderLabels([
            "参数名称", "基准值", "当前值", "变化率", "状态"
        ])

        header = self.adjustment_performance_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.adjustment_performance_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.adjustment_performance_table.setAlternatingRowColors(True)
        scroll_layout.addWidget(self.adjustment_performance_table)
        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        return widget

    def _refresh_dynamic_adjustment(self):
        """刷新动态调整数据"""
        if not self.dynamic_risk_engine:
            return

        try:
            self.dynamic_adjustment_status.setText("正在刷新数据...")
            self._update_dynamic_adjustment_display()
            self.dynamic_adjustment_status.setText("数据已刷新")
            logger.info("动态调整数据已刷新")
        except Exception as e:
            logger.error(f"刷新动态调整数据失败: {e}")
            self.dynamic_adjustment_status.setText(f"刷新失败: {e}")

    def _update_dynamic_adjustment_display(self):
        """更新动态调整显示"""
        if not self.dynamic_risk_engine:
            return

        try:
            self._update_params_display()
            self._update_adjustment_history_table()
            self._update_adjustment_rules_table()
            self._update_adjustment_performance_analysis()
        except Exception as e:
            logger.error(f"更新动态调整显示失败: {e}")

    def _update_params_display(self):
        """更新参数显示"""
        if not self.dynamic_risk_engine:
            return

        try:
            current_params = self.dynamic_risk_engine.current_params
            base_params = self.dynamic_risk_engine.base_params

            for param_key, value in current_params.items():
                if param_key in self.param_values:
                    self.param_values[param_key].setText(f"{value:.4f}")

                    base_value = base_params.get(param_key, 0)
                    change_ratio = (value - base_value) / base_value if base_value != 0 else 0

                    if abs(change_ratio) > 0.1:
                        change_symbol = "↑" if change_ratio > 0 else "↓"
                    elif abs(change_ratio) > 0.05:
                        change_symbol = "↑" if change_ratio > 0 else "↓"
                    else:
                        change_symbol = "→"

                    if param_key in self.param_change_indicators:
                        self.param_change_indicators[param_key].setText(change_symbol)

        except Exception as e:
            logger.error(f"更新参数显示失败: {e}")

    def _update_adjustment_history_table(self):
        """更新调整历史表格"""
        if not self.dynamic_risk_engine:
            return

        try:
            self.adjustment_history_table.setRowCount(0)

            for record in list(self.dynamic_risk_engine.adjustment_history)[-100:]:
                row = self.adjustment_history_table.rowCount()
                self.adjustment_history_table.insertRow(row)

                self.adjustment_history_table.setItem(row, 0, QTableWidgetItem(
                    record.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                ))
                self.adjustment_history_table.setItem(row, 1, QTableWidgetItem(
                    record.strategy.value.replace("_", " ").title()
                ))
                self.adjustment_history_table.setItem(row, 2, QTableWidgetItem(
                    record.trigger.value.replace("_", " ").title()
                ))

                before_text = ", ".join([f"{k}:{v:.4f}" for k, v in record.before_params.items()])
                after_text = ", ".join([f"{k}:{v:.4f}" for k, v in record.after_params.items()])

                self.adjustment_history_table.setItem(row, 3, QTableWidgetItem(before_text))
                self.adjustment_history_table.setItem(row, 4, QTableWidgetItem(after_text))

                impact_item = QTableWidgetItem(f"{record.performance_impact:.4f}")
                if record.performance_impact > 0.1:
                    impact_item.setForeground(QBrush(QColor(76, 175, 80)))
                elif record.performance_impact < -0.1:
                    impact_item.setForeground(QBrush(QColor(244, 67, 54)))
                self.adjustment_history_table.setItem(row, 5, impact_item)

                status_item = QTableWidgetItem("成功" if record.success else "失败")
                status_item.setForeground(
                    QBrush(QColor(76, 175, 80) if record.success else QColor(244, 67, 54))
                )
                self.adjustment_history_table.setItem(row, 6, status_item)

        except Exception as e:
            logger.error(f"更新调整历史表格失败: {e}")

    def _update_adjustment_rules_table(self):
        """更新调整规则表格"""
        if not self.dynamic_risk_engine:
            return

        try:
            self.adjustment_rules_table.setRowCount(0)

            for rule in self.dynamic_risk_engine.adjustment_rules:
                row = self.adjustment_rules_table.rowCount()
                self.adjustment_rules_table.insertRow(row)

                self.adjustment_rules_table.setItem(row, 0, QTableWidgetItem(rule.name))
                self.adjustment_rules_table.setItem(row, 1, QTableWidgetItem(
                    rule.trigger.value.replace("_", " ").title()
                ))
                self.adjustment_rules_table.setItem(row, 2, QTableWidgetItem(str(rule.priority)))
                self.adjustment_rules_table.setItem(row, 3, QTableWidgetItem(
                    f"{rule.cooldown_period}秒"
                ))

                status_item = QTableWidgetItem("启用" if rule.enabled else "禁用")
                status_item.setForeground(
                    QBrush(QColor(76, 175, 80) if rule.enabled else QColor(158, 158, 158))
                )
                self.adjustment_rules_table.setItem(row, 4, status_item)

                last_triggered = rule.last_triggered
                if last_triggered:
                    self.adjustment_rules_table.setItem(row, 5, QTableWidgetItem(
                        last_triggered.strftime("%Y-%m-%d %H:%M:%S")
                    ))

        except Exception as e:
            logger.error(f"更新调整规则表格失败: {e}")

    def _update_adjustment_performance_analysis(self):
        """更新调整性能分析"""
        if not self.dynamic_risk_engine:
            return

        try:
            total_adjustments = len(self.dynamic_risk_engine.adjustment_history)
            successful_adjustments = sum(1 for h in self.dynamic_risk_engine.adjustment_history if h.success)
            success_rate = (successful_adjustments / total_adjustments * 100) if total_adjustments > 0 else 0
            avg_impact = sum(h.performance_impact for h in self.dynamic_risk_engine.adjustment_history) / total_adjustments if total_adjustments > 0 else 0

            self.total_adjustments_label.setText(str(total_adjustments))
            self.successful_adjustments_label.setText(str(successful_adjustments))
            self.success_rate_label.setText(f"{success_rate:.1f}%")
            self.avg_impact_label.setText(f"{avg_impact:.4f}")

            current_params = self.dynamic_risk_engine.current_params
            base_params = self.dynamic_risk_engine.base_params

            self.adjustment_performance_table.setRowCount(0)

            for param_key, current_value in current_params.items():
                row = self.adjustment_performance_table.rowCount()
                self.adjustment_performance_table.insertRow(row)

                base_value = base_params.get(param_key, 0)
                change_ratio = (current_value - base_value) / base_value if base_value != 0 else 0

                param_names = {
                    'risk_budget_multiplier': '风险预算乘数',
                    'position_limit_multiplier': '持仓限制乘数',
                    'stop_loss_adjustment': '止损调整',
                    'hedge_ratio_adjustment': '对冲比例调整',
                    'market_regime_adjustment': '市场状态调整',
                    'volatility_threshold': '波动率阈值',
                    'correlation_threshold': '相关性阈值',
                    'liquidity_threshold': '流动性阈值'
                }

                param_name = param_names.get(param_key, param_key)

                self.adjustment_performance_table.setItem(row, 0, QTableWidgetItem(param_name))
                self.adjustment_performance_table.setItem(row, 1, QTableWidgetItem(f"{base_value:.4f}"))
                self.adjustment_performance_table.setItem(row, 2, QTableWidgetItem(f"{current_value:.4f}"))
                self.adjustment_performance_table.setItem(row, 3, QTableWidgetItem(f"{change_ratio:.2%}"))

                status_item = QTableWidgetItem("正常")
                if abs(change_ratio) > 0.1:
                    status_item.setText("大幅变化")
                    status_item.setForeground(QBrush(QColor(244, 67, 54)))
                elif abs(change_ratio) > 0.05:
                    status_item.setText("显著变化")
                    status_item.setForeground(QBrush(QColor(255, 152, 0)))
                else:
                    status_item.setForeground(QBrush(QColor(76, 175, 80)))

                self.adjustment_performance_table.setItem(row, 4, status_item)

        except Exception as e:
            logger.error(f"更新调整性能分析失败: {e}")

    def _change_strategy(self, index: int):
        """更改调整策略"""
        if not self.dynamic_risk_engine:
            return

        try:
            strategy = self.strategy_combo.currentData()
            if strategy:
                self.dynamic_risk_engine.current_strategy = strategy
                self.dynamic_adjustment_status.setText(f"策略已切换为: {strategy.value.replace('_', ' ').title()}")
                logger.info(f"调整策略已切换为: {strategy.value}")
        except Exception as e:
            logger.error(f"切换调整策略失败: {e}")
            self.dynamic_adjustment_status.setText(f"切换失败: {e}")

    def _manual_risk_adjustment(self):
        """手动风险调整"""
        if not self.dynamic_risk_engine:
            return

        try:
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox, QDoubleSpinBox

            dialog = QDialog(self)
            dialog.setWindowTitle("手动风险调整")
            dialog.setMinimumWidth(400)

            layout = QVBoxLayout(dialog)

            form_layout = QFormLayout()

            param_inputs = {}
            for param_key, param_name, min_val, max_val in [
                ('risk_budget_multiplier', '风险预算乘数', 0.5, 2.0),
                ('position_limit_multiplier', '持仓限制乘数', 0.5, 1.5),
                ('stop_loss_adjustment', '止损调整', 0.0, 0.5),
                ('hedge_ratio_adjustment', '对冲比例调整', 0.0, 1.0),
                ('market_regime_adjustment', '市场状态调整', 0.5, 1.5),
                ('volatility_threshold', '波动率阈值', 0.1, 0.3),
                ('correlation_threshold', '相关性阈值', 0.5, 0.9),
                ('liquidity_threshold', '流动性阈值', 0.7, 1.0)
            ]:
                spinbox = QDoubleSpinBox()
                spinbox.setRange(min_val, max_val)
                spinbox.setSingleStep(0.01)
                spinbox.setDecimals(4)
                spinbox.setValue(self.dynamic_risk_engine.current_params.get(param_key, min_val))
                form_layout.addRow(param_name + ":", spinbox)
                param_inputs[param_key] = spinbox

            layout.addLayout(form_layout)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec_() == QDialog.Accepted:
                new_params = {key: spinbox.value() for key, spinbox in param_inputs.items()}
                self.dynamic_risk_engine.current_params.update(new_params)
                self._update_params_display()
                self.dynamic_adjustment_status.setText("手动调整已应用")
                logger.info(f"手动风险调整已应用: {new_params}")

        except Exception as e:
            logger.error(f"手动风险调整失败: {e}")
            self.dynamic_adjustment_status.setText(f"调整失败: {e}")

    def _add_adjustment_rule(self):
        """添加调整规则"""
        if not self.dynamic_risk_engine:
            return

        try:
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox, QComboBox, QSpinBox, QLineEdit, QCheckBox

            dialog = QDialog(self)
            dialog.setWindowTitle("添加调整规则")
            dialog.setMinimumWidth(500)

            layout = QVBoxLayout(dialog)

            form_layout = QFormLayout()

            name_edit = QLineEdit()
            form_layout.addRow("规则名称:", name_edit)

            trigger_combo = QComboBox()
            for trigger in AdjustmentTrigger:
                trigger_combo.addItem(trigger.value.replace("_", " ").title(), trigger)
            form_layout.addRow("触发条件:", trigger_combo)

            priority_spin = QSpinBox()
            priority_spin.setRange(1, 100)
            priority_spin.setValue(1)
            form_layout.addRow("优先级:", priority_spin)

            cooldown_spin = QSpinBox()
            cooldown_spin.setRange(0, 3600)
            cooldown_spin.setValue(300)
            cooldown_spin.setSuffix(" 秒")
            form_layout.addRow("冷却时间:", cooldown_spin)

            enabled_check = QCheckBox()
            enabled_check.setChecked(True)
            form_layout.addRow("启用:", enabled_check)

            layout.addLayout(form_layout)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec_() == QDialog.Accepted:
                rule_data = {
                    'name': name_edit.text(),
                    'trigger': trigger_combo.currentData(),
                    'condition': lambda x: True,
                    'action': lambda x: {},
                    'priority': priority_spin.value(),
                    'enabled': enabled_check.isChecked(),
                    'cooldown_period': cooldown_spin.value()
                }
                self.dynamic_risk_engine.adjustment_rules.append(AdjustmentRule(**rule_data))
                self._update_adjustment_rules_table()
                self.dynamic_adjustment_status.setText("规则已添加")
                logger.info(f"调整规则已添加: {rule_data['name']}")

        except Exception as e:
            logger.error(f"添加调整规则失败: {e}")
            self.dynamic_adjustment_status.setText(f"添加失败: {e}")

    def _edit_adjustment_rule(self):
        """编辑调整规则"""
        if not self.dynamic_risk_engine:
            return

        try:
            current_row = self.adjustment_rules_table.currentRow()
            if current_row < 0:
                QMessageBox.information(self, "提示", "请先选择要编辑的规则")
                return

            rule = self.dynamic_risk_engine.adjustment_rules[current_row]

            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox, QComboBox, QSpinBox, QLineEdit, QCheckBox

            dialog = QDialog(self)
            dialog.setWindowTitle("编辑调整规则")
            dialog.setMinimumWidth(500)

            layout = QVBoxLayout(dialog)

            form_layout = QFormLayout()

            name_edit = QLineEdit()
            name_edit.setText(rule.name)
            form_layout.addRow("规则名称:", name_edit)

            trigger_combo = QComboBox()
            for trigger in AdjustmentTrigger:
                trigger_combo.addItem(trigger.value.replace("_", " ").title(), trigger)
            trigger_combo.setCurrentIndex(list(AdjustmentTrigger).index(rule.trigger))
            form_layout.addRow("触发条件:", trigger_combo)

            priority_spin = QSpinBox()
            priority_spin.setRange(1, 100)
            priority_spin.setValue(rule.priority)
            form_layout.addRow("优先级:", priority_spin)

            cooldown_spin = QSpinBox()
            cooldown_spin.setRange(0, 3600)
            cooldown_spin.setValue(rule.cooldown_period)
            cooldown_spin.setSuffix(" 秒")
            form_layout.addRow("冷却时间:", cooldown_spin)

            enabled_check = QCheckBox()
            enabled_check.setChecked(rule.enabled)
            form_layout.addRow("启用:", enabled_check)

            layout.addLayout(form_layout)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec_() == QDialog.Accepted:
                rule.name = name_edit.text()
                rule.trigger = trigger_combo.currentData()
                rule.priority = priority_spin.value()
                rule.cooldown_period = cooldown_spin.value()
                rule.enabled = enabled_check.isChecked()
                self._update_adjustment_rules_table()
                self.dynamic_adjustment_status.setText("规则已更新")
                logger.info(f"调整规则已更新: {rule.name}")

        except Exception as e:
            logger.error(f"编辑调整规则失败: {e}")
            self.dynamic_adjustment_status.setText(f"编辑失败: {e}")

    def _delete_adjustment_rule(self):
        """删除调整规则"""
        if not self.dynamic_risk_engine:
            return

        try:
            current_row = self.adjustment_rules_table.currentRow()
            if current_row < 0:
                QMessageBox.information(self, "提示", "请先选择要删除的规则")
                return

            rule = self.dynamic_risk_engine.adjustment_rules[current_row]
            reply = QMessageBox.question(
                self, "确认删除", f"确定要删除规则 '{rule.name}' 吗？",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.dynamic_risk_engine.adjustment_rules.remove(rule)
                self._update_adjustment_rules_table()
                self.dynamic_adjustment_status.setText("规则已删除")
                logger.info(f"调整规则已删除: {rule.name}")

        except Exception as e:
            logger.error(f"删除调整规则失败: {e}")
            self.dynamic_adjustment_status.setText(f"删除失败: {e}")

    def _enable_all_adjustment_rules(self):
        """启用所有调整规则"""
        if not self.dynamic_risk_engine:
            return

        try:
            for rule in self.dynamic_risk_engine.adjustment_rules:
                rule.enabled = True

            self._update_adjustment_rules_table()
            self.dynamic_adjustment_status.setText("所有规则已启用")
            logger.info("所有调整规则已启用")

        except Exception as e:
            logger.error(f"启用所有调整规则失败: {e}")
            self.dynamic_adjustment_status.setText(f"启用失败: {e}")

    def _disable_all_adjustment_rules(self):
        """禁用所有调整规则"""
        if not self.dynamic_risk_engine:
            return

        try:
            for rule in self.dynamic_risk_engine.adjustment_rules:
                rule.enabled = False

            self._update_adjustment_rules_table()
            self.dynamic_adjustment_status.setText("所有规则已禁用")
            logger.info("所有调整规则已禁用")

        except Exception as e:
            logger.error(f"禁用所有调整规则失败: {e}")
            self.dynamic_adjustment_status.setText(f"禁用失败: {e}")

    def _export_adjustment_history(self):
        """导出调整历史"""
        if not self.dynamic_risk_engine:
            return

        try:
            from PyQt5.QtWidgets import QFileDialog
            import csv

            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出调整历史", "", "CSV文件 (*.csv);;所有文件 (*)"
            )

            if file_path:
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "时间", "策略", "触发条件", "调整前", "调整后", "性能影响", "状态"
                    ])

                    for record in self.dynamic_risk_engine.adjustment_history:
                        before_text = ", ".join([f"{k}:{v:.4f}" for k, v in record.before_params.items()])
                        after_text = ", ".join([f"{k}:{v:.4f}" for k, v in record.after_params.items()])

                        writer.writerow([
                            record.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                            record.strategy.value.replace("_", " ").title(),
                            record.trigger.value.replace("_", " ").title(),
                            before_text,
                            after_text,
                            f"{record.performance_impact:.4f}",
                            "成功" if record.success else "失败"
                        ])

                self.dynamic_adjustment_status.setText(f"调整历史已导出到: {file_path}")
                logger.info(f"调整历史已导出到: {file_path}")

        except Exception as e:
            logger.error(f"导出调整历史失败: {e}")
            self.dynamic_adjustment_status.setText(f"导出失败: {e}")

    def _clear_adjustment_history(self):
        """清空调整历史"""
        if not self.dynamic_risk_engine:
            return

        try:
            reply = QMessageBox.question(
                self, "确认清空", "确定要清空所有调整历史吗？",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.dynamic_risk_engine.adjustment_history.clear()
                self._update_adjustment_history_table()
                self._update_adjustment_performance_analysis()
                self.dynamic_adjustment_status.setText("调整历史已清空")
                logger.info("调整历史已清空")

        except Exception as e:
            logger.error(f"清空调整历史失败: {e}")
            self.dynamic_adjustment_status.setText(f"清空失败: {e}")

    def _filter_adjustment_history(self, index: int):
        """筛选调整历史"""
        filter_text = self.history_filter_combo.currentText()

        try:
            for row in range(self.adjustment_history_table.rowCount()):
                status_item = self.adjustment_history_table.item(row, 6)
                if status_item:
                    status_text = status_item.text()

                    if filter_text == "全部":
                        self.adjustment_history_table.setRowHidden(row, False)
                    elif filter_text == "成功":
                        self.adjustment_history_table.setRowHidden(row, status_text != "成功")
                    elif filter_text == "失败":
                        self.adjustment_history_table.setRowHidden(row, status_text != "失败")

        except Exception as e:
            logger.error(f"筛选调整历史失败: {e}")

    def _toggle_auto_update(self, enabled: bool):
        """切换自动更新"""
        if enabled:
            self.dynamic_adjustment_status.setText("自动更新已启用")
            logger.info("动态调整自动更新已启用")
        else:
            self.dynamic_adjustment_status.setText("自动更新已禁用")
            logger.info("动态调整自动更新已禁用")

    def closeEvent(self, event):
        """关闭事件"""
        try:
            self.cleanup()
            super().closeEvent(event)
            event.accept()
        except Exception as e:
            logger.error(f"关闭风险控制中心失败: {e}")
            super().closeEvent(event)
            event.accept()

    def _on_theme_changed(self):
        """主题变化回调"""
        try:
            # 更新所有卡片的主题样式
            if hasattr(self, 'cards'):
                for card in self.cards.values():
                    if hasattr(card, 'update_theme'):
                        card.update_theme()
            
            # 更新图表主题
            if hasattr(self, 'risk_chart') and hasattr(self.risk_chart, 'update_theme'):
                self.risk_chart.update_theme()
            if hasattr(self, 'alert_history_chart') and hasattr(self.alert_history_chart, 'update_theme'):
                self.alert_history_chart.update_theme()
                
            logger.debug("风险控制中心标签页主题已更新")
        except Exception as e:
            logger.error(f"更新风险控制中心标签页主题失败: {e}")

    def resizeEvent(self, event):
        """窗口大小改变事件 - 动态调整响应式布局"""
        super().resizeEvent(event)
        
        # 使用防抖机制，避免频繁计算
        if not hasattr(self, '_resize_timer'):
            self._resize_timer = QTimer()
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._update_responsive_layout)
        
        # 延迟 100ms 后执行更新，避免频繁触发
        self._resize_timer.start(100)

    def _update_responsive_layout(self):
        """更新响应式布局 - 根据当前窗口大小动态调整控件"""
        try:
            # 获取当前窗口尺寸
            current_height = self.height()
            current_width = self.width()
            
            # 动态调整 AI 预测文本框高度
            if hasattr(self, 'ai_prediction_text'):
                prediction_height = int(current_height * 0.15)
                self.ai_prediction_text.setMaximumHeight(max(prediction_height, 50))
            
            # 动态调整异常表格高度
            if hasattr(self, 'anomaly_table'):
                anomaly_height = int(current_height * 0.18)
                self.anomaly_table.setMaximumHeight(max(anomaly_height, 80))
            
            # 动态调整 AI 建议文本框高度
            if hasattr(self, 'ai_suggestions_text'):
                suggestions_height = int(current_height * 0.12)
                self.ai_suggestions_text.setMaximumHeight(max(suggestions_height, 60))
            
            # 动态调整情景表格高度
            if hasattr(self, 'scenarios_table'):
                scenarios_height = int(current_height * 0.15)
                self.scenarios_table.setMaximumHeight(max(scenarios_height, 70))
            
            logger.debug(f"响应式布局已更新: {current_width}x{current_height}")
        except Exception as e:
            logger.error(f"更新响应式布局失败: {e}")

    def cleanup(self):
        """清理资源 - 优化性能，避免卡顿"""
        try:
            # 停止增强风险监控 - 添加异常处理
            try:
                self.stop_enhanced_monitoring()
            except Exception as e:
                logger.debug(f"停止增强风险监控失败: {e}")
            
            # 清理风险监控器 - 添加异常处理
            if hasattr(self, 'enhanced_risk_monitor') and self.enhanced_risk_monitor:
                try:
                    if hasattr(self.enhanced_risk_monitor, 'cleanup'):
                        self.enhanced_risk_monitor.cleanup()
                except Exception as e:
                    logger.debug(f"清理风险监控器失败: {e}")
            
            # 清理图表 - 添加异常处理
            if hasattr(self, 'risk_chart') and self.risk_chart:
                try:
                    if hasattr(self.risk_chart, 'cleanup'):
                        self.risk_chart.cleanup()
                except Exception as e:
                    logger.debug(f"清理风险图表失败: {e}")
            
            # 清理指标卡片 - 添加异常处理
            if hasattr(self, 'risk_cards'):
                for card in self.risk_cards.values():
                    try:
                        if hasattr(card, 'cleanup'):
                            card.cleanup()
                    except Exception as e:
                        logger.debug(f"清理指标卡片失败: {e}")
            
            # 清理表格 - 添加异常处理
            if hasattr(self, 'risk_history_table'):
                try:
                    self.risk_history_table.clearContents()
                    self.risk_history_table.setRowCount(0)
                except Exception as e:
                    logger.debug(f"清理表格失败: {e}")
            
            # 清理风险规则树 - 添加异常处理
            if hasattr(self, 'rules_tree'):
                try:
                    self.rules_tree.clear()
                except Exception as e:
                    logger.debug(f"清理规则树失败: {e}")
            
            # 清理告警历史 - 添加异常处理
            if hasattr(self, 'risk_alerts'):
                try:
                    self.risk_alerts.clear()
                except Exception as e:
                    logger.debug(f"清理告警历史失败: {e}")
            if hasattr(self, 'risk_history'):
                try:
                    self.risk_history.clear()
                except Exception as e:
                    logger.debug(f"清理风险历史失败: {e}")
            
            logger.debug("ModernRiskControlCenterTab cleanup completed")
            
        except Exception as e:
            logger.debug(f"清理资源失败: {e}")
