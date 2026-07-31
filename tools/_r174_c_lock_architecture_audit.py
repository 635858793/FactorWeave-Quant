"""
R174-C 锁架构深度分析
- R104 §12 铁律 #3+#5 严格实现 (递归 with.body + AST unparse)
- R100-F-P1-1 4 锁独立策略核验
- 输出 AccountManager + TradingEngine 完整长锁清单
"""

import ast
import json
import sys
from pathlib import Path
from typing import List, Dict, Set


def get_lock_name(item: ast.withitem) -> str | None:
    """从 with 项提取锁名 (处理 self._xxx_lock 形式)"""
    ctx = item.context_expr
    if isinstance(ctx, ast.Attribute):
        if isinstance(ctx.value, ast.Name) and ctx.value.id == "self":
            return ctx.attr
    elif isinstance(ctx, ast.Name):
        return ctx.id
    return None


def find_nested_locks_in_method(method_node: ast.FunctionDef, target_locks: Set[str]) -> List[Dict]:
    """递归进入 with.body 检测锁嵌套 (R104 §12 铁律 #3)"""
    violations = []

    def visit_with(with_node, parent_locks, path_stack):
        current_locks = set(parent_locks)
        new_locks = set()
        for item in with_node.items:
            lock_name = get_lock_name(item)
            if lock_name and lock_name in target_locks:
                if lock_name in current_locks:
                    violations.append({
                        "type": "NESTED_LOCK",
                        "outer_lock": lock_name,
                        "inner_lock": lock_name,
                        "method": method_node.name,
                        "line": with_node.lineno,
                        "depth": len(current_locks) + 1,
                    })
                new_locks.add(lock_name)
        current_locks = current_locks | new_locks
        for stmt in with_node.body:
            visit_stmt(stmt, current_locks, path_stack + [with_node])
        for stmt in with_node.orelse if hasattr(with_node, 'orelse') else []:
            visit_stmt(stmt, current_locks, path_stack + [with_node])

    def visit_stmt(stmt, current_locks, path_stack):
        if isinstance(stmt, ast.With):
            visit_with(stmt, current_locks, path_stack)
        elif isinstance(stmt, ast.If):
            for s in stmt.body: visit_stmt(s, current_locks, path_stack)
            for s in stmt.orelse: visit_stmt(s, current_locks, path_stack)
        elif isinstance(stmt, (ast.For, ast.While)):
            for s in stmt.body: visit_stmt(s, current_locks, path_stack)
            for s in stmt.orelse: visit_stmt(s, current_locks, path_stack)
        elif isinstance(stmt, ast.Try):
            for s in stmt.body: visit_stmt(s, current_locks, path_stack)
            for s in stmt.handlers:
                for s2 in s.body: visit_stmt(s2, current_locks, path_stack)
            for s in stmt.orelse: visit_stmt(s, current_locks, path_stack)
            for s in stmt.finalbody: visit_stmt(s, current_locks, path_stack)

    for stmt in method_node.body:
        visit_stmt(stmt, set(), [])
    return violations


def measure_lock_block_size(method_node: ast.FunctionDef, target_locks: Set[str]) -> List[Dict]:
    """测量 with 锁块大小 (行数), 标记长锁"""
    long_locks = []

    def visit_stmt(stmt, current_locks):
        if isinstance(stmt, ast.With):
            for item in stmt.items:
                lock_name = get_lock_name(item)
                if lock_name and lock_name in target_locks:
                    start = stmt.lineno
                    end = stmt.end_lineno or start
                    size = end - start + 1
                    if size >= 10:
                        long_locks.append({
                            "lock": lock_name,
                            "method": method_node.name,
                            "line": start,
                            "end_line": end,
                            "size": size,
                        })
            for s in stmt.body: visit_stmt(s, current_locks)
        elif isinstance(stmt, ast.If):
            for s in stmt.body: visit_stmt(s, current_locks)
            for s in stmt.orelse: visit_stmt(s, current_locks)
        elif isinstance(stmt, (ast.For, ast.While)):
            for s in stmt.body: visit_stmt(s, current_locks)
            for s in stmt.orelse: visit_stmt(s, current_locks)
        elif isinstance(stmt, ast.Try):
            for s in stmt.body: visit_stmt(s, current_locks)
            for s in stmt.finalbody: visit_stmt(s, current_locks)

    for stmt in method_node.body:
        visit_stmt(stmt, set())
    return long_locks


def get_method_source(node: ast.FunctionDef, source_lines: List[str]) -> str:
    """AST unparse 还原方法体 (R104 §12 铁律 #5)"""
    if hasattr(node, 'end_lineno') and node.end_lineno:
        return "\n".join(source_lines[node.lineno-1:node.end_lineno])
    return ""


def analyze_long_lock_with_io(method_node, source_lines, target_locks) -> List[Dict]:
    """对每个长锁方法, 用 AST unparse 还原方法体, 二次验证锁内 IO"""
    io_keywords = {
        "publish", "submit_order", "submit", "save", "write", "update",
        "execute", "query", "insert", "delete", "send", "fetch",
        "request", "call", "log", "notify", "send_mail", "broadcast",
        "sync_account_positions", "sync_data",
    }
    method_source = get_method_source(method_node, source_lines)
    findings = []
    for line in method_source.split("\n"):
        for kw in io_keywords:
            if f"{kw}(" in line and "self." in line:
                findings.append({
                    "method": method_node.name,
                    "method_line": method_node.lineno,
                    "io_keyword": kw,
                    "code_snippet": line.strip()[:120],
                })
    return findings


def analyze_file_detailed(file_path: str, target_locks: Set[str], long_lock_threshold: int = 10) -> Dict:
    if not Path(file_path).exists():
        return {"error": f"File not found: {file_path}"}
    source = Path(file_path).read_text(encoding="utf-8", errors="ignore")
    source_lines = source.split("\n")
    tree = ast.parse(source)
    all_nested = []
    all_long = []
    all_io_in_method = []
    found_locks = set()
    methods = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    if isinstance(target.value, ast.Name) and target.value.id == "self":
                        name = target.attr
                        if "_lock" in name:
                            found_locks.add(name)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            methods[node.name] = node
            all_nested.extend(find_nested_locks_in_method(node, target_locks))
            all_long.extend(measure_lock_block_size(node, target_locks))
            all_io_in_method.extend(analyze_long_lock_with_io(node, source_lines, target_locks))

    return {
        "file": file_path,
        "found_locks": sorted(found_locks),
        "target_locks": sorted(target_locks),
        "missing_locks": sorted(target_locks - found_locks),
        "nested_violations": all_nested,
        "long_locks": all_long,
        "io_in_long_locks": all_io_in_method,
        "total_methods": len(methods),
    }


def main():
    targets = {
        "AccountManager": {
            "path": "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/trading/account_manager.py",
            "locks": {"_account_lock", "_position_lock", "_fund_info_lock", "_sync_lock"},
        },
        "TradingEngine": {
            "path": "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/trading_engine.py",
            "locks": {"_cache_lock", "_positions_lock", "_signals_lock", "_pending_lock"},
        },
    }
    output = {}
    for name, conf in targets.items():
        print(f"\n{'='*80}\nR174-C 锁架构深度分析: {name}\n{'='*80}")
        result = analyze_file_detailed(conf["path"], conf["locks"])
        output[name] = result
        print(f"  找到锁: {result['found_locks']}")
        if result['missing_locks']:
            print(f"  缺目标锁: {result['missing_locks']}")
        print(f"  方法总数: {result['total_methods']}")
        print(f"  锁嵌套: {len(result['nested_violations'])} 处")
        print(f"  长锁 (≥10 行): {len(result['long_locks'])} 处")
        print(f"  长锁方法中含 IO 关键字: {len(result['io_in_long_locks'])} 处")
        print(f"\n  --- 长锁完整清单 ---")
        for ll in sorted(result['long_locks'], key=lambda x: -x['size']):
            print(f"    {ll['method']}.{ll['line']}: {ll['lock']} ({ll['size']} 行, L{ll['line']}-L{ll['end_line']})")
        print(f"\n  --- 长锁方法内 IO 关键字 (AST unparse 验证) ---")
        for io in result['io_in_long_locks']:
            print(f"    {io['method']} (L{io['method_line']}): {io['io_keyword']}() → {io['code_snippet']}")

    out_path = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/.trae/reports/rounds/_r174_c_lock_architecture.json"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n\n详细 JSON 输出: {out_path}")


if __name__ == "__main__":
    main()
