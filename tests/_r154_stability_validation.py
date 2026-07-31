#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R154 HVD-153-B 5x 稳定性验证 + AST unparse 锁嵌套验证
"""
import ast
import sys
import time
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============== Part 1: AST unparse 锁嵌套验证 ==============
def verify_lock_nesting():
    """AST unparse 严格验证 config_impact_analyzer.py 锁嵌套"""
    target = PROJECT_ROOT / "core" / "ai" / "config_impact_analyzer.py"
    content = target.read_text(encoding="utf-8")
    tree = ast.parse(content)

    target_locks = {"_analysis_lock", "_cache_lock"}
    violations = []

    def visit_with(node, parent_locks, depth=0):
        current_locks = set(parent_locks)
        for item in node.items:
            if isinstance(item.context_expr, ast.Attribute):
                if item.context_expr.attr in target_locks:
                    current_locks.add(item.context_expr.attr)
        for stmt in node.body:
            if isinstance(stmt, ast.With):
                for sub in stmt.items:
                    if isinstance(sub.context_expr, ast.Attribute):
                        lock_name = sub.context_expr.attr
                        if lock_name in target_locks and lock_name in current_locks:
                            violations.append({
                                "line": stmt.lineno,
                                "parent_locks": sorted(current_locks),
                                "inner_lock": lock_name,
                                "depth": depth,
                            })
                visit_with(stmt, current_locks, depth + 1)
            elif isinstance(stmt, ast.Try):
                for sub in stmt.body:
                    if isinstance(sub, ast.With):
                        visit_with(sub, current_locks, depth + 1)
            elif isinstance(stmt, (ast.If, ast.For, ast.While)):
                for sub in stmt.body:
                    if isinstance(sub, ast.With):
                        visit_with(sub, current_locks, depth + 1)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for sub in node.body:
                if isinstance(sub, ast.With):
                    visit_with(sub, set(), 0)

    print(f"[AST] config_impact_analyzer.py CROSS-LOCK 嵌套违规: {len(violations)}")
    for v in violations:
        print(f"  L{v['line']}: parent={v['parent_locks']} inner={v['inner_lock']} depth={v['depth']}")
    return len(violations) == 0


# ============== Part 2: 5x 稳定性并发测试 ==============
def stability_5x():
    """5x 稳定性验证 - HVD-153-B 锁修复"""
    from core.ai.config_impact_analyzer import ConfigImpactAnalyzer
    from core.importdata.import_config_manager import ImportTaskConfig, DataFrequency, ImportMode

    analyzer = ConfigImpactAnalyzer(db_path=":memory:")

    cfg_orig = ImportTaskConfig(
        task_id="r154_orig",
        name="R154 原配置",
        data_source="tdx",
        asset_type="stock",
        data_type="kdata",
        symbols=["000001.SZ"],
        frequency=DataFrequency.DAILY,
        mode=ImportMode.BATCH,
    )
    cfg_tgt = ImportTaskConfig(
        task_id="r154_tgt",
        name="R154 目标配置",
        data_source="tdx",
        asset_type="stock",
        data_type="kdata",
        symbols=["000001.SZ"],
        frequency=DataFrequency.DAILY,
        mode=ImportMode.SCHEDULED,
    )

    all_passed = True
    for round_n in range(5):
        start = time.perf_counter()
        errors = []
        lock = threading.Lock()

        def run():
            local_errors = []
            for _ in range(50):
                try:
                    analyzer.analyze_config_change_impact(cfg_orig, cfg_tgt)
                except Exception as e:
                    local_errors.append(str(e))
            if local_errors:
                with lock:
                    errors.extend(local_errors)

        threads = [threading.Thread(target=run) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed_ms = (time.perf_counter() - start) * 1000
        status = "PASS" if not errors else f"FAIL ({len(errors)})"
        print(f"[5x 稳定性] Round {round_n+1}/5: {elapsed_ms:.2f}ms, errors={len(errors)} {status}")
        if errors:
            all_passed = False

    return all_passed


if __name__ == "__main__":
    print("=" * 70)
    print("R154 HVD-153-B 5x 稳定性 + AST unparse 锁嵌套验证")
    print("=" * 70)
    print()
    print("--- Part 1: AST unparse 锁嵌套验证 ---")
    ast_ok = verify_lock_nesting()
    print()
    print("--- Part 2: 5x 稳定性并发测试 ---")
    stable_ok = stability_5x()
    print()
    print("=" * 70)
    print(f"R154 HVD-153-B 综合: {'PASS' if ast_ok and stable_ok else 'FAIL'}")
    print("=" * 70)
    sys.exit(0 if (ast_ok and stable_ok) else 1)
