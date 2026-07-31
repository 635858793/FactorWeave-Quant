"""
logger.debug 业务关键路径升级扫描器
R118 B15 教训: 业务关键路径 logger.debug 静默 → 监控盲点
业务关键路径关键词: order, fill, trade, position, balance, risk, fund
"""
import ast
import re
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

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

# 业务关键路径关键词 (出现在方法名/类名/调用参数中)
BUSINESS_KEYWORDS = [
    "order", "fill", "trade", "position", "balance", "risk", "fund",
    "execute", "submit", "cancel", "reject", "approve", "alert",
    "monitor", "check", "validate", "verify",
]


def is_business_method(method_name: str) -> bool:
    """判断方法名是否属于业务关键路径"""
    lower = method_name.lower()
    return any(kw in lower for kw in BUSINESS_KEYWORDS)


def find_business_debug_calls(tree, source_lines):
    """找到业务关键路径的 logger.debug 调用"""
    candidates = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_name = node.name
            if not is_business_method(method_name):
                continue

            for child in ast.walk(node):
                if isinstance(child, ast.Expr) and isinstance(child.value, ast.Call):
                    call = child.value
                    if isinstance(call.func, ast.Attribute):
                        if call.func.attr == "debug":
                            # 检查是否是 logger.debug
                            if isinstance(call.func.value, ast.Name):
                                if call.func.value.id in ("logger", "log", "_logger", "self_logger"):
                                    snippet = source_lines[child.lineno - 1].strip() if child.lineno - 1 < len(source_lines) else ""
                                    candidates.append({
                                        "method": method_name,
                                        "line": child.lineno,
                                        "snippet": snippet,
                                    })
    return candidates


def scan_file(rel_path: str):
    abs_path = PROJECT_ROOT / rel_path
    if not abs_path.exists():
        return None
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        source_lines = source.splitlines()
        candidates = find_business_debug_calls(tree, source_lines)
        return {"file": rel_path, "candidates": candidates, "total_lines": len(source_lines)}
    except SyntaxError as e:
        return {"file": rel_path, "error": str(e)}


def main():
    print("=== logger.debug 业务关键路径升级扫描 ===")
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
        n = len(r["candidates"])
        total += n
        print(f"\n=== {rel}: {n} 处 ===")
        for c in r["candidates"][:10]:  # 最多显示 10 处
            print(f"  L{c['line']} [{c['method']}]: {c['snippet'][:100]}")
        if len(r["candidates"]) > 10:
            print(f"  ... 还有 {len(r['candidates']) - 10} 处")

    print(f"\n总业务关键路径 logger.debug: {total}")

    import json
    output = PROJECT_ROOT / "tests" / "_r161_d_debug_upgrade.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"JSON: {output}")


if __name__ == "__main__":
    main()
