"""
TET (Transform-Extract-Transform) 统一数据源框架

该模块提供了统一的数据源管理框架，支持：
- 传统数据源的TET化改造
- 插件化数据源管理
- 统一的数据接口和适配器
- 智能路由和故障转移
"""

try:
    from .pipeline.enhanced_tet_pipeline import EnhancedTETDataPipeline
except ImportError:
    EnhancedTETDataPipeline = None

try:
    from .data_sources.registry.tet_provider_registry import TETProviderRegistry
except ImportError:
    TETProviderRegistry = None

try:
    from .data_sources.registry.tet_provider_factory import TETProviderFactory
except ImportError:
    TETProviderFactory = None

__all__ = [
    'EnhancedTETDataPipeline',
    'TETProviderRegistry',
    'TETProviderFactory'
]

__version__ = '1.0.0'