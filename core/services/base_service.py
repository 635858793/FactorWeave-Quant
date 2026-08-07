"""
基础服务模块

定义所有服务的基础接口和通用功能。
为架构精简重构提供增强的服务基类。
"""

import time
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from datetime import datetime
from loguru import logger
from ..events import EventBus, get_event_bus



class BaseService(ABC):
    """
    基础服务接口

    所有业务服务都应该继承此类。
    为架构精简重构提供统一的服务基础设施。
    """

    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        初始化基础服务

        Args:
            event_bus: 事件总线，如果为None则使用全局事件总线
        """
        # HVD-241-P1-B: event_bus or → is not None (EventBus __len__ falsy 陷阱, R240-P0-007)
        self._event_bus = event_bus if event_bus is not None else get_event_bus()
        self._initialized = False
        self._disposed = False
        self._name = self.__class__.__name__

        # 架构精简重构增强功能
        self._initialization_time: Optional[float] = None
        self._last_health_check: Optional[datetime] = None
        self._dependencies: List[str] = []
        self._service_id = f"{self._name}_{id(self)}"
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()
        self._metrics: Dict[str, Any] = {
            "initialization_count": 0,
            "error_count": 0,
            "last_error": None,
            "operation_count": 0
        }

    @property
    def name(self) -> str:
        """获取服务名称"""
        return self._name

    @property
    def initialized(self) -> bool:
        """检查服务是否已初始化"""
        return self._initialized

    @property
    def disposed(self) -> bool:
        """检查服务是否已释放"""
        return self._disposed

    @property
    def event_bus(self) -> EventBus:
        """获取事件总线"""
        return self._event_bus

    @property
    def service_id(self) -> str:
        """获取服务唯一标识"""
        return self._service_id

    @property
    def initialization_time(self) -> Optional[float]:
        """获取初始化时间（秒）"""
        return self._initialization_time

    @property
    def dependencies(self) -> List[str]:
        """获取服务依赖列表"""
        return self._dependencies.copy()

    @property
    def metrics(self) -> Dict[str, Any]:
        """获取服务指标 - 支持字典和对象类型"""
        with self._lock:
            # 支持多种metrics类型
            if isinstance(self._metrics, dict):
                return self._metrics.copy()
            elif hasattr(self._metrics, 'to_dict'):
                return self._metrics.to_dict()
            elif hasattr(self._metrics, '__dict__'):
                return vars(self._metrics).copy()
            else:
                return {'metrics': str(self._metrics)}

    def initialize(self) -> None:
        """
        初始化服务

        子类可以重写此方法来执行初始化逻辑。
        为架构精简重构提供增强的初始化流程。
        """
        if self._initialized:
            logger.warning(f"Service {self._name} is already initialized")
            return

        start_time = time.time()

        try:
            with self._lock:
                self._metrics["initialization_count"] += 1

            logger.info(f"Initializing service {self._name} for architecture simplification")

            # 执行实际初始化
            self._do_initialize()

            # 记录初始化时间
            self._initialization_time = time.time() - start_time
            self._initialized = True
            self._last_health_check = datetime.now()

            logger.info(f"Service {self._name} initialized successfully in {self._initialization_time:.3f}s")

            # 发送初始化成功事件
            self._event_bus.publish(f"service.{self._name}.initialized",
                                    service_id=self._service_id,
                                    initialization_time=self._initialization_time
                                    )

        except Exception as e:
            with self._lock:
                self._metrics["error_count"] += 1
                self._metrics["last_error"] = str(e)

            logger.error(f"Failed to initialize service {self._name}: {e}")

            # 发送初始化失败事件
            self._event_bus.publish(f"service.{self._name}.initialization_failed",
                                    service_id=self._service_id,
                                    error=str(e)
                                    )
            raise

    def dispose(self) -> None:
        """
        释放服务资源

        子类可以重写此方法来执行清理逻辑。
        """
        if self._disposed:
            logger.warning(f"Service {self._name} is already disposed")
            return

        try:
            self._do_dispose()
            self._disposed = True
            self._initialized = False
            logger.info(f"Service {self._name} disposed successfully")
        except Exception as e:
            logger.error(f"Failed to dispose service {self._name}: {e}")
            raise

    def _do_initialize(self) -> None:
        """
        执行初始化逻辑

        子类应该重写此方法来实现具体的初始化逻辑。
        """
        pass

    def _do_dispose(self) -> None:
        """
        执行清理逻辑

        子类应该重写此方法来实现具体的清理逻辑。
        """
        pass

    def _ensure_initialized(self) -> None:
        """确保服务已初始化"""
        if not self._initialized:
            raise RuntimeError(f"Service {self._name} is not initialized")

    def _ensure_not_disposed(self) -> None:
        """确保服务未被释放"""
        if self._disposed:
            raise RuntimeError(f"Service {self._name} has been disposed")

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()

    def perform_health_check(self) -> Dict[str, Any]:
        """
        执行健康检查

        Returns:
            健康检查结果
        """
        self._last_health_check = datetime.now()

        health_status = {
            "service_name": self._name,
            "service_id": self._service_id,
            "status": "healthy" if self._initialized and not self._disposed else "unhealthy",
            "initialized": self._initialized,
            "disposed": self._disposed,
            "initialization_time": self._initialization_time,
            "last_check": self._last_health_check.isoformat(),
            "metrics": self.metrics  # 这里调用属性，返回字典
        }

        # 子类可以重写此方法添加自定义健康检查
        try:
            custom_health = self._do_health_check()
            if custom_health:
                health_status.update(custom_health)
        except Exception as e:
            health_status["custom_health_error"] = str(e)
            with self._lock:
                self._metrics["error_count"] += 1
                self._metrics["last_error"] = str(e)

        return health_status

    def _do_health_check(self) -> Optional[Dict[str, Any]]:
        """
        执行自定义健康检查

        子类可以重写此方法来实现特定的健康检查逻辑。

        Returns:
            自定义健康检查结果，或None
        """
        return None

    def add_dependency(self, dependency_name: str) -> None:
        """
        添加服务依赖

        Args:
            dependency_name: 依赖的服务名称
        """
        if dependency_name not in self._dependencies:
            self._dependencies.append(dependency_name)
            logger.debug(f"Service {self._name} added dependency: {dependency_name}")

    def remove_dependency(self, dependency_name: str) -> None:
        """
        移除服务依赖

        Args:
            dependency_name: 依赖的服务名称
        """
        if dependency_name in self._dependencies:
            self._dependencies.remove(dependency_name)
            logger.debug(f"Service {self._name} removed dependency: {dependency_name}")

    def increment_operation_count(self) -> None:
        """增加操作计数"""
        with self._lock:
            self._metrics["operation_count"] += 1

    def get_service_info(self) -> Dict[str, Any]:
        """
        获取服务信息

        Returns:
            服务信息字典
        """
        return {
            "service_name": self._name,
            "service_id": self._service_id,
            "initialized": self._initialized,
            "disposed": self._disposed,
            "initialization_time": self._initialization_time,
            "dependencies": self.dependencies,
            "metrics": self.metrics,
            "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None
        }


class AsyncBaseService(BaseService):
    """
    异步基础服务接口

    支持异步操作的服务应该继承此类。
    """

    async def initialize_async(self) -> None:
        """
        异步初始化服务
        """
        if self._initialized:
            logger.warning(f"Service {self._name} is already initialized")
            return

        try:
            await self._do_initialize_async()
            self._initialized = True
            logger.info(
                f"Service {self._name} initialized successfully (async)")
        except Exception as e:
            logger.error(
                f"Failed to initialize service {self._name} (async): {e}")
            raise

    async def dispose_async(self) -> None:
        """
        异步释放服务资源
        """
        if self._disposed:
            logger.warning(f"Service {self._name} is already disposed")
            return

        try:
            await self._do_dispose_async()
            self._disposed = True
            self._initialized = False
            logger.info(f"Service {self._name} disposed successfully (async)")
        except Exception as e:
            logger.error(
                f"Failed to dispose service {self._name} (async): {e}")
            raise

    async def _do_initialize_async(self) -> None:
        """
        执行异步初始化逻辑

        子类应该重写此方法来实现具体的异步初始化逻辑。
        """
        pass

    async def _do_dispose_async(self) -> None:
        """
        执行异步清理逻辑

        子类应该重写此方法来实现具体的异步清理逻辑。
        """
        pass

    async def __aenter__(self):
        await self.initialize_async()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.dispose_async()


class ConfigurableService(BaseService):
    """
    可配置服务基类

    需要配置的服务应该继承此类。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, event_bus: Optional[EventBus] = None):
        """
        初始化可配置服务

        Args:
            config: 服务配置
            event_bus: 事件总线
        """
        super().__init__(event_bus)
        self._config = config or {}

    @property
    def config(self) -> Dict[str, Any]:
        """获取服务配置"""
        return self._config.copy()

    def update_config(self, config: Dict[str, Any]) -> None:
        """
        更新服务配置

        Args:
            config: 新的配置
        """
        self._config.update(config)
        self._on_config_updated()
        logger.debug(f"Updated config for service {self._name}")

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值
        """
        return self._config.get(key, default)

    def _on_config_updated(self) -> None:
        """
        配置更新回调

        子类可以重写此方法来响应配置更新。
        """
        pass


class CacheableService(BaseService):
    """
    可缓存服务基类

    需要缓存功能的服务应该继承此类。
    强制使用统一的 CacheService，不提供独立缓存回退。
    """

    def __init__(self, cache_size: int = 100, event_bus: Optional[EventBus] = None,
                 namespace: Optional[str] = None):
        """
        初始化可缓存服务

        Args:
            cache_size: 缓存大小（已废弃，保留参数兼容性）
            event_bus: 事件总线
            namespace: 缓存命名空间（用于统一缓存服务）
        """
        super().__init__(event_bus)
        self._cache_size = cache_size
        self._cache_hits = 0
        self._cache_misses = 0
        self._namespace = namespace or self.__class__.__name__.lower().replace('service', '')
        self._unified_cache = None

        self._init_unified_cache()

    def _init_unified_cache(self) -> None:
        """初始化统一缓存服务（强制的优雅降级）"""
        from core.containers import get_service_container
        from core.services.cache_service import CacheService

        container = get_service_container()
        if container and container.is_registered(CacheService):
            self._unified_cache = container.resolve(CacheService)
            logger.debug(f"{self.__class__.__name__} 已连接到统一缓存服务，命名空间: {self._namespace}")
        else:
            self._unified_cache = None
            logger.debug(f"{self.__class__.__name__} 统一缓存服务未注册，缓存功能降级为空操作")

    def get_from_cache(self, key: str) -> Optional[Any]:
        if self._unified_cache is None:
            self._cache_misses += 1
            return None

        value = self._unified_cache.get(key, namespace=self._namespace)
        if value is not None:
            self._cache_hits += 1
            return value
        else:
            self._cache_misses += 1
            return None

    def put_to_cache(self, key: str, value: Any, ttl: Optional[Any] = None) -> None:
        if self._unified_cache is None:
            return

        from datetime import timedelta
        ttl_delta = None
        if ttl is not None:
            if isinstance(ttl, (int, float)):
                ttl_delta = timedelta(seconds=ttl)
            elif isinstance(ttl, timedelta):
                ttl_delta = ttl

        self._unified_cache.set(key, value, ttl=ttl_delta, namespace=self._namespace)

    def clear_cache(self) -> None:
        if self._unified_cache is None:
            return

        self._unified_cache.clear_namespace(self._namespace)
        logger.debug(f"统一缓存命名空间 {self._namespace} 已清空")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计信息
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0

        stats = {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate': hit_rate,
            'namespace': self._namespace,
        }

        if self._unified_cache:
            try:
                ns_stats = self._unified_cache.get_namespace_stats(self._namespace)
                if ns_stats:
                    stats['unified_cache_stats'] = ns_stats
            except Exception as e:
                logger.debug(f"获取统一缓存统计失败: {e}")

        return stats

    def _do_dispose(self) -> None:
        """清理缓存资源"""
        self.clear_cache()
        super()._do_dispose()
