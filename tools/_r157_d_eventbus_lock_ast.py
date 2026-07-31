"""R157-D 事件总线 4 锁独立策略 AST 递归 with.body 嵌套检测 (R104 §12 #3 + #5 强制)"""
import ast
import sys

# 目标: event_bus.py 关键方法
target_methods = [
    'cleanup_orphan_handlers',  # L742-770
    '_publish_internal',        # L1235-1275
    'get_stats',                 # L1495-1500
    'dispose',                   # L1595-1600
    '__len__',                   # L1663-1664
]

# 4 把独立锁
target_locks = {'_lock', '_stats_lock', '_history_lock', '_futures_lock',
                '_dedup_lock', '_registry_lock', '_coro_lock'}

with open('core/events/event_bus.py', 'r', encoding='utf-8') as f:
    source = f.read()

tree = ast.parse(source)

# 查找所有方法定义
method_locations = {}
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == 'EventBus':
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_locations[item.name] = item

print("R157-D 事件总线 4 锁独立策略 AST 递归 with.body 嵌套检测")
print("=" * 80)
print(f"目标方法: {target_methods}")
print(f"目标锁: {target_locks}")
print(f"目标类: EventBus")
print()

def check_nested_locks(method_node, target_locks, parent_locks=set()):
    """递归检测 with.body 内是否嵌套目标锁 (R104 §12 #3 强制)"""
    violations = []

    def visit_block(stmts, current_locks):
        for stmt in stmts:
            if isinstance(stmt, ast.With):
                # 提取 with 块中的锁
                new_locks = set(current_locks)
                for item in stmt.items:
                    ctx = item.context_expr
                    if isinstance(ctx, ast.Attribute) and isinstance(ctx.value, ast.Name):
                        if ctx.value.id == 'self' and ctx.attr in target_locks:
                            new_locks.add(ctx.attr)
                            # 检查是否嵌套
                            if ctx.attr in current_locks:
                                violations.append(f"NESTED LOCK: {ctx.attr} (parent_locks={current_locks})")
                # 递归进入 with.body
                visit_block(stmt.body, new_locks)
            elif isinstance(stmt, ast.Try):
                visit_block(stmt.body, current_locks)
                for handler in stmt.handlers:
                    visit_block(handler.body, current_locks)
            elif isinstance(stmt, ast.If):
                visit_block(stmt.body, current_locks)
                if stmt.orelse:
                    visit_block(stmt.orelse, current_locks)
            elif isinstance(stmt, (ast.For, ast.While)):
                visit_block(stmt.body, current_locks)
                if stmt.orelse:
                    visit_block(stmt.orelse, current_locks)

    visit_block(method_node.body, parent_locks)
    return violations

# 验证每个目标方法
total_violations = 0
for method_name in target_methods:
    if method_name in method_locations:
        method_node = method_locations[method_name]
        violations = check_nested_locks(method_node, target_locks)
        method_start = method_node.lineno
        method_end = method_node.end_lineno if hasattr(method_node, 'end_lineno') else method_node.lineno
        status = "✅ 0 嵌套" if not violations else f"❌ {len(violations)} 嵌套"
        print(f"  [{status}] {method_name} (L{method_start}-{method_end})")
        if violations:
            for v in violations:
                print(f"    - {v}")
        total_violations += len(violations)
    else:
        print(f"  [⚠️ 未找到] {method_name}")

print()
print(f"总嵌套违规: {total_violations}")

# 额外: 列出所有 with self.X 块 (供溯源)
print()
print("所有 with self.<lock> 块统计 (R100-F 4 锁独立策略核验):")
with_block_stats = {}
for node in ast.walk(tree):
    if isinstance(node, ast.With):
        for item in node.items:
            ctx = item.context_expr
            if isinstance(ctx, ast.Attribute) and isinstance(ctx.value, ast.Name):
                if ctx.value.id == 'self' and ctx.attr in target_locks:
                    with_block_stats[ctx.attr] = with_block_stats.get(ctx.attr, 0) + 1

for lock in sorted(target_locks):
    count = with_block_stats.get(lock, 0)
    print(f"  {lock}: {count} 个 with 块")
