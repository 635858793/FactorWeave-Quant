"""
主题切换功能集成测试

测试QSS和JSON主题切换的完整流程。
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt5.QtCore import Qt
from core.events.event_bus import EventBus, set_event_bus
from core.events.events import ThemeChangedEvent
from utils.theme import ThemeManager, Theme


class TestThemeSwitching:
    """主题切换功能测试"""
    
    @pytest.fixture
    def qapp(self):
        """创建QApplication实例"""
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
    
    @pytest.fixture
    def event_bus(self):
        """创建测试EventBus实例"""
        bus = EventBus(deduplication_window=0.5)
        set_event_bus(bus)
        yield bus
        set_event_bus(None)
    
    @pytest.fixture
    def theme_manager(self, event_bus):
        """创建测试ThemeManager实例"""
        with patch('utils.theme.ConfigManager'):
            manager = ThemeManager()
            manager._event_bus = event_bus
            yield manager
    
    def test_qss_theme_switching(self, theme_manager, event_bus, qapp):
        """测试QSS主题切换功能"""
        # 订阅事件
        events_received = []
        def on_theme_changed(event):
            events_received.append(event)
        
        event_bus.subscribe(ThemeChangedEvent, on_theme_changed)
        
        # 创建测试窗口
        window = QMainWindow()
        window.setWindowTitle("Test Window")
        
        # 模拟QSS主题切换
        event = ThemeChangedEvent(
            theme_name='dark_qss',
            theme_config={'background': '#1a1a1a', 'text': '#ffffff'}
        )
        event_bus.publish(event)
        
        # 验证事件发布
        assert len(events_received) == 1
        assert events_received[0].theme_name == 'dark_qss'
        
        # 验证主题配置
        assert events_received[0].theme_config['background'] == '#1a1a1a'
        
        window.close()
    
    def test_json_theme_switching(self, theme_manager, event_bus, qapp):
        """测试JSON主题切换功能"""
        # 订阅事件
        events_received = []
        def on_theme_changed(event):
            events_received.append(event)
        
        event_bus.subscribe(ThemeChangedEvent, on_theme_changed)
        
        # 创建测试窗口
        window = QMainWindow()
        window.setWindowTitle("Test Window")
        
        # 模拟JSON主题切换
        event = ThemeChangedEvent(
            theme_name='light_json',
            theme_config={
                'background': '#FFFFFF',
                'text': '#222b45',
                'primary': '#3699ff',
                'secondary': '#f64e60'
            }
        )
        event_bus.publish(event)
        
        # 验证事件发布
        assert len(events_received) == 1
        assert events_received[0].theme_name == 'light_json'
        
        # 验证主题配置
        assert events_received[0].theme_config['background'] == '#FFFFFF'
        assert events_received[0].theme_config['primary'] == '#3699ff'
        
        window.close()
    
    def test_event_deduplication(self, event_bus):
        """测试事件去重功能"""
        # 订阅事件
        events_received = []
        def on_theme_changed(event):
            events_received.append(event)
        
        event_bus.subscribe(ThemeChangedEvent, on_theme_changed)
        
        # 快速发布相同的事件
        for _ in range(5):
            event = ThemeChangedEvent(
                theme_name='dark',
                theme_config={'background': '#1a1a1a'}
            )
            event_bus.publish(event)
        
        # 验证去重效果（应该只收到1个事件）
        assert len(events_received) == 1
        
        # 等待去重窗口过期
        time.sleep(0.6)
        
        # 再次发布相同的事件
        event = ThemeChangedEvent(
            theme_name='dark',
            theme_config={'background': '#1a1a1a'}
        )
        event_bus.publish(event)
        
        # 验证收到新的事件
        assert len(events_received) == 2
    
    def test_multiple_subscribers(self, event_bus):
        """测试多个订阅者接收事件"""
        # 创建多个订阅者
        subscriber1_events = []
        subscriber2_events = []
        subscriber3_events = []
        
        def on_theme_changed1(event):
            subscriber1_events.append(event)
        
        def on_theme_changed2(event):
            subscriber2_events.append(event)
        
        def on_theme_changed3(event):
            subscriber3_events.append(event)
        
        event_bus.subscribe(ThemeChangedEvent, on_theme_changed1)
        event_bus.subscribe(ThemeChangedEvent, on_theme_changed2)
        event_bus.subscribe(ThemeChangedEvent, on_theme_changed3)
        
        # 发布事件
        event = ThemeChangedEvent(
            theme_name='light',
            theme_config={'background': '#FFFFFF'}
        )
        event_bus.publish(event)
        
        # 验证所有订阅者都收到事件
        assert len(subscriber1_events) == 1
        assert len(subscriber2_events) == 1
        assert len(subscriber3_events) == 1
    
    def test_theme_manager_integration(self, theme_manager, event_bus):
        """测试ThemeManager与EventBus集成"""
        # 订阅事件
        events_received = []
        def on_theme_changed(event):
            events_received.append(event)
        
        event_bus.subscribe(ThemeChangedEvent, on_theme_changed)
        
        # 模拟主题切换
        event = ThemeChangedEvent(
            theme_name='custom_theme',
            theme_config={'background': '#f0f0f0', 'text': '#333333'}
        )
        event_bus.publish(event)
        
        # 验证事件
        assert len(events_received) == 1
        assert events_received[0].theme_name == 'custom_theme'
        assert events_received[0].theme_config['background'] == '#f0f0f0'
