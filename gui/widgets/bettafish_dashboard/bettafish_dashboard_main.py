#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BettaFish仪表板主组件
提供多智能体系统的可视化监控和分析界面
"""

import sys
import os
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QSplitter,
    QFrame, QLabel, QPushButton, QGridLayout, QSizePolicy,
    QScrollArea, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QPalette, QColor, QPixmap, QIcon

from loguru import logger

from core.agents.bettafish_agent import BettaFishAgent
from core.services.bettafish_monitoring_service import BettaFishMonitoringService

from .sentiment_monitor_panel import SentimentMonitorPanel
from .news_impact_panel import NewsImpactPanel
from .multi_agent_status_panel import MultiAgentStatusPanel
from .trading_signal_panel import TradingSignalPanel
from .risk_assessment_panel import RiskAssessmentPanel


class BettaFishDashboard(QWidget):
    """
    BettaFish仪表板主组件
    
    提供多个监控面板的集成界面：
    - 舆情监控面板
    - 新闻影响评估
    - 多智能体状态监控
    - 交易信号面板
    - 风险评估仪表板
    """

    # 信号定义
    data_updated = pyqtSignal()  # 数据更新信号
    alert_triggered = pyqtSignal(str)  # 告警信号

    def __init__(self, parent=None, bettafish_agent: BettaFishAgent = None):
        """
        初始化BettaFish仪表板

        Args:
            parent: 父组件
            bettafish_agent: BettaFish代理实例
        """
        super().__init__(parent)
        
        # 初始化组件
        self._bettafish_agent = bettafish_agent
        self._monitoring_service = None
        
        # 定时器用于刷新仪表板
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_dashboard)
        
        # 存储各个面板
        self._panels = {}
        
        # 初始化UI
        self._init_ui()
        
        # 初始化监控服务
        self._init_monitoring_service()
        
        # 启动定时器
        self._update_timer.start(5000)  # 每5秒更新一次

    def _init_ui(self):
        """初始化UI"""
        # 设置主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 创建标题区域
        self._create_title_bar(main_layout)
        
        # 创建仪表板选项卡
        self._create_dashboard_tabs(main_layout)
        
        # 创建状态栏
        self._create_status_bar(main_layout)

    def _create_title_bar(self, layout):
        """创建标题栏"""
        title_frame = QFrame()
        title_frame.setFrameStyle(QFrame.StyledPanel)
        
        title_layout = QHBoxLayout(title_frame)
        
        # 标题
        title_label = QLabel("BettaFish 多智能体系统仪表板")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2C3E50;")
        
        title_layout.addWidget(title_label)
        
        # 添加按钮区域
        button_layout = QHBoxLayout()
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_dashboard)
        button_layout.addWidget(refresh_btn)
        
        # 设置按钮
        settings_btn = QPushButton("设置")
        settings_btn.clicked.connect(self._open_settings)
        button_layout.addWidget(settings_btn)
        
        title_layout.addLayout(button_layout)
        
        layout.addWidget(title_frame)

    def _create_dashboard_tabs(self, layout):
        """创建仪表板选项卡"""
        # 创建选项卡容器
        self.tab_widget = QTabWidget()
        
        # 创建各个面板
        self._create_sentiment_panel()
        self._create_news_impact_panel()
        self._create_multi_agent_status_panel()
        self._create_trading_signal_panel()
        self._create_risk_assessment_panel()
        
        # 添加选项卡到主容器
        for name, panel in self._panels.items():
            self.tab_widget.addTab(panel, name)
        
        layout.addWidget(self.tab_widget)

    def _create_sentiment_panel(self):
        """创建舆情监控面板"""
        try:
            self._panels["舆情监控"] = SentimentMonitorPanel(
                parent=self,
                bettafish_agent=self._bettafish_agent
            )
        except Exception as e:
            logger.error(f"创建舆情监控面板失败: {e}")
            self._panels["舆情监控"] = QLabel("舆情监控面板加载失败")

    def _create_news_impact_panel(self):
        """创建新闻影响评估面板"""
        try:
            self._panels["新闻影响"] = NewsImpactPanel(
                parent=self,
                bettafish_agent=self._bettafish_agent
            )
        except Exception as e:
            logger.error(f"创建新闻影响面板失败: {e}")
            self._panels["新闻影响"] = QLabel("新闻影响面板加载失败")

    def _create_multi_agent_status_panel(self):
        """创建多智能体状态监控面板"""
        try:
            self._panels["多智能体状态"] = MultiAgentStatusPanel(
                parent=self,
                monitoring_service=self._monitoring_service
            )
        except Exception as e:
            logger.error(f"创建多智能体状态面板失败: {e}")
            self._panels["多智能体状态"] = QLabel("多智能体状态面板加载失败")

    def _create_trading_signal_panel(self):
        """创建交易信号面板"""
        try:
            self._panels["交易信号"] = TradingSignalPanel(
                parent=self,
                bettafish_agent=self._bettafish_agent
            )
        except Exception as e:
            logger.error(f"创建交易信号面板失败: {e}")
            self._panels["交易信号"] = QLabel("交易信号面板加载失败")

    def _create_risk_assessment_panel(self):
        """创建风险评估面板"""
        try:
            self._panels["风险评估"] = RiskAssessmentPanel(
                parent=self,
                bettafish_agent=self._bettafish_agent
            )
        except Exception as e:
            logger.error(f"创建风险评估面板失败: {e}")
            self._panels["风险评估"] = QLabel("风险评估面板加载失败")

    def _create_status_bar(self, layout):
        """创建状态栏"""
        status_frame = QFrame()
        status_frame.setMaximumHeight(40)
        status_frame.setFrameStyle(QFrame.StyledPanel)
        
        status_layout = QHBoxLayout(status_frame)
        
        # 系统状态指示
        self.system_status_label = QLabel("● 系统状态：运行中")
        self.system_status_label.setStyleSheet("color: green; font-weight: bold;")
        
        # 最后更新时间
        self.last_update_label = QLabel(f"最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 数据源状态
        self.data_source_label = QLabel("● 数据源：已连接")
        self.data_source_label.setStyleSheet("color: green; font-weight: bold;")
        
        status_layout.addWidget(self.system_status_label)
        status_layout.addWidget(self.last_update_label)
        status_layout.addWidget(self.data_source_label)
        
        layout.addWidget(status_frame)

    def _init_monitoring_service(self):
        """初始化监控服务"""
        try:
            if not self._monitoring_service:
                self._monitoring_service = BettaFishMonitoringService()
                logger.info("BettaFish监控服务初始化成功")
        except Exception as e:
            logger.error(f"BettaFish监控服务初始化失败: {e}")

    def _update_dashboard(self):
        """更新仪表板数据"""
        try:
            # 更新各个面板
            for panel in self._panels.values():
                if hasattr(panel, 'update_data'):
                    panel.update_data()
            
            # 更新状态栏
            self.last_update_label.setText(f"最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 发出数据更新信号
            self.data_updated.emit()
            
        except Exception as e:
            logger.error(f"更新仪表板失败: {e}")

    def _refresh_dashboard(self):
        """刷新仪表板"""
        logger.info("刷新BettaFish仪表板")
        self._update_dashboard()

    def _open_settings(self):
        """打开设置对话框"""
        logger.info("打开BettaFish仪表板设置")
        # TODO: 实现设置对话框

    def closeEvent(self, event):
        """关闭事件处理"""
        # 停止定时器
        self._update_timer.stop()
        
        # 关闭各个面板
        for panel in self._panels.values():
            if hasattr(panel, 'close'):
                panel.close()
        
        # 调用父类关闭事件
        super().closeEvent(event)