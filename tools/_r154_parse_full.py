#!/usr/bin/env python3
"""R154 子智能体 D: 完整解析 R51 lint JSON 报告, 生成可分析的数据结构"""
import json
from collections import defaultdict, Counter

JSON_PATH = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tools\r154_r51_full.json"

with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

print("=== R51 lint 报告概览 ===")
print(f"扫描文件数: {data['scan_metadata']['files_scanned']}")
print(f"豁免位置数: {data['scan_metadata']['exempt_count']}")
print(f"P1 违规: {data['summary']['p1_violations']}")
print(f"P2 违规: {data['summary']['p2_violations']}")
print(f"违规总数: {data['summary']['total_violations']}")
print()

all_v = data["violations"]
p1_v = [v for v in all_v if v["severity"] == "P1"]
p2_v = [v for v in all_v if v["severity"] == "P2"]

# 按模块 + 文件聚合
p1_by_module = defaultdict(int)
p1_by_file = Counter(v["file"] for v in p1_v)
p1_by_method = Counter(f"{v['file']}::{v['method']}" for v in p1_v)

for v in p1_v:
    p1_by_module[v["file"].split("/")[0]] += 1

print(f"=== P1 按模块分布 ===")
for m, c in sorted(p1_by_module.items(), key=lambda x: -x[1]):
    print(f"  {m:15s}: {c:4d}")

print(f"\n=== P1 Top 30 文件 ===")
for f, c in p1_by_file.most_common(30):
    print(f"  {c:4d} | {f}")

print(f"\n=== P1 Top 30 方法 (跨文件) ===")
for fm, c in p1_by_method.most_common(30):
    print(f"  {c:3d} | {fm}")

# 保存分析结果
result = {
    "stats": data["summary"],
    "metadata": data["scan_metadata"],
    "p1_by_module": dict(p1_by_module),
    "p1_by_file": dict(p1_by_file.most_common()),
    "p1_by_method": dict(p1_by_method.most_common()),
    "p1_count": len(p1_v),
    "p2_count": len(p2_v),
}
with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tools\r154_p1_stats.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\n统计已保存: tools/r154_p1_stats.json")
