"""
告警规则编辑对话框

提供完整的告警规则新增和编辑功能
"""

from loguru import logger
from typing import Dict, Optional
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QPushButton, QTextEdit, QLabel, QDialogButtonBox, QMessageBox,
    QTabWidget, QWidget, QSlider, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

logger = logger


class AlertRuleDialog(QDialog):
    """告警规则编辑对话框"""

    rule_saved = pyqtSignal(dict)  # 规则保存信号

    def __init__(self, parent=None, rule_data: Optional[Dict] = None):
        super().__init__(parent)
        self.rule_data = rule_data or {}
        self.is_edit_mode = bool(rule_data)

        self.setWindowTitle("编辑告警规则" if self.is_edit_mode else "新增告警规则")
        self.setModal(True)
        self.resize(600, 500)

        self.init_ui()
        self.load_rule_data()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 创建标签页
        self.tab_widget = QTabWidget()

        # 基本信息标签页
        self.basic_tab = self.create_basic_tab()
        self.tab_widget.addTab(self.basic_tab, "基本信息")

        # 条件设置标签页
        self.condition_tab = self.create_condition_tab()
        self.tab_widget.addTab(self.condition_tab, "触发条件")

        # 通知设置标签页
        self.notification_tab = self.create_notification_tab()
        self.tab_widget.addTab(self.notification_tab, "通知设置")

        layout.addWidget(self.tab_widget)

        # 按钮区域
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal
        )
        button_box.accepted.connect(self.accept_rule)
        button_box.rejected.connect(self.reject)

        # 添加测试按钮
        self.test_button = QPushButton("测试规则")
        self.test_button.clicked.connect(self.test_rule)
        button_box.addButton(self.test_button, QDialogButtonBox.ActionRole)

        layout.addWidget(button_box)

    def create_basic_tab(self) -> QWidget:
        """创建基本信息标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 基本信息组
        basic_group = QGroupBox("规则基本信息")
        basic_layout = QFormLayout()

        # 规则名称
        self.rule_name = QLineEdit()
        self.rule_name.setPlaceholderText("输入规则名称")
        basic_layout.addRow("规则名称*:", self.rule_name)

        # 规则类型
        self.rule_type = QComboBox()
        self.rule_type.addItems([
            "系统资源", "业务逻辑", "系统健康", "性能指标",
            "数据质量", "安全事件", "自定义"
        ])
        basic_layout.addRow("规则类型:", self.rule_type)

        # 优先级
        self.priority = QComboBox()
        self.priority.addItems(["低", "中", "高", "紧急"])
        self.priority.setCurrentText("中")
        basic_layout.addRow("优先级:", self.priority)

        # 规则状态
        self.enabled = QCheckBox("启用此规则")
        self.enabled.setChecked(True)
        basic_layout.addRow("", self.enabled)

        # 规则描述
        self.description = QTextEdit()
        self.description.setMaximumHeight(80)
        self.description.setPlaceholderText("输入规则描述...")
        basic_layout.addRow("规则描述:", self.description)

        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)

        # 分类标签
        tags_group = QGroupBox("分类标签")
        tags_layout = QFormLayout()

        self.tags = QLineEdit()
        self.tags.setPlaceholderText("多个标签用逗号分隔，如：CPU,内存,性能")
        tags_layout.addRow("标签:", self.tags)

        tags_group.setLayout(tags_layout)
        layout.addWidget(tags_group)

        layout.addStretch()
        return tab

    def create_condition_tab(self) -> QWidget:
        """创建条件设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 监控指标组
        metric_group = QGroupBox("监控指标")
        metric_layout = QFormLayout()

        # 指标类型
        self.metric_type = QComboBox()
        self.metric_type.addItems([
            "CPU使用率", "内存使用率", "磁盘使用率", "网络流量",
            "响应时间", "错误率", "吞吐量", "连接数", "自定义指标"
        ])
        self.metric_type.currentTextChanged.connect(self.on_metric_type_changed)
        metric_layout.addRow("监控指标:", self.metric_type)

        # 比较操作符
        self.operator = QComboBox()
        self.operator.addItems([">", ">=", "<", "<=", "==", "!="])
        metric_layout.addRow("比较操作:", self.operator)

        # 阈值设置
        threshold_layout = QHBoxLayout()
        self.threshold_value = QDoubleSpinBox()
        self.threshold_value.setRange(0, 999999)
        self.threshold_value.setDecimals(2)
        threshold_layout.addWidget(self.threshold_value)

        self.threshold_unit = QComboBox()
        self.threshold_unit.addItems(["%", "MB", "GB", "ms", "s", "次/秒", "个"])
        threshold_layout.addWidget(self.threshold_unit)

        metric_layout.addRow("阈值:", threshold_layout)

        # 持续时间
        self.duration = QSpinBox()
        self.duration.setRange(1, 3600)
        self.duration.setValue(60)
        self.duration.setSuffix("秒")
        metric_layout.addRow("持续时间:", self.duration)

        metric_group.setLayout(metric_layout)
        layout.addWidget(metric_group)

        # 高级条件组
        advanced_group = QGroupBox("高级条件")
        advanced_layout = QFormLayout()

        # 检查频率
        self.check_interval = QSpinBox()
        self.check_interval.setRange(10, 3600)
        self.check_interval.setValue(60)
        self.check_interval.setSuffix("秒")
        advanced_layout.addRow("检查频率:", self.check_interval)

        # 静默期
        self.silence_period = QSpinBox()
        self.silence_period.setRange(0, 86400)
        self.silence_period.setValue(300)
        self.silence_period.setSuffix("秒")
        advanced_layout.addRow("静默期:", self.silence_period)

        # 最大告警次数
        self.max_alerts = QSpinBox()
        self.max_alerts.setRange(1, 100)
        self.max_alerts.setValue(10)
        advanced_layout.addRow("最大告警次数:", self.max_alerts)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        layout.addStretch()
        return tab

    def create_notification_tab(self) -> QWidget:
        """创建通知设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 通知方式组
        method_group = QGroupBox("通知方式")
        method_layout = QFormLayout()

        self.email_notify = QCheckBox("邮件通知")
        self.email_notify.setChecked(True)
        method_layout.addRow("", self.email_notify)

        self.sms_notify = QCheckBox("短信通知")
        method_layout.addRow("", self.sms_notify)

        self.webhook_notify = QCheckBox("Webhook通知")
        method_layout.addRow("", self.webhook_notify)

        self.dingtalk_notify = QCheckBox("钉钉通知")
        method_layout.addRow("", self.dingtalk_notify)

        self.desktop_notify = QCheckBox("桌面通知")
        self.desktop_notify.setChecked(True)
        method_layout.addRow("", self.desktop_notify)

        self.sound_notify = QCheckBox("声音提醒")
        method_layout.addRow("", self.sound_notify)

        method_group.setLayout(method_layout)
        layout.addWidget(method_group)

        # 收件人设置组
        recipients_group = QGroupBox("收件人设置")
        recipients_layout = QFormLayout()

        self.email_recipients = QLineEdit()
        self.email_recipients.setPlaceholderText("多个邮箱用逗号分隔")
        recipients_layout.addRow("邮件收件人:", self.email_recipients)

        self.sms_recipients = QLineEdit()
        self.sms_recipients.setPlaceholderText("多个手机号用逗号分隔")
        recipients_layout.addRow("短信收件人:", self.sms_recipients)

        self.webhook_url = QLineEdit()
        self.webhook_url.setPlaceholderText("Webhook URL")
        recipients_layout.addRow("Webhook URL:", self.webhook_url)

        self.dingtalk_webhook_url = QLineEdit()
        self.dingtalk_webhook_url.setPlaceholderText("钉钉Webhook URL")
        recipients_layout.addRow("钉钉Webhook URL:", self.dingtalk_webhook_url)

        recipients_group.setLayout(recipients_layout)
        layout.addWidget(recipients_group)

        # 消息模板组
        template_group = QGroupBox("消息模板")
        template_layout = QFormLayout()

        self.message_template = QTextEdit()
        self.message_template.setMaximumHeight(100)
        self.message_template.setPlaceholderText(
            "告警消息模板，支持变量：\n"
            "{rule_name} - 规则名称\n"
            "{metric_type} - 指标类型\n"
            "{current_value} - 当前值\n"
            "{threshold_value} - 阈值\n"
            "{timestamp} - 时间戳"
        )
        self.message_template.setText(
            "【FactorWeave-Quant】告警通知\n"
            "规则：{rule_name}\n"
            "指标：{metric_type}\n"
            "当前值：{current_value}\n"
            "阈值：{threshold_value}\n"
            "时间：{timestamp}"
        )
        template_layout.addRow("消息模板:", self.message_template)

        template_group.setLayout(template_layout)
        layout.addWidget(template_group)

        layout.addStretch()
        return tab

    def on_metric_type_changed(self, metric_type: str):
        """指标类型变化时更新单位"""
        unit_map = {
            "CPU使用率": "%",
            "内存使用率": "%",
            "磁盘使用率": "%",
            "网络流量": "MB",
            "响应时间": "ms",
            "错误率": "%",
            "吞吐量": "次/秒",
            "连接数": "个"
        }

        unit = unit_map.get(metric_type, "%")
        index = self.threshold_unit.findText(unit)
        if index >= 0:
            self.threshold_unit.setCurrentIndex(index)

    def load_rule_data(self):
        """加载规则数据"""
        if not self.rule_data:
            return

        try:
            # 基本信息
            self.rule_name.setText(self.rule_data.get('name', ''))
            self.rule_type.setCurrentText(self.rule_data.get('type', '系统资源'))
            self.priority.setCurrentText(self.rule_data.get('priority', '中'))
            self.enabled.setChecked(self.rule_data.get('enabled', True))
            self.description.setText(self.rule_data.get('description', ''))
            self.tags.setText(self.rule_data.get('tags', ''))

            # 条件设置
            conditions = self.rule_data.get('conditions', {})
            self.metric_type.setCurrentText(conditions.get('metric_type', 'CPU使用率'))
            self.operator.setCurrentText(conditions.get('operator', '>'))
            self.threshold_value.setValue(conditions.get('threshold_value', 80.0))
            self.threshold_unit.setCurrentText(conditions.get('threshold_unit', '%'))
            self.duration.setValue(conditions.get('duration', 60))
            self.check_interval.setValue(conditions.get('check_interval', 60))
            self.silence_period.setValue(conditions.get('silence_period', 300))
            self.max_alerts.setValue(conditions.get('max_alerts', 10))

            # 通知设置
            notifications = self.rule_data.get('notifications', {})
            self.email_notify.setChecked(notifications.get('email_notify', True))
            self.sms_notify.setChecked(notifications.get('sms_notify', False))
            self.webhook_notify.setChecked(notifications.get('webhook_notify', False))
            self.dingtalk_notify.setChecked(notifications.get('dingtalk_notify', False))
            self.desktop_notify.setChecked(notifications.get('desktop_notify', True))
            self.sound_notify.setChecked(notifications.get('sound_notify', False))
            self.email_recipients.setText(notifications.get('email_recipients', ''))
            self.sms_recipients.setText(notifications.get('sms_recipients', ''))
            self.webhook_url.setText(notifications.get('webhook_url', ''))
            self.dingtalk_webhook_url.setText(notifications.get('dingtalk_webhook_url', ''))
            self.message_template.setText(notifications.get('message_template', ''))

        except Exception as e:
            logger.error(f"加载规则数据失败: {e}")

    def get_rule_data(self) -> Dict:
        """获取规则数据"""
        return {
            'name': self.rule_name.text(),
            'type': self.rule_type.currentText(),
            'priority': self.priority.currentText(),
            'enabled': self.enabled.isChecked(),
            'description': self.description.toPlainText(),
            'tags': self.tags.text(),
            'conditions': {
                'metric_type': self.metric_type.currentText(),
                'operator': self.operator.currentText(),
                'threshold_value': self.threshold_value.value(),
                'threshold_unit': self.threshold_unit.currentText(),
                'duration': self.duration.value(),
                'check_interval': self.check_interval.value(),
                'silence_period': self.silence_period.value(),
                'max_alerts': self.max_alerts.value()
            },
            'notifications': {
                'email_notify': self.email_notify.isChecked(),
                'sms_notify': self.sms_notify.isChecked(),
                'webhook_notify': self.webhook_notify.isChecked(),
                'dingtalk_notify': self.dingtalk_notify.isChecked(),
                'desktop_notify': self.desktop_notify.isChecked(),
                'sound_notify': self.sound_notify.isChecked(),
                'email_recipients': self.email_recipients.text(),
                'sms_recipients': self.sms_recipients.text(),
                'webhook_url': self.webhook_url.text(),
                'dingtalk_webhook_url': self.dingtalk_webhook_url.text(),
                'message_template': self.message_template.toPlainText()
            }
        }

    def validate_rule(self) -> bool:
        """验证规则数据"""
        if not self.rule_name.text().strip():
            QMessageBox.warning(self, "验证失败", "请输入规则名称")
            self.tab_widget.setCurrentIndex(0)
            self.rule_name.setFocus()
            return False

        if self.threshold_value.value() <= 0:
            QMessageBox.warning(self, "验证失败", "阈值必须大于0")
            self.tab_widget.setCurrentIndex(1)
            self.threshold_value.setFocus()
            return False

        if self.email_notify.isChecked() and not self.email_recipients.text().strip():
            QMessageBox.warning(self, "验证失败", "启用邮件通知时必须设置收件人")
            self.tab_widget.setCurrentIndex(2)
            self.email_recipients.setFocus()
            return False

        if self.sms_notify.isChecked() and not self.sms_recipients.text().strip():
            QMessageBox.warning(self, "验证失败", "启用短信通知时必须设置收件人")
            self.tab_widget.setCurrentIndex(2)
            self.sms_recipients.setFocus()
            return False

        if self.webhook_notify.isChecked() and not self.webhook_url.text().strip():
            QMessageBox.warning(self, "验证失败", "启用Webhook通知时必须设置URL")
            self.tab_widget.setCurrentIndex(2)
            self.webhook_url.setFocus()
            return False

        if self.dingtalk_notify.isChecked() and not self.dingtalk_webhook_url.text().strip():
            QMessageBox.warning(self, "验证失败", "启用钉钉通知时必须设置Webhook URL")
            self.tab_widget.setCurrentIndex(2)
            self.dingtalk_webhook_url.setFocus()
            return False

        return True

    def test_rule(self):
        """测试规则"""
        try:
            if not self.validate_rule():
                return

            rule_data = self.get_rule_data()

            # 模拟测试数据
            test_data = {
                'rule_name': rule_data['name'],
                'metric_type': rule_data['conditions']['metric_type'],
                'current_value': rule_data['conditions']['threshold_value'] + 10,
                'threshold_value': rule_data['conditions']['threshold_value'],
                'timestamp': '2024-01-15 10:30:00'
            }

            # 生成测试消息
            template = rule_data['notifications']['message_template']
            test_message = template.format(**test_data)

            QMessageBox.information(
                self, "规则测试",
                f"规则配置正确！\n\n模拟告警消息：\n{test_message}"
            )

        except Exception as e:
            QMessageBox.critical(self, "测试失败", f"规则测试失败: {e}")

    def accept_rule(self):
        """接受规则"""
        if self.validate_rule():
            rule_data = self.get_rule_data()
            self.rule_saved.emit(rule_data)
            self.accept()


class AlertRuleListWidget(QWidget):
    """告警规则列表组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        self.add_rule_btn = QPushButton("新增规则")
        self.add_rule_btn.clicked.connect(self.add_rule)
        toolbar_layout.addWidget(self.add_rule_btn)

        self.edit_rule_btn = QPushButton("编辑规则")
        self.edit_rule_btn.clicked.connect(self.edit_rule)
        toolbar_layout.addWidget(self.edit_rule_btn)

        self.delete_rule_btn = QPushButton("删除规则")
        self.delete_rule_btn.clicked.connect(self.delete_rule)
        toolbar_layout.addWidget(self.delete_rule_btn)

        self.copy_rule_btn = QPushButton("复制规则")
        self.copy_rule_btn.clicked.connect(self.copy_rule)
        toolbar_layout.addWidget(self.copy_rule_btn)

        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)

        # 规则列表（这里可以使用QTreeWidget或QTableWidget）
        from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem
        self.rules_tree = QTreeWidget()
        self.rules_tree.setHeaderLabels(["规则名称", "类型", "状态", "优先级", "阈值", "最后修改"])
        self.rules_tree.itemDoubleClicked.connect(self.edit_rule)
        layout.addWidget(self.rules_tree)

    def add_rule(self):
        """添加规则"""
        dialog = AlertRuleDialog(self)
        dialog.rule_saved.connect(self.on_rule_saved)
        dialog.exec_()

    def edit_rule(self):
        """编辑规则"""
        current_item = self.rules_tree.currentItem()
        if not current_item:
            QMessageBox.information(self, "提示", "请选择要编辑的规则")
            return

        # 获取规则数据（这里需要根据实际数据结构调整）
        rule_data = {}  # 从current_item获取规则数据

        dialog = AlertRuleDialog(self, rule_data)
        dialog.rule_saved.connect(self.on_rule_updated)
        dialog.exec_()

    def delete_rule(self):
        """删除规则"""
        current_item = self.rules_tree.currentItem()
        if not current_item:
            QMessageBox.information(self, "提示", "请选择要删除的规则")
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除规则 '{current_item.text(0)}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.rules_tree.takeTopLevelItem(
                self.rules_tree.indexOfTopLevelItem(current_item)
            )

    def copy_rule(self):
        """复制规则"""
        current_item = self.rules_tree.currentItem()
        if not current_item:
            QMessageBox.information(self, "提示", "请选择要复制的规则")
            return

        # 获取规则数据并创建副本
        rule_data = {}  # 从current_item获取规则数据
        rule_data['name'] = f"{rule_data.get('name', '未命名规则')} - 副本"

        dialog = AlertRuleDialog(self, rule_data)
        dialog.rule_saved.connect(self.on_rule_saved)
        dialog.exec_()

    def on_rule_saved(self, rule_data: Dict):
        """规则保存处理"""
        # 添加到树形控件
        item = QTreeWidgetItem([
            rule_data['name'],
            rule_data['type'],
            "启用" if rule_data['enabled'] else "禁用",
            rule_data['priority'],
            f"{rule_data['conditions']['threshold_value']}{rule_data['conditions']['threshold_unit']}",
            "刚刚"
        ])
        self.rules_tree.addTopLevelItem(item)

    def on_rule_updated(self, rule_data: Dict):
        """规则更新处理"""
        current_item = self.rules_tree.currentItem()
        if current_item:
            current_item.setText(0, rule_data['name'])
            current_item.setText(1, rule_data['type'])
            current_item.setText(2, "启用" if rule_data['enabled'] else "禁用")
            current_item.setText(3, rule_data['priority'])
            current_item.setText(4, f"{rule_data['conditions']['threshold_value']}{rule_data['conditions']['threshold_unit']}")
            current_item.setText(5, "刚刚")
