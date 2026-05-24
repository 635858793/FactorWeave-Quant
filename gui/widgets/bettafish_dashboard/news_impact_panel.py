#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新闻影响评估面板
监控和分析新闻事件对股价的影响
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


class NewsImpactPanel(QWidget):
    """
    新闻影响评估面板
    
    提供新闻事件影响分析和评估功能：
    - 新闻事件列表
    - 影响程度评估
    - 价格影响图表
    - 历史影响分析
    """

    # 信号定义
    news_alert = pyqtSignal(str, str)  # 新闻告警信号(级别, 消息)
    news_update = pyqtSignal(dict)  # 新闻更新信号

    def __init__(self, parent=None, bettafish_agent: BettaFishAgent = None):
        """
        初始化新闻影响评估面板

        Args:
            parent: 父组件
            bettafish_agent: BettaFish代理实例
        """
        super().__init__(parent)
        
        # 初始化组件
        self._bettafish_agent = bettafish_agent
        
        # 新闻数据
        self._news_data = {
            'recent_news': [],  # 最新新闻
            'high_impact_news': [],  # 高影响新闻
            'impact_analysis': {},  # 影响分析
            'historical_impacts': [],  # 历史影响数据
            'impact_sources': {},  # 数据源状态
        }
        
        # 定时器用于刷新新闻数据
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_news_data)
        
        # 初始化UI
        self._init_ui()
        
        # 启动定时器
        self._update_timer.start(60000)  # 每分钟更新一次

    def _init_ui(self):
        """初始化UI"""
        # 设置主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 创建控制面板
        self._create_control_panel(main_layout)
        
        # 创建选项卡区域
        self._create_news_tabs(main_layout)

    def _create_control_panel(self, layout):
        """创建控制面板"""
        control_frame = QFrame()
        control_frame.setFrameStyle(QFrame.StyledPanel)
        
        control_layout = QHBoxLayout(control_frame)
        
        # 新闻源选择
        control_layout.addWidget(QLabel("新闻源:"))
        self.news_source_combo = QComboBox()
        self.news_source_combo.addItems(["全部", "财经媒体", "社交媒体", "官方公告"])
        self.news_source_combo.currentTextChanged.connect(self._update_news_data)
        control_layout.addWidget(self.news_source_combo)
        
        # 影响类型过滤
        control_layout.addWidget(QLabel("影响类型:"))
        self.impact_type_combo = QComboBox()
        self.impact_type_combo.addItems(["全部", "正面", "负面", "中性"])
        self.impact_type_combo.currentTextChanged.connect(self._update_news_data)
        control_layout.addWidget(self.impact_type_combo)
        
        # 实时更新开关
        self.realtime_update_check = QCheckBox("实时更新")
        self.realtime_update_check.setChecked(True)
        self.realtime_update_check.toggled.connect(self._toggle_realtime_update)
        control_layout.addWidget(self.realtime_update_check)
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._update_news_data)
        control_layout.addWidget(refresh_btn)
        
        layout.addWidget(control_frame)

    def _create_news_tabs(self, layout):
        """创建新闻选项卡"""
        # 创建选项卡容器
        self.news_tab_widget = QTabWidget()
        
        # 创建各个选项卡
        self._create_recent_news_tab()
        self._create_impact_analysis_tab()
        self._create_historical_impacts_tab()
        
        layout.addWidget(self.news_tab_widget)

    def _create_recent_news_tab(self):
        """创建最新新闻选项卡"""
        recent_news_widget = QWidget()
        recent_news_layout = QVBoxLayout(recent_news_widget)
        
        # 新闻列表
        self.news_list = QListWidget()
        recent_news_layout.addWidget(self.news_list)
        
        # 新闻详情
        news_detail_frame = QFrame()
        news_detail_frame.setFrameStyle(QFrame.StyledPanel)
        news_detail_frame.setMinimumHeight(150)
        
        news_detail_layout = QVBoxLayout(news_detail_frame)
        
        # 标题
        title_label = QLabel("新闻详情")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        news_detail_layout.addWidget(title_label)
        
        # 详情内容
        self.news_detail_text = QLabel("选择一个新闻查看详情")
        self.news_detail_text.setWordWrap(True)
        news_detail_layout.addWidget(self.news_detail_text)
        
        recent_news_layout.addWidget(news_detail_frame)
        
        # 连接信号
        self.news_list.itemSelectionChanged.connect(self._on_news_selection_changed)
        
        # 添加到选项卡
        self.news_tab_widget.addTab(recent_news_widget, "最新新闻")

    def _create_impact_analysis_tab(self):
        """创建影响分析选项卡"""
        impact_widget = QWidget()
        impact_layout = QVBoxLayout(impact_widget)
        
        # 高影响新闻
        high_impact_group = QGroupBox("高影响新闻")
        high_impact_layout = QVBoxLayout(high_impact_group)
        
        self.high_impact_table = QTableWidget()
        self.high_impact_table.setColumnCount(5)
        self.high_impact_table.setHorizontalHeaderLabels([
            "时间", "新闻标题", "影响股票", "影响程度", "价格变化"
        ])
        self.high_impact_table.setAlternatingRowColors(True)
        self.high_impact_table.setSelectionBehavior(QTableWidget.SelectRows)
        high_impact_layout.addWidget(self.high_impact_table)
        
        impact_layout.addWidget(high_impact_group)
        
        # 影响分析图表
        if CHARTS_AVAILABLE:
            self._create_impact_chart(impact_layout)
        else:
            placeholder_label = QLabel("图表功能需要安装matplotlib库")
            placeholder_label.setAlignment(Qt.AlignCenter)
            impact_layout.addWidget(placeholder_label)
        
        # 添加到选项卡
        self.news_tab_widget.addTab(impact_widget, "影响分析")

    def _create_historical_impacts_tab(self):
        """创建历史影响选项卡"""
        historical_widget = QWidget()
        historical_layout = QVBoxLayout(historical_widget)
        
        # 历史影响图表
        if CHARTS_AVAILABLE:
            self._create_historical_chart(historical_layout)
        else:
            placeholder_label = QLabel("图表功能需要安装matplotlib库")
            placeholder_label.setAlignment(Qt.AlignCenter)
            historical_layout.addWidget(placeholder_label)
        
        # 影响统计
        stats_group = QGroupBox("影响统计")
        stats_layout = QGridLayout(stats_group)
        
        # 统计指标
        self.impact_stats = {
            'total_news': QLabel("0"),
            'positive_impact': QLabel("0%"),
            'negative_impact': QLabel("0%"),
            'neutral_impact': QLabel("0%"),
            'avg_impact_time': QLabel("0分钟")
        }
        
        # 添加统计标签
        stats_layout.addWidget(QLabel("新闻总数:"), 0, 0)
        stats_layout.addWidget(self.impact_stats['total_news'], 0, 1)
        
        stats_layout.addWidget(QLabel("正面影响:"), 0, 2)
        stats_layout.addWidget(self.impact_stats['positive_impact'], 0, 3)
        
        stats_layout.addWidget(QLabel("负面影响:"), 1, 0)
        stats_layout.addWidget(self.impact_stats['negative_impact'], 1, 1)
        
        stats_layout.addWidget(QLabel("中性影响:"), 1, 2)
        stats_layout.addWidget(self.impact_stats['neutral_impact'], 1, 3)
        
        stats_layout.addWidget(QLabel("平均影响时间:"), 2, 0)
        stats_layout.addWidget(self.impact_stats['avg_impact_time'], 2, 1)
        
        historical_layout.addWidget(stats_group)
        
        # 添加到选项卡
        self.news_tab_widget.addTab(historical_widget, "历史影响")

    def _create_impact_chart(self, layout):
        """创建影响分析图表"""
        # 创建图形和画布
        self.impact_figure = Figure(figsize=(5, 3), dpi=100)
        self.impact_canvas = FigureCanvas(self.impact_figure)
        
        # 创建子图
        self.impact_ax = self.impact_figure.add_subplot(111)
        
        # 初始化图表
        self.impact_ax.set_title("新闻影响分析")
        self.impact_ax.set_ylabel("价格变化 (%)")
        self.impact_ax.set_xlabel("时间")
        
        # 添加到布局
        layout.addWidget(self.impact_canvas)
        
        # 初始化线条
        self.impact_line, = self.impact_ax.plot([], [], label="价格变化", color="blue")
        
        # 添加图例
        self.impact_ax.legend(loc='upper right')
        
        # 刷新画布
        self.impact_canvas.draw()

    def _create_historical_chart(self, layout):
        """创建历史影响图表"""
        # 创建图形和画布
        self.historical_figure = Figure(figsize=(5, 3), dpi=100)
        self.historical_canvas = FigureCanvas(self.historical_figure)
        
        # 创建子图
        self.historical_ax = self.historical_figure.add_subplot(111)
        
        # 初始化图表
        self.historical_ax.set_title("历史影响分析")
        self.historical_ax.set_ylabel("影响程度")
        self.historical_ax.set_xlabel("时间")
        
        # 添加到布局
        layout.addWidget(self.historical_canvas)
        
        # 初始化线条
        self.historical_line, = self.historical_ax.plot([], [], label="历史影响", color="green")
        
        # 添加图例
        self.historical_ax.legend(loc='upper right')
        
        # 刷新画布
        self.historical_canvas.draw()

    def _update_news_data(self):
        """更新新闻数据"""
        try:
            # 从BettaFish Agent获取新闻数据
            if self._bettafish_agent:
                # 模拟从Agent获取数据（实际实现中应调用Agent的方法）
                news_data = self._bettafish_agent.get_news_analysis()
                if news_data:
                    self._news_data.update(news_data)
            
            # 更新最新新闻列表
            self._update_recent_news()
            
            # 更新高影响新闻表格
            self._update_high_impact_table()
            
            # 更新影响分析图表
            if CHARTS_AVAILABLE:
                self._update_impact_chart()
            
            # 更新历史影响图表
            if CHARTS_AVAILABLE:
                self._update_historical_chart()
            
            # 更新影响统计
            self._update_impact_stats()
            
            # 检查新闻告警
            self._check_news_alerts()
            
            # 发出更新信号
            self.news_update.emit(self._news_data)
            
        except Exception as e:
            logger.error(f"更新新闻数据失败: {e}")

    def _update_recent_news(self):
        """更新最新新闻列表"""
        # 获取最新新闻
        recent_news = self._news_data.get('recent_news', [])
        
        # 清除现有新闻
        self.news_list.clear()
        
        # 添加新新闻
        for news in recent_news:
            item = QListWidgetItem()
            
            # 设置新闻文本
            news_time = news.get('timestamp', datetime.now())
            news_title = news.get('title', '未知新闻')
            news_impact = news.get('impact_score', 0.0)
            
            # 根据影响值设置颜色
            if news_impact > 0.7:
                item.setBackground(QColor(46, 204, 113, 100))  # 绿色
            elif news_impact < 0.3:
                item.setBackground(QColor(231, 76, 60, 100))  # 红色
            else:
                item.setBackground(QColor(241, 196, 15, 100))  # 黄色
            
            # 设置文本
            item.setText(f"{news_time.strftime('%H:%M:%S')} - {news_title} (影响: {news_impact:.2f})")
            
            # 存储新闻数据
            item.setData(Qt.UserRole, news)
            
            # 添加到列表
            self.news_list.addItem(item)

    def _update_high_impact_table(self):
        """更新高影响新闻表格"""
        # 获取高影响新闻
        high_impact_news = self._news_data.get('high_impact_news', [])
        
        # 设置表格行数
        self.high_impact_table.setRowCount(len(high_impact_news))
        
        # 添加数据
        for row, news in enumerate(high_impact_news):
            # 时间
            time_item = QTableWidgetItem(news.get('timestamp', datetime.now()).strftime('%H:%M:%S'))
            self.high_impact_table.setItem(row, 0, time_item)
            
            # 新闻标题
            title_item = QTableWidgetItem(news.get('title', '未知新闻'))
            self.high_impact_table.setItem(row, 1, title_item)
            
            # 影响股票
            stock_item = QTableWidgetItem(news.get('related_stocks', '未知'))
            self.high_impact_table.setItem(row, 2, stock_item)
            
            # 影响程度
            impact_item = QTableWidgetItem(f"{news.get('impact_score', 0.0):.2f}")
            self.high_impact_table.setItem(row, 3, impact_item)
            
            # 价格变化
            price_change_item = QTableWidgetItem(f"{news.get('price_change', 0.0):.2f}%")
            self.high_impact_table.setItem(row, 4, price_change_item)
            
            # 设置行高
            self.high_impact_table.setRowHeight(row, 30)

    def _update_impact_chart(self):
        """更新影响分析图表"""
        # 获取影响分析数据
        impact_data = self._news_data.get('impact_analysis', {})
        
        if not impact_data:
            return
        
        # 提取数据
        timestamps = impact_data.get('timestamps', [])
        price_changes = impact_data.get('price_changes', [])
        
        if not timestamps or not price_changes:
            return
        
        # 更新线条数据
        self.impact_line.set_data(range(len(price_changes)), price_changes)
        
        # 更新坐标轴范围
        self.impact_ax.set_xlim(0, max(1, len(timestamps)))
        max_change = max(abs(min(price_changes, default=0)), abs(max(price_changes, default=1)))
        self.impact_ax.set_ylim(-max_change * 1.1, max_change * 1.1)
        
        # 刷新画布
        self.impact_canvas.draw()

    def _update_historical_chart(self):
        """更新历史影响图表"""
        # 获取历史影响数据
        historical_data = self._news_data.get('historical_impacts', [])
        
        if not historical_data:
            return
        
        # 提取数据
        timestamps = [item.get('timestamp', datetime.now()) for item in historical_data]
        impact_values = [item.get('impact_score', 0.5) for item in historical_data]
        
        # 更新线条数据
        self.historical_line.set_data(range(len(impact_values)), impact_values)
        
        # 更新坐标轴范围
        if timestamps:
            self.historical_ax.set_xlim(0, max(1, len(timestamps)))
            self.historical_ax.set_ylim(0, 1)
        
        # 刷新画布
        self.historical_canvas.draw()

    def _update_impact_stats(self):
        """更新影响统计"""
        # 获取统计数据
        stats = self._news_data.get('impact_statistics', {})
        
        # 更新统计标签
        self.impact_stats['total_news'].setText(str(stats.get('total_count', 0)))
        self.impact_stats['positive_impact'].setText(f"{stats.get('positive_percentage', 0):.1f}%")
        self.impact_stats['negative_impact'].setText(f"{stats.get('negative_percentage', 0):.1f}%")
        self.impact_stats['neutral_impact'].setText(f"{stats.get('neutral_percentage', 0):.1f}%")
        self.impact_stats['avg_impact_time'].setText(f"{stats.get('average_impact_time', 0):.0f}分钟")

    def _check_news_alerts(self):
        """检查新闻告警"""
        # 获取高影响新闻
        high_impact_news = self._news_data.get('high_impact_news', [])
        
        # 检查是否有高影响新闻
        for news in high_impact_news:
            impact_score = news.get('impact_score', 0.0)
            if impact_score > 0.8:
                # 高影响新闻告警
                self.news_alert.emit(
                    "warning", 
                    f"检测到高影响新闻: {news.get('title', '未知新闻')} (影响: {impact_score:.2f})"
                )

    def _on_news_selection_changed(self):
        """处理新闻选择变化"""
        # 获取当前选中的新闻
        current_item = self.news_list.currentItem()
        
        if current_item:
            # 获取新闻数据
            news_data = current_item.data(Qt.UserRole)
            
            # 更新新闻详情
            news_time = news_data.get('timestamp', datetime.now())
            news_title = news_data.get('title', '未知新闻')
            news_content = news_data.get('content', '无内容')
            news_impact = news_data.get('impact_score', 0.0)
            news_source = news_data.get('source', '未知来源')
            related_stocks = news_data.get('related_stocks', '未知')
            
            # 更新详情标签
            detail_text = f"时间: {news_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            detail_text += f"标题: {news_title}\n"
            detail_text += f"来源: {news_source}\n"
            detail_text += f"影响程度: {news_impact:.2f}\n"
            detail_text += f"相关股票: {related_stocks}\n"
            detail_text += f"内容: {news_content}"
            
            self.news_detail_text.setText(detail_text)
        else:
            # 清空详情
            self.news_detail_text.setText("选择一个新闻查看详情")

    def _toggle_realtime_update(self, enabled):
        """切换实时更新"""
        if enabled:
            self._update_timer.start(60000)  # 1分钟
        else:
            self._update_timer.stop()

    def closeEvent(self, event):
        """关闭事件处理"""
        # 停止定时器
        self._update_timer.stop()
        
        # 调用父类关闭事件
        super().closeEvent(event)