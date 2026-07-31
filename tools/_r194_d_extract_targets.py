#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R194-D 任务清单提取"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

with open(PROJECT_ROOT / "_r193_d_strict_scan.json", encoding="utf-8") as f:
    data = json.load(f)

for s in data:
    fname = s["file"].replace("\\", "/")
    if "trading_service" in fname or "ai_selection_integration" in fname:
        print(f"\n=== {fname} ===")
        for v in s["violations"]:
            line = v.get("line", "?")
            method = v.get("method", "?")
            kind = v.get("silent_type") or v.get("violation_kind", "?")
            sev = v.get("severity", "?")
            body = v.get("body_preview", "")[:60]
            print(f"  L{line:>5d}  {method:35s}  [{sev}] {kind:18s}  | body: {body}")
