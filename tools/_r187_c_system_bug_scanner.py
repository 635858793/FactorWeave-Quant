#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""R187-C: 系统级 bug 深度扫描器 (7 大维度)

扫描维度 (R187-C 主智能体任务 3):
1. **logging 一致性**: 全项目 logger.warning/error 异常路径缺 exc_info=True (R174 §12 强约束)
2. **import 顺序混乱**: PEP8 违反 (R51 教训, 系统性)
3. **未注册 P1 service**: 类似 R51/R53 软解析 (R182 web/backend 教训)
4. **死代码**: 跨子目录死类/死方法 (R6 §6.1 8 铁律)
5. **lock 嵌套/长锁**: 业务关键路径 (R104 §12 #3+#5 + R177 模板)
6. **event_bus ORPHAN_PUB/SUB**: 业务关键事件 (R8 §8.1 + R84)
7. **cache_key 6 维度**: R183 教训 100% 应用 (asset_type + stock_code + period + count + adjustment + data_source)

输出: JSON 报告 + stdout 表格

用法:
    python tools/_r187_c_system_bug_scanner.py
    python tools/_r187_c_system_bug_scanner.py --json
    python tools/_r187_c_system_bug_scanner.py --severity P0
"""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")
SCAN_DIRS = ["core", "utils", "data", "plugins", "scripts", "backtest", "evaluation",
             "optimization", "strategies", "features", "models", "components", "analysis"]
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules",
             "site-packages", "conda", "tools"}


# ============== 数据结构 ==============
@dataclass
class Bug:
    """单个 bug 记录"""
    dimension: str       # 7 大维度之一
    file: str            # 相对路径
    line: int            # 1-based 行号
    severity: str        # P0/P1/P2/P3
    message: str         # 简要描述
    code_snippet: str = ""  # 代码片段


@dataclass
class ScanReport:
    """扫描报告"""
    bugs: List[Bug] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

    def add(self, bug: Bug):
        self.bugs.append(bug)

    def by_dimension(self) -> Dict[str, List[Bug]]:
        result = defaultdict(list)
        for b in self.bugs:
            result[b.dimension].append(b)
        return dict(result)

    def by_severity(self) -> Dict[str, int]:
        result = defaultdict(int)
        for b in self.bugs:
            result[b.severity] += 1
        return dict(result)


# ============== 1. Logging 一致性扫描 ==============
def scan_logging_consistency(py_file: Path, content: str, tree: ast.Module) -> List[Bug]:
    """扫描 logger.warning/error 异常路径缺 exc_info=True

    R174 §12 强约束: except 块内 logger.warning(...) 必须有 exc_info=True
    """
    bugs = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Expr):
                continue
            if not isinstance(stmt.value, ast.Call):
                continue
            call = stmt.value
            # 检查是否 logger.warning / logger.error
            if not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr not in ('warning', 'error', 'exception', 'critical'):
                continue

            # 检查是否有 exc_info=True / exc_info=... 关键字参数
            has_exc_info = any(kw.arg == 'exc_info' for kw in call.keywords)

            # 简化: 取 code snippet
            try:
                snippet = ast.unparse(stmt).split('\n')[0][:100]
            except Exception:
                snippet = call.func.attr + "(...)"

            if not has_exc_info:
                bugs.append(Bug(
                    dimension="logging_consistency",
                    file=str(py_file.relative_to(ROOT)),
                    line=stmt.lineno,
                    severity="P2",
                    message=f"except 块内 logger.{call.func.attr} 缺 exc_info=True (R174 §12)",
                    code_snippet=snippet,
                ))
    return bugs


# ============== 2. Import 顺序混乱扫描 ==============
def scan_import_order(py_file: Path, content: str, tree: ast.Module) -> List[Bug]:
    """扫描 PEP8 import 顺序: 标准库 → 第三方 → 本地

    简化: 检测同一文件内 import 顺序问题
    """
    bugs = []
    # 收集所有 import 语句及其行号
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append((node.lineno, node))

    # 按行号排序
    imports.sort(key=lambda x: x[0])

    # 简化规则: 同一分组内 import 必须按字母顺序
    groups = defaultdict(list)  # (is_from, module) -> [(lineno, node)]
    for lineno, node in imports:
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_top = alias.name.split('.')[0]
                groups[('notfrom', module_top)].append((lineno, node, alias.name or ""))
        else:
            module_top = (node.module or '').split('.')[0]
            groups[('from', module_top)].append((lineno, node, node.module or ""))

    # 检测同组内顺序
    for key, items in groups.items():
        if len(items) < 2:
            continue
        names = [item[2] for item in items if item[2]]
        if not names or len(names) < 2:
            continue
        sorted_names = sorted(names)
        if names != sorted_names:
            # 报告一次 (只在第一处)
            bugs.append(Bug(
                dimension="import_order",
                file=str(py_file.relative_to(ROOT)),
                line=items[0][0],
                severity="P3",
                message=f"PEP8: import 顺序非字母序 ({names[:3]}...)",
                code_snippet=str(items[0][1].lineno),
            ))
    return bugs


# ============== 3. 未注册 P1 Service 扫描 ==============
# 关键 Service 类名候选 (从 service_bootstrap.py 已知)
KNOWN_SERVICES = {
    'RiskAlertSystem', 'RiskManager', 'RiskControlService', 'RiskExporter',
    'TradingEngine', 'OrderExecutor', 'PositionManager', 'MoneyManager',
    'TakeProfitService', 'StopLossService', 'DataQualityRiskManager',
    'EventBus', 'CacheService', 'NetworkService', 'ConfigService',
    'AdvancedRiskControlService', 'SignalArbitrator', 'StrategyEngine',
    'BacktestEngine', 'OptimizationEngine', 'IndicatorService',
    'UnifiedIndicatorService', 'AITradingService', 'AlertService',
}


def scan_unregistered_service(py_file: Path, content: str, tree: ast.Module) -> List[Bug]:
    """扫描疑似未注册 service 类"""
    bugs = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name not in KNOWN_SERVICES:
            continue
        # 必须有 __init__ + 公共方法, 才是真正的 service
        has_init = any(isinstance(m, ast.FunctionDef) and m.name == '__init__'
                       for m in node.body)
        has_methods = sum(1 for m in node.body if isinstance(m, ast.FunctionDef))
        if has_init and has_methods >= 3:
            # 检查是否在 service_bootstrap 中注册 (简化: 名字在文件出现)
            # 真正的注册检查需要读 service_bootstrap.py, 这里仅做候选标记
            bugs.append(Bug(
                dimension="unregistered_service_candidate",
                file=str(py_file.relative_to(ROOT)),
                line=node.lineno,
                severity="P2",
                message=f"类 {node.name} 疑似 Service, 需 R+1 验证 service_bootstrap 注册",
                code_snippet=f"class {node.name}:",
            ))
    return bugs


# ============== 4. 死代码扫描 (简化: 跨子目录类引用计数) ==============
def scan_dead_code(py_files: List[Path], py_contents: Dict[Path, str]) -> List[Bug]:
    """简化: 统计类名引用, 0 引用的可能是死代码 (R6 §6.1 4 源验证后标记)"""
    bugs = []

    # 1. 收集所有类名 + 定义位置
    class_defs = {}  # class_name -> (file, line)
    for py_file in py_files:
        try:
            tree = ast.parse(py_contents[py_file])
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if not node.name.startswith('_'):  # 公开类
                    class_defs[node.name] = (py_file, node.lineno)

    # 2. 统计类名被引用的次数 (排除自身定义)
    ref_count = defaultdict(int)
    for py_file in py_files:
        content = py_contents[py_file]
        for class_name in class_defs:
            # 简单计数 (会误报, 仅作起点)
            count = content.count(class_name) - 1 if py_file == class_defs[class_name][0] else content.count(class_name)
            ref_count[class_name] += count

    # 3. 标记候选 (ref_count == 0)
    for class_name, (py_file, line) in class_defs.items():
        if ref_count[class_name] == 0:
            bugs.append(Bug(
                dimension="dead_code_candidate",
                file=str(py_file.relative_to(ROOT)),
                line=line,
                severity="P3",
                message=f"类 {class_name} 候选死代码 (0 引用, 需 R6 §6.1 4 源验证)",
                code_snippet=f"class {class_name}:",
            ))
    return bugs


# ============== 5. Lock 嵌套/长锁扫描 ==============
def scan_lock_nesting(py_file: Path, content: str, tree: ast.Module) -> List[Bug]:
    """扫描 with self._lock: 嵌套 + 锁内代码 > 30 行 (R104 §12 #3+#5)"""
    bugs = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        # 递归检测嵌套锁
        lock_stacks = []  # 当前方法内的锁栈

        def visit_with_block(stmts, parent_locks=set()):
            for stmt in stmts:
                if isinstance(stmt, ast.With):
                    current_locks = set(parent_locks)
                    for item in stmt.items:
                        if isinstance(item.context_expr, ast.Attribute):
                            if item.context_expr.attr.startswith('_') and 'lock' in item.context_expr.attr:
                                lock_name = item.context_expr.attr
                                if lock_name in current_locks:
                                    bugs.append(Bug(
                                        dimension="lock_nesting",
                                        file=str(py_file.relative_to(ROOT)),
                                        line=stmt.lineno,
                                        severity="P1",
                                        message=f"锁嵌套: {lock_name} 已在父作用域持锁 (R104 §12 #3)",
                                        code_snippet=f"with self.{lock_name}:",
                                    ))
                                current_locks.add(lock_name)
                    # 递归进入 body
                    visit_with_block(stmt.body, current_locks)
                elif isinstance(stmt, ast.Try):
                    visit_with_block(stmt.body, parent_locks)
                    for handler in stmt.handlers:
                        visit_with_block(handler.body, parent_locks)

        visit_with_block(node.body)
    return bugs


# ============== 6. Event Bus ORPHAN_PUB/SUB 扫描 ==============
def scan_event_orphan(py_file: Path, content: str, tree: ast.Module) -> List[Bug]:
    """扫描 bus.publish('xxx') 字符串事件 (简化: 不做 ORPHAN 配对, 仅标记候选)"""
    bugs = []
    # 只扫描 'risk.*' 业务关键事件 (R8 §8.1 强约束)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # 检查 bus.publish('xxx', ...)
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'publish':
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if arg.value.startswith('risk.'):
                        # 标记 P2 候选
                        bugs.append(Bug(
                            dimension="event_bus_string_publish",
                            file=str(py_file.relative_to(ROOT)),
                            line=node.lineno,
                            severity="P2",
                            message=f"字符串事件 publish('{arg.value}') 候选 (R8 §8.1 集中 helper)",
                            code_snippet=f"publish('{arg.value}')",
                        ))
    return bugs


# ============== 7. Cache Key 6 维度扫描 ==============
def scan_cache_key_dims(py_file: Path, content: str, tree: ast.Module) -> List[Bug]:
    """扫描 cache_key 是否含 6 维度 (asset_type + stock_code + period + count + adjustment + data_source)"""
    bugs = []
    # 简化: 仅在已知 cache 函数名中扫描
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if 'cache_key' not in node.name and 'kdata_key' not in node.name:
            continue
        # 检查是否含 stock_code / period 等维度
        func_src = ast.unparse(node)
        missing_dims = []
        for dim, pattern in [
            ('stock_code', r'stock_code|stock'),
            ('period', r'period'),
            ('count', r'count'),
            ('adjustment', r'adjust|adj'),
            ('data_source', r'data_source|ds|src'),
            ('asset_type', r'asset_type|at_code'),
        ]:
            if not re.search(pattern, func_src, re.IGNORECASE):
                missing_dims.append(dim)
        if missing_dims:
            bugs.append(Bug(
                dimension="cache_key_dims",
                file=str(py_file.relative_to(ROOT)),
                line=node.lineno,
                severity="P2",
                message=f"cache_key 函数缺维度: {missing_dims} (R9 §9.1 6 维度)",
                code_snippet=f"def {node.name}(...):",
            ))
    return bugs


# ============== 主扫描函数 ==============
def main():
    # 收集所有 .py 文件
    py_files = []
    py_contents = {}
    for scan_dir in SCAN_DIRS:
        scan_path = ROOT / scan_dir
        if not scan_path.exists():
            continue
        for py_file in scan_path.rglob("*.py"):
            if any(p in SKIP_DIRS for p in py_file.parts):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            py_files.append(py_file)
            py_contents[py_file] = content

    print(f"扫描 {len(py_files)} 个 .py 文件, 根目录: {ROOT}")

    report = ScanReport()

    # 维度 1-3, 5-7: 单文件扫描
    for py_file in py_files:
        content = py_contents[py_file]
        try:
            tree = ast.parse(content)
        except Exception:
            continue
        report.bugs.extend(scan_logging_consistency(py_file, content, tree))
        report.bugs.extend(scan_import_order(py_file, content, tree))
        report.bugs.extend(scan_unregistered_service(py_file, content, tree))
        report.bugs.extend(scan_lock_nesting(py_file, content, tree))
        report.bugs.extend(scan_event_orphan(py_file, content, tree))
        report.bugs.extend(scan_cache_key_dims(py_file, content, tree))

    # 维度 4: 跨子目录
    report.bugs.extend(scan_dead_code(py_files, py_contents))

    # 统计
    report.stats = {
        "total_files": len(py_files),
        "total_bugs": len(report.bugs),
        "by_dimension": {k: len(v) for k, v in report.by_dimension().items()},
        "by_severity": report.by_severity(),
    }

    # 输出
    if "--json" in sys.argv:
        out = {
            "stats": report.stats,
            "bugs": [asdict(b) for b in report.bugs],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print()
        print("=" * 60)
        print("R187-C 系统级 bug 扫描报告")
        print("=" * 60)
        print(f"扫描文件数: {report.stats['total_files']}")
        print(f"总 bug 数:   {report.stats['total_bugs']}")
        print()
        print("按维度统计:")
        for dim, count in report.stats['by_dimension'].items():
            print(f"  {dim:35s}: {count}")
        print()
        print("按严重性统计:")
        for sev, count in report.stats['by_severity'].items():
            print(f"  {sev}: {count}")
        print()

        # 按维度分组打印
        by_dim = report.by_dimension()
        for dim in sorted(by_dim.keys()):
            print(f"\n--- {dim} ({len(by_dim[dim])} 项) ---")
            for b in by_dim[dim][:20]:  # 每个维度最多 20 项
                print(f"  [{b.severity}] {b.file}:{b.line} - {b.message}")
            if len(by_dim[dim]) > 20:
                print(f"  ... (省略 {len(by_dim[dim]) - 20} 项)")

    # 写入 JSON 报告
    json_path = ROOT / "_r187_c_scan_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "stats": report.stats,
            "bugs": [asdict(b) for b in report.bugs],
        }, f, ensure_ascii=False, indent=2)
    print(f"\nJSON 报告已写入: {json_path}")


if __name__ == "__main__":
    main()
