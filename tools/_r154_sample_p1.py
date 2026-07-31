#!/usr/bin/env python3
"""R154 子智能体 D: 抽取 30+ 关键 P1 violations, 准备 4 源验证"""
import json
from collections import defaultdict, Counter

JSON_PATH = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tools\r154_r51_full.json"

with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

p1 = [v for v in data["violations"] if v["severity"] == "P1"]

# 关键业务路径分类
business_critical = {
    "trading": [v for v in p1 if any(k in v["file"] for k in [
        "trading", "order", "position_manager", "money_manager", "risk_control"
    ])],
    "data_core": [v for v in p1 if any(k in v["file"] for k in [
        "asset_database_manager", "duckdb_manager", "data_source", "unified_data",
        "data_router", "importdata"
    ])],
    "agents": [v for v in p1 if "agents/" in v["file"]],
    "services": [v for v in p1 if "services/" in v["file"]],
    "gui": [v for v in p1 if v["file"].startswith("gui/")],
    "async": [v for v in p1 if "async_management" in v["file"]],
}

# 按方法名 P1 > 2 的高重复方法 (业务热点)
method_counter = Counter(f"{v['file']}::{v['method']}" for v in p1)
hot_methods = [(k, c) for k, c in method_counter.most_common(20) if c >= 2]

# 输出关键抽样
print("=== 关键业务路径 P1 分布 ===")
for cat, vs in business_critical.items():
    print(f"  {cat:15s}: {len(vs)} P1")

print("\n=== 业务热点方法 (P1 >= 2) ===")
for k, c in hot_methods[:20]:
    print(f"  {c:2d} | {k}")

# 抽样策略:
# - 关键业务路径 5 项
# - 高重复方法 10 项
# - 单一 P1 典型 15 项
# - 边缘 P1 (但有潜力) 5 项
# 总计 35 项

sampled = []

# 1) 业务热点方法 (高频 P1)
seen = set()
for fm, c in hot_methods[:15]:
    f, m = fm.split("::")
    for v in p1:
        if v["file"] == f and v["method"] == m and (f, v["line"]) not in seen:
            sampled.append(v)
            seen.add((f, v["line"]))
            break  # 1 个文件/方法 1 个样

# 2) 关键业务路径补足
for cat, vs in business_critical.items():
    for v in vs:
        if len(sampled) >= 35:
            break
        key = (v["file"], v["line"])
        if key not in seen:
            sampled.append(v)
            seen.add(key)

# 3) 多样性: 不同文件尽量多
files_seen = set()
final_sample = []
for v in sampled:
    if v["file"] not in files_seen and len(final_sample) < 35:
        final_sample.append(v)
        files_seen.add(v["file"])
    elif len(final_sample) < 35:
        final_sample.append(v)

# 补足到 35
if len(final_sample) < 35:
    for v in p1:
        if len(final_sample) >= 35:
            break
        if (v["file"], v["line"]) not in seen:
            final_sample.append(v)
            seen.add((v["file"], v["line"]))

print(f"\n=== 抽样 P1 数量: {len(final_sample)} ===")
print(f"涉及文件数: {len(set(v['file'] for v in final_sample))}")

# 保存样本
with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tools\r154_sampled_p1.json", "w", encoding="utf-8") as f:
    json.dump(final_sample, f, ensure_ascii=False, indent=2)

# 输出供后续 4 源验证
print("\n=== 抽样清单 (供 4 源验证) ===")
for i, v in enumerate(final_sample, 1):
    print(f"\n[{i}] {v['file']}:{v['line']} ({v['method']})")
    print(f"    except: {v['except_class']}")
    # 输出上下文前 2 行
    ctx_lines = v["context"].split("\n")
    for cl in ctx_lines[:3]:
        print(f"    | {cl}")
