"""R180 C 子智能体: 死代码/孤儿事件审计 (R6 §6.1 8 铁律 + R6 §6.2 2 铁律)

R84 教训: 32 个孤儿发布 / 13 个孤儿订阅
复用 R84 模式 (grep publish - grep subscribe 差集)
"""
import ast
import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple


def extract_event_strings(filepath: str, method_name: str) -> Set[str]:
    """从文件中提取指定方法调用的字符串字面量"""
    source = Path(filepath).read_text(encoding='utf-8')
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    results = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == method_name:
                if node.args and isinstance(node.args[0], ast.Constant):
                    results.add(node.args[0].value)
    return results


def scan_pubsub_orphan(core_dir: str = 'core') -> Tuple[Set[str], Set[str]]:
    """
    扫描全项目 publish - subscribe 差集
    返回: (orphan_publish, orphan_subscribe)
    """
    all_publish = {}  # event_str -> [file:lineno]
    all_subscribe = {}  # event_str -> [file:lineno]

    for root, dirs, files in os.walk(core_dir):
        if any(x in root for x in ['__pycache__', '.git', 'node_modules']):
            continue
        for f in files:
            if not f.endswith('.py'):
                continue
            path = os.path.join(root, f)
            try:
                pub_set = extract_event_strings(path, 'publish')
                sub_set = extract_event_strings(path, 'subscribe')
                for ev in pub_set:
                    all_publish.setdefault(ev, []).append(path)
                for ev in sub_set:
                    all_subscribe.setdefault(ev, []).append(path)
            except Exception:
                continue

    orphan_pub = set(all_publish.keys()) - set(all_subscribe.keys())
    orphan_sub = set(all_subscribe.keys()) - set(all_publish.keys())

    return orphan_pub, orphan_sub, all_publish, all_subscribe


def scan_dead_functions(core_dir: str = 'core') -> List[Dict]:
    """
    扫描死代码: 跨子目录零调用的函数/类
    R6 §6.1 铁律: 永远不 仅看字符串匹配判定死代码
    """
    # 1. 收集所有定义
    definitions = {}  # (file, name) -> {'type': 'class'|'def', 'lineno': int}
    for root, dirs, files in os.walk(core_dir):
        if any(x in root for x in ['__pycache__', '.git']):
            continue
        for f in files:
            if not f.endswith('.py'):
                continue
            path = os.path.join(root, f)
            try:
                source = Path(path).read_text(encoding='utf-8')
                tree = ast.parse(source)
            except (SyntaxError, Exception):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    definitions.setdefault(node.name, []).append({
                        'file': path,
                        'type': 'class',
                        'lineno': node.lineno,
                    })
                elif isinstance(node, ast.FunctionDef):
                    if not node.name.startswith('_'):
                        continue  # 只看公共函数
                    definitions.setdefault(node.name, []).append({
                        'file': path,
                        'type': 'def',
                        'lineno': node.lineno,
                    })

    # 2. 跨子目录搜索调用
    dead_candidates = []
    for name, defs in definitions.items():
        if not defs:
            continue
        # 跳过常见 Python 魔术方法
        if name in ('__init__', '__str__', '__repr__', '__new__', '__del__',
                   '__enter__', '__exit__', '__call__', '__iter__', '__next__',
                   '__len__', '__getitem__', '__setitem__', '__getattr__',
                   '__setattr__', '__contains__', '__hash__', '__eq__', '__ne__',
                   '__lt__', '__gt__', '__le__', '__ge__', '__bool__', '__add__'):
            continue
        # 简单 Grep 检测 (R6 §6.1 #1: 永远不 仅看字符串)
        call_count = 0
        for root, dirs, files in os.walk(core_dir):
            if any(x in root for x in ['__pycache__', '.git']):
                continue
            for f in files:
                if not f.endswith('.py'):
                    continue
                path = os.path.join(root, f)
                try:
                    content = Path(path).read_text(encoding='utf-8')
                except Exception:
                    continue
                # 排除定义本身
                if any(d['file'] == path for d in defs):
                    # 在定义文件查找时, 减去定义行
                    lines = content.split('\n')
                    for line in lines:
                        if name in line and 'def ' not in line and 'class ' not in line:
                            call_count += 1
                else:
                    if name in content:
                        call_count += content.count(name)
        if call_count < 2:  # 至少 2 次引用 (1 定义 + 1 调用)
            for d in defs:
                dead_candidates.append({
                    'name': name,
                    'file': d['file'],
                    'type': d['type'],
                    'lineno': d['lineno'],
                    'call_count': call_count,
                })
    return dead_candidates


def main():
    print("=" * 100)
    print("R180 C 子智能体: 死代码/孤儿事件审计 (R6 §6.1 8 铁律 + R6 §6.2 2 铁律)")
    print("=" * 100)

    print("\n=== R84 教训复用: publish - subscribe 差集审计 ===")
    orphan_pub, orphan_sub, all_pub, all_sub = scan_pubsub_orphan('core')

    print(f"\n全项目 publish 事件数: {len(all_pub)}")
    print(f"全项目 subscribe 事件数: {len(all_sub)}")

    print(f"\n孤儿发布 (ORPHAN_PUB, 有 publish 无 subscribe): {len(orphan_pub)}")
    for ev in sorted(orphan_pub)[:20]:
        print(f"  - {ev}")
    if len(orphan_pub) > 20:
        print(f"  ... 还有 {len(orphan_pub) - 20} 个")

    print(f"\n孤儿订阅 (ORPHAN_SUB, 有 subscribe 无 publish): {len(orphan_sub)}")
    for ev in sorted(orphan_sub)[:20]:
        print(f"  - {ev}")
    if len(orphan_sub) > 20:
        print(f"  ... 还有 {len(orphan_sub) - 20} 个")

    print("\n=== 死代码扫描 (低调用数, R6 §6.1 8 铁律注意: 仅供参考, 物理删除前需 4 源验证) ===")
    dead = scan_dead_functions('core')
    print(f"\n可疑死代码候选 (call_count < 2): {len(dead)}")
    # 按文件分组
    by_file = {}
    for d in dead:
        by_file.setdefault(d['file'], []).append(d)
    for f, defs in sorted(by_file.items())[:5]:
        print(f"\n  {f}:")
        for d in defs[:10]:
            print(f"    L{d['lineno']:>5} [{d['type']}] {d['name']} (call_count={d['call_count']})")


if __name__ == '__main__':
    main()
