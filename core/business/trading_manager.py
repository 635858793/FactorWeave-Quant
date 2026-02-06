from loguru import logger
"""
交易管理业务逻辑

负责交易执行和风险控制相关的业务逻辑处理，包括：
- 交易信号执行
- 风险控制
- 订单管理
- 交易记录
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from ..data.models import StockInfo
from ..data.data_access import DataAccess


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"  # 市价单
    LIMIT = "limit"    # 限价单
    STOP = "stop"      # 止损单


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"      # 待成交
    FILLED = "filled"        # 已成交
    CANCELLED = "cancelled"  # 已取消
    REJECTED = "rejected"    # 已拒绝


@dataclass
class Order:
    """订单信息"""
    order_id: str
    stock_code: str
    stock_name: str
    order_type: OrderType
    side: str  # 'buy' or 'sell'
    quantity: int
    price: Optional[Decimal] = None  # 限价单价格
    status: OrderStatus = OrderStatus.PENDING
    created_time: datetime = None
    filled_time: Optional[datetime] = None
    filled_price: Optional[Decimal] = None
    filled_quantity: int = 0
    commission: Decimal = Decimal('0')
    notes: str = ""


@dataclass
class TradeRecord:
    """交易记录"""
    trade_id: str
    stock_code: str
    stock_name: str
    side: str  # 'buy' or 'sell'
    quantity: int
    price: Decimal
    amount: Decimal  # 交易金额
    commission: Decimal  # 手续费
    trade_time: datetime
    order_id: str
    notes: str = ""


class TradingManager:
    """交易管理器"""

    def __init__(self, data_access: DataAccess):
        self.data_access = data_access
        self._orders: Dict[str, Order] = {}  # 订单字典
        self._trade_records: List[TradeRecord] = []  # 交易记录
        self._next_order_id = 1
        self._next_trade_id = 1

        # 交易参数
        self._commission_rate = Decimal('0.0003')  # 手续费率 0.03%
        self._min_commission = Decimal('5.0')      # 最低手续费 5元
        self._max_position_ratio = 0.3             # 单只股票最大仓位比例
        self._max_single_trade_ratio = 0.1         # 单笔交易最大资金比例

    def place_order(self, stock_code: str, side: str, quantity: int,
                    order_type: OrderType = OrderType.MARKET,
                    price: Optional[Decimal] = None) -> Optional[str]:
        """
        下单

        Args:
            stock_code: 股票代码
            side: 买卖方向 ('buy' or 'sell')
            quantity: 数量
            order_type: 订单类型
            price: 价格（限价单时必填）

        Returns:
            订单ID，如果下单失败返回None
        """
        try:
            # 获取股票信息
            stock_info = self.data_access.get_stock_info(stock_code)
            if not stock_info:
                self.logger.error(f"Stock {stock_code} not found")
                return None

            # 生成订单ID
            order_id = f"ORD{self._next_order_id:06d}"
            self._next_order_id += 1

            # 创建订单
            order = Order(
                order_id=order_id,
                stock_code=stock_code,
                stock_name=stock_info.name,
                order_type=order_type,
                side=side,
                quantity=quantity,
                price=price,
                created_time=datetime.now()
            )

            # 风险检查
            if not self._risk_check(order):
                order.status = OrderStatus.REJECTED
                order.notes = "风险检查未通过"
                self._orders[order_id] = order
                return None

            # 保存订单
            self._orders[order_id] = order

            # 模拟订单执行（在实际系统中这里会发送到交易所）
            self._simulate_order_execution(order)

            self.logger.info(
                f"Order placed: {order_id} - {side} {quantity} {stock_code}")
            return order_id

        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """
        取消订单

        Args:
            order_id: 订单ID

        Returns:
            是否取消成功
        """
        try:
            if order_id not in self._orders:
                self.logger.error(f"Order {order_id} not found")
                return False

            order = self._orders[order_id]

            if order.status != OrderStatus.PENDING:
                self.logger.error(
                    f"Order {order_id} cannot be cancelled, status: {order.status}")
                return False

            order.status = OrderStatus.CANCELLED
            order.notes = "用户取消"

            self.logger.info(f"Order cancelled: {order_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def get_orders(self, status: Optional[OrderStatus] = None) -> List[Order]:
        """
        获取订单列表

        Args:
            status: 订单状态筛选

        Returns:
            订单列表
        """
        orders = list(self._orders.values())

        if status:
            orders = [o for o in orders if o.status == status]

        # 按创建时间倒序排列
        orders.sort(key=lambda x: x.created_time, reverse=True)
        return orders

    def get_order(self, order_id: str) -> Optional[Order]:
        """
        获取订单详情

        Args:
            order_id: 订单ID

        Returns:
            订单信息
        """
        return self._orders.get(order_id)

    def get_trade_records(self, stock_code: Optional[str] = None,
                          days: int = 30) -> List[TradeRecord]:
        """
        获取交易记录

        Args:
            stock_code: 股票代码筛选
            days: 查询天数

        Returns:
            交易记录列表
        """
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days)

            records = [
                r for r in self._trade_records if r.trade_time >= cutoff_date]

            if stock_code:
                records = [r for r in records if r.stock_code == stock_code]

            # 按交易时间倒序排列
            records.sort(key=lambda x: x.trade_time, reverse=True)
            return records

        except Exception as e:
            self.logger.error(f"Failed to get trade records: {e}")
            return []

    def get_trading_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        获取交易统计

        Args:
            days: 统计天数

        Returns:
            交易统计信息
        """
        try:
            records = self.get_trade_records(days=days)

            if not records:
                return {
                    'total_trades': 0,
                    'total_volume': Decimal('0'),
                    'total_commission': Decimal('0'),
                    'buy_trades': 0,
                    'sell_trades': 0,
                    'most_traded_stock': None
                }

            total_trades = len(records)
            total_volume = sum(r.amount for r in records)
            total_commission = sum(r.commission for r in records)
            buy_trades = len([r for r in records if r.side == 'buy'])
            sell_trades = len([r for r in records if r.side == 'sell'])

            # 统计最常交易的股票
            stock_counts = {}
            for record in records:
                stock_counts[record.stock_code] = stock_counts.get(
                    record.stock_code, 0) + 1

            most_traded_stock = max(stock_counts.items(), key=lambda x: x[1])[
                0] if stock_counts else None

            return {
                'total_trades': total_trades,
                'total_volume': float(total_volume),
                'total_commission': float(total_commission),
                'buy_trades': buy_trades,
                'sell_trades': sell_trades,
                'most_traded_stock': most_traded_stock,
                'average_trade_size': float(total_volume / total_trades) if total_trades > 0 else 0,
                'commission_rate': float(total_commission / total_volume) * 100 if total_volume > 0 else 0
            }

        except Exception as e:
            self.logger.error(f"Failed to get trading statistics: {e}")
            return {}

    def _risk_check(self, order: Order) -> bool:
        """风险检查"""
        try:
            # 检查股票是否存在
            stock_info = self.data_access.get_stock_info(order.stock_code)
            if not stock_info:
                self.logger.warning(
                    f"Risk check failed: stock {order.stock_code} not found")
                return False

            # 检查数量是否合理（至少100股，且为100的倍数）
            if order.quantity < 100 or order.quantity % 100 != 0:
                self.logger.warning(
                    f"Risk check failed: invalid quantity {order.quantity}")
                return False

            # 检查价格是否合理（限价单）
            if order.order_type == OrderType.LIMIT and order.price:
                current_price = self.data_access.get_latest_price(
                    order.stock_code)
                if current_price:
                    price_diff_ratio = abs(
                        float(order.price) - current_price) / current_price
                    if price_diff_ratio > 0.2:  # 价格偏差超过20%
                        self.logger.warning(
                            f"Risk check failed: price deviation too large")
                        return False

            return True

        except Exception as e:
            self.logger.error(f"Risk check error: {e}")
            return False

    def _simulate_order_execution(self, order: Order) -> None:
        """模拟订单执行"""
        try:
            # 获取当前价格
            current_price = self.data_access.get_latest_price(order.stock_code)
            if not current_price:
                order.status = OrderStatus.REJECTED
                order.notes = "无法获取当前价格"
                return

            # 模拟成交
            filled_price = Decimal(str(current_price))

            # 限价单检查
            if order.order_type == OrderType.LIMIT and order.price:
                if order.side == 'buy' and order.price < filled_price:
                    # 买入限价单价格低于当前价，不成交
                    return
                elif order.side == 'sell' and order.price > filled_price:
                    # 卖出限价单价格高于当前价，不成交
                    return
                filled_price = order.price

            # 计算手续费
            amount = filled_price * order.quantity
            commission = max(amount * self._commission_rate,
                             self._min_commission)

            # 更新订单状态
            order.status = OrderStatus.FILLED
            order.filled_time = datetime.now()
            order.filled_price = filled_price
            order.filled_quantity = order.quantity
            order.commission = commission

            # 创建交易记录
            trade_id = f"TRD{self._next_trade_id:06d}"
            self._next_trade_id += 1

            trade_record = TradeRecord(
                trade_id=trade_id,
                stock_code=order.stock_code,
                stock_name=order.stock_name,
                side=order.side,
                quantity=order.quantity,
                price=filled_price,
                amount=amount,
                commission=commission,
                trade_time=order.filled_time,
                order_id=order.order_id
            )

            self._trade_records.append(trade_record)
            self.logger.info(
                f"Order executed: {order.order_id} - {trade_record.trade_id}")

        except Exception as e:
            self.logger.error(f"Order execution simulation failed: {e}")
            order.status = OrderStatus.REJECTED
            order.notes = f"执行失败: {str(e)}"

    def set_commission_rate(self, rate: float) -> None:
        """设置手续费率"""
        self._commission_rate = Decimal(str(rate))
        self.logger.info(f"Commission rate set to {rate:.4%}")

    def set_min_commission(self, amount: float) -> None:
        """设置最低手续费"""
        self._min_commission = Decimal(str(amount))
        self.logger.info(f"Minimum commission set to {amount}")

    def clear_history(self) -> None:
        """清除历史记录"""
        # 只保留未完成的订单
        pending_orders = {k: v for k, v in self._orders.items(
        ) if v.status == OrderStatus.PENDING}
        self._orders = pending_orders

        # 清除交易记录
        self._trade_records.clear()

        self.logger.info("Trading history cleared")
