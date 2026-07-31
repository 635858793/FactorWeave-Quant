"""R183-A 服务启动期阶段分析工具 - 临时脚本"""
import re
import sys

with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\service_bootstrap.py", 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find all _register_* methods
pattern = re.compile(r'^    def (_register_\w+)\(')
current_method = None
current_start = 0
method_lines = {}

for i, line in enumerate(lines, 1):
    m = pattern.match(line)
    if m:
        if current_method:
            method_lines[current_method] = (current_start, i-1, i-1-current_start+1)
        current_method = m.group(1)
        current_start = i

if current_method:
    method_lines[current_method] = (current_start, len(lines), len(lines)-current_start+1)

# Print sorted by start line
print(f"{'Method':<55} {'Start':>6} {'End':>6} {'Lines':>6}")
print('-'*80)
for method, (start, end, n) in sorted(method_lines.items(), key=lambda x: x[1][0]):
    print(f"{method:<55} {start:>6} {end:>6} {n:>6}")

# Find bootstrap() main call sequence
print("\n\n--- bootstrap() main sequence ---")
for i, line in enumerate(lines, 1):
    if 'bootstrap' in line.lower() and 'self._register' in line and 'self.bootstrap' not in line:
        print(f"  L{i}: {line.rstrip()}")
