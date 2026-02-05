from loguru import logger
"""
交易面板模块

提供交易执行和持仓管理的UI界面。
精简版，只包含交易功能，不包含重复的分析功能。
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget, QTextEdit,
    QMessageBox, QDialog, QDialogButtonBox, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QColor

from core.services.trading_service import TradingService, Portfolio, Position, TradeRecord
from core.events import EventBus, StockSelectedEvent, TradeExecutedEvent, PositionUpdatedEvent
# 纯Loguru架构，移除旧的日志导入
logger = logger

class TradingPanel(QWidget):
    """
    交易面板

    负责：
    1. 交易执行（买入/卖出）
    2. 持仓展示和管理
    3. 交易历史查看
    4. 投资组合概览
    """

    # 信号定义
    trade_executed = pyqtSignal(dict)  # 交易执行信号
    error_occurred = pyqtSignal(str)   # 错误信号

    def __init__(self,
                 trading_service: TradingService,
                 event_bus: EventBus,
                 parent: Optional[QWidget] = None):
        """
        初始化交易面板

        Args:
            trading_service: 交易服务
            event_bus: 事件总线
            parent: 父窗口
        """
        super().__init__(parent)

        self.trading_service = trading_service
        self.event_bus = event_bus
        # 纯Loguru架构，移除log_manager依赖

        # 当前状态
        self._current_stock_code: Optional[str] = None
        self._current_stock_name: Optional[str] = None
        self._portfolio: Optional[Portfolio] = None

        # 初始化UI
        self._init_ui()

        # 连接信号
        self._connect_signals()

        # 订阅事件
        self._subscribe_events()

        # 启动定时刷新
        self._setup_refresh_timer()

    def _init_ui(self) -> None:
        """初始化用户界面"""
        try:
            layout = QVBoxLayout(self)
            layout.setSpacing(10)
            layout.setContentsMargins(10, 10, 10, 10)

            # 创建标签页
            tab_widget = QTabWidget()
            layout.addWidget(tab_widget)

            # 1. 交易执行标签页
            self._create_trading_tab(tab_widget)

            # 2. 持仓管理标签页
            self._create_position_tab(tab_widget)

            # 3. 交易历史标签页
            self._create_history_tab(tab_widget)

            # 4. 投资组合标签页
            self._create_portfolio_tab(tab_widget)

            logger.info("Trading panel UI initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize trading panel UI: {e}")
            self.error_occurred.emit(f"初始化交易面板失败: {e}")

    def _create_trading_tab(self, tab_widget: QTabWidget) -> None:
        """创建交易执行标签页"""
        trading_widget = QWidget()
        layout = QVBoxLayout(trading_widget)

        # 当前股票信息
        stock_group = QGroupBox("当前股票")
        stock_layout = QFormLayout(stock_group)

        self.current_stock_label = QLabel("未选择")
        self.current_stock_label.setFont(QFont("Arial", 12, QFont.Bold))
        stock_layout.addRow("股票代码:", self.current_stock_label)

        self.current_price_label = QLabel("--")
        stock_layout.addRow("当前价格:", self.current_price_label)

        layout.addWidget(stock_group)

        # 交易操作区
        trade_group = QGroupBox("交易操作")
        trade_layout = QVBoxLayout(trade_group)

        # 买入区域
        buy_layout = QHBoxLayout()
        buy_layout.addWidget(QLabel("买入数量:"))

        self.buy_quantity_spin = QSpinBox()
        self.buy_quantity_spin.setRange(100, 999999)
        self.buy_quantity_spin.setValue(100)
        self.buy_quantity_spin.setSingleStep(100)
        buy_layout.addWidget(self.buy_quantity_spin)

        self.buy_button = QPushButton("买入")
        self.buy_button.setStyleSheet("""
            QPushButton {
                background-color: #ff6b6b;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff5252;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        buy_layout.addWidget(self.buy_button)

        trade_layout.addLayout(buy_layout)

        # 卖出区域
        sell_layout = QHBoxLayout()
        sell_layout.addWidget(QLabel("卖出数量:"))

        self.sell_quantity_spin = QSpinBox()
        self.sell_quantity_spin.setRange(100, 999999)
        self.sell_quantity_spin.setValue(100)
        self.sell_quantity_spin.setSingleStep(100)
        sell_layout.addWidget(self.sell_quantity_spin)

        self.sell_button = QPushButton("卖出")
        self.sell_button.setStyleSheet("""
            QPushButton {
                background-color: #4ecdc4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #26d0ce;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        sell_layout.addWidget(self.sell_button)

        trade_layout.addLayout(sell_layout)

        layout.addWidget(trade_group)

        # 可用资金信息
        cash_group = QGroupBox("资金信息")
        cash_layout = QFormLayout(cash_group)

        self.available_cash_label = QLabel("--")
        cash_layout.addRow("可用资金:", self.available_cash_label)

        self.total_assets_label = QLabel("--")
        cash_layout.addRow("总资产:", self.total_assets_label)

        layout.addWidget(cash_group)

        tab_widget.addTab(trading_widget, "交易执行")

    def _create_position_tab(self, tab_widget: QTabWidget) -> None:
        """创建持仓管理标签页"""
        position_widget = QWidget()
        layout = QVBoxLayout(position_widget)

        # 持仓表格
        self.position_table = QTableWidget()
        self.position_table.setColumnCount(8)
        self.position_table.setHorizontalHeaderLabels([
            "股票代码", "股票名称", "持仓数量", "平均成本",
            "当前价格", "市值", "盈亏", "盈亏比例"
        ])

        # 设置表格属性
        header = self.position_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.position_table.setSelectionBehavior(QTableWidget.SelectRows)

        layout.addWidget(self.position_table)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.refresh_position_btn = QPushButton("刷新持仓")
        button_layout.addWidget(self.refresh_position_btn)

        self.clear_position_btn = QPushButton("清空持仓")
        self.clear_position_btn.setStyleSheet("color: red;")
        button_layout.addWidget(self.clear_position_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        tab_widget.addTab(position_widget, "持仓管理")

    def _create_history_tab(self, tab_widget: QTabWidget) -> None:
        """创建交易历史标签页"""
        history_widget = QWidget()
        layout = QVBoxLayout(history_widget)

        # 交易历史表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(9)
        self.history_table.setHorizontalHeaderLabels([
            "时间", "交易编号", "股票代码", "股票名称",
            "操作", "价格", "数量", "金额", "状态"
        ])

        # 设置表格属性
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)

        layout.addWidget(self.history_table)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.refresh_history_btn = QPushButton("刷新历史")
        button_layout.addWidget(self.refresh_history_btn)

        self.export_history_btn = QPushButton("导出历史")
        button_layout.addWidget(self.export_history_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        tab_widget.addTab(history_widget, "交易历史")

    def _create_portfolio_tab(self, tab_widget: QTabWidget) -> None:
        """创建投资组合标签页"""
        portfolio_widget = QWidget()
        layout = QVBoxLayout(portfolio_widget)

        # 组合概览
        overview_group = QGroupBox("投资组合概览")
        overview_layout = QFormLayout(overview_group)

        self.total_assets_overview_label = QLabel("--")
        overview_layout.addRow("总资产:", self.total_assets_overview_label)

        self.available_cash_overview_label = QLabel("--")
        overview_layout.addRow("可用现金:", self.available_cash_overview_label)

        self.market_value_label = QLabel("--")
        overview_layout.addRow("持仓市值:", self.market_value_label)

        self.total_profit_loss_label = QLabel("--")
        overview_layout.addRow("总盈亏:", self.total_profit_loss_label)

        self.profit_loss_pct_label = QLabel("--")
        overview_layout.addRow("收益率:", self.profit_loss_pct_label)

        layout.addWidget(overview_group)

        # 持仓分布图表区域（预留）
        chart_group = QGroupBox("持仓分布")
        chart_layout = QVBoxLayout(chart_group)

        self.chart_placeholder = QLabel("持仓分布图表\n（功能开发中）")
        self.chart_placeholder.setAlignment(Qt.AlignCenter)
        self.chart_placeholder.setStyleSheet("""
            QLabel {
                border: 2px dashed #cccccc;
                border-radius: 8px;
                padding: 20px;
                color: #666666;
            }
        """)
        chart_layout.addWidget(self.chart_placeholder)

        layout.addWidget(chart_group)

        tab_widget.addTab(portfolio_widget, "投资组合")

    def _connect_signals(self) -> None:
        """连接信号"""
        try:
            # 连接按钮信号
            self.buy_button.clicked.connect(self._on_buy_clicked)
            self.sell_button.clicked.connect(self._on_sell_clicked)

            # 连接刷新按钮
            self.refresh_position_btn.clicked.connect(self._refresh_positions)
            self.refresh_history_btn.clicked.connect(self._refresh_history)

            # 连接清空按钮
            self.clear_position_btn.clicked.connect(self._on_clear_positions)

            # 连接导出按钮
            self.export_history_btn.clicked.connect(self._on_export_history)

            logger.debug("Trading panel signals connected")

        except Exception as e:
            logger.error(f"Failed to connect trading panel signals: {e}")

    def _subscribe_events(self) -> None:
        """订阅事件"""
        try:
            # 订阅股票选择事件
            self.event_bus.subscribe(StockSelectedEvent, self._on_stock_selected)

            # 订阅交易执行事件
            self.event_bus.subscribe(TradeExecutedEvent, self._on_trade_executed)

            # 订阅持仓更新事件
            self.event_bus.subscribe(PositionUpdatedEvent, self._on_position_updated)

            logger.debug("Trading panel events subscribed")

        except Exception as e:
            logger.error(f"Failed to subscribe trading panel events: {e}")

    def _setup_refresh_timer(self) -> None:
        """设置定时刷新"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_data)
        self.refresh_timer.start(5000)  # 每5秒刷新一次

    @pyqtSlot(object)
    def _on_stock_selected(self, event: StockSelectedEvent) -> None:
        """处理股票选择事件"""
        try:
            self._current_stock_code = event.stock_code
            self._current_stock_name = event.stock_name

            # 更新UI显示
            self.current_stock_label.setText(f"{event.stock_name} ({event.stock_code})")
            self.current_price_label.setText("获取中...")

            # 启用交易按钮
            self.buy_button.setEnabled(True)

            # 检查持仓情况，决定是否启用卖出按钮
            self._update_sell_button_state()

            logger.debug(f"Trading panel: stock selected {event.stock_code}")

        except Exception as e:
            logger.error(f"Failed to handle stock selected event: {e}")

    @pyqtSlot()
    def _on_buy_clicked(self) -> None:
        """处理买入按钮点击"""
        try:
            if not self._current_stock_code:
                QMessageBox.warning(self, "买入失败", "请先选择股票")
                return

            quantity = self.buy_quantity_spin.value()

            # 异步执行买入操作
            self._execute_trade_async('BUY', quantity)

        except Exception as e:
            logger.error(f"Buy button click failed: {e}")
            self.error_occurred.emit(f"买入操作失败: {e}")

    @pyqtSlot()
    def _on_sell_clicked(self) -> None:
        """处理卖出按钮点击"""
        try:
            if not self._current_stock_code:
                QMessageBox.warning(self, "卖出失败", "请先选择股票")
                return

            quantity = self.sell_quantity_spin.value()

            # 异步执行卖出操作
            self._execute_trade_async('SELL', quantity)

        except Exception as e:
            logger.error(f"Sell button click failed: {e}")
            self.error_occurred.emit(f"卖出操作失败: {e}")

    def _execute_trade_async(self, action: str, quantity: int) -> None:
        """异步执行交易"""
        class TradeWorker(QThread):
            finished = pyqtSignal(object)
            error = pyqtSignal(str)

            def __init__(self, trading_service, action, stock_code, stock_name, quantity):
                super().__init__()
                self.trading_service = trading_service
                self.action = action
                self.stock_code = stock_code
                self.stock_name = stock_name
                self.quantity = quantity

            def run(self):
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    if self.action == 'BUY':
                        result = loop.run_until_complete(
                            self.trading_service.execute_buy_order(
                                self.stock_code, self.stock_name, self.quantity
                            )
                        )
                    else:  # SELL
                        result = loop.run_until_complete(
                            self.trading_service.execute_sell_order(
                                self.stock_code, self.stock_name, self.quantity
                            )
                        )

                    self.finished.emit(result)

                except Exception as e:
                    self.error.emit(str(e))
                finally:
                    loop.close()

        # 创建并启动工作线程
        self.trade_worker = TradeWorker(
            self.trading_service, action,
            self._current_stock_code, self._current_stock_name, quantity
        )
        self.trade_worker.finished.connect(self._on_trade_finished)
        self.trade_worker.error.connect(self._on_trade_error)

        # 禁用按钮防止重复点击
        self.buy_button.setEnabled(False)
        self.sell_button.setEnabled(False)
        self.buy_button.setText("交易中...")
        self.sell_button.setText("交易中...")

        self.trade_worker.start()

    @pyqtSlot(object)
    def _on_trade_finished(self, trade_record: TradeRecord) -> None:
        """处理交易完成"""
        try:
            if trade_record.status == 'executed':
                QMessageBox.information(
                    self, "交易成功",
                    f"成功{trade_record.action} {trade_record.stock_name} "
                    f"{trade_record.quantity}股 @{trade_record.price:.2f}"
                )

                # 刷新数据
                self._refresh_data()
            else:
                QMessageBox.warning(
                    self, "交易失败",
                    f"交易失败: {trade_record.notes}"
                )

        except Exception as e:
            logger.error(f"Failed to handle trade finished: {e}")
        finally:
            # 恢复按钮状态
            self._restore_button_state()

    @pyqtSlot(str)
    def _on_trade_error(self, error_message: str) -> None:
        """处理交易错误"""
        logger.error(f"Trade error: {error_message}")
        QMessageBox.critical(self, "交易错误", f"交易执行失败: {error_message}")
        self._restore_button_state()

    def _restore_button_state(self) -> None:
        """恢复按钮状态"""
        self.buy_button.setText("买入")
        self.sell_button.setText("卖出")
        self.buy_button.setEnabled(bool(self._current_stock_code))
        self._update_sell_button_state()

    def _update_sell_button_state(self) -> None:
        """更新卖出按钮状态"""
        if not self._current_stock_code:
            self.sell_button.setEnabled(False)
            return

        # 检查是否有持仓
        position = self.trading_service.get_position(self._current_stock_code)
        self.sell_button.setEnabled(position is not None and position.quantity > 0)

    @pyqtSlot()
    def _refresh_data(self) -> None:
        """刷新数据"""
        try:
            # 更新投资组合数据
            self._portfolio = self.trading_service.get_portfolio()

            # 更新UI显示
            self._update_portfolio_display()
            self._refresh_positions()
            self._refresh_history()

            # 更新卖出按钮状态
            self._update_sell_button_state()

        except Exception as e:
            logger.error(f"Failed to refresh trading data: {e}")

    def _update_portfolio_display(self) -> None:
        """更新投资组合显示"""
        if not self._portfolio:
            return

        try:
            # 更新资金信息
            self.available_cash_label.setText(f"¥{self._portfolio.available_cash:,.2f}")
            self.total_assets_label.setText(f"¥{self._portfolio.total_assets:,.2f}")

            # 更新组合概览
            self.total_assets_overview_label.setText(f"¥{self._portfolio.total_assets:,.2f}")
            self.available_cash_overview_label.setText(f"¥{self._portfolio.available_cash:,.2f}")
            self.market_value_label.setText(f"¥{self._portfolio.market_value:,.2f}")

            # 设置盈亏颜色
            profit_loss_text = f"¥{self._portfolio.total_profit_loss:,.2f}"
            profit_loss_pct_text = f"{self._portfolio.total_profit_loss_pct:.2f}%"

            color = "green" if self._portfolio.total_profit_loss >= 0 else "red"
            self.total_profit_loss_label.setText(profit_loss_text)
            self.total_profit_loss_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.profit_loss_pct_label.setText(profit_loss_pct_text)
            self.profit_loss_pct_label.setStyleSheet(f"color: {color}; font-weight: bold;")

        except Exception as e:
            logger.error(f"Failed to update portfolio display: {e}")

    def _refresh_positions(self) -> None:
        """刷新持仓表格"""
        if not self._portfolio:
            return

        try:
            positions = self._portfolio.positions
            self.position_table.setRowCount(len(positions))

            for row, position in enumerate(positions):
                # 股票代码
                self.position_table.setItem(row, 0, QTableWidgetItem(position.stock_code))

                # 股票名称
                self.position_table.setItem(row, 1, QTableWidgetItem(position.stock_name))

                # 持仓数量
                self.position_table.setItem(row, 2, QTableWidgetItem(str(position.quantity)))

                # 平均成本
                self.position_table.setItem(row, 3, QTableWidgetItem(f"{position.avg_cost:.2f}"))

                # 当前价格
                self.position_table.setItem(row, 4, QTableWidgetItem(f"{position.current_price:.2f}"))

                # 市值
                self.position_table.setItem(row, 5, QTableWidgetItem(f"{position.market_value:.2f}"))

                # 盈亏
                profit_loss_item = QTableWidgetItem(f"{position.profit_loss:.2f}")
                color = QColor("green") if position.profit_loss >= 0 else QColor("red")
                profit_loss_item.setForeground(color)
                self.position_table.setItem(row, 6, profit_loss_item)

                # 盈亏比例
                profit_loss_pct_item = QTableWidgetItem(f"{position.profit_loss_pct:.2f}%")
                profit_loss_pct_item.setForeground(color)
                self.position_table.setItem(row, 7, profit_loss_pct_item)

        except Exception as e:
            logger.error(f"Failed to refresh positions: {e}")

    def _refresh_history(self) -> None:
        """刷新交易历史表格"""
        try:
            history = self.trading_service.get_trade_history(50)  # 最近50条记录
            self.history_table.setRowCount(len(history))

            for row, trade in enumerate(history):
                # 时间
                time_str = trade.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                self.history_table.setItem(row, 0, QTableWidgetItem(time_str))

                # 交易编号
                self.history_table.setItem(row, 1, QTableWidgetItem(trade.trade_id))

                # 股票代码
                self.history_table.setItem(row, 2, QTableWidgetItem(trade.stock_code))

                # 股票名称
                self.history_table.setItem(row, 3, QTableWidgetItem(trade.stock_name))

                # 操作
                action_item = QTableWidgetItem(trade.action)
                action_color = QColor("red") if trade.action == "BUY" else QColor("green")
                action_item.setForeground(action_color)
                self.history_table.setItem(row, 4, action_item)

                # 价格
                self.history_table.setItem(row, 5, QTableWidgetItem(f"{trade.price:.2f}"))

                # 数量
                self.history_table.setItem(row, 6, QTableWidgetItem(str(trade.quantity)))

                # 金额
                self.history_table.setItem(row, 7, QTableWidgetItem(f"{trade.amount:.2f}"))

                # 状态
                status_item = QTableWidgetItem(trade.status)
                if trade.status == 'executed':
                    status_item.setForeground(QColor("green"))
                elif trade.status == 'failed':
                    status_item.setForeground(QColor("red"))
                self.history_table.setItem(row, 8, status_item)

        except Exception as e:
            logger.error(f"Failed to refresh history: {e}")

    @pyqtSlot()
    def _on_clear_positions(self) -> None:
        """清空持仓"""
        reply = QMessageBox.question(
            self, "清空持仓",
            "确定要清空所有持仓吗？此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 这里实现清空持仓的逻辑
            QMessageBox.information(self, "提示", "清空持仓功能开发中")

    @pyqtSlot()
    def _on_export_history(self) -> None:
        """导出交易历史"""
        QMessageBox.information(self, "提示", "导出交易历史功能开发中")

    @pyqtSlot(object)
    def _on_trade_executed(self, event: TradeExecutedEvent) -> None:
        """处理交易执行事件"""
        self._refresh_data()

    @pyqtSlot(object)
    def _on_position_updated(self, event: PositionUpdatedEvent) -> None:
        """处理持仓更新事件"""
        self._refresh_data()

    def dispose(self) -> None:
        """清理资源"""
        try:
            # 停止定时器
            if hasattr(self, 'refresh_timer'):
                self.refresh_timer.stop()

            # 取消事件订阅
            self.event_bus.unsubscribe(StockSelectedEvent, self._on_stock_selected)
            self.event_bus.unsubscribe(TradeExecutedEvent, self._on_trade_executed)
            self.event_bus.unsubscribe(PositionUpdatedEvent, self._on_position_updated)

            logger.debug("Trading panel disposed")

        except Exception as e:
            logger.error(f"Failed to dispose trading panel: {e}")
