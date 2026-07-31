#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R193-D 子智能体 D 严格扫描器 v2 (R174 §12 AST 必杀技复刻)
=========================================================================

**强制度合规**:
- R104 §12 5 铁律 100% (AST 递归 + unparse 验证)
- R51 §7.1 #5 100% (严禁静默失败, 显式 warning/error + exc_info)
- R174 §12 AST 严格扫描 v2 (递归进入 with.body, ast.walk on ExceptHandler.body)
- R176 死缓存防御兼容期保留 (修复时保留旧类属性/dict 默认值/dataclass 字段)

**5 个目标文件 (Top 5 Service P0 静默失败)**:
1. core/services/ai_selection_risk_control_service.py (15 P0)
2. core/services/unified_data_manager.py (13 P0)
3. core/services/service_bootstrap.py (13 P0)
4. core/coordinators/main_window_coordinator.py (10 P0)
5. core/services/ai_selection_integration_service.py (9 P0)
"""
import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# R193 Top 5 Service P0 静默失败目标文件
R193_TARGETS = [
    "core/services/ai_selection_risk_control_service.py",
    "core/services/unified_data_manager.py",
    "core/services/service_bootstrap.py",
    "core/coordinators/main_window_coordinator.py",
    "core/services/ai_selection_integration_service.py",
]

# R51 合规 logger 级别
R51_LEVELS = ("warning", "error", "critical", "exception", "warn")


def is_logger_r51_call(node: ast.Call) -> Tuple[bool, str]:
    """检查是否为 logger.warning/error/critical/exception 调用"""
    if not isinstance(node, ast.Call):
        return False, ""
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False, ""
    if not isinstance(func.value, ast.Name):
        return False, ""
    if func.value.id != "logger":
        return False, ""
    if func.attr not in R51_LEVELS:
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
    # 向上找最近的 FunctionDef
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if n.lineno <= handler_line <= (n.end_lineno or handler_line):
                return n.name
    return "<module>"


def is_import_error_handler(node: ast.ExceptHandler) -> bool:
    """判断 except 块是否专门处理 ImportError (合规)"""
    if node.type is None:
        return False
    type_str = ast.unparse(node.type)
    return "ImportError" in type_str or "ModuleNotFoundError" in type_str or "Optional" in type_str


def is_body_pass_empty(body: List[ast.stmt]) -> Tuple[bool, str]:
    """
    R174 §12 v2 必杀技: 判断 body 是否为 PASS/EMPTY
    - PASS: 只有 'pass' 关键字
    - 1-stmt: 单一 return False / return None / return 0 / continue / break
    """
    if len(body) == 0:
        return True, "EMPTY"
    if len(body) == 1:
        stmt = body[0]
        if isinstance(stmt, ast.Pass):
            return True, "PASS"
        if isinstance(stmt, ast.Return):
            if stmt.value is None:
                return True, "RETURN_NONE"
            if isinstance(stmt.value, ast.Constant) and stmt.value.value is False:
                return True, "RETURN_FALSE"
            if isinstance(stmt.value, ast.Constant) and stmt.value.value == 0:
                return True, "RETURN_ZERO"
        if isinstance(stmt, ast.Continue):
            return True, "CONTINUE"
        if isinstance(stmt, ast.Break):
            return True, "BREAK"
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            # 单调用
            return False, "SINGLE_CALL"
    return False, f"BODY_{len(body)}_STMTS"


def collect_violations(file_path: Path) -> List[Dict]:
    """
    收集所有 except 块内 P0 静默失败违规
    R174 §12 v2 必杀技: 递归进入 with.body + ast.walk on ExceptHandler.body
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return [{"file": str(file_path), "error": str(e)}]

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        return [{"file": str(file_path), "error": f"SyntaxError: {e}"}]

    violations = []
    rel = str(file_path.relative_to(PROJECT_ROOT))

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue

        # 排除 ImportError 模式 (合规)
        if is_import_error_handler(node):
            continue

        handler_line = node.lineno
        method_name = get_method_name(node, tree)
        exc_type = ast.unparse(node.type) if node.type else "Exception"

        # R174 §12: 递归遍历 ExceptHandler.body 内所有 logger 调用
        loggers = []
        for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
            if not isinstance(child, ast.Call):
                continue
            is_r51, level = is_logger_r51_call(child)
            if is_r51:
                has_exc = has_exc_info_true(child)
                loggers.append({
                    "level": level,
                    "line": child.lineno,
                    "has_exc_info": has_exc,
                    "msg_preview": ast.unparse(child.args[0])[:80] if child.args else "(no msg)"
                })

        # 业务关键路径判断
        # 1. body 为 PASS/EMPTY/1-stmt 静默反模式 -> P0
        is_silent, silent_type = is_body_pass_empty(node.body)

        if is_silent:
            # PASS/EMPTY 1-stmt 静默反模式 = P0
            body_preview = ast.unparse(node.body[0])[:100] if node.body else "<empty>"
            violations.append({
                "file": rel,
                "line": handler_line,
                "method": method_name,
                "exception_type": exc_type,
                "silent_type": silent_type,
                "body_preview": body_preview,
                "loggers": loggers,
                "severity": "P0",
                "violation_kind": "SILENT_BODY",
                "reason": f"except 块为 {silent_type} 静默反模式, 无任何 logger 记录"
            })
        elif not loggers:
            # 完全无 logger 调用 = P0
            body_preview = ast.unparse(node.body[0])[:100] if node.body else "<empty>"
            violations.append({
                "file": rel,
                "line": handler_line,
                "method": method_name,
                "exception_type": exc_type,
                "silent_type": "NO_LOGGER",
                "body_preview": body_preview,
                "loggers": [],
                "severity": "P0",
                "violation_kind": "NO_LOGGER",
                "reason": "except 块内无 logger.warning/error 调用, 静默吞错"
            })
        else:
            # 有 logger 但缺 exc_info=True = P1
            for lg in loggers:
                if not lg["has_exc_info"]:
                    violations.append({
                        "file": rel,
                        "line": lg["line"],
                        "method": method_name,
                        "exception_type": exc_type,
                        "loggers": [lg],
                        "severity": "P1",
                        "violation_kind": "MISSING_EXC_INFO",
                        "reason": f"logger.{lg['level']} 缺 exc_info=True"
                    })
                    break  # 每个 except 块只报 1 次

    return violations


def classify_business_critical(rel_path: str) -> bool:
    """
    区分业务关键路径 vs 业务非关键路径
    业务关键: event_bus / DB / service_bootstrap / risk / trading / coordinator
    业务非关键: 计算辅助 / 解析 / UI 子流程
    """
    critical_markers = [
        "service_bootstrap.py",
        "unified_data_manager.py",
        "main_window_coordinator.py",
        "ai_selection_risk_control_service.py",
        "ai_selection_integration_service.py",
    ]
    for marker in critical_markers:
        if marker in rel_path:
            return True
    return False


def main():
    print("=" * 80)
    print("R193-D 子智能体 D 严格扫描 v2: Top 5 Service P0 静默失败复扫")
    print("=" * 80)
    print()

    all_violations = []
    file_summaries = []

    for rel_path in R193_TARGETS:
        file_path = PROJECT_ROOT / rel_path
        if not file_path.exists():
            print(f"[MISSING] {rel_path}")
            continue

        violations = collect_violations(file_path)
        p0 = [v for v in violations if v.get("severity") == "P0"]
        p1 = [v for v in violations if v.get("severity") == "P1"]

        is_critical = classify_business_critical(rel_path)
        all_violations.extend(violations)
        file_summaries.append({
            "file": rel_path,
            "p0_count": len(p0),
            "p1_count": len(p1),
            "is_business_critical": is_critical,
            "violations": violations,
        })

        print(f"--- {rel_path} ---")
        print(f"  P0 静默失败: {len(p0)} | P1 缺 exc_info: {len(p1)} | 业务关键: {is_critical}")
        for v in p0:
            print(f"  P0  L{v['line']:5d}  {v['method']:35s} | {v.get('silent_type', 'NO_LOGGER'):15s} | {v.get('reason', '')[:60]}")
        for v in p1:
            print(f"  P1  L{v['line']:5d}  {v['method']:35s} | {v.get('violation_kind', '')[:25]} | {v.get('reason', '')[:50]}")
        print()

    print("=" * 80)
    total_p0 = sum(s["p0_count"] for s in file_summaries)
    total_p1 = sum(s["p1_count"] for s in file_summaries)
    print(f"总计: P0 静默失败 {total_p0} | P1 缺 exc_info {total_p1}")
    print(f"业务关键文件: {sum(1 for s in file_summaries if s['is_business_critical'])}/5")
    print("=" * 80)

    # 保存 JSON
    out_path = PROJECT_ROOT / "_r193_d_strict_scan.json"
    out_path.write_text(
        json.dumps(file_summaries, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8"
    )
    print(f"\n详细结果已保存: {out_path}")


if __name__ == "__main__":
    main()
