"""
服务依赖解析器

实现服务依赖关系管理和循环依赖检测
"""

import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type
from loguru import logger

from .base_service import BaseService
from ..containers import ServiceContainer, get_service_container
from ..events import EventBus, get_event_bus


class DependencyType(Enum):
    """依赖类型"""
    REQUIRED = "required"
    OPTIONAL = "optional"
    WEAK = "weak"


class ServiceState(Enum):
    """服务状态"""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    FAILED = "failed"


@dataclass
class ServiceNode:
    """服务节点"""
    service_type: Type
    service_name: str
    dependencies: Set[Type]
    dependents: Set[Type]
    state: ServiceState = ServiceState.UNINITIALIZED
    initialization_order: int = -1


@dataclass
class CircularDependency:
    """循环依赖"""
    cycle_path: List[Type]
    severity: str = "ERROR"
    suggestion: str = ""


class DependencyResolver:
    """服务依赖解析器"""

    def __init__(self,
                 service_container: Optional[ServiceContainer] = None,
                 event_bus: Optional[EventBus] = None):
        """初始化依赖解析器"""
        self._service_container = service_container or get_service_container()
        # HVD-241-P1-B: event_bus or → is not None (EventBus __len__ falsy 陷阱, R240-P0-007)
        self._event_bus = event_bus if event_bus is not None else get_event_bus()

        self._dependency_graph: Dict[Type, ServiceNode] = {}
        self._lock = threading.RLock()

        logger.info("Dependency resolver initialized")

    def register_service(self,
                         service_type: Type,
                         dependencies: Optional[List[Type]] = None,
                         service_name: Optional[str] = None) -> None:
        """注册服务及其依赖"""
        with self._lock:
            if service_type not in self._dependency_graph:
                self._dependency_graph[service_type] = ServiceNode(
                    service_type=service_type,
                    service_name=service_name or service_type.__name__,
                    dependencies=set(),
                    dependents=set()
                )

            if dependencies:
                for dep_type in dependencies:
                    self.add_dependency(service_type, dep_type)

            logger.debug(f"Service registered: {service_type.__name__}")

    def add_dependency(self, from_service: Type, to_service: Type) -> None:
        """添加服务依赖关系"""
        with self._lock:
            # 确保服务节点存在
            if from_service not in self._dependency_graph:
                self._dependency_graph[from_service] = ServiceNode(
                    service_type=from_service,
                    service_name=from_service.__name__,
                    dependencies=set(),
                    dependents=set()
                )

            if to_service not in self._dependency_graph:
                self._dependency_graph[to_service] = ServiceNode(
                    service_type=to_service,
                    service_name=to_service.__name__,
                    dependencies=set(),
                    dependents=set()
                )

            # 添加依赖关系
            self._dependency_graph[from_service].dependencies.add(to_service)
            self._dependency_graph[to_service].dependents.add(from_service)

            logger.debug(f"Dependency added: {from_service.__name__} -> {to_service.__name__}")

    def detect_circular_dependencies(self) -> List[CircularDependency]:
        """检测循环依赖"""
        circular_deps = []
        visited = set()
        rec_stack = set()

        def dfs(service_type: Type, path: List[Type]) -> None:
            if service_type in rec_stack:
                # 找到循环依赖
                cycle_start = path.index(service_type)
                cycle_path = path[cycle_start:] + [service_type]

                circular_dep = CircularDependency(
                    cycle_path=cycle_path,
                    severity="ERROR",
                    suggestion=f"Circular dependency: {' -> '.join([s.__name__ for s in cycle_path])}"
                )
                circular_deps.append(circular_dep)
                return

            if service_type in visited:
                return

            visited.add(service_type)
            rec_stack.add(service_type)

            if service_type in self._dependency_graph:
                for dep_service in self._dependency_graph[service_type].dependencies:
                    dfs(dep_service, path + [service_type])

            rec_stack.remove(service_type)

        for service_type in self._dependency_graph:
            if service_type not in visited:
                dfs(service_type, [])

        return circular_deps

    def get_initialization_order(self) -> List[Type]:
        """获取初始化顺序（拓扑排序）"""
        in_degree = defaultdict(int)

        # 计算入度
        for service_type in self._dependency_graph:
            in_degree[service_type] = len(self._dependency_graph[service_type].dependencies)

            # 初始化队列
        queue = deque([svc for svc in self._dependency_graph if in_degree[svc] == 0])
        order = []

        while queue:
            current = queue.popleft()
            order.append(current)

            if current in self._dependency_graph:
                for dependent in self._dependency_graph[current].dependents:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        # 设置初始化顺序
        for i, service_type in enumerate(order):
            if service_type in self._dependency_graph:
                self._dependency_graph[service_type].initialization_order = i

        return order

    def has_circular_dependencies(self) -> bool:
        """检查是否存在循环依赖"""
        return len(self.detect_circular_dependencies()) > 0

    def get_service_status(self, service_type: Type) -> Dict[str, Any]:
        """获取服务状态"""
        node = self._dependency_graph.get(service_type)
        if not node:
            return {'error': 'Service not found'}

        return {
            'service_name': node.service_name,
            'state': node.state.value,
            'initialization_order': node.initialization_order,
            'dependencies': [svc.__name__ for svc in node.dependencies],
            'dependents': [svc.__name__ for svc in node.dependents]
        }

    def export_dependency_graph(self) -> Dict[str, Any]:
        """导出依赖图"""
        export_data = {
            'metadata': {
                'total_services': len(self._dependency_graph),
                'exported_at': datetime.now().isoformat()
            },
            'services': {},
            'circular_dependencies': []
        }

        # 导出服务信息
        for service_type, node in self._dependency_graph.items():
            export_data['services'][service_type.__name__] = {
                'service_name': node.service_name,
                'state': node.state.value,
                'initialization_order': node.initialization_order,
                'dependencies': [svc.__name__ for svc in node.dependencies],
                'dependents': [svc.__name__ for svc in node.dependents]
            }

        # 导出循环依赖
        circular_deps = self.detect_circular_dependencies()
        for circular_dep in circular_deps:
            export_data['circular_dependencies'].append({
                'cycle_path': [svc.__name__ for svc in circular_dep.cycle_path],
                'severity': circular_dep.severity,
                'suggestion': circular_dep.suggestion
            })

        return export_data


# 全局实例
_dependency_resolver: Optional[DependencyResolver] = None


def get_dependency_resolver() -> DependencyResolver:
    """获取依赖解析器实例"""
    global _dependency_resolver

    if _dependency_resolver is None:
        _dependency_resolver = DependencyResolver()

    return _dependency_resolver
