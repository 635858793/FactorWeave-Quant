from typing import Dict, Any
from datetime import datetime
from loguru import logger

from core.strategy.base_strategy import StrategySignal
from core.trading_engine import TradingSignal
from core.plugin_types import AssetType


def convert_strategy_to_trading_signal(
    strategy_signal: StrategySignal,
    symbol: str = "",
    asset_type: AssetType = AssetType.STOCK_A,
) -> TradingSignal:
    """
    将 StrategySignal 转换为 TradingSignal

    StrategySignal (base_strategy.py) 与 TradingSignal (trading_engine.py)
    是两种独立的 dataclass，字段不完全对应。本函数提供桥接转换。

    字段映射：
      - timestamp, signal_type, price, confidence, reason → 直接映射
      - metadata → 直接映射，并将 strategy_signal 独有字段（strategy_name,
        stop_loss, take_profit, position_size）存入 metadata 中

    缺失字段处理（StrategySignal 中不存在的字段）：
      - symbol: 必须由调用方提供，默认为空字符串
      - volume: 默认为 0
      - asset_type: 默认为 AssetType.STOCK_A
    """
    enriched_metadata: Dict[str, Any] = dict(strategy_signal.metadata) if strategy_signal.metadata else {}
    enriched_metadata["strategy_name"] = strategy_signal.strategy_name

    if strategy_signal.stop_loss is not None:
        enriched_metadata["stop_loss"] = strategy_signal.stop_loss
    if strategy_signal.take_profit is not None:
        enriched_metadata["take_profit"] = strategy_signal.take_profit
    if strategy_signal.position_size is not None:
        enriched_metadata["position_size"] = strategy_signal.position_size

    if not symbol:
        if not hasattr(AssetType, 'get_identifier') or not asset_type:
            raise ValueError(
                f"StrategySignal 转 TradingSignal 失败: symbol 为空且 asset_type 未提供有效备选标识。"
                f"策略 '{strategy_signal.strategy_name}' 无法生成有效的交易信号。"
                "请在调用 convert_strategy_to_trading_signal 时传入 symbol 参数。"
            )
        logger.warning(
            f"StrategySignal 转 TradingSignal: symbol 未提供，"
            f"策略 '{strategy_signal.strategy_name}' 的信号将使用 asset_type={asset_type.value} 作为标识。"
            "请在调用 convert_strategy_to_trading_signal 时传入 symbol 参数。"
        )

    volume = int(strategy_signal.position_size) if strategy_signal.position_size is not None else 100

    reason_parts = [strategy_signal.reason] if strategy_signal.reason else []
    if strategy_signal.stop_loss is not None:
        reason_parts.append(f"止损:{strategy_signal.stop_loss:.2f}")
    if strategy_signal.take_profit is not None:
        reason_parts.append(f"止盈:{strategy_signal.take_profit:.2f}")
    enriched_reason = "; ".join(reason_parts)

    return TradingSignal(
        symbol=symbol,
        signal_type=strategy_signal.signal_type,
        timestamp=strategy_signal.timestamp,
        price=strategy_signal.price,
        volume=volume,
        confidence=strategy_signal.confidence,
        reason=enriched_reason,
        asset_type=asset_type,
        metadata=enriched_metadata,
    )