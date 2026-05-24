"""
对话框模块

包含所有对话框类的导入和初始化。
"""

from .base_dialog import BaseDialog, LoadingIndicator
from .settings_dialog import SettingsDialog
from .advanced_search_dialog import AdvancedSearchDialog
from .stock_detail_dialog import StockDetailDialog
from .calculator_dialog import CalculatorDialog
from .converter_dialog import ConverterDialog
from .data_quality_dialog import DataQualityDialog
from .data_usage_terms_dialog import DataUsageTermsDialog, DataUsageManager
from .history_data_dialog import HistoryDataDialog
from .technical_analysis_dialog import TechnicalAnalysisDialog
from .interval_stat_dialog import IntervalStatDialog
from .interval_stat_settings_dialog import IntervalStatSettingsDialog
from .system_optimizer_dialog import SystemOptimizerDialog, show_system_optimizer_dialog
from .startup_guides_dialog import StartupGuidesDialog

# 统一数据管理对话框 (V2) - 推荐使用
from .data_management_dialog_unified import (
    UnifiedDataManagementDialog,
    DataImportThread,
    DataExportThread,
)

# 废弃的数据管理对话框 - 从统一版本重导出，保持向后兼容
DataManagementDialog = UnifiedDataManagementDialog
DataImportWizardDialog = UnifiedDataManagementDialog
ImportHistoryDialog = UnifiedDataManagementDialog
DataExportDialog = UnifiedDataManagementDialog
AdvancedDataExportDialog = UnifiedDataManagementDialog
DatabaseAdminDialog = UnifiedDataManagementDialog

# 统一策略管理对话框 (V4) - 推荐使用
from .strategy_manager_dialog import (
    StrategyManagerDialog,
    StrategyTemplateManager,
    StrategyConfigValidator,
    StrategyEditorWidget,
)

# 废弃的策略管理对话框 - 从统一版本重导出，保持向后兼容
EnhancedStrategyManagerDialog = StrategyManagerDialog
EnhancedStrategyManagerDialogV3 = StrategyManagerDialog
AIStrategyManagementDialog = StrategyManagerDialog

# 统一插件管理对话框 (V3) - 推荐使用
from .plugin_manager_dialog_unified import PluginManagerDialogUnified, PluginConfigDialog

# 废弃的插件管理对话框 - 从统一版本重导出，保持向后兼容
EnhancedPluginManagerDialog = PluginManagerDialogUnified

__all__ = [
    'BaseDialog',
    'LoadingIndicator',

    'SettingsDialog',
    'AdvancedSearchDialog',
    'StockDetailDialog',
    'CalculatorDialog',
    'ConverterDialog',
    'DataQualityDialog',
    'DataUsageTermsDialog',
    'DataUsageManager',
    'HistoryDataDialog',

    'TechnicalAnalysisDialog',
    'DatabaseAdminDialog',
    'IntervalStatDialog',
    'IntervalStatSettingsDialog',
    'SystemOptimizerDialog',
    'show_system_optimizer_dialog',
    'StartupGuidesDialog',

    'UnifiedDataManagementDialog',
    'DataImportThread',
    'DataExportThread',

    'DataManagementDialog',
    'DataImportWizardDialog',
    'ImportHistoryDialog',
    'DataExportDialog',
    'AdvancedDataExportDialog',

    'StrategyManagerDialog',
    'StrategyTemplateManager',
    'StrategyConfigValidator',
    'StrategyEditorWidget',
    'EnhancedStrategyManagerDialog',
    'EnhancedStrategyManagerDialogV3',
    'AIStrategyManagementDialog',

    'PluginManagerDialogUnified',
    'PluginConfigDialog',
    'EnhancedPluginManagerDialog',
]