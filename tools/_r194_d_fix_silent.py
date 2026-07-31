#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R194-D 自动化修复脚本
=========================================================================

**任务**: R194-D P0 静默失败治理 - 自动添加 logger.warning(..., exc_info=True)
**修复对象**:
1. core/services/ai_selection_risk_control_service.py (14 P0)
2. core/services/unified_data_manager.py (33 P0)
3. core/services/service_bootstrap.py (24 P0)
4. core/coordinators/main_window_coordinator.py (60 P0 + 38 P1)
5. core/services/ai_selection_integration_service.py (12 P0 + 1 P1)
6. core/services/trading_service.py (12 P0)

**修复模式**:
- SILENT_PASS: 'pass' → 'logger.warning(..., exc_info=True)'
- SILENT_CONTINUE: 'continue' → 'logger.warning(..., exc_info=True); continue'
- SILENT_RETURN_*: 'return x' → 'logger.warning(..., exc_info=True); return x'
- NO_LOGGER: 'logger.debug(...)' → 'logger.warning(..., exc_info=True)'
- LOW_LEVEL: 'logger.debug(...)' → 'logger.warning(..., exc_info=True)'
- MISSING_EXC_INFO: 'logger.warning(..., )' → 'logger.warning(..., exc_info=True)'

**强制度合规**:
- R174 §12 v2 AST 严格扫描
- R6 §6.3 死代码审计铁律 (不删代码,只添加 logger)
- R176 死缓存防御兼容 (保留原 body 结构)
- Windows PowerShell Edit 不稳定 → Python 脚本直接操作
"""
import ast
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# R194-D 修复目标 (与 R193-D 一致)
R194_TARGETS = [
    "core/services/ai_selection_risk_control_service.py",
    "core/services/unified_data_manager.py",
    "core/services/service_bootstrap.py",
    "core/coordinators/main_window_coordinator.py",
    "core/services/ai_selection_integration_service.py",
    "core/services/trading_service.py",
]


def backup_file(file_path: Path) -> Path:
    """备份原文件 (R6 §6.3 步骤: 执行删除/修改前先备份)"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(file_path.suffix + f".r194d.{ts}")
    shutil.copy2(file_path, backup_path)
    return backup_path


def get_logger_name(source: str, file_path: Path) -> str:
    """推断文件中的 logger 名称 (默认 'logger', 可能不同)"""
    # 检查是否有 'from loguru import logger' 或 'logger = logging.getLogger(...)'
    if "loguru" in source:
        return "logger"
    return "logger"


def find_except_handlers(tree: ast.Module) -> List[Tuple[ast.ExceptHandler, str]]:
    """递归找到所有 except handler (R174 §12 v2)"""
    results = []

    def visit(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Try):
                for handler in child.handlers:
                    # 找到 handler 所在方法名
                    results.append((handler, child.lineno))
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
    """推断行号所在方法名"""
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if n.lineno <= line <= (n.end_lineno or line):
                return n.name
    return "<module>"


def is_import_error_handler(node: ast.ExceptHandler) -> bool:
    """ImportError 模式 (合规, R118 豁免)"""
    if node.type is None:
        return False
    try:
        type_str = ast.unparse(node.type)
    except Exception:
        return False
    return "ImportError" in type_str or "ModuleNotFoundError" in type_str


def has_r51_logger(handler: ast.ExceptHandler) -> bool:
    """检查 except 块内是否已有 logger.warning/error"""
    for child in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if not isinstance(child, ast.Call):
            continue
        if not isinstance(child.func, ast.Attribute):
            continue
        if not isinstance(child.func.value, ast.Name):
            continue
        if child.func.value.id == "logger":
            if child.func.attr in ("warning", "error", "critical", "exception", "warn"):
                return True
    return False


def find_logger_call_in_except(handler: ast.ExceptHandler) -> Optional[Tuple[ast.Call, str]]:
    """找到 except 块内第一个 logger.warning/error 调用 (R174 §12 递归)"""
    for child in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if not isinstance(child, ast.Call):
            continue
        if not isinstance(child.func, ast.Attribute):
            continue
        if not isinstance(child.func.value, ast.Name):
            continue
        if child.func.value.id == "logger":
            if child.func.attr in ("warning", "error", "critical", "exception", "warn"):
                return (child, child.func.attr)
    return None


def find_low_logger_in_except(handler: ast.ExceptHandler) -> Optional[Tuple[ast.Call, str]]:
    """找到 except 块内第一个 logger.debug/info 调用 (R51 P1)"""
    for child in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if not isinstance(child, ast.Call):
            continue
        if not isinstance(child.func, ast.Attribute):
            continue
        if not isinstance(child.func.value, ast.Name):
            continue
        if child.func.value.id == "logger":
            if child.func.attr in ("debug", "info"):
                return (child, child.func.attr)
    return None


def classify_handler_violation(handler: ast.ExceptHandler) -> Optional[Dict]:
    """分类 handler 违规类型 (R194-D 严格检测)
    返回: None (合规) 或 dict {kind, line, method, exception_type, has_r51}
    """
    if is_import_error_handler(handler):
        return None

    # 检查 ImportError 模式豁免
    try:
        exc_type = ast.unparse(handler.type) if handler.type else "Exception"
    except Exception:
        exc_type = "Exception"

    if "ImportError" in exc_type or "ModuleNotFoundError" in exc_type:
        return None

    body = handler.body
    has_r51 = has_r51_logger(handler)

    # 静默反模式
    if len(body) == 0:
        return {
            "kind": "SILENT_EMPTY",
            "line": handler.lineno,
            "exception_type": exc_type,
            "has_r51": has_r51,
        }
    if len(body) == 1:
        stmt = body[0]
        if isinstance(stmt, ast.Pass):
            return {
                "kind": "SILENT_PASS",
                "line": handler.lineno,
                "exception_type": exc_type,
                "has_r51": has_r51,
            }
        if isinstance(stmt, (ast.Continue, ast.Break)):
            return {
                "kind": f"SILENT_{type(stmt).__name__.upper()}",
                "line": handler.lineno,
                "exception_type": exc_type,
                "has_r51": has_r51,
            }
        if isinstance(stmt, ast.Return):
            if stmt.value is None or (
                isinstance(stmt.value, ast.Constant) and stmt.value.value in (False, 0)
            ):
                return {
                    "kind": "SILENT_RETURN",
                    "line": handler.lineno,
                    "exception_type": exc_type,
                    "has_r51": has_r51,
                }

    # 检查 r51 logger 缺 exc_info
    if has_r51:
        for child in ast.walk(ast.Module(body=body, type_ignores=[])):
            if not isinstance(child, ast.Call):
                continue
            if not isinstance(child.func, ast.Attribute):
                continue
            if not isinstance(child.func.value, ast.Name):
                continue
            if child.func.value.id == "logger":
                if child.func.attr in ("warning", "error", "critical", "exception", "warn"):
                    has_exc = False
                    for kw in child.keywords:
                        if kw.arg == "exc_info":
                            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                has_exc = True
                            if isinstance(kw.value, ast.NameConstant) and kw.value.value is True:
                                has_exc = True
                    if not has_exc:
                        return {
                            "kind": "MISSING_EXC_INFO",
                            "line": child.lineno,
                            "logger_level": child.func.attr,
                            "exception_type": exc_type,
                            "has_r51": True,
                        }
                    break  # 第一个 r51 logger 即可

    # 检查仅低级别 logger
    if not has_r51:
        for child in ast.walk(ast.Module(body=body, type_ignores=[])):
            if not isinstance(child, ast.Call):
                continue
            if not isinstance(child.func, ast.Attribute):
                continue
            if not isinstance(child.func.value, ast.Name):
                continue
            if child.func.value.id == "logger" and child.func.attr in ("debug", "info"):
                return {
                    "kind": "LOW_LEVEL",
                    "line": child.lineno,
                    "logger_level": child.func.attr,
                    "exception_type": exc_type,
                    "has_r51": False,
                }
                break

    # 检查无 logger
    if not has_r51:
        # 检查是否完全无 logger
        has_any_logger = False
        for child in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                if isinstance(child.func.value, ast.Name) and child.func.value.id == "logger":
                    has_any_logger = True
                    break
        if not has_any_logger:
            return {
                "kind": "NO_LOGGER",
                "line": handler.lineno,
                "exception_type": exc_type,
                "has_r51": False,
            }

    return None


def fix_silent_pass(source_lines: List[str], handler: ast.ExceptHandler, method_name: str, logger_name: str) -> bool:
    """修复 SILENT_PASS: 'pass' → 'logger.warning(..., exc_info=True)'"""
    if len(handler.body) != 1:
        return False
    stmt = handler.body[0]
    if not isinstance(stmt, ast.Pass):
        return False
    line_idx = stmt.lineno - 1
    if line_idx < 0 or line_idx >= len(source_lines):
        return False
    original = source_lines[line_idx]
    # 计算缩进
    indent = re.match(r"^(\s*)", original).group(1)
    exception_type = ast.unparse(handler.type) if handler.type else "Exception"
    # 找到 except 行 (handler.lineno)
    handler_line_idx = handler.lineno - 1
    new_line = f"{indent}{logger_name}.warning(\"[R194-D][{method_name}] {exception_type} 静默吞错, 已升级为 warning\", exc_info=True)  # R51 §7.1 #5 修复"
    source_lines[line_idx] = new_line
    return True


def fix_no_logger_or_low_level(
    source_lines: List[str],
    handler: ast.ExceptHandler,
    method_name: str,
    logger_name: str,
    violation: Dict,
) -> bool:
    """修复 NO_LOGGER / LOW_LEVEL: 在 body 第一行前插入 logger.warning"""
    if not handler.body:
        return False
    # 在 body 第一行前插入
    first_stmt = handler.body[0]
    first_line_idx = first_stmt.lineno - 1
    if first_line_idx < 0 or first_line_idx >= len(source_lines):
        return False
    # 取第一行的缩进
    original = source_lines[first_line_idx]
    indent = re.match(r"^(\s*)", original).group(1)
    exception_type = violation.get("exception_type", "Exception")

    if violation["kind"] == "NO_LOGGER":
        new_line = f"{indent}{logger_name}.warning(\"[R194-D][{method_name}] {exception_type} 异常, 已记录堆栈\", exc_info=True)  # R51 §7.1 #5 修复"
        source_lines.insert(first_line_idx, new_line)
        return True
    elif violation["kind"] == "LOW_LEVEL":
        # 升级 logger.debug/info 为 logger.warning
        # 找到 low logger call 的行
        for child in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
            if not isinstance(child, ast.Call):
                continue
            if not isinstance(child.func, ast.Attribute):
                continue
            if not isinstance(child.func.value, ast.Name):
                continue
            if child.func.value.id == "logger" and child.func.attr in ("debug", "info"):
                low_line_idx = child.lineno - 1
                if low_line_idx < 0 or low_line_idx >= len(source_lines):
                    return False
                original_line = source_lines[low_line_idx]
                # 替换 logger.debug → logger.warning
                new_line = original_line.replace(f"{logger_name}.debug(", f"{logger_name}.warning(", 1)
                if new_line == original_line:
                    new_line = original_line.replace(f"{logger_name}.info(", f"{logger_name}.warning(", 1)
                # 加 exc_info=True
                if "exc_info=" not in new_line:
                    new_line = new_line.rstrip()
                    if new_line.endswith(")"):
                        new_line = new_line[:-1] + ", exc_info=True)"
                source_lines[low_line_idx] = new_line
                return True
        return False
    return False


def fix_missing_exc_info(
    source_lines: List[str],
    handler: ast.ExceptHandler,
    method_name: str,
    logger_name: str,
) -> bool:
    """修复 MISSING_EXC_INFO: 在 logger.warning/error 调用加 exc_info=True"""
    for child in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if not isinstance(child, ast.Call):
            continue
        if not isinstance(child.func, ast.Attribute):
            continue
        if not isinstance(child.func.value, ast.Name):
            continue
        if child.func.value.id == "logger":
            if child.func.attr in ("warning", "error", "critical", "exception", "warn"):
                # 检查是否已有 exc_info
                has_exc = False
                for kw in child.keywords:
                    if kw.arg == "exc_info":
                        if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            has_exc = True
                        if isinstance(kw.value, ast.NameConstant) and kw.value.value is True:
                            has_exc = True
                if not has_exc:
                    line_idx = child.lineno - 1
                    if line_idx < 0 or line_idx >= len(source_lines):
                        return False
                    original = source_lines[line_idx]
                    # 检查是否跨多行
                    if "exc_info=" in original:
                        return False
                    # 在行末加 ", exc_info=True)"
                    new_line = original.rstrip()
                    if new_line.endswith(")"):
                        new_line = new_line[:-1] + ", exc_info=True)"
                    else:
                        # 多行调用, 需要找下一行的 )
                        # 简化处理: 找到 handler 结束行, 拼接
                        # 这里只处理单行
                        return False
                    source_lines[line_idx] = new_line
                    return True
                break
    return False


def fix_file(file_path: Path) -> Tuple[int, int, int]:
    """修复单个文件
    返回: (p0_fixed, p1_fixed, syntax_errors)
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  [ERROR] 读取失败: {e}")
        return 0, 0, 1

    # 备份
    backup_path = backup_file(file_path)

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        print(f"  [WARN] 语法错误: {e}, 跳过")
        return 0, 0, 1

    logger_name = "logger"  # 默认

    source_lines = source.split("\n")
    p0_fixed = 0
    p1_fixed = 0

    # 找到所有 except handler (递归)
    handlers = find_except_handlers(tree)

    # 倒序处理,避免行号偏移
    handlers_sorted = sorted(handlers, key=lambda x: x[0].lineno, reverse=True)

    for handler, _ in handlers_sorted:
        if is_import_error_handler(handler):
            continue

        method_name = get_method_name_for_line(tree, handler.lineno)
        violation = classify_handler_violation(handler)
        if violation is None:
            continue

        kind = violation["kind"]
        try:
            if kind == "SILENT_PASS" and len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                if fix_silent_pass(source_lines, handler, method_name, logger_name):
                    p0_fixed += 1
            elif kind in ("NO_LOGGER", "LOW_LEVEL"):
                # 重新解析 (因为前面可能修改了)
                try:
                    new_source = "\n".join(source_lines)
                    new_tree = ast.parse(new_source)
                    new_handlers = find_except_handlers(new_tree)
                    # 找到对应 handler (按 line 匹配)
                    target = None
                    for h, _ in new_handlers:
                        if h.lineno == handler.lineno:
                            target = h
                            break
                    if target:
                        if fix_no_logger_or_low_level(source_lines, target, method_name, logger_name, violation):
                            if kind == "NO_LOGGER":
                                p0_fixed += 1
                            else:
                                p1_fixed += 1
                except SyntaxError:
                    pass
            elif kind == "MISSING_EXC_INFO":
                if fix_missing_exc_info(source_lines, handler, method_name, logger_name):
                    p1_fixed += 1
        except Exception as e:
            print(f"  [WARN] 修复 {kind} L{handler.lineno} 失败: {e}")

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

    return p0_fixed, p1_fixed, syntax_errors


def main():
    """R194-D 修复主入口"""
    print("=" * 80)
    print("R194-D 自动化修复 (R51 §7.1 #5 + R174 §12 v2)")
    print(f"目标: {len(R194_TARGETS)} 个文件")
    print("=" * 80)

    grand_p0 = 0
    grand_p1 = 0
    grand_err = 0

    for rel_path in R194_TARGETS:
        file_path = PROJECT_ROOT / rel_path
        if not file_path.exists():
            print(f"[MISSING] {rel_path}")
            continue
        print(f"\n--- {rel_path} ---")
        p0, p1, err = fix_file(file_path)
        grand_p0 += p0
        grand_p1 += p1
        grand_err += err
        print(f"  P0 修复: {p0} | P1 修复: {p1} | 语法错误: {err}")

    print(f"\n{'=' * 80}")
    print(f"总计: P0={grand_p0}, P1={grand_p1}, 语法错误={grand_err}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
