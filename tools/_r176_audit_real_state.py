"""R176 真实状态核查工具 - AST 严格 except 块 logger 审计"""
import ast
import os
import json

# 1. R51 #5 实际剩余违规审计
target_files_r51 = [
    r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\service_bootstrap.py',
    r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\events\event_bus.py',
    r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\risk_rule_manager.py',
]

# 2. Trading engine 长锁审计
trading_engine_path = r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\trading_engine.py'

results_r51 = {}

for fp in target_files_r51:
    if not os.path.exists(fp):
        results_r51[fp] = {'error': 'NOT EXIST'}
        continue

    with open(fp, 'r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source)

    total_except = 0
    violations_critical = []  # logger.warning/error 缺 exc_info
    violations_debug = []     # logger.debug 缺 exc_info (非业务关键)

    def visit(node):
        global total_except
        if isinstance(node, ast.ExceptHandler):
            total_except += 1
            block_text = ast.unparse(node)
            # 移除注释行
            lines = []
            for line in block_text.split('\n'):
                if line.strip().startswith('#'):
                    continue
                lines.append(line)
            code_only = '\n'.join(lines)

            # 检查 logger.warning/error/exception (业务关键, 必须 exc_info)
            for log_func in ['logger.warning', 'logger.error', 'logger.exception']:
                if log_func in code_only:
                    if 'exc_info=True' not in code_only:
                        violations_critical.append({
                            'line': node.lineno,
                            'log_func': log_func,
                            'preview': block_text[:200].replace('\n', ' | '),
                        })
            # logger.debug 业务路径可能不要求 exc_info (R51 仅禁止静默失败)
            if 'logger.debug' in code_only and 'exc_info=True' not in code_only:
                # 判断是否在业务关键路径
                is_business_critical = any(keyword in code_only for keyword in [
                    'publish', 'service.', 'order', 'risk', 'trade', 'position'
                ])
                if is_business_critical:
                    violations_debug.append({
                        'line': node.lineno,
                        'log_func': 'logger.debug',
                        'preview': block_text[:200].replace('\n', ' | '),
                    })
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    results_r51[fp] = {
        'total_except': total_except,
        'violations_critical': len(violations_critical),
        'violations_debug_critical': len(violations_debug),
        'critical_samples': violations_critical[:5],
        'debug_samples': violations_debug[:5],
    }

print("=" * 80)
print("R176 R51 #5 真实状态审计 (R175-B 报告 198 处复检)")
print("=" * 80)
print(json.dumps(results_r51, ensure_ascii=False, indent=2))

# 3. Trading engine 长锁审计
print("\n" + "=" * 80)
print("Trading Engine 长锁审计 (HVD-177-C 立项验证)")
print("=" * 80)

with open(trading_engine_path, 'r', encoding='utf-8') as f:
    source = f.read()
tree = ast.parse(source)


def measure_method(node):
    """测量方法实际持锁区间行数 (with 块入口到对应 with 块结束)"""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    method_name = node.name
    method_start = node.lineno
    method_end = node.end_lineno or node.lineno

    # 找 with 块
    def visit_with(n, parent_locks=set()):
        if isinstance(n, ast.With):
            lock_names = set()
            for item in n.items:
                if isinstance(item.context_expr, ast.Attribute):
                    if isinstance(item.context_expr.value, ast.Name) and item.context_expr.value.id == 'self':
                        lock_names.add(item.context_expr.attr)
            current_locks = parent_locks | lock_names
            # 检查 body 内是否还有嵌套
            for stmt in n.body:
                if isinstance(stmt, ast.With):
                    inner_locks = set()
                    for item in stmt.items:
                        if isinstance(item.context_expr, ast.Attribute):
                            if isinstance(item.context_expr.value, ast.Name) and item.context_expr.value.id == 'self':
                                inner_locks.add(item.context_expr.attr)
                    intersection = inner_locks & current_locks
                    if intersection:
                        return {'nested': True, 'locks': list(intersection), 'line': n.lineno}
                    sub = visit_with(stmt, current_locks)
                    if sub:
                        return sub
            return {'nested': False, 'lock_count': len(lock_names), 'start': n.lineno, 'end': n.end_lineno}
        for child in ast.iter_child_nodes(n):
            r = visit_with(child, parent_locks)
            if r:
                return r
        return None

    return {
        'method': method_name,
        'start': method_start,
        'end': method_end,
        'length': method_end - method_start + 1,
        'nesting': visit_with(node),
    }


# 找所有 _execute_buy / _execute_sell / _risk_check 等关键方法
target_methods = ['_execute_buy', '_execute_sell', '_risk_check', 'submit_order', 'execute_order',
                  '_update_position_from_trade', 'handle_order_fill', '_on_position_updated',
                  'on_bar_close', 'unfreeze_cash']

for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.name in target_methods:
            info = measure_method(node)
            if info and info['length'] >= 30:  # 长锁阈值
                print(f"\n{method_name if False else info['method']}:")
                print(f"  Lines: L{info['start']}-L{info['end']} ({info['length']} lines)")
                if info['nesting']:
                    if info['nesting'].get('nested'):
                        print(f"  ⚠️ 嵌套: {info['nesting']['locks']} at L{info['nesting']['line']}")
                    else:
                        print(f"  Lock count: {info['nesting'].get('lock_count', 0)}")
