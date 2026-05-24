"""
TET数据源基础组件

提供TET框架的核心接口和基类
"""

try:
    from .tet_data_source_interface import ITETDataSource, TETDataSourceCapability
except ImportError:
    ITETDataSource = None
    TETDataSourceCapability = None

try:
    from .tet_adapter_base import TETAdapterBase
except ImportError:
    TETAdapterBase = None

try:
    from .tet_plugin_validator import TETPluginValidator
except ImportError:
    TETPluginValidator = None

__all__ = [
    'ITETDataSource',
    'TETDataSourceCapability',
    'TETAdapterBase',
    'TETPluginValidator'
]