#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R181-D R+1 round 验证脚本: 4 源 100% 命中 (R104 §12 铁律 #1 + #4)

验证范围: 10 文件 Agent/Strategy exc_info 批量修复
验证方法: 4 源交叉验证 (AST 扫描 + Grep 跨子目录 + Read 关键行号 + 业务调用链)
"""
import ast
import importlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")
os.chdir(PROJECT_ROOT)


TARGET_FILES = [
    ("core/database/duckdb_manager.py", [184, 406, 408]),
    ("core/agents/fusion_engine.py", [198, 415, 491, 529, 586, 633]),
    ("core/agents/technical_agent.py", [212, 233, 318, 338, 408]),
    ("core/services/strategy_service.py", [320, 1057, 1217, 1458, 2206, 3263]),
    ("core/services/stock_service.py", []),
    ("core/services/asset_service.py", []),
    ("core/services/industry_service.py", []),
    ("core/services/chart_service.py", []),
    ("core/agents/news_agent.py", []),
    ("core/agents/sentiment_agent.py", []),
]


# === 源 1: AST 扫描器 v3 ===
def source_1_ast_scanner(file_path: str) -> Tuple[int, int, int]:
    """AST 扫描器 v3: 统计 P0/P1/P2 违规数"""
    if not Path(file_path).exists():
        return 0, 0, 0

    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return -1, -1, -1

    p0, p1, p2 = 0, 0, 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            for sub in ast.walk(node):
                if (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and isinstance(sub.func.value, ast.Name)
                    and sub.func.value.id in ("logger", "_logger")
                    and sub.func.attr in ("error", "warning", "critical", "info", "exception")
                ):
                    has_ei = any(
                        kw.arg == "exc_info"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                        for kw in sub.keywords
                    )
                    if not has_ei:
                        if sub.func.attr in ("error", "critical"):
                            p0 += 1
                        elif sub.func.attr == "warning":
                            p1 += 1
                        elif sub.func.attr in ("info", "exception"):
                            p2 += 1
                        # logger.debug 不计入 (R51 §7.1 #5 范围: error/warning/critical/info/exception)
    return p0, p1, p2


# === 源 2: Grep 跨子目录 ===
def source_2_grep_subdir(file_path: str) -> int:
    """统计文件内 exc_info=True 出现次数"""
    if not Path(file_path).exists():
        return 0
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return len(re.findall(r"exc_info=True", content))


# === 源 3: Read 关键行号 ===
def source_3_read_key_lines(file_path: str, key_lines: List[int]) -> Dict[int, bool]:
    """Read 关键行号, 验证是否含 exc_info=True (允许 ±5 行偏移)"""
    result = {}
    if not Path(file_path).exists() or not key_lines:
        return result

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line_no in key_lines:
        # 检查 ±5 行范围内
        found = False
        for offset in range(-5, 6):
            idx = line_no - 1 + offset
            if 0 <= idx < len(lines):
                if "exc_info=True" in lines[idx]:
                    found = True
                    break
        result[line_no] = found
    return result


# === 源 4: 业务调用链 (Import 验证) ===
def source_4_business_chain(module_name: str) -> bool:
    """Import 验证: 模块可正常加载, 业务链未断裂"""
    try:
        importlib.import_module(module_name)
        return True
    except Exception as e:
        print(f"    [IMPORT FAIL] {module_name}: {e}")
        return False


# === 综合验证 ===
def main():
    print("=" * 80)
    print("R181-D R+1 round 验证: 4 源 100% 命中 (R104 §12 铁律 #1 + #4)")
    print("=" * 80)
    print()

    all_results = {}
    for fp, key_lines in TARGET_FILES:
        print(f"--- {fp} ---")
        # 源 1: AST 扫描
        p0, p1, p2 = source_1_ast_scanner(fp)
        total = p0 + p1 + p2
        print(f"  源1 AST 扫描: P0={p0}, P1={p1}, P2={p2}, 总={total}")

        # 源 2: Grep
        grep_count = source_2_grep_subdir(fp)
        print(f"  源2 Grep: exc_info=True 出现 {grep_count} 次")

        # 源 3: Read 关键行号
        if key_lines:
            key_results = source_3_read_key_lines(fp, key_lines)
            all_hit = all(key_results.values())
            print(f"  源3 Read 关键行号 ({len(key_lines)}): {key_results}")
            print(f"  源3 总判定: {'✅ 全部命中' if all_hit else '❌ 有未命中'}")
        else:
            print(f"  源3 Read 关键行号: 0 (文件无 R180-B 报告行号)")

        # 源 4: Import 验证
        module_name = fp.replace("/", ".").replace(".py", "")
        import_ok = source_4_business_chain(module_name)
        print(f"  源4 Import: {'✅ 成功' if import_ok else '❌ 失败'}")

        # 综合判定
        all_pass = (total == 0) and (grep_count > 0) and (import_ok)
        if key_lines:
            all_pass = all_pass and all(key_results.values())
        print(f"  综合判定: {'✅ 4 源 100% 命中' if all_pass else '❌ 有偏差'}")
        print()

        all_results[fp] = {
            "ast": {"p0": p0, "p1": p1, "p2": p2, "total": total},
            "grep_count": grep_count,
            "key_lines_pass": all(key_results.values()) if key_lines else None,
            "import_ok": import_ok,
            "all_pass": all_pass,
        }

    # 总汇总
    print("=" * 80)
    print("R+1 round 总汇总")
    print("=" * 80)

    total_p0 = sum(r["ast"]["p0"] for r in all_results.values())
    total_p1 = sum(r["ast"]["p1"] for r in all_results.values())
    total_p2 = sum(r["ast"]["p2"] for r in all_results.values())
    total_exc = sum(r["grep_count"] for r in all_results.values())
    files_pass = sum(1 for r in all_results.values() if r["all_pass"])
    imports_pass = sum(1 for r in all_results.values() if r["import_ok"])

    print(f"  AST 扫描: P0={total_p0}, P1={total_p1}, P2={total_p2}")
    print(f"  Grep 总 exc_info=True: {total_exc} 处")
    print(f"  Import 验证: {imports_pass}/10 成功")
    print(f"  4 源全通过文件: {files_pass}/10")
    print()
    if files_pass == 10:
        print("=" * 80)
        print("✅ R+1 round 验证通过: 10 文件 4 源 100% 命中 (R104 §12 铁律 #1)")
        print("=" * 80)
        return 0
    else:
        print("=" * 80)
        print(f"❌ R+1 round 验证失败: {10 - files_pass} 文件未通过")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
