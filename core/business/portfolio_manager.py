from loguru import logger
"""
投资组合管理业务逻辑

负责投资组合相关的业务逻辑处理，包括：
- 持仓管理
- 投资组合分析
- 风险评估
- 收益计算
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from decimal import Decimal

from ..data.models import StockInfo, KlineData
from ..data.data_access import DataAccess


@dataclass
class Position:
    """持仓信息"""
    stock_code: str
    stock_name: str
    quantity: int  # 持仓数量
    cost_price: Decimal  # 成本价
    current_price: Optional[Decimal] = None  # 当前价
    market_value: Optional[Decimal] = None  # 市值
    profit_loss: Optional[Decimal] = None  # 盈亏
    profit_loss_ratio: Optional[float] = None  # 盈亏比例
    weight: Optional[float] = None  # 仓位权重

    def update_current_data(self, current_price: Decimal, total_value: Decimal):
        """更新当前数据"""
        self.current_price = current_price
        self.market_value = current_price * self.quantity
        self.profit_loss = self.market_value - \
            (self.cost_price * self.quantity)
        self.profit_loss_ratio = float(
            self.profit_loss / (self.cost_price * self.quantity)) * 100
        self.weight = float(self.market_value / total_value) * \
            100 if total_value > 0 else 0


@dataclass
class PortfolioSummary:
    """投资组合摘要"""
    total_cost: Decimal  # 总成本
    total_market_value: Decimal  # 总市值
    total_profit_loss: Decimal  # 总盈亏
    total_profit_loss_ratio: float  # 总盈亏比例
    position_count: int  # 持仓数量
    cash_available: Decimal  # 可用资金
    total_assets: Decimal  # 总资产
    last_updated: datetime  # 最后更新时间


class PortfolioManager:
    """投资组合管理器"""

    def __init__(self, data_access: DataAccess):
        self.data_access = data_access
        self._positions: Dict[str, Position] = {}  # 持仓字典
        self._cash_available = Decimal('100000.00')  # 初始可用资金10万
        self._transaction_history = []  # 交易历史

    def add_position(self, stock_code: str, quantity: int,
                     cost_price: Decimal) -> bool:
        """
        添加持仓

        Args:
            stock_code: 股票代码
            quantity: 数量
            cost_price: 成本价

        Returns:
            是否添加成功
        """
        try:
            # 获取股票信息
            stock_info = self.data_access.get_stock_info(stock_code)
            if not stock_info:
                self.logger.error(f"Stock {stock_code} not found")
                return False

            # 计算所需资金
            required_cash = Decimal(quantity) * cost_price
            if required_cash > self._cash_available:
                self.logger.error(
                    f"Insufficient cash: required {required_cash}, available {self._cash_available}")
                return False

            # 添加或更新持仓
            if stock_code in self._positions:
                # 更新现有持仓
                existing = self._positions[stock_code]
                total_quantity = existing.quantity + quantity
                total_cost = (existing.quantity *
                              existing.cost_price) + (quantity * cost_price)
                new_cost_price = total_cost / total_quantity

                existing.quantity = total_quantity
                existing.cost_price = new_cost_price
            else:
                # 新增持仓
                position = Position(
                    stock_code=stock_code,
                    stock_name=stock_info.name,
                    quantity=quantity,
                    cost_price=cost_price
                )
                self._positions[stock_code] = position

            # 扣除资金
            self._cash_available -= required_cash

            # 记录交易
            self._transaction_history.append({
                'type': 'buy',
                'stock_code': stock_code,
                'quantity': quantity,
                'price': cost_price,
                'timestamp': datetime.now(),
                'total_amount': required_cash
            })

            self.logger.info(
                f"Added position: {stock_code} x{quantity} @ {cost_price}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to add position {stock_code}: {e}")
            return False

    def reduce_position(self, stock_code: str, quantity: int,
                        sell_price: Decimal) -> bool:
        """
        减少持仓

        Args:
            stock_code: 股票代码
            quantity: 减少数量
            sell_price: 卖出价格

        Returns:
            是否操作成功
        """
        try:
            if stock_code not in self._positions:
                self.logger.error(f"Position {stock_code} not found")
                return False

            position = self._positions[stock_code]
            if quantity > position.quantity:
                self.logger.error(
                    f"Insufficient position: trying to sell {quantity}, available {position.quantity}")
                return False

            # 计算收回资金
            cash_received = Decimal(quantity) * sell_price
            self._cash_available += cash_received

            # 更新持仓
            if quantity == position.quantity:
                # 清空持仓
                del self._positions[stock_code]
            else:
                # 减少持仓
                position.quantity -= quantity

            # 记录交易
            self._transaction_history.append({
                'type': 'sell',
                'stock_code': stock_code,
                'quantity': quantity,
                'price': sell_price,
                'timestamp': datetime.now(),
                'total_amount': cash_received
            })

            self.logger.info(
                f"Reduced position: {stock_code} x{quantity} @ {sell_price}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to reduce position {stock_code}: {e}")
            return False

    def get_positions(self) -> List[Position]:
        """
        获取所有持仓

        Returns:
            持仓列表
        """
        try:
            positions = list(self._positions.values())

            # 更新当前价格和计算数据
            total_value = Decimal('0')
            for position in positions:
                # 获取当前价格
                current_price = self.data_access.get_latest_price(
                    position.stock_code)
                if current_price:
                    position.current_price = Decimal(str(current_price))
                    position.market_value = position.current_price * position.quantity
                    total_value += position.market_value

            # 计算权重和盈亏
            for position in positions:
                if position.market_value:
                    position.update_current_data(
                        position.current_price, total_value)

            return positions

        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
            return []

    def get_position(self, stock_code: str) -> Optional[Position]:
        """
        获取指定持仓

        Args:
            stock_code: 股票代码

        Returns:
            持仓信息，如果不存在返回None
        """
        if stock_code not in self._positions:
            return None

        positions = self.get_positions()
        for position in positions:
            if position.stock_code == stock_code:
                return position

        return None

    def get_portfolio_summary(self) -> PortfolioSummary:
        """
        获取投资组合摘要

        Returns:
            投资组合摘要
        """
        try:
            positions = self.get_positions()

            total_cost = Decimal('0')
            total_market_value = Decimal('0')

            for position in positions:
                total_cost += position.cost_price * position.quantity
                if position.market_value:
                    total_market_value += position.market_value

            total_profit_loss = total_market_value - total_cost
            total_profit_loss_ratio = float(
                total_profit_loss / total_cost) * 100 if total_cost > 0 else 0
            total_assets = total_market_value + self._cash_available

            return PortfolioSummary(
                total_cost=total_cost,
                total_market_value=total_market_value,
                total_profit_loss=total_profit_loss,
                total_profit_loss_ratio=total_profit_loss_ratio,
                position_count=len(positions),
                cash_available=self._cash_available,
                total_assets=total_assets,
                last_updated=datetime.now()
            )

        except Exception as e:
            self.logger.error(f"Failed to get portfolio summary: {e}")
            return PortfolioSummary(
                total_cost=Decimal('0'),
                total_market_value=Decimal('0'),
                total_profit_loss=Decimal('0'),
                total_profit_loss_ratio=0.0,
                position_count=0,
                cash_available=self._cash_available,
                total_assets=self._cash_available,
                last_updated=datetime.now()
            )

    def get_top_positions(self, limit: int = 5) -> List[Position]:
        """
        获取权重最大的持仓

        Args:
            limit: 返回数量限制

        Returns:
            按权重排序的持仓列表
        """
        positions = self.get_positions()
        positions.sort(key=lambda x: x.weight or 0, reverse=True)
        return positions[:limit]

    def get_profit_loss_positions(self, profit_only: bool = False) -> List[Position]:
        """
        获取盈亏持仓

        Args:
            profit_only: 是否只返回盈利持仓

        Returns:
            按盈亏排序的持仓列表
        """
        positions = self.get_positions()

        if profit_only:
            positions = [
                p for p in positions if p.profit_loss and p.profit_loss > 0]

        positions.sort(
            key=lambda x: x.profit_loss or Decimal('0'), reverse=True)
        return positions

    def calculate_risk_metrics(self) -> Dict[str, Any]:
        """
        计算风险指标

        Returns:
            风险指标字典
        """
        try:
            positions = self.get_positions()
            summary = self.get_portfolio_summary()

            if not positions:
                return {'error': 'No positions found'}

            # 计算集中度风险
            weights = [p.weight or 0 for p in positions]
            max_weight = max(weights) if weights else 0

            # 计算行业分散度
            industries = {}
            for position in positions:
                stock_info = self.data_access.get_stock_info(
                    position.stock_code)
                if stock_info and stock_info.industry:
                    industry = stock_info.industry
                    industries[industry] = industries.get(
                        industry, 0) + (position.weight or 0)

            industry_concentration = max(
                industries.values()) if industries else 0

            return {
                'max_position_weight': max_weight,
                'industry_concentration': industry_concentration,
                'position_count': len(positions),
                'cash_ratio': float(summary.cash_available / summary.total_assets) * 100,
                # 简单的分散度评分
                'diversification_score': min(100, len(positions) * 10),
                'risk_level': self._assess_risk_level(max_weight, industry_concentration, len(positions))
            }

        except Exception as e:
            self.logger.error(f"Failed to calculate risk metrics: {e}")
            return {'error': str(e)}

    def _assess_risk_level(self, max_weight: float, industry_concentration: float,
                           position_count: int) -> str:
        """评估风险等级"""
        risk_score = 0

        # 单一持仓过大
        if max_weight > 30:
            risk_score += 3
        elif max_weight > 20:
            risk_score += 2
        elif max_weight > 10:
            risk_score += 1

        # 行业集中度过高
        if industry_concentration > 50:
            risk_score += 3
        elif industry_concentration > 30:
            risk_score += 2
        elif industry_concentration > 20:
            risk_score += 1

        # 持仓数量过少
        if position_count < 3:
            risk_score += 2
        elif position_count < 5:
            risk_score += 1

        if risk_score >= 5:
            return 'High'
        elif risk_score >= 3:
            return 'Medium'
        else:
            return 'Low'

    def get_transaction_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        获取交易历史

        Args:
            days: 查询天数

        Returns:
            交易历史列表
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_transactions = [
                t for t in self._transaction_history
                if t['timestamp'] >= cutoff_date
            ]

            # 按时间倒序排列
            recent_transactions.sort(
                key=lambda x: x['timestamp'], reverse=True)
            return recent_transactions

        except Exception as e:
            self.logger.error(f"Failed to get transaction history: {e}")
            return []

    def set_cash_available(self, amount: Decimal) -> None:
        """
        设置可用资金

        Args:
            amount: 资金金额
        """
        self._cash_available = amount
        self.logger.info(f"Cash available set to {amount}")

    def clear_positions(self) -> None:
        """清空所有持仓"""
        self._positions.clear()
        self._transaction_history.clear()
        self.logger.info("All positions cleared")
