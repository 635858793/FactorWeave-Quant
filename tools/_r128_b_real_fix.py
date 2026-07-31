"""R128 子智能体 B: 真实批量修复 6 文件缺 exc_info=True 的位置.

策略:
1. AST 解析每个文件
2. 找所有 except handler 内的 logger.XXX() 调用
3. 检查是否含 exc_info=True
4. 在 logger 调用的 ) 前插入 , exc_info=True

R104 §12 5 铁律 + R6 §6.1 8 铁律 + R85 假修复鉴别 4 步法
"""
import ast
import re
import sys
import shutil
import json
from pathlib import Path

# 6 个目标文件
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
    """判断是否为 logger.XXX() 或 self.logger.XXX() 调用."""
    if not isinstance(node, ast.Call):
        return False
    if not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr not in LOGGER_METHODS:
        return False
    # Check if it's a logger-like call (logger.X, self.logger.X, _logger.X, cls.logger.X, etc.)
    return True


def _has_exc_info(node):
    """检查 logger 调用是否含 exc_info=True."""
    for kw in node.keywords:
        if kw.arg == 'exc_info':
            return True
    return False


def fix_logger_call(call_node, lines):
    """给 logger.XXX() 调用添加 exc_info=True.

    Returns: bool - 是否修改了行
    """
    if not _is_logger_call(call_node):
        return False

    if _has_exc_info(call_node):
        return False  # 已有, 跳过

    end_lineno = call_node.end_lineno
    end_col = call_node.end_col_offset

    if end_lineno < 1 or end_lineno > len(lines):
        return False

    # 获取最后一行
    last_line = lines[end_lineno - 1]

    # 找到 ) 位置 (排除字符串内的 ) )
    # 简单实现: 找最后一个 ), 前面必须是 , 或空白或开始
    # 由于 logger 调用内含 f-string 复杂场景, 这里采用启发式:
    # 在 end_col 位置之前的 ) 即为 logger 调用的闭合括号

    # 安全起见, 我们找调用结尾处的 )
    # 调用 node 的 end_col_offset 是 ) 之后的列
    if end_col > 0 and end_col <= len(last_line) and last_line[end_col - 1] == ')':
        # end_col - 1 就是 ) 的位置
        close_paren_idx = end_col - 1
    else:
        # 退而求其次, 找最后一个 )
        close_paren_idx = last_line.rfind(')')
        if close_paren_idx < 0:
            return False

    # 插入 ", exc_info=True"
    new_line = (
        last_line[:close_paren_idx]
        + ', exc_info=True'
        + last_line[close_paren_idx:]
    )
    lines[end_lineno - 1] = new_line
    return True


def fix_file(file_path, dry_run=True):
    """修复文件, 返回 (fixes_applied, total_violations)."""
    src = Path(file_path).read_text(encoding='utf-8')
    lines = src.splitlines()
    tree = ast.parse(src)

    fixes = []
    total = 0

    def _walk(node):
        nonlocal total
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ExceptHandler):
                if child.body:
                    for stmt in child.body:
                        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                            if _is_logger_call(stmt.value):
                                total += 1
                                if not _has_exc_info(stmt.value):
                                    fixes.append(stmt.value)
                        _walk(stmt)
            elif isinstance(child, ast.Try):
                _walk(child)
            else:
                _walk(child)

    _walk(tree)

    # 应用修复
    applied = 0
    for call_node in fixes:
        if fix_logger_call(call_node, lines):
            applied += 1

    if applied > 0 and not dry_run:
        # 写回
        new_src = '\n'.join(lines)
        # 保留文件末尾的换行符 (如果有)
        if src.endswith('\n') and not new_src.endswith('\n'):
            new_src += '\n'
        # 备份原文件
        backup = file_path + '.r128_pre'
        if not Path(backup).exists():
            shutil.copy2(file_path, backup)
        Path(file_path).write_text(new_src, encoding='utf-8')

    return applied, total


if __name__ == '__main__':
    print("=" * 80)
    print("R128 子智能体 B: 真正批量修复 6 文件缺 exc_info=True")
    print("=" * 80)

    dry_run = '--apply' not in sys.argv

    if dry_run:
        print("\n[DRY-RUN] 仅扫描, 不修改文件. 使用 --apply 参数应用修复")
    else:
        print("\n[APPLY] 实际应用修复 (会创建 .r128_pre 备份)")

    total_fixes = 0
    total_violations = 0
    for f in TARGET_FILES:
        applied, total = fix_file(f, dry_run=dry_run)
        total_fixes += applied
        total_violations += total - applied  # 修复前的违规数 = 缺 exc_info 的数
        print(f"\n{f}:")
        print(f"  except 块内 logger 调用总数: {total}")
        print(f"  缺 exc_info=True (修复前): {total - applied}")
        print(f"  本次修复: {applied}")

    print()
    print("=" * 80)
    if dry_run:
        print(f"DRY-RUN 结果: 6 文件共 {total_violations} 处缺 exc_info")
        print(f"  实际将修复: {total_violations} 处")
        print(f"  重新运行: python tools/_r128_b_real_fix.py --apply")
    else:
        print(f"修复完成: 6 文件共 {total_fixes} 处 exc_info=True 已添加")
    print("=" * 80)
