"""
TDX服务器管理器widget

提供TDX（通达信）服务器的可视化管理功能，包括：
- 服务器状态实时监控
- 添加/删除服务器
- 手动服务器测试
- 当前服务器切换
- 自动发现最佳服务器

作者: FactorWeave-Quant 开发团队
版本: 1.0.0
日期: 2024
"""

from loguru import logger
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QProgressBar, QFrame, QSplitter,
    QCheckBox, QTextEdit, QDialog, QFormLayout, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QPixmap

logger = logger.bind(module=__name__)

class ServerDiscoveryWorker(QThread):
    """服务器发现工作线程"""

    discovery_progress = pyqtSignal(int, str)  # progress, message
    discovery_complete = pyqtSignal(list)  # discovered_servers

    def __init__(self, discovery_service, db_manager):
        super().__init__()
        self.discovery_service = discovery_service
        self.db_manager = db_manager
        self.running = False

    def run(self):
        """执行服务器发现"""
        self.running = True
        try:
            import asyncio

            # 创建异步事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # 执行异步发现
                self.discovery_progress.emit(10, "开始联网查询服务器...")

                # 发现服务器
                servers = loop.run_until_complete(
                    self.discovery_service.discover_servers(include_online=True, test_connectivity=True)
                )

                if not self.running:
                    return

                self.discovery_progress.emit(70, "保存服务器到数据库...")

                # 保存到数据库
                saved_count = 0
                for server in servers:
                    if not self.running:
                        break

                    success = self.db_manager.save_tdx_server(
                        host=server['host'],
                        port=server['port'],
                        status=server['status'],
                        response_time=server.get('response_time'),
                        location=server.get('location'),
                        source=server.get('source', 'online'),
                        last_tested=server.get('last_tested')
                    )
                    if success:
                        saved_count += 1

                self.discovery_progress.emit(100, "服务器发现完成")
                self.discovery_complete.emit(servers)

                logger.info(f"服务器发现完成: 发现 {len(servers)} 个，保存 {saved_count} 个")

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"服务器发现失败: {e}")
            self.discovery_progress.emit(100, f"发现失败: {e}")
            self.discovery_complete.emit([])
        finally:
            self.running = False

    def stop(self):
        """停止发现"""
        self.running = False

class ServerTestWorker(QThread):
    """服务器测试工作线程"""

    test_progress = pyqtSignal(int, str)  # progress, message
    test_complete = pyqtSignal(list)  # server_status_list

    def __init__(self, plugin, test_all=True, target_server=None):
        super().__init__()
        self.plugin = plugin
        self.test_all = test_all
        self.target_server = target_server
        self.running = False

    def run(self):
        """执行服务器测试"""
        self.running = True
        try:
            if self.test_all:
                # 测试所有服务器
                self.test_progress.emit(0, "开始测试所有服务器...")
                self.plugin.refresh_server_status()

                for i in range(101):
                    if not self.running:
                        break
                    self.test_progress.emit(i, f"测试进度: {i}%")
                    self.msleep(20)  # 模拟进度

                server_list = self.plugin.get_server_status()
                self.test_complete.emit(server_list)
            else:
                # 测试单个服务器
                if self.target_server:
                    host, port = self.target_server
                    self.test_progress.emit(0, f"测试服务器 {host}:{port}...")

                    result = self.plugin.test_server(host, port)
                    server_list = self.plugin.get_server_status()

                    self.test_progress.emit(100, "测试完成")
                    self.test_complete.emit(server_list)

        except Exception as e:
            logger.error(f"服务器测试失败: {e}")
            self.test_progress.emit(100, f"测试失败: {e}")
        finally:
            self.running = False

    def stop(self):
        """停止测试"""
        self.running = False

class AddServerDialog(QDialog):
    """添加服务器对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("添加TDX服务器")
        self.setModal(True)
        self.resize(400, 200)

        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 表单区域
        form_layout = QFormLayout()

        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("例如: 119.147.212.81")
        form_layout.addRow("服务器地址:", self.host_edit)

        self.port_spinbox = QSpinBox()
        self.port_spinbox.setRange(1, 65535)
        self.port_spinbox.setValue(7709)
        form_layout.addRow("端口:", self.port_spinbox)

        layout.addLayout(form_layout)

        # 按钮区域
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_server_info(self):
        """获取服务器信息"""
        return self.host_edit.text().strip(), self.port_spinbox.value()

class TdxServerManagerWidget(QWidget):
    """TDX服务器管理器widget"""

    server_changed = pyqtSignal(str, int)  # host, port

    def __init__(self, plugin=None, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.test_worker = None

        self.init_ui()
        self.setup_timer()

        if self.plugin:
            self.refresh_server_list()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 标题和控制区域
        header_layout = QHBoxLayout()

        title_label = QLabel("TDX服务器管理")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # 控制按钮
        self.refresh_btn = QPushButton("刷新状态")
        self.refresh_btn.clicked.connect(self.refresh_server_status)
        header_layout.addWidget(self.refresh_btn)

        self.fetch_btn = QPushButton("获取服务器")
        self.fetch_btn.clicked.connect(self.fetch_servers_online)
        self.fetch_btn.setToolTip("联网查询最新可用的TDX服务器IP地址")
        self.fetch_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        header_layout.addWidget(self.fetch_btn)

        self.add_server_btn = QPushButton("添加服务器")
        self.add_server_btn.clicked.connect(self.add_server)
        header_layout.addWidget(self.add_server_btn)

        self.test_all_btn = QPushButton("测试所有")
        self.test_all_btn.clicked.connect(self.test_all_servers)
        header_layout.addWidget(self.test_all_btn)

        layout.addLayout(header_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 状态信息
        self.status_label = QLabel("准备就绪")
        self.status_label.setStyleSheet("color: blue; font-weight: bold;")
        layout.addWidget(self.status_label)

        # 服务器列表表格
        self.server_table = QTableWidget()
        self.init_server_table()
        layout.addWidget(self.server_table)

        # 自动刷新选项
        auto_refresh_layout = QHBoxLayout()

        self.auto_refresh_checkbox = QCheckBox("自动刷新状态")
        self.auto_refresh_checkbox.setChecked(True)
        self.auto_refresh_checkbox.stateChanged.connect(self.toggle_auto_refresh)
        auto_refresh_layout.addWidget(self.auto_refresh_checkbox)

        auto_refresh_layout.addStretch()

        self.current_server_label = QLabel("当前服务器: 未知")
        self.current_server_label.setStyleSheet("color: green; font-weight: bold;")
        auto_refresh_layout.addWidget(self.current_server_label)

        layout.addLayout(auto_refresh_layout)

    def init_server_table(self):
        """初始化服务器列表表格"""
        headers = ["状态", "地址", "端口", "响应时间", "状态描述", "最后测试", "操作"]
        self.server_table.setColumnCount(len(headers))
        self.server_table.setHorizontalHeaderLabels(headers)

        # 设置表格属性
        self.server_table.setAlternatingRowColors(True)
        self.server_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.server_table.verticalHeader().setVisible(False)

        # 设置列宽
        header = self.server_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.resizeSection(0, 60)   # 状态
        header.resizeSection(1, 120)  # 地址
        header.resizeSection(2, 60)   # 端口
        header.resizeSection(3, 80)   # 响应时间
        header.resizeSection(4, 80)   # 状态描述
        header.resizeSection(5, 120)  # 最后测试

    def setup_timer(self):
        """设置定时器"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_server_list)
        self.refresh_timer.start(30000)  # 30秒刷新一次

    def toggle_auto_refresh(self, state):
        """切换自动刷新"""
        if state == Qt.Checked:
            self.refresh_timer.start(30000)
        else:
            self.refresh_timer.stop()

    def set_plugin(self, plugin):
        """设置插件实例"""
        self.plugin = plugin
        if plugin:
            self.refresh_server_list()

    def refresh_server_list(self):
        """刷新服务器列表"""
        if not self.plugin:
            return

        try:
            server_list = self.plugin.get_server_status()
            self.update_server_table(server_list)
            self.update_current_server_info()

        except Exception as e:
            logger.error(f"刷新服务器列表失败: {e}")
            self.status_label.setText(f"刷新失败: {e}")

    def update_server_table(self, server_list):
        """更新服务器表格"""
        self.server_table.setRowCount(len(server_list))

        for row, server in enumerate(server_list):
            # 状态指示器
            status_item = QTableWidgetItem()
            if server['available']:
                if server['is_current']:
                    status_item.setText("★使用中")
                    status_item.setBackground(QColor(144, 238, 144))  # 浅绿色
                else:
                    status_item.setText("●可用")
                    status_item.setBackground(QColor(173, 216, 230))  # 浅蓝色
            else:
                status_item.setText("●不可用")
                status_item.setBackground(QColor(255, 182, 193))  # 浅红色

            status_item.setTextAlignment(Qt.AlignCenter)
            self.server_table.setItem(row, 0, status_item)

            # 地址
            host_item = QTableWidgetItem(server['host'])
            host_item.setTextAlignment(Qt.AlignCenter)
            self.server_table.setItem(row, 1, host_item)

            # 端口
            port_item = QTableWidgetItem(str(server['port']))
            port_item.setTextAlignment(Qt.AlignCenter)
            self.server_table.setItem(row, 2, port_item)

            # 响应时间
            if server['response_time_ms'] < 9999:
                response_text = f"{server['response_time_ms']}ms"
            else:
                response_text = "超时"
            response_item = QTableWidgetItem(response_text)
            response_item.setTextAlignment(Qt.AlignCenter)
            self.server_table.setItem(row, 3, response_item)

            # 状态描述
            status_desc_item = QTableWidgetItem(server['status_text'])
            status_desc_item.setTextAlignment(Qt.AlignCenter)
            self.server_table.setItem(row, 4, status_desc_item)

            # 最后测试时间
            last_test = server.get('last_test', '')
            if last_test:
                try:
                    dt = datetime.fromisoformat(last_test.replace('Z', '+00:00'))
                    test_text = dt.strftime('%H:%M:%S')
                except Exception:
                    test_text = last_test
            else:
                test_text = "未测试"

            test_item = QTableWidgetItem(test_text)
            test_item.setTextAlignment(Qt.AlignCenter)
            self.server_table.setItem(row, 5, test_item)

            # 操作按钮
            self.create_action_buttons(row, server)

    def create_action_buttons(self, row, server):
        """创建操作按钮"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        # 测试按钮
        test_btn = QPushButton("测试")
        test_btn.setMaximumSize(QSize(50, 25))
        test_btn.clicked.connect(
            lambda: self.test_single_server(server['host'], server['port'])
        )
        layout.addWidget(test_btn)

        # 设为当前按钮
        if not server['is_current'] and server['available']:
            set_current_btn = QPushButton("使用")
            set_current_btn.setMaximumSize(QSize(50, 25))
            set_current_btn.clicked.connect(
                lambda: self.set_current_server(server['host'], server['port'])
            )
            layout.addWidget(set_current_btn)

        # 删除按钮
        if len(self.plugin.server_list) > 1:  # 保留至少一个服务器
            delete_btn = QPushButton("删除")
            delete_btn.setMaximumSize(QSize(50, 25))
            delete_btn.setStyleSheet("QPushButton { color: red; }")
            delete_btn.clicked.connect(
                lambda: self.remove_server(server['host'], server['port'])
            )
            layout.addWidget(delete_btn)

        self.server_table.setCellWidget(row, 6, widget)

    def update_current_server_info(self):
        """更新当前服务器信息"""
        if not self.plugin:
            return

        try:
            current_server = self.plugin.current_server
            if current_server:
                host, port = current_server
                self.current_server_label.setText(f"当前服务器: {host}:{port}")
                self.current_server_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.current_server_label.setText("当前服务器: 未设置")
                self.current_server_label.setStyleSheet("color: red; font-weight: bold;")
        except Exception as e:
            logger.error(f"更新当前服务器信息失败: {e}")

    def add_server(self):
        """添加服务器"""
        dialog = AddServerDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            host, port = dialog.get_server_info()

            if not host:
                QMessageBox.warning(self, "警告", "请输入服务器地址")
                return

            try:
                if self.plugin.add_server(host, port):
                    self.status_label.setText(f"已添加服务器: {host}:{port}")
                    self.refresh_server_list()
                else:
                    QMessageBox.warning(self, "警告", "服务器已存在或添加失败")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"添加服务器失败: {e}")

    def remove_server(self, host, port):
        """删除服务器"""
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除服务器 {host}:{port} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                if self.plugin.remove_server(host, port):
                    self.status_label.setText(f"已删除服务器: {host}:{port}")
                    self.refresh_server_list()
                else:
                    QMessageBox.warning(self, "警告", "删除服务器失败")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除服务器失败: {e}")

    def set_current_server(self, host, port):
        """设置当前服务器"""
        try:
            if self.plugin.set_current_server(host, port):
                self.status_label.setText(f"已切换到服务器: {host}:{port}")
                self.refresh_server_list()
                self.server_changed.emit(host, port)
            else:
                QMessageBox.warning(self, "警告", "切换服务器失败")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"切换服务器失败: {e}")

    def test_single_server(self, host, port):
        """测试单个服务器"""
        if self.test_worker and self.test_worker.isRunning():
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"正在测试服务器 {host}:{port}...")

        self.test_worker = ServerTestWorker(
            self.plugin,
            test_all=False,
            target_server=(host, port)
        )
        self.test_worker.test_progress.connect(self.update_test_progress)
        self.test_worker.test_complete.connect(self.test_complete)
        self.test_worker.start()

    def test_all_servers(self):
        """测试所有服务器"""
        if self.test_worker and self.test_worker.isRunning():
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("正在测试所有服务器...")

        self.test_worker = ServerTestWorker(self.plugin, test_all=True)
        self.test_worker.test_progress.connect(self.update_test_progress)
        self.test_worker.test_complete.connect(self.test_complete)
        self.test_worker.start()

    def refresh_server_status(self):
        """刷新服务器状态"""
        if not self.plugin:
            return

        try:
            self.plugin.refresh_server_status()
            self.refresh_server_list()
            self.status_label.setText("服务器状态已刷新")
        except Exception as e:
            logger.error(f"刷新服务器状态失败: {e}")
            self.status_label.setText(f"刷新失败: {e}")

    def update_test_progress(self, progress, message):
        """更新测试进度"""
        self.progress_bar.setValue(progress)
        self.status_label.setText(message)

    def test_complete(self, server_list):
        """测试完成"""
        self.progress_bar.setVisible(False)
        self.update_server_table(server_list)
        self.status_label.setText("测试完成")

        # 统计可用服务器数量
        available_count = sum(1 for s in server_list if s['available'])
        total_count = len(server_list)

        self.status_label.setText(
            f"测试完成 - 可用服务器: {available_count}/{total_count}"
        )

    def fetch_servers_online(self):
        """联网获取最新的TDX服务器列表"""
        try:
            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("正在联网查询最新服务器...")
            self.fetch_btn.setEnabled(False)

            # 启动服务器发现工作线程
            from core.services.tdx_server_discovery import get_discovery_service
            from core.database.tdx_server_manager import get_tdx_db_manager

            self.discovery_worker = ServerDiscoveryWorker(get_discovery_service(), get_tdx_db_manager())
            self.discovery_worker.discovery_progress.connect(self.update_discovery_progress)
            self.discovery_worker.discovery_complete.connect(self.discovery_complete)
            self.discovery_worker.start()

        except Exception as e:
            logger.error(f"启动服务器发现失败: {e}")
            self.status_label.setText(f"获取服务器失败: {e}")
            self.progress_bar.setVisible(False)
            self.fetch_btn.setEnabled(True)

    def update_discovery_progress(self, progress, message):
        """更新发现进度"""
        self.progress_bar.setValue(progress)
        self.status_label.setText(message)

    def discovery_complete(self, discovered_servers):
        """服务器发现完成"""
        try:
            self.progress_bar.setVisible(False)
            self.fetch_btn.setEnabled(True)

            if discovered_servers:
                # 统计发现的服务器
                total_count = len(discovered_servers)
                available_count = sum(1 for s in discovered_servers if s.get('status') == 'available')

                # 更新插件的服务器列表
                if self.plugin:
                    # 添加发现的服务器到插件
                    for server in discovered_servers:
                        if server.get('status') == 'available':
                            self.plugin.add_server(server['host'], server['port'])

                # 刷新界面
                self.refresh_server_status()

                # 显示结果
                QMessageBox.information(
                    self,
                    "服务器获取完成",
                    f"成功发现 {total_count} 个服务器，其中 {available_count} 个可用。\n"
                    f"可用服务器已自动添加到列表中。"
                )

                self.status_label.setText(f"发现完成: {available_count}/{total_count} 个服务器可用")
            else:
                QMessageBox.warning(
                    self,
                    "服务器获取失败",
                    "未能发现可用的服务器，请检查网络连接或稍后重试。"
                )
                self.status_label.setText("未发现可用服务器")

        except Exception as e:
            logger.error(f"处理发现结果失败: {e}")
            self.status_label.setText(f"处理结果失败: {e}")

    def closeEvent(self, event):
        """关闭事件"""
        if self.test_worker and self.test_worker.isRunning():
            self.test_worker.stop()
            self.test_worker.wait()

        if hasattr(self, 'discovery_worker') and self.discovery_worker and self.discovery_worker.isRunning():
            self.discovery_worker.stop()
            self.discovery_worker.wait()

        self.refresh_timer.stop()
        super().closeEvent(event)
        event.accept()
