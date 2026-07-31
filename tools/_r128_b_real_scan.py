"""R128 子智能体 B: 真正找出 6 文件中所有缺 exc_info=True 的位置.

R85 假修复鉴别 4 步法实战:
- 任务报告"7 文件 74 处 R145-F 假修复"是双重误报:
  - 修复从未实施 (Grep 工具的 R145-F 标记输出是幻觉)
  - 报告说有 74 处假修复, 实际 0 处真修复
- 实际任务: 实施 6 文件 74 处 exc_info=True 修复 (R145 阶段 1 漏修)

扫描策略:
1. AST 解析每个文件
2. 递归找所有 except handler
3. 在 except.body 中找 logger.XXX() 调用
4. 检查是否含 exc_info=True
5. 输出所有缺 exc_info 的位置
"""
import ast
import json
import sys
from pathlib import Path

# 6 个目标文件 (R128 任务)
TARGET_FILES = [
    'core/services/unified_data_manager.py',
    'core/services/ai_selection_integration_service.py',
    'core/services/dynamic_risk_adjustment_service.py',
    'core/strategy/strategy_engine.py',
    'core/trading/order_service.py',
    'core/trading/account_manager.py',
]

LOGGER_METHODS = {'error', 'warning', 'warn', 'info', 'debug', 'exception', 'critical', 'trace'}


def _is_logger_call(node):
    """判断是否为 logger.XXX() 调用."""
    if not isinstance(node, ast.Call):
        return False
    if not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr not in LOGGER_METHODS:
        return False
    return True


def _has_exc_info(node):
    """检查 logger 调用是否含 exc_info=True."""
    for kw in node.keywords:
        if kw.arg == 'exc_info':
            return True
    return False


def scan_file_for_missing_exc_info(file_path):
    """扫描文件, 找出所有缺 exc_info=True 的 logger 调用."""
    src = Path(file_path).read_text(encoding='utf-8')
    tree = ast.parse(src)
    lines = src.splitlines()
    violations = []
    total_logger = 0

    def _walk(node, in_except=False):
        nonlocal total_logger
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ExceptHandler):
                # 进入 except 块, 设置 in_except=True
                if child.body:
                    for stmt in child.body:
                        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                            if _is_logger_call(stmt.value):
                                total_logger += 1
                                if not _has_exc_info(stmt.value):
                                    line_no = stmt.value.lineno
                                    violations.append({
                                        'line': line_no,
                                        'method': stmt.value.func.attr,
                                        'content': lines[line_no - 1].strip()[:200],
                                    })
                        # 递归子节点 (嵌套 try/with 等)
                        _walk(stmt, in_except=True)
            elif isinstance(child, ast.Try):
                # Try 块, 递归找所有 ExceptHandler
                _walk(child, in_except=in_except)
            else:
                _walk(child, in_except=in_except)

    _walk(tree)
    return violations, total_logger


if __name__ == '__main__':
    print("=" * 80)
    print("R128 子智能体 B: 真实扫描 6 文件缺 exc_info=True 的位置")
    print("=" * 80)

    all_violations = {}
    total_v = 0
    total_l = 0
    for f in TARGET_FILES:
        violations, total_logger = scan_file_for_missing_exc_info(f)
        all_violations[f] = violations
        total_v += len(violations)
        total_l += total_logger
        print(f"\n[{f}]")
        print(f"  except 块内 logger 调用: {total_logger}")
        print(f"  缺 exc_info=True: {len(violations)}")
        for v in violations[:5]:
            print(f"    L{v['line']:>5} logger.{v['method']:>8} | {v['content'][:120]}")
        if len(violations) > 5:
            print(f"    ... (+{len(violations) - 5} more)")

    print()
    print("=" * 80)
    print(f"汇总: 6 文件共 {total_l} 处 except 块内 logger 调用, {total_v} 处缺 exc_info=True")
    print("=" * 80)

    # 写入 JSON
    with open('d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/_r128_b_real_violations.json', 'w', encoding='utf-8') as f:
        json.dump({
            'total_logger_calls_in_except': total_l,
            'total_missing_exc_info': total_v,
            'files': all_violations,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n详细违规清单已写入 _r128_b_real_violations.json")
