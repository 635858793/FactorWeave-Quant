#!/usr/bin/env python3
"""R154 子智能体 D: 重点高价值 P1 候选深度 4 源验证"""
import json
from pathlib import Path

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
with open(ROOT / "tools/r154_r51_full.json", "r", encoding="utf-8") as f:
    data = json.load(f)
p1 = [v for v in data["violations"] if v["severity"] == "P1"]

# 新发现的潜在高价值 P1
new_candidates = [
    {"file": "core/services/uni_plugin_data_manager.py", "line": 929, "context_note": "get_statistics 业务核心统计, plugin_center 失败降级"},
    {"file": "core/services/uni_plugin_data_manager.py", "line": 938, "context_note": "get_statistics 风险质量统计, risk_manager 失败降级"},
    {"file": "core/services/uni_plugin_data_manager.py", "line": 947, "context_note": "get_statistics 路由统计, tet_engine 失败降级"},
    {"file": "core/services/database_service.py", "line": 4832, "context_note": "_deserialize_value 类型转换降级"},
    {"file": "core/services/cache_service.py", "line": 1324, "context_note": "warm_up 单条预热失败"},
    {"file": "gui/dialogs/order_management_dialog.py", "line": 2300, "context_note": "create_order 资产验证一级 fallback"},
    {"file": "gui/dialogs/order_management_dialog.py", "line": 2313, "context_note": "create_order 资产验证二级 fallback"},
    {"file": "core/services/new_stock_fetcher.py", "line": 150, "context_note": "新股 K线 EastMoney 适配器失败"},
    {"file": "core/services/dividend_data_service.py", "line": 170, "context_note": "AKShare 分红接口失败"},
    {"file": "core/services/enhanced_data_manager.py", "line": 424, "context_note": "数据准确性价格波动检测"},
    {"file": "core/services/performance_service.py", "line": 740, "context_note": "BacktestResultManager 不可用"},
    {"file": "core/services/sector_fund_flow_service.py", "line": 680, "context_note": "数据源支持情况检查"},
]

print("=== 新发现 P1 候选 4 源验证 (深度) ===\n")
for nc in new_candidates:
    matches = [v for v in p1 if v["file"] == nc["file"] and v["line"] == nc["line"]]
    if not matches:
        print(f"[NOT FOUND] {nc['file']}:L{nc['line']}")
        continue
    v = matches[0]
    try:
        with open(ROOT / v["file"], "r", encoding="utf-8") as f:
            lines = f.readlines()
        start = max(0, v["line"]-4)
        end = min(len(lines), v["line"]+2)
        ctx = "".join(f"{i+1:4d}| {lines[i].rstrip()}\n" for i in range(start, end))
        print(f"\n[{nc['context_note']}]")
        print(f"  {v['file']}:L{v['line']} ({v['method']})")
        print(f"  except: {v['except_class']}")
        print(f"  上下文:\n{ctx}")
    except Exception as ex:
        print(f"  READ ERROR: {ex}")

# 业务调用方 grep (方法名)
print("\n\n=== 业务调用方 ===")
import os
for nc in new_candidates[:5]:
    method_name = "get_statistics" if "uni_plugin_data_manager" in nc["file"] else None
    if not method_name:
        continue
    hits = []
    for sub in ["core", "gui", "services", "trading", "tests", "plugins"]:
        base = ROOT / sub
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts or ".pytest_cache" in path.parts:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if method_name in content:
                    rel = str(path.relative_to(ROOT)).replace("\\", "/")
                    hits.append(rel)
            except Exception:
                continue
    print(f"\n  {method_name} 跨子目录: {len(hits)} 处")
    for h in hits[:5]:
        print(f"    {h}")
