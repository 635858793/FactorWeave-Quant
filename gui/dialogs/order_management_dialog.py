#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单管理对话框

提供完整的订单管理功能，包括订单创建、查询、取消、修改等
"""

from loguru import logger
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QLabel, QLineEdit, QTextEdit, QTableWidget,
    QTableWidgetItem, QPushButton, QComboBox, QDateEdit,
    QFrame, QSplitter, QGroupBox, QMessageBox,
    QHeaderView, QSpinBox, QDoubleSpinBox, QCheckBox,
    QProgressBar, QAbstractItemView, QMenu, QAction, QWidget,
    QListWidget, QListWidgetItem, QDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QDate, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QColor

from core.trading.order_models import (
    Order, OrderRequest, OrderQuery, OrderType, OrderStatus, OrderCategory
)
from core.trading.order_service import OrderService
from core.containers import get_service_container
from core.events import get_event_bus
from core.plugin_types import AssetType
from core.trading.account_manager import AccountManager
from core.services.unified_data_manager import UnifiedDataManager
from core.services.asset_service import AssetService

from .base_dialog import BaseDialog


class OrderManagementDialog(BaseDialog):
    """订单管理对话框"""

    # 信号定义
    order_created = pyqtSignal(dict)
    order_cancelled = pyqtSignal(dict)
    order_modified = pyqtSignal(dict)

    def __init__(self, parent=None):
        """
        初始化订单管理对话框

        Args:
            parent: 父窗口
        """
        self.service_container = get_service_container()
        self.event_bus = get_event_bus()
        self.order_service = self.service_container.resolve(OrderService)

        self.orders = []
        self.current_order = None
        self.filter_conditions = {}

        super().__init__(
            parent,
            title="订单管理",
            min_size=(1200, 800),
            size=(1500, 900),
            settings_key="OrderManagementDialog"
        )

        self.init_ui()
        self.load_orders()

        logger.info("订单管理对话框初始化完成")

    def init_ui(self):
        """初始化用户界面"""
        try:
            # 主布局
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(10, 10, 10, 10)

            # 创建工具栏
            self.create_toolbar()
            main_layout.addWidget(self.toolbar_frame)

            # 创建内容区域
            content_splitter = QSplitter(Qt.Horizontal)

            # 左侧订单列表
            self.create_order_list()
            content_splitter.addWidget(self.order_list_frame)

            # 右侧详情区域
            self.create_detail_area()
            content_splitter.addWidget(self.detail_widget)

            # 设置分割比例
            content_splitter.setSizes([900, 500])
            main_layout.addWidget(content_splitter)

            # 创建底部状态栏
            self.create_status_bar()
            main_layout.addWidget(self.status_bar_frame)

            # 订阅事件
            self.subscribe_events()

        except Exception as e:
            logger.error(f"初始化UI失败: {e}")

    def create_toolbar(self):
        """创建工具栏"""
        try:
            self.toolbar_frame = QFrame()
            self.toolbar_frame.setFrameStyle(QFrame.StyledPanel)
            self.toolbar_frame.setMaximumHeight(50)

            layout = QHBoxLayout(self.toolbar_frame)
            layout.setContentsMargins(10, 5, 10, 5)

            # 创建订单按钮
            self.create_order_btn = QPushButton("创建订单")
            self.create_order_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
            """)
            self.create_order_btn.clicked.connect(self.show_create_order_dialog)
            layout.addWidget(self.create_order_btn)

            # 刷新按钮
            self.refresh_btn = QPushButton("刷新")
            self.refresh_btn.clicked.connect(self.load_orders)
            layout.addWidget(self.refresh_btn)

            # 导出按钮
            self.export_btn = QPushButton("导出")
            self.export_btn.clicked.connect(self.export_orders)
            layout.addWidget(self.export_btn)

            layout.addStretch()

            # 筛选区域
            filter_label = QLabel("资产类型:")
            layout.addWidget(filter_label)

            self.asset_type_filter_combo = QComboBox()
            self.asset_type_filter_combo.addItems(["股票-A股", "股票-B股", "股票-港股", "股票-美股", "股票-北交所",
                "期货", "期权", "加密货币", "外汇", "债券", "商品", "指数", "基金", "权证"])
            self.asset_type_filter_combo.currentTextChanged.connect(self.apply_filter)
            layout.addWidget(self.asset_type_filter_combo)

            filter_label = QLabel("状态筛选:")
            layout.addWidget(filter_label)

            self.status_filter_combo = QComboBox()
            self.status_filter_combo.addItems(["全部", "待处理", "已提交", "部分成交", "已成交", "已取消", "已拒绝"])
            self.status_filter_combo.currentTextChanged.connect(self.apply_filter)
            layout.addWidget(self.status_filter_combo)

            # 搜索框
            search_label = QLabel("搜索:")
            layout.addWidget(search_label)

            self.search_edit = QLineEdit()
            self.search_edit.setPlaceholderText("输入订单ID或股票代码...")
            self.search_edit.setMaximumWidth(200)
            self.search_edit.textChanged.connect(self.on_search_text_changed)
            layout.addWidget(self.search_edit)

            # 验证设置按钮
            self.validation_settings_btn = QPushButton("下单验证设置")
            self.validation_settings_btn.clicked.connect(self.show_validation_settings)
            layout.addWidget(self.validation_settings_btn)

            layout.addStretch()

        except Exception as e:
            logger.error(f"创建工具栏失败: {e}")

    def create_order_list(self):
        """创建订单列表"""
        try:
            self.order_list_frame = QFrame()
            self.order_list_frame.setFrameStyle(QFrame.StyledPanel)

            layout = QVBoxLayout(self.order_list_frame)
            layout.setContentsMargins(5, 5, 5, 5)

            # 标题
            title_label = QLabel("订单列表")
            title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
            layout.addWidget(title_label)

            # 订单表格
            self.order_table = QTableWidget()
            # R271: 12 列, 新增"拒绝原因"列展示 error_code/error_message (风控熔断拒绝原因 UI 呈现)
            self.order_table.setColumnCount(12)
            self.order_table.setHorizontalHeaderLabels([
                "订单ID", "资产类型", "股票代码", "方向", "数量", "价格", "状态", "创建时间", "成交数量", "成交价格", "拒绝原因", "操作"
            ])
            self.order_table.setSortingEnabled(True)
            self.order_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.order_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
            # 设置表格样式
            header = self.order_table.horizontalHeader()
            header.setStretchLastSection(True)
            # header.setSectionResizeMode(QHeaderView.Interactive)

            # 设置选择模式
            self.order_table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.order_table.setSelectionMode(QAbstractItemView.SingleSelection)
            self.order_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

            # 连接信号
            self.order_table.itemSelectionChanged.connect(self.on_order_selected)
            self.order_table.itemDoubleClicked.connect(self.on_order_double_clicked)

            layout.addWidget(self.order_table)

        except Exception as e:
            logger.error(f"创建订单列表失败: {e}")

    def create_detail_area(self):
        """创建详情区域"""
        try:
            self.detail_widget = QTabWidget()

            # 订单详情标签页
            try:
                self.create_order_detail_tab()
                self.detail_widget.addTab(self.order_detail_tab, "订单详情")
            except Exception as e:
                logger.error(f"创建订单详情标签页失败: {e}")
                self.order_detail_tab = QWidget()
                self.detail_widget.addTab(self.order_detail_tab, "订单详情")

            # 订单成交记录标签页
            try:
                self.create_order_fills_tab()
                self.detail_widget.addTab(self.order_fills_tab, "成交记录")
            except Exception as e:
                logger.error(f"创建订单成交记录标签页失败: {e}")
                self.order_fills_tab = QWidget()
                self.detail_widget.addTab(self.order_fills_tab, "成交记录")

            # 订单统计标签页
            try:
                self.create_order_statistics_tab()
                self.detail_widget.addTab(self.order_statistics_tab, "订单统计")
            except Exception as e:
                logger.error(f"创建订单统计标签页失败: {e}")
                self.order_statistics_tab = QWidget()
                self.detail_widget.addTab(self.order_statistics_tab, "订单统计")

        except Exception as e:
            logger.error(f"创建详情区域失败: {e}")

    def create_order_detail_tab(self):
        """创建订单详情标签页"""
        try:
            self.order_detail_tab = QWidget()
            layout = QVBoxLayout(self.order_detail_tab)

            # 订单信息组
            info_group = QGroupBox("订单信息")
            info_layout = QGridLayout()
            info_layout.setSpacing(10)

            # 订单ID
            info_layout.addWidget(QLabel("订单ID:"), 0, 0)
            self.order_id_label = QLabel("-")
            self.order_id_label.setStyleSheet("font-weight: bold; color: #333;")
            info_layout.addWidget(self.order_id_label, 0, 1)

            # 资产类型
            info_layout.addWidget(QLabel("资产类型:"), 1, 0)
            self.asset_type_label = QLabel("-")
            self.asset_type_label.setStyleSheet("font-weight: bold; color: #333;")
            info_layout.addWidget(self.asset_type_label, 1, 1)

            # 股票代码
            info_layout.addWidget(QLabel("股票代码:"), 2, 0)
            self.stock_code_label = QLabel("-")
            self.stock_code_label.setStyleSheet("font-weight: bold; color: #333;")
            info_layout.addWidget(self.stock_code_label, 2, 1)

            # 订单方向
            info_layout.addWidget(QLabel("订单方向:"), 3, 0)
            self.order_type_label = QLabel("-")
            self.order_type_label.setStyleSheet("font-weight: bold; color: #333;")
            info_layout.addWidget(self.order_type_label, 3, 1)

            # 订单数量
            info_layout.addWidget(QLabel("订单数量:"), 4, 0)
            self.order_quantity_label = QLabel("-")
            self.order_quantity_label.setStyleSheet("font-weight: bold; color: #333;")
            info_layout.addWidget(self.order_quantity_label, 4, 1)

            # 订单价格
            info_layout.addWidget(QLabel("订单价格:"), 5, 0)
            self.order_price_label = QLabel("-")
            self.order_price_label.setStyleSheet("font-weight: bold; color: #333;")
            info_layout.addWidget(self.order_price_label, 5, 1)

            # 订单状态
            info_layout.addWidget(QLabel("订单状态:"), 6, 0)
            self.order_status_label = QLabel("-")
            self.order_status_label.setStyleSheet("font-weight: bold; color: #333;")
            info_layout.addWidget(self.order_status_label, 6, 1)

            # 创建时间
            info_layout.addWidget(QLabel("创建时间:"), 7, 0)
            self.create_time_label = QLabel("-")
            self.create_time_label.setStyleSheet("color: #666;")
            info_layout.addWidget(self.create_time_label, 7, 1)

            # 成交数量
            info_layout.addWidget(QLabel("成交数量:"), 8, 0)
            self.filled_quantity_label = QLabel("-")
            self.filled_quantity_label.setStyleSheet("color: #666;")
            info_layout.addWidget(self.filled_quantity_label, 8, 1)

            # 成交价格
            info_layout.addWidget(QLabel("成交价格:"), 9, 0)
            self.filled_price_label = QLabel("-")
            self.filled_price_label.setStyleSheet("color: #666;")
            info_layout.addWidget(self.filled_price_label, 9, 1)

            # 资产特定信息
            info_layout.addWidget(QLabel("资产特定信息:"), 10, 0)
            self.asset_specific_info_label = QLabel("-")
            self.asset_specific_info_label.setStyleSheet("color: #666;")
            self.asset_specific_info_label.setWordWrap(True)
            info_layout.addWidget(self.asset_specific_info_label, 10, 1)

            info_group.setLayout(info_layout)
            layout.addWidget(info_group)

            # 操作按钮组
            action_group = QGroupBox("订单操作")
            action_layout = QHBoxLayout()

            self.cancel_order_btn = QPushButton("取消订单")
            self.cancel_order_btn.setEnabled(False)
            self.cancel_order_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
                QPushButton:disabled {
                    background-color: #ccc;
                }
            """)
            self.cancel_order_btn.clicked.connect(self.cancel_selected_order)
            action_layout.addWidget(self.cancel_order_btn)

            self.modify_order_btn = QPushButton("修改订单")
            self.modify_order_btn.setEnabled(False)
            self.modify_order_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f39c12;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #e67e22;
                }
                QPushButton:disabled {
                    background-color: #ccc;
                }
            """)
            self.modify_order_btn.clicked.connect(self.modify_selected_order)
            action_layout.addWidget(self.modify_order_btn)

            self.submit_order_btn = QPushButton("提交订单")
            self.submit_order_btn.setEnabled(False)
            self.submit_order_btn.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #229954;
                }
                QPushButton:disabled {
                    background-color: #ccc;
                }
            """)
            self.submit_order_btn.clicked.connect(self.submit_selected_order)
            action_layout.addWidget(self.submit_order_btn)

            action_group.setLayout(action_layout)
            layout.addWidget(action_group)

            # 备注信息
            note_group = QGroupBox("备注信息")
            note_layout = QVBoxLayout()

            self.note_text = QTextEdit()
            self.note_text.setReadOnly(True)
            self.note_text.setMaximumHeight(100)
            note_layout.addWidget(self.note_text)

            note_group.setLayout(note_layout)
            layout.addWidget(note_group)

            layout.addStretch()

        except Exception as e:
            logger.error(f"创建订单详情标签页失败: {e}")

    def create_order_fills_tab(self):
        """创建订单成交记录标签页"""
        try:
            self.order_fills_tab = QWidget()
            layout = QVBoxLayout(self.order_fills_tab)

            # 成交记录表格
            self.fills_table = QTableWidget()
            self.fills_table.setColumnCount(5)
            self.fills_table.setHorizontalHeaderLabels([
                "成交ID", "成交时间", "成交价格", "成交数量", "手续费"
            ])

            # 设置表格样式
            header = self.fills_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QHeaderView.Interactive)

            self.fills_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.fills_table.setAlternatingRowColors(True)

            layout.addWidget(self.fills_table)

        except Exception as e:
            logger.error(f"创建订单成交记录标签页失败: {e}")

    def create_order_statistics_tab(self):
        """创建订单统计标签页"""
        try:
            self.order_statistics_tab = QWidget()
            layout = QVBoxLayout(self.order_statistics_tab)

            # 基础统计信息
            stats_group = QGroupBox("基础统计")
            stats_layout = QGridLayout()

            stats_layout.addWidget(QLabel("总订单数:"), 0, 0)
            self.total_orders_label = QLabel("0")
            self.total_orders_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #333;")
            stats_layout.addWidget(self.total_orders_label, 0, 1)

            stats_layout.addWidget(QLabel("已成交订单:"), 1, 0)
            self.filled_orders_label = QLabel("0")
            self.filled_orders_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #27ae60;")
            stats_layout.addWidget(self.filled_orders_label, 1, 1)

            stats_layout.addWidget(QLabel("已取消订单:"), 2, 0)
            self.cancelled_orders_label = QLabel("0")
            self.cancelled_orders_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #e74c3c;")
            stats_layout.addWidget(self.cancelled_orders_label, 2, 1)

            stats_layout.addWidget(QLabel("已拒绝订单:"), 3, 0)
            self.rejected_orders_label = QLabel("0")
            self.rejected_orders_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #c0392b;")
            stats_layout.addWidget(self.rejected_orders_label, 3, 1)

            stats_layout.addWidget(QLabel("成交率:"), 4, 0)
            self.fill_rate_label = QLabel("0%")
            self.fill_rate_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #2980b9;")
            stats_layout.addWidget(self.fill_rate_label, 4, 1)

            stats_group.setLayout(stats_layout)
            layout.addWidget(stats_group)

            # 执行分析
            execution_group = QGroupBox("执行分析")
            execution_layout = QGridLayout()

            execution_layout.addWidget(QLabel("平均执行时间:"), 0, 0)
            self.avg_execution_time_label = QLabel("-")
            self.avg_execution_time_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #333;")
            execution_layout.addWidget(self.avg_execution_time_label, 0, 1)

            execution_layout.addWidget(QLabel("平均成交比例:"), 1, 0)
            self.avg_fill_ratio_label = QLabel("-")
            self.avg_fill_ratio_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #333;")
            execution_layout.addWidget(self.avg_fill_ratio_label, 1, 1)

            execution_layout.addWidget(QLabel("总成交金额:"), 2, 0)
            self.total_filled_value_label = QLabel("-")
            self.total_filled_value_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #27ae60;")
            execution_layout.addWidget(self.total_filled_value_label, 2, 1)

            execution_layout.addWidget(QLabel("总手续费:"), 3, 0)
            self.total_commission_label = QLabel("-")
            self.total_commission_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #e67e22;")
            execution_layout.addWidget(self.total_commission_label, 3, 1)

            execution_group.setLayout(execution_layout)
            layout.addWidget(execution_group)

            # 滑点分析
            slippage_group = QGroupBox("滑点分析")
            slippage_layout = QGridLayout()

            slippage_layout.addWidget(QLabel("平均滑点:"), 0, 0)
            self.avg_slippage_label = QLabel("-")
            self.avg_slippage_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #333;")
            slippage_layout.addWidget(self.avg_slippage_label, 0, 1)

            slippage_layout.addWidget(QLabel("最大滑点:"), 1, 0)
            self.max_slippage_label = QLabel("-")
            self.max_slippage_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #e74c3c;")
            slippage_layout.addWidget(self.max_slippage_label, 1, 1)

            slippage_layout.addWidget(QLabel("最小滑点:"), 2, 0)
            self.min_slippage_label = QLabel("-")
            self.min_slippage_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #27ae60;")
            slippage_layout.addWidget(self.min_slippage_label, 2, 1)

            slippage_layout.addWidget(QLabel("正向滑点次数:"), 3, 0)
            self.positive_slippage_count_label = QLabel("-")
            self.positive_slippage_count_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #27ae60;")
            slippage_layout.addWidget(self.positive_slippage_count_label, 3, 1)

            slippage_layout.addWidget(QLabel("负向滑点次数:"), 4, 0)
            self.negative_slippage_count_label = QLabel("-")
            self.negative_slippage_count_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #e74c3c;")
            slippage_layout.addWidget(self.negative_slippage_count_label, 4, 1)

            slippage_group.setLayout(slippage_layout)
            layout.addWidget(slippage_group)

            # 高级分析
            advanced_group = QGroupBox("高级分析")
            advanced_layout = QGridLayout()

            advanced_layout.addWidget(QLabel("订单执行路径:"), 0, 0)
            self.path_analysis_btn = QPushButton("分析")
            self.path_analysis_btn.clicked.connect(self.analyze_order_path)
            advanced_layout.addWidget(self.path_analysis_btn, 0, 1)

            advanced_layout.addWidget(QLabel("订单成本分析:"), 1, 0)
            self.cost_analysis_btn = QPushButton("分析")
            self.cost_analysis_btn.clicked.connect(self.analyze_order_cost)
            advanced_layout.addWidget(self.cost_analysis_btn, 1, 1)

            advanced_layout.addWidget(QLabel("订单时间特征:"), 2, 0)
            self.timing_analysis_btn = QPushButton("分析")
            self.timing_analysis_btn.clicked.connect(self.analyze_order_timing)
            advanced_layout.addWidget(self.timing_analysis_btn, 2, 1)

            advanced_layout.addWidget(QLabel("订单风险分析:"), 3, 0)
            self.risk_analysis_btn = QPushButton("分析")
            self.risk_analysis_btn.clicked.connect(self.analyze_order_risk)
            advanced_layout.addWidget(self.risk_analysis_btn, 3, 1)

            advanced_layout.addWidget(QLabel("成交概率预测:"), 4, 0)
            self.probability_btn = QPushButton("预测")
            self.probability_btn.clicked.connect(self.predict_fill_probability)
            advanced_layout.addWidget(self.probability_btn, 4, 1)

            advanced_group.setLayout(advanced_layout)
            layout.addWidget(advanced_group)

            # 刷新分析按钮
            refresh_button = QPushButton("刷新分析")
            refresh_button.clicked.connect(self.refresh_analysis)
            refresh_button.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
            """)
            layout.addWidget(refresh_button)

            layout.addStretch()

        except Exception as e:
            logger.error(f"创建订单统计标签页失败: {e}")

    def create_status_bar(self):
        """创建状态栏"""
        try:
            self.status_bar_frame = QFrame()
            self.status_bar_frame.setFrameStyle(QFrame.StyledPanel)
            self.status_bar_frame.setMaximumHeight(30)

            layout = QHBoxLayout(self.status_bar_frame)
            layout.setContentsMargins(10, 5, 10, 5)

            self.status_label = QLabel("就绪")
            layout.addWidget(self.status_label)

            layout.addStretch()

            self.order_count_label = QLabel("订单数: 0")
            layout.addWidget(self.order_count_label)

        except Exception as e:
            logger.error(f"创建状态栏失败: {e}")

    def subscribe_events(self):
        """订阅事件"""
        try:
            self.event_bus.subscribe('order_created', self.on_order_created_event)
            self.event_bus.subscribe('order_updated', self.on_order_updated_event)
            self.event_bus.subscribe('order_cancelled', self.on_order_cancelled_event)
            self.event_bus.subscribe('order_filled', self.on_order_filled_event)
            self.event_bus.subscribe('order_rejected', self.on_order_rejected_event)
            self.event_bus.subscribe('order_submit_failed', self.on_order_submit_failed_event)
            self.event_bus.subscribe('order_modified', self.on_order_modified_event)
            # R271: 订阅订单验证失败事件 (覆盖 DAILY_LOSS_LIMIT_EXCEEDED 等订单未创建型拒绝)
            self.event_bus.subscribe('order_validation_failed', self.on_order_validation_failed_event)
        except Exception as e:
            logger.error(f"订阅事件失败: {e}")

    def closeEvent(self, event):
        try:
            self.event_bus.unsubscribe('order_created', self.on_order_created_event)
            self.event_bus.unsubscribe('order_updated', self.on_order_updated_event)
            self.event_bus.unsubscribe('order_cancelled', self.on_order_cancelled_event)
            self.event_bus.unsubscribe('order_filled', self.on_order_filled_event)
            self.event_bus.unsubscribe('order_rejected', self.on_order_rejected_event)
            self.event_bus.unsubscribe('order_submit_failed', self.on_order_submit_failed_event)
            self.event_bus.unsubscribe('order_modified', self.on_order_modified_event)
            self.event_bus.unsubscribe('order_validation_failed', self.on_order_validation_failed_event)
        except Exception as e:
            logger.error(f"取消事件订阅失败: {e}")
        super().closeEvent(event)

    def load_orders(self):
        """加载订单列表"""
        try:
            self.status_label.setText("正在加载订单...")

            # 构建查询条件
            query = OrderQuery(limit=1000, sort_by="create_time", sort_order="desc")

            # 应用资产类型筛选
            asset_type_filter = self.asset_type_filter_combo.currentText()
            if asset_type_filter != "全部":
                asset_type_map = {
                    "股票-A股": AssetType.STOCK_A,
                    "股票-B股": AssetType.STOCK_B,
                    "股票-港股": AssetType.STOCK_HK,
                    "股票-美股": AssetType.STOCK_US,
                    "股票-北交所": AssetType.STOCK_B,
                    "期货": AssetType.FUTURES,
                    "期权": AssetType.OPTION,
                    "加密货币": AssetType.CRYPTO,
                    "外汇": AssetType.FOREX,
                    "债券": AssetType.BOND,
                    "商品": AssetType.COMMODITY,
                    "指数": AssetType.INDEX,
                    "基金": AssetType.FUND,
                    "权证": AssetType.WARRANT
                }
                query.asset_type = asset_type_map.get(asset_type_filter)

            # 应用状态筛选
            status_filter = self.status_filter_combo.currentText()
            if status_filter == "待处理":
                query.order_status = OrderStatus.PENDING
            elif status_filter == "已提交":
                query.order_status = OrderStatus.SUBMITTED
            elif status_filter == "部分成交":
                query.order_status = OrderStatus.PARTIALLY_FILLED
            elif status_filter == "已成交":
                query.order_status = OrderStatus.FILLED
            elif status_filter == "已取消":
                query.order_status = OrderStatus.CANCELLED
            elif status_filter == "已拒绝":
                query.order_status = OrderStatus.REJECTED

            # 查询订单
            self.orders = self.order_service.query_orders(query)

            # 更新表格
            self.update_order_table()

            # 更新统计
            self.update_statistics()

            self.status_label.setText(f"加载完成，共 {len(self.orders)} 条订单")
            self.order_count_label.setText(f"订单数: {len(self.orders)}")

        except Exception as e:
            logger.error(f"加载订单失败: {e}")
            self.status_label.setText(f"加载失败: {str(e)}")

    def update_order_table(self):
        """更新订单表格"""
        try:
            self.order_table.setRowCount(0)

            for order in self.orders:
                row = self.order_table.rowCount()
                self.order_table.insertRow(row)

                # 订单ID
                self.order_table.setItem(row, 0, QTableWidgetItem(order.order_id))

                # 资产类型
                asset_type_text = order.asset_type.value if order.asset_type else "-"
                self.order_table.setItem(row, 1, QTableWidgetItem(asset_type_text))

                # 股票代码
                self.order_table.setItem(row, 2, QTableWidgetItem(order.stock_code))

                # 订单方向
                type_text = "买入" if order.order_type == OrderType.BUY else "卖出"
                type_item = QTableWidgetItem(type_text)
                type_item.setForeground(QColor("#27ae60") if order.order_type == OrderType.BUY else QColor("#e74c3c"))
                self.order_table.setItem(row, 3, type_item)

                # 订单数量
                self.order_table.setItem(row, 4, QTableWidgetItem(str(order.order_quantity)))

                # 订单价格
                self.order_table.setItem(row, 5, QTableWidgetItem(f"{order.order_price:.2f}"))

                # 订单状态
                status_text = self.get_status_text(order.order_status)
                status_item = QTableWidgetItem(status_text)
                status_item.setForeground(self.get_status_color(order.order_status))
                self.order_table.setItem(row, 6, status_item)

                # 创建时间
                self.order_table.setItem(row, 7, QTableWidgetItem(order.create_time.strftime("%Y-%m-%d %H:%M:%S")))

                # 成交数量
                self.order_table.setItem(row, 8, QTableWidgetItem(str(order.filled_quantity)))

                # 成交价格
                filled_price = f"{order.filled_price:.2f}" if order.filled_price > 0 else "-"
                self.order_table.setItem(row, 9, QTableWidgetItem(filled_price))

                # 拒绝原因 (R271: error_code + error_message 文本, 风控熔断拒绝原因 UI 呈现)
                reject_reason = self._format_reject_reason(
                    getattr(order, 'error_code', None), getattr(order, 'error_message', None))
                reason_item = QTableWidgetItem(reject_reason)
                if reject_reason:
                    reason_item.setForeground(QColor("#e74c3c"))
                    reason_item.setToolTip(reject_reason)
                self.order_table.setItem(row, 10, reason_item)

                # 操作按钮
                btn_widget = QPushButton("操作")
                btn_widget.clicked.connect(lambda checked, o=order: self.show_order_context_menu(o))
                self.order_table.setCellWidget(row, 11, btn_widget)

        except Exception as e:
            logger.error(f"更新订单表格失败: {e}")

    @staticmethod
    def _format_reject_reason(error_code, error_message) -> str:
        """R271: 格式化拒绝原因 (error_code 文案映射 + error_message 截断)"""
        code_map = {
            'RISK_HALTED': '风控熔断',
            'DAILY_LOSS_LIMIT_EXCEEDED': '当日亏损熔断',
            'RISK_CHECK_FAILED': '风控拒绝',
        }
        if error_code:
            label = code_map.get(error_code, error_code)
            if error_message:
                return f"{label}: {error_message[:40]}"
            return label
        if error_message:
            return error_message[:40]
        return ""

    def get_status_text(self, status: OrderStatus) -> str:
        """获取状态文本"""
        status_map = {
            OrderStatus.PENDING: "待处理",
            OrderStatus.SUBMITTED: "已提交",
            OrderStatus.PARTIALLY_FILLED: "部分成交",
            OrderStatus.FILLED: "已成交",
            OrderStatus.CANCELLED: "已取消",
            OrderStatus.REJECTED: "已拒绝",
            OrderStatus.EXPIRED: "已过期"
        }
        return status_map.get(status, status.value)

    def get_status_color(self, status: OrderStatus) -> QColor:
        """获取状态颜色"""
        color_map = {
            OrderStatus.PENDING: QColor("#f39c12"),
            OrderStatus.SUBMITTED: QColor("#3498db"),
            OrderStatus.PARTIALLY_FILLED: QColor("#9b59b6"),
            OrderStatus.FILLED: QColor("#27ae60"),
            OrderStatus.CANCELLED: QColor("#e74c3c"),
            OrderStatus.REJECTED: QColor("#c0392b"),
            OrderStatus.EXPIRED: QColor("#7f8c8d")
        }
        return color_map.get(status, QColor("#333"))

    def update_statistics(self):
        """更新订单统计"""
        try:
            total = len(self.orders)
            filled = len([o for o in self.orders if o.order_status == OrderStatus.FILLED])
            cancelled = len([o for o in self.orders if o.order_status == OrderStatus.CANCELLED])
            rejected = len([o for o in self.orders if o.order_status == OrderStatus.REJECTED])

            fill_rate = (filled / total * 100) if total > 0 else 0

            if hasattr(self, 'total_orders_label'):
                self.total_orders_label.setText(str(total))
            if hasattr(self, 'filled_orders_label'):
                self.filled_orders_label.setText(str(filled))
            if hasattr(self, 'cancelled_orders_label'):
                self.cancelled_orders_label.setText(str(cancelled))
            if hasattr(self, 'rejected_orders_label'):
                self.rejected_orders_label.setText(str(rejected))
            if hasattr(self, 'fill_rate_label'):
                self.fill_rate_label.setText(f"{fill_rate:.1f}%")

        except Exception as e:
            logger.error(f"更新订单统计失败: {e}")

    def refresh_analysis(self):
        """刷新分析数据"""
        try:
            self.status_label.setText("正在刷新分析...")

            # 执行分析
            execution_analysis = self.order_service.analyze_orders(period="day")
            if execution_analysis:
                self.avg_execution_time_label.setText(f"{execution_analysis.get('avg_execution_time', 0):.2f}秒")
                self.avg_fill_ratio_label.setText(f"{execution_analysis.get('avg_fill_ratio', 0):.2%}")
                self.total_filled_value_label.setText(f"{execution_analysis.get('filled_value', 0):.2f}")
                self.total_commission_label.setText(f"{execution_analysis.get('total_commission', 0):.2f}")

            # 滑点分析
            slippage_analysis = self.order_service.analyze_slippage(period="day")
            if slippage_analysis:
                self.avg_slippage_label.setText(f"{slippage_analysis.get('avg_slippage', 0):.4f}")
                self.max_slippage_label.setText(f"{slippage_analysis.get('max_slippage', 0):.4f}")
                self.min_slippage_label.setText(f"{slippage_analysis.get('min_slippage', 0):.4f}")
                self.positive_slippage_count_label.setText(str(slippage_analysis.get('positive_slippage_count', 0)))
                self.negative_slippage_count_label.setText(str(slippage_analysis.get('negative_slippage_count', 0)))

            self.status_label.setText("分析刷新完成")

        except Exception as e:
            logger.error(f"刷新分析失败: {e}")
            self.status_label.setText(f"刷新失败: {str(e)}")

    def analyze_order_path(self):
        """分析订单执行路径"""
        try:
            if not self.current_order:
                QMessageBox.warning(self, '警告', '请先选择一个订单')
                return

            self.status_label.setText("正在分析订单执行路径...")
            path_analysis = self.order_service.analyze_order_path(self.current_order.order_id)

            if path_analysis:
                message = f"订单执行路径分析:\n\n"
                message += f"创建时间: {path_analysis.get('create_time', '-')}\n"
                message += f"提交时间: {path_analysis.get('submit_time', '-')}\n"
                message += f"完成时间: {path_analysis.get('completion_time', '-')}\n"
                message += f"总耗时: {path_analysis.get('total_duration', 0):.2f} 秒\n"
                message += f"提交耗时: {path_analysis.get('submit_duration', 0):.2f} 秒\n"
                message += f"执行耗时: {path_analysis.get('execution_duration', 0):.2f} 秒\n"
                message += f"状态变化次数: {len(path_analysis.get('status_changes', []))}\n"
                message += f"成交记录数: {len(path_analysis.get('fills', []))}"

                QMessageBox.information(self, '订单执行路径分析', message)
                self.status_label.setText("分析完成")
            else:
                QMessageBox.warning(self, '警告', '订单执行路径分析失败')
                self.status_label.setText("分析失败")

        except Exception as e:
            logger.error(f"分析订单执行路径失败: {e}")
            QMessageBox.critical(self, '错误', f'分析失败: {str(e)}')
            self.status_label.setText(f"分析失败: {str(e)}")

    def analyze_order_cost(self):
        """分析订单成本"""
        try:
            if not self.current_order:
                QMessageBox.warning(self, '警告', '请先选择一个订单')
                return

            self.status_label.setText("正在分析订单成本...")
            cost_analysis = self.order_service.analyze_order_cost(self.current_order.order_id)

            if cost_analysis:
                message = f"订单成本分析:\n\n"
                message += f"订单价值: {cost_analysis.get('order_value', 0):.2f}\n"
                message += f"成交价值: {cost_analysis.get('filled_value', 0):.2f}\n"
                message += f"手续费: {cost_analysis.get('commission', 0):.2f}\n"
                message += f"滑点成本: {cost_analysis.get('slippage_cost', 0):.2f}\n"
                message += f"总成本: {cost_analysis.get('total_cost', 0):.2f}\n"
                message += f"成本比例: {cost_analysis.get('cost_ratio', 0):.4f}"

                QMessageBox.information(self, '订单成本分析', message)
                self.status_label.setText("分析完成")
            else:
                QMessageBox.warning(self, '警告', '订单成本分析失败')
                self.status_label.setText("分析失败")

        except Exception as e:
            logger.error(f"分析订单成本失败: {e}")
            QMessageBox.critical(self, '错误', f'分析失败: {str(e)}')
            self.status_label.setText(f"分析失败: {str(e)}")

    def analyze_order_timing(self):
        """分析订单时间特征"""
        try:
            self.status_label.setText("正在分析订单时间特征...")
            timing_analysis = self.order_service.analyze_order_timing(period="day")

            if timing_analysis:
                message = f"订单时间特征分析:\n\n"
                message += f"总订单数: {timing_analysis.get('total_orders', 0)}\n"
                message += f"平均等待时间: {timing_analysis.get('avg_waiting_time', 0):.2f} 秒\n"
                message += f"最大等待时间: {timing_analysis.get('max_waiting_time', 0):.2f} 秒\n"
                message += f"最小等待时间: {timing_analysis.get('min_waiting_time', 0):.2f} 秒\n"

                most_active_hour = timing_analysis.get('most_active_hour', {})
                if most_active_hour:
                    message += f"\n最活跃时段: {most_active_hour.get('hour', 0)}:00 ({most_active_hour.get('count', 0)} 个订单)\n"

                most_active_weekday = timing_analysis.get('most_active_weekday', {})
                if most_active_weekday:
                    message += f"最活跃星期: {most_active_weekday.get('weekday', '-')} ({most_active_weekday.get('count', 0)} 个订单)"

                QMessageBox.information(self, '订单时间特征分析', message)
                self.status_label.setText("分析完成")
            else:
                QMessageBox.warning(self, '警告', '订单时间特征分析失败')
                self.status_label.setText("分析失败")

        except Exception as e:
            logger.error(f"分析订单时间特征失败: {e}")
            QMessageBox.critical(self, '错误', f'分析失败: {str(e)}')
            self.status_label.setText(f"分析失败: {str(e)}")

    def analyze_order_risk(self):
        """分析订单风险"""
        try:
            if not self.current_order:
                QMessageBox.warning(self, '警告', '请先选择一个订单')
                return

            self.status_label.setText("正在分析订单风险...")
            risk_analysis = self.order_service.analyze_order_risk(self.current_order.order_id)

            if risk_analysis:
                message = f"订单风险分析:\n\n"
                message += f"风险等级: {risk_analysis.get('risk_level', '-')}\n"
                message += f"风险评分: {risk_analysis.get('risk_score', 0):.2f}\n\n"
                message += f"市场风险: {risk_analysis.get('market_risk', 0):.2f}\n"
                message += f"执行风险: {risk_analysis.get('execution_risk', 0):.2f}\n"
                message += f"流动性风险: {risk_analysis.get('liquidity_risk', 0):.2f}\n"
                message += f"集中度风险: {risk_analysis.get('concentration_risk', 0):.2f}\n\n"
                message += f"风险因子: {', '.join(risk_analysis.get('risk_factors', []))}"

                QMessageBox.information(self, '订单风险分析', message)
                self.status_label.setText("分析完成")
            else:
                QMessageBox.warning(self, '警告', '订单风险分析失败')
                self.status_label.setText("分析失败")

        except Exception as e:
            logger.error(f"分析订单风险失败: {e}")
            QMessageBox.critical(self, '错误', f'分析失败: {str(e)}')
            self.status_label.setText(f"分析失败: {str(e)}")

    def predict_fill_probability(self):
        """预测订单成交概率"""
        try:
            if not self.current_order:
                QMessageBox.warning(self, '警告', '请先选择一个订单')
                return

            self.status_label.setText("正在预测订单成交概率...")
            order_request = {
                'stock_code': self.current_order.stock_code,
                'order_type': self.current_order.order_type.value,
                'asset_type': self.current_order.asset_type.value
            }
            prediction = self.order_service.predict_order_fill_probability(order_request)

            if prediction:
                message = f"订单成交概率预测:\n\n"
                message += f"成交概率: {prediction.get('probability', 0):.2%}\n"
                message += f"置信度: {prediction.get('confidence', '-')}\n\n"

                factors = prediction.get('factors', {})
                for key, value in factors.items():
                    message += f"{key}: {value}\n"

                QMessageBox.information(self, '订单成交概率预测', message)
                self.status_label.setText("预测完成")
            else:
                QMessageBox.warning(self, '警告', '订单成交概率预测失败')
                self.status_label.setText("预测失败")

        except Exception as e:
            logger.error(f"预测订单成交概率失败: {e}")
            QMessageBox.critical(self, '错误', f'预测失败: {str(e)}')
            self.status_label.setText(f"预测失败: {str(e)}")

    @pyqtSlot()
    def on_order_selected(self):
        """订单选中事件"""
        try:
            selected_items = self.order_table.selectedItems()
            if not selected_items:
                self.current_order = None
                self.clear_order_detail()
                self.disable_action_buttons()
                return

            row = selected_items[0].row()
            order_id = self.order_table.item(row, 0).text()
            self.current_order = next((o for o in self.orders if o.order_id == order_id), None)

            if self.current_order:
                self.update_order_detail(self.current_order)
                self.load_order_fills(self.current_order.order_id)
                self.enable_action_buttons()

        except Exception as e:
            logger.error(f"订单选中事件处理失败: {e}")

    def on_order_double_clicked(self, item):
        """订单双击事件"""
        try:
            row = item.row()
            order_id = self.order_table.item(row, 0).text()
            order = next((o for o in self.orders if o.order_id == order_id), None)

            if order:
                self.show_order_detail_dialog(order)

        except Exception as e:
            logger.error(f"订单双击事件处理失败: {e}")

    def update_order_detail(self, order: Order):
        """更新订单详情"""
        try:
            self.order_id_label.setText(order.order_id)
            self.asset_type_label.setText(order.asset_type.value if order.asset_type else "-")
            self.stock_code_label.setText(order.stock_code)
            self.order_type_label.setText("买入" if order.order_type == OrderType.BUY else "卖出")
            self.order_quantity_label.setText(str(order.order_quantity))
            self.order_price_label.setText(f"{order.order_price:.2f}")
            self.order_status_label.setText(self.get_status_text(order.order_status))
            self.create_time_label.setText(order.create_time.strftime("%Y-%m-%d %H:%M:%S"))
            self.filled_quantity_label.setText(str(order.filled_quantity))
            self.filled_price_label.setText(f"{order.filled_price:.2f}" if order.filled_price > 0 else "-")

            # 更新资产特定信息
            asset_specific_info = ""
            if order.asset_type == AssetType.FUTURES:
                asset_specific_info = f"合约乘数: {order.contract_multiplier}\n"
                asset_specific_info += f"保证金比例: {order.margin_ratio:.2%}"
            elif order.asset_type == AssetType.OPTION:
                asset_specific_info = f"行权价: {order.strike_price:.2f}\n"
                asset_specific_info += f"到期日: {order.expiry_date.strftime('%Y-%m-%d') if order.expiry_date else '-'}\n"
                asset_specific_info += f"期权类型: {order.option_type or '-'}"
            elif order.asset_type in [AssetType.STOCK_A, AssetType.STOCK_B, AssetType.STOCK_H, AssetType.STOCK_US, AssetType.STOCK_HK]:
                asset_specific_info = "标准股票订单"
            elif order.asset_type == AssetType.CRYPTO:
                asset_specific_info = "加密货币订单"
            elif order.asset_type == AssetType.FOREX:
                asset_specific_info = "外汇订单"
            elif order.asset_type == AssetType.FUND:
                asset_specific_info = "基金订单"
            elif order.asset_type == AssetType.BOND:
                asset_specific_info = "债券订单"
            elif order.asset_type == AssetType.COMMODITY:
                asset_specific_info = "商品订单"
            elif order.asset_type == AssetType.INDEX:
                asset_specific_info = "指数订单"
            elif order.asset_type == AssetType.WARRANT:
                asset_specific_info = "权证订单"
            else:
                asset_specific_info = "其他资产类型"

            self.asset_specific_info_label.setText(asset_specific_info)

            # 更新备注
            note_text = f"策略ID: {order.strategy_id}\n"
            note_text += f"用户ID: {order.user_id}\n"
            note_text += f"账户ID: {order.account_id}\n"
            if order.tags:
                note_text += f"标签: {', '.join(order.tags)}\n"
            if getattr(order, 'error_code', None):
                note_text += f"错误码: {order.error_code}\n"
            if order.error_message:
                note_text += f"错误信息: {order.error_message}"

            self.note_text.setText(note_text)

        except Exception as e:
            logger.error(f"更新订单详情失败: {e}")

    def clear_order_detail(self):
        """清空订单详情"""
        try:
            self.order_id_label.setText("-")
            self.stock_code_label.setText("-")
            self.order_type_label.setText("-")
            self.order_quantity_label.setText("-")
            self.order_price_label.setText("-")
            self.order_status_label.setText("-")
            self.create_time_label.setText("-")
            self.filled_quantity_label.setText("-")
            self.filled_price_label.setText("-")
            self.note_text.clear()
            self.fills_table.setRowCount(0)

        except Exception as e:
            logger.error(f"清空订单详情失败: {e}")

    def load_order_fills(self, order_id: str):
        """加载订单成交记录"""
        try:
            fills = self.order_service.get_order_fills(order_id)
            self.fills_table.setRowCount(0)

            for fill in fills:
                row = self.fills_table.rowCount()
                self.fills_table.insertRow(row)

                self.fills_table.setItem(row, 0, QTableWidgetItem(fill.fill_id))
                self.fills_table.setItem(row, 1, QTableWidgetItem(fill.fill_time.strftime("%Y-%m-%d %H:%M:%S")))
                self.fills_table.setItem(row, 2, QTableWidgetItem(f"{fill.fill_price:.2f}"))
                self.fills_table.setItem(row, 3, QTableWidgetItem(str(fill.fill_quantity)))
                self.fills_table.setItem(row, 4, QTableWidgetItem(f"{fill.commission:.2f}"))

        except Exception as e:
            logger.error(f"加载订单成交记录失败: {e}")

    def enable_action_buttons(self):
        """启用操作按钮"""
        try:
            if not self.current_order:
                return

            # 取消订单按钮
            self.cancel_order_btn.setEnabled(self.current_order.is_active)

            # 修改订单按钮
            self.modify_order_btn.setEnabled(self.current_order.is_active)

            # 提交订单按钮
            self.submit_order_btn.setEnabled(self.current_order.order_status == OrderStatus.PENDING)

        except Exception as e:
            logger.error(f"启用操作按钮失败: {e}")

    def disable_action_buttons(self):
        """禁用操作按钮"""
        try:
            self.cancel_order_btn.setEnabled(False)
            self.modify_order_btn.setEnabled(False)
            self.submit_order_btn.setEnabled(False)

        except Exception as e:
            logger.error(f"禁用操作按钮失败: {e}")

    def show_create_order_dialog(self):
        """显示创建订单对话框"""
        try:
            account_manager = self.service_container.resolve(AccountManager)
            dialog = CreateOrderDialog(self.order_service, account_manager, self)
            if dialog.exec_() == QDialog.Accepted:
                self.load_orders()
                self.order_created.emit({})

        except Exception as e:
            logger.error(f"显示创建订单对话框失败: {e}")

    def show_order_detail_dialog(self, order: Order):
        """显示订单详情对话框"""
        try:
            dialog = OrderDetailDialog(order, self)
            dialog.exec_()

        except Exception as e:
            logger.error(f"显示订单详情对话框失败: {e}")

    def show_order_context_menu(self, order: Order):
        """显示订单右键菜单"""
        try:
            menu = QMenu(self)

            if order.is_active:
                cancel_action = QAction("取消订单", self)
                cancel_action.triggered.connect(lambda: self.cancel_order(order.order_id))
                menu.addAction(cancel_action)

                modify_action = QAction("修改订单", self)
                modify_action.triggered.connect(lambda: self.modify_order(order.order_id))
                menu.addAction(modify_action)

                if order.order_status == OrderStatus.PENDING:
                    submit_action = QAction("提交订单", self)
                    submit_action.triggered.connect(lambda: self.submit_order(order.order_id))
                    menu.addAction(submit_action)

            view_action = QAction("查看详情", self)
            view_action.triggered.connect(lambda: self.show_order_detail_dialog(order))
            menu.addAction(view_action)

            menu.exec_(self.cursor().pos())

        except Exception as e:
            logger.error(f"显示订单右键菜单失败: {e}")

    def cancel_selected_order(self):
        """取消选中的订单"""
        if self.current_order:
            self.cancel_order(self.current_order.order_id)

    def modify_selected_order(self):
        """修改选中的订单"""
        if self.current_order:
            self.modify_order(self.current_order.order_id)

    def submit_selected_order(self):
        """提交选中的订单"""
        if self.current_order:
            self.submit_order(self.current_order.order_id)

    def cancel_order(self, order_id: str):
        """取消订单"""
        try:
            reply = QMessageBox.question(
                self, '确认取消', '确定要取消该订单吗？',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                result = self.order_service.cancel_order(order_id)
                if result.status == 'success':
                    QMessageBox.information(self, '成功', '订单已取消')
                    self.load_orders()
                    self.order_cancelled.emit({'order_id': order_id})
                else:
                    QMessageBox.warning(self, '失败', f'取消订单失败: {result.message}')

        except Exception as e:
            logger.error(f"{order_id}:取消订单失败: {e}")
            QMessageBox.critical(self, '错误', f'取消订单失败: {str(e)}')

    def modify_order(self, order_id: str):
        """修改订单"""
        try:
            order = self.order_service.get_order(order_id)
            if not order:
                QMessageBox.warning(self, '警告', '订单不存在')
                return

            dialog = ModifyOrderDialog(order, self.order_service, self)
            if dialog.exec_() == QDialog.Accepted:
                self.load_orders()
                self.order_modified.emit({'order_id': order_id})

        except Exception as e:
            logger.error(f"修改订单失败: {e}")
            QMessageBox.critical(self, '错误', f'修改订单失败: {str(e)}')

    def submit_order(self, order_id: str):
        """提交订单"""
        try:
            result = self.order_service.submit_order(order_id)
            if result.status == 'success':
                QMessageBox.information(self, '成功', '订单已提交')
                self.load_orders()
            else:
                QMessageBox.warning(self, '失败', f'提交订单失败: {result.message}')

        except Exception as e:
            logger.error(f"提交订单失败: {e}")
            QMessageBox.critical(self, '错误', f'提交订单失败: {str(e)}')

    def apply_filter(self):
        """应用筛选"""
        try:
            self.load_orders()

        except Exception as e:
            logger.error(f"应用筛选失败: {e}")

    def export_orders(self):
        """导出订单"""
        try:
            QMessageBox.information(self, '提示', '订单导出功能开发中...')

        except Exception as e:
            logger.error(f"导出订单失败: {e}")

    @pyqtSlot(dict)
    def on_order_created_event(self, event):
        """订单创建事件"""
        try:
            self.load_orders()
        except Exception as e:
            logger.error(f"处理订单创建事件失败: {e}")

    @pyqtSlot(object)
    def on_order_updated_event(self, event):
        """订单更新事件"""
        try:
            self.load_orders()
        except Exception as e:
            logger.error(f"处理订单更新事件失败: {e}")

    @pyqtSlot(object)
    def on_order_cancelled_event(self, event):
        """订单取消事件"""
        try:
            self.load_orders()
        except Exception as e:
            logger.error(f"处理订单取消事件失败: {e}")

    @pyqtSlot(object)
    def on_order_filled_event(self, event):
        """订单成交事件"""
        try:
            self.load_orders()
        except Exception as e:
            logger.error(f"处理订单成交事件失败: {e}")

    @pyqtSlot(object)
    def on_order_rejected_event(self, event):
        """订单被拒绝事件"""
        try:
            self.load_orders()
        except Exception as e:
            logger.error(f"处理订单被拒绝事件失败: {e}")

    @pyqtSlot(object)
    def on_order_submit_failed_event(self, event):
        """订单提交失败事件"""
        try:
            self.load_orders()
        except Exception as e:
            logger.error(f"处理订单提交失败事件失败: {e}")

    @pyqtSlot(object)
    def on_order_validation_failed_event(self, event):
        """订单验证失败事件 (R271: 覆盖订单未创建型拒绝, 如 DAILY_LOSS_LIMIT_EXCEEDED)

        订单因风控验证失败未创建 (无法从订单列表展示), 此处直接在状态栏呈现拒绝原因。
        """
        try:
            stock_code = getattr(event, 'stock_code', '')
            error = getattr(event, 'error', '')
            error_code = getattr(event, 'error_code', '')
            reason = self._format_reject_reason(error_code, error)
            if reason:
                self.status_label.setText(f"订单验证失败: {stock_code} - {reason}")
                logger.warning(f"订单验证失败 (UI 呈现): {stock_code} - {reason}")
        except Exception as e:
            logger.error(f"处理订单验证失败事件失败: {e}")

    @pyqtSlot(object)
    def on_order_modified_event(self, event):
        """订单修改事件"""
        try:
            self.load_orders()
        except Exception as e:
            logger.error(f"处理订单修改事件失败: {e}")

    @pyqtSlot(str)
    def on_search_text_changed(self, text: str):
        """搜索文本变化"""
        try:
            if not text:
                self.apply_filter()
                return

            # 搜索订单
            filtered_orders = []
            for order in self.orders:
                if (text.lower() in order.order_id.lower() or
                    text.lower() in order.stock_code.lower()):
                    filtered_orders.append(order)

            # 更新表格
            self.update_order_table_with_orders(filtered_orders)

        except Exception as e:
            logger.error(f"搜索失败: {e}")

    def show_validation_settings(self):
        """显示验证设置对话框"""
        try:
            dialog = ValidationSettingsDialog(self.order_service.validator, self)
            if dialog.exec_() == QDialog.Accepted:
                # 重新加载订单以应用新的验证规则
                self.load_orders()
                QMessageBox.information(self, "设置已保存", "验证设置已更新")

        except Exception as e:
            logger.error(f"显示验证设置失败: {e}")
            QMessageBox.critical(self, "错误", f"显示验证设置失败: {str(e)}")

    def update_order_table_with_orders(self, orders: List[Order]):
        """使用指定订单列表更新表格"""
        try:
            self.order_table.setRowCount(0)

            for row, order in enumerate(orders):
                self.order_table.insertRow(row)

                # 订单ID
                self.order_table.setItem(row, 0, QTableWidgetItem(order.order_id))

                # 股票代码
                self.order_table.setItem(row, 1, QTableWidgetItem(order.stock_code))

                # 订单类型
                self.order_table.setItem(row, 2, QTableWidgetItem(order.order_type.value))

                # 订单类别
                self.order_table.setItem(row, 3, QTableWidgetItem(order.order_category.value))

                # 订单价格
                self.order_table.setItem(row, 4, QTableWidgetItem(f"{order.order_price:.2f}"))

                # 订单数量
                self.order_table.setItem(row, 5, QTableWidgetItem(str(order.order_quantity)))

                # 订单状态
                self.order_table.setItem(row, 6, QTableWidgetItem(order.order_status.value))

                # 创建时间
                self.order_table.setItem(row, 7, QTableWidgetItem(order.create_time.strftime("%Y-%m-%d %H:%M:%S")))

                # 策略ID
                self.order_table.setItem(row, 8, QTableWidgetItem(order.strategy_id))

        except Exception as e:
            logger.error(f"更新订单表格失败: {e}")


class ValidationSettingsDialog(QDialog):
    """验证设置对话框"""

    def __init__(self, validator, parent=None):
        super().__init__(parent)
        self.validator = validator
        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        try:
            self.setWindowTitle("订单验证设置")
            self.setMinimumSize(400, 300)

            layout = QVBoxLayout(self)

            # 验证选项
            options_group = QGroupBox("验证选项")
            options_layout = QGridLayout()

            # 交易时间验证
            self.validate_trading_time_checkbox = QCheckBox("启用交易时间验证")
            self.validate_trading_time_checkbox.setChecked(
                self.validator._config.get('validate_trading_time', False)
            )
            self.validate_trading_time_checkbox.setToolTip(
                "验证订单是否在交易时间内提交"
            )
            options_layout.addWidget(self.validate_trading_time_checkbox, 0, 0, 1, 2)

            # 订单价值限制验证
            self.validate_order_value_checkbox = QCheckBox("启用订单价值限制验证")
            self.validate_order_value_checkbox.setChecked(
                self.validator._config.get('validate_order_value', False)
            )
            self.validate_order_value_checkbox.setToolTip(
                "验证订单价值是否超过限制"
            )
            options_layout.addWidget(self.validate_order_value_checkbox, 1, 0, 1, 2)

            # 资金验证
            self.validate_funds_checkbox = QCheckBox("启用资金验证")
            self.validate_funds_checkbox.setChecked(
                self.validator._config.get('validate_funds', False)
            )
            self.validate_funds_checkbox.setToolTip(
                "验证账户资金是否充足（需要账户管理系统）"
            )
            options_layout.addWidget(self.validate_funds_checkbox, 2, 0, 1, 2)

            # 持仓验证
            self.validate_position_checkbox = QCheckBox("启用持仓验证")
            self.validate_position_checkbox.setChecked(
                self.validator._config.get('validate_position', False)
            )
            self.validate_position_checkbox.setToolTip(
                "验证持仓是否超过限制（需要账户管理系统）"
            )
            options_layout.addWidget(self.validate_position_checkbox, 3, 0, 1, 2)

            options_group.setLayout(options_layout)
            layout.addWidget(options_group)

            # 验证参数
            params_group = QGroupBox("验证参数")
            params_layout = QGridLayout()

            # 最小订单数量
            params_layout.addWidget(QLabel("最小订单数量:"), 0, 0)
            self.min_order_quantity_spin = QSpinBox()
            self.min_order_quantity_spin.setRange(1, 1000000)
            self.min_order_quantity_spin.setValue(
                self.validator._config.get('min_order_quantity', 100)
            )
            params_layout.addWidget(self.min_order_quantity_spin, 0, 1)

            # 最大订单数量
            params_layout.addWidget(QLabel("最大订单数量:"), 1, 0)
            self.max_order_quantity_spin = QSpinBox()
            self.max_order_quantity_spin.setRange(1, 10000000)
            self.max_order_quantity_spin.setValue(
                self.validator._config.get('max_order_quantity', 1000000)
            )
            params_layout.addWidget(self.max_order_quantity_spin, 1, 1)

            # 最小订单价格
            params_layout.addWidget(QLabel("最小订单价格:"), 2, 0)
            self.min_order_price_spin = QDoubleSpinBox()
            self.min_order_price_spin.setRange(0.01, 1000000.0)
            self.min_order_price_spin.setDecimals(2)
            self.min_order_price_spin.setValue(
                self.validator._config.get('min_order_price', 0.01)
            )
            params_layout.addWidget(self.min_order_price_spin, 2, 1)

            # 最大订单价格
            params_layout.addWidget(QLabel("最大订单价格:"), 3, 0)
            self.max_order_price_spin = QDoubleSpinBox()
            self.max_order_price_spin.setRange(0.01, 10000000.0)
            self.max_order_price_spin.setDecimals(2)
            self.max_order_price_spin.setValue(
                self.validator._config.get('max_order_price', 1000000.0)
            )
            params_layout.addWidget(self.max_order_price_spin, 3, 1)

            params_group.setLayout(params_layout)
            layout.addWidget(params_group)

            # 按钮
            button_layout = QHBoxLayout()
            button_layout.addStretch()

            save_btn = QPushButton("保存")
            save_btn.clicked.connect(self.save_settings)
            button_layout.addWidget(save_btn)

            cancel_btn = QPushButton("取消")
            cancel_btn.clicked.connect(self.reject)
            button_layout.addWidget(cancel_btn)

            layout.addLayout(button_layout)

        except Exception as e:
            logger.error(f"初始化验证设置对话框失败: {e}")

    def save_settings(self):
        """保存设置"""
        try:
            # 更新验证器配置
            self.validator._config['validate_trading_time'] = self.validate_trading_time_checkbox.isChecked()
            self.validator._config['validate_order_value'] = self.validate_order_value_checkbox.isChecked()
            self.validator._config['validate_funds'] = self.validate_funds_checkbox.isChecked()
            self.validator._config['validate_position'] = self.validate_position_checkbox.isChecked()

            # 更新验证参数
            self.validator._config['min_order_quantity'] = self.min_order_quantity_spin.value()
            self.validator._config['max_order_quantity'] = self.max_order_quantity_spin.value()
            self.validator._config['min_order_price'] = self.min_order_price_spin.value()
            self.validator._config['max_order_price'] = self.max_order_price_spin.value()

            logger.info("验证设置已保存")
            self.accept()

        except Exception as e:
            logger.error(f"保存验证设置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存验证设置失败: {str(e)}")


class CreateOrderDialog(QDialog):
    """创建订单对话框"""

    def __init__(self, order_service: OrderService, account_manager: AccountManager, parent=None):
        super().__init__(parent)
        self.order_service = order_service
        self.account_manager = account_manager
        self.service_container = get_service_container()
        
        # 初始化搜索结果浮窗
        self.search_results_popup = None
        self.search_timer = None
        self.current_search_results = []
        
        self.init_ui()
        
        # 初始化时加载默认账号列表
        self.load_accounts()

    def init_ui(self):
        """初始化用户界面"""
        try:
            self.setWindowTitle("创建订单")
            self.setMinimumSize(500, 400)

            layout = QVBoxLayout(self)

            # 订单信息表单
            form_layout = QGridLayout()

            # 资产类型
            form_layout.addWidget(QLabel("资产类型*:"), 0, 0)
            self.asset_type_combo = QComboBox()
            self.asset_type_combo.addItems([
                "股票-A股", "股票-B股", "股票-港股", "股票-美股", "股票-北交所",
                "期货", "期权", "加密货币", "外汇", "债券", "商品", "指数", "基金", "权证"
            ])
            self.asset_type_combo.setCurrentIndex(0)
            self.asset_type_combo.currentTextChanged.connect(self.on_asset_type_changed)
            form_layout.addWidget(self.asset_type_combo, 0, 1)

            # 账号选择
            form_layout.addWidget(QLabel("账号:"), 1, 0)
            self.account_combo = QComboBox()
            self.account_combo.addItem("使用默认账号", "default")
            form_layout.addWidget(self.account_combo, 1, 1)

            # 股票代码（支持自动筛选）
            form_layout.addWidget(QLabel("股票代码*:"), 2, 0)
            stock_code_layout = QHBoxLayout()
            self.stock_code_input = QLineEdit()
            self.stock_code_input.setPlaceholderText("输入代码或名称自动筛选...")
            self.stock_code_input.setMinimumWidth(200)
            self.stock_code_input.textChanged.connect(self.on_stock_code_text_changed)
            stock_code_layout.addWidget(self.stock_code_input)
            
            form_layout.addLayout(stock_code_layout, 2, 1)

            # 订单方向
            form_layout.addWidget(QLabel("订单方向*:"), 4, 0)
            self.order_type_combo = QComboBox()
            self.order_type_combo.addItems(["买入", "卖出"])
            form_layout.addWidget(self.order_type_combo, 4, 1)

            # 订单类别
            form_layout.addWidget(QLabel("订单类别*:"), 5, 0)
            self.order_category_combo = QComboBox()
            self.order_category_combo.addItems(["限价单", "市价单", "止损单", "止损限价单"])
            form_layout.addWidget(self.order_category_combo, 5, 1)

            # 订单数量
            form_layout.addWidget(QLabel("订单数量*:"), 6, 0)
            self.order_quantity_spin = QSpinBox()
            self.order_quantity_spin.setRange(100, 1000000)
            self.order_quantity_spin.setValue(100)
            self.order_quantity_spin.setSingleStep(100)
            form_layout.addWidget(self.order_quantity_spin, 6, 1)

            # 订单价格
            form_layout.addWidget(QLabel("订单价格*:"), 7, 0)
            self.order_price_spin = QDoubleSpinBox()
            self.order_price_spin.setRange(0.01, 1000000.0)
            self.order_price_spin.setValue(10.0)
            self.order_price_spin.setDecimals(2)
            self.order_price_spin.setSingleStep(0.01)
            form_layout.addWidget(self.order_price_spin, 7, 1)

            # 止损价格
            form_layout.addWidget(QLabel("止损价格:"), 8, 0)
            self.stop_price_spin = QDoubleSpinBox()
            self.stop_price_spin.setRange(0.01, 1000000.0)
            self.stop_price_spin.setValue(0.0)
            self.stop_price_spin.setDecimals(2)
            self.stop_price_spin.setSingleStep(0.01)
            form_layout.addWidget(self.stop_price_spin, 8, 1)

            # 期货参数（初始隐藏）
            form_layout.addWidget(QLabel("合约代码:"), 9, 0)
            self.futures_contract_input = QLineEdit()
            self.futures_contract_input.setPlaceholderText("例如: IF2401")
            self.futures_contract_input.setVisible(False)
            form_layout.addWidget(self.futures_contract_input, 9, 1)

            form_layout.addWidget(QLabel("合约月份:"), 10, 0)
            self.futures_month_combo = QComboBox()
            self.futures_month_combo.addItems([str(i) for i in range(1, 13)])
            self.futures_month_combo.setCurrentIndex(0)
            self.futures_month_combo.setVisible(False)
            form_layout.addWidget(self.futures_month_combo, 10, 1)

            form_layout.addWidget(QLabel("合约乘数:"), 11, 0)
            self.futures_multiplier_spin = QSpinBox()
            self.futures_multiplier_spin.setRange(1, 10000)
            self.futures_multiplier_spin.setValue(1)
            self.futures_multiplier_spin.setVisible(False)
            form_layout.addWidget(self.futures_multiplier_spin, 11, 1)

            form_layout.addWidget(QLabel("保证金比例(%):"), 12, 0)
            self.futures_margin_spin = QDoubleSpinBox()
            self.futures_margin_spin.setRange(0.0, 100.0)
            self.futures_margin_spin.setValue(10.0)
            self.futures_margin_spin.setDecimals(2)
            self.futures_margin_spin.setVisible(False)
            form_layout.addWidget(self.futures_margin_spin, 12, 1)

            # 期权参数（初始隐藏）
            form_layout.addWidget(QLabel("行权价:"), 13, 0)
            self.option_strike_price_spin = QDoubleSpinBox()
            self.option_strike_price_spin.setRange(0.01, 1000000.0)
            self.option_strike_price_spin.setValue(10.0)
            self.option_strike_price_spin.setDecimals(2)
            self.option_strike_price_spin.setVisible(False)
            form_layout.addWidget(self.option_strike_price_spin, 13, 1)

            form_layout.addWidget(QLabel("到期日:"), 14, 0)
            self.option_expiry_date = QDateEdit()
            self.option_expiry_date.setDate(QDate.currentDate().addMonths(3))
            self.option_expiry_date.setCalendarPopup(True)
            self.option_expiry_date.setVisible(False)
            form_layout.addWidget(self.option_expiry_date, 14, 1)

            form_layout.addWidget(QLabel("期权类型:"), 15, 0)
            self.option_type_combo = QComboBox()
            self.option_type_combo.addItems(["看涨", "看跌"])
            self.option_type_combo.setCurrentIndex(0)
            self.option_type_combo.setVisible(False)
            form_layout.addWidget(self.option_type_combo, 15, 1)

            layout.addLayout(form_layout)

            # 连接资产类型变化信号
            self.asset_type_combo.currentTextChanged.connect(self.on_asset_type_changed)

            # 按钮
            button_layout = QHBoxLayout()

            cancel_btn = QPushButton("取消")
            cancel_btn.clicked.connect(self.reject)
            button_layout.addWidget(cancel_btn)

            create_btn = QPushButton("创建")
            create_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
            """)
            create_btn.clicked.connect(self.create_order)
            button_layout.addWidget(create_btn)

            layout.addLayout(button_layout)

        except Exception as e:
            logger.error(f"初始化创建订单对话框UI失败: {e}")

    def load_accounts(self, asset_type: AssetType = None):
        """根据资产类型加载账号列表"""
        try:
            self.account_combo.clear()
            self.account_combo.addItem("使用默认账号", "default")
            
            accounts = self.account_manager.get_all_accounts()
            
            if asset_type:
                account_type_map = {
                    AssetType.STOCK_A: "股票账户",
                    AssetType.STOCK_B: "股票账户",
                    AssetType.STOCK_HK: "股票账户",
                    AssetType.STOCK_US: "股票账户",
                    AssetType.STOCK_H: "股票账户",
                    AssetType.FUTURES: "期货账户",
                    AssetType.OPTION: "期权账户",
                    AssetType.CRYPTO: "加密货币账户",
                    AssetType.FOREX: "外汇账户",
                    AssetType.BOND: "债券账户",
                    AssetType.COMMODITY: "商品账户",
                    AssetType.INDEX: "指数账户",
                    AssetType.FUND: "基金账户",
                    AssetType.WARRANT: "权证账户"
                }
                target_account_type = account_type_map.get(asset_type)
                
                if target_account_type:
                    accounts = [a for a in accounts if a.account_type == target_account_type]
            
            for account in accounts:
                account_name = f"{account.account_name} ({account.institution_name})"
                self.account_combo.addItem(account_name, account.account_id)
            
            logger.info(f"加载了 {len(accounts)} 个账号，资产类型: {asset_type.value if asset_type else '全部'}")
        except Exception as e:
            logger.error(f"加载账号列表失败: {e}")
    
    def on_stock_code_text_changed(self, text: str):
        """股票代码输入变化时自动筛选"""
        try:
            # 清除之前的定时器
            if self.search_timer:
                self.search_timer.stop()
                self.search_timer = None
            
            # 如果输入为空，隐藏浮窗
            if not text.strip():
                self.hide_search_results_popup()
                return
            
            # 创建新的定时器，延迟300ms后执行搜索
            self.search_timer = QTimer()
            self.search_timer.setSingleShot(True)
            self.search_timer.timeout.connect(lambda: self.perform_auto_search(text.strip()))
            self.search_timer.start(300)
            
        except Exception as e:
            logger.error(f"自动筛选失败: {e}")
    
    def perform_auto_search(self, search_text: str):
        """执行自动搜索"""
        try:
            asset_type_text = self.asset_type_combo.currentText()
            asset_type_map = {
                "股票-A股": AssetType.STOCK_A,
                "股票-B股": AssetType.STOCK_B,
                "股票-港股": AssetType.STOCK_HK,
                "股票-美股": AssetType.STOCK_US,
                "股票-北交所": AssetType.STOCK_B,
                "期货": AssetType.FUTURES,
                "期权": AssetType.OPTION,
                "加密货币": AssetType.CRYPTO,
                "外汇": AssetType.FOREX,
                "债券": AssetType.BOND,
                "商品": AssetType.COMMODITY,
                "指数": AssetType.INDEX,
                "基金": AssetType.FUND,
                "权证": AssetType.WARRANT
            }
            asset_type = asset_type_map.get(asset_type_text, AssetType.STOCK_A)
            
            try:
                data_manager = self.service_container.resolve(UnifiedDataManager)
                asset_service = self.service_container.resolve(AssetService)
                
                # 执行搜索
                assets = self._perform_asset_search(data_manager, asset_service, search_text, asset_type)
                self.current_search_results = assets
                
                # 显示搜索结果浮窗
                self.show_search_results_popup(assets)
                
                logger.info(f"自动搜索完成，找到 {len(assets)} 个资产")
                
            except Exception as e:
                logger.error(f"执行自动搜索失败: {e}")
                self.hide_search_results_popup()
                
        except Exception as e:
            logger.error(f"自动搜索失败: {e}")
    
    def show_search_results_popup(self, assets: List[Dict[str, Any]]):
        """显示搜索结果浮窗"""
        try:
            # 如果浮窗已存在，先隐藏
            if self.search_results_popup:
                self.search_results_popup.close()
                self.search_results_popup = None
            
            # 如果没有结果，不显示浮窗
            if not assets or len(assets) == 0:
                return
            
            # 创建浮窗
            from PyQt5.QtWidgets import QFrame, QVBoxLayout
            
            self.search_results_popup = QFrame(self)
            self.search_results_popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)

            
            # 创建列表
            popup_layout = QVBoxLayout(self.search_results_popup)
            popup_layout.setContentsMargins(5, 5, 5, 5)
            popup_layout.setSpacing(2)
            
            results_list = QListWidget()

            results_list.setSelectionMode(QAbstractItemView.SingleSelection)
            results_list.itemClicked.connect(self.on_search_result_selected)
            
            # 添加搜索结果
            for asset in assets[:20]:
                display_text = asset.get('display', f"{asset.get('code', '')} {asset.get('name', '')}")
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, asset)
                results_list.addItem(item)
            
            popup_layout.addWidget(results_list)
            
            # 计算浮窗位置
            input_rect = self.stock_code_input.geometry()
            global_pos = self.stock_code_input.mapToGlobal(input_rect.bottomLeft())
            
            # 设置浮窗大小和位置
            self.search_results_popup.resize(input_rect.width(), min(200, 40 + len(assets[:20]) * 30))
            self.search_results_popup.move(global_pos)
            self.search_results_popup.show()
            
            logger.info(f"显示搜索结果浮窗，位置: {global_pos}")
            
        except Exception as e:
            logger.error(f"显示搜索结果浮窗失败: {e}")
    
    def hide_search_results_popup(self):
        """隐藏搜索结果浮窗"""
        try:
            if self.search_results_popup:
                self.search_results_popup.close()
                self.search_results_popup = None
        except Exception as e:
            logger.error(f"隐藏搜索结果浮窗失败: {e}")
    
    def on_search_result_selected(self, item: QListWidgetItem):
        """选择搜索结果"""
        try:
            asset = item.data(Qt.UserRole)
            if asset:
                self.stock_code_input.setText(asset.get('code', ''))
                self.hide_search_results_popup()
                logger.info(f"选择资产: {asset.get('code', '')} - {asset.get('name', '')}")
        except Exception as e:
            logger.error(f"选择搜索结果失败: {e}")
    
    def _perform_asset_search(self, data_manager: UnifiedDataManager, asset_service: AssetService, 
                            search_text: str, asset_type: AssetType) -> List[Dict[str, Any]]:
        """执行资产搜索（复用左侧面板逻辑）"""
        assets = []
        search_text = search_text.strip()
        
        try:
            # 1. 直接查询DuckDB数据库（参考左侧面板实现）
            try:
                import duckdb
                from pathlib import Path
                
                logger.info(f"直接查询DuckDB数据库: {asset_type.value}")
                
                # 获取数据库路径
                try:
                    from core.asset_database_manager import get_asset_separated_database_manager
                    asset_db_manager = get_asset_separated_database_manager()
                    db_path = asset_db_manager.get_database_path(asset_type)
                except Exception as e:
                    logger.warning(f"获取资产数据库路径失败: {e}，使用默认路径")
                    # 降级：使用默认路径
                    asset_type_str = asset_type.value.lower()
                    db_path = Path.cwd() / "cache" / "duckdb" / asset_type_str / f"{asset_type_str}_data.duckdb"
                    db_path = str(db_path)
                
                # 检查数据库文件是否存在
                if not Path(db_path).exists():
                    logger.warning(f"DuckDB文件不存在: {db_path}")
                else:
                    # 构建查询条件
                    query_conditions = []
                    params = []
                    query_conditions.append("asset_type = ?")
                    params.append(asset_type.value)
                    
                    if search_text:
                        query_conditions.append("(symbol LIKE ? OR name LIKE ?)")
                        params.append(f"%{search_text}%")
                        params.append(f"%{search_text}%")
                    
                    # 构建查询SQL
                    base_query = "SELECT symbol as code, name, market, industry, sector, asset_type, updated_at as update_time FROM asset_metadata"
                    if query_conditions:
                        query = f"{base_query} WHERE {' AND '.join(query_conditions)}"
                    else:
                        query = base_query
                    
                    query += " ORDER BY symbol"
                    
                    # 执行查询
                    with duckdb.connect(db_path) as conn:
                        # 检查表是否存在
                        table_check = "SHOW TABLES"
                        tables_result = conn.execute(table_check).fetchall()
                        table_names = [table[0] for table in tables_result]
                        
                        if 'asset_metadata' in table_names:
                            # 执行股票查询
                            asset_df = conn.execute(query, params).df()
                            
                            if not asset_df.empty:
                                # 转换为标准格式
                                for _, row in asset_df.iterrows():
                                    code = str(row.get('code', ''))
                                    name = str(row.get('name', ''))
                                    
                                    if code and code != 'nan' and code != 'None':
                                        display_text = f"{code} {name}" if name and name != 'nan' and name != 'None' else code
                                        asset_item = {
                                            'code': code,
                                            'name': name if name != 'nan' and name != 'None' else '',
                                            'market': str(row.get('market', '')),
                                            'industry': str(row.get('industry', '')),
                                            'sector': str(row.get('sector', '')),
                                            'display': display_text
                                        }
                                        assets.append(asset_item)
                                
                                return assets
                            else:
                                logger.info("DuckDB查询返回空结果")
                
            except ImportError:
                logger.debug("duckdb模块不可用，跳过直接查询")
            except Exception as e:
                logger.warning(f"直接查询DuckDB失败: {e}")
            
            # 2. 优先使用AssetService（更稳定的API）
            if asset_service:
                try:
                    logger.info(f"使用AssetService搜索资产: {asset_type.value}")
                    asset_list = asset_service.get_asset_list(asset_type, market='all')
                    
                    if asset_list and isinstance(asset_list, list) and len(asset_list) > 0:
                        # 应用搜索过滤
                        if search_text:
                            search_lower = search_text.lower()
                            filtered_assets = [
                                asset for asset in asset_list
                                if search_lower in asset.get('code', '').lower() or
                                   search_lower in asset.get('name', '').lower() or
                                   search_lower in str(asset.get('symbol', '')).lower()
                            ]
                        else:
                            filtered_assets = asset_list
                        
                        # 标准化格式
                        standardized_assets = []
                        for asset in filtered_assets:
                            code = str(asset.get('code', '') or asset.get('symbol', ''))
                            name = str(asset.get('name', ''))
                            
                            if code and code != 'nan' and code != 'None':
                                standardized_assets.append({
                                    'code': code,
                                    'name': name if name != 'nan' and name != 'None' else '',
                                    'market': str(asset.get('market', '')),
                                    'industry': str(asset.get('industry', '')),
                                    'sector': str(asset.get('sector', '')),
                                    'display': f"{code} {name}" if name and name != 'nan' and name != 'None' else code
                                })
                        
                        logger.info(f"AssetService搜索成功: {len(standardized_assets)} 个资产")
                        return standardized_assets
                        
                except Exception as e:
                    logger.warning(f"AssetService获取资产列表失败: {e}")
            
            # 3. 降级到UnifiedDataManager（修复参数格式）
            if data_manager:
                try:
                    logger.info(f"使用UnifiedDataManager搜索资产: {asset_type}")
                    
                    # 转换资产类型为字符串，确保兼容性
                    asset_type_str = asset_type.value.lower()
                    asset_df = data_manager.get_asset_list(
                        asset_type=asset_type_str, 
                        market='all'
                    )
                    
                    if asset_df is not None and not asset_df.empty:
                        # 应用搜索过滤
                        if search_text:
                            search_lower = search_text.lower()
                            # 查找包含搜索文本的列
                            search_columns = ['code', 'symbol', 'name']
                            search_conditions = []
                            
                            for col in search_columns:
                                if col in asset_df.columns:
                                    search_conditions.append(
                                        asset_df[col].astype(str).str.contains(search_lower, case=False, na=False)
                                    )
                            
                            if search_conditions:
                                # 合并所有搜索条件
                                combined_condition = search_conditions[0]
                                for condition in search_conditions[1:]:
                                    combined_condition = combined_condition | condition
                                
                                filtered_df = asset_df[combined_condition]
                            else:
                                filtered_df = asset_df
                        else:
                            filtered_df = asset_df
                        
                        # 转换为标准格式
                        for _, row in filtered_df.iterrows():
                            code = str(row.get('code', '') or row.get('symbol', ''))
                            name = str(row.get('name', ''))
                            
                            if code and code != 'nan' and code != 'None':
                                assets.append({
                                    'code': code,
                                    'name': name if name != 'nan' and name != 'None' else '',
                                    'market': str(row.get('market', '')),
                                    'industry': str(row.get('industry', '')),
                                    'sector': str(row.get('sector', '')),
                                    'display': f"{code} {name}" if name and name != 'nan' and name != 'None' else code
                                })
                        
                        logger.info(f"UnifiedDataManager搜索成功: {len(assets)} 个资产")
                        return assets
                    else:
                        logger.warning("UnifiedDataManager返回空DataFrame")
                        
                except Exception as e:
                    logger.warning(f"UnifiedDataManager获取资产列表失败: {e}")
            
            # 最后降级到默认数据（确保有数据可用）
            logger.info("使用默认资产列表")
            return self._get_default_assets(asset_type)
            
        except Exception as e:
            logger.error(f"执行资产搜索失败: {e}")
            # 即使出错也返回默认数据，确保UI有内容显示
            return self._get_default_assets(asset_type)
    
    def _get_default_assets(self, asset_type: AssetType) -> List[Dict[str, Any]]:
        """获取默认资产列表（降级方案）"""
        logger.info(f"使用默认资产列表: {asset_type.value}")
        
        default_assets = {
            AssetType.STOCK_A: [
                {'code': '000001', 'name': '平安银行', 'market': 'SZ', 'display': '000001 平安银行'},
                {'code': '000002', 'name': '万科A', 'market': 'SZ', 'display': '000002 万科A'},
                {'code': '600000', 'name': '浦发银行', 'market': 'SH', 'display': '600000 浦发银行'},
                {'code': '600036', 'name': '招商银行', 'market': 'SH', 'display': '600036 招商银行'},
            ],
            AssetType.FUTURES: [
                {'code': 'IF2401', 'name': '沪深300期货2401', 'market': 'CFFEX', 'display': 'IF2401 沪深300期货2401'},
                {'code': 'IH2401', 'name': '上证50期货2401', 'market': 'CFFEX', 'display': 'IH2401 上证50期货2401'},
                {'code': 'IC2401', 'name': '中证500期货2401', 'market': 'CFFEX', 'display': 'IC2401 中证500期货2401'},
            ],
            AssetType.CRYPTO: [
                {'code': 'BTC', 'name': 'Bitcoin', 'market': 'Binance', 'display': 'BTC Bitcoin'},
                {'code': 'ETH', 'name': 'Ethereum', 'market': 'Binance', 'display': 'ETH Ethereum'},
                {'code': 'BNB', 'name': 'Binance Coin', 'market': 'Binance', 'display': 'BNB Binance Coin'},
            ]
        }
        
        return default_assets.get(asset_type, [])
    
    @pyqtSlot(str)
    def on_asset_type_changed(self, asset_type_text: str):
        """资产类型变化处理"""
        try:
            asset_type_map = {
                "股票-A股": AssetType.STOCK_A,
                "股票-B股": AssetType.STOCK_B,
                "股票-港股": AssetType.STOCK_HK,
                "股票-美股": AssetType.STOCK_US,
                "股票-北交所": AssetType.STOCK_B,
                "期货": AssetType.FUTURES,
                "期权": AssetType.OPTION,
                "加密货币": AssetType.CRYPTO,
                "外汇": AssetType.FOREX,
                "债券": AssetType.BOND,
                "商品": AssetType.COMMODITY,
                "指数": AssetType.INDEX,
                "基金": AssetType.FUND,
                "权证": AssetType.WARRANT
            }
            asset_type = asset_type_map.get(asset_type_text, AssetType.STOCK_A)
            
            # 隐藏所有特殊参数
            self.futures_contract_input.setVisible(False)
            self.futures_month_combo.setVisible(False)
            self.futures_multiplier_spin.setVisible(False)
            self.futures_margin_spin.setVisible(False)
            self.option_strike_price_spin.setVisible(False)
            self.option_expiry_date.setVisible(False)
            self.option_type_combo.setVisible(False)

            # 根据资产类型显示相关参数
            if asset_type_text == "期货":
                self.futures_contract_input.setVisible(True)
                self.futures_month_combo.setVisible(True)
                self.futures_multiplier_spin.setVisible(True)
                self.futures_margin_spin.setVisible(True)
            elif asset_type_text == "期权":
                self.option_strike_price_spin.setVisible(True)
                self.option_expiry_date.setVisible(True)
                self.option_type_combo.setVisible(True)
            
            # 根据资产类型加载对应的账号列表
            self.load_accounts(asset_type)

        except Exception as e:
            logger.error(f"资产类型变化处理失败: {e}")

    def create_order(self):
        """创建订单"""
        try:
            stock_code = self.stock_code_input.text().strip()
            if not stock_code:
                QMessageBox.warning(self, '警告', '请输入股票代码')
                return

            asset_type_text = self.asset_type_combo.currentText()
            asset_type_map = {
                "股票-A股": AssetType.STOCK_A,
                "股票-B股": AssetType.STOCK_B,
                "股票-港股": AssetType.STOCK_HK,
                "股票-美股": AssetType.STOCK_US,
                "股票-北交所": AssetType.STOCK_B,
                "期货": AssetType.FUTURES,
                "期权": AssetType.OPTION,
                "加密货币": AssetType.CRYPTO,
                "外汇": AssetType.FOREX,
                "债券": AssetType.BOND,
                "商品": AssetType.COMMODITY,
                "指数": AssetType.INDEX,
                "基金": AssetType.FUND,
                "权证": AssetType.WARRANT
            }
            asset_type = asset_type_map.get(asset_type_text, AssetType.STOCK_A)
            
            # 验证资产代码是否有效
            try:
                data_manager = self.service_container.resolve(UnifiedDataManager)
                asset_service = self.service_container.resolve(AssetService)
                
                # 尝试获取资产信息以验证代码有效性
                asset_valid = False
                try:
                    asset_list = asset_service.get_asset_list(asset_type, market='all')
                    if asset_list:
                        for asset in asset_list:
                            if stock_code.upper() in [asset.get('code', '').upper(), 
                                                     asset.get('symbol', '').upper()]:
                                asset_valid = True
                                break
                except Exception as e:
                    logger.debug(f"验证资产列表失败: {e}")
                
                if not asset_valid:
                    try:
                        asset_df = data_manager.get_asset_list(asset_type=asset_type.value.lower(), market='all')
                        if asset_df is not None and not asset_df.empty:
                            if 'code' in asset_df.columns:
                                if stock_code.upper() in asset_df['code'].astype(str).str.upper().values:
                                    asset_valid = True
                            elif 'symbol' in asset_df.columns:
                                if stock_code.upper() in asset_df['symbol'].astype(str).str.upper().values:
                                    asset_valid = True
                    except Exception as e:
                        logger.debug(f"通过get_asset_list验证资产失败: {e}")
                
                if not asset_valid:
                    reply = QMessageBox.question(
                        self, '资产代码验证', 
                        f'资产代码 "{stock_code}" 未在系统中找到，可能无效。\n\n是否继续创建订单？',
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                    )
                    if reply == QMessageBox.No:
                        return
                        
            except Exception as e:
                logger.warning(f"资产代码验证失败，继续创建订单: {e}")

            order_type = OrderType.BUY if self.order_type_combo.currentText() == "买入" else OrderType.SELL
            category_text = self.order_category_combo.currentText()
            category_map = {
                "限价单": OrderCategory.LIMIT,
                "市价单": OrderCategory.MARKET,
                "止损单": OrderCategory.STOP,
                "止损限价单": OrderCategory.STOP_LIMIT
            }
            order_category = category_map.get(category_text, OrderCategory.LIMIT)

            order_quantity = self.order_quantity_spin.value()
            order_price = self.order_price_spin.value()
            stop_price = self.stop_price_spin.value() if self.stop_price_spin.value() > 0 else None

            # 根据资产类型读取特殊参数
            contract_multiplier = 1
            margin_ratio = 0.0
            strike_price = None
            expiry_date = None
            option_type = None

            if asset_type_text == "期货":
                contract_multiplier = self.futures_multiplier_spin.value()
                margin_ratio = self.futures_margin_spin.value() / 100.0  # 转换为小数
            elif asset_type_text == "期权":
                strike_price = self.option_strike_price_spin.value()
                expiry_date = self.option_expiry_date.date().toPyDate()
                option_type = self.option_type_combo.currentText()

            # 创建订单请求
            request = OrderRequest(
                strategy_id="manual",
                asset_type=asset_type,
                stock_code=stock_code,
                order_type=order_type,
                order_category=order_category,
                order_price=order_price,
                order_quantity=order_quantity,
                stop_price=stop_price,
                user_id="system",
                account_id=self.account_combo.currentData(),
                contract_multiplier=contract_multiplier,
                margin_ratio=margin_ratio,
                strike_price=strike_price,
                expiry_date=expiry_date,
                option_type=option_type
            )

            # 创建订单
            order = self.order_service.create_order(request)
            if order:
                QMessageBox.information(self, '成功', f'订单创建成功: {order.order_id}')
                self.accept()
            else:
                QMessageBox.warning(self, '失败', '订单创建失败')

        except Exception as e:
            logger.error(f"创建订单失败: {e}")
            QMessageBox.critical(self, '错误', f'创建订单失败: {str(e)}')


class ModifyOrderDialog(QDialog):
    """修改订单对话框"""

    def __init__(self, order: Order, order_service: OrderService, parent=None):
        super().__init__(parent)
        self.order = order
        self.order_service = order_service
        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        try:
            self.setWindowTitle("修改订单")
            self.setMinimumSize(400, 100)

            layout = QVBoxLayout(self)

            # 订单信息表单
            form_layout = QGridLayout()

            # 股票代码（只读）
            form_layout.addWidget(QLabel("股票代码:"), 0, 0)
            self.stock_code_label = QLabel(self.order.stock_code)
            self.stock_code_label.setStyleSheet("font-weight: bold; color: #333;")
            form_layout.addWidget(self.stock_code_label, 0, 1)

            # 订单数量
            form_layout.addWidget(QLabel("订单数量*:"), 1, 0)
            self.order_quantity_spin = QSpinBox()
            self.order_quantity_spin.setRange(100, 1000000)
            self.order_quantity_spin.setValue(self.order.order_quantity)
            self.order_quantity_spin.setSingleStep(100)
            form_layout.addWidget(self.order_quantity_spin, 1, 1)

            # 订单价格
            form_layout.addWidget(QLabel("订单价格*:"), 2, 0)
            self.order_price_spin = QDoubleSpinBox()
            self.order_price_spin.setRange(0.01, 1000000.0)
            self.order_price_spin.setValue(self.order.order_price)
            self.order_price_spin.setDecimals(2)
            self.order_price_spin.setSingleStep(0.01)
            form_layout.addWidget(self.order_price_spin, 2, 1)

            layout.addLayout(form_layout)

            # 按钮
            button_layout = QHBoxLayout()

            cancel_btn = QPushButton("取消")
            cancel_btn.clicked.connect(self.reject)
            button_layout.addWidget(cancel_btn)

            modify_btn = QPushButton("修改")
            modify_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f39c12;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #e67e22;
                }
            """)
            modify_btn.clicked.connect(self.modify_order)
            button_layout.addWidget(modify_btn)

            layout.addLayout(button_layout)

        except Exception as e:
            logger.error(f"初始化修改订单对话框UI失败: {e}")

    def modify_order(self):
        """修改订单"""
        try:
            new_quantity = self.order_quantity_spin.value()
            new_price = self.order_price_spin.value()

            success = self.order_service.modify_order(
                self.order.order_id,
                new_price=new_price,
                new_quantity=new_quantity
            )

            if success:
                QMessageBox.information(self, '成功', '订单修改成功')
                self.accept()
            else:
                QMessageBox.warning(self, '失败', '订单修改失败')

        except Exception as e:
            logger.error(f"修改订单失败: {e}")
            QMessageBox.critical(self, '错误', f'修改订单失败: {str(e)}')


class OrderDetailDialog(QDialog):
    """订单详情对话框"""

    def __init__(self, order: Order, parent=None):
        super().__init__(parent)
        self.order = order
        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        try:
            self.setWindowTitle("订单详情")
            self.setMinimumSize(300, 450)

            layout = QVBoxLayout(self)

            # 订单信息
            info_text = QTextEdit()
            info_text.setReadOnly(True)

            info = f"""
            <h2>订单信息</h2>
            <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
                <tr><td><b>订单ID:</b></td><td>{self.order.order_id}</td></tr>
                <tr><td><b>股票代码:</b></td><td>{self.order.stock_code}</td></tr>
                <tr><td><b>订单方向:</b></td><td>{'买入' if self.order.order_type == OrderType.BUY else '卖出'}</td></tr>
                <tr><td><b>订单数量:</b></td><td>{self.order.order_quantity}</td></tr>
                <tr><td><b>订单价格:</b></td><td>{self.order.order_price:.2f}</td></tr>
                <tr><td><b>订单状态:</b></td><td>{self.order.order_status.value}</td></tr>
                <tr><td><b>创建时间:</b></td><td>{self.order.create_time.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
                <tr><td><b>成交数量:</b></td><td>{self.order.filled_quantity}</td></tr>
                <tr><td><b>成交价格:</b></td><td>{f"{self.order.filled_price:.2f}" if self.order.filled_price > 0 else '-'}</td></tr>
                <tr><td><b>手续费:</b></td><td>{self.order.commission:.2f}</td></tr>
                <tr><td><b>策略ID:</b></td><td>{self.order.strategy_id}</td></tr>
                <tr><td><b>用户ID:</b></td><td>{self.order.user_id}</td></tr>
                <tr><td><b>账户ID:</b></td><td>{self.order.account_id}</td></tr>
            </table>
            """

            info_text.setHtml(info)
            layout.addWidget(info_text)

            # 关闭按钮
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(self.accept)
            layout.addWidget(close_btn)

        except Exception as e:
            logger.error(f"初始化订单详情对话框UI失败: {e}")
