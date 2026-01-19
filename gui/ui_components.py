"""
UI components for trading system

This module contains reusable UI components for the trading system.
"""

from loguru import logger
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QProgressBar, QTextEdit,
    QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox,
    QListWidget, QTableWidget, QTableWidgetItem, QDialog, QCheckBox,
    QHeaderView, QInputDialog, QAbstractItemView, QMessageBox
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

        try:

            logger.info("初始化策略回测UI组件")
            super().__init__(parent)
            # 集成TradingWidget实例（仅作分析逻辑调用，不显示UI）
            from gui.widgets.trading_widget import TradingWidget
            self.trading_widget = TradingWidget()
            # 初始化UI
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
            strategy_layout = QVBoxLayout()
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
            logger.error(f"增强批量分析资源清理失败: {str(e)}")

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
