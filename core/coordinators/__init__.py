"""
协调器模块

提供系统协调器的基类和实现，负责协调各个组件和服务。
"""

from .base_coordinator import BaseCoordinator
from .main_window_coordinator import MainWindowCoordinator
from .panel_coordinator import PanelCoordinator
from .event_coordinator import EventCoordinator
from .dialog_coordinator import DialogCoordinator
from .theme_coordinator import ThemeCoordinator

__all__ = [
    'BaseCoordinator',
    'MainWindowCoordinator',
    'PanelCoordinator',
    'EventCoordinator',
    'DialogCoordinator',
    'ThemeCoordinator'
]
