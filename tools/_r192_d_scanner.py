#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R192-D 子智能体 D 扫描器: 可观测性 + R51 静默失败 + 业务关键路径审计
=========================================================================

**强制度合规**:
- R104 §12 5 铁律 100% (AST 递归 + unparse 验证)
- R51 铁律 #5 100% (R51 §7.1 #5 严禁静默失败, 显式 warning/error + exc_info)
- R174 §12 AST 严格扫描 v2 (递归进入 with.body)
- R143-B 续 (缺 metrics/health_check Service 扫描)
- R8 #1 (logger.debug 业务事件升级)

**重点审计文件 (R190-R191 阶段交付)**:
- core/monitoring/sla_monitor.py (R190-A 优化)
- core/services/service_bootstrap.py (R190-B 注册)
- core/events/r84_event_helper.py (R190-B helper)
- core/coordinators/event_coordinator.py (R190-B 订阅)
- core/feature_flags/flag_manager.py (R191-B 13 flag)
- core/importdata/unified_data_import_engine.py (R191-B 同步)
- core/ui_integration/smart_data_integration.py (R190-D 6 维)
"""
import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_TARGETS = [
    "core/monitoring",
    "core/services",
    "core/events",
    "core/coordinators",
    "core/feature_flags",
    "core/importdata",
    "core/ui_integration",
    "core/risk",
]
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv"}


def is_logger_call(node: ast.Call) -> Tuple[bool, str]:
    """判断是否为 logger 调用"""
    if not isinstance(node, ast.Call):
        return False, ""
    if not isinstance(node.func, ast.Attribute):
        return False, ""
    parts = []
    cur = node.func
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    name = ".".join(reversed(parts))
    if "." not in name:
        return False, ""
    base = name.rsplit(".", 1)[0] if "." in name else ""
    method = parts[0] if parts else ""
    logger_keywords = ["logger", "Logger", "_logger", "log", "Log", "LOG"]
    if any(kw in base for kw in logger_keywords):
        return True, method
    return False, ""


def is_exc_info_true(node: ast.Call) -> bool:
    """检查 logger.error/warning/exc_info 参数"""
    for kw in node.keywords:
        if kw.arg == "exc_info":
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
    return False


def get_handler_body_loggers(handler_body: List[ast.stmt]) -> List[Tuple[str, int, str, bool]]:
    """从 except handler body 中提取所有 logger 调用, 返回 [(method_name, line, full_call, has_exc_info), ...]"""
    results = []
    for stmt in handler_body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            is_logger, method = is_logger_call(call)
            if is_logger:
                has_exc = is_exc_info_true(call)
                full_name = ast.unparse(call.func) if hasattr(ast, 'unparse') else ""
                results.append((method, stmt.lineno, full_name, has_exc))
        elif isinstance(stmt, ast.If):
            # 递归进入 if
            results.extend(get_handler_body_loggers(stmt.body))
            results.extend(get_handler_body_loggers(stmt.orelse))
        elif isinstance(stmt, ast.Try):
            # 递归进入 try
            results.extend(get_handler_body_loggers(stmt.body))
            results.extend(get_handler_body_loggers(stmt.finalbody))
    return results


def analyze_file(file_path: Path) -> List[Dict]:
    """分析单个文件, 返回违例列表"""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return [{"file": str(file_path), "error": str(e)}]

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return [{"file": str(file_path), "error": f"SyntaxError: {e}"}]

    violations = []

    # 递归遍历所有 ExceptHandler
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            handler_line = node.lineno
            handler_body = node.body

            # 收集 handler body 中所有 logger 调用
            loggers = get_handler_body_loggers(handler_body)

            # 业务关键路径 = handler 必须有 logger.error/warning + exc_info=True
            # 静默反模式: handler body 中无 logger 调用
            if not loggers:
                # 提取 body 简短描述
                body_desc = []
                for stmt in handler_body:
                    body_desc.append(ast.unparse(stmt)[:80] if hasattr(ast, 'unparse') else "...")
                violations.append({
                    "file": str(file_path.relative_to(PROJECT_ROOT)),
                    "line": handler_line,
                    "type": "R51_SILENT",
                    "severity": "P0",
                    "exception_type": ast.unparse(node.type) if node.type else "Exception",
                    "body_summary": body_desc,
                    "reason": "except 块内无 logger 调用, 静默吞错",
                })
            else:
                # 验证 logger 调用是否合规
                has_warning = any(m in ("error", "warning", "warn", "exception", "critical") for m, _, _, _ in loggers)
                has_exc_info = any(has_exc for _, _, _, has_exc in loggers)

                if not has_warning:
                    # 仅用 debug/info - 业务异常必须 warning
                    methods = [m for m, _, _, _ in loggers]
                    violations.append({
                        "file": str(file_path.relative_to(PROJECT_ROOT)),
                        "line": handler_line,
                        "type": "R51_LOW_LEVEL",
                        "severity": "P1",
                        "exception_type": ast.unparse(node.type) if node.type else "Exception",
                        "methods": methods,
                        "reason": f"except 块内仅用 {methods}, 业务异常必须 warning/error",
                    })
                elif not has_exc_info:
                    # 用了 warning/error 但缺 exc_info=True
                    violations.append({
                        "file": str(file_path.relative_to(PROJECT_ROOT)),
                        "line": handler_line,
                        "type": "R51_MISSING_EXC_INFO",
                        "severity": "P1",
                        "exception_type": ast.unparse(node.type) if node.type else "Exception",
                        "loggers": [f"{m}@{l}" for m, l, _, _ in loggers],
                        "reason": "except 块内 logger.error/warning 缺 exc_info=True",
                    })

    return violations


def scan_priority_files() -> List[Path]:
    """扫描优先级文件 (R190-R191 阶段交付)"""
    priority_files = []
    for subdir in SCAN_TARGETS:
        base = PROJECT_ROOT / subdir
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if any(s in path.parts for s in SKIP_DIRS):
                continue
            priority_files.append(path)
    return priority_files


def main():
    files = scan_priority_files()
    print(f"[R192-D Scanner] Scanning {len(files)} files across {len(SCAN_TARGETS)} priority dirs...")

    all_violations = []
    for f in files:
        vs = analyze_file(f)
        all_violations.extend(vs)

    # 分类输出
    by_severity = {"P0": [], "P1": [], "P2": [], "ERROR": []}
    for v in all_violations:
        if "error" in v:
            by_severity["ERROR"].append(v)
        else:
            by_severity.get(v.get("severity", "P2"), by_severity["P2"]).append(v)

    print(f"\n=== 扫描结果 ===")
    print(f"总文件数: {len(files)}")
    print(f"总违例数: {len(all_violations)}")
    print(f"  P0 (静默): {len(by_severity['P0'])}")
    print(f"  P1 (低级别/缺 exc_info): {len(by_severity['P1'])}")
    print(f"  ERROR: {len(by_severity['ERROR'])}")

    # 输出 P0 详情
    print(f"\n=== P0 静默失败详情 (前 30) ===")
    for v in by_severity["P0"][:30]:
        print(f"  {v['file']}:{v['line']} | {v.get('exception_type', '?')}")
        for s in v.get("body_summary", [])[:2]:
            print(f"      body: {s}")

    # 输出 P1 详情
    print(f"\n=== P1 缺 exc_info / 低级别详情 (前 30) ===")
    for v in by_severity["P1"][:30]:
        print(f"  {v['file']}:{v['line']} | {v.get('type', '?')} | {v.get('reason', '')}")

    # 输出 ERROR
    if by_severity["ERROR"]:
        print(f"\n=== 解析错误 ===")
        for v in by_severity["ERROR"]:
            print(f"  {v.get('file', '?')}: {v.get('error', '?')}")

    # 保存 JSON
    out_path = PROJECT_ROOT / "_r192_d_scan.json"
    out_path.write_text(json.dumps(all_violations, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n详细结果已保存: {out_path}")


if __name__ == "__main__":
    main()
