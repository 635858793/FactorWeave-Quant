from loguru import logger
"""
统一数据管理器

负责协调各服务的数据加载请求，避免重复数据加载，提供统一的数据访问接口。
集成FactorWeave-Quant数据管理功能，基于TET框架和插件架构。
"""

import threading
import time
import re
from typing import Dict, Any, Optional, List, Callable, Set, Union, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import asyncio
from asyncio import Future as AsyncioFuture
import numpy as np
import os
import traceback

from ..database.unified_sqlite_access import UnifiedSQLiteAccess


def _build_data_source_router():
    """从系统配置构造 DataSourceRouter（R275 扩展: 健康检查间隔 + 熔断阈值可配置化）

    读取 DataConfig（config/data 段）中的 health_check_interval 与 circuit_* 字段，
    配置缺失/异常时回退到 DataSourceRouter 默认值，不影响启动。
    """
    from ..data_source_router import DataSourceRouter, CircuitBreakerConfig
    from utils.config_types import DataConfig

    data_config = DataConfig()
    try:
        from core.config import get_config_manager
        config_mgr = get_config_manager()
        data_cfg = config_mgr.get('data')
        if isinstance(data_cfg, dict):
            data_config = DataConfig.from_dict(data_cfg)
    except Exception as e:
        logger.warning(f"读取数据源路由配置失败，使用默认值: {e}")

    return DataSourceRouter(
        health_check_interval=data_config.health_check_interval,
        circuit_breaker_config=CircuitBreakerConfig(
            failure_threshold=data_config.circuit_failure_threshold,
            failure_rate_threshold=data_config.circuit_failure_rate,
            recovery_timeout_ms=data_config.circuit_recovery_timeout_ms,
            half_open_max_calls=data_config.circuit_half_open_max_calls,
            sliding_window_size=data_config.circuit_sliding_window_size,
        )
    )

try:
    from ..events import EventBus, DataUpdateEvent
    EVENTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"events模块导入失败: {e}")
    EventBus = None
    DataUpdateEvent = None
    EVENTS_AVAILABLE = False

try:
    from ..containers import ServiceContainer, get_service_container
except ImportError as e:
    logger.warning(f"containers模块导入失败: {e}")
    ServiceContainer = None
    get_service_container = None

try:
    from ..plugin_types import AssetType, DataType
except ImportError as e:
    logger.warning(f"plugin_types模块导入失败: {e}")
    AssetType = None
    DataType = None

try:
    from ..tet_data_pipeline import TETDataPipeline, StandardQuery, StandardData
except ImportError as e:
    logger.warning(f"tet_data_pipeline模块导入失败: {e}")
    TETDataPipeline = None
    StandardQuery = None
    StandardData = None

try:
    from .asset_fallback_loader import AssetFallbackLoader
except ImportError as e:
    logger.warning(f"AssetFallbackLoader导入失败: {e}")
    AssetFallbackLoader = None

# 导入UniPluginDataManager
try:
    from .uni_plugin_data_manager import UniPluginDataManager
except ImportError as e:
    logger.warning(f"UniPluginDataManager导入失败: {e}")
    UniPluginDataManager = None

# 系统基于DuckDB优先架构和TET框架运行

# 传统数据源已迁移到TET+Plugin架构，不再直接导入
# 数据源现在通过UniPluginDataManager统一管理

# 导入缓存和工具
try:
    # from utils.cache import Cache  # 已统一使用MultiLevelCacheManager
    # log_structured已替换为直接的logger调用
    from core.performance import measure_performance
except ImportError as e:
    logger.warning(f"工具模块导入失败: {e}")
    # Cache = None  # 已统一使用MultiLevelCacheManager

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'factorweave_system.sqlite')


# ---- R257 跨组件财报表名治理：分裂期旧表惰性迁移 ----
# 统一插件名 DEFAULT_FINANCIAL_PLUGIN 定义于 core/database/table_manager.py
_financial_migration_done = False
_financial_migration_lock = threading.Lock()

# R257 治理前两组件各自生成的旧财报表名（SIMPLE 模式 {data_type}_{plugin_name}_default）
_LEGACY_FINANCIAL_TABLES = (
    "financial_statement_unified_data_manager_default",
    "financial_statement_enhanced_duckdb_downloader_default",
)


def _financial_table_row_count(operations, db_path: str, table_name: str) -> int:
    """查询 duckdb_tables() 中指定表是否存在（COUNT(*)）；异常/空结果安全返回 0。

    兼容 execute_query 返回 list[dict] 或 DataFrame 两种 data 格式。
    """
    try:
        result = operations.execute_query(
            db_path,
            "SELECT COUNT(*) AS cnt FROM duckdb_tables() WHERE table_name = ?",
            [table_name],
        )
        if result is None or not getattr(result, "success", False):
            return 0
        data = getattr(result, "data", None)
        if data is None:
            return 0
        if isinstance(data, list):
            if not data:
                return 0
            first = data[0]
            if isinstance(first, dict):
                return int(first.get("cnt", 0))
            return int(first[0]) if first else 0
        if getattr(data, "empty", True):
            return 0
        if "cnt" in getattr(data, "columns", []):
            return int(data["cnt"].iloc[0])
        return int(data.iloc[0, 0])
    except Exception:
        return 0


def get_unified_data_manager() -> Optional['UnifiedDataManager']:
    """
    获取统一数据管理器的实例

    Returns:
        统一数据管理器实例，如果未注册则返回None
    """
    try:
        container = get_service_container()
        if container:
            return container.resolve(UnifiedDataManager)
        return None
    except Exception as e:
        logger.error(f"获取统一数据管理器失败: {e}")
        return None


class DataRequestStatus(Enum):
    """数据请求状态"""
    PENDING = "pending"
    LOADING = "loading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DataRequest:
    """数据请求"""
    request_id: str
    symbol: str  # 统一使用symbol替代stock_code
    asset_type: AssetType = AssetType.STOCK_A  # 新增资产类型支持（A股）
    data_type: str = 'kdata'  # 'kdata', 'indicators', 'analysis'
    period: str = 'D'
    time_range: int = 365
    parameters: Dict[str, Any] = None
    priority: int = 0  # 0=高优先级, 1=中优先级, 2=低优先级
    future: Optional[AsyncioFuture] = None  # 用于async/await
    timestamp: float = 0
    status: DataRequestStatus = DataRequestStatus.PENDING

    # 向后兼容属性
    @property
    def stock_code(self) -> str:
        """
        清理缓存 - 使用统一的MultiLevelCacheManager向后兼容：股票代码"""
        return self.symbol

    @stock_code.setter
    def stock_code(self, value: str):
        """向后兼容：设置股票代码"""
        self.symbol = value

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()
        if self.parameters is None:
            self.parameters = {}

    def __eq__(self, other):
        if not isinstance(other, DataRequest):
            return NotImplemented
        return (self.symbol == other.symbol and
                self.asset_type == other.asset_type and
                self.data_type == other.data_type and
                self.period == other.period and
                self.time_range == other.time_range and
                self.parameters == other.parameters)

    def __hash__(self):
        # The hash should be based on the immutable fields that define the request's identity
        # Note: self.parameters is mutable, so we convert it to a string representation of its items
        param_tuple = tuple(sorted((self.parameters or {}).items()))
        return hash((self.symbol,
                     self.asset_type,
                     self.data_type,
                     self.period,
                     self.time_range,
                     param_tuple))


# 线程本地防重入守卫 (R204-P0-3): 阻断 UDM get_stock_list → get_asset_list → StockService →
# StockManager → DataAccess → StockRepository → data_manager.get_stock_list 无限递归环
_recursion_guard = threading.local()


class UnifiedDataManager:
    """
    统一数据管理器

    功能：
    1. 协调数据加载请求
    2. 避免重复数据加载
    3. 提供统一的数据访问接口
    4. 管理数据缓存
    5. 优化数据加载性能
    6. 支持TET数据管道（Transform-Extract-Transform）
    7. 多资产类型数据处理
    8. 集成FactorWeave-Quant、东方财富、新浪等多数据源
    9. 行业数据管理
    10. SQLite数据库支持
    """

    # R285 修复4：DB 直读质量门槛（0-100 口径，与落库准入阈值一致）。
    # DB 命中但质量分低于该值时视为"低质量单份数据"，触发回源重拉。
    _DB_QUALITY_MIN_SCORE = 60.0

    def __init__(self, service_container: ServiceContainer = None, event_bus: EventBus = None, max_workers: int = 3):
        """
        初始化统一数据管理器

        Args:
            service_container: 服务容器 (可选)
            event_bus: 事件总线 (可选)
            max_workers: 最大工作线程数
        """
        # 兼容性处理 - 允许None参数
        from ..containers import get_service_container
        self.service_container = service_container or get_service_container()
        self.event_bus = event_bus
        self.loop = None  # 延迟初始化，在异步方法中获取

        # 线程池
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="DataManager")

        # 请求管理
        self._pending_requests: Dict[str, DataRequest] = {}
        self._active_requests: Dict[str, DataRequest] = {}
        self._completed_requests: Dict[str, DataRequest] = {}
        self._request_lock = threading.Lock()

        self._cache_ttl = 300  # 5分钟缓存TTL

        # R263 增量更新状态：防止无谓的重复联网拉取
        # _kdata_history_exhausted: {(asset,freq) -> datetime} 历史已到尽头（再往前拉无数据）
        # _kdata_incremental_checked: {(asset,freq) -> datetime} 最近一次增量检查时间（TTL内不重复）
        self._kdata_history_exhausted: Dict[str, datetime] = {}
        self._kdata_incremental_checked: Dict[str, datetime] = {}
        self._kdata_incremental_ttl = 6 * 3600  # 增量检查间隔 6 小时

        # R238-P1-3 修复: clear_cache/_get_from_cache 依赖的缓存属性必须在 __init__ 定义,
        # 否则 dispose 调用 clear_cache 时抛 AttributeError (生产关闭路径必崩)
        self._cache_lock = threading.Lock()
        self._data_cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}

        self._stock_info_cache = None

        # SQL注入防护：允许的列名白名单
        self._ALLOWED_STOCK_COLUMNS = frozenset({
            'code', 'name', 'industry', 'area', 'market', 'list_date',
            'total_shares', 'circulating_shares', 'total_market_cap',
            'pe', 'pb', 'roe', 'eps', 'revenue', 'profit'
        })
        self._ALLOWED_MARKET_COLUMNS = frozenset({
            'code', 'trade_date', 'open', 'high', 'low', 'close',
            'volume', 'amount', 'change', 'pct_change', 'turnover'
        })

        self.cache_manager = None
        try:
            from core.containers import get_service_container
            from core.services.cache_service import CacheService
            
            container = get_service_container()
            if container and container.is_registered(CacheService):
                self.cache_manager = container.resolve(CacheService)
                logger.info("统一缓存服务已初始化")
        except Exception as e:
            logger.warning(f"获取统一缓存服务失败: {e}，将使用延迟初始化")

        # 数据库连接（兼容模式：提供与sqlite3.connect相同的接口）
        try:
            self.db_access = UnifiedSQLiteAccess.get_instance(DB_PATH)
            # 兼容旧代码：提供一个获取连接的上下文管理器
            self._db_lock = threading.Lock()
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            self.db_access = None
            self._db_lock = None

        # 初始化UniPluginDataManager (延迟模式)

        self._uni_plugin_manager = None

        self._is_initialized = False

        # FactorWeave-Quant已移除，系统基于TET框架和插件架构运行
        self._invalid_stocks_cache = set()
        self._valid_stocks_cache = set()

        # 多数据源支持 - 默认使用TET框架
        self._current_source = 'tet_framework'
        self._data_sources = {}

        # 插件化数据源管理
        self._plugin_data_sources = {}
        self._registered_data_sources = {}  # 存储已注册的数据源信息
        self._data_source_priorities = {
            'stock': ['eastmoney', 'sina', 'tonghuashun'],
            'futures': [],
            'crypto': []
        }
        self._routing_strategy = 'priority'
        self._health_status = {}
        self._plugin_lock = threading.RLock()

        # 行业管理器初始化
        try:
            from ..industry_manager import IndustryManager
            self.industry_manager = IndustryManager()
            self._load_industry_data()
        except Exception as e:
            logger.warning(f"行业管理器初始化失败: {e}")
            self.industry_manager = None

        # 去重机制
        self._request_dedup: Dict[str, Set[DataRequest]] = {}
        self._dedup_lock = threading.Lock()

        # 请求跟踪
        self.request_tracker: Dict[str, Dict[str, Any]] = {}
        self.request_tracker_lock = threading.Lock()

        # TET数据管道支持
        self.tet_enabled = True  # 默认启用TET模式
        self.tet_pipeline = None

        # 数据处理策略
        from ..tet_data_pipeline import HistoryDataStrategy, RealtimeDataStrategy
        self.history_data_strategy = HistoryDataStrategy()
        self.realtime_data_strategy = RealtimeDataStrategy()

        # 初始化TET管道
        try:
            from ..tet_data_pipeline import TETDataPipeline
            from ..data_source_router import DataSourceRouter

            # 创建数据源路由器（R275 扩展: 从配置读取健康检查间隔/熔断阈值；
            # R279 改为优先复用 DI 容器单例，消除实例分裂）
            data_source_router = self._resolve_or_create_data_source_router()

            # 初始化TET管道
            self.tet_pipeline = TETDataPipeline(data_source_router)
            logger.info("TET数据管道初始化成功")

            # 注册FactorWeave-Quant数据源插件到路由器和TET管道 - 删除手动注册，使用自动发现机制
            # self._register_hikyuu_plugin_to_router(data_source_router)

            # 插件发现状态标记
            self._plugins_discovered = False

            # 注册传统数据源到TET路由器
            self._register_legacy_data_sources_to_router()

            # 延迟插件发现 - 不在初始化时立即执行
            # 将在服务引导完成后通过外部调用执行
            logger.info("TET数据管道初始化完成，等待插件发现...")

        except ImportError as e:
            logger.error(f"TET数据管道模块导入失败: {e}")
            logger.info("禁用TET数据管道，使用传统模式")
            self.tet_enabled = False
            self.tet_pipeline = None
        except Exception as e:
            logger.warning(f"TET数据管道初始化失败: {e}")
            logger.info("降级到传统模式")
            self.tet_enabled = False
            self._plugins_discovered = False

        # 板块数据服务初始化
        self._sector_data_service = None
        self._initialize_sector_service()

        # 统计信息
        self._stats = {
            'requests_total': 0,
            'requests_completed': 0,
            'requests_failed': 0,
            'requests_cancelled': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }

        # 初始化 AssetFallbackLoader
        self._init_fallback_loader()

        # DuckDB集成支持 - 直接集成到现有管理器
        self._init_duckdb_integration()

        logger.info("统一数据管理器构造完成")

        # 从配置服务读取缓存启用状态
        try:
            config_service = self.service_container.get('config_service')
            if config_service:
                self.cache_enabled = config_service.get('data.cache_enabled', True)
                logger.info(f"缓存启用状态: {self.cache_enabled}")
            else:
                self.cache_enabled = True  # 配置服务不可用时默认启用缓存
                logger.warning("配置服务不可用，使用默认缓存设置（已启用）")
        except Exception as e:
            self.cache_enabled = True  # 出错时默认启用缓存
            logger.warning(f"读取缓存配置失败，使用默认值: {e}")

    def _init_fallback_loader(self):
        """初始化 AssetFallbackLoader"""
        try:
            if AssetFallbackLoader is None:
                logger.warning("⚠️ AssetFallbackLoader 不可用，跳过初始化")
                self.fallback_loader = None
                return

            # 从服务容器解析各服务
            stock_service = None
            index_service = None
            fund_service = None
            bond_service = None

            if self.service_container:
                try:
                    from .stock_service import StockService
                    if self.service_container.is_registered(StockService):
                        stock_service = self.service_container.resolve(StockService)
                        logger.info("StockService 解析成功")
                except Exception as e:
                    logger.warning(f"⚠️ StockService 解析失败: {e}")

                try:
                    from .index_service import IndexService
                    if self.service_container.is_registered(IndexService):
                        index_service = self.service_container.resolve(IndexService)
                        logger.info("IndexService 解析成功")
                    else:
                        from .index_service import get_index_service
                        index_service = get_index_service()
                        logger.info("IndexService 实例获取成功")
                except Exception as e:
                    logger.warning(f"⚠️ IndexService 解析失败: {e}")

                try:
                    from .fund_service import FundService
                    if self.service_container.is_registered(FundService):
                        fund_service = self.service_container.resolve(FundService)
                        logger.info("FundService 解析成功")
                    else:
                        from .fund_service import get_fund_service
                        fund_service = get_fund_service()
                        logger.info("FundService 实例获取成功")
                except Exception as e:
                    logger.warning(f"⚠️ FundService 解析失败: {e}")

                try:
                    from .bond_service import BondService
                    if self.service_container.is_registered(BondService):
                        bond_service = self.service_container.resolve(BondService)
                        logger.info("BondService 解析成功")
                    else:
                        from .bond_service import get_bond_service
                        bond_service = get_bond_service()
                        logger.info("BondService 实例获取成功")
                except Exception as e:
                    logger.warning(f"⚠️ BondService 解析失败: {e}")

            # 加密货币 API 配置
            crypto_api_config = {
                'provider': 'binance',
                'enabled': False,
                'api_key': None,
                'api_secret': None
            }

            # 创建 AssetFallbackLoader 实例
            self.fallback_loader = AssetFallbackLoader(
                duckdb_manager=self.duckdb_manager if hasattr(self, 'duckdb_manager') else None,
                stock_service=stock_service,
                index_service=index_service,
                fund_service=fund_service,
                bond_service=bond_service,
                crypto_api_config=crypto_api_config
            )

            logger.info("AssetFallbackLoader 初始化成功")

        except Exception as e:
            logger.warning(f"⚠️ AssetFallbackLoader 初始化失败: {e}")
            self.fallback_loader = None

    def initialize(self):
        """延迟初始化，由服务容器控制时机"""
        if self._is_initialized:
            logger.info("UnifiedDataManager已初始化，跳过重复初始化")
            return

        logger.info("开始初始化UnifiedDataManager...")

        # 延迟获取统一缓存服务
        if self.cache_manager is None:
            try:
                from core.containers import get_service_container
                from core.services.cache_service import CacheService
                
                container = get_service_container()
                if container and container.is_registered(CacheService):
                    self.cache_manager = container.resolve(CacheService)
                    logger.info("延迟初始化：统一缓存服务已获取")
            except Exception as e:
                logger.warning(f"延迟获取统一缓存服务失败: {e}")

        # 从服务容器获取已注册的实例，而不是创建新的
        try:
            if UniPluginDataManager and hasattr(self, 'service_container') and self.service_container:
                if self.service_container.is_registered(UniPluginDataManager):
                    self._uni_plugin_manager = self.service_container.resolve(UniPluginDataManager)
                    logger.info("从服务容器获取UniPluginDataManager成功")
                else:
                    logger.warning("UniPluginDataManager未在服务容器中注册，将使用延迟创建模式")
            else:
                logger.warning("服务容器不可用或UniPluginDataManager未导入，将使用延迟创建模式")
        except Exception as e:
            logger.error(f"[ERROR] 从服务容器获取UniPluginDataManager失败: {e}")

        # 增强DuckDB数据下载器 - 在UniPluginDataManager可用后初始化
        self._init_enhanced_duckdb_downloader()

        # 初始化StockService用于后备机制获取股票列表
        self._init_stock_service()

        self._is_initialized = True
        logger.info("UnifiedDataManager初始化完成")

    def _init_duckdb_integration(self):
        """
        集成DuckDB功能到现有数据管理器

        在现有架构基础上增加DuckDB支持，不破坏现有功能
        """
        try:
            # 导入DuckDB核心组件
            from ..database.duckdb_operations import get_duckdb_operations
            from ..database.duckdb_manager import get_connection_manager
            from ..database.table_manager import get_table_manager
            from ..integration.data_router import DataRouter
            from ..performance.cache_manager import MultiLevelCacheManager
            from ..asset_database_manager import AssetSeparatedDatabaseManager
            from ..asset_type_identifier import get_asset_type_identifier

            # 初始化DuckDB组件
            self.duckdb_operations = get_duckdb_operations()
            self.duckdb_manager = get_connection_manager()
            self.table_manager = get_table_manager()

            # 初始化资产数据库管理器和资产类型识别器
            self.asset_manager = AssetSeparatedDatabaseManager()
            self.asset_identifier = get_asset_type_identifier()

            # 智能数据路由器
            self.data_router = DataRouter()

            # 多级缓存管理器（增强现有缓存）
            from ..performance.cache_manager import CacheLevel
            # 使用正确的构造函数参数：max_size和ttl（秒）
            self.multi_cache = MultiLevelCacheManager(max_size=1000, ttl=1800)  # 30分钟 = 1800秒

            # 质量评分缓存（专门用于data_quality_monitor查询）
            self._quality_score_cache = {}
            self._quality_cache_lock = threading.RLock()
            self._quality_cache_ttl = 300  # 5分钟缓存时间

            # DuckDB可用标志
            self.duckdb_available = True

            logger.info("DuckDB功能集成成功（包含资产数据库管理器）")

        except ImportError as e:
            logger.warning(f" DuckDB模块导入失败，将使用传统模式: {e}")
            self.duckdb_operations = None
            self.duckdb_manager = None
            self.table_manager = None
            self.asset_manager = None
            self.asset_identifier = None
            self.data_router = None
            self.multi_cache = None
            self.duckdb_available = False
        except Exception as e:
            logger.warning(f" DuckDB功能集成失败，将使用传统模式: {e}")
            self.duckdb_operations = None
            self.duckdb_manager = None
            self.table_manager = None
            self.asset_manager = None
            self.asset_identifier = None
            self.data_router = None
            self.multi_cache = None
            self.duckdb_available = False

    def _init_enhanced_duckdb_downloader(self):
        """
        初始化增强DuckDB数据下载器

        提供强大的数据下载和存储能力，完全基于TET框架和插件架构
        """
        try:
            from .enhanced_duckdb_data_downloader import get_enhanced_duckdb_downloader

            if self._uni_plugin_manager:
                self.enhanced_duckdb_downloader = get_enhanced_duckdb_downloader(self._uni_plugin_manager)
                logger.info("增强DuckDB数据下载器初始化成功")
            else:
                logger.warning("UniPluginDataManager不可用，无法初始化增强DuckDB下载器")
                self.enhanced_duckdb_downloader = None

        except Exception as e:
            logger.warning(f" 增强DuckDB数据下载器初始化失败: {e}")
            self.enhanced_duckdb_downloader = None

    def _init_stock_service(self):
        """初始化StockService用于后备机制获取股票列表"""
        try:
            from .stock_service import StockService

            if self.service_container and self.service_container.is_registered(StockService):
                self._stock_service = self.service_container.resolve(StockService)
                logger.info("StockService从服务容器初始化成功")
            else:
                self._stock_service = None
                logger.debug("StockService未在服务容器中注册，后备机制将无法获取股票列表")

        except Exception as e:
            self._stock_service = None
            logger.warning(f"⚠️ StockService初始化失败: {e}")

    def _get_quality_score_from_cache(self, symbol: str, frequency: str, 
                                       data_source: str = '', check_date: str = '') -> Optional[float]:
        """
        从缓存获取质量评分

        R287 P0-1 修复：缓存键统一为 symbol+frequency。读路径 _get_db_quality_score
        仅按 symbol+frequency 查询"最近一次质量分"（SQL 不区分 data_source/check_date），
        原 4 元组 key 与读路径不匹配导致缓存从未命中、每次直查 DB。data_source/check_date
        参数保留仅为兼容写路径调用点，实际不再参与 key 计算。

        Args:
            symbol: 股票代码
            frequency: 频率
            data_source: 数据源（兼容保留，不参与 key）
            check_date: 检查日期（兼容保留，不参与 key）

        Returns:
            质量评分，如果缓存不存在或已过期则返回None
        """
        cache = getattr(self, '_quality_score_cache', None)
        if cache is None:
            return None
        lock = getattr(self, '_quality_cache_lock', None)
        if lock is None:
            return None
        ttl = getattr(self, '_quality_cache_ttl', 300)
        cache_key = f"{symbol}_{frequency}"

        with lock:
            if cache_key in cache:
                cached_data = cache[cache_key]
                if (datetime.now() - cached_data['timestamp']).total_seconds() < ttl:
                    logger.debug(f"[质量评分缓存] 命中缓存: {cache_key}")
                    return cached_data['score']
                else:
                    del cache[cache_key]
                    logger.debug(f"[质量评分缓存] 缓存过期: {cache_key}")

        return None

    def _set_quality_score_to_cache(self, symbol: str, frequency: str, 
                                    data_source: str = '', check_date: str = '', score: float = None):
        """
        将质量评分存入缓存

        R287 P0-1 修复：与 _get_quality_score_from_cache 对齐，key 统一为 symbol+frequency
        （语义即"该 symbol+frequency 最近一次质量分"，data_source/check_date 不再参与）。

        Args:
            symbol: 股票代码
            frequency: 频率
            data_source: 数据源（兼容保留，不参与 key）
            check_date: 检查日期（兼容保留，不参与 key）
            score: 质量评分
        """
        cache = getattr(self, '_quality_score_cache', None)
        if cache is None:
            return
        lock = getattr(self, '_quality_cache_lock', None)
        if lock is None:
            return
        cache_key = f"{symbol}_{frequency}"

        with lock:
            cache[cache_key] = {
                'score': score,
                'timestamp': datetime.now()
            }
            logger.debug(f"[质量评分缓存] 存入缓存: {cache_key}, score: {score:.3f}")

    def _create_uni_plugin_manager_if_needed(self):
        """初始化UniPluginDataManager"""
        try:
            from core.plugin_manager import PluginManager
            from core.data_source_router import DataSourceRouter
            from core.tet_data_pipeline import TETDataPipeline
            from core.services.uni_plugin_data_manager import UniPluginDataManager

            logger.info("开始初始化UniPluginDataManager...")

            # 从服务容器获取已有的PluginManager实例，而不是创建新的
            plugin_manager = None
            if self.service_container and self.service_container.is_registered(PluginManager):
                try:
                    plugin_manager = self.service_container.resolve(PluginManager)
                    logger.info("从服务容器获取PluginManager成功")
                except Exception as e:
                    logger.warning(f"从服务容器获取PluginManager失败: {e}")

            # 如果服务容器中没有，则创建新实例（兼容旧逻辑）
            if plugin_manager is None:
                plugin_manager = PluginManager()
                logger.warning("使用新创建的PluginManager实例（非单例）")

            # 创建数据源路由器（R275 扩展: 从配置读取健康检查间隔/熔断阈值；
            # R279 改为优先复用 DI 容器单例，消除实例分裂）
            data_source_router = self._resolve_or_create_data_source_router()
            tet_pipeline = TETDataPipeline(data_source_router)

            # 创建UniPluginDataManager
            self._uni_plugin_manager = UniPluginDataManager(
                plugin_manager=plugin_manager,
                data_source_router=data_source_router,
                tet_pipeline=tet_pipeline
            )

            # 关键修复：调用initialize()方法来注册插件到路由器
            self._uni_plugin_manager.initialize()

            logger.info("UniPluginDataManager初始化成功")

        except Exception as e:
            logger.error(f"[ERROR] UniPluginDataManager初始化失败: {e}")
            self._uni_plugin_manager = None

    def get_uni_plugin_manager(self):
        """获取UniPluginDataManager实例"""
        return self._uni_plugin_manager

    def _register_legacy_data_source_to_router(self, source_id: str, legacy_source):
        """将传统数据源注册到TET路由器"""
        try:
            # 检查TET管道是否可用
            if not (hasattr(self, 'tet_pipeline') and self.tet_pipeline and hasattr(self.tet_pipeline, 'router')):
                logger.debug(f"TET管道不可用，跳过注册传统数据源: {source_id}")
                return

            # 创建传统数据源的适配器
            from ..data_source_extensions import DataSourcePluginAdapter
            from .legacy_datasource_adapter import LegacyDataSourceAdapter

            # 包装传统数据源为IDataSourcePlugin接口
            plugin_adapter = LegacyDataSourceAdapter(legacy_source, source_id)

            # 创建数据源插件适配器
            adapter = DataSourcePluginAdapter(plugin_adapter, source_id)

            # 注册到路由器
            router = self.tet_pipeline.router
            success = router.register_data_source(source_id, adapter, priority=1, weight=1.0)

            if success:
                logger.info(f"传统数据源 {source_id} 已注册到TET路由器")

                # 关键修复：同时注册到TET管道的适配器字典
                if hasattr(self.tet_pipeline, '_adapters'):
                    self.tet_pipeline._adapters[source_id] = adapter
                    logger.info(f"传统数据源 {source_id} 已注册到TET管道适配器字典")
                else:
                    logger.warning("TET管道缺少_adapters属性")

                # 如果适配器有对应的插件实例，也注册到_plugins字典
                if hasattr(adapter, 'plugin') and hasattr(self.tet_pipeline, '_plugins'):
                    self.tet_pipeline._plugins[source_id] = adapter.plugin
                    logger.info(f"传统数据源 {source_id} 已注册到TET管道插件字典")
            else:
                logger.warning(f"传统数据源 {source_id} 注册到TET路由器失败")

        except Exception as e:
            logger.error(f"注册传统数据源 {source_id} 到TET路由器异常: {e}")

    def _register_legacy_data_sources_to_router(self):
        """将所有传统数据源注册到TET路由器"""
        try:
            logger.info("开始注册传统数据源到TET路由器")

            # 注册所有已初始化的传统数据源
            for source_id, legacy_source in self._data_sources.items():
                if legacy_source is not None:
                    self._register_legacy_data_source_to_router(source_id, legacy_source)

            logger.info("传统数据源注册到TET路由器完成")
        except Exception as e:
            logger.error(f"注册传统数据源到TET路由器异常: {e}")

    def _load_industry_data(self):
        """加载行业数据"""
        if self.industry_manager:
            try:
                self.industry_manager.load_cache()
                self.industry_manager.update_industry_data()
                logger.info("行业数据加载成功")
            except Exception as e:
                logger.error(f"行业数据加载失败: {e}")

    def get_available_sources(self) -> List[str]:
        """获取可用的数据源列表"""
        sources = []
        # FactorWeave-Quant已移除
        sources.extend(self._data_sources.keys())
        return sources

    def switch_data_source(self, source: str) -> bool:
        """切换数据源"""
        if source in self.get_available_sources():
            old_source = self._current_source
            self._current_source = source
            logger.info(f"数据源从 {old_source} 切换到 {source}")
            return True
        else:
            logger.error(f"数据源 {source} 不可用")
            return False

    def get_stock_list(self, market: str = 'all') -> pd.DataFrame:
        """
        获取股票列表（DuckDB优先架构）- 重构为调用通用资产列表方法

        Args:
            market: 市场类型 ('all', 'sh', 'sz', 'bj')

        Returns:
            股票列表DataFrame
        """
        return self.get_asset_list(asset_type='stock_a', market=market)

    def _get_industry_info(self, stock_code: str) -> str:
        """获取股票行业信息"""
        if self.industry_manager:
            try:
                industry_info = self.industry_manager.get_industry(stock_code)
                if industry_info:
                    return (industry_info.get('csrc_industry') or
                            industry_info.get('exchange_industry') or
                            industry_info.get('industry') or '其他')
            except Exception as e:
                logger.warning(f"获取股票 {stock_code} 行业信息失败: {e}")
        return '其他'

    def get_kdata(self, stock_code: str, period: str = 'D', count: int = 365,
                  asset_type: AssetType = AssetType.STOCK_A) -> pd.DataFrame:
        """
        获取K线数据 - 统一接口（DB优先架构：DuckDB优先 → 插件补齐 → 落库 → 返回）

        Args:
            stock_code: 股票代码（或其他资产代码）
            period: 周期 (D/W/M/1/5/15/30/60)
            count: 数据条数
            asset_type: 资产类型（默认为股票，支持CRYPTO/FUTURES/FOREX/INDEX/FUND等）

        Returns:
            K线数据DataFrame
        """
        try:
            # 缓存键包含资产类型，避免跨资产混淆
            cache_key = f"kdata_{asset_type.value}_{stock_code}_{period}_{count}"

            # 1. 多级缓存检查（增强缓存策略）
            cached_data = self._get_cached_data(cache_key)
            if cached_data is not None and not cached_data.empty:
                logger.debug(f"缓存命中: {stock_code} ({asset_type.value})")
                return cached_data

            # 2. 优先从DuckDB获取（DB优先）
            df = pd.DataFrame()
            if self.duckdb_available:
                logger.debug(f"尝试从DuckDB获取K线数据: {stock_code}, period={period}, count={count}, asset_type={asset_type.value}")
                df = self._get_kdata_from_duckdb(stock_code, period, count, asset_type=asset_type)

                if not df.empty:
                    # R285 修复4：DB 直读质量校验——DB 只有一份低质量数据时，
                    # 无条件返回会让坏数据直达图表。识别后置空走插件补齐链路重拉
                    # （原 R264 只处理"空"不处理"低质量"，此处补全）。
                    from core.plugin_types import Period
                    frequency = Period.to_duckdb_frequency(period)
                    db_score = self._get_db_quality_score(stock_code, frequency, asset_type)
                    if db_score is not None and db_score < self._DB_QUALITY_MIN_SCORE:
                        logger.warning(f"DB中 {stock_code} ({frequency}) 数据质量分偏低 "
                                       f"{db_score:.1f} < {self._DB_QUALITY_MIN_SCORE}，触发回源重拉")
                        df = pd.DataFrame()
                    else:
                        # R263 增量更新：DB 命中后按需补齐（隔天增量 / 历史不足），
                        # 修复"隔天数据不更新"与"重启后重新联网拉全量"两个缺陷
                        merged_df = self._incremental_fill_kdata(stock_code, period, count, df, asset_type)
                        if merged_df is not None and not merged_df.empty:
                            df = merged_df
                        if len(df) > count:
                            df = df.tail(count).reset_index(drop=True)
                        logger.info(f"从DuckDB获取数据成功: {stock_code} ({asset_type.value}), 记录数={len(df)}")
                        self._cache_data(cache_key, df)
                        return df
                logger.warning(f"DuckDB中没有数据，尝试通过数据源插件补齐: {stock_code} ({asset_type.value})")
            else:
                logger.warning("DuckDB不可用，尝试通过数据源插件补齐")

            # 3. 插件补齐 + 落库（DB缺失数据的回退链路，补齐后写入historical_kline_data）
            if df.empty:
                try:
                    fallback_df, plugin_id = self._fetch_kdata_from_tet(stock_code, period, count, asset_type)
                    if fallback_df is not None and not fallback_df.empty:
                        df = fallback_df
                        # 落库（统一表名 historical_kline_data，INSERT OR REPLACE 幂等）
                        try:
                            if self.asset_manager is not None:
                                self._persist_kdata_to_duckdb(df, stock_code, period, asset_type,
                                                              data_source=plugin_id)
                        except Exception as e:
                            logger.warning(f"补齐数据落库失败: {stock_code} - {e}")
                        self._cache_data(cache_key, df)
                        logger.info(f"插件补齐并落库成功: {stock_code} ({asset_type.value}), 来源={plugin_id}, 记录数={len(df)}")
                        return df
                except Exception as e:
                    logger.error(f"插件补齐K线数据失败: {stock_code} - {e}")

            logger.warning(f"数据库与插件均无数据: {stock_code} ({asset_type.value})")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"获取K线数据失败: {stock_code} ({asset_type.value}) - {e}")
            return pd.DataFrame()

    def _persist_kdata_to_duckdb(self, df: pd.DataFrame, stock_code: str, period: str,
                                 asset_type: AssetType, data_source: Optional[str] = None) -> None:
        """R263: K线数据统一落库（统一表名 historical_kline_data，INSERT OR REPLACE 幂等）

        get_kdata 全量补齐与 _incremental_fill_kdata 增量合并均复用此方法，
        保证"获取后必入库、重复入库幂等"。

        R275 修复：
        - data_source 支持真实插件 id 溯源（TET failover 成功源），替代恒硬编码 'tet_plugin'；
        - 兼容插件返回的 datetime 索引 df（东财/baostock 均 set_index('datetime')），
          否则 timestamp 列缺失 → 违反 NOT NULL 约束 → 落库失败。
        """
        if df is None or df.empty or self.asset_manager is None:
            return
        persist_df = df.copy()
        # 时间列统一为timestamp（DuckDB K线表结构）
        if 'timestamp' not in persist_df.columns:
            # 兼容插件返回的 datetime 索引（datetime 在 index 而非 columns）
            if 'datetime' not in persist_df.columns and 'date' not in persist_df.columns:
                if isinstance(persist_df.index, pd.DatetimeIndex) or persist_df.index.name in ('datetime', 'date'):
                    persist_df = persist_df.reset_index()
                    # R277: 无命名 DatetimeIndex reset_index 后新列为 'index'，
                    # 统一改名为 datetime，否则 timestamp 无法生成 → 落库数据无时间戳
                    if 'index' in persist_df.columns:
                        persist_df = persist_df.rename(columns={'index': 'datetime'})
            # R290: 新增 timestamp 后删除 datetime/date 列，避免 DataFrame 同时携带
            # datetime+timestamp 两列，被 asset_database_manager._filter_dataframe_columns
            # 的 datetime→timestamp 映射再次 rename 成重复列 → DuckDB 报
            # "Binder Error: Duplicate column name timestamp in INSERT"。
            if 'datetime' in persist_df.columns:
                persist_df['timestamp'] = pd.to_datetime(persist_df['datetime'])
                persist_df = persist_df.drop(columns=['datetime'])
            elif 'date' in persist_df.columns:
                persist_df['timestamp'] = pd.to_datetime(persist_df['date'])
                persist_df = persist_df.drop(columns=['date'])
        # 补齐关键列，保证落库后可按symbol/frequency查询
        # R291 修复：列"存在但全为 NaN"（如增量行缺 symbol）时原判断不生效，
        # symbol/data_source 以 NULL 直插违反 NOT NULL 约束 → 改用 fillna 兜底。
        if 'symbol' in persist_df.columns:
            persist_df['symbol'] = persist_df['symbol'].fillna(stock_code)
        else:
            persist_df['symbol'] = stock_code
        if 'frequency' not in persist_df.columns:
            try:
                from core.plugin_types import Period
                persist_df['frequency'] = Period.to_duckdb_frequency(period)
            except Exception:
                pass
        if 'data_source' in persist_df.columns:
            persist_df['data_source'] = persist_df['data_source'].fillna(data_source or 'tet_plugin')
        else:
            persist_df['data_source'] = data_source or 'tet_plugin'
        # R289: 落库关键节点计时（对齐 asset_database_manager._upsert_data 的
        # write_duration/write_speed 模式），用于排查"获取快/落库慢"的性能瓶颈。
        persist_start = time.time()
        try:
            self.asset_manager.store_standardized_data(
                persist_df, asset_type, DataType.HISTORICAL_KLINE)
            persist_duration = time.time() - persist_start
            persist_speed = len(persist_df) / persist_duration if persist_duration > 0 else 0
            if persist_duration > 1.0:
                logger.warning(
                    f"[K线落库] 写入较慢: {stock_code} {period}, "
                    f"{len(persist_df)}行, 耗时: {persist_duration:.2f}秒, 速度: {persist_speed:.1f}行/秒")
            else:
                logger.debug(
                    f"[K线落库] {stock_code} {period} 成功写入 {len(persist_df)} 行, "
                    f"耗时: {persist_duration:.2f}秒, 速度: {persist_speed:.1f}行/秒")
        except Exception:
            persist_duration = time.time() - persist_start
            logger.error(
                f"[K线落库] 失败: {stock_code} {period}, "
                f"耗时: {persist_duration:.2f}秒, {len(persist_df)}行")
            raise

    def _resolve_or_create_data_source_router(self):
        """R279：优先复用 DI 容器 DataSourceRouter 单例（消除 router 实例分裂）。

        此前 UDM 初始化 tet_pipeline 用 _build_data_source_router() 自建 router，
        与 service_bootstrap 注册的 DI 单例是不同实例 → mark_unavailable 写在
        UDM 实例 B 上，走到实例 A/C/D 的请求看不到熔断状态，切换股票后失效。
        统一为容器单例后，熔断/健康状态跨服务、跨请求共享。
        """
        try:
            from ..data_source_router import DataSourceRouter
            if (self.service_container is not None
                    and self.service_container.is_registered(DataSourceRouter)):
                return self.service_container.resolve(DataSourceRouter)
        except Exception as e:
            logger.warning(f"从容器获取 DataSourceRouter 失败，回退自建: {e}")
        return _build_data_source_router()

    def _get_enhanced_quality_monitor(self):
        """R278：惰性获取增强数据质量监控器（DI 单例，未注册/不可用时返回 None）"""
        try:
            from ..containers import get_service_container
            from core.services.enhanced_data_quality_monitor import EnhancedDataQualityMonitor
            container = get_service_container()
            if container is None or not container.is_registered(EnhancedDataQualityMonitor):
                return None
            return container.resolve(EnhancedDataQualityMonitor)
        except Exception as e:
            logger.debug(f"获取增强数据质量监控器失败: {e}")
            return None

    def _incremental_fill_kdata(self, stock_code: str, period: str, count: int,
                                db_df: pd.DataFrame,
                                asset_type: AssetType) -> Optional[pd.DataFrame]:
        """R263 增量更新：DB 命中后按需补齐缺口数据，合并去重并落库

        场景A（隔天增量）：DB 最新K线日期 < 今天 → 只拉最新日期之后的新K线
             （东财 beg=最新日期+1天，TET管道 L523-524 透传 start_date）
        场景B（历史不足）：DB 条数 < count → 只拉 DB 最早日期之前的缺口历史
             （东财 end=最早日期-1天，透传 end_date）
        合并结果按 datetime 去重升序；有新增则 upsert 回库（幂等）。
        拉取失败/无新增时静默返回 None，不影响主流程返回 DB 数据。

        Args:
            stock_code: 股票代码
            period: 周期
            count: 请求条数
            db_df: DB 已读到的 K 线（升序）
            asset_type: 资产类型

        Returns:
            Optional[pd.DataFrame]: 增量合并后的完整数据（升序）；无需增量或失败返回 None
        """
        try:
            if db_df is None or db_df.empty or 'datetime' not in db_df.columns:
                return None

            ts_series = pd.to_datetime(db_df['datetime'])
            latest_ts = pd.Timestamp(ts_series.max())
            earliest_ts = pd.Timestamp(ts_series.min())

            # 增量检查频率限制：TTL 内不重复联网检查（隔天更新自然被覆盖）
            try:
                from core.plugin_types import Period
                freq = Period.to_duckdb_frequency(period)
            except Exception:
                freq = str(period)
            check_key = f"{asset_type.value}|{stock_code}|{freq}"
            now = datetime.now()
            last_check = self._kdata_incremental_checked.get(check_key)
            if last_check and (now - last_check).total_seconds() < self._kdata_incremental_ttl:
                return None
            self._kdata_incremental_checked[check_key] = now

            today = datetime.now().date()
            # R287 P2-a：记录 (df, plugin_id) 元组，落库时透传真实成功源
            new_parts: List[Tuple[pd.DataFrame, Optional[str]]] = []

            # 场景A：隔天增量（DB 最新K线日期 < 今天）
            if latest_ts.date() < today:
                start_date = (latest_ts + pd.Timedelta(days=1)).strftime('%Y%m%d')
                logger.info(f"[增量更新-隔天] {stock_code} {period} 最新={latest_ts.date()} < 今天={today}，"
                            f"拉取 {start_date} 起的新数据")
                new_df, new_plugin_id = self._fetch_kdata_from_tet(
                    stock_code, period, count, asset_type, start_date=start_date)
                if new_df is not None and not new_df.empty:
                    new_parts.append((new_df, new_plugin_id))
            else:
                # R294 修复: 分钟线"当天内"增量补齐——原实现仅 latest_ts.date() < today
                # 才触发，DB 已有当日部分分钟数据时，当天新产生的分钟永远无法增量拉取。
                # 分钟频率下: 最新时刻落后当前时刻 >= 2 个周期时长即重拉当天数据，
                # 由下游按 datetime 精确去重(L1208-1210)只插入新时刻，实现按时刻增量;
                # TET/东财增量参数仅支持日期粒度(东财 beg=YYYYMMDD)，当天重拉+精确
                # 去重即达到时刻级增量效果；2 周期阈值避免每次刷新都重拉当天全量。
                intraday_minutes = {
                    '1min': 1, '5min': 5, '15min': 15,
                    '30min': 30, '60min': 60,
                }.get(freq)
                if intraday_minutes is not None:
                    span = pd.Timedelta(minutes=2 * intraday_minutes)
                    if latest_ts < now - span:
                        start_date = latest_ts.strftime('%Y%m%d')
                        logger.info(f"[增量更新-分钟当天] {stock_code} {period} 最新={latest_ts} "
                                    f"落后>={2 * intraday_minutes}分钟，重拉当天 {start_date} 增量")
                        new_df, new_plugin_id = self._fetch_kdata_from_tet(
                            stock_code, period, count, asset_type, start_date=start_date)
                        if new_df is not None and not new_df.empty:
                            new_parts.append((new_df, new_plugin_id))

            # 场景B：历史补齐（DB 条数 < count，且历史未耗尽）
            if len(db_df) < count and not self._kdata_history_exhausted.get(check_key):
                end_date = (earliest_ts - pd.Timedelta(days=1)).strftime('%Y%m%d')
                logger.info(f"[增量更新-历史] {stock_code} {period} DB={len(db_df)}条 < count={count}，"
                            f"拉取 {end_date} 前的缺口历史")
                history_df, history_plugin_id = self._fetch_kdata_from_tet(
                    stock_code, period, count, asset_type, end_date=end_date)
                if history_df is not None and not history_df.empty:
                    new_parts.append((history_df, history_plugin_id))

            if not new_parts:
                return None

            # 合并（以 datetime 为键，升序排列）
            merged = pd.concat([db_df] + [part[0] for part in new_parts], ignore_index=True)
            merged['datetime'] = pd.to_datetime(merged['datetime'])

            # R291 修复：列补齐提前到 all_new 切片之前。
            # 原 R290 补齐只作用于重新赋值后的 merged，而落库用的是先前的
            # all_new 切片（缺少 symbol/code/data_source/adj_type 补齐与 NaN 兜底），
            # 导致新增行 symbol 为 NULL 违反 NOT NULL 约束、整批落库失败。
            # 补齐后 all_new 与 merged 均含完整列，切片/落库一致。
            persist_source = next((pid for _, pid in reversed(new_parts) if pid), None)
            for _col, _default in (('adj_type', 'none'), ('adj_source', 'plugin'),
                                   ('data_quality_score', 0.0),
                                   ('code', stock_code), ('symbol', stock_code),
                                   ('data_source', persist_source or 'tet_plugin')):
                if _col not in merged.columns:
                    merged[_col] = _default
                else:
                    merged[_col] = merged[_col].fillna(_default)

            # R292 修复：日线/周/月线按日期粒度去重。
            # 此前用精确 datetime 相等比较（isin），DB 存 00:00:00 而新拉取行带
            # 时刻（如 15:00:00）或历史遗留分钟垃圾行时同日不去重 → 同日多行堆积，
            # 日线展示"数据多但日期集中"。按日期粒度比较后同日只保留一行。
            _day_level = freq in ('1d', '1w', '1M')
            if _day_level:
                db_keys = set(pd.to_datetime(ts_series).dt.date)
                merged_dates = pd.to_datetime(merged['datetime']).dt.date
                all_new = merged[~merged_dates.isin(db_keys)]
            else:
                db_keys = set(ts_series)
                all_new = merged[~merged['datetime'].isin(db_keys)]
            if all_new.empty:
                # 无新增：若场景B曾拉取仍未扩展历史，标记历史尽头，避免重复全量拉取
                if len(db_df) < count:
                    self._kdata_history_exhausted[check_key] = now
                    logger.info(f"[增量更新] {stock_code} {period} 历史已到尽头，短期内不再拉取")
                return None

            merged['_r292_dup_key'] = (
                pd.to_datetime(merged['datetime']).dt.date if _day_level
                else merged['datetime'])
            merged = (merged.drop_duplicates(subset=['_r292_dup_key'], keep='last')
                      .drop(columns=['_r292_dup_key'])
                      .sort_values(by='datetime', ascending=True)
                      .reset_index(drop=True))

            # 有新增 → 落库（R287 P2-a 修复）
            # 原实现：a) 落库 merged 全量（DB 已有行被重复 upsert，白写）；b) 未传
            # data_source → _persist_kdata_to_duckdb 恒回退 'tet_plugin'，与 DB 中
            # 既有 (symbol, 'tongdaxin', ...) 主键不匹配 → 主键错配插入重复行。
            # 现改为：只插新增行 all_new + 透传 TET failover 真实成功源 plugin_id。
            try:
                self._persist_kdata_to_duckdb(
                    all_new, stock_code, period, asset_type, data_source=persist_source)
            except Exception as e:
                logger.warning(f"[增量更新] 落库失败: {stock_code} {period} - {e}")

            logger.info(f"[增量更新] {stock_code} {period} 合并完成: {len(db_df)} → {len(merged)} 条")
            return merged

        except Exception as e:
            logger.error(f"[增量更新] 失败: {stock_code} {period} - {e}")
            return None

    def _fetch_kdata_from_tet(self, stock_code: str, period: str, count: int,
                              asset_type: AssetType, start_date: str = None,
                              end_date: str = None) -> Optional[Tuple[pd.DataFrame, Optional[str]]]:
        """
        通过TET数据管道从插件数据源补齐K线数据（DuckDB无数据时的网络回退）

        R263 增量更新：支持 start_date/end_date 区间透传（TET管道 L523-524 →
        插件适配器 get_kdata → 东财 beg/end 参数），仅拉取缺口数据。

        R275 溯源：返回 (df, plugin_id)，plugin_id 为 TET failover 实际成功源
        （source_info.provider / metadata.failover.successful_source），
        供落库时 data_source 列记录真实来源，替代恒 'tet_plugin'。

        Args:
            stock_code: 股票代码（或其他资产代码）
            period: 周期
            count: 数据条数
            asset_type: 资产类型
            start_date: 增量拉取起始日期（YYYYMMDD，东财 beg 格式；None 表示从头）
            end_date: 增量拉取截止日期（YYYYMMDD，东财 end 格式；None 表示到最新）

        Returns:
            Optional[Tuple[pd.DataFrame, Optional[str]]]: (数据, 成功插件id)；失败返回 (None, None)
        """
        try:
            if not getattr(self, 'tet_enabled', False) or not getattr(self, 'tet_pipeline', None):
                logger.warning(f"TET数据管道不可用，无法补齐K线数据: {stock_code}")
                return None, None

            # 构造标准化查询（period传给query，count放extra_params，增量区间透传）
            from core.tet_data_pipeline import StandardQuery
            query = StandardQuery(
                symbol=stock_code,
                asset_type=asset_type,
                data_type=DataType.HISTORICAL_KLINE,
                period=period,
                start_date=start_date,
                end_date=end_date,
                extra_params={'count': count}
            )

            result = self.tet_pipeline.process(query)
            if result is None:
                return None, None

            # 兼容StandardData（.data字段为DataFrame）与直接DataFrame两种返回
            if hasattr(result, 'data'):
                df = result.data
            elif isinstance(result, pd.DataFrame):
                df = result
            else:
                logger.warning(f"TET返回了不支持的数据类型: {type(result)}，无法补齐: {stock_code}")
                return None, None

            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                logger.warning(f"TET插件补齐数据为空: {stock_code}")
                return None, None

            # 提取实际成功的数据源插件id（用于落库溯源）
            plugin_id = None
            try:
                if hasattr(result, 'source_info') and isinstance(result.source_info, dict):
                    plugin_id = result.source_info.get('provider')
                if not plugin_id and hasattr(result, 'metadata'):
                    failover = result.metadata.get('failover', {})
                    plugin_id = failover.get('successful_source') if isinstance(failover, dict) else None
            except Exception:
                plugin_id = None

            # R291/R292 修复：TET 标准化（_standardize_data_types）与各插件（东财/sina等）
            # 将 datetime/date set_index 到索引，导致后续 concat 合并时新增行 datetime 列
            # 全为 NaN → 落库违反 NOT NULL 约束。原 R291 仅对 index.name 为
            # ('datetime','date') 或 DatetimeIndex 时 reset_index()，但无命名 DatetimeIndex
            # 会生成 'index' 列而非 'datetime'，sina 的 'date' 索引生成 'date' 列仍缺
            # datetime → 偶发数据形态/范围错乱。统一走 _standardize_kdata_format 出口。
            if 'datetime' not in df.columns:
                try:
                    standardized = self._standardize_kdata_format(df, stock_code)
                    if (standardized is not None and not standardized.empty
                            and 'datetime' in standardized.columns):
                        df = standardized
                except Exception as std_error:
                    logger.warning(f"TET补齐数据标准化失败，保留原始形态: {stock_code} - {std_error}")

            return df.copy(), plugin_id

        except Exception as e:
            logger.error(f"TET插件补齐K线数据失败: {stock_code} - {e}")
            return None, None

    def get_kline_data(self, stock_code: str, period: str = 'D', count: int = 365,
                       asset_type=None, **kwargs) -> pd.DataFrame:
        """
        获取K线数据（别名方法，兼容其他服务调用）

        Args:
            stock_code: 股票代码
            period: 周期
            count: 数据条数
            asset_type: 资产类型（可以是字符串或AssetType枚举）
            **kwargs: 其他参数（忽略）

        Returns:
            K线数据DataFrame
        """
        from core.plugin_types import AssetType as AT
        if asset_type is None:
            final_asset_type = AT.STOCK_A
        elif isinstance(asset_type, str):
            type_map = {
                'stock_a': AT.STOCK_A,
                'stock': AT.STOCK_A,
                'index': AT.INDEX,
                'fund': AT.FUND,
                'bond': AT.BOND,
                'futures': AT.FUTURES,
                'option': AT.OPTION,
                'etf': AT.ETF
            }
            final_asset_type = type_map.get(asset_type.lower(), AT.STOCK_A)
        else:
            final_asset_type = asset_type

        return self.get_kdata(stock_code, period, count, asset_type=final_asset_type)

    def get_kdata_from_source(self, stock_code: str, period: str = 'D', count: int = 365,
                              data_source: str = None, asset_type: AssetType = None,
                              start_date=None, end_date=None, adjustment: str = 'none') -> pd.DataFrame:
        """
        从指定数据源获取K线数据

        Args:
            stock_code: 股票代码
            period: 周期 (D/W/M/1/5/15/30/60/daily/weekly/monthly等)
            count: 数据条数
            data_source: 数据源名称 (如: '通达信', 'akshare', 'eastmoney'等)
            asset_type: 资产类型（可选，如果不提供则使用默认值A股）
            start_date: 开始日期 (可选，如果不提供则自动计算，格式: YYYY-MM-DD或datetime对象)
            end_date: 结束日期 (可选，如果不提供则自动计算，格式: YYYY-MM-DD或datetime对象)
            adjustment: 复权类型 ('qfq', 'hfq', 'none')

        Returns:
            K线数据DataFrame
        """
        try:
            from core.plugin_types import Period
            frequency = Period.to_frequency(period)

            cache_key = f"kdata_{stock_code}_{period}_{count}_{data_source}_{adjustment}"

            # 1. 检查缓存
            cached_data = self._get_cached_data(cache_key)
            if cached_data is not None and not cached_data.empty:
                logger.debug(f"从缓存获取K线数据: {stock_code} (数据源: {data_source})")
                return cached_data

            # 2. 使用UniPluginDataManager获取数据
            if self._uni_plugin_manager:
                try:
                    from ..plugin_types import AssetType
                    from datetime import datetime, timedelta

                    # 优先使用传入的日期范围，如果没有则自动计算
                    if start_date is None or end_date is None:
                        # 计算日期范围（当未提供日期参数时）
                        end_date = datetime.now() if end_date is None else end_date
                        # 根据周期计算开始日期
                        if start_date is None:
                            if frequency == 'daily':
                                start_date = end_date - timedelta(days=count * 2)  # 预留空间排除非交易日
                            elif frequency == 'weekly':
                                start_date = end_date - timedelta(weeks=count)
                            elif frequency == 'monthly':
                                start_date = end_date - timedelta(days=count * 31)
                            else:
                                start_date = end_date - timedelta(days=count)
                    else:
                        # 确保 end_date 是 datetime 对象
                        if isinstance(end_date, str):
                            end_date = datetime.strptime(end_date, '%Y-%m-%d')
                        elif end_date is None:
                            end_date = datetime.now()

                        # 确保 start_date 是 datetime 对象
                        if isinstance(start_date, str):
                            start_date = datetime.strptime(start_date, '%Y-%m-%d')

                    # 验证日期范围的有效性
                    if start_date >= end_date:
                        logger.warning(f"日期范围无效: start_date={start_date} >= end_date={end_date}，调整为默认范围")
                        end_date = datetime.now()
                        start_date = end_date - timedelta(days=count * 2)

                    # 调用插件管理器获取数据，传递data_source参数
                    # 使用传入的资产类型，如果没有则使用默认值A股
                    final_asset_type = asset_type or AssetType.STOCK_A

                    # 智能处理count参数：如果指定了时间范围，根据时间段计算实际需要的数据量
                    actual_count = count
                    if start_date and end_date:
                        # 根据日期范围和频率估算需要的数据量（考虑交易日和不同频率）
                        try:
                            from datetime import datetime
                            days_diff = (end_date - start_date).days

                            # 根据不同的频率类型，使用不同的估算方法
                            if frequency == 'daily':
                                # 日线：一年约250个交易日，估算公式：天数 * 0.7（考虑周末和节假日）
                                estimated_count = int(days_diff * 0.7)
                            elif frequency == 'weekly':
                                # 周线：一年约52周，估算公式：天数 / 7 * 0.9（考虑节假日）
                                estimated_count = int(days_diff / 7 * 0.9)
                            elif frequency == 'monthly':
                                # 月线：一年约12个月，估算公式：月份数
                                estimated_count = int(days_diff / 30)
                            elif frequency in ['1min', '5min', '15min', '30min', '60min']:
                                # 分钟线：根据频率计算（1分钟=240条/天，5分钟=48条/天，15分钟=16条/天，30分钟=8条/天，60分钟=4条/天）
                                minutes_per_day = {'1min': 240, '5min': 48, '15min': 16, '30min': 8, '60min': 4}
                                minutes_per_record = minutes_per_day.get(frequency, 240)
                                # 估算：天数 * 每天条数 * 0.7（考虑非交易时间）
                                estimated_count = int(days_diff * minutes_per_record * 0.7)
                            else:
                                # 其他频率：使用默认估算方法
                                estimated_count = int(days_diff * 0.7)

                            # 修复：不再强制最小值为800，而是使用实际计算出的数量
                            # 只有超过上限时才限制，不超过800时就使用实际计算的数量
                            # 上限设置为10000（超过这个值会在Tongdaxin插件中分片）
                            MAX_COUNT_LIMIT = 10000
                            if estimated_count > MAX_COUNT_LIMIT:
                                actual_count = MAX_COUNT_LIMIT
                                logger.warning(f"[数据获取] 估算数量{estimated_count}超过上限{MAX_COUNT_LIMIT}，调整为{actual_count}（将在插件中分片）")
                            else:
                                # 使用实际计算出的数量（可能是1、10、100等任何值，不再强制800）
                                actual_count = estimated_count

                            # 确保最小值为1（避免0或负数）
                            if actual_count < 1:
                                actual_count = 1
                                logger.warning(f"[数据获取] 估算数量过小，调整为最小值1")

                            logger.info(f"[数据获取] 已指定时间范围 {start_date} ~ {end_date}，"
                                        f"日期跨度{days_diff}天，频率={frequency}，估算需要{estimated_count}条，实际请求{actual_count}条")
                        except Exception as e:
                            # 如果计算失败，使用传入的count参数（而不是强制800）
                            actual_count = count if count > 0 else 365
                            logger.warning(f"[数据获取] 日期范围计算失败: {e}，使用传入的count={actual_count}")
                    else:
                        logger.info(f"[数据获取] 未指定时间范围，使用count={count}获取最近数据")

                    logger.info(f"[数据获取] 开始查询 {stock_code}，时间范围: {start_date} 到 {end_date}，频率: {frequency}，count: {actual_count}，数据源: {data_source}, 复权: {adjustment}")

                    df = self._uni_plugin_manager.get_kline_data(
                        symbol=stock_code,
                        asset_type=final_asset_type,
                        start_date=start_date,
                        end_date=end_date,
                        frequency=frequency,
                        count=actual_count,
                        data_source=data_source,
                        adjustment=adjustment
                    )

                    if not df.empty:
                        logger.info(f"[数据获取] 原始数据量: {len(df)} 条，时间跨度: {df['datetime'].min() if 'datetime' in df.columns else 'N/A'} ~ {df['datetime'].max() if 'datetime' in df.columns else 'N/A'}")

                        # 改进：数据截断逻辑 - 仅在明显超量且没有指定日期范围时才截断
                        # 如果用户指定了日期范围，则不进行截断（尊重用户意图）
                        should_truncate = False
                        if start_date is None or end_date is None:
                            # 未指定日期范围时，根据count判断是否截断
                            if len(df) > count * 3:  # 提高阈值到3倍，更宽容
                                should_truncate = True

                        # 修复：先进行数据标准化（包含排序），再进行截断
                        # 确保数据在截断前已经按时间升序排列
                        df = self._standardize_kdata_format(df, stock_code)

                        if should_truncate and not df.empty:
                            original_len = len(df)
                            # 修复：数据已经标准化并排序（升序），使用tail获取最新的count条数据
                            df = df.tail(count).reset_index(drop=True)
                            logger.warning(f"[数据获取] 未指定日期范围且数据量 {original_len} 超过限制 {count * 3}，截断为 {len(df)} 条（最新数据）")
                        else:
                            logger.info(f"[数据获取] 保留全部 {len(df)} 条数据（{'已指定日期范围' if start_date and end_date else '数据量未超限'}）")

                        # 缓存数据
                        self._cache_data(cache_key, df)

                        logger.info(f"[数据获取] 从数据源 {data_source} 获取K线数据成功: {stock_code}, 最终数据量: {len(df)}, 时间跨度: {df['datetime'].min() if 'datetime' in df.columns else 'N/A'} ~ {df['datetime'].max() if 'datetime' in df.columns else 'N/A'}")
                        return df
                    else:
                        logger.warning(f"从数据源 {data_source} 获取K线数据为空: {stock_code}，时间范围: {start_date} 到 {end_date}")

                except Exception as e:
                    logger.error(f"使用UniPluginDataManager从数据源 {data_source} 获取K线数据失败: {e}")

            # 3. 降级到默认get_kdata方法
            logger.warning(f"从指定数据源 {data_source} 获取失败，降级到默认方法")
            return self.get_kdata(stock_code, period, count, asset_type=asset_type)

        except Exception as e:
            logger.error(f"从数据源 {data_source} 获取K线数据失败: {stock_code} - {e}")
            return pd.DataFrame()

    def _get_cached_data(self, cache_key: str) -> Optional[pd.DataFrame]:
        """增强缓存获取 - 统一使用CacheService"""
        try:
            if self.duckdb_available and self.multi_cache:
                cached_data = self.multi_cache.get(cache_key)
                if cached_data is not None:
                    return cached_data

            if self.cache_manager:
                return self.cache_manager.get(cache_key, namespace='unified_data_manager')

            return None
        except Exception as e:
            logger.warning(f"缓存获取失败: {e}")
            return None

    def _cache_data(self, cache_key: str, data: pd.DataFrame):
        """增强缓存存储 - 统一使用CacheService"""
        try:
            if self.duckdb_available and self.multi_cache:
                self.multi_cache.set(cache_key, data, ttl=self._cache_ttl)

            if self.cache_manager:
                from datetime import timedelta
                ttl = timedelta(seconds=self._cache_ttl) if self._cache_ttl else None
                self.cache_manager.set(cache_key, data, ttl=ttl, namespace='unified_data_manager')

        except Exception as e:
            logger.warning(f"缓存存储失败: {e}")

    def _validate_columns(self, columns: List[str], allowed_columns: frozenset) -> List[str]:
        """验证列名是否在白名单中，防止SQL注入"""
        validated = []
        for col in columns:
            if col in allowed_columns:
                validated.append(col)
            else:
                logger.warning(f"列名 {col} 不在白名单中，已过滤")
        return validated

    def get_asset_list(self, asset_type: str = 'stock_a', market: str = 'all') -> pd.DataFrame:
        """
        获取资产列表（DuckDB优先架构）- 支持所有资产类型

        Args:
            asset_type: 资产类型 ('stock', 'crypto', 'fund', 'bond', 'index', 'sector')
            market: 市场类型 ('all', 'sh', 'sz', 'bj', 'us', 'hk')

        Returns:
            资产列表DataFrame
        """
        try:
            cache_key = f"asset_list_{asset_type}_{market}"

            # 处理资产类型参数，确保兼容字符串和枚举类型
            from core.plugin_types import AssetType as AssetTypeEnum
            asset_type_str = str(asset_type).lower()
            
            # 1. 优先从DuckDB数据库获取资产列表
            if self.duckdb_available and self.duckdb_operations:
                logger.debug(f"🗄️ 从DuckDB数据库获取{asset_type_str}资产列表")
                try:
                    asset_list_df = self._get_asset_list_from_duckdb(asset_type_str, market)
                    if asset_list_df is not None and not asset_list_df.empty:
                        logger.debug(f"DuckDB数据库获取{asset_type_str}资产列表成功: {len(asset_list_df)} 个资产")
                        # 缓存结果
                        if self.cache_enabled:
                            self._cache_data(cache_key, asset_list_df)
                        return asset_list_df
                    else:
                        logger.info(f"📥 DuckDB中没有{asset_type_str}资产数据")
                except Exception as e:
                    logger.warning(f"⚠️ DuckDB{asset_type_str}资产列表获取失败: {e}")

            # 2. 修复：如果DuckDB没有数据，尝试从传统数据源获取
            logger.info(f"📥 DuckDB中没有{asset_type_str}资产数据，尝试从传统数据源获取")
            
            # 转换资产类型为枚举 - 统一使用完整的资产类型映射
            asset_type_mapping = {
                'stock': AssetTypeEnum.STOCK_A,
                'stock_a': AssetTypeEnum.STOCK_A,
                'stock_b': AssetTypeEnum.STOCK_B,
                'stock_h': AssetTypeEnum.STOCK_H,
                'stock_us': AssetTypeEnum.STOCK_US,
                'stock_hk': AssetTypeEnum.STOCK_HK,
                'crypto': AssetTypeEnum.CRYPTO,
                'fund': AssetTypeEnum.FUND,
                'bond': AssetTypeEnum.BOND,
                'index': AssetTypeEnum.INDEX,
                'sector': AssetTypeEnum.SECTOR,
                'futures': AssetTypeEnum.FUTURES,
                'forex': AssetTypeEnum.FOREX,
                'option': AssetTypeEnum.OPTION,
                'warrant': AssetTypeEnum.WARRANT,
                'commodity': AssetTypeEnum.COMMODITY,
                'industry_sector': AssetTypeEnum.INDUSTRY_SECTOR,
                'concept_sector': AssetTypeEnum.CONCEPT_SECTOR,
                'style_sector': AssetTypeEnum.STYLE_SECTOR,
                'theme_sector': AssetTypeEnum.THEME_SECTOR,
                'macro': AssetTypeEnum.MACRO
            }
            
            asset_type_enum = asset_type_mapping.get(asset_type_str, AssetTypeEnum.STOCK_A)
            
            # 3. 尝试调用_legacy_get_asset_list方法获取资产列表
            try:
                legacy_assets = self._legacy_get_asset_list(asset_type_enum, market)
                if not legacy_assets.empty:
                    logger.info(f"从传统数据源获取{asset_type_str}资产列表成功: {len(legacy_assets)} 个资产")
                    if self.cache_enabled:
                        self._cache_data(cache_key, legacy_assets)
                    return legacy_assets
            except Exception as e:
                logger.warning(f"⚠️ 从传统数据源获取{asset_type_str}资产列表失败: {e}")
            
            # 4. 返回空DataFrame，但保持正确的列结构
            import pandas as pd
            logger.warning(f"⚠️ 无法获取{asset_type_str}资产列表，返回空DataFrame")
            return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

        except Exception as e:
            logger.error(f"获取{asset_type}资产列表失败: {e}")
            import pandas as pd
            return pd.DataFrame()

    def _get_asset_list_from_duckdb(self, asset_type: str, market: str = None) -> pd.DataFrame:
        """从DuckDB数据库获取资产列表 - 支持多种资产类型"""
        try:
            import pandas as pd

            if not self.duckdb_operations:
                logger.warning("DuckDB操作器不可用")
                return pd.DataFrame()

            # 将字符串转换为AssetType枚举
            from ..plugin_types import AssetType
            asset_type_enum_mapping = {
                'stock': AssetType.STOCK_A,
                'stock_a': AssetType.STOCK_A,
                'stock_b': AssetType.STOCK_B,
                'stock_h': AssetType.STOCK_H,
                'stock_us': AssetType.STOCK_US,
                'stock_hk': AssetType.STOCK_HK,
                'crypto': AssetType.CRYPTO,
                'fund': AssetType.FUND,
                'bond': AssetType.BOND,
                'index': AssetType.INDEX,
                'sector': AssetType.SECTOR,
                'futures': AssetType.FUTURES,
                'forex': AssetType.FOREX,
                'option': AssetType.OPTION,
                'warrant': AssetType.WARRANT,
                'commodity': AssetType.COMMODITY,
                'industry_sector': AssetType.INDUSTRY_SECTOR,
                'concept_sector': AssetType.CONCEPT_SECTOR,
                'style_sector': AssetType.STYLE_SECTOR,
                'theme_sector': AssetType.THEME_SECTOR,
                'macro': AssetType.MACRO
            }
            asset_type_enum = asset_type_enum_mapping.get(asset_type, AssetType.STOCK_A)

            # 资产类型映射（用于WHERE条件）- 完整支持20+资产类型
            asset_type_value_mapping = {
                'stock': 'stock_a',
                'stock_a': 'stock_a',
                'stock_b': 'stock_b',
                'stock_h': 'stock_h',
                'stock_us': 'stock_us',
                'stock_hk': 'stock_hk',
                'crypto': 'crypto',
                'fund': 'fund',
                'bond': 'bond',
                'index': 'index',
                'sector': 'sector',
                'futures': 'futures',
                'forex': 'forex',
                'option': 'option',
                'warrant': 'warrant',
                'commodity': 'commodity',
                'industry_sector': 'industry_sector',
                'concept_sector': 'concept_sector',
                'style_sector': 'style_sector',
                'theme_sector': 'theme_sector',
                'macro': 'macro'
            }
            asset_type_value = asset_type_value_mapping.get(asset_type, 'stock_a')

            # 所有资产类型统一使用 asset_metadata 表
            table_name = 'asset_metadata'

            # 构建查询语句（使用 asset_metadata 表的字段名）
            if market and market != 'all':
                query = f"""
                SELECT DISTINCT 
                    symbol as code,
                    name,
                    market,
                    CASE WHEN industry IS NOT NULL AND industry != '' THEN industry ELSE NULL END as industry,
                    CASE WHEN sector IS NOT NULL AND sector != '' THEN sector ELSE NULL END as sector,
                    listing_date as list_date,
                    listing_status as status
                FROM {table_name} 
                WHERE market = '{market.upper()}' 
                  AND listing_status = 'active'
                  AND asset_type = '{asset_type_value}'
                ORDER BY symbol
                """
            else:
                query = f"""
                SELECT DISTINCT 
                    symbol as code,
                    name,
                    market,
                    CASE WHEN industry IS NOT NULL AND industry != '' THEN industry ELSE NULL END as industry,
                    CASE WHEN sector IS NOT NULL AND sector != '' THEN sector ELSE NULL END as sector,
                    listing_date as list_date,
                    listing_status as status
                FROM {table_name} 
                WHERE listing_status = 'active'
                  AND asset_type = '{asset_type_value}'
                ORDER BY symbol
                """

            import sys
            import io

            old_stdout = sys.stdout
            old_stderr = sys.stderr
            captured_stdout = io.StringIO()
            captured_stderr = io.StringIO()

            try:
                sys.stdout = captured_stdout
                sys.stderr = captured_stderr

                result = self.duckdb_operations.query_data(
                    database_path=self.asset_manager.get_database_path(asset_type_enum),
                    table_name=table_name,
                    custom_sql=query
                )
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                stdout_content = captured_stdout.getvalue()
                stderr_content = captured_stderr.getvalue()

                if stdout_content and len(stdout_content) < 500:
                    logger.debug(f"[CAPTURED STDOUT] query_data: {stdout_content!r}")
                if stderr_content and len(stderr_content) < 500 and 'recursion' not in stderr_content.lower():
                    logger.debug(f"[CAPTURED STDERR] query_data: {stderr_content!r}")

            # DEBUG: 检查result对象
            logger.debug(f"[DEBUG] query_data returned: type={type(result)}, success={result.success if result else 'None'}")

            if result.success and not result.data.empty:
                df = result.data
                logger.debug(f"从DuckDB获取{asset_type}资产列表成功: {len(df)} 个资产")  # 优化：改为debug级别减少日志噪音
                return df
            else:
                logger.info(f"DuckDB中没有{asset_type}资产列表数据")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"从DuckDB获取{asset_type}资产列表失败: {e}")
            return pd.DataFrame()

    def _get_db_quality_score(self, symbol: str, frequency: str,
                              asset_type: AssetType = AssetType.STOCK_A) -> Optional[float]:
        """R285 修复4：查询 data_quality_monitor 该 symbol+frequency 最近一次质量分

        读前质量校验（DB 直读不再无条件信任）：
        - 返回该 symbol+frequency 最近一次（MAX check_date）评估的质量分（0-100）
        - 无评估记录返回 None（不触发回源，保持现状）
        - 查询失败/DB 不可用返回 None（安全降级，不阻断）

        R287 P0-1 修复：接通质量分缓存——先查 _get_quality_score_from_cache
        （key=symbol+frequency，TTL=300s），命中则跳过 DB 查询；未命中才直查
        data_quality_monitor，结果写回缓存。避免窗口内多次调用（get_kdata /
        get_asset_data 主链路）反复全量直查 DB。
        """
        # P0-1：优先查缓存（symbol+frequency 统一 key）
        cached = self._get_quality_score_from_cache(symbol, frequency)
        if cached is not None:
            logger.debug(f"[读前质量校验-缓存] 命中 {symbol}/{frequency}: score={cached}")
            return cached

        try:
            if not self.duckdb_available or not self.duckdb_operations or self.asset_manager is None:
                return None
            database_path = self.asset_manager.get_database_path(asset_type)
            _q_start = time.perf_counter()
            result = self.duckdb_operations.execute_query(
                database_path=database_path,
                query="""
                    SELECT quality_score FROM data_quality_monitor
                    WHERE symbol = ? AND frequency = ?
                    ORDER BY check_date DESC
                    LIMIT 1
                """,
                params=[symbol, frequency]
            )
            _q_elapsed = (time.perf_counter() - _q_start) * 1000
            logger.debug(f"[读前质量校验-DB] {symbol}/{frequency} 查询耗时 {_q_elapsed:.1f}ms")
            if result is None or not getattr(result, 'success', False):
                return None
            data = getattr(result, 'data', None)
            if data is None:
                return None
            if isinstance(data, pd.DataFrame):
                if data.empty:
                    return None
                val = data['quality_score'].iloc[0]
            else:
                if not data:
                    return None
                val = data[0].get('quality_score') if isinstance(data[0], dict) else data[0][0]
            score = float(val) if pd.notna(val) else None
            if score is not None:
                self._set_quality_score_to_cache(symbol, frequency, '', '', score)
            return score
        except Exception as e:
            logger.debug(f"DB质量分查询失败: {symbol}/{frequency} - {e}")
            return None

    def _get_kdata_from_duckdb(self, stock_code: str, period: str, count: int, data_source: str = None, asset_type: AssetType = None) -> pd.DataFrame:
        """优化：从DuckDB获取K线数据（使用视图自动选择最优质量数据）"""
        try:
            if not self.duckdb_operations:
                logger.debug("DuckDB operations不可用")
                return pd.DataFrame()

            # 使用asset-separated架构的数据库
            final_asset_type = asset_type or AssetType.STOCK_A
            database_path = self.asset_manager.get_database_path(final_asset_type)
            logger.debug(f"DuckDB路径: {database_path}, 资产类型: {final_asset_type.value}")

            # 周期到频率的映射（DuckDB表中的frequency字段）
            from core.plugin_types import Period
            frequency = Period.to_duckdb_frequency(period)
            logger.debug(f"周期映射: {period} -> {frequency}")

            # R246 修复: 直接使用存储侧统一表名, 与 AssetSeparatedDatabaseManager.
            # _generate_table_name (asset_database_manager.py L1479) 保持一致。
            # 此前调用 generate_table_name 生成 "kline_data_default_t_1min_all" 等动态表名,
            # 与存储侧 "historical_kline_data" 不一致, 视图查询必然抛
            # "Table with name kline_data_default_* does not exist" Catalog Error。
            table_name = "historical_kline_data"

            # 优化：在CTE中添加WHERE条件，提前过滤数据，减少JOIN的数据量
            view_query = f"""
                WITH ranked_data AS (
                    SELECT 
                        hkd.*,
                        dqm.quality_score,
                        -- 数据源优先级：有质量评分的优先，其次按数据源名称稳定排序
                        CASE 
                            WHEN dqm.quality_score IS NOT NULL THEN dqm.quality_score
                            WHEN hkd.data_source = 'tongdaxin' THEN 60.0
                            WHEN hkd.data_source = 'akshare' THEN 55.0
                            WHEN hkd.data_source = 'tushare' THEN 65.0
                            ELSE 50.0
                        END as effective_quality_score,
                        ROW_NUMBER() OVER (
                            PARTITION BY hkd.symbol, hkd.timestamp, hkd.frequency 
                            ORDER BY 
                                -- 首先按有效质量分数排序（降序）
                                CASE 
                                    WHEN dqm.quality_score IS NOT NULL THEN dqm.quality_score
                                    WHEN hkd.data_source = 'tongdaxin' THEN 60.0
                                    WHEN hkd.data_source = 'akshare' THEN 55.0
                                    WHEN hkd.data_source = 'tushare' THEN 65.0
                                    ELSE 50.0
                                END DESC,
                                -- 其次按更新时间排序（降序，最新的优先）
                                hkd.updated_at DESC
                        ) as quality_rank
                    FROM {table_name} hkd
                    -- R285 修复：JOIN 断链（与 unified_best_quality_kline 视图一致）——
                    -- 原条件 DATE(hkd.timestamp) = dqm.check_date 中 check_date 为落库
                    -- 评估当天日期，历史 K 线（timestamp=交易日）永远无法命中，质量分恒
                    -- NULL → 回退硬编码数据源优先级。改为关联每 symbol+data_source+
                    -- frequency 最近一次评估记录，使质量优选对历史数据真正生效。
                    -- R287 P0-2：JOIN 目标改为物化表 monitor_latest（每 symbol+data_source+
                    -- frequency 仅一行，落库时同步维护），消除每次查询的全表 GROUP BY 聚合。
                    LEFT JOIN monitor_latest dqm ON (
                        hkd.symbol = dqm.symbol
                        AND hkd.data_source = dqm.data_source
                        AND hkd.frequency = dqm.frequency
                    )
                    -- R292 修复：日线查询隔离分钟垃圾行。
                    -- 根因：import_execution_engine 曾将分钟K线以 frequency='1d' 落库
                    -- （_standardize_kline_data_fields 硬编码默认 '1d'），导致日线视图混入
                    -- 大量同日期不同时刻（09:31~15:00）的分钟行 → 展示"数据多但日期集中"。
                    -- 日线/周/月线的合法 timestamp 恒为 00:00:00，此处仅对 '1d' 做时刻过滤。
                    WHERE hkd.symbol = ? AND hkd.frequency = ?
                      AND (hkd.frequency <> '1d' OR CAST(hkd.timestamp AS TIME) = TIME '00:00:00')
                )
                SELECT 
                    symbol as code, 
                    timestamp as datetime, 
                    open, high, low, close, volume, amount
                FROM ranked_data 
                WHERE quality_rank = 1
                ORDER BY timestamp DESC 
                LIMIT ?
            """

            logger.debug(f"[视图查询] database={database_path}, symbol={stock_code}, frequency={frequency}, limit={count}")

            try:
                # 先尝试质量优选视图
                _vq_start = time.perf_counter()
                result = self.duckdb_operations.execute_query(
                    database_path=database_path,
                    query=view_query,
                    params=[stock_code, frequency, count]
                )
                _vq_elapsed = (time.perf_counter() - _vq_start) * 1000
                logger.debug(f"[视图查询-DB] {stock_code}/{frequency} 耗时 {_vq_elapsed:.1f}ms")

                if result.success and result.data is not None:
                    if isinstance(result.data, pd.DataFrame):
                        df = result.data
                    else:
                        df = pd.DataFrame(result.data)

                    if not df.empty:
                        logger.info(f"[视图查询成功（质量优选）]: {stock_code}, frequency={frequency}, {len(df)} 条记录")
                        # R285 修复：不再把 data_source 强制覆盖为 'best_quality' 伪源。
                        # 视图 SELECT hkd.* 已透传真实数据源，覆盖会污染溯源：
                        # 增量合并（_incremental_fill_kdata）→ _persist_kdata_to_duckdb
                        # 落库时 data_source 主键列保留伪值 → DB 出现 best_quality 假源。
                        if 'data_source' not in df.columns:
                            df['data_source'] = 'best_quality'
                        
                        # 仅缓存最新一条记录的评分（数据按timestamp DESC排序，iloc[0]即最新）
                        if 'quality_score' in df.columns and len(df) > 0:
                            latest_ts = df['datetime'].iloc[0]
                            latest_score = df['quality_score'].iloc[0]
                            check_date = pd.Timestamp(latest_ts).date() if pd.notna(latest_ts) else datetime.now().date()
                            real_source = str(df['data_source'].iloc[0]) if 'data_source' in df.columns else 'best_quality'
                            self._set_quality_score_to_cache(
                                symbol=stock_code,
                                frequency=frequency,
                                data_source=real_source,
                                check_date=check_date.isoformat(),
                                score=float(latest_score) if pd.notna(latest_score) else 0.0
                            )
                        
                        # 修复：对从DuckDB获取的数据进行标准化和排序
                        df = self._standardize_kdata_format(df, stock_code)
                        return df
                    else:
                        logger.warning(f"⚠️  [视图查询结果为空]: {stock_code}, frequency={frequency}")
                else:
                    logger.warning(f"⚠️  [视图查询失败或无数据]: {stock_code}, success={result.success if result else None}")

            except Exception as view_error:
                logger.error(f"❌ [视图查询异常]: {stock_code}, error={view_error}")
                import traceback
                logger.error(f"详细错误:\n{traceback.format_exc()}")

            # 如果视图查询失败或无数据，尝试查询基础表
            try:
                base_query = f"""
                    SELECT 
                        symbol as code, 
                        timestamp as datetime, 
                        open, high, low, close, volume, amount,
                        data_source
                    FROM historical_kline_data
                    WHERE symbol = ? 
                      AND frequency = ?
                      -- R292 修复：与视图查询一致，日线隔离分钟垃圾行
                      AND (frequency <> '1d' OR CAST(timestamp AS TIME) = TIME '00:00:00')
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """

                logger.info(f"[基础表查询] 尝试使用基础表获取数据...")

                result = self.duckdb_operations.execute_query(
                    database_path=database_path,
                    query=base_query,
                    params=[stock_code, frequency, count]
                )

                if result.success and result.data is not None:
                    if isinstance(result.data, pd.DataFrame):
                        df = result.data
                    else:
                        df = pd.DataFrame(result.data)

                    if not df.empty:
                        logger.info(f"[基础表查询成功]: {stock_code}, frequency={frequency}, {len(df)} 条记录, 数据源: {df['data_source'].unique().tolist() if 'data_source' in df.columns else '未知'}")
                        # 修复：对从DuckDB获取的数据进行标准化和排序
                        df = self._standardize_kdata_format(df, stock_code)
                        return df
                    else:
                        logger.warning(f"⚠️  [基础表查询结果为空]: {stock_code}, frequency={frequency}")
                else:
                    logger.warning(f"⚠️  [基础表查询失败或无数据]: {stock_code}, success={result.success if result else None}")

            except Exception as base_error:
                logger.error(f"❌ [基础表查询异常]: {stock_code}, error={base_error}")
                import traceback
                logger.error(f"详细错误:\n{traceback.format_exc()}")

            logger.warning(f"❌ [DuckDB无数据]: {stock_code} (视图和基础表都无数据)")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"❌ [DuckDB数据获取失败]: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame()

    async def _store_asset_list_to_duckdb(self, data: pd.DataFrame, asset_type: AssetType, market: str = None):
        """存储资产列表到DuckDB（异步后备机制数据持久化）"""
        try:
            if data.empty or not self.duckdb_operations:
                return

            db_path = self.asset_manager.get_database_path(asset_type)
            table_name = "asset_metadata"

            logger.debug(f"📦 开始存储{asset_type.value}资产列表到DuckDB: {len(data)} 条记录")

            asset_type_value = asset_type.value if hasattr(asset_type, 'value') else str(asset_type)

            prepared_data = data.copy()

            if 'code' in prepared_data.columns:
                prepared_data['symbol'] = prepared_data['code']
            if 'list_date' in prepared_data.columns:
                prepared_data['listing_date'] = prepared_data['list_date']
            if 'status' in prepared_data.columns:
                prepared_data['listing_status'] = prepared_data['status']

            prepared_data['asset_type'] = asset_type_value
            prepared_data['update_time'] = datetime.now()

            if market and 'market' not in prepared_data.columns:
                prepared_data['market'] = market.upper()

            field_mapping = {
                'code': 'symbol',
                'name': 'name',
                'market': 'market',
                'industry': 'industry',
                'sector': 'sector',
                'list_date': 'listing_date',
                'status': 'listing_status'
            }

            final_columns = []
            for col in ['symbol', 'name', 'market', 'industry', 'sector', 'listing_date', 'listing_status', 'asset_type', 'update_time']:
                if col in prepared_data.columns:
                    final_columns.append(col)

            if not final_columns:
                logger.warning(f"⚠️ 资产列表数据缺少必要字段，无法存储到DuckDB")
                return

            prepared_data = prepared_data[final_columns]

            result = self.duckdb_operations.insert_dataframe(
                database_path=db_path,
                table_name=table_name,
                dataframe=prepared_data,
                upsert=True
            )

            if result.success:
                logger.info(f"资产列表持久化成功: {asset_type_value}, {len(prepared_data)} 条记录")
            else:
                logger.warning(f"⚠️ 资产列表持久化失败: {asset_type_value}")

        except Exception as e:
            logger.warning(f"⚠️ 资产列表存储到DuckDB失败: {e}")

    # K线数据获取统一使用DuckDB优先架构

    def get_historical_data(self, symbol: str, asset_type=None, period: str = "D", count: int = 365, **kwargs) -> Optional[pd.DataFrame]:
        """
        获取历史数据（兼容AssetService接口）

        Args:
            symbol: 资产代码
            asset_type: 资产类型（兼容性参数，可选）
            period: 周期
            count: 数据条数
            **kwargs: 其他参数

        Returns:
            Optional[pd.DataFrame]: 历史数据
        """
        try:
            from core.plugin_types import AssetType
            final_asset_type = asset_type if asset_type else AssetType.STOCK_A
            return self.get_kdata(symbol, period, count, asset_type=final_asset_type)
        except Exception as e:
            logger.error(f"获取历史数据失败 {symbol}: {e}")
            return None

    # 数据获取统一使用DuckDB优先架构

    def _standardize_kdata_format(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """标准化K线数据格式"""
        try:
            if df.empty:
                return df

            # 确保必要的列存在
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.warning(f"K线数据缺少必要列: {missing_columns}")
                return pd.DataFrame()

            # 修复：处理datetime列和索引，避免datetime既是索引又是列
            if 'datetime' not in df.columns:
                # 如果没有datetime列，尝试从索引或date列获取
                if isinstance(df.index, pd.DatetimeIndex):
                    # 关键修复：将索引转为列后，必须重置索引为数字索引
                    df['datetime'] = df.index
                    df = df.reset_index(drop=True)
                    logger.debug("从DatetimeIndex创建datetime列并重置索引")
                elif 'date' in df.columns:
                    df['datetime'] = pd.to_datetime(df['date'])
                else:
                    logger.warning("K线数据缺少datetime字段")
                    return pd.DataFrame()
            else:
                # 确保datetime列是datetime类型
                # R292 修复：数值型日期（如 20240814）会被 pd.to_datetime 按纳秒
                # 时间戳解释为 1970-01-01 → 所有日期基本相同。先转字符串按
                # YYYYMMDD 解析；同时清理上游 errors='coerce' 残留的 NaT 日期行。
                _dt_series = df['datetime']
                if pd.api.types.is_numeric_dtype(_dt_series):
                    df['datetime'] = pd.to_datetime(
                        _dt_series.astype(str), errors='coerce')
                else:
                    df['datetime'] = pd.to_datetime(_dt_series, errors='coerce')
                _na_mask = df['datetime'].isna()
                if _na_mask.any():
                    logger.warning(
                        f"K线数据包含 {int(_na_mask.sum())} 行无效datetime，已移除")
                    df = df[~_na_mask]
                # 修复：如果datetime同时是索引名，重置索引避免歧义
                if df.index.name == 'datetime' or isinstance(df.index, pd.DatetimeIndex):
                    df = df.reset_index(drop=True)
                    logger.debug("检测到datetime同时是列和索引，已重置索引")

            # 数据清洗
            df = df.replace([np.inf, -np.inf], np.nan)
            df = df.dropna(subset=['close'])  # 至少要有收盘价

            # 修复：确保code和symbol字段都存在
            if 'code' not in df.columns and 'symbol' not in df.columns:
                df['code'] = stock_code
                df['symbol'] = stock_code
                logger.debug(f"添加code和symbol字段: {stock_code}")
            elif 'symbol' in df.columns and 'code' not in df.columns:
                df['code'] = df['symbol']
                logger.debug(f"数据已包含symbol字段，添加code字段")
            elif 'code' in df.columns and 'symbol' not in df.columns:
                df['symbol'] = df['code']
                logger.debug(f"数据已包含code字段，添加symbol字段")

            # 修复：确保adj_close和adj_factor字段存在（用于复权策略）
            if 'adj_close' not in df.columns:
                df['adj_close'] = df['close']
                logger.debug("添加adj_close字段，使用close值")
            
            if 'adj_factor' not in df.columns:
                df['adj_factor'] = 1.0
                logger.debug("添加adj_factor字段，默认值为1.0")

            # 确保amount字段存在
            if 'amount' not in df.columns:
                df['amount'] = 0.0

            # 数据类型转换 — pd.to_numeric本身已是C级优化，直接逐列调用
            for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # 修复：统一按时间升序排序，确保K线图显示顺序正确
            # 这是解决K线数据展示顺序错乱问题的关键修复
            if 'datetime' in df.columns and not df.empty:
                try:
                    df = df.sort_values(by='datetime', ascending=True).reset_index(drop=True)
                    logger.debug(f"K线数据已按时间升序排序: {stock_code}, 记录数={len(df)}, 时间范围={df['datetime'].min()} ~ {df['datetime'].max()}")
                except Exception as sort_error:
                    logger.warning(f"⚠️ K线数据排序失败: {stock_code}, 错误={sort_error}")
                    # 如果排序失败，记录警告但不中断流程

            return df

        except Exception as e:
            logger.error(f"标准化K线数据格式失败: {e}")
            return pd.DataFrame()

    def invalidate_stock_info_cache(self):
        """使股票信息缓存失效，下次调用 get_stock_info() 将重新加载全表"""
        self._stock_info_cache = None
        logger.debug("股票信息缓存已失效")

    def get_stock_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取股票信息（带内存缓存，首次调用加载全表并 set_index('code')，后续 O(1) 查找）"""
        try:
            if self._stock_info_cache is None:
                stock_list = self.get_stock_list()
                if stock_list.empty:
                    self._stock_info_cache = pd.DataFrame()
                else:
                    self._stock_info_cache = stock_list.set_index('code')
                    logger.debug(f"股票信息缓存已初始化，共 {len(self._stock_info_cache)} 条记录")

            if self._stock_info_cache.empty:
                return None

            if stock_code in self._stock_info_cache.index:
                record = self._stock_info_cache.loc[stock_code]
                if isinstance(record, pd.DataFrame):
                    return record.iloc[0].to_dict()
                return record.to_dict()

            return None

        except Exception as e:
            logger.error(f"获取股票信息失败: {stock_code} - {e}")
            return None

    def search_stocks(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索股票"""
        try:
            stock_list = self.get_stock_list()
            if stock_list.empty:
                return []

            keyword_lower = keyword.lower()
            matches = stock_list[
                (stock_list['code'].str.lower().str.contains(keyword_lower, na=False)) |
                (stock_list['name'].str.lower().str.contains(keyword_lower, na=False))
            ]

            return matches.to_dict('records')

        except Exception as e:
            logger.error(f"搜索股票失败: {keyword} - {e}")
            return []

    def get_fund_flow(self) -> Dict[str, Any]:
        """获取资金流数据 - 通过TET框架和数据源插件获取真实数据"""
        try:
            fund_flow_data = {
                'sector_flow_rank': pd.DataFrame(),
                'individual_flow': pd.DataFrame(),
                'market_flow': {}
            }

            if self.tet_enabled and self.tet_pipeline:
                logger.info("使用TET数据管道获取资金流数据")

                try:
                    # 获取板块资金流数据
                    sector_query = StandardQuery(
                        asset_type=AssetType.SECTOR,
                        data_type=DataType.SECTOR_FUND_FLOW,
                        symbol="",
                        extra_params={"period": "1d", "limit": 50}
                    )
                    sector_result = self.tet_pipeline.process(sector_query)

                    if sector_result and sector_result.success and sector_result.data is not None:
                        if isinstance(sector_result.data, pd.DataFrame):
                            fund_flow_data['sector_flow_rank'] = sector_result.data
                        else:
                            # 如果返回的是列表或字典，转换为DataFrame
                            fund_flow_data['sector_flow_rank'] = pd.DataFrame(sector_result.data)
                        logger.info(f" TET获取板块资金流数据成功: {len(fund_flow_data['sector_flow_rank'])} 条记录")
                    else:
                        logger.warning("TET板块资金流数据为空或失败")

                except Exception as e:
                    logger.warning(f" TET获取板块资金流数据失败: {e}")

                try:
                    # 获取个股资金流数据
                    individual_query = StandardQuery(
                        asset_type=AssetType.STOCK_A,
                        data_type=DataType.INDIVIDUAL_FUND_FLOW,
                        symbol="",
                        extra_params={"period": "1d", "limit": 100}
                    )
                    individual_result = self.tet_pipeline.process(individual_query)

                    if individual_result and individual_result.success and individual_result.data is not None:
                        if isinstance(individual_result.data, pd.DataFrame):
                            fund_flow_data['individual_flow'] = individual_result.data
                        else:
                            fund_flow_data['individual_flow'] = pd.DataFrame(individual_result.data)
                        logger.info(f" TET获取个股资金流数据成功: {len(fund_flow_data['individual_flow'])} 条记录")
                    else:
                        logger.warning("TET个股资金流数据为空或失败")

                except Exception as e:
                    logger.warning(f" TET获取个股资金流数据失败: {e}")

                try:
                    # 获取市场整体资金流数据
                    market_query = StandardQuery(
                        asset_type=AssetType.INDEX,
                        data_type=DataType.MAIN_FUND_FLOW,
                        symbol="",
                        extra_params={"period": "1d"}
                    )
                    market_result = self.tet_pipeline.process(market_query)

                    if market_result and market_result.success and market_result.data is not None:
                        if isinstance(market_result.data, dict):
                            fund_flow_data['market_flow'] = market_result.data
                        elif isinstance(market_result.data, pd.DataFrame) and not market_result.data.empty:
                            # 将DataFrame转换为字典
                            fund_flow_data['market_flow'] = market_result.data.to_dict('records')[0] if len(market_result.data) > 0 else {}
                        else:
                            fund_flow_data['market_flow'] = {}
                        logger.info(f" TET获取市场资金流数据成功")
                    else:
                        logger.warning("TET市场资金流数据为空或失败")

                except Exception as e:
                    logger.warning(f" TET获取市场资金流数据失败: {e}")

            else:
                logger.info("降级到传统数据源模式获取资金流数据")

            # 所有数据源均无资金流数据：返回空结构（不再注入模拟数据，避免干扰真实场景）
            if (fund_flow_data['sector_flow_rank'].empty and
                fund_flow_data['individual_flow'].empty and
                    not fund_flow_data['market_flow']):
                logger.warning("所有数据源均无资金流数据，返回空结构。请配置资金流向数据源以获取真实数据。")
                fund_flow_data = {
                    'sector_flow_rank': pd.DataFrame(),
                    'individual_flow': pd.DataFrame(),
                    'market_flow': {
                        'total_net_inflow': None,
                        'main_net_inflow': None,
                        'retail_net_inflow': None,
                        'north_fund_inflow': None,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'market_status': 'open' if 9 <= datetime.now().hour <= 15 else 'closed'
                    }
                }

            return fund_flow_data

        except Exception as e:
            logger.error(f"获取资金流数据失败: {e}")
            return {
                'sector_flow_rank': pd.DataFrame(),
                'individual_flow': pd.DataFrame(),
                'market_flow': {}
            }

    def test_connection(self) -> bool:
        """测试数据源连接"""
        try:
            if not self._data_sources:
                logger.warning("无可用数据源，连接测试失败")
                return False

            if self._current_source in self._data_sources:
                test_list = self._data_sources[self._current_source].get_stock_list('sh')
                return not test_list.empty
            else:
                logger.warning(f"当前数据源 {self._current_source} 未在可用数据源中找到")
                return False

        except Exception as e:
            logger.error(f"测试数据源连接失败: {e}")
            return False

    def get_latest_price(self, stock_code: str) -> float:
        """获取最新价格"""
        try:
            # 获取最近的K线数据
            kdata = self.get_kdata(stock_code, 'D', 1)
            if not kdata.empty:
                return float(kdata['close'].iloc[-1])
            else:
                return 0.0

        except Exception as e:
            logger.error(f"获取最新价格失败: {stock_code} - {e}")
            return 0.0

    def cleanup(self):
        """清理资源"""
        try:
            # 关闭线程池
            if hasattr(self, '_executor'):
                self._executor.shutdown(wait=True)

            # UnifiedSQLiteAccess 自动管理连接，无需手动关闭

            logger.info("统一数据管理器资源清理完成")

        except Exception as e:
            logger.error(f"清理资源失败: {e}")

    def _legacy_get_asset_list(self, asset_type: AssetType, market: str = None) -> pd.DataFrame:
        """
        从传统数据源获取资产列表（后备方法）

        当DuckDB没有数据时，尝试从传统数据源获取资产列表。
        支持所有资产类型的统一获取。

        Args:
            asset_type: 资产类型枚举
            market: 市场过滤条件

        Returns:
            pd.DataFrame: 资产列表数据，包含列：['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type']
        """
        import pandas as pd
        from ..plugin_types import AssetType

        # 防重入保护 (R204-P0-3): 统一入口阻断所有资产类型的递归环
        # (stock/index/fund/bond 的 _get_xxx_asset_list → xxx_service → StockRepository
        #  → data_manager.get_stock_list → get_asset_list → _legacy_get_asset_list 回环)
        if getattr(_recursion_guard, 'in_legacy_get_asset_list', False):
            logger.warning("检测到 _legacy_get_asset_list 递归重入，已阻断循环（返回空列表）")
            return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])
        _recursion_guard.in_legacy_get_asset_list = True

        try:
            asset_type_value = asset_type.value if hasattr(asset_type, 'value') else str(asset_type)
            logger.debug(f"从传统数据源获取{asset_type_value}资产列表")

            if asset_type in [AssetType.SECTOR, AssetType.INDUSTRY_SECTOR,
                              AssetType.CONCEPT_SECTOR, AssetType.STYLE_SECTOR,
                              AssetType.THEME_SECTOR]:
                return self._get_sector_asset_list(asset_type, market)
            elif asset_type in [AssetType.STOCK_A, AssetType.STOCK_B, AssetType.STOCK_H,
                                AssetType.STOCK_US, AssetType.STOCK_HK]:
                return self._get_stock_asset_list(asset_type, market)
            elif asset_type == AssetType.INDEX:
                return self._get_index_asset_list(asset_type, market)
            elif asset_type == AssetType.FUND:
                return self._get_fund_asset_list(asset_type, market)
            elif asset_type == AssetType.BOND:
                return self._get_bond_asset_list(asset_type, market)
            elif asset_type == AssetType.CRYPTO:
                return self._get_crypto_asset_list(asset_type, market)
            elif asset_type == AssetType.FUTURES:
                return self._get_futures_asset_list(asset_type, market)
            elif asset_type == AssetType.FOREX:
                return self._get_forex_asset_list(asset_type, market)
            elif asset_type == AssetType.OPTION:
                return self._get_option_asset_list(asset_type, market)
            elif asset_type == AssetType.WARRANT:
                return self._get_warrant_asset_list(asset_type, market)
            else:
                logger.warning(f"⚠️ 不支持的资产类型: {asset_type_value}")
                return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

        except Exception as e:
            logger.error(f"从传统数据源获取{asset_type}资产列表失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])
        finally:
            _recursion_guard.in_legacy_get_asset_list = False

    def _get_sector_asset_list(self, asset_type: AssetType, market: str = None) -> pd.DataFrame:
        """获取板块资产列表"""
        import pandas as pd
        try:
            asset_type_value = asset_type.value if hasattr(asset_type, 'value') else str(asset_type)
            logger.debug(f"获取板块资产列表: {asset_type_value}")

            if self._sector_data_service is not None:
                try:
                    if hasattr(self._sector_data_service, 'get_all_sectors'):
                        sectors = self._sector_data_service.get_all_sectors()
                        if sectors is not None and not sectors.empty:
                            df = pd.DataFrame({
                                'code': sectors.get('code', sectors.get('sector_code', [])),
                                'name': sectors.get('name', sectors.get('sector_name', [])),
                                'market': 'all',
                                'industry': sectors.get('industry', []),
                                'sector': asset_type_value,
                                'list_date': sectors.get('list_date', []),
                                'status': 'active',
                                'asset_type': asset_type_value
                            })
                            logger.info(f"从SectorDataService获取{asset_type_value}资产列表成功: {len(df)} 个")
                            return df
                except Exception as e:
                    logger.warning(f"⚠️ SectorDataService获取板块列表失败: {e}")

            logger.info(f"📭 SectorDataService未初始化或无数据，返回空{asset_type_value}列表")
            return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])
        except Exception as e:
            logger.error(f"获取板块资产列表失败: {e}")
            return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def _get_stock_asset_list(self, asset_type: AssetType, market: str = None) -> pd.DataFrame:
        """获取股票资产列表"""
        import pandas as pd
        # 防重入保护 (R204-P0-3): 阻断 get_asset_list → StockService → StockManager →
        # DataAccess → StockRepository → data_manager.get_stock_list → get_asset_list 无限递归环
        if getattr(_recursion_guard, 'in_get_stock_asset_list', False):
            logger.warning("检测到 _get_stock_asset_list 递归重入，已阻断循环（返回空列表）")
            return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])
        _recursion_guard.in_get_stock_asset_list = True
        try:
            stock_service_ready = (
                hasattr(self, '_stock_service') and self._stock_service is not None
                and hasattr(self._stock_service, 'get_stock_list')
            )
            if stock_service_ready:
                # R244-P0-2 修复: StockService 初始化期间(_do_initialize → _load_stock_list
                # → DataAccess → StockRepository → data_manager.get_stock_list)会自我调用
                # 回同一尚未初始化完成的实例，_ensure_initialized() 抛 "Service StockService
                # is not initialized"，导致传统后备数据源在启动期失效并产生 ERROR 日志。
                # 未初始化完成时跳过服务路径（走 DuckDB/空后备），初始化完成后自动恢复。
                if not getattr(self._stock_service, '_initialized', False):
                    logger.debug(f"StockService 尚未初始化完成，跳过服务路径获取{asset_type}资产列表")
                else:
                    stock_list = self._stock_service.get_stock_list()

                    if stock_list is None:
                        logger.debug(f"StockService返回None，无法获取{asset_type}列表")
                        return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

                    if isinstance(stock_list, pd.DataFrame):
                        is_empty = stock_list.empty
                    elif isinstance(stock_list, (list, tuple)):
                        is_empty = len(stock_list) == 0
                    else:
                        logger.warning(f"StockService返回了未知类型: {type(stock_list)}")
                        return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

                    if is_empty:
                        logger.debug(f"StockService返回空数据，无法获取{asset_type}列表")
                        return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

                    if isinstance(stock_list, pd.DataFrame):
                        df = stock_list.copy()
                    else:
                        df = pd.DataFrame(stock_list)

                    if 'code' not in df.columns and 'symbol' in df.columns:
                        df['code'] = df['symbol']

                    df['asset_type'] = asset_type.value

                    df = self._filter_stocks_by_asset_type(df, asset_type)

                    if len(df) == 0:
                        logger.debug(f"过滤后无{asset_type.value}数据")
                        return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

                    if self.duckdb_available and hasattr(self, '_persist_fallback_data') and self._persist_fallback_data:
                        try:
                            asyncio.create_task(self._store_asset_list_to_duckdb(df, asset_type, market))
                        except Exception as persist_error:
                            logger.warning(f"⚠️ 触发资产列表持久化任务失败: {persist_error}")

                    return df

            logger.debug(f"StockService不可用，无法获取{asset_type}列表")
            return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])
        except Exception as e:
            logger.error(f"获取股票资产列表失败: {e}")
            return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])
        finally:
            _recursion_guard.in_get_stock_asset_list = False

    def _filter_stocks_by_asset_type(self, df: pd.DataFrame, asset_type: AssetType) -> pd.DataFrame:
        """
        根据资产类型过滤股票数据

        Args:
            df: 股票数据DataFrame
            asset_type: 资产类型枚举

        Returns:
            过滤后的DataFrame
        """
        try:
            if df.empty:
                return df

            market_col = df['market'].astype(str).str.upper().str.strip()

            stock_type_market_mapping = {
                AssetType.STOCK_A: ['SH', 'SZ', 'CSI', 'A'],
                AssetType.STOCK_B: ['B'],
                AssetType.STOCK_H: ['HK', 'HKEX', 'H股'],
                AssetType.STOCK_US: ['US', 'NASDAQ', 'NYSE', 'AMEX', '美股'],
                AssetType.STOCK_HK: ['HK', 'HKEX', '港股'],
            }

            if asset_type in stock_type_market_mapping:
                valid_markets = stock_type_market_mapping[asset_type]
                mask = market_col.isin(valid_markets)
                filtered_df = df[mask].copy()

                if len(filtered_df) > 0:
                    logger.debug(f"资产类型过滤: {asset_type.value} → {len(filtered_df)} 条 (市场匹配: {valid_markets})")
                    return filtered_df
                else:
                    logger.debug(f"资产类型过滤: {asset_type.value} → 0 条 (无匹配市场: {valid_markets})")
                    return df

            return df

        except Exception as e:
            logger.warning(f"资产类型过滤失败: {e}")
            return df

    def _get_index_asset_list(self, asset_type: AssetType, market: str = None) -> pd.DataFrame:
        """获取指数资产列表 - 使用fallback加载器"""
        import pandas as pd
        logger.debug(f"获取指数资产列表: {asset_type.value}")

        if self.fallback_loader is not None:
            return self.fallback_loader.get_asset_list(asset_type, market)

        return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def _get_fund_asset_list(self, asset_type: AssetType, market: str = None) -> pd.DataFrame:
        """获取基金资产列表 - 使用fallback加载器"""
        import pandas as pd
        logger.debug(f"获取基金资产列表: {asset_type.value}")

        if self.fallback_loader is not None:
            return self.fallback_loader.get_asset_list(asset_type, market)

        return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def _get_bond_asset_list(self, asset_type: AssetType, market: str = None) -> pd.DataFrame:
        """获取债券资产列表 - 使用fallback加载器"""
        import pandas as pd
        logger.debug(f"获取债券资产列表: {asset_type.value}")

        if self.fallback_loader is not None:
            return self.fallback_loader.get_asset_list(asset_type, market)

        return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def _get_crypto_asset_list(self, asset_type: AssetType, market: str = None) -> pd.DataFrame:
        """获取加密货币资产列表 - 使用fallback加载器"""
        import pandas as pd
        logger.debug(f"获取加密货币资产列表: {asset_type.value}")

        if self.fallback_loader is not None:
            return self.fallback_loader.get_asset_list(asset_type, market)

        return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def _get_futures_asset_list(self, asset_type: AssetType, market: str = None) -> pd.DataFrame:
        """获取期货资产列表 - 使用fallback加载器"""
        import pandas as pd
        logger.debug(f"获取期货资产列表: {asset_type.value}")

        if self.fallback_loader is not None:
            return self.fallback_loader.get_asset_list(asset_type, market)

        return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def _get_forex_asset_list(self, asset_type: AssetType, market: str = None) -> pd.DataFrame:
        """获取外汇资产列表 - 使用fallback加载器"""
        import pandas as pd
        logger.debug(f"获取外汇资产列表: {asset_type.value}")

        if self.fallback_loader is not None:
            return self.fallback_loader.get_asset_list(asset_type, market)

        return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def _get_option_asset_list(self, asset_type: AssetType, market: str = None) -> pd.DataFrame:
        """获取期权资产列表 - 使用fallback加载器"""
        import pandas as pd
        logger.debug(f"获取期权资产列表: {asset_type.value}")

        if self.fallback_loader is not None:
            return self.fallback_loader.get_asset_list(asset_type, market)

        return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def _get_warrant_asset_list(self, asset_type: AssetType, market: str = None) -> pd.DataFrame:
        """获取涡轮资产列表 - 使用fallback加载器"""
        import pandas as pd
        logger.debug(f"获取涡轮资产列表: {asset_type.value}")

        if self.fallback_loader is not None:
            return self.fallback_loader.get_asset_list(asset_type, market)

        return pd.DataFrame(columns=['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type'])

    def get_current_source(self) -> str:
        """获取当前数据源"""
        return getattr(self, '_current_source', 'tet_framework')

    def get_historical_data(self, symbol: str, asset_type: AssetType = AssetType.STOCK_A,
                            period: str = "D", count: int = 365, **kwargs) -> Optional[pd.DataFrame]:
        """
        获取历史数据（兼容AssetService接口）

        Args:
            symbol: 资产代码
            asset_type: 资产类型
            period: 周期
            count: 数据条数
            **kwargs: 其他参数

        Returns:
            Optional[pd.DataFrame]: 历史数据
        """
        try:
            if asset_type == AssetType.STOCK_A:
                return self.get_kdata(symbol, period, count, asset_type=asset_type)
            else:
                return self.get_asset_data(symbol, asset_type, DataType.HISTORICAL_KLINE, period, **kwargs)
        except Exception as e:
            logger.error(f"获取历史数据失败 {symbol}: {e}")
            return None

    def get_asset_data(self, symbol: str, asset_type: Union[AssetType, str] = AssetType.STOCK_A,
                       data_type: DataType = DataType.HISTORICAL_KLINE,
                       period: str = "D", **kwargs) -> Optional[pd.DataFrame]:
        """
        获取资产数据（TET模式）

        Args:
            symbol: 交易代码
            asset_type: 资产类型（支持AssetType枚举或字符串）
            data_type: 数据类型
            period: 周期
            **kwargs: 其他参数

        Returns:
            Optional[pd.DataFrame]: 标准化数据
        """
        # 确保asset_type是AssetType枚举
        if isinstance(asset_type, str):
            try:
                asset_type = AssetType(asset_type)
            except ValueError:
                logger.warning(f"无效的资产类型字符串: {asset_type}, 使用默认值: {AssetType.STOCK_A.value}")
                asset_type = AssetType.STOCK_A
        
        if self.tet_enabled and self.tet_pipeline:
            try:
                logger.info(f" 使用TET模式获取数据: {symbol} ({asset_type.value})")

                # 将count参数移到extra_params中，因为StandardQuery没有count参数
                extra_params = kwargs.copy()
                count = extra_params.pop('count', None)
                if count is not None:
                    extra_params['count'] = count

                # R284 修复：K线主链路 DB 优先——切换股票时先查 DuckDB，
                # DB 命中即返回（数据不满足 count 时由 _incremental_fill_kdata
                # 自动回源补齐并更新数据库，复用 R263 增量闭环）；
                # 仅 DB 空时才走 TET 网络管道。
                # 背景：get_asset_data 原实现无任何 DB 查询，直接 tet_pipeline.process，
                # TET 内存缓存键含 symbol（tet_data_pipeline.py L1252-1263）且 TTL 仅 5 分钟，
                # 切换不同股票必然 miss → 每次都重新联网遍历数据源（DB 明明已落库 1,129,151 条）。
                if (data_type == DataType.HISTORICAL_KLINE and self.duckdb_available
                        and not extra_params.get('start_date') and not extra_params.get('end_date')):
                    db_count = int(count or 365)
                    db_df = self._get_kdata_from_duckdb(
                        symbol, period, db_count, asset_type=asset_type)
                    if not db_df.empty:
                        # R285 修复4：DB 直读质量校验——DB 只有一份低质量数据时
                        # 不直接返回（会让坏数据直达图表），置空走下方 TET 网络管道
                        # 重拉并落库覆盖。
                        from core.plugin_types import Period
                        db_freq = Period.to_duckdb_frequency(period)
                        db_score = self._get_db_quality_score(symbol, db_freq, asset_type)
                        if db_score is not None and db_score < self._DB_QUALITY_MIN_SCORE:
                            logger.warning(f" 主链路DB直读: {symbol} ({period}) 质量分偏低 "
                                           f"{db_score:.1f}，改走TET网络管道重拉")
                        else:
                            # 数据不足/隔天增量：自动回源补齐 + 合并去重 + 落库更新
                            merged_df = self._incremental_fill_kdata(
                                symbol, period, db_count, db_df, asset_type)
                            if merged_df is not None and not merged_df.empty:
                                db_df = merged_df
                            if len(db_df) > db_count:
                                db_df = db_df.tail(db_count).reset_index(drop=True)
                            logger.info(f" 主链路DB直读: {symbol} ({period}) | "
                                        f"{len(db_df)} 条 | 免联网")
                            return db_df
                
                query = StandardQuery(
                    symbol=symbol,
                    asset_type=asset_type,
                    data_type=data_type,
                    period=period,
                    # R284: start_date/end_date 提为顶层字段——transform_query
                    # (tet_data_pipeline.py L529-530) 只读 query.start_date/end_date，
                    # 原实现仅放 extra_params 导致区间参数静默丢失。
                    start_date=extra_params.get('start_date'),
                    end_date=extra_params.get('end_date'),
                    extra_params=extra_params
                )

                result = self.tet_pipeline.process(query)

                # 记录使用的数据源
                data_source = None
                if result and hasattr(result, 'source_info') and result.source_info:
                    data_source = result.source_info.get('provider')
                    logger.info(f" TET数据获取成功: {symbol} | 数据源: {data_source} | 记录数: {len(result.data) if result.data is not None else 0}")
                else:
                    logger.info(f" TET数据获取成功: {symbol} | 记录数: {len(result.data) if result.data is not None else 0}")

                # R277 修复：TET 成功获取的历史K线立即落库。
                # 原实现仅 UDM.get_kdata 的 fallback 分支落库（_persist_kdata_to_duckdb），
                # 而 UI 主链路（repository TET 模式 → AssetService → get_asset_data）成功后
                # 直接返回不落库 → 重启后 DuckDB 仍无数据 → 每次都重新联网遍历数据源。
                if (result and result.data is not None and not result.data.empty
                        and data_type == DataType.HISTORICAL_KLINE):
                    try:
                        self._persist_kdata_to_duckdb(
                            result.data, symbol, period, asset_type,
                            data_source=data_source)
                        logger.info(f" TET历史K线已落库: {symbol} ({period}) | "
                                    f"{len(result.data)} 条 | 数据源: {data_source or 'Unknown'}")
                    except Exception as persist_error:
                        logger.warning(f" TET历史K线落库失败: {symbol} - {persist_error}")

                    # R278 数据治理：TET 主链路灌入增强数据质量监控器（六维度评分 + 低分告警）。
                    # 此前 monitor_data_quality 全项目零调用，监控器无真实数据可监控。
                    try:
                        from core.services.enhanced_data_quality_monitor import EnhancedDataQualityMonitor
                        monitor = self._get_enhanced_quality_monitor()
                        if monitor is not None:
                            monitor.monitor_data_quality(
                                data_source=data_source or 'tet_plugin',
                                data_type='kline',
                                data=result.data,
                                symbol=symbol)
                    except Exception as monitor_error:
                        logger.debug(f"数据质量监控灌入失败: {symbol} - {monitor_error}")

                # R292 B1：统一形态——TET 管道 _standardize_data_types 强制 datetime
                # set_index 到索引（索引形态），直接返回会让 UI 判 'datetime' not in
                # columns 走数字轴 + 渲染器 date2num(索引) 画蜡烛 → 蜡烛出视野、
                # 图表范围偶发错乱。返回前统一还原为 datetime 列 + 数字索引。
                try:
                    return self._standardize_kdata_format(result.data, symbol)
                except Exception:
                    return result.data

            except Exception as e:
                logger.warning(f" TET模式获取数据失败: {symbol} - {e}")
                logger.info("降级到传统数据获取模式")

        # 降级到传统方式
        if asset_type == AssetType.STOCK_A:
            logger.info(f" 使用传统模式获取股票数据: {symbol}")
            data = self._legacy_get_stock_data(symbol, period, **kwargs)
            if data is not None:
                logger.info(f" 传统模式数据获取成功: {symbol} | 数据源: DataAccess | 记录数: {len(data)}")
            else:
                logger.warning(f" 传统模式数据获取失败: {symbol}")
            return data
        else:
            logger.warning(f" 传统模式不支持资产类型: {asset_type.value} | 建议启用TET模式")
            return None

    def _get_intraday_data(self, symbol: str, asset_type: AssetType = AssetType.STOCK_A,
                           date: str = None, **kwargs) -> pd.DataFrame:
        """获取分时数据（TET模式，R295-G4 数据链路层）

        构造 StandardQuery(data_type=DataType.INTRADAY_DATA) 走 TET 管道：
        tet_data_pipeline._extract_from_source else 兜底 (L844-853) 自动调
        plugin.fetch_data(symbol, 'intraday_data', **extra_params) → 通达信
        get_minute_time_data（pytdx 空/异常时降级腾讯分时源）。

        Args:
            symbol: 股票代码
            asset_type: 资产类型（默认股票）
            date: 交易日 YYYYMMDD, 默认实时分时 (透传 extra_params['date'])
            **kwargs: 其他参数

        Returns:
            pd.DataFrame: index=datetime, 列 [price, vol, amount]; 失败返回空 DataFrame
        """
        try:
            if not self.tet_enabled or not self.tet_pipeline:
                logger.warning(f"TET模式未启用，无法获取分时数据: {symbol}")
                return pd.DataFrame()

            from ..tet_data_pipeline import StandardQuery
            from ..plugin_types import DataType

            extra_params = kwargs.copy()
            if date:
                extra_params['date'] = date

            query = StandardQuery(
                symbol=symbol,
                asset_type=asset_type,
                data_type=DataType.INTRADAY_DATA,
                period='1min',  # 分时语义 (TET transform_query 仅透传 metadata)
                extra_params=extra_params
            )

            result = self.tet_pipeline.process(query)
            data = getattr(result, 'data', None)
            if isinstance(data, pd.DataFrame) and not data.empty:
                logger.info(f" TET分时数据获取成功: {symbol} | {len(data)} 点")
                return data
            logger.warning(f" TET分时数据为空: {symbol} {date or '实时'}")
            return pd.DataFrame()

        except Exception as e:
            logger.warning(f" TET模式获取分时数据失败: {symbol} - {e}")
            return pd.DataFrame()

    def get_intraday_data(self, symbol: str, date: str = None,
                          asset_type: AssetType = AssetType.STOCK_A, **kwargs) -> pd.DataFrame:
        """获取分时数据（公有入口，R295-G4 图表层轮询调用）

        薄封装 _get_intraday_data：构造 StandardQuery(INTRADAY_DATA) 走 TET 管道，
        数据源层空/异常自动降级腾讯分时源。失败返回空 DataFrame
        （index=DatetimeIndex，列 [price, vol, amount]）。
        """
        return self._get_intraday_data(symbol, asset_type=asset_type, date=date, **kwargs)

    def _format_asset_list(self, asset_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """格式化资产列表为标准格式"""
        if asset_data.empty:
            return []

        cols = ['symbol', 'name', 'asset_type', 'market']
        df = asset_data[cols].copy()
        for c in cols:
            if c not in df.columns:
                df[c] = ''
        if 'status' not in asset_data.columns:
            df['status'] = 'active'
        else:
            df['status'] = asset_data['status']
        result = df.fillna('').to_dict('records')

        return result

    def register_data_source_plugin(self, plugin_id: str, adapter, priority: int = 0, weight: float = 1.0) -> bool:
        """
        注册数据源插件到路由器和TET管道

        Args:
            plugin_id: 插件ID
            adapter: 插件适配器
            priority: 优先级
            weight: 权重

        Returns:
            bool: 注册是否成功
        """
        try:
            # 检查TET管道是否可用
            if not (hasattr(self, 'tet_pipeline') and self.tet_pipeline):
                logger.warning("TET数据管道不可用，无法注册插件")
                return False

            # 注册到TET管道的路由器
            if hasattr(self.tet_pipeline, 'router'):
                router = self.tet_pipeline.router
                router_success = router.register_data_source(plugin_id, adapter, priority, weight)
                if router_success:
                    logger.info(f" 插件 {plugin_id} 已注册到TET数据管道路由器")
                else:
                    logger.error(f" 插件 {plugin_id} 注册到TET数据管道路由器失败")
                    return False
            else:
                logger.error("TET数据管道缺少路由器")
                return False

            # 关键修复：同时注册到TET管道的适配器字典
            if hasattr(self.tet_pipeline, '_adapters'):
                self.tet_pipeline._adapters[plugin_id] = adapter
                logger.info(f" 插件 {plugin_id} 已注册到TET管道适配器字典")
            else:
                logger.warning("TET管道缺少_adapters属性")

            # 如果适配器有对应的插件实例，也注册到_plugins字典
            if hasattr(adapter, 'plugin') and hasattr(self.tet_pipeline, '_plugins'):
                self.tet_pipeline._plugins[plugin_id] = adapter.plugin
                logger.info(f" 插件 {plugin_id} 已注册到TET管道插件字典")

            # 记录已注册的数据源信息
            plugin_info = {
                'plugin_id': plugin_id,
                'adapter': adapter,
                'priority': priority,
                'weight': weight,
                'display_name': getattr(adapter, 'display_name', plugin_id),
                'supported_assets': getattr(adapter, 'supported_assets', []),
                'status': 'active'
            }
            self._registered_data_sources[plugin_id] = plugin_info
            logger.info(f" 数据源 {plugin_id} 信息已记录")

            return True

        except Exception as e:
            logger.error(f" 注册数据源插件失败 {plugin_id}: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return False

    def get_registered_data_sources(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有已注册的数据源

        Returns:
            Dict[str, Dict[str, Any]]: 已注册的数据源信息
        """
        return self._registered_data_sources.copy()

    def get_available_data_source_names(self) -> List[str]:
        """
        获取可用数据源名称列表

        Returns:
            List[str]: 数据源名称列表
        """
        # 基础数据源
        base_sources = ['东方财富', '新浪财经', '同花顺']

        # 添加已注册的插件数据源
        plugin_sources = []
        for plugin_id, info in self._registered_data_sources.items():
            display_name = info.get('display_name', plugin_id)
            if display_name not in base_sources:
                plugin_sources.append(display_name)

        # 合并并去重
        all_sources = base_sources + plugin_sources
        return list(dict.fromkeys(all_sources))  # 保持顺序的去重

    def get_data_source_info(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定数据源的详细信息

        Args:
            plugin_id: 数据源插件ID

        Returns:
            Optional[Dict[str, Any]]: 数据源信息或None
        """
        return self._registered_data_sources.get(plugin_id)

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取数据管理器的统计信息

        用于数据质量监控和系统状态评估

        Returns:
            Dict[str, Any]: 统计信息字典，包含：
                - requests: 请求统计
                - cache: 缓存统计
                - data_sources: 数据源统计
                - data_quality: 数据质量统计
                - system: 系统状态统计
        """
        try:
            # 1. 请求统计
            request_stats = self._stats.copy()

            # 计算成功率
            total_requests = request_stats.get('requests_total', 0)
            if total_requests > 0:
                success_rate = (request_stats.get('requests_completed', 0) / total_requests) * 100
                request_stats['success_rate'] = round(success_rate, 2)
            else:
                request_stats['success_rate'] = 0.0

            # 2. 缓存统计
            cache_total = request_stats.get('cache_hits', 0) + request_stats.get('cache_misses', 0)
            if cache_total > 0:
                cache_hit_rate = (request_stats.get('cache_hits', 0) / cache_total) * 100
            else:
                cache_hit_rate = 0.0

            cache_stats = {
                'hits': request_stats.get('cache_hits', 0),
                'misses': request_stats.get('cache_misses', 0),
                'hit_rate': round(cache_hit_rate, 2),
                'total_queries': cache_total
            }

            # 3. 数据源统计
            data_source_stats = {
                'total_registered': len(self._registered_data_sources),
                'available_sources': len(self.get_available_data_source_names()),
                'registered_plugins': list(self._registered_data_sources.keys())
            }

            # 4. 数据质量统计（基于请求统计估算）
            # 为UI数据质量监控提供所需的字段
            completed = request_stats.get('requests_completed', 0)
            failed = request_stats.get('requests_failed', 0)

            quality_stats = {
                # UI期望的字段
                'expected_records': total_requests,  # 预期记录数
                'actual_records': completed,  # 实际记录数
                'total_count': completed,  # 总数（实际完成的）
                'error_count': failed,  # 错误数
                'failed_records': failed,  # 失败记录数
                'cancelled_records': request_stats.get('requests_cancelled', 0),  # 取消记录数
                'inconsistent_records': 0,  # 不一致记录数（暂无）
                'invalid_records': failed,  # 无效记录数（与失败数相同）
                'duplicate_records': 0,  # 重复记录数（暂无）
                'quality_score': request_stats.get('success_rate', 0) / 100,  # 质量分数（0-1）
                'last_update_time': datetime.now()  # 最后更新时间
            }

            # 5. 系统状态统计
            system_stats = {
                'initialized': self._is_initialized,
                'tet_enabled': self.tet_enabled,
                'plugins_discovered': self._plugins_discovered,
                'active_requests': len(self._active_requests),
                'pending_requests': len(self._pending_requests),
                'completed_requests': len(self._completed_requests)
            }

            # 6. DuckDB统计（如果可用）
            duckdb_stats = {}
            if hasattr(self, 'duckdb_manager') and self.duckdb_manager:
                try:
                    # 获取DuckDB连接池统计
                    duckdb_stats = {
                        'enabled': True,
                        'database_path': str(getattr(self.duckdb_manager, 'db_path', 'unknown'))
                    }
                except Exception:
                    duckdb_stats = {'enabled': False}
            else:
                duckdb_stats = {'enabled': False}

            # 组装完整统计信息
            statistics = {
                'requests': request_stats,
                'cache': cache_stats,
                'data_sources': data_source_stats,
                'data_quality': quality_stats,
                'system': system_stats,
                'duckdb': duckdb_stats,
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'total_requests': total_requests,
                    'success_rate': request_stats.get('success_rate', 0),
                    'cache_hit_rate': round(cache_hit_rate, 2),
                    'data_quality_score': quality_stats['quality_score'],
                    'active_data_sources': data_source_stats['total_registered']
                }
            }

            return statistics

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

            # 返回默认统计信息
            return {
                'requests': self._stats.copy(),
                'cache': {'hits': 0, 'misses': 0, 'hit_rate': 0.0},
                'data_sources': {'total_registered': 0, 'available_sources': 0},
                'data_quality': {'expected_records': 0, 'actual_records': 0, 'quality_score': 0.0},
                'system': {'initialized': self._is_initialized},
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

    def _legacy_get_stock_data(self, symbol: str, period: str = "D", asset_type=None, **kwargs) -> Optional[pd.DataFrame]:
        """传统方式获取股票数据"""
        try:
            from ..data.data_access import DataAccess
            data_access = DataAccess()
            return data_access.get_kdata(symbol, period, asset_type=asset_type)
        except Exception as e:
            logger.error(f"传统方式获取股票数据失败: {e}")
            return None

    async def get_stock_data(self, code: str, freq: str, start_date=None, end_date=None, request_id=None):
        """统一的数据请求方法，区分历史和实时数据"""
        if request_id:
            self._register_request(request_id)

        try:
            # 检查是否需要实时数据
            if self._needs_realtime_data(end_date):
                return await self.realtime_data_strategy.get_data(code, freq, start_date, end_date)
            else:
                return await self.history_data_strategy.get_data(code, freq, start_date, end_date)
        except Exception as e:
            logger.error(f"Error fetching data for {code}: {e}")
            return None
        finally:
            if request_id:
                self._unregister_request(request_id)

    def _needs_realtime_data(self, end_date=None):
        """判断是否需要实时数据"""
        if end_date is None:
            # 没有指定结束日期，需要实时数据
            return True

        # 如果结束日期是今天或未来，需要实时数据
        today = datetime.now().date()
        if isinstance(end_date, str):
            try:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                return True

        if isinstance(end_date, datetime):
            end_date = end_date.date()

        return end_date >= today

    async def request_data(self, stock_code: str, data_type: str = 'kdata',
                           period: str = 'D', time_range: str = "最近1年",
                           asset_type: AssetType = AssetType.STOCK_A, **kwargs) -> Any:
        """请求数据（优化：支持多资产类型）

        Args:
            stock_code: 股票代码（或其他资产代码）
            data_type: 数据类型，如'kdata', 'financial', 'news'等
            period: 周期，如'D'(日线)、'W'(周线)、'M'(月线)、'60'(60分钟)等
            time_range: 时间范围，如"最近7天"、"最近30天"、"最近1年"等
            asset_type: 资产类型（默认为股票，支持CRYPTO/FUTURES/FOREX/INDEX/FUND等）
            **kwargs: 其他参数

        Returns:
            请求的数据
        """
        try:
            # 参数验证
            if not stock_code or not str(stock_code).strip():
                logger.error(f"无效的股票代码: {stock_code}")
                return None

            # 清理股票代码
            stock_code = str(stock_code).strip()

            # 处理周期映射（使用统一的 Period 枚举类）
            from core.plugin_types import Period
            actual_period = Period.normalize(period)

            # 处理时间范围映射（转换为天数）
            time_range_map = {
                "最近7天": 7,
                "最近30天": 30,
                "最近90天": 90,
                "最近180天": 180,
                "最近1年": 365,
                "最近2年": 365 * 2,
                "最近3年": 365 * 3,
                "最近5年": 365 * 5,
                "全部": None  # 表示所有可用数据（不限制日期范围）
            }

            # 获取天数，默认为365天（约1年）
            days = time_range_map.get(time_range, 365)

            # R277 修复：时间范围语义由"条数"改为"自然日日期区间"。
            # 原实现把"最近1年"直接映射为 count=365（条数语义），而 365 条日线 ≈ 1.4-1.5 自然年，
            # 导致"最近1年"实际显示约 1.5 年数据（起点提前约 6 个月）。
            # 修复：按周期把自然日换算为"覆盖该区间所需K线根数"作为 LIMIT 上限（adjusted_count），
            # 并在 _get_kdata 返回后按日期区间精确裁剪，保证起点/终点与用户选择一致。
            start_date = None
            end_date = None
            count = days
            if days is not None:
                from datetime import datetime, timedelta
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                count = self._calc_period_adjusted_count(days, actual_period)
                logger.info(f"请求数据：代码={stock_code}, 类型={data_type}, 周期={actual_period}, "
                            f"时间范围={days}天 ({start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}), "
                            f"覆盖条数={count}, 资产类型={asset_type.value}")
            else:
                logger.info(f"请求数据：代码={stock_code}, 类型={data_type}, 周期={actual_period}, "
                            f"时间范围=全部, 资产类型={asset_type.value}")

            if data_type == 'kdata':
                # 获取K线数据（传递资产类型与日期区间）
                return await self._get_kdata(stock_code, period=actual_period, count=count,
                                             asset_type=asset_type, start_date=start_date, end_date=end_date)
            elif data_type in ('intraday', 'intraday_data', 'minute_time'):
                # R295-G4 分时数据链路: 走 TET 管道 (StandardQuery INTRADAY_DATA)
                # → plugin.fetch_data(symbol, 'intraday_data', date=...)
                return self._get_intraday_data(
                    stock_code, asset_type=asset_type, date=kwargs.get('date'))
            elif data_type == 'financial':
                # 获取财务数据
                return await self._get_financial_data(stock_code)
            elif data_type == 'news':
                # 获取新闻数据
                return await self._get_news(stock_code)
            elif data_type == 'all':
                # 获取所有数据（传递资产类型）
                kdata = await self._get_kdata(stock_code, period=actual_period, count=count, asset_type=asset_type)
                financial = await self._get_financial_data(stock_code)
                news = await self._get_news(stock_code)
                return {
                    'kdata': kdata,
                    'financial': financial,
                    'news': news
                }
            else:
                logger.error(f"未知的数据类型: {data_type}")
                return None
        except Exception as e:
            logger.error(f"请求数据失败: {e}", exc_info=True)
            return None

    async def get_data_async(self, symbol: str, asset_type: AssetType = AssetType.STOCK_A,
                           data_type: str = 'kdata', period: str = 'D', 
                           time_range: int = 365, **kwargs) -> Any:
        """获取数据（异步适配器方法）

        这是 request_data 方法的适配器，用于兼容调用方使用的参数格式。
        调用方使用 symbol 和整数 time_range，而 request_data 使用 stock_code 和字符串 time_range。

        Args:
            symbol: 股票代码（或其他资产代码）
            asset_type: 资产类型（默认为股票）
            data_type: 数据类型，如'kdata', 'financial', 'news'等
            period: 周期，如'D'(日线)、'W'(周线)、'M'(月线)等
            time_range: 时间范围（天数，整数）
            **kwargs: 其他参数

        Returns:
            请求的数据
        """
        try:
            # 将整数 time_range 转换为 request_data 期望的字符串格式
            time_range_map = {
                7: "最近7天",
                30: "最近30天",
                90: "最近90天",
                180: "最近180天",
                365: "最近1年",
                365 * 2: "最近2年",
                365 * 3: "最近3年",
                365 * 5: "最近5年"
            }
            
            # 如果 time_range 是整数，转换为对应的字符串描述
            if isinstance(time_range, int):
                time_range_str = time_range_map.get(time_range, f"最近{time_range}天")
            else:
                time_range_str = str(time_range)
            
            # 调用 request_data 方法
            return await self.request_data(
                stock_code=symbol,
                data_type=data_type,
                period=period,
                time_range=time_range_str,
                asset_type=asset_type,
                **kwargs
            )
        except Exception as e:
            logger.error(f"get_data_async 获取数据失败: {e}", exc_info=True)
            return None

    async def _get_kdata(self, stock_code: str, period: str = 'D', count: int = 365,
                         asset_type: AssetType = AssetType.STOCK_A,
                         start_date=None, end_date=None) -> pd.DataFrame:
        """获取K线数据（优化：支持多资产类型）

        Args:
            stock_code: 股票代码（或其他资产代码）
            period: 周期，如'D'、'W'、'M'
            count: 获取的条数（LIMIT 上限）
            asset_type: 资产类型（默认为股票）
            start_date: R277 可选，日期区间起点（datetime/Timestamp/str），返回后按此精确裁剪
            end_date: R277 可选，日期区间终点，返回后按此精确裁剪

        Returns:
            K线DataFrame
        """
        try:
            logger.info(f"获取K线数据: {stock_code}, 周期={period}, 数量={count}, 资产类型={asset_type.value}")

            # 尝试从服务容器解析ChartService
            from core.services.chart_service import ChartService
            chart_service = self.service_container.resolve(ChartService)

            if chart_service:
                df = await chart_service.get_kdata_async(stock_code, period, count, asset_type=asset_type)
                return self._clip_kdata_by_date(df, start_date, end_date)

            # 如果没有ChartService，使用默认数据源
            # 注意：core.data_manager已迁移，使用当前实例
            data_manager = self

            if data_manager:
                # 传递asset_type参数
                df = data_manager.get_kdata(stock_code, period, count, asset_type=asset_type)
                return self._clip_kdata_by_date(df, start_date, end_date)

            logger.error("无法获取K线数据：未找到数据服务")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"获取K线数据失败: {e}", exc_info=True)
            return pd.DataFrame()

    @staticmethod
    def _calc_period_adjusted_count(days: int, period: str) -> int:
        """R277: 按周期把自然日天数换算为覆盖该区间的K线根数（LIMIT 上限，含冗余）

        交易日约为自然日的 250/365 ≈ 0.685 倍，各周期每自然日的K线根数近似：
        日线 0.7、周线 0.14、月线 0.03、60分钟 2.8、30分钟 5.6、15分钟 11、
        5分钟 33、1分钟 165。取向上整数并保留冗余，确保 LIMIT 条数能覆盖
        完整日期区间，随后由调用方按日期精确裁剪。
        """
        factor_map = {'1m': 170, '5m': 35, '15m': 12, '30m': 6, '1H': 3,
                      'D': 1, 'W': 0.2, 'M': 0.05}
        factor = factor_map.get(period, 1)
        count = int(days * factor) + 20
        return max(count, days)

    @staticmethod
    def _clip_kdata_by_date(df, start_date, end_date) -> pd.DataFrame:
        """R277: 按日期区间裁剪K线数据（start_date/end_date 为 None 时不裁剪）"""
        if df is None or df.empty or start_date is None or end_date is None:
            return df if df is not None else pd.DataFrame()
        try:
            ts = pd.to_datetime(df['datetime']) if 'datetime' in df.columns else pd.to_datetime(df.index)
            start_ts = pd.Timestamp(start_date)
            end_ts = pd.Timestamp(end_date)
            mask = (ts >= start_ts) & (ts <= end_ts)
            clipped = df[mask].copy()
            logger.info(f"按日期区间裁剪K线: 原 {len(df)} 条 -> {len(clipped)} 条 "
                        f"({start_ts.date()} ~ {end_ts.date()})")
            return clipped
        except Exception as e:
            logger.warning(f"按日期区间裁剪K线失败: {e}，返回原数据")
            return df if df is not None else pd.DataFrame()

    async def _get_financial_data(self, stock_code: str) -> Dict[str, Any]:
        """获取财务数据（增强版：集成DuckDB存储）

        Args:
            stock_code: 股票代码

        Returns:
            财务数据字典
        """
        try:
            logger.info(f"获取财务数据: {stock_code}")

            cache_key = f"financial_{stock_code}"

            # 1. 尝试从DuckDB获取财务数据
            if self.duckdb_available and self.duckdb_operations:
                financial_data = await self._get_financial_from_duckdb(stock_code)
                if financial_data:
                    return financial_data

            # 2. 通过TET管道获取财务数据
            if self.tet_enabled and self.tet_pipeline:
                try:
                    from ..tet_data_pipeline import StandardQuery
                    from ..plugin_types import AssetType, DataType

                    query = StandardQuery(
                        symbol=stock_code,
                        asset_type=AssetType.STOCK_A,
                        data_type=DataType.FINANCIAL_STATEMENT,
                        provider=self._current_source
                    )

                    result = self.tet_pipeline.process(query)
                    if result and result.data:
                        # 存储到DuckDB
                        if self.duckdb_available:
                            await self._store_financial_to_duckdb(stock_code, result.data)
                        return result.data

                except Exception as e:
                    logger.warning(f"TET管道获取财务数据失败: {e}")

            # 3. 回退到传统方式（保持兼容性）
            return {}

        except Exception as e:
            logger.error(f"获取财务数据失败: {e}", exc_info=True)
            return {}

    def _migrate_legacy_financial_tables(self, db_path: str) -> None:
        """R257：将分裂期旧财报表数据惰性合并到统一表（不 DROP 旧表，失败仅 warning 不阻断）。

        旧表：financial_statement_unified_data_manager_default /
              financial_statement_enhanced_duckdb_downloader_default
        新表：DEFAULT_FINANCIAL_PLUGIN 统一生成（financial_statement_system_default）。
        仅当检测到旧表存在时执行 INSERT INTO 新表 SELECT * FROM 旧表
        ON CONFLICT (symbol, report_date, report_type) DO NOTHING；
        列不匹配等失败仅 warning（列名对齐列入 R258）。
        """
        global _financial_migration_done
        if _financial_migration_done or not self.duckdb_operations or not self.table_manager:
            return
        with _financial_migration_lock:
            if _financial_migration_done:
                return
            try:
                from ..database.table_manager import TableType, DEFAULT_FINANCIAL_PLUGIN
                new_table = self.table_manager.generate_table_name(
                    TableType.FINANCIAL_STATEMENT, DEFAULT_FINANCIAL_PLUGIN
                )
                legacy_tables = [
                    legacy for legacy in _LEGACY_FINANCIAL_TABLES
                    if legacy != new_table
                    and _financial_table_row_count(self.duckdb_operations, db_path, legacy) > 0
                ]
                if not legacy_tables:
                    _financial_migration_done = True
                    return
                ensured = self.table_manager.ensure_table_exists(
                    db_path, TableType.FINANCIAL_STATEMENT, DEFAULT_FINANCIAL_PLUGIN
                )
                if not ensured:
                    logger.warning("旧财报表迁移失败：统一新表创建失败，跳过合并（不阻断）")
                    return
                for legacy in legacy_tables:
                    try:
                        result = self.duckdb_operations.execute_sql(
                            db_path,
                            f"INSERT INTO {ensured} SELECT * FROM {legacy} "
                            f"ON CONFLICT (symbol, report_date, report_type) DO NOTHING",
                        )
                        if result is not None and not getattr(result, "success", True):
                            logger.warning(
                                f"旧财报表合并失败（列名不匹配等，R258 对齐列名）: {legacy} -> {ensured}")
                        else:
                            logger.info(f"旧财报表数据合并完成: {legacy} -> {ensured}")
                    except Exception as e:
                        logger.warning(f"旧财报表合并异常（不阻断，R258 对齐列名）: {legacy}: {e}")
                _financial_migration_done = True
            except Exception as e:
                logger.warning(f"旧财报表迁移执行失败（不阻断）: {e}")

    async def _get_financial_from_duckdb(self, stock_code: str, asset_type: AssetType = None) -> Optional[Dict[str, Any]]:
        """从DuckDB获取财务数据"""
        try:
            # R257：入口惰性迁移旧财报表（幂等、失败不阻断）
            try:
                migration_asset_type = asset_type or AssetType.STOCK_A
                self._migrate_legacy_financial_tables(
                    self.asset_manager.get_database_path(migration_asset_type))
            except Exception as e:
                logger.warning(f"旧财报表迁移失败（不阻断）: {e}")
            # 使用与写入一致的表名（与 ensure_table_exists 同一生成路径，保证读写同表）
            if self.table_manager:
                from ..database.table_manager import TableType, DEFAULT_FINANCIAL_PLUGIN
                table_name = self.table_manager.generate_table_name(
                    TableType.FINANCIAL_STATEMENT, DEFAULT_FINANCIAL_PLUGIN
                )
            else:
                table_name = "financial_statements"

            query = f"""
                SELECT * FROM {table_name} 
                WHERE symbol = ? 
                ORDER BY report_date DESC 
                LIMIT 1
            """

            final_asset_type = asset_type or AssetType.STOCK_A
            result = self.duckdb_operations.execute_query(
                database_path=self.asset_manager.get_database_path(final_asset_type),
                query=query,
                params=[stock_code]
            )

            if result.success and result.data:
                return result.data[0] if result.data else None

            return None

        except Exception as e:
            logger.error(f"DuckDB财务数据获取失败: {e}")
            return None

    async def _store_financial_to_duckdb(self, stock_code: str, data: Dict[str, Any]):
        """存储财务数据到DuckDB"""
        try:
            # R258-P0: 空判断兼容 DataFrame 输入 (TET 管道 result.data 为 DataFrame,
            # `if not data` 对 DataFrame 抛 "truth value ambiguous" → 直接吞掉返回)
            if data is None:
                return
            if isinstance(data, pd.DataFrame):
                if data.empty:
                    return
            elif not data:
                return

            # 识别资产类型
            asset_type = self.asset_identifier.identify_asset_type(stock_code)
            db_path = self.asset_manager.get_database_path(asset_type)

            # R257：入口惰性迁移旧财报表（幂等、失败不阻断）
            try:
                self._migrate_legacy_financial_tables(db_path)
            except Exception as e:
                logger.warning(f"旧财报表迁移失败（不阻断）: {e}")

            # 确保财务数据表存在（返回实际表名，保证建表与插入使用同一表名）
            if self.table_manager:
                from ..database.table_manager import TableType, DEFAULT_FINANCIAL_PLUGIN
                table_name = self.table_manager.ensure_table_exists(
                    db_path, TableType.FINANCIAL_STATEMENT, DEFAULT_FINANCIAL_PLUGIN
                )
                if not table_name:
                    logger.error("创建财务数据表失败")
                    return
            else:
                table_name = "financial_statements"

            # 转换为DataFrame并存储
            # R258-P0 (交叉审查修正): 财务统一表主键 (symbol, report_date, report_type)
            # (table_manager.py:287), 表无 update_time 列 —— conflict_columns 引用不存在的
            # 列 → ON CONFLICT Binder Error → 全事务 ROLLBACK → 财务数据 0 行落库。
            # 真实调用传 TET 管道 result.data (unified_data_manager.py:2963-2967, DataFrame),
            # 需兼容 dict / DataFrame / list 三种输入。
            if isinstance(data, pd.DataFrame):
                df = data
            elif isinstance(data, dict):
                df = pd.DataFrame([data])
            else:
                df = pd.DataFrame(data)
            result = self.duckdb_operations.insert_dataframe(
                database_path=db_path,
                table_name=table_name,
                data=df,
                upsert=True,
                conflict_columns=['symbol', 'report_date', 'report_type']
            )

            if result.success:
                logger.info(f" 财务数据存储到DuckDB成功: {stock_code}")

        except Exception as e:
            logger.warning(f"DuckDB财务数据存储失败: {e}")

    def get_macro_economic_data(self, indicator: str, period: str = 'M', count: int = 100) -> pd.DataFrame:
        """
        获取宏观经济数据（新增方法：集成DuckDB存储）

        Args:
            indicator: 经济指标名称 (GDP, CPI, PMI等)
            period: 数据周期 (M/Q/Y)
            count: 数据条数

        Returns:
            宏观经济数据DataFrame
        """
        try:
            cache_key = f"macro_{indicator}_{period}_{count}"

            # 1. 多级缓存检查
            cached_data = self._get_cached_data(cache_key)
            if cached_data is not None and not cached_data.empty:
                return cached_data

            # 2. 从DuckDB获取
            if self.duckdb_available and self.duckdb_operations:
                df = self._get_macro_from_duckdb(indicator, period, count)
                if not df.empty:
                    self._cache_data(cache_key, df)
                    return df

            # 3. 通过TET管道获取
            if self.tet_enabled and self.tet_pipeline:
                try:
                    from ..tet_data_pipeline import StandardQuery
                    from ..plugin_types import AssetType, DataType

                    query = StandardQuery(
                        symbol=indicator,
                        asset_type=AssetType.MACRO,
                        data_type=DataType.MACRO_ECONOMIC,
                        period=period,
                        provider=self._current_source,
                        extra_params={'count': count}
                    )

                    result = self.tet_pipeline.process(query)
                    if result and result.data is not None:
                        if isinstance(result.data, pd.DataFrame) and not result.data.empty:
                            # 存储到DuckDB
                            self._store_macro_to_duckdb(result.data, indicator, period)
                            self._cache_data(cache_key, result.data)
                            return result.data

                except Exception as e:
                    logger.warning(f"TET管道获取宏观数据失败: {e}")

            # 4. 返回空DataFrame
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"获取宏观经济数据失败: {indicator} - {e}")
            return pd.DataFrame()

    def _get_macro_from_duckdb(self, indicator: str, period: str, count: int, asset_type: AssetType = None) -> pd.DataFrame:
        """从DuckDB获取宏观经济数据"""
        try:
            query = """
                SELECT * FROM macro_economic_data 
                WHERE indicator = ? AND frequency = ?
                ORDER BY release_date DESC 
                LIMIT ?
            """

            final_asset_type = asset_type or AssetType.STOCK_A
            result = self.duckdb_operations.execute_query(
                database_path=self.asset_manager.get_database_path(final_asset_type),
                query=query,
                params=[indicator, period, count]
            )

            if result.success and result.data:
                df = pd.DataFrame(result.data)
                logger.info(f" 从DuckDB获取宏观数据成功: {indicator}, {len(df)}条")
                return df

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"DuckDB宏观数据获取失败: {e}")
            return pd.DataFrame()

    def _store_macro_to_duckdb(self, data: pd.DataFrame, indicator: str, period: str):
        """存储宏观经济数据到DuckDB"""
        try:
            if not self.duckdb_operations or data.empty:
                return

            # 宏观数据使用MACRO资产类型
            from ..plugin_types import AssetType
            asset_type = AssetType.MACRO
            db_path = self.asset_manager.get_database_path(asset_type)

            # 确保宏观数据表存在
            if self.table_manager:
                from ..database.table_manager import TableType
                if not self.table_manager.ensure_table_exists(
                    db_path, TableType.MACRO_ECONOMIC, "unified_data_manager"
                ):
                    logger.error("创建宏观数据表失败")
                    return

            # 插入数据
            result = self.duckdb_operations.insert_dataframe(
                database_path=db_path,
                table_name="macro_economic_data",
                data=data,
                upsert=True
            )

            if result.success:
                logger.info(f" 宏观数据存储到DuckDB成功: {indicator}, {len(data)}条")

        except Exception as e:
            logger.warning(f"DuckDB宏观数据存储失败: {e}")

    # ==================== 增强数据下载功能接口 ====================

    async def download_historical_data_batch(self,
                                             symbols: List[str],
                                             period: str = 'D',
                                             days_back: int = 365) -> Dict[str, pd.DataFrame]:
        """
        批量下载历史数据 - 通过增强DuckDB下载器获取数据

        Args:
            symbols: 股票代码列表
            period: 数据周期
            days_back: 回溯天数

        Returns:
            Dict[symbol, DataFrame]: 下载的历史数据
        """
        if not hasattr(self, 'enhanced_duckdb_downloader') or not self.enhanced_duckdb_downloader:
            logger.error("增强DuckDB数据下载器不可用")
            return {}

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        return await self.enhanced_duckdb_downloader.download_historical_kline_data(
            symbols=symbols,
            period=period,
            start_date=start_date,
            end_date=end_date,
            force_update=False
        )

    async def update_stock_universe(self, market: str = 'all') -> pd.DataFrame:
        """
        更新股票池 - 通过增强DuckDB下载器获取股票列表

        Args:
            market: 市场代码

        Returns:
            DataFrame: 更新后的股票列表
        """
        if not hasattr(self, 'enhanced_duckdb_downloader') or not self.enhanced_duckdb_downloader:
            logger.error("增强DuckDB数据下载器不可用")
            return pd.DataFrame()

        return await self.enhanced_duckdb_downloader.download_stock_list(market=market)

    async def incremental_data_update(self, max_symbols: int = 100) -> Dict[str, Any]:
        """
        增量数据更新 - 通过增强DuckDB下载器进行数据更新

        Args:
            max_symbols: 最大处理股票数量

        Returns:
            Dict: 更新结果统计
        """
        if not hasattr(self, 'enhanced_duckdb_downloader') or not self.enhanced_duckdb_downloader:
            logger.error("增强DuckDB数据下载器不可用")
            return {}

        return await self.enhanced_duckdb_downloader.incremental_update_all_data(max_symbols=max_symbols)

    def get_data_storage_statistics(self) -> Dict[str, Any]:
        """
        获取数据存储统计 - 通过增强DuckDB下载器获取统计信息

        Returns:
            Dict: 数据存储统计信息
        """
        if not hasattr(self, 'enhanced_duckdb_downloader') or not self.enhanced_duckdb_downloader:
            logger.error("增强DuckDB数据下载器不可用")
            return {}

        from utils.async_utils import run_async_blocking
        return run_async_blocking(self.enhanced_duckdb_downloader.get_data_statistics())

    async def get_historical_data_batch(self,
                                       symbols: List[str],
                                       period: str = 'D',
                                       start_date: datetime = None,
                                       end_date: datetime = None,
                                       count: int = 365,
                                       asset_type: AssetType = AssetType.STOCK_A) -> Dict[str, pd.DataFrame]:
        """
        从数据库批量获取历史数据（非下载，直接查询）

        Args:
            symbols: 股票代码列表
            period: 数据周期
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            count: 数据条数（当start_date和end_date都为None时使用）
            asset_type: 资产类型

        Returns:
            Dict[symbol, DataFrame]: 历史数据字典
        """
        if not self.duckdb_available or not self.duckdb_operations:
            logger.error("DuckDB不可用，无法批量查询历史数据")
            return {}

        if not symbols:
            logger.warning("股票代码列表为空")
            return {}

        try:
            logger.info(f"开始批量查询历史数据: {len(symbols)} 只股票, period={period}, asset_type={asset_type.value}")

            # 周期到频率的映射（使用统一的 Period 枚举类）
            from core.plugin_types import Period
            frequency = Period.to_duckdb_frequency(period)

            # 获取数据库路径
            database_path = self.asset_manager.get_database_path(asset_type)
            logger.debug(f"使用数据库路径: {database_path}")

            # 性能优化：使用临时表替代IN子查询
            # 当symbols列表很大时，IN子查询性能急剧下降
            # 使用临时表+JOIN可以显著提升性能
            temp_table_name = f"temp_symbols_{int(datetime.now().timestamp())}"
            
            # 创建临时表并插入数据
            create_temp_table = f"""
                CREATE TEMPORARY TABLE {temp_table_name} (
                    symbol VARCHAR PRIMARY KEY
                )
            """
            
            # 准备批量插入数据
            symbols_values = [(s,) for s in symbols]
            
            # 准备查询参数
            query_params = [frequency]
            
            # 优先查询质量优选视图（使用临时表JOIN）
            view_query = f"""
                {create_temp_table}
            """
            
            # 执行创建临时表、插入数据、查询（在同一个connection中）
            with self.duckdb_manager.get_connection(database_path) as conn:
                import time
                
                # 记录开始时间
                start_time = time.time()
                temp_table_start = time.time()
                
                conn.execute(view_query)
                
                # 批量插入symbol到临时表
                conn.executemany(f"INSERT INTO {temp_table_name} VALUES (?)", symbols_values)
                
                temp_table_end = time.time()
                logger.debug(f"⏱️ 临时表创建和插入耗时: {temp_table_end - temp_table_start:.3f}秒")
                
                # 使用JOIN替代IN子查询（先去重，再取前count条）
                view_query = f"""
                    SELECT 
                        code, 
                        datetime, 
                        open, high, low, close, volume, amount
                    FROM (
                        SELECT 
                            symbol as code, 
                            timestamp as datetime, 
                            open, high, low, close, volume, amount,
                            ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY timestamp DESC) as rn
                        FROM (
                            SELECT 
                                hkd.symbol,
                                hkd.timestamp,
                                hkd.open, hkd.high, hkd.low, hkd.close, hkd.volume, hkd.amount,
                                hkd.frequency,
                                hkd.data_source,
                                hkd.updated_at,
                                dqm.quality_score
                            FROM historical_kline_data hkd
                            INNER JOIN {temp_table_name} temp ON hkd.symbol = temp.symbol
                            LEFT JOIN data_quality_monitor dqm ON (
                                hkd.symbol = dqm.symbol 
                                AND hkd.data_source = dqm.data_source 
                                AND CAST(hkd.timestamp AS DATE) = dqm.check_date
                                AND hkd.frequency = dqm.frequency
                            )
                            WHERE hkd.frequency = ?
                              AND (hkd.frequency <> '1d' OR CAST(hkd.timestamp AS TIME) = TIME '00:00:00')
                            QUALIFY ROW_NUMBER() OVER (
                                PARTITION BY hkd.symbol, hkd.timestamp, hkd.frequency 
                                ORDER BY 
                                    CASE 
                                        WHEN dqm.quality_score IS NOT NULL THEN dqm.quality_score
                                        WHEN hkd.data_source = 'tongdaxin' THEN 60.0
                                        WHEN hkd.data_source = 'akshare' THEN 55.0
                                        WHEN hkd.data_source = 'tushare' THEN 65.0
                                        ELSE 50.0
                                    END DESC,
                                    hkd.updated_at DESC
                            ) = 1
                        ) deduplicated_hkd
                    ) subq
                """

                # 添加日期过滤条件和行数限制
                if start_date or end_date:
                    if start_date:
                        view_query += " WHERE datetime >= ?"
                        query_params.append(start_date)
                    
                    if end_date:
                        if start_date:
                            view_query += " AND datetime <= ?"
                        else:
                            view_query += " WHERE datetime <= ?"
                        query_params.append(end_date)
                    
                    view_query += " AND rn <= ?"
                    query_params.append(count)
                else:
                    view_query += " WHERE rn <= ?"
                    query_params.append(count)

                # 按symbol和timestamp排序
                view_query += " ORDER BY code, datetime DESC"

                logger.debug(f"执行批量查询SQL: {view_query}")
                logger.debug(f"查询参数: {query_params}")
                logger.debug(f"参数类型: {[type(p).__name__ for p in query_params]}")

                # ========== EXPLAIN分析查询执行计划 ==========
                explain_start = time.time()
                try:
                    explain_query = f"EXPLAIN {view_query}"
                    explain_result = conn.execute(explain_query, query_params).fetchall()
                    
                    logger.info("=" * 80)
                    logger.info("查询执行计划分析")
                    logger.info("=" * 80)
                    
                    for i, row in enumerate(explain_result, 1):
                        logger.info(f"  步骤{i}: {row[0]}")
                    
                    # 检查是否使用了索引
                    explain_str = str(explain_result)
                    index_used = False
                    index_details = []
                    
                    if 'idx_' in explain_str:
                        index_used = True
                        for row in explain_result:
                            if 'idx_' in str(row[0]):
                                index_details.append(row[0])
                    
                    if index_used:
                        logger.info(f"索引使用情况: 已使用索引")
                        for detail in index_details:
                            logger.info(f"   - {detail}")
                    else:
                        logger.warning(f"⚠️  索引使用情况: 未使用索引（可能存在全表扫描）")
                    
                    # 检查是否有全表扫描
                    if 'SEQ_SCAN' in explain_str or 'sequential_scan' in explain_str:
                        logger.warning(f"⚠️  检测到全表扫描（SEQ_SCAN），性能可能受影响")
                    
                    # 检查是否有哈希连接
                    if 'HASH_JOIN' in explain_str or 'hash_join' in explain_str:
                        logger.info(f"使用哈希连接（HASH_JOIN）")
                    
                    # 检查是否有排序操作
                    if 'ORDER_BY' in explain_str or 'order_by' in explain_str:
                        logger.info(f"检测到排序操作（ORDER_BY）")
                    
                    logger.info("=" * 80)
                    
                    explain_end = time.time()
                    logger.debug(f"⏱️ EXPLAIN分析耗时: {explain_end - explain_start:.3f}秒")
                    
                except Exception as explain_error:
                    logger.warning(f"EXPLAIN分析失败: {explain_error}")
                
                # ========== 检查数据库索引信息 ==========
                try:
                    logger.info("=" * 80)
                    logger.info("📋 数据库索引信息")
                    logger.info("=" * 80)
                    
                    # 检查historical_kline_data表的索引
                    index_check = conn.execute("""
                        SELECT index_name 
                        FROM duckdb_indexes() 
                        WHERE table_name = 'historical_kline_data'
                        ORDER BY index_name
                    """).fetchall()
                    
                    if index_check:
                        logger.info(f"historical_kline_data表索引数量: {len(index_check)}")
                        for idx_info in index_check:
                            logger.info(f"  - {idx_info[0]}")
                    else:
                        logger.warning(f"⚠️  historical_kline_data表没有索引")
                        logger.info(f"💡 提示: 请在数据库初始化时创建索引，或在系统空闲时手动创建索引")
                    
                    # 检查data_quality_monitor表的索引
                    index_check = conn.execute("""
                        SELECT index_name 
                        FROM duckdb_indexes() 
                        WHERE table_name = 'data_quality_monitor'
                        ORDER BY index_name
                    """).fetchall()
                    
                    if index_check:
                        logger.info(f"data_quality_monitor表索引数量: {len(index_check)}")
                        for idx_info in index_check:
                            logger.info(f"  - {idx_info[0]}")
                    else:
                        logger.warning(f"⚠️  data_quality_monitor表没有索引")
                        logger.info(f"💡 提示: 请在数据库初始化时创建索引，或在系统空闲时手动创建索引")
                    
                    logger.info("=" * 80)
                    
                except Exception as index_error:
                    logger.warning(f"索引信息检查失败: {index_error}")

                try:
                    # 直接在同一个connection中执行查询
                    query_start = time.time()
                    result_df = conn.execute(view_query, query_params).df()
                    query_end = time.time()
                    
                    logger.info(f"⏱️ 查询执行耗时: {query_end - query_start:.3f}秒")
                    logger.info(f"⏱️ 总耗时（含EXPLAIN）: {query_end - start_time:.3f}秒")
                    
                    # 清理临时表
                    try:
                        cleanup_start = time.time()
                        conn.execute(f"DROP TABLE IF EXISTS {temp_table_name}")
                        cleanup_end = time.time()
                        logger.debug(f"⏱️ 清理临时表耗时: {cleanup_end - cleanup_start:.3f}秒")
                        logger.debug(f"已清理临时表: {temp_table_name}")
                    except Exception as cleanup_error:
                        logger.warning(f"清理临时表失败: {cleanup_error}")

                    if result_df is not None and not result_df.empty:
                        df = result_df
                        logger.info(f"批量查询成功: 共 {len(df)} 条记录, {df['code'].nunique()} 只股票")

                        # R285 修复：不再强制覆盖 data_source 为 'best_quality' 伪源
                        # （视图 SELECT hkd.* 已透传真实数据源，覆盖会污染溯源/落库主键）
                        if 'data_source' not in df.columns:
                            df['data_source'] = 'best_quality'

                        # ========== 数据标准化阶段性能监控 ==========
                        standardization_start = time.time()
                        
                        # 仅缓存最新一条记录的评分（数据按timestamp DESC排序，iloc[0]即最新）
                        if 'quality_score' in df.columns and len(df) > 0:
                            cache_start = time.time()
                            latest_code = df['code'].iloc[0]
                            latest_ts = df['datetime'].iloc[0]
                            latest_score = df['quality_score'].iloc[0]
                            check_date = pd.Timestamp(latest_ts).date() if pd.notna(latest_ts) else datetime.now().date()
                            real_source = str(df['data_source'].iloc[0]) if 'data_source' in df.columns else 'best_quality'
                            self._set_quality_score_to_cache(
                                symbol=latest_code,
                                frequency=frequency,
                                data_source=real_source,
                                check_date=check_date.isoformat(),
                                score=float(latest_score) if pd.notna(latest_score) else 0.0
                            )
                            cache_end = time.time()
                            logger.debug(f"⏱️ 质量评分缓存耗时: {cache_end - cache_start:.3f}秒")

                        # ========== 批量标准化优化 ==========
                        # 一次性标准化所有数据，而不是对每只股票单独调用标准化函数
                        # 这可以大幅提升性能（从61秒降低到几秒）
                        batch_standardize_start = time.time()
                        
                        try:
                            # 1. 数据清洗（一次性处理所有数据）
                            df = df.replace([np.inf, -np.inf], np.nan)
                            df = df.dropna(subset=['close'])
                            
                            # 2. 确保datetime是datetime类型
                            df['datetime'] = pd.to_datetime(df['datetime'])
                            
                            # 3. 确保symbol字段存在
                            if 'symbol' not in df.columns:
                                df['symbol'] = df['code']
                            
                            # 4. 添加缺失的字段（向量化操作）
                            if 'adj_close' not in df.columns:
                                df['adj_close'] = df['close']
                            
                            if 'adj_factor' not in df.columns:
                                df['adj_factor'] = 1.0
                            
                            if 'amount' not in df.columns:
                                df['amount'] = 0.0
                            
                            # 5. 数据类型转换（向量化操作）
                            for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                                if col in df.columns:
                                    df[col] = pd.to_numeric(df[col], errors='coerce')
                            
                            # 6. 按code和datetime排序（一次性排序所有数据）
                            df = df.sort_values(by=['code', 'datetime'], ascending=[True, True]).reset_index(drop=True)
                            
                            batch_standardize_end = time.time()
                            logger.debug(f"⏱️ 批量标准化耗时: {batch_standardize_end - batch_standardize_start:.3f}秒")
                            
                        except Exception as batch_error:
                            logger.warning(f"批量标准化失败，回退到逐个标准化: {batch_error}")
                            # 如果批量标准化失败，回退到原来的逐个标准化方式
                            batch_standardize_end = time.time()
                            logger.debug(f"⏱️ 批量标准化耗时（失败）: {batch_standardize_end - batch_standardize_start:.3f}秒")

                        # 按symbol分组（使用pandas groupby优化，避免循环扫描）
                        result_dict = {}
                        grouping_start = time.time()
                        
                        # 使用字典推导式分组，避免循环扫描DataFrame
                        # 这比逐个筛选快10-100倍
                        grouped = {code: group for code, group in df.groupby('code')}
                        
                        for symbol in symbols:
                            if symbol in grouped:
                                # 数据已经批量标准化过了，直接使用
                                result_dict[symbol] = grouped[symbol].copy()
                            else:
                                # 如果视图查询没有数据，尝试查询基础表
                                result_dict[symbol] = await self._get_kdata_from_base_table(
                                    database_path, symbol, frequency, start_date, end_date, count
                                )
                        
                        grouping_end = time.time()
                        logger.debug(f"⏱️ 数据分组耗时: {grouping_end - grouping_start:.3f}秒")
                        
                        standardization_end = time.time()
                        logger.info(f"⏱️ 数据标准化总耗时: {standardization_end - standardization_start:.3f}秒")
                        
                        # ========== 性能汇总 ==========
                        total_end = time.time()
                        total_time = total_end - start_time
                        logger.info("=" * 80)
                        logger.info("批量查询性能汇总")
                        logger.info("=" * 80)
                        logger.info(f"总耗时: {total_time:.3f}秒")
                        logger.info(f"查询股票数: {len(symbols)}")
                        logger.info(f"返回记录数: {len(df)}")
                        logger.info(f"有数据股票数: {len(result_dict)}")
                        logger.info(f"平均每只股票耗时: {total_time / len(symbols):.3f}秒")
                        logger.info(f"平均每条记录耗时: {total_time / len(df):.3f}秒")
                        logger.info("=" * 80)

                        logger.info(f"批量查询完成: {len(result_dict)}/{len(symbols)} 只股票有数据")
                        return result_dict
                    else:
                        logger.warning(f"批量查询结果为空，尝试使用基础表查询")
                        return await self._batch_query_from_base_table(
                            database_path, symbols, frequency, start_date, end_date, count
                        )

                except Exception as view_error:
                    error_msg = str(view_error)
                    
                    # 检测DuckDB受限模式（FATAL Error）
                    if "FATAL Error" in error_msg or "database has been invalidated" in error_msg:
                        logger.error("🚨 检测到DuckDB受限模式，尝试重启连接池...")
                        
                        # 重启连接池
                        try:
                            restart_success = self.duckdb_manager.restart_pool(database_path)
                            if restart_success:
                                logger.info("连接池重启成功，重试查询...")
                                # 重试查询
                                return await self.get_historical_data_batch(
                                    symbols=symbols,
                                    period=period,
                                    start_date=start_date,
                                    end_date=end_date,
                                    count=count,
                                    asset_type=asset_type
                                )
                            else:
                                logger.error("❌ 连接池重启失败，使用基础表查询")
                        except Exception as restart_error:
                            logger.error(f"重启连接池异常: {restart_error}")
                    
                    logger.error(f"批量查询异常: {view_error}")
                    import traceback
                    logger.error(f"详细错误:\n{traceback.format_exc()}")
                    return await self._batch_query_from_base_table(
                        database_path, symbols, frequency, start_date, end_date, count
                    )

        except Exception as e:
            logger.error(f"批量获取历史数据失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}

    async def _get_kdata_from_base_table(self, database_path: str, symbol: str, frequency: str,
                                       start_date: datetime = None, end_date: datetime = None,
                                       count: int = 365) -> pd.DataFrame:
        """从基础表查询单个股票的数据"""
        try:
            base_query = f"""
                SELECT 
                    symbol as code, 
                    timestamp as datetime, 
                    open, high, low, close, volume, amount,
                    data_source
                FROM historical_kline_data
                WHERE symbol = ? 
                  AND frequency = ?
                  AND (frequency <> '1d' OR CAST(timestamp AS TIME) = TIME '00:00:00')
            """

            query_params = [symbol, frequency]

            if start_date:
                base_query += " AND timestamp >= ?"
                query_params.append(start_date)

            if end_date:
                base_query += " AND timestamp <= ?"
                query_params.append(end_date)

            if not start_date and not end_date:
                base_query += " ORDER BY timestamp DESC LIMIT ?"
                query_params.append(count)
            else:
                base_query += " ORDER BY timestamp"

            result = self.duckdb_operations.execute_query(
                database_path=database_path,
                query=base_query,
                params=query_params
            )

            if result.success and result.data is not None:
                if isinstance(result.data, pd.DataFrame):
                    df = result.data
                else:
                    df = pd.DataFrame(result.data)

                if not df.empty:
                    df = self._standardize_kdata_format(df, symbol)
                    return df

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"从基础表查询失败 {symbol}: {e}")
            return pd.DataFrame()

    async def _batch_query_from_base_table(self, database_path: str, symbols: List[str], frequency: str,
                                         start_date: datetime = None, end_date: datetime = None,
                                         count: int = 365) -> Dict[str, pd.DataFrame]:
        """从基础表批量查询数据"""
        try:
            base_query = f"""
                SELECT 
                    code, 
                    datetime, 
                    open, high, low, close, volume, amount,
                    data_source
                FROM (
                    SELECT 
                        symbol as code, 
                        timestamp as datetime, 
                        open, high, low, close, volume, amount,
                        data_source,
                        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY timestamp DESC) as rn
                    FROM historical_kline_data
                    WHERE symbol IN ({','.join([f"'{s}'" for s in symbols])})
                      AND frequency = ?
                      AND (frequency <> '1d' OR CAST(timestamp AS TIME) = TIME '00:00:00')
            """

            query_params = [frequency]

            if start_date:
                base_query += " AND timestamp >= ?"
                query_params.append(start_date)

            if end_date:
                base_query += " AND timestamp <= ?"
                query_params.append(end_date)

            # 闭合子查询并添加过滤条件
            base_query += ") subq WHERE rn <= ?"
            query_params.append(count)

            # 按symbol和timestamp排序
            base_query += " ORDER BY code, datetime DESC"

            result = self.duckdb_operations.execute_query(
                database_path=database_path,
                query=base_query,
                params=query_params
            )

            if result.success and result.data is not None:
                if isinstance(result.data, pd.DataFrame):
                    df = result.data
                else:
                    df = pd.DataFrame(result.data)

                if not df.empty:
                    logger.info(f"基础表批量查询成功: 共 {len(df)} 条记录, {df['code'].nunique()} 只股票")

                    # 如果没有指定日期范围，按symbol分组并取前count条
                    if not start_date and not end_date:
                        df_list = []
                        for symbol in df['code'].unique():
                            symbol_df = df[df['code'] == symbol].head(count)
                            df_list.append(symbol_df)
                        df = pd.concat(df_list, ignore_index=True)

                    # 按symbol分组
                    result_dict = {}
                    for symbol in symbols:
                        symbol_df = df[df['code'] == symbol].copy()
                        if not symbol_df.empty:
                            symbol_df = self._standardize_kdata_format(symbol_df, symbol)
                            result_dict[symbol] = symbol_df
                        else:
                            result_dict[symbol] = pd.DataFrame()

                    return result_dict
                else:
                    logger.warning(f"基础表批量查询结果为空")
                    return {symbol: pd.DataFrame() for symbol in symbols}
            else:
                logger.warning(f"基础表批量查询失败: success={result.success}")
                return {symbol: pd.DataFrame() for symbol in symbols}

        except Exception as e:
            logger.error(f"基础表批量查询异常: {e}")
            return {symbol: pd.DataFrame() for symbol in symbols}

    async def _get_news(self, stock_code: str) -> Dict[str, Any]:
        """获取新闻数据

        Args:
            stock_code: 股票代码

        Returns:
            新闻数据字典
        """
        try:
            logger.info(f"获取新闻数据: {stock_code}")

            # 获取新闻数据可能需要特定的服务
            # 这里仅作为示例实现，返回空字典
            return {}

        except Exception as e:
            logger.error(f"获取新闻数据失败: {e}", exc_info=True)
            return {}

    async def create_database_indexes(self, asset_type: AssetType = AssetType.STOCK_A) -> Dict[str, Any]:
        """
        创建数据库索引（独立功能，避免在批量查询时创建）

        Args:
            asset_type: 资产类型

        Returns:
            创建结果字典
        """
        result = {
            'success': False,
            'message': '',
            'created_indexes': [],
            'failed_indexes': []
        }

        if not self.duckdb_available or not self.duckdb_manager:
            result['message'] = 'DuckDB不可用'
            return result

        try:
            database_path = self.asset_manager.get_database_path(asset_type)
            logger.info(f"开始为数据库创建索引: {database_path}")

            with self.duckdb_manager.get_connection(database_path) as conn:
                # 创建historical_kline_data表的索引
                logger.info("创建historical_kline_data表索引...")
                indexes_to_create = [
                    ("idx_historical_kline_data_symbol", "CREATE INDEX IF NOT EXISTS idx_historical_kline_data_symbol ON historical_kline_data(symbol)"),
                    ("idx_historical_kline_data_timestamp", "CREATE INDEX IF NOT EXISTS idx_historical_kline_data_timestamp ON historical_kline_data(timestamp)"),
                    ("idx_historical_kline_data_symbol_timestamp", "CREATE INDEX IF NOT EXISTS idx_historical_kline_data_symbol_timestamp ON historical_kline_data(symbol, timestamp)"),
                    ("idx_historical_kline_data_data_source", "CREATE INDEX IF NOT EXISTS idx_historical_kline_data_data_source ON historical_kline_data(data_source)"),
                    ("idx_historical_kline_data_conflict_key", "CREATE INDEX IF NOT EXISTS idx_historical_kline_data_conflict_key ON historical_kline_data(symbol, data_source, timestamp, frequency)"),
                    ("idx_historical_kline_data_symbol_frequency", "CREATE INDEX IF NOT EXISTS idx_historical_kline_data_symbol_frequency ON historical_kline_data(symbol, frequency)"),
                    ("idx_historical_kline_data_symbol_timestamp_frequency", "CREATE INDEX IF NOT EXISTS idx_historical_kline_data_symbol_timestamp_frequency ON historical_kline_data(symbol, timestamp, frequency)"),
                    ("idx_historical_kline_data_frequency_timestamp", "CREATE INDEX IF NOT EXISTS idx_historical_kline_data_frequency_timestamp ON historical_kline_data(frequency, timestamp)")
                ]

                for index_name, create_sql in indexes_to_create:
                    try:
                        conn.execute(create_sql)
                        result['created_indexes'].append(index_name)
                        logger.info(f"创建索引成功: {index_name}")
                    except Exception as e:
                        result['failed_indexes'].append({'index': index_name, 'error': str(e)})
                        logger.error(f"❌ 创建索引失败: {index_name}, 错误: {e}")

                # 创建data_quality_monitor表的索引
                logger.info("创建data_quality_monitor表索引...")
                quality_indexes_to_create = [
                    ("idx_data_quality_monitor_symbol_data_source_check_date_frequency", "CREATE INDEX IF NOT EXISTS idx_data_quality_monitor_symbol_data_source_check_date_frequency ON data_quality_monitor(symbol, data_source, check_date, frequency)"),
                    ("idx_data_quality_monitor_symbol_check_date_frequency", "CREATE INDEX IF NOT EXISTS idx_data_quality_monitor_symbol_check_date_frequency ON data_quality_monitor(symbol, check_date, frequency)"),
                    ("idx_data_quality_monitor_check_date_frequency", "CREATE INDEX IF NOT EXISTS idx_data_quality_monitor_check_date_frequency ON data_quality_monitor(check_date, frequency)"),
                    ("idx_data_quality_monitor_symbol_data_source_check_date", "CREATE INDEX IF NOT EXISTS idx_data_quality_monitor_symbol_data_source_check_date ON data_quality_monitor(symbol, data_source, check_date)"),
                    ("idx_data_quality_monitor_symbol_check_date", "CREATE INDEX IF NOT EXISTS idx_data_quality_monitor_symbol_check_date ON data_quality_monitor(symbol, check_date)"),
                    ("idx_data_quality_monitor_check_date", "CREATE INDEX IF NOT EXISTS idx_data_quality_monitor_check_date ON data_quality_monitor(check_date)")
                ]

                for index_name, create_sql in quality_indexes_to_create:
                    try:
                        conn.execute(create_sql)
                        result['created_indexes'].append(index_name)
                        logger.info(f"创建索引成功: {index_name}")
                    except Exception as e:
                        result['failed_indexes'].append({'index': index_name, 'error': str(e)})
                        logger.error(f"❌ 创建索引失败: {index_name}, 错误: {e}")

                result['success'] = True
                result['message'] = f"成功创建 {len(result['created_indexes'])} 个索引，失败 {len(result['failed_indexes'])} 个"

                logger.info("=" * 80)
                logger.info("索引创建完成")
                logger.info(f"成功: {len(result['created_indexes'])} 个")
                logger.info(f"失败: {len(result['failed_indexes'])} 个")
                logger.info("=" * 80)

        except Exception as e:
            result['message'] = f"创建索引失败: {str(e)}"
            logger.error(f"创建数据库索引失败: {e}", exc_info=True)

        return result

    def cancel_request(self, request_id: str) -> bool:
        """
        取消请求

        Args:
            request_id: 请求ID

        Returns:
            是否成功取消
        """
        # 路径A防死锁(R238-P0-2): _cleanup_resources 内部会再次获取 request_tracker_lock,
        # 若在锁内调用将同线程重入普通 Lock → 死锁. 故仅锁内取消任务, 清理移到锁块外.
        found_in_tracker = False
        with self.request_tracker_lock:
            if request_id in self.request_tracker:
                task = self.request_tracker[request_id].get('task')
                if task and not task.done():
                    task.cancel()
                    logger.info(f"Request {request_id} cancelled")

                # 更新统计信息
                self._stats['requests_cancelled'] += 1
                found_in_tracker = True

        if found_in_tracker:
            # 锁外清理资源 (避免重入 request_tracker_lock 死锁)
            self._cleanup_resources(request_id)
            return True

        with self._request_lock:
            # 检查待处理请求
            if request_id in self._pending_requests:
                request = self._pending_requests[request_id]
                request.status = DataRequestStatus.CANCELLED
                del self._pending_requests[request_id]
                logger.debug(f"Cancelled pending request {request_id}")
                return True

            # 检查活动请求
            if request_id in self._active_requests:
                request = self._active_requests[request_id]
                if request.future and not request.future.done():
                    request.future.cancel()
                request.status = DataRequestStatus.CANCELLED
                del self._active_requests[request_id]
                logger.debug(f"Cancelled active request {request_id}")
                return True

        return False

    def _register_request(self, request_id: str):
        """注册请求到跟踪器"""
        with self.request_tracker_lock:
            try:
                task = asyncio.current_task() if asyncio.iscoroutinefunction(
                    self.get_stock_data) else None
            except RuntimeError:
                # 没有运行的事件循环
                task = None
            self.request_tracker[request_id] = {
                'timestamp': time.time(),
                'task': task
            }

    def _unregister_request(self, request_id: str):
        """从跟踪器中注销请求"""
        with self.request_tracker_lock:
            if request_id in self.request_tracker:
                del self.request_tracker[request_id]

    def _cleanup_resources(self, request_id: str):
        """清理请求相关资源"""
        # 从各种集合中移除请求
        with self._request_lock:
            if request_id in self._pending_requests:
                del self._pending_requests[request_id]

            if request_id in self._active_requests:
                del self._active_requests[request_id]

            if request_id in self._completed_requests:
                del self._completed_requests[request_id]

        # 从去重机制中移除
        with self._dedup_lock:
            for key, requests in list(self._request_dedup.items()):
                if request_id in requests:
                    requests.remove(request_id)
                    if not requests:
                        del self._request_dedup[key]
                    break

        # 从跟踪器中移除
        self._unregister_request(request_id)

        logger.debug(f"Resources cleaned up for request {request_id}")

    def preload_data(self, code: str, freq: str = 'D', priority: str = 'low'):
        """预加载数据"""
        # 转换优先级字符串到数值
        priority_map = {'high': 0, 'normal': 1, 'low': 2}
        priority_value = priority_map.get(priority.lower(), 2)

        # 使用低优先级请求预加载数据
        self.request_data(
            stock_code=code,
            data_type='kdata',
            period=freq,
            priority=priority_value,
            callback=None  # 无需回调
        )

        logger.debug(f"Preloading data for {code} with priority {priority}")

        return True

    def get_request_status(self, request_id: str) -> Optional[DataRequestStatus]:
        """
        获取请求状态

        Args:
            request_id: 请求ID

        Returns:
            请求状态
        """
        with self._request_lock:
            if request_id in self._pending_requests:
                return self._pending_requests[request_id].status
            elif request_id in self._active_requests:
                return self._active_requests[request_id].status
            elif request_id in self._completed_requests:
                return self._completed_requests[request_id].status

        return None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._request_lock:
            return {
                **self._stats,
                'pending_requests': len(self._pending_requests),
                'active_requests': len(self._active_requests),
                'completed_requests': len(self._completed_requests),
                'cache_size': self.multi_cache.get_statistics()['total_items'] if self.multi_cache else 0
            }

    def clear_cache(self, stock_code: str = None, data_type: str = None) -> None:
        """
        清理缓存

        Args:
            stock_code: 股票代码（可选，清理特定股票的缓存）
            data_type: 数据类型（可选，清理特定类型的缓存）
        """
        with self._cache_lock:
            if stock_code is None and data_type is None:
                # 清理所有缓存
                self._data_cache.clear()
                self._cache_timestamps.clear()
                logger.info("All cache cleared")
            else:
                # 清理特定缓存
                keys_to_remove = []
                for key in self._data_cache.keys():
                    if stock_code and stock_code not in key:
                        continue
                    if data_type and data_type not in key:
                        continue
                    keys_to_remove.append(key)

                for key in keys_to_remove:
                    del self._data_cache[key]
                    if key in self._cache_timestamps:
                        del self._cache_timestamps[key]

                logger.info(f"Cleared {len(keys_to_remove)} cache entries")

    def _submit_request(self, request: DataRequest) -> None:
        """提交请求到线程池"""
        with self._request_lock:
            self._pending_requests[request.request_id] = request

        # 提交到线程池
        future = self._executor.submit(self._process_request, request)
        request.future = future

        logger.debug(
            f"Submitted request {request.request_id} for {request.stock_code}")

    def _process_request(self, request: DataRequest) -> None:
        """
        处理数据请求
        """
        try:
            data = None
            if request.data_type == 'kdata':
                kline_data = self._load_kdata(request)
                # 修改：将K线数据包装在字典中，保持数据结构一致性
                data = {
                    'kline_data': kline_data,
                    'stock_code': request.stock_code,
                    'period': request.period
                }
            elif request.data_type == 'indicators':
                data = self._load_indicators(request)
            elif request.data_type == 'analysis':
                data = self._load_analysis(request)
            elif request.data_type == 'chart':
                kline_data = self._load_kdata(request)
                indicators_data = self._load_indicators(request)
                data = {
                    'kline_data': kline_data,
                    'indicators_data': indicators_data
                }
            else:
                raise ValueError(f"Unsupported data type: {request.data_type}")

            self._complete_request(request, data)

        except Exception as e:
            logger.error(
                f"Failed to process request {request.request_id}: {e}")
            self._complete_request(request, None, str(e))

    def _complete_request(self, request: DataRequest, data: Any, error: str = None) -> None:
        """
        完成请求并通过Future返回结果
        """
        request_key = self._get_request_key(
            request.stock_code, request.data_type, request.period, request.time_range, request.parameters)

        with self._dedup_lock:
            request_group = self._request_dedup.pop(request_key, set())

        for req in request_group:
            if req.future and not req.future.done():
                if error:
                    exception = Exception(error)
                    self.loop.call_soon_threadsafe(
                        req.future.set_exception, exception)
                else:
                    self.loop.call_soon_threadsafe(req.future.set_result, data)

            with self._request_lock:
                self._completed_requests[req.request_id] = req
                req.status = DataRequestStatus.COMPLETED if not error else DataRequestStatus.FAILED

        if not error:
            self._stats['requests_completed'] += len(request_group)
        else:
            self._stats['requests_failed'] += len(request_group)

    def _load_kdata(self, request: DataRequest) -> pd.DataFrame:
        """加载K线数据"""
        try:
            from .stock_service import StockService
            stock_service = self.service_container.resolve(StockService)
            return stock_service.get_stock_data(
                request.stock_code, request.period, request.time_range, asset_type=request.asset_type
            )
        except Exception as e:
            logger.error(f"Failed to load kdata: {e}")
            raise

    def _load_indicators(self, request: DataRequest) -> Dict[str, Any]:
        """加载技术指标数据"""
        try:
            from .analysis_service import AnalysisService
            analysis_service = self.service_container.resolve(AnalysisService)

            indicators = request.parameters.get('indicators', ['MA', 'MACD'])
            return analysis_service.calculate_technical_indicators(
                request.stock_code, indicators, request.period, request.time_range
            )
        except Exception as e:
            logger.error(f"Failed to load indicators: {e}")
            raise

    def _load_analysis(self, request: DataRequest) -> Dict[str, Any]:
        """加载分析数据"""
        try:
            from .analysis_service import AnalysisService
            analysis_service = self.service_container.resolve(AnalysisService)

            analysis_type = request.parameters.get(
                'analysis_type', 'comprehensive')
            return analysis_service.analyze_stock(request.stock_code, analysis_type)
        except Exception as e:
            logger.error(f"Failed to load analysis: {e}")
            raise

    def _get_cache_key(self, stock_code: str, data_type: str, period: str,
                       time_range: int, parameters: Dict[str, Any]) -> str:
        """生成缓存键"""
        param_hash = hash(str(sorted(parameters.items()))
                          if parameters else "")
        return f"{data_type}_{stock_code}_{period}_{time_range}_{param_hash}"

    def _get_request_key(self, stock_code: str, data_type: str, period: str,
                         time_range: int, parameters: Dict[str, Any]) -> str:
        """生成请求键"""
        return self._get_cache_key(stock_code, data_type, period, time_range, parameters)

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """从缓存获取数据 - 使用统一的MultiLevelCacheManager"""
        with self._cache_lock:
            # if cache_key in self._data_cache:  # 已统一使用MultiLevelCacheManager
            if self.multi_cache and self.multi_cache.get(cache_key) is not None:
                timestamp = self._cache_timestamps.get(cache_key, 0)
                if time.time() - timestamp < self._cache_ttl:
                    return self.multi_cache.get(cache_key)
                else:
                    # 缓存过期，清理
                    del self._data_cache[cache_key]
                    if cache_key in self._cache_timestamps:
                        del self._cache_timestamps[cache_key]

        return None

    def _put_to_cache(self, cache_key: str, data: Any) -> None:
        """将数据放入缓存 - 使用统一的MultiLevelCacheManager"""
        with self._cache_lock:
            # self._data_cache[cache_key] = data  # 已统一使用MultiLevelCacheManager
            if self.multi_cache:
                self.multi_cache.set(cache_key, data, ttl=self._cache_ttl)

    def dispose(self) -> None:
        """清理资源"""
        logger.info("Disposing unified data manager")

        # 路径B防死锁(R238-P0-2): cancel_request 内部会获取 _request_lock,
        # 若在此锁内调用将同线程重入普通 Lock → 死锁. 故仅锁内收集 request_id, 锁外逐个取消.
        request_ids_to_cancel = []
        with self._request_lock:
            request_ids_to_cancel.extend(
                request.request_id for request in self._pending_requests.values())
            request_ids_to_cancel.extend(
                request.request_id for request in self._active_requests.values())

        for request_id in request_ids_to_cancel:
            self.cancel_request(request_id)

        # 关闭线程池
        self._executor.shutdown(wait=True)

        # 清理缓存
        self.clear_cache()

        logger.info("Unified data manager disposed")

    def _auto_discover_data_source_plugins(self) -> None:
        """自动发现和注册数据源插件"""
        try:
            # 从服务容器获取插件管理器
            plugin_manager = None
            if self.service_container:
                try:
                    from ..plugin_manager import PluginManager
                    plugin_manager = self.service_container.resolve(PluginManager)
                except Exception:
                    logger.warning("无法获取插件管理器，跳过插件自动发现")
                    return

            if not plugin_manager:
                logger.warning("插件管理器不可用，跳过插件自动发现")
                return

            # 获取所有已加载的插件
            all_plugins = plugin_manager.get_all_plugins()
            registered_count = 0

            for plugin_name, plugin_instance in all_plugins.items():
                try:
                    # 检查是否是数据源插件
                    if self._is_data_source_plugin(plugin_instance):
                        # 注册到TET数据管道
                        success = self.register_data_source_plugin(
                            plugin_name,
                            plugin_instance,
                            priority=getattr(plugin_instance, 'priority', 50),
                            weight=getattr(plugin_instance, 'weight', 1.0)
                        )

                        if success:
                            registered_count += 1
                            logger.info(f" 自动注册数据源插件: {plugin_name}")
                        else:
                            logger.warning(f" 数据源插件注册失败: {plugin_name}")

                except Exception as e:
                    logger.warning(f" 检查插件失败 {plugin_name}: {e}")

            if registered_count > 0:
                logger.info(f" 自动发现并注册了 {registered_count} 个数据源插件")
                self._plugins_discovered = True
            else:
                logger.info("未发现新的数据源插件")

        except Exception as e:
            logger.error(f" 自动发现数据源插件失败: {e}")

    def _is_data_source_plugin(self, plugin_instance) -> bool:
        """检查插件是否是数据源插件"""
        try:
            from ..data_source_extensions import IDataSourcePlugin
            return isinstance(plugin_instance, IDataSourcePlugin)
        except Exception:
            # 检查是否有必要的方法
            required_methods = ['get_asset_list', 'get_kdata', 'health_check']
            return all(hasattr(plugin_instance, method) for method in required_methods)

    def discover_and_register_data_source_plugins(self) -> None:
        """
        发现并注册数据源插件（公共方法）
        在所有服务初始化完成后调用
        """
        if self._plugins_discovered:
            logger.info("插件已发现，跳过重复发现")
            return

        logger.info("🔍 开始发现和注册数据源插件...")

        try:
            # 使用插件管理器动态加载插件（替代硬编码）
            registered_count = self._register_plugins_from_plugin_manager()

            if registered_count > 0:
                self._plugins_discovered = True
                logger.info(f"插件发现和注册完成: 共注册 {registered_count} 个插件")
            else:
                logger.warning("⚠️ 未注册任何插件，请检查插件管理器状态")

        except Exception as e:
            logger.error(f"❌ 插件发现和注册失败: {e}")
            logger.error(traceback.format_exc())

    def _register_plugins_from_plugin_manager(self) -> int:
        """
        从插件管理器动态注册数据源插件

        Returns:
            成功注册的插件数量
        """
        # 获取插件管理器
        plugin_manager = None

        # 方法1: 从service_container获取
        if hasattr(self, 'service_container') and self.service_container:
            try:
                from core.plugin_manager import PluginManager
                if self.service_container.is_registered(PluginManager):
                    plugin_manager = self.service_container.resolve(PluginManager)
                    logger.debug("从服务容器获取PluginManager成功")
            except Exception as e:
                logger.debug(f"从服务容器获取PluginManager失败: {e}")

        # 方法2: 从全局实例获取
        if not plugin_manager:
            try:
                from core.plugin_manager import PluginManager
                # 通过ServiceContainer获取PluginManager实例
                from core.containers import get_service_container
                container = get_service_container()
                plugin_manager = container.resolve(PluginManager) if container else None
            except Exception as e:
                logger.debug(f"无法通过ServiceContainer获取PluginManager: {e}")

        if not plugin_manager:
            logger.warning("⚠️ 插件管理器未初始化，无法注册插件")
            return 0

        registered_count = 0

        try:
            from core.plugin_types import PluginType

            # 1. 获取所有插件实例
            all_plugins = plugin_manager.plugin_instances

            if not all_plugins:
                logger.warning("⚠️ 插件管理器中没有加载任何插件")
                return 0

            logger.info(f"📦 插件管理器中有 {len(all_plugins)} 个插件")

            # 2. 筛选数据源插件
            data_source_plugins = []
            for plugin_id, plugin_instance in all_plugins.items():
                # 获取插件元数据
                metadata = plugin_manager.plugin_metadata.get(plugin_id, {})
                plugin_type = metadata.get('plugin_type') or metadata.get('type')

                # 检查是否为数据源插件
                is_data_source = False
                if plugin_type:
                    if isinstance(plugin_type, str):
                        is_data_source = 'data_source' in plugin_type.lower()
                    elif hasattr(plugin_type, 'value'):
                        is_data_source = 'data_source' in str(plugin_type.value).lower()
                    else:
                        is_data_source = 'data_source' in str(plugin_type).lower()

                # 也检查plugin_id前缀
                if not is_data_source:
                    is_data_source = plugin_id.startswith('data_sources.')

                if is_data_source:
                    data_source_plugins.append((plugin_id, plugin_instance, metadata))

            logger.info(f"🔍 发现 {len(data_source_plugins)} 个数据源插件")

            # 3. 注册每个数据源插件
            for plugin_id, plugin_instance, metadata in data_source_plugins:
                try:
                    # 检查插件是否启用
                    is_enabled = metadata.get('enabled', True)
                    if not is_enabled:
                        logger.debug(f"⏭️ 跳过禁用的插件: {plugin_id}")
                        continue

                    # 验证插件有必要的方法
                    if not self._is_data_source_plugin(plugin_instance):
                        logger.warning(f"⚠️ 插件缺少必要方法，跳过: {plugin_id}")
                        continue

                    # 获取优先级和权重
                    priority = 0
                    weight = 1.0

                    if hasattr(plugin_instance, 'priority'):
                        priority = plugin_instance.priority
                    elif 'priority' in metadata:
                        priority = metadata['priority']

                    if hasattr(plugin_instance, 'weight'):
                        weight = plugin_instance.weight
                    elif 'weight' in metadata:
                        weight = metadata['weight']

                    # 注册插件
                    success = self.register_data_source_plugin(
                        plugin_id=plugin_id,
                        adapter=plugin_instance,
                        priority=priority,
                        weight=weight
                    )

                    if success:
                        registered_count += 1
                        plugin_name = metadata.get('name', plugin_id)
                        logger.info(f"  成功注册: {plugin_name} ({plugin_id})")
                    else:
                        logger.warning(f"  ⚠️ 注册失败: {plugin_id}")

                except Exception as e:
                    logger.error(f"  ❌ 注册插件异常 {plugin_id}: {e}")
                    continue

            logger.info(f"插件注册统计: 成功 {registered_count}/{len(data_source_plugins)}")
            return registered_count

        except Exception as e:
            logger.error(f"❌ 从插件管理器注册插件失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return registered_count

    def _extend_akshare_plugin_for_sector_flow(self, akshare_plugin) -> None:
        """扩展AkShare插件以支持SECTOR_FUND_FLOW数据类型"""
        try:
            # 添加SECTOR_FUND_FLOW到支持的数据类型
            if hasattr(akshare_plugin, 'plugin_info'):
                plugin_info = akshare_plugin.plugin_info
                if hasattr(plugin_info, 'supported_data_types'):
                    from ..plugin_types import DataType
                    if DataType.SECTOR_FUND_FLOW not in plugin_info.supported_data_types:
                        plugin_info.supported_data_types.append(DataType.SECTOR_FUND_FLOW)
                        logger.info("AkShare插件已扩展支持SECTOR_FUND_FLOW")

            # 添加获取板块资金流的方法
            def get_sector_fund_flow_data(symbol: str, **kwargs):
                try:
                    import akshare as ak
                    # 根据symbol类型选择合适的akshare函数
                    if symbol == "sector":
                        return ak.stock_sector_fund_flow_rank(indicator="今日")
                    else:
                        return ak.stock_sector_fund_flow_summary(symbol=symbol, indicator="今日")
                except Exception as e:
                    logger.error(f"获取板块资金流数据失败: {e}")
                    return None

            # 动态添加方法到插件实例
            akshare_plugin.get_sector_fund_flow_data = get_sector_fund_flow_data
            logger.info("AkShare插件已添加板块资金流数据获取方法")

        except Exception as e:
            logger.error(f"扩展AkShare插件失败: {e}")

    @property
    def data_source_router(self):
        """
        兼容性属性：提供对数据源路由器的访问

        Returns:
            数据源路由器实例，如果TET管道可用的话
        """
        if hasattr(self, 'tet_pipeline') and self.tet_pipeline:
            return self.tet_pipeline.router
        return None

    def set_asset_routing_priorities(self, asset_type: AssetType, priorities: List[str]) -> bool:
        """
        设置资产类型的数据源路由优先级

        Args:
            asset_type: 资产类型
            priorities: 数据源优先级列表

        Returns:
            bool: 设置是否成功
        """
        try:
            router = self.data_source_router
            if router is None:
                logger.error("数据源路由器不可用，无法设置优先级")
                return False

            # 调用路由器的set_asset_priorities方法
            router.set_asset_priorities(asset_type, priorities)
            logger.info(f" 成功设置{asset_type.value}的路由优先级: {priorities}")
            return True

        except Exception as e:
            logger.error(f" 设置资产路由优先级失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_asset_routing_priorities(self, asset_type: AssetType) -> List[str]:
        """
        获取资产类型的数据源路由优先级

        Args:
            asset_type: 资产类型

        Returns:
            List[str]: 数据源优先级列表
        """
        try:
            router = self.data_source_router
            if router is None:
                logger.warning("数据源路由器不可用，返回空优先级列表")
                return []

            return router.asset_priorities.get(asset_type, [])

        except Exception as e:
            logger.error(f" 获取资产路由优先级失败: {e}")
            return []

    def get_data_source_priorities(self) -> Dict[str, List[str]]:
        """
        获取数据源优先级配置（PluginManager.switch_data_source 数据源切换使用）

        R275 修复：该方法此前不存在，导致 plugin_manager.py L1220-1231 的
        switch_data_source hasattr 判断为 False → 切换静默跳过、TET 路由优先级永不变。
        返回值以 TET 路由器实际生效的 asset_priorities 为准，保证短名/完整 plugin_id 一致。
        """
        try:
            router = self.data_source_router
            if router is not None and getattr(router, 'asset_priorities', None):
                merged = dict(self._data_source_priorities)
                for at, priorities in router.asset_priorities.items():
                    merged[at.value if hasattr(at, 'value') else str(at)] = list(priorities)
                return merged
        except Exception as e:
            logger.error(f"获取数据源优先级失败: {e}")
        return dict(self._data_source_priorities)

    def set_data_source_priority(self, asset_type: Union[str, AssetType], priorities: List[str]) -> bool:
        """
        设置数据源优先级，并同步到 TET 路由器（使切换真实影响 failover 路由顺序）

        R275 修复：PluginManager.switch_data_source 调用的该方法此前缺失，
        现已补齐并将优先级写入 DataSourceRouter.asset_priorities（_get_available_sources
        优先使用配置的优先级列表），数据源切换不再是"假实现"。
        """
        try:
            asset_key = asset_type.value if hasattr(asset_type, 'value') else str(asset_type)
            self._data_source_priorities[asset_key] = list(priorities)

            try:
                from ..plugin_types import AssetType as _AssetType
                asset_enum = asset_type if isinstance(asset_type, _AssetType) else _AssetType(asset_key)
                router = self.data_source_router
                if router is not None:
                    router.set_asset_priorities(asset_enum, list(priorities))
            except Exception as e:
                logger.warning(f"同步数据源优先级到TET路由器失败: {e}")

            logger.info(f"数据源优先级已更新: {asset_key} -> {list(priorities)}")
            return True
        except Exception as e:
            logger.error(f"设置数据源优先级失败: {e}")
            return False

    def _initialize_sector_service(self):
        """
        初始化板块数据服务
        """
        try:
            # 延迟导入避免循环依赖
            from .sector_data_service import SectorDataService, get_sector_data_service

            # 优先从服务容器解析（服务注册铁律，R253 P1 修复）
            container = getattr(self, 'service_container', None)
            if container is not None and container.is_registered(SectorDataService):
                self._sector_data_service = container.resolve(SectorDataService)
                logger.info("板块数据服务从服务容器解析成功")
            else:
                # 容器不可用时回退到模块级单例工厂
                cache_manager = getattr(self, 'cache_manager', None)
                self._sector_data_service = get_sector_data_service(
                    cache_manager=cache_manager,
                    tet_pipeline=self.tet_pipeline
                )
                logger.info("板块数据服务通过模块级工厂初始化成功")

            logger.info("板块数据服务初始化成功")

        except Exception as e:
            logger.error(f"板块数据服务初始化失败: {e}")
            self._sector_data_service = None

    def get_sector_fund_flow_service(self):
        """
        获取板块资金流服务实例

        Returns:
            SectorDataService: 板块数据服务实例，如果初始化失败则返回None
        """
        return self._sector_data_service

    def get_sector_fund_flow_ranking(self, date_range: str = "today", sort_by: str = 'main_net_inflow'):
        """
        获取板块资金流排行榜（统一数据管理器入口）

        Args:
            date_range: 时间范围，如 "today", "3d", "5d", "1m"
            sort_by: 排序字段，默认按主力净流入排序

        Returns:
            pd.DataFrame: 板块排行榜数据
        """
        try:
            if self._sector_data_service is None:
                logger.warning("板块数据服务不可用")
                return pd.DataFrame()

            return self._sector_data_service.get_sector_fund_flow_ranking(date_range, sort_by)

        except Exception as e:
            logger.error(f"获取板块资金流排行榜失败: {e}")
            return pd.DataFrame()

    def get_sector_historical_trend(self, sector_id: str, period: int = 30):
        """
        获取单板块历史趋势数据（统一数据管理器入口）

        Args:
            sector_id: 板块ID，如 "BK0001"
            period: 查询天数，默认30天

        Returns:
            pd.DataFrame: 板块历史趋势数据
        """
        try:
            if self._sector_data_service is None:
                logger.warning("板块数据服务不可用")
                return pd.DataFrame()

            return self._sector_data_service.get_sector_historical_trend(sector_id, period)

        except Exception as e:
            logger.error(f"获取板块历史趋势失败: {e}")
            return pd.DataFrame()

    def get_sector_intraday_flow(self, sector_id: str, date: str):
        """
        获取板块分时资金流数据（统一数据管理器入口）

        Args:
            sector_id: 板块ID，如 "BK0001"
            date: 查询日期，格式 "YYYY-MM-DD"

        Returns:
            pd.DataFrame: 板块分时资金流数据
        """
        try:
            if self._sector_data_service is None:
                logger.warning("板块数据服务不可用")
                return pd.DataFrame()

            return self._sector_data_service.get_sector_intraday_flow(sector_id, date)

        except Exception as e:
            logger.error(f"获取板块分时资金流失败: {e}")
            return pd.DataFrame()

    def import_sector_historical_data(self, source: str, start_date: str, end_date: str):
        """
        导入板块历史数据（统一数据管理器入口）

        Args:
            source: 数据源名称，如 "akshare", "eastmoney"
            start_date: 开始日期，格式 "YYYY-MM-DD"
            end_date: 结束日期，格式 "YYYY-MM-DD"

        Returns:
            Dict[str, Any]: 导入结果统计信息
        """
        try:
            if self._sector_data_service is None:
                logger.warning("板块数据服务不可用")
                return {"success": False, "error": "板块数据服务不可用"}

            return self._sector_data_service.import_sector_historical_data(source, start_date, end_date)

        except Exception as e:
            logger.error(f"导入板块历史数据失败: {e}")
            return {"success": False, "error": str(e)}

    def add_stock(self, stock_data: Dict[str, Any]) -> bool:
        """添加股票信息"""
        try:
            if not stock_data or 'code' not in stock_data:
                logger.error("股票数据无效，必须包含 'code' 字段")
                return False

            stock_code = stock_data['code']
            cache_key = f"stock_{stock_code}"

            if self.duckdb_available and self.duckdb_operations:
                success = self.duckdb_operations.insert_stock_info(stock_data)
                if success:
                    logger.info(f"股票信息已添加到DuckDB: {stock_code}")
                    self._cache_data(cache_key, stock_data)
                    return True
                else:
                    logger.warning(f"DuckDB添加失败，尝试SQLite: {stock_code}")

            if self.db_access and self._db_lock:
                with self._db_lock:
                    with self.db_access.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO stocks (code, name, market, industry, list_date, delist_date, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(code) DO UPDATE SET
                                name = excluded.name,
                                market = excluded.market,
                                industry = excluded.industry,
                                list_date = excluded.list_date,
                                delist_date = excluded.delist_date,
                                status = excluded.status
                        ''', (
                            stock_data.get('code'),
                            stock_data.get('name'),
                            stock_data.get('market'),
                            stock_data.get('industry'),
                            stock_data.get('list_date'),
                            stock_data.get('delist_date'),
                            stock_data.get('status', 'active')
                        ))

                logger.info(f"股票信息已添加到SQLite: {stock_code}")
                self._cache_data(cache_key, stock_data)
                return True

            logger.error("数据库不可用，无法添加股票信息")
            return False

        except Exception as e:
            logger.error(f"添加股票信息失败: {e}")
            return False

    def update_stock(self, stock_code: str, data: Dict[str, Any]) -> bool:
        """更新股票信息"""
        try:
            if not stock_code:
                logger.error("股票代码不能为空")
                return False

            cache_key = f"stock_{stock_code}"

            if self.duckdb_available and self.duckdb_operations:
                success = self.duckdb_operations.update_stock_info(stock_code, data)
                if success:
                    logger.info(f"股票信息已在DuckDB更新: {stock_code}")
                    cached_data = self._get_cached_data(cache_key)
                    if cached_data:
                        cached_data.update(data)
                        self._cache_data(cache_key, cached_data)
                    return True

            if self.db_access and self._db_lock:
                with self._db_lock:
                    with self.db_access.get_connection() as conn:
                        cursor = conn.cursor()
                        # SQL注入防护：验证列名白名单
                        validated_keys = self._validate_columns(list(data.keys()), self._ALLOWED_STOCK_COLUMNS)
                        if not validated_keys:
                            logger.error(f"股票数据列名验证失败，无有效列: {list(data.keys())}")
                            return False
                        set_clause = ', '.join([f"{key} = ?" for key in validated_keys])
                        sql = f"UPDATE stocks SET {set_clause} WHERE code = ?"
                        params = [data[key] for key in validated_keys] + [stock_code]
                        cursor.execute(sql, params)

                        if cursor.rowcount > 0:
                            logger.info(f"股票信息已在SQLite更新: {stock_code}")
                            cached_data = self._get_cached_data(cache_key)
                            if cached_data:
                                cached_data.update(data)
                                self._cache_data(cache_key, cached_data)
                            return True

            logger.error("数据库不可用，无法更新股票信息")
            return False

        except Exception as e:
            logger.error(f"更新股票信息失败: {e}")
            return False

    def delete_stock(self, stock_code: str) -> bool:
        """删除股票信息"""
        try:
            if not stock_code:
                logger.error("股票代码不能为空")
                return False

            cache_key = f"stock_{stock_code}"
            deleted = False

            if self.duckdb_available and self.duckdb_operations:
                success = self.duckdb_operations.delete_stock_info(stock_code)
                if success:
                    logger.info(f"股票信息已从DuckDB删除: {stock_code}")
                    deleted = True

            if self.db_access and self._db_lock:
                with self._db_lock:
                    with self.db_access.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM stocks WHERE code = ?", (stock_code,))

                        if cursor.rowcount > 0:
                            logger.info(f"股票信息已从SQLite删除: {stock_code}")
                            deleted = True

            if deleted:
                self._invalidate_cache(cache_key)
                return True

            logger.warning(f"股票未找到: {stock_code}")
            return False

        except Exception as e:
            logger.error(f"删除股票信息失败: {e}")
            return False

    def add_kline(self, stock_code: str, period: str, data: pd.DataFrame) -> bool:
        try:
            if not stock_code or data.empty:
                logger.error("股票代码或K线数据无效")
                return False

            cache_key = f"kdata_{stock_code}_{period}"
            total_input = len(data)

            if self.duckdb_available and self.duckdb_operations:
                # R251 修复: insert_kline_data 已补齐, 传入资产库路径使写入/读取库一致
                asset_type = self.asset_identifier.identify_asset_type(stock_code)
                db_path = self.asset_manager.get_database_path(asset_type)
                result = self.duckdb_operations.insert_kline_data(
                    stock_code, period, data, database_path=db_path
                )
                success = result.success if hasattr(result, 'success') else bool(result)
                if success:
                    logger.info(f"K线数据已添加到DuckDB: {stock_code} ({period}), {total_input} 条")
                    self._cache_data(cache_key, data)
                    return True

            if self.db_access and self._db_lock:
                with self._db_lock:
                    with self.db_access.get_connection() as conn:
                        cursor = conn.cursor()

                        cursor.execute(
                            "SELECT COUNT(*) FROM kline WHERE stock_code = ? AND period = ?",
                            (stock_code, period)
                        )
                        before_count = cursor.fetchone()[0]

                        inserted = 0
                        records = [
                            (stock_code, period, row.trade_date, row.open, row.high,
                             row.low, row.close, row.volume, row.amount)
                            for row in data.itertuples(index=False)
                        ]
                        cursor.executemany('''
                            INSERT INTO kline (stock_code, period, trade_date, open, high, low, close, volume, amount)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(stock_code, period, trade_date) DO UPDATE SET
                                open = excluded.open,
                                high = excluded.high,
                                low = excluded.low,
                                close = excluded.close,
                                volume = excluded.volume,
                                amount = excluded.amount
                        ''', records)
                        inserted = len(records)

                        cursor.execute(
                            "SELECT COUNT(*) FROM kline WHERE stock_code = ? AND period = ?",
                            (stock_code, period)
                        )
                        after_count = cursor.fetchone()[0]
                        new_records = after_count - before_count
                        duplicates = total_input - new_records

                if duplicates > 0:
                    logger.info(
                        f"K线数据已添加到SQLite: {stock_code} ({period}), "
                        f"总: {total_input} 条, 新增: {new_records} 条, 重复(跳过): {duplicates} 条"
                    )
                else:
                    logger.info(f"K线数据已添加到SQLite: {stock_code} ({period}), {total_input} 条")
                self._cache_data(cache_key, data)
                return True

            logger.error("数据库不可用，无法添加K线数据")
            return False

        except Exception as e:
            logger.error(f"添加K线数据失败: {e}")
            return False

    def update_kline(self, stock_code: str, period: str, data: pd.DataFrame) -> bool:
        """更新K线数据"""
        try:
            if not stock_code or data.empty:
                logger.error("股票代码或K线数据无效")
                return False

            if self.delete_kline(stock_code, period):
                return self.add_kline(stock_code, period, data)

            logger.error("删除旧数据失败，无法更新K线数据")
            return False

        except Exception as e:
            logger.error(f"更新K线数据失败: {e}")
            return False

    def delete_kline(self, stock_code: str, period: str = None, start_date: str = None, end_date: str = None) -> bool:
        """删除K线数据"""
        try:
            if not stock_code:
                logger.error("股票代码不能为空")
                return False

            cache_pattern = f"kdata_{stock_code}_{period}" if period else f"kdata_{stock_code}"
            deleted = False

            if self.duckdb_available and self.duckdb_operations:
                # R251 修复: delete_kline_data 已补齐(签名 stock_code/period/database_path),
                # start_date/end_date 仅作用于 SQLite 分支
                asset_type = self.asset_identifier.identify_asset_type(stock_code)
                db_path = self.asset_manager.get_database_path(asset_type)
                success = self.duckdb_operations.delete_kline_data(
                    stock_code, period, database_path=db_path
                )
                if success:
                    logger.info(f"K线数据已从DuckDB删除: {stock_code}")
                    deleted = True

            if self.db_access and self._db_lock:
                with self._db_lock:
                    with self.db_access.get_connection() as conn:
                        cursor = conn.cursor()
                        sql = "DELETE FROM kline WHERE stock_code = ?"
                        params = [stock_code]

                        if period:
                            sql += " AND period = ?"
                            params.append(period)
                        if start_date:
                            sql += " AND trade_date >= ?"
                            params.append(start_date)
                        if end_date:
                            sql += " AND trade_date <= ?"
                            params.append(end_date)

                        cursor.execute(sql, params)

                        if cursor.rowcount > 0:
                            logger.info(f"K线数据已从SQLite删除: {stock_code}")
                            deleted = True

            if deleted:
                self._invalidate_cache(cache_pattern)
                return True

            logger.warning(f"K线数据未找到: {stock_code}")
            return False

        except Exception as e:
            logger.error(f"删除K线数据失败: {e}")
            return False

    def add_market_data(self, market_data: Dict[str, Any]) -> bool:
        try:
            if not market_data or 'code' not in market_data:
                logger.error("行情数据无效，必须包含 'code' 字段")
                return False

            stock_code = market_data['code']
            trade_date = market_data.get('trade_date')
            cache_key = f"market_{stock_code}_{trade_date}"

            if self.duckdb_available and self.duckdb_operations:
                success = self.duckdb_operations.insert_market_data(market_data)
                if success:
                    logger.info(f"行情数据已添加到DuckDB: {stock_code} ({trade_date})")
                    self._cache_data(cache_key, market_data)
                    return True

            if self.db_access and self._db_lock:
                with self._db_lock:
                    with self.db_access.get_connection() as conn:
                        cursor = conn.cursor()

                        cursor.execute(
                            "SELECT COUNT(*) FROM market WHERE code = ? AND trade_date = ?",
                            (stock_code, trade_date)
                        )
                        existed = cursor.fetchone()[0] > 0

                        cursor.execute('''
                            INSERT INTO market (code, trade_date, open, high, low, close, volume, amount, change_pct)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(code, trade_date) DO UPDATE SET
                                open = excluded.open,
                                high = excluded.high,
                                low = excluded.low,
                                close = excluded.close,
                                volume = excluded.volume,
                                amount = excluded.amount,
                                change_pct = excluded.change_pct
                        ''', (
                            stock_code, trade_date,
                            market_data.get('open'), market_data.get('high'),
                            market_data.get('low'), market_data.get('close'),
                            market_data.get('volume'), market_data.get('amount'),
                            market_data.get('change_pct')
                        ))

                if existed:
                    logger.info(f"行情数据已更新(覆盖重复): {stock_code} ({trade_date})")
                else:
                    logger.info(f"行情数据已添加到SQLite: {stock_code} ({trade_date})")
                self._cache_data(cache_key, market_data)
                return True

            logger.error("数据库不可用，无法添加行情数据")
            return False

        except Exception as e:
            logger.error(f"添加行情数据失败: {e}")
            return False

    def update_market_data(self, index_code: str, data: Dict[str, Any]) -> bool:
        """更新行情数据"""
        try:
            if not index_code:
                logger.error("股票代码不能为空")
                return False

            trade_date = data.get('trade_date')
            if not trade_date:
                logger.error("行情数据必须包含 'trade_date' 字段")
                return False

            cache_key = f"market_{index_code}_{trade_date}"

            if self.duckdb_available and self.duckdb_operations:
                success = self.duckdb_operations.update_market_data(index_code, trade_date, data)
                if success:
                    logger.info(f"行情数据已在DuckDB更新: {index_code} ({trade_date})")
                    cached_data = self._get_cached_data(cache_key)
                    if cached_data:
                        cached_data.update(data)
                        self._cache_data(cache_key, cached_data)
                    return True

            if self.db_access and self._db_lock:
                with self._db_lock:
                    with self.db_access.get_connection() as conn:
                        cursor = conn.cursor()
                        # SQL注入防护：验证列名白名单
                        data_keys = [key for key in data.keys() if key != 'trade_date']
                        validated_keys = self._validate_columns(data_keys, self._ALLOWED_MARKET_COLUMNS)
                        if not validated_keys:
                            logger.error(f"行情数据列名验证失败，无有效列: {data_keys}")
                            return False
                        set_clause = ', '.join([f"{key} = ?" for key in validated_keys])
                        sql = f"UPDATE market SET {set_clause} WHERE code = ? AND trade_date = ?"
                        params = [data[key] for key in validated_keys]
                        params.extend([index_code, trade_date])
                        cursor.execute(sql, params)

                        if cursor.rowcount > 0:
                            logger.info(f"行情数据已在SQLite更新: {index_code} ({trade_date})")
                            cached_data = self._get_cached_data(cache_key)
                            if cached_data:
                                cached_data.update(data)
                                self._cache_data(cache_key, cached_data)
                            return True

            logger.error("数据库不可用，无法更新行情数据")
            return False

        except Exception as e:
            logger.error(f"更新行情数据失败: {e}")
            return False

    def delete_market_data(self, index_code: str, date: datetime = None) -> bool:
        """删除行情数据"""
        try:
            if not index_code:
                logger.error("股票代码不能为空")
                return False

            cache_pattern = f"market_{index_code}_{date}" if date else f"market_{index_code}"
            deleted = False

            if self.duckdb_available and self.duckdb_operations:
                success = self.duckdb_operations.delete_market_data(index_code, date)
                if success:
                    logger.info(f"行情数据已从DuckDB删除: {index_code}")
                    deleted = True

            if self.db_access and self._db_lock:
                with self._db_lock:
                    with self.db_access.get_connection() as conn:
                        cursor = conn.cursor()
                        sql = "DELETE FROM market WHERE code = ?"
                        params = [index_code]

                        if date:
                            sql += " AND trade_date = ?"
                            params.append(date)

                        cursor.execute(sql, params)

                        if cursor.rowcount > 0:
                            logger.info(f"行情数据已从SQLite删除: {index_code}")
                            deleted = True

            if deleted:
                self._invalidate_cache(cache_pattern)
                return True

            logger.warning(f"行情数据未找到: {index_code}")
            return False

        except Exception as e:
            logger.error(f"删除行情数据失败: {e}")
            return False

    def get_fundamental_data(self, symbol: str, asset_type: AssetType = AssetType.STOCK_A, **params) -> Dict[str, Any]:
        """
        获取基本面数据 - 统一入口

        Args:
            symbol: 标的代码
            asset_type: 资产类型
            **params: 其他参数

        Returns:
            Dict[str, Any]: 基本面数据
        """
        try:
            if self._uni_plugin_manager is None:
                self._create_uni_plugin_manager_if_needed()
            
            if self._uni_plugin_manager:
                return self._uni_plugin_manager.get_fundamental_data(symbol, asset_type, **params)
            else:
                logger.warning("UniPluginDataManager不可用，返回空的基本面数据")
                return {}
        except Exception as e:
            logger.error(f"获取基本面数据失败: {e}")
            return {}

    def get_fundamental_data_batch(self, symbols: List[str], asset_type: AssetType = AssetType.STOCK_A, **params) -> Dict[str, Dict[str, Any]]:
        """
        批量获取基本面数据 - 统一入口

        Args:
            symbols: 标的代码列表
            asset_type: 资产类型
            **params: 其他参数

        Returns:
            Dict[symbol, Dict[str, Any]]: 基本面数据字典
        """
        try:
            if self._uni_plugin_manager is None:
                self._create_uni_plugin_manager_if_needed()
            
            if self._uni_plugin_manager:
                return self._uni_plugin_manager.get_fundamental_data_batch(symbols, asset_type, **params)
            else:
                logger.warning("UniPluginDataManager不可用，返回空的基本面数据字典")
                return {symbol: {} for symbol in symbols}
        except Exception as e:
            logger.error(f"批量获取基本面数据失败: {e}")
            return {symbol: {} for symbol in symbols}
