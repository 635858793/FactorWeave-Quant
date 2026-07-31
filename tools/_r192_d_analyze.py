#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R192-D 详细分析"""
import json
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding='utf-8')

with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_r192_d_scan.json', encoding='utf-8') as f:
    data = json.load(f)
data = [v for v in data if 'error' not in v]
for v in data:
    v['file'] = v['file'].replace('\\', '/')

out_lines = []
out_lines.append(f"Total violations: {len(data)}")
out_lines.append(f"P0: {sum(1 for v in data if v.get('severity')=='P0')}")
out_lines.append(f"P1: {sum(1 for v in data if v.get('severity')=='P1')}")

by_file = defaultdict(lambda: {'P0': 0, 'P1': 0, 'lines': []})
for v in data:
    sev = v.get('severity', 'P2')
    by_file[v['file']][sev] += 1
    by_file[v['file']]['lines'].append((v.get('line'), sev, v.get('type')))

sorted_files = sorted(by_file.items(), key=lambda x: (-x[1]['P0'], -x[1]['P1']))

out_lines.append("")
out_lines.append("=== Top 30 by P0 count ===")
for f, info in sorted_files[:30]:
    out_lines.append(f"  P0={info['P0']:3d} P1={info['P1']:3d}  {f}")

out_lines.append("")
out_lines.append("=== R190-R191 Priority Files ===")
priority = [
    'core/monitoring/sla_monitor.py',
    'core/services/service_bootstrap.py',
    'core/events/r84_event_helper.py',
    'core/coordinators/event_coordinator.py',
    'core/feature_flags/flag_manager.py',
    'core/importdata/unified_data_import_engine.py',
    'core/ui_integration/smart_data_integration.py',
]
for pf in priority:
    if pf in by_file:
        info = by_file[pf]
        out_lines.append(f"\n--- {pf} ---")
        out_lines.append(f"  P0={info['P0']}, P1={info['P1']}")
        for line, sev, vtype in info['lines'][:10]:
            out_lines.append(f"    L{line:4d} {sev} {vtype}")
    else:
        out_lines.append(f"\n--- {pf} --- NOT FOUND")

out_lines.append("")
out_lines.append("=== By subdir ===")
by_subdir = defaultdict(lambda: {'P0': 0, 'P1': 0})
for f, info in by_file.items():
    parts = f.split('/')
    if len(parts) >= 2:
        subdir = '/'.join(parts[:2])
    else:
        subdir = parts[0]
    by_subdir[subdir]['P0'] += info['P0']
    by_subdir[subdir]['P1'] += info['P1']
for sub, info in sorted(by_subdir.items(), key=lambda x: -x[1]['P0']):
    out_lines.append(f"  P0={info['P0']:4d} P1={info['P1']:4d}  {sub}")

# Save to file
with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_r192_d_analyze_out.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out_lines))

print("DONE")
