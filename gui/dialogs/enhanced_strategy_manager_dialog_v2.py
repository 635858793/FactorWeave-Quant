"""
增强策略管理对话框 V2 - 对标行业软件，集成系统主题管理
提供：
1. 现代化UI布局（Tab切换）
2. 系统主题集成
3. 行业标准图表配色
4. 实时状态反馈
5. 后端API正确连接
"""

from loguru import logger
import asyncio
import json
import time
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import asdict
import pandas as pd
import numpy as np
from enum import Enum

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QLabel, QTextEdit, QLineEdit,
    QGroupBox, QFormLayout, QPushButton, QScrollArea, QSplitter,
    QHeaderView, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QFileDialog, QMessageBox, QProgressDialog, QInputDialog,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QProgressBar, QFrame, QGridLayout, QSlider, QDateEdit,
    QApplication, QMenu, QAction, QSizePolicy, QToolButton,
    QStackedWidget, QButtonGroup
)
from PyQt5.QtCore import QObject, Qt, pyqtSignal, QThread, QTimer, QDateTime, QThreadPool, QRunnable, QMetaObject, Q_ARG, QSettings, QMimeData
from PyQt5.QtGui import QFont, QPixmap, QIcon, QColor, QPalette, QPainter, QBrush, QDrag

# 导入服务和数据结构
from core.services.strategy_service import StrategyService, StrategyConfig, BacktestStatus, OptimizationStatus
from core.services.trading_service import TradingService, StrategyState
from core.strategy_extensions import (
    StrategyContext, StandardMarketData, TimeFrame, AssetType,
    StrategyType, RiskLevel, ParameterDef, PerformanceMetrics
)

# 导入服务
from core.services.strategy_service import StrategyService, StrategyConfig, BacktestStatus, OptimizationStatus
from core.services.trading_service import TradingService, StrategyState
from core.services.unified_data_manager import UnifiedDataManager

# 导入系统主题管理器
from utils.theme import get_theme_manager, Theme
from core.events.event_bus import get_event_bus
from core.events.types import ThemeChangedEvent
from core.events import (
    StrategyStartedEvent, StrategyStoppedEvent, StrategyErrorEvent,
    SignalGeneratedEvent, EventType, EventPriority, EventFilter,
    get_event_bus
)

# 导入图表库（带错误处理）
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    from utils.matplotlib_font_config import configure_matplotlib_chinese_font
    configure_matplotlib_chinese_font()
    MATPLOTLIB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"matplotlib 不可用: {e}")
    MATPLOTLIB_AVAILABLE = False

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"plotly 不可用: {e}")
    PLOTLY_AVAILABLE = False

# 行业标准金融配色
FINANCIAL_COLORS = {
    'primary': '#2962FF',      # 蓝色 - 主线
    'profit': '#10B981',       # 绿色 - 收益
    'loss': '#EF4444',         # 红色 - 亏损
    'warning': '#F59E0B',       # 橙色 - 警告
    'auxiliary_1': '#8B5CF6', # 紫色 - 辅助
    'auxiliary_2': '#EC4899', # 粉色 - 辅助
    'auxiliary_3': '#06B6D4', # 青色 - 辅助
    'auxiliary_4': '#F59E0B', # 橙色 - 辅助
}

# 状态指示器颜色（语义化）
STATUS_COLORS = {
    'running': '#10B981',  # 绿色
    'configured': '#3B82F6',  # 蓝色
    'error': '#EF4444',  # 红色
    'stopped': '#6B7280'  # 灰色
}

# 性能指标卡片渐变色
METRIC_CARD_GRADIENTS = {
    'return': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #10B981, stop:1 #059669)',
    'sharpe': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3B82F6, stop:1 #1E40AF)',
    'drawdown': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EF4444, stop:1 #B91C1C)',
    'win_rate': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706)'
}

class EnhancedStrategyManagerDialogV2(QDialog):
    """增强策略管理对话框 V2 - 对标行业软件，集成系统主题管理"""

    # 信号
    strategy_selected = pyqtSignal(str)  # 策略ID
    strategy_started = pyqtSignal(str)   # 策略ID
    strategy_stopped = pyqtSignal(str)   # 策略ID

    def __init__(self, parent=None, strategy_service=None, trading_service=None):
        """
        初始化增强策略管理对话框 V2

        Args:
            parent: 父窗口
            strategy_service: 策略服务（已弃用，建议使用服务容器）
            trading_service: 交易服务（已弃用，建议使用服务容器）
        """
        super().__init__(parent)

        # 获取系统主题管理器
        self.theme_manager = get_theme_manager()
        
        # 初始化服务容器（如果提供了服务，使用依赖注入）
        self._setup_services(strategy_service, trading_service)

        self.current_strategy_id = None
        self.current_view = 'home'  # 当前视图
        
        # 缓存图表引用，避免频繁查找
        self._cached_charts = []
        
        # 设置窗口属性
        self.setWindowTitle("策略管理器")
        self.setModal(False)  # 非模态对话框，允许与主窗口交互
        self.resize(1600, 1000)

        # 监听主题变化
        self.theme_manager.theme_changed.connect(self._on_theme_changed)

        # 创建UI
        self._setup_ui()
        
        # 应用系统主题
        self.theme_manager.apply_theme(self)
        
        # 加载策略数据
        self._load_strategies()

    def _setup_services(self, strategy_service=None, trading_service=None):
        """设置服务依赖注入"""
        # 如果提供了服务实例，直接使用（向后兼容）
        if strategy_service:
            self.strategy_service = strategy_service
        else:
            # 使用服务容器获取服务实例
            try:
                from core.containers.service_container import get_service_container
                container = get_service_container()
                self.strategy_service = container.resolve(StrategyService)
            except Exception as e:
                logger.warning(f"无法从服务容器获取StrategyService: {e}")
                self.strategy_service = None

        if trading_service:
            self.trading_service = trading_service
        else:
            # 使用服务容器获取服务实例
            try:
                from core.containers.service_container import get_service_container
                container = get_service_container()
                self.trading_service = container.resolve(TradingService)
            except Exception as e:
                logger.warning(f"无法从服务容器获取TradingService: {e}")
                self.trading_service = None

        logger.info(f"策略服务初始化完成: {self.strategy_service is not None}")
        logger.info(f"交易服务初始化完成: {self.trading_service is not None}")
        
        # 初始化策略事件处理器
        self._strategy_event_handler = None
        self._subscribe_strategy_events()

    def _subscribe_strategy_events(self):
        """订阅策略事件"""
        try:
            from core.events.event_bus import EventBus
            event_bus = get_event_bus()
            def strategy_event_handler(event):
                try:
                    if hasattr(self, '_on_strategy_event'):
                        self._on_strategy_event(event)
                except Exception as e:
                    pass

            event_bus.subscribe(StrategyStartedEvent, strategy_event_handler, priority=0)
            event_bus.subscribe(StrategyStoppedEvent, strategy_event_handler, priority=0)
            event_bus.subscribe(SignalGeneratedEvent, strategy_event_handler, priority=0)
            event_bus.subscribe(StrategyErrorEvent, strategy_event_handler, priority=0)
            logger.info("策略事件订阅已注册")
        except Exception as e:
            logger.warning(f"注册策略事件订阅失败: {e}")
    
    def _on_strategy_event(self, event):
        """处理策略事件"""
        try:
            
            if isinstance(event, StrategyStartedEvent):
                logger.info(f"策略启动事件: {event.strategy_id}")
                self._update_strategy_status(event.strategy_id, "running")
                
            elif isinstance(event, StrategyStoppedEvent):
                logger.info(f"策略停止事件: {event.strategy_id}, 原因: {event.reason}")
                self._update_strategy_status(event.strategy_id, "stopped")
                if event.performance:
                    self._show_performance_notification(event.performance)
                    
            elif isinstance(event, SignalGeneratedEvent):
                if hasattr(event, 'signals') and event.signals:
                    signal_count = len(event.signals)
                    logger.info(f"信号生成事件: {event.strategy_id}, 信号数: {signal_count}")
                    self._update_signal_counter(signal_count)
                    
            elif isinstance(event, StrategyErrorEvent):
                logger.error(f"策略错误事件: {event.strategy_id}, 错误: {event.error_message}")
                self._show_error_notification(event.strategy_id, event.error_message)
                
        except Exception as e:
            logger.error(f"处理策略事件失败: {e}")
    
    def _update_strategy_status(self, strategy_id: str, status: str):
        """更新策略状态显示"""
        if status == "running":
            self.backtest_status_label.setText(f"回测运行中: {strategy_id}")
            self.backtest_progress_bar.setRange(0, 0)
        elif status == "stopped":
            self.backtest_status_label.setText(f"回测完成: {strategy_id}")
            self.backtest_progress_bar.setRange(0, 100)
            self.backtest_progress_bar.setValue(100)
            self._reset_backtest_ui()
    
    def _show_performance_notification(self, performance):
        """显示性能通知"""
        try:
            if performance:
                value_label = self.total_return_card.findChild(QLabel, "value_label")
                if value_label:
                    total_return = performance.total_return
                    if hasattr(total_return, 'iloc'):
                        total_return = float(total_return.iloc[0]) if len(total_return) > 0 else 0.0
                    elif total_return is not None:
                        total_return = float(total_return)
                    else:
                        total_return = 0.0
                    value_label.setText(f"{total_return*100:.2f}%")

                value_label = self.sharpe_ratio_card.findChild(QLabel, "value_label")
                if value_label:
                    sharpe = performance.sharpe_ratio
                    if hasattr(sharpe, 'iloc'):
                        sharpe = float(sharpe.iloc[0]) if len(sharpe) > 0 else 0.0
                    elif sharpe is not None:
                        sharpe = float(sharpe)
                    else:
                        sharpe = 0.0
                    value_label.setText(f"{sharpe:.2f}")

                value_label = self.max_drawdown_card.findChild(QLabel, "value_label")
                if value_label:
                    drawdown = performance.max_drawdown
                    if hasattr(drawdown, 'iloc'):
                        drawdown = float(drawdown.iloc[0]) if len(drawdown) > 0 else 0.0
                    elif drawdown is not None:
                        drawdown = float(drawdown)
                    else:
                        drawdown = 0.0
                    value_label.setText(f"{drawdown*100:.2f}%")

                value_label = self.win_rate_card.findChild(QLabel, "value_label")
                if value_label:
                    win_rate = performance.win_rate
                    if hasattr(win_rate, 'iloc'):
                        win_rate = float(win_rate.iloc[0]) if len(win_rate) > 0 else 0.0
                    elif win_rate is not None:
                        win_rate = float(win_rate)
                    else:
                        win_rate = 0.0
                    value_label.setText(f"{win_rate*100:.1f}%")
        except Exception as e:
            logger.warning(f"更新性能指标失败: {e}")
    
    def _update_signal_counter(self, count: int):
        """更新信号计数器"""
        self.backtest_status_label.setText(f"已生成 {count} 个交易信号")
    
    def _show_error_notification(self, strategy_id: str, error: str):
        """显示错误通知"""
        self.backtest_status_label.setText(f"错误: {error}")
        self.backtest_progress_bar.setRange(0, 100)
        self._reset_backtest_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 创建顶部导航栏
        nav_bar = self._create_navigation_bar()
        layout.addWidget(nav_bar)
        
        # 创建主内容区（StackedWidget）
        self.content_stack = QStackedWidget()
        layout.addWidget(self.content_stack)
        
        # 创建各个视图
        self._create_views()
        
        # 默认显示首页
        self._switch_view('home')

    def _create_navigation_bar(self) -> QWidget:
        """创建导航栏"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 导航按钮组
        self.nav_button_group = QButtonGroup(self)
        self.nav_buttons = []
        
        nav_items = [
            ('🏠 首页', 'home'),
            ('📋 策略库', 'library'),
            ('🔬 回测实验室', 'backtest'),
            ('⚙️ 参数优化', 'optimization'),
            ('📊 性能分析', 'performance')
        ]
        
        for text, name in nav_items:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, n=name: self._switch_view(n))
            btn.setAutoExclusive(True)
            
            # 设置按钮样式
            btn.setObjectName("nav_button")
            
            self.nav_button_group.addButton(btn)
            layout.addWidget(btn)
            self.nav_buttons.append(btn)
        
        # 默认选中首页
        self.nav_buttons[0].setChecked(True)
        
        # 添加弹性空间
        layout.addStretch()
        
        return widget

    def _create_views(self):
        """创建各个视图"""
        # 首页视图
        self.home_view = self._create_home_view()
        self.content_stack.addWidget(self.home_view)
        
        # 策略库视图
        self.library_view = self._create_library_view()
        self.content_stack.addWidget(self.library_view)
        
        # 回测实验室视图
        self.backtest_view = self._create_backtest_view()
        self.content_stack.addWidget(self.backtest_view)
        
        # 参数优化视图
        self.optimization_view = self._create_optimization_view()
        self.content_stack.addWidget(self.optimization_view)
        
        # 性能分析视图
        self.performance_view = self._create_performance_view()
        self.content_stack.addWidget(self.performance_view)

    def _create_home_view(self) -> QWidget:
        """创建首页视图"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 统计卡片区域
        stats_layout = QHBoxLayout()
        
        # 策略总数卡片
        total_card = self._create_stat_card("策略总数", "25", FINANCIAL_COLORS['primary'])
        stats_layout.addWidget(total_card)
        
        # 运行中卡片
        running_card = self._create_stat_card("运行中", "5", STATUS_COLORS['running'])
        stats_layout.addWidget(running_card)
        
        # 已配置卡片
        configured_card = self._create_stat_card("已配置", "18", STATUS_COLORS['configured'])
        stats_layout.addWidget(configured_card)
        
        # 错误卡片
        error_card = self._create_stat_card("错误", "2", STATUS_COLORS['error'])
        stats_layout.addWidget(error_card)
        
        layout.addLayout(stats_layout)
        
        # 性能趋势图
        trend_group = QGroupBox("性能趋势（最近30天）")
        trend_layout = QVBoxLayout(trend_group)
        
        if MATPLOTLIB_AVAILABLE:
            self.trend_chart = self._create_trend_chart()
            trend_layout.addWidget(self.trend_chart)
        else:
            trend_layout.addWidget(QLabel("图表功能需要安装 matplotlib 库"))
        
        layout.addWidget(trend_group)
        
        # 策略排行榜
        ranking_group = QGroupBox("策略性能排行榜")
        ranking_layout = QVBoxLayout(ranking_group)
        
        self.ranking_table = self._create_ranking_table()
        ranking_layout.addWidget(self.ranking_table)
        
        layout.addWidget(ranking_group)
        
        return widget

    def _create_stat_card(self, title: str, value: str, color: str) -> QWidget:
        """创建统计卡片"""
        card = QWidget()
        card.setFixedHeight(120)
        card.setFixedWidth(200)
        
        # 自定义样式（不使用系统主题）
        # card.setStyleSheet(f"""
        #     QWidget {{
        #         background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
        #             stop:0 rgba(41, 98, 255, 0.1), 
        #             stop:1 rgba(41, 98, 255, 0.2));
        #         border-radius: 8px;
        #         border: 1px solid rgba(41, 98, 255, 0.3);
        #     }}
        #     QLabel {{
        #         color: #FFFFFF;
        #         font-size: 12px;
        #         font-weight: bold;
        #     }}
        #     .value_label {{
        #         color: #FFFFFF;
        #         font-size: 24px;
        #         font-weight: bold;
        #     }}
        # """)
        
        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignCenter)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: rgba(155, 215, 55, 0.8); font-size: 22px;")
        
        value_label = QLabel(value, alignment=Qt.AlignCenter)
        value_label.setStyleSheet("font-size: 15px;")
        value_label.setObjectName("value_label")
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        return card

    def _create_trend_chart(self) -> QWidget:
        """创建性能趋势图（使用系统主题背景，自定义金融配色）"""
        widget = FigureCanvas(Figure(figsize=(10, 4)))
        
        # 缓存图表引用
        self._cached_charts.append(widget)
        
        # 应用系统主题到图表背景
        self.theme_manager.apply_chart_theme(widget.figure)
        
        ax = widget.figure.add_subplot(111)
        ax.set_title("性能趋势（最近30天）", fontsize=12, fontweight='bold')
        ax.set_xlabel("日期", fontsize=10)
        ax.set_ylabel("收益率 (%)", fontsize=10)
        ax.grid(True, alpha=0.3)
        
        # 获取真实数据
        dates = []
        returns = []
        
        if self.strategy_service:
            try:
                # 获取所有策略配置
                strategies = self.strategy_service.get_all_strategy_configs()
                
                # 获取每个策略的最新回测结果
                for strategy in strategies:
                    # 获取该策略的所有回测任务
                    strategy_backtests = []
                    for task_id, task in self.strategy_service._backtest_tasks.items():
                        if (task.strategy_config.strategy_id == strategy.strategy_id and 
                            task.status.value == 'completed' and
                            task.result):
                            strategy_backtests.append(task)
                    
                    # 按完成时间排序
                    strategy_backtests.sort(key=lambda t: t.completed_at if t.completed_at else datetime.min)
                    
                    # 提取最近30天的数据
                    thirty_days_ago = datetime.now() - timedelta(days=30)
                    for task in strategy_backtests:
                        if task.completed_at and task.completed_at >= thirty_days_ago:
                            dates.append(task.completed_at)
                            if task.result:
                                returns.append(task.result.total_return * 100)  # 转换为百分比
            except Exception as e:
                logger.error(f"获取性能趋势数据失败: {e}")
        
        # 如果没有真实数据，显示空图表
        if not dates:
            dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
            returns = [0] * len(dates)
            ax.text(0.5, 0.5, '暂无数据', transform=ax.transAxes, 
                   ha='center', va='center', fontsize=12, alpha=0.5)
        else:
            # 按日期排序
            sorted_data = sorted(zip(dates, returns), key=lambda x: x[0])
            dates = [d[0] for d in sorted_data]
            returns = [d[1] for d in sorted_data]
            
            # 计算基准线（平均收益率）
            if returns:
                baseline = np.mean(returns)
                baseline_returns = [baseline] * len(dates)
                
                # 绘制收益曲线（使用金融配色）
                ax.plot(dates, returns, color=FINANCIAL_COLORS['profit'], linewidth=1, label='收益率')
                ax.plot(dates, baseline_returns, color=FINANCIAL_COLORS['primary'], linewidth=1, label='基准', linestyle='--')
            else:
                ax.text(0.5, 0.5, '暂无数据', transform=ax.transAxes, 
                       ha='center', va='center', fontsize=12, alpha=0.5)
        
        ax.legend()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        
        return widget

    def _create_ranking_table(self) -> QTableWidget:
        """创建策略排行榜表格"""
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([
            "排名", "策略名称", "收益率", "夏普比率", "操作"
        ])
        
        # 设置表格属性（使用系统主题）
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        
        # 获取真实数据
        strategies = []
        
        if self.strategy_service:
            try:
                # 获取所有策略配置
                all_strategies = self.strategy_service.get_all_strategy_configs()
                
                # 为每个策略获取最新的回测结果
                strategy_metrics = []
                for strategy in all_strategies:
                    # 获取该策略的所有回测任务
                    strategy_backtests = []
                    for task_id, task in self.strategy_service._backtest_tasks.items():
                        if (task.strategy_config.strategy_id == strategy.strategy_id and 
                            task.status.value == 'completed' and
                            task.result):
                            strategy_backtests.append(task)
                    
                    # 按完成时间排序，获取最新的回测结果
                    if strategy_backtests:
                        strategy_backtests.sort(key=lambda t: t.completed_at if t.completed_at else datetime.min, reverse=True)
                        latest_backtest = strategy_backtests[0]
                        strategy_metrics.append({
                            'strategy_id': strategy.strategy_id,
                            'name': strategy.strategy_id,
                            'total_return': latest_backtest.result.total_return,
                            'sharpe_ratio': latest_backtest.result.sharpe_ratio
                        })
                
                # 按收益率排序
                strategy_metrics.sort(key=lambda x: x['total_return'], reverse=True)
                
                # 生成排行榜数据
                for rank, metric in enumerate(strategy_metrics[:10], 1):  # 只显示前10名
                    strategies.append((
                        str(rank),
                        metric['name'],
                        f"{metric['total_return']:.2%}",
                        f"{metric['sharpe_ratio']:.2f}"
                    ))
            except Exception as e:
                logger.error(f"获取策略排行榜数据失败: {e}")
        
        # 如果没有真实数据，显示空表格
        if not strategies:
            table.setRowCount(1)
            table.setItem(0, 0, QTableWidgetItem("-"))
            table.setItem(0, 1, QTableWidgetItem("暂无数据"))
            table.setItem(0, 2, QTableWidgetItem("-"))
            table.setItem(0, 3, QTableWidgetItem("-"))
            btn = QPushButton("查看")
            btn.setEnabled(False)
            table.setCellWidget(0, 4, btn)
        else:
            table.setRowCount(len(strategies))
            for row, (rank, name, ret, sharpe) in enumerate(strategies):
                table.setItem(row, 0, QTableWidgetItem(rank))
                table.setItem(row, 1, QTableWidgetItem(name))
                table.setItem(row, 2, QTableWidgetItem(ret))
                table.setItem(row, 3, QTableWidgetItem(sharpe))
            
            # 操作按钮
            btn = QPushButton("查看")
            btn.setMaximumSize(60, 25)
            btn.clicked.connect(lambda checked, r=rank: self._view_strategy(r))
            table.setCellWidget(row, 4, btn)
        
        return table

    def _create_library_view(self) -> QWidget:
        """创建策略库视图"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 工具栏
        toolbar = self._create_library_toolbar()
        layout.addWidget(toolbar)
        
        # 策略表格
        self.strategy_table = self._create_strategy_table()
        layout.addWidget(self.strategy_table)
        
        return widget

    def _create_library_toolbar(self) -> QWidget:
        """创建策略库工具栏"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        # 按钮组
        create_btn = QPushButton("新建策略")
        create_btn.clicked.connect(self._create_strategy)
        
        import_btn = QPushButton("导入")
        import_btn.clicked.connect(self._import_strategy)
        
        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self._export_strategy)
        
        batch_update_btn = QPushButton("批量修改默认账号")
        batch_update_btn.clicked.connect(self._batch_update_default_account)
        
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._load_strategies)
        
        # 搜索和筛选
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("搜索策略...")
        search_edit.textChanged.connect(self._on_search_text_changed)
        
        status_filter = QComboBox()
        status_filter.addItems(["全部状态", "已配置", "运行中", "错误"])
        status_filter.currentTextChanged.connect(self._on_status_filter_changed)
        
        # 默认账号筛选
        account_filter = QComboBox()
        account_filter.addItem("全部账号", "all")
        account_filter.addItem("系统默认", "default")
        
        # 加载账号列表
        self._load_accounts_for_filter(account_filter)
        account_filter.currentTextChanged.connect(self._on_account_filter_changed)
        
        # 布局
        layout.addWidget(create_btn)
        layout.addWidget(import_btn)
        layout.addWidget(export_btn)
        layout.addWidget(batch_update_btn)
        layout.addWidget(refresh_btn)
        layout.addSpacing(20)
        layout.addWidget(QLabel("搜索:"))
        layout.addWidget(search_edit)
        layout.addWidget(QLabel("状态:"))
        layout.addWidget(status_filter)
        layout.addWidget(QLabel("默认账号:"))
        layout.addWidget(account_filter)
        layout.addStretch()
        
        return widget

    def _create_strategy_table(self) -> QTableWidget:
        """创建策略表格（使用系统主题）"""
        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels([
            "选择", "策略ID", "策略名称", "框架", "类型", "默认账号", "状态", "最后更新", "操作"
        ])
        
        # 在第一列表头添加全选复选框
        header = table.horizontalHeader()
        self.select_all_checkbox = QCheckBox()
        self.select_all_checkbox.stateChanged.connect(self._on_select_all_changed)
        
        # 创建容器并居中复选框
        select_all_widget = QWidget()
        select_all_layout = QHBoxLayout(select_all_widget)
        select_all_layout.setContentsMargins(0, 0, 0, 0)
        select_all_layout.setAlignment(Qt.AlignCenter)
        select_all_layout.addWidget(self.select_all_checkbox)
        
        # 设置表头控件
        header.setIndexWidget(header.model().index(0, 0), select_all_widget)
        
        # 设置表格属性
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.ExtendedSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)
        
        # 连接信号
        table.itemDoubleClicked.connect(self._on_strategy_double_clicked)
        table.itemSelectionChanged.connect(self._on_strategy_selection_changed)
        table.itemChanged.connect(self._on_item_changed)
        
        return table

    def _create_backtest_view(self) -> QWidget:
        """创建回测实验室视图"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        # 左侧：配置面板
        config_panel = self._create_backtest_config_panel()
        layout.addWidget(config_panel, 1)
        
        # 右侧：结果面板
        result_panel = self._create_backtest_result_panel()
        layout.addWidget(result_panel, 2)
        
        return widget

    def _create_backtest_config_panel(self) -> QWidget:
        """创建回测配置面板（使用系统主题）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 策略选择（使用系统主题GroupBox）
        strategy_group = QGroupBox("策略选择")
        strategy_layout = QFormLayout(strategy_group)
        
        self.backtest_strategy_combo = QComboBox()
        self._load_strategies()
        strategy_layout.addRow("策略：", self.backtest_strategy_combo)
        
        layout.addWidget(strategy_group)
        
        # 回测配置（使用系统主题GroupBox）
        config_group = QGroupBox("回测配置")
        config_layout = QFormLayout(config_group)
        
        self.backtest_start_date = QDateEdit()
        self.backtest_start_date.setDate(QDateTime.currentDateTime().addDays(-365).date())
        self.backtest_start_date.setCalendarPopup(True)
        
        self.backtest_end_date = QDateEdit()
        self.backtest_end_date.setDate(QDateTime.currentDateTime().date())
        self.backtest_end_date.setCalendarPopup(True)
        
        self.backtest_initial_capital = QDoubleSpinBox()
        self.backtest_initial_capital.setRange(1000, 10000000)
        self.backtest_initial_capital.setValue(100000)
        self.backtest_initial_capital.setSuffix(" 元")
        
        self.backtest_commission_rate = QDoubleSpinBox()
        self.backtest_commission_rate.setRange(0, 0.01)
        self.backtest_commission_rate.setValue(0.0003)
        self.backtest_commission_rate.setDecimals(4)
        self.backtest_commission_rate.setSuffix(" %")
        
        # 时间周期选择
        self.backtest_timeframe_combo = QComboBox()
        self.backtest_timeframe_combo.addItem("日线", TimeFrame.DAY_1)
        self.backtest_timeframe_combo.addItem("1小时", TimeFrame.HOUR_1)
        self.backtest_timeframe_combo.addItem("30分钟", TimeFrame.MINUTE_30)
        self.backtest_timeframe_combo.addItem("15分钟", TimeFrame.MINUTE_15)
        self.backtest_timeframe_combo.addItem("5分钟", TimeFrame.MINUTE_5)
        self.backtest_timeframe_combo.addItem("1分钟", TimeFrame.MINUTE_1)
        self.backtest_timeframe_combo.setCurrentIndex(0)  # 默认选择日线
        
        config_layout.addRow("开始日期：", self.backtest_start_date)
        config_layout.addRow("结束日期：", self.backtest_end_date)
        config_layout.addRow("时间周期：", self.backtest_timeframe_combo)
        config_layout.addRow("初始资金：", self.backtest_initial_capital)
        config_layout.addRow("手续费率：", self.backtest_commission_rate)
        
        layout.addWidget(config_group)
        
        # 操作按钮（使用系统主题按钮）
        button_layout = QHBoxLayout()
        
        self.run_backtest_button = QPushButton("开始回测")
        self.run_backtest_button.clicked.connect(self._run_backtest)
        
        self.batch_backtest_button = QPushButton("批量回测")
        self.batch_backtest_button.clicked.connect(self._batch_backtest)
        
        self.parameter_scan_button = QPushButton("参数扫描")
        self.parameter_scan_button.clicked.connect(self._parameter_scan)
        
        button_layout.addWidget(self.run_backtest_button)
        button_layout.addWidget(self.batch_backtest_button)
        button_layout.addWidget(self.parameter_scan_button)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        return panel

    def _create_backtest_result_panel(self) -> QWidget:
        """创建回测结果面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 进度显示（使用系统主题）
        self.backtest_progress_group = QGroupBox("回测进度")
        progress_layout = QVBoxLayout(self.backtest_progress_group)
        
        self.backtest_progress_bar = QProgressBar()
        self.backtest_progress_bar.setRange(0, 100)
        
        self.backtest_status_label = QLabel("等待开始...")
        self.backtest_status_label.setAlignment(Qt.AlignCenter)
        
        self.cancel_backtest_button = QPushButton("取消")
        self.cancel_backtest_button.clicked.connect(self._cancel_backtest)
        self.cancel_backtest_button.setEnabled(False)
        
        progress_layout.addWidget(self.backtest_progress_bar)
        progress_layout.addWidget(self.backtest_status_label)
        progress_layout.addWidget(self.cancel_backtest_button)
        
        layout.addWidget(self.backtest_progress_group)
        
        # 性能指标卡片（自定义渐变样式）
        self.backtest_metrics_group = QGroupBox("性能指标")
        metrics_layout = QGridLayout(self.backtest_metrics_group)
        
        self.total_return_card = self._create_metric_card("总收益率", "N/A", 'return')
        self.sharpe_ratio_card = self._create_metric_card("夏普比率", "N/A", 'sharpe')
        self.max_drawdown_card = self._create_metric_card("最大回撤", "N/A", 'drawdown')
        self.win_rate_card = self._create_metric_card("胜率", "N/A", 'win_rate')
        
        metrics_layout.addWidget(self.total_return_card, 0, 0)
        metrics_layout.addWidget(self.sharpe_ratio_card, 0, 1)
        metrics_layout.addWidget(self.max_drawdown_card, 0, 2)
        metrics_layout.addWidget(self.win_rate_card, 0, 3)
        
        layout.addWidget(self.backtest_metrics_group)
        
        # 回测图表（使用系统主题背景，自定义金融配色）
        self.backtest_chart_tabs = QTabWidget()
        
        if MATPLOTLIB_AVAILABLE:
            self.equity_chart = self._create_equity_chart()
            self.backtest_chart_tabs.addTab(self.equity_chart, "权益曲线")
            
            self.drawdown_chart = self._create_drawdown_chart()
            self.backtest_chart_tabs.addTab(self.drawdown_chart, "回撤分析")
            
            self.trades_chart = self._create_trades_chart()
            self.backtest_chart_tabs.addTab(self.trades_chart, "交易记录")
        else:
            self.backtest_chart_tabs.addTab(QLabel("图表功能需要安装 matplotlib 库"), "图表")
        
        layout.addWidget(self.backtest_chart_tabs)
        
        return panel

    def _create_metric_card(self, title: str, value: str, metric_type: str) -> QWidget:
        """创建性能指标卡片（自定义渐变样式）"""
        card = QWidget()
        card.setFixedHeight(100)
        card.setFixedWidth(200)
        
        # 使用渐变样式
        gradient = METRIC_CARD_GRADIENTS[metric_type]
        card.setStyleSheet(f"""
            QWidget {{
                background: {gradient};
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}
            QLabel {{
                color: #FFFFFF;
                font-size: 12px;
                font-weight: bold;
            }}
            .value_label {{
                color: #FFFFFF;
                font-size: 24px;
                font-weight: bold;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignCenter)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 12px;")
        
        value_label = QLabel(value)
        value_label.setObjectName("value_label")
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        return card

    def _create_equity_chart(self) -> QWidget:
        """创建权益曲线图（使用系统主题背景，自定义金融配色）"""
        widget = FigureCanvas(Figure(figsize=(10, 6)))
        
        # 缓存图表引用
        self._cached_charts.append(widget)
        
        # 应用系统主题到图表背景
        self.theme_manager.apply_chart_theme(widget.figure)
        
        ax = widget.figure.add_subplot(111)
        ax.set_title("策略权益曲线", fontsize=14, fontweight='bold')
        ax.set_xlabel("日期", fontsize=12)
        ax.set_ylabel("累计收益率", fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # 显示空状态提示
        ax.text(0.5, 0.5, '等待回测完成...', transform=ax.transAxes, 
               ha='center', va='center', fontsize=14, alpha=0.5)
        
        ax.legend()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        
        return widget

    def _create_drawdown_chart(self) -> QWidget:
        """创建回撤分析图（使用系统主题背景，自定义金融配色）"""
        widget = FigureCanvas(Figure(figsize=(10, 6)))
        
        # 缓存图表引用
        self._cached_charts.append(widget)
        
        # 应用系统主题到图表背景
        self.theme_manager.apply_chart_theme(widget.figure)
        
        ax = widget.figure.add_subplot(111)
        ax.set_title("策略回撤分析", fontsize=14, fontweight='bold')
        ax.set_xlabel("日期", fontsize=12)
        ax.set_ylabel("回撤比例", fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # 显示空状态提示
        ax.text(0.5, 0.5, '等待回测完成...', transform=ax.transAxes, 
               ha='center', va='center', fontsize=14, alpha=0.5)
        
        ax.legend()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        
        return widget

    def _create_trades_chart(self) -> QWidget:
        """创建交易记录图（使用系统主题背景，自定义金融配色）"""
        widget = FigureCanvas(Figure(figsize=(10, 6)))
        
        # 缓存图表引用
        self._cached_charts.append(widget)
        
        # 应用系统主题到图表背景
        self.theme_manager.apply_chart_theme(widget.figure)
        
        ax = widget.figure.add_subplot(111)
        ax.set_title("交易记录分析", fontsize=14, fontweight='bold')
        ax.set_xlabel("交易序号", fontsize=12)
        ax.set_ylabel("盈亏金额", fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # 显示空状态提示
        ax.text(0.5, 0.5, '等待回测完成...', transform=ax.transAxes, 
               ha='center', va='center', fontsize=14, alpha=0.5)
        
        ax.legend()
        
        return widget

    def _create_optimization_view(self) -> QWidget:
        """创建参数优化视图"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        # 左侧：参数范围配置（使用系统主题）
        param_panel = self._create_optimization_param_panel()
        layout.addWidget(param_panel, 1)
        
        # 右侧：优化结果（使用系统主题）
        result_panel = self._create_optimization_result_panel()
        layout.addWidget(result_panel, 2)
        
        return widget

    def _create_optimization_param_panel(self) -> QWidget:
        """创建参数优化配置面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 优化配置（使用系统主题GroupBox）
        config_group = QGroupBox("优化配置")
        config_layout = QFormLayout(config_group)
        
        self.opt_strategy_combo = QComboBox()
        self._load_strategies()
        
        self.opt_algorithm_combo = QComboBox()
        self.opt_algorithm_combo.addItems(['grid_search', 'random_search', 'bayesian'])
        
        self.opt_target_metric_combo = QComboBox()
        self.opt_target_metric_combo.addItems(['total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate'])
        
        self.opt_max_iterations = QSpinBox()
        self.opt_max_iterations.setRange(10, 1000)
        self.opt_max_iterations.setValue(100)
        
        config_layout.addRow("策略：", self.opt_strategy_combo)
        config_layout.addRow("优化算法：", self.opt_algorithm_combo)
        config_layout.addRow("目标指标：", self.opt_target_metric_combo)
        config_layout.addRow("最大迭代：", self.opt_max_iterations)
        
        self.opt_timeframe_combo = QComboBox()
        self.opt_timeframe_combo.addItem("日线", TimeFrame.DAY_1)
        self.opt_timeframe_combo.addItem("1小时", TimeFrame.HOUR_1)
        self.opt_timeframe_combo.addItem("30分钟", TimeFrame.MINUTE_30)
        self.opt_timeframe_combo.addItem("15分钟", TimeFrame.MINUTE_15)
        self.opt_timeframe_combo.addItem("5分钟", TimeFrame.MINUTE_5)
        self.opt_timeframe_combo.addItem("1分钟", TimeFrame.MINUTE_1)
        self.opt_timeframe_combo.setCurrentIndex(0)
        config_layout.addRow("时间周期：", self.opt_timeframe_combo)
        
        layout.addWidget(config_group)
        
        # 参数范围表格（使用系统主题表格）
        param_group = QGroupBox("参数范围")
        param_layout = QVBoxLayout(param_group)
        
        self.opt_param_table = QTableWidget()
        self.opt_param_table.setColumnCount(5)
        self.opt_param_table.setHorizontalHeaderLabels([
            "参数名", "最小值", "最大值", "步长", "类型"
        ])
        self.opt_param_table.horizontalHeader().setStretchLastSection(True)
        
        # 添加示例参数
        params = [
            ("lookback_period", "5", "60", "5", "int"),
            ("threshold", "0.01", "0.1", "0.01", "float"),
            ("stop_loss", "0.02", "0.1", "0.01", "float"),
            ("take_profit", "0.05", "0.2", "0.01", "float")
        ]
        
        self.opt_param_table.setRowCount(len(params))
        for row, (name, min_val, max_val, step, param_type) in enumerate(params):
            self.opt_param_table.setItem(row, 0, QTableWidgetItem(name))
            self.opt_param_table.setItem(row, 1, QTableWidgetItem(min_val))
            self.opt_param_table.setItem(row, 2, QTableWidgetItem(max_val))
            self.opt_param_table.setItem(row, 3, QTableWidgetItem(step))
            self.opt_param_table.setItem(row, 4, QTableWidgetItem(param_type))
        
        param_layout.addWidget(self.opt_param_table)
        
        # 操作按钮（使用系统主题按钮）
        button_layout = QHBoxLayout()
        
        add_param_btn = QPushButton("添加参数")
        add_param_btn.clicked.connect(self._add_optimization_param)
        
        import_btn = QPushButton("导入范围")
        import_btn.clicked.connect(self._import_optimization_ranges)
        
        export_btn = QPushButton("导出范围")
        export_btn.clicked.connect(self._export_optimization_ranges)
        
        button_layout.addWidget(add_param_btn)
        button_layout.addWidget(import_btn)
        button_layout.addWidget(export_btn)
        
        param_layout.addLayout(button_layout)
        layout.addWidget(param_group)
        
        # 开始优化按钮（使用系统主题按钮）
        start_layout = QHBoxLayout()
        
        self.start_optimization_button = QPushButton("开始优化")
        self.start_optimization_button.clicked.connect(self._start_optimization)
        
        self.opt_scan_button = QPushButton("参数扫描")
        self.opt_scan_button.clicked.connect(self._parameter_scan)
        
        self.opt_sensitivity_button = QPushButton("敏感性分析")
        self.opt_sensitivity_button.clicked.connect(self._sensitivity_analysis)
        
        start_layout.addWidget(self.start_optimization_button)
        start_layout.addWidget(self.opt_scan_button)
        start_layout.addWidget(self.opt_sensitivity_button)
        
        layout.addLayout(start_layout)
        layout.addStretch()
        
        return panel

    def _create_optimization_result_panel(self) -> QWidget:
        """创建优化结果面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 优化进度（使用系统主题）
        self.opt_progress_group = QGroupBox("优化进度")
        progress_layout = QVBoxLayout(self.opt_progress_group)
        
        self.opt_progress_bar = QProgressBar()
        self.opt_progress_bar.setRange(0, 100)
        
        self.opt_iteration_label = QLabel("当前迭代：0/100")
        self.opt_iteration_label.setAlignment(Qt.AlignCenter)
        
        self.opt_best_value_label = QLabel("最佳值：0.0000")
        self.opt_best_value_label.setAlignment(Qt.AlignCenter)
        
        self.cancel_optimization_button = QPushButton("取消")
        self.cancel_optimization_button.clicked.connect(self._cancel_optimization)
        self.cancel_optimization_button.setEnabled(False)
        
        progress_layout.addWidget(self.opt_progress_bar)
        progress_layout.addWidget(self.opt_iteration_label)
        progress_layout.addWidget(self.opt_best_value_label)
        progress_layout.addWidget(self.cancel_optimization_button)
        
        layout.addWidget(self.opt_progress_group)
        
        # 优化曲线图（使用系统主题背景，自定义金融配色）
        if MATPLOTLIB_AVAILABLE:
            self.optimization_chart = self._create_optimization_chart()
            layout.addWidget(self.optimization_chart)
        else:
            layout.addWidget(QLabel("图表功能需要安装 matplotlib 库"))
        
        # 最佳参数表格（使用系统主题表格）
        best_param_group = QGroupBox("最佳参数")
        best_param_layout = QVBoxLayout(best_param_group)
        
        self.best_param_table = QTableWidget()
        self.best_param_table.setColumnCount(4)
        self.best_param_table.setHorizontalHeaderLabels([
            "参数名", "最佳值", "当前值", "改进"
        ])
        
        # 添加示例参数
        best_params = [
            ("lookback_period", "20", "10", "+100%"),
            ("threshold", "0.02", "0.05", "-60%"),
            ("stop_loss", "0.05", "0.08", "-37.5%"),
            ("take_profit", "0.15", "0.10", "+50%")
        ]
        
        self.best_param_table.setRowCount(len(best_params))
        for row, (name, best, current, improvement) in enumerate(best_params):
            self.best_param_table.setItem(row, 0, QTableWidgetItem(name))
            self.best_param_table.setItem(row, 1, QTableWidgetItem(best))
            self.best_param_table.setItem(row, 2, QTableWidgetItem(current))
            
            # 改进列使用颜色
            improvement_item = QTableWidgetItem(improvement)
            if improvement.startswith('+'):
                improvement_item.setForeground(QColor(FINANCIAL_COLORS['profit']))
            else:
                improvement_item.setForeground(QColor(FINANCIAL_COLORS['loss']))
            
            self.best_param_table.setItem(row, 3, improvement_item)
        
        best_param_layout.addWidget(self.best_param_table)
        
        # 操作按钮（使用系统主题按钮）
        apply_button = QPushButton("应用最佳参数")
        apply_button.clicked.connect(self._apply_best_parameters)
        
        save_button = QPushButton("保存配置")
        save_button.clicked.connect(self._save_optimization_config)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(apply_button)
        button_layout.addWidget(save_button)
        
        best_param_layout.addLayout(button_layout)
        layout.addWidget(best_param_group)
        
        return panel

    def _create_optimization_chart(self) -> QWidget:
        """创建优化曲线图（使用系统主题背景，自定义金融配色）"""
        widget = FigureCanvas(Figure(figsize=(10, 6)))
        
        # 缓存图表引用
        self._cached_charts.append(widget)
        
        # 应用系统主题到图表背景
        self.theme_manager.apply_chart_theme(widget.figure)
        
        ax = widget.figure.add_subplot(111)
        ax.set_title("优化曲线", fontsize=14, fontweight='bold')
        ax.set_xlabel("迭代次数", fontsize=12)
        ax.set_ylabel("目标指标", fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # 显示空状态提示
        ax.text(0.5, 0.5, '等待优化完成...', transform=ax.transAxes, 
               ha='center', va='center', fontsize=14, alpha=0.5)
        
        ax.legend()
        
        return widget

    def _create_performance_view(self) -> QWidget:
        """创建性能分析视图"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 性能概览
        overview_group = QGroupBox("性能概览")
        overview_layout = QGridLayout(overview_group)
        
        # 添加性能指标
        metrics = [
            ("总收益率", "+15.8%", FINANCIAL_COLORS['profit']),
            ("年化收益率", "+18.5%", FINANCIAL_COLORS['profit']),
            ("夏普比率", "1.65", FINANCIAL_COLORS['primary']),
            ("最大回撤", "-8.3%", FINANCIAL_COLORS['loss']),
            ("胜率", "58.5%", FINANCIAL_COLORS['warning']),
            ("盈亏比", "1.35", FINANCIAL_COLORS['auxiliary_1']),
            ("平均持仓天数", "5.2", FINANCIAL_COLORS['auxiliary_2'])
        ]
        
        for i, (name, value, color) in enumerate(metrics):
            label = QLabel(f"{name}:")
            value_label = QLabel(value)
            
            # 设置颜色
            label.setStyleSheet(f"color: {color}; font-weight: bold;")
            value_label.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
            
            overview_layout.addWidget(label, i // 4, i % 4)
            overview_layout.addWidget(value_label, i // 4, i % 4)
        
        layout.addWidget(overview_group)
        
        # 策略对比
        comparison_group = QGroupBox("策略对比")
        comparison_layout = QVBoxLayout(comparison_group)
        
        # 策略选择工具栏
        toolbar_layout = QHBoxLayout()
        
        toolbar_layout.addWidget(QLabel("选择策略进行对比："))
        
        self.compare_strategy_combo1 = QComboBox()
        self.compare_strategy_combo1.setMinimumWidth(200)
        toolbar_layout.addWidget(self.compare_strategy_combo1)
        
        toolbar_layout.addWidget(QLabel("vs"))
        
        self.compare_strategy_combo2 = QComboBox()
        self.compare_strategy_combo2.setMinimumWidth(200)
        toolbar_layout.addWidget(self.compare_strategy_combo2)
        
        self.compare_button = QPushButton("开始对比")
        self.compare_button.clicked.connect(self._compare_strategies)
        toolbar_layout.addWidget(self.compare_button)
        
        toolbar_layout.addStretch()
        
        comparison_layout.addLayout(toolbar_layout)
        
        # 对比结果表格
        self.comparison_table = QTableWidget()
        self.comparison_table.setColumnCount(3)
        self.comparison_table.setHorizontalHeaderLabels(["指标", "策略1", "策略2"])
        self.comparison_table.horizontalHeader().setStretchLastSection(True)
        self.comparison_table.setAlternatingRowColors(True)
        comparison_layout.addWidget(self.comparison_table)
        
        layout.addWidget(comparison_group)
        
        # 性能图表
        chart_group = QGroupBox("性能图表")
        chart_layout = QVBoxLayout(chart_group)
        
        if MATPLOTLIB_AVAILABLE:
            self.performance_chart = self._create_performance_chart()
            chart_layout.addWidget(self.performance_chart)
        else:
            chart_layout.addWidget(QLabel("图表功能需要安装 matplotlib 库"))
        
        layout.addWidget(chart_group)
        
        # 加载策略列表到对比下拉框
        self._load_comparison_strategies()
        
        return widget

    def _create_performance_chart(self) -> QWidget:
        """创建性能图表（使用系统主题背景，自定义金融配色）"""
        widget = FigureCanvas(Figure(figsize=(10, 6)))
        
        # 缓存图表引用
        self._cached_charts.append(widget)
        
        # 应用系统主题到图表背景
        self.theme_manager.apply_chart_theme(widget.figure)
        
        ax = widget.figure.add_subplot(111)
        ax.set_title("策略性能分析", fontsize=14, fontweight='bold')
        ax.set_xlabel("时间", fontsize=12)
        ax.set_ylabel("收益率 (%)", fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # 显示空状态提示
        ax.text(0.5, 0.5, '等待回测完成...', transform=ax.transAxes, 
               ha='center', va='center', fontsize=14, alpha=0.5)
        
        ax.legend()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m'))
        
        return widget

    def _switch_view(self, view_name: str):
        """切换视图"""
        self.current_view = view_name
        
        # 更新按钮状态
        for btn in self.nav_buttons:
            btn.setChecked(btn.text().lower().find(view_name) >= 0)
        
        # 切换内容
        view_map = {
            'home': self.home_view,
            'library': self.library_view,
            'backtest': self.backtest_view,
            'optimization': self.optimization_view,
            'performance': self.performance_view
        }
        
        self.content_stack.setCurrentWidget(view_map.get(view_name, self.home_view))

    def _on_theme_changed(self, theme: Theme):
        """主题变化事件"""
        logger.info(f"主题已切换: {theme}")
        
        # 系统主题管理器会自动应用主题到所有控件
        # 这里只需要更新自定义样式的组件
        
        # 更新图表主题
        self._update_chart_themes()
        
        # 更新状态指示器
        self._update_status_indicators()
        
        # 更新性能指标卡片
        self._update_metric_cards()
        
        # 更新统计卡片
        self._update_stat_cards()
        
        # 重新绘制所有图表
        self._refresh_all_charts()

    def _update_chart_themes(self):
        """更新图表主题（使用缓存的图表引用）"""
        try:
            # 使用缓存的图表引用，避免遍历整个控件树
            for chart in self._cached_charts:
                if chart and hasattr(chart, 'figure'):
                    self.theme_manager.apply_chart_theme(chart.figure)
                    
                    # 自定义图表线条颜色（金融配色）
                    self._apply_chart_line_colors(chart.figure)
                    
                    # 重新绘制图表
                    chart.draw()
                
            logger.info(f"已更新 {len(self._cached_charts)} 个图表的主题")
            
        except Exception as e:
            logger.error(f"更新图表主题失败: {e}")

    def _apply_chart_line_colors(self, figure):
        """应用自定义图表线条颜色（金融配色）"""
        try:
            # 获取当前主题
            current_theme = self.theme_manager.current_theme
            
            # 根据主题调整图表样式
            for ax in figure.axes:
                # 设置网格颜色
                if current_theme == Theme.DARK:
                    ax.grid(True, alpha=0.2, color='gray')
                else:
                    ax.grid(True, alpha=0.3, color='lightgray')
                
                # 设置坐标轴颜色
                ax.xaxis.label.set_color('white' if current_theme == Theme.DARK else 'black')
                ax.yaxis.label.set_color('white' if current_theme == Theme.DARK else 'black')
                ax.title.set_color('white' if current_theme == Theme.DARK else 'black')
                
                # 设置刻度标签颜色
                for tick in ax.get_xticklabels() + ax.get_yticklabels():
                    tick.set_color('white' if current_theme == Theme.DARK else 'black')
                    
        except Exception as e:
            logger.error(f"应用图表线条颜色失败: {e}")

    def _update_status_indicators(self):
        """更新状态指示器（自定义语义化颜色）"""
        try:
            # 更新策略表格中的状态项
            if hasattr(self, 'strategy_table'):
                for row in range(self.strategy_table.rowCount()):
                    status_item = self.strategy_table.item(row, 5)  # 状态列（第6列）
                    if status_item:
                        status = status_item.text()
                        # 使用自定义语义化颜色
                        if status == "运行中":
                            status_item.setForeground(QColor(STATUS_COLORS['running']))
                        elif status == "错误":
                            status_item.setForeground(QColor(STATUS_COLORS['error']))
                        elif status == "已配置":
                            status_item.setForeground(QColor(STATUS_COLORS['configured']))
                        else:
                            status_item.setForeground(QColor(STATUS_COLORS['stopped']))
                            
        except Exception as e:
            logger.error(f"更新状态指示器失败: {e}")

    def _update_metric_cards(self):
        """更新性能指标卡片（自定义渐变样式）"""
        try:
            # 性能指标卡片使用固定的渐变样式，不随主题变化
            # 这里可以添加动态调整的逻辑
            pass
            
        except Exception as e:
            logger.error(f"更新性能指标卡片失败: {e}")

    def _update_stat_cards(self):
        """更新统计卡片"""
        try:
            # 统计卡片使用固定的渐变样式，不随主题变化
            # 这里可以添加动态调整的逻辑
            pass
            
        except Exception as e:
            logger.error(f"更新统计卡片失败: {e}")

    def _refresh_all_charts(self):
        """刷新所有图表（使用缓存的图表引用）"""
        try:
            # 使用缓存的图表引用，避免遍历整个控件树
            for chart in self._cached_charts:
                if chart:
                    chart.draw()
                
            logger.info(f"已刷新 {len(self._cached_charts)} 个图表")
            
        except Exception as e:
            logger.error(f"刷新图表失败: {e}")

    def _load_strategies(self):
        """加载策略列表（使用增量更新优化性能）"""
        if not self.strategy_service:
            QMessageBox.warning(self, "警告", "策略服务不可用")
            return

        try:
            # 阻塞信号以避免频繁更新全选复选框
            self.strategy_table.blockSignals(True)
            
            # 调用后端API获取策略列表
            strategies = self.strategy_service.get_all_strategy_configs()
            
            # 获取当前表格中的所有策略ID
            current_strategy_ids = set()
            for row in range(self.strategy_table.rowCount()):
                item = self.strategy_table.item(row, 1)
                if item:
                    current_strategy_ids.add(item.text())
            
            # 获取新策略ID集合
            new_strategy_ids = {strategy.strategy_id for strategy in strategies}
            
            # 找出需要删除的策略
            to_remove = current_strategy_ids - new_strategy_ids
            
            # 找出需要添加的策略
            to_add = new_strategy_ids - current_strategy_ids
            
            # 找出需要更新的策略
            to_update = current_strategy_ids & new_strategy_ids
            
            # 创建策略ID到策略对象的映射
            strategy_map = {strategy.strategy_id: strategy for strategy in strategies}
            
            # 删除不存在的策略（从后往前删除，避免索引变化）
            rows_to_remove = []
            for row in range(self.strategy_table.rowCount()):
                item = self.strategy_table.item(row, 1)
                if item and item.text() in to_remove:
                    rows_to_remove.append(row)
            
            for row in sorted(rows_to_remove, reverse=True):
                self.strategy_table.removeRow(row)
            
            # 更新现有策略
            for row in range(self.strategy_table.rowCount()):
                item = self.strategy_table.item(row, 1)
                if item and item.text() in to_update:
                    strategy_id = item.text()
                    strategy = strategy_map.get(strategy_id)
                    if strategy:
                        self._update_strategy_row(row, strategy)
            
            # 添加新策略
            for strategy_id in to_add:
                strategy = strategy_map.get(strategy_id)
                if strategy:
                    row = self.strategy_table.rowCount()
                    self.strategy_table.insertRow(row)
                    self._add_strategy_row(row, strategy)
            
            # 恢复信号
            self.strategy_table.blockSignals(False)
            
            # 更新回测策略选择下拉框
            if hasattr(self, 'backtest_strategy_combo'):
                self._update_combo_with_strategies(self.backtest_strategy_combo, strategies)
            
            # 更新优化策略选择下拉框
            if hasattr(self, 'opt_strategy_combo'):
                self._update_combo_with_strategies(self.opt_strategy_combo, strategies)
            
            # 更新对比策略选择下拉框
            if hasattr(self, 'compare_strategy_combo1') and hasattr(self, 'compare_strategy_combo2'):
                self._load_comparison_strategies()
            
            # 更新全选复选框状态
            if hasattr(self, 'select_all_checkbox'):
                self._update_select_all_checkbox_state()
                    
            logger.info(f"成功加载 {len(strategies)} 个策略（新增: {len(to_add)}, 删除: {len(to_remove)}, 更新: {len(to_update)}）")
                    
        except Exception as e:
            logger.error(f"加载策略列表失败: {e}")
            QMessageBox.warning(self, "错误", f"加载策略列表失败: {e}")
        finally:
            self.strategy_table.blockSignals(False)
    
    def _update_strategy_row(self, row: int, strategy: StrategyConfig):
        """更新策略行数据"""
        # 策略名称（从metadata中获取）
        strategy_name = strategy.metadata.get('name', strategy.strategy_id)
        name_item = self.strategy_table.item(row, 2)
        if name_item:
            name_item.setText(strategy_name)
        
        # 框架类型
        plugin_item = self.strategy_table.item(row, 3)
        if plugin_item:
            plugin_item.setText(strategy.plugin_type)
        
        # 策略类型（从metadata中获取）
        strategy_type = strategy.metadata.get('type', 'unknown')
        type_text = self._get_strategy_type_text(strategy_type)
        type_item = self.strategy_table.item(row, 4)
        if type_item:
            type_item.setText(type_text)
        
        # 默认账号（从metadata中获取）
        default_account_id = strategy.metadata.get('default_account_id', 'default')
        default_account_text = "系统默认" if default_account_id == 'default' else default_account_id
        account_item = self.strategy_table.item(row, 5)
        if account_item:
            account_item.setText(default_account_text)
        
        # 最后更新时间
        last_updated = strategy.updated_at
        if last_updated:
            try:
                last_updated = last_updated.strftime('%Y-%m-%d %H:%M')
            except:
                pass
        updated_item = self.strategy_table.item(row, 7)
        if updated_item:
            updated_item.setText(last_updated)
    
    def _update_combo_with_strategies(self, combo: QComboBox, strategies: List[StrategyConfig]):
        """更新下拉框的策略列表（增量更新）"""
        # 保存当前选择
        current_selection = combo.currentData()
        
        # 获取当前下拉框中的所有策略ID
        current_ids = {combo.itemData(i) for i in range(combo.count())}
        
        # 获取新策略ID集合
        new_ids = {strategy.strategy_id for strategy in strategies}
        
        # 找出需要删除的策略
        to_remove = current_ids - new_ids
        
        # 找出需要添加的策略
        to_add = new_ids - current_ids
        
        # 创建策略ID到策略对象的映射
        strategy_map = {strategy.strategy_id: strategy for strategy in strategies}
        
        # 删除不存在的策略（从后往前删除，避免索引变化）
        for i in range(combo.count() - 1, -1, -1):
            if combo.itemData(i) in to_remove:
                combo.removeItem(i)
        
        # 添加新策略
        for strategy_id in to_add:
            strategy = strategy_map.get(strategy_id)
            if strategy:
                display_text = f"{strategy.strategy_id}"
                combo.addItem(display_text, strategy.strategy_id)
        
        # 恢复之前的选择
        if current_selection:
            index = combo.findData(current_selection)
            if index >= 0:
                combo.setCurrentIndex(index)

    def _add_strategy_row(self, row: int, strategy: StrategyConfig):
        """添加策略行（适配9列表格结构）"""
        # 选择框
        checkbox_item = QTableWidgetItem()
        checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        checkbox_item.setCheckState(Qt.Unchecked)
        self.strategy_table.setItem(row, 0, checkbox_item)
        
        # 策略ID
        self.strategy_table.setItem(row, 1, QTableWidgetItem(strategy.strategy_id))
        
        # 策略名称（从metadata中获取）
        strategy_name = strategy.metadata.get('name', strategy.strategy_id)
        self.strategy_table.setItem(row, 2, QTableWidgetItem(strategy_name))
        
        # 框架类型
        self.strategy_table.setItem(row, 3, QTableWidgetItem(strategy.plugin_type))
        
        # 策略类型（从metadata中获取）
        strategy_type = strategy.metadata.get('type', 'unknown')
        type_text = self._get_strategy_type_text(strategy_type)
        self.strategy_table.setItem(row, 4, QTableWidgetItem(type_text))
        
        # 默认账号（从metadata中获取）
        default_account_id = strategy.metadata.get('default_account_id', 'default')
        default_account_text = "系统默认" if default_account_id == 'default' else default_account_id
        self.strategy_table.setItem(row, 5, QTableWidgetItem(default_account_text))
        
        # 状态（使用自定义语义化颜色）
        status = "已配置"
        status_item = QTableWidgetItem(status)
        status_item.setForeground(QColor(STATUS_COLORS.get('configured', '#6B7280')))
        self.strategy_table.setItem(row, 6, status_item)
        
        # 最后更新时间
        last_updated = strategy.updated_at
        if last_updated:
            try:
                last_updated = last_updated.strftime('%Y-%m-%d %H:%M')
            except:
                pass
        self.strategy_table.setItem(row, 7, QTableWidgetItem(last_updated))
        
        # 操作按钮
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(2, 2, 2, 2)
        button_layout.setSpacing(5)
        
        edit_button = QPushButton("编辑")
        edit_button.setMaximumSize(50, 25)
        edit_button.clicked.connect(lambda checked, sid=strategy.strategy_id: self._edit_strategy(sid))
        
        delete_button = QPushButton("删除")
        delete_button.setMaximumSize(50, 25)
        delete_button.clicked.connect(lambda checked, sid=strategy.strategy_id: self._delete_strategy(sid))
        
        button_layout.addWidget(edit_button)
        button_layout.addWidget(delete_button)
        self.strategy_table.setCellWidget(row, 8, button_widget)

    def _on_search_text_changed(self, text: str):
        """搜索文本变化事件"""
        try:
            self._filter_strategies(text, self._get_current_status_filter(), self._get_current_account_filter())
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            QMessageBox.warning(self, "警告", f"搜索失败: {str(e)}")

    def _on_status_filter_changed(self, text: str):
        """状态筛选变化事件"""
        try:
            self._filter_strategies(self._get_current_search_text(), text, self._get_current_account_filter())
        except Exception as e:
            logger.error(f"状态筛选失败: {e}")
            QMessageBox.warning(self, "警告", f"状态筛选失败: {str(e)}")

    def _filter_strategies(self, search_text: str, status_filter: str, account_filter: str = "all"):
        """筛选策略列表"""
        if not self.strategy_service:
            return
        
        try:
            # 阻塞信号以避免频繁更新全选复选框
            self.strategy_table.blockSignals(True)
            
            # 获取所有策略
            all_strategies = self.strategy_service.get_all_strategy_configs()
            
            # 应用筛选条件
            filtered_strategies = []
            for strategy in all_strategies:
                # 搜索文本筛选
                if search_text:
                    search_lower = search_text.lower()
                    strategy_id = strategy.strategy_id.lower()
                    strategy_name = getattr(strategy, 'name', '').lower()
                    if search_lower not in strategy_id and search_lower not in strategy_name:
                        continue
                
                # 状态筛选
                if status_filter and status_filter != "全部状态":
                    status_map = {
                        "已配置": "configured",
                        "运行中": "running",
                        "错误": "error"
                    }
                    filter_status = status_map.get(status_filter, "")
                    if filter_status:
                        strategy_status = getattr(strategy, 'status', 'stopped')
                        if strategy_status != filter_status:
                            continue
                
                # 默认账号筛选
                if account_filter and account_filter != "all":
                    default_account_id = strategy.metadata.get('default_account_id', 'default')
                    if default_account_id != account_filter:
                        continue
                
                filtered_strategies.append(strategy)
            
            # 更新表格
            self.strategy_table.setRowCount(len(filtered_strategies))
            for row, strategy in enumerate(filtered_strategies):
                self._add_strategy_row(row, strategy)
            
            # 恢复信号
            self.strategy_table.blockSignals(False)
            
            # 更新全选复选框状态
            self._update_select_all_checkbox_state()
            
        except Exception as e:
            logger.error(f"筛选策略失败: {e}")
        finally:
            self.strategy_table.blockSignals(False)

    def _get_current_search_text(self) -> str:
        """获取当前搜索文本"""
        search_edit = self.findChild(QLineEdit)
        if search_edit and search_edit.placeholderText() == "搜索策略...":
            return search_edit.text()
        return ""

    def _get_current_status_filter(self) -> str:
        """获取当前状态筛选"""
        status_filter = self.findChild(QComboBox)
        if status_filter and status_filter.count() > 0:
            return status_filter.currentText()
        return ""
    
    def _load_accounts_for_filter(self, account_filter: QComboBox):
        """加载账号列表到筛选下拉框"""
        try:
            from core.trading.account_manager import AccountManager
            account_manager = self.service_container.resolve(AccountManager)
            
            if account_manager:
                accounts = account_manager.get_all_accounts()
                for account in accounts:
                    account_filter.addItem(account.account_id, account.account_id)
        except Exception as e:
            logger.error(f"加载账号列表失败: {e}")
    
    def _on_account_filter_changed(self, text: str):
        """账号筛选变化事件"""
        try:
            self._filter_strategies(
                self._get_current_search_text(),
                self._get_current_status_filter(),
                self._get_current_account_filter()
            )
        except Exception as e:
            logger.error(f"账号筛选失败: {e}")
            QMessageBox.warning(self, "警告", f"账号筛选失败: {str(e)}")
    
    def _get_current_account_filter(self) -> str:
        """获取当前账号筛选"""
        account_filters = self.findChildren(QComboBox)
        for account_filter in account_filters:
            if account_filter.count() > 0 and account_filter.itemData(0) == "all":
                return account_filter.currentData()
        return "all"

    def _load_comparison_strategies(self):
        """加载策略列表到对比下拉框"""
        if not self.strategy_service:
            return
        
        try:
            strategies = self.strategy_service.get_all_strategy_configs()
            
            # 保存当前选择
            current_selection1 = self.compare_strategy_combo1.currentData()
            current_selection2 = self.compare_strategy_combo2.currentData()
            
            # 清空并重新加载
            self.compare_strategy_combo1.clear()
            self.compare_strategy_combo2.clear()
            
            for strategy in strategies:
                display_text = f"{strategy.strategy_id} - {strategy.metadata.get('name', '')}"
                self.compare_strategy_combo1.addItem(display_text, strategy.strategy_id)
                self.compare_strategy_combo2.addItem(display_text, strategy.strategy_id)
            
            # 恢复之前的选择
            if current_selection1:
                index1 = self.compare_strategy_combo1.findData(current_selection1)
                if index1 >= 0:
                    self.compare_strategy_combo1.setCurrentIndex(index1)
            
            if current_selection2:
                index2 = self.compare_strategy_combo2.findData(current_selection2)
                if index2 >= 0:
                    self.compare_strategy_combo2.setCurrentIndex(index2)
            
        except Exception as e:
            logger.error(f"加载对比策略列表失败: {e}")

    def _compare_strategies(self):
        """对比策略"""
        try:
            strategy_id1 = self.compare_strategy_combo1.currentData()
            strategy_id2 = self.compare_strategy_combo2.currentData()
            
            if not strategy_id1 or not strategy_id2:
                QMessageBox.warning(self, "警告", "请选择两个策略进行对比")
                return
            
            if strategy_id1 == strategy_id2:
                QMessageBox.warning(self, "警告", "请选择不同的策略进行对比")
                return
            
            # 获取策略配置
            config1 = self.strategy_service.get_strategy_config(strategy_id1)
            config2 = self.strategy_service.get_strategy_config(strategy_id2)
            
            if not config1 or not config2:
                QMessageBox.warning(self, "警告", "无法获取策略配置")
                return
            
            # 创建并显示策略对比对话框
            dialog = StrategyComparisonDialog(self, strategy_id1, strategy_id2, config1, config2, self.strategy_service)
            dialog.run_comparison()
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"策略对比失败: {e}")
            QMessageBox.critical(self, "错误", f"策略对比失败: {str(e)}")

    def _get_strategy_type_text(self, strategy_type: str) -> str:
        """获取策略类型文本"""
        type_map = {
            'momentum': '动量策略',
            'mean_reversion': '均值回归',
            'trend_following': '趋势跟踪',
            'arbitrage': '套利策略',
            'statistical': '统计套利',
            'custom': '自定义策略',
            'unknown': '未知'
        }
        return type_map.get(strategy_type, strategy_type)

    def _on_strategy_double_clicked(self, item):
        """策略双击事件"""
        try:
            row = item.row()
            strategy_id_item = self.strategy_table.item(row, 1)
            if strategy_id_item:
                self._edit_strategy(strategy_id_item.text())
        except Exception as e:
            logger.error(f"打开策略详情失败: {e}")
            QMessageBox.warning(self, "警告", f"打开策略详情失败: {str(e)}")

    def _on_strategy_selection_changed(self):
        """策略选择变化事件"""
        try:
            selected_items = self.strategy_table.selectedItems()
            if not selected_items:
                return

            row = selected_items[0].row()
            strategy_id_item = self.strategy_table.item(row, 1)
            if strategy_id_item:
                strategy_id = strategy_id_item.text()
                self.current_strategy_id = strategy_id
                self.strategy_selected.emit(strategy_id)
        except Exception as e:
            logger.error(f"策略选择失败: {e}")
    
    def _on_select_all_changed(self, state: int):
        """全选复选框状态变化事件"""
        try:
            for row in range(self.strategy_table.rowCount()):
                checkbox_item = self.strategy_table.item(row, 0)
                if checkbox_item:
                    checkbox_item.setCheckState(Qt.CheckState(state))
        except Exception as e:
            logger.error(f"全选操作失败: {e}")
            QMessageBox.warning(self, "警告", f"全选操作失败: {str(e)}")
    
    def _on_item_changed(self, item: QTableWidgetItem):
        """表格项变化事件（用于更新全选复选框状态）"""
        try:
            if item.column() == 0:
                self._update_select_all_checkbox_state()
        except Exception as e:
            logger.error(f"表格项变化处理失败: {e}")
    
    def _update_select_all_checkbox_state(self):
        """更新全选复选框状态"""
        if not hasattr(self, 'select_all_checkbox'):
            return
        
        total_rows = self.strategy_table.rowCount()
        if total_rows == 0:
            self.select_all_checkbox.setCheckState(Qt.Unchecked)
            return
        
        checked_count = 0
        for row in range(total_rows):
            checkbox_item = self.strategy_table.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                checked_count += 1
        
        if checked_count == 0:
            self.select_all_checkbox.setCheckState(Qt.Unchecked)
        elif checked_count == total_rows:
            self.select_all_checkbox.setCheckState(Qt.Checked)
        else:
            self.select_all_checkbox.setCheckState(Qt.PartiallyChecked)

    def _get_selected_strategy_rows(self):
        """获取选中的策略行号列表"""
        selected_rows = set()
        for item in self.strategy_table.selectedItems():
            selected_rows.add(item.row())
        return sorted(list(selected_rows))

    def _view_strategy(self, rank: str):
        """查看策略详情"""
        QMessageBox.information(self, "策略详情", f"查看排名第 {rank} 的策略")

    def _create_strategy(self):
        """创建策略"""
        try:
            # 检查策略服务
            if not self.strategy_service:
                logger.warning("策略服务未初始化")
                QMessageBox.warning(self, "警告", "策略服务未初始化")
                return
            
            # 创建策略配置对话框
            dialog = StrategyConfigDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                config_data = dialog.get_config_data()
                
                # 验证策略ID
                strategy_id = config_data.get('strategy_id', '').strip()
                if not strategy_id:
                    QMessageBox.warning(self, "警告", "策略ID不能为空")
                    return
                
                # 验证策略ID格式（只允许字母、数字、下划线和连字符）
                import re
                if not re.match(r'^[a-zA-Z0-9_-]+$', strategy_id):
                    QMessageBox.warning(self, "警告", "策略ID只能包含字母、数字、下划线和连字符")
                    return
                
                # 验证策略名称
                strategy_name = config_data.get('metadata', {}).get('name', '').strip()
                if not strategy_name:
                    QMessageBox.warning(self, "警告", "策略名称不能为空")
                    return
                
                # 验证参数
                parameters = config_data.get('parameters', {})
                for param_name, param_value in parameters.items():
                    if not param_name.strip():
                        QMessageBox.warning(self, "警告", "参数名不能为空")
                        return
                    if param_value is None:
                        QMessageBox.warning(self, "警告", f"参数 '{param_name}' 的值不能为空")
                        return
                
                # 检查策略ID是否已存在
                existing_strategy = self.strategy_service.get_strategy_config(strategy_id)
                if existing_strategy:
                    QMessageBox.warning(self, "警告", f"策略ID '{strategy_id}' 已存在，请使用其他ID")
                    return
                
                # 调用后端API创建策略
                success = self.strategy_service.create_strategy_config(
                    strategy_id=strategy_id,
                    plugin_type=config_data['plugin_type'],
                    parameters=parameters,
                    metadata=config_data.get('metadata', {})
                )
                
                if success:
                    QMessageBox.information(self, "成功", f"策略创建成功！\n策略ID: {strategy_id}")
                    self._load_strategies()
                else:
                    QMessageBox.warning(self, "警告", "策略创建失败")
                    
        except Exception as e:
            logger.error(f"创建策略失败: {e}")
            QMessageBox.critical(self, "错误", f"创建策略失败: {str(e)}")

    def _import_strategy(self):
        """导入策略"""
        try:
            # 检查策略服务
            if not self.strategy_service:
                logger.warning("策略服务未初始化")
                QMessageBox.warning(self, "警告", "策略服务未初始化")
                return
            
            # 选择文件
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "导入策略",
                "",
                "策略文件 (*.json);;所有文件 (*.*)"
            )
            
            if not file_path:
                return
            
            # 读取策略配置
            with open(file_path, 'r', encoding='utf-8') as f:
                strategy_data = json.load(f)
            
            # 验证数据格式
            if not isinstance(strategy_data, dict):
                QMessageBox.warning(self, "警告", "策略文件格式错误：必须是JSON对象")
                return
            
            # 验证必需字段
            required_fields = ['strategy_id', 'plugin_type']
            missing_fields = [field for field in required_fields if field not in strategy_data]
            if missing_fields:
                QMessageBox.warning(self, "警告", f"策略文件缺少必需字段: {', '.join(missing_fields)}")
                return
            
            # 验证策略ID
            strategy_id = strategy_data.get('strategy_id', '').strip()
            if not strategy_id:
                QMessageBox.warning(self, "警告", "策略ID不能为空")
                return
            
            # 验证策略ID格式
            import re
            if not re.match(r'^[a-zA-Z0-9_-]+$', strategy_id):
                QMessageBox.warning(self, "警告", "策略ID只能包含字母、数字、下划线和连字符")
                return
            
            # 验证插件类型
            plugin_type = strategy_data.get('plugin_type', '').strip()
            if not plugin_type:
                QMessageBox.warning(self, "警告", "插件类型不能为空")
                return
            
            # 验证参数格式
            parameters = strategy_data.get('parameters', {})
            if not isinstance(parameters, dict):
                QMessageBox.warning(self, "警告", "参数格式错误：必须是对象")
                return
            
            # 验证元数据格式
            metadata = strategy_data.get('metadata', {})
            if not isinstance(metadata, dict):
                QMessageBox.warning(self, "警告", "元数据格式错误：必须是对象")
                return
            
            # 检查策略ID是否已存在
            existing_strategy = self.strategy_service.get_strategy_config(strategy_id)
            if existing_strategy:
                reply = QMessageBox.question(
                    self,
                    "确认",
                    f"策略ID '{strategy_id}' 已存在，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
            
            # 调用后端API创建策略
            success = self.strategy_service.create_strategy_config(
                strategy_id=strategy_id,
                plugin_type=plugin_type,
                parameters=parameters,
                metadata=metadata
            )
            
            if success:
                QMessageBox.information(self, "成功", f"策略导入成功！\n策略ID: {strategy_id}")
                self._load_strategies()
            else:
                QMessageBox.warning(self, "警告", "策略导入失败")
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            QMessageBox.critical(self, "错误", f"策略文件格式错误：无法解析JSON文件\n{str(e)}")
        except FileNotFoundError:
            logger.error(f"文件不存在: {file_path}")
            QMessageBox.critical(self, "错误", f"文件不存在: {file_path}")
        except Exception as e:
            logger.error(f"导入策略失败: {e}")
            QMessageBox.critical(self, "错误", f"导入策略失败: {str(e)}")

    def _export_strategy(self):
        """导出策略"""
        try:
            # 获取选中的策略
            selected_rows = self._get_selected_strategy_rows()
            
            if not selected_rows:
                QMessageBox.warning(self, "警告", "请先选择要导出的策略")
                return
            
            if len(selected_rows) > 1:
                QMessageBox.warning(self, "警告", "请只选择一个策略进行导出")
                return
            
            # 获取策略ID
            row = selected_rows[0]
            strategy_id_item = self.strategy_table.item(row, 1)
            strategy_id = strategy_id_item.text() if strategy_id_item else None
            
            if not strategy_id:
                QMessageBox.warning(self, "警告", "无法获取策略ID")
                return
            
            # 从策略服务获取策略配置（使用公共API）
            strategy_config = self.strategy_service.get_strategy_config(strategy_id)
            
            if strategy_config:
                # 转换为可序列化的字典
                strategy_data = {
                    'strategy_id': strategy_config.strategy_id,
                    'plugin_type': strategy_config.plugin_type,
                    'parameters': strategy_config.parameters,
                    'enabled': strategy_config.enabled,
                    'metadata': strategy_config.metadata
                }
                
                # 选择保存路径
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "导出策略",
                    f"{strategy_id}.json",
                    "策略文件 (*.json);;所有文件 (*.*)"
                )
                
                if file_path:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(strategy_data, f, indent=2, ensure_ascii=False, default=str)
                    
                    QMessageBox.information(self, "成功", f"策略导出成功！\n保存路径: {file_path}")
            else:
                QMessageBox.warning(self, "警告", "无法获取策略配置")
                
        except Exception as e:
            logger.error(f"导出策略失败: {e}")
            QMessageBox.critical(self, "错误", f"导出策略失败: {str(e)}")

    def _edit_strategy(self, strategy_id: str):
        """编辑策略"""
        try:
            # 从策略服务获取策略配置（使用公共API）
            strategy_config = self.strategy_service.get_strategy_config(strategy_id)
            
            if not strategy_config:
                QMessageBox.warning(self, "警告", "无法获取策略配置")
                return
            
            # 创建策略编辑对话框
            dialog = StrategyConfigDialog(self, strategy_config)
            if dialog.exec_() == QDialog.Accepted:
                config_data = dialog.get_config_data()
                
                # 调用后端API更新策略
                success = self.strategy_service.update_strategy_config(
                    strategy_id=strategy_id,
                    plugin_type=config_data['plugin_type'],
                    parameters=config_data['parameters'],
                    metadata=config_data.get('metadata', {})
                )
                
                if success:
                    QMessageBox.information(self, "成功", "策略更新成功")
                    self._load_strategies()
                else:
                    QMessageBox.warning(self, "警告", "策略更新失败")
                    
        except Exception as e:
            logger.error(f"编辑策略失败: {e}")
            QMessageBox.critical(self, "错误", f"编辑策略失败: {str(e)}")

    def _delete_strategy(self, strategy_id: str):
        """删除策略"""
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除策略 '{strategy_id}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 调用后端API
            if self.strategy_service:
                success = self.strategy_service.delete_strategy_config(strategy_id)
                if success:
                    QMessageBox.information(self, "成功", "策略删除成功")
                    self._load_strategies()  # 刷新列表
                else:
                    QMessageBox.warning(self, "失败", "策略删除失败")
    
    def _batch_update_default_account(self):
        """批量修改默认账号"""
        try:
            # 获取选中的策略
            selected_strategy_ids = []
            for row in range(self.strategy_table.rowCount()):
                checkbox_item = self.strategy_table.item(row, 0)
                if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                    strategy_id_item = self.strategy_table.item(row, 1)
                    if strategy_id_item:
                        selected_strategy_ids.append(strategy_id_item.text())
            
            if not selected_strategy_ids:
                QMessageBox.warning(self, "提示", "请先选择要修改的策略")
                return
            
            # 获取账号管理器
            account_manager = None
            try:
                from core.trading.account_manager import AccountManager
                account_manager = self.service_container.resolve(AccountManager)
            except Exception as e:
                logger.error(f"获取账号管理器失败: {e}")
            
            # 打开批量修改对话框
            dialog = BatchUpdateDefaultAccountDialog(
                self,
                strategy_ids=selected_strategy_ids,
                strategy_service=self.strategy_service,
                account_manager=account_manager
            )
            
            if dialog.exec_() == QDialog.Accepted:
                # 获取选中的账号
                selected_account = dialog.get_selected_account()
                
                # 批量更新策略
                success_count = 0
                failed_count = 0
                
                for strategy_id in selected_strategy_ids:
                    try:
                        # 获取策略配置
                        strategy_config = self.strategy_service.get_strategy_config(strategy_id)
                        
                        if strategy_config:
                            # 更新 metadata 中的 default_account_id
                            strategy_config.metadata['default_account_id'] = selected_account
                            
                            # 保存策略配置
                            success = self.strategy_service.update_strategy_config(strategy_config)
                            
                            if success:
                                success_count += 1
                            else:
                                failed_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.error(f"更新策略 {strategy_id} 失败: {e}")
                        failed_count += 1
                
                # 刷新策略列表
                self._load_strategies()
                
                # 显示结果
                if failed_count == 0:
                    QMessageBox.information(
                        self, "成功",
                        f"成功更新 {success_count} 个策略的默认账号"
                    )
                else:
                    QMessageBox.warning(
                        self, "部分成功",
                        f"成功更新 {success_count} 个策略，失败 {failed_count} 个策略"
                    )
        
        except Exception as e:
            logger.error(f"批量修改默认账号失败: {e}")
            QMessageBox.critical(self, "错误", f"批量修改默认账号失败: {e}")

    def _get_real_market_data(self, start_date: str, end_date: str, timeframe: TimeFrame, symbol: str = '000001') -> StandardMarketData:
        """从真实数据源获取市场数据"""
        try:
            data_manager = UnifiedDataManager()
            
            timeframe_map = {
                TimeFrame.DAY_1: 'D',
                TimeFrame.HOUR_1: '60',
                TimeFrame.MINUTE_30: '30',
                TimeFrame.MINUTE_15: '15',
                TimeFrame.MINUTE_5: '5',
                TimeFrame.MINUTE_1: '1'
            }
            period = timeframe_map.get(timeframe, 'D')
            
            df = data_manager.get_kdata_from_source(
                stock_code=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                count=365
            )
            
            if df is None or df.empty:
                logger.warning(f"无法获取 {symbol} 的历史数据，使用默认股票")
                df = data_manager.get_kdata_from_source(
                    stock_code='000001',
                    period=period,
                    count=365
                )
            
            if df is not None and not df.empty:
                return StandardMarketData.from_dataframe(df, symbol=symbol)
            else:
                logger.error(f"无法获取任何历史数据")
                return None
                
        except Exception as e:
            logger.error(f"获取真实市场数据失败: {e}")
            return None

    def _run_backtest(self):
        """运行回测"""
        try:
            # 获取回测配置
            strategy_id = self.backtest_strategy_combo.currentData()
            if not strategy_id:
                QMessageBox.warning(self, "警告", "请选择策略")
                return
            
            start_date = self.backtest_start_date.date().toString("yyyy-MM-dd")
            end_date = self.backtest_end_date.date().toString("yyyy-MM-dd")
            initial_capital = self.backtest_initial_capital.value()
            commission_rate = self.backtest_commission_rate.value()
            timeframe = self.backtest_timeframe_combo.currentData()
            
            # 获取股票代码（如果有选择的话）
            symbol = getattr(self, 'backtest_symbol_combo', None)
            if symbol and hasattr(symbol, 'currentText'):
                symbol = symbol.currentText()
            else:
                symbol = '000001'
            
            # 从真实数据源获取市场数据
            market_data = self._get_real_market_data(start_date, end_date, timeframe, symbol)
            
            if market_data is None:
                QMessageBox.warning(self, "警告", "无法获取历史数据，请检查数据源配置")
                return
            
            context = StrategyContext(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                commission_rate=commission_rate
            )
            
            # 更新UI状态
            self.backtest_progress_bar.setValue(0)
            self.backtest_status_label.setText("正在初始化回测...")
            self.cancel_backtest_button.setEnabled(True)
            self.run_backtest_button.setEnabled(False)
            
            # 调用后端API启动回测（异步调用）
            if self.strategy_service:
                # 使用asyncio运行异步方法
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 如果事件循环正在运行，使用create_task
                        asyncio.create_task(self._run_backtest_async(strategy_id, market_data, context))
                    else:
                        # 如果事件循环未运行，使用run_until_complete
                        backtest_id = loop.run_until_complete(
                            self.strategy_service.run_backtest(strategy_id, market_data, context)
                        )
                        if backtest_id:
                            self.current_backtest_id = backtest_id
                            self.backtest_status_label.setText(f"回测已启动 (ID: {backtest_id})")
                            logger.info(f"回测已启动: {backtest_id}")
                            
                            # 启动进度监控
                            self._monitor_backtest_progress(backtest_id)
                        else:
                            QMessageBox.warning(self, "警告", "回测启动失败")
                            self._reset_backtest_ui()
                except RuntimeError as e:
                    logger.error(f"事件循环错误: {e}")
                    QMessageBox.critical(self, "错误", f"事件循环错误: {str(e)}")
                    self._reset_backtest_ui()
            else:
                logger.warning("策略服务未初始化")
                QMessageBox.warning(self, "警告", "策略服务未初始化")
                self._reset_backtest_ui()
                
        except Exception as e:
            logger.error(f"运行回测失败: {e}")
            QMessageBox.critical(self, "错误", f"运行回测失败: {str(e)}")
            self._reset_backtest_ui()

    async def _run_backtest_async(self, strategy_id: str, market_data: StandardMarketData, context: StrategyContext):
        """异步运行回测（用于事件循环运行时）"""
        try:
            backtest_id = await self.strategy_service.run_backtest(strategy_id, market_data, context)
            if backtest_id:
                self.current_backtest_id = backtest_id
                self.backtest_status_label.setText(f"回测已启动 (ID: {backtest_id})")
                logger.info(f"回测已启动: {backtest_id}")
                
                # 启动进度监控
                self._monitor_backtest_progress(backtest_id)
            else:
                QMessageBox.warning(self, "警告", "回测启动失败")
                self._reset_backtest_ui()
        except Exception as e:
            logger.error(f"异步回测失败: {e}")
            QMessageBox.critical(self, "错误", f"异步回测失败: {str(e)}")
            self._reset_backtest_ui()

    def _batch_backtest(self):
        """批量回测"""
        try:
            # 获取选中的策略
            selected_rows = self._get_selected_strategy_rows()
            
            if not selected_rows:
                QMessageBox.warning(self, "警告", "请先选择要回测的策略")
                return
            
            # 获取回测配置
            start_date = self.backtest_start_date.date().toString("yyyy-MM-dd")
            end_date = self.backtest_end_date.date().toString("yyyy-MM-dd")
            initial_capital = self.backtest_initial_capital.value()
            commission_rate = self.backtest_commission_rate.value()
            timeframe = self.backtest_timeframe_combo.currentData()
            
            # 获取股票代码（如果有选择的话）
            symbol = getattr(self, 'backtest_symbol_combo', None)
            if symbol and hasattr(symbol, 'currentText'):
                symbol = symbol.currentText()
            else:
                symbol = '000001'
            
            # 从真实数据源获取市场数据
            market_data = self._get_real_market_data(start_date, end_date, timeframe, symbol)
            
            if market_data is None:
                QMessageBox.warning(self, "警告", "无法获取历史数据，请检查数据源配置")
                return
            
            context = StrategyContext(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                commission_rate=commission_rate
            )
            
            # 更新UI状态
            self.backtest_progress_bar.setValue(0)
            self.backtest_status_label.setText(f"正在启动 {len(selected_rows)} 个回测任务...")
            self.cancel_backtest_button.setEnabled(True)
            
            # 调用后端API启动批量回测
            backtest_ids = []
            if self.strategy_service:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 如果事件循环正在运行，使用异步任务
                        asyncio.create_task(self._run_batch_backtest_async(selected_rows, market_data, context))
                    else:
                        # 如果事件循环未运行，使用同步方式
                        for row in selected_rows:
                            strategy_id_item = self.strategy_table.item(row, 1)
                            if strategy_id_item:
                                try:
                                    backtest_id = loop.run_until_complete(
                                        self.strategy_service.run_backtest(strategy_id_item.text(), market_data, context)
                                    )
                                    if backtest_id:
                                        backtest_ids.append(backtest_id)
                                except Exception as e:
                                    logger.error(f"启动回测失败: {strategy_id_item.text()}, 错误: {e}")
                        
                        if backtest_ids:
                            self.current_batch_backtest_ids = backtest_ids
                            self.backtest_status_label.setText(f"批量回测已启动 ({len(backtest_ids)} 个任务)")
                            logger.info(f"批量回测已启动: {len(backtest_ids)} 个任务")
                            
                            # 启动进度监控
                            self._monitor_batch_backtest_progress(backtest_ids)
                        else:
                            QMessageBox.warning(self, "警告", "批量回测启动失败")
                            self._reset_backtest_ui()
                except RuntimeError as e:
                    logger.error(f"事件循环错误: {e}")
                    QMessageBox.critical(self, "错误", f"事件循环错误: {str(e)}")
                    self._reset_backtest_ui()
            else:
                logger.warning("策略服务未初始化")
                QMessageBox.warning(self, "警告", "策略服务未初始化")
                self._reset_backtest_ui()
                
        except Exception as e:
            logger.error(f"批量回测失败: {e}")
            QMessageBox.critical(self, "错误", f"批量回测失败: {str(e)}")
            self._reset_backtest_ui()

    async def _run_batch_backtest_async(self, selected_rows: List[int], market_data: StandardMarketData, context: StrategyContext):
        """异步运行批量回测（用于事件循环运行时）"""
        backtest_ids = []
        try:
            for row in selected_rows:
                strategy_id_item = self.strategy_table.item(row, 1)
                if strategy_id_item:
                    try:
                        backtest_id = await self.strategy_service.run_backtest(strategy_id_item.text(), market_data, context)
                        if backtest_id:
                            backtest_ids.append(backtest_id)
                    except Exception as e:
                        logger.error(f"启动回测失败: {strategy_id_item.text()}, 错误: {e}")
            
            if backtest_ids:
                self.current_batch_backtest_ids = backtest_ids
                self.backtest_status_label.setText(f"批量回测已启动 ({len(backtest_ids)} 个任务)")
                logger.info(f"批量回测已启动: {len(backtest_ids)} 个任务)")
                
                # 启动进度监控
                self._monitor_batch_backtest_progress(backtest_ids)
            else:
                QMessageBox.warning(self, "警告", "批量回测启动失败")
                self._reset_backtest_ui()
        except Exception as e:
            logger.error(f"异步批量回测失败: {e}")
            QMessageBox.critical(self, "错误", f"异步批量回测失败: {str(e)}")
            self._reset_backtest_ui()

    def _parameter_scan(self):
        """参数扫描"""
        try:
            strategy_id = self.backtest_strategy_combo.currentData()
            if not strategy_id:
                QMessageBox.warning(self, "警告", "请选择策略")
                return
            
            # 获取策略配置
            strategy_config = self.strategy_service.get_strategy_config(strategy_id)
            if not strategy_config:
                QMessageBox.warning(self, "警告", "无法获取策略配置")
                return
            
            # 创建并显示参数扫描对话框
            dialog = ParameterScanDialog(self, strategy_id, strategy_config, self.strategy_service)
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"参数扫描失败: {e}")
            QMessageBox.critical(self, "错误", f"参数扫描失败: {str(e)}")

    def _monitor_backtest_progress(self, backtest_id: str):
        """监控回测进度"""
        try:
            # 创建定时器监控进度
            if not hasattr(self, 'backtest_timer'):
                self.backtest_timer = QTimer()
                self.backtest_timer.timeout.connect(self._check_backtest_status)
            
            self.current_backtest_id = backtest_id
            self.backtest_start_time = time.time()  # 记录开始时间
            self.backtest_timeout = 600  # 10分钟超时
            self.backtest_timer.start(1000)  # 每秒检查一次
            
        except Exception as e:
            logger.error(f"监控回测进度失败: {e}")

    def _check_backtest_status(self):
        """检查回测状态"""
        try:
            if not hasattr(self, 'current_backtest_id') or not self.current_backtest_id:
                return
            
            # 检查是否超时
            if hasattr(self, 'backtest_start_time') and hasattr(self, 'backtest_timeout'):
                elapsed_time = time.time() - self.backtest_start_time
                if elapsed_time > self.backtest_timeout:
                    self.backtest_status_label.setText("回测超时")
                    self._reset_backtest_ui()
                    QMessageBox.warning(self, "警告", f"回测超时（超过{self.backtest_timeout // 60}分钟），已自动取消")
                    
                    # 停止定时器
                    if hasattr(self, 'backtest_timer'):
                        self.backtest_timer.stop()
                    return
            
            # 调用后端API获取回测状态
            if self.strategy_service:
                status_info = self.strategy_service.get_backtest_status(self.current_backtest_id)
                
                if status_info:
                    # 更新进度条
                    progress = status_info.get('progress', 0)
                    self.backtest_progress_bar.setValue(int(progress * 100))
                    
                    # 更新状态标签
                    status = status_info.get('status', 'running')
                    if status == 'running':
                        elapsed = int(time.time() - self.backtest_start_time) if hasattr(self, 'backtest_start_time') else 0
                        self.backtest_status_label.setText(f"回测进行中... {int(progress * 100)}% (已运行{elapsed}秒)")
                    elif status == 'completed':
                        self.backtest_status_label.setText("回测完成")
                        self.backtest_progress_bar.setValue(100)
                        self._reset_backtest_ui()
                        
                        # 加载回测结果
                        self._load_backtest_results(self.current_backtest_id)
                        
                        # 停止定时器
                        if hasattr(self, 'backtest_timer'):
                            self.backtest_timer.stop()
                    elif status == 'error' or status == 'failed':
                        self.backtest_status_label.setText("回测失败")
                        self._reset_backtest_ui()
                        error_message = status_info.get('error_message', '未知错误')
                        QMessageBox.warning(self, "警告", f"回测失败: {error_message}")
                        
                        # 停止定时器
                        if hasattr(self, 'backtest_timer'):
                            self.backtest_timer.stop()
                else:
                    logger.warning(f"无法获取回测状态: {self.current_backtest_id}")
                    
        except Exception as e:
            logger.error(f"检查回测状态失败: {e}")

    def _monitor_batch_backtest_progress(self, backtest_ids: List[str]):
        """监控批量回测进度"""
        try:
            # 创建定时器监控进度
            if not hasattr(self, 'batch_backtest_timer'):
                self.batch_backtest_timer = QTimer()
                self.batch_backtest_timer.timeout.connect(self._check_batch_backtest_status)
            
            self.current_batch_backtest_ids = backtest_ids
            self.batch_backtest_timer.start(1000)  # 每秒检查一次
            
        except Exception as e:
            logger.error(f"监控批量回测进度失败: {e}")

    def _check_batch_backtest_status(self):
        """检查批量回测状态"""
        try:
            if not hasattr(self, 'current_batch_backtest_ids') or not self.current_batch_backtest_ids:
                return
            
            # 调用后端API获取批量回测状态
            if self.strategy_service:
                status_list = self.strategy_service.get_batch_backtest_status(self.current_batch_backtest_ids)
                
                if status_list:
                    # 计算总体进度
                    total_progress = sum(s.get('progress', 0) for s in status_list) / len(status_list)
                    self.backtest_progress_bar.setValue(int(total_progress * 100))
                    
                    # 统计状态
                    completed_count = sum(1 for s in status_list if s.get('status') == 'completed')
                    running_count = sum(1 for s in status_list if s.get('status') == 'running')
                    failed_count = sum(1 for s in status_list if s.get('status') == 'failed')
                    cancelled_count = sum(1 for s in status_list if s.get('status') == 'cancelled')
                    error_count = failed_count + cancelled_count
                    
                    self.backtest_status_label.setText(
                        f"批量回测进度: {completed_count}/{len(status_list)} 完成, "
                        f"{running_count} 运行中, {error_count} 错误"
                    )
                    
                    # 检查是否全部完成
                    if completed_count + error_count == len(status_list):
                        self._reset_backtest_ui()
                        
                        # 停止定时器
                        if hasattr(self, 'batch_backtest_timer'):
                            self.batch_backtest_timer.stop()
                            
                        QMessageBox.information(self, "完成", f"批量回测完成！\n成功: {completed_count}, 失败: {error_count}")
                else:
                    logger.warning("无法获取批量回测状态")
                    
        except Exception as e:
            logger.error(f"检查批量回测状态失败: {e}")

    def _load_backtest_results(self, backtest_id: str):
        """加载回测结果"""
        try:
            # 调用后端API获取回测结果
            if self.strategy_service:
                result = self.strategy_service.get_backtest_result(backtest_id)
                
                if result:
                    # 转换为字典格式
                    results = {
                        'total_return': result.total_return,
                        'sharpe_ratio': result.sharpe_ratio,
                        'max_drawdown': result.max_drawdown,
                        'win_rate': result.win_rate,
                        'equity_curve': self._convert_equity_curve(result),
                        'drawdown_curve': self._convert_drawdown_curve(result),
                        'trades': self._convert_trades(result)
                    }
                    
                    # 更新性能指标卡片
                    self._update_backtest_metrics(results)
                    
                    # 更新图表
                    self._update_backtest_charts(results)
                    
                    logger.info(f"回测结果加载成功: {backtest_id}")
                else:
                    logger.warning(f"无法获取回测结果: {backtest_id}")
                    
        except Exception as e:
            logger.error(f"加载回测结果失败: {e}")

    def _convert_equity_curve(self, result) -> List[Dict[str, Any]]:
        """转换权益曲线数据"""
        try:
            # 从PerformanceMetrics中提取权益曲线数据
            equity_curve = []
            if hasattr(result, 'equity_curve') and result.equity_curve is not None:
                base_date = datetime(2024, 1, 1)
                for i, value in enumerate(result.equity_curve):
                    current_date = base_date + timedelta(days=i)
                    equity_curve.append({
                        'date': current_date.strftime('%Y-%m-%d'),
                        'value': value
                    })
            return equity_curve
        except Exception as e:
            logger.error(f"转换权益曲线数据失败: {e}")
            return []

    def _convert_drawdown_curve(self, result) -> List[Dict[str, Any]]:
        """转换回撤曲线数据"""
        try:
            # 从PerformanceMetrics中提取回撤曲线数据
            drawdown_curve = []
            if hasattr(result, 'drawdown_curve') and result.drawdown_curve is not None:
                base_date = datetime(2024, 1, 1)
                for i, value in enumerate(result.drawdown_curve):
                    current_date = base_date + timedelta(days=i)
                    drawdown_curve.append({
                        'date': current_date.strftime('%Y-%m-%d'),
                        'value': value
                    })
            return drawdown_curve
        except Exception as e:
            logger.error(f"转换回撤曲线数据失败: {e}")
            return []

    def _convert_trades(self, result) -> List[Dict[str, Any]]:
        """转换交易记录数据"""
        try:
            # 从PerformanceMetrics中提取交易记录数据
            trades = []
            if hasattr(result, 'trades') and result.trades is not None:
                for trade in result.trades:
                    trades.append({
                        'date': trade.entry_time.strftime('%Y-%m-%d') if hasattr(trade, 'entry_time') else '2024-01-01',
                        'pnl': trade.pnl if hasattr(trade, 'pnl') else 0
                    })
            return trades
        except Exception as e:
            logger.error(f"转换交易记录数据失败: {e}")
            return []

    def _update_backtest_metrics(self, results: Dict[str, Any]):
        """更新回测性能指标"""
        try:
            # 获取性能指标
            total_return = results.get('total_return', 0)
            sharpe_ratio = results.get('sharpe_ratio', 0)
            max_drawdown = results.get('max_drawdown', 0)
            win_rate = results.get('win_rate', 0)
            
            # 更新卡片显示
            self._update_metric_card(self.total_return_card, f"{total_return:.2f}%")
            self._update_metric_card(self.sharpe_ratio_card, f"{sharpe_ratio:.2f}")
            self._update_metric_card(self.max_drawdown_card, f"{max_drawdown:.2f}%")
            self._update_metric_card(self.win_rate_card, f"{win_rate:.2f}%")
            
        except Exception as e:
            logger.error(f"更新回测指标失败: {e}")

    def _update_metric_card(self, card: QWidget, value: str):
        """更新指标卡片值"""
        try:
            value_label = card.findChild(QLabel, "value_label")
            if value_label:
                value_label.setText(value)
        except Exception as e:
            logger.error(f"更新指标卡片失败: {e}")

    def _update_backtest_charts(self, results: Dict[str, Any]):
        """更新回测图表"""
        try:
            # 获取图表数据
            equity_curve = results.get('equity_curve', [])
            drawdown_curve = results.get('drawdown_curve', [])
            trades = results.get('trades', [])
            
            # 更新权益曲线图
            if equity_curve and hasattr(self, 'equity_chart'):
                self._update_equity_chart(equity_curve)
            
            # 更新回撤分析图
            if drawdown_curve and hasattr(self, 'drawdown_chart'):
                self._update_drawdown_chart(drawdown_curve)
            
            # 更新交易记录图
            if trades and hasattr(self, 'trades_chart'):
                self._update_trades_chart(trades)
                
        except Exception as e:
            logger.error(f"更新回测图表失败: {e}")

    def _update_equity_chart(self, equity_curve: List[Dict[str, Any]]):
        """更新权益曲线图"""
        try:
            if not MATPLOTLIB_AVAILABLE:
                return
            
            ax = self.equity_chart.figure.axes[0]
            ax.clear()
            
            # 提取数据
            dates = [pd.to_datetime(d['date']) for d in equity_curve]
            values = [d['value'] for d in equity_curve]
            
            # 绘制曲线
            ax.plot(dates, values, color=FINANCIAL_COLORS['profit'], linewidth=1, label='策略收益')
            ax.axhline(y=values[0], color=FINANCIAL_COLORS['primary'], linestyle='--', alpha=0.5, label='基准线')
            
            ax.set_title("策略权益曲线", fontsize=14, fontweight='bold')
            ax.set_xlabel("日期", fontsize=12)
            ax.set_ylabel("累计收益率", fontsize=12)
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            self.equity_chart.draw()
            
        except Exception as e:
            logger.error(f"更新权益曲线图失败: {e}")

    def _update_drawdown_chart(self, drawdown_curve: List[Dict[str, Any]]):
        """更新回撤分析图"""
        try:
            if not MATPLOTLIB_AVAILABLE:
                return
            
            ax = self.drawdown_chart.figure.axes[0]
            ax.clear()
            
            # 提取数据
            dates = [pd.to_datetime(d['date']) for d in drawdown_curve]
            values = [d['value'] for d in drawdown_curve]
            
            # 绘制曲线（使用红色表示回撤）
            ax.fill_between(dates, values, 0, color=FINANCIAL_COLORS['loss'], alpha=0.3)
            ax.plot(dates, values, color=FINANCIAL_COLORS['loss'], linewidth=1, label='回撤')
            
            ax.set_title("回撤分析", fontsize=14, fontweight='bold')
            ax.set_xlabel("日期", fontsize=12)
            ax.set_ylabel("回撤率 (%)", fontsize=12)
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            self.drawdown_chart.draw()
            
        except Exception as e:
            logger.error(f"更新回撤分析图失败: {e}")

    def _update_trades_chart(self, trades: List[Dict[str, Any]]):
        """更新交易记录图"""
        try:
            if not MATPLOTLIB_AVAILABLE:
                return
            
            ax = self.trades_chart.figure.axes[0]
            ax.clear()
            
            # 提取数据
            dates = [pd.to_datetime(t['date']) for t in trades]
            pnl = [t['pnl'] for t in trades]
            
            # 绘制交易盈亏
            colors = [FINANCIAL_COLORS['profit'] if p >= 0 else FINANCIAL_COLORS['loss'] for p in pnl]
            ax.bar(dates, pnl, color=colors, alpha=0.7)
            
            ax.set_title("交易记录", fontsize=14, fontweight='bold')
            ax.set_xlabel("日期", fontsize=12)
            ax.set_ylabel("盈亏", fontsize=12)
            ax.grid(True, alpha=0.3)
            ax.axhline(y=0, color=FINANCIAL_COLORS['primary'], linestyle='-', alpha=0.5)
            
            self.trades_chart.draw()
            
        except Exception as e:
            logger.error(f"更新交易记录图失败: {e}")

    def _cancel_backtest(self):
        """取消回测"""
        try:
            # 取消单个回测
            if hasattr(self, 'current_backtest_id') and self.current_backtest_id:
                if self.strategy_service:
                    success = self.strategy_service.cancel_backtest(self.current_backtest_id)
                    
                    if success:
                        self.backtest_status_label.setText("回测已取消")
                        self._reset_backtest_ui()
                        
                        # 停止定时器
                        if hasattr(self, 'backtest_timer'):
                            self.backtest_timer.stop()
                            
                        QMessageBox.information(self, "成功", "回测已取消")
                    else:
                        QMessageBox.warning(self, "警告", "取消回测失败")
            
            # 取消批量回测
            elif hasattr(self, 'current_batch_backtest_ids') and self.current_batch_backtest_ids:
                if self.strategy_service:
                    success = self.strategy_service.cancel_batch_backtest(self.current_batch_backtest_ids)
                    
                    if success:
                        self.backtest_status_label.setText("批量回测已取消")
                        self._reset_backtest_ui()
                        
                        # 停止定时器
                        if hasattr(self, 'batch_backtest_timer'):
                            self.batch_backtest_timer.stop()
                            
                        QMessageBox.information(self, "成功", "批量回测已取消")
                    else:
                        QMessageBox.warning(self, "警告", "取消批量回测失败")
            else:
                QMessageBox.warning(self, "警告", "没有正在运行的回测任务")
                
        except Exception as e:
            logger.error(f"取消回测失败: {e}")
            QMessageBox.critical(self, "错误", f"取消回测失败: {str(e)}")

    def _reset_backtest_ui(self):
        """重置回测UI状态"""
        self.run_backtest_button.setEnabled(True)
        self.cancel_backtest_button.setEnabled(False)

    def _start_optimization(self):
        """开始优化"""
        try:
            # 获取优化配置
            strategy_id = self.opt_strategy_combo.currentData()
            if not strategy_id:
                QMessageBox.warning(self, "警告", "请选择策略")
                return
            
            algorithm = self.opt_algorithm_combo.currentText()
            target_metric = self.opt_target_metric_combo.currentText()
            max_iterations = self.opt_max_iterations.value()
            timeframe = self.opt_timeframe_combo.currentData()
            
            # 获取参数范围
            param_ranges = self._get_optimization_param_ranges()
            
            if not param_ranges:
                QMessageBox.warning(self, "警告", "请至少配置一个参数范围")
                return
            
            # 从真实数据源获取市场数据
            market_data = self._get_real_market_data('2023-01-01', '2024-01-01', timeframe, '000001')
            
            if market_data is None:
                QMessageBox.warning(self, "警告", "无法获取历史数据，请检查数据源配置")
                return
            
            context = StrategyContext(
                symbol='000001',
                timeframe=timeframe,
                start_date='2023-01-01',
                end_date='2024-01-01',
                initial_capital=100000,
                commission_rate=0.0003
            )
            
            # 构建优化参数
            optimization_params = {
                'algorithm': algorithm,
                'target_metric': target_metric,
                'max_iterations': max_iterations,
                'param_ranges': param_ranges
            }
            
            # 更新UI状态
            self.opt_progress_bar.setValue(0)
            self.opt_iteration_label.setText(f"当前迭代：0/{max_iterations}")
            self.opt_best_value_label.setText("最佳值：0.0000")
            self.cancel_optimization_button.setEnabled(True)
            self.start_optimization_button.setEnabled(False)
            
            # 调用后端API启动优化（异步调用）
            if self.strategy_service:
                # 使用asyncio运行异步方法
                loop = asyncio.get_event_loop()
                optimization_id = loop.run_until_complete(
                    self.strategy_service.run_optimization(strategy_id, optimization_params, market_data, context)
                )
                
                if optimization_id:
                    self.current_optimization_id = optimization_id
                    self.opt_iteration_label.setText(f"优化已启动 (ID: {optimization_id})")
                    logger.info(f"参数优化已启动: {optimization_id}")
                    
                    # 启动进度监控
                    self._monitor_optimization_progress(optimization_id)
                else:
                    QMessageBox.warning(self, "警告", "参数优化启动失败")
                    self._reset_optimization_ui()
            else:
                logger.warning("策略服务未初始化")
                QMessageBox.warning(self, "警告", "策略服务未初始化")
                self._reset_optimization_ui()
                
        except Exception as e:
            logger.error(f"启动参数优化失败: {e}")
            QMessageBox.critical(self, "错误", f"启动参数优化失败: {str(e)}")
            self._reset_optimization_ui()

    def _get_optimization_param_ranges(self) -> List[Dict[str, Any]]:
        """获取优化参数范围"""
        param_ranges = []
        
        for row in range(self.opt_param_table.rowCount()):
            name_item = self.opt_param_table.item(row, 0)
            min_item = self.opt_param_table.item(row, 1)
            max_item = self.opt_param_table.item(row, 2)
            step_item = self.opt_param_table.item(row, 3)
            type_item = self.opt_param_table.item(row, 4)
            
            if name_item and min_item and max_item and step_item and type_item:
                param_ranges.append({
                    'name': name_item.text(),
                    'min': float(min_item.text()),
                    'max': float(max_item.text()),
                    'step': float(step_item.text()),
                    'type': type_item.text()
                })
        
        return param_ranges

    def _monitor_optimization_progress(self, optimization_id: str):
        """监控优化进度"""
        try:
            # 创建定时器监控进度
            if not hasattr(self, 'optimization_timer'):
                self.optimization_timer = QTimer()
                self.optimization_timer.timeout.connect(self._check_optimization_status)
            
            self.current_optimization_id = optimization_id
            self.optimization_start_time = time.time()  # 记录开始时间
            self.optimization_timeout = 1800  # 30分钟超时
            self.optimization_timer.start(1000)  # 每秒检查一次
            
        except Exception as e:
            logger.error(f"监控优化进度失败: {e}")

    def _check_optimization_status(self):
        """检查优化状态"""
        try:
            if not hasattr(self, 'current_optimization_id') or not self.current_optimization_id:
                return
            
            # 检查是否超时
            if hasattr(self, 'optimization_start_time') and hasattr(self, 'optimization_timeout'):
                elapsed_time = time.time() - self.optimization_start_time
                if elapsed_time > self.optimization_timeout:
                    self.opt_iteration_label.setText("优化超时")
                    self._reset_optimization_ui()
                    QMessageBox.warning(self, "警告", f"优化超时（超过{self.optimization_timeout // 60}分钟），已自动取消")
                    
                    # 停止定时器
                    if hasattr(self, 'optimization_timer'):
                        self.optimization_timer.stop()
                    return
            
            # 调用后端API获取优化状态
            if self.strategy_service:
                status_info = self.strategy_service.get_optimization_status(self.current_optimization_id)
                
                if status_info:
                    # 更新进度条
                    progress = status_info.get('progress', 0)
                    self.opt_progress_bar.setValue(int(progress * 100))
                    
                    # 更新迭代标签
                    iterations_completed = status_info.get('iterations_completed', 0)
                    elapsed = int(time.time() - self.optimization_start_time) if hasattr(self, 'optimization_start_time') else 0
                    self.opt_iteration_label.setText(f"已完成迭代：{iterations_completed} (已运行{elapsed}秒)")
                    
                    # 更新最佳值标签
                    best_performance = status_info.get('best_performance', 0)
                    if best_performance:
                        self.opt_best_value_label.setText(f"最佳值：{best_performance:.4f}")
                    
                    # 更新优化曲线
                    optimization_history = status_info.get('optimization_history', [])
                    if optimization_history:
                        self._update_optimization_chart(optimization_history)
                    
                    # 检查状态
                    status = status_info.get('status', 'running')
                    if status == 'running':
                        pass  # 继续运行
                    elif status == 'completed':
                        self.opt_iteration_label.setText("优化完成")
                        self.opt_progress_bar.setValue(100)
                        self._reset_optimization_ui()
                        
                        # 加载优化结果
                        self._load_optimization_results(self.current_optimization_id)
                        
                        # 停止定时器
                        if hasattr(self, 'optimization_timer'):
                            self.optimization_timer.stop()
                    elif status == 'error' or status == 'failed':
                        self.opt_iteration_label.setText("优化失败")
                        self._reset_optimization_ui()
                        error_message = status_info.get('error_message', '未知错误')
                        QMessageBox.warning(self, "警告", f"参数优化失败: {error_message}")
                        
                        # 停止定时器
                        if hasattr(self, 'optimization_timer'):
                            self.optimization_timer.stop()
                else:
                    logger.warning(f"无法获取优化状态: {self.current_optimization_id}")
                    
        except Exception as e:
            logger.error(f"检查优化状态失败: {e}")

    def _load_optimization_results(self, optimization_id: str):
        """加载优化结果"""
        try:
            # 调用后端API获取优化结果
            if self.strategy_service:
                result = self.strategy_service.get_optimization_result(optimization_id)
                
                if result:
                    # 转换为字典格式
                    results = {
                        'best_params': result.get('best_parameters', {}),
                        'current_params': {},  # 当前参数需要从策略配置中获取
                        'strategy_id': self.current_optimization_id.split('_')[0]  # 从优化任务ID中提取策略ID
                    }
                    
                    # 更新最佳参数表格
                    self._update_best_params_table(results)
                    
                    logger.info(f"优化结果加载成功: {optimization_id}")
                else:
                    logger.warning(f"无法获取优化结果: {optimization_id}")
                    
        except Exception as e:
            logger.error(f"加载优化结果失败: {e}")

    def _update_best_params_table(self, results: Dict[str, Any]):
        """更新最佳参数表格"""
        try:
            best_params = results.get('best_params', {})
            current_params = results.get('current_params', {})
            
            self.best_param_table.setRowCount(len(best_params))
            
            for row, (param_name, best_value) in enumerate(best_params.items()):
                current_value = current_params.get(param_name, 'N/A')
                
                # 计算改进百分比
                improvement = "N/A"
                if isinstance(best_value, (int, float)) and isinstance(current_value, (int, float)):
                    if current_value != 0:
                        improvement_pct = ((best_value - current_value) / abs(current_value)) * 100
                        improvement = f"{improvement_pct:+.1f}%"
                
                # 添加到表格
                self.best_param_table.setItem(row, 0, QTableWidgetItem(param_name))
                self.best_param_table.setItem(row, 1, QTableWidgetItem(str(best_value)))
                self.best_param_table.setItem(row, 2, QTableWidgetItem(str(current_value)))
                
                # 改进列使用颜色
                improvement_item = QTableWidgetItem(improvement)
                if improvement.startswith('+'):
                    improvement_item.setForeground(QColor(FINANCIAL_COLORS['profit']))
                elif improvement.startswith('-'):
                    improvement_item.setForeground(QColor(FINANCIAL_COLORS['loss']))
                
                self.best_param_table.setItem(row, 3, improvement_item)
                
        except Exception as e:
            logger.error(f"更新最佳参数表格失败: {e}")

    def _update_optimization_chart(self, history: List[Dict[str, Any]]):
        """更新优化曲线图"""
        try:
            if not MATPLOTLIB_AVAILABLE or not hasattr(self, 'optimization_chart'):
                return
            
            ax = self.optimization_chart.figure.axes[0]
            ax.clear()
            
            # 提取数据
            iterations = [h['iteration'] for h in history]
            values = [h['value'] for h in history]
            
            # 绘制优化曲线
            ax.plot(iterations, values, color=FINANCIAL_COLORS['primary'], linewidth=1, label='目标值')
            ax.scatter(iterations, values, color=FINANCIAL_COLORS['profit'], s=20, alpha=0.7)
            
            # 标记最佳点
            if values:
                best_idx = values.index(max(values))
                ax.scatter([iterations[best_idx]], [values[best_idx]], 
                          color=FINANCIAL_COLORS['warning'], s=100, marker='*', 
                          label='最佳参数', zorder=5)
            
            ax.set_title("参数优化曲线", fontsize=14, fontweight='bold')
            ax.set_xlabel("迭代次数", fontsize=12)
            ax.set_ylabel("目标值", fontsize=12)
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            self.optimization_chart.draw()
            
        except Exception as e:
            logger.error(f"更新优化曲线图失败: {e}")

    def _add_optimization_param(self):
        """添加优化参数"""
        try:
            # 创建参数配置对话框
            dialog = OptimizationParamDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                param_config = dialog.get_param_config()
                
                # 添加到表格
                row = self.opt_param_table.rowCount()
                self.opt_param_table.insertRow(row)
                
                self.opt_param_table.setItem(row, 0, QTableWidgetItem(param_config['name']))
                self.opt_param_table.setItem(row, 1, QTableWidgetItem(str(param_config['min'])))
                self.opt_param_table.setItem(row, 2, QTableWidgetItem(str(param_config['max'])))
                self.opt_param_table.setItem(row, 3, QTableWidgetItem(str(param_config['step'])))
                self.opt_param_table.setItem(row, 4, QTableWidgetItem(param_config['type']))
                
        except Exception as e:
            logger.error(f"添加优化参数失败: {e}")
            QMessageBox.critical(self, "错误", f"添加优化参数失败: {str(e)}")

    def _import_optimization_ranges(self):
        """导入优化范围"""
        try:
            # 选择文件
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "导入优化范围",
                "",
                "JSON文件 (*.json);;所有文件 (*.*)"
            )
            
            if not file_path:
                return
            
            # 读取参数范围配置
            with open(file_path, 'r', encoding='utf-8') as f:
                param_ranges = json.load(f)
            
            # 清空表格
            self.opt_param_table.setRowCount(0)
            
            # 添加参数范围
            for param_range in param_ranges:
                row = self.opt_param_table.rowCount()
                self.opt_param_table.insertRow(row)
                
                self.opt_param_table.setItem(row, 0, QTableWidgetItem(param_range.get('name', '')))
                self.opt_param_table.setItem(row, 1, QTableWidgetItem(str(param_range.get('min', ''))))
                self.opt_param_table.setItem(row, 2, QTableWidgetItem(str(param_range.get('max', ''))))
                self.opt_param_table.setItem(row, 3, QTableWidgetItem(str(param_range.get('step', ''))))
                self.opt_param_table.setItem(row, 4, QTableWidgetItem(param_range.get('type', 'float')))
            
            QMessageBox.information(self, "成功", f"成功导入 {len(param_ranges)} 个参数范围")
            
        except Exception as e:
            logger.error(f"导入优化范围失败: {e}")
            QMessageBox.critical(self, "错误", f"导入优化范围失败: {str(e)}")

    def _export_optimization_ranges(self):
        """导出优化范围"""
        try:
            # 获取参数范围
            param_ranges = self._get_optimization_param_ranges()
            
            if not param_ranges:
                QMessageBox.warning(self, "警告", "没有可导出的参数范围")
                return
            
            # 选择保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出优化范围",
                "optimization_params.json",
                "JSON文件 (*.json);;所有文件 (*.*)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(param_ranges, f, indent=2, ensure_ascii=False)
                
                QMessageBox.information(self, "成功", f"成功导出 {len(param_ranges)} 个参数范围")
            
        except Exception as e:
            logger.error(f"导出优化范围失败: {e}")
            QMessageBox.critical(self, "错误", f"导出优化范围失败: {str(e)}")

    def _cancel_optimization(self):
        """取消优化"""
        try:
            if hasattr(self, 'current_optimization_id') and self.current_optimization_id:
                if self.strategy_service:
                    success = self.strategy_service.cancel_optimization(self.current_optimization_id)
                    
                    if success:
                        self.opt_iteration_label.setText("优化已取消")
                        self._reset_optimization_ui()
                        
                        # 停止定时器
                        if hasattr(self, 'optimization_timer'):
                            self.optimization_timer.stop()
                            
                        QMessageBox.information(self, "成功", "参数优化已取消")
                    else:
                        QMessageBox.warning(self, "警告", "取消优化失败")
            else:
                QMessageBox.warning(self, "警告", "没有正在运行的优化任务")
                
        except Exception as e:
            logger.error(f"取消优化失败: {e}")
            QMessageBox.critical(self, "错误", f"取消优化失败: {str(e)}")

    def _reset_optimization_ui(self):
        """重置优化UI状态"""
        self.start_optimization_button.setEnabled(True)
        self.cancel_optimization_button.setEnabled(False)

    def _apply_best_parameters(self):
        """应用最佳参数"""
        try:
            if not hasattr(self, 'current_optimization_id') or not self.current_optimization_id:
                QMessageBox.warning(self, "警告", "没有可应用的优化结果")
                return
            
            # 获取优化结果
            if self.strategy_service:
                results = self.strategy_service.get_optimization_results(self.current_optimization_id)
                
                if results:
                    best_params = results.get('best_params', {})
                    strategy_id = results.get('strategy_id', '')
                    
                    # 应用参数到策略
                    success = self.strategy_service.apply_strategy_parameters(strategy_id, best_params)
                    
                    if success:
                        QMessageBox.information(self, "成功", f"成功应用 {len(best_params)} 个参数到策略 {strategy_id}")
                    else:
                        QMessageBox.warning(self, "警告", "应用参数失败")
                else:
                    QMessageBox.warning(self, "警告", "无法获取优化结果")
            else:
                logger.warning("策略服务未初始化")
                QMessageBox.warning(self, "警告", "策略服务未初始化")
                
        except Exception as e:
            logger.error(f"应用最佳参数失败: {e}")
            QMessageBox.critical(self, "错误", f"应用最佳参数失败: {str(e)}")

    def _save_optimization_config(self):
        """保存优化配置"""
        try:
            # 获取优化配置
            strategy_id = self.opt_strategy_combo.currentData()
            algorithm = self.opt_algorithm_combo.currentText()
            target_metric = self.opt_target_metric_combo.currentText()
            max_iterations = self.opt_max_iterations.value()
            param_ranges = self._get_optimization_param_ranges()
            
            config = {
                'strategy_id': strategy_id,
                'algorithm': algorithm,
                'target_metric': target_metric,
                'max_iterations': max_iterations,
                'param_ranges': param_ranges
            }
            
            # 选择保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存优化配置",
                "optimization_config.json",
                "JSON文件 (*.json);;所有文件 (*.*)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                QMessageBox.information(self, "成功", "优化配置保存成功")
            
        except Exception as e:
            logger.error(f"保存优化配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存优化配置失败: {str(e)}")

    def _cleanup(self):
        """清理资源"""
        try:
            # 断开主题订阅
            if hasattr(self, 'theme_manager') and self.theme_manager:
                try:
                    self.theme_manager.theme_changed.disconnect(self._on_theme_changed)
                    logger.info("已断开主题订阅")
                except Exception as e:
                    logger.warning(f"断开主题订阅失败: {e}")
            
            # 停止所有定时器
            timers = ['backtest_timer', 'batch_backtest_timer', 'optimization_timer']
            for timer_name in timers:
                if hasattr(self, timer_name):
                    timer = getattr(self, timer_name)
                    if timer and timer.isActive():
                        timer.stop()
                        logger.info(f"已停止定时器: {timer_name}")
            
            # 取消所有异步任务
            if hasattr(self, 'task_manager') and self.task_manager:
                try:
                    self.task_manager.cancel_all_tasks()
                    logger.info("已取消所有异步任务")
                except Exception as e:
                    logger.warning(f"取消异步任务失败: {e}")
            
            # 清理图表资源
            if hasattr(self, '_cached_charts'):
                chart_count = len(self._cached_charts)
                for chart in self._cached_charts:
                    if chart and hasattr(chart, 'figure'):
                        try:
                            chart.figure.clear()
                            if MATPLOTLIB_AVAILABLE:
                                plt.close(chart.figure)
                        except Exception as e:
                            logger.warning(f"清理图表资源失败: {e}")
                self._cached_charts.clear()
                logger.info(f"已清理 {chart_count} 个图表资源")
            
            # 取消策略事件订阅
            if hasattr(self, '_strategy_event_handler') and self._strategy_event_handler:
                try:
                    from core.events.event_bus import get_event_bus
                    event_bus = get_event_bus()
                    event_bus.unsubscribe_all(self._strategy_event_handler)
                    logger.info("已取消策略事件订阅")
                except Exception as e:
                    logger.warning(f"取消策略事件订阅失败: {e}")
            
            logger.info("资源清理完成")
        except Exception as e:
            logger.error(f"资源清理过程中发生错误: {e}")

    def _sensitivity_analysis(self):
        """敏感性分析"""
        try:
            strategy_id = self.opt_strategy_combo.currentData()
            if not strategy_id:
                QMessageBox.warning(self, "警告", "请选择策略")
                return
            
            # 获取策略配置
            strategy_config = self.strategy_service.get_strategy_config(strategy_id)
            if not strategy_config:
                QMessageBox.warning(self, "警告", "无法获取策略配置")
                return
            
            # 创建并显示敏感性分析对话框
            dialog = SensitivityAnalysisDialog(self, strategy_id, strategy_config, self.strategy_service)
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"敏感性分析失败: {e}")
            QMessageBox.critical(self, "错误", f"敏感性分析失败: {str(e)}")

    def closeEvent(self, event):
        """关闭事件"""
        # 清理资源
        self._cleanup()
        
        event.accept()
        logger.info("策略管理器对话框已关闭")


class OptimizationParamDialog(QDialog):
    """优化参数配置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加优化参数")
        self.setModal(True)
        self.resize(400, 300)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 参数名称
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("参数名称，如：lookback_period")
        
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(-1000000, 1000000)
        self.min_spin.setDecimals(4)
        
        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(-1000000, 1000000)
        self.max_spin.setDecimals(4)
        
        self.step_spin = QDoubleSpinBox()
        self.step_spin.setRange(0.0001, 1000000)
        self.step_spin.setDecimals(4)
        self.step_spin.setValue(1)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(['int', 'float'])
        
        form_layout.addRow("参数名称：", self.name_edit)
        form_layout.addRow("最小值：", self.min_spin)
        form_layout.addRow("最大值：", self.max_spin)
        form_layout.addRow("步长：", self.step_spin)
        form_layout.addRow("类型：", self.type_combo)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
    
    def get_param_config(self) -> Dict[str, Any]:
        """获取参数配置"""
        return {
            'name': self.name_edit.text(),
            'min': self.min_spin.value(),
            'max': self.max_spin.value(),
            'step': self.step_spin.value(),
            'type': self.type_combo.currentText()
        }
    
    def closeEvent(self, event):
        """关闭事件"""
        event.accept()


class SensitivityAnalysisDialog(QDialog):
    """参数敏感性分析对话框"""
    
    def __init__(self, parent=None, strategy_id: str = None, strategy_config: StrategyConfig = None, strategy_service=None):
        super().__init__(parent)
        self.strategy_id = strategy_id
        self.strategy_config = strategy_config
        self.strategy_service = strategy_service
        self.setWindowTitle("参数敏感性分析")
        self.setModal(True)
        self.resize(900, 700)
        
        self.sensitivity_results = {}
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 参数选择区域
        param_group = QGroupBox("参数配置")
        param_layout = QGridLayout(param_group)
        
        # 参数选择
        param_layout.addWidget(QLabel("选择参数："), 0, 0, 1, 1)
        self.param_combo = QComboBox()
        param_layout.addWidget(self.param_combo, 0, 1, 1, 2)
        
        # 参数范围
        param_layout.addWidget(QLabel("最小值："), 1, 0)
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setDecimals(4)
        self.min_spin.setRange(-999999, 999999)
        param_layout.addWidget(self.min_spin, 1, 1)
        
        param_layout.addWidget(QLabel("最大值："), 1, 2)
        self.max_spin = QDoubleSpinBox()
        self.max_spin.setDecimals(4)
        self.max_spin.setRange(-999999, 999999)
        param_layout.addWidget(self.max_spin, 1, 3)
        
        param_layout.addWidget(QLabel("步长："), 2, 0)
        self.step_spin = QDoubleSpinBox()
        self.step_spin.setDecimals(4)
        self.step_spin.setRange(0.0001, 999999)
        self.step_spin.setValue(0.1)
        param_layout.addWidget(self.step_spin, 2, 1)
        
        # 样本点数
        param_layout.addWidget(QLabel("样本点数："), 2, 2)
        self.samples_spin = QSpinBox()
        self.samples_spin.setRange(5, 100)
        self.samples_spin.setValue(10)
        param_layout.addWidget(self.samples_spin, 2, 3)
        
        # 性能指标选择
        param_layout.addWidget(QLabel("性能指标："), 3, 0)
        self.metric_combo = QComboBox()
        self.metric_combo.addItems(['总收益率', '夏普比率', '最大回撤', '胜率'])
        param_layout.addWidget(self.metric_combo, 3, 1, 1, 3)
        
        # 时间周期选择
        param_layout.addWidget(QLabel("时间周期："), 4, 0)
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItem("日线", TimeFrame.DAY_1)
        self.timeframe_combo.addItem("1小时", TimeFrame.HOUR_1)
        self.timeframe_combo.addItem("30分钟", TimeFrame.MINUTE_30)
        self.timeframe_combo.addItem("15分钟", TimeFrame.MINUTE_15)
        self.timeframe_combo.addItem("5分钟", TimeFrame.MINUTE_5)
        self.timeframe_combo.addItem("1分钟", TimeFrame.MINUTE_1)
        self.timeframe_combo.setCurrentIndex(0)
        param_layout.addWidget(self.timeframe_combo, 4, 1, 1, 3)
        
        layout.addWidget(param_group)
        
        # 分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 结果表格
        result_group = QGroupBox("分析结果")
        result_layout = QVBoxLayout(result_group)
        
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(4)
        self.result_table.setHorizontalHeaderLabels(["参数值", "总收益率", "夏普比率", "最大回撤"])
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.result_table.setAlternatingRowColors(True)
        result_layout.addWidget(self.result_table)
        
        splitter.addWidget(result_group)
        
        # 图表区域
        chart_group = QGroupBox("敏感性曲线")
        chart_layout = QVBoxLayout(chart_group)
        
        if MATPLOTLIB_AVAILABLE:
            self.figure = Figure(figsize=(8, 4))
            self.canvas = FigureCanvas(self.figure)
            chart_layout.addWidget(self.canvas)
        else:
            chart_layout.addWidget(QLabel("图表功能不可用（matplotlib未安装）"))
        
        splitter.addWidget(chart_group)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.analyze_button = QPushButton("开始分析")
        self.analyze_button.clicked.connect(self._run_analysis)
        
        self.export_button = QPushButton("导出结果")
        self.export_button.clicked.connect(self._export_results)
        self.export_button.setEnabled(False)
        
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.analyze_button)
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        # 加载策略参数
        self._load_strategy_parameters()
    
    def _load_strategy_parameters(self):
        """加载策略参数"""
        if self.strategy_config and self.strategy_config.parameters:
            self.param_combo.clear()
            for param_name in self.strategy_config.parameters.keys():
                self.param_combo.addItem(param_name)
            
            # 设置默认值
            if self.param_combo.count() > 0:
                param_name = self.param_combo.currentText()
                param_value = self.strategy_config.parameters.get(param_name, 0)
                
                # 根据参数类型设置默认范围
                if isinstance(param_value, (int, float)):
                    self.min_spin.setValue(float(param_value) * 0.8)
                    self.max_spin.setValue(float(param_value) * 1.2)
                    self.step_spin.setValue(float(param_value) * 0.05)
    
    def _run_analysis(self):
        """运行敏感性分析"""
        try:
            param_name = self.param_combo.currentText()
            if not param_name:
                QMessageBox.warning(self, "警告", "请选择要分析的参数")
                return
            
            min_val = self.min_spin.value()
            max_val = self.max_spin.value()
            step = self.step_spin.value()
            num_samples = self.samples_spin.value()
            
            if min_val >= max_val:
                QMessageBox.warning(self, "警告", "最小值必须小于最大值")
                return
            
            if step <= 0:
                QMessageBox.warning(self, "警告", "步长必须大于0")
                return
            
            # 生成参数值序列
            if num_samples > 1:
                param_values = np.linspace(min_val, max_val, num_samples)
            else:
                param_values = np.array([min_val])
            
            # 显示进度对话框
            progress = QProgressDialog("正在运行敏感性分析...", "取消", 0, len(param_values), self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            # 运行分析
            self.sensitivity_results = {}
            results_data = []
            
            # 检查策略服务是否可用
            if not self.strategy_service:
                QMessageBox.warning(self, "警告", "策略服务未初始化")
                return
            
            # 获取选择的时间周期
            timeframe = self.timeframe_combo.currentData()
            
            # 从真实数据源获取市场数据
            market_data = self._get_real_market_data('2023-01-01', '2024-01-01', timeframe, '000001')
            
            if market_data is None:
                QMessageBox.warning(self, "警告", "无法获取历史数据，请检查数据源配置")
                return
            
            context = StrategyContext(
                symbol='000001',
                timeframe=timeframe,
                start_date='2023-01-01',
                end_date='2024-01-01',
                initial_capital=100000,
                commission_rate=0.0003
            )
            
            # 对每个参数值运行回测
            backtest_ids = []
            for i, param_val in enumerate(param_values):
                if progress.wasCanceled():
                    break
                
                progress.setValue(i)
                QApplication.processEvents()
                
                # 克隆策略配置并修改参数
                modified_params = self.strategy_config.parameters.copy()
                modified_params[param_name] = param_val
                
                # 创建临时策略配置
                temp_config = StrategyConfig(
                    strategy_id=f"{self.strategy_id}_sensitivity_{i}",
                    plugin_type=self.strategy_config.plugin_type,
                    parameters=modified_params,
                    metadata=self.strategy_config.metadata
                )
                
                # 调用后端API运行回测
                try:
                    loop = asyncio.get_event_loop()
                    backtest_id = loop.run_until_complete(
                        self.strategy_service.run_backtest(
                            f"{self.strategy_id}_sensitivity_{i}",
                            market_data,
                            context
                        )
                    )
                    
                    if backtest_id:
                        backtest_ids.append((param_val, backtest_id))
                except Exception as e:
                    logger.error(f"回测失败 (参数值={param_val}): {e}")
                    continue
            
            progress.setValue(len(param_values))
            
            # 等待所有回测完成并收集结果
            for param_val, backtest_id in backtest_ids:
                try:
                    loop = asyncio.get_event_loop()
                    result = loop.run_until_complete(
                        self.strategy_service.get_backtest_result(backtest_id)
                    )
                    
                    if result:
                        total_return = result.total_return
                        sharpe_ratio = result.sharpe_ratio
                        max_drawdown = result.max_drawdown
                        
                        self.sensitivity_results[param_val] = {
                            'total_return': total_return,
                            'sharpe_ratio': sharpe_ratio,
                            'max_drawdown': max_drawdown
                        }
                        
                        results_data.append([
                            f"{param_val:.4f}",
                            f"{total_return:.2%}",
                            f"{sharpe_ratio:.2f}",
                            f"{max_drawdown:.2%}"
                        ])
                except Exception as e:
                    logger.error(f"获取回测结果失败 (backtest_id={backtest_id}): {e}")
                    continue
            
            # 更新结果表格
            self.result_table.setRowCount(len(results_data))
            for row, data in enumerate(results_data):
                for col, value in enumerate(data):
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.result_table.setItem(row, col, item)
            
            # 绘制图表
            self._plot_sensitivity_curve()
            
            # 启用导出按钮
            self.export_button.setEnabled(True)
            
            QMessageBox.information(self, "完成", "敏感性分析完成")
            
        except Exception as e:
            logger.error(f"敏感性分析失败: {e}")
            QMessageBox.critical(self, "错误", f"敏感性分析失败: {str(e)}")
    
    def _plot_sensitivity_curve(self):
        """绘制敏感性曲线"""
        if not MATPLOTLIB_AVAILABLE:
            return
        
        try:
            self.figure.clear()
            
            if not self.sensitivity_results:
                return
            
            # 获取主题管理器
            theme_manager = get_theme_manager()
            current_theme = theme_manager.get_current_theme()
            
            # 根据主题设置背景色
            if current_theme == Theme.DARK:
                bg_color = '#1e1e1e'
                text_color = '#ffffff'
                grid_color = '#333333'
            else:
                bg_color = '#ffffff'
                text_color = '#000000'
                grid_color = '#e0e0e0'
            
            self.figure.patch.set_facecolor(bg_color)
            
            # 创建子图
            ax = self.figure.add_subplot(111)
            ax.set_facecolor(bg_color)
            
            # 提取数据
            param_values = sorted(self.sensitivity_results.keys())
            metric_name = self.metric_combo.currentText()
            
            if metric_name == '总收益率':
                values = [self.sensitivity_results[v]['total_return'] for v in param_values]
                color = FINANCIAL_COLORS['profit']
                ylabel = '总收益率'
            elif metric_name == '夏普比率':
                values = [self.sensitivity_results[v]['sharpe_ratio'] for v in param_values]
                color = FINANCIAL_COLORS['primary']
                ylabel = '夏普比率'
            elif metric_name == '最大回撤':
                values = [self.sensitivity_results[v]['max_drawdown'] for v in param_values]
                color = FINANCIAL_COLORS['loss']
                ylabel = '最大回撤'
            else:  # 胜率
                values = [self.sensitivity_results[v].get('win_rate', 0.5) for v in param_values]
                color = FINANCIAL_COLORS['warning']
                ylabel = '胜率'
            
            # 绘制曲线
            ax.plot(param_values, values, marker='o', linewidth=1, markersize=6, color=color)
            ax.fill_between(param_values, values, alpha=0.3, color=color)
            
            # 设置标签和标题
            param_name = self.param_combo.currentText()
            ax.set_xlabel(f'{param_name}', color=text_color)
            ax.set_ylabel(ylabel, color=text_color)
            ax.set_title(f'{param_name} 敏感性分析', color=text_color, fontsize=12, fontweight='bold')
            
            # 设置刻度颜色
            ax.tick_params(axis='x', colors=text_color)
            ax.tick_params(axis='y', colors=text_color)
            
            # 设置网格
            ax.grid(True, linestyle='--', alpha=0.5, color=grid_color)
            
            # 设置边框颜色
            for spine in ax.spines.values():
                spine.set_edgecolor(grid_color)
            
            self.figure.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            logger.error(f"绘制敏感性曲线失败: {e}")
    
    def _get_real_market_data(self, start_date: str, end_date: str, timeframe: TimeFrame, symbol: str = '000001') -> StandardMarketData:
        """从真实数据源获取市场数据"""
        try:
            data_manager = UnifiedDataManager()
            
            timeframe_map = {
                TimeFrame.DAY_1: 'D',
                TimeFrame.HOUR_1: '60',
                TimeFrame.MINUTE_30: '30',
                TimeFrame.MINUTE_15: '15',
                TimeFrame.MINUTE_5: '5',
                TimeFrame.MINUTE_1: '1'
            }
            period = timeframe_map.get(timeframe, 'D')
            
            df = data_manager.get_kdata_from_source(
                stock_code=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                count=365
            )
            
            if df is None or df.empty:
                logger.warning(f"无法获取 {symbol} 的历史数据，使用默认股票")
                df = data_manager.get_kdata_from_source(
                    stock_code='000001',
                    period=period,
                    count=365
                )
            
            if df is not None and not df.empty:
                return StandardMarketData.from_dataframe(df, symbol=symbol)
            else:
                logger.error(f"无法获取任何历史数据")
                return None
                
        except Exception as e:
            logger.error(f"获取真实市场数据失败: {e}")
            return None
    
    def _export_results(self):
        """导出结果"""
        try:
            if not self.sensitivity_results:
                QMessageBox.warning(self, "警告", "没有可导出的结果")
                return
            
            # 选择保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出敏感性分析结果",
                f"sensitivity_analysis_{self.strategy_id}.csv",
                "CSV文件 (*.csv);;所有文件 (*.*)"
            )
            
            if file_path:
                # 准备数据
                data = []
                for param_val, metrics in sorted(self.sensitivity_results.items()):
                    data.append({
                        '参数值': param_val,
                        '总收益率': metrics['total_return'],
                        '夏普比率': metrics['sharpe_ratio'],
                        '最大回撤': metrics['max_drawdown']
                    })
                
                # 保存为CSV
                df = pd.DataFrame(data)
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                
                QMessageBox.information(self, "成功", f"结果导出成功！\n保存路径: {file_path}")
            
        except Exception as e:
            logger.error(f"导出结果失败: {e}")
            QMessageBox.critical(self, "错误", f"导出结果失败: {str(e)}")
    
    def closeEvent(self, event):
        """关闭事件"""
        event.accept()


class StrategyComparisonDialog(QDialog):
    """策略对比对话框"""
    
    def __init__(self, parent=None, strategy_id1: str = None, strategy_id2: str = None, 
                 strategy_config1: StrategyConfig = None, strategy_config2: StrategyConfig = None, 
                 strategy_service=None):
        super().__init__(parent)
        self.strategy_id1 = strategy_id1
        self.strategy_id2 = strategy_id2
        self.strategy_config1 = strategy_config1
        self.strategy_config2 = strategy_config2
        self.strategy_service = strategy_service
        self.setWindowTitle("策略对比")
        self.setModal(True)
        self.resize(1000, 800)
        
        self.comparison_data = {}
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 配置区域
        config_group = QGroupBox("配置")
        config_layout = QFormLayout(config_group)
        
        # 时间周期选择
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItem("日线", TimeFrame.DAY_1)
        self.timeframe_combo.addItem("1小时", TimeFrame.HOUR_1)
        self.timeframe_combo.addItem("30分钟", TimeFrame.MINUTE_30)
        self.timeframe_combo.addItem("15分钟", TimeFrame.MINUTE_15)
        self.timeframe_combo.addItem("5分钟", TimeFrame.MINUTE_5)
        self.timeframe_combo.addItem("1分钟", TimeFrame.MINUTE_1)
        self.timeframe_combo.setCurrentIndex(0)
        config_layout.addRow("时间周期：", self.timeframe_combo)
        
        layout.addWidget(config_group)
        
        # 对比结果表格
        result_group = QGroupBox("对比结果")
        result_layout = QVBoxLayout(result_group)
        
        self.comparison_table = QTableWidget()
        self.comparison_table.setColumnCount(3)
        self.comparison_table.setHorizontalHeaderLabels(["指标", "策略1", "策略2"])
        self.comparison_table.horizontalHeader().setStretchLastSection(True)
        self.comparison_table.setAlternatingRowColors(True)
        result_layout.addWidget(self.comparison_table)
        
        layout.addWidget(result_group)
        
        # 图表区域
        chart_group = QGroupBox("收益曲线对比")
        chart_layout = QVBoxLayout(chart_group)
        
        if MATPLOTLIB_AVAILABLE:
            self.figure = Figure(figsize=(10, 5))
            self.canvas = FigureCanvas(self.figure)
            chart_layout.addWidget(self.canvas)
        else:
            chart_layout.addWidget(QLabel("图表功能不可用（matplotlib未安装）"))
        
        layout.addWidget(chart_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.export_button = QPushButton("导出对比结果")
        self.export_button.clicked.connect(self._export_results)
        self.export_button.setEnabled(False)
        
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def run_comparison(self):
        """运行对比"""
        try:
            # 检查策略服务是否可用
            if not self.strategy_service:
                QMessageBox.warning(self, "警告", "策略服务未初始化")
                return
            
            # 生成对比数据
            self.comparison_data = self._generate_comparison_data()
            
            # 更新对比表格
            self._update_comparison_table()
            
            # 绘制对比图表
            self._plot_comparison_chart()
            
            # 启用导出按钮
            self.export_button.setEnabled(True)
            
        except Exception as e:
            logger.error(f"策略对比失败: {e}")
            QMessageBox.critical(self, "错误", f"策略对比失败: {str(e)}")
    
    def _get_real_market_data(self, start_date: str, end_date: str, timeframe: TimeFrame, symbol: str = '000001') -> StandardMarketData:
        """从真实数据源获取市场数据"""
        try:
            data_manager = UnifiedDataManager()
            
            timeframe_map = {
                TimeFrame.DAY_1: 'D',
                TimeFrame.HOUR_1: '60',
                TimeFrame.MINUTE_30: '30',
                TimeFrame.MINUTE_15: '15',
                TimeFrame.MINUTE_5: '5',
                TimeFrame.MINUTE_1: '1'
            }
            period = timeframe_map.get(timeframe, 'D')
            
            df = data_manager.get_kdata_from_source(
                stock_code=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                count=365
            )
            
            if df is None or df.empty:
                logger.warning(f"无法获取 {symbol} 的历史数据，使用默认股票")
                df = data_manager.get_kdata_from_source(
                    stock_code='000001',
                    period=period,
                    count=365
                )
            
            if df is not None and not df.empty:
                return StandardMarketData.from_dataframe(df, symbol=symbol)
            else:
                logger.error(f"无法获取任何历史数据")
                return None
                
        except Exception as e:
            logger.error(f"获取真实市场数据失败: {e}")
            return None
    
    def _generate_comparison_data(self) -> Dict[str, Any]:
        """生成对比数据"""
        # 获取选择的时间周期
        timeframe = self.timeframe_combo.currentData()
        
        # 从真实数据源获取市场数据
        market_data = self._get_real_market_data('2023-01-01', '2024-01-01', timeframe, '000001')
        
        if market_data is None:
            QMessageBox.warning(self, "警告", "无法获取历史数据，请检查数据源配置")
            return {}
        
        context = StrategyContext(
            symbol='000001',
            timeframe=timeframe,
            start_date='2023-01-01',
            end_date='2024-01-01',
            initial_capital=100000,
            commission_rate=0.0003
        )
        
        data = {}
        
        # 对策略1进行回测
        try:
            loop = asyncio.get_event_loop()
            backtest_id1 = loop.run_until_complete(
                self.strategy_service.run_backtest(
                    self.strategy_id1,
                    market_data,
                    context
                )
            )
            
            if backtest_id1:
                result1 = loop.run_until_complete(
                    self.strategy_service.get_backtest_result(backtest_id1)
                )
                
                if result1:
                    data['strategy1'] = {
                        'id': self.strategy_id1,
                        'name': self.strategy_config1.metadata.get('name', self.strategy_id1) if self.strategy_config1 else self.strategy_id1,
                        'total_return': result1.total_return,
                        'annual_return': result1.annual_return,
                        'sharpe_ratio': result1.sharpe_ratio,
                        'max_drawdown': result1.max_drawdown,
                        'win_rate': result1.win_rate,
                        'profit_loss_ratio': result1.profit_factor,
                        'total_trades': result1.total_trades,
                        'avg_holding_days': 0,  # 需要从交易记录中计算
                        'result': result1  # 保存完整的回测结果对象
                    }
        except Exception as e:
            logger.error(f"策略1回测失败: {e}")
            data['strategy1'] = None
        
        # 对策略2进行回测
        try:
            loop = asyncio.get_event_loop()
            backtest_id2 = loop.run_until_complete(
                self.strategy_service.run_backtest(
                    self.strategy_id2,
                    market_data,
                    context
                )
            )
            
            if backtest_id2:
                result2 = loop.run_until_complete(
                    self.strategy_service.get_backtest_result(backtest_id2)
                )
                
                if result2:
                    data['strategy2'] = {
                        'id': self.strategy_id2,
                        'name': self.strategy_config2.metadata.get('name', self.strategy_id2) if self.strategy_config2 else self.strategy_id2,
                        'total_return': result2.total_return,
                        'annual_return': result2.annual_return,
                        'sharpe_ratio': result2.sharpe_ratio,
                        'max_drawdown': result2.max_drawdown,
                        'win_rate': result2.win_rate,
                        'profit_loss_ratio': result2.profit_factor,
                        'total_trades': result2.total_trades,
                        'avg_holding_days': 0,  # 需要从交易记录中计算
                        'result': result2  # 保存完整的回测结果对象
                    }
        except Exception as e:
            logger.error(f"策略2回测失败: {e}")
            data['strategy2'] = None
        
        return data
    
    def _update_comparison_table(self):
        """更新对比表格"""
        # 检查是否有有效数据
        if not self.comparison_data.get('strategy1') or not self.comparison_data.get('strategy2'):
            QMessageBox.warning(self, "警告", "策略对比数据不完整")
            return
        
        metrics = [
            ('策略ID', 'id'),
            ('策略名称', 'name'),
            ('总收益率', 'total_return'),
            ('年化收益率', 'annual_return'),
            ('夏普比率', 'sharpe_ratio'),
            ('最大回撤', 'max_drawdown'),
            ('胜率', 'win_rate'),
            ('盈亏比', 'profit_loss_ratio'),
            ('总交易次数', 'total_trades'),
            ('平均持仓天数', 'avg_holding_days')
        ]
        
        self.comparison_table.setRowCount(len(metrics))
        
        for row, (metric_name, metric_key) in enumerate(metrics):
            # 指标名称
            metric_item = QTableWidgetItem(metric_name)
            self.comparison_table.setItem(row, 0, metric_item)
            
            # 策略1的值
            value1 = self.comparison_data['strategy1'].get(metric_key, 0)
            if isinstance(value1, float):
                if 'return' in metric_key or 'rate' in metric_key or 'ratio' in metric_key:
                    text1 = f"{value1:.2%}" if 'return' in metric_key or 'rate' in metric_key else f"{value1:.2f}"
                elif 'drawdown' in metric_key:
                    text1 = f"{value1:.2%}"
                else:
                    text1 = f"{value1:.2f}"
            else:
                text1 = str(value1)
            
            item1 = QTableWidgetItem(text1)
            item1.setTextAlignment(Qt.AlignCenter)
            self.comparison_table.setItem(row, 1, item1)
            
            # 策略2的值
            value2 = self.comparison_data['strategy2'].get(metric_key, 0)
            if isinstance(value2, float):
                if 'return' in metric_key or 'rate' in metric_key or 'ratio' in metric_key:
                    text2 = f"{value2:.2%}" if 'return' in metric_key or 'rate' in metric_key else f"{value2:.2f}"
                elif 'drawdown' in metric_key:
                    text2 = f"{value2:.2%}"
                else:
                    text2 = f"{value2:.2f}"
            else:
                text2 = str(value2)
            
            item2 = QTableWidgetItem(text2)
            item2.setTextAlignment(Qt.AlignCenter)
            self.comparison_table.setItem(row, 2, item2)
    
    def _plot_comparison_chart(self):
        """绘制对比图表"""
        if not MATPLOTLIB_AVAILABLE:
            return
        
        try:
            self.figure.clear()
            
            if not self.comparison_data:
                return
            
            # 获取主题管理器
            theme_manager = get_theme_manager()
            current_theme = theme_manager.get_current_theme()
            
            # 根据主题设置背景色
            if current_theme == Theme.DARK:
                bg_color = '#1e1e1e'
                text_color = '#ffffff'
                grid_color = '#333333'
            else:
                bg_color = '#ffffff'
                text_color = '#000000'
                grid_color = '#e0e0e0'
            
            self.figure.patch.set_facecolor(bg_color)
            
            # 创建子图
            ax = self.figure.add_subplot(111)
            ax.set_facecolor(bg_color)
            
            # 获取真实的收益曲线数据
            result1 = self.comparison_data.get('strategy1', {}).get('result')
            result2 = self.comparison_data.get('strategy2', {}).get('result')
            
            if result1 and result1.equity_curve is not None:
                dates1 = result1.equity_curve.index
                returns1 = result1.equity_curve.values * 100  # 转换为百分比
                ax.plot(dates1, returns1, color=FINANCIAL_COLORS['primary'], linewidth=1, 
                       label=f"{self.comparison_data['strategy1']['name']}")
            else:
                logger.warning("策略1没有收益曲线数据")
            
            if result2 and result2.equity_curve is not None:
                dates2 = result2.equity_curve.index
                returns2 = result2.equity_curve.values * 100  # 转换为百分比
                ax.plot(dates2, returns2, color=FINANCIAL_COLORS['auxiliary_1'], linewidth=1, 
                       label=f"{self.comparison_data['strategy2']['name']}")
            else:
                logger.warning("策略2没有收益曲线数据")
            
            # 绘制基准线
            ax.axhline(y=0, color=FINANCIAL_COLORS['primary'], linestyle='--', alpha=0.5, label='基准线')
            
            # 设置标签和标题
            ax.set_xlabel('时间', color=text_color)
            ax.set_ylabel('收益率 (%)', color=text_color)
            ax.set_title('策略收益对比', color=text_color, fontsize=12, fontweight='bold')
            
            # 设置刻度颜色
            ax.tick_params(axis='x', colors=text_color)
            ax.tick_params(axis='y', colors=text_color)
            
            # 设置网格
            ax.grid(True, linestyle='--', alpha=0.5, color=grid_color)
            
            # 设置边框颜色
            for spine in ax.spines.values():
                spine.set_edgecolor(grid_color)
            
            # 添加图例
            ax.legend()
            
            self.figure.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            logger.error(f"绘制对比图表失败: {e}")
    
    def _export_results(self):
        """导出对比结果"""
        try:
            if not self.comparison_data:
                QMessageBox.warning(self, "警告", "没有可导出的结果")
                return
            
            # 选择保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出策略对比结果",
                f"strategy_comparison_{self.strategy_id1}_vs_{self.strategy_id2}.csv",
                "CSV文件 (*.csv);;所有文件 (*.*)"
            )
            
            if file_path:
                # 准备数据
                data = []
                metrics = [
                    ('策略ID', 'id'),
                    ('策略名称', 'name'),
                    ('总收益率', 'total_return'),
                    ('年化收益率', 'annual_return'),
                    ('夏普比率', 'sharpe_ratio'),
                    ('最大回撤', 'max_drawdown'),
                    ('胜率', 'win_rate'),
                    ('盈亏比', 'profit_loss_ratio'),
                    ('总交易次数', 'total_trades'),
                    ('平均持仓天数', 'avg_holding_days')
                ]
                
                for metric_name, metric_key in metrics:
                    row_data = {
                        '指标': metric_name,
                        f"策略1 ({self.comparison_data['strategy1']['name']})": self.comparison_data['strategy1'].get(metric_key, 0),
                        f"策略2 ({self.comparison_data['strategy2']['name']})": self.comparison_data['strategy2'].get(metric_key, 0)
                    }
                    data.append(row_data)
                
                # 保存为CSV
                df = pd.DataFrame(data)
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                
                QMessageBox.information(self, "成功", f"对比结果导出成功！保存路径: {file_path}")
            
        except Exception as e:
            logger.error(f"导出对比结果失败: {e}")
            QMessageBox.critical(self, "错误", f"导出对比结果失败: {str(e)}")
    
    def closeEvent(self, event):
        """关闭事件"""
        event.accept()


class ParameterScanDialog(QDialog):
    """参数扫描对话框"""
    
    def __init__(self, parent=None, strategy_id: str = None, strategy_config: StrategyConfig = None, strategy_service=None):
        super().__init__(parent)
        self.strategy_id = strategy_id
        self.strategy_config = strategy_config
        self.strategy_service = strategy_service
        self.setWindowTitle("参数扫描")
        self.setModal(True)
        self.resize(900, 700)
        
        self.scan_results = {}
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 参数选择区域
        param_group = QGroupBox("参数配置")
        param_layout = QGridLayout(param_group)
        
        # 参数选择
        param_layout.addWidget(QLabel("选择参数："), 0, 0, 1, 1)
        self.param_combo = QComboBox()
        param_layout.addWidget(self.param_combo, 0, 1, 1, 2)
        
        # 参数范围
        param_layout.addWidget(QLabel("最小值："), 1, 0)
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setDecimals(4)
        self.min_spin.setRange(-999999, 999999)
        param_layout.addWidget(self.min_spin, 1, 1)
        
        param_layout.addWidget(QLabel("最大值："), 1, 2)
        self.max_spin = QDoubleSpinBox()
        self.max_spin.setDecimals(4)
        self.max_spin.setRange(-999999, 999999)
        param_layout.addWidget(self.max_spin, 1, 3)
        
        param_layout.addWidget(QLabel("步长："), 2, 0)
        self.step_spin = QDoubleSpinBox()
        self.step_spin.setDecimals(4)
        self.step_spin.setRange(0.0001, 999999)
        self.step_spin.setValue(0.1)
        param_layout.addWidget(self.step_spin, 2, 1)
        
        # 扫描点数
        param_layout.addWidget(QLabel("扫描点数："), 2, 2)
        self.samples_spin = QSpinBox()
        self.samples_spin.setRange(5, 100)
        self.samples_spin.setValue(10)
        param_layout.addWidget(self.samples_spin, 2, 3)
        
        # 时间周期选择
        param_layout.addWidget(QLabel("时间周期："), 3, 0)
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItem("日线", TimeFrame.DAY_1)
        self.timeframe_combo.addItem("1小时", TimeFrame.HOUR_1)
        self.timeframe_combo.addItem("30分钟", TimeFrame.MINUTE_30)
        self.timeframe_combo.addItem("15分钟", TimeFrame.MINUTE_15)
        self.timeframe_combo.addItem("5分钟", TimeFrame.MINUTE_5)
        self.timeframe_combo.addItem("1分钟", TimeFrame.MINUTE_1)
        self.timeframe_combo.setCurrentIndex(0)
        param_layout.addWidget(self.timeframe_combo, 3, 1, 1, 3)
        
        layout.addWidget(param_group)
        
        # 分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 结果表格
        result_group = QGroupBox("扫描结果")
        result_layout = QVBoxLayout(result_group)
        
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(4)
        self.result_table.setHorizontalHeaderLabels(["参数值", "总收益率", "夏普比率", "最大回撤"])
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.result_table.setAlternatingRowColors(True)
        result_layout.addWidget(self.result_table)
        
        splitter.addWidget(result_group)
        
        # 图表区域
        chart_group = QGroupBox("扫描曲线")
        chart_layout = QVBoxLayout(chart_group)
        
        if MATPLOTLIB_AVAILABLE:
            self.figure = Figure(figsize=(8, 4))
            self.canvas = FigureCanvas(self.figure)
            chart_layout.addWidget(self.canvas)
        else:
            chart_layout.addWidget(QLabel("图表功能不可用（matplotlib未安装）"))
        
        splitter.addWidget(chart_group)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.scan_button = QPushButton("开始扫描")
        self.scan_button.clicked.connect(self._run_scan)
        
        self.export_button = QPushButton("导出结果")
        self.export_button.clicked.connect(self._export_results)
        self.export_button.setEnabled(False)
        
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.scan_button)
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        # 加载策略参数
        self._load_strategy_parameters()
    
    def _load_strategy_parameters(self):
        """加载策略参数"""
        if self.strategy_config and self.strategy_config.parameters:
            self.param_combo.clear()
            for param_name in self.strategy_config.parameters.keys():
                self.param_combo.addItem(param_name)
            
            # 设置默认值
            if self.param_combo.count() > 0:
                param_name = self.param_combo.currentText()
                param_value = self.strategy_config.parameters.get(param_name, 0)
                
                # 根据参数类型设置默认范围
                if isinstance(param_value, (int, float)):
                    self.min_spin.setValue(float(param_value) * 0.8)
                    self.max_spin.setValue(float(param_value) * 1.2)
                    self.step_spin.setValue(float(param_value) * 0.05)
    
    def _run_scan(self):
        """运行参数扫描"""
        try:
            param_name = self.param_combo.currentText()
            if not param_name:
                QMessageBox.warning(self, "警告", "请选择要扫描的参数")
                return
            
            min_val = self.min_spin.value()
            max_val = self.max_spin.value()
            step = self.step_spin.value()
            num_samples = self.samples_spin.value()
            
            if min_val >= max_val:
                QMessageBox.warning(self, "警告", "最小值必须小于最大值")
                return
            
            if step <= 0:
                QMessageBox.warning(self, "警告", "步长必须大于0")
                return
            
            # 生成参数值序列
            if num_samples > 1:
                param_values = np.linspace(min_val, max_val, num_samples)
            else:
                param_values = np.array([min_val])
            
            # 显示进度对话框
            progress = QProgressDialog("正在运行参数扫描...", "取消", 0, len(param_values), self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            # 运行扫描
            self.scan_results = {}
            results_data = []
            
            # 检查策略服务是否可用
            if not self.strategy_service:
                QMessageBox.warning(self, "警告", "策略服务未初始化")
                return
            
            # 获取选择的时间周期
            timeframe = self.timeframe_combo.currentData()
            
            # 从真实数据源获取市场数据
            market_data = self._get_real_market_data('2023-01-01', '2024-01-01', timeframe, '000001')
            
            if market_data is None:
                QMessageBox.warning(self, "警告", "无法获取历史数据，请检查数据源配置")
                return
            
            context = StrategyContext(
                symbol='000001',
                timeframe=timeframe,
                start_date='2023-01-01',
                end_date='2024-01-01',
                initial_capital=100000,
                commission_rate=0.0003
            )
            
            # 对每个参数值运行回测
            backtest_ids = []
            for i, param_val in enumerate(param_values):
                if progress.wasCanceled():
                    break
                
                progress.setValue(i)
                QApplication.processEvents()
                
                # 克隆策略配置并修改参数
                modified_params = self.strategy_config.parameters.copy()
                modified_params[param_name] = param_val
                
                # 创建临时策略配置
                temp_config = StrategyConfig(
                    strategy_id=f"{self.strategy_id}_scan_{i}",
                    plugin_type=self.strategy_config.plugin_type,
                    parameters=modified_params,
                    metadata=self.strategy_config.metadata
                )
                
                # 调用后端API运行回测
                try:
                    loop = asyncio.get_event_loop()
                    backtest_id = loop.run_until_complete(
                        self.strategy_service.run_backtest(
                            f"{self.strategy_id}_scan_{i}",
                            market_data,
                            context
                        )
                    )
                    
                    if backtest_id:
                        backtest_ids.append((param_val, backtest_id))
                except Exception as e:
                    logger.error(f"回测失败 (参数值={param_val}): {e}")
                    continue
            
            progress.setValue(len(param_values))
            
            # 等待所有回测完成并收集结果
            for param_val, backtest_id in backtest_ids:
                try:
                    loop = asyncio.get_event_loop()
                    result = loop.run_until_complete(
                        self.strategy_service.get_backtest_result(backtest_id)
                    )
                    
                    if result:
                        total_return = result.total_return
                        sharpe_ratio = result.sharpe_ratio
                        max_drawdown = result.max_drawdown
                        
                        self.scan_results[param_val] = {
                            'total_return': total_return,
                            'sharpe_ratio': sharpe_ratio,
                            'max_drawdown': max_drawdown
                        }
                        
                        results_data.append([
                            f"{param_val:.4f}",
                            f"{total_return:.2%}",
                            f"{sharpe_ratio:.2f}",
                            f"{max_drawdown:.2%}"
                        ])
                except Exception as e:
                    logger.error(f"获取回测结果失败 (backtest_id={backtest_id}): {e}")
                    continue
            
            # 更新结果表格
            self.result_table.setRowCount(len(results_data))
            for row, data in enumerate(results_data):
                for col, value in enumerate(data):
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.result_table.setItem(row, col, item)
            
            # 绘制图表
            self._plot_scan_curve()
            
            # 启用导出按钮
            self.export_button.setEnabled(True)
            
            QMessageBox.information(self, "完成", "参数扫描完成")
            
        except Exception as e:
            logger.error(f"参数扫描失败: {e}")
            QMessageBox.critical(self, "错误", f"参数扫描失败: {str(e)}")
    
    def _plot_scan_curve(self):
        """绘制扫描曲线"""
        if not MATPLOTLIB_AVAILABLE:
            return
        
        try:
            self.figure.clear()
            
            if not self.scan_results:
                return
            
            # 获取主题管理器
            theme_manager = get_theme_manager()
            current_theme = theme_manager.get_current_theme()
            
            # 根据主题设置背景色
            if current_theme == Theme.DARK:
                bg_color = '#1e1e1e'
                text_color = '#ffffff'
                grid_color = '#333333'
            else:
                bg_color = '#ffffff'
                text_color = '#000000'
                grid_color = '#e0e0e0'
            
            self.figure.patch.set_facecolor(bg_color)
            
            # 创建子图
            ax = self.figure.add_subplot(111)
            ax.set_facecolor(bg_color)
            
            # 提取数据
            param_values = sorted(self.scan_results.keys())
            returns = [self.scan_results[v]['total_return'] for v in param_values]
            
            # 绘制曲线
            ax.plot(param_values, returns, marker='o', linewidth=2, markersize=6, color=FINANCIAL_COLORS['profit'])
            ax.fill_between(param_values, returns, alpha=0.3, color=FINANCIAL_COLORS['profit'])
            
            # 设置标签和标题
            param_name = self.param_combo.currentText()
            ax.set_xlabel(f'{param_name}', color=text_color)
            ax.set_ylabel('总收益率', color=text_color)
            ax.set_title(f'{param_name} 参数扫描', color=text_color, fontsize=12, fontweight='bold')
            
            # 设置刻度颜色
            ax.tick_params(axis='x', colors=text_color)
            ax.tick_params(axis='y', colors=text_color)
            
            # 设置网格
            ax.grid(True, linestyle='--', alpha=0.5, color=grid_color)
            
            # 设置边框颜色
            for spine in ax.spines.values():
                spine.set_edgecolor(grid_color)
            
            self.figure.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            logger.error(f"绘制扫描曲线失败: {e}")
    
    def _export_results(self):
        """导出结果"""
        try:
            if not self.scan_results:
                QMessageBox.warning(self, "警告", "没有可导出的结果")
                return
            
            # 选择保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出参数扫描结果",
                f"parameter_scan_{self.strategy_id}.csv",
                "CSV文件 (*.csv);;所有文件 (*.*)"
            )
            
            if file_path:
                # 准备数据
                data = []
                for param_val, metrics in sorted(self.scan_results.items()):
                    data.append({
                        '参数值': param_val,
                        '总收益率': metrics['total_return'],
                        '夏普比率': metrics['sharpe_ratio'],
                        '最大回撤': metrics['max_drawdown']
                    })
                
                # 保存为CSV
                df = pd.DataFrame(data)
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                
                QMessageBox.information(self, "成功", f"对比结果导出成功！\n保存路径: {file_path}")
            
        except Exception as e:
            logger.error(f"导出结果失败: {e}")
            QMessageBox.critical(self, "错误", f"导出结果失败: {str(e)}")
    
    def _get_real_market_data(self, start_date: str, end_date: str, timeframe: TimeFrame, symbol: str = '000001') -> StandardMarketData:
        """从真实数据源获取市场数据"""
        try:
            data_manager = UnifiedDataManager()
            
            timeframe_map = {
                TimeFrame.DAY_1: 'D',
                TimeFrame.HOUR_1: '60',
                TimeFrame.MINUTE_30: '30',
                TimeFrame.MINUTE_15: '15',
                TimeFrame.MINUTE_5: '5',
                TimeFrame.MINUTE_1: '1'
            }
            period = timeframe_map.get(timeframe, 'D')
            
            df = data_manager.get_kdata_from_source(
                stock_code=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                count=365
            )
            
            if df is None or df.empty:
                logger.warning(f"无法获取 {symbol} 的历史数据，使用默认股票")
                df = data_manager.get_kdata_from_source(
                    stock_code='000001',
                    period=period,
                    count=365
                )
            
            if df is not None and not df.empty:
                return StandardMarketData.from_dataframe(df, symbol=symbol)
            else:
                logger.error(f"无法获取任何历史数据")
                return None
                
        except Exception as e:
            logger.error(f"获取真实市场数据失败: {e}")
            return None
    
    def closeEvent(self, event):
        """关闭事件"""
        event.accept()


class StrategyConfigDialog(QDialog):
    """策略配置对话框"""
    
    def __init__(self, parent=None, strategy_config=None):
        super().__init__(parent)
        self.strategy_config = strategy_config
        self.setWindowTitle("编辑策略" if strategy_config is not None else "创建策略")
        self.setModal(True)
        self.resize(600, 500)
        
        # 获取账号列表
        self.accounts = self._load_accounts()
        
        self._setup_ui()
        
        if strategy_config:
            self._load_config(strategy_config)
    
    def _load_accounts(self) -> List[str]:
        """加载账号列表"""
        try:
            from core.containers import get_service_container
            from core.trading.account_manager import AccountManager
            
            service_container = get_service_container()
            if service_container and service_container.is_registered(AccountManager):
                account_manager = service_container.resolve(AccountManager)
                accounts = account_manager.get_all_accounts()
                return [acc.account_id for acc in accounts]
            else:
                return []
        except Exception as e:
            logger.warning(f"加载账号列表失败: {e}")
            return []
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 基本信息
        basic_group = QGroupBox("基本信息")
        basic_layout = QFormLayout(basic_group)
        
        self.strategy_id_edit = QLineEdit()
        self.strategy_id_edit.setPlaceholderText("策略ID，如：momentum_strategy_v1")
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("策略名称")
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(['momentum', 'mean_reversion', 'trend_following', 'arbitrage', 'statistical', 'custom'])
        
        self.default_account_combo = QComboBox()
        self.default_account_combo.addItem("使用系统默认账号", "default")
        for account_id in self.accounts:
            self.default_account_combo.addItem(account_id, account_id)
        
        basic_layout.addRow("策略ID：", self.strategy_id_edit)
        basic_layout.addRow("策略名称：", self.name_edit)
        basic_layout.addRow("策略类型：", self.type_combo)
        basic_layout.addRow("默认账号：", self.default_account_combo)
        
        layout.addWidget(basic_group)
        
        # 插件类型
        plugin_group = QGroupBox("插件类型")
        plugin_layout = QFormLayout(plugin_group)
        
        self.plugin_type_combo = QComboBox()
        self.plugin_type_combo.addItems(['factorweave', 'backtrader', 'custom'])
        
        plugin_layout.addRow("插件类型：", self.plugin_type_combo)
        
        layout.addWidget(plugin_group)
        
        # 参数配置
        param_group = QGroupBox("参数配置")
        param_layout = QVBoxLayout(param_group)
        
        self.param_table = QTableWidget()
        self.param_table.setColumnCount(3)
        self.param_table.setHorizontalHeaderLabels(["参数名", "参数值", "操作"])
        self.param_table.horizontalHeader().setStretchLastSection(True)
        
        param_layout.addWidget(self.param_table)
        
        # 添加参数按钮
        add_param_button = QPushButton("添加参数")
        add_param_button.clicked.connect(self._add_parameter_row)
        param_layout.addWidget(add_param_button)
        
        layout.addWidget(param_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
    
    def _load_config(self, strategy_config: StrategyConfig):
        """加载策略配置"""
        self.strategy_id_edit.setText(strategy_config.strategy_id)
        self.name_edit.setText(strategy_config.metadata.get('name', ''))
        self.type_combo.setCurrentText(strategy_config.metadata.get('type', 'custom'))
        self.plugin_type_combo.setCurrentText(strategy_config.plugin_type)
        
        # 加载默认账号
        default_account_id = strategy_config.metadata.get('default_account_id', 'default')
        index = self.default_account_combo.findData(default_account_id)
        if index >= 0:
            self.default_account_combo.setCurrentIndex(index)
        else:
            self.default_account_combo.setCurrentIndex(0)
        
        # 加载参数
        self.param_table.setRowCount(0)
        for param_name, param_value in strategy_config.parameters.items():
            self._add_parameter_row(param_name, str(param_value))
    
    def _add_parameter_row(self, param_name: str = '', param_value: str = ''):
        """添加参数行"""
        row = self.param_table.rowCount()
        self.param_table.insertRow(row)
        
        name_item = QTableWidgetItem(param_name)
        value_item = QTableWidgetItem(param_value)
        
        self.param_table.setItem(row, 0, name_item)
        self.param_table.setItem(row, 1, value_item)
        
        # 删除按钮
        delete_button = QPushButton("删除")
        delete_button.setMaximumSize(50, 25)
        delete_button.clicked.connect(lambda checked, r=row: self._remove_parameter_row(r))
        
        self.param_table.setCellWidget(row, 2, delete_button)
    
    def _remove_parameter_row(self, row: int):
        """删除参数行"""
        self.param_table.removeRow(row)
    
    def get_config_data(self) -> Dict[str, Any]:
        """获取配置数据"""
        # 收集参数
        parameters = {}
        for row in range(self.param_table.rowCount()):
            name_item = self.param_table.item(row, 0)
            value_item = self.param_table.item(row, 1)
            
            if name_item and value_item:
                param_name = name_item.text()
                param_value = value_item.text()
                
                # 尝试转换为数值
                try:
                    if '.' in param_value:
                        param_value = float(param_value)
                    else:
                        param_value = int(param_value)
                except ValueError:
                    pass
                
                parameters[param_name] = param_value
        
        return {
            'strategy_id': self.strategy_id_edit.text(),
            'plugin_type': self.plugin_type_combo.currentText(),
            'parameters': parameters,
            'metadata': {
                'name': self.name_edit.text(),
                'type': self.type_combo.currentText(),
                'default_account_id': self.default_account_combo.currentData()
            }
        }


class BatchUpdateDefaultAccountDialog(QDialog):
    """批量修改默认账号对话框"""
    
    def __init__(self, parent=None, strategy_ids=None, strategy_service=None, account_manager=None):
        super().__init__(parent)
        self.strategy_ids = strategy_ids or []
        self.strategy_service = strategy_service
        self.account_manager = account_manager
        self.accounts = []
        
        self.setWindowTitle("批量修改默认账号")
        self.setModal(True)
        self.resize(600, 400)
        
        self._load_accounts()
        self._setup_ui()
    
    def _load_accounts(self):
        """加载账号列表"""
        if self.account_manager:
            try:
                accounts = self.account_manager.get_all_accounts()
                self.accounts = [account.account_id for account in accounts]
            except Exception as e:
                logger.error(f"加载账号列表失败: {e}")
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 策略列表
        strategy_group = QGroupBox("选中的策略")
        strategy_layout = QVBoxLayout(strategy_group)
        
        self.strategy_list = QListWidget()
        self.strategy_list.setSelectionMode(QListWidget.NoSelection)
        for strategy_id in self.strategy_ids:
            self.strategy_list.addItem(strategy_id)
        
        strategy_layout.addWidget(self.strategy_list)
        layout.addWidget(strategy_group)
        
        # 默认账号选择
        account_group = QGroupBox("设置默认账号")
        account_layout = QFormLayout(account_group)
        
        self.account_combo = QComboBox()
        self.account_combo.addItem("使用系统默认账号", "default")
        for account_id in self.accounts:
            self.account_combo.addItem(account_id, account_id)
        
        account_layout.addRow("默认账号：", self.account_combo)
        layout.addWidget(account_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
    
    def get_selected_account(self) -> str:
        """获取选中的账号ID"""
        return self.account_combo.currentData()
    
    def closeEvent(self, event):
        """关闭事件"""
        event.accept()