#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R194-D 改进修复脚本 v2
=========================================================================
处理剩余 P0:
- 嵌套 try 中的 PASS/CONTINUE/RETURN_*
- 多行 NO_LOGGER (在第一行前插入 logger.warning)
- RETURN_FALSE/RETURN_ZERO
"""
import ast
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

R194_TARGETS = [
    "core/services/ai_selection_risk_control_service.py",
    "core/services/unified_data_manager.py",
    "core/services/service_bootstrap.py",
    "core/coordinators/main_window_coordinator.py",
    "core/services/ai_selection_integration_service.py",
    "core/services/trading_service.py",
    "core/events/event_bus.py",
    "core/monitoring/queue_monitor.py",
    "core/monitoring/cache_degradation_exporter.py",
    "core/risk_manager.py",
]


def backup_file(file_path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(file_path.suffix + f".r194dv2.{ts}")
    shutil.copy2(file_path, backup_path)
    return backup_path


def find_all_except_handlers(tree: ast.Module) -> List[ast.ExceptHandler]:
    """递归找到所有 except handler (R174 §12 v2 - 全 AST 递归)"""
    results = []

    def visit(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Try):
                for handler in child.handlers:
                    results.append(handler)
                visit(child)
            elif isinstance(child, (
                ast.If, ast.For, ast.While, ast.With,
                ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                ast.Lambda,
            )):
                visit(child)

    visit(tree)
    return results


def get_method_name_for_line(tree: ast.Module, line: int) -> str:
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if n.lineno <= line <= (n.end_lineno or line):
                return n.name
    return "<module>"


def is_import_error_handler(node: ast.ExceptHandler) -> bool:
    if node.type is None:
        return False
    try:
        type_str = ast.unparse(node.type)
    except Exception:
        return False
    return "ImportError" in type_str or "ModuleNotFoundError" in type_str


def has_r51_logger(handler: ast.ExceptHandler) -> bool:
    for child in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if not isinstance(child, ast.Call):
            continue
        if not isinstance(child.func, ast.Attribute):
            continue
        if not isinstance(child.func.value, ast.Name):
            continue
        if child.func.value.id == "logger" and child.func.attr in ("warning", "error", "critical", "exception", "warn"):
            return True
    return False


def fix_any_silent(
    source_lines: List[str],
    handler: ast.ExceptHandler,
    method_name: str,
    logger_name: str,
) -> bool:
    """通用静默修复: 处理所有 1-stmt 静默反模式 + 多行 NO_LOGGER"""
    if is_import_error_handler(handler):
        return False

    # 已有 r51 logger, 不处理
    if has_r51_logger(handler):
        return False

    exception_type = "Exception"
    try:
        exception_type = ast.unparse(handler.type) if handler.type else "Exception"
    except Exception:
        pass

    # 1-stmt 静默
    if len(handler.body) == 1:
        stmt = handler.body[0]
        if isinstance(stmt, ast.Pass):
            line_idx = stmt.lineno - 1
            original = source_lines[line_idx]
            indent = re.match(r"^(\s*)", original).group(1)
            new_line = f"{indent}{logger_name}.warning(\"[R194-D][{method_name}] {exception_type} 静默吞错, 已升级为 warning\", exc_info=True)  # R51 §7.1 #5 修复"
            source_lines[line_idx] = new_line
            return True
        elif isinstance(stmt, ast.Continue):
            line_idx = stmt.lineno - 1
            original = source_lines[line_idx]
            indent = re.match(r"^(\s*)", original).group(1)
            new_line = f"{indent}{logger_name}.warning(\"[R194-D][{method_name}] {exception_type} continue 静默, 已升级为 warning\", exc_info=True)  # R51 §7.1 #5 修复; {original.lstrip()}"
            source_lines[line_idx] = new_line
            return True
        elif isinstance(stmt, ast.Break):
            line_idx = stmt.lineno - 1
            original = source_lines[line_idx]
            indent = re.match(r"^(\s*)", original).group(1)
            new_line = f"{indent}{logger_name}.warning(\"[R194-D][{method_name}] {exception_type} break 静默, 已升级为 warning\", exc_info=True)  # R51 §7.1 #5 修复; {original.lstrip()}"
            source_lines[line_idx] = new_line
            return True
        elif isinstance(stmt, ast.Return):
            line_idx = stmt.lineno - 1
            original = source_lines[line_idx]
            indent = re.match(r"^(\s*)", original).group(1)
            # return None / return False / return 0
            if stmt.value is None:
                ret_str = "None"
            elif isinstance(stmt.value, ast.Constant):
                ret_str = repr(stmt.value.value)
            else:
                ret_str = ast.unparse(stmt.value)
            new_line = f"{indent}{logger_name}.warning(\"[R194-D][{method_name}] {exception_type} 异常, 已记录堆栈\", exc_info=True)  # R51 §7.1 #5 修复\n{indent}return {ret_str}"
            source_lines[line_idx] = new_line
            return True

    # 多行 NO_LOGGER - 在第一行前插入
    if handler.body:
        first_stmt = handler.body[0]
        first_line_idx = first_stmt.lineno - 1
        if 0 <= first_line_idx < len(source_lines):
            original = source_lines[first_line_idx]
            indent = re.match(r"^(\s*)", original).group(1)
            new_line = f"{indent}{logger_name}.warning(\"[R194-D][{method_name}] {exception_type} 异常, 已记录堆栈\", exc_info=True)  # R51 §7.1 #5 修复"
            source_lines.insert(first_line_idx, new_line)
            return True

    return False


def fix_file(file_path: Path) -> Tuple[int, int, int]:
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  [ERROR] 读取失败: {e}")
        return 0, 0, 1

    backup_path = backup_file(file_path)

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        print(f"  [WARN] 语法错误: {e}, 跳过")
        return 0, 0, 1

    logger_name = "logger"
    source_lines = source.split("\n")
    p0_fixed = 0

    handlers = find_all_except_handlers(tree)
    # 倒序处理,避免行号偏移
    handlers_sorted = sorted(handlers, key=lambda h: h.lineno, reverse=True)

    for handler in handlers_sorted:
        if is_import_error_handler(handler):
            continue
        if has_r51_logger(handler):
            continue

        method_name = get_method_name_for_line(tree, handler.lineno)
        # 重新解析 (因为前面可能修改了)
        try:
            new_source = "\n".join(source_lines)
            new_tree = ast.parse(new_source)
            new_handlers = find_all_except_handlers(new_tree)
            target = None
            for h in new_handlers:
                if h.lineno == handler.lineno:
                    target = h
                    break
            if not target:
                continue
            if has_r51_logger(target):
                continue
            if fix_any_silent(source_lines, target, method_name, logger_name):
                p0_fixed += 1
        except SyntaxError:
            pass
        except Exception as e:
            print(f"  [WARN] 修复失败 L{handler.lineno}: {e}")

    # 验证语法
    new_source = "\n".join(source_lines)
    try:
        ast.parse(new_source)
        syntax_errors = 0
        file_path.write_text(new_source, encoding="utf-8")
    except SyntaxError as e:
        print(f"  [ERROR] 修复后语法错误: {e}, 恢复备份")
        shutil.copy2(backup_path, file_path)
        syntax_errors = 1

    return p0_fixed, 0, syntax_errors


def main():
    print("=" * 80)
    print("R194-D 改进修复 v2 (处理嵌套 + 多行 NO_LOGGER + RETURN_*)")
    print(f"目标: {len(R194_TARGETS)} 个文件")
    print("=" * 80)

    grand_p0 = 0
    grand_err = 0

    for rel_path in R194_TARGETS:
        file_path = PROJECT_ROOT / rel_path
        if not file_path.exists():
            print(f"[MISSING] {rel_path}")
            continue
        print(f"\n--- {rel_path} ---")
        p0, p1, err = fix_file(file_path)
        grand_p0 += p0
        grand_err += err
        print(f"  P0 修复: {p0} | 语法错误: {err}")

    print(f"\n{'=' * 80}")
    print(f"总计: P0={grand_p0}, 语法错误={grand_err}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
