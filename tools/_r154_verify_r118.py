#!/usr/bin/env python3
"""R154 子智能体 D: 验证 R118 豁免 8/8 锁定位置 100% 命中"""
import json
import yaml
from pathlib import Path

JSON_PATH = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tools\r154_r51_full.json"
REGISTRY_PATH = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\r118_exceptions_registry.yaml"

with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
    registry = yaml.safe_load(f)

# 提取豁免清单
exempt_locations = set()
for category in ["r118_b15_field_degradation", "r118_b16_monitoring_auxiliary"]:
    for entry in registry.get(category, []):
        f_path = entry["file"].replace("\\", "/")
        exempt_locations.add((f_path, int(entry["line"])))

# 从扫描结果检查豁免是否被正确识别
violations = data["violations"]
violation_keys = set((v["file"], v["line"]) for v in violations)

# R118 豁免位置是否都没出现在 violations 中 (即豁免成功)
hit_count = 0
miss_locations = []
for f_path, line in exempt_locations:
    if (f_path, line) not in violation_keys:
        hit_count += 1
    else:
        miss_locations.append((f_path, line))

print(f"=== R118 豁免验证 ===")
print(f"R118 豁免登记位置: {len(exempt_locations)}")
print(f"豁免命中 (未出现在 violations): {hit_count}")
print(f"豁免未命中 (出现在 violations): {len(miss_locations)}")
print(f"命中比例: {hit_count}/{len(exempt_locations)} = {hit_count/len(exempt_locations)*100:.1f}%")
print()

# 详细列出豁免位置
print("=== R118 豁免位置详情 ===")
for cat in ["r118_b15_field_degradation", "r118_b16_monitoring_auxiliary"]:
    print(f"\n--- {cat} ---")
    for entry in registry.get(cat, []):
        f_path = entry["file"].replace("\\", "/")
        line = int(entry["line"])
        is_hit = (f_path, line) not in violation_keys
        status = "[EXEMPT]" if is_hit else "[NOT EXEMPT]"
        print(f"  {status} {entry['id']} {f_path}:{line} - {entry['context'][:50]}")

# 统计各 P1 严重性级别
print("\n=== P1 分类 (按文件聚合) ===")
p1_v = [v for v in violations if v["severity"] == "P1"]
from collections import Counter
files_with_p1 = Counter(v["file"] for v in p1_v)
print(f"P1 涉及文件数: {len(files_with_p1)}")
print(f"P1 总数: {len(p1_v)}")

# 关键业务路径 P1 (高 ROI 候选)
business_critical = [
    "core/trading_engine", "core/risk_control", "core/risk_manager",
    "core/position_manager", "core/asset_database_manager",
    "core/money_manager", "core/importdata/import_execution_engine",
    "core/database/duckdb_manager", "core/agents",
    "core/coordinators", "core/services", "core/async_management",
]
print("\n=== 关键业务路径 P1 候选 ===")
for path_prefix in business_critical:
    p1_in_path = [v for v in p1_v if v["file"].startswith(path_prefix)]
    if p1_in_path:
        print(f"\n--- {path_prefix} ({len(p1_in_path)} P1) ---")
        for v in p1_in_path[:5]:
            print(f"  L{v['line']:4d} {v['method']:40s} except={v['except_class']}")
