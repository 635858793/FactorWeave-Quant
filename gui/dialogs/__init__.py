"""
对话框模块

包含所有对话框类的导入和初始化。使用懒加载以兼容无头环境。
"""

__all__ = [
    'BaseDialog', 'LoadingIndicator',
    'SettingsDialog', 'AdvancedSearchDialog', 'StockDetailDialog',
    'CalculatorDialog', 'ConverterDialog', 'DataQualityDialog',
    'DataUsageTermsDialog', 'DataUsageManager', 'HistoryDataDialog',
    'TechnicalAnalysisDialog', 'DatabaseAdminDialog',
    'IntervalStatDialog', 'IntervalStatSettingsDialog',
    'SystemOptimizerDialog', 'show_system_optimizer_dialog', 'StartupGuidesDialog',
    'UnifiedDataManagementDialog', 'DataImportThread', 'DataExportThread',
    'DataManagementDialog', 'DataImportWizardDialog', 'ImportHistoryDialog',
    'DataExportDialog', 'AdvancedDataExportDialog',
    'StrategyManagerDialog', 'StrategyTemplateManager',
    'StrategyConfigValidator', 'StrategyEditorWidget',
    'EnhancedStrategyManagerDialog', 'EnhancedStrategyManagerDialogV3',
    'AIStrategyManagementDialog',
    'PluginManagerDialogUnified', 'PluginConfigDialog', 'EnhancedPluginManagerDialog',
    'IndicatorParamsDialog', 'IndicatorCombinationDialog',
    # R282: 补齐既有未接线对话框导出（模块文件均已存在，仅缺包级导出）
    'AlertRuleDialog', 'DuckDBConfigDialog', 'LLMConfigDialog', 'PortfolioDialog',
    'QualityReportDialog', 'RiskRuleConfigDialog', 'VersionManagerDialog',
    'WebGPUStatusDialog', 'ScheduledTaskDialog', 'CloudApiDialog',
    'IndicatorSelectionDialog', 'IndicatorMarketDialog', 'CompactAdvancedFilterDialog', 'PluginManagerDialog',
    'EnhancedPluginMarketDialog', 'ModelTrainingDialog', 'IntelligentModelSelectionDialog',
    'AIPredictionConfigDialog', 'PerformanceEvaluationDialog', 'PredictionAccuracyDialog',
    'ExternalAlertChannelConfigDialog', 'DistributedServiceMonitorDialog',
    'DistributedNodeMonitorDialog', 'ConnectionPoolManagerDialog',
    'DataSourcePluginConfigDialog', 'EnhancedConfigManagementDialog',
    'OrderManagementDialog', 'AccountManagementDialog', 'AdaptivePoolConfigDialog',
]

_LAZY_IMPORTS = {
    'BaseDialog': ('.base_dialog', ['BaseDialog']),
    'LoadingIndicator': ('.base_dialog', ['LoadingIndicator']),
    'SettingsDialog': ('.settings_dialog', ['SettingsDialog']),
    'AdvancedSearchDialog': ('.advanced_search_dialog', ['AdvancedSearchDialog']),
    'StockDetailDialog': ('.stock_detail_dialog', ['StockDetailDialog']),
    'CalculatorDialog': ('.calculator_dialog', ['CalculatorDialog']),
    'ConverterDialog': ('.converter_dialog', ['ConverterDialog']),
    'DataQualityDialog': ('.data_quality_dialog', ['DataQualityDialog']),
    'DataUsageTermsDialog': ('.data_usage_terms_dialog', ['DataUsageTermsDialog']),
    'DataUsageManager': ('.data_usage_terms_dialog', ['DataUsageManager']),
    'HistoryDataDialog': ('.history_data_dialog', ['HistoryDataDialog']),
    'TechnicalAnalysisDialog': ('.technical_analysis_dialog', ['TechnicalAnalysisDialog']),
    'IntervalStatDialog': ('.interval_stat_dialog', ['IntervalStatDialog']),
    'IntervalStatSettingsDialog': ('.interval_stat_settings_dialog', ['IntervalStatSettingsDialog']),
    'SystemOptimizerDialog': ('.system_optimizer_dialog', ['SystemOptimizerDialog']),
    'show_system_optimizer_dialog': ('.system_optimizer_dialog', ['show_system_optimizer_dialog']),
    'StartupGuidesDialog': ('.startup_guides_dialog', ['StartupGuidesDialog']),
    'UnifiedDataManagementDialog': ('.data_management_dialog_unified', ['UnifiedDataManagementDialog']),
    'DataImportThread': ('.data_management_dialog_unified', ['DataImportThread']),
    'DataExportThread': ('.data_management_dialog_unified', ['DataExportThread']),
    'StrategyManagerDialog': ('.strategy_manager_dialog', ['StrategyManagerDialog']),
    'StrategyTemplateManager': ('.strategy_manager_dialog', ['StrategyTemplateManager']),
    'StrategyConfigValidator': ('.strategy_manager_dialog', ['StrategyConfigValidator']),
    'StrategyEditorWidget': ('.strategy_manager_dialog', ['StrategyEditorWidget']),
    'PluginManagerDialogUnified': ('.plugin_manager_dialog_unified', ['PluginManagerDialogUnified']),
    'PluginConfigDialog': ('.plugin_manager_dialog_unified', ['PluginConfigDialog']),
    'IndicatorParamsDialog': ('.indicator_params_dialog', ['IndicatorParamsDialog']),
    'IndicatorCombinationDialog': ('.indicator_combination_dialog', ['IndicatorCombinationDialog']),
    # R282: 补齐既有未接线对话框懒加载（模块文件均已存在，仅缺包级导出）
    'AlertRuleDialog': ('.alert_rule_dialog', ['AlertRuleDialog']),
    'DuckDBConfigDialog': ('.duckdb_config_dialog', ['DuckDBConfigDialog']),
    'LLMConfigDialog': ('.llm_config_dialog', ['LLMConfigDialog']),
    'PortfolioDialog': ('.portfolio_dialog', ['PortfolioDialog']),
    'QualityReportDialog': ('.quality_report_dialog', ['QualityReportDialog']),
    'RiskRuleConfigDialog': ('.risk_rule_config_dialog', ['RiskRuleConfigDialog']),
    'VersionManagerDialog': ('.version_manager_dialog', ['VersionManagerDialog']),
    'WebGPUStatusDialog': ('.webgpu_status_dialog', ['WebGPUStatusDialog']),
    'ScheduledTaskDialog': ('.scheduled_task_dialog', ['ScheduledTaskDialog']),
    'CloudApiDialog': ('.cloud_api_dialog', ['CloudApiDialog']),
    'IndicatorSelectionDialog': ('.indicator_selection_dialog', ['IndicatorSelectionDialog']),
    'IndicatorMarketDialog': ('.indicator_market_dialog', ['IndicatorMarketDialog']),
    'CompactAdvancedFilterDialog': ('.batch_filter_dialog', ['CompactAdvancedFilterDialog']),
    'PluginManagerDialog': ('.plugin_manager_dialog_unified', ['PluginManagerDialog']),
    'EnhancedPluginMarketDialog': ('.enhanced_plugin_market_dialog', ['EnhancedPluginMarketDialog']),
    'ModelTrainingDialog': ('.model_training_dialog', ['ModelTrainingDialog']),
    'IntelligentModelSelectionDialog': ('.intelligent_model_selection_dialog', ['IntelligentModelSelectionDialog']),
    'AIPredictionConfigDialog': ('.ai_prediction_config_dialog', ['AIPredictionConfigDialog']),
    'PerformanceEvaluationDialog': ('.performance_evaluation_dialog', ['PerformanceEvaluationDialog']),
    'PredictionAccuracyDialog': ('.prediction_accuracy_dialog', ['PredictionAccuracyDialog']),
    'ExternalAlertChannelConfigDialog': ('.external_alert_channel_config_dialog', ['ExternalAlertChannelConfigDialog']),
    'DistributedServiceMonitorDialog': ('.distributed_service_monitor_dialog', ['DistributedServiceMonitorDialog']),
    'DistributedNodeMonitorDialog': ('.distributed_node_monitor_dialog', ['DistributedNodeMonitorDialog']),
    'ConnectionPoolManagerDialog': ('.connection_pool_manager_dialog', ['ConnectionPoolManagerDialog']),
    'DataSourcePluginConfigDialog': ('.data_source_plugin_config_dialog', ['DataSourcePluginConfigDialog']),
    'EnhancedConfigManagementDialog': ('.enhanced_config_management_dialog', ['EnhancedConfigManagementDialog']),
    'OrderManagementDialog': ('.order_management_dialog', ['OrderManagementDialog']),
    'AccountManagementDialog': ('.account_management_dialog', ['AccountManagementDialog']),
    'AdaptivePoolConfigDialog': ('.adaptive_pool_config_dialog', ['AdaptivePoolConfigDialog']),
}


def __getattr__(name):
    if name in _LAZY_IMPORTS:
        import importlib
        module_path, names = _LAZY_IMPORTS[name]
        # 使用 importlib.import_module 显式传入 package，避免 __import__ 相对导入
        # 对 globals['__name__'] 的隐式依赖（R204-P1: "'__name__' not in globals" 根因）
        mod = importlib.import_module(module_path, package=__name__)
        obj = getattr(mod, names[0])
        globals()[name] = obj
        return obj
    aliases = {
        'DataManagementDialog': 'UnifiedDataManagementDialog',
        'DataImportWizardDialog': 'UnifiedDataManagementDialog',
        'ImportHistoryDialog': 'UnifiedDataManagementDialog',
        'DataExportDialog': 'UnifiedDataManagementDialog',
        'AdvancedDataExportDialog': 'UnifiedDataManagementDialog',
        'DatabaseAdminDialog': 'UnifiedDataManagementDialog',
        'EnhancedStrategyManagerDialog': 'StrategyManagerDialog',
        'EnhancedStrategyManagerDialogV3': 'StrategyManagerDialog',
        'AIStrategyManagementDialog': 'StrategyManagerDialog',
        'EnhancedPluginManagerDialog': 'PluginManagerDialogUnified',
    }
    if name in aliases:
        return __getattr__(aliases[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")