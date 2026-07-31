#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R194-A 子智能体: Top 5 Service 重新精确扫描
- 使用 _r192_d_scanner 的 JSON 输出
- 按文件分组统计 P0 数量
- 输出 Top 10 排名
"""
import json
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_JSON = PROJECT_ROOT / "_r192_d_scan.json"

with open(SCAN_JSON, "r", encoding="utf-8") as f:
    violations = json.load(f)

# 按文件分组统计 P0
p0_by_file = Counter()
p1_by_file = Counter()
p0_details = {}

for v in violations:
    if "error" in v:
        continue
    f = v.get("file", "?")
    sev = v.get("severity", "P2")
    if sev == "P0":
        p0_by_file[f] += 1
        p0_details.setdefault(f, []).append({
            "line": v.get("line"),
            "type": v.get("type"),
            "exc": v.get("exception_type", "?"),
            "body": v.get("body_summary", [])[:2],
            "reason": v.get("reason", "")
        })
    elif sev == "P1":
        p1_by_file[f] += 1

print(f"\n=== R194-A 重扫 P0 统计 ===")
print(f"总 P0 静默失败: {sum(p0_by_file.values())}")
print(f"总 P1 缺 exc_info/低级别: {sum(p1_by_file.values())}")
print(f"\n=== Top 20 P0 静默失败文件排名 ===")

top20 = p0_by_file.most_common(20)
for rank, (f, cnt) in enumerate(top20, 1):
    print(f"{rank:2d}. {cnt:3d} P0  {f}")

print(f"\n=== Top 5 累计: {sum(c for _, c in top20[:5])} P0 ===")
print(f"=== Top 10 累计: {sum(c for _, c in top20[:10])} P0 ===")
print(f"=== Top 20 累计: {sum(c for _, c in top20)} P0 ===")

# 重点服务详细分析
focus_services = [
    "core\\services\\ai_selection_risk_control_service.py",
    "core\\services\\trading_service.py",
    "core\\services\\order_service.py",
    "core\\services\\unified_data_manager.py",
    "core\\services\\service_bootstrap.py",
    "core\\services\\ai_selection_integration_service.py",
    "core\\services\\ai_prediction_service.py",
    "core\\services\\cache_service.py",
    "core\\services\\enhanced_realtime_data_manager.py",
    "core\\services\\realtime_compute_engine.py",
    "core\\coordinators\\main_window_coordinator.py",
]

print(f"\n=== 重点服务 P0 详情 ===")
for svc in focus_services:
    p0 = p0_by_file.get(svc, 0)
    p1 = p1_by_file.get(svc, 0)
    print(f"\n{svc}")
    print(f"  P0 静默: {p0} 处, P1 缺 exc_info: {p1} 处")
    if svc in p0_details:
        for d in p0_details[svc][:5]:
            print(f"  - L{d['line']:5d} | {d['type']:25s} | exc={d['exc']:30s}")
            for b in d.get('body', [])[:1]:
                print(f"      body: {b[:80]}")
