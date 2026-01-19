"""
基础协调器模块

定义协调器的基础接口和通用功能。
"""

from loguru import logger
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from core.events import EventBus, get_event_bus, BaseEvent
from core.containers import ServiceContainer, get_service_container


class BaseCoordinator(ABC):
    """
    基础协调器接口

    所有协调器都应该继承此类。协调器负责协调各个组件和服务的交互。
    """

    def __init__(self,
                 service_container: Optional[ServiceContainer] = None,
                 event_bus: Optional[EventBus] = None):
        """
        初始化基础协调器

        Args:
            service_container: 服务容器，如果为None则使用全局容器
            event_bus: 事件总线，如果为None则使用全局事件总线
        """
        self._service_container = service_container or get_service_container()
        self._event_bus = event_bus or get_event_bus()
        self._initialized = False
        self._disposed = False
        self._name = self.__class__.__name__
        self._event_handlers = []

    @property
    def name(self) -> str:
        """获取协调器名称"""
        return self._name

    @property
    def initialized(self) -> bool:
        """检查协调器是否已初始化"""
        return self._initialized

    @property
    def disposed(self) -> bool:
        """检查协调器是否已释放"""
        return self._disposed

    @property
    def service_container(self) -> ServiceContainer:
        """获取服务容器"""
        return self._service_container

    @property
    def event_bus(self) -> EventBus:
        """获取事件总线"""
        return self._event_bus

    def initialize(self) -> None:
        """
        初始化协调器

        子类可以重写此方法来执行初始化逻辑。
        """
        if self._initialized:
            logger.warning(f"Coordinator {self._name} is already initialized")
            return

        try:
            self._register_event_handlers()
            self._do_initialize()
            self._initialized = True
            logger.info(f"Coordinator {self._name} initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize coordinator {self._name}: {e}")
            raise

    def dispose(self) -> None:
        """
        释放协调器资源

        子类可以重写此方法来执行清理逻辑。
        """
        if self._disposed:
            logger.warning(f"Coordinator {self._name} is already disposed")
            return

        try:
            self._unregister_event_handlers()
            self._do_dispose()
            self._disposed = True
            self._initialized = False
            logger.info(f"Coordinator {self._name} disposed successfully")
        except Exception as e:
            logger.error(f"Failed to dispose coordinator {self._name}: {e}")
            raise

    def get_service(self, service_type: Type[Any]) -> Any:
        """
        获取服务实例

        Args:
            service_type: 服务类型

        Returns:
            服务实例
        """
        return self._service_container.resolve(service_type)

    def try_get_service(self, service_type: Type[Any]) -> Optional[Any]:
        """
        尝试获取服务实例

        Args:
            service_type: 服务类型

        Returns:
            服务实例或None
        """
        return self._service_container.try_resolve(service_type)

    def publish_event(self, event: BaseEvent) -> List[Any]:
        """
        发布事件

        Args:
            event: 要发布的事件

        Returns:
            事件处理结果列表
        """
        return self._event_bus.publish(event)

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

    def _register_event_handlers(self) -> None:
        """
        注册事件处理器

        子类应该重写此方法来注册需要的事件处理器。
        """
        pass

    def _unregister_event_handlers(self) -> None:
        """
        取消注册事件处理器
        """
        for event_type, handler in self._event_handlers:
            self._event_bus.unsubscribe(event_type, handler)
        self._event_handlers.clear()

    def _subscribe_event(self, event_type: Type[BaseEvent], handler, priority: int = 0) -> None:
        """
        订阅事件

        Args:
            event_type: 事件类型
            handler: 事件处理器
            priority: 优先级
        """
        self._event_bus.subscribe(event_type, handler, priority)
        self._event_handlers.append((event_type, handler))

    def _ensure_initialized(self) -> None:
        """确保协调器已初始化"""
        if not self._initialized:
            raise RuntimeError(f"Coordinator {self._name} is not initialized")

    def _ensure_not_disposed(self) -> None:
        """确保协调器未被释放"""
        if self._disposed:
            raise RuntimeError(f"Coordinator {self._name} has been disposed")

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()

class UICoordinator(BaseCoordinator):
    """
    UI协调器基类

    所有UI相关的协调器应该继承此类。
    """

    def __init__(self,
                 parent_widget=None,
                 service_container: Optional[ServiceContainer] = None,
                 event_bus: Optional[EventBus] = None):
        """
        初始化UI协调器

        Args:
            parent_widget: 父级UI组件
            service_container: 服务容器
            event_bus: 事件总线
        """
        super().__init__(service_container, event_bus)
        self._parent_widget = parent_widget
        self._ui_components = {}

    @property
    def parent_widget(self):
        """获取父级UI组件"""
        return self._parent_widget

    def get_ui_component(self, name: str) -> Optional[Any]:
        """
        获取UI组件

        Args:
            name: 组件名称

        Returns:
            UI组件或None
        """
        return self._ui_components.get(name)

    def register_ui_component(self, name: str, component: Any) -> None:
        """
        注册UI组件

        Args:
            name: 组件名称
            component: UI组件
        """
        self._ui_components[name] = component
        logger.debug(
            f"Registered UI component {name} in coordinator {self._name}")

    def unregister_ui_component(self, name: str) -> None:
        """
        取消注册UI组件

        Args:
            name: 组件名称
        """
        if name in self._ui_components:
            del self._ui_components[name]
            logger.debug(
                f"Unregistered UI component {name} from coordinator {self._name}")

    def _do_dispose(self) -> None:
        """清理UI组件"""
        self._ui_components.clear()
        super()._do_dispose()

class AsyncCoordinator(BaseCoordinator):
    """
    异步协调器基类

    支持异步操作的协调器应该继承此类。
    """

    async def initialize_async(self) -> None:
        """
        异步初始化协调器
        """
        if self._initialized:
            logger.warning(f"Coordinator {self._name} is already initialized")
            return

        try:
            self._register_event_handlers()
            await self._do_initialize_async()
            self._initialized = True
            logger.info(
                f"Coordinator {self._name} initialized successfully (async)")
        except Exception as e:
            logger.error(
                f"Failed to initialize coordinator {self._name} (async): {e}")
            raise

    async def dispose_async(self) -> None:
        """
        异步释放协调器资源
        """
        if self._disposed:
            logger.warning(f"Coordinator {self._name} is already disposed")
            return

        try:
            self._unregister_event_handlers()
            await self._do_dispose_async()
            self._disposed = True
            self._initialized = False
            logger.info(
                f"Coordinator {self._name} disposed successfully (async)")
        except Exception as e:
            logger.error(
                f"Failed to dispose coordinator {self._name} (async): {e}")
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
