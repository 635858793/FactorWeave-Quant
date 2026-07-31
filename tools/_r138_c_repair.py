"""R138 子智能体 C: 综合修复脚本.

策略:
1. 对每个目标文件,先检查并删除所有错误的 _do_health_check / _do_dispose 注入
2. 用 AST 找到类末尾,正确插入方法
"""
import ast
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path('.').resolve()

# 模板
TEMPLATES = {}

# Import 模板从 _r138_c_implement_hooks
import importlib.util
spec = importlib.util.spec_from_file_location("_r138_c_implement_hooks", PROJECT_ROOT / "tools/_r138_c_implement_hooks.py")
hooks_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hooks_module)
HEALTHCHECK_TEMPLATES = hooks_module.HEALTHCHECK_TEMPLATES
DISPOSE_TEMPLATES = hooks_module.DISPOSE_TEMPLATES
HEALTHCHECK_FILES = hooks_module.HEALTHCHECK_FILES
DISPOSE_FILES = hooks_module.DISPOSE_FILES


def find_method_ranges_in_class(file_path: Path, class_name: str, method_name: str) -> list:
    """找到类内指定方法的所有定义范围 (1-indexed start, end)."""
    content = file_path.read_text(encoding='utf-8')
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    ranges = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                    ranges.append((item.lineno, item.end_lineno))
    return ranges


def remove_method_from_class(file_path: Path, class_name: str, method_name: str) -> bool:
    """从类中删除指定方法(包括其前后空行)."""
    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')
    ranges = find_method_ranges_in_class(file_path, class_name, method_name)
    if not ranges:
        return False

    # 收集所有要删除的行(0-indexed)
    to_remove = set()
    for start, end in ranges:
        for i in range(start - 1, end):
            to_remove.add(i)
        # 删除方法前的空行
        i = start - 2  # 方法前一行
        while i >= 0 and lines[i].strip() == '':
            to_remove.add(i)
            i -= 1
        # 删除方法后的空行
        i = end  # 方法后一行 (1-indexed end 行的下一行 = end (0-indexed))
        while i < len(lines) and lines[i].strip() == '':
            to_remove.add(i)
            i += 1

    new_lines = [l for i, l in enumerate(lines) if i not in to_remove]
    new_content = '\n'.join(new_lines)
    file_path.write_text(new_content, encoding='utf-8')
    print(f"  [REMOVED] {file_path.name}::{class_name} {method_name} ({len(ranges)} occurrences)")
    return True


def find_class_end(file_path: Path, class_name: str) -> int:
    """用 AST 找到类结束行 (1-indexed, end_lineno)."""
    content = file_path.read_text(encoding='utf-8')
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"  [SYNTAX] {file_path.name}: {e}")
        return -1
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node.end_lineno
    return -1


def find_last_method_end(file_path: Path, class_name: str) -> int:
    """用 AST 找到类内最后一个方法的结束行 (1-indexed)."""
    content = file_path.read_text(encoding='utf-8')
    tree = ast.parse(content)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            last_end = 0
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if hasattr(item, 'end_lineno') and item.end_lineno:
                        last_end = max(last_end, item.end_lineno)
            return last_end
    return -1


def inject_method_at_class_end(file_path: Path, class_name: str, method_name: str, method_code: str) -> bool:
    """在类内最后一个方法后插入新方法."""
    last_end = find_last_method_end(file_path, class_name)
    if last_end <= 0:
        print(f"  [FAIL] {file_path.name}::{class_name}: 找不到类或无方法")
        return False

    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')

    # 找到 last_end 行 (0-indexed: last_end - 1)
    # 在 last_end 行后插入空行 + method_code
    # last_end 是 1-indexed 结束行 (e.g. 322 = L322 是方法最后一行)
    # 0-indexed: 322 - 1 = 321
    # 在 lines[322] (last_end 行后) 插入
    insert_idx = last_end  # 0-indexed: 这是 last_end 后的位置

    # 跳过连续空行
    while insert_idx < len(lines) and lines[insert_idx].strip() == '':
        insert_idx += 1

    # 找到下一个非空行(类的下一行或文件末尾)
    # 实际上我们要在 last_end 后插入(确保空行)
    # 简化: 直接在 last_end 后插入
    insert_idx = last_end

    # 检查插入位置是否合适 - 不在 except/else/finally 后
    # 简单方法:确保插入位置前的最后非空行不以 `:` (except/else/finally) 结尾
    # 但这复杂,直接插入看语法

    new_lines = lines[:insert_idx] + ['', method_code, ''] + lines[insert_idx:]
    new_content = '\n'.join(new_lines)

    # 验证语法
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        print(f"  [SYNTAX ERROR after inject] {file_path.name}::{class_name} {method_name}: {e}")
        return False

    file_path.write_text(new_content, encoding='utf-8')
    print(f"  [OK] {file_path.name}::{class_name} {method_name} injected at L{insert_idx + 1}")
    return True


def process_file(cls_name: str, rel_path: str, method_name: str, templates: dict) -> bool:
    """处理一个文件:删除错误的注入,然后正确注入."""
    file_path = PROJECT_ROOT / rel_path
    if not file_path.exists():
        print(f"  [SKIP] {file_path} 不存在")
        return False

    template = templates.get(cls_name)
    if not template:
        print(f"  [NO TEMPLATE] {cls_name}")
        return False

    # 1. 删除错误的注入(类内已有的同名方法)
    remove_method_from_class(file_path, cls_name, method_name)

    # 2. 在类末尾正确注入
    return inject_method_at_class_end(file_path, cls_name, method_name, template)


def main():
    print("=" * 60)
    print("R138 子智能体 C: 综合修复 + AST 安全注入")
    print("=" * 60)

    print("\n[Phase 1] healthcheck 17 候选:")
    for cls_name, rel_path in HEALTHCHECK_FILES.items():
        process_file(cls_name, rel_path, '_do_health_check', HEALTHCHECK_TEMPLATES)

    print("\n[Phase 2] dispose 22 候选:")
    for cls_name, rel_path in DISPOSE_FILES.items():
        process_file(cls_name, rel_path, '_do_dispose', DISPOSE_TEMPLATES)

    print("\n" + "=" * 60)
    print("修复完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
