"""
服务注册表模块

管理服务的注册信息、生命周期和依赖关系。
"""

from loguru import logger
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union
import threading


class ServiceScope(Enum):
    """
    服务作用域枚举
    """
    SINGLETON = "singleton"  # 单例模式
    TRANSIENT = "transient"  # 每次请求都创建新实例
    SCOPED = "scoped"       # 在特定作用域内是单例

@dataclass
class ServiceInfo:
    """
    服务信息

    包含服务的注册信息和元数据。
    """
    service_type: Type
    implementation: Union[Type, Callable, Any]
    scope: ServiceScope = ServiceScope.SINGLETON
    dependencies: List[Type] = field(default_factory=list)
    name: str = ""
    description: str = ""
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    factory: Optional[Callable] = None
    instance: Optional[Any] = None
    initialized: bool = False

    def __post_init__(self):
        """初始化后处理"""
        if not self.name:
            self.name = self.service_type.__name__

class ServiceRegistry:
    """
    服务注册表

    负责管理服务的注册、查找和生命周期。
    """

    def __init__(self):
        """初始化服务注册表"""
        self._services: Dict[Type, ServiceInfo] = {}
        self._named_services: Dict[str, ServiceInfo] = {}
        self._lock = threading.RLock()
        self._dependency_graph: Dict[Type, Set[Type]] = {}

    def register(self,
                 service_type: Type,
                 implementation: Union[Type, Callable, Any] = None,
                 scope: ServiceScope = ServiceScope.SINGLETON,
                 name: str = "",
                 description: str = "",
                 tags: Optional[Set[str]] = None,
                 metadata: Optional[Dict[str, Any]] = None,
                 factory: Optional[Callable] = None) -> 'ServiceRegistry':
        """
        注册服务

        Args:
            service_type: 服务类型（接口或抽象类）
            implementation: 服务实现（类、工厂函数或实例）
            scope: 服务作用域
            name: 服务名称
            description: 服务描述
            tags: 服务标签
            metadata: 服务元数据
            factory: 服务工厂函数

        Returns:
            服务注册表实例（支持链式调用）
        """
        with self._lock:
            # 如果没有提供实现，使用服务类型本身
            if implementation is None:
                implementation = service_type

            # 分析依赖关系
            dependencies = self._analyze_dependencies(implementation)

            service_info = ServiceInfo(
                service_type=service_type,
                implementation=implementation,
                scope=scope,
                dependencies=dependencies,
                name=name or service_type.__name__,
                description=description,
                tags=tags or set(),
                metadata=metadata or {},
                factory=factory
            )

            # 注册到类型映射
            self._services[service_type] = service_info

            # 如果有名称，注册到名称映射
            if service_info.name:
                self._named_services[service_info.name] = service_info

            # 更新依赖图
            self._dependency_graph[service_type] = set(dependencies)

            logger.debug(
                f"Registered service {service_type.__name__} with scope {scope.value}")

            return self

    def register_instance(self,
                          service_type: Type,
                          instance: Any,
                          name: str = "",
                          description: str = "",
                          tags: Optional[Set[str]] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> 'ServiceRegistry':
        """
        注册服务实例

        Args:
            service_type: 服务类型
            instance: 服务实例
            name: 服务名称
            description: 服务描述
            tags: 服务标签
            metadata: 服务元数据

        Returns:
            服务注册表实例（支持链式调用）
        """
        with self._lock:
            service_info = ServiceInfo(
                service_type=service_type,
                implementation=instance,
                scope=ServiceScope.SINGLETON,
                name=name or service_type.__name__,
                description=description,
                tags=tags or set(),
                metadata=metadata or {},
                instance=instance,
                initialized=True
            )

            self._services[service_type] = service_info

            if service_info.name:
                self._named_services[service_info.name] = service_info

            logger.debug(
                f"Registered service instance {service_type.__name__}")

            return self

    def register_factory(self,
                         service_type: Type,
                         factory: Callable,
                         scope: ServiceScope = ServiceScope.SINGLETON,
                         name: str = "",
                         description: str = "",
                         tags: Optional[Set[str]] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> 'ServiceRegistry':
        """
        注册服务工厂

        Args:
            service_type: 服务类型
            factory: 工厂函数
            scope: 服务作用域
            name: 服务名称
            description: 服务描述
            tags: 服务标签
            metadata: 服务元数据

        Returns:
            服务注册表实例（支持链式调用）
        """
        return self.register(
            service_type=service_type,
            implementation=factory,
            scope=scope,
            name=name,
            description=description,
            tags=tags,
            metadata=metadata,
            factory=factory
        )

    def get_service_info(self, service_type: Type) -> Optional[ServiceInfo]:
        """
        获取服务信息

        Args:
            service_type: 服务类型

        Returns:
            服务信息，如果未找到则返回None
        """
        with self._lock:
            return self._services.get(service_type)

    def get_service_info_by_name(self, name: str) -> Optional[ServiceInfo]:
        """
        根据名称获取服务信息

        Args:
            name: 服务名称

        Returns:
            服务信息，如果未找到则返回None
        """
        with self._lock:
            return self._named_services.get(name)

    def is_registered(self, service_type: Type) -> bool:
        """
        检查服务是否已注册

        Args:
            service_type: 服务类型

        Returns:
            是否已注册
        """
        with self._lock:
            return service_type in self._services

    def unregister(self, service_type: Type) -> bool:
        """
        取消注册服务

        Args:
            service_type: 服务类型

        Returns:
            是否成功取消注册
        """
        with self._lock:
            if service_type in self._services:
                service_info = self._services[service_type]

                # 从类型映射中移除
                del self._services[service_type]

                # 从名称映射中移除
                if service_info.name in self._named_services:
                    del self._named_services[service_info.name]

                # 从依赖图中移除
                if service_type in self._dependency_graph:
                    del self._dependency_graph[service_type]

                logger.debug(f"Unregistered service {service_type.__name__}")
                return True

            return False

    def get_all_services(self) -> List[ServiceInfo]:
        """
        获取所有已注册的服务

        Returns:
            服务信息列表
        """
        with self._lock:
            return list(self._services.values())

    def get_services_by_tag(self, tag: str) -> List[ServiceInfo]:
        """
        根据标签获取服务

        Args:
            tag: 标签名称

        Returns:
            匹配的服务信息列表
        """
        with self._lock:
            return [info for info in self._services.values() if tag in info.tags]

    def get_dependency_order(self, service_type: Type) -> List[Type]:
        """
        获取服务的依赖顺序

        Args:
            service_type: 服务类型

        Returns:
            依赖顺序列表（拓扑排序）
        """
        with self._lock:
            return self._topological_sort(service_type)

    def check_circular_dependencies(self) -> List[List[Type]]:
        """
        检查循环依赖

        Returns:
            循环依赖的列表
        """
        with self._lock:
            cycles = []
            visited = set()
            rec_stack = set()

            def dfs(node: Type, path: List[Type]):
                visited.add(node)
                rec_stack.add(node)
                path.append(node)

                for neighbor in self._dependency_graph.get(node, []):
                    if neighbor not in visited:
                        dfs(neighbor, path.copy())
                    elif neighbor in rec_stack:
                        # 找到循环
                        cycle_start = path.index(neighbor)
                        cycle = path[cycle_start:] + [neighbor]
                        cycles.append(cycle)

                rec_stack.remove(node)

            for service_type in self._dependency_graph:
                if service_type not in visited:
                    dfs(service_type, [])

            return cycles

    def clear(self) -> None:
        """清除所有注册的服务"""
        with self._lock:
            self._services.clear()
            self._named_services.clear()
            self._dependency_graph.clear()
            logger.debug("Cleared all registered services")

    def _analyze_dependencies(self, implementation: Union[Type, Callable, Any]) -> List[Type]:
        """
        分析依赖关系

        Args:
            implementation: 服务实现

        Returns:
            依赖类型列表
        """
        dependencies = []

        if hasattr(implementation, '__init__'):
            import inspect
            sig = inspect.signature(implementation.__init__)
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                if param.annotation != inspect.Parameter.empty:
                    # 忽略基本类型和内置类型
                    if self._is_service_type(param.annotation):
                        dependencies.append(param.annotation)

        return dependencies

    def _is_service_type(self, annotation: Type) -> bool:
        """
        判断是否为服务类型（排除基本类型）

        Args:
            annotation: 类型注解

        Returns:
            是否为服务类型
        """
        # 基本类型列表
        basic_types = {
            str, int, float, bool, bytes,
            list, dict, tuple, set, frozenset,
            type(None)
        }

        # 检查是否为基本类型
        if annotation in basic_types:
            return False

        # 检查是否为泛型类型（如List[str], Dict[str, int]等）
        if hasattr(annotation, '__origin__'):
            return False

        # 检查是否为字符串类型注解
        if isinstance(annotation, str):
            return False

        # 其他情况认为是服务类型
        return True

    def _topological_sort(self, start_type: Type) -> List[Type]:
        """
        拓扑排序获取依赖顺序

        Args:
            start_type: 起始服务类型

        Returns:
            排序后的依赖列表
        """
        visited = set()
        result = []

        def dfs(node: Type):
            if node in visited:
                return
            visited.add(node)

            for dependency in self._dependency_graph.get(node, []):
                dfs(dependency)

            result.append(node)

        dfs(start_type)
        return result[:-1]  # 排除起始类型本身

    def __len__(self) -> int:
        """返回注册的服务数量"""
        return len(self._services)

    def __contains__(self, service_type: Type) -> bool:
        """检查服务是否已注册"""
        return self.is_registered(service_type)

    def __str__(self) -> str:
        return f"ServiceRegistry(services={len(self._services)})"
