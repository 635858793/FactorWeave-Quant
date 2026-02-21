"""
回测模块
包含高性能回测引擎和优化器
"""

from loguru import logger

# 延迟导入，避免循环依赖和提高启动速度
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

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
