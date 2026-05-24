"""
统一服务容器模块

为架构精简重构提供增强的服务容器，支持15个核心服务的统一管理。
专为从164个Manager精简到15个Service设计。
"""

import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar, Set, Union
from dataclasses import dataclass
from loguru import logger

from .service_container import ServiceContainer
from .service_registry import ServiceRegistry, ServiceScope


T = TypeVar('T')


class ServiceStatus(Enum):
    """服务状态枚举"""
    UNREGISTERED = "unregistered"
    REGISTERED = "registered"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DISPOSED = "disposed"


@dataclass
class ServiceHealth:
    """服务健康状态"""
    service_name: str
    status: ServiceStatus
    last_check: datetime
    error_count: int = 0
    last_error: Optional[str] = None
    startup_time: Optional[float] = None
    memory_usage: Optional[float] = None


@dataclass
class ServiceDependency:
    """服务依赖关系"""
    service_type: Type
    depends_on: List[Type]
    priority: int = 0  # 启动优先级，数字越小越早启动


class UnifiedServiceContainer(ServiceContainer):
    """
    统一服务容器

    为架构精简重构提供增强功能：
    1. 15个核心服务的生命周期管理
    2. 服务健康监控
    3. 依赖关系解析和启动顺序管理
    4. 防止重复初始化
    5. 服务性能监控
    """

    def __init__(self, registry: Optional[ServiceRegistry] = None):
        """初始化统一服务容器"""
        super().__init__(registry)

        # 服务健康监控
        self._service_health: Dict[Type, ServiceHealth] = {}
        self._health_lock = threading.RLock()

        # 服务依赖管理
        self._dependencies: Dict[Type, ServiceDependency] = {}
        self._startup_order: List[Type] = []
        self._dependency_lock = threading.RLock()

        # 生命周期管理
        self._initialization_status: Dict[Type, ServiceStatus] = {}
        self._initialization_lock = threading.RLock()
        self._startup_times: Dict[Type, float] = {}

        # 防止重复操作
        self._initializing_services: Set[Type] = set()
        self._initialized_services: Set[Type] = set()

        # 名称到类型的反向索引（O(1)查询）
        self._name_to_type: Dict[str, Type] = {}

        logger.info("UnifiedServiceContainer initialized for architecture simplification")

    def register_core_service(self,
                              service_type: Type[T],
                              implementation: Type[T] = None,
                              dependencies: List[Union[Type, str]] = None,
                              priority: int = 0,
                              **kwargs) -> 'UnifiedServiceContainer':
        """
        注册核心服务（15个核心服务专用）

        Args:
            service_type: 服务类型
            implementation: 服务实现类
            dependencies: 依赖的其他服务类型列表（可以是类型或类型名称字符串）
            priority: 启动优先级（数字越小越早启动）
            **kwargs: 其他参数
        """
        # 注册到基础容器
        self.register(
            service_type=service_type,
            implementation=implementation or service_type,
            scope=ServiceScope.SINGLETON,
            **kwargs
        )

        # 转换字符串依赖为类型对象
        resolved_dependencies = []
        if dependencies:
            for dep in dependencies:
                if isinstance(dep, str):
                    # 根据字符串名称查找已注册的服务类型
                    dep_type = self._resolve_service_type_by_name(dep)
                    if dep_type:
                        resolved_dependencies.append(dep_type)
                    else:
                        logger.warning(f"Cannot resolve dependency '{dep}' for service {service_type.__name__}")
                else:
                    resolved_dependencies.append(dep)

        # 注册依赖关系
        with self._dependency_lock:
            self._dependencies[service_type] = ServiceDependency(
                service_type=service_type,
                depends_on=resolved_dependencies,
                priority=priority
            )

        # 初始化健康状态
        with self._health_lock:
            self._service_health[service_type] = ServiceHealth(
                service_name=service_type.__name__,
                status=ServiceStatus.REGISTERED,
                last_check=datetime.now()
            )

        # 更新状态
        with self._initialization_lock:
            self._initialization_status[service_type] = ServiceStatus.REGISTERED

        # 构建名称反向索引（O(1)查询）
        self._name_to_type[service_type.__name__] = service_type

        logger.info(f"Core service {service_type.__name__} registered with priority {priority}")
        return self

    def _resolve_service_type_by_name(self, service_name: str) -> Optional[Type]:
        """根据服务名称解析服务类型（O(1)反向索引查询）"""
        return self._name_to_type.get(service_name)

    def resolve_with_lifecycle(self, service_type: Type[T]) -> T:
        """
        解析服务并管理生命周期

        Args:
            service_type: 服务类型

        Returns:
            服务实例
        """
        start_time = time.time()

        try:
            # 检查是否正在初始化（防止循环依赖）
            if service_type in self._initializing_services:
                raise RuntimeError(f"Circular dependency detected for service {service_type.__name__}")

            # 检查是否已初始化
            if service_type in self._initialized_services:
                return self.resolve(service_type)

            # 标记为正在初始化
            with self._initialization_lock:
                self._initializing_services.add(service_type)
                self._initialization_status[service_type] = ServiceStatus.INITIALIZING

            # 更新健康状态
            self._update_service_status(service_type, ServiceStatus.INITIALIZING)

            # 首先解析依赖
            self._resolve_dependencies(service_type)

            # 解析服务
            service = self.resolve(service_type)

            # 初始化服务
            if hasattr(service, 'initialize') and callable(service.initialize):
                logger.info(f"Initializing service {service_type.__name__}")
                service.initialize()

            # 记录启动时间
            startup_time = time.time() - start_time
            self._startup_times[service_type] = startup_time

            # 更新状态
            with self._initialization_lock:
                self._initializing_services.discard(service_type)
                self._initialized_services.add(service_type)
                self._initialization_status[service_type] = ServiceStatus.RUNNING

            # 更新健康状态
            self._update_service_health(service_type, ServiceStatus.RUNNING, startup_time)

            logger.info(f"Service {service_type.__name__} initialized successfully in {startup_time:.3f}s")
            return service

        except Exception as e:
            # 处理错误
            with self._initialization_lock:
                self._initializing_services.discard(service_type)
                self._initialization_status[service_type] = ServiceStatus.ERROR

            self._update_service_error(service_type, str(e))
            logger.error(f"Failed to initialize service {service_type.__name__}: {e}")
            raise

    def _resolve_dependencies(self, service_type: Type) -> None:
        """解析服务依赖"""
        if service_type not in self._dependencies:
            return

        dependency = self._dependencies[service_type]
        for dep_type in dependency.depends_on:
            if dep_type not in self._initialized_services:
                logger.info(f"Resolving dependency {dep_type.__name__} for {service_type.__name__}")
                self.resolve_with_lifecycle(dep_type)

    def _update_service_status(self, service_type: Type, status: ServiceStatus) -> None:
        """更新服务状态"""
        with self._health_lock:
            if service_type in self._service_health:
                self._service_health[service_type].status = status
                self._service_health[service_type].last_check = datetime.now()

    def _update_service_health(self, service_type: Type, status: ServiceStatus, startup_time: float = None) -> None:
        """更新服务健康状态"""
        with self._health_lock:
            if service_type in self._service_health:
                health = self._service_health[service_type]
                health.status = status
                health.last_check = datetime.now()
                if startup_time:
                    health.startup_time = startup_time

    def _update_service_error(self, service_type: Type, error_msg: str) -> None:
        """更新服务错误状态"""
        with self._health_lock:
            if service_type in self._service_health:
                health = self._service_health[service_type]
                health.status = ServiceStatus.ERROR
                health.error_count += 1
                health.last_error = error_msg
                health.last_check = datetime.now()

    def get_startup_order(self) -> List[Type]:
        """获取服务启动顺序（基于依赖关系和优先级）"""
        with self._dependency_lock:
            if self._startup_order:
                return self._startup_order.copy()

            # 计算启动顺序
            services = list(self._dependencies.keys())
            ordered = []
            processed = set()

            def add_service(service_type: Type):
                if service_type in processed:
                    return

                # 先添加依赖
                if service_type in self._dependencies:
                    for dep in self._dependencies[service_type].depends_on:
                        add_service(dep)

                if service_type not in processed:
                    ordered.append(service_type)
                    processed.add(service_type)

            # 按优先级排序后添加
            services.sort(key=lambda s: self._dependencies.get(s, ServiceDependency(s, [])).priority)
            for service in services:
                add_service(service)

            self._startup_order = ordered
            return ordered.copy()

    def start_all_services(self) -> Dict[Type, bool]:
        """启动所有注册的核心服务"""
        logger.info("Starting all core services for architecture simplification")
        startup_order = self.get_startup_order()
        results = {}

        for service_type in startup_order:
            try:
                self.resolve_with_lifecycle(service_type)
                results[service_type] = True
                logger.info(f"✓ {service_type.__name__} started successfully")
            except Exception as e:
                results[service_type] = False
                logger.error(f"✗ {service_type.__name__} failed to start: {e}")

        # 生成启动报告
        self._generate_startup_report(results)
        return results

    def _generate_startup_report(self, results: Dict[Type, bool]) -> None:
        """生成启动报告"""
        total = len(results)
        successful = sum(1 for success in results.values() if success)
        failed = total - successful

        logger.info("=" * 60)
        logger.info("ARCHITECTURE SIMPLIFICATION - SERVICE STARTUP REPORT")
        logger.info("=" * 60)
        logger.info(f"Total Core Services: {total}")
        logger.info(f"Successfully Started: {successful}")
        logger.info(f"Failed to Start: {failed}")

        if failed > 0:
            logger.warning("Failed services:")
            for service_type, success in results.items():
                if not success:
                    health = self._service_health.get(service_type)
                    error_msg = health.last_error if health else "Unknown error"
                    logger.warning(f"  - {service_type.__name__}: {error_msg}")

        # 显示启动时间
        if self._startup_times:
            logger.info("Service startup times:")
            for service_type, startup_time in self._startup_times.items():
                logger.info(f"  - {service_type.__name__}: {startup_time:.3f}s")

        logger.info("=" * 60)

    def get_service_health_report(self) -> Dict[str, Any]:
        """获取服务健康报告"""
        with self._health_lock:
            report = {
                "timestamp": datetime.now().isoformat(),
                "total_services": len(self._service_health),
                "services": {}
            }

            status_counts = {}
            for health in self._service_health.values():
                status = health.status.value
                status_counts[status] = status_counts.get(status, 0) + 1

                report["services"][health.service_name] = {
                    "status": status,
                    "last_check": health.last_check.isoformat(),
                    "error_count": health.error_count,
                    "last_error": health.last_error,
                    "startup_time": health.startup_time
                }

            report["status_summary"] = status_counts
            return report

    def shutdown_all_services(self) -> None:
        """关闭所有服务"""
        logger.info("Shutting down all core services")

        # 按相反顺序关闭服务
        shutdown_order = list(reversed(self.get_startup_order()))

        for service_type in shutdown_order:
            try:
                if service_type in self._initialized_services:
                    service = self.resolve(service_type)
                    if hasattr(service, 'dispose') and callable(service.dispose):
                        logger.info(f"Disposing service {service_type.__name__}")
                        service.dispose()

                    self._initialized_services.discard(service_type)
                    self._update_service_status(service_type, ServiceStatus.DISPOSED)
                    logger.info(f"✓ {service_type.__name__} disposed successfully")
            except Exception as e:
                logger.error(f"✗ Failed to dispose {service_type.__name__}: {e}")

        logger.info("All core services shutdown completed")

    def is_service_initialized(self, service_type: Type) -> bool:
        """检查服务是否已初始化"""
        return service_type in self._initialized_services

    def get_initialization_status(self, service_type: Type) -> ServiceStatus:
        """获取服务初始化状态"""
        return self._initialization_status.get(service_type, ServiceStatus.UNREGISTERED)


# 全局统一服务容器实例
_unified_container: Optional[UnifiedServiceContainer] = None
_container_lock = threading.Lock()


def get_unified_container() -> UnifiedServiceContainer:
    from .service_container import get_service_container, set_service_container

    container = get_service_container()
    if isinstance(container, UnifiedServiceContainer):
        return container

    global _unified_container

    if _unified_container is None:
        with _container_lock:
            if _unified_container is None:
                _unified_container = UnifiedServiceContainer()
                set_service_container(_unified_container)
                logger.info("Global UnifiedServiceContainer created and set as primary container")

    return _unified_container


def reset_unified_container() -> None:
    global _unified_container

    with _container_lock:
        if _unified_container:
            _unified_container.shutdown_all_services()
        _unified_container = None
        logger.info("Global UnifiedServiceContainer reset")
