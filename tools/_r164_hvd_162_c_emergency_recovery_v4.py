#!/usr/bin/env python3
"""R164 综合恢复 v3.1: 简单版, 避免正则回溯崩溃"""
import re
import ast
import sys
from pathlib import Path

ROOT = Path(".")

P0_FILES = [
    'gui/dialogs/order_management_dialog.py',
    'gui/widgets/performance/tabs/risk_control_center_tab.py',
    'gui/widgets/trading_widget.py',
    'core/risk_monitoring/enhanced_risk_monitor.py',
    'gui/dialogs/account_management_dialog.py',
    'gui/widgets/trading_panel.py',
    'core/services/signal_trading_bridge.py',
    'gui/widgets/performance/tabs/trading_execution_monitor_tab.py',
    'core/services/ai_selection_risk_control_service.py',
    'core/agents/risk_agent.py',
    'core/risk_rule_manager.py',
    'gui/widgets/enhanced_ui/order_book_widget.py',
    'core/trading/account_manager.py',
    'core/risk_exporter.py',
    'core/risk/risk_event_subscribers.py',
    'core/risk_metrics.py',
    'gui/widgets/advanced_risk_control_widget.py',
    'core/performance/professional_risk_metrics.py',
    'gui/widgets/dynamic_risk_adjustment_widget.py',
    'gui/widgets/enhanced_trading_monitor_widget.py',
    'core/risk_alert.py',
    'gui/widgets/bettafish_dashboard/risk_assessment_panel.py',
    'gui/widgets/bettafish_dashboard/trading_signal_panel.py',
    'core/risk_monitoring/sherman_morrison_correlation.py',
    'gui/dialogs/risk_rule_config_dialog.py',
    'core/risk_control.py',
    'core/trading/signal_adapters.py',
    'core/trading/trading_mode.py',
    'gui/dialogs/signal_trading_bridge_dialog.py',
]


def fix_indent_simple(content: str) -> tuple:
    """简单行级修复: except 后 logger 缩进 + 孤立 exc_info 行合并"""
    lines = content.split('\n')
    new_lines = list(lines)
    fixed = 0

    for i in range(len(lines) - 1):
        line = lines[i]

        # 模式 1: except ... as ... :  \n logger.X(
        if re.match(r'\s*except\b.*\s*as\s+\w+\s*:\s*$', line):
            next_line = lines[i + 1]
            stripped = next_line.lstrip()
            if stripped.startswith('logger.'):
                # 计算 indent: except 的缩进 + 4
                except_indent = len(line) - len(line.lstrip())
                new_indent = ' ' * (except_indent + 4)
                if not new_lines[i + 1].startswith(new_indent):
                    new_lines[i + 1] = new_indent + stripped
                    fixed += 1
                    # 修复后, 重新读取
                    lines = new_lines

        # 模式 2: 独立行 `, exc_info=True)`
        if re.match(r'^\s*,\s*exc_info=True\s*\)\s*$', line):
            # 找上一个非空行, 合并
            j = i - 1
            while j >= 0 and new_lines[j].strip() == '':
                j -= 1
            if j >= 0:
                prev_line = new_lines[j]
                new_prev = prev_line.rstrip()
                if new_prev.endswith(','):
                    new_prev += ' exc_info=True,'
                elif new_prev.endswith('('):
                    new_prev += 'exc_info=True,'
                else:
                    new_prev += ', exc_info=True,'
                new_lines[j] = new_prev
                new_lines[i] = ''
                fixed += 1
                lines = new_lines

    return '\n'.join(new_lines), fixed


def fix_fstring_simple(content: str) -> tuple:
    """简单 f-string 修复: {xxx, exc_info=True) → {xxx}"""
    # 简单模式: 内部不含 }
    pattern = re.compile(r'\{([^}]*?),\s*exc_info=True\s*\)')
    new_content, n = pattern.subn(r'{\1})', content)
    return new_content, n


def main():
    total_fixed = 0
    for rel_path in P0_FILES:
        full_path = ROOT / rel_path
        if not full_path.exists():
            continue
        original = full_path.read_text(encoding='utf-8')
        content = original

        # Step 1: f-string 修复
        content, c1 = fix_fstring_simple(content)
        # Step 2: 缩进 + 孤立行修复
        content, c2 = fix_indent_simple(content)

        total = c1 + c2
        if total > 0:
            full_path.write_text(content, encoding='utf-8')
            print(f"  ✅ {rel_path}: 修复 {total} (f-string={c1}, indent/orphan={c2})")
            total_fixed += total

    print(f"\n总修复: {total_fixed}")
    print()

    errors = []
    for rel_path in P0_FILES:
        full_path = ROOT / rel_path
        if not full_path.exists():
            continue
        try:
            ast.parse(full_path.read_text(encoding='utf-8'))
        except SyntaxError as e:
            errors.append((rel_path, e.lineno, e.msg))
            print(f"  ❌ {rel_path}: L{e.lineno} {e.msg}")

    print()
    if errors:
        print(f"❌ 仍有 {len(errors)} 语法错误")
    else:
        print("✅ 全部 30 P0 文件语法 OK")
    return len(errors)


if __name__ == '__main__':
    sys.exit(0 if main() == 0 else 1)
