"""
插件状态枚举定义

统一的插件状态枚举，合并了所有模块中的插件状态定义。
注意：这个枚举与PluginState不同，PluginState表示插件的生命周期状态，
而PluginStatus表示插件的启用/禁用状态。
"""

from enum import Enum


class PluginStatus(Enum):
    """
    插件状态枚举

    合并了以下模块的插件状态定义：
    - db/models/plugin_models.py
    - core/services/strategy_service.py
    - core/plugin_manager.py
    - core/plugin_center.py

    状态说明：
    - UNKNOWN: 插件状态未知
    - UNLOADED: 插件未加载
    - LOADED: 插件已加载
    - ENABLED: 插件已启用
    - DISABLED: 插件已禁用
    - ACTIVE: 插件处于活动状态
    - INACTIVE: 插件处于非活动状态
    - RUNNING: 插件正在运行
    - IDLE: 插件处于空闲状态
    - ERROR: 插件出错
    - FAILED: 插件失败
    - INSTALLING: 插件正在安装
    - UPDATING: 插件正在更新
    - UNINSTALLING: 插件正在卸载
    - CREATED: 插件已创建
    - INITIALIZED: 插件已初始化
    - DESTROYED: 插件已销毁
    """

    UNKNOWN = "unknown"
    UNLOADED = "unloaded"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ACTIVE = "active"
    INACTIVE = "inactive"
    RUNNING = "running"
    IDLE = "idle"
    ERROR = "error"
    FAILED = "failed"
    INSTALLING = "installing"
    UPDATING = "updating"
    UNINSTALLING = "uninstalling"
    CREATED = "created"
    INITIALIZED = "initialized"
    DESTROYED = "destroyed"

    def __str__(self) -> str:
        return self.value

    def is_enabled(self) -> bool:
        """检查插件是否已启用"""
        return self in (PluginStatus.ENABLED, PluginStatus.ACTIVE, PluginStatus.RUNNING)

    def is_disabled(self) -> bool:
        """检查插件是否已禁用"""
        return self in (PluginStatus.DISABLED, PluginStatus.INACTIVE, PluginStatus.IDLE)

    def is_loaded(self) -> bool:
        """检查插件是否已加载"""
        return self in (PluginStatus.LOADED, PluginStatus.INITIALIZED)

    def is_unloaded(self) -> bool:
        """检查插件是否未加载"""
        return self in (PluginStatus.UNLOADED, PluginStatus.DESTROYED)

    def is_error(self) -> bool:
        """检查插件是否处于错误状态"""
        return self in (PluginStatus.ERROR, PluginStatus.FAILED)

    def is_operational(self) -> bool:
        """检查插件是否可以运行"""
        return self in (
            PluginStatus.ENABLED,
            PluginStatus.ACTIVE,
            PluginStatus.RUNNING,
            PluginStatus.LOADED,
            PluginStatus.INITIALIZED,
        )

    def is_maintenance(self) -> bool:
        """检查插件是否处于维护状态"""
        return self in (PluginStatus.INSTALLING, PluginStatus.UPDATING, PluginStatus.UNINSTALLING)

    def can_enable(self) -> bool:
        """检查插件是否可以启用"""
        return self in (PluginStatus.LOADED, PluginStatus.INITIALIZED, PluginStatus.DISABLED)

    def can_disable(self) -> bool:
        """检查插件是否可以禁用"""
        return self in (PluginStatus.ENABLED, PluginStatus.ACTIVE, PluginStatus.RUNNING)

    def can_load(self) -> bool:
        """检查插件是否可以加载"""
        return self in (PluginStatus.UNLOADED, PluginStatus.CREATED)

    def can_unload(self) -> bool:
        """检查插件是否可以卸载"""
        return self in (PluginStatus.LOADED, PluginStatus.INITIALIZED, PluginStatus.ERROR, PluginStatus.FAILED)
