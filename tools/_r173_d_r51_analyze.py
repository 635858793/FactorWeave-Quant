#!/usr/bin/env python3
"""R173-D R51 #5 扫描结果分析脚本"""
import json
import os
from collections import defaultdict

REPORTS_DIR = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\.trae\reports\rounds"
FILES = [
    "audit_r173_d_r51_core.json",
    "audit_r173_d_r51_plugins.json",
    "audit_r173_d_r51_gui.json",
]

all_violations = []
for fname in FILES:
    path = os.path.join(REPORTS_DIR, fname)
    if not os.path.exists(path):
        print(f"NOT FOUND: {path}")
        continue
    try:
        d = json.load(open(path, encoding="utf-8"))
        s = d.get("summary", {})
        print(f"\n=== {fname} ===")
        print(f"  Total violations: {s.get('total_violations', '?')}")
        print(f"  Exempt: {s.get('exempt_count', '?')}")
        print(f"  By severity: {s.get('by_severity', {})}")
        print(f"  By pattern: {s.get('by_pattern', {})}")
        # Collect violations
        for v in d.get("violations", []):
            v["_source"] = fname
            all_violations.append(v)
    except Exception as e:
        print(f"Error reading {path}: {e}")

print(f"\n=== Total collected: {len(all_violations)} violations ===")

# Aggregate by file
by_file = defaultdict(int)
by_pattern = defaultdict(int)
by_severity = defaultdict(int)
for v in all_violations:
    by_file[v.get("file", "unknown")] += 1
    by_pattern[v.get("pattern", "unknown")] += 1
    by_severity[v.get("severity", "unknown")] += 1

print("\n=== By Severity ===")
for k, v in sorted(by_severity.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

print("\n=== By Pattern ===")
for k, v in sorted(by_pattern.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

print("\n=== Top 20 files by violation count ===")
for k, v in sorted(by_file.items(), key=lambda x: -x[1])[:20]:
    print(f"  {v:4d}  {k}")
