"""
监控埋点扫描器
HVD-158-A-2: 9 个服务是否都实现 health_check / get_metrics / get_status
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


def find_monitoring_methods(tree):
    """找到所有 health_check / get_metrics / get_status / get_health 方法"""
    methods = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            if name in ("health_check", "get_metrics", "get_status", "get_health"):
                methods[name] = {
                    "line": node.lineno,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "is_property": False,  # 简化
                }
            # 检查 @property 装饰器
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name) and decorator.id == "property":
                    if name in ("health", "is_healthy", "metrics", "status"):
                        methods[f"{name}@property"] = {
                            "line": node.lineno,
                            "is_async": False,
                            "is_property": True,
                        }
    return methods


def find_classes_in_file(tree):
    """找到所有顶级类"""
    classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "bases": [ast.unparse(b) for b in node.bases] if node.bases else [],
            })
    return classes


def scan_file(rel_path: str):
    abs_path = PROJECT_ROOT / rel_path
    if not abs_path.exists():
        return None
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        monitoring = find_monitoring_methods(tree)
        classes = find_classes_in_file(tree)
        return {
            "file": rel_path,
            "monitoring": monitoring,
            "classes": [c["name"] for c in classes],
        }
    except SyntaxError as e:
        return {"file": rel_path, "error": str(e)}


def main():
    print("=== 监控埋点扫描 HVD-158-A-2 ===")
    results = {}
    for rel in KEY_FILES:
        r = scan_file(rel)
        if not r:
            print(f"[SKIP] {rel}")
            continue
        if "error" in r:
            print(f"[ERR] {rel}: {r['error']}")
            continue
        results[rel] = r
        m = r["monitoring"]
        print(f"\n=== {rel} ===")
        print(f"  Classes: {r['classes']}")
        print(f"  Monitoring: {list(m.keys()) if m else '(none)'}")
        for name, info in m.items():
            print(f"    {name} @ L{info['line']} (async={info['is_async']}, property={info['is_property']})")

    # 汇总
    print("\n=== 监控埋点覆盖率表 ===")
    all_methods = ["health_check", "get_metrics", "get_status", "get_health"]
    print(f"{'文件':<45} | " + " | ".join(f"{m:<15}" for m in all_methods))
    print("-" * 100)
    for rel, r in results.items():
        m = r.get("monitoring", {})
        row = f"{rel:<45} | "
        for method in all_methods:
            row += f"{'YES' if method in m else 'NO':<15} | "
        print(row)

    import json
    output = PROJECT_ROOT / "tests" / "_r161_d_monitoring.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nJSON: {output}")


if __name__ == "__main__":
    main()
