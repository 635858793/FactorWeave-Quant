"""Fix unterminated f-strings in risk_agent.py."""
import re
import sys

file_path = 'core/agents/risk_agent.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
fixed_lines = []
fix_count = 0
for i, line in enumerate(lines):
    # Pattern 1: logger.X(f"....{yyy  (ends with { but not closing quote)
    # Detect: logger.(error|warning|info|debug)\(f"([^"]*)\{[^}]+$
    match = re.match(r'^(\s*)(logger\.(?:error|warning|info|debug))\(f"([^"]*?)\{([^}]+)\s*$', line)
    if match:
        indent = match.group(1)
        level = match.group(2)
        msg_part = match.group(3)
        var_part = match.group(4)
        # Reconstruct: logger.error(f"msg{var}", exc_info=True)
        # var_part is something like 'str(e)' or 'e'
        fixed = f'{indent}{level}(f"{msg_part}{{{var_part}}}", exc_info=True)'
        fixed_lines.append(fixed)
        print(f'Fixing L{i+1}: {line.strip()} -> {fixed.strip()}')
        fix_count += 1
    else:
        fixed_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(fixed_lines))
print(f'\nFixed {fix_count} lines')
