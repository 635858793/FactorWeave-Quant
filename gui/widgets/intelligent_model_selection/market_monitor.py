#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场状态监控界面组件

提供实时市场状态监控和分析功能，包括：
- 市场波动状态可视化
- 趋势强度分析
- 流动性状态监控
- 市场阶段识别
"""

from loguru import logger
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QPushButton, QGroupBox, QScrollArea,
    QProgressBar, QTextEdit, QSplitter,
    QFrame, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy
)
from PyQt5.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, QSize, 
    QPropertyAnimation, QEasingCurve
)
from PyQt5.QtGui import (
    QFont, QPalette, QBrush, QColor, QPainter, 
    QPainterPath, QPen, QPixmap
)


class MarketStateMonitor(QWidget):
    """市场状态监控界面"""
    
    # 信号定义
    market_state_changed = pyqtSignal(dict)  # 市场状态变更信号
    alert_triggered = pyqtSignal(str, str)  # 告警触发信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_market_data = {}
        self.historical_data = []
        self.monitoring_timer = QTimer()
        self.last_update_time = None
        self.alert_thresholds = {
            'volatility_high': 0.25,
            'volatility_low': 0.05,
            'trend_strength_high': 0.8,
            'trend_strength_low': 0.2,
            'liquidity_low': 0.3
        }
        
        self.init_ui()
        self.setup_connections()
        self.start_monitoring()
    
    def init_ui(self):
        """初始化用户界面"""
        self.setMinimumSize(600, 500)
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        
        # 1. 顶部状态栏
        status_header = self._create_status_header()
        main_layout.addWidget(status_header)
        
        # 2. 主要监控区域
        monitor_area = self._create_monitor_area()
        main_layout.addWidget(monitor_area, 1)
        
        # 3. 底部控制栏
        control_footer = self._create_control_footer()
        main_layout.addWidget(control_footer)
        
        # 应用统一样式
        self._apply_unified_styles()
    
    def _create_status_header(self) -> QWidget:
        """创建状态头部"""
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 当前时间
        self.time_label = QLabel()
        self.time_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
                padding: 5px 10px;
            }
        """)
        layout.addWidget(self.time_label)
        
        layout.addStretch()
        
        # 市场状态指示器
        self.market_status_label = QLabel("🔴 监控中")
        self.market_status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 8px 12px;
                border-radius: 4px;
                background-color: #e8f5e8;
                color: #2e7d32;
                border: 1px solid #4caf50;
            }
        """)
        layout.addWidget(self.market_status_label)
        
        # 最后更新时间
        self.last_update_label = QLabel("最后更新: --")
        self.last_update_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #7f8c8d;
                padding: 5px;
            }
        """)
        layout.addWidget(self.last_update_label)
        
        return header
    
    def _create_monitor_area(self) -> QWidget:
        """创建监控区域"""
        monitor_widget = QWidget()
        layout = QVBoxLayout(monitor_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 1. 市场概览选项卡
        overview_tab = self._create_overview_tab()
        self.tab_widget.addTab(overview_tab, "市场概览")
        
        # 2. 波动性分析选项卡
        volatility_tab = self._create_volatility_tab()
        self.tab_widget.addTab(volatility_tab, "📈 波动性分析")
        
        # 3. 趋势分析选项卡
        trend_tab = self._create_trend_tab()
        self.tab_widget.addTab(trend_tab, "📉 趋势分析")
        
        # 4. 流动性监控选项卡
        liquidity_tab = self._create_liquidity_tab()
        self.tab_widget.addTab(liquidity_tab, "💧 流动性监控")
        
        return monitor_widget
    
    def _create_overview_tab(self) -> QWidget:
        """创建市场概览选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 创建网格布局显示关键指标
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        
        # 1. 波动率指标
        vol_group = self._create_volatility_overview()
        grid_layout.addWidget(vol_group, 0, 0)
        
        # 2. 趋势强度指标
        trend_group = self._create_trend_overview()
        grid_layout.addWidget(trend_group, 0, 1)
        
        # 3. 流动性指标
        liquidity_group = self._create_liquidity_overview()
        grid_layout.addWidget(liquidity_group, 1, 0)
        
        # 4. 市场阶段指标
        regime_group = self._create_regime_overview()
        grid_layout.addWidget(regime_group, 1, 1)
        
        layout.addWidget(grid_widget)
        
        # 状态描述文本
        self.status_description = QTextEdit()
        self.status_description.setMaximumHeight(120)
        self.status_description.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
                background-color: #f8f9fa;
                font-size: 12px;
            }
        """)
        self.status_description.setReadOnly(True)
        layout.addWidget(self.status_description)
        
        return tab
    
    def _create_volatility_overview(self) -> QGroupBox:
        """创建波动率概览"""
        group = QGroupBox("市场波动率")
        layout = QVBoxLayout(group)
        
        # 当前波动率
        current_vol_layout = QHBoxLayout()
        current_vol_layout.addWidget(QLabel("当前波动率:"))
        
        self.current_volatility_label = QLabel("--")
        self.current_volatility_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        current_vol_layout.addWidget(self.current_volatility_label)
        current_vol_layout.addStretch()
        
        layout.addLayout(current_vol_layout)
        
        # 波动率状态
        self.volatility_status_label = QLabel("状态: --")
        self.volatility_status_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                padding: 5px;
                border-radius: 3px;
                background-color: #e9ecef;
            }
        """)
        layout.addWidget(self.volatility_status_label)
        
        # 历史波动率图表区域
        vol_chart_frame = QFrame()
        vol_chart_frame.setMinimumHeight(100)
        vol_chart_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f8f9fa;
            }
        """)
        layout.addWidget(vol_chart_frame)
        
        return group
    
    def _create_trend_overview(self) -> QGroupBox:
        """创建趋势概览"""
        group = QGroupBox("📈 趋势强度")
        layout = QVBoxLayout(group)
        
        # 趋势强度
        trend_strength_layout = QHBoxLayout()
        trend_strength_layout.addWidget(QLabel("趋势强度:"))
        
        self.trend_strength_label = QLabel("--")
        self.trend_strength_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        trend_strength_layout.addWidget(self.trend_strength_label)
        trend_strength_layout.addStretch()
        
        layout.addLayout(trend_strength_layout)
        
        # 趋势方向
        self.trend_direction_label = QLabel("方向: --")
        self.trend_direction_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                padding: 5px;
                border-radius: 3px;
                background-color: #e9ecef;
            }
        """)
        layout.addWidget(self.trend_direction_label)
        
        # 趋势稳定性
        self.trend_stability_label = QLabel("稳定性: --")
        self.trend_stability_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                padding: 5px;
                border-radius: 3px;
                background-color: #e9ecef;
            }
        """)
        layout.addWidget(self.trend_stability_label)
        
        return group
    
    def _create_liquidity_overview(self) -> QGroupBox:
        """创建流动性概览"""
        group = QGroupBox("💧 市场流动性")
        layout = QVBoxLayout(group)
        
        # 流动性水平
        liquidity_layout = QHBoxLayout()
        liquidity_layout.addWidget(QLabel("流动性水平:"))
        
        self.liquidity_level_label = QLabel("--")
        self.liquidity_level_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        liquidity_layout.addWidget(self.liquidity_level_label)
        liquidity_layout.addStretch()
        
        layout.addLayout(liquidity_layout)
        
        # 成交量状态
        self.volume_status_label = QLabel("成交量: --")
        self.volume_status_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                padding: 5px;
                border-radius: 3px;
                background-color: #e9ecef;
            }
        """)
        layout.addWidget(self.volume_status_label)
        
        # 买卖价差
        self.spread_status_label = QLabel("价差: --")
        self.spread_status_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                padding: 5px;
                border-radius: 3px;
                background-color: #e9ecef;
            }
        """)
        layout.addWidget(self.spread_status_label)
        
        return group
    
    def _create_regime_overview(self) -> QGroupBox:
        """创建市场阶段概览"""
        group = QGroupBox("市场阶段")
        layout = QVBoxLayout(group)
        
        # 当前阶段
        self.current_regime_label = QLabel("当前阶段: --")
        self.current_regime_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
                background-color: #e3f2fd;
                color: #1565c0;
                text-align: center;
            }
        """)
        self.current_regime_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.current_regime_label)
        
        # 阶段置信度
        confidence_layout = QHBoxLayout()
        confidence_layout.addWidget(QLabel("置信度:"))
        
        self.regime_confidence_label = QLabel("--")
        self.regime_confidence_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        confidence_layout.addWidget(self.regime_confidence_label)
        confidence_layout.addStretch()
        
        layout.addLayout(confidence_layout)
        
        # 阶段转换历史
        self.regime_history_label = QLabel("转换历史: --")
        self.regime_history_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #7f8c8d;
                padding: 3px;
            }
        """)
        layout.addWidget(self.regime_history_label)
        
        return group
    
    def _create_volatility_tab(self) -> QWidget:
        """创建波动性分析选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 波动率统计表格
        self.volatility_table = QTableWidget(5, 3)
        self.volatility_table.setHorizontalHeaderLabels(["指标", "当前值", "状态"])
        
        # 设置表格样式
        self.volatility_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                gridline-color: #e0e0e0;
                selection-background-color: #bbdefb;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
        """)
        
        # 填充表格数据
        volatility_items = [
            ("实时波动率", "0.00", "正常"),
            ("历史波动率", "0.00", "正常"),
            ("隐含波动率", "0.00", "正常"),
            ("波动率偏斜", "0.00", "正常"),
            ("波动率聚集", "0.00", "正常")
        ]
        
        for i, (item, value, status) in enumerate(volatility_items):
            self.volatility_table.setItem(i, 0, QTableWidgetItem(item))
            self.volatility_table.setItem(i, 1, QTableWidgetItem(value))
            self.volatility_table.setItem(i, 2, QTableWidgetItem(status))
        
        layout.addWidget(self.volatility_table)
        
        # 波动率图表区域
        chart_frame = QFrame()
        chart_frame.setMinimumHeight(200)
        chart_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #fafafa;
            }
        """)
        layout.addWidget(chart_frame)
        
        return tab
    
    def _create_trend_tab(self) -> QWidget:
        """创建趋势分析选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 趋势指标表格
        self.trend_table = QTableWidget(6, 4)
        self.trend_table.setHorizontalHeaderLabels(["指标", "短期", "中期", "长期"])
        
        # 设置表格样式
        self.trend_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                gridline-color: #e0e0e0;
                selection-background-color: #bbdefb;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
        """)
        
        # 填充表格数据
        trend_items = [
            ("趋势方向", "↗️", "↗️", "↘️"),
            ("趋势强度", "0.75", "0.60", "0.25"),
            ("动量指标", "0.80", "0.65", "0.30"),
            ("支撑阻力", "强支撑", "中等支撑", "弱阻力"),
            ("突破信号", "无", "潜在突破", "无"),
            ("趋势确认", "已确认", "待确认", "未确认")
        ]
        
        for i, row_data in enumerate(trend_items):
            for j, cell_data in enumerate(row_data):
                self.trend_table.setItem(i, j, QTableWidgetItem(cell_data))
        
        layout.addWidget(self.trend_table)
        
        # 趋势分析图表
        trend_chart_frame = QFrame()
        trend_chart_frame.setMinimumHeight(200)
        trend_chart_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #fafafa;
            }
        """)
        layout.addWidget(trend_chart_frame)
        
        return tab
    
    def _create_liquidity_tab(self) -> QWidget:
        """创建流动性监控选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 流动性指标
        metrics_frame = QFrame()
        metrics_layout = QGridLayout(metrics_frame)
        
        # 创建流动性指标卡片
        self.liquidity_metrics = {}
        liquidity_items = [
            ("成交量", "0", "正常"),
            ("成交额", "¥0", "正常"),
            ("换手率", "0%", "正常"),
            ("买卖价差", "0.00%", "正常"),
            ("深度指标", "0", "正常"),
            ("冲击成本", "0.00%", "正常")
        ]
        
        for i, (name, value, status) in enumerate(liquidity_items):
            card = self._create_metric_card(name, value, status)
            row = i // 3
            col = i % 3
            metrics_layout.addWidget(card, row, col)
            self.liquidity_metrics[name] = card
        
        layout.addWidget(metrics_frame)
        
        # 流动性分析图表
        liquidity_chart_frame = QFrame()
        liquidity_chart_frame.setMinimumHeight(150)
        liquidity_chart_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #fafafa;
            }
        """)
        layout.addWidget(liquidity_chart_frame)
        
        return tab
    
    def _create_metric_card(self, title: str, value: str, status: str) -> QFrame:
        """创建指标卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 6px;
                background-color: white;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)
        
        # 标题
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #666;
                font-weight: bold;
            }
        """)
        layout.addWidget(title_label)
        
        # 数值
        value_label = QLabel(value)
        value_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        layout.addWidget(value_label)
        
        # 状态
        status_label = QLabel(status)
        status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 10px;
                padding: 3px 6px;
                border-radius: 3px;
                background-color: {self._get_status_color(status)};
                color: white;
            }}
        """)
        layout.addWidget(status_label)
        
        return card
    
    def _create_control_footer(self) -> QWidget:
        """创建控制底部栏"""
        footer = QWidget()
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 监控控制按钮
        self.toggle_monitor_btn = QPushButton("⏸️ 暂停监控")
        self.toggle_monitor_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f8f9fa;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """)
        layout.addWidget(self.toggle_monitor_btn)
        
        # 刷新数据按钮
        self.refresh_btn = QPushButton("刷新数据")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #007bff;
                border-radius: 4px;
                background-color: #007bff;
                color: white;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        layout.addWidget(self.refresh_btn)
        
        # 导出报告按钮
        self.export_btn = QPushButton("📄 导出报告")
        self.export_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #28a745;
                border-radius: 4px;
                background-color: #28a745;
                color: white;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        layout.addWidget(self.export_btn)
        
        layout.addStretch()
        
        # 数据更新频率设置
        frequency_layout = QHBoxLayout()
        frequency_layout.addWidget(QLabel("更新频率:"))
        
        self.frequency_combo = QPushButton("实时")
        self.frequency_combo.setStyleSheet("""
            QPushButton {
                padding: 5px 10px;
                border: 1px solid #ddd;
                border-radius: 3px;
                background-color: white;
                font-size: 11px;
            }
        """)
        frequency_layout.addWidget(self.frequency_combo)
        
        layout.addLayout(frequency_layout)
        
        return footer
    
    def setup_connections(self):
        """设置信号连接"""
        # 监控控制
        self.toggle_monitor_btn.clicked.connect(self.toggle_monitoring)
        self.refresh_btn.clicked.connect(self.refresh_data)
        self.export_btn.clicked.connect(self.export_report)
        
        # 定时器设置
        self.monitoring_timer.timeout.connect(self.update_market_data)
        self.monitoring_timer.start(2000)  # 每2秒更新一次
    
    def start_monitoring(self):
        """开始监控"""
        self.monitoring_timer.start()
        self.last_update_time = datetime.now()
        self.update_time_display()
        
        logger.info("市场状态监控已启动")
    
    def toggle_monitoring(self):
        """切换监控状态"""
        if self.monitoring_timer.isActive():
            self.monitoring_timer.stop()
            self.toggle_monitor_btn.setText("▶️ 开始监控")
            self.market_status_label.setText("🟡 已暂停")
            self.market_status_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: bold;
                    padding: 8px 12px;
                    border-radius: 4px;
                    background-color: #fff3cd;
                    color: #856404;
                    border: 1px solid #ffeaa7;
                }
            """)
            logger.info("市场状态监控已暂停")
        else:
            self.monitoring_timer.start()
            self.toggle_monitor_btn.setText("⏸️ 暂停监控")
            self.market_status_label.setText("🟢 监控中")
            self.market_status_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: bold;
                    padding: 8px 12px;
                    border-radius: 4px;
                    background-color: #d4edda;
                    color: #155724;
                    border: 1px solid #c3e6cb;
                }
            """)
            logger.info("市场状态监控已恢复")
    
    def refresh_data(self):
        """刷新数据"""
        logger.info("手动刷新市场数据")
        self.update_market_data()
    
    def export_report(self):
        """导出报告"""
        logger.info("导出市场状态报告")
        # TODO: 实现报告导出功能
    
    def update_market_data(self):
        """更新市场数据"""
        try:
            current_time = datetime.now()

            market_data = self._fetch_real_market_data(current_time)

            self._update_ui_display(market_data)

            self.current_market_data = market_data
            self.historical_data.append({
                'timestamp': current_time,
                'data': market_data.copy()
            })

            if len(self.historical_data) > 1000:
                self.historical_data.pop(0)

            self.market_state_changed.emit(market_data)

            self.last_update_time = current_time
            self.update_time_display()

        except Exception as e:
            logger.error(f"更新市场数据失败: {e}")
    
    def _fetch_real_market_data(self, timestamp: datetime) -> Dict[str, Any]:
        """从RealDataProvider获取真实市场数据"""
        try:
            from core.real_data_provider import get_real_data_provider
            provider = get_real_data_provider()
            if not provider:
                return self._get_no_data_market_state(timestamp)

            default_stocks = ['000001', '000002', '000858', '600519']
            quotes = []
            for symbol in default_stocks:
                try:
                    quote = provider.get_real_quote(symbol)
                    if quote:
                        quotes.append(quote)
                except Exception:
                    continue

            if not quotes:
                return self._get_no_data_market_state(timestamp)

            import numpy as np

            prices = [q.get('price', 0) for q in quotes if q.get('price', 0) > 0]
            change_pcts = [q.get('change_pct', 0) for q in quotes]
            volumes = [q.get('volume', 0) for q in quotes if q.get('volume', 0) > 0]

            avg_price = sum(prices) / len(prices) if prices else 0
            total_volume = sum(volumes)

            raw_volatility = np.std(change_pcts) if len(change_pcts) > 1 else 0.0
            volatility = min(raw_volatility / 10.0, 1.0)

            up_count = sum(1 for c in change_pcts if c > 0)
            trend_strength = up_count / len(change_pcts) if change_pcts else 0.5

            if trend_strength > 0.55:
                trend_direction = 'up'
            elif trend_strength < 0.45:
                trend_direction = 'down'
            else:
                trend_direction = 'sideways'

            if volumes:
                vol_min = min(volumes)
                vol_max = max(volumes)
                if vol_max > vol_min:
                    normalized_volumes = [(v - vol_min) / (vol_max - vol_min) for v in volumes]
                    liquidity = sum(normalized_volumes) / len(normalized_volumes)
                else:
                    liquidity = 0.5
            else:
                liquidity = 0.0

            regime = self._determine_market_regime(volatility, trend_strength, liquidity)
            regime_confidence = len(quotes) / len(default_stocks)

            return {
                'timestamp': timestamp,
                'volatility': volatility,
                'trend_strength': trend_strength,
                'trend_direction': trend_direction,
                'liquidity': liquidity,
                'volume': total_volume,
                'regime': regime,
                'regime_confidence': regime_confidence,
                'alerts': []
            }
        except Exception as e:
            logger.warning(f"获取真实市场数据失败: {e}")
            return self._get_no_data_market_state(timestamp)

    def _get_no_data_market_state(self, timestamp: datetime) -> Dict[str, Any]:
        """返回市场数据不可用状态"""
        return {
            'timestamp': timestamp,
            'volatility': 0.0,
            'trend_strength': 0.0,
            'trend_direction': 'unknown',
            'liquidity': 0.0,
            'volume': 0,
            'regime': '市场数据不可用',
            'regime_confidence': 0.0,
            'alerts': ['数据不可用']
        }

    def _determine_market_regime(self, volatility: float, trend_strength: float, liquidity: float) -> str:
        """确定市场阶段"""
        if volatility > 0.25 and trend_strength > 0.7:
            return "强趋势高波动"
        elif volatility > 0.25 and trend_strength < 0.4:
            return "震荡高波动"
        elif volatility < 0.08 and trend_strength > 0.7:
            return "强趋势低波动"
        elif volatility < 0.08 and trend_strength < 0.4:
            return "横盘整理"
        elif liquidity < 0.4:
            return "流动性不足"
        else:
            return "正常市场"
    
    def _check_alert_conditions(self, volatility: float, trend_strength: float, liquidity: float) -> List[str]:
        """检查告警条件"""
        alerts = []
        
        if volatility > self.alert_thresholds['volatility_high']:
            alerts.append("高波动率告警")
        
        if volatility < self.alert_thresholds['volatility_low']:
            alerts.append("低波动率告警")
        
        if trend_strength > self.alert_thresholds['trend_strength_high']:
            alerts.append("强趋势告警")
        
        if trend_strength < self.alert_thresholds['trend_strength_low']:
            alerts.append("弱趋势告警")
        
        if liquidity < self.alert_thresholds['liquidity_low']:
            alerts.append("流动性不足告警")
        
        return alerts
    
    def _update_ui_display(self, market_data: Dict[str, Any]):
        """更新UI显示"""
        try:
            # 更新时间显示
            self.update_time_display()
            
            # 更新概览数据
            self._update_overview_display(market_data)
            
            # 更新详细表格
            self._update_detail_tables(market_data)
            
            # 更新状态描述
            self._update_status_description(market_data)
            
            # 处理告警
            if market_data.get('alerts'):
                self._handle_alerts(market_data['alerts'])
            
        except Exception as e:
            logger.error(f"更新UI显示失败: {e}")
    
    def update_time_display(self):
        """更新时间显示"""
        current_time = datetime.now()
        time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.setText(f"🕐 {time_str}")
        
        if self.last_update_time:
            update_str = self.last_update_time.strftime("%H:%M:%S")
            self.last_update_label.setText(f"最后更新: {update_str}")
    
    def _update_overview_display(self, market_data: Dict[str, Any]):
        """更新概览显示"""
        # 更新波动率
        volatility = market_data.get('volatility', 0)
        self.current_volatility_label.setText(f"{volatility:.1%}")
        
        vol_status = self._get_status_text(volatility, self.alert_thresholds['volatility_low'], self.alert_thresholds['volatility_high'])
        self.volatility_status_label.setText(f"状态: {vol_status}")
        
        # 更新趋势
        trend_strength = market_data.get('trend_strength', 0)
        self.trend_strength_label.setText(f"{trend_strength:.1%}")
        
        trend_direction = market_data.get('trend_direction', 'unknown')
        direction_icon = "↗️" if trend_direction == 'upward' else "↘️" if trend_direction == 'downward' else "➡️"
        self.trend_direction_label.setText(f"方向: {direction_icon} {trend_direction}")
        
        trend_stability = "稳定" if trend_strength > 0.6 else "不稳定" if trend_strength < 0.4 else "一般"
        self.trend_stability_label.setText(f"稳定性: {trend_stability}")
        
        # 更新流动性
        liquidity = market_data.get('liquidity', 0)
        self.liquidity_level_label.setText(f"{liquidity:.1%}")
        
        volume = market_data.get('volume', 0)
        volume_str = f"{volume:,}" if volume > 1000000 else f"{volume/1000:.0f}K"
        self.volume_status_label.setText(f"成交量: {volume_str}")
        
        # 更新市场阶段
        regime = market_data.get('regime', '未知')
        self.current_regime_label.setText(f"当前阶段: {regime}")
        
        confidence = market_data.get('regime_confidence', 0)
        self.regime_confidence_label.setText(f"{confidence:.1%}")
        
        # 更新转换历史
        if len(self.historical_data) >= 2:
            last_regime = self.historical_data[-2]['data'].get('regime', '未知')
            if last_regime != regime:
                self.regime_history_label.setText(f"上次阶段: {last_regime}")
    
    def _update_detail_tables(self, market_data: Dict[str, Any]):
        """更新详细表格"""
        # 更新波动率表格
        volatility_data = [
            ("实时波动率", f"{market_data.get('volatility', 0):.2%}", self._get_status_text(market_data.get('volatility', 0))),
            ("历史波动率", f"{market_data.get('volatility', 0) * 0.9:.2%}", "正常"),
            ("隐含波动率", f"{market_data.get('volatility', 0) * 1.1:.2%}", "正常"),
            ("波动率偏斜", "0.05", "正常"),
            ("波动率聚集", "0.12", "正常")
        ]
        
        for i, (item, value, status) in enumerate(volatility_data):
            if i < self.volatility_table.rowCount():
                self.volatility_table.setItem(i, 1, QTableWidgetItem(value))
                self.volatility_table.setItem(i, 2, QTableWidgetItem(status))
        
        # 更新趋势表格
        trend_data = [
            ("趋势方向", "↗️", "↗️", "↘️"),
            ("趋势强度", f"{market_data.get('trend_strength', 0):.2f}", f"{market_data.get('trend_strength', 0) * 0.8:.2f}", f"{market_data.get('trend_strength', 0) * 0.6:.2f}"),
            ("动量指标", f"{market_data.get('trend_strength', 0) * 1.1:.2f}", f"{market_data.get('trend_strength', 0) * 0.9:.2f}", f"{market_data.get('trend_strength', 0) * 0.7:.2f}"),
            ("支撑阻力", "强支撑", "中等支撑", "弱阻力"),
            ("突破信号", "无", "潜在突破", "无"),
            ("趋势确认", "已确认", "待确认", "未确认")
        ]
        
        for i, row_data in enumerate(trend_data):
            if i < self.trend_table.rowCount():
                for j, cell_data in enumerate(row_data):
                    if j < self.trend_table.columnCount():
                        self.trend_table.setItem(i, j, QTableWidgetItem(cell_data))
        
        # 更新流动性指标
        liquidity_data = [
            ("成交量", f"{market_data.get('volume', 0):,}", "正常"),
            ("成交额", f"¥{market_data.get('volume', 0) * 1000:,}", "正常"),
            ("换手率", f"{market_data.get('liquidity', 0) * 2:.1%}", "正常"),
            ("买卖价差", f"{0.05 - market_data.get('liquidity', 0) * 0.03:.2%}", "正常"),
            ("深度指标", f"{market_data.get('liquidity', 0) * 100:.0f}", "正常"),
            ("冲击成本", f"{0.1 - market_data.get('liquidity', 0) * 0.05:.2%}", "正常")
        ]
        
        for i, (name, value, status) in enumerate(liquidity_data):
            if name in self.liquidity_metrics:
                card = self.liquidity_metrics[name]
                # 更新卡片内容
                for child in card.findChildren(QLabel):
                    if child.text() == name:
                        continue
                    elif child.styleSheet().find('font-weight: bold') >= 0:
                        child.setText(value)
                    else:
                        child.setText(status)
    
    def _update_status_description(self, market_data: Dict[str, Any]):
        """更新状态描述"""
        regime = market_data.get('regime', '未知')
        volatility = market_data.get('volatility', 0)
        trend_strength = market_data.get('trend_strength', 0)
        liquidity = market_data.get('liquidity', 0)
        
        description = f"市场状态分析报告 ({datetime.now().strftime('%H:%M:%S')})\n\n"
        description += f"当前市场阶段: {regime}\n"
        description += f"波动率水平: {volatility:.1%} ({'高' if volatility > 0.2 else '中' if volatility > 0.1 else '低'})\n"
        description += f"趋势强度: {trend_strength:.1%} ({'强' if trend_strength > 0.7 else '中' if trend_strength > 0.4 else '弱'})\n"
        description += f"流动性水平: {liquidity:.1%} ({'充足' if liquidity > 0.7 else '一般' if liquidity > 0.5 else '不足'})\n\n"
        
        # 添加建议
        recommendations = []
        if volatility > 0.25:
            recommendations.append("建议采用保守策略，控制仓位")
        elif volatility < 0.08:
            recommendations.append("市场波动较小，可考虑增加仓位")
        
        if trend_strength > 0.8:
            recommendations.append("趋势明确，建议顺势操作")
        elif trend_strength < 0.3:
            recommendations.append("趋势不明朗，建议观望")
        
        if liquidity < 0.4:
            recommendations.append("流动性不足，注意交易成本")
        
        if recommendations:
            description += "操作建议:\n"
            for i, rec in enumerate(recommendations, 1):
                description += f"{i}. {rec}\n"
        else:
            description += "市场状态相对平衡，建议维持当前策略"
        
        self.status_description.setPlainText(description)
    
    def _handle_alerts(self, alerts: List[str]):
        """处理告警"""
        for alert in alerts:
            logger.warning(f"市场状态告警: {alert}")
            self.alert_triggered.emit("市场监控", alert)
    
    def _get_status_text(self, value: float, low_threshold: float, high_threshold: float) -> str:
        """获取状态文本"""
        if value < low_threshold:
            return "偏低"
        elif value > high_threshold:
            return "偏高"
        else:
            return "正常"
    
    def _get_status_color(self, status: str) -> str:
        """获取状态颜色"""
        color_map = {
            "正常": "#28a745",
            "偏低": "#ffc107", 
            "偏高": "#dc3545",
            "高": "#dc3545",
            "中": "#ffc107",
            "低": "#17a2b8"
        }
        return color_map.get(status, "#6c757d")
    
    def _apply_unified_styles(self):
        """应用统一样式"""
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                font-family: 'Microsoft YaHei', Arial, sans-serif;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTabWidget::pane {
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #f8f9fa;
                padding: 8px 16px;
                margin-right: 2px;
                border: 1px solid #dee2e6;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: white;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #e9ecef;
            }
        """)
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.monitoring_timer.isActive():
            self.monitoring_timer.stop()
        logger.info("市场状态监控界面已关闭")
        super().closeEvent(event)


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 创建并显示监控界面
    monitor = MarketStateMonitor()
    monitor.show()
    
    sys.exit(app.exec_())