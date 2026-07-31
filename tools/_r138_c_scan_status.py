"""R138 子智能体 C: 扫描所有已修改文件,找出错误的 _do_health_check / _do_dispose 注入."""
import ast
from pathlib import Path
import sys

PROJECT_ROOT = Path('.').resolve()

HEALTHCHECK_FILES = {
    "AlertRuleHotLoader": "core/services/alert_rule_hot_loader.py",
    "AsyncBaseService": "core/services/base_service.py",
    "ConfigurableService": "core/services/base_service.py",
    "CacheableService": "core/services/base_service.py",
    "BondService": "core/services/bond_service.py",
    "DatabaseMonitoringService": "core/services/database_monitoring_service.py",
    "DividendDataService": "core/services/dividend_data_service.py",
    "ExtensionService": "core/services/extension_service.py",
    "FundService": "core/services/fund_service.py",
    "GPUAccelerationManager": "core/services/gpu_acceleration_manager.py",
    "HybridRecommendationEngine": "core/services/hybrid_recommendation_engine.py",
    "IndexService": "core/services/index_service.py",
    "IndustryService": "core/services/industry_service.py",
    "ModelTrainingService": "core/services/model_training_service.py",
    "PerformanceBaselineService": "core/services/performance_baseline_service.py",
    "PredictionTrackingService": "core/services/prediction_tracking_service.py",
    "SystemOptimizerService": "core/services/system_optimizer.py",
}

DISPOSE_FILES = {
    "AISelectionBacktestService": "core/services/ai_selection_backtest_service.py",
    "AISelectionRiskControlService": "core/services/ai_selection_risk_control_service.py",
    "AuditDeadCodeService": "core/services/audit_dead_code_service.py",
    "AsyncBaseService": "core/services/base_service.py",
    "ConfigurableService": "core/services/base_service.py",
    "BondService": "core/services/bond_service.py",
    "DataMaskingService": "core/services/data_masking_service.py",
    "DatabaseMonitoringService": "core/services/database_monitoring_service.py",
    "DeepAnalysisService": "core/services/deep_analysis_service.py",
    "DistributedService": "core/services/distributed_service.py",
    "DividendDataService": "core/services/dividend_data_service.py",
    "DynamicRiskAdjustmentService": "core/services/dynamic_risk_adjustment_service.py",
    "FundingRateAnalysisService": "core/services/funding_rate_analysis_service.py",
    "FundService": "core/services/fund_service.py",
    "HybridRecommendationEngine": "core/services/hybrid_recommendation_engine.py",
    "IndexService": "core/services/index_service.py",
    "ModelTrainingService": "core/services/model_training_service.py",
    "PredictionTrackingService": "core/services/prediction_tracking_service.py",
    "SectorDataService": "core/services/sector_data_service.py",
    "SystemOptimizerService": "core/services/system_optimizer.py",
    "TdxServerDiscoveryService": "core/services/tdx_server_discovery.py",
    "TradingConfirmationService": "core/services/trading_confirmation_service.py",
}


def check_file(file_path: Path, class_name: str) -> dict:
    """检查文件的语法和类内方法."""
    try:
        content = file_path.read_text(encoding='utf-8')
        tree = ast.parse(content)
    except SyntaxError as e:
        return {'error': str(e), 'lineno': e.lineno}

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append({
                        'name': item.name,
                        'lineno': item.lineno,
                        'end_lineno': item.end_lineno,
                    })
            return {'methods': methods, 'end_lineno': node.end_lineno}
    return {'error': 'class not found'}


# 扫描所有文件
print("=== healthcheck 候选 ===")
hc_ok = hc_fail = 0
for cls, rel in HEALTHCHECK_FILES.items():
    fp = PROJECT_ROOT / rel
    result = check_file(fp, cls)
    if 'error' in result:
        print(f"  [FAIL] {rel}::{cls}: {result['error']} (L{result.get('lineno', '?')})")
        hc_fail += 1
    else:
        has_hc = any(m['name'] == '_do_health_check' for m in result['methods'])
        if has_hc:
            hc_ok += 1
        else:
            print(f"  [MISSING] {rel}::{cls}: 无 _do_health_check")
            hc_fail += 1

print(f"\nhealthcheck: {hc_ok} OK, {hc_fail} FAIL")

print("\n=== dispose 候选 ===")
dp_ok = dp_fail = 0
for cls, rel in DISPOSE_FILES.items():
    fp = PROJECT_ROOT / rel
    result = check_file(fp, cls)
    if 'error' in result:
        print(f"  [FAIL] {rel}::{cls}: {result['error']} (L{result.get('lineno', '?')})")
        dp_fail += 1
    else:
        has_dp = any(m['name'] == '_do_dispose' for m in result['methods'])
        if has_dp:
            dp_ok += 1
        else:
            print(f"  [MISSING] {rel}::{cls}: 无 _do_dispose")
            dp_fail += 1

print(f"\ndispose: {dp_ok} OK, {dp_fail} FAIL")
print(f"\n总计: {hc_ok + dp_ok} OK, {hc_fail + dp_fail} FAIL")
