"""
R174 终极版智能缩进修复器:
- 运行 ast.parse 找到第一个错误行
- 找到该行,根据其上下文(函数/if/except 缩进)智能修复
- 重复直到 ast.parse 通过
"""
import ast
import re
import sys
from pathlib import Path


def find_correct_indent(lines, error_line_idx):
    """根据 error_line_idx 附近的上下文,推断 logger.* 行的正确缩进"""
    error_line = lines[error_line_idx]

    # 向上搜索 1-30 行, 找到第一个非空行
    for j in range(error_line_idx - 1, max(-1, error_line_idx - 30), -1):
        prev = lines[j]
        if not prev.strip():
            continue
        prev_indent = len(prev) - len(prev.lstrip(' '))
        prev_stripped = prev.strip()

        # 如果上一行是 def/class/if/elif/else/try/except/finally/with/for/while,logger 应多缩进 4 空格
        if (prev_stripped.startswith('def ') or prev_stripped.startswith('class ') or
            prev_stripped.startswith('if ') or prev_stripped.startswith('elif ') or
            prev_stripped.startswith('else:') or prev_stripped.startswith('try:') or
            prev_stripped.startswith('except') or prev_stripped.startswith('finally:') or
            prev_stripped.startswith('with ') or prev_stripped.startswith('for ') or
            prev_stripped.startswith('while ')):
            # logger 是该块的第一个语句, 比 def/if 缩进 +4
            return ' ' * (prev_indent + 4)

        # 如果上一行是普通语句, logger 与其同缩进
        if prev_indent > 0:
            return ' ' * prev_indent

        # 否则默认 8 空格
        return '        '

    return '        '  # 默认 8 空格


def fix_file(file_path: str, max_iterations: int = 50) -> int:
    """修复文件中所有 logger.* 缩进错误, 返回修复总行数"""
    p = Path(file_path)
    content = p.read_text(encoding='utf-8')
    total_fixed = 0

    for iteration in range(max_iterations):
        try:
            ast.parse(content)
            return total_fixed
        except SyntaxError as e:
            if e.lineno is None:
                print(f"  Cannot fix: {e.msg}")
                return total_fixed
            lines = content.split('\n')
            error_idx = e.lineno - 1
            if error_idx >= len(lines):
                return total_fixed
            line = lines[error_idx]

            # 只处理 logger.* 行的缩进错误
            m = re.match(r'^(?P<indent>[ ]+)(?P<content>logger\.\w+\()', line)
            if not m:
                print(f"  L{e.lineno} NOT a logger line, stop: {line[:80]}")
                return total_fixed

            correct = find_correct_indent(lines, error_idx)
            old_indent = m.group('indent')
            new_line = correct + m.group('content') + line[m.end():]
            lines[error_idx] = new_line
            content = '\n'.join(lines)
            total_fixed += 1
            print(f"  L{e.lineno}: '{old_indent}'({len(old_indent)}) -> '{correct}'({len(correct)})")

    return total_fixed


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\trading\account_manager.py'
    print(f"=== Ultimate smart indent fix: {target} ===")
    n = fix_file(target)
    print(f"Total fixed: {n}")
    # 验证
    try:
        ast.parse(Path(target).read_text(encoding='utf-8'))
        print("Final: AST OK")
    except SyntaxError as e:
        print(f"Final: SyntaxError L{e.lineno}: {e.msg}")
