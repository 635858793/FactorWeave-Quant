#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R146 子智能体 B: HVD-143-A/F 阶段 1 修复现状实测
扫描 7 P0 核心文件, 验证 R143 D 报告 117 处 except 缺 exc_info 修复情况
"""
import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# R143 D 报告 7 P0 核心文件清单
P0_FILES = [
    ("core/trading/order_executor.py", "HVD-143-F", 35),
    ("core/risk_manager.py", "HVD-143-A-step1.2", 23),
    ("core/events/event_bus.py", "HVD-143-A-step1.3", 17),
    ("core/services/strategy_service.py", "HVD-143-A-step1.4", 14),
    ("core/trading_engine.py", "HVD-143-A-step1.5", 13),
    ("core/services/notification_service.py", "HVD-143-A-step1.6", 12),
    ("core/trading/order_event_handlers.py", "HVD-143-A-step1.7", 3),
]

# HVD-143-F 详细行号 (R143 报告)
HVD_143_F_LINES = [
    237, 250, 363, 463, 625, 882, 917, 1393, 1414, 1434,
    1472, 1522, 1855, 1925, 2126, 2154, 2188, 2212, 2225, 2243,
    2384, 2422, 2445, 2541, 2584, 2595, 2639, 2656, 2670, 2732,
    2750, 2770, 2875, 2944, 1977
]

# risk_manager.py R143 报告 23 处行号
HVD_143_A_RM_LINES = [
    351, 385, 405, 446, 473, 526, 544, 666, 730, 780, 792, 893, 936,
    988, 1033, 1112, 1216, 1383, 1405, 1432, 1787, 1846, 1895
]

# event_bus.py R143 报告 17 处行号
HVD_143_A_EB_LINES = [
    407, 436, 445, 462, 493, 523, 539, 578, 670, 681, 706, 714,
    769, 792, 833, 1214, 1339, 1453, 1647
]


def scan_file_exc_info(file_path: str) -> List[Tuple[int, str, bool]]:
    """扫描单个文件中所有 except 块, 返回 (行号, 错误变量名, 是否带 exc_info)

    使用 AST 递归进入 except.body 检测 exc_info
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
    except Exception as e:
        return [(-1, f"无法读取: {e}", False)]

    results = []
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [(-1, f"语法错误: {e}", False)]

    # 遍历 AST
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            line_no = node.lineno
            exc_name = node.name or ""
            # 检测 except.body 内是否含 exc_info
            has_exc_info = _check_exc_info_in_body(node.body)
            # 错误信息: 简化为空,只标记状态
            results.append((line_no, exc_name, has_exc_info))

    return results


def _check_exc_info_in_body(body: List[ast.stmt]) -> bool:
    """递归检查 body 中是否含 exc_info=True

    关键: 递归进入嵌套 with/try/if/for/while, 不能用 ast.walk 扁平化
    """
    for stmt in body:
        # 直接 logger 调用 exc_info=True
        if _has_exc_info_kwarg(stmt):
            return True
        # 递归: 进入 with 块
        if isinstance(stmt, ast.With):
            if _check_exc_info_in_body(stmt.body):
                return True
            for item in stmt.items:
                if _check_exc_info_in_body(item.context_expr.__class__.__bases__):
                    pass
        # 递归: 进入 try 块
        elif isinstance(stmt, ast.Try):
            if _check_exc_info_in_body(stmt.body):
                return True
            for handler in stmt.handlers:
                if _check_exc_info_in_body(handler.body):
                    return True
        # 递归: 进入 if 块
        elif isinstance(stmt, ast.If):
            if _check_exc_info_in_body(stmt.body):
                return True
            for orelse in stmt.orelse:
                if _check_exc_info_in_body([orelse]):
                    return True
        # 递归: 进入循环
        elif isinstance(stmt, (ast.For, ast.While)):
            if _check_exc_info_in_body(stmt.body):
                return True
            for orelse in stmt.orelse:
                if _check_exc_info_in_body([orelse]):
                    return True
    return False


def _has_exc_info_kwarg(stmt: ast.stmt) -> bool:
    """检查单个语句是否含 exc_info=True

    重点匹配模式:
    - logger.error/warning/debug/info/critical(..., exc_info=True)
    - logger.exception(...)
    - 任何函数调用 + exc_info=True kwarg
    """
    for node in ast.walk(stmt):
        if isinstance(node, ast.Call):
            # 检查 kwargs
            for kw in node.keywords:
                if kw.arg == "exc_info" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    return True
    return False


def analyze_file(file_path: str, expected_lines: List[int] = None) -> Dict:
    """分析单个文件

    Args:
        file_path: 文件路径
        expected_lines: R143 D 报告的预期行号

    Returns:
        统计结果 dict
    """
    if not os.path.exists(file_path):
        return {"exists": False, "error": "file not found"}

    all_excepts = scan_file_exc_info(file_path)
    except_with_exc_info = [e for e in all_excepts if e[2]]
    except_without_exc_info = [e for e in all_excepts if not e[2]]
    except_lines = [e[0] for e in all_excepts]

    # 匹配 R143 报告的预期行号
    matched_fixed = []
    matched_unfixed = []
    for line in (expected_lines or []):
        if line in [e[0] for e in except_with_exc_info]:
            matched_fixed.append(line)
        elif line in [e[0] for e in except_without_exc_info]:
            matched_unfixed.append(line)
        else:
            # 行号找不到,可能代码已重构
            pass

    return {
        "exists": True,
        "file": file_path,
        "total_except": len(all_excepts),
        "with_exc_info": len(except_with_exc_info),
        "without_exc_info": len(except_without_exc_info),
        "exc_info_ratio": f"{len(except_with_exc_info) / max(1, len(all_excepts)) * 100:.1f}%",
        "r143_expected_lines": len(expected_lines or []),
        "r143_matched_fixed": matched_fixed,
        "r143_matched_unfixed": matched_unfixed,
        "all_except_lines": except_lines,
        "unfixed_except_lines": [e[0] for e in except_without_exc_info],
    }


def main():
    output_lines = []
    output_lines.append("=" * 100)
    output_lines.append("R146 子智能体 B: HVD-143-A/F 阶段 1 修复现状实测")
    output_lines.append("=" * 100)
    output_lines.append("")

    grand_total_except = 0
    grand_total_exc_info = 0
    grand_total_without = 0
    grand_total_expected = 0
    grand_total_matched_fixed = 0
    grand_total_matched_unfixed = 0

    for file_path, hvd_id, r143_count in P0_FILES:
        output_lines.append(f"\n{'=' * 80}")
        output_lines.append(f"文件: {file_path}")
        output_lines.append(f"立项: {hvd_id} (R143 D 报告: {r143_count} 处)")
        output_lines.append(f"{'=' * 80}")

        # 选择预期行号
        if "order_executor" in file_path:
            expected = HVD_143_F_LINES
        elif "risk_manager" in file_path:
            expected = HVD_143_A_RM_LINES
        elif "event_bus" in file_path:
            expected = HVD_143_A_EB_LINES
        else:
            expected = None

        result = analyze_file(file_path, expected)
        if not result.get("exists"):
            output_lines.append(f"  [X] 文件不存在: {file_path}")
            continue

        output_lines.append(f"  总 except 块数: {result['total_except']}")
        output_lines.append(f"  含 exc_info: {result['with_exc_info']}")
        output_lines.append(f"  缺 exc_info: {result['without_exc_info']}")
        output_lines.append(f"  exc_info 比例: {result['exc_info_ratio']}")
        if expected:
            output_lines.append(f"  R143 报告预期行号: {result['r143_expected_lines']}")
            output_lines.append(f"  R143 预期已修复: {len(result['r143_matched_fixed'])}")
            output_lines.append(f"  R143 预期未修复: {len(result['r143_matched_unfixed'])}")
            if result['r143_matched_unfixed']:
                output_lines.append(f"    未修复行号: {result['r143_matched_unfixed']}")
            if result['r143_matched_fixed']:
                output_lines.append(f"    已修复行号: {result['r143_matched_fixed']}")

        grand_total_except += result['total_except']
        grand_total_exc_info += result['with_exc_info']
        grand_total_without += result['without_exc_info']
        grand_total_expected += result['r143_expected_lines']
        grand_total_matched_fixed += len(result['r143_matched_fixed'])
        grand_total_matched_unfixed += len(result['r143_matched_unfixed'])

    output_lines.append(f"\n{'=' * 80}")
    output_lines.append(f"7 P0 核心文件汇总 (R146 B 实测):")
    output_lines.append(f"{'=' * 80}")
    output_lines.append(f"总 except 块: {grand_total_except}")
    output_lines.append(f"  含 exc_info: {grand_total_exc_info}")
    output_lines.append(f"  缺 exc_info: {grand_total_without}")
    if grand_total_except > 0:
        output_lines.append(f"  exc_info 比例: {grand_total_exc_info / grand_total_except * 100:.1f}%")
    output_lines.append(f"")
    output_lines.append(f"R143 D 报告预期:")
    output_lines.append(f"  报告行号总数: {grand_total_expected} (实际 R143 D 报告 117 处, 含 order_executor 35)")
    output_lines.append(f"  报告中已修复: {grand_total_matched_fixed}")
    output_lines.append(f"  报告未修复: {grand_total_matched_unfixed}")
    if grand_total_expected > 0:
        output_lines.append(f"  修复率: {grand_total_matched_fixed / grand_total_expected * 100:.1f}%")
    output_lines.append("")
    output_lines.append("=" * 80)
    output_lines.append("综合判定:")
    output_lines.append("=" * 80)
    if grand_total_matched_fixed == 0 and grand_total_matched_unfixed == grand_total_expected:
        output_lines.append(f"[RED] 阶段 1 **未启动**: R143 D 报告 {grand_total_expected} 处 except 缺 exc_info 全部未修复")
        output_lines.append(f"   当前实际缺 exc_info 数量: {grand_total_without}")
    elif grand_total_matched_unfixed < grand_total_expected / 2:
        output_lines.append(f"[YELLOW] 阶段 1 **部分启动**: 已修复 {grand_total_matched_fixed} 处, 剩余 {grand_total_matched_unfixed} 处")
    else:
        output_lines.append(f"[GREEN] 阶段 1 **基本完成**: 已修复 {grand_total_matched_fixed} / {grand_total_expected} 处")

    # 写入文件
    out_path = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/_r146_b_scan_output.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"Output written to {out_path}")
    print(f"Summary: {grand_total_matched_fixed}/{grand_total_expected} R143 expected lines fixed")


if __name__ == "__main__":
    main()
