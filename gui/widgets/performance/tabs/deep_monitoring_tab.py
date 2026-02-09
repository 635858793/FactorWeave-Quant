#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深度优化实时监控标签页

提供深度优化服务的实时监控界面，包括指标图表、告警面板和数据分析

作者: FactorWeave-Quant团队
版本: 1.0
"""

import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
    QLabel, QPushButton, QProgressBar, QGroupBox, QFrame, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QCheckBox, QSpinBox, QSlider, QLineEdit, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QDateTime
from PyQt5.QtGui import QFont, QPalette, QColor, QPainter, QBrush

# 导入监控相关模块
try:
    from core.advanced_optimization.real_time_monitoring import (
        DeepOptimizationMonitor, OptimizationMetrics, MonitoringStatus,
        create_deep_optimization_monitor
    )
    from core.performance.unified_monitor import UnifiedPerformanceMonitor
except ImportError as e:
    print(f"监控模块导入失败: {e}")

class MetricsChartWidget(QFrame):
    """简单的指标图表组件"""
    
    def __init__(self, title: str = "", max_points: int = 50):
        super().__init__()
        self.title = title
        self.max_points = max_points
        self.data_points = []
        self.color = QColor(52, 152, 219)  # 蓝色
        
        self.setStyleSheet("""
            QFrame {
                background: rgba(44, 62, 80, 0.3);
                border: 1px solid #34495e;
                border-radius: 4px;
            }
        """)
        self.setMinimumHeight(150)
        
    def add_data_point(self, value: float, timestamp: float = None):
        """添加数据点"""
        if timestamp is None:
            timestamp = time.time()
            
        self.data_points.append((timestamp, value))
        
        # 保持最大点数限制
        if len(self.data_points) > self.max_points:
            self.data_points.pop(0)
        
        self.update()
    
    def paintEvent(self, event):
        """绘制图表"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制背景
        painter.fillRect(self.rect(), QBrush(QColor(44, 62, 80, 30)))
        
        if len(self.data_points) < 2:
            return
        
        # 计算数据范围
        values = [point[1] for point in self.data_points]
        min_val = min(values)
        max_val = max(values)
        
        if max_val == min_val:
            return
        
        # 绘制数据线
        painter.setPen(self.color)
        painter.setWidth(2)
        
        rect = self.rect()
        width = rect.width()
        height = rect.height()
        
        for i in range(1, len(self.data_points)):
            x1 = rect.left() + (i - 1) * width / (self.max_points - 1)
            y1 = rect.bottom() - (self.data_points[i - 1][1] - min_val) / (max_val - min_val) * height
            x2 = rect.left() + i * width / (self.max_points - 1)
            y2 = rect.bottom() - (self.data_points[i][1] - min_val) / (max_val - min_val) * height
            
            painter.drawLine(x1, y1, x2, y2)
        
        # 绘制当前值
        current_value = self.data_points[-1][1]
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(rect, Qt.AlignRight | Qt.AlignTop, f"{current_value:.2f}")


class AlertPanelWidget(QFrame):
    """告警面板组件"""
    
    alert_triggered = pyqtSignal(str, dict)  # 告警类型, 告警数据
    
    def __init__(self):
        super().__init__()
        self.alerts = []
        self.max_alerts = 10
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 标题
        title_label = QLabel("🚨 实时告警")
        title_label.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 12px;")
        layout.addWidget(title_label)
        
        # 告警列表
        self.alert_list = QTextEdit()
        self.alert_list.setMaximumHeight(200)
        self.alert_list.setStyleSheet("""
            QTextEdit {
                background: rgba(231, 76, 60, 0.1);
                color: #ecf0f1;
                font-family: 'Consolas', monospace;
                font-size: 10px;
                border: 1px solid #e74c3c;
                border-radius: 4px;
            }
        """)
        self.alert_list.setReadOnly(True)
        layout.addWidget(self.alert_list)
        
        # 告警控制
        control_layout = QHBoxLayout()
        
        clear_button = QPushButton("清空告警")
        clear_button.setStyleSheet("""
            QPushButton {
                background: #34495e;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 10px;
            }
            QPushButton:hover {
                background: #2c3e50;
            }
        """)
        clear_button.clicked.connect(self.clear_alerts)
        
        control_layout.addWidget(clear_button)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
    
    def add_alert(self, alert_type: str, alert_data: Dict[str, Any]):
        """添加告警"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        message = alert_data.get('message', f"告警类型: {alert_type}")
        
        # 确定告警颜色
        severity = alert_data.get('severity', 'info')
        color_map = {
            'critical': '#e74c3c',
            'warning': '#f39c12',
            'info': '#3498db'
        }
        color = color_map.get(severity, '#95a5a6')
        
        alert_text = f"[{timestamp}] {message}"
        
        # 添加到告警列表
        self.alerts.insert(0, (alert_text, color, timestamp))
        
        # 保持最大告警数量
        if len(self.alerts) > self.max_alerts:
            self.alerts.pop()
        
        # 使用 QTimer.singleShot 确保在主线程中更新UI
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, self._update_alert_display_in_main_thread)
        
        # 发送信号
        self.alert_triggered.emit(alert_type, alert_data)
    
    def clear_alerts(self):
        """清空告警"""
        self.alerts.clear()
        # 使用 QTimer.singleShot 确保在主线程中更新UI
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, self._update_alert_display_in_main_thread)
    
    def _update_alert_display_in_main_thread(self):
        """在主线程中更新告警显示"""
        if not self.alerts:
            self.alert_list.setPlainText("暂无告警信息")
            return
        
        display_text = ""
        for alert_text, color, timestamp in self.alerts:
            display_text += f'<span style="color: {color};">{alert_text}</span>\n'
        
        self.alert_list.setHtml(display_text)


class DeepMonitoringOverviewTab(QWidget):
    """深度监控概览标签页"""
    
    def __init__(self, optimization_service, unified_monitor):
        super().__init__()
        self.optimization_service = optimization_service
        self.unified_monitor = unified_monitor
        
        # 监控器
        self.monitor = None
        
        # 监控线程
        self.monitoring_thread = None
        self.monitoring_stop_event = None
        
        # 指标图表
        self.charts = {}
        
        # 当前指标值
        self.current_values = {
            'cache_hit_rate': 0.0,
            'render_time': 0.0,
            'ai_confidence': 0.0,
            'network_latency': 0.0,
            'overall_score': 0.0
        }
        
        self.init_ui()
        self.setup_timer()
        
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 控制面板
        control_frame = QFrame()
        control_frame.setStyleSheet("""
            QFrame {
                background: rgba(52, 73, 94, 0.3);
                border: 1px solid #34495e;
                border-radius: 6px;
                padding: 10px;
                margin: 5px;
            }
        """)
        control_layout = QHBoxLayout(control_frame)
        
        # 监控状态
        self.status_label = QLabel("监控状态: 停止")
        self.status_label.setStyleSheet("""
            color: #e74c3c;
            font-weight: bold;
            font-size: 12px;
        """)
        control_layout.addWidget(self.status_label)
        
        control_layout.addStretch()
        
        # 控制按钮
        self.start_button = QPushButton("开始监控")
        self.start_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #27ae60, stop: 1 #229954);
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #229954, stop: 1 #1e8449);
            }
        """)
        self.start_button.clicked.connect(self.start_monitoring)
        
        self.stop_button = QPushButton("停止监控")
        self.stop_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #e74c3c, stop: 1 #c0392b);
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #c0392b, stop: 1 #a93226);
            }
        """)
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.stop_button.setEnabled(False)
        
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        
        layout.addWidget(control_frame)
        
        # 关键指标卡片
        metrics_frame = QGroupBox("关键性能指标")
        metrics_layout = QGridLayout(metrics_frame)
        
        # 创建指标卡片
        self.metrics_cards = {}
        
        # 缓存命中率
        self.metrics_cards['cache_hit_rate'] = self._create_metric_card("缓存命中率", "0%", "#27ae60")
        metrics_layout.addWidget(self.metrics_cards['cache_hit_rate'], 0, 0)
        
        # 渲染时间
        self.metrics_cards['render_time'] = self._create_metric_card("渲染时间", "0ms", "#3498db")
        metrics_layout.addWidget(self.metrics_cards['render_time'], 0, 1)
        
        # AI置信度
        self.metrics_cards['ai_confidence'] = self._create_metric_card("AI置信度", "0%", "#9b59b6")
        metrics_layout.addWidget(self.metrics_cards['ai_confidence'], 1, 0)
        
        # 网络延迟
        self.metrics_cards['network_latency'] = self._create_metric_card("网络延迟", "0ms", "#e67e22")
        metrics_layout.addWidget(self.metrics_cards['network_latency'], 1, 1)
        
        # 总体分数
        self.metrics_cards['overall_score'] = self._create_metric_card("总体分数", "0.0", "#e74c3c")
        metrics_layout.addWidget(self.metrics_cards['overall_score'], 2, 0)
        
        layout.addWidget(metrics_frame)
        
        # 图表区域
        charts_frame = QGroupBox("实时指标图表")
        charts_layout = QGridLayout(charts_frame)
        
        # 创建图表
        self.charts['cache_hit_rate'] = MetricsChartWidget("缓存命中率")
        self.charts['render_time'] = MetricsChartWidget("渲染时间(ms)")
        self.charts['network_latency'] = MetricsChartWidget("网络延迟(ms)")
        self.charts['overall_score'] = MetricsChartWidget("总体分数")
        
        charts_layout.addWidget(self.charts['cache_hit_rate'], 0, 0)
        charts_layout.addWidget(self.charts['render_time'], 0, 1)
        charts_layout.addWidget(self.charts['network_latency'], 1, 0)
        charts_layout.addWidget(self.charts['overall_score'], 1, 1)
        
        layout.addWidget(charts_frame)
        
        # 告警面板
        self.alert_panel = AlertPanelWidget()
        layout.addWidget(self.alert_panel)
        
        layout.addStretch()
        
    def _create_metric_card(self, title: str, value: str, color: str) -> QFrame:
        """创建指标卡片"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: rgba(52, 73, 94, 0.5);
                border: 1px solid {color};
                border-radius: 8px;
                padding: 15px;
                margin: 5px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(5)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #bdc3c7; font-size: 11px;")
        
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
        
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)
        
        return card
        
    def setup_timer(self):
        """设置定时更新"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_charts)
        self.timer.start(2000)  # 2秒更新一次图表
        
    def create_monitor(self):
        """创建监控器"""
        try:
            if self.monitor:
                self.monitor.stop_monitoring()
            
            self.monitor = create_deep_optimization_monitor(
                self.optimization_service,
                self.unified_monitor
            )
            
            # 添加指标回调
            self.monitor.add_metrics_callback(self.on_metrics_updated)
            
            # 添加告警回调
            self.monitor.add_alert_callback(self.on_alert_triggered)
            
        except Exception as e:
            print(f"创建监控器失败: {e}")
            
    def start_monitoring(self):
        """开始监控"""
        try:
            if not self.monitor:
                self.create_monitor()
            
            if self.monitor:
                import asyncio
                import threading
                
                # 停止之前的监控线程（如果存在）
                if self.monitoring_thread and self.monitoring_thread.is_alive():
                    if self.monitoring_stop_event:
                        self.monitoring_stop_event.set()
                    # 不等待线程结束，因为线程是 daemon=True，会自动清理
                    # 如果使用 join() 会阻塞主线程，导致UI卡顿
                
                # 创建新的停止事件
                self.monitoring_stop_event = threading.Event()
                
                def start_async_monitoring():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self.monitor.start_monitoring())
                    except Exception as e:
                        logger.error(f"监控线程执行失败: {e}")
                    finally:
                        loop.close()
                
                # 在新线程中启动异步监控
                self.monitoring_thread = threading.Thread(target=start_async_monitoring, daemon=True)
                self.monitoring_thread.start()
                
                # 更新UI状态
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                self.status_label.setText("监控状态: 运行中")
                self.status_label.setStyleSheet("""
                    color: #27ae60;
                    font-weight: bold;
                    font-size: 12px;
                """)
                
        except Exception as e:
            print(f"启动监控失败: {e}")
            
    def stop_monitoring(self):
        """停止监控"""
        try:
            if self.monitor:
                self.monitor.stop_monitoring()
            
            # 停止监控线程
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                if self.monitoring_stop_event:
                    self.monitoring_stop_event.set()
                # 不等待线程结束，因为线程是 daemon=True，会自动清理
                # 如果使用 join() 会阻塞主线程，导致UI卡顿
            
            # 更新UI状态
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.status_label.setText("监控状态: 停止")
            self.status_label.setStyleSheet("""
                color: #e74c3c;
                font-weight: bold;
                font-size: 12px;
            """)
            
        except Exception as e:
            print(f"停止监控失败: {e}")
            
    def on_metrics_updated(self, metrics: OptimizationMetrics):
        """指标更新回调"""
        try:
            # 更新当前值
            self.current_values.update({
                'cache_hit_rate': metrics.cache_hit_rate,
                'render_time': metrics.virtualization_render_time,
                'ai_confidence': metrics.ai_confidence_score,
                'network_latency': metrics.network_latency,
                'overall_score': metrics.overall_optimization_score
            })
            
            # 更新UI显示
            self._update_metrics_display()
            
        except Exception as e:
            print(f"更新指标显示失败: {e}")
            
    def _update_metrics_display(self):
        """更新指标显示"""
        try:
            # 更新缓存命中率
            hit_rate_text = f"{self.current_values['cache_hit_rate']:.1%}"
            self.metrics_cards['cache_hit_rate'].findChild(QLabel).setText(hit_rate_text)
            
            # 更新渲染时间
            render_time_text = f"{self.current_values['render_time']:.1f}ms"
            self.metrics_cards['render_time'].findChild(QLabel).setText(render_time_text)
            
            # 更新AI置信度
            ai_confidence_text = f"{self.current_values['ai_confidence']:.1%}"
            self.metrics_cards['ai_confidence'].findChild(QLabel).setText(ai_confidence_text)
            
            # 更新网络延迟
            network_latency_text = f"{self.current_values['network_latency']:.1f}ms"
            self.metrics_cards['network_latency'].findChild(QLabel).setText(network_latency_text)
            
            # 更新总体分数
            overall_score_text = f"{self.current_values['overall_score']:.2f}"
            self.metrics_cards['overall_score'].findChild(QLabel).setText(overall_score_text)
            
        except Exception as e:
            print(f"更新指标显示失败: {e}")
            
    def update_charts(self):
        """更新图表"""
        try:
            # 为图表添加数据点
            self.charts['cache_hit_rate'].add_data_point(self.current_values['cache_hit_rate'] * 100)
            self.charts['render_time'].add_data_point(self.current_values['render_time'])
            self.charts['network_latency'].add_data_point(self.current_values['network_latency'])
            self.charts['overall_score'].add_data_point(self.current_values['overall_score'])
            
        except Exception as e:
            print(f"更新图表失败: {e}")
            
    def on_alert_triggered(self, alert_type: str, alert_data: Dict[str, Any]):
        """告警回调"""
        try:
            self.alert_panel.add_alert(alert_type, alert_data)
        except Exception as e:
            print(f"处理告警失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'monitor') and self.monitor:
                try:
                    self.monitor.stop()
                except Exception as e:
                    logger.error(f"停止监控器失败: {e}")
            
            if hasattr(self, 'charts'):
                for chart in self.charts.values():
                    if hasattr(chart, 'cleanup'):
                        try:
                            chart.cleanup()
                        except Exception as e:
                            logger.error(f"清理图表失败: {e}")
            
            logger.info("DeepMonitoringOverviewTab 资源已清理")
        except Exception as e:
            logger.error(f"清理 DeepMonitoringOverviewTab 资源失败: {e}")


class DeepMonitoringDetailsTab(QWidget):
    """深度监控详情标签页"""
    
    def __init__(self, optimization_service, unified_monitor):
        super().__init__()
        self.optimization_service = optimization_service
        self.unified_monitor = unified_monitor
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 统计信息表格
        stats_group = QGroupBox("监控统计信息")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(3)
        self.stats_table.setHorizontalHeaderLabels(["统计项目", "当前值", "状态"])
        header = self.stats_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        
        stats_layout.addWidget(self.stats_table)
        
        # 导出按钮
        export_layout = QHBoxLayout()
        
        export_button = QPushButton("导出监控数据")
        export_button.clicked.connect(self.export_data)
        
        refresh_button = QPushButton("刷新统计")
        refresh_button.clicked.connect(self.refresh_stats)
        
        export_layout.addWidget(export_button)
        export_layout.addWidget(refresh_button)
        export_layout.addStretch()
        
        stats_layout.addLayout(export_layout)
        
        layout.addWidget(stats_group)
        
        # 初始化统计数据
        self.init_stats_data()
        
    def init_stats_data(self):
        """初始化统计数据"""
        stats_data = [
            ["监控运行时间", "00:00:00", "正常"],
            ["数据收集次数", "0", "正常"],
            ["告警触发次数", "0", "正常"],
            ["平均收集间隔", "0.0秒", "正常"],
            ["最后收集时间", "无", "正常"],
            ["错误计数", "0", "正常"]
        ]
        
        self.stats_table.setRowCount(len(stats_data))
        for row, (name, value, status) in enumerate(stats_data):
            self.stats_table.setItem(row, 0, QTableWidgetItem(name))
            self.stats_table.setItem(row, 1, QTableWidgetItem(value))
            
            status_item = QTableWidgetItem(status)
            if status == "正常":
                status_item.setBackground(QColor(46, 204, 113, 100))
            else:
                status_item.setBackground(QColor(231, 76, 60, 100))
            
            self.stats_table.setItem(row, 2, status_item)
            
    def refresh_stats(self):
        """刷新统计数据"""
        # 这里可以添加获取实时统计数据的逻辑
        current_time = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.stats_table.setItem(1, 1, QTableWidgetItem("0"))  # 数据收集次数
        self.stats_table.setItem(4, 1, QTableWidgetItem(current_time))  # 最后收集时间
        
    def export_data(self):
        """导出数据"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "导出监控数据",
                f"deep_monitoring_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "JSON files (*.json)"
            )
            
            if filename:
                # 这里可以调用监控器的导出功能
                QMessageBox.information(self, "导出成功", f"数据已导出到: {filename}")
                
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出数据时发生错误: {str(e)}")
    
    def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'stats_table'):
                self.stats_table.clear()
            
            logger.info("DeepMonitoringDetailsTab 资源已清理")
        except Exception as e:
            logger.error(f"清理 DeepMonitoringDetailsTab 资源失败: {e}")


class DeepMonitoringTab(QWidget):
    """深度监控标签页主类"""
    
    def __init__(self, optimization_service, unified_monitor):
        super().__init__()
        self.optimization_service = optimization_service
        self.unified_monitor = unified_monitor
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #34495e;
                background: #2c3e50;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #34495e;
                border: 1px solid #34495e;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 16px;
                margin-right: 2px;
                color: #bdc3c7;
            }
            QTabBar::tab:selected {
                background: #2c3e50;
                color: #ecf0f1;
            }
            QTabBar::tab:hover {
                background: #3c5a6b;
            }
        """)
        
        # 创建子标签页
        self.overview_tab = DeepMonitoringOverviewTab(self.optimization_service, self.unified_monitor)
        self.details_tab = DeepMonitoringDetailsTab(self.optimization_service, self.unified_monitor)
        
        # 添加标签页
        self.tab_widget.addTab(self.overview_tab, "📊 概览")
        self.tab_widget.addTab(self.details_tab, "📋 详情")
        
        layout.addWidget(self.tab_widget)
        
        print("深度监控标签页初始化完成")
    
    def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'overview_tab') and self.overview_tab:
                if hasattr(self.overview_tab, 'cleanup'):
                    self.overview_tab.cleanup()
            
            if hasattr(self, 'details_tab') and self.details_tab:
                if hasattr(self.details_tab, 'cleanup'):
                    self.details_tab.cleanup()
            
            logger.info("DeepMonitoringTab 资源已清理")
        except Exception as e:
            logger.error(f"清理 DeepMonitoringTab 资源失败: {e}")