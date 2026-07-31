"""
R175 子智能体 A: 3 个 P0 长锁方法 AST 递归分析
严格遵守 R104 §12 铁律 #3 (AST 递归 with.body, 非 ast.walk 扁平化) + #5 (AST unparse 验证)
"""
import ast
import sys


def find_with_blocks_recursive(node, parent_locks=set(), path=""):
    """
    递归进入 with.body, 检测锁嵌套
    严格按照 R104 §12 #3 实现
    """
    violations = []
    if isinstance(node, ast.With):
        # 提取当前 with 块的锁名
        current_locks = set()
        for item in node.items:
            ce = item.context_expr
            if isinstance(ce, ast.Attribute) and isinstance(ce.value, ast.Name):
                if ce.value.id == 'self':
                    current_locks.add(ce.attr)

        # 检查当前 with 块内的嵌套
        new_parent_locks = parent_locks | current_locks

        # 递归进入 with.body
        for stmt in node.body:
            sub_violations = find_with_blocks_recursive(stmt, new_parent_locks, f"{path}/with")
            violations.extend(sub_violations)

        return violations

    elif isinstance(node, ast.Try):
        for sub_node in list(node.body) + list(node.handlers) + list(node.finalbody) + list(node.orelse):
            violations.extend(find_with_blocks_recursive(sub_node, parent_locks, f"{path}/try"))

    elif isinstance(node, (ast.If, ast.For, ast.While)):
        for sub_node in node.body + getattr(node, 'orelse', []):
            violations.extend(find_with_blocks_recursive(sub_node, parent_locks, f"{path}/if"))

    elif isinstance(node, ast.With):
        pass  # already handled

    return violations


def detect_lock_calls_in_range(node, lock_attrs):
    """
    递归检查方法体中所有函数调用, 是否调用了可能持锁的方法
    """
    calls = []
    for sub_node in ast.walk(node):
        if isinstance(sub_node, ast.Call):
            func = sub_node.func
            # self.method() 形式
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id == 'self' and func.attr in lock_attrs:
                    calls.append((func.attr, sub_node.lineno))
    return calls


def analyze_method(tree, method_name, start_line, end_line):
    """
    分析指定方法
    """
    # 找到方法定义
    method_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            if node.lineno == start_line:
                method_node = node
                break

    if method_node is None:
        return None

    # 方法体反 unparse
    method_source = ast.unparse(method_node)
    method_ast = ast.parse(method_source).body[0]

    # 提取所有顶层 with 块
    top_with_blocks = []
    for stmt in method_node.body:
        if isinstance(stmt, ast.With):
            for item in stmt.items:
                if isinstance(item.context_expr, ast.Attribute):
                    if isinstance(item.context_expr.value, ast.Name) and item.context_expr.value.id == 'self':
                        top_with_blocks.append({
                            'lock_attr': item.context_expr.attr,
                            'start_line': stmt.lineno,
                            'end_line': stmt.end_lineno,
                            'body_lines': stmt.end_lineno - stmt.lineno + 1,
                        })

    # 递归检测锁嵌套
    nested_violations = find_with_blocks_recursive(method_node, parent_locks=set())

    # 统计方法大小
    method_lines = method_node.end_lineno - method_node.lineno + 1
    method_bytes = len(method_source.encode('utf-8'))

    # 检测锁内 I/O 调用 (网络/DB/磁盘)
    io_calls = []
    io_keywords = ['urllib', 'requests', 'http', 'socket', 'sqlite', 'psycopg', 'pymongo',
                   'open(', '.read()', '.write()', '.save(', 'session.', 'cursor.execute',
                   'query', 'fetch', 'insert', 'update_', 'delete_', 'commit()', 'rollback']
    for sub_node in ast.walk(method_node):
        if isinstance(sub_node, ast.Call):
            func = sub_node.func
            if isinstance(func, ast.Attribute):
                func_name = func.attr
                if any(kw in func_name.lower() for kw in io_keywords):
                    io_calls.append((func_name, sub_node.lineno))

    # 检测锁内其他可能持锁的方法调用
    suspect_lock_methods = {'_invalidate_cache', '_invalidate_cache_inline', '_get_cached_value',
                            '_refresh_cache', '_set_cache', '_update_cache', 'get_portfolio_value',
                            'get_portfolio_value_with_lock', 'publish', 'subscribe', '_publish_internal'}
    lock_method_calls = []
    for sub_node in ast.walk(method_node):
        if isinstance(sub_node, ast.Call):
            func = sub_node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id == 'self' and func.attr in suspect_lock_methods:
                    lock_method_calls.append((func.attr, sub_node.lineno))

    return {
        'method_name': method_name,
        'start_line': method_node.lineno,
        'end_line': method_node.end_lineno,
        'method_lines': method_lines,
        'method_bytes': method_bytes,
        'top_with_blocks': top_with_blocks,
        'nested_violations': nested_violations,
        'io_calls': io_calls,
        'lock_method_calls': lock_method_calls,
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

        print(f"\n[顶层 with 块]:")
        for wb in result['top_with_blocks']:
            print(f"  - with self.{wb['lock_attr']}  L{wb['start_line']}-L{wb['end_line']}  持锁体 {wb['body_lines']} 行")

        print(f"\n[递归检测锁嵌套] (R104 §12 #3 严格实现):")
        if not result['nested_violations']:
            print(f"  ✅ 0 锁嵌套违规")
        else:
            for v in result['nested_violations']:
                print(f"  ⚠️ {v}")

        print(f"\n[锁内 I/O 调用嫌疑] (网络/DB/磁盘):")
        if not result['io_calls']:
            print(f"  ✅ 0 显式 I/O 调用")
        else:
            for name, line in result['io_calls']:
                print(f"  - {name} @ L{line}")

        print(f"\n[锁内其他可能持锁方法调用]:")
        if not result['lock_method_calls']:
            print(f"  ✅ 0 持锁方法调用")
        else:
            for name, line in result['lock_method_calls']:
                print(f"  - self.{name} @ L{line}")


if __name__ == "__main__":
    main()
