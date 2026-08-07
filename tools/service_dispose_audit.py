"""
R241-P1-D 转正: 业务核心 Service dispose 链审计工具 (service_dispose_audit.py)

由旧版 dispose 审计脚本转正 (R231 声称重建 → R241 落地), 4 项结构性改动:
1. MRO 链解析: 全量 AST 类名索引 + 递归基类链 → 间接继承 BaseService 也识别
   (替换旧版仅检查直接基类名)
2. _do_dispose 钩子检测: BaseService 子类不再直接跳过, 而是检查是否重写
   _do_dispose → 输出 base_service_without_do_dispose_hook 分组 (P1-C 三层遗漏可见化)
3. EXCLUDE_DIRS 修正: 移除 core 下不存在的 backtest/deployment/distributed_node,
   不再排除 monitoring (PerformanceMonitor 需被扫描)
4. callsite 精确化: ast.NodeVisitor 统计 ast.Name 真实引用, 排除注释/字符串/定义处
   (替换原 L102 纯字符串子串匹配, 消除同名前缀类误计数)

TDD: tests/test_r241_p0c_dispose_chains_tools_cache.py T12-T14
"""
import ast
import json
from pathlib import Path
from typing import Dict, List, Set, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = PROJECT_ROOT / "core"

# 业务核心类名后缀
CORE_SUFFIXES = (
    "Service", "Manager", "Engine", "Provider", "Bridge",
    "Executor", "Coordinator", "Monitor", "Factory", "Router", "Adapter",
)
# 排除的类名后缀 (GUI 控件 / 渲染层)
EXCLUDE_SUFFIXES = (
    "Widget", "Dialog", "Panel", "Tab", "Button", "Label",
    "Layout", "Style", "Theme", "Window", "View", "Frame",
    "ItemDelegate", "Proxy", "Renderer", "Model",
)
# 排除的目录 (改动 3: 移除 core 下不存在的 backtest/deployment/distributed_node;
# 不再排除 monitoring → PerformanceMonitor 可被扫描)
EXCLUDE_DIRS = (
    "webgpu", "utils", "ui_integration", "gui",
)
# 4 链 dispose 方法
DISPOSE_METHODS = ("dispose", "shutdown", "close", "cleanup", "do_dispose", "stop")
# BaseService 类名 (自动拥有 dispose)
BASE_SERVICE_NAMES = {
    "BaseService", "AsyncBaseService", "ConfigurableService", "CacheableService",
    "ComponentLifecycleManager",
}

# 全量 AST 类索引: class_name -> 直接基类名列表 (MRO 链解析基础, 改动 1)
_CLASS_INDEX: Dict[str, List[str]] = {}
# _do_dispose 钩子索引: class_name -> 是否重写 _do_dispose (改动 2)
_DO_DISPOSE_INDEX: Dict[str, bool] = {}


def is_excluded_dir(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    return any(p in EXCLUDE_DIRS for p in parts)


def is_business_class(name: str) -> bool:
    if name.endswith(EXCLUDE_SUFFIXES):
        return False
    return any(name.endswith(s) for s in CORE_SUFFIXES)


def build_class_index(core_dir: Path) -> None:
    """构建全量 class_name -> 直接基类名 映射 + _do_dispose 重写索引 (改动 1/2 前置)"""
    _CLASS_INDEX.clear()
    _DO_DISPOSE_INDEX.clear()
    for py_file in core_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        rel_path = str(py_file.relative_to(PROJECT_ROOT)).replace("\\", "/")
        if is_excluded_dir(rel_path):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content, filename=str(py_file))
        except Exception:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    bases.append(b.id)
                elif isinstance(b, ast.Attribute):
                    bases.append(b.attr)
            _CLASS_INDEX[node.name] = bases
            _DO_DISPOSE_INDEX[node.name] = any(
                isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "_do_dispose"
                for item in node.body
            )


def resolve_mro_ancestors(class_name: str, _seen: Optional[Set[str]] = None) -> Set[str]:
    """递归解析 class_name 的 MRO 祖先类名集合 (含间接基类, 改动 1)"""
    if _seen is None:
        _seen = set()
    if class_name in _seen:
        return _seen
    _seen.add(class_name)
    for base in _CLASS_INDEX.get(class_name, []):
        resolve_mro_ancestors(base, _seen)
    return _seen


def is_inheritance_of_base_service(class_name: str) -> bool:
    """MRO 链解析: 直接/间接继承 BASE_SERVICE_NAMES 任一基类均识别 (改动 1)"""
    ancestors = resolve_mro_ancestors(class_name)
    return bool(ancestors & BASE_SERVICE_NAMES)


def is_enum_or_dataclass(class_node: ast.ClassDef) -> bool:
    for dec in class_node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "dataclass":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == "dataclass":
            return True
    for b in class_node.bases:
        if isinstance(b, ast.Name) and b.id in ("Enum", "IntEnum", "Flag", "IntFlag"):
            return True
    return False


def get_class_methods(node: ast.ClassDef) -> Set[str]:
    methods = set()
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.add(item.name)
    return methods


def has_dispose_chain(methods: Set[str]) -> bool:
    return bool(methods & set(DISPOSE_METHODS))


class CallsiteVisitor(ast.NodeVisitor):
    """精确统计 class_name 作为 ast.Name 引用的次数 (改动 4:
    排除注释/字符串/定义处/同名前缀类, 原实现为子串匹配误计数)"""

    def __init__(self, class_name: str):
        self.class_name = class_name
        self.count = 0

    def visit_Name(self, node: ast.Name):
        if node.id == self.class_name:
            self.count += 1
        self.generic_visit(node)


def count_callsites(class_name: str, project_root: Path) -> int:
    """callsite 精确统计 (改动 4)"""
    count = 0
    files: List[Path] = []
    for item in ("core", "tests", "services", "plugins", "gui", "backtest"):
        item_path = project_root / item
        if item_path.is_dir():
            files.extend(item_path.rglob("*.py"))
    for fname in ("main.py", "api_server.py"):
        p = project_root / fname
        if p.exists():
            files.append(p)

    for f in files:
        if "__pycache__" in str(f).replace("\\", "/"):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content, filename=str(f))
        except Exception:
            continue
        visitor = CallsiteVisitor(class_name)
        visitor.visit(tree)
        count += visitor.count
    return count


def scan_classes(core_dir: Path):
    """扫描候选类: 返回 (0 dispose 链候选, BaseService 子类缺 _do_dispose 钩子列表)"""
    results = []
    base_service_without_hook = []
    for py_file in core_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        rel_path = str(py_file.relative_to(PROJECT_ROOT)).replace("\\", "/")
        if is_excluded_dir(rel_path):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content, filename=str(py_file))
        except Exception:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name.startswith("_"):
                continue
            if is_enum_or_dataclass(node):
                continue
            if is_inheritance_of_base_service(node.name):
                # 改动 2: BaseService 子类不再直接跳过, 检查 _do_dispose 钩子
                if not _DO_DISPOSE_INDEX.get(node.name, False):
                    base_service_without_hook.append({
                        "class_name": node.name,
                        "file": rel_path,
                        "line": node.lineno,
                    })
                continue  # BaseService 子类自带 dispose, 不属 0 dispose 链
            if not is_business_class(node.name):
                continue
            methods = get_class_methods(node)
            has_chain = has_dispose_chain(methods)
            results.append({
                "class_name": node.name,
                "file": rel_path,
                "line": node.lineno,
                "methods": sorted(methods),
                "has_dispose_chain": has_chain,
            })
    return results, base_service_without_hook


def main():
    print("=" * 80)
    print("R241-P1-D 转正: 业务核心 Service dispose 链精确审计 (service_dispose_audit)")
    print("=" * 80)

    build_class_index(CORE_DIR)
    all_classes, base_service_without_hook = scan_classes(CORE_DIR)
    print(f"扫描到 {len(all_classes)} 个候选类 (非 BaseService 链 + 非 Enum/dataclass + 业务核心)")
    print(f"BaseService 子类缺 _do_dispose 重写: {len(base_service_without_hook)} 个 (P1-C 层)")

    with_chain = [r for r in all_classes if r["has_dispose_chain"]]
    without_chain = [r for r in all_classes if not r["has_dispose_chain"]]
    print(f"  有 4 链 dispose/stop 方法: {len(with_chain)}")
    print(f"  0 dispose 链 (候选): {len(without_chain)}")

    coverage = (len(with_chain) / len(all_classes) * 100.0) if all_classes else 0.0
    print(f"覆盖率: {coverage:.1f}%")
    print()

    # 计算 callsite (AST 精确统计)
    print("计算 callsite 计数 (ast.Name 精确引用)...")
    for r in without_chain:
        r["callsites"] = count_callsites(r["class_name"], PROJECT_ROOT)

    without_chain.sort(key=lambda x: -x["callsites"])

    # R235-B 6 P1 候选状态
    r235_p1_candidates = {
        "OrderMonitor": "core/trading/order_monitor.py",
        "DataStandardizationEngine": "core/data_standardization_engine.py",
        "DataQualityRiskManager": "core/data_quality_risk_manager.py",
        "IntelligentFailoverEngine": "core/intelligent_failover_engine.py",
        "StrategyManager": "core/trading/strategy_manager.py",
        "IndustryManager": "core/industry_manager.py",
    }
    print("=" * 80)
    print("R235-B 6 P1 候选状态核验")
    print("=" * 80)
    for cname, expected_file in r235_p1_candidates.items():
        match = next((r for r in without_chain if r["class_name"] == cname and r["file"] == expected_file), None)
        if match:
            print(f"  [⏳ 仍待办] {cname:<35} {expected_file}:{match['line']}, callsite={match['callsites']}")
        else:
            match_with = next((r for r in with_chain if r["class_name"] == cname), None)
            if match_with:
                print(f"  [✅ 已治理] {cname:<35} 找到 dispose 链")
            else:
                print(f"  [❓ 找不到] {cname:<35} 文件路径异常")

    # R237-B 6 P2 候选状态
    r237_p2_candidates = {
        "AssetSeparatedDatabaseManager": "core/asset_database_manager.py",
        "EnhancedMoneyManager": "core/money_manager.py",
        "RealDataProvider": "core/real_data_provider.py",
        "UnifiedResourceMonitor": "core/performance/resource_monitor.py",
        "DataMissingManager": "core/ui_integration/data_missing_manager.py",
        "JITWarmupManager": "core/jit_warmup.py",
    }
    print()
    print("=" * 80)
    print("R237-B 6 P2 候选状态核验 (应为已治理)")
    print("=" * 80)
    for cname, expected_file in r237_p2_candidates.items():
        match_with = next((r for r in with_chain if r["class_name"] == cname and r["file"] == expected_file), None)
        match_without = next((r for r in without_chain if r["class_name"] == cname and r["file"] == expected_file), None)
        if match_with:
            print(f"  [✅ R237-B 已治理] {cname:<35} {expected_file}")
        elif match_without:
            print(f"  [❌ R237-B 假修复] {cname:<35} 仍未治理, callsite={match_without['callsites']}")
        else:
            print(f"  [❓ 未找到] {cname:<35}")

    # BaseService 子类缺 _do_dispose 钩子 (P1-C 层, 改动 2 输出)
    print()
    print("=" * 80)
    print("BaseService 子类缺 _do_dispose 钩子重写 (dispose() 空操作风险)")
    print("=" * 80)
    for i, r in enumerate(sorted(base_service_without_hook, key=lambda x: x["file"]), 1):
        print(f"  #{i:<3} {r['class_name']:<45} {r['file']}:{r['line']}")

    # 业务核心 0 dispose 链 (callsite >= 5) 剩余候选
    print()
    print("=" * 80)
    print("剩余业务核心 0 dispose 链候选 (callsite >= 5, 按 callsite 排序)")
    print("=" * 80)
    business_remaining = [r for r in without_chain if r["callsites"] >= 5]
    seen = set()
    deduped = []
    for r in business_remaining:
        if r["class_name"] in seen:
            continue
        seen.add(r["class_name"])
        deduped.append(r)
    deduped.sort(key=lambda x: -x["callsites"])

    for i, r in enumerate(deduped, 1):
        print(f"  #{i:<3} {r['class_name']:<45} {r['file']}:{r['line']:<4} callsite={r['callsites']}")

    # 写入 JSON
    output = {
        "tool": "tools/service_dispose_audit.py (R241-P1-D 转正)",
        "scan_root": "core/",
        "total_business_classes": len(all_classes),
        "with_dispose_chain": len(with_chain),
        "without_dispose_chain": len(without_chain),
        "base_service_without_do_dispose_hook": len(base_service_without_hook),
        "coverage_percent": round(coverage, 2),
        "r235_p1_candidates_status": r235_p1_candidates,
        "r237_p2_candidates_status": r237_p2_candidates,
        "remaining_business_core_0_dispose": deduped,
        "base_service_without_do_dispose_hook_list": base_service_without_hook,
    }
    out_path = PROJECT_ROOT / ".trae" / "reports" / "monitoring" / "service_dispose_audit.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n结果已写入: {out_path}")
    print(f"\n剩余 0 dispose 链 (callsite>=5, 去重): {len(deduped)} 个")
    print(f"BaseService 子类缺 _do_dispose 钩子: {len(base_service_without_hook)} 个")


if __name__ == "__main__":
    main()
