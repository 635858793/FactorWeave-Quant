#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R104 §12 #3 + #5: AST 递归 with.body 检测锁嵌套 + AST unparse 验证方法体"""
import ast
import sys

def find_nested_locks(method_node, target_lock_names):
    """R104 §12 #3: 递归检测 with.body 内是否含 target_lock 嵌套"""
    violations = []
    def visit_with(with_node, parent_locks, current_method):
        current_locks = set(parent_locks)
        for item in with_node.items:
            if (isinstance(item.context_expr, ast.Attribute) and
                isinstance(item.context_expr.value, ast.Name) and
                item.context_expr.value.id == 'self' and
                item.context_expr.attr in target_lock_names):
                current_locks.add(item.context_expr.attr)
        for stmt in with_node.body:
            if isinstance(stmt, ast.With):
                for sub_item in stmt.items:
                    if (isinstance(sub_item.context_expr, ast.Attribute) and
                        isinstance(sub_item.context_expr.value, ast.Name) and
                        sub_item.context_expr.value.id == 'self' and
                        sub_item.context_expr.attr in target_lock_names and
                        sub_item.context_expr.attr in current_locks):
                        violations.append({
                            'method': current_method,
                            'parent_lino': with_node.lineno,
                            'nested_lino': stmt.lineno,
                            'lock': sub_item.context_expr.attr
                        })
                visit_with(stmt, current_locks, current_method)
    for n in ast.walk(method_node):
        if isinstance(n, ast.With):
            visit_with(n, set(), method_node.name)
    return violations


def get_method_body(method_node):
    """R104 §12 #5: AST unparse 还原方法体"""
    return ast.unparse(method_node)


def scan_file(filepath, target_methods, target_locks):
    src = open(filepath, encoding='utf-8').read()
    tree = ast.parse(src)
    print(f'\n=== {filepath} ===')
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in target_methods:
            viols = find_nested_locks(node, target_locks)
            body = get_method_body(node)
            results.append({
                'method': node.name,
                'lineno': node.lineno,
                'end_lineno': node.end_lineno,
                'body_lines': node.end_lineno - node.lineno,
                'nested_violations': viols,
            })
            if viols:
                for v in viols:
                    print(f'  [NESTED] {node.name}@L{node.lineno} (range {node.lineno}-{node.end_lineno}, {node.end_lineno-node.lineno} lines): '
                          f'parent_with@L{v["parent_lino"]} NESTED {v["lock"]}@L{v["nested_lino"]}')
            else:
                print(f'  [CLEAN]  {node.name}@L{node.lineno} (range {node.lineno}-{node.end_lineno}, {node.end_lineno-node.lineno} lines): NO NESTED LOCKS')
    return results


# === 扫描 trading_engine.py 长锁方法 ===
TARGET_METHODS = {
    '_execute_buy', '_execute_sell', '_risk_check',
    'execute_order', '_on_position_updated', 'submit_order', 'on_bar_close',
    '_update_position_from_trade', 'unfreeze_cash', 'freeze_cash',
    '_reduce_pending_position', 'place_order', '_check_price_limit',
    '_calculate_cost', '_build_trade_executed_event', '_build_position_updated_event',
    '_enhanced_risk_precheck',
}

TARGET_LOCKS = {
    '_positions_lock', '_cache_lock', '_pending_lock', '_state_lock',
    '_signals_lock', '_portfolio_lock', '_global_lock', '_execution_lock',
    '_shm_lock', '_data_lock', '_rebalance_lock', '_risk_lock',
    '_execution_state_lock', '_health_check_lock',
}

print('========= trading_engine.py (R104 §12 #3 + #5 100% 应用) =========')
te_results = scan_file('core/trading_engine.py', TARGET_METHODS, TARGET_LOCKS)

print('\n========= order_executor.py =========')
oe_results = scan_file('core/trading/order_executor.py', TARGET_METHODS, TARGET_LOCKS)

print('\n========= ai_selection_risk_control_service.py =========')
ai_results = scan_file('core/services/ai_selection_risk_control_service.py', TARGET_METHODS, TARGET_LOCKS)

print('\n========= enhanced_risk_monitor.py (背景) =========')
erm_results = scan_file('core/risk_monitoring/enhanced_risk_monitor.py', TARGET_METHODS, TARGET_LOCKS)

# 汇总
print('\n========= 汇总: 长锁 (>= 30 行) =========')
all_results = te_results + oe_results + ai_results + erm_results
long_locks = [r for r in all_results if r['body_lines'] >= 30]
for r in sorted(long_locks, key=lambda x: -x['body_lines']):
    nested_flag = 'NESTED!' if r['nested_violations'] else 'CLEAN'
    print(f'  {r["method"]:35s} L{r["lineno"]}-{r["end_lineno"]} ({r["body_lines"]:3d} lines) {nested_flag}')
print(f'\n总长锁 (>= 30 行): {len(long_locks)} 项')
print(f'其中嵌套违规: {sum(1 for r in long_locks if r["nested_violations"])} 项')
