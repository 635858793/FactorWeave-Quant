"""
统一插件接口定义

本模块定义了FactorWeave-Quant系统中所有插件必须实现的统一接口，
解决现有系统中插件生命周期管理混乱的问题。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from enum import Enum
import asyncio

from ..enums import PluginLifecycle
from ..plugin_types import PluginType


@dataclass
class PluginInfo:
    """插件信息"""

    # 基础信息
    name: str
    version: str
    description: str = ""

    # 插件类型和分类
    plugin_type: PluginType = PluginType.ANALYSIS
    category: str = "general"

    # 作者和许可信息
    author: str = ""
    license: str = ""
    homepage: str = ""

    # 技术信息
    module_path: str = ""
    entry_point: str = "create_plugin"

    # 依赖关系
    dependencies: List[str] = field(default_factory=list)
    optional_dependencies: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)

    # 系统要求
    min_python_version: str = "3.8"
    max_python_version: Optional[str] = None
    required_packages: List[str] = field(default_factory=list)

    # 配置信息
    config_schema: Dict[str, Any] = field(default_factory=dict)
    default_config: Dict[str, Any] = field(default_factory=dict)

    # 运行时信息
    state: PluginLifecycle = PluginLifecycle.UNLOADED
    instance: Optional['IPlugin'] = None
    load_time: Optional[datetime] = None
    error_message: Optional[str] = None

    # 扩展信息
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        from dataclasses import asdict
        result = asdict(self)
        result['plugin_type'] = self.plugin_type.value
        result['state'] = self.state.value
        if self.load_time:
            result['load_time'] = self.load_time.isoformat()
        # 移除不可序列化的字段
        result.pop('instance', None)
        return result


@dataclass
class PluginEvent:
    """插件事件"""

    event_type: str
    plugin_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        from dataclasses import asdict
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


class IPlugin(ABC):
    """统一插件接口

    所有插件必须实现此接口，提供统一的插件管理方式。
    """

    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """插件信息"""
        pass

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """插件是否激活"""
        pass

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化插件

        Args:
            config: 插件配置

        Returns:
            bool: 初始化是否成功

        Raises:
            PluginError: 初始化失败时抛出
        """
        pass

    @abstractmethod
    async def start(self) -> bool:
        """启动插件

        Returns:
            bool: 启动是否成功

        Raises:
            PluginError: 启动失败时抛出
        """
        pass

    @abstractmethod
    async def stop(self) -> bool:
        """停止插件

        Returns:
            bool: 停止是否成功
        """
        pass

    @abstractmethod
    async def cleanup(self) -> bool:
        """清理插件资源

        Returns:
            bool: 清理是否成功
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """健康检查

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        pass

    async def pause(self) -> bool:
        """暂停插件

        Returns:
            bool: 暂停是否成功
        """
        # 默认实现，子类可以重写
        return True

    async def resume(self) -> bool:
        """恢复插件

        Returns:
            bool: 恢复是否成功
        """
        # 默认实现，子类可以重写
        return True

    async def reload(self) -> bool:
        """重新加载插件

        Returns:
            bool: 重新加载是否成功
        """
        # 默认实现：停止 -> 清理 -> 初始化 -> 启动
        try:
            await self.stop()
            await self.cleanup()
            config = self.info.default_config
            await self.initialize(config)
            await self.start()
            return True
        except Exception:
            return False

    async def get_config_schema(self) -> Dict[str, Any]:
        """获取配置模式

        Returns:
            Dict[str, Any]: 配置模式定义
        """
        return self.info.config_schema

    async def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """验证配置

        Args:
            config: 配置数据

        Returns:
            List[str]: 验证错误列表，空列表表示验证通过
        """
        # 默认实现，子类可以重写
        return []

    async def get_metrics(self) -> Dict[str, Any]:
        """获取插件指标

        Returns:
            Dict[str, Any]: 插件运行指标
        """
        # 默认实现，子类可以重写
        return {
            "name": self.info.name,
            "version": self.info.version,
            "state": self.info.state.value,
            "is_active": self.is_active,
            "load_time": self.info.load_time.isoformat() if self.info.load_time else None
        }


class IPluginEventHandler(ABC):
    """插件事件处理器接口"""

    @abstractmethod
    async def handle_event(self, event: PluginEvent) -> bool:
        """处理插件事件

        Args:
            event: 插件事件

        Returns:
            bool: 处理是否成功
        """
        pass


class IPluginRegistry(ABC):
    """插件注册表接口"""

    @abstractmethod
    async def register_plugin(self, plugin_info: PluginInfo) -> bool:
        """注册插件

        Args:
            plugin_info: 插件信息

        Returns:
            bool: 注册是否成功
        """
        pass

    @abstractmethod
    async def unregister_plugin(self, plugin_name: str) -> bool:
        """注销插件

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 注销是否成功
        """
        pass

    @abstractmethod
    async def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """获取插件信息

        Args:
            plugin_name: 插件名称

        Returns:
            Optional[PluginInfo]: 插件信息，不存在时返回None
        """
        pass

    @abstractmethod
    async def list_plugins(self, plugin_type: Optional[PluginType] = None) -> List[PluginInfo]:
        """列出插件

        Args:
            plugin_type: 插件类型过滤，None表示所有类型

        Returns:
            List[PluginInfo]: 插件信息列表
        """
        pass

    @abstractmethod
    async def find_plugins_by_category(self, category: str) -> List[PluginInfo]:
        """按分类查找插件

        Args:
            category: 插件分类

        Returns:
            List[PluginInfo]: 插件信息列表
        """
        pass


class PluginError(Exception):
    """插件异常基类"""

    def __init__(self, message: str, plugin_name: Optional[str] = None,
                 error_code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.plugin_name = plugin_name
        self.error_code = error_code


class PluginLoadError(PluginError):
    """插件加载异常"""
    pass


class PluginInitializationError(PluginError):
    """插件初始化异常"""
    pass


class PluginDependencyError(PluginError):
    """插件依赖异常"""
    pass


class PluginValidationError(PluginError):
    """插件验证异常"""
    pass


class CircularDependencyError(PluginError):
    """循环依赖异常"""
    pass
