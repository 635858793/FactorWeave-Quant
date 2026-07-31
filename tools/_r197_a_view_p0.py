"""Show P0 violations for fix selection"""
import json
from pathlib import Path

with open('tools/_r197_a_p0_scan.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

p0_violations = data['p0_violations_for_fix']
print(f"Total P0 violations: {len(p0_violations)}")
print()
# Group by file
from collections import defaultdict
by_file = defaultdict(list)
for v in p0_violations:
    fn = v['file'].split('\\')[-1]
    by_file[fn].append(v)

# Show all files with counts
for fn, vs in sorted(by_file.items(), key=lambda x: -len(x[1])):
    print(f"  {fn}: {len(vs)}")
    # Show first 2 violations in this file
    for v in vs[:2]:
        print(f"    L{v['line']} - {v['snippet'][:80]}")
    print()
