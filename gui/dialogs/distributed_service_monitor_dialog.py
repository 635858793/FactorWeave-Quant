"""
分布式服务综合监控对话框
增强版：包含节点监控和任务监控功能
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTableWidget, QTableWidgetItem, QLabel, QGroupBox,
                             QHeaderView, QMessageBox, QLineEdit, QSpinBox,
                             QFormLayout, QDialogButtonBox, QTabWidget, QWidget,
                             QComboBox, QProgressBar, QStatusBar)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QColor, QFont
from loguru import logger
from datetime import datetime
from typing import List, Dict, Any
import uuid


class NodeStatsWorker(QThread):
    """后台节点状态获取线程"""
    stats_ready = pyqtSignal(list)

    def __init__(self, distributed_service, parent=None):
        super().__init__(parent)
        self.distributed_service = distributed_service
        self._running = True

    def run(self):
        try:
            if self._running:
                nodes = self.distributed_service.get_all_nodes_status()
                self.stats_ready.emit(nodes)
        except Exception as e:
            logger.error(f"后台获取节点状态失败: {e}")

    def stop(self):
        self._running = False


class TaskStatsWorker(QThread):
    """后台任务状态获取线程"""
    stats_ready = pyqtSignal(dict)

    def __init__(self, distributed_service, parent=None):
        super().__init__(parent)
        self.distributed_service = distributed_service
        self._running = True

    def run(self):
        try:
            if self._running:
                task_stats = self.distributed_service.get_task_stats()
                self.stats_ready.emit(task_stats)
        except Exception as e:
            logger.error(f"后台获取任务状态失败: {e}")

    def stop(self):
        self._running = False


class AddNodeDialog(QDialog):
    """添加节点对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加分布式节点")
        self.setMinimumWidth(400)
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()

        self.node_id_input = QLineEdit()
        self.node_id_input.setPlaceholderText("worker-1")
        layout.addRow("节点ID:", self.node_id_input)

        self.host_input = QLineEdit()
        self.host_input.setText("127.0.0.1")
        layout.addRow("主机地址:", self.host_input)

        self.port_input = QSpinBox()
        self.port_input.setRange(5000, 65535)
        self.port_input.setValue(8000)
        layout.addRow("端口:", self.port_input)

        self.node_type_input = QLineEdit()
        self.node_type_input.setText("worker")
        layout.addRow("节点类型:", self.node_type_input)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def get_node_config(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id_input.text().strip(),
            "host": self.host_input.text().strip(),
            "port": self.port_input.value(),
            "node_type": self.node_type_input.text().strip()
        }


class CreateTaskDialog(QDialog):
    """创建任务对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("创建分布式任务")
        self.setMinimumWidth(450)
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()

        self.task_type_combo = QComboBox()
        self.task_type_combo.addItems([
            "backtest", "optimization", "analysis", "data_processing",
            "model_training", "report_generation"
        ])
        layout.addRow("任务类型*:", self.task_type_combo)

        self.task_name_input = QLineEdit()
        self.task_name_input.setPlaceholderText("我的回测任务")
        layout.addRow("任务名称:", self.task_name_input)

        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 10)
        self.priority_spin.setValue(5)
        self.priority_spin.setToolTip("1-10，数字越小优先级越高")
        layout.addRow("优先级:", self.priority_spin)

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("任务描述...")
        layout.addRow("描述:", self.description_input)

        self.params_text = QLineEdit()
        self.params_text.setText("{}")
        self.params_text.setToolTip("JSON格式的任务参数")
        layout.addRow("任务参数(JSON):", self.params_text)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)

        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def _validate_and_accept(self):
        import json
        params_text = self.params_text.text().strip()
        if params_text:
            try:
                json.loads(params_text)
            except json.JSONDecodeError as e:
                QMessageBox.warning(self, "参数错误", f"任务参数JSON格式错误:\n{e}")
                return

        self.accept()

    def get_task_config(self) -> Dict[str, Any]:
        import json
        params_text = self.params_text.text().strip()
        params = json.loads(params_text) if params_text else {}

        return {
            "task_type": self.task_type_combo.currentText(),
            "task_name": self.task_name_input.text().strip() or "未命名任务",
            "priority": self.priority_spin.value(),
            "description": self.description_input.text().strip(),
            "task_data": params
        }


class DistributedServiceMonitorDialog(QDialog):
    """分布式服务综合监控对话框"""

    def __init__(self, distributed_service, parent=None):
        super().__init__(parent)
        self.distributed_service = distributed_service
        self.setWindowTitle("分布式服务监控")
        self.setMinimumSize(1200, 700)

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.refresh_all)

        self.stats_worker = None
        self.task_worker = None

        self.init_ui()
        self.refresh_all()

        self.update_timer.start(5000)

    def init_ui(self):
        main_layout = QVBoxLayout()

        self.title_label = QLabel("<h1>分布式服务监控</h1>")
        main_layout.addWidget(self.title_label)

        self.tab_widget = QTabWidget()

        self.nodes_tab = self._create_nodes_tab()
        self.tasks_tab = self._create_tasks_tab()
        self.queue_tab = self._create_queue_tab()

        self.tab_widget.addTab(self.nodes_tab, "节点监控")
        self.tab_widget.addTab(self.tasks_tab, "任务管理")
        self.tab_widget.addTab(self.queue_tab, "任务队列")

        main_layout.addWidget(self.tab_widget)

        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        main_layout.addWidget(self.status_bar)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        main_layout.addWidget(close_btn)

        self.setLayout(main_layout)

    def _create_nodes_tab(self) -> QWidget:
        """创建节点监控标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        header_layout = QHBoxLayout()
        self.nodes_stats_label = QLabel("总节点: 0 | 活跃: 0 | 忙碌: 0 | 离线: 0")
        header_layout.addWidget(self.nodes_stats_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        button_layout = QHBoxLayout()

        self.refresh_nodes_btn = QPushButton("🔄 刷新")
        self.refresh_nodes_btn.clicked.connect(self.refresh_nodes)
        button_layout.addWidget(self.refresh_nodes_btn)

        self.add_node_btn = QPushButton("➕ 添加节点")
        self.add_node_btn.clicked.connect(self.add_node)
        button_layout.addWidget(self.add_node_btn)

        self.remove_node_btn = QPushButton("➖ 移除节点")
        self.remove_node_btn.clicked.connect(self.remove_node)
        button_layout.addWidget(self.remove_node_btn)

        self.test_node_btn = QPushButton("🧪 测试节点")
        self.test_node_btn.clicked.connect(self.test_node)
        button_layout.addWidget(self.test_node_btn)

        button_layout.addStretch()

        self.auto_refresh_nodes_btn = QPushButton("⏸️ 暂停刷新")
        self.auto_refresh_nodes_btn.setCheckable(True)
        self.auto_refresh_nodes_btn.clicked.connect(self.toggle_nodes_auto_refresh)
        button_layout.addWidget(self.auto_refresh_nodes_btn)

        layout.addLayout(button_layout)

        self.nodes_table = QTableWidget()
        self.nodes_table.setColumnCount(10)
        self.nodes_table.setHorizontalHeaderLabels([
            "节点ID", "地址", "状态", "类型", "CPU使用率",
            "内存使用率", "当前任务", "运行时间", "最后心跳", "功能支持"
        ])
        self.nodes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.nodes_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.nodes_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.nodes_table)

        tab.setLayout(layout)
        return tab

    def _create_tasks_tab(self) -> QWidget:
        """创建任务管理标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        header_layout = QHBoxLayout()
        self.tasks_stats_label = QLabel("总任务: 0 | 运行中: 0 | 已完成: 0 | 失败: 0")
        header_layout.addWidget(self.tasks_stats_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        button_layout = QHBoxLayout()

        self.refresh_tasks_btn = QPushButton("🔄 刷新")
        self.refresh_tasks_btn.clicked.connect(self.refresh_tasks)
        button_layout.addWidget(self.refresh_tasks_btn)

        self.create_task_btn = QPushButton("➕ 创建任务")
        self.create_task_btn.clicked.connect(self.create_task)
        button_layout.addWidget(self.create_task_btn)

        self.cancel_task_btn = QPushButton("❌ 取消任务")
        self.cancel_task_btn.clicked.connect(self.cancel_task)
        button_layout.addWidget(self.cancel_task_btn)

        self.retry_task_btn = QPushButton("🔁 重试任务")
        self.retry_task_btn.clicked.connect(self.retry_task)
        button_layout.addWidget(self.retry_task_btn)

        button_layout.addStretch()

        layout.addLayout(button_layout)

        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(9)
        self.tasks_table.setHorizontalHeaderLabels([
            "任务ID", "任务名称", "类型", "状态", "优先级",
            "分配节点", "进度", "创建时间", "耗时"
        ])
        self.tasks_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tasks_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.tasks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.tasks_table)

        tab.setLayout(layout)
        return tab

    def _create_queue_tab(self) -> QWidget:
        """创建任务队列标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        header_layout = QHBoxLayout()
        self.queue_stats_label = QLabel("队列任务数: 0 | 等待中: 0")
        header_layout.addWidget(self.queue_stats_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        button_layout = QHBoxLayout()

        self.refresh_queue_btn = QPushButton("🔄 刷新")
        self.refresh_queue_btn.clicked.connect(self.refresh_queue)
        button_layout.addWidget(self.refresh_queue_btn)

        self.clear_queue_btn = QPushButton("🗑️ 清空队列")
        self.clear_queue_btn.clicked.connect(self.clear_queue)
        button_layout.addWidget(self.clear_queue_btn)

        button_layout.addStretch()

        layout.addLayout(button_layout)

        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(7)
        self.queue_table.setHorizontalHeaderLabels([
            "任务ID", "任务名称", "类型", "优先级", "状态",
            "创建时间", "等待时间"
        ])
        self.queue_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.queue_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.queue_table)

        tab.setLayout(layout)
        return tab

    def refresh_all(self):
        """刷新所有数据"""
        self.refresh_nodes()
        self.refresh_tasks()
        self.refresh_queue()

    def refresh_nodes(self):
        """刷新节点列表"""
        try:
            if self.stats_worker is not None:
                try:
                    if self.stats_worker.isRunning():
                        return
                except RuntimeError:
                    self.stats_worker = None

            self.stats_worker = NodeStatsWorker(self.distributed_service, self)
            self.stats_worker.stats_ready.connect(self._update_nodes_table)
            self.stats_worker.finished.connect(self._on_nodes_worker_finished)
            self.stats_worker.start()
        except Exception as e:
            logger.error(f"刷新节点失败: {e}")

    def _on_nodes_worker_finished(self):
        if self.stats_worker:
            self.stats_worker.deleteLater()
            self.stats_worker = None

    @pyqtSlot(list)
    def _update_nodes_table(self, nodes):
        try:
            total = len(nodes)
            active = sum(1 for n in nodes if n.get('status') == 'active')
            busy = sum(1 for n in nodes if n.get('status') == 'busy')
            offline = sum(1 for n in nodes if n.get('status') == 'offline')

            self.nodes_stats_label.setText(
                f"总节点: {total} | 活跃: {active} | 忙碌: {busy} | 离线: {offline}"
            )

            self.nodes_table.setRowCount(len(nodes))

            for row, node in enumerate(nodes):
                self.nodes_table.setItem(row, 0, QTableWidgetItem(node.get('node_id', 'N/A')))

                address = f"{node.get('host', 'N/A')}:{node.get('port', 'N/A')}"
                self.nodes_table.setItem(row, 1, QTableWidgetItem(address))

                status_item = QTableWidgetItem(node.get('status', 'unknown'))
                status = node.get('status', 'unknown')
                if status == 'active':
                    status_item.setBackground(QColor(144, 238, 144))
                elif status == 'busy':
                    status_item.setBackground(QColor(255, 255, 0))
                elif status == 'offline':
                    status_item.setBackground(QColor(255, 182, 193))
                self.nodes_table.setItem(row, 2, status_item)

                self.nodes_table.setItem(row, 3, QTableWidgetItem(node.get('node_type', 'N/A')))

                cpu_usage = node.get('cpu_usage_percent', 0)
                self.nodes_table.setItem(row, 4, QTableWidgetItem(f"{cpu_usage:.1f}%"))

                mem_usage = node.get('memory_usage_percent', 0)
                self.nodes_table.setItem(row, 5, QTableWidgetItem(f"{mem_usage:.1f}%"))

                current_tasks = node.get('current_tasks', 0)
                self.nodes_table.setItem(row, 6, QTableWidgetItem(str(current_tasks)))

                uptime = node.get('uptime_seconds', 0)
                uptime_str = self._format_uptime(uptime)
                self.nodes_table.setItem(row, 7, QTableWidgetItem(uptime_str))

                last_heartbeat = node.get('last_heartbeat')
                if last_heartbeat:
                    if isinstance(last_heartbeat, datetime):
                        heartbeat_str = last_heartbeat.strftime("%H:%M:%S")
                    else:
                        heartbeat_str = str(last_heartbeat)
                else:
                    heartbeat_str = "N/A"
                self.nodes_table.setItem(row, 8, QTableWidgetItem(heartbeat_str))

                capabilities = node.get('capabilities', [])
                self.nodes_table.setItem(row, 9, QTableWidgetItem(', '.join(capabilities)))

        except Exception as e:
            logger.error(f"刷新节点列表失败: {e}")
            QMessageBox.warning(self, "错误", f"刷新节点列表失败: {e}")

    def refresh_tasks(self):
        """刷新任务列表"""
        try:
            if self.task_worker is not None:
                try:
                    if self.task_worker.isRunning():
                        return
                except RuntimeError:
                    self.task_worker = None

            self.task_worker = TaskStatsWorker(self.distributed_service, self)
            self.task_worker.stats_ready.connect(self._update_tasks_table)
            self.task_worker.finished.connect(self._on_tasks_worker_finished)
            self.task_worker.start()
        except Exception as e:
            logger.error(f"刷新任务失败: {e}")

    def _on_tasks_worker_finished(self):
        if self.task_worker:
            self.task_worker.deleteLater()
            self.task_worker = None

    @pyqtSlot(dict)
    def _update_tasks_table(self, task_stats):
        try:
            running_tasks = task_stats.get('running_tasks', [])
            completed_tasks = task_stats.get('completed_tasks', [])

            total = len(running_tasks) + len(completed_tasks)
            running = len(running_tasks)
            completed = len(completed_tasks)
            failed = sum(1 for t in completed_tasks if t.get('status') == 'failed')

            self.tasks_stats_label.setText(
                f"总任务: {total} | 运行中: {running} | 已完成: {completed} | 失败: {failed}"
            )

            all_tasks = running_tasks + completed_tasks
            self.tasks_table.setRowCount(len(all_tasks))

            for row, task in enumerate(all_tasks):
                self.tasks_table.setItem(row, 0, QTableWidgetItem(task.get('task_id', 'N/A')[:8] + '...'))
                self.tasks_table.setItem(row, 1, QTableWidgetItem(task.get('task_name', task.get('task_type', 'N/A'))))
                self.tasks_table.setItem(row, 2, QTableWidgetItem(task.get('task_type', 'N/A')))

                status_item = QTableWidgetItem(task.get('status', 'unknown'))
                status = task.get('status', 'unknown')
                if status == 'running':
                    status_item.setBackground(QColor(144, 238, 144))
                elif status == 'completed':
                    status_item.setBackground(QColor(173, 216, 230))
                elif status == 'failed':
                    status_item.setBackground(QColor(255, 182, 193))
                self.tasks_table.setItem(row, 3, status_item)

                priority = task.get('priority', 5)
                self.tasks_table.setItem(row, 4, QTableWidgetItem(str(priority)))

                assigned_node = task.get('assigned_node', 'N/A')
                self.tasks_table.setItem(row, 5, QTableWidgetItem(assigned_node))

                progress = task.get('progress', 0)
                progress_item = QTableWidgetItem(f"{progress}%")
                if status == 'running':
                    progress_item.setBackground(QColor(255, 255, 0))
                self.tasks_table.setItem(row, 6, progress_item)

                created_time = task.get('created_time')
                if created_time:
                    if isinstance(created_time, datetime):
                        created_str = created_time.strftime("%H:%M:%S")
                    else:
                        created_str = str(created_time)[:19]
                else:
                    created_str = "N/A"
                self.tasks_table.setItem(row, 7, QTableWidgetItem(created_str))

                duration = task.get('duration', 'N/A')
                self.tasks_table.setItem(row, 8, QTableWidgetItem(str(duration)))

        except Exception as e:
            logger.error(f"刷新任务列表失败: {e}")

    def refresh_queue(self):
        """刷新任务队列"""
        try:
            task_stats = self.distributed_service.get_task_stats()
            queued_tasks = task_stats.get('queued_tasks', [])

            self.queue_stats_label.setText(
                f"队列任务数: {len(queued_tasks)} | 等待中: {len(queued_tasks)}"
            )

            self.queue_table.setRowCount(len(queued_tasks))

            for row, task in enumerate(queued_tasks):
                self.queue_table.setItem(row, 0, QTableWidgetItem(task.get('task_id', 'N/A')[:8] + '...'))
                self.queue_table.setItem(row, 1, QTableWidgetItem(task.get('task_name', task.get('task_type', 'N/A'))))
                self.queue_table.setItem(row, 2, QTableWidgetItem(task.get('task_type', 'N/A')))

                priority = task.get('priority', 5)
                priority_item = QTableWidgetItem(str(priority))
                if priority <= 3:
                    priority_item.setBackground(QColor(255, 182, 193))
                elif priority <= 6:
                    priority_item.setBackground(QColor(255, 255, 0))
                self.queue_table.setItem(row, 3, priority_item)

                self.queue_table.setItem(row, 4, QTableWidgetItem(task.get('status', 'pending')))

                created_time = task.get('created_time')
                if created_time:
                    if isinstance(created_time, datetime):
                        created_str = created_time.strftime("%H:%M:%S")
                    else:
                        created_str = str(created_time)[:19]
                else:
                    created_str = "N/A"
                self.queue_table.setItem(row, 5, QTableWidgetItem(created_str))

                wait_time = task.get('wait_time', 'N/A')
                self.queue_table.setItem(row, 6, QTableWidgetItem(str(wait_time)))

        except Exception as e:
            logger.error(f"刷新队列失败: {e}")

    def _format_uptime(self, seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            return f"{seconds // 60}分钟"
        elif seconds < 86400:
            return f"{seconds // 3600}小时"
        else:
            return f"{seconds // 86400}天"

    def add_node(self):
        dialog = AddNodeDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            config = dialog.get_node_config()

            if not config['node_id'] or not config['host']:
                QMessageBox.warning(self, "警告", "节点ID和主机地址不能为空")
                return

            try:
                success = self.distributed_service.add_node(
                    node_id=config['node_id'],
                    host=config['host'],
                    port=config['port'],
                    node_type=config['node_type']
                )

                if success:
                    QMessageBox.information(self, "成功", f"节点 {config['node_id']} 已添加")
                    self.refresh_nodes()
                else:
                    QMessageBox.warning(
                        self, "失败",
                        f"添加节点失败：节点 '{config['node_id']}' 可能已存在"
                    )

            except Exception as e:
                logger.error(f"添加节点失败: {e}")
                QMessageBox.critical(self, "错误", f"添加节点失败: {e}")

    def remove_node(self):
        selected_rows = self.nodes_table.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, "警告", "请先选择要移除的节点")
            return

        row = selected_rows[0].row()
        node_id = self.nodes_table.item(row, 0).text()

        reply = QMessageBox.question(
            self, "确认", f"确定要移除节点 {node_id} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                success = self.distributed_service.remove_node(node_id)
                if success:
                    QMessageBox.information(self, "成功", f"节点 {node_id} 已移除")
                    self.refresh_nodes()
                else:
                    QMessageBox.warning(self, "失败", "移除节点失败")
            except Exception as e:
                logger.error(f"移除节点失败: {e}")
                QMessageBox.critical(self, "错误", f"移除节点失败: {e}")

    def test_node(self):
        selected_rows = self.nodes_table.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, "警告", "请先选择要测试的节点")
            return

        row = selected_rows[0].row()
        node_id = self.nodes_table.item(row, 0).text()

        try:
            result = self.distributed_service.test_node_connection(node_id)

            if result and result.get('success'):
                response_time = result.get('response_time', 'N/A')
                capabilities = result.get('capabilities', [])
                capabilities_str = ', '.join(capabilities) if capabilities else '未知'

                message = f"节点 {node_id} 连接正常\n响应时间: {response_time}ms\n支持功能: {capabilities_str}"
                QMessageBox.information(self, "测试成功", message)
                self.refresh_nodes()
            else:
                error_msg = result.get('error', '未知错误') if result else '无响应'
                QMessageBox.warning(self, "测试失败", f"节点 {node_id} 无法连接\n错误: {error_msg}")
                self.refresh_nodes()

        except Exception as e:
            logger.error(f"测试节点失败: {e}")
            QMessageBox.critical(self, "错误", f"测试节点失败: {e}")

    def toggle_nodes_auto_refresh(self):
        if self.auto_refresh_nodes_btn.isChecked():
            self.update_timer.stop()
            self.auto_refresh_nodes_btn.setText("▶️ 继续刷新")
        else:
            self.update_timer.start(5000)
            self.auto_refresh_nodes_btn.setText("⏸️ 暂停刷新")

    def create_task(self):
        dialog = CreateTaskDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            config = dialog.get_task_config()

            try:
                task_id = str(uuid.uuid4())[:8]

                from core.services.distributed_service import DistributedTask
                task = DistributedTask(
                    task_id=task_id,
                    task_type=config['task_type'],
                    task_data=config['task_data'],
                    priority=config['priority']
                )

                task.task_name = config['task_name']

                success = self.distributed_service.submit_task(task)

                if success:
                    QMessageBox.information(self, "成功", f"任务已创建: {task_id}")
                    self.refresh_all()
                else:
                    QMessageBox.warning(self, "失败", "提交任务失败")

            except Exception as e:
                logger.error(f"创建任务失败: {e}")
                QMessageBox.critical(self, "错误", f"创建任务失败: {e}")

    def cancel_task(self):
        selected_rows = self.tasks_table.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, "警告", "请先选择要取消的任务")
            return

        row = selected_rows[0].row()
        task_id = self.tasks_table.item(row, 0).text()

        reply = QMessageBox.question(
            self, "确认", f"确定要取消任务 {task_id} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                success = self.distributed_service.cancel_task(task_id)
                if success:
                    QMessageBox.information(self, "成功", f"任务 {task_id} 已取消")
                    self.refresh_all()
                else:
                    QMessageBox.warning(self, "失败", "取消任务失败")
            except Exception as e:
                logger.error(f"取消任务失败: {e}")
                QMessageBox.critical(self, "错误", f"取消任务失败: {e}")

    def retry_task(self):
        selected_rows = self.tasks_table.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, "警告", "请先选择要重试的任务")
            return

        row = selected_rows[0].row()
        task_id = self.tasks_table.item(row, 0).text()

        try:
            success = self.distributed_service.retry_task(task_id)
            if success:
                QMessageBox.information(self, "成功", f"任务 {task_id} 已重新提交")
                self.refresh_all()
            else:
                QMessageBox.warning(self, "失败", "重试任务失败")
        except Exception as e:
            logger.error(f"重试任务失败: {e}")
            QMessageBox.critical(self, "错误", f"重试任务失败: {e}")

    def clear_queue(self):
        reply = QMessageBox.question(
            self, "确认", "确定要清空任务队列吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.distributed_service.clear_task_queue()
                QMessageBox.information(self, "成功", "任务队列已清空")
                self.refresh_all()
            except Exception as e:
                logger.error(f"清空队列失败: {e}")
                QMessageBox.critical(self, "错误", f"清空队列失败: {e}")

    def closeEvent(self, event):
        self.update_timer.stop()

        if self.stats_worker is not None:
            try:
                if self.stats_worker.isRunning():
                    self.stats_worker.stop()
                    self.stats_worker.wait(1000)
            except RuntimeError:
                pass

        if self.task_worker is not None:
            try:
                if self.task_worker.isRunning():
                    self.task_worker.stop()
                    self.task_worker.wait(1000)
            except RuntimeError:
                pass

        event.accept()
