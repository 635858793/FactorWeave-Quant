#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R195-A v5 修复器 - 多行 logger 调用 P1 修复
=========================================================================
针对 v4 修复器无法处理的多行 logger.{warning,error,debug,info}(...) 调用
"""
import ast
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# 11 个剩余多行 P1 修复目标 (去重: 同位置只修复一次)
R195_A_REMAINING_P1 = [
    ("core/ai/config_recommendation_engine.py", 768, "LOW_LEVEL"),
    ("core/ai/continuous_learning_manager.py", 679, "MISSING_EXC_INFO"),
    ("core/ai/intelligent_selection/intelligent_selector.py", 379, "MISSING_EXC_INFO"),
    ("core/async_management/enhanced_async_manager.py", 775, "MISSING_EXC_INFO"),
    ("core/async_management/enhanced_async_manager.py", 848, "MISSING_EXC_INFO"),
    ("core/async_management/enhanced_async_manager.py", 674, "MISSING_EXC_INFO"),
    ("core/async_management/safe_async_runner.py", 328, "MISSING_EXC_INFO"),
    ("core/async_management/safe_async_runner.py", 234, "MISSING_EXC_INFO"),
    ("core/performance/factorweave_performance_integration.py", 460, "MISSING_EXC_INFO"),
    ("core/performance/unified_monitor.py", 973, "MISSING_EXC_INFO"),
]


def backup_file(file_path: Path) -> Path:
    """备份文件"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(file_path.suffix + f".r195av5.{ts}")
    shutil.copy2(file_path, backup_path)
    return backup_path


def find_logger_call_end(source: str, logger_lineno: int) -> Optional[Tuple[int, int]]:
    """
    找到 logger.X( 调用的结束位置 (返回 (行号, 字符位置))
    logger_lineno 是 1-based
    """
    lines = source.split("\n")
    if logger_lineno < 1 or logger_lineno > len(lines):
        return None
    start_line = logger_lineno - 1
    start_line_content = lines[start_line]
    # 找 logger.X(
    m = re.search(r'logger\.(warning|error|debug|info|critical|exception|warn)\(', start_line_content)
    if not m:
        return None
    paren_pos = m.end() - 1  # ( 的位置
    paren_depth = 1
    current_line = start_line
    current_pos = paren_pos + 1
    while current_line < len(lines):
        line = lines[current_line]
        while current_pos < len(line):
            ch = line[current_pos]
            if ch == '(':
                paren_depth += 1
            elif ch == ')':
                paren_depth -= 1
                if paren_depth == 0:
                    return (current_line + 1, current_pos)  # 1-based
            current_pos += 1
        current_line += 1
        current_pos = 0
    return None


def fix_multiline_logger(file_path: Path, logger_lineno: int, kind: str) -> bool:
    """
    修复多行 logger 调用:
    - MISSING_EXC_INFO: 在 ) 前插入 , exc_info=True
    - LOW_LEVEL: logger.{debug,info} → logger.warning, 在 ) 前插入 , exc_info=True
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception:
        return False

    # 找 logger 调用结束位置
    end_pos = find_logger_call_end(source, logger_lineno)
    if not end_pos:
        return False
    end_line, end_col = end_pos
    end_line_idx = end_line - 1  # 0-based

    lines = source.split("\n")
    end_line_content = lines[end_line_idx]

    # 提取缩进
    indent_match = re.match(r"^(\s*)", end_line_content)
    indent = indent_match.group(1) if indent_match else ""

    # 找到 ) 的位置
    close_paren_idx = end_col
    if close_paren_idx >= len(end_line_content) or end_line_content[close_paren_idx] != ')':
        return False

    # 在 ) 前插入 , exc_info=True
    # 但是要先检查 end_line 是否有 ")" 后没有其他内容 (除了空白)
    after_paren = end_line_content[close_paren_idx + 1:].rstrip()

    # 如果该行除了 ) 之外还有其他非空内容 (例如 # 注释), 注释放外面
    if "#" in after_paren:
        # 把注释移动到 exc_info 后面
        comment_match = re.search(r'(#.*)', end_line_content[close_paren_idx + 1:])
        if comment_match:
            comment = comment_match.group(1)
            new_end_line = (end_line_content[:close_paren_idx]
                            + ", exc_info=True"
                            + ")"
                            + "  "
                            + comment)
        else:
            new_end_line = end_line_content[:close_paren_idx] + ", exc_info=True)" + end_line_content[close_paren_idx + 1:]
    else:
        new_end_line = end_line_content[:close_paren_idx] + ", exc_info=True)" + end_line_content[close_paren_idx + 1:]

    if kind == "LOW_LEVEL":
        # logger.debug/info → logger.warning
        start_line_content = lines[logger_lineno - 1]
        new_start_line = re.sub(r'logger\.(debug|info)\(', 'logger.warning(', start_line_content)
        if new_start_line != start_line_content:
            lines[logger_lineno - 1] = new_start_line

    lines[end_line_idx] = new_end_line

    # 幂等性检查: 如果新行已有 exc_info=True, 不再插入 (防止重复修复)
    if "exc_info=True" in new_end_line:
        # 已经是正确的, 跳过 (但这里已修改, 需回滚?)
        # 实际上如果 idempotency 检查在 fix 前做更好
        pass

    new_source = "\n".join(lines)

    # 验证语法
    try:
        ast.parse(new_source)
    except SyntaxError:
        return False

    file_path.write_text(new_source, encoding="utf-8")
    return True


def fix_multiline_logger_idempotent(file_path: Path, logger_lineno: int, kind: str) -> bool:
    """
    修复多行 logger 调用 (幂等性):
    - 如果 exc_info=True 已存在, 跳过
    - MISSING_EXC_INFO: 在 ) 前插入 , exc_info=True
    - LOW_LEVEL: logger.{debug,info} → logger.warning, 在 ) 前插入 , exc_info=True
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception:
        return False

    # 幂等性检查: 如果 end_line 已有 exc_info=True, 跳过
    end_pos = find_logger_call_end(source, logger_lineno)
    if not end_pos:
        return False
    end_line, end_col = end_pos
    lines = source.split("\n")
    if end_line - 1 < len(lines):
        end_line_content = lines[end_line - 1]
        if "exc_info" in end_line_content:
            # 已修复, 跳过
            return True  # 视为已成功 (但不算新修复)

    return fix_multiline_logger(file_path, logger_lineno, kind)


def main():
    print("=" * 80)
    print("R195-A v5 多行 logger P1 修复器 (剩余 11 块)")
    print("=" * 80)

    by_file: Dict[str, List[Tuple[int, str]]] = {}
    for f, ln, k in R195_A_REMAINING_P1:
        by_file.setdefault(f, []).append((ln, k))

    grand_fixed = 0
    backed_up = set()
    for rel_path, fixes in by_file.items():
        file_path = PROJECT_ROOT / rel_path
        if not file_path.exists():
            print(f"[MISSING] {rel_path}")
            continue
        # 仅在第一次见到该文件时备份
        if rel_path not in backed_up:
            backup_file(file_path)
            backed_up.add(rel_path)
        file_fixed = 0
        for ln, kind in fixes:
            if fix_multiline_logger_idempotent(file_path, ln, kind):
                file_fixed += 1
        grand_fixed += file_fixed
        print(f"  [{file_fixed}/{len(fixes)}] {rel_path}")

    print(f"\n总计: {grand_fixed}/{len(R195_A_REMAINING_P1)}")


if __name__ == "__main__":
    main()
