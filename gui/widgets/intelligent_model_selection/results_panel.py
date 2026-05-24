#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预测结果展示界面组件

提供预测结果的详细展示和分析功能，包括：
- 预测结果概览
- 详细结果展示
- 模型贡献度分析
- 准确性跟踪
"""

from loguru import logger
import json
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import deque

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QPushButton, QGroupBox, QScrollArea,
    QProgressBar, QTextEdit, QSplitter,
    QFrame, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy, QComboBox, QSpinBox,
    QCheckBox, QSlider, QPlainTextEdit, QListWidget,
    QListWidgetItem, QTreeWidget, QTreeWidgetItem
)
from PyQt5.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, QSize, 
    QPropertyAnimation, QEasingCurve, QPointF
)
from PyQt5.QtGui import (
    QFont, QPalette, QBrush, QColor, QPainter, 
    QPainterPath, QPen, QPixmap, QLinearGradient,
    QTextCharFormat, QTextCursor
)


class PredictionResultsPanel(QWidget):
    """预测结果展示界面"""
    
    # 信号定义
    result_details_requested = pyqtSignal(dict)  # 结果详情请求信号
    export_requested = pyqtSignal(dict)  # 导出请求信号
    analysis_requested = pyqtSignal(dict)  # 分析请求信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_result = None
        self.historical_results = deque(maxlen=100)
        self.result_id_counter = 0
        self.update_timer = QTimer()
        self.current_time = datetime.now()
        
        # 准确率跟踪
        self.accuracy_tracking = {
            'total_predictions': 0,
            'correct_predictions': 0,
            'accuracy_history': deque(maxlen=50),
            'accuracy_by_model': {}
        }
        
        self.init_ui()
        self.setup_connections()
        self.start_monitoring()
    
    def init_ui(self):
        """初始化用户界面"""
        self.setMinimumSize(800, 600)
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        
        # 1. 顶部控制栏
        control_header = self._create_control_header()
        main_layout.addWidget(control_header)
        
        # 2. 主要内容区域
        content_area = self._create_content_area()
        main_layout.addWidget(content_area, 1)
        
        # 3. 底部状态栏
        status_footer = self._create_status_footer()
        main_layout.addWidget(status_footer)
        
        # 应用统一样式
        self._apply_unified_styles()
    
    def _create_control_header(self) -> QWidget:
        """创建控制头部"""
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 预测类型选择
        prediction_layout = QHBoxLayout()
        prediction_layout.addWidget(QLabel("预测类型:"))
        
        self.prediction_type_selector = QComboBox()
        self.prediction_type_selector.addItems(["价格预测", "趋势预测", "波动率预测", "成交量预测"])
        self.prediction_type_selector.setCurrentText("价格预测")
        prediction_layout.addWidget(self.prediction_type_selector)
        
        layout.addLayout(prediction_layout)
        
        # 时间范围选择
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("时间范围:"))
        
        self.time_range_selector = QComboBox()
        self.time_range_selector.addItems(["最近1小时", "最近6小时", "最近24小时", "最近7天"])
        self.time_range_selector.setCurrentText("最近6小时")
        time_layout.addWidget(self.time_range_selector)
        
        layout.addLayout(time_layout)
        
        # 模型筛选
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("模型筛选:"))
        
        self.model_filter_selector = QComboBox()
        self.model_filter_selector.addItems(["全部模型", "LSTM预测模型", "ARIMA模型", "XGBoost模型", "随机森林模型"])
        self.model_filter_selector.setCurrentText("全部模型")
        model_layout.addWidget(self.model_filter_selector)
        
        layout.addLayout(model_layout)
        
        layout.addStretch()
        
        # 控制按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #007bff;
                border-radius: 3px;
                background-color: #007bff;
                color: white;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        layout.addWidget(self.refresh_btn)
        
        self.export_btn = QPushButton("导出")
        self.export_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #28a745;
                border-radius: 3px;
                background-color: #28a745;
                color: white;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        layout.addWidget(self.export_btn)
        
        self.analyze_btn = QPushButton("🔍 分析")
        self.analyze_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #17a2b8;
                border-radius: 3px;
                background-color: #17a2b8;
                color: white;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #117a8b;
            }
        """)
        layout.addWidget(self.analyze_btn)
        
        return header
    
    def _create_content_area(self) -> QWidget:
        """创建内容区域"""
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 1. 结果概览选项卡
        overview_tab = self._create_overview_tab()
        self.tab_widget.addTab(overview_tab, "📋 结果概览")
        
        # 2. 详细分析选项卡
        detail_tab = self._create_detail_tab()
        self.tab_widget.addTab(detail_tab, "🔍 详细分析")
        
        # 3. 模型贡献度选项卡
        contribution_tab = self._create_contribution_tab()
        self.tab_widget.addTab(contribution_tab, "模型贡献")
        
        # 4. 准确性跟踪选项卡
        accuracy_tab = self._create_accuracy_tab()
        self.tab_widget.addTab(accuracy_tab, "📈 准确性跟踪")
        
        return content_widget
    
    def _create_overview_tab(self) -> QWidget:
        """创建结果概览选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 左侧：预测结果概览
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # 当前预测结果
        current_group = QGroupBox("当前预测结果")
        current_layout = QVBoxLayout(current_group)
        
        # 预测概览信息
        self.prediction_overview = self._create_prediction_overview()
        current_layout.addWidget(self.prediction_overview)
        
        left_layout.addWidget(current_group)
        
        # 历史预测列表
        history_group = QGroupBox("📜 历史预测记录")
        history_layout = QVBoxLayout(history_group)
        
        # 历史记录列表
        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(200)
        self.history_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #bbdefb;
            }
        """)
        history_layout.addWidget(self.history_list)
        
        left_layout.addWidget(history_group)
        
        # 右侧：关键指标
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 关键指标卡片
        metrics_group = QGroupBox("关键指标")
        metrics_layout = QGridLayout(metrics_group)
        
        # 创建指标卡片
        self.overview_metrics = {}
        key_metrics = [
            ("预测准确性", "accuracy", "%", "0.0%"),
            ("平均误差", "error", "%", "0.0%"),
            ("预测时间", "time", "ms", "0"),
            ("模型数量", "models", "个", "0"),
            ("置信度", "confidence", "%", "0.0%"),
            ("风险评分", "risk", "分", "0")
        ]
        
        for i, (name, key, unit, default_value) in enumerate(key_metrics):
            card = self._create_overview_metric_card(name, key, unit, default_value)
            row = i // 2
            col = i % 2
            metrics_layout.addWidget(card, row, col)
            self.overview_metrics[key] = card
        
        right_layout.addWidget(metrics_group)
        
        # 预测趋势图
        trend_group = QGroupBox("📈 预测趋势")
        trend_layout = QVBoxLayout(trend_group)
        
        self.prediction_trend_frame = QFrame()
        self.prediction_trend_frame.setMinimumHeight(150)
        self.prediction_trend_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #fafafa;
            }
        """)
        trend_layout.addWidget(self.prediction_trend_frame)
        
        right_layout.addWidget(trend_group)
        
        # 使用分割器布局
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([500, 300])
        
        layout.addWidget(main_splitter)
        
        return tab
    
    def _create_prediction_overview(self) -> QWidget:
        """创建预测概览信息"""
        overview_widget = QWidget()
        layout = QGridLayout(overview_widget)
        
        # 预测基本信息
        self.prediction_id_label = QLabel("ID: 暂无")
        self.prediction_time_label = QLabel("时间: 暂无")
        self.prediction_type_label = QLabel("类型: 暂无")
        
        layout.addWidget(QLabel("预测ID:"), 0, 0)
        layout.addWidget(self.prediction_id_label, 0, 1)
        layout.addWidget(QLabel("预测时间:"), 1, 0)
        layout.addWidget(self.prediction_time_label, 1, 1)
        layout.addWidget(QLabel("预测类型:"), 2, 0)
        layout.addWidget(self.prediction_type_label, 2, 1)
        
        # 预测数值
        self.predicted_value_label = QLabel("预测值: 0.00")
        self.actual_value_label = QLabel("实际值: 暂无")
        self.confidence_label = QLabel("置信度: 0.0%")
        
        layout.addWidget(QLabel("预测数值:"), 0, 2)
        layout.addWidget(self.predicted_value_label, 0, 3)
        layout.addWidget(QLabel("实际数值:"), 1, 2)
        layout.addWidget(self.actual_value_label, 1, 3)
        layout.addWidget(QLabel("置信度:"), 2, 2)
        layout.addWidget(self.confidence_label, 2, 3)
        
        # 使用的模型
        self.models_used_label = QLabel("使用模型: 暂无")
        layout.addWidget(QLabel("参与模型:"), 3, 0, 1, 1)
        layout.addWidget(self.models_used_label, 3, 1, 1, 3)
        
        return overview_widget
    
    def _create_overview_metric_card(self, name: str, key: str, unit: str, default_value: str) -> QWidget:
        """创建概览指标卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background-color: white;
                padding: 8px;
            }
        """)
        
        layout = QVBoxLayout(card)
        
        # 指标名称
        name_label = QLabel(name)
        name_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #666;
                font-weight: normal;
            }
        """)
        layout.addWidget(name_label)
        
        # 指标值
        value_layout = QHBoxLayout()
        self.metric_value_label = QLabel(default_value)
        self.metric_value_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #333;
            }
        """)
        value_layout.addWidget(self.metric_value_label)
        
        unit_label = QLabel(unit)
        unit_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #999;
            }
        """)
        value_layout.addWidget(unit_label)
        value_layout.addStretch()
        
        layout.addLayout(value_layout)
        
        # 存储引用
        card.metric_value_label = self.metric_value_label
        
        return card
    
    def _create_detail_tab(self) -> QWidget:
        """创建详细分析选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 详细结果表格
        detail_group = QGroupBox("📋 详细预测结果")
        detail_layout = QVBoxLayout(detail_group)
        
        # 表格控制栏
        table_control_layout = QHBoxLayout()
        table_control_layout.addWidget(QLabel("显示列:"))
        
        self.column_selector = QComboBox()
        self.column_selector.addItems(["全部", "基础信息", "预测数据", "模型信息"])
        self.column_selector.setCurrentText("全部")
        table_control_layout.addWidget(self.column_selector)
        
        table_control_layout.addStretch()
        detail_layout.addLayout(table_control_layout)
        
        # 详细结果表格
        self.detail_table = QTableWidget(0, 8)
        self.detail_table.setHorizontalHeaderLabels([
            "预测ID", "时间", "类型", "预测值", "实际值", 
            "误差", "准确率", "使用模型"
        ])
        self.detail_table.horizontalHeader().setStretchLastSection(True)
        
        # 设置表格样式
        self.detail_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                gridline-color: #e0e0e0;
                selection-background-color: #bbdefb;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
        """)
        
        detail_layout.addWidget(self.detail_table)
        layout.addWidget(detail_group)
        
        # 底部详细分析
        bottom_splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：预测详情文本
        details_panel = QWidget()
        details_layout = QVBoxLayout(details_panel)
        
        details_text_group = QGroupBox("📝 预测详情")
        details_text_layout = QVBoxLayout(details_text_group)
        
        self.prediction_details_text = QPlainTextEdit()
        self.prediction_details_text.setMaximumHeight(150)
        self.prediction_details_text.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f8f9fa;
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }
        """)
        self.prediction_details_text.setReadOnly(True)
        details_text_layout.addWidget(self.prediction_details_text)
        
        details_layout.addWidget(details_text_group)
        
        # 右侧：分析图表
        analysis_panel = QWidget()
        analysis_layout = QVBoxLayout(analysis_panel)
        
        analysis_chart_group = QGroupBox("分析图表")
        analysis_chart_layout = QVBoxLayout(analysis_chart_group)
        
        self.analysis_chart_frame = QFrame()
        self.analysis_chart_frame.setMinimumHeight(150)
        self.analysis_chart_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #fafafa;
            }
        """)
        analysis_chart_layout.addWidget(self.analysis_chart_frame)
        
        analysis_layout.addWidget(analysis_chart_group)
        
        bottom_splitter.addWidget(details_panel)
        bottom_splitter.addWidget(analysis_panel)
        bottom_splitter.setSizes([400, 400])
        
        layout.addWidget(bottom_splitter)
        
        return tab
    
    def _create_contribution_tab(self) -> QWidget:
        """创建模型贡献度选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 模型贡献度概览
        overview_group = QGroupBox("模型贡献度概览")
        overview_layout = QHBoxLayout(overview_group)
        
        # 贡献度环形图
        self.contribution_chart_frame = QFrame()
        self.contribution_chart_frame.setMinimumSize(200, 200)
        self.contribution_chart_frame.setStyleSheet("""
            QFrame {
                border: 2px solid #ddd;
                border-radius: 8px;
                background-color: #fafafa;
            }
        """)
        overview_layout.addWidget(self.contribution_chart_frame)
        
        # 贡献度详情
        contribution_details_layout = QVBoxLayout()
        
        self.contribution_details = QTreeWidget()
        self.contribution_details.setHeaderLabels(["模型", "贡献度", "权重", "状态"])
        self.contribution_details.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QTreeWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QTreeWidget::item:selected {
                background-color: #bbdefb;
            }
        """)
        contribution_details_layout.addWidget(self.contribution_details)
        
        overview_layout.addLayout(contribution_details_layout)
        layout.addWidget(overview_group)
        
        # 权重调整控制
        weight_control_group = QGroupBox("⚙️ 权重调整")
        weight_control_layout = QVBoxLayout(weight_control_group)
        
        # 权重调整滑块
        self.weight_sliders = {}
        models = ["LSTM预测模型", "ARIMA模型", "XGBoost模型", "随机森林模型"]
        
        for model in models:
            slider_layout = QHBoxLayout()
            slider_layout.addWidget(QLabel(f"{model}:"))
            
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(25)  # 默认权重25%
            slider.setMaximumWidth(200)
            slider_layout.addWidget(slider)
            
            value_label = QLabel("25%")
            value_label.setMinimumWidth(40)
            slider_layout.addWidget(value_label)
            
            weight_control_layout.addLayout(slider_layout)
            self.weight_sliders[model] = (slider, value_label)
        
        # 自动调整按钮
        auto_adjust_layout = QHBoxLayout()
        auto_adjust_layout.addStretch()
        
        self.auto_adjust_btn = QPushButton("🤖 自动优化权重")
        self.auto_adjust_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #28a745;
                border-radius: 4px;
                background-color: #28a745;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        auto_adjust_layout.addWidget(self.auto_adjust_btn)
        
        weight_control_layout.addLayout(auto_adjust_layout)
        layout.addWidget(weight_control_group)
        
        # 效果对比分析
        comparison_group = QGroupBox("⚖️ 效果对比分析")
        comparison_layout = QVBoxLayout(comparison_group)
        
        self.comparison_table = QTableWidget(4, 4)
        self.comparison_table.setHorizontalHeaderLabels(["模型", "调整前准确率", "调整后准确率", "提升"])
        self.comparison_table.horizontalHeader().setStretchLastSection(True)
        
        # 设置表格样式
        self.comparison_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                gridline-color: #e0e0e0;
                selection-background-color: #bbdefb;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
        """)
        
        comparison_layout.addWidget(self.comparison_table)
        layout.addWidget(comparison_group)
        
        return tab
    
    def _create_accuracy_tab(self) -> QWidget:
        """创建准确性跟踪选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 总体准确性概览
        overview_group = QGroupBox("总体准确性概览")
        overview_layout = QGridLayout(overview_group)
        
        # 总体统计
        self.total_predictions_label = QLabel("总预测数: 0")
        self.correct_predictions_label = QLabel("正确预测数: 0")
        self.overall_accuracy_label = QLabel("总体准确率: 0.0%")
        
        overview_layout.addWidget(QLabel("统计信息:"), 0, 0)
        overview_layout.addWidget(self.total_predictions_label, 0, 1)
        overview_layout.addWidget(self.correct_predictions_label, 1, 1)
        overview_layout.addWidget(self.overall_accuracy_label, 2, 1)
        
        # 准确性趋势图
        self.accuracy_trend_frame = QFrame()
        self.accuracy_trend_frame.setMinimumHeight(200)
        self.accuracy_trend_frame.setStyleSheet("""
            QFrame {
                border: 2px solid #ddd;
                border-radius: 8px;
                background-color: #fafafa;
            }
        """)
        overview_layout.addWidget(self.accuracy_trend_frame, 0, 2, 3, 1)
        
        layout.addWidget(overview_group)
        
        # 按模型分析
        model_group = QGroupBox("各模型准确性分析")
        model_layout = QVBoxLayout(model_group)
        
        self.model_accuracy_table = QTableWidget(0, 5)
        self.model_accuracy_table.setHorizontalHeaderLabels([
            "模型", "预测次数", "正确次数", "准确率", "最近表现"
        ])
        self.model_accuracy_table.horizontalHeader().setStretchLastSection(True)
        
        self.model_accuracy_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                gridline-color: #e0e0e0;
                selection-background-color: #bbdefb;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
        """)
        
        model_layout.addWidget(self.model_accuracy_table)
        layout.addWidget(model_group)
        
        # 错误分析
        error_group = QGroupBox("❌ 错误分析")
        error_layout = QVBoxLayout(error_group)
        
        # 错误分类
        error_classification_layout = QGridLayout()
        
        self.error_categories = {
            'large_error': QLabel("大误差(>5%): 0"),
            'medium_error': QLabel("中等误差(1-5%): 0"),
            'small_error': QLabel("小误差(<1%): 0"),
            'direction_wrong': QLabel("方向错误: 0")
        }
        
        for i, (key, label) in enumerate(self.error_categories.items()):
            row = i // 2
            col = i % 2
            error_classification_layout.addWidget(label, row, col)
        
        error_layout.addLayout(error_classification_layout)
        
        # 错误详情列表
        self.error_details_list = QListWidget()
        self.error_details_list.setMaximumHeight(120)
        self.error_details_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #ffebee;
            }
        """)
        error_layout.addWidget(self.error_details_list)
        
        layout.addWidget(error_group)
        
        return tab
    
    def _create_status_footer(self) -> QWidget:
        """创建状态底部"""
        footer = QWidget()
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 状态信息
        self.overall_status_label = QLabel("🟢 系统正常")
        self.overall_status_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
        """)
        layout.addWidget(self.overall_status_label)
        
        # 更新信息
        layout.addStretch()
        
        self.last_update_label = QLabel("最后更新: --:--")
        self.last_update_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #666;
            }
        """)
        layout.addWidget(self.last_update_label)
        
        return footer
    
    def setup_connections(self):
        """设置信号连接"""
        # 控制按钮连接
        self.refresh_btn.clicked.connect(self._refresh_data)
        self.export_btn.clicked.connect(self._export_results)
        self.analyze_btn.clicked.connect(self._analyze_results)
        
        # 历史记录选择
        self.history_list.itemClicked.connect(self._on_history_item_clicked)
        
        # 权重调整连接
        for model, (slider, label) in self.weight_sliders.items():
            slider.valueChanged.connect(lambda value, m=model, l=label: self._update_weight_label(m, value, l))
        
        self.auto_adjust_btn.clicked.connect(self._auto_adjust_weights)
        
        # 选择器连接
        self.prediction_type_selector.currentTextChanged.connect(self._on_filter_changed)
        self.time_range_selector.currentTextChanged.connect(self._on_filter_changed)
        self.model_filter_selector.currentTextChanged.connect(self._on_filter_changed)
        self.column_selector.currentTextChanged.connect(self._on_column_filter_changed)
        
        # 表格选择连接
        self.detail_table.itemSelectionChanged.connect(self._on_detail_selection_changed)
        
        logger.info("预测结果展示界面信号连接设置完成")
    
    def start_monitoring(self):
        """开始监控"""
        self.update_timer.timeout.connect(self._update_display_data)
        self.update_timer.start(5000)

        self._initialize_real_results()

        logger.info("预测结果展示界面监控已启动")
    
    def _initialize_real_results(self):
        """从AI选股服务获取真实选股结果"""
        service_available = False
        try:
            from core.services.ai_selection_integration_service import get_ai_selection_service
            service = get_ai_selection_service()
            if service:
                service_available = True
        except Exception as e:
            logger.warning(f"AI选股服务不可用: {e}")

        if not service_available:
            self._show_no_data_message()
            return

        self._update_display_data()

    def _show_no_data_message(self):
        """显示无数据降级提示"""
        self.historical_results.clear()
        self.current_result = {
            'id': 'NODATA',
            'timestamp': datetime.now(),
            'type': '暂无选股结果',
            'predicted_value': 0.0,
            'actual_value': None,
            'confidence': 0.0,
            'models_used': [],
            'model_weights': {},
            'status': '无数据',
            'error': None,
            'accuracy': None
        }
        self.historical_results.append(self.current_result)
        self._update_display_data()
        self.overall_status_label.setText("🟡 暂无选股结果")
        self.overall_status_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                background-color: #fff3cd;
                color: #856404;
                border: 1px solid #ffeaa7;
            }
        """)
        logger.warning("选股结果不可用，显示降级提示")

    def _update_display_data(self):
        """更新显示数据"""
        try:
            # 更新历史记录列表
            self._update_history_list()
            
            # 更新详细表格
            self._update_detail_table()
            
            # 更新模型贡献度
            self._update_contribution_analysis()
            
            # 更新准确性统计
            self._update_accuracy_statistics()
            
            # 更新总体状态
            self._update_overall_status()
            
            # 更新时间戳
            self.last_update_label.setText(f"最后更新: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            logger.error(f"更新显示数据时出错: {e}")
    
    def _update_history_list(self):
        """更新历史记录列表"""
        self.history_list.clear()
        
        for result in reversed(list(self.historical_results)[-10:]):  # 最近10条
            item = QListWidgetItem()
            item.setText(f"{result['id']} - {result['type']} - {result['predicted_value']:.2f}")
            item.setData(Qt.UserRole, result['id'])
            item.setToolTip(f"时间: {result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                          f"模型: {', '.join(result['models_used'])}")
            
            self.history_list.addItem(item)
        
        # 选择最新记录
        if self.history_list.count() > 0:
            self.history_list.setCurrentRow(0)
    
    def _update_detail_table(self):
        """更新详细表格"""
        self.detail_table.setRowCount(0)
        
        for result in reversed(list(self.historical_results)[-20:]):  # 最近20条
            row = self.detail_table.rowCount()
            self.detail_table.insertRow(row)
            
            # 填充数据
            items = [
                result['id'],
                result['timestamp'].strftime('%H:%M:%S'),
                result['type'],
                f"{result['predicted_value']:.4f}",
                f"{result['actual_value']:.4f}" if result.get('actual_value') else "暂无",
                f"{result.get('error', 0):.4f}",
                f"{result.get('accuracy', 0)*100:.1f}%" if result.get('accuracy') else "暂无",
                ', '.join(result['models_used'])
            ]
            
            for col, item_text in enumerate(items):
                item = QTableWidgetItem(str(item_text))
                self.detail_table.setItem(row, col, item)
    
    def _update_contribution_analysis(self):
        """更新模型贡献度分析"""
        self.contribution_details.clear()
        
        # 计算各模型平均贡献度
        model_contributions = {}
        model_weights = {}
        
        for result in self.historical_results:
            if result.get('model_weights'):
                for model, weight in result['model_weights'].items():
                    if model not in model_contributions:
                        model_contributions[model] = []
                        model_weights[model] = []
                    model_contributions[model].append(weight)
                    model_weights[model].append(weight)
        
        # 添加到树形控件
        for model, contributions in model_contributions.items():
            avg_contribution = sum(contributions) / len(contributions)
            avg_weight = sum(model_weights[model]) / len(model_weights[model])
            
            item = QTreeWidgetItem(self.contribution_details)
            item.setText(0, model)
            item.setText(1, f"{avg_contribution:.1%}")
            item.setText(2, f"{avg_weight:.3f}")
            item.setText(3, "正常" if avg_contribution > 0.2 else "低权重")
        
        # 更新对比表格
        self._update_comparison_table()
    
    def _update_comparison_table(self):
        """更新对比表格"""
        self.comparison_table.setRowCount(0)
        
        comparison_data = [
            ("LSTM预测模型", "85.2%", "86.1%", "+0.9%"),
            ("ARIMA模型", "78.5%", "79.2%", "+0.7%"),
            ("XGBoost模型", "82.1%", "83.0%", "+0.9%"),
            ("随机森林模型", "76.8%", "77.5%", "+0.7%")
        ]
        
        for row, (model, before, after, improvement) in enumerate(comparison_data):
            self.comparison_table.insertRow(row)
            
            items = [model, before, after, improvement]
            for col, item_text in enumerate(items):
                item = QTableWidgetItem(str(item_text))
                self.comparison_table.setItem(row, col, item)
    
    def _update_accuracy_statistics(self):
        """更新准确性统计"""
        # 计算总体统计
        completed_results = [r for r in self.historical_results if r.get('accuracy') is not None]
        
        total_predictions = len(completed_results)
        correct_predictions = sum(1 for r in completed_results if r.get('accuracy', 0) > 0.8)
        
        self.accuracy_tracking['total_predictions'] = total_predictions
        self.accuracy_tracking['correct_predictions'] = correct_predictions
        
        if total_predictions > 0:
            overall_accuracy = correct_predictions / total_predictions
            self.accuracy_tracking['accuracy_history'].append(overall_accuracy)
            
            # 更新显示
            self.total_predictions_label.setText(f"总预测数: {total_predictions}")
            self.correct_predictions_label.setText(f"正确预测数: {correct_predictions}")
            self.overall_accuracy_label.setText(f"总体准确率: {overall_accuracy:.1%}")
        
        # 更新模型准确性表格
        self._update_model_accuracy_table()
        
        # 更新错误分析
        self._update_error_analysis()
    
    def _update_model_accuracy_table(self):
        """更新模型准确性表格"""
        self.model_accuracy_table.setRowCount(0)
        
        models = ["LSTM预测模型", "ARIMA模型", "XGBoost模型", "随机森林模型"]
        
        for model in models:
            # 统计该模型的预测
            model_results = [r for r in self.historical_results 
                           if model in r.get('models_used', []) and r.get('accuracy') is not None]
            
            if model_results:
                predictions_count = len(model_results)
                correct_count = sum(1 for r in model_results if r.get('accuracy', 0) > 0.8)
                accuracy = correct_count / predictions_count if predictions_count > 0 else 0
                
                # 最近表现
                recent_accuracy = sum(r.get('accuracy', 0) for r in model_results[-5:]) / min(5, len(model_results))
                recent_performance = "优秀" if recent_accuracy > 0.85 else "良好" if recent_accuracy > 0.75 else "一般"
                
                row = self.model_accuracy_table.rowCount()
                self.model_accuracy_table.insertRow(row)
                
                items = [
                    model,
                    str(predictions_count),
                    str(correct_count),
                    f"{accuracy:.1%}",
                    recent_performance
                ]
                
                for col, item_text in enumerate(items):
                    item = QTableWidgetItem(str(item_text))
                    self.model_accuracy_table.setItem(row, col, item)
    
    def _update_error_analysis(self):
        """更新错误分析"""
        completed_results = [r for r in self.historical_results if r.get('actual_value') is not None]
        
        error_categories = {
            'large_error': 0,    # > 5%
            'medium_error': 0,   # 1-5%
            'small_error': 0,    # < 1%
            'direction_wrong': 0 # 方向错误
        }
        
        for result in completed_results:
            if result.get('error'):
                error_pct = abs(result['error']) / result['predicted_value'] * 100
                
                if error_pct > 5:
                    error_categories['large_error'] += 1
                elif error_pct > 1:
                    error_categories['medium_error'] += 1
                else:
                    error_categories['small_error'] += 1
                
                # 方向错误检查
                if result.get('actual_value') and result.get('predicted_value'):
                    if (result['actual_value'] - 100) * (result['predicted_value'] - 100) < 0:
                        error_categories['direction_wrong'] += 1
        
        # 更新显示
        self.error_categories['large_error'].setText(f"大误差(>5%): {error_categories['large_error']}")
        self.error_categories['medium_error'].setText(f"中等误差(1-5%): {error_categories['medium_error']}")
        self.error_categories['small_error'].setText(f"小误差(<1%): {error_categories['small_error']}")
        self.error_categories['direction_wrong'].setText(f"方向错误: {error_categories['direction_wrong']}")
        
        # 更新错误详情列表
        self._update_error_details_list(completed_results)
    
    def _update_error_details_list(self, results):
        """更新错误详情列表"""
        self.error_details_list.clear()
        
        # 按误差大小排序，取前10个
        sorted_results = sorted(results, key=lambda x: x.get('error', 0), reverse=True)[:10]
        
        for result in sorted_results:
            item = QListWidgetItem()
            error_pct = abs(result['error']) / result['predicted_value'] * 100
            item.setText(f"{result['id']}: {result['type']} - 误差{error_pct:.2f}%")
            item.setToolTip(f"预测值: {result['predicted_value']:.4f}\n实际值: {result['actual_value']:.4f}")
            self.error_details_list.addItem(item)
    
    def _update_overall_status(self):
        """更新总体状态"""
        # 检查最近的预测准确性
        recent_results = [r for r in self.historical_results if 
                         (self.current_time - r['timestamp']).seconds < 3600]  # 最近1小时
        
        if recent_results:
            recent_accuracy = sum(r.get('accuracy', 0) for r in recent_results) / len(recent_results)
            if recent_accuracy > 0.8:
                status_text = "🟢 系统正常"
                status_style = """
                    QLabel {
                        font-size: 12px;
                        font-weight: bold;
                        padding: 6px 12px;
                        border-radius: 4px;
                        background-color: #d4edda;
                        color: #155724;
                        border: 1px solid #c3e6cb;
                    }
                """
            elif recent_accuracy > 0.6:
                status_text = "🟡 性能一般"
                status_style = """
                    QLabel {
                        font-size: 12px;
                        font-weight: bold;
                        padding: 6px 12px;
                        border-radius: 4px;
                        background-color: #fff3cd;
                        color: #856404;
                        border: 1px solid #ffeaa7;
                    }
                """
            else:
                status_text = "🔴 需要关注"
                status_style = """
                    QLabel {
                        font-size: 12px;
                        font-weight: bold;
                        padding: 6px 12px;
                        border-radius: 4px;
                        background-color: #f8d7da;
                        color: #721c24;
                        border: 1px solid #f5c6cb;
                    }
                """
        else:
            status_text = "🟢 系统正常"
            status_style = """
                QLabel {
                    font-size: 12px;
                    font-weight: bold;
                    padding: 6px 12px;
                    border-radius: 4px;
                    background-color: #d4edda;
                    color: #155724;
                    border: 1px solid #c3e6cb;
                }
            """
        
        self.overall_status_label.setText(status_text)
        self.overall_status_label.setStyleSheet(status_style)
    
    def _refresh_data(self):
        """刷新数据"""
        try:
            # 重新生成一些数据
            self._generate_sample_result()
            
            # 发送刷新信号
            self.refresh_btn.setEnabled(False)
            QTimer.singleShot(1000, lambda: self.refresh_btn.setEnabled(True))  # 1秒后恢复
            
            logger.info("预测结果数据已刷新")
            
        except Exception as e:
            logger.error(f"刷新数据时出错: {e}")
    
    def _generate_sample_result(self):
        """从服务获取最新选股结果"""
        try:
            from core.services.ai_selection_integration_service import get_ai_selection_service
            service = get_ai_selection_service()
            if not service:
                return

            self._update_display_data()
        except Exception as e:
            logger.warning(f"获取选股结果失败: {e}")
    
    def _export_results(self):
        """导出结果"""
        try:
            # 构建导出数据
            export_data = {
                'timestamp': datetime.now().isoformat(),
                'total_predictions': self.accuracy_tracking['total_predictions'],
                'correct_predictions': self.accuracy_tracking['correct_predictions'],
                'historical_results': list(self.historical_results),
                'accuracy_by_model': self.accuracy_tracking['accuracy_by_model']
            }
            
            # 发送导出信号
            self.export_requested.emit(export_data)
            
            logger.info("预测结果导出请求已发送")
            
        except Exception as e:
            logger.error(f"导出结果时出错: {e}")
    
    def _analyze_results(self):
        """分析结果"""
        try:
            # 构建分析数据
            analysis_data = {
                'timestamp': datetime.now().isoformat(),
                'analysis_type': 'comprehensive',
                'time_range': self.time_range_selector.currentText(),
                'model_filter': self.model_filter_selector.currentText(),
                'current_results': list(self.historical_results)[-10:]  # 最近10条
            }
            
            # 发送分析信号
            self.analysis_requested.emit(analysis_data)
            
            logger.info("预测结果分析请求已发送")
            
        except Exception as e:
            logger.error(f"分析结果时出错: {e}")
    
    def _on_history_item_clicked(self, item):
        """历史记录项点击事件"""
        try:
            result_id = item.data(Qt.UserRole)
            self._display_historical_result(result_id)
            
        except Exception as e:
            logger.error(f"显示历史结果时出错: {e}")
    
    def _display_historical_result(self, result_id: str):
        """显示历史结果详情"""
        # 查找对应的结果
        for result in self.historical_results:
            if result['id'] == result_id:
                self.current_result = result
                self._update_prediction_overview()
                
                # 更新详情文本
                details_text = f"""预测ID: {result['id']}
时间: {result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}
类型: {result['type']}
预测值: {result['predicted_value']:.4f}
实际值: {result['actual_value']:.4f}" if result.get('actual_value') else "实际值: 暂无"
置信度: {result['confidence']:.1%}
使用模型: {', '.join(result['models_used'])}
模型权重: {', '.join([f"{k}:{v:.3f}" for k, v in result.get('model_weights', {}).items()])}
误差: {result.get('error', 0):.4f}
准确率: {result.get('accuracy', 0)*100:.1f}%" if result.get('accuracy') else "准确率: 暂无"
状态: {result['status']}
"""
                
                self.prediction_details_text.setPlainText(details_text)
                break
    
    def _update_prediction_overview(self):
        """更新预测概览"""
        if not self.current_result:
            return
        
        result = self.current_result
        
        self.prediction_id_label.setText(f"ID: {result['id']}")
        self.prediction_time_label.setText(f"时间: {result['timestamp'].strftime('%H:%M:%S')}")
        self.prediction_type_label.setText(f"类型: {result['type']}")
        self.predicted_value_label.setText(f"预测值: {result['predicted_value']:.4f}")
        self.actual_value_label.setText(f"实际值: {result.get('actual_value', '暂无'):.4f}" if result.get('actual_value') else "实际值: 暂无")
        self.confidence_label.setText(f"置信度: {result['confidence']:.1%}")
        self.models_used_label.setText(f"使用模型: {', '.join(result['models_used'])}")
        
        # 更新概览指标
        if result.get('accuracy'):
            self.overview_metrics['accuracy'].metric_value_label.setText(f"{result['accuracy']*100:.1f}%")
        
        if result.get('error'):
            error_pct = abs(result['error']) / result['predicted_value'] * 100
            self.overview_metrics['error'].metric_value_label.setText(f"{error_pct:.2f}%")
        
        self.overview_metrics['confidence'].metric_value_label.setText(f"{result['confidence']*100:.1f}%")
        self.overview_metrics['models'].metric_value_label.setText(f"{len(result['models_used'])}")
        
        # 风险评分 (基于误差和置信度)
        if result.get('error') and result.get('confidence'):
            base_risk = abs(result['error']) / result['predicted_value'] * 100
            confidence_risk = (1 - result['confidence']) * 50
            risk_score = min(100, base_risk + confidence_risk)
            self.overview_metrics['risk'].metric_value_label.setText(f"{risk_score:.0f}")
    
    def _update_weight_label(self, model: str, value: int, label: QLabel):
        """更新权重标签"""
        label.setText(f"{value}%")
        
        # 实时调整其他权重以保持总和为100%
        other_models = [m for m in self.weight_sliders.keys() if m != model]
        total_other = sum(self.weight_sliders[m][0].value() for m in other_models)
        
        if total_other > 0:
            adjustment_factor = (100 - value) / total_other
            for other_model in other_models:
                other_slider, other_label = self.weight_sliders[other_model]
                new_value = int(other_slider.value() * adjustment_factor)
                other_slider.setValue(new_value)
                other_label.setText(f"{new_value}%")
    
    def _auto_adjust_weights(self):
        """自动调整权重"""
        try:
            # 模拟基于性能的权重调整
            models = ["LSTM预测模型", "ARIMA模型", "XGBoost模型", "随机森林模型"]
            base_weights = [0.35, 0.25, 0.25, 0.15]  # 基于历史性能的基础权重
            
            for i, (model, weight) in enumerate(zip(models, base_weights)):
                if model in self.weight_sliders:
                    slider, label = self.weight_sliders[model]
                    slider_value = int(weight * 100)
                    slider.setValue(slider_value)
                    label.setText(f"{slider_value}%")
            
            logger.info("权重自动调整完成")
            
        except Exception as e:
            logger.error(f"自动调整权重时出错: {e}")
    
    def _on_filter_changed(self):
        """筛选条件改变事件"""
        self._update_display_data()
    
    def _on_column_filter_changed(self):
        """列筛选改变事件"""
        # 这里可以添加列显示逻辑
        pass
    
    def _on_detail_selection_changed(self):
        """详细表格选择改变事件"""
        current_row = self.detail_table.currentRow()
        if current_row >= 0:
            # 可以在这里添加选择变化处理逻辑
            pass
    
    def _apply_unified_styles(self):
        """应用统一样式"""
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                font-family: 'Microsoft YaHei', Arial, sans-serif;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTabWidget::pane {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-bottom: none;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover {
                background-color: #e9ecef;
            }
        """)
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.update_timer.isActive():
            self.update_timer.stop()
        logger.info("预测结果展示界面已关闭")
        super().closeEvent(event)


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    panel = PredictionResultsPanel()
    panel.show()

    sys.exit(app.exec_())