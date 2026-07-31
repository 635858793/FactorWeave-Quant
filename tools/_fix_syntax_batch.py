"""Batch fix unterminated f-strings.

The line is like: logger.error(f"text{var)  - var is the expression, missing " between } and ).
"""
import sys
import re

file_path = sys.argv[1] if len(sys.argv) > 1 else 'core/agents/risk_agent.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed_lines = []
fix_count = 0
for i, line in enumerate(lines):
    stripped = line.rstrip('\n').rstrip('\r')
    # Pattern: logger.X(f"text{var) - var is "str(e", the } is f-string expression close, ) is function call close
    # But the f-string itself is missing closing ". The var captured is without trailing ")"
    # var is "str(e" (the expression without closing paren)
    m = re.match(r'^(\s*)logger\.(\w+)\(f"(.+)\{([^}]+)\}\)\s*$', stripped)
    if m:
        indent = m.group(1)
        level = m.group(2)
        msg = m.group(3)
        var = m.group(4)  # e.g. "str(e" - the expression content without closing
        # The actual expression in the broken code was: {var + ")" + }
        # So the original expression is: str(e)
        # But var captured is "str(e" - missing the ")"
        # We need to add the ")" back to the var before closing the f-string
        # The fix: f"text{var})", exc_info=True)
        # That is: f"text{str(e)}", exc_info=True)
        fixed_line = f'{indent}logger.{level}(f"{msg}{{{var})}}", exc_info=True)\n'
        fixed_lines.append(fixed_line)
        print(f'L{i+1}: {stripped} -> {fixed_line.rstrip()}')
        fix_count += 1
    else:
        fixed_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)
print(f'\nFixed {fix_count} lines in {file_path}')
