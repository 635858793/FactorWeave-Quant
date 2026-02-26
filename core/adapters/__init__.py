"""
适配器模块
包含各种适配器类，用于兼容不同的接口和实现
"""

from .legacy_cache_adapter import (
    LegacyCacheAdapter,
    SmartDataCacheAdapter,
    StrategyCacheAdapter,
    AsyncIOManagerAdapter,
    create_smart_cache_adapter,
    create_strategy_cache_adapter,
    create_async_io_adapter
)

__all__ = [
    'LegacyCacheAdapter',
    'SmartDataCacheAdapter',
    'StrategyCacheAdapter',
    'AsyncIOManagerAdapter',
    'create_smart_cache_adapter',
    'create_strategy_cache_adapter',
    'create_async_io_adapter'
]
