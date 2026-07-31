"""
R176-B-1 批量修复脚本: service_bootstrap.py 62 处 P0 必修 R51 #5 违规
================================================================

Why: R176-C 子智能体发现 service_bootstrap.py 有 62 处 except 块内 logger.warning
     缺 exc_info=True, 违反 R51 §7.1 #5 强约束 (业务关键路径 100% exc_info=True).

Fix: 用 AST 精确定位 except 块内的 logger.warning 调用, 自动添加 exc_info=True.

Ref:
- R51 §7.1 #5 强约束
- R104 §12 5 铁律 (R+1 round 二次验证)
- R162 立项描述错位教训
- R85 假修复鉴别 4 步法

TDD:
- tests/test_r176_b_1_service_bootstrap_exc_info.py
"""
import ast
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui").resolve()
TARGET_FILE = PROJECT_ROOT / "core" / "services" / "service_bootstrap.py"


def find_except_logger_warnings(tree: ast.AST, source: str) -> list:
    """查找所有在 except 块内的 logger.warning 调用 (无 exc_info=True)"""
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
            # 检查是否已有 exc_info=True
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
    """为 except 块内的 logger.warning 添加 exc_info=True

    策略:
    1. 单行调用: 在 closing ) 前加 , exc_info=True
    2. 多行调用: 找到最后一个非空行, 在 ) 前加 , exc_info=True
    """
    lines = source.split("\n")
    # 按行号倒序处理, 避免行号偏移
    for start_line, end_line, _, _ in sorted(violations, key=lambda x: -x[0]):
        # 找到 logger.warning( 调用的结束位置 (对应的 ))
        # end_line 指向最后一个 )
        # 找到 end_line 行内 ) 的位置
        target_line_idx = end_line - 1
        if target_line_idx >= len(lines):
            continue
        target_line = lines[target_line_idx]
        # 找到最后一个 ) 之前的位置
        # 跳过字符串内的 )
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
        # 检查 last_paren 前是否已有 exc_info
        prefix = target_line[:last_paren]
        if "exc_info" in prefix:
            print(f"  SKIP: L{end_line} 已有 exc_info 提及")
            continue
        # 在 last_paren 前插入 , exc_info=True
        # 判断 last_paren 前是否需要换行 (短行直接同行)
        if last_paren > 0 and target_line[last_paren-1] != ",":
            new_line = target_line[:last_paren] + ", exc_info=True" + target_line[last_paren:]
        else:
            new_line = target_line[:last_paren] + "exc_info=True" + target_line[last_paren:]
        lines[target_line_idx] = new_line
        print(f"  FIX L{end_line}: 添加 exc_info=True")
    return "\n".join(lines)


def main():
    if not TARGET_FILE.exists():
        print(f"ERROR: {TARGET_FILE} 不存在")
        sys.exit(1)
    source = TARGET_FILE.read_text(encoding="utf-8")
    print(f"读取: {TARGET_FILE}")
    print(f"源文件行数: {len(source.splitlines())}")
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"ERROR: 源文件语法错误: {e}")
        sys.exit(1)
    violations = find_except_logger_warnings(tree, source)
    print(f"\n=== R51 #5 违规统计 (except 块内 P0 必修) ===")
    print(f"违规数: {len(violations)}")
    if len(violations) == 0:
        print("无违规, 退出")
        return
    print(f"\n开始修复...")
    new_source = fix_exc_info(source, violations)
    # 验证新代码 AST 仍可解析
    try:
        new_tree = ast.parse(new_source)
    except SyntaxError as e:
        print(f"ERROR: 修复后语法错误: {e}")
        print("请手动回滚")
        sys.exit(1)
    # 验证修复数量
    new_violations = find_except_logger_warnings(new_tree, new_source)
    print(f"\n=== 修复后统计 ===")
    print(f"剩余违规: {len(new_violations)}")
    if len(new_violations) > 0:
        print("WARN: 部分位置未修复, 请检查")
    # 写回
    TARGET_FILE.write_text(new_source, encoding="utf-8")
    print(f"\n✅ 修复完成, 已写回 {TARGET_FILE}")
    print(f"修复数: {len(violations) - len(new_violations)}")


if __name__ == "__main__":
    main()
