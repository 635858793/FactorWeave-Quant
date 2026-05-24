"""
数据库模型包
"""

from .llm_config_models import LLMConfigManager, get_llm_config_manager
from .alert_config_models import (
    NotificationConfig,
    AlertRule,
    AlertHistory,
    AlertRiskHistoryRecord,
    AlertConfigDatabase,
    get_alert_config_database,
)
from .duckdb_config_models import (
    DuckDBConfigProfile,
    DuckDBConfigManager,
    get_duckdb_config_manager,
)
from .performance_history_models import (
    RiskHistoryRecord,
    ExecutionHistoryRecord,
    PerformanceHistoryManager,
    get_performance_history_manager,
)
from .plugin_models import (
    PluginRecord,
    PluginDatabaseManager,
    DataSourcePluginConfigManager,
    get_data_source_config_manager,
)
from .indicator_models import (
    IndicatorParameter,
    IndicatorImplementation,
    Indicator,
    IndicatorCategory,
    IndicatorDatabase,
)
from .cache_config_models import CacheConfigManager
from .ai_config_models import AIPredictionConfigManager, get_ai_config_manager

__all__ = [
    'LLMConfigManager',
    'get_llm_config_manager',
    'NotificationConfig',
    'AlertRule',
    'AlertHistory',
    'AlertRiskHistoryRecord',
    'AlertConfigDatabase',
    'get_alert_config_database',
    'DuckDBConfigProfile',
    'DuckDBConfigManager',
    'get_duckdb_config_manager',
    'RiskHistoryRecord',
    'ExecutionHistoryRecord',
    'PerformanceHistoryManager',
    'get_performance_history_manager',
    'PluginRecord',
    'PluginDatabaseManager',
    'DataSourcePluginConfigManager',
    'get_data_source_config_manager',
    'IndicatorParameter',
    'IndicatorImplementation',
    'Indicator',
    'IndicatorCategory',
    'IndicatorDatabase',
    'CacheConfigManager',
    'AIPredictionConfigManager',
    'get_ai_config_manager',
]
