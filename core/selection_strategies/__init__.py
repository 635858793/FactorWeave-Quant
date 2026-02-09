"""
选股策略模块

提供资产类型特定的选股策略，支持多种策略类型
作者：FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

from .selection_strategy_base import (
    SelectionStrategyBase,
    SelectionCriteria,
    SelectionResult,
    StrategyType
)
from .stock_value_strategy import StockValueStrategy
from .futures_momentum_strategy import FuturesMomentumStrategy
from .crypto_growth_strategy import CryptoGrowthStrategy

__all__ = [
    'SelectionStrategyBase',
    'SelectionCriteria',
    'SelectionResult',
    'StrategyType',
    'StockValueStrategy',
    'FuturesMomentumStrategy',
    'CryptoGrowthStrategy'
]
