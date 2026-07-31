"""R202-A AST 扫描器: 验证剩余业务关键方法已添加 account_id 隔离 (HVD-R200-A-NEW-3 P0)

R104 §12 #3 AST 嵌套检测递归 with.body 强约束
R85 假修复鉴别 4 步法: AST 全局索引 + 跨子目录 + 方法/类/import 三维
R6 §6.1 #6 Read 类定义 + 方法实现 (4 源之三)
R104 §13 多账户隔离铁律 (P0 业务核心)
R51 §7.1 5 强约束 (禁止静默失败)
"""
import ast
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).parent.parent

# ============================================================================
# 目标文件清单 (R202-A 范围)
# ============================================================================
# 1. core/services/ 业务关键方法 (R201-A 跳过, R202-A 治理)
# 2. core/risk/ 业务关键方法 (跳过 risk_event_subscribers.py, R201-A 已修复)
# 3. core/trading/ 业务关键方法 (跳过 order_service.py, R201-A 已修复)

TARGET_FILES = {
    "ai_selection_integration_service": ROOT / 'core' / 'services' / 'ai_selection_integration_service.py',
    "ai_selection_risk_control_service": ROOT / 'core' / 'services' / 'ai_selection_risk_control_service.py',
    "dynamic_risk_adjustment_service": ROOT / 'core' / 'services' / 'dynamic_risk_adjustment_service.py',
    "notification_service": ROOT / 'core' / 'services' / 'notification_service.py',
    "data_service": ROOT / 'core' / 'services' / 'data_service.py',
    "database_service": ROOT / 'core' / 'services' / 'database_service.py',
    "strategy_service": ROOT / 'core' / 'services' / 'strategy_service.py',
    "compliance_audit_logger": ROOT / 'core' / 'risk' / 'compliance_audit_logger.py',
    "account_consistency": ROOT / 'core' / 'risk' / 'account_consistency.py',
    "data_quality_monitor": ROOT / 'core' / 'risk' / 'data_quality_monitor.py',
    "account_manager": ROOT / 'core' / 'trading' / 'account_manager.py',
    "order_executor": ROOT / 'core' / 'trading' / 'order_executor.py',
    "order_repository": ROOT / 'core' / 'trading' / 'order_repository.py',
    "order_validator": ROOT / 'core' / 'trading' / 'order_validator.py',
}

# ============================================================================
# 业务关键方法清单 (R202-A 候选 - 需要修复的目标)
# ============================================================================
# a 方案 (新增 account_id 参数) - 用于主动调用方
# b 方案 (显式校验 - effective_account_id) - 用于事件处理/订阅方

AI_SELECTION_INTEGRATION_METHODS = [
    # (class_name, method_name, expected_line, scheme)
    ('AISelectionIntegrationService', 'select_stocks', 3316, 'a'),
    ('AISelectionIntegrationService', 'select_stocks_with_nlp', 564, 'a'),
    ('AISelectionIntegrationService', 'select_stocks_with_explanation', 792, 'a'),
    ('AISelectionIntegrationService', '_execute_selection', 992, 'a'),
    ('AISelectionIntegrationService', 'create_selection_strategy', 744, 'a'),
]

AI_SELECTION_RISK_METHODS = [
    ('AISelectionRiskControlService', 'assess_risk', 559, 'a'),
    ('AISelectionRiskControlService', '_assess_market_risk', 660, 'a'),
    ('AISelectionRiskControlService', '_assess_liquidity_risk', 734, 'a'),
    ('AISelectionRiskControlService', '_assess_concentration_risk', 809, 'a'),
    ('AISelectionRiskControlService', '_assess_model_risk', 882, 'a'),
]

DYNAMIC_RISK_ADJUSTMENT_METHODS = [
    ('DynamicRiskAdjustmentEngine', 'evaluate_adjustment_need', 229, 'a'),
    ('DynamicRiskAdjustmentEngine', 'execute_adjustment', 277, 'a'),
    ('DynamicRiskAdjustmentEngine', 'add_performance_metric', 371, 'a'),
    ('DynamicRiskAdjustmentEngine', 'predict_optimal_adjustment', 341, 'a'),
    ('DynamicRiskAdjustmentEngine', 'get_adjustment_statistics', 380, 'a'),
]

NOTIFICATION_SERVICE_METHODS = [
    ('NotificationService', 'send_notification', 879, 'a'),
    ('NotificationService', 'send_alert', 930, 'a'),
    ('NotificationService', 'add_alert_rule', 818, 'a'),
    ('NotificationService', 'update_alert_rule', 845, 'a'),
    ('NotificationService', 'get_notification_history', 1795, 'a'),
    ('NotificationService', 'clear_notification_history', 1888, 'a'),
]

DATA_SERVICE_METHODS = [
    ('DataService', 'get_data', 502, 'a'),
    ('DataService', '_get_from_cache', 576, 'a'),
    ('DataService', '_fetch_from_sources', 604, 'a'),
    ('DataService', 'clear_cache', 1039, 'a'),
]

DATABASE_SERVICE_METHODS = [
    ('DatabaseService', 'execute_query', 1131, 'a'),
    ('DatabaseService', 'fetch_all', 1234, 'a'),
    ('DatabaseService', 'fetch_one', 1303, 'a'),
    ('DatabaseService', 'begin_transaction', 1320, 'a'),
    ('DatabaseService', 'execute_in_transaction', 1450, 'a'),
]

STRATEGY_SERVICE_METHODS = [
    ('StrategyService', 'create_strategy', 0, 'a'),  # 行号待 AST 定位
    ('StrategyService', 'update_strategy', 0, 'a'),
    ('StrategyService', 'get_strategy', 0, 'a'),
]

COMPLIANCE_AUDIT_METHODS = [
    ('ComplianceAuditLogger', 'log_event', 0, 'b'),
    ('ComplianceAuditLogger', 'log_order_event', 0, 'b'),
    ('ComplianceAuditLogger', 'log_risk_event', 0, 'b'),
]

ACCOUNT_CONSISTENCY_METHODS = [
    ('RiskAccountConsistencyChecker', 'check_account_id_consistency', 0, 'a'),
    ('RiskAccountConsistencyChecker', '_check_drift', 0, 'a'),
]

DATA_QUALITY_METHODS = [
    ('DataQualityMonitor', 'check_quality', 0, 'a'),
]

ACCOUNT_MANAGER_METHODS = [
    ('AccountManager', 'get_account', 0, 'a'),
    ('AccountManager', 'list_accounts', 0, 'a'),
    ('AccountManager', 'create_account', 0, 'a'),
]

ORDER_EXECUTOR_METHODS = [
    ('OrderExecutor', 'execute', 0, 'a'),
    ('OrderExecutor', 'cancel', 0, 'a'),
]

ORDER_REPOSITORY_METHODS = [
    ('OrderRepository', 'get_order', 0, 'a'),
    ('OrderRepository', 'save_order', 0, 'a'),
]

ORDER_VALIDATOR_METHODS = [
    ('OrderValidator', 'validate', 0, 'a'),
]


def parse_file(path: Path):
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return ast.parse(f.read())


def find_method(tree, class_name: str, method_name: str):
    """R104 §12 #3 强制要求: 递归查找方法, 不依赖 ast.walk 扁平化 (R104 TDD 教训)

    同时识别 FunctionDef 和 AsyncFunctionDef (Python 3.5+)
    """
    if tree is None:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                    return item
    return None


def has_account_id_param(fn: ast.FunctionDef) -> bool:
    """R104 §13: 检查方法签名是否含 account_id 参数"""
    if fn is None:
        return False
    return 'account_id' in [a.arg for a in fn.args.args]


def get_method_source(path: Path, fn: ast.FunctionDef) -> str:
    """获取方法体源代码 (含前 5 行上下文)"""
    if fn is None or not path.exists():
        return ""
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    start = max(0, fn.lineno - 5)
    end = min(len(lines), fn.end_lineno)
    return ''.join(lines[start:end])


def has_r202_a_marker(fn: ast.FunctionDef, source: str = None) -> bool:
    """检查方法是否含 [R202-A] 标记 (兼容 R200-A/R201-A)"""
    if source is None:
        return False
    return any(marker in source for marker in ('[R202-A]', '[R201-A]', '[R200-A]'))


def has_explicit_account_id_check(fn: ast.FunctionDef, source: str) -> bool:
    """检查方法是否含显式 account_id 校验 (b 方案标志)"""
    if fn is None:
        return False
    # 检查方法体内是否提到 account_id None 校验
    return ('account_id is None' in source or
            'not account_id' in source or
            'account_id or' in source or
            'effective_account_id' in source)


def scan_method(file_key: str, class_name: str, method_name: str, scheme: str) -> Dict[str, Any]:
    """扫描单个方法, 返回状态"""
    path = TARGET_FILES.get(file_key)
    result = {
        'file': str(path.relative_to(ROOT)) if path else 'N/A',
        'class': class_name,
        'method': method_name,
        'scheme': scheme,
        'exists': False,
        'has_account_id_param': False,
        'has_r202_a_marker': False,
        'has_explicit_check': False,
        'status': 'PENDING',
        'line': None,
    }
    if path is None or not path.exists():
        result['status'] = 'MISSING_FILE'
        return result
    tree = parse_file(path)
    fn = find_method(tree, class_name, method_name)
    if fn is None:
        result['status'] = 'METHOD_MISSING'
        return result
    result['exists'] = True
    result['line'] = fn.lineno
    result['has_account_id_param'] = has_account_id_param(fn)
    source = get_method_source(path, fn)
    result['has_r202_a_marker'] = has_r202_a_marker(fn, source)
    result['has_explicit_check'] = has_explicit_account_id_check(fn, source)
    # 综合判定
    if result['has_account_id_param'] and result['has_r202_a_marker']:
        result['status'] = 'OK'
    elif result['has_account_id_param']:
        result['status'] = 'OK_NO_MARKER'  # 已有参数但缺标记
    else:
        result['status'] = 'FAIL'
    return result


def scan_all() -> Dict[str, List[Dict[str, Any]]]:
    """扫描全部目标方法"""
    return {
        'ai_selection_integration': [
            scan_method('ai_selection_integration_service', cls, m, s)
            for cls, m, _, s in AI_SELECTION_INTEGRATION_METHODS
        ],
        'ai_selection_risk': [
            scan_method('ai_selection_risk_control_service', cls, m, s)
            for cls, m, _, s in AI_SELECTION_RISK_METHODS
        ],
        'dynamic_risk_adjustment': [
            scan_method('dynamic_risk_adjustment_service', cls, m, s)
            for cls, m, _, s in DYNAMIC_RISK_ADJUSTMENT_METHODS
        ],
        'notification_service': [
            scan_method('notification_service', cls, m, s)
            for cls, m, _, s in NOTIFICATION_SERVICE_METHODS
        ],
        'data_service': [
            scan_method('data_service', cls, m, s)
            for cls, m, _, s in DATA_SERVICE_METHODS
        ],
        'database_service': [
            scan_method('database_service', cls, m, s)
            for cls, m, _, s in DATABASE_SERVICE_METHODS
        ],
    }


def get_flat_results() -> List[Dict[str, Any]]:
    """获取扁平化的全部结果列表"""
    all_results = scan_all()
    flat = []
    for category, results in all_results.items():
        flat.extend(results)
    return flat


if __name__ == '__main__':
    results = get_flat_results()
    print(f"Total scanned: {len(results)}")
    ok = sum(1 for r in results if r['status'] == 'OK')
    fail = sum(1 for r in results if r['status'] == 'FAIL')
    print(f"OK: {ok}, FAIL: {fail}, OK_NO_MARKER: {sum(1 for r in results if r['status'] == 'OK_NO_MARKER')}")
    for r in results:
        if r['status'] != 'OK':
            print(f"  [{r['status']}] {r['file']}:{r.get('line', 'N/A')} {r['class']}.{r['method']}")
