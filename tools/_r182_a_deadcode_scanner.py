#!/usr/bin/env python3
"""R182 A 子智能体 - 死代码候选精准扫描器

扫描目标:
- 公共方法 (无下划线开头) + 静态方法 + 公开类
- 跨 4 子目录 (core/gui/web/tests) 字符串引用
- 输出 0 业务方候选, 供 HVD 立项
"""
import ast
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict


SCAN_DIRS = ['core', 'gui', 'web', 'tests', 'plugins']
SKIP_DIRS = {'__pycache__', '.git', '.pytest_cache', '.cache', 'node_modules', '.serena', '.mypy_cache', '.codegraph'}


def collect_python_files(root: str = '.') -> List[str]:
    py_files = []
    for scan_dir in SCAN_DIRS:
        if not os.path.exists(scan_dir):
            continue
        for dirpath, dirnames, filenames in os.walk(scan_dir):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for f in filenames:
                if f.endswith('.py'):
                    rel_path = os.path.relpath(os.path.join(dirpath, f), '.')
                    py_files.append(rel_path)
    return py_files


def get_class_methods(filepath: str) -> List[Dict]:
    """提取所有公开方法 (无下划线开头, 非继承自 object)"""
    try:
        source = Path(filepath).read_text(encoding='utf-8')
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
        return []
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            if class_name.startswith('_') and class_name not in ('__init__',):
                continue
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_name = item.name
                    # 排除私有方法 / dunder / 测试辅助
                    if method_name.startswith('_') and method_name not in ('__init__', '__call__'):
                        continue
                    if method_name in ('__init__', '__call__', '__enter__', '__exit__', '__str__', '__repr__'):
                        continue
                    results.append({
                        'file': filepath,
                        'class': class_name,
                        'method': method_name,
                        'qualname': f'{class_name}.{method_name}',
                        'lineno': item.lineno,
                    })
    return results


def main():
    py_files = collect_python_files()
    print(f"扫描 Python 文件数: {len(py_files)}")

    all_methods = []
    for filepath in py_files:
        methods = get_class_methods(filepath)
        all_methods.extend(methods)

    print(f"公开方法总数: {len(all_methods)}")

    # 跨子目录搜索 (粗略)
    method_references = defaultdict(set)
    for filepath in py_files:
        try:
            source = Path(filepath).read_text(encoding='utf-8')
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for m in all_methods:
            qualname = m['qualname']
            method_name = m['method']
            class_name = m['class']
            if filepath == m['file']:
                # 自身文件 1 次 (定义)
                continue
            # 简单字符串匹配
            count = source.count(qualname) + source.count(method_name)
            if count >= 2:  # 排除偶然出现
                method_references[qualname].add(filepath)

    # 找 0 引用候选
    dead_candidates = []
    for m in all_methods:
        qualname = m['qualname']
        if qualname not in method_references:
            # 进一步检查: 类名是否被引用
            dead_candidates.append(m)

    print(f"\n=== 0 业务引用候选 (公开方法 + 0 跨文件引用) ===")
    print(f"候选数: {len(dead_candidates)}")

    # 按文件分组
    file_groups = defaultdict(list)
    for m in dead_candidates:
        file_groups[m['file']].append(m)

    for fpath, methods in sorted(file_groups.items(), key=lambda x: -len(x[1]))[:30]:
        print(f"\n  [{len(methods)} 个候选] {fpath}")
        for m in methods[:5]:
            print(f"    L{m['lineno']:>5} {m['qualname']}")

    # 写 JSON
    import json
    output = {
        'total_methods': len(all_methods),
        'dead_candidates': dead_candidates[:200],
        'file_groups': {f: [{'class': m['class'], 'method': m['method'], 'lineno': m['lineno']} for m in ms] for f, ms in file_groups.items()},
    }
    output_path = 'tests/_r182_a_dead_candidates.json'
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n详细结果: {output_path}")
    except Exception as e:
        print(f"JSON 写入失败: {e}")


if __name__ == '__main__':
    sys.exit(main())
