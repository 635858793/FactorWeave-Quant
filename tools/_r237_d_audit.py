"""
R237-D 子智能体 D: 业务核心 Service 0 dispose 链扫描脚本
- 扫 core/ 目录下所有 Service/Manager/Engine/Provider/Bridge/Executor/Coordinator/Monitor/Factory 类
- 检查 4 链 dispose 方法 (dispose/shutdown/close/cleanup)
- 排除 GUI widget / 单例 utility / DB model / Backtest / DistributedNode / Deployment
- 识别业务核心 (callsite 数 ≥ 3) + 0 dispose 链
"""
import ast
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = PROJECT_ROOT / "core"

# 类名后缀: 业务核心 service/manager/engine
CORE_SUFFIXES = (
    "Service", "Manager", "Engine", "Provider", "Bridge",
    "Executor", "Coordinator", "Monitor", "Factory", "Router", "Adapter",
)
# 排除的类名后缀 (GUI widget / utility)
EXCLUDE_SUFFIXES = (
    "Widget", "Dialog", "Panel", "Tab", "Button", "Label",
    "Layout", "Style", "Theme", "Window", "View", "Frame",
    "ItemDelegate", "Proxy", "Renderer", "Model",
)
# 排除的目录
EXCLUDE_DIRS = (
    "webgpu", "backtest", "deployment", "distributed_node", "utils",
    "ui_integration", "gui", "monitoring",
)

# 4 链 dispose 方法
DISPOSE_METHODS = ("dispose", "shutdown", "close", "cleanup", "do_dispose")


def is_excluded_dir(rel_path: str) -> bool:
    parts = rel_path.split("/")
    return any(p in EXCLUDE_DIRS for p in parts)


def is_business_class(name: str) -> bool:
    if name.endswith(EXCLUDE_SUFFIXES):
        return False
    return any(name.endswith(s) for s in CORE_SUFFIXES)


def get_class_methods(node: ast.ClassDef) -> Set[str]:
    methods = set()
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.add(item.name)
    return methods


def has_dispose_chain(methods: Set[str]) -> bool:
    """是否拥有 4 链 dispose 方法中的任意一个"""
    return bool(methods & set(DISPOSE_METHODS))


def count_callsites(class_name: str, project_root: Path) -> int:
    """简易统计: Grep 类名 (跨 core/ + tests/ + gui/ + plugins/ + services/)"""
    count = 0
    search_dirs = ["core", "tests", "services", "plugins"]
    for d in search_dirs:
        dir_path = project_root / d
        if not dir_path.exists():
            continue
        for f in dir_path.rglob("*.py"):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                # 仅在代码行匹配 (避免注释/docstring)
                for line in content.split("\n"):
                    if class_name in line and not line.strip().startswith("#"):
                        count += 1
            except Exception:
                pass
    return count


def is_inheritance_of_base_service(class_node: ast.ClassDef) -> bool:
    """检查类是否继承 BaseService / AsyncBaseService / ConfigurableService / CacheableService"""
    bases = []
    for b in class_node.bases:
        if isinstance(b, ast.Name):
            bases.append(b.id)
        elif isinstance(b, ast.Attribute):
            bases.append(b.attr)
    base_service_set = {
        "BaseService", "AsyncBaseService", "ConfigurableService", "CacheableService",
    }
    return any(b in base_service_set for b in bases)


def scan_classes(core_dir: Path) -> List[Dict]:
    """扫描 core/ 目录所有类"""
    results = []
    for py_file in core_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        rel_path = str(py_file.relative_to(PROJECT_ROOT))
        if is_excluded_dir(rel_path):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content, filename=str(py_file))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if not is_business_class(node.name):
                    continue
                methods = get_class_methods(node)
                has_chain = has_dispose_chain(methods)
                inherits_base = is_inheritance_of_base_service(node)
                # 排除继承 BaseService (自动拥有 dispose)
                if inherits_base:
                    continue
                # 计算行号
                if hasattr(node, "lineno"):
                    line_no = node.lineno
                else:
                    line_no = 0
                # 排除私有内部类 (以下划线开头)
                if node.name.startswith("_"):
                    continue
                results.append({
                    "class_name": node.name,
                    "file": rel_path,
                    "line": line_no,
                    "methods": sorted(methods),
                    "has_dispose_chain": has_chain,
                    "inherits_base_service": inherits_base,
                })
    return results


def find_0_dispose_candidates(results: List[Dict]) -> List[Dict]:
    """找出 0 dispose 链候选"""
    candidates = []
    for r in results:
        if r["has_dispose_chain"]:
            continue
        candidates.append(r)
    return candidates


def main():
    print("=" * 80)
    print("R237-D 业务核心 Service 0 dispose 链扫描")
    print("=" * 80)
    print(f"扫描根目录: {CORE_DIR}")
    print(f"扫描类后缀: {CORE_SUFFIXES}")
    print(f"排除目录: {EXCLUDE_DIRS}")
    print()
    
    all_classes = scan_classes(CORE_DIR)
    print(f"扫描到 {len(all_classes)} 个候选类 (业务核心 + 非 BaseService 继承)")
    
    with_chain = [r for r in all_classes if r["has_dispose_chain"]]
    without_chain = find_0_dispose_candidates(all_classes)
    print(f"  其中有 4 链 dispose: {len(with_chain)}")
    print(f"  其中 0 dispose 链 (候选): {len(without_chain)}")
    print()
    
    coverage = (len(with_chain) / len(all_classes) * 100.0) if all_classes else 0.0
    print(f"覆盖率: {coverage:.1f}%")
    print()
    
    # 计算 callsite (前 30)
    print("计算 callsite 计数 (前 30 候选)...")
    enriched = []
    for r in without_chain:
        cs = count_callsites(r["class_name"], PROJECT_ROOT)
        r["callsites"] = cs
        enriched.append(r)
    
    # 按 callsite 排序
    enriched.sort(key=lambda x: -x["callsites"])
    
    print()
    print("=" * 80)
    print(f"0 dispose 链候选清单 (按 callsite 排序, 前 30)")
    print("=" * 80)
    print(f"{'#':<4} {'类名':<45} {'文件:行':<55} {'callsite':<10}")
    print("-" * 120)
    for i, r in enumerate(enriched[:30], 1):
        location = f"{r['file']}:{r['line']}"
        print(f"{i:<4} {r['class_name']:<45} {location:<55} {r['callsites']:<10}")
    
    # 业务核心 (callsite ≥ 3)
    business_cores = [r for r in enriched if r["callsites"] >= 3]
    print()
    print("=" * 80)
    print(f"业务核心 0 dispose 链候选 (callsite >= 3): {len(business_cores)}")
    print("=" * 80)
    for i, r in enumerate(business_cores, 1):
        print(f"  P{i}: {r['class_name']:<45} ({r['file']}:{r['line']}, callsites={r['callsites']})")
    
    # 写入 JSON
    output = {
        "scan_root": str(CORE_DIR),
        "total_classes": len(all_classes),
        "with_dispose_chain": len(with_chain),
        "without_dispose_chain": len(without_chain),
        "coverage_percent": round(coverage, 2),
        "business_core_0_dispose": len(business_cores),
        "candidates_0_dispose": [
            {k: v for k, v in r.items() if k != "methods"} 
            for r in enriched
        ],
        "business_core_list": [
            {k: v for k, v in r.items() if k != "methods"}
            for r in business_cores
        ],
    }
    out_path = PROJECT_ROOT / ".trae" / "reports" / "monitoring" / "r237_d_dispose_audit.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n结果已写入: {out_path}")


if __name__ == "__main__":
    main()
