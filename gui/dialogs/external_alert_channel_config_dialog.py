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


class SoundChannelConfigWidget(QWidget):
    """声音告警渠道配置组件"""

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

        basic_group = QGroupBox("基本设置")
        basic_layout = QFormLayout()

        self.use_system_sound = QCheckBox("使用系统默认声音")
        self.use_system_sound.setChecked(True)
        self.use_system_sound.stateChanged.connect(self._on_use_system_sound_changed)
        basic_layout.addRow("", self.use_system_sound)

        self.volume_slider = QDoubleSpinBox()
        self.volume_slider.setRange(0.0, 1.0)
        self.volume_slider.setSingleStep(0.1)
        self.volume_slider.setValue(0.8)
        self.volume_slider.setDecimals(1)
        basic_layout.addRow("音量:", self.volume_slider)

        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)

        sound_type_group = QGroupBox("声音类型")
        sound_type_layout = QFormLayout()

        self.sound_type = QComboBox()
        self.sound_type.addItems([
            "默认提示音",
            "紧急告警音",
            "警告提示音",
            "信息提示音",
            "自定义声音文件"
        ])
        sound_type_layout.addRow("声音类型:", self.sound_type)

        self.custom_sound_path = QLineEdit()
        self.custom_sound_path.setPlaceholderText("选择自定义声音文件 (.wav, .mp3)")
        self.custom_sound_path.setEnabled(False)
        sound_type_layout.addRow("自定义文件:", self.custom_sound_path)

        self.browse_button = QPushButton("浏览...")
        self.browse_button.setEnabled(False)
        self.browse_button.clicked.connect(self._browse_sound_file)
        sound_type_layout.addRow("", self.browse_button)

        sound_type_group.setLayout(sound_type_layout)
        layout.addWidget(sound_type_group)

        alert_level_group = QGroupBox("告警级别声音配置")
        alert_level_layout = QFormLayout()

        self.critical_sound = QComboBox()
        self.critical_sound.addItems(["高频急促音", "双音提示", "持续警报"])
        alert_level_layout.addRow("严重告警:", self.critical_sound)

        self.error_sound = QComboBox()
        self.error_sound.addItems(["中频提示音", "单音提示", "短促音"])
        alert_level_layout.addRow("错误告警:", self.error_sound)

        self.warning_sound = QComboBox()
        self.warning_sound.addItems(["低频提示音", "柔和提示", "轻微音"])
        alert_level_layout.addRow("警告告警:", self.warning_sound)

        self.info_sound = QComboBox()
        self.info_sound.addItems(["轻微提示音", "静音", "默认音"])
        alert_level_layout.addRow("信息告警:", self.info_sound)

        alert_level_group.setLayout(alert_level_layout)
        layout.addWidget(alert_level_group)

        test_group = QGroupBox("测试")
        test_layout = QHBoxLayout()

        self.test_button = QPushButton("🔊 测试声音")
        self.test_button.clicked.connect(self._test_sound)
        test_layout.addWidget(self.test_button)

        test_layout.addStretch()
        test_group.setLayout(test_layout)
        layout.addWidget(test_group)

        layout.addStretch()
        
        self.sound_type.currentTextChanged.connect(self._on_sound_type_changed)
        self._on_use_system_sound_changed(self.use_system_sound.checkState())

    def _on_use_system_sound_changed(self, state):
        """系统声音选项变化"""
        use_system = state == Qt.Checked
        self.sound_type.setEnabled(not use_system)
        self.custom_sound_path.setEnabled(not use_system and self.sound_type.currentText() == "自定义声音文件")
        self.browse_button.setEnabled(not use_system and self.sound_type.currentText() == "自定义声音文件")
        self.critical_sound.setEnabled(not use_system)
        self.error_sound.setEnabled(not use_system)
        self.warning_sound.setEnabled(not use_system)
        self.info_sound.setEnabled(not use_system)

    def _on_sound_type_changed(self, text):
        """声音类型变化"""
        is_custom = text == "自定义声音文件"
        use_system = self.use_system_sound.isChecked()
        self.custom_sound_path.setEnabled(is_custom and not use_system)
        self.browse_button.setEnabled(is_custom and not use_system)

    def _browse_sound_file(self):
        """浏览声音文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择声音文件",
            "",
            "声音文件 (*.wav *.mp3 *.ogg);;所有文件 (*.*)"
        )
        if file_path:
            self.custom_sound_path.setText(file_path)

    def _test_sound(self):
        """测试声音"""
        try:
            import platform
            import threading
            
            def play_test_sound():
                try:
                    system = platform.system()
                    if system == "Windows":
                        try:
                            import winsound
                            winsound.Beep(1000, 500)
                        except:
                            pass
                    elif system == "Darwin":
                        import subprocess
                        subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'], check=False)
                    elif system == "Linux":
                        import subprocess
                        subprocess.run(['aplay', '-q', '/usr/share/sounds/alsa/Front_Center.wav'], check=False)
                except Exception as e:
                    logger.warning(f"测试声音播放失败: {e}")
            
            thread = threading.Thread(target=play_test_sound, daemon=True)
            thread.start()
            
            QMessageBox.information(self, "测试声音", "正在播放测试声音...")
            
        except Exception as e:
            QMessageBox.warning(self, "测试失败", f"播放测试声音失败: {e}")

    def load_config(self):
        """加载配置"""
        self.use_system_sound.setChecked(self.config.get('use_system_sound', True))
        self.volume_slider.setValue(self.config.get('volume', 0.8))
        self.sound_type.setCurrentText(self.config.get('sound_type', '默认提示音'))
        self.custom_sound_path.setText(self.config.get('custom_sound_path', ''))
        self.critical_sound.setCurrentText(self.config.get('critical_sound', '高频急促音'))
        self.error_sound.setCurrentText(self.config.get('error_sound', '中频提示音'))
        self.warning_sound.setCurrentText(self.config.get('warning_sound', '低频提示音'))
        self.info_sound.setCurrentText(self.config.get('info_sound', '轻微提示音'))

    def get_config(self) -> Dict:
        """获取配置"""
        return {
            'use_system_sound': self.use_system_sound.isChecked(),
            'volume': self.volume_slider.value(),
            'sound_type': self.sound_type.currentText(),
            'custom_sound_path': self.custom_sound_path.text().strip(),
            'critical_sound': self.critical_sound.currentText(),
            'error_sound': self.error_sound.currentText(),
            'warning_sound': self.warning_sound.currentText(),
            'info_sound': self.info_sound.currentText()
        }

    def validate(self) -> bool:
        """验证配置"""
        if self.sound_type.currentText() == "自定义声音文件":
            if not self.custom_sound_path.text().strip():
                QMessageBox.warning(self, "验证失败", "请选择自定义声音文件")
                return False
        return True


class DesktopChannelConfigWidget(QWidget):
    """桌面通知渠道配置组件"""

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

        display_group = QGroupBox("显示设置")
        display_layout = QFormLayout()

        self.show_icon = QCheckBox("显示应用图标")
        self.show_icon.setChecked(True)
        display_layout.addRow("", self.show_icon)

        self.auto_dismiss = QCheckBox("自动关闭通知")
        self.auto_dismiss.setChecked(True)
        display_layout.addRow("", self.auto_dismiss)

        self.dismiss_timeout = QSpinBox()
        self.dismiss_timeout.setRange(1, 60)
        self.dismiss_timeout.setValue(5)
        self.dismiss_timeout.setSuffix(" 秒")
        display_layout.addRow("关闭时间:", self.dismiss_timeout)

        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        content_group = QGroupBox("内容设置")
        content_layout = QFormLayout()

        self.show_title = QCheckBox("显示标题")
        self.show_title.setChecked(True)
        content_layout.addRow("", self.show_title)

        self.show_content = QCheckBox("显示内容预览")
        self.show_content.setChecked(True)
        content_layout.addRow("", self.show_content)

        self.max_content_length = QSpinBox()
        self.max_content_length.setRange(50, 500)
        self.max_content_length.setValue(200)
        self.max_content_length.setSuffix(" 字符")
        content_layout.addRow("最大内容长度:", self.max_content_length)

        content_group.setLayout(content_layout)
        layout.addWidget(content_group)

        priority_group = QGroupBox("优先级设置")
        priority_layout = QFormLayout()

        self.critical_popup = QCheckBox("严重告警弹出窗口")
        self.critical_popup.setChecked(True)
        priority_layout.addRow("", self.critical_popup)

        self.sound_with_desktop = QCheckBox("同时播放声音")
        self.sound_with_desktop.setChecked(True)
        priority_layout.addRow("", self.sound_with_desktop)

        priority_group.setLayout(priority_layout)
        layout.addWidget(priority_group)

        layout.addStretch()

    def load_config(self):
        """加载配置"""
        self.show_icon.setChecked(self.config.get('show_icon', True))
        self.auto_dismiss.setChecked(self.config.get('auto_dismiss', True))
        self.dismiss_timeout.setValue(self.config.get('dismiss_timeout', 5))
        self.show_title.setChecked(self.config.get('show_title', True))
        self.show_content.setChecked(self.config.get('show_content', True))
        self.max_content_length.setValue(self.config.get('max_content_length', 200))
        self.critical_popup.setChecked(self.config.get('critical_popup', True))
        self.sound_with_desktop.setChecked(self.config.get('sound_with_desktop', True))

    def get_config(self) -> Dict:
        """获取配置"""
        return {
            'show_icon': self.show_icon.isChecked(),
            'auto_dismiss': self.auto_dismiss.isChecked(),
            'dismiss_timeout': self.dismiss_timeout.value(),
            'show_title': self.show_title.isChecked(),
            'show_content': self.show_content.isChecked(),
            'max_content_length': self.max_content_length.value(),
            'critical_popup': self.critical_popup.isChecked(),
            'sound_with_desktop': self.sound_with_desktop.isChecked()
        }

    def validate(self) -> bool:
        """验证配置"""
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
            'dingtalk': '钉钉',
            'sound': '声音通知',
            'desktop': '桌面通知'
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
        elif self.channel_type == 'sound':
            return SoundChannelConfigWidget(self.config, self)
        elif self.channel_type == 'desktop':
            return DesktopChannelConfigWidget(self.config, self)
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
        if not self.config_widget.validate():
            return
        
        config = self.config_widget.get_config()
        
        try:
            from core.services.notification_service import (
                get_notification_service, NotificationChannel, NotificationType
            )
            
            service = get_notification_service()
            if service:
                type_map = {
                    'email': NotificationType.EMAIL,
                    'sms': NotificationType.SMS,
                    'webhook': NotificationType.WEBHOOK,
                    'dingtalk': NotificationType.DINGTALK,
                    'sound': NotificationType.SOUND,
                    'desktop': NotificationType.DESKTOP
                }
                
                channel = NotificationChannel(
                    channel_id=f"temp_{self.channel_type}",
                    name=f"临时{self._get_channel_name()}渠道",
                    notification_type=type_map.get(self.channel_type, NotificationType.EMAIL),
                    config=config,
                    enabled=True
                )
                
                errors = service.validate_channel_config(channel)
                if errors:
                    error_msg = "\n".join(f"• {error}" for error in errors)
                    QMessageBox.warning(
                        self,
                        "配置验证失败",
                        f"以下配置问题需要修正：\n\n{error_msg}"
                    )
                    return
        except Exception as e:
            logger.warning(f"调用NotificationService验证失败，使用本地验证: {e}")
        
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
            ('dingtalk', '钉钉', '💬'),
            ('sound', '声音通知', '🔊'),
            ('desktop', '桌面通知', '🖥️')
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

        if self.config_persistence:
            self.config_persistence.save_channel_config(channel_type, config)
        
        if channel_type in ['desktop', 'sound']:
            self._save_to_database(channel_type, config)

        self.on_channel_selected(self.channel_list.currentItem())
    
    def _save_to_database(self, channel_type: str, config: dict):
        """保存桌面和声音配置到数据库"""
        try:
            from db.models.alert_config_models import get_alert_config_database, NotificationConfig
            
            db = get_alert_config_database()
            current_config = db.load_notification_config()
            
            if current_config is None:
                current_config = NotificationConfig()
            
            if channel_type == 'desktop':
                current_config.desktop_enabled = True
                current_config.desktop_show_icon = config.get('show_icon', True)
                current_config.desktop_auto_dismiss = config.get('auto_dismiss', True)
                current_config.desktop_dismiss_timeout = config.get('dismiss_timeout', 5)
                current_config.desktop_show_title = config.get('show_title', True)
                current_config.desktop_show_content = config.get('show_content', True)
                current_config.desktop_max_content_length = config.get('max_content_length', 200)
                current_config.desktop_critical_popup = config.get('critical_popup', True)
                current_config.desktop_sound_with_desktop = config.get('sound_with_desktop', True)
            
            elif channel_type == 'sound':
                current_config.sound_enabled = True
                current_config.sound_use_system = config.get('use_system_sound', True)
                current_config.sound_volume = config.get('volume', 0.8)
                current_config.sound_type = config.get('sound_type', '默认提示音')
                current_config.sound_custom_path = config.get('custom_sound_path', '')
                current_config.sound_critical = config.get('critical_sound', '高频急促音')
                current_config.sound_error = config.get('error_sound', '中频提示音')
                current_config.sound_warning = config.get('warning_sound', '低频提示音')
                current_config.sound_info = config.get('info_sound', '轻微提示音')
            
            db.save_notification_config(current_config)
            logger.info(f"已保存 {channel_type} 配置到数据库")
            
        except Exception as e:
            logger.error(f"保存配置到数据库失败: {e}")

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

                if self.config_persistence:
                    self.config_persistence.delete_channel_config(channel_type)
                
                if channel_type in ['desktop', 'sound']:
                    self._disable_in_database(channel_type)

            self.on_channel_selected(current_item)
    
    def _disable_in_database(self, channel_type: str):
        """在数据库中禁用渠道"""
        try:
            from db.models.alert_config_models import get_alert_config_database, NotificationConfig
            
            db = get_alert_config_database()
            current_config = db.load_notification_config()
            
            if current_config is None:
                current_config = NotificationConfig()
            
            if channel_type == 'desktop':
                current_config.desktop_enabled = False
            elif channel_type == 'sound':
                current_config.sound_enabled = False
            
            db.save_notification_config(current_config)
            logger.info(f"已在数据库中禁用 {channel_type} 渠道")
            
        except Exception as e:
            logger.error(f"禁用渠道失败: {e}")

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
