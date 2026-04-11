#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Level-2 数据面板（增强版）
提供Level-2行情数据的实时显示和交互功能
新增功能：订单簿深度图表、数据导出、历史回放、自定义指标、价格预警、多股票对比
"""

import asyncio
import csv
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QSplitter, QFrame, QPushButton, QComboBox, QSpinBox,
    QGroupBox, QGridLayout, QProgressBar, QTabWidget, QDialog,
    QLineEdit, QTextEdit, QMessageBox, QFileDialog, QCheckBox,
    QSlider, QMenu, QAction
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QPoint
from PyQt5.QtGui import QFont, QColor, QPalette, QCursor
from loguru import logger

from core.services.enhanced_realtime_data_manager import EnhancedRealtimeDataManager
from core.plugin_types import DataType, AssetType
from core.events.event_bus import EventBus, RealtimeDataEvent, TickDataEvent, OrderBookEvent
from core.events.types import StockSelectedEvent
from gui.widgets.enhanced_ui.order_book_widget import OrderBookWidget


class CustomIndicatorDialog(QDialog):
    """自定义指标对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定义指标")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.indicators = {}
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 指标列表
        self.indicator_table = QTableWidget()
        self.indicator_table.setColumnCount(4)
        self.indicator_table.setHorizontalHeaderLabels(["指标名称", "公式", "删除", "测试"])
        self.indicator_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.indicator_table)

        # 添加按钮
        add_btn = QPushButton("添加指标")
        add_btn.clicked.connect(self._add_indicator)
        layout.addWidget(add_btn)

        # 按钮栏
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def _add_indicator(self):
        """添加指标"""
        row = self.indicator_table.rowCount()
        self.indicator_table.insertRow(row)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("指标名称")
        self.indicator_table.setCellWidget(row, 0, name_edit)

        formula_edit = QLineEdit()
        formula_edit.setPlaceholderText("公式，如: bid_volume + ask_volume")
        self.indicator_table.setCellWidget(row, 1, formula_edit)

        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda: self.indicator_table.removeRow(row))
        self.indicator_table.setCellWidget(row, 2, del_btn)

        test_btn = QPushButton("测试")
        test_btn.clicked.connect(lambda: self._test_indicator(formula_edit.text()))
        self.indicator_table.setCellWidget(row, 3, test_btn)

    def _test_indicator(self, formula: str):
        """测试指标公式"""
        try:
            test_data = {
                'bid_volume': 1000,
                'ask_volume': 1200,
                'bid_price': 99.95,
                'ask_price': 100.05,
                'total_volume': 2200
            }
            result = eval(formula, {"__builtins__": None}, test_data)
            QMessageBox.information(self, "测试成功", f"计算结果: {result}")
        except Exception as e:
            QMessageBox.warning(self, "测试失败", f"公式错误: {str(e)}")

    def get_indicators(self) -> Dict[str, str]:
        """获取所有指标"""
        indicators = {}
        for row in range(self.indicator_table.rowCount()):
            name_edit = self.indicator_table.cellWidget(row, 0)
            formula_edit = self.indicator_table.cellWidget(row, 1)
            if name_edit and formula_edit:
                name = name_edit.text()
                formula = formula_edit.text()
                if name and formula:
                    indicators[name] = formula
        return indicators


class PriceAlertDialog(QDialog):
    """价格预警对话框"""

    def __init__(self, parent=None, current_price: float = 0.0):
        super().__init__(parent)
        self.setWindowTitle("价格预警设置")
        self.setModal(True)
        self.current_price = current_price
        self.alerts = []
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 当前价格
        current_price_label = QLabel(f"当前价格: {self.current_price:.2f}")
        current_price_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(current_price_label)

        # 预警列表
        self.alert_table = QTableWidget()
        self.alert_table.setColumnCount(4)
        self.alert_table.setHorizontalHeaderLabels(["预警类型", "价格", "启用", "删除"])
        self.alert_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.alert_table)

        # 添加预警按钮
        add_alert_layout = QHBoxLayout()
        add_alert_layout.addWidget(QLabel("预警价格:"))
        self.alert_price_edit = QLineEdit()
        self.alert_price_edit.setPlaceholderText("输入价格")
        add_alert_layout.addWidget(self.alert_price_edit)

        self.alert_type_combo = QComboBox()
        self.alert_type_combo.addItems(["高于", "低于"])
        add_alert_layout.addWidget(self.alert_type_combo)

        add_btn = QPushButton("添加预警")
        add_btn.clicked.connect(self._add_alert)
        add_alert_layout.addWidget(add_btn)

        layout.addLayout(add_alert_layout)

        # 按钮栏
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def _add_alert(self):
        """添加预警"""
        try:
            alert_type = self.alert_type_combo.currentText()
            alert_price = float(self.alert_price_edit.text())

            row = self.alert_table.rowCount()
            self.alert_table.insertRow(row)

            self.alert_table.setItem(row, 0, QTableWidgetItem(alert_type))
            self.alert_table.setItem(row, 1, QTableWidgetItem(f"{alert_price:.2f}"))

            enable_check = QCheckBox()
            enable_check.setChecked(True)
            self.alert_table.setCellWidget(row, 2, enable_check)

            del_btn = QPushButton("删除")
            del_btn.clicked.connect(lambda: self.alert_table.removeRow(row))
            self.alert_table.setCellWidget(row, 3, del_btn)

            self.alert_price_edit.clear()

        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的价格")

    def get_alerts(self) -> List[Dict[str, Any]]:
        """获取所有预警"""
        alerts = []
        for row in range(self.alert_table.rowCount()):
            alert_type = self.alert_table.item(row, 0).text()
            alert_price = float(self.alert_table.item(row, 1).text())
            enable_check = self.alert_table.cellWidget(row, 2)
            enabled = enable_check.isChecked()

            alerts.append({
                'type': alert_type,
                'price': alert_price,
                'enabled': enabled
            })
        return alerts


class HistoricalReplayDialog(QDialog):
    """历史数据回放对话框"""

    def __init__(self, parent=None, historical_data: List[Dict] = None):
        super().__init__(parent)
        self.setWindowTitle("历史数据回放")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        self.historical_data = historical_data or []
        self.current_index = 0
        self.is_playing = False
        self.playback_speed = 1000
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 控制面板
        control_panel = QFrame()
        control_layout = QHBoxLayout(control_panel)

        # 播放控制
        self.play_btn = QPushButton("播放")
        self.play_btn.clicked.connect(self._toggle_playback)
        control_layout.addWidget(self.play_btn)

        self.pause_btn = QPushButton("暂停")
        self.pause_btn.clicked.connect(self._pause_playback)
        self.pause_btn.setEnabled(False)
        control_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self._stop_playback)
        control_layout.addWidget(self.stop_btn)

        # 进度条
        control_layout.addWidget(QLabel("进度:"))
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, len(self.historical_data) - 1)
        self.progress_slider.valueChanged.connect(self._on_slider_changed)
        control_layout.addWidget(self.progress_slider)

        # 速度控制
        control_layout.addWidget(QLabel("速度:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["100ms", "500ms", "1s", "2s", "5s"])
        self.speed_combo.currentTextChanged.connect(self._on_speed_changed)
        control_layout.addWidget(self.speed_combo)

        # 时间显示
        self.time_label = QLabel("时间: --")
        control_layout.addWidget(self.time_label)

        layout.addWidget(control_panel)

        # 数据显示
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(5)
        self.data_table.setHorizontalHeaderLabels(["时间", "价格", "成交量", "方向", "类型"])
        self.data_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.data_table)

        # 回放定时器
        self.replay_timer = QTimer()
        self.replay_timer.timeout.connect(self._on_replay_tick)

    def _toggle_playback(self):
        """切换播放状态"""
        if not self.historical_data:
            QMessageBox.warning(self, "无数据", "没有可回放的历史数据")
            return

        self.is_playing = True
        self.play_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.replay_timer.start(self.playback_speed)
        logger.info("开始历史数据回放")

    def _pause_playback(self):
        """暂停回放"""
        self.is_playing = False
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.replay_timer.stop()
        logger.info("暂停历史数据回放")

    def _stop_playback(self):
        """停止回放"""
        self.is_playing = False
        self.current_index = 0
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.replay_timer.stop()
        self.progress_slider.setValue(0)
        self.data_table.setRowCount(0)
        logger.info("停止历史数据回放")

    def _on_replay_tick(self):
        """回放定时器回调"""
        if self.current_index >= len(self.historical_data):
            self._pause_playback()
            QMessageBox.information(self, "回放完成", "历史数据回放已完成")
            return

        data = self.historical_data[self.current_index]
        self._display_data(data)

        self.current_index += 1
        self.progress_slider.setValue(self.current_index)

    def _on_slider_changed(self, value: int):
        """滑块变更处理"""
        if not self.is_playing and self.historical_data:
            self.current_index = value
            data = self.historical_data[value]
            self._display_data(data)

    def _on_speed_changed(self, speed_text: str):
        """速度变更处理"""
        speed_map = {
            "100ms": 100,
            "500ms": 500,
            "1s": 1000,
            "2s": 2000,
            "5s": 5000
        }
        self.playback_speed = speed_map.get(speed_text, 1000)
        if self.is_playing:
            self.replay_timer.setInterval(self.playback_speed)

    def _display_data(self, data: Dict):
        """显示数据"""
        timestamp = data.get('timestamp', '')
        price = data.get('price', 0)
        volume = data.get('volume', 0)
        tick_type = data.get('type', 'unknown')

        row = self.data_table.rowCount()
        self.data_table.insertRow(row)

        time_str = timestamp.split('T')[1][:8] if 'T' in timestamp else timestamp
        self.data_table.setItem(row, 0, QTableWidgetItem(time_str))
        self.data_table.setItem(row, 1, QTableWidgetItem(f"{price:.2f}"))
        self.data_table.setItem(row, 2, QTableWidgetItem(f"{volume:,}"))

        direction = "↑" if tick_type == "buy" else "↓"
        self.data_table.setItem(row, 3, QTableWidgetItem(direction))
        self.data_table.setItem(row, 4, QTableWidgetItem(tick_type))

        self.time_label.setText(f"时间: {time_str}")

        # 滚动到底部
        self.data_table.scrollToBottom()


class Level2DataPanel(QWidget):
    """
    Level-2 数据面板（增强版）
    集成现有ChartWidget设计风格，提供专业的Level-2行情数据显示
    新增功能：订单簿深度图表、数据导出、历史回放、自定义指标、价格预警、多股票对比
    """

    # 信号定义
    symbol_selected = pyqtSignal(str)
    data_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    alert_triggered = pyqtSignal(str, float, str)

    def __init__(self, parent=None, event_bus: EventBus = None,
                 realtime_manager: EnhancedRealtimeDataManager = None):
        super().__init__(parent)

        self.event_bus = event_bus
        self.realtime_manager = realtime_manager
        self.current_symbol = None
        self.subscribed_symbols = set()

        # 防抖定时器
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._on_debounced_symbol_change)
        self._pending_symbol = None

        # 数据缓存
        self.level2_data_cache = {}
        self.tick_data_cache = {}
        self.order_book_cache = {}
        self.historical_data = []

        # 自定义指标
        self.custom_indicators = {}

        # 价格预警
        self.price_alerts = {}

        # 多股票对比
        self.comparison_symbols = []

        # 更新控制
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(100)

        self.init_ui()
        self.setup_event_connections()

        logger.info("Level2DataPanel（增强版）初始化完成")

    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 控制面板
        control_panel = self._create_control_panel()
        layout.addWidget(control_panel)

        # 主要内容区域
        main_splitter = QSplitter(Qt.Horizontal)

        # 左侧：Level-2行情表格
        left_panel = self._create_level2_panel()
        main_splitter.addWidget(left_panel)

        # 右侧：Tick数据和订单簿（集成深度图表）
        right_panel = self._create_right_panel()
        main_splitter.addWidget(right_panel)

        # 设置分割比例
        main_splitter.setSizes([400, 500])
        layout.addWidget(main_splitter)

        # 状态栏
        status_bar = self._create_status_bar()
        layout.addWidget(status_bar)

    def _create_control_panel(self) -> QWidget:
        """创建控制面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel)
        panel.setMaximumHeight(80)

        layout = QVBoxLayout(panel)

        # 第一行：股票代码和订阅
        row1_layout = QHBoxLayout()

        row1_layout.addWidget(QLabel("股票代码:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.setEditable(True)
        self.symbol_combo.addItems(["000001", "000002", "600000", "600036", "000858"])
        self.symbol_combo.currentTextChanged.connect(self._on_symbol_changed)
        row1_layout.addWidget(self.symbol_combo)

        self.subscribe_btn = QPushButton("订阅Level-2")
        self.subscribe_btn.clicked.connect(self._toggle_subscription)
        row1_layout.addWidget(self.subscribe_btn)

        row1_layout.addWidget(QLabel("显示档位:"))
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(5, 20)
        self.depth_spin.setValue(10)
        self.depth_spin.valueChanged.connect(self._on_depth_changed)
        row1_layout.addWidget(self.depth_spin)

        row1_layout.addWidget(QLabel("刷新频率:"))
        self.refresh_combo = QComboBox()
        self.refresh_combo.addItems(["100ms", "200ms", "500ms", "1000ms"])
        self.refresh_combo.currentTextChanged.connect(self._on_refresh_rate_changed)
        row1_layout.addWidget(self.refresh_combo)

        row1_layout.addStretch()

        self.connection_status = QLabel("● 未连接")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        row1_layout.addWidget(self.connection_status)

        layout.addLayout(row1_layout)

        # 第二行：新增功能按钮
        row2_layout = QHBoxLayout()

        self.export_btn = QPushButton("导出数据")
        self.export_btn.clicked.connect(self._export_data)
        row2_layout.addWidget(self.export_btn)

        self.replay_btn = QPushButton("历史回放")
        self.replay_btn.clicked.connect(self._show_historical_replay)
        row2_layout.addWidget(self.replay_btn)

        self.custom_indicator_btn = QPushButton("自定义指标")
        self.custom_indicator_btn.clicked.connect(self._show_custom_indicator_dialog)
        row2_layout.addWidget(self.custom_indicator_btn)

        self.price_alert_btn = QPushButton("价格预警")
        self.price_alert_btn.clicked.connect(self._show_price_alert_dialog)
        row2_layout.addWidget(self.price_alert_btn)

        self.compare_btn = QPushButton("多股票对比")
        self.compare_btn.clicked.connect(self._show_comparison_dialog)
        row2_layout.addWidget(self.compare_btn)

        row2_layout.addStretch()

        layout.addLayout(row2_layout)

        return panel

    def _create_level2_panel(self) -> QWidget:
        """创建Level-2行情面板"""
        group = QGroupBox("Level-2 行情")
        layout = QVBoxLayout(group)

        # 基本行情信息
        info_panel = self._create_basic_info_panel()
        layout.addWidget(info_panel)

        # 五档行情表格
        self.level2_table = QTableWidget()
        self.level2_table.setColumnCount(6)
        self.level2_table.setHorizontalHeaderLabels([
            "档位", "买量", "买价", "卖价", "卖量", "比例"
        ])

        self.level2_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.level2_table.verticalHeader().setVisible(False)

        header = self.level2_table.horizontalHeader()
        header.setStretchLastSection(True)
        for i in range(6):
            header.resizeSection(i, 80)

        layout.addWidget(self.level2_table)

        return group

    def _create_basic_info_panel(self) -> QWidget:
        """创建基本信息面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel)
        panel.setMaximumHeight(80)

        layout = QGridLayout(panel)

        self.price_label = QLabel("--")
        self.change_label = QLabel("--")
        self.volume_label = QLabel("--")
        self.turnover_label = QLabel("--")

        font = QFont()
        font.setPointSize(12)
        font.setBold(True)

        self.price_label.setFont(font)
        self.change_label.setFont(font)

        layout.addWidget(QLabel("最新价:"), 0, 0)
        layout.addWidget(self.price_label, 0, 1)
        layout.addWidget(QLabel("涨跌幅:"), 0, 2)
        layout.addWidget(self.change_label, 0, 3)

        layout.addWidget(QLabel("成交量:"), 1, 0)
        layout.addWidget(self.volume_label, 1, 1)
        layout.addWidget(QLabel("成交额:"), 1, 2)
        layout.addWidget(self.turnover_label, 1, 3)

        return panel

    def _create_right_panel(self) -> QWidget:
        """创建右侧面板（Tick数据 + 订单簿）"""
        tab_widget = QTabWidget()

        # Tick数据标签页
        tick_tab = QWidget()
        tick_layout = QVBoxLayout(tick_tab)

        self.tick_table = QTableWidget()
        self.tick_table.setColumnCount(5)
        self.tick_table.setHorizontalHeaderLabels(["时间", "价格", "成交量", "方向", "类型"])
        self.tick_table.horizontalHeader().setStretchLastSection(True)
        tick_layout.addWidget(self.tick_table)

        tab_widget.addTab(tick_tab, "Tick数据")

        # 订单簿标签页（集成深度图表）
        order_book_tab = QWidget()
        order_book_layout = QVBoxLayout(order_book_tab)

        # 订单簿表格
        self.order_book_table = QTableWidget()
        self.order_book_table.setColumnCount(3)
        self.order_book_table.setHorizontalHeaderLabels(["买量", "价格", "卖量"])
        self.order_book_table.horizontalHeader().setStretchLastSection(True)
        order_book_layout.addWidget(self.order_book_table)

        # 订单簿深度图表
        self.order_book_widget = OrderBookWidget(
            parent=self,
            event_bus=self.event_bus
        )
        order_book_layout.addWidget(self.order_book_widget)

        # 自定义指标表格
        self.custom_indicator_table = QTableWidget()
        self.custom_indicator_table.setColumnCount(2)
        self.custom_indicator_table.setHorizontalHeaderLabels(["指标名称", "值"])
        self.custom_indicator_table.horizontalHeader().setStretchLastSection(True)
        order_book_layout.addWidget(self.custom_indicator_table)

        tab_widget.addTab(order_book_tab, "订单簿")

        return tab_widget

    def _create_status_bar(self) -> QWidget:
        """创建状态栏"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel)
        panel.setMaximumHeight(30)

        layout = QHBoxLayout(panel)

        self.status_label = QLabel("就绪")
        self.update_time_label = QLabel("更新时间: --")

        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(self.update_time_label)

        return panel

    def setup_event_connections(self):
        """设置事件连接"""
        if self.event_bus:
            self.event_bus.subscribe(RealtimeDataEvent, self._handle_realtime_data)
            self.event_bus.subscribe(TickDataEvent, self._handle_tick_data)
            self.event_bus.subscribe(OrderBookEvent, self._handle_order_book_data)
            
            # 订阅股票选择事件，实现与左侧面板的同步
            self.event_bus.subscribe(StockSelectedEvent, self._on_stock_selected)

    def _on_symbol_changed(self, symbol: str):
        """股票代码变更处理"""
        self.current_symbol = symbol
        self.symbol_selected.emit(symbol)
        logger.info(f"股票代码变更: {symbol}")

    def _on_stock_selected(self, event: StockSelectedEvent):
        """
        处理股票选择事件
        实现与左侧面板的同步
        使用防抖机制，避免频繁订阅/取消订阅
        """
        try:
            if not event or not event.stock_code:
                return

            # 获取股票代码
            symbol = event.stock_code
            
            # 如果股票代码没有变化，直接返回
            if self.current_symbol == symbol:
                return

            logger.info(f"接收到股票选择事件: {symbol}")

            # 使用防抖机制
            self._pending_symbol = symbol
            self._debounce_timer.start(300)  # 300ms防抖

        except Exception as e:
            logger.error(f"处理股票选择事件失败: {e}")
            self.error_occurred.emit(f"同步股票失败: {e}")

    def _on_debounced_symbol_change(self):
        """防抖后的股票变更处理"""
        try:
            if not self._pending_symbol:
                return

            symbol = self._pending_symbol
            self._pending_symbol = None

            logger.info(f"防抖后处理股票变更: {symbol}")

            # 取消订阅旧的股票
            if self.current_symbol and self.is_subscribed(self.current_symbol):
                self._unsubscribe_symbol(self.current_symbol)

            # 设置新的股票代码
            self.set_symbol(symbol)

            # 自动订阅新的股票
            self._subscribe_symbol(symbol)

            logger.info(f"已同步到股票: {symbol}")

        except Exception as e:
            logger.error(f"防抖后处理股票变更失败: {e}")
            self.error_occurred.emit(f"同步股票失败: {e}")

    def _toggle_subscription(self):
        """切换订阅状态"""
        if not self.current_symbol:
            QMessageBox.warning(self, "提示", "请先选择股票代码")
            return

        if self.is_subscribed(self.current_symbol):
            self._unsubscribe_symbol(self.current_symbol)
            self.subscribe_btn.setText("订阅Level-2")
            self.connection_status.setText("● 未连接")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        else:
            self._subscribe_symbol(self.current_symbol)
            self.subscribe_btn.setText("取消订阅")
            self.connection_status.setText("● 已连接")
            self.connection_status.setStyleSheet("color: green; font-weight: bold;")

    def _subscribe_symbol(self, symbol: str):
        """订阅股票Level-2数据"""
        try:
            if self.realtime_manager:
                asyncio.create_task(self.realtime_manager.subscribe_realtime_data(
                    [symbol], [DataType.LEVEL2_DATA, DataType.TICK_DATA, DataType.ORDER_BOOK],
                    AssetType.STOCK_A
                ))

            self.subscribed_symbols.add(symbol)
            logger.info(f"已订阅 {symbol} 的Level-2数据")
        except Exception as e:
            logger.error(f"订阅失败: {e}")
            self.error_occurred.emit(f"订阅失败: {e}")

    def _unsubscribe_symbol(self, symbol: str):
        """取消订阅股票Level-2数据"""
        try:
            if self.realtime_manager:
                asyncio.create_task(self.realtime_manager.unsubscribe_realtime_data(
                    [symbol], [DataType.LEVEL2_DATA, DataType.TICK_DATA, DataType.ORDER_BOOK]
                ))

            self.subscribed_symbols.discard(symbol)
            logger.info(f"已取消订阅 {symbol} 的Level-2数据")
        except Exception as e:
            logger.error(f"取消订阅失败: {e}")
            self.error_occurred.emit(f"取消订阅失败: {e}")

    def is_subscribed(self, symbol: str) -> bool:
        """检查是否已订阅"""
        return symbol in self.subscribed_symbols

    def _handle_realtime_data(self, event: RealtimeDataEvent):
        """处理Level-2实时数据"""
        try:
            data = event.realtime_data
            symbol = data.get('symbol')

            if symbol != self.current_symbol:
                return

            # 更新缓存
            self.level2_data_cache[symbol] = data

            # 保存历史数据
            self.historical_data.append(data)
            if len(self.historical_data) > 10000:
                self.historical_data.pop(0)

            # 更新UI
            self._update_level2_display(data)

            # 检查价格预警
            self._check_price_alerts(data)

            # 更新自定义指标
            self._update_custom_indicators()

            self.data_updated.emit(data)

        except Exception as e:
            logger.error(f"处理Level-2数据失败: {e}")
            self.error_occurred.emit(f"处理数据失败: {e}")

    def _handle_tick_data(self, event: TickDataEvent):
        """处理Tick数据"""
        try:
            data = event.tick_data
            symbol = data.get('symbol')

            if symbol != self.current_symbol:
                return

            # 更新缓存
            if symbol not in self.tick_data_cache:
                self.tick_data_cache[symbol] = []

            self.tick_data_cache[symbol].append(data)

            # 限制缓存大小
            if len(self.tick_data_cache[symbol]) > 100:
                self.tick_data_cache[symbol].pop(0)

            # 更新UI
            self._update_tick_display(data)

        except Exception as e:
            logger.error(f"处理Tick数据失败: {e}")

    def _handle_order_book_data(self, event: OrderBookEvent):
        """处理订单簿数据"""
        try:
            data = event.order_book_data
            symbol = data.get('symbol')

            if symbol != self.current_symbol:
                return

            # 更新缓存
            self.order_book_cache[symbol] = data

            # 更新UI
            self._update_order_book_display(data)

        except Exception as e:
            logger.error(f"处理订单簿数据失败: {e}")

    def _update_display(self):
        """定时更新显示"""
        try:
            if self.current_symbol:
                self.update_time_label.setText(f"更新时间: {datetime.now().strftime('%H:%M:%S')}")

        except Exception as e:
            logger.error(f"更新显示失败: {e}")

    def _update_level2_display(self, data: Dict):
        """更新Level-2数据显示"""
        try:
            # 更新基本信息
            price = data.get('price', 0)
            change = data.get('change', 0)
            change_pct = data.get('change_pct', 0)
            volume = data.get('volume', 0)
            turnover = data.get('turnover', 0)

            self.price_label.setText(f"{price:.2f}")
            self.change_label.setText(f"{change:+.2f} ({change_pct:+.2f}%)")
            self.volume_label.setText(f"{volume:,}")
            self.turnover_label.setText(f"{turnover:,.0f}")

            # 更新五档行情
            bids = data.get('bids', [])
            asks = data.get('asks', [])

            self.level2_table.setRowCount(max(len(bids), len(asks)))

            for i in range(max(len(bids), len(asks))):
                if i < len(bids):
                    bid = bids[i]
                    self.level2_table.setItem(i, 0, QTableWidgetItem(f"买{i+1}"))
                    self.level2_table.setItem(i, 1, QTableWidgetItem(f"{bid.get('volume', 0):,}"))
                    self.level2_table.setItem(i, 2, QTableWidgetItem(f"{bid.get('price', 0):.2f}"))
                else:
                    self.level2_table.setItem(i, 0, QTableWidgetItem(""))
                    self.level2_table.setItem(i, 1, QTableWidgetItem(""))
                    self.level2_table.setItem(i, 2, QTableWidgetItem(""))

                if i < len(asks):
                    ask = asks[i]
                    self.level2_table.setItem(i, 3, QTableWidgetItem(f"{ask.get('price', 0):.2f}"))
                    self.level2_table.setItem(i, 4, QTableWidgetItem(f"{ask.get('volume', 0):,}"))
                else:
                    self.level2_table.setItem(i, 3, QTableWidgetItem(""))
                    self.level2_table.setItem(i, 4, QTableWidgetItem(""))

                # 计算买卖比例
                if i < len(bids) and i < len(asks):
                    bid_vol = bids[i].get('volume', 0)
                    ask_vol = asks[i].get('volume', 0)
                    if ask_vol > 0:
                        ratio = bid_vol / ask_vol
                        self.level2_table.setItem(i, 5, QTableWidgetItem(f"{ratio:.2f}"))
                    else:
                        self.level2_table.setItem(i, 5, QTableWidgetItem("∞"))
                else:
                    self.level2_table.setItem(i, 5, QTableWidgetItem(""))

        except Exception as e:
            logger.error(f"更新Level-2显示失败: {e}")

    def _update_tick_display(self, data: Dict):
        """更新Tick数据显示"""
        try:
            timestamp = data.get('timestamp', '')
            price = data.get('price', 0)
            volume = data.get('volume', 0)
            tick_type = data.get('type', 'unknown')

            row = self.tick_table.rowCount()
            self.tick_table.insertRow(0)

            time_str = timestamp.split('T')[1][:8] if 'T' in timestamp else timestamp
            self.tick_table.setItem(0, 0, QTableWidgetItem(time_str))
            self.tick_table.setItem(0, 1, QTableWidgetItem(f"{price:.2f}"))
            self.tick_table.setItem(0, 2, QTableWidgetItem(f"{volume:,}"))

            direction = "↑" if tick_type == "buy" else "↓"
            self.tick_table.setItem(0, 3, QTableWidgetItem(direction))
            self.tick_table.setItem(0, 4, QTableWidgetItem(tick_type))

            # 限制行数
            if self.tick_table.rowCount() > 100:
                self.tick_table.removeRow(100)

        except Exception as e:
            logger.error(f"更新Tick显示失败: {e}")

    def _update_order_book_display(self, data: Dict):
        """更新订单簿数据显示"""
        try:
            bids = data.get('bids', [])
            asks = data.get('asks', [])

            self.order_book_table.setRowCount(max(len(bids), len(asks)))

            for i in range(max(len(bids), len(asks))):
                if i < len(bids):
                    bid = bids[i]
                    self.order_book_table.setItem(i, 0, QTableWidgetItem(f"{bid.get('volume', 0):,}"))
                else:
                    self.order_book_table.setItem(i, 0, QTableWidgetItem(""))

                if i < len(bids) and i < len(asks):
                    mid_price = (bids[i].get('price', 0) + asks[i].get('price', 0)) / 2
                    self.order_book_table.setItem(i, 1, QTableWidgetItem(f"{mid_price:.2f}"))
                elif i < len(bids):
                    self.order_book_table.setItem(i, 1, QTableWidgetItem(f"{bids[i].get('price', 0):.2f}"))
                elif i < len(asks):
                    self.order_book_table.setItem(i, 1, QTableWidgetItem(f"{asks[i].get('price', 0):.2f}"))
                else:
                    self.order_book_table.setItem(i, 1, QTableWidgetItem(""))

                if i < len(asks):
                    ask = asks[i]
                    self.order_book_table.setItem(i, 2, QTableWidgetItem(f"{ask.get('volume', 0):,}"))
                else:
                    self.order_book_table.setItem(i, 2, QTableWidgetItem(""))

        except Exception as e:
            logger.error(f"更新订单簿显示失败: {e}")

    def _check_price_alerts(self, data: Dict):
        """检查价格预警"""
        try:
            if not self.current_symbol:
                return

            alerts = self.price_alerts.get(self.current_symbol, [])
            if not alerts:
                return

            price = data.get('price', 0)

            for alert in alerts:
                if not alert.get('enabled', True):
                    continue

                alert_type = alert.get('type')
                alert_price = alert.get('price')

                if alert_type == '高于' and price > alert_price:
                    self.alert_triggered.emit(self.current_symbol, price, f"价格高于 {alert_price:.2f}")
                    QMessageBox.information(self, "价格预警", f"{self.current_symbol} 价格 {price:.2f} 高于 {alert_price:.2f}")
                elif alert_type == '低于' and price < alert_price:
                    self.alert_triggered.emit(self.current_symbol, price, f"价格低于 {alert_price:.2f}")
                    QMessageBox.information(self, "价格预警", f"{self.current_symbol} 价格 {price:.2f} 低于 {alert_price:.2f}")

        except Exception as e:
            logger.error(f"检查价格预警失败: {e}")

    def _update_custom_indicators(self):
        """更新自定义指标"""
        try:
            if not self.current_symbol or not self.custom_indicators:
                return

            data = self.level2_data_cache.get(self.current_symbol, {})
            if not data:
                return

            # 准备计算数据
            calc_data = {
                'bid_volume': data.get('bid_volume', 0),
                'ask_volume': data.get('ask_volume', 0),
                'bid_price': data.get('bid_price', 0),
                'ask_price': data.get('ask_price', 0),
                'total_volume': data.get('volume', 0)
            }

            self.custom_indicator_table.setRowCount(len(self.custom_indicators))

            for row, (name, formula) in enumerate(self.custom_indicators.items()):
                try:
                    result = eval(formula, {"__builtins__": None}, calc_data)
                    self.custom_indicator_table.setItem(row, 0, QTableWidgetItem(name))
                    self.custom_indicator_table.setItem(row, 1, QTableWidgetItem(f"{result:.2f}"))
                except Exception as e:
                    self.custom_indicator_table.setItem(row, 0, QTableWidgetItem(name))
                    self.custom_indicator_table.setItem(row, 1, QTableWidgetItem("计算错误"))

        except Exception as e:
            logger.error(f"更新自定义指标失败: {e}")

    def _on_depth_changed(self, depth: int):
        """档位变更处理"""
        logger.info(f"显示档位变更: {depth}")

    def _on_refresh_rate_changed(self, rate: str):
        """刷新频率变更处理"""
        rate_map = {
            "100ms": 100,
            "200ms": 200,
            "500ms": 500,
            "1000ms": 1000
        }
        self.update_timer.setInterval(rate_map.get(rate, 100))
        logger.info(f"刷新频率变更: {rate}")

    def _export_data(self):
        """导出数据"""
        try:
            if not self.current_symbol:
                QMessageBox.warning(self, "提示", "请先选择股票代码")
                return

            # 创建导出对话框
            dialog = QFileDialog()
            dialog.setAcceptMode(QFileDialog.AcceptSave)
            dialog.setNameFilter("CSV文件 (*.csv);;Excel文件 (*.xlsx);;JSON文件 (*.json)")

            if dialog.exec_() == QFileDialog.Accepted:
                file_path = dialog.selectedFiles()[0]

                if file_path.endswith('.csv'):
                    self._export_to_csv(file_path)
                elif file_path.endswith('.xlsx'):
                    self._export_to_excel(file_path)
                elif file_path.endswith('.json'):
                    self._export_to_json(file_path)
                else:
                    QMessageBox.warning(self, "错误", "不支持的文件格式")

        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            QMessageBox.critical(self, "错误", f"导出数据失败: {e}")

    def _export_to_csv(self, file_path: str):
        """导出为CSV"""
        try:
            tick_data = self.tick_data_cache.get(self.current_symbol, [])

            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["时间", "价格", "成交量", "方向", "类型"])

                for data in tick_data:
                    timestamp = data.get('timestamp', '')
                    time_str = timestamp.split('T')[1][:8] if 'T' in timestamp else timestamp
                    writer.writerow([
                        time_str,
                        data.get('price', 0),
                        data.get('volume', 0),
                        data.get('type', ''),
                        data.get('type', '')
                    ])

            QMessageBox.information(self, "成功", f"数据已导出到 {file_path}")
            logger.info(f"数据已导出到 {file_path}")

        except Exception as e:
            logger.error(f"导出CSV失败: {e}")
            raise

    def _export_to_excel(self, file_path: str):
        """导出为Excel"""
        try:
            tick_data = self.tick_data_cache.get(self.current_symbol, [])

            df = pd.DataFrame(tick_data)
            df.to_excel(file_path, index=False)

            QMessageBox.information(self, "成功", f"数据已导出到 {file_path}")
            logger.info(f"数据已导出到 {file_path}")

        except Exception as e:
            logger.error(f"导出Excel失败: {e}")
            raise

    def _export_to_json(self, file_path: str):
        """导出为JSON"""
        try:
            export_data = {
                'symbol': self.current_symbol,
                'export_time': datetime.now().isoformat(),
                'tick_data': self.tick_data_cache.get(self.current_symbol, []),
                'level2_data': self.level2_data_cache.get(self.current_symbol, {}),
                'order_book_data': self.order_book_cache.get(self.current_symbol, {}),
                'historical_data': self.historical_data[-100:]
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            QMessageBox.information(self, "成功", f"数据已导出到 {file_path}")
            logger.info(f"数据已导出到 {file_path}")

        except Exception as e:
            logger.error(f"导出JSON失败: {e}")
            raise

    def _show_historical_replay(self):
        """显示历史数据回放对话框"""
        try:
            if not self.historical_data:
                QMessageBox.warning(self, "提示", "没有可回放的历史数据")
                return

            dialog = HistoricalReplayDialog(self, self.historical_data)
            dialog.exec_()

        except Exception as e:
            logger.error(f"显示历史回放失败: {e}")
            QMessageBox.critical(self, "错误", f"显示历史回放失败: {e}")

    def _show_custom_indicator_dialog(self):
        """显示自定义指标对话框"""
        try:
            dialog = CustomIndicatorDialog(self)

            # 加载现有指标
            if self.custom_indicators:
                for name, formula in self.custom_indicators.items():
                    row = dialog.indicator_table.rowCount()
                    dialog.indicator_table.insertRow(row)

                    name_edit = QLineEdit(name)
                    dialog.indicator_table.setCellWidget(row, 0, name_edit)

                    formula_edit = QLineEdit(formula)
                    dialog.indicator_table.setCellWidget(row, 1, formula_edit)

                    del_btn = QPushButton("删除")
                    del_btn.clicked.connect(lambda: dialog.indicator_table.removeRow(row))
                    dialog.indicator_table.setCellWidget(row, 2, del_btn)

                    test_btn = QPushButton("测试")
                    test_btn.clicked.connect(lambda: dialog._test_indicator(formula))
                    dialog.indicator_table.setCellWidget(row, 3, test_btn)

            if dialog.exec_() == QDialog.Accepted:
                self.custom_indicators = dialog.get_indicators()
                self._update_custom_indicators()
                logger.info(f"自定义指标已更新: {list(self.custom_indicators.keys())}")

        except Exception as e:
            logger.error(f"显示自定义指标对话框失败: {e}")
            QMessageBox.critical(self, "错误", f"显示自定义指标对话框失败: {e}")

    def _show_price_alert_dialog(self):
        """显示价格预警对话框"""
        try:
            current_price = 0
            if self.current_symbol:
                data = self.level2_data_cache.get(self.current_symbol, {})
                current_price = data.get('price', 0)

            dialog = PriceAlertDialog(self, current_price)

            # 加载现有预警
            if self.current_symbol and self.current_symbol in self.price_alerts:
                for alert in self.price_alerts[self.current_symbol]:
                    row = dialog.alert_table.rowCount()
                    dialog.alert_table.insertRow(row)

                    dialog.alert_table.setItem(row, 0, QTableWidgetItem(alert.get('type', '')))
                    dialog.alert_table.setItem(row, 1, QTableWidgetItem(f"{alert.get('price', 0):.2f}"))

                    enable_check = QCheckBox()
                    enable_check.setChecked(alert.get('enabled', True))
                    dialog.alert_table.setCellWidget(row, 2, enable_check)

                    del_btn = QPushButton("删除")
                    del_btn.clicked.connect(lambda: dialog.alert_table.removeRow(row))
                    dialog.alert_table.setCellWidget(row, 3, del_btn)

            if dialog.exec_() == QDialog.Accepted:
                self.price_alerts[self.current_symbol] = dialog.get_alerts()
                logger.info(f"价格预警已更新: {len(self.price_alerts[self.current_symbol])} 个预警")

        except Exception as e:
            logger.error(f"显示价格预警对话框失败: {e}")
            QMessageBox.critical(self, "错误", f"显示价格预警对话框失败: {e}")

    def _show_comparison_dialog(self):
        """显示多股票对比对话框"""
        try:
            QMessageBox.information(self, "功能开发中", "多股票对比功能正在开发中，敬请期待！")
            logger.info("多股票对比功能待实现")

        except Exception as e:
            logger.error(f"显示对比对话框失败: {e}")

    def set_symbol(self, symbol: str):
        """设置当前股票代码"""
        self.current_symbol = symbol
        self.symbol_combo.setCurrentText(symbol)
        self.symbol_selected.emit(symbol)
        logger.info(f"设置股票代码: {symbol}")

    def get_current_symbol(self) -> Optional[str]:
        """获取当前股票代码"""
        return self.current_symbol

    def _clear_displays(self):
        """清空显示"""
        try:
            self.level2_table.setRowCount(0)
            self.tick_table.setRowCount(0)
            self.order_book_table.setRowCount(0)
            self.custom_indicator_table.setRowCount(0)

            self.price_label.setText("--")
            self.change_label.setText("--")
            self.volume_label.setText("--")
            self.turnover_label.setText("--")

        except Exception as e:
            logger.error(f"清空显示失败: {e}")

    def closeEvent(self, event):
        """关闭事件"""
        try:
            # 取消所有订阅
            for symbol in list(self.subscribed_symbols):
                self._unsubscribe_symbol(symbol)

            # 取消订阅事件
            if self.event_bus:
                self.event_bus.unsubscribe(StockSelectedEvent, self._on_stock_selected)

            # 停止防抖定时器
            if self._debounce_timer.isActive():
                self._debounce_timer.stop()

            # 停止更新定时器
            self.update_timer.stop()

            logger.info("Level2DataPanel 已关闭")

        except Exception as e:
            logger.error(f"关闭面板失败: {e}")

        event.accept()
