#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易执行监控标签页
专为量化交易执行质量监控设计
"""

from typing import Dict, List, Any
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QComboBox,
    QLabel, QTabWidget, QFrame, QGridLayout, QProgressBar,
    QTextEdit, QSplitter, QHeaderView, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont
from gui.widgets.performance.components.metric_card import ModernMetricCard
from gui.widgets.performance.components.performance_chart import ModernPerformanceChart
from loguru import logger

# 延迟导入主题管理器，避免在模块级别导入时崩溃
THEME_MANAGER_AVAILABLE = False
get_theme_manager = None

def _import_theme_manager():
    """延迟导入主题管理器"""
    global THEME_MANAGER_AVAILABLE, get_theme_manager
    if not THEME_MANAGER_AVAILABLE:
        try:
            from utils.theme import get_theme_manager as _get_theme_manager
            get_theme_manager = _get_theme_manager
            THEME_MANAGER_AVAILABLE = True
            logger.info("主题管理器模块导入成功")
        except Exception as e:
            logger.warning(f"导入主题管理器失败: {e}")

class ModernTradingExecutionMonitorTab(QWidget):
    """现代化交易执行监控标签页 - 量化交易专用"""

    def __init__(self):
        super().__init__()
        self.execution_data = []
        self.order_history = []
        
        # 延迟导入并初始化主题管理器
        _import_theme_manager()
        self.theme_manager = None
        if THEME_MANAGER_AVAILABLE:
            try:
                self.theme_manager = get_theme_manager()
                self.theme_manager.theme_changed.connect(self._on_theme_changed)
            except Exception as e:
                logger.warning(f"获取ThemeManager失败: {e}")
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 创建子标签页
        self.tab_widget = QTabWidget()

        # 实时执行监控
        self.realtime_tab = self._create_realtime_monitor_tab()
        self.tab_widget.addTab(self.realtime_tab, "实时监控")

        # 执行分析
        self.analysis_tab = self._create_execution_analysis_tab()
        self.tab_widget.addTab(self.analysis_tab, "执行分析")

        # 订单历史
        self.history_tab = self._create_order_history_tab()
        self.tab_widget.addTab(self.history_tab, "订单历史")

        layout.addWidget(self.tab_widget)

    def _create_realtime_monitor_tab(self):
        """创建实时执行监控标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 执行质量总览
        quality_group = QGroupBox("执行质量总览")
        quality_layout = QHBoxLayout()

        self.execution_score_label = QLabel("执行质量评分: 85.6")
        self.execution_score_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #27ae60;")
        quality_layout.addWidget(self.execution_score_label)

        quality_layout.addStretch()

        # 执行质量进度条
        self.execution_score_bar = QProgressBar()
        self.execution_score_bar.setMaximum(100)
        self.execution_score_bar.setValue(86)
        self.execution_score_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #27ae60;
                border-radius: 3px;
            }
        """)
        quality_layout.addWidget(self.execution_score_bar)

        quality_group.setLayout(quality_layout)
        layout.addWidget(quality_group)

        # 执行指标卡片
        cards_frame = QFrame()
        cards_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        cards_layout = QGridLayout(cards_frame)
        cards_layout.setContentsMargins(2, 2, 2, 2)
        cards_layout.setSpacing(2)

        self.execution_cards = {}
        execution_metrics = [
            # 第一行：核心执行指标
            ("平均延迟", "#3498db", 0, 0),
            ("成交率", "#27ae60", 0, 1),
            ("平均滑点", "#e67e22", 0, 2),
            ("交易成本", "#e74c3c", 0, 3),
            ("市场冲击", "#9b59b6", 0, 4),
            ("执行效率", "#1abc9c", 0, 5),

            # 第二行：详细执行指标
            ("订单完成率", "#2ecc71", 1, 0),
            ("部分成交率", "#f39c12", 1, 1),
            ("撤单率", "#c0392b", 1, 2),
            ("TWAP偏差", "#8e44ad", 1, 3),
            ("VWAP偏差", "#2980b9", 1, 4),
            ("实施缺口", "#16a085", 1, 5),
        ]

        for name, color, row, col in execution_metrics:
            if "延迟" in name:
                unit = "ms"
            elif "率" in name or "滑点" in name or "成本" in name or "冲击" in name or "效率" in name or "偏差" in name or "缺口" in name:
                unit = "%"
            else:
                unit = ""

            card = ModernMetricCard(name, "0", unit, color)
            self.execution_cards[name] = card
            cards_layout.addWidget(card, row, col)

        layout.addWidget(cards_frame)

        # 实时订单监控表格
        orders_group = QGroupBox("实时订单监控")
        orders_layout = QVBoxLayout()

        self.realtime_orders_table = QTableWidget()
        self.realtime_orders_table.setColumnCount(8)
        self.realtime_orders_table.setHorizontalHeaderLabels([
            "时间", "股票代码", "方向", "数量", "价格", "状态", "延迟(ms)", "滑点(%)"
        ])
        self.realtime_orders_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.realtime_orders_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # self.realtime_orders_table.setMaximumHeight(200)

        # 设置列宽
        header = self.realtime_orders_table.horizontalHeader()
        header.setStretchLastSection(True)

        orders_layout.addWidget(self.realtime_orders_table)
        orders_group.setLayout(orders_layout)
        layout.addWidget(orders_group)

        return tab

    def _create_execution_analysis_tab(self):
        """创建执行分析标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 分析控制面板
        control_group = QGroupBox("分析控制")
        control_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        control_layout = QHBoxLayout()

        control_layout.addWidget(QLabel("分析周期:"))

        self.analysis_period_combo = QComboBox()
        self.analysis_period_combo.addItems(["最近1小时", "今日", "最近3天", "最近7天", "最近30天"])
        self.analysis_period_combo.currentTextChanged.connect(self.update_execution_analysis)
        control_layout.addWidget(self.analysis_period_combo)

        control_layout.addWidget(QLabel("股票筛选:"))

        self.stock_filter_combo = QComboBox()
        self.stock_filter_combo.addItems(["全部", "沪深300", "中证500", "创业板", "科创板"])
        self.stock_filter_combo.currentTextChanged.connect(self.update_execution_analysis)
        control_layout.addWidget(self.stock_filter_combo)

        control_layout.addStretch()

        refresh_btn = QPushButton("刷新分析")
        refresh_btn.clicked.connect(self.refresh_execution_analysis)
        control_layout.addWidget(refresh_btn)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # 执行分析图表区域
        charts_splitter = QSplitter(Qt.Horizontal)

        # 滑点分布图
        self.slippage_chart = ModernPerformanceChart("滑点分布分析", "histogram")
        charts_splitter.addWidget(self.slippage_chart)

        # 延迟分布图
        self.latency_chart = ModernPerformanceChart("延迟分布分析", "histogram")
        charts_splitter.addWidget(self.latency_chart)

        layout.addWidget(charts_splitter)

        # 执行质量趋势图
        self.quality_trend_chart = ModernPerformanceChart("执行质量趋势", "line")
        layout.addWidget(self.quality_trend_chart)

        return tab

    def _create_order_history_tab(self):
        """创建订单历史标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 历史查询控制
        query_group = QGroupBox("历史查询")
        query_layout = QHBoxLayout()

        query_layout.addWidget(QLabel("时间范围:"))

        self.history_time_combo = QComboBox()
        self.history_time_combo.addItems(["今日", "最近3天", "最近7天", "最近30天", "自定义"])
        self.history_time_combo.currentTextChanged.connect(self.load_order_history)
        query_layout.addWidget(self.history_time_combo)

        query_layout.addWidget(QLabel("订单状态:"))

        self.order_status_combo = QComboBox()
        self.order_status_combo.addItems(["全部", "已成交", "部分成交", "已撤单", "待成交"])
        self.order_status_combo.currentTextChanged.connect(self.filter_order_history)
        query_layout.addWidget(self.order_status_combo)

        query_layout.addStretch()

        export_btn = QPushButton("导出数据")
        export_btn.clicked.connect(self.export_order_history)
        query_layout.addWidget(export_btn)

        query_group.setLayout(query_layout)
        layout.addWidget(query_group)

        # 订单历史表格
        self.order_history_table = QTableWidget()
        self.order_history_table.setColumnCount(12)
        self.order_history_table.setHorizontalHeaderLabels([
            "时间", "订单ID", "股票代码", "股票名称", "方向", "委托数量",
            "委托价格", "成交数量", "成交价格", "状态", "延迟(ms)", "滑点(%)"
        ])
        self.order_history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.order_history_table.setSortingEnabled(True)

        # 设置列宽自适应
        header = self.order_history_table.horizontalHeader()
        header.setStretchLastSection(True)
        for i in range(12):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        layout.addWidget(self.order_history_table)

        # 统计信息
        stats_group = QGroupBox("统计信息")
        stats_layout = QHBoxLayout()

        self.total_orders_label = QLabel("总订单数: 0")
        stats_layout.addWidget(self.total_orders_label)

        self.success_rate_label = QLabel("成功率: 0%")
        stats_layout.addWidget(self.success_rate_label)

        self.avg_slippage_label = QLabel("平均滑点: 0%")
        stats_layout.addWidget(self.avg_slippage_label)

        self.avg_latency_label = QLabel("平均延迟: 0ms")
        stats_layout.addWidget(self.avg_latency_label)

        stats_layout.addStretch()

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        return tab

    def update_execution_data(self, execution_metrics: Dict[str, float]):
        """更新执行监控数据"""
        try:
            # 使用 QTimer.singleShot 确保在主线程中更新UI
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._update_execution_ui_in_main_thread(execution_metrics))

        except Exception as e:
            logger.error(f"更新执行监控数据失败: {e}")

    def _update_execution_ui_in_main_thread(self, execution_metrics: Dict[str, float]):
        """在主线程中更新执行UI"""
        try:
            # 更新执行指标卡片
            for name, value in execution_metrics.items():
                if name in self.execution_cards:
                    if value == 0:
                        self.execution_cards[name].update_value("--", "neutral")
                    else:
                        # 根据指标类型判断趋势
                        if name in ["成交率", "订单完成率", "执行效率"]:
                            # 这些指标越高越好
                            trend = "up" if value > 90 else "neutral" if value > 70 else "down"
                        elif name in ["平均延迟", "平均滑点", "交易成本", "市场冲击", "撤单率"]:
                            # 这些指标越低越好
                            trend = "up" if value < 10 else "neutral" if value < 30 else "down"
                        else:
                            trend = "neutral"

                        if name == "平均延迟":
                            self.execution_cards[name].update_value(f"{value:.0f}", trend)
                        else:
                            self.execution_cards[name].update_value(f"{value:.2f}", trend)

            # 更新执行质量评分
            execution_score = self._calculate_execution_score(execution_metrics)
            self._update_execution_score(execution_score)

        except Exception as e:
            logger.error(f"在主线程中更新执行UI失败: {e}")

    def _calculate_execution_score(self, metrics: Dict[str, float]) -> float:
        """计算执行质量评分 - 修复版算法"""
        try:
            # 权重配置 (总和为1.0)
            weights = {
                "成交率": 0.25,      # 正向指标，越高越好
                "平均滑点": -0.20,   # 负向指标，越低越好 (单位：%)
                "平均延迟": -0.15,   # 负向指标，越低越好 (单位：ms)
                "交易成本": -0.15,   # 负向指标，越低越好 (单位：%)
                "执行效率": 0.15,    # 正向指标，越高越好
                "订单完成率": 0.10   # 正向指标，越高越好
            }

            score = 0

            for metric, weight in weights.items():
                if metric in metrics:
                    value = metrics[metric]

                    if weight > 0:
                        # 正向指标：直接加权 (值域0-100)
                        normalized_value = min(value, 100)
                        score += normalized_value * weight
                    else:
                        # 负向指标：需要根据指标类型进行标准化
                        if metric == "平均滑点":
                            # 滑点：0.1%=95分, 0.5%=75分, 1.0%=50分, >2.0%=0分
                            if value <= 0.1:
                                normalized_value = 100
                            elif value <= 0.5:
                                normalized_value = 100 - (value - 0.1) * 62.5  # 线性递减
                            elif value <= 1.0:
                                normalized_value = 75 - (value - 0.5) * 50    # 线性递减
                            elif value <= 2.0:
                                normalized_value = 50 - (value - 1.0) * 50    # 线性递减
                            else:
                                normalized_value = 0
                        elif metric == "平均延迟":
                            # 延迟：<10ms=100分, <50ms=80分, <100ms=60分, >200ms=0分
                            if value <= 10:
                                normalized_value = 100
                            elif value <= 50:
                                normalized_value = 100 - (value - 10) * 0.5   # 线性递减
                            elif value <= 100:
                                normalized_value = 80 - (value - 50) * 0.4    # 线性递减
                            elif value <= 200:
                                normalized_value = 60 - (value - 100) * 0.6   # 线性递减
                            else:
                                normalized_value = 0
                        elif metric == "交易成本":
                            # 交易成本：<0.05%=100分, <0.1%=80分, <0.2%=60分, >0.5%=0分
                            if value <= 0.05:
                                normalized_value = 100
                            elif value <= 0.1:
                                normalized_value = 100 - (value - 0.05) * 400  # 线性递减
                            elif value <= 0.2:
                                normalized_value = 80 - (value - 0.1) * 200    # 线性递减
                            elif value <= 0.5:
                                normalized_value = 60 - (value - 0.2) * 200    # 线性递减
                            else:
                                normalized_value = 0
                        else:
                            # 其他负向指标：简单转换
                            normalized_value = max(0, 100 - value)

                        score += max(0, min(100, normalized_value)) * abs(weight)

            return max(0, min(100, score))

        except Exception as e:
            logger.error(f"计算执行质量评分失败: {e}")
            return 0

    def _update_execution_score(self, score: float):
        """更新执行质量评分显示"""
        try:
            if score >= 90:
                level = "优秀"
                color = "#27ae60"
            elif score >= 80:
                level = "良好"
                color = "#2ecc71"
            elif score >= 70:
                level = "一般"
                color = "#f39c12"
            elif score >= 60:
                level = "较差"
                color = "#e67e22"
            else:
                level = "差"
                color = "#e74c3c"

            self.execution_score_label.setText(f"执行质量评分: {score:.1f} ({level})")
            self.execution_score_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {color};")

            self.execution_score_bar.setValue(int(score))
            self.execution_score_bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 2px solid grey;
                    border-radius: 5px;
                    text-align: center;
                    font-weight: bold;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 3px;
                }}
            """)

        except Exception as e:
            logger.error(f"更新执行质量评分显示失败: {e}")

    def add_realtime_order(self, order_data: Dict[str, Any]):
        """添加实时订单到监控表格"""
        try:
            row_count = self.realtime_orders_table.rowCount()
            self.realtime_orders_table.insertRow(row_count)

            # 计算TWAP/VWAP偏差
            twap_deviation = self._calculate_twap_deviation(order_data)
            vwap_deviation = self._calculate_vwap_deviation(order_data)

            # 填充订单数据
            items = [
                order_data.get('time', ''),
                order_data.get('symbol', ''),
                order_data.get('direction', ''),
                str(order_data.get('quantity', 0)),
                f"{order_data.get('price', 0):.2f}",
                order_data.get('status', ''),
                f"{order_data.get('latency', 0):.0f}",
                f"{order_data.get('slippage', 0):.2f}"
            ]

            for col, item in enumerate(items):
                self.realtime_orders_table.setItem(row_count, col, QTableWidgetItem(item))

            # 保持最新的订单在顶部
            if row_count > 50:  # 限制显示最近50条
                self.realtime_orders_table.removeRow(0)

        except Exception as e:
            logger.error(f"添加实时订单失败: {e}")

    def _calculate_twap_deviation(self, order_data: Dict[str, Any]) -> float:
        """计算TWAP偏差"""
        try:
            from core.trading.execution_benchmarks import get_execution_benchmarks
            from datetime import datetime, timedelta

            symbol = order_data.get('symbol', '')
            execution_price = order_data.get('price', 0)
            order_time = order_data.get('time', '')

            if not symbol or not execution_price or not order_time:
                return 0.0

            # 解析订单时间
            if isinstance(order_time, str):
                order_datetime = datetime.strptime(order_time, '%H:%M:%S')
                # 假设是今天的时间
                today = datetime.now().date()
                order_datetime = datetime.combine(today, order_datetime.time())
            else:
                order_datetime = order_time

            # 计算TWAP时间窗口（订单前后30分钟）
            start_time = order_datetime - timedelta(minutes=30)
            end_time = order_datetime + timedelta(minutes=30)

            # 获取基准价格
            benchmarks = get_execution_benchmarks()
            benchmark_prices = benchmarks.get_benchmark_prices(symbol, start_time, end_time)

            twap_price = benchmark_prices.get('twap', 0)
            if twap_price > 0:
                deviation = benchmarks.calculate_execution_deviation(execution_price, twap_price)
                return deviation

            return 0.0

        except Exception as e:
            logger.debug(f"TWAP偏差计算失败: {e}")
            return 0.0

    def _calculate_vwap_deviation(self, order_data: Dict[str, Any]) -> float:
        """计算VWAP偏差"""
        try:
            from core.trading.execution_benchmarks import get_execution_benchmarks
            from datetime import datetime, timedelta

            symbol = order_data.get('symbol', '')
            execution_price = order_data.get('price', 0)
            order_time = order_data.get('time', '')

            if not symbol or not execution_price or not order_time:
                return 0.0

            # 解析订单时间
            if isinstance(order_time, str):
                order_datetime = datetime.strptime(order_time, '%H:%M:%S')
                today = datetime.now().date()
                order_datetime = datetime.combine(today, order_datetime.time())
            else:
                order_datetime = order_time

            # 计算VWAP时间窗口（订单前后30分钟）
            start_time = order_datetime - timedelta(minutes=30)
            end_time = order_datetime + timedelta(minutes=30)

            # 获取基准价格
            benchmarks = get_execution_benchmarks()
            benchmark_prices = benchmarks.get_benchmark_prices(symbol, start_time, end_time)

            vwap_price = benchmark_prices.get('vwap', 0)
            if vwap_price > 0:
                deviation = benchmarks.calculate_execution_deviation(execution_price, vwap_price)
                return deviation

            return 0.0

        except Exception as e:
            logger.debug(f"VWAP偏差计算失败: {e}")
            return 0.0

    def update_execution_analysis(self):
        """更新执行分析"""
        try:
            period = self.analysis_period_combo.currentText()
            stock_filter = self.stock_filter_combo.currentText()
            logger.info(f"更新执行分析: 周期={period}, 筛选={stock_filter}")

            # 这里应该从数据库加载实际的执行分析数据

        except Exception as e:
            logger.error(f"更新执行分析失败: {e}")

    def refresh_execution_analysis(self):
        """刷新执行分析"""
        try:
            self.update_execution_analysis()
        except Exception as e:
            logger.error(f"刷新执行分析失败: {e}")

    def load_order_history(self):
        """加载订单历史"""
        try:
            from db.models.performance_history_models import get_performance_history_manager
            from datetime import datetime, timedelta

            time_range = self.history_time_combo.currentText()
            logger.info(f"加载订单历史: {time_range}")

            # 计算时间范围
            end_time = datetime.now()
            if time_range == "今日":
                start_time = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
            elif time_range == "最近3天":
                start_time = end_time - timedelta(days=3)
            elif time_range == "最近7天":
                start_time = end_time - timedelta(days=7)
            elif time_range == "最近30天":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(days=1)

            # 从数据库获取执行历史数据
            history_manager = get_performance_history_manager()
            execution_records = history_manager.get_execution_history(
                start_time=start_time,
                end_time=end_time,
                limit=1000
            )

            # 更新历史表格
            self._update_order_history_table(execution_records)

            # 更新统计信息
            self._update_execution_statistics(execution_records)

        except Exception as e:
            logger.error(f"加载订单历史失败: {e}")

    def _update_order_history_table(self, records):
        """更新订单历史表格"""
        try:
            self.order_history_table.setRowCount(len(records))

            for row, record in enumerate(records):
                items = [
                    record.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    record.order_id,
                    record.symbol,
                    record.symbol,  # 股票名称，这里简化使用代码
                    "买入" if record.direction == "buy" else "卖出",
                    str(record.quantity),
                    f"{record.order_price:.2f}",
                    str(record.quantity),  # 成交数量，这里简化
                    f"{record.execution_price:.2f}",
                    record.order_status,
                    f"{record.latency_ms:.0f}",
                    f"{record.slippage_pct:.2f}"
                ]

                for col, item in enumerate(items):
                    table_item = QTableWidgetItem(item)

                    # 根据订单状态设置颜色
                    if record.order_status == "filled":
                        table_item.setBackground(QColor("#e8f5e8"))  # 浅绿色
                    elif record.order_status == "cancelled":
                        table_item.setBackground(QColor("#ffebee"))  # 浅红色
                    elif record.order_status == "partial":
                        table_item.setBackground(QColor("#fff3e0"))  # 浅橙色

                    self.order_history_table.setItem(row, col, table_item)

            logger.info(f"订单历史表格已更新: {len(records)}条记录")

        except Exception as e:
            logger.error(f"更新订单历史表格失败: {e}")

    def _update_execution_statistics(self, records):
        """更新执行统计信息"""
        try:
            if not records:
                self.total_orders_label.setText("总订单数: 0")
                self.success_rate_label.setText("成功率: 0%")
                self.avg_slippage_label.setText("平均滑点: 0%")
                self.avg_latency_label.setText("平均延迟: 0ms")
                return

            # 计算统计信息
            total_orders = len(records)
            filled_orders = len([r for r in records if r.order_status == "filled"])
            success_rate = (filled_orders / total_orders) * 100 if total_orders > 0 else 0

            # 计算平均滑点和延迟
            slippages = [abs(r.slippage_pct) for r in records if r.slippage_pct != 0]
            latencies = [r.latency_ms for r in records if r.latency_ms > 0]

            avg_slippage = sum(slippages) / len(slippages) if slippages else 0
            avg_latency = sum(latencies) / len(latencies) if latencies else 0

            # 更新标签
            self.total_orders_label.setText(f"总订单数: {total_orders}")
            self.success_rate_label.setText(f"成功率: {success_rate:.1f}%")
            self.avg_slippage_label.setText(f"平均滑点: {avg_slippage:.2f}%")
            self.avg_latency_label.setText(f"平均延迟: {avg_latency:.0f}ms")

        except Exception as e:
            logger.error(f"更新执行统计信息失败: {e}")

    def save_execution_record(self, order_data: Dict[str, Any]):
        """保存执行记录到数据库"""
        try:
            from db.models.performance_history_models import get_performance_history_manager, ExecutionHistoryRecord
            from datetime import datetime
            import uuid

            # 计算TWAP/VWAP偏差
            twap_deviation = self._calculate_twap_deviation(order_data)
            vwap_deviation = self._calculate_vwap_deviation(order_data)

            # 计算执行质量评分
            execution_metrics = {
                '平均延迟': order_data.get('latency', 0),
                '成交率': 100.0 if order_data.get('status') == 'filled' else 0.0,
                '平均滑点': abs(order_data.get('slippage', 0)),
                '交易成本': order_data.get('cost', 0),
                '市场冲击': order_data.get('market_impact', 0),
                '执行效率': 90.0,  # 默认值
                '订单完成率': 100.0 if order_data.get('status') == 'filled' else 0.0
            }
            quality_score = self._calculate_execution_score(execution_metrics)

            # 创建执行历史记录
            record = ExecutionHistoryRecord(
                timestamp=datetime.now(),
                order_id=order_data.get('order_id', str(uuid.uuid4())),
                symbol=order_data.get('symbol', ''),
                direction=order_data.get('direction', 'buy'),
                quantity=order_data.get('quantity', 0),
                order_price=order_data.get('order_price', 0),
                execution_price=order_data.get('price', 0),
                execution_time=datetime.now(),
                latency_ms=order_data.get('latency', 0),
                slippage_pct=order_data.get('slippage', 0),
                trading_cost_pct=order_data.get('cost', 0),
                market_impact_pct=order_data.get('market_impact', 0),
                twap_deviation_pct=twap_deviation,
                vwap_deviation_pct=vwap_deviation,
                implementation_shortfall_pct=0.0,  # 需要更多数据计算
                execution_quality_score=quality_score,
                order_status=order_data.get('status', 'unknown'),
                venue=order_data.get('venue', ''),
                notes=order_data.get('notes', '')
            )

            # 保存到数据库
            history_manager = get_performance_history_manager()
            success = history_manager.save_execution_record(record)

            if success:
                logger.debug(f"执行历史记录已保存: {record.order_id}")
            else:
                logger.warning(f"执行历史记录保存失败: {record.order_id}")

        except Exception as e:
            logger.debug(f"保存执行历史记录失败: {e}")

    def filter_order_history(self):
        """筛选订单历史"""
        try:
            status_filter = self.order_status_combo.currentText()
            logger.info(f"筛选订单历史: {status_filter}")

        except Exception as e:
            logger.error(f"筛选订单历史失败: {e}")

    def export_order_history(self):
        """导出订单历史"""
        try:
            logger.info("导出订单历史数据")
            # 这里应该实现实际的数据导出功能

        except Exception as e:
            logger.error(f"导出订单历史失败: {e}")

    def update_data(self, data: Dict[str, any]):
        """统一数据更新接口"""
        try:
            if 'execution_metrics' in data:
                self.update_execution_data(data['execution_metrics'])

            if 'realtime_order' in data:
                self.add_realtime_order(data['realtime_order'])

        except Exception as e:
            logger.error(f"更新交易执行监控数据失败: {e}")

    def _on_theme_changed(self):
        """主题变化回调"""
        try:
            # 更新所有卡片的主题样式
            if hasattr(self, 'cards'):
                for card in self.cards.values():
                    if hasattr(card, 'update_theme'):
                        card.update_theme()
            if hasattr(self, 'execution_cards'):
                for card in self.execution_cards.values():
                    if hasattr(card, 'update_theme'):
                        card.update_theme()
            
            # 更新图表主题
            if hasattr(self, 'execution_chart') and hasattr(self.execution_chart, 'update_theme'):
                self.execution_chart.update_theme()
                
            logger.debug("交易执行监控标签页主题已更新")
        except Exception as e:
            logger.error(f"更新交易执行监控标签页主题失败: {e}")

    def cleanup(self):
        """清理资源 - 优化性能，避免卡顿"""
        try:
            # 清理图表 - 添加异常处理
            if hasattr(self, 'execution_chart') and self.execution_chart:
                try:
                    if hasattr(self.execution_chart, 'cleanup'):
                        self.execution_chart.cleanup()
                except Exception as e:
                    logger.debug(f"清理执行图表失败: {e}")
            
            # 清理指标卡片 - 添加异常处理
            if hasattr(self, 'execution_cards'):
                for card in self.execution_cards.values():
                    try:
                        if hasattr(card, 'cleanup'):
                            card.cleanup()
                    except Exception as e:
                        logger.debug(f"清理指标卡片失败: {e}")
            
            # 清理表格 - 添加异常处理
            if hasattr(self, 'order_history_table'):
                try:
                    self.order_history_table.clearContents()
                    self.order_history_table.setRowCount(0)
                except Exception as e:
                    logger.debug(f"清理表格失败: {e}")
            
            # 清理执行数据 - 添加异常处理
            if hasattr(self, 'execution_data'):
                try:
                    self.execution_data.clear()
                except Exception as e:
                    logger.debug(f"清理执行数据失败: {e}")
            if hasattr(self, 'order_history'):
                try:
                    self.order_history.clear()
                except Exception as e:
                    logger.debug(f"清理订单历史失败: {e}")
            
            logger.debug("ModernTradingExecutionMonitorTab cleanup completed")
            
        except Exception as e:
            logger.debug(f"清理资源失败: {e}")

    def resizeEvent(self, event):
        """窗口大小改变事件处理"""
        super().resizeEvent(event)
        self._update_responsive_layout()

    def _update_responsive_layout(self):
        """更新响应式布局"""
        try:
            window_width = self.width()
            window_height = self.height()

            logger.debug(f"TradingExecutionMonitorTab 响应式布局更新: {window_width}x{window_height}")

            # 更新执行指标卡片高度
            cards_frames = self.findChildren(QFrame)
            for frame in cards_frames:
                if frame.layout() and isinstance(frame.layout(), QGridLayout):
                    frame_height = max(100, int(window_height * 0.18))
                    frame.setMinimumHeight(frame_height)
                    frame.setMaximumHeight(int(window_height * 0.22))

            # 更新滑点分布图高度
            if hasattr(self, 'slippage_chart'):
                chart_height = max(120, int(window_height * 0.25))
                self.slippage_chart.setMinimumHeight(chart_height)

            # 更新延迟分布图高度
            if hasattr(self, 'latency_chart'):
                chart_height = max(120, int(window_height * 0.25))
                self.latency_chart.setMinimumHeight(chart_height)

            # 更新执行质量趋势图高度
            if hasattr(self, 'quality_trend_chart'):
                chart_height = max(120, int(window_height * 0.25))
                self.quality_trend_chart.setMinimumHeight(chart_height)

        except Exception as e:
            logger.error(f"更新响应式布局失败: {e}")
