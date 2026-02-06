"""
适配器模块
包含各种适配器类，用于兼容不同的接口和实现
"""

from .legacy_cache_adapter import (
    LegacyCacheAdapter,
    AsyncLegacyCacheAdapter,
    create_legacy_cache_adapter
)

__all__ = [
    'LegacyCacheAdapter',
    'AsyncLegacyCacheAdapter',
    'create_legacy_cache_adapter'
]
