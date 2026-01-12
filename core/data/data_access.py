from loguru import logger
"""
数据访问门面

提供统一的数据访问入口，隐藏底层仓库的复杂性。
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd

from .models import StockInfo, KlineData, MarketData, QueryParams
from .repository import StockRepository, KlineRepository, MarketRepository


class DataAccess:
    """
    数据访问门面类

    提供统一的数据访问接口，内部使用仓库模式管理不同类型的数据。
    """

    def __init__(self, data_manager=None, uni_plugin_manager=None):
        """
        初始化数据访问层

        Args:
            data_manager: 数据管理器实例（可选，向后兼容）
            uni_plugin_manager: 统一插件数据管理器（优先使用）
        """
        from core.services.uni_plugin_data_manager import UniPluginDataManager
        
        # 设置数据管理器
        self.data_manager = data_manager
        
        # 优先使用UniPluginDataManager
        self.uni_plugin_manager = uni_plugin_manager

        # 初始化各个仓库 - 传入UniPluginDataManager
        self.stock_repo = StockRepository(data_manager, uni_plugin_manager)
        self.kline_repo = KlineRepository(asset_service=data_manager, uni_plugin_manager=uni_plugin_manager)
        self.market_repo = MarketRepository(data_manager, uni_plugin_manager)

        # 连接状态
        self._connected = False
        
        # 初始化logger
        self.logger = logger.bind(module=self.__class__.__name__)
    def connect(self) -> bool:
        """连接所有数据源"""
        try:
            stock_connected = self.stock_repo.connect()
            kline_connected = self.kline_repo.connect()
            market_connected = self.market_repo.connect()

            self._connected = stock_connected and kline_connected and market_connected

            if self._connected:
                self.logger.info("Data access layer connected successfully")
            else:
                self.logger.warning("Some repositories failed to connect")

            return self._connected

        except Exception as e:
            self.logger.error(f"Failed to connect data access layer: {e}")
            return False

    def disconnect(self) -> None:
        """断开所有数据源连接"""
        try:
            self.stock_repo.disconnect()
            self.kline_repo.disconnect()
            self.market_repo.disconnect()
            self._connected = False
            self.logger.info("Data access layer disconnected")

        except Exception as e:
            self.logger.error(f"Failed to disconnect data access layer: {e}")

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected

    # 股票相关方法
    def get_stock_info(self, stock_code: str) -> Optional[StockInfo]:
        """
        获取股票基本信息

        Args:
            stock_code: 股票代码

        Returns:
            股票信息对象或None
        """
        if not self._connected:
            self.connect()

        return self.stock_repo.get_stock_info(stock_code)

    def get_stock_list(self, market: Optional[str] = None) -> List[StockInfo]:
        """
        获取股票列表

        Args:
            market: 市场代码（可选）

        Returns:
            股票信息列表
        """
        if not self._connected:
            self.connect()

        return self.stock_repo.get_stock_list(market)

    def search_stocks(self, keyword: str) -> List[StockInfo]:
        """
        搜索股票

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的股票信息列表
        """
        if not self._connected:
            self.connect()

        return self.stock_repo.search_stocks(keyword)

    # K线数据相关方法
    def get_kline_data(self, stock_code: str, period: str = 'D',
                       count: Optional[int] = None,
                       start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None) -> Optional[KlineData]:
        """
        获取K线数据

        Args:
            stock_code: 股票代码
            period: 周期（1m/5m/15m/30m/1H/D/W/M）
            count: 数据条数
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            K线数据对象或None
        """
        if not self._connected:
            self.connect()

        params = QueryParams(
            stock_code=stock_code,
            period=period,
            count=count,
            start_date=start_date,
            end_date=end_date
        )

        return self.kline_repo.get_kline_data(params)

    def get_latest_price(self, stock_code: str) -> Optional[float]:
        """
        获取最新价格

        Args:
            stock_code: 股票代码

        Returns:
            最新价格或None
        """
        if not self._connected:
            self.connect()

        return self.kline_repo.get_latest_price(stock_code)

    # 兼容性方法（保持与原有接口一致）
    def get_kdata(self, stock_code: str, period: str = 'D', count: int = 365) -> pd.DataFrame:
        """
        获取K线数据（兼容性方法）

        Args:
            stock_code: 股票代码
            period: 周期
            count: 数据条数

        Returns:
            K线数据DataFrame
        """
        kline_data = self.get_kline_data(stock_code, period, count)
        if kline_data and kline_data.data is not None:
            return kline_data.data

        # 返回空DataFrame保持兼容性
        return pd.DataFrame()

    # 市场数据相关方法
    def get_market_data(self, index_code: str, date: Optional[datetime] = None) -> Optional[MarketData]:
        """
        获取市场数据

        Args:
            index_code: 指数代码
            date: 日期（可选）

        Returns:
            市场数据对象或None
        """
        if not self._connected:
            self.connect()

        return self.market_repo.get_market_data(index_code, date)

    def get_market_indices(self) -> List[str]:
        """
        获取市场指数列表

        Returns:
            指数代码列表
        """
        if not self._connected:
            self.connect()

        return self.market_repo.get_market_indices()

    # 批量操作方法
    def get_multiple_kline_data(self, stock_codes: List[str],
                                period: str = 'D',
                                count: int = 365) -> Dict[str, KlineData]:
        """
        批量获取多只股票的K线数据

        Args:
            stock_codes: 股票代码列表
            period: 周期
            count: 数据条数

        Returns:
            股票代码到K线数据的映射
        """
        results = {}

        for stock_code in stock_codes:
            try:
                kline_data = self.get_kline_data(stock_code, period, count)
                if kline_data:
                    results[stock_code] = kline_data
            except Exception as e:
                self.logger.error(
                    f"Failed to get kline data for {stock_code}: {e}")

        return results

    def get_multiple_latest_prices(self, stock_codes: List[str]) -> Dict[str, float]:
        """
        批量获取多只股票的最新价格

        Args:
            stock_codes: 股票代码列表

        Returns:
            股票代码到最新价格的映射
        """
        results = {}

        for stock_code in stock_codes:
            try:
                price = self.get_latest_price(stock_code)
                if price is not None:
                    results[stock_code] = price
            except Exception as e:
                self.logger.error(
                    f"Failed to get latest price for {stock_code}: {e}")

        return results

    # 缓存管理方法
    def clear_cache(self) -> None:
        """清除所有缓存"""
        try:
            self.stock_repo._stock_cache.clear()
            self.kline_repo._cache.clear()
            self.market_repo._market_cache.clear()
            self.logger.info("All caches cleared")
        except Exception as e:
            self.logger.error(f"Failed to clear cache: {e}")

    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        return {
            'stock_cache_size': len(self.stock_repo._stock_cache),
            'kline_cache_size': len(self.kline_repo._cache),
            'market_cache_size': len(self.market_repo._market_cache)
        }
