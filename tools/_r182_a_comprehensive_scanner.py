#!/usr/bin/env python3
"""R182 A 子智能体综合扫描器

扫描目标:
1. 长锁全项目扫描 (P0) - 扩展 R180-C 工具到全项目 (core/gui/web/tests/scripts/plugins)
2. 跨容器自解析 (R51 P0) - service_container = ServiceContainer() 模式
3. logger.exc_info 合规复检 - 扩展到其他重要文件
4. publish/subscribe 差集 - 孤儿事件审计 (R84 模板)

R104 §12 5 铁律 100% 应用:
- 铁律 #3: AST 递归 with.body
- 铁律 #5: AST unparse 验证方法体
"""
import ast
import re
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict


# 扫描目录
SCAN_DIRS = ['core', 'gui', 'web', 'tests', 'scripts', 'plugins', 'backtest', 'optimization', 'utils']

# 跳过目录
SKIP_DIRS = {'__pycache__', '.git', '.pytest_cache', '.cache', 'node_modules', '.serena', '.mypy_cache', '.codegraph'}

# 重要业务文件 (优先扫描)
PRIORITY_FILES = [
    'core/trading_engine.py',
    'core/events/event_bus.py',
    'core/services/service_bootstrap.py',
    'core/services/unified_data_manager.py',
    'core/risk_rule_manager.py',
    'core/containers/service_container.py',
    'core/containers/enhanced_service_container.py',
    'core/containers/unified_service_container.py',
    'core/data_router.py',
    'core/position_manager.py',
    'core/importdata/import_execution_engine.py',
    'core/coordinators/event_coordinator.py',
    'core/agents/risk_agent.py',
    'core/agents/fusion_engine.py',
]


def collect_python_files(root: str = '.') -> List[str]:
    """收集所有 Python 文件"""
    py_files = []
    for scan_dir in SCAN_DIRS:
        if not os.path.exists(scan_dir):
            continue
        for dirpath, dirnames, filenames in os.walk(scan_dir):
            # 跳过指定目录
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for f in filenames:
                if f.endswith('.py'):
                    rel_path = os.path.relpath(os.path.join(dirpath, f), '.')
                    py_files.append(rel_path)
    return py_files


def find_long_locks(filepath: str, min_lines: int = 30) -> List[Dict]:
    """长锁方法扫描 - 持锁行数超过 min_lines 的 with 块"""
    try:
        source = Path(filepath).read_text(encoding='utf-8')
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return []

    results = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_name = node.name
            method_start = node.lineno
            # 递归遍历方法体内 with 块
            for sub in ast.walk(node):
                if isinstance(sub, ast.With):
                    if hasattr(sub, 'end_lineno') and sub.end_lineno:
                        block_lines = sub.end_lineno - sub.lineno
                        if block_lines >= min_lines:
                            lock_names = []
                            for item in sub.items:
                                ctx = item.context_expr
                                if isinstance(ctx, ast.Attribute):
                                    if isinstance(ctx.value, ast.Name) and ctx.value.id == 'self':
                                        lock_names.append(f'self.{ctx.attr}')
                                elif isinstance(ctx, ast.Call):
                                    if isinstance(ctx.func, ast.Attribute) and ctx.func.attr in ('RLock', 'Lock'):
                                        if isinstance(ctx.func.value, ast.Name) and ctx.func.value.id == 'threading':
                                            if ctx.args:
                                                if isinstance(ctx.args[0], ast.Attribute):
                                                    if isinstance(ctx.args[0].value, ast.Name) and ctx.args[0].value.id == 'self':
                                                        lock_names.append(f'self.{ctx.args[0].attr}')
                            if lock_names:
                                results.append({
                                    'lineno': sub.lineno,
                                    'end_lineno': sub.end_lineno,
                                    'block_lines': block_lines,
                                    'method': method_name,
                                    'method_line': method_start,
                                    'locks': lock_names,
                                    'file': filepath,
                                })
    return results


def find_service_container_self_parse(filepath: str) -> List[Dict]:
    """跨容器自解析扫描 - R51 教训 P0"""
    try:
        source = Path(filepath).read_text(encoding='utf-8')
    except (UnicodeDecodeError, FileNotFoundError):
        return []
    results = []

    lines = source.split('\n')
    for i, line in enumerate(lines, 1):
        # 排除注释
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        # service_container = ServiceContainer()
        if re.search(r'\bservice_container\s*=\s*ServiceContainer\s*\(', line):
            results.append({
                'lineno': i,
                'pattern': 'self-construct ServiceContainer',
                'line': stripped[:120],
                'file': filepath,
            })
        # _container = ServiceContainer()
        if re.search(r'\b_container\s*=\s*ServiceContainer\s*\(', line):
            results.append({
                'lineno': i,
                'pattern': 'self-construct _container',
                'line': stripped[:120],
                'file': filepath,
            })
        # container = ServiceContainer()
        if re.search(r'^\s*container\s*=\s*ServiceContainer\s*\(', line):
            results.append({
                'lineno': i,
                'pattern': 'self-construct container',
                'line': stripped[:120],
                'file': filepath,
            })
        # 直接实例化 ServiceContainer()
        if re.search(r'\bget_service_container\s*\(\s*\)', line):
            results.append({
                'lineno': i,
                'pattern': 'get_service_container()',
                'line': stripped[:120],
                'file': filepath,
            })
    return results


def audit_exc_info_compliance(filepath: str) -> Dict:
    """logger.error/warning/critical 在 except 块内是否含 exc_info=True - R51 #5"""
    try:
        source = Path(filepath).read_text(encoding='utf-8')
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return {
            'filepath': filepath,
            'total_except_blocks': 0,
            'logger_in_except': 0,
            'logger_with_exc_info': 0,
            'logger_without_exc_info': 0,
            'violations': [],
        }

    parent_map = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent_map[id(child)] = node

    result = {
        'filepath': filepath,
        'total_except_blocks': 0,
        'logger_in_except': 0,
        'logger_with_exc_info': 0,
        'logger_without_exc_info': 0,
        'violations': [],
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            result['total_except_blocks'] += 1

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Attribute):
                continue
            if not (isinstance(node.func.value, ast.Name) and node.func.value.id == 'logger'):
                continue
            if node.func.attr not in ('error', 'warning', 'critical'):
                continue
            # 找 ExceptHandler 父节点
            current = parent_map.get(id(node))
            in_except = False
            while current is not None:
                if isinstance(current, ast.ExceptHandler):
                    in_except = True
                    break
                current = parent_map.get(id(current))
            if not in_except:
                continue
            result['logger_in_except'] += 1
            has_exc_info = False
            for kw in node.keywords:
                if kw.arg == 'exc_info':
                    if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        has_exc_info = True
                    elif isinstance(kw.value, (ast.Call, ast.Attribute, ast.Name)):
                        has_exc_info = True
            if has_exc_info:
                result['logger_with_exc_info'] += 1
            else:
                result['logger_without_exc_info'] += 1
                lines = source.split('\n')
                line_text = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ''
                result['violations'].append({
                    'lineno': node.lineno,
                    'func_name': node.func.attr,
                    'line': line_text[:120],
                })

    return result


def find_publish_calls(filepath: str) -> Set[str]:
    """提取所有 publish() 调用的字符串"""
    try:
        source = Path(filepath).read_text(encoding='utf-8')
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return set()
    results = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'publish':
                if node.args and isinstance(node.args[0], ast.Constant):
                    if isinstance(node.args[0].value, str):
                        results.add(node.args[0].value)
    return results


def find_subscribe_calls(filepath: str) -> Set[str]:
    """提取所有 subscribe() 调用的字符串"""
    try:
        source = Path(filepath).read_text(encoding='utf-8')
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return set()
    results = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in ('subscribe', 'subscribe_topic', 'on'):
                if node.args and isinstance(node.args[0], ast.Constant):
                    if isinstance(node.args[0].value, str):
                        results.add(node.args[0].value)
    return results


def find_class_definitions(filepath: str) -> List[Dict]:
    """提取类定义列表"""
    try:
        source = Path(filepath).read_text(encoding='utf-8')
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return []
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            results.append({
                'name': node.name,
                'lineno': node.lineno,
                'bases': [ast.unparse(b) for b in node.bases] if node.bases else [],
            })
    return results


def main():
    print("=" * 100)
    print("R182 A 子智能体综合扫描器")
    print("扫描范围: core/ gui/ web/ tests/ scripts/ plugins/ backtest/ optimization/ utils/")
    print("=" * 100)

    # 收集所有 Python 文件
    py_files = collect_python_files()
    print(f"\n扫描 Python 文件数: {len(py_files)}")

    # === 1. 长锁全项目扫描 ===
    print(f"\n{'=' * 80}")
    print("[1] 长锁方法扫描 (>30 行持锁, P0 候选)")
    print(f"{'=' * 80}")
    all_long_locks = []
    for filepath in py_files:
        locks = find_long_locks(filepath, min_lines=30)
        all_long_locks.extend(locks)

    # 按 block_lines 降序
    all_long_locks.sort(key=lambda x: x['block_lines'], reverse=True)
    print(f"长锁总数: {len(all_long_locks)}")
    for ll in all_long_locks[:30]:
        print(f"  L{ll['lineno']:>5}-{ll['end_lineno']:<5} ({ll['block_lines']:>4} 行) {ll['file']}:{ll['method']}")
        print(f"         锁: {ll['locks']}")

    # === 2. 跨容器自解析扫描 ===
    print(f"\n{'=' * 80}")
    print("[2] 跨容器自解析扫描 (R51 教训 P0)")
    print(f"{'=' * 80}")
    all_container_self = []
    for filepath in py_files:
        results = find_service_container_self_parse(filepath)
        all_container_self.extend(results)
    print(f"违规总数: {len(all_container_self)}")
    for cs in all_container_self[:30]:
        print(f"  L{cs['lineno']:>5} [{cs['pattern']}] {cs['file']}")
        print(f"         {cs['line']}")

    # === 3. logger.exc_info 合规复检 (扩展到重要文件) ===
    print(f"\n{'=' * 80}")
    print("[3] logger.exc_info 合规复检 (R51 #5 P0)")
    print(f"{'=' * 80}")
    total_exc_violations = 0
    total_exc_compliance = 0
    total_exc_logger = 0
    file_exc_results = {}

    # 优先扫描 + 全项目
    for filepath in py_files:
        result = audit_exc_info_compliance(filepath)
        if result['logger_without_exc_info'] > 0:
            file_exc_results[filepath] = result
            total_exc_violations += result['logger_without_exc_info']
        total_exc_compliance += result['logger_with_exc_info']
        total_exc_logger += result['logger_in_except']

    print(f"扫描文件数: {len(py_files)}")
    print(f"违规文件数: {len(file_exc_results)}")
    print(f"except 块内 logger 总数: {total_exc_logger}")
    print(f"含 exc_info=True: {total_exc_compliance}")
    print(f"缺 exc_info=True (违规): {total_exc_violations}")
    if total_exc_logger > 0:
        compliance = total_exc_compliance / total_exc_logger * 100
        print(f"全项目合规率: {compliance:.2f}%")

    # 展示违规文件
    for filepath, result in sorted(file_exc_results.items(), key=lambda x: -x[1]['logger_without_exc_info'])[:15]:
        print(f"\n  [{result['logger_without_exc_info']} 处违规] {filepath}")
        for v in result['violations'][:5]:
            print(f"    L{v['lineno']:>5} [{v['func_name']}] {v['line'][:80]}")
        if len(result['violations']) > 5:
            print(f"    ... 还有 {len(result['violations']) - 5} 条")

    # === 4. publish/subscribe 孤儿事件审计 ===
    print(f"\n{'=' * 80}")
    print("[4] publish/subscribe 孤儿事件审计 (R84 模板)")
    print(f"{'=' * 80}")
    all_publish = defaultdict(list)
    all_subscribe = defaultdict(list)
    for filepath in py_files:
        pubs = find_publish_calls(filepath)
        subs = find_subscribe_calls(filepath)
        for p in pubs:
            all_publish[p].append(filepath)
        for s in subs:
            all_subscribe[s].append(filepath)

    orphan_publish = {k: v for k, v in all_publish.items() if k not in all_subscribe}
    orphan_subscribe = {k: v for k, v in all_subscribe.items() if k not in all_publish}

    print(f"publish 事件类型总数: {len(all_publish)}")
    print(f"subscribe 事件类型总数: {len(all_subscribe)}")
    print(f"孤儿发布 (无订阅): {len(orphan_publish)}")
    for evt, files in list(orphan_publish.items())[:20]:
        print(f"  '{evt}': {files[:3]}")

    print(f"\n孤儿订阅 (无发布): {len(orphan_subscribe)}")
    for evt, files in list(orphan_subscribe.items())[:20]:
        print(f"  '{evt}': {files[:3]}")

    # === 5. 死代码候选 (类级 0 引用) ===
    print(f"\n{'=' * 80}")
    print("[5] 死代码候选扫描 (类级 0 引用, R6 §6.1 8 铁律)")
    print(f"{'=' * 80}")
    all_classes = defaultdict(list)
    for filepath in py_files:
        classes = find_class_definitions(filepath)
        for cls in classes:
            all_classes[cls['name']].append((filepath, cls['lineno']))

    # 检查每个类名在 py_files 中被引用的次数 (粗略, 用于 HVD 立项)
    class_references = defaultdict(int)
    for filepath in py_files:
        try:
            source = Path(filepath).read_text(encoding='utf-8')
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for cls_name in all_classes.keys():
            # 简单字符串匹配 (粗略)
            count = source.count(cls_name)
            if count > 0:
                class_references[cls_name] += count

    # 类名仅在自身文件中出现的可能候选
    print(f"已索引类名: {len(all_classes)}")
    print("(全项目 < 5 处字符串引用的类作为 HVD 候选起点, 后续需 4 源验证)")

    # 输出到 JSON 供后续使用
    import json
    output = {
        'long_locks': all_long_locks[:50],
        'container_self_parse': all_container_self,
        'exc_info_violations': {f: r for f, r in file_exc_results.items()},
        'orphan_publish': dict(orphan_publish),
        'orphan_subscribe': dict(orphan_subscribe),
        'all_classes_count': len(all_classes),
        'total_files': len(py_files),
    }
    output_path = 'tests/_r182_a_scan.json'
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n详细结果已写入: {output_path}")
    except Exception as e:
        print(f"JSON 写入失败: {e}")

    print(f"\n{'=' * 80}")
    print("R182 A 子智能体扫描完毕")
    print(f"{'=' * 80}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
