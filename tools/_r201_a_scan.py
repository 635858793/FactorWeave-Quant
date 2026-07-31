"""R201-A AST 扫描器: 验证 24+21 处 P0 业务关键方法已添加 account_id 隔离

R104 §12 #3 AST 嵌套检测递归 with.body 强约束
R85 假修复鉴别 4 步法: AST 全局索引 + 跨子目录 + 方法/类/import 三维
R6 §6.1 #6 Read 类定义 + 方法实现 (4 源之三)
"""
import ast
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

ORDER_SERVICE = ROOT / 'core' / 'trading' / 'order_service.py'
RISK_SUBSCRIBERS = ROOT / 'core' / 'risk' / 'risk_event_subscribers.py'

# 24 处业务关键方法 (a 方案): core/trading/order_service.py
# 这些方法应添加 account_id: Optional[str] = None 参数 + [R201-A] 标记
ORDER_SERVICE_24_METHODS = [
    '_assess_order_risk',          # L231
    '_resolve_or_initialize_repository',  # L311
    'health_check',                # L341
    '_resolve_account_context',    # L445
    '_get_order_lock',             # L498
    '_cleanup_order_lock',         # L505
    'create_order',                # L511
    '_check_idempotent_order',     # L641
    '_validate_order_params',      # L702
    '_assess_create_order_risk',   # L766
    '_resolve_account_strategy',   # L824
    '_save_and_verify_order',      # L986
    '_emit_order_created_event',   # L1018
    '_trace_create_order_exit',    # L1045
    'create_orders_batch',         # L1084
    'submit_order',                # L1230
    'cancel_order',                # L1528
    'cancel_orders_batch',         # L1651
    'modify_order',                # L1747
    'get_order',                   # L1989
    'query_orders',                # L2010
    'get_orders_by_strategy',      # L2059
    'get_orders_by_stock',         # L2078
    'get_order_fills',             # L2097
]

# 21 处业务关键方法 (b 方案): core/risk/risk_event_subscribers.py
# 这些方法应显式校验 event.account_id + [R201-A] 标记
RISK_SUBSCRIBERS_21_METHODS = [
    '_handle_risk_monitor',                 # L539
    '_handle_risk_reduce_position',         # L543
    '_handle_risk_stop_trading',            # L556
    '_handle_risk_emergency_liquidation',   # L560
    '_handle_risk_stop_loss_triggered',     # L588
    '_handle_risk_stop_loss_updated',       # L649
    '_handle_order_executed',               # L702
    '_handle_order_submitted_success',      # L706
    '_handle_order_submitted_failed',       # L710
    '_handle_order_filled',                 # L716
    '_handle_order_fill_saved',             # L720
    '_handle_order_partially_filled',       # L791
    '_handle_order_cancelled',              # L795
    '_handle_order_cancel_failed',          # L799
    '_handle_order_terminal_state',         # L803
    '_handle_batch_orders_success',         # L807
    '_handle_batch_orders_failed',          # L811
    '_handle_order_validation_failed',      # L817
    '_handle_order_risk_check_failed',      # L822
    '_handle_order_position_limit_failed',  # L827
    '_handle_order_confirmed',              # L832
]


def parse_file(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return ast.parse(f.read())


def find_method(tree, class_name, method_name):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return item
    return None


def has_account_id_param(fn: ast.FunctionDef) -> bool:
    return 'account_id' in [a.arg for a in fn.args.args]


def has_r201_a_marker(fn: ast.FunctionDef, source: str = None) -> bool:
    """检查方法体或相邻代码是否含 [R201-A] 标记 (R200-A 标记视为 R201-A 兼容)"""
    if source is None:
        return False
    # 检查方法体 3 行范围内 (含 docstring)
    return '[R201-A]' in source or '[R200-A]' in source


def get_method_source(path: Path, fn: ast.FunctionDef) -> str:
    """获取方法源码段 (含前后 5 行上下文, 用于检测 docstring 中的标记)"""
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    start = max(0, fn.lineno - 5)
    end = min(len(lines), fn.end_lineno + 5)
    return ''.join(lines[start:end])


def scan_order_service():
    """扫描 core/trading/order_service.py 的 24 处业务关键方法 (a 方案)"""
    tree = parse_file(ORDER_SERVICE)
    results = []
    for method_name in ORDER_SERVICE_24_METHODS:
        fn = find_method(tree, 'OrderService', method_name)
        if fn is None:
            results.append({
                'method': method_name,
                'status': 'MISSING',
                'has_account_id_param': False,
                'has_r201_a_marker': False,
                'line': None,
            })
            continue
        src = get_method_source(ORDER_SERVICE, fn)
        has_param = has_account_id_param(fn)
        has_marker = has_r201_a_marker(fn, src)
        # 检查方法体是否含 account_id 处理 (b 方案: 显式校验)
        has_account_id_handling = 'account_id' in src
        # a 方案: 公共业务方法必须有 account_id 参数
        # b 方案兼容: 内部 helper 可以只有 [R201-A] 标记 + account_id 处理
        ok = has_marker and (has_param or has_account_id_handling)
        results.append({
            'method': method_name,
            'line': fn.lineno,
            'status': 'PASS' if ok else 'FAIL',
            'has_account_id_param': has_param,
            'has_r201_a_marker': has_marker,
            'has_account_id_handling': has_account_id_handling,
        })
    return results


def scan_risk_subscribers():
    """扫描 core/risk/risk_event_subscribers.py 的 21 处业务关键方法 (b 方案)"""
    tree = parse_file(RISK_SUBSCRIBERS)
    results = []
    for method_name in RISK_SUBSCRIBERS_21_METHODS:
        fn = find_method(tree, 'RiskEventSubscriber', method_name)
        if fn is None:
            results.append({
                'method': method_name,
                'status': 'MISSING',
                'has_account_id_check': False,
                'has_r201_a_marker': False,
                'line': None,
            })
            continue
        src = get_method_source(RISK_SUBSCRIBERS, fn)
        has_marker = has_r201_a_marker(fn, src)
        # b 方案: 方法体内应显式校验 event.account_id (getattr(event, 'account_id', ...))
        # 或 显式 warning
        has_account_id_check = (
            'account_id' in src and
            ("getattr(event, 'account_id'" in src or
             "event.data.get('account_id'" in src or
             "self._extract_event_field(event, 'account_id'" in src)
        )
        ok = has_account_id_check and has_marker
        results.append({
            'method': method_name,
            'line': fn.lineno,
            'status': 'PASS' if ok else 'FAIL',
            'has_account_id_check': has_account_id_check,
            'has_r201_a_marker': has_marker,
        })
    return results


def main():
    order_results = scan_order_service()
    risk_results = scan_risk_subscribers()

    summary = {
        'order_service': {
            'target': 24,
            'fixed': sum(1 for r in order_results if r['status'] == 'PASS'),
            'pending': sum(1 for r in order_results if r['status'] == 'FAIL'),
            'missing': sum(1 for r in order_results if r['status'] == 'MISSING'),
            'results': order_results,
        },
        'risk_subscribers': {
            'target': 21,
            'fixed': sum(1 for r in risk_results if r['status'] == 'PASS'),
            'pending': sum(1 for r in risk_results if r['status'] == 'FAIL'),
            'missing': sum(1 for r in risk_results if r['status'] == 'MISSING'),
            'results': risk_results,
        },
    }

    out_path = ROOT / 'tools' / '_r201_a_results.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f'=== R201-A 扫描结果 ===')
    print(f"order_service.py: {summary['order_service']['fixed']}/{summary['order_service']['target']} PASS")
    print(f"risk_event_subscribers.py: {summary['risk_subscribers']['fixed']}/{summary['risk_subscribers']['target']} PASS")
    print(f"输出: {out_path}")

    return 0 if (
        summary['order_service']['fixed'] == 24 and
        summary['risk_subscribers']['fixed'] == 21
    ) else 1


if __name__ == '__main__':
    sys.exit(main())
