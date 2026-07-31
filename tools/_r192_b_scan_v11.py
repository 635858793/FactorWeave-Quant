# -*- coding: utf-8 -*-
"""
R192-B V11: V10 修正版 - 移除通用 event/publish 误判
只接受包含事件名作为字符串字面量/类名参数的 publish/subscribe 调用
"""
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_DIRS = ["core", "gui", "web", "tests", "plugins", "scripts"]
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules", "data", "data/cache"}


def find_event_strict(file_path, evt):
    """严格事件追踪: 只接受直接包含事件名"""
    pubs = []
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

        # === PUBLISH (必须直接包含事件名) ===
        # 1. 字符串字面量
        if (f"'{evt}'" in line or f'"{evt}"' in line or f"EventType.{evt}" in line):
            if '.publish(' in line or '_safe_publish(' in line:
                pubs.append((i, 'direct', line.rstrip()[:200]))
        # 2. dataclass publish(SomeEvent(...))  - 必须含类名
        # 注: 不使用 'publish(event)' 因为太通用
        if f"publish({evt}(" in line or f"publish({evt}.)" in line:
            pubs.append((i, 'dataclass', line.rstrip()[:200]))
        # 3. helper 函数
        helper = f"publish_{evt}"
        if helper + '(' in line and not line.strip().startswith('def '):
            pubs.append((i, 'helper', line.rstrip()[:200]))
        # 4. _safe_publish
        if f'_safe_publish("{evt}"' in line or f"_safe_publish('{evt}'" in line:
            if not pubs or pubs[-1][0] != i:
                pubs.append((i, 'safe_helper', line.rstrip()[:200]))
        # 5. events_to_publish 累积 (含事件名字面量)
        if 'events_to_publish' in line and 'append' in line:
            if f"'{evt}'" in line or f'"{evt}"' in line:
                pubs.append((i, 'deferred', line.rstrip()[:200]))

        # === SUBSCRIBE ===
        if (f"'{evt}'" in line or f'"{evt}"' in line):
            if '.subscribe(' in line or '_subscribe_event(' in line:
                subs.append((i, 'direct', line.rstrip()[:200]))
        if f"subscribe({evt}(" in line or f"subscribe({evt}.)" in line:
            subs.append((i, 'dataclass', line.rstrip()[:200]))
        if f"'{evt}'" in line and ', self' in line and 'self._on_' in line:
            if not subs or subs[-1][0] != i:
                subs.append((i, 'tuple', line.rstrip()[:200]))

    return pubs, subs


# 关键 4 源验证事件
verify_events = [
    # === R84 P1-10 真 ORPHAN_PUB ===
    ("order_save_retry", "P0", "ORPHAN_PUB", "R84 P1-10 修复, 0 订阅方"),

    # === R86 P0-2 已闭环 ===
    ("order_saved", "P1", "✓ 闭环", "R86 P0-2 修复"),
    ("order_save_failed", "P0", "✓ 闭环", "R86 P0-2 修复"),
    ("order_deleted", "P1", "✓ 闭环", "R86 P0-2 修复"),
    ("order_cancel_requested", "P1", "✓ 闭环", "R86 P0-2 修复"),
    ("data.masked", "P1", "✓ 闭环", "R86 P0-2 修复"),

    # === R142 P0-4 ORPHAN_PUB 候选 ===
    ("order_save_failed_need_unfreeze", "P0", "ORPHAN_PUB?", "R142 P0-4 修复"),
    ("batch_orders_created", "P0", "ORPHAN_PUB?", "R142 P0-4 修复"),
    ("batch_orders_cancelled", "P0", "ORPHAN_PUB?", "R142 P0-4 修复"),
    ("all_active_orders_cancelled", "P0", "ORPHAN_PUB?", "R142 P0-4 修复"),

    # === R84 P0-HIGH/P0-MED 已闭环 ===
    ("service.started", "P0", "✓ 闭环", "R84 P0-HIGH"),
    ("service.stopped", "P0", "✓ 闭环", "R84 P0-HIGH"),
    ("service.error", "P0", "✓ 闭环", "R84 P0-HIGH"),
    ("task.status_changed", "P0", "✓ 闭环", "R84 P0-MED"),
    ("ai.status_updated", "P0", "✓ 闭环", "R84 P0-MED"),

    # === R108 HVD-35 ORPHAN_PUB 候选 ===
    ("order_submitted", "P0", "✓ 闭环", "R108 HVD-35"),
    ("order_rejected", "P0", "✓ 闭环", "R108 HVD-35"),
    ("theme_changed", "P1", "ORPHAN_PUB?", "R108 HVD-35"),
    ("asset_selected", "P1", "ORPHAN_PUB?", "R108 HVD-35"),

    # === R190/R188 已闭环 ===
    ("sla.violation", "P0", "✓ 闭环", "R190-B 修复"),
    ("writer.health_alert", "P0", "✓ 闭环", "R188-D 修复"),
    ("MetricsAggregated", "P1", "✓ 闭环", "R147 HVD-147-ORPHAN-CLEANUP"),
    ("ResourceThresholdExceeded", "P1", "✓ 闭环", "R147 HVD-147-ORPHAN-CLEANUP"),

    # === R147 ===
    ("metrics.aggregated", "P1", "?", "需 4 源验证"),
    ("resource.threshold.exceeded", "P1", "?", "需 4 源验证"),
]


def main():
    out = []
    out.append("=" * 100)
    out.append("R192-B V11 严格事件追踪 (移除通用 publish(event) 误判)")
    out.append("=" * 100)

    summary_table = []
    for evt, severity, expected, history in verify_events:
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
                    pubs, subs = find_event_strict(full, evt)
                    for ln, kind, s in pubs:
                        pub_total += 1
                        if not rel.startswith("tests"):
                            pub_prod.append((rel, ln, kind, s))
                    for ln, kind, s in subs:
                        sub_total += 1
                        if not rel.startswith("tests"):
                            sub_prod.append((rel, ln, kind, s))

        if pub_total == 0 and sub_total > 0:
            status = "✅ ORPHAN_SUB (真)"
        elif pub_total > 0 and sub_total == 0:
            status = "✅ ORPHAN_PUB (真)"
        elif pub_total == 0 and sub_total == 0:
            status = "⚠️ 0 命中"
        else:
            status = "✓ 闭环"

        summary_table.append((evt, status, pub_total, sub_total, expected, history, severity))
        out.append(f"\n=== [{status}] {evt} ({severity}) | 预期: {expected} | {history} ===")
        out.append(f"  publish: {pub_total} ({len(pub_prod)} prod)")
        for f, ln, kind, s in pub_prod[:3]:
            out.append(f"    PUB[{kind}]: {f}:{ln}")
            out.append(f"           {s[:130]}")
        out.append(f"  subscribe: {sub_total} ({len(sub_prod)} prod)")
        for f, ln, kind, s in sub_prod[:3]:
            out.append(f"    SUB[{kind}]: {f}:{ln}")
            out.append(f"           {s[:130]}")

    out.insert(4, "\n=== SUMMARY ===")
    out.insert(5, f"  事件总数: {len(summary_table)}")
    out.insert(6, f"  真 ORPHAN_SUB: {sum(1 for s in summary_table if 'ORPHAN_SUB (真)' in s[1])}")
    out.insert(7, f"  真 ORPHAN_PUB: {sum(1 for s in summary_table if 'ORPHAN_PUB (真)' in s[1])}")
    out.insert(8, f"  闭环: {sum(1 for s in summary_table if '✓ 闭环' in s[1])}")
    out.insert(9, f"  0 命中: {sum(1 for s in summary_table if '0 命中' in s[1])}")
    out.insert(10, "")

    output = "\n".join(out)
    with open(PROJECT_ROOT / ".audit_r192_b_v11.txt", "w", encoding="utf-8") as f:
        f.write(output)
    print(output, flush=True)


if __name__ == "__main__":
    main()
