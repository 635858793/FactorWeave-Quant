from loguru import logger
from core.trading.trading_mode import TradingMode, ModeContext
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
    
    # 新增信号：图表展示完成
    chart_display_completed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)  # parent 可以为 None，由 layout 系统管理
        # parent_widget 会在外部设置，用于访问其他面板
        self.parent_widget = None
        self.pending_data = []  # 待显示的完整数据集（用于渐进式加载）
        self.displayed_count = 0  # 已显示的数据点数量
        self.animation_timer = QTimer()  # 动画定时器
        self.animation_timer.timeout.connect(self._incremental_update)
        
        # 模式选择器
        self.mode_label = QLabel("交易模式:")
        self.mode_selector = QComboBox()
        self.mode_selector.addItems(['回测模式', '实盘模式', '混合模式'])
        self.mode_selector.setToolTip("选择回测/实盘/混合模式")
        self.mode_selector.currentTextChanged.connect(self.on_mode_changed)
        self.current_mode = TradingMode.BACKTEST  # 默认回测模式
        
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


    def set_chart_type(self, chart_type: str):
        """设置图表类型"""
        if UNIFIED_CHART_AVAILABLE and hasattr(self, 'chart_widget'):
            self.chart_widget.set_chart_type(chart_type)

    def apply_theme(self, theme: str):
        """应用主题"""
        if UNIFIED_CHART_AVAILABLE and hasattr(self, 'chart_widget'):
            self.chart_widget.apply_theme(theme)

    def on_mode_changed(self, mode_text: str):
        """处理模式切换"""
        mode_map = {
            '回测模式': TradingMode.BACKTEST,
            '实盘模式': TradingMode.LIVE,
            '混合模式': getattr(TradingMode, 'HYBRID', TradingMode.BACKTEST)
        }
        self.current_mode = mode_map.get(mode_text, TradingMode.BACKTEST)
        logger.info(f"切换交易模式：{mode_text} -> {self.current_mode.value}")

    def start_progressive_display(self, data_points: List[Dict], batch_size: int = 10, interval_ms: int = 50):
        """启动渐进式动态展示"""
        try:
            # 停止之前的动画
            self.animation_timer.stop()
            
            # 清空旧数据
            self.pending_data = data_points[:]
            self.displayed_count = 0
            
            # 检查 data_points
            logger.info(f"start_progressive_display: 接收 {len(data_points)} 个数据点")
            if data_points and len(data_points) > 0:
                logger.info(f"前 3 个数据点：capital={[dp['capital'] for dp in data_points[:3]]}, "
                           f"cumulative_return={[dp['cumulative_return'] for dp in data_points[:3]]}, "
                           f"current_drawdown={[dp['current_drawdown'] for dp in data_points[:3]]}")
            
            # 清空图表
            if hasattr(self.chart_widget, 'clear_data'):
                self.chart_widget.clear_data()
            
            # 设置每批大小和间隔
            self._batch_size = batch_size
            self._interval_ms = interval_ms
            
            # 启动动画定时器
            self.animation_timer.start(interval_ms)
            
            logger.info(f"启动渐进式展示：共{len(data_points)}个点，每批{batch_size}个，间隔{interval_ms}ms")
            
        except Exception as e:
            logger.error(f"启动渐进式展示失败：{e}")

    def _incremental_update(self):
        """增量更新图表（用于渐进式展示）"""
        try:
            if self.displayed_count >= len(self.pending_data):
                # 所有数据已显示完毕，停止定时器
                self.animation_timer.stop()
                logger.info("渐进式展示完成")
                # ✅ 发射图表展示完成信号
                self.chart_display_completed.emit()
                return
            
            # 计算本批次的结束位置
            end_index = min(self.displayed_count + self._batch_size, len(self.pending_data))
            
            # 获取本批次数据
            batch = self.pending_data[self.displayed_count:end_index]
            
            # 添加到图表
            if hasattr(self.chart_widget, '_backtest_metrics'):
                self.chart_widget._backtest_metrics.extend(batch)
            else:
                self.chart_widget._backtest_metrics = batch
            
            # 更新已显示计数
            self.displayed_count = end_index
            
            # 绘制当前状态
            if hasattr(self.chart_widget, '_draw_backtest_charts'):
                self.chart_widget._draw_backtest_charts()
            
            logger.debug(f"已显示 {self.displayed_count}/{len(self.pending_data)} 个数据点")
            
        except Exception as e:
            logger.error(f"增量更新失败：{e}")


class MetricsPanel(QWidget):
    """指标面板"""

    def __init__(self, parent=None):
        super().__init__(parent)  # parent 可以为 None，由 layout 系统管理
        # parent_widget 会在外部设置，用于访问其他面板
        self.parent_widget = None
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

        # 设置专业表格样式（深蓝科技风格）
        self.metrics_table.setStyleSheet("""
            QTableWidget {
                background: rgba(30, 41, 59, 128);
                border: 1px solid #374151;
                border-radius: 8px;
                gridline-color: #374151;
                font-size: 11px;
                font-family: 'Consolas', 'Monaco', monospace;
                selection-background-color: #1e40af;
                color: #e2e8f0;
            }
            QTableWidget::item {
                padding: 8px 10px;
                border: 1px solid #374151;
                text-align: center;
                min-height: 22px;
            }
            QTableWidget::item:hover {
                background-color: rgba(59, 130, 246, 0.15);
                border: 1px solid #3b82f6;
            }
            QTableWidget::item:selected {
                background-color: rgba(59, 130, 246, 0.25);
                color: #ffffff;
                font-weight: 600;
            }
            QHeaderView::section {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1e40af, stop:1 #0891b2);
                color: #dbeafe;
                padding: 10px;
                border: 1px solid #374151;
                font-weight: 700;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            QHeaderView::section:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1e3a8a, stop:1 #0e7490);
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
            def _fmt(key, fmt_str):
                if key not in metrics:
                    return "--"
                return fmt_str.format(metrics[key])

            def _fmt_pct(key):
                return _fmt(key, "{:.2%}")

            def _fmt_f3(key):
                return _fmt(key, "{:.3f}")

            def _fmt_f2(key):
                return _fmt(key, "{:.2f}")

            def _fmt_f0(key):
                return _fmt(key, "{:.0f}")

            total_return = metrics.get('total_return', 0)
            annualized_return = metrics.get('annualized_return', 0)
            sharpe_ratio = metrics.get('sharpe_ratio', 0)
            max_drawdown = metrics.get('max_drawdown', 0)
            win_rate = metrics.get('win_rate', 0)

            table_data = [
                [_fmt_pct('total_return'), _fmt_pct('annualized_return'), _fmt_f3('sharpe_ratio'),
                 _fmt_pct('max_drawdown'), _fmt_pct('win_rate')],
                [f"VaR: {_fmt_pct('var_95')}", f"β: {_fmt_f3('beta')}", f"偏度: {_fmt_f2('skew')}",
                 f"峰度: {_fmt_f2('kurtosis')}", f"波动率: {_fmt_pct('volatility')}"],
                [f"交易: {_fmt_f0('trade_count')}次", f"盈亏比: {_fmt_f2('profit_loss_ratio')}", f"期望: {_fmt_pct('expectancy')}",
                 f"连胜: {_fmt_f0('max_consecutive_wins')}次", f"持仓: {_fmt_f0('avg_holding_period')}天"],
                [f"换手: {_fmt_pct('turnover_rate')}", f"α: {_fmt_f3('alpha')}", f"Sortino: {_fmt_f3('sortino_ratio')}",
                 f"盈利因子: {_fmt_f2('profit_factor')}", f"期望收益: {_fmt_pct('annualized_return')}"]
            ]

            for row in range(4):
                for col in range(5):
                    item = self.metrics_table.item(row, col)
                    if item:
                        item.setText(table_data[row][col])

                        if row == 0:
                            if col == 0:
                                color = "#10b981" if total_return >= 0 else "#ef4444"
                            elif col == 1:
                                color = "#10b981" if annualized_return >= 0 else "#ef4444"
                            elif col == 2:
                                color = "#10b981" if sharpe_ratio >= 1.0 else "#f59e0b" if sharpe_ratio >= 0.5 else "#ef4444"
                            elif col == 3:
                                color = "#10b981" if max_drawdown <= 0.1 else "#f59e0b" if max_drawdown <= 0.2 else "#ef4444"
                            else:
                                color = "#10b981" if win_rate >= 0.6 else "#f59e0b" if win_rate >= 0.5 else "#ef4444"

                            item.setForeground(QColor(color))
                            font = item.font()
                            font.setBold(True)
                            font.setPointSize(11)
                            item.setFont(font)

                        elif row == 1:
                            item.setForeground(QColor("#fbbf24"))
                            font = item.font()
                            font.setPointSize(10)
                            item.setFont(font)

                        elif row == 2:
                            item.setForeground(QColor("#34d399"))
                            font = item.font()
                            font.setPointSize(10)
                            item.setFont(font)

                        else:
                            item.setForeground(QColor("#a0aec0"))
                            font = item.font()
                            font.setPointSize(9)
                            item.setFont(font)

        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                logger.warning(f"Qt控件已销毁，取消更新指标: {e}")
            else:
                raise
        except Exception as e:
            logger.error(f"更新指标表格失败: {e}")


class ControlPanel(QWidget):
    """控制面板"""

    # 定义信号
    start_backtest = pyqtSignal(dict)
    stop_backtest = pyqtSignal()

    # 类变量：状态标签样式（所有实例共享）
    STATUS_STYLES = {
        'ready': """
            QLabel {
                color: #10b981;
                font-weight: 600;
                padding: 12px;
                border: 1px solid #374151;
                border-radius: 6px;
                background-color: rgba(30, 41, 59, 128);
                font-size: 11px;
            }
        """,
        'starting': """
            QLabel {
                color: #3b82f6;
                font-weight: 600;
                padding: 12px;
                border: 1px solid #374151;
                border-radius: 6px;
                background-color: rgba(30, 41, 59, 128);
                font-size: 11px;
            }
        """,
        'running': """
            QLabel {
                color: #f59e0b;
                font-weight: 600;
                padding: 12px;
                border: 1px solid #374151;
                border-radius: 6px;
                background-color: rgba(30, 41, 59, 128);
                font-size: 11px;
            }
        """,
        'completed': """
            QLabel {
                color: #10b981;
                font-weight: 600;
                padding: 12px;
                border: 1px solid #374151;
                border-radius: 6px;
                background-color: rgba(30, 41, 59, 128);
                font-size: 11px;
            }
        """,
        'stopped': """
            QLabel {
                color: #ef4444;
                font-weight: 600;
                padding: 12px;
                border: 1px solid #374151;
                border-radius: 6px;
                background-color: rgba(30, 41, 59, 128);
                font-size: 11px;
            }
        """,
        'error': """
            QLabel {
                color: #ef4444;
                font-weight: 600;
                padding: 12px;
                border: 1px solid #374151;
                border-radius: 6px;
                background-color: rgba(30, 41, 59, 128);
                font-size: 11px;
            }
        """
    }

    # 类变量：按钮样式（所有实例共享）
    START_BUTTON_ENABLED_STYLE = """
        QPushButton {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 #1e40af, stop:1 #0891b2);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: bold;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 #1e3a8a, stop:1 #0e7490);
        }
        QPushButton:pressed {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 #1e293b, stop:1 #155e75);
        }
    """
    START_BUTTON_DISABLED_STYLE = """
        QPushButton {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 #4b5563, stop:1 #6b7280);
            color: #9ca3af;
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: bold;
            font-size: 12px;
        }
    """
    STOP_BUTTON_ENABLED_STYLE = """
        QPushButton {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 #991b1b, stop:1 #b91c1c);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: bold;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 #7f1d1d, stop:1 #991b1b);
        }
        QPushButton:pressed {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 #450a0a, stop:1 #7f1d1d);
        }
    """
    STOP_BUTTON_DISABLED_STYLE = """
        QPushButton {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 #4b5563, stop:1 #6b7280);
            color: #9ca3af;
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: bold;
            font-size: 12px;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)  # parent 可以为 None，由 layout 系统管理
        # parent_widget 会在外部设置，用于访问其他面板
        self.parent_widget = None
        self._is_closing = False  # 关闭状态标志
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("控制面板")
        title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #60a5fa;
                padding: 8px 10px;
                border-bottom: 2px solid #3b82f6;
                margin-bottom: 8px;
                background: rgba(59, 130, 246, 0.1);
                border-radius: 6px;
            }
        """)
        layout.addWidget(title)

        # 参数设置组
        params_group = QGroupBox("回测参数")
        params_group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                font-size: 12px;
                border: 1px solid #374151;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 12px;
                color: #e2e8f0;
                background: rgba(30, 41, 59, 128);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px 0 6px;
                color: #93c5fd;
                font-size: 11px;
                font-weight: 600;
            }
        """)
        params_layout = QFormLayout(params_group)
        
        # 统一输入框样式（深蓝科技风）
        input_style = """
            QSpinBox, QDoubleSpinBox, QComboBox {
                background: rgba(30, 41, 59, 128);
                border: 1px solid #374151;
                border-radius: 4px;
                padding: 4px 8px;
                color: #e2e8f0;
                font-size: 11px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border-color: #3b82f6;
            }
            QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {
                border-color: #64748b;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 8px solid #93c5fd;
                margin-right: 5px;
            }
        """

        # 初始资金
        self.initial_capital = QSpinBox()
        self.initial_capital.setRange(10000, 100000000)
        self.initial_capital.setValue(1000000)
        self.initial_capital.setSuffix("元")
        # 应用输入框样式
        self.initial_capital.setStyleSheet(input_style)
        params_layout.addRow("初始资金:", self.initial_capital)

        # 仓位大小
        self.position_size = QDoubleSpinBox()
        self.position_size.setRange(1, 100)
        self.position_size.setValue(95)
        self.position_size.setSingleStep(1)
        self.position_size.setSuffix("%")
        # 应用输入框样式
        self.position_size.setStyleSheet(input_style)
        params_layout.addRow("仓位大小:", self.position_size)

        # 手续费率（用户输入 0.03 表示 0.03%）
        self.commission_pct = QDoubleSpinBox()
        self.commission_pct.setRange(0.001, 1.0)
        self.commission_pct.setValue(0.03)
        self.commission_pct.setDecimals(2)
        self.commission_pct.setSuffix("%")
        # 应用输入框样式
        self.commission_pct.setStyleSheet(input_style)
        params_layout.addRow("手续费率:", self.commission_pct)

        # 专业级别
        self.professional_level = QComboBox()
        self.professional_level.addItems([
            "RETAIL", "INSTITUTIONAL", "HEDGE_FUND", "INVESTMENT_BANK"
        ])
        self.professional_level.setCurrentText("INVESTMENT_BANK")
        # 应用输入框样式
        self.professional_level.setStyleSheet(input_style)
        params_layout.addRow("专业级别:", self.professional_level)

        # 性能级别
        self.performance_level = QComboBox()
        self.performance_level.addItems([
            "STANDARD", "HIGH", "ULTRA", "EXTREME"
        ])
        self.performance_level.setCurrentText("ULTRA")
        params_layout.addRow("性能级别:", self.performance_level)

        layout.addWidget(params_group)

        # 策略设置组
        strategy_group = QGroupBox("策略设置")
        strategy_group.setStyleSheet(params_group.styleSheet())
        strategy_layout = QFormLayout(strategy_group)

        # 策略选择
        self.strategy_combo = QComboBox()
        self.load_strategies_from_registry()
        self.strategy_combo.setToolTip("选择要使用的交易策略")
        strategy_layout.addRow("策略:", self.strategy_combo)

        # 策略参数表格
        self.params_table = QTableWidget()
        self.params_table.setColumnCount(2)
        self.params_table.setHorizontalHeaderLabels(['参数', '值'])
        self.params_table.setMaximumHeight(120)
        self.params_table.setStyleSheet("""
            QTableWidget {
                background: rgba(30, 35, 45, 0.8);
                border: 1px solid #4a5568;
                border-radius: 4px;
                gridline-color: #4a5568;
                font-size: 10px;
            }
            QTableWidget::item {
                padding: 4px;
                border: 1px solid #4a5568;
            }
            QHeaderView::section {
                background: rgba(74, 85, 104, 0.8);
                color: #e2e8f0;
                padding: 4px;
                border: 1px solid #4a5568;
                font-size: 9px;
                font-weight: bold;
            }
        """)
        strategy_layout.addRow(self.params_table)

        # 高级参数配置按钮（使用 ParameterEditorWidget）
        advanced_params_btn = QPushButton("📝 高级参数配置")
        advanced_params_btn.setStyleSheet("""
            QPushButton {
                background: linear-gradient(45deg, #8b5cf6, #7c3aed);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background: linear-gradient(45deg, #7c3aed, #6d28d9);
            }
            QPushButton:pressed {
                background: linear-gradient(45deg, #6d28d9, #5b21b6);
            }
        """)
        advanced_params_btn.setToolTip("打开可视化参数编辑器，支持参数扫描、预设管理和智能推荐")
        advanced_params_btn.clicked.connect(
            lambda: self.parent_widget._open_advanced_parameter_editor()
        )
        strategy_layout.addRow(advanced_params_btn)

        # 策略预览按钮
        preview_button = QPushButton("策略预览")
        preview_button.setStyleSheet("""
            QPushButton {
                background: linear-gradient(45deg, #3b82f6, #1d4ed8);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background: linear-gradient(45deg, #2563eb, #1e40af);
            }
            QPushButton:pressed {
                background: linear-gradient(45deg, #1d4ed8, #1e3a8a);
            }
        """)
        preview_button.clicked.connect(self._preview_strategy)
        strategy_layout.addRow(preview_button)

        layout.addWidget(strategy_group)

        # 股票选择组
        stock_group = QGroupBox("股票选择")
        stock_group.setStyleSheet(params_group.styleSheet())
        stock_layout = QFormLayout(stock_group)

        # 股票代码输入
        self.stock_code_input = QLineEdit()
        self.stock_code_input.setText('000001')
        self.stock_code_input.setPlaceholderText("请输入股票代码，如 000001")
        self.stock_code_input.setToolTip("输入要回测的股票代码")
        stock_layout.addRow("股票代码:", self.stock_code_input)

        layout.addWidget(stock_group)

        # 时间范围设置组
        time_group = QGroupBox("时间范围设置")
        time_group.setStyleSheet(params_group.styleSheet())
        time_layout = QFormLayout(time_group)

        # 开始日期
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addYears(-1))
        self.start_date.setCalendarPopup(True)
        # 应用输入框样式
        self.start_date.setStyleSheet(input_style)
        time_layout.addRow("开始日期:", self.start_date)

        # 结束日期
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        # 应用输入框样式
        self.end_date.setStyleSheet(input_style)
        time_layout.addRow("结束日期:", self.end_date)

        # 数据频率
        from core.plugin_types import Period
        self.data_frequency = QComboBox()
        self.data_frequency.addItems(Period.all_periods())
        self.data_frequency.setCurrentText("日线")
        # 应用输入框样式
        self.data_frequency.setStyleSheet(input_style)
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
        # 应用输入框样式
        self.engine_type.setStyleSheet(input_style)
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

        # 成交模型选择
        self.execution_model = QComboBox()
        self.execution_model.addItems([
            "固定滑点(默认)", "VWAP模型", "随机价格模型"
        ])
        self.execution_model.setCurrentText("固定滑点(默认)")
        self.execution_model.setToolTip("固定滑点(默认)：按固定比例计算滑点\nVWAP模型：成交量加权平均价格模型，更真实\n随机价格模型：模拟价格随机波动")
        engine_layout.addRow("成交模型:", self.execution_model)

        layout.addWidget(params_group)
        layout.addWidget(time_group)  # 添加时间范围设置组
        layout.addWidget(benchmark_group)  # 添加基准对比设置组
        layout.addWidget(engine_group)

        # 控制按钮
        buttons_layout = QHBoxLayout()

        self.start_button = QPushButton("▶ 开始回测 (Ctrl+Enter)")
        self.start_button.setMinimumHeight(40)
        self.start_button.setFont(QFont("Segoe UI", 11, QFont.Bold))
        # 使用类变量样式
        self.start_button.setStyleSheet(self.START_BUTTON_ENABLED_STYLE)
        self.start_button.clicked.connect(self.on_start_backtest)
        self.start_button.setToolTip("开始执行回测 (Ctrl+Enter)")

        self.stop_button = QPushButton("⏹ 停止回测 (Ctrl+Esc)")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setFont(QFont("Segoe UI", 11, QFont.Bold))
        # 使用类变量样式
        self.stop_button.setStyleSheet(self.STOP_BUTTON_ENABLED_STYLE)
        self.stop_button.clicked.connect(self.stop_backtest.emit)
        self.stop_button.setEnabled(False)
        self.stop_button.setToolTip("停止当前回测 (Ctrl+Esc)")

        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.stop_button)
        # 等宽布局，使按钮宽度一致
        buttons_layout.setStretchFactor(self.start_button, 1)
        buttons_layout.setStretchFactor(self.stop_button, 1)
        layout.addLayout(buttons_layout)

        # 导出按钮
        export_layout = QHBoxLayout()
        export_button = QPushButton("💾 导出结果")
        export_button.setMinimumHeight(40)
        export_button.setFont(QFont("Segoe UI", 11, QFont.Bold))
        export_button.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #047857, stop:1 #059669);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #065f46, stop:1 #047857);
            }
            QPushButton:pressed {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #064e3b, stop:1 #065f46);
            }
        """)
        export_button.clicked.connect(self._export_results)
        export_layout.addWidget(export_button)
        layout.addLayout(export_layout)

        # 高级功能分组
        advanced_group = QGroupBox("高级功能")
        advanced_group.setStyleSheet(params_group.styleSheet())
        advanced_layout = QVBoxLayout(advanced_group)

        # 风险管理按钮
        risk_management_button = QPushButton("🛡️ 风险管理")
        risk_management_button.setMinimumHeight(36)
        risk_management_button.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f59e0b, stop:1 #d97706);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: bold;
                font-size: 11px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #d97706, stop:1 #b45309);
            }
            QPushButton:pressed {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #b45309, stop:1 #92400e);
            }
        """)
        risk_management_button.setToolTip("打开性能监控中心的风险控制标签页")
        risk_management_button.clicked.connect(self._open_risk_management)
        advanced_layout.addWidget(risk_management_button)

        # 参数优化按钮
        parameter_optimization_button = QPushButton("⚙️ 参数优化")
        parameter_optimization_button.setMinimumHeight(36)
        parameter_optimization_button.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #8b5cf6, stop:1 #7c3aed);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: bold;
                font-size: 11px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #7c3aed, stop:1 #6d28d9);
            }
            QPushButton:pressed {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #6d28d9, stop:1 #5b21b6);
            }
        """)
        parameter_optimization_button.setToolTip("打开策略管理器的参数优化视图")
        parameter_optimization_button.clicked.connect(self._open_parameter_optimization)
        advanced_layout.addWidget(parameter_optimization_button)

        # 策略对比按钮
        strategy_comparison_button = QPushButton("📊 策略对比")
        strategy_comparison_button.setMinimumHeight(36)
        strategy_comparison_button.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #06b6d4, stop:1 #0891b2);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: bold;
                font-size: 11px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0891b2, stop:1 #0e7490);
            }
            QPushButton:pressed {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0e7490, stop:1 #155e75);
            }
        """)
        strategy_comparison_button.setToolTip("打开策略管理器的策略对比功能")
        strategy_comparison_button.clicked.connect(self._open_strategy_comparison)
        advanced_layout.addWidget(strategy_comparison_button)

        layout.addWidget(advanced_group)

        # 状态显示
        self.status_label = QLabel("状态: 就绪")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #10b981;
                font-weight: 600;
                padding: 12px;
                border: 1px solid #374151;
                border-radius: 6px;
                background-color: rgba(30, 41, 59, 128);
                font-size: 11px;
            }
        """)
        layout.addWidget(self.status_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #374151;
                border-radius: 6px;
                text-align: center;
                background-color: rgba(30, 41, 59, 128);
                color: #e2e8f0;
                font-size: 11px;
                height: 22px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #059669);
                border-radius: 5px;
            }
        """)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - %v")
        layout.addWidget(self.progress_bar)

        layout.addStretch()

    def closeEvent(self, event):
        """窗口关闭事件处理"""
        try:
            logger.info("ControlPanel 收到关闭事件")
            self._is_closing = True  # 设置关闭标志
            
            # 【新增】断开循环引用
            if hasattr(self, 'parent_widget'):
                self.parent_widget = None
            
            # 【新增】断开信号连接
            try:
                self.start_backtest.disconnect()
                self.stop_backtest.disconnect()
            except Exception as e:
                logger.debug(f"断开回测信号失败: {e}")
            
            super().closeEvent(event)
        except Exception as e:
            logger.error(f"ControlPanel closeEvent 失败：{e}")
            super().closeEvent(event)

    def update_progress(self, progress: int, stage: str, message: str):
        """更新进度"""
        try:
            self.progress_bar.setValue(progress)
            self.progress_bar.setFormat(f"{progress}% - {stage}")

            self.status_label.setText(f"状态: {stage}")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #10b981;
                    font-weight: 600;
                    padding: 12px;
                    border: 1px solid #374151;
                    border-radius: 6px;
                    background-color: rgba(30, 41, 59, 128);
                    font-size: 11px;
                }
            """)

            if self.parent_widget and hasattr(self.parent_widget, 'alerts_panel'):
                try:
                    self.parent_widget.alerts_panel.add_alert('info', f"{stage}: {message}")
                except RuntimeError:
                    pass
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                logger.warning(f"Qt控件已销毁，取消更新进度: {e}")
            else:
                raise
        except Exception as e:
            logger.error(f"更新进度失败: {e}")

    def reset_progress(self):
        """重置进度"""
        try:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("0% - 就绪")
            self.status_label.setText("状态: 就绪")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #10b981;
                    font-weight: 600;
                    padding: 12px;
                    border: 1px solid #374151;
                    border-radius: 6px;
                    background-color: rgba(30, 41, 59, 128);
                    font-size: 11px;
                }
            """)
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                logger.warning(f"Qt控件已销毁，取消重置进度: {e}")
            else:
                raise
        except Exception as e:
            logger.error(f"重置进度失败: {e}")

    def load_strategies_from_registry(self):
        """从策略注册器加载策略列表"""
        try:
            from core.containers import get_service_container
            from core.strategy.strategy_registry import StrategyRegistry

            container = get_service_container()
            if container.is_registered(StrategyRegistry):
                registry = container.resolve(StrategyRegistry)
                strategies = registry.get_all_metadata()
                strategy_names = list(strategies.keys())
                if strategy_names:
                    self.strategy_combo.addItems(strategy_names)
                    self.strategy_combo.setCurrentIndex(0)
                    logger.info(f"从策略注册器加载了 {len(strategy_names)} 个策略")
                else:
                    logger.warning("策略注册器中没有策略，使用默认策略列表")
                    self._load_default_strategies()
            else:
                logger.warning("StrategyRegistry 未注册，使用默认策略列表")
                self._load_default_strategies()
        except Exception as e:
            logger.error(f"从策略注册器加载策略失败: {e}")
            self._load_default_strategies()

    def _load_default_strategies(self):
        """加载默认策略列表"""
        self.strategy_combo.addItems([
            "MA策略", "MACD策略", "RSI策略", "KDJ策略",
            "布林带策略", "形态分析策略"
        ])
        self.strategy_combo.setCurrentIndex(0)

    def _preview_strategy(self):
        """预览策略信号"""
        try:
            strategy_name = self.strategy_combo.currentText()
            logger.info(f"预览策略：{strategy_name}")

            QMessageBox.information(
                self,
                "策略预览",
                f"已选择策略：{strategy_name}\n\n"
                f"策略参数将根据选择的策略自动配置。\n"
                f"点击'开始回测'按钮执行回测。"
            )
        except Exception as e:
            logger.error(f"策略预览失败：{e}")
            QMessageBox.warning(
                self,
                "预览失败",
                f"策略预览失败：{str(e)}"
            )

    def on_start_backtest(self):
        """开始回测"""
        try:
            # 检查是否正在关闭
            if self._is_closing:
                logger.warning("控制面板正在关闭，取消启动回测")
                return
            
            # 检查控件是否有效
            if not hasattr(self, 'start_date') or not hasattr(self, 'end_date'):
                logger.warning("控制面板未完全初始化，取消启动回测")
                return
            
            # 检查控件是否已销毁
            try:
                self.start_date.date()
                self.end_date.date()
            except RuntimeError as e:
                if "wrapped C/C++ object" in str(e) or "has been deleted" in str(e):
                    logger.warning(f"Qt 控件已销毁，取消启动回测：{e}")
                    return
                raise
            
            engine_type_text = self.engine_type.currentText()
            if engine_type_text == "自动选择（推荐）":
                use_vectorized_engine = self.use_vectorized.isChecked()
                auto_select_engine = True
            elif engine_type_text == "向量化引擎":
                use_vectorized_engine = True
                auto_select_engine = False
            else:
                use_vectorized_engine = False
                auto_select_engine = False

            params = {
                'initial_capital': self.initial_capital.value(),
                'position_size': self.position_size.value() / 100,
                'commission_pct': self.commission_pct.value() / 100,
                'professional_level': self.professional_level.currentText(),
                'performance_level': self.performance_level.currentText(),
                'use_vectorized_engine': use_vectorized_engine,
                'auto_select_engine': auto_select_engine,
                'execution_model': self.execution_model.currentText(),
                'strategy': self.strategy_combo.currentText(),
                'stock_code': self.stock_code_input.text().strip() or '000001',
                'start_date': self.start_date.date().toString('yyyy-MM-dd'),
                'end_date': self.end_date.date().toString('yyyy-MM-dd'),
                'period': self.data_frequency.currentText(),
                'benchmark': self.parent_widget.benchmark_index.currentText() if hasattr(self, 'parent_widget') and hasattr(self.parent_widget, 'benchmark_index') else '沪深300',
                'risk_control': {
                    'max_drawdown_limit': self.parent_widget.max_drawdown_limit.value() if hasattr(self, 'parent_widget') and hasattr(self.parent_widget, 'max_drawdown_limit') else 0.20,
                    'stop_loss': self.parent_widget.stop_loss.value() if hasattr(self, 'parent_widget') and hasattr(self.parent_widget, 'stop_loss') else 0.10,
                    'take_profit': self.parent_widget.take_profit.value() if hasattr(self, 'parent_widget') and hasattr(self.parent_widget, 'take_profit') else 0.20,
                    'max_position_size': self.parent_widget.max_position_size.value() if hasattr(self, 'parent_widget') and hasattr(self.parent_widget, 'max_position_size') else 0.10,
                    'max_holding_periods': self.parent_widget.max_holding_periods.value() if hasattr(self, 'parent_widget') and hasattr(self.parent_widget, 'max_holding_periods') else 0
                }
            }

            self.start_backtest.emit(params)
            # 更新按钮状态 - 运行中
            self.start_button.setEnabled(False)
            self.start_button.setStyleSheet(self.START_BUTTON_DISABLED_STYLE)
            self.stop_button.setEnabled(True)
            self.stop_button.setStyleSheet(self.STOP_BUTTON_ENABLED_STYLE)
            self.status_label.setText("状态：运行中")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #f59e0b;
                    font-weight: 600;
                    padding: 12px;
                    border: 1px solid #374151;
                    border-radius: 6px;
                    background-color: rgba(30, 41, 59, 128);
                    font-size: 11px;
                }
            """)
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e) or "has been deleted" in str(e):
                logger.warning(f"Qt控件已销毁，取消启动回测: {e}")
            else:
                raise
        except Exception as e:
            logger.error(f"启动回测失败: {e}")

    def on_stop_backtest(self):
        """停止回测"""
        try:
            # 重置按钮状态 - 已停止
            self.start_button.setEnabled(True)
            self.start_button.setStyleSheet(self.START_BUTTON_ENABLED_STYLE)
            self.stop_button.setEnabled(False)
            self.stop_button.setStyleSheet(self.STOP_BUTTON_DISABLED_STYLE)
            self.status_label.setText("状态: 已停止")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #ef4444;
                    font-weight: 600;
                    padding: 12px;
                    border: 1px solid #374151;
                    border-radius: 6px;
                    background-color: rgba(30, 41, 59, 128);
                    font-size: 11px;
                }
            """)
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                logger.warning(f"Qt 控件已销毁，取消停止操作：{e}")
            else:
                raise

    def on_backtest_finished(self):
        """回测完成后的状态重置"""
        try:
            # 重置按钮状态
            self.start_button.setEnabled(True)
            self.start_button.setStyleSheet(self.START_BUTTON_ENABLED_STYLE)
            self.stop_button.setEnabled(False)
            self.stop_button.setStyleSheet(self.STOP_BUTTON_DISABLED_STYLE)
            
            # 更新状态标签为完成状态（绿色）
            self.status_label.setText("状态：已完成")
            self.status_label.setStyleSheet(self.STATUS_STYLES['completed'])
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                logger.warning(f"Qt 控件已销毁，取消状态重置：{e}")
            else:
                raise

    def _export_results(self):
        """导出回测结果"""
        try:
            # 检查 openpyxl 是否已安装
            try:
                import openpyxl
            except ImportError:
                QMessageBox.critical(
                    self,
                    "缺少依赖",
                    "请安装 openpyxl 库来导出 Excel 文件\n\n"
                    "安装命令: pip install openpyxl"
                )
                return

            # 获取父级 ProfessionalBacktestWidget
            parent_widget = self.parent()
            while parent_widget and not isinstance(parent_widget, ProfessionalBacktestWidget):
                parent_widget = parent_widget.parent()

            if not parent_widget:
                QMessageBox.warning(
                    self,
                    "警告",
                    "无法获取回测组件"
                )
                return

            # 检查是否有回测结果
            if not hasattr(parent_widget, 'current_results') or not parent_widget.current_results:
                QMessageBox.warning(
                    self,
                    "警告",
                    "没有可导出的回测结果\n\n"
                    "请先执行回测"
                )
                return

            # 选择保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出回测结果",
                "",
                "Excel 文件 (*.xlsx);;CSV 文件 (*.csv)"
            )

            if not file_path:
                return

            # 导出结果
            import pandas as pd

            if file_path.endswith('.xlsx'):
                # 导出 Excel
                results_df = pd.json_normalize(parent_widget.current_results)

                # 导出交易记录
                if 'trades' in parent_widget.current_results:
                    trades_df = pd.DataFrame(parent_widget.current_results['trades'])
                else:
                    trades_df = pd.DataFrame()

                # 写入 Excel
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    results_df.to_excel(writer, sheet_name='回测结果', index=False)
                    if not trades_df.empty:
                        trades_df.to_excel(writer, sheet_name='交易记录', index=False)

                logger.info(f"Excel导出成功: {file_path}")

            elif file_path.endswith('.csv'):
                # 导出 CSV
                results_df = pd.json_normalize(parent_widget.current_results)
                results_df.to_csv(file_path, index=False, encoding='utf-8-sig')

                logger.info(f"CSV导出成功: {file_path}")

            QMessageBox.information(
                self,
                "导出成功",
                f"回测结果已导出到:\n{file_path}"
            )

        except Exception as e:
            logger.error(f"导出失败: {e}")
            QMessageBox.critical(
                self,
                "导出失败",
                f"导出回测结果失败: {str(e)}"
            )

    def _open_risk_management(self):
        """打开风险管理功能"""
        try:
            from gui.widgets.modern_performance_widget import show_modern_performance_monitor
            
            parent_widget = self.parent()
            while parent_widget and not hasattr(parent_widget, '_main_window'):
                parent_widget = parent_widget.parent()
            
            main_window = parent_widget._main_window if parent_widget else None
            
            performance_widget = show_modern_performance_monitor(main_window)
            
            if performance_widget is not None:
                performance_widget.setWindowTitle("FactorWeave-Quant 性能监控中心 - Professional Edition")
                performance_widget.tab_widget.setCurrentIndex(3)
                performance_widget.show()
                logger.info("风险管理功能已打开")
            else:
                QMessageBox.warning(self, "错误", "无法打开风险管理功能")
                
        except Exception as e:
            logger.error(f"打开风险管理功能失败: {e}")
            QMessageBox.warning(self, "错误", f"无法打开风险管理功能: {e}")

    def _open_parameter_optimization(self):
        """打开参数优化功能"""
        try:
            from gui.dialogs.strategy_manager_dialog import StrategyManagerDialog
            
            parent_widget = self.parent()
            while parent_widget and not hasattr(parent_widget, '_main_window'):
                parent_widget = parent_widget.parent()
            
            main_window = parent_widget._main_window if parent_widget else None
            
            dialog = StrategyManagerDialog(main_window)
            dialog._switch_view('optimization')
            dialog.show()
            logger.info("参数优化功能已打开")
            
        except Exception as e:
            logger.error(f"打开参数优化功能失败: {e}")
            QMessageBox.warning(self, "错误", f"无法打开参数优化功能: {e}")

    def _open_strategy_comparison(self):
        """打开策略对比功能"""
        try:
            from gui.dialogs.strategy_manager_dialog import StrategyManagerDialog
            
            parent_widget = self.parent()
            while parent_widget and not hasattr(parent_widget, '_main_window'):
                parent_widget = parent_widget.parent()
            
            main_window = parent_widget._main_window if parent_widget else None
            
            dialog = StrategyManagerDialog(main_window)
            dialog._switch_view('library')
            dialog.show()
            logger.info("策略对比功能已打开")
            
        except Exception as e:
            logger.error(f"打开策略对比功能失败: {e}")
            QMessageBox.warning(self, "错误", f"无法打开策略对比功能: {e}")


class AlertsPanel(QWidget):
    """预警面板"""

    def __init__(self, parent=None):
        super().__init__(parent)  # parent 可以为 None，由 layout 系统管理
        # parent_widget 会在外部设置，用于访问其他面板
        self.parent_widget = None
        self.alerts = []
        self.risk_metrics_history = []
        self.max_history_points = 50
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

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

        # 移除性能指标面板

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

    def _init_risk_chart(self):
        """初始化风险指标图表"""
        self.risk_figure.clear()
        
        self.risk_ax = self.risk_figure.add_subplot(111)
        self.risk_ax.set_facecolor('#1e2329')
        self.risk_ax.tick_params(colors='white')
        self.risk_ax.spines['bottom'].set_color('white')
        self.risk_ax.spines['top'].set_color('white')
        self.risk_ax.spines['left'].set_color('white')
        self.risk_ax.spines['right'].set_color('white')
        self.risk_ax.set_xlabel('时间点', color='white')
        self.risk_ax.set_ylabel('指标值', color='white')
        self.risk_ax.set_title('风险指标实时趋势', color='white')
        
        self.risk_canvas.draw()

    def _update_risk_chart(self):
        """更新风险指标图表"""
        try:
            if not self.risk_metrics_history:
                return
            
            self.risk_ax.clear()
            self.risk_ax.set_facecolor('#1e2329')
            self.risk_ax.tick_params(colors='white')
            self.risk_ax.spines['bottom'].set_color('white')
            self.risk_ax.spines['top'].set_color('white')
            self.risk_ax.spines['left'].set_color('white')
            self.risk_ax.spines['right'].set_color('white')
            
            x = range(len(self.risk_metrics_history))
            
            var_values = [m.get('var_95', 0) * 100 for m in self.risk_metrics_history]
            cvar_values = [m.get('cvar_95', 0) * 100 for m in self.risk_metrics_history]
            drawdown_values = [m.get('max_drawdown', 0) * 100 for m in self.risk_metrics_history]
            sharpe_values = [m.get('sharpe_ratio', 0) for m in self.risk_metrics_history]
            
            self.risk_ax.plot(x, var_values, 'r-', label='VaR(95%)', linewidth=2)
            self.risk_ax.plot(x, cvar_values, 'orange', label='CVaR(95%)', linewidth=2)
            self.risk_ax.plot(x, drawdown_values, 'y-', label='最大回撤', linewidth=2)
            
            ax2 = self.risk_ax.twinx()
            ax2.plot(x, sharpe_values, 'g-', label='夏普比率', linewidth=2)
            ax2.tick_params(colors='white')
            ax2.spines['right'].set_color('white')
            ax2.set_ylabel('夏普比率', color='white')
            
            self.risk_ax.set_xlabel('时间点', color='white')
            self.risk_ax.set_ylabel('风险指标 (%)', color='white')
            self.risk_ax.set_title('风险指标实时趋势', color='white')
            
            lines1, labels1 = self.risk_ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            self.risk_ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left', 
                               facecolor='#2d3748', edgecolor='white', labelcolor='white')
            
            self.risk_ax.grid(True, alpha=0.3, color='white')
            
            self.risk_figure.tight_layout()
            self.risk_canvas.draw()
        except RuntimeError:
            pass

    def add_alert(self, level: str, message: str):
        """添加预警"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")

            if level == 'critical':
                icon = ''
                color = '#ef4444'
            elif level == 'warning':
                icon = ''
                color = '#f59e0b'
            else:
                icon = 'ℹ'
                color = '#3b82f6'

            alert_item = QListWidgetItem()
            alert_text = f"{icon} [{timestamp}] {level.upper()}: {message}"
            alert_item.setText(alert_text)
            alert_item.setForeground(QColor(color))

            self.alerts_list.insertItem(0, alert_item)

            if self.alerts_list.count() > 50:
                self.alerts_list.takeItem(self.alerts_list.count() - 1)

            self.alerts.append({
                'timestamp': timestamp,
                'level': level,
                'message': message
            })
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                pass
            else:
                raise

    def clear_alerts(self):
        """清除所有预警"""
        try:
            self.alerts_list.clear()
            self.alerts.clear()
        except RuntimeError:
            pass

    def update_risk_metrics(self, risk_metrics: Dict):
        """更新风险指标显示"""
        try:
            self.risk_metrics_history.append(risk_metrics.copy())
            if len(self.risk_metrics_history) > self.max_history_points:
                self.risk_metrics_history.pop(0)
            
            if not hasattr(self, 'risk_group'):
                self.risk_group = QGroupBox("风险指标")
                risk_layout = QFormLayout(self.risk_group)
                
                self.var_label = QLabel("N/A")
                self.cvar_label = QLabel("N/A")
                self.max_drawdown_label = QLabel("N/A")
                self.volatility_label = QLabel("N/A")
                self.sharpe_label = QLabel("N/A")
                
                risk_layout.addRow("VaR(95%):", self.var_label)
                risk_layout.addRow("CVaR(95%):", self.cvar_label)
                risk_layout.addRow("最大回撤:", self.max_drawdown_label)
                risk_layout.addRow("波动率:", self.volatility_label)
                risk_layout.addRow("夏普比率:", self.sharpe_label)
                
                self.layout().insertWidget(2, self.risk_group)
            
            var_95 = risk_metrics.get('var_95', 0)
            self.var_label.setText(f"{var_95:.2%}")
            self.var_label.setStyleSheet("color: #ef4444; font-weight: bold;")
            
            cvar_95 = risk_metrics.get('cvar_95', 0)
            self.cvar_label.setText(f"{cvar_95:.2%}")
            self.cvar_label.setStyleSheet("color: #ef4444; font-weight: bold;")
            
            max_drawdown = risk_metrics.get('max_drawdown', 0)
            self.max_drawdown_label.setText(f"{max_drawdown:.2%}")
            self.max_drawdown_label.setStyleSheet("color: #f59e0b; font-weight: bold;")
            
            volatility = risk_metrics.get('volatility', 0)
            self.volatility_label.setText(f"{volatility:.2%}")
            self.volatility_label.setStyleSheet("color: #3b82f6; font-weight: bold;")
            
            sharpe_ratio = risk_metrics.get('sharpe_ratio', 0)
            self.sharpe_label.setText(f"{sharpe_ratio:.3f}")
            sharpe_color = "#10b981" if sharpe_ratio > 1.0 else "#f59e0b" if sharpe_ratio > 0 else "#ef4444"
            self.sharpe_label.setStyleSheet(f"color: {sharpe_color}; font-weight: bold;")
            
            if hasattr(self, 'risk_ax') and self.risk_ax is not None:
                self._update_risk_chart()
            
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                pass
            else:
                raise
        except Exception as e:
            logger.error(f"更新风险指标显示失败: {e}")


class ProfessionalBacktestWidget(QWidget):
    """专业级回测 UI 组件"""

    # 定义信号
    backtest_completed = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    request_ui_update = pyqtSignal(dict)  # 用于从工作线程请求 UI 更新
    request_progress_update = pyqtSignal(int, str, str)  # 进度更新信号
    request_alert = pyqtSignal(str, str)  # 预警信号

    def __init__(self, parent=None, config_manager: Optional[ConfigManager] = None):
        super().__init__(parent)
        self.config_manager = config_manager or ConfigManager()
        # 纯 Loguru 架构，移除 log_manager 依赖

        # 回测相关组件（使用实例复用模式）
        self.backtest_engine = None
        self.monitor = None
        self.validator = None
        self.optimizer = None
        
        # 引擎和监控器配置缓存（用于复用）
        self._engine_config = None
        self._monitoring_data = {}  # 存储完整回测结果

        # 监控线程
        self.monitoring_thread = None
        self.is_monitoring = False
        self.monitoring_data = []
        self.monitoring_data_lock = Lock()
        self._is_closing = False
        
        # 异步清理工作线程（用于优雅清理监控线程）
        self._cleanup_worker = None

        # 回测相关变量
        self.current_stock_code = None
        self.current_stock_name = None
        self.current_strategy = None
        self.execution_time = 0.0
        self.current_results = None

        # 缓存相关
        self.stock_data_cache = {}
        self.signal_cache = {}
        self.result_cache = {}
        self.cache_max_size = 100
        self.cache_lock = Lock()

        # 状态锁
        self.state_lock = Lock()

        # 获取 BacktestResultManager
        try:
            from core.containers import get_service_container
            from core.services.backtest_result_manager import BacktestResultManager
            container = get_service_container()
            self.backtest_result_manager = container.resolve(BacktestResultManager)
            logger.info("成功获取BacktestResultManager")
        except Exception as e:
            logger.warning(f"无法获取BacktestResultManager: {e}")
            self.backtest_result_manager = None

        # 初始化风险管理器
        try:
            from core.risk_manager import RiskManager
            from core.risk_metrics import RiskMetricsCalculator
            self.risk_manager = RiskManager()
            self.risk_metrics_calculator = RiskMetricsCalculator()
            logger.info("风险管理器初始化成功")
        except Exception as e:
            logger.warning(f"无法初始化风险管理器: {e}")
            self.risk_manager = None
            self.risk_metrics_calculator = None

        # 风险监控相关变量
        self.risk_metrics = {}
        self.risk_alerts = []
        self.risk_thresholds = {
            'var_95': -0.05,
            'max_drawdown': -0.20,
            'volatility': 0.30,
            'sharpe_ratio': 0.5
        }

        # 初始化 UI
        self.init_ui()

        # 初始化回测组件
        self.init_backtest_components()
        
        # 连接信号到槽（确保在主线程中更新 UI）
        self.request_ui_update.connect(self._on_backtest_completed, Qt.QueuedConnection)
        self.request_progress_update.connect(self._on_progress_update, Qt.QueuedConnection)
        self.request_alert.connect(self._on_alert_request, Qt.QueuedConnection)
        
        # 模式管理
        self.current_mode = TradingMode.BACKTEST  # 默认回测模式

    def on_mode_changed(self, mode_text: str):
        """处理模式切换"""
        mode_map = {
            '回测模式': TradingMode.BACKTEST,
            '实盘模式': TradingMode.LIVE,
            '混合模式': getattr(TradingMode, 'HYBRID', TradingMode.BACKTEST)
        }
        self.current_mode = mode_map.get(mode_text, TradingMode.BACKTEST)
        logger.info(f"ProfessionalBacktestWidget 切换交易模式：{mode_text} -> {self.current_mode.value}")
        
        # 根据模式调整配置
        if self.current_mode == TradingMode.LIVE:
            logger.info("实盘模式：启用严格风控和性能优化")
        elif self.current_mode == TradingMode.BACKTEST:
            logger.info("回测模式：使用完整计算")

    def closeEvent(self, event):
        """窗口关闭事件处理 - 确保正确清理资源"""
        try:
            logger.info("ProfessionalBacktestWidget 收到关闭事件，开始清理...")
            self._is_closing = True

            if hasattr(self, 'control_panel') and self.control_panel:
                self.control_panel.stop_backtest.emit()

            if hasattr(self, 'is_monitoring') and self.is_monitoring:
                # 窗口关闭时使用同步清理（不更新 UI，避免不必要的操作）
                self._cleanup_thread_sync(update_ui=False)

            if hasattr(self, 'chart_widget') and self.chart_widget and hasattr(self.chart_widget, 'animation_timer'):
                self.chart_widget.animation_timer.stop()

            super().closeEvent(event)
            logger.info("ProfessionalBacktestWidget 清理完成")
        except Exception as e:
            logger.error(f"关闭时清理资源失败: {e}")
            super().closeEvent(event)

    def _cleanup_before_close(self):
        """在窗口关闭前清理资源（供外部调用）"""
        try:
            logger.info("ProfessionalBacktestWidget _cleanup_before_close 开始清理...")
            self._is_closing = True

            if hasattr(self, 'control_panel') and self.control_panel:
                self.control_panel.stop_backtest.emit()

            if hasattr(self, 'is_monitoring') and self.is_monitoring:
                # 窗口关闭时使用同步清理（不更新 UI，避免不必要的操作）
                self._cleanup_thread_sync(update_ui=False)

            if hasattr(self, 'chart_widget') and self.chart_widget and hasattr(self.chart_widget, 'animation_timer'):
                self.chart_widget.animation_timer.stop()

            logger.info("ProfessionalBacktestWidget _cleanup_before_close 完成")
        except Exception as e:
            logger.error(f"_cleanup_before_close 失败: {e}")

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

        # 主布局 - 使用QSplitter实现可调节布局
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setHandleWidth(4)
        main_splitter.setStyleSheet("""
            QSplitter::handle {
                background: #2d3748;
            }
            QSplitter::handle:hover {
                background: #4299e1;
            }
            QSplitter::handle:pressed {
                background: #63b3ed;
            }
        """)

        # 左侧控制面板（只保留控制和预警）
        left_panel = QVBoxLayout()
        left_panel.setSpacing(6)
        left_panel.setContentsMargins(4, 4, 4, 4)

        # 控制面板
        self.control_panel = ControlPanel()  # 不设置 parent，让 layout 系统自动管理
        self.control_panel.parent_widget = self  # 保存父组件引用，用于访问其他面板
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
        self.alerts_panel = AlertsPanel()  # 不设置 parent，让 layout 系统自动管理
        self.alerts_panel.parent_widget = self  # 保存父组件引用
        left_panel.addWidget(self.alerts_panel)

        # 左侧面板容器（添加滚动功能）
        left_widget = QWidget()
        left_widget.setLayout(left_panel)

        # 创建滚动区域 - 支持可调节宽度
        left_scroll = QScrollArea()
        left_scroll.setWidget(left_widget)
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setMinimumWidth(280)  # 最小宽度增加到 280px
        left_scroll.setMaximumWidth(800)  # 最大宽度放宽到 800px，允许用户自由调整
        left_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
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

        # 右侧区域（指标 + 图表 + 预警）
        right_layout = QVBoxLayout()
        right_layout.setSpacing(4)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 指标面板（固定高度）
        self.metrics_panel = MetricsPanel()  # 不设置 parent，让 layout 系统自动管理
        self.metrics_panel.parent_widget = self  # 保存父组件引用
        # self.metrics_panel.setMaximumHeight(180)
        # self.metrics_panel.setMinimumHeight(160)
        right_layout.addWidget(self.metrics_panel)

        # 图表区域（占用剩余空间的主要部分）
        self.chart_widget = RealTimeChart()  # 不设置 parent，让 layout 系统自动管理
        self.chart_widget.parent_widget = self  # 保存父组件引用
        self.chart_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chart_widget.setMinimumHeight(400)
        # ✅ 连接图表展示完成信号，在图表展示完成后才切换按钮状态
        self.chart_widget.chart_display_completed.connect(self.on_chart_display_completed)
        right_layout.addWidget(self.chart_widget, 1)  # stretch=1，占用主要空间

        # 右侧容器
        right_widget = QWidget()
        right_widget.setLayout(right_layout)

        # 添加到分割器 - 实现可调节布局
        main_splitter.addWidget(left_scroll)
        main_splitter.addWidget(right_widget)

        # 设置初始比例 (左侧:右侧 = 1:3)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)

        # 设置初始分割位置
        total_width = 1200  # 默认窗口宽度
        main_splitter.setSizes([int(total_width * 0.25), int(total_width * 0.75)])

        # 允许左侧面板折叠
        main_splitter.setCollapsible(0, True)
        main_splitter.setCollapsible(1, False)

        # 添加到主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.addWidget(main_splitter)

        # 保存引用以便响应式调整
        self.main_splitter = main_splitter
        self.left_scroll = left_scroll

    def resizeEvent(self, event):
        """窗口大小变化时自适应调整布局"""
        super().resizeEvent(event)
        self._adjust_layout_on_resize(event)

    def _adjust_layout_on_resize(self, event):
        """根据窗口大小调整布局"""
        try:
            width = event.size().width()
            height = event.size().height()

            if hasattr(self, 'main_splitter'):
                current_sizes = self.main_splitter.sizes()
                total = sum(current_sizes)
                if total > 0:
                    min_left = 280  # 更新为新的最小值
                    max_left = 800  # 更新为新的最大值
                    if width < 1024:
                        new_left = min(int(width * 0.22), min_left)
                    elif width > 1920:
                        new_left = min(int(width * 0.20), max_left)
                    else:
                        new_left = int(width * 0.20)
                    new_left = max(min_left, min(max_left, new_left))
                    new_right = width - new_left - 4
                    self.main_splitter.setSizes([new_left, new_right])
            
            # 调整指标面板高度（使用百分比）
            if hasattr(self, 'metrics_panel') and self.metrics_panel:
                # 根据窗口高度动态调整指标面板高度
                # 小屏幕 25%，中等屏幕 20%，大屏幕 15%
                if height < 768:
                    metrics_height = int(height * 0.25)
                elif height > 1080:
                    metrics_height = int(height * 0.15)
                else:
                    metrics_height = int(height * 0.20)
                
                # 限制在合理范围内
                metrics_height = max(150, min(400, metrics_height))
                
                if hasattr(self.metrics_panel, 'metrics_table'):
                    self.metrics_panel.metrics_table.setMaximumHeight(metrics_height)
                    self.metrics_panel.metrics_table.setMinimumHeight(metrics_height)
        except Exception as e:
            logger.warning(f"调整布局失败: {e}")

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
        from core.plugin_types import Period
        self.data_frequency = QComboBox()
        self.data_frequency.addItems(Period.all_periods())
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
            "无", "沪深300", "上证指数", "深证成指", "创业板", "科创50",
            "上证50", "中证500", "中证1000"
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
        
        # 最大持有期设置
        self.max_holding_periods = QSpinBox()
        self.max_holding_periods.setRange(0, 365)
        self.max_holding_periods.setSingleStep(1)
        self.max_holding_periods.setValue(0)
        self.max_holding_periods.setToolTip("0表示不限制持有期")
        layout.addRow("最大持有期(天):", self.max_holding_periods)

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
            if getattr(self, '_is_closing', False):
                return
            logger.info("开始启动回测")

            # 更新进度
            self.control_panel.update_progress(0, "开始回测", "正在初始化...")

            stock_code = params.get('stock_code', '000001')
            period = params.get('period', '1y')
            strategy_name = params.get('strategy', 'MA策略')

            # 设置当前回测信息
            self.current_stock_code = stock_code
            self.current_stock_name = params.get('stock_name', '未知股票')
            self.current_strategy = strategy_name

            # 记录开始时间
            import time
            self.start_time = time.time()

            # 更新进度
            self.control_panel.update_progress(10, "获取股票数据", f"正在获取 {stock_code} 的数据...")

            stock_data = self._get_stock_data(stock_code, period)

            # 更新进度
            self.control_panel.update_progress(20, "获取股票数据", f"已获取 {len(stock_data)} 条数据")

            # 获取基准指数数据
            benchmark_name = params.get('benchmark', '沪深300')
            benchmark_data = self._get_benchmark_data(benchmark_name, stock_code, period)

            # 将 benchmark_data 添加到 params 中，传递给 start_monitoring
            params['benchmark_data'] = benchmark_data

            # 生成策略信号
            try:
                self.control_panel.update_progress(30, "生成策略信号", f"正在执行 {strategy_name} 策略...")
                signals = self._generate_strategy_signals(stock_data, strategy_name)
                stock_data['signal'] = signals
                logger.info(f"策略信号已添加到数据: {strategy_name}")
                # 更新进度
                self.control_panel.update_progress(40, "生成策略信号", f"已生成信号")
            except Exception as e:
                logger.warning(f"生成策略信号失败，使用默认信号: {e}")
                stock_data['signal'] = 0.0

            from backtest.unified_backtest_engine import BacktestLevel

            use_vectorized = params.get('use_vectorized_engine', True)
            auto_select = params.get('auto_select_engine', True)
            execution_model_text = params.get('execution_model', '固定滑点(默认)')
            execution_model_map = {
                '固定滑点(默认)': 'fixed',
                'VWAP模型': 'vwap',
                '随机价格模型': 'random'
            }
            execution_model = execution_model_map.get(execution_model_text, 'fixed')

            # 保存引擎配置，用于复用
            self._engine_config = {
                'backtest_level': BacktestLevel.PROFESSIONAL,
                'use_vectorized_engine': use_vectorized,
                'auto_select_engine': auto_select,
                'execution_model': execution_model
            }

            # 更新进度
            self.control_panel.update_progress(50, "启动监控", "正在初始化回测引擎...")

            # 使用复用模式获取引擎（避免重复创建）
            self.backtest_engine = self._get_engine(self._engine_config)

            engine_info = f"向量化: {use_vectorized}, 自动选择: {auto_select}, 成交模型: {execution_model}"
            logger.info(f"回测引擎创建/复用成功 - {engine_info}")

            try:
                # 复用监控器（避免重复创建）
                self.monitor = self._get_monitor()
                if self.monitor and hasattr(self.monitor, '_is_running') and self.monitor._is_running:
                    logger.info("复用已有监控器，先停止")
                    self.monitor.stop_monitoring()
                    QTimer.singleShot(100, lambda: self._do_continue_backtest(stock_data, params, stock_code))
                    return
            except Exception as e:
                logger.warning(f'获取监控器失败: {e}，创建新的监控器')
                self.monitor = self._get_monitor()

            self._do_continue_backtest(stock_data, params, stock_code)

        except Exception as e:
            logger.error(f"启动回测失败: {e}")
            self.error_occurred.emit(f"启动回测失败: {str(e)}")
            self.control_panel.on_stop_backtest()
            self.control_panel.reset_progress()

    def _do_continue_backtest(self, stock_data, params, stock_code):
        """异步继续回测启动（在监控器停止后调用）"""
        try:
            self.monitor = self._get_monitor()
            self.current_data = stock_data

            engine_type = "向量化引擎" if params.get('use_vectorized_engine', True) else "标准引擎"
            if params.get('auto_select_engine', True):
                engine_type += " (自动选择)"

            self.start_monitoring(stock_data, params)

            if getattr(self, '_is_closing', False):
                return
            self.alerts_panel.add_alert('info', f'回测已启动，使用{engine_type}，数据: {stock_code}')
        except Exception as e:
            logger.error(f"启动回测失败: {e}")
            self.error_occurred.emit(f"启动回测失败: {str(e)}")
            self.control_panel.on_stop_backtest()
            self.control_panel.reset_progress()

    def _open_advanced_parameter_editor(self):
        """打开高级参数编辑器（ParameterEditorWidget）"""
        try:
            from gui.widgets.parameter_editor import ParameterEditorWidget
            from core.strategy.strategy_engine import get_strategy_engine
            from core.trading.trading_mode import ModeContext, TradingMode
            
            # 获取当前策略
            strategy_name = self.control_panel.strategy_combo.currentText()
            logger.info(f"打开高级参数编辑器：{strategy_name}")
            
            # 创建策略实例
            strategy_engine = get_strategy_engine()
            strategy = strategy_engine.get_strategy_instance(strategy_name)
            
            # 创建 mode_context
            mode_context = ModeContext.create_backtest()
            strategy.set_mode_context(mode_context)
            
            # 创建参数编辑器对话框
            from PyQt5.QtWidgets import QDialog
            dialog = QDialog(self)
            dialog.setWindowTitle(f"高级参数配置 - {strategy_name}")
            dialog.resize(700, 900)
            
            # 创建参数编辑器
            parameter_editor = ParameterEditorWidget(strategy, dialog)
            
            # 传递 kdata（如果有）
            if hasattr(self, 'current_data') and self.current_data is not None:
                parameter_editor.kdata = self.current_data
                logger.info(f"已传递 K 线数据到参数编辑器：{len(self.current_data)} 条")
            
            # 传递 mode_context
            parameter_editor.mode_context = mode_context
            
            # 连接信号
            parameter_editor.parameter_changed.connect(
                lambda name, value: self._on_advanced_parameter_changed(name, value, strategy)
            )
            parameter_editor.parameters_applied.connect(
                lambda: self._on_advanced_parameters_applied(strategy)
            )
            parameter_editor.scan_completed.connect(
                lambda result: self._on_parameter_scan_completed(result)
            )
            parameter_editor.comparison_completed.connect(
                lambda results: self._on_parameter_comparison_completed(results)
            )
            
            # 添加到对话框
            layout = QVBoxLayout(dialog)
            layout.addWidget(parameter_editor)
            
            # 显示对话框
            dialog.exec_()
            
            logger.info("高级参数编辑器已关闭")
            
        except Exception as e:
            logger.error(f"打开高级参数编辑器失败：{e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "错误",
                f"无法打开高级参数编辑器：{e}"
            )

    def _on_advanced_parameter_changed(self, name, value, strategy):
        """高级参数变化回调"""
        logger.info(f"高级参数变化：{name} = {value}")

    def _on_advanced_parameters_applied(self, strategy):
        """高级参数应用回调"""
        logger.info(f"高级参数已应用：{strategy.name}")

    def _on_parameter_scan_completed(self, result):
        """参数扫描完成回调"""
        logger.info(f"参数扫描完成：{len(result)} 个结果")

    def _on_parameter_comparison_completed(self, results):
        """参数对比完成回调"""
        logger.info(f"参数对比完成：{len(results)} 个结果")

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

    def _get_engine(self, config: Dict = None) -> 'UnifiedBacktestEngine':
        """获取或创建回测引擎（复用模式）"""
        from backtest.unified_backtest_engine import UnifiedBacktestEngine, BacktestLevel
        
        if self.backtest_engine is not None and config is not None:
            if self._engine_config == config:
                logger.info("复用已有回测引擎实例")
                return self.backtest_engine
        
        if config is None:
            config = self._engine_config or {
                'backtest_level': BacktestLevel.PROFESSIONAL,
                'use_vectorized_engine': True,
                'auto_select_engine': True,
                'execution_model': 'fixed'
            }
        
        backtest_level = config.get('backtest_level')
        if backtest_level is None:
            backtest_level = BacktestLevel.PROFESSIONAL
        
        use_vectorized = config.get('use_vectorized_engine', True)
        auto_select = config.get('auto_select_engine', True)
        execution_model = config.get('execution_model', 'fixed')
        
        self.backtest_engine = UnifiedBacktestEngine(
            backtest_level=backtest_level,
            use_vectorized_engine=use_vectorized,
            auto_select_engine=auto_select,
            execution_model=execution_model
        )
        self._engine_config = config
        logger.info(f"创建新的回测引擎实例")
        return self.backtest_engine

    def _get_monitor(self, force_new: bool = False) -> 'RealTimeBacktestMonitor':
        """获取或创建监控器（复用模式）"""
        from backtest.real_time_backtest_monitor import RealTimeBacktestMonitor, MonitoringLevel
        
        # 强制创建新实例或没有旧实例
        if force_new or self.monitor is None:
            self.monitor = RealTimeBacktestMonitor(monitoring_level=MonitoringLevel.REAL_TIME)
            logger.info("创建新的监控器实例")
            return self.monitor
        
        # 检查旧实例状态
        if hasattr(self.monitor, 'is_monitoring') and self.monitor.is_monitoring:
            logger.info("监控器正在运行，停止并重新创建")
            self.monitor.stop_monitoring()
            # 不等待，直接创建新实例（消除硬编码延迟）
            self.monitor = RealTimeBacktestMonitor(monitoring_level=MonitoringLevel.REAL_TIME)
            logger.info("已创建新监控器实例")
        else:
            logger.info("复用已有监控器实例")
        
        return self.monitor

    BENCHMARK_MAPPING = {
        '沪深300': '000300',
        '上证指数': '000001',
        '深证成指': '399001',
        '创业板': '399006',
        '科创50': '000688',
        '上证50': '000016',
        '中证500': '000905',
        '中证1000': '000852',
    }

    def _get_benchmark_data(self, benchmark_name: str, stock_code: str, period: str) -> Optional[pd.DataFrame]:
        """获取基准指数数据"""
        try:
            if not benchmark_name or benchmark_name == '无':
                logger.info("未选择基准指数，跳过")
                return None

            benchmark_code = self.BENCHMARK_MAPPING.get(benchmark_name)
            if not benchmark_code:
                logger.warning(f"未找到基准指数 {benchmark_name} 的代码映射")
                return None

            stock_service = self._get_stock_service()
            if stock_service is None:
                logger.warning("无法获取StockService实例，无法获取基准数据")
                return None

            period_ui_to_internal = {
                '分时': 'tick', '5分钟': '5m', '15分钟': '15m', '30分钟': '30m',
                '60分钟': '60m', '日线': '1d', '周线': '1w', '月线': '1M'
            }
            period_internal = period_ui_to_internal.get(period, period)

            period_map = {
                "1w": 7, "2w": 14, "1m": 30, "3m": 90,
                "6m": 180, "1y": 365, "2y": 730, "5y": 1825,
                "1d": 365, "1M": 365, "tick": 1
            }
            days = period_map.get(period_internal, 365)

            period_to_stock_service = {
                'tick': 'tick', '5m': '5m', '15m': '15m', '30m': '30m',
                '60分钟': '60m', '1d': 'D', '1w': 'W', '1M': 'M'
            }
            stock_period = period_to_stock_service.get(period_internal, 'D')
            benchmark_data = stock_service.get_kdata(benchmark_code, period=stock_period, count=days)

            if benchmark_data is None or benchmark_data.empty:
                logger.warning(f"无法获取基准指数 {benchmark_name} ({benchmark_code}) 的数据")
                return None

            close_col = 'close' if 'close' in benchmark_data.columns else ('收盘' if '收盘' in benchmark_data.columns else None)
            if close_col is None:
                logger.warning(f"基准数据缺少价格列")
                return None

            benchmark_data = benchmark_data.copy()
            benchmark_data['close'] = benchmark_data[close_col]

            logger.info(f"成功获取基准指数数据: {benchmark_name} ({benchmark_code}), {len(benchmark_data)}条记录")
            return benchmark_data

        except Exception as e:
            logger.error(f"获取基准指数数据失败: {e}")
            return None

    def _get_stock_data(self, stock_code: str, period: str, timeout: int = 30) -> pd.DataFrame:
        """从系统框架获取真实股票数据（带超时控制）"""
        try:
            # 检查缓存
            cache_key = f"{stock_code}_{period}"
            if cache_key in self.stock_data_cache:
                logger.info(f"使用缓存的股票数据: {cache_key}")
                return self.stock_data_cache[cache_key]

            stock_service = self._get_stock_service()

            if stock_service is None:
                raise RuntimeError("无法获取StockService实例")

            period_ui_to_internal = {
                '分时': 'tick', '5分钟': '5m', '15分钟': '15m', '30分钟': '30m',
                '60分钟': '60m', '日线': '1d', '周线': '1w', '月线': '1M'
            }
            period_internal = period_ui_to_internal.get(period, period)

            period_map = {
                "1w": 7, "2w": 14, "1m": 30, "3m": 90,
                "6m": 180, "1y": 365, "2y": 730, "5y": 1825,
                "1d": 365, "1M": 365, "tick": 1
            }
            days = period_map.get(period_internal, 365)

            period_to_stock_service = {
                'tick': 'tick', '5m': '5m', '15m': '15m', '30m': '30m',
                '60m': '60m', '1d': 'D', '1w': 'W', '1M': 'M'
            }
            stock_period = period_to_stock_service.get(period_internal, 'D')
            
            # 使用线程池实现超时控制
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
            
            def fetch_data():
                return stock_service.get_kdata(stock_code, period=stock_period, count=days)
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(fetch_data)
                try:
                    kdata = future.result(timeout=timeout)  # 超时控制
                except FuturesTimeoutError:
                    logger.error(f"获取股票数据超时（{timeout}秒）：{stock_code}")
                    raise RuntimeError(f"获取股票数据超时，请检查网络连接（超时时间：{timeout}秒）")
                except Exception as e:
                    logger.error(f"获取股票数据失败：{e}")
                    raise

            if kdata is None or kdata.empty:
                raise RuntimeError(f"无法获取股票 {stock_code} 的K线数据，数据为空")

            close_col = 'close' if 'close' in kdata.columns else ('收盘' if '收盘' in kdata.columns else None)
            if close_col is None:
                raise RuntimeError(f"股票数据缺少价格列")

            price_data = kdata[close_col]
            if hasattr(price_data, 'fillna'):
                price_data = price_data.fillna(method='ffill')

            kdata = kdata.copy()
            kdata['close'] = price_data

            # 缓存股票数据
            with self.cache_lock:
                if len(self.stock_data_cache) >= self.cache_max_size:
                    # 清理最旧的缓存
                    oldest_key = next(iter(self.stock_data_cache))
                    del self.stock_data_cache[oldest_key]
                self.stock_data_cache[cache_key] = kdata

            logger.info(f"成功获取股票数据: {stock_code}, {len(kdata)}条记录")
            return kdata

        except Exception as e:
            logger.error(f"获取股票数据失败: {e}")
            logger.info("尝试使用备用数据源...")
            kdata = self._get_fallback_stock_data(stock_code, period)
            if kdata is not None and not kdata.empty:
                logger.info(f"备用数据源成功: {len(kdata)}条记录")
                return kdata
            raise RuntimeError(f"无法获取股票 {stock_code} 的数据，请检查网络连接或稍后重试")

    def _get_fallback_stock_data(self, stock_code: str, period: str) -> pd.DataFrame:
        """从备用数据源获取股票数据"""
        import yfinance as yf

        period_map = {
            "1w": "1mo", "2w": "1mo", "1m": "1mo", "3m": "3mo",
            "6m": "6mo", "1y": "1y", "2y": "2y", "5y": "5y"
        }
        yf_period = period_map.get(period, "1y")

        ticker = yf.Ticker(f"{stock_code}.SS" if stock_code.startswith('6') else f"{stock_code}.SZ")
        data = ticker.history(period=yf_period)

        if data is None or data.empty:
            raise RuntimeError("备用数据源返回空数据")

        data = data.reset_index()
        data = data.rename(columns={
            'Date': 'datetime',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })

        logger.info(f"备用数据源获取成功: {len(data)}条记录")
        return data

    def _generate_strategy_signals(self, kdata: pd.DataFrame, strategy_name: str) -> pd.Series:
        """生成策略信号"""
        try:
            # 确保策略已注册
            try:
                from core.strategy import get_strategy_registry, _register_builtin_strategies
                registry = get_strategy_registry()
                _register_builtin_strategies(registry)
                logger.debug(f"强制注册内置策略完成，当前注册策略: {list(registry._strategies.keys())}")
            except Exception as reg_err:
                logger.warning(f"强制注册内置策略失败: {reg_err}")

            # 检查缓存 - 包含策略版本和阈值参数信息以避免参数修改后返回旧缓存
            strategy_version = "3.0.2"  # AdaptivePandas策略版本
            # 获取策略默认阈值参数（用于缓存键）
            backtest_threshold = 0.45  # 默认回测阈值
            live_threshold = 0.6  # 默认实盘阈值
            cache_key = f"{strategy_name}_v{strategy_version}_bt{backtest_threshold}_live{live_threshold}_{len(kdata)}"
            if cache_key in self.signal_cache:
                logger.info(f"使用缓存的策略信号: {cache_key}")
                return self.signal_cache[cache_key]

            from core.strategy.base_strategy import SignalType
            from core.strategy.strategy_engine import get_strategy_engine

            logger.info(f"生成策略信号: {strategy_name}")

            # 获取策略引擎
            strategy_engine = get_strategy_engine()

            # 执行策略
            signals_list, execution_info = strategy_engine.execute_strategy(
                strategy_name,
                kdata,
                use_cache=True,
                save_to_db=False
            )

            # 转换为数值类型（BUY=1, SELL=-1, HOLD=0）
            signals = pd.Series(0.0, index=kdata.index, dtype=float)
            
            # 构建时间戳到索引的映射，处理timestamp可能不在index中的情况
            timestamp_to_idx = {ts: i for i, ts in enumerate(kdata.index)}
            
            for signal in signals_list:
                if signal.timestamp in timestamp_to_idx:
                    idx = timestamp_to_idx[signal.timestamp]
                    if signal.signal_type == SignalType.BUY:
                        signals.iloc[idx] = 1.0
                    elif signal.signal_type == SignalType.SELL:
                        signals.iloc[idx] = -1.0
                    else:  # HOLD
                        signals.iloc[idx] = 0.0

            # 验证信号格式
            signals = self._validate_signals(signals, kdata)

            # 缓存策略信号
            with self.cache_lock:
                if len(self.signal_cache) >= self.cache_max_size:
                    # 清理最旧的缓存
                    oldest_key = next(iter(self.signal_cache))
                    del self.signal_cache[oldest_key]
                self.signal_cache[cache_key] = signals

            logger.info(f"生成策略信号成功: {strategy_name}, {len(signals_list)}个信号, 耗时: {execution_info['execution_time']:.3f}s")
            return signals

        except ImportError as e:
            logger.error(f"策略模块导入失败: {e}")
            QMessageBox.warning(
                self,
                "策略模块不可用",
                "策略模块暂时无法使用，回测将使用默认策略（无交易信号）。\n\n"
                "可能的原因：\n"
                "• 策略模块未正确安装\n"
                "• 策略模块配置错误\n\n"
                "建议：稍后重试或联系技术支持。"
            )
            # 返回默认信号（全0）
            return pd.Series(0.0, index=kdata.index, dtype=float)
        except Exception as e:
            logger.error(f"生成策略信号失败: {e}")
            QMessageBox.warning(
                self,
                "策略执行失败",
                "策略执行过程中发生错误，回测将使用默认策略（无交易信号）。\n\n"
                "建议：检查策略参数是否正确，或尝试使用其他策略。"
            )
            # 返回默认信号（全0）
            return pd.Series(0.0, index=kdata.index, dtype=float)

    def _validate_signals(self, signals: pd.Series, kdata: pd.DataFrame) -> pd.Series:
        """验证信号格式"""
        try:
            logger.info("验证信号格式...")

            # 验证信号类型
            if not isinstance(signals, (pd.Series, np.ndarray)):
                raise ValueError(f"信号类型错误: {type(signals)}，期望 pd.Series 或 np.ndarray")

            # 转换为 pd.Series
            if isinstance(signals, np.ndarray):
                signals = pd.Series(signals, index=kdata.index)

            # 验证信号值类型
            if not pd.api.types.is_numeric_dtype(signals):
                raise ValueError("信号值必须为数值类型")

            # 验证信号索引
            if not signals.index.equals(kdata.index):
                logger.warning("信号索引与数据索引不一致，尝试对齐...")
                signals = signals.reindex(kdata.index, fill_value=0.0)

            # 验证信号长度
            if len(signals) != len(kdata):
                raise ValueError(f"信号长度({len(signals)})与数据长度({len(kdata)})不一致")

            # 验证信号值范围
            invalid_values = signals[(signals != 1) & (signals != 0) & (signals != -1)]
            if len(invalid_values) > 0:
                logger.warning(f"发现{len(invalid_values)}个无效信号值，将被限制在[-1, 1]范围内")
                signals = signals.clip(-1, 1)

            # 检查 NaN 值
            if signals.isna().any():
                nan_count = signals.isna().sum()
                logger.warning(f"发现{nan_count}个 NaN 信号值，将被替换为 0")
                signals = signals.fillna(0.0)

            logger.info("信号格式验证通过")
            return signals

        except Exception as e:
            logger.error(f"信号格式验证失败: {e}")
            raise

    def _validate_backtest_results(self, results: Dict) -> Dict:
        """验证回测结果"""
        try:
            logger.info("验证回测结果...")

            # 验证结果类型
            if not isinstance(results, dict):
                raise ValueError(f"结果类型错误: {type(results)}，期望 dict")

            # 验证必需字段
            required_fields = ['total_return', 'max_drawdown', 'sharpe_ratio']
            for field in required_fields:
                if field not in results:
                    logger.warning(f"缺少必需字段: {field}，将使用默认值 0.0")
                    results[field] = 0.0

            # 验证数值字段
            numeric_fields = ['total_return', 'max_drawdown', 'sharpe_ratio', 'volatility', 'win_rate', 'profit_factor']
            for field in numeric_fields:
                if field in results:
                    value = results[field]
                    if pd.isna(value) or np.isinf(value):
                        logger.warning(f"字段{field}包含无效值: {value}，将使用默认值 0.0")
                        results[field] = 0.0
                    elif not isinstance(value, (int, float)):
                        logger.warning(f"字段{field}类型错误: {type(value)}，将转换为 float")
                        results[field] = float(value)

            # 验证收益率范围
            if 'total_return' in results:
                if results['total_return'] < -1.0 or results['total_return'] > 10.0:
                    logger.warning(f"收益率异常: {results['total_return']:.2%}，将被限制在[-100%, 1000%]范围内")
                    results['total_return'] = max(-1.0, min(10.0, results['total_return']))

            # 验证夏普比率范围
            if 'sharpe_ratio' in results:
                if results['sharpe_ratio'] < -10.0 or results['sharpe_ratio'] > 10.0:
                    logger.warning(f"夏普比率异常: {results['sharpe_ratio']}，将被限制在[-10, 10]范围内")
                    results['sharpe_ratio'] = max(-10.0, min(10.0, results['sharpe_ratio']))

            # 验证最大回撤范围
            if 'max_drawdown' in results:
                if results['max_drawdown'] < -1.0 or results['max_drawdown'] > 0.0:
                    logger.warning(f"最大回撤异常: {results['max_drawdown']:.2%}，将被限制在[-100%, 0%]范围内")
                    results['max_drawdown'] = max(-1.0, min(0.0, results['max_drawdown']))

            # 验证交易记录
            if 'trades' in results:
                if not isinstance(results['trades'], list):
                    logger.warning("交易记录格式错误，将使用空列表")
                    results['trades'] = []
                else:
                    # 验证每个交易记录
                    valid_trades = []
                    for trade in results['trades']:
                        if isinstance(trade, dict) and 'price' in trade and 'quantity' in trade:
                            valid_trades.append(trade)
                        else:
                            logger.warning(f"交易记录格式错误: {trade}")
                    results['trades'] = valid_trades

            # 验证资金曲线
            if 'equity_curve' in results:
                if isinstance(results['equity_curve'], pd.Series):
                    results['equity_curve'] = results['equity_curve'].tolist()
                elif not isinstance(results['equity_curve'], (list, np.ndarray)):
                    logger.warning("资金曲线格式错误，将使用空列表")
                    results['equity_curve'] = []

            logger.info("回测结果验证通过")
            return results

        except Exception as e:
            logger.error(f"回测结果验证失败: {e}")
            raise

    def _on_backtest_completed(self, results: Dict):
        """回测完成处理"""
        try:
            if getattr(self, '_is_closing', False):
                return
            import time

            self.backtest_completed.emit(results)

            # 记录执行时间
            self.execution_time = time.time() - self.start_time if hasattr(self, 'start_time') else 0.0

            logger.info(f"回测完成，执行时间：{self.execution_time:.2f}s")
            logger.info(f"回测结果总览: total_return={results.get('total_return', 0):.4f}, "
                       f"max_drawdown={results.get('max_drawdown', 0):.4f}, "
                       f"sharpe_ratio={results.get('sharpe_ratio', 0):.4f}, "
                       f"trade_count={results.get('trade_count', 0)}")

            # 更新进度到 100%
            self.control_panel.update_progress(100, "回测完成", "回测已完成")
            
            # ❌ 移除：不在这里切换按钮状态，等待图表展示完成
            # self.control_panel.on_backtest_finished()  # 已删除

            # 保存回测结果
            if self.backtest_result_manager:
                try:
                    from core.services.backtest_result_manager import BacktestResult
                    self.backtest_result_manager.add_result(
                        BacktestResult(
                            stock_code=self.current_stock_code,
                            stock_name=self.current_stock_name,
                            strategy_name=self.current_strategy,
                            backtest_time=time.time(),
                            backtest_results=results,
                            trades=results.get('trades', []),
                            duration=self.execution_time,
                            is_professional=True
                        )
                    )
                    logger.info("回测结果已保存")
                except Exception as e:
                    logger.error(f"保存回测结果失败: {e}")
                    # 尝试保存到本地文件
                    try:
                        self._save_results_to_local_file(results)
                        logger.warning("回测结果已保存到本地文件")
                    except Exception as e2:
                        logger.error(f"保存到本地文件也失败: {e2}")
            else:
                # 如果没有 BacktestResultManager，直接保存到本地文件
                try:
                    self._save_results_to_local_file(results)
                    logger.info("回测结果已保存到本地文件")
                except Exception as e:
                    logger.error(f"保存到本地文件失败: {e}")

            # 使用线程锁保护共享变量
            with self.state_lock:
                self.current_results = results

            # 发布事件通知RightPanel刷新
            try:
                from core.events import get_event_bus, AnalysisCompleteEvent
                event_bus = get_event_bus()
                event_bus.publish(AnalysisCompleteEvent(
                    stock_code=self.current_stock_code,
                    analysis_type="backtest",
                    results={"backtest": results}
                ))
                logger.info("回测完成事件已发布")
            except Exception as e:
                logger.warning(f"发布事件失败: {e}")

            # 更新当前 UI 的图表和指标显示
            try:
                # 更新指标面板
                if hasattr(self, 'metrics_panel') and self.metrics_panel:
                    self.metrics_panel.update_metrics(results)
                    logger.info("回测指标面板已更新")
                
                # 更新风险指标面板（如果存在）
                if hasattr(self, 'risk_metrics_panel') and self.risk_metrics_panel:
                    self.risk_metrics_panel.update_risk_metrics(results)
                    logger.info("风险指标面板已更新")
                
                # 更新图表 - 使用事件驱动的实时推送方式
                if hasattr(self, 'chart_widget') and self.chart_widget:
                    # 从回测结果中提取 equity_curve 数据
                    equity_curve = results.get('equity_curve')
                    logger.info(f"equity_curve 提取：type={type(equity_curve)}, len={len(equity_curve) if hasattr(equity_curve, '__len__') else 'N/A'}")
                    
                    if equity_curve is not None and len(equity_curve) > 0:
                        # 准备所有数据点 - 包含回撤计算
                        from datetime import datetime
                        
                        if isinstance(equity_curve, pd.Series):
                            logger.info(f"equity_curve 前 5 个值 (Series): {equity_curve[:5].tolist()}")
                            logger.info(f"equity_curve 统计：min={equity_curve.min():.2f}, max={equity_curve.max():.2f}, mean={equity_curve.mean():.2f}")
                            equity_curve = equity_curve.tolist()
                        
                        if isinstance(equity_curve, list):
                            logger.info(f"equity_curve 前 5 个值 (list): {equity_curve[:5]}")
                            if len(equity_curve) > 0:
                                logger.info(f"equity_curve 统计：min={min(equity_curve):.2f}, max={max(equity_curve):.2f}, mean={sum(equity_curve)/len(equity_curve):.2f}")
                                logger.info(f"equity_curve 后 5 个值：{equity_curve[-5:]}")
                            
                            # 提取初始资金（必须在最前面定义）
                            initial_capital = equity_curve[0] if equity_curve[0] != 0 else 1
                            logger.info(f"初始资金：{initial_capital}")
                            
                            # 检查是否有非初始值的点
                            non_initial = [v for v in equity_curve if abs(v - initial_capital) > 0.01]
                            logger.info(f"非初始资金的数据点数量：{len(non_initial)}/{len(equity_curve)}")
                            
                            # 从回测结果中提取风险指标（这些是整体指标，不是时间序列）
                            risk_metrics_for_chart = {
                                'var_95': results.get('var_95', 0) or 0,
                                'cvar_95': results.get('cvar_95', 0) or 0,
                                'sharpe_ratio': results.get('sharpe_ratio', 0) or 0
                            }
                            
                            logger.info(f"提取风险指标：VaR={risk_metrics_for_chart['var_95']:.6f}, CVaR={risk_metrics_for_chart['cvar_95']:.6f}, Sharpe={risk_metrics_for_chart['sharpe_ratio']:.3f}")
                            
                            # 计算回撤曲线
                            running_max = initial_capital
                            drawdown_curve = []
                            
                            data_points = []
                            for i, value in enumerate(equity_curve):
                                # 更新运行最大值
                                if value > running_max:
                                    running_max = value
                                    logger.debug(f"bar {i}: 更新 running_max = {running_max}")
                                
                                # 计算当前回撤
                                current_drawdown = (value - running_max) / running_max if running_max > 0 else 0
                                drawdown_curve.append(current_drawdown)
                                
                                if i < 5 or i >= len(equity_curve) - 5 or i % 50 == 0:  # 显示前 5 个、后 5 个和每 50 个的日志
                                    logger.info(f"bar {i}: value={value:.2f}, running_max={running_max:.2f}, drawdown={current_drawdown:.6f}")
                                
                                # 创建数据点，包含风险指标
                                data_point = {
                                    'timestamp': datetime.now(),
                                    'cumulative_return': (value / initial_capital - 1),
                                    'current_drawdown': current_drawdown,  # ✅ 使用计算的回撤值
                                    'capital': value,
                                    'bar_index': i,
                                    'total_bars': len(equity_curve),
                                    # 添加风险指标（每个点都包含相同的整体指标值）
                                    'var_95': risk_metrics_for_chart['var_95'],
                                    'cvar_95': risk_metrics_for_chart['cvar_95'],
                                    'sharpe_ratio': risk_metrics_for_chart['sharpe_ratio']
                                }
                                data_points.append(data_point)
                            
                            # 输出回撤统计
                            if drawdown_curve:
                                logger.info(f"回撤计算完成：min={min(drawdown_curve):.6f}, max={max(drawdown_curve):.6f}, 非零数量={sum(1 for d in drawdown_curve if d < 0)}")
                                logger.info(f"回撤后 5 个值：{drawdown_curve[-5:]}")
                            
                            # 方案 1: 使用渐进式动态展示（推荐，可看到动态过程）
                            if hasattr(self.chart_widget, 'start_progressive_display'):
                                self.chart_widget.start_progressive_display(data_points, batch_size=15, interval_ms=30)
                                logger.info(f"启动渐进式展示：{len(equity_curve)}个数据点")
                            
                            # 方案 2: 使用事件推送（实时性更好，需要事件总线支持）
                            # 已注释，因为当前使用渐进式展示已经足够
                            # try:
                            #     from core.events import get_event_bus, BacktestProgressEvent
                            #     event_bus = get_event_bus()
                            #     for dp in data_points:
                            #         event_bus.publish(BacktestProgressEvent(
                            #             bar_index=dp['bar_index'],
                            #             total_bars=dp['total_bars'],
                            #             progress=dp['bar_index'] / dp['total_bars'],
                            #             current_result=dp
                            #         ))
                            # except Exception as e:
                            #     logger.warning(f"事件推送失败：{e}")
            except Exception as e:
                logger.warning(f"更新图表失败：{e}")


            # 更新UI显示 - 使用统一的风险指标更新和预警检查
            try:
                # 调用统一的风险指标更新（内部会检查预警）
                self._update_risk_metrics(results)
            except Exception as e:
                logger.warning(f"风险指标更新失败: {e}")
                # 备用方案：直接检查关键预警
                self._check_critical_alerts(results)

            self.alerts_panel.add_alert('success', f'回测完成: {self.current_stock_code}')

        except Exception as e:
            logger.error(f"处理回测完成失败：{e}")
            # 【新增】通知用户并恢复状态
            try:
                self.control_panel.update_progress(0, "回测失败", f"回测完成处理失败：{str(e)}")
                self.control_panel.on_stop_backtest()
            except Exception as e:
                logger.warning(f"回测失败后通知UI失败: {e}")

    def _on_progress_update(self, progress: int, stage: str, message: str):
        """进度更新槽函数（在主线程执行）"""
        try:
            if getattr(self, '_is_closing', False):
                return
            self.control_panel.update_progress(progress, stage, message)
        except Exception as e:
            logger.error(f"进度更新失败：{e}")

    def on_chart_display_completed(self):
        """图表展示完成后的处理（在主线程执行）"""
        try:
            if getattr(self, '_is_closing', False):
                logger.info("窗口正在关闭，跳过图表完成后的按钮状态重置")
                return
            logger.info("图表展示完成，重置按钮状态")
            # ✅ 在图表完全展示后才切换按钮状态
            self.control_panel.on_backtest_finished()
        except Exception as e:
            logger.error(f"图表展示完成处理失败：{e}")

    def _on_alert_request(self, level: str, message: str):
        """预警添加槽函数（在主线程执行）"""
        try:
            if getattr(self, '_is_closing', False):
                return
            self.alerts_panel.add_alert(level, message)
        except Exception as e:
            logger.error(f"添加预警失败：{e}")

    def _save_results_to_local_file(self, results: Dict):
        """保存回测结果到本地文件（带事务保证）"""
        import json
        import os
        import tempfile
        from datetime import datetime

        save_dir = os.path.join(os.getcwd(), 'backtest_results')
        os.makedirs(save_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"backtest_{self.current_stock_code}_{self.current_strategy}_{timestamp}.json"
        filepath = os.path.join(save_dir, filename)

        save_data = {
            'stock_code': self.current_stock_code,
            'stock_name': self.current_stock_name,
            'strategy_name': self.current_strategy,
            'backtest_time': datetime.now().isoformat(),
            'execution_time': self.execution_time,
            'results': results
        }

        temp_fd, temp_path = tempfile.mkstemp(suffix='.json', dir=save_dir)
        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())

            with open(temp_path, 'r', encoding='utf-8') as f:
                verified_data = json.load(f)
                if verified_data.get('stock_code') != self.current_stock_code:
                    raise RuntimeError("数据验证失败")

            os.replace(temp_path, filepath)
            logger.info(f"回测结果已保存到: {filepath}")
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.debug(f"清理临时文件失败: {e}")
            raise RuntimeError(f"保存到本地文件失败: {e}")

    def stop_backtest(self):
        """停止回测"""
        try:
            if getattr(self, '_is_closing', False):
                return
            if not self.is_monitoring:
                logger.info("没有正在运行的回测")
                return

            # 显示确认对话框
            reply = QMessageBox.question(
                self,
                "确认停止",
                "确定要停止当前回测吗？\n\n"
                "停止后，当前的回测结果将不会被保存。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.No:
                logger.info("用户取消停止操作")
                return

            logger.info("正在停止回测...")
            self.is_monitoring = False

            if self.monitoring_thread and self.monitoring_thread.is_alive():
                logger.info(f"等待监控线程结束 - 线程 ID: {self.monitoring_thread.ident}")

                # 异步等待线程结束，UI 更新由 _on_thread_cleanup_complete 处理
                self._cleanup_thread_async()
                # 不立即执行 UI 更新，等待异步清理完成
            else:
                # 线程已结束或未启动，直接清理并更新 UI
                self.monitoring_thread = None
                self._on_thread_cleanup_complete()

            # 性能监控已移至性能监控中心

            logger.info("回测已停止")

        except Exception as e:
            logger.error(f"停止回测失败：{e}")

    def _cleanup_thread_async(self):
        """异步清理监控线程，避免阻塞 UI"""
        from PyQt5.QtCore import QThread
        
        # 检查是否已有清理线程在运行（防止重复创建）
        if hasattr(self, '_cleanup_thread') and self._cleanup_thread is not None:
            if self._cleanup_thread.isRunning():
                logger.warning("已有清理线程在运行，跳过")
                return
        
        def wait_thread():
            """在工作线程中等待监控线程结束"""
            try:
                if self.monitoring_thread and self.monitoring_thread.is_alive():
                    self.monitoring_thread.join(timeout=2.0)
                    
                    if self.monitoring_thread.is_alive():
                        logger.warning(f"监控线程未能在 2 秒内结束 - 线程 ID: {self.monitoring_thread.ident}")
                    else:
                        logger.info("监控线程已正常结束")
            except Exception as e:
                logger.error(f"等待线程结束失败：{e}")
            finally:
                # 清理线程引用
                self.monitoring_thread = None
                
                # 通过信号通知清理完成（在主线程中执行）
                try:
                    # 使用 metaObject 方法调用主线程的方法
                    from PyQt5.QtCore import QMetaObject, Qt
                    QMetaObject.invokeMethod(
                        self, '_on_thread_cleanup_complete', Qt.QueuedConnection
                    )
                except Exception as e:
                    logger.error(f"调用清理完成方法失败：{e}")
        
        # 创建工作线程并保存引用
        try:
            from PyQt5.QtCore import QObject
            self._cleanup_worker = QObject()
            self._cleanup_thread = QThread()
            self._cleanup_worker.moveToThread(self._cleanup_thread)
            self._cleanup_thread.started.connect(lambda: wait_thread())
            self._cleanup_thread.finished.connect(self._on_cleanup_worker_finished)
            
            # 启动工作线程
            self._cleanup_thread.start()
            logger.info("已启动异步线程清理任务")
        except Exception as e:
            logger.error(f"启动清理线程失败：{e}")
            # 回退到同步清理
            self.monitoring_thread = None
            self._on_thread_cleanup_complete()
    
    def _on_cleanup_worker_finished(self):
        """清理工作线程完成后的处理"""
        logger.debug("清理工作线程已结束")
        self._cleanup_worker = None
        self._cleanup_thread = None
    
    def _cleanup_thread_sync(self, update_ui=True):
        """同步清理监控线程（用于窗口关闭等场景）
        
        Args:
            update_ui: 是否更新 UI。窗口关闭时设为 False 可避免不必要的 UI 更新
        """
        try:
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                logger.info("同步等待监控线程结束...")
                self.monitoring_thread.join(timeout=2.0)
                
                if self.monitoring_thread.is_alive():
                    logger.warning(f"监控线程未能在 2 秒内结束 - 线程 ID: {self.monitoring_thread.ident}")
                else:
                    logger.info("监控线程已正常结束")
        except Exception as e:
            logger.error(f"同步等待线程结束失败：{e}")
        finally:
            self.monitoring_thread = None
            
        # 根据参数决定是否更新 UI
        if update_ui:
            self._on_thread_cleanup_complete()
    
    def _on_thread_cleanup_complete(self):
        """线程清理完成后的处理（在主线程中执行）"""
        logger.info("线程清理完成，更新 UI")
        self.control_panel.on_stop_backtest()
        self.control_panel.reset_progress()
        self.alerts_panel.add_alert('warning', '回测已停止，结果未保存')

    def start_monitoring(self, data: pd.DataFrame, params: Dict):
        """启动监控"""
        if getattr(self, '_is_closing', False):
            return
        if self.is_monitoring:
            self.stop_backtest()

        # 创建真实的回测监控器（不使用资源管理器）
        from backtest.real_time_backtest_monitor import RealTimeBacktestMonitor, MonitoringLevel
        from backtest.unified_backtest_engine import UnifiedBacktestEngine
        
        def monitoring_loop():
            """优化的回测监控循环 - 单次完整回测"""
            thread_name = threading.current_thread().name
            logger.info(f"回测监控循环开始 - 线程: {thread_name}")
            
            try:
                # 获取当前回测数据
                if hasattr(self, 'current_data') and self.current_data is not None:
                    data = self.current_data
                else:
                    raise RuntimeError("无法获取回测数据，请先启动回测")
                
                data_len = len(data)
                logger.info(f"回测数据量: {data_len} 条")
                
                # 获取风控配置参数
                risk_control = params.get('risk_control', {})
                stop_loss = risk_control.get('stop_loss', 0.10)
                take_profit = risk_control.get('take_profit', 0.20)
                max_holding = risk_control.get('max_holding_periods', 0)
                
                # 转换为引擎需要的格式（小数）
                stop_loss_pct = stop_loss / 100 if stop_loss > 1 else stop_loss
                take_profit_pct = take_profit / 100 if take_profit > 1 else take_profit
                max_holding_periods = int(max_holding) if max_holding and max_holding > 0 else None
                
                # 获取引擎配置
                use_vectorized = params.get('use_vectorized_engine', True)
                auto_select = params.get('auto_select_engine', True)
                execution_model_text = params.get('execution_model', '固定滑点(默认)')
                execution_model_map = {
                    '固定滑点(默认)': 'fixed',
                    'VWAP模型': 'vwap',
                    '随机价格模型': 'random'
                }
                execution_model = execution_model_map.get(execution_model_text, 'fixed')
                
                # 使用复用模式获取引擎
                from backtest.unified_backtest_engine import BacktestLevel
                engine_config = {
                    'backtest_level': BacktestLevel.PROFESSIONAL,
                    'use_vectorized_engine': use_vectorized,
                    'auto_select_engine': auto_select,
                    'execution_model': execution_model
                }
                backtest_engine = self._get_engine(engine_config)
                
                logger.info("使用复用的回测引擎")
                
                # 定义真实进度回调函数（替代模拟进度线程）
                def progress_callback(bar_index: int, total_bars: int, current_result: Dict = None):
                    """真实的回测进度回调"""
                    if getattr(self, '_is_closing', False):
                        return
                    try:
                        progress = int((bar_index / total_bars) * 100) if total_bars > 0 else 0
                        
                        # 根据进度判断阶段
                        if progress < 20:
                            stage_name = "数据验证"
                            message = f"验证数据完整性... ({bar_index}/{total_bars})"
                        elif progress < 40:
                            stage_name = "策略计算"
                            message = f"计算策略指标... ({bar_index}/{total_bars})"
                        elif progress < 60:
                            stage_name = "信号生成"
                            message = f"生成交易信号... ({bar_index}/{total_bars})"
                        elif progress < 80:
                            stage_name = "回测执行"
                            message = f"执行回测引擎... ({bar_index}/{total_bars})"
                        elif progress < 95:
                            stage_name = "风险计算"
                            message = f"计算风险指标... ({bar_index}/{total_bars})"
                        else:
                            stage_name = "结果汇总"
                            message = f"汇总回测结果... ({bar_index}/{total_bars})"
                        
                        self.request_progress_update.emit(progress, stage_name, message)
                    except Exception as e:
                        logger.debug(f"进度回调异常: {e}")
                
                # 直接运行一次完整回测（使用真实进度回调）
                try:
                    logger.info("开始执行单次完整回测...")
                    
                    # 创建模式上下文
                    mode_context = ModeContext.create_backtest(
                        start_date=params.get('start_date') if params else None,
                        end_date=params.get('end_date') if params else None
                    )
                    
                    # 设置引擎的模式上下文
                    if hasattr(backtest_engine, 'mode_context'):
                        backtest_engine.mode_context = mode_context
                    
                    final_result = backtest_engine.run_backtest(
                        data=data,
                        initial_capital=params.get('initial_capital', 100000),
                        position_size=params.get('position_size', 1.0),
                        commission_pct=params.get('commission_pct', 0.001),
                        slippage_pct=params.get('slippage_pct', 0.001),
                        stop_loss_pct=stop_loss_pct if stop_loss_pct > 0 else None,
                        take_profit_pct=take_profit_pct if take_profit_pct > 0 else None,
                        max_holding_periods=max_holding_periods,
                        enable_compound=params.get('enable_compound', True),
                        benchmark_data=params.get('benchmark_data'),
                        mode_context=mode_context,
                        progress_callback=progress_callback  # 使用真实进度回调
                    )
                    # 调试：打印返回类型
                    logger.info(f"回测结果类型：{type(final_result).__name__}")
                    if isinstance(final_result, dict):
                        eq_curve = final_result.get('equity_curve')
                        if eq_curve is not None:
                            logger.info(f"返回字典，键数：{len(final_result)}, equity_curve 类型：{type(eq_curve).__name__}, 长度：{len(eq_curve) if hasattr(eq_curve, '__len__') else 'N/A'}")
                        else:
                            logger.info(f"返回字典，键数：{len(final_result)}, equity_curve: None")
                    elif hasattr(final_result, '__len__'):
                        logger.info(f"返回对象长度：{len(final_result)}")
                except Exception as e:
                    logger.error(f"回测执行失败：{e}")
                    raise
                
                # 获取完整结果
                final_results = None
                
                # 处理两种返回类型：字典（统一引擎）或DataFrame（标准引擎）
                if isinstance(final_result, dict):
                    # 统一引擎返回的字典格式
                    try:
                        final_results = {
                            'equity_curve': final_result.get('equity_curve'),
                            'trades': final_result.get('trades', []),
                            'total_trades': final_result.get('total_trades', 0),
                            'total_return': final_result.get('total_return', 0.0),
                            'max_drawdown': final_result.get('max_drawdown', 0.0),
                            'sharpe_ratio': final_result.get('sharpe_ratio', 0.0),
                            'win_rate': final_result.get('win_rate', 0.0),
                            'profit_factor': final_result.get('profit_factor', 0.0),
                            'volatility': final_result.get('volatility', 0.0),
                            'annualized_return': final_result.get('annualized_return', 0.0),
                            'calmar_ratio': final_result.get('calmar_ratio', 0.0),
                            'sortino_ratio': final_result.get('sortino_ratio', 0.0),
                            'var_95': final_result.get('var_95', 0.0),
                            'cvar_95': final_result.get('cvar_95', 0.0),
                            'trade_count': final_result.get('total_trades', 0),
                            'data_rows': len(final_result.get('equity_curve', [])) if final_result.get('equity_curve') is not None else 0
                        }
                        logger.info(f"成功获取完整回测结果，交易次数: {final_results['total_trades']}")
                    except Exception as e:
                        logger.error(f"转换回测结果失败: {e}")
                        final_results = None
                elif final_result is not None and hasattr(final_result, 'to_dict'):
                    # 兼容DataFrame格式（旧引擎）
                    try:
                        result_dict = final_result.to_dict(orient='records')
                        
                        # 计算累计收益
                        cumulative_return = 0.0
                        if 'capital' in final_result.columns and len(final_result) > 0:
                            cumulative_return = (final_result['capital'].iloc[-1] / final_result['capital'].iloc[0] - 1)
                        
                        # 计算交易次数
                        trade_count = 0
                        if 'position' in final_result.columns:
                            positions = final_result['position'].values
                            trade_count = np.sum(np.diff(positions) != 0)
                        
                        final_results = {
                            'backtest_data': result_dict,
                            'equity_curve': final_result['capital'].tolist() if 'capital' in final_result.columns else [],
                            'position_curve': final_result['position'].tolist() if 'position' in final_result.columns else [],
                            'returns_curve': final_result['returns'].tolist() if 'returns' in final_result.columns else [],
                            'cumulative_return': cumulative_return,
                            'trade_count': int(trade_count),
                            'data_rows': len(final_result)
                        }
                        logger.info(f"成功获取完整回测结果，数据行数: {len(final_result)}")
                    except Exception as e:
                        logger.error(f"转换回测结果失败: {e}")
                        final_results = None
                
                # 如果单次回测失败，尝试使用监控器方式（带进度回调）
                if final_results is None:
                    logger.warning("单次回测失败，尝试使用监控器方式")
                    
                    def monitor_progress_callback(bar_index: int, total_bars: int, current_result: Dict = None):
                        """监控器进度回调"""
                        if getattr(self, '_is_closing', False):
                            return
                        progress = int((bar_index / total_bars) * 100) if total_bars > 0 else 0
                        self.request_progress_update.emit(progress, "回测执行", f"监控模式: {bar_index}/{total_bars}")
                    
                    monitor = self._get_monitor()
                    monitor.start_monitoring(
                        backtest_engine=backtest_engine,
                        data=data,
                        initial_capital=params.get('initial_capital', 100000),
                        engine_type="unified",
                        stop_loss_pct=stop_loss_pct,
                        take_profit_pct=take_profit_pct,
                        max_holding_periods=max_holding_periods,
                        progress_callback=monitor_progress_callback  # 传入进度回调
                    )
                    
                    # 等待监控完成
                    while self.is_monitoring and monitor.is_monitoring:
                        time.sleep(0.2)
                    
                    # 从监控器获取结果
                    if hasattr(monitor, 'get_monitoring_summary'):
                        summary = monitor.get_monitoring_summary()
                        if summary:
                            final_results = summary
                    monitor.stop_monitoring()
                
                # 保存结果
                if final_results:
                    self._monitoring_data = final_results
                    final_results = self._validate_backtest_results(final_results)
                    self.current_results = final_results
                    
                    # 通过信号更新进度到 100%（修复工作线程无法使用 QTimer 的问题）
                    self.request_progress_update.emit(100, "回测完成", "回测已完成")
                    
                    # 通过信号调用主线程的 UI 更新方法（修复工作线程无法使用 QTimer 的问题）
                    self.request_ui_update.emit(final_results)
                    logger.info(f"回测完成，最终结果已保存，已发送 UI 更新信号")
                else:
                    logger.error("未能获取最终回测结果")
                    # 通过信号更新失败状态
                    self.request_progress_update.emit(0, "回测失败", "无法获取回测结果")
                
            except Exception as e:
                logger.error(f"回测循环异常：{e}")
                import traceback
                logger.error(traceback.format_exc())
                
                # 通过信号通知 UI 回测失败（修复工作线程无法使用 QTimer 的问题）
                self.request_progress_update.emit(0, "回测失败", str(e))
            
            finally:
                self.is_monitoring = False
                logger.info(f"回测循环结束 - 线程: {thread_name}")

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
            if getattr(self, '_is_closing', False):
                return
            drawdown = data.get('current_drawdown', 0)
            if drawdown > 0.15:
                self._safe_add_alert({'level': 'critical', 'message': f'回撤过大: {drawdown:.2%}'})
            elif drawdown > 0.1:
                self._safe_add_alert({'level': 'warning', 'message': f'回撤警告: {drawdown:.2%}'})

            sharpe = data.get('sharpe_ratio', 0)
            if sharpe < 0:
                self._safe_add_alert({'level': 'warning', 'message': f'Sharpe比率为负: {sharpe:.3f}'})

            volatility = data.get('volatility', 0)
            if volatility > 0.3:
                self._safe_add_alert({'level': 'warning', 'message': f'波动率过高: {volatility:.2%}'})

        except Exception as e:
            logger.error(f"检查预警失败: {e}")

    def _update_risk_metrics(self, results: Dict):
        """从回测结果更新风险指标（统一入口）"""
        try:
            if getattr(self, '_is_closing', False):
                return
            
            if not results:
                return
            
            # 提取风险指标
            var_95 = results.get('var_95', 0) or 0
            cvar_95 = results.get('cvar_95', 0) or 0
            max_drawdown = results.get('max_drawdown', 0) or 0
            volatility = results.get('volatility', 0) or 0
            sharpe_ratio = results.get('sharpe_ratio', 0) or 0
            
            new_metrics = {
                'var_95': var_95,
                'cvar_95': cvar_95,
                'max_drawdown': max_drawdown,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio
            }
            
            # 检查是否有变化
            if hasattr(self, 'risk_metrics') and self.risk_metrics == new_metrics:
                return
            
            self.risk_metrics = new_metrics
            self._check_risk_alerts()
            
            if hasattr(self, 'alerts_panel') and self.alerts_panel:
                self.alerts_panel.update_risk_metrics(self.risk_metrics)
                
        except Exception as e:
            logger.error(f"更新风险指标失败: {e}")

    def _check_critical_alerts(self, results: Dict):
        """检查关键预警（备用方案）"""
        try:
            max_dd = results.get('max_drawdown', 0) or 0
            dd_threshold = abs(self.risk_thresholds.get('max_drawdown', -0.20))
            if max_dd < -dd_threshold:
                self.alerts_panel.add_alert('critical', f"最大回撤 {abs(max_dd):.1%} 超过 {dd_threshold:.1%}")
            elif max_dd < -(dd_threshold / 2):
                self.alerts_panel.add_alert('warning', f"最大回撤 {abs(max_dd):.1%} 超过 {dd_threshold/2:.1%}")

            sharpe = results.get('sharpe_ratio', 0) or 0
            sharpe_threshold = self.risk_thresholds.get('sharpe_ratio', 0.5)
            if sharpe < 0:
                self.alerts_panel.add_alert('critical', f"夏普比率 {sharpe:.2f} 为负")
            elif sharpe < sharpe_threshold:
                self.alerts_panel.add_alert('warning', f"夏普比率 {sharpe:.2f} 低于 {sharpe_threshold:.2f}")
        except Exception as e:
            logger.error(f"检查关键预警失败: {e}")

    def _calculate_and_update_risk_metrics(self, data: Dict):
        """计算并更新风险指标 - 性能优化版本"""
        try:
            if not self.risk_metrics_calculator:
                return
            
            if 'returns' not in data or not data['returns']:
                return
            
            returns = data.get('returns', [])
            if len(returns) < 10:
                return
            
            returns_tuple = tuple(returns[-100:]) if len(returns) > 100 else tuple(returns)
            returns_hash = hash(returns_tuple)
            
            if hasattr(self, '_last_risk_returns_hash') and self._last_risk_returns_hash == returns_hash:
                return
            
            self._last_risk_returns_hash = returns_hash
            
            import pandas as pd
            import numpy as np
            returns_series = pd.Series(returns)
            
            var_95 = self.risk_metrics_calculator.calculate_value_at_risk(returns_series, 0.95)
            cvar_95 = self.risk_metrics_calculator.calculate_conditional_var(returns_series, 0.95)
            max_drawdown = data.get('max_drawdown', 0)
            volatility = data.get('volatility', 0)
            sharpe_ratio = data.get('sharpe_ratio', 0)
            
            new_metrics = {
                'var_95': var_95,
                'cvar_95': cvar_95,
                'max_drawdown': max_drawdown,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio
            }
            
            if hasattr(self, 'risk_metrics') and self.risk_metrics == new_metrics:
                return
            
            self.risk_metrics = new_metrics
            
            self._check_risk_alerts()
            
            if hasattr(self, 'alerts_panel') and self.alerts_panel:
                self.alerts_panel.update_risk_metrics(self.risk_metrics)
                
        except Exception as e:
            logger.error(f"计算风险指标失败: {e}")

    def _check_risk_alerts(self):
        """检查风险预警"""
        try:
            if getattr(self, '_is_closing', False):
                return
            if not self.risk_metrics:
                return
            
            # 检查VaR预警
            var_95 = self.risk_metrics.get('var_95', 0)
            if var_95 < self.risk_thresholds['var_95']:
                alert_msg = f"⚠️ VaR(95%)风险预警: {var_95:.2%} < {self.risk_thresholds['var_95']:.2%}"
                if alert_msg not in self.risk_alerts:
                    self.risk_alerts.append(alert_msg)
                    if hasattr(self, 'alerts_panel') and self.alerts_panel:
                        self.alerts_panel.add_alert('critical', alert_msg)
            
            # 检查最大回撤预警
            max_drawdown = self.risk_metrics.get('max_drawdown', 0)
            if max_drawdown < self.risk_thresholds['max_drawdown']:
                alert_msg = f"⚠️ 最大回撤风险预警: {max_drawdown:.2%} < {self.risk_thresholds['max_drawdown']:.2%}"
                if alert_msg not in self.risk_alerts:
                    self.risk_alerts.append(alert_msg)
                    if hasattr(self, 'alerts_panel') and self.alerts_panel:
                        self.alerts_panel.add_alert('critical', alert_msg)
            
            # 检查波动率预警
            volatility = self.risk_metrics.get('volatility', 0)
            if volatility > self.risk_thresholds['volatility']:
                alert_msg = f"⚠️ 波动率风险预警: {volatility:.2%} > {self.risk_thresholds['volatility']:.2%}"
                if alert_msg not in self.risk_alerts:
                    self.risk_alerts.append(alert_msg)
                    if hasattr(self, 'alerts_panel') and self.alerts_panel:
                        self.alerts_panel.add_alert('warning', alert_msg)
            
            # 检查夏普比率预警
            sharpe_ratio = self.risk_metrics.get('sharpe_ratio', 0)
            if sharpe_ratio < self.risk_thresholds['sharpe_ratio']:
                alert_msg = f"⚠️ 夏普比率风险预警: {sharpe_ratio:.3f} < {self.risk_thresholds['sharpe_ratio']:.3f}"
                if alert_msg not in self.risk_alerts:
                    self.risk_alerts.append(alert_msg)
                    if hasattr(self, 'alerts_panel') and self.alerts_panel:
                        self.alerts_panel.add_alert('warning', alert_msg)
                        
        except Exception as e:
            logger.error(f"检查风险预警失败: {e}")

    def _apply_risk_control_rules(self, ui_data: Dict, params: Dict):
        """应用风险控制规则"""
        try:
            if getattr(self, '_is_closing', False):
                return
            risk_control = params.get('risk_control', {})
            if not risk_control:
                return
            
            max_drawdown_limit = risk_control.get('max_drawdown_limit', 0.20)
            stop_loss = risk_control.get('stop_loss', 0.10)
            take_profit = risk_control.get('take_profit', 0.20)
            max_position_size = risk_control.get('max_position_size', 0.10)
            
            current_drawdown = abs(ui_data.get('current_drawdown', 0))
            cumulative_return = ui_data.get('cumulative_return', 0)
            
            if current_drawdown >= max_drawdown_limit:
                alert_msg = f"🛑 风险控制触发: 最大回撤限制 {current_drawdown:.2%} >= {max_drawdown_limit:.2%}"
                if alert_msg not in self.risk_alerts:
                    self.risk_alerts.append(alert_msg)
                    if hasattr(self, 'alerts_panel') and self.alerts_panel:
                        self.alerts_panel.add_alert('critical', alert_msg)
                    logger.warning(f"风险控制触发: 最大回撤限制")
            
            if cumulative_return <= -stop_loss:
                alert_msg = f"🛑 风险控制触发: 止损 {cumulative_return:.2%} <= -{stop_loss:.2%}"
                if alert_msg not in self.risk_alerts:
                    self.risk_alerts.append(alert_msg)
                    if hasattr(self, 'alerts_panel') and self.alerts_panel:
                        self.alerts_panel.add_alert('critical', alert_msg)
                    logger.warning(f"风险控制触发: 止损")
            
            if cumulative_return >= take_profit:
                alert_msg = f"✅ 风险控制触发: 止盈 {cumulative_return:.2%} >= {take_profit:.2%}"
                if alert_msg not in self.risk_alerts:
                    self.risk_alerts.append(alert_msg)
                    if hasattr(self, 'alerts_panel') and self.alerts_panel:
                        self.alerts_panel.add_alert('info', alert_msg)
                    logger.info(f"风险控制触发: 止盈")
                        
        except Exception as e:
            logger.error(f"应用风险控制规则失败: {e}")

    def _safe_add_alert(self, alert_data):
        """安全的添加预警方法 - 在主线程中执行"""
        try:
            if getattr(self, '_is_closing', False):
                return
            if threading.current_thread() != threading.main_thread():
                QTimer.singleShot(0, lambda: self._add_alert_main_thread(alert_data))
            else:
                self._add_alert_main_thread(alert_data)
        except Exception as e:
            logger.error(f"安全添加预警失败: {e}")

    def _add_alert_main_thread(self, alert_data):
        """在主线程中添加预警的具体实现"""
        try:
            if getattr(self, '_is_closing', False):
                return
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
