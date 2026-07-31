#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析 R197 D 扫描结果"""
import json
from collections import defaultdict

with open('tools/_r197_d_new_hvd.json', encoding='utf-8') as f:
    data = json.load(f)

candidates = data['candidates']

print("=" * 80)
print("维度 2 P0 锁违规 (3 项)")
print("=" * 80)
for c in candidates:
    if c.get('severity') == 'P0' and c.get('dimension') == 2:
        print(f"  {c['file']}:{c['line']} - {c.get('type')}")
        print(f"    {c.get('parent')} -> {c.get('current')} (方法: {c.get('method')})")

print()
print("=" * 80)
print("维度 2 P1 缓存键 6 维度违规 (27 项) - 列出前 10")
print("=" * 80)
cache_violations = [c for c in candidates if c.get('type') == 'CACHE_KEY_6D_VIOLATION']
for c in cache_violations[:10]:
    print(f"  {c['file']}:{c['line']} - {c.get('method')}")
    print(f"    缺维度: {c.get('missing_dimensions')}")

print()
print("=" * 80)
print("维度 2 事件总线双轨违规 (2 项)")
print("=" * 80)
for c in candidates:
    if c.get('type') == 'EVENTBUS_DOUBLE_TRACK_VIOLATION':
        print(f"  {c['file']}:{c['line']} - {c.get('method')}")
        print(f"    has_enum: {c.get('has_enum')}, has_subclass: {c.get('has_subclass')}")

print()
print("=" * 80)
print("维度 3 兼容层 alias 候选 (2 项)")
print("=" * 80)
for c in candidates:
    if c.get('dimension') == 3:
        print(f"  {c['file']}:{c['line']} - {c.get('type')}")
        print(f"    alias_name: {c.get('alias_name')} -> target_name: {c.get('target_name')}")
        print(f"    wrapper_name: {c.get('wrapper_name')} -> target_name: {c.get('target_name')}")

print()
print("=" * 80)
print("维度 4 ORPHAN 候选 (7 项)")
print("=" * 80)
for c in candidates:
    if c.get('dimension') == 4:
        print(f"  {c['file']}:{c['line']} - {c.get('type')}")
        print(f"    event: {c.get('event')}")

print()
print("=" * 80)
print("维度 5 多账户缺 account_id (5 项)")
print("=" * 80)
for c in candidates:
    if c.get('dimension') == 5:
        print(f"  {c['file']}:{c['line']} - {c.get('class')}.{c.get('method')}")
        print(f"    type: {c.get('type')}")
