#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R194-D 查看剩余 P0 详情"""
import json
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

with open(PROJECT_ROOT / "_r194_d_strict_scan.json", encoding="utf-8") as f:
    data = json.load(f)

lines = []
lines.append("=" * 80)
lines.append("R194-D 剩余 P0 详情 (按文件)")
lines.append("=" * 80)

for s in data:
    fname = s["file"].replace("\\", "/")
    p0_violations = [v for v in s["violations"] if v.get("severity") == "P0"]
    if not p0_violations:
        continue
    lines.append(f"\n{fname}: P0 剩余 {len(p0_violations)} 处")
    for v in p0_violations:
        line = v.get("line", "?")
        method = v.get("method", "?")
        kind = v.get("silent_type") or v.get("violation_kind", "?")
        body = v.get("body_preview", "")[:80]
        lines.append(f"  L{line:>5d}  {method:35s}  {kind:25s}  body: {body}")

lines.append(f"\n{'=' * 80}")
total_p0 = sum(s["p0_count"] for s in data)
lines.append(f"总计: P0={total_p0}")
lines.append("=" * 80)

out = PROJECT_ROOT / "_r194_d_remaining.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Written: {out}")
