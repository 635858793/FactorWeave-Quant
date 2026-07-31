"""
R174 批量智能修复 account_manager.py 的 logger 缩进错误

策略: 对于每个出现 IndentationError 的位置, 找到该 logger 行,
      根据其上一行/下一行的缩进, 智能选择正确缩进 (8/12/16/20 空格)
"""
import ast
import re
import sys
from pathlib import Path


def smart_fix_indentation(file_path: str) -> int:
    """智能修复 logger.* 行缩进错误, 返回修复次数"""
    p = Path(file_path)
    content = p.read_text(encoding='utf-8')
    lines = content.split('\n')
    fixed_count = 0
    new_lines = []

    for i, line in enumerate(lines):
        # 检测 logger.* 行的可疑缩进
        m = re.match(r'^(?P<indent>[ ]+)logger\.(?P<level>\w+)\(', line)
        if not m:
            new_lines.append(line)
            continue

        indent = m.group('indent')
        # 缩进必须是 4 的倍数 (8/12/16/20)
        if len(indent) % 4 == 0:
            new_lines.append(line)
            continue

        # 找到正确的缩进
        # 向上搜索最近的非空行
        correct_indent = None
        for j in range(i - 1, max(0, i - 10), -1):
            prev = lines[j]
            if prev.strip() == '':
                continue
            prev_indent = len(prev) - len(prev.lstrip(' '))
            # logger 行应比上一行多 4 或 8 个空格
            if prev_indent == 0:
                correct_indent = '            '  # 12 空格 (方法内)
            elif prev_indent == 4:
                correct_indent = '        '  # 8 空格
            elif prev_indent == 8:
                correct_indent = '            '  # 12 空格
            elif prev_indent == 12:
                correct_indent = '                '  # 16 空格
            else:
                correct_indent = ' ' * (prev_indent + 4)
            break

        if correct_indent is None:
            correct_indent = '            '

        # 替换为正确缩进
        new_line = correct_indent + line.lstrip(' ')
        new_lines.append(new_line)
        fixed_count += 1
        print(f"L{i+1}: '{indent}' ({len(indent)}) -> '{correct_indent}' ({len(correct_indent)})")
        print(f"  OLD: {line[:80]}")
        print(f"  NEW: {new_line[:80]}")

    if fixed_count > 0:
        p.write_text('\n'.join(new_lines), encoding='utf-8')
    return fixed_count


def try_parse(file_path: str) -> bool:
    """尝试 ast.parse, 成功返回 True"""
    try:
        ast.parse(Path(file_path).read_text(encoding='utf-8'))
        return True
    except SyntaxError as e:
        print(f"  SyntaxError at L{e.lineno}: {e.msg}")
        return False


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\trading\account_manager.py'
    print(f"=== Smart fix logger indent: {target} ===")
    iteration = 0
    while iteration < 20:
        iteration += 1
        if try_parse(target):
            print(f"OK after {iteration-1} iterations")
            break
        print(f"\n--- Iteration {iteration} ---")
        n = smart_fix_indentation(target)
        if n == 0:
            print("No more logger indent fixes, manual review needed")
            break
        print(f"Fixed {n} lines")
    else:
        print(f"Max iterations ({iteration}) reached")
