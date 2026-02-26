from loguru import logger
#!/usr/bin/env python3
"""
FactorWeave-Quant策略管理系统

统一的策略管理、执行和评估框架
集成数据库存储，使用系统统一组件
"""

import atexit
from typing import Dict, List, Optional, Any, Type

# 使用系统统一组件
from core.system_adapters import get_config

# 导入核心组件
from .base_strategy import (
    BaseStrategy, StrategySignal, StrategyParameter, StrategyType, SignalType
)
from .strategy_registry import (
    StrategyRegistry, get_strategy_registry, register_strategy
)
from .strategy_engine import (
    StrategyEngine, get_strategy_engine, initialize_strategy_engine
)
from .strategy_factory import (
    StrategyFactory, get_strategy_factory
)
from .parameter_manager import (
    StrategyParameterManager, ParameterValidator, get_parameter_manager
)
# 使用统一性能监控系统
from core.performance import get_performance_monitor as get_performance_evaluator
from .lifecycle_manager import (
    StrategyLifecycleManager, get_lifecycle_manager
)
from .strategy_database import (
    StrategyDatabaseManager, get_strategy_database_manager, initialize_strategy_database
)
from .builtin_strategies import *

# 版本信息
__version__ = "2.0.0"
__author__ = "FactorWeave 团队"

# 全局管理器实例
_managers_initialized = False
logger = logger.bind(module=__name__)


def initialize_strategy_system(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    初始化策略管理系统

    Args:
        config: 系统配置，如果为None则使用默认配置

    Returns:
        初始化的管理器实例字典
    """
    global _managers_initialized

    if _managers_initialized:
        logger.warning("策略系统已经初始化")
        return get_system_managers()

    try:
        logger.info("开始初始化策略管理系统...")

        # 获取配置
        system_config = get_config()
        if config:
            system_config.update(config)

        strategy_config = system_config.get('strategy_system', {})

        # 初始化数据库管理器
        db_config = strategy_config.get('database', {})
        db_path = db_config.get('path')
        db_manager = initialize_strategy_database(db_path)
        logger.info("数据库管理器初始化完成")

        # 初始化策略注册器
        registry = get_strategy_registry()
        logger.info("策略注册器初始化完成")

        # 初始化执行引擎
        engine_config = strategy_config.get('engine', {})
        engine = initialize_strategy_engine(
            max_workers=engine_config.get('max_workers'),
            cache_size=engine_config.get('cache_size', 1000),
            cache_ttl=engine_config.get('cache_ttl', 3600)
        )
        logger.info("策略执行引擎初始化完成")

        # 初始化其他管理器
        factory = get_strategy_factory()
        parameter_manager = get_parameter_manager()
        performance_evaluator = get_performance_evaluator()
        lifecycle_manager = get_lifecycle_manager()

        logger.info("所有管理器初始化完成")

        # 自动发现和注册内置策略
        _register_builtin_strategies(registry)

        # 自动发现外部策略
        discovery_config = strategy_config.get('discovery', {})
        if discovery_config.get('auto_discover', True):
            search_paths = discovery_config.get('paths', ['strategies'])
            discovered_count = registry.auto_discover_strategies(search_paths)
            logger.info(f"自动发现策略: {discovered_count}个")

        _managers_initialized = True

        # 注册清理函数
        atexit.register(shutdown_strategy_system)

        managers = get_system_managers()
        logger.info("策略管理系统初始化完成")

        return managers

    except Exception as e:
        logger.error(f"策略管理系统初始化失败: {e}")
        raise


def get_system_managers() -> Dict[str, Any]:
    """
    获取系统管理器实例

    Returns:
        管理器实例字典
    """
    return {
        'database': get_strategy_database_manager(),
        'registry': get_strategy_registry(),
        'engine': get_strategy_engine(),
        'factory': get_strategy_factory(),
        'parameter_manager': get_parameter_manager(),
        'performance_evaluator': get_performance_evaluator(),
        'lifecycle_manager': get_lifecycle_manager()
    }


def get_system_stats() -> Dict[str, Any]:
    """
    获取系统统计信息

    Returns:
        系统统计信息
    """
    try:
        managers = get_system_managers()

        stats = {
            'version': __version__,
            'initialized': _managers_initialized,
            'registry': managers['registry'].get_registry_stats(),
            'engine': managers['engine'].get_engine_stats(),
            'database': managers['database'].get_database_stats(),
            'factory': managers['factory'].get_factory_stats(),
            'parameter_manager': managers['parameter_manager'].get_manager_stats(),
            'performance_evaluator': managers['performance_evaluator'].get_evaluator_stats(),
            'lifecycle_manager': managers['lifecycle_manager'].get_manager_stats()
        }

        return stats

    except Exception as e:
        logger.error(f"获取系统统计失败: {e}")
        return {'error': str(e)}


def shutdown_strategy_system():
    """关闭策略管理系统"""
    global _managers_initialized

    if not _managers_initialized:
        return

    try:
        logger.info("正在关闭策略管理系统...")

        # 获取管理器
        managers = get_system_managers()

        # 关闭执行引擎
        managers['engine'].shutdown(wait=True)
        logger.info("策略执行引擎已关闭")

        # 关闭生命周期管理器
        managers['lifecycle_manager'].shutdown()
        logger.info("生命周期管理器已关闭")

        # 清理数据库连接
        try:
            managers['database'].cleanup_old_data()
        except Exception as e:
            logger.warning(f"数据库清理失败: {e}")

        _managers_initialized = False
        logger.info("策略管理系统已关闭")

    except Exception as e:
        logger.error(f"关闭策略管理系统失败: {e}")


def _register_builtin_strategies(registry: StrategyRegistry):
    """注册内置策略"""
    try:
        # 内置策略会通过装饰器自动注册
        # 这里只需要确保模块被导入
        builtin_strategies = [
            'MAStrategy', 'MACDStrategy', 'RSIStrategy',
            'KDJStrategy', 'BollingerBandsStrategy'
        ]

        registered_count = 0
        for strategy_name in builtin_strategies:
            if registry.get_strategy_class(strategy_name):
                registered_count += 1

        logger.info(f"内置策略注册完成: {registered_count}个")

    except Exception as e:
        logger.warning(f"注册内置策略失败: {e}")

# 便捷函数


def create_strategy(strategy_name: str, **kwargs) -> Optional[BaseStrategy]:
    """
    创建策略实例

    Args:
        strategy_name: 策略名称
        **kwargs: 策略参数

    Returns:
        策略实例或None
    """
    try:
        factory = get_strategy_factory()
        return factory.create_strategy(strategy_name, **kwargs)
    except Exception as e:
        logger.error(f"创建策略实例失败 {strategy_name}: {e}")
        return None


def execute_strategy(strategy_name: str, data, **kwargs) -> tuple:
    """
    执行策略

    Args:
        strategy_name: 策略名称
        data: 市场数据
        **kwargs: 执行参数

    Returns:
        (信号列表, 执行信息)
    """
    try:
        engine = get_strategy_engine()
        return engine.execute_strategy(strategy_name, data, **kwargs)
    except Exception as e:
        logger.error(f"执行策略失败 {strategy_name}: {e}")
        return [], {'success': False, 'error_message': str(e)}


def list_strategies(category: Optional[str] = None,
                    strategy_type: Optional[StrategyType] = None) -> List[str]:
    """
    列出可用策略

    Args:
        category: 策略分类过滤
        strategy_type: 策略类型过滤

    Returns:
        策略名称列表
    """
    try:
        registry = get_strategy_registry()
        return registry.list_strategies(category=category, strategy_type=strategy_type)
    except Exception as e:
        logger.error(f"列出策略失败: {e}")
        return []


def list_available_strategies() -> List[str]:
    """
    列出所有可用策略（简化版本）

    Returns:
        策略名称列表
    """
    return list_strategies()


def get_strategy_info(strategy_name: str) -> Optional[Dict[str, Any]]:
    """
    获取策略信息

    Args:
        strategy_name: 策略名称

    Returns:
        策略信息字典或None
    """
    try:
        registry = get_strategy_registry()
        return registry.get_strategy_metadata(strategy_name)
    except Exception as e:
        logger.error(f"获取策略信息失败 {strategy_name}: {e}")
        return None


def optimize_strategy_parameters(strategy_name: str, data,
                                 parameter_ranges: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """
    优化策略参数

    Args:
        strategy_name: 策略名称
        data: 市场数据
        parameter_ranges: 参数范围
        **kwargs: 优化参数

    Returns:
        优化结果
    """
    try:
        parameter_manager = get_parameter_manager()
        return parameter_manager.optimize_parameters(
            strategy_name, data, parameter_ranges, **kwargs
        )
    except Exception as e:
        logger.error(f"参数优化失败 {strategy_name}: {e}")
        return {'success': False, 'error_message': str(e)}


def evaluate_strategy_performance(strategy_name: str, signals: List[StrategySignal],
                                  data, **kwargs) -> Dict[str, Any]:
    """
    评估策略性能

    Args:
        strategy_name: 策略名称
        signals: 策略信号
        data: 市场数据
        **kwargs: 评估参数

    Returns:
        性能评估结果
    """
    try:
        evaluator = get_performance_evaluator()
        metrics = evaluator.evaluate_strategy_performance(
            signals, data, **kwargs)
        result = metrics.to_dict()
        result['strategy_name'] = strategy_name
        result['success'] = True
        return result
    except Exception as e:
        logger.error(f"性能评估失败 {strategy_name}: {e}")
        return {'success': False, 'error_message': str(e), 'strategy_name': strategy_name}


# 导出的公共接口
__all__ = [
    # 核心类
    'BaseStrategy', 'StrategySignal', 'StrategyParameter', 'StrategyType', 'SignalType',
    'StrategyRegistry', 'StrategyEngine', 'StrategyFactory',
    'StrategyParameterManager', 'ParameterValidator', 'StrategyPerformanceEvaluator',
    'StrategyLifecycleManager', 'StrategyDatabaseManager',

    # 装饰器
    'register_strategy',

    # 管理器获取函数
    'get_strategy_registry', 'get_strategy_engine', 'get_strategy_factory',
    'get_parameter_manager', 'get_performance_evaluator', 'get_lifecycle_manager',
    'get_strategy_database_manager',

    # 系统管理函数
    'initialize_strategy_system', 'get_system_managers', 'get_system_stats',
    'shutdown_strategy_system',

    # 便捷函数
    'create_strategy', 'execute_strategy', 'list_strategies', 'get_strategy_info',
    'optimize_strategy_parameters', 'evaluate_strategy_performance',

    # 版本信息
    '__version__', '__author__'
]
