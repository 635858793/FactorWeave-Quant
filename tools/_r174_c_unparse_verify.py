"""
R174-C AST unparse 验证脚本
对每个长锁方法 unparse 完整方法体二次验证
R104 §12 铁律 #5 严格实施
"""

import ast
import json
import sys
from pathlib import Path
from typing import List, Dict


def unparse_method_body(source_lines: List[str], start_line: int, end_line: int) -> str:
    """AST unparse 还原方法体"""
    return "\n".join(source_lines[start_line-1:end_line])


def find_lock_blocks(source_lines: List[str], method_start: int, method_end: int) -> List[Dict]:
    """找出方法内所有 with 块 (用于二次验证锁内 IO)"""
    src = "\n".join(source_lines[method_start-1:method_end])
    tree = ast.parse(src)
    locks = []

    def visit_with(node, depth=0, parent=None):
        if isinstance(node, ast.With):
            for item in node.items:
                ctx = item.context_expr
                lock_name = None
                if isinstance(ctx, ast.Attribute):
                    if isinstance(ctx.value, ast.Name) and ctx.value.id == "self":
                        lock_name = ctx.attr
                elif isinstance(ctx, ast.Name):
                    lock_name = ctx.id
                if lock_name and "_lock" in lock_name:
                    locks.append({
                        "lock": lock_name,
                        "start": method_start + node.lineno - 1,
                        "end": method_start + (node.end_lineno or node.lineno) - 1,
                        "depth": depth,
                    })
            for child in node.body:
                visit_with(child, depth + 1, lock_name)

    for stmt in tree.body[0].body:
        visit_with(stmt)
    return locks


def check_io_in_range(source_lines: List[str], start: int, end: int) -> List[Dict]:
    """检查区间内的 IO 调用"""
    io_patterns = ["publish", "save_account", "save_position", "save_fund_info",
                   "delete_account", "delete_position", "get_accounts", "query_positions",
                   "save", "execute", "fetch", "query"]
    findings = []
    for i in range(start, min(end + 1, len(source_lines))):
        line = source_lines[i - 1]
        for pat in io_patterns:
            if pat in line and "self." in line:
                findings.append({
                    "line": i,
                    "code": line.strip()[:160],
                    "io_keyword": pat,
                })
    return findings


def main():
    # AccountManager 长锁方法
    am_methods = [
        ("refresh_accounts", 269, 310),
        ("create_account", 372, 427),
        ("update_account", 428, 469),
        ("query_accounts", 485, 529),
        ("delete_account", 530, 562),
        ("create_position", 563, 611),
        ("update_position", 611, 684),
        ("query_positions", 698, 738),
        ("delete_position", 740, 770),
        ("update_fund_info", 772, 815),
        ("freeze_cash", 1164, 1234),
        ("unfreeze_cash", 1235, 1310),
        ("_on_position_updated", 2400, 2565),
        ("_schedule_position_sync", 2589, 2620),
    ]

    # TradingEngine 长锁方法
    te_methods = [
        ("_reduce_pending_position", 580, 656),
        ("add_signal", 760, 825),
        ("execute_signal", 1100, 1150),
        ("_execute_buy", 1232, 1395),
        ("_execute_sell", 1419, 1650),
        ("_risk_check", 1760, 1942),
        ("update_positions", 2307, 2340),
        ("_publish_correlation_warning", 2750, 2880),
    ]

    print("=" * 80)
    print("R174-C AST unparse 验证长锁内 IO (R104 §12 铁律 #5)")
    print("=" * 80)

    # AccountManager
    print("\n--- AccountManager 长锁内 IO 验证 ---")
    am_path = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/trading/account_manager.py"
    am_source = Path(am_path).read_text(encoding="utf-8", errors="ignore").split("\n")
    for name, start, end in am_methods:
        locks = find_lock_blocks(am_source, start, end)
        for lock in locks:
            io_findings = check_io_in_range(am_source, lock["start"], lock["end"])
            if io_findings:
                print(f"\n  {name} (L{start}-L{end})")
                print(f"    锁: {lock['lock']} (L{lock['start']}-L{lock['end']}, depth={lock['depth']})")
                for io in io_findings:
                    print(f"    ⚠️ L{io['line']} [{io['io_keyword']}]: {io['code']}")

    # TradingEngine
    print("\n--- TradingEngine 长锁内 IO 验证 ---")
    te_path = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/trading_engine.py"
    te_source = Path(te_path).read_text(encoding="utf-8", errors="ignore").split("\n")
    for name, start, end in te_methods:
        locks = find_lock_blocks(te_source, start, end)
        for lock in locks:
            io_findings = check_io_in_range(te_source, lock["start"], lock["end"])
            if io_findings:
                print(f"\n  {name} (L{start}-L{end})")
                print(f"    锁: {lock['lock']} (L{lock['start']}-L{lock['end']}, depth={lock['depth']})")
                for io in io_findings:
                    print(f"    ⚠️ L{io['line']} [{io['io_keyword']}]: {io['code']}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
