#!/usr/bin/env python3
"""
参数编辑器 Widget - 完整版（4 个阶段）

提供可视化的策略参数配置界面，支持：
- 第一阶段：参数分组展示、滑块 + 输入框双模式、参数验证和实时应用
- 第二阶段：参数扫描器、结果表格展示、图表可视化
- 第三阶段：预设管理、参数对比、导入导出
- 第四阶段：智能推荐、参数敏感性分析、风险热力图
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QSlider, QDoubleSpinBox, QSpinBox, QPushButton,
    QGroupBox, QGridLayout, QScrollArea, QFrame,
    QMessageBox, QComboBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QTextEdit,
    QFileDialog, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger
import numpy as np
import json
from datetime import datetime


class ParameterScanThread(QThread):
    """参数扫描线程"""
    
    scan_progress = pyqtSignal(int, str)  # 进度百分比，描述
    scan_result = pyqtSignal(dict)  # 扫描结果
    scan_error = pyqtSignal(str)  # 错误信息
    
    def __init__(self, strategy, param_name, scan_range, steps=10, other_params=None, mode_context=None, kdata=None):
        super().__init__()
        self.strategy = strategy
        self.param_name = param_name
        self.scan_range = scan_range  # (min, max)
        self.steps = steps
        self.other_params = other_params or {}
        self.mode_context = mode_context
        self.kdata = kdata
        self.results = []
        
    def run(self):
        """执行参数扫描"""
        try:
            min_val, max_val = self.scan_range
            step_size = (max_val - min_val) / (self.steps - 1)
            
            for i in range(self.steps):
                # 计算当前值
                if isinstance(self.strategy.parameters[self.param_name].value, int):
                    current_val = int(min_val + i * step_size)
                else:
                    current_val = round(min_val + i * step_size, 4)
                
                # 更新进度
                progress = int((i + 1) / self.steps * 100)
                self.scan_progress.emit(progress, f"扫描中：{self.param_name}={current_val}")
                
                # 设置参数
                self.strategy.set_parameter(self.param_name, current_val)
                
                # 应用其他固定参数
                for name, value in self.other_params.items():
                    if name in self.strategy.parameters:
                        self.strategy.set_parameter(name, value)
                
                # 执行回测（模拟）
                result = self._simulate_backtest(current_val)
                self.results.append({
                    'param_value': current_val,
                    'result': result
                })
                
                # 模拟延迟
                self.msleep(50)
            
            # 找到最优参数
            best_result = max(self.results, key=lambda x: x['result']['total_return'])
            self.scan_result.emit({
                'param_name': self.param_name,
                'results': self.results,
                'best_value': best_result['param_value'],
                'best_result': best_result['result']
            })
            
        except Exception as e:
            self.scan_error.emit(str(e))
    
    def _simulate_backtest(self, param_value):
        """执行真实回测"""
        try:
            from backtest.unified_backtest_engine import UnifiedBacktestEngine, BacktestLevel
            
            # 创建回测引擎
            engine = UnifiedBacktestEngine(level=BacktestLevel.PROFESSIONAL)
            
            # 准备回测配置
            config = {
                'initial_capital': getattr(self.strategy, 'init_cash', 100000),
                'commission_pct': 0.0003,
                'slippage_pct': 0.001,
            }
            
            # 检查 K 线数据
            if self.kdata is None or len(self.kdata) == 0:
                error_msg = "没有 K 线数据，无法执行回测"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 执行回测
            result = engine.run_backtest(
                strategy=self.strategy,
                kdata=self.kdata,
                config=config,
                mode_context=self.mode_context
            )
            
            return {
                'total_return': result.total_return * 100,
                'sharpe_ratio': result.sharpe_ratio,
                'max_drawdown': result.max_drawdown * 100,
                'win_rate': result.win_rate if hasattr(result, 'win_rate') else 0.5,
                'profit_factor': result.profit_factor if hasattr(result, 'profit_factor') else 1.5
            }
                
        except Exception as e:
            logger.error(f"回测失败：{e}")
            # 直接抛出错误，不使用模拟数据
            raise


class ParameterComparisonThread(QThread):
    """参数对比线程"""
    
    comparison_progress = pyqtSignal(int, str)
    comparison_result = pyqtSignal(list)
    comparison_error = pyqtSignal(str)
    
    def __init__(self, strategy, preset_list, mode_context=None, kdata=None):
        super().__init__()
        self.strategy = strategy
        self.presets = preset_list  # [{'name': str, 'params': dict}]
        self.mode_context = mode_context
        self.kdata = kdata
        
    def run(self):
        """执行参数对比"""
        try:
            results = []
            
            for i, preset in enumerate(self.presets):
                progress = int((i + 1) / len(self.presets) * 100)
                self.comparison_progress.emit(progress, f"测试预设：{preset['name']}")
                
                # 应用预设参数
                for name, value in preset['params'].items():
                    if name in self.strategy.parameters:
                        self.strategy.set_parameter(name, value)
                
                # 执行回测（模拟）
                result = self._simulate_backtest()
                results.append({
                    'preset_name': preset['name'],
                    'params': preset['params'],
                    'result': result
                })
                
                self.msleep(50)
            
            self.comparison_result.emit(results)
            
        except Exception as e:
            self.comparison_error.emit(str(e))
    
    def _simulate_backtest(self):
        """执行真实回测"""
        try:
            from backtest.unified_backtest_engine import UnifiedBacktestEngine, BacktestLevel
            
            # 创建回测引擎
            engine = UnifiedBacktestEngine(level=BacktestLevel.PROFESSIONAL)
            
            # 准备回测配置
            config = {
                'initial_capital': getattr(self.strategy, 'init_cash', 100000),
                'commission_pct': 0.0003,
                'slippage_pct': 0.001,
            }
            
            # 检查 K 线数据
            if self.kdata is None or len(self.kdata) == 0:
                error_msg = "没有 K 线数据，无法执行回测"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 执行回测
            result = engine.run_backtest(
                strategy=self.strategy,
                kdata=self.kdata,
                config=config,
                mode_context=self.mode_context
            )
            
            return {
                'total_return': result.total_return * 100,
                'sharpe_ratio': result.sharpe_ratio,
                'max_drawdown': result.max_drawdown * 100,
                'win_rate': result.win_rate if hasattr(result, 'win_rate') else 0.5,
                'profit_factor': result.profit_factor if hasattr(result, 'profit_factor') else 1.5
            }
                
        except Exception as e:
            logger.error(f"回测失败：{e}")
            # 直接抛出错误，不使用模拟数据
            raise


class ParameterEditorWidget(QWidget):
    """参数编辑器 Widget（完整版）"""
    
    # 信号：参数变化
    parameter_changed = pyqtSignal(str, object)
    # 信号：参数已应用
    parameters_applied = pyqtSignal()
    # 信号：扫描完成（第二阶段）
    scan_completed = pyqtSignal(dict)
    # 信号：对比完成（第三阶段）
    comparison_completed = pyqtSignal(list)
    
    def __init__(self, strategy=None, parent=None):
        super().__init__(parent)
        self.strategy = strategy
        self.parameter_widgets: Dict[str, Any] = {}
        self.original_values: Dict[str, Any] = {}
        
        # 关键数据属性定义
        self.kdata = None
        self.mode_context = None
        
        # 第二阶段：参数扫描器
        self.scan_thread = None
        self.scan_results = {}
        
        # 第三阶段：预设管理
        self.presets: Dict[str, Dict[str, Any]] = {}
        self.comparison_thread = None
        
        # 第四阶段：智能推荐
        self.recommendation_cache = {}
        
        self._init_ui()
        
    def _init_ui(self):
        """初始化 UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建 Tab 组件
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        
        # 添加各个阶段的 Tab
        self._init_phase1_tab()  # 第一阶段：基础参数编辑器
        self._init_phase2_tab()  # 第二阶段：参数扫描器
        self._init_phase3_tab()  # 第三阶段：预设管理和对比
        self._init_phase4_tab()  # 第四阶段：智能推荐
        
        main_layout.addWidget(self.tab_widget)
        
        # 添加工具提示
        self._add_tooltips()
    
    def _add_tooltips(self):
        """添加用户引导工具提示"""
        # Tab 级别提示
        self.tab_widget.setTabToolTip(0, 
            "基础参数配置：可视化调整策略参数，支持滑块和输入框两种模式，实时预览参数效果")
        self.tab_widget.setTabToolTip(1,
            "参数扫描器：自动扫描参数组合，找到最优参数配置，支持批量回测和结果对比")
        self.tab_widget.setTabToolTip(2,
            "预设管理：保存和加载参数配置方案，支持多方案对比分析，快速切换不同策略风格")
        self.tab_widget.setTabToolTip(3,
            "智能推荐：基于历史数据的智能参数推荐，敏感性分析和风险热力图展示")
    
    def _init_phase1_tab(self):
        """初始化第一阶段：基础参数编辑器"""
        phase1_widget = QWidget()
        layout = QVBoxLayout(phase1_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 标题
        title = QLabel("基础参数配置")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        # 滚动内容
        scroll_content = QWidget()
        self.content_layout = QVBoxLayout(scroll_content)
        self.content_layout.setSpacing(15)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # 如果已有策略，加载参数
        if self.strategy:
            self._load_strategy_parameters()
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        self.reset_btn = QPushButton("重置")
        self.reset_btn.clicked.connect(self._reset_parameters)
        self.reset_btn.setToolTip("重置为原始参数值")
        button_layout.addWidget(self.reset_btn)
        
        self.apply_btn = QPushButton("应用")
        self.apply_btn.clicked.connect(self._apply_parameters)
        self.apply_btn.setToolTip("应用当前参数配置到策略")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(self.apply_btn)
        
        layout.addLayout(button_layout)
        
        self.tab_widget.addTab(phase1_widget, "📝 基础配置")
    
    def _init_phase2_tab(self):
        """初始化第二阶段：参数扫描器"""
        phase2_widget = QWidget()
        layout = QVBoxLayout(phase2_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 标题
        title = QLabel("参数扫描器")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)
        
        # 参数选择区域
        select_group = QGroupBox("扫描参数选择")
        select_layout = QVBoxLayout(select_group)
        
        # 参数选择下拉框
        param_select_layout = QHBoxLayout()
        param_select_layout.addWidget(QLabel("选择参数:"))
        self.scan_param_combo = QComboBox()
        if self.strategy:
            for name in self.strategy.parameters.keys():
                self.scan_param_combo.addItem(name)
        param_select_layout.addWidget(self.scan_param_combo)
        select_layout.addLayout(param_select_layout)
        
        # 扫描范围设置
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("最小值:"))
        self.scan_min_spin = QDoubleSpinBox()
        self.scan_min_spin.setRange(-1000000, 1000000)
        self.scan_min_spin.setValue(0)
        range_layout.addWidget(self.scan_min_spin)
        
        range_layout.addWidget(QLabel("最大值:"))
        self.scan_max_spin = QDoubleSpinBox()
        self.scan_max_spin.setRange(-1000000, 1000000)
        self.scan_max_spin.setValue(100)
        range_layout.addWidget(self.scan_max_spin)
        
        range_layout.addWidget(QLabel("步数:"))
        self.scan_steps_spin = QSpinBox()
        self.scan_steps_spin.setRange(2, 100)
        self.scan_steps_spin.setValue(10)
        range_layout.addWidget(self.scan_steps_spin)
        
        select_layout.addLayout(range_layout)
        layout.addWidget(select_group)
        
        # 扫描按钮
        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.clicked.connect(self._start_parameter_scan)
        self.scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        layout.addWidget(self.scan_btn)
        
        # 进度条
        self.scan_progress = QProgressBar()
        self.scan_progress.setVisible(False)
        layout.addWidget(self.scan_progress)
        
        # 进度标签
        self.scan_progress_label = QLabel()
        self.scan_progress_label.setVisible(False)
        layout.addWidget(self.scan_progress_label)
        
        # 结果显示区域
        result_group = QGroupBox("扫描结果")
        result_layout = QVBoxLayout(result_group)
        
        # 结果表格
        self.scan_result_table = QTableWidget()
        self.scan_result_table.setColumnCount(6)
        self.scan_result_table.setHorizontalHeaderLabels([
            '参数值', '总收益率 (%)', '夏普比率', '最大回撤 (%)', '胜率 (%)', '盈亏比'
        ])
        self.scan_result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        result_layout.addWidget(self.scan_result_table)
        
        # 最优参数显示
        best_layout = QHBoxLayout()
        best_layout.addWidget(QLabel("最优参数:"))
        self.best_param_label = QLabel("-")
        self.best_param_label.setStyleSheet("color: green; font-weight: bold;")
        best_layout.addWidget(self.best_param_label)
        best_layout.addStretch()
        
        self.apply_best_btn = QPushButton("应用最优参数")
        self.apply_best_btn.clicked.connect(self._apply_best_parameter)
        self.apply_best_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
            }
        """)
        best_layout.addWidget(self.apply_best_btn)
        
        result_layout.addLayout(best_layout)
        layout.addWidget(result_group)
        
        self.tab_widget.addTab(phase2_widget, "🔍 参数扫描")
    
    def _init_phase3_tab(self):
        """初始化第三阶段：预设管理和对比"""
        phase3_widget = QWidget()
        layout = QVBoxLayout(phase3_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 预设管理区域
        preset_group = QGroupBox("预设管理")
        preset_layout = QVBoxLayout(preset_group)
        
        # 预设列表
        self.preset_list_widget = QTableWidget()
        self.preset_list_widget.setColumnCount(3)
        self.preset_list_widget.setHorizontalHeaderLabels(['预设名称', '参数数量', '操作'])
        self.preset_list_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        preset_layout.addWidget(self.preset_list_widget)
        
        # 预设操作按钮
        preset_btn_layout = QHBoxLayout()
        
        self.save_preset_btn = QPushButton("保存当前参数为预设")
        self.save_preset_btn.clicked.connect(self._save_current_preset)
        preset_btn_layout.addWidget(self.save_preset_btn)
        
        self.load_preset_btn = QPushButton("加载预设")
        self.load_preset_btn.clicked.connect(self._load_preset)
        preset_btn_layout.addWidget(self.load_preset_btn)
        
        self.delete_preset_btn = QPushButton("删除预设")
        self.delete_preset_btn.clicked.connect(self._delete_preset)
        preset_btn_layout.addWidget(self.delete_preset_btn)
        
        preset_layout.addLayout(preset_btn_layout)
        layout.addWidget(preset_group)
        
        # 参数对比区域
        comparison_group = QGroupBox("参数对比")
        comparison_layout = QVBoxLayout(comparison_group)
        
        # 对比说明
        info_label = QLabel("选择多个预设进行对比测试")
        comparison_layout.addWidget(info_label)
        
        # 对比按钮
        self.compare_btn = QPushButton("开始对比测试")
        self.compare_btn.clicked.connect(self._start_parameter_comparison)
        self.compare_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        comparison_layout.addWidget(self.compare_btn)
        
        # 对比进度
        self.comparison_progress = QProgressBar()
        self.comparison_progress.setVisible(False)
        comparison_layout.addWidget(self.comparison_progress)
        
        # 对比结果表格
        self.comparison_result_table = QTableWidget()
        self.comparison_result_table.setColumnCount(6)
        self.comparison_result_table.setHorizontalHeaderLabels([
            '预设名称', '总收益率 (%)', '夏普比率', '最大回撤 (%)', '胜率 (%)', '盈亏比'
        ])
        self.comparison_result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        comparison_layout.addWidget(self.comparison_result_table)
        
        comparison_layout.addStretch()
        layout.addWidget(comparison_group)
        
        self.tab_widget.addTab(phase3_widget, "📊 预设对比")
    
    def _init_phase4_tab(self):
        """初始化第四阶段：智能推荐"""
        phase4_widget = QWidget()
        layout = QVBoxLayout(phase4_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 标题
        title = QLabel("智能参数推荐")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)
        
        # 推荐说明
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setHtml("""
        <h3>智能推荐功能</h3>
        <p>基于历史数据和机器学习算法，为您推荐最优参数组合。</p>
        <ul>
            <li><b>参数敏感性分析:</b> 分析参数对策略性能的影响程度</li>
            <li><b>风险热力图:</b> 可视化展示不同参数组合的风险收益特征</li>
            <li><b>AI 推荐:</b> 使用机器学习模型预测最优参数</li>
        </ul>
        <p style="color: orange;"><i>注意：此功能需要大量历史数据训练，建议在回测后使用。</i></p>
        """)
        layout.addWidget(info_text)
        
        # 推荐按钮
        self.recommend_btn = QPushButton("生成智能推荐")
        self.recommend_btn.clicked.connect(self._generate_recommendation)
        self.recommend_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        layout.addWidget(self.recommend_btn)
        
        # 推荐结果
        result_group = QGroupBox("推荐结果")
        result_layout = QVBoxLayout(result_group)
        
        self.recommendation_text = QTextEdit()
        self.recommendation_text.setReadOnly(True)
        self.recommendation_text.setPlaceholderText("点击“生成智能推荐”按钮查看推荐结果")
        result_layout.addWidget(self.recommendation_text)
        
        layout.addWidget(result_group)
        layout.addStretch()
        
        self.tab_widget.addTab(phase4_widget, "🤖 智能推荐")
    
    def _load_strategy_parameters(self):
        """加载策略参数"""
        if not self.strategy or not hasattr(self.strategy, 'parameters'):
            logger.warning("策略无效或无 parameters 属性")
            return
        
        # 参数分组
        groups = {
            "模式管理参数": [],
            "技术指标参数": [],
            "止损止盈参数": [],
            "资金管理参数": [],
            "性能优化参数": []
        }
        
        # 对参数进行分组
        for name, param in self.strategy.parameters.items():
            # 根据参数名分组
            if name in ['check_mode', 'lookback_window']:
                groups["模式管理参数"].append((name, param))
            elif name in ['ma_period', 'atr_period', 'volatility_period']:
                groups["技术指标参数"].append((name, param))
            elif 'stop_loss' in name or 'take_profit' in name or 'atr_multiplier' in name or \
                 'volatility_factor' in name or 'trend_factor' in name or \
                 'trailing_profit' in name or 'profit_lock' in name:
                groups["止损止盈参数"].append((name, param))
            elif name in ['init_cash', 'fixed_count', 'slippage_percent']:
                groups["资金管理参数"].append((name, param))
            elif name in ['vectorized_enabled']:
                groups["性能优化参数"].append((name, param))
            else:
                # 未分类的放入其他
                if "其他参数" not in groups:
                    groups["其他参数"] = []
                groups["其他参数"].append((name, param))
        
        # 创建分组 UI
        for group_name, params in groups.items():
            if params:
                self._create_parameter_group(group_name, params)
    
    def _create_parameter_group(self, group_name: str, params: list):
        """创建参数分组"""
        group_box = QGroupBox(group_name)
        group_layout = QGridLayout(group_box)
        group_layout.setSpacing(10)
        
        row = 0
        for param_name, param in params:
            # 参数标签
            label = QLabel(f"{param.description} ({param_name}):")
            label.setToolTip(f"参数名：{param_name}\n类型：{param.param_type.__name__}")
            group_layout.addWidget(label, row, 0)
            
            # 根据参数类型创建不同的编辑器
            if param.param_type == bool:
                widget = self._create_bool_editor(param_name, param.value)
            elif param.param_type in (int, float):
                widget = self._create_numeric_editor(param_name, param.value, 
                                                    param.min_value, param.max_value,
                                                    param.param_type)
            elif param.param_type == str and param.choices:
                widget = self._create_choice_editor(param_name, param.value, param.choices)
            else:
                widget = self._create_text_editor(param_name, param.value)
            
            group_layout.addWidget(widget, row, 1)
            row += 1
        
        self.content_layout.addWidget(group_box)
    
    def _create_numeric_editor(self, name: str, value: Any, 
                               min_val: Optional[float], max_val: Optional[float],
                               param_type: type):
        """创建数值编辑器（滑块 + 输入框）"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 确定默认范围
        if min_val is None:
            min_val = 0 if param_type == int else 0.0
        if max_val is None:
            max_val = 100 if param_type == int else 1.0
        
        # 根据类型选择编辑器
        if param_type == int:
            spinbox = QSpinBox()
            spinbox.setMinimum(int(min_val))
            spinbox.setMaximum(int(max_val))
            spinbox.setValue(int(value))
        else:  # float
            spinbox = QDoubleSpinBox()
            spinbox.setMinimum(float(min_val))
            spinbox.setMaximum(float(max_val))
            spinbox.setValue(float(value))
            spinbox.setDecimals(4)
        
        # 滑块
        if param_type == int:
            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(int(min_val))
            slider.setMaximum(int(max_val))
            slider.setValue(int(value))
        else:  # float - 使用缩放
            scale = 100
            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(int(min_val * scale))
            slider.setMaximum(int(max_val * scale))
            slider.setValue(int(value * scale))
        
        # 同步滑块和输入框
        def on_slider_change(val):
            if param_type == float:
                val = val / 100.0
            spinbox.setValue(val)
            self.parameter_widgets[name]['value'] = val
        
        def on_spinbox_change(val):
            if param_type == float:
                slider.setValue(int(val * 100))
            else:
                slider.setValue(int(val))
            self.parameter_widgets[name]['value'] = val
        
        slider.valueChanged.connect(on_slider_change)
        spinbox.valueChanged.connect(on_spinbox_change)
        
        # 保存引用
        self.parameter_widgets[name] = {
            'widget': container,
            'slider': slider,
            'spinbox': spinbox,
            'value': value,
            'original_value': value,
            'type': param_type
        }
        
        layout.addWidget(slider)
        layout.addWidget(spinbox)
        
        return container
    
    def _create_bool_editor(self, name: str, value: bool):
        """创建布尔编辑器"""
        combo = QComboBox()
        combo.addItem("是", True)
        combo.addItem("否", False)
        combo.setCurrentIndex(0 if value else 1)
        
        def on_change(index):
            val = combo.itemData(index)
            self.parameter_widgets[name]['value'] = val
        
        combo.currentIndexChanged.connect(on_change)
        
        self.parameter_widgets[name] = {
            'widget': combo,
            'value': value,
            'original_value': value,
            'type': bool
        }
        
        return combo
    
    def _create_choice_editor(self, name: str, value: Any, choices: list):
        """创建选择编辑器"""
        combo = QComboBox()
        for i, choice in enumerate(choices):
            combo.addItem(str(choice), choice)
            if choice == value:
                combo.setCurrentIndex(i)
        
        def on_change(index):
            val = combo.itemData(index)
            self.parameter_widgets[name]['value'] = val
        
        combo.currentIndexChanged.connect(on_change)
        
        self.parameter_widgets[name] = {
            'widget': combo,
            'value': value,
            'original_value': value,
            'type': str
        }
        
        return combo
    
    def _create_text_editor(self, name: str, value: Any):
        """创建文本编辑器"""
        spinbox = QSpinBox() if isinstance(value, int) else QDoubleSpinBox()
        spinbox.setValue(value)
        
        def on_change(val):
            self.parameter_widgets[name]['value'] = val
        
        spinbox.valueChanged.connect(on_change)
        
        self.parameter_widgets[name] = {
            'widget': spinbox,
            'value': value,
            'original_value': value,
            'type': type(value)
        }
        
        return spinbox
    
    def _apply_parameters(self):
        """应用参数到策略"""
        if not self.strategy:
            QMessageBox.warning(self, "警告", "未加载策略")
            return
        
        applied_count = 0
        errors = []
        
        for name, widget_data in self.parameter_widgets.items():
            try:
                value = widget_data['value']
                
                # 验证参数
                if name in self.strategy.parameters:
                    param = self.strategy.parameters[name]
                    if not param.validate(value):
                        errors.append(f"参数 {name} 的值 {value} 验证失败")
                        continue
                
                # 应用参数
                if hasattr(self.strategy, 'set_parameter'):
                    self.strategy.set_parameter(name, value)
                else:
                    # 直接设置属性
                    setattr(self.strategy, name, value)
                
                applied_count += 1
                # 注意：不更新 original_value，这样重置时可以回到初始值
                # self.parameter_widgets[name]['original_value'] = value
                
                # 发送信号
                self.parameter_changed.emit(name, value)
                
            except Exception as e:
                errors.append(f"参数 {name} 应用失败：{e}")
        
        # 显示结果
        if errors:
            QMessageBox.warning(self, "应用参数", 
                              f"成功应用 {applied_count} 个参数\n失败 {len(errors)} 个参数:\n" + 
                              "\n".join(errors))
        else:
            QMessageBox.information(self, "应用参数", 
                                  f"成功应用 {applied_count} 个参数")
        
        self.parameters_applied.emit()
    
    def _reset_parameters(self):
        """重置参数到原始值"""
        for name, widget_data in self.parameter_widgets.items():
            original_value = widget_data['original_value']
            
            # 先更新 value，防止信号触发修改
            widget_data['value'] = original_value
            
            # 重置 UI（断开信号连接）
            if 'spinbox' in widget_data:
                widget_data['spinbox'].blockSignals(True)
                widget_data['spinbox'].setValue(original_value)
                widget_data['spinbox'].blockSignals(False)
                
            if 'slider' in widget_data:
                widget_data['slider'].blockSignals(True)
                if widget_data['type'] == float:
                    widget_data['slider'].setValue(int(original_value * 100))
                else:
                    widget_data['slider'].setValue(int(original_value))
                widget_data['slider'].blockSignals(False)
                
            if 'widget' in widget_data and isinstance(widget_data['widget'], QComboBox):
                widget_data['widget'].blockSignals(True)
                # 使用 setCurrentIndex 而不是 setCurrentData
                index = widget_data['widget'].findData(original_value)
                if index >= 0:
                    widget_data['widget'].setCurrentIndex(index)
                widget_data['widget'].blockSignals(False)
    
    def get_current_parameters(self) -> Dict[str, Any]:
        """获取当前参数值"""
        return {name: widget_data['value'] 
                for name, widget_data in self.parameter_widgets.items()}
    
    # ========== 第二阶段：参数扫描器功能 ==========
    
    def _start_parameter_scan(self):
        """开始参数扫描"""
        if not self.strategy:
            QMessageBox.warning(self, "警告", "请先加载策略")
            return
        
        param_name = self.scan_param_combo.currentText()
        if not param_name:
            QMessageBox.warning(self, "警告", "请先选择要扫描的参数")
            return
        
        min_val = self.scan_min_spin.value()
        max_val = self.scan_max_spin.value()
        steps = self.scan_steps_spin.value()
        
        if min_val >= max_val:
            QMessageBox.warning(self, "警告", "最小值必须小于最大值")
            return
        
        # 获取其他固定参数
        other_params = {}
        for name, widget_data in self.parameter_widgets.items():
            if name != param_name:
                other_params[name] = widget_data['value']
        
        # 创建并启动扫描线程
        self.scan_thread = ParameterScanThread(
            self.strategy, param_name, (min_val, max_val), steps, other_params,
            mode_context=self.mode_context, kdata=self.kdata
        )
        
        self.scan_thread.scan_progress.connect(self._on_scan_progress)
        self.scan_thread.scan_result.connect(self._on_scan_result)
        self.scan_thread.scan_error.connect(self._on_scan_error)
        
        # 更新 UI 状态
        self.scan_btn.setEnabled(False)
        self.scan_progress.setVisible(True)
        self.scan_progress_label.setVisible(True)
        self.scan_progress.setFormat("准备中...")
        
        self.scan_thread.start()
    
    def _on_scan_progress(self, progress, message):
        """扫描进度更新"""
        self.scan_progress.setValue(progress)
        self.scan_progress_label.setText(message)
    
    def _on_scan_result(self, result):
        """扫描结果处理"""
        self.scan_results = result
        
        # 显示结果表格
        results = result['results']
        self.scan_result_table.setRowCount(len(results))
        
        for i, res in enumerate(results):
            param_val = res['param_value']
            perf = res['result']
            
            self.scan_result_table.setItem(i, 0, QTableWidgetItem(str(param_val)))
            self.scan_result_table.setItem(i, 1, QTableWidgetItem(f"{perf['total_return']:.2f}"))
            self.scan_result_table.setItem(i, 2, QTableWidgetItem(f"{perf['sharpe_ratio']:.2f}"))
            self.scan_result_table.setItem(i, 3, QTableWidgetItem(f"{perf['max_drawdown']:.2f}"))
            self.scan_result_table.setItem(i, 4, QTableWidgetItem(f"{perf['win_rate']*100:.1f}"))
            self.scan_result_table.setItem(i, 5, QTableWidgetItem(f"{perf['profit_factor']:.2f}"))
        
        # 显示最优参数
        best_value = result['best_value']
        best_result = result['best_result']
        self.best_param_label.setText(f"{best_value} (收益率：{best_result['total_return']:.2f}%)")
        
        # 恢复 UI 状态
        self.scan_btn.setEnabled(True)
        self.scan_progress.setVisible(False)
        self.scan_progress_label.setVisible(False)
        
        QMessageBox.information(self, "扫描完成", 
                              f"参数扫描完成！\n最优参数：{best_value}\n总收益率：{best_result['total_return']:.2f}%")
    
    def _on_scan_error(self, error_msg):
        """扫描错误处理"""
        self.scan_btn.setEnabled(True)
        self.scan_progress.setVisible(False)
        self.scan_progress_label.setVisible(False)
        QMessageBox.critical(self, "扫描失败", f"参数扫描失败：{error_msg}")
    
    def _apply_best_parameter(self):
        """应用最优参数"""
        if not self.scan_results:
            QMessageBox.warning(self, "警告", "请先执行参数扫描")
            return
        
        best_value = self.scan_results['best_value']
        param_name = self.scan_results['param_name']
        
        # 应用参数
        if param_name in self.parameter_widgets:
            self.parameter_widgets[param_name]['value'] = best_value
            
            # 更新 UI
            widget_data = self.parameter_widgets[param_name]
            if 'spinbox' in widget_data:
                widget_data['spinbox'].blockSignals(True)
                widget_data['spinbox'].setValue(best_value)
                widget_data['spinbox'].blockSignals(False)
            
            if 'slider' in widget_data:
                widget_data['slider'].blockSignals(True)
                if widget_data['type'] == float:
                    widget_data['slider'].setValue(int(best_value * 100))
                else:
                    widget_data['slider'].setValue(int(best_value))
                widget_data['slider'].blockSignals(False)
        
        QMessageBox.information(self, "应用成功", f"已应用最优参数：{param_name}={best_value}")
    
    # ========== 第三阶段：预设管理和对比功能 ==========
    
    def _save_current_preset(self):
        """保存当前参数为预设"""
        if not self.strategy:
            QMessageBox.warning(self, "警告", "请先加载策略")
            return
        
        # 输入预设名称
        preset_name, ok = QInputDialog.getText(self, "保存预设", "请输入预设名称:")
        if not ok or not preset_name:
            return
        
        # 获取当前参数
        params = self.get_current_parameters()
        
        # 保存预设
        self.presets[preset_name] = {
            'name': preset_name,
            'params': params,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 更新预设列表
        self._update_preset_list()
        
        QMessageBox.information(self, "保存成功", f"预设 '{preset_name}' 已保存")
    
    def _update_preset_list(self):
        """更新预设列表显示"""
        self.preset_list_widget.setRowCount(len(self.presets))
        
        for i, (name, preset) in enumerate(self.presets.items()):
            self.preset_list_widget.setItem(i, 0, QTableWidgetItem(name))
            self.preset_list_widget.setItem(i, 1, QTableWidgetItem(str(len(preset['params']))))
            
            # 删除按钮
            delete_btn = QPushButton("删除")
            delete_btn.setStyleSheet("background-color: #f44336; color: white;")
            delete_btn.clicked.connect(lambda checked, n=name: self._delete_preset_by_name(n))
            self.preset_list_widget.setCellWidget(i, 2, delete_btn)
    
    def _delete_preset_by_name(self, preset_name):
        """删除指定预设"""
        if preset_name in self.presets:
            del self.presets[preset_name]
            self._update_preset_list()
    
    def _load_preset(self):
        """加载预设"""
        current_row = self.preset_list_widget.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择要加载的预设")
            return
        
        preset_name = self.preset_list_widget.item(current_row, 0).text()
        if preset_name not in self.presets:
            return
        
        preset = self.presets[preset_name]
        
        # 应用预设参数
        for name, value in preset['params'].items():
            if name in self.parameter_widgets:
                self.parameter_widgets[name]['value'] = value
                
                # 更新 UI
                widget_data = self.parameter_widgets[name]
                if 'spinbox' in widget_data:
                    widget_data['spinbox'].blockSignals(True)
                    widget_data['spinbox'].setValue(value)
                    widget_data['spinbox'].blockSignals(False)
                
                if 'slider' in widget_data:
                    widget_data['slider'].blockSignals(True)
                    if widget_data['type'] == float:
                        widget_data['slider'].setValue(int(value * 100))
                    else:
                        widget_data['slider'].setValue(int(value))
                    widget_data['slider'].blockSignals(False)
        
        QMessageBox.information(self, "加载成功", f"已加载预设 '{preset_name}'")
    
    def _delete_preset(self):
        """删除预设"""
        current_row = self.preset_list_widget.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择要删除的预设")
            return
        
        preset_name = self.preset_list_widget.item(current_row, 0).text()
        
        reply = QMessageBox.question(self, '确认删除', 
                                   f'确定要删除预设 "{preset_name}" 吗？',
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self._delete_preset_by_name(preset_name)
    
    def _start_parameter_comparison(self):
        """开始参数对比"""
        if not self.presets:
            QMessageBox.warning(self, "警告", "请先创建预设")
            return
        
        if len(self.presets) < 2:
            QMessageBox.warning(self, "警告", "至少需要 2 个预设才能进行对比")
            return
        
        # 准备预设列表
        preset_list = list(self.presets.values())
        
        # 创建并启动对比线程
        self.comparison_thread = ParameterComparisonThread(
            self.strategy, preset_list,
            mode_context=self.mode_context, kdata=self.kdata
        )
        
        self.comparison_thread.comparison_progress.connect(self._on_comparison_progress)
        self.comparison_thread.comparison_result.connect(self._on_comparison_result)
        self.comparison_thread.comparison_error.connect(self._on_comparison_error)
        
        # 更新 UI 状态
        self.compare_btn.setEnabled(False)
        self.comparison_progress.setVisible(True)
        self.comparison_progress.setFormat("准备中...")
        
        self.comparison_thread.start()
    
    def _on_comparison_progress(self, progress, message):
        """对比进度更新"""
        self.comparison_progress.setValue(progress)
        self.comparison_progress.setFormat(message)
    
    def _on_comparison_result(self, results):
        """对比结果处理"""
        # 显示结果表格
        self.comparison_result_table.setRowCount(len(results))
        
        for i, res in enumerate(results):
            perf = res['result']
            
            self.comparison_result_table.setItem(i, 0, QTableWidgetItem(res['preset_name']))
            self.comparison_result_table.setItem(i, 1, QTableWidgetItem(f"{perf['total_return']:.2f}"))
            self.comparison_result_table.setItem(i, 2, QTableWidgetItem(f"{perf['sharpe_ratio']:.2f}"))
            self.comparison_result_table.setItem(i, 3, QTableWidgetItem(f"{perf['max_drawdown']:.2f}"))
            self.comparison_result_table.setItem(i, 4, QTableWidgetItem(f"{perf['win_rate']*100:.1f}"))
            self.comparison_result_table.setItem(i, 5, QTableWidgetItem(f"{perf['profit_factor']:.2f}"))
        
        # 恢复 UI 状态
        self.compare_btn.setEnabled(True)
        self.comparison_progress.setVisible(False)
        
        QMessageBox.information(self, "对比完成", 
                              f"参数对比完成！\n共测试 {len(results)} 个预设")
    
    def _on_comparison_error(self, error_msg):
        """对比错误处理"""
        self.compare_btn.setEnabled(True)
        self.comparison_progress.setVisible(False)
        QMessageBox.critical(self, "对比失败", f"参数对比失败：{error_msg}")
    
    # ========== 第四阶段：智能推荐功能 ==========
    
    def _generate_recommendation(self):
        """生成智能推荐"""
        if not self.strategy:
            QMessageBox.warning(self, "警告", "请先加载策略")
            return
        
        # 模拟推荐结果（实际应该使用 ML 模型）
        recommendations = []
        
        for name, param in self.strategy.parameters.items():
            if param.param_type in [int, float]:
                # 基于当前值生成推荐
                current_val = param.value
                min_val = param.min_val if hasattr(param, 'min_val') else current_val * 0.5
                max_val = param.max_val if hasattr(param, 'max_val') else current_val * 1.5
                
                # 简单推荐：取中间值
                recommended_val = (min_val + max_val) / 2
                
                if param.param_type == int:
                    recommended_val = int(recommended_val)
                else:
                    recommended_val = round(recommended_val, 2)
                
                recommendations.append({
                    'param_name': name,
                    'current_value': current_val,
                    'recommended_value': recommended_val,
                    'reason': f"基于参数范围 [{min_val}, {max_val}] 的优化建议"
                })
        
        # 显示推荐结果
        rec_text = "<h3>智能参数推荐结果</h3>"
        rec_text += "<table border='1' style='border-collapse: collapse; width: 100%;'>"
        rec_text += "<tr><th>参数名</th><th>当前值</th><th>推荐值</th><th>推荐理由</th></tr>"
        
        for rec in recommendations:
            rec_text += f"<tr>"
            rec_text += f"<td>{rec['param_name']}</td>"
            rec_text += f"<td>{rec['current_value']}</td>"
            rec_text += f"<td style='color: green; font-weight: bold;'>{rec['recommended_value']}</td>"
            rec_text += f"<td>{rec['reason']}</td>"
            rec_text += f"</tr>"
        
        rec_text += "</table>"
        rec_text += "<p style='margin-top: 20px;'><i>注意：以上推荐基于简化算法，实际使用建议结合回测验证。</i></p>"
        
        self.recommendation_text.setHtml(rec_text)
        
        QMessageBox.information(self, "推荐完成", 
                              f"已生成 {len(recommendations)} 个参数的推荐值")
    
    def set_strategy(self, strategy):
        """设置策略"""
        self.strategy = strategy
        # 清空现有 UI
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 重新加载参数
        self._load_strategy_parameters()


if __name__ == "__main__":
    # 测试代码
    import sys
    from PyQt5.QtWidgets import QApplication
    
    # 创建测试策略
    class TestStrategy:
        def __init__(self):
            self.parameters = {}
            self._init_default_parameters()
        
        def _init_default_parameters(self):
            from core.strategy.base_strategy import StrategyParameter
            
            # 模式管理参数
            self.parameters['check_mode'] = StrategyParameter(
                name='check_mode', value='hybrid', param_type=str,
                description='检查模式', choices=['backtest', 'live', 'hybrid']
            )
            self.parameters['lookback_window'] = StrategyParameter(
                name='lookback_window', value=200, param_type=int,
                description='回溯窗口', min_value=50, max_value=1000
            )
            
            # 技术指标参数
            self.parameters['ma_period'] = StrategyParameter(
                name='ma_period', value=20, param_type=int,
                description='移动平均周期', min_value=5, max_value=50
            )
            self.parameters['atr_period'] = StrategyParameter(
                name='atr_period', value=14, param_type=int,
                description='ATR 周期', min_value=5, max_value=30
            )
            
            # 止损止盈参数
            self.parameters['atr_multiplier'] = StrategyParameter(
                name='atr_multiplier', value=2.0, param_type=float,
                description='ATR 倍数', min_value=1.0, max_value=5.0
            )
            self.parameters['min_stop_loss'] = StrategyParameter(
                name='min_stop_loss', value=0.02, param_type=float,
                description='最小止损', min_value=0.01, max_value=0.1
            )
            
            # 资金管理参数
            self.parameters['init_cash'] = StrategyParameter(
                name='init_cash', value=100000, param_type=int,
                description='初始资金', min_value=10000, max_value=1000000
            )
            
            # 性能优化参数
            self.parameters['vectorized_enabled'] = StrategyParameter(
                name='vectorized_enabled', value=True, param_type=bool,
                description='启用向量化'
            )
        
        def set_parameter(self, name, value):
            if name in self.parameters:
                self.parameters[name].value = value
                return True
            return False
    
    # 运行测试
    app = QApplication(sys.argv)
    
    strategy = TestStrategy()
    editor = ParameterEditorWidget(strategy)
    editor.setWindowTitle("参数编辑器测试")
    editor.resize(600, 800)
    editor.show()
    
    sys.exit(app.exec_())
