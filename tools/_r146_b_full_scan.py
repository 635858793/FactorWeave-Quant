#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R146 子智能体 B: 全项目 except 缺 exc_info 扫描
验证 R143 D 报告 3431 处实测 + 实际当前状态
"""
import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

EXCLUDE_DIRS = {'__pycache__', '.git', '.idea', 'node_modules', 'venv', '.venv', '.pytest_cache', 'tests', '.codegraph'}


def scan_except_blocks(file_path: str) -> List[Tuple[int, str, bool]]:
    """扫描单个文件中所有 except 块

    Returns:
        [(line_no, exc_name, has_exc_info), ...]
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
    except Exception:
        return []

    results = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            line_no = node.lineno
            exc_name = node.name or ""
            has_exc_info = _has_exc_info_in_handler(node)
            results.append((line_no, exc_name, has_exc_info))

    return results


def _has_exc_info_in_handler(handler: ast.ExceptHandler) -> bool:
    """检测 except handler body 中是否含 exc_info=True (递归进入嵌套结构)"""
    return _recursive_check(handler.body)


def _recursive_check(body: List[ast.stmt]) -> bool:
    """递归检查 body 中是否含 exc_info=True (R104 §12 #3 嵌套检测)

    关键: 不能用 ast.walk 扁平化, 必须递归进入 with.body / try.body / if.body / for.body
    """
    for stmt in body:
        # logger.xxx(..., exc_info=True) 或 logger.exception(...)
        if _stmt_has_exc_info(stmt):
            return True
        # 递归: with 块
        if isinstance(stmt, ast.With):
            if _recursive_check(stmt.body):
                return True
        # 递归: try 块
        elif isinstance(stmt, ast.Try):
            if _recursive_check(stmt.body):
                return True
            for h in stmt.handlers:
                if _recursive_check(h.body):
                    return True
            if stmt.finalbody and _recursive_check(stmt.finalbody):
                return True
        # 递归: if
        elif isinstance(stmt, ast.If):
            if _recursive_check(stmt.body):
                return True
            if _recursive_check(stmt.orelse):
                return True
        # 递归: for/while
        elif isinstance(stmt, (ast.For, ast.While)):
            if _recursive_check(stmt.body):
                return True
            if _recursive_check(stmt.orelse):
                return True
    return False


def _stmt_has_exc_info(stmt: ast.stmt) -> bool:
    """检查单个 statement (含嵌套子语句) 是否含 exc_info=True"""
    for node in ast.walk(stmt):
        if isinstance(node, ast.Call):
            # logger.exception(...) 自动带 exc_info
            if isinstance(node.func, ast.Attribute) and node.func.attr == "exception":
                return True
            # logger.xxx(..., exc_info=True)
            for kw in node.keywords:
                if kw.arg == "exc_info":
                    if isinstance(kw.value, ast.Constant):
                        if kw.value.value is True:
                            return True
                    elif isinstance(kw.value, ast.NameConstant):  # Python 3.7 compat
                        if kw.value.value is True:
                            return True
    return False


def scan_directory(root_dir: str) -> Dict:
    """扫描目录下所有 .py 文件"""
    total_files = 0
    total_except = 0
    total_with_exc_info = 0
    total_without_exc_info = 0
    file_results = []
    unfixed_examples = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # 过滤
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith('.')]

        for filename in filenames:
            if not filename.endswith('.py'):
                continue
            file_path = os.path.join(dirpath, filename)
            total_files += 1
            blocks = scan_except_blocks(file_path)
            if not blocks:
                continue
            total_except += len(blocks)
            with_ei = sum(1 for b in blocks if b[2])
            without_ei = len(blocks) - with_ei
            total_with_exc_info += with_ei
            total_without_exc_info += without_ei
            if without_ei > 0:
                rel_path = os.path.relpath(file_path, root_dir)
                file_results.append({
                    "file": rel_path,
                    "total": len(blocks),
                    "with_ei": with_ei,
                    "without_ei": without_ei,
                })
                if len(unfixed_examples) < 20:
                    unfixed_examples.append((rel_path, [b[0] for b in blocks if not b[2]][:5]))

    return {
        "total_files": total_files,
        "total_except_blocks": total_except,
        "total_with_exc_info": total_with_exc_info,
        "total_without_exc_info": total_without_exc_info,
        "exc_info_ratio": f"{total_with_exc_info / max(1, total_except) * 100:.1f}%",
        "files_with_unfixed": len(file_results),
        "file_results": sorted(file_results, key=lambda x: -x['without_ei']),
        "unfixed_examples": unfixed_examples,
    }


def main():
    target_dirs = [("core", "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core")]
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("R146 B 全项目 except 缺 exc_info 扫描 (排除 tests/)")
    output_lines.append("=" * 80)
    for d, path in target_dirs:
        if not os.path.exists(path):
            continue
        output_lines.append(f"\n>>> Scanning {d}/ ...")
        result = scan_directory(path)
        output_lines.append(f"  Files: {result['total_files']}")
        output_lines.append(f"  Total except: {result['total_except_blocks']}")
        output_lines.append(f"  With exc_info: {result['total_with_exc_info']}")
        output_lines.append(f"  Without exc_info: {result['total_without_exc_info']}")
        output_lines.append(f"  Ratio: {result['exc_info_ratio']}")
        output_lines.append(f"  Files with unfixed: {result['files_with_unfixed']}")
        output_lines.append(f"  Top 30 files by unfixed count:")
        for f in result['file_results'][:30]:
            output_lines.append(f"    {f['without_ei']:4d} / {f['total']:4d}  {f['file']}")
    out = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/_r146_b_full_scan_output.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"Output: {out}")


if __name__ == "__main__":
    main()
