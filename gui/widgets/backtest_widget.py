from loguru import logger
"""
专业级回测UI组件
集成到FactorWeave-Quant GUI系统中，提供实时回测监控和数据联动功能
对标行业专业软件标准
"""
import matplotlib
matplotlib.use('Agg')
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

# 明确导入QAbstractItemView以防止运行时错误
from PyQt5.QtWidgets import QAbstractItemView
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import threading
from threading import Lock
import time
import queue
from typing import Dict, List, Optional, Any, Tuple
import json
from pathlib import Path

# 导入matplotlib相关
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates
from matplotlib.animation import FuncAnimation


# 配置中文字体
try:
    from utils.matplotlib_font_config import configure_matplotlib_chinese_font
    configure_matplotlib_chinese_font()
except ImportError:
    logger.info("无法导入字体配置工具，使用默认配置")

# 导入回测相关模块
try:
    from backtest.unified_backtest_engine import (
        UnifiedBacktestEngine, BacktestLevel, create_unified_backtest_engine
    )
    from backtest.real_time_backtest_monitor import RealTimeBacktestMonitor, MonitoringLevel
    from backtest.ultra_performance_optimizer import UltraPerformanceOptimizer, PerformanceLevel
    from backtest.backtest_validator import ProfessionalBacktestValidator
except ImportError:
    # 如果导入失败，创建模拟类
    class BacktestLevel:
        BASIC = "basic"
        PROFESSIONAL = "professional"
        INSTITUTIONAL = "institutional"
        INVESTMENT_BANK = "investment_bank"

    class MonitoringLevel:
        BASIC = "BASIC"
        STANDARD = "STANDARD"
        ADVANCED = "ADVANCED"
        REAL_TIME = "REAL_TIME"

# 导入统一图表服务
try:
    from core.services.unified_chart_service import get_unified_chart_service
    from gui.widgets.chart_widget import ChartWidget
    UNIFIED_CHART_AVAILABLE = True
except ImportError:
    UNIFIED_CHART_AVAILABLE = False

# 导入核心模块
try:
    from utils.config_manager import ConfigManager
    CORE_MODULES_AVAILABLE = True
except ImportError:
    # 如果核心模块不可用，使用简化版本
    try:
        # 尝试导入基础日志管理器
        from core.base_logger import BaseLogger
    except ImportError:

        class LogManager:
            def log(self, message, level):
                logger.info(f"[{level}] {message}")

            def info(self, message):
                logger.info(f"[INFO] {message}")

            def warning(self, message):
                logger.info(f" {message}")

            def error(self, message):
                logger.info(f"[ERROR] {message}")

    # 简化版配置管理器
    class ConfigManager:
        def __init__(self):
            self.config = {
                'backtest': {
                    'initial_capital': 100000,
                    'commission_pct': 0.001,
                    'slippage_pct': 0.001
                },
                'ui': {
                    'theme': 'dark',
                    'update_interval': 1000
                }
            }

        def get(self, key, default=None):
            keys = key.split('.')
            value = self.config
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value

    CORE_MODULES_AVAILABLE = False


class RealTimeChart(QWidget):
    """实时图表组件 - 基于统一图表服务的高性能实现"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_queue = queue.Queue()
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        if UNIFIED_CHART_AVAILABLE:
            # 使用统一图表服务
            self.chart_widget = ChartWidget(self)
            layout.addWidget(self.chart_widget)

            # 配置图表
            self.setup_chart()
        else:
            # 降级到简单显示
            self.fallback_widget = QLabel("图表服务不可用，请检查依赖")
            self.fallback_widget.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.fallback_widget)

        # 启动定时器更新数据
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_charts)
        self.timer.start(1000)  # 每秒更新一次

    def setup_chart(self):
        """设置图表配置"""
        if not UNIFIED_CHART_AVAILABLE:
            return

        try:
            # 获取统一图表服务
            chart_service = get_unified_chart_service()

            # 配置图表主题（如果支持）
            if hasattr(chart_service, 'apply_theme'):
                chart_service.apply_theme(self.chart_widget, 'dark')
            else:
                logger.debug("图表服务不支持apply_theme方法")

            # 设置图表类型为多子图模式
            self.chart_widget.set_chart_type('multi_panel')

            # 启用实时更新
            self.chart_widget.enable_real_time_update(True)

        except Exception as e:
            logger.error(f"图表设置失败: {e}")

    def update_charts(self):
        """更新图表"""
        if not UNIFIED_CHART_AVAILABLE:
            return

        try:
            # 获取最新数据
            if not self.data_queue.empty():
                data = []
                while not self.data_queue.empty():
                    data.append(self.data_queue.get())

                if data:
                    # 转换为DataFrame
                    df = pd.DataFrame(data)

                    # 更新图表数据
                    self.chart_widget.update_data(df)

        except Exception as e:
            logger.error(f"图表更新失败: {e}")

    def add_data(self, data: Dict):
        """添加数据到队列"""
        self.data_queue.put(data)

    def clear_data(self):
        """清空数据"""
        while not self.data_queue.empty():
            self.data_queue.get()

        if UNIFIED_CHART_AVAILABLE and hasattr(self, 'chart_widget'):
            self.chart_widget.clear_data()

    def set_chart_type(self, chart_type: str):
        """设置图表类型"""
        if UNIFIED_CHART_AVAILABLE and hasattr(self, 'chart_widget'):
            self.chart_widget.set_chart_type(chart_type)

    def apply_theme(self, theme: str):
        """应用主题"""
        if UNIFIED_CHART_AVAILABLE and hasattr(self, 'chart_widget'):
            chart_service = get_unified_chart_service()
            if hasattr(chart_service, 'apply_theme'):
                chart_service.apply_theme(self.chart_widget, theme)
            else:
                logger.debug("图表服务不支持apply_theme方法")


class MetricsPanel(QWidget):
    """指标面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(2)  # 进一步减少间距
        layout.setContentsMargins(4, 4, 4, 4)  # 进一步减少边距

        # 标题
        title = QLabel("关键指标")
        title.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: 600;
                color: #48bb78;
                padding: 6px 8px;
                border-bottom: 1px solid #48bb78;
                margin-bottom: 4px;
                background: rgba(72, 187, 120, 0.1);
                border-radius: 4px;
            }
        """)
        layout.addWidget(title)

        # 指标表格 - 扩展为更多指标
        self.metrics_table = QTableWidget(4, 5)  # 4行5列，重要指标在前
        self.metrics_table.setMaximumHeight(400)  # 增加高度
        self.metrics_table.setMinimumHeight(180)   # 增加最小高度

        # 设置专业表格样式
        self.metrics_table.setStyleSheet("""
            QTableWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1f2e, stop:1 #0f1419);
                border: 2px solid #2d3748;
                border-radius: 8px;
                gridline-color: #4a5568;
                font-size: 11px;
                font-family: 'Consolas', 'Monaco', monospace;
                selection-background-color: #4299e1;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border: 1px solid #2d3748;
                text-align: center;
                min-height: 20px;
            }
            QTableWidget::item:hover {
                background-color: rgba(66, 153, 225, 0.2);
                border: 1px solid #4299e1;
            }
            QTableWidget::item:selected {
                background-color: rgba(66, 153, 225, 0.3);
                color: #ffffff;
                font-weight: bold;
            }
            QHeaderView::section {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a5568, stop:1 #2d3748);
                color: #e2e8f0;
                padding: 8px;
                border: 1px solid #4a5568;
                font-weight: 700;
                font-size: 10px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            QHeaderView::section:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5a6578, stop:1 #3d4758);
            }
        """)

        # 设置表头 - 重要指标在前
        headers = ["总收益率", "年化收益", "Sharpe比率", "最大回撤", "胜率"]
        self.metrics_table.setHorizontalHeaderLabels(headers)
        self.metrics_table.setVerticalHeaderLabels(["核心指标", "风险指标", "交易指标", "其他指标"])

        # 设置表格属性
        self.metrics_table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # 不可编辑
        self.metrics_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.metrics_table.horizontalHeader().setStretchLastSection(True)
        self.metrics_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.metrics_table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # 初始化表格数据
        self.init_metrics_table()

        layout.addWidget(self.metrics_table)

    def init_metrics_table(self):
        """初始化指标表格数据"""
        # 初始化数据 - 4行5列，重要指标在前
        initial_data = [
            # 核心指标行（最重要）
            ["0.00%", "0.00%", "0.000", "0.00%", "0.00%"],
            # 风险指标行
            ["VaR: 0.00%", "β: 0.000", "偏度: 0.00", "峰度: 0.00", "波动率: 0.00%"],
            # 交易指标行
            ["交易: 0次", "盈亏比: 0.00", "期望: 0.00%", "连胜: 0次", "持仓: 0天"],
            # 其他指标行
            ["换手: 0.00%", "α: 0.000", "Sortino: 0.000", "盈利因子: 0.00", "期望收益: 0.00%"]
        ]

        for row in range(4):
            for col in range(5):
                item = QTableWidgetItem(initial_data[row][col])
                item.setTextAlignment(Qt.AlignCenter)

                # 设置不同行的样式
                if row == 0:  # 核心指标行
                    item.setForeground(QColor("#ffffff"))
                    font = item.font()
                    font.setBold(True)
                    font.setPointSize(11)
                    item.setFont(font)
                elif row == 1:  # 风险指标行
                    item.setForeground(QColor("#fbbf24"))  # 黄色
                    font = item.font()
                    font.setPointSize(10)
                    item.setFont(font)
                elif row == 2:  # 交易指标行
                    item.setForeground(QColor("#34d399"))  # 绿色
                    font = item.font()
                    font.setPointSize(10)
                    item.setFont(font)
                else:  # 其他指标行
                    item.setForeground(QColor("#a0aec0"))  # 灰色
                    font = item.font()
                    font.setPointSize(9)
                    item.setFont(font)

                self.metrics_table.setItem(row, col, item)

    def update_metrics(self, metrics: Dict):
        """更新指标表格"""
        try:
            # 准备所有指标数据
            total_return = metrics.get('total_return', 0)
            annualized_return = metrics.get('annualized_return', 0)
            sharpe_ratio = metrics.get('sharpe_ratio', 0)
            sortino_ratio = metrics.get('sortino_ratio', 0)
            max_drawdown = metrics.get('max_drawdown', 0)
            win_rate = metrics.get('win_rate', 0)

            # 风险指标
            var_95 = metrics.get('var_95', 0)
            beta = metrics.get('beta', 0)
            skew = metrics.get('skew', 0)
            kurtosis = metrics.get('kurtosis', 0)
            volatility = metrics.get('volatility', 0)
            alpha = metrics.get('alpha', 0)

            # 交易指标
            trade_count = metrics.get('trade_count', 0)
            profit_loss_ratio = metrics.get('profit_loss_ratio', 0)
            expectancy = metrics.get('expectancy', 0)
            max_consecutive_wins = metrics.get('max_consecutive_wins', 0)
            avg_holding_period = metrics.get('avg_holding_period', 0)
            turnover_rate = metrics.get('turnover_rate', 0)

            # 更新表格数据 - 4行5列，重要指标在前
            table_data = [
                # 核心指标行（最重要）
                [f"{total_return:.2%}", f"{annualized_return:.2%}", f"{sharpe_ratio:.3f}",
                 f"{max_drawdown:.2%}", f"{win_rate:.2%}"],
                # 风险指标行
                [f"VaR: {var_95:.2%}", f"β: {beta:.3f}", f"偏度: {skew:.2f}",
                 f"峰度: {kurtosis:.2f}", f"波动率: {volatility:.2%}"],
                # 交易指标行
                [f"交易: {trade_count}次", f"盈亏比: {profit_loss_ratio:.2f}", f"期望: {expectancy:.2%}",
                 f"连胜: {max_consecutive_wins}次", f"持仓: {avg_holding_period:.0f}天"],
                # 其他指标行
                [f"换手: {turnover_rate:.2%}", f"α: {alpha:.3f}", f"Sortino: {sortino_ratio:.3f}",
                 f"盈利因子: {profit_loss_ratio:.2f}", f"期望收益: {annualized_return:.2%}"]
            ]

            for row in range(4):
                for col in range(5):
                    item = self.metrics_table.item(row, col)
                    if item:
                        item.setText(table_data[row][col])

                        # 根据数值和行设置颜色
                        if row == 0:  # 核心指标行（重要指标，颜色动态变化）
                            if col == 0:  # 总收益率
                                color = "#10b981" if total_return >= 0 else "#ef4444"
                            elif col == 1:  # 年化收益
                                color = "#10b981" if annualized_return >= 0 else "#ef4444"
                            elif col == 2:  # Sharpe比率
                                color = "#10b981" if sharpe_ratio >= 1.0 else "#f59e0b" if sharpe_ratio >= 0.5 else "#ef4444"
                            elif col == 3:  # 最大回撤
                                color = "#10b981" if max_drawdown <= 0.1 else "#f59e0b" if max_drawdown <= 0.2 else "#ef4444"
                            else:  # 胜率
                                color = "#10b981" if win_rate >= 0.6 else "#f59e0b" if win_rate >= 0.5 else "#ef4444"

                            item.setForeground(QColor(color))
                            font = item.font()
                            font.setBold(True)
                            font.setPointSize(11)
                            item.setFont(font)

                        elif row == 1:  # 风险指标行
                            item.setForeground(QColor("#fbbf24"))  # 统一黄色
                            font = item.font()
                            font.setPointSize(10)
                            item.setFont(font)

                        elif row == 2:  # 交易指标行
                            item.setForeground(QColor("#34d399"))  # 统一绿色
                            font = item.font()
                            font.setPointSize(10)
                            item.setFont(font)

                        else:  # 其他指标行
                            item.setForeground(QColor("#a0aec0"))  # 统一灰色
                            font = item.font()
                            font.setPointSize(9)
                            item.setFont(font)

        except Exception as e:
            logger.error(f"更新指标表格失败: {e}")


class ControlPanel(QWidget):
    """控制面板"""

    # 定义信号
    start_backtest = pyqtSignal(dict)
    stop_backtest = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("控制面板")
        title.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: 600;
                color: #4299e1;
                padding: 6px 8px;
                border-bottom: 1px solid #4299e1;
                margin-bottom: 4px;
                background: rgba(66, 153, 225, 0.1);
                border-radius: 4px;
            }
        """)
        layout.addWidget(title)

        # 参数设置组
        params_group = QGroupBox("回测参数")
        params_group.setStyleSheet("""
            QGroupBox {
                font-weight: 500;
                font-size: 11px;
                border: 1px solid #4a5568;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 6px;
                color: #e2e8f0;
                background: rgba(45, 55, 72, 0.2);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
                color: #cbd5e0;
                font-size: 10px;
            }
        """)
        params_layout = QFormLayout(params_group)

        # 初始资金
        self.initial_capital = QSpinBox()
        self.initial_capital.setRange(10000, 100000000)
        self.initial_capital.setValue(1000000)
        self.initial_capital.setSuffix("元")
        params_layout.addRow("初始资金:", self.initial_capital)

        # 仓位大小
        self.position_size = QDoubleSpinBox()
        self.position_size.setRange(0.1, 1.0)
        self.position_size.setValue(0.95)
        self.position_size.setSingleStep(0.05)
        self.position_size.setSuffix("%")
        params_layout.addRow("仓位大小:", self.position_size)

        # 手续费率
        self.commission_pct = QDoubleSpinBox()
        self.commission_pct.setRange(0.0001, 0.01)
        self.commission_pct.setValue(0.0003)
        self.commission_pct.setDecimals(4)
        self.commission_pct.setSuffix("%")
        params_layout.addRow("手续费率:", self.commission_pct)

        # 专业级别
        self.professional_level = QComboBox()
        self.professional_level.addItems([
            "RETAIL", "INSTITUTIONAL", "HEDGE_FUND", "INVESTMENT_BANK"
        ])
        self.professional_level.setCurrentText("INVESTMENT_BANK")
        params_layout.addRow("专业级别:", self.professional_level)

        # 性能级别
        self.performance_level = QComboBox()
        self.performance_level.addItems([
            "STANDARD", "HIGH", "ULTRA", "EXTREME"
        ])
        self.performance_level.setCurrentText("ULTRA")
        params_layout.addRow("性能级别:", self.performance_level)

        # 时间范围设置组
        time_group = QGroupBox("时间范围设置")
        time_group.setStyleSheet(params_group.styleSheet())
        time_layout = QFormLayout(time_group)

        # 开始日期
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addYears(-1))
        self.start_date.setCalendarPopup(True)
        time_layout.addRow("开始日期:", self.start_date)

        # 结束日期
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        time_layout.addRow("结束日期:", self.end_date)

        # 数据频率
        self.data_frequency = QComboBox()
        self.data_frequency.addItems(["日线", "小时线", "30分钟", "15分钟", "5分钟", "1分钟"])
        self.data_frequency.setCurrentText("日线")
        time_layout.addRow("数据频率:", self.data_frequency)

        # 基准对比设置组
        benchmark_group = QGroupBox("基准对比设置")
        benchmark_group.setStyleSheet(params_group.styleSheet())
        benchmark_layout = QFormLayout(benchmark_group)

        # 基准指数选择
        self.benchmark_index = QComboBox()
        self.benchmark_index.addItems([
            "无基准", "沪深300", "中证500", "创业板指", "上证50",
            "科创50", "恒生指数", "纳斯达克", "标普500"
        ])
        self.benchmark_index.setCurrentText("沪深300")
        benchmark_layout.addRow("基准指数:", self.benchmark_index)

        # 引擎选择
        engine_group = QGroupBox("回测引擎设置")
        engine_group.setStyleSheet(params_group.styleSheet())
        engine_layout = QFormLayout(engine_group)

        # 引擎类型选择
        self.engine_type = QComboBox()
        self.engine_type.addItems([
            "自动选择（推荐）", "向量化引擎", "标准引擎"
        ])
        self.engine_type.setCurrentText("自动选择（推荐）")
        self.engine_type.setToolTip("自动选择：根据数据大小和功能需求智能选择最优引擎\n向量化引擎：高性能，适合大数据集\n标准引擎：功能完整，支持高级功能")
        engine_layout.addRow("引擎类型:", self.engine_type)

        # 向量化选项
        self.use_vectorized = QCheckBox("启用向量化优化")
        self.use_vectorized.setChecked(True)
        self.use_vectorized.setToolTip("启用向量化计算，可提升3-5倍性能")
        engine_layout.addRow("", self.use_vectorized)

        # 自动选择选项
        self.auto_select = QCheckBox("智能引擎选择")
        self.auto_select.setChecked(True)
        self.auto_select.setToolTip("根据数据大小和功能需求自动选择最优引擎")
        engine_layout.addRow("", self.auto_select)

        layout.addWidget(params_group)
        layout.addWidget(engine_group)

        # 控制按钮
        buttons_layout = QHBoxLayout()

        self.start_button = QPushButton("开始回测")
        self.start_button.setStyleSheet("""
            QPushButton {
                background: linear-gradient(45deg, #10d4ff, #8b5cf6);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background: linear-gradient(45deg, #0099cc, #6d28d9);
            }
            QPushButton:pressed {
                background: linear-gradient(45deg, #0066aa, #5b21b6);
            }
        """)
        self.start_button.clicked.connect(self.on_start_backtest)

        self.stop_button = QPushButton("停止回测")
        self.stop_button.setStyleSheet("""
            QPushButton {
                background: linear-gradient(45deg, #1f4444, #dc2626);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background: linear-gradient(45deg, #dc2626, #b91c1c);
            }
            QPushButton:pressed {
                background: linear-gradient(45deg, #b91c1c, #991b1b);
            }
        """)
        self.stop_button.clicked.connect(self.stop_backtest.emit)
        self.stop_button.setEnabled(False)

        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.stop_button)
        layout.addLayout(buttons_layout)

        # 状态显示
        self.status_label = QLabel("状态: 就绪")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #10b981;
                font-weight: bold;
                padding: 10px;
                border: 1px solid #2d3748;
                border-radius: 5px;
                background-color: #1e2329;
            }
        """)
        layout.addWidget(self.status_label)

        layout.addStretch()

    def on_start_backtest(self):
        """开始回测"""
        # 解析引擎选择
        engine_type_text = self.engine_type.currentText()
        if engine_type_text == "自动选择（推荐）":
            use_vectorized_engine = self.use_vectorized.isChecked()
            auto_select_engine = True
        elif engine_type_text == "向量化引擎":
            use_vectorized_engine = True
            auto_select_engine = False
        else:  # 标准引擎
            use_vectorized_engine = False
            auto_select_engine = False

        params = {
            'initial_capital': self.initial_capital.value(),
            'position_size': self.position_size.value() / 100,
            'commission_pct': self.commission_pct.value() / 100,
            'professional_level': self.professional_level.currentText(),
            'performance_level': self.performance_level.currentText(),
            'use_vectorized_engine': use_vectorized_engine,
            'auto_select_engine': auto_select_engine
        }

        self.start_backtest.emit(params)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("状态: 运行中")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #f59e0b;
                font-weight: bold;
                padding: 10px;
                border: 1px solid #2d3748;
                border-radius: 5px;
                background-color: #1e2329;
            }
        """)

    def on_stop_backtest(self):
        """停止回测"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("状态: 已停止")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #ef4444;
                font-weight: bold;
                padding: 10px;
                border: 1px solid #2d3748;
                border-radius: 5px;
                background-color: #1e2329;
            }
        """)


class AlertsPanel(QWidget):
    """预警面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.alerts = []
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("监控中心")
        title.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: 600;
                color: #f6ad55;
                padding: 6px 8px;
                border-bottom: 1px solid #f6ad55;
                margin-bottom: 4px;
                background: rgba(246, 173, 85, 0.1);
                border-radius: 4px;
            }
        """)
        layout.addWidget(title)

        # 性能指标显示
        self.performance_group = QGroupBox("性能指标")
        performance_layout = QFormLayout(self.performance_group)

        self.engine_type_label = QLabel("未启动")
        self.execution_time_label = QLabel("0.00秒")
        self.data_size_label = QLabel("0条")
        self.trade_count_label = QLabel("0次")

        performance_layout.addRow("引擎类型:", self.engine_type_label)
        performance_layout.addRow("执行时间:", self.execution_time_label)
        performance_layout.addRow("数据量:", self.data_size_label)
        performance_layout.addRow("交易次数:", self.trade_count_label)

        layout.addWidget(self.performance_group)

        # 预警列表
        self.alerts_list = QListWidget()
        self.alerts_list.setStyleSheet("""
            QListWidget {
                background-color: #1e2329;
                border: 1px solid #2d3748;
                border-radius: 5px;
                color: white;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #2d3748;
            }
            QListWidget::item:selected {
                background-color: #2d3748;
            }
        """)
        layout.addWidget(self.alerts_list)

        # 清除按钮
        clear_button = QPushButton("清除预警")
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: white;
                border: 1px solid #4b5563;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        clear_button.clicked.connect(self.clear_alerts)
        layout.addWidget(clear_button)

    def add_alert(self, level: str, message: str):
        """添加预警"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # 确定图标和颜色
        if level == 'critical':
            icon = ''
            color = '#ef4444'
        elif level == 'warning':
            icon = ''
            color = '#f59e0b'
        else:
            icon = 'ℹ'
            color = '#3b82f6'

        # 创建预警项
        alert_item = QListWidgetItem()
        alert_text = f"{icon} [{timestamp}] {level.upper()}: {message}"
        alert_item.setText(alert_text)
        alert_item.setForeground(QColor(color))

        # 添加到列表顶部
        self.alerts_list.insertItem(0, alert_item)

        # 限制预警数量
        if self.alerts_list.count() > 50:
            self.alerts_list.takeItem(self.alerts_list.count() - 1)

        # 存储预警
        self.alerts.append({
            'timestamp': timestamp,
            'level': level,
            'message': message
        })

    def clear_alerts(self):
        """清除所有预警"""
        self.alerts_list.clear()
        self.alerts.clear()

    def update_performance_metrics(self, engine_type: str = None, execution_time: float = None,
                                   data_size: int = None, trade_count: int = None):
        """更新性能指标显示"""
        if engine_type:
            self.engine_type_label.setText(engine_type)
            self.engine_type_label.setStyleSheet("color: #10b981; font-weight: bold;")

        if execution_time is not None:
            self.execution_time_label.setText(f"{execution_time:.4f}秒")
            # 根据执行时间设置颜色
            if execution_time < 1.0:
                color = "#10b981"  # 绿色 - 快
            elif execution_time < 5.0:
                color = "#f59e0b"  # 黄色 - 中等
            else:
                color = "#ef4444"  # 红色 - 慢
            self.execution_time_label.setStyleSheet(f"color: {color}; font-weight: bold;")

        if data_size is not None:
            self.data_size_label.setText(f"{data_size}条")
            self.data_size_label.setStyleSheet("color: #3b82f6; font-weight: bold;")

        if trade_count is not None:
            self.trade_count_label.setText(f"{trade_count}次")
            self.trade_count_label.setStyleSheet("color: #8b5cf6; font-weight: bold;")


class ProfessionalBacktestWidget(QWidget):
    """专业级回测UI组件"""

    # 定义信号
    backtest_completed = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None, config_manager: Optional[ConfigManager] = None):
        super().__init__(parent)
        self.config_manager = config_manager or ConfigManager()
        # 纯Loguru架构，移除log_manager依赖

        # 回测相关组件
        self.backtest_engine = None
        self.monitor = None
        self.validator = None
        self.optimizer = None

        # 监控线程
        self.monitoring_thread = None
        self.is_monitoring = False
        self.monitoring_data = []
        self.monitoring_data_lock = Lock()

        # 初始化UI
        self.init_ui()

        # 初始化回测组件
        self.init_backtest_components()

    def init_ui(self):
        """初始化UI"""
        # 设置窗口样式
        self.setStyleSheet("""
            QWidget {
                background-color: #0e1117;
                color: white;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)

        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # 左侧控制面板（只保留控制和预警）
        left_panel = QVBoxLayout()
        left_panel.setSpacing(6)
        left_panel.setContentsMargins(4, 4, 4, 4)

        # 控制面板
        self.control_panel = ControlPanel()
        self.control_panel.start_backtest.connect(self.start_backtest)
        self.control_panel.stop_backtest.connect(self.stop_backtest)
        left_panel.addWidget(self.control_panel)

        # 时间范围设置面板
        self.time_panel = self.create_time_panel()
        left_panel.addWidget(self.time_panel)

        # 基准对比设置面板
        self.benchmark_panel = self.create_benchmark_panel()
        left_panel.addWidget(self.benchmark_panel)

        # 风险管理设置面板
        self.risk_panel = self.create_risk_panel()
        left_panel.addWidget(self.risk_panel)

        # 高级设置面板
        self.advanced_panel = self.create_advanced_panel()
        left_panel.addWidget(self.advanced_panel)

        # 预警面板
        self.alerts_panel = AlertsPanel()
        left_panel.addWidget(self.alerts_panel)

        # 左侧面板容器（添加滚动功能）
        left_widget = QWidget()
        left_widget.setLayout(left_panel)

        # 创建滚动区域
        left_scroll = QScrollArea()
        left_scroll.setWidget(left_widget)
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setMinimumWidth(280)  # 增加宽度
        left_scroll.setMaximumWidth(340)  # 增加最大宽度
        left_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: rgba(45, 55, 72, 0.3);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(66, 153, 225, 0.6);
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(66, 153, 225, 0.8);
            }
        """)

        # 右侧区域（指标+图表）
        right_layout = QVBoxLayout()
        right_layout.setSpacing(4)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 指标面板
        self.metrics_panel = MetricsPanel()
        # self.metrics_panel.setMaximumHeight(200)  # 进一步增加高度避免遮挡
        # self.metrics_panel.setMinimumHeight(180)  # 设置最小高度
        right_layout.addWidget(self.metrics_panel)

        # 图表区域
        self.chart_widget = RealTimeChart()
        right_layout.addWidget(self.chart_widget, 1)  # 占用剩余空间

        # 右侧容器
        right_widget = QWidget()
        right_widget.setLayout(right_layout)

        # 添加到主布局
        main_layout.addWidget(left_scroll)
        main_layout.addWidget(right_widget, 1)

    def create_time_panel(self):
        """创建时间范围设置面板"""
        group = QGroupBox("时间范围设置")
        group.setStyleSheet(self.get_group_style())
        layout = QFormLayout(group)

        # 开始日期
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addYears(-1))
        self.start_date.setCalendarPopup(True)
        layout.addRow("开始日期:", self.start_date)

        # 结束日期
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        layout.addRow("结束日期:", self.end_date)

        # 数据频率
        self.data_frequency = QComboBox()
        self.data_frequency.addItems(["日线", "小时线", "30分钟", "15分钟", "5分钟", "1分钟"])
        self.data_frequency.setCurrentText("日线")
        layout.addRow("数据频率:", self.data_frequency)

        return group

    def create_benchmark_panel(self):
        """创建基准对比设置面板"""
        group = QGroupBox("基准对比设置")
        group.setStyleSheet(self.get_group_style())
        layout = QFormLayout(group)

        # 基准指数选择
        self.benchmark_index = QComboBox()
        self.benchmark_index.addItems([
            "无基准", "沪深300", "中证500", "创业板指", "上证50",
            "科创50", "恒生指数", "纳斯达克", "标普500"
        ])
        self.benchmark_index.setCurrentText("沪深300")
        layout.addRow("基准指数:", self.benchmark_index)

        return group

    def create_risk_panel(self):
        """创建风险管理设置面板"""
        group = QGroupBox("风险管理设置")
        group.setStyleSheet(self.get_group_style())
        layout = QFormLayout(group)

        # 最大回撤限制
        self.max_drawdown_limit = QDoubleSpinBox()
        self.max_drawdown_limit.setRange(0.0, 1.0)
        self.max_drawdown_limit.setSingleStep(0.01)
        self.max_drawdown_limit.setValue(0.20)
        self.max_drawdown_limit.setSuffix("%")
        layout.addRow("最大回撤限制:", self.max_drawdown_limit)

        # 止损设置
        self.stop_loss = QDoubleSpinBox()
        self.stop_loss.setRange(0.0, 1.0)
        self.stop_loss.setSingleStep(0.01)
        self.stop_loss.setValue(0.10)
        self.stop_loss.setSuffix("%")
        layout.addRow("止损比例:", self.stop_loss)

        # 止盈设置
        self.take_profit = QDoubleSpinBox()
        self.take_profit.setRange(0.0, 5.0)
        self.take_profit.setSingleStep(0.1)
        self.take_profit.setValue(0.20)
        self.take_profit.setSuffix("%")
        layout.addRow("止盈比例:", self.take_profit)

        # 单笔最大投资比例
        self.max_position_size = QDoubleSpinBox()
        self.max_position_size.setRange(0.01, 1.0)
        self.max_position_size.setSingleStep(0.01)
        self.max_position_size.setValue(0.10)
        self.max_position_size.setSuffix("%")
        layout.addRow("单笔最大仓位:", self.max_position_size)

        return group

    def create_advanced_panel(self):
        """创建高级设置面板"""
        group = QGroupBox("高级设置")
        group.setStyleSheet(self.get_group_style())
        layout = QFormLayout(group)

        # 滑点设置
        self.slippage = QDoubleSpinBox()
        self.slippage.setRange(0.0, 0.1)
        self.slippage.setSingleStep(0.001)
        self.slippage.setValue(0.001)
        self.slippage.setSuffix("%")
        layout.addRow("滑点:", self.slippage)

        # 手续费设置
        self.commission = QDoubleSpinBox()
        self.commission.setRange(0.0, 0.01)
        self.commission.setSingleStep(0.0001)
        self.commission.setValue(0.0003)
        self.commission.setSuffix("%")
        layout.addRow("手续费:", self.commission)

        # 最小交易单位
        self.min_trade_unit = QSpinBox()
        self.min_trade_unit.setRange(1, 10000)
        self.min_trade_unit.setValue(100)
        layout.addRow("最小交易单位:", self.min_trade_unit)

        return group

    def get_group_style(self):
        """获取统一的组样式"""
        return """
            QGroupBox {
                font-weight: 500;
                font-size: 11px;
                border: 1px solid #4a5568;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 6px;
                color: #e2e8f0;
                background: rgba(45, 55, 72, 0.2);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
                color: #cbd5e0;
                font-size: 10px;
            }
        """

    def init_backtest_components(self):
        """初始化回测组件 - 修复版本"""
        try:
            logger.info("开始初始化回测组件...")

            # 初始化性能优化器 - 使用改进的错误处理
            self.performance_optimizer = None

            try:
                # 尝试导入并创建UltraPerformanceOptimizer
                from backtest.ultra_performance_optimizer import UltraPerformanceOptimizer
                self.performance_optimizer = UltraPerformanceOptimizer()
                logger.info("UltraPerformanceOptimizer初始化成功,使用GPU加速回测")
            except ImportError:
                logger.warning("📦 UltraPerformanceOptimizer模块不可用，使用基础优化器")
                self._create_fallback_optimizer()
            except Exception as e:
                logger.warning(f" UltraPerformanceOptimizer初始化失败: {e}，使用基础优化器")
                self._create_fallback_optimizer()

            # 初始化其他回测组件
            self._init_other_backtest_components()

            logger.info("回测组件初始化完成")

        except Exception as e:
            logger.error(f"[ERROR] 初始化回测组件失败: {e}")
            # 确保有基本的组件可用
            self._create_minimal_backtest_components()

    def _create_fallback_optimizer(self):
        """创建后备优化器"""
        try:
            class BasicPerformanceOptimizer:
                """基础性能优化器"""

                def __init__(self):
                    self.optimization_level = 'basic'
                    logger.info("基础性能优化器已启用")

                def optimize(self, *args, **kwargs):
                    """基础优化方法"""
                    return {'status': 'optimized', 'level': 'basic'}

                def get_stats(self):
                    """获取优化统计"""
                    return {'optimizations': 0, 'level': 'basic'}

            self.performance_optimizer = BasicPerformanceOptimizer()
            logger.info("基础性能优化器创建成功")

        except Exception as e:
            logger.error(f"创建后备优化器失败: {e}")
            self.performance_optimizer = None

    def _init_other_backtest_components(self):
        """初始化其他回测组件"""
        try:
            # 初始化回测引擎
            self.backtest_engine = None

            # 初始化监控器
            self.backtest_monitor = None

            # 初始化验证器
            self.backtest_validator = None

            logger.info("其他回测组件初始化完成")

        except Exception as e:
            logger.warning(f"初始化其他回测组件时发生警告: {e}")

    def _create_minimal_backtest_components(self):
        """创建最小回测组件"""
        try:
            self.performance_optimizer = None
            self.backtest_engine = None
            self.backtest_monitor = None
            self.backtest_validator = None

            logger.info("最小回测组件创建完成")

        except Exception as e:
            logger.error(f"创建最小回测组件失败: {e}")

    def start_backtest(self, params: Dict):
        """开始回测"""
        try:
            logger.info("开始启动回测")

            stock_code = params.get('stock_code', '000001')
            period = params.get('period', '1y')

            stock_data = self._get_stock_data(stock_code, period)

            from backtest.unified_backtest_engine import BacktestLevel

            use_vectorized = params.get('use_vectorized_engine', True)
            auto_select = params.get('auto_select_engine', True)

            self.backtest_engine = UnifiedBacktestEngine(
                backtest_level=BacktestLevel.PROFESSIONAL,
                use_vectorized_engine=use_vectorized,
                auto_select_engine=auto_select
            )

            engine_info = f"向量化: {use_vectorized}, 自动选择: {auto_select}"
            logger.info(f"回测引擎创建成功 - {engine_info}")

            try:
                self.monitor = RealTimeBacktestMonitor(
                    monitoring_level=MonitoringLevel.REAL_TIME
                )
            except Exception as e:
                logger.error(f'创建监控器失败: {e}')
                self.monitor = None

            self.current_data = stock_data

            engine_type = "向量化引擎" if params.get('use_vectorized_engine', True) else "标准引擎"
            if params.get('auto_select_engine', True):
                engine_type += " (自动选择)"

            self.alerts_panel.update_performance_metrics(
                engine_type=engine_type,
                data_size=len(stock_data)
            )

            self.start_monitoring(stock_data, params)

            self.alerts_panel.add_alert('info', f'回测已启动，使用{engine_type}，数据: {stock_code}')

        except Exception as e:
            logger.error(f"启动回测失败: {e}")
            self.error_occurred.emit(f"启动回测失败: {str(e)}")
            self.control_panel.on_stop_backtest()

    def _get_stock_service(self):
        """获取股票服务"""
        try:
            from core.services.stock_service import StockService
            
            if hasattr(self, 'service_container') and self.service_container:
                return self.service_container.resolve(StockService)
            else:
                # 通过全局服务容器获取
                try:
                    from core.containers import get_service_container
                    container = get_service_container()
                    return container.resolve(StockService)
                except Exception as e:
                    logger.warning(f"无法从服务容器获取StockService: {e}")
                    return None
        except Exception as e:
            logger.error(f"获取StockService失败: {e}")
            return None

    def _get_stock_data(self, stock_code: str, period: str) -> pd.DataFrame:
        """从系统框架获取真实股票数据"""
        try:
            stock_service = self._get_stock_service()
            
            if stock_service is None:
                raise RuntimeError("无法获取StockService实例")
            
            period_map = {
                "1w": 7, "2w": 14, "1m": 30, "3m": 90,
                "6m": 180, "1y": 365, "2y": 730, "5y": 1825
            }
            days = period_map.get(period, 365)
            
            kdata = stock_service.get_kdata(stock_code, period='D', count=days)
            
            if kdata is None or kdata.empty:
                raise RuntimeError(f"无法获取股票 {stock_code} 的K线数据，数据为空")
            
            close_col = 'close' if 'close' in kdata.columns else ('收盘' if '收盘' in kdata.columns else None)
            if close_col is None:
                raise RuntimeError(f"股票数据缺少价格列")
            
            price_data = kdata[close_col].copy()
            if hasattr(price_data, 'fillna'):
                price_data = price_data.fillna(method='ffill').fillna(method='bfill')
            
            kdata = kdata.copy()
            kdata['close'] = price_data
            kdata['signal'] = 0
            
            logger.info(f"成功获取股票数据: {stock_code}, {len(kdata)}条记录")
            return kdata
            
        except ImportError as e:
            raise RuntimeError(f"StockService模块导入失败: {e}")
        except Exception as e:
            raise RuntimeError(f"获取股票数据失败: {str(e)}")

    def stop_backtest(self):
        """停止回测"""
        try:
            logger.info("正在停止回测...")
            self.is_monitoring = False

            if self.monitoring_thread and self.monitoring_thread.is_alive():
                logger.info(f"等待监控线程结束 - 线程ID: {self.monitoring_thread.ident}")

                # 给线程更多时间优雅退出
                self.monitoring_thread.join(timeout=10.0)

                if self.monitoring_thread.is_alive():
                    logger.warning(f"监控线程未能在10秒内结束 - 线程ID: {self.monitoring_thread.ident}")
                else:
                    logger.info("监控线程已正常结束")

            # 清理线程引用
            self.monitoring_thread = None

            # 性能监控已移至性能监控中心

            self.control_panel.on_stop_backtest()
            self.alerts_panel.add_alert('info', '回测已停止')

            logger.info("回测已停止")

        except Exception as e:
            logger.error(f"停止回测失败: {e}")

    def start_monitoring(self, data: pd.DataFrame, params: Dict):
        """启动监控"""
        # 停止之前的监控（如果有的话）
        if self.is_monitoring:
            self.stop_backtest()

        # 创建真实的回测监控器（不使用资源管理器）
        from backtest.real_time_backtest_monitor import RealTimeBacktestMonitor, MonitoringLevel
        from backtest.unified_backtest_engine import UnifiedBacktestEngine
        
        def monitoring_loop():
            """真实的回测监控循环"""
            thread_name = threading.current_thread().name
            logger.info(f"真实回测监控循环开始 - 线程: {thread_name}")
            
            try:
                # 获取当前回测数据
                if hasattr(self, 'current_data') and self.current_data is not None:
                    data = self.current_data
                else:
                    raise RuntimeError("无法获取回测数据，请先启动回测")
                
                # 创建真实回测引擎
                from backtest.unified_backtest_engine import BacktestLevel
                backtest_engine = UnifiedBacktestEngine(
                    backtest_level=BacktestLevel.PROFESSIONAL,
                    use_vectorized_engine=True,
                    auto_select_engine=True
                )
                
                # 创建真实监控器
                monitor = RealTimeBacktestMonitor(monitoring_level=MonitoringLevel.REAL_TIME)
                
                # 启动监控
                monitor.start_monitoring(
                    backtest_engine=backtest_engine,
                    data=data,
                    initial_capital=100000,
                    engine_type="unified"
                )
                
                # 监控循环：等待监控器数据并更新UI
                iteration = 0
                while self.is_monitoring:
                    try:
                        # 检查停止信号
                        if not self.is_monitoring:
                            logger.info(f"收到停止信号，退出监控循环 - 线程: {thread_name}")
                            break
                        
                        # 等待监控数据
                        time.sleep(0.5)  # 500ms间隔
                        
                        # 从监控器获取最新指标数据
                        if hasattr(monitor, 'get_latest_metrics'):
                            latest_metrics = monitor.get_latest_metrics()
                            if latest_metrics:
                                # 转换为UI友好的格式
                                ui_data = {
                                    'timestamp': latest_metrics.timestamp,
                                    'current_return': latest_metrics.current_return,
                                    'cumulative_return': latest_metrics.cumulative_return,
                                    'current_drawdown': latest_metrics.current_drawdown,
                                    'max_drawdown': latest_metrics.max_drawdown,
                                    'sharpe_ratio': latest_metrics.sharpe_ratio,
                                    'volatility': latest_metrics.volatility,
                                    'var_95': latest_metrics.var_95,
                                    'total_return': latest_metrics.cumulative_return,
                                    'annualized_return': latest_metrics.cumulative_return * 252,
                                    'win_rate': latest_metrics.win_rate,
                                    'profit_factor': latest_metrics.profit_factor,
                                    'execution_time': latest_metrics.execution_time
                                }
                                
                                # 安全的UI更新（使用信号槽机制）
                                self._safe_update_ui(ui_data)
                                
                                # 存储监控数据（线程安全）
                                with self.monitoring_data_lock:
                                    self.monitoring_data.append(ui_data)
                                    
                                    # 限制数据长度
                                    if len(self.monitoring_data) > 1000:
                                        self.monitoring_data = self.monitoring_data[-1000:]
                        
                        iteration += 1
                        
                        # 检查预警
                        if hasattr(monitor, 'get_latest_alerts') and monitor.alerts_history:
                            latest_alerts = monitor.get_latest_alerts()
                            if latest_alerts:
                                for alert in latest_alerts:
                                    QTimer.singleShot(0, lambda a=alert: self._safe_add_alert(a))
                        
                    except Exception as e:
                        logger.error(f"监控循环处理异常: {e}")
                        # 继续运行，不要因为单个错误而退出
                        time.sleep(1.0)
                        continue
                        
            except Exception as e:
                logger.error(f"监控线程异常: {e}")
            finally:
                # 停止监控器
                try:
                    if 'monitor' in locals():
                        monitor.stop_monitoring()
                except Exception as e:
                    logger.error(f"停止监控器失败: {e}")
                
                logger.info(f"监控循环结束 - 线程: {thread_name}")
                self.is_monitoring = False

        # 启动监控线程（非守护线程，确保可以正确停止）
        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(
            target=monitoring_loop,
            daemon=False,
            name=f"BacktestWidget-Monitor-{threading.get_ident()}")
        self.monitoring_thread.start()

        # 性能监控已移至性能监控中心

        logger.info(f"监控线程已启动 - 线程ID: {self.monitoring_thread.ident}")

    def _get_monitoring_data(self, monitor, iteration: int) -> Dict:
        """从真实监控系统获取监控数据"""
        try:
            if hasattr(monitor, 'get_latest_metrics') and monitor.get_latest_metrics() is not None:
                latest_metrics = monitor.get_latest_metrics()
                return {
                    'timestamp': latest_metrics.timestamp,
                    'current_return': latest_metrics.current_return,
                    'cumulative_return': latest_metrics.cumulative_return,
                    'current_drawdown': latest_metrics.current_drawdown,
                    'max_drawdown': latest_metrics.max_drawdown,
                    'sharpe_ratio': latest_metrics.sharpe_ratio,
                    'volatility': latest_metrics.volatility,
                    'var_95': latest_metrics.var_95,
                    'total_return': latest_metrics.cumulative_return,
                    'annualized_return': latest_metrics.cumulative_return * 252,
                    'win_rate': latest_metrics.win_rate,
                    'profit_factor': latest_metrics.profit_factor,
                    'execution_time': latest_metrics.execution_time
                }
            else:
                raise RuntimeError("监控器尚未产生有效指标数据")
        except Exception as e:
            raise RuntimeError(f"获取监控数据失败: {str(e)}")

    def _check_alerts(self, data: Dict):
        """检查预警"""
        try:
            # 检查回撤预警
            drawdown = data.get('current_drawdown', 0)
            if drawdown > 0.15:
                QTimer.singleShot(0, lambda: self.alerts_panel.add_alert(
                    'critical', f'回撤过大: {drawdown:.2%}'
                ))
            elif drawdown > 0.1:
                QTimer.singleShot(0, lambda: self.alerts_panel.add_alert(
                    'warning', f'回撤警告: {drawdown:.2%}'
                ))

            # 检查Sharpe比率预警
            sharpe = data.get('sharpe_ratio', 0)
            if sharpe < 0:
                QTimer.singleShot(0, lambda: self.alerts_panel.add_alert(
                    'warning', f'Sharpe比率为负: {sharpe:.3f}'
                ))

            # 检查波动率预警
            volatility = data.get('volatility', 0)
            if volatility > 0.3:
                QTimer.singleShot(0, lambda: self.alerts_panel.add_alert(
                    'warning', f'波动率过高: {volatility:.2%}'
                ))

        except Exception as e:
            logger.error(f"检查预警失败: {e}")

    def _safe_update_ui(self, data: Dict):
        """安全的UI更新方法 - 在主线程中执行UI更新"""
        try:
            # 确保在主线程中更新UI
            if threading.current_thread() != threading.main_thread():
                # 如果不在主线程，使用信号槽机制延迟到主线程执行
                QTimer.singleShot(0, lambda: self._update_ui_main_thread(data))
            else:
                # 如果已经在主线程，直接更新
                self._update_ui_main_thread(data)
        except Exception as e:
            logger.error(f"安全UI更新失败: {e}")

    def _update_ui_main_thread(self, data: Dict):
        """在主线程中更新UI的具体实现"""
        try:
            # 更新图表数据
            if hasattr(self, 'chart_widget') and self.chart_widget:
                self.chart_widget.add_data(data)
            
            # 更新指标面板
            if hasattr(self, 'metrics_panel') and self.metrics_panel:
                self.metrics_panel.update_metrics(data)
            
            # 更新关键指标标签
            if hasattr(self, 'total_return_label'):
                total_return = data.get('total_return', 0)
                self.total_return_label.setText(f"{total_return:.2%}")
                
                # 设置颜色
                color = "red" if total_return < 0 else "green"
                self.total_return_label.setStyleSheet(f"color: {color};")
            
            if hasattr(self, 'sharpe_ratio_label'):
                sharpe = data.get('sharpe_ratio', 0)
                self.sharpe_ratio_label.setText(f"{sharpe:.3f}")
                
                # 设置颜色
                color = "red" if sharpe < 0 else "green"
                self.sharpe_ratio_label.setStyleSheet(f"color: {color};")
            
            if hasattr(self, 'max_drawdown_label'):
                max_dd = data.get('max_drawdown', 0)
                self.max_drawdown_label.setText(f"{max_dd:.2%}")
                self.max_drawdown_label.setStyleSheet("color: red;")
            
            if hasattr(self, 'win_rate_label'):
                win_rate = data.get('win_rate', 0)
                self.win_rate_label.setText(f"{win_rate:.2%}")
                
                # 设置颜色
                color = "red" if win_rate < 0.5 else "green"
                self.win_rate_label.setStyleSheet(f"color: {color};")
            
            if hasattr(self, 'profit_factor_label'):
                pf = data.get('profit_factor', 0)
                self.profit_factor_label.setText(f"{pf:.3f}")
                
                # 设置颜色
                color = "red" if pf < 1.0 else "green"
                self.profit_factor_label.setStyleSheet(f"color: {color};")
                
        except Exception as e:
            logger.error(f"主线程UI更新失败: {e}")

    def _safe_add_alert(self, alert_data):
        """安全的添加预警方法 - 在主线程中执行"""
        try:
            # 确保在主线程中更新UI
            if threading.current_thread() != threading.main_thread():
                # 如果不在主线程，使用信号槽机制延迟到主线程执行
                QTimer.singleShot(0, lambda: self._add_alert_main_thread(alert_data))
            else:
                # 如果已经在主线程，直接添加
                self._add_alert_main_thread(alert_data)
        except Exception as e:
            logger.error(f"安全添加预警失败: {e}")

    def _add_alert_main_thread(self, alert_data):
        """在主线程中添加预警的具体实现"""
        try:
            if hasattr(self, 'alerts_panel') and self.alerts_panel:
                # 处理不同格式的预警数据
                if isinstance(alert_data, dict):
                    level = alert_data.get('level', 'info')
                    message = alert_data.get('message', str(alert_data))
                else:
                    # 如果不是字典格式，直接作为消息处理
                    level = 'info'
                    message = str(alert_data)
                
                self.alerts_panel.add_alert(level, message)
            else:
                logger.warning("预警面板不可用")
                
        except Exception as e:
            logger.error(f"主线程添加预警失败: {e}")

    def set_kdata(self, kdata):
        """设置K线数据"""
        try:
            if kdata is not None and not kdata.empty:
                logger.info("接收到K线数据，准备回测")
                # 这里可以使用真实的K线数据进行回测

        except Exception as e:
            logger.error(f"设置K线数据失败: {e}")

    def refresh_data(self):
        """刷新数据"""
        try:
            if self.is_monitoring:
                logger.info("刷新监控数据")

        except Exception as e:
            logger.error(f"刷新数据失败: {e}")

    def clear_data(self):
        """清除数据"""
        try:
            with self.monitoring_data_lock:
                self.monitoring_data.clear()
            self.alerts_panel.clear_alerts()
            self.chart_widget.clear_data()

            logger.info("数据已清除")

        except Exception as e:
            logger.error(f"清除数据失败: {e}")

# 便捷函数


def create_backtest_widget(config_manager: Optional[ConfigManager] = None) -> ProfessionalBacktestWidget:
    """创建回测组件实例"""
    return ProfessionalBacktestWidget(config_manager)


# 测试代码
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("FactorWeave-Quant Professional Backtest System")
    window.setGeometry(100, 100, 1400, 800)

    # 创建回测组件
    backtest_widget = create_backtest_widget()
    window.setCentralWidget(backtest_widget)

    # 显示窗口
    window.show()

    sys.exit(app.exec_())
