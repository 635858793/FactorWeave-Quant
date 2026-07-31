# -*- coding: utf-8 -*-
"""
R192-B V5: 精确 ORPHAN 业务候选 + 4 源验证
只关注 prod 业务事件 (非变量名/属性名)
"""
import os
import re
from pathlib import Path
from collections import Counter
import sys

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_DIRS = ["core", "gui", "web", "tests", "plugins", "scripts"]
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules", "data", "data/cache"}

# 关键业务事件清单
events = [
    ("ai_selection.started", "ORPHAN_PUB", "P1", "0 prod publish, 仅 test"),
    ("HybridRecommendationCompleted", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("task_started", "ORPHAN_SUB", "P0", "0 publish, 3 subscribe"),
    ("task_completed", "ORPHAN_SUB", "P0", "0 publish, 3 subscribe"),
    ("task_failed", "ORPHAN_SUB", "P0", "0 publish, 3 subscribe"),
    ("task_retrying", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("data_source_switched", "ORPHAN_SUB", "P1", "0 publish, 3 subscribe"),
    ("order_created", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("order_submitted", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("order_save_retry", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("cancel_order_rejected", "ORPHAN_SUB", "P1", "0 publish, 1 subscribe"),
    ("bettafish.sentiment.analysis.completed", "ORPHAN_SUB", "P1", "0 publish, 1 subscribe"),
    ("bettafish.analysis.completed", "ORPHAN_SUB", "P1", "需 4 源验证"),
    ("bettafish.analysis.failed", "ORPHAN_SUB", "P1", "需 4 源验证"),
    ("order_cancel_failed", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("order_filled", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("order_cancelled", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("order_rejected", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("order_submitted_success", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("order_submitted_failed", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("order_terminal_state", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("order_partially_filled", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("order.confirmed", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("order.risk_check_failed", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("order.position_limit_failed", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("order.validation_failed", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("order.updated", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("order.executed", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("position_updated", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("position_created", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("position_deleted", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("position_saved", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("account_created", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("account_updated", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("account_deleted", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("fund_updated", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("risk.monitor", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("risk.stop_trading", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("risk.reduce_position", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("risk.emergency_liquidation", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("trading_interface_circuit_breaker", "ORPHAN_SUB", "P0", "需 4 源验证"),
    ("ai.status_updated", "ORPHAN_PUB?SUB?", "P0", "需 4 源验证"),
    ("task.status_changed", "ORPHAN_PUB?SUB?", "P0", "需 4 源验证"),
    ("performance.metrics_updated", "ORPHAN_PUB?SUB?", "P0", "需 4 源验证"),
    ("KLineCloseEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("AISelectionStartedEvent", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("AISelectionCompletedEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("AISelectionFailedEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("ApplicationAlert", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("ResourceAlert", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("AccountSwitchedEvent", "ORPHAN_SUB", "P0", "0 publish, 14 subscribe"),
    ("AnalysisCompleteEvent", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("ApplicationMetricRecorded", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("AssetSelectedEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("AssetTypeChangedEvent", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("ChartUpdateEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("ComputedIndicatorEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("ConfigChangedEvent", "ORPHAN_SUB", "P0", "0 publish, 3 subscribe"),
    ("CorrelationRiskEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("DataAnalysisEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("DataIntegrityEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("DataUpdateEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("ExecutionQualitySnapshotEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("ModelRetrainTriggerEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("MultiScreenToggleEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("OrderBookEvent", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("OrderCancelFailedEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("OrderCancelRejectedEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("OrderFilledEvent", "ORPHAN_SUB", "P0", "0 publish, 4 subscribe"),
    ("OrderModifiedEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("OrderSubmittedFailedEvent", "ORPHAN_SUB", "P0", "0 publish, 3 subscribe"),
    ("OrderSubmittedSuccessEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("PatternSignalsDisplayEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("PositionReconcileEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("PositionUpdatedEvent", "ORPHAN_SUB", "P0", "0 publish, 5 subscribe"),
    ("RealtimeComponentsRestoredEvent", "ORPHAN_SUB", "P0", "0 publish, 3 subscribe"),
    ("RealtimeComponentsUnavailableEvent", "ORPHAN_SUB", "P0", "0 publish, 3 subscribe"),
    ("RiskActualSnapshotEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("SignalGeneratedEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("SignalPerformanceSnapshotEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("StockSelectedEvent", "ORPHAN_SUB", "P0", "0 publish, 4 subscribe"),
    ("StrategyErrorEvent", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("StrategyPausedEvent", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("StrategyResumedEvent", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("StrategyStartedEvent", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("StrategyStoppedEvent", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("SystemResourceUpdated", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("ThemeChangedEvent", "ORPHAN_SUB", "P0", "0 publish, 4 subscribe"),
    ("TickDataEvent", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("TradeExecutedEvent", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("TradeFeedbackEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("TradeSignalReceivedEvent", "ORPHAN_SUB", "P0", "0 publish, 1 subscribe"),
    ("UIDataReadyEvent", "ORPHAN_SUB", "P0", "0 publish, 2 subscribe"),
    ("UpdateHistoryEvent", "ORPHAN_SUB", "P0", "5 publish, 1 subscribe"),
]


def find_event(file_path, evt):
    """在文件中找事件 publish/subscribe 调用"""
    pubs = []
    subs = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                # publish 模式
                if (f"'{evt}'" in line or f'"{evt}"' in line or f"EventType.{evt}" in line or f"EventType['{evt}']" in line) and '.publish(' in line:
                    pubs.append((i, line.rstrip()[:200]))
                # subscribe 模式
                if (f"'{evt}'" in line or f'"{evt}"' in line) and ('.subscribe(' in line or '_subscribe_event(' in line):
                    subs.append((i, line.rstrip()[:200]))
                # 元组形式 ('EVT', handler)
                if f"'{evt}'" in line and ', self' in line and 'self._on_' in line:
                    if not subs or subs[-1][0] != i:
                        subs.append((i, line.rstrip()[:200]))
    except Exception:
        pass
    return pubs, subs


def main():
    out_lines = []
    out_lines.append("=" * 100)
    out_lines.append("R192-B V5 4 源精确验证 (关键业务事件)")
    out_lines.append("=" * 100)

    # 4 源验证: CodeGraph (扫描基线) + Read (上溯源码) + Grep (跨子目录) + 业务调用链
    out_lines.append("\n4 源验证清单:")
    out_lines.append("  - 源 1: CodeGraph 节点追踪 (codegraph_search / codegraph_callers)")
    out_lines.append("  - 源 2: Grep 跨 4 子目录 (core/gui/web/tests + plugins/scripts)")
    out_lines.append("  - 源 3: Read 上溯源码 (publish/subscribe 上下文 + handler 实现)")
    out_lines.append("  - 源 4: 业务调用链 (从 handler 实现上溯到业务入口)")

    for evt, evt_type, severity, note in events:
        out_lines.append(f"\n=== [{evt_type}] {evt} ({severity}) | {note} ===")

        pub_total = 0
        sub_total = 0
        pub_prod = []
        sub_prod = []

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
                    pubs, subs = find_event(full, evt)
                    for i, s in pubs:
                        pub_total += 1
                        if not rel.startswith("tests"):
                            pub_prod.append((rel, i, s))
                    for i, s in subs:
                        sub_total += 1
                        if not rel.startswith("tests"):
                            sub_prod.append((rel, i, s))

        out_lines.append(f"  publish: total {pub_total}, prod {len(pub_prod)}")
        for f, l, s in pub_prod[:5]:
            out_lines.append(f"    - {f}:{l}")
        out_lines.append(f"  subscribe: total {sub_total}, prod {len(sub_prod)}")
        for f, l, s in sub_prod[:5]:
            out_lines.append(f"    - {f}:{l}")
        if len(pub_prod) > 5:
            out_lines.append(f"    ... +{len(pub_prod) - 5}")
        if len(sub_prod) > 5:
            out_lines.append(f"    ... +{len(sub_prod) - 5}")

    output = "\n".join(out_lines)
    with open(PROJECT_ROOT / ".audit_r192_b_v5.txt", "w", encoding="utf-8") as f:
        f.write(output)
    # 同时输出
    print(output, flush=True)


if __name__ == "__main__":
    main()
