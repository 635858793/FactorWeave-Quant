"""
主题协调器模块

负责管理主题切换、样式应用。
从 MainWindowCoordinator 中提取主题相关功能，实现集中化管理。
"""

from loguru import logger
from typing import Dict, Any, Optional, List, Callable
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import pyqtSignal, QObject

from core.coordinators.base_coordinator import BaseCoordinator


class ThemeCoordinator(BaseCoordinator):
    """
    主题协调器

    职责：
    1. 管理主题切换、样式应用
    2. 提供可用主题列表
    3. 通知主题变更事件
    4. 协调各组件的主题同步
    """

    def __init__(self,
                 main_window_coordinator=None,
                 main_window=None,
                 service_container=None,
                 event_bus=None,
                 theme_manager=None):
        """
        初始化主题协调器

        Args:
            main_window_coordinator: 主窗口协调器引用
            main_window: 主窗口实例
            service_container: 服务容器
            event_bus: 事件总线
            theme_manager: 主题管理器实例
        """
        super().__init__(service_container, event_bus)
        
        self._main_window_coordinator = main_window_coordinator
        self._main_window = main_window
        self._theme_manager = theme_manager
        self._current_theme: Optional[str] = None
        self._theme_change_callbacks: List[Callable] = []
        self._registered_widgets: Dict[str, QWidget] = {}

    def apply_theme(self, theme_name: str) -> bool:
        """
        应用指定主题
        
        Args:
            theme_name: 主题名称
            
        Returns:
            是否成功应用
        """
        try:
            self._ensure_not_disposed()
            
            if not self._theme_manager:
                logger.error("ThemeManager not available")
                return False
            
            # 应用主题
            if hasattr(self._theme_manager, 'set_theme'):
                self._theme_manager.set_theme(theme_name)
            elif hasattr(self._theme_manager, 'apply_theme'):
                self._theme_manager.apply_theme(theme_name)
            else:
                logger.error("ThemeManager has no set_theme or apply_theme method")
                return False
            
            self._current_theme = theme_name
            
            # 通知所有注册的组件
            self._notify_theme_changed(theme_name)
            
            # 发布主题变更事件
            self._publish_theme_changed_event(theme_name)
            
            # 调用回调函数
            for callback in self._theme_change_callbacks:
                try:
                    callback(theme_name)
                except Exception as e:
                    logger.error(f"Error in theme change callback: {e}")
            
            logger.info(f"Theme applied: {theme_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply theme {theme_name}: {e}")
            return False

    def get_available_themes(self) -> List[str]:
        """
        获取可用主题列表
        
        Returns:
            主题名称列表
        """
        try:
            if self._theme_manager:
                if hasattr(self._theme_manager, 'get_available_themes'):
                    return self._theme_manager.get_available_themes()
                elif hasattr(self._theme_manager, 'available_themes'):
                    themes = self._theme_manager.available_themes
                    if callable(themes):
                        return themes()
                    return themes
            
            # 默认主题列表
            return ['default', 'light', 'dark']
            
        except Exception as e:
            logger.error(f"Failed to get available themes: {e}")
            return ['default', 'light', 'dark']

    def get_current_theme(self) -> Optional[str]:
        """
        获取当前主题
        
        Returns:
            当前主题名称
        """
        try:
            if self._theme_manager:
                if hasattr(self._theme_manager, 'current_theme'):
                    return self._theme_manager.current_theme
                elif hasattr(self._theme_manager, 'get_current_theme'):
                    return self._theme_manager.get_current_theme()
            
            return self._current_theme
            
        except Exception as e:
            logger.error(f"Failed to get current theme: {e}")
            return self._current_theme

    def notify_theme_changed(self) -> None:
        """
        通知主题已变更（用于外部触发）
        """
        try:
            current_theme = self.get_current_theme()
            if current_theme:
                self._notify_theme_changed(current_theme)
                self._publish_theme_changed_event(current_theme)
                logger.info(f"Theme change notification sent: {current_theme}")
            
        except Exception as e:
            logger.error(f"Failed to notify theme changed: {e}")

    def register_widget(self, widget_name: str, widget: QWidget) -> None:
        """
        注册需要主题同步的组件
        
        Args:
            widget_name: 组件名称
            widget: 组件实例
        """
        try:
            self._registered_widgets[widget_name] = widget
            logger.debug(f"Registered widget for theme sync: {widget_name}")
            
        except Exception as e:
            logger.error(f"Failed to register widget {widget_name}: {e}")

    def unregister_widget(self, widget_name: str) -> None:
        """
        取消注册组件
        
        Args:
            widget_name: 组件名称
        """
        try:
            if widget_name in self._registered_widgets:
                del self._registered_widgets[widget_name]
                logger.debug(f"Unregistered widget from theme sync: {widget_name}")
            
        except Exception as e:
            logger.error(f"Failed to unregister widget {widget_name}: {e}")

    def register_theme_change_callback(self, callback: Callable[[str], None]) -> None:
        """
        注册主题变更回调函数
        
        Args:
            callback: 回调函数，接收主题名称作为参数
        """
        if callback not in self._theme_change_callbacks:
            self._theme_change_callbacks.append(callback)
            logger.debug("Theme change callback registered")

    def unregister_theme_change_callback(self, callback: Callable[[str], None]) -> None:
        """
        取消注册主题变更回调函数
        
        Args:
            callback: 回调函数
        """
        if callback in self._theme_change_callbacks:
            self._theme_change_callbacks.remove(callback)
            logger.debug("Theme change callback unregistered")

    def is_qss_theme(self) -> bool:
        """
        检查当前主题是否为QSS主题
        
        Returns:
            是否为QSS主题
        """
        try:
            if self._theme_manager and hasattr(self._theme_manager, 'is_qss_theme'):
                return self._theme_manager.is_qss_theme()
            return False
            
        except Exception as e:
            logger.error(f"Failed to check QSS theme: {e}")
            return False

    def _notify_theme_changed(self, theme_name: str) -> None:
        """
        通知所有注册组件主题变更
        
        Args:
            theme_name: 新主题名称
        """
        try:
            for widget_name, widget in self._registered_widgets.items():
                try:
                    if hasattr(widget, 'update_theme'):
                        widget.update_theme(theme_name)
                    elif hasattr(widget, 'set_theme'):
                        widget.set_theme(theme_name)
                    elif hasattr(widget, 'update_style'):
                        widget.update_style()
                    else:
                        widget.style().unpolish(widget)
                        widget.style().polish(widget)
                        widget.update()
                    
                    logger.debug(f"Notified widget {widget_name} of theme change")
                    
                except Exception as e:
                    logger.error(f"Failed to notify widget {widget_name}: {e}")
            
        except Exception as e:
            logger.error(f"Failed to notify theme change: {e}")

    def _publish_theme_changed_event(self, theme_name: str) -> None:
        """
        发布主题变更事件
        
        Args:
            theme_name: 新主题名称
        """
        try:
            from core.events import ThemeChangedEvent
            
            event = ThemeChangedEvent(
                theme_name=theme_name,
                theme_config={'is_qss': self.is_qss_theme()}
            )
            self.publish_event(event)
            
            logger.debug(f"Published theme changed event: {theme_name}")
            
        except ImportError:
            logger.warning("ThemeChangedEvent not available")
        except Exception as e:
            logger.error(f"Failed to publish theme changed event: {e}")

    def _do_dispose(self) -> None:
        """
        清理主题协调器资源
        """
        try:
            self._theme_change_callbacks.clear()
            self._registered_widgets.clear()
            self._current_theme = None
            
            logger.info("Theme coordinator disposed")
            
        except Exception as e:
            logger.error(f"Failed to dispose theme coordinator: {e}")
