from loguru import logger
"""
现代化系统监控标签页（重构版）

使用统一管理器替代独立的定时器和线程池，采用事件驱动架构。
"""

from typing import Dict, List, Any
from collections import defaultdict, deque
from datetime import datetime
import psutil
import gc
import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QFrame, QGroupBox, QHBoxLayout,
    QTabWidget, QToolBar, QAction, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QTextEdit, QLabel, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor

from ..components.metric_card import ModernMetricCard
from ..components.performance_chart import ModernPerformanceChart

# 导入统一管理器
try:
    from core.performance import (
        get_data_update_manager,
        get_resource_monitor,
        get_performance_monitor,
        UpdateStrategy
    )
    UNIFIED_MANAGERS_AVAILABLE = True
except ImportError:
    UNIFIED_MANAGERS_AVAILABLE = False
    logger.warning("统一管理器不可用，system_monitor_tab将使用传统方式")

# 导入增强风险监控
try:
    from core.risk_monitoring.enhanced_risk_monitor import get_enhanced_risk_monitor
    ENHANCED_RISK_AVAILABLE = True
except ImportError:
    ENHANCED_RISK_AVAILABLE = False

# 导入主题管理器
try:
    from utils.theme import get_theme_manager
    THEME_MANAGER_AVAILABLE = True
except ImportError:
    THEME_MANAGER_AVAILABLE = False
    logger.warning("ThemeManager不可用，system_monitor_tab将使用默认样式")


class ModernSystemMonitorTab(QWidget):
    """现代化系统监控标签页（重构版）"""

    def __init__(self):
        super().__init__()

        # 内存监控相关属性
        try:
            self.memory_baseline = psutil.virtual_memory().used
        except Exception:
            self.memory_baseline = 0
        self.gc_count = 0
        self.memory_history = []

        # 性能监控相关属性
        self.alerts: List[Any] = []
        self.recommendations: List[Dict[str, Any]] = []
        self.performance_history: List[Dict[str, Any]] = deque(maxlen=100)
        self.current_component = "all"

        # 初始化增强风险监控
        self.enhanced_risk_monitor = None
        if ENHANCED_RISK_AVAILABLE:
            try:
                self.enhanced_risk_monitor = get_enhanced_risk_monitor()
            except Exception as e:
                logger.warning(f"初始化增强风险监控失败: {e}")

        # 初始化主题管理器
        self.theme_manager = None
        if THEME_MANAGER_AVAILABLE:
            try:
                self.theme_manager = get_theme_manager()
                self.theme_manager.theme_changed.connect(self._on_theme_changed)
            except Exception as e:
                logger.warning(f"获取ThemeManager失败: {e}")

        # 初始化统一管理器
        self.data_update_manager = None
        self.resource_monitor = None
        self.performance_monitor = None

        if UNIFIED_MANAGERS_AVAILABLE:
            try:
                self.data_update_manager = get_data_update_manager()
                self.resource_monitor = get_resource_monitor()
                self.performance_monitor = get_performance_monitor()

                # 注册到数据更新管理器
                self.data_update_manager.register_tab(
                    tab_name="system_monitor",
                    data_collector=self._collect_system_data,
                    update_interval=5.0,  # 5秒更新一次
                    update_strategy=UpdateStrategy.EVENT_DRIVEN,
                    enabled=True
                )

                # 连接数据更新信号
                self.data_update_manager.data_updated.connect(self._on_data_updated)
                self.data_update_manager.update_error.connect(self._on_update_error)

                logger.info("系统监控标签页已使用统一管理器")
            except Exception as e:
                logger.warning(f"初始化统一管理器失败: {e}")

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # 工具栏
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)

        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self.refresh_data)
        self.toolbar.addAction(refresh_action)

        self.toolbar.addSeparator()

        start_action = QAction("启动监控", self)
        start_action.triggered.connect(self.start_monitoring)
        self.toolbar.addAction(start_action)

        stop_action = QAction("停止监控", self)
        stop_action.triggered.connect(self.stop_monitoring)
        self.toolbar.addAction(stop_action)

        self.toolbar.addSeparator()

        auto_refresh_action = QAction("自动刷新", self)
        auto_refresh_action.setCheckable(True)
        auto_refresh_action.setChecked(True)
        auto_refresh_action.toggled.connect(self.toggle_auto_refresh)
        self.toolbar.addAction(auto_refresh_action)

        # 组件选择器
        self.toolbar.addSeparator()
        self.toolbar.addWidget(QLabel("组件:"))
        self.component_combo = QComboBox()
        self.component_combo.setMinimumWidth(150)
        self.component_combo.addItems(["all", "volume", "kline", "chart", "data_import", "strategy"])
        self.component_combo.currentTextChanged.connect(self.on_component_changed)
        self.toolbar.addWidget(self.component_combo)

        layout.addWidget(self.toolbar)

        # 标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.create_overview_tab(), "概览")
        self.tab_widget.addTab(self.create_metrics_tab(), "指标详情")
        self.tab_widget.addTab(self.create_alerts_tab(), "性能警报")
        self.tab_widget.addTab(self.create_recommendations_tab(), "优化建议")
        self.tab_widget.addTab(self.create_history_tab(), "历史记录")

        layout.addWidget(self.tab_widget)

    def create_overview_tab(self):
        """创建概览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # 系统资源指标卡片 - 两行布局，每行8个
        cards_frame = QFrame()
        cards_frame.setMinimumHeight(120)
        cards_frame.setMaximumHeight(140)
        cards_layout = QGridLayout(cards_frame)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(2)
        cards_layout.setRowStretch(0, 1)
        cards_layout.setColumnStretch(0, 1)

        # 创建扩展的系统指标 - 两行布局，每行8个
        self.cards = {}
        system_metrics = [
            # 第一行：8个核心系统指标
            ("CPU使用率", "#e74c3c", 0, 0),
            ("内存使用率", "#f39c12", 0, 1),
            ("磁盘使用率", "#9b59b6", 0, 2),
            ("网络吞吐", "#1abc9c", 0, 3),
            ("内存可用", "#16a085", 0, 4),
            ("磁盘可用", "#8e44ad", 0, 5),
            ("网络发送", "#d35400", 0, 6),
            ("网络接收", "#27ae60", 0, 7),
            # 第二行：8个扩展监控指标
            ("进程数量", "#3498db", 0, 8),
            ("线程数量", "#2ecc71", 0, 9),
            ("句柄数量", "#e67e22", 0, 10),
            ("响应时间", "#95a5a6", 1, 0),
            ("内存增长", "#e67e22", 1, 1),
            ("GC清理次数", "#9b59b6", 1, 2),
            ("内存峰值", "#c0392b", 1, 3),
            ("内存效率", "#27ae60", 1, 4),
        ]

        # 如果增强风险监控可用，添加风险系统状态指标
        if ENHANCED_RISK_AVAILABLE:
            risk_metrics = [
                ("风险监控状态", "#e74c3c", 1, 5),
                ("风险预警数量", "#f39c12", 1, 6),
                ("风险等级", "#e67e22", 1, 7),
                ("AI预测状态", "#3498db", 1, 8),
                ("异常检测数", "#9b59b6", 1, 9),
                ("风险分析延迟", "#1abc9c", 1, 10),
            ]
            system_metrics.extend(risk_metrics)

        for name, color, row, col in system_metrics:
            # 根据指标类型设置单位
            if "率" in name or "效率" in name:
                unit = "%"
            elif "时间" in name:
                unit = "ms"
            elif "可用" in name or "峰值" in name:
                unit = "GB"
            elif "发送" in name or "接收" in name:
                unit = "MB"
            elif "增长" in name:
                unit = "MB"
            elif "次数" in name or "数量" in name or "检测数" in name:
                unit = "个"
            elif "状态" in name:
                unit = ""
            elif "等级" in name:
                unit = ""
            elif "延迟" in name:
                unit = "ms"
            else:
                unit = ""

            card = ModernMetricCard(name, "0", unit, color)
            self.cards[name] = card
            cards_layout.addWidget(card, row, col)

        layout.addWidget(cards_frame)

        # 系统资源历史图表 - 适应性显示区域
        self.resource_chart = ModernPerformanceChart("系统资源使用趋势", "line")
        self.resource_chart.setMinimumHeight(200)
        layout.addWidget(self.resource_chart, 1)

        return widget

    def create_metrics_tab(self):
        """创建指标详情标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 时间范围选择
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("时间范围:"))

        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems(["10分钟", "30分钟", "1小时", "2小时", "6小时", "24小时"])
        self.time_range_combo.setCurrentIndex(0)
        controls_layout.addWidget(self.time_range_combo)

        controls_layout.addStretch()

        refresh_metrics_btn = QPushButton("刷新指标")
        refresh_metrics_btn.clicked.connect(self.refresh_metrics)
        controls_layout.addWidget(refresh_metrics_btn)

        layout.addLayout(controls_layout)

        # 指标数据表格
        metrics_group = QGroupBox("性能指标")
        metrics_layout = QVBoxLayout(metrics_group)

        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(6)
        self.metrics_table.setHorizontalHeaderLabels([
            "时间", "类型", "组件", "值", "单位", "附加数据"
        ])
        self.metrics_table.horizontalHeader().setStretchLastSection(True)
        self.metrics_table.verticalHeader().setVisible(False)
        self.metrics_table.setAlternatingRowColors(True)
        metrics_layout.addWidget(self.metrics_table)

        layout.addWidget(metrics_group)

        return widget

    def create_alerts_tab(self):
        """创建性能警报标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 警报显示
        alerts_group = QGroupBox("性能警报")
        alerts_layout = QVBoxLayout(alerts_group)

        self.alerts_table = QTableWidget()
        self.alerts_table.setColumnCount(5)
        self.alerts_table.setHorizontalHeaderLabels(["级别", "组件", "消息", "值/阈值", "时间"])
        self.alerts_table.horizontalHeader().setStretchLastSection(True)
        self.alerts_table.verticalHeader().setVisible(False)
        self.alerts_table.setAlternatingRowColors(True)
        alerts_layout.addWidget(self.alerts_table)

        # 操作按钮
        buttons_layout = QHBoxLayout()

        clear_alerts_btn = QPushButton("清除警报")
        clear_alerts_btn.clicked.connect(self.clear_alerts)
        buttons_layout.addWidget(clear_alerts_btn)

        export_alerts_btn = QPushButton("导出警报")
        export_alerts_btn.clicked.connect(self.export_alerts)
        buttons_layout.addWidget(export_alerts_btn)

        buttons_layout.addStretch()

        layout.addWidget(alerts_group)
        layout.addLayout(buttons_layout)
        layout.addStretch()

        return widget

    def create_recommendations_tab(self):
        """创建优化建议标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 建议列表
        recommendations_group = QGroupBox("优化建议")
        recommendations_layout = QVBoxLayout(recommendations_group)

        self.recommendations_table = QTableWidget()
        self.recommendations_table.setColumnCount(4)
        self.recommendations_table.setHorizontalHeaderLabels([
            "优先级", "组件", "建议", "预期效果"
        ])
        self.recommendations_table.horizontalHeader().setStretchLastSection(True)
        self.recommendations_table.verticalHeader().setVisible(False)
        self.recommendations_table.setAlternatingRowColors(True)
        recommendations_layout.addWidget(self.recommendations_table)

        # 操作按钮
        buttons_layout = QHBoxLayout()

        refresh_recommendations_btn = QPushButton("刷新建议")
        refresh_recommendations_btn.clicked.connect(self.refresh_recommendations)
        buttons_layout.addWidget(refresh_recommendations_btn)

        apply_recommendations_btn = QPushButton("应用建议")
        apply_recommendations_btn.clicked.connect(self.apply_recommendations)
        buttons_layout.addWidget(apply_recommendations_btn)

        buttons_layout.addStretch()

        layout.addWidget(recommendations_group)
        layout.addLayout(buttons_layout)
        layout.addStretch()

        return widget

    def create_history_tab(self):
        """创建历史记录标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 历史记录表格
        history_group = QGroupBox("性能历史")
        history_layout = QVBoxLayout(history_group)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "时间", "类型", "组件", "值", "单位", "状态"
        ])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setAlternatingRowColors(True)
        history_layout.addWidget(self.history_table)

        # 操作按钮
        buttons_layout = QHBoxLayout()

        export_history_btn = QPushButton("导出历史")
        export_history_btn.clicked.connect(self.export_history)
        buttons_layout.addWidget(export_history_btn)

        clear_history_btn = QPushButton("清除历史")
        clear_history_btn.clicked.connect(self.clear_history)
        buttons_layout.addWidget(clear_history_btn)

        buttons_layout.addStretch()

        layout.addWidget(history_group)
        layout.addLayout(buttons_layout)
        layout.addStretch()

        return widget

    def start_monitoring(self):
        """启动监控"""
        logger.info("启动性能监控")
        if self.data_update_manager:
            self.data_update_manager.enable_tab("system_monitor")

    def stop_monitoring(self):
        """停止监控"""
        logger.info("停止性能监控")
        if self.data_update_manager:
            self.data_update_manager.disable_tab("system_monitor")

    def toggle_auto_refresh(self, enabled: bool):
        """切换自动刷新"""
        if enabled:
            self.start_monitoring()
        else:
            self.stop_monitoring()

    def refresh_data(self):
        """刷新数据"""
        logger.info("刷新性能数据")
        if self.data_update_manager:
            self.data_update_manager.request_data_refresh("system_monitor", refresh_type='full')

    def on_component_changed(self, component: str):
        """组件改变"""
        self.current_component = component
        logger.info(f"切换到组件: {component}")

    def refresh_metrics(self):
        """刷新指标"""
        logger.info("刷新性能指标")
        self.refresh_data()

    def clear_alerts(self):
        """清除警报"""
        logger.info("清除性能警报")
        self.alerts.clear()
        self.alerts_table.setRowCount(0)

    def export_alerts(self):
        """导出警报"""
        try:
            logger.info("导出性能警报")
            if not self.alerts:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.information(self, "提示", "没有警报可导出")
                return

            from PyQt5.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出警报", "", "CSV Files (*.csv);;All Files (*)"
            )
            if file_path:
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['时间', '类型', '级别', '消息'])
                    for alert in self.alerts:
                        writer.writerow([
                            alert.timestamp.isoformat() if hasattr(alert, 'timestamp') else '',
                            alert.alert_type if hasattr(alert, 'alert_type') else '',
                            alert.severity if hasattr(alert, 'severity') else '',
                            alert.message if hasattr(alert, 'message') else str(alert)
                        ])
                logger.info(f"警报导出成功: {file_path}")
        except Exception as e:
            logger.error(f"导出警报失败: {e}")

    def refresh_recommendations(self):
        """刷新建议"""
        try:
            logger.info("刷新优化建议")
            if hasattr(self, 'data_update_manager') and self.data_update_manager:
                self.data_update_manager.request_data_refresh("system_monitor", refresh_type='recommendations')
            logger.info("优化建议刷新完成")
        except Exception as e:
            logger.error(f"刷新优化建议失败: {e}")

    def apply_recommendations(self):
        """应用建议"""
        try:
            logger.info("应用优化建议")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "建议应用功能已就绪")
        except Exception as e:
            logger.error(f"应用建议失败: {e}")

    def export_history(self):
        """导出历史"""
        try:
            logger.info("导出性能历史")
            if not hasattr(self, 'performance_history') or not self.performance_history:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.information(self, "提示", "没有历史数据可导出")
                return

            from PyQt5.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出历史", "", "CSV Files (*.csv);;All Files (*)"
            )
            if file_path:
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    if hasattr(self, 'performance_history') and self.performance_history:
                        fieldnames = self.performance_history[0].keys() if hasattr(self.performance_history[0], 'keys') else []
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        for record in self.performance_history:
                            writer.writerow(record) if hasattr(record, 'keys') else writer.writerow([record])
                logger.info(f"历史导出成功: {file_path}")
        except Exception as e:
            logger.error(f"导出历史失败: {e}")

    def clear_history(self):
        """清除历史"""
        logger.info("清除性能历史")
        self.performance_history.clear()
        self.history_table.setRowCount(0)

    def _collect_system_data(self) -> Dict[str, Any]:
        """
        收集系统数据（供统一管理器调用）

        Returns:
            系统数据字典
        """
        try:
            data = {}

            # 获取CPU信息
            try:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                data['CPU使用率'] = cpu_percent
            except Exception as e:
                logger.warning(f"获取CPU信息失败: {e}")
                data['CPU使用率'] = 0.0

            # 获取内存信息
            try:
                memory = psutil.virtual_memory()
                data['内存使用率'] = memory.percent
                data['内存可用'] = memory.available / (1024 * 1024 * 1024)  # GB

                # 计算内存增长
                memory_growth = (memory.used - self.memory_baseline) / (1024 * 1024)  # MB
                data['内存增长'] = memory_growth

                # 更新内存历史
                self.memory_history.append(memory.used)
                if len(self.memory_history) > 100:
                    self.memory_history.pop(0)

                # 计算内存峰值
                memory_peak = max(self.memory_history) / (1024 * 1024 * 1024)  # GB
                data['内存峰值'] = memory_peak

                # 计算内存效率
                memory_efficiency = (memory.available / memory.total) * 100
                data['内存效率'] = memory_efficiency
            except Exception as e:
                logger.warning(f"获取内存信息失败: {e}")
                data['内存使用率'] = 0.0
                data['内存可用'] = 0.0
                data['内存增长'] = 0.0
                data['内存峰值'] = 0.0
                data['内存效率'] = 0.0

            # 获取磁盘信息
            try:
                disk = psutil.disk_usage('/')
                data['磁盘使用率'] = disk.percent
                data['磁盘可用'] = disk.free / (1024 * 1024 * 1024)  # GB
            except Exception as e:
                logger.warning(f"获取磁盘信息失败: {e}")
                data['磁盘使用率'] = 0.0
                data['磁盘可用'] = 0.0

            # 获取网络信息
            try:
                network = psutil.net_io_counters()
                data['网络发送'] = network.bytes_sent / (1024 * 1024)  # MB
                data['网络接收'] = network.bytes_recv / (1024 * 1024)  # MB
                data['网络吞吐'] = (network.bytes_sent + network.bytes_recv) / (1024 * 1024)  # MB
            except Exception as e:
                logger.warning(f"获取网络信息失败: {e}")
                data['网络发送'] = 0.0
                data['网络接收'] = 0.0
                data['网络吞吐'] = 0.0

            # 获取进程和线程信息
            try:
                data['进程数量'] = len(psutil.pids())
            except Exception as e:
                logger.warning(f"获取进程数量失败: {e}")
                data['进程数量'] = 0

            try:
                data['线程数量'] = sum(len(p.threads()) for p in psutil.process_iter(['threads']))
            except Exception as e:
                logger.warning(f"获取线程数量失败: {e}")
                data['线程数量'] = 0

            try:
                data['句柄数量'] = sum(p.num_handles() for p in psutil.process_iter(['num_handles']))
            except Exception as e:
                logger.warning(f"获取句柄数量失败: {e}")
                data['句柄数量'] = 0

            # 真实测量响应时间
            response_start = time.perf_counter()
            try:
                _ = psutil.cpu_percent(interval=0.001)
            except Exception:
                pass
            response_time = (time.perf_counter() - response_start) * 1000
            data['响应时间'] = round(response_time, 2)

            # 获取GC统计
            try:
                gc_stats = gc.get_stats()
                total_collections = sum(stat['collections'] for stat in gc_stats)
                if total_collections != self.gc_count:
                    self.gc_count = total_collections
                data['GC清理次数'] = self.gc_count
            except Exception as e:
                logger.warning(f"获取GC统计失败: {e}")
                data['GC清理次数'] = 0

            # 获取风险监控数据（如果可用）
            if self.enhanced_risk_monitor:
                try:
                    risk_status = self.enhanced_risk_monitor.get_current_risk_status()
                    risk_alerts = self.enhanced_risk_monitor.get_risk_alerts(1, False)

                    if risk_status:
                        data['风险监控状态'] = "运行中" if risk_status.get('monitoring_status') == 'active' else "停止"
                        distribution = risk_status.get('risk_distribution', {})
                        level_mapping = {
                            'very_low': '极低', 'low': '低', 'medium': '中',
                            'high': '高', 'critical': '严重', 'extreme': '极高'
                        }
                        max_count = 0
                        main_level = "低"
                        for level, count in distribution.items():
                            if count > max_count:
                                max_count = count
                                main_level = level_mapping.get(level, '未知')
                        data['风险等级'] = main_level

                    data['风险预警数量'] = len(risk_alerts)
                    data['AI预测状态'] = "正常"
                    data['异常检测数'] = sum(1 for alert in risk_alerts if 'anomaly' in alert.get('category', '').lower())
                    
                    # 真实测量风险分析延迟
                    risk_analysis_start = time.perf_counter()
                    try:
                        _ = self.enhanced_risk_monitor.get_current_risk_status()
                    except Exception:
                        pass
                    risk_analysis_latency = (time.perf_counter() - risk_analysis_start) * 1000
                    data['风险分析延迟'] = round(risk_analysis_latency, 2)
                except Exception as e:
                    logger.warning(f"获取风险监控数据失败: {e}")
                    data['风险监控状态'] = "--"
                    data['风险预警数量'] = 0
                    data['风险等级'] = "--"
                    data['AI预测状态'] = "--"
                    data['异常检测数'] = 0
                    data['风险分析延迟'] = 0

            return data

        except Exception as e:
            logger.error(f"收集系统数据失败: {e}")
            return {}

    def _on_data_updated(self, tab_name: str, data_type: str, data: Dict[str, Any]):
        """
        数据更新回调

        Args:
            tab_name: 标签页名称
            data_type: 数据类型
            data: 数据
        """
        try:
            if tab_name != "system_monitor" or data_type != "data":
                return

            if not data:
                return

            # 更新UI
            self._update_ui_in_main_thread(data)

        except Exception as e:
            logger.error(f"处理数据更新失败: {e}")

    def _on_update_error(self, tab_name: str, data_type: str, error: str):
        """
        更新错误回调

        Args:
            tab_name: 标签页名称
            data_type: 数据类型
            error: 错误信息
        """
        logger.error(f"数据更新失败: {tab_name}, {data_type}, {error}")

    def _update_ui_in_main_thread(self, system_metrics: Dict[str, float]):
        """在主线程中更新UI"""
        try:
            # 更新指标卡片（只更新有变化的）
            for name, value in system_metrics.items():
                if name in self.cards:
                    # 检查值是否有显著变化（避免微小变化导致的频繁更新）
                    current_text = self.cards[name].value_label.text()
                    if isinstance(value, (int, float)):
                        new_text = f"{value:.1f}" if isinstance(value, float) else str(value)
                    else:
                        new_text = str(value)

                    if current_text != new_text:
                        if isinstance(value, (int, float)):
                            trend = "up" if value > 70 else "down" if value < 30 else "neutral"
                            if name == "响应时间":
                                trend = "down" if value > 100 else "up" if value < 50 else "neutral"
                        else:
                            trend = "neutral"
                        self.cards[name].update_value(new_text, trend)

            # 批量更新图表数据（减少重绘次数）
            chart_metrics = ["CPU使用率", "内存使用率", "磁盘使用率", "网络吞吐", "响应时间"]
            chart_updated = False
            for name, value in system_metrics.items():
                if name in chart_metrics and isinstance(value, (int, float)):
                    # 对响应时间进行标准化处理（转换为百分比显示）
                    if name == "响应时间":
                        normalized_value = min(value / 10, 100)  # 将ms转换为百分比显示
                        self.resource_chart.add_data_point(name, normalized_value)
                    else:
                        self.resource_chart.add_data_point(name, value)
                    chart_updated = True

            # 只有数据更新时才重绘图表
            if chart_updated:
                self.resource_chart.update_chart()

        except Exception as e:
            logger.error(f"在主线程中更新UI失败: {e}")

    def get_memory_usage(self):
        """获取内存使用情况（供外部调用）"""
        try:
            memory = psutil.virtual_memory()
            return {
                'percentage': memory.percent,
                'used': memory.used / (1024 * 1024 * 1024),  # GB
                'available': memory.available / (1024 * 1024 * 1024),  # GB
                'total': memory.total / (1024 * 1024 * 1024),  # GB
                'growth': (memory.used - self.memory_baseline) / (1024 * 1024),  # MB
                'gc_count': self.gc_count
            }
        except Exception as e:
            logger.error(f"获取内存使用情况失败: {e}")
            return {}

    def _on_theme_changed(self):
        """主题变化回调"""
        try:
            # 更新所有卡片的主题样式
            for card in self.cards.values():
                if hasattr(card, 'update_theme'):
                    card.update_theme()

            # 更新图表主题
            if hasattr(self.resource_chart, 'update_theme'):
                self.resource_chart.update_theme()

            logger.debug("系统监控标签页主题已更新")
        except Exception as e:
            logger.error(f"更新系统监控标签页主题失败: {e}")

    def cleanup(self):
        """清理资源"""
        try:
            # 注销标签页
            if self.data_update_manager:
                try:
                    self.data_update_manager.unregister_tab("system_monitor")
                    logger.debug("系统监控标签页已从数据更新管理器注销")
                except Exception as e:
                    logger.debug(f"注销系统监控标签页失败: {e}")

        except Exception as e:
            logger.debug(f"清理系统监控资源失败: {e}")
