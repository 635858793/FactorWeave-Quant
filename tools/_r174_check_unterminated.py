"""R174: 查看具体 unterminated_fstring 模式"""
import re
from pathlib import Path

files = [
    'core/agents/bettafish_agent.py',
    'core/services/ai_selection_integration_service.py',
]

for f in files:
    content = Path(f).read_text(encoding='utf-8')
    matches = re.finditer(r'logger\.(error|warning|critical)\(\s*f["\'][^)]*$', content, re.MULTILINE)
    print(f'=== {f} ===')
    for m in matches:
        # Find line number
        line_num = content[:m.start()].count('\n') + 1
        line = content.split('\n')[line_num-1]
        # Next 2 lines for context
        all_lines = content.split('\n')
        next1 = all_lines[line_num] if line_num < len(all_lines) else ''
        print(f'L{line_num}: {line.strip()[:80]}')
        print(f'  +1: {next1.strip()[:80]}')
