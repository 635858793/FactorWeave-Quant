#!/usr/bin/env python3
"""R165 终极验证脚本 - 严格 AST 感知 (避免静默 catch SyntaxError)

R164-D 子智能体 B 发现 R164-A-续期脚本 BUG: catch SyntaxError 静默吞, 假 [OK]
本工具: 严格区分 SyntaxError (🟡 待修) vs missing=0 (🟢 闭环)
"""
import ast
import sys
from pathlib import Path

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

# P0 业务核心 18 文件
P0_FILES = [
    'gui/dialogs/order_management_dialog.py',
    'gui/widgets/performance/tabs/risk_control_center_tab.py',
    'gui/widgets/trading_widget.py',
    'core/risk_monitoring/enhanced_risk_monitor.py',
    'gui/dialogs/account_management_dialog.py',
    'gui/widgets/trading_panel.py',
    'gui/widgets/performance/tabs/trading_execution_monitor_tab.py',
    'core/services/ai_selection_risk_control_service.py',
    'gui/widgets/enhanced_ui/order_book_widget.py',
    'core/risk/risk_event_subscribers.py',
    'gui/widgets/advanced_risk_control_widget.py',
    'gui/widgets/dynamic_risk_adjustment_widget.py',
    'gui/widgets/enhanced_trading_monitor_widget.py',
    'gui/widgets/bettafish_dashboard/risk_assessment_panel.py',
    'gui/widgets/bettafish_dashboard/trading_signal_panel.py',
    'core/risk_monitoring/sherman_morrison_correlation.py',
    'gui/dialogs/risk_rule_config_dialog.py',
    'gui/dialogs/signal_trading_bridge_dialog.py',
]

# R162 HVD-161-B 假修复文件 (R+1 round 发现)
R162_FALSE_FIX = {
    'core/trading/account_repository.py': 7,
    'core/trading/order_event_handlers.py': 3,
}


def analyze(file_path: Path) -> tuple:
    """返回 (status, missing_count, detail)
    status: 'OK' / 'SYNTAX_ERROR' / 'MISSING' / 'NOT_FOUND'
    """
    if not file_path.exists():
        return 'NOT_FOUND', 0, '文件不存在'
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return 'NOT_FOUND', 0, f'读取失败: {e}'
    try:
        tree = ast.parse(content)
    except (SyntaxError, IndentationError) as e:
        return 'SYNTAX_ERROR', 0, f'L{e.lineno}: {e.msg}'

    # AST 感知统计
    missing = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if not (isinstance(child.func, ast.Attribute)
                    and child.func.attr in ('error', 'warning', 'critical')
                    and isinstance(child.func.value, ast.Name)
                    and child.func.value.id == 'logger'):
                continue
            if not any(kw.arg == 'exc_info' for kw in child.keywords):
                missing += 1
    return ('OK' if missing == 0 else 'MISSING'), missing, ''


def main():
    print("=" * 80)
    print("R165 终极验证 - P0 业务核心 18 文件 + R162 假修复 2 文件")
    print("=" * 80)

    print("\n=== P0 业务核心 18 文件 ===")
    p0_ok = 0
    p0_missing = 0
    p0_syntax = 0
    for rel in P0_FILES:
        fp = ROOT / rel
        status, missing, detail = analyze(fp)
        if status == 'OK':
            print(f"  [OK] {rel}")
            p0_ok += 1
        elif status == 'SYNTAX_ERROR':
            print(f"  [SYNTAX_ERROR] {rel}: {detail}")
            p0_syntax += 1
        elif status == 'MISSING':
            print(f"  [MISSING] {rel}: {missing} missing")
            p0_missing += 1
        else:
            print(f"  [NOT_FOUND] {rel}: {detail}")

    print(f"\n  P0 统计: {p0_ok} OK, {p0_syntax} SYNTAX_ERROR, {p0_missing} MISSING")

    print("\n=== R162 HVD-161-B 假修复 2 文件 ===")
    r162_missing = 0
    for rel, expected in R162_FALSE_FIX.items():
        fp = ROOT / rel
        status, missing, detail = analyze(fp)
        if status == 'OK':
            print(f"  [OK] {rel}: 0 missing")
        elif status == 'SYNTAX_ERROR':
            print(f"  [SYNTAX_ERROR] {rel}: {detail}")
        else:
            print(f"  [MISSING] {rel}: {missing} missing (R+1 round 报告 {expected})")
            r162_missing += missing

    print(f"\n  R162 假修复总计: {r162_missing} missing (待修)")

    return 0 if p0_syntax == 0 and p0_missing == 0 and r162_missing == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
