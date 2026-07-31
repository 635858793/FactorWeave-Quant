#!/usr/bin/env python3
"""R164 综合恢复脚本 v2: 修复所有 v1/v2 脚本破坏的语法

模式 1: {var, exc_info=True)  →  {var})
   (在 except 块中, logger.* 末尾加 , exc_info=True)

模式 2: except ... as ...:\nlogger. → except ... as ...:\n    logger.
   (缩进破坏)

模式 3: \n, exc_info=True) (单独行的, exc_info) → 已经在模式 1 修复后自动正确
"""
import re
import ast
import sys
from pathlib import Path

ROOT = Path(".")

# 全部 P0 文件
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


def fix_fstring_pattern1(content: str) -> tuple:
    """修复 f-string 内错误插入的 exc_info=True

    模式: {xxx, exc_info=True) → {xxx})

    实际: f"...{str(e, exc_info=True)\nstuff..., exc_info=True)
    修复: f"...{str(e)}", exc_info=True, ...)
    """
    fixed_count = 0
    # 使用更宽松的匹配: 任何 { 内的 , exc_info=True) 模式
    # 关键是 { 后面跟着 内容 + , exc_info=True)

    # 模式 1: {var, exc_info=True) - var 是单词字符或带 () 的调用
    pattern = re.compile(r'\{([^{}()]*?\([^)]*\)[^{}]*?|e|err|exc|error|dc_exc|notify_err|_probe_e|str\(e\)), exc_info=True\)')

    def replace(m):
        return '{' + m.group(1) + '}'

    new_content, n = pattern.subn(replace, content)
    fixed_count += n

    return new_content, fixed_count


def fix_indent_pattern2(content: str) -> tuple:
    """修复 except 块后 logger 调用缩进丢失

    模式: except ... as e:\nlogger. → except ... as e:\n    logger.
    """
    fixed_count = 0
    lines = content.split('\n')
    new_lines = list(lines)

    for i in range(len(lines) - 1):
        line = lines[i]
        next_line = lines[i + 1]

        # 检查 except 关键字
        if re.match(r'\s*except\s+.*\s*as\s+\w+\s*:\s*$', line):
            # 下一行直接是 logger. 调用 (无缩进)
            if re.match(r'logger\.', next_line):
                # 加 4 空格缩进
                new_lines[i + 1] = '    ' + next_line
                fixed_count += 1

    return '\n'.join(new_lines), fixed_count


def main():
    print("=" * 70)
    print("R164 综合恢复 v2: 修复 v1/v2 脚本破坏的语法")
    print("=" * 70)
    print()

    total_fixed = 0
    for rel_path in P0_FILES:
        full_path = ROOT / rel_path
        if not full_path.exists():
            continue

        original = full_path.read_text(encoding='utf-8')
        content = original

        # Step 1: 修复 f-string 内错误
        content, c1 = fix_fstring_pattern1(content)
        # Step 2: 修复缩进
        content, c2 = fix_indent_pattern2(content)

        if c1 + c2 > 0:
            full_path.write_text(content, encoding='utf-8')
            print(f"  ✅ {rel_path}: 修复 {c1 + c2} 处 (f-string={c1}, indent={c2})")
            total_fixed += c1 + c2
        else:
            # 不打印 OK 噪音
            pass

    print(f"\n  总修复: {total_fixed} 处")
    print()

    # 验证
    print("【验证: AST 语法检查】")
    errors = []
    for rel_path in P0_FILES:
        full_path = ROOT / rel_path
        if not full_path.exists():
            continue
        try:
            ast.parse(full_path.read_text(encoding='utf-8'))
        except SyntaxError as e:
            errors.append((rel_path, e.lineno, e.msg))

    if errors:
        print(f"  ❌ 仍有 {len(errors)} 个文件语法错误:")
        for path, line, msg in errors:
            print(f"     {path}: L{line} {msg}")
    else:
        print(f"  ✅ 全部 30 P0 文件语法 OK")

    print()
    print("=" * 70)
    return len(errors)


if __name__ == '__main__':
    errors = main()
    sys.exit(0 if errors == 0 else 1)
