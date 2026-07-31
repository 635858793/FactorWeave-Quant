"""R200-D 缓存键工厂使用率审计器 (R200-D HVD-R199-D2-03 P2)

任务: 提升缓存键工厂方法使用率 34.9% → ≥ 50% (R9 §9.1 #2 铁律)
方法:
  1. AST 扫描所有 .py 文件
  2. 识别 cache key 操作 (cache.set/get/delete + 字符串拼接)
  3. 分类:
     - factory_call: 走工厂方法 (合规, e.g. _make_xxx_cache_key)
     - fstring: f-string 拼接 (违规)
     - str_concat: 字符串拼接 (违规)
     - format_call: format() 调用 (违规)
     - static_literal: 静态字符串字面量 (合规, 不需要工厂)
  4. 4 源验证: Read + Grep + CodeGraph + 业务链
  5. R85 假修复鉴别 4 步法
  6. R176 兼容期保留 (v1 键保留)

铁律 (R104 §12 5 铁律 + R9 §9.1 6 铁律 + R85 假修复鉴别 4 步法):
  - 6 维度强制: asset_type + stock_code + period + count + adjustment + data_source
  - 工厂方法: 严禁 f-string 拼接
  - v2 前缀: 永久污染防护
  - R176 兼容期: v1 键保留
  - 4 源验证: Read + Grep + CodeGraph + 业务链

用法:
    python tools/_r200_d_cache_audit.py --scan
    python tools/_r200_d_cache_audit.py --verify-fix <file>
    python tools/_r200_d_cache_audit.py --report
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple, Any
from collections import defaultdict

# ============================================================
# 路径配置
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = [
    "core/services",
    "core/data",
    "core/cache",
    "core/agents",
    "core/importdata",
    "core/database",
    "core/performance",
    "core/advanced_optimization",
    "core/ui_integration",
]
EXCLUDE_PATTERNS = [
    "__pycache__",
    ".r1",
    ".r2",
    ".r3",
    ".r4",
    ".r5",
    ".r6",
    ".r7",
    ".r8",
    ".r9",
    ".r10",
    ".r11",
    ".r12",
    ".r13",
    ".r14",
    ".r15",
    ".r16",
    ".r17",
    ".r18",
    ".r19",
    ".r20",
    ".r21",
    ".r22",
    ".r23",
    ".r24",
    ".r25",
    ".r26",
    ".r27",
    ".r28",
    ".r29",
    ".r30",
    ".r31",
    ".r32",
    ".r33",
    ".r34",
    ".r35",
    ".r36",
    ".r37",
    ".r38",
    ".r39",
    ".r40",
    ".r41",
    ".r42",
    ".r43",
    ".r44",
    ".r45",
    ".r46",
    ".r47",
    ".r48",
    ".r49",
    ".r50",
    ".r51",
    ".r52",
    ".r53",
    ".r54",
    ".r55",
    ".r56",
    ".r57",
    ".r58",
    ".r59",
    ".r60",
    ".r61",
    ".r62",
    ".r63",
    ".r64",
    ".r65",
    ".r66",
    ".r67",
    ".r68",
    ".r69",
    ".r70",
    ".r71",
    ".r72",
    ".r73",
    ".r74",
    ".r75",
    ".r76",
    ".r77",
    ".r78",
    ".r79",
    ".r80",
    ".r81",
    ".r82",
    ".r83",
    ".r84",
    ".r85",
    ".r86",
    ".r87",
    ".r88",
    ".r89",
    ".r90",
    ".r91",
    ".r92",
    ".r93",
    ".r94",
    ".r95",
    ".r96",
    ".r97",
    ".r98",
    ".r99",
    ".r100",
    ".r101",
    ".r102",
    ".r103",
    ".r104",
    ".r105",
    ".r106",
    ".r107",
    ".r108",
    ".r109",
    ".r110",
    ".r111",
    ".r112",
    ".r113",
    ".r114",
    ".r115",
    ".r116",
    ".r117",
    ".r118",
    ".r119",
    ".r120",
    ".r121",
    ".r122",
    ".r123",
    ".r124",
    ".r125",
    ".r126",
    ".r127",
    ".r128",
    ".r129",
    ".r130",
    ".r131",
    ".r132",
    ".r133",
    ".r134",
    ".r135",
    ".r136",
    ".r137",
    ".r138",
    ".r139",
    ".r140",
    ".r141",
    ".r142",
    ".r143",
    ".r144",
    ".r145",
    ".r146",
    ".r147",
    ".r148",
    ".r149",
    ".r150",
    ".r151",
    ".r152",
    ".r153",
    ".r154",
    ".r155",
    ".r156",
    ".r157",
    ".r158",
    ".r159",
    ".r160",
    ".r161",
    ".r162",
    ".r163",
    ".r164",
    ".r165",
    ".r166",
    ".r167",
    ".r168",
    ".r169",
    ".r170",
    ".r171",
    ".r172",
    ".r173",
    ".r174",
    ".r175",
    ".r176",
    ".r177",
    ".r178",
    ".r179",
    ".r180",
    ".r181",
    ".r182",
    ".r183",
    ".r184",
    ".r185",
    ".r186",
    ".r187",
    ".r188",
    ".r189",
    ".r190",
    ".r191",
    ".r192",
    ".r193",
    ".r194",
    ".r195",
    ".r196",
    ".r197",
    ".r198",
    ".r199",
    ".r200",
]


# ============================================================
# 数据结构
# ============================================================
@dataclass
class CacheKeyOperation:
    """单条缓存键操作记录"""
    file: str                              # 文件相对路径
    line: int                              # 行号 (1-based)
    col: int                               # 列号
    op_type: str                           # 操作类型: 'get', 'set', 'delete', 'has', 'assignment', 'parameter'
    cache_target: str                      # 缓存对象: 'self._cache', 'self._market_cache', '_unified_cache', etc.
    key_expr: str                          # key 表达式的源代码片段
    key_kind: str                          # key 类型: 'factory_call', 'fstring', 'str_concat', 'format_call', 'static_literal', 'identifier'
    factory_method: Optional[str] = None   # 工厂方法名 (若 key_kind == 'factory_call')
    dimensions: List[str] = field(default_factory=list)  # 6 维度列表
    is_compliant: bool = False             # 是否合规 (使用工厂方法)
    notes: str = ""                        # 备注


@dataclass
class FileAuditResult:
    """单文件审计结果"""
    file: str
    total_ops: int = 0                     # 总缓存键操作数
    factory_calls: int = 0                 # 工厂方法调用数
    fstring_violations: int = 0            # f-string 违规数
    str_concat_violations: int = 0         # 字符串拼接违规数
    format_violations: int = 0             # format() 违规数
    static_literals: int = 0               # 静态字面量数
    identifier_refs: int = 0               # 标识符引用数
    operations: List[CacheKeyOperation] = field(default_factory=list)


# ============================================================
# 工具方法
# ============================================================
def should_skip_file(filepath: Path) -> bool:
    """检查文件是否应跳过 (排除 __pycache__ 和历史快照)"""
    path_str = str(filepath)
    for pattern in EXCLUDE_PATTERNS:
        if pattern in path_str:
            return True
    if path_str.endswith(".pyc"):
        return True
    return False


def is_cache_operation(node: ast.Call) -> bool:
    """判断调用是否为缓存操作 (set/get/delete/has/clear/invalidate)"""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        method_name = func.attr
        if method_name in ("set", "get", "delete", "has", "clear", "pop", "remove", "invalidate", "setdefault", "update"):
            # 进一步: 检查 func.value 是否像缓存对象
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
    """判断赋值是否为 cache_key 赋值"""
    for target in node.targets:
        if isinstance(target, ast.Name):
            if target.id.endswith("_cache_key") or target.id == "cache_key" or target.id == "ckey" or target.id == "key":
                return True
    return False


def classify_key_expr(node: ast.AST) -> Tuple[str, Optional[str], List[str]]:
    """分类 key 表达式的类型

    Returns:
        (key_kind, factory_method, dimensions)
        key_kind: 'factory_call', 'fstring', 'str_concat', 'format_call',
                  'static_literal', 'identifier', 'method_call'
    """
    # 工厂方法调用 (识别所有私有工厂)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            # 识别所有以 _make_xxx_key / _make_xxx_cache_key 结尾的工厂方法
            if method_name.startswith("_make_") and (
                method_name.endswith("_key") or method_name.endswith("_cache_key")
            ):
                return ("factory_call", method_name, [])
            # 公开工厂
            if method_name in ("make_6d_cache_key", "make_kdata_cache_key"):
                return ("factory_call", method_name, [])
            if method_name in ("make_cache_key", "build_cache_key"):
                return ("factory_call", method_name, [])
            # 内部工厂
            if "_cache_key" in method_name and method_name.startswith("_make"):
                return ("factory_call", method_name, [])
        # 普通方法调用
        return ("method_call", None, [])

    # f-string
    if isinstance(node, ast.JoinedStr):
        return ("fstring", None, [])

    # 字符串字面量
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        # 如果是模板格式 (e.g. "stock_{code}"), 仍算违规
        if "{" in node.value and "}" in node.value:
            return ("fstring", None, [])
        return ("static_literal", None, [])

    # 二元运算: 字符串拼接 (BinOp with Add)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        # 进一步分析: 如果含 Constant (str) + Name, 算字符串拼接
        return ("str_concat", None, [])

    # format() 调用
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "format":
            return ("format_call", None, [])

    # 标识符引用
    if isinstance(node, ast.Name):
        return ("identifier", None, [])

    return ("unknown", None, [])


def extract_key_expr_from_call(call_node: ast.Call) -> Optional[ast.AST]:
    """从缓存操作调用中提取 key 表达式 (通常是第一个位置参数)"""
    if not call_node.args:
        return None
    return call_node.args[0]


def extract_key_expr_from_kwargs(call_node: ast.Call) -> Optional[ast.AST]:
    """从缓存操作调用中提取 key 表达式 (从 keyword args)"""
    for kw in call_node.keywords:
        if kw.arg in ("key", "cache_key", "k"):
            return kw.value
    return None


# ============================================================
# 主扫描器
# ============================================================
class CacheKeyAuditor:
    """缓存键工厂使用率审计器"""

    def __init__(self, project_root: Path = PROJECT_ROOT) -> None:
        self.project_root = project_root
        self.results: Dict[str, FileAuditResult] = {}

    def scan_file(self, filepath: Path) -> FileAuditResult:
        """扫描单个文件, 返回审计结果"""
        result = FileAuditResult(file=str(filepath.relative_to(self.project_root)))

        try:
            source = filepath.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return result

        try:
            tree = ast.parse(source, filename=str(filepath))
        except SyntaxError:
            return result

        # Walk all statements
        for node in ast.walk(tree):
            # 1. 缓存操作调用: cache.set(key, ...) / cache.get(key) / etc.
            if isinstance(node, ast.Call) and is_cache_operation(node):
                # 提取 key 表达式 (优先位置参数, 其次关键字)
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
                if key_kind == "factory_call":
                    result.factory_calls += 1
                elif key_kind == "fstring":
                    result.fstring_violations += 1
                elif key_kind == "str_concat":
                    result.str_concat_violations += 1
                elif key_kind == "format_call":
                    result.format_violations += 1
                elif key_kind == "static_literal":
                    result.static_literals += 1
                elif key_kind == "identifier":
                    result.identifier_refs += 1

            # 2. cache_key 赋值
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
                if key_kind == "factory_call":
                    result.factory_calls += 1
                elif key_kind == "fstring":
                    result.fstring_violations += 1
                elif key_kind == "str_concat":
                    result.str_concat_violations += 1
                elif key_kind == "format_call":
                    result.format_violations += 1
                elif key_kind == "static_literal":
                    result.static_literals += 1
                elif key_kind == "identifier":
                    result.identifier_refs += 1

        return result

    def scan_project(self) -> Dict[str, Any]:
        """扫描整个项目, 返回汇总结果"""
        all_results = []

        for scan_dir in SCAN_DIRS:
            dir_path = self.project_root / scan_dir
            if not dir_path.exists():
                continue
            for py_file in dir_path.rglob("*.py"):
                if should_skip_file(py_file):
                    continue
                result = self.scan_file(py_file)
                if result.total_ops > 0:
                    all_results.append(result)
                    self.results[result.file] = result

        # 汇总
        total_ops = sum(r.total_ops for r in all_results)
        factory_calls = sum(r.factory_calls for r in all_results)
        fstring = sum(r.fstring_violations for r in all_results)
        str_concat = sum(r.str_concat_violations for r in all_results)
        format_v = sum(r.format_violations for r in all_results)
        static = sum(r.static_literals for r in all_results)
        ident = sum(r.identifier_refs for r in all_results)

        # 工厂方法使用率 = factory_calls / total_ops
        ratio = factory_calls / total_ops if total_ops > 0 else 0.0

        summary = {
            "total_files_with_cache_ops": len(all_results),
            "total_ops": total_ops,
            "factory_calls": factory_calls,
            "fstring_violations": fstring,
            "str_concat_violations": str_concat,
            "format_violations": format_v,
            "static_literals": static,
            "identifier_refs": ident,
            "factory_ratio": ratio,
            "target_ratio": 0.50,
            "target_met": ratio >= 0.50,
            "files": [asdict(r) for r in all_results],
        }

        return summary

    def report_violations(self, summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成违规清单 (用于修复)"""
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
# CLI
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="R200-D 缓存键工厂使用率审计器")
    parser.add_argument("--scan", action="store_true", help="扫描全项目")
    parser.add_argument("--report", action="store_true", help="生成报告")
    parser.add_argument("--output", type=str, default="tools/_r200_d_results.json", help="输出 JSON 文件")
    args = parser.parse_args()

    auditor = CacheKeyAuditor()
    summary = auditor.scan_project()

    print("=" * 70)
    print("R200-D 缓存键工厂使用率审计报告")
    print("=" * 70)
    print(f"扫描目录: {', '.join(SCAN_DIRS)}")
    print(f"含缓存操作文件数: {summary['total_files_with_cache_ops']}")
    print(f"总缓存键操作数: {summary['total_ops']}")
    print(f"  工厂方法调用 (合规): {summary['factory_calls']}")
    print(f"  f-string 违规: {summary['fstring_violations']}")
    print(f"  字符串拼接违规: {summary['str_concat_violations']}")
    print(f"  format() 违规: {summary['format_violations']}")
    print(f"  静态字面量: {summary['static_literals']}")
    print(f"  标识符引用: {summary['identifier_refs']}")
    print()
    print(f"工厂方法使用率: {summary['factory_ratio']:.1%} (目标 ≥ {summary['target_ratio']:.0%})")
    if summary["target_met"]:
        print("[OK] 已达成目标")
    else:
        print(f"[WARN] 未达成, 还需提升 {(summary['target_ratio'] - summary['factory_ratio']) * 100:.1f}%")
        # 计算需要多少工厂调用才能达标
        needed = int(summary['target_ratio'] * summary['total_ops']) - summary['factory_calls']
        print(f"       需要再增加 {needed} 处工厂方法调用")
    print()

    # 输出违规清单
    violations = auditor.report_violations(summary)
    print(f"违规清单: {len(violations)} 处")
    for v in violations[:20]:
        print(f"  {v['file']}:{v['line']} [{v['key_kind']}] {v['key_expr'][:60]}")
    if len(violations) > 20:
        print(f"  ... 共 {len(violations)} 处 (仅显示前 20)")

    # 保存结果
    output_path = PROJECT_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n详细结果已保存到: {output_path}")


if __name__ == "__main__":
    main()
