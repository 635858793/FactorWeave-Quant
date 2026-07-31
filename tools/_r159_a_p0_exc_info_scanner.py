"""R159-A 统计仅 logger.error/critical 缺 exc_info 的位置 (P0 必修)"""
import ast
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

TOP_5_P0_FILES = [
    "core/coordinators/main_window_coordinator.py",
    "gui/widgets/enhanced_data_import_widget.py",
    "core/ui/panels/right_panel.py",
    "core/services/advanced_risk_control_service.py",
    "core/trading/order_service.py",
    "core/importdata/import_execution_engine.py",
]


def extract_string_value(node) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
        return " ".join(parts)
    return ""


def is_p0_logger_call(node: ast.Call) -> bool:
    """仅检测 logger.error / logger.critical (P0 必修)"""
    if isinstance(node.func, ast.Attribute):
        if node.func.attr in ("error", "critical"):
            return True
    return False


def has_exc_info(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg == "exc_info":
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
    return False


def extract_keyword(call: ast.Call) -> str:
    """从 logger call 提取唯一 keyword"""
    if not call.args:
        return ""
    keyword = extract_string_value(call.args[0])
    # 截取有效部分
    keyword = keyword.replace("\n", " ").replace("\r", " ")
    # 删除多余空格
    keyword = " ".join(keyword.split())
    return keyword[:120]


def in_except_context(tree: ast.Module, target_line: int) -> bool:
    """检查 target_line 是否在 except 块内 (R51 强约束: except 块中 logger.error 必须 exc_info)"""
    # 简化: 通过父节点关系判断
    # AST 节点 lineno 属性, 比较目标行是否在 try/except handler 块内
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            # node.handlers 是 except 块
            for handler in node.handlers:
                if handler.lineno <= target_line:
                    # 检查 target_line 是否在 handler.body 内
                    handler_end = max((s.end_lineno or s.lineno) for s in handler.body) if handler.body else handler.lineno
                    if target_line <= handler_end:
                        return True
    return False


def analyze_file_p0(file_path: str) -> Dict[str, Any]:
    """分析 P0 logger.error 缺 exc_info"""
    full_path = PROJECT_ROOT / file_path
    if not full_path.exists():
        return {"file": file_path, "error": "File not found", "p0_missing": 0}

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception as e:
        return {"file": file_path, "error": f"Parse error: {e}", "p0_missing": 0}

    p0_missing = []
    p1_warning_missing = []
    p0_already_with_exc = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and is_p0_logger_call(node):
            method = node.func.attr
            line = node.lineno
            keyword = extract_keyword(node)
            has_ei = has_exc_info(node)
            in_except = in_except_context(tree, line)

            if has_ei:
                if in_except:
                    p0_already_with_exc += 1
                continue

            # 缺 exc_info
            if in_except:
                # P0 必修 (except 块内 logger.error 缺 exc_info)
                p0_missing.append({
                    "file": file_path,
                    "line": line,
                    "method": method,
                    "keyword": keyword,
                    "in_except": True,
                })
            else:
                # P2 业务路径外 (非 except 块, R51 #5 例子外)
                p0_missing.append({
                    "file": file_path,
                    "line": line,
                    "method": method,
                    "keyword": keyword,
                    "in_except": False,
                })

    # 分类
    in_except_count = sum(1 for m in p0_missing if m["in_except"])
    out_except_count = sum(1 for m in p0_missing if not m["in_except"])

    return {
        "file": file_path,
        "p0_missing_total": len(p0_missing),
        "p0_missing_in_except": in_except_count,
        "p0_missing_out_except": out_except_count,
        "p0_already_with_exc": p0_already_with_exc,
        "details": p0_missing[:50],  # 保留前 50 个 detail
        "details_total": len(p0_missing),
    }


def main():
    results = []
    for f in TOP_5_P0_FILES:
        result = analyze_file_p0(f)
        results.append(result)
        print(f"{f}:")
        print(f"  P0 missing total: {result.get('p0_missing_total', 0)}")
        print(f"  P0 missing in except: {result.get('p0_missing_in_except', 0)}")
        print(f"  P0 missing out except: {result.get('p0_missing_out_except', 0)}")
        print(f"  P0 already with exc_info: {result.get('p0_already_with_exc', 0)}")

    output_path = PROJECT_ROOT / "tests" / "_r159_a_p0_scan_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {output_path}")
    total = sum(r.get("p0_missing_total", 0) for r in results)
    total_in = sum(r.get("p0_missing_in_except", 0) for r in results)
    total_out = sum(r.get("p0_missing_out_except", 0) for r in results)
    print(f"\nTotal P0 missing exc_info: {total}")
    print(f"  in except (P0 必修): {total_in}")
    print(f"  out except (P2 业务路径外): {total_out}")


if __name__ == "__main__":
    main()
