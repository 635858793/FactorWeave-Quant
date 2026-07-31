#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R194-D 终极修复 v3.1 - 修正 body[0] vs handler.lineno
=========================================================================
扫描器记录的 lineno 是 except handler 自身,实际修改应针对 body[0]
"""
import ast
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# 14 个剩余 P0 精确位置 (handler.lineno)
R194_HANDLER_P0 = [
    # (file, handler_lineno, method, kind, body_preview)
    ("core/services/unified_data_manager.py", 1475, "get_kdata", "PASS", "pass"),
    ("core/services/unified_data_manager.py", 1637, "get_kdata", "PASS", "pass"),
    ("core/services/unified_data_manager.py", 2166, "get_latest_prices_batch", "CONTINUE", "continue"),
    ("core/services/unified_data_manager.py", 2340, "get_kdata_from_source", "PASS", "pass"),
    ("core/services/unified_data_manager.py", 7639, "add_kline", "ASSIGN", "success = False"),
    ("core/services/service_bootstrap.py", 4518, "_register_longterm_p1_services", "ASSIGN", "_icm_instance = None"),
    ("core/services/service_bootstrap.py", 5689, "_register_ui_consumer_services", "ASSIGN", "instance = None"),
    ("core/coordinators/main_window_coordinator.py", 857, "_update_health_statusbar", "PASS", "pass"),
    ("core/coordinators/main_window_coordinator.py", 2667, "_on_database_admin", "INSERT", "QMessageBox.information"),
    ("core/coordinators/main_window_coordinator.py", 3480, "_on_signal_trading_bridge", "ASSIGN", "metrics = {'error': str(me)}"),
    ("core/coordinators/main_window_coordinator.py", 3640, "_on_alert_history", "INSERT", "QMessageBox.warning"),
    ("core/coordinators/main_window_coordinator.py", 6027, "_initialize_realtime_components", "PASS", "pass"),
    ("core/services/ai_selection_integration_service.py", 1103, "_get_candidate_stocks", "INSERT", "error_collector.add_error"),
    ("core/services/trading_service.py", 1473, "cancel_order", "PASS", "pass"),
]


def backup_file(file_path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(file_path.suffix + f".r194dv31.{ts}")
    shutil.copy2(file_path, backup_path)
    return backup_path


def get_handler_body_first_line(file_path: Path, handler_lineno: int) -> int:
    """获取 except handler body[0] 的 lineno"""
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))
    for n in ast.walk(tree):
        if isinstance(n, ast.ExceptHandler) and n.lineno == handler_lineno:
            if n.body:
                return n.body[0].lineno
    return handler_lineno + 1  # fallback


def fix_pass(source_lines: List[str], body_lineno: int, method: str) -> bool:
    """1-stmt PASS: 替换 body[0] 的 pass 为 logger.warning + exc_info=True"""
    line_idx = body_lineno - 1
    if line_idx >= len(source_lines):
        return False
    original = source_lines[line_idx]
    if "pass" not in original or "passport" in original or "passphrase" in original:
        return False
    # 只匹配真正的 pass 关键字
    stripped = original.strip()
    if stripped != "pass" and not stripped.startswith("pass "):
        return False
    indent = re.match(r"^(\s*)", original).group(1)
    new_line = f"{indent}logger.warning(\"[R194-D][{method}] 静默吞错 (pass), 已升级为 warning\", exc_info=True)  # R51 §7.1 #5 修复"
    source_lines[line_idx] = new_line
    return True


def fix_continue(source_lines: List[str], body_lineno: int, method: str) -> bool:
    """1-stmt CONTINUE: 在 body[0] 前插入 logger.warning + exc_info=True"""
    line_idx = body_lineno - 1
    if line_idx >= len(source_lines):
        return False
    original = source_lines[line_idx]
    if "continue" not in original:
        return False
    indent = re.match(r"^(\s*)", original).group(1)
    new_line = f"{indent}logger.warning(\"[R194-D][{method}] 静默吞错 (continue), 已记录堆栈\", exc_info=True)  # R51 §7.1 #5 修复"
    source_lines.insert(line_idx, new_line)
    return True


def fix_assign(source_lines: List[str], body_lineno: int, method: str) -> bool:
    """1-stmt Assign: 在 body[0] (assign) 前插入 logger.warning + exc_info=True"""
    line_idx = body_lineno - 1
    if line_idx >= len(source_lines):
        return False
    original = source_lines[line_idx]
    indent = re.match(r"^(\s*)", original).group(1)
    new_line = f"{indent}logger.warning(\"[R194-D][{method}] 异常, 降级路径 (assign), 已记录堆栈\", exc_info=True)  # R51 §7.1 #5 修复"
    source_lines.insert(line_idx, new_line)
    return True


def fix_insert_warning(source_lines: List[str], body_lineno: int, method: str) -> bool:
    """多行 NO_LOGGER: 在 except handler body[0] 前插入 logger.warning"""
    line_idx = body_lineno - 1
    if line_idx >= len(source_lines):
        return False
    original = source_lines[line_idx]
    indent = re.match(r"^(\s*)", original).group(1)
    new_line = f"{indent}logger.warning(\"[R194-D][{method}] 异常, 已记录堆栈\", exc_info=True)  # R51 §7.1 #5 修复"
    source_lines.insert(line_idx, new_line)
    return True


def fix_file_p0s(file_path: Path, p0_list: List[Tuple[int, str, str, str]]) -> int:
    """修复文件中所有指定 P0 位置"""
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  [ERROR] 读取失败: {e}")
        return 0

    backup_path = backup_file(file_path)
    source_lines = source.split("\n")
    fixed = 0

    # 按 handler_lineno 倒序处理,避免行号偏移
    sorted_p0s = sorted(p0_list, key=lambda x: x[0], reverse=True)

    for handler_lineno, method, kind, body_preview in sorted_p0s:
        body_lineno = get_handler_body_first_line(file_path, handler_lineno)
        # 注意: file_path.read_text 在循环中重复,但只在备份创建前一次性读
        # 实际上行号偏移只影响 source_lines,所以这里 body_lineno 用最初源文件的即可
        # 但 get_handler_body_first_line 用了 file_path.read_text -> 这是当前文件状态
        # 倒序处理后,前面已修复的不会影响后面
        # 但 fix_assign/fix_insert_warning 会插入新行,导致后续 body_lineno 偏移
        # 倒序处理可避免此问题 (因为我们只对更早的位置插入)

        # 重新计算 body_lineno (基于 file_path 当前状态 = 原始状态,因为倒序处理先处理后面的)
        # 实际上 file_path.read_text 读的是初始源 (因为我们还没 write)
        body_lineno = get_handler_body_first_line(file_path, handler_lineno)

        if kind == "PASS":
            if fix_pass(source_lines, body_lineno, method):
                fixed += 1
        elif kind == "CONTINUE":
            if fix_continue(source_lines, body_lineno, method):
                fixed += 1
        elif kind == "ASSIGN":
            if fix_assign(source_lines, body_lineno, method):
                fixed += 1
        elif kind == "INSERT":
            if fix_insert_warning(source_lines, body_lineno, method):
                fixed += 1

    # 验证语法
    new_source = "\n".join(source_lines)
    try:
        ast.parse(new_source)
        file_path.write_text(new_source, encoding="utf-8")
    except SyntaxError as e:
        print(f"  [ERROR] 修复后语法错误: {e}, 恢复备份")
        shutil.copy2(backup_path, file_path)
        return 0

    return fixed


def main():
    print("=" * 80)
    print("R194-D 终极修复 v3.1 (14 个剩余 P0, body[0] 修正)")
    print("=" * 80)

    by_file: Dict[str, List] = {}
    for f, ln, m, k, b in R194_HANDLER_P0:
        by_file.setdefault(f, []).append((ln, m, k, b))

    grand_fixed = 0
    for rel_path, p0_list in by_file.items():
        file_path = PROJECT_ROOT / rel_path
        if not file_path.exists():
            print(f"[MISSING] {rel_path}")
            continue
        print(f"\n--- {rel_path} ({len(p0_list)} P0) ---")
        fixed = fix_file_p0s(file_path, p0_list)
        grand_fixed += fixed
        print(f"  修复: {fixed}/{len(p0_list)}")

    print(f"\n{'=' * 80}")
    print(f"总计修复: {grand_fixed}/{len(R194_HANDLER_P0)}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
