"""R164 紧急修复 v9: 修复特定行"""
from pathlib import Path

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui").resolve()

FIXES = [
    # trading_widget.py L1194
    (
        'gui/widgets/trading_widget.py',
        'logger.error(f"分析异常: {str(e)}',
        'logger.error(f"分析异常: {str(e)}", exc_info=True)',
    ),
    # enhanced_risk_monitor.py L1977 缩进问题
    # 直接修改行内容
]

# 修复 enhanced_risk_monitor.py L1977 (logger.error 缩进错误)
p = ROOT / 'core/risk_monitoring/enhanced_risk_monitor.py'
content = p.read_text(encoding='utf-8')
lines = content.split('\n')
if 1976 < len(lines) and 'logger.error(' in lines[1976]:
    # L1977 (0-indexed 1976) 是 `logger.error(`, 但前面应该缩进 24 空格
    line_1977 = lines[1976]
    if not line_1977.startswith('                            '):
        # 添加 24 空格缩进
        lines[1976] = '                            ' + line_1977.lstrip()
    # L1980 也需要修正缩进
    if 1979 < len(lines) and "hhi_violation_rule, hhi_warn_rule, hhi_grade = True, True, 'RED'" in lines[1979]:
        line_1980 = lines[1979]
        if not line_1980.startswith('                            '):
            lines[1979] = '                            ' + line_1980.lstrip()
    # L1978 L1979 也需要缩进
    for i in [1977, 1978]:
        if i < len(lines) and lines[i].lstrip().startswith('"') or (i < len(lines) and '"HHI 检查失败' in lines[i]):
            line = lines[i]
            if not line.startswith('                                '):  # 32 空格
                lines[i] = '                                ' + line.lstrip()
    p.write_text('\n'.join(lines), encoding='utf-8')
    print('[FIX] enhanced_risk_monitor.py L1977-1980 缩进')

# 修复 account_manager.py L541 缩进
p = ROOT / 'core/trading/account_manager.py'
content = p.read_text(encoding='utf-8')
lines = content.split('\n')
if 540 < len(lines) and 'logger.warning(f"账户不存在: {account_id}")' in lines[540]:
    line_541 = lines[540]
    if not line_541.startswith('                    '):
        lines[540] = '                    ' + line_541.lstrip()
    p.write_text('\n'.join(lines), encoding='utf-8')
    print('[FIX] account_manager.py L541 缩进')

# 修复 trading_widget.py L1194
p = ROOT / 'gui/widgets/trading_widget.py'
content = p.read_text(encoding='utf-8')
old = 'logger.error(f"分析异常: {str(e)}'
new = 'logger.error(f"分析异常: {str(e)}", exc_info=True)'
if old in content:
    content = content.replace(old, new, 1)
    p.write_text(content, encoding='utf-8')
    print('[FIX] trading_widget.py L1194')

print('Done')
