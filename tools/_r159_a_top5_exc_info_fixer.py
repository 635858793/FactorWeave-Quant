"""R159-A TOP 5 P0 业务核心 logger.exc_info 批量修复工具

应用:
- R51 铁律 #5: 禁止静默吞错, 必须 logger.error + exc_info=True
- R150 keyword 模式: 避免行号漂移
- R156-P0-1 模板: 严格保留原 msg 主体, 仅追加 exc_info=True
- R104 §12 5 铁律: 4 源验证 + AST unparse 验证

策略:
- 用 Python AST 检测 except 块内的 logger.error/critical 缺 exc_info=True
- 文本模式追加 ", exc_info=True" 到 logger call 末尾
- 保留所有原 msg 主体, 不修改任何业务逻辑
"""
import ast
import json
import re
import shutil
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# TOP 5 P0 业务核心文件 (R158-C 报告)
TOP_5_P0_FILES = [
    "core/coordinators/main_window_coordinator.py",
    "gui/widgets/enhanced_data_import_widget.py",
    "core/ui/panels/right_panel.py",
    "core/trading/order_service.py",
    "core/importdata/import_execution_engine.py",
]

# 备份目录
BACKUP_DIR = PROJECT_ROOT / ".trae" / "reports" / "rounds" / "_r159_a_backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def backup_file(file_path: str) -> str:
    """备份文件"""
    full_path = PROJECT_ROOT / file_path
    backup_name = file_path.replace("/", "_").replace("\\", "_") + ".bak"
    backup_path = BACKUP_DIR / backup_name
    shutil.copy2(full_path, backup_path)
    return str(backup_path)


def has_exc_info(call: ast.Call) -> bool:
    """检测 logger call 是否带 exc_info=True"""
    for kw in call.keywords:
        if kw.arg == "exc_info":
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
    return False


def is_p0_logger_call(node: ast.Call) -> bool:
    """仅检测 logger.error / logger.critical"""
    if isinstance(node.func, ast.Attribute):
        if node.func.attr in ("error", "critical"):
            return True
    return False


def get_logger_call_end_line(source_lines: List[str], start_line: int) -> Tuple[int, int, int]:
    """获取 logger call 的开始行和结束行 (用于文本修改)

    Returns: (start_line, start_col, end_line, end_col)
    """
    # start_line 是 1-based
    # 找到从 start_line 开始的 logger call 结束位置
    # logger.error(... ) 的 ) 位置
    line_idx = start_line - 1
    if line_idx >= len(source_lines):
        return start_line, 0, start_line, 0

    # 简单的括号匹配: 在从 start_line 开始的行内, 找到第一个完整的 logger call
    # 但 logger call 可能跨行, 用 ast.end_lineno 拿精确位置
    return start_line, 0, start_line, 0


def find_logger_call_end_in_source(source: str, start_offset: int) -> int:
    """在源代码中从 start_offset 开始, 找到 logger call 的结束位置 (匹配的右括号)"""
    # 从 start_offset 开始, 找到匹配的 ')', 跳过字符串内的括号
    paren_depth = 0
    in_string = None
    i = start_offset
    n = len(source)
    found_first = False
    while i < n:
        c = source[i]
        if in_string:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == in_string:
                in_string = None
            i += 1
            continue
        if c in ('"', "'"):
            # 检查是否是 triple-quoted
            if i + 2 < n and source[i:i+3] in ('"""', "'''"):
                end = source.find(source[i:i+3], i+3)
                if end == -1:
                    return -1
                i = end + 3
                continue
            in_string = c
            i += 1
            continue
        if c == "#":
            # 行注释, 跳过到行尾
            j = source.find("\n", i)
            if j == -1:
                return -1
            i = j
            continue
        if c == "(":
            paren_depth += 1
            found_first = True
            i += 1
            continue
        if c == ")":
            paren_depth -= 1
            if found_first and paren_depth == 0:
                return i
            i += 1
            continue
        i += 1
    return -1


def is_in_except_context(tree: ast.Module, target_line: int) -> bool:
    """检查 target_line 是否在 except 块内"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                handler_start = handler.lineno
                handler_end = handler.end_lineno or handler.lineno
                if handler_start <= target_line <= handler_end:
                    return True
    return False


def find_logger_calls_in_except_missing_exc(file_path: str) -> List[Dict[str, Any]]:
    """查找 except 块内 logger.error/critical 缺 exc_info 的位置"""
    full_path = PROJECT_ROOT / file_path
    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()
    tree = ast.parse(source)

    missing = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and is_p0_logger_call(node):
            line = node.lineno
            col = node.col_offset
            if has_exc_info(node):
                continue
            if not is_in_except_context(tree, line):
                continue

            # 找到 call 结束位置
            # 找 logger 关键字位置
            # call.lineno/col_offset 是 call 起始位置
            # 但要找到 "(" 位置, 因为 col_offset 是 call 起始 (logger 关键字)
            # 用 line + col 找到字符串中的位置
            line_start_offset = sum(len(l) + 1 for l in source.split("\n")[:line-1])
            call_start = line_start_offset + col
            # 从 call_start 找第一个 "(" (logger.error 的左括号)
            open_paren_offset = source.find("(", call_start)
            if open_paren_offset == -1:
                continue
            # 从 open_paren_offset + 1 开始, 找匹配的 ")"
            end_offset = find_logger_call_end_in_source(source, open_paren_offset)
            if end_offset == -1:
                continue

            # 找到 ) 位置
            missing.append({
                "file": file_path,
                "line": line,
                "col": col,
                "open_paren_offset": open_paren_offset,
                "end_offset": end_offset,
                "method": node.func.attr,
            })

    return missing


def apply_exc_info_fix(file_path: str, missing: List[Dict[str, Any]]) -> Tuple[int, str]:
    """对文件应用 exc_info 修复

    Returns: (fix_count, new_source)
    """
    full_path = PROJECT_ROOT / file_path
    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()

    # 按 end_offset 倒序, 从后往前插入避免偏移错位
    sorted_missing = sorted(missing, key=lambda m: -m["end_offset"])
    new_source = source
    fix_count = 0

    for m in sorted_missing:
        end_offset = m["end_offset"]
        # 在 ) 之前插入 , exc_info=True
        # 检查 ) 之前是否已经有 kwargs (含逗号)
        # 简化: 直接在 ) 之前插入
        before = new_source[:end_offset]
        after = new_source[end_offset:]

        # 进一步检查: ) 前面是否有逗号
        trimmed_before = before.rstrip()
        if trimmed_before.endswith(","):
            # 已经有逗号, 直接追加
            new_at = trimmed_before + " exc_info=True" + before[len(trimmed_before):]
        else:
            # 没有逗号, 加 ", exc_info=True"
            new_at = trimmed_before + ", exc_info=True" + before[len(trimmed_before):]
        new_source = new_at + after
        fix_count += 1

    return fix_count, new_source


def fix_file(file_path: str) -> Dict[str, Any]:
    """修复单个文件"""
    backup_path = backup_file(file_path)
    missing = find_logger_calls_in_except_missing_exc(file_path)
    if not missing:
        return {
            "file": file_path,
            "fix_count": 0,
            "missing_count": 0,
            "backup": backup_path,
        }

    fix_count, new_source = apply_exc_info_fix(file_path, missing)
    if fix_count > 0:
        full_path = PROJECT_ROOT / file_path
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_source)

    # 验证修复
    post_missing = find_logger_calls_in_except_missing_exc(file_path)
    return {
        "file": file_path,
        "missing_count": len(missing),
        "fix_count": fix_count,
        "post_missing_count": len(post_missing),
        "backup": backup_path,
    }


def main():
    print("R159-A TOP 5 P0 业务核心 logger.exc_info 批量修复")
    print("=" * 70)
    print()

    results = []
    for f in TOP_5_P0_FILES:
        print(f"修复: {f}")
        result = fix_file(f)
        results.append(result)
        print(f"  missing: {result['missing_count']}, "
              f"fix: {result['fix_count']}, "
              f"post_missing: {result['post_missing_count']}")
        print()

    output_path = PROJECT_ROOT / "tests" / "_r159_a_fix_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    total_fix = sum(r["fix_count"] for r in results)
    total_missing = sum(r["missing_count"] for r in results)
    total_post = sum(r["post_missing_count"] for r in results)
    print(f"总 missing: {total_missing}, 总 fix: {total_fix}, post_missing: {total_post}")


if __name__ == "__main__":
    main()
