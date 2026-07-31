"""
R51 铁律 #5 残留扫描器
检查 logger.error/critical/exception 调用是否在 except 块内且缺少 exc_info=True
"""
import ast
import os
import sys
import json
from pathlib import Path

# 9 个关键文件
KEY_FILES = [
    "core/services/trading_service.py",
    "core/services/advanced_risk_control_service.py",
    "core/events/event_bus.py",
    "core/services/cache_service.py",
    "core/services/unified_data_manager.py",
    "core/trading/order_service.py",
    "core/trading/trading_engine.py",
    "core/risk_manager.py",
    "core/services/service_bootstrap.py",
]

# 一些已修的 trade_engine 在 core/ 而非 core/trading/
ALT_FILES = {
    "core/trading/trading_engine.py": "core/trading_engine.py",
}

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")


def resolve_file(rel_path: str) -> Path:
    """解析文件路径，处理替代路径"""
    if rel_path in ALT_FILES:
        return PROJECT_ROOT / ALT_FILES[rel_path]
    return PROJECT_ROOT / rel_path


def find_except_logger_calls(tree: ast.AST, source_lines: list) -> list:
    """
    找到所有 except 块内的 logger.error/critical/exception 调用
    检查是否缺 exc_info=True
    """
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.type is None:
                    continue
                # 处理 except 块的 body
                _scan_except_body(handler.body, handler.lineno, violations, source_lines, handler.name)

    return violations


def _scan_except_body(body, except_lineno, violations, source_lines, exc_name):
    """递归扫描 except body 内的 logger 调用"""
    for stmt in body:
        _scan_stmt(stmt, except_lineno, violations, source_lines, exc_name, depth=0)


def _scan_stmt(stmt, except_lineno, violations, source_lines, exc_name, depth):
    """递归扫描语句"""
    # AST 1.x compatibility
    if hasattr(ast, 'TryStar'):
        try_types = (ast.Try, ast.TryStar)
    else:
        try_types = (ast.Try,)

    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        call = stmt.value
        if _is_logger_error_call(call):
            has_exc_info = _has_exc_info_kwarg(call)
            if not has_exc_info:
                method_name = _get_method_name(call)
                violations.append({
                    "except_line": except_lineno,
                    "call_line": stmt.lineno,
                    "method": method_name,
                    "snippet": source_lines[stmt.lineno - 1].strip() if stmt.lineno - 1 < len(source_lines) else "",
                    "exc_name": exc_name,
                })
    elif isinstance(stmt, try_types):
        for sub_handler in stmt.handlers:
            if sub_handler.type is not None:
                _scan_except_body(sub_handler.body, sub_handler.lineno, violations, source_lines, sub_handler.name)
    elif hasattr(ast, 'If') and isinstance(stmt, ast.If):
        for s in stmt.body:
            _scan_stmt(s, except_lineno, violations, source_lines, exc_name, depth+1)
        for s in stmt.orelse:
            _scan_stmt(s, except_lineno, violations, source_lines, exc_name, depth+1)
    elif isinstance(stmt, (ast.For, ast.While)):
        for s in stmt.body:
            _scan_stmt(s, except_lineno, violations, source_lines, exc_name, depth+1)
        for s in stmt.orelse:
            _scan_stmt(s, except_lineno, violations, source_lines, exc_name, depth+1)
    elif isinstance(stmt, ast.With):
        for s in stmt.body:
            _scan_stmt(s, except_lineno, violations, source_lines, exc_name, depth+1)


def _is_logger_error_call(call: ast.Call) -> bool:
    """判断是否是 logger.error/critical 调用 (logger.exception 单独标记, 它自动含 exc_info)"""
    if not isinstance(call.func, ast.Attribute):
        return False
    # logger.exception 自动包含 exc_info=True, 不算违规
    if call.func.attr == "exception":
        return False
    if call.func.attr not in ("error", "critical"):
        return False
    return True


def _has_exc_info_kwarg(call: ast.Call) -> bool:
    """检查调用是否包含 exc_info=True 关键字参数"""
    for kw in call.keywords:
        if kw.arg == "exc_info":
            return True
    return False


def _get_method_name(call: ast.Call) -> str:
    """获取 logger.method 名称"""
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return "unknown"


def find_parent_method(tree: ast.AST, target_lineno: int) -> str:
    """找到目标行号所属的方法名"""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= target_lineno <= (node.end_lineno or target_lineno):
                return node.name
    return "<module>"


def scan_file(rel_path: str) -> dict:
    """扫描单个文件"""
    abs_path = resolve_file(rel_path)
    if not abs_path.exists():
        return {"file": rel_path, "exists": False, "violations": []}

    with open(abs_path, "r", encoding="utf-8") as f:
        source = f.read()

    source_lines = source.splitlines()
    try:
        tree = ast.parse(source, filename=str(abs_path))
    except SyntaxError as e:
        return {"file": rel_path, "exists": True, "error": str(e), "violations": []}

    violations = find_except_logger_calls(tree, source_lines)

    # 关联到方法
    for v in violations:
        v["parent_method"] = find_parent_method(tree, v["call_line"])

    return {
        "file": rel_path,
        "exists": True,
        "abs_path": str(abs_path),
        "total_lines": len(source_lines),
        "violations": violations,
    }


def main():
    results = {}
    for rel_path in KEY_FILES:
        results[rel_path] = scan_file(rel_path)

    # 输出
    total_violations = sum(len(r["violations"]) for r in results.values())
    print(f"=== R51 铁律 #5 残留扫描 ===")
    print(f"扫描文件: {len(KEY_FILES)}")
    print(f"总违规数: {total_violations}")
    print()

    # 按文件汇总
    for rel_path, r in results.items():
        if not r["exists"]:
            print(f"[SKIP] {rel_path}: 文件不存在")
            continue
        if "error" in r:
            print(f"[ERROR] {rel_path}: {r['error']}")
            continue

        violations = r["violations"]
        print(f"=== {rel_path} ===")
        print(f"  行数: {r['total_lines']}, 违规: {len(violations)}")

        # 按 parent_method 分类
        by_method = {}
        for v in violations:
            m = v["parent_method"]
            by_method.setdefault(m, []).append(v)

        for method, vs in by_method.items():
            print(f"  [{method}]: {len(vs)} 处")
            for v in vs[:5]:  # 最多显示 5 处
                print(f"    L{v['call_line']}: {v['method']} (except L{v['except_line']})")
            if len(vs) > 5:
                print(f"    ... 还有 {len(vs) - 5} 处")

    # 保存 JSON
    output_path = PROJECT_ROOT / "tests" / "_r161_d_r51_scan.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nJSON 输出: {output_path}")


if __name__ == "__main__":
    main()
