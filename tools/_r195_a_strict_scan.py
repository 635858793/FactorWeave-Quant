#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R195-A v4 严格扫描器 - 5 子目录 P1 静默失败扫描
=========================================================================
任务: R195 阶段子智能体 A - P1 静默失败治理 (5 子目录 110 静默块)
强制度合规:
- R104 §12 5 铁律 100% (R+1 round, 4 源验证, AST 递归 with.body, 物理删除前 4 源, AST unparse)
- R51 §7.1 #5 严禁静默失败, 显式 warning/error + exc_info
- R174 §12 AST 严格扫描 v2 (递归进入 with.body, ast.walk on ExceptHandler.body)
- R194-D v3 经验: handler.lineno != body[0].lineno
- R194-D v3 经验: 1-stmt Assign 反模式 + R118 豁免 ImportError 模式

5 子目录扫描目标:
- core/optimization/    (HVD-194-A-4, 22 块 P1)
- core/ai/              (HVD-194-A-5, 18 块 P1)
- core/async_management/ (HVD-194-A-6, 12 块 P1)
- core/performance/     (HVD-194-A-7, 35 块 P1)
- core/data/            (HVD-194-A-8, 23 块 P1)
合计 110 块

升级策略: P1 (logger.debug/info + 缺 exc_info) → logger.warning + exc_info=True
"""
import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# 5 个目标子目录
R195_A_SUBDIRS = [
    "core/optimization",
    "core/ai",
    "core/async_management",
    "core/performance",
    "core/data",
]

# R51 合规 logger 级别
R51_LEVELS = ("warning", "error", "critical", "exception", "warn")

# P1 升级目标: low_level (debug/info) + missing_exc_info


def collect_py_files(subdirs: List[str]) -> List[Path]:
    """收集子目录下所有 .py 文件 (排除 __pycache__)"""
    py_files = []
    for subdir in subdirs:
        subdir_path = PROJECT_ROOT / subdir
        if not subdir_path.exists():
            print(f"[MISSING DIR] {subdir}")
            continue
        for py in subdir_path.rglob("*.py"):
            if "__pycache__" not in str(py):
                py_files.append(py)
    return sorted(py_files)


def is_logger_call(node: ast.Call, levels: Tuple[str, ...]) -> Tuple[bool, str]:
    """检查是否为 logger.<level> 调用"""
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
    """检查 logger 调用是否带 exc_info=True 关键字参数"""
    for kw in node.keywords:
        if kw.arg == "exc_info":
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
            if isinstance(kw.value, ast.NameConstant) and kw.value.value is True:
                return True
    return False


def get_method_name(node: ast.ExceptHandler, tree: ast.Module) -> str:
    """根据 ExceptHandler 的位置推断所在方法名"""
    handler_line = node.lineno
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if n.lineno <= handler_line <= (n.end_lineno or handler_line):
                return n.name
    return "<module>"


def is_import_error_handler(node: ast.ExceptHandler) -> bool:
    """判断 except 块是否专门处理 ImportError (合规, R118 豁免模式)"""
    if node.type is None:
        return False
    try:
        type_str = ast.unparse(node.type)
    except Exception:
        return False
    return "ImportError" in type_str or "ModuleNotFoundError" in type_str


def collect_loggers_in_handler(handler: ast.ExceptHandler) -> List[Dict]:
    """收集 except 块内所有 logger 调用 (递归进入 with.body)"""
    loggers = []
    for child in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if not isinstance(child, ast.Call):
            continue
        is_r51, r51_level = is_logger_call(child, R51_LEVELS)
        is_low, low_level = is_logger_call(child, ("debug", "info"))
        if is_r51 or is_low:
            level = r51_level or low_level
            is_r51_compliant = is_r51
            has_exc = has_exc_info_true(child) if is_r51 else False
            msg_preview = ""
            try:
                if child.args:
                    msg_preview = ast.unparse(child.args[0])[:100]
            except Exception:
                msg_preview = "(?)"
            loggers.append({
                "level": level,
                "is_r51": is_r51_compliant,
                "line": child.lineno,
                "has_exc_info": has_exc,
                "msg_preview": msg_preview,
            })
    return loggers


def collect_violations(file_path: Path) -> List[Dict]:
    """收集文件所有 P1 静默失败违规 (R174 §12 v2)"""
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return [{"file": str(file_path), "error": str(e)}]

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        return [{"file": str(file_path), "error": f"SyntaxError: {e}"}]

    violations = []
    rel = str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/")

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        # 排除 ImportError 模式 (合规, R118 豁免)
        if is_import_error_handler(node):
            continue

        handler_line = node.lineno
        method_name = get_method_name(node, tree)
        try:
            exc_type = ast.unparse(node.type) if node.type else "Exception"
        except Exception:
            exc_type = "Exception"

        # 收集所有 logger 调用
        all_loggers = collect_loggers_in_handler(node)

        if not all_loggers:
            continue  # P0 范畴 (R194-D 已处理, R195-A 只关注 P1)

        r51_loggers = [lg for lg in all_loggers if lg["is_r51"]]
        low_loggers = [lg for lg in all_loggers if not lg["is_r51"]]

        # P1 反模式 1: 仅低级别 logger (debug/info) - 业务异常必须 warning
        if low_loggers and not r51_loggers:
            for lg in low_loggers:
                violations.append({
                    "file": rel,
                    "line": lg["line"],
                    "method": method_name,
                    "exception_type": exc_type,
                    "logger_level": lg["level"],
                    "has_exc_info": False,
                    "msg_preview": lg["msg_preview"],
                    "severity": "P1",
                    "violation_kind": "LOW_LEVEL",
                    "reason": f"logger.{lg['level']} 业务异常必须 warning/error, 已记录堆栈",
                    "fix_strategy": "upgrade_to_warning_with_exc_info",
                })
                break  # 每个 except 块只报 1 次

        # P1 反模式 2: 有 r51 logger 但缺 exc_info=True
        for lg in r51_loggers:
            if not lg["has_exc_info"]:
                violations.append({
                    "file": rel,
                    "line": lg["line"],
                    "method": method_name,
                    "exception_type": exc_type,
                    "logger_level": lg["level"],
                    "has_exc_info": False,
                    "msg_preview": lg["msg_preview"],
                    "severity": "P1",
                    "violation_kind": "MISSING_EXC_INFO",
                    "reason": f"logger.{lg['level']} 缺 exc_info=True",
                    "fix_strategy": "add_exc_info_true",
                })
                break  # 每个 except 块只报 1 次

    return violations


def main():
    """R195-A 严格扫描主入口"""
    print("=" * 80)
    print("R195-A 子智能体 A 严格扫描 v4 (5 子目录 P1 静默失败)")
    print(f"扫描子目录: {R195_A_SUBDIRS}")
    print("=" * 80)

    py_files = collect_py_files(R195_A_SUBDIRS)
    print(f"\n扫描文件数: {len(py_files)}")

    all_summaries = []
    total_p1 = 0
    by_subdir: Dict[str, int] = {sub: 0 for sub in R195_A_SUBDIRS}

    for file_path in py_files:
        rel = str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        violations = collect_violations(file_path)
        p1 = [v for v in violations if v.get("severity") == "P1"]

        # 归属到子目录
        for v in p1:
            for sub in R195_A_SUBDIRS:
                if v["file"].startswith(sub):
                    by_subdir[sub] += 1
                    break

        all_summaries.append({
            "file": rel,
            "p1_count": len(p1),
            "violations": violations,
        })
        total_p1 += len(p1)

        if p1:
            print(f"[P1={len(p1):2d}] {rel}")
            for v in p1:
                print(f"        L{v['line']:5d} {v['method']:35s} {v['violation_kind']:20s} {v['logger_level']}")
        # else: print(f"[OK]   {rel}")

    print(f"\n{'=' * 80}")
    print(f"R195-A 总计: P1 = {total_p1}")
    print(f"\n各子目录 P1 统计:")
    for sub, cnt in by_subdir.items():
        marker = "[OK]" if cnt == 0 else "[P1]"
        print(f"  {marker} {sub}: {cnt}")
    print(f"{'=' * 80}")

    # 保存 JSON
    out_path = PROJECT_ROOT / "_r195_a_strict_scan.json"
    out_path.write_text(
        json.dumps({
            "total_p1": total_p1,
            "by_subdir": by_subdir,
            "summaries": all_summaries,
        }, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\n详细结果: {out_path}")
    return total_p1


if __name__ == "__main__":
    main()
