#!/usr/bin/env python3
"""R182 A 子智能体 - 跨容器自解析精细化扫描器 (R51 教训 P0)

R51 教训类型 (P0 严重):
- `service_container = ServiceContainer()` 临时实例化 (与全局脱钩)
- `_container = ServiceContainer()` 临时实例化

合法模式 (不应标记违规):
- `get_service_container()` 全局单例访问 (R84 后的标准)
- `set_service_container()` 注册全局容器
- 文档/注释中提及
"""
import ast
import re
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict


SCAN_DIRS = ['core', 'gui', 'web', 'tests', 'scripts', 'plugins', 'backtest', 'optimization', 'utils']
SKIP_DIRS = {'__pycache__', '.git', '.pytest_cache', '.cache', 'node_modules', '.serena', '.mypy_cache', '.codegraph'}


def collect_python_files(root: str = '.') -> List[str]:
    """收集所有 Python 文件"""
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
    # 添加 main.py
    if os.path.exists('main.py'):
        py_files.append('main.py')
    return py_files


def is_docstring_line(source_lines, line_idx):
    """检查该行是否是 docstring 的一部分"""
    # 简化的 docstring 检测
    if line_idx < 0 or line_idx >= len(source_lines):
        return False
    line = source_lines[line_idx].strip()
    # 行内 docstring 标志
    return False


def find_service_container_temp_instantiation(filepath: str) -> List[Dict]:
    """真正的 P0 违规: 临时实例化 ServiceContainer (与全局脱钩)"""
    try:
        source = Path(filepath).read_text(encoding='utf-8')
    except (UnicodeDecodeError, FileNotFoundError):
        return []
    results = []
    lines = source.split('\n')
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        # 模式 1: service_container = ServiceContainer() / _container = ServiceContainer()
        # 模式 2: container = ServiceContainer() (单变量)
        # 模式 3: 在函数内 self.service_container = ServiceContainer() 临时实例
        if re.search(r'\b(\w*container\w*)\s*=\s*ServiceContainer\s*\(', line):
            # 排除合法模式
            if 'get_service_container' in line or 'set_service_container' in line:
                continue
            if 'class ServiceContainer' in line:
                continue
            # 排除 type annotation / 返回值
            if re.search(r'->\s*ServiceContainer', line):
                continue
            if re.search(r':\s*ServiceContainer\s*=', line):
                continue
            # 排除 isinstance 检查
            if 'isinstance' in line:
                continue
            # 排除 raise / assert
            if re.match(r'\s*(raise|assert)', stripped):
                continue
            results.append({
                'lineno': i,
                'pattern': 'temp ServiceContainer instantiation',
                'line': stripped[:150],
                'file': filepath,
            })
        # 模式 4: EnhancedServiceContainer() / UnifiedServiceContainer() 临时实例
        for cls_name in ('EnhancedServiceContainer', 'UnifiedServiceContainer', 'ServiceRegistry'):
            m = re.search(rf'\b(\w*container\w*)\s*=\s*{cls_name}\s*\(', line)
            if m:
                if 'isinstance' in line or 'class ' in line or 'return ' in line:
                    continue
                results.append({
                    'lineno': i,
                    'pattern': f'temp {cls_name} instantiation',
                    'line': stripped[:150],
                    'file': filepath,
                })
    return results


def find_unified_network_service_pattern(filepath: str) -> List[Dict]:
    """扫描 unified_network_service.py:20-23 类似的临时容器自解析"""
    try:
        source = Path(filepath).read_text(encoding='utf-8')
    except (UnicodeDecodeError, FileNotFoundError):
        return []
    results = []
    lines = source.split('\n')
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        # 模式: 自构造一个 ServiceContainer 然后 .get() 服务
        # 例如: container = ServiceContainer(); svc = container.get(X)
        # 但需要先识别
        if re.search(r'\bcontainer\s*=\s*ServiceContainer\s*\(', line):
            # 后续 10 行内是否有 .get( 调用
            for j in range(i, min(i + 10, len(lines))):
                next_line = lines[j] if j < len(lines) else ''
                if re.search(r'\.get\s*\(', next_line) or re.search(r'\.resolve\s*\(', next_line):
                    results.append({
                        'lineno': i,
                        'pattern': 'temp container + get/resolve pattern',
                        'line': stripped[:150],
                        'file': filepath,
                        'context': next_line.strip()[:80],
                    })
                    break
    return results


def main():
    py_files = collect_python_files()
    print(f"扫描 Python 文件数: {len(py_files)}")

    all_temp_instantiations = []
    all_unified_patterns = []
    for filepath in py_files:
        temps = find_service_container_temp_instantiation(filepath)
        unifieds = find_unified_network_service_pattern(filepath)
        all_temp_instantiations.extend(temps)
        all_unified_patterns.extend(unifieds)

    print(f"\n=== 真正的 P0 跨容器自解析 (临时 ServiceContainer 实例化) ===")
    print(f"总数: {len(all_temp_instantiations)}")
    # 按文件分组
    file_groups = defaultdict(list)
    for r in all_temp_instantiations:
        file_groups[r['file']].append(r)
    for fpath, items in sorted(file_groups.items(), key=lambda x: -len(x[1]))[:30]:
        print(f"  [{len(items)} 处] {fpath}")
        for r in items[:3]:
            print(f"    L{r['lineno']:>5} [{r['pattern']}] {r['line']}")

    print(f"\n=== unified_network_service 类型: 临时容器 + get/resolve 模式 ===")
    print(f"总数: {len(all_unified_patterns)}")
    for r in all_unified_patterns[:20]:
        print(f"  L{r['lineno']:>5} {r['file']}")
        print(f"         {r['line']}")
        print(f"         后续: {r.get('context', '')}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
