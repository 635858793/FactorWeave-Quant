"""
对话框模块

包含所有对话框类的导入和初始化。
"""

from .settings_dialog import SettingsDialog
from .advanced_search_dialog import AdvancedSearchDialog
from .stock_detail_dialog import StockDetailDialog
from .calculator_dialog import CalculatorDialog
from .converter_dialog import ConverterDialog
from .data_quality_dialog import DataQualityDialog
from .data_usage_terms_dialog import DataUsageTermsDialog, DataUsageManager
from .history_data_dialog import HistoryDataDialog
from .technical_analysis_dialog import TechnicalAnalysisDialog
from .database_admin_dialog import DatabaseAdminDialog
from .interval_stat_dialog import IntervalStatDialog
from .interval_stat_settings_dialog import IntervalStatSettingsDialog
from .system_optimizer_dialog import SystemOptimizerDialog, show_system_optimizer_dialog
from .startup_guides_dialog import StartupGuidesDialog

__all__ = [
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
    'StartupGuidesDialog'
]
