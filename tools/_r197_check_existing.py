import json
from pathlib import Path

with open('tools/_r196_b_p0_scan.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

target_subdirs = ['core/ui', 'core/webgpu', 'core/importdata', 'core/advanced_optimization']
total_per_dir = {}
for sd in target_subdirs:
    sd_back = sd.replace('/', '\\')
    matches = [v for v in data['violations'] if sd_back in v['file']]
    total_per_dir[sd] = len(matches)
    print(f'=== {sd}: {len(matches)} violations ===')
    # Group by file
    by_file = {}
    for v in matches:
        fn = Path(v['file']).name
        by_file.setdefault(fn, []).append(v)
    for fn, vs in by_file.items():
        print(f'  {fn}: {len(vs)} violations')
        for v in vs[:3]:
            print(f'    L{v["line"]} {v["function"]} - {v["snippet"][:80]}')
    print()

print('Total: ', total_per_dir)
