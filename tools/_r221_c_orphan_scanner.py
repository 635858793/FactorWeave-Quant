#!/usr/bin/env python3
"""
R221 子智能体 C: EventBus ORPHAN 扫描器
扫描 core/ + gui/ + web/ + tests/ + plugins/ + scripts/ + strategies/ + backtest/
排除 *.bak.* / *.r*.* 备份文件
"""
import re
import os
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# 排除模式
EXCLUDE_RE = re.compile(r"\.(bak|r\d+[a-z]*)\.")  # 排除 .bak. 和 .r*.* 文件

# 包含的子目录
SUBDIRS = ["core", "gui", "web", "tests", "plugins", "scripts", "strategies", "backtest"]

# 提取事件名 (从 publish('xxx', ...) / publish("xxx", ...))
PUB_STR_RE = re.compile(r"""\.publish\(\s*(?:['"]([^'"]+)['"]|(\w+Event)\()""")
SUB_STR_RE = re.compile(r"""\.subscribe\(\s*(?:['"]([^'"]+)['"]|(\w+Event)(?:,|\s))""")

def should_skip(path: Path) -> bool:
    return bool(EXCLUDE_RE.search(str(path)))

def scan_subdir(subdir: str):
    """扫描指定子目录"""
    publishes = defaultdict(list)  # event_name -> [file:line]
    subscribes = defaultdict(list)
    sub_path = ROOT / subdir
    if not sub_path.exists():
        return publishes, subscribes
    for pyfile in sub_path.rglob("*.py"):
        if should_skip(pyfile):
            continue
        rel = pyfile.relative_to(ROOT)
        try:
            text = pyfile.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for m in PUB_STR_RE.finditer(line):
                evt = m.group(1) or m.group(2)
                if evt:
                    publishes[evt].append(f"{rel}:{i}")
            for m in SUB_STR_RE.finditer(line):
                evt = m.group(1) or m.group(2)
                if evt:
                    subscribes[evt].append(f"{rel}:{i}")
    return publishes, subscribes

all_pubs = defaultdict(list)
all_subs = defaultdict(list)
for sd in SUBDIRS:
    p, s = scan_subdir(sd)
    for k, v in p.items():
        all_pubs[k].extend([(sd, x) for x in v])
    for k, v in s.items():
        all_subs[k].extend([(sd, x) for x in v])

# 排除测试文件中的 publish/subscribe (test_*.py / final/ / compatibility/)
# 这些用于单元测试,不算业务方
def is_test(path: str) -> bool:
    return (
        "/tests/" in path
        and ("/test_" in path or "/final/" in path or "/simulation/" in path or "/compatibility/" in path)
    )

# 输出所有 publish 事件 + 配对状态
print("=" * 100)
print("R221 子智能体 C: EventBus ORPHAN 扫描报告 (生产代码 + 业务文件)")
print("=" * 100)
print(f"扫描子目录: {SUBDIRS}")
print(f"排除备份文件: {EXCLUDE_RE.pattern}")
print(f"扫描时间: 2026-07-28")
print()

# 业务方 publish 列表 (排除 tests/ 下的)
bus_pubs = defaultdict(list)
for k, locs in all_pubs.items():
    for sd, loc in locs:
        if not is_test(loc):
            bus_pubs[k].append((sd, loc))

bus_subs = defaultdict(list)
for k, locs in all_subs.items():
    for sd, loc in locs:
        if not is_test(loc):
            bus_subs[k].append((sd, loc))

# ORPHAN_PUB: 业务方 publish 但无业务方 subscribe (白名单除外)
WHITELIST_DYNAMIC = re.compile(r"^service\.[^.]+\.(initialized|initialization_failed)$")
WHITELIST_R202B = {
    "service.started", "service.stopped", "service.error", "service.initialization_failed",
    "ResourceThresholdExceeded", "SystemResourceUpdated", "MetricsAggregated",
    "theme_changed", "StrategyConfigsLoadedEvent", "IndicatorChangedEvent",
    "task_started", "task_completed", "task_failed", "task_retrying",  # enhanced_async_manager
}

orphan_pubs = []
for evt, locs in sorted(bus_pubs.items()):
    if evt in bus_subs:
        continue
    # 跳过白名单
    if WHITELIST_DYNAMIC.match(evt) or evt in WHITELIST_R202B:
        continue
    # 跳过纯类名 (BaseEvent 子类名) — 这些是事件类, 由 .publish(SomeEvent(...)) 调用
    orphan_pubs.append((evt, locs))

# ORPHAN_SUB: 业务方 subscribe 但无业务方 publish
orphan_subs = []
for evt, locs in sorted(bus_subs.items()):
    if evt in bus_pubs:
        continue
    orphan_subs.append((evt, locs))

print("【A. ORPHAN_PUB (业务方发布, 0 业务订阅)】")
print("-" * 100)
if not orphan_pubs:
    print("  无 ORPHAN_PUB (白名单事件已排除)")
else:
    for evt, locs in orphan_pubs:
        print(f"  事件: {evt}")
        for sd, loc in locs[:5]:
            print(f"    publish  @ {loc}")
        if len(locs) > 5:
            print(f"    ... (+{len(locs)-5} more)")

print()
print("【B. ORPHAN_SUB (业务方订阅, 0 业务发布)】")
print("-" * 100)
if not orphan_subs:
    print("  无 ORPHAN_SUB")
else:
    for evt, locs in orphan_subs:
        print(f"  事件: {evt}")
        for sd, loc in locs[:5]:
            print(f"    subscribe  @ {loc}")
        if len(locs) > 5:
            print(f"    ... (+{len(locs)-5} more)")

print()
print("【C. 配对成功 (业务方发布 + 订阅)】")
print("-" * 100)
print(f"  共 {len([k for k in bus_pubs if k in bus_subs])} 个事件有完整配对")
print(f"  业务方 publish 事件总数: {len(bus_pubs)}")
print(f"  业务方 subscribe 事件总数: {len(bus_subs)}")

# 输出 ORPHAN_PUB 数量
print()
print("=" * 100)
print(f"ORPHAN_PUB 数量: {len(orphan_pubs)}")
print(f"ORPHAN_SUB 数量: {len(orphan_subs)}")
print("=" * 100)
