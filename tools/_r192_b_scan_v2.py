# -*- coding: utf-8 -*-
"""
R192-B 扫描 V2: 修正 subscribe 第一参数提取
"""
import os
import re
from pathlib import Path
from collections import defaultdict, Counter

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_DIRS = ["core", "gui", "web", "tests", "plugins", "scripts"]
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules", "__pycache__",
                ".mypy_cache", ".cache", "data", "data/cache"}

PUBLISH_PATTERNS = [
    re.compile(r'\bbus\.publish\s*\('),
    re.compile(r'\bself\._bus\.publish\s*\('),
    re.compile(r'\bevent_bus\.publish\s*\('),
    re.compile(r'\bself\._event_bus\.publish\s*\('),
    re.compile(r'\bbus_instance\.publish\s*\('),
]

SUBSCRIBE_PATTERNS = [
    re.compile(r'\bbus\.subscribe\s*\('),
    re.compile(r'\bself\._bus\.subscribe\s*\('),
    re.compile(r'\bevent_bus\.subscribe\s*\('),
    re.compile(r'\bself\._event_bus\.subscribe\s*\('),
    re.compile(r'\bbus_instance\.subscribe\s*\('),
]


def extract_first_arg(line, start_pos):
    """提取 publish/subscribe 的第一参数 (处理嵌套括号)"""
    # 跳过 publish/subscribe( 本身
    i = start_pos
    while i < len(line) and line[i] != '(':
        i += 1
    if i >= len(line):
        return None
    i += 1  # skip '('
    # 跳过空白
    while i < len(line) and line[i] in ' \t\n':
        i += 1
    if i >= len(line):
        return None
    # 处理嵌套括号
    depth = 1
    start = i
    while i < len(line) and depth > 0:
        c = line[i]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                break
        elif c == "'" or c == '"':
            # 跳过字符串
            quote = c
            i += 1
            while i < len(line) and line[i] != quote:
                if line[i] == '\\':
                    i += 1
                i += 1
        i += 1
    return line[start:i].strip()


def extract_event_arg_v2(line, method='publish'):
    """提取 publish/subscribe 的第一参数"""
    pattern_str = r'\.' + method + r'\s*\('
    m = re.search(pattern_str, line)
    if not m:
        return None
    arg = extract_first_arg(line, m.end() - 1)
    return arg


def scan_file(path):
    pubs = []
    subs = []
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                for pat in PUBLISH_PATTERNS:
                    if pat.search(line):
                        evt = extract_event_arg_v2(line, 'publish')
                        pubs.append((i, line.rstrip(), evt))
                        break
                for pat in SUBSCRIBE_PATTERNS:
                    if pat.search(line):
                        evt = extract_event_arg_v2(line, 'subscribe')
                        subs.append((i, line.rstrip(), evt))
                        break
    except Exception as e:
        pass
    return pubs, subs


def main():
    all_pubs = []
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

    print("=" * 80, flush=True)
    print(f"R192-B V2 业务调用链扫描报告", flush=True)
    print("=" * 80, flush=True)
    print(f"扫描目录: {SCAN_DIRS}", flush=True)
    print(f"publish 调用总数: {len(all_pubs)}", flush=True)
    print(f"subscribe 调用总数: {len(all_subs)}", flush=True)
    print(flush=True)

    pub_events = Counter()
    sub_events = Counter()

    for _, _, _, evt in all_pubs:
        if evt:
            evt_clean = re.sub(r'^EventType\.', '', evt)
            pub_events[evt_clean] += 1

    for _, _, _, evt in all_subs:
        if evt:
            evt_clean = re.sub(r'^EventType\.', '', evt)
            sub_events[evt_clean] += 1

    orphan_pub = set(pub_events.keys()) - set(sub_events.keys())
    orphan_sub = set(sub_events.keys()) - set(pub_events.keys())

    print(f"唯一 publish 事件类型数: {len(pub_events)}", flush=True)
    print(f"唯一 subscribe 事件类型数: {len(sub_events)}", flush=True)
    print(f"ORPHAN_PUB (publish 但无 subscribe): {len(orphan_pub)}", flush=True)
    print(f"ORPHAN_SUB (subscribe 但无 publish): {len(orphan_sub)}", flush=True)
    print(flush=True)

    # 按子目录汇总
    print("=" * 80, flush=True)
    print("按子目录汇总", flush=True)
    print("=" * 80, flush=True)
    pub_by_dir = Counter()
    sub_by_dir = Counter()
    for rel, _, _, _ in all_pubs:
        d = rel.split("\\")[0] if "\\" in rel else rel.split("/")[0]
        pub_by_dir[d] += 1
    for rel, _, _, _ in all_subs:
        d = rel.split("\\")[0] if "\\" in rel else rel.split("/")[0]
        sub_by_dir[d] += 1
    for d in sorted(set(list(pub_by_dir.keys()) + list(sub_by_dir.keys()))):
        print(f"  {d:20s}  publish: {pub_by_dir[d]:3d} | subscribe: {sub_by_dir[d]:3d}", flush=True)
    print(flush=True)

    # 过滤 ORPHAN_PUB: 排除测试代码
    print("=" * 80, flush=True)
    print("ORPHAN_PUB 业务候选 (非 tests 目录, 需 4 源验证)", flush=True)
    print("=" * 80, flush=True)
    for evt in sorted(orphan_pub):
        locs = [(f, l, s) for f, l, s, e in all_pubs if e and re.sub(r'^EventType\.', '', e) == evt]
        # 排除纯测试
        prod_locs = [(f, l, s) for f, l, s in locs if not f.startswith("tests")]
        if not prod_locs:
            continue
        print(f"\n[ORPHAN_PUB] {evt} (prod publish {len(prod_locs)} 处, total {len(locs)}):", flush=True)
        for f, l, s in prod_locs[:3]:
            print(f"  - {f}:{l}", flush=True)
        if len(prod_locs) > 3:
            print(f"  ... 还有 {len(prod_locs) - 3} 处", flush=True)

    print()
    print("=" * 80, flush=True)
    print("ORPHAN_SUB 业务候选 (非 tests 目录, 需 4 源验证)", flush=True)
    print("=" * 80, flush=True)
    for evt in sorted(orphan_sub):
        locs = [(f, l, s) for f, l, s, e in all_subs if e and re.sub(r'^EventType\.', '', e) == evt]
        prod_locs = [(f, l, s) for f, l, s in locs if not f.startswith("tests")]
        if not prod_locs:
            continue
        print(f"\n[ORPHAN_SUB] {evt} (prod subscribe {len(prod_locs)} 处, total {len(locs)}):", flush=True)
        for f, l, s in prod_locs[:3]:
            print(f"  - {f}:{l}", flush=True)

    # 输出到文件
    out = open(PROJECT_ROOT / ".audit_r192_b_v2.txt", "w", encoding="utf-8")
    out.write(f"publish 总数: {len(all_pubs)}\n")
    out.write(f"subscribe 总数: {len(all_subs)}\n")
    out.write(f"唯一 publish 事件类型数: {len(pub_events)}\n")
    out.write(f"唯一 subscribe 事件类型数: {len(sub_events)}\n")
    out.write(f"ORPHAN_PUB: {len(orphan_pub)}\n")
    out.write(f"ORPHAN_SUB: {len(orphan_sub)}\n\n")

    out.write("===== publish 全部事件 (按调用次数降序) =====\n")
    for evt, cnt in sorted(pub_events.items(), key=lambda x: -x[1]):
        sub_match = "✓" if evt in sub_events else "✗"
        out.write(f"  {cnt:3d}x  {evt}  {sub_match}\n")

    out.write("\n===== subscribe 全部事件 (按调用次数降序) =====\n")
    for evt, cnt in sorted(sub_events.items(), key=lambda x: -x[1]):
        pub_match = "✓" if evt in pub_events else "✗"
        out.write(f"  {cnt:3d}x  {evt}  {pub_match}\n")
    out.close()
    print(f"\n详细结果已写入 .audit_r192_b_v2.txt", flush=True)


if __name__ == "__main__":
    main()
