"""
R147 子智能体 B - 持锁 IO/网络/磁盘/序列化检测工具 v1
- 递归 with.body 内是否有 pickle.dumps / publish / file IO / network IO
"""
import ast
import sys
from pathlib import Path

IO_FUNCTIONS = {
    # 序列化
    'pickle': {'dumps', 'loads', 'dump', 'load'},
    'json': {'dumps', 'loads', 'dump', 'load'},
    # 文件 IO
    'open': None,
    'Path': {'read_text', 'write_text', 'read_bytes', 'write_bytes', 'unlink', 'mkdir', 'rmdir'},
    'shutil': {'copy', 'copy2', 'copytree', 'rmtree', 'move'},
    'os': {'remove', 'unlink', 'mkdir', 'rmdir', 'rename', 'replace'},
    # 网络
    'socket': None,
    'requests': {'get', 'post', 'put', 'delete', 'patch', 'request'},
    'urllib': set(),
    'httpx': {'get', 'post', 'put', 'delete', 'patch'},
    'aiohttp': {'get', 'post', 'put', 'delete', 'patch'},
    # DB
    'cursor': {'execute', 'executemany', 'fetchall', 'fetchone', 'fetchmany'},
    'connect': None,
}


def find_lock_with_blocks(node, target_lock_names, results):
    """递归查找所有 with self._xxx_lock: 块"""
    if isinstance(node, ast.With):
        for item in node.items:
            ctx = item.context_expr
            if (isinstance(ctx, ast.Attribute) and
                isinstance(ctx.value, ast.Name) and
                ctx.value.id == "self" and
                ctx.attr in target_lock_names):
                # 找到锁块, 检查其 body 内是否有 IO 调用
                for sub_stmt in node.body:
                    check_io_in_stmt(sub_stmt, ctx.attr, node.lineno, results)
        # 继续递归 body
        for sub_stmt in node.body:
            find_lock_with_blocks(sub_stmt, target_lock_names, results)
    elif isinstance(node, (ast.If, ast.For, ast.While, ast.Try)):
        for sub_stmt in node.body:
            find_lock_with_blocks(sub_stmt, target_lock_names, results)
    elif hasattr(node, 'body') and isinstance(node.body, list):
        for sub_stmt in node.body:
            find_lock_with_blocks(sub_stmt, target_lock_names, results)


def check_io_in_stmt(stmt, lock_name, lock_line, results):
    """检查一个语句中是否有 IO 调用"""
    for node in ast.walk(stmt):
        if isinstance(node, ast.Call):
            func = node.func
            # 处理 attribute chain: a.b.c.method()
            attr_chain = []
            cur = func
            while isinstance(cur, ast.Attribute):
                attr_chain.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                attr_chain.append(cur.id)
            attr_chain.reverse()

            # 匹配 IO 函数
            if not attr_chain:
                continue
            first = attr_chain[0]
            if first not in IO_FUNCTIONS:
                # 也检查 publish 等
                if any(kw in ('publish', 'send', 'recv', 'read', 'write') for kw in attr_chain):
                    results.append({
                        'lock': lock_name,
                        'lock_line': lock_line,
                        'call_line': node.lineno,
                        'call_chain': '.'.join(attr_chain),
                    })
                continue

            valid_attrs = IO_FUNCTIONS[first]
            if valid_attrs is None:
                # 整个类都被标记
                results.append({
                    'lock': lock_name,
                    'lock_line': lock_line,
                    'call_line': node.lineno,
                    'call_chain': '.'.join(attr_chain),
                })
            else:
                # 检查最后的方法名
                if len(attr_chain) >= 2 and attr_chain[-1] in valid_attrs:
                    results.append({
                        'lock': lock_name,
                        'lock_line': lock_line,
                        'call_line': node.lineno,
                        'call_chain': '.'.join(attr_chain),
                    })


def scan_file(filepath, target_lock_names):
    """扫描文件, 返回持锁 IO 违规清单"""
    src = Path(filepath).read_text(encoding='utf-8')
    tree = ast.parse(src)

    results = []
    # 顶层扫描
    for node in tree.body:
        find_lock_with_blocks(node, target_lock_names, results)

    # 嵌套类
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                find_lock_with_blocks(item, target_lock_names, results)

    return results


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python _r147_b_lock_io.py <file> <lock1,lock2,...>")
        sys.exit(1)

    fp = sys.argv[1]
    lock_names = set(sys.argv[2].split(','))
    results = scan_file(fp, lock_names)
    print(f"\n=== R147 持锁 IO/网络/磁盘/序列化扫描 v1 ===")
    print(f"File: {fp}")
    print(f"Locks: {lock_names}")
    print(f"Violations: {len(results)}")
    for r in results:
        print(f"  [{r['lock']}] L{r['lock_line']} -> L{r['call_line']}: {r['call_chain']}")
