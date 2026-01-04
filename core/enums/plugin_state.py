"""
插件生命周期状态枚举定义

统一的插件生命周期状态枚举，合并了所有模块中的插件生命周期状态定义。
"""

from enum import Enum


class PluginLifecycle(Enum):
    """
    插件生命周期状态枚举

    合并了以下模块的插件生命周期状态定义：
    - core/services/plugin_service.py
    - core/interfaces/plugin.py
    - plugins/plugin_interface.py

    状态说明：
    - UNKNOWN: 插件状态未知
    - CREATED: 插件对象已创建
    - DISCOVERED: 插件已被发现
    - VALIDATED: 插件已通过验证
    - UNLOADED: 插件未加载
    - LOADING: 插件正在加载
    - LOADED: 插件已加载
    - INITIALIZING: 插件正在初始化
    - INITIALIZED: 插件已初始化
    - CONNECTING: 插件正在连接
    - CONNECTED: 插件已连接
    - ACTIVATED: 插件已激活
    - ACTIVE: 插件处于活动状态
    - PAUSED: 插件已暂停
    - DEACTIVATED: 插件已停用
    - INACTIVE: 插件处于非活动状态
    - UNLOADING: 插件正在卸载
    - FAILED: 插件失败
    - ERROR: 插件出错
    - REMOVED: 插件已移除
    - DESTROYED: 插件已销毁
    """

    UNKNOWN = "unknown"
    CREATED = "created"
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ACTIVATED = "activated"
    ACTIVE = "active"
    PAUSED = "paused"
    DEACTIVATED = "deactivated"
    INACTIVE = "inactive"
    UNLOADING = "unloading"
    FAILED = "failed"
    ERROR = "error"
    REMOVED = "removed"
    DESTROYED = "destroyed"

    def __str__(self) -> str:
        return self.value

    def is_initial_state(self) -> bool:
        """检查是否处于初始状态"""
        return self in (PluginLifecycle.UNKNOWN, PluginLifecycle.CREATED, PluginLifecycle.DISCOVERED)

    def is_loading(self) -> bool:
        """检查是否正在加载"""
        return self in (PluginLifecycle.LOADING, PluginLifecycle.INITIALIZING, PluginLifecycle.CONNECTING)

    def is_loaded(self) -> bool:
        """检查是否已加载"""
        return self in (PluginLifecycle.LOADED, PluginLifecycle.INITIALIZED, PluginLifecycle.CONNECTED)

    def is_active(self) -> bool:
        """检查是否处于活动状态"""
        return self in (PluginLifecycle.ACTIVATED, PluginLifecycle.ACTIVE)

    def is_inactive(self) -> bool:
        """检查是否处于非活动状态"""
        return self in (PluginLifecycle.PAUSED, PluginLifecycle.DEACTIVATED, PluginLifecycle.INACTIVE)

    def is_error(self) -> bool:
        """检查是否处于错误状态"""
        return self in (PluginLifecycle.FAILED, PluginLifecycle.ERROR)

    def is_final_state(self) -> bool:
        """检查是否处于最终状态"""
        return self in (PluginLifecycle.REMOVED, PluginLifecycle.DESTROYED)

    def can_transition_to(self, target_state: 'PluginLifecycle') -> bool:
        """
        检查是否可以转换到目标状态

        Args:
            target_state: 目标状态

        Returns:
            是否可以转换
        """
        valid_transitions = {
            PluginLifecycle.UNKNOWN: [PluginLifecycle.CREATED, PluginLifecycle.DISCOVERED],
            PluginLifecycle.CREATED: [PluginLifecycle.DISCOVERED, PluginLifecycle.VALIDATED, PluginLifecycle.LOADING],
            PluginLifecycle.DISCOVERED: [PluginLifecycle.VALIDATED, PluginLifecycle.LOADING],
            PluginLifecycle.VALIDATED: [PluginLifecycle.LOADING],
            PluginLifecycle.UNLOADED: [PluginLifecycle.LOADING],
            PluginLifecycle.LOADING: [PluginLifecycle.LOADED, PluginLifecycle.FAILED, PluginLifecycle.ERROR],
            PluginLifecycle.LOADED: [PluginLifecycle.INITIALIZING, PluginLifecycle.ACTIVATED, PluginLifecycle.UNLOADING],
            PluginLifecycle.INITIALIZING: [PluginLifecycle.INITIALIZED, PluginLifecycle.FAILED, PluginLifecycle.ERROR],
            PluginLifecycle.INITIALIZED: [PluginLifecycle.CONNECTING, PluginLifecycle.ACTIVATED, PluginLifecycle.DEACTIVATED],
            PluginLifecycle.CONNECTING: [PluginLifecycle.CONNECTED, PluginLifecycle.FAILED, PluginLifecycle.ERROR],
            PluginLifecycle.CONNECTED: [PluginLifecycle.ACTIVATED, PluginLifecycle.DEACTIVATED],
            PluginLifecycle.ACTIVATED: [PluginLifecycle.ACTIVE, PluginLifecycle.DEACTIVATED],
            PluginLifecycle.ACTIVE: [PluginLifecycle.PAUSED, PluginLifecycle.DEACTIVATED, PluginLifecycle.INACTIVE],
            PluginLifecycle.PAUSED: [PluginLifecycle.ACTIVE, PluginLifecycle.DEACTIVATED],
            PluginLifecycle.DEACTIVATED: [PluginLifecycle.INACTIVE, PluginLifecycle.UNLOADING],
            PluginLifecycle.INACTIVE: [PluginLifecycle.ACTIVATED, PluginLifecycle.UNLOADING],
            PluginLifecycle.UNLOADING: [PluginLifecycle.UNLOADED, PluginLifecycle.REMOVED, PluginLifecycle.DESTROYED],
            PluginLifecycle.FAILED: [PluginLifecycle.LOADING, PluginLifecycle.REMOVED, PluginLifecycle.DESTROYED],
            PluginLifecycle.ERROR: [PluginLifecycle.LOADING, PluginLifecycle.REMOVED, PluginLifecycle.DESTROYED],
            PluginLifecycle.REMOVED: [PluginLifecycle.DESTROYED],
            PluginLifecycle.DESTROYED: [],
        }
        return target_state in valid_transitions.get(self, [])
