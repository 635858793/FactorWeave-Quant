"""
基本面数据抽象层

提供统一的基本面数据接口，支持多种资产类型的基本面数据获取、处理和评分
作者：FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

from .fundamental_data_base import FundamentalDataBase, FundamentalScoreLevel
from .stock_fundamental_data import StockFundamentalData
from .futures_fundamental_data import FuturesFundamentalData
from .crypto_fundamental_data import CryptoFundamentalData
from .fundamental_data_factory import FundamentalDataFactory

__all__ = [
    'FundamentalDataBase',
    'FundamentalScoreLevel',
    'StockFundamentalData',
    'FuturesFundamentalData',
    'CryptoFundamentalData',
    'FundamentalDataFactory'
]
