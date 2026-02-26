"""
统一数据服务 - 架构精简重构版本

统一所有数据管理器功能，提供单一的数据访问接口。
整合UnifiedDataManager、UniPluginDataManager等核心数据管理器。
完全重构以符合15个核心服务的架构精简目标。
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Set, Tuple, Type
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
import pandas as pd
import numpy as np
import sqlite3
import os
import traceback
from collections import defaultdict

from loguru import logger

from .base_service import BaseService
from ..events import EventBus, DataUpdateEvent, get_event_bus
from ..containers import ServiceContainer, get_service_container
from ..plugin_types import AssetType, DataType, PluginType
from ..data_source_extensions import IDataSourcePlugin, PluginInfo, HealthCheckResult
from ..tet_data_pipeline import TETDataPipeline, StandardQuery, StandardData
from ..data_source_router import DataSourceRouter, RoutingStrategy
from ..plugin_manager import PluginManager
from ..plugin_center import PluginCenter
from ..tet_router_engine import TETRouterEngine
from ..data_quality_risk_manager import DataQualityRiskManager
from .metrics_base import add_dict_interface


class DataAccessMode(Enum):
    """数据访问模式"""
    REAL_TIME = "real_time"
    CACHED = "cached"
    HYBRID = "hybrid"
    FALLBACK = "fallback"


class DataServiceStatus(Enum):
    """数据服务状态"""
    INITIALIZING = "initializing"
    READY = "ready"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class DataQualityLevel(Enum):
    """数据质量等级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass
class DataRequest:
    """统一数据请求"""
    request_id: str
    asset_type: AssetType
    data_type: DataType
    symbol: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    frequency: str = "1d"
    parameters: Dict[str, Any] = field(default_factory=dict)
    access_mode: DataAccessMode = DataAccessMode.HYBRID
    priority: int = 1
    timeout: Optional[float] = None
    callback: Optional[Callable] = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """后处理初始化"""
        if not self.end_date:
            self.end_date = datetime.now()
        if not self.start_date:
            self.start_date = self.end_date - timedelta(days=365)


@dataclass
class DataResponse:
    """统一数据响应"""
    request_id: str
    data: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    quality: DataQualityLevel = DataQualityLevel.UNKNOWN
    source: Optional[str] = None
    cached: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
    processing_time: float = 0.0


@add_dict_interface
@dataclass
class DataMetrics:
    """数据服务指标"""
    # 基础指标字段（与BaseService一致）
    initialization_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    operation_count: int = 0

    # 数据服务特定字段
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_response_time: float = 0.0
    data_sources_active: int = 0
    data_sources_total: int = 0
    last_update: datetime = field(default_factory=datetime.now)


class DataService(BaseService):
    """
    统一数据服务 - 架构精简重构版本

    整合所有数据管理器功能：
    - UnifiedDataManager: 统一数据管理
    - UniPluginDataManager: 插件数据管理
    - 其他各类数据管理器

    提供统一的数据访问接口，支持：
    1. 多数据源管理和路由
    2. 智能缓存策略
    3. 实时和历史数据获取
    4. 数据质量管理
    5. 插件数据集成
    6. 异步和并发处理
    7. 性能监控和优化
    """

    def __init__(self, service_container: Optional[ServiceContainer] = None):
        """
        初始化数据服务

        Args:
            service_container: 服务容器
        """
        super().__init__()
        self.service_name = "DataService"

        # 依赖注入
        self._service_container = service_container or get_service_container()

        # 核心组件
        self._data_pipeline: Optional[TETDataPipeline] = None
        self._data_router: Optional[DataSourceRouter] = None
        self._plugin_manager: Optional[PluginManager] = None
        self._plugin_center: Optional[PluginCenter] = None
        self._tet_engine: Optional[TETRouterEngine] = None
        self._quality_manager: Optional[DataQualityRiskManager] = None

        # 状态管理
        self._status = DataServiceStatus.INITIALIZING
        self._metrics = DataMetrics()
        self._service_lock = threading.RLock()

        # 数据源管理
        self._data_sources: Dict[str, IDataSourcePlugin] = {}
        self._source_health: Dict[str, bool] = {}
        self._source_capabilities: Dict[str, Set[DataType]] = {}

        # 缓存系统 - 强制使用统一缓存服务
        self._cache_metadata: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl_config: Dict[DataType, timedelta] = {
            DataType.REAL_TIME_QUOTE: timedelta(minutes=1),
            DataType.HISTORICAL_KLINE: timedelta(minutes=5),
            DataType.FUNDAMENTAL: timedelta(hours=6),
            DataType.NEWS: timedelta(minutes=15),
            DataType.SENTIMENT_DATA: timedelta(minutes=30),
            DataType.FUND_FLOW: timedelta(minutes=5),
            DataType.TECHNICAL_INDICATORS: timedelta(minutes=10)
        }
        self._unified_cache = None
        self._cache_namespace = 'data_service'
        self._init_unified_cache()

        # 请求管理
        self._pending_requests: Dict[str, DataRequest] = {}
        self._active_requests: Dict[str, DataRequest] = {}
        self._completed_requests: Dict[str, DataResponse] = {}
        self._request_futures: Dict[str, Future] = {}
        self._request_lock = threading.RLock()

        # 线程池管理（v2.4性能优化：增加工作线程）
        self._data_executor = ThreadPoolExecutor(
            max_workers=40,  # 从20增加到40
            thread_name_prefix="DataService-Worker"
        )
        self._cache_executor = ThreadPoolExecutor(
            max_workers=10,  # 从5增加到10
            thread_name_prefix="DataService-Cache"
        )

        # 订阅者管理
        self._data_subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._real_time_subscriptions: Set[str] = set()

        # 配置参数
        self._config = {
            "max_concurrent_requests": 50,
            "cache_cleanup_interval": 300,  # 5分钟
            "health_check_interval": 60,    # 1分钟
            "request_timeout": 30.0,        # 30秒
            "enable_cache": True,
            "enable_async_processing": True,
            "enable_data_quality_check": True
        }

        # 监控和统计
        self._start_time = datetime.now()
        self._last_health_check = datetime.now()
        self._performance_samples: List[float] = []

        logger.info("DataService initialized for architecture simplification")

    def _init_unified_cache(self) -> None:
        """初始化统一缓存服务（强制）"""
        from core.services.cache_service import CacheService
        
        if self._service_container and self._service_container.is_registered(CacheService):
            self._unified_cache = self._service_container.resolve(CacheService)
            logger.debug(f"DataService 已连接到统一缓存服务，命名空间: {self._cache_namespace}")
        else:
            raise RuntimeError("统一缓存服务未注册，请确保 CacheService 已在服务容器中注册")

    def _do_initialize(self) -> None:
        """执行具体的初始化逻辑"""
        try:
            logger.info("Initializing DataService core components...")

            # 1. 初始化数据路由器
            self._initialize_data_router()

            # 2. 初始化TET数据管道
            self._initialize_data_pipeline()

            # 3. 初始化插件系统
            self._initialize_plugin_system()

            # 4. 初始化TET路由引擎
            self._initialize_tet_engine()

            # 5. 初始化质量管理器
            self._initialize_quality_manager()

            # 6. 发现和注册数据源
            self._discover_data_sources()

            # 7. 启动后台任务
            self._start_background_tasks()

            # 8. 验证系统健康状态
            self._validate_system_health()

            self._status = DataServiceStatus.READY

            logger.info("DataService initialized successfully with full data management capabilities")

        except Exception as e:
            self._status = DataServiceStatus.OFFLINE
            logger.error(f"❌ Failed to initialize DataService: {e}")
            logger.error(traceback.format_exc())
            raise

    def _initialize_data_router(self) -> None:
        """初始化数据源路由器"""
        try:
            if self._service_container.is_registered(DataSourceRouter):
                self._data_router = self._service_container.resolve(DataSourceRouter)
                logger.info("✓ Using existing DataSourceRouter from container")
            else:
                self._data_router = DataSourceRouter()
                logger.info("✓ Created new DataSourceRouter")

        except Exception as e:
            logger.error(f"Failed to initialize data router: {e}")
            raise

    def _initialize_data_pipeline(self) -> None:
        """初始化TET数据管道"""
        try:
            if not self._data_router:
                raise ValueError("DataSourceRouter must be initialized first")

            self._data_pipeline = TETDataPipeline(self._data_router)
            logger.info("✓ TET Data Pipeline initialized")

        except Exception as e:
            logger.error(f"Failed to initialize data pipeline: {e}")
            raise

    def _initialize_plugin_system(self) -> None:
        """初始化插件系统"""
        try:
            # 获取或创建插件管理器
            if self._service_container.is_registered(PluginManager):
                self._plugin_manager = self._service_container.resolve(PluginManager)
                logger.info("✓ Using existing PluginManager from container")
            else:
                self._plugin_manager = PluginManager()
                logger.info("✓ Created new PluginManager")

            # 创建插件中心
            self._plugin_center = PluginCenter(self._plugin_manager)
            logger.info("✓ Plugin Center initialized")

        except Exception as e:
            logger.error(f"Failed to initialize plugin system: {e}")
            raise

    def _initialize_tet_engine(self) -> None:
        """初始化TET路由引擎"""
        try:
            if not self._data_router or not self._data_pipeline:
                raise ValueError("DataSourceRouter and TETDataPipeline must be initialized first")

            self._tet_engine = TETRouterEngine(self._data_router, self._data_pipeline)
            logger.info("✓ TET Router Engine initialized")

        except Exception as e:
            logger.error(f"Failed to initialize TET engine: {e}")
            raise

    def _initialize_quality_manager(self) -> None:
        """初始化质量管理器"""
        try:
            self._quality_manager = DataQualityRiskManager()
            logger.info("✓ Data Quality Risk Manager initialized")

        except Exception as e:
            logger.error(f"Failed to initialize quality manager: {e}")
            raise

    def _discover_data_sources(self) -> None:
        """发现和注册数据源"""
        try:
            if not self._plugin_center:
                logger.warning("Plugin center not available, skipping data source discovery")
                return

            # 发现并注册插件
            discovered_plugins = self._plugin_center.discover_and_register_plugins()

            # 遍历已注册的插件并添加到数据源
            for plugin_name, plugin_info in discovered_plugins.items():
                try:
                    # 获取插件实例
                    plugin = self._plugin_manager.get_plugin(plugin_name)
                    if plugin and hasattr(plugin, 'get_supported_data_types'):
                        # 注册到数据源管理
                        self._data_sources[plugin_name] = plugin
                        self._source_capabilities[plugin_name] = set(plugin.get_supported_data_types())
                        self._source_health[plugin_name] = True

                        logger.info(f"✓ Registered data source: {plugin_name}")

                except Exception as e:
                    logger.warning(f"Failed to register data source {plugin_name}: {e}")

            self._metrics.data_sources_total = len(self._data_sources)
            self._metrics.data_sources_active = len([s for s in self._source_health.values() if s])

            logger.info(f"✓ Data source discovery completed: {len(self._data_sources)} sources found")

        except Exception as e:
            logger.error(f"Failed to discover data sources: {e}")

    def _start_background_tasks(self) -> None:
        """启动后台任务"""
        try:
            # 启动缓存清理任务
            self._data_executor.submit(self._cache_cleanup_loop)

            # 启动健康检查任务
            self._data_executor.submit(self._health_check_loop)

            # 启动性能监控任务
            self._data_executor.submit(self._performance_monitoring_loop)

            logger.info("✓ Background tasks started")

        except Exception as e:
            logger.error(f"Failed to start background tasks: {e}")

    def _validate_system_health(self) -> None:
        """验证系统健康状态"""
        try:
            # 检查核心组件
            components = {
                "DataRouter": self._data_router,
                "DataPipeline": self._data_pipeline,
                "PluginManager": self._plugin_manager,
                "PluginCenter": self._plugin_center,
                "TETEngine": self._tet_engine,
                "QualityManager": self._quality_manager
            }

            healthy_components = 0
            for name, component in components.items():
                if component is not None:
                    healthy_components += 1
                    logger.info(f"✓ {name}: Healthy")
                else:
                    logger.warning(f"⚠ {name}: Not available")

            if healthy_components < 4:  # 至少需要4个核心组件
                self._status = DataServiceStatus.DEGRADED
                logger.warning(f"System running in degraded mode: {healthy_components}/{len(components)} components healthy")
            else:
                logger.info(f"✓ System health validation passed: {healthy_components}/{len(components)} components healthy")

        except Exception as e:
            logger.error(f"System health validation failed: {e}")
            self._status = DataServiceStatus.DEGRADED

    def _cache_cleanup_loop(self) -> None:
        """缓存清理循环"""
        while not self._shutdown_event.is_set():
            try:
                self._cleanup_expired_cache()
                self._shutdown_event.wait(self._config["cache_cleanup_interval"])
            except Exception as e:
                logger.error(f"Error in cache cleanup loop: {e}")
                self._shutdown_event.wait(60)  # 出错时等待1分钟

    def _health_check_loop(self) -> None:
        """健康检查循环"""
        while not self._shutdown_event.is_set():
            try:
                self._perform_health_checks()
                self._shutdown_event.wait(self._config["health_check_interval"])
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                self._shutdown_event.wait(60)

    def _performance_monitoring_loop(self) -> None:
        """性能监控循环"""
        while not self._shutdown_event.is_set():
            try:
                self._collect_performance_metrics()
                self._shutdown_event.wait(30)  # 每30秒收集一次
            except Exception as e:
                logger.error(f"Error in performance monitoring loop: {e}")
                self._shutdown_event.wait(60)

    def get_data(self, request: DataRequest) -> DataResponse:
        """
        获取数据 - 主要接口方法

        Args:
            request: 数据请求

        Returns:
            数据响应
        """
        start_time = time.time()

        try:
            with self._request_lock:
                self._metrics.total_requests += 1
                self._pending_requests[request.request_id] = request

            # 检查缓存
            if self._config["enable_cache"] and request.access_mode in [DataAccessMode.CACHED, DataAccessMode.HYBRID]:
                cached_response = self._get_from_cache(request)
                if cached_response:
                    self._metrics.cache_hits += 1
                    cached_response.processing_time = time.time() - start_time
                    return cached_response
                else:
                    self._metrics.cache_misses += 1

            # 从数据源获取
            response = self._fetch_from_sources(request)

            # 更新缓存
            if response and response.data is not None and self._config["enable_cache"]:
                self._update_cache(request, response)

            # 更新统计
            if response and response.error is None:
                self._metrics.successful_requests += 1
            else:
                self._metrics.failed_requests += 1

            # 记录性能
            processing_time = time.time() - start_time
            response.processing_time = processing_time
            self._performance_samples.append(processing_time)

            # 更新平均响应时间
            if len(self._performance_samples) > 100:
                self._performance_samples = self._performance_samples[-100:]
            self._metrics.avg_response_time = sum(self._performance_samples) / len(self._performance_samples)

            # 移动到已完成请求
            with self._request_lock:
                if request.request_id in self._pending_requests:
                    del self._pending_requests[request.request_id]
                self._completed_requests[request.request_id] = response

            return response

        except Exception as e:
            self._metrics.failed_requests += 1
            error_response = DataResponse(
                request_id=request.request_id,
                error=str(e),
                processing_time=time.time() - start_time
            )

            with self._request_lock:
                if request.request_id in self._pending_requests:
                    del self._pending_requests[request.request_id]
                self._completed_requests[request.request_id] = error_response

            logger.error(f"Failed to get data for request {request.request_id}: {e}")
            return error_response

    def _get_from_cache(self, request: DataRequest) -> Optional[DataResponse]:
        """从缓存获取数据 - 使用统一缓存服务"""
        try:
            cache_key = self._generate_cache_key(request)
            ttl = self._cache_ttl_config.get(request.data_type, timedelta(minutes=5))

            if self._unified_cache is None:
                raise RuntimeError("统一缓存服务未初始化")

            cached_entry = self._unified_cache.get(cache_key, namespace=self._cache_namespace)
            if cached_entry is not None:
                data, timestamp, quality = cached_entry
                if datetime.now() - timestamp < ttl:
                    return DataResponse(
                        request_id=request.request_id,
                        data=data,
                        quality=quality,
                        cached=True,
                        timestamp=timestamp,
                        metadata=self._cache_metadata.get(cache_key, {})
                    )

            return None

        except Exception as e:
            logger.error(f"Error accessing cache for request {request.request_id}: {e}")
            return None

    def _fetch_from_sources(self, request: DataRequest) -> DataResponse:
        """从数据源获取数据"""
        try:
            # 根据数据类型选择合适的数据源
            suitable_sources = self._find_suitable_sources(request)

            if not suitable_sources:
                return DataResponse(
                    request_id=request.request_id,
                    error=f"No suitable data sources found for {request.data_type}"
                )

            # 尝试从首选数据源获取
            for source_name in suitable_sources:
                try:
                    source = self._data_sources[source_name]

                    # 使用TET引擎进行查询
                    if self._tet_engine:
                        query = StandardQuery(
                            asset_type=request.asset_type,
                            data_type=request.data_type,
                            symbol=request.symbol,
                            start_date=request.start_date,
                            end_date=request.end_date,
                            frequency=request.frequency,
                            parameters=request.parameters
                        )

                        result = self._tet_engine.execute_query(query)
                        if result and result.data is not None:
                            quality = self._assess_data_quality(result.data, request)

                            return DataResponse(
                                request_id=request.request_id,
                                data=result.data,
                                metadata=result.metadata,
                                quality=quality,
                                source=source_name,
                                timestamp=datetime.now()
                            )

                except Exception as e:
                    logger.warning(f"Failed to fetch from source {source_name}: {e}")
                    # 标记数据源不健康
                    self._source_health[source_name] = False
                    continue

            # 所有数据源都失败
            return DataResponse(
                request_id=request.request_id,
                error="All data sources failed to provide data"
            )

        except Exception as e:
            logger.error(f"Error fetching from sources: {e}")
            return DataResponse(
                request_id=request.request_id,
                error=str(e)
            )

    def _find_suitable_sources(self, request: DataRequest) -> List[str]:
        """查找合适的数据源"""
        suitable_sources = []

        for source_name, capabilities in self._source_capabilities.items():
            # 检查数据源是否支持请求的数据类型
            if request.data_type in capabilities:
                # 检查数据源健康状态
                if self._source_health.get(source_name, False):
                    suitable_sources.append(source_name)

        # 按优先级排序（这里可以加入更复杂的优先级逻辑）
        suitable_sources.sort()

        return suitable_sources

    def _assess_data_quality(self, data: Any, request: DataRequest) -> DataQualityLevel:
        """评估数据质量"""
        try:
            if self._quality_manager:
                # 使用质量管理器进行评估
                # 这里需要适配质量管理器的接口
                return DataQualityLevel.HIGH

            # 简单的质量评估
            if data is None:
                return DataQualityLevel.UNKNOWN

            if isinstance(data, pd.DataFrame):
                if len(data) == 0:
                    return DataQualityLevel.LOW
                elif data.isnull().sum().sum() > len(data) * 0.3:  # 超过30%的缺失值
                    return DataQualityLevel.MEDIUM
                else:
                    return DataQualityLevel.HIGH

            return DataQualityLevel.MEDIUM

        except Exception as e:
            logger.error(f"Error assessing data quality: {e}")
            return DataQualityLevel.UNKNOWN

    def _update_cache(self, request: DataRequest, response: DataResponse) -> None:
        """更新缓存 - 使用统一缓存服务"""
        try:
            cache_key = self._generate_cache_key(request)
            cache_entry = (response.data, response.timestamp, response.quality)
            ttl = self._cache_ttl_config.get(request.data_type, timedelta(minutes=5))

            if self._unified_cache is None:
                raise RuntimeError("统一缓存服务未初始化")

            self._unified_cache.set(cache_key, cache_entry, ttl=ttl, namespace=self._cache_namespace)
            self._cache_metadata[cache_key] = response.metadata.copy()

        except Exception as e:
            logger.error(f"Error updating cache: {e}")

    def _generate_cache_key(self, request: DataRequest) -> str:
        """生成缓存键"""
        key_parts = [
            str(request.asset_type.value if hasattr(request.asset_type, 'value') else request.asset_type),
            str(request.data_type.value if hasattr(request.data_type, 'value') else request.data_type),
            request.symbol,
            request.frequency,
            str(request.start_date.date() if request.start_date else ""),
            str(request.end_date.date() if request.end_date else "")
        ]

        # 添加参数到键中
        if request.parameters:
            param_str = "_".join([f"{k}={v}" for k, v in sorted(request.parameters.items())])
            key_parts.append(param_str)

        return "|".join(key_parts)

    def _cleanup_expired_cache(self) -> None:
        """清理过期缓存 - 统一缓存服务自动管理TTL，此方法保留用于清理元数据"""
        try:
            expired_keys = [k for k in self._cache_metadata.keys() 
                          if self._unified_cache.get(k, namespace=self._cache_namespace) is None]
            
            for key in expired_keys:
                del self._cache_metadata[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache metadata entries")

        except Exception as e:
            logger.error(f"Error in cache cleanup: {e}")

    def _perform_health_checks(self) -> None:
        """执行健康检查"""
        try:
            self._last_health_check = datetime.now()

            # 检查数据源健康状态
            active_sources = 0
            for source_name, source in self._data_sources.items():
                try:
                    if hasattr(source, 'health_check'):
                        health_result = source.health_check()
                        is_healthy = health_result.is_healthy if hasattr(health_result, 'is_healthy') else True
                    else:
                        is_healthy = True  # 假设健康

                    self._source_health[source_name] = is_healthy
                    if is_healthy:
                        active_sources += 1

                except Exception as e:
                    logger.warning(f"Health check failed for source {source_name}: {e}")
                    self._source_health[source_name] = False

            self._metrics.data_sources_active = active_sources

            # 更新服务状态
            if active_sources == 0:
                self._status = DataServiceStatus.OFFLINE
            elif active_sources < len(self._data_sources) * 0.5:
                self._status = DataServiceStatus.DEGRADED
            else:
                self._status = DataServiceStatus.READY

        except Exception as e:
            logger.error(f"Error in health checks: {e}")

    def _collect_performance_metrics(self) -> None:
        """收集性能指标"""
        try:
            self._metrics.last_update = datetime.now()

            # 清理旧的性能样本
            if len(self._performance_samples) > 1000:
                self._performance_samples = self._performance_samples[-500:]

        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")

    def _do_health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        try:
            return {
                "status": self._status.value,
                "data_sources_active": self._metrics.data_sources_active,
                "data_sources_total": self._metrics.data_sources_total,
                "cache_size": len(self._cache),
                "pending_requests": len(self._pending_requests),
                "active_requests": len(self._active_requests),
                "avg_response_time": self._metrics.avg_response_time,
                "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
                "last_health_check": self._last_health_check.isoformat()
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_service_metrics(self) -> DataMetrics:
        """获取服务指标"""
        return self._metrics

    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        with self._cache_lock:
            return {
                "cache_size": len(self._cache),
                "cache_hit_rate": (
                    self._metrics.cache_hits / max(1, self._metrics.cache_hits + self._metrics.cache_misses)
                ),
                "ttl_config": {str(k): str(v) for k, v in self._cache_ttl_config.items()}
            }

    def clear_cache(self, data_type: Optional[DataType] = None) -> int:
        """清理缓存"""
        try:
            with self._cache_lock:
                if data_type is None:
                    # 清理所有缓存
                    cleared_count = len(self._cache)
                    self._cache.clear()
                    self._cache_metadata.clear()
                else:
                    # 清理特定类型的缓存
                    data_type_str = str(data_type.value if hasattr(data_type, 'value') else data_type)
                    keys_to_remove = [k for k in self._cache.keys() if data_type_str in k]
                    cleared_count = len(keys_to_remove)

                    for key in keys_to_remove:
                        del self._cache[key]
                        if key in self._cache_metadata:
                            del self._cache_metadata[key]

                logger.info(f"Cleared {cleared_count} cache entries")
                return cleared_count

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0

    def _do_dispose(self) -> None:
        """清理资源"""
        try:
            logger.info("Disposing DataService resources...")

            # 停止线程池
            if self._data_executor:
                self._data_executor.shutdown(wait=True)
                logger.info("Data executor shutdown")

            if self._cache_executor:
                self._cache_executor.shutdown(wait=True)
                logger.info("Cache executor shutdown")

            # 清理缓存
            with self._cache_lock:
                self._cache.clear()
                self._cache_metadata.clear()

            # 清理请求
            with self._request_lock:
                self._pending_requests.clear()
                self._active_requests.clear()
                self._completed_requests.clear()

            logger.info("DataService disposed successfully")

        except Exception as e:
            logger.error(f"Error disposing DataService: {e}")

    @property
    def metrics(self) -> Dict[str, Any]:
        """返回数据服务指标的字典表示"""
        if not hasattr(self, '_data_metrics'):
            self._data_metrics = self._metrics

        return {
            'total_requests': self._data_metrics.total_requests,
            'successful_requests': self._data_metrics.successful_requests,
            'failed_requests': self._data_metrics.failed_requests,
            'cache_hits': self._data_metrics.cache_hits,
            'cache_misses': self._data_metrics.cache_misses,
            'avg_response_time': self._data_metrics.avg_response_time,
            'data_sources_active': self._data_metrics.data_sources_active,
            'data_sources_total': self._data_metrics.data_sources_total,
            'last_update': self._data_metrics.last_update.isoformat()
        }


# 便利函数
def create_data_request(symbol: str, data_type: DataType, asset_type: AssetType = AssetType.STOCK_A, **kwargs) -> DataRequest:
    """创建数据请求的便利函数"""
    import uuid

    return DataRequest(
        request_id=str(uuid.uuid4()),
        symbol=symbol,
        data_type=data_type,
        asset_type=asset_type,
        **kwargs
    )
