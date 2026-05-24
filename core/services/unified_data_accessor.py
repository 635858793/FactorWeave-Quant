from loguru import logger
"""
统一数据访问适配器

提供统一的数据访问接口，替代UI层和其他组件的直接FactorWeave-Quant调用。
所有数据访问都通过插件系统进行，确保架构一致性。
"""

import pandas as pd
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from .asset_service import AssetService
from ..utils.data_standardizer import DataStandardizer
from ..plugin_types import AssetType, DataType
from ..tet_data_pipeline import StandardQuery


class UnifiedDataAccessor:
    """
    统一数据访问适配器

    提供简化的数据访问接口，内部通过插件系统获取数据。
    用于替代UI层和其他组件的直接数据源调用。
    """

    def __init__(self, asset_service: AssetService = None, data_standardizer: DataStandardizer = None):
        """
        初始化统一数据访问器

        Args:
            asset_service: 资产服务实例
            data_standardizer: 数据标准化器实例
        """
        self.logger = logger.bind(module=self.__class__.__name__)
        self.asset_service = asset_service
        self.data_standardizer = data_standardizer
        
        # 如果没有提供服务，尝试从服务容器获取
        if not self.asset_service or not self.data_standardizer:
            self._init_services_from_container()

    def _init_services_from_container(self):
        """从服务容器初始化服务"""
        try:
            from ..containers.service_container import get_service_container
            container = get_service_container()

            if container:
                if not self.asset_service:
                    self.asset_service = container.get('AssetService')
                if not self.data_standardizer:
                    try:
                        self.data_standardizer = container.get('DataStandardizer')
                    except Exception:
                        # 兼容旧版本：如果没有DataStandardizer，则使用data_standardizer服务
                        self.data_standardizer = container.get('data_standardizer')

                self.logger.info("从服务容器初始化服务成功")
            else:
                self.logger.warning("服务容器不可用")

        except Exception as e:
            self.logger.error(f"从服务容器初始化服务失败: {e}")

    def get_stock_data(self, stock_code: str, period: str = 'D', count: int = 30) -> Optional[pd.DataFrame]:
        """
        获取股票K线数据

        Args:
            stock_code: 股票代码
            period: 数据周期 ('D', 'W', 'M', '1', '5', '15', '30', '60')
            count: 数据条数

        Returns:
            DataFrame: K线数据，包含open, high, low, close, volume等列
        """
        try:
            self.logger.info(f"获取股票数据: {stock_code}, period={period}, count={count}")

            if self.asset_service:
                # 通过资产服务获取历史数据
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=count*2)).strftime('%Y-%m-%d')  # 预留更多天数

                df = self.asset_service.get_historical_data(
                    symbol=stock_code,
                    asset_type=AssetType.STOCK_A,
                    start_date=start_date,
                    end_date=end_date,
                    period=period
                )

                if df is not None and not df.empty:
                    # 限制返回条数
                    if len(df) > count:
                        df = df.tail(count)

                    self.logger.info(f"通过资产服务获取股票数据成功: {len(df)} 条记录")
                    return df
                else:
                    self.logger.warning("资产服务返回空数据")

            elif self.data_standardizer:
                # 使用数据标准化器
                df = self.data_standardizer.get_stock_data(stock_code, period, count)
                if df is not None and not df.empty:
                    self.logger.info(f"通过数据标准化器获取股票数据成功: {len(df)} 条记录")
                    return df
                else:
                    self.logger.warning("数据标准化器返回空数据")

            self.logger.error("无可用的数据服务")
            return None

        except Exception as e:
            self.logger.error(f"获取股票数据失败: {e}")
            return None

    def get_stock_list(self, market: str = 'all') -> List[Dict[str, Any]]:
        """
        获取股票列表

        Args:
            market: 市场代码 ('all', 'sh', 'sz', 'bj')

        Returns:
            List[Dict]: 股票列表
        """
        try:
            self.logger.info(f"获取股票列表: market={market}")

            if self.asset_service:
                # 通过资产服务获取股票列表
                stock_list = self.asset_service.get_asset_list(AssetType.STOCK_A, market=market)

                if stock_list:
                    self.logger.info(f"通过资产服务获取股票列表成功: {len(stock_list)} 只股票")
                    return stock_list
                else:
                    self.logger.warning("资产服务返回空股票列表")

            elif self.data_standardizer:
                # 使用数据标准化器获取股票列表
                df = self.data_standardizer.get_stock_list(market)
                if df is not None and not df.empty:
                    stock_list = df.to_dict('records')
                    self.logger.info(f"通过数据标准化器获取股票列表成功: {len(stock_list)} 只股票")
                    return stock_list
                else:
                    self.logger.warning("数据标准化器返回空股票列表")

            self.logger.error("无可用的数据服务")
            return []

        except Exception as e:
            self.logger.error(f"获取股票列表失败: {e}")
            return []

    def get_stock_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票基本信息

        Args:
            stock_code: 股票代码

        Returns:
            Dict: 股票基本信息
        """
        try:
            self.logger.info(f"获取股票信息: {stock_code}")

            # 从股票列表中查找
            stock_list = self.get_stock_list()
            for stock in stock_list:
                if stock.get('code') == stock_code or stock.get('symbol') == stock_code:
                    self.logger.info(f"找到股票信息: {stock.get('name', 'Unknown')}")
                    return stock

            self.logger.warning(f"未找到股票信息: {stock_code}")
            return None

        except Exception as e:
            self.logger.error(f"获取股票信息失败: {e}")
            return None

    def is_stock_valid(self, stock_code: str) -> bool:
        """
        检查股票代码是否有效

        Args:
            stock_code: 股票代码

        Returns:
            bool: 是否有效
        """
        try:
            stock_info = self.get_stock_info(stock_code)
            return stock_info is not None
        except Exception as e:
            self.logger.error(f"检查股票有效性失败: {e}")
            return False

    def get_data_source_status(self) -> Dict[str, str]:
        """
        获取数据源状态

        Returns:
            Dict: 数据源状态信息
        """
        status = {}
        
        if self.asset_service:
            status['asset_service'] = 'available'
        else:
            status['asset_service'] = 'unavailable'
            
        if self.data_standardizer:
            status['data_standardizer'] = 'available'
        else:
            status['data_standardizer'] = 'unavailable'
            
        return status