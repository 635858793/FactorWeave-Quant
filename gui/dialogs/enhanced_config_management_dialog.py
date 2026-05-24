"""
增强配置管理对话框

提供全面的系统配置管理：
1. 策略参数配置
2. 风险控制设置
3. 交易接口配置
4. 监控报警设置
5. 系统参数配置
"""

from loguru import logger
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QLabel, QTextEdit, QLineEdit,
    QGroupBox, QFormLayout, QPushButton, QScrollArea, QSplitter,
    QHeaderView, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QFileDialog, QMessageBox, QProgressDialog, QInputDialog,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QSlider, QDateEdit, QTimeEdit, QColorDialog, QFontDialog,
    QGridLayout, QFrame, QButtonGroup, QRadioButton
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSettings, QDateTime
from PyQt5.QtGui import QFont, QPixmap, QIcon, QColor, QPalette

from .base_dialog import BaseDialog

# 导入服务
from core.services.strategy_service import StrategyService
from core.services.trading_service import TradingService
from core.services.unified_data_manager import UnifiedDataManager

logger = logger


@dataclass
class RiskControlConfig:
    """风险控制配置"""
    max_daily_loss: float = 0.05          # 最大日损失5%
    max_single_trade: float = 0.1         # 单次交易最大10%
    max_positions: int = 10               # 最大持仓数量
    max_strategies: int = 5               # 最大策略数量
    position_size_limit: float = 0.3      # 单仓位限制30%
    stop_loss_enabled: bool = True        # 启用止损
    take_profit_enabled: bool = True      # 启用止盈
    margin_call_threshold: float = 0.2    # 保证金预警阈值
    leverage_limit: float = 1.0           # 杠杆限制


@dataclass
class TradingInterfaceConfig:
    """交易接口配置"""
    interface_type: str = "simulation"    # 接口类型: simulation, real, paper
    broker_name: str = ""                 # 券商名称
    api_endpoint: str = ""                # API端点
    api_key: str = ""                     # API密钥
    secret_key: str = ""                  # 密钥
    account_id: str = ""                  # 账户ID
    commission_rate: float = 0.0003       # 手续费率
    min_commission: float = 5.0           # 最低手续费
    slippage: float = 0.0001              # 滑点
    timeout: int = 30                     # 超时时间(秒)
    retry_count: int = 3                  # 重试次数
    enable_logging: bool = True           # 启用日志


@dataclass
class MonitoringConfig:
    """监控报警配置"""
    enable_alerts: bool = True            # 启用报警
    email_alerts: bool = False            # 邮件报警
    sms_alerts: bool = False              # 短信报警
    desktop_alerts: bool = True           # 桌面通知
    alert_sound: bool = True              # 报警声音

    # 报警条件
    loss_alert_threshold: float = 0.02    # 损失报警阈值2%
    profit_alert_threshold: float = 0.05  # 盈利报警阈值5%
    position_alert_threshold: float = 0.8  # 仓位报警阈值80%

    # 邮件配置
    smtp_server: str = ""                 # SMTP服务器
    smtp_port: int = 587                  # SMTP端口
    email_username: str = ""              # 邮箱用户名
    email_password: str = ""              # 邮箱密码
    alert_recipients: List[str] = field(default_factory=list)  # 报警接收人


@dataclass
class SystemConfig:
    """系统配置"""
    auto_start: bool = False              # 自动启动
    auto_save: bool = True                # 自动保存
    save_interval: int = 300              # 保存间隔(秒)
    log_level: str = "INFO"               # 日志级别
    max_log_files: int = 10               # 最大日志文件数
    data_update_interval: int = 2000      # 数据更新间隔(毫秒)
    chart_update_interval: int = 5000     # 图表更新间隔(毫秒)

    # 界面配置
    theme: str = "default"                # 主题
    font_family: str = "Arial"            # 字体
    font_size: int = 10                   # 字体大小
    window_opacity: float = 1.0           # 窗口透明度

    # 性能配置
    max_concurrent_backtests: int = 3     # 最大并发回测数
    max_concurrent_optimizations: int = 1  # 最大并发优化数
    cache_enabled: bool = True            # 启用缓存
    cache_size: int = 1000                # 缓存大小


class RiskControlConfigWidget(QWidget):
    """风险控制配置组件"""

    def __init__(self, parent=None, config: Optional[RiskControlConfig] = None):
        super().__init__(parent)
        self.config = config or RiskControlConfig()
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 基本风险限制
        basic_group = QGroupBox("基本风险限制")
        basic_layout = QFormLayout(basic_group)

        self.max_daily_loss_spin = QDoubleSpinBox()
        self.max_daily_loss_spin.setRange(0.01, 0.5)
        self.max_daily_loss_spin.setDecimals(3)
        self.max_daily_loss_spin.setSuffix("%")

        self.max_single_trade_spin = QDoubleSpinBox()
        self.max_single_trade_spin.setRange(0.01, 1.0)
        self.max_single_trade_spin.setDecimals(3)
        self.max_single_trade_spin.setSuffix("%")

        self.max_positions_spin = QSpinBox()
        self.max_positions_spin.setRange(1, 100)

        self.max_strategies_spin = QSpinBox()
        self.max_strategies_spin.setRange(1, 20)

        self.position_size_limit_spin = QDoubleSpinBox()
        self.position_size_limit_spin.setRange(0.01, 1.0)
        self.position_size_limit_spin.setDecimals(3)
        self.position_size_limit_spin.setSuffix("%")

        basic_layout.addRow("最大日损失:", self.max_daily_loss_spin)
        basic_layout.addRow("单次交易限制:", self.max_single_trade_spin)
        basic_layout.addRow("最大持仓数:", self.max_positions_spin)
        basic_layout.addRow("最大策略数:", self.max_strategies_spin)
        basic_layout.addRow("单仓位限制:", self.position_size_limit_spin)

        layout.addWidget(basic_group)

        # 止损止盈设置
        stop_group = QGroupBox("止损止盈设置")
        stop_layout = QFormLayout(stop_group)

        self.stop_loss_checkbox = QCheckBox("启用止损")
        self.take_profit_checkbox = QCheckBox("启用止盈")

        self.margin_call_spin = QDoubleSpinBox()
        self.margin_call_spin.setRange(0.1, 0.9)
        self.margin_call_spin.setDecimals(2)
        self.margin_call_spin.setSuffix("%")

        self.leverage_limit_spin = QDoubleSpinBox()
        self.leverage_limit_spin.setRange(1.0, 10.0)
        self.leverage_limit_spin.setDecimals(1)

        stop_layout.addRow("", self.stop_loss_checkbox)
        stop_layout.addRow("", self.take_profit_checkbox)
        stop_layout.addRow("保证金预警:", self.margin_call_spin)
        stop_layout.addRow("杠杆限制:", self.leverage_limit_spin)

        layout.addWidget(stop_group)

        layout.addStretch()

    def _load_config(self):
        """加载配置"""
        self.max_daily_loss_spin.setValue(self.config.max_daily_loss * 100)
        self.max_single_trade_spin.setValue(self.config.max_single_trade * 100)
        self.max_positions_spin.setValue(self.config.max_positions)
        self.max_strategies_spin.setValue(self.config.max_strategies)
        self.position_size_limit_spin.setValue(self.config.position_size_limit * 100)

        self.stop_loss_checkbox.setChecked(self.config.stop_loss_enabled)
        self.take_profit_checkbox.setChecked(self.config.take_profit_enabled)
        self.margin_call_spin.setValue(self.config.margin_call_threshold * 100)
        self.leverage_limit_spin.setValue(self.config.leverage_limit)

    def get_config(self) -> RiskControlConfig:
        """获取配置"""
        return RiskControlConfig(
            max_daily_loss=self.max_daily_loss_spin.value() / 100,
            max_single_trade=self.max_single_trade_spin.value() / 100,
            max_positions=self.max_positions_spin.value(),
            max_strategies=self.max_strategies_spin.value(),
            position_size_limit=self.position_size_limit_spin.value() / 100,
            stop_loss_enabled=self.stop_loss_checkbox.isChecked(),
            take_profit_enabled=self.take_profit_checkbox.isChecked(),
            margin_call_threshold=self.margin_call_spin.value() / 100,
            leverage_limit=self.leverage_limit_spin.value()
        )


class TradingInterfaceConfigWidget(QWidget):
    """交易接口配置组件"""

    def __init__(self, parent=None, config: Optional[TradingInterfaceConfig] = None):
        super().__init__(parent)
        self.config = config or TradingInterfaceConfig()
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 接口类型
        type_group = QGroupBox("接口类型")
        type_layout = QVBoxLayout(type_group)

        self.interface_type_group = QButtonGroup()

        self.simulation_radio = QRadioButton("模拟交易")
        self.paper_radio = QRadioButton("纸上交易")
        self.real_radio = QRadioButton("实盘交易")

        self.interface_type_group.addButton(self.simulation_radio, 0)
        self.interface_type_group.addButton(self.paper_radio, 1)
        self.interface_type_group.addButton(self.real_radio, 2)

        type_layout.addWidget(self.simulation_radio)
        type_layout.addWidget(self.paper_radio)
        type_layout.addWidget(self.real_radio)

        layout.addWidget(type_group)

        # 连接配置
        connection_group = QGroupBox("连接配置")
        connection_layout = QFormLayout(connection_group)

        self.broker_name_edit = QLineEdit()
        self.api_endpoint_edit = QLineEdit()
        self.api_key_edit = QLineEdit()
        self.secret_key_edit = QLineEdit()
        self.secret_key_edit.setEchoMode(QLineEdit.Password)
        self.account_id_edit = QLineEdit()

        connection_layout.addRow("券商名称:", self.broker_name_edit)
        connection_layout.addRow("API端点:", self.api_endpoint_edit)
        connection_layout.addRow("API密钥:", self.api_key_edit)
        connection_layout.addRow("密钥:", self.secret_key_edit)
        connection_layout.addRow("账户ID:", self.account_id_edit)

        layout.addWidget(connection_group)

        # 交易参数
        trading_group = QGroupBox("交易参数")
        trading_layout = QFormLayout(trading_group)

        self.commission_rate_spin = QDoubleSpinBox()
        self.commission_rate_spin.setRange(0.0001, 0.01)
        self.commission_rate_spin.setDecimals(4)
        self.commission_rate_spin.setSuffix("%")

        self.min_commission_spin = QDoubleSpinBox()
        self.min_commission_spin.setRange(0.1, 100.0)
        self.min_commission_spin.setDecimals(1)

        self.slippage_spin = QDoubleSpinBox()
        self.slippage_spin.setRange(0.0001, 0.01)
        self.slippage_spin.setDecimals(4)
        self.slippage_spin.setSuffix("%")

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 300)
        self.timeout_spin.setSuffix("秒")

        self.retry_count_spin = QSpinBox()
        self.retry_count_spin.setRange(1, 10)

        self.enable_logging_checkbox = QCheckBox("启用交易日志")

        trading_layout.addRow("手续费率:", self.commission_rate_spin)
        trading_layout.addRow("最低手续费:", self.min_commission_spin)
        trading_layout.addRow("滑点:", self.slippage_spin)
        trading_layout.addRow("超时时间:", self.timeout_spin)
        trading_layout.addRow("重试次数:", self.retry_count_spin)
        trading_layout.addRow("", self.enable_logging_checkbox)

        layout.addWidget(trading_group)

        # 测试连接按钮
        test_button = QPushButton("测试连接")
        test_button.clicked.connect(self._test_connection)
        layout.addWidget(test_button)

        layout.addStretch()

    def _load_config(self):
        """加载配置"""
        # 设置接口类型
        if self.config.interface_type == "simulation":
            self.simulation_radio.setChecked(True)
        elif self.config.interface_type == "paper":
            self.paper_radio.setChecked(True)
        elif self.config.interface_type == "real":
            self.real_radio.setChecked(True)

        # 设置连接配置
        self.broker_name_edit.setText(self.config.broker_name)
        self.api_endpoint_edit.setText(self.config.api_endpoint)
        self.api_key_edit.setText(self.config.api_key)
        self.secret_key_edit.setText(self.config.secret_key)
        self.account_id_edit.setText(self.config.account_id)

        # 设置交易参数
        self.commission_rate_spin.setValue(self.config.commission_rate * 10000)  # 转换为基点
        self.min_commission_spin.setValue(self.config.min_commission)
        self.slippage_spin.setValue(self.config.slippage * 10000)  # 转换为基点
        self.timeout_spin.setValue(self.config.timeout)
        self.retry_count_spin.setValue(self.config.retry_count)
        self.enable_logging_checkbox.setChecked(self.config.enable_logging)

    def get_config(self) -> TradingInterfaceConfig:
        """获取配置"""
        # 获取接口类型
        interface_type = "simulation"
        if self.paper_radio.isChecked():
            interface_type = "paper"
        elif self.real_radio.isChecked():
            interface_type = "real"

        return TradingInterfaceConfig(
            interface_type=interface_type,
            broker_name=self.broker_name_edit.text(),
            api_endpoint=self.api_endpoint_edit.text(),
            api_key=self.api_key_edit.text(),
            secret_key=self.secret_key_edit.text(),
            account_id=self.account_id_edit.text(),
            commission_rate=self.commission_rate_spin.value() / 10000,
            min_commission=self.min_commission_spin.value(),
            slippage=self.slippage_spin.value() / 10000,
            timeout=self.timeout_spin.value(),
            retry_count=self.retry_count_spin.value(),
            enable_logging=self.enable_logging_checkbox.isChecked()
        )

    def _test_connection(self):
        """测试连接"""
        config = self.get_config()

        # 简化的连接测试
        if config.interface_type == "simulation":
            QMessageBox.information(self, "连接测试", "模拟交易接口连接正常")
        elif not config.api_endpoint:
            QMessageBox.warning(self, "连接测试", "请填写API端点")
        elif not config.api_key:
            QMessageBox.warning(self, "连接测试", "请填写API密钥")
        else:
            # 这里应该实现真实的连接测试
            QMessageBox.information(self, "连接测试", "连接测试功能待实现")


class MonitoringConfigWidget(QWidget):
    """监控报警配置组件"""

    def __init__(self, parent=None, config: Optional[MonitoringConfig] = None):
        super().__init__(parent)
        self.config = config or MonitoringConfig()
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 报警开关
        alert_group = QGroupBox("报警设置")
        alert_layout = QFormLayout(alert_group)

        self.enable_alerts_checkbox = QCheckBox("启用报警")
        self.email_alerts_checkbox = QCheckBox("邮件报警")
        self.sms_alerts_checkbox = QCheckBox("短信报警")
        self.desktop_alerts_checkbox = QCheckBox("桌面通知")
        self.alert_sound_checkbox = QCheckBox("报警声音")

        alert_layout.addRow("", self.enable_alerts_checkbox)
        alert_layout.addRow("", self.email_alerts_checkbox)
        alert_layout.addRow("", self.sms_alerts_checkbox)
        alert_layout.addRow("", self.desktop_alerts_checkbox)
        alert_layout.addRow("", self.alert_sound_checkbox)

        layout.addWidget(alert_group)

        # 报警条件
        condition_group = QGroupBox("报警条件")
        condition_layout = QFormLayout(condition_group)

        self.loss_alert_spin = QDoubleSpinBox()
        self.loss_alert_spin.setRange(0.01, 0.5)
        self.loss_alert_spin.setDecimals(3)
        self.loss_alert_spin.setSuffix("%")

        self.profit_alert_spin = QDoubleSpinBox()
        self.profit_alert_spin.setRange(0.01, 1.0)
        self.profit_alert_spin.setDecimals(3)
        self.profit_alert_spin.setSuffix("%")

        self.position_alert_spin = QDoubleSpinBox()
        self.position_alert_spin.setRange(0.1, 1.0)
        self.position_alert_spin.setDecimals(2)
        self.position_alert_spin.setSuffix("%")

        condition_layout.addRow("损失报警阈值:", self.loss_alert_spin)
        condition_layout.addRow("盈利报警阈值:", self.profit_alert_spin)
        condition_layout.addRow("仓位报警阈值:", self.position_alert_spin)

        layout.addWidget(condition_group)

        # 邮件配置
        email_group = QGroupBox("邮件配置")
        email_layout = QFormLayout(email_group)

        self.smtp_server_edit = QLineEdit()
        self.smtp_port_spin = QSpinBox()
        self.smtp_port_spin.setRange(1, 65535)

        self.email_username_edit = QLineEdit()
        self.email_password_edit = QLineEdit()
        self.email_password_edit.setEchoMode(QLineEdit.Password)

        self.recipients_edit = QTextEdit()
        self.recipients_edit.setMaximumHeight(80)
        self.recipients_edit.setPlaceholderText("每行一个邮箱地址")

        email_layout.addRow("SMTP服务器:", self.smtp_server_edit)
        email_layout.addRow("SMTP端口:", self.smtp_port_spin)
        email_layout.addRow("用户名:", self.email_username_edit)
        email_layout.addRow("密码:", self.email_password_edit)
        email_layout.addRow("接收人:", self.recipients_edit)

        layout.addWidget(email_group)

        # 测试报警按钮
        test_button = QPushButton("测试报警")
        test_button.clicked.connect(self._test_alert)
        layout.addWidget(test_button)

        layout.addStretch()

    def _load_config(self):
        """加载配置"""
        self.enable_alerts_checkbox.setChecked(self.config.enable_alerts)
        self.email_alerts_checkbox.setChecked(self.config.email_alerts)
        self.sms_alerts_checkbox.setChecked(self.config.sms_alerts)
        self.desktop_alerts_checkbox.setChecked(self.config.desktop_alerts)
        self.alert_sound_checkbox.setChecked(self.config.alert_sound)

        self.loss_alert_spin.setValue(self.config.loss_alert_threshold * 100)
        self.profit_alert_spin.setValue(self.config.profit_alert_threshold * 100)
        self.position_alert_spin.setValue(self.config.position_alert_threshold * 100)

        self.smtp_server_edit.setText(self.config.smtp_server)
        self.smtp_port_spin.setValue(self.config.smtp_port)
        self.email_username_edit.setText(self.config.email_username)
        self.email_password_edit.setText(self.config.email_password)

        if self.config.alert_recipients:
            self.recipients_edit.setText('\n'.join(self.config.alert_recipients))

    def get_config(self) -> MonitoringConfig:
        """获取配置"""
        recipients = []
        recipients_text = self.recipients_edit.toPlainText().strip()
        if recipients_text:
            recipients = [line.strip() for line in recipients_text.split('\n') if line.strip()]

        return MonitoringConfig(
            enable_alerts=self.enable_alerts_checkbox.isChecked(),
            email_alerts=self.email_alerts_checkbox.isChecked(),
            sms_alerts=self.sms_alerts_checkbox.isChecked(),
            desktop_alerts=self.desktop_alerts_checkbox.isChecked(),
            alert_sound=self.alert_sound_checkbox.isChecked(),
            loss_alert_threshold=self.loss_alert_spin.value() / 100,
            profit_alert_threshold=self.profit_alert_spin.value() / 100,
            position_alert_threshold=self.position_alert_spin.value() / 100,
            smtp_server=self.smtp_server_edit.text(),
            smtp_port=self.smtp_port_spin.value(),
            email_username=self.email_username_edit.text(),
            email_password=self.email_password_edit.text(),
            alert_recipients=recipients
        )

    def _test_alert(self):
        """测试报警"""
        config = self.get_config()

        if not config.enable_alerts:
            QMessageBox.warning(self, "测试报警", "请先启用报警功能")
            return

        if config.desktop_alerts:
            QMessageBox.information(self, "测试报警", "这是一个测试报警消息")

        if config.email_alerts:
            if not config.smtp_server or not config.email_username:
                QMessageBox.warning(self, "测试报警", "请完善邮件配置")
            else:
                # 这里应该实现真实的邮件发送测试
                QMessageBox.information(self, "测试报警", "邮件报警测试功能待实现")


class SystemConfigWidget(QWidget):
    """系统配置组件"""

    def __init__(self, parent=None, config: Optional[SystemConfig] = None):
        super().__init__(parent)
        self.config = config or SystemConfig()
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 基本设置
        basic_group = QGroupBox("基本设置")
        basic_layout = QFormLayout(basic_group)

        self.auto_start_checkbox = QCheckBox("开机自动启动")
        self.auto_save_checkbox = QCheckBox("自动保存配置")

        self.save_interval_spin = QSpinBox()
        self.save_interval_spin.setRange(60, 3600)
        self.save_interval_spin.setSuffix("秒")

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])

        self.max_log_files_spin = QSpinBox()
        self.max_log_files_spin.setRange(1, 100)

        basic_layout.addRow("", self.auto_start_checkbox)
        basic_layout.addRow("", self.auto_save_checkbox)
        basic_layout.addRow("保存间隔:", self.save_interval_spin)
        basic_layout.addRow("日志级别:", self.log_level_combo)
        basic_layout.addRow("最大日志文件:", self.max_log_files_spin)

        layout.addWidget(basic_group)

        # 界面设置
        ui_group = QGroupBox("界面设置")
        ui_layout = QFormLayout(ui_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["default", "dark", "light", "blue"])

        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(["Arial", "Microsoft YaHei", "SimSun", "Consolas"])

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(50, 100)
        self.opacity_label = QLabel("100%")
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_label.setText(f"{v}%"))

        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(self.opacity_slider)
        opacity_layout.addWidget(self.opacity_label)

        ui_layout.addRow("主题:", self.theme_combo)
        ui_layout.addRow("字体:", self.font_family_combo)
        ui_layout.addRow("字体大小:", self.font_size_spin)
        ui_layout.addRow("窗口透明度:", opacity_layout)

        layout.addWidget(ui_group)

        # 性能设置
        performance_group = QGroupBox("性能设置")
        performance_layout = QFormLayout(performance_group)

        self.data_update_interval_spin = QSpinBox()
        self.data_update_interval_spin.setRange(500, 10000)
        self.data_update_interval_spin.setSuffix("毫秒")

        self.chart_update_interval_spin = QSpinBox()
        self.chart_update_interval_spin.setRange(1000, 30000)
        self.chart_update_interval_spin.setSuffix("毫秒")

        self.max_backtests_spin = QSpinBox()
        self.max_backtests_spin.setRange(1, 10)

        self.max_optimizations_spin = QSpinBox()
        self.max_optimizations_spin.setRange(1, 5)

        self.cache_enabled_checkbox = QCheckBox("启用缓存")

        self.cache_size_spin = QSpinBox()
        self.cache_size_spin.setRange(100, 10000)

        performance_layout.addRow("数据更新间隔:", self.data_update_interval_spin)
        performance_layout.addRow("图表更新间隔:", self.chart_update_interval_spin)
        performance_layout.addRow("最大并发回测:", self.max_backtests_spin)
        performance_layout.addRow("最大并发优化:", self.max_optimizations_spin)
        performance_layout.addRow("", self.cache_enabled_checkbox)
        performance_layout.addRow("缓存大小:", self.cache_size_spin)

        layout.addWidget(performance_group)

        layout.addStretch()

    def _load_config(self):
        """加载配置"""
        self.auto_start_checkbox.setChecked(self.config.auto_start)
        self.auto_save_checkbox.setChecked(self.config.auto_save)
        self.save_interval_spin.setValue(self.config.save_interval)
        self.log_level_combo.setCurrentText(self.config.log_level)
        self.max_log_files_spin.setValue(self.config.max_log_files)

        self.theme_combo.setCurrentText(self.config.theme)
        self.font_family_combo.setCurrentText(self.config.font_family)
        self.font_size_spin.setValue(self.config.font_size)
        self.opacity_slider.setValue(int(self.config.window_opacity * 100))

        self.data_update_interval_spin.setValue(self.config.data_update_interval)
        self.chart_update_interval_spin.setValue(self.config.chart_update_interval)
        self.max_backtests_spin.setValue(self.config.max_concurrent_backtests)
        self.max_optimizations_spin.setValue(self.config.max_concurrent_optimizations)
        self.cache_enabled_checkbox.setChecked(self.config.cache_enabled)
        self.cache_size_spin.setValue(self.config.cache_size)

    def get_config(self) -> SystemConfig:
        """获取配置"""
        return SystemConfig(
            auto_start=self.auto_start_checkbox.isChecked(),
            auto_save=self.auto_save_checkbox.isChecked(),
            save_interval=self.save_interval_spin.value(),
            log_level=self.log_level_combo.currentText(),
            max_log_files=self.max_log_files_spin.value(),
            data_update_interval=self.data_update_interval_spin.value(),
            chart_update_interval=self.chart_update_interval_spin.value(),
            theme=self.theme_combo.currentText(),
            font_family=self.font_family_combo.currentText(),
            font_size=self.font_size_spin.value(),
            window_opacity=self.opacity_slider.value() / 100.0,
            max_concurrent_backtests=self.max_backtests_spin.value(),
            max_concurrent_optimizations=self.max_optimizations_spin.value(),
            cache_enabled=self.cache_enabled_checkbox.isChecked(),
            cache_size=self.cache_size_spin.value()
        )


class EnhancedConfigManagementDialog(BaseDialog):
    """增强配置管理对话框"""

    # 信号
    config_changed = pyqtSignal(str, object)  # 配置类型, 配置对象

    def __init__(self, parent=None,
                 strategy_service=None,
                 trading_service=None,
                 data_manager=None):
        """
        初始化增强配置管理对话框

        Args:
            parent: 父窗口
            strategy_service: 策略服务
            trading_service: 交易服务
            data_manager: 数据管理器
        """
        self.strategy_service = strategy_service
        self.trading_service = trading_service
        self.data_manager = data_manager

        # 配置存储
        self.config_file = "config/system_config.json"
        self._ensure_config_dir()

        super().__init__(
            parent,
            title="系统配置管理",
            size=(800, 600),
            settings_key="EnhancedConfigManagementDialog"
        )

        self._setup_ui()
        self._load_all_configs()

    def _ensure_config_dir(self):
        """确保配置目录存在"""
        config_dir = os.path.dirname(self.config_file)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 创建选项卡
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # 风险控制选项卡
        self.risk_config_widget = RiskControlConfigWidget()
        self.tab_widget.addTab(self.risk_config_widget, "风险控制")

        # 交易接口选项卡
        self.trading_config_widget = TradingInterfaceConfigWidget()
        self.tab_widget.addTab(self.trading_config_widget, "交易接口")

        # 监控报警选项卡
        self.monitoring_config_widget = MonitoringConfigWidget()
        self.tab_widget.addTab(self.monitoring_config_widget, "监控报警")

        # 系统设置选项卡
        self.system_config_widget = SystemConfigWidget()
        self.tab_widget.addTab(self.system_config_widget, "系统设置")

        # 按钮区域
        button_layout = QHBoxLayout()

        # 导入导出按钮
        import_button = QPushButton("导入配置")
        import_button.clicked.connect(self._import_config)

        export_button = QPushButton("导出配置")
        export_button.clicked.connect(self._export_config)

        # 重置按钮
        reset_button = QPushButton("重置默认")
        reset_button.clicked.connect(self._reset_to_default)

        # 应用和确定按钮
        apply_button = QPushButton("应用")
        apply_button.clicked.connect(self._apply_config)

        ok_button = QPushButton("确定")
        ok_button.clicked.connect(self._ok_clicked)

        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(import_button)
        button_layout.addWidget(export_button)
        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        button_layout.addWidget(apply_button)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def _load_all_configs(self):
        """加载所有配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

                # 加载各个配置
                if 'risk_control' in config_data:
                    risk_config = RiskControlConfig(**config_data['risk_control'])
                    self.risk_config_widget.config = risk_config
                    self.risk_config_widget._load_config()

                if 'trading_interface' in config_data:
                    trading_config = TradingInterfaceConfig(**config_data['trading_interface'])
                    self.trading_config_widget.config = trading_config
                    self.trading_config_widget._load_config()

                if 'monitoring' in config_data:
                    monitoring_config = MonitoringConfig(**config_data['monitoring'])
                    self.monitoring_config_widget.config = monitoring_config
                    self.monitoring_config_widget._load_config()

                if 'system' in config_data:
                    system_config = SystemConfig(**config_data['system'])
                    self.system_config_widget.config = system_config
                    self.system_config_widget._load_config()

        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            QMessageBox.warning(self, "警告", f"加载配置失败: {e}")

    def _save_all_configs(self):
        """保存所有配置"""
        try:
            config_data = {
                'risk_control': asdict(self.risk_config_widget.get_config()),
                'trading_interface': asdict(self.trading_config_widget.get_config()),
                'monitoring': asdict(self.monitoring_config_widget.get_config()),
                'system': asdict(self.system_config_widget.get_config()),
                'last_updated': datetime.now().isoformat()
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            logger.info("配置保存成功")
            return True

        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存配置失败: {e}")
            return False

    def _apply_config(self):
        """应用配置"""
        try:
            # 保存配置
            if not self._save_all_configs():
                return

            # 获取各个配置
            risk_config = self.risk_config_widget.get_config()
            trading_config = self.trading_config_widget.get_config()
            monitoring_config = self.monitoring_config_widget.get_config()
            system_config = self.system_config_widget.get_config()

            # 发送配置变更信号
            self.config_changed.emit('risk_control', risk_config)
            self.config_changed.emit('trading_interface', trading_config)
            self.config_changed.emit('monitoring', monitoring_config)
            self.config_changed.emit('system', system_config)

            # 应用到服务
            self._apply_to_services(risk_config, trading_config, monitoring_config, system_config)

            QMessageBox.information(self, "成功", "配置已应用")

        except Exception as e:
            logger.error(f"应用配置失败: {e}")
            QMessageBox.critical(self, "错误", f"应用配置失败: {e}")

    def _apply_to_services(self, risk_config, trading_config, monitoring_config, system_config):
        """应用配置到服务"""
        try:
            # 应用到交易服务
            if self.trading_service:
                # 更新风险限制
                self.trading_service._risk_limits.update({
                    'max_daily_loss': risk_config.max_daily_loss,
                    'max_single_trade': risk_config.max_single_trade,
                    'max_positions': risk_config.max_positions,
                    'max_strategies': risk_config.max_strategies
                })

                # 更新交易配置
                self.trading_service._trading_config.update({
                    'commission_rate': trading_config.commission_rate,
                    'min_commission': trading_config.min_commission,
                    'slippage': trading_config.slippage
                })

            # 应用到策略服务
            if self.strategy_service:
                # 更新并发限制
                self.strategy_service._max_concurrent_backtests = system_config.max_concurrent_backtests
                self.strategy_service._max_concurrent_optimizations = system_config.max_concurrent_optimizations

            logger.info("配置已应用到服务")

        except Exception as e:
            logger.error(f"应用配置到服务失败: {e}")

    def _ok_clicked(self):
        """确定按钮点击"""
        self._apply_config()
        self.accept()

    def _import_config(self):
        """导入配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入配置", "", "JSON Files (*.json)"
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

                # 验证配置格式
                required_sections = ['risk_control', 'trading_interface', 'monitoring', 'system']
                if not all(section in config_data for section in required_sections):
                    QMessageBox.warning(self, "错误", "配置文件格式不正确")
                    return

                # 加载配置
                self.config_file = file_path
                self._load_all_configs()

                QMessageBox.information(self, "成功", "配置导入成功")

            except Exception as e:
                logger.error(f"导入配置失败: {e}")
                QMessageBox.critical(self, "错误", f"导入配置失败: {e}")

    def _export_config(self):
        """导出配置"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出配置",
            f"system_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json)"
        )

        if file_path:
            try:
                config_data = {
                    'risk_control': asdict(self.risk_config_widget.get_config()),
                    'trading_interface': asdict(self.trading_config_widget.get_config()),
                    'monitoring': asdict(self.monitoring_config_widget.get_config()),
                    'system': asdict(self.system_config_widget.get_config()),
                    'exported_at': datetime.now().isoformat(),
                    'version': '1.0'
                }

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)

                QMessageBox.information(self, "成功", f"配置已导出到: {file_path}")

            except Exception as e:
                logger.error(f"导出配置失败: {e}")
                QMessageBox.critical(self, "错误", f"导出配置失败: {e}")

    def _reset_to_default(self):
        """重置为默认配置"""
        reply = QMessageBox.question(
            self, "确认重置",
            "确定要重置所有配置为默认值吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # 重置各个配置组件
                self.risk_config_widget.config = RiskControlConfig()
                self.risk_config_widget._load_config()

                self.trading_config_widget.config = TradingInterfaceConfig()
                self.trading_config_widget._load_config()

                self.monitoring_config_widget.config = MonitoringConfig()
                self.monitoring_config_widget._load_config()

                self.system_config_widget.config = SystemConfig()
                self.system_config_widget._load_config()

                QMessageBox.information(self, "成功", "配置已重置为默认值")

            except Exception as e:
                logger.error(f"重置配置失败: {e}")
                QMessageBox.critical(self, "错误", f"重置配置失败: {e}")

    def get_risk_config(self) -> RiskControlConfig:
        """获取风险控制配置"""
        return self.risk_config_widget.get_config()

    def get_trading_config(self) -> TradingInterfaceConfig:
        """获取交易接口配置"""
        return self.trading_config_widget.get_config()

    def get_monitoring_config(self) -> MonitoringConfig:
        """获取监控配置"""
        return self.monitoring_config_widget.get_config()

    def get_system_config(self) -> SystemConfig:
        """获取系统配置"""
        return self.system_config_widget.get_config()


# 测试代码
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 创建测试对话框
    dialog = EnhancedConfigManagementDialog()
    dialog.show()

    sys.exit(app.exec_())
