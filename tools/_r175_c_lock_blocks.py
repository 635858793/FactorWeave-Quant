#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R104 §12 #5: 用 AST unparse 验证方法体, 找出每个方法内具体的锁块范围"""
import ast

def get_lock_blocks(method_node, target_lock_names):
    """遍历方法体, 找出所有 `with self._xxx_lock` 块的精确范围"""
    blocks = []
    def visit_with(with_node, lock_attr):
        body_start = with_node.body[0].lineno if with_node.body else with_node.lineno
        body_end = with_node.body[-1].end_lineno if (with_node.body and hasattr(with_node.body[-1], 'end_lineno')) else body_start
        blocks.append({
            'lock': lock_attr,
            'with_lino': with_node.lineno,
            'body_start': body_start,
            'body_end': body_end,
            'span': body_end - body_start + 1
        })
        for stmt in with_node.body:
            if isinstance(stmt, ast.With):
                for item in stmt.items:
                    if (isinstance(item.context_expr, ast.Attribute) and
                        isinstance(item.context_expr.value, ast.Name) and
                        item.context_expr.value.id == 'self' and
                        item.context_expr.attr in target_lock_names):
                        visit_with(stmt, item.context_expr.attr)
    for n in method_node.body:
        if isinstance(n, ast.With):
            for item in n.items:
                if (isinstance(item.context_expr, ast.Attribute) and
                    isinstance(item.context_expr.value, ast.Name) and
                    item.context_expr.value.id == 'self' and
                    item.context_expr.attr in target_lock_names):
                    visit_with(n, item.context_expr.attr)
    return blocks


def analyze_file(filepath, target_methods, target_locks):
    src = open(filepath, encoding='utf-8').read()
    tree = ast.parse(src)
    print(f'\n========== {filepath} ==========')
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in target_methods:
            blocks = get_lock_blocks(node, target_locks)
            if blocks:
                print(f'\n{node.name}@L{node.lineno}-{node.end_lineno} ({node.end_lineno-node.lineno+1} lines):')
                for b in blocks:
                    if b['span'] >= 30:
                        print(f'  >>> 长锁: with self.{b["lock"]} (L{b["with_lino"]}) '
                              f'body L{b["body_start"]}-{b["body_end"]} ({b["span"]} lines)')


TARGET_LOCKS = {
    '_positions_lock', '_cache_lock', '_pending_lock', '_state_lock',
    '_signals_lock', '_portfolio_lock', '_global_lock', '_execution_lock',
    '_shm_lock', '_data_lock', '_rebalance_lock', '_risk_lock',
    '_execution_state_lock', '_health_check_lock',
}

print('========= trading_engine.py: 长锁块范围 =========')
analyze_file('core/trading_engine.py', {
    '_execute_buy', '_execute_sell', '_risk_check', '_reduce_pending_position',
    'place_order', 'on_bar_close', '_enhanced_risk_precheck'
}, TARGET_LOCKS)

print('\n========= order_executor.py: 长锁块范围 =========')
analyze_file('core/trading/order_executor.py', {
    'submit_order', 'execute_order', '_on_position_updated', 'on_bar_close',
    '_risk_check', '_pre_trade_risk_check'
}, TARGET_LOCKS)

print('\n========= enhanced_risk_monitor.py: 长锁块范围 =========')
analyze_file('core/risk_monitoring/enhanced_risk_monitor.py', {
    'on_bar_close', 'update_portfolio_positions', 'check_order_risk',
    '_check_hhi', '_sync_hhi_from_positions', '_sync_correlation_from_positions',
    'check_correlation_risk', 'get_correlation_summary',
}, TARGET_LOCKS)

print('\n========= ai_selection_risk_control_service.py: 长锁块范围 =========')
analyze_file('core/services/ai_selection_risk_control_service.py', {
    'check_order_risk', 'update_portfolio', 'select_stocks', 'calculate_position_size',
    'unfreeze_cash', 'freeze_cash', 'on_bar_close', 'submit_order',
}, TARGET_LOCKS)
