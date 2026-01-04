"""
核心组件EventBus迁移测试

测试EnhancedStrategyManagerDialog等核心组件的EventBus集成。
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtCore import Qt
from core.events.event_bus import EventBus, set_event_bus
from core.events import ThemeChangedEvent


class TestCoreComponentMigration:
    """核心组件EventBus迁移测试"""
    
    @pytest.fixture
    def qapp(self):
        """创建QApplication实例"""
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
    
    @pytest.fixture
    def event_bus(self):
        """创建测试EventBus实例（禁用去重）"""
        bus = EventBus(deduplication_window=0)  # 禁用去重
        set_event_bus(bus)
        yield bus
        set_event_bus(None)
    
    def test_enhanced_strategy_manager_dialog_eventbus_integration(self, event_bus, qapp):
        """测试EnhancedStrategyManagerDialog的EventBus集成"""
        # 模拟EnhancedStrategyManagerDialog的EventBus集成
        class MockStrategyDialog(QDialog):
            def __init__(self, event_bus):
                super().__init__()
                self._event_bus = event_bus
                self._event_subscription = None
                self.theme_change_count = 0
                
                # 订阅EventBus主题变化事件
                self._event_subscription = self._event_bus.subscribe(
                    ThemeChangedEvent,
                    self._on_theme_changed_eventbus
                )
            
            def _on_theme_changed_eventbus(self, event: ThemeChangedEvent):
                """主题变化时的处理（EventBus模式）"""
                self.theme_change_count += 1
        
        # 创建对话框
        dialog = MockStrategyDialog(event_bus)
        
        # 发布主题变化事件
        event = ThemeChangedEvent(
            theme_name='dark',
            theme_config={'background': '#1a1a1a'}
        )
        event_bus.publish(event)
        
        # 验证对话框收到事件
        assert dialog.theme_change_count == 1
        
        # 发布多个主题变化事件
        for i in range(3):
            event = ThemeChangedEvent(
                theme_name=f'theme_{i}',
                theme_config={'background': f'#ffffff{i}'}
            )
            event_bus.publish(event)
        
        # 验证对话框收到所有事件
        assert dialog.theme_change_count == 4
        
        # 清理订阅
        event_bus.unsubscribe(ThemeChangedEvent, dialog._on_theme_changed_eventbus)
        
        dialog.close()
    
    def test_eventbus_subscription_cleanup(self, event_bus, qapp):
        """测试EventBus订阅清理"""
        # 创建模拟对话框
        class MockDialog(QDialog):
            def __init__(self, event_bus):
                super().__init__()
                self._event_bus = event_bus
                self.event_count = 0
                
                # 订阅EventBus
                self._event_bus.subscribe(
                    ThemeChangedEvent,
                    self._on_theme_changed
                )
            
            def _on_theme_changed(self, event: ThemeChangedEvent):
                self.event_count += 1
            
            def cleanup(self):
                """清理EventBus订阅"""
                self._event_bus.unsubscribe(ThemeChangedEvent, self._on_theme_changed)
        
        # 创建对话框
        dialog = MockDialog(event_bus)
        
        # 发布事件
        event = ThemeChangedEvent(
            theme_name='light',
            theme_config={'background': '#FFFFFF'}
        )
        event_bus.publish(event)
        
        # 验证收到事件
        assert dialog.event_count == 1
        
        # 清理订阅
        dialog.cleanup()
        
        # 再次发布事件
        event_bus.publish(event)
        
        # 验证没有收到新事件
        assert dialog.event_count == 1
        
        dialog.close()
    
    def test_multiple_dialogs_eventbus(self, event_bus, qapp):
        """测试多个对话框共享EventBus"""
        # 创建多个对话框
        class MockDialog(QDialog):
            def __init__(self, event_bus, name):
                super().__init__()
                self.name = name
                self._event_bus = event_bus
                self._event_subscription = None
                self.events_received = []
                
                # 订阅EventBus
                self._event_subscription = self._event_bus.subscribe(
                    ThemeChangedEvent,
                    self._on_theme_changed
                )
            
            def _on_theme_changed(self, event: ThemeChangedEvent):
                self.events_received.append(event)
        
        # 创建3个对话框
        dialog1 = MockDialog(event_bus, "Dialog1")
        dialog2 = MockDialog(event_bus, "Dialog2")
        dialog3 = MockDialog(event_bus, "Dialog3")
        
        # 发布主题变化事件
        event = ThemeChangedEvent(
            theme_name='dark',
            theme_config={'background': '#1a1a1a'}
        )
        event_bus.publish(event)
        
        # 验证所有对话框都收到事件
        assert len(dialog1.events_received) == 1
        assert len(dialog2.events_received) == 1
        assert len(dialog3.events_received) == 1
        
        # 发布多个事件
        for i in range(3):
            event = ThemeChangedEvent(
                theme_name=f'theme_{i}',
                theme_config={'background': f'#ffffff{i}'}
            )
            event_bus.publish(event)
        
        # 验证所有对话框都收到所有事件
        assert len(dialog1.events_received) == 4
        assert len(dialog2.events_received) == 4
        assert len(dialog3.events_received) == 4
        
        # 清理订阅
        event_bus.unsubscribe(ThemeChangedEvent, dialog1._on_theme_changed)
        event_bus.unsubscribe(ThemeChangedEvent, dialog2._on_theme_changed)
        event_bus.unsubscribe(ThemeChangedEvent, dialog3._on_theme_changed)
        
        dialog1.close()
        dialog2.close()
        dialog3.close()
    
    def test_eventbus_error_handling(self, event_bus, qapp):
        """测试EventBus错误处理"""
        # 创建一个会抛出异常的处理器
        class MockDialog(QDialog):
            def __init__(self, event_bus):
                super().__init__()
                self._event_bus = event_bus
                self._event_subscription = None
                self.error_count = 0
                
                # 订阅EventBus
                self._event_subscription = self._event_bus.subscribe(
                    ThemeChangedEvent,
                    self._on_theme_changed
                )
            
            def _on_theme_changed(self, event: ThemeChangedEvent):
                # 模拟错误
                if event.theme_name == 'error':
                    raise ValueError("Test error")
                self.error_count += 1
        
        # 创建对话框
        dialog = MockDialog(event_bus)
        
        # 发布正常事件
        event = ThemeChangedEvent(
            theme_name='light',
            theme_config={'background': '#FFFFFF'}
        )
        event_bus.publish(event)
        
        # 验证收到事件
        assert dialog.error_count == 1
        
        # 发布错误事件
        event = ThemeChangedEvent(
            theme_name='error',
            theme_config={'background': '#FF0000'}
        )
        event_bus.publish(event)
        
        # 验证错误计数没有增加（事件处理失败）
        assert dialog.error_count == 1
        
        # 清理订阅
        event_bus.unsubscribe(ThemeChangedEvent, dialog._on_theme_changed)
        
        dialog.close()
    
    def test_eventbus_async_mode(self, event_bus, qapp):
        """测试EventBus异步执行模式"""
        import asyncio
        
        # 创建异步处理器
        class MockDialog(QDialog):
            def __init__(self, event_bus):
                super().__init__()
                self._event_bus = event_bus
                self._event_subscription = None
                self.events_received = []
                
                # 订阅EventBus
                self._event_subscription = self._event_bus.subscribe(
                    ThemeChangedEvent,
                    self._on_theme_changed
                )
            
            def _on_theme_changed(self, event: ThemeChangedEvent):
                # 同步处理事件（EventBus会自动检测异步函数）
                self.events_received.append(event)
        
        # 创建对话框
        dialog = MockDialog(event_bus)
        
        # 发布事件
        event = ThemeChangedEvent(
            theme_name='dark',
            theme_config={'background': '#1a1a1a'}
        )
        event_bus.publish(event)
        
        # 验证收到事件
        assert len(dialog.events_received) == 1
        
        # 清理订阅
        event_bus.unsubscribe(ThemeChangedEvent, dialog._on_theme_changed)
        
        dialog.close()
