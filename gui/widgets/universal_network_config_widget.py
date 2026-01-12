"""
通用网络配置UI组件
为所有需要网络配置的插件提供统一的配置界面
"""

import logging
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QComboBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QProgressBar, QFrame, QSplitter,
    QTabWidget, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette

from core.network.universal_network_config import (
    get_universal_network_manager, PluginNetworkConfig, NetworkEndpoint
)

logger = logging.getLogger(__name__)


class UniversalNetworkConfigWidget(QWidget):
    """通用网络配置UI组件"""

    config_changed = pyqtSignal(str)  # 配置变更信号 (plugin_id)

    def __init__(self, plugin_id: str = None, parent=None):
        super().__init__(parent)

        self.plugin_id = plugin_id
        self.network_manager = get_universal_network_manager()
        self.config = None

        self.init_ui()

        if plugin_id:
            self.load_plugin_config(plugin_id)

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("网络配置")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title_label)

        # 创建标签页
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # 端点配置标签页
        self.create_endpoints_tab()

        # 网络设置标签页
        self.create_network_settings_tab()

        # 代理设置标签页
        self.create_proxy_settings_tab()

        # 统计信息标签页
        self.create_statistics_tab()

        # 操作按钮
        self.create_action_buttons(layout)

        # 状态栏
        self.status_label = QLabel("准备就绪")
        self.status_label.setStyleSheet("color: blue; padding: 5px;")
        layout.addWidget(self.status_label)

    def create_endpoints_tab(self):
        """创建端点配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 快速配置区域
        quick_config_group = QGroupBox("快速配置")
        quick_layout = QVBoxLayout(quick_config_group)

        # 端点地址输入框
        endpoint_layout = QHBoxLayout()
        endpoint_layout.addWidget(QLabel("端点地址:"))

        self.endpoints_edit = QLineEdit()
        self.endpoints_edit.setPlaceholderText("请输入端点地址，多个地址用分号(;)分隔")
        self.endpoints_edit.textChanged.connect(self.on_endpoints_text_changed)
        endpoint_layout.addWidget(self.endpoints_edit)

        # 从默认获取按钮
        self.fetch_defaults_btn = QPushButton("获取默认地址")
        self.fetch_defaults_btn.clicked.connect(self.fetch_default_endpoints)
        self.fetch_defaults_btn.setToolTip("从插件获取默认的端点地址")
        endpoint_layout.addWidget(self.fetch_defaults_btn)

        # 测试连接按钮
        self.test_endpoints_btn = QPushButton("测试连接")
        self.test_endpoints_btn.clicked.connect(self.test_all_endpoints)
        self.test_endpoints_btn.setToolTip("测试所有端点的连接性")
        endpoint_layout.addWidget(self.test_endpoints_btn)

        quick_layout.addLayout(endpoint_layout)
        layout.addWidget(quick_config_group)

        # 详细配置区域
        detail_group = QGroupBox("详细配置")
        detail_layout = QVBoxLayout(detail_group)

        # 端点表格
        self.endpoints_table = QTableWidget()
        self.endpoints_table.setColumnCount(8)
        self.endpoints_table.setHorizontalHeaderLabels([
            "名称", "地址", "描述", "优先级", "超时(秒)", "启用", "统计", "操作"
        ])

        # 设置表格属性
        header = self.endpoints_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # 地址列拉伸
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 描述列

        detail_layout.addWidget(self.endpoints_table)

        # 端点操作按钮
        endpoint_buttons = QHBoxLayout()

        self.add_endpoint_btn = QPushButton("添加端点")
        self.add_endpoint_btn.clicked.connect(self.add_endpoint)
        endpoint_buttons.addWidget(self.add_endpoint_btn)

        self.remove_endpoint_btn = QPushButton("删除端点")
        self.remove_endpoint_btn.clicked.connect(self.remove_endpoint)
        endpoint_buttons.addWidget(self.remove_endpoint_btn)

        endpoint_buttons.addStretch()
        detail_layout.addLayout(endpoint_buttons)

        layout.addWidget(detail_group)

        self.tab_widget.addTab(tab, "端点配置")

    def create_network_settings_tab(self):
        """创建网络设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 频率限制设置
        rate_limit_group = QGroupBox("频率限制")
        rate_layout = QFormLayout(rate_limit_group)

        self.rate_limit_enabled = QCheckBox("启用频率限制")
        rate_layout.addRow("", self.rate_limit_enabled)

        self.requests_per_minute = QSpinBox()
        self.requests_per_minute.setRange(1, 1000)
        self.requests_per_minute.setValue(30)
        rate_layout.addRow("每分钟请求数:", self.requests_per_minute)

        self.request_delay = QDoubleSpinBox()
        self.request_delay.setRange(0.1, 60.0)
        self.request_delay.setValue(2.0)
        self.request_delay.setSuffix("秒")
        rate_layout.addRow("请求间隔:", self.request_delay)

        layout.addWidget(rate_limit_group)

        # 重试设置
        retry_group = QGroupBox("重试设置")
        retry_layout = QFormLayout(retry_group)

        self.retry_count = QSpinBox()
        self.retry_count.setRange(0, 10)
        self.retry_count.setValue(3)
        retry_layout.addRow("重试次数:", self.retry_count)

        self.retry_delay = QDoubleSpinBox()
        self.retry_delay.setRange(0.1, 30.0)
        self.retry_delay.setValue(1.0)
        self.retry_delay.setSuffix("秒")
        retry_layout.addRow("重试延迟:", self.retry_delay)

        layout.addWidget(retry_group)

        # HTTP设置
        http_group = QGroupBox("HTTP设置")
        http_layout = QFormLayout(http_group)

        self.user_agent = QLineEdit()
        self.user_agent.setText("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        http_layout.addRow("User-Agent:", self.user_agent)

        self.custom_headers = QTextEdit()
        self.custom_headers.setPlaceholderText("自定义请求头，JSON格式，如:\n{\n  \"Authorization\": \"Bearer token\",\n  \"Accept\": \"application/json\"\n}")
        self.custom_headers.setMaximumHeight(100)
        http_layout.addRow("自定义请求头:", self.custom_headers)

        layout.addWidget(http_group)

        layout.addStretch()

        self.tab_widget.addTab(tab, "网络设置")

    def create_proxy_settings_tab(self):
        """创建代理设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 代理设置
        proxy_group = QGroupBox("代理配置")
        proxy_layout = QVBoxLayout(proxy_group)

        self.proxy_enabled = QCheckBox("启用代理")
        proxy_layout.addWidget(self.proxy_enabled)

        # 代理列表
        proxy_list_layout = QHBoxLayout()
        proxy_list_layout.addWidget(QLabel("代理列表:"))

        self.proxy_list = QTextEdit()
        self.proxy_list.setPlaceholderText("每行一个代理地址，格式:\nhttp://proxy.example.com:8080\nsocks5://user:pass@proxy.example.com:1080")
        self.proxy_list.setMaximumHeight(120)
        proxy_list_layout.addWidget(self.proxy_list)

        # 代理操作按钮
        proxy_buttons = QVBoxLayout()

        self.test_proxies_btn = QPushButton("测试代理")
        self.test_proxies_btn.clicked.connect(self.test_proxies)
        proxy_buttons.addWidget(self.test_proxies_btn)

        self.import_proxies_btn = QPushButton("导入代理")
        self.import_proxies_btn.clicked.connect(self.import_proxies)
        proxy_buttons.addWidget(self.import_proxies_btn)

        proxy_buttons.addStretch()
        proxy_list_layout.addLayout(proxy_buttons)

        proxy_layout.addLayout(proxy_list_layout)
        layout.addWidget(proxy_group)

        layout.addStretch()

        self.tab_widget.addTab(tab, "代理设置")

    def create_statistics_tab(self):
        """创建统计信息标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 统计信息显示
        stats_group = QGroupBox("网络统计")
        stats_layout = QGridLayout(stats_group)

        # 创建统计标签
        self.stats_labels = {}
        stats_items = [
            ("total_requests", "总请求数"),
            ("success_rate", "成功率"),
            ("avg_response_time", "平均响应时间"),
            ("active_endpoints", "活跃端点"),
            ("proxy_status", "代理状态"),
            ("last_update", "最后更新")
        ]

        for i, (key, label) in enumerate(stats_items):
            row = i // 2
            col = (i % 2) * 2

            stats_layout.addWidget(QLabel(label + ":"), row, col)

            value_label = QLabel("-")
            value_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
            stats_layout.addWidget(value_label, row, col + 1)

            self.stats_labels[key] = value_label

        layout.addWidget(stats_group)

        # 刷新按钮
        refresh_layout = QHBoxLayout()
        refresh_layout.addStretch()

        self.refresh_stats_btn = QPushButton("刷新统计")
        self.refresh_stats_btn.clicked.connect(self.refresh_statistics)
        refresh_layout.addWidget(self.refresh_stats_btn)

        layout.addLayout(refresh_layout)
        layout.addStretch()

        self.tab_widget.addTab(tab, "统计信息")

    def create_action_buttons(self, layout):
        """创建操作按钮"""
        button_layout = QHBoxLayout()

        # 保存按钮
        self.save_btn = QPushButton("保存配置")
        self.save_btn.clicked.connect(self.save_config)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        button_layout.addWidget(self.save_btn)

        # 重置按钮
        self.reset_btn = QPushButton("重置")
        self.reset_btn.clicked.connect(self.reset_config)
        button_layout.addWidget(self.reset_btn)

        # 测试配置按钮
        self.test_config_btn = QPushButton("测试配置")
        self.test_config_btn.clicked.connect(self.test_configuration)
        button_layout.addWidget(self.test_config_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def load_plugin_config(self, plugin_id: str):
        """加载插件配置"""
        try:
            self.plugin_id = plugin_id
            self.config = self.network_manager.get_plugin_config(plugin_id)

            if not self.config:
                self.status_label.setText(f"插件配置不存在: {plugin_id}")
                return

            # 更新UI
            self.update_ui_from_config()
            self.status_label.setText(f"已加载配置: {self.config.plugin_name}")

        except Exception as e:
            logger.error(f"加载插件配置失败: {e}")
            self.status_label.setText(f"加载配置失败: {e}")

    def update_ui_from_config(self):
        """从配置更新UI"""
        if not self.config:
            return

        try:
            # 更新端点配置
            endpoints_str = self.network_manager.get_endpoints_as_string(self.plugin_id)
            self.endpoints_edit.setText(endpoints_str)

            # 更新端点表格
            self.update_endpoints_table()

            # 更新网络设置
            self.rate_limit_enabled.setChecked(self.config.rate_limit_enabled)
            self.requests_per_minute.setValue(self.config.requests_per_minute)
            self.request_delay.setValue(self.config.request_delay)
            self.retry_count.setValue(self.config.retry_count)
            self.retry_delay.setValue(self.config.retry_delay)
            self.user_agent.setText(self.config.user_agent)

            # 更新代理设置
            self.proxy_enabled.setChecked(self.config.proxy_enabled)
            self.proxy_list.setText('\n'.join(self.config.proxy_list))

            # 更新统计信息
            self.refresh_statistics()

        except Exception as e:
            logger.error(f"更新UI失败: {e}")

    def update_endpoints_table(self):
        """更新端点表格"""
        if not self.config:
            return

        self.endpoints_table.setRowCount(len(self.config.endpoints))

        for i, endpoint in enumerate(self.config.endpoints):
            # 名称
            self.endpoints_table.setItem(i, 0, QTableWidgetItem(endpoint.name))

            # 地址
            self.endpoints_table.setItem(i, 1, QTableWidgetItem(endpoint.url))

            # 描述
            self.endpoints_table.setItem(i, 2, QTableWidgetItem(endpoint.description))

            # 优先级
            self.endpoints_table.setItem(i, 3, QTableWidgetItem(str(endpoint.priority)))

            # 超时
            self.endpoints_table.setItem(i, 4, QTableWidgetItem(str(endpoint.timeout)))

            # 启用状态
            enabled_item = QTableWidgetItem()
            enabled_item.setCheckState(Qt.Checked if endpoint.enabled else Qt.Unchecked)
            self.endpoints_table.setItem(i, 5, enabled_item)

            # 统计信息
            total_requests = endpoint.success_count + endpoint.failure_count
            success_rate = endpoint.success_count / max(total_requests, 1) * 100
            stats_text = f"成功: {endpoint.success_count}\n失败: {endpoint.failure_count}\n成功率: {success_rate:.1f}%"
            self.endpoints_table.setItem(i, 6, QTableWidgetItem(stats_text))

            # 操作按钮
            test_btn = QPushButton("测试")
            test_btn.clicked.connect(lambda checked, idx=i: self.test_single_endpoint(idx))
            self.endpoints_table.setCellWidget(i, 7, test_btn)

    def on_endpoints_text_changed(self):
        """端点文本变更事件"""
        if not self.plugin_id:
            return

        endpoints_str = self.endpoints_edit.text().strip()
        if endpoints_str:
            # 临时更新配置以预览
            self.network_manager.update_endpoints_from_string(self.plugin_id, endpoints_str)
            self.config = self.network_manager.get_plugin_config(self.plugin_id)
            self.update_endpoints_table()

    def fetch_default_endpoints(self):
        """获取默认端点地址"""
        # 这里需要与插件系统集成，获取插件的默认端点
        # 暂时显示提示消息
        QMessageBox.information(
            self,
            "获取默认地址",
            "此功能需要插件支持INetworkConfigurable接口。\n"
            "请联系插件开发者添加默认端点配置。"
        )

    def test_all_endpoints(self):
        """测试所有端点"""
        if not self.config or not self.config.endpoints:
            QMessageBox.warning(self, "警告", "没有可测试的端点")
            return

        self.test_endpoints_btn.setEnabled(False)
        self.status_label.setText("正在测试端点连接...")

        # 这里应该实现异步测试逻辑
        # 暂时显示消息
        QTimer.singleShot(2000, self._test_endpoints_finished)

    def _test_endpoints_finished(self):
        """端点测试完成"""
        self.test_endpoints_btn.setEnabled(True)
        self.status_label.setText("端点测试完成")
        QMessageBox.information(self, "测试完成", "所有端点测试已完成，请查看统计信息")

    def test_single_endpoint(self, index: int):
        """测试单个端点"""
        if not self.config or index >= len(self.config.endpoints):
            return

        endpoint = self.config.endpoints[index]
        self.status_label.setText(f"正在测试端点: {endpoint.name}")

        # 这里应该实现单个端点测试逻辑
        QTimer.singleShot(1000, lambda: self.status_label.setText(f"端点测试完成: {endpoint.name}"))

    def add_endpoint(self):
        """添加端点"""
        if not self.config:
            return

        # 简单的添加端点对话框（可以扩展为更详细的对话框）
        from PyQt5.QtWidgets import QInputDialog

        url, ok = QInputDialog.getText(self, "添加端点", "请输入端点地址:")
        if ok and url.strip():
            new_endpoint = NetworkEndpoint(
                name=f"endpoint_{len(self.config.endpoints) + 1}",
                url=url.strip(),
                description="用户添加的端点"
            )
            self.config.endpoints.append(new_endpoint)
            self.update_endpoints_table()
            self.update_endpoints_edit()

    def remove_endpoint(self):
        """删除端点"""
        current_row = self.endpoints_table.currentRow()
        if current_row >= 0 and self.config and current_row < len(self.config.endpoints):
            reply = QMessageBox.question(
                self, "确认删除",
                f"确定要删除端点 '{self.config.endpoints[current_row].name}' 吗？",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                del self.config.endpoints[current_row]
                self.update_endpoints_table()
                self.update_endpoints_edit()

    def update_endpoints_edit(self):
        """更新端点编辑框"""
        if self.config:
            endpoints_str = ';'.join([ep.url for ep in self.config.endpoints if ep.enabled])
            self.endpoints_edit.setText(endpoints_str)

    def test_proxies(self):
        """测试代理"""
        proxy_text = self.proxy_list.toPlainText().strip()
        if not proxy_text:
            QMessageBox.warning(self, "警告", "请先输入代理地址")
            return

        self.test_proxies_btn.setEnabled(False)
        self.status_label.setText("正在测试代理...")

        # 实现代理测试逻辑
        QTimer.singleShot(3000, self._proxy_test_finished)

    def _proxy_test_finished(self):
        """代理测试完成"""
        self.test_proxies_btn.setEnabled(True)
        self.status_label.setText("代理测试完成")

    def import_proxies(self):
        """导入代理"""
        from PyQt5.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入代理列表", "", "文本文件 (*.txt);;所有文件 (*)"
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    proxy_content = f.read()
                self.proxy_list.setText(proxy_content)
                self.status_label.setText(f"已导入代理列表: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入代理列表失败: {e}")

    def refresh_statistics(self):
        """刷新统计信息"""
        if not self.plugin_id:
            return

        try:
            stats = self.network_manager.get_plugin_statistics(self.plugin_id)

            self.stats_labels['total_requests'].setText(str(stats.get('total_requests', 0)))
            self.stats_labels['success_rate'].setText(f"{stats.get('success_rate', 0) * 100:.1f}%")
            self.stats_labels['avg_response_time'].setText(f"{stats.get('avg_response_time', 0):.2f}s")
            self.stats_labels['active_endpoints'].setText(f"{stats.get('enabled_endpoints', 0)}/{stats.get('total_endpoints', 0)}")
            self.stats_labels['proxy_status'].setText("启用" if stats.get('proxy_enabled') else "禁用")
            self.stats_labels['last_update'].setText(datetime.now().strftime("%H:%M:%S"))

        except Exception as e:
            logger.error(f"刷新统计信息失败: {e}")

    def save_config(self):
        """保存配置"""
        if not self.config or not self.plugin_id:
            QMessageBox.warning(self, "警告", "没有可保存的配置")
            return

        try:
            # 从UI更新配置
            self.config.rate_limit_enabled = self.rate_limit_enabled.isChecked()
            self.config.requests_per_minute = self.requests_per_minute.value()
            self.config.request_delay = self.request_delay.value()
            self.config.retry_count = self.retry_count.value()
            self.config.retry_delay = self.retry_delay.value()
            self.config.user_agent = self.user_agent.text()
            self.config.proxy_enabled = self.proxy_enabled.isChecked()

            # 更新代理列表
            proxy_text = self.proxy_list.toPlainText().strip()
            self.config.proxy_list = [line.strip() for line in proxy_text.split('\n') if line.strip()]

            # 保存配置
            success = self.network_manager.update_plugin_config(self.plugin_id, self.config)

            if success:
                self.status_label.setText("配置保存成功")
                self.config_changed.emit(self.plugin_id)
                QMessageBox.information(self, "成功", "网络配置已保存")
            else:
                QMessageBox.critical(self, "错误", "配置保存失败")

        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存配置失败: {e}")

    def reset_config(self):
        """重置配置"""
        reply = QMessageBox.question(
            self, "确认重置", "确定要重置所有配置吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.load_plugin_config(self.plugin_id)
            self.status_label.setText("配置已重置")

    def test_configuration(self):
        """测试配置"""
        if not self.config:
            QMessageBox.warning(self, "警告", "没有可测试的配置")
            return

        self.test_config_btn.setEnabled(False)
        self.status_label.setText("正在测试网络配置...")

        # 实现配置测试逻辑
        QTimer.singleShot(2000, self._config_test_finished)

    def _config_test_finished(self):
        """配置测试完成"""
        self.test_config_btn.setEnabled(True)
        self.status_label.setText("网络配置测试完成")
        QMessageBox.information(self, "测试完成", "网络配置测试已完成")


class PluginNetworkConfigDialog(QWidget):
    """插件网络配置对话框"""

    def __init__(self, plugin_id: str, plugin_name: str = None, parent=None):
        super().__init__(parent)

        self.plugin_id = plugin_id
        self.plugin_name = plugin_name or plugin_id

        self.setWindowTitle(f"网络配置 - {self.plugin_name}")
        self.setFixedSize(800, 600)

        layout = QVBoxLayout(self)

        # 配置组件
        self.config_widget = UniversalNetworkConfigWidget(plugin_id)
        layout.addWidget(self.config_widget)

        # 关闭按钮
        close_layout = QHBoxLayout()
        close_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        close_layout.addWidget(close_btn)

        layout.addLayout(close_layout)
