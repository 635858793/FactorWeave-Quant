#!/usr/bin/env python3
"""
HVD-173-D-4 全量扫描 v3 - 检查所有 logger.warning/error/exception/critical 调用
不受 except 块限制
"""
import ast
from pathlib import Path
from typing import Tuple, List, Dict

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

TOP_20_FILES = [
    "core/trading/order_service.py",
    "core/trading/order_executor.py",
    "core/trading/account_manager.py",
    "core/trading/order_monitor.py",
    "core/trading_engine.py",
    "core/trading_controller.py",
    "core/risk_manager.py",
    "core/risk_monitoring/enhanced_risk_monitor.py",
    "core/services/unified_data_manager.py",
    "core/services/cache_service.py",
    "core/services/advanced_risk_control_service.py",
    "core/services/dynamic_risk_adjustment_service.py",
    "core/services/ai_selection_integration_service.py",
    "core/agents/bettafish_agent.py",
    "core/agents/risk_agent.py",
    "core/agents/sentiment_agent.py",
    "core/events/event_bus.py",
    "core/coordinators/main_window_coordinator.py",
    "core/risk/risk_event_subscribers.py",
    "core/risk/compliance_audit_logger.py",
]

R51_LEVELS = ("warning", "error", "critical", "exception")


def is_logger_r51_call(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Attribute):
        return False
    if not isinstance(node.func.value, ast.Name):
        return False
    if node.func.value.id != "logger":
        return False
    if node.func.attr not in R51_LEVELS:
        return False
    return True


def has_exc_info_true(node: ast.Call) -> bool:
    for kw in node.keywords:
        if kw.arg == "exc_info":
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
            if isinstance(kw.value, ast.NameConstant) and kw.value.value is True:
                return True
    return False


def analyze_file(file_path: Path) -> Tuple[int, int, List[Dict]]:
    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError):
        return 0, 0, []

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return 0, 0, []

    total = 0
    missing = 0
    violations = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not is_logger_r51_call(node):
            continue
        total += 1
        if not has_exc_info_true(node):
            missing += 1
            msg_preview = ast.unparse(node.args[0])[:60] if node.args else "(no msg)"
            violations.append({
                "line": node.lineno,
                "level": node.func.attr,
                "msg": msg_preview,
            })

    return total, missing, violations


def main():
    print("=" * 80)
    print("HVD-173-D-4 v3: Top 20 全量 logger.warning/error/exception/critical 扫描")
    print("=" * 80)
    print()

    grand_total = 0
    grand_missing = 0
    all_violations = []

    for rel_path in TOP_20_FILES:
        file_path = PROJECT_ROOT / rel_path
        if not file_path.exists():
            continue

        total, missing, violations = analyze_file(file_path)
        grand_total += total
        grand_missing += missing
        coverage = ((total - missing) / total * 100) if total > 0 else 100.0
        status = "[OK]" if missing == 0 else "[WARN]" if missing < 10 else "[FAIL]"

        print(f"{status} {rel_path}")
        print(f"   全量 logger 总数: {total}, 缺 exc_info: {missing}, 合规率: {coverage:.1f}%")

        for v in violations:
            all_violations.append({"file": rel_path, **v})

    print()
    print("=" * 80)
    coverage = ((grand_total - grand_missing) / grand_total * 100) if grand_total > 0 else 100.0
    print(f"全量: 总数 {grand_total}, 缺 exc_info: {grand_missing}, 合规率: {coverage:.1f}%")
    print(f"违规详情: {len(all_violations)} 条")
    print("=" * 80)


if __name__ == "__main__":
    main()
