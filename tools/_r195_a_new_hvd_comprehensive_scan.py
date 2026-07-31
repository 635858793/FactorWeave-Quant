#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scan all remaining core/ subdirs not in R195-A scope, identify new HVD candidates"""
import ast
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
R195_A_SUBDIRS = {"core/optimization", "core/ai", "core/async_management", "core/performance", "core/data"}
R194_D_SUBDIRS = {"core/services", "core/coordinators", "core/monitoring", "core/events"}
ALREADY_AUDITED = R195_A_SUBDIRS | R194_D_SUBDIRS

# 找 core/ 下所有子目录
def get_all_subdirs():
    subdirs = set()
    for item in (PROJECT_ROOT / "core").iterdir():
        if item.is_dir() and not item.name.startswith("__") and not item.name.startswith("."):
            rel = f"core/{item.name}"
            subdirs.add(rel)
    return subdirs


def collect_py_files(subdir: str) -> List[Path]:
    subdir_path = PROJECT_ROOT / subdir
    if not subdir_path.exists():
        return []
    return sorted([py for py in subdir_path.rglob("*.py") if "__pycache__" not in str(py)])


def is_logger_call(node, levels):
    if not isinstance(node, ast.Call):
        return False, ""
    if not isinstance(node.func, ast.Attribute):
        return False, ""
    if not isinstance(node.func.value, ast.Name):
        return False, ""
    if node.func.value.id != "logger":
        return False, ""
    if node.func.attr not in levels:
        return False, ""
    return True, node.func.attr


def has_exc_info_true(node):
    for kw in node.keywords:
        if kw.arg == "exc_info":
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
    return False


def is_import_error_handler(node):
    if node.type is None:
        return False
    try:
        return "ImportError" in ast.unparse(node.type) or "ModuleNotFoundError" in ast.unparse(node.type)
    except Exception:
        return False


def scan_file_all(file_path):
    """扫描文件的 P0 + P1 静默失败"""
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception:
        return {"p0": 0, "p1": 0, "total_except": 0}
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return {"p0": 0, "p1": 0, "total_except": 0}

    p0 = 0
    p1 = 0
    total_except = 0

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if is_import_error_handler(node):
            continue
        total_except += 1

        # 检查 PASS/CONTINUE/EMPTY
        if len(node.body) <= 1:
            stmt = node.body[0] if node.body else None
            if stmt is None or isinstance(stmt, (ast.Pass, ast.Continue, ast.Break)):
                # 检查是否有 logger 调用
                has_logger = False
                for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                    if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                        if isinstance(child.func.value, ast.Name) and child.func.value.id == "logger":
                            has_logger = True
                            break
                if not has_logger:
                    p0 += 1
                    continue

        # 检查 logger 级别
        has_r51 = False
        has_low = False
        missing_exc = False
        for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
            if not isinstance(child, ast.Call):
                continue
            is_r51, _ = is_logger_call(child, ("warning", "error", "critical", "exception", "warn"))
            is_low, _ = is_logger_call(child, ("debug", "info"))
            if is_r51:
                has_r51 = True
                if not has_exc_info_true(child):
                    missing_exc = True
            if is_low:
                has_low = True

        if has_low and not has_r51:
            p1 += 1
        elif has_r51 and missing_exc:
            p1 += 1

    return {"p0": p0, "p1": p1, "total_except": total_except}


def main():
    print("=" * 80)
    print("R195-A 新 HVD 候选扫描 (排除已审计 9 子目录)")
    print("=" * 80)

    all_subdirs = get_all_subdirs()
    candidates = all_subdirs - ALREADY_AUDITED
    print(f"\n全部子目录: {len(all_subdirs)}")
    print(f"已审计: {sorted(ALREADY_AUDITED)}")
    print(f"待审计: {sorted(candidates)}")

    results = []
    grand_p1 = 0

    for sub in sorted(candidates):
        py_files = collect_py_files(sub)
        if not py_files:
            continue
        sub_p0 = 0
        sub_p1 = 0
        sub_total = 0
        for f in py_files:
            r = scan_file_all(f)
            sub_p0 += r["p0"]
            sub_p1 += r["p1"]
            sub_total += r["total_except"]
        if sub_p1 > 0 or sub_p0 > 0:
            results.append((sub, len(py_files), sub_p0, sub_p1, sub_total))
        grand_p1 += sub_p1

    print(f"\n{'子目录':<40} {'文件':>5} {'P0':>4} {'P1':>4} {'except':>6}")
    print("-" * 70)
    for r in results:
        sub, n, p0, p1, t = r
        marker = "[NEW HVD]" if p1 > 0 else "[OK]"
        print(f"{marker} {sub:<37} {n:>5} {p0:>4} {p1:>4} {t:>6}")
    print(f"\nTotal new P1: {grand_p1}")

    out_path = PROJECT_ROOT / "_r195_a_new_hvd_candidates.txt"
    with open(out_path, "w", encoding="utf-8") as fp:
        fp.write(f"Total new P1: {grand_p1}\n")
        fp.write(f"{'Subdir':<40} {'Files':>5} {'P0':>4} {'P1':>4} {'except':>6}\n")
        fp.write("-" * 70 + "\n")
        for r in results:
            sub, n, p0, p1, t = r
            fp.write(f"{sub:<40} {n:>5} {p0:>4} {p1:>4} {t:>6}\n")
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
