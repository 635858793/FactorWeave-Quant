#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R194-A: trading_service.py + ai_selection_integration_service.py 详细 P0/P1 验证
- HVD-193-DB: trading_service.py 13 P0 位置精确验证
- HVD-193-DD: ai_selection_integration_service.py 1 P1 缺 exc_info 验证
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_JSON = PROJECT_ROOT / "_r192_d_scan.json"

with open(SCAN_JSON, "r", encoding="utf-8") as f:
    violations = json.load(f)

# trading_service.py 全部 P0
print(f"\n=== HVD-193-DB: trading_service.py 13 P0 完整列表 ===")
trading_p0 = [v for v in violations if v.get("file") == "core\\services\\trading_service.py" and v.get("severity") == "P0"]
for v in trading_p0:
    body = v.get("body_summary", [])
    print(f"L{v['line']:5d} | {v.get('type'):25s} | exc={v.get('exception_type', '?'):30s}")
    for b in body[:2]:
        print(f"      body: {b[:90]}")

# trading_service.py 全部 P1
print(f"\n=== trading_service.py P1 列表 ===")
trading_p1 = [v for v in violations if v.get("file") == "core\\services\\trading_service.py" and v.get("severity") == "P1"]
for v in trading_p1:
    print(f"L{v['line']:5d} | {v.get('type'):30s} | {v.get('reason', '')[:80]}")

# ai_selection_integration_service.py 全部 P0 + P1
print(f"\n=== HVD-193-DD: ai_selection_integration_service.py 全部违例 ===")
ais_p0 = [v for v in violations if v.get("file") == "core\\services\\ai_selection_integration_service.py" and v.get("severity") == "P0"]
ais_p1 = [v for v in violations if v.get("file") == "core\\services\\ai_selection_integration_service.py" and v.get("severity") == "P1"]
print(f"\n--- P0 静默 ({len(ais_p0)} 处) ---")
for v in ais_p0:
    body = v.get("body_summary", [])
    print(f"L{v['line']:5d} | {v.get('type'):25s} | exc={v.get('exception_type', '?'):30s}")
    for b in body[:1]:
        print(f"      body: {b[:100]}")
print(f"\n--- P1 缺 exc_info/低级别 ({len(ais_p1)} 处) ---")
for v in ais_p1:
    loggers = v.get("loggers", v.get("methods", []))
    print(f"L{v['line']:5d} | {v.get('type'):30s} | {v.get('reason', '')[:80]}")
    if loggers:
        print(f"      loggers: {loggers}")

# 找 order_service 和 risk_manager / account_manager
print(f"\n=== order_service.py / risk_manager.py / account_manager.py 验证 ===")
for f in ["core\\services\\order_service.py", "core\\services\\risk_manager.py", "core\\services\\account_manager.py"]:
    p0 = [v for v in violations if v.get("file") == f and v.get("severity") == "P0"]
    p1 = [v for v in violations if v.get("file") == f and v.get("severity") == "P1"]
    print(f"\n{f}: P0={len(p0)}, P1={len(p1)}")
    if p0:
        for v in p0[:3]:
            print(f"  L{v['line']} P0: {v.get('type')} exc={v.get('exception_type')}")
