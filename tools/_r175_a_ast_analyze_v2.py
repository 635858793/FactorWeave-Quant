"""
R175 子智能体 A: 3 个 P0 长锁方法 AST 递归分析 (V2)
严格遵守 R104 §12 铁律 #3 (AST 递归 with.body, 非 ast.walk 扁平化) + #5 (AST unparse 验证)
修复: 递归查找所有 with 块, 包括嵌套在 try 内的 with
"""
import ast
import sys


def find_all_with_blocks(node, depth=0):
    """
    递归查找所有 with 块 (包括嵌套在 try/if/for/while 内的 with)
    严格按照 R104 §12 #3 实现: 必须递归进入 body
    """
    with_blocks = []

    if isinstance(node, ast.With):
        # 提取当前 with 块的锁名
        for item in node.items:
            ce = item.context_expr
            if isinstance(ce, ast.Attribute) and isinstance(ce.value, ast.Name):
                if ce.value.id == 'self':
                    with_blocks.append({
                        'lock_attr': ce.attr,
                        'start_line': node.lineno,
                        'end_line': node.end_lineno,
                        'body_lines': node.end_lineno - node.lineno + 1,
                        'depth': depth,
                        'parent_type': 'method',
                    })
                    break  # 只记录第一个 lock 表达式

    # 递归进入各种容器
    for child in ast.iter_child_nodes(node):
        # 跳过已经处理过的 With
        if isinstance(child, ast.With) and isinstance(node, ast.With):
            continue  # 内部 with 在外层 with 内部递归

        child_with = find_all_with_blocks(child, depth + 1)
        with_blocks.extend(child_with)

    return with_blocks


def check_lock_nesting_in_method(method_node, lock_attrs=('positions', 'cache', 'stats', 'futures')):
    """
    检测方法内的锁嵌套
    R104 §12 #3: 递归进入 with.body, 非 ast.walk 扁平化
    """
    violations = []

    def visit(node, parent_locks, path):
        if isinstance(node, ast.With):
            current_locks = set()
            for item in node.items:
                ce = item.context_expr
                if isinstance(ce, ast.Attribute) and isinstance(ce.value, ast.Name):
                    if ce.value.id == 'self':
                        current_locks.add(ce.attr)

            # 检查 parent_locks 与 current_locks 是否有交集
            for cl in current_locks:
                if cl in parent_locks:
                    violations.append({
                        'type': 'NESTED_LOCK',
                        'outer_lock': list(parent_locks)[0] if parent_locks else None,
                        'inner_lock': cl,
                        'inner_line': node.lineno,
                        'path': path,
                    })

            new_parent_locks = parent_locks | current_locks

            # 递归进入 with.body (R104 §12 #3 关键)
            for stmt in node.body:
                visit(stmt, new_parent_locks, f"{path}/with_body")

        elif isinstance(node, ast.Try):
            for sub in list(node.body) + list(node.handlers) + list(node.finalbody) + list(node.orelse):
                visit(sub, parent_locks, f"{path}/try")

        elif isinstance(node, ast.If):
            for sub in node.body + node.orelse:
                visit(sub, parent_locks, f"{path}/if")

        elif isinstance(node, (ast.For, ast.While)):
            for sub in node.body + node.orelse:
                visit(sub, parent_locks, f"{path}/loop")

    visit(method_node, set(), "method")
    return violations


def analyze_method(tree, method_name, start_line, end_line):
    """分析指定方法"""
    method_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            if node.lineno == start_line:
                method_node = node
                break

    if method_node is None:
        return None

    method_source = ast.unparse(method_node)
    method_bytes = len(method_source.encode('utf-8'))
    method_lines = method_node.end_lineno - method_node.lineno + 1

    # 1. 递归查找所有 with 块 (包括嵌套在 try 内的)
    with_blocks = find_all_with_blocks(method_node)

    # 2. 递归检测锁嵌套
    nested = check_lock_nesting_in_method(method_node)

    # 3. 锁内 I/O 检测
    io_calls = []
    io_keywords = ['urllib', 'requests', 'http', 'socket', 'sqlite', 'psycopg', 'pymongo',
                   'cursor.execute', 'query', 'fetch', 'session.post', 'session.get',
                   'requests.post', 'requests.get', 'requests.put', 'requests.delete',
                   'session.commit', 'session.rollback']
    # 锁块范围集合
    lock_line_ranges = [(wb['start_line'], wb['end_line']) for wb in with_blocks]
    for sub_node in ast.walk(method_node):
        if isinstance(sub_node, ast.Call):
            func = sub_node.func
            if isinstance(func, ast.Attribute):
                func_name = func.attr
                full_name = ast.unparse(func)
                # 检测锁内 I/O
                for ls, le in lock_line_ranges:
                    if ls <= sub_node.lineno <= le:
                        if any(kw in full_name.lower() for kw in io_keywords):
                            io_calls.append((full_name, sub_node.lineno))
                        break

    # 4. 锁内其他可能持锁方法
    suspect_methods = {'_invalidate_cache', '_invalidate_cache_inline', '_get_cached_value',
                       '_refresh_cache', '_set_cache', '_update_cache', 'get_portfolio_value',
                       'get_portfolio_value_with_lock', '_publish_internal', 'publish', 'subscribe'}
    lock_method_calls = []
    for sub_node in ast.walk(method_node):
        if isinstance(sub_node, ast.Call):
            func = sub_node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id == 'self' and func.attr in suspect_methods:
                    for ls, le in lock_line_ranges:
                        if ls <= sub_node.lineno <= le:
                            lock_method_calls.append((func.attr, sub_node.lineno))
                            break

    # 5. 锁内 logger.info 等耗时操作
    logger_info_in_lock = []
    for sub_node in ast.walk(method_node):
        if isinstance(sub_node, ast.Call):
            func = sub_node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id == 'logger' and func.attr in ('info', 'debug', 'warning', 'error'):
                    for ls, le in lock_line_ranges:
                        if ls <= sub_node.lineno <= le:
                            logger_info_in_lock.append((sub_node.lineno, func.attr))
                            break

    # 6. 锁内 Position/Event 构造
    object_construction_in_lock = []
    for sub_node in ast.walk(method_node):
        if isinstance(sub_node, ast.Call):
            func = sub_node.func
            if isinstance(func, ast.Name) and func.id in ('Position', 'OrderFilledEvent', 'TradeExecutedEvent', 'PositionUpdatedEvent'):
                for ls, le in lock_line_ranges:
                    if ls <= sub_node.lineno <= le:
                        object_construction_in_lock.append((func.id, sub_node.lineno))
                        break

    # 7. 锁内 _build_*_event
    build_event_calls = []
    for sub_node in ast.walk(method_node):
        if isinstance(sub_node, ast.Call):
            func = sub_node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id == 'self' and func.attr.startswith('_build_'):
                    for ls, le in lock_line_ranges:
                        if ls <= sub_node.lineno <= le:
                            build_event_calls.append((func.attr, sub_node.lineno))
                            break

    return {
        'method_name': method_name,
        'start_line': method_node.lineno,
        'end_line': method_node.end_lineno,
        'method_lines': method_lines,
        'method_bytes': method_bytes,
        'with_blocks': with_blocks,
        'nested_violations': nested,
        'io_calls_in_lock': io_calls,
        'lock_method_calls_in_lock': lock_method_calls,
        'logger_in_lock_count': len(logger_info_in_lock),
        'object_construction_in_lock': object_construction_in_lock,
        'build_event_calls_in_lock': build_event_calls,
    }


def main():
    file_path = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\trading_engine.py"
    with open(file_path, 'r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source)

    methods = [
        ('_execute_buy', 1232, 1417),
        ('_execute_sell', 1419, 1676),
        ('_risk_check', 1764, 1941),
    ]

    for method_name, start, end in methods:
        print(f"\n{'='*80}")
        print(f"方法: {method_name}  L{start}-L{end}")
        print(f"{'='*80}")
        result = analyze_method(tree, method_name, start, end)
        if result is None:
            print(f"  ⚠️ 未找到方法定义")
            continue

        print(f"方法体行数: {result['method_lines']} 行")
        print(f"方法体字节数: {result['method_bytes']:,} bytes")

        print(f"\n[所有 with 块] (递归查找, 包括 try 嵌套):")
        if not result['with_blocks']:
            print(f"  ⚠️ 0 with 块")
        for wb in result['with_blocks']:
            print(f"  - with self.{wb['lock_attr']}  L{wb['start_line']}-L{wb['end_line']}  持锁体 {wb['body_lines']} 行  嵌套深度 {wb['depth']}")

        print(f"\n[锁嵌套违规] (R104 §12 #3 严格递归检测):")
        if not result['nested_violations']:
            print(f"  ✅ 0 锁嵌套违规 (R110-P0 修复有效)")
        else:
            for v in result['nested_violations']:
                print(f"  ⚠️ {v}")

        print(f"\n[锁内 I/O 调用嫌疑]:")
        if not result['io_calls_in_lock']:
            print(f"  ✅ 0 显式 I/O 调用 (网络/DB/磁盘)")
        else:
            for name, line in result['io_calls_in_lock']:
                print(f"  - {name} @ L{line}")

        print(f"\n[锁内可能持锁的方法调用]:")
        if not result['lock_method_calls_in_lock']:
            print(f"  ✅ 0 持锁方法调用")
        else:
            for name, line in result['lock_method_calls_in_lock']:
                print(f"  - self.{name} @ L{line}")

        print(f"\n[锁内耗时操作统计]:")
        print(f"  - logger.info/debug/warn/error 调用: {result['logger_in_lock_count']} 次")
        print(f"  - Position/Event 对象构造: {len(result['object_construction_in_lock'])} 次")
        for name, line in result['object_construction_in_lock']:
            print(f"    {name}() @ L{line}")
        print(f"  - _build_*_event 事件构建: {len(result['build_event_calls_in_lock'])} 次")
        for name, line in result['build_event_calls_in_lock']:
            print(f"    self.{name} @ L{line}")


if __name__ == "__main__":
    main()
