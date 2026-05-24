"""
FactorWeave-Quant  插件接口定义

定义了插件开发的标准接口和规范，为插件生态建设提供统一的标准。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.enums.plugin_state import PluginLifecycle
from core.plugin_types import PluginType, PluginCategory, AssetType, DataType

from loguru import logger

# 延迟导入PyQt5，避免在没有QApplication时初始化失败
QWidget = None
QMenu = None
QAction = None
QObject = None
pyqtSignal = None

def _ensure_qt_imports():
    """确保Qt模块已导入"""
    global QWidget, QMenu, QAction, QObject, pyqtSignal
    if QWidget is None:
        try:
            # 检查是否有QApplication实例
            from PyQt5.QtWidgets import QApplication
            if QApplication.instance() is None:
                # 没有QApplication实例，不导入Qt模块
                return
            from PyQt5.QtWidgets import QWidget, QMenu, QAction
            from PyQt5.QtCore import QObject, pyqtSignal
        except ImportError:
            from PyQt5.QtWidgets import QApplication
            if QApplication.instance() is None:
                return
            from PyQt5.QtWidgets import QWidget, QMenu, QAction
            from PyQt5.QtCore import QObject, pyqtSignal


@dataclass
class PluginMetadata:
    """插件元数据"""
    name: str                        # 插件名称
    version: str                     # 版本号
    description: str                 # 插件描述
    author: str                      # 作者
    email: str                       # 联系邮箱
    website: str                     # 官网地址
    license: str                     # 许可证
    plugin_type: PluginType          # 插件类型
    category: PluginCategory         # 插件分类
    dependencies: List[str]          # 依赖列表
    min_framework_version: str       # 最低框架版本要求
    max_framework_version: str       # 最高框架版本要求
    tags: List[str]                  # 标签
    icon_path: Optional[str] = None  # 图标路径
    documentation_url: Optional[str] = None  # 文档地址
    support_url: Optional[str] = None        # 支持地址
    changelog_url: Optional[str] = None      # 更新日志地址


class IPlugin(ABC):
    """插件接口基类"""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """获取插件元数据"""
        pass

    @abstractmethod
    def initialize(self, config: dict = None) -> bool:
        """
        初始化插件

        Args:
            config: 配置字典（向后兼容：保留旧版PluginContext支持）

        Returns:
            bool: 初始化是否成功
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """清理插件资源"""
        pass

    def get_config_schema(self) -> Optional[Dict[str, Any]]:
        """
        获取插件配置模式

        Returns:
            配置模式字典或None
        """
        return None

    def get_default_config(self) -> Optional[Dict[str, Any]]:
        """
        获取默认配置

        Returns:
            默认配置字典或None
        """
        return None

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证配置

        Args:
            config: 配置字典

        Returns:
            bool: 配置是否有效
        """
        return True

    def on_event(self, event_name: str, *args, **kwargs) -> None:
        """
        处理事件

        Args:
            event_name: 事件名称
            *args: 位置参数
            **kwargs: 关键字参数
        """
        pass


class IIndicatorPlugin(IPlugin):
    """技术指标插件接口"""

    @abstractmethod
    def get_indicator_name(self) -> str:
        """获取指标名称"""
        pass

    @abstractmethod
    def get_indicator_parameters(self) -> Dict[str, Any]:
        """获取指标参数定义"""
        pass

    @abstractmethod
    def calculate(self, data: Any, **params) -> Any:
        """
        计算指标值

        Args:
            data: 输入数据
            **params: 参数

        Returns:
            计算结果
        """
        pass

    def get_plot_config(self) -> Dict[str, Any]:
        """
        获取绘图配置

        Returns:
            绘图配置
        """
        return {}


class IDataSourceStrategyPlugin(IPlugin):
    """
    数据源策略插件接口
    
    这是数据源插件的策略接口，用于轻量级的信号生成场景。
    与 core/strategy_extensions.py 中的 IStrategyPlugin 不同：
    - 此接口：用于数据源插件，简单信号生成
    - core 中的：完整的策略插件接口，支持完整的生命周期管理
    
    推荐使用场景:
    - 数据源内置的简单策略
    - 快速原型验证
    - 轻量级信号生成
    
    完整策略开发推荐使用:
    - core.strategy_extensions.IStrategyPlugin
    - 配合 StrategyService 使用
    """

    @abstractmethod
    def get_strategy_name(self) -> str:
        """
        获取策略名称
        
        Returns:
            str: 策略名称
        """
        pass

    @abstractmethod
    def get_strategy_parameters(self) -> Dict[str, Any]:
        """
        获取策略参数定义
        
        Returns:
            Dict[str, Any]: 参数名到默认值/描述的映射
        """
        pass

    @abstractmethod
    def generate_signals(self, data: Any, **params) -> Any:
        """
        生成交易信号

        Args:
            data: 市场数据（通常是 pandas DataFrame）
            **params: 策略参数

        Returns:
            交易信号
        """
        pass


class IDataSourcePlugin(IPlugin):
    """数据源插件接口（支持异步初始化）"""

    def __init__(self):
        """初始化插件基类属性"""
        super().__init__() if hasattr(super(), '__init__') else None
        self.plugin_state = PluginLifecycle.CREATED
        self._connection_future = None
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix=f"Plugin-{self.__class__.__name__}")
        self.last_error = None
        self.initialized = False

    @abstractmethod
    def get_data_source_name(self) -> str:
        """获取数据源名称"""
        pass

    @abstractmethod
    def get_supported_data_types(self) -> List[str]:
        """获取支持的数据类型"""
        pass

    @abstractmethod
    def fetch_data(self, symbol: str, data_type: str, **params) -> Any:
        """
        获取数据

        Args:
            symbol: 股票代码
            data_type: 数据类型
            **params: 其他参数

        Returns:
            数据
        """
        pass

    def test_connection(self) -> bool:
        """
        测试连接

        Returns:
            bool: 连接是否正常
        """
        return True

    # === 新增：异步初始化接口 ===

    def connect_async(self) -> Future:
        """
        异步连接（在后台线程中建立连接）

        子类如果需要耗时的网络连接操作，应该重写 _do_connect() 方法

        Returns:
            Future: 连接任务的Future对象，可以查询连接状态
        """
        if self.plugin_state == PluginLifecycle.CONNECTED:
            # 已连接，直接返回成功的 Future
            future = Future()
            future.set_result(True)
            return future

        if self._connection_future and not self._connection_future.done():
            # 连接中，返回现有的 Future
            return self._connection_future

        # 启动新的连接任务
        self.plugin_state = PluginLifecycle.CONNECTING
        logger.info(f"[{self.__class__.__name__}] 启动异步连接...")
        self._connection_future = self._executor.submit(self._do_connect)
        return self._connection_future

    def _do_connect(self) -> bool:
        """
        实际的连接逻辑（在后台线程中执行）

        子类应该重写此方法，实现真正的连接逻辑

        Returns:
            bool: 连接是否成功
        """
        try:
            # 默认实现：调用test_connection
            result = self.test_connection()
            if result:
                self.plugin_state = PluginLifecycle.CONNECTED
                logger.info(f"[{self.__class__.__name__}] 连接成功")
            else:
                self.plugin_state = PluginLifecycle.FAILED
                self.last_error = "Connection test failed"
                logger.warning(f"[{self.__class__.__name__}] 连接失败")
            return result
        except Exception as e:
            self.plugin_state = PluginLifecycle.FAILED
            self.last_error = str(e)
            logger.error(f"[{self.__class__.__name__}] 连接异常: {e}")
            return False

    def is_ready(self) -> bool:
        """
        检查插件是否已就绪（已连接）

        Returns:
            bool: 插件是否可用
        """
        return self.plugin_state == PluginLifecycle.CONNECTED

    def wait_until_ready(self, timeout: float = 30.0) -> bool:
        """
        等待插件就绪（用于首次使用时确保连接已建立）

        Args:
            timeout: 超时时间（秒）

        Returns:
            bool: 插件是否就绪
        """
        if self.is_ready():
            return True

        if not self._connection_future:
            # 还未开始连接，立即启动
            logger.info(f"[{self.__class__.__name__}] 首次使用，启动连接...")
            self.connect_async()

        try:
            # 等待连接完成
            result = self._connection_future.result(timeout=timeout)
            return result
        except TimeoutError:
            logger.warning(f"[{self.__class__.__name__}] 等待连接超时({timeout}s)")
            return False
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 等待连接异常: {e}")
            return False

    def cleanup(self) -> None:
        """强制释放线程池资源"""
        try:
            if hasattr(self, '_executor') and self._executor is not None:
                self._executor.shutdown(wait=True, cancel_futures=True)
                self._executor = None
        except Exception as e:
            logger.warning(f"[{self.__class__.__name__}] cleanup failed: {e}")
        super().cleanup()

    def __del__(self):
        """析构函数，强制释放线程池"""
        try:
            if hasattr(self, '_executor') and self._executor:
                self._executor.shutdown(wait=True)
                self._executor = None
        except Exception:
            pass


class IAnalysisPlugin(IPlugin):
    """分析工具插件接口"""

    @abstractmethod
    def get_analysis_name(self) -> str:
        """获取分析工具名称"""
        pass

    @abstractmethod
    def analyze(self, data: Any, **params) -> Dict[str, Any]:
        """
        执行分析

        Args:
            data: 输入数据
            **params: 分析参数

        Returns:
            分析结果
        """
        pass

    def get_analysis_parameters(self) -> Dict[str, Any]:
        """获取分析参数定义"""
        return {}


class IUIComponentPlugin(IPlugin):
    """UI组件插件接口"""

    @abstractmethod
    def get_component_name(self) -> str:
        """获取组件名称"""
        pass

    @abstractmethod
    def create_widget(self, parent: Optional['QWidget'] = None) -> 'QWidget':
        """
        创建组件

        Args:
            parent: 父组件

        Returns:
            QWidget: 组件实例
        """
        pass

    def get_menu_actions(self) -> List['QAction']:
        """
        获取菜单动作

        Returns:
            动作列表
        """
        return []

    def get_toolbar_actions(self) -> List['QAction']:
        """
        获取工具栏动作

        Returns:
            动作列表
        """
        return []


class IExportPlugin(IPlugin):
    """导出插件接口"""

    @abstractmethod
    def get_export_name(self) -> str:
        """获取导出器名称"""
        pass

    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """获取支持的格式"""
        pass

    @abstractmethod
    def export_data(self, data: Any, format_type: str, output_path: str, **params) -> bool:
        """
        导出数据

        Args:
            data: 要导出的数据
            format_type: 格式类型
            output_path: 输出路径
            **params: 其他参数

        Returns:
            bool: 导出是否成功
        """
        pass


class INotificationPlugin(IPlugin):
    """通知插件接口"""

    @abstractmethod
    def get_notification_name(self) -> str:
        """获取通知器名称"""
        pass

    @abstractmethod
    def send_notification(self, title: str, message: str, **params) -> bool:
        """
        发送通知

        Args:
            title: 标题
            message: 消息内容
            **params: 其他参数

        Returns:
            bool: 发送是否成功
        """
        pass

    def get_notification_types(self) -> List[str]:
        """获取支持的通知类型"""
        return ["info", "warning", "error"]


class IChartToolPlugin(IPlugin):
    """图表工具插件接口"""

    @abstractmethod
    def get_tool_name(self) -> str:
        """获取工具名称"""
        pass

    @abstractmethod
    def get_tool_icon(self) -> str:
        """获取工具图标路径"""
        pass

    @abstractmethod
    def activate_tool(self, chart_widget: QWidget) -> None:
        """
        激活工具

        Args:
            chart_widget: 图表组件
        """
        pass

    @abstractmethod
    def deactivate_tool(self) -> None:
        """停用工具"""
        pass


class PluginContext:
    """插件上下文"""

    def __init__(self, main_window, data_manager, config_manager):
        """
        初始化插件上下文

        Args:
            main_window: 主窗口
            data_manager: 数据管理器
            config_manager: 配置管理器
            # log_manager: 已迁移到Loguru日志系统
        """
        self.main_window = main_window
        self.data_manager = data_manager
        self.config_manager = config_manager
        # log_manager已迁移到Loguru
        self._event_handlers: Dict[str, List[Callable]] = {}

    def register_event_handler(self, event_name: str, handler: Callable) -> None:
        """
        注册事件处理器

        Args:
            event_name: 事件名称
            handler: 处理器函数
        """
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)

    def emit_event(self, event_name: str, *args, **kwargs) -> None:
        """
        发射事件

        Args:
            event_name: 事件名称
            *args: 位置参数
            **kwargs: 关键字参数
        """
        if event_name in self._event_handlers:
            for handler in self._event_handlers[event_name]:
                try:
                    handler(*args, **kwargs)
                except Exception as e:
                    logger.error(f"事件处理器执行失败: {e}")

    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """
        获取插件配置

        Args:
            plugin_name: 插件名称

        Returns:
            插件配置
        """
        return self.config_manager.get_plugin_config(plugin_name, {})

    def save_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> None:
        """
        保存插件配置

        Args:
            plugin_name: 插件名称
            config: 配置数据
        """
        self.config_manager.save_plugin_config(plugin_name, config)

# 插件装饰器


def plugin_metadata(**kwargs):
    """
    插件元数据装饰器

    Args:
        **kwargs: 元数据参数
    """
    def decorator(cls):
        cls._plugin_metadata = PluginMetadata(**kwargs)
        return cls
    return decorator


def register_plugin(plugin_type: PluginType):
    """
    插件注册装饰器

    Args:
        plugin_type: 插件类型
    """
    def decorator(cls):
        cls._plugin_type = plugin_type
        return cls
    return decorator
