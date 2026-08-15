#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
实时写入功能UI组件

包含四个主要面板：
1. RealtimeWriteConfigPanel - 配置面板
2. RealtimeWriteControlPanel - 控制面板  
3. RealtimeWriteMonitoringWidget - 监控面板
4. IPMonitorWidget - IP使用监控面板（通达信）

作者: FactorWeave-Quant团队
版本: 1.0
"""

from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox,
    QCheckBox, QComboBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QWidget, QTabWidget, QTextEdit, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread
from PyQt5.QtGui import QFont, QColor
from loguru import logger
from typing import Dict, Any, Optional
from datetime import datetime
import threading


class RealtimeWriteConfigPanel(QGroupBox):
    """实时写入配置面板"""

    config_changed = pyqtSignal(dict)

    def __init__(self):
        super().__init__("实时写入配置")
        self.init_ui()
        self.config_lock = threading.Lock()

    def init_ui(self):
        """初始化UI"""
        layout = QGridLayout()

        # 批量大小配置
        layout.addWidget(QLabel("批量大小:"), 0, 0)
        self.batch_size_spinbox = QSpinBox()
        self.batch_size_spinbox.setRange(1, 1000)
        self.batch_size_spinbox.setValue(100)
        self.batch_size_spinbox.setSuffix(" 条")
        self.batch_size_spinbox.valueChanged.connect(self.on_config_changed)
        layout.addWidget(self.batch_size_spinbox, 0, 1)

        # 并发数配置
        layout.addWidget(QLabel("并发数:"), 0, 2)
        self.concurrency_spinbox = QSpinBox()
        self.concurrency_spinbox.setRange(1, 16)
        self.concurrency_spinbox.setValue(4)
        self.concurrency_spinbox.valueChanged.connect(self.on_config_changed)
        layout.addWidget(self.concurrency_spinbox, 0, 3)

        # 超时时间配置
        layout.addWidget(QLabel("超时时间:"), 1, 0)
        self.timeout_spinbox = QSpinBox()
        self.timeout_spinbox.setRange(10, 3600)
        self.timeout_spinbox.setValue(300)
        self.timeout_spinbox.setSuffix(" 秒")
        self.timeout_spinbox.valueChanged.connect(self.on_config_changed)
        layout.addWidget(self.timeout_spinbox, 1, 1)

        # 内存监控启用
        layout.addWidget(QLabel("监控选项:"), 1, 2)
        self.enable_memory_monitor = QCheckBox("内存监控")
        self.enable_memory_monitor.setChecked(True)
        self.enable_memory_monitor.stateChanged.connect(self.on_config_changed)
        layout.addWidget(self.enable_memory_monitor, 1, 3)

        # 性能监控启用
        self.enable_performance_monitor = QCheckBox("性能监控")
        self.enable_performance_monitor.setChecked(True)
        self.enable_performance_monitor.stateChanged.connect(self.on_config_changed)
        layout.addWidget(self.enable_performance_monitor, 2, 0)

        # 质量监控启用
        self.enable_quality_monitor = QCheckBox("数据质量监控")
        self.enable_quality_monitor.setChecked(True)
        self.enable_quality_monitor.stateChanged.connect(self.on_config_changed)
        layout.addWidget(self.enable_quality_monitor, 2, 1)

        # 写入策略
        layout.addWidget(QLabel("写入策略:"), 2, 2)
        self.write_strategy_combo = QComboBox()
        self.write_strategy_combo.addItems(["实时写入", "批量写入", "自适应"])
        self.write_strategy_combo.currentTextChanged.connect(self.on_config_changed)
        layout.addWidget(self.write_strategy_combo, 2, 3)

        self.setLayout(layout)

    def on_config_changed(self):
        """配置变更处理"""
        config = self.get_config()
        self.config_changed.emit(config)
        logger.debug(f"配置已变更: {config}")

    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        with self.config_lock:
            return {
                'batch_size': self.batch_size_spinbox.value(),
                'concurrency': self.concurrency_spinbox.value(),
                'timeout': self.timeout_spinbox.value(),
                'enable_memory_monitor': self.enable_memory_monitor.isChecked(),
                'enable_performance_monitor': self.enable_performance_monitor.isChecked(),
                'enable_quality_monitor': self.enable_quality_monitor.isChecked(),
                'write_strategy': self.write_strategy_combo.currentText()
            }

    def set_config(self, config: Dict[str, Any]):
        """设置配置"""
        with self.config_lock:
            self.batch_size_spinbox.setValue(config.get('batch_size', 100))
            self.concurrency_spinbox.setValue(config.get('concurrency', 4))
            self.timeout_spinbox.setValue(config.get('timeout', 300))
            self.enable_memory_monitor.setChecked(config.get('enable_memory_monitor', True))
            self.enable_performance_monitor.setChecked(config.get('enable_performance_monitor', True))
            self.enable_quality_monitor.setChecked(config.get('enable_quality_monitor', True))


class RealtimeWriteControlPanel(QGroupBox):
    """实时写入控制面板"""

    pause_requested = pyqtSignal()
    resume_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self):
        super().__init__("实时写入控制")
        self.is_running = False
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout()

        # 暂停按钮
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.pause_requested.emit)
        layout.addWidget(self.pause_btn)

        # 恢复按钮
        self.resume_btn = QPushButton("恢复")
        self.resume_btn.setEnabled(False)
        self.resume_btn.clicked.connect(self.resume_requested.emit)
        layout.addWidget(self.resume_btn)

        # 取消按钮
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(self.cancel_btn)

        # 分隔符
        layout.addSpacing(20)

        # 统计标签
        self.stats_label = QLabel("就绪")
        self.stats_label.setStyleSheet("color: green; font-weight: bold;")
        layout.addWidget(self.stats_label)

        layout.addStretch()
        self.setLayout(layout)

    def set_running(self, is_running: bool):
        """设置运行状态"""
        self.is_running = is_running
        self.pause_btn.setEnabled(is_running)
        self.resume_btn.setEnabled(False)
        self.cancel_btn.setEnabled(is_running)

        if is_running:
            self.stats_label.setText("运行中")
            self.stats_label.setStyleSheet("color: blue; font-weight: bold;")
        else:
            self.stats_label.setText("已停止")
            self.stats_label.setStyleSheet("color: gray; font-weight: bold;")

    def set_paused(self, is_paused: bool):
        """设置暂停状态"""
        self.pause_btn.setEnabled(not is_paused and self.is_running)
        self.resume_btn.setEnabled(is_paused)

        if is_paused:
            self.stats_label.setText("已暂停")
            self.stats_label.setStyleSheet("color: orange; font-weight: bold;")

    def update_stats(self, stats: Dict[str, Any]):
        """更新统计信息"""
        success = stats.get('success_count', 0)
        failure = stats.get('failure_count', 0)
        total = stats.get('total_count', 0)
        speed = stats.get('write_speed', 0)

        text = f"成功: {success} | 失败: {failure} | 总计: {total} | 速度: {speed:.0f}条/秒"
        self.stats_label.setText(text)
        self.stats_label.setStyleSheet("color: navy; font-weight: bold;")


class IPMonitorWidget(QWidget):
    """IP使用监控组件（通达信）"""

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # IP统计摘要
        ip_summary_layout = QHBoxLayout()
        ip_summary_layout.addWidget(QLabel("健康IP:"))
        self.healthy_ips_label = QLabel("0")
        self.healthy_ips_label.setStyleSheet("color: green; font-weight: bold;")
        ip_summary_layout.addWidget(self.healthy_ips_label)

        ip_summary_layout.addSpacing(15)
        ip_summary_layout.addWidget(QLabel("限流IP:"))
        self.limited_ips_label = QLabel("0")
        self.limited_ips_label.setStyleSheet("color: orange; font-weight: bold;")
        ip_summary_layout.addWidget(self.limited_ips_label)

        ip_summary_layout.addSpacing(15)
        ip_summary_layout.addWidget(QLabel("故障IP:"))
        self.failed_ips_label = QLabel("0")
        self.failed_ips_label.setStyleSheet("color: red; font-weight: bold;")
        ip_summary_layout.addWidget(self.failed_ips_label)

        ip_summary_layout.addSpacing(15)
        ip_summary_layout.addWidget(QLabel("总连接数:"))
        self.total_connections_label = QLabel("0")
        self.total_connections_label.setStyleSheet("color: blue; font-weight: bold;")
        ip_summary_layout.addWidget(self.total_connections_label)

        ip_summary_layout.addStretch()
        layout.addLayout(ip_summary_layout)

        # IP详细统计表
        layout.addWidget(QLabel("IP详细统计:"))
        self.ip_stats_table = QTableWidget()
        self.ip_stats_table.setColumnCount(8)
        self.ip_stats_table.setHorizontalHeaderLabels([
            "IP地址", "端口", "使用次数", "成功数", "失败数", "平均响应(ms)", "成功率", "状态"
        ])
        self.ip_stats_table.setMaximumHeight(200)
        self.ip_stats_table.setAlternatingRowColors(True)
        self.ip_stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        # 设置列宽
        self.ip_stats_table.setColumnWidth(0, 120)  # IP地址
        self.ip_stats_table.setColumnWidth(1, 60)   # 端口
        self.ip_stats_table.setColumnWidth(2, 80)   # 使用次数
        self.ip_stats_table.setColumnWidth(3, 70)   # 成功数
        self.ip_stats_table.setColumnWidth(4, 70)   # 失败数
        self.ip_stats_table.setColumnWidth(5, 100)  # 平均响应
        self.ip_stats_table.setColumnWidth(6, 70)   # 成功率
        self.ip_stats_table.setColumnWidth(7, 80)   # 状态
        layout.addWidget(self.ip_stats_table)

        # 修复：初始化时显示提示信息，避免空白
        self.ip_stats_table.setRowCount(1)
        init_item = QTableWidgetItem("正在加载IP监控数据...")
        init_item.setForeground(QColor(128, 128, 128))  # 灰色
        self.ip_stats_table.setItem(0, 0, init_item)
        self.ip_stats_table.setSpan(0, 0, 1, 8)

    def update_ip_stats(self, ip_stats: Dict[str, Any]):
        """
        更新IP使用统计信息

        Args:
            ip_stats: {
                'total_connections': int,
                'active_servers': int,
                'healthy_ips': int,
                'limited_ips': int,
                'failed_ips': int,
                'ip_stats': List[Dict]  # IP详细统计列表
                'error_message': str  # 错误信息（可选）
            }
        """
        try:
            if not ip_stats:
                logger.debug("IP监控: 接收到的ip_stats为空")
                ip_stats = {
                    'total_connections': 0,
                    'active_servers': 0,
                    'healthy_ips': 0,
                    'limited_ips': 0,
                    'failed_ips': 0,
                    'ip_stats': [],
                    'error_message': '数据为空'
                }

            # 检查是否有错误信息
            error_message = ip_stats.get('error_message', '')
            if error_message:
                logger.debug(f"IP监控: {error_message}")

            # 更新摘要信息
            if hasattr(self, 'healthy_ips_label'):
                healthy_ips = ip_stats.get('healthy_ips', 0)
                self.healthy_ips_label.setText(str(healthy_ips))
                # 如果没有健康IP且有错误信息，显示警告颜色
                if healthy_ips == 0 and error_message:
                    self.healthy_ips_label.setStyleSheet("color: orange; font-weight: bold;")

            if hasattr(self, 'limited_ips_label'):
                self.limited_ips_label.setText(str(ip_stats.get('limited_ips', 0)))

            if hasattr(self, 'failed_ips_label'):
                self.failed_ips_label.setText(str(ip_stats.get('failed_ips', 0)))

            if hasattr(self, 'total_connections_label'):
                total_connections = ip_stats.get('total_connections', 0)
                self.total_connections_label.setText(str(total_connections))
                # 如果没有连接且有错误信息，显示警告颜色
                if total_connections == 0 and error_message:
                    self.total_connections_label.setStyleSheet("color: orange; font-weight: bold;")

            # 更新IP详细统计表
            if hasattr(self, 'ip_stats_table'):
                ip_stats_list = ip_stats.get('ip_stats', [])

                # 如果没有IP统计且有错误信息，显示错误提示
                if not ip_stats_list and error_message:
                    self.ip_stats_table.setRowCount(1)
                    error_item = QTableWidgetItem(f"⚠ {error_message}")
                    error_item.setForeground(QColor(255, 165, 0))  # 橙色
                    self.ip_stats_table.setItem(0, 0, error_item)
                    # 合并单元格显示错误信息
                    self.ip_stats_table.setSpan(0, 0, 1, 8)
                    return

                self.ip_stats_table.setRowCount(len(ip_stats_list) if ip_stats_list else 0)

                # 如果没有数据，显示提示信息
                if not ip_stats_list:
                    self.ip_stats_table.setRowCount(1)
                    no_data_item = QTableWidgetItem("暂无IP统计数据（连接池可能未初始化或未使用）")
                    no_data_item.setForeground(QColor(128, 128, 128))  # 灰色
                    self.ip_stats_table.setItem(0, 0, no_data_item)
                    self.ip_stats_table.setSpan(0, 0, 1, 8)
                    return

                for row, ip_stat in enumerate(ip_stats_list):
                    if not isinstance(ip_stat, dict):
                        logger.debug(f"IP监控: 跳过非字典类型的ip_stat: {type(ip_stat)}")
                        continue

                    # 修复：确保所有字段都有有效值，避免显示空白
                    # IP地址
                    ip = ip_stat.get('ip', '') or ''
                    self.ip_stats_table.setItem(row, 0, QTableWidgetItem(str(ip)))

                    # 端口
                    port = ip_stat.get('port', '') or ''
                    self.ip_stats_table.setItem(row, 1, QTableWidgetItem(str(port)))

                    # 使用次数
                    use_count = ip_stat.get('use_count', 0) or 0
                    self.ip_stats_table.setItem(row, 2, QTableWidgetItem(str(use_count)))

                    # 成功数
                    success_count = ip_stat.get('success_count', 0) or 0
                    self.ip_stats_table.setItem(row, 3, QTableWidgetItem(str(success_count)))

                    # 失败数
                    failure_count = ip_stat.get('failure_count', 0) or 0
                    self.ip_stats_table.setItem(row, 4, QTableWidgetItem(str(failure_count)))

                    # 平均响应时间（毫秒）
                    avg_response = ip_stat.get('avg_response_time', 0.0) or 0.0
                    avg_response_ms = f"{avg_response * 1000:.1f}" if avg_response > 0 else "0.0"
                    self.ip_stats_table.setItem(row, 5, QTableWidgetItem(avg_response_ms))

                    # 成功率
                    success_rate = ip_stat.get('success_rate', 0.0) or 0.0
                    success_rate_str = f"{success_rate * 100:.1f}%" if success_rate > 0 else "0.0%"
                    self.ip_stats_table.setItem(row, 6, QTableWidgetItem(success_rate_str))

                    # 状态
                    status = ip_stat.get('status', 'healthy') or 'healthy'
                    status_item = QTableWidgetItem(status)
                    if status == 'healthy':
                        status_item.setForeground(QColor(0, 128, 0))  # 绿色
                    elif status == 'limited':
                        status_item.setForeground(QColor(255, 165, 0))  # 橙色
                    elif status == 'failed':
                        status_item.setForeground(QColor(255, 0, 0))  # 红色
                    else:
                        status_item.setForeground(QColor(128, 128, 128))  # 灰色
                    self.ip_stats_table.setItem(row, 7, status_item)

                    # 修复：如果IP有值但其他字段都为空，记录警告日志
                    if ip and not port and use_count == 0:
                        logger.debug(f"IP监控: 检测到不完整的数据行 (IP={ip}, port={port}, use_count={use_count})")

        except Exception as e:
            logger.error(f"更新IP统计失败: {e}", exc_info=True) if logger else None
            # 显示错误信息到表格
            if hasattr(self, 'ip_stats_table'):
                try:
                    self.ip_stats_table.setRowCount(1)
                    error_item = QTableWidgetItem(f"❌ 更新失败: {str(e)}")
                    error_item.setForeground(QColor(255, 0, 0))  # 红色
                    self.ip_stats_table.setItem(0, 0, error_item)
                    self.ip_stats_table.setSpan(0, 0, 1, 8)
                except Exception:
                    pass


class RealtimeWriteMonitoringWidget(QWidget):
    """实时写入监控面板"""

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.write_data = {
            'progress': 0,
            'speed': 0,
            'success': 0,
            'failure': 0,
            'memory_usage': 0,
            'errors': []
        }
        self.instance_pool_stats = None
        # 修复：用于计算写入速度的数据（基于total_writes）
        self._write_speed_calc_data = {
            'last_time': None,
            'last_total_writes': 0,
            'last_speed': 0
        }

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()

        # 任务信息
        task_layout = QHBoxLayout()
        task_layout.addWidget(QLabel("当前任务:"))
        self.task_label = QLabel("无")
        self.task_label.setStyleSheet("color: gray; font-weight: bold;")
        task_layout.addWidget(self.task_label)
        task_layout.addStretch()
        layout.addLayout(task_layout)

        # 进度显示
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("下载进度:"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        # 🔧 设置进度条显示文本，不再使用外部标签
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 4px;
                text-align: center;
                background-color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        progress_layout.addWidget(self.progress_bar, stretch=1)
        layout.addLayout(progress_layout)

        # 状态消息
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("状态:"))
        self.status_label = QLabel("等待下载...")
        self.status_label.setStyleSheet("color: gray;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        # 统计信息行
        stats_layout = QHBoxLayout()

        # 下载速度
        stats_layout.addWidget(QLabel("下载速度:"))
        self.speed_label = QLabel("0 条/秒")
        self.speed_label.setStyleSheet("color: blue;")
        stats_layout.addWidget(self.speed_label)

        stats_layout.addSpacing(20)

        # 成功计数
        stats_layout.addWidget(QLabel("成功:"))
        self.success_label = QLabel("0")
        self.success_label.setStyleSheet("color: green;")
        stats_layout.addWidget(self.success_label)

        stats_layout.addSpacing(20)

        # 失败计数
        stats_layout.addWidget(QLabel("失败:"))
        self.failure_label = QLabel("0")
        self.failure_label.setStyleSheet("color: red;")
        stats_layout.addWidget(self.failure_label)

        stats_layout.addSpacing(20)

        # 内存使用
        stats_layout.addWidget(QLabel("内存:"))
        self.memory_label = QLabel("0 MB")
        self.memory_label.setStyleSheet("color: purple;")
        stats_layout.addWidget(self.memory_label)

        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # 数据库写入队列信息（新增）
        queue_layout = QHBoxLayout()

        # 队列深度
        queue_layout.addWidget(QLabel("写入队列:"))
        self.queue_size_label = QLabel("0")
        self.queue_size_label.setStyleSheet("color: navy;")
        queue_layout.addWidget(self.queue_size_label)

        queue_layout.addSpacing(20)

        # 合并缓冲区
        queue_layout.addWidget(QLabel("合并缓冲:"))
        self.merge_buffer_label = QLabel("0")
        self.merge_buffer_label.setStyleSheet("color: teal;")
        queue_layout.addWidget(self.merge_buffer_label)

        queue_layout.addSpacing(20)

        # 已写入数
        queue_layout.addWidget(QLabel("已写入:"))
        self.total_writes_label = QLabel("0")
        self.total_writes_label.setStyleSheet("color: darkgreen;")
        queue_layout.addWidget(self.total_writes_label)

        queue_layout.addStretch()
        layout.addLayout(queue_layout)

        # 错误日志表
        error_log_header_layout = QHBoxLayout()
        error_log_header_layout.addWidget(QLabel("错误日志:"))
        error_log_header_layout.addStretch()
        # 新增：全量重新下载按钮
        self.redownload_all_btn = QPushButton("全量重新下载")
        self.redownload_all_btn.setToolTip("重新下载所有记录错误的资产")
        self.redownload_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.redownload_all_btn.clicked.connect(self._on_redownload_all_clicked)
        error_log_header_layout.addWidget(self.redownload_all_btn)
        layout.addLayout(error_log_header_layout)

        self.error_table = QTableWidget()
        self.error_table.setColumnCount(4)
        self.error_table.setHorizontalHeaderLabels(["时间", "符号", "错误类型", "错误信息"])
        self.error_table.setMaximumHeight(180)
        layout.addWidget(self.error_table, stretch=50)

        # 新增：存储父组件引用和当前任务配置（用于重新下载）
        self.parent_widget = None  # 父组件（EnhancedDataImportWidget）
        self.current_task_config = None  # 当前任务配置

        # 初始状态：按钮禁用（没有错误时）
        self.redownload_all_btn.setEnabled(False)

        # 数据源实例池状态（新增，简要概览）
        pool_layout = QHBoxLayout()
        pool_layout.addWidget(QLabel("实例池:"))
        self.pool_status_label = QLabel("0/0")
        self.pool_status_label.setStyleSheet("color: #444;")
        pool_layout.addWidget(self.pool_status_label)
        pool_layout.addStretch()
        layout.addLayout(pool_layout)

        # 实例池配置（UI控制）
        config_row = QHBoxLayout()
        config_row.addWidget(QLabel("最大实例:"))
        self.pool_size_spin = QSpinBox()
        self.pool_size_spin.setRange(1, 200)
        self.pool_size_spin.setValue(5)
        config_row.addWidget(self.pool_size_spin)

        config_row.addSpacing(15)
        config_row.addWidget(QLabel("超时(s):"))
        self.pool_timeout_spin = QSpinBox()
        self.pool_timeout_spin.setRange(5, 600)
        self.pool_timeout_spin.setValue(30)
        config_row.addWidget(self.pool_timeout_spin)

        config_row.addSpacing(15)
        config_row.addWidget(QLabel("清理间隔(s):"))
        self.pool_cleanup_spin = QSpinBox()
        self.pool_cleanup_spin.setRange(30, 3600)
        self.pool_cleanup_spin.setValue(300)
        config_row.addWidget(self.pool_cleanup_spin)

        self.apply_pool_btn = QPushButton("应用实例池配置")
        self.apply_pool_btn.clicked.connect(self._apply_instance_pool_config)
        config_row.addWidget(self.apply_pool_btn)
        layout.addLayout(config_row)

        # 新增：数据库连接池配置（DuckDB连接池）
        db_pool_group = QHBoxLayout()
        db_pool_group.addWidget(QLabel("数据库连接池:"))

        # 连接池大小配置
        self.db_pool_size_spin = QSpinBox()
        self.db_pool_size_spin.setRange(5, 100)
        self.db_pool_size_spin.setValue(10)  # 默认值10
        self.db_pool_size_spin.setToolTip("DuckDB数据库连接池大小（用于元数据保存等数据库操作）")
        db_pool_group.addWidget(self.db_pool_size_spin)

        # 新增：连接池使用统计显示
        db_pool_group.addWidget(QLabel("使用:"))
        self.db_pool_usage_label = QLabel("0/10")
        self.db_pool_usage_label.setStyleSheet("color: #444;")
        self.db_pool_usage_label.setToolTip("活跃连接数/连接池大小")
        db_pool_group.addWidget(self.db_pool_usage_label)

        self.apply_db_pool_btn = QPushButton("应用数据库连接池")
        self.apply_db_pool_btn.clicked.connect(self._apply_database_pool_config)
        db_pool_group.addWidget(self.apply_db_pool_btn)
        layout.addLayout(db_pool_group)

        layout.addStretch()
        self.setLayout(layout)

    def update_write_stats(self, stats: Dict[str, Any]):
        """更新写入统计"""
        self.write_data.update(stats)
        self.update_display()

    def add_error(self, timestamp: str, symbol: str, error_type: str, error_msg: str):
        """添加错误记录"""
        # 修复：先检查是否已存在该symbol的错误记录，如果存在则更新，否则添加新记录
        existing_row = self._find_error_row_by_symbol(symbol)

        if existing_row is not None:
            # 更新现有错误记录
            self.error_table.setItem(existing_row, 0, QTableWidgetItem(timestamp))
            self.error_table.setItem(existing_row, 1, QTableWidgetItem(symbol))
            self.error_table.setItem(existing_row, 2, QTableWidgetItem(error_type))
            self.error_table.setItem(existing_row, 3, QTableWidgetItem(error_msg))
            logger.debug(f"[错误日志] 已更新符号错误记录: {symbol} - {error_msg}")
        else:
            # 添加新错误记录
            row = self.error_table.rowCount()
            self.error_table.insertRow(row)

            self.error_table.setItem(row, 0, QTableWidgetItem(timestamp))
            self.error_table.setItem(row, 1, QTableWidgetItem(symbol))
            self.error_table.setItem(row, 2, QTableWidgetItem(error_type))
            self.error_table.setItem(row, 3, QTableWidgetItem(error_msg))
            logger.debug(f"[错误日志] 已添加符号错误记录: {symbol} - {error_msg}")

        # 移除100条限制，允许记录所有错误（用于重新下载功能）
        # 原代码：while self.error_table.rowCount() > 100: self.error_table.removeRow(0)

        # 更新按钮状态：如果有错误记录，启用按钮
        if self.error_table.rowCount() > 0:
            self.redownload_all_btn.setEnabled(True)

    def remove_error(self, symbol: str) -> bool:
        """
        移除指定symbol的错误记录（成功导入时调用）

        Args:
            symbol: 资产符号

        Returns:
            bool: 是否成功移除（True=已移除，False=未找到）
        """
        row = self._find_error_row_by_symbol(symbol)
        if row is not None:
            self.error_table.removeRow(row)
            logger.debug(f"[错误日志] 已清除符号错误记录: {symbol}（导入成功）")

            # 更新按钮状态：如果没有错误记录，禁用按钮
            if self.error_table.rowCount() == 0:
                self.redownload_all_btn.setEnabled(False)

            return True
        return False

    def _find_error_row_by_symbol(self, symbol: str) -> Optional[int]:
        """
        查找指定symbol在错误表中的行号

        Args:
            symbol: 资产符号

        Returns:
            Optional[int]: 行号（如果找到），否则返回None
        """
        for row in range(self.error_table.rowCount()):
            symbol_item = self.error_table.item(row, 1)  # 符号列
            if symbol_item and symbol_item.text().strip() == symbol.strip():
                return row
        return None

    def set_parent_widget(self, parent_widget):
        """设置父组件引用（用于访问导入引擎和任务配置）"""
        self.parent_widget = parent_widget

    def set_current_task_config(self, task_config):
        """设置当前任务配置（用于重新下载时使用相同配置）"""
        self.current_task_config = task_config

    def _on_redownload_all_clicked(self):
        """全量重新下载按钮点击事件"""
        try:
            from PyQt5.QtWidgets import QMessageBox

            # 检查是否有错误记录
            error_count = self.error_table.rowCount()
            if error_count == 0:
                QMessageBox.information(self, "提示", "没有错误记录，无需重新下载")
                return

            # 确认对话框
            reply = QMessageBox.question(
                self,
                "确认重新下载",
                f"确定要重新下载所有 {error_count} 个失败的资产吗？\n\n这将创建一个新的导入任务。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            # 从错误日志表中提取所有失败的符号
            failed_symbols = []
            for row in range(self.error_table.rowCount()):
                symbol_item = self.error_table.item(row, 1)  # 符号列
                if symbol_item:
                    symbol = symbol_item.text().strip()
                    if symbol and symbol not in failed_symbols:
                        failed_symbols.append(symbol)

            if not failed_symbols:
                QMessageBox.warning(self, "警告", "未能提取到有效的资产符号")
                return

            # 获取父组件的导入引擎和配置管理器
            if not self.parent_widget:
                QMessageBox.warning(self, "错误", "无法访问导入引擎，请确保任务正在运行")
                return

            import_engine = getattr(self.parent_widget, 'import_engine', None)
            config_manager = getattr(self.parent_widget, 'config_manager', None)

            if not import_engine or not config_manager:
                QMessageBox.warning(self, "错误", "导入引擎或配置管理器未初始化")
                return

            # 获取当前任务配置（如果存在）
            task_config = self.current_task_config

            # 如果没有当前任务配置，尝试从父组件获取
            if not task_config:
                current_task_id = getattr(self.parent_widget, 'current_task_id', None)
                if current_task_id and config_manager:
                    try:
                        all_tasks = config_manager.get_import_tasks()
                        for task in all_tasks:
                            if task.task_id == current_task_id:
                                task_config = task
                                break
                    except Exception as e:
                        logger.warning(f"获取当前任务配置失败: {e}")

            # 如果仍然没有任务配置，使用默认配置
            if not task_config:
                # 尝试从UI获取配置
                if hasattr(self.parent_widget, '_get_current_ui_config'):
                    try:
                        ui_config = self.parent_widget._get_current_ui_config()
                        from core.importdata.import_config_manager import ImportTaskConfig, DataFrequency, ImportMode

                        # 频率映射
                        frequency_str = ui_config.get('frequency', '1d')
                        frequency_map = {
                            '1d': DataFrequency.DAILY,
                            '1w': DataFrequency.WEEKLY,
                            '1m': DataFrequency.MONTHLY,
                            '5m': DataFrequency.MINUTE_5,
                            '15m': DataFrequency.MINUTE_15,
                            '30m': DataFrequency.MINUTE_30,
                            '60m': DataFrequency.HOUR_1,
                            '1min': DataFrequency.MINUTE_1,
                            'daily': DataFrequency.DAILY
                        }
                        frequency_enum = frequency_map.get(frequency_str, DataFrequency.DAILY)

                        task_config = ImportTaskConfig(
                            task_id=f"redownload_{int(datetime.now().timestamp())}",
                            name=f"重新下载失败资产_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                            symbols=failed_symbols,
                            data_source=ui_config.get('data_source', 'data_sources.stock.tongdaxin_plugin'),
                            asset_type=ui_config.get('asset_type', 'stock_a'),
                            data_type=ui_config.get('data_type', 'K线数据'),
                            frequency=frequency_enum,
                            mode=ImportMode.MANUAL,
                            batch_size=ui_config.get('batch_size', 100),
                            max_workers=ui_config.get('max_workers', 4),
                            start_date=ui_config.get('start_date', None),
                            end_date=ui_config.get('end_date', None),
                            retry_count=ui_config.get('retry_count', 3),
                            error_strategy=ui_config.get('error_strategy', '跳过'),
                            memory_limit=ui_config.get('memory_limit', 2048),
                            timeout=ui_config.get('timeout', 60),
                            progress_interval=ui_config.get('progress_interval', 5),
                            validate_data=ui_config.get('validate_data', True)
                        )
                    except Exception as e:
                        logger.error(f"从UI配置创建任务配置失败: {e}")
                        QMessageBox.critical(self, "错误", f"创建任务配置失败: {e}")
                        return
                else:
                    QMessageBox.warning(self, "错误", "无法获取任务配置，请先创建一个导入任务")
                    return
            else:
                # 使用当前任务配置，但替换符号列表
                from core.importdata.import_config_manager import ImportTaskConfig, DataFrequency, ImportMode
                from copy import deepcopy

                # 创建新任务配置（基于当前任务配置）
                new_task_config = ImportTaskConfig(
                    task_id=f"redownload_{int(datetime.now().timestamp())}",
                    name=f"重新下载失败资产_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    symbols=failed_symbols,  # 使用失败的符号列表
                    data_source=task_config.data_source,
                    asset_type=task_config.asset_type,
                    data_type=task_config.data_type,
                    frequency=task_config.frequency,
                    mode=ImportMode.MANUAL,
                    batch_size=task_config.batch_size,
                    max_workers=task_config.max_workers,
                    start_date=task_config.start_date,
                    end_date=task_config.end_date,
                    retry_count=task_config.retry_count,
                    error_strategy=task_config.error_strategy,
                    memory_limit=task_config.memory_limit,
                    timeout=task_config.timeout,
                    progress_interval=task_config.progress_interval,
                    validate_data=task_config.validate_data
                )
                task_config = new_task_config

            # 添加任务到配置管理器并启动
            config_manager.add_import_task(task_config)

            if import_engine.start_task(task_config.task_id):
                QMessageBox.information(
                    self,
                    "成功",
                    f"已创建重新下载任务：{task_config.name}\n\n"
                    f"资产数量：{len(failed_symbols)}\n"
                    f"任务ID：{task_config.task_id}"
                )
                logger.info(f"全量重新下载任务已创建: {task_config.task_id}, 资产数量: {len(failed_symbols)}")

                # 刷新父组件的任务列表
                if hasattr(self.parent_widget, 'refresh_task_list'):
                    self.parent_widget.refresh_task_list()
            else:
                QMessageBox.warning(self, "错误", "启动重新下载任务失败")
                logger.error(f"❌ 启动重新下载任务失败: {task_config.task_id}")

        except Exception as e:
            logger.error(f"全量重新下载失败: {e}", exc_info=True)
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "错误", f"重新下载失败: {str(e)}")

    def update_instance_pool_stats(self, stats: Dict[str, Any]):
        """更新数据源实例池状态"""
        try:
            self.instance_pool_stats = stats or {}
            # 修复：使用total_instances（包括空闲和活跃实例）
            total = self.instance_pool_stats.get('total_instances', 0)
            max_size = self.instance_pool_stats.get('max_pool_size', 0)

            # 显示格式：总实例数/最大池大小 (空闲: X, 活跃: Y)
            total_idle = self.instance_pool_stats.get('total_idle', 0)
            total_active = self.instance_pool_stats.get('total_active', 0)

            if total_idle > 0 or total_active > 0:
                # 有实例时显示详细信息
                display_text = f"{total}/{max_size} (空闲:{total_idle}, 活跃:{total_active})"
            else:
                # 修复：即使为0也显示，并添加提示
                if max_size > 0:
                    display_text = f"{total}/{max_size} (未使用)"
                else:
                    display_text = "0/0 (未配置)"

            self.pool_status_label.setText(display_text)

            # 同步UI默认值（仅在首次或变更时）
            if max_size and self.pool_size_spin.value() != max_size:
                self.pool_size_spin.setValue(max_size)

            # 修复：加载数据库连接池大小配置和使用统计
            try:
                from core.asset_database_manager import AssetSeparatedDatabaseManager
                manager = AssetSeparatedDatabaseManager.get_instance()
                if hasattr(manager, 'config') and hasattr(manager.config, 'pool_size'):
                    db_pool_size = manager.config.pool_size
                    # 修复：如果SpinBox有焦点（用户正在输入），不更新值，避免覆盖用户输入
                    if hasattr(self, 'db_pool_size_spin'):
                        if not self.db_pool_size_spin.hasFocus() and self.db_pool_size_spin.value() != db_pool_size:
                            self.db_pool_size_spin.setValue(db_pool_size)

                    # 新增：更新数据库连接池使用统计
                    if hasattr(manager, 'get_database_pool_status'):
                        db_pool_status = manager.get_database_pool_status()
                        active_connections = db_pool_status.get('active_connections', 0)
                        total_connections = db_pool_status.get('total_connections', 0)
                        max_pool_size = db_pool_status.get('max_pool_size', db_pool_size)

                        # 修复：使用实际创建的连接数（total_connections）而不是最大池大小作为分母
                        # 如果total_connections为0，则使用max_pool_size（连接池还未创建任何连接）
                        denominator = total_connections if total_connections > 0 else max_pool_size
                        if hasattr(self, 'db_pool_usage_label'):
                            usage_text = f"{active_connections}/{denominator}"
                            if total_connections > 0:
                                usage_text += f" (最大:{max_pool_size})"
                            self.db_pool_usage_label.setText(usage_text)
                            # 根据使用率调整颜色
                            if denominator > 0:
                                usage_rate = active_connections / denominator
                                if usage_rate > 0.8:
                                    self.db_pool_usage_label.setStyleSheet("color: red; font-weight: bold;")
                                elif usage_rate > 0.5:
                                    self.db_pool_usage_label.setStyleSheet("color: orange;")
                                else:
                                    self.db_pool_usage_label.setStyleSheet("color: green;")
            except Exception as e:
                logger.debug(f"更新数据库连接池配置失败: {e}")
                pass  # 静默失败
        except Exception as e:
            logger.debug(f"更新实例池状态失败: {e}")
            pass

    def _apply_instance_pool_config(self):
        """将UI配置应用到RealDataProvider"""
        try:
            from core.real_data_provider import get_real_data_provider
            provider = get_real_data_provider()
            provider.set_pool_config(
                max_pool_size=self.pool_size_spin.value(),
                pool_timeout=self.pool_timeout_spin.value(),
                pool_cleanup_interval=self.pool_cleanup_spin.value()
            )
            # 立即刷新显示
            stats = provider.get_pool_status()
            self.update_instance_pool_stats(stats)
        except Exception as e:
            # 静默处理，避免中断UI
            if hasattr(self, 'pool_status_label'):
                self.pool_status_label.setText("应用失败")

    def _apply_database_pool_config(self):
        """将数据库连接池配置应用到AssetSeparatedDatabaseManager"""
        try:
            from core.asset_database_manager import AssetSeparatedDatabaseManager
            from loguru import logger

            # 获取管理器实例
            manager = AssetSeparatedDatabaseManager.get_instance()

            # 更新连接池大小
            new_pool_size = self.db_pool_size_spin.value()
            success = manager.update_pool_size(new_pool_size)

            if success:
                logger.info(f"数据库连接池大小已更新为: {new_pool_size}")

                # 显示提示 (HVD-E: update_pool_size 已改为运行时重建全部连接池,
                # 不再需要重启生效; 重建为 EAGER 建池, 界面可能短暂无响应)
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.information(
                    None,
                    "配置已更新",
                    f"数据库连接池大小已设置为: {new_pool_size}\n\n"
                    f"已立即生效（重建连接池期间界面可能短暂无响应）。"
                )
            else:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(None, "配置失败", f"连接池大小超出范围 (5-100)")
        except Exception as e:
            from loguru import logger
            logger.error(f"应用数据库连接池配置失败: {e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(None, "配置失败", f"应用数据库连接池配置失败: {str(e)}")

    def update_progress(self, progress_data: Dict[str, Any]):
        """
        更新下载进度

        Args:
            progress_data: {
                'progress': float,  # 进度 0.0-1.0
                'message': str,
                'task_id': str,
                'task_name': str
            }
        """
        try:
            # 更新任务ID
            task_id = progress_data.get('task_id', '')
            task_name = progress_data.get('task_name', '')
            if task_id and hasattr(self, 'task_label'):
                self.task_label.setText(task_name+' - '+task_id)
                self.task_label.setStyleSheet("color: blue; font-weight: bold;")

            # 更新进度
            progress = progress_data.get('progress', 0)
            progress_percent = int(progress * 100)
            if hasattr(self, 'progress_bar'):
                self.progress_bar.setValue(progress_percent)
            if hasattr(self, 'progress_text_label'):
                self.progress_text_label.setText(f"{progress_percent}%")

            # 更新消息
            message = progress_data.get('message', '')
            if message and hasattr(self, 'status_label'):
                self.status_label.setText(message)

            # 修复：不再在update_progress中更新速度
            # 速度计算已移至update_queue_stats中，基于total_writes计算写入速度
            # 这里只更新进度和状态，速度由update_queue_stats统一管理
            self.write_data['progress'] = progress_percent

            logger.debug(f"K线下载监控更新: {progress_percent}% - {message}")

        except Exception as e:
            logger.error(f"更新下载进度失败: {e}")

    def update_display(self):
        """更新显示"""
        self.progress_bar.setValue(int(self.write_data.get('progress', 0)))

        speed = self.write_data.get('speed', 0)
        self.speed_label.setText(f"{speed:.0f} 条/秒")

        success = self.write_data.get('success', 0)
        self.success_label.setText(str(success))

        failure = self.write_data.get('failure', 0)
        if failure > 0:
            self.failure_label.setStyleSheet("color: red; font-weight: bold;")
        self.failure_label.setText(str(failure))

        memory = self.write_data.get('memory_usage', 0)
        self.memory_label.setText(f"{memory:.1f} MB")

    def update_queue_stats(self, queue_stats: Dict[str, Any]):
        """
        更新数据库写入队列统计信息（新增方法）

        Args:
            queue_stats: {
                'queue_size': int,           # 队列当前大小
                'queue_peak': int,           # 队列峰值
                'total_writes': int,         # 总写入任务次数
                'failed_writes': int,        # 失败写入任务次数
                'total_records': int,        # 成功落库记录总数（真实记录数）
                'failed_records': int,       # 落库失败记录总数
                'merge_buffer_size': int,    # 合并缓冲区大小
                'is_stopped': bool           # 是否已停止
            }
        """
        try:
            # 更新队列深度
            queue_size = queue_stats.get('queue_size', 0)
            queue_peak = queue_stats.get('queue_peak', 0)
            if hasattr(self, 'queue_size_label'):
                self.queue_size_label.setText(f"{queue_size} (峰值:{queue_peak})")
                # 根据队列大小调整颜色
                if queue_size > 500:
                    self.queue_size_label.setStyleSheet("color: red; font-weight: bold;")
                elif queue_size > 200:
                    self.queue_size_label.setStyleSheet("color: orange; font-weight: bold;")
                else:
                    self.queue_size_label.setStyleSheet("color: navy;")

            # 更新合并缓冲区
            merge_buffer_size = queue_stats.get('merge_buffer_size', 0)
            if hasattr(self, 'merge_buffer_label'):
                self.merge_buffer_label.setText(str(merge_buffer_size))

            # 更新已写入记录数（修复：使用真实落库记录数，而非写入任务次数）
            total_writes = queue_stats.get('total_writes', 0)
            failed_writes = queue_stats.get('failed_writes', 0)
            # 优先使用真实记录数（新统计字段），兼容旧统计只有任务次数的情况
            total_records = queue_stats.get('total_records', total_writes)
            failed_records = queue_stats.get('failed_records', failed_writes)
            if hasattr(self, 'total_writes_label'):
                if failed_records > 0:
                    self.total_writes_label.setText(f"{total_records} (失败:{failed_records})")
                    self.total_writes_label.setStyleSheet("color: red; font-weight: bold;")
                else:
                    self.total_writes_label.setText(str(total_records))
                    self.total_writes_label.setStyleSheet("color: darkgreen;")

            # 修复：基于真实落库记录数(total_records)计算写入速度（条/秒），
            # 原先基于total_writes（写入任务次数），任务大多仅进入合并缓冲未落库，
            # 导致速度恒为0且单位与"条/秒"不一致
            import time
            current_time = time.time()

            # 初始化速度计算数据
            if self._write_speed_calc_data['last_time'] is None:
                self._write_speed_calc_data['last_time'] = current_time
                self._write_speed_calc_data['last_total_writes'] = total_records
                self._write_speed_calc_data['last_speed'] = 0
            else:
                # 计算时间差
                time_delta = current_time - self._write_speed_calc_data['last_time']
                if time_delta > 0.1:  # 至少0.1秒才更新速度，避免抖动
                    # 计算记录数增量
                    writes_delta = total_records - self._write_speed_calc_data['last_total_writes']
                    if writes_delta > 0:
                        # 计算速度（条/秒）
                        speed = writes_delta / time_delta
                        # 使用指数移动平均平滑速度
                        alpha = 0.3  # 平滑因子
                        self._write_speed_calc_data['last_speed'] = (
                            alpha * speed + (1 - alpha) * self._write_speed_calc_data['last_speed']
                        )
                    else:
                        # 如果没有新写入，速度逐渐衰减
                        self._write_speed_calc_data['last_speed'] *= 0.9

                    # 更新记录
                    self._write_speed_calc_data['last_time'] = current_time
                    self._write_speed_calc_data['last_total_writes'] = total_records

                # 更新速度显示（使用真实落库速度，单位统一为条/秒）
                if hasattr(self, 'speed_label'):
                    write_speed = self._write_speed_calc_data['last_speed']
                    speed_text = f"{write_speed:.1f} 条/秒"
                    self.speed_label.setText(speed_text)
                    # 根据速度调整颜色
                    if write_speed > 10:
                        self.speed_label.setStyleSheet("color: green; font-weight: bold;")
                    elif write_speed > 5:
                        self.speed_label.setStyleSheet("color: blue;")
                    else:
                        self.speed_label.setStyleSheet("color: orange;")

                    # 同步到内部数据
                    self.write_data['speed'] = write_speed

        except Exception as e:
            logger.error(f"更新队列统计失败: {e}")

    def start_monitoring(self):
        """启动监控"""
        self.update_timer.start(500)  # 每500ms更新一次
        logger.info("实时写入监控已启动")

    def stop_monitoring(self):
        """停止监控"""
        self.update_timer.stop()
        logger.info("实时写入监控已停止")

    def reset(self):
        """重置监控数据"""
        self.progress_bar.setValue(0)
        self.speed_label.setText("0 条/秒")
        self.success_label.setText("0")
        self.failure_label.setText("0")
        self.memory_label.setText("0 MB")
        self.error_table.setRowCount(0)
        # 清空错误日志后，禁用重新下载按钮
        self.redownload_all_btn.setEnabled(False)
        self.write_data.clear()
        # 修复：重置速度计算状态，避免跨任务的速度/计数残留
        self._write_speed_calc_data = {
            'last_time': None,
            'last_total_writes': 0,
            'last_speed': 0
        }
