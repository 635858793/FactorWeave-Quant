#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DuckDB配置管理对话框

提供图形界面管理DuckDB性能配置
"""

from core.database.duckdb_performance_optimizer import (
    DuckDBPerformanceOptimizer, WorkloadType
)
from db.models.duckdb_config_models import (
    DuckDBConfigManager, DuckDBConfigProfile, get_duckdb_config_manager
)
import sys
import json
from loguru import logger
from typing import Dict, List, Any, Optional
from pathlib import Path

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
    QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QGroupBox,
    QMessageBox, QProgressBar, QSplitter, QFrame, QScrollArea,
    QHeaderView, QAbstractItemView, QMenu, QAction
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPalette, QColor

from .base_dialog import BaseDialog

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logger

class DuckDBConfigTestThread(QThread):
    """DuckDB配置测试线程"""

    progress_updated = pyqtSignal(int, str)
    test_completed = pyqtSignal(dict)
    test_failed = pyqtSignal(str)

    def __init__(self, profile: DuckDBConfigProfile):
        super().__init__()
        self.profile = profile
        self.test_db_path = 'data/test_config_ui.duckdb'

    def run(self):
        """运行配置测试"""
        try:
            self.progress_updated.emit(10, "初始化测试环境...")

            # 创建临时优化器
            optimizer = DuckDBPerformanceOptimizer(self.test_db_path)

            self.progress_updated.emit(30, "应用配置参数...")

            # 应用配置
            from core.database.duckdb_performance_optimizer import WorkloadType
            workload_type = getattr(WorkloadType, self.profile.workload_type, WorkloadType.OLAP)
            success = optimizer.optimize_for_workload(workload_type)

            if not success:
                self.test_failed.emit("配置应用失败")
                return

            self.progress_updated.emit(50, "执行性能测试...")

            # 执行基准测试
            test_queries = [
                "SELECT 1 as test",
                "SELECT COUNT(*) FROM (SELECT 1 as x FROM generate_series(1, 10000))",
                "SELECT x, x*2 FROM generate_series(1, 1000) as t(x) ORDER BY x DESC LIMIT 100",
                "SELECT x%100 as grp, COUNT(*), AVG(x) FROM generate_series(1, 50000) as t(x) GROUP BY grp ORDER BY grp LIMIT 50"
            ]

            benchmark_result = optimizer.benchmark_configuration(test_queries)

            self.progress_updated.emit(80, "收集系统信息...")

            # 获取系统信息
            import psutil
            system_info = {
                'memory_gb': psutil.virtual_memory().total / (1024**3),
                'cpu_cores': psutil.cpu_count(logical=True),
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent
            }

            self.progress_updated.emit(100, "测试完成")

            # 整合测试结果
            test_result = {
                'profile_id': self.profile.id,
                'test_name': f"UI配置测试 - {self.profile.profile_name}",
                'test_type': 'ui_test',
                'benchmark_result': benchmark_result,
                'system_info': system_info,
                'profile_config': self.profile.to_dict()
            }

            if 'summary' in benchmark_result:
                summary = benchmark_result['summary']
                test_result.update({
                    'success_rate': summary.get('success_rate', 0),
                    'average_query_time': summary.get('average_time', 0),
                    'total_test_time': summary.get('total_time', 0),
                    'test_queries_count': summary.get('total_queries', 0),
                    'successful_queries': summary.get('successful_queries', 0),
                    'failed_queries': summary.get('total_queries', 0) - summary.get('successful_queries', 0)
                })

            test_result.update({
                'system_memory_gb': system_info['memory_gb'],
                'system_cpu_cores': system_info['cpu_cores'],
                'cpu_usage_percent': system_info['cpu_percent'],
                'memory_usage_mb': 0,  # 简化处理
                'test_data_size': 50000
            })

            # 清理
            optimizer.close()

            self.test_completed.emit(test_result)

        except Exception as e:
            logger.error(f"配置测试失败: {e}")
            self.test_failed.emit(str(e))

class DuckDBConfigDialog(BaseDialog):
    """DuckDB配置管理对话框"""

    def __init__(self, parent=None):
        self.config_manager = get_duckdb_config_manager()
        self.current_profile = None
        self.test_thread = None

        super().__init__(
            parent,
            title="DuckDB性能配置管理",
            min_size=(1000, 700),
            size=(1200, 800),
            settings_key="DuckDBConfigDialog"
        )

        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
                alternate-background-color: #f9f9f9;
            }
            QTableWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
        """)

        self.init_ui()
        self.load_profiles()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧：配置列表
        left_widget = self.create_profile_list_widget()
        splitter.addWidget(left_widget)

        # 右侧：配置详情
        right_widget = self.create_config_detail_widget()
        splitter.addWidget(right_widget)

        # 设置分割比例
        splitter.setSizes([300, 700])

        # 底部按钮
        button_layout = QHBoxLayout()

        self.test_btn = QPushButton("测试配置")
        self.test_btn.clicked.connect(self.test_current_config)
        button_layout.addWidget(self.test_btn)

        self.apply_btn = QPushButton("应用配置")
        self.apply_btn.clicked.connect(self.apply_current_config)
        button_layout.addWidget(self.apply_btn)

        button_layout.addStretch()

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

        # 进度条（初始隐藏）
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel()
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)

    def create_profile_list_widget(self):
        """创建配置列表组件"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 标题
        title_label = QLabel("配置配置文件")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title_label)

        # 配置列表
        self.profile_table = QTableWidget()
        self.profile_table.setColumnCount(4)
        self.profile_table.setHorizontalHeaderLabels(["名称", "类型", "状态", "描述"])

        # 设置表格属性
        self.profile_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.profile_table.setAlternatingRowColors(True)
        self.profile_table.horizontalHeader().setStretchLastSection(True)
        self.profile_table.verticalHeader().setVisible(False)

        # 连接选择事件
        self.profile_table.itemSelectionChanged.connect(self.on_profile_selected)

        # 右键菜单
        self.profile_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.profile_table.customContextMenuRequested.connect(self.show_profile_context_menu)

        layout.addWidget(self.profile_table)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.new_profile_btn = QPushButton("新建")
        self.new_profile_btn.clicked.connect(self.create_new_profile)
        button_layout.addWidget(self.new_profile_btn)

        self.clone_profile_btn = QPushButton("克隆")
        self.clone_profile_btn.clicked.connect(self.clone_current_profile)
        button_layout.addWidget(self.clone_profile_btn)

        self.delete_profile_btn = QPushButton("删除")
        self.delete_profile_btn.clicked.connect(self.delete_current_profile)
        button_layout.addWidget(self.delete_profile_btn)

        layout.addLayout(button_layout)

        return widget

    def create_config_detail_widget(self):
        """创建配置详情组件"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 标题和基本信息
        header_layout = QHBoxLayout()

        self.profile_name_label = QLabel("未选择配置")
        self.profile_name_label.setFont(QFont("Arial", 14, QFont.Bold))
        header_layout.addWidget(self.profile_name_label)

        header_layout.addStretch()

        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_current_profile)
        self.save_btn.setEnabled(False)
        header_layout.addWidget(self.save_btn)

        layout.addLayout(header_layout)

        # 配置选项卡
        self.config_tabs = QTabWidget()

        # 基本信息选项卡
        self.config_tabs.addTab(self.create_basic_info_tab(), "基本信息")

        # 内存配置选项卡
        self.config_tabs.addTab(self.create_memory_config_tab(), "内存配置")

        # 线程配置选项卡
        self.config_tabs.addTab(self.create_thread_config_tab(), "线程配置")

        # 存储配置选项卡
        self.config_tabs.addTab(self.create_storage_config_tab(), "存储配置")

        # 查询配置选项卡
        self.config_tabs.addTab(self.create_query_config_tab(), "查询配置")

        # 高级配置选项卡
        self.config_tabs.addTab(self.create_advanced_config_tab(), "高级配置")

        # 测试结果选项卡
        self.config_tabs.addTab(self.create_test_results_tab(), "测试结果")

        layout.addWidget(self.config_tabs)

        return widget

    def create_basic_info_tab(self):
        """创建基本信息选项卡"""
        widget = QScrollArea()
        content = QFrame()
        layout = QGridLayout(content)

        # 配置名称
        layout.addWidget(QLabel("配置名称:"), 0, 0)
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self.on_config_changed)
        layout.addWidget(self.name_edit, 0, 1)

        # 描述
        layout.addWidget(QLabel("描述:"), 1, 0)
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.textChanged.connect(self.on_config_changed)
        layout.addWidget(self.description_edit, 1, 1)

        # 工作负载类型
        layout.addWidget(QLabel("工作负载类型:"), 2, 0)
        self.workload_combo = QComboBox()
        self.workload_combo.addItems(["OLAP", "OLTP", "MIXED"])
        self.workload_combo.currentTextChanged.connect(self.on_config_changed)
        layout.addWidget(self.workload_combo, 2, 1)

        # 状态
        layout.addWidget(QLabel("状态:"), 3, 0)
        status_layout = QHBoxLayout()

        self.is_active_cb = QCheckBox("活动配置")
        self.is_active_cb.stateChanged.connect(self.on_config_changed)
        status_layout.addWidget(self.is_active_cb)

        self.is_default_cb = QCheckBox("默认配置")
        self.is_default_cb.stateChanged.connect(self.on_config_changed)
        status_layout.addWidget(self.is_default_cb)

        status_layout.addStretch()
        layout.addLayout(status_layout, 3, 1)

        # 创建者和时间信息
        layout.addWidget(QLabel("创建者:"), 4, 0)
        self.created_by_label = QLabel("-")
        layout.addWidget(self.created_by_label, 4, 1)

        layout.addWidget(QLabel("创建时间:"), 5, 0)
        self.created_at_label = QLabel("-")
        layout.addWidget(self.created_at_label, 5, 1)

        layout.addWidget(QLabel("更新时间:"), 6, 0)
        self.updated_at_label = QLabel("-")
        layout.addWidget(self.updated_at_label, 6, 1)

        layout.setRowStretch(7, 1)

        widget.setWidget(content)
        widget.setWidgetResizable(True)
        return widget

    def create_memory_config_tab(self):
        """创建内存配置选项卡"""
        widget = QScrollArea()
        content = QFrame()
        layout = QGridLayout(content)

        # 内存限制
        layout.addWidget(QLabel("内存限制:"), 0, 0)
        self.memory_limit_edit = QLineEdit()
        self.memory_limit_edit.setPlaceholderText("例如: 4.0GB")
        self.memory_limit_edit.textChanged.connect(self.on_config_changed)
        layout.addWidget(self.memory_limit_edit, 0, 1)

        # 最大内存
        layout.addWidget(QLabel("最大内存:"), 1, 0)
        self.max_memory_edit = QLineEdit()
        self.max_memory_edit.setPlaceholderText("例如: 4.4GB")
        self.max_memory_edit.textChanged.connect(self.on_config_changed)
        layout.addWidget(self.max_memory_edit, 1, 1)

        # 缓冲池大小
        layout.addWidget(QLabel("缓冲池大小:"), 2, 0)
        self.buffer_pool_size_edit = QLineEdit()
        self.buffer_pool_size_edit.setPlaceholderText("例如: 1GB")
        self.buffer_pool_size_edit.textChanged.connect(self.on_config_changed)
        layout.addWidget(self.buffer_pool_size_edit, 2, 1)

        # 临时内存限制
        layout.addWidget(QLabel("临时内存限制:"), 3, 0)
        self.temp_memory_limit_edit = QLineEdit()
        self.temp_memory_limit_edit.setPlaceholderText("例如: 2GB")
        self.temp_memory_limit_edit.textChanged.connect(self.on_config_changed)
        layout.addWidget(self.temp_memory_limit_edit, 3, 1)

        layout.setRowStretch(4, 1)

        widget.setWidget(content)
        widget.setWidgetResizable(True)
        return widget

    def create_thread_config_tab(self):
        """创建线程配置选项卡"""
        widget = QScrollArea()
        content = QFrame()
        layout = QGridLayout(content)

        # 线程数
        layout.addWidget(QLabel("线程数:"), 0, 0)
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 64)
        self.threads_spin.valueChanged.connect(self.on_config_changed)
        layout.addWidget(self.threads_spin, 0, 1)

        # I/O线程数
        layout.addWidget(QLabel("I/O线程数:"), 1, 0)
        self.io_threads_spin = QSpinBox()
        self.io_threads_spin.setRange(1, 16)
        self.io_threads_spin.valueChanged.connect(self.on_config_changed)
        layout.addWidget(self.io_threads_spin, 1, 1)

        # 并行任务数
        layout.addWidget(QLabel("并行任务数:"), 2, 0)
        self.parallel_tasks_spin = QSpinBox()
        self.parallel_tasks_spin.setRange(1, 32)
        self.parallel_tasks_spin.valueChanged.connect(self.on_config_changed)
        layout.addWidget(self.parallel_tasks_spin, 2, 1)

        # 工作线程数
        layout.addWidget(QLabel("工作线程数:"), 3, 0)
        self.worker_threads_spin = QSpinBox()
        self.worker_threads_spin.setRange(1, 32)
        self.worker_threads_spin.valueChanged.connect(self.on_config_changed)
        layout.addWidget(self.worker_threads_spin, 3, 1)

        layout.setRowStretch(4, 1)

        widget.setWidget(content)
        widget.setWidgetResizable(True)
        return widget

    def create_storage_config_tab(self):
        """创建存储配置选项卡"""
        widget = QScrollArea()
        content = QFrame()
        layout = QGridLayout(content)

        # 检查点阈值
        layout.addWidget(QLabel("检查点阈值:"), 0, 0)
        self.checkpoint_threshold_edit = QLineEdit()
        self.checkpoint_threshold_edit.setPlaceholderText("例如: 512MB")
        self.checkpoint_threshold_edit.textChanged.connect(self.on_config_changed)
        layout.addWidget(self.checkpoint_threshold_edit, 0, 1)

        # WAL自动检查点
        layout.addWidget(QLabel("WAL自动检查点:"), 1, 0)
        self.wal_autocheckpoint_spin = QSpinBox()
        self.wal_autocheckpoint_spin.setRange(100, 100000)
        self.wal_autocheckpoint_spin.valueChanged.connect(self.on_config_changed)
        layout.addWidget(self.wal_autocheckpoint_spin, 1, 1)

        # 临时目录大小
        layout.addWidget(QLabel("临时目录大小:"), 2, 0)
        self.temp_directory_size_edit = QLineEdit()
        self.temp_directory_size_edit.setPlaceholderText("例如: 20GB")
        self.temp_directory_size_edit.textChanged.connect(self.on_config_changed)
        layout.addWidget(self.temp_directory_size_edit, 2, 1)

        # 存储选项
        storage_options_layout = QVBoxLayout()

        self.enable_fsync_cb = QCheckBox("启用Fsync")
        self.enable_fsync_cb.stateChanged.connect(self.on_config_changed)
        storage_options_layout.addWidget(self.enable_fsync_cb)

        self.enable_mmap_cb = QCheckBox("启用内存映射")
        self.enable_mmap_cb.stateChanged.connect(self.on_config_changed)
        storage_options_layout.addWidget(self.enable_mmap_cb)

        layout.addWidget(QLabel("存储选项:"), 3, 0)
        layout.addLayout(storage_options_layout, 3, 1)

        layout.setRowStretch(4, 1)

        widget.setWidget(content)
        widget.setWidgetResizable(True)
        return widget

    def create_query_config_tab(self):
        """创建查询配置选项卡"""
        widget = QScrollArea()
        content = QFrame()
        layout = QGridLayout(content)

        # 查询优化选项
        query_options_layout = QVBoxLayout()

        self.enable_optimizer_cb = QCheckBox("启用查询优化器")
        self.enable_optimizer_cb.stateChanged.connect(self.on_config_changed)
        query_options_layout.addWidget(self.enable_optimizer_cb)

        self.enable_profiling_cb = QCheckBox("启用性能分析")
        self.enable_profiling_cb.stateChanged.connect(self.on_config_changed)
        query_options_layout.addWidget(self.enable_profiling_cb)

        self.enable_progress_bar_cb = QCheckBox("启用进度条")
        self.enable_progress_bar_cb.stateChanged.connect(self.on_config_changed)
        query_options_layout.addWidget(self.enable_progress_bar_cb)

        self.enable_object_cache_cb = QCheckBox("启用对象缓存")
        self.enable_object_cache_cb.stateChanged.connect(self.on_config_changed)
        query_options_layout.addWidget(self.enable_object_cache_cb)

        self.enable_external_access_cb = QCheckBox("启用外部访问")
        self.enable_external_access_cb.stateChanged.connect(self.on_config_changed)
        query_options_layout.addWidget(self.enable_external_access_cb)

        self.enable_httpfs_cb = QCheckBox("启用HTTP文件系统")
        self.enable_httpfs_cb.stateChanged.connect(self.on_config_changed)
        query_options_layout.addWidget(self.enable_httpfs_cb)

        self.enable_parquet_statistics_cb = QCheckBox("启用Parquet统计")
        self.enable_parquet_statistics_cb.stateChanged.connect(self.on_config_changed)
        query_options_layout.addWidget(self.enable_parquet_statistics_cb)

        self.preserve_insertion_order_cb = QCheckBox("保持插入顺序")
        self.preserve_insertion_order_cb.stateChanged.connect(self.on_config_changed)
        query_options_layout.addWidget(self.preserve_insertion_order_cb)

        self.enable_verification_cb = QCheckBox("启用验证")
        self.enable_verification_cb.stateChanged.connect(self.on_config_changed)
        query_options_layout.addWidget(self.enable_verification_cb)

        layout.addWidget(QLabel("查询选项:"), 0, 0)
        layout.addLayout(query_options_layout, 0, 1)

        # 最大表达式深度
        layout.addWidget(QLabel("最大表达式深度:"), 1, 0)
        self.max_expression_depth_spin = QSpinBox()
        self.max_expression_depth_spin.setRange(100, 10000)
        self.max_expression_depth_spin.valueChanged.connect(self.on_config_changed)
        layout.addWidget(self.max_expression_depth_spin, 1, 1)

        layout.setRowStretch(2, 1)

        widget.setWidget(content)
        widget.setWidgetResizable(True)
        return widget

    def create_advanced_config_tab(self):
        """创建高级配置选项卡"""
        widget = QScrollArea()
        content = QFrame()
        layout = QGridLayout(content)

        # 高级优化选项
        advanced_options_layout = QVBoxLayout()

        self.force_parallelism_cb = QCheckBox("强制并行")
        self.force_parallelism_cb.stateChanged.connect(self.on_config_changed)
        advanced_options_layout.addWidget(self.force_parallelism_cb)

        self.enable_join_order_optimizer_cb = QCheckBox("启用连接顺序优化器")
        self.enable_join_order_optimizer_cb.stateChanged.connect(self.on_config_changed)
        advanced_options_layout.addWidget(self.enable_join_order_optimizer_cb)

        self.enable_unnest_rewriter_cb = QCheckBox("启用嵌套重写器")
        self.enable_unnest_rewriter_cb.stateChanged.connect(self.on_config_changed)
        advanced_options_layout.addWidget(self.enable_unnest_rewriter_cb)

        self.enable_object_cache_map_cb = QCheckBox("启用对象缓存映射")
        self.enable_object_cache_map_cb.stateChanged.connect(self.on_config_changed)
        advanced_options_layout.addWidget(self.enable_object_cache_map_cb)

        self.enable_auto_analyze_cb = QCheckBox("启用自动分析")
        self.enable_auto_analyze_cb.stateChanged.connect(self.on_config_changed)
        advanced_options_layout.addWidget(self.enable_auto_analyze_cb)

        self.enable_compression_cb = QCheckBox("启用压缩")
        self.enable_compression_cb.stateChanged.connect(self.on_config_changed)
        advanced_options_layout.addWidget(self.enable_compression_cb)

        layout.addWidget(QLabel("高级选项:"), 0, 0)
        layout.addLayout(advanced_options_layout, 0, 1)

        # 自动分析样本大小
        layout.addWidget(QLabel("自动分析样本大小:"), 1, 0)
        self.auto_analyze_sample_size_spin = QSpinBox()
        self.auto_analyze_sample_size_spin.setRange(1000, 1000000)
        self.auto_analyze_sample_size_spin.valueChanged.connect(self.on_config_changed)
        layout.addWidget(self.auto_analyze_sample_size_spin, 1, 1)

        # 压缩级别
        layout.addWidget(QLabel("压缩级别:"), 2, 0)
        self.compression_level_spin = QSpinBox()
        self.compression_level_spin.setRange(1, 9)
        self.compression_level_spin.valueChanged.connect(self.on_config_changed)
        layout.addWidget(self.compression_level_spin, 2, 1)

        # HTTP超时
        layout.addWidget(QLabel("HTTP超时(ms):"), 3, 0)
        self.http_timeout_spin = QSpinBox()
        self.http_timeout_spin.setRange(1000, 300000)
        self.http_timeout_spin.valueChanged.connect(self.on_config_changed)
        layout.addWidget(self.http_timeout_spin, 3, 1)

        # HTTP重试次数
        layout.addWidget(QLabel("HTTP重试次数:"), 4, 0)
        self.http_retries_spin = QSpinBox()
        self.http_retries_spin.setRange(0, 10)
        self.http_retries_spin.valueChanged.connect(self.on_config_changed)
        layout.addWidget(self.http_retries_spin, 4, 1)

        layout.setRowStretch(5, 1)

        widget.setWidget(content)
        widget.setWidgetResizable(True)
        return widget

    def create_test_results_tab(self):
        """创建测试结果选项卡"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 测试结果表格
        self.test_results_table = QTableWidget()
        self.test_results_table.setColumnCount(6)
        self.test_results_table.setHorizontalHeaderLabels([
            "测试时间", "测试类型", "成功率", "平均查询时间", "总时间", "备注"
        ])

        self.test_results_table.horizontalHeader().setStretchLastSection(True)
        self.test_results_table.setAlternatingRowColors(True)

        layout.addWidget(self.test_results_table)

        # 刷新按钮
        refresh_btn = QPushButton("刷新测试结果")
        refresh_btn.clicked.connect(self.load_test_results)
        layout.addWidget(refresh_btn)

        return widget

    def load_profiles(self):
        """加载配置配置文件"""
        try:
            profiles = self.config_manager.list_profiles()

            self.profile_table.setRowCount(len(profiles))

            for row, profile in enumerate(profiles):
                # 名称
                self.profile_table.setItem(row, 0, QTableWidgetItem(profile.profile_name))

                # 类型
                self.profile_table.setItem(row, 1, QTableWidgetItem(profile.workload_type))

                # 状态
                status = []
                if profile.is_active:
                    status.append("活动")
                if profile.is_default:
                    status.append("默认")
                status_text = ", ".join(status) if status else "-"
                self.profile_table.setItem(row, 2, QTableWidgetItem(status_text))

                # 描述
                description = profile.description[:50] + "..." if len(profile.description) > 50 else profile.description
                self.profile_table.setItem(row, 3, QTableWidgetItem(description))

                # 存储profile对象
                self.profile_table.item(row, 0).setData(Qt.UserRole, profile)

            # 调整列宽
            self.profile_table.resizeColumnsToContents()

        except Exception as e:
            logger.error(f"加载配置配置文件失败: {e}")
            QMessageBox.warning(self, "错误", f"加载配置配置文件失败: {e}")

    def on_profile_selected(self):
        """配置选择事件"""
        current_row = self.profile_table.currentRow()
        if current_row >= 0:
            item = self.profile_table.item(current_row, 0)
            if item:
                profile = item.data(Qt.UserRole)
                self.load_profile_details(profile)

    def load_profile_details(self, profile: DuckDBConfigProfile):
        """加载配置详情"""
        self.current_profile = profile

        # 更新标题
        self.profile_name_label.setText(f"配置: {profile.profile_name}")

        # 基本信息
        self.name_edit.setText(profile.profile_name)
        self.description_edit.setPlainText(profile.description)
        self.workload_combo.setCurrentText(profile.workload_type)
        self.is_active_cb.setChecked(profile.is_active)
        self.is_default_cb.setChecked(profile.is_default)

        self.created_by_label.setText(profile.created_by)
        self.created_at_label.setText(profile.created_at or "-")
        self.updated_at_label.setText(profile.updated_at or "-")

        # 内存配置
        self.memory_limit_edit.setText(profile.memory_limit)
        self.max_memory_edit.setText(profile.max_memory)
        self.buffer_pool_size_edit.setText(profile.buffer_pool_size)
        self.temp_memory_limit_edit.setText(profile.temp_memory_limit)

        # 线程配置
        self.threads_spin.setValue(profile.threads)
        self.io_threads_spin.setValue(profile.io_threads)
        self.parallel_tasks_spin.setValue(profile.parallel_tasks)
        self.worker_threads_spin.setValue(profile.worker_threads)

        # 存储配置
        self.checkpoint_threshold_edit.setText(profile.checkpoint_threshold)
        self.wal_autocheckpoint_spin.setValue(profile.wal_autocheckpoint)
        self.temp_directory_size_edit.setText(profile.temp_directory_size)
        self.enable_fsync_cb.setChecked(profile.enable_fsync)
        self.enable_mmap_cb.setChecked(profile.enable_mmap)

        # 查询配置
        self.enable_optimizer_cb.setChecked(profile.enable_optimizer)
        self.enable_profiling_cb.setChecked(profile.enable_profiling)
        self.enable_progress_bar_cb.setChecked(profile.enable_progress_bar)
        self.enable_object_cache_cb.setChecked(profile.enable_object_cache)
        self.max_expression_depth_spin.setValue(profile.max_expression_depth)
        self.enable_external_access_cb.setChecked(profile.enable_external_access)
        self.enable_httpfs_cb.setChecked(profile.enable_httpfs)
        self.enable_parquet_statistics_cb.setChecked(profile.enable_parquet_statistics)
        self.preserve_insertion_order_cb.setChecked(profile.preserve_insertion_order)
        self.enable_verification_cb.setChecked(profile.enable_verification)

        # 高级配置
        self.force_parallelism_cb.setChecked(profile.force_parallelism)
        self.enable_join_order_optimizer_cb.setChecked(profile.enable_join_order_optimizer)
        self.enable_unnest_rewriter_cb.setChecked(profile.enable_unnest_rewriter)
        self.enable_object_cache_map_cb.setChecked(profile.enable_object_cache_map)
        self.enable_auto_analyze_cb.setChecked(profile.enable_auto_analyze)
        self.auto_analyze_sample_size_spin.setValue(profile.auto_analyze_sample_size)
        self.enable_compression_cb.setChecked(profile.enable_compression)
        self.compression_level_spin.setValue(profile.compression_level)
        self.http_timeout_spin.setValue(profile.http_timeout)
        self.http_retries_spin.setValue(profile.http_retries)

        # 启用保存按钮
        self.save_btn.setEnabled(True)

        # 加载测试结果
        self.load_test_results()

    def on_config_changed(self):
        """配置变更事件"""
        if self.current_profile:
            self.save_btn.setEnabled(True)

    def save_current_profile(self):
        """保存当前配置"""
        if not self.current_profile:
            return

        try:
            # 更新配置对象
            self.current_profile.profile_name = self.name_edit.text()
            self.current_profile.description = self.description_edit.toPlainText()
            self.current_profile.workload_type = self.workload_combo.currentText()
            self.current_profile.is_active = self.is_active_cb.isChecked()
            self.current_profile.is_default = self.is_default_cb.isChecked()

            # 内存配置
            self.current_profile.memory_limit = self.memory_limit_edit.text()
            self.current_profile.max_memory = self.max_memory_edit.text()
            self.current_profile.buffer_pool_size = self.buffer_pool_size_edit.text()
            self.current_profile.temp_memory_limit = self.temp_memory_limit_edit.text()

            # 线程配置
            self.current_profile.threads = self.threads_spin.value()
            self.current_profile.io_threads = self.io_threads_spin.value()
            self.current_profile.parallel_tasks = self.parallel_tasks_spin.value()
            self.current_profile.worker_threads = self.worker_threads_spin.value()

            # 存储配置
            self.current_profile.checkpoint_threshold = self.checkpoint_threshold_edit.text()
            self.current_profile.wal_autocheckpoint = self.wal_autocheckpoint_spin.value()
            self.current_profile.temp_directory_size = self.temp_directory_size_edit.text()
            self.current_profile.enable_fsync = self.enable_fsync_cb.isChecked()
            self.current_profile.enable_mmap = self.enable_mmap_cb.isChecked()

            # 查询配置
            self.current_profile.enable_optimizer = self.enable_optimizer_cb.isChecked()
            self.current_profile.enable_profiling = self.enable_profiling_cb.isChecked()
            self.current_profile.enable_progress_bar = self.enable_progress_bar_cb.isChecked()
            self.current_profile.enable_object_cache = self.enable_object_cache_cb.isChecked()
            self.current_profile.max_expression_depth = self.max_expression_depth_spin.value()
            self.current_profile.enable_external_access = self.enable_external_access_cb.isChecked()
            self.current_profile.enable_httpfs = self.enable_httpfs_cb.isChecked()
            self.current_profile.enable_parquet_statistics = self.enable_parquet_statistics_cb.isChecked()
            self.current_profile.preserve_insertion_order = self.preserve_insertion_order_cb.isChecked()
            self.current_profile.enable_verification = self.enable_verification_cb.isChecked()

            # 高级配置
            self.current_profile.force_parallelism = self.force_parallelism_cb.isChecked()
            self.current_profile.enable_join_order_optimizer = self.enable_join_order_optimizer_cb.isChecked()
            self.current_profile.enable_unnest_rewriter = self.enable_unnest_rewriter_cb.isChecked()
            self.current_profile.enable_object_cache_map = self.enable_object_cache_map_cb.isChecked()
            self.current_profile.enable_auto_analyze = self.enable_auto_analyze_cb.isChecked()
            self.current_profile.auto_analyze_sample_size = self.auto_analyze_sample_size_spin.value()
            self.current_profile.enable_compression = self.enable_compression_cb.isChecked()
            self.current_profile.compression_level = self.compression_level_spin.value()
            self.current_profile.http_timeout = self.http_timeout_spin.value()
            self.current_profile.http_retries = self.http_retries_spin.value()

            # 保存到数据库
            success = self.config_manager.update_profile(self.current_profile, "ui_user")

            if success:
                QMessageBox.information(self, "成功", "配置保存成功")
                self.save_btn.setEnabled(False)
                self.load_profiles()  # 刷新列表
            else:
                QMessageBox.warning(self, "错误", "配置保存失败")

        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            QMessageBox.warning(self, "错误", f"保存配置失败: {e}")

    def create_new_profile(self):
        """创建新配置"""
        try:
            # 创建默认配置
            new_profile = DuckDBConfigProfile(
                profile_name="新配置",
                description="新创建的DuckDB配置",
                workload_type="OLAP",
                created_by="ui_user"
            )

            profile_id = self.config_manager.create_profile(new_profile)
            new_profile.id = profile_id

            QMessageBox.information(self, "成功", "新配置创建成功")
            self.load_profiles()

            # 选择新创建的配置
            for row in range(self.profile_table.rowCount()):
                item = self.profile_table.item(row, 0)
                if item and item.data(Qt.UserRole).id == profile_id:
                    self.profile_table.selectRow(row)
                    break

        except Exception as e:
            logger.error(f"创建新配置失败: {e}")
            QMessageBox.warning(self, "错误", f"创建新配置失败: {e}")

    def clone_current_profile(self):
        """克隆当前配置"""
        if not self.current_profile:
            QMessageBox.warning(self, "警告", "请先选择要克隆的配置")
            return

        try:
            # 克隆配置
            cloned_profile = DuckDBConfigProfile(**self.current_profile.to_dict())
            cloned_profile.id = None
            cloned_profile.profile_name = f"{self.current_profile.profile_name} - 副本"
            cloned_profile.is_active = False
            cloned_profile.is_default = False
            cloned_profile.created_by = "ui_user"
            cloned_profile.created_at = None
            cloned_profile.updated_at = None

            profile_id = self.config_manager.create_profile(cloned_profile)
            cloned_profile.id = profile_id

            QMessageBox.information(self, "成功", "配置克隆成功")
            self.load_profiles()

        except Exception as e:
            logger.error(f"克隆配置失败: {e}")
            QMessageBox.warning(self, "错误", f"克隆配置失败: {e}")

    def delete_current_profile(self):
        """删除当前配置"""
        if not self.current_profile:
            QMessageBox.warning(self, "警告", "请先选择要删除的配置")
            return

        if self.current_profile.is_active:
            QMessageBox.warning(self, "警告", "不能删除活动配置")
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除配置 '{self.current_profile.profile_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                success = self.config_manager.delete_profile(self.current_profile.id, "ui_user")

                if success:
                    QMessageBox.information(self, "成功", "配置删除成功")
                    self.load_profiles()
                    self.current_profile = None
                    self.profile_name_label.setText("未选择配置")
                    self.save_btn.setEnabled(False)
                else:
                    QMessageBox.warning(self, "错误", "配置删除失败")

            except Exception as e:
                logger.error(f"删除配置失败: {e}")
                QMessageBox.warning(self, "错误", f"删除配置失败: {e}")

    def show_profile_context_menu(self, position):
        """显示配置右键菜单"""
        if self.profile_table.itemAt(position):
            menu = QMenu(self)

            activate_action = QAction("激活配置", self)
            activate_action.triggered.connect(self.activate_current_profile)
            menu.addAction(activate_action)

            menu.addSeparator()

            clone_action = QAction("克隆配置", self)
            clone_action.triggered.connect(self.clone_current_profile)
            menu.addAction(clone_action)

            delete_action = QAction("删除配置", self)
            delete_action.triggered.connect(self.delete_current_profile)
            menu.addAction(delete_action)

            menu.exec_(self.profile_table.mapToGlobal(position))

    def activate_current_profile(self):
        """激活当前配置"""
        if not self.current_profile:
            QMessageBox.warning(self, "警告", "请先选择要激活的配置")
            return

        try:
            success = self.config_manager.activate_profile(self.current_profile.id, "ui_user")

            if success:
                QMessageBox.information(self, "成功", f"配置 '{self.current_profile.profile_name}' 已激活")
                self.load_profiles()
                # 重新加载当前配置以更新状态
                updated_profile = self.config_manager.get_profile(self.current_profile.id)
                if updated_profile:
                    self.load_profile_details(updated_profile)
            else:
                QMessageBox.warning(self, "错误", "配置激活失败")

        except Exception as e:
            logger.error(f"激活配置失败: {e}")
            QMessageBox.warning(self, "错误", f"激活配置失败: {e}")

    def test_current_config(self):
        """测试当前配置"""
        if not self.current_profile:
            QMessageBox.warning(self, "警告", "请先选择要测试的配置")
            return

        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("准备测试...")

        # 禁用按钮
        self.test_btn.setEnabled(False)
        self.apply_btn.setEnabled(False)

        # 启动测试线程
        self.test_thread = DuckDBConfigTestThread(self.current_profile)
        self.test_thread.progress_updated.connect(self.on_test_progress)
        self.test_thread.test_completed.connect(self.on_test_completed)
        self.test_thread.test_failed.connect(self.on_test_failed)
        self.test_thread.start()

    def on_test_progress(self, progress: int, message: str):
        """测试进度更新"""
        self.progress_bar.setValue(progress)
        self.progress_label.setText(message)

    def on_test_completed(self, test_result: Dict[str, Any]):
        """测试完成"""
        # 隐藏进度条
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)

        # 启用按钮
        self.test_btn.setEnabled(True)
        self.apply_btn.setEnabled(True)

        # 保存测试结果
        try:
            self.config_manager.save_performance_test(test_result)

            # 显示测试结果
            success_rate = test_result.get('success_rate', 0)
            avg_time = test_result.get('average_query_time', 0)

            QMessageBox.information(
                self, "测试完成",
                f"配置测试完成！\n\n"
                f"成功率: {success_rate:.1f}%\n"
                f"平均查询时间: {avg_time:.4f}s\n"
                f"测试查询数: {test_result.get('test_queries_count', 0)}"
            )

            # 刷新测试结果
            self.load_test_results()

        except Exception as e:
            logger.error(f"保存测试结果失败: {e}")
            QMessageBox.warning(self, "警告", f"测试完成但保存结果失败: {e}")

    def on_test_failed(self, error_message: str):
        """测试失败"""
        # 隐藏进度条
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)

        # 启用按钮
        self.test_btn.setEnabled(True)
        self.apply_btn.setEnabled(True)

        QMessageBox.warning(self, "测试失败", f"配置测试失败: {error_message}")

    def apply_current_config(self):
        """应用当前配置"""
        if not self.current_profile:
            QMessageBox.warning(self, "警告", "请先选择要应用的配置")
            return

        reply = QMessageBox.question(
            self, "确认应用",
            f"确定要应用配置 '{self.current_profile.profile_name}' 吗？\n"
            f"这将激活该配置并重新初始化DuckDB连接。",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # 激活配置
                success = self.config_manager.activate_profile(self.current_profile.id, "ui_user")

                if success:
                    # R289 修复：原实现只写 SQLite is_active 标记（"假生效"）——
                    # 高级配置对话框编辑保存的配置从未推送到任何连接体系。
                    # 现在将 profile 映射为 manager 版 DuckDBConfig 并注入全局
                    # DuckDBConnectionManager 单例（settings_dialog._apply_duckdb_config_to_manager
                    # 同款路径）：更新 _default_config 并重建业务连接池，经
                    # DuckDBConnectionPool._apply_config 对每个池连接真正 SET。
                    applied = self._apply_profile_to_manager(self.current_profile)

                    QMessageBox.information(
                        self, "成功",
                        f"配置 '{self.current_profile.profile_name}' 已应用并激活"
                        + ("，已注入业务 DuckDB 连接池" if applied else "（业务连接池注入失败，请查看日志）")
                    )

                    self.load_profiles()

                    # 重新加载当前配置
                    updated_profile = self.config_manager.get_profile(self.current_profile.id)
                    if updated_profile:
                        self.load_profile_details(updated_profile)
                else:
                    QMessageBox.warning(self, "错误", "配置应用失败")

            except Exception as e:
                logger.error(f"应用配置失败: {e}")
                QMessageBox.warning(self, "错误", f"应用配置失败: {e}")

    def _apply_profile_to_manager(self, profile: 'DuckDBConfigProfile') -> bool:
        """R289：将高级配置 profile 注入全局 DuckDBConnectionManager（真正生效）

        把 DuckDBConfigProfile（33 字段、int threads）映射为 manager 版
        DuckDBConfig（交集字段、str threads），调用 apply_default_config。
        仅映射 manager 支持的字段，其余 profile 专属字段（io_threads/
        buffer_pool_size/compression_level/http_* 等）业务连接不消费，忽略。
        """
        try:
            from core.database.duckdb_manager import get_connection_manager, DuckDBConfig
            cfg = DuckDBConfig(
                memory_limit=getattr(profile, 'memory_limit', None) or '4.0GB',
                threads=str(getattr(profile, 'threads', 4)),
                max_memory=getattr(profile, 'max_memory', None) or '4.4GB',
                checkpoint_threshold=getattr(profile, 'checkpoint_threshold', None) or '512MB',
                enable_progress_bar=getattr(profile, 'enable_progress_bar', True),
                enable_profiling=getattr(profile, 'enable_profiling', False),
                preserve_insertion_order=getattr(profile, 'preserve_insertion_order', False),
                enable_external_access=getattr(profile, 'enable_external_access', True),
            )
            ok = get_connection_manager().apply_default_config(cfg)
            if ok:
                logger.info(
                    f"DuckDB 高级配置已注入业务连接池: memory_limit={cfg.memory_limit} "
                    f"threads={cfg.threads} max_memory={cfg.max_memory}")
            return ok
        except Exception as e:
            logger.error(f"DuckDB 高级配置注入失败: {e}")
            return False

    def load_test_results(self):
        """加载测试结果"""
        if not self.current_profile:
            self.test_results_table.setRowCount(0)
            return

        try:
            test_results = self.config_manager.get_performance_tests(self.current_profile.id)

            self.test_results_table.setRowCount(len(test_results))

            for row, result in enumerate(test_results):
                # 测试时间
                tested_at = result.get('tested_at', '')
                if tested_at:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(tested_at)
                        tested_at = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass

                self.test_results_table.setItem(row, 0, QTableWidgetItem(tested_at))

                # 测试类型
                self.test_results_table.setItem(row, 1, QTableWidgetItem(result.get('test_type', '')))

                # 成功率
                success_rate = result.get('success_rate', 0)
                self.test_results_table.setItem(row, 2, QTableWidgetItem(f"{success_rate:.1f}%"))

                # 平均查询时间
                avg_time = result.get('average_query_time', 0)
                self.test_results_table.setItem(row, 3, QTableWidgetItem(f"{avg_time:.4f}s"))

                # 总时间
                total_time = result.get('total_test_time', 0)
                self.test_results_table.setItem(row, 4, QTableWidgetItem(f"{total_time:.4f}s"))

                # 备注
                notes = result.get('notes', '')
                self.test_results_table.setItem(row, 5, QTableWidgetItem(notes))

            self.test_results_table.resizeColumnsToContents()

        except Exception as e:
            logger.error(f"加载测试结果失败: {e}")

def show_duckdb_config_dialog(parent=None):
    """显示DuckDB配置对话框"""
    try:
        # 确保默认配置存在
        from db.models.duckdb_config_models import create_default_profiles
        create_default_profiles()

        dialog = DuckDBConfigDialog(parent)
        return dialog.exec_()

    except Exception as e:
        logger.error(f"显示DuckDB配置对话框失败: {e}")
        if parent:
            QMessageBox.warning(parent, "错误", f"无法打开DuckDB配置对话框: {e}")
        return QDialog.Rejected

if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication

    # 配置日志
    # Loguru配置在core.loguru_config中统一管理

    app = QApplication(sys.argv)

    # 显示对话框
    result = show_duckdb_config_dialog()

    sys.exit(result)
