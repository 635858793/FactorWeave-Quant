"""
增强服务容器模块

提供生命周期感知的依赖注入容器，支持服务健康监控和重复初始化防护。
"""

import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, Set
from dataclasses import dataclass, field
from collections import defaultdict
from loguru import logger

from .service_container import ServiceContainer, ServiceScope
from .service_registry import ServiceRegistry, ServiceInfo
from ..services.base_service import BaseService
from ..events import EventBus, get_event_bus


T = TypeVar('T')


class ServiceStatus(Enum):
    """服务状态枚举"""
    UNKNOWN = "unknown"
    REGISTERING = "registering"
    REGISTERED = "registered"
    INITIALIZING = "initializing"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISPOSED = "disposed"


@dataclass
class ServiceHealth:
    """服务健康状态"""
    service_name: str
    service_type: Type
    status: ServiceStatus
    last_check: datetime
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    initialization_time: Optional[float] = None
    initialization_count: int = 0
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ServiceLifecycleEvent:
    """服务生命周期事件"""
    service_name: str
    service_type: Type
    event_type: str  # registering, registered, initializing, initialized, failed, disposed
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)


class EnhancedServiceContainer(ServiceContainer):
    """
    增强服务容器

    提供生命周期感知、健康监控和重复初始化防护的依赖注入容器。
    """

    def __init__(self, registry: Optional[ServiceRegistry] = None, event_bus: Optional[EventBus] = None):
        """
        初始化增强服务容器

        Args:
            registry: 服务注册表
            event_bus: 事件总线
        """
        super().__init__(registry)
        # HVD-241-P1-B: event_bus or → is not None (EventBus __len__ falsy 陷阱, R240-P0-007)
        self._event_bus = event_bus if event_bus is not None else get_event_bus()

        # 健康监控相关
        self._service_health: Dict[Type, ServiceHealth] = {}
        self._health_lock = threading.RLock()

        # 初始化跟踪
        self._initialization_order: List[Type] = []
        self._initialization_times: Dict[Type, float] = {}
        self._duplicate_attempts: Dict[Type, int] = defaultdict(int)

        # 依赖关系图
        self._dependencies: Dict[Type, Set[Type]] = defaultdict(set)
        self._dependents: Dict[Type, Set[Type]] = defaultdict(set)

        # 生命周期事件
        self._lifecycle_events: List[ServiceLifecycleEvent] = []
        self._lifecycle_lock = threading.RLock()

        logger.info("Enhanced service container initialized with lifecycle management")

    def register(self,
                 service_type: Type[T],
                 implementation: Union[Type[T], Callable[..., T], T] = None,
                 scope: ServiceScope = ServiceScope.SINGLETON,
                 name: str = "",
                 dependencies: Optional[List[Type]] = None,
                 **kwargs) -> 'EnhancedServiceContainer':
        """
        注册服务（增强版）

        Args:
            service_type: 服务类型
            implementation: 服务实现
            scope: 服务作用域
            name: 服务名称
            dependencies: 服务依赖列表
            **kwargs: 其他参数
        """
        with self._health_lock:
            # 检查是否已注册
            if self._registry.is_registered(service_type):
                self._duplicate_attempts[service_type] += 1
                logger.warning(
                    f"Service {service_type.__name__} already registered. "
                    f"Duplicate attempt #{self._duplicate_attempts[service_type]}"
                )
                return self

            # 记录注册事件
            self._record_lifecycle_event(
                service_type, "registering",
                {"implementation": str(implementation), "scope": scope.value}
            )

            # 初始化健康状态
            self._service_health[service_type] = ServiceHealth(
                service_name=name or service_type.__name__,
                service_type=service_type,
                status=ServiceStatus.REGISTERING,
                last_check=datetime.now(),
                dependencies=[dep.__name__ for dep in (dependencies or [])]
            )

            # 注册依赖关系
            if dependencies:
                self._dependencies[service_type].update(dependencies)
                for dep in dependencies:
                    self._dependents[dep].add(service_type)

            # 调用父类注册方法
            super().register(service_type, implementation, scope, name, **kwargs)

            # 更新状态
            self._service_health[service_type].status = ServiceStatus.REGISTERED
            self._record_lifecycle_event(service_type, "registered")

            logger.info(f"Service {service_type.__name__} registered successfully")

        return self

    def resolve(self, service_type: Type[T], scope_id: str = None) -> T:
        """
        解析服务（增强版）

        Args:
            service_type: 服务类型
            scope_id: 作用域ID

        Returns:
            服务实例
        """
        start_time = time.time()

        try:
            with self._health_lock:
                # 检查是否已注册
                if not self._registry.is_registered(service_type):
                    error_msg = f"Service {service_type.__name__} is not registered"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                # 更新健康状态
                if service_type in self._service_health:
                    self._service_health[service_type].status = ServiceStatus.INITIALIZING
                    self._service_health[service_type].initialization_count += 1
                    self._record_lifecycle_event(service_type, "initializing")

                # 检查循环依赖
                self._check_circular_dependencies(service_type)

                # 解析服务
                instance = super().resolve(service_type)

                # 记录初始化时间
                initialization_time = time.time() - start_time
                self._initialization_times[service_type] = initialization_time

                # 更新健康状态
                if service_type in self._service_health:
                    health = self._service_health[service_type]
                    health.status = ServiceStatus.HEALTHY
                    health.last_check = datetime.now()
                    health.initialization_time = initialization_time
                    health.metrics.update({
                        'initialization_time_ms': initialization_time * 1000,
                        'initialization_count': health.initialization_count
                    })

                # 记录初始化顺序
                if service_type not in self._initialization_order:
                    self._initialization_order.append(service_type)

                self._record_lifecycle_event(
                    service_type, "initialized",
                    {"initialization_time_ms": initialization_time * 1000}
                )

                logger.info(
                    f"Service {service_type.__name__} initialized successfully "
                    f"in {initialization_time*1000:.2f}ms"
                )

                return instance

        except Exception as e:
            # 记录失败状态
            if service_type in self._service_health:
                self._service_health[service_type].status = ServiceStatus.FAILED
                self._service_health[service_type].error_message = str(e)
                self._service_health[service_type].last_check = datetime.now()

            self._record_lifecycle_event(
                service_type, "failed",
                {"error": str(e), "initialization_time_ms": (time.time() - start_time) * 1000}
            )

            logger.error(f"Service {service_type.__name__} initialization failed: {e}")
            raise

    def _check_circular_dependencies(self, service_type: Type, visited: Optional[Set[Type]] = None) -> None:
        """
        检查循环依赖

        Args:
            service_type: 要检查的服务类型
            visited: 已访问的服务类型集合
        """
        if visited is None:
            visited = set()

        if service_type in visited:
            cycle_path = " -> ".join([t.__name__ for t in visited]) + f" -> {service_type.__name__}"
            error_msg = f"Circular dependency detected: {cycle_path}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        visited.add(service_type)

        for dependency in self._dependencies.get(service_type, set()):
            self._check_circular_dependencies(dependency, visited)

        visited.discard(service_type)

    def get_service_health(self, service_type: Optional[Type] = None) -> Union[ServiceHealth, Dict[Type, ServiceHealth]]:
        """
        获取服务健康状态

        Args:
            service_type: 服务类型，为None时返回所有服务健康状态

        Returns:
            服务健康状态或所有服务健康状态字典
        """
        with self._health_lock:
            if service_type:
                return self._service_health.get(service_type)
            return self._service_health.copy()

    def get_initialization_order(self) -> List[Type]:
        """获取服务初始化顺序"""
        return self._initialization_order.copy()

    def get_initialization_times(self) -> Dict[Type, float]:
        """获取服务初始化时间"""
        return self._initialization_times.copy()

    def get_dependency_graph(self) -> Dict[str, Any]:
        """
        获取依赖关系图

        Returns:
            依赖关系图数据
        """
        return {
            "dependencies": {
                service_type.__name__: [dep.__name__ for dep in deps]
                for service_type, deps in self._dependencies.items()
            },
            "dependents": {
                service_type.__name__: [dep.__name__ for dep in deps]
                for service_type, deps in self._dependents.items()
            }
        }

    def get_lifecycle_events(self, service_type: Optional[Type] = None, limit: int = 100) -> List[ServiceLifecycleEvent]:
        """
        获取生命周期事件

        Args:
            service_type: 服务类型，为None时返回所有事件
            limit: 返回事件数量限制

        Returns:
            生命周期事件列表
        """
        with self._lifecycle_lock:
            events = self._lifecycle_events
            if service_type:
                events = [e for e in events if e.service_type == service_type]

            # 按时间倒序返回最新的事件
            return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]

    def _record_lifecycle_event(self, service_type: Type, event_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        记录生命周期事件

        Args:
            service_type: 服务类型
            event_type: 事件类型
            details: 事件详情
        """
        with self._lifecycle_lock:
            event = ServiceLifecycleEvent(
                service_name=service_type.__name__,
                service_type=service_type,
                event_type=event_type,
                timestamp=datetime.now(),
                details=details or {}
            )
            self._lifecycle_events.append(event)

            # 限制事件数量，避免内存泄漏
            if len(self._lifecycle_events) > 1000:
                self._lifecycle_events = self._lifecycle_events[-500:]

    def perform_health_check(self) -> Dict[str, Any]:
        """
        执行健康检查

        Returns:
            健康检查报告
        """
        with self._health_lock:
            now = datetime.now()
            healthy_count = 0
            degraded_count = 0
            failed_count = 0
            total_count = len(self._service_health)

            service_statuses = {}

            for service_type, health in self._service_health.items():
                # 更新最后检查时间
                health.last_check = now

                # 统计状态
                if health.status == ServiceStatus.HEALTHY:
                    healthy_count += 1
                elif health.status == ServiceStatus.DEGRADED:
                    degraded_count += 1
                elif health.status == ServiceStatus.FAILED:
                    failed_count += 1

                service_statuses[service_type.__name__] = {
                    "status": health.status.value,
                    "initialization_time_ms": health.initialization_time * 1000 if health.initialization_time else None,
                    "initialization_count": health.initialization_count,
                    "last_check": health.last_check.isoformat(),
                    "error_message": health.error_message,
                    "dependencies": health.dependencies
                }

            report = {
                "timestamp": now.isoformat(),
                "overall_status": "healthy" if failed_count == 0 and degraded_count == 0 else "degraded" if failed_count == 0 else "failed",
                "summary": {
                    "total": total_count,
                    "healthy": healthy_count,
                    "degraded": degraded_count,
                    "failed": failed_count
                },
                "services": service_statuses,
                "initialization_order": [t.__name__ for t in self._initialization_order],
                "duplicate_attempts": {
                    t.__name__: count for t, count in self._duplicate_attempts.items()
                }
            }

            return report

    def dispose(self) -> None:
        """释放服务容器"""
        with self._health_lock:
            # 按依赖关系逆序释放服务
            disposal_order = self._calculate_disposal_order()

            for service_type in disposal_order:
                try:
                    if service_type in self._instances:
                        instance = self._instances[service_type]
                        if hasattr(instance, 'dispose') and callable(instance.dispose):
                            instance.dispose()

                        # 更新健康状态
                        if service_type in self._service_health:
                            self._service_health[service_type].status = ServiceStatus.DISPOSED

                        self._record_lifecycle_event(service_type, "disposed")

                except Exception as e:
                    logger.error(f"Error disposing service {service_type.__name__}: {e}")

            super().dispose()
            logger.info("Enhanced service container disposed")

    def _calculate_disposal_order(self) -> List[Type]:
        """
        计算服务释放顺序（依赖关系逆序）

        Returns:
            服务释放顺序列表
        """
        disposal_order = []
        remaining = set(self._initialization_order)
        max_iterations = len(remaining) * 2

        while remaining and max_iterations > 0:
            for service_type in list(remaining):
                dependents = self._dependents.get(service_type, set())
                if not dependents.intersection(remaining):
                    disposal_order.append(service_type)
                    remaining.remove(service_type)
                    break
            else:
                logger.error(
                    f"Disposal order calculation exceeded max iterations, "
                    f"remaining services with circular dependencies: "
                    f"{[t.__name__ for t in remaining]}"
                )
                disposal_order.extend(remaining)
                break
            max_iterations -= 1

        return disposal_order


# 全局增强服务容器实例
_enhanced_container: Optional[EnhancedServiceContainer] = None
_container_lock = threading.Lock()


def get_enhanced_container() -> EnhancedServiceContainer:
    """获取全局增强服务容器实例"""
    global _enhanced_container
    if _enhanced_container is None:
        with _container_lock:
            if _enhanced_container is None:
                _enhanced_container = EnhancedServiceContainer()
    return _enhanced_container


def set_enhanced_container(container: EnhancedServiceContainer) -> None:
    """设置全局增强服务容器实例"""
    global _enhanced_container
    with _container_lock:
        _enhanced_container = container
