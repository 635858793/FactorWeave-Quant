from loguru import logger
"""
数据源状态监控小部件

提供实时的数据源状态监控功能，包括：
- 实时健康状态显示
- 路由统计信息
- 失效通知和告警

作者: FactorWeave-Quant 开发团队
版本: 1.0.0
日期: 2024
"""

import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QFrame,
    QScrollArea, QListWidget, QListWidgetItem, QSplitter,
    QTabWidget, QTextEdit, QComboBox, QSpinBox, QCheckBox,
    QApplication
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QColor, QPalette, QPixmap, QPainter, QBrush

logger = logger.bind(module=__name__)


class StatusUpdateWorker(QThread):
    """数据源状态异步更新工作线程"""

    # 信号定义
    status_updated = pyqtSignal(dict)  # 状态数据
    metrics_updated = pyqtSignal(dict)  # 指标数据
    routing_updated = pyqtSignal(dict)  # 路由数据
    update_completed = pyqtSignal()    # 更新完成
    update_failed = pyqtSignal(str)    # 更新失败

    def __init__(self, router, parent=None):
        super().__init__(parent)
        self.router = router
        self._is_running = False

    def run(self):
        """异步更新数据源状态"""
        try:
            self._is_running = True

            if not self.router:
                logger.info("路由器不可用")
                self.update_failed.emit("路由器不可用")
                return

            data_sources = self.router.data_sources
            logger.info(f" 开始异步更新，数据源数量: {len(data_sources)}")

            if not data_sources:
                logger.info("没有注册的数据源")
                self.update_failed.emit("没有注册的数据源")
                return

            # 获取数据源指标（修复版本）
            metrics = self._get_source_metrics(data_sources)

            status_data = {}
            for source_id, adapter in data_sources.items():
                if not self._is_running:
                    break

                try:
                    # 获取插件信息（可能耗时）
                    plugin_info = adapter.get_plugin_info()

                    # 获取适配器统计信息
                    adapter_stats = adapter.get_statistics()

                    # 执行健康检查
                    health_result = adapter.health_check()

                    # 构建状态数据
                    status_data[source_id] = {
                        'name': plugin_info.name if plugin_info else source_id,
                        'status': 'healthy' if health_result.is_healthy else 'error',
                        'last_update': datetime.now(),
                        'response_time': getattr(health_result, 'response_time', 0.0),
                        'health_score': 1.0 if health_result.is_healthy else 0.0,
                        'total_requests': adapter_stats.get('total_requests', 0),
                        'success_rate': adapter_stats.get('success_rate', 0.0),
                        'error_count': adapter_stats.get('error_count', 0)
                    }

                    # 每处理一个数据源，发送一次更新（渐进式更新）
                    self.status_updated.emit({source_id: status_data[source_id]})

                    # 短暂休眠，让出CPU时间
                    self.msleep(5)

                except Exception as e:
                    logger.info(f" 处理数据源状态失败 {source_id}: {e}")
                    # 创建错误状态数据
                    status_data[source_id] = {
                        'name': source_id,
                        'status': 'error',
                        'last_update': datetime.now(),
                        'response_time': 0.0,
                        'health_score': 0.0,
                        'total_requests': 0,
                        'success_rate': 0.0,
                        'error_count': 1,
                        'error_message': str(e)
                    }
                    self.status_updated.emit({source_id: status_data[source_id]})
                    continue

            # 发送路由统计数据（保留最小必要信息）
            if self._is_running:
                routing_data = {}
                try:
                    routing_data = self._get_routing_statistics({})
                except Exception:
                    routing_data = {}
                self.routing_updated.emit(routing_data)

            if self._is_running:
                self.update_completed.emit()
                logger.info("异步状态更新完成")

        except Exception as e:
            self.update_failed.emit(str(e))
            logger.info(f" 异步状态更新失败: {e}")

    def _get_source_metrics(self, data_sources: dict) -> dict:
        """获取数据源指标（精简版，移除性能监控统计）"""
        return {source_id: {} for source_id in data_sources.keys()}

    def _get_routing_statistics(self, metrics: dict) -> dict:
        """获取路由统计数据（基于路由器的 DataSourceMetrics）"""
        routing_data = {}
        try:
            from core.services.unified_data_manager import get_unified_data_manager
            unified_manager = get_unified_data_manager()
            if not unified_manager or not hasattr(unified_manager, 'data_source_router'):
                return routing_data

            router = unified_manager.data_source_router
            router_metrics = router.get_all_metrics()  # Dict[str, DataSourceMetrics]

            for source_id, metric in router_metrics.items():
                try:
                    routing_data[source_id] = {
                        'request_count': getattr(metric, 'total_requests', 0),
                        'success_count': getattr(metric, 'successful_requests', 0),
                        'error_count': getattr(metric, 'failed_requests', 0),
                        'avg_response_time': getattr(metric, 'avg_response_time_ms', 0.0),
                        'last_request_time': getattr(metric, 'last_request_time', 'N/A')
                    }
                except Exception as e:
                    logger.info(f" 获取路由统计失败 {source_id}: {e}")
        except Exception as e:
            logger.info(f" 获取路由统计失败: {e}")

        return routing_data

    def stop(self):
        """停止更新"""
        self._is_running = False


class StatusIndicator(QLabel):
    """状态指示器组件"""

    def __init__(self, initial_status="unknown", parent=None):
        super().__init__(parent)
        self.status = initial_status
        self.setFixedSize(16, 16)
        self.update_indicator()

    def set_status(self, status: str):
        """设置状态"""
        if self.status != status:
            self.status = status
            self.update_indicator()

    def update_indicator(self):
        """更新指示器显示"""
        colors = {
            "healthy": "#28a745",    # 绿色
            "warning": "#ffc107",    # 黄色
            "error": "#dc3545",      # 红色
            "unknown": "#6c757d"     # 灰色
        }

        color = colors.get(self.status, "#6c757d")

        # 创建圆形指示器
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, 12, 12)
        painter.end()

        self.setPixmap(pixmap)
        self.setToolTip(f"状态: {self.status}")


class MetricCard(QFrame):
    """指标卡片组件"""

    def __init__(self, title: str, value: str = "0", unit: str = "", parent=None):
        super().__init__(parent)
        self.title = title
        self.value = value
        self.unit = unit

        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 10px;
            }
            QFrame:hover {
                border-color: #007bff;
                background-color: #f8f9fa;
            }
        """)

        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # 标题
        title_label = QLabel(self.title)
        title_label.setFont(QFont("Arial", 10))
        title_label.setStyleSheet("color: #6c757d; margin-bottom: 5px;")
        layout.addWidget(title_label)

        # 数值
        value_layout = QHBoxLayout()
        self.value_label = QLabel(self.value)
        self.value_label.setFont(QFont("Arial", 20, QFont.Bold))
        self.value_label.setStyleSheet("color: #495057;")
        value_layout.addWidget(self.value_label)

        if self.unit:
            unit_label = QLabel(self.unit)
            unit_label.setFont(QFont("Arial", 12))
            unit_label.setStyleSheet("color: #6c757d; margin-left: 5px;")
            value_layout.addWidget(unit_label)

        value_layout.addStretch()
        layout.addLayout(value_layout)

    def update_value(self, value: str, color: str = "#495057"):
        """更新数值"""
        self.value_label.setText(value)
        self.value_label.setStyleSheet(f"color: {color};")


class NotificationItem(QListWidgetItem):
    """通知项目"""

    def __init__(self, level: str, message: str, timestamp: datetime = None):
        super().__init__()
        self.level = level
        self.message = message
        self.timestamp = timestamp or datetime.now()

        # 设置图标和颜色
        icons = {
            "info": "ℹ",
            "warning": "",
            "error": "",
            "success": ""
        }

        icon = icons.get(level, "ℹ")
        time_str = self.timestamp.strftime("%H:%M:%S")

        self.setText(f"{icon} [{time_str}] {message}")

        # 设置颜色
        colors = {
            "info": QColor(23, 162, 184),
            "warning": QColor(255, 193, 7),
            "error": QColor(220, 53, 69),
            "success": QColor(40, 167, 69)
        }

        if level in colors:
            self.setForeground(colors[level])


class DataSourceStatusWidget(QWidget):
    """数据源状态监控主组件"""

    # 信号定义
    status_changed = pyqtSignal(str, str)  # source_id, status
    notification_added = pyqtSignal(str, str, str)  # level, message, source_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.source_status = {}
        self.last_metrics = {}
        self.notifications = []
        self.max_notifications = 100

        self.init_ui()
        self.init_timers()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("数据源状态监控")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # 控制按钮
        self.auto_refresh_check = QCheckBox("自动刷新")
        self.auto_refresh_check.setChecked(True)
        self.auto_refresh_check.toggled.connect(self.toggle_auto_refresh)
        title_layout.addWidget(self.auto_refresh_check)

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_status)
        title_layout.addWidget(refresh_btn)

        clear_btn = QPushButton("清空通知")
        clear_btn.clicked.connect(self.clear_notifications)
        title_layout.addWidget(clear_btn)

        layout.addLayout(title_layout)

        # 创建标签页
        self.tab_widget = QTabWidget()

        # 1. 概览标签页
        self.overview_tab = self.create_overview_tab()
        self.tab_widget.addTab(self.overview_tab, "概览")

        # 2. 详细状态标签页
        self.details_tab = self.create_details_tab()
        self.tab_widget.addTab(self.details_tab, "详细状态")

        # 3. 通知中心标签页
        self.notifications_tab = self.create_notifications_tab()
        self.tab_widget.addTab(self.notifications_tab, "通知中心")

        # 4. 路由统计标签页
        self.routing_tab = self.create_routing_tab()
        self.tab_widget.addTab(self.routing_tab, "路由统计")

        layout.addWidget(self.tab_widget)

    def create_overview_tab(self):
        """创建概览标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 总体状态指标卡片
        cards_layout = QGridLayout()

        self.total_sources_card = MetricCard("数据源总数", "0", "个")
        cards_layout.addWidget(self.total_sources_card, 0, 0)

        self.healthy_sources_card = MetricCard("健康数据源", "0", "个")
        cards_layout.addWidget(self.healthy_sources_card, 0, 1)

        self.total_requests_card = MetricCard("总请求数", "0", "次")
        cards_layout.addWidget(self.total_requests_card, 0, 2)

        self.avg_response_time_card = MetricCard("平均响应时间", "0", "ms")
        cards_layout.addWidget(self.avg_response_time_card, 1, 0)

        self.success_rate_card = MetricCard("总体成功率", "0", "%")
        cards_layout.addWidget(self.success_rate_card, 1, 1)

        self.error_count_card = MetricCard("错误计数", "0", "次")
        cards_layout.addWidget(self.error_count_card, 1, 2)

        layout.addLayout(cards_layout)

        # 数据源状态列表
        status_group = QGroupBox("数据源状态")
        status_layout = QVBoxLayout(status_group)

        self.status_table = QTableWidget()
        self.status_table.setColumnCount(5)
        self.status_table.setHorizontalHeaderLabels([
            "数据源", "状态", "响应时间", "成功率", "最后检查"
        ])

        # 设置表格列宽
        header = self.status_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        status_layout.addWidget(self.status_table)
        layout.addWidget(status_group)

        return tab

    def create_details_tab(self):
        """创建详细状态标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 数据源选择
        selection_layout = QHBoxLayout()
        selection_layout.addWidget(QLabel("选择数据源:"))

        self.source_combo = QComboBox()
        self.source_combo.currentTextChanged.connect(self.update_source_details)
        selection_layout.addWidget(self.source_combo)

        selection_layout.addStretch()
        layout.addLayout(selection_layout)

        # 详细信息显示
        details_group = QGroupBox("详细信息")
        details_layout = QGridLayout(details_group)

        # 基本信息
        details_layout.addWidget(QLabel("插件ID:"), 0, 0)
        self.detail_plugin_id_label = QLabel("-")
        details_layout.addWidget(self.detail_plugin_id_label, 0, 1)

        details_layout.addWidget(QLabel("当前状态:"), 1, 0)
        self.detail_status_layout = QHBoxLayout()
        self.detail_status_indicator = StatusIndicator()
        self.detail_status_label = QLabel("-")
        self.detail_status_layout.addWidget(self.detail_status_indicator)
        self.detail_status_layout.addWidget(self.detail_status_label)
        self.detail_status_layout.addStretch()
        details_layout.addLayout(self.detail_status_layout, 1, 1)

        details_layout.addWidget(QLabel("支持资产:"), 2, 0)
        self.detail_assets_label = QLabel("-")
        details_layout.addWidget(self.detail_assets_label, 2, 1)

        details_layout.addWidget(QLabel("连接信息:"), 3, 0)
        self.detail_connection_label = QLabel("-")
        details_layout.addWidget(self.detail_connection_label, 3, 1)

        layout.addWidget(details_group)

        # 性能图表占位符
        chart_group = QGroupBox("性能趋势")
        chart_layout = QVBoxLayout(chart_group)

        self.chart_placeholder = QLabel("性能图表功能开发中...")
        self.chart_placeholder.setAlignment(Qt.AlignCenter)
        self.chart_placeholder.setMinimumHeight(200)
        self.chart_placeholder.setStyleSheet("""
            QLabel {
                border: 2px dashed #dee2e6;
                color: #6c757d;
                font-size: 14px;
            }
        """)
        chart_layout.addWidget(self.chart_placeholder)

        layout.addWidget(chart_group)

        return tab

    def create_notifications_tab(self):
        """创建通知中心标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 过滤控制
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("级别过滤:"))

        self.level_filter_combo = QComboBox()
        self.level_filter_combo.addItems(["全部", "信息", "警告", "错误", "成功"])
        self.level_filter_combo.currentTextChanged.connect(self.filter_notifications)
        filter_layout.addWidget(self.level_filter_combo)

        filter_layout.addStretch()

        # 通知统计
        self.notification_count_label = QLabel("通知总数: 0")
        filter_layout.addWidget(self.notification_count_label)

        layout.addLayout(filter_layout)

        # 通知列表
        self.notifications_list = QListWidget()
        layout.addWidget(self.notifications_list)

        return tab

    def create_routing_tab(self):
        """创建路由统计标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 路由统计表格
        routing_group = QGroupBox("路由统计")
        routing_layout = QVBoxLayout(routing_group)

        self.routing_table = QTableWidget()
        self.routing_table.setColumnCount(6)
        self.routing_table.setHorizontalHeaderLabels([
            "数据源", "路由次数", "成功次数", "失败次数", "成功率", "平均响应时间"
        ])

        # 设置表格列宽
        header = self.routing_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 6):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        routing_layout.addWidget(self.routing_table)
        layout.addWidget(routing_group)

        # 熔断器状态
        circuit_group = QGroupBox("熔断器状态")
        circuit_layout = QVBoxLayout(circuit_group)

        self.circuit_table = QTableWidget()
        self.circuit_table.setColumnCount(4)
        self.circuit_table.setHorizontalHeaderLabels([
            "数据源", "状态", "失败次数", "下次尝试时间"
        ])

        # 设置表格列宽
        header = self.circuit_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 4):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        circuit_layout.addWidget(self.circuit_table)
        layout.addWidget(circuit_group)

        return tab

    def init_timers(self):
        """初始化定时器"""
        # 状态刷新定时器
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.start(5000)  # 5秒间隔

        # 健康检查定时器
        self.health_check_timer = QTimer()
        self.health_check_timer.timeout.connect(self.check_all_health)
        self.health_check_timer.start(30000)  # 30秒间隔

    def toggle_auto_refresh(self, enabled: bool):
        """切换自动刷新"""
        if enabled:
            self.refresh_timer.start(5000)
            self.health_check_timer.start(30000)
        else:
            self.refresh_timer.stop()
            self.health_check_timer.stop()

    def refresh_status(self):
        """刷新状态 - 异步处理防止UI卡死"""
        try:
            logger.info("开始刷新数据源状态...")

            # 尝试从统一数据管理器获取数据
            router = None
            try:
                unified_manager = get_unified_data_manager()
                if unified_manager and hasattr(unified_manager, 'data_source_router'):
                    router = unified_manager.data_source_router
                    logger.info(f" 获取到数据源路由器，注册数据源数量: {len(router.data_sources) if router.data_sources else 0}")
                else:
                    logger.info("统一数据管理器不可用或缺少路由器")
            except ImportError:
                logger.info("无法导入统一数据管理器")
            except Exception as e:
                logger.info(f" 获取统一数据管理器失败: {e}")

            # 如果没有路由器，尝试从插件管理器获取数据
            if not router:
                logger.info("尝试从插件管理器获取数据源信息...")
                self._refresh_from_plugin_manager()
                return

            # 检查是否有正在运行的更新线程
            if hasattr(self, 'status_worker') and self.status_worker.isRunning():
                self.status_worker.stop()
                self.status_worker.wait(1000)

            # 创建异步状态更新工作线程
            self.status_worker = StatusUpdateWorker(router, self)

            # 连接信号
            self.status_worker.status_updated.connect(self._on_status_updated)
            self.status_worker.metrics_updated.connect(self._on_metrics_updated)
            self.status_worker.routing_updated.connect(self._on_routing_updated)
            self.status_worker.update_completed.connect(self._on_update_completed)
            self.status_worker.update_failed.connect(self._on_update_failed)

            # 启动异步更新
            self.status_worker.start()
            logger.info("异步状态更新线程已启动")

        except Exception as e:
            logger.info(f" 刷新状态失败: {e}")
            import traceback
            traceback.print_exc()
            logger.error(f"刷新状态失败: {str(e)}")
            self.add_notification("error", f"刷新状态失败: {str(e)}")

    def _refresh_from_plugin_manager(self):
        """从插件管理器刷新数据源信息（回退方案）"""
        try:
            logger.info("使用插件管理器作为数据源...")

            # 尝试从服务容器获取插件管理器和数据管理器
            plugin_manager = None
            data_manager = None
            try:
                from core.containers.service_container import get_service_container
                container = get_service_container()
                if container:
                    plugin_manager = getattr(container, 'plugin_manager', None)
                    data_manager = getattr(container, 'data_manager', None)
                    logger.info(f"从服务容器获取: plugin_manager={plugin_manager is not None} data_manager={data_manager is not None}")
            except Exception as e:
                logger.info(f" 从服务容器获取服务失败: {e}")

            # 创建模拟数据
            mock_status_data = {}
            mock_metrics_data = {}
            mock_routing_data = {}

            # 方案1：从插件管理器获取数据源插件
            if plugin_manager and hasattr(plugin_manager, 'get_data_source_plugins'):
                try:
                    ds_plugins = plugin_manager.get_data_source_plugins()
                    logger.info(f" 从插件管理器获取到 {len(ds_plugins)} 个数据源插件")

                    for source_id, plugin_info in ds_plugins.items():
                        try:
                            # 获取插件实例
                            plugin_instance = getattr(plugin_info, 'instance', None)
                            name = getattr(plugin_info, 'name', source_id)

                            # 尝试获取健康状态
                            is_healthy = True
                            response_time = 0.0
                            health_score = 0.8

                            if plugin_instance and hasattr(plugin_instance, 'health_check'):
                                try:
                                    health_result = plugin_instance.health_check()
                                    if hasattr(health_result, 'is_healthy'):
                                        is_healthy = health_result.is_healthy
                                    if hasattr(health_result, 'response_time'):
                                        response_time = health_result.response_time
                                    elif hasattr(health_result, 'response_time_ms'):
                                        response_time = health_result.response_time_ms
                                    health_score = 1.0 if is_healthy else 0.0
                                except Exception as e:
                                    logger.info(f"     健康检查失败 {source_id}: {e}")
                                    is_healthy = False
                                    health_score = 0.0

                            # 创建状态数据
                            mock_status_data[source_id] = {
                                'name': name,
                                'status': 'healthy' if is_healthy else 'error',
                                'last_update': datetime.now(),
                                'response_time': response_time,
                                'health_score': health_score
                            }

                            # 创建指标数据
                            mock_metrics_data[source_id] = {
                                'total_requests': 0,
                                'successful_requests': 0,
                                'failed_requests': 0,
                                'avg_response_time': response_time,
                                'success_rate': 1.0 if is_healthy else 0.0
                            }

                            logger.info(f"   添加数据源: {source_id} ({name}) - {mock_status_data[source_id]['status']}")
                        except Exception as e:
                            logger.info(f"   处理数据源 {source_id} 失败: {e}")
                except Exception as e:
                    logger.info(f" 获取数据源插件失败: {e}")

            # 方案2：从数据管理器获取插件数据源
            if data_manager and hasattr(data_manager, 'get_plugin_data_sources'):
                try:
                    plugin_sources = data_manager.get_plugin_data_sources()
                    logger.info(f" 从数据管理器获取到 {len(plugin_sources)} 个插件数据源")

                    for source_id, source_info in plugin_sources.items():
                        if source_id not in mock_status_data:  # 避免重复
                            try:
                                info = source_info.get('info', {})
                                stats = source_info.get('statistics', {})
                                health_status = source_info.get('health_status', False)

                                name = info.get('name', source_id)

                                # 创建状态数据
                                mock_status_data[source_id] = {
                                    'name': name,
                                    'status': 'healthy' if health_status else 'error',
                                    'last_update': datetime.now(),
                                    'response_time': stats.get('avg_response_time', 0.0),
                                    'health_score': 1.0 if health_status else 0.0
                                }

                                # 创建指标数据
                                mock_metrics_data[source_id] = {
                                    'total_requests': stats.get('total_requests', 0),
                                    'successful_requests': stats.get('successful_requests', 0),
                                    'failed_requests': stats.get('failed_requests', 0),
                                    'avg_response_time': stats.get('avg_response_time', 0.0),
                                    'success_rate': stats.get('success_rate', 0.0)
                                }

                                logger.info(f"   添加数据管理器数据源: {source_id} ({name}) - {mock_status_data[source_id]['status']}")
                            except Exception as e:
                                logger.info(f"   处理数据管理器数据源 {source_id} 失败: {e}")
                except Exception as e:
                    logger.info(f" 获取数据管理器插件数据源失败: {e}")

            # 如果没有找到任何数据源，创建示例数据
            if not mock_status_data:
                logger.info("创建示例数据源信息...")
                example_sources = [
                    ("akshare_stock", "AkShare股票数据源", True),
                    ("yahoo_finance", "Yahoo Finance数据源", False),
                    ("eastmoney_stock", "东方财富数据源", True)
                ]

                for source_id, name, is_healthy in example_sources:
                    mock_status_data[source_id] = {
                        'name': name,
                        'status': 'healthy' if is_healthy else 'offline',
                        'last_update': datetime.now(),
                        'response_time': 50.0 if is_healthy else 0.0,
                        'health_score': 0.9 if is_healthy else 0.0
                    }

                    mock_metrics_data[source_id] = {
                        'total_requests': 10 if is_healthy else 0,
                        'successful_requests': 10 if is_healthy else 0,
                        'failed_requests': 0,
                        'avg_response_time': 50.0 if is_healthy else 0.0,
                        'success_rate': 1.0 if is_healthy else 0.0
                    }

            # 创建路由数据
            mock_routing_data = {
                'total_requests': sum(m['total_requests'] for m in mock_metrics_data.values()),
                'successful_routes': sum(m['successful_requests'] for m in mock_metrics_data.values()),
                'failed_routes': sum(m['failed_requests'] for m in mock_metrics_data.values()),
                'avg_routing_time': sum(m['avg_response_time'] for m in mock_metrics_data.values()) / max(len(mock_metrics_data), 1)
            }

            # 更新UI
            self._on_status_updated(mock_status_data)
            self._on_metrics_updated(mock_metrics_data)
            self._on_routing_updated(mock_routing_data)
            self._on_update_completed()

            logger.info(f" 已更新 {len(mock_status_data)} 个数据源的状态信息")

        except Exception as e:
            logger.info(f" 从插件管理器刷新状态失败: {e}")
            traceback.print_exc()
            self.add_notification("error", f"从插件管理器刷新状态失败: {str(e)}")

    def _on_status_updated(self, status_data: dict):
        """状态数据更新回调（渐进式更新）"""
        try:
            for source_id, data in status_data.items():
                # 更新概览指标
                self._update_single_overview_metric(source_id, data)
                # 更新状态表格的单行
                self._update_single_status_row(source_id, data)

            QApplication.processEvents()  # 保持UI响应
        except Exception as e:
            logger.error(f"更新状态数据失败: {e}")

    def _on_metrics_updated(self, metrics: dict):
        """指标数据更新回调"""
        self.last_metrics = metrics

    def _on_routing_updated(self, routing_data: dict):
        """路由数据更新回调"""
        try:
            self._update_routing_table_async(routing_data)
        except Exception as e:
            logger.error(f"更新路由数据失败: {e}")

    def _on_update_completed(self):
        """异步更新完成回调"""
        logger.info("数据源状态异步更新完成")

    def _on_update_failed(self, error_message: str):
        """异步更新失败回调"""
        logger.error(f"异步状态更新失败: {error_message}")
        self.add_notification("error", f"状态更新失败: {error_message}")

    def _update_single_overview_metric(self, source_id: str, data: dict):
        """更新单个概览指标"""
        # 更新概览统计
        pass  # 这里可以添加具体的概览更新逻辑

    def _update_single_status_row(self, source_id: str, data: dict):
        """更新状态表格的单行"""
        try:
            # 查找对应的行
            for row in range(self.status_table.rowCount()):
                if self.status_table.item(row, 0) and self.status_table.item(row, 0).text() == data['name']:
                    # 更新状态
                    health_score = data['health_score']
                    if health_score > 0.7:
                        status_item = QTableWidgetItem("健康")
                        status_item.setForeground(QColor("#28a745"))
                    elif health_score > 0.3:
                        status_item = QTableWidgetItem("警告")
                        status_item.setForeground(QColor("#ffc107"))
                    else:
                        status_item = QTableWidgetItem("错误")
                        status_item.setForeground(QColor("#dc3545"))

                    self.status_table.setItem(row, 1, status_item)

                    # 更新响应时间
                    response_time = f"{data['avg_response_time']:.1f}ms"
                    self.status_table.setItem(row, 2, QTableWidgetItem(response_time))

                    # 更新成功率
                    success_rate = f"{data['success_rate']:.1%}"
                    self.status_table.setItem(row, 3, QTableWidgetItem(success_rate))

                    # 更新最后检查时间
                    last_check = datetime.now().strftime("%H:%M:%S")
                    self.status_table.setItem(row, 4, QTableWidgetItem(last_check))

                    break

        except Exception as e:
            logger.error(f"更新状态行失败: {e}")

    def _update_routing_table_async(self, routing_data: dict):
        """异步更新路由表格"""
        try:
            self.routing_table.setRowCount(len(routing_data))

            for row, (source_id, data) in enumerate(routing_data.items()):
                self.routing_table.setItem(row, 0, QTableWidgetItem(source_id))
                self.routing_table.setItem(row, 1, QTableWidgetItem(str(data['request_count'])))
                self.routing_table.setItem(row, 2, QTableWidgetItem(str(data['success_count'])))
                self.routing_table.setItem(row, 3, QTableWidgetItem(str(data['error_count'])))
                self.routing_table.setItem(row, 4, QTableWidgetItem(f"{data['avg_response_time']:.1f}ms"))
                self.routing_table.setItem(row, 5, QTableWidgetItem(str(data['last_request_time'])))

        except Exception as e:
            logger.error(f"更新路由表格失败: {e}")

    def update_overview_metrics(self, router):
        """更新概览指标"""
        try:
            data_sources = router.data_sources
            metrics = router.get_all_metrics()

            # 统计数据
            total_sources = len(data_sources)
            healthy_sources = 0
            total_requests = 0
            total_response_time = 0
            total_successes = 0
            error_count = 0

            for source_id, metric in metrics.items():
                if metric.health_score > 0.7:  # 健康分数阈值
                    healthy_sources += 1

                total_requests += metric.total_requests
                total_response_time += metric.avg_response_time_ms * metric.total_requests
                total_successes += int(metric.total_requests * metric.success_rate)
                error_count += metric.total_requests - int(metric.total_requests * metric.success_rate)

            # 计算平均值
            avg_response_time = (total_response_time / total_requests) if total_requests > 0 else 0
            success_rate = (total_successes / total_requests * 100) if total_requests > 0 else 0

            # 更新卡片
            self.total_sources_card.update_value(str(total_sources))
            self.healthy_sources_card.update_value(
                str(healthy_sources),
                "#28a745" if healthy_sources == total_sources else "#ffc107"
            )
            self.total_requests_card.update_value(str(total_requests))
            self.avg_response_time_card.update_value(f"{avg_response_time:.1f}")
            self.success_rate_card.update_value(
                f"{success_rate:.1f}",
                "#28a745" if success_rate >= 95 else "#ffc107" if success_rate >= 80 else "#dc3545"
            )
            self.error_count_card.update_value(
                str(error_count),
                "#28a745" if error_count == 0 else "#dc3545"
            )

        except Exception as e:
            logger.error(f"更新概览指标失败: {str(e)}")

    def update_status_table(self, router):
        """更新状态表格"""
        try:
            data_sources = router.data_sources
            metrics = router.get_all_metrics()

            self.status_table.setRowCount(len(data_sources))

            for row, (source_id, adapter) in enumerate(data_sources.items()):
                try:
                    plugin_info = adapter.get_plugin_info()
                    metric = metrics.get(source_id)

                    # 数据源名称
                    self.status_table.setItem(row, 0, QTableWidgetItem(plugin_info.name))

                    # 状态
                    if metric and metric.health_score > 0.7:
                        status_item = QTableWidgetItem("健康")
                        status_item.setForeground(QColor("#28a745"))
                    elif metric and metric.health_score > 0.3:
                        status_item = QTableWidgetItem("警告")
                        status_item.setForeground(QColor("#ffc107"))
                    else:
                        status_item = QTableWidgetItem("错误")
                        status_item.setForeground(QColor("#dc3545"))

                    self.status_table.setItem(row, 1, status_item)

                    # 响应时间
                    response_time = f"{metric.avg_response_time_ms:.1f}ms" if metric else "N/A"
                    self.status_table.setItem(row, 2, QTableWidgetItem(response_time))

                    # 成功率
                    success_rate = f"{metric.success_rate:.1%}" if metric else "N/A"
                    self.status_table.setItem(row, 3, QTableWidgetItem(success_rate))

                    # 最后检查时间
                    last_check = datetime.now().strftime("%H:%M:%S")
                    self.status_table.setItem(row, 4, QTableWidgetItem(last_check))

                except Exception as e:
                    logger.error(f"更新状态表格行失败: {str(e)}")

        except Exception as e:
            logger.error(f"更新状态表格失败: {str(e)}")

    def update_routing_statistics(self, router):
        """更新路由统计"""
        try:
            metrics = router.get_all_metrics()

            self.routing_table.setRowCount(len(metrics))

            for row, (source_id, metric) in enumerate(metrics.items()):
                try:
                    # 数据源名称
                    self.routing_table.setItem(row, 0, QTableWidgetItem(source_id))

                    # 路由次数
                    self.routing_table.setItem(row, 1, QTableWidgetItem(str(metric.total_requests)))

                    # 成功次数
                    success_count = int(metric.total_requests * metric.success_rate)
                    self.routing_table.setItem(row, 2, QTableWidgetItem(str(success_count)))

                    # 失败次数
                    failure_count = metric.total_requests - success_count
                    self.routing_table.setItem(row, 3, QTableWidgetItem(str(failure_count)))

                    # 成功率
                    self.routing_table.setItem(row, 4, QTableWidgetItem(f"{metric.success_rate:.1%}"))

                    # 平均响应时间
                    self.routing_table.setItem(row, 5, QTableWidgetItem(f"{metric.avg_response_time_ms:.1f}ms"))

                except Exception as e:
                    logger.error(f"更新路由统计行失败: {str(e)}")

        except Exception as e:
            logger.error(f"更新路由统计失败: {str(e)}")

    def update_circuit_breaker_status(self, router):
        """更新熔断器状态"""
        try:
            circuit_breakers = router.circuit_breakers

            self.circuit_table.setRowCount(len(circuit_breakers))

            for row, (source_id, cb) in enumerate(circuit_breakers.items()):
                try:
                    # 数据源名称
                    self.circuit_table.setItem(row, 0, QTableWidgetItem(source_id))

                    # 状态
                    state_map = {
                        "CLOSED": " 关闭",
                        "OPEN": " 开启",
                        "HALF_OPEN": " 半开"
                    }
                    state_text = state_map.get(cb.state.value, cb.state.value)
                    self.circuit_table.setItem(row, 1, QTableWidgetItem(state_text))

                    # 失败次数
                    self.circuit_table.setItem(row, 2, QTableWidgetItem(str(cb.failure_count)))

                    # 下次尝试时间
                    if hasattr(cb, 'next_attempt_time') and cb.next_attempt_time:
                        next_time = cb.next_attempt_time.strftime("%H:%M:%S")
                    else:
                        next_time = "立即"
                    self.circuit_table.setItem(row, 3, QTableWidgetItem(next_time))

                except Exception as e:
                    logger.error(f"更新熔断器状态行失败: {str(e)}")

        except Exception as e:
            logger.error(f"更新熔断器状态失败: {str(e)}")

    def update_source_combo(self, router):
        """更新数据源选择框"""
        try:
            current_text = self.source_combo.currentText()
            self.source_combo.clear()

            for source_id in router.data_sources.keys():
                self.source_combo.addItem(source_id)

            # 恢复之前的选择
            if current_text:
                index = self.source_combo.findText(current_text)
                if index >= 0:
                    self.source_combo.setCurrentIndex(index)

        except Exception as e:
            logger.error(f"更新数据源选择框失败: {str(e)}")

    def update_source_details(self, source_id: str):
        """更新数据源详情"""
        if not source_id:
            return

        try:

            unified_manager = get_unified_data_manager()
            if not unified_manager or not hasattr(unified_manager, 'data_source_router'):
                return

            router = unified_manager.data_source_router
            if source_id not in router.data_sources:
                return

            adapter = router.data_sources[source_id]
            plugin_info = adapter.get_plugin_info()
            metrics = router.get_all_metrics()
            metric = metrics.get(source_id)

            # 更新详情显示
            self.detail_plugin_id_label.setText(plugin_info.id)

            # 状态
            if metric and metric.health_score > 0.7:
                self.detail_status_indicator.set_status("healthy")
                self.detail_status_label.setText("健康")
            elif metric and metric.health_score > 0.3:
                self.detail_status_indicator.set_status("warning")
                self.detail_status_label.setText("警告")
            else:
                self.detail_status_indicator.set_status("error")
                self.detail_status_label.setText("错误")

            # 支持资产
            assets = ", ".join([asset.value for asset in plugin_info.supported_asset_types])
            self.detail_assets_label.setText(assets)

            # 连接信息
            connection_info = f"响应时间: {metric.avg_response_time_ms:.1f}ms, 成功率: {metric.success_rate:.1%}" if metric else "无数据"
            self.detail_connection_label.setText(connection_info)

        except Exception as e:
            logger.error(f"更新数据源详情失败: {str(e)}")

    def check_all_health(self):
        """检查所有数据源健康状态"""
        try:

            unified_manager = get_unified_data_manager()
            if not unified_manager or not hasattr(unified_manager, 'data_source_router'):
                return

            router = unified_manager.data_source_router

            for source_id, adapter in router.data_sources.items():
                try:
                    health_result = adapter.health_check()

                    # 检查状态变化
                    old_status = self.source_status.get(source_id, "unknown")
                    new_status = "healthy" if health_result.is_healthy else "error"

                    if old_status != new_status:
                        self.source_status[source_id] = new_status
                        self.status_changed.emit(source_id, new_status)

                        # 添加状态变化通知
                        level = "success" if new_status == "healthy" else "error"
                        message = f"数据源 {source_id} 状态变化: {old_status} -> {new_status}"
                        self.add_notification(level, message, source_id)

                except Exception as e:
                    logger.error(f"检查数据源 {source_id} 健康状态失败: {str(e)}")
                    self.add_notification("error", f"检查数据源 {source_id} 健康状态失败: {str(e)}", source_id)

        except Exception as e:
            logger.error(f"检查所有健康状态失败: {str(e)}")

    def add_notification(self, level: str, message: str, source_id: str = None):
        """添加通知"""
        try:
            # 限制通知数量
            if len(self.notifications) >= self.max_notifications:
                self.notifications = self.notifications[-(self.max_notifications-1):]

            notification = {
                "level": level,
                "message": message,
                "source_id": source_id,
                "timestamp": datetime.now()
            }

            self.notifications.append(notification)

            # 更新通知列表
            self.refresh_notifications_list()

            # 发送信号
            self.notification_added.emit(level, message, source_id or "")

        except Exception as e:
            logger.error(f"添加通知失败: {str(e)}")

    def refresh_notifications_list(self):
        """刷新通知列表"""
        try:
            self.notifications_list.clear()

            # 应用过滤
            filter_level = self.level_filter_combo.currentText()
            level_map = {"信息": "info", "警告": "warning", "错误": "error", "成功": "success"}

            filtered_notifications = self.notifications
            if filter_level != "全部" and filter_level in level_map:
                target_level = level_map[filter_level]
                filtered_notifications = [n for n in self.notifications if n["level"] == target_level]

            # 按时间倒序显示
            for notification in reversed(filtered_notifications):
                item = NotificationItem(
                    notification["level"],
                    notification["message"],
                    notification["timestamp"]
                )
                self.notifications_list.addItem(item)

            # 更新计数
            self.notification_count_label.setText(f"通知总数: {len(filtered_notifications)}")

        except Exception as e:
            logger.error(f"刷新通知列表失败: {str(e)}")

    def filter_notifications(self):
        """过滤通知"""
        self.refresh_notifications_list()

    def clear_notifications(self):
        """清空通知"""
        self.notifications.clear()
        self.notifications_list.clear()
        self.notification_count_label.setText("通知总数: 0")
        self.add_notification("info", "通知已清空")


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    widget = DataSourceStatusWidget()
    widget.show()

    sys.exit(app.exec_())
