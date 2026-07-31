"""R164 紧急修复 v6: 修复特定行的语法错误"""
from pathlib import Path

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui").resolve()

# 修复目标 (file, line, search_text, replace_text)
FIXES = [
    (
        'gui/widgets/trading_widget.py',
        1163,
        '            logger.error(f"清除数据失败: {str(e)}',
        '            logger.error(f"清除数据失败: {str(e)}", exc_info=True)',
    ),
    (
        'core/risk_monitoring/enhanced_risk_monitor.py',
        1535,
        'logger.error(f"风险评分失败: {str(e)}',
        'logger.error(f"风险评分失败: {str(e)}", exc_info=True)',
    ),
    (
        'core/services/ai_selection_risk_control_service.py',
        2276,
        'logger.warning(f"[R118-P0-3][_check_risk_limits] _get_current_position_count 异常',
        'logger.warning(f"[R118-P0-3][_check_risk_limits] _get_current_position_count 异常(降级): {e}", exc_info=True)',
    ),
    (
        'core/trading/account_manager.py',
        597,
        'logger.warning(',
        '                    logger.warning(',
    ),
]


def main():
    for rel, line, old, new in FIXES:
        p = ROOT / rel
        if not p.exists():
            print(f'[SKIP] {rel}')
            continue
        content = p.read_text(encoding='utf-8')
        if old in content:
            content = content.replace(old, new)
            p.write_text(content, encoding='utf-8')
            print(f'[FIX]  {rel} (L{line})')
        else:
            print(f'[NOT FOUND] {rel} (L{line})')
            # 打印上下文
            lines = content.split('\n')
            for i in range(max(0, line-3), min(len(lines), line+2)):
                print(f'  L{i+1}: {lines[i][:120]}')


if __name__ == '__main__':
    main()
