from loguru import logger
"""
统一资产服务
提供OpenBB风格的统一资产访问接口，支持多种资产类型
借鉴OpenBB的Provider模式，适配FactorWeave-Quant现有服务架构
"""

from typing import List, Dict, Any, Optional, Union
import pandas as pd

from ..plugin_types import AssetType, DataType
from .unified_data_manager import UnifiedDataManager
from .stock_service import StockService
from ..tet_data_pipeline import StandardQuery, StandardData


class AssetService:
    """
    统一资产服务

    提供类似OpenBB的统一API接口：
    - asset_service.get_historical_data() ≈ obb.equity.price.historical()
    - asset_service.get_asset_list() ≈ obb.equity.search()
    - asset_service.get_real_time_data() ≈ obb.equity.price.quote()

    支持多种资产类型：股票、加密货币、期货、外汇等
    """

    def __init__(self,
                 unified_data_manager: UnifiedDataManager,
                 stock_service: StockService,
                 service_container):
        """
        初始化资产服务

        Args:
            unified_data_manager: 统一数据管理器
            stock_service: 股票服务
            service_container: 服务容器
        """
        self.unified_data_manager = unified_data_manager
        self.stock_service = stock_service
        self.service_container = service_container

        # 资产类型到服务的映射（用于优化特定资产类型的处理）
        self.asset_service_mapping = {
            AssetType.STOCK_A: self.stock_service,
            AssetType.INDEX: self.stock_service,  # 指数复用股票服务
            AssetType.FUND: self.stock_service,   # 基金复用股票服务
            # 其他资产类型通过UnifiedDataManager的TET管道处理
        }

        logger.info("AssetService初始化完成")

    def get_historical_data(self, symbol: str, asset_type: Union[AssetType, str],
                            start_date: str = None, end_date: str = None,
                            period: str = "D", provider: str = None, **kwargs) -> pd.DataFrame:
        """
        获取历史数据（OpenBB风格API）

        类似于：obb.equity.price.historical("AAPL", start_date="2024-01-01")

        Args:
            symbol: 交易代码
            asset_type: 资产类型（支持AssetType枚举或字符串）
            start_date: 开始日期
            end_date: 结束日期  
            period: 数据周期
            provider: 指定数据源
            **kwargs: 其他参数

        Returns:
            pd.DataFrame: 标准化的历史数据

        Examples:
            # 获取股票历史数据
            stock_data = asset_service.get_historical_data("000001", AssetType.STOCK_A)

            # 获取加密货币历史数据
            crypto_data = asset_service.get_historical_data("BTCUSDT", AssetType.CRYPTO)
        """
        try:
            # 确保asset_type是AssetType枚举
            if isinstance(asset_type, str):
                try:
                    asset_type = AssetType(asset_type)
                except ValueError:
                    logger.warning(f"无效的资产类型字符串: {asset_type}, 使用默认值: {AssetType.STOCK_A.value}")
                    asset_type = AssetType.STOCK_A
            
            logger.info(f" AssetService获取历史数据: {symbol} ({asset_type.value})")

            # 优先使用TET管道
            if self.unified_data_manager.tet_enabled:
                logger.info(f" AssetService使用TET模式: {symbol}")
                result = self.unified_data_manager.get_asset_data(
                    symbol=symbol,
                    asset_type=asset_type,
                    data_type=DataType.HISTORICAL_KLINE,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                    provider=provider,
                    **kwargs
                )
                if result is not None:
                    logger.info(f" AssetService TET模式成功: {symbol} | 记录数: {len(result)}")
                else:
                    logger.warning(f" AssetService TET模式返回空数据: {symbol}")
                return result
            else:
                logger.warning(f" TET模式未启用，降级到传统模式: {symbol}")

            # 降级到专用服务
            if asset_type in self.asset_service_mapping:
                service = self.asset_service_mapping[asset_type]
                if hasattr(service, 'get_stock_data'):
                    return service.get_stock_data(symbol, period, **kwargs)

            # 最后降级到UnifiedDataManager传统模式
            return self.unified_data_manager._legacy_get_stock_data(symbol, period, **kwargs)

        except Exception as e:
            logger.error(f"获取历史数据失败 {symbol}: {e}")
            return pd.DataFrame()

    def get_asset_list(self, asset_type: Union[AssetType, str],
                       market: str = None, **filters) -> List[Dict[str, Any]]:
        """
        获取资产列表（OpenBB风格API）

        类似于：obb.equity.search()

        Args:
            asset_type: 资产类型（支持AssetType枚举或字符串）
            market: 市场过滤
            **filters: 其他过滤条件

        Returns:
            List[Dict]: 标准化的资产列表

        Examples:
            # 获取股票列表
            stocks = asset_service.get_asset_list(AssetType.STOCK_A, market="上海")
            # 或使用字符串形式
            stocks = asset_service.get_asset_list("stock_a", market="上海")

            # 获取加密货币列表
            cryptos = asset_service.get_asset_list(AssetType.CRYPTO)
        """
        # 确保asset_type是AssetType枚举
        if isinstance(asset_type, str):
            try:
                asset_type = AssetType(asset_type)
            except ValueError:
                logger.warning(f"无效的资产类型字符串: {asset_type}, 使用默认值: {AssetType.STOCK_A.value}")
                asset_type = AssetType.STOCK_A
        
        try:
            logger.info(f"获取资产列表: {asset_type.value}")

            # 优先使用TET模式
            if self.unified_data_manager.tet_enabled:
                return self.unified_data_manager.get_asset_list(asset_type, market)

            # 降级到专用服务
            if asset_type in self.asset_service_mapping:
                service = self.asset_service_mapping[asset_type]
                if hasattr(service, 'get_stock_list'):
                    raw_data = service.get_stock_list()
                    return self._standardize_asset_list(raw_data, asset_type)

            # 最后降级
            return self.unified_data_manager._legacy_get_asset_list(asset_type, market)

        except Exception as e:
            logger.error(f"获取资产列表失败 {asset_type.value}: {e}")
            return []

    def get_real_time_data(self, symbols: List[str],
                           asset_type: AssetType) -> Dict[str, Any]:
        """
        获取实时数据（OpenBB风格API）

        类似于：obb.equity.price.quote(["AAPL", "MSFT"])

        Args:
            symbols: 交易代码列表
            asset_type: 资产类型

        Returns:
            Dict[str, Any]: 实时数据字典

        Examples:
            # 获取多只股票实时数据
            quotes = asset_service.get_real_time_data(["000001", "000002"], AssetType.STOCK_A)
        """
        try:
            self.logger.info(f"获取实时数据: {symbols} ({asset_type.value})")

            result = {}

            for symbol in symbols:
                try:
                    if self.unified_data_manager.tet_enabled:
                        data = self.unified_data_manager.get_asset_data(
                            symbol=symbol,
                            asset_type=asset_type,
                            data_type=DataType.REAL_TIME_QUOTE
                        )
                        if data is not None and not data.empty:
                            result[symbol] = data.iloc[-1].to_dict()

                except Exception as e:
                    self.logger.warning(f"获取 {symbol} 实时数据失败: {e}")
                    result[symbol] = None

            return result

        except Exception as e:
            self.logger.error(f"获取实时数据失败: {e}")
            return {}

    def get_market_list(self, asset_type: AssetType = None) -> List[Dict[str, Any]]:
        """
        获取市场列表

        Args:
            asset_type: 资产类型过滤

        Returns:
            List[Dict]: 市场信息列表
        """
        try:
            if self.unified_data_manager.tet_enabled and self.unified_data_manager.tet_pipeline:
                # 通过TET管道获取市场列表
                markets = []

                # 获取所有支持的资产类型的市场
                asset_types = [asset_type] if asset_type else [
                    AssetType.STOCK_A, AssetType.CRYPTO, AssetType.FUTURES, AssetType.FOREX
                ]

                for at in asset_types:
                    try:
                        # 通过数据源路由器获取支持该资产类型的市场
                        router = self.unified_data_manager.tet_pipeline.router
                        available_sources = router._get_available_sources(at)

                        for source_id in available_sources:
                            source = router.get_data_source(source_id)
                            if source and hasattr(source.plugin, 'get_market_list'):
                                source_markets = source.plugin.get_market_list()
                                markets.extend(source_markets)

                    except Exception as e:
                        logger.debug(f"获取 {at.value} 市场列表失败: {e}")

                return markets

            # 降级到默认市场列表
            return self._get_default_markets(asset_type)

        except Exception as e:
            logger.error(f"获取市场列表失败: {e}")
            return self._get_default_markets(asset_type)

    def _standardize_asset_list(self, raw_data: Any, asset_type: AssetType) -> List[Dict[str, Any]]:
        """
        标准化资产列表格式

        Args:
            raw_data: 原始资产数据
            asset_type: 资产类型

        Returns:
            List[Dict]: 标准化资产列表
        """
        if not raw_data:
            return []

        standardized = []

        try:
            # 处理不同格式的原始数据
            if isinstance(raw_data, pd.DataFrame):
                for _, row in raw_data.iterrows():
                    standardized.append({
                        'symbol': row.get('symbol', row.get('code', '')),
                        'name': row.get('name', row.get('名称', '')),
                        'asset_type': asset_type.value,
                        'market': row.get('market', row.get('市场', '')),
                        'status': 'active'
                    })
            elif isinstance(raw_data, list):
                for item in raw_data:
                    if isinstance(item, dict):
                        standardized.append({
                            'symbol': item.get('symbol', item.get('code', '')),
                            'name': item.get('name', item.get('名称', '')),
                            'asset_type': asset_type.value,
                            'market': item.get('market', item.get('市场', '')),
                            'status': 'active'
                        })

        except Exception as e:
            logger.error(f"标准化资产列表失败: {e}")

        return standardized

    def _get_default_markets(self, asset_type: AssetType = None) -> List[Dict[str, Any]]:
        """
        获取默认市场列表

        Args:
            asset_type: 资产类型过滤

        Returns:
            List[Dict]: 默认市场列表
        """
        default_markets = {
            AssetType.STOCK_A: [
                {'id': 'sh', 'name': '上海证券交易所', 'asset_type': 'STOCK'},
                {'id': 'sz', 'name': '深圳证券交易所', 'asset_type': 'STOCK'},
                {'id': 'bj', 'name': '北京证券交易所', 'asset_type': 'STOCK'}
            ],
            AssetType.CRYPTO: [
                {'id': 'binance', 'name': 'Binance', 'asset_type': 'CRYPTO'},
                {'id': 'coinbase', 'name': 'Coinbase', 'asset_type': 'CRYPTO'},
                {'id': 'okx', 'name': 'OKX', 'asset_type': 'CRYPTO'}
            ],
            AssetType.FUTURES: [
                {'id': 'shfe', 'name': '上海期货交易所', 'asset_type': 'FUTURES'},
                {'id': 'dce', 'name': '大连商品交易所', 'asset_type': 'FUTURES'},
                {'id': 'czce', 'name': '郑州商品交易所', 'asset_type': 'FUTURES'},
                {'id': 'cffex', 'name': '中国金融期货交易所', 'asset_type': 'FUTURES'}
            ],
            AssetType.FOREX: [
                {'id': 'forex_major', 'name': '主要货币对', 'asset_type': 'FOREX'},
                {'id': 'forex_minor', 'name': '次要货币对', 'asset_type': 'FOREX'},
                {'id': 'forex_exotic', 'name': '奇异货币对', 'asset_type': 'FOREX'}
            ]
        }

        if asset_type:
            return default_markets.get(asset_type, [])

        # 返回所有市场
        all_markets = []
        for markets in default_markets.values():
            all_markets.extend(markets)

        return all_markets

    def get_supported_asset_types(self) -> List[AssetType]:
        """
        获取支持的资产类型列表

        Returns:
            List[AssetType]: 支持的资产类型
        """
        try:
            if self.unified_data_manager.tet_enabled and self.unified_data_manager.tet_pipeline:
                # 通过TET管道查询所有支持的资产类型
                router = self.unified_data_manager.tet_pipeline.router
                supported_types = set()

                for source_id in router.data_sources:
                    source = router.get_data_source(source_id)
                    if source and hasattr(source.plugin, 'get_supported_asset_types'):
                        try:
                            types = source.plugin.get_supported_asset_types()
                            supported_types.update(types)
                        except Exception as e:
                            logger.debug(f"获取 {source_id} 支持的资产类型失败: {e}")

                return list(supported_types)

            # 降级到默认支持的类型
            return [AssetType.STOCK_A, AssetType.INDEX, AssetType.FUND]

        except Exception as e:
            logger.error(f"获取支持的资产类型失败: {e}")
            return [AssetType.STOCK_A]

    def get_provider_info(self, asset_type: AssetType = None) -> List[Dict[str, Any]]:
        """
        获取数据源提供商信息

        Args:
            asset_type: 资产类型过滤

        Returns:
            List[Dict]: 提供商信息列表
        """
        try:
            providers = []

            if self.unified_data_manager.tet_enabled and self.unified_data_manager.tet_pipeline:
                router = self.unified_data_manager.tet_pipeline.router

                for source_id in router.data_sources:
                    source = router.get_data_source(source_id)
                    if source:
                        try:
                            # 检查是否支持指定的资产类型
                            if asset_type:
                                supported_types = source.plugin.get_supported_asset_types()
                                if asset_type not in supported_types:
                                    continue

                            provider_info = {
                                'id': source_id,
                                'name': getattr(source.plugin, 'name', source_id),
                                'description': getattr(source.plugin, 'description', ''),
                                'supported_asset_types': [t.value for t in source.plugin.get_supported_asset_types()],
                                'supported_data_types': [t.value for t in source.plugin.get_supported_data_types()],
                                'status': 'active' if source.is_connected() else 'inactive'
                            }

                            providers.append(provider_info)

                        except Exception as e:
                            logger.debug(f"获取 {source_id} 提供商信息失败: {e}")

            return providers

        except Exception as e:
            self.logger.error(f"获取提供商信息失败: {e}")
            return []

    def health_check(self) -> Dict[str, Any]:
        """
        检查资产服务健康状态

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        try:
            logger.info(f"健康检查: {self.__class__.__name__}")
            
            status = {
                'service_name': 'AssetService',
                'status': 'healthy',
                'tet_enabled': self.unified_data_manager.tet_enabled,
                'supported_asset_types': [t.value for t in self.get_supported_asset_types()],
                'provider_count': 0,
                'issues': []
            }

            try:
                # 检查TET管道状态
                if not self.unified_data_manager.tet_enabled:
                    status['issues'].append('TET数据管道未启用')

                # 检查提供商状态
                providers = self.get_provider_info()
                status['provider_count'] = len(providers)

                active_providers = [p for p in providers if p['status'] == 'active']
                if len(active_providers) == 0:
                    status['issues'].append('没有活跃的数据提供商')
                    status['status'] = 'warning'

                # 检查核心服务
                if not self.stock_service:
                    status['issues'].append('股票服务不可用')
                    status['status'] = 'error'

                if not self.unified_data_manager:
                    status['issues'].append('统一数据管理器不可用')
                    status['status'] = 'error'

                # 检查各个子服务状态
                service_states = {
                    'unified_data_manager': self.unified_data_manager.health_check(),
                    'stock_service': self.stock_service.health_check() if self.stock_service else False,
                    'crypto_service': self.crypto_service.health_check() if self.crypto_service else False,
                    'forex_service': self.forex_service.health_check() if self.forex_service else False,
                    'fund_service': self.fund_service.health_check() if self.fund_service else False,
                    'futures_service': self.futures_service.health_check() if self.futures_service else False
                }

                all_healthy = True
                for service_name, state in service_states.items():
                    if not state:
                        logger.warning(f"服务 {service_name} 状态异常")
                        all_healthy = False

                if all_healthy:
                    logger.info("所有资产服务健康状态正常")
                else:
                    logger.warning("部分资产服务状态异常")
                    status['status'] = 'warning'

            except Exception as e:
                status['status'] = 'error'
                status['issues'].append(f'健康检查异常: {str(e)}')
                logger.error(f"健康检查失败: {e}")

            return status

        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return {
                'service_name': 'AssetService',
                'status': 'error',
                'error': str(e)
            }

# 便捷函数


def create_asset_service(unified_data_manager: UnifiedDataManager,
                         stock_service: StockService,
                         service_container) -> AssetService:
    """
    创建资产服务实例

    Args:
        unified_data_manager: 统一数据管理器
        stock_service: 股票服务
        service_container: 服务容器

    Returns:
        AssetService: 资产服务实例
    """
    return AssetService(unified_data_manager, stock_service, service_container)
