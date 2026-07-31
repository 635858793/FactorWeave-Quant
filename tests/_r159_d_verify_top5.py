"""R159-D R+1 round 假修复鉴别: 实测 R159-A 修复 615 处是否真实"""
import ast
import re
from pathlib import Path

PROJECT_ROOT = Path('d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui')

TOP_5 = [
    'core/coordinators/main_window_coordinator.py',
    'gui/widgets/enhanced_data_import_widget.py',
    'core/ui/panels/right_panel.py',
    'core/trading/order_service.py',
    'core/importdata/import_execution_engine.py',
]


def has_exc_info(call):
    for kw in call.keywords:
        if kw.arg == 'exc_info':
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
    return False


def is_p0_logger(node):
    if isinstance(node.func, ast.Attribute):
        if node.func.attr in ('error', 'critical'):
            return True
    return False


def in_except(tree, line):
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for h in node.handlers:
                if h.lineno <= line <= (h.end_lineno or h.lineno):
                    return True
    return False


print("=" * 70)
print("R159-A R+1 round 实测验证: 615 处 fix 真实核对")
print("=" * 70)
print()

results = []
for f in TOP_5:
    path = PROJECT_ROOT / f
    if not path.exists():
        print(f"  [SKIP] {f}")
        continue
    src = path.read_text(encoding='utf-8', errors='replace')
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f"  [SYNTAX ERROR] {f}: {e}")
        continue

    missing = 0
    total_exc_info = 0
    total_logger = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and is_p0_logger(node):
            total_logger += 1
            if has_exc_info(node):
                total_exc_info += 1
                continue
            if in_except(tree, node.lineno):
                missing += 1

    results.append({
        'file': f,
        'total_logger_error_critical': total_logger,
        'total_exc_info': total_exc_info,
        'missing_in_except': missing,
    })
    print(f"  {f}")
    print(f"    total logger.error/critical: {total_logger}")
    print(f"    total exc_info=True: {total_exc_info}")
    print(f"    missing in except block: {missing}")

# 总体
print()
print("=" * 70)
print("R159-A 总计")
print("=" * 70)
total_logger = sum(r['total_logger_error_critical'] for r in results)
total_exc = sum(r['total_exc_info'] for r in results)
total_missing = sum(r['missing_in_except'] for r in results)
print(f"  总 logger.error/critical: {total_logger}")
print(f"  总 exc_info=True: {total_exc}")
print(f"  总 except 块内仍缺 exc_info: {total_missing}")
print(f"  R159-A 声明 fix 数: 615")
print(f"  R159-D R+1 round 实测验证: 缺={total_missing}, 期望=0 → {'✅ 真修复' if total_missing == 0 else '🔴 假修复'}")
