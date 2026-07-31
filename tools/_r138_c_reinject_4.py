"""R138 子智能体 C: 重新注入 4 个文件缺失的方法."""
import ast
from pathlib import Path
import importlib.util

# Import 模板
spec = importlib.util.spec_from_file_location("_r138_c_implement_hooks", Path('tools/_r138_c_implement_hooks.py'))
hooks_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hooks_module)

PROJECT_ROOT = Path('.').resolve()

# 4 个需要重新注入的文件
TARGETS = [
    ('ExtensionService', 'core/services/extension_service.py', '_do_health_check', hooks_module.HEALTHCHECK_TEMPLATES['ExtensionService']),
    ('GPUAccelerationManager', 'core/services/gpu_acceleration_manager.py', '_do_health_check', hooks_module.HEALTHCHECK_TEMPLATES['GPUAccelerationManager']),
    ('AISelectionBacktestService', 'core/services/ai_selection_backtest_service.py', '_do_dispose', hooks_module.DISPOSE_TEMPLATES['AISelectionBacktestService']),
    ('AISelectionRiskControlService', 'core/services/ai_selection_risk_control_service.py', '_do_dispose', hooks_module.DISPOSE_TEMPLATES['AISelectionRiskControlService']),
]


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


def has_method(file_path: Path, class_name: str, method_name: str) -> bool:
    """检查类内是否已定义某方法."""
    content = file_path.read_text(encoding='utf-8')
    tree = ast.parse(content)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                    return True
    return False


def inject_method(file_path: Path, class_name: str, method_name: str, method_code: str) -> bool:
    """在类内最后方法后插入新方法."""
    if has_method(file_path, class_name, method_name):
        print(f"  [EXISTS] {file_path.name}::{class_name}.{method_name}")
        return True

    last_end = find_last_method_end(file_path, class_name)
    if last_end <= 0:
        print(f"  [FAIL] {file_path.name} 找不到 {class_name}")
        return False

    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')

    # 在 last_end 行后插入
    insert_idx = last_end  # 0-indexed

    new_lines = lines[:insert_idx] + ['', method_code, ''] + lines[insert_idx:]
    new_content = '\n'.join(new_lines)

    try:
        ast.parse(new_content)
    except SyntaxError as e:
        print(f"  [SYNTAX] {file_path.name}::{class_name}: {e}")
        return False

    file_path.write_text(new_content, encoding='utf-8')
    print(f"  [OK] {file_path.name}::{class_name}.{method_name} injected at L{insert_idx + 1}")
    return True


for cls, rel, method, code in TARGETS:
    fp = PROJECT_ROOT / rel
    print(f"Processing: {rel}::{cls}.{method}")
    inject_method(fp, cls, method, code)
