"""
统一枚举定义模块

提供系统中所有枚举类型的统一定义，避免重复定义和类型不一致问题。
"""

from .health_status import HealthStatus
from .plugin_state import PluginLifecycle
from .plugin_status import PluginStatus
from .component_state import ComponentState, ComponentType

__all__ = [
    'HealthStatus',
    'PluginLifecycle',
    'PluginStatus',
    'ComponentState',
    'ComponentType',
]
