#!/usr/bin/env python3
"""R154 子智能体 D: 详细查看关键未抽样 P1 violations"""
import json
from pathlib import Path
from collections import Counter

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
with open(ROOT / "tools/r154_r51_full.json", "r", encoding="utf-8") as f:
    data = json.load(f)
p1 = [v for v in data["violations"] if v["severity"] == "P1"]

# 重点关注: account_manager / risk_control / order_*
print("=== account_manager.py P1 全部 ===")
for v in [x for x in p1 if x["file"] == "core/trading/account_manager.py"]:
    try:
        with open(ROOT / v["file"], "r", encoding="utf-8") as f:
            lines = f.readlines()
        ctx = "".join(f"{i+1:4d}| {lines[i].rstrip()}\n" for i in range(max(0, v["line"]-4), min(len(lines), v["line"]+1)))
        print(f"\n  L{v['line']:4d} {v['method']}")
        print(f"  except: {v['except_class']}")
        print(f"  上下文:\n{ctx}")
    except Exception as ex:
        print(f"  READ ERROR: {ex}")

print("\n\n=== risk_control_center_tab.py P1 抽样 (前 5) ===")
rcc_p1 = [v for v in p1 if v["file"] == "gui/widgets/performance/tabs/risk_control_center_tab.py"]
for v in rcc_p1[:5]:
    try:
        with open(ROOT / v["file"], "r", encoding="utf-8") as f:
            lines = f.readlines()
        ctx = "".join(f"{i+1:4d}| {lines[i].rstrip()}\n" for i in range(max(0, v["line"]-3), min(len(lines), v["line"]+1)))
        print(f"\n  L{v['line']:4d} {v['method']}")
        print(f"  上下文:\n{ctx}")
    except Exception as ex:
        print(f"  READ ERROR: {ex}")

# 检查 asset_database_manager / risk_manager
print("\n\n=== risk_manager P1 ===")
for v in [x for x in p1 if "risk_manager" in x["file"]]:
    print(f"  {v['file']}:L{v['line']} {v['method']}")

print("\n\n=== order_*/position_manager P1 ===")
for v in [x for x in p1 if "order" in x["file"].lower() or "position" in x["file"].lower()]:
    print(f"  {v['file']}:L{v['line']} {v['method']}")

# 关键服务 Service
print("\n\n=== 关键服务 P1 (前 20) ===")
service_p1 = [v for v in p1 if "services/" in v["file"]]
print(f"  Services P1 总数: {len(service_p1)}")
from collections import Counter
file_counter = Counter(v["file"] for v in service_p1)
for f, c in file_counter.most_common(20):
    print(f"  {c:3d} | {f}")
