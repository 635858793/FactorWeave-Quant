#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据管理主界面组件

提供统一的数据管理界面，包括：
- 数据源管理和配置
- 下载任务管理和监控
- 数据质量监控和报告
- 智能数据缺失处理

作者: FactorWeave-Quant团队
版本: 1.0
"""

import sys
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QSplitter, QScrollArea,
    QTableWidget, QTableWidgetItem, QTextEdit, QProgressBar,
    QGroupBox, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QApplication, QHeaderView, QComboBox, QLineEdit,
    QDateEdit, QSpinBox, QCheckBox, QListWidget, QListWidgetItem,
    QMessageBox, QMenu, QToolBar, QAction, QStatusBar,
    QDialog, QDialogButtonBox, QFormLayout, QAbstractItemView
)
from PyQt5.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QDate, QSize,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
)
from PyQt5.QtGui import (
    QFont, QPalette, QColor, QIcon, QPixmap, QPainter,
    QLinearGradient, QPen, QBrush
)

# 导入核心组件
try:
    from core.plugin_types import AssetType, DataType, PluginType, DataSourceProvider
    from core.asset_type_identifier import AssetTypeIdentifier
    from core.data_router import DataRouter, get_data_router
    from core.ui_integration.data_missing_manager import DataMissingManager, get_data_missing_manager
    from core.ui_integration.smart_data_integration import SmartDataIntegration, get_smart_data_integration
    from core.database_maintenance_engine import DatabaseMaintenanceEngine
    from core.data_standardization_engine import DataStandardizationEngine
    from loguru import logger
    CORE_AVAILABLE = True
except ImportError as e:
    logger = None
    print(f"导入核心组件失败: {e}")
    CORE_AVAILABLE = False

logger = logger.bind(module=__name__) if logger else None


class DataSourceStatus(Enum):
    """数据源状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class DataSourceInfo:
    """数据源信息"""
    name: str
    provider: str
    status: DataSourceStatus
    asset_types: List[AssetType]
    data_types: List[DataType]
    last_update: Optional[datetime] = None
    error_message: Optional[str] = None
    config: Dict[str, Any] = None


class DataSourceManagementWidget(QWidget):
    """数据源管理组件"""

    # 信号定义
    source_selected = pyqtSignal(str)  # 数据源选中
    source_configured = pyqtSignal(str, dict)  # 数据源配置
    source_enabled = pyqtSignal(str, bool)  # 数据源启用/禁用

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_router = None
        self.data_sources = {}
        self.setup_ui()
        self.setup_connections()
        self.load_data_sources()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # 刷新按钮
        refresh_action = QAction("刷新", self)
        refresh_action.setIcon(self.style().standardIcon(self.style().SP_BrowserReload))
        refresh_action.triggered.connect(self.refresh_sources)
        toolbar.addAction(refresh_action)

        # 配置按钮
        config_action = QAction("配置", self)
        config_action.setIcon(self.style().standardIcon(self.style().SP_ComputerIcon))
        config_action.triggered.connect(self.configure_selected_source)
        toolbar.addAction(config_action)

        layout.addWidget(toolbar)

        # 数据源列表
        self.sources_table = QTableWidget()
        self.sources_table.setColumnCount(6)
        self.sources_table.setHorizontalHeaderLabels([
            "数据源", "提供商", "状态", "支持资产", "支持数据类型", "最后更新"
        ])

        # 设置表格属性
        header = self.sources_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.sources_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sources_table.setAlternatingRowColors(True)

        layout.addWidget(self.sources_table)

        # 详细信息面板
        details_group = QGroupBox("数据源详情")
        details_layout = QVBoxLayout(details_group)

        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(150)
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)

        layout.addWidget(details_group)

    def setup_connections(self):
        """设置信号连接"""
        self.sources_table.itemSelectionChanged.connect(self.on_source_selected)

    def load_data_sources(self):
        """加载数据源信息"""
        if not CORE_AVAILABLE:
            return

        try:
            # 获取数据路由器
            self.data_router = get_data_router()
            if not self.data_router:
                return

            # 获取数据源统计信息
            stats = self.data_router.get_route_statistics()

            logger.warning("数据源信息引擎不可用，无法加载真实数据源列表。请配置数据源插件管理器。")
            self.update_sources_table([])

        except Exception as e:
            if logger:
                logger.error(f"加载数据源失败: {e}")

    def update_sources_table(self, sources: List[DataSourceInfo]):
        """更新数据源表格"""
        self.sources_table.setRowCount(len(sources))

        for row, source in enumerate(sources):
            # 数据源名称
            name_item = QTableWidgetItem(source.name)
            self.sources_table.setItem(row, 0, name_item)

            # 提供商
            provider_item = QTableWidgetItem(source.provider)
            self.sources_table.setItem(row, 1, provider_item)

            # 状态
            status_item = QTableWidgetItem(source.status.value)
            if source.status == DataSourceStatus.ACTIVE:
                status_item.setBackground(QColor(144, 238, 144))  # 浅绿色
            elif source.status == DataSourceStatus.ERROR:
                status_item.setBackground(QColor(255, 182, 193))  # 浅红色
            else:
                status_item.setBackground(QColor(211, 211, 211))  # 浅灰色
            self.sources_table.setItem(row, 2, status_item)

            # 支持的资产类型
            asset_types = ", ".join([at.value for at in source.asset_types])
            asset_item = QTableWidgetItem(asset_types)
            self.sources_table.setItem(row, 3, asset_item)

            # 支持的数据类型
            data_types = ", ".join([dt.value for dt in source.data_types])
            data_item = QTableWidgetItem(data_types)
            self.sources_table.setItem(row, 4, data_item)

            # 最后更新时间
            last_update = source.last_update.strftime("%Y-%m-%d %H:%M") if source.last_update else "未知"
            update_item = QTableWidgetItem(last_update)
            self.sources_table.setItem(row, 5, update_item)

            # 存储完整信息
            self.data_sources[source.name] = source

    def on_source_selected(self):
        """数据源选中事件"""
        current_row = self.sources_table.currentRow()
        if current_row >= 0:
            name_item = self.sources_table.item(current_row, 0)
            if name_item:
                source_name = name_item.text()
                source_info = self.data_sources.get(source_name)
                if source_info:
                    self.show_source_details(source_info)
                    self.source_selected.emit(source_name)

    def show_source_details(self, source: DataSourceInfo):
        """显示数据源详情"""
        details = f"""
数据源: {source.name}
提供商: {source.provider}
状态: {source.status.value}
支持资产类型: {', '.join([at.value for at in source.asset_types])}
支持数据类型: {', '.join([dt.value for dt in source.data_types])}
最后更新: {source.last_update.strftime('%Y-%m-%d %H:%M:%S') if source.last_update else '未知'}
"""

        if source.error_message:
            details += f"\n错误信息: {source.error_message}"

        if source.config:
            details += f"\n配置信息: {json.dumps(source.config, indent=2, ensure_ascii=False)}"

        self.details_text.setText(details)

    def refresh_sources(self):
        """刷新数据源"""
        self.load_data_sources()

    def configure_selected_source(self):
        """配置选中的数据源"""
        current_row = self.sources_table.currentRow()
        if current_row >= 0:
            name_item = self.sources_table.item(current_row, 0)
            if name_item:
                source_name = name_item.text()
                self.show_source_config_dialog(source_name)

    def show_source_config_dialog(self, source_name: str):
        """显示数据源配置对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"配置数据源: {source_name}")
        dialog.setModal(True)
        dialog.resize(400, 300)

        layout = QVBoxLayout(dialog)

        # 配置表单
        form_layout = QFormLayout()

        # 启用/禁用
        enabled_cb = QCheckBox()
        enabled_cb.setChecked(True)
        form_layout.addRow("启用:", enabled_cb)

        # 超时设置
        timeout_spin = QSpinBox()
        timeout_spin.setRange(1, 300)
        timeout_spin.setValue(30)
        timeout_spin.setSuffix("秒")
        form_layout.addRow("超时时间:", timeout_spin)

        # 重试次数
        retry_spin = QSpinBox()
        retry_spin.setRange(0, 10)
        retry_spin.setValue(3)
        form_layout.addRow("重试次数:", retry_spin)

        layout.addLayout(form_layout)

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec_() == QDialog.Accepted:
            config = {
                'enabled': enabled_cb.isChecked(),
                'timeout': timeout_spin.value(),
                'retry_count': retry_spin.value()
            }
            self.source_configured.emit(source_name, config)


class DownloadTaskWidget(QWidget):
    """下载任务管理组件"""

    # 信号定义
    task_started = pyqtSignal(str)  # 任务开始
    task_paused = pyqtSignal(str)   # 任务暂停
    task_stopped = pyqtSignal(str)  # 任务停止

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks = {}
        self.setup_ui()
        self.setup_timer()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # 新建任务
        new_task_action = QAction("新建任务", self)
        new_task_action.setIcon(self.style().standardIcon(self.style().SP_FileIcon))
        new_task_action.triggered.connect(self.create_new_task)
        toolbar.addAction(new_task_action)

        # 开始任务
        start_action = QAction("开始", self)
        start_action.setIcon(self.style().standardIcon(self.style().SP_MediaPlay))
        start_action.triggered.connect(self.start_selected_task)
        toolbar.addAction(start_action)

        # 暂停任务
        pause_action = QAction("暂停", self)
        pause_action.setIcon(self.style().standardIcon(self.style().SP_MediaPause))
        pause_action.triggered.connect(self.pause_selected_task)
        toolbar.addAction(pause_action)

        # 停止任务
        stop_action = QAction("停止", self)
        stop_action.setIcon(self.style().standardIcon(self.style().SP_MediaStop))
        stop_action.triggered.connect(self.stop_selected_task)
        toolbar.addAction(stop_action)

        layout.addWidget(toolbar)

        # 任务列表
        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(7)
        self.tasks_table.setHorizontalHeaderLabels([
            "任务名称", "数据源", "资产类型", "状态", "进度", "开始时间", "预计完成"
        ])

        # 设置表格属性
        header = self.tasks_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)

        self.tasks_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tasks_table.setAlternatingRowColors(True)

        layout.addWidget(self.tasks_table)

        # 任务详情
        details_group = QGroupBox("任务详情")
        details_layout = QVBoxLayout(details_group)

        self.task_details = QTextEdit()
        self.task_details.setMaximumHeight(120)
        self.task_details.setReadOnly(True)
        details_layout.addWidget(self.task_details)

        layout.addWidget(details_group)

    def setup_timer(self):
        """设置定时器"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_task_progress)
        self.update_timer.start(1000)  # 每秒更新一次

    def create_new_task(self):
        """创建新任务"""
        dialog = QDialog(self)
        dialog.setWindowTitle("创建下载任务")
        dialog.setModal(True)
        dialog.resize(500, 400)

        layout = QVBoxLayout(dialog)

        # 任务配置表单
        form_layout = QFormLayout()

        # 任务名称
        name_edit = QLineEdit()
        name_edit.setText(f"下载任务_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        form_layout.addRow("任务名称:", name_edit)

        # 数据源选择
        source_combo = QComboBox()
        source_combo.addItems(["tongdaxin", "eastmoney", "sina", "binance"])
        form_layout.addRow("数据源:", source_combo)

        # 资产类型
        asset_combo = QComboBox()
        asset_combo.addItems([at.value for at in AssetType])
        form_layout.addRow("资产类型:", asset_combo)

        # 数据类型
        data_combo = QComboBox()
        data_combo.addItems([dt.value for dt in DataType])
        form_layout.addRow("数据类型:", data_combo)

        # 股票代码
        symbols_edit = QTextEdit()
        symbols_edit.setMaximumHeight(80)
        symbols_edit.setPlaceholderText("输入股票代码，每行一个，例如：\n000001\n000002\n600000")
        form_layout.addRow("股票代码:", symbols_edit)

        # 日期范围
        start_date = QDateEdit()
        start_date.setDate(QDate.currentDate().addDays(-30))
        start_date.setCalendarPopup(True)
        form_layout.addRow("开始日期:", start_date)

        end_date = QDateEdit()
        end_date.setDate(QDate.currentDate())
        end_date.setCalendarPopup(True)
        form_layout.addRow("结束日期:", end_date)

        layout.addLayout(form_layout)

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec_() == QDialog.Accepted:
            # 创建任务
            task_config = {
                'name': name_edit.text(),
                'source': source_combo.currentText(),
                'asset_type': asset_combo.currentText(),
                'data_type': data_combo.currentText(),
                'symbols': [s.strip() for s in symbols_edit.toPlainText().split('\n') if s.strip()],
                'start_date': start_date.date().toPyDate(),
                'end_date': end_date.date().toPyDate(),
                'status': 'pending',
                'progress': 0,
                'created_at': datetime.now()
            }

            self.add_task(task_config)

    def add_task(self, task_config: Dict[str, Any]):
        """添加任务"""
        task_id = task_config['name']
        self.tasks[task_id] = task_config
        self.update_tasks_table()

    def update_tasks_table(self):
        """更新任务表格"""
        self.tasks_table.setRowCount(len(self.tasks))

        for row, (task_id, task) in enumerate(self.tasks.items()):
            # 任务名称
            name_item = QTableWidgetItem(task['name'])
            self.tasks_table.setItem(row, 0, name_item)

            # 数据源
            source_item = QTableWidgetItem(task['source'])
            self.tasks_table.setItem(row, 1, source_item)

            # 资产类型
            asset_item = QTableWidgetItem(task['asset_type'])
            self.tasks_table.setItem(row, 2, asset_item)

            # 状态
            status_item = QTableWidgetItem(task['status'])
            if task['status'] == 'running':
                status_item.setBackground(QColor(144, 238, 144))  # 浅绿色
            elif task['status'] == 'completed':
                status_item.setBackground(QColor(173, 216, 230))  # 浅蓝色
            elif task['status'] == 'error':
                status_item.setBackground(QColor(255, 182, 193))  # 浅红色
            self.tasks_table.setItem(row, 3, status_item)

            # 进度
            progress_item = QTableWidgetItem(f"{task['progress']:.1f}%")
            self.tasks_table.setItem(row, 4, progress_item)

            # 开始时间
            start_time = task.get('started_at', task['created_at'])
            start_item = QTableWidgetItem(start_time.strftime("%H:%M:%S"))
            self.tasks_table.setItem(row, 5, start_item)

            # 预计完成时间
            eta = "计算中..." if task['status'] == 'running' else "--"
            eta_item = QTableWidgetItem(eta)
            self.tasks_table.setItem(row, 6, eta_item)

    def update_task_progress(self):
        """更新任务进度"""
        for task_id, task in self.tasks.items():
            if task['status'] == 'running':
                # 模拟进度更新
                task['progress'] = min(task['progress'] + 0.5, 100.0)
                if task['progress'] >= 100.0:
                    task['status'] = 'completed'

        self.update_tasks_table()

    def start_selected_task(self):
        """开始选中的任务"""
        current_row = self.tasks_table.currentRow()
        if current_row >= 0:
            name_item = self.tasks_table.item(current_row, 0)
            if name_item:
                task_name = name_item.text()
                task = self.tasks.get(task_name)
                if task and task['status'] in ['pending', 'paused']:
                    task['status'] = 'running'
                    task['started_at'] = datetime.now()
                    self.task_started.emit(task_name)
                    self.update_tasks_table()

    def pause_selected_task(self):
        """暂停选中的任务"""
        current_row = self.tasks_table.currentRow()
        if current_row >= 0:
            name_item = self.tasks_table.item(current_row, 0)
            if name_item:
                task_name = name_item.text()
                task = self.tasks.get(task_name)
                if task and task['status'] == 'running':
                    task['status'] = 'paused'
                    self.task_paused.emit(task_name)
                    self.update_tasks_table()

    def stop_selected_task(self):
        """停止选中的任务"""
        current_row = self.tasks_table.currentRow()
        if current_row >= 0:
            name_item = self.tasks_table.item(current_row, 0)
            if name_item:
                task_name = name_item.text()
                task = self.tasks.get(task_name)
                if task and task['status'] in ['running', 'paused']:
                    task['status'] = 'stopped'
                    self.task_stopped.emit(task_name)
                    self.update_tasks_table()


class DataQualityMonitorWidget(QWidget):
    """数据质量监控组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_quality_data()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 质量概览
        overview_group = QGroupBox("数据质量概览")
        overview_layout = QGridLayout(overview_group)

        # 质量指标卡片
        self.create_metric_card(overview_layout, "数据完整性", "95.2%", QColor(144, 238, 144), 0, 0)
        self.create_metric_card(overview_layout, "数据准确性", "98.7%", QColor(144, 238, 144), 0, 1)
        self.create_metric_card(overview_layout, "数据及时性", "92.1%", QColor(255, 255, 0), 0, 2)
        self.create_metric_card(overview_layout, "数据一致性", "89.5%", QColor(255, 182, 193), 0, 3)

        layout.addWidget(overview_group)

        # 质量报告表格
        reports_group = QGroupBox("质量检查报告")
        reports_layout = QVBoxLayout(reports_group)

        self.reports_table = QTableWidget()
        self.reports_table.setColumnCount(6)
        self.reports_table.setHorizontalHeaderLabels([
            "检查时间", "数据源", "资产类型", "问题类型", "严重程度", "状态"
        ])

        header = self.reports_table.horizontalHeader()
        header.setStretchLastSection(True)

        reports_layout.addWidget(self.reports_table)
        layout.addWidget(reports_group)

    def create_metric_card(self, layout: QGridLayout, title: str, value: str,
                           color: QColor, row: int, col: int):
        """创建指标卡片"""
        card = QFrame()
        card.setFrameStyle(QFrame.Box)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {color.name()};
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 10px;
            }}
        """)

        card_layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Arial", 10))

        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setFont(QFont("Arial", 16, QFont.Bold))

        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)

        layout.addWidget(card, row, col)

    def load_quality_data(self):
        """加载质量数据"""
        # 模拟质量报告数据
        reports = [
            {
                'time': datetime.now() - timedelta(hours=1),
                'source': 'tongdaxin',
                'asset_type': 'stock_a',
                'issue': '数据缺失',
                'severity': '中等',
                'status': '已修复'
            },
            {
                'time': datetime.now() - timedelta(hours=2),
                'source': 'eastmoney',
                'asset_type': 'stock_a',
                'issue': '数据延迟',
                'severity': '轻微',
                'status': '监控中'
            },
            {
                'time': datetime.now() - timedelta(hours=3),
                'source': 'yahoo',
                'asset_type': 'stock_us',
                'issue': '连接超时',
                'severity': '严重',
                'status': '待处理'
            }
        ]

        self.reports_table.setRowCount(len(reports))

        for row, report in enumerate(reports):
            # 检查时间
            time_item = QTableWidgetItem(report['time'].strftime("%H:%M:%S"))
            self.reports_table.setItem(row, 0, time_item)

            # 数据源
            source_item = QTableWidgetItem(report['source'])
            self.reports_table.setItem(row, 1, source_item)

            # 资产类型
            asset_item = QTableWidgetItem(report['asset_type'])
            self.reports_table.setItem(row, 2, asset_item)

            # 问题类型
            issue_item = QTableWidgetItem(report['issue'])
            self.reports_table.setItem(row, 3, issue_item)

            # 严重程度
            severity_item = QTableWidgetItem(report['severity'])
            if report['severity'] == '严重':
                severity_item.setBackground(QColor(255, 182, 193))
            elif report['severity'] == '中等':
                severity_item.setBackground(QColor(255, 255, 0))
            else:
                severity_item.setBackground(QColor(144, 238, 144))
            self.reports_table.setItem(row, 4, severity_item)

            # 状态
            status_item = QTableWidgetItem(report['status'])
            self.reports_table.setItem(row, 5, status_item)


class DataManagementWidget(QWidget):
    """数据管理主界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("数据管理中心")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # 选项卡
        self.tab_widget = QTabWidget()

        # 数据源管理选项卡
        self.source_widget = DataSourceManagementWidget()
        self.tab_widget.addTab(self.source_widget, "数据源管理")

        # 下载任务选项卡
        self.task_widget = DownloadTaskWidget()
        self.tab_widget.addTab(self.task_widget, "下载任务")

        # 数据质量监控选项卡
        self.quality_widget = DataQualityMonitorWidget()
        self.tab_widget.addTab(self.quality_widget, "质量监控")

        layout.addWidget(self.tab_widget)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("数据管理系统就绪")
        layout.addWidget(self.status_bar)

    def setup_connections(self):
        """设置信号连接"""
        # 数据源管理信号
        self.source_widget.source_selected.connect(self.on_source_selected)
        self.source_widget.source_configured.connect(self.on_source_configured)

        # 下载任务信号
        self.task_widget.task_started.connect(self.on_task_started)
        self.task_widget.task_paused.connect(self.on_task_paused)
        self.task_widget.task_stopped.connect(self.on_task_stopped)

    def on_source_selected(self, source_name: str):
        """数据源选中事件"""
        self.status_bar.showMessage(f"已选中数据源: {source_name}")

    def on_source_configured(self, source_name: str, config: Dict[str, Any]):
        """数据源配置事件"""
        self.status_bar.showMessage(f"数据源 {source_name} 配置已更新")
        if logger:
            logger.info(f"数据源配置更新: {source_name} -> {config}")

    def on_task_started(self, task_name: str):
        """任务开始事件"""
        self.status_bar.showMessage(f"任务已开始: {task_name}")

    def on_task_paused(self, task_name: str):
        """任务暂停事件"""
        self.status_bar.showMessage(f"任务已暂停: {task_name}")

    def on_task_stopped(self, task_name: str):
        """任务停止事件"""
        self.status_bar.showMessage(f"任务已停止: {task_name}")


def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    # 创建主窗口
    widget = DataManagementWidget()
    widget.setWindowTitle("FactorWeave-Quant 数据管理中心")
    widget.resize(1200, 800)
    widget.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
