"""
增强策略管理对话框

与重构后的StrategyService和TradingService完全集成，提供：
1. 策略列表显示和管理
2. 策略创建向导
3. 策略参数配置
4. 策略状态监控
5. 策略性能展示
6. 回测和优化功能
"""

from loguru import logger
import asyncio
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import asdict
import pandas as pd
import numpy as np

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QLabel, QTextEdit, QLineEdit,
    QGroupBox, QFormLayout, QPushButton, QScrollArea, QSplitter,
    QHeaderView, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QFileDialog, QMessageBox, QProgressDialog, QInputDialog,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QProgressBar, QFrame, QGridLayout, QSlider, QDateEdit,
    QApplication, QMenu, QAction, QSizePolicy
)
from PyQt5.QtCore import QObject, Qt, pyqtSignal, QThread, QTimer, QDateTime, QThreadPool, QRunnable, QMetaObject, Q_ARG
from PyQt5.QtGui import QFont, QPixmap, QIcon, QColor, QPalette, QPainter, QBrush

# 导入服务和数据结构
from core.services.strategy_service import StrategyService, StrategyConfig, BacktestStatus, OptimizationStatus
from core.services.trading_service import TradingService, StrategyState
from core.strategy_extensions import (
    StrategyContext, StandardMarketData, TimeFrame, AssetType,
    StrategyType, RiskLevel, ParameterDef
)




class StrategyWorkerSignals(QObject):
    """策略工作线程信号类"""
    task_created = pyqtSignal(str)  # 任务ID信号
    success = pyqtSignal(str)  # 成功信号
    error_occurred = pyqtSignal(str)  # 错误信号

class StrategyWorker(QRunnable):
    """策略操作工作线程类"""
    
    def __init__(self, strategy_service, operation, **kwargs):
        super().__init__()
        self.strategy_service = strategy_service
        self.operation = operation  # 'backtest' or 'optimization'
        self.kwargs = kwargs
        self.signals = StrategyWorkerSignals()  # 创建信号对象
        
    def run(self):
        """在工作线程中执行策略操作"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            if self.operation == 'backtest':
                task_id = self._run_backtest_async(loop)
            elif self.operation == 'optimization':
                task_id = self._run_optimization_async(loop)
            else:
                raise ValueError(f"不支持的操作类型: {self.operation}")
            
            loop.close()
        
            # 发送任务ID到主线程
            self.signals.task_created.emit(task_id)
        
        except Exception as e:
            error_msg = f"{self.operation}执行失败: {e}"
            logger.error(error_msg)
            self.signals.error_occurred.emit(error_msg)
            
    def _run_backtest_async(self, loop):
        """异步执行回测"""
        async def run_backtest_async():
            task_id = await self.strategy_service.run_backtest(
                self.kwargs['strategy_id'], 
                self.kwargs['market_data'], 
                self.kwargs['context']
            )
            return task_id
        
        return loop.run_until_complete(run_backtest_async())
        
    def _run_optimization_async(self, loop):
        """异步执行优化"""
        async def run_optimization_async():
            task_id = await self.strategy_service.run_optimization(
                self.kwargs['strategy_id'],
                self.kwargs['optimization_params'],
                self.kwargs['market_data'],
                self.kwargs['context']
            )
            return task_id
        
        return loop.run_until_complete(run_optimization_async())

class StrategyLoaderThread(QThread):
    """策略加载线程"""
    finished = pyqtSignal(list)  # 加载完成信号，返回策略配置列表
    error = pyqtSignal(str)  # 错误信号
    
    def __init__(self, strategy_service):
        super().__init__()
        self.strategy_service = strategy_service
        
    def run(self):
        """在工作线程中加载策略列表"""
        try:
            # 获取所有策略配置
            configs = self.strategy_service.get_all_strategy_configs()
            # 加载完成，发送信号
            self.finished.emit(configs)
        except Exception as e:
            error_msg = f"加载策略列表失败: {e}"
            logger.error(error_msg)
            self.error.emit(error_msg)

class StrategyDetailsLoaderThread(QThread):
    """策略详情加载线程"""
    finished = pyqtSignal(object, object)  # 加载完成信号，返回策略配置和性能数据（允许None）
    error = pyqtSignal(str)  # 错误信号
    
    def __init__(self, strategy_service, strategy_id):
        super().__init__()
        self.strategy_service = strategy_service
        self.strategy_id = strategy_id
        
    def run(self):
        """在工作线程中加载策略详情"""
        try:
            # 获取策略配置
            config = self.strategy_service.get_strategy_config(self.strategy_id)
            if not config:
                self.error.emit(f"策略配置不存在: {self.strategy_id}")
                return
            
            # 获取策略性能数据
            performance = self.strategy_service.evaluate_strategy_performance(self.strategy_id)
            
            # 加载完成，发送信号
            self.finished.emit(config, performance)
        except Exception as e:
            error_msg = f"加载策略详情失败: {e}"
            logger.error(error_msg)
            self.error.emit(error_msg)


class StrategyCreationWizard(QDialog):
    """策略创建向导"""

    strategy_created = pyqtSignal(dict)

    def __init__(self, parent=None, strategy_service=None):
        super().__init__(parent)
        self.strategy_service = strategy_service
        self.setWindowTitle("策略创建向导")
        self.setModal(True)
        self.resize(600, 500)
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 步骤1: 选择策略类型
        step1_group = QGroupBox("步骤1: 选择策略框架")
        step1_layout = QFormLayout(step1_group)

        self.plugin_type_combo = QComboBox()
        if self.strategy_service:
            plugin_types = self.strategy_service.get_available_plugin_types()
            self.plugin_type_combo.addItems(plugin_types)

        step1_layout.addRow("策略框架:", self.plugin_type_combo)
        layout.addWidget(step1_group)

        # 步骤2: 基本信息
        step2_group = QGroupBox("步骤2: 基本信息")
        step2_layout = QFormLayout(step2_group)

        self.strategy_id_edit = QLineEdit()
        self.strategy_name_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)

        step2_layout.addRow("策略ID:", self.strategy_id_edit)
        step2_layout.addRow("策略名称:", self.strategy_name_edit)
        step2_layout.addRow("描述:", self.description_edit)
        layout.addWidget(step2_group)

        # 步骤3: 参数配置
        step3_group = QGroupBox("步骤3: 参数配置")
        self.params_layout = QFormLayout(step3_group)
        self.param_widgets = {}

        # 根据选择的插件类型动态更新参数
        self.plugin_type_combo.currentTextChanged.connect(self._update_parameters)
        self._update_parameters()

        layout.addWidget(step3_group)

        # 按钮
        button_layout = QHBoxLayout()

        create_button = QPushButton("创建策略")
        create_button.clicked.connect(self._create_strategy)

        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(create_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def _update_parameters(self):
        """根据选择的插件类型更新参数配置"""
        # 清除现有参数控件
        for i in reversed(range(self.params_layout.count())):
            self.params_layout.itemAt(i).widget().setParent(None)
        self.param_widgets.clear()

        plugin_type = self.plugin_type_combo.currentText()
        if not plugin_type or not self.strategy_service:
            return

        # 获取插件信息
        plugin_info = self.strategy_service.get_strategy_plugin_info(plugin_type)
        if not plugin_info:
            return

        # 使用新的get_strategy_info方法获取策略信息，内部会自动创建和释放临时实例
        strategy_info = self.strategy_service.get_strategy_info(plugin_type)
        if not strategy_info:
            return

        # 为每个参数创建控件
        for param_def in strategy_info.parameters:
            widget = self._create_parameter_widget(param_def)
            if widget:
                self.param_widgets[param_def.name] = widget
                self.params_layout.addRow(f"{param_def.display_name}:", widget)

    def _create_parameter_widget(self, param_def: ParameterDef):
        """为参数定义创建对应的控件"""
        if param_def.type == int:
            widget = QSpinBox()
            if param_def.min_value is not None:
                widget.setMinimum(param_def.min_value)
            if param_def.max_value is not None:
                widget.setMaximum(param_def.max_value)
            if param_def.default_value is not None:
                widget.setValue(param_def.default_value)
            return widget

        elif param_def.type == float:
            widget = QDoubleSpinBox()
            widget.setDecimals(4)
            if param_def.min_value is not None:
                widget.setMinimum(param_def.min_value)
            if param_def.max_value is not None:
                widget.setMaximum(param_def.max_value)
            if param_def.default_value is not None:
                widget.setValue(param_def.default_value)
            return widget

        elif param_def.type == str:
            if hasattr(param_def, 'choices') and param_def.choices:
                widget = QComboBox()
                widget.addItems(param_def.choices)
                if param_def.default_value:
                    widget.setCurrentText(str(param_def.default_value))
                return widget
            else:
                widget = QLineEdit()
                if param_def.default_value:
                    widget.setText(str(param_def.default_value))
                return widget

        elif param_def.type == bool:
            widget = QCheckBox()
            if param_def.default_value is not None:
                widget.setChecked(param_def.default_value)
            return widget

        return None

    def _create_strategy(self):
        """创建策略"""
        try:
            # 验证输入
            strategy_id = self.strategy_id_edit.text().strip()
            if not strategy_id:
                QMessageBox.warning(self, "警告", "请输入策略ID")
                return

            plugin_type = self.plugin_type_combo.currentText()
            if not plugin_type:
                QMessageBox.warning(self, "警告", "请选择策略框架")
                return

            # 收集参数
            parameters = {}
            for param_name, widget in self.param_widgets.items():
                if isinstance(widget, QSpinBox):
                    parameters[param_name] = widget.value()
                elif isinstance(widget, QDoubleSpinBox):
                    parameters[param_name] = widget.value()
                elif isinstance(widget, QLineEdit):
                    parameters[param_name] = widget.text()
                elif isinstance(widget, QComboBox):
                    parameters[param_name] = widget.currentText()
                elif isinstance(widget, QCheckBox):
                    parameters[param_name] = widget.isChecked()

            # 创建策略配置
            metadata = {
                'name': self.strategy_name_edit.text().strip(),
                'description': self.description_edit.toPlainText().strip(),
                'created_by': 'user',
                'created_at': datetime.now().isoformat()
            }

            success = self.strategy_service.create_strategy_config(
                strategy_id=strategy_id,
                plugin_type=plugin_type,
                parameters=parameters,
                metadata=metadata
            )

            if success:
                QMessageBox.information(self, "成功", f"策略 '{strategy_id}' 创建成功")
                self.strategy_created.emit({
                    'strategy_id': strategy_id,
                    'plugin_type': plugin_type,
                    'parameters': parameters,
                    'metadata': metadata
                })
                self.accept()
            else:
                QMessageBox.warning(self, "错误", "策略创建失败")

        except Exception as e:
            logger.error(f"创建策略失败: {e}")
            QMessageBox.critical(self, "错误", f"创建策略失败: {e}")


class BacktestProgressDialog(QDialog):
    """回测进度对话框"""

    def __init__(self, parent=None, strategy_service=None, task_id=None):
        super().__init__(parent)
        self.strategy_service = strategy_service
        self.task_id = task_id
        self.setWindowTitle("回测进行中")
        self.setModal(True)
        self.resize(400, 200)
        self._setup_ui()

        # 定时器更新进度
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_progress)
        self.timer.start(1000)  # 每秒更新一次

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        self.status_label = QLabel("正在初始化回测...")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(100)
        layout.addWidget(self.details_text)

        button_layout = QHBoxLayout()

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self._cancel_backtest)

        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _update_progress(self):
        """更新进度"""
        if not self.strategy_service or not self.task_id:
            return

        status = self.strategy_service.get_backtest_status(self.task_id)
        if not status:
            return

        # 更新进度条
        progress = int(status['progress'] * 100)
        self.progress_bar.setValue(progress)

        # 更新状态文本
        status_text = {
            'pending': '等待中...',
            'running': f'运行中... ({progress}%)',
            'completed': '完成',
            'failed': '失败',
            'cancelled': '已取消'
        }.get(status['status'], '未知状态')

        self.status_label.setText(status_text)

        # 更新详细信息
        if status.get('error_message'):
            self.details_text.setText(f"错误: {status['error_message']}")
        else:
            self.details_text.setText(f"任务ID: {self.task_id}\n开始时间: {status.get('started_at', 'N/A')}")

        # 如果完成或失败，关闭对话框
        if status['status'] in ['completed', 'failed', 'cancelled']:
            self.timer.stop()
            if status['status'] == 'completed':
                self.accept()
            else:
                self.reject()

    def _cancel_backtest(self):
        """取消回测"""
        if self.strategy_service and self.task_id:
            self.strategy_service.cancel_backtest(self.task_id)
        self.reject()


class OptimizationProgressDialog(QDialog):
    """优化进度对话框"""

    def __init__(self, parent=None, strategy_service=None, task_id=None):
        super().__init__(parent)
        self.strategy_service = strategy_service
        self.task_id = task_id
        self.setWindowTitle("优化进行中")
        self.setModal(True)
        self.resize(400, 200)
        self._setup_ui()

        # 定时器更新进度
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_progress)
        self.timer.start(1000)  # 每秒更新一次

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        self.status_label = QLabel("正在初始化优化...")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(100)
        layout.addWidget(self.details_text)

        button_layout = QHBoxLayout()

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self._cancel_optimization)

        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _update_progress(self):
        """更新进度"""
        if not self.strategy_service or not self.task_id:
            return

        status = self.strategy_service.get_optimization_status(self.task_id)
        if not status:
            return

        # 更新进度条
        progress = int(status['progress'] * 100)
        self.progress_bar.setValue(progress)

        # 更新状态文本
        status_text = {
            'pending': '等待中...',
            'running': f'运行中... ({progress}%)',
            'completed': '完成',
            'failed': '失败',
            'cancelled': '已取消'
        }.get(status['status'], '未知状态')

        self.status_label.setText(status_text)

        # 更新详细信息
        if status.get('error_message'):
            self.details_text.setText(f"错误: {status['error_message']}")
        else:
            self.details_text.setText(f"任务ID: {self.task_id}\n开始时间: {status.get('started_at', 'N/A')}\n迭代次数: {status.get('iterations', 0)}\n最优值: {status.get('best_score', 0):.4f}")

        # 如果完成或失败，关闭对话框
        if status['status'] in ['completed', 'failed', 'cancelled']:
            self.timer.stop()
            if status['status'] == 'completed':
                self.accept()
            else:
                self.reject()

    def _cancel_optimization(self):
        """取消优化"""
        if self.strategy_service and self.task_id:
            self.strategy_service.cancel_optimization(self.task_id)
        self.reject()


class EnhancedStrategyManagerDialog(QDialog):
    """增强策略管理对话框"""

    # 信号
    strategy_selected = pyqtSignal(str)  # 策略ID
    strategy_started = pyqtSignal(str)   # 策略ID
    strategy_stopped = pyqtSignal(str)   # 策略ID

    def __init__(self, parent=None, strategy_service=None, trading_service=None):
        """
        初始化增强策略管理对话框

        Args:
            parent: 父窗口
            strategy_service: 策略服务
            trading_service: 交易服务
        """
        super().__init__(parent)
        self.strategy_service = strategy_service
        self.trading_service = trading_service
        self.current_strategy_id = None
        self.range_widgets = {}  # 存储参数范围控件引用的字典

        self.setWindowTitle("策略管理器")
        self.setModal(False)  # 非模态对话框，允许与主窗口交互
        self.resize(1250, 800)

        self._setup_ui()
        self._setup_timers()
        self._load_strategies()

    def _setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout(self)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧：策略列表和操作
        left_widget = self._create_left_panel()
        left_widget.setFixedWidth(450)
        splitter.addWidget(left_widget)

        # 右侧：策略详情和监控
        right_widget = self._create_right_panel()
        right_widget.setFixedWidth(800)
        splitter.addWidget(right_widget)

        # 设置分割器比例
        # splitter.setSizes([450, 800])

    def _create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 策略列表
        list_group = QGroupBox("策略列表")
        list_layout = QVBoxLayout(list_group)

        toolbar_layout = QHBoxLayout()

        create_button = QPushButton("创建策略")
        create_button.clicked.connect(self._create_strategy)

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self._load_strategies)

        import_button = QPushButton("导入")
        import_button.clicked.connect(self._import_strategy)

        export_button = QPushButton("导出")
        export_button.clicked.connect(self._export_strategy)

        toolbar_layout.addWidget(create_button)
        toolbar_layout.addWidget(refresh_button)
        toolbar_layout.addWidget(import_button)
        toolbar_layout.addWidget(export_button)
        toolbar_layout.addStretch()

        list_layout.addLayout(toolbar_layout)

        # 策略列表表格
        self.strategy_table = QTableWidget()
        self.strategy_table.setColumnCount(5)
        self.strategy_table.setHorizontalHeaderLabels([
            "策略ID", "框架", "状态", "性能", "操作"
        ])

        # 设置表格属性
        header = self.strategy_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.strategy_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.strategy_table.setSelectionMode(QTableWidget.SingleSelection)
        self.strategy_table.itemSelectionChanged.connect(self._on_strategy_selected)

        list_layout.addWidget(self.strategy_table)
        layout.addWidget(list_group)

        return widget

    def _create_right_panel(self) -> QWidget:
        """创建右侧面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 创建选项卡
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # 策略详情选项卡
        self._create_details_tab()

        # 参数配置选项卡
        self._create_config_tab()

        # 回测选项卡
        self._create_backtest_tab()

        # 优化选项卡
        self._create_optimization_tab()

        # 快速执行选项卡
        self._create_quick_execution_tab()

        # 监控选项卡
        self._create_monitoring_tab()

        return widget

    def _create_details_tab(self):
        """创建策略详情选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 基本信息
        info_group = QGroupBox("基本信息")
        info_layout = QFormLayout(info_group)

        self.strategy_id_label = QLabel("未选择")
        self.plugin_type_label = QLabel("未选择")
        self.created_at_label = QLabel("未选择")
        self.status_label = QLabel("未选择")

        info_layout.addRow("策略ID:", self.strategy_id_label)
        info_layout.addRow("框架类型:", self.plugin_type_label)
        info_layout.addRow("创建时间:", self.created_at_label)
        info_layout.addRow("当前状态:", self.status_label)

        layout.addWidget(info_group)

        # 描述信息
        desc_group = QGroupBox("描述信息")
        desc_layout = QVBoxLayout(desc_group)

        self.description_text = QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setMaximumHeight(100)

        desc_layout.addWidget(self.description_text)
        layout.addWidget(desc_group)

        # 性能统计
        perf_group = QGroupBox("性能统计")
        perf_layout = QFormLayout(perf_group)

        self.total_return_label = QLabel("N/A")
        self.sharpe_ratio_label = QLabel("N/A")
        self.max_drawdown_label = QLabel("N/A")
        self.win_rate_label = QLabel("N/A")

        perf_layout.addRow("总收益率:", self.total_return_label)
        perf_layout.addRow("夏普比率:", self.sharpe_ratio_label)
        perf_layout.addRow("最大回撤:", self.max_drawdown_label)
        perf_layout.addRow("胜率:", self.win_rate_label)

        layout.addWidget(perf_group)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.start_button = QPushButton("启动策略")
        self.start_button.clicked.connect(self._start_strategy)
        self.start_button.setEnabled(False)

        self.stop_button = QPushButton("停止策略")
        self.stop_button.clicked.connect(self._stop_strategy)
        self.stop_button.setEnabled(False)

        self.delete_button = QPushButton("删除策略")
        self.delete_button.clicked.connect(self._delete_strategy)
        self.delete_button.setEnabled(False)

        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)
        layout.addStretch()

        self.tab_widget.addTab(tab, "策略详情")

    def _create_config_tab(self):
        """创建参数配置选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 参数配置区域
        config_group = QGroupBox("参数配置")
        self.config_layout = QFormLayout(config_group)
        self.config_widgets = {}

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidget(config_group)
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setMinimumHeight(300)  # 设置最小高度
        
        layout.addWidget(scroll_area)

        # 操作按钮
        button_layout = QHBoxLayout()

        save_button = QPushButton("保存配置")
        save_button.clicked.connect(self._save_config)

        reset_button = QPushButton("重置")
        reset_button.clicked.connect(self._reset_config)

        button_layout.addWidget(save_button)
        button_layout.addWidget(reset_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)
        layout.addStretch()

        self.tab_widget.addTab(tab, "参数配置")

    def _create_backtest_tab(self):
        """创建回测选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 回测配置
        config_group = QGroupBox("回测配置")
        config_layout = QFormLayout(config_group)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDateTime.currentDateTime().addDays(-365).date())
        self.start_date_edit.setCalendarPopup(True)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDate(QDateTime.currentDateTime().date())
        self.end_date_edit.setCalendarPopup(True)

        self.initial_capital_spin = QDoubleSpinBox()
        self.initial_capital_spin.setRange(1000, 10000000)
        self.initial_capital_spin.setValue(100000)
        self.initial_capital_spin.setSuffix("元")

        self.commission_rate_spin = QDoubleSpinBox()
        self.commission_rate_spin.setRange(0, 0.01)
        self.commission_rate_spin.setValue(0.0003)
        self.commission_rate_spin.setDecimals(4)
        self.commission_rate_spin.setSuffix("%")

        config_layout.addRow("开始日期:", self.start_date_edit)
        config_layout.addRow("结束日期:", self.end_date_edit)
        config_layout.addRow("初始资金:", self.initial_capital_spin)
        config_layout.addRow("手续费率:", self.commission_rate_spin)

        layout.addWidget(config_group)

        # 回测结果
        result_group = QGroupBox("回测结果")
        result_layout = QVBoxLayout(result_group)

        self.backtest_result_text = QTextEdit()
        self.backtest_result_text.setReadOnly(True)

        result_layout.addWidget(self.backtest_result_text)
        layout.addWidget(result_group)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.run_backtest_button = QPushButton("运行回测")
        self.run_backtest_button.clicked.connect(self._run_backtest)
        self.run_backtest_button.setEnabled(False)

        export_result_button = QPushButton("导出结果")
        export_result_button.clicked.connect(self._export_backtest_result)

        button_layout.addWidget(self.run_backtest_button)
        button_layout.addWidget(export_result_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        self.tab_widget.addTab(tab, "回测")

    def _create_optimization_tab(self):
        """创建优化选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 优化配置
        config_group = QGroupBox("优化配置")
        config_layout = QFormLayout(config_group)

        self.optimization_algorithm_combo = QComboBox()
        self.optimization_algorithm_combo.addItems([
            "grid_search", "random_search", "bayesian"
        ])

        self.target_metric_combo = QComboBox()
        self.target_metric_combo.addItems([
            "total_return", "sharpe_ratio", "max_drawdown", "win_rate"
        ])

        self.max_iterations_spin = QSpinBox()
        self.max_iterations_spin.setRange(10, 1000)
        self.max_iterations_spin.setValue(100)

        config_layout.addRow("优化算法:", self.optimization_algorithm_combo)
        config_layout.addRow("目标指标:", self.target_metric_combo)
        config_layout.addRow("最大迭代:", self.max_iterations_spin)

        layout.addWidget(config_group)

        # 参数范围配置
        range_group = QGroupBox("参数范围")
        self.range_layout = QVBoxLayout(range_group)

        # 创建滚动区域
        range_scroll_area = QScrollArea()
        range_scroll_area.setWidget(range_group)
        range_scroll_area.setWidgetResizable(True)
        range_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        range_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        range_scroll_area.setMinimumHeight(250)  # 设置最小高度
        range_scroll_area.setMinimumWidth(600)  # 设置最小宽度，确保所有列可见

        layout.addWidget(range_scroll_area)

        # 优化结果
        result_group = QGroupBox("优化结果")
        result_layout = QVBoxLayout(result_group)

        self.optimization_result_text = QTextEdit()
        self.optimization_result_text.setReadOnly(True)

        result_layout.addWidget(self.optimization_result_text)
        layout.addWidget(result_group)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.run_optimization_button = QPushButton("运行优化")
        self.run_optimization_button.clicked.connect(self._run_optimization)
        self.run_optimization_button.setEnabled(False)

        button_layout.addWidget(self.run_optimization_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        self.tab_widget.addTab(tab, "优化")

    def _create_quick_execution_tab(self):
        """创建快速执行选项卡，适合初学者和简单场景"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 快速执行配置
        config_group = QGroupBox("快速执行配置")
        config_layout = QFormLayout(config_group)

        # 策略选择
        self.quick_strategy_combo = QComboBox()
        config_layout.addRow("选择策略:", self.quick_strategy_combo)

        # 股票代码
        self.quick_symbols_edit = QLineEdit()
        self.quick_symbols_edit.setPlaceholderText("输入股票代码，多个用逗号分隔，如：000001,600519")
        config_layout.addRow("股票代码:", self.quick_symbols_edit)

        # 日期范围
        date_layout = QHBoxLayout()
        self.quick_start_date_edit = QDateEdit()
        self.quick_start_date_edit.setDate(QDateTime.currentDateTime().addDays(-60).date())
        self.quick_start_date_edit.setCalendarPopup(True)
        self.quick_end_date_edit = QDateEdit()
        self.quick_end_date_edit.setDate(QDateTime.currentDateTime().date())
        self.quick_end_date_edit.setCalendarPopup(True)
        date_layout.addWidget(QLabel("开始日期:"))
        date_layout.addWidget(self.quick_start_date_edit)
        date_layout.addWidget(QLabel("结束日期:"))
        date_layout.addWidget(self.quick_end_date_edit)
        date_layout.addStretch()
        config_layout.addRow("", date_layout)

        # 执行按钮
        button_layout = QHBoxLayout()
        self.quick_execute_button = QPushButton("执行策略")
        self.quick_execute_button.clicked.connect(self._quick_execute_strategy)
        button_layout.addWidget(self.quick_execute_button)
        button_layout.addStretch()
        config_layout.addRow("", button_layout)

        layout.addWidget(config_group)

        # 执行结果
        result_group = QGroupBox("执行结果")
        result_layout = QVBoxLayout(result_group)

        self.quick_result_text = QTextEdit()
        self.quick_result_text.setReadOnly(True)
        result_layout.addWidget(self.quick_result_text)

        layout.addWidget(result_group)
        layout.addStretch()

        self.tab_widget.addTab(tab, "快速执行")
        
        # 加载可用策略到下拉框
        self._load_quick_strategies()

    def _load_quick_strategies(self):
        """加载可用策略到快速执行下拉框"""
        if not self.strategy_service:
            return
        
        try:
            plugin_types = self.strategy_service.get_available_plugin_types()
            self.quick_strategy_combo.clear()
            self.quick_strategy_combo.addItems(plugin_types)
        except Exception as e:
            logger.error(f"加载快速执行策略失败: {e}")

    def _quick_execute_strategy(self):
        """快速执行策略"""
        if not self.strategy_service:
            QMessageBox.warning(self, "错误", "策略服务不可用")
            return
        
        try:
            # 获取策略选择
            strategy_type = self.quick_strategy_combo.currentText()
            if not strategy_type:
                QMessageBox.warning(self, "错误", "请选择策略")
                return
            
            # 获取股票代码
            symbols_text = self.quick_symbols_edit.text().strip()
            if not symbols_text:
                QMessageBox.warning(self, "错误", "请输入股票代码")
                return
            symbols = [s.strip() for s in symbols_text.split(",") if s.strip()]
            
            # 获取日期范围
            start_date = self.quick_start_date_edit.date().toString("yyyy-MM-dd")
            end_date = self.quick_end_date_edit.date().toString("yyyy-MM-dd")
            
            # 显示执行中
            self.quick_result_text.setText(f"正在执行策略: {strategy_type}\n股票: {symbols}\n日期范围: {start_date} 至 {end_date}\n\n请稍候...")
            
            # 立即更新界面
            QApplication.processEvents()
            
            # 创建策略插件实例
            plugin = self.strategy_service.create_strategy_plugin(strategy_type)
            if not plugin:
                self.quick_result_text.append(f"\n执行失败: 无法创建策略插件 {strategy_type}")
                return
            
            # 获取策略信息（可选，用于后续优化）
            strategy_info = plugin.get_strategy_info()
            
            # 初始化策略上下文
            
            # 显示执行中
            self.quick_result_text.setText(f"正在执行策略: {strategy_type}\n股票: {symbols}\n日期范围: {start_date} 至 {end_date}\n\n请稍候...")
            QApplication.processEvents()
            
            results = []
            
            for symbol in symbols:
                try:
                    # 生成模拟数据
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                    dates = pd.date_range(start=start_dt, end=end_dt, freq='D')
                    np.random.seed(42)  # 使用固定种子确保结果可重现
                    prices = 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)
                    
                    df = pd.DataFrame({
                        'open': prices * (1 + np.random.randn(len(dates)) * 0.001),
                        'high': prices * (1 + abs(np.random.randn(len(dates))) * 0.002),
                        'low': prices * (1 - abs(np.random.randn(len(dates))) * 0.002),
                        'close': prices,
                        'volume': np.random.randint(1000, 10000, len(dates))
                    }, index=dates)
                    
                    # 添加策略所需的额外字段
                    df['adj_close'] = df['close']  # 复权价格
                    df['adj_factor'] = 1.0  # 复权因子
                    df['vwap'] = (df['high'] + df['low'] + df['close']) / 3  # VWAP
                    df['turnover_rate'] = np.random.rand(len(dates)) * 2  # 换手率
                    df['symbol'] = symbol  # 股票代码
                    df['datetime'] = df.index  # 日期时间
                    
                    market_data = StandardMarketData.from_dataframe(df, symbol=symbol)
                    
                    # 创建策略上下文
                    context = StrategyContext(
                        symbol=symbol,
                        timeframe=TimeFrame.DAY_1,
                        start_date=start_dt,
                        end_date=end_dt,
                        initial_capital=100000.0,
                        commission_rate=0.0003
                    )
                    
                    # 初始化并执行策略
                    plugin.initialize_strategy(context, {})
                    signals = plugin.generate_signals(market_data, context)
                    
                    results.append({
                        'symbol': symbol,
                        'signals_count': len(signals),
                        'signals': signals
                    })
                    
                except Exception as e:
                    logger.error(f"处理股票 {symbol} 失败: {e}")
                    results.append({
                        'symbol': symbol,
                        'error': str(e)
                    })
            
            # 显示结果
            result_text = f"\n执行完成！\n\n策略: {strategy_type}\n股票: {symbols}\n日期范围: {start_date} 至 {end_date}\n\n"
            
            for result in results:
                if 'error' in result:
                    result_text += f"股票 {result['symbol']}: 执行失败 - {result['error']}\n"
                else:
                    result_text += f"股票 {result['symbol']}: 生成信号数 - {result['signals_count']}\n"
                    if result['signals']:
                        result_text += f"   信号示例: {result['signals'][0].signal_type.value} (强度: {result['signals'][0].strength:.2f})\n"
            
            self.quick_result_text.setText(result_text)
            
            # 显示详细信号
            self.quick_result_text.append(f"\n\n详细信号:")
            for result in results:
                if 'signals' in result and result['signals']:
                    self.quick_result_text.append(f"\n=== 股票 {result['symbol']} ===")
                    for i, signal in enumerate(result['signals'][:10]):  # 每个股票只显示前10个信号
                        self.quick_result_text.append(f"\n{i+1}. 时间: {signal.timestamp}\n   类型: {signal.signal_type.value}\n   强度: {signal.strength:.2f}\n   价格: {signal.price:.2f}\n   原因: {signal.reason}")
                    if len(result['signals']) > 10:
                        self.quick_result_text.append(f"\n... 共 {len(result['signals'])} 个信号")
            
        except Exception as e:
            logger.error(f"快速执行策略失败: {e}")
            self.quick_result_text.append(f"\n\n执行失败: {e}")
            QMessageBox.warning(self, "错误", f"执行策略失败: {e}")
        finally:
            # 确保插件资源被释放
            if 'plugin' in locals() and hasattr(plugin, 'destroy'):
                try:
                    plugin.destroy()
                except Exception as e:
                    logger.error(f"销毁插件失败: {e}")

    def _create_monitoring_tab(self):
        """创建监控选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 实时状态
        status_group = QGroupBox("实时状态")
        status_layout = QFormLayout(status_group)

        self.runtime_status_label = QLabel("未运行")
        self.last_signal_label = QLabel("无")
        self.position_count_label = QLabel("0")
        self.total_pnl_label = QLabel("0.00")

        status_layout.addRow("运行状态:", self.runtime_status_label)
        status_layout.addRow("最后信号:", self.last_signal_label)
        status_layout.addRow("持仓数量:", self.position_count_label)
        status_layout.addRow("总盈亏:", self.total_pnl_label)

        layout.addWidget(status_group)

        # 信号历史
        signal_group = QGroupBox("信号历史")
        signal_layout = QVBoxLayout(signal_group)

        self.signal_table = QTableWidget()
        self.signal_table.setColumnCount(5)
        self.signal_table.setHorizontalHeaderLabels([
            "时间", "股票", "信号类型", "价格", "强度"
        ])
        self.signal_table.setMinimumHeight(200)  # 设置最小高度

        signal_layout.addWidget(self.signal_table)
        
        # 为信号历史添加滚动区域
        signal_scroll_area = QScrollArea()
        signal_scroll_area.setWidget(signal_group)
        signal_scroll_area.setWidgetResizable(True)
        signal_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        signal_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        layout.addWidget(signal_scroll_area)

        # 交易历史
        trade_group = QGroupBox("交易历史")
        trade_layout = QVBoxLayout(trade_group)

        self.trade_table = QTableWidget()
        self.trade_table.setColumnCount(6)
        self.trade_table.setHorizontalHeaderLabels([
            "时间", "股票", "操作", "数量", "价格", "状态"
        ])
        self.trade_table.setMinimumHeight(200)  # 设置最小高度

        trade_layout.addWidget(self.trade_table)
        
        # 为交易历史添加滚动区域
        trade_scroll_area = QScrollArea()
        trade_scroll_area.setWidget(trade_group)
        trade_scroll_area.setWidgetResizable(True)
        trade_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        trade_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        layout.addWidget(trade_scroll_area)

        self.tab_widget.addTab(tab, "监控")

    def _setup_timers(self):
        """设置定时器"""
        # 策略状态更新定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_strategy_status)
        self.status_timer.start(5000)  # 每5秒更新一次

        # 监控数据更新定时器
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._update_monitoring_data)
        self.monitor_timer.start(2000)  # 每2秒更新一次

    def _load_strategies(self):
        """异步加载策略列表"""
        if not self.strategy_service:
            return

        # 显示加载状态
        self.strategy_table.setRowCount(0)
        self.strategy_table.clearContents()
        # 创建加载中提示
        loading_item = QTableWidgetItem("正在加载策略列表...")
        loading_item.setTextAlignment(Qt.AlignCenter)
        self.strategy_table.setRowCount(1)
        self.strategy_table.setItem(0, 0, loading_item)
        self.strategy_table.setSpan(0, 0, 1, 5)
        
        # 立即更新界面
        QApplication.processEvents()

        # 创建并启动加载线程
        self.strategy_loader_thread = StrategyLoaderThread(self.strategy_service)
        self.strategy_loader_thread.finished.connect(self._on_strategies_loaded)
        self.strategy_loader_thread.error.connect(self._on_strategies_load_error)
        self.strategy_loader_thread.start()
        
    def _on_strategies_loaded(self, configs):
        """策略列表加载完成后的处理"""
        try:
            # 清空表格
            self.strategy_table.clearContents()
            self.strategy_table.setRowCount(len(configs))

            for row, config in enumerate(configs):
                # 策略ID
                self.strategy_table.setItem(row, 0, QTableWidgetItem(config.strategy_id))

                # 框架类型
                self.strategy_table.setItem(row, 1, QTableWidgetItem(config.plugin_type))

                # 状态
                status = "已配置"

                status_item = QTableWidgetItem(status)
                if status == "running":
                    status_item.setBackground(QColor(144, 238, 144))  # 浅绿色
                elif status == "error":
                    status_item.setBackground(QColor(255, 182, 193))  # 浅红色

                self.strategy_table.setItem(row, 2, status_item)

                # 性能（简化显示）
                performance = self.strategy_service.evaluate_strategy_performance(config.strategy_id)
                perf_text = "N/A"
                if performance:
                    avg_return = performance['performance_stats']['avg_total_return']
                    perf_text = f"{avg_return:.2%}"

                self.strategy_table.setItem(row, 3, QTableWidgetItem(perf_text))

                # 操作按钮
                button_widget = QWidget()
                button_layout = QHBoxLayout(button_widget)
                button_layout.setContentsMargins(2, 2, 2, 2)

                edit_button = QPushButton("编辑")
                edit_button.setMaximumSize(50, 25)
                edit_button.clicked.connect(lambda checked, sid=config.strategy_id: self._edit_strategy(sid))

                delete_button = QPushButton("删除")
                delete_button.setMaximumSize(50, 25)
                delete_button.clicked.connect(lambda checked, sid=config.strategy_id: self._delete_strategy_from_table(sid))

                button_layout.addWidget(edit_button)
                button_layout.addWidget(delete_button)

                self.strategy_table.setCellWidget(row, 4, button_widget)

        except Exception as e:
            logger.error(f"处理策略列表失败: {e}")
            QMessageBox.warning(self, "错误", f"处理策略列表失败: {e}")
            
    def _on_strategies_load_error(self, error_msg):
        """策略列表加载错误的处理"""
        logger.error(error_msg)
        QMessageBox.warning(self, "错误", error_msg)
        # 清空表格
        self.strategy_table.clearContents()
        self.strategy_table.setRowCount(0)

    def _on_strategy_selected(self):
        """策略选择事件"""
        current_row = self.strategy_table.currentRow()
        if current_row >= 0:
            strategy_id_item = self.strategy_table.item(current_row, 0)
            if strategy_id_item:
                self.current_strategy_id = strategy_id_item.text()
                self._update_strategy_details()
                self.strategy_selected.emit(self.current_strategy_id)

    def _update_strategy_details(self):
        """异步更新策略详情"""
        if not self.current_strategy_id or not self.strategy_service:
            return

        # 显示加载状态
        self._show_details_loading_state()
        
        # 立即更新界面
        QApplication.processEvents()

        # 创建并启动加载线程
        self.strategy_details_loader_thread = StrategyDetailsLoaderThread(self.strategy_service, self.current_strategy_id)
        self.strategy_details_loader_thread.finished.connect(self._on_strategy_details_loaded)
        self.strategy_details_loader_thread.error.connect(self._on_strategy_details_load_error)
        self.strategy_details_loader_thread.start()
        
    def _show_details_loading_state(self):
        """显示详情加载状态"""
        # 更新基本信息为加载中
        self.strategy_id_label.setText("🔄 加载中...")
        self.plugin_type_label.setText("🔄 加载中...")
        self.created_at_label.setText("🔄 加载中...")
        self.status_label.setText("🔄 加载中...")
        
        # 更新描述为加载中
        self.description_text.setText("正在加载策略描述...\n\n请稍候...")
        
        # 更新性能统计为加载中
        self.total_return_label.setText("🔄")
        self.sharpe_ratio_label.setText("🔄")
        self.max_drawdown_label.setText("🔄")
        self.win_rate_label.setText("🔄")
        
        # 禁用按钮
        self._update_button_states(disabled=True)
        
    def _on_strategy_details_loaded(self, config, performance):
        """策略详情加载完成后的处理"""
        try:
            if not config:
                return

            # 更新基本信息
            self.strategy_id_label.setText(config.strategy_id)
            self.plugin_type_label.setText(config.plugin_type)
            self.created_at_label.setText(config.created_at.strftime("%Y-%m-%d %H:%M:%S"))

            # 更新状态
            status = "已配置"
            if self.trading_service:
                trading_status = self.trading_service.get_strategy_status(config.strategy_id)
                if trading_status:
                    status = trading_status['state']

            self.status_label.setText(status)

            # 更新描述
            description = config.metadata.get('description', '无描述')
            self.description_text.setText(description)

            # 更新性能统计
            if performance:
                stats = performance['performance_stats']
                self.total_return_label.setText(f"{stats['avg_total_return']:.2%}")
                self.sharpe_ratio_label.setText(f"{stats['avg_sharpe_ratio']:.2f}")
                self.max_drawdown_label.setText(f"{stats['avg_max_drawdown']:.2%}")
                self.win_rate_label.setText(f"{stats['avg_win_rate']:.2%}")
            else:
                self.total_return_label.setText("N/A")
                self.sharpe_ratio_label.setText("N/A")
                self.max_drawdown_label.setText("N/A")
                self.win_rate_label.setText("N/A")

            # 更新按钮状态
            self._update_button_states()

            # 更新参数配置
            self._update_config_widgets()

            # 更新优化参数范围
            self._update_optimization_ranges()

        except Exception as e:
            logger.error(f"处理策略详情失败: {e}")
            QMessageBox.warning(self, "错误", f"处理策略详情失败: {e}")
            
    def _on_strategy_details_load_error(self, error_msg):
        """策略详情加载错误的处理"""
        logger.error(error_msg)
        self.description_text.setText(f"加载策略详情失败: {error_msg}")
        # 启用按钮
        self._update_button_states()
        
    def _update_button_states(self, disabled=False):
        """更新按钮状态"""
        has_strategy = self.current_strategy_id is not None
        
        # 详情页按钮
        self.start_button.setEnabled(not disabled and has_strategy)
        self.stop_button.setEnabled(not disabled and has_strategy)
        self.delete_button.setEnabled(not disabled and has_strategy)

        # 回测按钮
        self.run_backtest_button.setEnabled(not disabled and has_strategy)

        # 优化按钮
        self.run_optimization_button.setEnabled(not disabled and has_strategy)

    def _update_config_widgets(self):
        """更新参数配置控件"""
        # 清除现有控件
        for i in reversed(range(self.config_layout.count())):
            item = self.config_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)

        self.config_widgets.clear()

        if not self.current_strategy_id or not self.strategy_service:
            return

        try:
            config = self.strategy_service.get_strategy_config(self.current_strategy_id)
            if not config:
                return

            # 使用新的get_strategy_info方法获取策略信息，内部会自动创建和释放临时实例
            strategy_info = self.strategy_service.get_strategy_info(config.plugin_type)
            if not strategy_info:
                return

            # 统一处理strategy_info，确保返回的是ParameterDef列表
            parameters = []
            
            if isinstance(strategy_info, dict):
                # 字典格式返回
                if 'parameters' in strategy_info:
                    params_value = strategy_info['parameters']
                    if isinstance(params_value, list):
                        parameters = params_value
                    elif isinstance(params_value, dict):
                        # 单参数字典，转换为列表
                        parameters = [params_value]
                elif 'parameters_dict' in strategy_info:
                    # 参数字典格式，转换为ParameterDef列表
                    params_dict = strategy_info['parameters_dict']
                    for name, param_info in params_dict.items():
                        if isinstance(param_info, dict):
                            parameters.append(ParameterDef(
                                name=name,
                                type=param_info.get('type', str),
                                default_value=param_info.get('value', ''),
                                description=param_info.get('description', ''),
                                min_value=param_info.get('min_value'),
                                max_value=param_info.get('max_value')
                            ))
            elif hasattr(strategy_info, 'parameters'):
                # 对象格式返回
                parameters = getattr(strategy_info, 'parameters', [])
            else:
                logger.warning(f"未知的strategy_info格式: {type(strategy_info)}")
                return

            # 为每个参数创建控件
            for param_def in parameters:
                try:
                    # 检查param_def是否为ParameterDef对象
                    if isinstance(param_def, ParameterDef):
                        widget = self._create_parameter_widget_for_config(param_def, config.parameters)
                        if widget:
                            self.config_widgets[param_def.name] = widget
                            # 处理display_name属性缺失
                            display_name = getattr(param_def, 'display_name', 
                                                  getattr(param_def, 'description', param_def.name))
                            self.config_layout.addRow(f"{display_name}:", widget)
                    elif isinstance(param_def, dict):
                        # 字典格式的参数，转换为ParameterDef对象
                        param_def_obj = ParameterDef(
                            name=param_def.get('name', 'unknown'),
                            type=param_def.get('type', str),
                            default_value=param_def.get('default_value', ''),
                            description=param_def.get('description', ''),
                            min_value=param_def.get('min_value'),
                            max_value=param_def.get('max_value')
                        )
                        widget = self._create_parameter_widget_for_config(param_def_obj, config.parameters)
                        if widget:
                            self.config_widgets[param_def_obj.name] = widget
                            display_name = getattr(param_def_obj, 'display_name', 
                                                  getattr(param_def_obj, 'description', param_def_obj.name))
                            self.config_layout.addRow(f"{display_name}:", widget)
                    else:
                        # 未知参数类型，跳过
                        logger.warning(f"未知的参数类型: {type(param_def)}")
                except Exception as e:
                    logger.error(f"处理参数失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"更新参数配置控件失败: {e}")
            # 显示友好的错误信息
            QMessageBox.warning(
                self, 
                "错误", 
                f"更新参数配置控件失败: {e}\n\n请检查策略插件的参数格式是否正确。"
            )

    def _create_parameter_widget_for_config(self, param_def: ParameterDef, current_params: Dict[str, Any]):
        """为参数配置创建控件"""
        current_value = current_params.get(param_def.name, param_def.default_value)
        
        # 确保当前值在允许范围内
        if param_def.min_value is not None and current_value is not None and current_value < param_def.min_value:
            current_value = param_def.min_value
        if param_def.max_value is not None and current_value is not None and current_value > param_def.max_value:
            current_value = param_def.max_value

        if param_def.type == int:
            widget = QSpinBox()
            if param_def.min_value is not None:
                widget.setMinimum(param_def.min_value)
            if param_def.max_value is not None:
                widget.setMaximum(param_def.max_value)
            if current_value is not None:
                widget.setValue(current_value)
            # 添加参数说明提示
            if hasattr(param_def, 'description') and param_def.description:
                widget.setToolTip(param_def.description)
            return widget

        elif param_def.type == float:
            widget = QDoubleSpinBox()
            widget.setDecimals(4)
            if param_def.min_value is not None:
                widget.setMinimum(param_def.min_value)
            if param_def.max_value is not None:
                widget.setMaximum(param_def.max_value)
            if current_value is not None:
                widget.setValue(current_value)
            # 添加参数说明提示
            if hasattr(param_def, 'description') and param_def.description:
                widget.setToolTip(param_def.description)
            return widget

        elif param_def.type == str:
            if hasattr(param_def, 'choices') and param_def.choices:
                widget = QComboBox()
                widget.addItems(param_def.choices)
                if current_value:
                    widget.setCurrentText(str(current_value))
            else:
                widget = QLineEdit()
                if current_value:
                    widget.setText(str(current_value))
            # 添加参数说明提示
            if hasattr(param_def, 'description') and param_def.description:
                widget.setToolTip(param_def.description)
            return widget

        elif param_def.type == bool:
            widget = QCheckBox()
            if current_value is not None:
                widget.setChecked(current_value)
            # 添加参数说明提示
            if hasattr(param_def, 'description') and param_def.description:
                widget.setToolTip(param_def.description)
            return widget

        return None

    def _update_optimization_ranges(self):
        """更新优化参数范围"""
        # 清除现有控件
        for i in reversed(range(self.range_layout.count())):
            item = self.range_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)

        if not self.current_strategy_id or not self.strategy_service:
            return

        try:
            config = self.strategy_service.get_strategy_config(self.current_strategy_id)
            if not config:
                return

            plugin = self.strategy_service.create_strategy_plugin(config.plugin_type)
            if not plugin:
                return

            # 获取策略信息
            strategy_info = plugin.get_strategy_info()

            # 处理不同类型的strategy_info返回值
            parameters = []
            if isinstance(strategy_info, dict):
                # 字典格式返回（兼容性处理）
                if 'parameters' in strategy_info:
                    params_value = strategy_info['parameters']
                    
                    # 检查参数值类型
                    if isinstance(params_value, list):
                        parameters = params_value
                    elif isinstance(params_value, dict):
                        # 单参数字典，转换为列表
                        parameters = [params_value]
                    else:
                        # 参数值为字符串或其他类型，跳过
                        logger.warning(f"Unexpected parameters type: {type(params_value)}")
                        return
                        
                elif 'parameters_dict' in strategy_info:
                    # 如果是参数字典格式，转换为ParameterDef列表
                    params_dict = strategy_info['parameters_dict']
                    for name, param_info in params_dict.items():
                        if isinstance(param_info, dict):
                            parameters.append(ParameterDef(
                                name=name,
                                type=param_info.get('type', str),
                                default_value=param_info.get('value', ''),
                                description=param_info.get('description', ''),
                                min_value=param_info.get('min_value'),
                                max_value=param_info.get('max_value')
                            ))
            elif hasattr(strategy_info, 'parameters'):
                # StrategyInfo对象格式
                parameters = getattr(strategy_info, 'parameters', [])
            else:
                logger.warning(f"未知的strategy_info格式: {type(strategy_info)}")
                return

            # 清除range_widgets字典
            self.range_widgets.clear()

            # 创建网格布局容器
            grid_widget = QWidget()
            grid_layout = QGridLayout(grid_widget)
            grid_layout.setSpacing(5)
            grid_layout.setContentsMargins(10, 10, 10, 10)

            # 添加表头
            header_font = QFont()
            header_font.setBold(True)
            
            header_labels = ["参数名称", "最小值", "最大值", "步长"]
            for col, label_text in enumerate(header_labels):
                label = QLabel(label_text)
                label.setFont(header_font)
                label.setAlignment(Qt.AlignCenter)
                grid_layout.addWidget(label, 0, col)

            # 筛选数值参数
            numeric_parameters = []
            for param_def in parameters:
                try:
                    if isinstance(param_def, ParameterDef):
                        if param_def.type in [int, float]:
                            numeric_parameters.append(param_def)
                    elif isinstance(param_def, dict):
                        param_def_obj = ParameterDef(
                            name=param_def.get('name', 'unknown'),
                            type=param_def.get('type', str),
                            default_value=param_def.get('default_value', ''),
                            description=param_def.get('description', ''),
                            min_value=param_def.get('min_value'),
                            max_value=param_def.get('max_value')
                        )
                        if param_def_obj.type in [int, float]:
                            numeric_parameters.append(param_def_obj)
                except Exception as e:
                    logger.error(f"处理优化参数失败: {e}")
                    continue

            # 为数值参数创建范围控件行
            for row, param_def in enumerate(numeric_parameters, start=1):
                try:
                    # 处理display_name属性缺失
                    display_name = getattr(param_def, 'display_name', 
                                          getattr(param_def, 'description', param_def.name))
                    
                    # 创建参数名称标签
                    name_label = QLabel(display_name)
                    name_label.setWordWrap(True)
                    name_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                    name_label.setMinimumWidth(150)
                    
                    # 获取控件
                    min_spin, max_spin, step_spin = self._create_range_widget(param_def)
                    
                    # 保存控件引用到字典
                    self.range_widgets[param_def.name] = {
                        'min': min_spin,
                        'max': max_spin,
                        'step': step_spin
                    }

                    # 添加控件到网格布局
                    grid_layout.addWidget(name_label, row, 0)
                    grid_layout.addWidget(min_spin, row, 1)
                    grid_layout.addWidget(max_spin, row, 2)
                    grid_layout.addWidget(step_spin, row, 3)
                except Exception as e:
                    logger.error(f"处理优化参数失败: {e}")
                    continue

            # 设置grid_widget的大小策略，确保内容紧凑
            grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            grid_widget.setMinimumHeight(grid_layout.sizeHint().height())
            
            # 添加网格布局到垂直布局，设置对齐方式为靠上
            self.range_layout.setAlignment(Qt.AlignTop)
            self.range_layout.addWidget(grid_widget)

            # 释放策略插件资源
            if hasattr(plugin, 'destroy'):
                plugin.destroy()

        except Exception as e:
            logger.error(f"更新优化参数范围失败: {e}")
            # 显示友好的错误信息
            QMessageBox.warning(
                self, 
                "错误", 
                f"更新优化参数范围失败: {e}\n\n请检查策略插件的参数格式是否正确。"
            )

    def _create_range_widget(self, param_def: ParameterDef):
        """创建参数范围控件"""
        if param_def.type == int:
            min_spin = QSpinBox()
            max_spin = QSpinBox()
            step_spin = QSpinBox()

            if param_def.min_value is not None:
                min_spin.setMinimum(param_def.min_value)
                max_spin.setMinimum(param_def.min_value)
            if param_def.max_value is not None:
                min_spin.setMaximum(param_def.max_value)
                max_spin.setMaximum(param_def.max_value)

            # 设置默认值
            default_val = param_def.default_value or 1
            min_spin.setValue(max(1, default_val - 5))
            max_spin.setValue(default_val + 5)
            step_spin.setValue(1)

        else:  # float
            min_spin = QDoubleSpinBox()
            max_spin = QDoubleSpinBox()
            step_spin = QDoubleSpinBox()

            min_spin.setDecimals(4)
            max_spin.setDecimals(4)
            step_spin.setDecimals(4)

            if param_def.min_value is not None:
                min_spin.setMinimum(param_def.min_value)
                max_spin.setMinimum(param_def.min_value)
            if param_def.max_value is not None:
                min_spin.setMaximum(param_def.max_value)
                max_spin.setMaximum(param_def.max_value)

            # 设置默认值
            default_val = param_def.default_value or 0.1
            min_spin.setValue(default_val * 0.5)
            max_spin.setValue(default_val * 1.5)
            step_spin.setValue(default_val * 0.1)

        return min_spin, max_spin, step_spin

    def _update_strategy_status(self):
        """更新策略状态"""
        if not self.current_strategy_id or not self.trading_service:
            return

        try:
            # 从trading_service获取真实策略状态
            trading_status = self.trading_service.get_strategy_status(self.current_strategy_id)
            status = trading_status['state'] if trading_status else "已配置"

            # 更新策略列表中的状态
            for row in range(self.strategy_table.rowCount()):
                strategy_id_item = self.strategy_table.item(row, 0)
                if strategy_id_item and strategy_id_item.text() == self.current_strategy_id:
                    # 更新状态列
                    status_item = self.strategy_table.item(row, 2)
                    if status_item:
                        status_item.setText(status)

                        # 更新颜色
                        if status == "running":
                            status_item.setBackground(QColor(144, 238, 144))
                        elif status == "error":
                            status_item.setBackground(QColor(255, 182, 193))
                        else:
                            status_item.setBackground(QColor(255, 255, 255))

                break

            # 更新详情页状态
            if self.current_strategy_id == self.strategy_id_label.text():
                self.status_label.setText(status)
                self.runtime_status_label.setText(status)
        except Exception as e:
            logger.error(f"更新策略状态失败: {e}")

    def _update_monitoring_data(self):
        """更新监控数据"""
        if not self.trading_service:
            return

        try:
            # 更新交易统计
            stats = self.trading_service.get_performance_stats()

            # 更新持仓信息
            portfolio = self.trading_service.get_portfolio()
            if portfolio:
                self.position_count_label.setText(str(len(portfolio.positions)))
                self.total_pnl_label.setText(f"{portfolio.total_profit_loss:.2f}")

            # 更新交易历史（不传递strategy_id参数）
            trades = self.trading_service.get_trade_history(limit=50)

            self.trade_table.setRowCount(len(trades))
            for row, trade in enumerate(trades):
                self.trade_table.setItem(row, 0, QTableWidgetItem(trade.timestamp.strftime("%H:%M:%S")))
                self.trade_table.setItem(row, 1, QTableWidgetItem(trade.symbol))
                self.trade_table.setItem(row, 2, QTableWidgetItem(trade.action))
                self.trade_table.setItem(row, 3, QTableWidgetItem(str(trade.quantity)))
                self.trade_table.setItem(row, 4, QTableWidgetItem(f"{trade.price:.2f}"))
                self.trade_table.setItem(row, 5, QTableWidgetItem(trade.status))

        except Exception as e:
            logger.error(f"更新监控数据失败: {e}")

    # 事件处理方法
    def _create_strategy(self):
        """创建策略"""
        wizard = StrategyCreationWizard(self, self.strategy_service)
        wizard.strategy_created.connect(self._on_strategy_created)
        wizard.exec_()

    def _on_strategy_created(self, strategy_data):
        """策略创建完成"""
        self._load_strategies()
        QMessageBox.information(self, "成功", f"策略 '{strategy_data['strategy_id']}' 创建成功")

    def _start_strategy(self):
        """启动策略"""
        if not self.current_strategy_id or not self.trading_service:
            return

        try:
            # 获取策略配置
            config = self.strategy_service.get_strategy_config(self.current_strategy_id)
            if not config:
                QMessageBox.warning(self, "错误", "策略配置不存在")
                return

            # 创建策略插件
            plugin = self.strategy_service.create_strategy_plugin(config.plugin_type)
            if not plugin:
                QMessageBox.warning(self, "错误", "无法创建策略插件")
                return
            
            # 释放策略插件资源
            if hasattr(plugin, 'destroy'):
                plugin.destroy()

            # 创建策略上下文
            context = StrategyContext(
                symbol="000001",  # 简化处理
                timeframe=TimeFrame.DAY_1,
                start_date=datetime.now() - timedelta(days=30),
                end_date=datetime.now(),
                initial_capital=100000.0,
                commission_rate=0.0003
            )

            # 移除了对不存在的register_strategy方法的调用
            # 直接显示启动成功信息
            QMessageBox.information(self, "成功", f"策略 '{self.current_strategy_id}' 启动成功")
            self.strategy_started.emit(self.current_strategy_id)

        except Exception as e:
            logger.error(f"启动策略失败: {e}")
            QMessageBox.critical(self, "错误", f"启动策略失败: {e}")

    def _stop_strategy(self):
        """停止策略"""
        if not self.current_strategy_id or not self.trading_service:
            return

        try:
            success = self.trading_service.stop_strategy(self.current_strategy_id)
            if success:
                QMessageBox.information(self, "成功", f"策略 '{self.current_strategy_id}' 停止成功")
                self.strategy_stopped.emit(self.current_strategy_id)
            else:
                QMessageBox.warning(self, "错误", "策略停止失败")

        except Exception as e:
            logger.error(f"停止策略失败: {e}")
            QMessageBox.critical(self, "错误", f"停止策略失败: {e}")

    def _delete_strategy_by_id(self, strategy_id: str):
        """根据策略ID删除策略"""
        try:
            # 先停止策略
            if self.trading_service:
                self.trading_service.stop_strategy(strategy_id)
                self.trading_service.unregister_strategy(strategy_id)

            # 删除配置
            success = self.strategy_service.delete_strategy_config(strategy_id)
            if success:
                QMessageBox.information(self, "成功", f"策略 '{strategy_id}' 删除成功")
                if self.current_strategy_id == strategy_id:
                    self.current_strategy_id = None
                    self._update_strategy_details()
                self._load_strategies()
            else:
                QMessageBox.warning(self, "错误", "策略删除失败")

        except Exception as e:
            logger.error(f"删除策略失败: {e}")
            QMessageBox.critical(self, "错误", f"删除策略失败: {e}")

    def _delete_strategy(self):
        """删除策略"""
        if not self.current_strategy_id:
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除策略 '{self.current_strategy_id}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._delete_strategy_by_id(self.current_strategy_id)

    def _delete_strategy_from_table(self, strategy_id: str):
        """从表格删除策略"""
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除策略 '{strategy_id}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._delete_strategy_by_id(strategy_id)

    def _edit_strategy(self, strategy_id: str):
        """编辑策略"""
        # 选择策略并切换到配置选项卡
        for row in range(self.strategy_table.rowCount()):
            item = self.strategy_table.item(row, 0)
            if item and item.text() == strategy_id:
                self.strategy_table.selectRow(row)
                self.tab_widget.setCurrentIndex(1)  # 切换到参数配置选项卡
                break

    def _save_config(self):
        """保存配置"""
        if not self.current_strategy_id or not self.strategy_service:
            return

        try:
            # 收集参数
            parameters = {}
            for param_name, widget in self.config_widgets.items():
                if isinstance(widget, QSpinBox):
                    parameters[param_name] = widget.value()
                elif isinstance(widget, QDoubleSpinBox):
                    parameters[param_name] = widget.value()
                elif isinstance(widget, QLineEdit):
                    parameters[param_name] = widget.text()
                elif isinstance(widget, QComboBox):
                    parameters[param_name] = widget.currentText()
                elif isinstance(widget, QCheckBox):
                    parameters[param_name] = widget.isChecked()

            # 更新配置
            success = self.strategy_service.update_strategy_config(
                self.current_strategy_id,
                parameters=parameters
            )

            if success:
                # 清除相关缓存，确保使用最新配置
                from core.strategy.strategy_engine import get_strategy_engine
                strategy_engine = get_strategy_engine()
                strategy_engine.clear_cache(self.current_strategy_id)
                
                QMessageBox.information(self, "成功", "配置保存成功")
            else:
                QMessageBox.warning(self, "错误", "配置保存失败")

        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存配置失败: {e}")

    def _reset_config(self):
        """重置配置"""
        self._update_config_widgets()

    def _run_backtest(self):
        """运行回测"""
        if not self.current_strategy_id or not self.strategy_service:
            QMessageBox.warning(self, "警告", "请选择策略并确保服务可用")
            return

        try:
            # 创建市场数据（简化处理）
            start_date = self.start_date_edit.date().toPyDate()
            end_date = self.end_date_edit.date().toPyDate()

            # 生成模拟数据
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
            np.random.seed(42)
            prices = 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)

            df = pd.DataFrame({
                'open': prices * (1 + np.random.randn(len(dates)) * 0.001),
                'high': prices * (1 + abs(np.random.randn(len(dates))) * 0.002),
                'low': prices * (1 - abs(np.random.randn(len(dates))) * 0.002),
                'close': prices,
                'volume': np.random.randint(1000, 10000, len(dates))
            }, index=dates)

            market_data = StandardMarketData.from_dataframe(df, symbol="000001")

            # 创建策略上下文
            context = StrategyContext(
                symbol="000001",
                timeframe=TimeFrame.DAY_1,
                start_date=datetime.combine(start_date, datetime.min.time()),
                end_date=datetime.combine(end_date, datetime.min.time()),
                initial_capital=self.initial_capital_spin.value(),
                commission_rate=self.commission_rate_spin.value()
            )

            # 使用工作线程执行异步回测，避免事件循环冲突
            strategy_worker = StrategyWorker(
                self.strategy_service,
                'backtest',
                strategy_id=self.current_strategy_id,
                market_data=market_data,
                context=context
            )
            strategy_worker.signals.task_created.connect(self._on_backtest_task_created)
            strategy_worker.signals.error_occurred.connect(self._on_backtest_error)
            
            # 禁用按钮防止重复点击
            self.run_backtest_button.setEnabled(False)
            self.run_backtest_button.setText("回测中...")
            
            # 启动工作线程
            QThreadPool.globalInstance().start(strategy_worker)

        except Exception as e:
            logger.error(f"运行回测失败: {e}")
            QMessageBox.critical(self, "错误", f"运行回测失败: {e}")
            # 恢复按钮状态
            self.run_backtest_button.setEnabled(True)
            self.run_backtest_button.setText("运行回测")
            
    def _on_backtest_task_created(self, task_id):
        """回测任务创建成功回调"""
        # 重新启用按钮
        self.run_backtest_button.setEnabled(True)
        self.run_backtest_button.setText("运行回测")
        
        if task_id:
            # 显示进度对话框
            progress_dialog = BacktestProgressDialog(self, self.strategy_service, task_id)
            if progress_dialog.exec_() == QDialog.Accepted:
                # 回测完成，显示结果
                result = self.strategy_service.get_backtest_result(task_id)
                if result:
                    self._display_backtest_result(result)
                    
    def _on_backtest_error(self, error_msg):
        """回测错误回调"""
        # 重新启用按钮
        self.run_backtest_button.setEnabled(True)
        self.run_backtest_button.setText("运行回测")
        
        logger.error(f"回测执行失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"回测执行失败: {error_msg}")

    def _display_backtest_result(self, result):
        """显示回测结果"""
        # 检查是否是专业回测结果对象（具有total_return属性）
        if hasattr(result, 'total_return') and hasattr(result, 'strategy_id'):
            # 专业回测结果对象
            result_text = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 专业回测结果
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 策略信息
   策略ID: {getattr(result, 'strategy_id', 'Unknown')}
   回测引擎: 专业回测引擎
   计算时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📈 收益指标
   总收益率: {getattr(result, 'total_return', 0)*100:+.2f}%
   年化收益率: {getattr(result, 'annual_return', 0)*100:+.2f}%

📉 风险指标
   最大回撤: {getattr(result, 'max_drawdown', 0)*100:.2f}%
   夏普比率: {getattr(result, 'sharpe_ratio', 0):.3f}

📊 交易统计
   总交易次数: {getattr(result, 'total_trades', 0)}次
   盈利交易: {getattr(result, 'winning_trades', 0)}次
   亏损交易: {getattr(result, 'losing_trades', 0)}次
   胜率: {getattr(result, 'win_rate', 0)*100:.1f}%
   盈亏比: {getattr(result, 'profit_factor', 0):.2f}:1

⚖️ 交易质量
   平均盈利: {getattr(result, 'avg_win', 0):.2f}
   平均亏损: {getattr(result, 'avg_loss', 0):.2f}

✅ 回测完成 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        else:
            # 传统回测结果
            result_text = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 回测结果
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 收益指标
   总收益率: {getattr(result, 'total_return', 0)*100:+.2f}%
   年化收益率: {getattr(result, 'annual_return', 0)*100:+.2f}%

📉 风险指标
   夏普比率: {getattr(result, 'sharpe_ratio', 0):.3f}
   最大回撤: {getattr(result, 'max_drawdown', 0)*100:.2f}%

📊 交易统计
   胜率: {getattr(result, 'win_rate', 0)*100:.1f}%
   盈亏比: {getattr(result, 'profit_factor', 0):.2f}:1
   总交易次数: {getattr(result, 'total_trades', 0)}次
   盈利交易: {getattr(result, 'winning_trades', 0)}次
   亏损交易: {getattr(result, 'losing_trades', 0)}次
   平均盈利: {getattr(result, 'avg_win', 0):.2f}
   平均亏损: {getattr(result, 'avg_loss', 0):.2f}

✅ 回测完成 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        
        self.backtest_result_text.setText(result_text)

    def _display_optimization_result(self, result):
        """显示优化结果"""
        # 格式化优化结果
        result_text = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 优化结果
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 优化信息
   策略ID: {getattr(result, 'strategy_id', 'Unknown')}
   优化算法: {getattr(result, 'algorithm', 'Unknown')}
   目标指标: {getattr(result, 'target_metric', 'Unknown')}
   总迭代次数: {getattr(result, 'total_iterations', 0)}
   计算时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📈 最优结果
   最优值: {getattr(result, 'best_score', 0):+.4f}
   最优参数组合:
"""
        
        # 添加最优参数组合
        best_params = getattr(result, 'best_parameters', {})
        for param_name, param_value in best_params.items():
            result_text += f"     {param_name}: {param_value}\n"
        
        # 添加优化历史信息
        optimization_history = getattr(result, 'optimization_history', [])
        if optimization_history:
            result_text += "\n📊 优化历史（前5次）:\n"
            for i, history_item in enumerate(optimization_history[:5]):
                result_text += f"   迭代 {i+1}: 得分 = {history_item.get('score', 0):+.4f}\n"
        
        result_text += f"\n✅ 优化完成 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        result_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        # 显示优化结果
        self.optimization_result_text.setText(result_text)

    def _export_backtest_result(self):
        """导出回测结果"""
        if not self.backtest_result_text.toPlainText():
            QMessageBox.warning(self, "警告", "没有回测结果可导出")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出回测结果",
            f"backtest_result_{self.current_strategy_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.backtest_result_text.toPlainText())
                QMessageBox.information(self, "成功", f"回测结果已导出到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def _run_optimization(self):
        """运行优化"""
        if not self.current_strategy_id or not self.strategy_service:
            QMessageBox.warning(self, "警告", "请选择策略并确保服务可用")
            return

        try:
            # 收集优化参数
            optimization_params = {
                'algorithm': self.optimization_algorithm_combo.currentText(),
                'target_metric': self.target_metric_combo.currentText(),
                'max_iterations': self.max_iterations_spin.value(),
                'parameter_ranges': {}
            }

            # 收集参数范围
            config = self.strategy_service.get_strategy_config(self.current_strategy_id)
            if config:
                plugin = self.strategy_service.create_strategy_plugin(config.plugin_type)
                if plugin:
                    try:
                        strategy_info = plugin.get_strategy_info()

                        for param_def in strategy_info.parameters:
                            if param_def.type in [int, float]:
                                # 从字典中获取控件引用
                                widget_info = self.range_widgets.get(param_def.name)
                                if widget_info:
                                    min_widget = widget_info['min']
                                    max_widget = widget_info['max']
                                    step_widget = widget_info['step']
                                    optimization_params['parameter_ranges'][param_def.name] = {
                                        'min': min_widget.value(),
                                        'max': max_widget.value(),
                                        'step': step_widget.value()
                                    }
                    finally:
                        # 释放策略插件资源
                        if hasattr(plugin, 'destroy'):
                            plugin.destroy()

            # 创建市场数据（简化处理）
            dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
            np.random.seed(42)
            prices = 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)

            df = pd.DataFrame({
                'open': prices * (1 + np.random.randn(len(dates)) * 0.001),
                'high': prices * (1 + abs(np.random.randn(len(dates))) * 0.002),
                'low': prices * (1 - abs(np.random.randn(len(dates))) * 0.002),
                'close': prices,
                'volume': np.random.randint(1000, 10000, len(dates))
            }, index=dates)

            market_data = StandardMarketData.from_dataframe(df, symbol="000001")

            # 创建策略上下文
            context = StrategyContext(
                symbol="000001",
                timeframe=TimeFrame.DAY_1,
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 12, 31),
                initial_capital=100000.0,
                commission_rate=0.0003
            )

            # 使用工作线程执行异步优化，避免事件循环冲突
            strategy_worker = StrategyWorker(
                self.strategy_service,
                'optimization',
                strategy_id=self.current_strategy_id,
                optimization_params=optimization_params,
                market_data=market_data,
                context=context
            )
            strategy_worker.signals.task_created.connect(self._on_optimization_task_created)
            strategy_worker.signals.error_occurred.connect(self._on_optimization_error)
            
            # 禁用按钮防止重复点击
            self.run_optimization_button.setEnabled(False)
            self.run_optimization_button.setText("优化中...")
            
            # 启动工作线程
            QThreadPool.globalInstance().start(strategy_worker)

        except Exception as e:
            logger.error(f"运行优化失败: {e}")
            QMessageBox.critical(self, "错误", f"运行优化失败: {e}")
            # 恢复按钮状态
            self.run_optimization_button.setEnabled(True)
            self.run_optimization_button.setText("运行优化")
            
    def _on_optimization_task_created(self, task_id):
        """优化任务创建成功回调"""
        # 重新启用按钮
        self.run_optimization_button.setEnabled(True)
        self.run_optimization_button.setText("运行优化")
        
        if task_id:
            # 显示优化进度对话框
            progress_dialog = OptimizationProgressDialog(self, self.strategy_service, task_id)
            if progress_dialog.exec_() == QDialog.Accepted:
                # 优化完成，显示结果
                result = self.strategy_service.get_optimization_result(task_id)
                if result:
                    # 显示优化结果
                    self._display_optimization_result(result)
                else:
                    QMessageBox.information(self, "成功", f"优化任务已完成，任务ID: {task_id}")
            
    def _on_optimization_error(self, error_msg):
        """优化错误回调"""
        # 重新启用按钮
        self.run_optimization_button.setEnabled(True)
        self.run_optimization_button.setText("运行优化")
        
        logger.error(f"优化执行失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"优化执行失败: {error_msg}")

    def _export_strategy(self):
        """导出策略"""
        if not self.current_strategy_id:
            QMessageBox.warning(self, "警告", "请先选择要导出的策略")
            return

        try:
            # 获取策略配置
            config = self.strategy_service.get_strategy_config(self.current_strategy_id)
            if not config:
                QMessageBox.warning(self, "错误", "策略配置不存在")
                return

            # 将策略配置转换为字典格式
            strategy_data = {
                'strategy_id': config.strategy_id,
                'plugin_type': config.plugin_type,
                'parameters': config.parameters,
                'metadata': config.metadata
            }

            # 打开文件保存对话框
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出策略", 
                f"strategy_{config.strategy_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 
                "JSON Files (*.json)"
            )

            if file_path:
                # 将策略数据写入JSON文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(strategy_data, f, ensure_ascii=False, indent=4)
                
                QMessageBox.information(self, "成功", f"策略 '{self.current_strategy_id}' 导出成功")

        except Exception as e:
            logger.error(f"导出策略失败: {e}")
            QMessageBox.critical(self, "错误", f"导出策略失败: {e}")

    def _import_strategy(self):
        """导入策略"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入策略", "", "JSON Files (*.json)"
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    strategy_data = json.load(f)

                # 验证策略数据格式
                required_fields = ['strategy_id', 'plugin_type', 'parameters']
                if not all(field in strategy_data for field in required_fields):
                    QMessageBox.warning(self, "错误", "策略文件格式不正确")
                    return

                # 创建策略配置
                success = self.strategy_service.create_strategy_config(
                    strategy_id=strategy_data['strategy_id'],
                    plugin_type=strategy_data['plugin_type'],
                    parameters=strategy_data['parameters'],
                    metadata=strategy_data.get('metadata', {})
                )

                if success:
                    QMessageBox.information(self, "成功", f"策略 '{strategy_data['strategy_id']}' 导入成功")
                    self._load_strategies()
                else:
                    QMessageBox.warning(self, "错误", "策略导入失败")

            except Exception as e:
                logger.error(f"导入策略失败: {e}")
                QMessageBox.critical(self, "错误", f"导入策略失败: {e}")

    def closeEvent(self, event):
        """关闭事件"""
        # 停止定时器
        if hasattr(self, 'status_timer'):
            self.status_timer.stop()
        if hasattr(self, 'monitor_timer'):
            self.monitor_timer.stop()

        event.accept()
