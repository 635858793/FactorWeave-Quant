"""
性能监控模块

提供现代化的性能监控UI组件
"""

# 导入异步工作线程
from .workers.async_workers import (
    AsyncDataWorker,
    AsyncStrategyWorker,
    SystemHealthCheckThread,
    AlertHistoryWorker,
    AsyncDataSignals,
    AlertHistorySignals,
    EmailTestWorker,
    SMSTestWorker,
    NotificationTestSignals
)

# 导入UI组件
from .components.metric_card import ModernMetricCard
from .components.performance_chart import ModernPerformanceChart

# 导入标签页组件 - 2024量化交易优化版
from .tabs.system_monitor_tab import ModernSystemMonitorTab
from .tabs.strategy_performance_tab import ModernStrategyPerformanceTab
from .tabs.algorithm_optimization_tab import ModernAlgorithmOptimizationTab
from .tabs.risk_control_center_tab import ModernRiskControlCenterTab
from .tabs.trading_execution_monitor_tab import ModernTradingExecutionMonitorTab
from .tabs.system_health_tab import ModernSystemHealthTab
# 已删除的标签页：UI优化、深度分析、算法性能、自动调优、告警配置
# 已合并或升级为新的专业量化交易标签页

# 导入主要组件
from .unified_performance_widget import ModernUnifiedPerformanceWidget

# 注意：EnhancedStockPoolSettingsDialog 和 DataImportMonitoringWidget
# 在重构过程中发现这些类可能不存在或未正确迁移，暂时注释掉

# 为了兼容性，重新导出所有类
__all__ = [
    'AsyncDataWorker',
    'AsyncStrategyWorker',
    'SystemHealthCheckThread',
    'AlertHistoryWorker',
    'AsyncDataSignals',
    'AlertHistorySignals',
    'ModernMetricCard',
    'ModernPerformanceChart',
    'ModernSystemMonitorTab',
    'ModernStrategyPerformanceTab',
    'ModernAlgorithmOptimizationTab',
    'ModernRiskControlCenterTab',
    'ModernTradingExecutionMonitorTab',
    'ModernSystemHealthTab',
    # 已删除的标签页类名：
    # 'ModernUIOptimizationTab', 'ModernDeepAnalysisTab',
    # 'ModernAlgorithmPerformanceTab', 'ModernAutoTuningTab', 'ModernAlertConfigTab'
    'ModernUnifiedPerformanceWidget',
    # 'EnhancedStockPoolSettingsDialog',  # 暂时注释，类不存在
    # 'DataImportMonitoringWidget',       # 暂时注释，类不存在
]
