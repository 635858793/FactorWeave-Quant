#!/usr/bin/env python3
"""R154 子智能体 D: 跨 5 子目录寻找新发现的高价值 P1 候选"""
import json
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
with open(ROOT / "tools/r154_r51_full.json", "r", encoding="utf-8") as f:
    data = json.load(f)
p1 = [v for v in data["violations"] if v["severity"] == "P1"]

# 按文件分类, 重点关注业务关键路径
key_paths = {
    "trading_engine": "core/trading_engine.py",
    "position_manager": "core/position_manager.py",
    "risk_control": "core/risk_control.py",
    "stop_loss": "core/stop_loss.py",
    "take_profit": "core/take_profit.py",
    "order_processor": lambda v: "order" in v["file"].lower() and "core/" in v["file"],
    "money_manager": "core/money_manager.py",
    "trading_controller": "core/trading_controller.py",
    "account_manager": "core/trading/account_manager.py",
}

print("=== 关键业务路径 P1 候选 (未抽样) ===\n")

# 检查每个关键文件
seen_files = {"trading", "agents", "async", "coordinator", "duckdb", "data_import", "service"}
all_seen = defaultdict(int)

# 列出所有 P1 涉及的 trading/account/order/position 相关
for v in p1:
    f = v["file"]
    if any(k in f for k in ["trading_engine", "position_manager", "risk_control", "stop_loss", "take_profit", "order_processor", "money_manager", "trading_controller", "account_manager", "trading/"]):
        all_seen[f] += 1

print("--- 业务关键文件 P1 统计 ---")
for f, c in sorted(all_seen.items(), key=lambda x: -x[1]):
    print(f"  {c:3d} | {f}")

# 详细列出 trading_engine / position_manager / risk_control
print("\n--- 关键路径详细 ---")
for keyword in ["trading_engine.py", "position_manager.py", "risk_control.py", "stop_loss.py", "take_profit.py", "trading_controller.py", "money_manager.py", "trading/account_manager.py"]:
    matches = [v for v in p1 if keyword in v["file"]]
    if matches:
        print(f"\n  [{keyword}] {len(matches)} P1:")
        for v in matches[:10]:
            print(f"    L{v['line']:4d} {v['method']:40s} except={v['except_class']}")

# 重点查 trading_engine.py 全部 P1
trading_engine_p1 = [v for v in p1 if v["file"] == "core/trading_engine.py"]
print(f"\n=== core/trading_engine.py P1 详细 ===")
print(f"  总数: {len(trading_engine_p1)}")
for v in trading_engine_p1:
    print(f"    L{v['line']:4d} {v['method']:40s}")
    # 取上下文
    try:
        with open(ROOT / v["file"], "r", encoding="utf-8") as f:
            lines = f.readlines()
        ctx = "".join(f"{i+1:4d}| {lines[i].rstrip()}\n" for i in range(max(0, v["line"]-3), min(len(lines), v["line"]+1)))
        print(f"    上下文:\n{ctx}")
    except Exception as ex:
        print(f"    READ ERROR: {ex}")
