"""R163-C: 业务调用方 Grep 验证 (替代 CodeGraph, 因后者不可用)"""
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# 关键 P0 文件
P0_TARGETS = {
    "core/agents/risk_agent.py": ["risk_agent", "RiskAgent"],
    "core/performance/professional_risk_metrics.py": ["professional_risk_metrics", "ProfessionalRiskMetrics"],
    "core/risk/risk_event_subscribers.py": ["risk_event_subscribers", "RiskEventSubscribers"],
    "core/risk_alert.py": ["risk_alert", "RiskAlert"],
    "core/risk_control.py": ["risk_control", "RiskControl"],
    "core/risk_exporter.py": ["risk_exporter", "RiskExporter"],
    "core/risk_manager.py": ["risk_manager", "RiskManager"],
    "core/risk_monitoring/enhanced_risk_monitor.py": ["enhanced_risk_monitor", "EnhancedRiskMonitor"],
    "core/stop_loss.py": ["stop_loss", "StopLoss"],
    "core/take_profit.py": ["take_profit", "TakeProfit"],
    "core/money_manager.py": ["money_manager", "MoneyManager"],
    "core/trading_engine.py": ["trading_engine", "TradingEngine"],
    "gui/dialogs/order_management_dialog.py": ["OrderManagementDialog", "order_management_dialog"],
    "gui/widgets/performance/tabs/risk_control_center_tab.py": ["RiskControlCenterTab", "risk_control_center_tab"],
    "gui/widgets/trading_widget.py": ["TradingWidget", "trading_widget"],
    "gui/dialogs/account_management_dialog.py": ["AccountManagementDialog", "account_management_dialog"],
    "gui/widgets/trading_panel.py": ["TradingPanel", "trading_panel"],
}

# 扫描
results = {}
for target_file, keywords in P0_TARGETS.items():
    callers = set()
    for py_file in PROJECT_ROOT.rglob("*.py"):
        if "__pycache__" in str(py_file) or ".git" in str(py_file):
            continue
        # 跳过自身
        try:
            rel = py_file.relative_to(PROJECT_ROOT)
            if str(rel).replace("\\", "/") == target_file:
                continue
        except ValueError:
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for kw in keywords:
            # 找 import / from ... import
            if re.search(rf'\b(from\s+[\w.]*{kw}\s+import|import\s+[\w.]*{kw})', content):
                callers.add(str(rel).replace("\\", "/"))
                break
            # 找直接调用 (类名 + .)
            if re.search(rf'\b{kw}\s*\(', content) or re.search(rf'\b{kw}\.', content):
                # 排除注释
                if not re.search(rf'#.*\b{kw}\b', content):
                    callers.add(str(rel).replace("\\", "/"))
                    break

    results[target_file] = sorted(callers)

# 输出
out = []
out.append("=" * 70)
out.append("R163-C: P0 业务核心文件业务调用方验证 (Grep 跨 4 子目录)")
out.append("=" * 70)

total_callers = 0
for target, callers in sorted(results.items(), key=lambda x: -len(x[1])):
    out.append(f"\n## {target} ({len(callers)} 业务调用方)")
    if not callers:
        out.append("  (无业务调用方)")
    for c in callers[:10]:
        out.append(f"  {c}")
    if len(callers) > 10:
        out.append(f"  ... + {len(callers) - 10} more")
    total_callers += len(callers)

out.append(f"\n{'='*70}")
out.append(f"汇总: P0 业务核心 {len(P0_TARGETS)} 文件, 总业务调用方 {total_callers}")
out.append(f"     平均每个 P0 文件 {total_callers / len(P0_TARGETS):.1f} 业务调用方")
out.append(f"     P0 业务核心度评级: {'🔴 P0 业务核心' if total_callers > 100 else '🟡 P0'}")

with open(PROJECT_ROOT / "tools" / "_r163_c_p0_callers.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))

print(f"P0 callers analysis written")
print(f"Total callers: {total_callers}")
