#!/usr/bin/env python3
"""R165 终极修复 - 简化为单步处理

策略: 读取文件, 找到 except 行, 修复后第一行(非空行)的缩进
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")


def fix_file(file_path: Path, max_iterations=20) -> tuple:
    """迭代修复, 每次修复后重新 ast.parse 找下一个错误"""
    for iteration in range(max_iterations):
        try:
            content = file_path.read_text(encoding='utf-8')
            ast.parse(content)
            return iteration, "OK"
        except (SyntaxError, IndentationError) as e:
            err_line = e.lineno
            lines = content.split('\n')
            # 找到错误行
            if err_line > len(lines):
                return iteration, f"超出范围: {err_line}"
            error_line = lines[err_line - 1] if err_line <= len(lines) else ""

            # 找到上一个 except 或 try 或 def
            fix_done = False
            for i in range(err_line - 1, -1, -1):
                prev = lines[i]
                if re.match(r'^\s*except\s+', prev):
                    # 找到 except 行, 缩进是 except_indent
                    except_indent = len(prev) - len(prev.lstrip())
                    expected = except_indent + 4
                    # 修复当前行: 改为 expected
                    if error_line.strip():
                        lines[err_line - 1] = ' ' * expected + error_line.lstrip()
                        fix_done = True
                    break

            if not fix_done:
                # 找 try 行
                for i in range(err_line - 1, -1, -1):
                    prev = lines[i]
                    if re.match(r'^\s*try\s*:', prev):
                        try_indent = len(prev) - len(prev.lstrip())
                        expected = try_indent + 4
                        if error_line.strip():
                            lines[err_line - 1] = ' ' * expected + error_line.lstrip()
                            fix_done = True
                        break

            if not fix_done:
                # 找 if/elif/else 行
                for i in range(err_line - 1, -1, -1):
                    prev = lines[i]
                    if re.match(r'^\s*(if|elif|else|for|while|def|class)\b', prev):
                        block_indent = len(prev) - len(prev.lstrip())
                        expected = block_indent + 4
                        if error_line.strip():
                            lines[err_line - 1] = ' ' * expected + error_line.lstrip()
                            fix_done = True
                        break

            if not fix_done:
                return iteration, f"无法自动修复 L{err_line}: {error_line[:80]}"

            new_content = '\n'.join(lines)
            file_path.write_text(new_content, encoding='utf-8')

    return max_iterations, "达到最大迭代"


def main():
    files = [
        "gui/widgets/trading_widget.py",
        "core/risk_monitoring/enhanced_risk_monitor.py",
    ]
    for rel in files:
        fp = ROOT / rel
        iter_count, status = fix_file(fp)
        print(f"{rel}: 迭代 {iter_count} 次, 状态: {status}")
        # 验证
        try:
            ast.parse(fp.read_text(encoding='utf-8'))
            print(f"  ✅ AST OK")
        except (SyntaxError, IndentationError) as e:
            print(f"  ❌ 仍有错误 L{e.lineno}: {e.msg}")


if __name__ == '__main__':
    main()
