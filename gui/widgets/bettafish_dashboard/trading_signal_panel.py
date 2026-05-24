#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易信号面板 - BettaFish仪表板组件
显示综合交易建议和信号
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QFrame, QGroupBox, QGridLayout, 
    QPushButton, QTabWidget, QTextEdit, QScrollArea,
    QProgressBar, QLCDNumber
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QPalette, QPixmap

from loguru import logger

# 临时移除BettaFishAgent依赖以避免循环导入
# from core.agents.bettafish_agent import BettaFishAgent


class TradingSignalPanel(QWidget):
    """
    交易信号面板
    
    功能：
    1. 显示综合交易信号
    2. 信号强度和置信度
    3. 历史信号统计
    4. 实时信号更新
    """

    # 信号定义
    signal_selected = pyqtSignal(str)  # 信号选择信号
    signal_confirmed = pyqtSignal(str, dict)  # 信号确认信号

    def __init__(self, parent=None, bettafish_agent=None):
        """
        初始化交易信号面板

        Args:
            parent: 父组件
            bettafish_agent: BettaFish代理实例
        """
        super().__init__(parent)
        
        self._bettafish_agent = bettafish_agent
        self._signals_data = []
        self._signal_stats = {}
        
        # 初始化UI
        self._init_ui()
        
        # 初始化定时器
        self._init_timer()
        
        # 初始化数据
        self._init_data()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 创建标题
        self._create_title(layout)
        
        # 创建主内容区域
        self._create_content(layout)

    def _create_title(self, layout):
        """创建标题"""
        title_frame = QFrame()
        title_frame.setFrameStyle(QFrame.StyledPanel)
        
        title_layout = QHBoxLayout(title_frame)
        
        # 标题标签
        title_label = QLabel("交易信号分析")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_layout.addWidget(title_label)
        
        # 状态指示器
        self.status_label = QLabel("● 实时监控")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        title_layout.addWidget(self.status_label)
        
        layout.addWidget(title_frame)

    def _create_content(self, layout):
        """创建主内容区域"""
        # 创建选项卡
        tab_widget = QTabWidget()
        
        # 信号概览
        overview_widget = QWidget()
        self._create_overview_tab(overview_widget)
        tab_widget.addTab(overview_widget, "信号概览")
        
        # 信号详情
        detail_widget = QWidget()
        self._create_detail_tab(detail_widget)
        tab_widget.addTab(detail_widget, "信号详情")
        
        # 统计信息
        stats_widget = QWidget()
        self._create_stats_tab(stats_widget)
        tab_widget.addTab(stats_widget, "统计信息")
        
        layout.addWidget(tab_widget)

    def _create_overview_tab(self, widget):
        """创建信号概览选项卡"""
        layout = QVBoxLayout(widget)
        
        # 当前信号状态
        status_group = QGroupBox("当前信号状态")
        status_layout = QGridLayout(status_group)
        
        # 信号类型统计
        self.buy_signals_label = QLabel("0")
        self.sell_signals_label = QLabel("0")
        self.hold_signals_label = QLabel("0")
        self.total_signals_label = QLabel("0")
        
        status_layout.addWidget(QLabel("买入信号:"), 0, 0)
        status_layout.addWidget(self.buy_signals_label, 0, 1)
        status_layout.addWidget(QLabel("卖出信号:"), 1, 0)
        status_layout.addWidget(self.sell_signals_label, 1, 1)
        status_layout.addWidget(QLabel("持有信号:"), 2, 0)
        status_layout.addWidget(self.hold_signals_label, 2, 1)
        status_layout.addWidget(QLabel("总信号数:"), 3, 0)
        status_layout.addWidget(self.total_signals_label, 3, 1)
        
        layout.addWidget(status_group)
        
        # 最新信号表格
        signals_group = QGroupBox("最新信号")
        signals_layout = QVBoxLayout(signals_group)
        
        self.signals_table = QTableWidget(0, 6)
        self.signals_table.setHorizontalHeaderLabels([
            "时间", "股票代码", "信号类型", "强度", "置信度", "状态"
        ])
        self.signals_table.horizontalHeader().setStretchLastSection(True)
        self.signals_table.setAlternatingRowColors(True)
        self.signals_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        signals_layout.addWidget(self.signals_table)
        layout.addWidget(signals_group)

    def _create_detail_tab(self, widget):
        """创建信号详情选项卡"""
        layout = QVBoxLayout(widget)
        
        # 信号详情显示
        detail_group = QGroupBox("信号详情")
        detail_layout = QVBoxLayout(detail_group)
        
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        detail_layout.addWidget(self.detail_text)
        
        layout.addWidget(detail_group)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.confirm_btn = QPushButton("确认信号")
        self.confirm_btn.clicked.connect(self._confirm_signal)
        self.confirm_btn.setEnabled(False)
        button_layout.addWidget(self.confirm_btn)
        
        self.dismiss_btn = QPushButton("忽略信号")
        self.dismiss_btn.clicked.connect(self._dismiss_signal)
        self.dismiss_btn.setEnabled(False)
        button_layout.addWidget(self.dismiss_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _create_stats_tab(self, widget):
        """创建统计信息选项卡"""
        layout = QVBoxLayout(widget)
        
        # 成功率统计
        success_group = QGroupBox("信号成功率")
        success_layout = QGridLayout(success_group)
        
        self.success_rate_label = QLabel("0.0%")
        self.accuracy_label = QLabel("0.0%")
        self.profit_rate_label = QLabel("0.0%")
        
        success_layout.addWidget(QLabel("总成功率:"), 0, 0)
        success_layout.addWidget(self.success_rate_label, 0, 1)
        success_layout.addWidget(QLabel("准确率:"), 1, 0)
        success_layout.addWidget(self.accuracy_label, 1, 1)
        success_layout.addWidget(QLabel("盈利率:"), 2, 0)
        success_layout.addWidget(self.profit_rate_label, 2, 1)
        
        layout.addWidget(success_group)
        
        # 信号强度分布
        strength_group = QGroupBox("信号强度分布")
        strength_layout = QVBoxLayout(strength_group)
        
        self.strength_chart = QLabel("信号强度图表")
        self.strength_chart.setMinimumHeight(200)
        self.strength_chart.setStyleSheet("border: 1px solid #ccc; background-color: #f9f9f9;")
        strength_layout.addWidget(self.strength_chart)
        
        layout.addWidget(strength_group)

    def _init_timer(self):
        """初始化定时器"""
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_signals)
        self._update_timer.start(10000)  # 每10秒更新一次

    def _init_data(self):
        """初始化数据"""
        # 加载历史信号数据
        self._load_historical_signals()
        
        # 更新显示
        self._update_display()

    def _load_historical_signals(self):
        """加载历史信号数据"""
        try:
            if self._bettafish_agent and hasattr(self._bettafish_agent, 'get_trading_signals'):
                agent_signals = self._bettafish_agent.get_trading_signals()
                if agent_signals:
                    self._signals_data = agent_signals
                    return

            self._signals_data = []
            logger.info("交易信号数据源未连接，显示暂无数据")
        except Exception as e:
            logger.error(f"加载历史信号数据失败: {e}")
            self._signals_data = []

    def _update_signals(self):
        """更新信号数据"""
        try:
            if self._bettafish_agent and hasattr(self._bettafish_agent, 'get_trading_signals'):
                agent_signals = self._bettafish_agent.get_trading_signals()
                if agent_signals:
                    self._signals_data = agent_signals

            self._update_display()
        except Exception as e:
            logger.error(f"更新信号数据失败: {e}")

    def _update_display(self):
        """更新显示"""
        try:
            # 更新信号统计
            self._update_signal_stats()
            
            # 更新信号表格
            self._update_signals_table()
            
            # 更新统计信息
            self._update_statistics()
            
        except Exception as e:
            logger.error(f"更新显示失败: {e}")

    def _update_signal_stats(self):
        """更新信号统计"""
        buy_count = sum(1 for signal in self._signals_data if signal.get("signal_type") == "BUY")
        sell_count = sum(1 for signal in self._signals_data if signal.get("signal_type") == "SELL")
        hold_count = sum(1 for signal in self._signals_data if signal.get("signal_type") == "HOLD")
        total_count = len(self._signals_data)
        
        self.buy_signals_label.setText(str(buy_count))
        self.sell_signals_label.setText(str(sell_count))
        self.hold_signals_label.setText(str(hold_count))
        self.total_signals_label.setText(str(total_count))

    def _update_signals_table(self):
        """更新信号表格"""
        self.signals_table.setRowCount(len(self._signals_data))
        
        for row, signal in enumerate(self._signals_data):
            # 时间
            time_item = QTableWidgetItem(signal["timestamp"].strftime("%H:%M:%S"))
            self.signals_table.setItem(row, 0, time_item)
            
            # 股票代码
            symbol_item = QTableWidgetItem(signal.get("symbol", ""))
            self.signals_table.setItem(row, 1, symbol_item)
            
            # 信号类型
            signal_type = signal.get("signal_type", "")
            type_item = QTableWidgetItem(signal_type)
            if signal_type == "BUY":
                type_item.setBackground(QColor(144, 238, 144))  # 浅绿色
            elif signal_type == "SELL":
                type_item.setBackground(QColor(255, 182, 193))  # 浅红色
            else:
                type_item.setBackground(QColor(255, 255, 224))  # 浅黄色
            self.signals_table.setItem(row, 2, type_item)
            
            # 强度
            strength_item = QTableWidgetItem(f"{signal.get('strength', 0):.2f}")
            self.signals_table.setItem(row, 3, strength_item)
            
            # 置信度
            confidence_item = QTableWidgetItem(f"{signal.get('confidence', 0):.2f}")
            self.signals_table.setItem(row, 4, confidence_item)
            
            # 状态
            status_item = QTableWidgetItem(signal.get("status", ""))
            self.signals_table.setItem(row, 5, status_item)

    def _update_statistics(self):
        """更新统计信息"""
        if not self._signals_data:
            self.success_rate_label.setText("暂无数据")
            self.accuracy_label.setText("暂无数据")
            self.profit_rate_label.setText("暂无数据")
            self.strength_chart.setText("暂无信号数据")
            return

        total = len(self._signals_data)
        if total == 0:
            self.success_rate_label.setText("0.0%")
            self.accuracy_label.setText("0.0%")
            self.profit_rate_label.setText("0.0%")
            self.strength_chart.setText("暂无信号数据")
            return

        strong = sum(1 for s in self._signals_data if s.get('strength', 0) >= 0.7)
        medium = sum(1 for s in self._signals_data if 0.4 <= s.get('strength', 0) < 0.7)
        weak = total - strong - medium

        confirmed = sum(1 for s in self._signals_data if s.get('status') == '已确认')
        success_rate = (confirmed / total * 100) if total > 0 else 0.0
        self.success_rate_label.setText(f"{success_rate:.1f}%")

        high_confidence = sum(1 for s in self._signals_data if s.get('confidence', 0) >= 0.7)
        accuracy = (high_confidence / total * 100) if total > 0 else 0.0
        self.accuracy_label.setText(f"{accuracy:.1f}%")

        profitable = sum(1 for s in self._signals_data if s.get('signal_type') == 'BUY')
        profit_rate = (profitable / total * 100) if total > 0 else 0.0
        self.profit_rate_label.setText(f"{profit_rate:.1f}%")

        block = '\u2588'
        shade = '\u2591'

        self.strength_chart.setText(
            "信号强度分布图\n\n" +
            f"\u5f3a\u4fe1\u53f7 (0.7-1.0): {block * min(10, int(strong / max(1, total) * 10))}{shade * max(0, 10 - int(strong / max(1, total) * 10))} {strong / max(1, total) * 100:.0f}%\n" +
            f"\u4e2d\u4fe1\u53f7 (0.4-0.7): {block * min(10, int(medium / max(1, total) * 10))}{shade * max(0, 10 - int(medium / max(1, total) * 10))} {medium / max(1, total) * 100:.0f}%\n" +
            f"\u5f31\u4fe1\u53f7 (0.0-0.4): {block * min(10, int(weak / max(1, total) * 10))}{shade * max(0, 10 - int(weak / max(1, total) * 10))} {weak / max(1, total) * 100:.0f}%"
        )

    def _confirm_signal(self):
        """确认信号"""
        current_row = self.signals_table.currentRow()
        if current_row >= 0 and current_row < len(self._signals_data):
            signal = self._signals_data[current_row]
            self.signal_confirmed.emit(signal["symbol"], signal)
            logger.info(f"信号已确认: {signal['symbol']} - {signal['signal_type']}")

    def _dismiss_signal(self):
        """忽略信号"""
        current_row = self.signals_table.currentRow()
        if current_row >= 0:
            self.signals_table.removeRow(current_row)
            if current_row < len(self._signals_data):
                self._signals_data.pop(current_row)
            logger.info("信号已被忽略")

    def refresh_data(self):
        """刷新数据"""
        self._update_signals()

    def get_signals_data(self) -> List[Dict[str, Any]]:
        """获取信号数据"""
        return self._signals_data

    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, '_update_timer'):
            self._update_timer.stop()
        super().closeEvent(event)