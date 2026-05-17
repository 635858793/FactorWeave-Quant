"""
AI选股组件

集成新的AI选股集成服务和可解释性服务，提供完整的AI选股界面
"""

import pandas as pd
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor
from loguru import logger
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import asyncio
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as patches

# UI组件
from gui.ui_components import BaseAnalysisPanel
from core.containers import get_service_container

# 数据管理服务
try:
    from core.services.unified_data_manager import UnifiedDataManager
except ImportError as e:
    logger.warning(f"UnifiedDataManager导入失败: {e}")
    UnifiedDataManager = None

# AI选股相关服务
try:
    from core.services.ai_selection_integration_service import AISelectionIntegrationService
    from core.services.ai_selection_integration_service import StockSelectionCriteria, SelectionStrategy, RiskLevel
    from core.services.ai_explainability_service import AIExplainabilityService, ExplanationLevel
except ImportError as e:
    logger.warning(f"AI选股服务导入失败: {e}")
    AISelectionIntegrationService = None
    AIExplainabilityService = None
    ExplanationLevel = None
    StockSelectionCriteria = None
    SelectionStrategy = None
    RiskLevel = None


class AISelectionWorker(QThread):
    """AI选股工作线程（增强版 - 支持进度更新和取消、自然语言解析）"""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, str)  # 进度百分比, 状态描述
    error = pyqtSignal(str)
    cancelled = pyqtSignal()
    
    def __init__(self, ai_selection_service, criteria, strategy, use_nlp=False, nlp_input=""):
        super().__init__()
        self.ai_selection_service = ai_selection_service
        self.criteria = criteria
        self.strategy = strategy
        self.use_nlp = use_nlp
        self.nlp_input = nlp_input
        self._cancelled = False
        self._error_collector = None
        
    def cancel(self):
        """取消选股"""
        self._cancelled = True
        logger.info("AI选股已取消")
        
    def run(self):
        try:
            self.progress.emit(0, "初始化AI选股分析...")
            
            # 检查是否已取消
            if self._cancelled:
                self.cancelled.emit()
                return
            
            # 初始化错误收集器
            from core.utils.error_collector import ErrorCollector
            self._error_collector = ErrorCollector()
            
            # 定义进度回调函数
            def progress_callback(progress_percent, status_message):
                if self._cancelled:
                    return
                self.progress.emit(progress_percent, status_message)
            
            self.progress.emit(5, "开始AI选股分析...")
            
            # 调用AI选股服务
            if self.use_nlp:
                # 使用自然语言解析模式
                if hasattr(self.ai_selection_service, 'select_stocks_with_nlp'):
                    from utils.async_utils import run_async_blocking
                    result = run_async_blocking(
                        self.ai_selection_service.select_stocks_with_nlp(
                            user_input=self.nlp_input,
                            strategy_type=self.strategy
                        )
                    )
                    
                    # 检查是否已取消
                    if self._cancelled:
                        self.cancelled.emit()
                        return
                    
                    self.progress.emit(100, "AI选股完成")
                    
                    # 添加错误摘要到结果
                    if self._error_collector:
                        result['error_summary'] = self._error_collector.get_summary()
                    
                    self.finished.emit(result)
                else:
                    self.error.emit("AI选股服务不支持自然语言解析")
            else:
                # 使用传统选股模式
                if hasattr(self.ai_selection_service, 'select_stocks'):
                    result = self.ai_selection_service.select_stocks(
                        criteria=self.criteria,
                        strategy=self.strategy,
                        error_collector=self._error_collector,
                        progress_callback=progress_callback
                    )
                    
                    # 检查是否已取消
                    if self._cancelled:
                        self.cancelled.emit()
                        return
                    
                    self.progress.emit(100, "AI选股完成")
                    
                    # 添加错误摘要到结果
                    if self._error_collector:
                        result['error_summary'] = self._error_collector.get_summary()
                    
                    self.finished.emit(result)
                else:
                    self.error.emit("AI选股服务不支持选股功能")
                
        except Exception as e:
            error_msg = f"AI选股失败: {str(e)}"
            self.error.emit(error_msg)
            logger.error(f"AI选股线程错误: {e}")
            logger.error(traceback.format_exc())
            
            # 记录到错误收集器
            if self._error_collector:
                self._error_collector.add_error(
                    error_type="strategy",
                    error_message=error_msg,
                    error_detail=traceback.format_exc(),
                    severity="critical"
                )


class ResultUpdateWorker(QThread):
    """结果更新工作线程 - 在后台处理数据转换和排序，避免阻塞UI"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, selection_results: Dict[str, Dict[str, Any]]):
        super().__init__()
        self.selection_results = selection_results
        
    def run(self):
        try:
            if not self.selection_results:
                self.finished.emit([])
                return
                
            # 转换为列表格式
            stock_list = []
            for stock_code, data in self.selection_results.items():
                stock_list.append([
                    stock_code,
                    data.get("name", ""),
                    f"{data.get('total_score', 0):.2f}",
                    f"{data.get('technical_score', 0):.2f}",
                    f"{data.get('fundamental_score', 0):.2f}",
                    f"{data.get('risk_score', 0):.2f}",
                    data.get("reason", ""),
                    f"{data.get('confidence', 0):.1%}"
                ])
                
            # 按评分排序（在工作线程中执行，不阻塞UI）
            stock_list.sort(key=lambda x: float(x[2]), reverse=True)
            
            self.finished.emit(stock_list)
            
        except Exception as e:
            error_msg = f"结果数据处理失败: {str(e)}"
            logger.error(error_msg)
            self.error.emit(error_msg)


class AIStockSelectionPanel(BaseAnalysisPanel):
    """AI选股面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ai_selection_service = None
        self.explainability_service = None
        self.cache_service = None
        self.selection_results = {}
        self.explanation_data = {}
        
        # 初始化服务
        self._init_services()
        
        # 创建UI
        self._create_ui()
        
    def _init_services(self):
        """初始化AI选股相关服务"""
        try:
            container = get_service_container()
            if container:
                if AISelectionIntegrationService:
                    self.ai_selection_service = container.resolve(AISelectionIntegrationService)
                    logger.info("AI选股集成服务加载成功")
                
                if AIExplainabilityService:
                    self.explainability_service = container.resolve(AIExplainabilityService)
                    logger.info("AI可解释性服务加载成功")
                
                # 初始化缓存服务
                from core.services.cache_service import CacheService
                self.cache_service = container.resolve(CacheService)
                logger.info("缓存服务加载成功")
            else:
                logger.warning("服务容器不可用")
        except Exception as e:
            logger.error(f"服务初始化失败: {e}")
    
    def _get_cached_data(self, cache_key: str, default: Any = None) -> Any:
        """从缓存服务获取数据
        
        Args:
            cache_key: 缓存键
            default: 默认值
            
        Returns:
            缓存数据或默认值
        """
        if self.cache_service:
            return self.cache_service.get(cache_key, default)
        return default
    
    def _set_cached_data(self, cache_key: str, data: Any, ttl: Optional[timedelta] = None) -> None:
        """设置缓存数据
        
        Args:
            cache_key: 缓存键
            data: 缓存数据
            ttl: 过期时间（默认5分钟）
        """
        if self.cache_service:
            if ttl is None:
                ttl = timedelta(minutes=5)
            self.cache_service.set(cache_key, data, ttl=ttl)
    
    def _clear_cache(self, cache_key: Optional[str] = None) -> None:
        """清除缓存
        
        Args:
            cache_key: 缓存键，如果为None则清除所有缓存
        """
        if self.cache_service:
            if cache_key:
                self.cache_service.delete(cache_key)
            else:
                self.cache_service.clear()


    def _create_ui(self):
        """创建UI界面"""
        # 自然语言输入组
        nlp_group = QGroupBox("自然语言选股（可选）")
        nlp_layout = QVBoxLayout(nlp_group)

        # 自然语言输入框
        self.nlp_input = QTextEdit()
        self.nlp_input.setPlaceholderText("请输入选股需求（如：高ROE、低估值、强势资金流等）")
        self.nlp_input.setMaximumHeight(80)
        nlp_layout.addWidget(self.nlp_input)

        # 使用自然语言复选框
        self.use_nlp_check = QCheckBox("使用自然语言解析")
        self.use_nlp_check.setChecked(False)
        self.use_nlp_check.toggled.connect(self._on_nlp_mode_changed)
        nlp_layout.addWidget(self.use_nlp_check)

        self.main_layout.addWidget(nlp_group)

        # 配置区域
        config_group = QGroupBox("AI选股配置")
        config_layout = QGridLayout(config_group)
        
        # 配置项列表
        config_items = [
            ("选股策略:", "strategy_combo"),
            ("选股数量:", "stock_count_spin"),
            ("解释级别:", "explanation_level_combo"),
            ("风险偏好:", "risk_tolerance_combo"),
            ("分析时间范围:", "timeframe_combo"),
            ("数据周期:", "data_period_combo")
        ]
        
        # 创建控件
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems([
            "技术指标驱动",
            "基本面驱动", 
            "综合评分",
            "成长性导向",
            "价值投资",
            "动量策略"
        ])
        
        self.stock_count_spin = QSpinBox()
        self.stock_count_spin.setRange(10, 200)
        self.stock_count_spin.setValue(50)
        self.stock_count_spin.setSuffix(" 只")
        
        if ExplanationLevel:
            self.explanation_level_combo = QComboBox()
            self.explanation_level_combo.addItems([
                "简单解释", "详细解释", "专业解释"
            ])
        
        self.risk_tolerance_combo = QComboBox()
        self.risk_tolerance_combo.addItems(["保守", "稳健", "积极", "激进"])
        
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems([
            "最近1个月", "最近3个月", "最近6个月", "最近1年"
        ])
        
        from core.plugin_types import Period
        self.data_period_combo = QComboBox()
        self.data_period_combo.addItems(Period.all_periods())
        self.data_period_combo.setCurrentText(Period.get_display_name(Period.DAY.value))
        
        # 2行3列布局
        for i, (label_text, widget_name) in enumerate(config_items):
            row = i // 3
            col = i % 3
            
            label = QLabel(label_text)
            widget = getattr(self, widget_name)
            
            config_layout.addWidget(label, row, col * 2)
            config_layout.addWidget(widget, row, col * 2 + 1)
        
        self.main_layout.addWidget(config_group)
        
        # 技术指标配置
        indicator_group = QGroupBox("技术指标权重")
        indicator_layout = QGridLayout(indicator_group)
        
        # 常用技术指标
        indicators = [
            ("MA5", 0.1), ("MA10", 0.15), ("MA20", 0.2),
            ("MACD", 0.15), ("RSI", 0.1), ("KDJ", 0.1),
            ("BOLL", 0.1), ("OBV", 0.1)
        ]
        
        self.indicator_weights = {}
        for i, (indicator, default_weight) in enumerate(indicators):
            row, col = i // 4, i % 4
            weight_spin = QDoubleSpinBox()
            weight_spin.setRange(0.0, 1.0)
            weight_spin.setSingleStep(0.05)
            weight_spin.setValue(default_weight)
            weight_spin.setSuffix(" (权重)")
            indicator_layout.addWidget(QLabel(f"{indicator}:"), row, col * 2)
            indicator_layout.addWidget(weight_spin, row, col * 2 + 1)
            self.indicator_weights[indicator] = weight_spin
            
        self.main_layout.addWidget(indicator_group)
        
        # 基本面指标配置
        fundamental_group = QGroupBox("基本面指标权重")
        fundamental_layout = QGridLayout(fundamental_group)
        
        fundamentals = [
            ("PE比率", 0.2), ("PB比率", 0.15), ("ROE", 0.2),
            ("营收增长率", 0.15), ("净利润增长率", 0.2), ("负债率", 0.1)
        ]
        
        self.fundamental_weights = {}
        for i, (fundamental, default_weight) in enumerate(fundamentals):
            row, col = i // 3, i % 3
            weight_spin = QDoubleSpinBox()
            weight_spin.setRange(0.0, 1.0)
            weight_spin.setSingleStep(0.05)
            weight_spin.setValue(default_weight)
            weight_spin.setSuffix(" (权重)")
            fundamental_layout.addWidget(QLabel(f"{fundamental}:"), row, col * 2)
            fundamental_layout.addWidget(weight_spin, row, col * 2 + 1)
            self.fundamental_weights[fundamental] = weight_spin
            
        self.main_layout.addWidget(fundamental_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("开始AI选股")
        self.start_btn.clicked.connect(self.start_ai_selection)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border: none;
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
        button_layout.addWidget(self.start_btn)
        
        self.export_btn = QPushButton("导出结果")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)
        
        self.clear_btn = QPushButton("清空结果")
        self.clear_btn.clicked.connect(self.clear_results)
        button_layout.addWidget(self.clear_btn)
        
        # 进度条（默认隐藏）
        self.progress_container = QWidget()
        progress_layout = QHBoxLayout(self.progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximumWidth(300)
        self.progress_bar.setVisible(False)
        
        # 设置渐变色滚动样式
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #4CAF50;
                border-radius: 5px;
                text-align: center;
                background-color: #f0f0f0;
                height: 20px;
            }
            QProgressBar::chunk {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:0.5 #8BC34A, stop:1 #CDDC39);
                border-radius: 3px;
            }
        """)
        
        self.status_label = QLabel("初始化...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setVisible(False)
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        
        self.progress_container.setVisible(False)
        button_layout.addWidget(self.progress_container)
        
        button_layout.addStretch()
        
        # LLM配置按钮
        self.llm_config_btn = QPushButton("LLM配置")
        self.llm_config_btn.clicked.connect(self.open_llm_config)
        self.llm_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1a5cd6;
            }
            QPushButton:pressed {
                background-color: #154eb3;
            }
        """)
        button_layout.addWidget(self.llm_config_btn)
        
        # 历史记录按钮
        self.history_btn = QPushButton("历史记录")
        self.history_btn.clicked.connect(self.open_history_panel)
        self.history_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e68900;
            }
            QPushButton:pressed {
                background-color: #cc7a00;
            }
        """)
        button_layout.addWidget(self.history_btn)
        
        self.main_layout.addLayout(button_layout)
        
        # 结果显示区域
        self._create_results_area()
        
    def _create_results_area(self):
        """创建结果显示区域"""
        results_group = QGroupBox("选股结果")
        results_layout = QVBoxLayout(results_group)
        
        # 结果表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(8)
        self.result_table.setHorizontalHeaderLabels([
            "股票代码", "股票名称", "综合评分", "技术评分", "基本面评分", 
            "风险评分", "推荐理由", "置信度"
        ])
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.result_table.itemSelectionChanged.connect(self.on_selection_changed)
        results_layout.addWidget(self.result_table)
        
        # 分页控件
        page_layout = QHBoxLayout()
        self.prev_page_btn = QPushButton("上一页")
        self.prev_page_btn.clicked.connect(self.prev_page)
        self.prev_page_btn.setEnabled(False)
        page_layout.addWidget(self.prev_page_btn)
        
        self.page_label = QLabel("第 1 页 / 共 1 页")
        page_layout.addWidget(self.page_label)
        
        self.next_page_btn = QPushButton("下一页")
        self.next_page_btn.clicked.connect(self.next_page)
        self.next_page_btn.setEnabled(False)
        page_layout.addWidget(self.next_page_btn)
        
        page_layout.addStretch()
        results_layout.addLayout(page_layout)
        
        self.main_layout.addWidget(results_group)
        
        # 可解释性区域
        explain_group = QGroupBox("选股可解释性")
        explain_layout = QVBoxLayout(explain_group)
        
        # 解释文本显示
        self.explain_text = QTextEdit()
        self.explain_text.setMaximumHeight(200)
        self.explain_text.setReadOnly(True)
        explain_layout.addWidget(self.explain_text)
        
        # 因子贡献图
        self.factor_chart = FigureCanvas(Figure(figsize=(6, 4)))
        self.factor_chart.setMinimumHeight(150)
        explain_layout.addWidget(self.factor_chart)
        
        self.main_layout.addWidget(explain_group)
        
        # 初始化分页
        self.current_page = 1
        self.page_size = 20
        self.total_pages = 1
        
    def _on_nlp_mode_changed(self, checked: bool):
        """自然语言模式切换"""
        if checked:
            # 启用自然语言输入框，禁用其他配置
            self.nlp_input.setEnabled(True)
            self.strategy_combo.setEnabled(False)
            self.stock_count_spin.setEnabled(True)
            if hasattr(self, 'indicator_group'):
                self.indicator_group.setEnabled(False)
            if hasattr(self, 'fundamental_group'):
                self.fundamental_group.setEnabled(False)
        else:
            # 禁用自然语言输入框，启用其他配置
            self.nlp_input.setEnabled(False)
            self.strategy_combo.setEnabled(True)
            self.stock_count_spin.setEnabled(True)
            if hasattr(self, 'indicator_group'):
                self.indicator_group.setEnabled(True)
            if hasattr(self, 'fundamental_group'):
                self.fundamental_group.setEnabled(True)
        
    def start_ai_selection(self):
        """开始AI选股"""
        if not self.ai_selection_service:
            QMessageBox.warning(self, "错误", "AI选股服务不可用")
            return
            
        # 判断是否使用自然语言模式
        use_nlp = self.use_nlp_check.isChecked()
        
        if use_nlp:
            # 自然语言模式
            nlp_input = self.nlp_input.toPlainText().strip()
            if not nlp_input:
                QMessageBox.warning(self, "警告", "请输入选股需求")
                return
                
            strategy = self._get_strategy()
            
            # 创建并启动工作线程
            self.worker = AISelectionWorker(
                self.ai_selection_service,
                None,
                strategy,
                use_nlp=True,
                nlp_input=nlp_input
            )
        else:
            # 传统模式
            criteria = self._collect_criteria()
            strategy = self._get_strategy()
            
            if not criteria:
                QMessageBox.warning(self, "错误", "请配置选股参数")
                return
                
            # 创建并启动工作线程
            self.worker = AISelectionWorker(
                self.ai_selection_service,
                criteria,
                strategy,
                use_nlp=False
            )
        
        self.worker.finished.connect(self.on_selection_completed)
        self.worker.progress.connect(self.update_progress)
        self.worker.error.connect(self.on_selection_error)
        self.worker.cancelled.connect(self.on_selection_cancelled)
        
        # 更新UI状态
        self.start_btn.setEnabled(False)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.cancel_selection)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #b71c1c;
            }
        """)
        
        # 添加取消按钮到布局
        button_layout = self.start_btn.parent().layout()
        button_layout.insertWidget(button_layout.indexOf(self.start_btn) + 1, self.cancel_btn)
        
        # 显示进度
        self.show_progress(True)
        
        self.worker.start()
    
    def cancel_selection(self):
        """取消AI选股"""
        if hasattr(self, 'worker') and self.worker:
            self.worker.cancel()
            self.update_status("正在取消...")
    
    def update_progress(self, progress: int, status: str):
        """更新进度"""
        if hasattr(self, 'progress_bar') and self.progress_bar:
            self.progress_bar.setValue(progress)
        
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.setText(f" - {status}")
    
    def on_selection_cancelled(self):
        """选股取消处理"""
        self.update_status("AI选股已取消")
        self.show_progress(False)
        self._restore_ui_state()
    
    def _restore_ui_state(self):
        """恢复UI状态"""
        self.start_btn.setEnabled(True)
        if hasattr(self, 'cancel_btn') and self.cancel_btn:
            self.cancel_btn.deleteLater()
            del self.cancel_btn
    
    def show_progress(self, show: bool):
        """显示/隐藏进度条"""
        if show:
            if hasattr(self, 'progress_container') and self.progress_container:
                self.progress_container.setVisible(True)
            if hasattr(self, 'progress_bar') and self.progress_bar:
                self.progress_bar.setVisible(True)
                self.progress_bar.setValue(0)
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.setVisible(True)
                self.status_label.setText("初始化...")
        else:
            if hasattr(self, 'progress_container') and self.progress_container:
                self.progress_container.setVisible(False)
            if hasattr(self, 'progress_bar') and self.progress_bar:
                self.progress_bar.setVisible(False)
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.setVisible(False)
        
    def _collect_criteria(self):
        """收集选股标准"""
        try:
            if not StockSelectionCriteria:
                return None
                
            criteria = StockSelectionCriteria()
            
            # 基础参数
            criteria.max_stocks = self.stock_count_spin.value()
            
            # 自然语言模式参数
            criteria.use_nlp = self.use_nlp_check.isChecked()
            if criteria.use_nlp:
                criteria.nlp_query = self.nlp_input.toPlainText().strip()
            else:
                criteria.nlp_query = ""
            
            # 风险等级转换
            risk_tolerance_map = {
                "保守": RiskLevel.CONSERVATIVE,
                "稳健": RiskLevel.MODERATE,
                "积极": RiskLevel.MODERATE,
                "激进": RiskLevel.AGGRESSIVE
            }
            criteria.risk_level = risk_tolerance_map.get(
                self.risk_tolerance_combo.currentText(),
                RiskLevel.MODERATE
            )
            criteria.risk_tolerance = self.risk_tolerance_combo.currentText()
            
            # 解释级别
            if hasattr(self, 'explanation_level_combo'):
                explanation_level_map = {
                    "简单解释": "simple",
                    "详细解释": "detailed",
                    "专业解释": "technical"
                }
                criteria.explanation_level = explanation_level_map.get(
                    self.explanation_level_combo.currentText(),
                    "detailed"
                )
            
            # 时间范围
            timeframe_map = {
                "最近1个月": 30,
                "最近3个月": 90, 
                "最近6个月": 180,
                "最近1年": 365
            }
            criteria.time_period = timeframe_map[self.timeframe_combo.currentText()]
            
            # 数据周期（使用统一的 Period 枚举类）
            from core.plugin_types import Period
            criteria.data_period = Period.normalize(self.data_period_combo.currentText())
            
            # 技术指标权重 - 将具体指标映射到评分维度
            criteria.technical_indicators = {}
            
            # 初始化评分维度权重
            technical_weight = 0.0
            momentum_weight = 0.0
            volatility_weight = 0.0
            liquidity_weight = 0.0
            
            # 映射具体指标到评分维度
            indicator_mapping = {
                "MA5": "technical",
                "MA10": "technical",
                "MA20": "technical",
                "MACD": "technical",
                "RSI": "technical",
                "KDJ": "technical",
                "BOLL": "volatility",
                "OBV": "liquidity"
            }
            
            for indicator, spin in self.indicator_weights.items():
                weight = spin.value()
                dimension = indicator_mapping.get(indicator, "technical")
                
                if dimension == "technical":
                    technical_weight += weight
                elif dimension == "momentum":
                    momentum_weight += weight
                elif dimension == "volatility":
                    volatility_weight += weight
                elif dimension == "liquidity":
                    liquidity_weight += weight
            
            # 设置评分维度权重
            criteria.technical_indicators["技术指标"] = technical_weight
            criteria.technical_indicators["动量指标"] = momentum_weight
            criteria.technical_indicators["波动性"] = volatility_weight
            criteria.technical_indicators["流动性"] = liquidity_weight
                
            # 基本面权重 - 将具体指标映射到策略需要的指标
            criteria.fundamental_indicators = {}
            
            # 获取当前选择的策略类型
            strategy_type = self._get_strategy()
            
            # 根据策略类型创建不同的映射
            if strategy_type == SelectionStrategy.VALUE_BASED:
                # 价值策略需要的指标
                fundamental_mapping = {
                    "PE比率": "PE估值",
                    "PB比率": "PB估值",
                    "ROE": None,  # 价值策略不直接使用ROE
                    "营收增长率": None,
                    "净利润增长率": None,
                    "负债率": None
                }
                
                # 初始化价值策略指标权重
                pe_weight = 0.0
                pb_weight = 0.0
                dividend_weight = 0.0  # UI中没有，使用默认值
                industry_pb_weight = 0.0  # UI中没有，使用默认值
                fcf_weight = 0.0  # UI中没有，使用默认值
                
                for indicator, spin in self.fundamental_weights.items():
                    weight = spin.value()
                    mapped_indicator = fundamental_mapping.get(indicator)
                    
                    if mapped_indicator == "PE估值":
                        pe_weight = weight
                    elif mapped_indicator == "PB估值":
                        pb_weight = weight
                
                # 设置价值策略指标权重
                criteria.fundamental_indicators["PE估值"] = pe_weight
                criteria.fundamental_indicators["PB估值"] = pb_weight
                criteria.fundamental_indicators["股息率"] = dividend_weight
                criteria.fundamental_indicators["市净率相对行业"] = industry_pb_weight
                criteria.fundamental_indicators["自由现金流"] = fcf_weight
                
            elif strategy_type == SelectionStrategy.GROWTH_BASED:
                # 成长策略需要的指标
                fundamental_mapping = {
                    "PE比率": None,
                    "PB比率": None,
                    "ROE": "ROE",
                    "营收增长率": "营收增长率",
                    "净利润增长率": "净利润增长率",
                    "负债率": None
                }
                
                # 初始化成长策略指标权重
                revenue_weight = 0.0
                profit_weight = 0.0
                roe_weight = 0.0
                momentum_weight = 0.0  # UI中没有，使用默认值
                industry_growth_weight = 0.0  # UI中没有，使用默认值
                
                for indicator, spin in self.fundamental_weights.items():
                    weight = spin.value()
                    mapped_indicator = fundamental_mapping.get(indicator)
                    
                    if mapped_indicator == "营收增长率":
                        revenue_weight = weight
                    elif mapped_indicator == "净利润增长率":
                        profit_weight = weight
                    elif mapped_indicator == "ROE":
                        roe_weight = weight
                
                # 设置成长策略指标权重
                criteria.fundamental_indicators["营收增长率"] = revenue_weight
                criteria.fundamental_indicators["净利润增长率"] = profit_weight
                criteria.fundamental_indicators["ROE"] = roe_weight
                criteria.fundamental_indicators["价格动量"] = momentum_weight
                criteria.fundamental_indicators["行业成长性"] = industry_growth_weight
                
            elif strategy_type == SelectionStrategy.QUALITY_BASED:
                # 质量策略需要的指标
                fundamental_mapping = {
                    "PE比率": None,
                    "PB比率": None,
                    "ROE": "ROE",
                    "营收增长率": None,
                    "净利润增长率": None,
                    "负债率": "资产负债率"
                }
                
                # 初始化质量策略指标权重
                roe_weight = 0.0
                roa_weight = 0.0  # UI中没有，使用默认值
                debt_ratio_weight = 0.0
                cash_flow_weight = 0.0  # UI中没有，使用默认值
                profit_margin_weight = 0.0  # UI中没有，使用默认值
                dividend_stability_weight = 0.0  # UI中没有，使用默认值
                
                for indicator, spin in self.fundamental_weights.items():
                    weight = spin.value()
                    mapped_indicator = fundamental_mapping.get(indicator)
                    
                    if mapped_indicator == "ROE":
                        roe_weight = weight
                    elif mapped_indicator == "资产负债率":
                        debt_ratio_weight = weight
                
                # 设置质量策略指标权重
                criteria.fundamental_indicators["ROE"] = roe_weight
                criteria.fundamental_indicators["ROA"] = roa_weight
                criteria.fundamental_indicators["资产负债率"] = debt_ratio_weight
                criteria.fundamental_indicators["现金流"] = cash_flow_weight
                criteria.fundamental_indicators["利润质量"] = profit_margin_weight
                criteria.fundamental_indicators["分红稳定性"] = dividend_stability_weight
                
            else:
                # 其他策略（综合评分、技术指标驱动、动量策略等）使用通用映射
                for indicator, spin in self.fundamental_weights.items():
                    criteria.fundamental_indicators[indicator] = spin.value()
                
            return criteria
            
        except Exception as e:
            logger.error(f"收集选股标准失败: {e}")
            return None
            
    def _get_strategy(self):
        """获取选股策略"""
        if not SelectionStrategy:
            return None
            
        strategy_map = {
            "技术指标驱动": SelectionStrategy.TECH_ANALYSIS,
            "基本面驱动": SelectionStrategy.QUALITY_BASED,
            "综合评分": SelectionStrategy.HYBRID,
            "成长性导向": SelectionStrategy.GROWTH_BASED,
            "价值投资": SelectionStrategy.VALUE_BASED,
            "动量策略": SelectionStrategy.MOMENTUM_BASED
        }
        
        return strategy_map.get(self.strategy_combo.currentText(), SelectionStrategy.HYBRID)
        
    def on_selection_completed(self, result):
        """选股完成回调"""
        try:
            self.show_progress(False)
            self._restore_ui_state()
            
            if result.get("success", False):
                data = result.get("data", {})
                
                # 转换数据结构以匹配UI期望的格式
                self.selection_results = self._convert_result_to_ui_format(data)
                
                # 使用工作线程处理数据转换和排序，避免阻塞UI
                self._process_results_in_background()
                
                # 显示错误摘要（如果有）
                error_summary = result.get("error_summary")
                if error_summary and error_summary.get("total_errors", 0) > 0:
                    self._show_error_summary(error_summary)
                
                self.update_status(f"AI选股完成，共找到 {len(self.selection_results)} 只股票")
                
                # 启用导出按钮
                self.export_btn.setEnabled(True)
                
                # 解释数据已在 _convert_result_to_ui_format 中处理，无需重复生成
            else:
                error_msg = result.get("error", "未知错误")
                
                # 显示错误摘要（如果有）
                error_summary = result.get("error_summary")
                if error_summary and error_summary.get("total_errors", 0) > 0:
                    self._show_error_summary(error_summary)
                
                QMessageBox.warning(self, "选股失败", f"错误: {error_msg}")
                self.update_status(f"选股失败: {error_msg}", error=True)
                
        except Exception as e:
            logger.error(f"处理选股结果失败: {e}")
            QMessageBox.critical(self, "错误", f"处理结果时出错: {str(e)}")
    
    def _process_results_in_background(self):
        """在后台线程中处理结果数据"""
        try:
            self.result_update_worker = ResultUpdateWorker(self.selection_results)
            self.result_update_worker.finished.connect(self.on_data_processed)
            self.result_update_worker.error.connect(self.on_data_processing_error)
            self.result_update_worker.start()
        except Exception as e:
            logger.error(f"启动结果处理线程失败: {e}")
            # 回退到主线程处理
            self._update_results_table()
    
    def on_data_processed(self, stock_list):
        """数据处理完成回调 - 在主线程中更新UI"""
        try:
            # 缓存处理后的数据，用于分页
            self._current_stock_list = stock_list
            
            if not stock_list:
                self.result_table.setRowCount(0)
                return
            
            # 只在主线程中执行UI更新
            self._display_page(stock_list)
        except Exception as e:
            logger.error(f"更新结果表格失败: {e}")
    
    def on_data_processing_error(self, error_msg):
        """数据处理错误回调"""
        logger.error(error_msg)
        QMessageBox.warning(self, "数据处理错误", error_msg)
    
    def _convert_result_to_ui_format(self, data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """将后端返回的数据转换为UI期望的格式（优化版 - 直接使用选股流程中的解释数据）
        
        Args:
            data: 后端返回的数据
            
        Returns:
            UI期望的格式：{股票代码: {股票数据}}
        """
        ui_format = {}
        
        selected_stocks = data.get("selected_stocks", [])
        stock_scores = data.get("stock_scores", {})
        detailed_scores = data.get("detailed_scores", {})
        explanations = data.get("explanations", [])
        
        # 创建解释映射并存储到 self.explanation_data
        explanations_map = {}
        self.explanation_data = {}  # 清空并重新初始化
        for exp in explanations:
            stock_code = exp.get("stock_code", "")
            explanations_map[stock_code] = exp
            # 存储到 self.explanation_data 供后续使用
            self.explanation_data[stock_code] = exp
        
        # 获取股票列表以获取股票名称
        stock_name_map = {}
        try:
            container = get_service_container()
            if UnifiedDataManager:
                data_manager = container.resolve(UnifiedDataManager)
                stock_list_df = data_manager.get_stock_list()
                
                # 创建股票代码到名称的映射
                if not stock_list_df.empty and 'code' in stock_list_df.columns and 'name' in stock_list_df.columns:
                    stock_name_map = dict(zip(stock_list_df['code'], stock_list_df['name']))
                    logger.info(f"成功获取股票列表，包含 {len(stock_name_map)} 只股票")
        except Exception as e:
            logger.warning(f"获取股票列表失败: {e}，股票名称将为空")
        
        # 转换为UI格式
        logger.info(f"开始转换选股结果为UI格式，选中的股票数量: {len(selected_stocks)}")
        logger.info(f"评分数据示例（前5个）: {dict(list(stock_scores.items())[:5])}")
        logger.info(f"详细评分数据示例（前3个）: {dict(list(detailed_scores.items())[:3])}")
        
        for stock_code in selected_stocks:
            total_score = stock_scores.get(stock_code, 0)
            
            # 使用详细评分数据（如果可用）
            if stock_code in detailed_scores:
                detail = detailed_scores[stock_code]
                technical_score = detail.get("technical_score", 0)
                momentum_score = detail.get("momentum_score", 0)
                volatility_score = detail.get("volatility_score", 0)
                liquidity_score = detail.get("liquidity_score", 0)
                
                # 计算基本面评分（基于动量评分）
                fundamental_score = momentum_score
                
                # 计算风险评分（基于波动性评分）
                risk_score = 100 - volatility_score
                
                logger.debug(f"股票 {stock_code}: 综合评分={total_score:.2f}, 技术评分={technical_score:.2f}, 基本面评分={fundamental_score:.2f}, 风险评分={risk_score:.2f}")
            else:
                # 回退到基于综合评分的假设
                technical_score = total_score * 0.4
                fundamental_score = total_score * 0.4
                risk_score = 100 - total_score
                
                logger.debug(f"股票 {stock_code}（使用回退评分）: 综合评分={total_score:.2f}, 技术评分={technical_score:.2f}, 基本面评分={fundamental_score:.2f}, 风险评分={risk_score:.2f}")
            
            # 从股票列表中获取股票名称
            stock_name = stock_name_map.get(stock_code, "")
            
            stock_data = {
                "name": stock_name,
                "total_score": total_score,
                "technical_score": technical_score,
                "fundamental_score": fundamental_score,
                "risk_score": risk_score,
                "reason": "",
                "confidence": total_score / 100,
                "industry": "",
                "market_cap": ""
            }
            
            # 从解释中获取推荐理由
            exp = explanations_map.get(stock_code, {})
            if exp:
                stock_data["reason"] = exp.get("selection_reason", "")
                # 如果解释中有股票名称且股票列表中没有，使用解释中的名称
                if not stock_name and exp.get("stock_name"):
                    stock_data["name"] = exp.get("stock_name", "")
            
            ui_format[stock_code] = stock_data
        
        return ui_format
    
    def _show_error_summary(self, error_summary: Dict[str, Any]):
        """显示错误摘要"""
        try:
            # 创建错误摘要对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("错误摘要")
            dialog.setMinimumSize(600, 400)
            
            layout = QVBoxLayout(dialog)
            
            # 总体信息
            summary_group = QGroupBox("总体信息")
            summary_layout = QFormLayout(summary_group)
            
            summary_layout.addRow("总错误数:", QLabel(str(error_summary.get("total_errors", 0))))
            summary_layout.addRow("持续时间(秒):", QLabel(f"{error_summary.get('duration_seconds', 0):.2f}"))
            summary_layout.addRow("错误率(个/秒):", QLabel(f"{error_summary.get('errors_per_second', 0):.4f}"))
            summary_layout.addRow("受影响股票数:", QLabel(str(error_summary.get("affected_stocks_count", 0))))
            
            layout.addWidget(summary_group)
            
            # 按类型分组
            if error_summary.get("errors_by_type"):
                type_group = QGroupBox("按类型分组")
                type_layout = QVBoxLayout(type_group)
                
                type_table = QTableWidget()
                type_table.setColumnCount(2)
                type_table.setHorizontalHeaderLabels(["错误类型", "数量"])
                type_table.horizontalHeader().setStretchLastSection(True)
                
                for error_type, count in error_summary["errors_by_type"].items():
                    row = type_table.rowCount()
                    type_table.insertRow(row)
                    type_table.setItem(row, 0, QTableWidgetItem(error_type))
                    type_table.setItem(row, 1, QTableWidgetItem(str(count)))
                
                type_layout.addWidget(type_table)
                layout.addWidget(type_group)
            
            # 按严重程度分组
            if error_summary.get("errors_by_severity"):
                severity_group = QGroupBox("按严重程度分组")
                severity_layout = QVBoxLayout(severity_group)
                
                severity_table = QTableWidget()
                severity_table.setColumnCount(2)
                severity_table.setHorizontalHeaderLabels(["严重程度", "数量"])
                severity_table.horizontalHeader().setStretchLastSection(True)
                
                for severity, count in error_summary["errors_by_severity"].items():
                    row = severity_table.rowCount()
                    severity_table.insertRow(row)
                    severity_table.setItem(row, 0, QTableWidgetItem(severity))
                    severity_table.setItem(row, 1, QTableWidgetItem(str(count)))
                
                severity_layout.addWidget(severity_table)
                layout.addWidget(severity_group)
            
            # 最新错误
            if error_summary.get("latest_errors"):
                latest_group = QGroupBox("最新错误")
                latest_layout = QVBoxLayout(latest_group)
                
                latest_table = QTableWidget()
                latest_table.setColumnCount(4)
                latest_table.setHorizontalHeaderLabels(["错误ID", "类型", "股票代码", "错误消息"])
                latest_table.horizontalHeader().setStretchLastSection(True)
                
                for error in error_summary["latest_errors"]:
                    row = latest_table.rowCount()
                    latest_table.insertRow(row)
                    latest_table.setItem(row, 0, QTableWidgetItem(error.get("error_id", "")))
                    latest_table.setItem(row, 1, QTableWidgetItem(error.get("error_type", "")))
                    latest_table.setItem(row, 2, QTableWidgetItem(error.get("stock_code", "")))
                    latest_table.setItem(row, 3, QTableWidgetItem(error.get("error_message", "")))
                
                latest_layout.addWidget(latest_table)
                layout.addWidget(latest_group)
            
            # 按钮
            button_layout = QHBoxLayout()
            
            export_btn = QPushButton("导出错误报告")
            export_btn.clicked.connect(lambda: self._export_error_report(error_summary))
            button_layout.addWidget(export_btn)
            
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.accept)
            button_layout.addWidget(close_btn)
            
            button_layout.addStretch()
            layout.addLayout(button_layout)
            
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"显示错误摘要失败: {e}")
    
    def _export_error_report(self, error_summary: Dict[str, Any]):
        """导出错误报告"""
        try:
            from datetime import datetime
            import json
            
            # 选择保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存错误报告",
                f"error_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "JSON Files (*.json)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(error_summary, f, ensure_ascii=False, indent=2)
                
                QMessageBox.information(self, "导出成功", f"错误报告已保存到:\n{file_path}")
                
        except Exception as e:
            logger.error(f"导出错误报告失败: {e}")
            QMessageBox.critical(self, "导出失败", f"导出错误报告时出错: {str(e)}")
            
    def on_selection_error(self, error_msg):
        """选股错误回调"""
        self.show_progress(False)
        self.start_btn.setEnabled(True)
        logger.error(f"AI选股错误: {error_msg}")
        QMessageBox.critical(self, "AI选股错误", error_msg)
        self.update_status(f"选股失败: {error_msg}", error=True)
        
    def _update_results_table(self):
        """更新结果表格"""
        try:
            if not self.selection_results:
                self.result_table.setRowCount(0)
                return
                
            # 转换为列表格式
            stock_list = []
            for stock_code, data in self.selection_results.items():
                stock_list.append([
                    stock_code,
                    data.get("name", ""),
                    f"{data.get('total_score', 0):.2f}",
                    f"{data.get('technical_score', 0):.2f}",
                    f"{data.get('fundamental_score', 0):.2f}",
                    f"{data.get('risk_score', 0):.2f}",
                    data.get("reason", ""),
                    f"{data.get('confidence', 0):.1%}"
                ])
                
            # 按评分排序
            stock_list.sort(key=lambda x: float(x[2]), reverse=True)
            
            # 分页显示
            self._display_page(stock_list)
            
        except Exception as e:
            logger.error(f"更新结果表格失败: {e}")
            
    def _display_page(self, stock_list):
        """分页显示"""
        total_stocks = len(stock_list)
        self.total_pages = max(1, (total_stocks + self.page_size - 1) // self.page_size)
        
        # 确保当前页在有效范围内
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages
            
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = min(start_idx + self.page_size, total_stocks)
        page_data = stock_list[start_idx:end_idx]
        
        # 更新表格
        self.result_table.setRowCount(len(page_data))
        for row, data in enumerate(page_data):
            for col, value in enumerate(data):
                item = QTableWidgetItem(str(value))
                if col in [2, 3, 4, 5, 7]:  # 数值列
                    item.setTextAlignment(Qt.AlignCenter)
                self.result_table.setItem(row, col, item)
                
        # 更新分页控件
        self.page_label.setText(f"第 {self.current_page} 页 / 共 {self.total_pages} 页")
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < self.total_pages)
        
    def prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            # 直接显示当前页，不需要重新处理数据
            if hasattr(self, '_current_stock_list') and self._current_stock_list:
                self._display_page(self._current_stock_list)
            else:
                # 如果没有缓存的数据，回退到完整处理
                self._update_results_table()
            
    def next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            # 直接显示当前页，不需要重新处理数据
            if hasattr(self, '_current_stock_list') and self._current_stock_list:
                self._display_page(self._current_stock_list)
            else:
                # 如果没有缓存的数据，回退到完整处理
                self._update_results_table()
            
    def _generate_explanations(self):
        """生成可解释性"""
        try:
            if not self.explainability_service or not self.selection_results:
                return
                
            # 为前几只股票生成解释
            top_stocks = list(self.selection_results.keys())[:5]
            
            for stock_code in top_stocks:
                if hasattr(self.explainability_service, 'generate_explanation'):
                    stock_data = self.selection_results[stock_code]
                    selection_data = {"score": stock_data.get("total_score", 0)}
                    
                    explanation = self.explainability_service.generate_explanation(
                        stock_code=stock_code,
                        stock_data=stock_data,
                        selection_data=selection_data
                    )
                    
                    self.explanation_data[stock_code] = explanation
                    
        except Exception as e:
            logger.error(f"生成可解释性失败: {e}")
            
    def on_selection_changed(self):
        """选中股票变化"""
        current_row = self.result_table.currentRow()
        if current_row < 0:
            return
            
        # 获取股票代码（从第一列）
        stock_code_item = self.result_table.item(current_row, 0)
        if not stock_code_item:
            return
            
        stock_code = stock_code_item.text()
        
        # 显示该股票的解释
        self._display_explanation(stock_code)
        
    def _display_explanation(self, stock_code):
        """显示股票解释"""
        try:
            explanation = self.explanation_data.get(stock_code)
            if not explanation:
                self.explain_text.setText("该股票暂无详细解释")
                self.factor_chart.setText("选择股票查看因子贡献分析")
                return
                
            # 显示解释文本（适配后端 SelectionExplanation 格式）
            if isinstance(explanation, dict):
                # 字典格式：检查 selection_reason 或 summary_text
                explanation_text = explanation.get("selection_reason") or explanation.get("summary_text", "")
                if explanation_text:
                    self.explain_text.setText(explanation_text)
                else:
                    self.explain_text.setText("暂无解释文本")
            else:
                # 对象格式：检查 selection_reason 或 summary_text 属性
                if hasattr(explanation, 'selection_reason'):
                    self.explain_text.setText(explanation.selection_reason)
                elif hasattr(explanation, 'summary_text'):
                    self.explain_text.setText(explanation.summary_text)
                else:
                    self.explain_text.setText("暂无解释文本")
                
            # 显示因子贡献图表
            self._display_factor_contribution_chart(stock_code, explanation)
            
        except Exception as e:
            logger.error(f"显示解释失败: {e}")
            self.explain_text.setText(f"解释显示失败: {str(e)}")
            
    def export_results(self):
        """导出结果"""
        try:
            if not self.selection_results:
                QMessageBox.information(self, "提示", "没有可导出的结果")
                return
                
            # 选择导出格式
            format_choice, ok = QInputDialog.getItem(
                self, "选择导出格式", "请选择导出格式:", 
                ["CSV文件", "Excel文件", "JSON文件"], 0, False
            )
            
            if not ok:
                return
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if format_choice == "CSV文件":
                filename, _ = QFileDialog.getSaveFileName(
                    self, "保存CSV文件", 
                    f"ai_selection_results_{timestamp}.csv",
                    "CSV Files (*.csv)"
                )
                if filename:
                    self._export_to_csv(filename)
                    
            elif format_choice == "Excel文件":
                filename, _ = QFileDialog.getSaveFileName(
                    self, "保存Excel文件",
                    f"ai_selection_results_{timestamp}.xlsx", 
                    "Excel Files (*.xlsx)"
                )
                if filename:
                    self._export_to_excel(filename)
                    
            elif format_choice == "JSON文件":
                filename, _ = QFileDialog.getSaveFileName(
                    self, "保存JSON文件",
                    f"ai_selection_results_{timestamp}.json",
                    "JSON Files (*.json)"
                )
                if filename:
                    self._export_to_json(filename)
                    
        except Exception as e:
            logger.error(f"导出结果失败: {e}")
            QMessageBox.critical(self, "导出失败", f"导出失败: {str(e)}")
            
    def _export_to_csv(self, filename):
        """导出到CSV"""
        import csv
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 写入表头
            writer.writerow([
                "股票代码", "股票名称", "综合评分", "技术评分", "基本面评分",
                "风险评分", "推荐理由", "置信度", "行业", "市值"
            ])
            
            # 写入数据
            for stock_code, data in self.selection_results.items():
                writer.writerow([
                    stock_code,
                    data.get("name", ""),
                    data.get("total_score", 0),
                    data.get("technical_score", 0),
                    data.get("fundamental_score", 0),
                    data.get("risk_score", 0),
                    data.get("reason", ""),
                    data.get("confidence", 0),
                    data.get("industry", ""),
                    data.get("market_cap", "")
                ])
                
        QMessageBox.information(self, "导出成功", f"结果已导出到: {filename}")
        
    def _export_to_excel(self, filename):
        """导出到Excel"""
        try:
            import openpyxl
            
            # 创建工作簿
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "AI选股结果"
            
            # 写入表头
            headers = [
                "股票代码", "股票名称", "综合评分", "技术评分", "基本面评分",
                "风险评分", "推荐理由", "置信度", "行业", "市值"
            ]
            ws.append(headers)
            
            # 写入数据
            for stock_code, data in self.selection_results.items():
                ws.append([
                    stock_code,
                    data.get("name", ""),
                    data.get("total_score", 0),
                    data.get("technical_score", 0),
                    data.get("fundamental_score", 0),
                    data.get("risk_score", 0),
                    data.get("reason", ""),
                    data.get("confidence", 0),
                    data.get("industry", ""),
                    data.get("market_cap", "")
                ])
                
            # 保存文件
            wb.save(filename)
            QMessageBox.information(self, "导出成功", f"结果已导出到: {filename}")
            
        except ImportError:
            QMessageBox.warning(self, "缺少依赖", "请安装openpyxl库来导出Excel文件")
            
    def _export_to_json(self, filename):
        """导出到JSON"""
        # 准备导出数据
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "total_count": len(self.selection_results),
            "results": self.selection_results
        }
        
        # 添加配置信息
        export_data["config"] = {
            "strategy": self.strategy_combo.currentText(),
            "stock_count": self.stock_count_spin.value(),
            "risk_tolerance": self.risk_tolerance_combo.currentText(),
            "timeframe": self.timeframe_combo.currentText(),
            "technical_weights": {k: v.value() for k, v in self.indicator_weights.items()},
            "fundamental_weights": {k: v.value() for k, v in self.fundamental_weights.items()}
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
            
        QMessageBox.information(self, "导出成功", f"结果已导出到: {filename}")
        
    def clear_results(self):
        """清空结果"""
        reply = QMessageBox.question(
            self, "确认清空", "确定要清空所有结果吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.selection_results.clear()
            self.explanation_data.clear()
            self.result_table.setRowCount(0)
            self.explain_text.clear()
            self.factor_chart.setText("选择股票查看因子贡献分析")
            self.export_btn.setEnabled(False)
            self.current_page = 1
            self.page_label.setText("第 1 页 / 共 1 页")
            self.update_status("结果已清空")
    
    def open_llm_config(self):
        """打开LLM配置对话框"""
        try:
            from gui.dialogs.llm_config_dialog import LLMConfigDialog
            from core.services.llm_config_service import LLMConfigService
            
            # 获取LLM配置服务
            service_container = get_service_container()
            llm_config_service = service_container.resolve(LLMConfigService)
            
            # 创建并显示配置对话框
            dialog = LLMConfigDialog(self, llm_config_service)
            dialog.exec_()
            
            # 如果配置更新，重新初始化AI选股服务
            if hasattr(dialog, 'config_updated'):
                dialog.config_updated.connect(self.on_llm_config_updated)
                
        except ImportError as e:
            logger.error(f"LLM配置对话框导入失败: {e}")
            QMessageBox.warning(self, "错误", "LLM配置功能不可用")
        except Exception as e:
            logger.error(f"打开LLM配置失败: {e}")
            QMessageBox.critical(self, "错误", f"打开LLM配置失败: {str(e)}")
    
    def on_llm_config_updated(self):
        """LLM配置更新回调"""
        logger.info("LLM配置已更新，重新初始化AI选股服务")
        self.update_status("LLM配置已更新")
        
        # 重新初始化服务
        self._init_services()
            
    def _display_factor_contribution_chart(self, stock_code, explanation):
        """显示因子贡献图表"""
        try:
            # 清除之前的内容
            self.factor_chart.figure.clear()
            
            # 创建子图
            ax = self.factor_chart.figure.add_subplot(111)
            
            # 提取因子贡献数据
            factor_data = self._extract_factor_contribution_data(explanation)
            
            if not factor_data:
                # 如果没有因子贡献数据，显示占位符
                ax.text(0.5, 0.5, f'{stock_code}\n因子贡献分析\n(数据不足)', 
                       horizontalalignment='center', verticalalignment='center',
                       transform=ax.transAxes, fontsize=12, 
                       bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.5))
                ax.set_xlim(0, 1)
                ax.set_ylim(0, 1)
                ax.axis('off')
            else:
                # 显示因子贡献图表
                categories = list(factor_data.keys())
                values = list(factor_data.values())
                colors = plt.cm.Set3(np.linspace(0, 1, len(categories)))
                
                # Min-Max 归一化到 [0, 100] 范围，使所有因子都能清晰显示
                min_val = min(values) if values else 0
                max_val = max(values) if values else 1
                
                if max_val > min_val:
                    normalized_values = [(v - min_val) / (max_val - min_val) * 100 for v in values]
                else:
                    normalized_values = [50.0] * len(values)
                
                # 创建柱状图（使用归一化后的值）
                bars = ax.barh(categories, normalized_values, color=colors)
                
                # 设置标签和标题
                ax.set_xlabel('贡献度（归一化）', fontsize=10)
                ax.set_title(f'{stock_code} 因子贡献分析', fontsize=12, fontweight='bold')
                ax.set_xlim(0, 110)
                
                # 添加数值标签（显示原始值）
                for i, (bar, value, original_value) in enumerate(zip(bars, normalized_values, values)):
                    label_text = f'{original_value:.2f}' if original_value < 1000 else f'{original_value:.0f}'
                    ax.text(value + 1, bar.get_y() + bar.get_height()/2,
                           label_text, va='center', fontsize=9)
                
                # 美化图表
                ax.grid(axis='x', alpha=0.3, linestyle='--', linewidth=0.5, color='gray', zorder=0, which='major')
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
            
            # 刷新画布
            self.factor_chart.draw()
            
        except Exception as e:
            logger.error(f"显示因子贡献图表失败: {e}")
            # 显示错误信息
            ax = self.factor_chart.figure.add_subplot(111)
            ax.text(0.5, 0.5, f'图表显示失败\n{str(e)}', 
                   horizontalalignment='center', verticalalignment='center',
                   transform=ax.transAxes, fontsize=10, color='red',
                   bbox=dict(boxstyle='round', facecolor='mistyrose', alpha=0.8))
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            self.factor_chart.draw()
    
    def _extract_factor_contribution_data(self, explanation):
        """提取因子贡献数据（适配后端 SelectionExplanation 格式）"""
        try:
            factor_data = {}
            
            # 添加调试日志
            logger.info(f"提取因子贡献数据，解释类型: {type(explanation)}")
            
            # 适配后端 SelectionExplanation 格式
            if isinstance(explanation, dict):
                # 字典格式：从所有信号中提取
                signals_map = {
                    '技术': explanation.get("technical_signals", {}),
                    '基本面': explanation.get("fundamental_signals", {}),
                    '市场': explanation.get("market_signals", {}),
                    '风险': explanation.get("risk_signals", {}),
                    '情绪': explanation.get("sentiment_signals", {})
                }
                
                logger.info(f"字典格式，信号映射: {signals_map}")
                
                # 提取所有因子的贡献度
                for category, signals in signals_map.items():
                    for factor_name, signal_data in signals.items():
                        if isinstance(signal_data, dict) and "contribution" in signal_data:
                            factor_data[f"{category}-{factor_name}"] = float(signal_data["contribution"])
                        elif isinstance(signal_data, (int, float)):
                            factor_data[f"{category}-{factor_name}"] = float(signal_data)
                
                # 如果有 key_indicators，也可以提取（作为备用）
                key_indicators = explanation.get("key_indicators", {})
                for factor_name, value in key_indicators.items():
                    if not any(f"-{factor_name}" in key for key in factor_data.keys()):
                        factor_data[factor_name] = float(value) if isinstance(value, (int, float)) else 0.0
            
            else:
                # 对象格式：从所有信号属性中提取
                signals_map = {
                    '技术': getattr(explanation, 'technical_signals', {}),
                    '基本面': getattr(explanation, 'fundamental_signals', {}),
                    '市场': getattr(explanation, 'market_signals', {}),
                    '风险': getattr(explanation, 'risk_signals', {}),
                    '情绪': getattr(explanation, 'sentiment_signals', {})
                }
                
                logger.info(f"对象格式，信号映射: {signals_map}")
                
                # 提取所有因子的贡献度
                for category, signals in signals_map.items():
                    for factor_name, signal_data in signals.items():
                        if isinstance(signal_data, dict) and "contribution" in signal_data:
                            factor_data[f"{category}-{factor_name}"] = float(signal_data["contribution"])
                        elif isinstance(signal_data, (int, float)):
                            factor_data[f"{category}-{factor_name}"] = float(signal_data)
                
                # 如果有 key_indicators 属性，也可以提取（作为备用）
                key_indicators = getattr(explanation, 'key_indicators', {})
                for factor_name, value in key_indicators.items():
                    if not any(f"-{factor_name}" in key for key in factor_data.keys()):
                        factor_data[factor_name] = float(value) if isinstance(value, (int, float)) else 0.0
            
            logger.info(f"提取的因子贡献数据: {factor_data}")
            
            return factor_data
            
        except Exception as e:
            logger.error(f"提取因子贡献数据失败: {e}")
            return {}
    
    def open_history_panel(self):
        """打开历史记录面板"""
        try:
            from components.selection_history_panel import SelectionHistoryPanel
            
            # 创建历史记录对话框
            history_dialog = QDialog(self)
            history_dialog.setWindowTitle("选股历史记录")
            history_dialog.setMinimumSize(1200, 800)
            
            # 创建布局
            dialog_layout = QVBoxLayout(history_dialog)
            
            # 创建历史记录面板
            history_panel = SelectionHistoryPanel(history_dialog)
            
            # 连接恢复策略信号
            history_panel.restore_strategy.connect(self._on_strategy_restored)
            
            # 添加到对话框
            dialog_layout.addWidget(history_panel)
            
            # 显示对话框
            history_dialog.exec_()
            
        except Exception as e:
            logger.error(f"打开历史记录面板失败: {e}")
            QMessageBox.critical(self, "错误", f"打开历史记录面板失败: {e}")
    
    def _on_strategy_restored(self, result_id: str, criteria: dict):
        """处理策略恢复事件
        
        Args:
            result_id: 结果ID
            criteria: 策略配置
        """
        try:
            # 关闭自然语言模式
            if self.use_nlp_check.isChecked():
                self.use_nlp_check.setChecked(False)
            
            # 根据criteria更新UI配置
            if criteria:
                # 更新选股数量
                max_stocks = criteria.get('max_stocks', 50)
                self.stock_count_spin.setValue(max_stocks)
                
                # 更新风险偏好
                risk_level = criteria.get('risk_level', 'moderate')
                risk_mapping = {
                    'conservative': '保守',
                    'moderate': '稳健',
                    'aggressive': '积极',
                    'high_risk': '激进'
                }
                risk_text = risk_mapping.get(risk_level, '稳健')
                risk_index = self.risk_tolerance_combo.findText(risk_text)
                if risk_index >= 0:
                    self.risk_tolerance_combo.setCurrentIndex(risk_index)
                
                # 更新策略类型
                strategy_type = criteria.get('strategy_type', 'quantitative')
                strategy_mapping = {
                    'technical': '技术指标驱动',
                    'fundamental': '基本面驱动',
                    'comprehensive': '综合评分',
                    'growth': '成长性导向',
                    'value': '价值投资',
                    'momentum': '动量策略'
                }
                strategy_text = strategy_mapping.get(strategy_type, '综合评分')
                strategy_index = self.strategy_combo.findText(strategy_text)
                if strategy_index >= 0:
                    self.strategy_combo.setCurrentIndex(strategy_index)
                
                # 更新市值范围（如果UI中有相关控件）
                market_cap_min = criteria.get('market_cap_min')
                market_cap_max = criteria.get('market_cap_max')
                
                # 更新技术指标权重（如果有）
                if 'indicator_weights' in criteria:
                    indicator_weights = criteria['indicator_weights']
                    for indicator, weight_spin in self.indicator_weights.items():
                        if indicator in indicator_weights:
                            weight_spin.setValue(indicator_weights[indicator])
                
                # 更新基本面指标权重（如果有）
                if 'fundamental_weights' in criteria:
                    fundamental_weights = criteria['fundamental_weights']
                    for fundamental, weight_spin in self.fundamental_weights.items():
                        if fundamental in fundamental_weights:
                            weight_spin.setValue(fundamental_weights[fundamental])
                
                # 显示成功消息
                QMessageBox.information(
                    self,
                    "策略恢复成功",
                    f"已恢复策略配置（结果ID: {result_id[:8]}...）\n\n"
                    f"策略类型: {strategy_text}\n"
                    f"风险等级: {risk_text}\n"
                    f"股票数量: {max_stocks}"
                )
                
                logger.info(f"成功恢复策略配置: {result_id[:8]}...")
            
        except Exception as e:
            logger.error(f"恢复策略配置失败: {e}")
            QMessageBox.critical(self, "错误", f"恢复策略配置失败: {e}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止工作线程
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
            
        event.accept()


def create_ai_stock_selection_widget(parent=None):
    """创建AI选股组件"""
    return AIStockSelectionPanel(parent)


if __name__ == "__main__":
    # 测试代码
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    widget = AIStockSelectionPanel()
    widget.show()
    sys.exit(app.exec_())