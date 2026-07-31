# -*- coding: utf-8 -*-
"""
R192-B V9: 最终 V8 + V7 综合 (双轨)
  - 保留 V7 模式: dataclass subscribe/publish(TickDataEvent, ...)
  - 保留 V8 模式: events_to_publish 累积
  - 移除 V8 误判: orphan_monitor.py 通用循环
  - 移除 V8 误判: trading_confirmation_service.py 通用 for-loop
  - 业务调用链: 标识 (动态 dispatch only) vs (直接 dispatch)
"""
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_DIRS = ["core", "gui", "web", "tests", "plugins", "scripts"]
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules", "data", "data/cache"}


def find_event_final(file_path, evt):
    """最终 4 源事件追踪"""
    pubs = []  # (line, type, line_content)
    subs = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.read().splitlines(keepends=False)
    except Exception:
        return pubs, subs

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('#') and 'subscribe' not in line and 'publish' not in line:
            continue

        # === PUBLISH 模式 ===
        # 1. 字符串字面量
        if (f"'{evt}'" in line or f'"{evt}"' in line or f"EventType.{evt}" in line or
                f"EventType['{evt}']" in line or f'EventType["{evt}"]' in line):
            if '.publish(' in line or '_safe_publish(' in line:
                pubs.append((i, 'direct', line.rstrip()[:200]))
        # 2. dataclass publish
        if (f"publish({evt}" in line or
                f"publish({evt.lower()}" in line or
                f"publish({evt[0].lower()}{evt[1:]}" in line):
            pubs.append((i, 'dataclass', line.rstrip()[:200]))
        # 3. helper 函数
        helper = f"publish_{evt}"
        if helper + '(' in line and not line.strip().startswith('def '):
            pubs.append((i, 'helper', line.rstrip()[:200]))
        if f"_safe_publish(\"{evt}\"" in line or f"_safe_publish('{evt}'" in line:
            if not pubs or pubs[-1][0] != i:
                pubs.append((i, 'safe_helper', line.rstrip()[:200]))
        # 4. events_to_publish 累积 (trading_confirmation_service.py:115-156)
        if ('events_to_publish' in line and ('append' in line or '+=' in line)
                and (f"'{evt}'" in line or f'"{evt}"' in line)):
            pubs.append((i, 'deferred', line.rstrip()[:200]))

        # === SUBSCRIBE 模式 ===
        if (f"'{evt}'" in line or f'"{evt}"' in line or f"EventType.{evt}" in line or
                f"EventType['{evt}']" in line or f'EventType["{evt}"]' in line):
            if '.subscribe(' in line or '_subscribe_event(' in line:
                subs.append((i, 'direct', line.rstrip()[:200]))
        if (f"subscribe({evt}" in line or f"subscribe({evt.lower()}" in line or
                f"subscribe({evt[0].lower()}{evt[1:]}" in line):
            subs.append((i, 'dataclass', line.rstrip()[:200]))
        if f"'{evt}'" in line and (', self' in line or ',self' in line) and 'self._on_' in line:
            if not subs or subs[-1][0] != i:
                subs.append((i, 'tuple', line.rstrip()[:200]))

    return pubs, subs


# 4 源验证事件
verify_events = [
    # === ORPHAN_PUB (R84 P1-10 修复, 但 0 订阅) ===
    ("order_save_retry", "ORPHAN_PUB", "P0", "R84 P1-10 修复, 0 订阅方"),
    # === PascalCase 字符串事件 ===
    ("TickDataEvent", "ORPHAN_PUB?", "P0", "r84_event_helper.py:441 + level2_data_panel.py:873 sub"),
    ("RealtimeDataEvent", "ORPHAN_PUB?", "P0", "r84_event_helper.py:557 + level2_data_panel.py:872 sub"),
    ("OrderBookEvent", "ORPHAN_PUB?", "P0", "r84_event_helper.py:571 + level2_data_panel.py:874 sub"),

    # === ORPHAN_SUB V8 已闭环 ===
    ("task_started", "ORPHAN_SUB", "P0", "动态 dispatch"),
    ("task_completed", "ORPHAN_SUB", "P0", "动态 dispatch"),
    ("task_failed", "ORPHAN_SUB", "P0", "动态 dispatch"),
    ("task_retrying", "ORPHAN_SUB", "P0", "动态 dispatch"),
    ("HybridRecommendationCompleted", "ORPHAN_SUB", "P0", "publish(completion_event) 漏检"),
    ("data_source_switched", "ORPHAN_SUB", "P1", "R134 设计意图保留"),
    ("order.confirmed", "ORPHAN_SUB?", "P0", "events_to_publish 累积"),
    ("order.risk_check_failed", "ORPHAN_SUB?", "P0", "events_to_publish 累积"),
    ("order.position_limit_failed", "ORPHAN_SUB?", "P0", "events_to_publish 累积"),
    ("order.validation_failed", "ORPHAN_SUB?", "P0", "events_to_publish 累积 + order_service.py:741"),
    ("order.cancel_requested", "ORPHAN_SUB", "P1", "0 命中验证"),
    ("bettafish.agent.stopped", "ORPHAN_SUB", "P1", "R134 设计意图保留"),
    ("data.masked", "ORPHAN_SUB", "P1", "需追溯"),
    ("PositionReconcileEvent", "ORPHAN_SUB", "P0", "_reconcile_loop_iteration 间接"),
]


def main():
    out = []
    out.append("=" * 100)
    out.append("R192-B V9 最终 4 源验证")
    out.append("=" * 100)
    out.append("\nV9 改进 (vs V7/V8):")
    out.append("  - 移除 V8 误判: orphan_monitor.py:155 (通用循环, 非真 publish)")
    out.append("  - 移除 V8 误判: trading_confirmation_service.py:162 (通用 for-loop)")
    out.append("  - 保留 V7 dataclass: subscribe(TickDataEvent, ...) 类名匹配")
    out.append("  - 保留 V8 events_to_publish 累积 + 标注 deferred 模式")
    out.append("  - publish 类型分类: direct / dataclass / helper / safe_helper / deferred")

    summary_table = []
    for evt, evt_type, severity, note in verify_events:
        pub_total, sub_total = 0, 0
        pub_prod, sub_prod = [], []
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
                    rel = str(full.relative_to(PROJECT_ROOT))
                    pubs, subs = find_event_final(full, evt)
                    for ln, kind, s in pubs:
                        pub_total += 1
                        if not rel.startswith("tests"):
                            pub_prod.append((rel, ln, kind, s))
                    for ln, kind, s in subs:
                        sub_total += 1
                        if not rel.startswith("tests"):
                            sub_prod.append((rel, ln, kind, s))

        # 区分真 ORPHAN 与假 ORPHAN (deferred 模式算闭环)
        deferred_only = (pub_total > 0
                         and all(p[2] == 'deferred' for p in pub_prod)
                         and sub_total > 0)
        if pub_total == 0 and sub_total > 0:
            status = "✅ ORPHAN_SUB (真)"
        elif deferred_only:
            status = "⚠️ deferred 闭环 (V7 误报)"
        elif pub_total > 0 and sub_total == 0:
            status = "✅ ORPHAN_PUB (真)"
        elif pub_total == 0 and sub_total == 0:
            status = "⚠️ 0 命中"
        else:
            status = "✓ 闭环"

        summary_table.append((evt, status, pub_total, sub_total, len(pub_prod), len(sub_prod), note, severity))
        out.append(f"\n=== [{status}] {evt} ({severity}) | {note} ===")
        out.append(f"  publish total: {pub_total} | prod: {len(pub_prod)}")
        for f, ln, kind, s in pub_prod[:5]:
            out.append(f"    PUB[{kind}]: {f}:{ln}")
            out.append(f"           {s[:130]}")
        out.append(f"  subscribe total: {sub_total} | prod: {len(sub_prod)}")
        for f, ln, kind, s in sub_prod[:5]:
            out.append(f"    SUB[{kind}]: {f}:{ln}")
            out.append(f"           {s[:130]}")

    # SUMMARY
    out.insert(4, "\n=== SUMMARY ===")
    out.insert(5, f"  事件总数: {len(summary_table)}")
    out.insert(6, f"  真 ORPHAN_SUB: {sum(1 for s in summary_table if 'ORPHAN_SUB (真)' in s[1])}")
    out.insert(7, f"  真 ORPHAN_PUB: {sum(1 for s in summary_table if 'ORPHAN_PUB (真)' in s[1])}")
    out.insert(8, f"  deferred 闭环 (V7 误报): {sum(1 for s in summary_table if 'deferred' in s[1])}")
    out.insert(9, f"  闭环: {sum(1 for s in summary_table if '✓ 闭环' in s[1])}")
    out.insert(10, f"  0 命中: {sum(1 for s in summary_table if '0 命中' in s[1])}")
    out.insert(11, "")

    output = "\n".join(out)
    with open(PROJECT_ROOT / ".audit_r192_b_v9.txt", "w", encoding="utf-8") as f:
        f.write(output)
    print(output, flush=True)


if __name__ == "__main__":
    main()
