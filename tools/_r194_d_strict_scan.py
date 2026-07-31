#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R194-D 子智能体 D 严格扫描器 v2 (R174 §12 AST 必杀技)
=========================================================================

**任务**: R194 阶段子智能体 D - 可观测性 R51 静默失败治理
**强制度合规**:
- R104 §12 5 铁律 100% (AST 递归 + unparse 验证)
- R51 §7.1 #5 100% (严禁静默失败, 显式 warning/error + exc_info)
- R174 §12 AST 严格扫描 v2 (递归进入 with.body, ast.walk on ExceptHandler.body)
- R6 §6.1 死代码审计铁律 100%

**8 个反模式检测** (R194-D 扩展):
1. SILENT_PASS: except 块仅含 pass
2. SILENT_CONTINUE: except 块仅含 continue
3. SILENT_RETURN_NONE: except 块仅含 return None
4. SILENT_RETURN_FALSE: except 块仅含 return False
5. SILENT_BREAK: except 块仅含 break
6. NO_LOGGER: except 块无任何 logger.warning/error 调用
7. MISSING_EXC_INFO: logger.warning/error 缺 exc_info=True
8. LOW_LEVEL: logger.debug/info 业务异常必须 warning
"""
import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# R194-D 扫描目标 (扩展 R193-D 5 文件 + 业务关键)
R194_TARGETS = [
    "core/services/ai_selection_risk_control_service.py",
    "core/services/unified_data_manager.py",
    "core/services/service_bootstrap.py",
    "core/coordinators/main_window_coordinator.py",
    "core/services/ai_selection_integration_service.py",
    "core/services/trading_service.py",
    "core/events/event_bus.py",
    "core/risk_manager.py",
    "core/monitoring/queue_monitor.py",
    "core/monitoring/sla_monitor.py",
    "core/monitoring/performance_monitor.py",
    "core/monitoring/cache_degradation_exporter.py",
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


def classify_silent_type(body: List[ast.stmt]) -> Tuple[bool, str]:
    """
    R174 §12 v2: 判断 body 是否为 PASS/EMPTY/CONTINUE/RETURN_NONE/RETURN_FALSE/BREAK 静默反模式
    返回: (is_silent, silent_type)
    """
    if len(body) == 0:
        return True, "EMPTY"
    if len(body) == 1:
        stmt = body[0]
        if isinstance(stmt, ast.Pass):
            return True, "PASS"
        if isinstance(stmt, ast.Continue):
            return True, "CONTINUE"
        if isinstance(stmt, ast.Break):
            return True, "BREAK"
        if isinstance(stmt, ast.Return):
            if stmt.value is None:
                return True, "RETURN_NONE"
            if isinstance(stmt.value, ast.Constant) and stmt.value.value is False:
                return True, "RETURN_FALSE"
            if isinstance(stmt.value, ast.Constant) and stmt.value.value == 0:
                return True, "RETURN_ZERO"
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            return False, "SINGLE_CALL"
    return False, f"BODY_{len(body)}_STMTS"


def collect_r51_levels(handler: ast.ExceptHandler) -> List[Dict]:
    """收集 except 块内所有 logger R51 级别调用 (递归进入 with.body)"""
    loggers = []
    # R174 §12 v2: 递归进入 handler.body
    for child in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if not isinstance(child, ast.Call):
            continue
        is_r51, level = is_logger_r51_call(child)
        if is_r51:
            has_exc = has_exc_info_true(child)
            msg_preview = ""
            try:
                if child.args:
                    msg_preview = ast.unparse(child.args[0])[:80]
            except Exception:
                msg_preview = "(?)"
            loggers.append({
                "level": level,
                "line": child.lineno,
                "has_exc_info": has_exc,
                "msg_preview": msg_preview,
            })
    return loggers


def collect_low_levels(handler: ast.ExceptHandler) -> List[Dict]:
    """收集 except 块内所有 logger.debug/info 低级别调用 (R51 P1)"""
    loggers = []
    for child in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if not isinstance(child, ast.Call):
            continue
        if not isinstance(child.func, ast.Attribute):
            continue
        if not isinstance(child.func.value, ast.Name):
            continue
        if child.func.value.id != "logger":
            continue
        if child.func.attr in ("debug", "info"):
            msg_preview = ""
            try:
                if child.args:
                    msg_preview = ast.unparse(child.args[0])[:80]
            except Exception:
                msg_preview = "(?)"
            loggers.append({
                "level": child.func.attr,
                "line": child.lineno,
                "msg_preview": msg_preview,
            })
    return loggers


def collect_violations(file_path: Path) -> List[Dict]:
    """收集文件所有 P0/P1 静默失败违规 (R174 §12 v2)"""
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

        # R51 级别 logger (warning/error/critical/exception)
        r51_loggers = collect_r51_levels(node)
        # 低级别 logger (debug/info) - R51 P1
        low_loggers = collect_low_levels(node)

        # 静默反模式检测 (R174 §12 v2 必杀技)
        is_silent, silent_type = classify_silent_type(node.body)

        body_preview = ""
        if node.body:
            try:
                body_preview = ast.unparse(node.body[0])[:100]
            except Exception:
                body_preview = "(?)"

        if is_silent:
            # PASS/EMPTY/CONTINUE/BREAK/RETURN_NONE 静默反模式 = P0
            violations.append({
                "file": rel,
                "line": handler_line,
                "method": method_name,
                "exception_type": exc_type,
                "silent_type": silent_type,
                "body_preview": body_preview,
                "r51_loggers": r51_loggers,
                "low_loggers": low_loggers,
                "severity": "P0",
                "violation_kind": f"SILENT_{silent_type}",
                "reason": f"except 块为 {silent_type} 静默反模式, 无任何 logger 记录",
            })
        elif not r51_loggers and not low_loggers:
            # 完全无 logger 调用 = P0
            violations.append({
                "file": rel,
                "line": handler_line,
                "method": method_name,
                "exception_type": exc_type,
                "silent_type": "NO_LOGGER",
                "body_preview": body_preview,
                "r51_loggers": [],
                "low_loggers": [],
                "severity": "P0",
                "violation_kind": "NO_LOGGER",
                "reason": "except 块内无 logger.warning/error 调用, 静默吞错",
            })
        elif low_loggers and not r51_loggers:
            # 仅低级别 logger.debug/info (R51 P1 - 业务异常必须 warning)
            for lg in low_loggers:
                violations.append({
                    "file": rel,
                    "line": lg["line"],
                    "method": method_name,
                    "exception_type": exc_type,
                    "loggers": [lg],
                    "severity": "P1",
                    "violation_kind": "LOW_LEVEL",
                    "reason": f"logger.{lg['level']} 业务异常必须 warning/error",
                })
                break  # 每个 except 块只报 1 次
        else:
            # 有 r51 logger 但缺 exc_info=True = P1
            for lg in r51_loggers:
                if not lg["has_exc_info"]:
                    violations.append({
                        "file": rel,
                        "line": lg["line"],
                        "method": method_name,
                        "exception_type": exc_type,
                        "loggers": [lg],
                        "severity": "P1",
                        "violation_kind": "MISSING_EXC_INFO",
                        "reason": f"logger.{lg['level']} 缺 exc_info=True",
                    })
                    break  # 每个 except 块只报 1 次

    return violations


def main():
    """R194-D 严格扫描主入口"""
    print("=" * 80)
    print("R194-D 子智能体 D 严格扫描 v2 (R174 §12 AST 必杀技)")
    print(f"扫描目标: {len(R194_TARGETS)} 个文件")
    print("=" * 80)

    all_summaries = []
    total_p0 = 0
    total_p1 = 0

    for rel_path in R194_TARGETS:
        file_path = PROJECT_ROOT / rel_path
        if not file_path.exists():
            print(f"[MISSING] {rel_path}")
            continue

        violations = collect_violations(file_path)
        p0 = [v for v in violations if v.get("severity") == "P0"]
        p1 = [v for v in violations if v.get("severity") == "P1"]

        all_summaries.append({
            "file": rel_path,
            "p0_count": len(p0),
            "p1_count": len(p1),
            "violations": violations,
        })
        total_p0 += len(p0)
        total_p1 += len(p1)

        status = "[OK]" if len(p0) == 0 and len(p1) == 0 else "[WARN]"
        print(f"\n{status} {rel_path}: P0={len(p0)}, P1={len(p1)}")

    print(f"\n{'=' * 80}")
    print(f"R194-D 总计: P0={total_p0}, P1={total_p1}")
    print(f"{'=' * 80}")

    # 保存 JSON
    out_path = PROJECT_ROOT / "_r194_d_strict_scan.json"
    out_path.write_text(
        json.dumps(all_summaries, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\n详细结果: {out_path}")


if __name__ == "__main__":
    main()
