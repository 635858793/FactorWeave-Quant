# Fix script - run with: python fix_syntax.py
file_path = r'db\models\llm_config_models.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Count occurrences - use raw string to avoid escaping
target = '`' + 'n'
count = content.count(target)
print(f'Found {count} occurrences of backtick-n')

# Replace all
replacement = '\n'
fixed_content = content.replace(target + '            with db.get_connection() as conn:', replacement + '            with db.get_connection() as conn:')

# Count after fix
fixed_count = fixed_content.count(target)
print(f'After fix: {fixed_count} occurrences remaining')

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print('File has been fixed!')

# Verify syntax
import py_compile
try:
    py_compile.compile(file_path, doraise=True)
    print('Syntax verification passed!')
except py_compile.PyCompileError as e:
    print(f'Syntax error: {e}')
