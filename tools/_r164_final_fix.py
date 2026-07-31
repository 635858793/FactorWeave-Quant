#!/usr/bin/env python3
"""R164 修复最后 2 个文件: trading_widget.py + enhanced_risk_monitor.py"""
from pathlib import Path

# Fix trading_widget.py L1026
p = Path('gui/widgets/trading_widget.py')
content = p.read_text(encoding='utf-8')
# 找到断开的 f-string 模式
old = 'logger.error(f"回测结果展示美化/多策略对比失败: {str(e})'
new = 'logger.error(f"回测结果展示美化/多策略对比失败: {str(e)}", exc_info=True)'
if old in content:
    content = content.replace(old, new)
    p.write_text(content, encoding='utf-8')
    print(f'Fixed: {p}')
else:
    print(f'NOT FOUND: {p}')

# Fix enhanced_risk_monitor.py L1530 indent
p = Path('core/risk_monitoring/enhanced_risk_monitor.py')
content = p.read_text(encoding='utf-8')
lines = content.split('\n')
# 找到 logger.error( 无缩进的位置
for i, line in enumerate(lines):
    if line == 'logger.error(' and i > 0 and 'fail-closed' in (lines[i+1] if i+1 < len(lines) else ''):
        lines[i] = '                logger.error('
        print(f'Fixed indent at L{i+1}: {p}')
        break
p.write_text('\n'.join(lines), encoding='utf-8')

print('Done')
