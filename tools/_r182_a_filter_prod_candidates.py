#!/usr/bin/env python3
"""R182 A 子智能体 - 生产代码死代码候选精准筛选 (排除 tests/)"""
import json
from pathlib import Path
from collections import defaultdict

# 读取之前的全项目扫描结果
with open('tests/_r182_a_dead_candidates.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 排除 tests/ 和 _archive/ 和 doc 目录
EXCLUDE_PREFIXES = ('tests/', 'docs/', 'tools/', '_archive/', 'reports/', 'analysis/')
EXCLUDE_FILES = {
    'core/services/service_bootstrap.py',  # 注册入口, 排除误报
    'core/containers/service_container.py',  # 全局单例, 排除误报
    'core/containers/enhanced_service_container.py',
    'core/containers/unified_service_container.py',
    'core/events/event_bus.py',  # 全局事件总线, 排除误报
    'main.py',
}

prod_candidates = []
for m in data['dead_candidates']:
    f = m['file']
    if f.startswith(EXCLUDE_PREFIXES):
        continue
    if f in EXCLUDE_FILES:
        continue
    prod_candidates.append(m)

# 按文件分组
file_groups = defaultdict(list)
for m in prod_candidates:
    file_groups[m['file']].append(m)

print(f"生产代码死代码候选 (排除 tests/ 等): {len(prod_candidates)}")
print(f"涉及文件数: {len(file_groups)}")
print()
for fpath, methods in sorted(file_groups.items(), key=lambda x: -len(x[1])):
    print(f"  [{len(methods)} 个候选] {fpath}")
    for m in methods[:10]:
        print(f"    L{m['lineno']:>5} {m['qualname']}")
    if len(methods) > 10:
        print(f"    ... +{len(methods) - 10} more")
    print()
