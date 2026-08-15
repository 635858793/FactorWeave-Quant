#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一数据管理对话框

整合了原有的6个数据管理相关对话框，提供一站式数据管理解决方案：
- 数据导入（支持向导模式）
- 导入历史查看
- 数据导出（基础+高级）
- 数据库管理（备份、清理、优化）
- 数据统计和概览
- 数据源管理
- 数据质量监控

作者: FactorWeave-Quant团队
版本: 2.0
更新日期: 2026-05-13

废弃文件（向后兼容）：
- data_management_dialog.py
- data_import_wizard_dialog.py
- import_history_dialog.py
- database_admin_dialog.py
- data_export_dialog.py
- advanced_data_export_dialog.py
"""

import sys
import os
import json
import warnings
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget,
    QLabel, QPushButton, QFrame, QSplitter, QScrollArea,
    QTableWidget, QTableWidgetItem, QTextEdit, QProgressBar,
    QGroupBox, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QApplication, QHeaderView, QComboBox, QLineEdit,
    QDateEdit, QSpinBox, QCheckBox, QListWidget, QListWidgetItem,
    QMessageBox, QMenu, QToolBar, QAction, QStatusBar,
    QDialogButtonBox, QFormLayout, QStackedWidget,
    QFileDialog, QInputDialog, QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QDate, QSize
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon

from loguru import logger

from .base_dialog import BaseDialog

logger = logger.bind(module=__name__)


class DataImportThread(QThread):
    """数据导入工作线程"""
    
    progress_updated = pyqtSignal(int, str)
    import_completed = pyqtSignal(str)
    import_failed = pyqtSignal(str)
    
    def __init__(self, import_config: Dict[str, Any]):
        super().__init__()
        self.import_config = import_config
    
    def run(self):
        try:
            self.progress_updated.emit(5, "正在初始化数据导入引擎...")

            data_type = self.import_config.get('data_type', '股票数据')
            start_date = self.import_config.get('start_date', '')
            end_date = self.import_config.get('end_date', '')
            stock_range = self.import_config.get('stock_range', '')

            asset_type_map = {
                '股票数据': 'stock_a',
                '债券数据': 'bond',
                '期货数据': 'future',
                '外汇数据': 'forex',
                '基金数据': 'fund',
                '宏观数据': 'macro',
            }
            asset_type = asset_type_map.get(data_type, 'stock_a')

            self.progress_updated.emit(15, "获取数据提供器...")

            from core.real_data_provider import get_real_data_provider
            provider = get_real_data_provider()

            self.progress_updated.emit(25, "获取股票列表...")

            try:
                stocks = provider.get_stock_list(asset_type=asset_type)
            except Exception:
                stocks = []
                self.progress_updated.emit(25, "使用默认股票列表...")

            if not stocks:
                default_stocks = [
                    {"code": "000001", "name": "平安银行"},
                    {"code": "000002", "name": "万科A"},
                    {"code": "600000", "name": "浦发银行"},
                    {"code": "600036", "name": "招商银行"},
                ]
                stocks = default_stocks

            total_count = len(stocks)
            self.progress_updated.emit(30, f"共 {total_count} 只股票待导入")

            imported_count = 0
            failed_count = 0

            for idx, stock in enumerate(stocks):
                # R248 修复：检查中断请求，支持关闭对话框时安全停止线程
                if self.isInterruptionRequested():
                    break
                try:
                    code = stock.get('code', stock.get('stock_code', ''))
                    name = stock.get('name', code)

                    progress_pct = 30 + int(65 * (idx + 1) / total_count)
                    self.progress_updated.emit(progress_pct, f"导入 {code} {name} ({idx + 1}/{total_count})...")

                    import_config = {
                        'symbol': code,
                        'start_date': start_date,
                        'end_date': end_date,
                        'asset_type': asset_type,
                    }
                    provider.import_stock_data(**import_config)
                    imported_count += 1
                except Exception as e:
                    failed_count += 1
                    logger.warning(f"导入股票 {stock} 失败: {e}")

            summary = f"导入完成: 成功 {imported_count}, 失败 {failed_count}"
            self.progress_updated.emit(100, summary)
            self.import_completed.emit(summary)
        except Exception as e:
            logger.error(f"数据导入失败: {e}")
            self.import_failed.emit(str(e))


class DataExportThread(QThread):
    """数据导出工作线程"""
    
    progress_updated = pyqtSignal(int, str)
    export_completed = pyqtSignal(str)
    export_failed = pyqtSignal(str)
    
    def __init__(self, export_config: Dict[str, Any]):
        super().__init__()
        self.export_config = export_config
    
    def run(self):
        """执行导出"""
        try:
            import pandas as pd
            
            self.progress_updated.emit(10, "准备导出数据...")
            
            export_format = self.export_config.get('format', 'Excel')
            file_path = self.export_config.get('file_path', '')
            data = self.export_config.get('data', pd.DataFrame())
            
            self.progress_updated.emit(30, f"导出为{export_format}格式...")
            
            if export_format == 'Excel':
                data.to_excel(file_path, index=False)
            elif export_format == 'CSV':
                data.to_csv(file_path, index=False, encoding='utf-8-sig')
            elif export_format == 'JSON':
                data.to_json(file_path, orient='records', date_format='iso')
            elif export_format == 'Parquet':
                data.to_parquet(file_path)
            
            self.progress_updated.emit(100, "导出完成")
            self.export_completed.emit(file_path)
        except Exception as e:
            logger.error(f"数据导出失败: {e}")
            self.export_failed.emit(str(e))


class UnifiedDataManagementDialog(BaseDialog):
    """
    统一数据管理对话框
    
    整合所有数据管理功能，包括：
    - 数据导入（向导模式）
    - 导入历史
    - 数据导出（基础+高级）
    - 数据库管理
    - 数据统计
    - 数据源管理
    """
    
    data_imported = pyqtSignal(dict)
    data_exported = pyqtSignal(str)
    database_updated = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(
            parent,
            title="统一数据管理中心",
            size=(1400, 900),
            settings_key="UnifiedDataManagementDialog",
            modal=False,
        )
        self.setWindowIcon(self.style().standardIcon(self.style().SP_DialogApplyButton))
        
        self.current_section = 0
        self.setup_ui()
        self.setup_connections()
        self.load_statistics()
        
        logger.info("统一数据管理对话框初始化完成")
    
    def setup_ui(self):
        """设置UI"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self._create_sidebar(main_layout)
        self._create_content_area(main_layout)
    
    def _create_sidebar(self, parent_layout):
        """创建侧边栏导航"""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("""
            QFrame#sidebar {
                background-color: #1a1d29;
                border-right: 2px solid #3d4152;
            }
        """)
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)
        sidebar_layout.setSpacing(5)
        
        title_label = QLabel("数据管理中心")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            color: #ff6b35;
            font-size: 16px;
            font-weight: bold;
            padding: 10px;
        """)
        sidebar_layout.addWidget(title_label)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #3d4152;")
        sidebar_layout.addWidget(separator)
        
        self.nav_buttons = []
        nav_items = [
            ("📊", "数据概览", "overview"),
            ("📥", "数据导入", "import"),
            ("📜", "导入历史", "history"),
            ("📤", "数据导出", "export"),
            ("🗄️", "数据库管理", "database"),
            ("🔗", "数据源管理", "sources"),
            ("📈", "数据质量", "quality"),
        ]
        
        for icon, text, section_id in nav_items:
            btn = self._create_nav_button(icon, text, section_id)
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)
        
        sidebar_layout.addStretch()
        
        version_label = QLabel("v2.0")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #6c757d; font-size: 11px; padding: 5px;")
        sidebar_layout.addWidget(version_label)
        
        parent_layout.addWidget(sidebar)
        
        self.nav_buttons[0].click()
    
    def _create_nav_button(self, icon: str, text: str, section_id: str) -> QPushButton:
        """创建导航按钮"""
        btn = QPushButton(f"{icon}  {text}")
        btn.setObjectName(f"nav_{section_id}")
        btn.setFixedHeight(40)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #b8bcc8;
                text-align: left;
                padding-left: 20px;
                border: none;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2d3142;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #ff6b35;
                color: #ffffff;
                font-weight: bold;
            }
        """)
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self._switch_section(section_id))
        btn.section_id = section_id
        return btn
    
    def _create_content_area(self, parent_layout):
        """创建内容区域"""
        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        content_frame.setStyleSheet("""
            QFrame#contentFrame {
                background-color: #252837;
            }
        """)
        
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.stacked_widget = QStackedWidget()
        
        self.overview_widget = self._create_overview_section()
        self.import_widget = self._create_import_section()
        self.history_widget = self._create_history_section()
        self.export_widget = self._create_export_section()
        self.database_widget = self._create_database_section()
        self.sources_widget = self._create_sources_section()
        self.quality_widget = self._create_quality_section()
        
        self.stacked_widget.addWidget(self.overview_widget)
        self.stacked_widget.addWidget(self.import_widget)
        self.stacked_widget.addWidget(self.history_widget)
        self.stacked_widget.addWidget(self.export_widget)
        self.stacked_widget.addWidget(self.database_widget)
        self.stacked_widget.addWidget(self.sources_widget)
        self.stacked_widget.addWidget(self.quality_widget)
        
        content_layout.addWidget(self.stacked_widget)
        
        parent_layout.addWidget(content_frame)
    
    def _switch_section(self, section_id: str):
        """切换功能模块"""
        section_map = {
            "overview": 0,
            "import": 1,
            "history": 2,
            "export": 3,
            "database": 4,
            "sources": 5,
            "quality": 6,
        }
        
        for btn in self.nav_buttons:
            btn.setChecked(btn.section_id == section_id)
        
        self.stacked_widget.setCurrentIndex(section_map.get(section_id, 0))
        
        if section_id == "overview":
            self.load_statistics()
        elif section_id == "history":
            self.load_import_history()
    
    def _create_overview_section(self) -> QWidget:
        """创建数据概览模块"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("📊 数据概览")
        title.setStyleSheet("color: #ff6b35; font-size: 20px; font-weight: bold; padding: 10px 0;")
        layout.addWidget(title)
        
        stats_grid = QGridLayout()
        stats_grid.setSpacing(15)
        
        stat_cards = [
            ("📥", "总导入次数", "0", "#4dabf7"),
            ("✅", "成功导入", "0", "#28a745"),
            ("❌", "失败次数", "0", "#dc3545"),
            ("📤", "总导出次数", "0", "#ffc107"),
            ("🗄️", "数据库数量", "0", "#17a2b8"),
            ("📈", "数据质量评分", "0%", "#6f42c1"),
        ]
        
        for i, (icon, label, value, color) in enumerate(stat_cards):
            card = self._create_stat_card(icon, label, value, color)
            stats_grid.addWidget(card, i // 3, i % 3)
        
        layout.addLayout(stats_grid)
        
        recent_group = QGroupBox("最近活动")
        recent_layout = QVBoxLayout(recent_group)
        
        self.recent_list = QListWidget()
        self.recent_list.setStyleSheet("""
            QListWidget {
                background-color: #1a1d29;
                border: 1px solid #3d4152;
                border-radius: 4px;
                color: #ffffff;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3d4152;
            }
        """)
        recent_layout.addWidget(self.recent_list)
        
        layout.addWidget(recent_group)
        
        layout.addStretch()
        return widget
    
    def _create_stat_card(self, icon: str, label: str, value: str, color: str) -> QFrame:
        """创建统计卡片"""
        card = QFrame()
        card.setFixedHeight(100)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #1a1d29;
                border: 2px solid {color};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(5)
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 24px;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)
        
        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(value_label)
        
        label_widget = QLabel(label)
        label_widget.setStyleSheet("color: #b8bcc8; font-size: 12px;")
        label_widget.setAlignment(Qt.AlignCenter)
        layout.addWidget(label_widget)
        
        card.value_label = value_label
        return card
    
    def _create_import_section(self) -> QWidget:
        """创建数据导入模块（向导模式）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("📥 数据导入")
        title.setStyleSheet("color: #ff6b35; font-size: 20px; font-weight: bold; padding: 10px 0;")
        layout.addWidget(title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        data_source_group = QGroupBox("数据源选择")
        source_layout = QGridLayout(data_source_group)
        
        source_layout.addWidget(QLabel("数据类型:"), 0, 0)
        self.import_type_combo = QComboBox()
        self.import_type_combo.addItems([
            "股票数据", "债券数据", "期货数据", 
            "外汇数据", "基金数据", "宏观数据"
        ])
        source_layout.addWidget(self.import_type_combo, 0, 1)
        
        source_layout.addWidget(QLabel("数据提供商:"), 1, 0)
        self.import_provider_combo = QComboBox()
        self.import_provider_combo.addItems([
            "Tushare", "东方财富", "同花顺", "聚宽", "自定义"
        ])
        source_layout.addWidget(self.import_provider_combo, 1, 1)
        
        source_layout.addWidget(QLabel("API密钥:"), 2, 0)
        self.import_api_key_edit = QLineEdit()
        self.import_api_key_edit.setEchoMode(QLineEdit.Password)
        self.import_api_key_edit.setPlaceholderText("请输入API密钥")
        source_layout.addWidget(self.import_api_key_edit, 2, 1)
        
        test_conn_btn = QPushButton("测试连接")
        test_conn_btn.clicked.connect(self._test_import_connection)
        source_layout.addWidget(test_conn_btn, 2, 2)
        
        scroll_layout.addWidget(data_source_group)
        
        range_group = QGroupBox("数据范围")
        range_layout = QGridLayout(range_group)
        
        range_layout.addWidget(QLabel("开始日期:"), 0, 0)
        self.import_start_date = QDateEdit()
        self.import_start_date.setDate(QDate.currentDate().addYears(-1))
        self.import_start_date.setCalendarPopup(True)
        range_layout.addWidget(self.import_start_date, 0, 1)
        
        range_layout.addWidget(QLabel("结束日期:"), 0, 2)
        self.import_end_date = QDateEdit()
        self.import_end_date.setDate(QDate.currentDate())
        self.import_end_date.setCalendarPopup(True)
        range_layout.addWidget(self.import_end_date, 0, 3)
        
        range_layout.addWidget(QLabel("股票范围:"), 1, 0)
        self.import_stock_range_combo = QComboBox()
        self.import_stock_range_combo.addItems([
            "全部A股", "沪深300", "中证500", "创业板", "自定义列表"
        ])
        range_layout.addWidget(self.import_stock_range_combo, 1, 1)
        
        scroll_layout.addWidget(range_group)
        
        options_group = QGroupBox("导入选项")
        options_layout = QVBoxLayout(options_group)
        
        self.import_cache_cb = QCheckBox("启用多级缓存")
        self.import_cache_cb.setChecked(True)
        options_layout.addWidget(self.import_cache_cb)
        
        self.import_compress_cb = QCheckBox("启用数据压缩")
        self.import_compress_cb.setChecked(True)
        options_layout.addWidget(self.import_compress_cb)
        
        self.import_validate_cb = QCheckBox("启用数据验证")
        self.import_validate_cb.setChecked(True)
        options_layout.addWidget(self.import_validate_cb)
        
        scroll_layout.addWidget(options_group)
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, 1)
        
        progress_group = QGroupBox("导入进度")
        progress_layout = QVBoxLayout(progress_group)
        
        self.import_progress_bar = QProgressBar()
        self.import_progress_bar.setVisible(False)
        progress_layout.addWidget(self.import_progress_bar)
        
        self.import_progress_label = QLabel("准备就绪")
        progress_layout.addWidget(self.import_progress_label)
        
        layout.addWidget(progress_group)
        
        button_layout = QHBoxLayout()
        start_import_btn = QPushButton("🚀 开始导入")
        start_import_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        start_import_btn.clicked.connect(self._start_import)
        button_layout.addWidget(start_import_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        return widget
    
    def _create_history_section(self) -> QWidget:
        """创建导入历史模块"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("📜 导入历史")
        title.setStyleSheet("color: #ff6b35; font-size: 20px; font-weight: bold; padding: 10px 0;")
        layout.addWidget(title)
        
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("任务状态:"))
        self.history_status_filter = QComboBox()
        self.history_status_filter.addItems(["全部", "成功", "失败", "运行中", "已取消"])
        self.history_status_filter.currentTextChanged.connect(self._filter_history)
        filter_layout.addWidget(self.history_status_filter)
        
        filter_layout.addWidget(QLabel("任务名称:"))
        self.history_name_filter = QLineEdit()
        self.history_name_filter.setPlaceholderText("输入任务名称搜索...")
        self.history_name_filter.textChanged.connect(self._filter_history)
        filter_layout.addWidget(self.history_name_filter)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(8)
        self.history_table.setHorizontalHeaderLabels([
            "任务名称", "开始时间", "结束时间", "耗时", "状态", 
            "成功数", "失败数", "总记录数"
        ])
        
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 8):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setStyleSheet("""
            QTableWidget {
                background-color: #1a1d29;
                alternate-background-color: #2d3142;
                gridline-color: #3d4152;
                color: #ffffff;
                border: 1px solid #3d4152;
                border-radius: 4px;
            }
            QHeaderView::section {
                background-color: #252837;
                color: #ffffff;
                border: 1px solid #3d4152;
                padding: 8px;
            }
        """)
        layout.addWidget(self.history_table)
        
        self.history_stats_label = QLabel()
        self.history_stats_label.setStyleSheet("color: #b8bcc8; padding: 10px; background-color: #1a1d29; border-radius: 4px;")
        layout.addWidget(self.history_stats_label)
        
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self.load_import_history)
        button_layout.addWidget(refresh_btn)
        
        clear_btn = QPushButton("🗑️ 清除历史")
        clear_btn.clicked.connect(self._clear_import_history)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        return widget
    
    def _create_export_section(self) -> QWidget:
        """创建数据导出模块"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("📤 数据导出")
        title.setStyleSheet("color: #ff6b35; font-size: 20px; font-weight: bold; padding: 10px 0;")
        layout.addWidget(title)
        
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3d4152;
                background-color: #1a1d29;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #2d3142;
                color: #b8bcc8;
                padding: 8px 16px;
                border: 1px solid #3d4152;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #ff6b35;
                color: #ffffff;
                font-weight: bold;
            }
        """)
        
        basic_tab = self._create_basic_export_tab()
        advanced_tab = self._create_advanced_export_tab()
        
        tab_widget.addTab(basic_tab, "基础导出")
        tab_widget.addTab(advanced_tab, "高级导出")
        
        layout.addWidget(tab_widget)
        
        return widget
    
    def _create_basic_export_tab(self) -> QWidget:
        """创建基础导出标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        settings_group = QGroupBox("导出设置")
        settings_layout = QGridLayout(settings_group)
        
        settings_layout.addWidget(QLabel("导出格式:"), 0, 0)
        self.basic_format_combo = QComboBox()
        self.basic_format_combo.addItems(["Excel (.xlsx)", "CSV (.csv)"])
        settings_layout.addWidget(self.basic_format_combo, 0, 1)
        
        settings_layout.addWidget(QLabel("开始日期:"), 1, 0)
        self.basic_start_date = QDateEdit()
        self.basic_start_date.setDate(QDate.currentDate().addYears(-1))
        self.basic_start_date.setCalendarPopup(True)
        settings_layout.addWidget(self.basic_start_date, 1, 1)
        
        settings_layout.addWidget(QLabel("结束日期:"), 1, 2)
        self.basic_end_date = QDateEdit()
        self.basic_end_date.setDate(QDate.currentDate())
        self.basic_end_date.setCalendarPopup(True)
        settings_layout.addWidget(self.basic_end_date, 1, 3)
        
        settings_layout.addWidget(QLabel("包含数据:"), 2, 0)
        data_layout = QHBoxLayout()
        self.basic_kline_cb = QCheckBox("K线数据")
        self.basic_kline_cb.setChecked(True)
        data_layout.addWidget(self.basic_kline_cb)
        self.basic_volume_cb = QCheckBox("成交量")
        self.basic_volume_cb.setChecked(True)
        data_layout.addWidget(self.basic_volume_cb)
        self.basic_indicators_cb = QCheckBox("技术指标")
        data_layout.addWidget(self.basic_indicators_cb)
        settings_layout.addLayout(data_layout, 2, 1, 1, 3)
        
        layout.addWidget(settings_group)
        
        file_group = QGroupBox("保存位置")
        file_layout = QHBoxLayout(file_group)
        
        self.basic_file_path_edit = QLineEdit()
        self.basic_file_path_edit.setPlaceholderText("选择保存位置...")
        file_layout.addWidget(self.basic_file_path_edit)
        
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_basic_export_path)
        file_layout.addWidget(browse_btn)
        
        layout.addWidget(file_group)
        
        button_layout = QHBoxLayout()
        start_export_btn = QPushButton("🚀 开始导出")
        start_export_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        start_export_btn.clicked.connect(self._start_basic_export)
        button_layout.addWidget(start_export_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        layout.addStretch()
        return widget
    
    def _create_advanced_export_tab(self) -> QWidget:
        """创建高级导出标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        format_group = QGroupBox("导出格式")
        format_layout = QGridLayout(format_group)
        
        format_layout.addWidget(QLabel("文件格式:"), 0, 0)
        self.advanced_format_combo = QComboBox()
        self.advanced_format_combo.addItems(['Excel', 'CSV', 'JSON', 'Parquet'])
        format_layout.addWidget(self.advanced_format_combo, 0, 1)
        
        format_layout.addWidget(QLabel("文件路径:"), 1, 0)
        self.advanced_file_path_edit = QLineEdit()
        format_layout.addWidget(self.advanced_file_path_edit, 1, 1)
        
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_advanced_export_path)
        format_layout.addWidget(browse_btn, 1, 2)
        
        layout.addWidget(format_group)
        
        options_group = QGroupBox("高级选项")
        options_layout = QGridLayout(options_group)
        
        self.advanced_index_cb = QCheckBox("包含索引")
        options_layout.addWidget(self.advanced_index_cb, 0, 0)
        
        self.advanced_header_cb = QCheckBox("包含列标题")
        self.advanced_header_cb.setChecked(True)
        options_layout.addWidget(self.advanced_header_cb, 0, 1)
        
        options_layout.addWidget(QLabel("行数限制:"), 1, 0)
        self.advanced_row_limit_spin = QSpinBox()
        self.advanced_row_limit_spin.setRange(0, 1000000)
        self.advanced_row_limit_spin.setValue(0)
        self.advanced_row_limit_spin.setSpecialValueText("无限制")
        options_layout.addWidget(self.advanced_row_limit_spin, 1, 1)
        
        layout.addWidget(options_group)
        
        button_layout = QHBoxLayout()
        start_export_btn = QPushButton("🚀 开始导出")
        start_export_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        start_export_btn.clicked.connect(self._start_advanced_export)
        button_layout.addWidget(start_export_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        layout.addStretch()
        return widget
    
    def _create_database_section(self) -> QWidget:
        """创建数据库管理模块"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("🗄️ 数据库管理")
        title.setStyleSheet("color: #ff6b35; font-size: 20px; font-weight: bold; padding: 10px 0;")
        layout.addWidget(title)
        
        button_layout = QHBoxLayout()
        
        scan_btn = QPushButton("🔍 扫描数据库")
        scan_btn.clicked.connect(self._scan_databases)
        self._scan_db_btn = scan_btn
        button_layout.addWidget(scan_btn)
        
        backup_btn = QPushButton("💾 备份数据库")
        backup_btn.clicked.connect(self._backup_database)
        self._backup_db_btn = backup_btn
        button_layout.addWidget(backup_btn)
        
        optimize_btn = QPushButton("⚡ 优化数据库")
        optimize_btn.clicked.connect(self._optimize_database)
        self._optimize_db_btn = optimize_btn
        button_layout.addWidget(optimize_btn)
        
        cleanup_btn = QPushButton("🧹 清理数据")
        cleanup_btn.clicked.connect(self._cleanup_database)
        self._cleanup_db_btn = cleanup_btn
        button_layout.addWidget(cleanup_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        db_list_group = QGroupBox("已发现的数据库")
        db_list_layout = QVBoxLayout(db_list_group)
        
        self.db_list_widget = QListWidget()
        self.db_list_widget.setStyleSheet("""
            QListWidget {
                background-color: #1a1d29;
                border: 1px solid #3d4152;
                border-radius: 4px;
                color: #ffffff;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3d4152;
            }
        """)
        db_list_layout.addWidget(self.db_list_widget)
        
        layout.addWidget(db_list_group)
        
        progress_group = QGroupBox("操作进度")
        progress_layout = QVBoxLayout(progress_group)
        
        self.db_progress_bar = QProgressBar()
        self.db_progress_bar.setVisible(False)
        progress_layout.addWidget(self.db_progress_bar)
        
        self.db_progress_label = QLabel("准备就绪")
        progress_layout.addWidget(self.db_progress_label)
        
        layout.addWidget(progress_group)
        
        return widget
    
    def _create_sources_section(self) -> QWidget:
        """创建数据源管理模块"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("🔗 数据源管理")
        title.setStyleSheet("color: #ff6b35; font-size: 20px; font-weight: bold; padding: 10px 0;")
        layout.addWidget(title)
        
        button_layout = QHBoxLayout()
        
        add_source_btn = QPushButton("➕ 添加数据源")
        add_source_btn.clicked.connect(self._add_data_source)
        self._add_source_btn = add_source_btn
        button_layout.addWidget(add_source_btn)
        
        edit_source_btn = QPushButton("✏️ 编辑数据源")
        edit_source_btn.clicked.connect(self._edit_data_source)
        self._edit_source_btn = edit_source_btn
        button_layout.addWidget(edit_source_btn)
        
        delete_source_btn = QPushButton("🗑️ 删除数据源")
        delete_source_btn.clicked.connect(self._delete_data_source)
        self._delete_source_btn = delete_source_btn
        button_layout.addWidget(delete_source_btn)
        
        test_source_btn = QPushButton("🧪 测试连接")
        test_source_btn.clicked.connect(self._test_data_source)
        self._test_source_btn = test_source_btn
        button_layout.addWidget(test_source_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.sources_table = QTableWidget()
        self.sources_table.setColumnCount(5)
        self.sources_table.setHorizontalHeaderLabels([
            "数据源名称", "类型", "提供商", "状态", "最后更新"
        ])
        
        header = self.sources_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 5):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        self.sources_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sources_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sources_table.setAlternatingRowColors(True)
        self.sources_table.setStyleSheet("""
            QTableWidget {
                background-color: #1a1d29;
                alternate-background-color: #2d3142;
                gridline-color: #3d4152;
                color: #ffffff;
                border: 1px solid #3d4152;
                border-radius: 4px;
            }
            QHeaderView::section {
                background-color: #252837;
                color: #ffffff;
                border: 1px solid #3d4152;
                padding: 8px;
            }
        """)
        layout.addWidget(self.sources_table)
        
        self._load_data_sources()
        
        return widget
    
    def _create_quality_section(self) -> QWidget:
        """创建数据质量监控模块"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("📈 数据质量")
        title.setStyleSheet("color: #ff6b35; font-size: 20px; font-weight: bold; padding: 10px 0;")
        layout.addWidget(title)
        
        button_layout = QHBoxLayout()
        
        check_quality_btn = QPushButton("🔍 检查数据质量")
        check_quality_btn.clicked.connect(self._check_data_quality)
        button_layout.addWidget(check_quality_btn)
        
        fix_issues_btn = QPushButton("🔧 修复数据问题")
        fix_issues_btn.clicked.connect(self._fix_data_issues)
        self._fix_issues_btn = fix_issues_btn
        button_layout.addWidget(fix_issues_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        quality_group = QGroupBox("数据质量报告")
        quality_layout = QVBoxLayout(quality_group)
        
        self.quality_progress = QProgressBar()
        self.quality_progress.setFormat("数据质量评分: %p%")
        self.quality_progress.setValue(0)
        self.quality_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #3d4152;
                border-radius: 5px;
                text-align: center;
                color: #ffffff;
                background-color: #1a1d29;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 3px;
            }
        """)
        quality_layout.addWidget(self.quality_progress)
        
        self.quality_table = QTableWidget()
        self.quality_table.setColumnCount(4)
        self.quality_table.setHorizontalHeaderLabels([
            "检查项", "状态", "问题数", "详情"
        ])
        
        header = self.quality_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 4):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        self.quality_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.quality_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.quality_table.setAlternatingRowColors(True)
        self.quality_table.setStyleSheet("""
            QTableWidget {
                background-color: #1a1d29;
                alternate-background-color: #2d3142;
                gridline-color: #3d4152;
                color: #ffffff;
                border: 1px solid #3d4152;
                border-radius: 4px;
            }
            QHeaderView::section {
                background-color: #252837;
                color: #ffffff;
                border: 1px solid #3d4152;
                padding: 8px;
            }
        """)
        quality_layout.addWidget(self.quality_table)
        
        layout.addWidget(quality_group)
        
        return widget
    
    def _test_import_connection(self):
        provider_name = self.import_provider_combo.currentText()
        api_key = self.import_api_key_edit.text()
        if not api_key:
            QMessageBox.warning(self, "提示", "请先输入API密钥")
            return
        try:
            from core.real_data_provider import get_real_data_provider
            provider = get_real_data_provider()
            result = provider.test_connection(provider_name, api_key)
            if result:
                QMessageBox.information(self, "连接测试", f"连接 {provider_name} 测试成功！")
            else:
                QMessageBox.warning(self, "连接测试", f"连接 {provider_name} 测试失败，请检查密钥和网络")
        except Exception as e:
            logger.warning(f"连接测试异常: {e}")
            QMessageBox.warning(self, "连接测试", f"连接测试失败: {e}")
    
    def _start_import(self):
        """开始数据导入"""
        api_key = self.import_api_key_edit.text()
        if not api_key:
            QMessageBox.warning(self, "警告", "请输入API密钥")
            return
        
        self.import_progress_bar.setVisible(True)
        self.import_progress_bar.setValue(0)
        self.import_progress_label.setText("正在初始化导入任务...")
        
        import_config = {
            'data_type': self.import_type_combo.currentText(),
            'provider': self.import_provider_combo.currentText(),
            'api_key': api_key,
            'start_date': self.import_start_date.date().toString(),
            'end_date': self.import_end_date.date().toString(),
            'stock_range': self.import_stock_range_combo.currentText(),
        }
        
        self.import_thread = DataImportThread(import_config)
        self.import_thread.progress_updated.connect(self._on_import_progress)
        self.import_thread.import_completed.connect(self._on_import_completed)
        self.import_thread.import_failed.connect(self._on_import_failed)
        self.import_thread.start()
    
    def _on_import_progress(self, progress: int, message: str):
        """导入进度更新"""
        self.import_progress_bar.setValue(progress)
        self.import_progress_label.setText(message)
    
    def _on_import_completed(self, message: str):
        """导入完成"""
        self.import_progress_bar.setVisible(False)
        self.import_progress_label.setText("导入完成")
        QMessageBox.information(self, "导入成功", message)
        self.data_imported.emit({})
    
    def _on_import_failed(self, error: str):
        """导入失败"""
        self.import_progress_bar.setVisible(False)
        self.import_progress_label.setText("导入失败")
        QMessageBox.critical(self, "导入失败", f"导入失败: {error}")
    
    def load_import_history(self):
        self.history_table.setRowCount(0)
        try:
            from core.importdata.import_config_manager import ImportConfigManager
            config_manager = ImportConfigManager()
            history_records = config_manager.get_history(limit=200)

            self._history_records = history_records
            self._filter_history()
        except Exception as e:
            logger.warning(f"加载导入历史失败: {e}")
            self.history_stats_label.setText("📈 统计：加载失败 | 共 0 条记录")
    
    def _filter_history(self):
        self.history_table.setRowCount(0)

        records = getattr(self, '_history_records', [])
        if not records:
            self.history_stats_label.setText("📈 统计：共 0 条记录 | 成功 0 | 失败 0 | 成功率 0.0%")
            return

        status_filter = self.history_status_filter.currentText()
        name_filter = self.history_name_filter.text().strip().lower()

        filtered_records = records
        if status_filter != "全部":
            status_map = {
                "成功": "completed",
                "失败": "failed",
                "运行中": "running",
                "已取消": "cancelled",
            }
            mapped_status = status_map.get(status_filter, "")
            filtered_records = [r for r in filtered_records if r.get('status', '') == mapped_status]

        if name_filter:
            filtered_records = [r for r in filtered_records
                                if name_filter in str(r.get('task_id', '')).lower()
                                or name_filter in str(r.get('id', '')).lower()]

        total_success = sum(1 for r in records if r.get('status') == 'completed')
        total_failed = sum(1 for r in records if r.get('status') == 'failed')
        success_rate = (total_success / len(records) * 100) if records else 0
        self.history_stats_label.setText(
            f"📈 统计：共 {len(records)} 条记录 | 成功 {total_success} | 失败 {total_failed} | 成功率 {success_rate:.1f}%"
        )

        for record in filtered_records:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            self.history_table.setItem(row, 0, QTableWidgetItem(str(record.get('task_id', ''))[:30]))
            self.history_table.setItem(row, 1, QTableWidgetItem(str(record.get('start_time', ''))[:19]))
            self.history_table.setItem(row, 2, QTableWidgetItem(str(record.get('end_time', ''))[:19]))
            self.history_table.setItem(row, 3, QTableWidgetItem(str(record.get('elapsed', ''))))
            self.history_table.setItem(row, 4, QTableWidgetItem(str(record.get('status', ''))))
            self.history_table.setItem(row, 5, QTableWidgetItem(str(record.get('imported_records', 0))))
            self.history_table.setItem(row, 6, QTableWidgetItem(str(record.get('error_count', 0))))
            self.history_table.setItem(row, 7, QTableWidgetItem(str(record.get('total_records', 0))))
    
    def _clear_import_history(self):
        """清除导入历史"""
        reply = QMessageBox.question(
            self,
            "确认清除",
            "确定要清除所有历史记录吗？\n此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.load_import_history()
    
    def _on_data_imported(self, data: dict):
        self.load_statistics()
        self.load_import_history()
    
    def _on_data_exported(self, file_path: str):
        self.recent_list.insertItem(0, f"📤 数据已导出: {file_path}")
        self.load_statistics()
    
    def _on_database_updated(self, action: str):
        self.recent_list.insertItem(0, f"🗄️ 数据库操作: {action}")
        self.load_statistics()
    
    def _browse_basic_export_path(self):
        """浏览基础导出保存路径"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存数据",
            f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel文件 (*.xlsx);;CSV文件 (*.csv);;所有文件 (*)"
        )
        if file_path:
            self.basic_file_path_edit.setText(file_path)
    
    def _browse_advanced_export_path(self):
        """浏览高级导出保存路径"""
        format_name = self.advanced_format_combo.currentText()
        extensions = {
            'Excel': '*.xlsx',
            'CSV': '*.csv',
            'JSON': '*.json',
            'Parquet': '*.parquet'
        }
        file_path, _ = QFileDialog.getSaveFileName(
            self, f"保存{format_name}文件",
            f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extensions[format_name][2:]}",
            f"{format_name} 文件 ({extensions[format_name]})"
        )
        if file_path:
            self.advanced_file_path_edit.setText(file_path)
    
    def _start_basic_export(self):
        file_path = self.basic_file_path_edit.text().strip()
        if not file_path:
            QMessageBox.warning(self, "提示", "请选择保存位置")
            return

        try:
            import pandas as pd
            from core.real_data_provider import get_real_data_provider
            provider = get_real_data_provider()

            start_date = self.basic_start_date.date().toString("yyyy-MM-dd")
            end_date = self.basic_end_date.date().toString("yyyy-MM-dd")

            data_list = []
            codes = ["000001", "000002", "600000", "600036"]
            for code in codes:
                try:
                    stock_data = provider.get_market_data(code, start_date, end_date)
                    if stock_data is not None and not stock_data.empty:
                        data_list.append(stock_data)
                except Exception:
                    pass

            if not data_list:
                QMessageBox.warning(self, "导出", "没有可导出的数据")
                return

            export_data = pd.concat(data_list, ignore_index=True)

            export_config = {
                'format': 'Excel' if file_path.endswith('.xlsx') else 'CSV',
                'file_path': file_path,
                'data': export_data,
            }
            self.export_thread = DataExportThread(export_config)
            self.export_thread.export_completed.connect(
                lambda path: self.data_exported.emit(path)
            )
            self.export_thread.start()
            QMessageBox.information(self, "导出", f"开始导出到: {file_path}")
        except Exception as e:
            logger.warning(f"基础导出失败: {e}")
            QMessageBox.warning(self, "导出失败", f"导出失败: {e}")
    
    def _start_advanced_export(self):
        file_path = self.advanced_file_path_edit.text().strip()
        if not file_path:
            QMessageBox.warning(self, "提示", "请选择保存位置")
            return

        try:
            import pandas as pd
            from core.real_data_provider import get_real_data_provider
            provider = get_real_data_provider()

            data_list = []
            codes = ["000001", "000002", "600000", "600036"]
            for code in codes:
                try:
                    stock_data = provider.get_market_data(code)
                    if stock_data is not None and not stock_data.empty:
                        data_list.append(stock_data)
                except Exception:
                    pass

            if not data_list:
                QMessageBox.warning(self, "导出", "没有可导出的数据")
                return

            export_data = pd.concat(data_list, ignore_index=True)

            export_config = {
                'format': self.advanced_format_combo.currentText(),
                'file_path': file_path,
                'data': export_data,
            }
            self.export_thread = DataExportThread(export_config)
            self.export_thread.export_completed.connect(
                lambda path: self.data_exported.emit(path)
            )
            self.export_thread.start()
            QMessageBox.information(self, "导出", f"开始高级导出到: {file_path}")
        except Exception as e:
            logger.warning(f"高级导出失败: {e}")
            QMessageBox.warning(self, "导出失败", f"导出失败: {e}")
    
    def _scan_databases(self):
        self.db_progress_bar.setVisible(True)
        self.db_progress_bar.setValue(0)
        self.db_progress_label.setText("正在扫描数据库...")
        self.db_list_widget.clear()
        try:
            data_dir = Path("data")
            if not data_dir.exists():
                self.db_progress_bar.setValue(100)
                self.db_progress_label.setText("未找到data目录")
                return

            db_files = list(data_dir.rglob("*.duckdb")) + list(data_dir.rglob("*.sqlite"))
            db_files = list(dict.fromkeys(db_files))
            self.db_progress_bar.setValue(20)

            if not db_files:
                self.db_progress_bar.setValue(100)
                self.db_progress_label.setText("未发现数据库文件")
                return

            for idx, db_path in enumerate(db_files):
                try:
                    file_size = db_path.stat().st_size
                    size_mb = file_size / (1024 * 1024)
                    relative_path = db_path.relative_to(Path.cwd())
                    self.db_list_widget.addItem(
                        f"📁 {relative_path} ({size_mb:.1f} MB)"
                    )
                    progress = 20 + int(80 * (idx + 1) / len(db_files))
                    self.db_progress_bar.setValue(progress)
                except Exception:
                    pass

            self.db_progress_bar.setValue(100)
            self.db_progress_label.setText(f"扫描完成，发现 {len(db_files)} 个数据库文件")
            self.database_updated.emit("数据库扫描完成")
        except Exception as e:
            logger.warning(f"扫描数据库失败: {e}")
            self.db_progress_bar.setValue(0)
            self.db_progress_label.setText(f"扫描失败: {e}")
    
    def _backup_database(self):
        """备份数据库"""
        try:
            from core.containers import get_service_container
            from core.services.database_service import DatabaseService

            container = get_service_container()
            if not container.is_registered(DatabaseService):
                QMessageBox.warning(self, "备份数据库", "数据库服务未初始化，无法执行备份")
                return

            db_service = container.resolve(DatabaseService)
            db_service.backup_now()
            QMessageBox.information(self, "备份数据库", "数据库备份完成")
        except Exception as e:
            logger.error(f"备份数据库失败: {e}")
            QMessageBox.warning(self, "备份数据库", f"备份数据库失败: {e}")

    def _optimize_database(self):
        """优化数据库"""
        try:
            from core.containers import get_service_container
            from core.services.database_service import DatabaseService

            container = get_service_container()
            if not container.is_registered(DatabaseService):
                QMessageBox.warning(self, "优化数据库", "数据库服务未初始化，无法执行优化")
                return

            db_service = container.resolve(DatabaseService)
            db_service.optimize_now()
            QMessageBox.information(self, "优化数据库", "数据库优化完成")
        except Exception as e:
            logger.error(f"优化数据库失败: {e}")
            QMessageBox.warning(self, "优化数据库", f"优化数据库失败: {e}")

    def _cleanup_database(self):
        """清理数据库"""
        try:
            from core.importdata.task_status_manager import get_task_status_manager
            manager = get_task_status_manager()
            removed_count = manager.cleanup_finished_tasks(older_than_hours=24)
            QMessageBox.information(self, "清理数据库", f"清理完成，共清理 {removed_count} 个历史任务")
        except Exception as e:
            logger.error(f"清理数据库失败: {e}")
            QMessageBox.warning(self, "清理数据库", f"清理数据库失败: {e}")

    def _load_data_sources(self):
        self.sources_table.setRowCount(0)
        try:
            from core.importdata.import_config_manager import ImportConfigManager
            config_manager = ImportConfigManager()
            sources = config_manager.get_all_data_sources()

            for name, source in sources.items():
                row = self.sources_table.rowCount()
                self.sources_table.insertRow(row)
                self.sources_table.setItem(row, 0, QTableWidgetItem(name))
                self.sources_table.setItem(row, 1, QTableWidgetItem(source.source_type or "-"))
                self.sources_table.setItem(row, 2, QTableWidgetItem(source.provider or "-"))
                self.sources_table.setItem(row, 3, QTableWidgetItem("启用" if source.enabled else "禁用"))
                self.sources_table.setItem(row, 4, QTableWidgetItem(source.updated_at[:10] if source.updated_at else "-"))
        except Exception as e:
            logger.warning(f"加载数据源列表失败: {e}")
    
    def _add_data_source(self):
        """添加数据源"""
        try:
            from core.importdata.import_config_manager import ImportConfigManager, DataSourceConfig

            name, ok = QInputDialog.getText(self, "添加数据源", "请输入数据源名称:")
            if not ok or not name.strip():
                return

            config_manager = ImportConfigManager()
            success = config_manager.add_data_source(
                DataSourceConfig(name=name.strip(), plugin_name=name.strip())
            )
            if success:
                QMessageBox.information(self, "添加数据源", f"数据源「{name.strip()}」添加成功")
                self._load_data_sources()
            else:
                QMessageBox.warning(self, "添加数据源", "添加数据源失败")
        except Exception as e:
            logger.error(f"添加数据源失败: {e}")
            QMessageBox.warning(self, "添加数据源", f"添加数据源失败: {e}")
    
    def _edit_data_source(self):
        """编辑数据源（切换启用状态）"""
        try:
            selected = self.sources_table.selectedItems()
            if not selected:
                QMessageBox.warning(self, "编辑数据源", "请先选择要编辑的数据源")
                return
            row = selected[0].row()
            name = self.sources_table.item(row, 0).text()

            from core.importdata.import_config_manager import ImportConfigManager
            config_manager = ImportConfigManager()
            source = config_manager.get_data_source(name)
            if not source:
                QMessageBox.warning(self, "编辑数据源", f"数据源「{name}」不存在")
                return

            new_enabled = not source.enabled
            success = config_manager.update_data_source(name, enabled=new_enabled)
            if success:
                new_state = "启用" if new_enabled else "禁用"
                QMessageBox.information(self, "编辑数据源", f"数据源「{name}」已{new_state}")
                self._load_data_sources()
            else:
                QMessageBox.warning(self, "编辑数据源", "编辑数据源失败")
        except Exception as e:
            logger.error(f"编辑数据源失败: {e}")
            QMessageBox.warning(self, "编辑数据源", f"编辑数据源失败: {e}")
    
    def _delete_data_source(self):
        """删除数据源"""
        try:
            selected = self.sources_table.selectedItems()
            if not selected:
                QMessageBox.warning(self, "删除数据源", "请先选择要删除的数据源")
                return
            row = selected[0].row()
            name = self.sources_table.item(row, 0).text()

            reply = QMessageBox.question(
                self, "删除数据源", f"确定要删除数据源「{name}」吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

            from core.importdata.import_config_manager import ImportConfigManager
            config_manager = ImportConfigManager()
            success = config_manager.remove_data_source(name)
            if success:
                QMessageBox.information(self, "删除数据源", f"数据源「{name}」已删除")
                self._load_data_sources()
            else:
                QMessageBox.warning(self, "删除数据源", "删除数据源失败")
        except Exception as e:
            logger.error(f"删除数据源失败: {e}")
            QMessageBox.warning(self, "删除数据源", f"删除数据源失败: {e}")
    
    def _test_data_source(self):
        """测试数据源连接"""
        try:
            from core.services.unified_data_manager import UnifiedDataManager
            data_manager = UnifiedDataManager()
            success = data_manager.test_connection()
            if success:
                QMessageBox.information(self, "测试数据源连接", "数据源连接正常")
            else:
                QMessageBox.warning(self, "测试数据源连接", "数据源连接失败，请检查数据源配置")
        except Exception as e:
            logger.error(f"测试数据源连接失败: {e}")
            QMessageBox.warning(self, "测试数据源连接", f"测试数据源连接失败: {e}")
    
    def _check_data_quality(self):
        try:
            # R278 数据治理：改走 DI 单例 + 真实数据样本评估。
            # 原实现直接 new 且无参调用 assess_quality() → DataQualityMonitor 对
            # None 返回固定 0.7 分 / 默认 90 分占位，质量面板数字失真。
            from core.containers import get_service_container
            from core.data_quality_risk_manager import DataQualityRiskManager
            quality_manager = get_service_container().resolve(DataQualityRiskManager)

            sample_df = self._get_quality_sample_data()
            if sample_df is None or sample_df.empty:
                self.quality_progress.setValue(0)
                QMessageBox.information(self, "质量检查", "数据库中暂无K线数据可评估，请先导入/获取数据后再检查")
                return

            report = quality_manager.assess_quality(
                sample_df, 'kline',
                {'source': 'data_management_dialog', 'sample_rows': len(sample_df)}
            )
            score = report.get('quality_score', 0)
            self.quality_progress.setValue(int(score))
            self.quality_progress.setStyleSheet(self.quality_progress.styleSheet().replace(
                '#28a745',
                '#28a745' if score >= 80 else ('#ffc107' if score >= 60 else '#dc3545')
            ))

            self.quality_table.setRowCount(0)
            checks = [
                ("完整性", report.get('completeness', 0), report.get('issues', 0), "数据字段是否完整"),
                ("准确性", report.get('accuracy', 0), report.get('issues', 0), "数据值是否在合理范围"),
                ("时效性", report.get('timeliness', 0), report.get('issues', 0), "数据是否及时更新"),
                ("一致性", report.get('consistency', 0), report.get('issues', 0), "多数据源数据是否一致"),
                ("唯一性", report.get('uniqueness', 0), report.get('issues', 0), "是否存在重复数据"),
            ]

            for check_name, check_score, issues, detail in checks:
                row = self.quality_table.rowCount()
                self.quality_table.insertRow(row)
                self.quality_table.setItem(row, 0, QTableWidgetItem(check_name))
                status_item = QTableWidgetItem("通过" if check_score >= 80 else ("警告" if check_score >= 60 else "异常"))
                self.quality_table.setItem(row, 1, status_item)
                self.quality_table.setItem(row, 2, QTableWidgetItem(str(issues)))
                self.quality_table.setItem(row, 3, QTableWidgetItem(detail))

            QMessageBox.information(
                self, "质量检查",
                f"数据质量检查完成，综合评分: {score:.0f}分（样本: {len(sample_df)} 条K线）")
        except Exception as e:
            logger.warning(f"数据质量检查失败: {e}")
            self.quality_progress.setValue(0)
            QMessageBox.warning(self, "质量检查", f"数据质量检查失败: {e}")

    def _get_quality_sample_data(self):
        """R278：从数据库读取数据量最大的 symbol 的最近 K 线样本用于真实质量评估"""
        try:
            from core.asset_database_manager import get_asset_separated_database_manager
            from core.plugin_types import AssetType
            asset_manager = get_asset_separated_database_manager()
            with asset_manager.get_connection(AssetType.STOCK_A) as conn:
                sample = conn.execute(
                    """
                    SELECT * FROM historical_kline_data
                    WHERE symbol = (
                        SELECT symbol FROM historical_kline_data
                        GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT 1
                    )
                    ORDER BY timestamp DESC LIMIT 1000
                    """
                ).df()
                return sample
        except Exception as e:
            logger.debug(f"读取质量样本失败: {e}")
            return None

    def _fix_data_issues(self):
        """修复数据问题（当前为诊断模式，基于真实数据输出质量报告与建议）"""
        try:
            # R278 数据治理：改走 DI 单例 + 真实数据样本评估（原实现无参 assess_quality 占位失真）
            from core.containers import get_service_container
            from core.data_quality_risk_manager import DataQualityRiskManager
            quality_manager = get_service_container().resolve(DataQualityRiskManager)

            sample_df = self._get_quality_sample_data()
            if sample_df is None or sample_df.empty:
                QMessageBox.information(self, "数据问题诊断", "数据库中暂无K线数据可评估，请先导入/获取数据")
                return

            report = quality_manager.assess_quality(
                sample_df, 'kline',
                {'source': 'data_management_dialog', 'sample_rows': len(sample_df)}
            )
            score = report.get('quality_score', 0)
            issues = report.get('issues', 0)
            recommendations = report.get('recommendations', [])

            lines = [
                f"数据质量综合评分: {score} 分（样本: {len(sample_df)} 条K线）",
                f"待处理问题数量: {issues} 个",
            ]
            if recommendations:
                lines.append("")
                lines.append("建议措施:")
                for idx, rec in enumerate(recommendations, 1):
                    lines.append(f"{idx}. {rec}")
            else:
                lines.append("")
                lines.append("暂无待处理建议")

            QMessageBox.information(self, "数据问题诊断", "\n".join(lines))
        except Exception as e:
            logger.error(f"数据问题诊断失败: {e}")
            QMessageBox.warning(self, "数据问题诊断", f"数据问题诊断失败: {e}")
    
    def load_statistics(self):
        try:
            from core.importdata.import_config_manager import ImportConfigManager
            config_manager = ImportConfigManager()
            stats = config_manager.get_statistics()

            tasks = stats.get('tasks', {})
            history = stats.get('history_30_days', {})
            sources = stats.get('data_sources', {})

            total_runs = history.get('total_runs', 0)
            successful = history.get('successful_runs', 0)
            failed = history.get('failed_runs', 0)
            total_imported = history.get('total_imported', 0)
            db_count = sources.get('total', 0)

            if hasattr(self, 'overview_widget'):
                layout = self.overview_widget.layout()
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if isinstance(item, QGridLayout) or hasattr(item, 'itemAt'):
                        grid = item if isinstance(item, QGridLayout) else item.layout()
                        if grid:
                            for j in range(grid.count()):
                                grid_item = grid.itemAt(j)
                                if grid_item and grid_item.widget():
                                    widget = grid_item.widget()
                                    if hasattr(widget, 'value_label'):
                                        value_label = widget.value_label
                                        parent_text = widget.findChild(QLabel, '', Qt.FindDirectChildrenOnly)
                                        if parent_text is None:
                                            continue
                                        text = value_label.text()
                                        if j == 0:
                                            value_label.setText(str(total_runs))
                                        elif j == 1:
                                            value_label.setText(str(successful))
                                        elif j == 2:
                                            value_label.setText(str(failed))
                                        elif j == 3:
                                            value_label.setText("0")
                                        elif j == 4:
                                            value_label.setText(str(db_count))
                                        elif j == 5:
                                            value_label.setText(f"{self.quality_progress.value()}%")

            self.recent_list.clear()
            if total_runs > 0:
                self.recent_list.addItem(f"📊 近30天总执行次数: {total_runs}")
                self.recent_list.addItem(f"✅ 成功导入: {successful} 次")
                if failed > 0:
                    self.recent_list.addItem(f"❌ 失败: {failed} 次")
                success_rate = (successful / total_runs * 100) if total_runs > 0 else 0
                self.recent_list.addItem(f"📈 成功率: {success_rate:.1f}%")
                self.recent_list.addItem(f"📥 总导入记录: {total_imported}")
            else:
                self.recent_list.addItem("暂无历史活动记录")
        except Exception as e:
            logger.warning(f"加载统计数据失败: {e}")
            self.recent_list.clear()
            self.recent_list.addItem("统计数据加载失败，请检查系统配置")
    
    def setup_connections(self):
        self.data_imported.connect(self._on_data_imported)
        self.data_exported.connect(self._on_data_exported)
        self.database_updated.connect(self._on_database_updated)

    def closeEvent(self, event):
        """关闭事件处理（R248 修复：先停止导入/导出线程，避免 QThread GC 崩溃）"""
        try:
            # 停止数据导入/导出线程
            for name, attr in (("数据导入", 'import_thread'), ("数据导出", 'export_thread')):
                thread = getattr(self, attr, None)
                if thread is not None:
                    try:
                        if thread.isRunning():
                            thread.requestInterruption()
                            if not thread.wait(3000):
                                logger.warning(f"{name}线程 3 秒内未退出，继续等待...")
                                if not thread.wait(5000):
                                    logger.warning(f"{name}线程仍未退出，强制终止")
                                    thread.terminate()
                                    thread.wait(1000)
                    except Exception as e:
                        logger.warning(f"停止{name}线程异常: {e}")
        except Exception as e:
            logger.warning(f"关闭对话框停止线程异常: {e}")
        super().closeEvent(event)


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    dialog = UnifiedDataManagementDialog()
    dialog.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
