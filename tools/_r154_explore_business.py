#!/usr/bin/env python3
"""R154 子智能体 D: 寻找新发现的高价值 P1 候选 (业务关键路径)"""
import json
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
with open(ROOT / "tools/r154_r51_full.json", "r", encoding="utf-8") as f:
    data = json.load(f)
p1 = [v for v in data["violations"] if v["severity"] == "P1"]

# 检查更细的字段
print("=== 重点业务路径: services/ (前 30) ===")
service_p1 = [v for v in p1 if "services/" in v["file"]]
file_counter = Counter(v["file"] for v in service_p1)
for f, c in file_counter.most_common(30):
    print(f"  {c:3d} | {f}")

# 显示 bettafish_monitoring_integration 全部
print("\n=== bettafish_monitoring_integration.py P1 全部 ===")
for v in [x for x in p1 if x["file"] == "core/services/bettafish_monitoring_integration.py"]:
    try:
        with open(ROOT / v["file"], "r", encoding="utf-8") as f:
            lines = f.readlines()
        ctx = "".join(f"{i+1:4d}| {lines[i].rstrip()}\n" for i in range(max(0, v["line"]-3), min(len(lines), v["line"]+1)))
        print(f"\n  L{v['line']:4d} {v['method']}")
        print(f"  上下文:\n{ctx}")
    except Exception as ex:
        print(f"  READ ERROR: {ex}")

print("\n=== sector_fund_flow_service.py P1 全部 ===")
for v in [x for x in p1 if x["file"] == "core/services/sector_fund_flow_service.py"]:
    try:
        with open(ROOT / v["file"], "r", encoding="utf-8") as f:
            lines = f.readlines()
        ctx = "".join(f"{i+1:4d}| {lines[i].rstrip()}\n" for i in range(max(0, v["line"]-3), min(len(lines), v["line"]+1)))
        print(f"\n  L{v['line']:4d} {v['method']}")
        print(f"  上下文:\n{ctx}")
    except Exception as ex:
        print(f"  READ ERROR: {ex}")

# 新候选: 业务关键路径
print("\n=== ai_selection_integration_service.py P1 全部 ===")
for v in [x for x in p1 if x["file"] == "core/services/ai_selection_integration_service.py"]:
    try:
        with open(ROOT / v["file"], "r", encoding="utf-8") as f:
            lines = f.readlines()
        ctx = "".join(f"{i+1:4d}| {lines[i].rstrip()}\n" for i in range(max(0, v["line"]-3), min(len(lines), v["line"]+1)))
        print(f"\n  L{v['line']:4d} {v['method']}")
        print(f"  上下文:\n{ctx}")
    except Exception as ex:
        print(f"  READ ERROR: {ex}")
