"""
基本面数据工厂类

根据资产类型创建相应的基本面数据对象，提供统一的基本面数据创建接口
作者：FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

from datetime import date
from typing import Dict, Any, Type, Optional

from loguru import logger

from core.fundamental_data.fundamental_data_base import FundamentalData
from core.fundamental_data.stock_fundamental_data import StockFundamentalData
from core.fundamental_data.futures_fundamental_data import FuturesFundamentalData
from core.fundamental_data.crypto_fundamental_data import CryptoFundamentalData
from core.plugin_types import AssetType


class FundamentalDataFactory:
    """基本面数据工厂类"""

    _registry: Dict[AssetType, Type[FundamentalData]] = {
        AssetType.STOCK_A: StockFundamentalData,
        AssetType.STOCK_B: StockFundamentalData,
        AssetType.STOCK_H: StockFundamentalData,
        AssetType.STOCK_US: StockFundamentalData,
        AssetType.STOCK_HK: StockFundamentalData,
        AssetType.FUTURES: FuturesFundamentalData,
        AssetType.CRYPTO: CryptoFundamentalData,
    }

    @classmethod
    def create(cls, asset_type: AssetType, symbol: str, data_date: date, raw_data: Dict[str, Any]) -> Optional[FundamentalData]:
        """
        创建基本面数据对象

        Args:
            asset_type: 资产类型
            symbol: 资产代码
            data_date: 数据日期
            raw_data: 原始数据

        Returns:
            基本面数据对象，如果不支持则返回None
        """
        data_class = cls._registry.get(asset_type)
        if data_class:
            try:
                return data_class(symbol, data_date, raw_data)
            except Exception as e:
                logger.error(f"创建基本面数据失败: {asset_type}, {symbol}, 错误: {e}")
                return None
        else:
            logger.warning(f"不支持的资产类型: {asset_type}")
            return None

    @classmethod
    def register(cls, asset_type: AssetType, data_class: Type[FundamentalData]) -> None:
        """
        注册基本面数据类

        Args:
            asset_type: 资产类型
            data_class: 基本面数据类
        """
        cls._registry[asset_type] = data_class
        logger.info(f"注册基本面数据类: {asset_type} -> {data_class.__name__}")

    @classmethod
    def get_supported_types(cls) -> List[AssetType]:
        """
        获取支持的资产类型

        Returns:
            支持的资产类型列表
        """
        return list(cls._registry.keys())
