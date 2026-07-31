#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R194-D 摘要生成 (写到文件)"""
import json
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

with open(PROJECT_ROOT / "_r194_d_strict_scan.json", encoding="utf-8") as f:
    data = json.load(f)

lines = []
lines.append("=" * 80)
lines.append("R194-D 修复后扫描结果")
lines.append("=" * 80)

total_p0 = 0
total_p1 = 0
for s in data:
    fname = s["file"].replace("\\", "/")
    lines.append(f"\n{fname}: P0={s['p0_count']}, P1={s['p1_count']}")
    total_p0 += s["p0_count"]
    total_p1 += s["p1_count"]

lines.append(f"\n{'=' * 80}")
lines.append(f"总计: P0={total_p0}, P1={total_p1}")
lines.append("=" * 80)

out = PROJECT_ROOT / "_r194_d_summary.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Written: {out}")
print("\n".join(lines))
