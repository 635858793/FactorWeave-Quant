#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 order_executor.py 中所有方法, 找 with 块 >= 40 行的候选"""
import ast
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")
TARGET_LOCKS = {
    '_positions_lock', '_order_lock', '_position_lock',
    '_state_lock', '_cache_lock', '_signals_lock',
    '_account_lock', '_fund_info_lock', '_sync_lock',
    '_portfolio_lock', '_trade_history_lock', '_service_lock', '_ctp_lock',
    '_interface_health_lock', '_alert_history_lock',
}


def get_lock_name(item):
    if not isinstance(item.context_expr, ast.Attribute):
        return None
    if not isinstance(item.context_expr.value, ast.Name):
        return None
    if item.context_expr.value.id != 'self':
        return None
    return item.context_expr.attr


def find_long_with_blocks(method_node):
    """找方法中所有 with 块, 返回 [(lock_name, body_lines, lineno, end_lineno)]"""
    results = []

    def visit(node, parent_locks):
        if isinstance(node, ast.With):
            for item in node.items:
                lock_name = get_lock_name(item)
                if lock_name and lock_name in TARGET_LOCKS:
                    body_start = min((getattr(s, 'lineno', 0) for s in node.body), default=0)
                    body_end = max((getattr(s, 'end_lineno', 0) for s in node.body), default=0)
                    body_lines = body_end - body_start + 1
                    results.append((lock_name, body_lines, node.lineno, body_end))
                    for stmt in node.body:
                        visit(stmt, parent_locks | {lock_name})
                    return
                else:
                    for stmt in node.body:
                        visit(stmt, parent_locks)
                    return
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for stmt in node.body:
                visit(stmt, parent_locks)
        elif isinstance(node, ast.If):
            for stmt in node.body:
                visit(stmt, parent_locks)
            for stmt in node.orelse:
                visit(stmt, parent_locks)
        elif isinstance(node, (ast.For, ast.While)):
            for stmt in node.body:
                visit(stmt, parent_locks)
            for stmt in node.orelse:
                visit(stmt, parent_locks)
        elif isinstance(node, ast.Try):
            for stmt in node.body:
                visit(stmt, parent_locks)
            for stmt in node.handlers:
                visit(stmt, parent_locks)
            for stmt in node.finalbody:
                visit(stmt, parent_locks)

    visit(method_node, set())
    return results


def scan_file(filepath, min_lock_lines=40):
    full_path = PROJECT_ROOT / filepath
    src = full_path.read_text(encoding='utf-8')
    tree = ast.parse(src)

    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            method_lines = node.end_lineno - node.lineno + 1
            locks = find_long_with_blocks(node)
            for lock_name, body_lines, lineno, end_lineno in locks:
                if body_lines >= min_lock_lines:
                    findings.append({
                        'method': node.name,
                        'method_start': node.lineno,
                        'method_end': node.end_lineno,
                        'method_lines': method_lines,
                        'lock': lock_name,
                        'lock_body_lines': body_lines,
                        'lock_start': lineno,
                        'lock_end': end_lineno,
                    })
    return findings


def main():
    print("=" * 100)
    print("R175-C P1 长锁扫描 (threshold: lock body >= 40 lines)")
    print("=" * 100)

    files = [
        "core/trading_engine.py",
        "core/trading/order_executor.py",
        "core/trading/account_manager.py",
        "core/services/trading_service.py",
        "core/risk_monitoring/enhanced_risk_monitor.py",
        "core/risk_monitoring/enhanced_risk_precheck.py",
        "core/risk_monitoring/liquidity_risk_monitor.py",
        "core/risk_monitoring/risk_monitor.py",
    ]

    for fp in files:
        full_path = PROJECT_ROOT / fp
        if not full_path.exists():
            continue
        findings = scan_file(fp, min_lock_lines=30)
        if not findings:
            continue
        print(f"\n### {fp}  ({len(findings)} candidates)")
        print(f"{'method':<35} {'method_lines':>12} {'lock':<22} {'lock_body':>9} {'lock_range':<20}")
        print("-" * 100)
        for f in findings:
            print(f"{f['method']:<35} {f['method_lines']:>12} {f['lock']:<22} {f['lock_body_lines']:>9} L{f['lock_start']}-{f['lock_end']}")


if __name__ == "__main__":
    main()
