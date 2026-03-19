"""
统一交易服务 - 架构精简重构版本

整合所有交易管理器功能，提供统一的交易执行和风险控制接口。
整合TradingManager、RiskManager、PositionManager、PortfolioManager等。
完全重构以符合15个核心服务的架构精简目标。
"""

import asyncio
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
from collections import defaultdict, deque

from loguru import logger

from .base_service import BaseService
from ..events import EventBus, get_event_bus, TradeExecutedEvent, PositionUpdatedEvent
from ..containers import ServiceContainer, get_service_container



try:
    from ..trading.trading_mode import TradingMode, ModeContext, ModeAwareMixin
except (ImportError, ValueError):
    from core.trading.trading_mode import TradingMode, ModeContext, ModeAwareMixin

class OrderType(Enum):
    """订单类型"""
    MARKET = "market"  # 市价单
    LIMIT = "limit"    # 限价单
    STOP = "stop"      # 止损单


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"      # 待成交
    FILLED = "filled"        # 已成交
    CANCELLED = "cancelled"  # 已取消
    REJECTED = "rejected"    # 已拒绝


class PositionType(Enum):
    """持仓类型"""
    LONG = "long"    # 多头
    SHORT = "short"  # 空头


@dataclass
class TradeRecord:
    """交易记录"""
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    stock_name: str = ""
    action: str = ""  # 'buy' or 'sell'
    quantity: int = 0
    price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "pending"  # 'pending', 'executed', 'failed'
    order_id: Optional[str] = None
    commission: float = 0.0
    total_amount: float = 0.0

    def __post_init__(self):
        """计算总金额"""
        if self.total_amount == 0.0:
            self.total_amount = self.quantity * self.price + self.commission


@dataclass
class TradingOrder:
    """交易订单"""
    order_id: str
    symbol: str
    symbol_name: str
    order_type: OrderType
    side: OrderSide
    quantity: int
    price: Optional[Decimal] = None
    status: OrderStatus = OrderStatus.PENDING
    created_time: datetime = field(default_factory=datetime.now)
    filled_time: Optional[datetime] = None
    filled_quantity: int = 0
    filled_price: Optional[Decimal] = None
    commission: Decimal = Decimal('0')

    @property
    def is_active(self) -> bool:
        """订单是否活跃"""
        return self.status == OrderStatus.PENDING


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    symbol_name: str
    quantity: int  # 持仓数量
    cost_price: Decimal  # 成本价
    current_price: Optional[Decimal] = None  # 当前价
    market_value: Optional[Decimal] = None  # 市值
    profit_loss: Optional[Decimal] = None  # 盈亏
    profit_loss_ratio: Optional[float] = None  # 盈亏比例
    last_update: datetime = field(default_factory=datetime.now)

    @property
    def avg_cost(self) -> float:
        """平均成本价"""
        return float(self.cost_price) if self.cost_price else 0.0

    @property
    def profit_loss_pct(self) -> float:
        """盈亏比例百分比"""
        return float(self.profit_loss_ratio) if self.profit_loss_ratio else 0.0

    def update_market_data(self, current_price: Decimal):
        """更新市场数据"""
        self.current_price = current_price
        self.market_value = current_price * self.quantity
        cost_value = self.cost_price * self.quantity
        self.profit_loss = self.market_value - cost_value

        if cost_value > 0:
            self.profit_loss_ratio = float(self.profit_loss / cost_value) * 100
        else:
            self.profit_loss_ratio = 0.0

        self.last_update = datetime.now()


@dataclass
class Portfolio:
    """投资组合"""
    portfolio_id: str
    name: str
    positions: Dict[str, Position] = field(default_factory=dict)
    cash: Decimal = Decimal('0')
    total_cost: Decimal = Decimal('0')
    total_market_value: Decimal = Decimal('0')
    total_profit_loss: Decimal = Decimal('0')

    # 交易面板需要的属性
    @property
    def available_cash(self) -> Decimal:
        """可用资金 - 等同于现金余额"""
        return self.cash

    @property
    def total_assets(self) -> Decimal:
        """总资产 - 现金 + 持仓市值"""
        return self.cash + self.total_market_value

    @property
    def market_value(self) -> Decimal:
        """持仓市值 - 等同于总市值"""
        return self.total_market_value

    @property
    def total_profit_loss_pct(self) -> float:
        """总盈亏百分比"""
        if self.total_cost > 0:
            return float(self.total_profit_loss / self.total_cost) * 100
        return 0.0
    total_profit_loss_ratio: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)

    def _recalculate(self):
        """重新计算组合指标"""
        # 确保所有计算都使用Decimal类型
        self.total_cost = Decimal(sum(pos.cost_price * pos.quantity for pos in self.positions.values()))

        # 计算持仓市值，确保使用Decimal
        positions_value = Decimal(sum(
            pos.market_value or (pos.current_price or pos.cost_price) * pos.quantity
            for pos in self.positions.values()
        ))
        self.total_market_value = Decimal(self.cash) + positions_value

        # 盈亏计算，确保都是Decimal
        self.total_profit_loss = self.total_market_value - self.total_cost

        if self.total_cost > Decimal('0'):
            self.total_profit_loss_ratio = float(self.total_profit_loss / self.total_cost) * 100
        else:
            self.total_profit_loss_ratio = 0.0

        self.last_update = datetime.now()


@dataclass
class TradingMetrics:
    """交易服务指标"""
    total_orders: int = 0
    filled_orders: int = 0
    cancelled_orders: int = 0
    active_orders: int = 0
    total_positions: int = 0
    total_volume: Decimal = Decimal('0')
    total_commission: Decimal = Decimal('0')
    last_update: datetime = field(default_factory=datetime.now)


class TradingService(BaseService, ModeAwareMixin):
    """
    统一交易服务 - 架构精简重构版本

    整合所有交易管理器功能：
    - TradingManager: 交易执行管理
    - RiskManager: 风险控制管理
    - PositionManager: 仓位管理
    - PortfolioManager: 投资组合管理
    """

    def __init__(self, service_container: Optional[ServiceContainer] = None):
        """初始化交易服务"""
        super().__init__()
        self.service_name = "TradingService"

        # 依赖注入
        self._service_container = service_container or get_service_container()

        # 事件总线
        self._event_bus = get_event_bus()

        # 延迟初始化 MarketService（避免循环依赖）
        self._market_service = None

        # 订单管理
        self._orders: Dict[str, TradingOrder] = {}
        self._active_orders: Dict[str, TradingOrder] = {}
        self._order_lock = threading.RLock()

        # 持仓管理
        self._positions: Dict[str, Position] = {}
        self._position_lock = threading.RLock()

        # 投资组合管理
        self._portfolios: Dict[str, Portfolio] = {}
        self._default_portfolio_id = "default"
        self._portfolio_lock = threading.RLock()

        # 交易历史记录
        self._trade_history: List[TradeRecord] = []
        self._trade_history_lock = threading.RLock()

        # 交易配置
        self._trading_config = {
            "commission_rate": 0.001,  # 0.1%
            "min_commission": Decimal('5.0'),  # 最小佣金
            "enable_risk_control": True,
        }

        # 服务指标
        self._trading_metrics = TradingMetrics()

        # 线程和锁
        self._service_lock = threading.RLock()

        # CTP接口管理
        self._ctp_interfaces: Dict[str, Any] = {}
        self._ctp_market_interfaces: Dict[str, Any] = {}
        self._ctp_lock = threading.RLock()

        logger.info("TradingService initialized for architecture simplification")
        
        # 模式上下文（ModeAwareMixin 要求）
        self._current_mode_context: Optional[ModeContext] = None
        self._mode_config: Dict[str, Any] = {}

    def _do_initialize(self) -> None:
        """执行具体的初始化逻辑"""
        try:
            logger.info("Initializing TradingService core components...")

            # 初始化默认投资组合
            self._initialize_default_portfolio()

            # 初始化 MarketService
            try:
                from .market_service import MarketService
                self._market_service = self._service_container.resolve(MarketService)
                logger.info("✓ MarketService initialized in TradingService")
            except Exception as e:
                logger.warning(f"Failed to initialize MarketService: {e}, will use fallback pricing")

            logger.info("TradingService initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize TradingService: {e}")
            raise

    def set_mode(self, mode: TradingMode, **config) -> None:
        """
        设置交易模式
        
        Args:
            mode: 交易模式
            **config: 模式相关配置
        """
        self._current_mode_context = ModeContext(
            mode=mode,
            config=config,
            metadata={'service': 'TradingService'}
        )
        self._mode_config = config
        logger.info(f"TradingService 设置为模式：{mode.value}")
        
        # 根据模式调整配置
        if mode == TradingMode.LIVE:
            self._trading_config["enable_risk_control"] = True
            self._trading_config["commission_rate"] = config.get("commission_rate", 0.001)
            logger.info("实盘模式：启用严格风控")
        elif mode == TradingMode.PAPER:
            self._trading_config["enable_risk_control"] = True
            self._trading_config["commission_rate"] = config.get("commission_rate", 0.001)
            logger.info("模拟模式：启用风控但不实际下单")
        elif mode == TradingMode.BACKTEST:
            self._trading_config["enable_risk_control"] = config.get("enable_risk_control", False)
            logger.info("回测模式：风控可选")

    def get_mode(self) -> TradingMode:
        """获取当前交易模式"""
        if self._current_mode_context:
            return self._current_mode_context.mode
        return TradingMode.BACKTEST  # 默认回测模式

    def is_backtest_mode(self) -> bool:
        """是否为回测模式"""
        return self.get_mode() == TradingMode.BACKTEST

    def is_live_mode(self) -> bool:
        """是否为实盘模式"""
        return self.get_mode() in (TradingMode.LIVE, TradingMode.PAPER)

    def _initialize_default_portfolio(self) -> None:
        """初始化默认投资组合"""
        try:
            default_portfolio = Portfolio(
                portfolio_id=self._default_portfolio_id,
                name="默认投资组合",
                cash=Decimal('100000')  # 10万初始资金
            )

            with self._portfolio_lock:
                self._portfolios[self._default_portfolio_id] = default_portfolio

            logger.info("✓ Default portfolio initialized")

        except Exception as e:
            logger.error(f"Failed to initialize default portfolio: {e}")

    def create_order(self, symbol: str, symbol_name: str, order_type: OrderType,
                     side: OrderSide, quantity: int, price: Optional[Decimal] = None) -> Tuple[bool, str]:
        """创建订单"""
        try:
            # 创建订单
            order_id = str(uuid.uuid4())
            order = TradingOrder(
                order_id=order_id,
                symbol=symbol,
                symbol_name=symbol_name,
                order_type=order_type,
                side=side,
                quantity=quantity,
                price=price
            )

            with self._order_lock:
                self._orders[order_id] = order
                self._active_orders[order_id] = order
                self._trading_metrics.total_orders += 1
                self._trading_metrics.active_orders += 1

            logger.info(f"Order created: {order_id} - {side.value} {quantity} {symbol}")
            return True, order_id

        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            return False, f"Order creation failed: {e}"

    async def execute_buy_order(self, stock_code: str, stock_name: str, quantity: int, price: Optional[Decimal] = None) -> TradeRecord:
        """
        执行买入订单

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            quantity: 买入数量
            price: 限价（可选），如果不提供则使用市价

        Returns:
            交易记录
        """
        try:
            # 获取当前价格
            if price is None:
                current_price = self._get_current_price(stock_code, stock_name)
                order_type = OrderType.MARKET
            else:
                current_price = price
                order_type = OrderType.LIMIT

            # 创建买入订单
            success, order_id = self.create_order(
                symbol=stock_code,
                symbol_name=stock_name,
                order_type=order_type,
                side=OrderSide.BUY,
                quantity=quantity,
                price=current_price
            )

            if not success:
                raise Exception(f"Failed to create buy order: {order_id}")

            # 执行订单
            success, message = self.execute_order(order_id, current_price)

            if not success:
                raise Exception(f"Failed to execute buy order: {message}")

            # 创建交易记录
            trade_record = TradeRecord(
                symbol=stock_code,
                stock_name=stock_name,
                action="buy",
                quantity=quantity,
                price=float(current_price),
                status="executed",
                order_id=order_id
            )

            # 添加到交易历史
            self.add_trade_record(trade_record)

            logger.info(f"Buy order executed: {stock_code} {quantity} @ {current_price}")
            return trade_record

        except Exception as e:
            logger.error(f"Failed to execute buy order: {e}")
            raise

    async def execute_sell_order(self, stock_code: str, stock_name: str, quantity: int, price: Optional[Decimal] = None) -> TradeRecord:
        """
        执行卖出订单

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            quantity: 卖出数量
            price: 限价（可选），如果不提供则使用市价

        Returns:
            交易记录
        """
        try:
            # 检查持仓
            position = self.get_position(stock_code)
            if not position or position.quantity < quantity:
                raise Exception(f"Insufficient position for {stock_code}")

            # 获取当前价格
            if price is None:
                current_price = self._get_current_price(stock_code, stock_name)
                order_type = OrderType.MARKET
            else:
                current_price = price
                order_type = OrderType.LIMIT

            # 创建卖出订单
            success, order_id = self.create_order(
                symbol=stock_code,
                symbol_name=stock_name,
                order_type=order_type,
                side=OrderSide.SELL,
                quantity=quantity,
                price=current_price
            )

            if not success:
                raise Exception(f"Failed to create sell order: {order_id}")

            # 执行订单
            success, message = self.execute_order(order_id, current_price)

            if not success:
                raise Exception(f"Failed to execute sell order: {message}")

            # 创建交易记录
            trade_record = TradeRecord(
                symbol=stock_code,
                stock_name=stock_name,
                action="sell",
                quantity=quantity,
                price=float(current_price),
                status="executed",
                order_id=order_id
            )

            # 添加到交易历史
            self.add_trade_record(trade_record)

            logger.info(f"Sell order executed: {stock_code} {quantity} @ {current_price}")
            return trade_record

        except Exception as e:
            logger.error(f"Failed to execute sell order: {e}")
            raise

    def execute_order(self, order_id: str, filled_price: Decimal) -> Tuple[bool, str]:
        """执行订单"""
        try:
            with self._order_lock:
                if order_id not in self._orders:
                    return False, "Order not found"

                order = self._orders[order_id]
                if not order.is_active:
                    return False, f"Order is not active"

                # 计算佣金
                trade_amount = filled_price * order.quantity
                commission = max(
                    trade_amount * Decimal(str(self._trading_config["commission_rate"])),
                    self._trading_config["min_commission"]
                )

                # 更新订单
                order.filled_quantity = order.quantity
                order.filled_price = filled_price
                order.commission = commission
                order.status = OrderStatus.FILLED
                order.filled_time = datetime.now()

                if order_id in self._active_orders:
                    del self._active_orders[order_id]

                self._trading_metrics.filled_orders += 1
                self._trading_metrics.active_orders = len(self._active_orders)
                self._trading_metrics.total_volume += trade_amount
                self._trading_metrics.total_commission += commission

            # 更新持仓
            self._update_position_from_trade(order, filled_price, commission)

            # 发布交易执行事件
            self._event_bus.publish(
                TradeExecutedEvent(
                    order_id=order_id,
                    symbol=order.symbol,
                    symbol_name=order.symbol_name,
                    side=str(order.side),
                    quantity=order.quantity,
                    price=float(filled_price),
                    commission=float(commission),
                    timestamp=datetime.now()
                )
            )

            logger.info(f"Order executed: {order_id} - {order.quantity}@{filled_price}")
            return True, "Order executed successfully"

        except Exception as e:
            logger.error(f"Failed to execute order: {e}")
            return False, f"Order execution failed: {e}"

    def _update_position_from_trade(self, order: TradingOrder, filled_price: Decimal, commission: Decimal):
        """从交易更新持仓"""
        try:
            with self._position_lock:
                if order.symbol not in self._positions:
                    if order.side == OrderSide.BUY:
                        position = Position(
                            symbol=order.symbol,
                            symbol_name=order.symbol_name,
                            quantity=order.quantity,
                            cost_price=filled_price
                        )
                        self._positions[order.symbol] = position
                        self._trading_metrics.total_positions += 1
                else:
                    position = self._positions[order.symbol]

                    if order.side == OrderSide.BUY:
                        # 买入：增加持仓
                        old_cost = position.cost_price * position.quantity
                        new_cost = old_cost + (filled_price * order.quantity) + commission
                        new_quantity = position.quantity + order.quantity
                        position.cost_price = new_cost / new_quantity
                        position.quantity = new_quantity

                    elif order.side == OrderSide.SELL:
                        # 卖出：减少持仓
                        position.quantity -= order.quantity

                        if position.quantity <= 0:
                            del self._positions[order.symbol]
                            self._trading_metrics.total_positions -= 1

            # 发布持仓更新事件
            self._event_bus.publish(
                PositionUpdatedEvent(
                    symbol=order.symbol,
                    symbol_name=order.symbol_name,
                    quantity=self._positions.get(order.symbol, Position(symbol=order.symbol, symbol_name=order.symbol_name, quantity=0)).quantity,
                    cost_price=float(self._positions.get(order.symbol, Position(symbol=order.symbol, symbol_name=order.symbol_name, quantity=0, cost_price=Decimal('0'))).cost_price),
                    timestamp=datetime.now()
                )
            )

        except Exception as e:
            logger.error(f"Failed to update position from trade: {e}")

    def get_order(self, order_id: str) -> Optional[TradingOrder]:
        """获取订单信息"""
        with self._order_lock:
            return self._orders.get(order_id)

    def get_active_orders(self) -> List[TradingOrder]:
        """获取活跃订单"""
        with self._order_lock:
            return list(self._active_orders.values())

    def get_position(self, symbol: str) -> Optional[Position]:
        """获取持仓信息"""
        with self._position_lock:
            return self._positions.get(symbol)

    def _get_current_price(self, stock_code: str, stock_name: str) -> Decimal:
        """
        获取当前价格

        优先级：
        1. 从 MarketService 获取实时行情
        2. 从持仓获取当前价格
        3. 抛出异常（不使用模拟数据）

        Args:
            stock_code: 股票代码
            stock_name: 股票名称

        Returns:
            当前价格

        Raises:
            ValueError: 无法获取价格时抛出
        """
        # 1. 尝试从 MarketService 获取实时行情
        if self._market_service:
            try:
                quote = self._market_service.get_quote(stock_code)
                if quote and quote.current_price:
                    logger.debug(f"Got real-time price for {stock_code}: {quote.current_price}")
                    return quote.current_price
            except Exception as e:
                logger.warning(f"Failed to get quote from MarketService: {e}")

        # 2. 尝试从持仓获取当前价格
        position = self.get_position(stock_code)
        if position and position.current_price:
            logger.debug(f"Got position price for {stock_code}: {position.current_price}")
            return position.current_price

        # 3. 无法获取价格，抛出异常
        error_msg = f"无法获取 {stock_code}({stock_name}) 的实时行情，请确保行情系统正常运行"
        logger.error(error_msg)
        raise ValueError(error_msg)

    def get_all_positions(self) -> Dict[str, Position]:
        """获取所有持仓"""
        with self._position_lock:
            return self._positions.copy()

    def get_portfolio(self, portfolio_id: str = None) -> Optional[Portfolio]:
        """获取投资组合"""
        portfolio_id = portfolio_id or self._default_portfolio_id
        with self._portfolio_lock:
            return self._portfolios.get(portfolio_id)

    def update_market_data(self, symbol: str, price: Decimal):
        """更新市场数据"""
        try:
            with self._position_lock:
                if symbol in self._positions:
                    position = self._positions[symbol]
                    position.update_market_data(price)

        except Exception as e:
            logger.error(f"Failed to update market data: {e}")

    def get_trading_metrics(self) -> TradingMetrics:
        """获取交易指标"""
        with self._service_lock:
            self._trading_metrics.last_update = datetime.now()
            return self._trading_metrics

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        获取性能统计信息

        Returns:
            包含性能统计的字典
        """
        try:
            with self._service_lock:
                # 获取投资组合
                portfolio = self.get_portfolio()

                # 获取交易指标
                metrics = self.get_trading_metrics()

                # 统计活跃策略数量（基于活跃订单和持仓）
                active_strategies = len(self._active_orders) + len([p for p in self._positions.values() if p.quantity > 0])
                total_strategies = len(self._orders)

                # 计算成功率（如果有filled_orders）
                success_rate = 0.0
                if metrics.filled_orders > 0:
                    # 使用filled_orders与total_orders的比率作为成功率
                    success_rate = metrics.filled_orders / max(metrics.total_orders, 1) * 100

                return {
                    'active_strategies': active_strategies,
                    'total_strategies': max(total_strategies, 1),  # 至少为1避免除零
                    'total_orders': metrics.total_orders,
                    'filled_orders': metrics.filled_orders,
                    'cancelled_orders': metrics.cancelled_orders,
                    'success_rate': success_rate,
                    'total_profit_loss': float(portfolio.total_profit_loss) if portfolio else 0.0,
                    'total_profit_loss_pct': portfolio.total_profit_loss_pct if portfolio else 0.0,
                    'win_rate': 0.0,  # 需要基于历史交易记录计算
                    'max_drawdown': 0.0,  # 需要基于历史净值计算
                    'sharpe_ratio': 0.0,  # 需要基于历史收益计算
                }

        except Exception as e:
            logger.error(f"Failed to get performance stats: {e}")
            return {
                'active_strategies': 0,
                'total_strategies': 1,
                'total_orders': 0,
                'filled_orders': 0,
                'cancelled_orders': 0,
                'success_rate': 0.0,
                'total_profit_loss': 0.0,
                'total_profit_loss_pct': 0.0,
                'win_rate': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
            }

    def _do_health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        try:
            return {
                "status": "healthy",
                "active_orders": len(self._active_orders),
                "total_positions": len(self._positions),
                "total_orders": self._trading_metrics.total_orders,
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _do_dispose(self) -> None:
        """清理资源"""
        try:
            logger.info("Disposing TradingService resources...")

            with self._order_lock:
                self._orders.clear()
                self._active_orders.clear()

            with self._position_lock:
                self._positions.clear()

            with self._portfolio_lock:
                self._portfolios.clear()

            logger.info("TradingService disposed successfully")

        except Exception as e:
            logger.error(f"Error disposing TradingService: {e}")

    def get_trade_history(self, limit: int = 50) -> List[TradeRecord]:
        """
        获取交易历史记录

        Args:
            limit: 返回记录数量限制，默认50条

        Returns:
            交易记录列表，按时间倒序排列
        """
        try:
            with self._trade_history_lock:
                # 按时间倒序排列，返回最近的记录
                sorted_history = sorted(
                    self._trade_history,
                    key=lambda x: x.timestamp,
                    reverse=True
                )
                return sorted_history[:limit]

        except Exception as e:
            logger.error(f"获取交易历史失败: {e}")
            return []

    def add_trade_record(self, trade_record: TradeRecord) -> None:
        """
        添加交易记录到历史

        Args:
            trade_record: 交易记录
        """
        try:
            with self._trade_history_lock:
                self._trade_history.append(trade_record)

                # 限制历史记录数量，避免内存过度使用
                max_history_size = 1000
                if len(self._trade_history) > max_history_size:
                    # 保留最新的记录
                    self._trade_history = sorted(
                        self._trade_history,
                        key=lambda x: x.timestamp,
                        reverse=True
                    )[:max_history_size]

            logger.debug(f"添加交易记录: {trade_record.trade_id}")

        except Exception as e:
            logger.error(f"添加交易记录失败: {e}")

    def clear_trade_history(self) -> None:
        """清空交易历史记录"""
        try:
            with self._trade_history_lock:
                self._trade_history.clear()
            logger.info("交易历史记录已清空")

        except Exception as e:
            logger.error(f"清空交易历史失败: {e}")

    def clear_all_positions(self) -> Tuple[bool, str]:
        """
        清空所有持仓

        Returns:
            (success, message) 成功标志和消息
        """
        try:
            with self._position_lock:
                if not self._positions:
                    return False, "没有持仓需要清空"

                # 获取所有持仓信息用于日志
                positions_info = [
                    f"{pos.symbol_name}({pos.symbol}): {pos.quantity}股"
                    for pos in self._positions.values()
                ]

                # 清空持仓
                self._positions.clear()
                self._trading_metrics.total_positions = 0

                # 更新投资组合
                portfolio = self.get_portfolio()
                if portfolio:
                    portfolio.total_market_value = Decimal('0')
                    portfolio.total_cost = Decimal('0')
                    portfolio.total_profit_loss = Decimal('0')
                    portfolio.total_profit_loss_ratio = 0.0
                    portfolio._recalculate()

                logger.info(f"已清空所有持仓: {', '.join(positions_info)}")
                return True, f"已清空 {len(positions_info)} 个持仓"

        except Exception as e:
            logger.error(f"清空持仓失败: {e}")
            return False, f"清空持仓失败: {e}"

    def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """
        撤销订单

        Args:
            order_id: 订单ID

        Returns:
            (success, message) 成功标志和消息
        """
        try:
            with self._order_lock:
                if order_id not in self._orders:
                    return False, f"订单 {order_id} 不存在"

                order = self._orders[order_id]

                if not order.is_active:
                    return False, f"订单 {order_id} 状态为 {order.status}，无法撤销"

                # 更新订单状态为已取消
                order.status = OrderStatus.CANCELLED

                if order_id in self._active_orders:
                    del self._active_orders[order_id]

                self._trading_metrics.cancelled_orders += 1
                self._trading_metrics.active_orders = len(self._active_orders)

                logger.info(f"订单已撤销: {order_id}")
                return True, f"订单 {order_id} 已成功撤销"

        except Exception as e:
            logger.error(f"撤销订单失败: {e}")
            return False, f"撤销订单失败: {e}"

    def get_portfolio(self, portfolio_id: Optional[str] = None) -> Optional[Portfolio]:
        """
        获取投资组合

        Args:
            portfolio_id: 投资组合ID，如果为None则返回默认组合

        Returns:
            投资组合对象，如果不存在则返回None
        """
        try:
            with self._portfolio_lock:
                target_id = portfolio_id or self._default_portfolio_id

                # 如果组合不存在，创建默认组合
                if target_id not in self._portfolios:
                    self._create_default_portfolio(target_id)

                return self._portfolios.get(target_id)

        except Exception as e:
            logger.error(f"获取投资组合失败: {e}")
            return None

    def _create_default_portfolio(self, portfolio_id: str) -> Portfolio:
        """
        创建默认投资组合

        Args:
            portfolio_id: 投资组合ID

        Returns:
            创建的投资组合对象
        """
        try:
            portfolio = Portfolio(
                portfolio_id=portfolio_id,
                name=f"默认投资组合-{portfolio_id}",
                cash=Decimal('100000.0'),  # 默认10万资金
                total_cost=Decimal('0'),
                total_market_value=Decimal('0'),
                total_profit_loss=Decimal('0')
            )

            self._portfolios[portfolio_id] = portfolio
            logger.info(f"创建默认投资组合: {portfolio_id}")

            return portfolio

        except Exception as e:
            logger.error(f"创建默认投资组合失败: {e}")
            raise

    def get_all_portfolios(self) -> Dict[str, Portfolio]:
        """获取所有投资组合"""
        try:
            with self._portfolio_lock:
                return self._portfolios.copy()

        except Exception as e:
            logger.error(f"获取所有投资组合失败: {e}")
            return {}

    def get_strategy_status(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """获取策略状态信息
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            包含策略状态信息的字典，如果策略不存在则返回None
        """
        try:
            # 检查策略是否在策略配置中存在
            from ..containers import get_service_container
            container = get_service_container()
            
            try:
                from .strategy_service import StrategyService
                strategy_service = container.resolve(StrategyService)
                
                if strategy_service and strategy_id in strategy_service._strategy_configs:
                    config = strategy_service._strategy_configs[strategy_id]
                    
                    # 返回策略状态信息
                    return {
                        'state': 'configured' if config.enabled else 'disabled',
                        'strategy_id': strategy_id,
                        'plugin_type': config.plugin_type,
                        'enabled': config.enabled,
                        'created_at': config.created_at.isoformat(),
                        'updated_at': config.updated_at.isoformat(),
                        'last_run': None,  # 可以后续扩展为实际的上次运行时间
                        'performance': None  # 可以后续扩展为实际性能数据
                    }
                else:
                    logger.warning(f"策略配置不存在: {strategy_id}")
                    return {
                        'state': 'not_found',
                        'strategy_id': strategy_id,
                        'error': 'Strategy configuration not found'
                    }
                    
            except Exception as e:
                logger.error(f"获取策略服务失败: {e}")
                # 如果无法获取策略服务，返回基本状态
                return {
                    'state': 'unknown',
                    'strategy_id': strategy_id,
                    'error': f'Strategy service unavailable: {str(e)}'
                }
                
        except Exception as e:
            logger.error(f"获取策略状态失败: {e}")
            return {
                'state': 'error',
                'strategy_id': strategy_id,
                'error': str(e)
            }


    # ==================== CTP接口管理 ====================

    def connect_ctp_account(self, account_id: str) -> Tuple[bool, str]:
        """
        连接CTP账户
        
        Args:
            account_id: 账户ID
            
        Returns:
            (success, message) 成功标志和消息
        """
        try:
            from core.trading.account_manager import AccountManager
            from core.trading.interfaces.ctp_trading_interface import CTPTradingInterface
            from core.trading.interfaces.ctp_market_interface import CTPMarketInterface
            from core.trading.interfaces.ctp_config import CTPConfig
            from core.trading.account_models import TradingInterfaceType
            
            account_manager = self._service_container.resolve(AccountManager)
            account = account_manager.get_account(account_id)
            
            if not account:
                return False, f"账户不存在: {account_id}"
            
            if account.trading_interface_type != TradingInterfaceType.CTP:
                return False, f"账户不是CTP类型: {account_id}"
            
            is_simulation = account.account_id.startswith("simnow_")
            
            config = CTPConfig(
                trade_front=account.ctp_trade_front,
                quote_front=account.ctp_quote_front,
                broker_id=account.ctp_broker_id,
                investor_id=account.ctp_investor_id,
                password=account.ctp_password,
                app_id=account.ctp_app_id,
                auth_code=account.ctp_auth_code,
                product_info=account.ctp_product_info,
                use_simulation=is_simulation
            )
            
            ctp_interface = CTPTradingInterface(config, self._event_bus)
            
            if not ctp_interface.connect():
                return False, f"CTP交易接口连接失败: {account_id}，请确保CTP SDK已安装"
            
            if not ctp_interface.login():
                return False, f"CTP交易接口登录失败: {account_id}，请检查账户配置"
            
            ctp_market_interface = CTPMarketInterface(config, self._event_bus)
            
            if not ctp_market_interface.connect():
                logger.warning(f"CTP行情接口连接失败: {account_id}，将继续使用交易接口")
            else:
                if not ctp_market_interface.login():
                    logger.warning(f"CTP行情接口登录失败: {account_id}，将继续使用交易接口")
            
            with self._ctp_lock:
                self._ctp_interfaces[account_id] = ctp_interface
                self._ctp_market_interfaces[account_id] = ctp_market_interface
            
            env_type = "SimNow模拟环境" if is_simulation else "实盘环境"
            logger.info(f"CTP账户连接成功: {account_id} ({env_type})")
            return True, f"CTP账户连接成功: {account_id} ({env_type})"
            
        except Exception as e:
            logger.error(f"连接CTP账户失败: {e}")
            return False, f"连接CTP账户失败: {e}"

    def disconnect_ctp_account(self, account_id: str) -> Tuple[bool, str]:
        """
        断开CTP账户连接
        
        Args:
            account_id: 账户ID
            
        Returns:
            (success, message) 成功标志和消息
        """
        try:
            with self._ctp_lock:
                if account_id in self._ctp_interfaces:
                    ctp_interface = self._ctp_interfaces[account_id]
                    ctp_interface.disconnect()
                    del self._ctp_interfaces[account_id]
                
                if account_id in self._ctp_market_interfaces:
                    ctp_market_interface = self._ctp_market_interfaces[account_id]
                    ctp_market_interface.disconnect()
                    del self._ctp_market_interfaces[account_id]
            
            logger.info(f"CTP账户已断开: {account_id}")
            return True, f"CTP账户已断开: {account_id}"
            
        except Exception as e:
            logger.error(f"断开CTP账户失败: {e}")
            return False, f"断开CTP账户失败: {e}"

    def get_ctp_connection_status(self, account_id: str) -> dict:
        """
        获取CTP连接状态
        
        Args:
            account_id: 账户ID
            
        Returns:
            dict: 连接状态信息
        """
        try:
            with self._ctp_lock:
                trading_connected = account_id in self._ctp_interfaces
                market_connected = account_id in self._ctp_market_interfaces
                
                return {
                    'account_id': account_id,
                    'trading_connected': trading_connected,
                    'market_connected': market_connected,
                    'fully_connected': trading_connected and market_connected
                }
                
        except Exception as e:
            logger.error(f"获取CTP连接状态失败: {e}")
            return {
                'account_id': account_id,
                'trading_connected': False,
                'market_connected': False,
                'fully_connected': False,
                'error': str(e)
            }

    def subscribe_ctp_quote(self, account_id: str, symbols: List[str]) -> Tuple[bool, str]:
        """
        订阅CTP行情
        
        Args:
            account_id: 账户ID
            symbols: 合约代码列表
            
        Returns:
            (success, message) 成功标志和消息
        """
        try:
            with self._ctp_lock:
                if account_id not in self._ctp_market_interfaces:
                    return False, f"CTP行情接口未连接: {account_id}"
                
                ctp_market_interface = self._ctp_market_interfaces[account_id]
                success = ctp_market_interface.subscribe_quote(symbols)
                
                if success:
                    return True, f"订阅CTP行情成功: {len(symbols)} 个合约"
                else:
                    return False, "订阅CTP行情失败"
                    
        except Exception as e:
            logger.error(f"订阅CTP行情失败: {e}")
            return False, f"订阅CTP行情失败: {e}"

    def get_ctp_quote(self, account_id: str, symbol: str) -> Optional[Any]:
        """
        获取CTP行情数据
        
        Args:
            account_id: 账户ID
            symbol: 合约代码
            
        Returns:
            行情数据，如果不存在则返回 None
        """
        try:
            with self._ctp_lock:
                if account_id not in self._ctp_market_interfaces:
                    logger.warning(f"CTP行情接口未连接: {account_id}")
                    return None
                
                ctp_market_interface = self._ctp_market_interfaces[account_id]
                return ctp_market_interface.get_quote(symbol)
                
        except Exception as e:
            logger.error(f"获取CTP行情数据失败: {e}")
            return None
