#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
外部告警渠道配置对话框

提供外部告警渠道的配置和管理功能
"""

from loguru import logger
from typing import Dict, Optional, List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QPushButton, QTextEdit, QLabel, QDialogButtonBox, QMessageBox,
    QTabWidget, QWidget, QListWidget, QListWidgetItem, QSplitter, QFileDialog
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

logger = logger


class EmailChannelConfigWidget(QWidget):
    """邮件告警渠道配置组件"""

    def __init__(self, config: Dict = None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self.init_ui()
        self.load_config()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # SMTP配置组
        smtp_group = QGroupBox("SMTP服务器配置")
        smtp_layout = QFormLayout()

        self.smtp_server = QLineEdit()
        self.smtp_server.setPlaceholderText("例如: smtp.gmail.com")
        smtp_layout.addRow("SMTP服务器*:", self.smtp_server)

        self.smtp_port = QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(587)
        smtp_layout.addRow("SMTP端口*:", self.smtp_port)

        self.use_tls = QCheckBox("使用TLS加密")
        self.use_tls.setChecked(True)
        smtp_layout.addRow("", self.use_tls)

        smtp_group.setLayout(smtp_layout)
        layout.addWidget(smtp_group)

        # 账户配置组
        account_group = QGroupBox("账户配置")
        account_layout = QFormLayout()

        self.username = QLineEdit()
        self.username.setPlaceholderText("邮箱地址")
        account_layout.addRow("用户名*:", self.username)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("邮箱密码或应用专用密码")
        account_layout.addRow("密码*:", self.password)

        self.from_email = QLineEdit()
        self.from_email.setPlaceholderText("发件人邮箱")
        account_layout.addRow("发件人邮箱*:", self.from_email)

        self.from_name = QLineEdit()
        self.from_name.setText("BettaFish监控系统")
        account_layout.addRow("发件人名称:", self.from_name)

        account_group.setLayout(account_layout)
        layout.addWidget(account_group)

        # 收件人配置组
        recipients_group = QGroupBox("收件人配置")
        recipients_layout = QFormLayout()

        self.to_emails = QLineEdit()
        self.to_emails.setPlaceholderText("多个邮箱用逗号分隔")
        recipients_layout.addRow("收件人邮箱*:", self.to_emails)

        recipients_group.setLayout(recipients_layout)
        layout.addWidget(recipients_group)

        layout.addStretch()

    def load_config(self):
        """加载配置"""
        self.smtp_server.setText(self.config.get('smtp_server', ''))
        self.smtp_port.setValue(self.config.get('smtp_port', 587))
        self.use_tls.setChecked(self.config.get('use_tls', True))
        self.username.setText(self.config.get('username', ''))
        self.password.setText(self.config.get('password', ''))
        self.from_email.setText(self.config.get('from_email', ''))
        self.from_name.setText(self.config.get('from_name', 'BettaFish监控系统'))
        self.to_emails.setText(self.config.get('to_emails', ''))

    def get_config(self) -> Dict:
        """获取配置"""
        return {
            'smtp_server': self.smtp_server.text().strip(),
            'smtp_port': self.smtp_port.value(),
            'use_tls': self.use_tls.isChecked(),
            'username': self.username.text().strip(),
            'password': self.password.text(),
            'from_email': self.from_email.text().strip(),
            'from_name': self.from_name.text().strip(),
            'to_emails': [email.strip() for email in self.to_emails.text().split(',') if email.strip()]
        }

    def validate(self) -> bool:
        """验证配置"""
        if not self.smtp_server.text().strip():
            QMessageBox.warning(self, "验证失败", "SMTP服务器不能为空")
            return False
        if not self.username.text().strip():
            QMessageBox.warning(self, "验证失败", "用户名不能为空")
            return False
        if not self.password.text():
            QMessageBox.warning(self, "验证失败", "密码不能为空")
            return False
        if not self.from_email.text().strip():
            QMessageBox.warning(self, "验证失败", "发件人邮箱不能为空")
            return False
        if not self.to_emails.text().strip():
            QMessageBox.warning(self, "验证失败", "收件人邮箱不能为空")
            return False
        return True


class SMSChannelConfigWidget(QWidget):
    """短信告警渠道配置组件"""

    def __init__(self, config: Dict = None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self.init_ui()
        self.load_config()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 服务提供商配置组
        provider_group = QGroupBox("服务提供商")
        provider_layout = QFormLayout()

        self.provider = QComboBox()
        self.provider.addItems(["mock", "tencent", "aliyun", "huawei"])
        provider_layout.addRow("服务提供商:", self.provider)

        provider_group.setLayout(provider_layout)
        layout.addWidget(provider_group)

        # API配置组
        api_group = QGroupBox("API配置")
        api_layout = QFormLayout()

        self.api_key = QLineEdit()
        self.api_key.setPlaceholderText("API密钥")
        api_layout.addRow("API密钥*:", self.api_key)

        self.api_secret = QLineEdit()
        self.api_secret.setEchoMode(QLineEdit.Password)
        self.api_secret.setPlaceholderText("API密钥")
        api_layout.addRow("API密钥*:", self.api_secret)

        self.from_number = QLineEdit()
        self.from_number.setPlaceholderText("发送号码")
        api_layout.addRow("发送号码:", self.from_number)

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        # 收件人配置组
        recipients_group = QGroupBox("收件人配置")
        recipients_layout = QFormLayout()

        self.to_numbers = QLineEdit()
        self.to_numbers.setPlaceholderText("多个手机号用逗号分隔")
        recipients_layout.addRow("收件人号码*:", self.to_numbers)

        self.sign_name = QLineEdit()
        self.sign_name.setText("BettaFish")
        recipients_layout.addRow("签名:", self.sign_name)

        recipients_group.setLayout(recipients_layout)
        layout.addWidget(recipients_group)

        layout.addStretch()

    def load_config(self):
        """加载配置"""
        self.provider.setCurrentText(self.config.get('provider', 'mock'))
        self.api_key.setText(self.config.get('api_key', ''))
        self.api_secret.setText(self.config.get('api_secret', ''))
        self.from_number.setText(self.config.get('from_number', ''))
        self.to_numbers.setText(self.config.get('to_numbers', ''))
        self.sign_name.setText(self.config.get('sign_name', 'BettaFish'))

    def get_config(self) -> Dict:
        """获取配置"""
        return {
            'provider': self.provider.currentText(),
            'api_key': self.api_key.text().strip(),
            'api_secret': self.api_secret.text(),
            'from_number': self.from_number.text().strip(),
            'to_numbers': [num.strip() for num in self.to_numbers.text().split(',') if num.strip()],
            'sign_name': self.sign_name.text().strip()
        }

    def validate(self) -> bool:
        """验证配置"""
        if not self.to_numbers.text().strip():
            QMessageBox.warning(self, "验证失败", "收件人号码不能为空")
            return False
        return True


class WebhookChannelConfigWidget(QWidget):
    """Webhook告警渠道配置组件"""

    def __init__(self, config: Dict = None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self.init_ui()
        self.load_config()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # URL配置组
        url_group = QGroupBox("Webhook配置")
        url_layout = QFormLayout()

        self.webhook_url = QLineEdit()
        self.webhook_url.setPlaceholderText("例如: https://example.com/webhook/alert")
        url_layout.addRow("Webhook URL*:", self.webhook_url)

        self.method = QComboBox()
        self.method.addItems(["POST", "GET", "PUT"])
        url_layout.addRow("请求方法:", self.method)

        self.timeout = QSpinBox()
        self.timeout.setRange(1, 300)
        self.timeout.setValue(10)
        self.timeout.setSuffix(" 秒")
        url_layout.addRow("超时时间:", self.timeout)

        url_group.setLayout(url_layout)
        layout.addWidget(url_group)

        # 重试配置组
        retry_group = QGroupBox("重试配置")
        retry_layout = QFormLayout()

        self.retry_count = QSpinBox()
        self.retry_count.setRange(0, 10)
        self.retry_count.setValue(3)
        retry_layout.addRow("重试次数:", self.retry_count)

        retry_group.setLayout(retry_layout)
        layout.addWidget(retry_group)

        # Headers配置组
        headers_group = QGroupBox("请求头")
        headers_layout = QVBoxLayout()

        self.headers_text = QTextEdit()
        self.headers_text.setMaximumHeight(100)
        self.headers_text.setPlaceholderText(
            "JSON格式的请求头，例如：\n"
            '{\n'
            '  "Content-Type": "application/json",\n'
            '  "Authorization": "Bearer token"\n'
            '}'
        )
        headers_layout.addWidget(self.headers_text)

        headers_group.setLayout(headers_layout)
        layout.addWidget(headers_group)

        layout.addStretch()

    def load_config(self):
        """加载配置"""
        self.webhook_url.setText(self.config.get('webhook_url', ''))
        self.method.setCurrentText(self.config.get('method', 'POST'))
        self.timeout.setValue(self.config.get('timeout', 10))
        self.retry_count.setValue(self.config.get('retry_count', 3))
        headers = self.config.get('headers', {})
        if headers:
            import json
            self.headers_text.setText(json.dumps(headers, indent=2, ensure_ascii=False))

    def get_config(self) -> Dict:
        """获取配置"""
        headers_text = self.headers_text.toPlainText().strip()
        headers = {}
        if headers_text:
            try:
                import json
                headers = json.loads(headers_text)
            except json.JSONDecodeError:
                pass

        return {
            'webhook_url': self.webhook_url.text().strip(),
            'method': self.method.currentText(),
            'timeout': self.timeout.value(),
            'retry_count': self.retry_count.value(),
            'headers': headers
        }

    def validate(self) -> bool:
        """验证配置"""
        if not self.webhook_url.text().strip():
            QMessageBox.warning(self, "验证失败", "Webhook URL不能为空")
            return False
        return True


class DingTalkChannelConfigWidget(QWidget):
    """钉钉告警渠道配置组件"""

    def __init__(self, config: Dict = None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self.init_ui()
        self.load_config()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Webhook配置组
        webhook_group = QGroupBox("钉钉Webhook配置")
        webhook_layout = QFormLayout()

        self.webhook_url = QLineEdit()
        self.webhook_url.setPlaceholderText("钉钉机器人Webhook URL")
        webhook_layout.addRow("Webhook URL*:", self.webhook_url)

        self.secret = QLineEdit()
        self.secret.setEchoMode(QLineEdit.Password)
        self.secret.setPlaceholderText("加签密钥（可选）")
        webhook_layout.addRow("加签密钥:", self.secret)

        webhook_group.setLayout(webhook_layout)
        layout.addWidget(webhook_group)

        # @配置组
        at_group = QGroupBox("@配置")
        at_layout = QFormLayout()

        self.at_mobiles = QLineEdit()
        self.at_mobiles.setPlaceholderText("多个手机号用逗号分隔")
        at_layout.addRow("@手机号:", self.at_mobiles)

        self.is_at_all = QCheckBox("@所有人")
        at_layout.addRow("", self.is_at_all)

        at_group.setLayout(at_layout)
        layout.addWidget(at_group)

        layout.addStretch()

    def load_config(self):
        """加载配置"""
        self.webhook_url.setText(self.config.get('webhook_url', ''))
        self.secret.setText(self.config.get('secret', ''))
        self.at_mobiles.setText(self.config.get('at_mobiles', ''))
        self.is_at_all.setChecked(self.config.get('is_at_all', False))

    def get_config(self) -> Dict:
        """获取配置"""
        return {
            'webhook_url': self.webhook_url.text().strip(),
            'secret': self.secret.text(),
            'at_mobiles': [num.strip() for num in self.at_mobiles.text().split(',') if num.strip()],
            'is_at_all': self.is_at_all.isChecked()
        }

    def validate(self) -> bool:
        """验证配置"""
        if not self.webhook_url.text().strip():
            QMessageBox.warning(self, "验证失败", "Webhook URL不能为空")
            return False
        return True


class ExternalAlertChannelConfigDialog(QDialog):
    """外部告警渠道配置对话框"""

    channel_configured = pyqtSignal(str, dict)  # channel_type, config

    def __init__(self, channel_type: str = "email", config: Dict = None, parent=None):
        super().__init__(parent)
        self.channel_type = channel_type
        self.config = config or {}
        self.init_ui()
        self.load_config()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"配置{self._get_channel_name()}告警渠道")
        self.setModal(True)
        self.resize(600, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 创建配置组件
        self.config_widget = self._create_config_widget()
        layout.addWidget(self.config_widget)

        # 按钮区域
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal
        )
        button_box.accepted.connect(self.accept_config)
        button_box.rejected.connect(self.reject)

        # 添加测试按钮
        self.test_button = QPushButton("测试连接")
        self.test_button.clicked.connect(self.test_connection)
        button_box.addButton(self.test_button, QDialogButtonBox.ActionRole)

        layout.addWidget(button_box)

    def _get_channel_name(self) -> str:
        """获取渠道名称"""
        names = {
            'email': '邮件',
            'sms': '短信',
            'webhook': 'Webhook',
            'dingtalk': '钉钉'
        }
        return names.get(self.channel_type, self.channel_type)

    def _create_config_widget(self) -> QWidget:
        """创建配置组件"""
        if self.channel_type == 'email':
            return EmailChannelConfigWidget(self.config, self)
        elif self.channel_type == 'sms':
            return SMSChannelConfigWidget(self.config, self)
        elif self.channel_type == 'webhook':
            return WebhookChannelConfigWidget(self.config, self)
        elif self.channel_type == 'dingtalk':
            return DingTalkChannelConfigWidget(self.config, self)
        else:
            return QWidget()

    def load_config(self):
        """加载配置"""
        pass

    def test_connection(self):
        """测试连接"""
        if not self.config_widget.validate():
            return

        QMessageBox.information(
            self,
            "测试连接",
            f"测试{self._get_channel_name()}告警渠道连接...\n\n"
            "注意：此功能需要实际的服务器配置才能正常工作。\n"
            "当前仅验证配置格式是否正确。"
        )

    def accept_config(self):
        """接受配置"""
        if self.config_widget.validate():
            config = self.config_widget.get_config()
            self.channel_configured.emit(self.channel_type, config)
            self.accept()


class ExternalAlertChannelManagerDialog(QDialog):
    """外部告警渠道管理对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.channel_configs = {}
        self.config_persistence = None
        self.init_ui()
        self.load_channels()
        self._init_config_persistence()

    def _init_config_persistence(self):
        """初始化配置持久化"""
        try:
            from core.services.external_alert_config_persistence import get_alert_config_persistence
            self.config_persistence = get_alert_config_persistence()
            logger.info("外部告警渠道配置持久化初始化成功")
        except Exception as e:
            logger.error(f"外部告警渠道配置持久化初始化失败: {e}")

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("外部告警渠道管理")
        self.setModal(True)
        self.resize(800, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：渠道列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        left_label = QLabel("告警渠道")
        left_label.setFont(QFont("Arial", 10, QFont.Bold))
        left_layout.addWidget(left_label)

        self.channel_list = QListWidget()
        self.channel_list.itemClicked.connect(self.on_channel_selected)
        left_layout.addWidget(self.channel_list)

        splitter.addWidget(left_widget)

        # 右侧：配置区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        right_label = QLabel("配置信息")
        right_label.setFont(QFont("Arial", 10, QFont.Bold))
        right_layout.addWidget(right_label)

        self.config_info = QLabel("请选择一个告警渠道进行配置")
        self.config_info.setWordWrap(True)
        self.config_info.setStyleSheet("color: #7f8c8d; padding: 20px;")
        right_layout.addWidget(self.config_info)

        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        # 按钮区域
        button_layout = QHBoxLayout()

        self.add_button = QPushButton("添加渠道")
        self.add_button.clicked.connect(self.add_channel)
        button_layout.addWidget(self.add_button)

        self.edit_button = QPushButton("编辑渠道")
        self.edit_button.clicked.connect(self.edit_channel)
        self.edit_button.setEnabled(False)
        button_layout.addWidget(self.edit_button)

        self.delete_button = QPushButton("删除渠道")
        self.delete_button.clicked.connect(self.delete_channel)
        self.delete_button.setEnabled(False)
        button_layout.addWidget(self.delete_button)

        button_layout.addStretch()

        self.export_button = QPushButton("导出配置")
        self.export_button.clicked.connect(self.export_config)
        button_layout.addWidget(self.export_button)

        self.import_button = QPushButton("导入配置")
        self.import_button.clicked.connect(self.import_config)
        button_layout.addWidget(self.import_button)

        layout.addLayout(button_layout)

        # 关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

    def load_channels(self):
        """加载渠道列表"""
        self.channel_list.clear()

        channels = [
            ('email', '邮件', '📧'),
            ('sms', '短信', '📱'),
            ('webhook', 'Webhook', '🔗'),
            ('dingtalk', '钉钉', '💬')
        ]

        for channel_type, channel_name, icon in channels:
            item = QListWidgetItem(f"{icon} {channel_name}")
            item.setData(Qt.UserRole, channel_type)
            self.channel_list.addItem(item)

    def on_channel_selected(self, item):
        """渠道选择事件"""
        channel_type = item.data(Qt.UserRole)
        self.edit_button.setEnabled(True)
        self.delete_button.setEnabled(True)

        if channel_type in self.channel_configs:
            config = self.channel_configs[channel_type]
            config_text = f"{channel_type.upper()} 渠道已配置\n\n"
            for key, value in config.items():
                if 'password' in key or 'secret' in key or 'key' in key:
                    value = '***'
                config_text += f"{key}: {value}\n"
            self.config_info.setText(config_text)
        else:
            self.config_info.setText(f"{channel_type.upper()} 渠道未配置\n\n点击'编辑渠道'按钮进行配置")

    def add_channel(self):
        """添加渠道"""
        current_item = self.channel_list.currentItem()
        if current_item:
            channel_type = current_item.data(Qt.UserRole)
            self.edit_channel()

    def edit_channel(self):
        """编辑渠道"""
        current_item = self.channel_list.currentItem()
        if not current_item:
            return

        channel_type = current_item.data(Qt.UserRole)
        config = self.channel_configs.get(channel_type, {})

        dialog = ExternalAlertChannelConfigDialog(channel_type, config, self)
        dialog.channel_configured.connect(self.on_channel_configured)
        dialog.exec_()

    def on_channel_configured(self, channel_type: str, config: dict):
        """渠道配置完成"""
        self.channel_configs[channel_type] = config

        # 保存到持久化
        if self.config_persistence:
            self.config_persistence.save_channel_config(channel_type, config)

        self.on_channel_selected(self.channel_list.currentItem())

    def delete_channel(self):
        """删除渠道"""
        current_item = self.channel_list.currentItem()
        if not current_item:
            return

        channel_type = current_item.data(Qt.UserRole)

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除{channel_type.upper()}渠道的配置吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if channel_type in self.channel_configs:
                del self.channel_configs[channel_type]

                # 从持久化删除
                if self.config_persistence:
                    self.config_persistence.delete_channel_config(channel_type)

            self.on_channel_selected(current_item)

    def export_config(self):
        """导出配置"""
        try:
            from PyQt5.QtWidgets import QFileDialog

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出外部告警渠道配置",
                "",
                "JSON文件 (*.json);;所有文件 (*.*)"
            )

            if file_path:
                if self.config_persistence:
                    success = self.config_persistence.export_config(file_path)
                    if success:
                        QMessageBox.information(
                            self,
                            "导出成功",
                            f"配置已成功导出到:\n{file_path}"
                        )
                    else:
                        QMessageBox.warning(
                            self,
                            "导出失败",
                            "配置导出失败，请查看日志了解详情"
                        )
                else:
                    QMessageBox.warning(
                        self,
                        "导出失败",
                        "配置持久化未初始化"
                    )

        except Exception as e:
            logger.error(f"导出配置失败: {e}")
            QMessageBox.warning(
                self,
                "导出失败",
                f"导出配置时发生错误:\n{e}"
            )

    def import_config(self):
        """导入配置"""
        try:
            from PyQt5.QtWidgets import QFileDialog

            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "导入外部告警渠道配置",
                "",
                "JSON文件 (*.json);;所有文件 (*.*)"
            )

            if file_path:
                if self.config_persistence:
                    success = self.config_persistence.import_config(file_path)
                    if success:
                        QMessageBox.information(
                            self,
                            "导入成功",
                            "配置已成功导入，请刷新查看"
                        )
                        # 重新加载配置
                        self.load_channels()
                    else:
                        QMessageBox.warning(
                            self,
                            "导入失败",
                            "配置导入失败，请查看日志了解详情"
                        )
                else:
                    QMessageBox.warning(
                        self,
                        "导入失败",
                        "配置持久化未初始化"
                    )

        except Exception as e:
            logger.error(f"导入配置失败: {e}")
            QMessageBox.warning(
                self,
                "导入失败",
                f"导入配置时发生错误:\n{e}"
            )

    def get_channel_configs(self) -> Dict:
        """获取所有渠道配置"""
        return self.channel_configs
