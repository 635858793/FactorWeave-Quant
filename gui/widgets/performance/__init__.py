"""
性能监控模块

提供现代化的性能监控UI组件
"""

# 延迟导入异步工作线程，避免在模块级别导入时卡住
_AsyncDataWorker = None
_AsyncStrategyWorker = None
_SystemHealthCheckThread = None
_AlertHistoryWorker = None
_AsyncDataSignals = None
_AlertHistorySignals = None
_EmailTestWorker = None
_SMSTestWorker = None
_NotificationTestSignals = None

def _import_async_workers():
    """延迟导入async_workers模块"""
    global _AsyncDataWorker, _AsyncStrategyWorker, _SystemHealthCheckThread
    global _AlertHistoryWorker, _AsyncDataSignals, _AlertHistorySignals
    global _EmailTestWorker, _SMSTestWorker, _NotificationTestSignals
    
    if _AsyncDataWorker is None:
        from .workers import (
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
        _AsyncDataWorker = AsyncDataWorker
        _AsyncStrategyWorker = AsyncStrategyWorker
        _SystemHealthCheckThread = SystemHealthCheckThread
        _AlertHistoryWorker = AlertHistoryWorker
        _AsyncDataSignals = AsyncDataSignals
        _AlertHistorySignals = AlertHistorySignals
        _EmailTestWorker = EmailTestWorker
        _SMSTestWorker = SMSTestWorker
        _NotificationTestSignals = NotificationTestSignals

def AsyncDataWorker(*args, **kwargs):
    """延迟导入AsyncDataWorker"""
    _import_async_workers()
    return _AsyncDataWorker(*args, **kwargs)

def AsyncStrategyWorker(*args, **kwargs):
    """延迟导入AsyncStrategyWorker"""
    _import_async_workers()
    return _AsyncStrategyWorker(*args, **kwargs)

def SystemHealthCheckThread(*args, **kwargs):
    """延迟导入SystemHealthCheckThread"""
    _import_async_workers()
    return _SystemHealthCheckThread(*args, **kwargs)

def AlertHistoryWorker(*args, **kwargs):
    """延迟导入AlertHistoryWorker"""
    _import_async_workers()
    return _AlertHistoryWorker(*args, **kwargs)

def AsyncDataSignals(*args, **kwargs):
    """延迟导入AsyncDataSignals"""
    _import_async_workers()
    return _AsyncDataSignals(*args, **kwargs)

def AlertHistorySignals(*args, **kwargs):
    """延迟导入AlertHistorySignals"""
    _import_async_workers()
    return _AlertHistorySignals(*args, **kwargs)

def EmailTestWorker(*args, **kwargs):
    """延迟导入EmailTestWorker"""
    _import_async_workers()
    return _EmailTestWorker(*args, **kwargs)

def SMSTestWorker(*args, **kwargs):
    """延迟导入SMSTestWorker"""
    _import_async_workers()
    return _SMSTestWorker(*args, **kwargs)

def NotificationTestSignals(*args, **kwargs):
    """延迟导入NotificationTestSignals"""
    _import_async_workers()
    return _NotificationTestSignals(*args, **kwargs)

# 延迟导入UI组件
_ModernMetricCard = None
_ModernPerformanceChart = None

def _import_components():
    """延迟导入UI组件"""
    global _ModernMetricCard, _ModernPerformanceChart
    
    if _ModernMetricCard is None:
        from .components.metric_card import ModernMetricCard
        from .components.performance_chart import ModernPerformanceChart
        _ModernMetricCard = ModernMetricCard
        _ModernPerformanceChart = ModernPerformanceChart

def ModernMetricCard(*args, **kwargs):
    """延迟导入ModernMetricCard"""
    _import_components()
    return _ModernMetricCard(*args, **kwargs)

def ModernPerformanceChart(*args, **kwargs):
    """延迟导入ModernPerformanceChart"""
    _import_components()
    return _ModernPerformanceChart(*args, **kwargs)

# 延迟导入标签页组件
_ModernSystemMonitorTab = None
_ModernStrategyPerformanceTab = None
_ModernAlgorithmOptimizationTab = None
_ModernRiskControlCenterTab = None
_ModernTradingExecutionMonitorTab = None
_ModernSystemHealthTab = None

def _import_tabs():
    """延迟导入标签页组件"""
    global _ModernSystemMonitorTab, _ModernStrategyPerformanceTab, _ModernAlgorithmOptimizationTab
    global _ModernRiskControlCenterTab, _ModernTradingExecutionMonitorTab, _ModernSystemHealthTab
    
    if _ModernSystemMonitorTab is None:
        from .tabs.system_monitor_tab import ModernSystemMonitorTab
        from .tabs.strategy_performance_tab import ModernStrategyPerformanceTab
        from .tabs.algorithm_optimization_tab import ModernAlgorithmOptimizationTab
        from .tabs.risk_control_center_tab import ModernRiskControlCenterTab
        from .tabs.trading_execution_monitor_tab import ModernTradingExecutionMonitorTab
        from .tabs.system_health_tab import ModernSystemHealthTab
        _ModernSystemMonitorTab = ModernSystemMonitorTab
        _ModernStrategyPerformanceTab = ModernStrategyPerformanceTab
        _ModernAlgorithmOptimizationTab = ModernAlgorithmOptimizationTab
        _ModernRiskControlCenterTab = ModernRiskControlCenterTab
        _ModernTradingExecutionMonitorTab = ModernTradingExecutionMonitorTab
        _ModernSystemHealthTab = ModernSystemHealthTab

def ModernSystemMonitorTab(*args, **kwargs):
    """延迟导入ModernSystemMonitorTab"""
    _import_tabs()
    return _ModernSystemMonitorTab(*args, **kwargs)

def ModernStrategyPerformanceTab(*args, **kwargs):
    """延迟导入ModernStrategyPerformanceTab"""
    _import_tabs()
    return _ModernStrategyPerformanceTab(*args, **kwargs)

def ModernAlgorithmOptimizationTab(*args, **kwargs):
    """延迟导入ModernAlgorithmOptimizationTab"""
    _import_tabs()
    return _ModernAlgorithmOptimizationTab(*args, **kwargs)

def ModernRiskControlCenterTab(*args, **kwargs):
    """延迟导入ModernRiskControlCenterTab"""
    _import_tabs()
    return _ModernRiskControlCenterTab(*args, **kwargs)

def ModernTradingExecutionMonitorTab(*args, **kwargs):
    """延迟导入ModernTradingExecutionMonitorTab"""
    _import_tabs()
    return _ModernTradingExecutionMonitorTab(*args, **kwargs)

def ModernSystemHealthTab(*args, **kwargs):
    """延迟导入ModernSystemHealthTab"""
    _import_tabs()
    return _ModernSystemHealthTab(*args, **kwargs)

# 延迟导入主要组件
_ModernUnifiedPerformanceWidget = None

def _import_unified_widget():
    """延迟导入主要组件"""
    global _ModernUnifiedPerformanceWidget
    
    if _ModernUnifiedPerformanceWidget is None:
        from .unified_performance_widget import ModernUnifiedPerformanceWidget
        _ModernUnifiedPerformanceWidget = ModernUnifiedPerformanceWidget

def ModernUnifiedPerformanceWidget(*args, **kwargs):
    """延迟导入ModernUnifiedPerformanceWidget"""
    _import_unified_widget()
    return _ModernUnifiedPerformanceWidget(*args, **kwargs)

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
