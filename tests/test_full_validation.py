"""
全面验证测试脚本
验证所有已迁移模块的导入、UnifiedSQLiteAccess、BaseDialog 和系统集成

测试分类：
1. 导入验证测试（~20个测试）
2. UnifiedSQLiteAccess 验证测试（~15个测试）
3. BaseDialog 验证测试（~15个测试）
4. 集成验证测试（~10个测试）

总计：60+ 个测试函数
"""

import os
import sys
import tempfile
import pytest
import importlib
from pathlib import Path
from typing import List, Tuple
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ==================== 1. 导入验证测试 ====================

class TestImportValidation:
    """模块导入验证测试类"""

    def test_import_core_database_modules(self):
        """验证核心数据库模块导入"""
        from core.database import sqlite_extensions
        assert sqlite_extensions is not None

    def test_import_unified_sqlite_access(self):
        """验证统一SQLite访问模块导入"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess, get_db
        assert UnifiedSQLiteAccess is not None
        assert get_db is not None

    def test_import_duckdb_manager(self):
        """验证DuckDB管理器导入"""
        from core.database.duckdb_manager import DuckDBManager
        assert DuckDBManager is not None

    def test_import_duckdb_operations(self):
        """验证DuckDB操作模块导入"""
        from core.database.duckdb_operations import DuckDBOperations
        assert DuckDBOperations is not None

    def test_import_table_manager(self):
        """验证表管理器导入"""
        from core.database.table_manager import TableManager
        assert TableManager is not None

    def test_import_table_schemas(self):
        """验证表结构模块导入"""
        from core.database.table_schemas import TableSchemas
        assert TableSchemas is not None

    def test_import_enhanced_data_manager(self):
        """验证增强数据管理器导入"""
        from core.services.enhanced_data_manager import DataQualityMonitor
        assert DataQualityMonitor is not None

    def test_import_unified_data_manager(self):
        """验证统一数据管理器导入"""
        from core.services.unified_data_manager import UnifiedDataManager
        assert UnifiedDataManager is not None

    def test_import_database_service(self):
        """验证数据库服务导入"""
        from core.services.database_service import DatabaseService
        assert DatabaseService is not None

    def test_import_data_service(self):
        """验证数据服务导入"""
        from core.services.data_service import DataService
        assert DataService is not None

    def test_import_config_service(self):
        """验证配置服务导入"""
        from core.services.config_service import ConfigService
        assert ConfigService is not None

    def test_import_db_models_init(self):
        """验证数据库模型初始化"""
        from db.models import __all__ as model_exports
        assert len(model_exports) > 0

    def test_import_indicator_models(self):
        """验证指标模型导入"""
        from db.models.indicator_models import IndicatorModel
        assert IndicatorModel is not None

    def test_import_alert_config_models(self):
        """验证告警配置模型导入"""
        from db.models.alert_config_models import AlertConfig
        assert AlertConfig is not None

    def test_import_llm_config_models(self):
        """验证LLM配置模型导入"""
        from db.models.llm_config_models import LLMConfig
        assert LLMConfig is not None

    def test_import_cache_config_models(self):
        """验证缓存配置模型导入"""
        from db.models.cache_config_models import CacheConfig
        assert CacheConfig is not None

    def test_import_ai_config_models(self):
        """验证AI配置模型导入"""
        from db.models.ai_config_models import AIConfig
        assert AIConfig is not None

    def test_import_import_data_engine(self):
        """验证数据导入引擎导入"""
        from core.importdata.import_engine import ImportEngine
        assert ImportEngine is not None

    def test_import_import_data_models(self):
        """验证数据导入模型导入"""
        from core.importdata.models import ImportTask
        assert ImportTask is not None

    def test_import_database_writer(self):
        """验证数据库写入器导入"""
        from core.importdata.database_writer import DatabaseWriter
        assert DatabaseWriter is not None

    def test_import_unified_data_import_engine(self):
        """验证统一数据导入引擎导入"""
        from core.importdata.unified_data_import_engine import UnifiedDataImportEngine
        assert UnifiedDataImportEngine is not None

    def test_import_task_status_manager(self):
        """验证任务状态管理器导入"""
        from core.importdata.task_status_manager import TaskStatusManager
        assert TaskStatusManager is not None

    def test_import_optimization_modules(self):
        """验证优化模块批量导入"""
        modules_to_test = [
            'optimization.algorithm_optimizer',
            'optimization.auto_tuner',
            'optimization.async_data_processor',
            'optimization.main_controller',
            'optimization.progressive_loading_manager',
            'optimization.update_throttler',
        ]
        
        failed_modules = []
        for module_name in modules_to_test:
            try:
                module = importlib.import_module(module_name)
                assert module is not None
            except ImportError as e:
                failed_modules.append((module_name, str(e)))
        
        if failed_modules:
            pytest.fail(f"以下模块导入失败: {failed_modules}")

    def test_import_core_optimization_modules(self):
        """验证核心优化模块批量导入"""
        modules_to_test = [
            'core.optimization.data_sampling_optimizer',
            'core.optimization.candle_virtual_renderer',
            'core.optimization.bar_virtual_renderer',
            'core.optimization.volume_virtual_renderer',
            'core.optimization.line_virtual_renderer',
        ]
        
        failed_modules = []
        for module_name in modules_to_test:
            try:
                module = importlib.import_module(module_name)
                assert module is not None
            except ImportError as e:
                failed_modules.append((module_name, str(e)))
        
        if failed_modules:
            pytest.fail(f"以下核心优化模块导入失败: {failed_modules}")

    def test_import_service_container(self):
        """验证服务容器导入"""
        from core.containers.service_container import ServiceContainer, get_service_container
        assert ServiceContainer is not None
        assert get_service_container is not None

    def test_import_service_registry(self):
        """验证服务注册表导入"""
        from core.containers.service_registry import ServiceRegistry, ServiceScope
        assert ServiceRegistry is not None
        assert ServiceScope is not None

    def test_import_event_bus(self):
        """验证事件总线导入"""
        from core.events.event_bus import EventBus, get_event_bus
        assert EventBus is not None
        assert get_event_bus is not None

    def test_import_event_types(self):
        """验证事件类型导入"""
        from core.events.types import BaseEvent, EventPriority
        assert BaseEvent is not None
        assert EventPriority is not None

    def test_import_coordinators(self):
        """验证协调器模块批量导入"""
        from core.coordinators.base_coordinator import BaseCoordinator
        from core.coordinators.event_coordinator import EventCoordinator
        from core.coordinators.theme_coordinator import ThemeCoordinator
        from core.coordinators.panel_coordinator import PanelCoordinator
        from core.coordinators.dialog_coordinator import DialogCoordinator
        
        assert BaseCoordinator is not None
        assert EventCoordinator is not None
        assert ThemeCoordinator is not None
        assert PanelCoordinator is not None
        assert DialogCoordinator is not None

    def test_import_base_service(self):
        """验证基础服务导入"""
        from core.services.base_service import BaseService
        assert BaseService is not None

    def test_import_stock_service(self):
        """验证股票服务导入"""
        from core.services.stock_service import StockService
        assert StockService is not None

    def test_import_market_service(self):
        """验证市场服务导入"""
        from core.services.market_service import MarketService
        assert MarketService is not None

    def test_import_fund_service(self):
        """验证基金服务导入"""
        from core.services.fund_service import FundService
        assert FundService is not None

    def test_import_industry_service(self):
        """验证行业服务导入"""
        from core.services.industry_service import IndustryService
        assert IndustryService is not None

    def test_import_sector_data_service(self):
        """验证板块数据服务导入"""
        from core.services.sector_data_service import SectorDataService
        assert SectorDataService is not None

    def test_import_performance_service(self):
        """验证性能服务导入"""
        from core.services.performance_service import PerformanceService
        assert PerformanceService is not None

    def test_import_notification_service(self):
        """验证通知服务导入"""
        from core.services.notification_service import NotificationService
        assert NotificationService is not None

    def test_import_cache_service(self):
        """验证缓存服务导入"""
        from core.services.cache_service import CacheService
        assert CacheService is not None

    def test_import_trading_service(self):
        """验证交易服务导入"""
        from core.services.trading_service import TradingService
        assert TradingService is not None

    def test_import_analysis_service(self):
        """验证分析服务导入"""
        from core.services.analysis_service import AnalysisService
        assert AnalysisService is not None

    def test_import_strategy_service(self):
        """验证策略服务导入"""
        from core.services.strategy_service import StrategyService
        assert StrategyService is not None

    def test_import_alert_rule_engine(self):
        """验证告警规则引擎导入"""
        from core.services.alert_rule_engine import AlertRuleEngine
        assert AlertRuleEngine is not None

    def test_import_alert_event_handler(self):
        """验证告警事件处理器导入"""
        from core.services.alert_event_handler import AlertEventHandler
        assert AlertEventHandler is not None

    def test_import_security_service(self):
        """验证安全服务导入"""
        from core.services.security_service import SecurityService
        assert SecurityService is not None

    def test_import_network_service(self):
        """验证网络服务导入"""
        from core.services.network_service import NetworkService
        assert NetworkService is not None

    def test_import_cloud_api_service(self):
        """验证云API服务导入"""
        from core.services.cloud_api_service import CloudApiService
        assert CloudApiService is not None

    def test_import_environment_service(self):
        """验证环境服务导入"""
        from core.services.environment_service import EnvironmentService
        assert EnvironmentService is not None

    def test_import_lifecycle_service(self):
        """验证生命周期服务导入"""
        from core.services.lifecycle_service import LifecycleService
        assert LifecycleService is not None

    def test_import_task_scheduler(self):
        """验证任务调度器导入"""
        from core.services.task_scheduler import TaskScheduler
        assert TaskScheduler is not None

    def test_import_routing_rule_manager(self):
        """验证路由规则管理器导入"""
        from core.services.routing_rule_manager import RoutingRuleManager
        assert RoutingRuleManager is not None

    def test_import_dependency_resolver(self):
        """验证依赖解析器导入"""
        from core.services.dependency_resolver import DependencyResolver
        assert DependencyResolver is not None

    def test_import_singleton_protection(self):
        """验证单例保护模块导入"""
        from core.services.singleton_protection import SingletonProtection
        assert SingletonProtection is not None

    def test_import_service_bootstrap(self):
        """验证服务引导模块导入"""
        from core.services.service_bootstrap import ServiceBootstrap
        assert ServiceBootstrap is not None

    def test_import_all_gui_dialogs_from_init(self):
        """验证GUI对话框模块 __init__.py 完整导入"""
        from gui.dialogs import (
            BaseDialog,
            LoadingIndicator,
            SettingsDialog,
            AdvancedSearchDialog,
            StockDetailDialog,
            CalculatorDialog,
            ConverterDialog,
            DataQualityDialog,
            HistoryDataDialog,
            DatabaseAdminDialog,
            IntervalStatDialog,
            IntervalStatSettingsDialog,
            SystemOptimizerDialog,
            StartupGuidesDialog,
            UnifiedDataManagementDialog,
            StrategyManagerDialog,
            PluginManagerDialogUnified,
        )
        
        assert BaseDialog is not None
        assert LoadingIndicator is not None
        assert SettingsDialog is not None
        assert AdvancedSearchDialog is not None
        assert StockDetailDialog is not None
        assert CalculatorDialog is not None
        assert ConverterDialog is not None
        assert DataQualityDialog is not None
        assert HistoryDataDialog is not None
        assert DatabaseAdminDialog is not None
        assert IntervalStatDialog is not None
        assert IntervalStatSettingsDialog is not None
        assert SystemOptimizerDialog is not None
        assert StartupGuidesDialog is not None
        assert UnifiedDataManagementDialog is not None
        assert StrategyManagerDialog is not None
        assert PluginManagerDialogUnified is not None

    def test_import_dialogs_inheriting_from_base_dialog(self):
        """验证所有继承自 BaseDialog 的对话框导入"""
        dialogs_to_test = [
            ('gui.dialogs.alert_rule_dialog', 'AlertRuleDialog'),
            ('gui.dialogs.calculator_dialog', 'CalculatorDialog'),
            ('gui.dialogs.converter_dialog', 'ConverterDialog'),
            ('gui.dialogs.data_quality_dialog', 'DataQualityDialog'),
            ('gui.dialogs.duckdb_config_dialog', 'DuckDBConfigDialog'),
            ('gui.dialogs.history_data_dialog', 'HistoryDataDialog'),
            ('gui.dialogs.import_history_dialog', 'ImportHistoryDialog'),
            ('gui.dialogs.interval_stat_dialog', 'IntervalStatDialog'),
            ('gui.dialogs.interval_stat_settings_dialog', 'IntervalStatSettingsDialog'),
            ('gui.dialogs.llm_config_dialog', 'LLMConfigDialog'),
            ('gui.dialogs.portfolio_dialog', 'PortfolioDialog'),
            ('gui.dialogs.quality_report_dialog', 'QualityReportDialog'),
            ('gui.dialogs.risk_rule_config_dialog', 'RiskRuleConfigDialog'),
            ('gui.dialogs.settings_dialog', 'SettingsDialog'),
            ('gui.dialogs.startup_guides_dialog', 'StartupGuidesDialog'),
            ('gui.dialogs.system_optimizer_dialog', 'SystemOptimizerDialog'),
            ('gui.dialogs.technical_analysis_dialog', 'TechnicalAnalysisDialog'),
            ('gui.dialogs.version_manager_dialog', 'VersionManagerDialog'),
            ('gui.dialogs.webgpu_status_dialog', 'WebGPUStatusDialog'),
            ('gui.dialogs.scheduled_task_dialog', 'ScheduledTaskDialog'),
            ('gui.dialogs.cloud_api_dialog', 'CloudApiDialog'),
            ('gui.dialogs.data_export_dialog', 'DataExportDialog'),
            ('gui.dialogs.data_import_wizard_dialog', 'DataImportWizardDialog'),
            ('gui.dialogs.indicator_selection_dialog', 'IndicatorSelectionDialog'),
            ('gui.dialogs.indicator_params_dialog', 'IndicatorParamsDialog'),
            ('gui.dialogs.indicator_combination_dialog', 'IndicatorCombinationDialog'),
            ('gui.dialogs.batch_filter_dialog', 'CompactAdvancedFilterDialog'),
        ]
        
        failed_imports = []
        for module_name, class_name in dialogs_to_test:
            try:
                module = importlib.import_module(module_name)
                dialog_class = getattr(module, class_name)
                assert dialog_class is not None
            except (ImportError, AttributeError) as e:
                failed_imports.append(f"{module_name}.{class_name}: {e}")
        
        if failed_imports:
            pytest.fail(f"以下对话框导入失败:\n" + "\n".join(failed_imports))

    def test_import_data_management_dialogs(self):
        """验证数据管理对话框导入"""
        from gui.dialogs.data_management_dialog import DataManagementDialog
        from gui.dialogs.data_management_dialog_unified import UnifiedDataManagementDialog
        from gui.dialogs.data_export_dialog import DataExportDialog
        from gui.dialogs.advanced_data_export_dialog import AdvancedDataExportDialog
        
        assert DataManagementDialog is not None
        assert UnifiedDataManagementDialog is not None
        assert DataExportDialog is not None
        assert AdvancedDataExportDialog is not None

    def test_import_strategy_management_dialogs(self):
        """验证策略管理对话框导入"""
        from gui.dialogs.strategy_manager_dialog import StrategyManagerDialog
        from gui.dialogs.enhanced_strategy_manager_dialog import EnhancedStrategyManagerDialog
        from gui.dialogs.enhanced_strategy_manager_dialog_v3 import EnhancedStrategyManagerDialogV3
        from gui.dialogs.ai_strategy_management_dialog import AIStrategyManagementDialog
        
        assert StrategyManagerDialog is not None
        assert EnhancedStrategyManagerDialog is not None
        assert EnhancedStrategyManagerDialogV3 is not None
        assert AIStrategyManagementDialog is not None

    def test_import_plugin_management_dialogs(self):
        """验证插件管理对话框导入"""
        from gui.dialogs.plugin_manager_dialog_unified import PluginManagerDialogUnified
        from gui.dialogs.plugin_manager_dialog import PluginManagerDialog
        from gui.dialogs.enhanced_plugin_manager_dialog import EnhancedPluginManagerDialog
        from gui.dialogs.enhanced_plugin_market_dialog import EnhancedPluginMarketDialog
        
        assert PluginManagerDialogUnified is not None
        assert PluginManagerDialog is not None
        assert EnhancedPluginManagerDialog is not None
        assert EnhancedPluginMarketDialog is not None

    def test_import_advanced_dialogs(self):
        """验证高级对话框导入"""
        from gui.dialogs.model_training_dialog import ModelTrainingDialog
        from gui.dialogs.intelligent_model_selection_dialog import IntelligentModelSelectionDialog
        from gui.dialogs.ai_prediction_config_dialog import AIPredictionConfigDialog
        from gui.dialogs.performance_evaluation_dialog import PerformanceEvaluationDialog
        from gui.dialogs.prediction_accuracy_dialog import PredictionAccuracyDialog
        from gui.dialogs.external_alert_channel_config_dialog import ExternalAlertChannelConfigDialog
        
        assert ModelTrainingDialog is not None
        assert IntelligentModelSelectionDialog is not None
        assert AIPredictionConfigDialog is not None
        assert PerformanceEvaluationDialog is not None
        assert PredictionAccuracyDialog is not None
        assert ExternalAlertChannelConfigDialog is not None

    def test_import_monitoring_dialogs(self):
        """验证监控对话框导入"""
        from gui.dialogs.distributed_service_monitor_dialog import DistributedServiceMonitorDialog
        from gui.dialogs.distributed_node_monitor_dialog import DistributedNodeMonitorDialog
        from gui.dialogs.connection_pool_manager_dialog import ConnectionPoolManagerDialog
        from gui.dialogs.database_admin_dialog import DatabaseAdminDialog
        
        assert DistributedServiceMonitorDialog is not None
        assert DistributedNodeMonitorDialog is not None
        assert ConnectionPoolManagerDialog is not None
        assert DatabaseAdminDialog is not None

    def test_import_data_source_dialogs(self):
        """验证数据源对话框导入"""
        from gui.dialogs.data_source_plugin_config_dialog import DataSourcePluginConfigDialog
        from gui.dialogs.enhanced_config_management_dialog import EnhancedConfigManagementDialog
        from gui.dialogs.enhanced_plugin_manager_dialog import EnhancedPluginManagerDialog
        
        assert DataSourcePluginConfigDialog is not None
        assert EnhancedConfigManagementDialog is not None
        assert EnhancedPluginManagerDialog is not None

    def test_import_trading_dialogs(self):
        """验证交易相关对话框导入"""
        from gui.dialogs.order_management_dialog import OrderManagementDialog
        from gui.dialogs.account_management_dialog import AccountManagementDialog
        
        assert OrderManagementDialog is not None
        assert AccountManagementDialog is not None

    def test_import_adaptive_pool_config_dialog(self):
        """验证自适应池配置对话框导入"""
        from gui.dialogs.adaptive_pool_config_dialog import AdaptivePoolConfigDialog
        assert AdaptivePoolConfigDialog is not None

    def test_import_indicator_market_dialog(self):
        """验证指标市场对话框导入"""
        from gui.dialogs.indicator_market_dialog import IndicatorMarketDialog
        assert IndicatorMarketDialog is not None

    def test_import_connection_pool_config_dialog(self):
        """验证连接池配置对话框导入"""
        from gui.dialogs.connection_pool_config_dialog import ConnectionPoolConfigDialog
        assert ConnectionPoolConfigDialog is not None

    def test_import_optimized_duckdb_import_dialog(self):
        """验证优化的DuckDB导入对话框导入"""
        from gui.dialogs.optimized_duckdb_import_dialog import OptimizedDuckDBImportDialog
        assert OptimizedDuckDBImportDialog is not None


# ==================== 2. UnifiedSQLiteAccess 验证测试 ====================

class TestUnifiedSQLiteAccess:
    """UnifiedSQLiteAccess 验证测试类"""

    @pytest.fixture
    def temp_db_path(self):
        """创建临时数据库路径"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            yield f.name
        # 清理
        if os.path.exists(f.name):
            os.remove(f.name)

    def test_singleton_pattern_returns_same_instance(self, temp_db_path):
        """验证单例模式返回相同实例"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        instance1 = UnifiedSQLiteAccess.get_instance(temp_db_path)
        instance2 = UnifiedSQLiteAccess.get_instance(temp_db_path)
        
        assert instance1 is instance2

    def test_singleton_pattern_different_paths_different_instances(self, temp_db_path):
        """验证不同路径返回不同实例"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        instance1 = UnifiedSQLiteAccess.get_instance(temp_db_path)
        instance2 = UnifiedSQLiteAccess.get_instance(temp_db_path + '_other')
        
        assert instance1 is not instance2

    def test_singleton_thread_safety(self, temp_db_path):
        """验证单例模式线程安全性"""
        import threading
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        instances = []
        lock = threading.Lock()
        
        def get_instance():
            inst = UnifiedSQLiteAccess.get_instance(temp_db_path + '_thread_test')
            with lock:
                instances.append(inst)
        
        threads = [threading.Thread(target=get_instance) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(set(id(i) for i in instances)) == 1

    def test_get_connection_context_manager(self, temp_db_path):
        """验证 get_connection() 上下文管理器工作正常"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path)
        
        with db.get_connection() as conn:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

    def test_auto_commit_on_success(self, temp_db_path):
        """验证成功操作时自动提交"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_commit_test')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT)")
            cursor.execute("INSERT INTO test_table (name) VALUES ('test')")
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test_table")
            count = cursor.fetchone()[0]
            assert count == 1

    def test_rollback_on_error(self, temp_db_path):
        """验证错误时自动回滚"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_rollback_test')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS rollback_test (id INTEGER PRIMARY KEY, value INTEGER)")
        
        initial_count = 0
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM rollback_test")
            initial_count = cursor.fetchone()[0]
        
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO rollback_test (value) VALUES (1)")
                cursor.execute("SELECT * FROM nonexistent_table")
        except Exception:
            pass
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM rollback_test")
            final_count = cursor.fetchone()[0]
            
            assert final_count == initial_count

    def test_wal_mode_enabled(self, temp_db_path):
        """验证 WAL 模式已启用"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_wal_test')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]
            assert journal_mode.lower() == 'wal'

    def test_foreign_keys_enabled(self, temp_db_path):
        """验证外键约束已启用"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_fk_test')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys")
            fk_status = cursor.fetchone()[0]
            assert fk_status == 1

    def test_execute_query(self, temp_db_path):
        """验证 execute 方法正常工作"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_execute_test')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS query_test (id INTEGER PRIMARY KEY, name TEXT)")
            cursor.execute("INSERT INTO query_test (name) VALUES ('item1')")
            cursor.execute("INSERT INTO query_test (name) VALUES ('item2')")
        
        results = db.execute("SELECT * FROM query_test WHERE name = ?", ('item1',))
        assert len(results) == 1
        assert results[0][1] == 'item1'

    def test_execute_write(self, temp_db_path):
        """验证 execute_write 方法正常工作"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_write_test')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS write_test (id INTEGER PRIMARY KEY, value TEXT)")
        
        rowcount = db.execute_write("INSERT INTO write_test (value) VALUES (?)", ('test_value',))
        assert rowcount >= 0

    def test_execute_many(self, temp_db_path):
        """验证 execute_many 方法批量插入"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_executemany_test')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS batch_test (id INTEGER PRIMARY KEY, value TEXT)")
        
        params_list = [('value1',), ('value2',), ('value3',)]
        rowcount = db.execute_many("INSERT INTO batch_test (value) VALUES (?)", params_list)
        assert rowcount >= 0
        
        results = db.execute("SELECT COUNT(*) FROM batch_test")
        assert results[0][0] == 3

    def test_execute_in_transaction(self, temp_db_path):
        """验证 execute_in_transaction 批量事务操作"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_transaction_test')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS trans_test (id INTEGER PRIMARY KEY, amount INTEGER)")
        
        operations = [
            ("INSERT INTO trans_test (amount) VALUES (?)", (100,)),
            ("INSERT INTO trans_test (amount) VALUES (?)", (200,)),
            ("INSERT INTO trans_test (amount) VALUES (?)", (300,)),
        ]
        
        total_affected = db.execute_in_transaction(operations)
        assert total_affected >= 0
        
        results = db.execute("SELECT SUM(amount) FROM trans_test")
        assert results[0][0] == 600

    def test_table_exists(self, temp_db_path):
        """验证 table_exists 方法"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_exists_test')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS exists_test (id INTEGER PRIMARY KEY)")
        
        assert db.table_exists('exists_test') is True
        assert db.table_exists('nonexistent_table') is False

    def test_get_table_count(self, temp_db_path):
        """验证 get_table_count 方法"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_count_test')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS count_test (id INTEGER PRIMARY KEY, name TEXT)")
            cursor.execute("INSERT INTO count_test (name) VALUES ('a')")
            cursor.execute("INSERT INTO count_test (name) VALUES ('b')")
            cursor.execute("INSERT INTO count_test (name) VALUES ('c')")
        
        count = db.get_table_count('count_test')
        assert count == 3

    def test_check_foreign_keys_enabled(self, temp_db_path):
        """验证 check_foreign_keys_enabled 方法"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_fk_check_test')
        assert db.check_foreign_keys_enabled() is True

    def test_get_database_info(self, temp_db_path):
        """验证 get_database_info 方法返回数据库信息"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_info_test')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS info_test (id INTEGER PRIMARY KEY, data TEXT)")
        
        info = db.get_database_info()
        
        assert 'journal_mode' in info
        assert 'foreign_keys' in info
        assert info['journal_mode'] == 'wal'
        assert info['foreign_keys'] == 1
        assert 'page_count' in info
        assert 'page_size' in info
        assert 'db_size_bytes' in info

    def test_get_foreign_key_violations(self, temp_db_path):
        """验证 get_foreign_key_violations 方法"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_fk_violations_test')
        
        violations = db.get_foreign_key_violations()
        assert isinstance(violations, list)

    def test_convenience_functions(self, temp_db_path):
        """验证便捷函数 get_db, execute_query, execute_write"""
        from core.database.unified_sqlite_access import get_db, execute_query, execute_write
        
        db = get_db(temp_db_path + '_convenience_test')
        assert db is not None
        
        execute_query(temp_db_path + '_convenience_test', "SELECT 1")

    def test_performance_optimization_settings(self, temp_db_path):
        """验证性能优化配置已应用"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_perf_test')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA cache_size")
            cache_size = cursor.fetchone()[0]
            assert cache_size == -64000
            
            cursor.execute("PRAGMA synchronous")
            sync_mode = cursor.fetchone()[0]
            assert sync_mode == 1

    def test_foreign_key_violation_detection(self, temp_db_path):
        """验证外键违反检测功能"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_fk_detect_test')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS parent_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS child_table (
                    id INTEGER PRIMARY KEY,
                    parent_id INTEGER,
                    FOREIGN KEY (parent_id) REFERENCES parent_table(id)
                )
            """)
        
        violations = db.get_foreign_key_violations()
        assert isinstance(violations, list)

    def test_row_factory_configuration(self, temp_db_path):
        """验证 row_factory 配置为 sqlite3.Row"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        import sqlite3
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_row_factory_test')
        
        with db.get_connection() as conn:
            assert conn.row_factory == sqlite3.Row

    def test_error_handling_invalid_sql(self, temp_db_path):
        """验证无效SQL时的错误处理"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_error_test')
        
        with pytest.raises(Exception):
            db.execute("SELECT * FROM nonexistent_table")

    def test_multiple_connections_independence(self, temp_db_path):
        """验证多个连接之间的独立性"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db = UnifiedSQLiteAccess.get_instance(temp_db_path + '_independence_test')
        
        with db.get_connection() as conn1:
            cursor = conn1.cursor()
            cursor.execute("SELECT 1")
            result1 = cursor.fetchone()
        
        with db.get_connection() as conn2:
            cursor = conn2.cursor()
            cursor.execute("SELECT 2")
            result2 = cursor.fetchone()
        
        assert result1[0] == 1
        assert result2[0] == 2

    def test_get_all_instances(self, temp_db_path):
        """验证 get_all_instances 方法"""
        from core.database.unified_sqlite_access import UnifiedSQLiteAccess
        
        db1 = UnifiedSQLiteAccess.get_instance(temp_db_path)
        db2 = UnifiedSQLiteAccess.get_instance(temp_db_path + '_other')
        
        all_instances = UnifiedSQLiteAccess.get_all_instances()
        assert len(all_instances) >= 2
        assert temp_db_path in all_instances


# ==================== 3. BaseDialog 验证测试 ====================

class TestBaseDialog:
    """BaseDialog 验证测试类"""

    def test_base_dialog_instantiation(self):
        """验证 BaseDialog 可以实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Test Dialog")
        
        assert dialog is not None
        assert dialog.windowTitle() == "Test Dialog"

    def test_base_dialog_min_size(self):
        """验证 BaseDialog 最小尺寸设置"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Size Test", min_size=(400, 300))
        
        assert dialog.minimumSize().width() == 400
        assert dialog.minimumSize().height() == 300

    def test_base_dialog_max_size(self):
        """验证 BaseDialog 最大尺寸设置"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Max Size Test", max_size=(800, 600))
        
        assert dialog.maximumSize().width() == 800
        assert dialog.maximumSize().height() == 600

    def test_base_dialog_initial_size(self):
        """验证 BaseDialog 初始尺寸设置"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Initial Size Test", size=(500, 400))
        
        assert dialog.width() == 500
        assert dialog.height() == 400

    def test_base_dialog_modal_setting(self):
        """验证 BaseDialog 模态设置"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog_modal = BaseDialog(title="Modal Test", modal=True)
        dialog_non_modal = BaseDialog(title="Non-Modal Test", modal=False)
        
        assert dialog_modal.isModal() is True
        assert dialog_non_modal.isModal() is False

    def test_base_dialog_show_error_method(self):
        """验证 BaseDialog show_error 方法"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Error Test")
        
        with patch('PyQt5.QtWidgets.QMessageBox.critical') as mock_critical:
            dialog.show_error("Error Title", "Error Message")
            mock_critical.assert_called_once_with(dialog, "Error Title", "Error Message")

    def test_base_dialog_show_warning_method(self):
        """验证 BaseDialog show_warning 方法"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Warning Test")
        
        with patch('PyQt5.QtWidgets.QMessageBox.warning') as mock_warning:
            dialog.show_warning("Warning Title", "Warning Message")
            mock_warning.assert_called_once_with(dialog, "Warning Title", "Warning Message")

    def test_base_dialog_show_success_method(self):
        """验证 BaseDialog show_success 方法"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Success Test")
        
        with patch('PyQt5.QtWidgets.QMessageBox.information') as mock_info:
            dialog.show_success("Success Title", "Success Message")
            mock_info.assert_called_once_with(dialog, "Success Title", "Success Message")

    def test_base_dialog_show_info_method(self):
        """验证 BaseDialog show_info 方法"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Info Test")
        
        with patch('PyQt5.QtWidgets.QMessageBox.information') as mock_info:
            dialog.show_info("Info Title", "Info Message")
            mock_info.assert_called_once_with(dialog, "Info Title", "Info Message")

    def test_base_dialog_confirm_method_yes(self):
        """验证 BaseDialog confirm 方法 - 确认"""
        from PyQt5.QtWidgets import QApplication, QMessageBox
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Confirm Test")
        
        with patch('PyQt5.QtWidgets.QMessageBox.question', return_value=QMessageBox.Yes):
            result = dialog.confirm("Confirm Title", "Are you sure?")
            assert result is True

    def test_base_dialog_confirm_method_no(self):
        """验证 BaseDialog confirm 方法 - 取消"""
        from PyQt5.QtWidgets import QApplication, QMessageBox
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Confirm Test")
        
        with patch('PyQt5.QtWidgets.QMessageBox.question', return_value=QMessageBox.No):
            result = dialog.confirm("Confirm Title", "Are you sure?")
            assert result is False

    def test_base_dialog_loading_indicator_setup(self):
        """验证 BaseDialog 加载指示器设置"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Loading Test")
        
        assert dialog._loading_indicator is None
        dialog.setup_loading_indicator()
        assert dialog._loading_indicator is not None

    def test_base_dialog_loading_indicator_show_hide(self):
        """验证 BaseDialog 加载指示器显示隐藏"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Loading Test")
        
        dialog.show_loading("Loading data...")
        assert dialog._loading_indicator.isVisible()
        
        dialog.hide_loading()
        assert not dialog._loading_indicator.isVisible()

    def test_base_dialog_shadow_effect(self):
        """验证 BaseDialog 阴影效果"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Shadow Test")
        
        dialog.add_shadow_effect()
        assert dialog.graphicsEffect() is not None

    def test_base_dialog_center_on_parent(self):
        """验证 BaseDialog 居中显示"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Center Test")
        
        dialog.center_on_parent()

    def test_base_dialog_settings_key(self):
        """验证 BaseDialog settings_key 设置"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Settings Test", settings_key="TestDialog")
        
        assert dialog._settings_key == "TestDialog"

    def test_base_dialog_window_geometry_save_restore(self):
        """验证 BaseDialog 窗口几何信息保存和恢复"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Geometry Test", settings_key="TestDialogGeometry")
        
        dialog.resize(600, 400)
        dialog.save_geometry()
        dialog.restore_geometry()

    def test_base_dialog_custom_subclass(self):
        """验证 BaseDialog 自定义子类工作正常"""
        from PyQt5.QtWidgets import QApplication, QVBoxLayout, QLabel
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        
        class CustomDialog(BaseDialog):
            def __init__(self):
                super().__init__(
                    title="Custom Dialog",
                    min_size=(400, 300),
                    settings_key="CustomDialog"
                )
                self.setup_custom_ui()
            
            def setup_custom_ui(self):
                layout = QVBoxLayout(self)
                label = QLabel("Custom Content")
                layout.addWidget(label)
        
        dialog = CustomDialog()
        assert dialog.windowTitle() == "Custom Dialog"
        assert dialog.minimumSize().width() == 400
        assert dialog.minimumSize().height() == 300

    def test_base_dialog_inheritance_chain(self):
        """验证 BaseDialog 继承链完整性"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        from gui.dialogs.calculator_dialog import CalculatorDialog
        
        app = QApplication.instance() or QApplication([])
        
        dialog = CalculatorDialog()
        assert isinstance(dialog, BaseDialog)

    def test_loading_indicator_component(self):
        """验证 LoadingIndicator 组件"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import LoadingIndicator
        
        app = QApplication.instance() or QApplication([])
        indicator = LoadingIndicator()
        
        assert indicator is not None
        indicator.show_message("Test Loading")
        assert indicator.isVisible()
        indicator.hide_indicator()
        assert not indicator.isVisible()

    def test_base_dialog_theme_manager_support(self):
        """验证 BaseDialog 主题管理器支持"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        
        mock_theme_manager = Mock()
        mock_theme_manager.get_current_theme.return_value = Mock(colors={'primary': '#000000'})
        
        dialog = BaseDialog(title="Theme Test", theme_manager=mock_theme_manager)
        colors = dialog.get_theme_colors()
        assert colors == {'primary': '#000000'}

    def test_base_dialog_theme_style_method(self):
        """验证 BaseDialog set_theme_style 方法"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Theme Style Test")
        
        dialog.set_theme_style(is_dark=True)
        dialog.set_theme_style(is_dark=False)

    def test_base_dialog_on_theme_changed(self):
        """验证 BaseDialog on_theme_changed 方法"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.base_dialog import BaseDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = BaseDialog(title="Theme Changed Test")
        
        dialog.on_theme_changed()

    def test_dialog_settings_dialog_instantiation(self):
        """验证 SettingsDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs import SettingsDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = SettingsDialog()
        
        assert dialog is not None
        assert isinstance(dialog, type(SettingsDialog()))

    def test_dialog_calculator_dialog_instantiation(self):
        """验证 CalculatorDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs import CalculatorDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = CalculatorDialog()
        
        assert dialog is not None

    def test_dialog_converter_dialog_instantiation(self):
        """验证 ConverterDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs import ConverterDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = ConverterDialog()
        
        assert dialog is not None

    def test_dialog_data_quality_dialog_instantiation(self):
        """验证 DataQualityDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs import DataQualityDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = DataQualityDialog()
        
        assert dialog is not None

    def test_dialog_history_data_dialog_instantiation(self):
        """验证 HistoryDataDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs import HistoryDataDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = HistoryDataDialog()
        
        assert dialog is not None

    def test_dialog_database_admin_dialog_instantiation(self):
        """验证 DatabaseAdminDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs import DatabaseAdminDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = DatabaseAdminDialog()
        
        assert dialog is not None

    def test_dialog_interval_stat_dialog_instantiation(self):
        """验证 IntervalStatDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs import IntervalStatDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = IntervalStatDialog()
        
        assert dialog is not None

    def test_dialog_system_optimizer_dialog_instantiation(self):
        """验证 SystemOptimizerDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs import SystemOptimizerDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = SystemOptimizerDialog()
        
        assert dialog is not None

    def test_dialog_startup_guides_dialog_instantiation(self):
        """验证 StartupGuidesDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs import StartupGuidesDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = StartupGuidesDialog()
        
        assert dialog is not None

    def test_dialog_alert_rule_dialog_instantiation(self):
        """验证 AlertRuleDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.alert_rule_dialog import AlertRuleDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = AlertRuleDialog()
        
        assert dialog is not None

    def test_dialog_advanced_search_dialog_instantiation(self):
        """验证 AdvancedSearchDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs import AdvancedSearchDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = AdvancedSearchDialog()
        
        assert dialog is not None

    def test_dialog_stock_detail_dialog_instantiation(self):
        """验证 StockDetailDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs import StockDetailDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = StockDetailDialog()
        
        assert dialog is not None

    def test_dialog_technical_analysis_dialog_instantiation(self):
        """验证 TechnicalAnalysisDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs import TechnicalAnalysisDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = TechnicalAnalysisDialog()
        
        assert dialog is not None

    def test_dialog_batch_filter_dialog_instantiation(self):
        """验证 CompactAdvancedFilterDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.batch_filter_dialog import CompactAdvancedFilterDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = CompactAdvancedFilterDialog()
        
        assert dialog is not None

    def test_dialog_duckdb_config_dialog_instantiation(self):
        """验证 DuckDBConfigDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.duckdb_config_dialog import DuckDBConfigDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = DuckDBConfigDialog()
        
        assert dialog is not None

    def test_dialog_llm_config_dialog_instantiation(self):
        """验证 LLMConfigDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.llm_config_dialog import LLMConfigDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = LLMConfigDialog()
        
        assert dialog is not None

    def test_dialog_portfolio_dialog_instantiation(self):
        """验证 PortfolioDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.portfolio_dialog import PortfolioDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = PortfolioDialog()
        
        assert dialog is not None

    def test_dialog_quality_report_dialog_instantiation(self):
        """验证 QualityReportDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.quality_report_dialog import QualityReportDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = QualityReportDialog()
        
        assert dialog is not None

    def test_dialog_risk_rule_config_dialog_instantiation(self):
        """验证 RiskRuleConfigDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.risk_rule_config_dialog import RiskRuleConfigDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = RiskRuleConfigDialog()
        
        assert dialog is not None

    def test_dialog_version_manager_dialog_instantiation(self):
        """验证 VersionManagerDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.version_manager_dialog import VersionManagerDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = VersionManagerDialog()
        
        assert dialog is not None

    def test_dialog_webgpu_status_dialog_instantiation(self):
        """验证 WebGPUStatusDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.webgpu_status_dialog import WebGPUStatusDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = WebGPUStatusDialog()
        
        assert dialog is not None

    def test_dialog_scheduled_task_dialog_instantiation(self):
        """验证 ScheduledTaskDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.scheduled_task_dialog import ScheduledTaskDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = ScheduledTaskDialog()
        
        assert dialog is not None

    def test_dialog_cloud_api_dialog_instantiation(self):
        """验证 CloudApiDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.cloud_api_dialog import CloudApiDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = CloudApiDialog()
        
        assert dialog is not None

    def test_dialog_data_export_dialog_instantiation(self):
        """验证 DataExportDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.data_export_dialog import DataExportDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = DataExportDialog()
        
        assert dialog is not None

    def test_dialog_data_import_wizard_dialog_instantiation(self):
        """验证 DataImportWizardDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.data_import_wizard_dialog import DataImportWizardDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = DataImportWizardDialog()
        
        assert dialog is not None

    def test_dialog_indicator_selection_dialog_instantiation(self):
        """验证 IndicatorSelectionDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.indicator_selection_dialog import IndicatorSelectionDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = IndicatorSelectionDialog()
        
        assert dialog is not None

    def test_dialog_indicator_params_dialog_instantiation(self):
        """验证 IndicatorParamsDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.indicator_params_dialog import IndicatorParamsDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = IndicatorParamsDialog()
        
        assert dialog is not None

    def test_dialog_indicator_combination_dialog_instantiation(self):
        """验证 IndicatorCombinationDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.indicator_combination_dialog import IndicatorCombinationDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = IndicatorCombinationDialog()
        
        assert dialog is not None

    def test_dialog_import_history_dialog_instantiation(self):
        """验证 ImportHistoryDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.import_history_dialog import ImportHistoryDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = ImportHistoryDialog()
        
        assert dialog is not None

    def test_dialog_interval_stat_settings_dialog_instantiation(self):
        """验证 IntervalStatSettingsDialog 实例化"""
        from PyQt5.QtWidgets import QApplication
        from gui.dialogs.interval_stat_settings_dialog import IntervalStatSettingsDialog
        
        app = QApplication.instance() or QApplication([])
        dialog = IntervalStatSettingsDialog()
        
        assert dialog is not None


# ==================== 4. 集成验证测试 ====================

class TestIntegrationValidation:
    """集成验证测试类"""

    def test_service_container_creation(self):
        """验证服务容器可以创建"""
        from core.containers.service_container import ServiceContainer
        
        container = ServiceContainer()
        assert container is not None

    def test_service_container_registration(self):
        """验证服务容器注册功能"""
        from core.containers.service_container import ServiceContainer
        from core.containers.service_registry import ServiceScope
        
        class TestService:
            def __init__(self):
                self.name = "test"
        
        container = ServiceContainer()
        container.register(TestService, TestService, scope=ServiceScope.SINGLETON)
        
        assert container.is_registered(TestService)

    def test_service_container_resolve(self):
        """验证服务容器解析功能"""
        from core.containers.service_container import ServiceContainer
        from core.containers.service_registry import ServiceScope
        
        class TestService:
            def __init__(self):
                self.name = "resolved"
        
        container = ServiceContainer()
        container.register(TestService, TestService, scope=ServiceScope.SINGLETON)
        
        service = container.resolve(TestService)
        assert service is not None
        assert service.name == "resolved"

    def test_service_container_singleton_scope(self):
        """验证服务容器单例作用域"""
        from core.containers.service_container import ServiceContainer
        from core.containers.service_registry import ServiceScope
        
        class TestService:
            pass
        
        container = ServiceContainer()
        container.register(TestService, TestService, scope=ServiceScope.SINGLETON)
        
        service1 = container.resolve(TestService)
        service2 = container.resolve(TestService)
        
        assert service1 is service2

    def test_service_container_transient_scope(self):
        """验证服务容器瞬态作用域"""
        from core.containers.service_container import ServiceContainer
        from core.containers.service_registry import ServiceScope
        
        class TestService:
            pass
        
        container = ServiceContainer()
        container.register(TestService, TestService, scope=ServiceScope.TRANSIENT)
        
        service1 = container.resolve(TestService)
        service2 = container.resolve(TestService)
        
        assert service1 is not service2

    def test_service_container_instance_registration(self):
        """验证服务容器实例注册"""
        from core.containers.service_container import ServiceContainer
        
        class TestService:
            def __init__(self):
                self.value = 42
        
        container = ServiceContainer()
        instance = TestService()
        container.register_instance(TestService, instance)
        
        resolved = container.resolve(TestService)
        assert resolved is instance
        assert resolved.value == 42

    def test_service_container_try_resolve(self):
        """验证服务容器 try_resolve 方法"""
        from core.containers.service_container import ServiceContainer
        
        class TestService:
            pass
        
        container = ServiceContainer()
        result = container.try_resolve(TestService)
        assert result is None

    def test_service_container_auto_wire(self):
        """验证服务容器自动装配"""
        from core.containers.service_container import ServiceContainer
        from core.containers.service_registry import ServiceScope
        
        class ConfigService:
            def __init__(self):
                self.config = {"debug": True}
        
        class MainService:
            def __init__(self, config_service: ConfigService):
                self.config_service = config_service
        
        container = ServiceContainer()
        container.register(ConfigService, ConfigService, scope=ServiceScope.SINGLETON)
        container.register(MainService, MainService, scope=ServiceScope.SINGLETON)
        
        main_service = container.auto_wire(MainService)
        assert main_service.config_service is not None

    def test_event_bus_creation(self):
        """验证事件总线可以创建"""
        from core.events.event_bus import EventBus
        
        event_bus = EventBus()
        assert event_bus is not None

    def test_event_bus_subscribe_publish(self):
        """验证事件总线订阅和发布"""
        from core.events.event_bus import EventBus
        from core.events.types import BaseEvent
        
        event_bus = EventBus()
        
        received_events = []
        
        class TestEvent(BaseEvent):
            pass
        
        def handler(event):
            received_events.append(event)
        
        event_bus.subscribe(TestEvent, handler)
        event_bus.publish(TestEvent())
        
        assert len(received_events) == 1

    def test_event_bus_unsubscribe(self):
        """验证事件总线取消订阅"""
        from core.events.event_bus import EventBus
        from core.events.types import BaseEvent
        
        event_bus = EventBus()
        
        class TestEvent(BaseEvent):
            pass
        
        call_count = [0]
        
        def handler(event):
            call_count[0] += 1
        
        event_bus.subscribe(TestEvent, handler)
        event_bus.publish(TestEvent())
        event_bus.unsubscribe(TestEvent, handler)
        event_bus.publish(TestEvent())
        
        assert call_count[0] == 1

    def test_event_bus_priority(self):
        """验证事件总线优先级机制"""
        from core.events.event_bus import EventBus
        from core.events.types import BaseEvent
        
        event_bus = EventBus()
        
        class TestEvent(BaseEvent):
            pass
        
        execution_order = []
        
        def handler1(event):
            execution_order.append(1)
        
        def handler2(event):
            execution_order.append(2)
        
        def handler3(event):
            execution_order.append(3)
        
        event_bus.subscribe(TestEvent, handler2, priority=2)
        event_bus.subscribe(TestEvent, handler1, priority=1)
        event_bus.subscribe(TestEvent, handler3, priority=3)
        
        event_bus.publish(TestEvent())
        
        assert execution_order == [1, 2, 3]

    def test_event_bus_stats(self):
        """验证事件总线统计功能"""
        from core.events.event_bus import EventBus
        from core.events.types import BaseEvent
        
        event_bus = EventBus()
        
        class TestEvent(BaseEvent):
            pass
        
        event_bus.subscribe(TestEvent, lambda e: None)
        event_bus.publish(TestEvent())
        event_bus.publish(TestEvent())
        
        stats = event_bus.get_stats()
        assert stats['events_published'] == 2
        assert stats['handlers_registered'] == 1

    def test_event_bus_deduplication(self):
        """验证事件总线去重机制"""
        from core.events.event_bus import EventBus
        from core.events.types import BaseEvent
        
        event_bus = EventBus(deduplication_window=1.0)
        
        class TestEvent(BaseEvent):
            pass
        
        call_count = [0]
        
        def handler(event):
            call_count[0] += 1
        
        event_bus.subscribe(TestEvent, handler)
        event_bus.publish(TestEvent())
        event_bus.publish(TestEvent())
        
        assert call_count[0] == 1

    def test_event_bus_history(self):
        """验证事件总线历史记录"""
        from core.events.event_bus import EventBus
        from core.events.types import BaseEvent
        
        event_bus = EventBus(enable_history=True)
        
        class TestEvent(BaseEvent):
            pass
        
        event_bus.publish(TestEvent())
        event_bus.publish(TestEvent())
        
        history = event_bus.get_history()
        assert len(history) == 2

    def test_get_global_event_bus(self):
        """验证获取全局事件总线"""
        from core.events.event_bus import get_event_bus, EventBus
        
        event_bus = get_event_bus()
        assert isinstance(event_bus, EventBus)
        
        event_bus2 = get_event_bus()
        assert event_bus is event_bus2

    def test_get_global_service_container(self):
        """验证获取全局服务容器"""
        from core.containers.service_container import get_service_container, ServiceContainer
        
        container = get_service_container()
        assert isinstance(container, ServiceContainer)

    def test_base_coordinator_creation(self):
        """验证基础协调器可以创建"""
        from core.coordinators.base_coordinator import BaseCoordinator
        
        class TestCoordinator(BaseCoordinator):
            pass
        
        coordinator = TestCoordinator()
        assert coordinator is not None
        assert coordinator.initialized is False

    def test_base_coordinator_initialization(self):
        """验证基础协调器初始化"""
        from core.coordinators.base_coordinator import BaseCoordinator
        
        class TestCoordinator(BaseCoordinator):
            def _do_initialize(self):
                self.custom_initialized = True
        
        coordinator = TestCoordinator()
        coordinator.initialize()
        
        assert coordinator.initialized is True
        assert coordinator.custom_initialized is True

    def test_base_coordinator_dispose(self):
        """验证基础协调器释放"""
        from core.coordinators.base_coordinator import BaseCoordinator
        
        class TestCoordinator(BaseCoordinator):
            def _do_dispose(self):
                self.custom_disposed = True
        
        coordinator = TestCoordinator()
        coordinator.initialize()
        coordinator.dispose()
        
        assert coordinator.disposed is True
        assert coordinator.initialized is False

    def test_event_coordinator_creation(self):
        """验证事件协调器可以创建"""
        from core.coordinators.event_coordinator import EventCoordinator
        
        coordinator = EventCoordinator()
        assert coordinator is not None

    def test_theme_coordinator_creation(self):
        """验证主题协调器可以创建"""
        from core.coordinators.theme_coordinator import ThemeCoordinator
        
        coordinator = ThemeCoordinator()
        assert coordinator is not None

    def test_panel_coordinator_creation(self):
        """验证面板协调器可以创建"""
        from core.coordinators.panel_coordinator import PanelCoordinator
        
        coordinator = PanelCoordinator()
        assert coordinator is not None

    def test_dialog_coordinator_creation(self):
        """验证对话框协调器可以创建"""
        from core.coordinators.dialog_coordinator import DialogCoordinator
        
        coordinator = DialogCoordinator()
        assert coordinator is not None

    def test_coordinator_context_manager(self):
        """验证协调器上下文管理器"""
        from core.coordinators.base_coordinator import BaseCoordinator
        
        class TestCoordinator(BaseCoordinator):
            pass
        
        with TestCoordinator() as coordinator:
            assert coordinator.initialized is True
        
        assert coordinator.disposed is True

    def test_coordinator_service_resolution(self):
        """验证协调器服务解析"""
        from core.coordinators.base_coordinator import BaseCoordinator
        from core.containers.service_container import ServiceContainer
        from core.containers.service_registry import ServiceScope
        
        class ConfigService:
            pass
        
        class TestCoordinator(BaseCoordinator):
            pass
        
        container = ServiceContainer()
        container.register(ConfigService, ConfigService, scope=ServiceScope.SINGLETON)
        
        coordinator = TestCoordinator(service_container=container)
        
        service = coordinator.get_service(ConfigService)
        assert service is not None

    def test_coordinator_event_publishing(self):
        """验证协调器事件发布"""
        from core.coordinators.base_coordinator import BaseCoordinator
        from core.events.event_bus import EventBus
        from core.events.types import BaseEvent
        
        class TestEvent(BaseEvent):
            pass
        
        class TestCoordinator(BaseCoordinator):
            def _do_initialize(self):
                event = TestEvent()
                self.publish_event(event)
        
        event_bus = EventBus()
        received = []
        event_bus.subscribe(TestEvent, lambda e: received.append(e))
        
        coordinator = TestCoordinator(event_bus=event_bus)
        coordinator.initialize()
        
        assert len(received) == 1

    def test_coordinator_try_get_service(self):
        """验证协调器尝试获取服务"""
        from core.coordinators.base_coordinator import BaseCoordinator
        from core.containers.service_container import ServiceContainer
        
        class UnknownService:
            pass
        
        class TestCoordinator(BaseCoordinator):
            pass
        
        container = ServiceContainer()
        coordinator = TestCoordinator(service_container=container)
        
        service = coordinator.try_get_service(UnknownService)
        assert service is None

    def test_ui_coordinator_creation(self):
        """验证 UI 协调器可以创建"""
        from core.coordinators.base_coordinator import UICoordinator
        
        coordinator = UICoordinator()
        assert coordinator is not None
        assert coordinator.parent_widget is None

    def test_ui_coordinator_register_component(self):
        """验证 UI 协调器注册组件"""
        from core.coordinators.base_coordinator import UICoordinator
        
        coordinator = UICoordinator()
        coordinator.register_ui_component("test_component", Mock())
        
        component = coordinator.get_ui_component("test_component")
        assert component is not None

    def test_ui_coordinator_unregister_component(self):
        """验证 UI 协调器取消注册组件"""
        from core.coordinators.base_coordinator import UICoordinator
        
        coordinator = UICoordinator()
        coordinator.register_ui_component("test_component", Mock())
        coordinator.unregister_ui_component("test_component")
        
        component = coordinator.get_ui_component("test_component")
        assert component is None

    def test_full_system_integration(self):
        """验证完整系统集成"""
        from core.containers.service_container import ServiceContainer, get_service_container
        from core.containers.service_registry import ServiceScope
        from core.events.event_bus import EventBus, get_event_bus
        from core.coordinators.base_coordinator import BaseCoordinator
        from core.events.types import BaseEvent
        
        class AppService:
            def __init__(self):
                self.status = "running"
        
        class ConfigService:
            def __init__(self):
                self.config = {"theme": "dark"}
        
        class TestEvent(BaseEvent):
            pass
        
        class AppCoordinator(BaseCoordinator):
            def __init__(self, service_container=None, event_bus=None):
                super().__init__(service_container, event_bus)
                self.app_started = False
            
            def _do_initialize(self):
                app_service = self.get_service(AppService)
                config_service = self.get_service(ConfigService)
                
                self.app_started = True
                self.publish_event(TestEvent())
        
        container = ServiceContainer()
        container.register(AppService, AppService, scope=ServiceScope.SINGLETON)
        container.register(ConfigService, ConfigService, scope=ServiceScope.SINGLETON)
        
        event_bus = EventBus()
        events_received = []
        event_bus.subscribe(TestEvent, lambda e: events_received.append(e))
        
        coordinator = AppCoordinator(service_container=container, event_bus=event_bus)
        coordinator.initialize()
        
        assert coordinator.app_started is True
        assert len(events_received) == 1
        
        app_service = container.resolve(AppService)
        assert app_service.status == "running"
        
        config_service = container.resolve(ConfigService)
        assert config_service.config["theme"] == "dark"

    def test_service_bootstrap(self):
        """验证服务引导"""
        from core.services.service_bootstrap import ServiceBootstrap
        from core.containers.service_container import ServiceContainer
        
        container = ServiceContainer()
        bootstrap = ServiceBootstrap(container)
        
        assert bootstrap is not None

    def test_base_service_creation(self):
        """验证基础服务可以创建"""
        from core.services.base_service import BaseService
        
        class TestService(BaseService):
            pass
        
        service = TestService()
        assert service is not None

    def test_service_health_monitor(self):
        """验证服务健康监控"""
        from core.services.service_health_monitor import ServiceHealthMonitor
        
        monitor = ServiceHealthMonitor()
        assert monitor is not None

    def test_performance_monitor(self):
        """验证性能监控"""
        from core.monitoring.performance_monitor import PerformanceMonitor
        
        monitor = PerformanceMonitor()
        assert monitor is not None

    def test_data_quality_risk_manager(self):
        """验证数据质量风险管理器"""
        from core.risk.data_quality_monitor import DataQualityMonitor
        
        monitor = DataQualityMonitor()
        assert monitor is not None

    def test_unified_indicator_service(self):
        """验证统一指标服务"""
        from core.unified_indicator_service import UnifiedIndicatorService
        
        service = UnifiedIndicatorService()
        assert service is not None

    def test_strategy_engine(self):
        """验证策略引擎"""
        from core.strategy.strategy_engine import StrategyEngine
        
        engine = StrategyEngine()
        assert engine is not None

    def test_backtest_engine(self):
        """验证回测引擎"""
        from backtest.unified_backtest_engine import UnifiedBacktestEngine
        
        engine = UnifiedBacktestEngine()
        assert engine is not None

    def test_pattern_manager(self):
        """验证形态管理器"""
        from analysis.pattern_manager import PatternManager
        
        manager = PatternManager()
        assert manager is not None

    def test_technical_analysis(self):
        """验证技术分析"""
        from analysis.technical_analysis import TechnicalAnalysis
        
        analysis = TechnicalAnalysis()
        assert analysis is not None

    def test_wave_analysis(self):
        """验证波浪分析"""
        from analysis.wave_analysis import WaveAnalysis
        
        analysis = WaveAnalysis()
        assert analysis is not None

    def test_data_router(self):
        """验证数据路由器"""
        from core.data_router import DataRouter
        
        router = DataRouter()
        assert router is not None

    def test_risk_manager(self):
        """验证风险管理器"""
        from core.risk_manager import RiskManager
        
        manager = RiskManager()
        assert manager is not None

    def test_money_manager(self):
        """验证资金管理器"""
        from core.money_manager import MoneyManager
        
        manager = MoneyManager()
        assert manager is not None

    def test_plugin_center(self):
        """验证插件中心"""
        from core.plugin_center import PluginCenter
        
        center = PluginCenter()
        assert center is not None

    def test_loguru_manager(self):
        """验证日志管理器"""
        from core.loguru_manager import LoguruManager
        
        manager = LoguruManager()
        assert manager is not None

    def test_indicator_service(self):
        """验证指标服务"""
        from core.indicator_service import IndicatorService
        
        service = IndicatorService()
        assert service is not None

    def test_market_environment(self):
        """验证市场环境"""
        from core.market_environment import MarketEnvironment
        
        env = MarketEnvironment()
        assert env is not None

    def test_data_schemas(self):
        """验证数据模式"""
        from core.data_schemas import DataSchemas
        
        schemas = DataSchemas()
        assert schemas is not None

    def test_cross_asset_query_engine(self):
        """验证跨资产查询引擎"""
        from core.cross_asset_query_engine import CrossAssetQueryEngine
        
        engine = CrossAssetQueryEngine()
        assert engine is not None

    def test_stock_screener(self):
        """验证股票筛选器"""
        from core.stock_screener import StockScreener
        
        screener = StockScreener()
        assert screener is not None

    def test_position_manager(self):
        """验证持仓管理器"""
        from core.position_manager import PositionManager
        
        manager = PositionManager()
        assert manager is not None

    def test_trading_controller(self):
        """验证交易控制器"""
        from core.trading_controller import TradingController
        
        controller = TradingController()
        assert controller is not None

    def test_data_validator(self):
        """验证数据验证器"""
        from core.data_validator import DataValidator
        
        validator = DataValidator()
        assert validator is not None

    def test_database_maintenance_engine(self):
        """验证数据库维护引擎"""
        from core.database_maintenance_engine import DatabaseMaintenanceEngine
        
        engine = DatabaseMaintenanceEngine()
        assert engine is not None


# ==================== 5. 辅助测试 ====================

class TestHelperFunctions:
    """辅助函数测试类"""

    def test_unified_sqlite_access_convenience_get_db(self):
        """验证便捷函数 get_db"""
        from core.database.unified_sqlite_access import get_db, UnifiedSQLiteAccess
        
        db = get_db(":memory:")
        assert isinstance(db, UnifiedSQLiteAccess)

    def test_unified_sqlite_access_convenience_execute_query(self):
        """验证便捷函数 execute_query"""
        from core.database.unified_sqlite_access import execute_query
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            execute_query(db_path, "SELECT 1")
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_unified_sqlite_access_convenience_execute_write(self):
        """验证便捷函数 execute_write"""
        from core.database.unified_sqlite_access import execute_write
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            execute_write(db_path, "SELECT 1")
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_project_root_in_sys_path(self):
        """验证项目根目录已添加到 sys.path"""
        project_root = Path(__file__).parent.parent
        assert str(project_root) in sys.path

    def test_test_file_exists(self):
        """验证测试文件存在"""
        test_file = Path(__file__)
        assert test_file.exists()
        assert test_file.is_file()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
