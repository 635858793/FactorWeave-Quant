"""
R176-B-3/B-4 批量修复脚本: import_execution_engine.py 25 处 + event_coordinator.py 14 处 R51 #5 违规
====================================================================================================

Why: R176-C 子智能体发现 R51 #5 违规在 2 个文件:
- core/importdata/import_execution_engine.py: 25 处 except 块内 P0 必修
- core/coordinators/event_coordinator.py: 14 处 except 块内 P0 必修

Fix: 用 AST 精确定位 except 块内的 logger.warning 调用, 自动添加 exc_info=True.

Ref:
- R51 §7.1 #5 强约束
- R104 §12 5 铁律
- R85 假修复鉴别 4 步法
"""
import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui").resolve()
TARGET_FILES = [
    PROJECT_ROOT / "core" / "importdata" / "import_execution_engine.py",
    PROJECT_ROOT / "core" / "coordinators" / "event_coordinator.py",
]


def find_except_logger_warnings(tree: ast.AST):
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if not (isinstance(child.func, ast.Attribute) and child.func.attr == "warning"):
                continue
            if not (isinstance(child.func.value, ast.Name) and child.func.value.id == "logger"):
                continue
            has_exc_info = any(
                isinstance(kw.value, ast.Constant) and kw.value.value is True
                for kw in child.keywords
                if kw.arg == "exc_info"
            )
            if has_exc_info:
                continue
            violations.append((child.lineno, child.end_lineno, child.col_offset, child.end_col_offset))
    return violations


def fix_exc_info(source: str, violations: list) -> str:
    lines = source.split("\n")
    for start_line, end_line, _, _ in sorted(violations, key=lambda x: -x[0]):
        target_line_idx = end_line - 1
        if target_line_idx >= len(lines):
            continue
        target_line = lines[target_line_idx]
        last_paren = -1
        paren_depth = 0
        in_string = False
        string_char = None
        for i, ch in enumerate(target_line):
            if in_string:
                if ch == string_char and (i == 0 or target_line[i-1] != "\\"):
                    in_string = False
                continue
            if ch in ('"', "'"):
                in_string = True
                string_char = ch
                continue
            if ch == "(":
                paren_depth += 1
            elif ch == ")":
                paren_depth -= 1
                if paren_depth <= 0:
                    last_paren = i
                    break
        if last_paren == -1:
            print(f"  WARN: L{end_line} 未找到匹配的 ), 跳过")
            continue
        prefix = target_line[:last_paren]
        if "exc_info" in prefix:
            print(f"  SKIP: L{end_line} 已有 exc_info 提及")
            continue
        if last_paren > 0 and target_line[last_paren-1] != ",":
            new_line = target_line[:last_paren] + ", exc_info=True" + target_line[last_paren:]
        else:
            new_line = target_line[:last_paren] + "exc_info=True" + target_line[last_paren:]
        lines[target_line_idx] = new_line
        print(f"  FIX L{end_line}: 添加 exc_info=True")
    return "\n".join(lines)


def main():
    total_fixed = 0
    for file_path in TARGET_FILES:
        if not file_path.exists():
            print(f"ERROR: {file_path} 不存在")
            continue
        print(f"\n=== {file_path.name} ===")
        source = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            print(f"ERROR: 源文件语法错误: {e}")
            continue
        violations = find_except_logger_warnings(tree)
        print(f"违规数: {len(violations)}")
        if len(violations) == 0:
            print("无违规, 跳过")
            continue
        new_source = fix_exc_info(source, violations)
        try:
            new_tree = ast.parse(new_source)
        except SyntaxError as e:
            print(f"ERROR: 修复后语法错误: {e}")
            continue
        new_violations = find_except_logger_warnings(new_tree)
        if len(new_violations) > 0:
            print(f"WARN: 修复后仍有 {len(new_violations)} 处违规")
        file_path.write_text(new_source, encoding="utf-8")
        fixed = len(violations) - len(new_violations)
        total_fixed += fixed
        print(f"✅ {file_path.name}: 修复 {fixed} 处")
    print(f"\n=== 总计 ===")
    print(f"修复: {total_fixed} 处")


if __name__ == "__main__":
    main()
