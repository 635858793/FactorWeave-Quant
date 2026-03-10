"""
UI components for trading system

This module contains reusable UI components for the trading system.
"""

from loguru import logger
from PyQt5.QtWidgets import (
    QDateEdit, QGridLayout, QListWidgetItem, QSizePolicy, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QProgressBar, QTextEdit,
    QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox,
    QListWidget, QTableWidget, QTableWidgetItem, QDialog, QCheckBox,
    QHeaderView, QInputDialog, QAbstractItemView, QMessageBox,
    QTabWidget
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QDate
from PyQt5.QtGui import QIcon, QColor, QBrush
import pandas as pd
import psutil
from datetime import datetime
import traceback
from utils.config_types import LoggingConfig
from typing import Optional, Dict, Any
import csv
import os
from gui.enhanced_batch_analysis_methods import EnhancedBatchAnalysisMixin
import time
import json
from concurrent.futures import ThreadPoolExecutor
import threading
import random
from PyQt5.QtWidgets import QApplication


class BaseAnalysisPanel(QWidget):
    """基础分析面板，统一参数设置、导出、日志、信号、按钮等通用功能"""

    # 定义信号
    analysis_completed = pyqtSignal(dict)  # 分析完成信号
    data_requested = pyqtSignal(dict)  # 数据请求信号
    error_occurred = pyqtSignal(str)  # 错误信号
    analysis_progress = pyqtSignal(str)  # 分析进度信号

    def __init__(self, parent=None):
        """初始化基础分析面板

        Args:
            parent: 父窗口
        """
        super().__init__(parent)

        # 设置基本属性
        self.parent = parent
        self.analysis_results = {}
        self.performance_metrics = {}
        self.current_strategy = None

        # 创建主布局
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(self.main_layout)

        # 初始化状态栏
        self.init_status_bar()

        # 初始化通用UI元素
        self.init_common_ui()

    def init_status_bar(self):
        """初始化状态栏"""
        status_layout = QHBoxLayout()
        self.status_label = QLabel("准备就绪")
        self.status_label.setStyleSheet("padding: 2px; border: 1px solid gray;")
        status_layout.addWidget(QLabel("状态:"))
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        status_widget = QWidget()
        status_widget.setLayout(status_layout)
        self.main_layout.addWidget(status_widget)

    def init_common_ui(self):
        """初始化通用UI元素"""
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.main_layout.addWidget(self.progress_bar)

    def show_progress(self, visible=True):
        """显示/隐藏进度条"""
        self.progress_bar.setVisible(visible)

    def set_progress(self, value):
        """设置进度条值"""
        self.progress_bar.setValue(value)

    def update_status(self, message: str, error: bool = False):
        """更新状态栏信息"""
        if hasattr(self, 'status_label'):
            self.status_label.setText(message)
            if error:
                self.status_label.setStyleSheet("color: red; padding: 2px; border: 1px solid gray;")
            else:
                self.status_label.setStyleSheet("padding: 2px; border: 1px solid gray;")

    def log_info(self, message: str):
        """记录信息日志"""
        if True:  # 使用Loguru日志
            logger.info(message)

    def log_error(self, message: str):
        """记录错误日志"""
        if True:  # 使用Loguru日志
            logger.error(message)

    def export_results_to_csv(self, data: Dict[str, Any], filename: str = None):
        """导出结果到CSV文件"""
        try:
            if not filename:
                filename = f"analysis_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            if isinstance(data, dict):
                df = pd.DataFrame([data])
            else:
                df = pd.DataFrame(data)

            df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.update_status(f"结果已导出到: {filename}")
            return True
        except Exception as e:
            self.log_error(f"导出CSV文件失败: {e}")
            self.update_status(f"导出失败: {e}", error=True)
            return False

    def get_system_info(self):
        """获取系统信息"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                'cpu_usage': f"{cpu_percent}%",
                'memory_usage': f"{memory.percent}%",
                'disk_usage': f"{disk.percent}%",
                'available_memory': f"{memory.available / (1024**3):.1f} GB"
            }
        except Exception as e:
            self.log_error(f"获取系统信息失败: {e}")
            return {}

    def cleanup_resources(self):
        """清理资源"""
        try:
            # 清理分析结果
            if hasattr(self, 'analysis_results'):
                self.analysis_results.clear()

            # 清理性能指标
            if hasattr(self, 'performance_metrics'):
                self.performance_metrics.clear()

            self.log_info("资源清理完成")
        except Exception as e:
            self.log_error(f"资源清理失败: {e}")

    def __del__(self):
        """析构函数"""
        try:
            self.cleanup_resources()
        except:
            pass


class AnalysisToolsPanel(BaseAnalysisPanel, EnhancedBatchAnalysisMixin):
    """Analysis tools panel for the right side of the main window"""

    # 定义信号
    analysis_completed = pyqtSignal(dict)  # 分析完成信号
    data_requested = pyqtSignal(dict)  # 数据请求信号
    error_occurred = pyqtSignal(str)  # 错误信号

    def __init__(self, parent=None):
        """初始化UI组件

        Args:
            parent: 父窗口
        """
        # 1. 先置空关键属性，防止部分流程未初始化时报错
        self.strategy_combo = None
        self.performance_metrics = {}
        self.backtest_widgets = {}
        self.data_cache = {}
        self.current_strategy = None
        self.default_params = {}
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.step_list = QListWidget()
        self.step_status = {}
        self.async_manager = ThreadPoolExecutor(max_workers=8, thread_name_prefix="AnalysisTools")
        self._batch_futures = []
        self._batch_cancelled = False
        self._batch_pause_events = []

        # 增强版批量分析状态
        self.enhanced_batch_analysis_config = {}
        self.enhanced_batch_results = []
        self.enhanced_batch_worker = None
        self._batch_results_lock = threading.Lock()
        self._batch_parallel_workers = 4
        self._last_ui_update_time = 0
        self._ui_update_interval = 500
        self._kline_cache = {}
        self._kline_cache_timeout = 300

        try:

            logger.info("初始化策略回测UI组件")
            super().__init__(parent)

            self.trading_widget = None
            try:
                from gui.widgets.trading_widget import TradingWidget
                self.trading_widget = TradingWidget()
            except Exception as tw_error:
                logger.warning(f"TradingWidget初始化失败: {tw_error}")

            try:
                self.init_ui()
            except Exception as e:
                logger.error(f"init_ui异常: {str(e)}")
                logger.error(traceback.format_exc())
            # 初始化数据
            try:
                self.init_data()
            except Exception as e:
                logger.error(f"init_data异常: {str(e)}")
                logger.error(traceback.format_exc())
            # 连接信号
            try:
                self.connect_signals()
            except Exception as e:
                logger.error(f"connect_signals异常: {str(e)}")
                logger.error(traceback.format_exc())
            logger.info("分析工具面板初始化完成")
            # 监听TradingWidget的analysis_progress信号
            if hasattr(self, 'trading_widget') and hasattr(self.trading_widget, 'analysis_progress'):
                self.trading_widget.analysis_progress.connect(
                    self.on_analysis_progress)
        except Exception as e:
            logger.info(f"初始化UI组件失败: {str(e)}")
            if True:  # 使用Loguru日志
                logger.error(f"初始化UI组件失败: {str(e)}")
                logger.error(traceback.format_exc())
            self.error_occurred.emit(f"初始化失败: {str(e)}")

    def init_ui(self):
        """初始化UI，合并所有功能区，确保所有控件都被正确初始化"""
        try:
            logger.info("初始化策略回测区域")
            layout = self.main_layout  # 用父类的主布局

            # 策略选择区域
            strategy_group = QGroupBox("策略选择")
            strategy_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            strategy_layout = QVBoxLayout()
            strategy_layout.setSpacing(4)
            strategy_layout.setContentsMargins(4, 4, 4, 4)
            self.strategy_combo = QComboBox()

            # 使用新的策略管理系统获取策略列表
            try:
                from core.strategy.strategy_registry import StrategyRegistry
                registry = StrategyRegistry()
                strategies = registry.get_all_strategies()

                if strategies:
                    for strategy in strategies:
                        self.strategy_combo.addItem(f"{strategy.name} - {strategy.description}", strategy.strategy_id)
                    logger.info(f"从策略管理系统加载了 {len(strategies)} 个策略")
                else:
                    # 如果没有策略，添加默认选项
                    default_strategies = ["MA策略", "MACD策略", "RSI策略", "KDJ策略", "布林带策略"]
                    self.strategy_combo.addItems(default_strategies)
                    logger.info("使用默认策略列表")

            except Exception as e:
                # 回退到默认策略列表
                default_strategies = ["MA策略", "MACD策略", "RSI策略", "KDJ策略", "布林带策略"]
                self.strategy_combo.addItems(default_strategies)
                logger.warning(f"策略管理系统加载失败，使用默认策略: {e}")

            strategy_layout.addWidget(self.strategy_combo)
            strategy_group.setLayout(strategy_layout)
            layout.addWidget(strategy_group)

            # 分析按钮
            self.analyze_btn = QPushButton("开始分析")
            self.analyze_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
            """)
            layout.addWidget(self.analyze_btn)

            self._create_batch_analysis_ui(layout)

            logger.info("分析工具面板UI初始化完成")

        except Exception as e:
            logger.error(f"UI初始化失败: {str(e)}")
            logger.error(traceback.format_exc())
            self.error_occurred.emit(f"UI初始化失败: {str(e)}")

    def init_data(self):
        """初始化数据"""
        try:
            logger.info("初始化策略回测数据")
            # 初始化默认参数
            self.default_params = {
                'lookback_period': 20,
                'stop_loss': 0.05,
                'take_profit': 0.10,
                'position_size': 0.1
            }

            # 初始化数据缓存
            self.data_cache = {}
            self.performance_metrics = {}

            logger.info("数据初始化完成")
        except Exception as e:
            logger.error(f"数据初始化失败: {str(e)}")
            self.error_occurred.emit(f"数据初始化失败: {str(e)}")

    def connect_signals(self):
        """连接信号槽"""
        try:
            # 连接分析按钮信号
            if hasattr(self, 'analyze_btn'):
                self.analyze_btn.clicked.connect(self.on_tools_panel_analyze)

            logger.info("信号连接完成")
        except Exception as e:
            logger.error(f"信号连接失败: {str(e)}")
            self.error_occurred.emit(f"信号连接失败: {str(e)}")

    def on_tools_panel_analyze(self):
        """分析按钮点击处理"""
        try:
            logger.info("开始执行策略分析")

            if not hasattr(self, 'strategy_combo') or not self.strategy_combo:
                self.error_occurred.emit("策略选择器未初始化")
                return

            current_strategy = self.strategy_combo.currentText()
            logger.info(f"选择的策略: {current_strategy}")

            # 更新状态
            self.update_status(f"正在分析策略: {current_strategy}")
            self.show_progress(True)
            self.set_progress(10)

            # 模拟分析过程
            QTimer.singleShot(1000, lambda: self.set_progress(50))
            QTimer.singleShot(2000, lambda: self.set_progress(80))
            QTimer.singleShot(3000, self.complete_analysis)

        except Exception as e:
            logger.error(f"分析执行失败: {str(e)}")
            self.error_occurred.emit(f"分析失败: {str(e)}")

    def complete_analysis(self):
        """完成分析"""
        try:
            self.set_progress(100)

            # 生成模拟结果
            results = {
                'strategy': self.strategy_combo.currentText(),
                'total_return': round(random.uniform(0.05, 0.25), 4),
                'sharpe_ratio': round(random.uniform(1.2, 2.5), 2),
                'max_drawdown': round(random.uniform(0.08, 0.15), 4),
                'win_rate': round(random.uniform(0.55, 0.75), 2),
                'total_trades': random.randint(50, 150)
            }

            self.performance_metrics = results
            self.update_status("分析完成")
            self.show_progress(False)

            # 发射完成信号
            self.analysis_completed.emit(results)

            logger.info(f"分析完成: {results}")

        except Exception as e:
            logger.error(f"分析完成处理失败: {str(e)}")
            self.error_occurred.emit(f"分析完成失败: {str(e)}")

    def on_analysis_progress(self, message: str):
        """处理分析进度信息"""
        try:
            self.update_status(message)
            self.analysis_progress.emit(message)
        except Exception as e:
            logger.error(f"进度更新失败: {str(e)}")

    def get_analysis_results(self):
        """获取分析结果"""
        return self.performance_metrics

    def export_analysis_results(self):
        """导出分析结果"""
        try:
            if not self.performance_metrics:
                self.update_status("没有可导出的分析结果", error=True)
                return False

            filename = f"strategy_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            return self.export_results_to_csv(self.performance_metrics, filename)

        except Exception as e:
            logger.error(f"导出分析结果失败: {str(e)}")
            self.update_status(f"导出失败: {str(e)}", error=True)
            return False

    def reset_analysis(self):
        """重置分析状态"""
        try:
            self.performance_metrics.clear()
            self.data_cache.clear()
            self.show_progress(False)
            self.set_progress(0)
            self.update_status("准备就绪")
            logger.info("分析状态已重置")
        except Exception as e:
            logger.error(f"重置分析状态失败: {str(e)}")

    def cleanup_enhanced_batch_analysis(self):
        """清理增强批量分析资源"""
        try:
            if hasattr(self, 'enhanced_batch_worker') and self.enhanced_batch_worker:
                self.enhanced_batch_worker.quit()
                self.enhanced_batch_worker.wait()
                self.enhanced_batch_worker = None

            if hasattr(self, 'enhanced_batch_results'):
                self.enhanced_batch_results.clear()

            if hasattr(self, 'enhanced_batch_analysis_config'):
                self.enhanced_batch_analysis_config.clear()

            logger.info("增强批量分析资源清理完成")
        except Exception as e:
            logger.error(f"增强批量分析资源清理失败: {e}")

    def _create_batch_analysis_ui(self, parent_layout):
        """创建批量分析UI组件"""
        try:
            logger.info("创建批量分析UI组件")

            batch_group = QGroupBox("批量分析")
            batch_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            batch_layout = QVBoxLayout()
            batch_layout.setSpacing(4)
            batch_layout.setContentsMargins(4, 4, 4, 4)

            stock_selection_layout = QHBoxLayout()
            stock_selection_layout.addWidget(QLabel("股票选择:"))
            self.batch_stock_selection_combo = QComboBox()
            self.batch_stock_selection_combo.addItems(["默认股票", "全部股票", "高级筛选条件"])
            self.batch_stock_selection_combo.currentTextChanged.connect(
                self._on_batch_stock_selection_changed)
            stock_selection_layout.addWidget(self.batch_stock_selection_combo)
            stock_selection_layout.addStretch()
            batch_layout.addLayout(stock_selection_layout)

            self.batch_stock_list = QListWidget()
            self.batch_stock_list.setMinimumHeight(80)
            self.batch_stock_list.setMaximumHeight(120)
            self.batch_stock_list.setSelectionMode(QAbstractItemView.MultiSelection)
            batch_layout.addWidget(QLabel("股票列表:"))
            batch_layout.addWidget(self.batch_stock_list)

            stock_buttons_layout = QHBoxLayout()
            select_all_btn = QPushButton("全选")
            select_all_btn.clicked.connect(self._batch_select_all_stocks)
            stock_buttons_layout.addWidget(select_all_btn)

            select_none_btn = QPushButton("全不选")
            select_none_btn.clicked.connect(self._batch_select_no_stocks)
            stock_buttons_layout.addWidget(select_none_btn)

            import_btn = QPushButton("导入")
            import_btn.clicked.connect(self._batch_import_stock_list)
            stock_buttons_layout.addWidget(import_btn)

            stock_buttons_layout.addStretch()
            batch_layout.addLayout(stock_buttons_layout)

            batch_layout.addWidget(QLabel("策略列表:"))
            self.batch_strategy_list = QListWidget()
            self.batch_strategy_list.setMinimumHeight(60)
            self.batch_strategy_list.setMaximumHeight(80)
            self.batch_strategy_list.setSelectionMode(QAbstractItemView.MultiSelection)

            default_strategies = ["MA策略", "MACD策略", "RSI策略", "KDJ策略", "布林带策略"]
            for strategy in default_strategies:
                item = QListWidgetItem(strategy)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                self.batch_strategy_list.addItem(item)
            batch_layout.addWidget(self.batch_strategy_list)

            param_layout = QGridLayout()
            param_layout.addWidget(QLabel("起始日期:"), 0, 0)
            self.batch_start_date = QDateEdit()
            self.batch_start_date.setCalendarPopup(True)
            self.batch_start_date.setDate(QDate.currentDate().addMonths(-1))
            param_layout.addWidget(self.batch_start_date, 0, 1)

            param_layout.addWidget(QLabel("结束日期:"), 0, 2)
            self.batch_end_date = QDateEdit()
            self.batch_end_date.setCalendarPopup(True)
            self.batch_end_date.setDate(QDate.currentDate())
            param_layout.addWidget(self.batch_end_date, 0, 3)

            param_layout.addWidget(QLabel("初始资金:"), 1, 0)
            self.batch_initial_capital_spin = QSpinBox()
            self.batch_initial_capital_spin.setRange(10000, 100000000)
            self.batch_initial_capital_spin.setValue(100000)
            self.batch_initial_capital_spin.setSuffix(" 元")
            param_layout.addWidget(self.batch_initial_capital_spin, 1, 1)

            param_layout.addWidget(QLabel("手续费:"), 1, 2)
            self.batch_commission_spin = QDoubleSpinBox()
            self.batch_commission_spin.setRange(0, 10)
            self.batch_commission_spin.setValue(0.3)
            self.batch_commission_spin.setSuffix(" ‰")
            param_layout.addWidget(self.batch_commission_spin, 1, 3)

            param_layout.addWidget(QLabel("滑点:"), 2, 0)
            self.batch_slippage_spin = QDoubleSpinBox()
            self.batch_slippage_spin.setRange(0, 5)
            self.batch_slippage_spin.setValue(0.1)
            self.batch_slippage_spin.setSuffix(" ‰")
            param_layout.addWidget(self.batch_slippage_spin, 2, 1)

            param_layout.setColumnStretch(1, 1)
            param_layout.setColumnStretch(3, 1)
            batch_layout.addLayout(param_layout)

            control_layout = QHBoxLayout()
            self.batch_start_btn = QPushButton("开始批量分析")
            self.batch_start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
            """)
            self.batch_start_btn.clicked.connect(self.start_enhanced_batch_analysis)
            control_layout.addWidget(self.batch_start_btn)

            self.batch_stop_btn = QPushButton("停止")
            self.batch_stop_btn.setEnabled(False)
            self.batch_stop_btn.clicked.connect(self.stop_enhanced_batch_analysis)
            control_layout.addWidget(self.batch_stop_btn)

            export_btn = QPushButton("导出结果")
            export_btn.clicked.connect(self.export_batch_results)
            control_layout.addWidget(export_btn)

            control_layout.addStretch()
            batch_layout.addLayout(control_layout)

            progress_layout = QHBoxLayout()
            progress_layout.addWidget(QLabel("进度:"))
            self.batch_overall_progress = QProgressBar()
            self.batch_overall_progress.setMaximum(100)
            progress_layout.addWidget(self.batch_overall_progress)
            progress_layout.addWidget(QLabel("已完成:"))
            self.batch_completed_tasks_label = QLabel("0")
            progress_layout.addWidget(self.batch_completed_tasks_label)
            progress_layout.addWidget(QLabel("/"))
            self.batch_total_tasks_label = QLabel("0")
            progress_layout.addWidget(self.batch_total_tasks_label)
            progress_layout.addWidget(QLabel("剩余:"))
            self.batch_remaining_tasks_label = QLabel("0")
            progress_layout.addWidget(self.batch_remaining_tasks_label)
            batch_layout.addLayout(progress_layout)

            self.batch_tabs = QTabWidget()
            self.batch_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

            tasks_tab = QWidget()
            tasks_layout = QVBoxLayout(tasks_tab)
            self.batch_tasks_table = QTableWidget(0, 6)
            self.batch_tasks_table.setHorizontalHeaderLabels(
                ["股票代码", "股票名称", "策略", "状态", "进度", "完成时间"])
            self.batch_tasks_table.horizontalHeader().setStretchLastSection(True)
            self.batch_tasks_table.setAlternatingRowColors(True)
            tasks_layout.addWidget(self.batch_tasks_table)
            self.batch_tabs.addTab(tasks_tab, "任务列表")

            results_tab = QWidget()
            results_layout = QVBoxLayout(results_tab)
            stats_layout = QGridLayout()

            stats_layout.addWidget(QLabel("总组合数:"), 0, 0)
            self.batch_total_combinations_label = QLabel("0")
            stats_layout.addWidget(self.batch_total_combinations_label, 0, 1)

            stats_layout.addWidget(QLabel("盈利组合:"), 0, 2)
            self.batch_profitable_combinations_label = QLabel("0")
            stats_layout.addWidget(self.batch_profitable_combinations_label, 0, 3)

            stats_layout.addWidget(QLabel("最高收益:"), 1, 0)
            self.batch_best_return_label = QLabel("0%")
            stats_layout.addWidget(self.batch_best_return_label, 1, 1)

            stats_layout.addWidget(QLabel("最低收益:"), 1, 2)
            self.batch_worst_return_label = QLabel("0%")
            stats_layout.addWidget(self.batch_worst_return_label, 1, 3)

            stats_layout.addWidget(QLabel("平均收益:"), 2, 0)
            self.batch_avg_return_label = QLabel("0%")
            stats_layout.addWidget(self.batch_avg_return_label, 2, 1)

            stats_layout.addWidget(QLabel("最佳夏普:"), 2, 2)
            self.batch_best_sharpe_label = QLabel("0")
            stats_layout.addWidget(self.batch_best_sharpe_label, 2, 3)

            results_layout.addLayout(stats_layout)

            self.batch_results_table = QTableWidget(0, 8)
            self.batch_results_table.setHorizontalHeaderLabels(
                ["股票代码", "股票名称", "策略", "收益率", "夏普比率", "最大回撤", "胜率", "交易次数"])
            self.batch_results_table.horizontalHeader().setStretchLastSection(True)
            self.batch_results_table.setAlternatingRowColors(True)
            results_layout.addWidget(self.batch_results_table)

            results_buttons_layout = QHBoxLayout()
            sort_return_btn = QPushButton("按收益率排序")
            sort_return_btn.clicked.connect(lambda: self._sort_batch_results('return_rate'))
            results_buttons_layout.addWidget(sort_return_btn)

            sort_sharpe_btn = QPushButton("按夏普排序")
            sort_sharpe_btn.clicked.connect(lambda: self._sort_batch_results('sharpe_ratio'))
            results_buttons_layout.addWidget(sort_sharpe_btn)

            filter_profitable_btn = QPushButton("仅显示盈利")
            filter_profitable_btn.clicked.connect(self._filter_profitable_batch_results)
            results_buttons_layout.addWidget(filter_profitable_btn)

            results_buttons_layout.addStretch()
            results_layout.addLayout(results_buttons_layout)

            self.batch_tabs.addTab(results_tab, "分析结果")

            log_tab = QWidget()
            log_layout = QVBoxLayout(log_tab)
            self.batch_log_text = QTextEdit()
            self.batch_log_text.setReadOnly(True)
            self.batch_log_text.setMaximumHeight(150)
            log_layout.addWidget(self.batch_log_text)

            log_buttons_layout = QHBoxLayout()
            clear_log_btn = QPushButton("清空日志")
            clear_log_btn.clicked.connect(self._clear_batch_log)
            log_buttons_layout.addWidget(clear_log_btn)

            save_log_btn = QPushButton("保存日志")
            save_log_btn.clicked.connect(self._save_batch_log)
            log_buttons_layout.addWidget(save_log_btn)

            log_buttons_layout.addStretch()
            log_layout.addLayout(log_buttons_layout)

            self.batch_tabs.addTab(log_tab, "分析日志")

            batch_layout.addWidget(self.batch_tabs)

            batch_group.setLayout(batch_layout)
            parent_layout.addWidget(batch_group)

            self._load_default_batch_stocks()

            logger.info("批量分析UI组件创建完成")

        except Exception as e:
            logger.error(f"创建批量分析UI失败: {str(e)}")
            logger.error(traceback.format_exc())

    def __del__(self):
        """析构函数"""
        try:
            self.cleanup_enhanced_batch_analysis()
            if hasattr(self, 'async_manager'):
                self.async_manager.shutdown(wait=False)
            super().__del__()
        except:
            pass


# 导出主要类
__all__ = ['BaseAnalysisPanel', 'AnalysisToolsPanel']
