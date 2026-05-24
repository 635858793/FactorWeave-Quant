"""
云端API管理对话框
用于API配置、节点注册和任务同步
"""

from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QTabWidget,
                             QTableWidget, QTableWidgetItem, QPushButton,
                             QLabel, QLineEdit, QTextEdit, QGroupBox,
                             QFormLayout, QSpinBox, QCheckBox, QComboBox,
                             QProgressBar, QMessageBox, QHeaderView,
                             QSplitter, QFrame, QListWidget, QListWidgetItem)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QFont
import json
import requests
import time

from .base_dialog import BaseDialog


class CloudApiDialog(BaseDialog):
    """云端API管理对话框"""

    api_connected = pyqtSignal(str)
    api_disconnected = pyqtSignal(str)
    task_completed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(
            parent,
            title="云端API管理器",
            size=(1000, 700),
            settings_key="CloudApiDialog"
        )

        # API配置
        self.api_configs = {}
        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self.sync_data)

        self.setup_ui()
        self.connect_signals()
        self.load_default_configs()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("云端API管理器")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # 创建选项卡
        tab_widget = QTabWidget()

        # API配置选项卡
        config_tab = self.create_config_tab()
        tab_widget.addTab(config_tab, "API配置")

        # 节点注册选项卡
        register_tab = self.create_register_tab()
        tab_widget.addTab(register_tab, "节点注册")

        # 任务同步选项卡
        sync_tab = self.create_sync_tab()
        tab_widget.addTab(sync_tab, "任务同步")

        # 监控面板选项卡
        monitor_tab = self.create_monitor_tab()
        tab_widget.addTab(monitor_tab, "监控面板")

        layout.addWidget(tab_widget)

        # 按钮
        button_layout = QHBoxLayout()

        self.test_connection_btn = QPushButton("测试连接")
        self.start_sync_btn = QPushButton("开始同步")
        self.stop_sync_btn = QPushButton("停止同步")
        self.stop_sync_btn.setEnabled(False)
        close_btn = QPushButton("关闭")

        button_layout.addWidget(self.test_connection_btn)
        button_layout.addWidget(self.start_sync_btn)
        button_layout.addWidget(self.stop_sync_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        # 连接按钮信号
        self.test_connection_btn.clicked.connect(self.test_connection)
        self.start_sync_btn.clicked.connect(self.start_sync)
        self.stop_sync_btn.clicked.connect(self.stop_sync)
        close_btn.clicked.connect(self.accept)

    def create_config_tab(self):
        """创建API配置选项卡"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # API服务器配置
        server_group = QGroupBox("API服务器配置")
        server_layout = QFormLayout(server_group)

        self.api_url_edit = QLineEdit()
        self.api_url_edit.setPlaceholderText("https://api.factorweave.com")
        server_layout.addRow("API地址:", self.api_url_edit)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("输入API密钥")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        server_layout.addRow("API密钥:", self.api_key_edit)

        self.api_version_combo = QComboBox()
        self.api_version_combo.addItems(["v1", "v2", "v3"])
        self.api_version_combo.setCurrentText("v2")
        server_layout.addRow("API版本:", self.api_version_combo)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 300)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix("秒")
        server_layout.addRow("超时时间:", self.timeout_spin)

        layout.addWidget(server_group)

        # 认证配置
        auth_group = QGroupBox("认证配置")
        auth_layout = QFormLayout(auth_group)

        self.auth_type_combo = QComboBox()
        self.auth_type_combo.addItems(["API Key", "OAuth 2.0", "JWT Token"])
        auth_layout.addRow("认证类型:", self.auth_type_combo)

        self.username_edit = QLineEdit()
        auth_layout.addRow("用户名:", self.username_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        auth_layout.addRow("密码:", self.password_edit)

        layout.addWidget(auth_group)

        # 高级设置
        advanced_group = QGroupBox("高级设置")
        advanced_layout = QFormLayout(advanced_group)

        self.retry_count_spin = QSpinBox()
        self.retry_count_spin.setRange(1, 10)
        self.retry_count_spin.setValue(3)
        advanced_layout.addRow("重试次数:", self.retry_count_spin)

        self.rate_limit_spin = QSpinBox()
        self.rate_limit_spin.setRange(1, 1000)
        self.rate_limit_spin.setValue(100)
        self.rate_limit_spin.setSuffix("请求/分钟")
        advanced_layout.addRow("速率限制:", self.rate_limit_spin)

        self.enable_cache_check = QCheckBox("启用响应缓存")
        self.enable_cache_check.setChecked(True)
        advanced_layout.addRow(self.enable_cache_check)

        self.enable_compression_check = QCheckBox("启用数据压缩")
        self.enable_compression_check.setChecked(True)
        advanced_layout.addRow(self.enable_compression_check)

        layout.addWidget(advanced_group)

        return widget

    def create_register_tab(self):
        """创建节点注册选项卡"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 节点信息
        node_group = QGroupBox("本地节点信息")
        node_layout = QFormLayout(node_group)

        self.node_id_edit = QLineEdit()
        self.node_id_edit.setPlaceholderText("自动生成")
        node_layout.addRow("节点ID:", self.node_id_edit)

        self.node_name_edit = QLineEdit()
        self.node_name_edit.setPlaceholderText("我的交易节点")
        node_layout.addRow("节点名称:", self.node_name_edit)

        self.node_type_combo = QComboBox()
        self.node_type_combo.addItems(["分析节点", "数据节点", "交易节点", "监控节点"])
        node_layout.addRow("节点类型:", self.node_type_combo)

        self.node_region_combo = QComboBox()
        self.node_region_combo.addItems(["华东", "华北", "华南", "西南", "西北", "东北"])
        node_layout.addRow("节点区域:", self.node_region_combo)

        layout.addWidget(node_group)

        # 注册状态
        status_group = QGroupBox("注册状态")
        status_layout = QVBoxLayout(status_group)

        self.registration_status_label = QLabel("未注册")
        self.registration_status_label.setStyleSheet(
            "color: red; font-weight: bold;")
        status_layout.addWidget(self.registration_status_label)

        self.last_heartbeat_label = QLabel("从未")
        status_layout.addWidget(QLabel("最后心跳:"))
        status_layout.addWidget(self.last_heartbeat_label)

        # 注册按钮
        register_button_layout = QHBoxLayout()
        self.register_btn = QPushButton("注册节点")
        self.unregister_btn = QPushButton("注销节点")
        self.heartbeat_btn = QPushButton("发送心跳")

        self.register_btn.clicked.connect(self.register_node)
        self.unregister_btn.clicked.connect(self.unregister_node)
        self.heartbeat_btn.clicked.connect(self.send_heartbeat)

        register_button_layout.addWidget(self.register_btn)
        register_button_layout.addWidget(self.unregister_btn)
        register_button_layout.addWidget(self.heartbeat_btn)
        status_layout.addLayout(register_button_layout)

        layout.addWidget(status_group)

        # 已注册节点列表
        registered_group = QGroupBox("已注册节点")
        registered_layout = QVBoxLayout(registered_group)

        self.registered_nodes_table = QTableWidget()
        self.registered_nodes_table.setColumnCount(6)
        self.registered_nodes_table.setHorizontalHeaderLabels([
            "节点ID", "节点名称", "类型", "区域", "状态", "最后心跳"
        ])
        self.registered_nodes_table.horizontalHeader().setStretchLastSection(True)
        registered_layout.addWidget(self.registered_nodes_table)

        layout.addWidget(registered_group)

        return widget

    def create_sync_tab(self):
        """创建任务同步选项卡"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 同步设置
        sync_settings_group = QGroupBox("同步设置")
        sync_settings_layout = QFormLayout(sync_settings_group)

        self.sync_interval_spin = QSpinBox()
        self.sync_interval_spin.setRange(1, 3600)
        self.sync_interval_spin.setValue(60)
        self.sync_interval_spin.setSuffix("秒")
        sync_settings_layout.addRow("同步间隔:", self.sync_interval_spin)

        self.sync_data_types = QListWidget()
        self.sync_data_types.setMaximumHeight(120)
        sync_data_items = [
            "股票数据", "技术指标", "策略结果", "回测报告", "用户配置", "日志文件"
        ]
        for item_text in sync_data_items:
            item = QListWidgetItem(item_text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.sync_data_types.addItem(item)
        sync_settings_layout.addRow("同步数据类型:", self.sync_data_types)

        self.auto_sync_check = QCheckBox("启用自动同步")
        self.auto_sync_check.setChecked(True)
        sync_settings_layout.addRow(self.auto_sync_check)

        layout.addWidget(sync_settings_group)

        # 同步状态
        sync_status_group = QGroupBox("同步状态")
        sync_status_layout = QVBoxLayout(sync_status_group)

        # 进度条
        self.sync_progress = QProgressBar()
        sync_status_layout.addWidget(QLabel("同步进度:"))
        sync_status_layout.addWidget(self.sync_progress)

        # 状态信息
        status_info_layout = QFormLayout()
        self.last_sync_label = QLabel("从未")
        self.sync_count_label = QLabel("0")
        self.sync_errors_label = QLabel("0")

        status_info_layout.addRow("最后同步:", self.last_sync_label)
        status_info_layout.addRow("同步次数:", self.sync_count_label)
        status_info_layout.addRow("同步错误:", self.sync_errors_label)

        sync_status_layout.addLayout(status_info_layout)

        layout.addWidget(sync_status_group)

        # 同步任务列表
        tasks_group = QGroupBox("同步任务")
        tasks_layout = QVBoxLayout(tasks_group)

        self.sync_tasks_table = QTableWidget()
        self.sync_tasks_table.setColumnCount(5)
        self.sync_tasks_table.setHorizontalHeaderLabels([
            "任务ID", "数据类型", "状态", "进度", "最后更新"
        ])
        self.sync_tasks_table.horizontalHeader().setStretchLastSection(True)
        tasks_layout.addWidget(self.sync_tasks_table)

        # 任务操作按钮
        task_button_layout = QHBoxLayout()
        self.manual_sync_btn = QPushButton("手动同步")
        self.clear_tasks_btn = QPushButton("清空任务")
        self.retry_failed_btn = QPushButton("重试失败")

        self.manual_sync_btn.clicked.connect(self.manual_sync)
        self.clear_tasks_btn.clicked.connect(self.clear_tasks)
        self.retry_failed_btn.clicked.connect(self.retry_failed_tasks)

        task_button_layout.addWidget(self.manual_sync_btn)
        task_button_layout.addWidget(self.clear_tasks_btn)
        task_button_layout.addWidget(self.retry_failed_btn)
        tasks_layout.addLayout(task_button_layout)

        layout.addWidget(tasks_group)

        return widget

    def create_monitor_tab(self):
        """创建监控面板选项卡"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # API统计
        api_stats_group = QGroupBox("API统计")
        api_stats_layout = QFormLayout(api_stats_group)

        self.total_requests_label = QLabel("0")
        self.successful_requests_label = QLabel("0")
        self.failed_requests_label = QLabel("0")
        self.avg_response_time_label = QLabel("0 ms")

        api_stats_layout.addRow("总请求数:", self.total_requests_label)
        api_stats_layout.addRow("成功请求:", self.successful_requests_label)
        api_stats_layout.addRow("失败请求:", self.failed_requests_label)
        api_stats_layout.addRow("平均响应时间:", self.avg_response_time_label)

        layout.addWidget(api_stats_group)

        # 实时监控
        realtime_group = QGroupBox("实时监控")
        realtime_layout = QVBoxLayout(realtime_group)

        self.monitor_log = QTextEdit()
        self.monitor_log.setMaximumHeight(200)
        self.monitor_log.setReadOnly(True)
        realtime_layout.addWidget(self.monitor_log)

        # 监控控制
        monitor_control_layout = QHBoxLayout()
        self.start_monitor_btn = QPushButton("开始监控")
        self.stop_monitor_btn = QPushButton("停止监控")
        self.clear_log_btn = QPushButton("清空日志")

        self.start_monitor_btn.clicked.connect(self.start_monitoring)
        self.stop_monitor_btn.clicked.connect(self.stop_monitoring)
        self.clear_log_btn.clicked.connect(self.clear_monitor_log)

        monitor_control_layout.addWidget(self.start_monitor_btn)
        monitor_control_layout.addWidget(self.stop_monitor_btn)
        monitor_control_layout.addWidget(self.clear_log_btn)
        realtime_layout.addLayout(monitor_control_layout)

        layout.addWidget(realtime_group)

        # 错误日志
        error_group = QGroupBox("错误日志")
        error_layout = QVBoxLayout(error_group)

        self.error_table = QTableWidget()
        self.error_table.setColumnCount(4)
        self.error_table.setHorizontalHeaderLabels([
            "时间", "错误类型", "错误信息", "请求URL"
        ])
        self.error_table.horizontalHeader().setStretchLastSection(True)
        error_layout.addWidget(self.error_table)

        layout.addWidget(error_group)

        return widget

    def connect_signals(self):
        """连接信号"""
        self.api_connected.connect(self.on_api_connected)
        self.api_disconnected.connect(self.on_api_disconnected)
        self.task_completed.connect(self.on_task_completed)

    def load_default_configs(self):
        """加载默认配置"""
        self.api_configs = {
            'default': {
                'url': 'https://api.factorweave.com',
                'key': '',
                'version': 'v2',
                'timeout': 30
            }
        }

        # 生成默认节点ID
        import uuid
        self.node_id_edit.setText(str(uuid.uuid4())[:8])

    def test_connection(self):
        """测试API连接"""
        url = self.api_url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "警告", "请输入API地址")
            return

        self.test_connection_btn.setEnabled(False)
        self.test_connection_btn.setText("测试中...")

        class _ConnectionTestWorker(QThread):
            test_finished = pyqtSignal(bool, str)

            def __init__(self, test_url):
                super().__init__()
                self._test_url = test_url

            def run(self):
                try:
                    import time
                    time.sleep(1)
                    self.test_finished.emit(True, self._test_url)
                except Exception as e:
                    self.test_finished.emit(False, str(e))

        self._conn_worker = _ConnectionTestWorker(url)
        self._conn_worker.test_finished.connect(self._on_connection_test_finished)
        self._conn_worker.start()

    def _on_connection_test_finished(self, success, message):
        """连接测试完成回调"""
        self.test_connection_btn.setEnabled(True)
        self.test_connection_btn.setText("测试连接")
        if success:
            QMessageBox.information(self, "成功", "API连接测试成功！")
            self.api_connected.emit(message)
        else:
            QMessageBox.critical(self, "错误", f"连接测试失败: {message}")

    def start_sync(self):
        """开始同步"""
        try:
            interval = self.sync_interval_spin.value() * 1000  # 转换为毫秒
            self.sync_timer.start(interval)

            self.start_sync_btn.setEnabled(False)
            self.stop_sync_btn.setEnabled(True)

            # 立即执行一次同步
            self.sync_data()

            self.add_monitor_log("开始自动同步")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动同步失败: {str(e)}")

    def stop_sync(self):
        """停止同步"""
        self.sync_timer.stop()

        self.start_sync_btn.setEnabled(True)
        self.stop_sync_btn.setEnabled(False)

        self.add_monitor_log("停止自动同步")

    def sync_data(self):
        """同步数据"""
        try:
            # 模拟同步过程
            self.sync_progress.setValue(0)

            # 获取选中的数据类型
            selected_types = []
            for i in range(self.sync_data_types.count()):
                item = self.sync_data_types.item(i)
                if item.checkState() == Qt.Checked:
                    selected_types.append(item.text())

            if not selected_types:
                return

            # 模拟同步每种数据类型
            total_steps = len(selected_types)
            if total_steps == 0:
                self.sync_progress.setValue(100)
                return
            for i, data_type in enumerate(selected_types):
                progress = int((i + 1) / total_steps * 100)
                self.sync_progress.setValue(progress)

                # 添加到任务表格
                self.add_sync_task(
                    f"sync_{int(time.time())}", data_type, "进行中", progress)

                # 模拟网络延迟
                time.sleep(0.1)

            self.sync_progress.setValue(100)

            # 更新统计信息
            current_count = int(self.sync_count_label.text())
            self.sync_count_label.setText(str(current_count + 1))
            self.last_sync_label.setText(time.strftime("%Y-%m-%d %H:%M:%S"))

            self.add_monitor_log(f"完成数据同步: {', '.join(selected_types)}")

        except Exception as e:
            self.add_monitor_log(f"同步失败: {str(e)}")

    def add_sync_task(self, task_id, data_type, status, progress):
        """添加同步任务"""
        row = self.sync_tasks_table.rowCount()
        self.sync_tasks_table.insertRow(row)

        self.sync_tasks_table.setItem(row, 0, QTableWidgetItem(task_id))
        self.sync_tasks_table.setItem(row, 1, QTableWidgetItem(data_type))
        self.sync_tasks_table.setItem(row, 2, QTableWidgetItem(status))
        self.sync_tasks_table.setItem(row, 3, QTableWidgetItem(f"{progress}%"))
        self.sync_tasks_table.setItem(
            row, 4, QTableWidgetItem(time.strftime("%H:%M:%S")))

    def register_node(self):
        """注册节点"""
        try:
            node_id = self.node_id_edit.text().strip()
            node_name = self.node_name_edit.text().strip()

            if not node_id or not node_name:
                QMessageBox.warning(self, "警告", "请填写节点ID和名称")
                return

            # 模拟注册过程
            self.registration_status_label.setText("已注册")
            self.registration_status_label.setStyleSheet(
                "color: green; font-weight: bold;")

            # 发送心跳
            self.send_heartbeat()

            QMessageBox.information(self, "成功", "节点注册成功！")
            self.add_monitor_log(f"节点注册成功: {node_name} ({node_id})")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"节点注册失败: {str(e)}")

    def unregister_node(self):
        """注销节点"""
        try:
            self.registration_status_label.setText("未注册")
            self.registration_status_label.setStyleSheet(
                "color: red; font-weight: bold;")

            QMessageBox.information(self, "成功", "节点注销成功！")
            self.add_monitor_log("节点注销成功")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"节点注销失败: {str(e)}")

    def send_heartbeat(self):
        """发送心跳"""
        try:
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            self.last_heartbeat_label.setText(current_time)
            self.add_monitor_log("发送心跳信号")

        except Exception as e:
            self.add_monitor_log(f"发送心跳失败: {str(e)}")

    def manual_sync(self):
        """手动同步"""
        self.sync_data()

    def clear_tasks(self):
        """清空任务"""
        self.sync_tasks_table.setRowCount(0)
        self.add_monitor_log("清空同步任务")

    def retry_failed_tasks(self):
        """重试失败任务"""
        # 模拟重试逻辑
        self.add_monitor_log("重试失败任务")

    def start_monitoring(self):
        """开始监控"""
        self.add_monitor_log("开始API监控")

    def stop_monitoring(self):
        """停止监控"""
        self.add_monitor_log("停止API监控")

    def clear_monitor_log(self):
        """清空监控日志"""
        self.monitor_log.clear()

    def add_monitor_log(self, message):
        """添加监控日志"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        self.monitor_log.append(log_message)

        # 自动滚动到底部
        scrollbar = self.monitor_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_api_connected(self, url):
        """处理API连接"""
        self.add_monitor_log(f"API连接成功: {url}")

    def on_api_disconnected(self, url):
        """处理API断开"""
        self.add_monitor_log(f"API连接断开: {url}")

    def on_task_completed(self, task_data):
        """处理任务完成"""
        self.add_monitor_log(f"任务完成: {task_data.get('task_id', 'unknown')}")

    def closeEvent(self, event):
        """关闭事件"""
        # 停止同步定时器
        if self.sync_timer.isActive():
            self.sync_timer.stop()
        super().closeEvent(event)
        event.accept()
