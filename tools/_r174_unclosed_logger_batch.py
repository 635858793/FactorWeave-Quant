"""
R174 终极批量修复器: 修复所有 logger.X(..., exc_info=True) 模式错误
- logger.X(f"..." 缺少 )
- logger.X(, exc_info=True) 空参数
- 缺少 )
"""
import re
import sys
import ast
from pathlib import Path


def fix_unclosed_logger(file_path: str) -> int:
    """修复 logger.X(f"..." 缺少闭合 ) 的情况"""
    p = Path(file_path)
    content = p.read_text(encoding='utf-8')
    lines = content.split('\n')
    fixed = 0
    new_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]
        # 检测 logger.X(f"..." 缺少闭合的情况
        m = re.match(r'^(\s*)logger\.(\w+)\(\s*f["\'].*$', line)
        if m and not line.rstrip().endswith(')'):
            # 找到下一个非空白行或闭合
            indent = m.group(1)
            level = m.group(2)
            # 拼接到下一个非缩进连续 f" 的行,直到遇到 ) 或 )
            collected = [line]
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if next_line.rstrip().endswith(')'):
                    # 检查是否还有 exc_info
                    if 'exc_info' not in next_line:
                        # 给该行加 exc_info=True
                        next_line_new = next_line.rstrip()[:-1] + ', exc_info=True)'
                    else:
                        next_line_new = next_line
                    collected.append(next_line_new)
                    j += 1
                    break
                elif next_line.rstrip().endswith(',') or next_line.rstrip() == '' or 'f"' in next_line or "f'" in next_line:
                    collected.append(next_line)
                    j += 1
                else:
                    # 异常情况,停止
                    break
            new_lines.extend(collected)
            i = j
            fixed += 1
            print(f"  L{i-fixed+1}: fixed unclosed logger.{level}")
            continue

        new_lines.append(line)
        i += 1

    if fixed > 0:
        p.write_text('\n'.join(new_lines), encoding='utf-8')
    return fixed


def fix_empty_param_logger(file_path: str) -> int:
    """修复 logger.X(, exc_info=True) 空参数错误"""
    p = Path(file_path)
    content = p.read_text(encoding='utf-8')
    fixed = 0

    # logger.error(, exc_info=True) → logger.error(
    pattern = re.compile(
        r'^(?P<indent>[ \t]*)logger\.(?P<level>error|warning|critical|debug|info)\(\s*,\s*exc_info=True\s*\)',
        re.MULTILINE,
    )

    def repl(m):
        nonlocal fixed
        fixed += 1
        return f"{m.group('indent')}logger.{m.group('level')}("

    new_content = pattern.sub(repl, content)
    if fixed > 0:
        p.write_text(new_content, encoding='utf-8')
    return fixed


def validate(file_path: str) -> bool:
    try:
        ast.parse(Path(file_path).read_text(encoding='utf-8'))
        return True
    except SyntaxError as e:
        print(f"  Remaining: L{e.lineno} {e.msg}")
        return False


if __name__ == '__main__':
    targets = sys.argv[1:] if len(sys.argv) > 1 else [
        r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\widgets\trading_widget.py',
    ]
    for target in targets:
        print(f"=== Fixing {target} ===")
        iteration = 0
        while iteration < 10:
            iteration += 1
            n1 = fix_unclosed_logger(target)
            n2 = fix_empty_param_logger(target)
            if n1 + n2 == 0:
                if validate(target):
                    print(f"  OK after {iteration-1} iterations")
                    break
                else:
                    print(f"  No more auto-fixes, manual review needed")
                    break
            print(f"  Iter {iteration}: unclosed={n1}, empty={n2}")
        else:
            print(f"  Max iterations reached")
