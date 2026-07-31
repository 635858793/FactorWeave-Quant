"""
R196-A 字符串事件扫描器: 扫描全项目 publish('...') 调用,识别 EventType 缺失
R196-A 工具脚本: HVD-195-C-2 实施辅助

参照 R195-C 报告的 49 字符串事件,继续扩大扫描范围。
"""
import ast
import os
import json
from pathlib import Path
from typing import List, Dict, Set, Tuple

# 已知 EventType 枚举值(从 core/events/types.py 提取,避免重复)
KNOWN_EVENT_TYPES = {
    # 图表
    "chart_created", "chart_updated", "chart_data_updated", "chart_removed", "chart_resized",
    # 数据
    "data_loaded", "data_updated", "data_error", "real_time_data",
    "realtime_components_unavailable", "realtime_components_restored",
    # 性能
    "performance_optimized", "performance_degraded", "performance_metrics_updated", "optimization_metrics_updated",
    # UI
    "ui_update", "theme_changed", "asset_selected", "asset_type_changed",
    # 交易
    "trade_executed", "order_placed", "order_filled", "position_updated",
    "order.validation_failed", "order.risk_check_failed", "order.position_limit_failed", "order.confirmed",
    "order_cancelled", "order_cancel_failed", "order_cancel_requested", "order_partially_filled",
    "order_terminal_state", "batch_orders_created", "batch_orders_cancelled",
    "batch_orders_submitted_success", "batch_orders_submitted_failed",
    # 性能/告警
    "performance_alert",
    # AI/ML
    "model_trained", "prediction_made", "accuracy_updated", "ai_selection",
    # 指标
    "indicator_updated", "indicator_computed",
    # 系统
    "system_error", "system_warning", "system_info",
    # 策略
    "strategy_started", "strategy_stopped", "strategy_paused", "strategy_resumed", "strategy_error",
    "signal_generated", "performance_updated",
    # 回测
    "backtest_progress", "backtest_completed",
    # 基线
    "baseline_drift_alert",
    # 账户
    "account_switched",
    # R174
    "free_stockdb.connected", "free_stockdb.disconnected", "free_stockdb.health.changed", "free_stockdb.error",
    "bettafish.sentiment.analysis.completed",
    # R192-C-3
    "cash_frozen", "cash_unfrozen", "reconcile_health_alert", "fund_info_saved", "xtp_error",
    # R193-C-D-001
    "order_save_retry", "order_save_failed_need_unfreeze", "all_active_orders_cancelled",
}

# 业务 publish 调用方法名
PUBLISH_METHODS = {"publish", "publish_async", "_publish", "_publish_internal", "_emit", "emit"}


def find_string_event_publishes(file_path: Path) -> List[Dict]:
    """扫描文件,找出所有 bus.publish('event_name', ...) 字符串字面量调用"""
    results = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return results

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # 检查是否是 publish 调用
        func_name = None
        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id
        if func_name not in PUBLISH_METHODS:
            continue
        # 检查第一个参数是否是字符串字面量
        if not node.args:
            continue
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            event_name = first_arg.value
            results.append({
                "file": str(file_path),
                "line": node.lineno,
                "event_name": event_name,
                "publish_method": func_name,
            })
    return results


def main():
    """主函数:扫描全项目所有 .py 文件"""
    project_root = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")
    # 跳过测试、虚拟环境、构建目录
    skip_patterns = {"test_", "__pycache__", ".git", "venv", "node_modules", "dist", "build", ".trae"}

    all_publishes = []
    py_files = []
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if not any(p in d for p in skip_patterns)]
        for f in files:
            if f.endswith(".py") and not f.startswith("test_"):
                py_files.append(Path(root) / f)

    for py_file in py_files:
        publishes = find_string_event_publishes(py_file)
        all_publishes.extend(publishes)

    # 找出 EventType 缺失的事件
    missing = {}
    for pub in all_publishes:
        evt = pub["event_name"]
        if evt in KNOWN_EVENT_TYPES:
            continue
        if evt not in missing:
            missing[evt] = []
        missing[evt].append(pub)

    # 输出结果
    output = {
        "total_publishes": len(all_publishes),
        "unique_events": len(set(p["event_name"] for p in all_publishes)),
        "missing_event_types": len(missing),
        "missing_list": [
            {
                "event_name": evt,
                "publish_count": len(pubs),
                "locations": [
                    {"file": p["file"], "line": p["line"]} for p in pubs[:5]
                ]
            }
            for evt, pubs in sorted(missing.items(), key=lambda x: -len(x[1]))
        ]
    }

    out_file = project_root / "tools" / "_r196_a_event_type_scan.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"扫描完成: {len(py_files)} 个 Python 文件")
    print(f"总 publish 调用: {len(all_publishes)}")
    print(f"唯一事件名: {len(set(p['event_name'] for p in all_publishes))}")
    print(f"缺失 EventType 枚举: {len(missing)}")
    print(f"结果写入: {out_file}")
    print()
    print("Top 30 缺失事件 (按 publish 数量降序):")
    for i, item in enumerate(output["missing_list"][:30], 1):
        print(f"  {i:2}. {item['event_name']:50s} -> {item['publish_count']} 处 publish")


if __name__ == "__main__":
    main()
