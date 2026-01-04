"""
FactorWeave-Quant 统一接口模块

本模块定义了系统中所有核心接口，实现统一的数据访问和插件管理标准。
"""

from .data_source import IDataSource, ConnectionConfig, DataRequest, DataResponse
from .plugin import IPlugin, PluginInfo, PluginLifecycle
from .cache import ICache, CacheConfig
from .circuit_breaker import ICircuitBreaker, CircuitBreakerConfig

__all__ = [
    # 数据源接口
    'IDataSource',
    'ConnectionConfig',
    'DataRequest',
    'DataResponse',

    # 插件接口
    'IPlugin',
    'PluginInfo',
    'PluginLifecycle',

    # 缓存接口
    'ICache',
    'CacheConfig',

    # 熔断器接口
    'ICircuitBreaker',
    'CircuitBreakerConfig',
]
