"""R164 紧急修复 v8: 综合修复所有 exc_info 升级引入的语法错误

修复模式:
1. 缩进问题: `^(\s*)logger\.` 行但缩进不对齐
2. 缺少右括号: `, exc_info=True,` 或 `, exc_info=True)` 后无完整闭合
3. f-string 未闭合: 含 `(exc_info=True` 但后面无 `)`
4. 重复 exc_info: `, exc_info=True)", exc_info=True)` 等
"""
import re
import ast
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


def normalize_exc_info_calls(content: str) -> str:
    """规范化所有 logger.* (..., exc_info=True, 缺少闭合) 等错误"""

    # 模式 1: logger.error(f"...", exc_info=True)", exc_info=True) -> logger.error(f"...", exc_info=True)
    # 重复闭合
    for _ in range(3):
        content = re.sub(
            r'(logger\.\w+\([^)]*?,\s*exc_info=True\))(?:\s*,\s*exc_info=True\))+',
            r'\1',
            content,
        )

    # 模式 2: logger.error(f"...exc_info=True) 缺少右括号和参数
    # logger.error(f"xxx(exc_info=True)  -> logger.error("xxx", exc_info=True)
    content = re.sub(
        r'logger\.(error|warning|critical)\(f"([^"]*?\(exc_info=True)"\)',
        r'logger.\1("\2", exc_info=True)',
        content,
    )

    # 模式 3: f-string 内的 (exc_info=True) 移除
    # f"xxx (exc_info=True)yyy" -> f"xxx yyy"
    content = re.sub(
        r'f"([^"]*?)\s*\(exc_info=True\)\s*([^"]*?)"',
        r'f"\1\2"',
        content,
    )

    return content


def fix_indent_and_orphans(file_path: Path) -> int:
    """修复缩进和孤立行"""
    content = file_path.read_text(encoding='utf-8')
    original = content
    fix_count = 0

    lines = content.split('\n')
    new_lines = []

    for i, line in enumerate(lines):
        # 检测孤立行 ", exc_info=True," 或 ", exc_info=True)" 单独成行
        stripped = line.strip()
        if stripped in (', exc_info=True', ', exc_info=True,', ', exc_info=True)'):
            # 这是一个孤立行, 应该合并到前一行
            if new_lines:
                # 移除上一行末尾的换行, 合并
                prev = new_lines[-1]
                if prev.rstrip().endswith(('"', "'", ',', '(', 'exc_info=True')):
                    # 简化: 直接添加 exc_info=True) 到上一行
                    if prev.rstrip().endswith(','):
                        new_lines[-1] = prev.rstrip() + ' exc_info=True)'
                    elif '(' in prev and prev.rstrip().endswith('('):
                        new_lines[-1] = prev.rstrip() + 'exc_info=True)'
                    elif not prev.rstrip().endswith('exc_info=True)'):
                        new_lines[-1] = prev.rstrip() + ', exc_info=True)'
                    else:
                        new_lines[-1] = prev.rstrip()
                    fix_count += 1
                    continue
        new_lines.append(line)

    content = '\n'.join(new_lines)

    # 模式: except 块后缩进丢失
    # `except Exception as e:\nlogger.xxx(` 应该是 `except Exception as e:\n    logger.xxx(`
    content = re.sub(
        r'(except[^\n]*:\n)(?![\s\n])logger\.',
        r'\1    logger.',
        content,
    )

    if content != original:
        file_path.write_text(content, encoding='utf-8')
        return fix_count
    return 0


def main():
    print("=" * 60)
    print("R164 紧急修复 v8: 综合修复")
    print("=" * 60)
    for rel in TARGET_FILES:
        p = ROOT / rel
        if not p.exists():
            print(f'[SKIP] {rel}')
            continue

        # Step 1: 规范化 exc_info 调用
        content = p.read_text(encoding='utf-8')
        content = normalize_exc_info_calls(content)
        p.write_text(content, encoding='utf-8')

        # Step 2: 验证语法
        try:
            ast.parse(content, str(p))
            print(f'[OK]   {rel}')
        except SyntaxError as e:
            print(f'[FAIL] {rel}: line {e.lineno}: {e.msg}')


if __name__ == '__main__':
    main()
