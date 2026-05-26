from core.performance import measure_performance as monitor_performance
from core.trading_engine import PositionType
from typing import TYPE_CHECKING, Dict, List
from loguru import logger

if TYPE_CHECKING:
    from core.strategy_extensions import Signal


class PositionManager:
    """仓位管理器（纯计算模块）

    设计特性：
    本模块是纯函数计算模块，不维护持久化持仓状态。所有仓位相关计算
    （如 calculate_exposure）依赖外部传入的持仓数据，自身无状态。

    数据流向：
    ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
    │  trading_engine   │────▶│   EventBus        │────▶│  account_manager │
    │  positions: Dict  │     │ 'position_updated'│     │  _positions: Dict│
    └──────────────────┘     └──────────────────┘     └──────────────────┘
                                      │
                                      │ (PositionManager 不订阅事件，
                                      │  由调用方负责传入最新持仓数据)
                                      ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │  PositionManager (本模块)                                         │
    │  - calculate_exposure(positions: List) → 纯函数，数据由外部注入   │
    │  - _get_buy_num(signal) → 依赖外部设置的 self.account             │
    │  - 无 EventBus 订阅，无内部持仓状态                                │
    └──────────────────────────────────────────────────────────────────┘

    TECH_DEBT-001 同步机制说明：
    trading_engine._publish_position_updated_event() 发布 PositionUpdatedEvent；
    account_manager._setup_position_sync_handlers() 订阅 'position_updated' 事件。
    PositionManager 作为纯计算模块，不直接订阅事件——调用方（如 TradeOrchestrator、
    risk_manager 等）负责在调用前确保传入的持仓数据已是最新状态。

    如需 PositionManager 感知持仓变更，应在调用方层面处理：
    ```python
    # 推荐：调用方订阅事件并在调用时传入最新数据
    event_bus.subscribe(PositionUpdatedEvent, lambda e: update_local_cache(e))
    # 然后在计算时使用缓存数据
    exposure = position_manager.calculate_exposure(latest_positions)
    ```
    """

    def __init__(self, account=None):
        self.account = account
        self.lot_size = 100
        self.commission_rate = 0.001
        self.position_limit = 0
        logger.info("仓位管理器初始化完成")

    def set_account(self, account):
        self.account = account

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
        long_value = sum(p.quantity * p.current_price for p in positions if p.position_type == PositionType.LONG)
        short_value = sum(p.quantity * p.current_price for p in positions if p.position_type == PositionType.SHORT)
        return {'long': long_value, 'short': short_value, 'net': long_value - short_value}
