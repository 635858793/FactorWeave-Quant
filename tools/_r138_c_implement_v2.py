"""R138 子智能体 C: AST 安全的批量实施 17 healthcheck + 22 dispose 钩子.

使用 AST 找到类末尾(避免在 try/except 中间插入的语法错误).
"""
import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 直接 import 模板
import importlib.util
spec = importlib.util.spec_from_file_location("_r138_c_implement_hooks", PROJECT_ROOT / "tools/_r138_c_implement_hooks.py")
hooks_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hooks_module)
HEALTHCHECK_TEMPLATES = hooks_module.HEALTHCHECK_TEMPLATES
DISPOSE_TEMPLATES = hooks_module.DISPOSE_TEMPLATES
HEALTHCHECK_FILES = hooks_module.HEALTHCHECK_FILES
DISPOSE_FILES = hooks_module.DISPOSE_FILES


def find_class_end_line(file_path: Path, class_name: str) -> int:
    """用 AST 找到类的真实结束行 (end_lineno)."""
    content = file_path.read_text(encoding='utf-8')
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"  [SYNTAX ERROR] {file_path}: {e}")
        return -1
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node.end_lineno
    return -1


def find_last_method_end_line(file_path: Path, class_name: str) -> int:
    """找到类内最后一个方法的结束行."""
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


def class_has_method(file_path: Path, class_name: str, method_name: str) -> bool:
    """检查指定类内是否已定义某方法."""
    content = file_path.read_text(encoding='utf-8')
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                    return True
    return False


def inject_method_safe(file_path: Path, class_name: str, method_name: str, method_code: str) -> bool:
    """使用 AST 找到类末尾后插入方法."""
    if not file_path.exists():
        print(f"  [SKIP] {file_path} 不存在")
        return False

    if class_has_method(file_path, class_name, method_name):
        print(f"  [EXISTS] {file_path.name}::{class_name} 已有 {method_name}")
        return True

    last_method_end = find_last_method_end_line(file_path, class_name)
    if last_method_end <= 0:
        print(f"  [FAIL] {file_path} 找不到 class {class_name} 或无方法")
        return False

    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')

    # 找到 last_method_end 行(0-indexed: last_method_end - 1)
    # 找到该方法体最后一行(连续有缩进的最后一行的下一空行)
    insert_idx = last_method_end  # 1-indexed: last_method_end 行的下一行
    # 跳过空行,找到下一个非空行
    while insert_idx < len(lines) and not lines[insert_idx].strip():
        insert_idx += 1
    # 实际插入点在 last_method_end 之后
    insert_idx = last_method_end  # 1-indexed

    # 在 last_method_end 行后插入空行 + method_code + 空行
    new_lines = lines[:insert_idx] + ['', method_code, ''] + lines[insert_idx:]
    new_content = '\n'.join(new_lines)

    # 验证语法
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        print(f"  [SYNTAX ERROR] {file_path.name}::{class_name}: {e}")
        return False

    file_path.write_text(new_content, encoding='utf-8')
    print(f"  [OK] {file_path.name}::{class_name} {method_name} 注入")
    return True


def main():
    print("=" * 60)
    print("R138 子智能体 C: AST 安全批量实施 17 healthcheck + 22 dispose 钩子")
    print("=" * 60)

    print("\n[Phase 1] healthcheck 17 候选实施:")
    success_hc = 0
    skip_hc = 0
    for cls_name, rel_path in HEALTHCHECK_FILES.items():
        file_path = PROJECT_ROOT / rel_path
        method_code = HEALTHCHECK_TEMPLATES.get(cls_name)
        if not method_code:
            print(f"  [NO_TEMPLATE] {cls_name}")
            continue
        result = inject_method_safe(file_path, cls_name, '_do_health_check', method_code)
        if result:
            success_hc += 1
        else:
            skip_hc += 1

    print("\n[Phase 2] dispose 22 候选实施:")
    success_dp = 0
    skip_dp = 0
    for cls_name, rel_path in DISPOSE_FILES.items():
        file_path = PROJECT_ROOT / rel_path
        method_code = DISPOSE_TEMPLATES.get(cls_name)
        if not method_code:
            print(f"  [NO_TEMPLATE] {cls_name}")
            continue
        result = inject_method_safe(file_path, cls_name, '_do_dispose', method_code)
        if result:
            success_dp += 1
        else:
            skip_dp += 1

    print(f"\n[Summary] healthcheck: {success_hc} success, {skip_hc} skipped")
    print(f"[Summary] dispose: {success_dp} success, {skip_dp} skipped")
    print(f"[Summary] Total: {success_hc + success_dp}/39 实施")

    print("\n" + "=" * 60)
    print("实施完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
