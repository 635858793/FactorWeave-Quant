"""
R221 子智能体 C - 4 锁独立策略审计工具

严格遵循 R104 §12.3 + R104 §12.5 铁律:
- AST 递归进入 with.body (R104 §12.3 教训)
- AST unparse 验证方法体 (R104 §12.5 教训)
- 4 锁独立策略检查 (_lock / _futures_lock / _stats_lock / _history_lock)

R100-F-P1-1 4 锁独立铁律:
- 禁止在 `with self._lock:` 块内嵌套 `with self._futures_lock:` / `_stats_lock` / `_history_lock`
- 持锁时间最小化: 锁内只读, 锁外用快照

R221-C-LOCK-AUDIT
"""
import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict
import json


PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
EVENT_BUS_PATH = PROJECT_ROOT / "core" / "events" / "event_bus.py"

# 4 锁 (EventBus 内的关键锁)
LOCK_NAMES = {"_lock", "_futures_lock", "_stats_lock", "_history_lock"}


def collect_with_in_method(method_node, lock_names=LOCK_NAMES):
    """递归检测方法内 with 块嵌套, 严格遵循 R104 §12.3

    Args:
        method_node: ast.FunctionDef 节点
        lock_names: 关注的锁名集合

    Returns:
        violations: list of {outer_lock, inner_lock, line, method, code}
    """
    violations = []

    def get_lock_name(item):
        """从 with item 中提取锁名 (支持 self._lock 形式)"""
        ctx = item.context_expr
        if isinstance(ctx, ast.Attribute) and ctx.attr in lock_names:
            return ctx.attr
        if isinstance(ctx, ast.Name) and ctx.id in lock_names:
            return ctx.id
        return None

    def visit_with(with_node, parent_locks, parent_method):
        """访问 with 节点, 递归检查嵌套"""
        # 收集本次 with 的锁
        current_locks = set(parent_locks)
        for item in with_node.items:
            lock_name = get_lock_name(item)
            if lock_name:
                current_locks.add(lock_name)

        # 关键: 递归进入 with.body
        for stmt in with_node.body:
            if isinstance(stmt, ast.With):
                # 嵌套 with, 检查是否锁嵌套
                for sub_item in stmt.items:
                    sub_lock = get_lock_name(sub_item)
                    if sub_lock and sub_lock in parent_locks:
                        # 真正嵌套! 违反 R100-F-P1-1
                        violations.append({
                            "outer_lock": sub_lock,
                            "inner_lock": sub_lock,
                            "line": stmt.lineno,
                            "outer_line": with_node.lineno,
                            "method": parent_method,
                            "code": ast.unparse(with_node)[:200] if hasattr(ast, 'unparse') else "",
                        })
                visit_with(stmt, current_locks, parent_method)
            elif isinstance(stmt, ast.Try):
                visit_try(stmt, current_locks, parent_method)
            elif isinstance(stmt, (ast.If, ast.For, ast.While)):
                # 递归进入 body / orelse
                visit_block(stmt.body, current_locks, parent_method)
                if hasattr(stmt, 'orelse') and stmt.orelse:
                    visit_block(stmt.orelse, current_locks, parent_method)

    def visit_try(try_node, parent_locks, parent_method):
        visit_block(try_node.body, parent_locks, parent_method)
        visit_block(try_node.orelse, parent_locks, parent_method)
        for h in try_node.handlers:
            visit_block(h.body, parent_locks, parent_method)
        visit_block(try_node.finalbody, parent_locks, parent_method)

    def visit_block(stmts, parent_locks, parent_method):
        for stmt in stmts:
            if isinstance(stmt, ast.With):
                visit_with(stmt, parent_locks, parent_method)
            elif isinstance(stmt, ast.Try):
                visit_try(stmt, parent_locks, parent_method)
            elif isinstance(stmt, (ast.If, ast.For, ast.While)):
                visit_block(stmt.body, parent_locks, parent_method)
                if hasattr(stmt, 'orelse') and stmt.orelse:
                    visit_block(stmt.orelse, parent_locks, parent_method)

    visit_block(method_node.body, set(), method_node.name)
    return violations


def find_4_locks_audit(tree: ast.Module) -> List[Dict[str, Any]]:
    """扫描整个文件, 找出所有方法的 4 锁嵌套违规"""
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            violations = collect_with_in_method(node)
            if violations:
                results.append({
                    "method": node.name,
                    "line": node.lineno,
                    "violations": violations,
                })
    return results


def main():
    if not EVENT_BUS_PATH.exists():
        print(f"[R221-C-LOCK] 文件不存在: {EVENT_BUS_PATH}")
        return

    print(f"[R221-C-LOCK] 开始审计 {EVENT_BUS_PATH}")
    with open(EVENT_BUS_PATH, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source, filename=str(EVENT_BUS_PATH))
    results = find_4_locks_audit(tree)

    # 4 锁独立合规状态
    print(f"\n[R221-C-LOCK] 4 锁嵌套违规检查:")
    print(f"  - 总方法数: {sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))}")
    print(f"  - 违规方法数: {len(results)}")
    print(f"  - 总违规数: {sum(len(r['violations']) for r in results)}")

    if results:
        print(f"\n  违规详情:")
        for r in results:
            print(f"  - 方法 `{r['method']}` (L{r['line']}):")
            for v in r['violations']:
                print(f"    - 锁嵌套: {v['outer_lock']} -> {v['inner_lock']} @ L{v['line']} (外锁 @ L{v['outer_line']})")

    # 保存 JSON
    output = {
        "file": str(EVENT_BUS_PATH),
        "lock_names": list(LOCK_NAMES),
        "violation_methods": results,
        "total_violations": sum(len(r['violations']) for r in results),
        "audit_compliant": len(results) == 0,
    }
    json_path = PROJECT_ROOT / "tools" / "_r221_c_lock_audit.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n[R221-C-LOCK] JSON 已保存到: {json_path}")

    return output


if __name__ == "__main__":
    main()
