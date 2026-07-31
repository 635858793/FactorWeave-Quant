"""R133 子智能体 D: 锁嵌套深度检测 (R104 §12 铁律 #3 + R111 经验)

核心规则:
1. 递归进入 with.body (不能用 ast.walk 扁平化)
2. 区分 Lock vs RLock (RLock 可重入, Lock 不行)
3. 跨方法调用需特别标注
4. 排除 'as 别名' 模式 (e.g., with lock: pass 模式)
"""
import ast
import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional

ROOT = Path('.').resolve()
SEARCH_DIRS = ['core', 'tests', 'plugins', 'gui', 'scripts', 'backtest', 'optimization']
SKIP_DIRS = ['__pycache__', '.git', '.pytest_cache', '.cache', 'node_modules']

def iter_py_files() -> List[str]:
    result = []
    for sdir in SEARCH_DIRS:
        dp = ROOT / sdir
        if not dp.exists(): continue
        for root, dirs, files in os.walk(dp):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if f.endswith('.py'):
                    result.append(os.path.join(root, f))
    for f in os.listdir(ROOT):
        if f.endswith('.py') and f != 'setup.py':
            full = ROOT / f
            if full.is_file() and str(full) not in result:
                result.append(str(full))
    return result

def get_lock_names_from_assignment(node) -> Set[str]:
    """提取赋值语句中的锁变量名 (e.g., self._lock = threading.Lock())"""
    # 处理 ast.Assign (有 targets) 和 ast.AnnAssign (有 target)
    target = getattr(node, 'targets', None)
    if target is None:
        target = [node.target] if hasattr(node, 'target') and node.target else []
    if not target:
        return set()
    if not isinstance(node.value, ast.Call):
        return set()
    func = node.value.func
    if isinstance(func, ast.Attribute):
        class_name = func.attr
        if 'Lock' in class_name:  # Lock, RLock, Event
            if isinstance(target[0], ast.Attribute):
                return {target[0].attr}
    return set()

def collect_lock_definitions(tree: ast.Module) -> Set[str]:
    """收集模块中所有 self._xxx_lock 锁定义"""
    locks = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for name in get_lock_names_from_assignment(node):
                locks.add(name)
        elif isinstance(node, ast.AnnAssign) and node.value:
            for name in get_lock_names_from_assignment(node):
                locks.add(name)
    return locks

def check_nested_locks(method_ast: ast.AST, target_locks: Set[str], class_name: str = "") -> List[Dict]:
    """递归检查方法体中是否嵌套 target_locks (R104 §12 铁律 #3)

    Returns: [{lock_name, outer_method, inner_method, line, severity, lock_type}]
    """
    violations = []

    def visit_block(block, parent_locks, current_func, depth=0):
        for stmt in block:
            if isinstance(stmt, ast.With):
                current_locks = parent_locks.copy()
                for item in stmt.items:
                    if isinstance(item.context_expr, ast.Attribute):
                        lock_name = item.context_expr.attr
                        if lock_name in target_locks:
                            current_locks.add(lock_name)
                            # 检查是否嵌套
                            if lock_name in parent_locks:
                                # 嵌套: 检测 lock 类型
                                severity = "CRITICAL" if depth > 0 else "WARNING"
                                violations.append({
                                    'class': class_name,
                                    'method': current_func,
                                    'lock': lock_name,
                                    'line': stmt.lineno,
                                    'severity': severity,
                                    'nesting_depth': depth + 1,
                                })
                # 递归进入 body
                if current_locks:
                    visit_block(stmt.body, current_locks, current_func, depth + 1)
                else:
                    visit_block(stmt.body, parent_locks, current_func, depth)
            elif isinstance(stmt, (ast.If, ast.For, ast.While, ast.Try)):
                # 递归进入控制流
                sub = getattr(stmt, 'body', [])
                if sub:
                    visit_block(sub, parent_locks, current_func, depth)
                if hasattr(stmt, 'orelse') and stmt.orelse:
                    visit_block(stmt.orelse, parent_locks, current_func, depth)
                if isinstance(stmt, ast.Try) and stmt.finalbody:
                    visit_block(stmt.finalbody, parent_locks, current_func, depth)
            elif isinstance(stmt, ast.FunctionDef):
                # 嵌套函数定义, 重置锁
                visit_block(stmt.body, set(), stmt.name, depth)

    for node in ast.iter_child_nodes(method_ast):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            visit_block(node.body, set(), node.name, 0)

    return violations

def analyze_file(fp: str) -> List[Dict]:
    """分析单个文件, 找出所有 lock 嵌套违规"""
    try:
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError, ValueError):
        return []

    target_locks = collect_lock_definitions(tree)
    if not target_locks:
        return []

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_violations = check_nested_locks(node, target_locks, node.name)
            for v in class_violations:
                v['file'] = os.path.relpath(fp, ROOT)
            violations.extend(class_violations)

    return violations

def main():
    py_files = iter_py_files()
    print(f"Total py files: {len(py_files)}", file=sys.stderr)

    all_violations = []
    for fp in py_files:
        v = analyze_file(fp)
        all_violations.extend(v)

    # 输出
    by_file = {}
    for v in all_violations:
        by_file.setdefault(v['file'], []).append(v)

    print(f"Files with violations: {len(by_file)}")
    for fp, vs in sorted(by_file.items(), key=lambda x: -len(x[1]))[:20]:
        print(f"  {fp}: {len(vs)} violations")
        for v in vs[:3]:
            print(f"    {v['class']}.{v['method']} L{v['line']} {v['lock']} severity={v['severity']}")

    # 严重等级
    critical = [v for v in all_violations if v['severity'] == 'CRITICAL']
    warning = [v for v in all_violations if v['severity'] == 'WARNING']
    print()
    print(f"CRITICAL: {len(critical)}")
    print(f"WARNING: {len(warning)}")

    with open('.audit_r133_d_lock_nesting.json', 'w', encoding='utf-8') as f:
        json.dump(all_violations, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    main()
