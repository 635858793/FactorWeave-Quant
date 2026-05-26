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
}


def __getattr__(name):
    if name in _LAZY_IMPORTS:
        module_path, names = _LAZY_IMPORTS[name]
        mod = __import__(module_path, fromlist=names, level=1)
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