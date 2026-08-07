"""
R238 锁嵌套检测器 (R104 §12 #3 + R100-F-P1-1 4 锁独立)

依据 R104 §12.4 铁律 #3 嵌套检测递归 with.body:
- 错误: ast.walk 扁平化, 丢失嵌套上下文
- 正确: 递归进入 with.body (含嵌套 with/try/if/循环)

依据 R8 §8.1 #8 (R100-F-P1-1 4 锁独立短锁铁律):
- 必须拆分 _lock / _futures_lock / _stats_lock / _history_lock 为 4 把独立短锁
- 禁止 在 with self._lock: 块内嵌套 with self._futures_lock: / _stats_lock: / _history_lock:
"""
import ast
import sys
from pathlib import Path

def find_nested_locks(tree, lock_names):
    """递归检测 with.body 内的锁嵌套.
    R100-F-P1-1: 任何 4 锁之一嵌套在另一个锁块内均视为违规.
    """
    violations = []

    def visit_block(stmts, parent_lock, path=""):
        for stmt in stmts:
            if isinstance(stmt, ast.With):
                for item in stmt.items:
                    lock_name = extract_lock_name(item.context_expr)
                    if lock_name in lock_names:
                        if parent_lock is not None:
                            # 嵌套违规! 任何 4 锁之一嵌套在另一个锁块内
                            violations.append({
                                "path": path,
                                "outer_lock": parent_lock,
                                "inner_lock": lock_name,
                                "line": stmt.lineno,
                            })
                        # 进入 with 块
                        visit_block(stmt.body, lock_name, f"{path}/with@{stmt.lineno}[{lock_name}]")
                        # 不再 visit 后续 stmt（已 visit）
                        return
                # 如果 with 内没有锁, 仍需 visit
                visit_block(stmt.body, parent_lock, f"{path}/with@{stmt.lineno}")
            elif isinstance(stmt, ast.Try):
                visit_block(stmt.body, parent_lock, f"{path}/try@{stmt.lineno}")
                visit_block(stmt.finalbody, parent_lock, f"{path}/try.finally@{stmt.lineno}")
            elif isinstance(stmt, ast.If):
                visit_block(stmt.body, parent_lock, f"{path}/if@{stmt.lineno}")
                visit_block(stmt.orelse, parent_lock, f"{path}/else@{stmt.lineno}")
            elif isinstance(stmt, (ast.For, ast.While)):
                visit_block(stmt.body, parent_lock, f"{path}/for@{stmt.lineno}")
                visit_block(stmt.orelse, parent_lock, f"{path}/for.else@{stmt.lineno}")

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    visit_block(item.body, None, f"{node.name}.{item.name}@{item.lineno}")

    return violations

def extract_lock_name(expr):
    """提取锁名, e.g. self._lock -> _lock."""
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name) and expr.value.id == "self":
        return expr.attr
    if isinstance(expr, ast.Name):
        return expr.id
    return None

if __name__ == "__main__":
    target_file = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\events\event_bus.py")
    if len(sys.argv) > 1:
        target_file = Path(sys.argv[1])
    src = target_file.read_text(encoding="utf-8")
    tree = ast.parse(src)

    # R100-F-P1-1 4 锁独立 + R235 §13.2 锁命名 (含 _dedup_lock)
    lock_names = {"_lock", "_futures_lock", "_stats_lock", "_history_lock", "_dedup_lock"}
    violations = find_nested_locks(tree, lock_names)

    print(f"File: {target_file}")
    print(f"Lock names (R100-F-P1-1): {sorted(lock_names)}")
    print(f"Total nested violations: {len(violations)}")
    print()
    if violations:
        for v in violations:
            print(f"  Line {v['line']}: {v['path']}")
            print(f"    OUTER: {v['outer_lock']}  CONTAINS  INNER: {v['inner_lock']}")
    else:
        print("  No lock nesting violations found.")
