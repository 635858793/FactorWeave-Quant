#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R104 §12 5铁律 100% 应用: 综合扫描所有目标文件的长锁与嵌套"""
import ast
import os

TARGET_LOCKS = {
    '_positions_lock', '_cache_lock', '_pending_lock', '_state_lock',
    '_signals_lock', '_portfolio_lock', '_global_lock', '_execution_lock',
    '_shm_lock', '_data_lock', '_rebalance_lock', '_risk_lock',
    '_execution_state_lock', '_health_check_lock', '_account_lock',
    '_position_lock', '_order_lock', '_alert_history_lock', '_monitoring_lock',
}


def find_nested_locks(method_node, target_lock_names):
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


def get_lock_blocks(method_node, target_lock_names):
    """R104 §12 #3 改进: 递归遍历 method 所有 stmt 子节点, 找出 with self._xxx_lock 块"""
    blocks = []
    def visit_stmt(stmt, parent_locks=set()):
        # 找到当前层的 with 块
        for n in (stmt.body if hasattr(stmt, 'body') else []):
            if isinstance(n, ast.With):
                for item in n.items:
                    if (isinstance(item.context_expr, ast.Attribute) and
                        isinstance(item.context_expr.value, ast.Name) and
                        item.context_expr.value.id == 'self' and
                        item.context_expr.attr in target_lock_names):
                        # 找到 with 块, 计算 body 范围
                        body_start = n.body[0].lineno if n.body else n.lineno
                        body_end = n.body[-1].end_lineno if (n.body and hasattr(n.body[-1], 'end_lineno')) else body_start
                        blocks.append({
                            'lock': item.context_expr.attr,
                            'with_lino': n.lineno,
                            'body_start': body_start,
                            'body_end': body_end,
                            'span': body_end - body_start + 1
                        })
                        # 递归进入 with 块内部, 查找嵌套
                        for sub_stmt in n.body:
                            visit_stmt(sub_stmt, parent_locks | {item.context_expr.attr})
            elif isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
                visit_stmt(n, parent_locks)
            elif hasattr(n, 'body') and isinstance(n.body, list):
                for sub in n.body:
                    if isinstance(sub, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
                        visit_stmt(sub, parent_locks)
    # 方法体本身
    for stmt in method_node.body:
        if isinstance(stmt, ast.With):
            for item in stmt.items:
                if (isinstance(item.context_expr, ast.Attribute) and
                    isinstance(item.context_expr.value, ast.Name) and
                    item.context_expr.value.id == 'self' and
                    item.context_expr.attr in target_lock_names):
                    body_start = stmt.body[0].lineno if stmt.body else stmt.lineno
                    body_end = stmt.body[-1].end_lineno if (stmt.body and hasattr(stmt.body[-1], 'end_lineno')) else body_start
                    blocks.append({
                        'lock': item.context_expr.attr,
                        'with_lino': stmt.lineno,
                        'body_start': body_start,
                        'body_end': body_end,
                        'span': body_end - body_start + 1
                    })
                    for sub_stmt in stmt.body:
                        visit_stmt(sub_stmt, {item.context_expr.attr})
        elif isinstance(stmt, (ast.If, ast.For, ast.While, ast.Try)):
            visit_stmt(stmt)
    return blocks


def analyze_file(filepath):
    if not os.path.exists(filepath):
        print(f'[SKIP] {filepath} not found')
        return []
    src = open(filepath, encoding='utf-8').read()
    tree = ast.parse(src)
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            viols = find_nested_locks(node, TARGET_LOCKS)
            blocks = get_lock_blocks(node, TARGET_LOCKS)
            long_locks = [b for b in blocks if b['span'] >= 30]
            if long_locks or viols:
                results.append({
                    'method': node.name,
                    'lineno': node.lineno,
                    'end_lineno': node.end_lineno,
                    'file': filepath,
                    'long_locks': long_locks,
                    'nested_violations': viols,
                })
    return results


print('=' * 80)
print('综合扫描: 所有目标文件的长锁 + 嵌套违规')
print('=' * 80)

FILES = [
    'core/trading_engine.py',
    'core/trading/order_executor.py',
    'core/trading/account_manager.py',
    'core/services/trading_service.py',
    'core/services/ai_selection_risk_control_service.py',
    'core/risk_monitoring/enhanced_risk_monitor.py',
]

all_results = []
for f in FILES:
    results = analyze_file(f)
    if results:
        print(f'\n===== {f} =====')
        for r in results:
            nested = 'NESTED!' if r['nested_violations'] else 'CLEAN'
            print(f'  {r["method"]:40s} L{r["lineno"]}-{r["end_lineno"]} {nested}')
            for b in r['long_locks']:
                print(f'      -> 长锁: with self.{b["lock"]} (L{b["with_lino"]}) '
                      f'body L{b["body_start"]}-{b["body_end"]} ({b["span"]} lines)')
        all_results.extend(results)

print(f'\n{"=" * 80}')
print(f'总长锁方法数: {len(all_results)}')
print(f'其中嵌套违规: {sum(1 for r in all_results if r["nested_violations"])}')

# 按文件分组汇总
by_file = {}
for r in all_results:
    by_file.setdefault(r['file'], []).append(r)
print(f'\n按文件汇总:')
for f, rs in by_file.items():
    print(f'  {f}: {len(rs)} 项长锁方法')
