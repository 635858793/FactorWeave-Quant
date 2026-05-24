"""
统一数据源接口定义

本模块定义了FactorWeave-Quant系统中所有数据源必须实现的统一接口，
解决现有系统中多套数据访问接口并存的问题。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum
import asyncio


class ConnectionStatus(Enum):
    """连接状态枚举"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


class DataType(Enum):
    """数据类型枚举"""
    KLINE = "kline"          # K线数据
    TICK = "tick"            # 逐笔数据
    ORDER_BOOK = "order_book"  # 订单簿
    FINANCIAL = "financial"   # 财务数据
    NEWS = "news"            # 新闻数据
    FACTOR = "factor"        # 因子数据
    INDEX = "index"          # 指数数据


@dataclass
class ConnectionConfig:
    """统一连接配置"""

    # 基础连接信息
    host: str
    port: int

    # 认证信息
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    api_key: Optional[str] = None

    # 数据库信息
    database: Optional[str] = None
    schema: Optional[str] = None

    # 连接参数
    timeout: int = 30
    connect_timeout: int = 10
    read_timeout: int = 30
    write_timeout: int = 30

    # SSL配置
    ssl_enabled: bool = False
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None
    ssl_ca_path: Optional[str] = None

    # 连接池配置
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle: int = 1800

    # 重试配置
    retry_attempts: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0

    # 扩展参数
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        from dataclasses import asdict
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConnectionConfig':
        """从字典创建配置"""
        return cls(**data)

    def validate(self) -> List[str]:
        """验证配置有效性"""
        errors = []

        if not self.host:
            errors.append("Host is required")

        if not (1 <= self.port <= 65535):
            errors.append("Port must be between 1 and 65535")

        if self.timeout <= 0:
            errors.append("Timeout must be positive")

        if self.pool_size <= 0:
            errors.append("Pool size must be positive")

        return errors


@dataclass
class DataRequest:
    """数据请求对象"""

    # 基础请求信息
    data_type: DataType
    symbol: str

    # 时间范围
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # 数据参数
    frequency: Optional[str] = None  # 数据频率: 1m, 5m, 1d等
    fields: Optional[List[str]] = None  # 请求字段
    limit: Optional[int] = None  # 数据条数限制

    # 查询条件
    filters: Dict[str, Any] = field(default_factory=dict)

    # 请求选项
    use_cache: bool = True
    cache_ttl: int = 300  # 缓存TTL(秒)
    priority: int = 0     # 请求优先级

    # 扩展参数
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        from dataclasses import asdict
        result = asdict(self)
        # 处理枚举类型
        result['data_type'] = self.data_type.value
        # 处理datetime类型
        if self.start_time:
            result['start_time'] = self.start_time.isoformat()
        if self.end_time:
            result['end_time'] = self.end_time.isoformat()
        return result


@dataclass
class DataResponse:
    """数据响应对象"""

    # 响应状态
    success: bool
    message: str = ""
    error_code: Optional[str] = None

    # 数据内容
    data: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 响应信息
    source: Optional[str] = None  # 数据源名称
    timestamp: datetime = field(default_factory=datetime.now)
    request_id: Optional[str] = None

    # 性能信息
    response_time: float = 0.0  # 响应时间(秒)
    data_size: int = 0          # 数据大小(字节)

    # 缓存信息
    from_cache: bool = False
    cache_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        from dataclasses import asdict
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


@dataclass
class HealthStatus:
    """健康状态对象"""

    is_healthy: bool
    status_message: str = ""

    # 连接信息
    connection_status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    last_check_time: datetime = field(default_factory=datetime.now)

    # 性能指标
    response_time: float = 0.0
    success_rate: float = 0.0
    error_count: int = 0

    # 详细信息
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        from dataclasses import asdict
        result = asdict(self)
        result['connection_status'] = self.connection_status.value
        result['last_check_time'] = self.last_check_time.isoformat()
        return result


class IDataSource(ABC):
    """统一数据源接口

    所有数据源适配器必须实现此接口，提供统一的数据访问方式。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称"""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """数据源版本"""
        pass

    @property
    @abstractmethod
    def supported_data_types(self) -> List[DataType]:
        """支持的数据类型"""
        pass

    @abstractmethod
    async def connect(self, config: ConnectionConfig) -> bool:
        """连接数据源

        Args:
            config: 连接配置

        Returns:
            bool: 连接是否成功

        Raises:
            ConnectionError: 连接失败时抛出
        """
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """断开连接

        Returns:
            bool: 断开是否成功
        """
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """检查连接状态

        Returns:
            bool: 是否已连接
        """
        pass

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """健康检查

        Returns:
            HealthStatus: 健康状态信息
        """
        pass

    @abstractmethod
    async def get_data(self, request: DataRequest) -> DataResponse:
        """获取数据

        Args:
            request: 数据请求对象

        Returns:
            DataResponse: 数据响应对象

        Raises:
            DataSourceError: 数据获取失败时抛出
        """
        pass

    @abstractmethod
    async def validate_request(self, request: DataRequest) -> List[str]:
        """验证请求参数

        Args:
            request: 数据请求对象

        Returns:
            List[str]: 验证错误列表，空列表表示验证通过
        """
        pass

    async def ping(self) -> float:
        """测试连接延迟

        Returns:
            float: 延迟时间(毫秒)
        """
        start_time = asyncio.get_event_loop().time()

        # 执行简单的健康检查
        await self.health_check()

        end_time = asyncio.get_event_loop().time()
        return (end_time - start_time) * 1000

    async def get_supported_symbols(self) -> List[str]:
        """获取支持的股票代码列表

        Returns:
            List[str]: 支持的股票代码列表
        """
        # 默认实现，子类可以重写
        return []

    async def get_data_info(self, data_type: DataType) -> Dict[str, Any]:
        """获取数据类型信息

        Args:
            data_type: 数据类型

        Returns:
            Dict[str, Any]: 数据类型信息
        """
        # 默认实现，子类可以重写
        return {
            "data_type": data_type.value,
            "supported": data_type in self.supported_data_types,
            "description": f"{data_type.value} data from {self.name}"
        }


class DataSourceError(Exception):
    """数据源异常基类"""

    def __init__(self, message: str, error_code: Optional[str] = None,
                 source: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.source = source


class ConnectionError(DataSourceError):
    """连接异常"""
    pass


class AuthenticationError(DataSourceError):
    """认证异常"""
    pass


class DataNotFoundError(DataSourceError):
    """数据未找到异常"""
    pass


class RateLimitError(DataSourceError):
    """频率限制异常"""
    pass


class ValidationError(DataSourceError):
    """参数验证异常"""
    pass
