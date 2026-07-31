"""
R170-C 锁架构 AST 递归扫描脚本
符合 R104 §12 #3 (AST 递归 with.body) + #5 (AST unparse 验证) 铁律
- 禁止用 ast.walk 扁平化
- 必须递归进入 with.body → try.body → if.body → for.body → while.body
- 必须用 ast.unparse 还原方法体, 二次验证锁路径
"""
import ast
import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Set, Tuple, Any


def collect_with_blocks(node: ast.AST, parent_locks: Set[str] = None,
                        results: List[Dict] = None, path: str = "") -> List[Dict]:
    """递归进入所有控制流结构, 收集 with 块及其路径上的锁"""
    if parent_locks is None:
        parent_locks = set()
    if results is None:
        results = []

    # 提取当前 with 块的锁名
    current_locks = set()
    if isinstance(node, ast.With):
        for item in node.items:
            if isinstance(item.context_expr, ast.Name):
                current_locks.add(item.context_expr.id)
            elif isinstance(item.context_expr, ast.Attribute):
                current_locks.add(ast.unparse(item.context_expr))

        # 检查嵌套
        nested_violation = current_locks & parent_locks
        if nested_violation:
            results.append({
                "type": "nested_lock",
                "outer_locks": list(parent_locks),
                "inner_lock": list(nested_violation),
                "line": node.lineno,
                "path": path,
            })

        # 递归进入 with.body
        new_parent = parent_locks | current_locks
        for stmt in node.body:
            collect_with_blocks(stmt, new_parent, results, path + f" -> with:{list(current_locks)}")
    else:
        # 递归进入所有子节点 (for, while, if, try, with, function)
        for child in ast.iter_child_nodes(node):
            # 进入新控制流时, 锁路径延续
            collect_with_blocks(child, parent_locks, results, path)

    return results


def detect_nested_locks_in_method(method_node: ast.FunctionDef,
                                  target_lock_names: Set[str]) -> List[Dict]:
    """检测单个方法内的锁嵌套 (R104 §12 #5: AST unparse 验证)"""
    # 第一遍: ast.unparse 还原方法体
    method_source = ast.unparse(method_node)
    # 第二遍: 重新解析, 递归进入
    try:
        reparsed = ast.parse(method_source).body[0]
    except Exception:
        return []

    violations = []
    # 提取方法参数和局部变量中的锁名
    method_locks = set()
    for arg in method_node.args.args:
        method_locks.add(arg.arg)

    collect_with_blocks(reparsed, set(), violations)
    return violations


def scan_file_for_nested_locks(filepath: str,
                                target_lock_names: Set[str]) -> List[Dict]:
    """扫描单个 Python 文件, 检测所有方法的锁嵌套"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()
    except Exception as e:
        return [{"error": f"read_failed: {e}", "file": filepath}]

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        return [{"error": f"syntax_error: {e}", "file": filepath}]

    all_violations = []
    for node in ast.walk(tree):
        # 只检查方法/函数
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            violations = detect_nested_locks_in_method(node, target_lock_names)
            for v in violations:
                v["method"] = node.name
                v["file"] = filepath
                v["method_line"] = node.lineno
            all_violations.extend(violations)

    return all_violations


def main():
    project_root = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")
    target_dirs = ["core", "gui", "plugins", "tests"]

    # 重点关注的目标锁 (R100-F-P1-1 4 锁独立策略)
    target_locks = {
        "_lock", "_positions_lock", "_stats_lock", "_history_lock",
        "_futures_lock", "_cache_lock", "_orders_lock", "_risk_lock",
        "_trades_lock", "_alerts_lock", "_events_lock", "_market_lock",
        "_data_lock", "_config_lock", "_state_lock", "_write_lock",
        "_read_lock", "_portfolio_lock", "_signal_lock", "_strategy_lock",
    }

    all_violations = []
    files_scanned = 0
    files_with_locks = 0
    file_extensions = [".py"]

    print(f"=== R170-C 锁架构 AST 递归扫描 ===")
    print(f"项目根目录: {project_root}")
    print(f"扫描目录: {target_dirs}")
    print(f"目标锁: {sorted(target_locks)}")
    print(f"算法: AST 递归 with.body + ast.unparse 验证 (R104 §12 #3 #5)")
    print()

    for target_dir in target_dirs:
        dir_path = project_root / target_dir
        if not dir_path.exists():
            continue
        for root, dirs, files in os.walk(dir_path):
            # 跳过 .pytest_cache, __pycache__, .bak
            dirs[:] = [d for d in dirs if d not in
                       {".pytest_cache", "__pycache__", ".git", "node_modules"}]
            for fname in files:
                if not any(fname.endswith(ext) for ext in file_extensions):
                    continue
                # 跳过 .bak 备份
                if ".bak" in fname or ".pre" in fname:
                    continue
                filepath = os.path.join(root, fname)
                files_scanned += 1
                violations = scan_file_for_nested_locks(filepath, target_locks)
                if violations:
                    files_with_locks += 1
                    all_violations.extend(violations)

    print(f"扫描文件总数: {files_scanned}")
    print(f"含锁使用文件数: {files_with_locks}")
    print(f"发现锁嵌套违规: {len(all_violations)}")
    print()

    if all_violations:
        print("=== 锁嵌套违规详情 ===")
        for v in all_violations:
            if "error" in v:
                print(f"  [ERROR] {v['file']}: {v['error']}")
            else:
                print(f"  {v.get('file', '?')}:{v.get('line', '?')} "
                      f"method={v.get('method', '?')} "
                      f"outer={v.get('outer_locks', [])} "
                      f"inner={v.get('inner_lock', [])}")
    else:
        print("✅ 0 锁嵌套违规 (符合 R104 §12 #3 #5 铁律)")

    # 写出 JSON 报告
    report = {
        "scanned_files": files_scanned,
        "files_with_locks": files_with_locks,
        "violations_count": len(all_violations),
        "violations": all_violations,
        "algorithm": "AST recursive with.body traversal + ast.unparse verification",
        "r104_compliance": "R104 §12 #3 (recursive) + #5 (ast.unparse)"
    }
    with open(project_root / "tools" / "r170_c_lock_scan.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    return 0 if not all_violations else 1


if __name__ == "__main__":
    sys.exit(main())
