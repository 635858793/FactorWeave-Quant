from loguru import logger
"""
交易控件模块 - 重构版本

使用服务容器获取交易服务，符合插件架构原则
"""
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import *
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QColor
import traceback
import time
from datetime import datetime
from PyQt5.QtWebEngineWidgets import QWebEngineView
import threading
import pandas as pd
import plotly.graph_objs as go
import plotly.io as pio

from utils.config_manager import ConfigManager

# 延迟导入主题管理器，避免在模块级别导入时崩溃
THEME_MANAGER_AVAILABLE = False
get_theme_manager = None

def _import_theme_manager():
    """延迟导入主题管理器"""
    global THEME_MANAGER_AVAILABLE, get_theme_manager
    if not THEME_MANAGER_AVAILABLE:
        try:
            from utils.theme import get_theme_manager as _get_theme_manager
            get_theme_manager = _get_theme_manager
            THEME_MANAGER_AVAILABLE = True
            logger.info("主题管理器模块导入成功")
        except Exception as e:
            logger.warning(f"导入主题管理器失败: {e}")
# log_structured已替换为直接的logger调用
from core.containers import get_service_container


class AnalysisStep:
    def __init__(self, step_id: str, name: str):
        self.step_id = step_id
        self.name = name
        self.status = 'pending'  # pending, running, success, failed
        self.start_time = None
        self.end_time = None
        self.duration = None
        self.log = ''
        self.error = ''

    def start(self):
        self.status = 'running'
        self.start_time = time.time()

    def finish(self, success=True, log='', error=''):
        self.status = 'success' if success else 'failed'
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time if self.start_time else None
        self.log = log
        self.error = error


class AnalysisProcessManager:
    def __init__(self):
        self.steps: List[AnalysisStep] = []
        self.history: List[List[AnalysisStep]] = []
        self.current_index = -1

    def add_step(self, step: AnalysisStep):
        self.steps.append(step)

    def start_step(self, step_id: str):
        step = self.get_step(step_id)
        if step:
            step.start()

    def finish_step(self, step_id: str, success=True, log='', error=''):
        step = self.get_step(step_id)
        if step:
            step.finish(success, log, error)

    def get_step(self, step_id: str) -> Optional[AnalysisStep]:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None

    def reset(self):
        if self.steps:
            self.history.append(self.steps)
        self.steps = []
        self.current_index += 1

    def get_history(self):
        return self.history


class TradingWidget(QWidget):
    """交易控件类 - 重构版本"""

    # 定义信号
    strategy_changed = pyqtSignal(str)  # 策略变更信号
    trade_executed = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)  # 错误信号
    analysis_progress = pyqtSignal(dict)  # 进度信号，dict包含step_id、status、msg、耗时等

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """初始化交易控件

        Args:
            config_manager: Optional ConfigManager instance to use
        """
        super().__init__()

        # 服务依赖
        self.service_container = get_service_container()
        self._trading_service = None
        self._trading_controller = None
        self._unified_data_manager = None
        self._trading_confirmation_service = None

        # 初始化基本属性
        self.current_stock = None
        self.current_signals = []
        self.current_positions = []
        # 纯Loguru架构，移除log_manager依赖
        self.config_manager = config_manager or ConfigManager()
        
        # 延迟导入并初始化主题管理器
        _import_theme_manager()
        self.theme_manager = None
        if THEME_MANAGER_AVAILABLE:
            try:
                self.theme_manager = get_theme_manager(self.config_manager)
            except Exception as e:
                logger.warning(f"获取ThemeManager失败: {e}")
        
        self.process_manager = AnalysisProcessManager()

        try:
            # 初始化服务
            self._initialize_services()

            # 初始化UI
            self.init_ui()

            # 连接信号
            self.connect_signals()

            logger.info("trading_widget_init", status="success")

        except Exception as e:
            error_msg = f"初始化交易控件失败: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.error_occurred.emit(error_msg)

    def _initialize_services(self):
        """初始化服务依赖"""
        try:
            # 初始化交易服务
            from core.services.trading_service import TradingService
            self._trading_service = self.service_container.resolve(TradingService)
            if self._trading_service:
                logger.info("交易服务初始化成功")
            else:
                logger.warning("交易服务初始化失败")

            # 初始化交易控制器
            from core.trading_controller import TradingController
            self._trading_controller = self.service_container.resolve(TradingController)
            if self._trading_controller:
                logger.info("交易控制器初始化成功")
            else:
                logger.warning("交易控制器初始化失败")

            # 初始化统一数据管理器
            from core.services.unified_data_manager import UnifiedDataManager
            self._unified_data_manager = self.service_container.resolve(UnifiedDataManager)
            if self._unified_data_manager:
                logger.info("统一数据管理器初始化成功")
            else:
                logger.warning("统一数据管理器初始化失败")

            # 初始化交易确认与风控服务
            from core.services.trading_confirmation_service import TradingConfirmationService
            self._trading_confirmation_service = self.service_container.resolve(TradingConfirmationService)
            if self._trading_confirmation_service:
                logger.info("交易确认与风控服务初始化成功")
            else:
                logger.warning("交易确认与风控服务初始化失败")

        except Exception as e:
            logger.error(f"服务初始化失败: {e}")

    def init_ui(self):
        """初始化UI"""
        try:
            layout = QVBoxLayout(self)

            # 创建策略选择组
            strategy_group = QGroupBox("交易策略")
            strategy_layout = QVBoxLayout(strategy_group)

            self.strategy_combo = QComboBox()
            self.strategy_combo.addItems([
                "MA策略", "MACD策略", "RSI策略", "布林带策略",
                "KDJ策略", "形态分析策略", "自定义策略"
            ])
            strategy_layout.addWidget(self.strategy_combo)

            # 创建参数设置组
            params_group = QGroupBox("参数设置")
            params_layout = QFormLayout(params_group)

            # 创建交易按钮
            buttons_layout = QHBoxLayout()

            self.buy_button = QPushButton("买入")
            self.buy_button.clicked.connect(self.execute_buy)
            buttons_layout.addWidget(self.buy_button)

            self.sell_button = QPushButton("卖出")
            self.sell_button.clicked.connect(self.execute_sell)
            buttons_layout.addWidget(self.sell_button)

            self.cancel_button = QPushButton("撤单")
            self.cancel_button.clicked.connect(self.cancel_order)
            buttons_layout.addWidget(self.cancel_button)

            # 添加到布局
            layout.addWidget(strategy_group)
            layout.addWidget(params_group)
            layout.addLayout(buttons_layout)

            # 创建分析操作按钮
            analysis_buttons_layout = QHBoxLayout()
            self.signal_btn = QPushButton("计算信号")
            analysis_buttons_layout.addWidget(self.signal_btn)
            self.backtest_btn = QPushButton("运行回测")
            analysis_buttons_layout.addWidget(self.backtest_btn)
            layout.addLayout(analysis_buttons_layout)

            # 创建策略参数输入控件
            strategy_params_group = QGroupBox("策略参数")
            strategy_params_layout = QFormLayout(strategy_params_group)

            self.ma_short_spin = QSpinBox()
            self.ma_short_spin.setRange(2, 120)
            self.ma_short_spin.setValue(5)
            strategy_params_layout.addRow("MA短周期:", self.ma_short_spin)

            self.ma_long_spin = QSpinBox()
            self.ma_long_spin.setRange(5, 250)
            self.ma_long_spin.setValue(10)
            strategy_params_layout.addRow("MA长周期:", self.ma_long_spin)

            self.macd_short_spin = QSpinBox()
            self.macd_short_spin.setRange(5, 50)
            self.macd_short_spin.setValue(7)
            strategy_params_layout.addRow("MACD快线:", self.macd_short_spin)

            self.macd_long_spin = QSpinBox()
            self.macd_long_spin.setRange(10, 100)
            self.macd_long_spin.setValue(26)
            strategy_params_layout.addRow("MACD慢线:", self.macd_long_spin)

            self.macd_signal_spin = QSpinBox()
            self.macd_signal_spin.setRange(2, 20)
            self.macd_signal_spin.setValue(9)
            strategy_params_layout.addRow("MACD信号:", self.macd_signal_spin)

            self.kdj_n_spin = QSpinBox()
            self.kdj_n_spin.setRange(3, 30)
            self.kdj_n_spin.setValue(9)
            strategy_params_layout.addRow("KDJ N:", self.kdj_n_spin)

            self.kdj_m1_spin = QSpinBox()
            self.kdj_m1_spin.setRange(1, 10)
            self.kdj_m1_spin.setValue(3)
            strategy_params_layout.addRow("KDJ M1:", self.kdj_m1_spin)

            self.kdj_m2_spin = QSpinBox()
            self.kdj_m2_spin.setRange(1, 10)
            self.kdj_m2_spin.setValue(3)
            strategy_params_layout.addRow("KDJ M2:", self.kdj_m2_spin)

            # 回测参数
            backtest_params_group = QGroupBox("回测参数")
            backtest_params_layout = QFormLayout(backtest_params_group)

            self.initial_cash_spin = QDoubleSpinBox()
            self.initial_cash_spin.setRange(1000, 100000000)
            self.initial_cash_spin.setValue(100000.0)
            self.initial_cash_spin.setPrefix("¥")
            backtest_params_layout.addRow("初始资金:", self.initial_cash_spin)

            self.commission_spin = QDoubleSpinBox()
            self.commission_spin.setRange(0.0, 0.1)
            self.commission_spin.setSingleStep(0.0001)
            self.commission_spin.setDecimals(6)
            self.commission_spin.setValue(0.0003)
            backtest_params_layout.addRow("佣金率:", self.commission_spin)

            self.slippage_spin = QDoubleSpinBox()
            self.slippage_spin.setRange(0.0, 0.1)
            self.slippage_spin.setSingleStep(0.0001)
            self.slippage_spin.setDecimals(6)
            self.slippage_spin.setValue(0.0001)
            backtest_params_layout.addRow("滑点:", self.slippage_spin)

            layout.addWidget(strategy_params_group)
            layout.addWidget(backtest_params_group)

            # 填充 param_controls 字典
            self.param_controls = {
                'ma_short': self.ma_short_spin,
                'ma_long': self.ma_long_spin,
                'macd_short': self.macd_short_spin,
                'macd_long': self.macd_long_spin,
                'macd_signal': self.macd_signal_spin,
                'kdj_n': self.kdj_n_spin,
                'kdj_m1': self.kdj_m1_spin,
                'kdj_m2': self.kdj_m2_spin,
                'initial_cash': self.initial_cash_spin,
                'commission_rate': self.commission_spin,
                'slippage': self.slippage_spin,
            }

            # 新增：创建绩效指标表格并放入滚动区
            self.performance_table = QTableWidget()
            self.performance_table.setColumnCount(2)
            self.performance_table.setHorizontalHeaderLabels(["绩效指标", "数值"])
            perf_scroll = QScrollArea()
            perf_scroll.setWidgetResizable(True)
            perf_scroll.setWidget(self.performance_table)
            layout.addWidget(perf_scroll)

            # 新增：创建风险指标表格并放入滚动区
            self.risk_table = QTableWidget()
            self.risk_table.setColumnCount(2)
            self.risk_table.setHorizontalHeaderLabels(["风险指标", "数值"])
            risk_scroll = QScrollArea()
            risk_scroll.setWidgetResizable(True)
            risk_scroll.setWidget(self.risk_table)
            layout.addWidget(risk_scroll)

            # 新增：创建信号明细表格
            self.signal_table = QTableWidget()
            self.signal_table.setColumnCount(5)
            self.signal_table.setHorizontalHeaderLabels(
                ["时间", "类型", "信号", "价格", "强度"])
            layout.addWidget(self.signal_table)

            # 创建持仓信息表格
            self.position_table = QTableWidget()
            self.position_table.setColumnCount(6)
            self.position_table.setHorizontalHeaderLabels([
                "股票代码", "股票名称", "持仓数量", "持仓成本", "当前价格", "盈亏比例"
            ])
            layout.addWidget(self.position_table)

            # 创建交易记录表格
            self.trade_table = QTableWidget()
            self.trade_table.setColumnCount(7)
            self.trade_table.setHorizontalHeaderLabels([
                "时间", "股票代码", "交易类型", "成交价格", "成交数量", "成交金额", "手续费"
            ])
            layout.addWidget(self.trade_table)

            logger.info("交易控件UI初始化完成")

        except Exception as e:
            error_msg = f"初始化UI失败: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.error_occurred.emit(error_msg)

    def connect_signals(self):
        """连接信号"""
        try:
            # 连接策略选择信号
            self.strategy_combo.currentTextChanged.connect(
                self.on_strategy_changed)

            logger.info("信号连接完成")

        except Exception as e:
            error_msg = f"连接信号失败: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.error_occurred.emit(error_msg)

    def execute_buy(self):
        """执行买入操作"""
        try:
            if not self.current_stock:
                QMessageBox.warning(self, "买入失败", "请先选择股票")
                return

            # 获取当前价格
            current_price = self._get_current_price()
            if not current_price:
                QMessageBox.warning(self, "买入失败", "无法获取当前价格")
                return

            # 创建买入对话框
            buy_dialog = QDialog(self)
            buy_dialog.setWindowTitle("买入股票")
            buy_dialog.setModal(True)
            buy_dialog.resize(300, 200)

            layout = QVBoxLayout(buy_dialog)

            # 股票信息
            info_label = QLabel(f"股票代码: {self.current_stock}")
            layout.addWidget(info_label)

            price_label = QLabel(f"当前价格: {current_price:.2f}")
            layout.addWidget(price_label)

            # 买入数量
            quantity_layout = QHBoxLayout()
            quantity_layout.addWidget(QLabel("买入数量:"))
            quantity_spin = QSpinBox()
            quantity_spin.setRange(100, 999999)
            quantity_spin.setValue(100)
            quantity_spin.setSingleStep(100)
            quantity_layout.addWidget(quantity_spin)
            layout.addLayout(quantity_layout)

            # 预计金额
            amount_label = QLabel(f"预计金额: {current_price * 100:.2f}")
            layout.addWidget(amount_label)

            # 更新金额显示
            def update_amount():
                amount = current_price * quantity_spin.value()
                amount_label.setText(f"预计金额: {amount:.2f}")

            quantity_spin.valueChanged.connect(update_amount)

            # 按钮
            button_layout = QHBoxLayout()
            confirm_btn = QPushButton("确认买入")
            cancel_btn = QPushButton("取消")
            button_layout.addWidget(confirm_btn)
            button_layout.addWidget(cancel_btn)
            layout.addLayout(button_layout)

            def on_confirm():
                quantity = quantity_spin.value()
                amount = current_price * quantity

                from core.services.trading_service import TradingOrder, OrderType, OrderSide
                from decimal import Decimal

                order = TradingOrder(
                    order_id=f"order_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    symbol=self.current_stock,
                    symbol_name=self.current_stock,
                    order_type=OrderType.MARKET,
                    side=OrderSide.BUY,
                    quantity=quantity,
                    price=Decimal(str(current_price))
                )

                if self._trading_confirmation_service:
                    try:
                        confirmation_result = self._trading_confirmation_service.confirm_order(order)

                        if not confirmation_result.get('approved', False):
                            error_msg = confirmation_result.get('error', '订单验证失败')
                            QMessageBox.warning(self, "买入失败", f"订单验证失败: {error_msg}")
                            return
                    except Exception as e:
                        logger.error(f"订单验证异常: {e}")
                        QMessageBox.warning(self, "买入失败", f"订单验证异常: {str(e)}")
                        return

                if self._trading_service:
                    try:
                        success, result = self._trading_service.create_order(
                            symbol=self.current_stock,
                            symbol_name=self.current_stock,
                            order_type=OrderType.MARKET,
                            side=OrderSide.BUY,
                            quantity=quantity,
                            price=Decimal(str(current_price))
                        )
                        if not success:
                            QMessageBox.warning(self, "买入失败", f"创建订单失败: {result}")
                            return
                        order_id = result

                        success, message = self._trading_service.execute_order(
                            order_id, Decimal(str(current_price))
                        )
                        if not success:
                            QMessageBox.warning(self, "买入失败", f"执行订单失败: {message}")
                            return
                    except Exception as e:
                        logger.error(f"交易服务调用异常: {e}")
                        QMessageBox.warning(self, "买入失败", f"交易服务异常: {str(e)}")
                        return
                else:
                    logger.warning("TradingService 不可用，仅记录本地交易")

                trade_record = {
                    'time': datetime.now(),
                    'stock_code': self.current_stock,
                    'type': 'BUY',
                    'price': current_price,
                    'quantity': quantity,
                    'amount': amount,
                    'fee': amount * 0.0003
                }

                self._update_position(trade_record)
                self._record_trade(trade_record)
                self.trade_executed.emit(trade_record)

                QMessageBox.information(self, "买入成功",
                                        f"成功买入 {self.current_stock} {quantity}股")
                buy_dialog.accept()

            confirm_btn.clicked.connect(on_confirm)
            cancel_btn.clicked.connect(buy_dialog.reject)

            buy_dialog.exec_()

        except Exception as e:
            error_msg = f"买入操作失败: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.error_occurred.emit(error_msg)

    def execute_sell(self):
        """执行卖出操作"""
        try:
            if not self.current_stock:
                QMessageBox.warning(self, "卖出失败", "请先选择股票")
                return

            # 检查持仓
            position = self._get_position(self.current_stock)
            if not position or position['quantity'] <= 0:
                QMessageBox.warning(self, "卖出失败", "没有该股票的持仓")
                return

            # 获取当前价格
            current_price = self._get_current_price()
            if not current_price:
                QMessageBox.warning(self, "卖出失败", "无法获取当前价格")
                return

            # 创建卖出对话框
            sell_dialog = QDialog(self)
            sell_dialog.setWindowTitle("卖出股票")
            sell_dialog.setModal(True)
            sell_dialog.resize(300, 250)

            layout = QVBoxLayout(sell_dialog)

            # 股票信息
            info_label = QLabel(f"股票代码: {self.current_stock}")
            layout.addWidget(info_label)

            price_label = QLabel(f"当前价格: {current_price:.2f}")
            layout.addWidget(price_label)

            # 持仓信息
            position_label = QLabel(f"持仓数量: {position['quantity']}")
            layout.addWidget(position_label)

            cost_label = QLabel(f"持仓成本: {position['cost']:.2f}")
            layout.addWidget(cost_label)

            # 卖出数量
            quantity_layout = QHBoxLayout()
            quantity_layout.addWidget(QLabel("卖出数量:"))
            quantity_spin = QSpinBox()
            quantity_spin.setRange(100, position['quantity'])
            quantity_spin.setValue(min(100, position['quantity']))
            quantity_spin.setSingleStep(100)
            quantity_layout.addWidget(quantity_spin)
            layout.addLayout(quantity_layout)

            # 预计金额和盈亏
            amount_label = QLabel(
                f"预计金额: {current_price * quantity_spin.value():.2f}")
            layout.addWidget(amount_label)

            profit_label = QLabel()
            layout.addWidget(profit_label)

            # 更新金额和盈亏显示
            def update_amount():
                quantity = quantity_spin.value()
                amount = current_price * quantity
                cost_amount = position['cost'] * quantity
                profit = amount - cost_amount
                profit_rate = (profit / cost_amount) * \
                    100 if cost_amount > 0 else 0

                amount_label.setText(f"预计金额: {amount:.2f}")
                profit_label.setText(
                    f"预计盈亏: {profit:.2f} ({profit_rate:.2f}%)")

                # 设置盈亏颜色
                if profit > 0:
                    profit_label.setStyleSheet("color: red;")
                elif profit < 0:
                    profit_label.setStyleSheet("color: green;")
                else:
                    profit_label.setStyleSheet("color: black;")

            quantity_spin.valueChanged.connect(update_amount)
            update_amount()  # 初始化显示

            # 按钮
            button_layout = QHBoxLayout()
            confirm_btn = QPushButton("确认卖出")
            cancel_btn = QPushButton("取消")
            button_layout.addWidget(confirm_btn)
            button_layout.addWidget(cancel_btn)
            layout.addLayout(button_layout)

            def on_confirm():
                quantity = quantity_spin.value()
                amount = current_price * quantity

                from core.services.trading_service import TradingOrder, OrderType, OrderSide
                from decimal import Decimal

                order = TradingOrder(
                    order_id=f"order_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    symbol=self.current_stock,
                    symbol_name=self.current_stock,
                    order_type=OrderType.MARKET,
                    side=OrderSide.SELL,
                    quantity=quantity,
                    price=Decimal(str(current_price))
                )

                if self._trading_confirmation_service:
                    try:
                        confirmation_result = self._trading_confirmation_service.confirm_order(order)

                        if not confirmation_result.get('approved', False):
                            error_msg = confirmation_result.get('error', '订单验证失败')
                            QMessageBox.warning(self, "卖出失败", f"订单验证失败: {error_msg}")
                            return
                    except Exception as e:
                        logger.error(f"订单验证异常: {e}")
                        QMessageBox.warning(self, "卖出失败", f"订单验证异常: {str(e)}")
                        return

                if self._trading_service:
                    try:
                        success, result = self._trading_service.create_order(
                            symbol=self.current_stock,
                            symbol_name=self.current_stock,
                            order_type=OrderType.MARKET,
                            side=OrderSide.SELL,
                            quantity=quantity,
                            price=Decimal(str(current_price))
                        )
                        if not success:
                            QMessageBox.warning(self, "卖出失败", f"创建订单失败: {result}")
                            return
                        order_id = result

                        success, message = self._trading_service.execute_order(
                            order_id, Decimal(str(current_price))
                        )
                        if not success:
                            QMessageBox.warning(self, "卖出失败", f"执行订单失败: {message}")
                            return
                    except Exception as e:
                        logger.error(f"交易服务调用异常: {e}")
                        QMessageBox.warning(self, "卖出失败", f"交易服务异常: {str(e)}")
                        return
                else:
                    logger.warning("TradingService 不可用，仅记录本地交易")

                trade_record = {
                    'time': datetime.now(),
                    'stock_code': self.current_stock,
                    'type': 'SELL',
                    'price': current_price,
                    'quantity': quantity,
                    'amount': amount,
                    'fee': amount * 0.0003
                }

                self._update_position(trade_record)
                self._record_trade(trade_record)

                # 发送信号
                self.trade_executed.emit(trade_record)

                QMessageBox.information(self, "卖出成功",
                                        f"成功卖出 {self.current_stock} {quantity}股")
                sell_dialog.accept()

            confirm_btn.clicked.connect(on_confirm)
            cancel_btn.clicked.connect(sell_dialog.reject)

            sell_dialog.exec_()

        except Exception as e:
            error_msg = f"卖出操作失败: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.error_occurred.emit(error_msg)

    def cancel_order(self):
        """撤销订单"""
        try:
            # 获取待撤销的订单列表
            pending_orders = self._get_pending_orders()

            if not pending_orders:
                QMessageBox.information(self, "撤单", "没有待撤销的订单")
                return

            # 创建撤单对话框
            cancel_dialog = QDialog(self)
            cancel_dialog.setWindowTitle("撤销订单")
            cancel_dialog.setModal(True)
            cancel_dialog.resize(400, 300)

            layout = QVBoxLayout(cancel_dialog)

            # 订单列表
            order_table = QTableWidget()
            order_table.setColumnCount(5)
            order_table.setHorizontalHeaderLabels(
                ["订单ID", "股票代码", "类型", "价格", "数量"])
            order_table.setRowCount(len(pending_orders))

            for i, order in enumerate(pending_orders):
                order_table.setItem(i, 0, QTableWidgetItem(str(order['id'])))
                order_table.setItem(
                    i, 1, QTableWidgetItem(order['stock_code']))
                order_table.setItem(i, 2, QTableWidgetItem(order['type']))
                order_table.setItem(
                    i, 3, QTableWidgetItem(f"{order['price']:.2f}"))
                order_table.setItem(
                    i, 4, QTableWidgetItem(str(order['quantity'])))

            order_table.resizeColumnsToContents()
            layout.addWidget(order_table)

            # 按钮
            button_layout = QHBoxLayout()
            cancel_btn = QPushButton("撤销选中订单")
            cancel_all_btn = QPushButton("撤销全部订单")
            close_btn = QPushButton("关闭")
            button_layout.addWidget(cancel_btn)
            button_layout.addWidget(cancel_all_btn)
            button_layout.addWidget(close_btn)
            layout.addLayout(button_layout)

            def cancel_selected():
                current_row = order_table.currentRow()
                if current_row >= 0:
                    order = pending_orders[current_row]
                    self._cancel_order(order['id'])
                    QMessageBox.information(
                        self, "撤单成功", f"订单 {order['id']} 已撤销")
                    cancel_dialog.accept()
                else:
                    QMessageBox.warning(self, "撤单失败", "请选择要撤销的订单")

            def cancel_all():
                reply = QMessageBox.question(self, "确认撤单", "确定要撤销所有订单吗？",
                                             QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    for order in pending_orders:
                        self._cancel_order(order['id'])
                    QMessageBox.information(
                        self, "撤单成功", f"已撤销 {len(pending_orders)} 个订单")
                    cancel_dialog.accept()

            cancel_btn.clicked.connect(cancel_selected)
            cancel_all_btn.clicked.connect(cancel_all)
            close_btn.clicked.connect(cancel_dialog.reject)

            cancel_dialog.exec_()

        except Exception as e:
            error_msg = f"撤单操作失败: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.error_occurred.emit(error_msg)

    def update_stock(self, stock_info: Dict[str, str]):
        """更新股票信息

        Args:
            stock_info: 股票信息字典
        """
        try:
            # 自动提取股票代码
            if isinstance(stock_info, dict):
                code = stock_info.get('code') or stock_info.get(
                    'stock') or next(iter(stock_info.values()), None)
            else:
                code = stock_info
            if not isinstance(code, str) or not code.strip():
                self.current_stock = None
                logger.error("update_stock: 股票信息无效，未能提取到股票代码")
                QMessageBox.warning(
                    self, "股票选择错误", "update_stock：未能提取到有效的股票代码，请重新选择股票！")
                return
            else:
                self.current_stock = code.strip()

            # 清除现有数据
            self.clear_data()

            # 重新计算信号
            self.calculate_signals()

        except Exception as e:
            logger.error(f"更新股票信息失败: {str(e)}")

    def update_signals(self, signals: List[Dict[str, Any]]):
        """更新信号列表

        Args:
            signals: 信号列表
        """
        try:
            self.current_signals = signals

            self.signal_table.setRowCount(len(signals))

            for i, signal in enumerate(signals):
                self.signal_table.setItem(
                    i, 0,
                    QTableWidgetItem(signal['time'].strftime('%Y-%m-%d'))
                )
                self.signal_table.setItem(
                    i, 1,
                    QTableWidgetItem(signal['type'])
                )
                self.signal_table.setItem(
                    i, 2,
                    QTableWidgetItem(signal['signal'])
                )
                self.signal_table.setItem(
                    i, 3,
                    QTableWidgetItem(f"{signal['price']:.3f}")
                )
                self.signal_table.setItem(
                    i, 4,
                    QTableWidgetItem(f"{signal['strength']:.4f}")
                )

            # 调整列宽
            self.signal_table.resizeColumnsToContents()

        except Exception as e:
            logger.error(f"更新信号列表失败: {str(e)}")

    def update_backtest_results(self, results: Dict[str, Any]):
        """美化回测结果表格，支持多策略对比和多种可视化"""
        try:
            from PyQt5.QtWidgets import QTableWidgetItem, QAbstractItemView, QHeaderView, QPushButton, QDialog, QVBoxLayout, QLabel
            from PyQt5.QtGui import QFont, QColor, QBrush
            # 1. 分组展示绩效、风险、交易指标
            perf = results.get('performance') or results.get('metrics') or {}
            risk = results.get('risk', {})
            trades = results.get('trades', [])
            perf_items = list(perf.items())
            self.performance_table.setRowCount(len(perf_items))
            font_bold = QFont()
            font_bold.setBold(True)
            for i, (k, v) in enumerate(perf_items):
                item0 = QTableWidgetItem(str(k))
                item1 = QTableWidgetItem(
                    f"{v:.4f}" if isinstance(v, float) else str(v))
                if '率' in k or 'return' in k:
                    item1.setForeground(
                        QColor('green') if v >= 0 else QColor('red'))
                if i % 2 == 0:
                    item0.setBackground(QBrush(QColor(245, 245, 250)))
                    item1.setBackground(QBrush(QColor(245, 245, 250)))
                item0.setFont(font_bold)
                item1.setFont(font_bold)
                self.performance_table.setItem(i, 0, item0)
                self.performance_table.setItem(i, 1, item1)
            self.performance_table.setSortingEnabled(True)
            self.performance_table.setSelectionBehavior(
                QAbstractItemView.SelectRows)
            self.performance_table.setEditTriggers(
                QAbstractItemView.NoEditTriggers)
            self.performance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.performance_table.setStyleSheet(
                "QTableWidget {border-radius: 8px; border: 1px solid #d0d0d0; background: #fff;}")
            risk_items = list(risk.items())
            self.risk_table.setRowCount(len(risk_items))
            for i, (k, v) in enumerate(risk_items):
                item0 = QTableWidgetItem(str(k))
                item1 = QTableWidgetItem(
                    f"{v:.4f}" if isinstance(v, float) else str(v))
                if 'drawdown' in k or '风险' in k:
                    item1.setForeground(QColor('red'))
                if i % 2 == 0:
                    item0.setBackground(QBrush(QColor(245, 245, 250)))
                    item1.setBackground(QBrush(QColor(245, 245, 250)))
                item0.setFont(font_bold)
                item1.setFont(font_bold)
                self.risk_table.setItem(i, 0, item0)
                self.risk_table.setItem(i, 1, item1)
            self.risk_table.setSortingEnabled(True)
            self.risk_table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.risk_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.risk_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.risk_table.setStyleSheet(
                "QTableWidget {border-radius: 8px; border: 1px solid #d0d0d0; background: #fff;}")
            # 2. 多策略对比与自定义可视化
            if hasattr(self, 'trend_chart_area'):
                self.trend_chart_area.setHtml("")
            else:
                self.trend_chart_area = QWebEngineView()
                self.layout().addWidget(self.trend_chart_area)
            # 多策略对比数据结构：results['multi_strategy'] = {'策略A': {...}, '策略B': {...}}
            multi_strategy = results.get('multi_strategy', None)
            fig = go.Figure()
            if multi_strategy:
                # 分组柱状图：对比年化收益、最大回撤等
                metrics = ['annualized_return', 'max_drawdown', 'sharpe_ratio']
                data = {k: [v.get(m, 0) for m in metrics]
                        for k, v in multi_strategy.items()}
                for i, m in enumerate(metrics):
                    fig.add_trace(go.Bar(name=m, x=list(data.keys()), y=[
                                  v[i] for v in data.values()]))
                fig.update_layout(
                    barmode='group', title='多策略分组对比', template='plotly_white')
                # 热力图
                heat_data = pd.DataFrame(data, index=metrics)
                fig2 = go.Figure(data=go.Heatmap(
                    z=heat_data.values, x=heat_data.columns, y=heat_data.index, colorscale='Viridis'))
                fig2.update_layout(title='多策略指标热力图', template='plotly_white')
                # 雷达图
                for k, v in data.items():
                    fig3 = go.Figure()
                    fig3.add_trace(go.Scatterpolar(
                        r=v, theta=metrics, fill='toself', name=k))
                    fig3.update_layout(polar=dict(radialaxis=dict(
                        visible=True)), showlegend=True, title=f'{k}雷达图', template='plotly_white')
                    # 合并雷达图到主图
                    html3 = pio.to_html(
                        fig3, full_html=False, include_plotlyjs='cdn')
                    self.trend_chart_area.setHtml(
                        self.trend_chart_area.page().toHtml() + html3)
                # 主分组图和热力图合并
                html = pio.to_html(fig, full_html=False,
                                   include_plotlyjs='cdn')
                html2 = pio.to_html(fig2, full_html=False,
                                    include_plotlyjs=False)
                self.trend_chart_area.setHtml(html + html2)
            else:
                # 单策略：趋势、回撤、收益分布
                equity = results.get('equity_curve')
                drawdown = results.get('drawdown_curve')
                returns = results.get('returns_histogram')
                if equity is not None:
                    fig.add_trace(go.Scatter(y=equity, mode='lines',
                                  name='资金曲线', line=dict(color='blue')))
                if drawdown is not None:
                    fig.add_trace(go.Scatter(y=drawdown, mode='lines',
                                  name='回撤曲线', line=dict(color='red')))
                if returns is not None:
                    fig.add_trace(
                        go.Bar(y=returns, name='收益分布', marker_color='orange'))
                fig.update_layout(title='回测结果可视化', template='plotly_white')
                html = pio.to_html(fig, full_html=False,
                                   include_plotlyjs='cdn')
                self.trend_chart_area.setHtml(html)
            # 3. 新增详细结果弹窗按钮
            if not hasattr(self, 'detail_btn'):
                self.detail_btn = QPushButton('详细结果')
                self.layout().addWidget(self.detail_btn)
                self.detail_btn.clicked.connect(
                    lambda: self.show_detail_dialog(results))
        except Exception as e:
            if True:  # 使用Loguru日志
                logger.error(f"回测结果展示美化/多策略对比失败: {str(e)}")

    def show_detail_dialog(self, results: dict):
        """弹出详细结果对话框，整合所有分组表格和图表，主UI可并行操作"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton
        dialog = QDialog(self)
        dialog.setWindowTitle("回测详细结果")
        layout = QVBoxLayout(dialog)
        # 绩效
        perf = results.get('performance') or results.get('metrics') or {}
        perf_table = QTableWidget()
        perf_table.setColumnCount(2)
        perf_table.setHorizontalHeaderLabels(["绩效指标", "数值"])
        perf_items = list(perf.items())
        perf_table.setRowCount(len(perf_items))
        for i, (k, v) in enumerate(perf_items):
            perf_table.setItem(i, 0, QTableWidgetItem(str(k)))
            perf_table.setItem(i, 1, QTableWidgetItem(
                f"{v:.4f}" if isinstance(v, float) else str(v)))
        perf_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(QLabel("绩效指标："))
        layout.addWidget(perf_table)
        risk = results.get('risk', {})
        risk_table = QTableWidget()
        risk_table.setColumnCount(2)
        risk_table.setHorizontalHeaderLabels(["风险指标", "数值"])
        risk_items = list(risk.items())
        risk_table.setRowCount(len(risk_items))
        for i, (k, v) in enumerate(risk_items):
            risk_table.setItem(i, 0, QTableWidgetItem(str(k)))
            risk_table.setItem(i, 1, QTableWidgetItem(
                f"{v:.4f}" if isinstance(v, float) else str(v)))
        risk_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(QLabel("风险指标："))
        layout.addWidget(risk_table)
        trades = results.get('trades', [])
        if trades:
            trades_table = QTableWidget()
            trades_table.setColumnCount(len(trades[0]))
            trades_table.setHorizontalHeaderLabels(list(trades[0].keys()))
            trades_table.setRowCount(len(trades))
            for i, trade in enumerate(trades):
                for col, k in enumerate(trade.keys()):
                    trades_table.setItem(
                        i, col, QTableWidgetItem(str(trade[k])))
            trades_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            layout.addWidget(QLabel("交易明细："))
            layout.addWidget(trades_table)
        # 可视化图表
        equity = results.get('equity_curve')
        drawdown = results.get('drawdown_curve')
        returns = results.get('returns_histogram')
        fig = go.Figure()
        if equity is not None:
            fig.add_trace(go.Scatter(y=equity, mode='lines',
                          name='资金曲线', line=dict(color='blue')))
        if drawdown is not None:
            fig.add_trace(go.Scatter(y=drawdown, mode='lines',
                          name='回撤曲线', line=dict(color='red')))
        if returns is not None:
            fig.add_trace(
                go.Bar(y=returns, name='收益分布', marker_color='orange'))
        fig.update_layout(title='回测结果可视化', template='plotly_white')
        chart = QWebEngineView()
        html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
        chart.setHtml(html)
        layout.addWidget(QLabel("可视化图表："))
        layout.addWidget(chart)
        # 导出按钮
        export_btn = QPushButton('导出结果')
        layout.addWidget(export_btn)

        def export():
            from PyQt5.QtWidgets import QFileDialog
            file, _ = QFileDialog.getSaveFileName(
                dialog, "导出回测结果", "backtest_results.xlsx", "Excel Files (*.xlsx)")
            if file:
                with pd.ExcelWriter(file) as writer:
                    pd.DataFrame(perf.items(), columns=["绩效指标", "数值"]).to_excel(
                        writer, sheet_name="绩效", index=False)
                    pd.DataFrame(risk.items(), columns=["风险指标", "数值"]).to_excel(
                        writer, sheet_name="风险", index=False)
                    if trades:
                        pd.DataFrame(trades).to_excel(
                            writer, sheet_name="交易明细", index=False)
        export_btn.clicked.connect(export)
        dialog.setLayout(layout)
        dialog.resize(900, 700)
        dialog.exec_()

    def export_backtest_results(self):
        """一键导出全部回测结果（绩效、风险、交易、持仓、图表）"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出回测结果", "回测结果", "Excel Files (*.xlsx);;CSV Files (*.csv)")
            if not file_path:
                return
            # 导出绩效、风险、交易、持仓
            perf_data = [[self.performance_table.item(i, 0).text(), self.performance_table.item(i, 1).text()]
                         for i in range(self.performance_table.rowCount())]
            risk_data = [[self.risk_table.item(i, 0).text(), self.risk_table.item(
                i, 1).text()] for i in range(self.risk_table.rowCount())]
            trade_data = [[self.trade_table.item(i, j).text() for j in range(self.trade_table.columnCount())]
                          for i in range(self.trade_table.rowCount())]
            pos_data = [[self.position_table.item(i, j).text() for j in range(self.position_table.columnCount())]
                        for i in range(self.position_table.rowCount())]
            with pd.ExcelWriter(file_path) as writer:
                pd.DataFrame(perf_data, columns=["指标", "数值"]).to_excel(
                    writer, sheet_name="绩效指标", index=False)
                pd.DataFrame(risk_data, columns=["风险指标", "数值"]).to_excel(
                    writer, sheet_name="风险指标", index=False)
                pd.DataFrame(trade_data).to_excel(
                    writer, sheet_name="交易明细", index=False)
                pd.DataFrame(pos_data).to_excel(
                    writer, sheet_name="持仓明细", index=False)
            QMessageBox.information(self, "导出成功", "回测结果已导出")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出回测结果失败: {str(e)}")

    def clear_data(self):
        """清除数据"""
        try:
            self.signal_table.setRowCount(0)
            self.performance_table.setRowCount(0)
            self.risk_table.setRowCount(0)
            self.trade_table.setRowCount(0)
            self.position_table.setRowCount(0)

            self.current_signals = []
            self.current_positions = []

        except Exception as e:
            logger.error(f"清除数据失败: {str(e)}")

    def _run_analysis_async(self, button, analysis_func, *args, progress_callback=None, **kwargs):
        original_text = button.text()
        button.setText("取消")
        button._interrupted = False

        def on_cancel():
            button._interrupted = True
            button.setText(original_text)
            button.setEnabled(True)
            try:
                button.clicked.disconnect()
            except Exception:
                pass
            button.clicked.connect(lambda: self._run_analysis_async(
                button, analysis_func, *args, progress_callback=progress_callback, **kwargs))
        try:
            button.clicked.disconnect()
        except Exception:
            pass
        button.clicked.connect(on_cancel)

        def task():
            try:
                if not getattr(button, '_interrupted', False):
                    result = analysis_func(
                        *args, progress_callback=progress_callback, **kwargs)
                    return result
            except Exception as e:
                if True:  # 使用Loguru日志
                    logger.error(f"分析异常: {str(e)}")
                return None
            finally:
                QTimer.singleShot(0, lambda: on_done(None))

        def on_done(future):
            button.setText(original_text)
            button.setEnabled(True)
            try:
                button.clicked.disconnect()
            except Exception:
                pass
            button.clicked.connect(lambda: self._run_analysis_async(
                button, analysis_func, *args, progress_callback=progress_callback, **kwargs))
        import os
        from concurrent.futures import ThreadPoolExecutor
        if not hasattr(self, '_thread_pool'):
            self._thread_pool = ThreadPoolExecutor(os.cpu_count() * 2)
        future = self._thread_pool.submit(task)
        # 支持进度回调
        if progress_callback:
            progress_callback(0, 1)  # 单任务时直接回调100%

    def calculate_signals(self):
        self._run_analysis_async(self.signal_btn, self._calculate_signals_impl)

    def _calculate_signals_impl(self):
        """计算交易信号的实际实现"""
        try:
            strategy_name = self.strategy_combo.currentText()
            if not strategy_name or strategy_name == "自定义策略":
                QMessageBox.warning(self, "提示", "请选择一个有效的策略。")
                return None

            logger.info(f"开始计算信号，策略: {strategy_name}")

            # 使用交易服务计算信号
            if self._trading_service and hasattr(self._trading_service, 'calculate_signals'):
                signals = self._trading_service.calculate_signals(
                    stock_code=self.current_stock.strip(),
                    kdata=self._kdata_cache.get(self.current_stock.strip()) if hasattr(self, '_kdata_cache') else None,
                    strategy=strategy_name
                )
            else:
                signals = []

            if signals is None:
                logger.error(f"策略 {strategy_name} 未能生成信号。")
                return {"error": f"策略 {strategy_name} 未能生成信号。"}

            logger.info(f"成功计算 {len(signals)} 个信号")

            # 更新UI
            self.update_signals(signals)

            return {"signals": signals}
        except Exception as e:
            error_msg = f"计算信号时出错: {e}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}

    def run_backtest(self):
        self._run_analysis_async(self.backtest_btn, self._run_backtest_impl)

    def reset_params(self):
        """重置参数"""
        try:
            # 重置策略参数
            self.ma_short_spin.setValue(5)
            self.ma_long_spin.setValue(10)
            self.macd_short_spin.setValue(7)
            self.macd_long_spin.setValue(26)
            self.macd_signal_spin.setValue(9)
            self.kdj_n_spin.setValue(9)
            self.kdj_m1_spin.setValue(3)
            self.kdj_m2_spin.setValue(3)

            # 重置回测参数
            self.initial_cash_spin.setValue(100000.0)
            self.commission_spin.setValue(0.0003)
            self.slippage_spin.setValue(0.0001)

        except Exception as e:
            logger.info(f"重置参数失败: {str(e)}")

    def on_strategy_changed(self, strategy: str):
        """处理策略变更事件，仅切换参数区，不自动回测"""
        try:
            self.strategy_changed.emit(strategy)
            # 只刷新参数区，不自动回测
            self.update_parameters_visibility()
        except Exception as e:
            logger.error(f"处理策略变更失败: {str(e)}")

    def update_parameters_visibility(self):
        """根据当前选择的策略显示/隐藏对应的参数控件"""
        strategy_name = self.strategy_combo.currentText() if hasattr(self, 'strategy_combo') else ""

        if hasattr(self, 'ma_short_spin'):
            self.ma_short_spin.setVisible(strategy_name == "MA策略")
        if hasattr(self, 'ma_long_spin'):
            self.ma_long_spin.setVisible(strategy_name == "MA策略")

        if hasattr(self, 'macd_short_spin'):
            self.macd_short_spin.setVisible(strategy_name == "MACD策略")
        if hasattr(self, 'macd_long_spin'):
            self.macd_long_spin.setVisible(strategy_name == "MACD策略")
        if hasattr(self, 'macd_signal_spin'):
            self.macd_signal_spin.setVisible(strategy_name == "MACD策略")

        if hasattr(self, 'kdj_n_spin'):
            self.kdj_n_spin.setVisible(strategy_name == "KDJ策略")
        if hasattr(self, 'kdj_m1_spin'):
            self.kdj_m1_spin.setVisible(strategy_name == "KDJ策略")
        if hasattr(self, 'kdj_m2_spin'):
            self.kdj_m2_spin.setVisible(strategy_name == "KDJ策略")

    def refresh(self) -> None:
        """
        刷新交易控件内容，异常只记录日志不抛出。
        """
        try:
            self.clear_data()
            self.calculate_signals()
        except Exception as e:
            error_msg = f"刷新交易控件失败: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            # 发射异常信号，主窗口可捕获弹窗
            self.error_occurred.emit(error_msg)

    def update(self) -> None:
        """
        兼容旧接口，重定向到refresh。
        """
        self.refresh()

    def reload(self) -> None:
        """
        兼容旧接口，重定向到refresh。
        """
        self.refresh()

    def _run_backtest_impl(self):
        """统一回测实现，支持所有策略，参数标准化，结果自动刷新到UI"""
        try:
            if not self.current_stock or not isinstance(self.current_stock, str) or not self.current_stock.strip():
                logger.warning("请先选择股票")
                QMessageBox.warning(self, "回测错误", "未选择有效的股票代码，请先选择股票！")
                return
            strategy = self.strategy_combo.currentText()
            params = {}
            for k, v in self.param_controls.items():
                if isinstance(v, (QSpinBox, QDoubleSpinBox)):
                    params[k] = v.value()
                elif isinstance(v, QComboBox):
                    params[k] = v.currentText()
            params['strategy'] = strategy
            params['stock'] = self.current_stock.strip()
            params['start_date'] = getattr(self, 'start_date', None).date().strftime(
                '%Y-%m-%d') if hasattr(self, 'start_date') else ''
            params['end_date'] = getattr(self, 'end_date', None).date().strftime(
                '%Y-%m-%d') if hasattr(self, 'end_date') else ''
            params['initial_cash'] = self.initial_cash_spin.value() if hasattr(
                self, 'initial_cash_spin') and self.initial_cash_spin is not None else 100000.0
            params['commission_rate'] = self.commission_spin.value() if hasattr(
                self, 'commission_spin') and self.commission_spin is not None else 0.0003
            params['slippage'] = self.slippage_spin.value() if hasattr(
                self, 'slippage_spin') and self.slippage_spin is not None else 0.0001
            logger.info(f"开始回测 - 策略: {strategy}")

            # 使用统一回测引擎
            from backtest.unified_backtest_engine import UnifiedBacktestEngine, BacktestLevel

            # 获取股票数据并生成信号（TET模式优先）
            from core.containers import get_service_container
            from core.services import StockService, AssetService
            from core.plugin_types import AssetType

            # 通过服务容器获取服务
            service_container = get_service_container()
            kdata = None

            #  优先尝试AssetService（TET模式）
            try:
                asset_service = service_container.resolve(AssetService)
                if asset_service:
                    logger.info(f" TradingWidget使用TET模式获取数据: {self.current_stock.strip()}")
                    kdata = asset_service.get_historical_data(
                        symbol=self.current_stock.strip(),
                        asset_type=AssetType.STOCK_A,
                        period='D'
                    )
                    if kdata is not None and not kdata.empty:
                        logger.info(f" TET模式获取成功: {self.current_stock.strip()} | 记录数: {len(kdata)}")
                    else:
                        logger.warning(f" TET模式返回空数据: {self.current_stock.strip()}")
                        kdata = None
            except Exception as e:
                logger.warning(f" TET模式获取失败: {e}")
                kdata = None

            #  降级到StockService
            if kdata is None or (hasattr(kdata, 'empty') and kdata.empty):
                stock_service = service_container.get_service(StockService)
                if stock_service:
                    logger.info(f" 降级到StockService模式: {self.current_stock.strip()}")
                    kdata = stock_service.get_kdata(self.current_stock.strip())
                    if kdata is not None and not kdata.empty:
                        logger.info(f" StockService获取成功: {self.current_stock.strip()} | 记录数: {len(kdata)}")

            if kdata is None or kdata.empty:
                raise ValueError("无法获取股票数据 - 所有数据源都失败")

            signal_data = kdata.copy()
            signal_data['signal'] = 0

            if strategy == "均线策略":
                ma_short = signal_data['close'].rolling(window=5).mean()
                ma_long = signal_data['close'].rolling(window=20).mean()
                signal_data.loc[ma_short > ma_long, 'signal'] = 1
                signal_data.loc[ma_short < ma_long, 'signal'] = -1

            engine = UnifiedBacktestEngine(
                backtest_level=BacktestLevel.PROFESSIONAL)

            result = engine.run_backtest(
                data=signal_data,
                initial_capital=params['initial_cash'],
                position_size=0.9,
                commission_pct=params['commission_rate'],
                slippage_pct=params['slippage']
            )

            metrics = {
                'total_return': result.get('total_return', 0.0),
                'annual_return': result.get('annualized_return', 0.0),
                'max_drawdown': result.get('max_drawdown', 0.0),
                'sharpe_ratio': result.get('sharpe_ratio', 0.0),
                'volatility': result.get('volatility', 0.0),
                'win_rate': result.get('win_rate', 0.0),
                'profit_loss_ratio': result.get('profit_factor', 0.0),
                'final_capital': result.get('final_equity', params['initial_cash']),
                'total_trades': result.get('total_trades', 0)
            }

            self.update_backtest_results(metrics)
            logger.info("回测完成")
        except Exception as e:
            error_msg = f"回测失败: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.error_occurred.emit(error_msg)

    def on_analyze(self):
        """
        统一分析入口，唯一负责参数校验、日志、分析逻辑和UI刷新。所有分析入口（包括AnalysisToolsPanel、菜单栏、工具栏等）都应调用本方法，避免重复实现和分散校验。
        返回分析结果字典。
        """
        self.process_manager.reset()
        self.process_manager.add_step(AnalysisStep('param_check', '参数校验'))
        self.process_manager.add_step(AnalysisStep('data_load', '数据加载'))
        self.process_manager.add_step(AnalysisStep('signal_gen', '信号生成'))
        self.process_manager.add_step(AnalysisStep('performance', '绩效计算'))
        self.process_manager.add_step(AnalysisStep('result', '结果展示'))

        try:
            self.process_manager.start_step('param_check')
            if not self.current_stock or not isinstance(self.current_stock, str) or not self.current_stock.strip():
                self.process_manager.finish_step('param_check', success=False, error='未选择有效的股票代码')
                self.analysis_progress.emit(
                    {'step_id': 'param_check', 'status': 'failed', 'msg': '参数校验失败：未选择有效的股票代码'})
                return {'error': '未选择有效的股票代码'}
            self.process_manager.finish_step('param_check', success=True)
            self.analysis_progress.emit(
                {'step_id': 'param_check', 'status': 'success', 'msg': f'参数校验通过: {self.current_stock.strip()}'})

            self.process_manager.start_step('data_load')
            kdata = None
            from core.containers import get_service_container
            from core.services import StockService, AssetService
            from core.plugin_types import AssetType
            service_container = get_service_container()
            try:
                asset_service = service_container.resolve(AssetService)
                if asset_service:
                    kdata = asset_service.get_historical_data(
                        symbol=self.current_stock.strip(), asset_type=AssetType.STOCK_A, period='D')
            except Exception:
                pass
            if kdata is None or (hasattr(kdata, 'empty') and kdata.empty):
                stock_service = service_container.get_service(StockService)
                if stock_service:
                    kdata = stock_service.get_kdata(self.current_stock.strip())
            if kdata is None or kdata.empty:
                self.process_manager.finish_step('data_load', success=False, error='无法获取股票数据')
                self.analysis_progress.emit(
                    {'step_id': 'data_load', 'status': 'failed', 'msg': '数据加载失败'})
                return {'error': '无法获取股票数据'}
            self.process_manager.finish_step('data_load', success=True)
            self.analysis_progress.emit(
                {'step_id': 'data_load', 'status': 'success', 'msg': f'数据加载完成: {len(kdata)} 条'})

            self.process_manager.start_step('signal_gen')
            try:
                signals_result = self._calculate_signals_impl()
                if signals_result and signals_result.get('error'):
                    self.process_manager.finish_step('signal_gen', success=False, error=signals_result['error'])
                    self.analysis_progress.emit(
                        {'step_id': 'signal_gen', 'status': 'failed', 'msg': signals_result['error']})
                    return {'error': signals_result['error']}
                self.process_manager.finish_step('signal_gen', success=True)
                self.analysis_progress.emit(
                    {'step_id': 'signal_gen', 'status': 'success', 'msg': '信号生成完成'})
            except Exception as e:
                self.process_manager.finish_step('signal_gen', success=False, error=str(e))
                self.analysis_progress.emit(
                    {'step_id': 'signal_gen', 'status': 'failed', 'msg': f'信号生成失败: {e}'})
                return {'error': str(e)}

            self.process_manager.start_step('performance')
            try:
                self._run_backtest_impl()
                self.process_manager.finish_step('performance', success=True)
                self.analysis_progress.emit(
                    {'step_id': 'performance', 'status': 'success', 'msg': '绩效计算完成'})
            except Exception as e:
                self.process_manager.finish_step('performance', success=False, error=str(e))
                self.analysis_progress.emit(
                    {'step_id': 'performance', 'status': 'failed', 'msg': f'绩效计算失败: {e}'})
                return {'error': str(e)}

            self.process_manager.start_step('result')
            self.process_manager.finish_step('result', success=True)
            self.analysis_progress.emit(
                {'step_id': 'result', 'status': 'success', 'msg': '结果展示完成'})
            return {'status': 'completed'}

        except Exception as e:
            logger.error(f"分析流程异常: {e}")
            self.analysis_progress.emit(
                {'step_id': 'result', 'status': 'failed', 'msg': f'分析失败: {e}'})
            return {'error': str(e)}

    def set_parameters(self, params: Dict[str, Any]):
        """
        外部设置参数控件的值，实现参数同步。
        Args:
            params: 参数字典 {控件名: 值}
        """
        for name, value in params.items():
            control = self.param_controls.get(name)
            if control is not None:
                if hasattr(control, 'setValue'):
                    try:
                        control.setValue(value)
                    except Exception:
                        pass
                elif hasattr(control, 'setText'):
                    try:
                        control.setText(str(value))
                    except Exception:
                        pass

    def set_status_message(self, message: str, error: bool = False):
        """
        兼容BaseAnalysisPanel的状态信息显示方法。
        Args:
            message: 状态信息
            error: 是否为错误信息
        """
        # 这里只做日志记录，或可扩展为UI提示
        if True:  # 使用Loguru日志
            if error:
                logger.error(message)
            else:
                logger.info(message)
        # 可扩展为弹窗或状态栏提示

    def _execute_analysis(self, strategy: str, params: dict) -> dict:
        """优化分析逻辑，提升性能和健壮性，标准化结果结构。"""
        import numpy as np
        results = {'strategy': strategy, 'signals': None,
                   'indicators': {}, 'metrics': {}, 'error': None}
        try:
            # 参数类型和范围校验
            def safe_int(val, default, minv=None, maxv=None):
                try:
                    v = int(val)
                    if minv is not None:
                        v = max(v, minv)
                    if maxv is not None:
                        v = min(v, maxv)
                    return v
                except Exception:
                    return default

            def safe_float(val, default, minv=None, maxv=None):
                try:
                    v = float(val)
                    if minv is not None:
                        v = max(v, minv)
                    if maxv is not None:
                        v = min(v, maxv)
                    return v
                except Exception:
                    return default
            # K线数据缓存（按股票+周期）
            stock = params.get('stock')
            if isinstance(stock, dict):
                stock_code = stock.get('code') or stock.get(
                    'stock') or next(iter(stock.values()), None)
            else:
                stock_code = stock
            if not isinstance(stock_code, str):
                results['error'] = "股票代码无效，无法分析"
                self.set_status_message(results['error'], error=True)
                return results
            params['stock'] = stock_code  # 保证后续都是字符串
            logger.info(f"准备回测股票:{stock_code}")
            cache_key = f"{stock_code}_{params.get('period','D')}"
            if not hasattr(self, '_kdata_cache'):
                self._kdata_cache = {}
            data = self._kdata_cache.get(cache_key)
            if data is None or data.empty:
                # 通过服务容器获取股票数据（TET模式优先）
                from core.services import AssetService
                from core.plugin_types import AssetType

                service_container = get_service_container()

                #  优先尝试AssetService（TET模式）
                try:
                    asset_service = service_container.resolve(AssetService)
                    if asset_service:
                        data = asset_service.get_historical_data(
                            symbol=stock_code,
                            asset_type=AssetType.STOCK_A,
                            period='D'
                        )
                        if data is not None and not data.empty:
                            self._kdata_cache[cache_key] = data
                            logger.info(f" 分析缓存TET模式: {stock_code} | 记录数: {len(data)}")
                except Exception as e:
                    logger.warning(f" 分析TET模式失败: {e}")
                    data = None

                #  降级到StockService
                if data is None or (hasattr(data, 'empty') and data.empty):
                    stock_service = service_container.get_service(StockService)
                    if stock_service:
                        data = stock_service.get_kdata(stock_code)
                        if data is not None and not data.empty:
                            self._kdata_cache[cache_key] = data
                            logger.info(f" 分析缓存StockService: {stock_code} | 记录数: {len(data)}")
            if data is None or data.empty:
                results['error'] = f"{stock_code}股票K线数据为空，无法分析"
                self.set_status_message(results['error'], error=True)
                return results
            # --- 均线策略 ---
            if strategy == "均线策略":
                fast = safe_int(params.get('快线周期', 5), 5, 1, 120)
                slow = safe_int(params.get('慢线周期', 20), 20, 5, 250)
                ma_short = data['close'].rolling(window=fast).mean()
                ma_long = data['close'].rolling(window=slow).mean()
                signals = pd.Series(0, index=data.index)
                signals[ma_short > ma_long] = 1
                signals[ma_short < ma_long] = -1
                results['signals'] = signals
                results['indicators'] = {
                    'MA_short': ma_short, 'MA_long': ma_long}
            # --- MACD策略 ---
            elif strategy == "MACD策略":
                fast = safe_int(params.get('快线周期', 12), 12, 5, 50)
                slow = safe_int(params.get('慢线周期', 26), 26, 10, 100)
                signal_p = safe_int(params.get('信号周期', 9), 9, 2, 20)
                exp1 = data['close'].ewm(span=fast, adjust=False).mean()
                exp2 = data['close'].ewm(span=slow, adjust=False).mean()
                macd = exp1 - exp2
                signal = macd.ewm(span=signal_p, adjust=False).mean()
                signals = pd.Series(0, index=data.index)
                signals[macd > signal] = 1
                signals[macd < signal] = -1
                results['signals'] = signals
                results['indicators'] = {'MACD': macd, 'Signal': signal}
            # --- RSI策略 ---
            elif strategy == "RSI策略":
                period = safe_int(params.get('周期', 14), 14, 5, 30)
                overbought = safe_float(params.get('超买阈值', 70), 70, 50, 90)
                oversold = safe_float(params.get('超卖阈值', 30), 30, 10, 50)
                delta = data['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(
                    window=period).mean()
                loss = (-delta.where(delta < 0, 0)
                        ).rolling(window=period).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                signals = pd.Series(0, index=data.index)
                signals[rsi < oversold] = 1
                signals[rsi > overbought] = -1
                results['signals'] = signals
                results['indicators'] = {'RSI': rsi}
            # --- 布林带策略 ---
            elif strategy == "布林带策略":
                period = safe_int(params.get('周期', 20), 20, 5, 60)
                stdv = safe_float(params.get('标准差倍数', 2), 2, 1, 3)
                ma = data['close'].rolling(window=period).mean()
                std = data['close'].rolling(window=period).std()
                upper = ma + stdv * std
                lower = ma - stdv * std
                signals = pd.Series(0, index=data.index)
                signals[data['close'] < lower] = 1
                signals[data['close'] > upper] = -1
                results['signals'] = signals
                results['indicators'] = {
                    'MA': ma, 'Upper': upper, 'Lower': lower}
            # --- KDJ策略 ---
            elif strategy == "KDJ策略":
                period = safe_int(params.get('周期', 9), 9, 5, 30)
                kf = safe_float(params.get('K平滑', 2), 2, 0.1, 1.0)
                df = safe_float(params.get('D平滑', 2), 2, 0.1, 1.0)
                low_min = data['low'].rolling(window=period).min()
                high_max = data['high'].rolling(window=period).max()
                rsv = (data['close'] - low_min) / (high_max - low_min) * 100
                k = rsv.ewm(com=kf).mean()
                d = k.ewm(com=df).mean()
                j = 3 * k - 2 * d
                signals = pd.Series(0, index=data.index)
                signals[k < 20] = 1
                signals[k > 80] = -1
                results['signals'] = signals
                results['indicators'] = {'K': k, 'D': d, 'J': j}
            # --- 形态分析 ---
            elif strategy == "形态分析":
                from analysis.pattern_recognition import PatternRecognizer
                recognizer = PatternRecognizer()
                kdata_for_pattern = data
                if isinstance(data, pd.DataFrame) and 'code' not in data.columns:
                    code = stock_code
                    if code:
                        kdata_for_pattern = data.copy()
                        kdata_for_pattern['code'] = code
                pattern_signals = recognizer.get_pattern_signals(
                    kdata_for_pattern)
                results['signals'] = pattern_signals
                results['indicators'] = {}
            # --- DX策略 ---
            elif strategy == "DX策略":
                period = safe_int(params.get('周期', 14), 14, 5, 30)
                threshold = safe_float(params.get('ADX阈值', 25), 25, 10, 50)
                high = data['high']
                low = data['low']
                close = data['close']
                tr1 = high - low
                tr2 = abs(high - close.shift(1))
                tr3 = abs(low - close.shift(1))
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                atr = tr.rolling(window=period).mean()
                up_move = high - high.shift(1)
                down_move = low.shift(1) - low
                plus_dm = np.where((up_move > down_move) &
                                   (up_move > 0), up_move, 0)
                minus_dm = np.where((down_move > up_move) &
                                    (down_move > 0), down_move, 0)
                plus_di = 100 * \
                    pd.Series(plus_dm).ewm(alpha=1/period,
                                           adjust=False).mean() / atr
                minus_di = 100 * \
                    pd.Series(minus_dm).ewm(
                        alpha=1/period, adjust=False).mean() / atr
                dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
                adx = pd.Series(dx).ewm(alpha=1/period, adjust=False).mean()
                signals = pd.Series(0, index=data.index)
                signals[(adx > threshold) & (plus_di > minus_di)] = 1
                signals[(adx > threshold) & (plus_di < minus_di)] = -1
                results['signals'] = signals
                results['indicators'] = {
                    'ADX': adx, 'DX': dx, '+DI': plus_di, '-DI': minus_di}
            else:
                results['error'] = "请选择策略"
                self.set_status_message(results['error'], error=True)
            return results
        except Exception as e:
            results['error'] = f"分析逻辑异常: {str(e)}"
            self.set_status_message(results['error'], error=True)
            return results

    def export_batch_results(self, results, filename=None):
        """
        导出批量分析/回测结果为Excel/CSV，结构化包含所有参数、绩效、风险、分组等信息。
        Args:
            results: 批量分析结果列表
            filename: 导出文件名（可选）
        """
        if not results:
            return
        df = pd.DataFrame([{
            **r.get('params', {}),
            'code': r.get('code'),
            'strategy': r.get('strategy'),
            **(r.get('result', {}).get('performance', {})),
            **(r.get('result', {}).get('risk', {})),
            'error': r.get('error', '')
        } for r in results])
        if not filename:
            filename = 'batch_results.xlsx'
        if filename.endswith('.csv'):
            df.to_csv(filename, index=False)
        else:
            df.to_excel(filename, index=False)

    def plot_batch_results(self, results, group_by='strategy', metric='annual_return'):
        """
        批量结果区自动生成分组对比图（柱状图、热力图、折线图），支持多策略/多参数/多股票横向对比。
        Args:
            results: 批量分析结果列表
            group_by: 分组字段
            metric: 绩效指标字段
        """
        import matplotlib.pyplot as plt
        if not results:
            return
        df = pd.DataFrame([{
            **r.get('params', {}),
            'code': r.get('code'),
            'strategy': r.get('strategy'),
            **(r.get('result', {}).get('performance', {})),
            **(r.get('result', {}).get('risk', {})),
            'error': r.get('error', '')
        } for r in results])
        if group_by in df.columns and metric in df.columns:
            grouped = df.groupby(group_by)[
                metric].mean().sort_values(ascending=False)
            grouped.plot(kind='bar', title=f'{metric} by {group_by}')
            plt.ylabel(metric)
            plt.tight_layout()
            plt.show()

    def run_batch_analysis(self, stock_list, strategy_list, param_grid, progress_callback=None, distributed_backend=None, remote_nodes=None):
        """
        批量分析/回测，支持本地/分布式执行。distributed_backend可选'dask'/'celery'/'ray'，remote_nodes为远程节点列表。
        Args:
            stock_list: 股票代码列表
            strategy_list: 策略名称列表
            param_grid: 参数组合列表（每个为dict）
            progress_callback: 进度回调函数，参数(已完成数, 总数)
            distributed_backend: 分布式后端（可选'dask'/'celery'/'ray'）
            remote_nodes: 远程节点地址列表（可选）
        Returns:
            results: 所有分析结果列表
        """
        results = []
        total = len(stock_list) * len(strategy_list) * len(param_grid)
        if distributed_backend == 'dask':
            try:
                from dask.distributed import Client
                client = Client(remote_nodes[0] if remote_nodes else None)
                import dask.dataframe as dd
                import dask

                def single_task(code, strategy, params):
                    # 使用服务容器获取交易服务
                    from core.containers import get_service_container
                    from core.services.trading_service import TradingService
                    service_container = get_service_container()
                    ts = service_container.resolve(TradingService)
                    if not ts:
                        return {'code': code, 'strategy': strategy, 'params': params, 'error': '交易服务不可用'}
                    if ts and hasattr(ts, 'set_current_stock'):
                        ts.set_current_stock(code)
                    if ts and hasattr(ts, 'get_kdata'):
                        kdata = ts.get_kdata(code)
                    p = dict(params)
                    p['strategy'] = strategy
                    # 使用直接调用 UnifiedBacktestEngine 的方式（替代不存在的 ts.run_backtest）
                    try:
                        from backtest.unified_backtest_engine import UnifiedBacktestEngine, BacktestLevel
                        if kdata is not None and not kdata.empty:
                            signal_data = kdata.copy()
                            signal_data['signal'] = 0
                            engine = UnifiedBacktestEngine(backtest_level=BacktestLevel.PROFESSIONAL)
                            result = engine.run_backtest(
                                data=signal_data,
                                initial_capital=p.get('initial_cash', 100000),
                                commission_pct=p.get('commission_rate', 0.001),
                                slippage_pct=p.get('slippage', 0.001)
                            )
                            res = result.to_dict() if hasattr(result, 'to_dict') else result
                        else:
                            res = {'error': '无法获取股票数据'}
                    except Exception as e:
                        res = {'error': f'回测执行失败: {str(e)}'}
                    return {'code': code, 'strategy': strategy, 'params': p, 'result': res}
                tasks = [dask.delayed(single_task)(code, strategy, params)
                         for code in stock_list for strategy in strategy_list for params in param_grid]
                futures = dask.persist(*tasks)
                results = client.gather(futures)
                if progress_callback:
                    progress_callback(total, total)
                return results
            except Exception as e:
                if progress_callback:
                    progress_callback(0, total)
                return [{'error': f'dask分布式执行失败: {str(e)}'}]
        elif distributed_backend == 'ray':
            try:
                import ray
                if not ray.is_initialized():
                    ray.init(address=remote_nodes[0] if remote_nodes else None)

                @ray.remote
                def single_task(code, strategy, params):
                    # 使用服务容器获取交易服务
                    from core.containers import get_service_container
                    from core.services.trading_service import TradingService
                    service_container = get_service_container()
                    ts = service_container.resolve(TradingService)
                    if not ts:
                        return {'code': code, 'strategy': strategy, 'params': params, 'error': '交易服务不可用'}
                    if ts and hasattr(ts, 'set_current_stock'):
                        ts.set_current_stock(code)
                    if ts and hasattr(ts, 'get_kdata'):
                        kdata = ts.get_kdata(code)
                    p = dict(params)
                    p['strategy'] = strategy
                    # 使用直接调用 UnifiedBacktestEngine 的方式
                    try:
                        from backtest.unified_backtest_engine import UnifiedBacktestEngine, BacktestLevel
                        if kdata is not None and not kdata.empty:
                            signal_data = kdata.copy()
                            signal_data['signal'] = 0
                            engine = UnifiedBacktestEngine(backtest_level=BacktestLevel.PROFESSIONAL)
                            result = engine.run_backtest(
                                data=signal_data,
                                initial_capital=p.get('initial_cash', 100000),
                                commission_pct=p.get('commission_rate', 0.001),
                                slippage_pct=p.get('slippage', 0.001)
                            )
                            res = result.to_dict() if hasattr(result, 'to_dict') else result
                        else:
                            res = {'error': '无法获取股票数据'}
                    except Exception as e:
                        res = {'error': f'回测执行失败: {str(e)}'}
                    return {'code': code, 'strategy': strategy, 'params': p, 'result': res}
                tasks = [single_task.remote(
                    code, strategy, params) for code in stock_list for strategy in strategy_list for params in param_grid]
                results = ray.get(tasks)
                if progress_callback:
                    progress_callback(total, total)
                return results
            except Exception as e:
                if progress_callback:
                    progress_callback(0, total)
                return [{'error': f'ray分布式执行失败: {str(e)}'}]
        elif distributed_backend == 'celery':
            try:
                from celery import group
                # 需预先配置celery worker和broker

                def single_task(code, strategy, params):
                    # 使用服务容器获取交易服务
                    from core.containers import get_service_container
                    from core.services.trading_service import TradingService
                    service_container = get_service_container()
                    ts = service_container.resolve(TradingService)
                    if not ts:
                        return {'code': code, 'strategy': strategy, 'params': params, 'error': '交易服务不可用'}
                    if ts and hasattr(ts, 'set_current_stock'):
                        ts.set_current_stock(code)
                    if ts and hasattr(ts, 'get_kdata'):
                        kdata = ts.get_kdata(code)
                    p = dict(params)
                    p['strategy'] = strategy
                    # 使用直接调用 UnifiedBacktestEngine 的方式
                    try:
                        from backtest.unified_backtest_engine import UnifiedBacktestEngine, BacktestLevel
                        if kdata is not None and not kdata.empty:
                            signal_data = kdata.copy()
                            signal_data['signal'] = 0
                            engine = UnifiedBacktestEngine(backtest_level=BacktestLevel.PROFESSIONAL)
                            result = engine.run_backtest(
                                data=signal_data,
                                initial_capital=p.get('initial_cash', 100000),
                                commission_pct=p.get('commission_rate', 0.001),
                                slippage_pct=p.get('slippage', 0.001)
                            )
                            res = result.to_dict() if hasattr(result, 'to_dict') else result
                        else:
                            res = {'error': '无法获取股票数据'}
                    except Exception as e:
                        res = {'error': f'回测执行失败: {str(e)}'}
                    return {'code': code, 'strategy': strategy, 'params': p, 'result': res}
                tasks = [group(single_task.s(code, strategy, params)
                               for code in stock_list for strategy in strategy_list for params in param_grid)]
                results = tasks.apply_async().get()
                if progress_callback:
                    progress_callback(total, total)
                return results
            except Exception as e:
                if progress_callback:
                    progress_callback(0, total)
                return [{'error': f'celery分布式执行失败: {str(e)}'}]
        else:
            # 本地多线程
            def worker():
                done = 0
                for code in stock_list:
                    for strategy in strategy_list:
                        for params in param_grid:
                            try:
                                # 使用服务容器获取交易服务
                                from core.containers import get_service_container
                                from core.services.trading_service import TradingService
                                service_container = get_service_container()
                                ts = service_container.resolve(TradingService)
                                if not ts:
                                    results.append({'code': code, 'strategy': strategy, 'params': params, 'error': '交易服务不可用'})
                                    done += 1
                                    if progress_callback:
                                        progress_callback(done, total)
                                    continue

                                if ts and hasattr(ts, 'set_current_stock'):
                                    ts.set_current_stock(code)
                                if ts and hasattr(ts, 'get_kdata'):
                                    kdata = ts.get_kdata(code)
                                p = dict(params)
                                p['strategy'] = strategy
                                # 使用直接调用 UnifiedBacktestEngine 的方式
                                try:
                                    from backtest.unified_backtest_engine import UnifiedBacktestEngine, BacktestLevel
                                    if kdata is not None and not kdata.empty:
                                        signal_data = kdata.copy()
                                        signal_data['signal'] = 0
                                        engine = UnifiedBacktestEngine(backtest_level=BacktestLevel.PROFESSIONAL)
                                        result = engine.run_backtest(
                                            data=signal_data,
                                            initial_capital=p.get('initial_cash', 100000),
                                            commission_pct=p.get('commission_rate', 0.001),
                                            slippage_pct=p.get('slippage', 0.001)
                                        )
                                        res = result.to_dict() if hasattr(result, 'to_dict') else result
                                    else:
                                        res = {'error': '无法获取股票数据'}
                                except Exception as e:
                                    res = {'error': f'回测执行失败: {str(e)}'}
                                results.append(
                                    {'code': code, 'strategy': strategy, 'params': p, 'result': res})
                            except Exception as e:
                                results.append(
                                    {'code': code, 'strategy': strategy, 'params': params, 'error': str(e)})
                            done += 1
                            if progress_callback:
                                progress_callback(done, total)
            threading.Thread(target=worker, daemon=True).start()
            return results

    def register_custom_indicator(self, name: str, func):
        """
        注册自定义指标，插件化扩展。
        Args:
            name: 指标名称
            func: 计算函数
        """
        from gui.ui_components import BaseAnalysisPanel
        BaseAnalysisPanel.register_custom_indicator(name, func)

    def update_results(self, results: dict):
        """
        统一展示分析/回测结果，兼容分组、表格和图表展示。
        Args:
            results: 分析或回测结果字典
        """
        # 1. 分组展示绩效/风险/交易指标（如有results_area可扩展）
        perf = results.get('metrics') or results.get('performance') or {}
        risk = results.get('risk', {})
        trade = results.get('trade', {})
        # 可选：如有results_area文本区可展示详细分组信息
        if hasattr(self, 'results_area') and self.results_area:
            self.results_area.clear()

            def show_group(title, data):
                if data:
                    lines = [f"<b>{title}：</b>"]
                    lines.extend(
                        f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}"
                        for k, v in data.items()
                    )
                    text = "<br>".join(lines) + "<br>"
                    self.results_area.append(text)
            show_group("收益类指标", perf)
            show_group("风险类指标", risk)
            show_group("交易类指标", trade)
            if 'signals' in results:
                self.results_area.append(
                    "<b>信号明细：</b><br>" + str(results['signals']))
            if 'analysis' in results:
                self.results_area.append(
                    "<b>分析结果：</b><br>" + str(results['analysis']))
        # 2. 自动填充表格（兼容原有update_backtest_results）
        if hasattr(self, 'update_backtest_results'):
            self.update_backtest_results(results)
        # 3. 可选：驱动图表联动（如有chart_widget）
        parent = self.parent()
        chart_widget = getattr(parent, 'chart_widget', None)
        if chart_widget:
            if 'equity_curve' in results:
                chart_widget.update_chart(
                    {'equity_curve': results['equity_curve']})
            if 'drawdown_curve' in results:
                chart_widget.update_chart(
                    {'drawdown_curve': results['drawdown_curve']})
            if 'returns_histogram' in results:
                chart_widget.update_chart(
                    {'returns_histogram': results['returns_histogram']})
            if 'signals' in results:
                chart_widget.plot_signals(results['signals'])
            if 'pattern_signals' in results:
                chart_widget.plot_patterns(results['pattern_signals'])
        # 4. 分组对比（如有group_results）
        group_results = results.get('group_results', None)
        if group_results and hasattr(self, 'results_area') and self.results_area:
            self.results_area.append("<b>分组对比：</b><br>")
            for group, group_metric in group_results.items():
                self.results_area.append(f"<u>{group}</u>:<br>")
                for k, v in group_metric.items():
                    if isinstance(v, float):
                        self.results_area.append(f"{k}: {v:.4f}")
                    else:
                        self.results_area.append(f"{k}: {v}")
            if chart_widget and hasattr(chart_widget, 'plot_group_comparison'):
                chart_widget.plot_group_comparison(group_results)

    # 交易功能辅助方法
    def _get_current_price(self) -> Optional[float]:
        """获取当前股票价格"""
        try:
            if not self.current_stock:
                return None

            #  尝试从AssetService获取实时/历史价格（TET模式优先）
            try:
                from core.containers import get_service_container
                from core.services import AssetService
                from core.plugin_types import AssetType

                service_container = get_service_container()
                asset_service = service_container.resolve(AssetService)

                if asset_service:
                    # 首先尝试获取实时数据
                    try:
                        realtime_data = asset_service.get_real_time_data(
                            symbols=[self.current_stock],
                            asset_type=AssetType.STOCK_A
                        )
                        if realtime_data and self.current_stock in realtime_data:
                            quote = realtime_data[self.current_stock]
                            if quote and 'price' in quote:
                                return float(quote['price'])
                    except Exception:
                        pass  # 实时数据失败，继续尝试历史数据

                    # 如果没有实时数据，使用最新的K线数据
                    kdata = asset_service.get_historical_data(
                        symbol=self.current_stock,
                        asset_type=AssetType.STOCK_A,
                        period='D'
                    )
                    if kdata is not None and len(kdata) > 0:
                        if hasattr(kdata, 'iloc'):  # DataFrame
                            return float(kdata.iloc[-1]['close'])
                        else:  # KData
                            return float(kdata[-1].close)
            except Exception as e:
                logger.warning(f" TET模式获取当前价格失败: {e}")

            #  降级到传统data_manager
            try:
                from core.services.unified_data_manager import get_unified_data_manager
                data_manager = get_unified_data_manager()
                uni_plugin = data_manager.get_uni_plugin_manager()
                if uni_plugin:
                    realtime_result = uni_plugin.get_real_time_data(
                        symbols=[self.current_stock],
                        asset_type=AssetType.STOCK_A
                    )
                    if realtime_result is not None and not realtime_result.empty:
                        row = realtime_result.iloc[-1] if hasattr(realtime_result, 'iloc') else realtime_result
                        return float(row.get('price', row.get('current_price', 0)))

                # 如果没有实时数据，使用最新的K线数据
                kdata = data_manager.get_kdata(self.current_stock, period='D')
                if kdata is not None and len(kdata) > 0:
                    if hasattr(kdata, 'iloc'):  # DataFrame
                        return float(kdata.iloc[-1]['close'])
                    else:  # KData
                        return float(kdata[-1].close)
            except Exception as e:
                logger.error(f" 传统模式获取当前价格失败: {e}")

            return None

        except Exception as e:
            logger.error(f"获取当前价格失败: {str(e)}")
            return None

    def _get_position(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取指定股票的持仓信息"""
        try:
            for position in self.current_positions:
                if position['stock_code'] == stock_code:
                    return position
            return None

        except Exception as e:
            logger.error(f"获取持仓信息失败: {str(e)}")
            return None

    def _update_position(self, trade_record: Dict[str, Any]):
        """更新持仓信息"""
        try:
            stock_code = trade_record['stock_code']
            trade_type = trade_record['type']
            quantity = trade_record['quantity']
            price = trade_record['price']

            # 查找现有持仓
            position = self._get_position(stock_code)

            if trade_type == 'BUY':
                if position:
                    # 更新持仓
                    total_cost = position['cost'] * \
                        position['quantity'] + price * quantity
                    total_quantity = position['quantity'] + quantity
                    position['cost'] = total_cost / total_quantity
                    position['quantity'] = total_quantity
                else:
                    # 新增持仓
                    self.current_positions.append({
                        'stock_code': stock_code,
                        'stock_name': stock_code,  # 简化处理
                        'quantity': quantity,
                        'cost': price,
                        'current_price': price
                    })

            elif trade_type == 'SELL':
                if position:
                    position['quantity'] -= quantity
                    if position['quantity'] <= 0:
                        # 清仓
                        self.current_positions.remove(position)

            # 更新持仓表格显示
            self._update_position_table()

        except Exception as e:
            logger.error(f"更新持仓信息失败: {str(e)}")

    def _record_trade(self, trade_record: Dict[str, Any]):
        """记录交易记录"""
        try:
            row = self.trade_table.rowCount()
            self.trade_table.setRowCount(row + 1)

            self.trade_table.setItem(row, 0, QTableWidgetItem(
                trade_record['time'].strftime('%Y-%m-%d %H:%M:%S')
            ))
            self.trade_table.setItem(
                row, 1, QTableWidgetItem(trade_record['stock_code']))
            self.trade_table.setItem(
                row, 2, QTableWidgetItem(trade_record['type']))
            self.trade_table.setItem(row, 3, QTableWidgetItem(
                f"{trade_record['price']:.2f}"))
            self.trade_table.setItem(
                row, 4, QTableWidgetItem(str(trade_record['quantity'])))
            self.trade_table.setItem(row, 5, QTableWidgetItem(
                f"{trade_record['amount']:.2f}"))
            self.trade_table.setItem(
                row, 6, QTableWidgetItem(f"{trade_record['fee']:.2f}"))

            self.trade_table.resizeColumnsToContents()

        except Exception as e:
            logger.error(f"记录交易失败: {str(e)}")

    def _update_position_table(self):
        """更新持仓表格显示"""
        try:
            self.position_table.setRowCount(len(self.current_positions))

            for i, position in enumerate(self.current_positions):
                current_price = self._get_current_price(
                ) if position['stock_code'] == self.current_stock else position['current_price']
                if current_price:
                    position['current_price'] = current_price

                profit_loss = (
                    current_price - position['cost']) / position['cost'] * 100 if position['cost'] > 0 else 0

                self.position_table.setItem(
                    i, 0, QTableWidgetItem(position['stock_code']))
                self.position_table.setItem(
                    i, 1, QTableWidgetItem(position['stock_name']))
                self.position_table.setItem(
                    i, 2, QTableWidgetItem(str(position['quantity'])))
                self.position_table.setItem(
                    i, 3, QTableWidgetItem(f"{position['cost']:.2f}"))
                self.position_table.setItem(
                    i, 4, QTableWidgetItem(f"{current_price:.2f}"))

                profit_item = QTableWidgetItem(f"{profit_loss:.2f}%")
                if profit_loss > 0:
                    profit_item.setForeground(QColor('red'))
                elif profit_loss < 0:
                    profit_item.setForeground(QColor('green'))
                self.position_table.setItem(i, 5, profit_item)

            self.position_table.resizeColumnsToContents()

        except Exception as e:
            logger.error(f"更新持仓表格失败: {str(e)}")

    def _get_pending_orders(self) -> List[Dict[str, Any]]:
        try:
            if self._trading_service:
                active_orders = self._trading_service.get_active_orders()
                return [
                    {
                        'id': o.order_id,
                        'stock_code': o.symbol,
                        'type': o.side.value.upper(),
                        'price': float(o.price) if o.price else 0.0,
                        'quantity': o.quantity,
                        'status': o.status.value.upper()
                    }
                    for o in active_orders
                ]
            return []

        except Exception as e:
            logger.error(f"获取待处理订单失败: {str(e)}")
            return []

    def _cancel_order(self, order_id: str):
        try:
            if self._trading_service:
                success, message = self._trading_service.cancel_order(order_id)
                if success:
                    logger.info(f"订单已撤销: {order_id}")
                else:
                    logger.warning(f"撤销订单失败: {order_id}, 原因: {message}")
                    raise RuntimeError(f"撤销订单失败: {message}")
            else:
                logger.warning(f"TradingService 不可用，无法撤销订单: {order_id}")
                raise RuntimeError("TradingService 不可用")

        except Exception as e:
            logger.error(f"撤销订单失败: {str(e)}")
            raise
