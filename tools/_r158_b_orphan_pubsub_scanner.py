#!/usr/bin/env python3
"""R158-B ORPHAN_PUB/SUB 全量扫描器

扫描 hikyuu-ui 全项目, 收集:
- 所有 publish 调用的事件名
- 所有 subscribe 调用的事件名
- 计算 ORPHAN_PUB (publish 但无订阅) / ORPHAN_SUB (subscribe 但无发布)
"""
import re
import os
import glob
from pathlib import Path

ROOT = Path(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui')

publish_events = {}  # event_name -> [(file, line)]
subscribe_events = {}

# 排除目录
EXCLUDE_DIRS = {'.pytest_cache', '__pycache__', '.git', 'node_modules', 'dist', 'build', '.venv'}

for filepath in ROOT.rglob('*.py'):
    parts = filepath.parts
    if any(ex in parts for ex in EXCLUDE_DIRS):
        continue
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception:
        continue

    rel = filepath.relative_to(ROOT)

    for lineno, line in enumerate(lines, 1):
        # 注释行跳过
        stripped = line.lstrip()
        if stripped.startswith('#'):
            continue

        # 字符串-based publish: bus.publish("event.name", ...)
        for m in re.finditer(r'\.publish\(\s*["\']([a-zA-Z_][a-zA-Z0-9_.]*)["\']', line):
            ev = m.group(1)
            publish_events.setdefault(ev, []).append((str(rel), lineno))

        # 类-based publish: bus.publish(SomeEvent, ...)
        for m in re.finditer(r'\.publish\(\s*([A-Z][a-zA-Z0-9_]*Event)\b', line):
            ev = m.group(1)
            # 排除 SomeEventInstance 形式 (即作为变量)
            # 简单判断: 必须首字母大写 + 全词 Event 结尾
            publish_events.setdefault(ev, []).append((str(rel), lineno))

        # 字符串-based subscribe
        for m in re.finditer(r'\.subscribe\(\s*["\']([a-zA-Z_][a-zA-Z0-9_.]*)["\']', line):
            ev = m.group(1)
            subscribe_events.setdefault(ev, []).append((str(rel), lineno))

        # 类-based subscribe
        for m in re.finditer(r'\.subscribe\(\s*([A-Z][a-zA-Z0-9_]*Event)\b', line):
            ev = m.group(1)
            subscribe_events.setdefault(ev, []).append((str(rel), lineno))

# 合并 set
pub_set = set(publish_events.keys())
sub_set = set(subscribe_events.keys())

orphan_pub = pub_set - sub_set
orphan_sub = sub_set - pub_set
paired = pub_set & sub_set

print(f'=== R158-B ORPHAN_PUB/SUB 扫描结果 ===')
print(f'扫描根目录: {ROOT}')
print(f'唯一 publish 事件: {len(pub_set)}')
print(f'唯一 subscribe 事件: {len(sub_set)}')
print(f'配对事件 (PAIRED): {len(paired)}')
print(f'孤儿发布 (ORPHAN_PUB): {len(orphan_pub)}')
print(f'孤儿订阅 (ORPHAN_SUB): {len(orphan_sub)}')
print()

print('=== PAIRED events ({}): ==='.format(len(paired)))
for e in sorted(paired):
    p_files = len(set(f for f, _ in publish_events[e]))
    s_files = len(set(f for f, _ in subscribe_events[e]))
    print(f'  {e}: publish {p_files} files / subscribe {s_files} files')
print()

print('=== ORPHAN_PUB (publish but no subscribe) ({}): ==='.format(len(orphan_pub)))
for e in sorted(orphan_pub):
    print(f'\n  {e}:')
    for f, ln in publish_events[e][:5]:
        print(f'    -> {f}:{ln}')
    if len(publish_events[e]) > 5:
        print(f'    ... {len(publish_events[e])-5} more')
print()

print('=== ORPHAN_SUB (subscribe but no publish) ({}): ==='.format(len(orphan_sub)))
for e in sorted(orphan_sub):
    print(f'\n  {e}:')
    for f, ln in subscribe_events[e][:5]:
        print(f'    -> {f}:{ln}')
    if len(subscribe_events[e]) > 5:
        print(f'    ... {len(subscribe_events[e])-5} more')
print()
