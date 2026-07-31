#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R181-D 误修核查: 检查所有带 exc_info=True 的 logger 调用是否在 try/except 块内"""
import ast
import sys
from pathlib import Path
from typing import List, Dict, Any


TARGET_FILES = [
    "core/database/duckdb_manager.py",
    "core/agents/fusion_engine.py",
    "core/agents/technical_agent.py",
    "core/services/strategy_service.py",
    "core/services/stock_service.py",
    "core/services/asset_service.py",
    "core/services/industry_service.py",
    "core/services/chart_service.py",
    "core/agents/news_agent.py",
    "core/agents/sentiment_agent.py",
]


def build_parent_map(tree: ast.AST) -> Dict[int, ast.AST]:
    parent_map = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent_map[id(child)] = node
    return parent_map


def find_enclosing_try(node: ast.AST, parent_map: Dict[int, ast.AST]) -> ast.Try:
    """找到最近的祖先 Try 节点"""
    current = node
    while current is not None and id(current) in parent_map:
        current = parent_map[id(current)]
        if isinstance(current, ast.Try):
            return current
    return None


def has_exc_info_true(node: ast.Call) -> bool:
    for kw in node.keywords:
        if kw.arg == "exc_info":
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
            if isinstance(kw.value, ast.NameConstant) and kw.value.value is True:
                return True
    return False


def is_in_except_handler(node: ast.AST, parent_map: Dict[int, ast.AST]) -> bool:
    """检查节点是否在 except handler 内"""
    current = node
    while current is not None and id(current) in parent_map:
        current = parent_map[id(current)]
        if isinstance(current, ast.ExceptHandler):
            return True
    return False


def is_in_try_body(node: ast.AST, parent_map: Dict[int, ast.AST]) -> bool:
    """检查节点是否在 try 块主体 (非 except/finally) 内"""
    # 找到最近的 Try 节点, 然后判断节点在 try 的哪个 body 内
    current = node
    last_try = None
    while current is not None and id(current) in parent_map:
        current = parent_map[id(current)]
        if isinstance(current, ast.Try):
            last_try = current
            break
    if last_try is None:
        return False
    # 检查 node 在 last_try.body (而非 handlers[].body 或 finalbody) 中
    # 通过再次向上追溯: 如果 node 在 last_try.body 内, 但不在任何 handler.body 内
    # 简化: 已经在 is_in_except_handler 中判断过, 这里只检查是否有 try 祖先
    return True  # 已经在函数入口处检查过 has try 祖先


def analyze_file(file_path: str) -> Dict[str, Any]:
    """分析文件, 找出所有带 exc_info=True 的 logger 调用及其上下文"""
    if not Path(file_path).exists():
        return {"error": "file not found"}

    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as e:
        return {"error": f"syntax: {e}"}

    parent_map = build_parent_map(tree)
    result = {
        "total_exc_info_true": 0,
        "in_except": 0,
        "in_try_body": 0,
        "no_try_ancestor": 0,  # 误修: 不在任何 try/except 内
        "details": [],
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if not isinstance(node.func.value, ast.Name):
            continue
        if node.func.value.id not in ("logger", "_logger"):
            continue
        if node.func.attr not in ("error", "warning", "critical", "info", "exception", "debug"):
            continue

        if not has_exc_info_true(node):
            continue

        result["total_exc_info_true"] += 1

        in_except = is_in_except_handler(node, parent_map)
        in_try = find_enclosing_try(node, parent_map) is not None

        if in_except:
            result["in_except"] += 1
            context = "except"
        elif in_try:
            result["in_try_body"] += 1
            context = "try_body"
        else:
            result["no_try_ancestor"] += 1
            context = "NO_TRY_ANCESTOR"

        if context == "NO_TRY_ANCESTOR":
            result["details"].append({
                "line": node.lineno,
                "col": node.col_offset,
                "method": node.func.attr,
                "context": context,
                "source": ast.unparse(node),
            })

    return result


def main():
    total_stats = {
        "total_exc_info_true": 0,
        "in_except": 0,
        "in_try_body": 0,
        "no_try_ancestor": 0,
        "false_positive_count": 0,
    }
    by_file = {}
    false_positive_files = []

    for fp in TARGET_FILES:
        stats = analyze_file(fp)
        by_file[fp] = stats
        if "error" not in stats:
            total_stats["total_exc_info_true"] += stats["total_exc_info_true"]
            total_stats["in_except"] += stats["in_except"]
            total_stats["in_try_body"] += stats["in_try_body"]
            total_stats["no_try_ancestor"] += stats["no_try_ancestor"]
            if stats["no_try_ancestor"] > 0:
                total_stats["false_positive_count"] += stats["no_try_ancestor"]
                false_positive_files.append(fp)

    print("=" * 70)
    print("R181-D 误修核查: exc_info=True 调用上下文分析")
    print("=" * 70)
    print(f"总 exc_info=True 数: {total_stats['total_exc_info_true']}")
    print(f"  - 在 except 块内: {total_stats['in_except']}")
    print(f"  - 在 try 块主体内: {total_stats['in_try_body']}")
    print(f"  - [误修] 无 try 祖先: {total_stats['no_try_ancestor']}")
    print()
    print("按文件分布:")
    for fp, stats in by_file.items():
        if "error" in stats:
            print(f"  {fp}: {stats['error']}")
        else:
            flag = " ⚠️" if stats["no_try_ancestor"] > 0 else ""
            print(f"  {fp}: {stats['total_exc_info_true']} 处 (except={stats['in_except']}, try={stats['in_try_body']}, no_try={stats['no_try_ancestor']}){flag}")
    print()
    if false_positive_files:
        print("=" * 70)
        print(f"⚠️ 误修文件 ({len(false_positive_files)}):")
        for fp in false_positive_files:
            stats = by_file[fp]
            print(f"\n  {fp}:")
            for d in stats["details"]:
                print(f"    L{d['line']}: {d['source'][:80]}")
    else:
        print("=" * 70)
        print("✅ 无误修: 所有 exc_info=True 调用都在 try 或 except 块内")

    return 0 if total_stats["no_try_ancestor"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
