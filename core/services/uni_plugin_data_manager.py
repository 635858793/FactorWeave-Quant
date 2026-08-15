"""
统一插件数据管理器

统一FactorWeave-Quant系统的数据源管理，建立单一的插件中心架构，
消除三套并行数据源管理体系，实现真正的插件中心统一管理。

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import re

from loguru import logger
from core.plugin_types import AssetType, DataType, PluginType
from core.data_source_extensions import IDataSourcePlugin, PluginInfo, HealthCheckResult
from core.tet_data_pipeline import TETDataPipeline, StandardQuery, StandardData
from core.data_source_router import DataSourceRouter, RoutingStrategy
from core.plugin_manager import PluginManager
from core.plugin_center import PluginCenter
from core.tet_router_engine import TETRouterEngine
from core.data_quality_risk_manager import DataQualityRiskManager

logger = logger.bind(module=__name__)


@dataclass
class RequestContext:
    """请求上下文"""
    asset_type: AssetType
    data_type: DataType
    symbol: Optional[str] = None
    market: Optional[str] = None
    priority: int = 50
    quality_requirement: float = 0.8
    timeout: int = 30
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class UniPluginDataManager:
    """
    统一插件数据管理器

    FactorWeave-Quant系统的统一数据访问入口，协调插件中心、TET路由引擎和风险管理器
    """

    def __init__(self, plugin_manager: PluginManager,
                 data_source_router: DataSourceRouter,
                 tet_pipeline: TETDataPipeline):
        """
        初始化统一插件数据管理器

        Args:
            plugin_manager: 插件管理器
            data_source_router: 数据源路由器
            tet_pipeline: TET数据管道
        """
        self.plugin_center = PluginCenter(plugin_manager)
        self.tet_engine = TETRouterEngine(data_source_router, tet_pipeline)
        try:
            from core.containers import get_service_container
            self.risk_manager = get_service_container().resolve(DataQualityRiskManager)
        except Exception:
            self.risk_manager = DataQualityRiskManager()

        # 保存路由器引用以便注册插件
        self.data_source_router = data_source_router

        # 数据标准化器
        self.data_normalizer = self._create_data_normalizer()

        # 性能统计
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "cache_hits": 0,
            "avg_response_time": 0.0
        }

        # 统一缓存服务（强制）
        self._unified_cache = None
        self._cache_namespace = 'uni_plugin_data'
        self._cache_ttl = 300  # 缓存TTL: 5分钟
        self._init_unified_cache()

        # 线程池（v2.4性能优化）
        self._executor = ThreadPoolExecutor(max_workers=8)  # 从4增加到8

        # 延迟初始化标志

        self._is_initialized = False

        # 基本面数据数据库管理器（延迟初始化）
        self._asset_db_manager = None

        logger.info("UniPluginDataManager构造完成，等待initialize()调用")

    def _init_unified_cache(self) -> None:
        """初始化统一缓存服务（强制）"""
        from core.services.cache_service import CacheService
        from core.containers import get_service_container
        
        container = get_service_container()
        if container and container.is_registered(CacheService):
            self._unified_cache = container.resolve(CacheService)
            logger.debug(f"UniPluginDataManager 已连接到统一缓存服务，命名空间: {self._cache_namespace}")
        else:
            self._unified_cache = None
            logger.debug(f"{self.__class__.__name__} 统一缓存服务未注册，缓存功能降级为空操作")

        logger.info("UniPluginDataManager依赖装配完成")

    def _register_plugins_to_router(self) -> None:
        """将插件中心的插件注册到TET路由器"""
        try:
            logger.info("[DISCOVERY] 开始发现插件...")
            # 发现并注册插件
            plugins = self.plugin_center.discover_and_register_plugins()
            logger.info(f"插件中心发现 {len(plugins)} 个插件")

            # 获取数据源插件并注册到路由器
            data_source_plugins = self.plugin_center.data_source_plugins
            logger.info(f"[DISCOVERY] 找到 {len(data_source_plugins)} 个数据源插件")
            registered_count = 0

            for plugin_id, plugin_instance in data_source_plugins.items():
                try:
                    # 创建数据源适配器
                    from core.data_source_extensions import DataSourcePluginAdapter
                    adapter = DataSourcePluginAdapter(plugin_instance, plugin_id)

                    # 注册到路由器
                    success = self.data_source_router.register_data_source(
                        plugin_id,
                        adapter,
                        priority=50,  # 默认优先级
                        weight=1.0    # 默认权重
                    )

                    if success:
                        registered_count += 1
                        logger.info(f"数据源插件注册到路由器成功: {plugin_id}")
                    else:
                        logger.warning(f"数据源插件注册到路由器失败: {plugin_id}")

                except Exception as e:
                    logger.error(f"注册插件到路由器失败 {plugin_id}: {e}")

            logger.info(f"成功注册 {registered_count} 个数据源插件到TET路由器")

        except Exception as e:
            logger.error(f"注册插件到路由器过程失败: {e}")

    def initialize(self) -> None:
        """统一的初始化入口，控制插件注册时机"""
        # R246 修复: 增加 data_source_plugins 非空条件。
        # 若时序异常导致提前初始化时 0 插件注册, _is_initialized 仍为 True,
        # 原短路会永久跳过后续真实初始化; 增加条件后允许在插件已就绪时重试注册。
        if self._is_initialized and self.plugin_center.data_source_plugins:
            logger.info("UniPluginDataManager已初始化，跳过重复初始化")
            return

        logger.info("开始初始化UniPluginDataManager...")

        # 现在才执行插件注册
        self._register_plugins_to_router()

        # 验证注册结果
        router_source_count = len(self.data_source_router.data_sources)
        logger.info(f"插件注册完成，TET路由器中有 {router_source_count} 个数据源")

        if router_source_count == 0:
            logger.warning("TET路由器中没有数据源，这可能导致数据获取失败")
        else:
            logger.info("TET路由器数据源注册成功")

        self._is_initialized = True
        logger.info("UniPluginDataManager初始化完成")

    def _create_data_normalizer(self):
        """创建数据标准化器"""
        class StockDataNormalizer:
            def normalize_stock_list(self, raw_data: List[Dict], source: str) -> List[Dict[str, Any]]:
                if not raw_data:
                    return []

                logger.info(f"[NORMALIZE] 标准化 {source} 数据源的股票列表，原始数量: {len(raw_data)}")

                normalized_stocks = []
                seen_codes = set()

                for raw_stock in raw_data:
                    try:
                        code = self._extract_code(raw_stock)
                        name = self._extract_name(raw_stock)

                        if not code or not name:
                            continue

                        std_code, market = self._normalize_code(code, source)

                        if std_code in seen_codes:
                            continue
                        seen_codes.add(std_code)

                        normalized_stock = {
                            'code': std_code,
                            'name': name.strip(),
                            'market': market,
                            'display_code': std_code.split('.')[0] if '.' in std_code else std_code,
                            'source': source,
                            **{k: v for k, v in raw_stock.items() if k not in ['code', 'name']}
                        }
                        normalized_stocks.append(normalized_stock)

                    except Exception:
                        continue

                normalized_stocks.sort(key=lambda x: x['code'])
                logger.info(f"{source} 标准化完成，标准化数量: {len(normalized_stocks)}")
                return normalized_stocks

            def _extract_code(self, raw: Dict) -> str:
                for field in ['code', 'symbol', 'ts_code', 'stock_code', 'SECUCODE']:
                    if field in raw and raw[field]:
                        return str(raw[field]).strip()
                return ""

            def _extract_name(self, raw: Dict) -> str:
                for field in ['name', 'sec_name', 'stock_name', 'SECUABBR']:
                    if field in raw and raw[field]:
                        return str(raw[field]).strip()
                return ""

            def _normalize_code(self, code: str, source: str) -> tuple:
                if 'eastmoney' in source:
                    return self._normalize_eastmoney_code(code)
                elif 'sina' in source:
                    return self._normalize_sina_code(code)
                elif 'tushare' in source:
                    return self._normalize_tushare_code(code)
                else:
                    return self._infer_market_from_code(code)

            def _normalize_eastmoney_code(self, code: str) -> tuple:
                if '.' in code:
                    parts = code.split('.')
                    if len(parts) == 2:
                        market_code, stock_code = parts
                        if market_code in ['0', 'SZ']:
                            return f"{stock_code}.SZ", "SZ"
                        elif market_code in ['1', 'SH']:
                            return f"{stock_code}.SH", "SH"
                return self._infer_market_from_code(code)

            def _normalize_sina_code(self, code: str) -> tuple:
                code_lower = code.lower()
                if code_lower.startswith('sz'):
                    return f"{code[2:]}.SZ", "SZ"
                elif code_lower.startswith('sh'):
                    return f"{code[2:]}.SH", "SH"
                return self._infer_market_from_code(code)

            def _normalize_tushare_code(self, code: str) -> tuple:
                if '.' in code:
                    parts = code.split('.')
                    if len(parts) == 2:
                        stock_code, market_code = parts
                        return f"{stock_code}.{market_code.upper()}", market_code.upper()
                return self._infer_market_from_code(code)

            def _infer_market_from_code(self, code: str) -> tuple:
                numeric_code = re.sub(r'[^\d]', '', code)
                if not numeric_code:
                    return f"{code}.SZ", "SZ"

                if numeric_code.startswith('6'):
                    return f"{numeric_code}.SH", "SH"
                elif numeric_code.startswith(('00', '30')):
                    return f"{numeric_code}.SZ", "SZ"
                elif numeric_code.startswith('68'):
                    return f"{numeric_code}.SH", "SH"
                elif numeric_code.startswith(('8', '9')):
                    return f"{numeric_code}.BJ", "BJ"
                else:
                    return f"{numeric_code}.SZ", "SZ"

        return StockDataNormalizer()

    def get_stock_list(self, market: str = None, **params) -> List[Dict[str, Any]]:
        """
        获取股票列表 - 统一入口

        Args:
            market: 市场代码
            **params: 其他参数

        Returns:
            List[Dict[str, Any]]: 标准化的股票列表
        """
        context = RequestContext(
            asset_type=AssetType.STOCK_A,
            data_type=DataType.ASSET_LIST,
            market=market
        )

        # 执行数据请求
        result = self._execute_data_request(context, 'get_asset_list', **params)

        # 数据标准化处理
        if result is not None and isinstance(result, list):
            plugin_id = getattr(context, 'actual_plugin_id', 'unknown')
            logger.info(f"[PROCESS] 开始标准化股票列表数据，来源插件: {plugin_id}")

            normalized_result = self.data_normalizer.normalize_stock_list(result, plugin_id)

            logger.info(f"[METRICS] 股票列表标准化完成: 原始 {len(result)} -> 标准化 {len(normalized_result)}")
            return normalized_result

        # 如果结果是DataFrame，直接返回（不需要标准化）
        if result is not None:
            return result

        return []

    def get_fund_list(self, market: str = None, **params) -> List[Dict[str, Any]]:
        """
        获取基金列表 - 统一入口

        Args:
            market: 市场代码
            **params: 其他参数

        Returns:
            List[Dict[str, Any]]: 基金列表
        """
        context = RequestContext(
            asset_type=AssetType.FUND,
            data_type=DataType.ASSET_LIST,
            market=market
        )

        return self._execute_data_request(context, 'get_asset_list', **params)

    def get_index_list(self, market: str = None, **params) -> List[Dict[str, Any]]:
        """
        获取指数列表 - 统一入口

        Args:
            market: 市场代码
            **params: 其他参数

        Returns:
            List[Dict[str, Any]]: 指数列表
        """
        context = RequestContext(
            asset_type=AssetType.INDEX,
            data_type=DataType.ASSET_LIST,
            market=market
        )

        return self._execute_data_request(context, 'get_asset_list', **params)

    def get_kline_data(self, symbol: str, asset_type: AssetType,
                       start_date: datetime = None, end_date: datetime = None,
                       frequency: str = None, **params) -> pd.DataFrame:
        """
        获取K线数据 - 统一入口

        Args:
            symbol: 标的代码
            asset_type: 资产类型
            start_date: 开始日期
            end_date: 结束日期
            frequency: 数据频率（默认使用Period.DAY.value）
            **params: 其他参数

        Returns:
            pd.DataFrame: K线数据
        """
        from core.plugin_types import Period
        if frequency is None:
            frequency = Period.DAY.value
        # 参数类型检查和转换
        if isinstance(asset_type, str):
            try:
                asset_type = AssetType(asset_type)
            except ValueError:
                asset_type = AssetType.STOCK_A

        context = RequestContext(
            asset_type=asset_type,
            data_type=DataType.HISTORICAL_KLINE,
            symbol=symbol
        )

        # 准备参数
        kline_params = {
            'symbol': symbol,
            'start_date': start_date,
            'end_date': end_date,
            'frequency': frequency,
            **params
        }

        return self._execute_data_request(context, 'get_kline_data', **kline_params)

    def get_real_time_data(self, symbols: List[str], asset_type: AssetType,
                           **params) -> pd.DataFrame:
        """
        获取实时数据 - 统一入口

        Args:
            symbols: 标的代码列表
            asset_type: 资产类型
            **params: 其他参数

        Returns:
            pd.DataFrame: 实时数据
        """
        # 参数类型检查和转换
        if isinstance(asset_type, str):
            try:
                asset_type = AssetType(asset_type)
            except ValueError:
                asset_type = AssetType.STOCK_A

        context = RequestContext(
            asset_type=asset_type,
            data_type=DataType.REAL_TIME_QUOTE
        )

        # 准备参数
        realtime_params = {
            'symbols': symbols,
            **params
        }

        return self._execute_data_request(context, 'get_real_time_data', **realtime_params)

    def get_fundamental_data(self, symbol: str, asset_type: AssetType = AssetType.STOCK_A,
                             **params) -> Dict[str, Any]:
        """
        获取基本面数据 - 统一入口

        Args:
            symbol: 标的代码
            asset_type: 资产类型
            **params: 其他参数

        Returns:
            Dict[str, Any]: 基本面数据
        """
        # 参数类型检查和转换
        if isinstance(asset_type, str):
            try:
                asset_type = AssetType(asset_type)
            except ValueError:
                asset_type = AssetType.STOCK_A

        context = RequestContext(
            asset_type=asset_type,
            data_type=DataType.FUNDAMENTAL,
            symbol=symbol
        )

        # 准备参数
        fundamental_params = {
            'symbol': symbol,
            **params
        }

        return self._execute_data_request(context, 'get_fundamental_data', **fundamental_params)

    def get_fundamental_data_batch(self, symbols: List[str], asset_type: AssetType = AssetType.STOCK_A,
                                   **params) -> Dict[str, Dict[str, Any]]:
        """
        批量获取基本面数据 - 统一入口（优化版：优先从数据库批量读取）

        Args:
            symbols: 标的代码列表
            asset_type: 资产类型
            **params: 其他参数

        Returns:
            Dict[symbol, Dict[str, Any]]: 基本面数据字典
        """
        # 参数类型检查和转换
        if isinstance(asset_type, str):
            try:
                asset_type = AssetType(asset_type)
            except ValueError:
                asset_type = AssetType.STOCK_A

        result = {}
        
        # 检查缓存
        uncached_symbols = []
        for symbol in symbols:
            context = RequestContext(
                asset_type=asset_type,
                data_type=DataType.FUNDAMENTAL,
                symbol=symbol
            )
            cache_key = self._generate_cache_key(context, 'get_fundamental_data', symbol=symbol, **params)
            cached_result = self._get_from_cache(cache_key)
            if cached_result is not None:
                result[symbol] = cached_result
            else:
                uncached_symbols.append(symbol)
        
        # 如果所有股票都有缓存，直接返回
        if not uncached_symbols:
            logger.debug(f"批量获取基本面数据：全部命中缓存 ({len(symbols)}个)")
            return result
        
        # 新增：优先从数据库批量读取未缓存的基本面数据
        db_loaded_symbols = []
        try:
            logger.info(f"[BATCH-DB] 开始批量从数据库加载基本面数据: {len(uncached_symbols)}个股票")
            
            if self._asset_db_manager is None:
                from core.asset_database_manager import get_asset_separated_database_manager
                self._asset_db_manager = get_asset_separated_database_manager()
                logger.debug("[BATCH-DB] 数据库管理器已初始化")
            
            # 批量从数据库加载
            db_results = self._asset_db_manager.load_fundamental_data_batch(uncached_symbols, asset_type)
            
            # 缓存数据库结果
            for symbol, fundamental_data in db_results.items():
                context = RequestContext(
                    asset_type=asset_type,
                    data_type=DataType.FUNDAMENTAL,
                    symbol=symbol
                )
                cache_key = self._generate_cache_key(context, 'get_fundamental_data', symbol=symbol, **params)
                self._cache_result(cache_key, fundamental_data)
                result[symbol] = fundamental_data
                db_loaded_symbols.append(symbol)
            
            logger.info(f"[BATCH-DB] 从数据库加载基本面数据成功: {len(db_loaded_symbols)}/{len(uncached_symbols)}个")
            
            # 更新未缓存列表（排除已从数据库加载的）
            uncached_symbols = [s for s in uncached_symbols if s not in db_loaded_symbols]
            
        except Exception as e:
            logger.error(f"[BATCH-DB] ❌ 批量从数据库加载基本面数据失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        # 如果还有未加载的数据，调用插件获取
        if uncached_symbols:
            logger.warning(f"[BATCH-API] ⚠️  需要调用API获取基本面数据: {len(uncached_symbols)}个股票")
            for symbol in uncached_symbols:
                try:
                    fundamental_data = self.get_fundamental_data(symbol, asset_type, **params)
                    result[symbol] = fundamental_data
                except Exception as e:
                    logger.warning(f"获取股票 {symbol} 基本面数据失败: {e}")
                    result[symbol] = {}
        
        return result

    def _execute_data_request(self, context: RequestContext, method_name: str, **params) -> Any:
        """
        执行数据请求的核心逻辑

        Args:
            context: 请求上下文
            method_name: 方法名
            **params: 方法参数

        Returns:
            Any: 请求结果
        """
        start_time = datetime.now()
        self.stats["total_requests"] += 1

        try:
            # 1. 检查缓存
            cache_key = self._generate_cache_key(context, method_name, **params)
            cached_result = self._get_from_cache(cache_key)
            if cached_result is not None:
                self.stats["cache_hits"] += 1
                logger.info(f"[CACHE] 缓存命中 - 方法: {method_name}, 数据类型: {context.data_type.value}")
                return cached_result

            # 2. 新增：K线数据 DB 优先（三级缓存策略，避免直调插件走网络）
            # R254 修复：此前仅 FUNDAMENTAL 有 DB 优先分支，K 线请求直调插件方重启后走网络
            if (context.data_type == DataType.HISTORICAL_KLINE
                    and method_name in ('get_kline_data', 'get_kdata')):
                db_kline = self._load_kline_from_database(context, params)
                if db_kline is not None and not db_kline.empty:
                    self._cache_result(cache_key, db_kline)
                    self.stats["cache_hits"] += 1
                    logger.info(f"[DATABASE-SUCCESS] K线DB优先命中: {context.symbol}, 已缓存")
                    return db_kline

            # 3. 新增：对于基本面数据，先尝试从数据库读取（三级缓存策略）
            if context.data_type == DataType.FUNDAMENTAL and method_name == 'get_fundamental_data':
                symbol = params.get('symbol')
                if symbol:
                    logger.info(f"[DATABASE-QUERY] 开始查询基本面数据: {symbol}, asset_type={context.asset_type.value}")
                    db_result = self._load_fundamental_from_database(symbol, context.asset_type)
                    if db_result:
                        # 缓存数据库结果
                        self._cache_result(cache_key, db_result)
                        self.stats["cache_hits"] += 1
                        logger.info(f"[DATABASE-SUCCESS] 从数据库加载基本面数据成功: {symbol}, 已缓存")
                        return db_result
                    else:
                        logger.info(f"[DATABASE-EMPTY] ⚠️  数据库中未找到基本面数据: {symbol}，将调用插件获取")

            # 3. 获取可用插件
            logger.info(f"[TET] TET框架开始数据请求处理 - 方法: {method_name}, 资产类型: {context.asset_type.value}, 数据类型: {context.data_type.value}")

            # 检查是否指定了数据源
            specified_data_source = params.get('data_source', None)
            if specified_data_source:
                logger.info(f"[DATA_SOURCE] 指定数据源: {specified_data_source}")

            # 首先尝试获取基于能力的可用插件
            available_plugins = self.plugin_center.get_available_plugins(
                context.data_type, context.asset_type, context.market
            )

            # 如果指定了数据源，优先使用指定的数据源（即使不在能力列表中）
            if specified_data_source:
                # 尝试匹配插件名称（支持中文名称和英文名称）
                filtered_plugins = []
                data_source_lower = specified_data_source.lower()

                # 从所有注册的插件中查找匹配的数据源
                all_registered_plugins = list(self.plugin_center.data_source_plugins.keys())
                logger.debug(f"[DATA_SOURCE] 从 {len(all_registered_plugins)} 个已注册插件中查找 '{specified_data_source}'")

                for plugin_id in all_registered_plugins:
                    plugin = self.plugin_center.get_plugin(plugin_id)
                    if plugin:
                        # 获取插件信息
                        plugin_info = getattr(plugin, 'plugin_info', None)
                        if plugin_info:
                            # 安全地获取属性值，处理 None 的情况
                            plugin_name_raw = getattr(plugin_info, 'name', '')
                            plugin_name = (plugin_name_raw.lower() if plugin_name_raw else '')

                            plugin_chinese_raw = getattr(plugin_info, 'chinese_name', '')
                            plugin_chinese_name = (plugin_chinese_raw.lower() if plugin_chinese_raw else '')

                            # 检查是否匹配（支持多种匹配方式）
                            if (data_source_lower in plugin_name or
                                data_source_lower in plugin_chinese_name or
                                data_source_lower in plugin_id.lower() or
                                specified_data_source in plugin_name or
                                    specified_data_source in plugin_chinese_name):
                                filtered_plugins.append(plugin_id)
                                logger.info(f"[DATA_SOURCE] 匹配到指定数据源插件: {plugin_id} (名称: {plugin_name}/{plugin_chinese_name})")
                        else:
                            # 如果没有plugin_info，尝试从name属性匹配
                            plugin_name_attr_raw = getattr(plugin, 'name', '')
                            plugin_name_attr = (plugin_name_attr_raw.lower() if plugin_name_attr_raw else '')
                            if (data_source_lower in plugin_name_attr or
                                specified_data_source in plugin_name_attr or
                                data_source_lower in plugin_id.lower() or
                                    specified_data_source in plugin_id.lower()):
                                filtered_plugins.append(plugin_id)
                                logger.info(f"[DATA_SOURCE] 匹配到指定数据源插件: {plugin_id} (通过name属性: {plugin_name_attr})")

                if filtered_plugins:
                    available_plugins = filtered_plugins
                    logger.info(f"[DATA_SOURCE] 根据指定数据源 '{specified_data_source}' 优先使用: {available_plugins}")
                else:
                    logger.warning(f"[DATA_SOURCE] 未在已注册插件中找到数据源 '{specified_data_source}'，尝试使用能力匹配的插件。已注册插件: {all_registered_plugins}")

                    # 如果能力列表为空，使用所有已注册插件作为备选
                    if not available_plugins:
                        available_plugins = all_registered_plugins
                        logger.warning(f"[DATA_SOURCE] 能力匹配为空，使用所有已注册插件作为备选: {available_plugins}")

            if not available_plugins:
                error_msg = f"没有可用的插件支持数据类型: {context.data_type.value}/{context.asset_type.value}"
                if specified_data_source:
                    error_msg += f"\n指定的数据源 '{specified_data_source}' 无法在已注册插件中找到"
                    # 列出所有已注册的插件，帮助调试
                    registered_plugins = list(self.plugin_center.data_source_plugins.keys())
                    error_msg += f"\n已注册的插件列表: {registered_plugins}"
                raise RuntimeError(error_msg)

            logger.info(f"[DISCOVERY] TET插件发现阶段完成 - 找到 {len(available_plugins)} 个可用插件: {available_plugins}")

            # 调试信息：列出每个可用插件的详细信息
            for plugin_id in available_plugins[:5]:  # 只列出前5个，避免日志过长
                plugin = self.plugin_center.get_plugin(plugin_id)
                if plugin:
                    try:
                        plugin_info = getattr(plugin, 'plugin_info', None)
                        if plugin_info:
                            logger.debug(f"[DISCOVERY] 可用插件详情: {plugin_id} - 名称: {getattr(plugin_info, 'name', 'Unknown')}/{getattr(plugin_info, 'chinese_name', 'Unknown')}")
                    except Exception as e:
                        logger.debug(f"[DISCOVERY] 获取插件信息失败: {plugin_id} - {e}")

            # 2.1 过滤出真正可用的插件（检查连接状态）
            connected_plugins = self._filter_connected_plugins(available_plugins)
            logger.info(f"[CONNECTION] TET连接状态检查 - {len(connected_plugins)} 个插件已连接: {connected_plugins}")

            if not connected_plugins:
                logger.warning("没有已连接的插件，尝试连接可用插件...")
                connected_plugins = self._attempt_plugin_connections(available_plugins)

                if not connected_plugins:
                    raise RuntimeError(f"所有插件都无法连接，数据类型: {context.data_type.value}/{context.asset_type.value}")

            # 3. TET路由引擎选择最优插件（仅从已连接的插件中选择）
            # 如果用户指定了数据源且已连接，强制使用用户指定的数据源
            if specified_data_source and specified_data_source in connected_plugins:
                selected_plugin_id = specified_data_source
                logger.info(f"[FORCE_USE] 强制使用用户指定数据源: {selected_plugin_id}")
            else:
                # 否则使用TET路由引擎进行智能选择
                logger.info(f"[ROUTING] TET路由引擎开始智能插件选择（从 {len(connected_plugins)} 个已连接插件中选择）...")
                selected_plugin_id = self.tet_engine.select_optimal_plugin(
                    connected_plugins, context, self.plugin_center
                )

            if not selected_plugin_id:
                raise RuntimeError("TET路由引擎无法从已连接插件中选择合适的插件")

            logger.info(f"TET路由引擎选择最优插件: {selected_plugin_id} (已验证连接状态)")

            # 4. 获取插件实例
            plugin = self.plugin_center.get_plugin(selected_plugin_id)
            if not plugin:
                raise RuntimeError(f"无法获取插件实例: {selected_plugin_id}")

            # 5. 检查插件是否有指定方法
            if not hasattr(plugin, method_name):
                # 尝试其他可能的方法名
                alternate_methods = self._get_alternate_method_names(method_name)
                actual_method = None
                for alt_method in alternate_methods:
                    if hasattr(plugin, alt_method):
                        actual_method = alt_method
                        break

                if not actual_method:
                    raise RuntimeError(f"插件 {selected_plugin_id} 不支持方法 {method_name}")

                method_name = actual_method

            # 6. 执行数据获取（带质量监控和故障转移）
            logger.info(f"[EXTRACT] TET数据提取阶段开始 - 插件: {selected_plugin_id}, 方法: {method_name}")

            # 尝试执行数据获取，如果失败则进行故障转移
            result, validation_result = self._execute_with_failover(
                connected_plugins, selected_plugin_id, method_name, context, params
            )

            # 7. 更新插件指标
            execution_time = (datetime.now() - start_time).total_seconds()

            # 从故障转移结果中获取实际使用的插件ID
            actual_plugin_id = getattr(validation_result, 'plugin_id', selected_plugin_id)

            self.plugin_center.update_plugin_metrics(
                actual_plugin_id, validation_result.is_valid, execution_time, validation_result.quality_score
            )

            # 8. 更新TET路由引擎健康状态
            logger.info(f"[METRICS] TET路由引擎更新插件健康状态 - 插件: {actual_plugin_id}, 成功: {validation_result.is_valid}")
            self.tet_engine.update_plugin_health(
                actual_plugin_id, validation_result.is_valid, execution_time
            )

            # 9. 缓存结果（仅当数据有效时）
            if validation_result.is_valid and validation_result.quality_score >= 0.3:
                self._cache_result(cache_key, result)
                logger.info(f"[CACHE] TET数据缓存 - 质量分数: {validation_result.quality_score:.3f} >= 0.3，结果已缓存")

            # 10. 更新统计信息
            self.stats["successful_requests"] += 1
            self._update_avg_response_time(execution_time)

            logger.info(f"[COMPLETE] TET框架数据请求完成 - 插件: {actual_plugin_id}, 方法: {method_name}, "
                        f"用时: {execution_time:.3f}s, 质量分数: {validation_result.quality_score:.3f}")

            # 将实际使用的插件ID设置到context中，供后续标准化使用
            context.actual_plugin_id = actual_plugin_id

            return result

        except Exception as e:
            # 更新失败统计
            self.stats["failed_requests"] += 1
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_avg_response_time(execution_time)

            logger.error(f"[ERROR] TET框架数据请求失败 - 方法: {method_name}, 错误: {e}")
            raise

    def _get_alternate_method_names(self, method_name: str) -> List[str]:
        """获取替代方法名"""
        alternates = {
            'get_asset_list': ['get_stock_list', 'get_symbol_list', 'get_instruments'],
            'get_kline_data': ['get_kdata', 'get_bars', 'get_candles', 'fetch_data'],
            'get_real_time_data': ['get_realtime_data', 'get_quote', 'get_tick'],
            'get_stock_list': ['get_asset_list', 'get_symbol_list'],
        }

        return alternates.get(method_name, [])

    # ========================================================================
    # R249 修复: 公共请求上下文/执行入口
    # enhanced_duckdb_data_downloader.py:182/249/291/571 等调用
    # uni_plugin_manager.create_request_context/execute_data_request 但此前不存在,
    # 导致 UI 数据导入面板 / 增量更新调度 / 断点续传链路 AttributeError。
    # ========================================================================

    def create_request_context(self, query: StandardQuery) -> RequestContext:
        """从标准化查询创建请求上下文（供下载器等外部调用）"""
        if not isinstance(query, StandardQuery):
            raise TypeError(f"create_request_context 需要 StandardQuery, 实际: {type(query)}")

        extra = query.extra_params or {}
        context = RequestContext(
            asset_type=query.asset_type,
            data_type=query.data_type,
            symbol=query.symbol,
            market=query.market,
            priority=getattr(query, 'priority', 50),
        )
        # 挂载查询附加信息（RequestContext 本身不含这些字段）
        context.query = query
        context.start_date = query.start_date
        context.end_date = query.end_date
        context.period = getattr(query, 'period', None) or extra.get('period') or extra.get('freq')
        context.count = extra.get('count')
        context.data_source = getattr(query, 'provider', None) or extra.get('data_source')
        context.adjustment = extra.get('adjustment', 'none')
        return context

    async def execute_data_request(self, context: RequestContext,
                                   method_name: str = None, **params) -> Any:
        """执行数据请求（公共异步入口，供下载器等外部调用）

        兼容两种用法:
        1. execute_data_request(context) - 从 create_request_context 创建的上下文自动构建参数
        2. execute_data_request(context, 'get_kline_data', symbol=..., start_date=...) - 显式参数
        """
        if not params:
            params = {
                'symbol': getattr(context, 'symbol', None),
                'start_date': getattr(context, 'start_date', None),
                'end_date': getattr(context, 'end_date', None),
                'count': getattr(context, 'count', None),
                'data_source': getattr(context, 'data_source', None),
            }
            freq = getattr(context, 'period', None)
            if freq:
                params['frequency'] = freq
            if getattr(context, 'adjustment', None):
                params['adjustment'] = getattr(context, 'adjustment')

        if not method_name:
            method_name = self._resolve_method_name(context.data_type)

        # 内部为同步实现，包装到线程池避免阻塞事件循环
        return await asyncio.to_thread(
            self._execute_data_request, context, method_name, **params
        )

    def _resolve_method_name(self, data_type: DataType) -> str:
        """根据数据类型解析插件方法名"""
        if data_type == DataType.HISTORICAL_KLINE:
            return 'get_kline_data'
        elif data_type == DataType.REAL_TIME_QUOTE:
            return 'get_real_time_quotes'
        elif data_type == DataType.ASSET_LIST:
            return 'get_asset_list'
        elif data_type == DataType.FUNDAMENTAL:
            return 'get_fundamental_data'
        return 'fetch_data'

    def _generate_cache_key(self, context: RequestContext, method_name: str, **params) -> str:
        """生成缓存键"""
        import hashlib

        key_parts = [
            method_name,
            context.asset_type.value if context.asset_type else "unknown",
            context.data_type.value if context.data_type else "unknown",
            context.market or "all",
            context.symbol or "all"
        ]

        # 添加参数hash
        if params:
            # 排序参数以确保一致性
            # 重要：将 adjustment 参数加入 hash 计算，确保不同复权类型缓存独立
            sorted_params = sorted(params.items())
            param_str = str(sorted_params)
            param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
            key_parts.append(param_hash)

        return ":".join(key_parts)

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """从缓存获取数据 - 使用统一缓存服务"""
        if self._unified_cache is None:
            return None
        
        return self._unified_cache.get(cache_key, namespace=self._cache_namespace)

    def _cache_result(self, cache_key: str, result: Any) -> None:
        """缓存结果 - 使用统一缓存服务"""
        try:
            if self._unified_cache is None:
                return
            
            self._unified_cache.set(cache_key, result, ttl=self._cache_ttl, namespace=self._cache_namespace)

        except Exception as e:
            logger.warning(f"缓存结果失败: {e}")

    def _update_avg_response_time(self, execution_time: float) -> None:
        """更新平均响应时间"""
        total_requests = self.stats["total_requests"]
        current_avg = self.stats["avg_response_time"]

        if total_requests == 0:
            self.stats["avg_response_time"] = execution_time
            return

        self.stats["avg_response_time"] = (current_avg * (total_requests - 1) + execution_time) / total_requests

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        plugin_stats = self.plugin_center.get_statistics()
        quality_stats = self.risk_manager.get_quality_statistics()
        tet_routing_stats = self.tet_engine.get_routing_statistics()

        return {
            **self.stats,
            'plugin_stats': plugin_stats,
            'quality_stats': quality_stats,
            'tet_framework_stats': {
                'routing_engine': tet_routing_stats,
                'total_tet_requests': self.stats["total_requests"],
                'tet_success_rate': self.stats["successful_requests"] / max(1, self.stats["total_requests"]),
                'tet_avg_response_time': self.stats["avg_response_time"],
                'tet_cache_efficiency': self.stats["cache_hits"] / max(1, self.stats["total_requests"]),
                'tet_enabled': True,
                'framework_version': 'TET-2.0-Enhanced'
            },
            'cache_size': len(self._cache),
            'cache_hit_rate': self.stats["cache_hits"] / max(1, self.stats["total_requests"])
        }

    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        logger.info("缓存已清空")

    def _load_fundamental_from_database(self, symbol: str, asset_type: AssetType) -> Optional[Dict[str, Any]]:
        """从数据库加载基本面数据（三级缓存策略的第二层）

        Args:
            symbol: 标的代码
            asset_type: 资产类型

        Returns:
            Dict[str, Any]: 基本面数据字典，如果不存在则返回None
        """
        try:
            logger.info(f"[DATABASE] 尝试从数据库加载基本面数据: {symbol}, asset_type={asset_type.value}")
            
            # 延迟初始化数据库管理器
            if self._asset_db_manager is None:
                try:
                    from core.asset_database_manager import get_asset_separated_database_manager
                    self._asset_db_manager = get_asset_separated_database_manager()
                    logger.debug("基本面数据数据库管理器已初始化")
                except Exception as e:
                    logger.error(f"[DATABASE] 初始化数据库管理器失败: {e}")
                    return None
            
            # 从数据库加载基本面数据
            fundamental_data = self._asset_db_manager.load_fundamental_data(symbol, asset_type)
            
            if fundamental_data:
                logger.info(f"[DATABASE] 从数据库成功加载基本面数据: {symbol}, 字段数={len(fundamental_data)}")
                return fundamental_data
            else:
                logger.info(f"[DATABASE] ⚠️  数据库中未找到基本面数据: {symbol}")
                return None
        except Exception as e:
            logger.error(f"[DATABASE] ❌ 从数据库加载基本面数据失败: {symbol}, {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def _load_kline_from_database(self, context: RequestContext, params: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """从数据库加载K线数据（DB优先架构，避免直调插件走网络）

        R254 修复：新增K线 DB 优先分支（此前仅 FUNDAMENTAL 有 DB 优先）。

        Args:
            context: 请求上下文
            params: 请求参数（symbol/start_date/end_date/period/frequency/freq）

        Returns:
            Optional[pd.DataFrame]: 数据库K线数据（timestamp 列已映射为 datetime，
            与 TET 标准化输出/下游 df['datetime'] 依赖兼容）；无数据、覆盖不足或
            异常时返回 None（视为 DB miss，继续插件流程）。
        """
        try:
            symbol = getattr(context, 'symbol', None) or params.get('symbol')
            if not symbol:
                return None

            # 延迟初始化数据库管理器
            if self._asset_db_manager is None:
                from core.asset_database_manager import get_asset_separated_database_manager
                self._asset_db_manager = get_asset_separated_database_manager()

            start_date = getattr(context, 'start_date', None) or params.get('start_date')
            end_date = getattr(context, 'end_date', None) or params.get('end_date')
            period = (getattr(context, 'period', None)
                      or params.get('period') or params.get('frequency') or params.get('freq'))
            frequency = None
            if period:
                try:
                    from core.plugin_types import Period
                    frequency = Period.to_duckdb_frequency(period)
                except Exception:
                    frequency = str(period)

            logger.info(f"[DATABASE-QUERY] 开始查询K线数据: {symbol}, asset_type={context.asset_type.value}, "
                        f"frequency={frequency}, range=({start_date}, {end_date})")
            df = self._asset_db_manager.load_kline_data(
                symbol, context.asset_type,
                start_date=start_date, end_date=end_date, frequency=frequency
            )

            if df is None or df.empty:
                logger.info(f"[DATABASE-EMPTY] ⚠️ 数据库中未找到K线数据: {symbol}，将调用插件获取")
                return None

            # 覆盖度校验（防坑）：请求带日期范围时，首末 timestamp 必须覆盖请求范围，不足视为 miss
            if not self._kline_db_coverage_ok(df, start_date, end_date):
                logger.info(f"[DATABASE-COVERAGE] 数据库K线数据未覆盖请求范围: {symbol}，将调用插件获取")
                return None

            # 返回格式兼容：timestamp 列映射为 datetime 列（下游依赖 df['datetime']，
            # 参照 unified_data_manager._get_kdata_from_duckdb 的处理）
            if 'timestamp' in df.columns:
                df = df.rename(columns={'timestamp': 'datetime'})
            df['datetime'] = pd.to_datetime(df['datetime'])

            logger.info(f"[DATABASE-SUCCESS] 从数据库加载K线数据成功: {symbol}, 记录数={len(df)}")
            return df
        except Exception as e:
            logger.error(f"[DATABASE] ❌ 从数据库加载K线数据失败: {getattr(context, 'symbol', '')}, {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def _kline_db_coverage_ok(self, df: pd.DataFrame,
                              start_date=None, end_date=None) -> bool:
        """校验数据库K线数据是否覆盖请求范围（覆盖不足视为 DB miss，防返回残缺数据）"""
        if df is None or df.empty:
            return False
        # 未指定日期范围（如 count 模式）时视为覆盖
        if start_date is None and end_date is None:
            return True
        try:
            ts_col = df['timestamp'] if 'timestamp' in df.columns else pd.to_datetime(df['datetime'])
            first_ts = pd.Timestamp(ts_col.min())
            last_ts = pd.Timestamp(ts_col.max())
            if start_date is not None and first_ts > pd.Timestamp(start_date):
                return False
            if end_date is not None and last_ts < pd.Timestamp(end_date):
                return False
            return True
        except Exception:
            return False

    def get_plugin_status(self) -> Dict[str, Any]:
        """获取所有插件状态"""
        return {
            'plugin_center': self.plugin_center.get_statistics(),
            'tet_engine': self.tet_engine.get_all_plugin_status(),
            'quality_manager': self.risk_manager.get_quality_statistics()
        }

    def get_tet_framework_status(self) -> Dict[str, Any]:
        """获取TET框架详细状态"""
        tet_stats = self.tet_engine.get_routing_statistics()
        plugin_stats = self.plugin_center.get_statistics()

        return {
            'framework_info': {
                'name': 'TET Framework (Transform-Extract-Transform)',
                'version': 'TET-2.0-Enhanced',
                'status': 'Active',
                'description': '智能数据源路由和插件管理框架'
            },
            'routing_engine': {
                'registered_plugins': tet_stats.get('registered_plugins', 0),
                'intelligent_routing_enabled': tet_stats.get('intelligent_routing_enabled', False),
                'adaptive_weights_enabled': tet_stats.get('adaptive_weights_enabled', False),
                'cache_size': tet_stats.get('cache_size', 0),
                'strategy_performance': tet_stats.get('strategy_performance', {})
            },
            'plugin_center': {
                'total_plugins': plugin_stats.get('total_plugins', 0),
                'active_plugins': plugin_stats.get('active_plugins', 0),
                'data_source_plugins': plugin_stats.get('data_source_plugins', 0)
            },
            'performance_metrics': {
                'total_requests': self.stats["total_requests"],
                'successful_requests': self.stats["successful_requests"],
                'failed_requests': self.stats["failed_requests"],
                'success_rate': self.stats["successful_requests"] / max(1, self.stats["total_requests"]),
                'avg_response_time': self.stats["avg_response_time"],
                'cache_hits': self.stats["cache_hits"],
                'cache_hit_rate': self.stats["cache_hits"] / max(1, self.stats["total_requests"])
            },
            'data_quality': self.risk_manager.get_quality_statistics()
        }

    def _filter_connected_plugins(self, plugin_ids: List[str]) -> List[str]:
        """过滤出已连接的插件"""
        connected_plugins = []

        for plugin_id in plugin_ids:
            try:
                plugin = self.plugin_center.get_plugin(plugin_id)
                if plugin and self._check_plugin_connection(plugin, plugin_id):
                    connected_plugins.append(plugin_id)
                else:
                    logger.debug(f"插件 {plugin_id} 未连接或不可用")
            except Exception as e:
                logger.warning(f"检查插件连接状态失败 {plugin_id}: {e}")

        return connected_plugins

    def _check_plugin_connection(self, plugin, plugin_id: str) -> bool:
        """检查插件连接状态"""
        try:
            # 检查插件是否有连接状态方法
            if hasattr(plugin, 'is_connected'):
                return plugin.is_connected()
            elif hasattr(plugin, 'connected'):
                return plugin.connected
            elif hasattr(plugin, '_connected'):
                return plugin._connected
            elif hasattr(plugin, 'connection_status'):
                return plugin.connection_status
            else:
                # 如果没有连接状态方法，尝试调用一个轻量级方法来测试
                if hasattr(plugin, 'get_plugin_info'):
                    plugin.get_plugin_info()
                    return True
                elif hasattr(plugin, 'health_check'):
                    result = plugin.health_check()
                    return getattr(result, 'is_healthy', True)
                else:
                    # R248: 原实现默认认为插件可用（恒 True），是无连接状态检查能力插件的
                    # 隐性"恒已连接"通道。改为判定未连接（宁缺毋滥，宁可触发重连也不误判可用）。
                    logger.debug(f"插件 {plugin_id} 没有连接状态检查方法，判定为未连接")
                    return False
        except Exception as e:
            logger.warning(f"插件连接检查异常 {plugin_id}: {e}")
            return False

    def _attempt_plugin_connections(self, plugin_ids: List[str]) -> List[str]:
        """尝试连接插件"""
        connected_plugins = []

        for plugin_id in plugin_ids:
            try:
                plugin = self.plugin_center.get_plugin(plugin_id)
                if plugin and self._attempt_plugin_connection(plugin, plugin_id):
                    connected_plugins.append(plugin_id)
                    logger.info(f"插件连接成功: {plugin_id}")
                else:
                    logger.warning(f" 插件连接失败: {plugin_id}")
            except Exception as e:
                logger.error(f"[ERROR] 插件连接异常 {plugin_id}: {e}")

        return connected_plugins

    def _attempt_plugin_connection(self, plugin, plugin_id: str) -> bool:
        """尝试连接单个插件"""
        try:
            # 如果插件已经连接，直接返回
            if self._check_plugin_connection(plugin, plugin_id):
                return True

            # 尝试连接插件
            if hasattr(plugin, 'connect'):
                result = plugin.connect()
                if result:
                    logger.info(f"插件 {plugin_id} 连接成功")
                    return True
                else:
                    logger.warning(f"插件 {plugin_id} 连接失败")
                    return False
            elif hasattr(plugin, 'initialize'):
                plugin.initialize()
                logger.info(f"插件 {plugin_id} 初始化成功")
                return True
            else:
                # 没有连接方法，假设插件可用
                logger.debug(f"插件 {plugin_id} 没有连接方法，假设可用")
                return True

        except Exception as e:
            logger.error(f"插件连接尝试失败 {plugin_id}: {e}")
            return False

    def _execute_with_failover(self, connected_plugins: List[str], primary_plugin_id: str,
                               method_name: str, context: RequestContext, params: Dict[str, Any]):
        """带故障转移的执行方法"""
        failed_plugins = []
        last_error = None

        # R254 修复：成功结果统一在循环外处理（落库职责与循环体解耦，全失败时不再重复落库）
        success_result = None
        success_validation = None

        # 将主选插件放在第一位，其他插件作为备选
        plugin_order = [primary_plugin_id] + [p for p in connected_plugins if p != primary_plugin_id]

        for attempt, plugin_id in enumerate(plugin_order, 1):
            try:
                logger.info(f"[RETRY] 尝试插件 {plugin_id} (第 {attempt}/{len(plugin_order)} 次尝试)")

                plugin = self.plugin_center.get_plugin(plugin_id)
                if not plugin:
                    logger.warning(f" 无法获取插件实例: {plugin_id}")
                    failed_plugins.append(plugin_id)
                    continue

                # 再次检查连接状态
                if not self._check_plugin_connection(plugin, plugin_id):
                    logger.warning(f" 插件 {plugin_id} 连接状态异常，尝试重连...")
                    if not self._attempt_plugin_connection(plugin, plugin_id):
                        logger.error(f"[ERROR] 插件 {plugin_id} 重连失败")
                        failed_plugins.append(plugin_id)
                        continue

                # 检查插件是否支持该方法
                if not hasattr(plugin, method_name):
                    alternate_methods = self._get_alternate_method_names(method_name)
                    actual_method = None
                    for alt_method in alternate_methods:
                        if hasattr(plugin, alt_method):
                            actual_method = alt_method
                            break

                    if not actual_method:
                        logger.warning(f" 插件 {plugin_id} 不支持方法 {method_name}")
                        failed_plugins.append(plugin_id)
                        continue

                    method_name = actual_method

                # 执行方法
                method = getattr(plugin, method_name)

                # 准备参数
                method_params = params.copy()
                if method_name == 'get_asset_list' and 'asset_type' not in method_params:
                    method_params['asset_type'] = context.asset_type
                if 'market' not in method_params and context.market:
                    method_params['market'] = context.market

                # 参数名称映射（不同插件可能使用不同的参数名）
                # 处理K线数据的参数转换
                if method_name in ('get_kline_data', 'get_kdata'):
                    # frequency 可能需要转换为 period（通达信使用）或 freq（某些插件使用）
                    if 'frequency' in method_params:
                        freq_value = method_params.pop('frequency')
                        # 对于 get_kdata 方法，通常使用 freq 而不是 frequency
                        if method_name == 'get_kdata':
                            method_params['freq'] = freq_value
                        # 对于 get_kline_data，某些插件使用 period
                        elif method_name == 'get_kline_data':
                            method_params['period'] = freq_value

                # 移除插件不支持的参数
                # data_source参数用于插件选择，不应传递给插件方法本身
                if 'data_source' in method_params:
                    method_params.pop('data_source')

                # 执行并监控
                result, validation_result = self.risk_manager.execute_with_monitoring(
                    plugin_id, method, **method_params
                )

                if validation_result.is_valid:
                    if attempt > 1:
                        logger.info(f"[FAILOVER] TET故障转移成功 - 插件: {plugin_id} (第 {attempt} 次尝试)")
                    else:
                        logger.info(f"TET数据获取成功 - 插件: {plugin_id}")

                    # 更新TET路由引擎，记录成功的插件
                    self.tet_engine.record_plugin_performance(
                        plugin_id, True, 0.1, context  # 成功执行，响应时间很短
                    )

                    # R254 修复：记录成功结果后跳出循环，落库统一在循环外执行一次
                    success_result = result
                    success_validation = validation_result
                    break
                else:
                    logger.warning(f" 插件 {plugin_id} 返回数据质量不合格: {validation_result.quality_score}")
                    failed_plugins.append(plugin_id)
                    last_error = f"数据质量不合格: {validation_result.quality_score}"

                    # R249 修复：is_valid=False（数据质量不合格）也应记录插件性能失败，
                    # 与 except 分支保持一致，避免 TET 路由引擎对失败插件的健康度评估失真
                    self.tet_engine.record_plugin_performance(
                        plugin_id, False, 1.0, context  # 失败执行，响应时间较长
                    )

            except Exception as e:
                logger.error(f"[ERROR] 插件 {plugin_id} 执行失败: {e}")
                failed_plugins.append(plugin_id)
                last_error = str(e)

                # 更新TET路由引擎，记录失败的插件
                self.tet_engine.record_plugin_performance(
                    plugin_id, False, 1.0, context  # 失败执行，响应时间较长
                )

        # R254 修复：落库块移出 for 循环（职责解耦），failover 成功后统一落库一次
        if success_result is not None and success_validation is not None:
            self._persist_fetched_data(context, params, success_result, success_validation)
            return success_result, success_validation

        # 所有插件都失败了
        error_msg = f"TET故障转移失败 - 所有插件都无法提供有效数据。失败插件: {failed_plugins}"
        if last_error:
            error_msg += f"，最后错误: {last_error}"

        logger.error(f"[ERROR] {error_msg}")
        raise RuntimeError(error_msg)

    def _persist_fetched_data(self, context: RequestContext, params: Dict[str, Any],
                              result: Any, validation_result: Any) -> None:
        """插件获取数据后统一落库（K线 DataFrame / 基本面 dict → DuckDB）

        R254 修复：
        - 落库块整体移出 _execute_with_failover 的 for 循环，全失败时 0 次落库，
          主插件/备选插件成功时均仅落库一次；
        - data_source 使用真实插件 id（validation_result.plugin_id），
          替代硬编码 'tet_plugin'，保证 DuckDB 数据源可追溯；
        - 落库条件扩展 FUNDAMENTAL：单条 dict → 单行 DataFrame → 补 symbol 列落库。
        落库失败仅告警，不阻断数据返回。
        """
        persist_target = None
        data_type = getattr(context, 'data_type', None)

        if (data_type == DataType.HISTORICAL_KLINE
                and isinstance(result, pd.DataFrame)
                and not result.empty):
            persist_target = result.copy()
        elif (data_type == DataType.FUNDAMENTAL
                and isinstance(result, dict)
                and result):
            # 基本面单条字典 → 单行 DataFrame（fundamentals 表已在表名映射中）
            persist_target = pd.DataFrame([result])

        if persist_target is None:
            return

        try:
            if self._asset_db_manager is None:
                from core.asset_database_manager import get_asset_separated_database_manager
                self._asset_db_manager = get_asset_separated_database_manager()

            persist_df = persist_target
            # R255 修复：data_source 溯源优先级 context.actual_plugin_id > validation_result.plugin_id > 'tet_plugin'。
            # 此前仅 getattr(validation_result, 'plugin_id', None)，而 execute_with_monitoring
            # 返回的匿名 ValidationResult 无 plugin_id 属性 → 恒回退硬编码 'tet_plugin'，
            # DuckDB 数据源不可追溯。修复后 validation_result.plugin_id 为真实插件 id；
            # context.actual_plugin_id 兜底外部直接调用本方法且 validation 无 plugin_id 的场景
            # （'tet_plugin' 保留为最低优先级最后兜底）。
            data_source = (getattr(context, 'actual_plugin_id', None)
                           or getattr(validation_result, 'plugin_id', None)
                           or 'tet_plugin')

            if data_type == DataType.HISTORICAL_KLINE:
                # 时间列统一为timestamp（DuckDB K线表结构）
                if 'timestamp' not in persist_df.columns:
                    # R275: 兼容插件返回的 datetime 索引（东财/baostock 均 set_index('datetime')）
                    if 'datetime' not in persist_df.columns and 'date' not in persist_df.columns:
                        if isinstance(persist_df.index, pd.DatetimeIndex) or persist_df.index.name in ('datetime', 'date'):
                            persist_df = persist_df.reset_index()
                            # R292 修复：无命名 DatetimeIndex reset_index 后新列为 'index'，
                            # 统一改名为 datetime（与 unified_data_manager._persist_kdata_to_duckdb 一致），
                            # 否则 timestamp 列无法构建 → 违反 NOT NULL 约束落库失败。
                            if 'index' in persist_df.columns and 'datetime' not in persist_df.columns:
                                persist_df = persist_df.rename(columns={'index': 'datetime'})
                    # R290: 新增 timestamp 后删除 datetime/date 列，避免与
                    # asset_database_manager._filter_dataframe_columns 的 datetime→timestamp
                    # 映射叠加产生重复列 → DuckDB "Duplicate column name timestamp" 报错。
                    if 'datetime' in persist_df.columns:
                        persist_df['timestamp'] = pd.to_datetime(persist_df['datetime'])
                        persist_df = persist_df.drop(columns=['datetime'])
                    elif 'date' in persist_df.columns:
                        persist_df['timestamp'] = pd.to_datetime(persist_df['date'])
                        persist_df = persist_df.drop(columns=['date'])
                # 补齐关键列，保证落库后可按symbol/frequency查询
                if 'symbol' not in persist_df.columns:
                    persist_df['symbol'] = getattr(context, 'symbol', None) or ''
                if 'frequency' not in persist_df.columns:
                    try:
                        from core.plugin_types import Period
                        period = params.get('period') or params.get('frequency') or params.get('freq') or 'D'
                        persist_df['frequency'] = Period.to_duckdb_frequency(period)
                    except Exception:
                        pass
            elif data_type == DataType.FUNDAMENTAL:
                # 基本面落库：补 symbol 列（fundamentals 表主键）
                if 'symbol' not in persist_df.columns:
                    persist_df['symbol'] = getattr(context, 'symbol', None) or ''

            if 'data_source' not in persist_df.columns:
                persist_df['data_source'] = data_source

            self._asset_db_manager.store_standardized_data(
                persist_df, context.asset_type, data_type)
        except Exception as e:
            logger.warning(f"插件数据落库失败: {getattr(context, 'symbol', '')} - {e}")

    def shutdown(self) -> None:
        """关闭管理器"""
        try:
            self._executor.shutdown(wait=True)
            logger.info("统一插件数据管理器已关闭")
        except Exception as e:
            logger.error(f"关闭统一插件数据管理器失败: {e}")


# 全局实例管理
_uni_plugin_data_manager: Optional[UniPluginDataManager] = None


def get_uni_plugin_data_manager() -> Optional[UniPluginDataManager]:
    """获取统一插件数据管理器实例"""
    return _uni_plugin_data_manager


def set_uni_plugin_data_manager(manager: UniPluginDataManager) -> None:
    """设置统一插件数据管理器实例"""
    global _uni_plugin_data_manager
    _uni_plugin_data_manager = manager
    logger.info("统一插件数据管理器全局实例已设置")
