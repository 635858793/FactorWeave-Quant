"""
R159-B 子智能体扫描器 v3: order_executor.py logger.exc_info 全量扫描
按 R158-D 报告的 57 处口径,扫描所有 logger.error/critical 缺 exc_info=True
"""
import ast
import os
import sys
from typing import List, Dict, Any, Set, Tuple

FILE_PATH = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\trading\order_executor.py"


class FullLoggerScanner:
    """
    全量扫描:
    - 所有 logger.error / logger.critical / logger.warning / logger.exception
    - 不论是否在 except 块
    - 标记是否含 exc_info=True
    - 标记是否在 except 块 (R51 铁律 #5 强约束)
    """

    def __init__(self, source: str):
        self.source = source
        self.lines = source.splitlines()
        self.findings: List[Dict[str, Any]] = []
        self._method_stack: List[Tuple[ast.AST, str]] = []
        self._class_stack: List[Tuple[ast.AST, str]] = []

    def _current_method(self) -> str:
        return self._method_stack[-1][1] if self._method_stack else "<module>"

    def _current_class(self) -> str:
        return ".".join(c[1] for c in self._class_stack) if self._class_stack else "<module>"

    def scan(self, tree: ast.AST):
        self._visit(tree, in_except=0)

    def _visit(self, node: ast.AST, in_except: int):
        if isinstance(node, ast.ClassDef):
            self._class_stack.append((node, node.name))
            for stmt in node.body:
                self._visit(stmt, in_except)
            self._class_stack.pop()
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._method_stack.append((node, node.name))
            for stmt in node.body:
                self._visit(stmt, in_except)
            self._method_stack.pop()
        elif isinstance(node, ast.Try):
            for stmt in node.body:
                self._visit(stmt, in_except)
            for handler in node.handlers:
                for stmt in handler.body:
                    self._visit(stmt, in_except + 1)
            for stmt in node.orelse:
                self._visit(stmt, in_except)
            for stmt in node.finalbody:
                self._visit(stmt, in_except)
        elif isinstance(node, ast.If):
            for stmt in node.body:
                self._visit(stmt, in_except)
            for stmt in node.orelse:
                self._visit(stmt, in_except)
        elif isinstance(node, (ast.For, ast.While)):
            for stmt in node.body:
                self._visit(stmt, in_except)
            for stmt in node.orelse:
                self._visit(stmt, in_except)
        elif isinstance(node, ast.With):
            for stmt in node.body:
                self._visit(stmt, in_except)
        elif isinstance(node, ast.Call):
            self._check_logger_call(node, in_except)
            for arg in node.args:
                self._visit(arg, in_except)
            for kw in node.keywords:
                self._visit(kw.value, in_except)
        else:
            for child in ast.iter_child_nodes(node):
                self._visit(child, in_except)

    def _check_logger_call(self, node: ast.Call, in_except: int):
        if not isinstance(node.func, ast.Attribute):
            return
        method_name = node.func.attr
        if method_name not in ("error", "critical", "exception", "warning"):
            return
        if isinstance(node.func.value, ast.Name):
            if node.func.value.id != "logger":
                return
        else:
            return

        has_exc_info = self._has_exc_info_kwarg(node)
        finding = {
            "line": node.lineno,
            "col": node.col_offset,
            "method_call": f"logger.{method_name}",
            "parent_method": self._current_method(),
            "parent_class": self._current_class(),
            "in_except": in_except > 0,
            "has_exc_info": has_exc_info,
            "source_line": self.lines[node.lineno - 1] if node.lineno <= len(self.lines) else "",
        }
        self.findings.append(finding)

    def _has_exc_info_kwarg(self, node: ast.Call) -> bool:
        for kw in node.keywords:
            if kw.arg == "exc_info":
                return True
        return False


def scan():
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    scanner = FullLoggerScanner(source)
    scanner.scan(tree)

    all_findings = scanner.findings

    # 按 R158-D 报告口径: logger.error/critical 缺 exc_info=True
    error_critical_no_exc = [f for f in all_findings
                              if f["method_call"] in ("logger.error", "logger.critical")
                              and not f["has_exc_info"]]

    # 按 R51 铁律 #5 口径: except 块内 logger.X 缺 exc_info=True
    except_no_exc = [f for f in all_findings
                      if f["in_except"] and not f["has_exc_info"]]

    print("=" * 80)
    print(f"扫描文件: {FILE_PATH}")
    print(f"文件总行数: {len(source.splitlines())}")
    print("=" * 80)
    print()
    print("## 全量总览 (R158-D 报告口径)")
    print(f"- logger.X 总调用数: {len(all_findings)}")
    print(f"  - logger.error: {sum(1 for f in all_findings if f['method_call'] == 'logger.error')}")
    print(f"  - logger.critical: {sum(1 for f in all_findings if f['method_call'] == 'logger.critical')}")
    print(f"  - logger.warning: {sum(1 for f in all_findings if f['method_call'] == 'logger.warning')}")
    print(f"  - logger.exception: {sum(1 for f in all_findings if f['method_call'] == 'logger.exception')}")
    print()
    print(f"## R158-D 报告口径: logger.error/critical 缺 exc_info=True ({len(error_critical_no_exc)} 处)")
    print(f"  - 在 except 块内: {sum(1 for f in error_critical_no_exc if f['in_except'])}")
    print(f"  - 不在 except 块: {sum(1 for f in error_critical_no_exc if not f['in_except'])}")
    print()
    print(f"## R51 铁律 #5 口径: except 块内 logger.X 缺 exc_info=True ({len(except_no_exc)} 处)")
    print()

    # 按方法 + 是否在 except 块分类
    print("=" * 80)
    print(f"## R158-D 报告口径 全部 {len(error_critical_no_exc)} 处清单 (按行号排序)")
    print("=" * 80)
    sorted_findings = sorted(error_critical_no_exc, key=lambda f: f["line"])
    for f in sorted_findings:
        exc_mark = "[IN_EXCEPT]" if f["in_except"] else "[NOT_EXCEPT]"
        print(f"  L{f['line']:>5} {exc_mark:<12} {f['parent_class']}.{f['parent_method']:>30} | {f['method_call']:>20}")
        src = f["source_line"].strip()
        if len(src) > 110:
            src = src[:110] + "..."
        print(f"          > {src}")
    print()

    # 按 parent_method 聚合
    print("=" * 80)
    print("## R158-D 漏修按 parent_method 聚合 (R150 keyword 模式消歧)")
    print("=" * 80)
    by_method: Dict[str, List[Dict[str, Any]]] = {}
    for f in error_critical_no_exc:
        key = f"{f['parent_class']}.{f['parent_method']}"
        by_method.setdefault(key, []).append(f)
    for method, findings in sorted(by_method.items()):
        exc_count = sum(1 for f in findings if f["in_except"])
        not_exc_count = sum(1 for f in findings if not f["in_except"])
        print(f"  {method}: {len(findings)} 处 (in_except={exc_count}, not_except={not_exc_count})")
    print()

    # 写入 JSON
    import json
    out_path = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tests\_r159_b_scan_v3.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "file": FILE_PATH,
            "all_findings_count": len(all_findings),
            "r158_d_口径": len(error_critical_no_exc),
            "r158_d_in_except": sum(1 for f in error_critical_no_exc if f["in_except"]),
            "r158_d_not_in_except": sum(1 for f in error_critical_no_exc if not f["in_except"]),
            "r51_铁律5_口径": len(except_no_exc),
            "error_critical_no_exc": error_critical_no_exc,
            "except_no_exc": except_no_exc,
        }, f, ensure_ascii=False, indent=2)
    print(f"JSON 报告已写入: {out_path}")


if __name__ == "__main__":
    scan()
