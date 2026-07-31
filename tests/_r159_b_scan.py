"""
R159-B 子智能体扫描器 v2: order_executor.py logger.exc_info 缺漏修扫描
R104 §12 5 铁律: AST 递归 with.body 嵌套检测
R150 keyword 模式: TDD 用 keyword + parent_method 消歧
R51 铁律 #5: logger.error/critical 必须 exc_info=True (except 块内)
"""
import ast
import os
import sys
from typing import List, Dict, Any, Set, Tuple

FILE_PATH = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\trading\order_executor.py"


class LoggerExcInfoScanner:
    """
    扫描类:
    - 找到所有 logger.error / logger.critical / logger.exception 调用
    - 记录是否在 except 块内 (R51 铁律 #5)
    - 检查是否含 exc_info=True keyword
    - 记录方法名 (parent_method) 用于消歧
    """

    def __init__(self, source: str):
        self.source = source
        self.lines = source.splitlines()
        self.findings: List[Dict[str, Any]] = []
        # 用节点 ID 跟踪 (避免 name 冲突, 例如嵌套函数)
        self._method_stack: List[Tuple[ast.AST, str]] = []
        self._class_stack: List[Tuple[ast.AST, str]] = []
        # 每个 AST 节点 -> 标记其是否在 except 块内
        self._except_flag_stack: List[int] = []  # 计数器, 表示当前栈深度下 in_except 状态

    def _current_method(self) -> str:
        return self._method_stack[-1][1] if self._method_stack else "<module>"

    def _current_class(self) -> str:
        return ".".join(c[1] for c in self._class_stack) if self._class_stack else "<module>"

    def _in_except(self) -> bool:
        return any(d > 0 for d in self._except_flag_stack)

    def scan(self, tree: ast.AST):
        self._visit(tree, in_except=0)

    def _visit(self, node: ast.AST, in_except: int):
        """递归访问, 传递 in_except 标记"""
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
            # 访问 try.body
            for stmt in node.body:
                self._visit(stmt, in_except)
            # 访问 except 块 (in_except + 1)
            for handler in node.handlers:
                for stmt in handler.body:
                    self._visit(stmt, in_except + 1)
            # orelse / finalbody 仍按当前 in_except
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
            # 继续访问子节点 (因为 logger.X(Y) 中 Y 可能含 logger call, 但我们只关心顶层)
            for arg in node.args:
                self._visit(arg, in_except)
            for kw in node.keywords:
                self._visit(kw.value, in_except)
        else:
            # 默认: 递归访问子节点
            for child in ast.iter_child_nodes(node):
                self._visit(child, in_except)

    def _check_logger_call(self, node: ast.Call, in_except: int):
        if not isinstance(node.func, ast.Attribute):
            return
        method_name = node.func.attr
        if method_name not in ("error", "critical", "exception", "warning"):
            return
        # 验证 func.value 是 'logger' 或 self.logger
        if isinstance(node.func.value, ast.Name):
            if node.func.value.id != "logger":
                return
        else:
            return  # 仅处理模块级 logger 顶级引用

        has_exc_info = self._has_exc_info_kwarg(node)
        finding = {
            "line": node.lineno,
            "col": node.col_offset,
            "method_call": f"logger.{method_name}",
            "parent_method": self._current_method(),
            "parent_class": self._current_class(),
            "in_except": in_except > 0,
            "except_depth": in_except,
            "has_exc_info": has_exc_info,
            "args_count": len(node.args),
            "kwargs": [k.arg for k in node.keywords],
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
    scanner = LoggerExcInfoScanner(source)
    scanner.scan(tree)

    all_findings = scanner.findings
    in_except_findings = [f for f in all_findings if f["in_except"]]
    no_exc_info_findings = [f for f in in_except_findings if not f["has_exc_info"]]
    with_exc_info_findings = [f for f in in_except_findings if f["has_exc_info"]]
    not_in_except_findings = [f for f in all_findings if not f["in_except"]]

    print("=" * 80)
    print(f"扫描文件: {FILE_PATH}")
    print(f"文件总行数: {len(source.splitlines())}")
    print("=" * 80)
    print()
    print(f"## 总览")
    print(f"- logger.X 调用总数: {len(all_findings)}")
    print(f"  - in except 块: {len(in_except_findings)}")
    print(f"    - 已含 exc_info=True: {len(with_exc_info_findings)}")
    print(f"    - 缺 exc_info=True (R51 铁律 #5 违规): {len(no_exc_info_findings)}")
    print(f"  - 不在 except 块: {len(not_in_except_findings)}")
    print()

    print("=" * 80)
    print(f"## R51 铁律 #5 违规: except 块内 logger.X 无 exc_info=True ({len(no_exc_info_findings)} 处)")
    print("=" * 80)
    for f in no_exc_info_findings:
        print(f"  L{f['line']:>5} {f['parent_class']}.{f['parent_method']:>30} | {f['method_call']:>20} | kwargs={f['kwargs']}")
        src = f["source_line"].strip()
        if len(src) > 130:
            src = src[:130] + "..."
        print(f"          > {src}")
    print()

    print("=" * 80)
    print(f"## R51 已合规: except 块内 logger.X 含 exc_info=True ({len(with_exc_info_findings)} 处)")
    print("=" * 80)
    for f in with_exc_info_findings:
        print(f"  L{f['line']:>5} {f['parent_class']}.{f['parent_method']:>30} | {f['method_call']:>20} | kwargs={f['kwargs']}")
    print()

    print("=" * 80)
    print(f"## 非 except 块的 logger.X 调用 (供参考, R51 不强制) ({len(not_in_except_findings)} 处)")
    print("=" * 80)
    for f in not_in_except_findings:
        print(f"  L{f['line']:>5} {f['parent_class']}.{f['parent_method']:>30} | {f['method_call']:>20} | kwargs={f['kwargs']}")
    print()

    # 按 parent_method 聚合漏修
    print("=" * 80)
    print("## R51 漏修按 parent_method 聚合 (R150 keyword 模式消歧)")
    print("=" * 80)
    by_method: Dict[str, List[Dict[str, Any]]] = {}
    for f in no_exc_info_findings:
        key = f"{f['parent_class']}.{f['parent_method']}"
        by_method.setdefault(key, []).append(f)
    for method, findings in sorted(by_method.items()):
        print(f"  {method}: {len(findings)} 处漏修")
        for f in findings:
            print(f"    L{f['line']:>5} {f['method_call']}")
    print()

    # 写入 JSON 报告辅助
    import json
    out_path = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tests\_r159_b_scan.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "file": FILE_PATH,
            "total_logger_calls": len(all_findings),
            "in_except_total": len(in_except_findings),
            "in_except_with_exc_info": len(with_exc_info_findings),
            "in_except_without_exc_info": len(no_exc_info_findings),
            "not_in_except": len(not_in_except_findings),
            "no_exc_info_findings": no_exc_info_findings,
            "with_exc_info_findings": with_exc_info_findings,
            "not_in_except_findings": not_in_except_findings,
        }, f, ensure_ascii=False, indent=2)
    print(f"JSON 报告已写入: {out_path}")


if __name__ == "__main__":
    scan()
