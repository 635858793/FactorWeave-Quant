"""R+1 round 独立验证脚本: 精确测量 R177 修复的锁结构"""
import ast
import sys


def measure_method_with_locks(filepath, method_name, lock_attrs):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            print(f'\n=== {method_name} (L{node.lineno}-L{node.end_lineno}, {node.end_lineno - node.lineno + 1} 行) ===')

            def visit_with(n, depth=0):
                if isinstance(n, ast.With):
                    is_target = False
                    lock_name = None
                    for item in n.items:
                        ctx = item.context_expr
                        if (isinstance(ctx, ast.Attribute)
                                and isinstance(ctx.value, ast.Name)
                                and ctx.value.id == 'self'):
                            if ctx.attr in lock_attrs:
                                is_target = True
                                lock_name = ctx.attr

                    if is_target:
                        print(f'  L{n.lineno}-L{n.end_lineno} ({n.end_lineno - n.lineno + 1} 行) depth={depth} lock={lock_name}')

                    for stmt in n.body:
                        visit_with(stmt, depth + 1)
                else:
                    for child in ast.iter_child_nodes(n):
                        visit_with(child, depth)

            visit_with(node)
            return
    print(f'未找到方法: {method_name}')


# 1. _execute_buy
print('=' * 80)
print('1. _execute_buy 锁结构验证 (trading_engine.py)')
print('=' * 80)
measure_method_with_locks(
    r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\trading_engine.py',
    '_execute_buy',
    {'_positions_lock', '_cache_lock', '_lock'},
)

# 2. _execute_sell
print('=' * 80)
print('2. _execute_sell 锁结构验证 (trading_engine.py)')
print('=' * 80)
measure_method_with_locks(
    r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\trading_engine.py',
    '_execute_sell',
    {'_positions_lock', '_cache_lock', '_lock'},
)

# 3. _risk_check
print('=' * 80)
print('3. _risk_check 锁结构验证 (trading_engine.py)')
print('=' * 80)
measure_method_with_locks(
    r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\trading_engine.py',
    '_risk_check',
    {'_positions_lock', '_cache_lock', '_lock'},
)

# 4. _risk_check_decide
print('=' * 80)
print('4. _risk_check_decide 锁结构验证 (trading_engine.py)')
print('=' * 80)
measure_method_with_locks(
    r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\trading_engine.py',
    '_risk_check_decide',
    {'_positions_lock', '_cache_lock', '_lock'},
)

# 5. trading_service.execute_order
print('=' * 80)
print('5. trading_service.execute_order 锁结构验证')
print('=' * 80)
measure_method_with_locks(
    r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\trading_service.py',
    'execute_order',
    {'_order_lock', '_position_lock', '_portfolio_lock'},
)

# 6. order_executor.submit_order (L1244)
print('=' * 80)
print('6. order_executor.submit_order 锁结构验证 (L1244+)')
print('=' * 80)
# 找到所有 submit_order 方法, 输出每个
with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\trading\order_executor.py', 'r', encoding='utf-8') as f:
    te_content = f.read()
te_tree = ast.parse(te_content)
for node in ast.walk(te_tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'submit_order':
        print(f'\n[submit_order] L{node.lineno}-L{node.end_lineno} ({node.end_lineno - node.lineno + 1} 行)')

        def visit_with(n, depth=0):
            if isinstance(n, ast.With):
                lock_name = None
                for item in n.items:
                    ctx = item.context_expr
                    if (isinstance(ctx, ast.Attribute)
                            and isinstance(ctx.value, ast.Name)
                            and ctx.value.id == 'self'):
                        if ctx.attr in {'_order_lock', '_state_lock', '_interface_health_lock'}:
                            lock_name = ctx.attr
                if lock_name:
                    print(f'  L{n.lineno}-L{n.end_lineno} ({n.end_lineno - n.lineno + 1} 行) depth={depth} lock={lock_name}')
                for stmt in n.body:
                    visit_with(stmt, depth + 1)
            else:
                for child in ast.iter_child_nodes(n):
                    visit_with(child, depth)
        visit_with(node)
