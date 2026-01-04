"""
基础插件模板

提供生产级插件的标准实现框架，包括：
- 异步初始化
- 状态管理
- 配置管理
- 错误处理
- 健康检查

使用方法：
1. 继承 BasePluginTemplate
2. 实现必要的抽象方法
3. 根据需要覆盖其他方法
"""

from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
import time
from datetime import datetime
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, Future

from core.data_source_extensions import IDataSourcePlugin, PluginInfo, HealthCheckResult
from core.plugin_types import PluginType, AssetType, DataType
from plugins.plugin_interface import PluginLifecycle


class BasePluginTemplate(IDataSourcePlugin, ABC):
    """
    基础插件模板

    提供生产级插件的标准实现，子类只需实现核心业务逻辑即可
    """

    def __init__(self):
        """初始化插件"""
        # 显式调用IDataSourcePlugin.__init__以确保plugin_state等属性被设置
        IDataSourcePlugin.__init__(self)

        # 确保plugin_state和initialized属性已设置（防御性检查）
        if not hasattr(self, 'plugin_state'):
            from plugins.plugin_interface import PluginLifecycle
            self.plugin_state = PluginLifecycle.CREATED
        if not hasattr(self, 'initialized'):
            self.initialized = False
        if not hasattr(self, 'last_error'):
            self.last_error = None

        self.logger = logger.bind(module=self.__class__.__name__)

        # 配置
        self.config = {}
        self.DEFAULT_CONFIG = self._get_default_config()

        # 插件基本信息（子类应覆盖）- 使用防御性设置，不覆盖子类已设置的值
        if not hasattr(self, 'plugin_id'):
            self.plugin_id = f"data_sources.{self.__class__.__name__}"
        if not hasattr(self, 'name'):
            self.name = "未命名插件"
        if not hasattr(self, 'version'):
            self.version = "1.0.0"
        if not hasattr(self, 'description'):
            self.description = "插件描述"
        if not hasattr(self, 'author'):
            self.author = "FactorWeave-Quant 开发团队"

        # 插件类型标识（子类应覆盖）
        if not hasattr(self, 'plugin_type'):
            self.plugin_type = PluginType.DATA_SOURCE_STOCK

        # 线程池（用于异步连接）
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"{self.name}_conn")

        # 健康检查
        self._last_health_check = 0
        self._health_check_interval = 300  # 5分钟
        self._health_score = 1.0

        # 统计信息
        self._stats = {
            'total_requests': 0,
            'failed_requests': 0,
            'last_request_time': None,
            'average_response_time': 0.0
        }

    @abstractmethod
    def _get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置

        子类必须实现，返回插件特定的默认配置

        Returns:
            Dict[str, Any]: 默认配置字典
        """
        return {
            'timeout': 30,
            'max_retries': 3,
            'cache_duration': 300,
        }

    def initialize(self, config: Dict[str, Any] = None) -> bool:
        """
        同步初始化插件（快速，不做网络连接）

        Args:
            config: 配置参数

        Returns:
            bool: 初始化是否成功
        """
        try:
            self.plugin_state = PluginLifecycle.INITIALIZING

            # 合并配置
            merged = self.DEFAULT_CONFIG.copy()
            merged.update(config or {})
            self.config = merged

            # 依赖检查
            if not self._check_dependencies():
                raise ImportError("依赖检查失败")

            # 验证配置
            if not self._validate_config():
                raise ValueError("配置验证失败")

            # 标记初始化完成
            self.initialized = True
            self.plugin_state = PluginLifecycle.INITIALIZED
            self.logger.info(f"{self.name} 初始化成功")

            return True

        except Exception as e:
            self.initialized = False
            self.last_error = str(e)
            self.plugin_state = PluginLifecycle.FAILED
            self.logger.error(f"{self.name} 初始化失败: {e}")
            return False

    @abstractmethod
    def _check_dependencies(self) -> bool:
        """
        检查依赖是否满足

        子类应实现此方法，检查必要的第三方库、API密钥等

        Returns:
            bool: 依赖是否满足
        """
        return True

    def _validate_config(self) -> bool:
        """
        验证配置是否有效

        子类可以覆盖此方法实现特定的配置验证逻辑

        Returns:
            bool: 配置是否有效
        """
        # 基础验证
        if 'timeout' in self.config and self.config['timeout'] <= 0:
            self.logger.error("timeout 必须大于0")
            return False

        if 'max_retries' in self.config and self.config['max_retries'] < 0:
            self.logger.error("max_retries 必须大于等于0")
            return False

        return True

    def _do_connect(self) -> bool:
        """
        异步连接实现（后台线程执行）

        子类应实现此方法，执行实际的连接和测试逻辑

        Returns:
            bool: 连接是否成功
        """
        try:
            self.plugin_state = PluginLifecycle.CONNECTING
            self.logger.info(f"{self.name} 开始连接...")

            # 子类实现具体连接逻辑
            if self._establish_connection():
                self.plugin_state = PluginLifecycle.CONNECTED
                self.logger.info(f"{self.name} 连接成功")
                return True
            else:
                self.plugin_state = PluginLifecycle.FAILED
                self.logger.error(f"{self.name} 连接失败")
                return False

        except Exception as e:
            self.plugin_state = PluginLifecycle.FAILED
            self.last_error = str(e)
            self.logger.error(f"{self.name} 连接异常: {e}")
            return False

    @abstractmethod
    def _establish_connection(self) -> bool:
        """
        建立连接

        子类必须实现，执行实际的连接逻辑（如测试API、建立WebSocket等）

        Returns:
            bool: 连接是否成功
        """
        return True

    def is_connected(self) -> bool:
        """
        检查是否已连接

        Returns:
            bool: 是否已连接
        """
        return self.initialized and self.plugin_state == PluginLifecycle.CONNECTED

    def health_check(self) -> HealthCheckResult:
        """
        健康检查

        Returns:
            HealthCheckResult: 健康检查结果
        """
        try:
            # 避免频繁检查
            current_time = time.time()
            if current_time - self._last_health_check < self._health_check_interval:
                return HealthCheckResult(
                    is_healthy=True,
                    message=f"健康度: {self._health_score:.2f}",
                    extra_info={'health_score': self._health_score, 'cached': True}
                )

            self._last_health_check = current_time

            # 执行健康检查
            is_healthy = self._perform_health_check()

            # 计算健康度
            if is_healthy:
                self._health_score = min(1.0, self._health_score + 0.1)
            else:
                self._health_score = max(0.0, self._health_score - 0.2)

            # 计算错误率
            error_rate = 0.0
            if self._stats['total_requests'] > 0:
                error_rate = self._stats['failed_requests'] / self._stats['total_requests']

            return HealthCheckResult(
                is_healthy=is_healthy and self._health_score > 0.5,
                message=f"健康度: {self._health_score:.2f}, 错误率: {error_rate:.2%}",
                extra_info={
                    'health_score': self._health_score,
                    'error_rate': error_rate,
                    'total_requests': self._stats['total_requests'],
                    'failed_requests': self._stats['failed_requests']
                }
            )

        except Exception as e:
            self.logger.error(f"健康检查异常: {e}")
            return HealthCheckResult(
                is_healthy=False,
                message=f"健康检查失败: {e}",
                extra_info={'health_score': 0.0, 'error': str(e)}
            )

    @abstractmethod
    def _perform_health_check(self) -> bool:
        """
        执行健康检查

        子类应实现此方法，执行实际的健康检查逻辑

        Returns:
            bool: 是否健康
        """
        return self.is_connected()

    def disconnect(self):
        """断开连接"""
        try:
            self._cleanup()
            self.initialized = False
            self.plugin_state = PluginLifecycle.CREATED
            self.logger.info(f"{self.name} 已断开连接")
        except Exception as e:
            self.logger.error(f"断开连接失败: {e}")

    @abstractmethod
    def _cleanup(self):
        """
        清理资源

        子类应实现此方法，执行资源清理逻辑（如关闭连接、释放资源等）
        """
        pass

    def _record_request(self, success: bool, response_time: float = 0.0):
        """
        记录请求统计

        Args:
            success: 请求是否成功
            response_time: 响应时间（秒）
        """
        self._stats['total_requests'] += 1
        if not success:
            self._stats['failed_requests'] += 1

        self._stats['last_request_time'] = datetime.now()

        # 计算平均响应时间（指数移动平均）
        if response_time > 0:
            alpha = 0.3
            self._stats['average_response_time'] = (
                alpha * response_time +
                (1 - alpha) * self._stats['average_response_time']
            )

    def get_plugin_info(self) -> PluginInfo:
        """
        获取插件信息

        Returns:
            PluginInfo: 插件信息对象
        """
        return PluginInfo(
            id=getattr(self, 'plugin_id', self.__class__.__name__),
            name=self.name,
            version=self.version,
            author=self.author,
            description=self.description,
            supported_asset_types=self.get_supported_asset_types(),
            supported_data_types=self.get_supported_data_types(),
            capabilities={}
        )

    @abstractmethod
    def get_supported_asset_types(self) -> List[AssetType]:
        """
        获取支持的资产类型

        子类必须实现

        Returns:
            List[AssetType]: 支持的资产类型列表
        """
        return [AssetType.STOCK_A]

    @abstractmethod
    def get_supported_data_types(self) -> List[DataType]:
        """
        获取支持的数据类型

        子类必须实现

        Returns:
            List[DataType]: 支持的数据类型列表
        """
        return [DataType.HISTORICAL_KLINE, DataType.REAL_TIME_QUOTE]

    # ===================================================================
    # 系统期望的数据源接口方法（鸭子类型）
    # ===================================================================

    def connect(self, **kwargs) -> bool:
        """
        连接数据源

        这是系统期望的连接方法，调用内部的_do_connect逻辑

        Args:
            **kwargs: 连接参数

        Returns:
            bool: 连接是否成功
        """
        try:
            if self.plugin_state == PluginLifecycle.CONNECTED:
                return True

            # 触发异步连接（如果尚未连接）
            if self.plugin_state == PluginLifecycle.CREATED:
                self.plugin_state = PluginLifecycle.INITIALIZING
                # 调用_do_connect建立连接
                result = self._do_connect()
                return result

            # 如果正在连接中，等待连接完成
            if self.plugin_state == PluginLifecycle.CONNECTING:
                return self.wait_until_ready(timeout=30.0)

            return self.is_ready()
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 连接失败: {e}")
            self.last_error = str(e)
            return False

    def get_connection_info(self):
        """
        获取连接信息

        Returns:
            ConnectionInfo: 连接信息对象
        """
        from core.data_source_extensions import ConnectionInfo
        return ConnectionInfo(
            source_name=self.name,
            is_connected=self.is_ready(),
            last_connected_time=datetime.now() if self.is_ready() else None,
            connection_state=self.plugin_state.value if hasattr(self.plugin_state, 'value') else str(self.plugin_state),
            error_message=self.last_error
        )

    def get_asset_list(self, asset_type, market: str = None):
        """
        获取资产列表

        Args:
            asset_type: 资产类型
            market: 市场代码（可选）

        Returns:
            List: 资产列表（通常为DataFrame或list）
        """
        logger.warning(f"[{self.__class__.__name__}] get_asset_list 未实现，返回空列表")
        return []

    def get_real_time_quotes(self, symbols: list):
        """
        获取实时行情数据

        Args:
            symbols: 股票代码列表

        Returns:
            pd.DataFrame: 实时行情数据
        """
        logger.warning(f"[{self.__class__.__name__}] get_real_time_quotes 未实现，返回空DataFrame")
        import pandas as pd
        return pd.DataFrame()

    @property
    def plugin_info(self):
        """
        plugin_info 属性（向后兼容）

        Returns:
            PluginInfo: 插件信息
        """
        return self.get_plugin_info()

    def __del__(self):
        """析构函数，清理线程池"""
        try:
            if hasattr(self, '_executor'):
                self._executor.shutdown(wait=False)
        except:
            pass


# 使用示例
if __name__ == "__main__":
    # 这是一个抽象类，不能直接实例化
    # 子类应该继承并实现所有抽象方法
    pass
