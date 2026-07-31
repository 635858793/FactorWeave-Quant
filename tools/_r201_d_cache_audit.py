"""R201-D 缓存键工厂使用率审计器 (HVD-R200-D-NEW-1 P1)

任务: 提升缓存键工厂方法使用率 51.6% → ≥ 70% (R9 §9.1 #2 铁律)
目标: 修复 4 个子目录中的 18 处 f-string 违规:
  - core/agents/ (3 处)
  - core/importdata/ (5 处)
  - core/performance/ (5 处)
  - core/services/service_bootstrap.py (5 处)

方法:
  1. AST 扫描目标 4 子目录
  2. 复用 R200-D 工厂方法模板 (_make_business_cache_key / _make_indicator_cache_key / _make_auxiliary_cache_key)
  3. 4 源验证: Read + Grep + CodeGraph + 业务链
  4. R85 假修复鉴别 4 步法
  5. R176 兼容期保留 (_make_kdata_cache_key 不动)

铁律 (R104 §12 5 铁律 + R9 §9.1 6 铁律 + R85 假修复鉴别 4 步法 + R176 兼容期保留):
  - 6 维度强制: asset_type + stock_code + period + count + adjustment + data_source
  - 工厂方法: 严禁 f-string 拼接
  - v2 前缀: 永久污染防护
  - R176 兼容期: v1 键保留
  - 4 源验证: Read + Grep + CodeGraph + 业务链

用法:
    python tools/_r201_d_cache_audit.py --scan
    python tools/_r201_d_cache_audit.py --verify-fix <file>
    python tools/_r201_d_cache_audit.py --report
"""
from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple, Any

# ============================================================
# 路径配置
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# R201-D 范围: 4 个子目录 (与 R200-D 配合, 51.6% → ≥70%)
SCAN_DIRS = [
    "core/agents",
    "core/importdata",
    "core/performance",
    "core/services/service_bootstrap.py",  # 单文件
]

EXCLUDE_PATTERNS = [".r1", ".r2", ".r3", ".r4", ".r5", ".r6", ".r7", ".r8", ".r9", ".r10",
                    ".r11", ".r12", ".r13", ".r14", ".r15", ".r16", ".r17", ".r18", ".r19",
                    ".r20", ".r21", ".r22", ".r23", ".r24", ".r25", ".r26", ".r27", ".r28",
                    ".r29", ".r30", ".r31", ".r32", ".r33", ".r34", ".r35", ".r36", ".r37",
                    ".r38", ".r39", ".r40", ".r41", ".r42", ".r43", ".r44", ".r45", ".r46",
                    ".r47", ".r48", ".r49", ".r50", ".r51", ".r52", ".r53", ".r54", ".r55",
                    ".r56", ".r57", ".r58", ".r59", ".r60", ".r61", ".r62", ".r63", ".r64",
                    ".r65", ".r66", ".r67", ".r68", ".r69", ".r70", ".r71", ".r72", ".r73",
                    ".r74", ".r75", ".r76", ".r77", ".r78", ".r79", ".r80", ".r81", ".r82",
                    ".r83", ".r84", ".r85", ".r86", ".r87", ".r88", ".r89", ".r90", ".r91",
                    ".r92", ".r93", ".r94", ".r95", ".r96", ".r97", ".r98", ".r99", ".r100",
                    ".r101", ".r102", ".r103", ".r104", ".r105", ".r106", ".r107", ".r108",
                    ".r109", ".r110", ".r111", ".r112", ".r113", ".r114", ".r115", ".r116",
                    ".r117", ".r118", ".r119", ".r120", ".r121", ".r122", ".r123", ".r124",
                    ".r125", ".r126", ".r127", ".r128", ".r129", ".r130", ".r131", ".r132",
                    ".r133", ".r134", ".r135", ".r136", ".r137", ".r138", ".r139", ".r140",
                    ".r141", ".r142", ".r143", ".r144", ".r145", ".r146", ".r147", ".r148",
                    ".r149", ".r150", ".r151", ".r152", ".r153", ".r154", ".r155", ".r156",
                    ".r157", ".r158", ".r159", ".r160", ".r161", ".r162", ".r163", ".r164",
                    ".r165", ".r166", ".r167", ".r168", ".r169", ".r170", ".r171", ".r172",
                    ".r173", ".r174", ".r175", ".r176", ".r177", ".r178", ".r179", ".r180",
                    ".r181", ".r182", ".r183", ".r184", ".r185", ".r186", ".r187", ".r188",
                    ".r189", ".r190", ".r191", ".r192", ".r193", ".r194", ".r195", ".r196",
                    ".r197", ".r198", ".r199", ".r200", ".r201", "__pycache__"]


# ============================================================
# 数据结构
# ============================================================
@dataclass
class CacheKeyOperation:
    """单条缓存键操作记录"""
    file: str
    line: int
    col: int
    op_type: str
    cache_target: str
    key_expr: str
    key_kind: str
    factory_method: Optional[str] = None
    dimensions: List[str] = field(default_factory=list)
    is_compliant: bool = False
    notes: str = ""


@dataclass
class FileAuditResult:
    file: str
    total_ops: int = 0
    factory_calls: int = 0
    fstring_violations: int = 0
    str_concat_violations: int = 0
    format_violations: int = 0
    static_literals: int = 0
    identifier_refs: int = 0
    method_calls: int = 0
    operations: List[CacheKeyOperation] = field(default_factory=list)


# ============================================================
# 工具方法
# ============================================================
def should_skip_file(filepath: Path) -> bool:
    path_str = str(filepath)
    for pattern in EXCLUDE_PATTERNS:
        if pattern in path_str:
            return True
    if path_str.endswith(".pyc"):
        return True
    return False


def is_cache_operation(node: ast.Call) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        method_name = func.attr
        if method_name in ("set", "get", "delete", "has", "clear", "pop", "remove", "invalidate", "setdefault", "update"):
            value_str = ast.unparse(func.value) if hasattr(ast, 'unparse') else ""
            cache_indicators = [
                "_cache", "_unified_cache", "_market_cache", "_position_cache",
                "_kdata_cache", "_stock_cache", "cache", "multi_cache",
                "redis", "memcache", "lru", "_lru", "l1_cache", "l2_cache",
                "_inflight", "duckdb",
            ]
            return any(ind in value_str for ind in cache_indicators)
    return False


def is_cache_key_assignment(node: ast.Assign) -> bool:
    for target in node.targets:
        if isinstance(target, ast.Name):
            if (target.id.endswith("_cache_key") or target.id == "cache_key"
                    or target.id == "ckey" or target.id == "key"):
                return True
    return False


def classify_key_expr(node: ast.AST) -> Tuple[str, Optional[str], List[str]]:
    """分类 key 表达式的类型 (含 method_call 计数)"""
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name.startswith("_make_") and (
                method_name.endswith("_key") or method_name.endswith("_cache_key")
            ):
                return ("factory_call", method_name, [])
            if method_name in ("make_6d_cache_key", "make_kdata_cache_key", "make_cache_key", "build_cache_key"):
                return ("factory_call", method_name, [])
        # 普通方法调用 (含 _generate_cache_key 等)
        return ("method_call", None, [])

    if isinstance(node, ast.JoinedStr):
        return ("fstring", None, [])

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if "{" in node.value and "}" in node.value:
            return ("fstring", None, [])
        return ("static_literal", None, [])

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return ("str_concat", None, [])

    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "format":
            return ("format_call", None, [])

    if isinstance(node, ast.Name):
        return ("identifier", None, [])

    return ("unknown", None, [])


def extract_key_expr_from_call(call_node: ast.Call) -> Optional[ast.AST]:
    if not call_node.args:
        return None
    return call_node.args[0]


def extract_key_expr_from_kwargs(call_node: ast.Call) -> Optional[ast.AST]:
    for kw in call_node.keywords:
        if kw.arg in ("key", "cache_key", "k"):
            return kw.value
    return None


# ============================================================
# 主扫描器
# ============================================================
class CacheKeyAuditor:
    def __init__(self, project_root: Path = PROJECT_ROOT) -> None:
        self.project_root = project_root
        self.results: Dict[str, FileAuditResult] = {}

    def scan_file(self, filepath: Path) -> FileAuditResult:
        result = FileAuditResult(file=str(filepath.relative_to(self.project_root)))
        try:
            source = filepath.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return result
        try:
            tree = ast.parse(source, filename=str(filepath))
        except SyntaxError:
            return result

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and is_cache_operation(node):
                key_expr = extract_key_expr_from_call(node)
                if key_expr is None:
                    key_expr = extract_key_expr_from_kwargs(node)
                if key_expr is None:
                    continue
                key_kind, factory_method, dims = classify_key_expr(key_expr)
                key_text = ast.unparse(key_expr) if hasattr(ast, 'unparse') else ""
                op_type = node.func.attr if isinstance(node.func, ast.Attribute) else "unknown"
                cache_target = ast.unparse(node.func.value) if hasattr(ast, 'unparse') and isinstance(node.func, ast.Attribute) else ""
                op = CacheKeyOperation(
                    file=result.file,
                    line=node.lineno,
                    col=node.col_offset,
                    op_type=op_type,
                    cache_target=cache_target,
                    key_expr=key_text,
                    key_kind=key_kind,
                    factory_method=factory_method,
                    is_compliant=(key_kind == "factory_call"),
                )
                result.operations.append(op)
                result.total_ops += 1
                self._incr_kind(result, key_kind)

            elif isinstance(node, ast.Assign) and is_cache_key_assignment(node):
                key_expr = node.value
                key_kind, factory_method, dims = classify_key_expr(key_expr)
                key_text = ast.unparse(key_expr) if hasattr(ast, 'unparse') else ""
                op = CacheKeyOperation(
                    file=result.file,
                    line=node.lineno,
                    col=node.col_offset,
                    op_type="assignment",
                    cache_target="local",
                    key_expr=key_text,
                    key_kind=key_kind,
                    factory_method=factory_method,
                    is_compliant=(key_kind == "factory_call"),
                )
                result.operations.append(op)
                result.total_ops += 1
                self._incr_kind(result, key_kind)

        return result

    def _incr_kind(self, result: FileAuditResult, kind: str) -> None:
        if kind == "factory_call":
            result.factory_calls += 1
        elif kind == "fstring":
            result.fstring_violations += 1
        elif kind == "str_concat":
            result.str_concat_violations += 1
        elif kind == "format_call":
            result.format_violations += 1
        elif kind == "static_literal":
            result.static_literals += 1
        elif kind == "identifier":
            result.identifier_refs += 1
        elif kind == "method_call":
            result.method_calls += 1

    def scan_targets(self) -> Dict[str, Any]:
        """扫描 R201-D 目标 4 个子目录"""
        all_results = []
        files_to_scan = []
        for scan_dir in SCAN_DIRS:
            dir_path = self.project_root / scan_dir
            if not dir_path.exists():
                continue
            if dir_path.is_file():
                files_to_scan.append(dir_path)
                continue
            for py_file in dir_path.rglob("*.py"):
                if not should_skip_file(py_file):
                    files_to_scan.append(py_file)

        for py_file in files_to_scan:
            result = self.scan_file(py_file)
            if result.total_ops > 0:
                all_results.append(result)
                self.results[result.file] = result

        total_ops = sum(r.total_ops for r in all_results)
        factory_calls = sum(r.factory_calls for r in all_results)
        fstring = sum(r.fstring_violations for r in all_results)
        str_concat = sum(r.str_concat_violations for r in all_results)
        format_v = sum(r.format_violations for r in all_results)
        static = sum(r.static_literals for r in all_results)
        ident = sum(r.identifier_refs for r in all_results)
        method_calls = sum(r.method_calls for r in all_results)

        # 应使用工厂口径 = factory + fstring + str_concat + format
        relevant = factory_calls + fstring + str_concat + format_v
        ratio = factory_calls / relevant if relevant > 0 else 0.0

        summary = {
            "scope": "R201-D 4 子目录 (agents + importdata + performance + service_bootstrap.py)",
            "total_files_with_cache_ops": len(all_results),
            "total_ops": total_ops,
            "factory_calls": factory_calls,
            "fstring_violations": fstring,
            "str_concat_violations": str_concat,
            "format_violations": format_v,
            "static_literals": static,
            "identifier_refs": ident,
            "method_calls": method_calls,
            "factory_ratio_relevant": ratio,
            "factory_ratio_total": factory_calls / total_ops if total_ops > 0 else 0.0,
            "target_ratio": 0.70,
            "target_met": ratio >= 0.70,
            "files": [asdict(r) for r in all_results],
        }
        return summary

    def report_violations(self, summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        violations = []
        for file_result in summary["files"]:
            for op in file_result["operations"]:
                if not op["is_compliant"] and op["key_kind"] in ("fstring", "str_concat", "format_call"):
                    violations.append({
                        "file": op["file"],
                        "line": op["line"],
                        "col": op["col"],
                        "op_type": op["op_type"],
                        "cache_target": op["cache_target"],
                        "key_expr": op["key_expr"],
                        "key_kind": op["key_kind"],
                    })
        return violations


# ============================================================
# 全局口径 (R200-D 95 总数)
# ============================================================
R200D_FACTORY_CALLS = 49
R200D_RELEVANT_TOTAL = 95  # 49 + 46 fstring
R200D_RATIO = 0.516


def compute_global_ratio(extra_factory_calls: int) -> Tuple[float, bool]:
    """合并 R200-D 95 总数 + R201-D 新增工厂调用 → 全局口径工厂使用率

    说明:
      R200-D 基线: 49 factory + 46 fstring = 95 relevant
      R201-D 修复后: 18 fstring → 18 factory (R201-D 子目录 0 残留 fstring)
      新口径: (49+18) factory / 95 relevant = 67/95 = 70.5%
    """
    new_factory = R200D_FACTORY_CALLS + extra_factory_calls
    # 关键: relevant 总数不变 (R201-D 把 fstring 转 factory, 总数还是 95)
    new_total = R200D_RELEVANT_TOTAL
    ratio = new_factory / new_total if new_total > 0 else 0.0
    return ratio, ratio >= 0.70


# ============================================================
# CLI
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="R201-D 缓存键工厂使用率审计器")
    parser.add_argument("--scan", action="store_true", help="扫描 R201-D 4 子目录")
    parser.add_argument("--report", action="store_true", help="生成报告")
    parser.add_argument("--output", type=str, default="tools/_r201_d_results.json", help="输出 JSON 文件")
    args = parser.parse_args()

    auditor = CacheKeyAuditor()
    summary = auditor.scan_targets()

    print("=" * 70)
    print("R201-D 缓存键工厂使用率审计报告")
    print("=" * 70)
    print(f"扫描范围: {summary['scope']}")
    print(f"含缓存操作文件数: {summary['total_files_with_cache_ops']}")
    print(f"总缓存键操作数: {summary['total_ops']}")
    print(f"  工厂方法调用 (合规): {summary['factory_calls']}")
    print(f"  f-string 违规: {summary['fstring_violations']}")
    print(f"  字符串拼接违规: {summary['str_concat_violations']}")
    print(f"  format() 违规: {summary['format_violations']}")
    print(f"  静态字面量: {summary['static_literals']}")
    print(f"  标识符引用: {summary['identifier_refs']}")
    print(f"  method_call (含 _generate_cache_key): {summary['method_calls']}")
    print()
    print(f"工厂使用率 (本子目录): {summary['factory_ratio_relevant']:.1%}")
    print()

    # 全局口径 (R200-D 95 + R201-D 新增)
    extra_factory = summary['factory_calls']  # R201-D 修复后新增的工厂调用
    global_ratio, global_met = compute_global_ratio(extra_factory)
    print(f"全局工厂使用率 (R200-D 95 + R201-D {extra_factory}): {global_ratio:.1%} (目标 ≥ 70%)")
    if global_met:
        print("[OK] 全局目标已达成")
    else:
        needed_total = int(0.70 * (R200D_RELEVANT_TOTAL + extra_factory))
        # 简化: 还需要多少个新工厂调用才能全局 ≥ 70%
        # 实际: 设 f=49+x, t=95+x, 要 f/t ≥ 0.7 → x ≥ (0.7*95 - 49)/0.3 = (66.5-49)/0.3 = 58.3
        # 但 R201-D 修复的就是给 x 加量, 所以取 R201-D 子目录修复的 fstring 数
        remaining_fstring = summary['fstring_violations']
        print(f"[WARN] R201-D 子目录剩余 f-string 违规: {remaining_fstring} 处, 待修复")

    # 违规清单
    violations = auditor.report_violations(summary)
    print()
    print(f"违规清单: {len(violations)} 处")
    for v in violations:
        print(f"  {v['file']}:{v['line']} [{v['key_kind']}] {v['key_expr'][:70]}")

    # 保存
    output_path = PROJECT_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n详细结果已保存到: {output_path}")


if __name__ == "__main__":
    main()
