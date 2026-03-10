from loguru import logger
"""
交易面板模块

提供交易执行和持仓管理的UI界面。
精简版，只包含交易功能，不包含重复的分析功能。
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal
import asyncio

from PyQt5.QtWidgets import (
    QAbstractItemView, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget, QTextEdit,
    QMessageBox, QDialog, QDialogButtonBox, QComboBox, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QColor

try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib 未安装，持仓分布图表将不显示")

from core.services.trading_service import OrderSide, OrderStatus, OrderType, TradingService, Portfolio, Position, TradeRecord
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

            # 3. 订单状态标签页
            self._create_orders_tab(tab_widget)

            # 4. 交易历史标签页
            self._create_history_tab(tab_widget)

            # 5. 投资组合标签页
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
        stock_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        stock_layout = QFormLayout(stock_group)

        self.current_stock_label = QLabel("未选择")
        self.current_stock_label.setFont(QFont("Arial", 12, QFont.Bold))
        stock_layout.addRow("股票代码:", self.current_stock_label)

        self.current_price_label = QLabel("--")
        stock_layout.addRow("当前价格:", self.current_price_label)

        # CTP连接状态
        self.ctp_connection_label = QLabel("CTP未连接")
        self.ctp_connection_label.setStyleSheet("color: red; font-weight: bold;")
        stock_layout.addRow("连接状态:", self.ctp_connection_label)

        # CTP账户选择和连接按钮
        ctp_control_layout = QHBoxLayout()
        
        from PyQt5.QtWidgets import QComboBox
        self.ctp_account_combo = QComboBox()
        self.ctp_account_combo.setMinimumWidth(150)
        self.ctp_account_combo.setPlaceholderText("选择CTP账户")
        ctp_control_layout.addWidget(self.ctp_account_combo)
        
        self.ctp_connect_btn = QPushButton("连接")
        self.ctp_connect_btn.setFixedWidth(60)
        self.ctp_connect_btn.clicked.connect(self._on_ctp_connect_clicked)
        ctp_control_layout.addWidget(self.ctp_connect_btn)
        
        self.ctp_disconnect_btn = QPushButton("断开")
        self.ctp_disconnect_btn.setFixedWidth(60)
        self.ctp_disconnect_btn.clicked.connect(self._on_ctp_disconnect_clicked)
        self.ctp_disconnect_btn.setEnabled(False)
        ctp_control_layout.addWidget(self.ctp_disconnect_btn)
        
        ctp_control_layout.addStretch()
        stock_layout.addRow("CTP账户:", ctp_control_layout)

        layout.addWidget(stock_group)

        # 交易操作区
        trade_group = QGroupBox("交易操作")
        trade_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        trade_layout = QVBoxLayout(trade_group)

        # 订单类型选择
        order_type_layout = QHBoxLayout()
        order_type_layout.addWidget(QLabel("订单类型:"))

        from PyQt5.QtWidgets import QComboBox
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(["市价单", "限价单"])
        self.order_type_combo.currentIndexChanged.connect(self._on_order_type_changed)
        order_type_layout.addWidget(self.order_type_combo)
        order_type_layout.addStretch()

        trade_layout.addLayout(order_type_layout)

        # 价格输入（限价单时使用）
        self.price_input_layout = QHBoxLayout()
        self.price_input_layout.addWidget(QLabel("限价:"))

        from PyQt5.QtWidgets import QDoubleSpinBox
        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0.01, 999999.99)
        self.price_spin.setDecimals(2)
        self.price_spin.setValue(0.00)
        self.price_spin.setSingleStep(0.01)
        self.price_spin.setEnabled(False)
        self.price_spin.setFixedWidth(120)
        self.price_input_layout.addWidget(self.price_spin)
        self.price_input_layout.addStretch()

        trade_layout.addLayout(self.price_input_layout)

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
        self.position_table.setMinimumHeight(200)

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

    def _create_orders_tab(self, tab_widget: QTabWidget) -> None:
        """创建订单状态标签页"""
        orders_widget = QWidget()
        layout = QVBoxLayout(orders_widget)

        # 订单列表
        orders_group = QGroupBox("订单列表")
        orders_layout = QVBoxLayout(orders_group)

        # 订单表格
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(8)
        self.orders_table.setHorizontalHeaderLabels([
            "订单ID", "股票", "类型", "方向", "数量", "价格", "状态", "创建时间"
        ])
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.orders_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.orders_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        orders_layout.addWidget(self.orders_table)

        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.refresh_orders_btn = QPushButton("刷新订单")
        self.refresh_orders_btn.clicked.connect(self._refresh_orders)
        button_layout.addWidget(self.refresh_orders_btn)

        self.cancel_order_btn = QPushButton("撤销订单")
        self.cancel_order_btn.clicked.connect(self._on_cancel_order)
        self.cancel_order_btn.setEnabled(False)
        button_layout.addWidget(self.cancel_order_btn)

        button_layout.addStretch()
        orders_layout.addLayout(button_layout)

        layout.addWidget(orders_group)
        tab_widget.addTab(orders_widget, "订单状态")

        # 连接表格选择信号
        self.orders_table.itemSelectionChanged.connect(self._on_order_selection_changed)

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
        self.history_table.setMinimumHeight(200)

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

        # 持仓分布图表区域
        chart_group = QGroupBox("持仓分布")
        chart_layout = QVBoxLayout(chart_group)

        if MATPLOTLIB_AVAILABLE:
            self.portfolio_figure = Figure(figsize=(4, 3))
            self.portfolio_canvas = FigureCanvas(self.portfolio_figure)
            chart_layout.addWidget(self.portfolio_canvas)
            self._portfolio_chart_initialized = True
        else:
            self.chart_placeholder = QLabel("持仓分布图表\n（matplotlib未安装）")
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
            self._portfolio_chart_initialized = False

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

            # 检查订单类型
            is_limit_order = (self.order_type_combo.currentIndex() == 1)

            # 获取价格
            if is_limit_order:
                # 限价单：使用用户输入的价格
                current_price = Decimal(str(self.price_spin.value()))
                if current_price <= 0:
                    QMessageBox.warning(self, "买入失败", "请输入有效的限价")
                    return
            else:
                # 市价单：获取当前市场价格
                current_price = self._get_current_price()
                if not current_price:
                    QMessageBox.warning(self, "买入失败", "无法获取当前价格")
                    return

            # 计算预计金额
            estimated_amount = current_price * quantity

            # 检查可用资金
            if not self._portfolio:
                QMessageBox.warning(self, "买入失败", "无法获取投资组合信息")
                return

            available_cash = self._portfolio.available_cash
            if estimated_amount > available_cash:
                QMessageBox.warning(
                    self, "资金不足",
                    f"可用资金: ¥{available_cash:,.2f}\n"
                    f"预计金额: ¥{estimated_amount:,.2f}\n"
                    f"资金缺口: ¥{estimated_amount - available_cash:,.2f}"
                )
                return

            # 显示交易确认对话框
            order_type_text = "限价单" if is_limit_order else "市价单"
            reply = QMessageBox.question(
                self, "确认买入",
                f"股票: {self._current_stock_name} ({self._current_stock_code})\n"
                f"订单类型: {order_type_text}\n"
                f"数量: {quantity}股\n"
                f"价格: ¥{current_price:.2f}\n"
                f"预计金额: ¥{estimated_amount:,.2f}\n\n"
                f"确认买入吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # 异步执行买入操作
                self._execute_trade_async('BUY', quantity, current_price, is_limit_order)

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

            # 检查订单类型
            is_limit_order = (self.order_type_combo.currentIndex() == 1)

            # 获取价格
            if is_limit_order:
                # 限价单：使用用户输入的价格
                current_price = Decimal(str(self.price_spin.value()))
                if current_price <= 0:
                    QMessageBox.warning(self, "卖出失败", "请输入有效的限价")
                    return
            else:
                # 市价单：获取当前市场价格
                current_price = self._get_current_price()
                if not current_price:
                    QMessageBox.warning(self, "卖出失败", "无法获取当前价格")
                    return

            # 检查持仓
            position = self.trading_service.get_position(self._current_stock_code)
            if not position or position.quantity < quantity:
                QMessageBox.warning(
                    self, "持仓不足",
                    f"当前持仓: {position.quantity if position else 0}股\n"
                    f"卖出数量: {quantity}股"
                )
                return

            # 计算预计金额
            estimated_amount = current_price * quantity

            # 显示交易确认对话框
            order_type_text = "限价单" if is_limit_order else "市价单"
            reply = QMessageBox.question(
                self, "确认卖出",
                f"股票: {self._current_stock_name} ({self._current_stock_code})\n"
                f"订单类型: {order_type_text}\n"
                f"数量: {quantity}股\n"
                f"价格: ¥{current_price:.2f}\n"
                f"预计金额: ¥{estimated_amount:,.2f}\n\n"
                f"确认卖出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # 异步执行卖出操作
                self._execute_trade_async('SELL', quantity, current_price, is_limit_order)

        except Exception as e:
            logger.error(f"Sell button click failed: {e}")
            self.error_occurred.emit(f"卖出操作失败: {e}")

    def _execute_trade_async(self, action: str, quantity: int, current_price: Optional[Decimal] = None, is_limit_order: bool = False) -> None:
        """异步执行交易"""
        class TradeWorker(QThread):
            finished = pyqtSignal(object)
            error = pyqtSignal(str)

            def __init__(self, trading_service, action, stock_code, stock_name, quantity, current_price=None, is_limit_order=False):
                super().__init__()
                self.trading_service = trading_service
                self.action = action
                self.stock_code = stock_code
                self.stock_name = stock_name
                self.quantity = quantity
                self.current_price = current_price
                self.is_limit_order = is_limit_order

            def run(self):
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    if self.action == 'BUY':
                        result = loop.run_until_complete(
                            self.trading_service.execute_buy_order(
                                self.stock_code, self.stock_name, self.quantity, self.current_price
                            )
                        )
                    else:  # SELL
                        result = loop.run_until_complete(
                            self.trading_service.execute_sell_order(
                                self.stock_code, self.stock_name, self.quantity, self.current_price
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
            self._current_stock_code, self._current_stock_name, quantity, current_price, is_limit_order
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
                    f"交易失败: 状态={trade_record.status}"
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

    def _load_ctp_accounts(self) -> None:
        """加载CTP账户列表"""
        try:
            from core.trading.account_manager import AccountManager
            from core.trading.account_models import TradingInterfaceType
            
            account_manager = self._service_container.resolve(AccountManager)
            accounts = account_manager.get_all_accounts()
            
            self.ctp_account_combo.clear()
            ctp_count = 0
            
            for account in accounts:
                if account.trading_interface_type == TradingInterfaceType.CTP:
                    self.ctp_account_combo.addItem(
                        f"{account.account_name} ({account.account_id})",
                        account.account_id
                    )
                    ctp_count += 1
            
            if ctp_count == 0:
                self.ctp_account_combo.setPlaceholderText("无CTP账户")
            
            logger.info(f"加载CTP账户: {ctp_count} 个")
            
        except Exception as e:
            logger.error(f"加载CTP账户失败: {e}")

    def _on_ctp_connect_clicked(self) -> None:
        """CTP连接按钮点击事件"""
        try:
            account_id = self.ctp_account_combo.currentData()
            
            if not account_id:
                QMessageBox.warning(self, "警告", "请先选择CTP账户")
                return
            
            self.ctp_connect_btn.setEnabled(False)
            self.ctp_connect_btn.setText("连接中...")
            
            success, message = self.trading_service.connect_ctp_account(account_id)
            
            if success:
                QMessageBox.information(self, "成功", message)
                self.ctp_disconnect_btn.setEnabled(True)
                self._update_ctp_connection_status()
            else:
                QMessageBox.warning(self, "连接失败", message)
                self.ctp_connect_btn.setEnabled(True)
                self.ctp_connect_btn.setText("连接")
                
        except Exception as e:
            logger.error(f"CTP连接失败: {e}")
            QMessageBox.critical(self, "错误", f"CTP连接失败: {e}")
            self.ctp_connect_btn.setEnabled(True)
            self.ctp_connect_btn.setText("连接")

    def _on_ctp_disconnect_clicked(self) -> None:
        """CTP断开按钮点击事件"""
        try:
            account_id = self.ctp_account_combo.currentData()
            
            if not account_id:
                return
            
            reply = QMessageBox.question(
                self,
                "确认断开",
                f"确定要断开CTP账户 {account_id} 的连接吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                success, message = self.trading_service.disconnect_ctp_account(account_id)
                
                if success:
                    QMessageBox.information(self, "成功", message)
                    self.ctp_connect_btn.setEnabled(True)
                    self.ctp_connect_btn.setText("连接")
                    self.ctp_disconnect_btn.setEnabled(False)
                    self._update_ctp_connection_status()
                else:
                    QMessageBox.warning(self, "断开失败", message)
                    
        except Exception as e:
            logger.error(f"CTP断开连接失败: {e}")
            QMessageBox.critical(self, "错误", f"CTP断开连接失败: {e}")

    def _update_ctp_connection_status(self) -> None:
        """更新CTP连接状态"""
        try:
            # 检查TradingService中是否有CTP接口连接
            if hasattr(self.trading_service, '_ctp_interfaces'):
                ctp_interfaces = self.trading_service._ctp_interfaces
                ctp_market_interfaces = self.trading_service._ctp_market_interfaces
                
                if ctp_interfaces or ctp_market_interfaces:
                    # 有CTP连接
                    trading_count = len(ctp_interfaces)
                    market_count = len(ctp_market_interfaces)
                    
                    if trading_count > 0 and market_count > 0:
                        status_text = f"CTP已连接 (交易:{trading_count} 行情:{market_count})"
                        self.ctp_connection_label.setStyleSheet("color: green; font-weight: bold;")
                    elif trading_count > 0:
                        status_text = f"CTP交易已连接 ({trading_count})"
                        self.ctp_connection_label.setStyleSheet("color: orange; font-weight: bold;")
                    else:
                        status_text = f"CTP行情已连接 ({market_count})"
                        self.ctp_connection_label.setStyleSheet("color: orange; font-weight: bold;")
                    
                    self.ctp_connection_label.setText(status_text)
                else:
                    # 无CTP连接
                    self.ctp_connection_label.setText("CTP未连接")
                    self.ctp_connection_label.setStyleSheet("color: red; font-weight: bold;")
            else:
                # TradingService不支持CTP
                self.ctp_connection_label.setText("CTP不支持")
                self.ctp_connection_label.setStyleSheet("color: gray; font-weight: bold;")
                
        except Exception as e:
            logger.error(f"更新CTP连接状态失败: {e}")
            self.ctp_connection_label.setText("CTP状态未知")
            self.ctp_connection_label.setStyleSheet("color: gray; font-weight: bold;")

    def _get_current_price(self) -> Optional[Decimal]:
        """
        获取当前价格

        Returns:
            当前价格，如果无法获取则返回 None
        """
        try:
            # 1. 尝试从持仓获取当前价格
            position = self.trading_service.get_position(self._current_stock_code)
            if position and position.current_price:
                return position.current_price

            # 2. 尝试从 MarketService 获取实时行情
            try:
                from core.services.market_service import MarketService
                market_service = self.trading_service._service_container.resolve(MarketService)
                quote = market_service.get_quote(self._current_stock_code)
                if quote and quote.current_price:
                    return quote.current_price
            except Exception as e:
                logger.warning(f"Failed to get quote from MarketService: {e}")

            return None
        except Exception as e:
            logger.error(f"Failed to get current price: {e}")
            return None

    @pyqtSlot(int)
    def _on_order_type_changed(self, index: int) -> None:
        """
        处理订单类型变化

        Args:
            index: 订单类型索引（0=市价单，1=限价单）
        """
        is_limit_order = (index == 1)
        self.price_spin.setEnabled(is_limit_order)

        if not is_limit_order:
            # 市价单时，自动填充当前价格
            current_price = self._get_current_price()
            if current_price:
                self.price_spin.setValue(float(current_price))
        else:
            # 切换到限价单时，提示用户输入价格
            logger.info("Switched to limit order, please input price")

    @pyqtSlot()
    def _refresh_data(self) -> None:
        """刷新数据"""
        try:
            # 更新投资组合数据
            self._portfolio = self.trading_service.get_portfolio()

            # 更新UI显示
            self._update_portfolio_display()
            self._refresh_positions()
            self._refresh_orders()
            self._refresh_history()

            # 加载CTP账户列表
            self._load_ctp_accounts()

            # 更新CTP连接状态
            self._update_ctp_connection_status()

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

            # 更新持仓分布图表
            self._update_portfolio_chart()

        except Exception as e:
            logger.error(f"Failed to update portfolio display: {e}")

    def _update_portfolio_chart(self) -> None:
        """更新持仓分布图表"""
        if not hasattr(self, '_portfolio_chart_initialized') or not self._portfolio_chart_initialized:
            return

        try:
            if not self._portfolio or not self._portfolio.positions:
                self.portfolio_figure.clear()
                ax = self.portfolio_figure.add_subplot(111)
                ax.text(0.5, 0.5, '暂无持仓数据', ha='center', va='center', fontsize=12, color='#666666')
                self.portfolio_canvas.draw()
                return

            positions = self._portfolio.positions
            labels = []
            sizes = []
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']

            for symbol, position in positions.items():
                mv = float(position.market_value) if position.market_value else 0.0
                labels.append(f"{symbol}\n{position.symbol_name}")
                sizes.append(mv)

            if not sizes or sum(sizes) == 0:
                self.portfolio_figure.clear()
                ax = self.portfolio_figure.add_subplot(111)
                ax.text(0.5, 0.5, '持仓市值为空', ha='center', va='center', fontsize=12, color='#666666')
                self.portfolio_canvas.draw()
                return

            self.portfolio_figure.clear()
            ax = self.portfolio_figure.add_subplot(111)
            wedges, texts, autotexts = ax.pie(
                sizes,
                labels=labels,
                autopct='%1.1f%%',
                colors=colors[:len(sizes)],
                startangle=90,
                pctdistance=0.75
            )
            ax.set_title('持仓分布', fontsize=12, fontweight='bold')
            self.portfolio_canvas.draw()
            logger.debug("Portfolio chart updated")

        except Exception as e:
            logger.error(f"Failed to update portfolio chart: {e}")

    def _refresh_positions(self) -> None:
        """刷新持仓表格"""
        if not self._portfolio:
            return

        try:
            positions = self._portfolio.positions
            position_list = list(positions.values())
            self.position_table.setRowCount(len(position_list))

            for row, position in enumerate(position_list):
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
            history = self.trading_service.get_trade_history(limit=100)
            self.history_table.setRowCount(len(history))

            for row, record in enumerate(history):
                # 交易ID
                self.history_table.setItem(row, 0, QTableWidgetItem(record.trade_id[:8]))

                # 股票代码
                self.history_table.setItem(row, 1, QTableWidgetItem(record.symbol))

                # 股票名称
                self.history_table.setItem(row, 2, QTableWidgetItem(record.stock_name))

                # 操作类型
                action_text = "买入" if record.action == "buy" else "卖出"
                self.history_table.setItem(row, 3, QTableWidgetItem(action_text))

                # 数量
                self.history_table.setItem(row, 4, QTableWidgetItem(str(record.quantity)))

                # 价格
                self.history_table.setItem(row, 5, QTableWidgetItem(f"{record.price:.2f}"))

                # 金额
                self.history_table.setItem(row, 6, QTableWidgetItem(f"{record.total_amount:.2f}"))

                # 时间
                time_str = record.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                self.history_table.setItem(row, 7, QTableWidgetItem(time_str))

        except Exception as e:
            logger.error(f"Failed to refresh history: {e}")

    def _refresh_orders(self) -> None:
        """刷新订单表格"""
        try:
            orders = self.trading_service.get_active_orders()
            self.orders_table.setRowCount(len(orders))

            for row, order in enumerate(orders):
                # 订单ID
                self.orders_table.setItem(row, 0, QTableWidgetItem(order.order_id[:8]))

                # 股票
                self.orders_table.setItem(row, 1, QTableWidgetItem(f"{order.symbol_name}({order.symbol})"))

                # 订单类型
                order_type_text = "限价单" if order.order_type == OrderType.LIMIT else "市价单"
                self.orders_table.setItem(row, 2, QTableWidgetItem(order_type_text))

                # 方向
                side_text = "买入" if order.side == OrderSide.BUY else "卖出"
                self.orders_table.setItem(row, 3, QTableWidgetItem(side_text))

                # 数量
                self.orders_table.setItem(row, 4, QTableWidgetItem(str(order.quantity)))

                # 价格
                price_text = f"{order.price:.2f}" if order.price else "--"
                self.orders_table.setItem(row, 5, QTableWidgetItem(price_text))

                # 状态
                status_text = {
                    OrderStatus.PENDING: "待成交",
                    OrderStatus.FILLED: "已成交",
                    OrderStatus.CANCELLED: "已取消",
                    OrderStatus.REJECTED: "已拒绝"
                }.get(order.status, str(order.status))
                self.orders_table.setItem(row, 6, QTableWidgetItem(status_text))

                # 创建时间
                time_str = order.created_time.strftime("%Y-%m-%d %H:%M:%S")
                self.orders_table.setItem(row, 7, QTableWidgetItem(time_str))

        except Exception as e:
            logger.error(f"Failed to refresh orders: {e}")

    def _on_order_selection_changed(self) -> None:
        """处理订单选择变化"""
        try:
            selected_rows = self.orders_table.selectionModel().selectedRows()
            has_selection = len(selected_rows) > 0
            self.cancel_order_btn.setEnabled(has_selection)
        except Exception as e:
            logger.error(f"Failed to handle order selection: {e}")

    @pyqtSlot()
    def _on_cancel_order(self) -> None:
        """撤销订单"""
        try:
            selected_rows = self.orders_table.selectionModel().selectedRows()
            if not selected_rows:
                QMessageBox.warning(self, "提示", "请先选择要撤销的订单")
                return

            # 获取订单ID
            row = selected_rows[0].row()
            order_id_item = self.orders_table.item(row, 0)
            order_id = order_id_item.text()

            # 确认撤销
            reply = QMessageBox.question(
                self, "撤销订单",
                f"确定要撤销订单 {order_id} 吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                success, message = self.trading_service.cancel_order(order_id)
                
                if success:
                    QMessageBox.information(self, "成功", message)
                    self._refresh_orders()
                else:
                    QMessageBox.warning(self, "失败", message)

        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            QMessageBox.critical(self, "错误", f"撤销订单失败: {e}")

    @pyqtSlot()
    def _on_clear_positions(self) -> None:
        """清空持仓"""
        try:
            # 获取当前持仓
            positions = self.trading_service.get_all_positions()
            
            if not positions:
                QMessageBox.information(self, "提示", "当前没有持仓")
                return

            # 显示持仓列表
            positions_text = "\n".join([
                f"  • {pos.symbol_name} ({pos.symbol}): {pos.quantity}股"
                for pos in positions.values()
            ])

            reply = QMessageBox.question(
                self, 
                "清空持仓",
                f"确定要清空以下持仓吗？此操作不可撤销！\n\n{positions_text}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # 清空持仓
                success, message = self.trading_service.clear_all_positions()
                
                if success:
                    QMessageBox.information(self, "成功", message)
                    # 刷新数据
                    self._refresh_data()
                else:
                    QMessageBox.warning(self, "失败", message)

        except Exception as e:
            logger.error(f"清空持仓失败: {e}")
            QMessageBox.critical(self, "错误", f"清空持仓失败: {e}")

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
            # 取消事件订阅
            self.event_bus.unsubscribe(StockSelectedEvent, self._on_stock_selected)
            self.event_bus.unsubscribe(TradeExecutedEvent, self._on_trade_executed)
            self.event_bus.unsubscribe(PositionUpdatedEvent, self._on_position_updated)

            logger.debug("Trading panel disposed")

        except Exception as e:
            logger.error(f"Failed to dispose trading panel: {e}")
