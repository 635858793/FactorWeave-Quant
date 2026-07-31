#!/usr/bin/env python3
"""
R129 子智能体 C - 维度 3 锁架构 + 维度 5 BaseService 继承扫描脚本
"""
import ast
import os
import sys

# ===== 维度 3: 锁嵌套检测 (R104 §12 铁律 #3 递归 with.body) =====
def detect_nested_locks_recursive(file_path, target_lock_names):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return []

    violations = []

    def get_lock_name(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    def visit_block(body, parent_locks, current_method=None):
        for stmt in body:
            if isinstance(stmt, ast.With):
                new_parents = set(parent_locks)
                for item in stmt.items:
                    lock_name = get_lock_name(item.context_expr)
                    if lock_name and lock_name in target_lock_names:
                        if lock_name in parent_locks:
                            violations.append({
                                'method': current_method,
                                'lock': lock_name,
                                'line': stmt.lineno,
                                'parent_locks': list(parent_locks)
                            })
                        new_parents.add(lock_name)
                visit_block(stmt.body, new_parents, current_method)
            elif isinstance(stmt, ast.Try):
                visit_block(stmt.body, parent_locks, current_method)
                for h in stmt.handlers:
                    visit_block(h.body, parent_locks, current_method)
                if stmt.finalbody:
                    visit_block(stmt.finalbody, parent_locks, current_method)
            elif isinstance(stmt, (ast.If, ast.For, ast.While)):
                visit_block(stmt.body, parent_locks, current_method)
                if hasattr(stmt, 'orelse') and stmt.orelse:
                    visit_block(stmt.orelse, parent_locks, current_method)
            elif isinstance(stmt, ast.AsyncWith):
                visit_block(stmt.body, parent_locks, current_method)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            visit_block(node.body, set(), node.name)

    return violations


def scan_dim3():
    target_locks = ['_lock', '_positions_lock', '_orders_lock', '_pending_lock',
                    '_cache_lock', '_stats_lock', '_history_lock', '_futures_lock',
                    '_order_lock', '_inflight_kdata_lock', '_dedup_lock', '_coro_lock']

    files_to_check = [
        'core/trading_engine.py', 'core/risk_manager.py',
        'core/events/event_bus.py', 'core/services/unified_data_manager.py',
        'core/services/cache_service.py', 'core/position_manager.py',
        'core/stop_loss.py', 'core/take_profit.py',
        'core/trading/order_executor.py', 'core/trading/account_manager.py',
        'core/trading/order_service.py', 'core/trading/order_repository.py',
        'core/services/advanced_risk_control_service.py',
        'core/services/dynamic_risk_adjustment_service.py',
        'core/risk_monitoring/enhanced_risk_monitor.py',
        'core/services/notification_service.py',
        'core/services/unified_cache_provider.py',
        'core/services/sector_data_service.py',
        'core/money_manager.py', 'core/indicator_service.py',
        'core/services/trading_service.py',
    ]

    print('R129-C 维度 3 锁架构 AST 递归 with.body 嵌套检测')
    print('=' * 80)
    total = 0
    for f in files_to_check:
        if not os.path.exists(f):
            print(f'NOT_FOUND: {f}')
            continue
        violations = detect_nested_locks_recursive(f, target_locks)
        if violations:
            print(f'\n{f}: {len(violations)} 嵌套违规')
            for v in violations[:5]:
                print(f'  L{v["line"]} {v["method"]}: {v["lock"]} 嵌套 in {v["parent_locks"]}')
            total += len(violations)
        else:
            print(f'{f}: 0 嵌套')
    print(f'\n总计: {total} 锁嵌套违规')


# ===== 维度 5: BaseService 继承检测 =====
def scan_dim5():
    """扫描 core/services/ 全部 Service/Manager/Engine 类是否继承 BaseService"""
    print('\n\nR129-C 维度 5 BaseService 继承检测')
    print('=' * 80)

    candidates = []
    services_dir = 'core/services'
    for f in os.listdir(services_dir):
        if not f.endswith('.py') or f == '__init__.py':
            continue
        path = os.path.join(services_dir, f)
        try:
            with open(path, 'r', encoding='utf-8') as fp:
                source = fp.read()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # 检查类名是否含 Service/Manager/Engine/Provider/Handler/Monitor
                keywords = ['Service', 'Manager', 'Engine', 'Provider', 'Handler',
                           'Monitor', 'Coordinator', 'Builder', 'Factory',
                           'Processor', 'Resolver', 'Collector', 'Exporter']
                if not any(kw in node.name for kw in keywords):
                    continue
                # 检查基类
                base_names = []
                for b in node.bases:
                    if isinstance(b, ast.Name):
                        base_names.append(b.id)
                    elif isinstance(b, ast.Attribute):
                        base_names.append(b.attr)
                has_base_service = 'BaseService' in base_names
                has_qobject = 'QObject' in base_names
                # 是否继承 BaseService
                if not has_base_service:
                    candidates.append({
                        'class': node.name,
                        'file': path,
                        'line': node.lineno,
                        'bases': base_names,
                        'has_qobject': has_qobject,
                    })

    print(f'\n发现 {len(candidates)} 个候选类 (未继承 BaseService):')
    for c in candidates:
        qo = ' (QObject)' if c['has_qobject'] else ''
        print(f'  {c["file"]}:{c["line"]} {c["class"]} 基类={c["bases"]}{qo}')


if __name__ == '__main__':
    os.chdir('d:\\DevelopTool\\FreeCode\\HIkyuu-UI\\hikyuu-ui')
    scan_dim3()
    scan_dim5()
