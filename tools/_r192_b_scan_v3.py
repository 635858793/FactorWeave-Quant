# -*- coding: utf-8 -*-
"""
R192-B V3: 字符串事件精确验证 (排除变量名)
对 V2 扫描的 ORPHAN_PUB 业务候选做精确字符串匹配验证
"""
import os
import re
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_DIRS = ["core", "gui", "web", "tests", "plugins", "scripts"]

# V2 业务候选 (排除变量名: w, position_event, request_event, ui_data_ready_event, trade_event)
ORPHAN_PUB_CANDIDATES = [
    "MetricsAggregated",
    "ResourceThresholdExceeded",
    "ApplicationThresholdExceeded",
    "ApplicationAlert",  # ORPHAN_SUB 候选
    "ResourceAlert",  # ORPHAN_SUB 候选
    "market.quote_updated",
    "sla.violation",
    "environment.changed",
    "performance.alert",
    "performance.alert_triggered",
    "performance.metrics_updated",
    "performance.optimization_completed",
    "performance.periodic_report",
    "order_filled",  # 不在 EventType 中
    "ai_selection.started",
    "bettafish.agent.started",
    "HybridRecommendationCompleted",
    "service.started",
    "service.error",
    "task_started",
    "task_completed",
    "task_failed",
    "task_retrying",
    "data_source_switched",
    "plugin_unloaded",
    "system.optimization.complete",
    "system.optimization.error",
    "system.optimization.start",
    "UpdateHistoryEvent",
    "ai.status_updated",
    "task.status_changed",
]


def find_str_in_files(pattern, file_glob="*.py"):
    """在指定目录递归搜索字符串 (用 Python 内部实现,绕过 findstr/ripgrep 限制)"""
    results = []
    for subdir in SCAN_DIRS:
        scan_path = PROJECT_ROOT / subdir
        if not scan_path.exists():
            continue
        for root, dirs, files in os.walk(scan_path):
            # 排除
            dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", ".pytest_cache", "node_modules", ".mypy_cache", ".cache"}]
            for fn in files:
                if not fn.endswith('.py'):
                    continue
                full = Path(root) / fn
                try:
                    with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                        for i, line in enumerate(f, 1):
                            if pattern in line:
                                rel = str(full.relative_to(PROJECT_ROOT))
                                results.append((rel, i, line.rstrip()))
                except Exception:
                    pass
    return results


def main():
    print("=" * 100, flush=True)
    print("R192-B V3 字符串事件 4 源验证", flush=True)
    print("=" * 100, flush=True)
    print(f"扫描目录: {SCAN_DIRS}", flush=True)
    print(flush=True)

    for evt in ORPHAN_PUB_CANDIDATES:
        print(f"\n=== {evt} ===", flush=True)
        # 同时搜 publish 和 subscribe 上下文
        matches = find_str_in_files(evt)
        pub_hits = []
        sub_hits = []
        other_hits = []
        for f, l, s in matches:
            sl = s.lower()
            if '.publish(' in sl or 'publish(' in sl:
                if evt in s and ('"' + evt + '"' in s or "'" + evt + "'" in s or "EventType." + evt in s):
                    pub_hits.append((f, l, s))
                else:
                    pub_hits.append((f, l, s))
            elif '.subscribe(' in sl or 'subscribe(' in sl:
                sub_hits.append((f, l, s))
            else:
                other_hits.append((f, l, s))

        # 输出 publish
        if pub_hits:
            print(f"  publish ({len(pub_hits)}):", flush=True)
            for f, l, s in pub_hits[:5]:
                print(f"    {f}:{l}", flush=True)
            if len(pub_hits) > 5:
                print(f"    ... +{len(pub_hits) - 5}", flush=True)
        # 输出 subscribe
        if sub_hits:
            print(f"  subscribe ({len(sub_hits)}):", flush=True)
            for f, l, s in sub_hits[:5]:
                print(f"    {f}:{l}", flush=True)
            if len(sub_hits) > 5:
                print(f"    ... +{len(sub_hits) - 5}", flush=True)
        if other_hits:
            print(f"  other ({len(other_hits)}):", flush=True)
            for f, l, s in other_hits[:3]:
                print(f"    {f}:{l}  -- {s[:100]}", flush=True)
        if not pub_hits and not sub_hits and not other_hits:
            print(f"  ⚠️ 0 命中!", flush=True)


if __name__ == "__main__":
    main()
