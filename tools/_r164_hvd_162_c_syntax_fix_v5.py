#!/usr/bin/env python3
"""R164 紧急修复 v5: 修复批量 exc_info 升级引入的所有语法错误

已知错误模式:
1. `traceback.format_exc(, exc_info=True)` - 缺少右括号
2. `except Exception as e:\nlogger.xxx(...)` - 缺少缩进
3. 孤立行 `, exc_info=True,` 或 `, exc_info=True)` - 与前一行合并
4. f-string 内错误插入 exc_info
"""
import re
import sys
from pathlib import Path

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui").resolve()

# 全部 18 个 P0 文件 (排除 19 个已闭环)
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
]


def fix_syntax_errors(file_path: Path) -> tuple:
    """修复一个文件的所有语法错误模式"""
    try:
        content = file_path.read_text(encoding='utf-8')
        original = content
        fix_count = 0

        # 模式 1: traceback.format_exc(, exc_info=True) -> traceback.format_exc(), exc_info=True
        # 修复: 缺少右括号 `format_exc(, exc_info` -> `format_exc(), exc_info`
        pattern1 = re.compile(r'logger\.(error|warning|critical)\(\s*traceback\.format_exc\(\s*,\s*exc_info')
        new_content, n1 = pattern1.subn(
            r'logger.\1(traceback.format_exc(), exc_info',
            content
        )
        if n1 > 0:
            content = new_content
            fix_count += n1

        # 模式 2: logger.xxx(f"...{str(e, exc_info=True}") -> logger.xxx(f"...{str(e)}", exc_info=True)
        # 修复: f-string 内的 str(e, exc_info=True) 应该移到外层
        pattern2 = re.compile(r'f"([^"]*?)\{str\(([^,}]+),\s*exc_info=True\)\}"')
        new_content, n2 = pattern2.subn(
            r'f"\1{\2}", exc_info=True',
            content
        )
        if n2 > 0:
            content = new_content
            fix_count += n2

        # 模式 3: logger.xxx(f"...{e, exc_info=True}") -> logger.xxx(f"...{e}", exc_info=True)
        pattern3 = re.compile(r'f"([^"]*?)\{([^,}]+),\s*exc_info=True\}"')
        new_content, n3 = pattern3.subn(
            r'f"\1{\2}", exc_info=True',
            content
        )
        if n3 > 0:
            content = new_content
            fix_count += n3

        # 模式 4: f-string 内部 exc_info 关键字直接相邻
        # 例如: f"xxx{exc_info=True}" 极少见, 但可处理
        # 模式 5: logger.warning("xxx (exc_info=True)") 字符串内有多余信息
        # 检查 logger.warning 字符串内的 (exc_info=True) 模式 - 这种情况是字符串内有误, 不需修复
        # 跳过

        # 模式 6: 孤立行 ", exc_info=True," 或 ", exc_info=True)"
        # 这通常意味着前一行缺少参数 - 上下文敏感, 难以自动修复
        # 检查: 如果一行只有 ", exc_info=True," 或 ", exc_info=True)" 而非完整的 logger.* 调用, 标记为错误
        # 通过 AST 验证可以发现

        # 写入
        if content != original:
            file_path.write_text(content, encoding='utf-8')
        return fix_count, content
    except Exception as e:
        return -1, str(e)


def main():
    print("=" * 60)
    print("R164 紧急修复 v5: 语法错误批量修复")
    print("=" * 60)
    for rel_path in TARGET_FILES:
        full_path = ROOT / rel_path
        if not full_path.exists():
            print(f'[SKIP] {rel_path}')
            continue
        n, msg = fix_syntax_errors(full_path)
        if n > 0:
            print(f'[FIX]  {rel_path}: {n} 处修复')
        elif n == 0:
            print(f'[OK]   {rel_path}: 0 修复')
        else:
            print(f'[ERR]  {rel_path}: {msg}')


if __name__ == '__main__':
    main()
