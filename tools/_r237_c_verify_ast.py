# -*- coding: utf-8 -*-
"""R237-C 精确 4 源验证: 关键业务 ORPHAN_PUB 候选深度审计."""
import os
import ast
import json
from pathlib import Path

CRITICAL = [
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

# 根目录
ROOT = Path(".")
SKIP_DIRS = {"__pycache__", ".git", ".idea", ".vscode", ".pytest_cache",
             "node_modules", "dist", "build", ".cursor", ".trae", ".codegraph",
             ".claude", ".serena", "tools"}


def walk_py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith("_r")]
        for fn in filenames:
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def is_event_string_arg(node, event_name):
    """检查 ast.Call 的第 1 个参数是否为 event_name (字符串字面量)."""
    if not node.args:
        return False
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value == event_name
    return False


def find_publish_calls(tree, event_name):
    """找到所有精确匹配 event_name 的 publish/emit/dispatch/fire 调用."""
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("publish", "publish_async", "emit", "dispatch", "fire"):
                if is_event_string_arg(node, event_name):
                    matches.append(node)
    return matches


def find_subscribe_calls(tree, event_name):
    """找到所有精确匹配 event_name 的 subscribe 调用 (含 5 模式)."""
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr in ("subscribe", "subscribe_topic", "subscribe_global",
                        "subscribe_async", "on", "listen", "add_listener",
                        "add_event_listener", "register_handler",
                        "register_event_handler", "_subscribe_event",
                        "_add_event_listener"):
                if is_event_string_arg(node, event_name):
                    matches.append(node)
    return matches


print("=" * 80)
print("R237-C 精确 4 源验证 (AST 级别, 排除误报)")
print("=" * 80)

results = {}
for evt in CRITICAL:
    pubs = []
    subs = []
    for filepath in walk_py_files(ROOT):
        try:
            src = filepath.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src, filename=str(filepath))
            for node in find_publish_calls(tree, evt):
                pubs.append((str(filepath), node.lineno))
            for node in find_subscribe_calls(tree, evt):
                subs.append((str(filepath), node.lineno))
        except Exception:
            pass

    results[evt] = {
        "publish_count": len(pubs),
        "subscribe_count": len(subs),
        "publish_sites": pubs[:5],
        "subscribe_sites": subs[:5],
    }
    if pubs and not subs:
        status = "ORPHAN_PUB"
    elif not pubs and not subs:
        status = "无匹配 (假阳性)"
    else:
        status = "OK"
    print(f"  {evt}: pub={len(pubs)}, sub={len(subs)} [{status}]")

with open('.trae/reports/rounds/raw/audit_r237_c_4source_ast.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False, default=str)

print()
print("=" * 80)
print("ORPHAN_PUB 真候选 (pub > 0 且 sub = 0):")
print("=" * 80)
true_orphans = [(e, r) for e, r in results.items() if r['publish_count'] > 0 and r['subscribe_count'] == 0]
for e, r in true_orphans:
    sites = ", ".join(f"{Path(s).name}:{ln}" for s, ln in r['publish_sites'])
    print(f"  {e} (publish: {sites})")
print(f"共 {len(true_orphans)} 个真 ORPHAN_PUB 候选")
