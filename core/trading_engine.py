from loguru import logger
"""
交易引擎核心模块

提供统一的交易执行、信号处理和仓位管理功能
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import pandas as pd
from dataclasses import dataclass, asdict
from enum import Enum

from .events import EventBus, TradeExecutedEvent, PositionUpdatedEvent
from .containers import ServiceContainer

class SignalType(Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

class PositionType(Enum):
    """仓位类型"""
    LONG = "long"
    SHORT = "short"
    EMPTY = "empty"

@dataclass
class TradingSignal:
    """交易信号"""
    symbol: str
    signal_type: SignalType
    timestamp: datetime
    price: float
    volume: int = 0
    confidence: float = 1.0
    reason: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class Position:
    """持仓信息"""
    symbol: str
    position_type: PositionType
    quantity: int
    avg_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    @property
    def market_value(self) -> float:
        """市值"""
        return self.quantity * self.current_price

    def update_price(self, new_price: float):
        """更新当前价格"""
        self.current_price = new_price
        if self.position_type == PositionType.LONG:
            self.unrealized_pnl = (new_price - self.avg_price) * self.quantity
        elif self.position_type == PositionType.SHORT:
            self.unrealized_pnl = (self.avg_price - new_price) * self.quantity

class TradingEngine:
    """
    交易引擎

    负责：
    1. 交易信号处理
    2. 仓位管理
    3. 订单执行
    4. 风险控制
    """

    def __init__(self, service_container: ServiceContainer, event_bus: EventBus):
        """
        初始化交易引擎

        Args:
            service_container: 服务容器
            event_bus: 事件总线
        """
        self.service_container = service_container
        self.event_bus = event_bus

        # 当前状态
        self.current_symbol: Optional[str] = None
        self.current_kdata: Optional[pd.DataFrame] = None
        self.positions: Dict[str, Position] = {}
        self.signals: List[TradingSignal] = []

        # 配置参数
        self.commission_rate = 0.0003  # 佣金费率
        self.min_commission = 5.0      # 最小佣金
        self.stamp_tax_rate = 0.001    # 印花税率

        # 风险控制参数
        self.max_position_size = 1000000  # 最大仓位
        self.max_single_position = 100000  # 单个股票最大仓位

        logger.info("交易引擎初始化完成")

    def set_symbol(self, symbol: str):
        """
        设置当前交易标的

        Args:
            symbol: 标的代码
        """
        try:
            self.current_symbol = symbol
            self.current_kdata = None
            logger.info(f"设置当前交易标的: {symbol}")

        except Exception as e:
            logger.error(f"设置交易标的失败: {e}")
            raise

    def load_kdata(self, symbol: str = None, period: str = 'D', count: int = 365) -> pd.DataFrame:
        """
        加载K线数据

        Args:
            symbol: 标的代码，如果为None则使用当前标的
            period: 周期
            count: 数据条数

        Returns:
            K线数据DataFrame
        """
        try:
            if symbol is None:
                symbol = self.current_symbol

            if not symbol:
                raise ValueError("未设置交易标的")

            # 从统一数据管理器获取数据
            from .services.unified_data_manager import get_unified_data_manager
            data_manager = get_unified_data_manager()

            if data_manager:
                kdata = data_manager.get_kdata(symbol, period, count)
                if symbol == self.current_symbol:
                    self.current_kdata = kdata
                return kdata
            else:
                logger.error("无法获取统一数据管理器")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"加载K线数据失败: {e}")
            return pd.DataFrame()

    def add_signal(self, signal: TradingSignal):
        """
        添加交易信号

        Args:
            signal: 交易信号
        """
        try:
            # 验证信号
            if not self._validate_signal(signal):
                logger.warning(f"信号验证失败: {signal}")
                return False

            # 添加信号
            self.signals.append(signal)

            # 发送信号事件
            from .events import SignalGeneratedEvent
            self.event_bus.publish(SignalGeneratedEvent(signal))

            logger.info(f"添加交易信号: {signal.symbol} {signal.signal_type.value}")
            return True

        except Exception as e:
            logger.error(f"添加交易信号失败: {e}")
            return False

    def execute_signal(self, signal: TradingSignal) -> bool:
        """
        执行交易信号

        Args:
            signal: 交易信号

        Returns:
            是否执行成功
        """
        try:
            # 风险检查
            if not self._risk_check(signal):
                logger.warning(f"风险检查未通过: {signal}")
                return False

            # 执行交易
            if signal.signal_type == SignalType.BUY:
                return self._execute_buy(signal)
            elif signal.signal_type == SignalType.SELL:
                return self._execute_sell(signal)
            else:
                logger.info(f"持有信号，无需执行: {signal}")
                return True

        except Exception as e:
            logger.error(f"执行交易信号失败: {e}")
            return False

    def _execute_buy(self, signal: TradingSignal) -> bool:
        """执行买入信号"""
        try:
            symbol = signal.symbol
            price = signal.price
            volume = signal.volume

            # 计算交易成本
            cost = self._calculate_cost(price, volume, is_buy=True)
            total_cost = price * volume + cost

            # 更新仓位
            if symbol in self.positions:
                position = self.positions[symbol]
                if position.position_type == PositionType.LONG:
                    # 加仓
                    new_quantity = position.quantity + volume
                    new_avg_price = ((position.avg_price * position.quantity) +
                                     (price * volume)) / new_quantity
                    position.quantity = new_quantity
                    position.avg_price = new_avg_price
                else:
                    # 平空开多
                    position.position_type = PositionType.LONG
                    position.quantity = volume
                    position.avg_price = price
            else:
                # 新开仓
                self.positions[symbol] = Position(
                    symbol=symbol,
                    position_type=PositionType.LONG,
                    quantity=volume,
                    avg_price=price,
                    current_price=price
                )

            # 发布交易执行事件
            self._publish_trade_executed_event(signal, "buy", volume, price)

            logger.info(f"执行买入: {symbol} {volume}@{price}")
            return True

        except Exception as e:
            logger.error(f"执行买入失败: {e}")
            return False

    def _execute_sell(self, signal: TradingSignal) -> bool:
        """执行卖出信号"""
        try:
            symbol = signal.symbol
            price = signal.price
            volume = signal.volume

            if symbol not in self.positions:
                logger.warning(f"无持仓，无法卖出: {symbol}")
                return False

            position = self.positions[symbol]

            if position.quantity < volume:
                logger.warning(f"持仓不足，无法卖出: {symbol} 持仓{position.quantity} 卖出{volume}")
                return False

            # 计算交易成本
            cost = self._calculate_cost(price, volume, is_buy=False)

            # 计算已实现盈亏
            realized_pnl = (price - position.avg_price) * volume - cost
            position.realized_pnl += realized_pnl

            # 更新仓位
            position.quantity -= volume
            if position.quantity == 0:
                position.position_type = PositionType.EMPTY

            # 发布交易执行事件
            self._publish_trade_executed_event(signal, "sell", volume, price, realized_pnl)

            logger.info(f"执行卖出: {symbol} {volume}@{price} 盈亏:{realized_pnl:.2f}")
            return True

        except Exception as e:
            logger.error(f"执行卖出失败: {e}")
            return False

    def _calculate_cost(self, price: float, volume: int, is_buy: bool) -> float:
        """计算交易成本"""
        # 佣金
        commission = max(price * volume * self.commission_rate, self.min_commission)

        # 印花税（仅卖出时收取）
        stamp_tax = 0.0
        if not is_buy:
            stamp_tax = price * volume * self.stamp_tax_rate

        return commission + stamp_tax

    def _validate_signal(self, signal: TradingSignal) -> bool:
        """验证交易信号"""
        if not signal.symbol:
            return False
        if signal.price <= 0:
            return False
        if signal.volume < 0:
            return False
        return True

    def _risk_check(self, signal: TradingSignal) -> bool:
        """风险检查"""
        # 检查单个股票仓位限制
        if signal.symbol in self.positions:
            position = self.positions[signal.symbol]
            if signal.signal_type == SignalType.BUY:
                new_value = (position.quantity + signal.volume) * signal.price
                if new_value > self.max_single_position:
                    logger.warning(f"超过单个股票最大仓位限制: {new_value}")
                    return False

        # 检查总仓位限制
        total_value = sum(pos.market_value for pos in self.positions.values())
        if signal.signal_type == SignalType.BUY:
            new_total = total_value + signal.volume * signal.price
            if new_total > self.max_position_size:
                logger.warning(f"超过总仓位限制: {new_total}")
                return False

        return True

    def _publish_trade_executed_event(self, signal: TradingSignal, action: str, 
                                       volume: int, price: float, realized_pnl: float = 0.0):
        """发布交易执行事件"""
        try:
            event = TradeExecutedEvent(
                symbol=signal.symbol,
                action=action,
                quantity=volume,
                price=price,
                commission=self._calculate_cost(price, volume, is_buy=(action == "buy")),
                realized_pnl=realized_pnl,
                timestamp=datetime.now(),
                signal_id=str(signal.timestamp.timestamp()) if signal.timestamp else None
            )
            self.event_bus.publish(event)
            logger.debug(f"发布交易执行事件: {signal.symbol} {action} {volume}@{price}")
        except Exception as e:
            logger.warning(f"发布交易执行事件失败: {e}")

    def _publish_position_updated_event(self, symbol: str, position: Position):
        """发布仓位更新事件"""
        try:
            event = PositionUpdatedEvent(
                symbol=symbol,
                position_type=position.position_type.name,
                quantity=position.quantity,
                avg_price=position.avg_price,
                current_price=position.current_price,
                unrealized_pnl=position.unrealized_pnl,
                realized_pnl=position.realized_pnl,
                timestamp=position.timestamp
            )
            self.event_bus.publish(event)
            logger.debug(f"发布仓位更新事件: {symbol} {position.position_type.name} {position.quantity}")
        except Exception as e:
            logger.warning(f"发布仓位更新事件失败: {e}")

    def update_positions(self, prices: Dict[str, float]):
        """
        更新持仓价格

        Args:
            prices: 股票代码到价格的映射
        """
        try:
            for symbol, position in self.positions.items():
                if symbol in prices:
                    position.update_price(prices[symbol])

        except Exception as e:
            logger.error(f"更新持仓价格失败: {e}")

    def get_position(self, symbol: str) -> Optional[Position]:
        """
        获取持仓信息

        Args:
            symbol: 股票代码

        Returns:
            持仓信息，如果没有持仓则返回None
        """
        return self.positions.get(symbol)

    def get_all_positions(self) -> Dict[str, Position]:
        """获取所有持仓"""
        return self.positions.copy()

    def get_portfolio_value(self) -> float:
        """获取组合总市值"""
        return sum(pos.market_value for pos in self.positions.values())

    def get_total_pnl(self) -> float:
        """获取总盈亏"""
        return sum(pos.unrealized_pnl + pos.realized_pnl for pos in self.positions.values())

    def clear_positions(self):
        """清空所有持仓"""
        self.positions.clear()
        logger.info("清空所有持仓")

    def get_signals(self, symbol: str = None, limit: int = 100) -> List[TradingSignal]:
        """
        获取交易信号

        Args:
            symbol: 股票代码，如果为None则返回所有信号
            limit: 返回信号数量限制

        Returns:
            交易信号列表
        """
        signals = self.signals

        if symbol:
            signals = [s for s in signals if s.symbol == symbol]

        # 按时间倒序排列
        signals = sorted(signals, key=lambda x: x.timestamp, reverse=True)

        return signals[:limit]

    def cleanup(self):
        """清理资源"""
        try:
            self.positions.clear()
            self.signals.clear()
            logger.info("交易引擎资源清理完成")

        except Exception as e:
            logger.error(f"交易引擎清理失败: {e}")

# 全局交易引擎实例
_global_engine = None

def get_trading_engine() -> Optional[TradingEngine]:
    """获取全局交易引擎实例"""
    global _global_engine
    return _global_engine

def initialize_trading_engine(service_container: ServiceContainer, event_bus: EventBus) -> TradingEngine:
    """初始化全局交易引擎"""
    global _global_engine
    if _global_engine is None:
        _global_engine = TradingEngine(service_container, event_bus)
    return _global_engine

def cleanup_trading_engine():
    """清理全局交易引擎"""
    global _global_engine
    if _global_engine:
        _global_engine.cleanup()
        _global_engine = None
