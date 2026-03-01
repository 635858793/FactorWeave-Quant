#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多智能体状态监控面板
监控各Agent的运行状态和性能
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QTabWidget, QScrollArea, QGroupBox, QGridLayout,
    QTableWidget, QTableWidgetItem, QProgressBar, QSlider, QComboBox,
    QCheckBox, QListWidget, QListWidgetItem, QSizePolicy, QSplitter
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QColor, QPixmap, QPainter, QBrush, QPen

from loguru import logger

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    CHARTS_AVAILABLE = True
except ImportError:
    logger.info("matplotlib 未安装，图表功能将受限")
    CHARTS_AVAILABLE = False

from core.services.bettafish_monitoring_service import BettaFishMonitoringService


class MultiAgentStatusPanel(QWidget):
    """
    多智能体状态监控面板
    
    提供多智能体系统各Agent的运行状态监控：
    - Agent状态总览
    - Agent性能指标
    - 资源使用情况
    - Agent日志和错误
    """

    # 信号定义
    agent_alert = pyqtSignal(str, str)  # Agent告警信号(级别, 消息)
    agent_update = pyqtSignal(dict)  # Agent更新信号

    def __init__(self, parent=None, monitoring_service: BettaFishMonitoringService = None):
        """
        初始化多智能体状态监控面板

        Args:
            parent: 父组件
            monitoring_service: BettaFish监控服务实例
        """
        super().__init__(parent)
        
        # 初始化组件
        self._monitoring_service = monitoring_service
        
        # Agent数据
        self._agents_data = {
            'sentiment_agent': {
                'status': '运行中',
                'cpu_usage': 15.3,
                'memory_usage': 256.2,
                'response_time': 0.5,
                'error_rate': 0.02,
                'last_update': datetime.now(),
                'alerts': []
            },
            'news_agent': {
                'status': '运行中',
                'cpu_usage': 22.1,
                'memory_usage': 512.8,
                'response_time': 1.2,
                'error_rate': 0.01,
                'last_update': datetime.now(),
                'alerts': []
            },
            'technical_agent': {
                'status': '运行中',
                'cpu_usage': 45.7,
                'memory_usage': 1024.5,
                'response_time': 0.8,
                'error_rate': 0.00,
                'last_update': datetime.now(),
                'alerts': []
            },
            'risk_agent': {
                'status': '运行中',
                'cpu_usage': 30.2,
                'memory_usage': 768.9,
                'response_time': 1.5,
                'error_rate': 0.01,
                'last_update': datetime.now(),
                'alerts': []
            },
            'fusion_engine': {
                'status': '运行中',
                'cpu_usage': 18.9,
                'memory_usage': 384.6,
                'response_time': 0.7,
                'error_rate': 0.00,
                'last_update': datetime.now(),
                'alerts': []
            }
        }
        
        # 定时器用于刷新Agent数据
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_agents_data)
        
        # 初始化UI
        self._init_ui()
        
        # 启动定时器
        self._update_timer.start(10000)  # 每10秒更新一次

    def _init_ui(self):
        """初始化UI"""
        # 设置主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 创建控制面板
        self._create_control_panel(main_layout)
        
        # 创建Agent状态选项卡
        self._create_agent_status_tabs(main_layout)

    def _create_control_panel(self, layout):
        """创建控制面板"""
        control_frame = QFrame()
        control_frame.setFrameStyle(QFrame.StyledPanel)
        
        control_layout = QHBoxLayout(control_frame)
        
        # Agent过滤
        control_layout.addWidget(QLabel("Agent过滤:"))
        self.agent_filter_combo = QComboBox()
        self.agent_filter_combo.addItems(["全部", "舆情分析", "新闻分析", "技术分析", "风险评估", "融合引擎"])
        self.agent_filter_combo.currentTextChanged.connect(self._filter_agents)
        control_layout.addWidget(self.agent_filter_combo)
        
        # 实时更新开关
        self.realtime_update_check = QCheckBox("实时更新")
        self.realtime_update_check.setChecked(True)
        self.realtime_update_check.toggled.connect(self._toggle_realtime_update)
        control_layout.addWidget(self.realtime_update_check)
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._update_agents_data)
        control_layout.addWidget(refresh_btn)
        
        layout.addWidget(control_frame)

    def _create_agent_status_tabs(self, layout):
        """创建Agent状态选项卡"""
        # 创建选项卡容器
        self.agent_tab_widget = QTabWidget()
        
        # 创建各个选项卡
        self._create_agent_overview_tab()
        self._create_agent_performance_tab()
        self._create_resource_usage_tab()
        self._create_agent_logs_tab()
        
        layout.addWidget(self.agent_tab_widget)

    def _create_agent_overview_tab(self):
        """创建Agent概览选项卡"""
        overview_widget = QWidget()
        overview_layout = QVBoxLayout(overview_widget)
        
        # Agent状态表格
        self.agent_status_table = QTableWidget()
        self.agent_status_table.setColumnCount(7)
        self.agent_status_table.setHorizontalHeaderLabels([
            "Agent名称", "状态", "CPU使用率", "内存使用", "响应时间", "错误率", "最后更新"
        ])
        self.agent_status_table.setAlternatingRowColors(True)
        self.agent_status_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.agent_status_table.setEditTriggers(QTableWidget.NoEditTriggers)
        overview_layout.addWidget(self.agent_status_table)
        
        # 系统总览
        system_overview_group = QGroupBox("系统总览")
        system_overview_layout = QGridLayout(system_overview_group)
        
        # 系统指标
        self.system_metrics = {
            'total_agents': QLabel("0"),
            'running_agents': QLabel("0"),
            'total_cpu_usage': QLabel("0%"),
            'total_memory_usage': QLabel("0MB"),
            'avg_response_time': QLabel("0秒"),
            'overall_error_rate': QLabel("0%")
        }
        
        # 添加系统指标标签
        system_overview_layout.addWidget(QLabel("Agent总数:"), 0, 0)
        system_overview_layout.addWidget(self.system_metrics['total_agents'], 0, 1)
        
        system_overview_layout.addWidget(QLabel("运行中Agent:"), 0, 2)
        system_overview_layout.addWidget(self.system_metrics['running_agents'], 0, 3)
        
        system_overview_layout.addWidget(QLabel("CPU总使用率:"), 1, 0)
        system_overview_layout.addWidget(self.system_metrics['total_cpu_usage'], 1, 1)
        
        system_overview_layout.addWidget(QLabel("内存总使用:"), 1, 2)
        system_overview_layout.addWidget(self.system_metrics['total_memory_usage'], 1, 3)
        
        system_overview_layout.addWidget(QLabel("平均响应时间:"), 2, 0)
        system_overview_layout.addWidget(self.system_metrics['avg_response_time'], 2, 1)
        
        system_overview_layout.addWidget(QLabel("总体错误率:"), 2, 2)
        system_overview_layout.addWidget(self.system_metrics['overall_error_rate'], 2, 3)
        
        overview_layout.addWidget(system_overview_group)
        
        # 添加到选项卡
        self.agent_tab_widget.addTab(overview_widget, "Agent概览")

    def _create_agent_performance_tab(self):
        """创建Agent性能选项卡"""
        performance_widget = QWidget()
        performance_layout = QVBoxLayout(performance_widget)
        
        # Agent性能图表
        if CHARTS_AVAILABLE:
            self._create_performance_chart(performance_layout)
        else:
            placeholder_label = QLabel("图表功能需要安装matplotlib库")
            placeholder_label.setAlignment(Qt.AlignCenter)
            performance_layout.addWidget(placeholder_label)
        
        # Agent性能表格
        self.agent_performance_table = QTableWidget()
        self.agent_performance_table.setColumnCount(6)
        self.agent_performance_table.setHorizontalHeaderLabels([
            "Agent名称", "响应时间", "吞吐量", "成功率", "错误数", "评分"
        ])
        self.agent_performance_table.setAlternatingRowColors(True)
        self.agent_performance_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.agent_performance_table.setEditTriggers(QTableWidget.NoEditTriggers)
        performance_layout.addWidget(self.agent_performance_table)
        
        # 添加到选项卡
        self.agent_tab_widget.addTab(performance_widget, "性能监控")

    def _create_resource_usage_tab(self):
        """创建资源使用选项卡"""
        resource_widget = QWidget()
        resource_layout = QVBoxLayout(resource_widget)
        
        # 资源使用图表
        if CHARTS_AVAILABLE:
            self._create_resource_chart(resource_layout)
        else:
            placeholder_label = QLabel("图表功能需要安装matplotlib库")
            placeholder_label.setAlignment(Qt.AlignCenter)
            resource_layout.addWidget(placeholder_label)
        
        # 资源使用详情表格
        self.resource_usage_table = QTableWidget()
        self.resource_usage_table.setColumnCount(6)
        self.resource_usage_table.setHorizontalHeaderLabels([
            "Agent名称", "CPU使用率", "内存使用", "磁盘I/O", "网络I/O", "负载指数"
        ])
        self.resource_usage_table.setAlternatingRowColors(True)
        self.resource_usage_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.resource_usage_table.setEditTriggers(QTableWidget.NoEditTriggers)
        resource_layout.addWidget(self.resource_usage_table)
        
        # 添加到选项卡
        self.agent_tab_widget.addTab(resource_widget, "资源使用")

    def _create_agent_logs_tab(self):
        """创建Agent日志选项卡"""
        logs_widget = QWidget()
        logs_layout = QVBoxLayout(logs_widget)
        
        # 日志过滤器
        log_filter_frame = QFrame()
        log_filter_layout = QHBoxLayout(log_filter_frame)
        
        log_filter_layout.addWidget(QLabel("日志级别:"))
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["全部", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level_combo.currentTextChanged.connect(self._filter_logs)
        log_filter_layout.addWidget(self.log_level_combo)
        
        log_filter_layout.addWidget(QLabel("Agent过滤:"))
        self.log_agent_combo = QComboBox()
        self.log_agent_combo.addItems(["全部", "舆情分析", "新闻分析", "技术分析", "风险评估", "融合引擎"])
        self.log_agent_combo.currentTextChanged.connect(self._filter_logs)
        log_filter_layout.addWidget(self.log_agent_combo)
        
        log_filter_layout.addWidget(QLabel("时间范围:"))
        self.log_time_combo = QComboBox()
        self.log_time_combo.addItems(["全部", "最近1小时", "最近6小时", "最近24小时"])
        self.log_time_combo.currentTextChanged.connect(self._filter_logs)
        log_filter_layout.addWidget(self.log_time_combo)
        
        log_filter_layout.addStretch()
        
        # 清除日志按钮
        clear_logs_btn = QPushButton("清除日志")
        clear_logs_btn.clicked.connect(self._clear_logs)
        log_filter_layout.addWidget(clear_logs_btn)
        
        logs_layout.addWidget(log_filter_frame)
        
        # 日志表格
        self.agent_logs_table = QTableWidget()
        self.agent_logs_table.setColumnCount(5)
        self.agent_logs_table.setHorizontalHeaderLabels([
            "时间", "Agent", "级别", "消息", "异常"
        ])
        self.agent_logs_table.setAlternatingRowColors(True)
        self.agent_logs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.agent_logs_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.agent_logs_table.setWordWrap(True)
        logs_layout.addWidget(self.agent_logs_table)
        
        # 添加到选项卡
        self.agent_tab_widget.addTab(logs_widget, "日志监控")

    def _create_performance_chart(self, layout):
        """创建性能图表"""
        # 创建图形和画布
        self.performance_figure = Figure(figsize=(5, 3), dpi=100)
        self.performance_canvas = FigureCanvas(self.performance_figure)
        
        # 创建子图
        self.performance_ax = self.performance_figure.add_subplot(111)
        
        # 初始化图表
        self.performance_ax.set_title("Agent性能趋势")
        self.performance_ax.set_ylabel("响应时间(秒)")
        self.performance_ax.set_xlabel("时间")
        
        # 添加到布局
        layout.addWidget(self.performance_canvas)
        
        # 初始化线条
        self.performance_lines = {}
        
        # 为每个Agent创建线条
        for agent_name in self._agents_data.keys():
            self.performance_lines[agent_name], = self.performance_ax.plot(
                [], [], label=self._get_agent_display_name(agent_name)
            )
        
        # 添加图例
        self.performance_ax.legend(loc='upper right')
        
        # 刷新画布
        self.performance_canvas.draw()

    def _create_resource_chart(self, layout):
        """创建资源使用图表"""
        # 创建图形和画布
        self.resource_figure = Figure(figsize=(5, 3), dpi=100)
        self.resource_canvas = FigureCanvas(self.resource_figure)
        
        # 创建子图
        self.resource_ax = self.resource_figure.add_subplot(111)
        
        # 初始化图表
        self.resource_ax.set_title("Agent资源使用")
        self.resource_ax.set_ylabel("使用率(%)")
        self.resource_ax.set_xlabel("时间")
        
        # 添加到布局
        layout.addWidget(self.resource_canvas)
        
        # 初始化线条
        self.resource_lines = {}
        
        # 为每个Agent创建线条
        for agent_name in self._agents_data.keys():
            self.resource_lines[agent_name], = self.resource_ax.plot(
                [], [], label=self._get_agent_display_name(agent_name)
            )
        
        # 添加图例
        self.resource_ax.legend(loc='upper right')
        
        # 刷新画布
        self.resource_canvas.draw()

    def _update_agents_data(self):
        """更新Agent数据"""
        try:
            # 从监控服务获取Agent数据
            if self._monitoring_service:
                # 模拟从服务获取数据（实际实现中应调用服务的方法）
                agents_data = self._monitoring_service.get_agents_status()
                if agents_data:
                    self._agents_data.update(agents_data)
            
            # 更新Agent状态表格
            self._update_agent_status_table()
            
            # 更新系统指标
            self._update_system_metrics()
            
            # 更新性能表格
            self._update_agent_performance_table()
            
            # 更新资源使用表格
            self._update_resource_usage_table()
            
            # 更新性能图表
            if CHARTS_AVAILABLE:
                self._update_performance_chart()
            
            # 更新资源使用图表
            if CHARTS_AVAILABLE:
                self._update_resource_chart()
            
            # 更新日志
            self._update_agent_logs()
            
            # 检查Agent告警
            self._check_agent_alerts()
            
            # 发出更新信号
            self.agent_update.emit(self._agents_data)
            
        except Exception as e:
            logger.error(f"更新Agent数据失败: {e}")

    def _update_agent_status_table(self):
        """更新Agent状态表格"""
        # 获取当前过滤
        filter_text = self.agent_filter_combo.currentText()
        
        # 设置表格行数
        filtered_agents = self._filter_agents_by_name(filter_text)
        self.agent_status_table.setRowCount(len(filtered_agents))
        
        # 添加数据
        for row, agent_name in enumerate(filtered_agents):
            agent_data = self._agents_data.get(agent_name, {})
            
            # Agent名称
            name_item = QTableWidgetItem(self._get_agent_display_name(agent_name))
            self.agent_status_table.setItem(row, 0, name_item)
            
            # 状态
            status_item = QTableWidgetItem(agent_data.get('status', '未知'))
            status_color = self._get_status_color(agent_data.get('status', '未知'))
            status_item.setBackground(status_color)
            self.agent_status_table.setItem(row, 1, status_item)
            
            # CPU使用率
            cpu_item = QTableWidgetItem(f"{agent_data.get('cpu_usage', 0):.1f}%")
            self.agent_status_table.setItem(row, 2, cpu_item)
            
            # 内存使用
            memory_item = QTableWidgetItem(f"{agent_data.get('memory_usage', 0):.1f}MB")
            self.agent_status_table.setItem(row, 3, memory_item)
            
            # 响应时间
            response_time_item = QTableWidgetItem(f"{agent_data.get('response_time', 0):.2f}秒")
            self.agent_status_table.setItem(row, 4, response_time_item)
            
            # 错误率
            error_rate_item = QTableWidgetItem(f"{agent_data.get('error_rate', 0):.2f}%")
            self.agent_status_table.setItem(row, 5, error_rate_item)
            
            # 最后更新
            last_update_item = QTableWidgetItem(
                agent_data.get('last_update', datetime.now()).strftime('%H:%M:%S')
            )
            self.agent_status_table.setItem(row, 6, last_update_item)
            
            # 设置行高
            self.agent_status_table.setRowHeight(row, 30)

    def _update_system_metrics(self):
        """更新系统指标"""
        # 计算系统指标
        total_agents = len(self._agents_data)
        running_agents = sum(1 for agent in self._agents_data.values() 
                            if agent.get('status') == '运行中')
        total_cpu = sum(agent.get('cpu_usage', 0) for agent in self._agents_data.values())
        total_memory = sum(agent.get('memory_usage', 0) for agent in self._agents_data.values())
        avg_response_time = sum(agent.get('response_time', 0) for agent in self._agents_data.values()) / max(1, total_agents)
        overall_error_rate = sum(agent.get('error_rate', 0) for agent in self._agents_data.values()) / max(1, total_agents)
        
        # 更新系统指标标签
        self.system_metrics['total_agents'].setText(str(total_agents))
        self.system_metrics['running_agents'].setText(str(running_agents))
        self.system_metrics['total_cpu_usage'].setText(f"{total_cpu:.1f}%")
        self.system_metrics['total_memory_usage'].setText(f"{total_memory:.1f}MB")
        self.system_metrics['avg_response_time'].setText(f"{avg_response_time:.2f}秒")
        self.system_metrics['overall_error_rate'].setText(f"{overall_error_rate:.2f}%")

    def _update_agent_performance_table(self):
        """更新Agent性能表格"""
        # 设置表格行数
        self.agent_performance_table.setRowCount(len(self._agents_data))
        
        # 添加数据
        for row, agent_name in enumerate(self._agents_data.keys()):
            agent_data = self._agents_data.get(agent_name, {})
            
            # Agent名称
            name_item = QTableWidgetItem(self._get_agent_display_name(agent_name))
            self.agent_performance_table.setItem(row, 0, name_item)
            
            # 响应时间
            response_time_item = QTableWidgetItem(f"{agent_data.get('response_time', 0):.2f}秒")
            self.agent_performance_table.setItem(row, 1, response_time_item)
            
            # 吞吐量
            throughput_item = QTableWidgetItem(f"{agent_data.get('throughput', 0):.1f}/秒")
            self.agent_performance_table.setItem(row, 2, throughput_item)
            
            # 成功率
            success_rate_item = QTableWidgetItem(f"{agent_data.get('success_rate', 0):.2f}%")
            self.agent_performance_table.setItem(row, 3, success_rate_item)
            
            # 错误数
            error_count_item = QTableWidgetItem(str(agent_data.get('error_count', 0)))
            self.agent_performance_table.setItem(row, 4, error_count_item)
            
            # 评分
            score_item = QTableWidgetItem(f"{agent_data.get('performance_score', 0):.1f}")
            self.agent_performance_table.setItem(row, 5, score_item)
            
            # 设置行高
            self.agent_performance_table.setRowHeight(row, 30)

    def _update_resource_usage_table(self):
        """更新资源使用表格"""
        # 设置表格行数
        self.resource_usage_table.setRowCount(len(self._agents_data))
        
        # 添加数据
        for row, agent_name in enumerate(self._agents_data.keys()):
            agent_data = self._agents_data.get(agent_name, {})
            
            # Agent名称
            name_item = QTableWidgetItem(self._get_agent_display_name(agent_name))
            self.resource_usage_table.setItem(row, 0, name_item)
            
            # CPU使用率
            cpu_item = QTableWidgetItem(f"{agent_data.get('cpu_usage', 0):.1f}%")
            self.resource_usage_table.setItem(row, 1, cpu_item)
            
            # 内存使用
            memory_item = QTableWidgetItem(f"{agent_data.get('memory_usage', 0):.1f}MB")
            self.resource_usage_table.setItem(row, 2, memory_item)
            
            # 磁盘I/O
            disk_io_item = QTableWidgetItem(f"{agent_data.get('disk_io', 0):.1f}MB/s")
            self.resource_usage_table.setItem(row, 3, disk_io_item)
            
            # 网络I/O
            network_io_item = QTableWidgetItem(f"{agent_data.get('network_io', 0):.1f}MB/s")
            self.resource_usage_table.setItem(row, 4, network_io_item)
            
            # 负载指数
            load_index_item = QTableWidgetItem(f"{agent_data.get('load_index', 0):.2f}")
            self.resource_usage_table.setItem(row, 5, load_index_item)
            
            # 设置行高
            self.resource_usage_table.setRowHeight(row, 30)

    def _update_performance_chart(self):
        """更新性能图表"""
        # 获取性能数据
        performance_data = self._agents_data.get('performance_history', {})
        
        if not performance_data:
            return
        
        # 更新每个Agent的线条
        for agent_name, line in self.performance_lines.items():
            agent_performance = performance_data.get(agent_name, {}).get('response_time', [])
            
            if agent_performance:
                # 更新线条数据
                line.set_data(range(len(agent_performance)), agent_performance)
        
        # 更新坐标轴范围
        max_length = max(len(self._agents_data.get('performance_history', {}).get(agent_name, {}).get('response_time', []))
                        for agent_name in self._agents_data.keys()) or 1
        self.performance_ax.set_xlim(0, max_length)
        
        # 刷新画布
        _canvas.draw()
    
    def _update_resource_chart(self):
        """更新资源使用图表"""
        # 获取资源使用数据
        resource_data = self._agents_data.get('resource_history', {})
        
        if not resource_data:
            return
        
        # 更新每个Agent的线条
        for agent_name, line in self.resource_lines.items():
            agent_resource = resource_data.get(agent_name, {}).get('cpu_usage', [])
            
            if agent_resource:
                # 更新线条数据
                line.set_data(range(len(agent_resource)), agent_resource)
        
        # 更新坐标轴范围
        max_length = max(len(self._agents_data.get('resource_history', {}).get(agent_name, {}).get('cpu_usage', []))
                        for agent_name in self._agents_data.keys()) or 1
        self.resource_ax.set_xlim(0, max_length)
        
        # 刷新画布
        self.resource_canvas.draw()

    def _update_agent_logs(self):
        """更新Agent日志"""
        # 获取日志数据
        logs = self._agents_data.get('logs', [])
        
        # 设置表格行数
        self.agent_logs_table.setRowCount(len(logs))
        
        # 添加数据
        for row, log in enumerate(logs):
            # 时间
            time_item = QTableWidgetItem(log.get('timestamp', datetime.now()).strftime('%H:%M:%S'))
            self.agent_logs_table.setItem(row, 0, time_item)
            
            # Agent
            agent_item = QTableWidgetItem(self._get_agent_display_name(log.get('agent', '')))
            self.agent_logs_table.setItem(row, 1, agent_item)
            
            # 级别
            level_item = QTableWidgetItem(log.get('level', 'INFO'))
            level_color = self._get_log_level_color(log.get('level', 'INFO'))
            level_item.setBackground(level_color)
            self.agent_logs_table.setItem(row, 2, level_item)
            
            # 消息
            message_item = QTableWidgetItem(log.get('message', ''))
            self.agent_logs_table.setItem(row, 3, message_item)
            
            # 异常
            exception_item = QTableWidgetItem(log.get('exception', ''))
            self.agent_logs_table.setItem(row, 4, exception_item)
            
            # 设置行高
            self.agent_logs_table.setRowHeight(row, 30)

    def _check_agent_alerts(self):
        """检查Agent告警"""
        # 检查每个Agent的状态
        for agent_name, agent_data in self._agents_data.items():
            # 检查CPU使用率
            cpu_usage = agent_data.get('cpu_usage', 0)
            if cpu_usage > 80:
                self.agent_alert.emit(
                    "warning", 
                    f"{self._get_agent_display_name(agent_name)} CPU使用率过高: {cpu_usage:.1f}%"
                )
            
            # 检查内存使用
            memory_usage = agent_data.get('memory_usage', 0)
            if memory_usage > 1024:
                self.agent_alert.emit(
                    "warning", 
                    f"{self._get_agent_display_name(agent_name)} 内存使用过高: {memory_usage:.1f}MB"
                )
            
            # 检查响应时间
            response_time = agent_data.get('response_time', 0)
            if response_time > 2.0:
                self.agent_alert.emit(
                    "warning", 
                    f"{self._get_agent_display_name(agent_name)} 响应时间过长: {response_time:.2f}秒"
                )
            
            # 检查错误率
            error_rate = agent_data.get('error_rate', 0)
            if error_rate > 0.05:
                self.agent_alert.emit(
                    "warning", 
                    f"{self._get_agent_display_name(agent_name)} 错误率过高: {error_rate:.2f}%"
                )

    def _filter_agents(self, filter_text):
        """过滤Agent"""
        # 更新表格
        self._update_agent_status_table()

    def _filter_agents_by_name(self, filter_text):
        """根据名称过滤Agent"""
        # 根据过滤文本返回匹配的Agent
        if filter_text == "全部":
            return list(self._agents_data.keys())
        elif filter_text == "舆情分析":
            return ['sentiment_agent']
        elif filter_text == "新闻分析":
            return ['news_agent']
        elif filter_text == "技术分析":
            return ['technical_agent']
        elif filter_text == "风险评估":
            return ['risk_agent']
        elif filter_text == "融合引擎":
            return ['fusion_engine']
        else:
            return list(self._agents_data.keys())

    def _get_agent_display_name(self, agent_name):
        """获取Agent的显示名称"""
        name_map = {
            'sentiment_agent': '舆情分析Agent',
            'news_agent': '新闻分析Agent',
            'technical_agent': '技术分析Agent',
            'risk_agent': '风险评估Agent',
            'fusion_engine': '信号融合引擎'
        }
        return name_map.get(agent_name, agent_name)

    def _get_status_color(self, status):
        """获取状态颜色"""
        if status == '运行中':
            return QColor(46, 204, 113, 100)  # 绿色
        elif status == '空闲':
            return QColor(52, 152, 219, 100)  # 蓝色
        elif status == '停止':
            return QColor(149, 165, 166, 100)  # 灰色
        elif status == '错误':
            return QColor(231, 76, 60, 100)  # 红色
        else:
            return QColor(241, 196, 15, 100)  # 黄色

    def _get_log_level_color(self, level):
        """获取日志级别颜色"""
        if level == 'DEBUG':
            return QColor(52, 152, 219, 100)  # 蓝色
        elif level == 'INFO':
            return QColor(46, 204, 113, 100)  # 绿色
        elif level == 'WARNING':
            return QColor(241, 196, 15, 100)  # 黄色
        elif level == 'ERROR':
            return QColor(230, 126, 34, 100)  # 橙色
        elif level == 'CRITICAL':
            return QColor(231, 76, 60, 100)  # 红色
        else:
            return QColor(189, 195, 199, 100)  # 浅灰色

    def _filter_logs(self):
        """过滤日志"""
        try:
            level_filter = self.log_level_combo.currentText()
            agent_filter = self.log_agent_combo.currentText()
            time_filter = self.log_time_combo.currentText()

            self._update_logs_display(level_filter, agent_filter, time_filter)
            logger.debug(f"日志过滤: 级别={level_filter}, Agent={agent_filter}, 时间={time_filter}")
        except Exception as e:
            logger.error(f"日志过滤失败: {e}")

    def _clear_logs(self):
        """清除日志"""
        try:
            self.agent_logs_table.setRowCount(0)
            logger.info("日志已清除")
        except Exception as e:
            logger.error(f"清除日志失败: {e}")

    def _update_logs_display(self, level_filter: str, agent_filter: str, time_filter: str):
        """更新日志显示"""
        if not hasattr(self, 'agent_logs_table'):
            return

        try:
            pass
        except Exception as e:
            logger.error(f"更新日志显示失败: {e}")

    def _toggle_realtime_update(self, enabled):
        """切换实时更新"""
        if enabled:
            self._update_timer.start(10000)  # 10秒
        else:
            self._update_timer.stop()

    def closeEvent(self, event):
        """关闭事件处理"""
        # 停止定时器
        self._update_timer.stop()
        
        # 调用父类关闭事件
        super().closeEvent(event)