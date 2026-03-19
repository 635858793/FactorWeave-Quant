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
from .plugin_types import AssetType
from analysis.pattern_base import SignalType

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
    asset_type: AssetType = AssetType.STOCK_A
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

        # 当前资产类型
        self.current_asset_type: AssetType = AssetType.STOCK_A

        # 配置参数（按资产类型）
        self.commission_rates = {
            AssetType.STOCK_A: 0.0003,      # A股佣金费率
            AssetType.STOCK_B: 0.0003,      # B股佣金费率
            AssetType.STOCK_H: 0.0003,      # H股佣金费率
            AssetType.STOCK_US: 0.001,       # 美股佣金费率
            AssetType.STOCK_HK: 0.001,       # 港股佣金费率
            AssetType.FUTURES: 0.0001,      # 期货佣金费率
            AssetType.CRYPTO: 0.001,        # 加密货币佣金费率
            AssetType.FOREX: 0.0001,       # 外汇佣金费率
            AssetType.BOND: 0.0002,        # 债券佣金费率
            AssetType.COMMODITY: 0.0001,   # 商品佣金费率
            AssetType.INDEX: 0.0003,       # 指数佣金费率
            AssetType.FUND: 0.0001,        # 基金佣金费率
            AssetType.OPTION: 0.001,        # 期权佣金费率
            AssetType.WARRANT: 0.001,       # 权证佣金费率
            AssetType.SECTOR: 0.0003,       # 板块佣金费率
            AssetType.INDUSTRY_SECTOR: 0.0003,  # 行业板块佣金费率
            AssetType.CONCEPT_SECTOR: 0.0003,  # 概念板块佣金费率
            AssetType.STYLE_SECTOR: 0.0003,    # 风格板块佣金费率
            AssetType.THEME_SECTOR: 0.0003,    # 主题板块佣金费率
            AssetType.MACRO: 0.0003,           # 宏观经济佣金费率
        }

        self.min_commissions = {
            AssetType.STOCK_A: 5.0,         # A股最小佣金
            AssetType.STOCK_B: 5.0,         # B股最小佣金
            AssetType.STOCK_H: 5.0,         # H股最小佣金
            AssetType.STOCK_US: 1.0,         # 美股最小佣金
            AssetType.STOCK_HK: 1.0,         # 港股最小佣金
            AssetType.FUTURES: 2.0,         # 期货最小佣金
            AssetType.CRYPTO: 1.0,          # 加密货币最小佣金
            AssetType.FOREX: 1.0,           # 外汇最小佣金
            AssetType.BOND: 2.0,             # 债券最小佣金
            AssetType.COMMODITY: 2.0,        # 商品最小佣金
            AssetType.INDEX: 5.0,           # 指数最小佣金
            AssetType.FUND: 1.0,            # 基金最小佣金
            AssetType.OPTION: 1.0,           # 期权最小佣金
            AssetType.WARRANT: 1.0,          # 权证最小佣金
            AssetType.SECTOR: 5.0,           # 板块最小佣金
            AssetType.INDUSTRY_SECTOR: 5.0,  # 行业板块最小佣金
            AssetType.CONCEPT_SECTOR: 5.0,  # 概念板块最小佣金
            AssetType.STYLE_SECTOR: 5.0,    # 风格板块最小佣金
            AssetType.THEME_SECTOR: 5.0,    # 主题板块最小佣金
            AssetType.MACRO: 5.0,           # 宏观经济最小佣金
        }

        self.stamp_tax_rates = {
            AssetType.STOCK_A: 0.001,       # A股印花税率
            AssetType.STOCK_B: 0.001,       # B股印花税率
            AssetType.STOCK_H: 0.001,       # H股印花税率
            AssetType.STOCK_US: 0.0,         # 美股印花税率
            AssetType.STOCK_HK: 0.001,       # 港股印花税率
            AssetType.FUTURES: 0.0,         # 期货印花税率
            AssetType.CRYPTO: 0.0,          # 加密货币印花税率
            AssetType.FOREX: 0.0,           # 外汇印花税率
            AssetType.BOND: 0.0,             # 债券印花税率
            AssetType.COMMODITY: 0.0,        # 商品印花税率
            AssetType.INDEX: 0.0,           # 指数印花税率
            AssetType.FUND: 0.0,             # 基金印花税率
            AssetType.OPTION: 0.0,           # 期权印花税率
            AssetType.WARRANT: 0.0,          # 权证印花税率
            AssetType.SECTOR: 0.0,          # 板块印花税率
            AssetType.INDUSTRY_SECTOR: 0.0,  # 行业板块印花税率
            AssetType.CONCEPT_SECTOR: 0.0,  # 概念板块印花税率
            AssetType.STYLE_SECTOR: 0.0,    # 风格板块印花税率
            AssetType.THEME_SECTOR: 0.0,    # 主题板块印花税率
            AssetType.MACRO: 0.0,           # 宏观经济印花税率
        }

        # 风险控制参数（按资产类型）
        self.max_single_positions = {
            AssetType.STOCK_A: 100000,     # A股单个股票最大仓位
            AssetType.STOCK_B: 100000,     # B股单个股票最大仓位
            AssetType.STOCK_H: 100000,     # H股单个股票最大仓位
            AssetType.STOCK_US: 50000,      # 美股单个股票最大仓位
            AssetType.STOCK_HK: 50000,      # 港股单个股票最大仓位
            AssetType.FUTURES: 500000,    # 期货单个合约最大仓位
            AssetType.CRYPTO: 10000,      # 加密货币单个币种最大仓位
            AssetType.FOREX: 100000,      # 外汇单个币种最大仓位
            AssetType.BOND: 500000,       # 债券单个债券最大仓位
            AssetType.COMMODITY: 500000,  # 商品单个合约最大仓位
            AssetType.INDEX: 100000,      # 指数单个指数最大仓位
            AssetType.FUND: 100000,       # 基金单个基金最大仓位
            AssetType.OPTION: 50000,      # 期权单个合约最大仓位
            AssetType.WARRANT: 50000,      # 权证单个权证最大仓位
            AssetType.SECTOR: 200000,     # 板块单个板块最大仓位
            AssetType.INDUSTRY_SECTOR: 200000,  # 行业板块单个板块最大仓位
            AssetType.CONCEPT_SECTOR: 200000,  # 概念板块单个板块最大仓位
            AssetType.STYLE_SECTOR: 200000,    # 风格板块单个板块最大仓位
            AssetType.THEME_SECTOR: 200000,    # 主题板块单个板块最大仓位
            AssetType.MACRO: 500000,           # 宏观经济单个指标最大仓位
        }

        # 最小交易单位（按资产类型）
        self.min_trade_units = {
            AssetType.STOCK_A: 100,         # A股最小交易单位（1手=100股）
            AssetType.STOCK_B: 100,         # B股最小交易单位
            AssetType.STOCK_H: 100,         # H股最小交易单位
            AssetType.STOCK_US: 1,          # 美股最小交易单位
            AssetType.STOCK_HK: 100,        # 港股最小交易单位
            AssetType.FUTURES: 1,          # 期货最小交易单位（1手）
            AssetType.CRYPTO: 0.001,       # 加密货币最小交易单位
            AssetType.FOREX: 1000,         # 外汇最小交易单位
            AssetType.BOND: 1000,          # 债券最小交易单位
            AssetType.COMMODITY: 1,        # 商品最小交易单位
            AssetType.INDEX: 1,            # 指数最小交易单位
            AssetType.FUND: 100,           # 基金最小交易单位
            AssetType.OPTION: 1,           # 期权最小交易单位
            AssetType.WARRANT: 100,        # 权证最小交易单位
            AssetType.SECTOR: 100,         # 板块最小交易单位
            AssetType.INDUSTRY_SECTOR: 100,  # 行业板块最小交易单位
            AssetType.CONCEPT_SECTOR: 100,  # 概念板块最小交易单位
            AssetType.STYLE_SECTOR: 100,    # 风格板块最小交易单位
            AssetType.THEME_SECTOR: 100,    # 主题板块最小交易单位
            AssetType.MACRO: 1,            # 宏观经济最小交易单位
        }

        # 默认配置（向后兼容）
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

    def set_asset_type(self, asset_type: AssetType):
        """
        设置当前资产类型

        Args:
            asset_type: 资产类型
        """
        try:
            self.current_asset_type = asset_type
            logger.info(f"设置当前资产类型: {asset_type.value}")

        except Exception as e:
            logger.error(f"设置资产类型失败: {e}")
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
            asset_type = signal.asset_type if signal.asset_type else self.current_asset_type

            # 计算交易成本
            cost = self._calculate_cost(price, volume, is_buy=True, asset_type=asset_type)
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
            asset_type = signal.asset_type if signal.asset_type else self.current_asset_type

            if symbol not in self.positions:
                logger.warning(f"无持仓，无法卖出: {symbol}")
                return False

            position = self.positions[symbol]

            if position.quantity < volume:
                logger.warning(f"持仓不足，无法卖出: {symbol} 持仓{position.quantity} 卖出{volume}")
                return False

            # 计算交易成本
            cost = self._calculate_cost(price, volume, is_buy=False, asset_type=asset_type)

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

    def _calculate_cost(self, price: float, volume: int, is_buy: bool, asset_type: AssetType = None) -> float:
        """计算交易成本（支持资产类型）"""
        # 使用当前资产类型或指定的资产类型
        if asset_type is None:
            asset_type = self.current_asset_type
        else:
            asset_type = asset_type

        # 获取资产类型的配置
        commission_rate = self.commission_rates.get(asset_type, self.commission_rate)
        min_commission = self.min_commissions.get(asset_type, self.min_commission)
        stamp_tax_rate = self.stamp_tax_rates.get(asset_type, self.stamp_tax_rate)

        # 佣金
        commission = max(price * volume * commission_rate, min_commission)

        # 印花税（仅卖出时收取）
        stamp_tax = 0.0
        if not is_buy:
            stamp_tax = price * volume * stamp_tax_rate

        return commission + stamp_tax

    def _validate_signal(self, signal: TradingSignal) -> bool:
        """验证交易信号（支持资产类型）"""
        if not signal.symbol:
            return False
        if signal.price <= 0:
            return False
        if signal.volume < 0:
            return False

        # 验证最小交易单位
        asset_type = signal.asset_type if signal.asset_type else self.current_asset_type
        min_trade_unit = self.min_trade_units.get(asset_type, 1)
        
        if signal.volume % min_trade_unit != 0:
            logger.warning(f"交易数量不符合最小交易单位: {signal.volume}，最小单位: {min_trade_unit} ({asset_type.value})")
            return False

        return True

    def _risk_check(self, signal: TradingSignal) -> bool:
        """风险检查（支持资产类型）"""
        asset_type = signal.asset_type if signal.asset_type else self.current_asset_type

        # 获取资产类型的最大仓位限制
        max_single_position = self.max_single_positions.get(asset_type, self.max_single_position)

        # 检查单个股票仓位限制
        if signal.symbol in self.positions:
            position = self.positions[signal.symbol]
            if signal.signal_type == SignalType.BUY:
                new_value = (position.quantity + signal.volume) * signal.price
                if new_value > max_single_position:
                    logger.warning(f"超过单个{asset_type.value}最大仓位限制: {new_value}")
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
            asset_type = signal.asset_type if signal.asset_type else self.current_asset_type
            event = TradeExecutedEvent(
                symbol=signal.symbol,
                action=action,
                quantity=volume,
                price=price,
                commission=self._calculate_cost(price, volume, is_buy=(action == "buy"), asset_type=asset_type),
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
