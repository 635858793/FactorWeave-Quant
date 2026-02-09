#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
深度优化实时监控面板

提供实时数据展示、告警监控和性能分析的可视化界面

作者: FactorWeave-Quant团队
版本: 1.0
"""

import sys
import time
import threading
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                            QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                            QTextEdit, QFrame, QSplitter, QGroupBox, QProgressBar,
                            QTabWidget, QScrollArea, QCheckBox, QSpinBox, QDoubleSpinBox,
                            QComboBox, QTreeWidget, QTreeWidgetItem, QHeaderView,
                            QAbstractItemView, QMenu, QAction, QMessageBox, QFileDialog)
from PyQt5.QtCore import (Qt, QTimer, QThread, pyqtSignal, QSize, QRect,
                         pyqtProperty, QPropertyAnimation, QEasingCurve, QPoint)
from PyQt5.QtGui import (QFont, QColor, QPalette, QPainter, QBrush, QPen,
                        QIcon, QPixmap, QLinearGradient)

try:
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from loguru import logger

# 导入相关模块
try:
    from core.advanced_optimization.real_time_monitoring import (
        DeepOptimizationMonitor, OptimizationMetrics, MonitoringStatus, create_deep_optimization_monitor
    )
except ImportError as e:
    logger.warning(f"深度优化模块导入失败: {e}")


class MetricsChartWidget(QWidget):
    """指标图表组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.data_history = deque(maxlen=100)  # 保存最近100个数据点
        self.init_ui()
        
        # 定时器用于更新图表
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_chart)
        self.update_timer.start(2000)  # 每2秒更新
    
    def init_ui(self):
        if not HAS_MATPLOTLIB:
            self.setLayout(QVBoxLayout())
            self.layout().addWidget(QLabel("未安装matplotlib，无法显示图表"))
            return
        
        # 创建matplotlib图形
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)
    
    def add_data_point(self, metrics: OptimizationMetrics):
        """添加数据点"""
        timestamp = datetime.fromtimestamp(metrics.timestamp)
        self.data_history.append({
            'timestamp': timestamp,
            'cache_hit_rate': metrics.cache_hit_rate,
            'render_time': metrics.virtualization_render_time,
            'ai_confidence': metrics.ai_confidence_score,
            'network_latency': metrics.network_latency,
            'overall_score': metrics.overall_optimization_score
        })
    
    def update_chart(self):
        """更新图表显示"""
        if not HAS_MATPLOTLIB or not self.data_history:
            return
        
        try:
            self.ax.clear()
            
            # 准备数据
            timestamps = [d['timestamp'] for d in self.data_history]
            cache_rates = [d['cache_hit_rate'] for d in self.data_history]
            render_times = [d['render_time'] for d in self.data_history]
            ai_confidence = [d['ai_confidence'] for d in self.data_history]
            overall_scores = [d['overall_score'] for d in self.data_history]
            
            # 绘制多个子图
            # 子图1: 缓存命中率和总体分数
            ax1 = self.ax
            ax1.plot(timestamps, cache_rates, 'b-', label='缓存命中率', alpha=0.7)
            ax1.plot(timestamps, overall_scores, 'g-', label='总体分数', alpha=0.7)
            ax1.set_ylabel('分数 (0-1)')
            ax1.legend(loc='upper left')
            ax1.grid(True, alpha=0.3)
            
            # 子图2: 渲染时间和AI置信度
            ax2 = ax1.twinx()
            ax2.plot(timestamps, render_times, 'r-', label='渲染时间(ms)', alpha=0.7)
            ax2.plot(timestamps, ai_confidence, 'm-', label='AI置信度', alpha=0.7)
            ax2.set_ylabel('时间/分数')
            ax2.legend(loc='upper right')
            
            # 设置x轴格式
            if len(timestamps) > 1:
                time_span = (timestamps[-1] - timestamps[0]).total_seconds()
                if time_span > 60:
                    self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                else:
                    self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            
            self.ax.set_title('深度优化实时指标监控')
            self.figure.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            logger.warning(f"更新图表失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()
            
            if hasattr(self, 'data_history'):
                self.data_history.clear()
            
            if HAS_MATPLOTLIB and hasattr(self, 'figure'):
                import matplotlib.pyplot as plt
                plt.close(self.figure)
            
            logger.info("MetricsChartWidget 资源已清理")
        except Exception as e:
            logger.error(f"清理 MetricsChartWidget 资源失败: {e}")


class MetricsTableWidget(QWidget):
    """指标表格组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_metrics = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 创建表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['指标类别', '指标名称', '当前值', '状态'])
        
        # 设置表格属性
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        # 预定义指标配置
        self.metrics_config = [
            ('缓存系统', '命中率', 'cache_hit_rate', 'percentage'),
            ('缓存系统', '平均访问时间', 'cache_avg_access_time', 'time_ms'),
            ('缓存系统', '内存使用', 'cache_memory_usage', 'memory_mb'),
            ('缓存系统', '预加载命中', 'cache_preload_hits', 'count'),
            
            ('虚拟化', '渲染时间', 'virtualization_render_time', 'time_ms'),
            ('虚拟化', '渲染块数量', 'virtualization_chunks_count', 'count'),
            ('虚拟化', '质量级别', 'virtualization_quality_level', 'level'),
            ('虚拟化', '内存使用', 'virtualization_memory_usage', 'memory_mb'),
            
            ('AI推荐', '推荐数量', 'ai_recommendation_count', 'count'),
            ('AI推荐', '置信度', 'ai_confidence_score', 'percentage'),
            ('AI推荐', '用户满意度', 'ai_user_satisfaction', 'percentage'),
            
            ('网络性能', '延迟', 'network_latency', 'time_ms'),
            ('网络性能', '吞吐量', 'network_throughput', 'throughput'),
            ('网络性能', '错误率', 'network_error_rate', 'percentage'),
            
            ('综合指标', '总体优化分数', 'overall_optimization_score', 'percentage'),
            ('综合指标', '性能改进', 'performance_improvement', 'percentage'),
            ('综合指标', '资源效率', 'resource_efficiency', 'percentage')
        ]
        
        self.table.setRowCount(len(self.metrics_config))
        
        layout.addWidget(self.table)
        self.setLayout(layout)
        
        # 初始化表格内容
        self._init_table_content()
    
    def _init_table_content(self):
        """初始化表格内容"""
        for row, (category, name, field, unit) in enumerate(self.metrics_config):
            self.table.setItem(row, 0, QTableWidgetItem(category))
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.setItem(row, 2, QTableWidgetItem('--'))
            self.table.setItem(row, 3, QTableWidgetItem('--'))
    
    def update_metrics(self, metrics: OptimizationMetrics):
        """更新指标数据"""
        self.current_metrics = metrics
        
        for row, (category, name, field, unit) in enumerate(self.metrics_config):
            # 获取指标值
            value = getattr(metrics, field, 0.0)
            
            # 格式化显示值
            display_value = self._format_value(value, unit)
            
            # 更新表格
            self.table.setItem(row, 2, QTableWidgetItem(display_value))
            
            # 更新状态颜色
            status_item = self.table.item(row, 3)
            status_item.setText(self._get_status_text(value, unit))
            self._set_status_color(status_item, value, unit)
    
    def _format_value(self, value: float, unit: str) -> str:
        """格式化数值显示"""
        if unit == 'percentage':
            return f"{value:.1%}"
        elif unit == 'time_ms':
            return f"{value:.1f}ms"
        elif unit == 'memory_mb':
            return f"{value:.1f}MB"
        elif unit == 'throughput':
            return f"{value:.1f}ops/s"
        elif unit == 'count':
            return f"{int(value)}"
        elif unit == 'level':
            return f"Level {int(value)}"
        else:
            return f"{value:.2f}"
    
    def _get_status_text(self, value: float, unit: str) -> str:
        """获取状态文本"""
        if unit == 'percentage':
            if value >= 0.8:
                return "优秀"
            elif value >= 0.6:
                return "良好"
            elif value >= 0.4:
                return "一般"
            else:
                return "需优化"
        elif unit == 'time_ms':
            if value <= 20:
                return "优秀"
            elif value <= 50:
                return "良好"
            elif value <= 100:
                return "一般"
            else:
                return "需优化"
        elif unit == 'count':
            return "正常"
        else:
            return "正常"
    
    def _set_status_color(self, item: QTableWidgetItem, value: float, unit: str):
        """设置状态颜色"""
        color_map = {
            "优秀": QColor(0, 128, 0),      # 绿色
            "良好": QColor(0, 150, 255),     # 蓝色
            "一般": QColor(255, 165, 0),     # 橙色
            "需优化": QColor(255, 0, 0),     # 红色
            "正常": QColor(128, 128, 128)    # 灰色
        }
        
        status_text = item.text()
        if status_text in color_map:
            item.setForeground(color_map[status_text])
            item.setBackground(QColor(240, 240, 240))

    def cleanup(self):
        """清理资源"""
        try:
            # 清理表格
            if hasattr(self, 'table'):
                self.table.clearContents()
                self.table.setRowCount(0)
            
            # 清理配置
            if hasattr(self, 'metrics_config'):
                self.metrics_config.clear()
            
            # 清理当前指标
            self.current_metrics = None
            
            # 清理布局
            if self.layout():
                while self.layout().count():
                    item = self.layout().takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                    elif item.layout():
                        while item.layout().count():
                            sub_item = item.layout().takeAt(0)
                            if sub_item.widget():
                                sub_item.widget().deleteLater()
            
            logger.debug("MetricsTableWidget cleanup completed")
            
        except Exception as e:
            logger.error(f"清理资源失败: {e}")


class AlertPanelWidget(QWidget):
    """告警面板组件"""
    
    alert_triggered = pyqtSignal(str, dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.alerts_history = deque(maxlen=50)  # 保存最近50个告警
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 标题和控制
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("系统告警"))
        
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.clear_alerts)
        title_layout.addWidget(self.clear_btn)
        
        layout.addLayout(title_layout)
        
        # 告警列表
        self.alert_table = QTableWidget()
        self.alert_table.setColumnCount(4)
        self.alert_table.setHorizontalHeaderLabels(['时间', '类型', '严重级别', '描述'])
        
        # 设置表格属性
        header = self.alert_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        
        self.alert_table.setMaximumHeight(200)
        
        layout.addWidget(self.alert_table)
        
        # 统计信息
        stats_layout = QHBoxLayout()
        self.warning_count = QLabel("警告: 0")
        self.info_count = QLabel("信息: 0")
        self.error_count = QLabel("错误: 0")
        
        stats_layout.addWidget(self.warning_count)
        stats_layout.addWidget(self.info_count)
        stats_layout.addWidget(self.error_count)
        stats_layout.addStretch()
        
        layout.addLayout(stats_layout)
        
        self.setLayout(layout)
    
    def add_alert(self, alert_type: str, alert_data: dict):
        """添加告警"""
        try:
            # 创建告警记录
            alert_record = {
                'timestamp': datetime.now(),
                'type': alert_type,
                'severity': alert_data.get('severity', 'info'),
                'description': alert_data.get('message', ''),
                'data': alert_data
            }
            
            self.alerts_history.append(alert_record)
            
            # 添加到表格
            self._add_alert_to_table(alert_record)
            
            # 更新统计
            self._update_statistics()
            
            # 发射信号
            self.alert_triggered.emit(alert_type, alert_data)
            
        except Exception as e:
            logger.error(f"添加告警失败: {e}")
    
    def _add_alert_to_table(self, alert_record: dict):
        """添加告警到表格"""
        try:
            row = self.alert_table.rowCount()
            self.alert_table.insertRow(row)
            
            # 设置表格项
            self.alert_table.setItem(row, 0, QTableWidgetItem(alert_record['timestamp'].strftime('%H:%M:%S')))
            self.alert_table.setItem(row, 1, QTableWidgetItem(alert_record['type']))
            self.alert_table.setItem(row, 2, QTableWidgetItem(alert_record['severity']))
            self.alert_table.setItem(row, 3, QTableWidgetItem(alert_record['description']))
            
            # 设置颜色
            severity = alert_record['severity']
            color_map = {
                'error': QColor(255, 0, 0),      # 红色
                'warning': QColor(255, 165, 0),  # 橙色
                'info': QColor(0, 150, 255)      # 蓝色
            }
            
            if severity in color_map:
                for col in range(4):
                    item = self.alert_table.item(row, col)
                    item.setForeground(color_map[severity])
            
        except Exception as e:
            logger.error(f"添加告警到表格失败: {e}")
    
    def _update_statistics(self):
        """更新统计信息"""
        try:
            warnings = sum(1 for a in self.alerts_history if a['severity'] == 'warning')
            infos = sum(1 for a in self.alerts_history if a['severity'] == 'info')
            errors = sum(1 for a in self.alerts_history if a['severity'] == 'error')
            
            self.warning_count.setText(f"警告: {warnings}")
            self.info_count.setText(f"信息: {infos}")
            self.error_count.setText(f"错误: {errors}")
            
        except Exception as e:
            logger.error(f"更新统计信息失败: {e}")
    
    def clear_alerts(self):
        """清空告警"""
        self.alerts_history.clear()
        self.alert_table.setRowCount(0)
        self._update_statistics()

    def cleanup(self):
        """清理资源"""
        try:
            # 清空告警历史
            self.alerts_history.clear()
            
            # 清理表格
            if hasattr(self, 'alert_table'):
                self.alert_table.clearContents()
                self.alert_table.setRowCount(0)
            
            # 清理布局
            if self.layout():
                while self.layout().count():
                    item = self.layout().takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                    elif item.layout():
                        while item.layout().count():
                            sub_item = item.layout().takeAt(0)
                            if sub_item.widget():
                                sub_item.widget().deleteLater()
            
            logger.debug("AlertPanelWidget cleanup completed")
            
        except Exception as e:
            logger.error(f"清理资源失败: {e}")


class DeepMonitoringTab(QWidget):
    """深度优化实时监控标签页"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.monitor = None
        self.optimization_service = None
        self.unified_monitor = None
        
        self.init_ui()
        self._init_connections()
    
    def init_ui(self):
        """初始化UI界面"""
        layout = QVBoxLayout()
        
        # 创建顶部控制面板
        control_panel = self._create_control_panel()
        layout.addWidget(control_panel)
        
        # 创建主内容区域
        main_splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：图表和指标表
        left_widget = self._create_left_panel()
        main_splitter.addWidget(left_widget)
        
        # 右侧：告警和详细信息
        right_widget = self._create_right_panel()
        main_splitter.addWidget(right_widget)
        
        # 设置分割器比例
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)
        
        layout.addWidget(main_splitter)
        self.setLayout(layout)
        
        # 初始化定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(1000)  # 每秒更新显示
    
    def _create_control_panel(self) -> QWidget:
        """创建控制面板"""
        panel = QGroupBox("控制面板")
        layout = QHBoxLayout()
        
        # 监控状态显示
        self.status_label = QLabel("状态: 未初始化")
        self.status_label.setMinimumWidth(100)
        layout.addWidget(self.status_label)
        
        # 监控控制按钮
        self.start_btn = QPushButton("启动监控")
        self.start_btn.clicked.connect(self.start_monitoring)
        layout.addWidget(self.start_btn)
        
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.clicked.connect(self.pause_monitoring)
        self.pause_btn.setEnabled(False)
        layout.addWidget(self.pause_btn)
        
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self.stop_monitoring)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)
        
        # 监控间隔设置
        layout.addWidget(QLabel("更新间隔:"))
        self.interval_spinbox = QDoubleSpinBox()
        self.interval_spinbox.setRange(1.0, 60.0)
        self.interval_spinbox.setValue(5.0)
        self.interval_spinbox.setSuffix("s")
        self.interval_spinbox.setDecimals(1)
        layout.addWidget(self.interval_spinbox)
        
        # 数据导出按钮
        self.export_btn = QPushButton("导出数据")
        self.export_btn.clicked.connect(self.export_metrics_data)
        layout.addWidget(self.export_btn)
        
        layout.addStretch()
        panel.setLayout(layout)
        return panel
    
    def _create_left_panel(self) -> QWidget:
        """创建左侧面板（图表和指标）"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 实时图表标签页
        if HAS_MATPLOTLIB:
            self.chart_widget = MetricsChartWidget()
            tab_widget.addTab(self.chart_widget, "实时图表")
        else:
            placeholder = QWidget()
            placeholder_layout = QVBoxLayout()
            placeholder_layout.addWidget(QLabel("需要安装matplotlib才能显示实时图表"))
            placeholder.setLayout(placeholder_layout)
            tab_widget.addTab(placeholder, "实时图表")
        
        # 指标表格标签页
        self.metrics_table = MetricsTableWidget()
        tab_widget.addTab(self.metrics_table, "指标详情")
        
        # 系统信息标签页
        self._create_system_info_tab(tab_widget)
        
        layout.addWidget(tab_widget)
        widget.setLayout(layout)
        return widget
    
    def _create_right_panel(self) -> QWidget:
        """创建右侧面板（告警和详细信息）"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 告警面板
        self.alert_panel = AlertPanelWidget()
        self.alert_panel.alert_triggered.connect(self._on_alert_triggered)
        layout.addWidget(self.alert_panel)
        
        # 详细信息面板
        details_group = QGroupBox("详细信息")
        details_layout = QVBoxLayout()
        
        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(150)
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)
        
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        
        widget.setLayout(layout)
        return widget
    
    def _create_system_info_tab(self, parent_tab_widget: QTabWidget):
        """创建系统信息标签页"""
        info_widget = QWidget()
        layout = QVBoxLayout()
        
        # 系统统计
        stats_group = QGroupBox("系统统计")
        stats_layout = QGridLayout()
        
        self.stat_labels = {}
        stats_items = [
            ('运行时间', 'runtime'),
            ('总收集次数', 'total_collections'),
            ('错误次数', 'error_count'),
            ('平均收集间隔', 'avg_interval'),
            ('当前总体分数', 'current_score'),
            ('缓存命中率', 'cache_hit_rate'),
            ('渲染时间', 'render_time'),
            ('网络延迟', 'network_latency')
        ]
        
        for i, (label, key) in enumerate(stats_items):
            row = i // 2
            col = i % 2
            
            stats_layout.addWidget(QLabel(f"{label}:"), row, col * 2)
            value_label = QLabel("--")
            value_label.setMinimumWidth(80)
            stats_layout.addWidget(value_label, row, col * 2 + 1)
            
            self.stat_labels[key] = value_label
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # 进度条
        progress_group = QGroupBox("性能指标")
        progress_layout = QGridLayout()
        
        self.progress_bars = {}
        progress_items = [
            ('总体优化分数', 'overall_score'),
            ('缓存性能', 'cache_performance'),
            ('渲染性能', 'render_performance'),
            ('AI推荐质量', 'ai_quality'),
            ('网络性能', 'network_performance')
        ]
        
        for i, (label, key) in enumerate(progress_items):
            row = i
            
            progress_layout.addWidget(QLabel(f"{label}:"), row, 0)
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(0)
            progress_layout.addWidget(progress_bar, row, 1)
            
            self.progress_bars[key] = progress_bar
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        info_widget.setLayout(layout)
        parent_tab_widget.addTab(info_widget, "系统信息")
    
    def _init_connections(self):
        """初始化连接"""
        # 监控间隔变化
        self.interval_spinbox.valueChanged.connect(self._on_interval_changed)
    
    def set_optimization_service(self, service):
        """设置优化服务"""
        self.optimization_service = service
        logger.info("深度监控面板已设置优化服务")
    
    def set_unified_monitor(self, monitor):
        """设置统一监控系统"""
        self.unified_monitor = monitor
        logger.info("深度监控面板已设置统一监控")
    
    def start_monitoring(self):
        """启动监控"""
        try:
            if not self.optimization_service:
                QMessageBox.warning(self, "警告", "未设置优化服务")
                return
            
            # 创建监控器
            self.monitor = create_deep_optimization_monitor(self.optimization_service, self.unified_monitor)
            
            # 设置回调
            self.monitor.add_metrics_callback(self._on_metrics_updated)
            self.monitor.add_alert_callback(self._on_alert_updated)
            
            # 启动监控
            interval = self.interval_spinbox.value()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.monitor.start_monitoring(interval))
            
            # 更新UI状态
            self._update_control_state()
            self.status_label.setText("状态: 运行中")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            
            QMessageBox.information(self, "成功", "深度优化监控已启动")
            
        except Exception as e:
            logger.error(f"启动监控失败: {e}")
            QMessageBox.critical(self, "错误", f"启动监控失败:\n{str(e)}")
    
    def pause_monitoring(self):
        """暂停监控"""
        if self.monitor:
            self.monitor.pause_monitoring()
            self._update_control_state()
            self.status_label.setText("状态: 已暂停")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")
    
    def stop_monitoring(self):
        """停止监控"""
        if self.monitor:
            self.monitor.stop_monitoring()
            self.monitor = None
            
            # 更新UI状态
            self._update_control_state()
            self.status_label.setText("状态: 已停止")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def _on_metrics_updated(self, metrics: OptimizationMetrics):
        """指标更新回调"""
        # 图表更新
        if hasattr(self, 'chart_widget'):
            self.chart_widget.add_data_point(metrics)
        
        # 表格更新
        self.metrics_table.update_metrics(metrics)
    
    def _on_alert_updated(self, alert_type: str, alert_data: dict):
        """告警更新回调"""
        self.alert_panel.add_alert(alert_type, alert_data)
    
    def _on_alert_triggered(self, alert_type: str, alert_data: dict):
        """告警触发回调"""
        # 这里可以添加更复杂的告警处理逻辑
        # 比如播放声音、弹出对话框等
        logger.info(f"告警触发: {alert_type}")
    
    def _update_display(self):
        """更新显示"""
        if self.monitor:
            # 更新统计信息
            stats = self.monitor.get_statistics()
            self._update_statistics_display(stats)
            
            # 更新进度条
            if hasattr(self, 'chart_widget') and hasattr(self, 'chart_widget'):
                current_metrics = self.monitor.get_current_metrics()
                self._update_progress_bars(current_metrics)
    
    def _update_statistics_display(self, stats: dict):
        """更新统计信息显示"""
        try:
            # 运行时间
            if stats.get('start_time'):
                runtime = time.time() - stats['start_time']
                runtime_str = self._format_duration(runtime)
                self.stat_labels['runtime'].setText(runtime_str)
            
            # 其他统计信息
            self.stat_labels['total_collections'].setText(str(stats.get('total_collections', 0)))
            self.stat_labels['error_count'].setText(str(stats.get('error_count', 0)))
            
            if stats.get('avg_collection_interval'):
                interval_str = f"{stats['avg_collection_interval']:.1f}s"
                self.stat_labels['avg_interval'].setText(interval_str)
            
            # 当前指标
            current_metrics = stats.get('current_metrics', {})
            self.stat_labels['current_score'].setText(f"{current_metrics.get('overall_score', 0):.2f}")
            self.stat_labels['cache_hit_rate'].setText(f"{current_metrics.get('cache_hit_rate', 0):.1%}")
            self.stat_labels['render_time'].setText(f"{current_metrics.get('render_time', 0):.1f}ms")
            self.stat_labels['network_latency'].setText(f"{current_metrics.get('network_latency', 0):.1f}ms")
            
        except Exception as e:
            logger.warning(f"更新统计信息显示失败: {e}")
    
    def _update_progress_bars(self, metrics: OptimizationMetrics):
        """更新进度条"""
        try:
            self.progress_bars['overall_score'].setValue(int(metrics.overall_optimization_score * 100))
            
            cache_perf = metrics.cache_hit_rate * 100
            self.progress_bars['cache_performance'].setValue(int(cache_perf))
            
            # 渲染性能（时间越短越好）
            render_perf = max(0, 100 - (metrics.virtualization_render_time / 100 * 100))
            self.progress_bars['render_performance'].setValue(int(min(100, render_perf)))
            
            self.progress_bars['ai_quality'].setValue(int(metrics.ai_confidence_score * 100))
            
            # 网络性能（延迟越低越好）
            network_perf = max(0, 100 - (metrics.network_latency / 200 * 100))
            self.progress_bars['network_performance'].setValue(int(min(100, network_perf)))
            
        except Exception as e:
            logger.warning(f"更新进度条失败: {e}")
    
    def _update_control_state(self):
        """更新控制状态"""
        if self.monitor and hasattr(self.monitor, 'status'):
            status = self.monitor.status
            is_running = status.value == 'running'
            is_paused = status.value == 'paused'
            
            self.start_btn.setEnabled(not is_running and not is_paused)
            self.pause_btn.setEnabled(is_running)
            self.pause_btn.setText("暂停" if is_running else "恢复")
            self.stop_btn.setEnabled(is_running or is_paused)
        else:
            self.start_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
    
    def _on_interval_changed(self, value: float):
        """监控间隔变化回调"""
        if self.monitor:
            # 这里需要重启监控来应用新的间隔
            logger.info(f"监控间隔已更改为: {value}s")
    
    def export_metrics_data(self):
        """导出指标数据"""
        if not self.monitor:
            QMessageBox.warning(self, "警告", "监控器未启动，无法导出数据")
            return
        
        try:
            # 选择导出路径
            filename, _ = QFileDialog.getSaveFileName(
                self, "导出深度优化监控数据",
                f"deep_optimization_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "JSON Files (*.json)"
            )
            
            if filename:
                result = self.monitor.export_metrics_data(filename)
                if result.get('success'):
                    QMessageBox.information(
                        self, "成功", 
                        f"数据已导出到: {filename}\n"
                        f"共导出 {result.get('records_count', 0)} 条记录"
                    )
                else:
                    QMessageBox.critical(self, "错误", f"导出失败: {result.get('error')}")
        
        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
    
    def _format_duration(self, seconds: float) -> str:
        """格式化时间持续"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
    
    def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()
            
            if hasattr(self, 'monitor') and self.monitor:
                try:
                    self.monitor.stop()
                except Exception as e:
                    logger.error(f"停止监控器失败: {e}")
            
            if hasattr(self, 'optimization_service') and self.optimization_service:
                try:
                    self.optimization_service.stop()
                except Exception as e:
                    logger.error(f"停止优化服务失败: {e}")
            
            logger.info("DeepMonitoringTab 资源已清理")
        except Exception as e:
            logger.error(f"清理 DeepMonitoringTab 资源失败: {e}")


# 全局函数
def create_deep_monitoring_tab() -> DeepMonitoringTab:
    """创建深度监控标签页实例"""
    return DeepMonitoringTab()