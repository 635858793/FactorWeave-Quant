"""
TET数据源统一管理模块

提供标准化的数据源接口、适配器和提供商实现
"""

try:
    from .base.tet_data_source_interface import ITETDataSource
except ImportError:
    ITETDataSource = None

try:
    from .base.tet_adapter_base import TETAdapterBase
except ImportError:
    TETAdapterBase = None

try:
    from .registry.tet_provider_registry import TETProviderRegistry
except ImportError:
    TETProviderRegistry = None

__all__ = [
    'ITETDataSource',
    'TETAdapterBase',
    'TETProviderRegistry'
]