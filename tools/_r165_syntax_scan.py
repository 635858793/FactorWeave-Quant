#!/usr/bin/env python3
"""R165 修复 4 文件 SyntaxError 专用脚本 (P0 紧急)

R+1 round 验证发现的 4 个假修复:
1. trading_widget.py L861 - IndentationError (已修)
2. trading_widget.py L900 - IndentationError (待修)
3. trading_widget.py 还可能有更多 - 待扫描
4. enhanced_risk_monitor.py L2131 - SyntaxError f-string (已修)
5. account_repository.py - 7 处 exc_info 漏修
6. order_event_handlers.py - 3 处 exc_info 漏修
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

CHECK_FILES = [
    "gui/widgets/trading_widget.py",
    "core/risk_monitoring/enhanced_risk_monitor.py",
    "core/trading/account_repository.py",
    "core/trading/order_event_handlers.py",
]


def scan_syntax_errors(file_path: Path) -> list:
    """扫描 SyntaxError/IndentationError"""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return [(0, f"文件读取失败: {e}")]

    try:
        ast.parse(content)
        return []
    except (SyntaxError, IndentationError) as e:
        return [(e.lineno, str(e))]


def find_indentation_errors(file_path: Path) -> list:
    """查找 except 块后缩进错误的行 (4 空格 vs 8 空格)"""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception:
        return []

    errors = []
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        # 匹配 except Exception as e: 后只有 4 空格的 logger/error
        if re.match(r'^\s{4}logger\.', line):
            # 看上一行是否是 except
            prev = lines[i-2] if i >= 2 else ''
            if re.match(r'^\s+except\s+', prev):
                # 检查缩进: logger 应该有 8 空格 (嵌套 in except) 或 12 空格 (嵌套 in try+method)
                indent_spaces = len(line) - len(line.lstrip())
                except_indent = len(prev) - len(prev.lstrip())
                # 如果 logger 缩进 <= except 缩进, 这是错误
                if indent_spaces <= except_indent:
                    errors.append((i, line.strip()[:100], prev.strip()))
    return errors


def main():
    for rel_path in CHECK_FILES:
        full_path = ROOT / rel_path
        if not full_path.exists():
            print(f"[X] {rel_path}: 文件不存在")
            continue
        # 1. 语法错误
        syntax_errs = scan_syntax_errors(full_path)
        # 2. 缩进错误
        indent_errs = find_indentation_errors(full_path)
        if syntax_errs or indent_errs:
            print(f"\n[{rel_path}]")
            if syntax_errs:
                print(f"  SyntaxError ({len(syntax_errs)} 处):")
                for line, msg in syntax_errs:
                    print(f"    L{line}: {msg}")
            if indent_errs:
                print(f"  IndentationError ({len(indent_errs)} 处):")
                for line, content, prev in indent_errs:
                    print(f"    L{line}: {content!r}")
                    print(f"      上一行: {prev!r}")


if __name__ == '__main__':
    main()
