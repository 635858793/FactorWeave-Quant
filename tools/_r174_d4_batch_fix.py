#!/usr/bin/env python3
"""
HVD-173-D-4 批量修复脚本 v2
使用 AST + 源码位置跟踪, 精确修复 except 块内 logger 缺 exc_info=True
"""
import ast
import re
from pathlib import Path
from typing import Tuple, List, Dict

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

# 待修复文件清单
TARGET_FILES = [
    "core/trading/order_service.py",
    "core/services/unified_data_manager.py",
    "core/services/dynamic_risk_adjustment_service.py",
    "core/services/ai_selection_integration_service.py",
    "core/agents/risk_agent.py",
    "core/events/event_bus.py",
    "core/coordinators/main_window_coordinator.py",
]

R51_LEVELS = ("warning", "error", "critical", "exception")


def find_logger_violations(source: str) -> List[Dict]:
    """找出所有 except 块内缺 exc_info=True 的 logger 调用"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
                continue
            if func.value.id != "logger" or func.attr not in R51_LEVELS:
                continue

            has_exc_info = False
            for kw in child.keywords:
                if kw.arg == "exc_info":
                    if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        has_exc_info = True
                    elif isinstance(kw.value, ast.NameConstant) and kw.value.value is True:
                        has_exc_info = True

            if not has_exc_info:
                violations.append({
                    "line": child.lineno,
                    "end_line": getattr(child, "end_lineno", child.lineno),
                    "end_col": getattr(child, "end_col_offset", 0),
                    "level": func.attr,
                })

    return violations


def find_call_end_in_source(source_lines: List[str], call_line: int, call_end_line: int, call_end_col: int) -> int:
    """找到 logger 调用的右括号位置 (绝对字符偏移)"""
    # 简单情况: 调用在单行内
    if call_line == call_end_line:
        return None  # 不需要这个函数

    # 跨行: 从 call_line 开始扫描, 找到右括号
    return None


def fix_file_violations(file_path: Path) -> Tuple[int, int, List[Dict]]:
    """修复单个文件的违规, 返回 (违规数, 已修复数, 剩余违规)"""
    source = file_path.read_text(encoding="utf-8")
    lines = source.split("\n")

    violations = find_logger_violations(source)
    if not violations:
        return 0, 0, []

    # 按行号倒序处理, 避免行号错位
    violations_sorted = sorted(violations, key=lambda v: (v["line"], v["end_line"]), reverse=True)
    fixed = 0
    remaining = []

    for v in violations_sorted:
        line_idx = v["line"] - 1
        end_line_idx = v["end_line"] - 1
        end_col = v["end_col"]

        if line_idx < 0 or end_line_idx >= len(lines):
            remaining.append(v)
            continue

        level = v["level"]

        # 单行调用
        if line_idx == end_line_idx:
            line = lines[line_idx]
            if "exc_info" in line and "exc_info=True" in line:
                continue
            # 在 end_col 位置 (即 ) 处) 前插入
            if end_col > 0 and end_col <= len(line) and line[end_col-1] == ")":
                # 找到 ) 前的位置
                insert_pos = end_col - 1
                # 检查 ) 之前是否有逗号或空格
                prefix = line[:insert_pos].rstrip()
                if prefix.endswith(","):
                    line = line[:insert_pos].rstrip() + " exc_info=True" + line[insert_pos:]
                else:
                    line = prefix + ", exc_info=True" + line[insert_pos:].lstrip()
                lines[line_idx] = line
                fixed += 1
                continue
            else:
                # 备选: 简单字符串替换, 在最后 ) 前插入
                m = re.search(rf'(logger\.{level}\s*\([^)]*)\)(\s*)$', line)
                if m:
                    lines[line_idx] = line.replace(m.group(0), m.group(1) + ", exc_info=True)" + m.group(2), 1)
                    fixed += 1
                    continue
                remaining.append(v)
        else:
            # 跨行调用
            # 找到调用结束的 ) 位置 (end_line 的 end_col)
            end_line = lines[end_line_idx]
            if end_col > 0 and end_col <= len(end_line) and end_line[end_col-1] == ")":
                insert_pos = end_col - 1
                # 检查 ) 之前是否有逗号或空格
                prefix = end_line[:insert_pos].rstrip()
                if prefix.endswith(","):
                    end_line = end_line[:insert_pos].rstrip() + " exc_info=True" + end_line[insert_pos:]
                else:
                    end_line = prefix + ", exc_info=True" + end_line[insert_pos:].lstrip()
                lines[end_line_idx] = end_line
                fixed += 1
            else:
                remaining.append(v)

    # 写回文件
    new_source = "\n".join(lines)
    file_path.write_text(new_source, encoding="utf-8")

    return len(violations), fixed, remaining


def main():
    print("=" * 80)
    print("HVD-173-D-4 批量修复 v2 (AST 精确修复 except 块内 logger 缺 exc_info=True)")
    print("=" * 80)

    total_violations = 0
    total_fixed = 0
    total_remaining = 0

    for rel_path in TARGET_FILES:
        file_path = PROJECT_ROOT / rel_path
        if not file_path.exists():
            print(f"[SKIP] {rel_path} (文件不存在)")
            continue

        violations_count, fixed_count, remaining = fix_file_violations(file_path)
        total_violations += violations_count
        total_fixed += fixed_count
        total_remaining += len(remaining)

        status = "[OK]" if len(remaining) == 0 and fixed_count == violations_count else "[WARN]" if fixed_count > 0 else "[FAIL]"
        print(f"{status} {rel_path}: 检测 {violations_count} 处, 修复 {fixed_count} 处, 剩余 {len(remaining)} 处")
        for r in remaining[:5]:
            print(f"   - L{r['line']}-L{r['end_line']} logger.{r['level']}")

    print()
    print("=" * 80)
    print(f"总计: 检测 {total_violations} 处, 修复 {total_fixed} 处, 剩余 {total_remaining} 处")
    print("=" * 80)


if __name__ == "__main__":
    main()
