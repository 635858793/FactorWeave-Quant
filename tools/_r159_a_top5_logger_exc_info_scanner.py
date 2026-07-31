"""R159-A TOP 5 P0 业务核心 logger.exc_info 扫描工具

应用 R104 §12 铁律 + R150 keyword 模式:
- 用 keyword 模式定位 logger.error 调用 (避免行号漂移)
- 检测缺 exc_info=True 的位置
- 输出 file:line + keyword + 上下文
"""
import ast
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# TOP 5 P0 业务核心文件 (R158-C 报告)
TOP_5_P0_FILES = [
    "core/coordinators/main_window_coordinator.py",
    "gui/widgets/enhanced_data_import_widget.py",
    "core/ui/panels/right_panel.py",
    "core/services/advanced_risk_control_service.py",
    "core/trading/order_service.py",
    "core/importdata/import_execution_engine.py",
]


def extract_string_value(node) -> str:
    """从 AST 节点提取字符串值"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        # f-string: 提取所有字面量部分作为 keyword
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
        return " ".join(parts)
    return ""


def is_logger_call(node: ast.Call) -> bool:
    """检测是否为 logger 调用"""
    if isinstance(node.func, ast.Attribute):
        if node.func.attr in ("error", "warning", "critical", "info", "debug"):
            return True
    return False


def has_exc_info(call: ast.Call) -> bool:
    """检测 logger call 是否带 exc_info=True"""
    for kw in call.keywords:
        if kw.arg == "exc_info":
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
    return False


def analyze_file(file_path: str) -> Dict[str, Any]:
    """分析单个文件的 logger 调用"""
    full_path = PROJECT_ROOT / file_path
    if not full_path.exists():
        return {"file": file_path, "error": "File not found", "total_calls": 0, "missing_exc_info": 0}

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception as e:
        return {"file": file_path, "error": f"Parse error: {e}", "total_calls": 0, "missing_exc_info": 0}

    logger_calls = []
    missing = []
    in_except_count = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and is_logger_call(node):
            method = node.func.attr
            line = node.lineno

            # 提取第一个位置参数作为 keyword
            keyword = ""
            if node.args:
                keyword = extract_string_value(node.args[0])
                # 截取关键标识符作为 unique keyword
                if len(keyword) > 80:
                    # 截取中段或去掉 f-string 占位符
                    keyword = keyword[:80]

            has_ei = has_exc_info(node)

            entry = {
                "file": file_path,
                "line": line,
                "method": method,
                "has_exc_info": has_ei,
                "keyword": keyword[:100],  # 限制长度
            }
            logger_calls.append(entry)

            if not has_ei and method in ("error", "critical"):
                missing.append(entry)
            elif not has_ei and method == "warning":
                # logger.warning 缺 exc_info 也算 (P1 必修)
                missing.append({**entry, "method": "warning"})

    return {
        "file": file_path,
        "total_logger_calls": len(logger_calls),
        "missing_exc_info": len(missing),
        "missing_details": missing,
    }


def main():
    results = []
    for f in TOP_5_P0_FILES:
        result = analyze_file(f)
        results.append(result)
        print(f"{f}: {result.get('total_logger_calls', 0)} logger calls, "
              f"{result.get('missing_exc_info', 0)} missing exc_info")

    # 写 JSON 报告
    output_path = PROJECT_ROOT / "tests" / "_r159_a_scan_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {output_path}")
    total_missing = sum(r.get("missing_exc_info", 0) for r in results)
    print(f"\nTotal missing exc_info (TOP 5 files): {total_missing}")


if __name__ == "__main__":
    main()
