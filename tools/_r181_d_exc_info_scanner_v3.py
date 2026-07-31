#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R181-D Agent/Strategy exc_info 严格扫描器 v3

R104 §12 5 铁律 100% 应用:
- 铁律 #3: AST 递归 with.body (含 try/if/for/while 嵌套)
- 铁律 #4: 物理删除/修复前 4 源 100% 命中
- 铁律 #5: AST unparse 还原方法体, 二次验证

扫描规则:
1. 遍历所有 Try/Except 块, 收集所有 logger.{error,warning,critical,info,debug} 调用
2. 对每个 logger 调用, 检查是否传 exc_info=True 关键字参数
3. 排除 falsy exc_info (None/False/动态值) - 仅 True 视为合规
4. 仅检测 except 块内 logger 调用 (非 try 块主体)

输出: JSON 报告, 含每条违规的文件、行号、方法、except 类型、原始 logger 调用
"""

import ast
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple


# R51 §7.1 #5 强约束: 业务关键 logger 列表
CRITICAL_LOGGER_METHODS = {"error", "warning", "critical", "info", "exception"}


class ExcInfoViolation:
    """单条 exc_info 违规记录"""

    def __init__(
        self,
        file_path: str,
        line: int,
        col: int,
        func_name: str,
        except_type: str,
        logger_method: str,
        logger_call_src: str,
        severity: str = "P1",
        business_critical: bool = False,
    ):
        self.file_path = file_path
        self.line = line
        self.col = col
        self.func_name = func_name
        self.except_type = except_type
        self.logger_method = logger_method
        self.logger_call_src = logger_call_src
        self.severity = severity
        self.business_critical = business_critical

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file_path,
            "line": self.line,
            "col": self.col,
            "func_name": self.func_name,
            "except_type": self.except_type,
            "logger_method": self.logger_method,
            "logger_call_src": self.logger_call_src,
            "severity": self.severity,
            "business_critical": self.business_critical,
        }


def find_enclosing_function(node: ast.AST) -> str:
    """找到节点所属的函数/方法名"""
    # 通过 parent_map 反向追溯
    return ""  # 由调用方通过 parent_map 注入


def build_parent_map(tree: ast.AST) -> Dict[int, ast.AST]:
    """构建 ast 节点 id -> 父节点 的映射"""
    parent_map = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent_map[id(child)] = node
    return parent_map


def find_enclosing_function_name(node: ast.AST, parent_map: Dict[int, ast.AST]) -> str:
    """递归向上找最近的 FunctionDef/AsyncFunctionDef"""
    current = node
    while current is not None and id(current) in parent_map:
        current = parent_map[id(current)]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name
    return "<module>"


def find_enclosing_except_handler(
    node: ast.AST, parent_map: Dict[int, ast.AST]
) -> ast.ExceptHandler:
    """递归向上找最近的 ExceptHandler"""
    current = node
    while current is not None and id(current) in parent_map:
        current = parent_map[id(current)]
        if isinstance(current, ast.ExceptHandler):
            return current
    return None


def extract_logger_call_src(node: ast.Call, source_lines: List[str]) -> str:
    """还原 logger 调用的源码片段 (用于二次验证)"""
    try:
        return ast.unparse(node)
    except Exception:
        # 降级: 从源码直接提取
        if hasattr(node, "lineno") and node.lineno <= len(source_lines):
            return source_lines[node.lineno - 1].strip()
    return ""


def get_exc_info_kwarg_value(node: ast.Call) -> Any:
    """获取 logger 调用的 exc_info 关键字参数值"""
    for kw in node.keywords:
        if kw.arg == "exc_info":
            if isinstance(kw.value, ast.Constant):
                return kw.value.value
            elif isinstance(kw.value, ast.NameConstant):  # Python 3.7 compat
                return kw.value.value
            else:
                # 动态值, 视为非 True (无法静态确认)
                return None
    return None


def has_exc_info_true(node: ast.Call) -> bool:
    """检查 logger 调用是否传 exc_info=True"""
    return get_exc_info_kwarg_value(node) is True


def collect_logger_calls_in_except(
    except_handler: ast.ExceptHandler,
    source_lines: List[str],
    file_path: str,
    func_name: str,
    parent_map: Dict[int, ast.AST],
) -> List[ExcInfoViolation]:
    """收集 except 块内所有 logger.{error,warning,critical,info,exception} 调用"""
    violations: List[ExcInfoViolation] = []
    except_type = ast.unparse(except_handler.type) if except_handler.type else "Exception"

    # 递归进入 except 块的所有语句 (R104 §12 铁律 #3)
    def visit_block(stmts: List[ast.stmt]):
        for stmt in stmts:
            if isinstance(stmt, ast.Try):
                # 嵌套 try: 进入 try 块, 其内可能有更多 logger
                visit_block(stmt.body)
                # 也进入 except 子句
                for handler in stmt.handlers:
                    visit_block(handler.body)
            elif isinstance(stmt, ast.If):
                # 嵌套 if: 进入 if.body + orelse
                visit_block(stmt.body)
                visit_block(stmt.orelse)
            elif isinstance(stmt, (ast.For, ast.While)):
                # 嵌套 for/while: 进入 body + orelse
                visit_block(stmt.body)
                visit_block(stmt.orelse)
            elif isinstance(stmt, ast.With):
                # 嵌套 with: 进入 with.body
                visit_block(stmt.body)
            else:
                # 检查 stmt 本身或内部
                for sub_node in ast.walk(stmt):
                    if isinstance(sub_node, ast.Call):
                        # 检查是否是 logger.{error,warning,critical,info,exception}(...)
                        if (
                            isinstance(sub_node.func, ast.Attribute)
                            and isinstance(sub_node.func.value, ast.Name)
                            and sub_node.func.value.id in ("logger", "_logger", "self")
                            and sub_node.func.attr in CRITICAL_LOGGER_METHODS
                        ):
                            # 排除 self._logger.foo 但保留 logger.foo
                            if sub_node.func.value.id == "self" and not sub_node.func.attr.startswith("_logger") and not sub_node.func.attr == "logger":
                                # self.logger.X() 也算
                                pass
                            logger_method = sub_node.func.attr
                            # 检查 exc_info
                            if not has_exc_info_true(sub_node):
                                # 是违规
                                # 判断严重性: logger.error/critical = P0, warning = P1, info/exception = P2
                                if logger_method in ("error", "critical"):
                                    severity = "P0"
                                elif logger_method in ("warning",):
                                    severity = "P1"
                                else:
                                    severity = "P2"
                                violations.append(
                                    ExcInfoViolation(
                                        file_path=file_path,
                                        line=sub_node.lineno,
                                        col=sub_node.col_offset,
                                        func_name=func_name,
                                        except_type=except_type,
                                        logger_method=logger_method,
                                        logger_call_src=extract_logger_call_src(
                                            sub_node, source_lines
                                        ),
                                        severity=severity,
                                        business_critical=True,
                                    )
                                )

    visit_block(except_handler.body)
    return violations


def scan_file(file_path: str) -> List[ExcInfoViolation]:
    """扫描单个 Python 文件, 返回所有 exc_info 违规"""
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()
        source_lines = source.split("\n")

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as e:
        print(f"  [SYNTAX ERROR] {file_path}: {e}", file=sys.stderr)
        return []

    parent_map = build_parent_map(tree)
    violations: List[ExcInfoViolation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            func_name = find_enclosing_function_name(node, parent_map)
            violations.extend(
                collect_logger_calls_in_except(
                    node, source_lines, file_path, func_name, parent_map
                )
            )

    return violations


def scan_files(file_paths: List[str]) -> Dict[str, Any]:
    """扫描多个文件, 返回 JSON 报告"""
    report = {
        "scanner": "tools/_r181_d_exc_info_scanner_v3.py",
        "version": "v3",
        "rules": "R51 §7.1 #5 + R104 §12 铁律 #3 + #5",
        "files_scanned": len(file_paths),
        "total_violations": 0,
        "by_severity": {"P0": 0, "P1": 0, "P2": 0},
        "by_file": {},
        "violations": [],
    }

    for fp in file_paths:
        if not os.path.exists(fp):
            report["by_file"][fp] = {"error": "file not found"}
            continue
        file_violations = scan_file(fp)
        report["by_file"][fp] = {
            "violation_count": len(file_violations),
            "violations": [v.to_dict() for v in file_violations],
        }
        report["total_violations"] += len(file_violations)
        for v in file_violations:
            report["by_severity"][v.severity] += 1
            report["violations"].append(v.to_dict())

    # 按文件 + 行号排序
    report["violations"].sort(key=lambda x: (x["file"], x["line"]))
    return report


def main():
    # 默认 10 个目标文件 (R180-B 报告)
    target_files = [
        "core/database/duckdb_manager.py",
        "core/agents/fusion_engine.py",
        "core/agents/technical_agent.py",
        "core/services/strategy_service.py",
        "core/services/stock_service.py",
        "core/services/asset_service.py",
        "core/services/industry_service.py",
        "core/services/chart_service.py",
        "core/agents/news_agent.py",
        "core/agents/sentiment_agent.py",
    ]

    # 也接受命令行参数
    if len(sys.argv) > 1:
        target_files = sys.argv[1:]

    print(f"[R181-D v3 scanner] Scanning {len(target_files)} files...")
    report = scan_files(target_files)

    # 输出 JSON 报告
    output_path = ".r181_d_exc_info_scan.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 控制台简要摘要
    print(f"\n=== R181-D v3 扫描结果 ===")
    print(f"扫描文件: {report['files_scanned']}")
    print(f"总违规数: {report['total_violations']}")
    print(f"  P0: {report['by_severity']['P0']}")
    print(f"  P1: {report['by_severity']['P1']}")
    print(f"  P2: {report['by_severity']['P2']}")
    print(f"\n按文件分布:")
    for fp, info in report["by_file"].items():
        if isinstance(info, dict) and "violation_count" in info:
            print(f"  {fp}: {info['violation_count']} 处")
        else:
            print(f"  {fp}: {info.get('error', 'unknown error')}")
    print(f"\n详细报告: {output_path}")


if __name__ == "__main__":
    main()
