#!/usr/bin/env python3
"""
R173-D R85 假修复鉴别 4 步法应用脚本 v4
对 v4 scan 发现的 ORPHAN_PUB/SUB 进行 4 步法鉴别
"""
import json
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

with open(ROOT / ".trae/reports/rounds/_r173_d_orphan_scan_v4.json", "r", encoding="utf-8") as f:
    scan = json.load(f)

# 已知 Lowercase 误判 (变量名, 不是事件名)
LOWERCASE_FALSE_POSITIVES = {
    "event", "evt", "ev", "event1", "event2", "event3", "event4", "event_class",
    "event_cls", "event_obj", "event_obj2", "evt_name", "_evt_name", "_event",
    "event_bus", "self.event_bus", "channel", "account", "test_event", "test_evt",
    "event_a", "event_b", "event_c", "my_event", "test_event_1", "test_event_2",
    "magicmock",
    "K线数据不足，无法分析",
    "AI选股服务不支持自然语言解析",
    "AI选股服务不支持选股功能",
    "CancelledError",
    # python builtin
    "self.OrderRejectedEvent",
}

# 已知测试事件 (排除)
TEST_EVENT_PATTERNS = [
    "Chain", "Mock", "TestEvent", "AISelection", "AccountSwitched",
    "KLineCloseEvent",  # 大量测试用例
    "ConcurrentMixedEvent", "ConcurrentStatsEvent",
    "CorrelationRiskEvent", "CustomEvent", "EmptyEvent",
    "EventA", "EventB", "EventC",
    "MockStockEvent", "MultiScreenToggleEvent", "NoPeriodEvent",
    "_TestEvent", "_RealTestEvent",
    "test.event", "initial_event", "history_test", "update_event",
    "SimpleEvent",
]


def r85_classify_orphan(orphan_type: str, event_name: str, entries: list) -> dict:
    result = {
        "event_name": event_name,
        "orphan_type": orphan_type,
        "publish_count": 0 if orphan_type == "ORPHAN_SUB" else len(entries),
        "subscribe_count": 0 if orphan_type == "ORPHAN_PUB" else len(entries),
        "verdict": "待验证",
        "real_orphan": False,
        "reason": "",
        "files": [e["file"] for e in entries],
    }

    # Step 3: 排除已知误判
    if event_name in LOWERCASE_FALSE_POSITIVES:
        result["verdict"] = "误报 (Lowercase 变量名)"
        result["reason"] = f"'{event_name}' 是 Python 变量名/测试变量, 不是真实事件名"
        return result

    for pattern in TEST_EVENT_PATTERNS:
        if pattern in event_name:
            result["verdict"] = "误报 (测试事件, 业务相关性低)"
            result["reason"] = f"'{event_name}' 是测试事件"
            return result

    # Step 1: 名称合法性
    name_valid = False
    if re.match(r"^[A-Z][A-Za-z0-9]*Event$", event_name):
        name_valid = True
    elif re.match(r"^[A-Z][A-Za-z0-9]+$", event_name):
        name_valid = True
    elif "." in event_name or "_" in event_name:
        name_valid = True
    elif re.match(r"^[a-z][a-z0-9_]*$", event_name) and ("_" in event_name or "." in event_name):
        # snake_case string event
        name_valid = True

    if not name_valid:
        result["verdict"] = "误报 (不符合事件命名规范)"
        result["reason"] = f"'{event_name}' 不符合 CamelCase/dotted/snake_case 命名"
        return result

    # Step 4: 业务相关性
    files = [e["file"] for e in entries]
    prod_files = [f for f in files if not f.startswith("tests/")]
    has_prod = len(prod_files) > 0

    if has_prod:
        result["verdict"] = "真 ORPHAN (生产代码, 需修复)"
        result["real_orphan"] = True
        result["reason"] = f"生产代码 {len(prod_files)} 处 publish, 0 业务订阅"
    else:
        result["verdict"] = "ORPHAN (仅测试, 业务影响低)"
        result["real_orphan"] = True
        result["reason"] = f"仅测试代码 {len(files)} 处"

    return result


def main():
    orphan_pub_verified = {}
    for event_name, entries in scan["ORPHAN_PUB"].items():
        verdict = r85_classify_orphan("ORPHAN_PUB", event_name, entries)
        orphan_pub_verified[event_name] = verdict

    orphan_sub_verified = {}
    for event_name, entries in scan["ORPHAN_SUB"].items():
        verdict = r85_classify_orphan("ORPHAN_SUB", event_name, entries)
        orphan_sub_verified[event_name] = verdict

    real_orphan_pub = [k for k, v in orphan_pub_verified.items() if v["real_orphan"]]
    real_orphan_sub = [k for k, v in orphan_sub_verified.items() if v["real_orphan"]]
    false_positive_pub = [k for k, v in orphan_pub_verified.items() if not v["real_orphan"]]
    false_positive_sub = [k for k, v in orphan_sub_verified.items() if not v["real_orphan"]]

    result = {
        "scan_summary": {
            "files_scanned": scan["files_scanned"],
            "publish_total_events": scan["publish_total_events"],
            "subscribe_total_events": scan["subscribe_total_events"],
            "matched_events": scan["matched_events"],
            "ORPHAN_PUB_raw": scan["ORPHAN_PUB_count"],
            "ORPHAN_SUB_raw": scan["ORPHAN_SUB_count"],
            "ORPHAN_PUB_real": len(real_orphan_pub),
            "ORPHAN_SUB_real": len(real_orphan_sub),
            "ORPHAN_PUB_false_positive": len(false_positive_pub),
            "ORPHAN_SUB_false_positive": len(false_positive_sub),
        },
        "ORPHAN_PUB_real": {k: orphan_pub_verified[k] for k in sorted(real_orphan_pub)},
        "ORPHAN_SUB_real": {k: orphan_sub_verified[k] for k in sorted(real_orphan_sub)},
        "ORPHAN_PUB_false_positive": {k: orphan_pub_verified[k] for k in sorted(false_positive_pub)},
        "ORPHAN_SUB_false_positive": {k: orphan_sub_verified[k] for k in sorted(false_positive_sub)},
    }

    out_path = ROOT / ".trae/reports/rounds/_r173_d_orphan_verified_v4.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"ORPHAN_PUB raw: {scan['ORPHAN_PUB_count']}")
    print(f"ORPHAN_PUB real: {len(real_orphan_pub)}")
    print(f"ORPHAN_PUB false positive: {len(false_positive_pub)}")
    print(f"ORPHAN_SUB raw: {scan['ORPHAN_SUB_count']}")
    print(f"ORPHAN_SUB real: {len(real_orphan_sub)}")
    print(f"ORPHAN_SUB false positive: {len(false_positive_sub)}")
    print(f"\nResult saved to: {out_path}")

    print("\n=== 真 ORPHAN_PUB (生产代码) - 按 publish 数排序 ===")
    real_pub_sorted = sorted(orphan_pub_verified.items(), key=lambda x: -len(x[1]["files"]) if x[1]["real_orphan"] else 0)
    for k, v in real_pub_sorted[:30]:
        if v["real_orphan"] and "真" in v["verdict"]:
            print(f"  [{len(v['files'])}] {k}: {v['reason'][:60]}")
            for f in v["files"][:2]:
                print(f"    {f}")


if __name__ == "__main__":
    main()
