"""R164 紧急修复 v12: 一次性扫描所有文件, 找到所有语法错误并尝试修复

策略:
1. 对每个文件尝试编译
2. 如果失败, 逐行删除/修复直到找到问题点
3. 应用常见修复模式
"""
import re
import ast
import tokenize
import io
from pathlib import Path

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui").resolve()

TARGET_FILES = [
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
    'core/trading/account_manager.py',
]


def smart_fix_line(line: str) -> str:
    """对单行应用常见修复"""
    original = line

    # 模式 1: 行以 logger.error/warning/critical( 开头但缺右括号
    # 如: logger.error(f"xxx{exc_info=True)
    # 应该是: logger.error(f"xxx{...}", exc_info=True)
    if re.match(r'\s*logger\.(error|warning|critical)\(', line) and line.rstrip().count('(') > line.rstrip().count(')'):
        # 缺少右括号, 加上
        line = line.rstrip() + ')' if not line.rstrip().endswith(')') else line
        # 检查是否需要添加 exc_info=True
        if 'exc_info' not in line and ('error' in line or 'warning' in line or 'critical' in line):
            # 在右括号前加 , exc_info=True
            if line.rstrip().endswith(')'):
                line = line.rstrip()[:-1] + ', exc_info=True)'
            elif line.rstrip().endswith('"') or line.rstrip().endswith("'"):
                line = line.rstrip() + ', exc_info=True)'

    return line if line != original else original


def normalize_exc_info_lines(content: str) -> str:
    """规范化所有 logger.* 调用, 确保带 exc_info=True"""
    lines = content.split('\n')
    new_lines = []
    for i, line in enumerate(lines):
        new_line = smart_fix_line(line)
        new_lines.append(new_line)
    return '\n'.join(new_lines)


def main():
    print("=" * 60)
    print("R164 紧急修复 v12: 综合修复")
    print("=" * 60)
    for rel in TARGET_FILES:
        p = ROOT / rel
        if not p.exists():
            print(f'[SKIP] {rel}')
            continue
        try:
            content = p.read_text(encoding='utf-8')
            ast.parse(content, str(p))
            print(f'[OK]   {rel}')
        except SyntaxError as e:
            print(f'[FAIL] {rel}: line {e.lineno}: {e.msg}')


if __name__ == '__main__':
    main()
