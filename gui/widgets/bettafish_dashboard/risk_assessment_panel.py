#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险评估面板 - BettaFish仪表板组件
显示实时风险指标和评估结果
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QFrame, QGroupBox, QGridLayout, 
    QPushButton, QTabWidget, QTextEdit, QScrollArea,
    QProgressBar, QLCDNumber, QDial
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QPoint
from PyQt5.QtGui import QFont, QColor, QPalette, QPixmap, QPainter, QBrush

from loguru import logger
from core.agents.bettafish_agent import BettaFishAgent


class RiskGauge(QWidget):
    """风险仪表盘组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0.0
        self.max_value = 100.0
        self.setMinimumSize(120, 120)
        
    def set_value(self, value):
        """设置值"""
        self.value = max(0, min(self.max_value, value))
        self.update()
        
    def paintEvent(self, event):
        """绘制事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        center = rect.center()
        radius = min(rect.width(), rect.height()) // 2 - 10
        
        # 绘制背景圆
        painter.setBrush(QBrush(QColor(240, 240, 240)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, radius, radius)
        
        # 绘制风险等级颜色
        if self.value <= 30:
            color = QColor(144, 238, 144)  # 绿色 - 低风险
        elif self.value <= 60:
            color = QColor(255, 255, 0)    # 黄色 - 中等风险
        elif self.value <= 80:
            color = QColor(255, 165, 0)    # 橙色 - 高风险
        else:
            color = QColor(255, 0, 0)      # 红色 - 极高风险
            
        # 绘制指针
        painter.save()
        painter.translate(center)
        
        # 计算角度 (0度为右侧，逆时针)
        angle = (self.value / self.max_value) * 180 - 90
        painter.rotate(angle)
        
        # 绘制指针
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPolygon([
            QPoint(0, -radius + 10),    # 指针末端
            QPoint(-5, 0),              # 指针左端
            QPoint(5, 0)                # 指针右端
        ])
        
        painter.restore()
        
        # 绘制中心圆
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(center, 8, 8)
        
        # 绘制数值
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(rect, Qt.AlignCenter, f"{self.value:.1f}")


class RiskAssessmentPanel(QWidget):
    """
    风险评估面板
    
    功能：
    1. 显示实时风险指标
    2. 风险等级评估
    3. 风险预警
    4. 历史风险趋势
    """

    # 信号定义
    risk_alert = pyqtSignal(str, dict)  # 风险预警信号
    risk_level_changed = pyqtSignal(str)  # 风险等级变化信号

    def __init__(self, parent=None, bettafish_agent: BettaFishAgent = None):
        """
        初始化风险评估面板

        Args:
            parent: 父组件
            bettafish_agent: BettaFish代理实例
        """
        super().__init__(parent)
        
        self._bettafish_agent = bettafish_agent
        self._risk_data = {}
        self._risk_alerts = []
        self._risk_history = []
        
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
        title_label = QLabel("风险评估分析")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_layout.addWidget(title_label)
        
        # 风险状态指示器
        self.risk_status_label = QLabel("● 风险监控中")
        self.risk_status_label.setStyleSheet("color: green; font-weight: bold;")
        title_layout.addWidget(self.risk_status_label)
        
        layout.addWidget(title_frame)

    def _create_content(self, layout):
        """创建主内容区域"""
        # 创建选项卡
        tab_widget = QTabWidget()
        
        # 概览
        overview_widget = QWidget()
        self._create_overview_tab(overview_widget)
        tab_widget.addTab(overview_widget, "风险概览")
        
        # 详细指标
        detail_widget = QWidget()
        self._create_detail_tab(detail_widget)
        tab_widget.addTab(detail_widget, "详细指标")
        
        # 预警信息
        alert_widget = QWidget()
        self._create_alert_tab(alert_widget)
        tab_widget.addTab(alert_widget, "风险预警")
        
        # 历史趋势
        history_widget = QWidget()
        self._create_history_tab(history_widget)
        tab_widget.addTab(history_widget, "历史趋势")
        
        layout.addWidget(tab_widget)

    def _create_overview_tab(self, widget):
        """创建风险概览选项卡"""
        layout = QGridLayout(widget)
        
        # 总体风险等级
        overall_group = QGroupBox("总体风险等级")
        overall_layout = QVBoxLayout(overall_group)
        
        self.risk_gauge = RiskGauge()
        overall_layout.addWidget(self.risk_gauge, alignment=Qt.AlignCenter)
        
        self.risk_level_label = QLabel("低风险")
        self.risk_level_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.risk_level_label.setAlignment(Qt.AlignCenter)
        self.risk_level_label.setStyleSheet("color: green;")
        overall_layout.addWidget(self.risk_level_label)
        
        layout.addWidget(overall_group, 0, 0)
        
        # 风险指标摘要
        summary_group = QGroupBox("风险指标摘要")
        summary_layout = QGridLayout(summary_group)
        
        # 各个风险指标
        self.var_label = QLabel("0.00%")
        self.max_drawdown_label = QLabel("0.00%")
        self.sharpe_ratio_label = QLabel("0.00")
        self.volatility_label = QLabel("0.00%")
        self.correlation_label = QLabel("0.00")
        self.concentration_label = QLabel("0.00%")
        
        summary_layout.addWidget(QLabel("VaR (95%):"), 0, 0)
        summary_layout.addWidget(self.var_label, 0, 1)
        summary_layout.addWidget(QLabel("最大回撤:"), 1, 0)
        summary_layout.addWidget(self.max_drawdown_label, 1, 1)
        summary_layout.addWidget(QLabel("夏普比率:"), 2, 0)
        summary_layout.addWidget(self.sharpe_ratio_label, 2, 1)
        summary_layout.addWidget(QLabel("波动率:"), 3, 0)
        summary_layout.addWidget(self.volatility_label, 3, 1)
        summary_layout.addWidget(QLabel("相关性:"), 4, 0)
        summary_layout.addWidget(self.correlation_label, 4, 1)
        summary_layout.addWidget(QLabel("集中度:"), 5, 0)
        summary_layout.addWidget(self.concentration_label, 5, 1)
        
        layout.addWidget(summary_group, 0, 1)
        
        # 快速状态
        status_group = QGroupBox("快速状态检查")
        status_layout = QVBoxLayout(status_group)
        
        self.status_checks = {
            "市场风险": QLabel("正常"),
            "流动性风险": QLabel("正常"),
            "信用风险": QLabel("正常"),
            "操作风险": QLabel("正常"),
            "集中度风险": QLabel("正常")
        }
        
        for check_name, check_label in self.status_checks.items():
            check_layout = QHBoxLayout()
            check_layout.addWidget(QLabel(f"{check_name}:"))
            check_layout.addWidget(check_label)
            check_layout.addStretch()
            status_layout.addLayout(check_layout)
        
        layout.addWidget(status_group, 1, 0, 1, 2)

    def _create_detail_tab(self, widget):
        """创建详细指标选项卡"""
        layout = QVBoxLayout(widget)
        
        # 详细风险指标表格
        detail_group = QGroupBox("详细风险指标")
        detail_layout = QVBoxLayout(detail_group)
        
        self.detail_table = QTableWidget(0, 3)
        self.detail_table.setHorizontalHeaderLabels(["指标", "当前值", "风险等级"])
        self.detail_table.horizontalHeader().setStretchLastSection(True)
        self.detail_table.setAlternatingRowColors(True)
        
        detail_layout.addWidget(self.detail_table)
        layout.addWidget(detail_group)
        
        # 风险分解
        breakdown_group = QGroupBox("风险分解")
        breakdown_layout = QVBoxLayout(breakdown_group)
        
        self.breakdown_chart = QLabel("风险分解图")
        self.breakdown_chart.setMinimumHeight(200)
        self.breakdown_chart.setStyleSheet("border: 1px solid #ccc; background-color: #f9f9f9;")
        breakdown_layout.addWidget(self.breakdown_chart)
        
        layout.addWidget(breakdown_group)

    def _create_alert_tab(self, widget):
        """创建风险预警选项卡"""
        layout = QVBoxLayout(widget)
        
        # 预警列表
        alert_group = QGroupBox("风险预警")
        alert_layout = QVBoxLayout(alert_group)
        
        self.alert_table = QTableWidget(0, 4)
        self.alert_table.setHorizontalHeaderLabels(["时间", "级别", "类型", "描述"])
        self.alert_table.horizontalHeader().setStretchLastSection(True)
        self.alert_table.setAlternatingRowColors(True)
        
        alert_layout.addWidget(self.alert_table)
        layout.addWidget(alert_group)
        
        # 预警设置
        settings_group = QGroupBox("预警设置")
        settings_layout = QGridLayout(settings_group)
        
        self.var_threshold = QProgressBar()
        self.var_threshold.setRange(0, 100)
        self.var_threshold.setValue(5)  # 5% VaR阈值
        
        self.drawdown_threshold = QProgressBar()
        self.drawdown_threshold.setRange(0, 50)
        self.drawdown_threshold.setValue(10)  # 10%回撤阈值
        
        settings_layout.addWidget(QLabel("VaR阈值 (%):"), 0, 0)
        settings_layout.addWidget(self.var_threshold, 0, 1)
        settings_layout.addWidget(QLabel("回撤阈值 (%):"), 1, 0)
        settings_layout.addWidget(self.drawdown_threshold, 1, 1)
        
        layout.addWidget(settings_group)

    def _create_history_tab(self, widget):
        """创建历史趋势选项卡"""
        layout = QVBoxLayout(widget)
        
        # 风险历史图表
        history_group = QGroupBox("风险历史趋势")
        history_layout = QVBoxLayout(history_group)
        
        self.history_chart = QLabel("风险趋势图")
        self.history_chart.setMinimumHeight(300)
        self.history_chart.setStyleSheet("border: 1px solid #ccc; background-color: #f9f9f9;")
        history_layout.addWidget(self.history_chart)
        
        layout.addWidget(history_group)
        
        # 统计信息
        stats_group = QGroupBox("历史统计")
        stats_layout = QGridLayout(stats_group)
        
        self.avg_risk_label = QLabel("0.0")
        self.max_risk_label = QLabel("0.0")
        self.min_risk_label = QLabel("0.0")
        self.risk_trend_label = QLabel("平稳")
        
        stats_layout.addWidget(QLabel("平均风险:"), 0, 0)
        stats_layout.addWidget(self.avg_risk_label, 0, 1)
        stats_layout.addWidget(QLabel("最高风险:"), 1, 0)
        stats_layout.addWidget(self.max_risk_label, 1, 1)
        stats_layout.addWidget(QLabel("最低风险:"), 2, 0)
        stats_layout.addWidget(self.min_risk_label, 2, 1)
        stats_layout.addWidget(QLabel("风险趋势:"), 3, 0)
        stats_layout.addWidget(self.risk_trend_label, 3, 1)
        
        layout.addWidget(stats_group)

    def _init_timer(self):
        """初始化定时器"""
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_risk_data)
        self._update_timer.start(30000)  # 每30秒更新一次

    def _init_data(self):
        """初始化数据"""
        # 加载风险数据
        self._load_risk_data()
        
        # 更新显示
        self._update_display()

    def _load_risk_data(self):
        """加载风险数据"""
        try:
            if self._bettafish_agent and hasattr(self._bettafish_agent, 'get_risk_assessment'):
                agent_risk = self._bettafish_agent.get_risk_assessment()
                if agent_risk:
                    self._risk_data = agent_risk
                    return

            self._risk_data = {}
            self._risk_alerts = []
            self._risk_history = []
            logger.info("风险评估数据源未连接，显示暂无数据")
        except Exception as e:
            logger.error(f"加载风险数据失败: {e}")
            self._risk_data = {}
            self._risk_alerts = []
            self._risk_history = []

    def _update_risk_data(self):
        """更新风险数据"""
        try:
            if self._bettafish_agent and hasattr(self._bettafish_agent, 'get_risk_assessment'):
                agent_risk = self._bettafish_agent.get_risk_assessment()
                if agent_risk:
                    self._risk_data = agent_risk

            if self._bettafish_agent and hasattr(self._bettafish_agent, 'get_risk_alerts'):
                agent_alerts = self._bettafish_agent.get_risk_alerts()
                if agent_alerts:
                    self._risk_alerts = agent_alerts

            self._update_display()
        except Exception as e:
            logger.error(f"更新风险数据失败: {e}")

    def _update_display(self):
        """更新显示"""
        try:
            # 更新总体风险
            self._update_overall_risk()
            
            # 更新详细指标
            self._update_detail_metrics()
            
            # 更新预警信息
            self._update_alerts()
            
            # 更新历史趋势
            self._update_history()
            
        except Exception as e:
            logger.error(f"更新显示失败: {e}")

    def _update_overall_risk(self):
        """更新总体风险"""
        if not self._risk_data:
            self.risk_gauge.set_value(0)
            self.risk_level_label.setText("暂无数据")
            self.risk_level_label.setStyleSheet("color: gray; font-weight: bold;")
            return

        risk_value = self._risk_data.get("overall_risk", 0)
        self.risk_gauge.set_value(risk_value)

        if risk_value <= 0:
            level = "暂无数据"
            color = "gray"
        elif risk_value <= 30:
            level = "低风险"
            color = "green"
        elif risk_value <= 60:
            level = "中等风险"
            color = "orange"
        elif risk_value <= 80:
            level = "高风险"
            color = "red"
        else:
            level = "极高风险"
            color = "darkred"

        self.risk_level_label.setText(level)
        self.risk_level_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _update_detail_metrics(self):
        """更新详细指标"""
        if not self._risk_data:
            self.var_label.setText("暂无数据")
            self.max_drawdown_label.setText("暂无数据")
            self.sharpe_ratio_label.setText("暂无数据")
            self.volatility_label.setText("暂无数据")
            self.correlation_label.setText("暂无数据")
            self.concentration_label.setText("暂无数据")
            for label in self.status_checks.values():
                label.setText("未知")
                label.setStyleSheet("color: gray;")
            self.detail_table.setRowCount(0)
            self.breakdown_chart.setText("暂无风险数据")
            return

        self.var_label.setText(f"{self._risk_data.get('var_95', 0):.2f}%")
        self.max_drawdown_label.setText(f"{self._risk_data.get('max_drawdown', 0):.2f}%")
        self.sharpe_ratio_label.setText(f"{self._risk_data.get('sharpe_ratio', 0):.2f}")
        self.volatility_label.setText(f"{self._risk_data.get('volatility', 0):.2f}%")
        self.correlation_label.setText(f"{self._risk_data.get('correlation', 0):.2f}")
        self.concentration_label.setText(f"{self._risk_data.get('concentration', 0):.2f}%")

        risk_types = ["market_risk", "liquidity_risk", "credit_risk", "operational_risk", "concentration_risk"]
        risk_names = ["市场风险", "流动性风险", "信用风险", "操作风险", "集中度风险"]

        for i, risk_type in enumerate(risk_types):
            if risk_type in self._risk_data:
                risk_level = self._risk_data[risk_type]
                label = self.status_checks[risk_names[i]]

                if risk_level == "low":
                    label.setText("正常")
                    label.setStyleSheet("color: green;")
                elif risk_level == "medium":
                    label.setText("警告")
                    label.setStyleSheet("color: orange;")
                else:
                    label.setText("危险")
                    label.setStyleSheet("color: red;")

        self._update_detail_table()

        self._update_risk_breakdown()

    def _update_detail_table(self):
        """更新详细指标表格"""
        if self._risk_data:
            metrics = [
                ("VaR (95%)", f"{self._risk_data.get('var_95', 0):.2f}%", "低"),
                ("最大回撤", f"{self._risk_data.get('max_drawdown', 0):.2f}%", "低"),
                ("夏普比率", f"{self._risk_data.get('sharpe_ratio', 0):.2f}", "良好"),
                ("波动率", f"{self._risk_data.get('volatility', 0):.2f}%", "中等"),
                ("相关性", f"{self._risk_data.get('correlation', 0):.2f}", "低"),
                ("集中度", f"{self._risk_data.get('concentration', 0):.2f}%", "中等")
            ]
            
            self.detail_table.setRowCount(len(metrics))
            for row, (name, value, level) in enumerate(metrics):
                self.detail_table.setItem(row, 0, QTableWidgetItem(name))
                self.detail_table.setItem(row, 1, QTableWidgetItem(value))
                
                level_item = QTableWidgetItem(level)
                if level == "低" or level == "良好":
                    level_item.setBackground(QColor(144, 238, 144))  # 浅绿色
                elif level == "中等":
                    level_item.setBackground(QColor(255, 255, 224))  # 浅黄色
                else:
                    level_item.setBackground(QColor(255, 182, 193))  # 浅红色
                self.detail_table.setItem(row, 2, level_item)

    def _update_risk_breakdown(self):
        """更新风险分解"""
        if not self._risk_data:
            self.breakdown_chart.setText("暂无风险数据")
            return

        market_pct = self._risk_data.get('market_risk_pct', 0)
        liquidity_pct = self._risk_data.get('liquidity_risk_pct', 0)
        credit_pct = self._risk_data.get('credit_risk_pct', 0)
        operational_pct = self._risk_data.get('operational_risk_pct', 0)
        concentration_pct = self._risk_data.get('concentration_risk_pct', 0)

        def bar_chart(value):
            blocks = min(20, int(value / 5))
            return '\u2588' * blocks + '\u2591' * (20 - blocks)

        self.breakdown_chart.setText(
            "\u98ce\u9669\u5206\u89e3\n\n" +
            f"\u5e02\u573a\u98ce\u9669: {bar_chart(market_pct)} {market_pct:.0f}%\n" +
            f"\u6d41\u52a8\u6027\u98ce\u9669: {bar_chart(liquidity_pct)} {liquidity_pct:.0f}%\n" +
            f"\u4fe1\u7528\u98ce\u9669: {bar_chart(credit_pct)} {credit_pct:.0f}%\n" +
            f"\u64cd\u4f5c\u98ce\u9669: {bar_chart(operational_pct)} {operational_pct:.0f}%\n" +
            f"\u96c6\u4e2d\u5ea6\u98ce\u9669: {bar_chart(concentration_pct)} {concentration_pct:.0f}%"
        )

    def _update_alerts(self):
        """更新预警信息"""
        self.alert_table.setRowCount(len(self._risk_alerts))
        
        for row, alert in enumerate(self._risk_alerts):
            # 时间
            time_item = QTableWidgetItem(alert["timestamp"].strftime("%H:%M:%S"))
            self.alert_table.setItem(row, 0, time_item)
            
            # 级别
            level_item = QTableWidgetItem(alert["level"])
            if alert["level"] == "WARNING":
                level_item.setBackground(QColor(255, 255, 0))  # 黄色
            elif alert["level"] == "ERROR":
                level_item.setBackground(QColor(255, 0, 0))   # 红色
            else:
                level_item.setBackground(QColor(144, 238, 144))  # 绿色
            self.alert_table.setItem(row, 1, level_item)
            
            # 类型
            type_item = QTableWidgetItem(alert["type"])
            self.alert_table.setItem(row, 2, type_item)
            
            # 描述
            desc_item = QTableWidgetItem(alert["description"])
            self.alert_table.setItem(row, 3, desc_item)

    def _update_history(self):
        """更新历史趋势"""
        if not self._risk_history:
            self.history_chart.setText("暂无历史风险数据")
            self.avg_risk_label.setText("暂无数据")
            self.max_risk_label.setText("暂无数据")
            self.min_risk_label.setText("暂无数据")
            self.risk_trend_label.setText("暂无数据")
            self.risk_trend_label.setStyleSheet("color: gray;")
            return

        recent_data = self._risk_history[-24:]

        history_text = "最近24小时风险趋势\n\n"
        for i, point in enumerate(recent_data[::3]):
            risk_level = point["risk_level"]
            if risk_level <= 30:
                bar = "\u2588" * int(risk_level / 5) + "\u2591" * (10 - int(risk_level / 5))
            elif risk_level <= 60:
                bar = "\u2593" * int(risk_level / 5) + "\u2591" * (10 - int(risk_level / 5))
            else:
                bar = "\u2589" * int(risk_level / 5) + "\u2591" * (10 - int(risk_level / 5))

            history_text += f"{point['timestamp'].strftime('%H:%M')}: {bar} {risk_level:.1f}\n"

        self.history_chart.setText(history_text)

        risk_values = [point["risk_level"] for point in recent_data]
        avg_risk = sum(risk_values) / len(risk_values)
        max_risk = max(risk_values)
        min_risk = min(risk_values)

        self.avg_risk_label.setText(f"{avg_risk:.1f}")
        self.max_risk_label.setText(f"{max_risk:.1f}")
        self.min_risk_label.setText(f"{min_risk:.1f}")

        if risk_values[-1] > risk_values[0]:
            trend = "上升"
            color = "orange"
        elif risk_values[-1] < risk_values[0]:
            trend = "下降"
            color = "green"
        else:
            trend = "平稳"
            color = "blue"

        self.risk_trend_label.setText(trend)
        self.risk_trend_label.setStyleSheet(f"color: {color};")

    def refresh_data(self):
        """刷新数据"""
        self._update_risk_data()

    def get_risk_data(self) -> Dict[str, Any]:
        """获取风险数据"""
        return self._risk_data

    def get_risk_alerts(self) -> List[Dict[str, Any]]:
        """获取风险预警"""
        return self._risk_alerts

    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, '_update_timer'):
            self._update_timer.stop()
        super().closeEvent(event)