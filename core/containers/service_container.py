"""
服务容器模块

提供依赖注入容器的实现，负责服务的创建、管理和注入。
"""

import threading
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
from .service_registry import ServiceRegistry, ServiceInfo, ServiceScope
from loguru import logger

# WebGPU相关导入
from core.webgpu import get_webgpu_manager

T = TypeVar('T')


class ServiceContainer:
    """
    服务容器

    依赖注入系统的核心，负责服务的创建、管理和生命周期。
    """

    def __init__(self, registry: Optional[ServiceRegistry] = None):
        """
        初始化服务容器

        Args:
            registry: 服务注册表，如果为None则创建新的
        """
        self._registry = registry or ServiceRegistry()
        self._instances: Dict[Type, Any] = {}
        self._scoped_instances: Dict[str, Dict[Type, Any]] = {}
        self._lock = threading.RLock()
        self._current_scope: Optional[str] = None
        self._resolving: set = set()  # 用于检测循环依赖

    @property
    def registry(self) -> ServiceRegistry:
        """获取服务注册表"""
        return self._registry

    def register(self,
                 service_type: Type[T],
                 implementation: Union[Type[T], Callable[..., T], T] = None,
                 scope: ServiceScope = ServiceScope.SINGLETON,
                 name: str = "",
                 **kwargs) -> 'ServiceContainer':
        """
        注册服务

        Args:
            service_type: 服务类型
            implementation: 服务实现
            scope: 服务作用域
            name: 服务名称
            **kwargs: 其他参数

        Returns:
            服务容器实例（支持链式调用）
        """
        self._registry.register(
            service_type=service_type,
            implementation=implementation,
            scope=scope,
            name=name,
            **kwargs
        )
        return self

    def register_instance(self,
                          service_type: Type[T],
                          instance: T,
                          name: str = "") -> 'ServiceContainer':
        """
        注册服务实例

        Args:
            service_type: 服务类型
            instance: 服务实例
            name: 服务名称

        Returns:
            服务容器实例（支持链式调用）
        """
        with self._lock:
            self._registry.register_instance(service_type, instance, name)
            self._instances[service_type] = instance
        return self

    def register_factory(self,
                         service_type: Type[T],
                         factory: Callable[..., T],
                         scope: ServiceScope = ServiceScope.SINGLETON,
                         name: str = "") -> 'ServiceContainer':
        """
        注册服务工厂

        Args:
            service_type: 服务类型
            factory: 工厂函数
            scope: 服务作用域
            name: 服务名称

        Returns:
            服务容器实例（支持链式调用）
        """
        self._registry.register_factory(service_type, factory, scope, name)
        return self

    def resolve(self, service_type: Type[T]) -> T:
        """
        解析服务

        Args:
            service_type: 服务类型

        Returns:
            服务实例

        Raises:
            ValueError: 如果服务未注册或解析失败
        """
        with self._lock:
            # 检查循环依赖
            if service_type in self._resolving:
                raise ValueError(
                    f"Circular dependency detected for {service_type.__name__}")

            service_info = self._registry.get_service_info(service_type)
            if service_info is None:
                raise ValueError(
                    f"Service {service_type.__name__} is not registered")

            # 根据作用域获取或创建实例
            if service_info.scope == ServiceScope.SINGLETON:
                return self._get_singleton(service_info)
            elif service_info.scope == ServiceScope.SCOPED:
                return self._get_scoped(service_info)
            else:  # TRANSIENT
                return self._create_instance(service_info)

    def resolve_by_name(self, name: str) -> Any:
        """
        根据名称解析服务

        Args:
            name: 服务名称

        Returns:
            服务实例

        Raises:
            ValueError: 如果服务未注册或解析失败
        """
        service_info = self._registry.get_service_info_by_name(name)
        if service_info is None:
            raise ValueError(f"Service with name '{name}' is not registered")

        return self.resolve(service_info.service_type)

    def try_resolve(self, service_type: Type[T]) -> Optional[T]:
        """
        尝试解析服务，失败时返回None

        Args:
            service_type: 服务类型

        Returns:
            服务实例或None
        """
        try:
            return self.resolve(service_type)
        except Exception as e:
            logger.debug(
                f"Failed to resolve service {service_type.__name__}: {e}")
            return None

    def get_service(self, service_name_or_type: Union[str, Type[T]]) -> Optional[T]:
        """
        根据名称或类型获取服务（兼容性方法）

        Args:
            service_name_or_type: 服务名称或服务类型

        Returns:
            服务实例或None
        """
        try:
            if isinstance(service_name_or_type, str):
                return self.resolve_by_name(service_name_or_type)
            else:
                return self.resolve(service_name_or_type)
        except Exception as e:
            logger.debug(f"Failed to get service {service_name_or_type}: {e}")
            return None

    def is_registered(self, service_type: Type) -> bool:
        """
        检查服务是否已注册

        Args:
            service_type: 服务类型

        Returns:
            是否已注册
        """
        return self._registry.is_registered(service_type)

    def create_scope(self, scope_name: str) -> 'ServiceScope':
        """
        创建服务作用域

        Args:
            scope_name: 作用域名称

        Returns:
            服务作用域上下文管理器
        """
        return ServiceScopeContext(self, scope_name)

    def dispose(self) -> None:
        """释放所有资源"""
        with self._lock:
            # 释放单例实例
            for instance in self._instances.values():
                self._dispose_instance(instance)
            self._instances.clear()

            # 释放作用域实例
            for scope_instances in self._scoped_instances.values():
                for instance in scope_instances.values():
                    self._dispose_instance(instance)
            self._scoped_instances.clear()

            logger.debug("Service container disposed")

    def get_all_services(self) -> List[ServiceInfo]:
        """
        获取所有已注册的服务

        Returns:
            服务信息列表
        """
        return self._registry.get_all_services()

    def auto_wire(self, cls: Type[T], *args, **kwargs) -> T:
        """
        自动装配类实例

        根据类的构造函数参数，自动从容器中注入依赖。
        这个功能来自于原始的core/service_container.py实现。

        Args:
            cls: 要实例化的类
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            实例化的对象
        """
        import inspect

        # 获取构造函数的参数
        sig = inspect.signature(cls.__init__)
        params = list(sig.parameters.values())[1:]  # 跳过self参数

        # 尝试从容器中获取依赖
        injected_kwargs = {}
        for param in params:
            if param.name not in kwargs:
                # 尝试按类型解析
                if param.annotation != inspect.Parameter.empty:
                    try:
                        dependency = self.resolve(param.annotation)
                        injected_kwargs[param.name] = dependency
                    except:
                        # 如果按类型解析失败，尝试按名称解析
                        if self._registry.get_service_info_by_name(param.name):
                            injected_kwargs[param.name] = self.resolve_by_name(
                                param.name)

        # 合并参数
        final_kwargs = {**injected_kwargs, **kwargs}

        return cls(*args, **final_kwargs)

    # 兼容旧的API
    def has(self, name: str) -> bool:
        """
        检查是否有服务（兼容旧API）

        Args:
            name: 服务名称

        Returns:
            是否存在服务
        """
        service_info = self._registry.get_service_info_by_name(name)
        return service_info is not None

    def get(self, name: str) -> Any:
        """
        根据名称获取服务（兼容旧API）

        Args:
            name: 服务名称

        Returns:
            服务实例
        """
        return self.resolve_by_name(name)

    def remove(self, name: str) -> bool:
        """
        移除服务（兼容旧API）

        Args:
            name: 服务名称

        Returns:
            是否成功移除
        """
        # 这个功能需要在ServiceRegistry中实现
        # 暂时返回False
        logger.warning(
            f"Remove service '{name}' is not implemented in new architecture")
        return False

    def clear(self) -> None:
        """
        清空所有服务（兼容旧API）
        """
        self.dispose()

    def get_service_names(self) -> List[str]:
        """
        获取所有已注册的服务名称（兼容旧API）

        Returns:
            服务名称列表
        """
        services = self._registry.get_all_services()
        return [s.name for s in services if s.name]

    def initialize_all(self) -> None:
        """
        初始化所有已注册的服务（兼容旧API）
        """
        # 先初始化WebGPU相关服务
        self._register_webgpu_services()
        
        for service_info in self._registry.get_all_services():
            try:
                service = self.resolve(service_info.service_type)
                if service and hasattr(service, 'initialize'):
                    service.initialize()
                    logger.debug(
                        f"Service initialized: {service_info.name or service_info.service_type.__name__}")
            except Exception as e:
                logger.error(
                    f"Failed to initialize service {service_info.name or service_info.service_type.__name__}: {e}")
    
    def _register_webgpu_services(self):
        """注册WebGPU相关服务到业务框架"""
        try:
            # WebGPU管理器服务 - 包含状态监控功能
            from core.webgpu.manager import WebGPUManager
            
            self.register_factory(
                WebGPUManager,
                lambda: get_webgpu_manager(),
                scope=ServiceScope.SINGLETON
            )
            
            logger.info("✅ WebGPU服务注册完成")
            
        except Exception as e:
            logger.error(f"❌ WebGPU服务注册失败: {e}")

    def _get_singleton(self, service_info: ServiceInfo) -> Any:
        """获取单例实例"""
        if service_info.service_type in self._instances:
            return self._instances[service_info.service_type]

        if service_info.instance is not None:
            self._instances[service_info.service_type] = service_info.instance
            return service_info.instance

        instance = self._create_instance(service_info)
        self._instances[service_info.service_type] = instance
        return instance

    def _get_scoped(self, service_info: ServiceInfo) -> Any:
        """获取作用域实例"""
        if self._current_scope is None:
            # 如果没有当前作用域，当作单例处理
            return self._get_singleton(service_info)

        scope_instances = self._scoped_instances.setdefault(
            self._current_scope, {})

        if service_info.service_type in scope_instances:
            return scope_instances[service_info.service_type]

        instance = self._create_instance(service_info)
        scope_instances[service_info.service_type] = instance
        return instance

    def _create_instance(self, service_info: ServiceInfo) -> Any:
        """创建服务实例"""
        self._resolving.add(service_info.service_type)

        try:
            if service_info.factory:
                # 使用工厂函数
                instance = self._call_factory(service_info.factory)
            elif callable(service_info.implementation):
                # 使用构造函数
                instance = self._call_constructor(
                    service_info.implementation, service_info.dependencies)
            else:
                # 直接返回实例
                instance = service_info.implementation

            logger.debug(
                f"Created instance of {service_info.service_type.__name__}")
            return instance

        finally:
            self._resolving.remove(service_info.service_type)

    def _call_factory(self, factory: Callable) -> Any:
        """调用工厂函数"""
        import inspect

        sig = inspect.signature(factory)
        kwargs = {}

        for param_name, param in sig.parameters.items():
            if param.annotation != inspect.Parameter.empty:
                dependency = self.resolve(param.annotation)
                kwargs[param_name] = dependency

        return factory(**kwargs)

    def _call_constructor(self, constructor: Type, dependencies: List[Type]) -> Any:
        """调用构造函数"""
        import inspect
        sig = inspect.signature(constructor.__init__)
        kwargs = {}

        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue

            # 只处理依赖项
            if param.annotation in dependencies:
                dependency = self.resolve(param.annotation)
                kwargs[param_name] = dependency
            elif param.default != inspect.Parameter.empty:
                # 如果有默认值，使用默认值
                continue
            # 其他参数（如基本类型）不处理，使用默认值

        return constructor(**kwargs)

    def _dispose_instance(self, instance: Any) -> None:
        """释放实例资源"""
        if hasattr(instance, 'dispose'):
            try:
                instance.dispose()
            except Exception as e:
                logger.error(f"Error disposing instance: {e}")
        elif hasattr(instance, 'close'):
            try:
                instance.close()
            except Exception as e:
                logger.error(f"Error closing instance: {e}")

    def _enter_scope(self, scope_name: str) -> None:
        """进入作用域"""
        self._current_scope = scope_name
        if scope_name not in self._scoped_instances:
            self._scoped_instances[scope_name] = {}

    def _exit_scope(self, scope_name: str) -> None:
        """退出作用域"""
        if scope_name in self._scoped_instances:
            # 释放作用域内的所有实例
            for instance in self._scoped_instances[scope_name].values():
                self._dispose_instance(instance)
            del self._scoped_instances[scope_name]

        self._current_scope = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()


class ServiceScopeContext:
    """
    服务作用域上下文管理器
    """

    def __init__(self, container: ServiceContainer, scope_name: str):
        self.container = container
        self.scope_name = scope_name

    def __enter__(self):
        self.container._enter_scope(self.scope_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.container._exit_scope(self.scope_name)


# 全局服务容器实例
_global_container: Optional[ServiceContainer] = None
_container_lock = threading.Lock()


def get_service_container() -> ServiceContainer:
    """
    获取全局服务容器实例

    Returns:
        服务容器实例
    """
    global _global_container

    with _container_lock:
        if _global_container is None:
            _global_container = ServiceContainer()
        return _global_container


def set_service_container(container: ServiceContainer) -> None:
    """
    设置全局服务容器

    Args:
        container: 服务容器实例
    """
    global _global_container

    with _container_lock:
        if _global_container is not None:
            _global_container.dispose()
        _global_container = container
