"""R174 R+1 round 二次验证: 检查 bettafish_agent.py + ai_selection_integration_service.py 的 exc_info 修复"""
import re
from pathlib import Path

files = [
    'core/agents/bettafish_agent.py',
    'core/services/ai_selection_integration_service.py',
]

for f in files:
    content = Path(f).read_text(encoding='utf-8')
    # Count all logger.error/warning/critical calls
    total = len(re.findall(r'logger\.(error|warning|critical)\(', content))
    # Count those with exc_info=True
    with_exc = 0
    # Simple line-based check
    in_logger = False
    logger_content = ''
    paren_depth = 0
    for line in content.split('\n'):
        # Detect start of logger.error/warning
        m = re.search(r'logger\.(error|warning|critical)\(', line)
        if m:
            in_logger = True
            paren_depth = line.count('(') - line.count(')')
            logger_content = line[m.start():]
            if paren_depth <= 0 and line.rstrip().endswith(')'):
                # Single line call
                if 'exc_info=True' in logger_content:
                    with_exc += 1
                in_logger = False
                logger_content = ''
        elif in_logger:
            paren_depth += line.count('(') - line.count(')')
            logger_content += line
            if paren_depth <= 0:
                if 'exc_info=True' in logger_content:
                    with_exc += 1
                in_logger = False
                logger_content = ''
    print(f'{f}: exc_info_compliance: {with_exc}/{total}')

# Also check: any leftover bad patterns?
print()
print('=== Bad patterns check ===')
for f in files:
    content = Path(f).read_text(encoding='utf-8')
    # Pattern 1: logger.X(, exc_info=True) - empty arg
    bad1 = re.findall(r'logger\.(error|warning|critical)\(\s*,\s*exc_info\s*=\s*True', content)
    # Pattern 2: logger.X(f"..." with no closing paren
    bad2 = re.findall(r'logger\.(error|warning|critical)\(\s*f["\'][^)]*$', content, re.MULTILINE)
    print(f'{f}: empty_arg={len(bad1)}, unterminated_fstring={len(bad2)}')
