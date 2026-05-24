#!/usr/bin/env python3
"""
数据导入向导对话框

【已废弃 - DEPRECATED】

此文件已被新的统一数据管理对话框替代：
- 新文件：data_management_dialog_unified.py
- 新类：UnifiedDataManagementDialog

本文件保留仅用于向后兼容性，将在未来版本中删除。
建议迁移到新的统一数据管理对话框。

原有功能：
- 对标Bloomberg Terminal的专业数据导入界面
- 分步骤的数据导入流程
- 支持多种数据源和配置选项

作者: FactorWeave-Quant团队
版本: 1.0 (已废弃)
废弃日期: 2026-05-13
"""

import warnings
warnings.warn(
    "DataImportWizardDialog is deprecated and will be removed in a future version. "
    "Use UnifiedDataManagementDialog from data_management_dialog_unified.py instead.",
    DeprecationWarning,
    stacklevel=2
)

import sys
import json
from loguru import logger
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox,
    QDateEdit, QTextEdit, QProgressBar, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QCheckBox, QGroupBox, QFrame, QSplitter, QScrollArea,
    QMessageBox, QFileDialog, QApplication
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QDate
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QPainter

from .base_dialog import BaseDialog

logger = logger


class DataImportWizardDialog(BaseDialog):
    """
    专业数据导入向导对话框

    对标Bloomberg Terminal的多步骤导入流程：
    1. 数据源选择
    2. 参数配置  
    3. 数据预览
    4. 导入执行
    """

    # 信号定义
    import_started = pyqtSignal(dict)  # 导入开始
    import_progress = pyqtSignal(int, str)  # 导入进度
    import_completed = pyqtSignal(dict)  # 导入完成

    def __init__(self, parent=None):
        super().__init__(
            parent,
            title="FactorWeave-Quant 专业数据导入系统",
            size=(1200, 800),
            settings_key="DataImportWizardDialog",
            modal=True
        )

        # 当前步骤
        self.current_step = 0
        self.total_steps = 4

        # 导入配置
        self.import_config = {
            'data_source': None,
            'data_type': None,
            'symbols': [],
            'date_range': {},
            'update_frequency': 'realtime',
            'storage_target': 'auto'
        }

        # 初始化UI
        self._init_ui()
        self._setup_styles()
        self._connect_signals()

        logger.info("数据导入向导对话框初始化完成")

    def _init_ui(self):
        """初始化用户界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        self._create_title_bar(main_layout)

        # 步骤指示器
        self._create_step_indicator(main_layout)

        # 主内容区域
        self._create_main_content(main_layout)

        # 底部按钮栏
        self._create_button_bar(main_layout)

    def _create_title_bar(self, parent_layout):
        """创建标题栏"""
        title_frame = QFrame()
        title_frame.setObjectName("titleFrame")
        title_frame.setFixedHeight(60)

        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(20, 0, 20, 0)

        # 图标和标题
        title_label = QLabel("专业数据导入系统")
        title_label.setObjectName("titleLabel")
        title_font = QFont("Microsoft YaHei", 16, QFont.Bold)
        title_label.setFont(title_font)

        subtitle_label = QLabel("对标Bloomberg Terminal的专业级数据导入解决方案")
        subtitle_label.setObjectName("subtitleLabel")
        subtitle_font = QFont("Microsoft YaHei", 10)
        subtitle_label.setFont(subtitle_font)

        title_vlayout = QVBoxLayout()
        title_vlayout.addWidget(title_label)
        title_vlayout.addWidget(subtitle_label)
        title_vlayout.setSpacing(2)

        title_layout.addLayout(title_vlayout)
        title_layout.addStretch()

        parent_layout.addWidget(title_frame)

    def _create_step_indicator(self, parent_layout):
        """创建步骤指示器"""
        step_frame = QFrame()
        step_frame.setObjectName("stepFrame")
        step_frame.setFixedHeight(80)

        step_layout = QHBoxLayout(step_frame)
        step_layout.setContentsMargins(40, 20, 40, 20)

        self.step_labels = []
        step_names = ["数据源选择", "参数配置", "数据预览", "开始导入"]

        for i, step_name in enumerate(step_names):
            # 步骤圆圈
            step_circle = QLabel(str(i + 1))
            step_circle.setObjectName(f"stepCircle_{i}")
            step_circle.setFixedSize(40, 40)
            step_circle.setAlignment(Qt.AlignCenter)
            step_circle.setStyleSheet(f"""
                QLabel#stepCircle_{i} {{
                    border: 2px solid #3d4152;
                    border-radius: 20px;
                    background-color: #2d3142;
                    color: #b8bcc8;
                    font-weight: bold;
                    font-size: 14px;
                }}
            """)

            # 步骤名称
            step_name_label = QLabel(step_name)
            step_name_label.setObjectName(f"stepName_{i}")
            step_name_label.setAlignment(Qt.AlignCenter)
            step_name_label.setStyleSheet(f"""
                QLabel#stepName_{i} {{
                    color: #b8bcc8;
                    font-size: 12px;
                    margin-top: 5px;
                }}
            """)

            # 步骤容器
            step_container = QVBoxLayout()
            step_container.addWidget(step_circle, 0, Qt.AlignCenter)
            step_container.addWidget(step_name_label, 0, Qt.AlignCenter)
            step_container.setSpacing(5)

            step_layout.addLayout(step_container)

            # 连接线（除了最后一个步骤）
            if i < len(step_names) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.HLine)
                line.setObjectName(f"stepLine_{i}")
                line.setStyleSheet(f"""
                    QFrame#stepLine_{i} {{
                        border: 1px solid #3d4152;
                        margin: 0 10px;
                    }}
                """)
                step_layout.addWidget(line, 1)

            self.step_labels.append((step_circle, step_name_label))

        parent_layout.addWidget(step_frame)

        # 更新当前步骤显示
        self._update_step_indicator()

    def _create_main_content(self, parent_layout):
        """创建主内容区域"""
        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")

        self.content_layout = QVBoxLayout(content_frame)
        self.content_layout.setContentsMargins(20, 20, 20, 20)

        # 创建各个步骤的内容页面
        self._create_step_pages()

        parent_layout.addWidget(content_frame, 1)

    def _create_step_pages(self):
        """创建各步骤页面"""
        # 步骤1: 数据源选择
        self.step1_widget = self._create_data_source_selection()

        # 步骤2: 参数配置
        self.step2_widget = self._create_parameter_configuration()

        # 步骤3: 数据预览
        self.step3_widget = self._create_data_preview()

        # 步骤4: 导入执行
        self.step4_widget = self._create_import_execution()

        # 添加到布局并隐藏
        self.step_widgets = [
            self.step1_widget, self.step2_widget,
            self.step3_widget, self.step4_widget
        ]

        for widget in self.step_widgets:
            self.content_layout.addWidget(widget)
            widget.hide()

        # 显示第一步
        self.step_widgets[0].show()

    def _create_data_source_selection(self):
        """创建数据源选择页面"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 页面标题
        title = QLabel("选择数据源类型")
        title.setObjectName("pageTitle")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        layout.addWidget(title)

        # 数据源类型选择
        source_group = QGroupBox("数据源类型")
        source_layout = QGridLayout(source_group)

        # 数据源选项
        data_sources = [
            ("stock", "股票数据", "沪深A股、港股、美股等全球股票市场"),
            ("bond", "债券数据", "国债、企业债、可转债等债券市场"),
            ("futures", "期货数据", "商品期货、金融期货等衍生品"),
            ("forex", "外汇数据", "主要货币对、人民币汇率等"),
            ("fund", "基金数据", "公募基金、私募基金、ETF等"),
            ("macro", "宏观数据", "GDP、CPI、PMI等宏观经济指标")
        ]

        self.source_buttons = {}
        for i, (key, name, desc) in enumerate(data_sources):
            row, col = i // 3, i % 3

            button = QPushButton(f"{name}\n{desc}")
            button.setObjectName(f"sourceButton_{key}")
            button.setFixedSize(250, 80)
            button.setCheckable(True)
            button.clicked.connect(lambda checked, k=key: self._select_data_source(k))

            source_layout.addWidget(button, row, col)
            self.source_buttons[key] = button

        layout.addWidget(source_group)

        # 数据提供商选择
        provider_group = QGroupBox("数据提供商")
        provider_layout = QHBoxLayout(provider_group)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "Wind万得 (专业版)",
            "Tushare (开源版)",
            "东方财富 (免费版)",
            "同花顺 (iFind)",
            "聚宽 (JoinQuant)",
            "自定义数据源"
        ])
        self.provider_combo.setFixedWidth(200)

        provider_layout.addWidget(QLabel("选择数据提供商:"))
        provider_layout.addWidget(self.provider_combo)
        provider_layout.addStretch()

        layout.addWidget(provider_group)
        layout.addStretch()

        return widget

    def _create_parameter_configuration(self):
        """创建参数配置页面"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 页面标题
        title = QLabel("配置导入参数")
        title.setObjectName("pageTitle")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        layout.addWidget(title)

        # 创建滚动区域
        scroll = QScrollArea()
        scroll_widget = QFrame()
        scroll_layout = QVBoxLayout(scroll_widget)

        # API配置组
        api_group = QGroupBox("API配置")
        api_layout = QGridLayout(api_group)

        api_layout.addWidget(QLabel("API密钥:"), 0, 0)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("请输入API密钥")
        api_layout.addWidget(self.api_key_edit, 0, 1)

        api_layout.addWidget(QLabel("服务器地址:"), 1, 0)
        self.server_edit = QLineEdit()
        self.server_edit.setText("https://api.example.com")
        api_layout.addWidget(self.server_edit, 1, 1)

        test_button = QPushButton("测试连接")
        test_button.clicked.connect(self._test_connection)
        api_layout.addWidget(test_button, 0, 2)

        scroll_layout.addWidget(api_group)

        # 数据范围配置
        range_group = QGroupBox("数据范围")
        range_layout = QGridLayout(range_group)

        range_layout.addWidget(QLabel("开始日期:"), 0, 0)
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addYears(-1))
        self.start_date.setCalendarPopup(True)
        range_layout.addWidget(self.start_date, 0, 1)

        range_layout.addWidget(QLabel("结束日期:"), 0, 2)
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        range_layout.addWidget(self.end_date, 0, 3)

        range_layout.addWidget(QLabel("股票列表:"), 1, 0)
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["全部A股", "沪深300", "中证500", "自定义列表"])
        range_layout.addWidget(self.symbol_combo, 1, 1)

        symbol_button = QPushButton("选择股票")
        symbol_button.clicked.connect(self._select_symbols)
        range_layout.addWidget(symbol_button, 1, 2)

        scroll_layout.addWidget(range_group)

        # 更新配置
        update_group = QGroupBox("更新配置")
        update_layout = QGridLayout(update_group)

        update_layout.addWidget(QLabel("更新频率:"), 0, 0)
        self.frequency_combo = QComboBox()
        self.frequency_combo.addItems([
            "实时更新", "1分钟", "5分钟", "15分钟",
            "30分钟", "1小时", "每日", "手动更新"
        ])
        update_layout.addWidget(self.frequency_combo, 0, 1)

        update_layout.addWidget(QLabel("存储目标:"), 1, 0)
        self.storage_combo = QComboBox()
        self.storage_combo.addItems([
            "智能路由 (推荐)", "SQLite数据库", "DuckDB数据库", "内存缓存"
        ])
        update_layout.addWidget(self.storage_combo, 1, 1)

        scroll_layout.addWidget(update_group)

        # 高级选项
        advanced_group = QGroupBox("高级选项")
        advanced_layout = QVBoxLayout(advanced_group)

        self.enable_cache_cb = QCheckBox("启用多级缓存")
        self.enable_cache_cb.setChecked(True)
        advanced_layout.addWidget(self.enable_cache_cb)

        self.enable_compression_cb = QCheckBox("启用数据压缩")
        self.enable_compression_cb.setChecked(True)
        advanced_layout.addWidget(self.enable_compression_cb)

        self.enable_validation_cb = QCheckBox("启用数据验证")
        self.enable_validation_cb.setChecked(True)
        advanced_layout.addWidget(self.enable_validation_cb)

        scroll_layout.addWidget(advanced_group)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        return widget

    def _create_data_preview(self):
        """创建数据预览页面"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 页面标题
        title = QLabel("数据预览")
        title.setObjectName("pageTitle")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        layout.addWidget(title)

        # 预览信息
        info_layout = QHBoxLayout()

        self.preview_info = QLabel("点击\"▶️刷新预览\"获取数据样本")
        info_layout.addWidget(self.preview_info)

        refresh_button = QPushButton("▶️刷新预览")
        refresh_button.clicked.connect(self._refresh_preview)
        info_layout.addWidget(refresh_button)

        layout.addLayout(info_layout)

        # 预览表格
        self.preview_table = QTableWidget()
        self.preview_table.setAlternatingRowColors(True)
        layout.addWidget(self.preview_table)

        # 统计信息
        stats_group = QGroupBox("数据统计")
        stats_layout = QGridLayout(stats_group)

        self.stats_labels = {}
        stats_items = [
            ("total_records", "总记录数:"),
            ("date_range", "日期范围:"),
            ("data_quality", "数据质量:"),
            ("estimated_size", "预估大小:")
        ]

        for i, (key, label) in enumerate(stats_items):
            stats_layout.addWidget(QLabel(label), i // 2, (i % 2) * 2)
            value_label = QLabel("--")
            value_label.setObjectName(f"stats_{key}")
            stats_layout.addWidget(value_label, i // 2, (i % 2) * 2 + 1)
            self.stats_labels[key] = value_label

        layout.addWidget(stats_group)

        return widget

    def _create_import_execution(self):
        """创建导入执行页面"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 页面标题
        title = QLabel("开始导入")
        title.setObjectName("pageTitle")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        layout.addWidget(title)

        # 导入配置摘要
        summary_group = QGroupBox("导入配置摘要")
        summary_layout = QVBoxLayout(summary_group)

        self.summary_text = QTextEdit()
        self.summary_text.setMaximumHeight(150)
        self.summary_text.setReadOnly(True)
        summary_layout.addWidget(self.summary_text)

        layout.addWidget(summary_group)

        # 进度显示
        progress_group = QGroupBox("导入进度")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("准备就绪，点击开始导入")
        progress_layout.addWidget(self.progress_label)

        layout.addWidget(progress_group)

        # 实时日志
        log_group = QGroupBox("实时日志")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group)

        return widget

    def _create_button_bar(self, parent_layout):
        """创建底部按钮栏"""
        button_frame = QFrame()
        button_frame.setObjectName("buttonFrame")
        button_frame.setFixedHeight(60)

        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(20, 10, 20, 10)

        # 左侧按钮
        self.prev_button = QPushButton("< 上一步")
        self.prev_button.setEnabled(False)
        self.prev_button.clicked.connect(self._prev_step)

        # 右侧按钮
        button_layout.addWidget(self.prev_button)
        button_layout.addStretch()

        self.next_button = QPushButton("下一步 >")
        self.next_button.clicked.connect(self._next_step)

        self.start_button = QPushButton("开始导入")
        self.start_button.setVisible(False)
        self.start_button.clicked.connect(self._start_import)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.next_button)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.cancel_button)

        parent_layout.addWidget(button_frame)

    def _setup_styles(self):
        """设置样式"""
        self.setStyleSheet("""
            /* 主对话框样式 */
            QDialog {
                background-color: #1a1d29;
                color: #ffffff;
            }
            
            /* 标题栏样式 */
            QFrame#titleFrame {
                background-color: #252837;
                border-bottom: 2px solid #ff6b35;
            }
            
            QLabel#titleLabel {
                color: #ffffff;
            }
            
            QLabel#subtitleLabel {
                color: #b8bcc8;
            }
            
            /* 步骤指示器样式 */
            QFrame#stepFrame {
                background-color: #2d3142;
                border-bottom: 1px solid #3d4152;
            }
            
            /* 内容区域样式 */
            QFrame#contentFrame {
                background-color: #1a1d29;
            }
            
            QLabel#pageTitle {
                color: #ff6b35;
                margin-bottom: 20px;
            }
            
            /* 按钮栏样式 */
            QFrame#buttonFrame {
                background-color: #252837;
                border-top: 1px solid #3d4152;
            }
            
            /* 组件样式 */
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3d4152;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                color: #ffffff;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #ff6b35;
            }
            
            QPushButton {
                background-color: #4dabf7;
                border: none;
                border-radius: 4px;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #339af0;
            }
            
            QPushButton:pressed {
                background-color: #1971c2;
            }
            
            QPushButton:disabled {
                background-color: #3d4152;
                color: #6c757d;
            }
            
            QPushButton:checked {
                background-color: #ff6b35;
            }
            
            QLineEdit, QComboBox, QDateEdit {
                background-color: #2d3142;
                border: 1px solid #3d4152;
                border-radius: 4px;
                padding: 6px;
                color: #ffffff;
            }
            
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
                border-color: #ff6b35;
            }
            
            QTableWidget {
                background-color: #2d3142;
                alternate-background-color: #252837;
                gridline-color: #3d4152;
                color: #ffffff;
            }
            
            QHeaderView::section {
                background-color: #252837;
                color: #ffffff;
                border: 1px solid #3d4152;
                padding: 6px;
            }
            
            QTextEdit {
                background-color: #2d3142;
                border: 1px solid #3d4152;
                border-radius: 4px;
                color: #ffffff;
            }
            
            QProgressBar {
                border: 1px solid #3d4152;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
            }
            
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 3px;
            }
            
            QCheckBox {
                color: #ffffff;
            }
            
            QCheckBox::indicator:checked {
                background-color: #ff6b35;
                border: 1px solid #ff6b35;
            }
        """)

    def _connect_signals(self):
        """连接信号"""
        pass

    def _select_data_source(self, source_type):
        """选择数据源类型"""
        # 取消其他按钮的选中状态
        for key, button in self.source_buttons.items():
            if key != source_type:
                button.setChecked(False)

        self.import_config['data_type'] = source_type
        logger.info(f"选择数据源类型: {source_type}")

    def _test_connection(self):
        """测试数据源连接"""
        api_key = self.api_key_edit.text()
        server = self.server_edit.text()

        if not api_key:
            QMessageBox.warning(self, "警告", "请输入API密钥")
            return

        # 模拟连接测试
        QMessageBox.information(self, "连接测试", "连接测试成功！")

    def _select_symbols(self):
        """选择股票代码"""
        # 这里可以打开股票选择对话框
        QMessageBox.information(self, "股票选择", "股票选择功能开发中...")

    def _refresh_preview(self):
        """刷新数据预览"""
        # 模拟数据预览
        self.preview_table.setRowCount(10)
        self.preview_table.setColumnCount(6)
        self.preview_table.setHorizontalHeaderLabels([
            "股票代码", "股票名称", "最新价", "涨跌幅", "成交量", "成交额"
        ])

        # 填充示例数据
        sample_data = [
            ["000001", "平安银行", "10.25", "+2.1%", "1,234,567", "12.65M"],
            ["000002", "万科A", "8.76", "-1.2%", "987,654", "8.63M"],
            ["000858", "五粮液", "128.50", "+0.8%", "456,789", "58.72M"],
        ]

        for row, data in enumerate(sample_data):
            for col, value in enumerate(data):
                item = QTableWidgetItem(value)
                self.preview_table.setItem(row, col, item)

        # 更新统计信息
        self.stats_labels['total_records'].setText("1,234,567")
        self.stats_labels['date_range'].setText("2020-01-01 ~ 2025-08-23")
        self.stats_labels['data_quality'].setText("99.8%")
        self.stats_labels['estimated_size'].setText("2.5 GB")

        self.preview_info.setText("数据预览已更新 (显示前10条记录)")

    def _update_step_indicator(self):
        """更新步骤指示器"""
        for i, (circle, name) in enumerate(self.step_labels):
            if i < self.current_step:
                # 已完成步骤
                circle.setStyleSheet(f"""
                    QLabel#stepCircle_{i} {{
                        border: 2px solid #28a745;
                        border-radius: 20px;
                        background-color: #28a745;
                        color: #ffffff;
                        font-weight: bold;
                        font-size: 14px;
                    }}
                """)
                name.setStyleSheet(f"""
                    QLabel#stepName_{i} {{
                        color: #28a745;
                        font-size: 12px;
                        font-weight: bold;
                        margin-top: 5px;
                    }}
                """)
            elif i == self.current_step:
                # 当前步骤
                circle.setStyleSheet(f"""
                    QLabel#stepCircle_{i} {{
                        border: 2px solid #ff6b35;
                        border-radius: 20px;
                        background-color: #ff6b35;
                        color: #ffffff;
                        font-weight: bold;
                        font-size: 14px;
                    }}
                """)
                name.setStyleSheet(f"""
                    QLabel#stepName_{i} {{
                        color: #ff6b35;
                        font-size: 12px;
                        font-weight: bold;
                        margin-top: 5px;
                    }}
                """)
            else:
                # 未完成步骤
                circle.setStyleSheet(f"""
                    QLabel#stepCircle_{i} {{
                        border: 2px solid #3d4152;
                        border-radius: 20px;
                        background-color: #2d3142;
                        color: #b8bcc8;
                        font-weight: bold;
                        font-size: 14px;
                    }}
                """)
                name.setStyleSheet(f"""
                    QLabel#stepName_{i} {{
                        color: #b8bcc8;
                        font-size: 12px;
                        margin-top: 5px;
                    }}
                """)

    def _prev_step(self):
        """上一步"""
        if self.current_step > 0:
            self.step_widgets[self.current_step].hide()
            self.current_step -= 1
            self.step_widgets[self.current_step].show()
            self._update_step_indicator()
            self._update_buttons()

    def _next_step(self):
        """下一步"""
        if self._validate_current_step():
            if self.current_step < self.total_steps - 1:
                self.step_widgets[self.current_step].hide()
                self.current_step += 1
                self.step_widgets[self.current_step].show()
                self._update_step_indicator()
                self._update_buttons()

                # 如果是最后一步，更新配置摘要
                if self.current_step == self.total_steps - 1:
                    self._update_summary()

    def _validate_current_step(self):
        """验证当前步骤"""
        if self.current_step == 0:
            # 验证数据源选择
            if not self.import_config.get('data_type'):
                QMessageBox.warning(self, "验证失败", "请选择数据源类型")
                return False
        elif self.current_step == 1:
            # 验证参数配置
            if not self.api_key_edit.text():
                QMessageBox.warning(self, "验证失败", "请输入API密钥")
                return False

        return True

    def _update_buttons(self):
        """更新按钮状态"""
        self.prev_button.setEnabled(self.current_step > 0)

        if self.current_step == self.total_steps - 1:
            self.next_button.setVisible(False)
            self.start_button.setVisible(True)
        else:
            self.next_button.setVisible(True)
            self.start_button.setVisible(False)

    def _update_summary(self):
        """更新配置摘要"""
        summary = f"""
数据源类型: {self.import_config.get('data_type', '未选择')}
数据提供商: {self.provider_combo.currentText()}
日期范围: {self.start_date.date().toString()} ~ {self.end_date.date().toString()}
股票范围: {self.symbol_combo.currentText()}
更新频率: {self.frequency_combo.currentText()}
存储目标: {self.storage_combo.currentText()}

高级选项:
- 多级缓存: {'启用' if self.enable_cache_cb.isChecked() else '禁用'}
- 数据压缩: {'启用' if self.enable_compression_cb.isChecked() else '禁用'}
- 数据验证: {'启用' if self.enable_validation_cb.isChecked() else '禁用'}
        """
        self.summary_text.setPlainText(summary.strip())

    def _start_import(self):
        """开始导入"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("正在初始化导入任务...")

        # 禁用按钮
        self.start_button.setEnabled(False)
        self.cancel_button.setText("停止导入")

        # 模拟导入过程
        self._simulate_import()

    def _simulate_import(self):
        """模拟导入过程"""
        self.import_timer = QTimer()
        self.import_progress_value = 0

        def update_progress():
            self.import_progress_value += 2
            self.progress_bar.setValue(self.import_progress_value)

            if self.import_progress_value <= 100:
                messages = [
                    "连接数据源...",
                    "验证API密钥...",
                    "获取股票列表...",
                    "开始下载数据...",
                    "处理K线数据...",
                    "存储到数据库...",
                    "更新索引...",
                    "导入完成!"
                ]

                message_index = min(self.import_progress_value // 15, len(messages) - 1)
                self.progress_label.setText(messages[message_index])

                # 添加日志
                if self.import_progress_value % 10 == 0:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    log_message = f"[{timestamp}] {messages[message_index]}"
                    self.log_text.append(log_message)

            if self.import_progress_value >= 100:
                self.import_timer.stop()
                self.progress_label.setText("导入完成! 共导入 1,234,567 条记录")
                self.start_button.setText("完成")
                self.start_button.setEnabled(True)
                self.start_button.clicked.disconnect()
                self.start_button.clicked.connect(self.accept)

        self.import_timer.timeout.connect(update_progress)
        self.import_timer.start(100)  # 每100ms更新一次


def main():
    """测试函数"""
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    dialog = DataImportWizardDialog()
    dialog.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
