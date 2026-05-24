import sys
sys.path.insert(0, r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui')

def test_batch(batch_name, imports_dict):
    """测试一组导入"""
    print(f"\n{'='*60}")
    print(f"测试: {batch_name}")
    print(f"{'='*60}")
    success = True
    errors = []
    
    for module_path, import_name in imports_dict.items():
        try:
            module = __import__(module_path, fromlist=[import_name])
            getattr(module, import_name)
            print(f"  ✓ {module_path}.{import_name}")
        except Exception as e:
            success = False
            error_msg = f"  ✗ {module_path}.{import_name}\n    错误: {type(e).__name__}: {e}"
            errors.append(error_msg)
            print(error_msg)
    
    if success:
        print(f"\n✅ {batch_name} - 全部通过")
    else:
        print(f"\n❌ {batch_name} - {len(errors)}/{len(imports_dict)} 失败")
        for err in errors:
            print(f"\n{err}")
    
    return success

# Batch 1 - Database Layer
print("\n" + "="*60)
print("Batch 1 - Database Layer")
print("="*60)
try:
    from core.database.duckdb_manager import DuckDBConnectionManager  # 修正为实际类名
    print("  ✓ core.database.duckdb_manager.DuckDBConnectionManager")
except Exception as e:
    print(f"  ✗ core.database.duckdb_manager.DuckDBManager/DuckDBConnectionManager: {e}")

try:
    from core.database.sqlite_extensions import SQLiteExtensionManager  # 修正为实际类名
    print("  ✓ core.database.sqlite_extensions.SQLiteExtensionManager")
except Exception as e:
    print(f"  ✗ core.database.sqlite_extensions.configure_sqlite_extension: {e}")

try:
    from core.database.table_manager import get_table_manager
    print("  ✓ core.database.table_manager.get_table_manager")
except Exception as e:
    print(f"  ✗ core.database.table_manager.get_table_manager: {e}")

# Batch 2 - Core Services
print("\n" + "="*60)
print("Batch 2 - Core Services")
print("="*60)
try:
    from core.services.database_service import DatabaseService
    print("  ✓ core.services.database_service.DatabaseService")
except Exception as e:
    print(f"  ✗ core.services.database_service.DatabaseService: {e}")

try:
    from core.services.db_utils import configure_connection
    print("  ✓ core.services.db_utils.configure_connection")
except Exception as e:
    print(f"  ✗ core.services.db_utils.configure_connection: {e}")

try:
    from core.services.config_service import ConfigService
    print("  ✓ core.services.config_service.ConfigService")
except Exception as e:
    print(f"  ✗ core.services.config_service.ConfigService: {e}")

try:
    from core.services.cache_service import CacheService
    print("  ✓ core.services.cache_service.CacheService")
except Exception as e:
    print(f"  ✗ core.services.cache_service.CacheService: {e}")

try:
    from core.services.stock_service import StockService
    print("  ✓ core.services.stock_service.StockService")
except Exception as e:
    print(f"  ✗ core.services.stock_service.StockService: {e}")

try:
    from core.services.chart_service import ChartService
    print("  ✓ core.services.chart_service.ChartService")
except Exception as e:
    print(f"  ✗ core.services.chart_service.ChartService: {e}")

# Batch 3 - Coordinators
print("\n" + "="*60)
print("Batch 3 - Coordinators")
print("="*60)
try:
    from core.coordinators.main_window_coordinator import MainWindowCoordinator
    print("  ✓ core.coordinators.main_window_coordinator.MainWindowCoordinator")
except Exception as e:
    print(f"  ✗ core.coordinators.main_window_coordinator.MainWindowCoordinator: {e}")

try:
    from core.coordinators.panel_coordinator import PanelCoordinator
    print("  ✓ core.coordinators.panel_coordinator.PanelCoordinator")
except Exception as e:
    print(f"  ✗ core.coordinators.panel_coordinator.PanelCoordinator: {e}")

try:
    from core.coordinators.dialog_coordinator import DialogCoordinator
    print("  ✓ core.coordinators.dialog_coordinator.DialogCoordinator")
except Exception as e:
    print(f"  ✗ core.coordinators.dialog_coordinator.DialogCoordinator: {e}")

try:
    from core.coordinators.event_coordinator import EventCoordinator
    print("  ✓ core.coordinators.event_coordinator.EventCoordinator")
except Exception as e:
    print(f"  ✗ core.coordinators.event_coordinator.EventCoordinator: {e}")

# Batch 4 - Events
print("\n" + "="*60)
print("Batch 4 - Events")
print("="*60)
try:
    from core.events.event_bus import EventBus
    print("  ✓ core.events.event_bus.EventBus")
except Exception as e:
    print(f"  ✗ core.events.event_bus.EventBus: {e}")

try:
    from core.events.event_handler import EventHandler
    print("  ✓ core.events.event_handler.EventHandler")
except Exception as e:
    print(f"  ✗ core.events.event_handler.EventHandler: {e}")

try:
    from core.events.types import StockSelectedEvent
    print("  ✓ core.events.types.StockSelectedEvent")
except Exception as e:
    print(f"  ✗ core.events.types.StockSelectedEvent: {e}")

# Batch 5 - DB Models
print("\n" + "="*60)
print("Batch 5 - DB Models")
print("="*60)
try:
    from db.models.alert_config_models import AlertConfigDatabase
    print("  ✓ db.models.alert_config_models.AlertConfigDatabase")
except Exception as e:
    print(f"  ✗ db.models.alert_config_models.AlertConfigDatabase: {e}")

try:
    from db.models.llm_config_models import LLMConfigManager
    print("  ✓ db.models.llm_config_models.LLMConfigManager")
except Exception as e:
    print(f"  ✗ db.models.llm_config_models.LLMConfigManager: {e}")

try:
    from db.models.ai_config_models import AIPredictionConfigManager
    print("  ✓ db.models.ai_config_models.AIPredictionConfigManager")
except Exception as e:
    print(f"  ✗ db.models.ai_config_models.AIPredictionConfigManager: {e}")

try:
    from db.models.cache_config_models import CacheConfigManager
    print("  ✓ db.models.cache_config_models.CacheConfigManager")
except Exception as e:
    print(f"  ✗ db.models.cache_config_models.CacheConfigManager: {e}")

try:
    from db.models.duckdb_config_models import DuckDBConfigManager
    print("  ✓ db.models.duckdb_config_models.DuckDBConfigManager")
except Exception as e:
    print(f"  ✗ db.models.duckdb_config_models.DuckDBConfigManager: {e}")

try:
    from db.models.indicator_models import Indicator
    print("  ✓ db.models.indicator_models.Indicator")
except Exception as e:
    print(f"  ✗ db.models.indicator_models.Indicator: {e}")

try:
    from db.models.plugin_models import Plugin
    print("  ✓ db.models.plugin_models.Plugin")
except Exception as e:
    print(f"  ✗ db.models.plugin_models.Plugin: {e}")

# Batch 6 - AI Modules
print("\n" + "="*60)
print("Batch 6 - AI Modules")
print("="*60)
try:
    from core.ai.config_impact_analyzer import ConfigImpactAnalyzer
    print("  ✓ core.ai.config_impact_analyzer.ConfigImpactAnalyzer")
except Exception as e:
    print(f"  ✗ core.ai.config_impact_analyzer.ConfigImpactAnalyzer: {e}")

try:
    from core.ai.data_anomaly_detector import DataAnomalyDetector
    print("  ✓ core.ai.data_anomaly_detector.DataAnomalyDetector")
except Exception as e:
    print(f"  ✗ core.ai.data_anomaly_detector.DataAnomalyDetector: {e}")

try:
    from core.ai.user_behavior_learner import UserBehaviorLearner
    print("  ✓ core.ai.user_behavior_learner.UserBehaviorLearner")
except Exception as e:
    print(f"  ✗ core.ai.user_behavior_learner.UserBehaviorLearner: {e}")

# Batch 7 - Risk & Trading
print("\n" + "="*60)
print("Batch 7 - Risk & Trading")
print("="*60)
try:
    from core.risk.compliance_audit_logger import ComplianceAuditLogger
    print("  ✓ core.risk.compliance_audit_logger.ComplianceAuditLogger")
except Exception as e:
    print(f"  ✗ core.risk.compliance_audit_logger.ComplianceAuditLogger: {e}")

try:
    from core.risk.data_quality_monitor import DataQualityMonitor
    print("  ✓ core.risk.data_quality_monitor.DataQualityMonitor")
except Exception as e:
    print(f"  ✗ core.risk.data_quality_monitor.DataQualityMonitor: {e}")

try:
    from core.risk.enhanced_circuit_breaker import EnhancedCircuitBreaker
    print("  ✓ core.risk.enhanced_circuit_breaker.EnhancedCircuitBreaker")
except Exception as e:
    print(f"  ✗ core.risk.enhanced_circuit_breaker.EnhancedCircuitBreaker: {e}")

try:
    from core.risk_rule_manager import RiskRuleManager
    print("  ✓ core.risk_rule_manager.RiskRuleManager")
except Exception as e:
    print(f"  ✗ core.risk_rule_manager.RiskRuleManager: {e}")

try:
    from core.risk_manager import RiskManager
    print("  ✓ core.risk_manager.RiskManager")
except Exception as e:
    print(f"  ✗ core.risk_manager.RiskManager: {e}")

# Batch 8 - Application Core
print("\n" + "="*60)
print("Batch 8 - Application Core")
print("="*60)
try:
    from core.app_initialization import FactorWeaveQuantApplication
    print("  ✓ core.app_initialization.FactorWeaveQuantApplication")
except Exception as e:
    print(f"  ✗ core.app_initialization.FactorWeaveQuantApplication: {e}")

try:
    from core.config import AppConfig
    print("  ✓ core.config.AppConfig")
except Exception as e:
    print(f"  ✗ core.config.AppConfig: {e}")

print("\n" + "="*60)
print("测试完成")
print("="*60)
