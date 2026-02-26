"""
回测模块
包含高性能回测引擎和优化器
"""

from loguru import logger

__all__ = [
    'UltraPerformanceOptimizer',
    'BacktestOptimizer',
    'BacktestValidator',
    'JITOptimizer',
    'AsyncIOManager',
    'SmartDataCache',
    'ResourceManager',
    'UnifiedBacktestEngine',
    'ProfessionalUISystem',
    'RealTimeBacktestMonitor',
    'get_async_io_manager',
    'get_smart_data_cache',
    'get_unified_cache_service',
    'migrate_to_unified_cache',
]


def __getattr__(name):
    """延迟导入优化器类"""
    if name == 'UltraPerformanceOptimizer':
        try:
            from .ultra_performance_optimizer import UltraPerformanceOptimizer
            return UltraPerformanceOptimizer
        except ImportError as e:
            logger.warning(f"无法导入 UltraPerformanceOptimizer: {e}")
            raise
    elif name == 'BacktestOptimizer':
        from .backtest_optimizer import BacktestOptimizer
        return BacktestOptimizer
    elif name == 'BacktestValidator':
        from .backtest_validator import BacktestValidator
        return BacktestValidator
    elif name == 'JITOptimizer':
        from .jit_optimizer import JITOptimizer
        return JITOptimizer
    elif name == 'AsyncIOManager':
        from .async_io_manager import AsyncIOManager
        return AsyncIOManager
    elif name == 'SmartDataCache':
        from .async_io_manager import SmartDataCache
        return SmartDataCache
    elif name == 'ResourceManager':
        from .resource_manager import ResourceManager
        return ResourceManager
    elif name == 'UnifiedBacktestEngine':
        from .unified_backtest_engine import UnifiedBacktestEngine
        return UnifiedBacktestEngine
    elif name == 'ProfessionalUISystem':
        from .professional_ui_system import ProfessionalUISystem
        return ProfessionalUISystem
    elif name == 'RealTimeBacktestMonitor':
        from .real_time_backtest_monitor import RealTimeBacktestMonitor
        return RealTimeBacktestMonitor
    elif name == 'get_async_io_manager':
        from .async_io_manager import get_async_io_manager
        return get_async_io_manager
    elif name == 'get_smart_data_cache':
        from .async_io_manager import get_smart_data_cache
        return get_smart_data_cache
    elif name == 'get_unified_cache_service':
        from .async_io_manager import get_unified_cache_service
        return get_unified_cache_service
    elif name == 'migrate_to_unified_cache':
        from .async_io_manager import migrate_to_unified_cache
        return migrate_to_unified_cache

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
