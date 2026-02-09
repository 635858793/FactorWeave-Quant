"""
扩展服务 - 架构精简重构版本

提供扩展点管理、钩子机制和第三方集成功能。
与PluginService互补，PluginService管理插件，ExtensionService管理扩展点和钩子。

核心功能:
1. 扩展点注册和管理
2. 钩子（Hook）机制
3. 扩展生命周期管理
4. 第三方库集成支持
"""

import threading
from typing import Dict, List, Optional, Any, Callable, Set, Type
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from enum import Enum

from loguru import logger

from .base_service import BaseService
from ..events import EventBus, get_event_bus


class HookType(Enum):
    """钩子类型"""
    BEFORE = "before"  # 前置钩子
    AFTER = "after"    # 后置钩子
    AROUND = "around"  # 环绕钩子
    ERROR = "error"    # 错误钩子


class ExtensionPoint(Enum):
    """系统扩展点"""
    # 数据处理扩展点
    DATA_LOAD = "data.load"
    DATA_TRANSFORM = "data.transform"
    DATA_VALIDATE = "data.validate"
    DATA_EXPORT = "data.export"

    # 策略扩展点
    STRATEGY_INIT = "strategy.init"
    STRATEGY_EXECUTE = "strategy.execute"
    STRATEGY_FINALIZE = "strategy.finalize"

    # UI扩展点
    UI_PANEL_INIT = "ui.panel.init"
    UI_WIDGET_CREATE = "ui.widget.create"
    UI_MENU_BUILD = "ui.menu.build"

    # 交易扩展点
    TRADE_ORDER_CREATE = "trade.order.create"
    TRADE_ORDER_EXECUTE = "trade.order.execute"
    TRADE_ORDER_COMPLETE = "trade.order.complete"

    # 系统扩展点
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_CONFIG_CHANGE = "system.config.change"


@dataclass
class Hook:
    """钩子定义"""
    name: str
    hook_type: HookType
    extension_point: ExtensionPoint
    callback: Callable
    priority: int = 0  # 优先级，数值越大越先执行
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.now)


@dataclass
class Extension:
    """扩展定义"""
    name: str
    extension_point: ExtensionPoint
    handler: Callable
    description: str = ""
    version: str = "1.0.0"
    enabled: bool = True
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.now)


@dataclass
class ExtensionMetrics:
    """扩展服务指标"""
    total_extensions: int = 0
    total_hooks: int = 0
    active_extensions: int = 0
    active_hooks: int = 0
    hook_executions: int = 0
    failed_executions: int = 0
    last_execution_time_ms: float = 0.0


class ExtensionService(BaseService):
    """
    扩展服务 - 15核心服务之一

    职责:
    1. 扩展点注册和管理
    2. 钩子机制实现
    3. 扩展生命周期管理
    4. 第三方库集成支持

    与PluginService的区别:
    - PluginService: 管理独立的插件模块（如数据源插件）
    - ExtensionService: 管理系统扩展点和钩子（如在数据加载前后执行自定义逻辑）
    """

    def __init__(self):
        """初始化扩展服务"""
        super().__init__()

        # 扩展点管理
        self._extensions: Dict[ExtensionPoint, List[Extension]] = defaultdict(list)

        # 钩子管理
        self._hooks: Dict[ExtensionPoint, List[Hook]] = defaultdict(list)

        # 扩展点启用状态
        self._extension_point_enabled: Dict[ExtensionPoint, bool] = {}

        # 指标
        self._extension_metrics = ExtensionMetrics()

        # 事件总线
        self._event_bus: Optional[EventBus] = None

        # 线程安全
        self._lock = threading.RLock()

        logger.info("ExtensionService initialized for architecture simplification")

    def _do_initialize(self) -> None:
        """初始化扩展服务核心组件"""
        logger.info("Initializing ExtensionService core components...")

        # 1. 初始化事件总线
        self._event_bus = get_event_bus()
        logger.info("✓ Event bus connected")

        # 2. 初始化所有扩展点（默认启用）
        for point in ExtensionPoint:
            self._extension_point_enabled[point] = True
        logger.info(f"✓ {len(ExtensionPoint)} extension points initialized")

        # 3. 注册系统默认钩子
        self._register_default_hooks()
        logger.info("✓ Default hooks registered")

        logger.info("ExtensionService initialized successfully")

    def _register_default_hooks(self):
        """注册系统默认钩子"""
        # 系统启动钩子
        self.register_hook(
            name="log_system_startup",
            hook_type=HookType.AFTER,
            extension_point=ExtensionPoint.SYSTEM_STARTUP,
            callback=lambda *args, **kwargs: logger.info("System startup completed"),
            priority=0
        )

        # 系统关闭钩子
        self.register_hook(
            name="log_system_shutdown",
            hook_type=HookType.BEFORE,
            extension_point=ExtensionPoint.SYSTEM_SHUTDOWN,
            callback=lambda *args, **kwargs: logger.info("System shutting down"),
            priority=0
        )

    def register_extension(
        self,
        name: str,
        extension_point: ExtensionPoint,
        handler: Callable,
        description: str = "",
        version: str = "1.0.0",
        dependencies: Optional[List[str]] = None,
        **metadata
    ) -> bool:
        """
        注册扩展

        Args:
            name: 扩展名称
            extension_point: 扩展点
            handler: 处理函数
            description: 描述
            version: 版本
            dependencies: 依赖的其他扩展
            **metadata: 元数据

        Returns:
            是否注册成功
        """
        try:
            with self._lock:
                extension = Extension(
                    name=name,
                    extension_point=extension_point,
                    handler=handler,
                    description=description,
                    version=version,
                    dependencies=dependencies or [],
                    metadata=metadata
                )

                self._extensions[extension_point].append(extension)
                self._extension_metrics.total_extensions += 1
                self._extension_metrics.active_extensions += 1

                logger.info(f"Extension registered: {name} at {extension_point.value}")
                return True

        except Exception as e:
            logger.error(f"Failed to register extension {name}: {e}")
            return False

    def register_hook(
        self,
        name: str,
        hook_type: HookType,
        extension_point: ExtensionPoint,
        callback: Callable,
        priority: int = 0,
        **metadata
    ) -> bool:
        """
        注册钩子

        Args:
            name: 钩子名称
            hook_type: 钩子类型
            extension_point: 扩展点
            callback: 回调函数
            priority: 优先级（越大越先执行）
            **metadata: 元数据

        Returns:
            是否注册成功
        """
        try:
            with self._lock:
                hook = Hook(
                    name=name,
                    hook_type=hook_type,
                    extension_point=extension_point,
                    callback=callback,
                    priority=priority,
                    metadata=metadata
                )

                self._hooks[extension_point].append(hook)
                # 按优先级排序
                self._hooks[extension_point].sort(key=lambda h: h.priority, reverse=True)

                self._extension_metrics.total_hooks += 1
                self._extension_metrics.active_hooks += 1

                logger.debug(f"Hook registered: {name} ({hook_type.value}) at {extension_point.value}")
                return True

        except Exception as e:
            logger.error(f"Failed to register hook {name}: {e}")
            return False

    def execute_extension_point(
        self,
        extension_point: ExtensionPoint,
        *args,
        **kwargs
    ) -> List[Any]:
        """
        执行扩展点

        Args:
            extension_point: 扩展点
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            所有扩展的执行结果列表
        """
        results = []

        with self._lock:
            # 检查扩展点是否启用
            if not self._extension_point_enabled.get(extension_point, True):
                logger.debug(f"Extension point {extension_point.value} is disabled")
                return results

            # 执行前置钩子
            self._execute_hooks(extension_point, HookType.BEFORE, *args, **kwargs)

            # 执行扩展
            extensions = self._extensions.get(extension_point, [])
            for ext in extensions:
                if not ext.enabled:
                    continue

                try:
                    start_time = datetime.now()
                    result = ext.handler(*args, **kwargs)
                    elapsed = (datetime.now() - start_time).total_seconds() * 1000

                    results.append(result)
                    self._extension_metrics.hook_executions += 1
                    self._extension_metrics.last_execution_time_ms = elapsed

                    logger.debug(f"Extension executed: {ext.name} ({elapsed:.2f}ms)")

                except Exception as e:
                    logger.error(f"Extension execution failed: {ext.name} - {e}")
                    self._extension_metrics.failed_executions += 1

                    # 执行错误钩子
                    self._execute_hooks(
                        extension_point,
                        HookType.ERROR,
                        error=e,
                        extension=ext.name,
                        *args,
                        **kwargs
                    )

            # 执行后置钩子
            self._execute_hooks(
                extension_point,
                HookType.AFTER,
                results=results,
                *args,
                **kwargs
            )

        return results

    def _execute_hooks(
        self,
        extension_point: ExtensionPoint,
        hook_type: HookType,
        *args,
        **kwargs
    ):
        """执行指定类型的钩子"""
        hooks = [
            h for h in self._hooks.get(extension_point, [])
            if h.hook_type == hook_type and h.enabled
        ]

        for hook in hooks:
            try:
                hook.callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Hook execution failed: {hook.name} - {e}")

    def enable_extension_point(self, extension_point: ExtensionPoint):
        """启用扩展点"""
        with self._lock:
            self._extension_point_enabled[extension_point] = True
            logger.info(f"Extension point enabled: {extension_point.value}")

    def disable_extension_point(self, extension_point: ExtensionPoint):
        """禁用扩展点"""
        with self._lock:
            self._extension_point_enabled[extension_point] = False
            logger.info(f"Extension point disabled: {extension_point.value}")

    def get_extensions(self, extension_point: Optional[ExtensionPoint] = None) -> List[Extension]:
        """获取扩展列表"""
        with self._lock:
            if extension_point:
                return self._extensions.get(extension_point, []).copy()

            all_extensions = []
            for exts in self._extensions.values():
                all_extensions.extend(exts)
            return all_extensions

    def get_hooks(self, extension_point: Optional[ExtensionPoint] = None) -> List[Hook]:
        """获取钩子列表"""
        with self._lock:
            if extension_point:
                return self._hooks.get(extension_point, []).copy()

            all_hooks = []
            for hooks in self._hooks.values():
                all_hooks.extend(hooks)
            return all_hooks

    def unregister_extension(self, name: str, extension_point: ExtensionPoint) -> bool:
        """注销扩展"""
        with self._lock:
            extensions = self._extensions.get(extension_point, [])
            for i, ext in enumerate(extensions):
                if ext.name == name:
                    extensions.pop(i)
                    self._extension_metrics.active_extensions -= 1
                    logger.info(f"Extension unregistered: {name}")
                    return True
            return False

    def unregister_hook(self, name: str, extension_point: ExtensionPoint) -> bool:
        """注销钩子"""
        with self._lock:
            hooks = self._hooks.get(extension_point, [])
            for i, hook in enumerate(hooks):
                if hook.name == name:
                    hooks.pop(i)
                    self._extension_metrics.active_hooks -= 1
                    logger.debug(f"Hook unregistered: {name}")
                    return True
            return False

    def get_extension_metrics(self) -> Dict[str, Any]:
        """获取扩展服务指标"""
        with self._lock:
            return {
                'total_extensions': self._extension_metrics.total_extensions,
                'total_hooks': self._extension_metrics.total_hooks,
                'active_extensions': self._extension_metrics.active_extensions,
                'active_hooks': self._extension_metrics.active_hooks,
                'hook_executions': self._extension_metrics.hook_executions,
                'failed_executions': self._extension_metrics.failed_executions,
                'last_execution_time_ms': self._extension_metrics.last_execution_time_ms,
            }

    def dispose(self) -> None:
        """释放资源"""
        try:
            with self._lock:
                # 清理扩展
                self._extensions.clear()
                self._hooks.clear()
                self._extension_point_enabled.clear()

                logger.info("ExtensionService disposed successfully")

        except Exception as e:
            logger.error(f"Error disposing ExtensionService: {e}")


# 便捷函数
def get_extension_service() -> ExtensionService:
    """获取扩展服务实例"""
    from ..containers import get_service_container
    container = get_service_container()
    return container.resolve(ExtensionService)
