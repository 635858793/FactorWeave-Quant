"""Fix all unterminated f-strings in a file.

For each line, check if it has a logger.X(f"...{var}  (no closing quote).
"""
import re
import sys

file_path = sys.argv[1] if len(sys.argv) > 1 else 'core/agents/risk_agent.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
fixed_lines = []
fix_count = 0
i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.rstrip()
    # Pattern: logger.X(f"text: {expr  (no closing quote, no exc_info)
    if re.search(r'logger\.\w+\(f"[^"]*\{', stripped):
        # Check if line ends without closing quote
        if not re.search(r'\}\s*",?\s*exc_info\s*=\s*True\s*\)\s*$', stripped):
            # Need to fix
            m = re.match(r'^(\s*)logger\.(\w+)\(f"(.+?)\{([^}]+)\}\s*$', stripped)
            if m:
                indent = m.group(1)
                level = m.group(2)
                msg = m.group(3)
                var = m.group(4)
                fixed = f'{indent}logger.{level}(f"{msg}{{{var}}}", exc_info=True)'
                fixed_lines.append(fixed)
                print(f'L{i+1}: {stripped} -> {fixed}')
                fix_count += 1
                i += 1
                continue
    fixed_lines.append(line)
    i += 1

with open(file_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(fixed_lines))
print(f'\nFixed {fix_count} lines in {file_path}')
