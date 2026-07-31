#!/usr/bin/env python3
"""
HVD-173-D-4 严格扫描器 v2 - 只检查 except 块内 logger 缺 exc_info=True
使用正确的 AST 递归处理 ExceptHandler
"""
import ast
from pathlib import Path
from typing import Tuple, List, Dict, Set

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

TOP_20_BUSINESS_CRITICAL = [
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


def is_logger_r51_call(node: ast.Call) -> Tuple[bool, str]:
    """检查是否为 logger.warning/error/critical/exception 调用"""
    if not isinstance(node, ast.Call):
        return False, ""
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False, ""
    if not isinstance(func.value, ast.Name):
        return False, ""
    if func.value.id != "logger":
        return False, ""
    if func.attr not in R51_LEVELS:
        return False, ""
    return True, func.attr


def has_exc_info_true(node: ast.Call) -> bool:
    """检查 logger 调用是否带 exc_info=True 关键字参数"""
    for kw in node.keywords:
        if kw.arg == "exc_info":
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
            if isinstance(kw.value, ast.NameConstant) and kw.value.value is True:
                return True
    return False


def collect_except_logger_violations(tree: ast.Module) -> Tuple[int, int, List[Dict]]:
    """
    收集所有 except 块内 logger.warning/error 调用
    通过遍历 ast.ExceptHandler 节点 (确保只在 except 块内)
    """
    total = 0
    missing = 0
    violations = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        # 遍历 ExceptHandler.body
        for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
            if not isinstance(child, ast.Call):
                continue
            is_r51, level = is_logger_r51_call(child)
            if not is_r51:
                continue
            total += 1
            if not has_exc_info_true(child):
                missing += 1
                msg_preview = ast.unparse(child.args[0])[:60] if child.args else "(no msg)"
                violations.append({
                    "line": child.lineno,
                    "level": level,
                    "msg": msg_preview,
                })
    return total, missing, violations


def main():
    print("=" * 80)
    print("HVD-173-D-4 v2: Top 20 except 块内 R51 #5 必修扫描")
    print("=" * 80)
    print()

    grand_total = 0
    grand_missing = 0
    all_results = []

    for rel_path in TOP_20_BUSINESS_CRITICAL:
        file_path = PROJECT_ROOT / rel_path
        if not file_path.exists():
            continue

        try:
            source = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            continue

        total, missing, violations = collect_except_logger_violations(tree)
        coverage = ((total - missing) / total * 100) if total > 0 else 100.0
        status = "[OK]" if missing == 0 else "[WARN]" if missing < 5 else "[FAIL]"

        all_results.append({
            "file": rel_path,
            "total": total,
            "missing": missing,
            "violations": violations
        })
        grand_total += total
        grand_missing += missing

        print(f"{status} {rel_path}")
        print(f"   except 块内 logger 总数: {total}")
        print(f"   缺 exc_info=True: {missing}")
        print(f"   合规率: {coverage:.1f}%")

    print()
    print("=" * 80)
    coverage = ((grand_total - grand_missing) / grand_total * 100) if grand_total > 0 else 100.0
    print(f"扫描文件数: {len(TOP_20_BUSINESS_CRITICAL)}")
    print(f"except 块内 logger 总数: {grand_total}")
    print(f"缺 exc_info=True: {grand_missing}")
    print(f"总合规率: {coverage:.1f}%")
    print("=" * 80)

    if all_results:
        print()
        print("违规详情 (按文件):")
        for r in all_results:
            if r["missing"] > 0:
                print(f"\n{r['file']} ({r['missing']} 处):")
                for v in r["violations"][:15]:
                    print(f"  L{v['line']:5d}  logger.{v['level']:10s} {v['msg']}")
                if len(r["violations"]) > 15:
                    print(f"  ... (还有 {len(r['violations']) - 15} 处)")


if __name__ == "__main__":
    main()
