"""
R163-D Stage 2: R8 事件总线 ORPHAN_PUB / ORPHAN_SUB 残存扫描

扫描目标:
1. 所有 bus.publish / bus.subscribe 调用
2. 计算 ORPHAN_PUB (有 publish 无 subscribe)
3. 计算 ORPHAN_SUB (有 subscribe 无 publish)
4. 排除 R165/R166 已闭环事件
5. 排除测试代码
"""
import ast
import os
import re
import sys
import json
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_DIRS = ["core", "gui", "plugins", "scripts", "web"]
EXCLUDE_DIRS = ["tests", ".trae", "data", ".git", "node_modules", "venv", "__pycache__", ".codegraph"]
EXCLUDE_FILES_SUFFIX = [".bak", ".r147_bak", ".r128_pre", ".pyc", ".pyo"]

# R84 集中 helper 模块 (R87 修复 B-001 字符串事件 payload + B-002 data 嵌套)
R84_HELPER_MODULES = {
    "core/events/r84_event_helper.py",
    "core/events/event_bus.py",
}

# R165/R166 已闭环事件 (R163-D 排除)
R165_R166_CLOSED_EVENTS = {
    # R165 HVD-165-C 4 事件补订阅
    "data.import.failed",
    "data.import.cancelled",
    "risk.limit.exceeded",
    "trading.order.timeout",
    # R166 HVD-166 已闭环
    "system.health.changed",
    "cache.invalidated",
    "trading.position.closed",
    "risk.alert.raised",
    "strategy.signal.generated",
    "data.sync.completed",
    "plugin.loaded",
    "plugin.unloaded",
}

# 已知健康事件 (R162 HVD-162-A-1 已闭环 12/12)
KNOWN_HEALTHY_EVENTS = {
    "service.started", "service.stopped", "service.registered", "service.unregistered",
    "config.changed", "config.reloaded", "config.loaded",
    "data.received", "data.processed", "data.imported",
    "order.placed", "order.filled", "order.rejected", "order.cancelled",
    "position.opened", "position.closed", "position.updated",
    "risk.alert", "risk.warning", "risk.breach",
    "strategy.started", "strategy.stopped", "strategy.signal",
    "trade.executed", "trade.failed", "trade.timeout",
    "health.changed", "health.degraded", "health.recovered",
    "error.occurred", "error.handled", "error.reported",
}

def is_excluded_path(path: Path) -> bool:
    parts = path.parts
    for ex in EXCLUDE_DIRS:
        if ex in parts:
            return True
    for suf in EXCLUDE_FILES_SUFFIX:
        if path.name.endswith(suf):
            return True
    if "test_" in path.name or path.name.startswith("test_"):
        return True
    if "conftest" in path.name:
        return True
    return False

def is_string_arg(node) -> str:
    """提取字符串参数值"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None

def extract_event_strings_from_args(args) -> list:
    """从参数列表中提取所有事件字符串"""
    events = []
    for arg in args:
        s = is_string_arg(arg)
        if s:
            events.append(s)
    return events

def find_publish_calls(tree: ast.Module) -> list:
    """查找所有 bus.publish / event_bus.publish / publish 调用"""
    results = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "publish":
            continue

        # 检查调用者是否是 bus / event_bus
        caller = None
        if isinstance(node.func.value, ast.Name):
            caller = node.func.value.id
        elif isinstance(node.func.value, ast.Attribute):
            caller = node.func.value.attr

        # 提取事件字符串 (第一个字符串参数)
        event_str = None
        for arg in node.args:
            s = is_string_arg(arg)
            if s:
                event_str = s
                break

        if event_str:
            results.append({
                "event": event_str,
                "caller": caller,
                "line": node.lineno,
                "args_count": len(node.args),
            })
    return results

def find_subscribe_calls(tree: ast.Module) -> list:
    """查找所有 bus.subscribe / event_bus.subscribe / subscribe 调用"""
    results = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "subscribe":
            continue

        caller = None
        if isinstance(node.func.value, ast.Name):
            caller = node.func.value.id
        elif isinstance(node.func.value, ast.Attribute):
            caller = node.func.value.attr

        event_str = None
        for arg in node.args:
            s = is_string_arg(arg)
            if s:
                event_str = s
                break

        if event_str:
            results.append({
                "event": event_str,
                "caller": caller,
                "line": node.lineno,
            })
    return results

def find_publish_internal_calls(tree: ast.Module) -> list:
    """查找 _publish_internal 调用 (R162 已修复)"""
    results = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "_publish_internal":
            continue
        results.append({
            "line": node.lineno,
            "kind": "internal_publish",
        })
    return results

def scan_file(filepath: Path) -> dict:
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {"publish": [], "subscribe": [], "internal": []}

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return {"publish": [], "subscribe": [], "internal": []}

    return {
        "publish": find_publish_calls(tree),
        "subscribe": find_subscribe_calls(tree),
        "internal": find_publish_internal_calls(tree),
    }

def main():
    print("=" * 80)
    print("R163-D Stage 2: R8 事件总线 ORPHAN 残存扫描")
    print("=" * 80)

    all_publish = []  # 列表 of {event, file, line, caller}
    all_subscribe = []  # 列表 of {event, file, line, caller}

    for scan_dir in SCAN_DIRS:
        scan_path = PROJECT_ROOT / scan_dir
        if not scan_path.exists():
            continue

        for root, dirs, files in os.walk(scan_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = Path(root) / fname
                if is_excluded_path(fpath):
                    continue

                result = scan_file(fpath)
                rel_path = str(fpath.relative_to(PROJECT_ROOT))

                for p in result["publish"]:
                    p["file"] = rel_path
                    all_publish.append(p)
                for s in result["subscribe"]:
                    s["file"] = rel_path
                    all_subscribe.append(s)

    # 计算事件集
    pub_events = defaultdict(list)
    sub_events = defaultdict(list)
    for p in all_publish:
        pub_events[p["event"]].append(p)
    for s in all_subscribe:
        sub_events[s["event"]].append(s)

    # 计算 ORPHAN_PUB: 排除 R165/R166 已闭环
    orphan_pub = []
    for ev, pubs in pub_events.items():
        if ev in R165_R166_CLOSED_EVENTS or ev in KNOWN_HEALTHY_EVENTS:
            continue
        if ev not in sub_events:
            orphan_pub.append({
                "event": ev,
                "publish_count": len(pubs),
                "publish_samples": pubs[:5],
            })

    # 计算 ORPHAN_SUB
    orphan_sub = []
    for ev, subs in sub_events.items():
        if ev in R165_R166_CLOSED_EVENTS or ev in KNOWN_HEALTHY_EVENTS:
            continue
        if ev not in pub_events:
            orphan_sub.append({
                "event": ev,
                "subscribe_count": len(subs),
                "subscribe_samples": subs[:5],
            })

    print(f"\n[扫描范围] {', '.join(SCAN_DIRS)} (排除: {', '.join(EXCLUDE_DIRS)})")
    print(f"\n[统计]")
    print(f"  publish 调用数: {len(all_publish)}")
    print(f"  subscribe 调用数: {len(all_subscribe)}")
    print(f"  唯一 publish 事件: {len(pub_events)}")
    print(f"  唯一 subscribe 事件: {len(sub_events)}")
    print(f"  ORPHAN_PUB 数: {len(orphan_pub)} (有 publish 无 subscribe)")
    print(f"  ORPHAN_SUB 数: {len(orphan_sub)} (有 subscribe 无 publish)")

    print(f"\n[ORPHAN_PUB 列表 (R+1 round 待验证)]")
    for op in sorted(orphan_pub, key=lambda x: -x["publish_count"]):
        print(f"  {op['event']:<50} publish={op['publish_count']} (no subscribe)")

    print(f"\n[ORPHAN_SUB 列表 (R+1 round 待验证)]")
    for os_ in sorted(orphan_sub, key=lambda x: -x["subscribe_count"]):
        print(f"  {os_['event']:<50} subscribe={os_['subscribe_count']} (no publish)")

    # 输出 JSON
    output_path = PROJECT_ROOT / "tools" / "r163_d_stage2_scan.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "scan_date": "2026-07-22",
            "scan_dirs": SCAN_DIRS,
            "total_publish": len(all_publish),
            "total_subscribe": len(all_subscribe),
            "unique_publish_events": len(pub_events),
            "unique_subscribe_events": len(sub_events),
            "orphan_pub_count": len(orphan_pub),
            "orphan_sub_count": len(orphan_sub),
            "orphan_pub": orphan_pub,
            "orphan_sub": orphan_sub,
            "r165_r166_closed": list(R165_R166_CLOSED_EVENTS),
            "known_healthy_events": list(KNOWN_HEALTHY_EVENTS),
            "pub_events": {k: v for k, v in pub_events.items()},
            "sub_events": {k: v for k, v in sub_events.items()},
        }, f, ensure_ascii=False, indent=2)

    print(f"\n[详细结果] {output_path}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
