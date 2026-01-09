#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Level-2 数据面板
提供Level-2行情数据的实时显示和交互功能
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QSplitter, QFrame, QScrollArea, QPushButton, QComboBox, QSpinBox,
    QGroupBox, QGridLayout, QProgressBar, QTabWidget
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QPalette
from loguru import logger

from core.services.enhanced_realtime_data_manager import EnhancedRealtimeDataManager
from core.plugin_types import DataType, AssetType
from core.events.event_bus import EventBus, RealtimeDataEvent, TickDataEvent, OrderBookEvent


class Level2DataPanel(QWidget):
    """
    Level-2 数据面板
    集成现有ChartWidget设计风格，提供专业的Level-2行情数据显示
    """

    # 信号定义
    symbol_selected = pyqtSignal(str)  # 股票选择信号
    data_updated = pyqtSignal(dict)    # 数据更新信号
    error_occurred = pyqtSignal(str)   # 错误信号

    def __init__(self, parent=None, event_bus: EventBus = None,
                 realtime_manager: EnhancedRealtimeDataManager = None):
        super().__init__(parent)

        self.event_bus = event_bus
        self.realtime_manager = realtime_manager
        self.current_symbol = None
        self.subscribed_symbols = set()

        # 数据缓存
        self.level2_data_cache = {}
        self.tick_data_cache = {}
        self.order_book_cache = {}

        # 更新控制
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(100)  # 100ms更新频率

        self.init_ui()
        self.setup_event_connections()

        logger.info("Level2DataPanel 初始化完成")

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

        # 右侧：Tick数据和订单簿
        right_panel = self._create_right_panel()
        main_splitter.addWidget(right_panel)

        # 设置分割比例
        main_splitter.setSizes([400, 300])
        layout.addWidget(main_splitter)

        # 状态栏
        status_bar = self._create_status_bar()
        layout.addWidget(status_bar)


    def _create_control_panel(self) -> QWidget:
        """创建控制面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel)
        panel.setMaximumHeight(60)

        layout = QHBoxLayout(panel)

        # 股票代码选择
        layout.addWidget(QLabel("股票代码:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.setEditable(True)
        self.symbol_combo.addItems(["000001", "000002", "600000", "600036", "000858"])
        self.symbol_combo.currentTextChanged.connect(self._on_symbol_changed)
        layout.addWidget(self.symbol_combo)

        # 订阅控制
        self.subscribe_btn = QPushButton("订阅Level-2")
        self.subscribe_btn.clicked.connect(self._toggle_subscription)
        layout.addWidget(self.subscribe_btn)

        # 深度档位设置
        layout.addWidget(QLabel("显示档位:"))
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(5, 20)
        self.depth_spin.setValue(10)
        self.depth_spin.valueChanged.connect(self._on_depth_changed)
        layout.addWidget(self.depth_spin)

        # 刷新频率设置
        layout.addWidget(QLabel("刷新频率:"))
        self.refresh_combo = QComboBox()
        self.refresh_combo.addItems(["100ms", "200ms", "500ms", "1000ms"])
        self.refresh_combo.currentTextChanged.connect(self._on_refresh_rate_changed)
        layout.addWidget(self.refresh_combo)

        layout.addStretch()

        # 连接状态指示器
        self.connection_status = QLabel("● 未连接")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.connection_status)

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

        # 设置表格属性
        self.level2_table.setAlternatingRowColors(True)
        self.level2_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.level2_table.verticalHeader().setVisible(False)

        # 调整列宽
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

        # 创建信息标签
        self.price_label = QLabel("--")
        self.change_label = QLabel("--")
        self.volume_label = QLabel("--")
        self.turnover_label = QLabel("--")

        # 设置字体
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)

        self.price_label.setFont(font)
        self.change_label.setFont(font)

        # 布局
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
        """创建右侧面板"""
        tab_widget = QTabWidget()

        # Tick数据标签页
        tick_panel = self._create_tick_panel()
        tab_widget.addTab(tick_panel, "Tick数据")

        # 订单簿标签页
        order_book_panel = self._create_order_book_panel()
        tab_widget.addTab(order_book_panel, "订单簿")

        # 统计信息标签页
        stats_panel = self._create_stats_panel()
        tab_widget.addTab(stats_panel, "统计信息")

        return tab_widget

    def _create_tick_panel(self) -> QWidget:
        """创建Tick数据面板"""
        group = QGroupBox("Tick 数据流")
        layout = QVBoxLayout(group)

        # Tick数据表格
        self.tick_table = QTableWidget()
        self.tick_table.setColumnCount(5)
        self.tick_table.setHorizontalHeaderLabels([
            "时间", "价格", "成交量", "方向", "类型"
        ])

        self.tick_table.setAlternatingRowColors(True)
        self.tick_table.verticalHeader().setVisible(False)
        # 设置初始行数，后续通过逻辑控制最大行数
        self.tick_table.setRowCount(0)
        self.max_tick_rows = 100  # 限制显示行数

        layout.addWidget(self.tick_table)

        return group

    def _create_order_book_panel(self) -> QWidget:
        """创建订单簿面板"""
        group = QGroupBox("订单簿深度")
        layout = QVBoxLayout(group)

        # 订单簿表格
        self.order_book_table = QTableWidget()
        self.order_book_table.setColumnCount(4)
        self.order_book_table.setHorizontalHeaderLabels([
            "价格", "数量", "累计", "占比"
        ])

        self.order_book_table.setAlternatingRowColors(True)
        self.order_book_table.verticalHeader().setVisible(False)

        layout.addWidget(self.order_book_table)

        return group

    def _create_stats_panel(self) -> QWidget:
        """创建统计信息面板"""
        group = QGroupBox("实时统计")
        layout = QVBoxLayout(group)

        # 统计信息网格
        stats_layout = QGridLayout()

        # 创建统计标签
        self.stats_labels = {}
        stats_items = [
            ("总成交量", "total_volume"),
            ("总成交额", "total_turnover"),
            ("平均价格", "avg_price"),
            ("最高价", "high_price"),
            ("最低价", "low_price"),
            ("买卖比", "buy_sell_ratio"),
            ("大单净流入", "large_order_flow"),
            ("活跃度", "activity_level")
        ]

        for i, (label, key) in enumerate(stats_items):
            row, col = i // 2, (i % 2) * 2
            stats_layout.addWidget(QLabel(f"{label}:"), row, col)

            value_label = QLabel("--")
            value_label.setStyleSheet("font-weight: bold; color: #2E86AB;")
            stats_layout.addWidget(value_label, row, col + 1)

            self.stats_labels[key] = value_label

        layout.addLayout(stats_layout)
        layout.addStretch()

        return group

    def _create_status_bar(self) -> QWidget:
        """创建状态栏"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel)
        panel.setMaximumHeight(30)

        layout = QHBoxLayout(panel)

        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # 数据更新时间
        self.update_time_label = QLabel("--")
        layout.addWidget(self.update_time_label)

        # 数据速率
        self.data_rate_label = QLabel("0 tick/s")
        layout.addWidget(self.data_rate_label)
        return panel

    def setup_event_connections(self):
        """设置事件连接"""
        if self.event_bus:
            # 订阅实时数据事件
            self.event_bus.subscribe(RealtimeDataEvent, self._handle_realtime_data)
            self.event_bus.subscribe(TickDataEvent, self._handle_tick_data)
            self.event_bus.subscribe(OrderBookEvent, self._handle_order_book_data)

            logger.info("Level2DataPanel 事件连接已建立")

    def _on_symbol_changed(self, symbol: str):
        """股票代码变更处理"""
        if symbol and symbol != self.current_symbol:
            self.current_symbol = symbol
            self.symbol_selected.emit(symbol)

            # 如果已订阅，重新订阅新股票
            if symbol in self.subscribed_symbols:
                self._subscribe_symbol(symbol)

            logger.info(f"股票代码已切换到: {symbol}")

    def _toggle_subscription(self):
        """切换订阅状态"""
        if not self.current_symbol:
            self.error_occurred.emit("请先选择股票代码")
            return

        if self.current_symbol in self.subscribed_symbols:
            self._unsubscribe_symbol(self.current_symbol)
        else:
            self._subscribe_symbol(self.current_symbol)

    async def _subscribe_symbol(self, symbol: str):
        """订阅股票的Level-2数据"""
        if not self.realtime_manager:
            self.error_occurred.emit("实时数据管理器未初始化")
            return

        try:
            # 订阅Level-2、Tick和订单簿数据
            await self.realtime_manager.subscribe_realtime_data(
                symbols=[symbol],
                data_types=[DataType.LEVEL2, DataType.TICK_DATA, DataType.ORDER_BOOK],
                asset_type=AssetType.STOCK_A
            )

            self.subscribed_symbols.add(symbol)
            self.subscribe_btn.setText("取消订阅")
            self.connection_status.setText("● 已连接")
            self.connection_status.setStyleSheet("color: green; font-weight: bold;")
            self.status_label.setText(f"已订阅 {symbol} 的Level-2数据")

            logger.info(f"成功订阅 {symbol} 的Level-2数据")

        except Exception as e:
            self.error_occurred.emit(f"订阅失败: {str(e)}")
            logger.error(f"订阅Level-2数据失败: {e}")

    def _unsubscribe_symbol(self, symbol: str):
        """取消订阅股票的Level-2数据"""
        if symbol in self.subscribed_symbols:
            self.subscribed_symbols.remove(symbol)

            self.subscribe_btn.setText("订阅Level-2")
            self.connection_status.setText("● 未连接")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")
            self.status_label.setText("已取消订阅")

            # 清空数据显示
            self._clear_displays()

            logger.info(f"已取消订阅 {symbol} 的Level-2数据")

    def _on_depth_changed(self, depth: int):
        """档位数量变更处理"""
        self.level2_table.setRowCount(depth)
        logger.debug(f"Level-2显示档位已调整为: {depth}")

    def _on_refresh_rate_changed(self, rate_text: str):
        """刷新频率变更处理"""
        rate_map = {
            "100ms": 100,
            "200ms": 200,
            "500ms": 500,
            "1000ms": 1000
        }

        interval = rate_map.get(rate_text, 100)
        self.update_timer.setInterval(interval)

        logger.debug(f"刷新频率已调整为: {interval}ms")

    @pyqtSlot(object)
    def _handle_realtime_data(self, event: RealtimeDataEvent):
        """处理Level-2实时数据事件"""
        try:
            data = event.realtime_data
            symbol = data.get('symbol')

            if symbol == self.current_symbol:
                self.level2_data_cache[symbol] = data
                logger.debug(f"收到 {symbol} 的Level-2数据")

        except Exception as e:
            logger.error(f"处理Level-2数据失败: {e}")

    @pyqtSlot(object)
    def _handle_tick_data(self, event: TickDataEvent):
        """处理Tick数据事件"""
        try:
            data = event.tick_data
            symbol = data.get('symbol')

            if symbol == self.current_symbol:
                if symbol not in self.tick_data_cache:
                    self.tick_data_cache[symbol] = []

                self.tick_data_cache[symbol].append(data)

                # 保持最近100条记录
                if len(self.tick_data_cache[symbol]) > 100:
                    self.tick_data_cache[symbol] = self.tick_data_cache[symbol][-100:]

                logger.debug(f"收到 {symbol} 的Tick数据")

        except Exception as e:
            logger.error(f"处理Tick数据失败: {e}")

    @pyqtSlot(object)
    def _handle_order_book_data(self, event: OrderBookEvent):
        """处理订单簿数据事件"""
        try:
            data = event.order_book_data
            symbol = data.get('symbol')

            if symbol == self.current_symbol:
                self.order_book_cache[symbol] = data
                logger.debug(f"收到 {symbol} 的订单簿数据")

        except Exception as e:
            logger.error(f"处理订单簿数据失败: {e}")

    def _update_display(self):
        """更新显示内容"""
        if not self.current_symbol:
            return

        try:
            # 更新Level-2行情表格
            self._update_level2_table()

            # 更新基本信息
            self._update_basic_info()

            # 更新Tick数据表格
            self._update_tick_table()

            # 更新订单簿表格
            self._update_order_book_table()

            # 更新统计信息
            self._update_stats()

            # 更新状态栏
            self._update_status_bar()

        except Exception as e:
            logger.error(f"更新显示失败: {e}")

    def _update_level2_table(self):
        """更新Level-2行情表格"""
        symbol = self.current_symbol
        if symbol not in self.level2_data_cache:
            return

        data = self.level2_data_cache[symbol]

        # 模拟Level-2数据结构
        bids = [(99.95 - i * 0.01, 1000 + i * 100) for i in range(10)]
        asks = [(100.05 + i * 0.01, 1200 + i * 150) for i in range(10)]

        depth = self.depth_spin.value()
        self.level2_table.setRowCount(depth)

        for i in range(depth):
            if i < len(bids) and i < len(asks):
                bid_price, bid_volume = bids[i]
                ask_price, ask_volume = asks[i]

                # 档位
                self.level2_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))

                # 买量
                buy_item = QTableWidgetItem(f"{bid_volume:,}")
                buy_item.setForeground(QColor("#E74C3C"))  # 红色
                self.level2_table.setItem(i, 1, buy_item)

                # 买价
                buy_price_item = QTableWidgetItem(f"{bid_price:.2f}")
                buy_price_item.setForeground(QColor("#E74C3C"))
                self.level2_table.setItem(i, 2, buy_price_item)

                # 卖价
                sell_price_item = QTableWidgetItem(f"{ask_price:.2f}")
                sell_price_item.setForeground(QColor("#27AE60"))  # 绿色
                self.level2_table.setItem(i, 3, sell_price_item)

                # 卖量
                sell_item = QTableWidgetItem(f"{ask_volume:,}")
                sell_item.setForeground(QColor("#27AE60"))
                self.level2_table.setItem(i, 4, sell_item)

                # 比例
                ratio = bid_volume / (bid_volume + ask_volume) * 100
                self.level2_table.setItem(i, 5, QTableWidgetItem(f"{ratio:.1f}%"))

    def _update_basic_info(self):
        """更新基本信息"""
        # 模拟基本行情数据
        self.price_label.setText("100.25")
        self.price_label.setStyleSheet("color: #E74C3C; font-weight: bold;")

        self.change_label.setText("+2.35%")
        self.change_label.setStyleSheet("color: #E74C3C; font-weight: bold;")

        self.volume_label.setText("1,234,567")
        self.turnover_label.setText("123.45万")

    def _update_tick_table(self):
        """更新Tick数据表格"""
        symbol = self.current_symbol
        if symbol not in self.tick_data_cache:
            return

        tick_data = self.tick_data_cache[symbol]

        # 显示最近的20条Tick数据
        display_count = min(20, len(tick_data))
        self.tick_table.setRowCount(display_count)

        for i, tick in enumerate(tick_data[-display_count:]):
            timestamp = tick.get('timestamp', '')
            price = tick.get('price', 0)
            volume = tick.get('volume', 0)
            tick_type = tick.get('type', 'unknown')

            # 时间
            time_str = timestamp.split('T')[1][:8] if 'T' in timestamp else timestamp
            self.tick_table.setItem(i, 0, QTableWidgetItem(time_str))

            # 价格
            price_item = QTableWidgetItem(f"{price:.2f}")
            color = QColor("#E74C3C") if tick_type == "buy" else QColor("#27AE60")
            price_item.setForeground(color)
            self.tick_table.setItem(i, 1, price_item)

            # 成交量
            self.tick_table.setItem(i, 2, QTableWidgetItem(f"{volume:,}"))

            # 方向
            direction = "↑" if tick_type == "buy" else "↓"
            direction_item = QTableWidgetItem(direction)
            direction_item.setForeground(color)
            self.tick_table.setItem(i, 3, direction_item)

            # 类型
            self.tick_table.setItem(i, 4, QTableWidgetItem(tick_type))

    def _update_order_book_table(self):
        """更新订单簿表格"""
        symbol = self.current_symbol
        if symbol not in self.order_book_cache:
            return

        data = self.order_book_cache[symbol]
        bids = data.get('bids', [])
        asks = data.get('asks', [])

        # 合并买卖盘数据
        all_orders = []
        for bid in bids[:10]:
            all_orders.append(('买', bid['price'], bid['volume']))
        for ask in asks[:10]:
            all_orders.append(('卖', ask['price'], ask['volume']))

        # 按价格排序
        all_orders.sort(key=lambda x: x[1], reverse=True)

        self.order_book_table.setRowCount(len(all_orders))

        total_volume = sum(order[2] for order in all_orders)
        cumulative = 0

        for i, (side, price, volume) in enumerate(all_orders):
            cumulative += volume

            # 价格
            price_item = QTableWidgetItem(f"{price:.2f}")
            color = QColor("#E74C3C") if side == "买" else QColor("#27AE60")
            price_item.setForeground(color)
            self.order_book_table.setItem(i, 0, price_item)

            # 数量
            self.order_book_table.setItem(i, 1, QTableWidgetItem(f"{volume:,}"))

            # 累计
            self.order_book_table.setItem(i, 2, QTableWidgetItem(f"{cumulative:,}"))

            # 占比
            ratio = volume / total_volume * 100 if total_volume > 0 else 0
            self.order_book_table.setItem(i, 3, QTableWidgetItem(f"{ratio:.1f}%"))

    def _update_stats(self):
        """更新统计信息"""
        # 模拟统计数据
        stats_data = {
            "total_volume": "1,234,567",
            "total_turnover": "123.45万",
            "avg_price": "100.15",
            "high_price": "102.50",
            "low_price": "98.80",
            "buy_sell_ratio": "1.25",
            "large_order_flow": "+1,250万",
            "activity_level": "活跃"
        }

        for key, value in stats_data.items():
            if key in self.stats_labels:
                self.stats_labels[key].setText(value)

    def _update_status_bar(self):
        """更新状态栏"""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.update_time_label.setText(f"更新: {current_time}")

        # 计算数据速率（模拟）
        self.data_rate_label.setText("15 tick/s")

    def _clear_displays(self):
        """清空所有显示"""
        self.level2_table.setRowCount(0)
        self.tick_table.setRowCount(0)
        self.order_book_table.setRowCount(0)

        # 重置基本信息
        self.price_label.setText("--")
        self.change_label.setText("--")
        self.volume_label.setText("--")
        self.turnover_label.setText("--")

        # 重置统计信息
        for label in self.stats_labels.values():
            label.setText("--")

    def set_symbol(self, symbol: str):
        """设置当前股票代码"""
        self.symbol_combo.setCurrentText(symbol)

    def get_current_symbol(self) -> str:
        """获取当前股票代码"""
        return self.current_symbol

    def is_subscribed(self, symbol: str = None) -> bool:
        """检查是否已订阅指定股票"""
        check_symbol = symbol or self.current_symbol
        return check_symbol in self.subscribed_symbols if check_symbol else False

    def closeEvent(self, event):
        """关闭事件处理"""
        # 停止定时器
        if self.update_timer.isActive():
            self.update_timer.stop()

        # 取消所有订阅
        for symbol in list(self.subscribed_symbols):
            self._unsubscribe_symbol(symbol)

        logger.info("Level2DataPanel 已关闭")
        event.accept()
