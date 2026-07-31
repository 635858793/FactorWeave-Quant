"""
R196-C/D health_check + metrics 扫描器:
扫描全项目 Service 类,识别缺 health_check/metrics 方法的 Service
"""
import ast
import json
from pathlib import Path
from typing import List, Dict

# R195-D 已闭环的 Service 列表 (78 个)
R195_D_COVERED_SERVICES = [
    "unified_data_manager", "service_bootstrap", "ai_selection_integration_service",
    "main_window_coordinator", "event_coordinator", "performance_service",
    "sla_monitor", "cache_degradation_exporter", "performance_monitor",
    # ... 78 项, R195-D 已闭环
]


def has_method(node: ast.ClassDef, method_name: str) -> bool:
    """检查类是否定义了指定方法"""
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
            return True
    return False


def find_service_classes(file_path: Path) -> List[Dict]:
    """扫描文件中的 Service/Manager/Engine/Provider 类"""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    results = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        # 检查类名是否包含 Service/Manager/Engine/Provider/Bridge
        if not any(kw in node.name for kw in ["Service", "Manager", "Engine", "Provider", "Bridge", "Coordinator"]):
            continue
        # 排除基础类
        if node.name in {"BaseService", "AsyncBaseService", "ConfigurableService", "ServiceContainer"}:
            continue
        has_health = has_method(node, "health_check")
        has_metrics = has_method(node, "get_metrics") or has_method(node, "metrics")
        results.append({
            "file": str(file_path),
            "class": node.name,
            "line": node.lineno,
            "has_health_check": has_health,
            "has_metrics": has_metrics,
        })
    return results


def main():
    project_root = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")
    skip_patterns = {"test_", "__pycache__", ".git", "venv", "node_modules", ".trae"}

    all_services = []
    for py_file in project_root.rglob("*.py"):
        if any(p in str(py_file) for p in skip_patterns):
            continue
        if py_file.name.startswith("test_"):
            continue
        if "core" not in str(py_file) and "services" not in str(py_file):
            continue
        services = find_service_classes(py_file)
        all_services.extend(services)

    # 分类
    no_health = [s for s in all_services if not s["has_health_check"]]
    no_metrics = [s for s in all_services if not s["has_metrics"]]
    no_both = [s for s in all_services if not s["has_health_check"] and not s["has_metrics"]]

    # 写结果
    out = {
        "total_services": len(all_services),
        "no_health_check": len(no_health),
        "no_metrics": len(no_metrics),
        "no_both": len(no_both),
        "no_health_list": no_health[:50],  # 限制输出
        "no_metrics_list": no_metrics[:50],
    }
    out_file = project_root / "tools" / "_r196_cd_health_metrics_scan.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"扫描完成: {len(all_services)} 个 Service 类")
    print(f"  缺 health_check: {len(no_health)}")
    print(f"  缺 metrics: {len(no_metrics)}")
    print(f"  缺两者: {len(no_both)}")
    print(f"结果写入: {out_file}")
    print()
    print("Top 20 缺 health_check 的 Service:")
    for i, s in enumerate(no_health[:20], 1):
        file_short = s['file'].replace(str(project_root) + '\\', '')
        print(f"  {i:2}. {s['class']:40s} {file_short}:L{s['line']}")


if __name__ == "__main__":
    main()
