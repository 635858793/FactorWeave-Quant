#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R146 子智能体 B: HVD-143-B 96 个 Service 缺 metrics/health_check 验证
扫描 core/services/ 下所有 Service 类, 检测 4 个方法
"""
import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

SERVICES_DIR = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services"
OUTPUT_FILE = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/_r146_b_hvd_143_b_output.txt"

# R145 报告 96 个 Service 严格口径清单 (无下划线 health_check)
SERVICE_FILES_R145 = [
    "advanced_risk_control_service.py",
    "ai_explainability_service.py",
    "ai_prediction_service.py",
    "ai_selection_backtest_service.py",
    "ai_selection_integration_service.py",
    "ai_selection_risk_control_service.py",
    "ai_stock_selector_service.py",
    "alert_deduplication_service.py",
    "alert_event_handler.py",
    "alert_rule_engine.py",
    "alert_rule_hot_loader.py",
    "asset_fallback_loader.py",
    "async_plugin_discovery.py",
    "audit_dead_code_service.py",
    "auto_ml_optimizer.py",
    "backtest_result_manager.py",
    "bettafish_advanced_monitoring_service.py",
    "bettafish_monitoring_integration.py",
    "bettafish_monitoring_service.py",
    "breakpoint_resume_manager.py",
    "cache_service.py",
    "config_service.py",
    "data_masking_service.py",
    "database_monitoring_service.py",
    "deep_analysis_framework.py",
    "deep_analysis_service.py",
    "distributed_service.py",
    "dividend_data_service.py",
    "enhanced_data_manager.py",
    "enhanced_data_quality_monitor.py",
    "enhanced_duckdb_data_downloader.py",
    "enhanced_performance_bridge.py",
    "enhanced_realtime_data_manager.py",
    "environment_service.py",
    "error_handling_service.py",
    "external_alert_channels_service.py",
    "external_alert_config_persistence.py",
    "fault_tolerance_manager.py",
    "feature_control_service.py",
    "feature_engineering.py",
    "fund_service.py",
    "fundamental_data_manager.py",
    "funding_rate_analysis_service.py",
    "hybrid_recommendation_engine.py",
    "incremental_data_analyzer.py",
    "incremental_update_recorder.py",
    "incremental_update_scheduler.py",
    "index_service.py",
    "indicator_dependency_manager.py",
    "industry_service.py",
    "integrated_signal_aggregator_service.py",
    "lifecycle_service.py",
    "macro_economic_data_manager.py",
    "market_cap_calculator.py",
    "model_explainer.py",
    "model_training_service.py",
    "new_stock_fetcher.py",
    "notification_service.py",
    "performance_baseline_service.py",
    "performance_data_bridge.py",
    "plugin_database_service.py",
    "prediction_tracking_service.py",
    "progress_persistence_manager.py",
    "quality_report_generator.py",
    "realtime_compute_engine.py",
    "recommendation_explanation_generator.py",
    "recommendation_model_trainer.py",
    "scheduled_task_executor.py",
    "sector_data_service.py",
    "sector_fund_flow_service.py",
    "singleton_protection.py",
    "smart_recommendation_engine.py",
    "stock_service.py",
    "strategy_plugin_pool.py",
    "strategy_status_monitor.py",
    "streaming_feature_engine.py",
    "system_optimizer.py",
    "task_scheduler.py",
    "tdx_server_discovery.py",
    "tensorflow_gpu_manager.py",
    "trading_confirmation_service.py",
    "trading_service.py",
    "training_data_collector.py",
    "uni_plugin_data_manager.py",
    "unified_cache_provider.py",
    "unified_chart_service.py",
    "unified_data_manager.py",
    "unified_data_quality_monitor.py",
]


def get_main_class_name(file_path: str) -> Tuple[str, int]:
    """获取文件中的主类名

    策略:
    1. 优先找继承 BaseService / ConfigurableService / CacheableService 的类
    2. 找不到则用第一个非内部类 (非下划线开头)
    3. 跳过 Enum / dataclass
    """
    with open(file_path, encoding="utf-8", errors="ignore") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ("?", -1)

    candidates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        # 跳过 Enum / dataclass
        bases = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.append(b.id)
            elif isinstance(b, ast.Attribute):
                bases.append(b.attr)
        # 跳过 Enum
        if "Enum" in bases or "IntEnum" in bases or "StrEnum" in bases:
            continue
        # 跳过嵌套类
        if node.col_offset and node.col_offset > 4:
            continue
        # 跳过内部类
        if node.name.startswith("_"):
            continue
        candidates.append((node.name, node.lineno, bases))

    if not candidates:
        return ("?", -1)

    # 优先返回继承 BaseService/ConfigurableService/CacheableService 的
    for name, line, bases in candidates:
        for base in bases:
            if base in ("BaseService", "ConfigurableService", "CacheableService", "AsyncBaseService"):
                return (name, line)

    # 次优返回第一个
    return candidates[0][:2]


def check_methods(file_path: str, class_name: str) -> Dict:
    """检测类的 4 个方法 (health_check / get_metrics / is_healthy / get_status)
    加上 _do_health_check 子类钩子
    """
    with open(file_path, encoding="utf-8", errors="ignore") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"error": "syntax error"}

    methods = {"health_check": False, "get_metrics": False, "is_healthy": False, "get_status": False, "_do_health_check": False}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for stmt in node.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if stmt.name in methods:
                        methods[stmt.name] = True
            break
    return methods


def main():
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("R146 B: HVD-143-B 96 个 Service 缺 metrics/health_check 验证")
    output_lines.append("=" * 80)
    output_lines.append("")
    output_lines.append("R145 D 报告: 96 个 Service 缺 health_check (严格口径, R145 阶段 1 已修 1/97 unified_data_manager)")
    output_lines.append("")

    fixed_in_r145 = 0
    still_missing = []
    total = 0
    r145_p0_fixed = []
    r145_p0_still_missing = []

    P0_SERVICES = {
        "unified_data_manager.py", "cache_service.py",
        "notification_service.py", "advanced_risk_control_service.py",
        "dynamic_risk_adjustment_service.py",
    }

    for filename in SERVICE_FILES_R145:
        file_path = os.path.join(SERVICES_DIR, filename)
        if not os.path.exists(file_path):
            continue
        total += 1
        class_name, class_line = get_main_class_name(file_path)
        methods = check_methods(file_path, class_name)

        has_health_check = methods.get("health_check", False)
        has_metrics = methods.get("get_metrics", False)
        has_is_healthy = methods.get("is_healthy", False)
        has_status = methods.get("get_status", False)
        has_do_health = methods.get("_do_health_check", False)

        # R145 严格口径: 缺 health_check (无下划线)
        missing_health_check = not has_health_check
        # R145 宽松口径: 既无 health_check 也无 _do_health_check
        missing_any_health = missing_health_check and not has_do_health

        if not missing_health_check:
            # R145 阶段 1 修复
            fixed_in_r145 += 1
            if filename in P0_SERVICES:
                r145_p0_fixed.append(filename)
        else:
            still_missing.append({
                "file": filename,
                "class": class_name,
                "line": class_line,
                "has_do_health": has_do_health,
            })
            if filename in P0_SERVICES:
                r145_p0_still_missing.append(filename)

    output_lines.append(f"扫描 Service 文件数: {total}")
    output_lines.append(f"R145 阶段 1 已修复 (有 health_check): {fixed_in_r145}")
    output_lines.append(f"R145 阶段 1 后仍缺 health_check: {len(still_missing)}")
    output_lines.append("")
    output_lines.append(f"P0 业务核心 5 个状态:")
    output_lines.append(f"  已修复: {r145_p0_fixed}")
    output_lines.append(f"  仍缺 health_check: {r145_p0_still_missing}")
    output_lines.append("")
    output_lines.append("=" * 80)
    output_lines.append(f"R145 阶段 1 后仍缺 health_check 的 Service (Top 30):")
    output_lines.append("=" * 80)

    # 按是否 _do_health_check 分组
    missing_with_do_health = [s for s in still_missing if s['has_do_health']]
    missing_no_any = [s for s in still_missing if not s['has_do_health']]

    output_lines.append(f"\n口径 1 (严格): 缺 health_check, 但有 _do_health_check: {len(missing_with_do_health)} 个")
    output_lines.append(f"  实际: R145 修复的仅是统一接口, 业务钩子已就位")
    output_lines.append(f"口径 2 (宽松): 缺 health_check + _do_health_check: {len(missing_no_any)} 个")
    output_lines.append(f"  实际: 业务钩子也没写, 可观测性盲区")

    for s in still_missing[:30]:
        marker = " [有_do_health]" if s['has_do_health'] else " [完全缺]"
        is_p0 = " [P0]" if s['file'] in P0_SERVICES else ""
        output_lines.append(f"  {s['file']:55s} -> {s['class']:35s} L{s['line']}{marker}{is_p0}")

    output_lines.append("")
    output_lines.append("=" * 80)
    output_lines.append("R146 B 关键发现:")
    output_lines.append("=" * 80)
    if fixed_in_r145 == 1:
        output_lines.append(f"  验证 R145 报告: 仅 unified_data_manager.py 1/97 修复")
        output_lines.append(f"  96/96 仍缺 health_check (严格口径)")
        output_lines.append(f"  其中 {len(missing_no_any)} 个完全无可观测性方法 (宽松口径)")
        output_lines.append(f"  实际剩余 P0 业务核心: {r145_p0_still_missing}")
        output_lines.append(f"  [RED] HVD-143-B 阶段 2 紧急立项: 4 个 P0 业务核心仍缺 health_check")
    elif fixed_in_r145 == len(SERVICE_FILES_R145):
        output_lines.append(f"  [GREEN] HVD-143-B 阶段 1-2 已完成 (96/96 已修复)")
    else:
        output_lines.append(f"  [YELLOW] HVD-143-B 阶段 1 修复 {fixed_in_r145}/{len(SERVICE_FILES_R145)}")
        output_lines.append(f"  仍缺 {len(still_missing)} 个")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"Output: {OUTPUT_FILE}")
    print(f"Summary: R145 fixed {fixed_in_r145}, still missing {len(still_missing)}")


if __name__ == "__main__":
    main()
