"""R181-C cache_key 6 维度铁律审计工具 (HVD-181-B, P0 修复 0.5d)

R9 §9.1 6 维度铁律: 缓存键必须含 6 维度
  at_code_period_count_adj_ds
  (asset_type + stock_code + period + count + adjustment + data_source)

R1 教训: 缺 data_source → 跨数据源假命中 → 用户看到错误数据

扫描规则 (R104 §12 5 铁律 100% 应用):
  1. 解析所有 .py 文件中的 `cache_key = ...` 赋值语句
  2. 检查 cache_key 字符串中是否含 6 维度关键字
  3. 标记缺失 data_source 维度的 cache_key (P0 候选)
  4. 输出 JSON 报告 (含行号 + 缺失维度 + 业务方)

白名单:
  - 静态资源类 (如 _ui_cache, _theme_cache) 不需 ds 维度
  - 用户/会话级 cache 不需 ds 维度
  - 业务方元数据 (strategy_id, user_id) 可不需 ds (但仍建议加)

用法:
  python tools/_r181_c_cache_key_audit.py --root . --output .r181_c_cache_key_audit.json
  python tools/_r181_c_cache_key_audit.py --root . --severity all
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple


# R9 §9.1 6 维度铁律关键字 (按权重排序)
DIMENSION_KEYWORDS = {
    "asset_type": ["asset_type", "at", "type"],
    "stock_code": ["stock_code", "code", "symbol", "ticker", "bond_code", "fund_code",
                    "index_code", "crypto_code", "futures_code", "user_id", "strategy_id",
                    "indicator_id", "selection_date", "params_hash"],
    "period": ["period", "timeframe", "interval", "freq"],
    "count": ["count", "limit", "n", "size", "time_range", "max_records"],
    "adjustment": ["adjustment", "adj"],
    "data_source": ["data_source", "ds", "source", "market"],
}

# 必须含 data_source 维度的 cache_key 前缀 (业务相关, R9 §9.1 强约束)
DATA_AWARE_PREFIXES = [
    "asset_list_", "stock_", "kdata_", "kline_", "financial_", "macro_",
    "market_", "index_", "bond_", "fund_", "crypto_", "futures_",
    "shares_data_", "search_", "stock_info_", "stock_list_",
    "fund_units_", "crypto_supply_", "futures_oi_", "index_mc_",
    "index_components_", "bond_info_", "fund_info_",
    # R181-C 新增
    "indicator_", "chart_", "performance_", "selection_",
    "recommendation_", "ai_selection_",
]

# 白名单: 静态/UI 缓存不需要 ds 维度
WHITELIST_KEYWORDS = [
    "_ui_cache", "theme_", "ui_state_", "config_", "setting_",
    "_layout", "widget_", "qt_", "qss_", "css_", "i18n_",
    "translation_", "dict_", "mapping_", "table_schema_",
    "_log_cache", "debug_", "trace_",
    # R181-C 新增: 已知非数据缓存误报
    "_singleton",  # manager_factory 单例标识 (非数据缓存)
    "_id_cache",   # Python id() 调用结果 (非数据缓存)
]


# 已知误报模式 (正则): 满足这些模式的 cache_key 即使缺 ds 也视为白名单
WHITELIST_PATTERNS = [
    re.compile(r"^\s*id\(\s*\w+\s*\)\s*$"),  # cache_key = id(some_var) (Python id() 调用)
    re.compile(r"^'?\w*singleton\w*'?$"),     # 'performance_monitor_singleton' 形式
    re.compile(r'^\s*self\._generate_cache_key\('),  # factory 方法 (内部已含 ds)
]


@dataclass
class CacheKeyViolation:
    """cache_key 缺失维度违规报告."""
    file: str
    line: int
    func_name: str
    cache_key_expr: str
    missing_dimensions: List[str]
    has_data_source: bool
    severity: str  # P0 / P1 / P2 / OK
    matched_prefix: Optional[str] = None
    business_callers: int = 0
    note: str = ""


def is_data_aware_key(key_expr: str) -> Tuple[bool, Optional[str]]:
    """判断 cache_key 是否为业务数据相关 (需含 ds 维度)."""
    for prefix in DATA_AWARE_PREFIXES:
        if prefix in key_expr:
            return True, prefix
    return False, None


def is_whitelist_key(key_expr: str) -> bool:
    """判断 cache_key 是否在白名单内."""
    for kw in WHITELIST_KEYWORDS:
        if kw in key_expr:
            return True
    return False


def extract_cache_key_string(node: ast.AST) -> Optional[str]:
    """从 cache_key 赋值节点的 RHS 提取字符串内容."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        # f-string: 拼接所有 parts
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            elif isinstance(v, ast.FormattedValue):
                # 尝试从 value 提取名称
                val = v.value
                if isinstance(val, ast.Name):
                    parts.append("{" + val.id + "}")
                elif isinstance(val, ast.Attribute):
                    parts.append("{" + ast.unparse(val) + "}")
                else:
                    parts.append("{?}")
        return "".join(parts)
    if isinstance(node, ast.Call):
        # 函数调用: e.g. self._make_xxx_cache_key(...)
        return ast.unparse(node)
    return None


def check_dimensions(key_expr: str) -> Dict[str, bool]:
    """检查 cache_key 字符串是否含 6 维度关键字."""
    result = {dim: False for dim in DIMENSION_KEYWORDS}
    key_lower = key_expr.lower()
    for dim, keywords in DIMENSION_KEYWORDS.items():
        for kw in keywords:
            if kw in key_lower:
                result[dim] = True
                break
    return result


def get_enclosing_function(tree: ast.AST, target_lineno: int) -> Optional[str]:
    """查找包含目标行号的最近函数定义."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= target_lineno <= (node.end_lineno or target_lineno):
                return node.name
    return None


def find_cache_key_assignments(tree: ast.Module) -> List[Tuple[int, str, ast.AST]]:
    """扫描所有 cache_key = ... 赋值语句, 返回 (行号, 函数名, RHS 节点)."""
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "cache_key":
                    rhs = node.value
                    func_name = get_enclosing_function(tree, node.lineno)
                    results.append((node.lineno, func_name or "<module>", rhs))
    return results


def analyze_file(filepath: Path, root: Path) -> List[CacheKeyViolation]:
    """分析单个 .py 文件的 cache_key 违规情况."""
    violations = []
    try:
        source = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        try:
            source = filepath.read_text(encoding="gbk")
        except Exception:
            return []
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    for lineno, func_name, rhs in find_cache_key_assignments(tree):
        key_str = extract_cache_key_string(rhs)
        if not key_str:
            continue
        # 白名单过滤
        if is_whitelist_key(key_str):
            continue
        # R181-C 新增: 正则白名单 (id() 调用, singleton 键, factory 方法)
        if any(p.match(key_str) for p in WHITELIST_PATTERNS):
            continue
        # 仅审计业务数据相关 cache_key
        is_data_aware, matched_prefix = is_data_aware_key(key_str)
        if not is_data_aware:
            continue
        # 工厂方法调用: self._make_xxx_cache_key(...) 视为 OK (R9 §9.1 铁律 #2)
        if "cache_key(" in key_str and "_make_" in key_str:
            continue
        # 检查维度
        dims = check_dimensions(key_str)
        missing = [d for d, has in dims.items() if not has]
        # 关键判定: data_source 缺失 → P0
        if not dims["data_source"]:
            violations.append(CacheKeyViolation(
                file=str(filepath.relative_to(root)),
                line=lineno,
                func_name=func_name,
                cache_key_expr=key_str[:200],
                missing_dimensions=missing,
                has_data_source=False,
                severity="P0",
                matched_prefix=matched_prefix,
                note="缺 data_source 维度, R1 教训: 跨数据源假命中",
            ))
        elif missing:
            violations.append(CacheKeyViolation(
                file=str(filepath.relative_to(root)),
                line=lineno,
                func_name=func_name,
                cache_key_expr=key_str[:200],
                missing_dimensions=missing,
                has_data_source=True,
                severity="P2",
                matched_prefix=matched_prefix,
                note=f"含 ds, 但缺 {','.join(missing)}",
            ))
    return violations


def main():
    import argparse
    parser = argparse.ArgumentParser(description="R181-C cache_key 6 维度铁律审计工具")
    parser.add_argument("--root", default=".", help="项目根目录")
    parser.add_argument("--output", default=".r181_c_cache_key_audit.json", help="JSON 报告输出路径")
    parser.add_argument("--severity", default="P0", choices=["P0", "P1", "P2", "all"],
                        help="最低严重性级别")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"ERROR: root 目录不存在: {root}", file=sys.stderr)
        sys.exit(1)

    skip_dirs = {"__pycache__", ".git", ".pytest_cache", ".cache", "node_modules",
                 ".codegraph", ".mypy_cache", ".trae", "node_modules", "dist", "build",
                 "_archive"}  # R181-C: 跳过 _archive/ 预修复备份
    all_violations: List[CacheKeyViolation] = []
    files_scanned = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            fp = Path(dirpath) / fn
            files_scanned += 1
            all_violations.extend(analyze_file(fp, root))

    # 严重性过滤
    sev_order = {"P0": 0, "P1": 1, "P2": 2, "OK": 3}
    min_sev = -1 if args.severity == "all" else sev_order.get(args.severity, 0)
    if min_sev >= 0:
        all_violations = [v for v in all_violations if sev_order.get(v.severity, 99) <= min_sev]

    # 统计
    by_file: Dict[str, List[CacheKeyViolation]] = {}
    for v in all_violations:
        by_file.setdefault(v.file, []).append(v)

    report = {
        "scan_root": str(root),
        "files_scanned": files_scanned,
        "total_violations": len(all_violations),
        "by_severity": {
            sev: sum(1 for v in all_violations if v.severity == sev)
            for sev in ["P0", "P1", "P2", "OK"]
        },
        "by_file_count": {f: len(vs) for f, vs in sorted(by_file.items())},
        "violations": [asdict(v) for v in all_violations],
    }

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[R181-C] 扫描完成: {files_scanned} 文件, {len(all_violations)} 处违规")
    print(f"[R181-C] 报告输出: {out_path}")
    print(f"[R181-C] 严重性统计: {report['by_severity']}")
    print(f"[R181-C] 前 10 个违规文件:")
    for f, cnt in list(report["by_file_count"].items())[:10]:
        print(f"  {f}: {cnt} 处")


if __name__ == "__main__":
    main()
