# -*- coding: utf-8 -*-
"""
R192-B V6: 终极精确版 ORPHAN 业务扫描
- 识别 dotted snake_case 字符串事件
- 识别 publish_xxx() / emit_xxx() 集中 helper
- 识别 EventType.XXX 枚举
- 排除变量名/参数名误报
"""
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_DIRS = ["core", "gui", "web", "tests", "plugins", "scripts"]
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules", "data", "data/cache"}


def find_event_v6(file_path, evt):
    """终极 4 源验证:
    - 字符串 publish('evt')
    - 字符串 publish("evt")
    - dotted publish('order.confirmed')
    - EventType.EVT
    - EventType['EVT']
    - publish_evt() helper call
    - _safe_publish("evt", ...)
    - tuple list: ('evt', handler)
    """
    pubs = []
    subs = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped.startswith('#') and 'Why' not in line and 'Fix' not in line and 'subscribe' not in line and 'publish' not in line:
                    continue

                # 1. publish 调用检测
                is_publish_call = ('.publish(' in line or '_safe_publish(' in line)
                is_subscribe_call = ('.subscribe(' in line or '_subscribe_event(' in line or
                                    ('(self,' in line and 'self._on_' in line))

                # dotted 字符串检测
                has_evt = (f"'{evt}'" in line or f'"{evt}"' in line or
                           f"EventType.{evt}" in line or f"EventType['{evt}']" in line or
                           f'EventType["{evt}"]' in line)

                if is_publish_call and has_evt:
                    pubs.append((i, line.rstrip()[:200]))
                elif is_subscribe_call and has_evt:
                    subs.append((i, line.rstrip()[:200]))
                elif has_evt and ', self' in line and 'self._on_' in line:
                    # tuple list 形式
                    if not subs or subs[-1][0] != i:
                        subs.append((i, line.rstrip()[:200]))

                # 2. helper 函数检测
                if not has_evt:
                    helper = f"publish_{evt}" if not evt.startswith("publish_") else evt
                    if (helper + '(') in line and not stripped.startswith('#'):
                        pubs.append((i, line.rstrip()[:200]))
                    helper2 = f"emit_{evt}" if not evt.startswith("emit_") else evt
                    if (helper2 + '(') in line and not stripped.startswith('#'):
                        pubs.append((i, line.rstrip()[:200]))
    except Exception:
        pass
    return pubs, subs


events = [
    # ORPHAN_PUB 候选
    "ai_selection.started",
    "ai_selection.completed",
    "ai_selection.failed",
    # 真正的 ORPHAN_SUB (0 publish)
    "task_started", "task_completed", "task_failed", "task_retrying",
    "HybridRecommendationCompleted",
    "data_source_switched",
    "bettafish.sentiment.analysis.completed",
    "ai.status_updated", "task.status_changed", "performance.metrics_updated",
    "order_save_retry", "order_rejected",
    "order_submitted", "order_submitted_failed",
    # dotted 事件 (V5 漏检)
    "order.confirmed", "order.risk_check_failed", "order.position_limit_failed",
    "order.validation_failed", "order.executed", "order.filled",
    "order.cancelled", "order.cancel_failed", "order.cancel_rejected",
    "order.saved", "order.save_failed", "order.deleted", "order.created",
    "order.update", "order.terminal_state", "order.partially_filled",
    "risk.monitor", "risk.stop_trading", "risk.reduce_position", "risk.emergency_liquidation",
    "trading_interface_circuit_breaker",
    "position.saved", "position.deleted", "position.created", "position.updated",
    "account.created", "account.updated", "account.deleted", "fund.updated",
    "security.threat_detected", "orders.batch_confirmed",
    "cash_frozen", "cash_unfrozen", "account_load_failed", "account_status_changed",
    "accounts_refreshed", "all_data_synced",
    "writer.health_alert", "risk.account_drift",
    "market.quote_updated", "sla.violation",
    "data.import.complete", "data.import.ui_feedback",
    "data.masked",
    "order_saved", "order_save_failed", "order_deleted", "order_cancel_requested",
    "bettafish.agent.started", "bettafish.agent.stopped",
    "bettafish.analysis.completed", "bettafish.analysis.failed",
    "service.started", "service.stopped", "service.error",
    "plugin_unloaded", "system.optimization.start", "system.optimization.complete",
    "system.optimization.error",
    "UpdateHistoryEvent", "ApplicationAlert", "ResourceAlert", "BaselineDriftAlert",
    # PascalCase 事件类
    "KLineCloseEvent", "AISelectionStartedEvent", "AISelectionCompletedEvent",
    "AISelectionFailedEvent", "AccountSwitchedEvent", "AnalysisCompleteEvent",
    "ApplicationMetricRecorded", "AssetSelectedEvent", "AssetTypeChangedEvent",
    "ChartUpdateEvent", "ComputedIndicatorEvent", "ConfigChangedEvent",
    "CorrelationRiskEvent", "DataAnalysisEvent", "DataIntegrityEvent",
    "DataUpdateEvent", "ExecutionQualitySnapshotEvent", "ModelRetrainTriggerEvent",
    "MultiScreenToggleEvent", "OrderBookEvent", "OrderCancelFailedEvent",
    "OrderCancelRejectedEvent", "OrderFilledEvent", "OrderModifiedEvent",
    "OrderSubmittedFailedEvent", "OrderSubmittedSuccessEvent",
    "PatternSignalsDisplayEvent", "PositionReconcileEvent", "PositionUpdatedEvent",
    "RealtimeComponentsRestoredEvent", "RealtimeComponentsUnavailableEvent",
    "RiskActualSnapshotEvent", "SignalGeneratedEvent", "SignalPerformanceSnapshotEvent",
    "StockSelectedEvent", "StrategyErrorEvent", "StrategyPausedEvent",
    "StrategyResumedEvent", "StrategyStartedEvent", "StrategyStoppedEvent",
    "SystemResourceUpdated", "ThemeChangedEvent", "TickDataEvent",
    "TradeExecutedEvent", "TradeFeedbackEvent", "TradeSignalReceivedEvent",
    "UIDataReadyEvent",
]


def main():
    out = []
    out.append("=" * 100)
    out.append("R192-B V6 终极 ORPHAN 业务扫描 (含 dotted 字符串 + PascalCase 事件类)")
    out.append("=" * 100)

    summary = []
    for evt in events:
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
                    pubs, subs = find_event_v6(full, evt)
                    for i, s in pubs:
                        pub_total += 1
                        if not rel.startswith("tests"):
                            pub_prod.append((rel, i, s))
                    for i, s in subs:
                        sub_total += 1
                        if not rel.startswith("tests"):
                            sub_prod.append((rel, i, s))

        # 4 源验证 + ORPHAN 判定
        if pub_total == 0 and sub_total > 0:
            status = "ORPHAN_SUB (有 sub 0 pub)"
        elif pub_total > 0 and sub_total == 0:
            status = "ORPHAN_PUB (有 pub 0 sub)"
        elif pub_total == 0 and sub_total == 0:
            status = "(0 命中)"
        else:
            status = "OK (业务链闭环)"

        summary.append((evt, status, pub_total, sub_total, len(pub_prod), len(sub_prod)))
        out.append(f"\n{status}: {evt} (pub total {pub_total}/{len(pub_prod)} prod | sub total {sub_total}/{len(sub_prod)} prod)")
        for f, l, s in pub_prod[:3]:
            out.append(f"    PUB: {f}:{l}: {s[:120]}")
        for f, l, s in sub_prod[:3]:
            out.append(f"    SUB: {f}:{l}: {s[:120]}")

    out.insert(4, "\n=== SUMMARY TABLE ===")
    for evt, status, pt, st, pp, sp in summary:
        out.insert(5, f"  {status:30s} {evt:50s} pub={pt}/{pp} | sub={st}/{sp}")

    output = "\n".join(out)
    with open(PROJECT_ROOT / ".audit_r192_b_v6.txt", "w", encoding="utf-8") as f:
        f.write(output)
    print(output, flush=True)


if __name__ == "__main__":
    main()
