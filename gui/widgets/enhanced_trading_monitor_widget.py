from loguru import logger
"""
增强交易监控组件

与重构后的TradingService完全集成，提供：
1. 实时信号显示
2. 订单状态监控
3. 仓位实时更新
4. 盈亏统计
5. 风险指标监控
6. 性能分析界面
"""

import sys
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import asdict

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QLabel, QGroupBox, QFormLayout, QPushButton,
    QScrollArea, QSplitter, QHeaderView, QProgressBar, QFrame,
    QGridLayout, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QApplication, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QListWidget, QListWidgetItem, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QPalette, QPixmap, QIcon

# 导入图表组件
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

import pandas as pd
import numpy as np
from decimal import Decimal

# 导入服务和数据结构
from core.services.trading_service import TradingService, TradeRecord, Portfolio
from core.services.strategy_service import StrategyService
from core.strategy_extensions import Signal, SignalType, Position

logger = logger

class RealTimeChart(QWidget):
    """实时图表组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)

        if MATPLOTLIB_AVAILABLE:
            self._setup_matplotlib()
        else:
            self._setup_fallback()

    def _setup_matplotlib(self):
        """设置matplotlib图表"""
        layout = QVBoxLayout(self)

        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        # 创建子图
        self.ax1 = self.figure.add_subplot(211)  # 收益曲线
        self.ax2 = self.figure.add_subplot(212)  # 回撤曲线

        self.figure.tight_layout()

        # 数据存储
        self.dates = []
        self.returns = []
        self.drawdowns = []

    def _setup_fallback(self):
        """设置备用显示"""
        layout = QVBoxLayout(self)

        label = QLabel("图表功能需要matplotlib库支持")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        layout.addWidget(self.text_display)

    def update_data(self, portfolio_data: Dict[str, Any]):
        """更新图表数据"""
        if not MATPLOTLIB_AVAILABLE:
            # 更新文本显示
            text = f"""
实时数据:
总资产: {portfolio_data.get('total_assets', 0):.2f}
可用资金: {portfolio_data.get('available_cash', 0):.2f}
市值: {portfolio_data.get('market_value', 0):.2f}
总盈亏: {portfolio_data.get('total_profit_loss', 0):.2f}
盈亏比例: {portfolio_data.get('total_profit_loss_pct', 0):.2%}
更新时间: {datetime.now().strftime('%H:%M:%S')}
"""
            self.text_display.setText(text)
            return

        # 更新matplotlib图表
        current_time = datetime.now()
        self.dates.append(current_time)

        # 计算收益率
        total_return = portfolio_data.get('total_profit_loss_pct', 0) / 100
        self.returns.append(total_return)

        # 计算回撤（简化）
        if self.returns:
            peak = max(self.returns)
            drawdown = (total_return - peak) / peak if peak > 0 else 0
            self.drawdowns.append(drawdown)
        else:
            self.drawdowns.append(0)

        # 保持最近100个数据点
        if len(self.dates) > 100:
            self.dates = self.dates[-100:]
            self.returns = self.returns[-100:]
            self.drawdowns = self.drawdowns[-100:]

        # 更新图表
        self._update_charts()

    def _update_charts(self):
        """更新图表显示"""
        if not MATPLOTLIB_AVAILABLE or not self.dates:
            return

        # 清除旧图
        self.ax1.clear()
        self.ax2.clear()

        # 绘制收益曲线
        self.ax1.plot(self.dates, [r * 100 for r in self.returns], 'b-', linewidth=1)
        self.ax1.set_title('收益率曲线 (%)')
        self.ax1.grid(True, alpha=0.3)
        self.ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

        # 绘制回撤曲线
        self.ax2.fill_between(self.dates, [d * 100 for d in self.drawdowns], 0,
                              color='red', alpha=0.3)
        self.ax2.set_title('回撤曲线 (%)')
        self.ax2.grid(True, alpha=0.3)
        self.ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

        # 旋转x轴标签
        plt.setp(self.ax1.xaxis.get_majorticklabels(), rotation=45)
        plt.setp(self.ax2.xaxis.get_majorticklabels(), rotation=45)

        self.figure.tight_layout()
        self.canvas.draw()

class SignalMonitorWidget(QWidget):
    """信号监控组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

        # 信号历史
        self.signal_history = []

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("实时信号监控")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title_label)

        # 信号统计
        stats_group = QGroupBox("信号统计")
        stats_layout = QFormLayout(stats_group)

        self.total_signals_label = QLabel("0")
        self.buy_signals_label = QLabel("0")
        self.sell_signals_label = QLabel("0")
        self.last_signal_label = QLabel("无")

        stats_layout.addRow("总信号数:", self.total_signals_label)
        stats_layout.addRow("买入信号:", self.buy_signals_label)
        stats_layout.addRow("卖出信号:", self.sell_signals_label)
        stats_layout.addRow("最后信号:", self.last_signal_label)

        layout.addWidget(stats_group)

        # 信号列表
        list_group = QGroupBox("信号历史")
        list_layout = QVBoxLayout(list_group)

        self.signal_table = QTableWidget()
        self.signal_table.setColumnCount(6)
        self.signal_table.setHorizontalHeaderLabels([
            "时间", "策略", "股票", "信号", "价格", "强度"
        ])

        # 设置表格属性
        header = self.signal_table.horizontalHeader()
        header.setStretchLastSection(True)
        for i in range(5):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.signal_table.setSelectionBehavior(QTableWidget.SelectRows)

        list_layout.addWidget(self.signal_table)
        layout.addWidget(list_group)

    def add_signal(self, strategy_id: str, signal: Signal):
        """添加新信号"""
        self.signal_history.append({
            'timestamp': datetime.now(),
            'strategy_id': strategy_id,
            'signal': signal
        })

        # 保持最近100个信号
        if len(self.signal_history) > 100:
            self.signal_history = self.signal_history[-100:]

        self._update_display()

    def _update_display(self):
        """更新显示"""
        # 更新统计
        total_signals = len(self.signal_history)
        buy_signals = sum(1 for s in self.signal_history if s['signal'].signal_type == SignalType.BUY)
        sell_signals = sum(1 for s in self.signal_history if s['signal'].signal_type == SignalType.SELL)

        self.total_signals_label.setText(str(total_signals))
        self.buy_signals_label.setText(str(buy_signals))
        self.sell_signals_label.setText(str(sell_signals))

        if self.signal_history:
            last_signal = self.signal_history[-1]
            last_text = f"{last_signal['signal'].signal_type.value} {last_signal['signal'].symbol}"
            self.last_signal_label.setText(last_text)

        # 更新表格
        self.signal_table.setRowCount(len(self.signal_history))

        for row, signal_data in enumerate(reversed(self.signal_history)):
            timestamp = signal_data['timestamp']
            strategy_id = signal_data['strategy_id']
            signal = signal_data['signal']

            self.signal_table.setItem(row, 0, QTableWidgetItem(timestamp.strftime("%H:%M:%S")))
            self.signal_table.setItem(row, 1, QTableWidgetItem(strategy_id))
            self.signal_table.setItem(row, 2, QTableWidgetItem(signal.symbol))

            # 信号类型用颜色区分
            signal_item = QTableWidgetItem(signal.signal_type.value)
            if signal.signal_type == SignalType.BUY:
                signal_item.setBackground(QColor(144, 238, 144))  # 浅绿色
            elif signal.signal_type == SignalType.SELL:
                signal_item.setBackground(QColor(255, 182, 193))  # 浅红色

            self.signal_table.setItem(row, 3, signal_item)
            self.signal_table.setItem(row, 4, QTableWidgetItem(f"{signal.price:.2f}"))
            self.signal_table.setItem(row, 5, QTableWidgetItem(f"{signal.strength:.2f}"))

class OrderMonitorWidget(QWidget):
    """订单监控组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

        # 订单历史
        self.order_history = []

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("订单状态监控")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title_label)

        # 订单统计
        stats_group = QGroupBox("订单统计")
        stats_layout = QFormLayout(stats_group)

        self.total_orders_label = QLabel("0")
        self.executed_orders_label = QLabel("0")
        self.pending_orders_label = QLabel("0")
        self.failed_orders_label = QLabel("0")

        stats_layout.addRow("总订单数:", self.total_orders_label)
        stats_layout.addRow("已执行:", self.executed_orders_label)
        stats_layout.addRow("待执行:", self.pending_orders_label)
        stats_layout.addRow("失败:", self.failed_orders_label)

        layout.addWidget(stats_group)

        # 订单列表
        list_group = QGroupBox("订单历史")
        list_layout = QVBoxLayout(list_group)

        self.order_table = QTableWidget()
        self.order_table.setColumnCount(8)
        self.order_table.setHorizontalHeaderLabels([
            "时间", "订单ID", "策略", "股票", "操作", "数量", "价格", "状态"
        ])

        # 设置表格属性
        header = self.order_table.horizontalHeader()
        header.setStretchLastSection(True)
        for i in range(7):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.order_table.setSelectionBehavior(QTableWidget.SelectRows)

        list_layout.addWidget(self.order_table)
        layout.addWidget(list_group)

    def add_order(self, order: TradeRecord):
        """添加新订单"""
        self.order_history.append(order)

        # 保持最近100个订单
        if len(self.order_history) > 100:
            self.order_history = self.order_history[-100:]

        self._update_display()

    def update_order_status(self, trade_id: str, status: str):
        """更新订单状态"""
        for order in self.order_history:
            if order.trade_id == trade_id:
                order.status = status
                break

        self._update_display()

    def _update_display(self):
        """更新显示"""
        # 更新统计
        total_orders = len(self.order_history)
        executed_orders = sum(1 for o in self.order_history if o.status == 'executed')
        pending_orders = sum(1 for o in self.order_history if o.status == 'pending')
        failed_orders = sum(1 for o in self.order_history if o.status == 'failed')

        self.total_orders_label.setText(str(total_orders))
        self.executed_orders_label.setText(str(executed_orders))
        self.pending_orders_label.setText(str(pending_orders))
        self.failed_orders_label.setText(str(failed_orders))

        # 更新表格
        self.order_table.setRowCount(len(self.order_history))

        for row, order in enumerate(reversed(self.order_history)):
            self.order_table.setItem(row, 0, QTableWidgetItem(order.timestamp.strftime("%H:%M:%S")))
            self.order_table.setItem(row, 1, QTableWidgetItem(order.trade_id))
            self.order_table.setItem(row, 2, QTableWidgetItem(order.strategy_id or "手动"))
            self.order_table.setItem(row, 3, QTableWidgetItem(order.stock_code))

            # 操作类型用颜色区分
            action_item = QTableWidgetItem(order.action)
            if order.action == 'BUY':
                action_item.setBackground(QColor(144, 238, 144))  # 浅绿色
            elif order.action == 'SELL':
                action_item.setBackground(QColor(255, 182, 193))  # 浅红色

            self.order_table.setItem(row, 4, action_item)
            self.order_table.setItem(row, 5, QTableWidgetItem(str(order.quantity)))
            self.order_table.setItem(row, 6, QTableWidgetItem(f"{order.price:.2f}"))

            # 状态用颜色区分
            status_item = QTableWidgetItem(order.status)
            if order.status == 'executed':
                status_item.setBackground(QColor(144, 238, 144))  # 浅绿色
            elif order.status == 'failed':
                status_item.setBackground(QColor(255, 182, 193))  # 浅红色
            elif order.status == 'pending':
                status_item.setBackground(QColor(255, 255, 224))  # 浅黄色

            self.order_table.setItem(row, 7, status_item)

class PositionMonitorWidget(QWidget):
    """持仓监控组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("持仓监控")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title_label)

        # 持仓汇总
        summary_group = QGroupBox("持仓汇总")
        summary_layout = QFormLayout(summary_group)

        self.total_positions_label = QLabel("0")
        self.total_market_value_label = QLabel("0.00")
        self.total_pnl_label = QLabel("0.00")
        self.total_pnl_pct_label = QLabel("0.00%")

        summary_layout.addRow("持仓数量:", self.total_positions_label)
        summary_layout.addRow("总市值:", self.total_market_value_label)
        summary_layout.addRow("总盈亏:", self.total_pnl_label)
        summary_layout.addRow("盈亏比例:", self.total_pnl_pct_label)

        layout.addWidget(summary_group)

        # 持仓明细
        detail_group = QGroupBox("持仓明细")
        detail_layout = QVBoxLayout(detail_group)

        self.position_table = QTableWidget()
        self.position_table.setColumnCount(8)
        self.position_table.setHorizontalHeaderLabels([
            "股票代码", "数量", "成本价", "现价", "市值", "盈亏", "盈亏%", "更新时间"
        ])

        # 设置表格属性
        header = self.position_table.horizontalHeader()
        header.setStretchLastSection(True)
        for i in range(7):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.position_table.setSelectionBehavior(QTableWidget.SelectRows)

        detail_layout.addWidget(self.position_table)
        layout.addWidget(detail_group)

    def update_positions(self, portfolio: Portfolio):
        """更新持仓信息"""
        positions = portfolio.positions

        # 更新汇总信息
        self.total_positions_label.setText(str(len(positions)))
        self.total_market_value_label.setText(f"{portfolio.market_value:.2f}")
        self.total_pnl_label.setText(f"{portfolio.total_profit_loss:.2f}")
        self.total_pnl_pct_label.setText(f"{portfolio.total_profit_loss_pct:.2f}%")

        # 更新持仓明细
        self.position_table.setRowCount(len(positions))

        for row, position in enumerate(positions):
            self.position_table.setItem(row, 0, QTableWidgetItem(position.symbol))
            self.position_table.setItem(row, 1, QTableWidgetItem(str(position.quantity)))
            self.position_table.setItem(row, 2, QTableWidgetItem(f"{position.avg_price:.2f}"))
            self.position_table.setItem(row, 3, QTableWidgetItem(f"{position.current_price:.2f}"))
            self.position_table.setItem(row, 4, QTableWidgetItem(f"{position.market_value:.2f}"))

            # 盈亏用颜色区分
            pnl_item = QTableWidgetItem(f"{position.unrealized_pnl:.2f}")
            pnl_pct = (position.unrealized_pnl / (position.quantity * position.avg_price)) * 100 if position.quantity > 0 else 0
            pnl_pct_item = QTableWidgetItem(f"{pnl_pct:.2f}%")

            if position.unrealized_pnl > 0:
                pnl_item.setBackground(QColor(144, 238, 144))  # 浅绿色
                pnl_pct_item.setBackground(QColor(144, 238, 144))
            elif position.unrealized_pnl < 0:
                pnl_item.setBackground(QColor(255, 182, 193))  # 浅红色
                pnl_pct_item.setBackground(QColor(255, 182, 193))

            self.position_table.setItem(row, 5, pnl_item)
            self.position_table.setItem(row, 6, pnl_pct_item)
            self.position_table.setItem(row, 7, QTableWidgetItem(position.timestamp.strftime("%H:%M:%S")))

class RiskMonitorWidget(QWidget):
    """风险监控组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("风险指标监控")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title_label)

        # 风险指标
        risk_group = QGroupBox("风险指标")
        risk_layout = QFormLayout(risk_group)

        self.max_drawdown_label = QLabel("0.00%")
        self.var_label = QLabel("0.00")
        self.sharpe_ratio_label = QLabel("0.00")
        self.volatility_label = QLabel("0.00%")

        risk_layout.addRow("最大回撤:", self.max_drawdown_label)
        risk_layout.addRow("VaR (95%):", self.var_label)
        risk_layout.addRow("夏普比率:", self.sharpe_ratio_label)
        risk_layout.addRow("波动率:", self.volatility_label)

        layout.addWidget(risk_group)

        # 风险限制
        limit_group = QGroupBox("风险限制")
        limit_layout = QFormLayout(limit_group)

        self.position_limit_label = QLabel("10")
        self.single_position_limit_label = QLabel("30%")
        self.daily_loss_limit_label = QLabel("5%")
        self.leverage_ratio_label = QLabel("1.0")

        limit_layout.addRow("最大持仓数:", self.position_limit_label)
        limit_layout.addRow("单仓位限制:", self.single_position_limit_label)
        limit_layout.addRow("日损失限制:", self.daily_loss_limit_label)
        limit_layout.addRow("杠杆比例:", self.leverage_ratio_label)

        layout.addWidget(limit_group)

        # 风险警告
        warning_group = QGroupBox("风险警告")
        warning_layout = QVBoxLayout(warning_group)

        self.warning_list = QListWidget()
        warning_layout.addWidget(self.warning_list)

        layout.addWidget(warning_group)

        layout.addStretch()

    def update_risk_metrics(self, portfolio: Portfolio, performance_stats: Dict[str, Any]):
        """更新风险指标"""
        # 计算风险指标（简化计算）
        total_assets = portfolio.total_assets
        initial_assets = Decimal('100000')  # 假设初始资金

        # 最大回撤（简化）
        current_return = (total_assets - initial_assets) / initial_assets
        max_drawdown = min(0, current_return) * 100
        self.max_drawdown_label.setText(f"{max_drawdown:.2f}%")

        # 夏普比率（简化）
        sharpe_ratio = current_return / 0.1 if current_return != 0 else 0  # 假设无风险利率为0，标准差为0.1
        self.sharpe_ratio_label.setText(f"{sharpe_ratio:.2f}")

        # 波动率（简化）
        volatility = abs(current_return) * 100
        self.volatility_label.setText(f"{volatility:.2f}%")

        # VaR（简化）
        var_95 = total_assets * Decimal('0.05')  # 假设95% VaR为总资产的5%
        self.var_label.setText(f"{var_95:.2f}")

        # 检查风险警告
        self._check_risk_warnings(portfolio, performance_stats)

    def _check_risk_warnings(self, portfolio: Portfolio, performance_stats: Dict[str, Any]):
        """检查风险警告"""
        warnings = []

        # 检查持仓数量
        if len(portfolio.positions) > 10:
            warnings.append("持仓数量超过限制")

        # 检查单仓位比例
        total_value = portfolio.total_assets
        for position in portfolio.positions:
            position_pct = (position.market_value / total_value) * 100 if total_value > 0 else 0
            if position_pct > 30:
                warnings.append(f"{position.symbol} 仓位过重 ({position_pct:.1f}%)")

        # 检查日损失
        daily_pnl_pct = portfolio.total_profit_loss_pct
        if daily_pnl_pct < -5:
            warnings.append(f"日损失超限 ({daily_pnl_pct:.1f}%)")

        # 检查可用资金
        cash_ratio = (portfolio.available_cash / portfolio.total_assets) * 100 if portfolio.total_assets > 0 else 0
        if cash_ratio < 5:
            warnings.append(f"可用资金不足 ({cash_ratio:.1f}%)")

        # 更新警告列表
        self.warning_list.clear()
        for warning in warnings:
            item = QListWidgetItem(warning)
            item.setBackground(QColor(255, 182, 193))  # 浅红色背景
            self.warning_list.addItem(item)

        if not warnings:
            item = QListWidgetItem("无风险警告")
            item.setBackground(QColor(144, 238, 144))  # 浅绿色背景
            self.warning_list.addItem(item)

class PerformanceAnalysisWidget(QWidget):
    """性能分析组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("性能分析")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title_label)

        # 创建选项卡
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        # 收益分析选项卡
        self._create_return_analysis_tab(tab_widget)

        # 交易分析选项卡
        self._create_trade_analysis_tab(tab_widget)

        # 策略对比选项卡
        self._create_strategy_comparison_tab(tab_widget)

    def _create_return_analysis_tab(self, tab_widget):
        """创建收益分析选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 收益指标
        metrics_group = QGroupBox("收益指标")
        metrics_layout = QFormLayout(metrics_group)

        self.total_return_label = QLabel("0.00%")
        self.annual_return_label = QLabel("0.00%")
        self.monthly_return_label = QLabel("0.00%")
        self.daily_return_label = QLabel("0.00%")

        metrics_layout.addRow("总收益率:", self.total_return_label)
        metrics_layout.addRow("年化收益率:", self.annual_return_label)
        metrics_layout.addRow("月收益率:", self.monthly_return_label)
        metrics_layout.addRow("日收益率:", self.daily_return_label)

        layout.addWidget(metrics_group)

        # 收益曲线图
        chart_group = QGroupBox("收益曲线")
        chart_layout = QVBoxLayout(chart_group)

        self.return_chart = RealTimeChart()
        chart_layout.addWidget(self.return_chart)

        layout.addWidget(chart_group)

        tab_widget.addTab(tab, "收益分析")

    def _create_trade_analysis_tab(self, tab_widget):
        """创建交易分析选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 交易统计
        stats_group = QGroupBox("交易统计")
        stats_layout = QFormLayout(stats_group)

        self.total_trades_label = QLabel("0")
        self.win_trades_label = QLabel("0")
        self.lose_trades_label = QLabel("0")
        self.win_rate_label = QLabel("0.00%")
        self.avg_win_label = QLabel("0.00")
        self.avg_lose_label = QLabel("0.00")
        self.profit_factor_label = QLabel("0.00")

        stats_layout.addRow("总交易数:", self.total_trades_label)
        stats_layout.addRow("盈利交易:", self.win_trades_label)
        stats_layout.addRow("亏损交易:", self.lose_trades_label)
        stats_layout.addRow("胜率:", self.win_rate_label)
        stats_layout.addRow("平均盈利:", self.avg_win_label)
        stats_layout.addRow("平均亏损:", self.avg_lose_label)
        stats_layout.addRow("盈亏比:", self.profit_factor_label)

        layout.addWidget(stats_group)

        # 交易分布
        distribution_group = QGroupBox("交易分布")
        distribution_layout = QVBoxLayout(distribution_group)

        self.trade_distribution_text = QTextEdit()
        self.trade_distribution_text.setReadOnly(True)
        self.trade_distribution_text.setMaximumHeight(200)

        distribution_layout.addWidget(self.trade_distribution_text)
        layout.addWidget(distribution_group)

        tab_widget.addTab(tab, "交易分析")

    def _create_strategy_comparison_tab(self, tab_widget):
        """创建策略对比选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 策略选择
        selection_group = QGroupBox("策略选择")
        selection_layout = QHBoxLayout(selection_group)

        self.strategy_checkboxes = {}

        # 这里可以动态添加策略选择框
        layout.addWidget(selection_group)

        # 对比表格
        comparison_group = QGroupBox("策略对比")
        comparison_layout = QVBoxLayout(comparison_group)

        self.comparison_table = QTableWidget()
        self.comparison_table.setColumnCount(6)
        self.comparison_table.setHorizontalHeaderLabels([
            "策略", "总收益", "夏普比率", "最大回撤", "胜率", "交易次数"
        ])

        comparison_layout.addWidget(self.comparison_table)
        layout.addWidget(comparison_group)

        tab_widget.addTab(tab, "策略对比")

    def update_performance_data(self, portfolio: Portfolio, trade_history: List[TradeRecord]):
        """更新性能数据"""
        # 更新收益指标
        initial_capital = Decimal('100000')  # 假设初始资金
        total_return = (portfolio.total_assets - initial_capital) / initial_capital * 100

        self.total_return_label.setText(f"{total_return:.2f}%")

        # 简化的年化收益率计算
        days_elapsed = 30  # 假设运行了30天
        annual_return = (total_return / days_elapsed) * 365 if days_elapsed > 0 else 0
        self.annual_return_label.setText(f"{annual_return:.2f}%")

        # 更新收益曲线
        portfolio_data = {
            'total_assets': portfolio.total_assets,
            'available_cash': portfolio.available_cash,
            'market_value': portfolio.market_value,
            'total_profit_loss': portfolio.total_profit_loss,
            'total_profit_loss_pct': portfolio.total_profit_loss_pct
        }
        self.return_chart.update_data(portfolio_data)

        # 更新交易统计
        if trade_history:
            total_trades = len(trade_history)
            win_trades = sum(1 for t in trade_history if t.action == 'SELL' and hasattr(t, 'profit') and t.profit > 0)
            lose_trades = total_trades - win_trades
            win_rate = (win_trades / total_trades) * 100 if total_trades > 0 else 0

            self.total_trades_label.setText(str(total_trades))
            self.win_trades_label.setText(str(win_trades))
            self.lose_trades_label.setText(str(lose_trades))
            self.win_rate_label.setText(f"{win_rate:.2f}%")

            # 交易分布分析
            distribution_text = f"""
交易时间分布:
- 上午 (09:30-11:30): {sum(1 for t in trade_history if 9 <= t.timestamp.hour < 12)} 笔
- 下午 (13:00-15:00): {sum(1 for t in trade_history if 13 <= t.timestamp.hour < 15)} 笔
- 其他时间: {sum(1 for t in trade_history if t.timestamp.hour < 9 or t.timestamp.hour >= 15)} 笔

交易类型分布:
- 买入: {sum(1 for t in trade_history if t.action == 'BUY')} 笔
- 卖出: {sum(1 for t in trade_history if t.action == 'SELL')} 笔
"""
            self.trade_distribution_text.setText(distribution_text)

class EnhancedTradingMonitorWidget(QWidget):
    """增强交易监控组件"""

    # 信号
    signal_received = pyqtSignal(str, object)  # 策略ID, Signal对象
    order_executed = pyqtSignal(object)        # TradeRecord对象
    position_updated = pyqtSignal(object)      # Portfolio对象

    def __init__(self, parent=None, trading_service=None, strategy_service=None):
        """
        初始化增强交易监控组件

        Args:
            parent: 父组件
            trading_service: 交易服务
            strategy_service: 策略服务
        """
        super().__init__(parent)
        self.trading_service = trading_service
        self.strategy_service = strategy_service

        self._setup_ui()
        self._setup_timers()

        # 连接服务事件（如果服务支持事件）
        self._connect_service_events()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 创建选项卡
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # 实时监控选项卡
        self._create_realtime_monitor_tab()

        # 信号监控选项卡
        self._create_signal_monitor_tab()

        # 订单监控选项卡
        self._create_order_monitor_tab()

        # 持仓监控选项卡
        self._create_position_monitor_tab()

        # 风险监控选项卡
        self._create_risk_monitor_tab()

        # 性能分析选项卡
        self._create_performance_analysis_tab()

    def _create_realtime_monitor_tab(self):
        """创建实时监控选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 总览面板
        overview_group = QGroupBox("交易总览")
        overview_layout = QGridLayout(overview_group)

        # 资产信息
        self.total_assets_label = QLabel("100,000.00")
        self.available_cash_label = QLabel("100,000.00")
        self.market_value_label = QLabel("0.00")
        self.total_pnl_label = QLabel("0.00")

        overview_layout.addWidget(QLabel("总资产:"), 0, 0)
        overview_layout.addWidget(self.total_assets_label, 0, 1)
        overview_layout.addWidget(QLabel("可用资金:"), 0, 2)
        overview_layout.addWidget(self.available_cash_label, 0, 3)
        overview_layout.addWidget(QLabel("市值:"), 1, 0)
        overview_layout.addWidget(self.market_value_label, 1, 1)
        overview_layout.addWidget(QLabel("总盈亏:"), 1, 2)
        overview_layout.addWidget(self.total_pnl_label, 1, 3)

        layout.addWidget(overview_group)

        # 活跃策略
        strategy_group = QGroupBox("活跃策略")
        strategy_layout = QVBoxLayout(strategy_group)

        self.active_strategy_list = QListWidget()
        strategy_layout.addWidget(self.active_strategy_list)

        layout.addWidget(strategy_group)

        # 实时图表
        chart_group = QGroupBox("实时图表")
        chart_layout = QVBoxLayout(chart_group)

        self.realtime_chart = RealTimeChart()
        chart_layout.addWidget(self.realtime_chart)

        layout.addWidget(chart_group)

        self.tab_widget.addTab(tab, "实时监控")

    def _create_signal_monitor_tab(self):
        """创建信号监控选项卡"""
        self.signal_monitor = SignalMonitorWidget()
        self.tab_widget.addTab(self.signal_monitor, "信号监控")

    def _create_order_monitor_tab(self):
        """创建订单监控选项卡"""
        self.order_monitor = OrderMonitorWidget()
        self.tab_widget.addTab(self.order_monitor, "订单监控")

    def _create_position_monitor_tab(self):
        """创建持仓监控选项卡"""
        self.position_monitor = PositionMonitorWidget()
        self.tab_widget.addTab(self.position_monitor, "持仓监控")

    def _create_risk_monitor_tab(self):
        """创建风险监控选项卡"""
        self.risk_monitor = RiskMonitorWidget()
        self.tab_widget.addTab(self.risk_monitor, "风险监控")

    def _create_performance_analysis_tab(self):
        """创建性能分析选项卡"""
        self.performance_analysis = PerformanceAnalysisWidget()
        self.tab_widget.addTab(self.performance_analysis, "性能分析")

    def _setup_timers(self):
        """设置定时器"""
        # 数据更新定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_all_data)
        self.update_timer.start(2000)  # 每2秒更新一次

        # 图表更新定时器
        self.chart_timer = QTimer()
        self.chart_timer.timeout.connect(self._update_charts)
        self.chart_timer.start(5000)  # 每5秒更新一次图表

    def _connect_service_events(self):
        """连接服务事件"""
        # 这里可以连接交易服务和策略服务的事件
        # 由于当前服务没有直接的PyQt信号，我们使用定时器轮询
        pass

    def _update_all_data(self):
        """更新所有数据"""
        if not self.trading_service:
            return

        try:
            # 获取投资组合信息
            portfolio = self.trading_service.get_portfolio()

            if portfolio is None:
                return

            # 更新总览信息
            self.total_assets_label.setText(f"{portfolio.total_assets:,.2f}")
            self.available_cash_label.setText(f"{portfolio.available_cash:,.2f}")
            self.market_value_label.setText(f"{portfolio.market_value:,.2f}")

            # 设置盈亏颜色
            if portfolio.total_profit_loss > 0:
                self.total_pnl_label.setStyleSheet("color: green; font-weight: bold;")
                self.total_pnl_label.setText(f"+{portfolio.total_profit_loss:,.2f}")
            elif portfolio.total_profit_loss < 0:
                self.total_pnl_label.setStyleSheet("color: red; font-weight: bold;")
                self.total_pnl_label.setText(f"{portfolio.total_profit_loss:,.2f}")
            else:
                self.total_pnl_label.setStyleSheet("color: black;")
                self.total_pnl_label.setText("0.00")

            # 更新活跃策略列表
            self._update_active_strategies()

            # 更新持仓监控
            self.position_monitor.update_positions(portfolio)

            # 获取交易历史
            trade_history = self.trading_service.get_trade_history(limit=100)

            # 更新性能分析
            self.performance_analysis.update_performance_data(portfolio, trade_history)

            # 更新风险监控
            performance_stats = self.trading_service.get_performance_stats()
            self.risk_monitor.update_risk_metrics(portfolio, performance_stats)

        except Exception as e:
            logger.error(f"更新数据失败: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")

    def _update_active_strategies(self):
        """更新活跃策略列表"""
        if not self.trading_service:
            return

        try:
            # 获取性能统计
            stats = self.trading_service.get_performance_stats()
            active_strategies = stats.get('active_strategies', 0)
            total_strategies = stats.get('total_strategies', 0)

            # 清空列表
            self.active_strategy_list.clear()

            # 添加统计信息
            summary_item = QListWidgetItem(f"活跃策略: {active_strategies}/{total_strategies}")
            summary_item.setBackground(QColor(240, 240, 240))
            self.active_strategy_list.addItem(summary_item)

            # 这里可以添加具体的策略状态信息
            # 由于当前架构限制，我们显示简化信息
            if active_strategies > 0:
                for i in range(min(active_strategies, 5)):  # 最多显示5个
                    strategy_item = QListWidgetItem(f"策略 #{i+1} - 运行中")
                    strategy_item.setBackground(QColor(144, 238, 144))
                    self.active_strategy_list.addItem(strategy_item)

        except Exception as e:
            logger.error(f"更新活跃策略失败: {e}")

    def _update_charts(self):
        """更新图表"""
        if not self.trading_service:
            return

        try:
            # 获取投资组合信息
            portfolio = self.trading_service.get_portfolio()

            # 更新实时图表
            portfolio_data = {
                'total_assets': portfolio.total_assets,
                'available_cash': portfolio.available_cash,
                'market_value': portfolio.market_value,
                'total_profit_loss': portfolio.total_profit_loss,
                'total_profit_loss_pct': portfolio.total_profit_loss_pct
            }

            self.realtime_chart.update_data(portfolio_data)

        except Exception as e:
            logger.error(f"更新图表失败: {e}")

    # 公共接口方法
    def add_signal(self, strategy_id: str, signal: Signal):
        """添加新信号"""
        self.signal_monitor.add_signal(strategy_id, signal)
        self.signal_received.emit(strategy_id, signal)

    def add_order(self, order: TradeRecord):
        """添加新订单"""
        self.order_monitor.add_order(order)
        self.order_executed.emit(order)

    def update_order_status(self, trade_id: str, status: str):
        """更新订单状态"""
        self.order_monitor.update_order_status(trade_id, status)

    def get_current_portfolio(self) -> Optional[Portfolio]:
        """获取当前投资组合"""
        if self.trading_service:
            return self.trading_service.get_portfolio()
        return None

    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        if not self.trading_service:
            return {}

        try:
            portfolio = self.trading_service.get_portfolio()
            stats = self.trading_service.get_performance_stats()

            return {
                'total_assets': portfolio.total_assets,
                'total_pnl': portfolio.total_profit_loss,
                'total_pnl_pct': portfolio.total_profit_loss_pct,
                'active_strategies': stats.get('active_strategies', 0),
                'total_signals': stats.get('total_signals', 0),
                'successful_trades': stats.get('successful_trades', 0),
                'failed_trades': stats.get('failed_trades', 0)
            }

        except Exception as e:
            logger.error(f"获取性能摘要失败: {e}")
            return {}

    def closeEvent(self, event):
        """关闭事件"""
        # 停止定时器
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        if hasattr(self, 'chart_timer'):
            self.chart_timer.stop()

        super().closeEvent(event)
        event.accept()

# 测试代码
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 创建测试窗口
    widget = EnhancedTradingMonitorWidget()
    widget.show()

    sys.exit(app.exec_())
