"""修复 ai_selection_backtest_service.py 中被破坏的 _do_dispose 注入."""
import ast
from pathlib import Path

fp = Path('core/services/ai_selection_backtest_service.py')
content = fp.read_text(encoding='utf-8')
lines = content.split('\n')

# 删除 L1227-L1251 (0-indexed: 1226-1250)
# L1227 = '    def _do_dispose(self) -> None:'
# L1251 = '            super()._do_dispose()'
# L1252 = '' (空行)
# 保留 L1252 空行
# 删除 1226-1250 (25 行)
new_lines = lines[:1226] + lines[1252:]
new_content = '\n'.join(new_lines)
fp.write_text(new_content, encoding='utf-8')
print('Fixed: removed broken _do_dispose at L1227-L1251')

# 验证
try:
    ast.parse(new_content)
    print('Syntax OK')
except SyntaxError as e:
    print(f'Syntax error: {e}')
