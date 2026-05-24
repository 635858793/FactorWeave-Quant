from core.performance import measure_performance as monitor_performance
from typing import TYPE_CHECKING, Dict, List
from loguru import logger

if TYPE_CHECKING:
    from core.strategy_extensions import Signal


class PositionManager:
    """仓位管理器

    设计债务（TECH_DEBT-001）：持仓三分问题
    本模块的仓位计算逻辑依赖外部传入的持仓数据，自身不维护持久化持仓状态。
    而 core/risk_manager.py（current_positions: dict）和 core/trading_engine.py
    （positions: Dict[str, Position]）各自独立维护持仓，三者之间无同步机制。
    建议通过事件总线（EventBus）同步：当任一处持仓变更时，发布
    'position_updated' 事件，由其他两模块订阅并更新。
    """

    def __init__(self):
        self.account = None
        self.lot_size = 100
        self.commission_rate = 0.001
        self.position_limit = 0
        logger.info("仓位管理器初始化完成")

    @monitor_performance("get_buy_num")
    def _get_buy_num(self, signal: 'Signal') -> int:
        """
        根据信号计算买入数量

        Args:
            signal (Signal): 交易信号

        Returns:
            int: 买入数量
        """
        if not signal.buy_price or signal.buy_price <= 0:
            return 0

        if not self.account or not hasattr(self.account, 'available_cash'):
            return 0
            
        available_cash = self.account.available_cash
        if available_cash <= 0:
            return 0

        # 计算每手交易成本
        cost_per_lot = signal.buy_price * \
            self.lot_size * (1 + self.commission_rate)

        # 计算最大可买入手数
        max_lots = int(available_cash / cost_per_lot)

        # 如果资金不足买一手，返回0
        if max_lots == 0:
            return 0

        # 如果有仓位限制，取较小值
        if self.position_limit > 0:
            max_lots = min(max_lots, self.position_limit)

        return max_lots * self.lot_size

    def get_sell_num(self, cash: float, price: float, risk_per_trade: float = 0.02) -> int:
        risk_amount = cash * risk_per_trade
        return int(risk_amount / price)

    def calculate_exposure(self, positions: List) -> Dict[str, float]:
        long_value = sum(p.quantity * p.current_price for p in positions if p.direction == 'BUY')
        short_value = sum(p.quantity * p.current_price for p in positions if p.direction == 'SELL')
        return {'long': long_value, 'short': short_value, 'net': long_value - short_value}
