"""
R161 R51 铁律 #5 批量修复脚本
- 自动识别所有 logger.error/critical 缺 exc_info=True 位置
- 对单行调用 + 多行调用分别处理
- 失败时仍写回已修复部分
"""
import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple

TARGETS = [
    Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\advanced_risk_control_service.py"),
    Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\unified_data_manager.py"),
    Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\service_bootstrap.py"),
]


def find_violations(file_path: Path) -> List[Tuple[int, int, str]]:
    """找出所有 logger.error/critical 缺 exc_info 的位置
    返回: [(line, end_line, level), ...]
    """
    src = file_path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    violations = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in ("error", "critical"):
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "logger":
            continue

        has_exc_info = any(kw.arg == "exc_info" for kw in node.keywords)
        if has_exc_info:
            continue

        start = node.lineno
        end = node.end_lineno or node.lineno
        violations.append((start, end, node.func.attr))

    return violations


def fix_violations(file_path: Path) -> Tuple[int, int]:
    """修复所有违规. 返回 (修复数, 失败数)"""
    violations = find_violations(file_path)
    if not violations:
        return 0, 0

    src = file_path.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)

    # 创建备份
    backup = file_path.with_suffix(file_path.suffix + ".bak_r161")
    backup.write_text(src, encoding="utf-8")

    fixed = 0
    failed = 0
    # 从后往前修复, 避免行号偏移
    for start, end, level in sorted(violations, key=lambda x: -x[0]):
        # 检查是否已有 exc_info (再次确认)
        block_text = "".join(lines[start - 1:end])
        if "exc_info" in block_text:
            continue

        # 单行调用: logger.error(...)
        if start == end:
            old_line = lines[start - 1]
            # 寻找匹配的右括号
            stripped = old_line.rstrip()
            if stripped.endswith(")"):
                # 替换为 logger.X(..., exc_info=True)
                # 找到 ")" 之前的位置
                idx = stripped.rfind(")")
                new_line = stripped[:idx] + ", exc_info=True)" + "\n"
                # 处理可能有 `,` 紧挨 `)` 的情况
                if new_line.endswith(", exc_info=True)\n"):
                    lines[start - 1] = new_line
                    fixed += 1
                else:
                    failed += 1
            else:
                failed += 1
        else:
            # 多行调用: 在最后一个右括号前加 exc_info=True
            last_line = lines[end - 1]
            stripped = last_line.rstrip()
            # 找到最后一个 `)` 的位置
            idx = stripped.rfind(")")
            if idx == -1:
                failed += 1
                continue
            new_line = stripped[:idx] + ", exc_info=True)" + "\n"
            lines[end - 1] = new_line
            fixed += 1

    # 写回文件
    new_content = "".join(lines)
    file_path.write_text(new_content, encoding="utf-8")
    return fixed, failed


def main():
    total_fixed = 0
    total_failed = 0
    for tf in TARGETS:
        if not tf.exists():
            print(f"SKIP: {tf.name} 不存在")
            continue
        f, fl = fix_violations(tf)
        total_fixed += f
        total_failed += fl
        print(f"{tf.name}: 修复 {f}, 失败 {fl}")

    print(f"\n总计: 修复 {total_fixed}, 失败 {total_failed}")
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
