#!/usr/bin/env python3
"""分析 r154_p2_scan.json 输出每个分类的内容"""
import json

with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tools\r154_p2_scan.json", encoding="utf-8") as f:
    data = json.load(f)

print("=" * 80)
print("P1 分类 (需升级 warning + exc_info=True)")
print("=" * 80)
for item in data["categories"]["P1"]:
    print(f"  {item['file']}:{item['line']} [exc_info={item['exc_info']}]")
    print(f"    {item['msg'][:200]}")
    print()

print("=" * 80)
print("B15 字段降级 (保留 debug)")
print("=" * 80)
for item in data["categories"]["B15"]:
    print(f"  {item['file']}:{item['line']} [exc_info={item['exc_info']}]")
    print(f"    {item['msg'][:200]}")
    print()

print("=" * 80)
print("B16 监控辅助 (保留 debug)")
print("=" * 80)
for item in data["categories"]["B16"]:
    print(f"  {item['file']}:{item['line']} [exc_info={item['exc_info']}]")
    print(f"    {item['msg'][:200]}")
    print()

print("=" * 80)
print("EXC_INFO_OK (有 exc_info=True, R51 允许)")
print("=" * 80)
for item in data["categories"]["EXC_INFO_OK"]:
    print(f"  {item['file']}:{item['line']}")
    print(f"    {item['msg'][:200]}")
    print()
