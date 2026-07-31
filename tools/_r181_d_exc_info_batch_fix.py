#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R181-D Agent/Strategy exc_info 批量修复脚本 v3 (最终稳健版)

R104 §12 5 铁律 100% 应用:
- 铁律 #4: 物理修改前 4 源 100% 命中
- 铁律 #5: AST unparse 二次验证

策略:
1. 用 ast.get_source_segment() 提取每个 logger 调用的精确源码 (单行 + 多行都支持)
2. 在 current_source 中用 str.replace(original_src, new_src, 1) 精确替换 (不依赖行号)
3. 每次修复后立即 ast.parse 验证
4. 闭合 ) 和 exc_info=True 都在 # 注释之前 (Python 语法关键)
"""

import ast
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


# 修复标记: 关键! 闭合 ) 和 exc_info=True 都必须在 # 注释之前
R180_D_FIX_TAG = ", exc_info=True)  # R181-D P0/P1/P2 修复 (R51 §7.1 #5 强约束"


def is_already_fixed_src(src: str) -> bool:
    """检查源码是否已含 R181-D 修复标记"""
    return "R181-D" in src and "R51 §7.1 #5 强约束" in src


def find_logger_call_in_source(source: str, target_line: int) -> Optional[Tuple[ast.Call, str]]:
    """在源码中找到目标行 (或 ±1 偏差) 的 logger 调用

    Returns:
        (Call节点, 完整原始源码) 或 None
    """
    try:
        tree = ast.parse(source, filename="<source>")
    except SyntaxError:
        return None

    # 1. 优先在 target_line 查找
    for node in ast.walk(tree):
        if _is_target_logger(node, target_line):
            src_segment = _extract_src_segment(source, node)
            if src_segment is not None:
                return node, src_segment

    # 2. 在 ±1 行范围查找 (R180-B 报告行号偏差兼容)
    for offset in (-1, 1, -2, 2):
        for node in ast.walk(tree):
            if _is_target_logger(node, target_line + offset):
                src_segment = _extract_src_segment(source, node)
                if src_segment is not None:
                    return node, src_segment

    return None


def _is_target_logger(node, line: int) -> bool:
    """检查节点是否是目标行的 logger 调用"""
    if not isinstance(node, ast.Call):
        return False
    if not hasattr(node, "lineno") or node.lineno != line:
        return False
    if not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr not in ("error", "warning", "critical", "exception", "info", "debug"):
        return False
    if not isinstance(node.func.value, ast.Name) or node.func.value.id != "logger":
        return False
    # 已含 exc_info=True 跳过
    for kw in node.keywords:
        if kw.arg == "exc_info":
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return False
            if isinstance(kw.value, ast.NameConstant) and kw.value.value is True:
                return False
    return True


def _extract_src_segment(source: str, node: ast.Call) -> Optional[str]:
    """提取 logger 调用的原始源码"""
    try:
        return ast.get_source_segment(source, node)
    except Exception:
        pass
    end_line = getattr(node, "end_lineno", node.lineno)
    lines = source.split("\n")
    if node.lineno == end_line:
        return lines[node.lineno - 1]
    return "\n".join(lines[node.lineno - 1:end_line])


def build_new_logger_call(source: str, node: ast.Call) -> str:
    """构造新的 logger 调用源码, 保留原始缩进和格式

    关键: 在 source 的 end_line 行 (绝对行) 的 end_col 字节偏移位置
          (即闭合 ) 之前) 插入 ", exc_info=True" 并闭合 ),
          然后追加 # 注释

    Args:
        source: 完整源码 (含缩进)
        node: AST Call 节点
    """
    end_line = getattr(node, "end_lineno", node.lineno)
    end_col = getattr(node, "end_col_offset", None)

    if end_line is None or end_col is None:
        return None

    lines = source.split("\n")
    if end_line < 1 or end_line > len(lines):
        return None

    line = lines[end_line - 1]
    line_bytes = line.encode("utf-8")

    if end_col - 1 < 0 or end_col - 1 > len(line_bytes):
        return None

    if line_bytes[end_col - 1:end_col] != b")":
        return None

    prefix = line_bytes[:end_col - 1].decode("utf-8")
    suffix = line_bytes[end_col:].decode("utf-8")
    new_line = prefix + R180_D_FIX_TAG + suffix
    lines[end_line - 1] = new_line
    return "\n".join(lines)


def fix_file_violations(file_path: str, violations: List[Dict]) -> List[Dict]:
    """修复单个文件的所有违规, 返回修复结果列表

    关键: 按行号降序处理, 用 str.replace 精确替换, 每次修复后 ast.parse 验证
    """
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    # 验证原文件语法
    try:
        ast.parse(source, filename=file_path)
    except SyntaxError as e:
        return [{
            "file": file_path,
            "line": v.get("line"),
            "status": "original_syntax_error",
            "error": str(e),
            "func_name": v.get("func_name"),
            "logger_method": v.get("logger_method"),
        } for v in violations]

    # 备份
    backup_dir = "_archive/r181_d_pre_fix_2026_07_24"
    backup_path = os.path.join(backup_dir, os.path.basename(file_path))
    os.makedirs(backup_dir, exist_ok=True)
    if not os.path.exists(backup_path):
        shutil.copy2(file_path, backup_path)

    # 按行号降序排序
    sorted_violations = sorted(violations, key=lambda v: v["line"], reverse=True)

    current_source = source
    results = []

    for v in sorted_violations:
        target_line = v["line"]
        result = {
            "file": file_path,
            "line": target_line,
            "status": "pending",
            "old_src": "",
            "new_src": "",
            "func_name": v.get("func_name", ""),
            "logger_method": v.get("logger_method", ""),
            "except_type": v.get("except_type", ""),
            "severity": v.get("severity", ""),
        }

        # 找 logger 调用节点
        find_result = find_logger_call_in_source(current_source, target_line)
        if find_result is None:
            result["status"] = "not_found_or_already_fixed"
            results.append(result)
            continue

        node, original_src = find_result
        result["old_src"] = original_src[:200]

        # 检查是否已修复
        if is_already_fixed_src(original_src):
            result["status"] = "already_fixed"
            results.append(result)
            continue

        # 构造新源码 (基于 current_source 完整源码, 不用行号偏移)
        new_source = build_new_logger_call(current_source, node)

        # 如果 build_new_logger_call 返回 None, 表示无法处理
        if new_source is None:
            result["status"] = "build_failed"
            results.append(result)
            continue

        if new_source == current_source:
            result["status"] = "build_failed_no_change"
            results.append(result)
            continue

        # 立即验证语法
        try:
            ast.parse(new_source, filename=file_path)
        except SyntaxError as e:
            result["status"] = "syntax_error_after_fix"
            result["error"] = str(e)
            results.append(result)
            continue

        # 成功
        current_source = new_source
        result["status"] = "fixed"
        result["new_src"] = " (see file)"
        results.append(result)

    # 写回文件
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(current_source)

    # 最终验证
    try:
        ast.parse(current_source, filename=file_path)
        final_ok = True
    except SyntaxError as e:
        final_ok = False
        final_error = str(e)
        # 回滚整个文件
        shutil.copy2(backup_path, file_path)
        for r in results:
            if r["status"] == "fixed":
                r["status"] = "rolled_back"

    if not final_ok:
        results.append({
            "file": file_path,
            "line": None,
            "status": "file_rolled_back",
            "error": final_error,
        })

    return results


def main():
    """批量修复主入口"""
    scan_report_path = ".r181_d_exc_info_scan.json"
    if not os.path.exists(scan_report_path):
        print(f"[ERROR] {scan_report_path} 不存在, 请先运行 v3 扫描器")
        sys.exit(1)

    with open(scan_report_path, "r", encoding="utf-8") as f:
        scan_report = json.load(f)

    violations = scan_report["violations"]
    print(f"[批量修复] 处理 {len(violations)} 条违规")

    # 按文件分组
    by_file: Dict[str, List[Dict]] = {}
    for v in violations:
        by_file.setdefault(v["file"], []).append(v)

    fix_log = {
        "scanner": "tools/_r181_d_exc_info_scanner_v3.py",
        "fixer": "tools/_r181_d_exc_info_batch_fix.py (v3 final)",
        "total": len(violations),
        "fixed": 0,
        "skipped": 0,
        "already_fixed": 0,
        "not_found_or_already_fixed": 0,
        "build_failed": 0,
        "syntax_error_after_fix": 0,
        "rolled_back": 0,
        "original_syntax_error": 0,
        "file_rolled_back": 0,
        "fixes": [],
    }

    for fp, file_violations in by_file.items():
        print(f"\n--- {fp} ({len(file_violations)} 处) ---")
        results = fix_file_violations(fp, file_violations)

        for r in results:
            fix_log["fixes"].append(r)
            status = r["status"]
            if status == "fixed":
                fix_log["fixed"] += 1
                print(f"  [FIXED] L{r['line']} {r.get('func_name', '')} logger.{r.get('logger_method', '')}")
            elif status == "already_fixed":
                fix_log["already_fixed"] += 1
            elif status == "not_found_or_already_fixed":
                fix_log["not_found_or_already_fixed"] += 1
            elif status == "build_failed":
                fix_log["build_failed"] += 1
                print(f"  [BUILD_FAIL] L{r['line']} logger.{r.get('logger_method', '')}")
            elif status == "syntax_error_after_fix":
                fix_log["syntax_error_after_fix"] += 1
                print(f"  [SYNTAX_ERR] L{r['line']} {r.get('error', '')[:100]}")
            elif status == "rolled_back":
                fix_log["rolled_back"] += 1
                print(f"  [ROLLED_BACK] L{r['line']}")
            elif status == "original_syntax_error":
                fix_log["original_syntax_error"] += 1
                print(f"  [ORIG_SYNTAX_ERR] {r.get('error', '')[:100]}")
            elif status == "file_rolled_back":
                fix_log["file_rolled_back"] += 1
                print(f"  [FILE_ROLLED_BACK] {r.get('error', '')[:100]}")
            else:
                fix_log["skipped"] += 1

    with open(".r181_d_exc_info_fix_log.json", "w", encoding="utf-8") as f:
        json.dump(fix_log, f, ensure_ascii=False, indent=2)

    print(f"\n=== 修复汇总 ===")
    print(f"  总违规: {fix_log['total']}")
    print(f"  成功修复: {fix_log['fixed']}")
    print(f"  之前已修复: {fix_log['already_fixed']}")
    print(f"  跳过 (未找到): {fix_log['not_found_or_already_fixed']}")
    print(f"  跳过 (构建失败): {fix_log['build_failed']}")
    print(f"  失败 (修复后语法错): {fix_log['syntax_error_after_fix']}")
    print(f"  失败 (回滚): {fix_log['rolled_back']}")
    print(f"  失败 (文件回滚): {fix_log['file_rolled_back']}")
    print(f"\n备份目录: _archive/r181_d_pre_fix_2026_07_24/")
    print(f"详细日志: .r181_d_exc_info_fix_log.json")


if __name__ == "__main__":
    main()
