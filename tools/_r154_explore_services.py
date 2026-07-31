#!/usr/bin/env python3
"""R154 子智能体 D: 深入检查其他 Service P1 候选"""
import json
from pathlib import Path

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
with open(ROOT / "tools/r154_r51_full.json", "r", encoding="utf-8") as f:
    data = json.load(f)
p1 = [v for v in data["violations"] if v["severity"] == "P1"]

target_files = [
    "core/services/database_service.py",
    "core/services/new_stock_fetcher.py",
    "core/services/system_optimizer.py",
    "core/services/uni_plugin_data_manager.py",
    "core/services/dividend_data_service.py",
    "core/services/dynamic_risk_adjustment_service.py",
    "core/services/performance_service.py",
    "core/services/service_health_monitor.py",
    "core/services/strategy_service.py",
    "core/services/asset_fallback_loader.py",
    "core/services/enhanced_data_manager.py",
    "core/services/strategy_plugin_pool.py",
    "core/services/unified_data_manager.py",
    "core/services/tdx_server_discovery.py",
    "core/services/cache_service.py",
]

for tf in target_files:
    matches = [v for v in p1 if v["file"] == tf]
    if matches:
        print(f"\n=== {tf} ({len(matches)} P1) ===")
        for v in matches:
            try:
                with open(ROOT / v["file"], "r", encoding="utf-8") as f:
                    lines = f.readlines()
                ctx = "".join(f"{i+1:4d}| {lines[i].rstrip()}\n" for i in range(max(0, v["line"]-3), min(len(lines), v["line"]+1)))
                print(f"  L{v['line']:4d} {v['method']}")
                print(f"  {ctx}")
            except Exception as ex:
                print(f"  READ ERROR: {ex}")
