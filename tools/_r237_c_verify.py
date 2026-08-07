# -*- coding: utf-8 -*-
"""R237-C 关键 ORPHAN_PUB 候选 4 源验证 (核心业务事件)."""
import sys
import json
import subprocess

CRITICAL_ORPHANS = [
    "data_source_switched",
    "plugin_unloaded",
    "task_completed",
    "task_submitted",
    "task_started",
    "task_cancelled",
    "environment.changed",
    "ai_selection.started",
    "ai_selection.completed",
    "ai_selection.failed",
    "auto_training.completed",
    "auto_training.failed",
    "performance.alert",
    "performance.periodic_report",
    "service_degradation",
    "service_reset",
    "funding_rate.analyzed",
    "funding_rates.batch_analyzed",
    "market.quote_updated",
    "training.task.created",
    "model.version.created",
    "model.version.current_changed",
    "model.version.rolled_back",
    "training.task.deleted",
    "training.progress_updated",
    "performance.metrics_collected",
    "performance.optimization_completed",
    "performance.alert_triggered",
    "prediction.recorded",
    "prediction.accuracy_updated",
    "security.threat_detected",
    "service.orphan_scan_completed",
    "orders.batch_confirmed",
    "order.confirmed",
    "order.validation_failed",
    "order.risk_check_failed",
    "order.position_limit_failed",
    "positions_refreshed",
    "fund_infos_refreshed",
    "all_data_synced",
    "account_load_failed",
    "order_fill_saved",
    "order_deleted",
    "order_save_failed",
    "order_cancel_requested",
    "market.contract_received",
    "market.connected",
    "market.disconnected",
    "bettafish.agent.initialized",
    "bettafish.sentiment.analysis.completed",
    "data.masked",
    "high_confidence_trend",
]

def grep_4source(event_name):
    """4 源验证: publish + subscribe (含 5 模式) + 业务调用方."""
    sources = {}

    # Source 1: Publish (publish 字符串)
    try:
        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", f"publish.*{event_name}\\|publish.*{event_name}\\W", "."],
            capture_output=True, text=True, encoding="utf-8", timeout=30
        )
        sources['publish'] = result.stdout[:2000] if result.stdout else "(no match)"
    except Exception as e:
        sources['publish'] = f"err: {e}"

    # Source 2: Subscribe (4 类订阅模式 + 5 类 v2 模式)
    subscribe_patterns = [
        f"subscribe.*{event_name}",
        f"_subscribe_event.*{event_name}",
        f"on.*{event_name}",
        f"listen.*{event_name}",
    ]
    sub_hits = []
    for pat in subscribe_patterns:
        try:
            result = subprocess.run(
                ["grep", "-rn", "--include=*.py", pat, "."],
                capture_output=True, text=True, encoding="utf-8", timeout=30
            )
            if result.stdout:
                sub_hits.append(f"PATTERN [{pat}]:\n{result.stdout[:1500]}")
        except Exception as e:
            pass
    sources['subscribe'] = "\n".join(sub_hits) if sub_hits else "(no match)"

    return sources


results = {}
print("=" * 60)
print(f"R237-C 关键 ORPHAN_PUB 4 源验证 ({len(CRITICAL_ORPHANS)} 个核心业务事件)")
print("=" * 60)

for evt in CRITICAL_ORPHANS:
    src = grep_4source(evt)
    has_pub = "(no match)" not in src['publish']
    has_sub = "(no match)" not in src['subscribe']
    results[evt] = {
        'has_publish': has_pub,
        'has_subscribe': has_sub,
        'publish_count': src['publish'].count('\n') if has_pub else 0,
        'subscribe_count': src['subscribe'].count('\n') if has_sub else 0,
    }
    status = "✓PUB+SUB" if (has_pub and has_sub) else (
        "⚠ PUB only (ORPHAN_PUB?)" if has_pub else
        "✗ NONE"
    )
    print(f"  {evt}: {status}")

with open('.trae/reports/rounds/raw/audit_r237_c_4source_verify.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print()
print("=" * 60)
print("ORPHAN_PUB 真候选 (有 publish 但 0 subscribe):")
print("=" * 60)
true_orphans = [evt for evt, r in results.items() if r['has_publish'] and not r['has_subscribe']]
for evt in true_orphans:
    print(f"  {evt}")
print(f"共 {len(true_orphans)} 个候选")
