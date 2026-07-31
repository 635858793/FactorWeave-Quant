#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R194-D 任务清单总览"""
import json
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

with open(PROJECT_ROOT / "_r193_d_strict_scan.json", encoding="utf-8") as f:
    data = json.load(f)

# 顺序: 业务关键度递减
print("=" * 80)
print("R194-D 修复清单 (5 个核心 Service + main_window_coordinator)")
print("=" * 80)
for s in data:
    fname = s["file"].replace("\\", "/")
    print(f"\n{fname}: P0={s['p0_count']}, P1={s['p1_count']}")
    for v in s["violations"][:20]:
        line = v.get("line", "?")
        method = v.get("method", "?")
        kind = v.get("silent_type") or v.get("violation_kind", "?")
        sev = v.get("severity", "?")
        body = v.get("body_preview", "")[:50]
        print(f"  [{sev}] L{line:>5d}  {method:35s}  {kind:18s}  {body}")
    if len(s["violations"]) > 20:
        print(f"  ... ({len(s['violations']) - 20} more)")

# 总计
total_p0 = sum(s["p0_count"] for s in data)
total_p1 = sum(s["p1_count"] for s in data)
print(f"\n总计: P0={total_p0}, P1={total_p1}")
