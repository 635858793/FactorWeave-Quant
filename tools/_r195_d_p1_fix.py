#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R195-D 升级修复器 v4.1 (P1 静默失败治理, 32 处) - 修正 v4 行号偏移 bug
=========================================================================

**v4.1 关键修正**:
- v4 bug: 倒序处理时,前序修复插入新行导致后续行号偏移 → source_lines[i] 不再对应原行号
- v4.1 修复: 每次修复前 re-read 文件 + 重新计算目标 except handler 的位置

**v4.1 改进**:
- AST-based except handler 定位 (按 method + 异常类型匹配)
- 严格区分 MISSING_EXC_INFO (logger.warning/error 缺 exc_info) vs LOW_LEVEL (logger.debug)
- 多行 logger 调用自动识别 (跨行 f-string 模式)
- 特殊处理: logger.error(traceback.format_exc()) → 删除 (exc_info=True 已提供)
"""
import ast
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# R195-D 32 个 P1 升级位置 (来自 R194-D 严格扫描器 v2)
# (file, line, method, kind, original_text_preview)
R195_D_P1_LOCATIONS = [
    # 1. sla_monitor.py (2)
    ("core/monitoring/sla_monitor.py", 195, "__init__", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/monitoring/sla_monitor.py", 292, "record", "LOW_LEVEL", "logger.debug(...)"),
    # 2. performance_monitor.py (7)
    ("core/monitoring/performance_monitor.py", 288, "_connect_alert_system", "MISSING_EXC_INFO", "logger.error(...)"),
    ("core/monitoring/performance_monitor.py", 311, "_on_alert_raised", "MISSING_EXC_INFO", "logger.error(...)"),
    ("core/monitoring/performance_monitor.py", 345, "record_metric", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/monitoring/performance_monitor.py", 409, "_periodic_monitoring", "MISSING_EXC_INFO", "logger.error(...)"),
    ("core/monitoring/performance_monitor.py", 418, "_generate_periodic_report", "MISSING_EXC_INFO", "logger.error(...)"),
    ("core/monitoring/performance_monitor.py", 463, "_save_report_to_file", "MISSING_EXC_INFO", "logger.error(...)"),
    ("core/monitoring/performance_monitor.py", 516, "export_metrics_to_csv", "MISSING_EXC_INFO", "logger.error(...)"),
    # 3. cache_degradation_exporter.py (5)
    ("core/monitoring/cache_degradation_exporter.py", 98, "_init_metrics", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/monitoring/cache_degradation_exporter.py", 148, "collect_metrics", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/monitoring/cache_degradation_exporter.py", 177, "collect_metrics", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/monitoring/cache_degradation_exporter.py", 201, "get_metrics_text", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/monitoring/cache_degradation_exporter.py", 233, "get_metrics_json", "MISSING_EXC_INFO", "logger.warning(...)"),
    # 4. unified_data_manager.py (3)
    ("core/services/unified_data_manager.py", 2741, "_on_data_import_event", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/services/unified_data_manager.py", 7668, "add_kline", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/services/unified_data_manager.py", 7774, "add_kline", "MISSING_EXC_INFO", "logger.warning(...)"),
    # 5. service_bootstrap.py (3)
    ("core/services/service_bootstrap.py", 3322, "_register_feedback_service", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/services/service_bootstrap.py", 3327, "_register_feedback_service", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/services/service_bootstrap.py", 5664, "_register_ui_consumer_services", "MISSING_EXC_INFO", "logger.warning(...)"),
    # 6. main_window_coordinator.py (11)
    ("core/coordinators/main_window_coordinator.py", 1407, "_on_node_management", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/coordinators/main_window_coordinator.py", 3360, "_on_service_health_monitor", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/coordinators/main_window_coordinator.py", 3455, "_on_signal_trading_bridge", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/coordinators/main_window_coordinator.py", 4023, "_check_data_usage_terms", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/coordinators/main_window_coordinator.py", 5103, "_create_standalone_backtest_window", "LOW_LEVEL", "logger.debug(...)"),
    ("core/coordinators/main_window_coordinator.py", 5597, "_on_distributed_computing", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/coordinators/main_window_coordinator.py", 5993, "_initialize_realtime_components", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/coordinators/main_window_coordinator.py", 6079, "_initialize_enhanced_ui_components_async", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/coordinators/main_window_coordinator.py", 6555, "_on_realtime_status_unavailable", "MISSING_EXC_INFO", "logger.warning(...)"),
    ("core/coordinators/main_window_coordinator.py", 6624, "_on_realtime_status_restored", "MISSING_EXC_INFO", "logger.warning(...)"),
    # 7. ai_selection_integration_service.py (1) - 特殊: traceback.format_exc() 重构
    ("core/services/ai_selection_integration_service.py", 3397, "select_stocks", "MISSING_EXC_INFO", "logger.error(traceback.format_exc())"),
]


def backup_file(file_path: Path) -> Path:
    """备份文件,带时间戳"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(file_path.suffix + f".r195dv41.{ts}")
    shutil.copy2(file_path, backup_path)
    return backup_path


def find_logger_call_range(source_lines: List[str], start_line: int) -> Tuple[int, int]:
    """
    找到从 start_line 开始的 logger 调用的结束行 (1-indexed)
    跨多行 f-string 模式处理
    """
    line_idx = start_line - 1
    if line_idx >= len(source_lines):
        return start_line, start_line

    paren_depth = 0
    start_idx = line_idx
    saw_open = False

    for i in range(line_idx, len(source_lines)):
        line = source_lines[i]
        # 跳过注释
        code_part = re.sub(r'#.*$', '', line)
        for ch in code_part:
            if ch == '(':
                paren_depth += 1
                saw_open = True
            elif ch == ')':
                paren_depth -= 1
                if saw_open and paren_depth == 0:
                    return start_idx + 1, i + 1  # 1-indexed inclusive

    return start_line, start_line


def is_already_fixed(source_lines: List[str], start_line: int, end_line: int) -> bool:
    """检查 logger 调用范围是否已经修复 (含 exc_info=True)"""
    for i in range(start_line - 1, end_line):
        if 'exc_info=True' in source_lines[i]:
            return True
    return False


def add_exc_info_single_line(source_lines: List[str], line_no: int, method: str) -> bool:
    """单行 logger.warning/error: 在行尾加 , exc_info=True"""
    line_idx = line_no - 1
    if line_idx >= len(source_lines):
        return False
    original = source_lines[line_idx]
    stripped = original.rstrip()
    if not stripped.endswith(')'):
        return False
    # 检查是否已经有 exc_info (避免重复)
    if 'exc_info=' in stripped:
        return False
    new_stripped = stripped[:-1].rstrip() + ", exc_info=True)  # R51 §7.1 #5 修复"
    source_lines[line_idx] = new_stripped
    return True


def upgrade_low_level_single_line(source_lines: List[str], line_no: int, method: str) -> bool:
    """单行 logger.debug → logger.warning + exc_info=True"""
    line_idx = line_no - 1
    if line_idx >= len(source_lines):
        return False
    original = source_lines[line_idx]
    stripped = original.rstrip()
    if not stripped.endswith(')'):
        return False
    if 'logger.debug(' not in stripped:
        return False
    # 1. logger.debug → logger.warning
    new_stripped = stripped.replace('logger.debug(', 'logger.warning(', 1)
    # 2. 在尾部加 , exc_info=True
    new_stripped = new_stripped[:-1].rstrip() + ", exc_info=True)  # R51 §7.1 #5 LOW_LEVEL 升级"
    source_lines[line_idx] = new_stripped
    return True


def add_exc_info_multi_line(source_lines: List[str], start_line: int, end_line: int, method: str) -> bool:
    """多行 logger.warning/error: 在最后字符串后,闭合 ) 前插入 exc_info=True"""
    last_str_line = end_line - 1  # 1-indexed
    last_str_idx = last_str_line - 1

    if last_str_idx < 0 or last_str_idx >= len(source_lines):
        return False

    last_str = source_lines[last_str_idx].rstrip()
    # 检查是否已经有 exc_info
    if 'exc_info=' in last_str:
        return False

    # 提取缩进
    indent = re.match(r"^(\s*)", source_lines[last_str_idx]).group(1)

    if last_str.endswith(','):
        # 最后一行已以 , 结尾, 直接加 exc_info=True 行
        new_line = f"{indent}exc_info=True,  # R51 §7.1 #5 修复"
        source_lines.insert(last_str_idx + 1, new_line)
        return True

    if last_str.endswith('"') or last_str.endswith("'"):
        # 最后一行以 f-string 闭合, 在末尾加 , 然后下一行加 exc_info=True,
        source_lines[last_str_idx] = last_str + ","
        new_line = f"{indent}exc_info=True,  # R51 §7.1 #5 修复"
        source_lines.insert(last_str_idx + 1, new_line)
        return True

    return False


def upgrade_low_level_multi_line(source_lines: List[str], start_line: int, end_line: int, method: str) -> bool:
    """多行 logger.debug → logger.warning + exc_info=True"""
    # 1. 修改 logger.debug → logger.warning
    for i in range(start_line - 1, end_line):
        if 'logger.debug(' in source_lines[i]:
            source_lines[i] = source_lines[i].replace('logger.debug(', 'logger.warning(', 1)
            break
    # 2. 添加 exc_info=True (复用多行修复逻辑)
    return add_exc_info_multi_line(source_lines, start_line, end_line, method)


def fix_special_traceback_format_exc(source_lines: List[str], line_no: int) -> bool:
    """
    特殊情况: logger.error(traceback.format_exc())
    因为 exc_info 已经由上一行 logger.error(... exc_info=True) 提供, 这个是冗余的
    删除整行
    """
    line_idx = line_no - 1
    if line_idx >= len(source_lines):
        return False
    original = source_lines[line_idx]
    if 'logger.error(traceback.format_exc())' not in original:
        return False
    del source_lines[line_idx]
    return True


def find_logger_call_by_method(source_lines: List[str], method_name: str, search_start: int = 0) -> Optional[int]:
    """
    在源代码中查找下一个 `def method_name(` 之后到下一个 def 之前的 logger.warning/error/debug 调用
    返回 logger 调用的行号 (1-indexed)
    """
    method_pattern = re.compile(rf"^\s+(?:async\s+)?def\s+{re.escape(method_name)}\s*\(")
    next_def_pattern = re.compile(r"^\s+(?:async\s+)?def\s+\w+\s*\(")
    in_method = False
    for i in range(search_start, len(source_lines)):
        line = source_lines[i]
        if not in_method:
            if method_pattern.match(line):
                in_method = True
                continue
        else:
            # 在方法内
            if next_def_pattern.match(line):
                return None  # 超出方法
            # 检查 logger.warning/error/debug 调用
            for level in ('warning', 'error', 'debug'):
                if f'logger.{level}(' in line:
                    return i + 1  # 1-indexed
    return None


def find_logger_call_in_method(source_path: Path, method_name: str, search_start: int = 0) -> Optional[Tuple[int, int, int]]:
    """
    使用 AST 查找指定方法中第一个 logger.warning/error/debug 调用 (按源码顺序)
    返回 (logger_call_lineno, method_start_lineno, method_end_lineno) 或 None
    """
    try:
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
    except Exception:
        return None

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name:
            # 找到方法
            method_start = node.lineno
            method_end = node.end_lineno or node.lineno
            # 在方法体内按源码顺序查找 logger 调用
            candidates = []
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Attribute):
                        if isinstance(child.func.value, ast.Name) and child.func.value.id == "logger":
                            if child.func.attr in ("warning", "error", "debug"):
                                candidates.append(child.lineno)
            if candidates:
                # 按源码顺序排序, 取第一个
                candidates.sort()
                return (candidates[0], method_start, method_end)
            return None  # 方法内无 logger 调用
    return None


def find_except_handler_logger(source_path: Path, method_name: str, target_line: int) -> Optional[int]:
    """
    在指定方法的 except 块中, 查找 target_line 附近 (向上) 的 logger.warning/error/debug 调用
    用于精确定位 L5597-style 场景 (multi-line call 在 except 内)
    """
    try:
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
    except Exception:
        return None

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name:
            # 找到方法
            for child in ast.walk(node):
                if isinstance(child, ast.ExceptHandler):
                    # 检查 except 块内是否有 logger 调用, 且行号 >= target_line
                    for grand in ast.walk(child):
                        if isinstance(grand, ast.Call):
                            if isinstance(grand.func, ast.Attribute):
                                if isinstance(grand.func.value, ast.Name) and grand.func.value.id == "logger":
                                    if grand.func.attr in ("warning", "error", "debug"):
                                        # 找最近的 logger 调用 (向上)
                                        if grand.lineno <= target_line + 5:  # 容忍小偏移
                                            return grand.lineno
            return None
    return None


def fix_location(file_path: Path, loc: Tuple, file_state_offset: int = 0) -> bool:
    """修复单个 P1 位置 (v4.1: 重新读取文件以避免行号偏移 bug)"""
    rel_file, line_no, method, kind, original_text = loc

    if not file_path.exists():
        print(f"  [MISSING] {file_path}")
        return False

    # 1. 重新读取文件 (避免行号偏移 bug)
    source = file_path.read_text(encoding="utf-8")
    source_lines = source.split("\n")

    # 2. 特殊处理 L3397
    if line_no == 3397 and 'traceback.format_exc()' in original_text:
        # 先检查该行是否已被删除 (v4 已删)
        line_idx = line_no - 1
        if line_idx < len(source_lines) and 'logger.error(traceback.format_exc())' in source_lines[line_idx]:
            result = fix_special_traceback_format_exc(source_lines, line_no)
            if not result:
                print(f"  [SKIP] L{line_no} ({method}) {kind} - 特殊处理失败")
                return False
        else:
            # 已经被 v4 删除
            print(f"  [ALREADY FIXED] L{line_no} ({method}) {kind} - 已被 v4 删除")
            return True
    else:
        # 3. 使用 AST 找到正确的 logger 调用行号 (v4.1 改进)
        # 优先用 except-handler-aware 定位 (适用于 multi-call 方法)
        except_logger = find_except_handler_logger(file_path, method, target_line=line_no)
        if except_logger is not None:
            actual_line = except_logger
        else:
            logger_info = find_logger_call_in_method(file_path, method, search_start=max(0, line_no - 200))
            if logger_info is None:
                # fallback: 文本搜索 (按 method 名称)
                actual_line = find_logger_call_by_method(source_lines, method, search_start=max(0, line_no - 200))
                if actual_line is None:
                    print(f"  [SKIP] L{line_no} ({method}) {kind} - 未找到 logger 调用")
                    return False
            else:
                actual_line = logger_info[0]

        # 4. 找到 logger 调用的范围
        start_line, end_line = find_logger_call_range(source_lines, actual_line)
        is_multi_line = (end_line > start_line)

        # 4.5. 检查是否已修复 (含 exc_info=True)
        if is_already_fixed(source_lines, start_line, end_line):
            print(f"  [ALREADY FIXED] L{line_no} ({method}) {kind}")
            return True  # 已修复视为成功

        # 5. 应用修复
        if kind == "MISSING_EXC_INFO":
            if is_multi_line:
                result = add_exc_info_multi_line(source_lines, start_line, end_line, method)
            else:
                result = add_exc_info_single_line(source_lines, actual_line, method)
        elif kind == "LOW_LEVEL":
            if is_multi_line:
                result = upgrade_low_level_multi_line(source_lines, start_line, end_line, method)
            else:
                result = upgrade_low_level_single_line(source_lines, actual_line, method)
        else:
            print(f"  [UNKNOWN kind: {kind}] L{line_no}")
            return False

        if not result:
            print(f"  [SKIP] L{line_no} ({method}) {kind} - 应用失败 (actual_line={actual_line}, multi={is_multi_line})")
            return False

    # 6. 验证语法
    new_source = "\n".join(source_lines)
    try:
        ast.parse(new_source)
    except SyntaxError as e:
        print(f"  [SYNTAX ERROR] L{line_no} ({method}) {kind} - {e}")
        return False

    # 7. 写回文件
    file_path.write_text(new_source, encoding="utf-8")
    return True


def fix_file_locations(file_path: Path, locations: List[Tuple]) -> int:
    """修复单个文件中的多个 P1 位置 (v4.1: 每次重新读取文件)"""
    backup_path = backup_file(file_path)
    print(f"  [BACKUP] {backup_path.name}")

    fixed = 0
    for loc in locations:
        if fix_location(file_path, loc):
            fixed += 1
            print(f"  [OK] L{loc[1]} ({loc[2]}) {loc[3]}")
        else:
            print(f"  [FAIL] L{loc[1]} ({loc[2]}) {loc[3]}")

    return fixed


def main():
    print("=" * 80)
    print("R195-D P1 升级修复器 v4.1 (32 处 MISSING_EXC_INFO + LOW_LEVEL)")
    print("=" * 80)

    by_file: Dict[str, List] = {}
    for loc in R195_D_P1_LOCATIONS:
        by_file.setdefault(loc[0], []).append(loc)

    grand_total = 0
    grand_fixed = 0

    for rel_path, locations in by_file.items():
        file_path = PROJECT_ROOT / rel_path
        if not file_path.exists():
            print(f"\n[MISSING] {rel_path}")
            continue
        print(f"\n--- {rel_path} ({len(locations)} P1) ---")
        fixed = fix_file_locations(file_path, locations)
        grand_total += len(locations)
        grand_fixed += fixed

    print(f"\n{'=' * 80}")
    print(f"R195-D v4.1 总计: 修复 {grand_fixed}/{grand_total}")
    print(f"{'=' * 80}")

    return grand_fixed == grand_total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
