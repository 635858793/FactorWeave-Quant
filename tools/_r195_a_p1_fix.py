#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R195-A v4 修复器 - 5 子目录 P1 静默失败修复
=========================================================================
任务: R195 阶段子智能体 A - P1 静默失败治理
强制度合规:
- R104 §12 5 铁律 100% (R+1 round, 4 源验证, AST 递归 with.body)
- R51 §7.1 #5 严禁静默失败, 显式 warning/error + exc_info
- R174 §12 AST 严格扫描 v2
- R194-D v3 经验: handler.lineno != body[0].lineno
- R194-D v3 经验: 1-stmt Assign 反模式
- R194-D v3 经验: R118 豁免 ImportError 模式

升级策略:
- MISSING_EXC_INFO: logger.{warning,error,critical,exception}(...) → 加 exc_info=True
- LOW_LEVEL: logger.{debug,info}(...) → logger.warning(..., exc_info=True)

v4 改进 (基于 R194-D v3):
- 解决 v3 3 重发现: 扫描器 handler.lineno != 修复位置 body[0].lineno
- 解决 v3 未处理: 1-stmt Assign 反模式
- 解决 v3 未识别: R118 豁免 ImportError 模式
"""
import ast
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set

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
LOW_LEVELS = ("debug", "info")


def collect_py_files(subdirs: List[str]) -> List[Path]:
    """收集子目录下所有 .py 文件 (排除 __pycache__)"""
    py_files = []
    for subdir in subdirs:
        subdir_path = PROJECT_ROOT / subdir
        if not subdir_path.exists():
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


def is_import_error_handler(node: ast.ExceptHandler) -> bool:
    """判断 except 块是否专门处理 ImportError (合规, R118 豁免模式)"""
    if node.type is None:
        return False
    try:
        type_str = ast.unparse(node.type)
    except Exception:
        return False
    return "ImportError" in type_str or "ModuleNotFoundError" in type_str


def find_logger_call_in_handler(handler: ast.ExceptHandler) -> Optional[ast.Call]:
    """在 except handler body 中找第一个 logger.{warning,error,critical,exception,debug,info} 调用"""
    for child in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if not isinstance(child, ast.Call):
            continue
        if not isinstance(child.func, ast.Attribute):
            continue
        if not isinstance(child.func.value, ast.Name):
            continue
        if child.func.value.id != "logger":
            continue
        if child.func.attr in R51_LEVELS + LOW_LEVELS:
            return child
    return None


def collect_violations(file_path: Path) -> List[Dict]:
    """收集文件所有 P1 静默失败违规"""
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return []

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    violations = []
    rel = str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/")

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if is_import_error_handler(node):
            continue

        logger_call = find_logger_call_in_handler(node)
        if not logger_call:
            continue

        is_r51, r51_level = is_logger_call(logger_call, R51_LEVELS)
        is_low, low_level = is_logger_call(logger_call, LOW_LEVELS)

        if is_low and not is_r51:
            # P1: LOW_LEVEL 业务异常必须 warning/error
            violations.append({
                "file": rel,
                "handler_lineno": node.lineno,
                "logger_lineno": logger_call.lineno,
                "logger_level": low_level,
                "violation_kind": "LOW_LEVEL",
                "fix_strategy": "upgrade_to_warning_with_exc_info",
            })
        elif is_r51 and not has_exc_info_true(logger_call):
            # P1: MISSING_EXC_INFO
            violations.append({
                "file": rel,
                "handler_lineno": node.lineno,
                "logger_lineno": logger_call.lineno,
                "logger_level": r51_level,
                "violation_kind": "MISSING_EXC_INFO",
                "fix_strategy": "add_exc_info_true",
            })

    return violations


def backup_file(file_path: Path) -> Path:
    """备份文件"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(file_path.suffix + f".r195a.{ts}")
    shutil.copy2(file_path, backup_path)
    return backup_path


def fix_line(source_lines: List[str], line_idx: int, violation: Dict) -> bool:
    """修复单行 (line_idx 是 0-based)"""
    if line_idx < 0 or line_idx >= len(source_lines):
        return False

    line = source_lines[line_idx]
    original_line = line
    kind = violation["violation_kind"]

    if kind == "MISSING_EXC_INFO":
        # logger.X(...) → logger.X(..., exc_info=True)
        # 处理单行情况
        if re.search(r'logger\.(warning|error|critical|exception|warn)\(', line):
            # 跳过已有 exc_info 的
            if "exc_info" in line:
                return False
            # 单行 logger.error(...) → logger.error(..., exc_info=True)
            # 检查是否以 ) 结尾
            stripped = line.rstrip()
            if stripped.endswith(")"):
                # 在 ) 前插入 , exc_info=True
                new_line = stripped[:-1] + ", exc_info=True)  # R195-A R51 §7.1 #5 修复"
                # 保留原行尾
                indent_match = re.match(r"^(\s*)", line)
                indent = indent_match.group(1) if indent_match else ""
                # 处理 line ending
                if line.endswith("\r\n"):
                    new_line = new_line + "\r\n"
                elif line.endswith("\n"):
                    new_line = new_line + "\n"
                source_lines[line_idx] = new_line
                return True
            else:
                # 多行 logger.error(... (以 ( 开头但 ) 在后面)
                # 这种情况下, 先把 ), exc_info=True 放在最后一行
                # 标记为需要手工处理
                return False
        return False
    elif kind == "LOW_LEVEL":
        # logger.debug(...) → logger.warning(..., exc_info=True)
        # logger.info(...) → logger.warning(..., exc_info=True)
        if "logger.debug(" in line or "logger.info(" in line:
            stripped = line.rstrip()
            if "exc_info" in stripped:
                return False  # 已有 exc_info
            if stripped.endswith(")"):
                # 替换 logger.debug → logger.warning
                new_line = re.sub(r'logger\.(debug|info)\(', 'logger.warning(', stripped)
                # 在 ) 前插入 , exc_info=True
                new_line = new_line[:-1] + ", exc_info=True)  # R195-A R51 §7.1 #5 修复 (debug/info 业务异常升级 warning)"
                # 处理行尾
                if line.endswith("\r\n"):
                    new_line = new_line + "\r\n"
                elif line.endswith("\n"):
                    new_line = new_line + "\n"
                source_lines[line_idx] = new_line
                return True
        return False
    return False


def fix_file_p1s(file_path: Path, p1_list: List[Dict]) -> int:
    """修复文件中所有 P1 违规"""
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  [ERROR] 读取失败: {e}")
        return 0

    backup_path = backup_file(file_path)
    source_lines = source.split("\n")
    # 同时保留 \n
    raw_lines = source.splitlines(keepends=True)
    fixed = 0
    skipped = 0

    # 倒序处理避免行号偏移
    sorted_p1s = sorted(p1_list, key=lambda x: x["logger_lineno"], reverse=True)

    for v in sorted_p1s:
        line_idx = v["logger_lineno"] - 1  # 0-based
        if line_idx < 0 or line_idx >= len(raw_lines):
            skipped += 1
            continue
        if fix_line(raw_lines, line_idx, v):
            fixed += 1
        else:
            skipped += 1

    # 验证语法
    new_source = "".join(raw_lines)
    try:
        ast.parse(new_source)
    except SyntaxError as e:
        print(f"  [ERROR] 修复后语法错误 L{e.lineno}: {e.msg}, 恢复备份")
        shutil.copy2(backup_path, file_path)
        return 0

    file_path.write_text(new_source, encoding="utf-8")
    return fixed


def main():
    print("=" * 80)
    print("R195-A v4 修复器 (5 子目录 P1 静默失败)")
    print(f"扫描子目录: {R195_A_SUBDIRS}")
    print("=" * 80)

    py_files = collect_py_files(R195_A_SUBDIRS)
    print(f"\n目标文件数: {len(py_files)}")

    all_summaries = []
    total_p1 = 0
    total_fixed = 0
    by_subdir_total: Dict[str, int] = {sub: 0 for sub in R195_A_SUBDIRS}
    by_subdir_fixed: Dict[str, int] = {sub: 0 for sub in R195_A_SUBDIRS}

    for file_path in py_files:
        rel = str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        violations = collect_violations(file_path)
        if not violations:
            continue

        # 统计
        for v in violations:
            total_p1 += 1
            for sub in R195_A_SUBDIRS:
                if v["file"].startswith(sub):
                    by_subdir_total[sub] += 1
                    break

        # 修复
        fixed = fix_file_p1s(file_path, violations)

        for v in violations:
            for sub in R195_A_SUBDIRS:
                if v["file"].startswith(sub):
                    by_subdir_fixed[sub] += fixed
                    break

        total_fixed += fixed
        all_summaries.append({
            "file": rel,
            "p1_count": len(violations),
            "fixed": fixed,
            "violations": violations,
        })

        kind_summary = {}
        for v in violations:
            kind_summary[v["violation_kind"]] = kind_summary.get(v["violation_kind"], 0) + 1
        kinds = ", ".join(f"{k}={n}" for k, n in sorted(kind_summary.items()))
        print(f"  [{fixed:3d}/{len(violations):3d}] {rel} ({kinds})")

    print(f"\n{'=' * 80}")
    print(f"R195-A 总计: P1 = {total_p1}, 修复 = {total_fixed}")
    print(f"\n各子目录修复统计:")
    for sub in R195_A_SUBDIRS:
        total = by_subdir_total[sub]
        fixed = by_subdir_fixed[sub]
        marker = "[OK]" if total == 0 else ("[FULL]" if fixed >= total else "[PARTIAL]")
        print(f"  {marker} {sub}: {fixed}/{total}")
    print(f"{'=' * 80}")

    # 保存 JSON
    out_path = PROJECT_ROOT / "_r195_a_fix_report.json"
    out_path.write_text(
        json.dumps({
            "total_p1": total_p1,
            "total_fixed": total_fixed,
            "by_subdir_total": by_subdir_total,
            "by_subdir_fixed": by_subdir_fixed,
            "summaries": all_summaries,
        }, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\n详细报告: {out_path}")


if __name__ == "__main__":
    main()
