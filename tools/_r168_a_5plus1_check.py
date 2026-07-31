"""R168-A: check service_bootstrap.py for 5+1 service registrations"""
import re

with open('core/services/service_bootstrap.py', 'r', encoding='utf-8') as f:
    content = f.read()
lines = content.split('\n')

# Look for specific registration patterns
keywords = ['RiskManager', 'MoneyManager', 'RiskControlStrategy', 'AccountManager', 'TradingService']
for keyword in keywords:
    print(f'\n{"=" * 80}')
    print(f'KEYWORD: {keyword}')
    print(f'{"=" * 80}')
    for i, line in enumerate(lines):
        if re.search(rf'\b{keyword}\b', line):
            start = max(0, i - 2)
            end = min(len(lines), i + 2)
            for j in range(start, end):
                marker = '>' if j == i else ' '
                print(f'{marker} L{j+1}: {lines[j]}')
            print()
