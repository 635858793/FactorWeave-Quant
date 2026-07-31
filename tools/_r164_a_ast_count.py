#!/usr/bin/env python3
"""R164-A-续期 AST 感知版 exc_info 缺失统计 (避免多行 logger 调用误报)

R104 §12 铁律 #5: 锁嵌套检测必须 AST unparse 验证完整方法体, 严禁字符串匹配
本工具同样原则: exc_info 检测必须 AST 感知, 严禁单行字符串匹配

用法:
    python tools/_r164_a_ast_count.py
    python tools/_r164_a_ast_count.py <file_path>
"""
import ast
import sys
from pathlib import Path

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

TARGETS = {
    "gui/widgets/trading_widget.py": 25,
    "gui/widgets/performance/tabs/risk_control_center_tab.py": 23,
    "gui/widgets/performance/tabs/trading_execution_monitor_tab.py": 21,
    "gui/widgets/enhanced_ui/order_book_widget.py": 17,
}


def count_exc_info_missing_ast(file_path: Path) -> tuple:
    """AST 感知版: 统计 except 块内 logger.error/warning/critical 调用缺 exc_info

    Returns:
        (missing_count, missing_details)
    """
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return 0, [(0, f"文件读取失败: {e}")]

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return 0, [(0, f"语法错误: {e}")]

    missing_details = []
    missing = 0

    # 遍历所有节点
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        # 块内所有 logger.error/warning/critical 调用
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            # 检查是否是 logger.error/warning/critical
            if not _is_logger_error_call(child):
                continue
            # 检查 exc_info 关键字参数
            if not _has_exc_info_kwarg(child):
                missing += 1
                line_no = child.lineno
                missing_details.append((line_no, _format_call(child)))

    return missing, missing_details


def _is_logger_error_call(call_node: ast.Call) -> bool:
    """检查是否是 logger.error/warning/critical 调用 (排除 logger.exception)"""
    if not isinstance(call_node.func, ast.Attribute):
        return False
    if call_node.func.attr not in ('error', 'warning', 'critical'):
        return False
    # logger.xxx
    if isinstance(call_node.func.value, ast.Name) and call_node.func.value.id == 'logger':
        return True
    return False


def _has_exc_info_kwarg(call_node: ast.Call) -> bool:
    """检查 Call 节点是否带 exc_info 关键字参数 (AST 严格检查)"""
    for kw in call_node.keywords:
        if kw.arg == 'exc_info':
            # 接受 True/真值/None (logger 会自己判断)
            return True
    return False


def _format_call(call_node: ast.Call) -> str:
    """格式化 Call 节点为单行字符串 (用于报告)"""
    try:
        return ast.unparse(call_node)[:120]
    except Exception:
        return f"<unparseable call at L{call_node.lineno}>"


def main():
    targets = TARGETS
    if len(sys.argv) > 1:
        # 命令行指定单个文件
        targets = {sys.argv[1]: 0}

    total_missing = 0
    print("=" * 80)
    print("R164-A-续期 AST 感知 exc_info 缺失统计")
    print("=" * 80)

    for rel_path, expected in targets.items():
        full_path = ROOT / rel_path
        if not full_path.exists():
            print(f"[X] {rel_path}: 文件不存在")
            continue
        actual, details = count_exc_info_missing_ast(full_path)
        total_missing += actual
        if actual == 0:
            print(f"[OK] {rel_path}: 0 missing")
        else:
            print(f"[待修复 {actual} 处] {rel_path}:")
            for line_no, line in details[:5]:
                print(f"    L{line_no}: {line}")
            if len(details) > 5:
                print(f"    ... 还有 {len(details) - 5} 处")

    print("=" * 80)
    print(f"总计 missing: {total_missing}")
    print("=" * 80)
    return 0 if total_missing == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
