"""
组件状态和类型枚举定义

统一的组件状态和类型枚举，合并了所有模块中的组件状态和类型定义。
"""

from enum import Enum


class ComponentState(Enum):
    """
    组件状态枚举

    合并了以下模块的组件状态定义：
    - gui/registry/component_registry.py
    - gui/coordinators/modern_ui_coordinator.py

    状态说明：
    - UNREGISTERED: 组件未注册
    - REGISTERED: 组件已注册
    - INITIALIZING: 组件正在初始化
    - INITIALIZED: 组件已初始化
    - LOADING: 组件正在加载
    - LOADED: 组件已加载
    - ACTIVE: 组件处于活动状态
    - INACTIVE: 组件处于非活动状态
    - UNLOADING: 组件正在卸载
    - DESTROYED: 组件已销毁
    - ERROR: 组件出错
    - HIDDEN: 组件已隐藏
    """

    UNREGISTERED = "unregistered"
    REGISTERED = "registered"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    LOADING = "loading"
    LOADED = "loaded"
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNLOADING = "unloading"
    DESTROYED = "destroyed"
    ERROR = "error"
    HIDDEN = "hidden"

    def __str__(self) -> str:
        return self.value

    def is_registered(self) -> bool:
        """检查组件是否已注册"""
        return self in (ComponentState.REGISTERED, ComponentState.INITIALIZING, ComponentState.INITIALIZED)

    def is_initializing(self) -> bool:
        """检查组件是否正在初始化"""
        return self in (ComponentState.INITIALIZING, ComponentState.LOADING)

    def is_loaded(self) -> bool:
        """检查组件是否已加载"""
        return self in (ComponentState.LOADED, ComponentState.INITIALIZED)

    def is_active(self) -> bool:
        """检查组件是否处于活动状态"""
        return self in (ComponentState.ACTIVE,)

    def is_inactive(self) -> bool:
        """检查组件是否处于非活动状态"""
        return self in (ComponentState.INACTIVE, ComponentState.HIDDEN)

    def is_error(self) -> bool:
        """检查组件是否处于错误状态"""
        return self in (ComponentState.ERROR,)

    def is_final_state(self) -> bool:
        """检查组件是否处于最终状态"""
        return self in (ComponentState.DESTROYED,)

    def can_activate(self) -> bool:
        """检查组件是否可以激活"""
        return self in (ComponentState.LOADED, ComponentState.INITIALIZED, ComponentState.INACTIVE)

    def can_deactivate(self) -> bool:
        """检查组件是否可以停用"""
        return self in (ComponentState.ACTIVE,)

    def can_destroy(self) -> bool:
        """检查组件是否可以销毁"""
        return self not in (ComponentState.DESTROYED, ComponentState.UNREGISTERED)


class ComponentType(Enum):
    """
    组件类型枚举

    合并了以下模块的组件类型定义：
    - gui/registry/component_registry.py
    - gui/coordinators/modern_ui_coordinator.py

    类型说明：
    - WIDGET: 小部件
    - DIALOG: 对话框
    - WINDOW: 窗口
    - TAB: 标签页
    - PANEL: 面板
    - TOOLBAR: 工具栏
    - STATUSBAR: 状态栏
    - MENU: 菜单
    - CUSTOM: 自定义组件
    """

    WIDGET = "widget"
    DIALOG = "dialog"
    WINDOW = "window"
    TAB = "tab"
    PANEL = "panel"
    TOOLBAR = "toolbar"
    STATUSBAR = "statusbar"
    MENU = "menu"
    CUSTOM = "custom"

    def __str__(self) -> str:
        return self.value

    def is_window(self) -> bool:
        """检查是否为窗口类型"""
        return self in (ComponentType.WINDOW,)

    def is_dialog(self) -> bool:
        """检查是否为对话框类型"""
        return self in (ComponentType.DIALOG,)

    def is_widget(self) -> bool:
        """检查是否为小部件类型"""
        return self in (ComponentType.WIDGET,)

    def is_container(self) -> bool:
        """检查是否为容器类型"""
        return self in (ComponentType.WINDOW, ComponentType.DIALOG, ComponentType.TAB, ComponentType.PANEL)

    def is_control(self) -> bool:
        """检查是否为控件类型"""
        return self in (ComponentType.TOOLBAR, ComponentType.STATUSBAR, ComponentType.MENU)

    def is_custom(self) -> bool:
        """检查是否为自定义类型"""
        return self in (ComponentType.CUSTOM,)
