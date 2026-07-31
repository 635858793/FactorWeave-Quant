"""
静默 except 块扫描器
找出 except: pass / except: continue / except: return (无 logger) / except: ...
"""
import ast
import re
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

# 9 个关键文件
KEY_FILES = [
    "core/services/trading_service.py",
    "core/services/advanced_risk_control_service.py",
    "core/events/event_bus.py",
    "core/services/cache_service.py",
    "core/services/unified_data_manager.py",
    "core/trading/order_service.py",
    "core/trading_engine.py",
    "core/risk_manager.py",
    "core/services/service_bootstrap.py",
]


def has_logger_in_block(body) -> bool:
    """检查 body 内是否有 logger 调用"""
    for node in body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute):
                if call.func.attr in ("error", "critical", "exception", "warning", "info", "debug", "trace"):
                    return True
        # 递归检查嵌套
        if isinstance(node, ast.If):
            if has_logger_in_block(node.body) or has_logger_in_block(node.orelse):
                return True
        if isinstance(node, (ast.For, ast.While)):
            if has_logger_in_block(node.body) or has_logger_in_block(node.orelse):
                return True
        if isinstance(node, ast.With):
            if has_logger_in_block(node.body):
                return True
    return False


def get_first_stmt_simplified(body) -> str:
    """获取 except 块第一个语句的简化形式"""
    if not body:
        return "<empty>"
    first = body[0]
    if isinstance(first, ast.Pass):
        return "pass"
    if isinstance(first, ast.Continue):
        return "continue"
    if isinstance(first, ast.Return):
        return "return"
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
        if first.value.value is Ellipsis:
            return "..."
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Call):
        call = first.value
        if isinstance(call.func, ast.Attribute):
            if call.func.attr in ("error", "critical", "exception", "warning", "info", "debug"):
                return f"logger.{call.func.attr}(...)"
    return f"<{type(first).__name__}>"


def find_silent_except_blocks(tree, source_lines):
    """找到所有静默 except 块"""
    silent = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if handler.type is None:
                # bare except
                continue
            body = handler.body
            # 检查是否只包含 pass/continue/return
            is_silent = False
            reason = ""
            if not body:
                is_silent = True
                reason = "empty"
            else:
                # 简化判断
                first_kind = get_first_stmt_simplified(body)
                if first_kind in ("pass", "continue", "...", "<empty>"):
                    is_silent = True
                    reason = first_kind
                elif first_kind == "return":
                    # 静默 return 不一定有 logger
                    if not has_logger_in_block(body):
                        is_silent = True
                        reason = "return_no_logger"

            if is_silent:
                silent.append({
                    "line": handler.lineno,
                    "exc_type": ast.unparse(handler.type) if handler.type else "Exception",
                    "reason": reason,
                    "snippet": source_lines[handler.lineno - 1].strip() if handler.lineno - 1 < len(source_lines) else "",
                })
    return silent


def scan_file(rel_path: str):
    abs_path = PROJECT_ROOT / rel_path
    if not abs_path.exists():
        return None
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        source_lines = source.splitlines()
        silent = find_silent_except_blocks(tree, source_lines)
        return {"file": rel_path, "violations": silent, "total_lines": len(source_lines)}
    except SyntaxError as e:
        return {"file": rel_path, "error": str(e)}


def main():
    print("=== 静默 except 块扫描 ===")
    results = {}
    total = 0
    for rel in KEY_FILES:
        r = scan_file(rel)
        if not r:
            print(f"[SKIP] {rel}")
            continue
        if "error" in r:
            print(f"[ERR] {rel}: {r['error']}")
            continue
        results[rel] = r
        n = len(r["violations"])
        total += n
        print(f"\n=== {rel} (行数 {r['total_lines']}): {n} 处 ===")
        for v in r["violations"]:
            print(f"  L{v['line']} except {v['exc_type']}: {v['reason']}")
    print(f"\n总静默 except: {total}")

    # JSON
    import json
    output = PROJECT_ROOT / "tests" / "_r161_d_silent_except.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"JSON: {output}")


if __name__ == "__main__":
    main()
