"""R180 C 子智能体: 5 类高价值 HVD 全项目扫描器

扫描目标:
a) 长锁方法 (>30 行持锁) - P0
b) 6 维度缺字段的 cache_key - P0
c) 死代码/孤儿 publish-subscribe - P1
d) 跨容器自解析 - R51 教训 P0
e) logger.error 缺 exc_info=True - R51 铁律 #5 P0
"""
import ast
import re
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


def find_long_locks(filepath: str, min_lines: int = 30) -> List[Dict]:
    """扫描长锁方法 - P0 候选"""
    source = Path(filepath).read_text(encoding='utf-8')
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    results = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_name = node.name
            # 查找方法内所有 with 块
            for sub in ast.walk(node):
                if isinstance(sub, ast.With):
                    # 估算 with 块行数
                    if hasattr(sub, 'end_lineno') and sub.end_lineno:
                        block_lines = sub.end_lineno - sub.lineno
                        if block_lines >= min_lines:
                            # 提取锁名
                            lock_names = []
                            for item in sub.items:
                                ctx = item.context_expr
                                if isinstance(ctx, ast.Attribute):
                                    if isinstance(ctx.value, ast.Name) and ctx.value.id == 'self':
                                        lock_names.append(f'self.{ctx.attr}')
                            results.append({
                                'lineno': sub.lineno,
                                'end_lineno': sub.end_lineno,
                                'block_lines': block_lines,
                                'method': method_name,
                                'locks': lock_names,
                            })
    return results


def find_cache_keys_with_missing_dims(filepath: str) -> List[Dict]:
    """扫描硬编码 cache_key 缺维度的位置 - P0 候选"""
    source = Path(filepath).read_text(encoding='utf-8')
    results = []

    # 匹配 cache_key = f"..." 模式
    pattern = re.compile(r'cache_key\s*=\s*(?:f?)["\']([^"\']+)["\']')
    for i, line in enumerate(source.split('\n'), 1):
        match = pattern.search(line)
        if not match:
            continue
        key_str = match.group(1)
        # 6 维度: at, sc, p, c, adj, ds
        # 检查维度关键词
        required_dims = ['at=', '_at', 'asset_type',
                        'sc=', '_sc', 'symbol', 'code',
                        'p=', '_p', 'period',
                        'c=', '_c', 'count',
                        'adj=', '_adj', 'adjust',
                        'ds=', '_ds', 'data_source', 'provider']
        found_dims = sum(1 for d in required_dims if d in key_str)
        # 至少 3 维度才合规
        if found_dims < 3 and len(key_str) > 10:
            results.append({
                'lineno': i,
                'key_str': key_str,
                'found_dims': found_dims,
            })
    return results


def find_publish_calls(filepath: str) -> Set[str]:
    """提取所有 publish() 调用的字符串"""
    source = Path(filepath).read_text(encoding='utf-8')
    results = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return results

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'publish':
                if node.args and isinstance(node.args[0], ast.Constant):
                    results.add(node.args[0].value)
    return results


def find_subscribe_calls(filepath: str) -> Set[str]:
    """提取所有 subscribe() 调用的字符串"""
    source = Path(filepath).read_text(encoding='utf-8')
    results = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return results

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in ('subscribe', 'subscribe_topic'):
                if node.args and isinstance(node.args[0], ast.Constant):
                    results.add(node.args[0].value)
    return results


def find_service_container_self_parse(filepath: str) -> List[Dict]:
    """扫描跨容器自解析 - R51 教训 P0"""
    source = Path(filepath).read_text(encoding='utf-8')
    results = []

    lines = source.split('\n')
    for i, line in enumerate(lines, 1):
        # 匹配 service_container = ServiceContainer() 模式
        if re.search(r'service_container\s*=\s*ServiceContainer\s*\(', line):
            results.append({
                'lineno': i,
                'pattern': 'self-construct ServiceContainer',
                'line': line.strip()[:100],
            })
        # 匹配 _container = ServiceContainer() 模式
        if re.search(r'_container\s*=\s*ServiceContainer\s*\(', line):
            results.append({
                'lineno': i,
                'pattern': 'self-construct _container',
                'line': line.strip()[:100],
            })
    return results


def find_logger_exceptions_without_exc_info(filepath: str) -> List[Dict]:
    """扫描 logger.error/warning/critical 缺 exc_info=True - R51 #5 P0"""
    source = Path(filepath).read_text(encoding='utf-8')
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    # 重建父节点映射
    parent_map = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent_map[id(child)] = node

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Attribute):
                continue
            if not (isinstance(node.func.value, ast.Name) and node.func.value.id == 'logger'):
                continue
            if node.func.attr not in ('error', 'warning', 'critical'):
                continue
            # 找到 ExceptHandler 父节点
            current = parent_map.get(id(node))
            in_except = False
            while current is not None:
                if isinstance(current, ast.ExceptHandler):
                    in_except = True
                    break
                current = parent_map.get(id(current))
            if not in_except:
                continue
            # 检查 exc_info
            has_exc_info = False
            for kw in node.keywords:
                if kw.arg == 'exc_info':
                    if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        has_exc_info = True
            if not has_exc_info:
                line_text = source.split('\n')[node.lineno - 1].strip() if node.lineno <= len(source.split('\n')) else ''
                violations.append({
                    'lineno': node.lineno,
                    'func_name': node.func.attr,
                    'line': line_text[:100],
                })
    return violations


def main():
    target_files = [
        'core/trading_engine.py',
        'core/events/event_bus.py',
        'core/services/service_bootstrap.py',
        'core/services/unified_data_manager.py',
        'core/risk_rule_manager.py',
    ]

    print("=" * 100)
    print("R180 5 类高价值 HVD 全项目扫描器")
    print("a) 长锁方法 (>30 行) b) cache_key 缺维度 c) 死代码/孤儿事件")
    print("d) 跨容器自解析 e) logger.error 缺 exc_info=True")
    print("=" * 100)

    all_long_locks = []
    all_cache_keys = []
    all_container_self = []
    all_exc_violations = []

    for filepath in target_files:
        if not Path(filepath).exists():
            continue

        long_locks = find_long_locks(filepath, min_lines=30)
        cache_keys = find_cache_keys_with_missing_dims(filepath)
        container_self = find_service_container_self_parse(filepath)
        exc_violations = find_logger_exceptions_without_exc_info(filepath)

        for ll in long_locks:
            ll['file'] = filepath
            all_long_locks.append(ll)
        for ck in cache_keys:
            ck['file'] = filepath
            all_cache_keys.append(ck)
        for cs in container_self:
            cs['file'] = filepath
            all_container_self.append(cs)
        for ev in exc_violations:
            ev['file'] = filepath
            all_exc_violations.append(ev)

    print(f"\n=== a) 长锁方法 (>30 行) - P0 ===")
    print(f"总数: {len(all_long_locks)}")
    for ll in all_long_locks[:20]:
        print(f"  L{ll['lineno']:>5}-{ll['end_lineno']:<5} ({ll['block_lines']:>3} 行) {ll['file']}")
        print(f"         方法: {ll['method']}, 锁: {ll['locks']}")

    print(f"\n=== b) cache_key 缺维度 (3 维度以下) - P0 ===")
    print(f"总数: {len(all_cache_keys)}")
    for ck in all_cache_keys[:20]:
        print(f"  L{ck['lineno']:>5} {ck['file']}")
        print(f"         key: {ck['key_str'][:80]}")
        print(f"         found_dims: {ck['found_dims']}")

    print(f"\n=== d) 跨容器自解析 (R51 教训) - P0 ===")
    print(f"总数: {len(all_container_self)}")
    for cs in all_container_self:
        print(f"  L{cs['lineno']:>5} {cs['file']}")
        print(f"         {cs['line']}")

    print(f"\n=== e) logger 缺 exc_info=True (R51 #5) - P0 ===")
    print(f"总数: {len(all_exc_violations)}")
    for ev in all_exc_violations[:30]:
        print(f"  L{ev['lineno']:>5} [{ev['func_name']}] {ev['file']}")
        print(f"         {ev['line'][:80]}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
