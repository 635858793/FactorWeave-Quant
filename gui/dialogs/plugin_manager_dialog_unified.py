"""
统一插件管理对话框

合并了基础插件管理 (plugin_manager_dialog.py) 和增强插件管理 (enhanced_plugin_manager_dialog.py) 的功能，
提供完整的插件生命周期管理、配置、监控、市场等一体化界面。

功能模块:
  Tab 1: 已安装插件 - 插件列表、状态管理、批量操作、过滤搜索
  Tab 2: 数据源管理 - 数据源插件健康检查、优先级、路由配置
  Tab 3: 指标与策略 - 指标/策略插件配置与管理
  Tab 4: 插件市场 - 在线插件浏览、安装、更新
  Tab 5: 性能监控 - 系统指标、插件性能统计
  Tab 6: 日志 - 操作日志查看与导出

Author: FactorWeave-Quant Team
Version: 3.0.0
"""

import os
import json
import time
import traceback
from datetime import datetime
from loguru import logger
from typing import Dict, List, Optional, Any, Tuple

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QGridLayout, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QSplitter,
    QProgressBar, QMessageBox, QWidget, QTabWidget,
    QTextEdit, QListWidget, QListWidgetItem, QTreeWidget,
    QTreeWidgetItem, QToolBar, QAction, QMenu, QStatusBar,
    QProgressDialog, QApplication, QScrollArea, QFileDialog,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt5.QtGui import QIcon, QFont, QColor, QPalette

from .base_dialog import BaseDialog

# 导入核心服务
from core.plugin_manager import PluginManager, PluginInfo, PluginStatus, PluginType, PluginCategory
from core.plugin_types import PluginType, PluginCategory

try:
    from core.services.plugin_database_service import get_plugin_database_service
    DB_SERVICE_AVAILABLE = True
except ImportError:
    DB_SERVICE_AVAILABLE = False
    logger.warning("Plugin database service not available")

try:
    from core.services.uni_plugin_data_manager import get_uni_plugin_data_manager
    UNI_DATA_MANAGER_AVAILABLE = True
except ImportError:
    UNI_DATA_MANAGER_AVAILABLE = False
    logger.warning("Uni plugin data manager not available")


# =============================================================================
# 插件状态卡片小部件（继承自基础版，优化增强版样式）
# =============================================================================

class PluginStatusWidget(QWidget):
    """插件状态显示卡片小部件"""

    def __init__(self, plugin_info: PluginInfo, parent=None):
        super().__init__(parent)
        self.plugin_info = plugin_info
        self.init_ui()

    def init_ui(self):
        """初始化UI - 采用简洁专业风格"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)

        # 卡片样式
        enabled = self.plugin_info.status in [PluginStatus.ENABLED, PluginStatus.LOADED]
        self.setStyleSheet(f"""
            PluginStatusWidget {{
                background-color: {'#ffffff' if enabled else '#f8f9fa'};
                border: 1px solid {'#dee2e6' if enabled else '#e9ecef'};
                border-left: 3px solid {'#28a745' if enabled else '#dc3545'};
                border-radius: 6px;
                margin: 2px;
            }}
            PluginStatusWidget:hover {{
                background-color: #f0f7ff;
                border-color: #007bff;
            }}
            QLabel {{
                border: none;
                background-color: transparent;
            }}
            QPushButton {{
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: bold;
                min-width: 55px;
            }}
            QPushButton:hover {{ background-color: #0056b3; }}
            QPushButton:pressed {{ background-color: #004085; }}
        """)

        # 状态指示点
        status_dot = QLabel("\u25cf")
        dot_color = self._get_status_color(self.plugin_info.status)
        status_dot.setStyleSheet(f"color: {dot_color}; font-size: 14px; font-weight: bold; min-width: 16px; max-width: 16px;")
        status_dot.setAlignment(Qt.AlignCenter)
        layout.addWidget(status_dot)

        # 插件信息
        info_layout = QVBoxLayout()

        name_label = QLabel(self.plugin_info.name or "未命名插件")
        name_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        name_label.setStyleSheet("color: #212529;")
        info_layout.addWidget(name_label)

        subtitle = f"v{self.plugin_info.version}"
        if self.plugin_info.description:
            desc = self.plugin_info.description[:50] + ("..." if len(self.plugin_info.description) > 50 else "")
            subtitle += f" - {desc}"
        subtitle_label = QLabel(subtitle)
        subtitle_label.setFont(QFont("Microsoft YaHei", 9))
        subtitle_label.setStyleSheet("color: #6c757d;")
        info_layout.addWidget(subtitle_label)

        layout.addLayout(info_layout)
        layout.addStretch()

        # 状态标签
        status_label = QLabel(self._get_status_text(self.plugin_info.status))
        status_label.setStyleSheet(f"""
            QLabel {{
                background-color: {dot_color};
                border-radius: 4px;
                padding: 3px 12px;
                color: white;
                font-size: 10px;
                font-weight: bold;
                margin: 0 10px;
            }}
        """)
        status_label.setFixedWidth(60)
        layout.addWidget(status_label)

        # 操作按钮
        buttons_layout = QHBoxLayout()

        if self.plugin_info.status in [PluginStatus.LOADED, PluginStatus.DISABLED, PluginStatus.UNLOADED]:
            enable_btn = QPushButton("\u542f\u7528")
            enable_btn.setStyleSheet("background-color: #28a745;")
            enable_btn.clicked.connect(self.enable_plugin)
            buttons_layout.addWidget(enable_btn)
        elif self.plugin_info.status == PluginStatus.ENABLED:
            disable_btn = QPushButton("\u7981\u7528")
            disable_btn.setStyleSheet("background-color: #dc3545;")
            disable_btn.clicked.connect(self.disable_plugin)
            buttons_layout.addWidget(disable_btn)

        config_btn = QPushButton("\u914d\u7f6e")
        config_btn.setStyleSheet("background-color: #6c757d;")
        config_btn.clicked.connect(self.configure_plugin)
        buttons_layout.addWidget(config_btn)

        info_btn = QPushButton("?")
        info_btn.setStyleSheet("background-color: #777777; min-width: 24px; max-width: 24px;")
        info_btn.clicked.connect(self.show_plugin_info)
        buttons_layout.addWidget(info_btn)

        layout.addLayout(buttons_layout)

    def _get_status_color(self, status: PluginStatus) -> str:
        """获取状态颜色"""
        color_map = {
            PluginStatus.UNLOADED: "#666666",
            PluginStatus.LOADED: "#17a2b8",
            PluginStatus.ENABLED: "#28a745",
            PluginStatus.DISABLED: "#ffc107",
            PluginStatus.ERROR: "#dc3545"
        }
        return color_map.get(status, "#666666")

    def _get_status_text(self, status: PluginStatus) -> str:
        """获取状态文本"""
        text_map = {
            PluginStatus.UNLOADED: "\u672a\u52a0\u8f7d",
            PluginStatus.LOADED: "\u5df2\u52a0\u8f7d",
            PluginStatus.ENABLED: "\u5df2\u542f\u7528",
            PluginStatus.DISABLED: "\u5df2\u7981\u7528",
            PluginStatus.ERROR: "\u9519\u8bef"
        }
        return text_map.get(status, "\u672a\u77e5")

    def enable_plugin(self):
        """启用插件"""
        dialog = self._find_parent_dialog()
        if dialog:
            dialog.enable_plugin(self.plugin_info.name)

    def disable_plugin(self):
        """禁用插件"""
        dialog = self._find_parent_dialog()
        if dialog:
            dialog.disable_plugin(self.plugin_info.name)

    def configure_plugin(self):
        """配置插件"""
        dialog = self._find_parent_dialog()
        if dialog:
            dialog.configure_plugin(self.plugin_info.name)

    def show_plugin_info(self):
        """显示插件详细信息"""
        from PyQt5.QtWidgets import QDialog as InfoDialog

        info_dialog = InfoDialog(self)
        info_dialog.setWindowTitle(f"\u63d2\u4ef6\u4fe1\u606f - {self.plugin_info.name}")
        info_dialog.setModal(True)
        info_dialog.resize(450, 350)

        layout = QVBoxLayout(info_dialog)

        none_text = '\u65e0'
        basic_info = f"""
        <h3>{self.plugin_info.name}</h3>
        <p><b>\u7248\u672c:</b> {self.plugin_info.version}</p>
        <p><b>\u4f5c\u8005:</b> {self.plugin_info.author}</p>
        <p><b>\u72b6\u6001:</b> {self._get_status_text(self.plugin_info.status)}</p>
        <p><b>\u63cf\u8ff0:</b> {self.plugin_info.description or none_text}</p>
        """
        info_text = QTextEdit()
        info_text.setHtml(basic_info)
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(200)
        layout.addWidget(info_text)

        if self.plugin_info.dependencies:
            additional = f"<h4>\u4f9d\u8d56:</h4><p>{', '.join(self.plugin_info.dependencies)}</p>"
            detail_text = QTextEdit()
            detail_text.setHtml(additional)
            detail_text.setReadOnly(True)
            detail_text.setMaximumHeight(120)
            layout.addWidget(detail_text)

        from PyQt5.QtWidgets import QDialogButtonBox
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(info_dialog.accept)
        layout.addWidget(buttons)

        info_dialog.exec_()

    def _find_parent_dialog(self):
        """查找父对话框"""
        parent = self.parent()
        while parent:
            if isinstance(parent, PluginManagerDialogUnified):
                return parent
            parent = parent.parent()
        return None

    def _update_status_display(self, new_status: PluginStatus):
        """更新状态显示"""
        try:
            self.plugin_info.status = new_status
            self.init_ui()
        except Exception as e:
            logger.warning(f"\u66f4\u65b0\u63d2\u4ef6\u72b6\u6001\u663e\u793a\u5931\u8d25: {e}")


# =============================================================================
# 插件配置对话框（继承自基础版）
# =============================================================================

class PluginConfigDialog(QDialog):
    """插件配置对话框"""

    def __init__(self, plugin_info: PluginInfo, plugin_manager: PluginManager, parent=None):
        super().__init__(parent)
        self.plugin_info = plugin_info
        self.plugin_manager = plugin_manager
        self.config_widgets = {}
        self.init_ui()
        self.load_config()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"\u914d\u7f6e\u63d2\u4ef6 - {self.plugin_info.name}")
        self.setModal(True)
        self.resize(400, 300)

        layout = QVBoxLayout(self)

        # 插件信息
        info_group = QGroupBox("\u63d2\u4ef6\u4fe1\u606f")
        info_layout = QGridLayout(info_group)

        info_layout.addWidget(QLabel("\u540d\u79f0:"), 0, 0)
        info_layout.addWidget(QLabel(self.plugin_info.name), 0, 1)

        info_layout.addWidget(QLabel("\u7248\u672c:"), 1, 0)
        info_layout.addWidget(QLabel(self.plugin_info.version), 1, 1)

        info_layout.addWidget(QLabel("\u4f5c\u8005:"), 2, 0)
        info_layout.addWidget(QLabel(self.plugin_info.author), 2, 1)

        info_layout.addWidget(QLabel("\u63cf\u8ff0:"), 3, 0)
        desc_label = QLabel(self.plugin_info.description)
        desc_label.setWordWrap(True)
        info_layout.addWidget(desc_label, 3, 1)

        layout.addWidget(info_group)

        # 配置选项
        self.config_group = QGroupBox("\u914d\u7f6e\u9009\u9879")
        self.config_layout = QGridLayout(self.config_group)
        layout.addWidget(self.config_group)

        # 按钮
        button_layout = QHBoxLayout()

        save_btn = QPushButton("\u4fdd\u5b58")
        save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("\u53d6\u6d88")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        reset_btn = QPushButton("\u91cd\u7f6e")
        reset_btn.clicked.connect(self.reset_config)
        button_layout.addWidget(reset_btn)

        layout.addLayout(button_layout)

    def load_config(self):
        """加载配置"""
        try:
            plugin_instance = self._get_plugin_instance()
            self.plugin_instance = plugin_instance

            if plugin_instance and self._is_configurable_plugin(plugin_instance):
                self._load_configurable_plugin_config(plugin_instance)
            else:
                self._load_traditional_config()

        except Exception as e:
            logger.error(f"\u52a0\u8f7d\u63d2\u4ef6\u914d\u7f6e\u5931\u8d25: {e}")
            QMessageBox.warning(self, "\u8b66\u544a", f"\u52a0\u8f7d\u914d\u7f6e\u5931\u8d25: {e}")

    def _get_plugin_instance(self):
        """尝试获取插件实例"""
        try:
            known_plugins = {
                'fmp_sentiment': 'plugins.sentiment_data_sources.fmp_sentiment_plugin.FMPSentimentPlugin',
                'vix_sentiment': 'plugins.sentiment_data_sources.vix_sentiment_plugin.VIXSentimentPlugin',
                'news_sentiment': 'plugins.sentiment_data_sources.news_sentiment_plugin.NewsSentimentPlugin',
            }

            plugin_path = known_plugins.get(self.plugin_info.name)

            if plugin_path:
                module_path, class_name = plugin_path.rsplit('.', 1)
                module = __import__(module_path, fromlist=[class_name])
                plugin_class = getattr(module, class_name)
                return plugin_class()

            return None
        except Exception:
            return None

    def _is_configurable_plugin(self, plugin_instance):
        """检查是否为ConfigurablePlugin"""
        try:
            from plugins.sentiment_data_sources.config_base import ConfigurablePlugin
            return isinstance(plugin_instance, ConfigurablePlugin)
        except ImportError:
            return False

    def _load_configurable_plugin_config(self, plugin_instance):
        """加载ConfigurablePlugin类型的配置"""
        try:
            config_schema = plugin_instance.get_config_schema()
            current_config = plugin_instance.load_config()

            row = 0
            for field in config_schema:
                label_text = field.display_name
                if field.required:
                    label_text += " *"
                label = QLabel(f"{label_text}:")
                self.config_layout.addWidget(label, row, 0)

                widget = self._create_field_control(field, current_config.get(field.name, field.default_value))
                if widget:
                    self.config_layout.addWidget(widget, row, 1)
                    self.config_widgets[field.name] = widget
                    row += 1

        except Exception as e:
            logger.error(f"\u52a0\u8f7d\u914d\u7f6e\u5931\u8d25: {e}")
            raise

    def _create_field_control(self, field, value):
        """创建配置字段控件"""
        try:
            if field.field_type == "boolean":
                widget = QCheckBox()
                widget.setChecked(bool(value))
                return widget
            elif field.field_type == "number":
                if field.min_value is not None and field.max_value is not None and isinstance(field.default_value, int):
                    widget = QSpinBox()
                    widget.setMinimum(int(field.min_value))
                    widget.setMaximum(int(field.max_value))
                    widget.setValue(int(value) if value is not None else 0)
                else:
                    widget = QDoubleSpinBox()
                    widget.setDecimals(3)
                    widget.setMinimum(field.min_value if field.min_value is not None else -999999.0)
                    widget.setMaximum(field.max_value if field.max_value is not None else 999999.0)
                    widget.setValue(float(value) if value is not None else 0.0)
                return widget
            elif field.field_type == "select":
                widget = QComboBox()
                if field.options:
                    widget.addItems(field.options)
                    if value in field.options:
                        widget.setCurrentText(str(value))
                return widget
            else:
                widget = QLineEdit()
                widget.setText(str(value))
                return widget
        except Exception:
            return None

    def _load_traditional_config(self):
        """加载传统字典配置"""
        config = self.plugin_info.config

        if not config:
            hint_label = QLabel("\u6b64\u63d2\u4ef6\u6ca1\u6709\u53ef\u914d\u7f6e\u7684\u53c2\u6570")
            hint_label.setStyleSheet("color: #666; font-style: italic; padding: 20px;")
            hint_label.setAlignment(Qt.AlignCenter)
            self.config_layout.addWidget(hint_label, 0, 0, 1, 2)
            return

        row = 0
        for key, value in config.items():
            if key.startswith('_'):
                continue

            label = QLabel(f"{key}:")
            self.config_layout.addWidget(label, row, 0)

            if isinstance(value, bool):
                widget = QCheckBox()
                widget.setChecked(value)
            elif isinstance(value, int):
                widget = QSpinBox()
                widget.setRange(-999999, 999999)
                widget.setValue(value)
            elif isinstance(value, float):
                widget = QDoubleSpinBox()
                widget.setRange(-999999.0, 999999.0)
                widget.setValue(value)
            else:
                widget = QLineEdit()
                widget.setText(str(value))

            self.config_layout.addWidget(widget, row, 1)
            self.config_widgets[key] = widget
            row += 1

    def save_config(self):
        """保存配置"""
        try:
            new_config = {}
            for key, widget in self.config_widgets.items():
                if isinstance(widget, QCheckBox):
                    new_config[key] = widget.isChecked()
                elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    new_config[key] = widget.value()
                elif isinstance(widget, QComboBox):
                    new_config[key] = widget.currentText()
                elif isinstance(widget, QLineEdit):
                    new_config[key] = widget.text().strip()

            if hasattr(self, 'plugin_instance') and self.plugin_instance:
                is_valid, error_msg = self.plugin_instance.validate_config(new_config)
                if not is_valid:
                    QMessageBox.warning(self, "\u914d\u7f6e\u9a8c\u8bc1\u5931\u8d25", error_msg)
                    return
                success = self.plugin_instance.save_config(new_config)
                if success:
                    QMessageBox.information(self, "\u6210\u529f", "\u63d2\u4ef6\u914d\u7f6e\u5df2\u4fdd\u5b58")
                    self.accept()
                else:
                    QMessageBox.warning(self, "\u4fdd\u5b58\u5931\u8d25", "\u65e0\u6cd5\u4fdd\u5b58\u63d2\u4ef6\u914d\u7f6e")
            else:
                self.plugin_info.config.update(new_config)
                if hasattr(self.plugin_manager, 'update_plugin_config'):
                    self.plugin_manager.update_plugin_config(self.plugin_info.name, new_config)
                QMessageBox.information(self, "\u6210\u529f", "\u914d\u7f6e\u5df2\u4fdd\u5b58")
                self.accept()

        except Exception as e:
            logger.error(f"\u4fdd\u5b58\u914d\u7f6e\u5931\u8d25: {e}")
            QMessageBox.critical(self, "\u9519\u8bef", f"\u4fdd\u5b58\u914d\u7f6e\u5931\u8d25: {e}")

    def reset_config(self):
        """重置配置"""
        reply = QMessageBox.question(self, "\u786e\u8ba4", "\u786e\u5b9a\u8981\u91cd\u7f6e\u914d\u7f6e\u5417\uff1f",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.load_config()


# =============================================================================
# 统一插件管理对话框（核心主类）
# =============================================================================

class PluginManagerDialogUnified(BaseDialog):
    """统一插件管理对话框
    
    整合了基础插件管理和增强插件管理的所有功能，提供：
    - 已安装插件管理（安装、卸载、启用、禁用、配置）
    - 数据源插件管理（健康检查、优先级、路由配置）
    - 指标与策略插件管理
    - 插件市场浏览与安装
    - 性能监控与统计
    - 操作日志查看与导出
    """

    # 信号定义
    plugin_enabled = pyqtSignal(str)
    plugin_disabled = pyqtSignal(str)
    plugin_configured = pyqtSignal(str)
    plugin_error = pyqtSignal(str, str)

    def __init__(self, plugin_manager: PluginManager, parent=None):
        super().__init__(
            parent,
            title="FactorWeave-Quant \u63d2\u4ef6\u7ba1\u7406\u5668",
            size=(1100, 750),
            settings_key="PluginManagerDialogUnified",
        )
        self.plugin_manager = plugin_manager

        if not self.plugin_manager:
            raise ValueError("\u63d2\u4ef6\u7ba1\u7406\u5668\u4e0d\u80fd\u4e3aNone")

        # 内部状态
        self.plugin_widgets = {}
        self.is_loading = False
        self.last_error = None

        # 数据库服务
        self.db_service = None
        if DB_SERVICE_AVAILABLE:
            try:
                self.db_service = get_plugin_database_service()
                logger.info("\u63d2\u4ef6\u6570\u636e\u5e93\u670d\u52a1\u96c6\u6210\u6210\u529f")
            except Exception as e:
                logger.error(f"\u63d2\u4ef6\u6570\u636e\u5e93\u670d\u52a1\u521d\u59cb\u5316\u5931\u8d25: {e}")

        # 统一数据管理器
        self.uni_data_manager = None
        if UNI_DATA_MANAGER_AVAILABLE:
            try:
                self.uni_data_manager = get_uni_plugin_data_manager()
            except Exception as e:
                logger.error(f"\u7edf\u4e00\u6570\u636e\u7ba1\u7406\u5668\u521d\u59cb\u5316\u5931\u8d25: {e}")

        # 定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_plugins)

        # UI 初始化
        self.init_ui()
        self.safe_load_plugins()

        if self.plugin_widgets:
            self.timer.start(10000)

    def init_ui(self):
        """初始化主界面"""

        # 窗口样式
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
                font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #dee2e6;
                background-color: white;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #e9ecef;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid #dee2e6;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 1px solid white;
            }
            QToolBar {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 5px;
                spacing: 5px;
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 7px 14px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0056b3; }
            QPushButton:pressed { background-color: #004085; }
            QLineEdit, QComboBox {
                padding: 6px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: white;
            }
            QStatusBar {
                background-color: #f8f9fa;
                border-top: 1px solid #dee2e6;
            }
        """)

        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)

        # 选项卡
        self.tab_widget = QTabWidget()

        # Tab 1: 已安装插件
        self.plugins_tab = self.create_plugins_tab()
        self.tab_widget.addTab(self.plugins_tab, "\u5df2\u5b89\u88c5\u63d2\u4ef6")

        # Tab 2: 数据源管理
        self.data_source_tab = self.create_data_source_tab()
        self.tab_widget.addTab(self.data_source_tab, "\u6570\u636e\u6e90\u7ba1\u7406")

        # Tab 3: 指标与策略
        self.indicator_strategy_tab = self.create_indicator_strategy_tab()
        self.tab_widget.addTab(self.indicator_strategy_tab, "\u6307\u6807/\u7b56\u7565")

        # Tab 4: 插件市场
        self.market_tab = self.create_market_tab()
        self.tab_widget.addTab(self.market_tab, "\u63d2\u4ef6\u5e02\u573a")

        # Tab 5: 性能监控
        self.monitor_tab = self.create_monitor_tab()
        self.tab_widget.addTab(self.monitor_tab, "\u6027\u80fd\u76d1\u63a7")

        # Tab 6: 日志
        self.logs_tab = self.create_logs_tab()
        self.tab_widget.addTab(self.logs_tab, "\u65e5\u5fd7")

        layout.addWidget(self.tab_widget)

        # 状态栏
        self.status_bar = QStatusBar()
        layout.addWidget(self.status_bar)
        self.update_status()

    def create_toolbar(self) -> QToolBar:
        """创建工具栏"""
        toolbar = QToolBar()

        refresh_action = QAction("\u5237\u65b0", self)
        refresh_action.triggered.connect(self.refresh_plugins)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()

        enable_all_action = QAction("\u5168\u90e8\u542f\u7528", self)
        enable_all_action.triggered.connect(self.enable_all_plugins)
        toolbar.addAction(enable_all_action)

        disable_all_action = QAction("\u5168\u90e8\u7981\u7528", self)
        disable_all_action.triggered.connect(self.disable_all_plugins)
        toolbar.addAction(disable_all_action)

        toolbar.addSeparator()

        export_action = QAction("\u5bfc\u51fa\u914d\u7f6e", self)
        export_action.triggered.connect(self.export_all_configs)
        toolbar.addAction(export_action)

        import_action = QAction("\u5bfc\u5165\u914d\u7f6e", self)
        import_action.triggered.connect(self.import_all_configs)
        toolbar.addAction(import_action)

        return toolbar

    def create_plugins_tab(self) -> QWidget:
        """创建已安装插件选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("\u641c\u7d22:"))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("\u8f93\u5165\u63d2\u4ef6\u540d\u79f0\u6216\u63cf\u8ff0...")
        self.search_edit.textChanged.connect(self.filter_plugins)
        search_layout.addWidget(self.search_edit)

        search_layout.addWidget(QLabel("\u7c7b\u578b:"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("\u5168\u90e8", "")
        for plugin_type in PluginType:
            self.type_combo.addItem(plugin_type.value, plugin_type.value)
        self.type_combo.currentTextChanged.connect(self.filter_plugins)
        search_layout.addWidget(self.type_combo)

        search_layout.addWidget(QLabel("\u72b6\u6001:"))
        self.status_combo = QComboBox()
        self.status_combo.addItem("\u5168\u90e8", "")
        for status in PluginStatus:
            self.status_combo.addItem(status.value, status.value)
        self.status_combo.currentTextChanged.connect(self.filter_plugins)
        search_layout.addWidget(self.status_combo)

        layout.addLayout(search_layout)

        # 插件列表
        self.plugins_list = QListWidget()
        layout.addWidget(self.plugins_list)

        return widget

    def create_data_source_tab(self) -> QWidget:
        """创建数据源管理选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        desc_label = QLabel("\u7ba1\u7406\u6570\u636e\u6e90\u63d2\u4ef6\uff0c\u5305\u62ec\u5065\u5eb7\u68c0\u67e5\u3001\u4f18\u5148\u7ea7\u8bbe\u7f6e\u548c\u8def\u7531\u914d\u7f6e\u3002")
        desc_label.setStyleSheet("color: #666; font-style: italic; margin-bottom: 10px;")
        layout.addWidget(desc_label)

        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        test_all_btn = QPushButton("\u6d4b\u8bd5\u6240\u6709\u8fde\u63a5")
        test_all_btn.clicked.connect(self.test_all_data_sources)
        toolbar_layout.addWidget(test_all_btn)

        refresh_btn = QPushButton("\u5237\u65b0\u72b6\u6001")
        refresh_btn.clicked.connect(self.refresh_data_source_status)
        toolbar_layout.addWidget(refresh_btn)

        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)

        # 数据源表格
        self.data_source_table = QTableWidget()
        self.data_source_table.setColumnCount(6)
        self.data_source_table.setHorizontalHeaderLabels([
            "\u63d2\u4ef6\u540d\u79f0", "\u72b6\u6001", "\u652f\u6301\u8d44\u4ea7", "\u5065\u5eb7\u5206\u6570", "\u4f18\u5148\u7ea7", "\u64cd\u4f5c"
        ])
        self.data_source_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.data_source_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.data_source_table)

        return widget

    def create_indicator_strategy_tab(self) -> QWidget:
        """创建指标与策略选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        desc_label = QLabel("\u7ba1\u7406\u6307\u6807\u548c\u7b56\u7565\u63d2\u4ef6\uff0c\u5305\u62ec\u53c2\u6570\u914d\u7f6e\u548c\u6279\u91cf\u64cd\u4f5c\u3002")
        desc_label.setStyleSheet("color: #666; font-style: italic; margin-bottom: 10px;")
        layout.addWidget(desc_label)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        config_btn = QPushButton("\u914d\u7f6e\u9009\u4e2d\u63d2\u4ef6")
        config_btn.clicked.connect(self.configure_selected_indicator)
        toolbar_layout.addWidget(config_btn)

        batch_apply_btn = QPushButton("\u6279\u91cf\u5e94\u7528")
        batch_apply_btn.clicked.connect(self.batch_apply_indicators)
        toolbar_layout.addWidget(batch_apply_btn)

        export_btn = QPushButton("\u5bfc\u51fa\u914d\u7f6e")
        export_btn.clicked.connect(self.export_indicator_configs)
        toolbar_layout.addWidget(export_btn)

        import_btn = QPushButton("\u5bfc\u5165\u914d\u7f6e")
        import_btn.clicked.connect(self.import_indicator_configs)
        toolbar_layout.addWidget(import_btn)

        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)

        # 指标/策略列表
        self.indicator_strategy_list = QListWidget()
        layout.addWidget(self.indicator_strategy_list)

        return widget

    def create_market_tab(self) -> QWidget:
        """创建插件市场选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("\u641c\u7d22:"))

        self.market_search_edit = QLineEdit()
        self.market_search_edit.setPlaceholderText("\u8f93\u5165\u63d2\u4ef6\u540d\u79f0\u6216\u5173\u952e\u8bcd...")
        search_layout.addWidget(self.market_search_edit)

        search_btn = QPushButton("\u641c\u7d22")
        search_btn.clicked.connect(self.search_market_plugins)
        search_layout.addWidget(search_btn)

        layout.addLayout(search_layout)

        # 分类过滤
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("\u5206\u7c7b:"))

        self.market_category_combo = QComboBox()
        self.market_category_combo.addItems(["\u5168\u90e8", "\u6570\u636e\u6e90", "\u6280\u672f\u6307\u6807", "\u7b56\u7565\u5de5\u5177", "UI \u589e\u5f3a", "\u5b9e\u7528\u5de5\u5177"])
        category_layout.addWidget(self.market_category_combo)
        category_layout.addStretch()

        refresh_btn = QPushButton("\u5237\u65b0\u5e02\u573a")
        refresh_btn.clicked.connect(self.refresh_market)
        category_layout.addWidget(refresh_btn)

        layout.addLayout(category_layout)

        # 插件卡片区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        self.market_plugins_widget = QWidget()
        self.market_plugins_layout = QVBoxLayout(self.market_plugins_widget)

        scroll_area.setWidget(self.market_plugins_widget)
        layout.addWidget(scroll_area)

        # 加载示例插件
        self.load_market_plugins()

        return widget

    def create_monitor_tab(self) -> QWidget:
        """创建性能监控选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 统计信息
        stats_group = QGroupBox("\u7edf\u8ba1\u4fe1\u606f")
        stats_layout = QGridLayout(stats_group)

        self.total_plugins_label = QLabel("0")
        self.enabled_plugins_label = QLabel("0")
        self.disabled_plugins_label = QLabel("0")
        self.error_plugins_label = QLabel("0")

        stats_layout.addWidget(QLabel("\u603b\u63d2\u4ef6\u6570:"), 0, 0)
        stats_layout.addWidget(self.total_plugins_label, 0, 1)

        stats_layout.addWidget(QLabel("\u5df2\u542f\u7528:"), 1, 0)
        stats_layout.addWidget(self.enabled_plugins_label, 1, 1)

        stats_layout.addWidget(QLabel("\u5df2\u7981\u7528:"), 2, 0)
        stats_layout.addWidget(self.disabled_plugins_label, 2, 1)

        stats_layout.addWidget(QLabel("\u9519\u8bef:"), 3, 0)
        stats_layout.addWidget(self.error_plugins_label, 3, 1)

        layout.addWidget(stats_group)

        # 性能信息
        perf_group = QGroupBox("\u6027\u80fd\u76d1\u63a7")
        perf_layout = QVBoxLayout(perf_group)

        self.perf_text = QTextEdit()
        self.perf_text.setReadOnly(True)
        perf_layout.addWidget(self.perf_text)

        layout.addWidget(perf_group)

        return widget

    def create_logs_tab(self) -> QWidget:
        """创建日志选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        control_layout = QHBoxLayout()

        clear_btn = QPushButton("\u6e05\u7a7a\u65e5\u5fd7")
        clear_btn.clicked.connect(self.clear_logs)
        control_layout.addWidget(clear_btn)

        export_btn = QPushButton("\u5bfc\u51fa\u65e5\u5fd7")
        export_btn.clicked.connect(self.export_logs)
        control_layout.addWidget(export_btn)

        control_layout.addStretch()

        control_layout.addWidget(QLabel("\u7ea7\u522b:"))
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setCurrentText("INFO")
        control_layout.addWidget(self.log_level_combo)

        layout.addLayout(control_layout)

        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setFont(QFont("Courier", 9))
        layout.addWidget(self.logs_text)

        return widget

    def safe_load_plugins(self):
        """安全加载插件列表"""
        try:
            self.is_loading = True
            self.load_plugins()
        except Exception as e:
            logger.error(f"\u5b89\u5168\u52a0\u8f7d\u63d2\u4ef6\u5931\u8d25: {e}")
            self.last_error = str(e)
            self.add_log(f"\u52a0\u8f7d\u63d2\u4ef6\u5217\u8868\u5931\u8d25: {e}")
        finally:
            self.is_loading = False

    def load_plugins(self):
        """加载已安装插件列表"""
        try:
            self.plugins_list.clear()
            self.plugin_widgets.clear()

            plugins = self.plugin_manager.get_all_plugin_metadata()

            for plugin_name, metadata in plugins.items():
                plugin_status = self._get_actual_plugin_status(plugin_name, metadata)

                plugin_info = PluginInfo(
                    name=plugin_name,
                    version=metadata.get('version', '1.0.0'),
                    description=metadata.get('description', ''),
                    author=metadata.get('author', ''),
                    path=metadata.get('path', ''),
                    status=plugin_status,
                    config=metadata.get('config', {}),
                    dependencies=metadata.get('dependencies', [])
                )

                plugin_widget = PluginStatusWidget(plugin_info)
                list_item = QListWidgetItem()
                list_item.setSizeHint(plugin_widget.sizeHint())

                self.plugins_list.addItem(list_item)
                self.plugins_list.setItemWidget(list_item, plugin_widget)

                self.plugin_widgets[plugin_name] = plugin_widget

            self.update_status()
            self.update_monitor_stats()

        except Exception as e:
            logger.error(f"\u52a0\u8f7d\u63d2\u4ef6\u5217\u8868\u5931\u8d25: {e}")
            QMessageBox.critical(self, "\u9519\u8bef", f"\u52a0\u8f7d\u63d2\u4ef6\u5217\u8868\u5931\u8d25: {e}")

    def _get_actual_plugin_status(self, plugin_name: str, metadata: dict) -> PluginStatus:
        """获取插件的实际状态"""
        try:
            if self.db_service:
                db_status = self.db_service.get_plugin_status(plugin_name)
                if db_status:
                    return self._convert_db_status_to_ui_status(db_status)
                else:
                    from db.models.plugin_models import PluginStatus as DbPluginStatus
                    self.db_service.register_plugin_from_metadata(plugin_name, metadata)
                    self.db_service.update_plugin_status(plugin_name, DbPluginStatus.DISABLED, "\u65b0\u53d1\u73b0\u63d2\u4ef6\uff0c\u9ed8\u8ba4\u7981\u7528")
                    return PluginStatus.DISABLED

            return self._determine_runtime_status(plugin_name)

        except Exception as e:
            logger.warning(f"\u83b7\u53d6\u63d2\u4ef6\u72b6\u6001\u5931\u8d25 {plugin_name}: {e}")
            return PluginStatus.UNLOADED

    def _convert_db_status_to_ui_status(self, db_status) -> PluginStatus:
        """将数据库状态转换为UI状态"""
        if isinstance(db_status, PluginStatus):
            return db_status

        status_value = db_status.value if hasattr(db_status, 'value') else str(db_status)

        status_mapping = {
            'unloaded': PluginStatus.UNLOADED,
            'loaded': PluginStatus.LOADED,
            'enabled': PluginStatus.ENABLED,
            'disabled': PluginStatus.DISABLED,
            'error': PluginStatus.ERROR,
        }

        return status_mapping.get(status_value.lower(), PluginStatus.UNLOADED)

    def _determine_runtime_status(self, plugin_name: str) -> PluginStatus:
        """确定插件的运行时状态"""
        try:
            if hasattr(self.plugin_manager, 'enhanced_plugins') and plugin_name in self.plugin_manager.enhanced_plugins:
                enhanced_plugin = self.plugin_manager.enhanced_plugins[plugin_name]
                return enhanced_plugin.status

            if hasattr(self.plugin_manager, 'plugin_instances'):
                if plugin_name in self.plugin_manager.plugin_instances:
                    if hasattr(self.plugin_manager, 'is_plugin_enabled'):
                        return PluginStatus.ENABLED if self.plugin_manager.is_plugin_enabled(plugin_name) else PluginStatus.DISABLED
                    else:
                        return PluginStatus.LOADED
                else:
                    return PluginStatus.UNLOADED

            if hasattr(self.plugin_manager, 'is_plugin_loaded'):
                return PluginStatus.ENABLED if self.plugin_manager.is_plugin_loaded(plugin_name) else PluginStatus.UNLOADED

            return PluginStatus.UNLOADED

        except Exception as e:
            logger.warning(f"\u786e\u5b9a\u8fd0\u884c\u65f6\u72b6\u6001\u5931\u8d25 {plugin_name}: {e}")
            return PluginStatus.UNLOADED

    def refresh_plugins(self):
        """刷新插件列表"""
        self.load_plugins()
        self.update_monitor_stats()

    def filter_plugins(self):
        """过滤插件"""
        search_text = self.search_edit.text().lower()
        plugin_type = self.type_combo.currentData()
        status = self.status_combo.currentData()

        for i in range(self.plugins_list.count()):
            item = self.plugins_list.item(i)
            widget = self.plugins_list.itemWidget(item)

            if widget and isinstance(widget, PluginStatusWidget):
                plugin_info = widget.plugin_info

                text_match = (search_text in plugin_info.name.lower() or
                              search_text in (plugin_info.description or '').lower())

                type_match = (not plugin_type or
                              (plugin_info.plugin_type and plugin_info.plugin_type.value == plugin_type))

                status_match = (not status or plugin_info.status.value == status)

                item.setHidden(not (text_match and type_match and status_match))

    def enable_plugin(self, plugin_name: str):
        """启用插件"""
        try:
            if hasattr(self.plugin_manager, 'enable_plugin'):
                success = self.plugin_manager.enable_plugin(plugin_name)
                if success:
                    self.plugin_enabled.emit(plugin_name)
                    self.add_log(f" \u63d2\u4ef6 '{plugin_name}' \u5df2\u6210\u529f\u542f\u7528")

                    if self.db_service:
                        from db.models.plugin_models import PluginStatus as DbPluginStatus
                        self.db_service.update_plugin_status(
                            plugin_name, DbPluginStatus.ENABLED, "\u7528\u6237\u624b\u52a8\u542f\u7528"
                        )

                    self._immediate_update_plugin_status(plugin_name, PluginStatus.ENABLED)
                    QTimer.singleShot(100, self.refresh_plugins)
                else:
                    self.add_log(f" \u63d2\u4ef6 '{plugin_name}' \u542f\u7528\u5931\u8d25")
                    QMessageBox.warning(self, "\u8b66\u544a", f"\u63d2\u4ef6 '{plugin_name}' \u542f\u7528\u5931\u8d25")
            else:
                if hasattr(self.plugin_manager, 'load_plugin'):
                    success = self.plugin_manager.load_plugin(plugin_name)
                    if success:
                        self.plugin_enabled.emit(plugin_name)
                        self.add_log(f" \u63d2\u4ef6 '{plugin_name}' \u5df2\u52a0\u8f7d")
                        self.refresh_plugins()
        except Exception as e:
            logger.error(f"\u542f\u7528\u63d2\u4ef6\u5931\u8d25: {e}")
            self.add_log(f" \u542f\u7528\u63d2\u4ef6 '{plugin_name}' \u65f6\u53d1\u751f\u9519\u8bef: {str(e)}")
            QMessageBox.critical(self, "\u9519\u8bef", f"\u542f\u7528\u63d2\u4ef6\u5931\u8d25: {e}")

    def disable_plugin(self, plugin_name: str):
        """禁用插件"""
        try:
            if hasattr(self.plugin_manager, 'disable_plugin'):
                success = self.plugin_manager.disable_plugin(plugin_name)
                if success:
                    self.plugin_disabled.emit(plugin_name)
                    self.add_log(f" \u63d2\u4ef6 '{plugin_name}' \u5df2\u6210\u529f\u7981\u7528")

                    if self.db_service:
                        from db.models.plugin_models import PluginStatus as DbPluginStatus
                        self.db_service.update_plugin_status(
                            plugin_name, DbPluginStatus.DISABLED, "\u7528\u6237\u624b\u52a8\u7981\u7528"
                        )

                    self._immediate_update_plugin_status(plugin_name, PluginStatus.DISABLED)
                    QTimer.singleShot(100, self.refresh_plugins)
                else:
                    self.add_log(f" \u63d2\u4ef6 '{plugin_name}' \u7981\u7528\u5931\u8d25")
                    QMessageBox.warning(self, "\u8b66\u544a", f"\u63d2\u4ef6 '{plugin_name}' \u7981\u7528\u5931\u8d25")
            else:
                if hasattr(self.plugin_manager, 'unload_plugin'):
                    success = self.plugin_manager.unload_plugin(plugin_name)
                    if success:
                        self.plugin_disabled.emit(plugin_name)
                        self.add_log(f" \u63d2\u4ef6 '{plugin_name}' \u5df2\u5378\u8f7d")
                        self.refresh_plugins()
        except Exception as e:
            logger.error(f"\u7981\u7528\u63d2\u4ef6\u5931\u8d25: {e}")
            self.add_log(f" \u7981\u7528\u63d2\u4ef6 '{plugin_name}' \u65f6\u53d1\u751f\u9519\u8bef: {str(e)}")
            QMessageBox.critical(self, "\u9519\u8bef", f"\u7981\u7528\u63d2\u4ef6\u5931\u8d25: {e}")

    def configure_plugin(self, plugin_name: str):
        """配置插件"""
        try:
            if plugin_name in self.plugin_widgets:
                plugin_widget = self.plugin_widgets[plugin_name]
                plugin_info = plugin_widget.plugin_info

                config_dialog = PluginConfigDialog(plugin_info, self.plugin_manager, self)
                if config_dialog.exec_() == QDialog.Accepted:
                    self.plugin_configured.emit(plugin_name)
                    self.add_log(f"\u63d2\u4ef6 {plugin_name} \u914d\u7f6e\u5df2\u66f4\u65b0")

        except Exception as e:
            logger.error(f"\u914d\u7f6e\u63d2\u4ef6\u5931\u8d25: {e}")
            QMessageBox.critical(self, "\u9519\u8bef", f"\u914d\u7f6e\u63d2\u4ef6\u5931\u8d25: {e}")

    def enable_all_plugins(self):
        """启用所有插件"""
        reply = QMessageBox.question(self, "\u786e\u8ba4", "\u786e\u5b9a\u8981\u542f\u7528\u6240\u6709\u63d2\u4ef6\u5417\uff1f",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._batch_enable_plugins(list(self.plugin_widgets.keys()))

    def disable_all_plugins(self):
        """禁用所有插件"""
        reply = QMessageBox.question(self, "\u786e\u8ba4", "\u786e\u5b9a\u8981\u7981\u7528\u6240\u6709\u63d2\u4ef6\u5417\uff1f",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._batch_disable_plugins(list(self.plugin_widgets.keys()))

    def _batch_enable_plugins(self, plugin_names: list):
        """批量启用插件"""
        try:
            success_count = 0
            error_count = 0

            progress = QProgressDialog("\u6b63\u5728\u6279\u91cf\u542f\u7528\u63d2\u4ef6...", "\u53d6\u6d88", 0, len(plugin_names), self)
            progress.setWindowTitle("\u6279\u91cf\u64cd\u4f5c\u8fdb\u5ea6")
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

            for i, plugin_name in enumerate(plugin_names):
                if progress.wasCanceled():
                    break

                progress.setValue(i)
                progress.setLabelText(f"\u6b63\u5728\u542f\u7528\u63d2\u4ef6: {plugin_name}")
                QApplication.processEvents()

                try:
                    if self.db_service:
                        from db.models.plugin_models import PluginStatus as DbPluginStatus
                        self.db_service.update_plugin_status(
                            plugin_name, DbPluginStatus.ENABLED, "\u6279\u91cf\u542f\u7528\u64cd\u4f5c"
                        )

                    self._immediate_update_plugin_status(plugin_name, PluginStatus.ENABLED)
                    success_count += 1
                    self.add_log(f" \u63d2\u4ef6 '{plugin_name}' \u5df2\u542f\u7528")

                except Exception as e:
                    error_count += 1
                    self.add_log(f" \u542f\u7528\u63d2\u4ef6 '{plugin_name}' \u5931\u8d25: {e}")

            progress.setValue(len(plugin_names))
            progress.close()

            QTimer.singleShot(100, self.refresh_plugins)

            if error_count == 0:
                self.add_log(f" \u6279\u91cf\u542f\u7528\u5b8c\u6210\uff0c\u6210\u529f\u542f\u7528 {success_count} \u4e2a\u63d2\u4ef6")
            else:
                self.add_log(f" \u6279\u91cf\u542f\u7528\u5b8c\u6210\uff0c\u6210\u529f {success_count} \u4e2a\uff0c\u5931\u8d25 {error_count} \u4e2a")

        except Exception as e:
            logger.error(f"\u6279\u91cf\u542f\u7528\u63d2\u4ef6\u5931\u8d25: {e}")
            self.add_log(f" \u6279\u91cf\u542f\u7528\u64cd\u4f5c\u5931\u8d25: {e}")

    def _batch_disable_plugins(self, plugin_names: list):
        """批量禁用插件"""
        try:
            success_count = 0
            error_count = 0

            progress = QProgressDialog("\u6b63\u5728\u6279\u91cf\u7981\u7528\u63d2\u4ef6...", "\u53d6\u6d88", 0, len(plugin_names), self)
            progress.setWindowTitle("\u6279\u91cf\u64cd\u4f5c\u8fdb\u5ea6")
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

            for i, plugin_name in enumerate(plugin_names):
                if progress.wasCanceled():
                    break

                progress.setValue(i)
                progress.setLabelText(f"\u6b63\u5728\u7981\u7528\u63d2\u4ef6: {plugin_name}")
                QApplication.processEvents()

                try:
                    if self.db_service:
                        from db.models.plugin_models import PluginStatus as DbPluginStatus
                        self.db_service.update_plugin_status(
                            plugin_name, DbPluginStatus.DISABLED, "\u6279\u91cf\u7981\u7528\u64cd\u4f5c"
                        )

                    self._immediate_update_plugin_status(plugin_name, PluginStatus.DISABLED)
                    success_count += 1
                    self.add_log(f" \u63d2\u4ef6 '{plugin_name}' \u5df2\u7981\u7528")

                except Exception as e:
                    error_count += 1
                    self.add_log(f" \u7981\u7528\u63d2\u4ef6 '{plugin_name}' \u5931\u8d25: {e}")

            progress.setValue(len(plugin_names))
            progress.close()

            QTimer.singleShot(100, self.refresh_plugins)

            if error_count == 0:
                self.add_log(f" \u6279\u91cf\u7981\u7528\u5b8c\u6210\uff0c\u6210\u529f\u7981\u7528 {success_count} \u4e2a\u63d2\u4ef6")
            else:
                self.add_log(f" \u6279\u91cf\u7981\u7528\u5b8c\u6210\uff0c\u6210\u529f {success_count} \u4e2a\uff0c\u5931\u8d25 {error_count} \u4e2a")

        except Exception as e:
            logger.error(f"\u6279\u91cf\u7981\u7528\u63d2\u4ef6\u5931\u8d25: {e}")
            self.add_log(f" \u6279\u91cf\u7981\u7528\u64cd\u4f5c\u5931\u8d25: {e}")

    def _immediate_update_plugin_status(self, plugin_name: str, new_status: PluginStatus):
        """立即更新插件状态显示"""
        try:
            if plugin_name in self.plugin_widgets:
                widget = self.plugin_widgets[plugin_name]
                widget._update_status_display(new_status)
                self.add_log(f" UI\u5df2\u66f4\u65b0\u63d2\u4ef6 '{plugin_name}' \u72b6\u6001\u4e3a: {self._get_status_text(new_status)}", "DEBUG")

            self.update_monitor_stats()
            self.update_status()

        except Exception as e:
            logger.error(f"\u7acb\u5373\u66f4\u65b0\u63d2\u4ef6\u72b6\u6001\u5931\u8d25: {e}")

    def _get_status_text(self, status: PluginStatus) -> str:
        """获取状态文本"""
        text_map = {
            PluginStatus.UNLOADED: "\u672a\u52a0\u8f7d",
            PluginStatus.LOADED: "\u5df2\u52a0\u8f7d",
            PluginStatus.ENABLED: "\u5df2\u542f\u7528",
            PluginStatus.DISABLED: "\u5df2\u7981\u7528",
            PluginStatus.ERROR: "\u9519\u8bef"
        }
        return text_map.get(status, "\u672a\u77e5")

    # ========================================================================
    # 数据源管理功能
    # ========================================================================

    def refresh_data_source_status(self):
        """刷新数据源状态"""
        try:
            if not self.uni_data_manager and hasattr(self.plugin_manager, 'get_data_source_plugins'):
                ds_plugins = self.plugin_manager.get_data_source_plugins()
            else:
                ds_plugins = {}

            self.data_source_table.setRowCount(len(ds_plugins))

            for row, (source_id, adapter) in enumerate(ds_plugins.items()):
                self._populate_data_source_row(row, source_id, adapter)

            self.add_log(" \u6570\u636e\u6e90\u72b6\u6001\u5df2\u5237\u65b0")

        except Exception as e:
            logger.error(f"\u5237\u65b0\u6570\u636e\u6e90\u72b6\u6001\u5931\u8d25: {e}")
            QMessageBox.critical(self, "\u9519\u8bef", f"\u5237\u65b0\u6570\u636e\u6e90\u72b6\u6001\u5931\u8d25: {e}")

    def _populate_data_source_row(self, row: int, source_id: str, adapter):
        """填充数据源表格行"""
        try:
            plugin_info = adapter.get_plugin_info() if hasattr(adapter, 'get_plugin_info') else None
            name = getattr(plugin_info, 'name', source_id) if plugin_info else source_id

            is_connected = False
            status_text = "\u672a\u8fde\u63a5"

            if hasattr(adapter, 'health_check'):
                health_result = adapter.health_check()
                if hasattr(health_result, 'is_healthy') and health_result.is_healthy:
                    is_connected = True
                    status_text = "\u6d3b\u8dc3"
                else:
                    status_text = getattr(health_result, 'error_message', "\u5065\u5eb7\u68c0\u67e5\u5931\u8d25")

            # 插件名称
            self.data_source_table.setItem(row, 0, QTableWidgetItem(name))

            # 状态
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor("#28a745" if is_connected else "#dc3545"))
            self.data_source_table.setItem(row, 1, status_item)

            # 支持资产
            assets = "\u901a\u7528"
            if plugin_info and hasattr(plugin_info, 'supported_asset_types'):
                asset_types = plugin_info.supported_asset_types
                if asset_types:
                    assets = ", ".join([getattr(a, 'value', str(a)) for a in asset_types])
            self.data_source_table.setItem(row, 2, QTableWidgetItem(assets))

            # 健康分数
            health_score = "0.85" if is_connected else "0.10"
            if hasattr(adapter, 'health_score'):
                health_score = f"{adapter.health_score:.2f}"
            self.data_source_table.setItem(row, 3, QTableWidgetItem(health_score))

            # 优先级
            self.data_source_table.setItem(row, 4, QTableWidgetItem(str(row + 1)))

            # 操作按钮
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(2, 2, 2, 2)

            test_btn = QPushButton("\u6d4b\u8bd5")
            test_btn.setStyleSheet("background-color: #17a2b8; font-size: 10px; padding: 3px 8px;")
            test_btn.clicked.connect(lambda: self.test_data_source_plugin(source_id))
            btn_layout.addWidget(test_btn)

            config_btn = QPushButton("\u914d\u7f6e")
            config_btn.setStyleSheet("background-color: #6c757d; font-size: 10px; padding: 3px 8px;")
            config_btn.clicked.connect(lambda: self.configure_data_source_plugin(source_id))
            btn_layout.addWidget(config_btn)

            self.data_source_table.setCellWidget(row, 5, btn_widget)

        except Exception as e:
            logger.error(f"\u586b\u5145\u6570\u636e\u6e90\u884c\u5931\u8d25: {e}")

    def test_data_source_plugin(self, source_id: str):
        """测试数据源插件连接"""
        try:
            self.add_log(f" \u6b63\u5728\u6d4b\u8bd5\u6570\u636e\u6e90\u63d2\u4ef6: {source_id}")

            if hasattr(self.plugin_manager, 'get_data_source_plugins'):
                ds_plugins = self.plugin_manager.get_data_source_plugins()
                if source_id in ds_plugins:
                    adapter = ds_plugins[source_id]
                    if hasattr(adapter, 'health_check'):
                        result = adapter.health_check()
                        if hasattr(result, 'is_healthy') and result.is_healthy:
                            QMessageBox.information(self, "\u6d4b\u8bd5\u6210\u529f", f"\u6570\u636e\u6e90 {source_id} \u8fde\u63a5\u6b63\u5e38")
                        else:
                            QMessageBox.warning(self, "\u6d4b\u8bd5\u5931\u8d25", f"\u6570\u636e\u6e90 {source_id} \u8fde\u63a5\u5f02\u5e38:\n{getattr(result, 'error_message', '')}")
            self.add_log(f" \u6570\u636e\u6e90 {source_id} \u6d4b\u8bd5\u5b8c\u6210")

        except Exception as e:
            logger.error(f"\u6d4b\u8bd5\u6570\u636e\u6e90\u63d2\u4ef6\u5931\u8d25: {e}")
            QMessageBox.critical(self, "\u9519\u8bef", f"\u6d4b\u8bd5\u6570\u636e\u6e90\u5931\u8d25: {e}")

    def test_all_data_sources(self):
        """测试所有数据源连接"""
        try:
            if hasattr(self.plugin_manager, 'get_data_source_plugins'):
                ds_plugins = self.plugin_manager.get_data_source_plugins()
                count = len(ds_plugins)
                if count == 0:
                    QMessageBox.information(self, "\u63d0\u793a", "\u6ca1\u6709\u53ef\u6d4b\u8bd5\u7684\u6570\u636e\u6e90\u63d2\u4ef6")
                    return

                progress = QProgressDialog("\u6b63\u5728\u6d4b\u8bd5\u6240\u6709\u6570\u636e\u6e90...", "\u53d6\u6d88", 0, count, self)
                progress.setWindowTitle("\u6d4b\u8bd5\u8fdb\u5ea6")
                progress.setWindowModality(Qt.WindowModal)
                progress.show()

                for i, (source_id, adapter) in enumerate(ds_plugins.items()):
                    if progress.wasCanceled():
                        break
                    progress.setValue(i)
                    progress.setLabelText(f"\u6b63\u5728\u6d4b\u8bd5: {source_id}")
                    QApplication.processEvents()
                    self.test_data_source_plugin(source_id)

                progress.setValue(count)
                progress.close()
                self.add_log(" \u6240\u6709\u6570\u636e\u6e90\u6d4b\u8bd5\u5b8c\u6210")

        except Exception as e:
            logger.error(f"\u6d4b\u8bd5\u6240\u6709\u6570\u636e\u6e90\u5931\u8d25: {e}")

    def configure_data_source_plugin(self, source_id: str):
        """配置数据源插件"""
        try:
            self.add_log(f" \u6253\u5f00\u6570\u636e\u6e90\u914d\u7f6e: {source_id}")
            QMessageBox.information(self, "\u63d0\u793a", f"\u914d\u7f6e\u6570\u636e\u6e90\u63d2\u4ef6: {source_id}")
        except Exception as e:
            logger.error(f"\u914d\u7f6e\u6570\u636e\u6e90\u63d2\u4ef6\u5931\u8d25: {e}")

    # ========================================================================
    # 指标/策略管理功能
    # ========================================================================

    def configure_selected_indicator(self):
        """配置选中的指标/策略插件"""
        try:
            selected = self.indicator_strategy_list.currentItem()
            if selected:
                plugin_name = selected.data(Qt.UserRole)
                self.add_log(f" \u6253\u5f00\u6307\u6807/\u7b56\u7565\u914d\u7f6e: {plugin_name}")
                QMessageBox.information(self, "\u63d0\u793a", f"\u914d\u7f6e\u6307\u6807/\u7b56\u7565\u63d2\u4ef6: {plugin_name}")
            else:
                QMessageBox.information(self, "\u63d0\u793a", "\u8bf7\u9009\u62e9\u4e00\u4e2a\u63d2\u4ef6")
        except Exception as e:
            logger.error(f"\u914d\u7f6e\u6307\u6807/\u7b56\u7565\u5931\u8d25: {e}")

    def batch_apply_indicators(self):
        """批量应用指标/策略配置"""
        try:
            count = self.indicator_strategy_list.count()
            if count == 0:
                QMessageBox.information(self, "\u63d0\u793a", "\u6ca1\u6709\u53ef\u5e94\u7528\u7684\u6307\u6807/\u7b56\u7565\u63d2\u4ef6")
                return

            reply = QMessageBox.question(self, "\u786e\u8ba4", f"\u786e\u5b9a\u8981\u6279\u91cf\u5e94\u7528 {count} \u4e2a\u63d2\u4ef6\u7684\u914d\u7f6e\u5417\uff1f",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.add_log(f" \u6279\u91cf\u5e94\u7528 {count} \u4e2a\u6307\u6807/\u7b56\u7565\u914d\u7f6e")
                QMessageBox.information(self, "\u6210\u529f", "\u6279\u91cf\u914d\u7f6e\u5e94\u7528\u6210\u529f")

        except Exception as e:
            logger.error(f"\u6279\u91cf\u5e94\u7528\u6307\u6807/\u7b56\u7565\u5931\u8d25: {e}")

    def export_indicator_configs(self):
        """导出指标/策略配置"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, "\u5bfc\u51fa\u914d\u7f6e", "", "JSON Files (*.json)")
            if file_path:
                self.add_log(f" \u5bfc\u51fa\u6307\u6807/\u7b56\u7565\u914d\u7f6e\u5230: {file_path}")
                QMessageBox.information(self, "\u6210\u529f", "\u914d\u7f6e\u5df2\u5bfc\u51fa")
        except Exception as e:
            logger.error(f"\u5bfc\u51fa\u914d\u7f6e\u5931\u8d25: {e}")

    def import_indicator_configs(self):
        """导入指标/策略配置"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, "\u5bfc\u5165\u914d\u7f6e", "", "JSON Files (*.json)")
            if file_path:
                self.add_log(f" \u4ece {file_path} \u5bfc\u5165\u6307\u6807/\u7b56\u7565\u914d\u7f6e")
                QMessageBox.information(self, "\u6210\u529f", "\u914d\u7f6e\u5df2\u5bfc\u5165")
        except Exception as e:
            logger.error(f"\u5bfc\u5165\u914d\u7f6e\u5931\u8d25: {e}")

    # ========================================================================
    # 插件市场功能
    # ========================================================================

    def load_market_plugins(self):
        """加载插件市场示例数据"""
        market_plugins = [
            {
                "name": "\u540c\u82b1\u987a\u6570\u636e\u6e90",
                "description": "\u540c\u82b1\u987a\u6570\u636e\u6e90\u63d2\u4ef6\uff0c\u63d0\u4f9b\u5b9e\u65f6\u884c\u60c5\u548c\u8d22\u52a1\u6570\u636e",
                "version": "1.0.0",
                "author": "\u793e\u533a\u5f00\u53d1\u8005",
                "downloads": 1250,
                "rating": 4.5,
                "status": "\u672a\u5b89\u88c5"
            },
            {
                "name": "Wind\u6570\u636e\u63a5\u53e3",
                "description": "Wind\u91d1\u878d\u7ec8\u7aef\u6570\u636e\u63a5\u53e3\uff0c\u652f\u6301\u4e13\u4e1a\u91d1\u878d\u6570\u636e",
                "version": "2.1.0",
                "author": "Wind\u5b98\u65b9",
                "downloads": 890,
                "rating": 4.8,
                "status": "\u672a\u5b89\u88c5"
            },
            {
                "name": "\u673a\u5668\u5b66\u4e60\u9884\u6d4b\u5668",
                "description": "\u57fa\u4e8e\u6df1\u5ea6\u5b66\u4e60\u7684\u80a1\u4ef7\u9884\u6d4b\u63d2\u4ef6",
                "version": "1.3.0",
                "author": "AI\u7814\u7a76\u56e2\u961f",
                "downloads": 2100,
                "rating": 4.2,
                "status": "\u53ef\u66f4\u65b0"
            }
        ]

        for plugin_info in market_plugins:
            plugin_card = self.create_market_plugin_card(plugin_info)
            self.market_plugins_layout.addWidget(plugin_card)

        self.market_plugins_layout.addStretch()

    def create_market_plugin_card(self, plugin_info: Dict[str, Any]) -> QWidget:
        """创建市场插件卡片"""
        card = QFrame()
        card.setFrameStyle(QFrame.StyledPanel)
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 10px;
                padding: 15px;
                margin: 5px;
            }
            QFrame:hover {
                border-color: #007bff;
            }
        """)

        layout = QHBoxLayout(card)

        info_layout = QVBoxLayout()

        name_label = QLabel(plugin_info['name'])
        name_label.setFont(QFont("Arial", 14, QFont.Bold))
        info_layout.addWidget(name_label)

        desc_label = QLabel(plugin_info['description'])
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666;")
        info_layout.addWidget(desc_label)

        meta_layout = QHBoxLayout()
        meta_layout.addWidget(QLabel(f"\u7248\u672c: {plugin_info['version']}"))
        meta_layout.addWidget(QLabel(f"\u4f5c\u8005: {plugin_info['author']}"))
        meta_layout.addWidget(QLabel(f"\u4e0b\u8f7d: {plugin_info['downloads']}"))
        meta_layout.addWidget(QLabel(f"\u8bc4\u5206: {plugin_info['rating']}"))
        meta_layout.addStretch()
        info_layout.addLayout(meta_layout)

        layout.addLayout(info_layout)

        button_layout = QVBoxLayout()

        status = plugin_info['status']
        if status == "\u672a\u5b89\u88c5":
            install_btn = QPushButton("\u5b89\u88c5")
            install_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; }")
        elif status == "\u53ef\u66f4\u65b0":
            install_btn = QPushButton("\u66f4\u65b0")
            install_btn.setStyleSheet("QPushButton { background-color: #ffc107; color: black; }")
        else:
            install_btn = QPushButton("\u5df2\u5b89\u88c5")
            install_btn.setEnabled(False)

        button_layout.addWidget(install_btn)

        details_btn = QPushButton("\u8be6\u60c5")
        button_layout.addWidget(details_btn)

        layout.addLayout(button_layout)

        return card

    def search_market_plugins(self):
        """搜索市场插件"""
        try:
            search_text = self.market_search_edit.text().lower()
            for i in range(self.market_plugins_layout.count() - 1):
                item = self.market_plugins_layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    name_label = widget.findChild(QLabel)
                    if name_label:
                        name = name_label.text().lower()
                        widget.setVisible(search_text in name or search_text == "")
            self.add_log(f" \u641c\u7d22\u5e02\u573a\u63d2\u4ef6: {search_text}")
        except Exception as e:
            logger.error(f"\u641c\u7d22\u5e02\u573a\u63d2\u4ef6\u5931\u8d25: {e}")

    def refresh_market(self):
        """刷新市场"""
        try:
            for i in reversed(range(self.market_plugins_layout.count() - 1)):
                item = self.market_plugins_layout.itemAt(i)
                if item and item.widget():
                    item.widget().deleteLater()

            self.load_market_plugins()
            self.add_log(" \u5e02\u573a\u63d2\u4ef6\u5237\u65b0\u6210\u529f")
        except Exception as e:
            logger.error(f"\u5237\u65b0\u5e02\u573a\u5931\u8d25: {e}")

    # ========================================================================
    # 性能监控功能
    # ========================================================================

    def update_status(self):
        """更新状态栏"""
        total = len(self.plugin_widgets)
        enabled = sum(1 for w in self.plugin_widgets.values()
                      if w.plugin_info.status == PluginStatus.ENABLED)

        self.status_bar.showMessage(f"\u603b\u8ba1: {total} \u4e2a\u63d2\u4ef6, \u5df2\u542f\u7528: {enabled} \u4e2a")

    def update_monitor_stats(self):
        """更新监控统计"""
        try:
            status_counts = {
                PluginStatus.ENABLED: 0,
                PluginStatus.DISABLED: 0,
                PluginStatus.LOADED: 0,
                PluginStatus.UNLOADED: 0,
                PluginStatus.ERROR: 0
            }

            total = len(self.plugin_widgets)

            for plugin_name, widget in self.plugin_widgets.items():
                try:
                    current_status = self._get_actual_plugin_status(plugin_name, {})
                    widget.plugin_info.status = current_status
                    status_counts[current_status] = status_counts.get(current_status, 0) + 1
                except Exception:
                    status_counts[PluginStatus.ERROR] += 1

            self.total_plugins_label.setText(str(total))
            self.enabled_plugins_label.setText(str(status_counts[PluginStatus.ENABLED]))
            self.disabled_plugins_label.setText(str(status_counts[PluginStatus.DISABLED]))
            self.error_plugins_label.setText(str(status_counts[PluginStatus.ERROR]))

            memory_info = self._get_memory_usage()
            response_times = self._get_plugin_response_times()

            avg_resp = "{:.2f} ms".format(response_times['average']) if response_times['average'] is not None else '\u6682\u65e0\u6570\u636e'
            min_resp = "{:.2f} ms".format(response_times['min']) if response_times['min'] is not None else '\u6682\u65e0\u6570\u636e'
            max_resp = "{:.2f} ms".format(response_times['max']) if response_times['max'] is not None else '\u6682\u65e0\u6570\u636e'

            perf_info = f""" \u63d2\u4ef6\u6027\u80fd\u76d1\u63a7\u62a5\u544a
{'='*40}

 \u72b6\u6001\u7edf\u8ba1:
\u251c\u2500 \u603b\u63d2\u4ef6\u6570: {total} \u4e2a
\u251c\u2500 \u5df2\u542f\u7528: {status_counts[PluginStatus.ENABLED]} \u4e2a
\u251c\u2500 \u5df2\u7981\u7528: {status_counts[PluginStatus.DISABLED]} \u4e2a
\u251c\u2500 \u5df2\u52a0\u8f7d: {status_counts[PluginStatus.LOADED]} \u4e2a
\u251c\u2500 \u672a\u52a0\u8f7d: {status_counts[PluginStatus.UNLOADED]} \u4e2a
\u2514\u2500 \u9519\u8bef: {status_counts[PluginStatus.ERROR]} \u4e2a

 \u5185\u5b58\u4f7f\u7528:
\u251c\u2500 \u63d2\u4ef6\u603b\u5185\u5b58: {memory_info['plugin_memory']:.2f} MB
\u251c\u2500 \u5e73\u5747\u6bcf\u63d2\u4ef6: {memory_info['avg_per_plugin']:.2f} MB
\u2514\u2500 \u7cfb\u7edf\u53ef\u7528: {memory_info['available']:.2f} MB

 \u6027\u80fd\u6307\u6807:
\u251c\u2500 \u5e73\u5747\u54cd\u5e94\u65f6\u95f4: {avg_resp}
\u251c\u2500 \u6700\u5feb\u54cd\u5e94: {min_resp}
\u251c\u2500 \u6700\u6162\u54cd\u5e94: {max_resp}
\u2514\u2500 \u63d2\u4ef6\u7ba1\u7406\u5668\u7248\u672c: FactorWeave-Quant v3.0

 \u6700\u540e\u66f4\u65b0: {self._get_current_time()}
"""
            self.perf_text.setText(perf_info.strip())

        except Exception as e:
            logger.error(f"\u66f4\u65b0\u76d1\u63a7\u7edf\u8ba1\u5931\u8d25: {e}")

    def _get_memory_usage(self) -> dict:
        """获取内存使用信息"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            available = psutil.virtual_memory().available / (1024*1024)

            plugin_memory = memory_info.rss / (1024*1024)
            avg_per_plugin = plugin_memory / max(len(self.plugin_widgets), 1)

            return {
                'plugin_memory': plugin_memory,
                'avg_per_plugin': avg_per_plugin,
                'available': available
            }
        except Exception:
            return {
                'plugin_memory': 0.0,
                'avg_per_plugin': 0.0,
                'available': 0.0
            }

    def _get_plugin_response_times(self) -> dict:
        return {
            'average': None,
            'min': None,
            'max': None
        }

    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ========================================================================
    # 配置导入/导出功能
    # ========================================================================

    def export_all_configs(self):
        """导出所有插件配置"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, "\u5bfc\u51fa\u914d\u7f6e", "", "JSON Files (*.json)")
            if file_path:
                configs = {}
                for plugin_name, widget in self.plugin_widgets.items():
                    configs[plugin_name] = widget.plugin_info.config

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(configs, f, ensure_ascii=False, indent=2)

                self.add_log(f" \u914d\u7f6e\u5df2\u5bfc\u51fa\u5230: {file_path}")
                QMessageBox.information(self, "\u6210\u529f", f"\u914d\u7f6e\u5df2\u5bfc\u51fa\u5230:\n{file_path}")

        except Exception as e:
            logger.error(f"\u5bfc\u51fa\u914d\u7f6e\u5931\u8d25: {e}")
            QMessageBox.critical(self, "\u9519\u8bef", f"\u5bfc\u51fa\u914d\u7f6e\u5931\u8d25: {e}")

    def import_all_configs(self):
        """导入插件配置"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, "\u5bfc\u5165\u914d\u7f6e", "", "JSON Files (*.json)")
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    configs = json.load(f)

                imported_count = 0
                for plugin_name, config in configs.items():
                    if plugin_name in self.plugin_widgets:
                        self.plugin_widgets[plugin_name].plugin_info.config.update(config)
                        imported_count += 1

                self.add_log(f" \u4ece {file_path} \u5bfc\u5165\u4e86 {imported_count} \u4e2a\u63d2\u4ef6\u7684\u914d\u7f6e")
                QMessageBox.information(self, "\u6210\u529f", f"\u6210\u529f\u5bfc\u5165 {imported_count} \u4e2a\u63d2\u4ef6\u7684\u914d\u7f6e")

        except Exception as e:
            logger.error(f"\u5bfc\u5165\u914d\u7f6e\u5931\u8d25: {e}")
            QMessageBox.critical(self, "\u9519\u8bef", f"\u5bfc\u5165\u914d\u7f6e\u5931\u8d25: {e}")

    # ========================================================================
    # 日志功能
    # ========================================================================

    def add_log(self, message: str, level: str = "INFO"):
        """添加日志"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] [{level}] {message}"

            if hasattr(self, 'logs_text') and self.logs_text:
                current_level = getattr(self, 'log_level_combo', None)
                if current_level:
                    selected_level = current_level.currentText()
                    level_priority = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
                    if level_priority.get(level, 1) < level_priority.get(selected_level, 1):
                        return

                color_map = {
                    "DEBUG": "#666666",
                    "INFO": "#000000",
                    "WARNING": "#ff8c00",
                    "ERROR": "#dc3545"
                }
                color = color_map.get(level, "#000000")

                html_entry = f'<span style="color: {color}">{log_entry}</span>'
                self.logs_text.append(html_entry)

                cursor = self.logs_text.textCursor()
                cursor.movePosition(cursor.End)
                self.logs_text.setTextCursor(cursor)
            else:
                print(f"[Plugin Manager] {log_entry}")

        except Exception as e:
            print(f"[Plugin Manager Log Error] \u6dfb\u52a0\u65e5\u5fd7\u5931\u8d25: {e}, \u539f\u59cb\u6d88\u606f: {message}")

    def clear_logs(self):
        """清空日志"""
        self.logs_text.clear()

    def export_logs(self):
        """导出日志"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, "\u5bfc\u51fa\u65e5\u5fd7", "", "Text Files (*.txt)")
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.logs_text.toPlainText())

                self.add_log(f" \u65e5\u5fd7\u5df2\u5bfc\u51fa\u5230: {file_path}")
                QMessageBox.information(self, "\u6210\u529f", f"\u65e5\u5fd7\u5df2\u5bfc\u51fa\u5230:\n{file_path}")

        except Exception as e:
            logger.error(f"\u5bfc\u51fa\u65e5\u5fd7\u5931\u8d25: {e}")

    def closeEvent(self, event):
        """关闭事件"""
        self.timer.stop()
        super().closeEvent(event)
        event.accept()


# =============================================================================
# 向后兼容别名
# =============================================================================

class PluginManagerDialog(PluginManagerDialogUnified):
    """向后兼容别名 - 建议使用 PluginManagerDialogUnified"""
    pass


# 测试代码
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    class MockPluginManager:
        def get_all_plugin_metadata(self):
            return {
                "test_plugin": {
                    "name": "\u6d4b\u8bd5\u63d2\u4ef6",
                    "version": "1.0.0",
                    "description": "\u8fd9\u662f\u4e00\u4e2a\u6d4b\u8bd5\u63d2\u4ef6",
                    "author": "\u6d4b\u8bd5\u4f5c\u8005",
                    "path": "/path/to/plugin",
                    "config": {"enabled": True, "threshold": 0.5}
                }
            }

        def is_plugin_loaded(self, name):
            return True

    dialog = PluginManagerDialogUnified(MockPluginManager())
    dialog.show()

    sys.exit(app.exec_())
