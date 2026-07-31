#!/usr/bin/env python3
"""R164 综合恢复脚本 v3: 智能修复所有损坏模式

模式分析:
1. `except ... as e:\nlogger.` → `except ... as e:\n    logger.` (缩进)
2. `, exc_info=True)\n` 后跟下一个 except/方法 (多余逗号) → 正常化

采用 Python AST 验证作为最终断言。
"""
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


def fix_indent_broken_except(content: str) -> tuple:
    """修复 except 块后 logger 调用缩进丢失

    模式: except ... as ...:\nlogger. → except ... as ...:\n    logger.

    关键是 except 行结束后, 下一行直接以 logger. 开头 (无缩进)
    """
    fixed_count = 0
    lines = content.split('\n')
    new_lines = list(lines)

    for i in range(len(lines) - 1):
        line = lines[i]
        next_line = lines[i + 1]

        # 检查 except 关键字 (可带变量名)
        if re.match(r'\s*except\b.*\s*as\s+\w+\s*:\s*$', line):
            # 下一行直接是 logger. 调用 (无缩进)
            stripped = next_line.lstrip()
            if stripped.startswith('logger.'):
                # 加 except 缩进 (通常是 4 空格, 但需匹配)
                # 计算 except 的缩进
                except_indent = len(line) - len(line.lstrip())
                new_indent = ' ' * (except_indent + 4)
                if not new_lines[i + 1].startswith(new_indent):
                    new_lines[i + 1] = new_indent + stripped
                    fixed_count += 1

    return '\n'.join(new_lines), fixed_count


def fix_comma_exc_info_orphan_line(content: str) -> tuple:
    """修复孤立行的 `, exc_info=True)`

    模式: 内容\n, exc_info=True)\n → 内容, exc_info=True)\n

    当 exc_info=True) 出现在单独一行 (没有缩进), 说明上一个 logger.warning(
    的闭合被破坏
    """
    fixed_count = 0
    lines = content.split('\n')
    new_lines = list(lines)

    for i in range(len(lines) - 1):
        line = lines[i]
        next_line = lines[i + 1] if i + 1 < len(lines) else ''

        # 检测孤立 `, exc_info=True)` (没有缩进)
        if re.match(r'^\s*,\s*exc_info=True\s*\)', line):
            # 找上一个 logger.warning( 或 logger.error( 开始的行
            # 把这个 exc_info=True) 合并到上一个非空行
            j = i - 1
            while j >= 0 and new_lines[j].strip() == '':
                j -= 1
            if j >= 0:
                prev_line = new_lines[j]
                # 把 ", exc_info=True)" 添加到 prev_line 末尾
                new_prev = prev_line.rstrip()
                if new_prev.endswith(','):
                    new_prev += ' exc_info=True,'
                elif new_prev.endswith('('):
                    new_prev += 'exc_info=True,'
                else:
                    new_prev += ', exc_info=True,'
                new_lines[j] = new_prev
                # 当前行设为空 (或保留)
                new_lines[i] = ''
                fixed_count += 1

    return '\n'.join(new_lines), fixed_count


def main():
    print("=" * 70)
    print("R164 综合恢复 v3: 智能修复 v1/v2 脚本破坏的语法")
    print("=" * 70)
    print()

    total_fixed = 0
    for rel_path in P0_FILES:
        full_path = ROOT / rel_path
        if not full_path.exists():
            continue

        original = full_path.read_text(encoding='utf-8')
        content = original

        # Step 1: 修复 f-string 内错误 (单行/多行)
        # 模式: {str(e, exc_info=True) → {str(e}) 单行
        # 多行: f"..." \n, exc_info=True) → 已经在 step 2 处理
        fstring_pattern = re.compile(r'\{((?:[^{}]|\{[^}]*\})*?),\s*exc_info=True\s*\)')
        fstring_count = 0
        new_content = content
        while True:
            new_content, n = fstring_pattern.subn(r'{\1})', new_content, count=1)
            fstring_count += n
            if n == 0:
                break
        content = new_content

        # Step 2: 修复 except 块后 logger 缩进
        content, c2 = fix_indent_broken_except(content)

        # Step 3: 修复孤立 `, exc_info=True)` 行
        content, c3 = fix_comma_exc_info_orphan_line(content)

        # Step 4: 清理多余空行
        content = re.sub(r'\n\n\n+', '\n\n', content)

        total = fstring_count + c2 + c3
        if total > 0:
            full_path.write_text(content, encoding='utf-8')
            print(f"  ✅ {rel_path}: 修复 {total} 处 (f-string={fstring_count}, indent={c2}, orphan={c3})")
            total_fixed += total

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
