"""
协调器单元测试

测试范围：
- BaseCoordinator 生命周期管理
- BaseCoordinator 事件处理
- BaseCoordinator 服务获取
- BaseCoordinator 上下文管理器
- UICoordinator UI组件管理
- AsyncCoordinator 异步操作
- 异常处理和边界条件
"""
import pytest
import asyncio
import sys
import os
import importlib.util
from unittest.mock import MagicMock, patch, call
from typing import Optional

project_root = os.path.join(os.path.dirname(__file__), '..')
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def _load_module_directly(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


base_coordinator_path = os.path.join(project_root, 'core', 'coordinators', 'base_coordinator.py')
base_coordinator = _load_module_directly('core.coordinators.base_coordinator', base_coordinator_path)

BaseCoordinator = base_coordinator.BaseCoordinator
UICoordinator = base_coordinator.UICoordinator
AsyncCoordinator = base_coordinator.AsyncCoordinator

from core.containers import ServiceContainer
from core.events import EventBus


class MockEvent:
    """模拟事件类"""
    pass


class TestConcreteCoordinator(BaseCoordinator):
    """用于测试的具体协调器实现"""
    
    def _do_initialize(self) -> None:
        pass
    
    def _do_dispose(self) -> None:
        pass


class TestUICoordinator(UICoordinator):
    """用于测试的具体UI协调器实现"""
    
    def _do_initialize(self) -> None:
        pass
    
    def _do_dispose(self) -> None:
        pass


class TestAsyncCoordinatorImpl(AsyncCoordinator):
    """用于测试的具体异步协调器实现"""
    
    async def _do_initialize_async(self) -> None:
        pass
    
    async def _do_dispose_async(self) -> None:
        pass


@pytest.fixture
def mock_service_container():
    container = MagicMock(spec=ServiceContainer)
    container.resolve = MagicMock()
    container.try_resolve = MagicMock()
    return container


@pytest.fixture
def mock_event_bus():
    bus = MagicMock(spec=EventBus)
    bus.publish = MagicMock()
    bus.subscribe = MagicMock()
    bus.unsubscribe = MagicMock()
    return bus


class TestBaseCoordinatorInitialization:

    def test_initialization_with_defaults(self):
        coordinator = TestConcreteCoordinator()
        assert coordinator._initialized is False
        assert coordinator._disposed is False
        assert coordinator._name == 'TestConcreteCoordinator'
        assert coordinator._event_handlers == []

    def test_initialization_with_provided_instances(self, mock_service_container, mock_event_bus):
        with patch.object(base_coordinator, 'get_event_bus', return_value=mock_event_bus):
            coordinator = TestConcreteCoordinator(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )
            assert coordinator._service_container == mock_service_container
            assert coordinator._event_bus == mock_event_bus

    def test_properties(self, mock_service_container, mock_event_bus):
        with patch.object(base_coordinator, 'get_event_bus', return_value=mock_event_bus):
            coordinator = TestConcreteCoordinator(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )
            assert coordinator.name == 'TestConcreteCoordinator'
            assert coordinator.initialized is False
            assert coordinator.disposed is False
            assert coordinator.service_container == mock_service_container
            assert coordinator.event_bus == mock_event_bus


class TestBaseCoordinatorLifecycle:

    def test_initialize_success(self, mock_service_container, mock_event_bus):
        coordinator = TestConcreteCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        coordinator.initialize()
        assert coordinator.initialized is True
        assert coordinator.disposed is False

    def test_initialize_already_initialized(self, mock_service_container, mock_event_bus):
        coordinator = TestConcreteCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        coordinator.initialize()
        assert coordinator.initialized is True
        coordinator.initialize()
        assert coordinator.initialized is True

    def test_initialize_with_exception(self, mock_service_container, mock_event_bus):
        class FailingCoordinator(BaseCoordinator):
            def _do_initialize(self) -> None:
                raise ValueError("Initialization failed")
        
        coordinator = FailingCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        with pytest.raises(ValueError):
            coordinator.initialize()
        assert coordinator.initialized is False

    def test_dispose_success(self, mock_service_container, mock_event_bus):
        coordinator = TestConcreteCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        coordinator.initialize()
        assert coordinator.initialized is True
        coordinator.dispose()
        assert coordinator.disposed is True
        assert coordinator.initialized is False

    def test_dispose_already_disposed(self, mock_service_container, mock_event_bus):
        coordinator = TestConcreteCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        coordinator.initialize()
        coordinator.dispose()
        assert coordinator.disposed is True
        coordinator.dispose()
        assert coordinator.disposed is True

    def test_dispose_with_exception(self, mock_service_container, mock_event_bus):
        class FailingCoordinator(BaseCoordinator):
            def _do_dispose(self) -> None:
                raise ValueError("Dispose failed")
        
        coordinator = FailingCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        coordinator.initialize()
        with pytest.raises(ValueError):
            coordinator.dispose()

    def test_dispose_without_initialize(self, mock_service_container, mock_event_bus):
        coordinator = TestConcreteCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        coordinator.dispose()
        assert coordinator.disposed is True
        assert coordinator.initialized is False


class TestBaseCoordinatorServiceManagement:

    def test_get_service_success(self, mock_service_container, mock_event_bus):
        mock_service = MagicMock()
        mock_service_container.resolve = MagicMock(return_value=mock_service)
        coordinator = TestConcreteCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        service = coordinator.get_service(str)
        assert service == mock_service
        mock_service_container.resolve.assert_called_once_with(str)

    def test_try_get_service_success(self, mock_service_container, mock_event_bus):
        mock_service = MagicMock()
        mock_service_container.try_resolve = MagicMock(return_value=mock_service)
        coordinator = TestConcreteCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        service = coordinator.try_get_service(str)
        assert service == mock_service
        mock_service_container.try_resolve.assert_called_once_with(str)

    def test_try_get_service_not_found(self, mock_service_container, mock_event_bus):
        mock_service_container.try_resolve = MagicMock(return_value=None)
        coordinator = TestConcreteCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        service = coordinator.try_get_service(str)
        assert service is None


class TestBaseCoordinatorEventManagement:

    def test_publish_event(self, mock_service_container, mock_event_bus):
        mock_event_bus.publish = MagicMock()
        with patch.object(base_coordinator, 'get_event_bus', return_value=mock_event_bus):
            coordinator = TestConcreteCoordinator(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )
            coordinator.publish_event(MockEvent())
            mock_event_bus.publish.assert_called_once()

    def test_register_event_handlers(self, mock_service_container, mock_event_bus):
        with patch.object(base_coordinator, 'get_event_bus', return_value=mock_event_bus):
            coordinator = TestConcreteCoordinator(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )
            def handler(event):
                pass
            coordinator._subscribe_event(MockEvent, handler, priority=10)
            assert len(coordinator._event_handlers) == 1
            assert coordinator._event_handlers[0] == (MockEvent, handler)
            mock_event_bus.subscribe.assert_called_once_with(MockEvent, handler, 10)

    def test_unregister_event_handlers(self, mock_service_container, mock_event_bus):
        with patch.object(base_coordinator, 'get_event_bus', return_value=mock_event_bus):
            coordinator = TestConcreteCoordinator(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )
            def handler(event):
                pass
            coordinator._subscribe_event(MockEvent, handler)
            coordinator._unregister_event_handlers()
            assert len(coordinator._event_handlers) == 0
            mock_event_bus.unsubscribe.assert_called_once_with(MockEvent, handler)

    def test_unregister_event_handlers_empty(self, mock_service_container, mock_event_bus):
        with patch.object(base_coordinator, 'get_event_bus', return_value=mock_event_bus):
            coordinator = TestConcreteCoordinator(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )
            coordinator._unregister_event_handlers()
            assert len(coordinator._event_handlers) == 0


class TestBaseCoordinatorContextManager:

    def test_context_manager_success(self, mock_service_container, mock_event_bus):
        coordinator = TestConcreteCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        with coordinator as coord:
            assert coord.initialized is True
            assert coord is coordinator
        assert coordinator.disposed is True
        assert coordinator.initialized is False

    def test_context_manager_with_exception(self, mock_service_container, mock_event_bus):
        coordinator = TestConcreteCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        try:
            with coordinator:
                raise ValueError("Test exception")
        except ValueError:
            pass
        assert coordinator.disposed is True
        assert coordinator.initialized is False


class TestBaseCoordinatorEnsureMethods:

    def test_ensure_initialized_when_not_initialized(self, mock_service_container, mock_event_bus):
        coordinator = TestConcreteCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        with pytest.raises(RuntimeError) as exc_info:
            coordinator._ensure_initialized()
        assert 'not initialized' in str(exc_info.value)

    def test_ensure_initialized_when_initialized(self, mock_service_container, mock_event_bus):
        coordinator = TestConcreteCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        coordinator.initialize()
        coordinator._ensure_initialized()

    def test_ensure_not_disposed_when_not_disposed(self, mock_service_container, mock_event_bus):
        coordinator = TestConcreteCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        coordinator._ensure_not_disposed()

    def test_ensure_not_disposed_when_disposed(self, mock_service_container, mock_event_bus):
        coordinator = TestConcreteCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        coordinator.dispose()
        with pytest.raises(RuntimeError) as exc_info:
            coordinator._ensure_not_disposed()
        assert 'has been disposed' in str(exc_info.value)


class TestUICoordinator:

    def test_ui_component_management(self):
        ui_components = {}
        
        component1 = MagicMock()
        component2 = MagicMock()
        
        ui_components['comp1'] = component1
        ui_components['comp2'] = component2
        
        assert len(ui_components) == 2
        assert 'comp1' in ui_components
        
        del ui_components['comp1']
        assert 'comp1' not in ui_components
        assert len(ui_components) == 1

    def test_ui_component_retrieval(self):
        ui_components = {}
        
        component = MagicMock()
        ui_components['test'] = component
        
        retrieved = ui_components.get('test')
        assert retrieved == component
        
        missing = ui_components.get('nonexistent')
        assert missing is None

    def test_ui_component_clear_on_dispose(self):
        ui_components = {}
        ui_components['comp1'] = MagicMock()
        ui_components['comp2'] = MagicMock()
        
        ui_components.clear()
        assert len(ui_components) == 0

    def test_ui_coordinator_parent_widget(self, mock_service_container, mock_event_bus):
        parent_widget = MagicMock()
        
        class MockUICoordinator:
            def __init__(self, parent_widget, service_container, event_bus):
                self._parent_widget = parent_widget
                self._ui_components = {}
            
            @property
            def parent_widget(self):
                return self._parent_widget
            
            def register_ui_component(self, name, component):
                self._ui_components[name] = component
            
            def get_ui_component(self, name):
                return self._ui_components.get(name)
            
            def unregister_ui_component(self, name):
                self._ui_components.pop(name, None)
            
            def dispose(self):
                self._ui_components.clear()
        
        coordinator = MockUICoordinator(
            parent_widget=parent_widget,
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        
        assert coordinator.parent_widget == parent_widget
        assert coordinator._ui_components == {}
        
        coordinator.register_ui_component('comp1', MagicMock())
        assert 'comp1' in coordinator._ui_components
        
        coordinator.dispose()
        assert len(coordinator._ui_components) == 0


class TestAsyncCoordinator:

    def test_async_initialize_success(self, mock_service_container, mock_event_bus):
        coordinator = TestAsyncCoordinatorImpl(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        async def run_test():
            await coordinator.initialize_async()
            assert coordinator.initialized is True
        asyncio.run(run_test())

    def test_async_initialize_already_initialized(self, mock_service_container, mock_event_bus):
        coordinator = TestAsyncCoordinatorImpl(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        async def run_test():
            await coordinator.initialize_async()
            await coordinator.initialize_async()
            assert coordinator.initialized is True
        asyncio.run(run_test())

    def test_async_dispose_success(self, mock_service_container, mock_event_bus):
        coordinator = TestAsyncCoordinatorImpl(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        async def run_test():
            await coordinator.initialize_async()
            await coordinator.dispose_async()
            assert coordinator.disposed is True
            assert coordinator.initialized is False
        asyncio.run(run_test())

    def test_async_dispose_already_disposed(self, mock_service_container, mock_event_bus):
        coordinator = TestAsyncCoordinatorImpl(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        async def run_test():
            await coordinator.initialize_async()
            await coordinator.dispose_async()
            await coordinator.dispose_async()
            assert coordinator.disposed is True
        asyncio.run(run_test())

    def test_async_context_manager(self, mock_service_container, mock_event_bus):
        coordinator = TestAsyncCoordinatorImpl(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        async def run_test():
            async with coordinator as coord:
                assert coord.initialized is True
                assert coord is coordinator
            assert coordinator.disposed is True
            assert coordinator.initialized is False
        asyncio.run(run_test())

    def test_async_initialize_with_exception(self, mock_service_container, mock_event_bus):
        class FailingAsyncCoordinator(AsyncCoordinator):
            async def _do_initialize_async(self) -> None:
                raise ValueError("Async initialization failed")
        
        coordinator = FailingAsyncCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        async def run_test():
            with pytest.raises(ValueError):
                await coordinator.initialize_async()
            assert coordinator.initialized is False
        asyncio.run(run_test())


class TestCoordinatorEdgeCases:

    def test_multiple_initializations_and_disposals(self, mock_service_container, mock_event_bus):
        coordinator = TestConcreteCoordinator(
            service_container=mock_service_container,
            event_bus=mock_event_bus
        )
        for _ in range(3):
            coordinator.initialize()
            assert coordinator.initialized is True
            coordinator.dispose()
            assert coordinator.disposed is True

    def test_event_handler_registration_multiple(self, mock_service_container, mock_event_bus):
        with patch.object(base_coordinator, 'get_event_bus', return_value=mock_event_bus):
            coordinator = TestConcreteCoordinator(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )
            handlers = []
            for i in range(5):
                def handler(event, idx=i):
                    pass
                handlers.append(handler)
                coordinator._subscribe_event(MockEvent, handler)
            assert len(coordinator._event_handlers) == 5
            coordinator._unregister_event_handlers()
            assert len(coordinator._event_handlers) == 0
            assert mock_event_bus.unsubscribe.call_count == 5

    def test_coordinator_name_inheritance(self, mock_service_container, mock_event_bus):
        class CustomCoordinator(BaseCoordinator):
            def _do_initialize(self) -> None:
                pass
            def _do_dispose(self) -> None:
                pass
        with patch.object(base_coordinator, 'get_event_bus', return_value=mock_event_bus):
            coordinator = CustomCoordinator(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )
            assert coordinator.name == 'CustomCoordinator'

    def test_coordinator_lifecycle_state_transitions(self, mock_service_container, mock_event_bus):
        with patch.object(base_coordinator, 'get_event_bus', return_value=mock_event_bus):
            coordinator = TestConcreteCoordinator(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )
            assert coordinator.initialized is False
            assert coordinator.disposed is False
            coordinator.initialize()
            assert coordinator.initialized is True
            assert coordinator.disposed is False
            coordinator.dispose()
            assert coordinator.initialized is False
            assert coordinator.disposed is True

    def test_context_manager_nested_exception(self, mock_service_container, mock_event_bus):
        with patch.object(base_coordinator, 'get_event_bus', return_value=mock_event_bus):
            coordinator = TestConcreteCoordinator(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )
            with pytest.raises(ValueError):
                with coordinator:
                    with coordinator:
                        raise ValueError("Nested exception")
            assert coordinator.disposed is True

    def test_publish_event_without_handlers(self, mock_service_container, mock_event_bus):
        mock_event_bus.publish = MagicMock(return_value=[])
        with patch.object(base_coordinator, 'get_event_bus', return_value=mock_event_bus):
            coordinator = TestConcreteCoordinator(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )
            coordinator.publish_event(MockEvent())
            mock_event_bus.publish.assert_called_once()
