"""
R163-C: 全项目 logger.exc_info 缺失扫描 (4 子目录: core/gui/web/tests)

基于 R162 扫描器, 扩展到全项目范围:
- 跨 4 子目录: core/ + gui/ + web/ + tests/
- AST 精确解析 except 块内 logger 调用
- 区分 P0 业务核心 / P1 重要业务 / P2 监控 / P3 工具
- 排除 R162 HVD-161-B 已升级位置

排除列表 (R145/R161/R162 已修复):
- core/importdata/import_execution_engine.py (R162 已升级 9 处)
- core/trading_engine.py (R145 已升级 14 处)
- core/order_service.py (R161+R145 升级 135+ 处)
- core/services/advanced_risk_control_service.py (R162 已升级)
- core/ctp/ctp_trading_interface.py (R163-A 闭环)
- core/risk_manager.py (R148 升级)
- 4 trading_interfaces (R163-A 闭环)
- core/asset_database_manager.py (R148-P0-A 34 处)

输出: 按文件分组 + 按优先级分类的 JSON 报告
"""
import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# 4 个扫描子目录
SCAN_DIRS = ["core", "gui", "web", "tests"]

# R145/R161/R162/R163-A 已修复/闭环文件 (排除)
ALREADY_FIXED = {
    # R163-A 闭环 (4 trading_interfaces)
    "core/trading/interfaces/ctp_trading_interface.py",
    "core/trading/interfaces/xtp_trading_interface.py",
    "core/trading/interfaces/xtp_pro_trading_interface.py",
    "core/trading/interfaces/miniqmt_trading_interface.py",
    # R162 HVD-161-B 闭环
    "core/services/dynamic_risk_adjustment_service.py",
    "core/services/advanced_risk_control_service.py",
    "core/services/trading_service.py",
    "core/services/trading_confirmation_service.py",
    "core/feedback/feedback_service.py",
    "core/stop_loss.py",
    "core/take_profit.py",
    "core/money_manager.py",
    "core/trading_controller.py",
    "core/trading/order_service.py",
    "core/trading/order_validator.py",
    "core/trading/order_monitor.py",
    "core/trading/order_event_handlers.py",
    "core/trading/order_analyzer.py",
    "core/trading/order_repository.py",
    "core/trading/account_repository.py",
    "core/trading/_event_helpers/account_position_helper.py",
    # R148 升级
    "core/asset_database_manager.py",
    # R145/R162 升级
    "core/importdata/import_execution_engine.py",
}

# P0 业务核心关键词
P0_KEYWORDS = [
    "trading", "order", "risk", "position", "account",
    "trade", "money", "stop_loss", "take_profit",
    "ctp", "xtp", "miniqmt",
]

# P1 重要业务关键词
P1_KEYWORDS = [
    "service", "repository", "manager", "engine",
    "controller", "validator", "monitor", "analyzer",
    "event", "cache", "data", "import", "export",
    "config", "session", "factory", "bridge",
]

# P3 工具/脚本关键词
P3_KEYWORDS = [
    "test_", "tests/", "tools/", "scripts/",
    "debug", "util", "helper", "fix_",
]


def classify_file_priority(file_path: str) -> str:
    """P0=业务核心, P1=重要业务, P2=次要, P3=工具/脚本"""
    rel = file_path.replace("\\", "/")
    file_lower = rel.lower()

    # P3 工具/脚本
    for kw in P3_KEYWORDS:
        if kw in file_lower:
            return "P3"

    # P0 业务核心
    for kw in P0_KEYWORDS:
        if kw in file_lower:
            # 排除 test_ 优先
            if "test_" in file_lower or "/tests/" in file_lower:
                return "P3"
            return "P0"

    # P1 重要业务
    for kw in P1_KEYWORDS:
        if kw in file_lower:
            return "P1"

    return "P2"


def is_optional_dep_import_error(node: ast.ExceptHandler) -> bool:
    """检测 optional-dep ImportError (R85 反例: 合法降级路径)"""
    if not node.type:
        return False
    type_str = ast.unparse(node.type) if node.type else ""
    return "ImportError" in type_str


def has_exc_info_kwarg(call: ast.Call) -> bool:
    """检查 logger 调用是否含 exc_info=True kwarg"""
    for kw in call.keywords:
        if kw.arg == "exc_info":
            if isinstance(kw.value, ast.Constant):
                return True
    return False


def is_logger_call(node: ast.Call) -> bool:
    """检查是否为 logger.X() 调用"""
    if isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name) and node.func.value.id in ("logger", "_logger", "log"):
            return True
    return False


def is_logger_exception(call: ast.Call) -> bool:
    """检查 logger.exception()"""
    if isinstance(call.func, ast.Attribute):
        return call.func.attr == "exception"
    return False


def scan_except_blocks(tree: ast.Module) -> List[Dict]:
    """
    扫描所有 except 块, 找出缺 exc_info 的位置
    R104 §12 铁律 #3: 必须递归进入 try.body/with.body (R104 TDD 教训)
    """
    violations = []

    def visit_except(handler: ast.ExceptHandler, parent_try: ast.Try):
        """访问 except 块, 收集 logger 调用"""
        except_type = ast.unparse(handler.type) if handler.type else "Exception"
        is_optional = is_optional_dep_import_error(handler)

        logger_calls = []
        missing = True

        for stmt in handler.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                if is_logger_call(call):
                    method = call.func.attr
                    has_ei = is_logger_exception(call) or has_exc_info_kwarg(call)
                    logger_calls.append({
                        "line": stmt.lineno,
                        "method": method,
                        "has_exc_info": has_ei,
                        "is_exception": is_logger_exception(call),
                    })
                    if has_ei:
                        missing = False

        if logger_calls and missing and not is_optional:
            violations.append({
                "line": handler.lineno,
                "except_type": except_type,
                "is_optional_import": is_optional,
                "logger_calls": logger_calls,
            })

    def visit_try(try_node: ast.Try):
        """递归访问 try 块 (含嵌套)"""
        for handler in try_node.handlers:
            visit_except(handler, try_node)
            # 递归: 嵌套 try 块
            for stmt in handler.body:
                if isinstance(stmt, ast.Try):
                    visit_try(stmt)
        for stmt in try_node.body:
            if isinstance(stmt, ast.Try):
                visit_try(stmt)

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            visit_try(node)

    return violations


def scan_file(file_path: Path) -> Dict:
    """扫描单个文件"""
    try:
        src = file_path.read_text(encoding="utf-8")
        tree = ast.parse(src)
    except (SyntaxError, UnicodeDecodeError):
        return {"file": str(file_path), "error": "parse_error", "violations": []}

    violations = scan_except_blocks(tree)
    rel = str(file_path.relative_to(PROJECT_ROOT))
    return {
        "file": rel,
        "priority": classify_file_priority(rel),
        "violations": violations,
    }


def main():
    print(f"=" * 70)
    print(f"R163-C: 全项目 logger.exc_info 缺失扫描 (4 子目录: {', '.join(SCAN_DIRS)})")
    print(f"=" * 70)

    all_files = []
    for scan_dir in SCAN_DIRS:
        scan_path = PROJECT_ROOT / scan_dir
        if not scan_path.exists():
            continue
        for py_file in scan_path.rglob("*.py"):
            rel = str(py_file.relative_to(PROJECT_ROOT)).replace("\\", "/")
            if rel in ALREADY_FIXED:
                continue
            all_files.append(py_file)

    print(f"扫描文件数: {len(all_files)} (已排除 {len(ALREADY_FIXED)} 个 R145/R161/R162/R163-A 闭环文件)")
    print(f"开始扫描...")

    results = {
        "P0": [],
        "P1": [],
        "P2": [],
        "P3": [],
    }
    total_except = 0
    total_missing = 0

    for i, py_file in enumerate(all_files):
        result = scan_file(py_file)
        if result.get("error"):
            continue
        violations = result["violations"]
        if violations:
            results[result["priority"]].append(result)
            for v in violations:
                total_except += 1
                if v.get("is_optional_import"):
                    continue
                # missing 含义: 所有 logger_calls 都没 exc_info
                if v["logger_calls"]:
                    total_missing += 1

        if (i + 1) % 50 == 0:
            print(f"  进度: {i+1}/{len(all_files)}")

    print()
    print(f"=" * 70)
    print(f"扫描结果汇总")
    print(f"=" * 70)

    summary = {}
    for p in ["P0", "P1", "P2", "P3"]:
        files = results[p]
        total_v = sum(len(f["violations"]) for f in files)
        missing_v = sum(
            1 for f in files for v in f["violations"]
            if not v.get("is_optional_import") and v["logger_calls"]
        )
        optional_v = sum(
            1 for f in files for v in f["violations"]
            if v.get("is_optional_import")
        )
        summary[p] = {
            "files": len(files),
            "total_violations": total_v,
            "missing_exc_info": missing_v,
            "optional_import": optional_v,
        }
        print(f"  {p}: {len(files)} 文件, {total_v} 处 except 缺 exc_info, "
              f"missing={missing_v}, optional-dep={optional_v}")

    print()
    print(f"总缺 exc_info: {sum(s['missing_exc_info'] for s in summary.values())}")
    print(f"  其中 optional-dep ImportError (R85 反例, 不修): "
          f"{sum(s['optional_import'] for s in summary.values())}")
    print(f"  真修复目标 (业务核心): "
          f"{sum(s['missing_exc_info'] for s in summary.values()) - sum(s['optional_import'] for s in summary.values())}")

    # 输出 P0 详细列表
    print()
    print(f"=" * 70)
    print(f"P0 业务核心缺失清单 (按 file:line 排序)")
    print(f"=" * 70)
    p0_list = []
    for f in results["P0"]:
        for v in f["violations"]:
            if v.get("is_optional_import"):
                continue
            if v["logger_calls"]:
                for lc in v["logger_calls"]:
                    p0_list.append({
                        "file": f["file"],
                        "except_line": v["line"],
                        "except_type": v["except_type"],
                        "logger_line": lc["line"],
                        "logger_method": lc["method"],
                    })
    p0_list.sort(key=lambda x: (x["file"], x["logger_line"]))
    print(f"P0 总数: {len(p0_list)} 处")
    for item in p0_list[:50]:
        print(f"  {item['file']}:{item['logger_line']} "
              f"(except {item['except_type']} @ L{item['except_line']}, "
              f"logger.{item['logger_method']})")
    if len(p0_list) > 50:
        print(f"  ... 还有 {len(p0_list) - 50} 处")

    # 输出 P1 详细列表
    print()
    print(f"=" * 70)
    print(f"P1 重要业务缺失清单 (按 file:line 排序, 仅显示前 30)")
    print(f"=" * 70)
    p1_list = []
    for f in results["P1"]:
        for v in f["violations"]:
            if v.get("is_optional_import"):
                continue
            if v["logger_calls"]:
                for lc in v["logger_calls"]:
                    p1_list.append({
                        "file": f["file"],
                        "except_line": v["line"],
                        "except_type": v["except_type"],
                        "logger_line": lc["line"],
                        "logger_method": lc["method"],
                    })
    p1_list.sort(key=lambda x: (x["file"], x["logger_line"]))
    print(f"P1 总数: {len(p1_list)} 处")
    for item in p1_list[:30]:
        print(f"  {item['file']}:{item['logger_line']} "
              f"(except {item['except_type']} @ L{item['except_line']}, "
              f"logger.{item['logger_method']})")
    if len(p1_list) > 30:
        print(f"  ... 还有 {len(p1_list) - 30} 处")

    # 输出 P2/P3 概要
    print()
    print(f"=" * 70)
    print(f"P2 次要业务 + P3 工具脚本概要")
    print(f"=" * 70)
    for p in ["P2", "P3"]:
        files = results[p]
        if not files:
            print(f"  {p}: 无缺失")
            continue
        p_list = []
        for f in files:
            for v in f["violations"]:
                if v.get("is_optional_import"):
                    continue
                if v["logger_calls"]:
                    for lc in v["logger_calls"]:
                        p_list.append({
                            "file": f["file"],
                            "logger_line": lc["line"],
                        })
        print(f"  {p}: {len(p_list)} 处缺失, 跨 {len(files)} 文件")
        for item in p_list[:10]:
            print(f"    {item['file']}:{item['logger_line']}")
        if len(p_list) > 10:
            print(f"    ... 还有 {len(p_list) - 10} 处")

    # 输出 JSON 报告
    output_path = PROJECT_ROOT / "tools" / "_r163_c_scan_result.json"
    output = {
        "summary": summary,
        "total_missing": total_missing,
        "results_by_file": {p: results[p] for p in ["P0", "P1", "P2", "P3"]},
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nJSON 报告已写入: {output_path}")

    return results


if __name__ == "__main__":
    main()
