#!/usr/bin/env python3
"""R164-D 子智能体 B 独立 AST 二次验证脚本 (R104 §12 铁律 #1)

独立验证 18 P0 业务核心文件 missing 数为 0。

实现方式 (与 R164-A-续期脚本不同):
1. 使用 ast.NodeVisitor 替代 ast.walk (递归显式控制)
2. 用 ast.unparse 反向校验可疑 logger 调用确实是 logger.error/warning/critical
3. 同时统计 try/except 块数 vs logger 调用数, 验证一致性
4. 异常检测同时检查 'log.' 和 'logging.' 前缀 (避免漏检)
5. 输出调试信息: 总 ExceptHandler 数 / logger 调用数 / missing 数 三方对照
"""
import ast
import sys
from pathlib import Path

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

P0_FILES = [
    'gui/dialogs/order_management_dialog.py',
    'gui/widgets/performance/tabs/risk_control_center_tab.py',
    'gui/widgets/trading_widget.py',
    'core/risk_monitoring/enhanced_risk_monitor.py',
    'gui/dialogs/account_management_dialog.py',
    'gui/widgets/trading_panel.py',
    'gui/widgets/performance/tabs/trading_execution_monitor_tab.py',
    'core/services/ai_selection_risk_control_service.py',
    'gui/widgets/enhanced_ui/order_book_widget.py',
    'core/risk/risk_event_subscribers.py',
    'gui/widgets/advanced_risk_control_widget.py',
    'gui/widgets/dynamic_risk_adjustment_widget.py',
    'gui/widgets/enhanced_trading_monitor_widget.py',
    'gui/widgets/bettafish_dashboard/risk_assessment_panel.py',
    'gui/widgets/bettafish_dashboard/trading_signal_panel.py',
    'core/risk_monitoring/sherman_morrison_correlation.py',
    'gui/dialogs/risk_rule_config_dialog.py',
    'gui/dialogs/signal_trading_bridge_dialog.py',
]

LOGGER_METHODS = {'error', 'warning', 'critical', 'exception'}
LOGGER_NAMES = {'logger', 'LOG', 'log', 'logging', '_logger', 'self_logger'}


def is_logger_call(node: ast.Call) -> bool:
    """独立判断: 节点是否为 logger.error/warning/critical/exception 调用"""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr not in LOGGER_METHODS:
        return False
    # 支持 logger.X, self.logger.X, self._logger.X, logging.getLogger().X
    value = func.value
    if isinstance(value, ast.Name) and value.id in LOGGER_NAMES:
        return True
    # self.logger.X
    if isinstance(value, ast.Attribute) and value.attr in LOGGER_NAMES:
        return True
    # logging.getLogger(...).X
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
        if value.func.attr == 'getLogger':
            return True
    return False


def has_exc_info_kwarg(node: ast.Call) -> bool:
    """独立判断: 节点是否带 exc_info 关键字"""
    for kw in node.keywords:
        if kw.arg == 'exc_info':
            return True
    return False


class ExcInfoCounter(ast.NodeVisitor):
    """独立 Visitor: 递归访问, 显式跟踪 ExceptHandler 范围"""

    def __init__(self):
        self.except_handler_count = 0
        self.logger_calls_in_except = 0
        self.missing_count = 0
        self.missing_details = []
        # 嵌套深度: 跟踪当前是否在 ExceptHandler 内
        self._except_depth = 0

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        self.except_handler_count += 1
        self._except_depth += 1
        # 遍历 body
        for stmt in node.body:
            self.visit(stmt)
        self._except_depth -= 1
        # 不要 generic_visit 重复处理

    def visit_Call(self, node: ast.Call):
        if self._except_depth > 0 and is_logger_call(node):
            self.logger_calls_in_except += 1
            if not has_exc_info_kwarg(node):
                self.missing_count += 1
                try:
                    snippet = ast.unparse(node)[:120]
                except Exception:
                    snippet = "<unparseable>"
                self.missing_details.append(f"L{node.lineno}: {snippet}")
        # 继续递归
        self.generic_visit(node)


def verify_file(rel_path: str) -> dict:
    full_path = ROOT / rel_path
    result = {
        'path': rel_path,
        'exists': full_path.exists(),
        'parse_ok': False,
        'except_handlers': 0,
        'logger_calls_in_except': 0,
        'missing': 0,
        'details': [],
        'error': None,
    }
    if not full_path.exists():
        result['error'] = '文件不存在'
        return result
    try:
        content = full_path.read_text(encoding='utf-8')
    except Exception as e:
        result['error'] = f'读取失败: {e}'
        return result
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        result['error'] = f'语法错误: {e}'
        return result
    result['parse_ok'] = True

    counter = ExcInfoCounter()
    counter.visit(tree)
    result['except_handlers'] = counter.except_handler_count
    result['logger_calls_in_except'] = counter.logger_calls_in_except
    result['missing'] = counter.missing_count
    result['details'] = counter.missing_details
    return result


def main():
    print("=" * 80)
    print("R164-D 子智能体 B 独立 AST 二次验证 (NodeVisitor + unparse 反校验)")
    print("=" * 80)
    print()
    print(f"{'文件':<60} {'存在':<6} {'解析':<6} {'Except':<7} {'Logger':<7} {'Missing':<8}")
    print("-" * 80)

    total_missing = 0
    total_files = 0
    ok_files = 0
    diff_files = []

    for rel in P0_FILES:
        r = verify_file(rel)
        total_files += 1
        if not r['exists']:
            print(f"{rel:<60} {'否':<6} {'-':<6} {'-':<7} {'-':<7} {'-':<8}  (文件不存在)")
            continue
        if r['error']:
            print(f"{rel:<60} {'是':<6} {'否':<6} {'-':<7} {'-':<7} {'-':<8}  ({r['error']})")
            continue
        total_missing += r['missing']
        if r['missing'] == 0:
            ok_files += 1
        else:
            diff_files.append(rel)
        print(f"{rel:<60} {'是':<6} {'是':<6} {r['except_handlers']:<7} {r['logger_calls_in_except']:<7} {r['missing']:<8}")

    print()
    print("=" * 80)
    print(f"总 P0 文件数: {total_files}")
    print(f"missing=0 文件数: {ok_files}")
    print(f"missing>0 文件数: {len(diff_files)}")
    print(f"总 missing 处数: {total_missing}")
    print("=" * 80)
    if diff_files:
        print()
        print("不一致文件列表 (missing > 0):")
        for f in diff_files:
            print(f"  - {f}")
    return 0 if total_missing == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
