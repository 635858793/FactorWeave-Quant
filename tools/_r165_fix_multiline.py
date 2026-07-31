#!/usr/bin/env python3
"""R165 多行 logger.warning 添加 exc_info=True"""
import ast
import sys
from pathlib import Path

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")


def fix_multiline(file_path: Path) -> tuple:
    """处理多行 logger.warning 调用

    策略: 找到 logger.warning( 后跨多行, 找到右括号, 在前一行加 , exc_info=True
    """
    content = file_path.read_text(encoding='utf-8')
    try:
        tree = ast.parse(content)
    except (SyntaxError, IndentationError) as e:
        return 0, f"语法错误: {e}"

    # 收集需要修改的 Call 节点
    lines = content.split('\n')
    fixed = 0

    # 找多行 logger.warning/error/critical 调用
    modifications = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Attribute)
                and node.func.attr in ('warning', 'error', 'critical')
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == 'logger'):
            continue
        if any(kw.arg == 'exc_info' for kw in node.keywords):
            continue
        # 必须是 except 块内
        is_in_except = False
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ExceptHandler) and node in ast.walk(parent):
                is_in_except = True
                break
        if not is_in_except:
            continue
        # 检查是否多行
        if node.end_lineno > node.lineno:
            # 多行: 在 node.end_lineno-1 行, 找到 ) 前插入
            last_line_idx = node.end_lineno - 1
            if last_line_idx < len(lines):
                last_line = lines[last_line_idx]
                # 找最后一个 ) 的位置
                rparen = last_line.rfind(')')
                if rparen > 0:
                    if ', exc_info' not in last_line:
                        lines[last_line_idx] = last_line[:rparen] + ', exc_info=True' + last_line[rparen:]
                        fixed += 1

    new_content = '\n'.join(lines)
    file_path.write_text(new_content, encoding='utf-8')
    return fixed, 'OK'


def main():
    files = [
        "core/trading/account_repository.py",
        "core/trading/order_event_handlers.py",
    ]
    for rel in files:
        fp = ROOT / rel
        n, status = fix_multiline(fp)
        print(f"{rel}: 修复 {n} 个多行调用, 状态: {status}")
        # 验证
        try:
            ast.parse(fp.read_text(encoding='utf-8'))
            print(f"  ✅ AST OK")
        except (SyntaxError, IndentationError) as e:
            print(f"  ❌ L{e.lineno}: {e.msg}")


if __name__ == '__main__':
    main()
