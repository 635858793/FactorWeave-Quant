"""
事件总线 ORPHAN_PUB / ORPHAN_SUB 扫描器
R84 教训: 找出无订阅方的发布、无发布方的订阅
"""
import re
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

# 4 子目录
SUBDIRS = ["core", "gui", "tests", "scripts"]


def grep_pattern(rel_root: str, pattern: str) -> list:
    """用 Grep 风格扫描, 返回 [(file, line, content)]"""
    results = []
    root = PROJECT_ROOT / rel_root
    if not root.exists():
        return results
    for py_file in root.rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    if re.search(pattern, line):
                        results.append((str(py_file.relative_to(PROJECT_ROOT)), i, line.rstrip()))
        except Exception:
            pass
    return results


def main():
    print("=== 事件总线 ORPHAN_PUB/SUB 扫描 ===\n")

    # 1. 扫描 bus.publish
    publish_pattern = r"\bbus\.publish\s*\("
    all_publishes = []
    for sub in SUBDIRS:
        results = grep_pattern(sub, publish_pattern)
        for f, l, c in results:
            all_publishes.append((f, l, c))
        print(f"  {sub}/publish: {len(results)}")

    # 2. 扫描 bus.subscribe
    subscribe_pattern = r"\bbus\.subscribe\s*\("
    all_subscribes = []
    for sub in SUBDIRS:
        results = grep_pattern(sub, subscribe_pattern)
        for f, l, c in results:
            all_subscribes.append((f, l, c))
        print(f"  {sub}/subscribe: {len(results)}")

    # 3. 提取事件名 (publish("event.name", ...) 或 publish(event_name, ...))
    def extract_event_name(content: str) -> str:
        m = re.search(r'\bpublish\s*\(\s*["\']([^"\']+)["\']', content)
        if m:
            return m.group(1)
        m = re.search(r'\bpublish\s*\(\s*([a-zA-Z_][a-zA-Z0-9_.]*)', content)
        if m:
            return f"<var:{m.group(1)}>"
        return "<unknown>"

    def extract_subscribe_name(content: str) -> str:
        m = re.search(r'\bsubscribe\s*\(\s*["\']([^"\']+)["\']', content)
        if m:
            return m.group(1)
        m = re.search(r'\bsubscribe\s*\(\s*([a-zA-Z_][a-zA-Z0-9_.]*)', content)
        if m:
            return f"<var:{m.group(1)}>"
        return "<unknown>"

    pub_events = defaultdict(list)
    for f, l, c in all_publishes:
        name = extract_event_name(c)
        pub_events[name].append((f, l, c))

    sub_events = defaultdict(list)
    for f, l, c in all_subscribes:
        name = extract_subscribe_name(c)
        sub_events[name].append((f, l, c))

    # 4. 找出 ORPHAN
    pub_names = set(pub_events.keys())
    sub_names = set(sub_events.keys())

    orphan_pub = pub_names - sub_names
    orphan_sub = sub_names - pub_names

    # 排除动态事件名
    orphan_pub = {n for n in orphan_pub if not n.startswith("<var:") and n != "<unknown>"}
    orphan_sub = {n for n in orphan_sub if not n.startswith("<var:") and n != "<unknown>"}

    print(f"\n=== ORPHAN_PUB (无订阅方): {len(orphan_pub)} ===")
    for name in sorted(orphan_pub):
        print(f"  {name}: {len(pub_events[name])} 处")
        for f, l, c in pub_events[name][:3]:
            print(f"    {f}:{l}  {c.strip()[:80]}")

    print(f"\n=== ORPHAN_SUB (无发布方): {len(orphan_sub)} ===")
    for name in sorted(orphan_sub):
        print(f"  {name}: {len(sub_events[name])} 处")
        for f, l, c in sub_events[name][:3]:
            print(f"    {f}:{l}  {c.strip()[:80]}")

    print(f"\n=== 匹配对: {len(pub_names & sub_names)} ===")
    common = sorted(pub_names & sub_names)
    for name in common[:10]:
        print(f"  {name}: pub={len(pub_events[name])} sub={len(sub_events[name])}")
    if len(common) > 10:
        print(f"  ... 还有 {len(common) - 10} 对")

    import json
    output = PROJECT_ROOT / "tests" / "_r161_d_orphan_events.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump({
            "publishes": {k: v for k, v in pub_events.items()},
            "subscribes": {k: v for k, v in sub_events.items()},
            "orphan_pub": list(orphan_pub),
            "orphan_sub": list(orphan_sub),
        }, f, ensure_ascii=False, indent=2)
    print(f"\nJSON: {output}")


if __name__ == "__main__":
    main()
