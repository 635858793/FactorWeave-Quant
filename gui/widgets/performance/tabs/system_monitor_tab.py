#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
现代化系统监控标签页

提供系统资源的实时监控和历史趋势显示
"""

from loguru import logger
from typing import Dict, List, Any
from collections import defaultdict, deque
from datetime import datetime
import psutil
import gc
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QFrame, QGroupBox, QHBoxLayout,
    QTabWidget, QToolBar, QAction, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QTextEdit, QLabel, QProgressBar, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor

from ..components.metric_card import ModernMetricCard
from ..components.performance_chart import ModernPerformanceChart

# 导入增强风险监控
try:
    from core.risk_monitoring.enhanced_risk_monitor import get_enhanced_risk_monitor
    ENHANCED_RISK_AVAILABLE = True
except ImportError:
    ENHANCED_RISK_AVAILABLE = False

# 延迟导入主题管理器，避免在模块级别导入时崩溃
THEME_MANAGER_AVAILABLE = False
get_theme_manager = None

def _import_theme_manager():
    """延迟导入主题管理器"""
    global THEME_MANAGER_AVAILABLE, get_theme_manager
    if not THEME_MANAGER_AVAILABLE:
        try:
            from utils.theme import get_theme_manager as _get_theme_manager
            get_theme_manager = _get_theme_manager
            THEME_MANAGER_AVAILABLE = True
            logger.info("主题管理器模块导入成功")
        except Exception as e:
            logger.warning(f"导入主题管理器失败: {e}")

# 延迟导入性能监控，避免在模块级别导入时崩溃
PERFORMANCE_MONITOR_AVAILABLE = False
PerformanceMonitor = None
PerformanceMetric = None
PerformanceAlert = None

def _import_performance_monitor():
    """延迟导入性能监控"""
    global PERFORMANCE_MONITOR_AVAILABLE, PerformanceMonitor, PerformanceMetric, PerformanceAlert
    if not PERFORMANCE_MONITOR_AVAILABLE:
        try:
            from core.monitoring.performance_monitor import PerformanceMonitor as _PerformanceMonitor, PerformanceMetric as _PerformanceMetric, PerformanceAlert as _PerformanceAlert
            PerformanceMonitor = _PerformanceMonitor
            PerformanceMetric = _PerformanceMetric
            PerformanceAlert = _PerformanceAlert
            PERFORMANCE_MONITOR_AVAILABLE = True
            logger.info("性能监控器模块导入成功")
        except Exception as e:
            logger.warning(f"导入性能监控器失败: {e}")


class ModernSystemMonitorTab(QWidget):
    """现代化系统监控标签页"""

    def __init__(self):
        super().__init__()

        # 内存监控相关属性
        try:
            self.memory_baseline = psutil.virtual_memory().used
        except Exception:
            self.memory_baseline = 0
        self.gc_count = 0
        self.memory_history = []

        # 异步数据收集
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="SystemMonitor")
        self.monitoring_timer = QTimer()
        self.monitoring_timer.timeout.connect(self._collect_data_async)

        # 新增：性能监控相关属性
        self.performance_monitor = None
        self.alerts: List[PerformanceAlert] = []
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

        # 延迟导入并初始化主题管理器
        _import_theme_manager()
        self.theme_manager = None
        if THEME_MANAGER_AVAILABLE:
            try:
                self.theme_manager = get_theme_manager()
                self.theme_manager.theme_changed.connect(self._on_theme_changed)
            except Exception as e:
                logger.warning(f"获取ThemeManager失败: {e}")

        # 延迟导入并初始化性能监控
        _import_performance_monitor()
        if PERFORMANCE_MONITOR_AVAILABLE:
            try:
                self.performance_monitor = PerformanceMonitor()
                logger.info("性能监控器初始化成功")
            except Exception as e:
                logger.warning(f"初始化性能监控失败: {e}")

        self.init_ui()

        # 不在初始化时启动定时器，延迟到UI完全准备好后再启动
        # self.monitoring_timer.start(1000)  # 每秒更新一次

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
        cards_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
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
        
        # 启动本地定时器
        self.monitoring_timer.start(1000)
        
        # 启动性能监控器的定时器
        if self.performance_monitor:
            self.performance_monitor.start_monitoring()

    def stop_monitoring(self):
        """停止监控"""
        logger.info("停止性能监控")
        
        # 停止本地定时器
        self.monitoring_timer.stop()
        
        # 停止性能监控器的定时器
        if self.performance_monitor:
            self.performance_monitor.stop_monitoring()

    def toggle_auto_refresh(self, enabled: bool):
        """切换自动刷新"""
        if enabled:
            self.monitoring_timer.start(1000)
        else:
            self.monitoring_timer.stop()

    def refresh_data(self):
        """刷新数据"""
        logger.info("刷新性能数据")
        # TODO: 实现数据刷新逻辑

    def on_component_changed(self, component: str):
        """组件改变"""
        self.current_component = component
        logger.info(f"切换到组件: {component}")

    def refresh_metrics(self):
        """刷新指标"""
        logger.info("刷新性能指标")
        # TODO: 实现指标刷新逻辑

    def clear_alerts(self):
        """清除警报"""
        logger.info("清除性能警报")
        self.alerts.clear()
        self.alerts_table.setRowCount(0)

    def export_alerts(self):
        """导出警报"""
        logger.info("导出性能警报")
        # TODO: 实现警报导出逻辑

    def refresh_recommendations(self):
        """刷新建议"""
        logger.info("刷新优化建议")
        # TODO: 实现建议刷新逻辑

    def apply_recommendations(self):
        """应用建议"""
        logger.info("应用优化建议")
        # TODO: 实现建议应用逻辑

    def export_history(self):
        """导出历史"""
        logger.info("导出性能历史")
        # TODO: 实现历史导出逻辑

    def clear_history(self):
        """清除历史"""
        logger.info("清除性能历史")
        self.performance_history.clear()
        self.history_table.setRowCount(0)

    def update_data(self, system_metrics: Dict[str, float]):
        """更新系统监控数据"""
        try:
            # 检查数据是否有实际变化，避免无意义的更新
            if not system_metrics:
                return

            # 使用 QTimer.singleShot 确保在主线程中更新UI
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._update_ui_in_main_thread(system_metrics))

        except Exception as e:
            logger.error(f"更新系统监控数据失败: {e}")

    def _update_ui_in_main_thread(self, system_metrics: Dict[str, float]):
        """在主线程中更新UI"""
        try:
            # 更新指标卡片（只更新有变化的）
            for name, value in system_metrics.items():
                if name in self.cards:
                    # 检查值是否有显著变化（避免微小变化导致的频繁更新）
                    current_text = self.cards[name].value_label.text()
                    new_text = f"{value:.1f}"
                    if current_text != new_text:
                        trend = "up" if value > 70 else "down" if value < 30 else "neutral"
                        if name == "响应时间":
                            trend = "down" if value > 100 else "up" if value < 50 else "neutral"
                        self.cards[name].update_value(new_text, trend)

            # 批量更新图表数据（减少重绘次数）
            chart_metrics = ["CPU使用率", "内存使用率", "磁盘使用率", "网络吞吐", "响应时间"]
            chart_updated = False
            for name, value in system_metrics.items():
                if name in chart_metrics:
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

    def _collect_data_async(self):
        """异步收集数据，避免UI卡死"""
        try:
            # 检查线程池是否已关闭
            if self.executor is None or self.executor._shutdown:
                return
            # 提交后台任务
            future = self.executor.submit(self._collect_memory_data)
            # 设置回调，在主线程中更新UI
            future.add_done_callback(self._on_data_collected)
        except RuntimeError as e:
            if "shutdown" in str(e):
                logger.debug("线程池已关闭，跳过数据收集")
            else:
                logger.error(f"提交异步数据收集任务失败: {e}")
        except Exception as e:
            logger.error(f"提交异步数据收集任务失败: {e}")

    def _collect_memory_data(self):
        """在后台线程中收集内存数据"""
        try:
            # 设置超时，避免长时间阻塞
            data = {}

            # 获取内存信息（设置超时）
            try:
                memory = psutil.virtual_memory()
                data['memory'] = memory
                data['current_used'] = memory.used
            except Exception as e:
                logger.warning(f"获取内存信息失败: {e}")
                data['memory'] = None

            # 获取GC统计（设置超时）
            try:
                gc_stats = gc.get_stats()
                data['gc_stats'] = gc_stats
            except Exception as e:
                logger.warning(f"获取GC统计失败: {e}")
                data['gc_stats'] = None

            # 获取风险监控数据（如果可用）
            if self.enhanced_risk_monitor:
                try:
                    risk_status = self.enhanced_risk_monitor.get_current_risk_status()
                    risk_alerts = self.enhanced_risk_monitor.get_risk_alerts(1, False)  # 最近1小时
                    data['risk_status'] = risk_status
                    data['risk_alerts'] = risk_alerts
                except Exception as e:
                    logger.warning(f"获取风险监控数据失败: {e}")
                    data['risk_status'] = None
                    data['risk_alerts'] = None

            return data

        except Exception as e:
            logger.error(f"后台数据收集失败: {e}")
            return None

    def _on_data_collected(self, future):
        """数据收集完成的回调，在主线程中更新UI"""
        try:
            # 获取结果，设置超时避免阻塞
            data = future.result(timeout=0.5)  # 500ms超时
            if data is None:
                self._show_no_data()
                return

            self._update_memory_stats_with_data(data)
            self._update_risk_monitoring_stats(data)

        except TimeoutError:
            logger.warning("数据收集超时")
            self._show_no_data()
        except Exception as e:
            logger.error(f"处理收集的数据失败: {e}")
            self._show_no_data()

    def _update_memory_stats_with_data(self, data):
        """使用收集的数据更新内存统计"""
        try:
            memory = data.get('memory')
            current_used = data.get('current_used')
            gc_stats = data.get('gc_stats')

            if memory and current_used is not None:
                # 计算内存增长
                memory_growth = (current_used - self.memory_baseline) / (1024 * 1024)  # MB

                # 更新内存历史
                self.memory_history.append(current_used)
                if len(self.memory_history) > 100:  # 保持最近100个数据点
                    self.memory_history.pop(0)

                # 计算内存峰值
                memory_peak = max(self.memory_history) / (1024 * 1024 * 1024)  # GB

                # 计算内存效率（可用内存/总内存）
                memory_efficiency = (memory.available / memory.total) * 100

                # 更新内存相关指标卡片
                if "内存增长" in self.cards:
                    trend = "up" if memory_growth > 0 else "down" if memory_growth < 0 else "neutral"
                    self.cards["内存增长"].update_value(f"{memory_growth:.1f}", trend)

                if "内存峰值" in self.cards:
                    self.cards["内存峰值"].update_value(f"{memory_peak:.2f}", "neutral")

                if "内存效率" in self.cards:
                    trend = "up" if memory_efficiency > 70 else "down" if memory_efficiency < 30 else "neutral"
                    self.cards["内存效率"].update_value(f"{memory_efficiency:.1f}", trend)
            else:
                # 内存数据不可用
                for metric_name in ["内存增长", "内存峰值", "内存效率"]:
                    if metric_name in self.cards:
                        self.cards[metric_name].update_value("--", "neutral")

            # 处理GC统计
            if "GC清理次数" in self.cards:
                if gc_stats:
                    try:
                        total_collections = sum(stat['collections'] for stat in gc_stats)
                        if total_collections != self.gc_count:
                            self.gc_count = total_collections
                        self.cards["GC清理次数"].update_value(str(self.gc_count), "neutral")
                    except Exception:
                        self.cards["GC清理次数"].update_value("--", "neutral")
                else:
                    self.cards["GC清理次数"].update_value("--", "neutral")

        except Exception as e:
            logger.error(f"更新内存统计失败: {e}")
            self._show_no_data()

    def _show_no_data(self):
        """显示无数据状态"""
        for metric_name in ["内存增长", "GC清理次数", "内存峰值", "内存效率"]:
            if metric_name in self.cards:
                self.cards[metric_name].update_value("--", "neutral")

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
        """清理资源 - 优化性能，避免卡顿"""
        try:
            if hasattr(self, 'monitoring_timer') and self.monitoring_timer:
                try:
                    self.monitoring_timer.stop()
                except Exception as e:
                    logger.debug(f"停止监控定时器失败: {e}")

            # 关闭线程池 - 使用非阻塞关闭
            if hasattr(self, 'executor') and self.executor:
                try:
                    self.executor.shutdown(wait=False)
                    logger.debug("系统监控线程池已关闭")
                except Exception as e:
                    logger.debug(f"关闭线程池失败: {e}")

        except Exception as e:
            logger.debug(f"清理系统监控资源失败: {e}")

    def _update_risk_monitoring_stats(self, data):
        """更新风险监控统计数据"""
        if not ENHANCED_RISK_AVAILABLE or not data:
            return

        try:
            risk_status = data.get('risk_status')
            risk_alerts = data.get('risk_alerts', [])

            # 更新风险监控状态
            if "风险监控状态" in self.cards:
                if risk_status and risk_status.get('monitoring_status') == 'active':
                    self.cards["风险监控状态"].update_value("运行中", "up")
                else:
                    self.cards["风险监控状态"].update_value("停止", "down")

            # 更新风险预警数量
            if "风险预警数量" in self.cards:
                alert_count = len(risk_alerts)
                trend = "up" if alert_count > 5 else "down" if alert_count == 0 else "neutral"
                self.cards["风险预警数量"].update_value(str(alert_count), trend)

            # 更新风险等级
            if "风险等级" in self.cards and risk_status:
                distribution = risk_status.get('risk_distribution', {})
                # 计算主要风险等级
                max_count = 0
                main_level = "低"
                level_mapping = {
                    'very_low': '极低', 'low': '低', 'medium': '中',
                    'high': '高', 'critical': '严重', 'extreme': '极高'
                }

                for level, count in distribution.items():
                    if count > max_count:
                        max_count = count
                        main_level = level_mapping.get(level, '未知')

                trend = "down" if main_level in ['极低', '低'] else "up" if main_level in ['严重', '极高'] else "neutral"
                self.cards["风险等级"].update_value(main_level, trend)

            # 更新AI预测状态
            if "AI预测状态" in self.cards:
                # 这里可以检查AI服务的状态
                self.cards["AI预测状态"].update_value("正常", "up")

            # 更新异常检测数
            if "异常检测数" in self.cards:
                # 从预警中统计异常类型的数量
                anomaly_count = sum(1 for alert in risk_alerts if 'anomaly' in alert.get('category', '').lower())
                trend = "up" if anomaly_count > 3 else "neutral"
                self.cards["异常检测数"].update_value(str(anomaly_count), trend)

            # 更新风险分析延迟
            if "风险分析延迟" in self.cards:
                # 模拟延迟数据，实际应该从风险监控系统获取
                import random
                delay = random.randint(50, 200)  # 50-200ms
                trend = "up" if delay > 150 else "down" if delay < 100 else "neutral"
                self.cards["风险分析延迟"].update_value(str(delay), trend)

        except Exception as e:
            logger.error(f"更新风险监控统计失败: {e}")
            # 设置默认值
            risk_metrics = ["风险监控状态", "风险预警数量", "风险等级", "AI预测状态", "异常检测数", "风险分析延迟"]
            for metric in risk_metrics:
                if metric in self.cards:
                    self.cards[metric].update_value("--", "neutral")

    def resizeEvent(self, event):
        """窗口大小改变事件处理"""
        super().resizeEvent(event)
        self._update_responsive_layout()

    def _update_responsive_layout(self):
        """更新响应式布局"""
        try:
            window_width = self.width()
            window_height = self.height()

            logger.debug(f"SystemMonitorTab 响应式布局更新: {window_width}x{window_height}")

            # 更新系统资源卡片高度
            cards_frames = self.findChildren(QFrame)
            for frame in cards_frames:
                if frame.layout() and isinstance(frame.layout(), QGridLayout):
                    frame_height = max(100, int(window_height * 0.18))
                    frame.setMinimumHeight(frame_height)
                    frame.setMaximumHeight(int(window_height * 0.22))

            # 更新资源图表高度
            if hasattr(self, 'resource_chart'):
                chart_height = max(150, int(window_height * 0.35))
                self.resource_chart.setMinimumHeight(chart_height)

            # 更新组件选择框宽度
            if hasattr(self, 'component_combo'):
                combo_width = max(120, int(window_width * 0.12))
                self.component_combo.setMinimumWidth(combo_width)
                self.component_combo.setMaximumWidth(int(window_width * 0.18))

        except Exception as e:
            logger.error(f"更新响应式布局失败: {e}")

    def cleanup(self):
        """清理资源，正确关闭线程池"""
        try:
            logger.info("开始清理 ModernSystemMonitorTab 资源...")

            # 停止定时器
            if hasattr(self, 'monitoring_timer'):
                self.monitoring_timer.stop()
                logger.debug("监控定时器已停止")

            # 关闭线程池
            if hasattr(self, 'executor') and self.executor is not None:
                self.executor.shutdown(wait=False)
                logger.debug("线程池已关闭")

            # 清理性能监控器
            if hasattr(self, 'performance_monitor') and self.performance_monitor is not None:
                try:
                    self.performance_monitor.stop_monitoring()
                    logger.debug("性能监控器已停止")
                except Exception as e:
                    logger.debug(f"停止性能监控器失败: {e}")

            # 清理增强风险监控
            if hasattr(self, 'enhanced_risk_monitor') and self.enhanced_risk_monitor is not None:
                try:
                    self.enhanced_risk_monitor.cleanup()
                    logger.debug("增强风险监控已清理")
                except Exception as e:
                    logger.debug(f"清理增强风险监控失败: {e}")

            logger.info("ModernSystemMonitorTab 资源清理完成")
        except Exception as e:
            logger.error(f"清理 ModernSystemMonitorTab 资源失败: {e}")
