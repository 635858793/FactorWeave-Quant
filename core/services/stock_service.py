from loguru import logger
"""
股票服务模块

负责股票数据的获取、缓存和管理。
使用数据访问层进行数据操作。
"""

import pandas as pd
from typing import Dict, List, Optional, Any
from .base_service import CacheableService, ConfigurableService
from ..events import StockSelectedEvent, DataUpdateEvent
from ..business.stock_manager import StockManager
from ..data.data_access import DataAccess
from ..plugin_types import AssetType
from datetime import datetime, timedelta
import numpy as np
import time

# 移除MockDataManager，使用真正的FactorWeave-Quant数据管理器


class StockService(CacheableService, ConfigurableService):
    """
    股票服务

    负责股票数据的获取、缓存和管理。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, cache_size: int = 100,
                 service_container=None, **kwargs):
        """
        初始化股票服务

        Args:
            config: 服务配置
            cache_size: 缓存大小
            service_container: 服务容器
            **kwargs: 其他参数
        """
        # 提取service_container，避免传递给不需要它的父类
        self.service_container = service_container

        # 初始化各个基类（不传递service_container）
        filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'service_container'}
        CacheableService.__init__(self, cache_size=cache_size, namespace='stock_service', **filtered_kwargs)
        ConfigurableService.__init__(self, config=config, **filtered_kwargs)

        # 使用新的数据访问层
        self._data_access = DataAccess()
        self._stock_manager = None  # 将在初始化时创建
        
        # 初始化市值计算器工厂
        from .market_cap_calculator import get_market_cap_calculator_factory
        self._market_cap_calculator_factory = get_market_cap_calculator_factory()
        self._current_stock = None
        self._stock_list = []
        self._favorites = set()
        self.use_mock_data = False  # 数据源是否降级

        # 添加负缓存机制
        self._no_data_cache = set()  # 缓存没有数据的股票
        self._no_info_cache = set()  # 缓存没有基本信息的股票
        self._last_query_time = {}   # 记录最后查询时间，避免频繁查询

    def _do_initialize(self) -> None:
        """初始化股票服务"""
        try:
            # 使用统一数据管理器
            try:
                from .unified_data_manager import get_unified_data_manager
                unified_data_manager = get_unified_data_manager()

                if unified_data_manager and unified_data_manager.test_connection():
                    logger.info("Using unified data manager")
                    # 获取UniPluginDataManager
                    uni_plugin_manager = unified_data_manager.get_uni_plugin_manager()
                    if uni_plugin_manager:
                        logger.info("Using UniPluginDataManager for data access")
                        self._data_access = DataAccess(unified_data_manager, uni_plugin_manager)
                    else:
                        logger.warning("UniPluginDataManager not available, using legacy mode")
                        self._data_access = DataAccess(unified_data_manager)
                    self._data_access.connect()
                else:
                    raise RuntimeError("Unified data manager connection test failed")

            except Exception as unified_error:
                logger.warning(f"Failed to initialize unified data manager: {unified_error}")
                logger.warning("Falling back to default data access layer")

                # 回退到默认数据访问层
                if not self._data_access.connect():
                    logger.warning("Data access layer connection failed, entering degraded mode")
                    self.use_mock_data = True
                else:
                    self.use_mock_data = False

            # 创建股票管理器
            self._stock_manager = StockManager(self._data_access)

            # 加载股票列表
            self._load_stock_list()

            # 加载收藏列表
            self._load_favorites()

            logger.info("Stock service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize stock service: {e}")
            logger.warning("Entering degraded mode")
            self.use_mock_data = True
            self._create_mock_data_access()
            self._stock_manager = StockManager(self._data_access)
            self._load_stock_list()
            self._load_favorites()

    def _create_mock_data_access(self) -> None:
        """创建降级数据访问层（返回空数据）"""
        try:
            self._data_access = DataAccess()
            self._data_access._connected = True
            logger.info("Created degraded data access layer")
        except Exception as e:
            logger.error(f"Failed to create degraded data access: {e}")

            class DegradedDataAccess:
                def __init__(self):
                    self._connected = True

                def connect(self):
                    return True

                def disconnect(self):
                    pass

                def is_connected(self):
                    return True

                def get_kdata(self, stock_code, period='D', count=365):
                    # 返回空DataFrame
                    return pd.DataFrame()

                def get_stock_info(self, stock_code):
                    return None

                def get_stock_list(self, market=None):
                    return []

                def search_stocks(self, keyword):
                    return []

            self._data_access = DegradedDataAccess()
            logger.info("Created minimal degraded data access")

    def get_stock_list(self, market: Optional[str] = None,
                       industry: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取股票列表

        Args:
            market: 市场筛选
            industry: 行业筛选

        Returns:
            股票列表
        """
        self._ensure_initialized()

        cache_key = f"stock_list_{market}_{industry}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            # 使用股票管理器获取股票列表
            stock_info_list = self._stock_manager.get_stock_list(
                market, industry)
            stock_list = []

            for stock_info in stock_info_list:
                stock_dict = {
                    'code': stock_info.code,
                    'name': stock_info.name,
                    'market': stock_info.market,
                    'industry': stock_info.industry,
                    'is_favorite': getattr(stock_info, 'is_favorite', False)
                }
                stock_list.append(stock_dict)

            # 缓存结果
            self.put_to_cache(cache_key, stock_list)

            return stock_list

        except Exception as e:
            logger.error(f"Failed to get stock list: {e}")
            return []

    def get_stock_data(self, stock_code: str, period: str = 'D',
                       count: int = 365, asset_type=None) -> Optional[pd.DataFrame]:
        """
        获取股票数据

        Args:
            stock_code: 股票代码
            period: 周期 (D/W/M)
            count: 数据条数
            asset_type: 资产类型（可选）

        Returns:
            股票K线数据
        """
        self._ensure_initialized()

        if stock_code in self._no_data_cache:
            logger.debug(
                f"Stock {stock_code} is in no-data cache, returning None")
            return None

        cache_key = f"stock_data_{stock_code}_{period}_{count}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        current_time = time.time()
        last_query_key = f"{stock_code}_{period}_{count}"
        if last_query_key in self._last_query_time:
            time_diff = current_time - self._last_query_time[last_query_key]
            if time_diff < 0.1:
                logger.debug(f"Query too frequent for {stock_code}, skipping")
                return None

        self._last_query_time[last_query_key] = current_time

        try:
            kdata = self._data_access.get_kdata(stock_code, period, count, asset_type=asset_type)

            if kdata is not None and not kdata.empty:
                self.put_to_cache(cache_key, kdata)

                event = DataUpdateEvent(
                    data_type="stock_data",
                    update_info={
                        'stock_code': stock_code,
                        'period': period,
                        'count': len(kdata)
                    }
                )
                self.event_bus.publish(event)

                return kdata
            else:
                self._no_data_cache.add(stock_code)
                logger.debug(
                    f"No data for {stock_code}, added to no-data cache")
                return None

        except Exception as e:
            logger.error(f"Failed to get stock data for {stock_code}: {e}")
            self._no_data_cache.add(stock_code)
            return None

    def get_kdata(self, stock_code: str, period: str = 'D', count: int = 365,
                  asset_type: 'AssetType' = None) -> pd.DataFrame:
        """
        获取K线数据（优化：支持多资产类型智能路由）

        Args:
            stock_code: 股票代码（或其他资产代码）
            period: 周期
            count: 数据条数
            asset_type: 资产类型（可选，如果是非股票资产则路由到UnifiedDataManager）

        Returns:
            K线数据DataFrame
        """
        # 智能路由：如果指定了非股票资产类型，使用UnifiedDataManager
        if asset_type is not None:
            from core.plugin_types import AssetType
            if asset_type != AssetType.STOCK_A:
                # 非股票资产，路由到UnifiedDataManager
                try:
                    from core.services.unified_data_manager import get_unified_data_manager
                    data_manager = get_unified_data_manager()
                    if data_manager:
                        logger.debug(f"路由到UnifiedDataManager查询{asset_type.value}资产: {stock_code}")
                        return data_manager.get_kdata(stock_code, period, count, asset_type=asset_type)
                except Exception as e:
                    logger.error(f"UnifiedDataManager路由失败: {e}")
                    return pd.DataFrame()

        # 股票资产或未指定类型，使用传统方法
        stock_data = self.get_stock_data(stock_code, period, count, asset_type=asset_type)
        if stock_data is not None:
            return stock_data

        return pd.DataFrame()

    def get_kline_data(self, stock_code: str, period: str = 'D', count: int = 365, asset_type=None) -> pd.DataFrame:
        """
        获取K线数据（别名方法）

        Args:
            stock_code: 股票代码
            period: 周期 (D/W/M)
            count: 数据条数
            asset_type: 资产类型（可选）

        Returns:
            K线数据DataFrame
        """
        return self.get_kdata(stock_code, period, count, asset_type=asset_type)

    def select_stock(self, stock_code: str) -> bool:
        """
        选择股票

        Args:
            stock_code: 股票代码

        Returns:
            是否成功选择
        """
        self._ensure_initialized()

        try:
            # 获取股票信息
            stock_info = self._get_stock_info(stock_code)
            if not stock_info:
                logger.warning(f"Stock {stock_code} not found")
                return False

            # 更新当前股票
            self._current_stock = stock_info

            # 发布股票选择事件
            event = StockSelectedEvent(
                stock_code=stock_info['code'],
                stock_name=stock_info['name'],
                market=stock_info['market']
            )
            self.event_bus.publish(event)

            logger.info(f"Selected stock: {stock_code} ({stock_info['name']})")
            return True

        except Exception as e:
            logger.error(f"Failed to select stock {stock_code}: {e}")
            return False

    def get_current_stock(self) -> Optional[Dict[str, Any]]:
        """
        获取当前选择的股票

        Returns:
            当前股票信息
        """
        return self._current_stock

    def add_to_favorites(self, stock_code: str) -> bool:
        """
        添加到收藏

        Args:
            stock_code: 股票代码

        Returns:
            是否成功添加
        """
        self._ensure_initialized()

        try:
            # 使用股票管理器添加收藏
            success = self._stock_manager.add_to_favorites(stock_code)
            if success:
                self._favorites.add(stock_code)
                self._save_favorites()

                # 清除相关缓存
                self._clear_stock_list_cache()

                logger.info(f"Added {stock_code} to favorites")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to add {stock_code} to favorites: {e}")
            return False

    def remove_from_favorites(self, stock_code: str) -> bool:
        """
        从收藏中移除

        Args:
            stock_code: 股票代码

        Returns:
            是否成功移除
        """
        self._ensure_initialized()

        try:
            # 使用股票管理器移除收藏
            success = self._stock_manager.remove_from_favorites(stock_code)
            if success and stock_code in self._favorites:
                self._favorites.remove(stock_code)
                self._save_favorites()

                # 清除相关缓存
                self._clear_stock_list_cache()

                logger.info(f"Removed {stock_code} from favorites")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to remove {stock_code} from favorites: {e}")
            return False

    def get_favorites(self) -> List[str]:
        """
        获取收藏列表

        Returns:
            收藏的股票代码列表
        """
        return list(self._favorites)

    def search_stocks(self, keyword: str) -> List[Dict[str, Any]]:
        """
        搜索股票

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的股票列表
        """
        self._ensure_initialized()

        cache_key = f"search_{keyword}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            # 使用股票管理器搜索股票
            stock_info_list = self._stock_manager.search_stocks(keyword)

            # 转换为字典格式
            results = []
            for stock_info in stock_info_list:
                stock_dict = {
                    'code': stock_info.code,
                    'name': stock_info.name,
                    'market': stock_info.market,
                    'industry': stock_info.industry,
                    'is_favorite': getattr(stock_info, 'is_favorite', False)
                }
                results.append(stock_dict)

            # 缓存结果
            self.put_to_cache(cache_key, results)

            return results

        except Exception as e:
            logger.error(
                f"Failed to search stocks with keyword '{keyword}': {e}")
            return []

    def get_stock_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票基本信息

        Args:
            stock_code: 股票代码

        Returns:
            股票基本信息字典
        """
        self._ensure_initialized()

        # 检查负缓存
        if stock_code in self._no_info_cache:
            logger.debug(
                f"Stock {stock_code} is in no-info cache, returning None")
            return None

        cache_key = f"stock_info_{stock_code}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            # 使用数据访问层获取股票信息
            stock_info = self._data_access.get_stock_info(stock_code)

            if stock_info:
                # 如果是 StockInfo 对象，转换为字典
                if hasattr(stock_info, 'to_dict'):
                    stock_info_dict = stock_info.to_dict()
                else:
                    stock_info_dict = stock_info
                
                # 缓存结果
                self.put_to_cache(cache_key, stock_info_dict)
                return stock_info_dict
            else:
                # 添加到负缓存
                self._no_info_cache.add(stock_code)
                logger.debug(
                    f"No info for {stock_code}, added to no-info cache")
                return None

        except Exception as e:
            logger.error(f"Failed to get stock info for {stock_code}: {e}")
            # 查询失败也加入负缓存
            self._no_info_cache.add(stock_code)
            return None

    def _load_stock_list(self) -> None:
        """加载股票列表"""
        try:
            if self.use_mock_data:
                self._stock_list = []
                logger.warning("真实数据源不可用，股票列表为空")
            else:
                stock_info_list = self._data_access.get_stock_list()
                self._stock_list = [stock_info.to_dict()
                                    for stock_info in stock_info_list]
                logger.debug(f"Loaded {len(self._stock_list)} stocks")
        except Exception as e:
            logger.error(f"Failed to load stock list: {e}")
            self._stock_list = []
            logger.warning("加载股票列表失败，返回空列表。请检查数据源连接。")

    def _load_favorites(self) -> None:
        """加载收藏列表"""
        try:
            # 从配置中加载收藏列表
            favorites_list = self.get_config_value('favorites', [])
            self._favorites = set(favorites_list)
            logger.debug(f"Loaded {len(self._favorites)} favorites")
        except Exception as e:
            logger.error(f"Failed to load favorites: {e}")
            self._favorites = set()

    def _save_favorites(self) -> None:
        """保存收藏列表"""
        try:
            self.update_config({'favorites': list(self._favorites)})
        except Exception as e:
            logger.error(f"Failed to save favorites: {e}")

    def _get_stock_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取股票信息"""
        try:
            for stock in self._stock_list:
                if stock.get('code') == stock_code:
                    return {
                        'code': stock.get('code', ''),
                        'name': stock.get('name', ''),
                        'market': stock.get('market', ''),
                        'industry': stock.get('industry', ''),
                        'is_favorite': stock_code in self._favorites
                    }
            return None
        except Exception as e:
            logger.error(f"Failed to get stock info for {stock_code}: {e}")
            return None

    def refresh_data(self) -> bool:
        """
        刷新股票数据

        Returns:
            是否成功刷新
        """
        try:
            logger.info("开始刷新股票数据...")

            # 清除所有缓存
            self.clear_cache()

            # 重新加载股票列表
            self._load_stock_list()

            # 重新加载收藏列表
            self._load_favorites()

            # 如果有数据管理器，尝试更新数据
            if hasattr(self, '_data_access') and self._data_access:
                try:
                    # 这里可以调用数据访问层的数据更新方法
                    # 具体实现取决于数据访问层的API
                    if hasattr(self._data_access, 'refresh_data'):
                        self._data_access.refresh_data()
                except Exception as e:
                    logger.warning(
                        f"Failed to refresh data from data access layer: {e}")

            logger.info(f"股票数据刷新完成，共加载 {len(self._stock_list)} 只股票")
            return True

        except Exception as e:
            logger.error(f"Failed to refresh stock data: {e}")
            return False

    def perform_advanced_search(self, conditions: Dict[str, Any], asset_type: AssetType = AssetType.STOCK_A) -> List[Dict[str, Any]]:
        """
        执行高级搜索

        Args:
            conditions: 搜索条件字典
            asset_type: 资产类型（默认为股票）

        Returns:
            符合条件的资产列表
        """
        try:
            logger.info(f"开始执行高级搜索... 资产类型: {asset_type.value}")

            all_stocks = self.get_stock_list()
            
            if not all_stocks:
                logger.info("高级搜索完成，找到 0 只符合条件的资产")
                return []

            df = pd.DataFrame(all_stocks)

            code_filter = conditions.get("code")
            if code_filter:
                code_mask = df['code'].str.contains(code_filter, na=False)
                df = df[code_mask]

            name_filter = conditions.get("name")
            if name_filter:
                name_mask = df['name'].str.contains(name_filter, na=False)
                df = df[name_mask]

            industry_filter = conditions.get("industry")
            if industry_filter and industry_filter != "全部":
                industry_mask = df['industry'] == industry_filter
                df = df[industry_mask]

            market_filter = conditions.get("market")
            if market_filter and market_filter != "全部":
                market_mask = df['code'].map(
                    lambda code: self._check_market_match(code, market_filter)
                )
                df = df[market_mask]

            if df.empty:
                logger.info("高级搜索完成，找到 0 只符合条件的资产")
                return []

            filtered_stocks = []
            _realtime_cache: Dict[str, Optional[Dict[str, Any]]] = {}

            for _, stock_info in df.iterrows():
                try:
                    stock_info_dict = stock_info.to_dict()
                    code = stock_info_dict.get('code', '')

                    if code not in _realtime_cache:
                        _realtime_cache[code] = self._get_stock_realtime_data(code, asset_type)
                    asset_data = _realtime_cache[code]

                    if not asset_data:
                        asset_data = {
                            'price': 0,
                            'volume': 0,
                            'turnover_rate': 0,
                            'market_cap': 0,
                            'metric_type': 'market_cap'
                        }
                        logger.debug(f"资产 {code} 没有实时数据，使用默认值")

                    latest_price = asset_data.get('price', 0)
                    if latest_price < conditions.get("min_price", 0) or latest_price > conditions.get("max_price", 10000):
                        continue

                    metric_type = asset_data.get('metric_type', 'market_cap')
                    if metric_type == 'market_cap':
                        market_cap = asset_data.get('market_cap', 0)
                        if market_cap < conditions.get("min_cap", 0) or market_cap > conditions.get("max_cap", 1000000):
                            continue
                    else:
                        logger.debug(f"资产 {code} 使用替代指标: {metric_type}")

                    volume = asset_data.get('volume', 0) / 10000
                    if volume < conditions.get("min_volume", 0) or volume > conditions.get("max_volume", 1000000):
                        continue

                    if 'stock' in asset_type.value:
                        turnover_rate = asset_data.get('turnover_rate', 0)
                        if turnover_rate < conditions.get("min_turnover", 0) or turnover_rate > conditions.get("max_turnover", 100):
                            continue

                    stock_info_dict.update(asset_data)

                    filtered_stocks.append(stock_info_dict)

                except Exception as e:
                    logger.warning(
                        f"处理资产 {stock_info.get('code', '未知')} 失败: {e}")
                    continue

            logger.info(f"高级搜索完成，找到 {len(filtered_stocks)} 只符合条件的资产")
            return filtered_stocks

        except Exception as e:
            logger.error(f"执行高级搜索失败: {e}")
            return []

    def _check_market_match(self, stock_code: str, market_filter: str) -> bool:
        """
        检查股票代码是否匹配市场筛选条件

        Args:
            stock_code: 股票代码
            market_filter: 市场筛选条件

        Returns:
            是否匹配
        """
        try:
            if not stock_code or len(stock_code) < 2:
                return False

            # 根据股票代码前缀判断市场
            if market_filter == "沪市主板" and stock_code.startswith('sh60'):
                return True
            elif market_filter == "深市主板" and stock_code.startswith('sz00'):
                return True
            elif market_filter == "创业板" and stock_code.startswith('sz30'):
                return True
            elif market_filter == "科创板" and stock_code.startswith('sh68'):
                return True
            elif market_filter == "北交所" and stock_code.startswith('bj8'):
                return True
            elif market_filter == "港股通" and stock_code.startswith('hk'):
                return True
            elif market_filter == "美股" and stock_code.startswith('us'):
                return True
            elif market_filter == "期货" and stock_code.startswith('IC'):
                return True
            elif market_filter == "期权" and stock_code.startswith('10'):
                return True

            return False

        except Exception as e:
            logger.error(f"检查市场匹配失败: {e}")
            return False

    def _get_stock_realtime_data(self, stock_code: str, asset_type: AssetType = AssetType.STOCK_A) -> Optional[Dict[str, Any]]:
        """
        获取股票实时数据

        Args:
            stock_code: 股票代码
            asset_type: 资产类型（默认为股票）

        Returns:
            实时数据字典，包含价格、市值、成交量、换手率等
        """
        try:
            if not self._data_access:
                return None

            # 从数据访问层获取实时数据
            kdata = self._data_access.get_kdata(
                stock_code, period='D', count=1)
            if kdata is None or kdata.empty:
                return None

            # 获取最新一条数据
            latest = kdata.iloc[-1]

            # 构造实时数据
            realtime_data = {
                'price': float(latest.get('close', 0)),
                'volume': float(latest.get('volume', 0)),
                'turnover_rate': float(latest.get('turnover', 0)) if 'turnover' in latest else 0
            }

            # 使用市值计算器计算市值
            price = realtime_data['price']
            if price > 0:
                # 获取额外的数据（股本、供应量等）
                additional_data = self._get_additional_market_data(stock_code, asset_type)
                
                # 获取对应的市值计算器
                calculator = self._market_cap_calculator_factory.get_calculator(asset_type)
                
                # 计算市值
                market_cap_result = calculator.calculate(price, additional_data)
                result_dict = market_cap_result.to_dict()
                
                # 将市值数据合并到实时数据中
                realtime_data.update(result_dict)
            else:
                realtime_data['market_cap'] = 0
                realtime_data['metric_type'] = 'market_cap'

            return realtime_data

        except Exception as e:
            logger.error(f"获取股票 {stock_code} 实时数据失败: {e}")
            return None

    def _get_additional_market_data(self, stock_code: str, asset_type: AssetType) -> Dict[str, Any]:
        """
        获取市值计算所需的额外数据（股本、供应量等）
        
        Args:
            stock_code: 资产代码
            asset_type: 资产类型
            
        Returns:
            包含额外数据的字典
        """
        try:
            additional_data = {}
            
            # 根据资产类型获取不同的数据
            if 'stock' in asset_type.value:
                # 股票：获取股本数据
                additional_data.update(self._get_stock_shares_data(stock_code))
            elif asset_type == AssetType.CRYPTO:
                # 加密货币：获取供应量数据
                additional_data.update(self._get_crypto_supply_data(stock_code))
            elif asset_type == AssetType.FUND:
                # 基金：获取份额数据
                additional_data.update(self._get_fund_units_data(stock_code))
            elif asset_type == AssetType.FUTURES:
                # 期货：获取持仓量数据
                additional_data.update(self._get_futures_open_interest(stock_code))
            elif asset_type == AssetType.INDEX:
                # 指数：获取成分股市值数据
                additional_data.update(self._get_index_market_cap(stock_code))
            
            return additional_data
            
        except Exception as e:
            logger.error(f"获取 {stock_code} 额外市场数据失败: {e}")
            return {}
    
    def _get_stock_shares_data(self, stock_code: str) -> Dict[str, Any]:
        """
        获取股票股本数据
        
        Args:
            stock_code: 股票代码
            
        Returns:
            包含total_shares和circulating_shares的字典
        """
        try:
            # 优先从数据库缓存获取
            cache_key = f"shares_data_{stock_code}"
            cached_data = self.get_from_cache(cache_key)
            if cached_data:
                return cached_data
            
            shares_data = {}
            
            # 尝试从数据访问层获取基本面数据
            if self._data_access and hasattr(self._data_access, 'get_fundamental_data'):
                fundamental_data = self._data_access.get_fundamental_data(stock_code)
                if fundamental_data:
                    shares_data['total_shares'] = fundamental_data.get('total_shares', 0)
                    shares_data['circulating_shares'] = fundamental_data.get('circulating_shares', 0)
            
            # 如果没有数据，尝试从股票信息获取
            if not shares_data.get('total_shares'):
                stock_info = self._stock_manager.get_stock_info(stock_code) if self._stock_manager else None
                if stock_info and hasattr(stock_info, 'total_shares'):
                    shares_data['total_shares'] = getattr(stock_info, 'total_shares', 0)
                    shares_data['circulating_shares'] = getattr(stock_info, 'circulating_shares', 0)
            
            # 缓存结果
            if shares_data:
                self.put_to_cache(cache_key, shares_data)
            
            return shares_data
            
        except Exception as e:
            logger.warning(f"获取股票 {stock_code} 股本数据失败: {e}")
            return {}

    def batch_update_stock_shares(self, stock_codes: List[str]) -> Dict[str, Any]:
        """
        批量更新股票股本数据
        
        Args:
            stock_codes: 股票代码列表
            
        Returns:
            更新结果统计
                - success_count: 成功更新的数量
                - failed_count: 失败的数量
                - updated_stocks: 更新的股票列表
                - failed_stocks: 失败的股票列表
        """
        try:
            result = {
                'success_count': 0,
                'failed_count': 0,
                'updated_stocks': [],
                'failed_stocks': []
            }
            
            if not stock_codes:
                logger.warning("股票代码列表为空，跳过批量更新")
                return result
            
            logger.info(f"开始批量更新 {len(stock_codes)} 只股票的股本数据...")
            
            # Phase 1: 采集所有股票数据
            records = []
            for stock_code in stock_codes:
                try:
                    shares_data = self._get_stock_shares_data(stock_code)
                    
                    if shares_data and shares_data.get('total_shares'):
                        records.append((stock_code, shares_data))
                        result['updated_stocks'].append(stock_code)
                        
                        if len(records) % 100 == 0:
                            logger.info(f"已采集 {len(records)} 只股票的股本数据")
                    else:
                        result['failed_count'] += 1
                        result['failed_stocks'].append(stock_code)
                        
                except Exception as e:
                    logger.warning(f"获取股票 {stock_code} 股本数据失败: {e}")
                    result['failed_count'] += 1
                    result['failed_stocks'].append(stock_code)
            
            # Phase 2: 批量写入数据库 (单连接 + executemany)
            if records:
                try:
                    self._batch_save_stock_shares_to_db(records)
                    result['success_count'] = len(records)
                except Exception as e:
                    logger.error(f"批量写入股本数据失败: {e}")
                    result['success_count'] = 0
                    result['failed_count'] = len(stock_codes)
                    result['updated_stocks'] = []
                    result['failed_stocks'] = list(stock_codes)
            
            logger.info(f"批量更新完成: 成功 {result['success_count']}, 失败 {result['failed_count']}")
            return result
            
        except Exception as e:
            logger.error(f"批量更新股票股本数据失败: {e}")
            return {'success_count': 0, 'failed_count': len(stock_codes), 'updated_stocks': [], 'failed_stocks': stock_codes}

    def _batch_save_stock_shares_to_db(self, records: List[tuple]):
        """
        批量写入股本数据到数据库 (单连接 + executemany)
        
        Args:
            records: [(stock_code, shares_data), ...] 元组列表
        """
        from datetime import datetime
        
        update_date = datetime.now()
        
        batch_data = []
        for stock_code, shares_data in records:
            batch_data.append((
                stock_code,
                shares_data.get('stock_name', ''),
                shares_data.get('total_shares', 0),
                shares_data.get('circulating_shares', 0),
                shares_data.get('total_market_cap', 0),
                shares_data.get('circulating_market_cap', 0),
                update_date
            ))
        
        if self._data_access and hasattr(self._data_access, 'uni_plugin_manager'):
            uni_plugin_manager = self._data_access.uni_plugin_manager
            if uni_plugin_manager and hasattr(uni_plugin_manager, 'asset_db_manager'):
                asset_db_manager = uni_plugin_manager.asset_db_manager
                
                with asset_db_manager.get_connection(AssetType.STOCK_A) as conn:
                    conn.executemany("""
                        INSERT INTO stock_shares 
                        (stock_code, stock_name, total_shares, circulating_shares, 
                         total_market_cap, circulating_market_cap, update_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (stock_code, update_date) 
                        DO UPDATE SET
                            stock_name = excluded.stock_name,
                            total_shares = excluded.total_shares,
                            circulating_shares = excluded.circulating_shares,
                            total_market_cap = excluded.total_market_cap,
                            circulating_market_cap = excluded.circulating_market_cap
                    """, batch_data)
        
        logger.info(f"批量写入 {len(records)} 条股本数据完成")
    
    def _get_crypto_supply_data(self, crypto_code: str) -> Dict[str, Any]:
        """
        获取加密货币供应量数据
        
        Args:
            crypto_code: 加密货币代码
            
        Returns:
            包含total_supply和circulating_supply的字典
        """
        try:
            cache_key = f"crypto_supply_{crypto_code}"
            cached_data = self.get_from_cache(cache_key)
            if cached_data:
                return cached_data
            
            supply_data = {}
            
            # 尝试从数据源获取供应量数据
            if self._data_access and hasattr(self._data_access, 'get_crypto_info'):
                crypto_info = self._data_access.get_crypto_info(crypto_code)
                if crypto_info:
                    supply_data['total_supply'] = crypto_info.get('total_supply', 0)
                    supply_data['circulating_supply'] = crypto_info.get('circulating_supply', 0)
            
            # 缓存结果（缓存5分钟）
            if supply_data:
                self.put_to_cache(cache_key, supply_data, ttl=300)
            
            return supply_data
            
        except Exception as e:
            logger.warning(f"获取加密货币 {crypto_code} 供应量数据失败: {e}")
            return {}
    
    def _get_fund_units_data(self, fund_code: str) -> Dict[str, Any]:
        """
        获取基金份额数据
        
        Args:
            fund_code: 基金代码
            
        Returns:
            包含total_units的字典
        """
        try:
            cache_key = f"fund_units_{fund_code}"
            cached_data = self.get_from_cache(cache_key)
            if cached_data:
                return cached_data
            
            units_data = {}
            
            # 尝试从数据源获取基金份额数据
            if self._data_access and hasattr(self._data_access, 'get_fund_info'):
                fund_info = self._data_access.get_fund_info(fund_code)
                if fund_info:
                    units_data['total_units'] = fund_info.get('total_units', 0)
            
            # 缓存结果（缓存1小时）
            if units_data:
                self.put_to_cache(cache_key, units_data, ttl=3600)
            
            return units_data
            
        except Exception as e:
            logger.warning(f"获取基金 {fund_code} 份额数据失败: {e}")
            return {}
    
    def _get_futures_open_interest(self, futures_code: str) -> Dict[str, Any]:
        """
        获取期货持仓量数据
        
        Args:
            futures_code: 期货代码
            
        Returns:
            包含open_interest的字典
        """
        try:
            cache_key = f"futures_oi_{futures_code}"
            cached_data = self.get_from_cache(cache_key)
            if cached_data:
                return cached_data
            
            oi_data = {}
            
            # 尝试从K线数据获取持仓量
            if self._data_access:
                kdata = self._data_access.get_kdata(futures_code, period='D', count=1)
                if kdata is not None and not kdata.empty:
                    latest = kdata.iloc[-1]
                    oi_data['open_interest'] = latest.get('open_interest', 0)
            
            # 缓存结果
            if oi_data:
                self.put_to_cache(cache_key, oi_data)
            
            return oi_data
            
        except Exception as e:
            logger.warning(f"获取期货 {futures_code} 持仓量数据失败: {e}")
            return {}
    
    def _get_index_market_cap(self, index_code: str) -> Dict[str, Any]:
        """
        获取指数成分股总市值
        
        Args:
            index_code: 指数代码
            
        Returns:
            包含total_market_cap的字典
        """
        try:
            cache_key = f"index_mc_{index_code}"
            cached_data = self.get_from_cache(cache_key)
            if cached_data:
                return cached_data
            
            mc_data = {}
            
            # 尝试从数据源获取指数成分股市值
            if self._data_access and hasattr(self._data_access, 'get_index_info'):
                index_info = self._data_access.get_index_info(index_code)
                if index_info:
                    mc_data['total_market_cap'] = index_info.get('total_market_cap', 0)
            
            # 缓存结果（缓存5分钟）
            if mc_data:
                self.put_to_cache(cache_key, mc_data, ttl=300)
            
            return mc_data
            
        except Exception as e:
            logger.warning(f"获取指数 {index_code} 成分股市值数据失败: {e}")
            return {}

    def _generate_mock_stock_list(self) -> List[Dict[str, Any]]:
        """真实数据不可用时的降级处理"""
        logger.warning("真实数据不可用，无法生成股票列表。请检查数据源连接。")
        return []

    def _clear_stock_list_cache(self) -> None:
        """清除股票列表相关缓存"""
        self.clear_cache(cache_type='data')

    def _do_dispose(self) -> None:
        """清理资源"""
        self._save_favorites()

        # 断开数据访问层连接
        if self._data_access:
            self._data_access.disconnect()

        self._current_stock = None
        self._stock_list = []
        self._favorites.clear()
        super()._do_dispose()

    def clear_cache(self, cache_type: str = 'all') -> None:
        """
        清理缓存

        Args:
            cache_type: 缓存类型 ('all', 'data', 'negative')
        """
        if cache_type in ('all', 'data'):
            super().clear_cache()

        if cache_type in ('all', 'negative'):
            self._no_data_cache.clear()
            self._no_info_cache.clear()
            self._last_query_time.clear()
            logger.info("Negative cache cleared")

    def remove_from_negative_cache(self, stock_code: str) -> None:
        """
        从负缓存中移除股票

        Args:
            stock_code: 股票代码
        """
        self._no_data_cache.discard(stock_code)
        self._no_info_cache.discard(stock_code)
        # 清理相关的查询时间记录
        keys_to_remove = [
            key for key in self._last_query_time.keys() if stock_code in key]
        for key in keys_to_remove:
            del self._last_query_time[key]
        logger.debug(f"Removed {stock_code} from negative cache")
