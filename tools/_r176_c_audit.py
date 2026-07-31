#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R176-C R51 #5 违规精确审计脚本
=================================

**任务背景**:
- R175-B 报告 198 处违规, 跨 5 个文件
- 必修 HVD-176-B-1 (service_bootstrap 62) + HVD-176-B-2 (event_bus 16 + risk_rule_manager 16)
- 选修 R176-B-3/4/5 (main_window_coordinator 43 + import_execution_engine 24 + event_coordinator 21)
- R162 立项描述错位教训: 必须验证每个 L 行号准确

**审计方法 (R104 §12 铁律 #5 严格应用)**:
- AST 解析 + unparse 验证
- 识别所有 logger.warning 调用
- 检查是否含 exc_info=True 关键字参数
- 区分 except 块内 vs except 块外
- 输出精确行号 + 上下文 + 业务影响判定

**输出**:
- JSON 详细报告
- Markdown 摘要报告
"""
import ast
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# 5 个目标文件
TARGET_FILES = [
    "core/services/service_bootstrap.py",
    "core/events/event_bus.py",
    "core/risk_rule_manager.py",
    "core/coordinators/main_window_coordinator.py",
    "core/importdata/import_execution_engine.py",
    "core/coordinators/event_coordinator.py",
]

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")


def get_call_name(node: ast.Call) -> str:
    """获取 logger 调用的完整名称"""
    if isinstance(node.func, ast.Attribute):
        parts = []
        cur = node.func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


def has_exc_info_kwarg(call: ast.Call) -> bool:
    """检查是否含 exc_info=True 关键字参数"""
    for kw in call.keywords:
        if kw.arg == "exc_info":
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
            return False  # exc_info=False 也算违规
    return False


def find_enclosing_except(tree: ast.AST, target_line: int) -> Tuple[bool, str, int]:
    """查找目标行是否在 except 块内, 返回 (in_except, except_type, except_line)

    R104 §12 #3: 递归进入 try.body/handler.body, 不用 ast.walk 扁平化
    """
    def visit_try(try_node, line):
        for handler in try_node.handlers:
            handler_end = getattr(handler, "end_lineno", None) or line
            if handler.lineno <= line <= handler_end:
                return True, handler
            # 递归进入 handler.body
            for stmt in handler.body:
                result = search_in_stmt(stmt, line)
                if result:
                    return result
        return None

    def search_in_stmt(stmt, line):
        if isinstance(stmt, ast.Try):
            for handler in stmt.handlers:
                handler_end = getattr(handler, "end_lineno", None) or line
                if handler.lineno <= line <= handler_end:
                    return True, handler
                for sub_stmt in handler.body:
                    result = search_in_stmt(sub_stmt, line)
                    if result:
                        return result
            # 继续搜索 try.body
            for sub_stmt in stmt.body:
                result = search_in_stmt(sub_stmt, line)
                if result:
                    return result
            return None
        elif isinstance(stmt, (ast.If, ast.For, ast.While)):
            for sub_stmt in stmt.body:
                result = search_in_stmt(sub_stmt, line)
                if result:
                    return result
            if hasattr(stmt, "orelse") and stmt.orelse:
                for sub_stmt in stmt.orelse:
                    result = search_in_stmt(sub_stmt, line)
                    if result:
                        return result
            return None
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            for sub_stmt in stmt.body:
                result = search_in_stmt(sub_stmt, line)
                if result:
                    return result
            return None
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub_stmt in stmt.body:
                result = search_in_stmt(sub_stmt, line)
                if result:
                    return result
            return None
        elif isinstance(stmt, ast.TryStar):
            for handler in stmt.handlers:
                handler_end = getattr(handler, "end_lineno", None) or line
                if handler.lineno <= line <= handler_end:
                    return True, handler
            return None
        return None

    def visit(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Try):
                for handler in child.handlers:
                    handler_end = getattr(handler, "end_lineno", None) or target_line
                    if handler.lineno <= target_line <= handler_end:
                        return True, handler
                result = search_in_stmt(child, target_line)
                if result:
                    return result
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                    ast.If, ast.For, ast.While, ast.With, ast.AsyncWith)):
                result = visit(child)
                if result:
                    return result
        return None

    result = visit(tree)
    if result:
        in_except, handler = result
        try:
            except_type = ast.unparse(handler.type) if handler.type else "bare"
        except Exception:
            except_type = "?"
        return True, except_type, handler.lineno
    return False, "", 0


def find_parent_method(tree: ast.AST, target_line: int) -> str:
    """查找目标行所属方法名"""
    best = ("", 0)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_line = getattr(node, "end_lineno", None) or target_line
            if node.lineno <= target_line <= end_line:
                if not best[0] or (end_line - node.lineno) < best[1] - best[0].count("."):
                    best = (node.name, node.lineno)
    return best[0]


def extract_context(source_lines: List[str], line: int, ctx: int = 2) -> str:
    """提取目标行上下文"""
    start = max(0, line - 1 - ctx)
    end = min(len(source_lines), line + ctx + 1)
    return "\n".join(f"{i+1:5d}: {source_lines[i]}" for i in range(start, end))


def scan_file(py_path: Path) -> Dict[str, Any]:
    """扫描单个文件的所有 logger.warning 调用"""
    try:
        source = py_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {"file": str(py_path), "error": str(e), "calls": []}

    source_lines = source.split("\n")
    try:
        tree = ast.parse(source, filename=str(py_path))
    except SyntaxError as e:
        return {"file": str(py_path), "error": f"SyntaxError: {e}", "calls": []}

    calls = []
    # 遍历所有 logger.warning 调用
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            call_name = get_call_name(call)
            if not call_name:
                continue
            # 识别 logger.warning / logger.warn
            parts = call_name.split(".")
            if len(parts) < 2:
                continue
            method = parts[-1]
            if method not in ("warning", "warn"):
                continue
            # 找 base (logger / self.logger)
            base = ".".join(parts[:-1])
            if "log" not in base.lower():
                continue

            line_no = node.lineno
            has_exc = has_exc_info_kwarg(call)
            in_except, except_type, except_line = find_enclosing_except(tree, line_no)
            method_name = find_parent_method(tree, line_no)

            # 提取 logger.warning 的消息内容 (粗略)
            msg_text = ""
            if call.args:
                first_arg = call.args[0]
                if isinstance(first_arg, ast.Constant):
                    msg_text = str(first_arg.value)[:200]
                elif hasattr(ast, "JoinedStr") and isinstance(first_arg, ast.JoinedStr):
                    msg_text = "<f-string>"
            elif call.keywords and any(k.arg is None for k in call.keywords):
                # 有 *args / **kwargs
                msg_text = "<starargs>"

            calls.append({
                "line": line_no,
                "method": method_name,
                "call_name": call_name,
                "has_exc_info": has_exc,
                "in_except_block": in_except,
                "except_type": except_type,
                "except_line": except_line,
                "msg_preview": msg_text,
                "context": extract_context(source_lines, line_no, 2),
                "violation": not has_exc,  # 缺 exc_info 即违规
            })

    # 统计
    total = len(calls)
    with_exc = sum(1 for c in calls if c["has_exc_info"])
    without_exc = total - with_exc
    in_except = sum(1 for c in calls if c["in_except_block"])
    in_except_without_exc = sum(1 for c in calls if c["in_except_block"] and not c["has_exc_info"])

    return {
        "file": str(py_path.relative_to(PROJECT_ROOT)),
        "total_warning_calls": total,
        "with_exc_info": with_exc,
        "without_exc_info": without_exc,
        "in_except_block": in_except,
        "in_except_block_without_exc": in_except_without_exc,
        "calls": calls,
    }


def main():
    print("=" * 80)
    print("R176-C R51 #5 违规精确审计")
    print("=" * 80)
    print(f"扫描时间: {datetime.now().isoformat()}")
    print(f"项目根: {PROJECT_ROOT}")
    print(f"目标文件数: {len(TARGET_FILES)}")
    print()

    all_results = []
    for rel_path in TARGET_FILES:
        abs_path = PROJECT_ROOT / rel_path
        if not abs_path.exists():
            print(f"[ERROR] 文件不存在: {rel_path}")
            continue
        print(f"扫描: {rel_path}")
        result = scan_file(abs_path)
        if "error" in result:
            print(f"  [ERROR] {result['error']}")
            continue
        all_results.append(result)
        print(f"  总 logger.warning: {result['total_warning_calls']}")
        print(f"  含 exc_info: {result['with_exc_info']}")
        print(f"  缺 exc_info: {result['without_exc_info']}")
        print(f"  except 块内: {result['in_except_block']}")
        print(f"  except 块内且缺 exc_info (P0): {result['in_except_block_without_exc']}")
        print()

    # 汇总
    print("=" * 80)
    print("R175-B vs R176-C 实际统计对比")
    print("=" * 80)
    r175b_claims = {
        "core/services/service_bootstrap.py": 62,
        "core/events/event_bus.py": 16,
        "core/risk_rule_manager.py": 16,
        "core/coordinators/main_window_coordinator.py": 43,
        "core/importdata/import_execution_engine.py": 24,
        "core/coordinators/event_coordinator.py": 21,
    }
    print(f"{'文件':<55} {'R175-B声称':<12} {'实际缺exc':<12} {'except缺exc':<12} {'差值':<8}")
    print("-" * 100)
    total_claim = 0
    total_actual = 0
    total_p0 = 0
    for r in all_results:
        f = r["file"]
        claim = r175b_claims.get(f, 0)
        actual = r["without_exc_info"]
        p0 = r["in_except_block_without_exc"]
        diff = actual - claim
        total_claim += claim
        total_actual += actual
        total_p0 += p0
        sign = "+" if diff > 0 else ""
        print(f"{f:<55} {claim:<12} {actual:<12} {p0:<12} {sign}{diff}")
    print("-" * 100)
    print(f"{'总计':<55} {total_claim:<12} {total_actual:<12} {total_p0:<12} {total_actual - total_claim}")
    print()

    # 输出 JSON 详细报告
    out_dir = PROJECT_ROOT / ".trae" / "reports" / "rounds"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "audit_r176_c_r51_iron_law_5.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "tool": "R176-C R51 #5 审计脚本",
                "scan_time": datetime.now().isoformat(),
                "project_root": str(PROJECT_ROOT),
                "r175b_claim_total": total_claim,
                "actual_violations_total": total_actual,
                "p0_violations_in_except": total_p0,
                "discrepancy": total_actual - total_claim,
            },
            "results": all_results,
        }, f, ensure_ascii=False, indent=2)
    print(f"JSON 报告: {json_path}")

    # 列出所有 violation 详情
    print()
    print("=" * 80)
    print("违规详情 (按文件)")
    print("=" * 80)
    for r in all_results:
        if r["without_exc_info"] == 0:
            continue
        print(f"\n### {r['file']} (缺 exc_info: {r['without_exc_info']})")
        violations = [c for c in r["calls"] if c["violation"]]
        for v in violations[:20]:
            tag = " [P0-EXCEPT]" if v["in_except_block"] else " [INFO-ONLY]"
            print(f"  L{v['line']:>5} {v['method']:<40} {tag}")
            print(f"        消息: {v['msg_preview'][:80]}")
            if v["in_except_block"]:
                print(f"        except: L{v['except_line']} type={v['except_type']}")
        if len(violations) > 20:
            print(f"  ... 还有 {len(violations) - 20} 条 (详见 JSON 报告)")


if __name__ == "__main__":
    main()
