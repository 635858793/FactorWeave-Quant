# -*- coding: utf-8 -*-
"""
R192-B 业务调用链扫描脚本
扫描 4 子目录: core/ + gui/ + web/ + tests/
统计: publish 调用 + subscribe 调用 + 业务链断裂候选
"""
import os
import re
import sys
from pathlib import Path
from collections import defaultdict, Counter

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_DIRS = ["core", "gui", "web", "tests", "plugins", "scripts"]
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules", "__pycache__",
                ".mypy_cache", ".cache", "data", "data/cache"}

# publish 模式: 1) bus.publish(...) 2) self._bus.publish(...) 3) event_bus.publish(...)
PUBLISH_PATTERNS = [
    re.compile(r'\bbus\.publish\s*\('),
    re.compile(r'\bself\._bus\.publish\s*\('),
    re.compile(r'\bevent_bus\.publish\s*\('),
    re.compile(r'\bself\._event_bus\.publish\s*\('),
    re.compile(r'\bbus_instance\.publish\s*\('),
]

# subscribe 模式
SUBSCRIBE_PATTERNS = [
    re.compile(r'\bbus\.subscribe\s*\('),
    re.compile(r'\bself\._bus\.subscribe\s*\('),
    re.compile(r'\bevent_bus\.subscribe\s*\('),
    re.compile(r'\bself\._event_bus\.subscribe\s*\('),
    re.compile(r'\bbus_instance\.subscribe\s*\('),
]

# 提取事件类型字符串 - 第一参数
def extract_event_arg(line):
    """提取 publish/subscribe 的第一参数 (事件类型)"""
    # 提取括号内第一参数
    m = re.search(r'\.publish\s*\(\s*([^,)\s]+(?:\([^)]*\))?[^,)]*)', line)
    if m:
        return m.group(1).strip()
    return None


def scan_file(path):
    """扫描单个文件,返回 publish/subscribe 调用列表"""
    pubs = []
    subs = []
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f, 1):
                # 跳过注释
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                for pat in PUBLISH_PATTERNS:
                    if pat.search(line):
                        evt = extract_event_arg(line)
                        pubs.append((i, line.rstrip(), evt))
                        break
                for pat in SUBSCRIBE_PATTERNS:
                    if pat.search(line):
                        evt = extract_event_arg(line)
                        subs.append((i, line.rstrip(), evt))
                        break
    except Exception as e:
        pass
    return pubs, subs


def main():
    all_pubs = []  # [(file, line, source_line, event_arg)]
    all_subs = []

    for subdir in SCAN_DIRS:
        scan_path = PROJECT_ROOT / subdir
        if not scan_path.exists():
            continue
        for root, dirs, files in os.walk(scan_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fn in files:
                if not fn.endswith('.py'):
                    continue
                full = Path(root) / fn
                pubs, subs = scan_file(full)
                rel = str(full.relative_to(PROJECT_ROOT))
                for ln, src, evt in pubs:
                    all_pubs.append((rel, ln, src, evt))
                for ln, src, evt in subs:
                    all_subs.append((rel, ln, src, evt))

    print("=" * 80)
    print(f"R192-B 业务调用链扫描报告")
    print("=" * 80)
    print(f"扫描目录: {SCAN_DIRS}")
    print(f"publish 调用总数: {len(all_pubs)}")
    print(f"subscribe 调用总数: {len(all_subs)}")
    print()

    # 统计事件类型
    pub_events = Counter()
    sub_events = Counter()

    for _, _, _, evt in all_pubs:
        if evt:
            # 简化: 去掉 EventType.XXX 中的 EventType. 前缀
            evt_clean = re.sub(r'^EventType\.', '', evt)
            evt_clean = re.sub(r'^EventType\["?(\w+)"?\]$', r'\1', evt_clean)
            pub_events[evt_clean] += 1

    for _, _, _, evt in all_subs:
        if evt:
            evt_clean = re.sub(r'^EventType\.', '', evt)
            evt_clean = re.sub(r'^EventType\["?(\w+)"?\]$', r'\1', evt_clean)
            sub_events[evt_clean] += 1

    # ORPHAN_PUB: publish 但无 subscribe
    orphan_pub = set(pub_events.keys()) - set(sub_events.keys())
    # ORPHAN_SUB: subscribe 但无 publish
    orphan_sub = set(sub_events.keys()) - set(pub_events.keys())

    print(f"唯一 publish 事件类型数: {len(pub_events)}")
    print(f"唯一 subscribe 事件类型数: {len(sub_events)}")
    print(f"ORPHAN_PUB 候选 (有 publish 无 subscribe): {len(orphan_pub)}")
    print(f"ORPHAN_SUB 候选 (有 subscribe 无 publish): {len(orphan_sub)}")
    print()

    # 详细输出 ORPHAN_PUB
    print("=" * 80)
    print("ORPHAN_PUB 清单 (publish 但 subscribe 0 命中, 跨子目录)")
    print("=" * 80)
    if orphan_pub:
        for evt in sorted(orphan_pub):
            count = pub_events[evt]
            # 找到该事件的所有 publish 调用
            locations = [(f, l, s) for f, l, s, e in all_pubs if e and re.sub(r'^EventType\.', '', e) == evt]
            print(f"\n[ORPHAN_PUB] {evt} (publish 调用 {count} 次):")
            for f, l, s in locations[:5]:  # 最多列 5 处
                print(f"  - {f}:{l}")
            if len(locations) > 5:
                print(f"  ... 还有 {len(locations) - 5} 处")
    else:
        print("(无)")

    print()
    print("=" * 80)
    print("ORPHAN_SUB 清单 (subscribe 但 publish 0 命中, 跨子目录)")
    print("=" * 80)
    if orphan_sub:
        for evt in sorted(orphan_sub):
            count = sub_events[evt]
            locations = [(f, l, s) for f, l, s, e in all_subs if e and re.sub(r'^EventType\.', '', e) == evt]
            print(f"\n[ORPHAN_SUB] {evt} (subscribe 调用 {count} 次):")
            for f, l, s in locations[:5]:
                print(f"  - {f}:{l}")
            if len(locations) > 5:
                print(f"  ... 还有 {len(locations) - 5} 处")
    else:
        print("(无)")

    # 全部 publish 事件类型详细列表
    print()
    print("=" * 80)
    print("publish 事件类型完整清单 (按出现次数降序)")
    print("=" * 80)
    for evt, cnt in sorted(pub_events.items(), key=lambda x: -x[1]):
        sub_match = "✓" if evt in sub_events else "✗ (无订阅)"
        print(f"  {cnt:3d}x  {evt:50s}  {sub_match}")

    print()
    print("=" * 80)
    print("subscribe 事件类型完整清单 (按出现次数降序)")
    print("=" * 80)
    for evt, cnt in sorted(sub_events.items(), key=lambda x: -x[1]):
        pub_match = "✓" if evt in pub_events else "✗ (无发布)"
        print(f"  {cnt:3d}x  {evt:50s}  {pub_match}")


if __name__ == "__main__":
    main()
