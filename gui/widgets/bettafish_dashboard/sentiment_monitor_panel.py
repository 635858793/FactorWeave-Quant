#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情监控面板
实时监控市场情绪和社交媒体舆情变化
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QTabWidget, QScrollArea, QGroupBox, QGridLayout,
    QTableWidget, QTableWidgetItem, QProgressBar, QSlider, QComboBox,
    QCheckBox, QListWidget, QListWidgetItem, QSizePolicy
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

from core.agents.bettafish_agent import BettaFishAgent


class SentimentMonitorPanel(QWidget):
    """
    舆情监控面板
    
    提供实时市场情绪分析和社交媒体舆情监控功能：
    - 市场情绪指标监控
    - 社交媒体舆情分析
    - 舆情趋势图表
    - 关键事件检测
    """

    # 信号定义
    sentiment_alert = pyqtSignal(str, str)  # 舆情告警信号(级别, 消息)
    sentiment_update = pyqtSignal(dict)  # 舆情更新信号

    def __init__(self, parent=None, bettafish_agent: BettaFishAgent = None):
        """
        初始化舆情监控面板

        Args:
            parent: 父组件
            bettafish_agent: BettaFish代理实例
        """
        super().__init__(parent)
        
        # 初始化组件
        self._bettafish_agent = bettafish_agent
        
        # 舆情数据
        self._sentiment_data = {
            'market_sentiment': 0.0,
            'social_sentiment': 0.0,
            'news_sentiment': 0.0,
            'overall_sentiment': 0.0,
            'sentiment_trend': [],
            'key_events': [],
            'sentiment_sources': {},
            '_data_loaded': False,
        }
        
        # 定时器用于刷新舆情数据
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_sentiment_data)
        
        # 初始化UI
        self._init_ui()
        
        # 启动定时器
        self._update_timer.start(30000)  # 每30秒更新一次

    def _init_ui(self):
        """初始化UI"""
        # 设置主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 创建控制面板
        self._create_control_panel(main_layout)
        
        # 创建舆情指标区域
        self._create_sentiment_metrics(main_layout)
        
        # 创建图表区域
        self._create_charts_area(main_layout)
        
        # 创建关键事件区域
        self._create_key_events_area(main_layout)

    def _create_control_panel(self, layout):
        """创建控制面板"""
        control_frame = QFrame()
        control_frame.setFrameStyle(QFrame.StyledPanel)
        
        control_layout = QHBoxLayout(control_frame)
        
        # 数据源选择
        control_layout.addWidget(QLabel("数据源:"))
        self.data_source_combo = QComboBox()
        self.data_source_combo.addItems(["全部", "市场数据", "社交媒体", "新闻"])
        self.data_source_combo.currentTextChanged.connect(self._update_sentiment_data)
        control_layout.addWidget(self.data_source_combo)
        
        # 实时更新开关
        self.realtime_update_check = QCheckBox("实时更新")
        self.realtime_update_check.setChecked(True)
        self.realtime_update_check.toggled.connect(self._toggle_realtime_update)
        control_layout.addWidget(self.realtime_update_check)
        
        # 告警阈值设置
        control_layout.addWidget(QLabel("告警阈值:"))
        self.alert_threshold_slider = QSlider(Qt.Horizontal)
        self.alert_threshold_slider.setRange(0, 100)
        self.alert_threshold_slider.setValue(25)
        self.alert_threshold_slider.valueChanged.connect(self._update_alert_threshold)
        control_layout.addWidget(self.alert_threshold_slider)
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._update_sentiment_data)
        control_layout.addWidget(refresh_btn)
        
        layout.addWidget(control_frame)

    def _create_sentiment_metrics(self, layout):
        """创建舆情指标区域"""
        metrics_frame = QFrame()
        metrics_frame.setFrameStyle(QFrame.StyledPanel)
        
        metrics_layout = QVBoxLayout(metrics_frame)
        
        # 标题
        title_label = QLabel("舆情指标")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        metrics_layout.addWidget(title_label)
        
        # 指标网格
        metrics_grid = QGridLayout()
        
        # 整体舆情
        self._create_sentiment_gauge(metrics_grid, "整体舆情", 0, 0)
        
        # 市场情绪
        self._create_sentiment_gauge(metrics_grid, "市场情绪", 0, 1)
        
        # 社交舆情
        self._create_sentiment_gauge(metrics_grid, "社交舆情", 1, 0)
        
        # 新闻舆情
        self._create_sentiment_gauge(metrics_grid, "新闻舆情", 1, 1)
        
        metrics_layout.addLayout(metrics_grid)
        
        layout.addWidget(metrics_frame)

    def _create_sentiment_gauge(self, layout, name, row, col):
        """创建舆情仪表盘"""
        gauge_frame = QFrame()
        gauge_frame.setFrameStyle(QFrame.StyledPanel)
        
        gauge_layout = QVBoxLayout(gauge_frame)
        
        # 指标名称
        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        gauge_layout.addWidget(name_label)
        
        # 仪表盘
        gauge_widget = QFrame()
        gauge_widget.setFixedHeight(60)
        gauge_widget.setStyleSheet("background-color: #F0F0F0; border-radius: 5px;")
        
        # 进度条显示
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(50)
        progress_bar.setTextVisible(False)
        
        # 颜色样式取决于值
        progress_bar.setStyleSheet("""
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                stop:0 #E74C3C, stop:0.5 #F39C12, stop:1 #2ECC71);
                border-radius: 3px;
            }
        """)
        
        gauge_layout.addWidget(progress_bar)
        
        # 数值标签
        value_label = QLabel("0.5")
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        
        gauge_layout.addWidget(value_label)
        
        # 存储引用
        setattr(self, f"{name.lower().replace(' ', '_')}_gauge", (progress_bar, value_label))
        
        # 添加到网格
        layout.addWidget(gauge_frame, row, col)

    def _create_charts_area(self, layout):
        """创建图表区域"""
        charts_frame = QFrame()
        charts_frame.setFrameStyle(QFrame.StyledPanel)
        charts_frame.setMinimumHeight(200)
        
        charts_layout = QVBoxLayout(charts_frame)
        
        # 标题
        title_label = QLabel("舆情趋势图表")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        charts_layout.addWidget(title_label)
        
        # 图表容器
        self.charts_container = QWidget()
        charts_layout.addWidget(self.charts_container)
        
        # 图表布局
        self.charts_layout = QVBoxLayout(self.charts_container)
        
        # 检查是否可用matplotlib
        if CHARTS_AVAILABLE:
            self._create_sentiment_chart()
        else:
            # 如果matplotlib不可用，显示替代内容
            placeholder_label = QLabel("图表功能需要安装matplotlib库")
            placeholder_label.setAlignment(Qt.AlignCenter)
            self.charts_layout.addWidget(placeholder_label)

    def _create_sentiment_chart(self):
        """创建舆情趋势图表"""
        # 创建图形和画布
        self.figure = Figure(figsize=(5, 3), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(self.charts_container)
        
        # 创建子图
        self.ax = self.figure.add_subplot(111)
        
        # 初始化空数据
        self.ax.set_xlim(0, 10)
        self.ax.set_ylim(0, 1)
        self.ax.set_title("舆情趋势")
        self.ax.set_ylabel("舆情指数")
        self.ax.set_xlabel("时间")
        
        # 添加到布局
        self.charts_layout.addWidget(self.canvas)
        
        # 初始化线条
        self.line_market, = self.ax.plot([], [], label="市场情绪", color="blue")
        self.line_social, = self.ax.plot([], [], label="社交舆情", color="green")
        self.line_news, = self.ax.plot([], [], label="新闻舆情", color="orange")
        self.line_overall, = self.ax.plot([], [], label="整体舆情", color="red")
        
        # 添加图例
        self.ax.legend(loc='upper right')
        
        # 刷新画布
        self.canvas.draw()

    def _create_key_events_area(self, layout):
        """创建关键事件区域"""
        events_frame = QFrame()
        events_frame.setFrameStyle(QFrame.StyledPanel)
        
        events_layout = QVBoxLayout(events_frame)
        
        # 标题
        title_label = QLabel("关键事件")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        events_layout.addWidget(title_label)
        
        # 事件列表
        self.events_list = QListWidget()
        events_layout.addWidget(self.events_list)
        
        # 事件详情框架
        event_detail_frame = QFrame()
        event_detail_frame.setFrameStyle(QFrame.StyledPanel)
        event_detail_frame.setMaximumHeight(100)
        
        event_detail_layout = QVBoxLayout(event_detail_frame)
        
        # 事件详情标签
        self.event_detail_label = QLabel("选择一个事件查看详情")
        self.event_detail_label.setWordWrap(True)
        event_detail_layout.addWidget(self.event_detail_label)
        
        events_layout.addWidget(event_detail_frame)
        
        # 连接信号
        self.events_list.itemSelectionChanged.connect(self._on_event_selection_changed)

    def _update_sentiment_data(self):
        """更新舆情数据"""
        try:
            if self._bettafish_agent and hasattr(self._bettafish_agent, 'get_sentiment_analysis'):
                sentiment_data = self._bettafish_agent.get_sentiment_analysis()
                if sentiment_data:
                    self._sentiment_data.update(sentiment_data)
                    self._sentiment_data['_data_loaded'] = True

            self._update_gauges()

            if CHARTS_AVAILABLE:
                self._update_chart()

            self._update_key_events()

            self._check_sentiment_alerts()

            self.sentiment_update.emit(self._sentiment_data)

        except Exception as e:
            logger.error(f"更新舆情数据失败: {e}")

    def _update_gauges(self):
        """更新舆情仪表盘"""
        if not self._sentiment_data.get('_data_loaded', False):
            for name in ['\u6574\u4f53\u8206\u60c5', '\u5e02\u573a\u60c5\u7eea', '\u793e\u4ea4\u8206\u60c5', '\u65b0\u95fb\u8206\u60c5']:
                gauge_widgets = getattr(self, f"{name.replace(' ', '_').lower()}_gauge", None)
                if gauge_widgets:
                    gauge_widgets[0].setValue(0)
                    gauge_widgets[1].setText("\u6570\u636e\u52a0\u8f7d\u4e2d...")
            return

        overall_value = int(self._sentiment_data.get('overall_sentiment', 0) * 100)
        overall_gauge, overall_label = getattr(self, '\u6574\u4f53\u8206\u60c5_gauge')
        overall_gauge.setValue(overall_value)
        overall_label.setText(f"{self._sentiment_data.get('overall_sentiment', 0):.2f}")

        market_value = int(self._sentiment_data.get('market_sentiment', 0) * 100)
        market_gauge, market_label = getattr(self, '\u5e02\u573a\u60c5\u7eea_gauge')
        market_gauge.setValue(market_value)
        market_label.setText(f"{self._sentiment_data.get('market_sentiment', 0):.2f}")

        social_value = int(self._sentiment_data.get('social_sentiment', 0) * 100)
        social_gauge, social_label = getattr(self, '\u793e\u4ea4\u8206\u60c5_gauge')
        social_gauge.setValue(social_value)
        social_label.setText(f"{self._sentiment_data.get('social_sentiment', 0):.2f}")

        news_value = int(self._sentiment_data.get('news_sentiment', 0) * 100)
        news_gauge, news_label = getattr(self, '\u65b0\u95fb\u8206\u60c5_gauge')
        news_gauge.setValue(news_value)
        news_label.setText(f"{self._sentiment_data.get('news_sentiment', 0):.2f}")

    def _update_chart(self):
        """更新舆情图表"""
        # 获取趋势数据
        trend_data = self._sentiment_data.get('sentiment_trend', [])
        
        if not trend_data:
            return
        
        # 提取时间戳和数值
        timestamps = [item.get('timestamp', datetime.now()) for item in trend_data]
        market_values = [item.get('market_sentiment', 0.5) for item in trend_data]
        social_values = [item.get('social_sentiment', 0.5) for item in trend_data]
        news_values = [item.get('news_sentiment', 0.5) for item in trend_data]
        overall_values = [item.get('overall_sentiment', 0.5) for item in trend_data]
        
        # 更新线条数据
        self.line_market.set_data(range(len(market_values)), market_values)
        self.line_social.set_data(range(len(social_values)), social_values)
        self.line_news.set_data(range(len(news_values)), news_values)
        self.line_overall.set_data(range(len(overall_values)), overall_values)
        
        # 更新坐标轴范围
        if timestamps:
            self.ax.set_xlim(0, max(1, len(timestamps)))
            self.ax.set_ylim(0, 1)
        
        # 刷新画布
        self.canvas.draw()

    def _update_key_events(self):
        """更新关键事件列表"""
        # 获取关键事件
        events = self._sentiment_data.get('key_events', [])
        
        # 清除现有事件
        self.events_list.clear()
        
        # 添加新事件
        for event in events:
            item = QListWidgetItem()
            
            # 设置事件文本
            event_time = event.get('timestamp', datetime.now())
            event_title = event.get('title', '未知事件')
            event_sentiment = event.get('sentiment_score', 0.5)
            
            # 根据情绪值设置颜色
            if event_sentiment > 0.7:
                item.setBackground(QColor(46, 204, 113, 100))  # 绿色
            elif event_sentiment < 0.3:
                item.setBackground(QColor(231, 76, 60, 100))  # 红色
            else:
                item.setBackground(QColor(241, 196, 15, 100))  # 黄色
            
            # 设置文本
            item.setText(f"{event_time.strftime('%H:%M:%S')} - {event_title} (情绪: {event_sentiment:.2f})")
            
            # 存储事件数据
            item.setData(Qt.UserRole, event)
            
            # 添加到列表
            self.events_list.addItem(item)

    def _check_sentiment_alerts(self):
        """检查舆情告警"""
        # 获取告警阈值
        threshold = self.alert_threshold_slider.value() / 100.0
        
        # 检查整体舆情
        overall_sentiment = self._sentiment_data.get('overall_sentiment', 0.5)
        
        if overall_sentiment < threshold:
            # 负面舆情告警
            self.sentiment_alert.emit("warning", f"检测到负面舆情，当前值: {overall_sentiment:.2f}")
        elif overall_sentiment > 1 - threshold:
            # 正面舆情告警
            self.sentiment_alert.emit("info", f"检测到正面舆情，当前值: {overall_sentiment:.2f}")

    def _on_event_selection_changed(self):
        """处理事件选择变化"""
        # 获取当前选中的事件
        current_item = self.events_list.currentItem()
        
        if current_item:
            # 获取事件数据
            event_data = current_item.data(Qt.UserRole)
            
            # 更新事件详情
            event_time = event_data.get('timestamp', datetime.now())
            event_title = event_data.get('title', '未知事件')
            event_description = event_data.get('description', '无描述')
            event_sentiment = event_data.get('sentiment_score', 0.5)
            
            # 更新详情标签
            detail_text = f"时间: {event_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            detail_text += f"事件: {event_title}\n"
            detail_text += f"情绪值: {event_sentiment:.2f}\n"
            detail_text += f"描述: {event_description}"
            
            self.event_detail_label.setText(detail_text)
        else:
            # 清空详情
            self.event_detail_label.setText("选择一个事件查看详情")

    def _toggle_realtime_update(self, enabled):
        """切换实时更新"""
        if enabled:
            self._update_timer.start(30000)  # 30秒
        else:
            self._update_timer.stop()

    def _update_alert_threshold(self, value):
        """更新告警阈值"""
        threshold = value / 100.0
        logger.info(f"更新告警阈值: {threshold}")
        self._sentiment_data['alert_threshold'] = threshold
        self._check_sentiment_alerts()

    def closeEvent(self, event):
        """关闭事件处理"""
        # 停止定时器
        self._update_timer.stop()
        
        # 调用父类关闭事件
        super().closeEvent(event)