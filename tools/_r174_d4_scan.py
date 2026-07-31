#!/usr/bin/env python3
"""
HVD-173-D-4 扫描器 - Top 20 业务关键文件 R51 #5 必修
扫描范围: core/services + trading + coordinators + agents
扫描目标: logger.warning/error 调用缺 exc_info=True (R51 #5 违规)
使用方式: python tools/_r174_d4_scan.py
"""
import ast
import os
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

# Top 20 业务关键文件 (按业务重要性排序, 路径 R174-D-4 物理确认)
TOP_20_BUSINESS_CRITICAL = [
    # core/trading/ (业务核心, 4/20)
    "core/trading/order_service.py",
    "core/trading/order_executor.py",
    "core/trading/account_manager.py",
    "core/trading/order_monitor.py",
    # core/ 根目录 (业务核心, 2/20)
    "core/trading_engine.py",
    "core/trading_controller.py",
    "core/risk_manager.py",
    # core/risk_monitoring/ (风控核心, 1/20)
    "core/risk_monitoring/enhanced_risk_monitor.py",
    # core/services/ (服务层, 5/20)
    "core/services/unified_data_manager.py",
    "core/services/cache_service.py",
    "core/services/advanced_risk_control_service.py",
    "core/services/dynamic_risk_adjustment_service.py",
    "core/services/ai_selection_integration_service.py",
    # core/agents/ (AI 核心, 3/20)
    "core/agents/bettafish_agent.py",
    "core/agents/risk_agent.py",
    "core/agents/sentiment_agent.py",
    # core/events/ (事件核心, 1/20)
    "core/events/event_bus.py",
    # core/coordinators/ (协调器, 1/20)
    "core/coordinators/main_window_coordinator.py",
    # core/risk/ (1/20)
    "core/risk/risk_event_subscribers.py",
    "core/risk/compliance_audit_logger.py",
]


def analyze_logger_calls(file_path: Path) -> Tuple[int, int, List[Dict]]:
    """
    分析 Python 文件中的 logger 调用
    返回: (logger.warning/error 总数, 缺 exc_info=True 数, 违规列表)
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError) as e:
        return 0, 0, []

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return 0, 0, []

    total = 0
    missing_exc_info = 0
    violations = []

    # 关注的 logger 等级
    R51_LEVELS = ("warning", "error", "critical", "exception")

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # 检查是否为 logger.warning/error() 调用
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if not isinstance(func.value, ast.Name):
            continue
        if func.value.id != "logger":
            continue
        if func.attr not in R51_LEVELS:
            continue

        total += 1

        # 检查 exc_info 关键字参数
        has_exc_info = False
        for kw in node.keywords:
            if kw.arg == "exc_info":
                if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    has_exc_info = True
                elif isinstance(kw.value, ast.NameConstant) and kw.value.value is True:
                    has_exc_info = True

        if not has_exc_info:
            missing_exc_info += 1
            violations.append({
                "file": str(file_path.relative_to(PROJECT_ROOT)),
                "line": node.lineno,
                "col": node.col_offset,
                "level": func.attr,
                "msg_preview": ast.unparse(node.args[0])[:80] if node.args else "(no msg)"
            })

    return total, missing_exc_info, violations


def main():
    print("=" * 80)
    print("HVD-173-D-4: Top 20 业务关键文件 R51 #5 必修扫描 (R174-D-4 物理路径版)")
    print("=" * 80)
    print()

    grand_total = 0
    grand_missing = 0
    grand_violations = 0
    all_results = []

    for rel_path in TOP_20_BUSINESS_CRITICAL:
        file_path = PROJECT_ROOT / rel_path
        if not file_path.exists():
            print(f"⚠️  {rel_path}: 文件不存在")
            continue

        total, missing, violations = analyze_logger_calls(file_path)
        coverage = ((total - missing) / total * 100) if total > 0 else 100.0

        status = "✅" if missing == 0 else "⚠️" if missing < 5 else "🔴"
        print(f"{status} {rel_path}")
        print(f"   logger.warning/error 总数: {total}")
        print(f"   缺 exc_info=True: {missing}")
        print(f"   合规率: {coverage:.1f}%")

        grand_total += total
        grand_missing += missing
        grand_violations += len(violations)
        all_results.append({
            "file": rel_path,
            "total": total,
            "missing": missing,
            "violations": violations
        })

    print()
    print("=" * 80)
    print("汇总")
    print("=" * 80)
    print(f"扫描文件数: {len(TOP_20_BUSINESS_CRITICAL)}")
    print(f"logger.warning/error 总数: {grand_total}")
    print(f"缺 exc_info=True: {grand_missing}")
    print(f"违规行数: {grand_violations}")
    coverage = ((grand_total - grand_missing) / grand_total * 100) if grand_total > 0 else 100.0
    print(f"总合规率: {coverage:.1f}%")

    # 输出违规详情
    if all_results:
        print()
        print("=" * 80)
        print("违规详情 (按文件)")
        print("=" * 80)
        for result in all_results:
            if result["missing"] > 0:
                print(f"\n{result['file']} ({result['missing']} 处):")
                for v in result["violations"][:10]:  # 只显示前 10 处
                    print(f"  L{v['line']:5d}  logger.{v['level']:10s} {v['msg_preview']}")
                if len(result["violations"]) > 10:
                    print(f"  ... (还有 {len(result['violations']) - 10} 处)")


if __name__ == "__main__":
    main()
