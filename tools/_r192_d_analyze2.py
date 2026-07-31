#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R192-D 详细分析 v2 - 排除 ImportError 模式 + 真实 P0 分类"""
import json
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding='utf-8')

with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_r192_d_scan.json', encoding='utf-8') as f:
    data = json.load(f)
data = [v for v in data if 'error' not in v]
for v in data:
    v['file'] = v['file'].replace('\\', '/')

# 排除 ImportError 模式 (合规)
data_filtered = []
for v in data:
    et = v.get('exception_type', '')
    if 'ImportError' in et:
        # ImportError: pass 是常规模式, 跳过
        continue
    data_filtered.append(v)

out_lines = []
out_lines.append(f"Total violations (excluding ImportError): {len(data_filtered)}")
out_lines.append(f"  P0: {sum(1 for v in data_filtered if v.get('severity')=='P0')}")
out_lines.append(f"  P1: {sum(1 for v in data_filtered if v.get('severity')=='P1')}")

# 按文件统计
by_file = defaultdict(lambda: {'P0': 0, 'P1': 0, 'p0_lines': [], 'p1_lines': []})
for v in data_filtered:
    sev = v.get('severity', 'P2')
    by_file[v['file']][sev] += 1
    if sev == 'P0':
        by_file[v['file']]['p0_lines'].append((v.get('line'), v.get('exception_type'), v.get('body_summary', [])[:1]))
    else:
        by_file[v['file']]['p1_lines'].append((v.get('line'), v.get('type'), v.get('reason', '')))

sorted_files = sorted(by_file.items(), key=lambda x: (-x[1]['P0'], -x[1]['P1']))

out_lines.append("")
out_lines.append("=== Top 20 by P0 count (excluding ImportError) ===")
for f, info in sorted_files[:20]:
    out_lines.append(f"  P0={info['P0']:3d} P1={info['P1']:3d}  {f}")

# 重点关注的 R190-R191 修改文件
out_lines.append("")
out_lines.append("=== R190-R191 Priority Files (Detail) ===")
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
        for line, et, body in info['p0_lines']:
            out_lines.append(f"    L{line:4d} P0 {et} | body: {body}")
        for line, vtype, reason in info['p1_lines'][:5]:
            out_lines.append(f"    L{line:4d} P1 {vtype} | {reason[:60]}")
    else:
        out_lines.append(f"\n--- {pf} --- (not in scan output)")

# By subdir
out_lines.append("")
out_lines.append("=== By subdir (excluding ImportError) ===")
by_subdir = defaultdict(lambda: {'P0': 0, 'P1': 0, 'files': 0})
for f, info in by_file.items():
    parts = f.split('/')
    if len(parts) >= 2:
        subdir = '/'.join(parts[:2])
    else:
        subdir = parts[0]
    by_subdir[subdir]['P0'] += info['P0']
    by_subdir[subdir]['P1'] += info['P1']
    by_subdir[subdir]['files'] += 1
for sub, info in sorted(by_subdir.items(), key=lambda x: -x[1]['P0']):
    out_lines.append(f"  P0={info['P0']:4d} P1={info['P1']:4d}  files={info['files']:3d}  {sub}")

# 业务关键路径 (event_bus/DB/service_bootstrap) exc_info 覆盖率
out_lines.append("")
out_lines.append("=== Business critical path coverage ===")
critical_files = [
    'core/events/event_bus.py',
    'core/services/service_bootstrap.py',
    'core/importdata/database_writer.py',
    'core/importdata/unified_data_import_engine.py',
    'core/importdata/import_execution_engine.py',
    'core/coordinators/event_coordinator.py',
    'core/coordinators/main_window_coordinator.py',
]
for cf in critical_files:
    if cf in by_file:
        info = by_file[cf]
        out_lines.append(f"  P0={info['P0']:3d} P1={info['P1']:3d}  {cf}")
    else:
        out_lines.append(f"  (合规) {cf}")

# 关键 P0 待修复清单 (Top 30 跨文件, 排除 ImportError)
out_lines.append("")
out_lines.append("=== Top 30 P0 silent failures (across all files) ===")
all_p0 = []
for f, info in by_file.items():
    for line, et, body in info['p0_lines']:
        all_p0.append((f, line, et, body))
all_p0.sort(key=lambda x: x[1])
for f, line, et, body in all_p0[:30]:
    out_lines.append(f"  L{line:4d}  {f}  | {et} | {body[0] if body else ''}")

with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_r192_d_analyze2_out.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out_lines))

print("DONE")
