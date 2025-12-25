"""
统一交易服务 - 架构精简重构版本

整合所有交易管理器功能，提供统一的交易执行和风险控制接口。
整合TradingManager、RiskManager、PositionManager、PortfolioManager等。
完全重构以符合15个核心服务的架构精简目标。
"""

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
from ..events import EventBus, get_event_bus
from ..containers import ServiceContainer, get_service_container
from ..strategy_extensions import StrategyLifecycle

# 为了向后兼容，将 StrategyLifecycle 重命名为 StrategyState
StrategyState = StrategyLifecycle


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


class TradingService(BaseService):
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

        logger.info("TradingService initialized for architecture simplification")

    def _do_initialize(self) -> None:
        """执行具体的初始化逻辑"""
        try:
            logger.info("Initializing TradingService core components...")

            # 初始化默认投资组合
            self._initialize_default_portfolio()

            logger.info("✅ TradingService initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize TradingService: {e}")
            raise

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
