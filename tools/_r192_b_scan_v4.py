# -*- coding: utf-8 -*-
"""
R192-B V4: 增强版 ORPHAN 扫描
精确识别所有 subscribe 模式, 包括元组列表 (R86 P0-2 模板):
  - bus.subscribe(EVT, handler)
  - self._subscribe_event(EVT, handler)
  - ('EVT', handler) 在循环/tuple/list 中
"""
import os
import re
from pathlib import Path
from collections import defaultdict, Counter

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_DIRS = ["core", "gui", "web", "tests", "plugins", "scripts"]
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules", "data", "data/cache"}


def scan_file(path):
    """扫描单个文件,返回所有 publish/subscribe 调用, 含多种模式"""
    pubs = []
    subs = []
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith('#'):
                    # 但要检测 `# subscribe` 注释行作为 ORPHAN 修复参考
                    if 'subscribe' in stripped.lower() or 'publish' in stripped.lower():
                        # 也算 other 参考
                        pass
                    continue

                # publish 模式
                if re.search(r'\bbus\.publish\s*\(', line) or \
                   re.search(r'\bself\._bus\.publish\s*\(', line) or \
                   re.search(r'\bevent_bus\.publish\s*\(', line) or \
                   re.search(r'\bself\._event_bus\.publish\s*\(', line):
                    # 提取事件名 (第一个参数)
                    m = re.search(r'\.publish\s*\(\s*([^,)\s]+(?:\([^)]*\))?)', line)
                    evt = m.group(1) if m else None
                    pubs.append((i, line.rstrip(), evt))
                    continue

                # subscribe 函数调用模式
                if re.search(r'\.subscribe\s*\(', line) or re.search(r'_subscribe_event\s*\(', line):
                    m = re.search(r'(?:\.subscribe|_subscribe_event)\s*\(\s*([^,)\s]+(?:\([^)]*\))?)', line)
                    evt = m.group(1) if m else None
                    subs.append((i, line.rstrip(), evt))
                    continue

                # 元组列表模式: ('EVT', handler) 或 ("EVT", handler)
                # 仅在循环/for/comprehension 中识别
                tuple_match = re.search(r"""['"]([a-zA-Z_][\w.]+(?:\.[a-zA-Z_][\w.]+)*)['"]\s*,\s*(?:self\.)?\w+""", line)
                if tuple_match and ('for ' in line or '[' in line or 'tuple(' in line or 'subscribe' in content[max(0, content.find(line)-500):content.find(line)]):
                    evt = tuple_match.group(1)
                    # 启发式: 仅当上下文含 subscribe / 循环列表时
                    if 'subscribe' in content[max(0, content.find(line)-1000):content.find(line)][-1500:]:
                        subs.append((i, line.rstrip(), evt))
                        continue
    except Exception:
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

    # 统计
    pub_events = Counter()
    sub_events = Counter()

    for _, _, _, evt in all_pubs:
        if evt and re.match(r'^[a-zA-Z_]', evt):
            evt_clean = re.sub(r'^EventType\.', '', evt)
            evt_clean = evt_clean.strip('"\'')
            pub_events[evt_clean] += 1

    for _, _, _, evt in all_subs:
        if evt and re.match(r'^[a-zA-Z_]', evt):
            evt_clean = re.sub(r'^EventType\.', '', evt)
            evt_clean = evt_clean.strip('"\'')
            sub_events[evt_clean] += 1

    print("=" * 100, flush=True)
    print("R192-B V4 增强 ORPHAN 扫描", flush=True)
    print("=" * 100, flush=True)
    print(f"publish 调用: {len(all_pubs)} | subscribe 调用: {len(all_subs)}", flush=True)
    print(f"唯一 publish 事件: {len(pub_events)} | 唯一 subscribe 事件: {len(sub_events)}", flush=True)
    print(flush=True)

    orphan_pub = set(pub_events.keys()) - set(sub_events.keys())
    orphan_sub = set(sub_events.keys()) - set(pub_events.keys())

    print(f"ORPHAN_PUB 候选: {len(orphan_pub)}", flush=True)
    print(f"ORPHAN_SUB 候选: {len(orphan_sub)}", flush=True)

    # 业务候选: 排除 tests
    print()
    print("=" * 100, flush=True)
    print("ORPHAN_PUB 业务候选 (非 tests 目录)", flush=True)
    print("=" * 100, flush=True)
    for evt in sorted(orphan_pub):
        locs = [(f, l, s) for f, l, s, e in all_pubs if e and re.sub(r'^EventType\.', '', e).strip('"\'') == evt]
        prod_locs = [(f, l, s) for f, l, s in locs if not f.startswith("tests")]
        if not prod_locs:
            continue
        print(f"\n  [ORPHAN_PUB] {evt} (prod {len(prod_locs)}, total {len(locs)}):", flush=True)
        for f, l, s in prod_locs[:3]:
            print(f"    {f}:{l}", flush=True)

    print()
    print("=" * 100, flush=True)
    print("ORPHAN_SUB 业务候选 (非 tests 目录, 排除变量名)", flush=True)
    print("=" * 100, flush=True)
    # 排除变量名
    var_names = {"event_type", "event_name", "event_cls", "event_obj", "event",
                 "evt_type", "evt_name", "evt", "topic", "w",
                 "trade_event", "position_event", "request_event", "ui_data_ready_event",
                 "_SGE", "test_event", "test_evt", "_r86_event"}
    for evt in sorted(orphan_sub):
        if evt in var_names:
            continue
        locs = [(f, l, s) for f, l, s, e in all_subs if e and re.sub(r'^EventType\.', '', e).strip('"\'') == evt]
        prod_locs = [(f, l, s) for f, l, s in locs if not f.startswith("tests")]
        if not prod_locs:
            continue
        print(f"\n  [ORPHAN_SUB] {evt} (prod {len(prod_locs)}, total {len(locs)}):", flush=True)
        for f, l, s in prod_locs[:3]:
            print(f"    {f}:{l}", flush=True)

    # 输出到文件
    out = open(PROJECT_ROOT / ".audit_r192_b_v4.txt", "w", encoding="utf-8")
    out.write(f"publish 总数: {len(all_pubs)}\nsubscribe 总数: {len(all_subs)}\n")
    out.write(f"ORPHAN_PUB: {len(orphan_pub)}\nORPHAN_SUB: {len(orphan_sub)}\n\n")
    out.write("===== ORPHAN_PUB 业务候选 =====\n")
    for evt in sorted(orphan_pub):
        locs = [(f, l, s) for f, l, s, e in all_pubs if e and re.sub(r'^EventType\.', '', e).strip('"\'') == evt]
        prod_locs = [(f, l, s) for f, l, s in locs if not f.startswith("tests")]
        if not prod_locs:
            continue
        out.write(f"\n[ORPHAN_PUB] {evt} (prod {len(prod_locs)}, total {len(locs)})\n")
        for f, l, s in prod_locs:
            out.write(f"  {f}:{l}: {s.strip()[:120]}\n")
    out.write("\n\n===== ORPHAN_SUB 业务候选 =====\n")
    for evt in sorted(orphan_sub):
        if evt in var_names:
            continue
        locs = [(f, l, s) for f, l, s, e in all_subs if e and re.sub(r'^EventType\.', '', e).strip('"\'') == evt]
        prod_locs = [(f, l, s) for f, l, s in locs if not f.startswith("tests")]
        if not prod_locs:
            continue
        out.write(f"\n[ORPHAN_SUB] {evt} (prod {len(prod_locs)}, total {len(locs)})\n")
        for f, l, s in prod_locs:
            out.write(f"  {f}:{l}: {s.strip()[:120]}\n")
    out.close()
    print(f"\n详细结果: .audit_r192_b_v4.txt", flush=True)


if __name__ == "__main__":
    main()
