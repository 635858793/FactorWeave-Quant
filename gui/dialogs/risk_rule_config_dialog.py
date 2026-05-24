#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险规则配置对话框
用于配置风险监控的告警规则
"""

from typing import Dict, Optional
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QPushButton, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox,
    QCheckBox, QTextEdit, QLabel, QTabWidget, QWidget, QMessageBox, QGridLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from loguru import logger

from .base_dialog import BaseDialog


class RiskRuleConfigDialog(BaseDialog):
    """风险规则配置对话框"""

    def __init__(self, rule_data: Optional[Dict] = None, parent=None):
        self.rule_data = rule_data or {}
        self.is_edit_mode = bool(rule_data)
        
        title = "编辑风险规则" if self.is_edit_mode else "添加风险规则"
        
        super().__init__(
            parent,
            title=title,
            size=(600, 500),
            settings_key="RiskRuleConfigDialog"
        )
        
        self.init_ui()
        self.load_rule_data()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 创建标签页
        self.tab_widget = QTabWidget()

        # 基本设置标签页
        self.basic_tab = self._create_basic_tab()
        self.tab_widget.addTab(self.basic_tab, "基本设置")

        # 触发条件标签页
        self.condition_tab = self._create_condition_tab()
        self.tab_widget.addTab(self.condition_tab, "触发条件")

        # 通知设置标签页
        self.notification_tab = self._create_notification_tab()
        self.tab_widget.addTab(self.notification_tab, "通知设置")

        layout.addWidget(self.tab_widget)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_rule)
        button_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _create_basic_tab(self):
        """创建基本设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 基本信息组
        basic_group = QGroupBox("基本信息")
        basic_form = QFormLayout()

        self.rule_name_edit = QLineEdit()
        self.rule_name_edit.setPlaceholderText("请输入规则名称")
        basic_form.addRow("规则名称*:", self.rule_name_edit)

        self.rule_type_combo = QComboBox()
        self.rule_type_combo.addItems([
            "VaR风险", "最大回撤", "波动率", "Beta系数", "夏普比率",
            "仓位风险", "市场风险", "行业风险", "流动性风险", "信用风险",
            "操作风险", "集中度风险", "综合风险评分"
        ])
        basic_form.addRow("风险类型*:", self.rule_type_combo)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["低", "中", "高", "紧急"])
        self.priority_combo.setCurrentText("中")
        basic_form.addRow("优先级:", self.priority_combo)

        self.enabled_checkbox = QCheckBox()
        self.enabled_checkbox.setChecked(True)
        basic_form.addRow("启用规则:", self.enabled_checkbox)

        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("请输入规则描述（可选）")
        basic_form.addRow("描述:", self.description_edit)

        basic_group.setLayout(basic_form)
        layout.addWidget(basic_group)

        layout.addStretch()
        return tab

    def _create_condition_tab(self):
        """创建触发条件标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 触发条件组
        condition_group = QGroupBox("触发条件")
        condition_form = QFormLayout()

        self.metric_combo = QComboBox()
        self.metric_combo.addItems([
            "VaR(95%)", "最大回撤", "波动率", "Beta系数", "夏普比率",
            "仓位风险", "市场风险", "行业风险", "流动性风险", "信用风险",
            "操作风险", "集中度风险", "综合风险评分"
        ])
        condition_form.addRow("监控指标*:", self.metric_combo)

        self.operator_combo = QComboBox()
        self.operator_combo.addItems([">", ">=", "<", "<=", "==", "!="])
        self.operator_combo.setCurrentText(">")
        condition_form.addRow("操作符*:", self.operator_combo)

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 999999.99)
        self.threshold_spin.setDecimals(2)
        self.threshold_spin.setValue(80.0)
        condition_form.addRow("阈值*:", self.threshold_spin)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["%", "倍", "分", "元", "无单位"])
        self.unit_combo.setCurrentText("%")
        condition_form.addRow("单位:", self.unit_combo)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 86400)  # 1秒到1天
        self.duration_spin.setValue(60)
        self.duration_spin.setSuffix("秒")
        condition_form.addRow("持续时间:", self.duration_spin)

        condition_group.setLayout(condition_form)
        layout.addWidget(condition_group)

        # 高级设置组
        advanced_group = QGroupBox("高级设置")
        advanced_form = QFormLayout()

        self.check_interval_spin = QSpinBox()
        self.check_interval_spin.setRange(1, 3600)  # 1秒到1小时
        self.check_interval_spin.setValue(60)
        self.check_interval_spin.setSuffix("秒")
        advanced_form.addRow("检查频率:", self.check_interval_spin)

        self.silence_period_spin = QSpinBox()
        self.silence_period_spin.setRange(0, 86400)  # 0秒到1天
        self.silence_period_spin.setValue(300)
        self.silence_period_spin.setSuffix("秒")
        advanced_form.addRow("静默期:", self.silence_period_spin)

        self.max_alerts_spin = QSpinBox()
        self.max_alerts_spin.setRange(1, 1000)
        self.max_alerts_spin.setValue(10)
        advanced_form.addRow("最大告警次数:", self.max_alerts_spin)

        advanced_group.setLayout(advanced_form)
        layout.addWidget(advanced_group)

        layout.addStretch()
        return tab

    def _create_notification_tab(self):
        """创建通知设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 通知方式组
        notification_group = QGroupBox("通知方式")
        notification_layout = QGridLayout()
        notification_layout.setColumnStretch(0, 1)
        notification_layout.setColumnStretch(1, 1)
        notification_layout.setColumnStretch(2, 1)

        # 第一行
        self.email_checkbox = QCheckBox("邮件通知")
        self.email_checkbox.setChecked(False)
        notification_layout.addWidget(self.email_checkbox, 0, 0)

        self.sms_checkbox = QCheckBox("短信通知")
        self.sms_checkbox.setChecked(False)
        notification_layout.addWidget(self.sms_checkbox, 0, 1)

        self.desktop_checkbox = QCheckBox("桌面通知")
        self.desktop_checkbox.setChecked(True)
        notification_layout.addWidget(self.desktop_checkbox, 0, 2)

        # 第二行
        self.sound_checkbox = QCheckBox("声音通知")
        self.sound_checkbox.setChecked(True)
        notification_layout.addWidget(self.sound_checkbox, 1, 0)

        self.webhook_checkbox = QCheckBox("Webhook通知")
        self.webhook_checkbox.setChecked(False)
        notification_layout.addWidget(self.webhook_checkbox, 1, 1)

        self.dingtalk_checkbox = QCheckBox("钉钉通知")
        self.dingtalk_checkbox.setChecked(False)
        notification_layout.addWidget(self.dingtalk_checkbox, 1, 2)

        notification_group.setLayout(notification_layout)
        layout.addWidget(notification_group)

        # 收件人设置组
        recipients_group = QGroupBox("收件人设置")
        recipients_form = QFormLayout()

        self.email_recipients_edit = QLineEdit()
        self.email_recipients_edit.setPlaceholderText("多个邮箱用逗号分隔")
        recipients_form.addRow("邮件收件人:", self.email_recipients_edit)

        self.sms_recipients_edit = QLineEdit()
        self.sms_recipients_edit.setPlaceholderText("多个手机号用逗号分隔")
        recipients_form.addRow("短信收件人:", self.sms_recipients_edit)

        self.webhook_url_edit = QLineEdit()
        self.webhook_url_edit.setPlaceholderText("Webhook URL")
        recipients_form.addRow("Webhook URL:", self.webhook_url_edit)

        self.dingtalk_webhook_url_edit = QLineEdit()
        self.dingtalk_webhook_url_edit.setPlaceholderText("钉钉Webhook URL")
        recipients_form.addRow("钉钉Webhook URL:", self.dingtalk_webhook_url_edit)

        recipients_group.setLayout(recipients_form)
        layout.addWidget(recipients_group)

        # 消息模板组
        template_group = QGroupBox("消息模板")
        template_layout = QVBoxLayout()

        template_label = QLabel("自定义消息模板（支持变量：{rule_name}, {metric}, {value}, {threshold}, {time}）:")
        template_layout.addWidget(template_label)

        self.message_template_edit = QTextEdit()
        self.message_template_edit.setMaximumHeight(100)
        self.message_template_edit.setPlainText(
            "【风险告警】规则\"{rule_name}\"触发：{metric} = {value}，超过阈值 {threshold}。时间：{time}"
        )
        template_layout.addWidget(self.message_template_edit)

        template_group.setLayout(template_layout)
        layout.addWidget(template_group)

        # 添加提示文字
        hint_label = QLabel("提示：如需配置邮件服务器、钉钉Webhook等通知渠道，请前往主界面的「告警配置」标签页，点击「配置通知服务」按钮进行全局设置。")
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-style: italic;
                background-color: #f5f5f5;
                padding: 10px;
                border-radius: 4px;
                border: 1px solid #e0e0e0;
            }
        """)
        layout.addWidget(hint_label)

        layout.addStretch()
        return tab

    def load_rule_data(self):
        """加载规则数据到界面"""
        if not self.rule_data:
            return

        try:
            # 基本信息
            self.rule_name_edit.setText(self.rule_data.get('name', ''))

            rule_type = self.rule_data.get('rule_type', 'VaR风险')
            index = self.rule_type_combo.findText(rule_type)
            if index >= 0:
                self.rule_type_combo.setCurrentIndex(index)

            priority = self.rule_data.get('priority', '中')
            index = self.priority_combo.findText(priority)
            if index >= 0:
                self.priority_combo.setCurrentIndex(index)

            self.enabled_checkbox.setChecked(self.rule_data.get('enabled', True))
            self.description_edit.setPlainText(self.rule_data.get('description', ''))

            # 触发条件
            metric = self.rule_data.get('metric_name', 'VaR(95%)')
            index = self.metric_combo.findText(metric)
            if index >= 0:
                self.metric_combo.setCurrentIndex(index)

            operator = self.rule_data.get('operator', '>')
            index = self.operator_combo.findText(operator)
            if index >= 0:
                self.operator_combo.setCurrentIndex(index)

            self.threshold_spin.setValue(self.rule_data.get('threshold_value', 80.0))

            unit = self.rule_data.get('threshold_unit', '%')
            index = self.unit_combo.findText(unit)
            if index >= 0:
                self.unit_combo.setCurrentIndex(index)

            self.duration_spin.setValue(self.rule_data.get('duration', 60))
            self.check_interval_spin.setValue(self.rule_data.get('check_interval', 60))
            self.silence_period_spin.setValue(self.rule_data.get('silence_period', 300))
            self.max_alerts_spin.setValue(self.rule_data.get('max_alerts', 10))

            # 通知设置
            self.email_checkbox.setChecked(self.rule_data.get('email_notification', False))
            self.sms_checkbox.setChecked(self.rule_data.get('sms_notification', False))
            self.desktop_checkbox.setChecked(self.rule_data.get('desktop_notification', True))
            self.sound_checkbox.setChecked(self.rule_data.get('sound_notification', True))
            self.webhook_checkbox.setChecked(self.rule_data.get('webhook_notification', False))
            self.dingtalk_checkbox.setChecked(self.rule_data.get('dingtalk_notification', False))

            # 通知参数
            self.email_recipients_edit.setText(self.rule_data.get('email_recipients', ''))
            self.sms_recipients_edit.setText(self.rule_data.get('sms_recipients', ''))
            self.webhook_url_edit.setText(self.rule_data.get('webhook_url', ''))
            self.dingtalk_webhook_url_edit.setText(self.rule_data.get('dingtalk_webhook_url', ''))

            template = self.rule_data.get('message_template', '')
            if template:
                self.message_template_edit.setPlainText(template)

        except Exception as e:
            logger.error(f"加载规则数据失败: {e}")

    def save_rule(self):
        """保存规则"""
        try:
            # 验证必填字段
            if not self.rule_name_edit.text().strip():
                QMessageBox.warning(self, "验证失败", "请输入规则名称")
                self.tab_widget.setCurrentIndex(0)  # 切换到基本设置标签页
                self.rule_name_edit.setFocus()
                return

            # 验证阈值合理性
            threshold_value = self.threshold_spin.value()
            metric_name = self.metric_combo.currentText()
            unit = self.unit_combo.currentText()

            # 根据不同指标验证阈值范围
            if unit == "%" and (threshold_value < 0 or threshold_value > 100):
                QMessageBox.warning(self, "验证失败", "百分比阈值应在0-100之间")
                self.tab_widget.setCurrentIndex(1)  # 切换到触发条件标签页
                self.threshold_spin.setFocus()
                return

            if metric_name in ["夏普比率", "Beta系数"] and (threshold_value < -10 or threshold_value > 10):
                QMessageBox.warning(self, "验证失败", f"{metric_name}阈值应在-10到10之间")
                self.tab_widget.setCurrentIndex(1)
                self.threshold_spin.setFocus()
                return

            # 验证时间参数合理性
            if self.duration_spin.value() > self.check_interval_spin.value() * 10:
                QMessageBox.warning(self, "验证失败", "持续时间不应超过检查频率的10倍")
                self.tab_widget.setCurrentIndex(1)
                self.duration_spin.setFocus()
                return

            if self.silence_period_spin.value() < self.check_interval_spin.value():
                QMessageBox.warning(self, "验证失败", "静默期应大于等于检查频率")
                self.tab_widget.setCurrentIndex(1)
                self.silence_period_spin.setFocus()
                return

            # 验证至少选择一种通知方式
            if not any([
                self.email_checkbox.isChecked(),
                self.sms_checkbox.isChecked(),
                self.desktop_checkbox.isChecked(),
                self.sound_checkbox.isChecked(),
                self.webhook_checkbox.isChecked(),
                self.dingtalk_checkbox.isChecked()
            ]):
                QMessageBox.warning(self, "验证失败", "请至少选择一种通知方式")
                self.tab_widget.setCurrentIndex(2)  # 切换到通知设置标签页
                return

            # 验证通知参数
            if self.email_checkbox.isChecked() and not self.email_recipients_edit.text().strip():
                QMessageBox.warning(self, "验证失败", "启用邮件通知时必须设置收件人")
                self.tab_widget.setCurrentIndex(2)
                self.email_recipients_edit.setFocus()
                return

            if self.sms_checkbox.isChecked() and not self.sms_recipients_edit.text().strip():
                QMessageBox.warning(self, "验证失败", "启用短信通知时必须设置收件人")
                self.tab_widget.setCurrentIndex(2)
                self.sms_recipients_edit.setFocus()
                return

            if self.webhook_checkbox.isChecked() and not self.webhook_url_edit.text().strip():
                QMessageBox.warning(self, "验证失败", "启用Webhook通知时必须设置URL")
                self.tab_widget.setCurrentIndex(2)
                self.webhook_url_edit.setFocus()
                return

            if self.dingtalk_checkbox.isChecked() and not self.dingtalk_webhook_url_edit.text().strip():
                QMessageBox.warning(self, "验证失败", "启用钉钉通知时必须设置Webhook URL")
                self.tab_widget.setCurrentIndex(2)
                self.dingtalk_webhook_url_edit.setFocus()
                return

            # 验证消息模板格式（如果有自定义模板）
            template = self.message_template_edit.toPlainText().strip()
            if template:
                required_vars = ['{rule_name}', '{metric}', '{value}', '{threshold}', '{time}']
                missing_vars = [var for var in required_vars if var not in template]
                if missing_vars:
                    reply = QMessageBox.question(
                        self, "模板验证",
                        f"消息模板缺少以下变量：{', '.join(missing_vars)}\n是否继续保存？",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.No:
                        self.tab_widget.setCurrentIndex(2)
                        self.message_template_edit.setFocus()
                        return

            # 收集规则数据
            rule_data = {
                'name': self.rule_name_edit.text().strip(),
                'rule_type': self.rule_type_combo.currentText(),
                'priority': self.priority_combo.currentText(),
                'enabled': self.enabled_checkbox.isChecked(),
                'description': self.description_edit.toPlainText().strip(),

                'metric_name': self.metric_combo.currentText(),
                'operator': self.operator_combo.currentText(),
                'threshold_value': self.threshold_spin.value(),
                'threshold_unit': self.unit_combo.currentText(),
                'duration': self.duration_spin.value(),

                'check_interval': self.check_interval_spin.value(),
                'silence_period': self.silence_period_spin.value(),
                'max_alerts': self.max_alerts_spin.value(),

                'email_notification': self.email_checkbox.isChecked(),
                'sms_notification': self.sms_checkbox.isChecked(),
                'desktop_notification': self.desktop_checkbox.isChecked(),
                'sound_notification': self.sound_checkbox.isChecked(),
                'webhook_notification': self.webhook_checkbox.isChecked(),
                'dingtalk_notification': self.dingtalk_checkbox.isChecked(),

                'email_recipients': self.email_recipients_edit.text().strip(),
                'sms_recipients': self.sms_recipients_edit.text().strip(),
                'webhook_url': self.webhook_url_edit.text().strip(),
                'dingtalk_webhook_url': self.dingtalk_webhook_url_edit.text().strip(),

                'message_template': self.message_template_edit.toPlainText().strip()
            }

            # 如果是编辑模式，保留原有ID
            if self.is_edit_mode and 'id' in self.rule_data:
                rule_data['id'] = self.rule_data['id']

            self.rule_data = rule_data
            self.accept()

        except Exception as e:
            logger.error(f"保存规则失败: {e}")
            QMessageBox.critical(self, "保存失败", f"保存规则时发生错误：{str(e)}")

    def get_rule_data(self) -> Dict:
        """获取规则数据"""
        return self.rule_data
