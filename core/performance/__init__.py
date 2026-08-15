"""
统一性能监控模块 - 唯一入口点

FactorWeave-Quant 2.0 统一性能监控系统
整合所有性能监控功能到一个完整的解决方案中

主要功能：
- 系统资源监控（CPU、内存、磁盘、网络）
- UI性能优化（懒加载、缓存、渐进式加载）
- 策略性能评估（交易指标、回测分析）
- 算法性能评估（形态识别、效率分析）
- 自动调优系统（参数优化）
- 实时监控与分析

使用方法：
```python
from core.performance import get_performance_monitor, measure_performance

# 获取全局监控实例
monitor = get_performance_monitor()

# 使用装饰器测量性能
@measure_performance("my_function")
def my_function():
    pass

# 使用上下文管理器
with monitor.measure_time("operation"):
    # 执行操作
    pass

# 记录自定义指标
monitor.record_metric("custom_metric", 123.45, PerformanceCategory.ALGORITHM, MetricType.GAUGE)

# 评估策略性能
performance = monitor.evaluate_strategy_performance(returns_series)

# 导出性能报告
report = monitor.export_report()
```
"""

from .unified_monitor import (
    # 主要类
    UnifiedPerformanceMonitor,
    PerformanceMetric,
    PerformanceStats,
    PerformanceCache,
    TradeResult,

    # 枚举类
    PerformanceCategory,
    MetricType,
    TuningDirection,

    # 数据类
    TuningState,
    CacheEntry,

    # 组件类
    SystemMonitor,
    UIOptimizer,
    PerformanceAutoTuner,

    # 全局函数
    get_performance_monitor,
    measure_performance,
    measure_event,
    measure_data_load
)

# R243-B-002 (2026-08-04): 补全统一资源监控/数据更新管理器导出
from .resource_monitor import (
    UnifiedResourceMonitor,
    ResourceAlert,
    ResourceUsage,
    ResourceThreshold,
    ResourceType,
    AlertSeverity,
    get_resource_monitor,
    initialize_resource_monitor,
)
from .data_update_manager import (
    PerformanceDataUpdateManager,
    UpdateStrategy,
    get_data_update_manager,
)

# 向后兼容别名
PerformanceMonitor = UnifiedPerformanceMonitor

__all__ = [
    # 核心类
    'UnifiedPerformanceMonitor',
    'PerformanceMonitor',  # 向后兼容
    'PerformanceMetric',
    'PerformanceStats',
    'PerformanceCache',
    'TradeResult',

    # 枚举
    'PerformanceCategory',
    'MetricType',
    'TuningDirection',

    # 数据类
    'TuningState',
    'CacheEntry',

    # 组件
    'SystemMonitor',
    'UIOptimizer',
    'PerformanceAutoTuner',

    # 全局函数
    'get_performance_monitor',
    'measure_performance',
    'measure_event',
    'measure_data_load',

    # R243-B-002: 统一资源监控/数据更新管理器导出
    'UnifiedResourceMonitor',
    'ResourceAlert',
    'ResourceUsage',
    'ResourceThreshold',
    'ResourceType',
    'AlertSeverity',
    'get_resource_monitor',
    'initialize_resource_monitor',
    'PerformanceDataUpdateManager',
    'UpdateStrategy',
    'get_data_update_manager'
]

# 版本信息
__version__ = "2.0.0"
__author__ = "FactorWeave-Quant Team"
