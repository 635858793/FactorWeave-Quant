from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统健康检查标签页
现代化系统健康监控界面
"""

import json
from datetime import datetime
from typing import Optional, Dict, List, Any
from collections import deque
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QCheckBox, QLabel, QGridLayout, QTextEdit, QListWidget,
    QFrame, QMessageBox, QTabWidget, QToolBar, QAction, QComboBox,
    QSpinBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QSplitter, QSizePolicy
)
from PyQt5.QtCore import pyqtSlot, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor
from gui.widgets.performance.workers.async_workers import SystemHealthCheckThread


class ModernSystemHealthTab(QWidget):
    """现代化系统健康检查标签页"""

    def __init__(self, health_checker=None):
        super().__init__()
        self._health_checker = health_checker
        self._check_thread = None

        # 新增：实时监控相关属性
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.current_node_id = "local"
        self.node_metrics: Dict[str, Any] = {}
        self.node_status: Dict[str, str] = {}
        self.health_history: List[Dict[str, Any]] = deque(maxlen=100)
        self.thresholds = {
            'cpu_usage': {'warning': 70.0, 'critical': 90.0},
            'memory_usage': {'warning': 80.0, 'critical': 95.0},
            'disk_usage': {'warning': 85.0, 'critical': 95.0},
            'network_latency': {'warning': 1000.0, 'critical': 5000.0},
            'error_rate': {'warning': 0.05, 'critical': 0.15},
            'response_time': {'warning': 2000.0, 'critical': 10000.0}
        }

        # 如果没有传入health_checker，尝试创建一个
        if not self._health_checker:
            try:
                from analysis.system_health_checker import SystemHealthChecker
                from core.metrics.aggregation_service import MetricsAggregationService
                from core.metrics.repository import MetricsRepository
                from core.events import EventBus

                # 创建必要的组件
                event_bus = EventBus()
                repo = MetricsRepository(db_path=':memory:')
                agg_service = MetricsAggregationService(event_bus, repo)

                # 创建健康检查器
                self._health_checker = SystemHealthChecker(
                    aggregation_service=agg_service,
                    repository=repo
                )
                logger.info("已自动创建系统健康检查器")
            except Exception as e:
                logger.error(f"创建健康检查器失败: {e}")
                self._health_checker = None

        self.init_ui()

        # 启动自动刷新
        self.update_timer.start(5000)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

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
        
        # 节点选择器
        self.toolbar.addSeparator()
        self.toolbar.addWidget(QLabel("节点:"))
        self.node_combo = QComboBox()
        self.node_combo.setMinimumWidth(150)
        self.node_combo.currentTextChanged.connect(self.on_node_changed)
        self.toolbar.addWidget(self.node_combo)
        
        layout.addWidget(self.toolbar)

        # 标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.create_overview_tab(), "概览")
        self.tab_widget.addTab(self.create_metrics_tab(), "指标详情")
        self.tab_widget.addTab(self.create_trend_tab(), "趋势分析")
        self.tab_widget.addTab(self.create_thresholds_tab(), "阈值配置")
        self.tab_widget.addTab(self.create_history_tab(), "历史记录")
        
        layout.addWidget(self.tab_widget)

        # 应用样式
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #27ae60;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background: #27ae60;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #229954;
            }
        """)

    def _create_status_card(self, name: str, status: str) -> QFrame:
        """创建状态卡片"""
        card = QFrame()
        card.setFrameStyle(QFrame.Box)
        card.setStyleSheet("""
            QFrame {
                border: 1px solid #bdc3c7;
                border-radius: 6px;
                background: #ecf0f1;
                padding: 5px;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(5, 5, 5, 5)

        name_label = QLabel(name)
        name_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(name_label)

        status_label = QLabel(status)
        status_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        layout.addWidget(status_label)

        card.status_label = status_label  # 保存引用以便更新
        return card

    def run_health_check(self):
        """执行健康检查"""
        if not self._health_checker:
            QMessageBox.warning(self, "错误", "健康检查器未初始化")
            return

        self.check_button.setEnabled(False)
        self.check_button.setText("检查中...")

        self._check_thread = SystemHealthCheckThread(self._health_checker)
        self._check_thread.health_check_completed.connect(self.on_check_completed)
        self._check_thread.health_check_error.connect(self.on_check_error)
        self._check_thread.start()

    @pyqtSlot(dict)
    def on_check_completed(self, report: dict):
        """健康检查完成处理"""
        self.check_button.setEnabled(True)
        self.check_button.setText("开始健康检查")

        # 更新总体状态
        overall_health = report.get('overall_health', 'unknown')
        status_colors = {
            'healthy': '#27ae60',
            'warning': '#f39c12',
            'critical': '#e74c3c',
            'unknown': '#7f8c8d'
        }
        color = status_colors.get(overall_health, '#7f8c8d')
        self.overall_status_label.setText(f"总体状态: {overall_health.upper()}")
        self.overall_status_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")

        # 更新各子系统状态
        for key, card in self.status_cards.items():
            subsystem_data = report.get(key, {})
            status = subsystem_data.get('status', 'unknown')
            card.status_label.setText(status)
            card.status_label.setStyleSheet(f"color: {status_colors.get(status, '#7f8c8d')}; font-size: 11px;")

        # 更新详细报告 - 使用HTML表格格式
        report_html = self._generate_html_report(report)
        self.report_text.setHtml(report_html)

        # 更新建议
        self.recommendations_list.clear()
        recommendations = report.get('recommendations', [])
        for rec in recommendations:
            self.recommendations_list.addItem(rec)

    @pyqtSlot(str)
    def on_check_error(self, error: str):
        """健康检查错误处理"""
        self.check_button.setEnabled(True)
        self.check_button.setText("开始健康检查")

        #  修复：更好的错误显示和日志
        logger.error(f"健康检查失败: {error}")

        # 在报告区域显示错误信息
        error_report = f""" 健康检查失败

错误信息: {error}

请检查：
1. 系统依赖是否完整
2. 相关服务是否正常运行
3. 查看日志获取更多详细信息

时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.report_text.setPlainText(error_report)

        # 更新总体状态
        self.overall_status_label.setText("总体状态: 检查失败")
        self.overall_status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e74c3c;")

        # 也显示弹窗
        QMessageBox.critical(self, "检查错误", f"健康检查失败：{error}")

    def _generate_html_report(self, report: dict) -> str:
        """生成HTML格式的健康检查报告"""
        try:
            html = """
            <html>
            <head>
                <style>
                    body { font-family: 'Microsoft YaHei', Arial, sans-serif; font-size: 12px; }
                    .header { background: #2c3e50; color: white; padding: 10px; border-radius: 5px; margin-bottom: 10px; }
                    .section { margin-bottom: 15px; }
                    .section-title { font-weight: bold; color: #2c3e50; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; margin-bottom: 8px; }
                    table { width: 100%; border-collapse: collapse; margin-bottom: 10px; }
                    th, td { border: 1px solid #bdc3c7; padding: 8px; text-align: left; }
                    th { background: #ecf0f1; font-weight: bold; }
                    .status-healthy { color: #27ae60; font-weight: bold; }
                    .status-warning { color: #f39c12; font-weight: bold; }
                    .status-error { color: #e74c3c; font-weight: bold; }
                    .status-critical { color: #c0392b; font-weight: bold; }
                    .timestamp { color: #7f8c8d; font-size: 11px; }
                    .metric-value { font-family: 'Consolas', monospace; }
                </style>
            </head>
            <body>
            """

            # 报告头部
            timestamp = report.get('timestamp', datetime.now().isoformat())
            overall_health = report.get('overall_health', 'unknown')

            html += f"""
            <div class="header">
                <h3>FactorWeave-Quant 系统健康检查报告</h3>
                <div class="timestamp">检查时间: {timestamp}</div>
                <div>总体状态: <span class="status-{overall_health}">{overall_health.upper()}</span></div>
            </div>
            """

            # 系统概览表格
            html += """
            <div class="section">
                <div class="section-title">系统概览</div>
                <table>
                    <tr><th>检查项目</th><th>状态</th><th>详细信息</th></tr>
            """

            # 各子系统状态
            subsystem_names = {
                'system_info': '系统信息',
                'pattern_recognition': '形态识别',
                'performance_metrics': '性能指标',
                'cache_system': '缓存系统',
                'memory_usage': '内存使用',
                'dependencies': '依赖检查',
                'database_connectivity': '数据库连接',
                'ui_components': 'UI组件'
            }

            for key, name in subsystem_names.items():
                subsystem_data = report.get(key, {})
                status = subsystem_data.get('status', 'unknown')

                # 提取关键信息
                details = []
                if key == 'system_info':
                    version = subsystem_data.get('version', 'unknown')
                    patterns = subsystem_data.get('supported_patterns', 0)
                    details.append(f"版本: {version}, 支持形态: {patterns}种")
                elif key == 'performance_metrics':
                    ops = subsystem_data.get('live_monitored_operations', 0)
                    calls = subsystem_data.get('live_total_calls', 0)
                    success_rate = subsystem_data.get('live_success_rate', 0)
                    details.append(f"监控操作: {ops}, 总调用: {calls}, 成功率: {success_rate:.1%}")
                elif key == 'cache_system':
                    size = subsystem_data.get('cache_size', 0)
                    hit_rate = subsystem_data.get('hit_rate', 0)
                    details.append(f"缓存大小: {size}, 命中率: {hit_rate:.1%}")
                elif key == 'memory_usage':
                    cpu = subsystem_data.get('cpu_percent', 0)
                    mem = subsystem_data.get('memory_percent', 0)
                    details.append(f"CPU: {cpu:.1f}%, 内存: {mem:.1f}%")

                detail_text = '; '.join(details) if details else subsystem_data.get('error', '正常')

                html += f"""
                    <tr>
                        <td>{name}</td>
                        <td><span class="status-{status}">{status}</span></td>
                        <td class="metric-value">{detail_text}</td>
                    </tr>
                """

            html += "</table></div>"

            # 建议和操作
            recommendations = report.get('recommendations', [])
            if recommendations:
                html += """
                <div class="section">
                    <div class="section-title">优化建议</div>
                    <ul>
                """
                for rec in recommendations:
                    html += f"<li>{rec}</li>"
                html += "</ul></div>"

            html += """
            </body>
            </html>
            """

            return html

        except Exception as e:
            logger.error(f"生成HTML报告失败: {e}")
            return f"<p>报告生成失败: {e}</p><pre>{json.dumps(report, indent=2, ensure_ascii=False)}</pre>"

    def cleanup(self):
        """清理资源 - 优化性能，避免卡顿"""
        try:
            # 停止健康检查线程 - 优化终止逻辑
            if hasattr(self, '_check_thread') and self._check_thread:
                if self._check_thread.isRunning():
                    try:
                        self._check_thread.terminate()
                        # 减少等待时间从1秒到200毫秒，避免卡顿
                        self._check_thread.wait(200)
                    except Exception as e:
                        logger.debug(f"停止健康检查线程失败: {e}")
                try:
                    self._check_thread.deleteLater()
                except Exception as e:
                    logger.debug(f"删除线程对象失败: {e}")
            
            # 清理自适应连接池监控
            if hasattr(self, 'adaptive_pool_monitor') and self.adaptive_pool_monitor:
                try:
                    if hasattr(self.adaptive_pool_monitor, 'cleanup'):
                        self.adaptive_pool_monitor.cleanup()
                except Exception as e:
                    logger.debug(f"清理自适应连接池监控失败: {e}")
            
            # 清理状态卡片
            if hasattr(self, 'status_cards'):
                for card in self.status_cards.values():
                    try:
                        if hasattr(card, 'cleanup'):
                            card.cleanup()
                    except Exception as e:
                        logger.debug(f"清理状态卡片失败: {e}")
            
            # 清理健康检查器
            if hasattr(self, '_health_checker') and self._health_checker:
                try:
                    if hasattr(self._health_checker, 'cleanup'):
                        self._health_checker.cleanup()
                except Exception as e:
                    logger.debug(f"清理健康检查器失败: {e}")
            
            logger.debug("ModernSystemHealthTab cleanup completed")
            
        except Exception as e:
            logger.debug(f"清理资源失败: {e}")

    def create_overview_tab(self):
        """创建概览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 健康检查控制面板
        control_group = QGroupBox("系统健康检查")
        control_layout = QHBoxLayout()
        
        self.check_button = QPushButton("开始健康检查")
        self.check_button.clicked.connect(self.run_health_check)
        control_layout.addWidget(self.check_button)
        
        self.auto_check_cb = QCheckBox("自动检查")
        control_layout.addWidget(self.auto_check_cb)
        
        control_layout.addStretch()
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # 健康状态总览
        overview_group = QGroupBox("健康状态总览")
        overview_layout = QGridLayout()
        
        self.overall_status_label = QLabel("总体状态: 未检查")
        self.overall_status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        overview_layout.addWidget(self.overall_status_label, 0, 0, 1, 2)
        
        # 各子系统状态卡片
        self.status_cards = {}
        subsystems = [
            ("系统信息", "system_info"),
            ("形态识别", "pattern_recognition"),
            ("性能指标", "performance_metrics"),
            ("缓存系统", "cache_system"),
            ("内存使用", "memory_usage"),
            ("依赖检查", "dependencies"),
            ("数据库连接", "database_connectivity"),
            ("连接池健康", "connection_pool_health"),
            ("UI组件", "ui_components")
        ]
        
        for i, (name, key) in enumerate(subsystems):
            card = self._create_status_card(name, "未检查")
            self.status_cards[key] = card
            overview_layout.addWidget(card, (i // 4) + 1, i % 4)
        
        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)
        
        # 详细报告
        report_group = QGroupBox("详细报告")
        report_layout = QVBoxLayout()
        
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setMaximumHeight(300)
        self.report_text.setHtml("<p>点击'开始健康检查'按钮开始检查系统健康状态</p>")
        report_layout.addWidget(self.report_text)
        
        report_group.setLayout(report_layout)
        layout.addWidget(report_group)
        
        # 建议和操作
        recommendations_group = QGroupBox("建议和操作")
        recommendations_layout = QVBoxLayout()
        
        self.recommendations_list = QListWidget()
        recommendations_layout.addWidget(self.recommendations_list)
        
        recommendations_group.setLayout(recommendations_layout)
        layout.addWidget(recommendations_group)
        
        return widget
    
    def create_metrics_tab(self):
        """创建指标详情标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 指标显示
        metrics_group = QGroupBox("健康指标")
        metrics_layout = QGridLayout(metrics_group)
        
        # CPU使用率
        metrics_layout.addWidget(QLabel("CPU使用率:"), 0, 0)
        self.cpu_bar = self._create_progress_bar()
        self.cpu_label = QLabel("0%")
        metrics_layout.addWidget(self.cpu_bar, 0, 1)
        metrics_layout.addWidget(self.cpu_label, 0, 2)
        
        # 内存使用率
        metrics_layout.addWidget(QLabel("内存使用率:"), 1, 0)
        self.memory_bar = self._create_progress_bar()
        self.memory_label = QLabel("0%")
        metrics_layout.addWidget(self.memory_bar, 1, 1)
        metrics_layout.addWidget(self.memory_label, 1, 2)
        
        # 磁盘使用率
        metrics_layout.addWidget(QLabel("磁盘使用率:"), 2, 0)
        self.disk_bar = self._create_progress_bar()
        self.disk_label = QLabel("0%")
        metrics_layout.addWidget(self.disk_bar, 2, 1)
        metrics_layout.addWidget(self.disk_label, 2, 2)
        
        # 网络延迟
        metrics_layout.addWidget(QLabel("网络延迟:"), 3, 0)
        self.network_bar = self._create_progress_bar()
        self.network_label = QLabel("0ms")
        metrics_layout.addWidget(self.network_bar, 3, 1)
        metrics_layout.addWidget(self.network_label, 3, 2)
        
        # 错误率
        metrics_layout.addWidget(QLabel("错误率:"), 4, 0)
        self.error_bar = self._create_progress_bar()
        self.error_label = QLabel("0%")
        metrics_layout.addWidget(self.error_bar, 4, 1)
        metrics_layout.addWidget(self.error_label, 4, 2)
        
        # 响应时间
        metrics_layout.addWidget(QLabel("响应时间:"), 5, 0)
        self.response_bar = self._create_progress_bar()
        self.response_label = QLabel("0ms")
        metrics_layout.addWidget(self.response_bar, 5, 1)
        metrics_layout.addWidget(self.response_label, 5, 2)
        
        layout.addWidget(metrics_group)
        layout.addStretch()
        
        return widget
    
    def create_trend_tab(self):
        """创建趋势分析标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 时间范围选择
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("时间范围:"))
        
        self.duration_combo = QComboBox()
        self.duration_combo.addItems(["30分钟", "1小时", "2小时", "6小时", "12小时", "24小时"])
        self.duration_combo.setCurrentIndex(0)
        controls_layout.addWidget(self.duration_combo)
        
        controls_layout.addStretch()
        
        refresh_trend_btn = QPushButton("刷新趋势")
        refresh_trend_btn.clicked.connect(self.refresh_trend)
        controls_layout.addWidget(refresh_trend_btn)
        
        layout.addLayout(controls_layout)
        
        # 趋势数据表格
        trend_group = QGroupBox("健康趋势")
        trend_layout = QVBoxLayout(trend_group)
        
        self.trend_table = QTableWidget()
        self.trend_table.setColumnCount(7)
        self.trend_table.setHorizontalHeaderLabels([
            "样本数", "时间范围", "平均CPU", "平均内存", "平均响应时间", "平均错误率", "状态"
        ])
        self.trend_table.horizontalHeader().setStretchLastSection(True)
        self.trend_table.verticalHeader().setVisible(False)
        self.trend_table.setAlternatingRowColors(True)
        trend_layout.addWidget(self.trend_table)
        
        layout.addWidget(trend_group)
        
        return widget
    
    def create_thresholds_tab(self):
        """创建阈值配置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 阈值配置表格
        thresholds_group = QGroupBox("健康阈值配置")
        thresholds_layout = QVBoxLayout(thresholds_group)
        
        self.thresholds_table = QTableWidget()
        self.thresholds_table.setColumnCount(4)
        self.thresholds_table.setHorizontalHeaderLabels(["指标", "警告阈值", "严重阈值", "单位"])
        self.thresholds_table.horizontalHeader().setStretchLastSection(True)
        self.thresholds_table.verticalHeader().setVisible(False)
        self.thresholds_table.setAlternatingRowColors(True)
        thresholds_layout.addWidget(self.thresholds_table)
        
        # 操作按钮
        buttons_layout = QHBoxLayout()
        
        save_btn = QPushButton("保存阈值")
        save_btn.clicked.connect(self.save_thresholds)
        buttons_layout.addWidget(save_btn)
        
        reset_btn = QPushButton("重置默认")
        reset_btn.clicked.connect(self.reset_thresholds)
        buttons_layout.addWidget(reset_btn)
        
        buttons_layout.addStretch()
        
        layout.addWidget(thresholds_group)
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
        history_group = QGroupBox("健康历史")
        history_layout = QVBoxLayout(history_group)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(8)
        self.history_table.setHorizontalHeaderLabels([
            "时间", "CPU", "内存", "磁盘", "网络延迟", "错误率", "响应时间", "状态"
        ])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setAlternatingRowColors(True)
        history_layout.addWidget(self.history_table)
        
        # 操作按钮
        buttons_layout = QHBoxLayout()
        
        export_btn = QPushButton("导出数据")
        export_btn.clicked.connect(self.export_history)
        buttons_layout.addWidget(export_btn)
        
        clear_btn = QPushButton("清除历史")
        clear_btn.clicked.connect(self.clear_history)
        buttons_layout.addWidget(clear_btn)
        
        buttons_layout.addStretch()
        
        layout.addWidget(history_group)
        layout.addLayout(buttons_layout)
        layout.addStretch()
        
        return widget
    
    def _create_progress_bar(self):
        """创建进度条"""
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setTextVisible(False)
        bar.setMaximumHeight(20)
        bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                background-color: #F5F5F5;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 2px;
            }
        """)
        return bar
    
    def start_monitoring(self):
        """启动监控"""
        logger.info("启动健康监控")
        self.update_timer.start(5000)
    
    def stop_monitoring(self):
        """停止监控"""
        logger.info("停止健康监控")
        self.update_timer.stop()
    
    def toggle_auto_refresh(self, enabled: bool):
        """切换自动刷新"""
        if enabled:
            self.update_timer.start(5000)
        else:
            self.update_timer.stop()
    
    def refresh_data(self):
        """刷新数据"""
        logger.info("刷新健康数据")
        self.run_health_check()
    
    def update_display(self):
        """更新显示"""
        if self.auto_check_cb.isChecked():
            self.run_health_check()
    
    def on_node_changed(self, node_id: str):
        """节点改变"""
        self.current_node_id = node_id
        logger.info(f"切换到节点: {node_id}")
    
    def refresh_trend(self):
        """刷新趋势"""
        logger.info("刷新健康趋势")
        # TODO: 实现趋势数据刷新逻辑
    
    def save_thresholds(self):
        """保存阈值"""
        logger.info("保存健康阈值")
        # TODO: 实现阈值保存逻辑
    
    def reset_thresholds(self):
        """重置阈值"""
        logger.info("重置健康阈值")
        self.thresholds = {
            'cpu_usage': {'warning': 70.0, 'critical': 90.0},
            'memory_usage': {'warning': 80.0, 'critical': 95.0},
            'disk_usage': {'warning': 85.0, 'critical': 95.0},
            'network_latency': {'warning': 1000.0, 'critical': 5000.0},
            'error_rate': {'warning': 0.05, 'critical': 0.15},
            'response_time': {'warning': 2000.0, 'critical': 10000.0}
        }
        logger.info("阈值已重置为默认值")
    
    def export_history(self):
        """导出历史"""
        logger.info("导出健康历史")
        # TODO: 实现历史导出逻辑
    
    def clear_history(self):
        """清除历史"""
        logger.info("清除健康历史")
        self.health_history.clear()
        self.history_table.setRowCount(0)
        logger.info("历史记录已清除")
