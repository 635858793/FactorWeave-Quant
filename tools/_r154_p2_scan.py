#!/usr/bin/env python3
"""
R154-P2-1 logger.debug 异常静默扫描工具
========================================

扫描跨 5 子目录 (core/ + gui/ + web/ + tests/ + scripts/) 中
except 块内的 logger.debug 调用, 按 R118 B15/B16 分类标准评估。

输出:
- 真 P1 业务路径 (需升级 warning + exc_info=True)
- B15 字段降级 (保留 debug)
- B16 监控辅助 (保留 debug)
- 业务正常 debug 日志 (非异常路径, 允许)
"""
import ast
import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple

PROJECT_ROOT = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui"
TARGET_DIRS = ["core", "gui", "web", "tests", "scripts"]


def find_logger_debug_in_except(tree: ast.AST) -> List[Dict]:
    """递归 AST 找到所有 except 块内的 logger.debug 调用 (含嵌套)"""
    results = []

    def visit_except_block(except_node: ast.ExceptHandler):
        """访问 except 块体, 找所有 logger.debug 调用"""
        for stmt in except_node.body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Call):
                    call = sub.value
                    if (isinstance(call.func, ast.Attribute)
                            and call.func.attr == "debug"):
                        # 提取 logger 变量名
                        logger_name = None
                        if isinstance(call.func.value, ast.Name):
                            logger_name = call.func.value.id
                        # 提取消息文本
                        msg = ast.unparse(call).split("\n")[0][:200]
                        # 是否有 exc_info
                        has_exc_info = False
                        for kw in call.keywords:
                            if kw.arg == "exc_info":
                                has_exc_info = True
                        results.append({
                            "line": sub.lineno,
                            "logger_name": logger_name,
                            "msg": msg,
                            "has_exc_info": has_exc_info,
                        })

    def visit_node(node):
        if isinstance(node, ast.Try):
            # 处理 except 块
            for handler in node.handlers:
                visit_except_block(handler)
            # 递归处理 try/else/finally
            for child in node.body + node.orelse + node.finalbody:
                visit_node(child)
        else:
            for child in ast.iter_child_nodes(node):
                visit_node(child)

    visit_node(tree)
    return results


def classify_debug(log_entry: Dict) -> str:
    """按 R118 B15/B16 标准分类"""
    msg = log_entry["msg"].lower()
    has_exc_info = log_entry["has_exc_info"]

    # B16 监控辅助关键词
    b16_keywords = [
        "更新进度", "性能指标", "健康检查", "健康状态", "性能汇总",
        "记录指标", "监控", "进度", "性能", "汇总", "deprecation",
        "deep_analysis", "traceback", "记录耗时", "调试",
    ]
    # B15 字段降级关键词
    b15_keywords = [
        "使用原始值", "data_type =", "stock_info =", "默认值",
        "data_type_none", "字段降级", "return none", "兜底",
        "无数据", "no data",
    ]
    # 真 P1 关键词(业务核心失败)
    p1_keywords = [
        "解析 plugin_center", "解析插件", "asset_identifier",
        "资产类型识别", "ioC 解析", "ioc 解析", "incoming",
        "服务注册", "容器解析",
    ]

    for kw in p1_keywords:
        if kw in msg:
            return "P1"
    for kw in b15_keywords:
        if kw in msg:
            return "B15"
    for kw in b16_keywords:
        if kw in msg:
            return "B16"
    # 有 exc_info=True 的 logger.debug 视为 R51 允许(R145 模板)
    if has_exc_info:
        return "EXC_INFO_OK"
    return "UNKNOWN"


def scan_dir(rel_dir: str) -> List[Tuple[str, Dict, str]]:
    """扫描指定目录, 返回 (文件, logger.debug, 分类) 列表"""
    full_dir = os.path.join(PROJECT_ROOT, rel_dir)
    if not os.path.isdir(full_dir):
        return []
    results = []
    for root, _, files in os.walk(full_dir):
        # 跳过 __pycache__ / .git / .codegraph
        if any(skip in root for skip in ["__pycache__", ".git", ".codegraph", "node_modules"]):
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            full_path = os.path.join(root, f)
            try:
                with open(full_path, "r", encoding="utf-8") as fp:
                    source = fp.read()
                tree = ast.parse(source)
            except (SyntaxError, UnicodeDecodeError):
                continue
            except Exception:
                continue
            for log_entry in find_logger_debug_in_except(tree):
                category = classify_debug(log_entry)
                rel_path = os.path.relpath(full_path, PROJECT_ROOT)
                results.append((rel_path, log_entry, category))
    return results


def main():
    print("=" * 80)
    print("R154-P2-1 logger.debug 异常静默扫描报告")
    print("=" * 80)
    print()

    all_results = []
    for d in TARGET_DIRS:
        results = scan_dir(d)
        all_results.extend(results)
        print(f"[{d}] 共 {len(results)} 处 logger.debug 异常静默")

    print()
    print(f"总计: {len(all_results)} 处")
    print()

    # 按分类统计
    categories = {}
    for rel_path, log_entry, cat in all_results:
        categories.setdefault(cat, []).append((rel_path, log_entry))

    for cat in ["P1", "B15", "B16", "EXC_INFO_OK", "UNKNOWN"]:
        items = categories.get(cat, [])
        print(f"--- 分类 {cat}: {len(items)} 处 ---")
        for rel_path, log_entry in items:
            exc_info_mark = "[exc_info]" if log_entry["has_exc_info"] else ""
            print(f"  {rel_path}:{log_entry['line']} {exc_info_mark}")
            print(f"    {log_entry['msg'][:150]}")
        print()

    # 写 JSON 报告
    import json
    report = {
        "total": len(all_results),
        "categories": {
            cat: [
                {"file": rp, "line": le["line"], "msg": le["msg"], "exc_info": le["has_exc_info"]}
                for rp, le in items
            ]
            for cat, items in categories.items()
        }
    }
    report_path = os.path.join(PROJECT_ROOT, "tools", "r154_p2_scan.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"详细报告: {report_path}")


if __name__ == "__main__":
    main()
