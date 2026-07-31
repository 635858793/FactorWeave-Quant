#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scan 3 uncovered subdirs for new HVD candidates (core/notification, core/integration, core/messaging)"""
import ast
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
CANDIDATE_SUBDIRS = ["core/notification", "core/integration", "core/messaging"]


def collect_py_files(subdirs: List[str]) -> List[Path]:
    py_files = []
    for subdir in subdirs:
        subdir_path = PROJECT_ROOT / subdir
        if not subdir_path.exists():
            print(f"  [NOT EXIST] {subdir}")
            continue
        for py in subdir_path.rglob("*.py"):
            if "__pycache__" not in str(py):
                py_files.append(py)
    return sorted(py_files)


def is_logger_call(node: ast.Call, levels: Tuple[str, ...]) -> Tuple[bool, str]:
    if not isinstance(node, ast.Call):
        return False, ""
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False, ""
    if not isinstance(func.value, ast.Name):
        return False, ""
    if func.value.id != "logger":
        return False, ""
    if func.attr not in levels:
        return False, ""
    return True, func.attr


def has_exc_info_true(node: ast.Call) -> bool:
    for kw in node.keywords:
        if kw.arg == "exc_info":
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
            if isinstance(kw.value, ast.NameConstant) and kw.value.value is True:
                return True
    return False


def is_import_error_handler(node: ast.ExceptHandler) -> bool:
    if node.type is None:
        return False
    try:
        type_str = ast.unparse(node.type)
    except Exception:
        return False
    return "ImportError" in type_str or "ModuleNotFoundError" in type_str


def scan_file_p1(file_path: Path) -> List[Dict]:
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception:
        return []
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if is_import_error_handler(node):
            continue
        # 找 logger 调用
        for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
            if not isinstance(child, ast.Call):
                continue
            is_r51, r51_level = is_logger_call(child, ("warning", "error", "critical", "exception", "warn"))
            is_low, low_level = is_logger_call(child, ("debug", "info"))
            if is_low and not is_r51:
                violations.append({"line": child.lineno, "kind": "LOW_LEVEL", "level": low_level})
            elif is_r51 and not has_exc_info_true(child):
                violations.append({"line": child.lineno, "kind": "MISSING_EXC_INFO", "level": r51_level})
    return violations


def main():
    print("=" * 80)
    print("R195-A 新 HVD 候选扫描 (3 子目录)")
    print("=" * 80)

    py_files = collect_py_files(CANDIDATE_SUBDIRS)
    print(f"\n扫描文件数: {len(py_files)}")

    by_subdir = {sub: 0 for sub in CANDIDATE_SUBDIRS}
    total = 0

    for f in py_files:
        rel = str(f.relative_to(PROJECT_ROOT)).replace("\\", "/")
        v = scan_file_p1(f)
        if v:
            print(f"\n  P1={len(v)} {rel}")
            for x in v:
                print(f"    L{x['line']} {x['kind']} {x['level']}")
            total += len(v)
            for sub in CANDIDATE_SUBDIRS:
                if rel.startswith(sub):
                    by_subdir[sub] += len(v)
                    break
        else:
            print(f"  [OK] {rel}")

    print(f"\n{'=' * 80}")
    print(f"Total P1: {total}")
    for sub, c in by_subdir.items():
        print(f"  {sub}: {c}")

    # Write to file
    out_path = PROJECT_ROOT / "_r195_a_new_hvd_scan.txt"
    with open(out_path, "w", encoding="utf-8") as fp:
        fp.write(f"Total P1: {total}\n")
        for sub, c in by_subdir.items():
            fp.write(f"  {sub}: {c}\n")
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
