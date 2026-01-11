#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单簿组件
提供专业的订单簿深度数据可视化和分析功能
"""

import math
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QFrame, QPushButton, QComboBox, QSpinBox, QCheckBox, QSlider,
    QGroupBox, QGridLayout, QProgressBar, QSplitter
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QPalette, QPainter, QBrush, QPen
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
from loguru import logger

from core.events.event_bus import EventBus, OrderBookEvent


class OrderBookDepthChart(FigureCanvas):
    """订单簿深度图表"""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='white')
        super().__init__(self.fig)
        self.setParent(parent)

        # 创建子图
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#FAFAFA')

        # 初始化数据
        self.bid_prices = []
        self.bid_volumes = []
        self.ask_prices = []
        self.ask_volumes = []

        self.setup_chart()

    def setup_chart(self):
        """设置图表样式"""
        self.ax.set_title('订单簿深度图', fontsize=10, fontweight='bold')
        self.ax.set_xlabel('价格', fontsize=8)
        self.ax.set_ylabel('累计数量', fontsize=8)
        self.ax.grid(True, alpha=0.3)
        self.ax.tick_params(axis='both', rotation=0, labelsize=8)

        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
        plt.rcParams['axes.unicode_minus'] = False

    def update_data(self, bids: List[Dict], asks: List[Dict]):
        """更新订单簿数据"""
        try:
            # 清空之前的数据
            self.ax.clear()
            self.setup_chart()

            if not bids or not asks:
                self.draw()
                return

            # 处理买盘数据
            bid_prices = [bid['price'] for bid in bids]
            bid_volumes = [bid['volume'] for bid in bids]

            # 处理卖盘数据
            ask_prices = [ask['price'] for ask in asks]
            ask_volumes = [ask['volume'] for ask in asks]

            # 计算累计量
            bid_cumulative = np.cumsum(bid_volumes[::-1])[::-1]  # 从高价到低价累计
            ask_cumulative = np.cumsum(ask_volumes)  # 从低价到高价累计

            # 绘制买盘（红色）
            self.ax.fill_between(bid_prices, 0, bid_cumulative,
                                 step='post', alpha=0.7, color='#E74C3C', label='买盘')
            self.ax.plot(bid_prices, bid_cumulative,
                         color='#C0392B', linewidth=2, drawstyle='steps-post')

            # 绘制卖盘（绿色）
            self.ax.fill_between(ask_prices, 0, ask_cumulative,
                                 step='pre', alpha=0.7, color='#27AE60', label='卖盘')
            self.ax.plot(ask_prices, ask_cumulative,
                         color='#229954', linewidth=2, drawstyle='steps-pre')

            # 添加图例
            self.ax.legend(loc='upper right')

            # 设置坐标轴范围
            all_prices = bid_prices + ask_prices
            if all_prices:
                price_range = max(all_prices) - min(all_prices)
                margin = price_range * 0.05
                self.ax.set_xlim(min(all_prices) - margin, max(all_prices) + margin)

            all_volumes = list(bid_cumulative) + list(ask_cumulative)
            if all_volumes:
                self.ax.set_ylim(0, max(all_volumes) * 1.1)

            self.draw()

        except Exception as e:
            logger.error(f"更新订单簿深度图失败: {e}")


class OrderBookWidget(QWidget):
    """
    订单簿组件
    提供专业的订单簿数据显示和分析功能
    """

    # 信号定义
    price_selected = pyqtSignal(float)     # 价格选择信号
    order_analyzed = pyqtSignal(dict)      # 订单分析信号
    depth_changed = pyqtSignal(int)        # 深度变更信号

    def __init__(self, parent=None, event_bus: EventBus = None):
        super().__init__(parent)

        self.event_bus = event_bus
        self.current_symbol = None
        self.order_book_data = {}

        # 显示设置
        self.display_depth = 20
        self.show_cumulative = True
        self.show_percentage = True
        self.price_precision = 2

        # 数据缓存
        self.historical_snapshots = []
        self.max_snapshots = 100

        self.init_ui()
        self.setup_event_connections()

        logger.info("OrderBookWidget 初始化完成")

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

        # 左侧：订单簿表格
        left_panel = self._create_order_book_table()
        main_splitter.addWidget(left_panel)

        # 右侧：深度图表和分析
        right_panel = self._create_analysis_panel()
        main_splitter.addWidget(right_panel)

        # 设置分割比例
        main_splitter.setSizes([400, 300])
        layout.addWidget(main_splitter)

        # 统计信息面板
        stats_panel = self._create_stats_panel()
        layout.addWidget(stats_panel)

    def _create_control_panel(self) -> QWidget:
        """创建控制面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel)
        panel.setMaximumHeight(50)

        layout = QHBoxLayout(panel)

        # 显示深度设置
        layout.addWidget(QLabel("显示深度:"))
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(5, 50)
        self.depth_spin.setValue(self.display_depth)
        self.depth_spin.valueChanged.connect(self._on_depth_changed)
        layout.addWidget(self.depth_spin)

        # 价格精度设置
        layout.addWidget(QLabel("价格精度:"))
        self.precision_spin = QSpinBox()
        self.precision_spin.setRange(0, 6)
        self.precision_spin.setValue(self.price_precision)
        self.precision_spin.valueChanged.connect(self._on_precision_changed)
        layout.addWidget(self.precision_spin)

        # 显示选项
        self.cumulative_check = QCheckBox("显示累计")
        self.cumulative_check.setChecked(self.show_cumulative)
        self.cumulative_check.toggled.connect(self._on_cumulative_toggled)
        layout.addWidget(self.cumulative_check)

        self.percentage_check = QCheckBox("显示百分比")
        self.percentage_check.setChecked(self.show_percentage)
        self.percentage_check.toggled.connect(self._on_percentage_toggled)
        layout.addWidget(self.percentage_check)

        layout.addStretch()

        # 分析按钮
        self.analyze_btn = QPushButton("深度分析")
        self.analyze_btn.clicked.connect(self._perform_depth_analysis)
        layout.addWidget(self.analyze_btn)

        # 导出按钮
        self.export_btn = QPushButton("导出数据")
        self.export_btn.clicked.connect(self._export_data)
        layout.addWidget(self.export_btn)

        return panel

    def _create_order_book_table(self) -> QWidget:
        """创建订单簿表格"""
        group = QGroupBox("订单簿")
        layout = QVBoxLayout(group)

        # 创建表格
        self.order_table = QTableWidget()

        # 根据显示选项设置列
        self._setup_table_columns()

        # 设置表格属性
        self.order_table.setAlternatingRowColors(True)
        self.order_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.order_table.verticalHeader().setVisible(False)
        self.order_table.itemClicked.connect(self._on_table_item_clicked)

        layout.addWidget(self.order_table)

        return group

    def _setup_table_columns(self):
        """设置表格列"""
        columns = ["档位", "买量", "买价", "卖价", "卖量"]

        if self.show_cumulative:
            columns.extend(["买累计", "卖累计"])

        if self.show_percentage:
            columns.extend(["买占比", "卖占比"])

        self.order_table.setColumnCount(len(columns))
        self.order_table.setHorizontalHeaderLabels(columns)

        # 调整列宽
        header = self.order_table.horizontalHeader()
        for i in range(len(columns)):
            if i < 5:  # 基础列
                header.resizeSection(i, 80)
            else:  # 扩展列
                header.resizeSection(i, 70)

    def _create_analysis_panel(self) -> QWidget:
        """创建分析面板"""
        group = QGroupBox("深度分析")
        layout = QVBoxLayout(group)

        # 深度图表
        self.depth_chart = OrderBookDepthChart()
        layout.addWidget(self.depth_chart)

        # 分析指标
        metrics_frame = QFrame()
        metrics_layout = QGridLayout(metrics_frame)

        # 创建分析指标标签
        self.metrics_labels = {}
        metrics_items = [
            ("买卖比", "buy_sell_ratio"),
            ("价差", "spread"),
            ("中间价", "mid_price"),
            ("不平衡度", "imbalance"),
            ("深度强度", "depth_strength"),
            ("价格影响", "price_impact")
        ]

        for i, (label, key) in enumerate(metrics_items):
            row, col = i // 2, (i % 2) * 2
            metrics_layout.addWidget(QLabel(f"{label}:"), row, col)

            value_label = QLabel("--")
            value_label.setStyleSheet("font-weight: bold; color: #2E86AB;")
            metrics_layout.addWidget(value_label, row, col + 1)

            self.metrics_labels[key] = value_label

        layout.addWidget(metrics_frame)

        return group

    def _create_stats_panel(self) -> QWidget:
        """创建统计信息面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel)
        panel.setMaximumHeight(60)

        layout = QHBoxLayout(panel)

        # 实时统计
        self.total_bid_volume = QLabel("总买量: --")
        self.total_ask_volume = QLabel("总卖量: --")
        self.weighted_bid_price = QLabel("加权买价: --")
        self.weighted_ask_price = QLabel("加权卖价: --")
        self.update_time = QLabel("更新时间: --")

        layout.addWidget(self.total_bid_volume)
        layout.addWidget(self.total_ask_volume)
        layout.addWidget(self.weighted_bid_price)
        layout.addWidget(self.weighted_ask_price)
        layout.addStretch()
        layout.addWidget(self.update_time)
        return panel

    def setup_event_connections(self):
        """设置事件连接"""
        if self.event_bus:
            # 订阅订单簿数据事件
            self.event_bus.subscribe(OrderBookEvent, self._handle_order_book_event)
            logger.info("OrderBookWidget 事件连接已建立")

    def _on_depth_changed(self, depth: int):
        """深度变更处理"""
        self.display_depth = depth
        self.depth_changed.emit(depth)
        self._update_table_display()
        logger.debug(f"订单簿显示深度已调整为: {depth}")

    def _on_precision_changed(self, precision: int):
        """价格精度变更处理"""
        self.price_precision = precision
        self._update_table_display()
        logger.debug(f"价格精度已调整为: {precision}")

    def _on_cumulative_toggled(self, checked: bool):
        """累计显示切换"""
        self.show_cumulative = checked
        self._setup_table_columns()
        self._update_table_display()

    def _on_percentage_toggled(self, checked: bool):
        """百分比显示切换"""
        self.show_percentage = checked
        self._setup_table_columns()
        self._update_table_display()

    def _on_table_item_clicked(self, item: QTableWidgetItem):
        """表格项点击处理"""
        try:
            row = item.row()

            # 获取价格列的数据
            buy_price_item = self.order_table.item(row, 2)  # 买价列
            sell_price_item = self.order_table.item(row, 3)  # 卖价列

            if buy_price_item and buy_price_item.text() != "--":
                price = float(buy_price_item.text())
                self.price_selected.emit(price)
            elif sell_price_item and sell_price_item.text() != "--":
                price = float(sell_price_item.text())
                self.price_selected.emit(price)

        except (ValueError, AttributeError) as e:
            logger.warning(f"处理表格点击事件失败: {e}")

    @pyqtSlot(object)
    def _handle_order_book_event(self, event: OrderBookEvent):
        """处理订单簿事件"""
        try:
            data = event.order_book_data
            symbol = data.get('symbol')

            if symbol:
                self.current_symbol = symbol
                self.order_book_data = data

                # 保存历史快照
                self._save_snapshot(data)

                # 更新显示
                self._update_display()

                logger.debug(f"收到 {symbol} 的订单簿数据")

        except Exception as e:
            logger.error(f"处理订单簿事件失败: {e}")

    def _save_snapshot(self, data: Dict):
        """保存订单簿快照"""
        snapshot = {
            'timestamp': datetime.now(),
            'data': data.copy()
        }

        self.historical_snapshots.append(snapshot)

        # 保持最大快照数量
        if len(self.historical_snapshots) > self.max_snapshots:
            self.historical_snapshots = self.historical_snapshots[-self.max_snapshots:]

    def _update_display(self):
        """更新显示"""
        if not self.order_book_data:
            return

        try:
            # 更新表格
            self._update_table_display()

            # 更新深度图表
            self._update_depth_chart()

            # 更新分析指标
            self._update_analysis_metrics()

            # 更新统计信息
            self._update_stats()

        except Exception as e:
            logger.error(f"更新订单簿显示失败: {e}")

    def _update_table_display(self):
        """更新表格显示"""
        if not self.order_book_data:
            return

        bids = self.order_book_data.get('bids', [])
        asks = self.order_book_data.get('asks', [])

        # 确保有足够的数据
        max_depth = min(self.display_depth, max(len(bids), len(asks)))
        self.order_table.setRowCount(max_depth)

        # 计算累计量和总量
        total_bid_volume = sum(bid['volume'] for bid in bids)
        total_ask_volume = sum(ask['volume'] for ask in asks)

        bid_cumulative = 0
        ask_cumulative = 0

        for i in range(max_depth):
            # 档位
            self.order_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))

            # 买盘数据
            if i < len(bids):
                bid = bids[i]
                bid_volume = bid['volume']
                bid_price = bid['price']
                bid_cumulative += bid_volume

                # 买量
                buy_volume_item = QTableWidgetItem(f"{bid_volume:,.0f}")
                buy_volume_item.setForeground(QColor("#E74C3C"))
                self.order_table.setItem(i, 1, buy_volume_item)

                # 买价
                buy_price_item = QTableWidgetItem(f"{bid_price:.{self.price_precision}f}")
                buy_price_item.setForeground(QColor("#E74C3C"))
                buy_price_item.setFont(QFont("Consolas", 9, QFont.Bold))
                self.order_table.setItem(i, 2, buy_price_item)
            else:
                self.order_table.setItem(i, 1, QTableWidgetItem("--"))
                self.order_table.setItem(i, 2, QTableWidgetItem("--"))

            # 卖盘数据
            if i < len(asks):
                ask = asks[i]
                ask_volume = ask['volume']
                ask_price = ask['price']
                ask_cumulative += ask_volume

                # 卖价
                sell_price_item = QTableWidgetItem(f"{ask_price:.{self.price_precision}f}")
                sell_price_item.setForeground(QColor("#27AE60"))
                sell_price_item.setFont(QFont("Consolas", 9, QFont.Bold))
                self.order_table.setItem(i, 3, sell_price_item)

                # 卖量
                sell_volume_item = QTableWidgetItem(f"{ask_volume:,.0f}")
                sell_volume_item.setForeground(QColor("#27AE60"))
                self.order_table.setItem(i, 4, sell_volume_item)
            else:
                self.order_table.setItem(i, 3, QTableWidgetItem("--"))
                self.order_table.setItem(i, 4, QTableWidgetItem("--"))

            # 累计量（如果启用）
            col_offset = 5
            if self.show_cumulative:
                if i < len(bids):
                    self.order_table.setItem(i, col_offset,
                                             QTableWidgetItem(f"{bid_cumulative:,.0f}"))
                else:
                    self.order_table.setItem(i, col_offset, QTableWidgetItem("--"))

                if i < len(asks):
                    self.order_table.setItem(i, col_offset + 1,
                                             QTableWidgetItem(f"{ask_cumulative:,.0f}"))
                else:
                    self.order_table.setItem(i, col_offset + 1, QTableWidgetItem("--"))

                col_offset += 2

            # 百分比（如果启用）
            if self.show_percentage:
                if i < len(bids) and total_bid_volume > 0:
                    bid_pct = (bid_volume / total_bid_volume) * 100
                    self.order_table.setItem(i, col_offset,
                                             QTableWidgetItem(f"{bid_pct:.1f}%"))
                else:
                    self.order_table.setItem(i, col_offset, QTableWidgetItem("--"))

                if i < len(asks) and total_ask_volume > 0:
                    ask_pct = (ask_volume / total_ask_volume) * 100
                    self.order_table.setItem(i, col_offset + 1,
                                             QTableWidgetItem(f"{ask_pct:.1f}%"))
                else:
                    self.order_table.setItem(i, col_offset + 1, QTableWidgetItem("--"))

    def _update_depth_chart(self):
        """更新深度图表"""
        if not self.order_book_data:
            return

        bids = self.order_book_data.get('bids', [])
        asks = self.order_book_data.get('asks', [])

        # 限制显示的深度
        display_bids = bids[:self.display_depth]
        display_asks = asks[:self.display_depth]

        self.depth_chart.update_data(display_bids, display_asks)

    def _update_analysis_metrics(self):
        """更新分析指标"""
        if not self.order_book_data:
            return

        bids = self.order_book_data.get('bids', [])
        asks = self.order_book_data.get('asks', [])

        if not bids or not asks:
            return

        try:
            # 计算各种指标
            best_bid = bids[0]['price']
            best_ask = asks[0]['price']

            # 买卖比
            total_bid_volume = sum(bid['volume'] for bid in bids[:10])
            total_ask_volume = sum(ask['volume'] for ask in asks[:10])
            buy_sell_ratio = total_bid_volume / total_ask_volume if total_ask_volume > 0 else 0

            # 价差
            spread = best_ask - best_bid

            # 中间价
            mid_price = (best_bid + best_ask) / 2

            # 不平衡度
            imbalance = (total_bid_volume - total_ask_volume) / (total_bid_volume + total_ask_volume) * 100

            # 深度强度（前5档的平均量）
            depth_strength = (sum(bid['volume'] for bid in bids[:5]) +
                              sum(ask['volume'] for ask in asks[:5])) / 10

            # 价格影响（1%数量对价格的影响）
            target_volume = (total_bid_volume + total_ask_volume) * 0.01
            price_impact = self._calculate_price_impact(bids, asks, target_volume)

            # 更新显示
            self.metrics_labels['buy_sell_ratio'].setText(f"{buy_sell_ratio:.2f}")
            self.metrics_labels['spread'].setText(f"{spread:.{self.price_precision}f}")
            self.metrics_labels['mid_price'].setText(f"{mid_price:.{self.price_precision}f}")
            self.metrics_labels['imbalance'].setText(f"{imbalance:.1f}%")
            self.metrics_labels['depth_strength'].setText(f"{depth_strength:,.0f}")
            self.metrics_labels['price_impact'].setText(f"{price_impact:.{self.price_precision}f}")

        except Exception as e:
            logger.error(f"计算分析指标失败: {e}")

    def _calculate_price_impact(self, bids: List[Dict], asks: List[Dict], volume: float) -> float:
        """计算价格影响"""
        try:
            # 简化的价格影响计算
            if not bids or not asks:
                return 0.0

            best_bid = bids[0]['price']
            best_ask = asks[0]['price']

            # 计算买入指定数量需要的平均价格
            remaining_volume = volume
            total_cost = 0

            for ask in asks:
                if remaining_volume <= 0:
                    break

                take_volume = min(remaining_volume, ask['volume'])
                total_cost += take_volume * ask['price']
                remaining_volume -= take_volume

            if volume > 0:
                avg_price = total_cost / volume
                return avg_price - best_ask

            return 0.0

        except Exception as e:
            logger.error(f"计算价格影响失败: {e}")
            return 0.0

    def _update_stats(self):
        """更新统计信息"""
        if not self.order_book_data:
            return

        bids = self.order_book_data.get('bids', [])
        asks = self.order_book_data.get('asks', [])

        # 计算统计数据
        total_bid_volume = sum(bid['volume'] for bid in bids)
        total_ask_volume = sum(ask['volume'] for ask in asks)

        # 加权平均价格
        if bids:
            weighted_bid_price = sum(bid['price'] * bid['volume'] for bid in bids) / total_bid_volume
        else:
            weighted_bid_price = 0

        if asks:
            weighted_ask_price = sum(ask['price'] * ask['volume'] for ask in asks) / total_ask_volume
        else:
            weighted_ask_price = 0

        # 更新显示
        self.total_bid_volume.setText(f"总买量: {total_bid_volume:,.0f}")
        self.total_ask_volume.setText(f"总卖量: {total_ask_volume:,.0f}")
        self.weighted_bid_price.setText(f"加权买价: {weighted_bid_price:.{self.price_precision}f}")
        self.weighted_ask_price.setText(f"加权卖价: {weighted_ask_price:.{self.price_precision}f}")

        # 更新时间
        current_time = datetime.now().strftime("%H:%M:%S")
        self.update_time.setText(f"更新时间: {current_time}")

    def _perform_depth_analysis(self):
        """执行深度分析"""
        if not self.order_book_data:
            return

        try:
            bids = self.order_book_data.get('bids', [])
            asks = self.order_book_data.get('asks', [])

            # 执行更深入的分析
            analysis_result = {
                'timestamp': datetime.now(),
                'symbol': self.current_symbol,
                'market_depth': len(bids) + len(asks),
                'liquidity_score': self._calculate_liquidity_score(bids, asks),
                'volatility_indicator': self._calculate_volatility_indicator(),
                'market_pressure': self._calculate_market_pressure(bids, asks)
            }

            self.order_analyzed.emit(analysis_result)
            logger.info(f"订单簿深度分析完成: {analysis_result}")

        except Exception as e:
            logger.error(f"执行深度分析失败: {e}")

    def _calculate_liquidity_score(self, bids: List[Dict], asks: List[Dict]) -> float:
        """计算流动性评分"""
        try:
            if not bids or not asks:
                return 0.0

            # 基于订单簿深度和数量的流动性评分
            total_volume = sum(bid['volume'] for bid in bids) + sum(ask['volume'] for ask in asks)
            depth_count = len(bids) + len(asks)

            # 简化的流动性评分算法
            liquidity_score = math.log(total_volume + 1) * math.log(depth_count + 1)
            return min(liquidity_score / 100, 1.0)  # 归一化到0-1

        except Exception as e:
            logger.error(f"计算流动性评分失败: {e}")
            return 0.0

    def _calculate_volatility_indicator(self) -> float:
        """计算波动性指标"""
        try:
            if len(self.historical_snapshots) < 2:
                return 0.0

            # 基于历史快照计算价格波动
            recent_snapshots = self.historical_snapshots[-10:]  # 最近10个快照
            mid_prices = []

            for snapshot in recent_snapshots:
                data = snapshot['data']
                bids = data.get('bids', [])
                asks = data.get('asks', [])

                if bids and asks:
                    mid_price = (bids[0]['price'] + asks[0]['price']) / 2
                    mid_prices.append(mid_price)

            if len(mid_prices) < 2:
                return 0.0

            # 计算价格变化的标准差
            price_changes = [abs(mid_prices[i] - mid_prices[i-1]) for i in range(1, len(mid_prices))]
            volatility = np.std(price_changes) if price_changes else 0.0

            return volatility

        except Exception as e:
            logger.error(f"计算波动性指标失败: {e}")
            return 0.0

    def _calculate_market_pressure(self, bids: List[Dict], asks: List[Dict]) -> str:
        """计算市场压力"""
        try:
            if not bids or not asks:
                return "未知"

            total_bid_volume = sum(bid['volume'] for bid in bids[:5])  # 前5档
            total_ask_volume = sum(ask['volume'] for ask in asks[:5])

            ratio = total_bid_volume / total_ask_volume if total_ask_volume > 0 else 0

            if ratio > 1.5:
                return "买盘压力"
            elif ratio < 0.67:
                return "卖盘压力"
            else:
                return "平衡"

        except Exception as e:
            logger.error(f"计算市场压力失败: {e}")
            return "未知"

    def _export_data(self):
        """导出订单簿数据"""
        try:
            if not self.order_book_data:
                logger.warning("没有可导出的订单簿数据")
                return

            # 这里可以实现数据导出功能
            # 例如导出为CSV、JSON等格式
            logger.info("订单簿数据导出功能待实现")

        except Exception as e:
            logger.error(f"导出订单簿数据失败: {e}")

    def set_symbol(self, symbol: str):
        """设置当前股票代码"""
        self.current_symbol = symbol
        # 清空历史数据
        self.historical_snapshots.clear()
        self.order_book_data.clear()

    def get_current_data(self) -> Dict:
        """获取当前订单簿数据"""
        return self.order_book_data.copy()

    def clear_data(self):
        """清空数据"""
        self.order_book_data.clear()
        self.historical_snapshots.clear()
        self.order_table.setRowCount(0)

        # 重置分析指标
        for label in self.metrics_labels.values():
            label.setText("--")

        # 重置统计信息
        self.total_bid_volume.setText("总买量: --")
        self.total_ask_volume.setText("总卖量: --")
        self.weighted_bid_price.setText("加权买价: --")
        self.weighted_ask_price.setText("加权卖价: --")
        self.update_time.setText("更新时间: --")
