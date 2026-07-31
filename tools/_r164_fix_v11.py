"""R164 紧急修复 v11: 用 line-based approach"""
from pathlib import Path
p = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\widgets\trading_widget.py")
lines = p.read_text(encoding='utf-8').split('\n')

# L1194 (0-indexed 1193)
target = 1193
old_line = lines[target]
print(f'L{target+1} (before): {repr(old_line)}')

# 检查 L1195
print(f'L{target+2}: {repr(lines[target+1])}')

# Replace
if '\u5206\u6790\u5f02\u5e38' in old_line and 'exc_info' not in old_line:
    new_line = old_line.rstrip() + '", exc_info=True)'
    lines[target] = new_line
    p.write_text('\n'.join(lines), encoding='utf-8')
    print(f'L{target+1} (after): {repr(new_line)}')
    print('[FIXED]')
else:
    print('[NOT NEEDED]')

# 同样修复 account_manager.py L542
p2 = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\trading\account_manager.py")
lines2 = p2.read_text(encoding='utf-8').split('\n')
# L542 (0-indexed 541)
target2 = 541
old_line2 = lines2[target2]
print(f'\nL{target2+1}: {repr(old_line2)}')
