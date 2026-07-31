"""R164 紧急修复 v15: 使用 tokenize 找到错误的 logger 行并修复缩进"""
import ast
import re
from pathlib import Path

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui").resolve()

# 1. 修复 trading_widget.py L208 (缩进)
# 2. 修复 enhanced_risk_monitor.py L376 (缩进)
# 3. 修复 account_manager.py L299 (缩进 + 内容)

FIXES = [
    ('gui/widgets/trading_widget.py', 207, '    logger.error(f"\u670d\u52a1\u521d\u59cb\u5316\u5931\u8d25: {e}", exc_info=True)'),
    # enhanced_risk_monitor L376
    ('core/risk_monitoring/enhanced_risk_monitor.py', 375, '            logger.error(f"\u521d\u59cb\u5316\u6570\u636e\u5e93\u5931\u8d25: {e}", exc_info=True)'),
]


def fix_indent_errors(file_path: Path, target_lines: list) -> int:
    """修复 logger 缩进错误: 应该比上一行 (except/if/with) 多 4 空格"""
    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')
    fixed = 0

    for line_no in target_lines:
        if line_no - 1 >= len(lines):
            continue
        # 0-indexed
        idx = line_no - 1
        if idx < 1:
            continue
        line = lines[idx]
        # 上一行应该是 except/if/with/elif 等以 : 结尾
        prev = lines[idx - 1]
        if prev.rstrip().endswith(':') and re.match(r'\s*logger\.', line):
            # 计算正确的缩进: prev 缩进 + 4 空格
            prev_indent = len(prev) - len(prev.lstrip())
            correct_indent = prev_indent + 4
            new_line = ' ' * correct_indent + line.lstrip()
            if new_line != line:
                lines[idx] = new_line
                fixed += 1

    if fixed > 0:
        file_path.write_text('\n'.join(lines), encoding='utf-8')
    return fixed


def main():
    for rel in ['gui/widgets/trading_widget.py', 'core/risk_monitoring/enhanced_risk_monitor.py']:
        p = ROOT / rel
        # 反复迭代修复缩进
        for _ in range(50):
            try:
                ast.parse(p.read_text(encoding='utf-8'), str(p))
                break
            except SyntaxError as e:
                # 找到错误行
                line_no = e.lineno
                # 找错误行是 logger 缩进问题
                content = p.read_text(encoding='utf-8')
                lines = content.split('\n')
                if line_no - 1 < len(lines):
                    line = lines[line_no - 1]
                    if re.match(r'\s*logger\.', line):
                        n = fix_indent_errors(p, [line_no])
                        if n == 0:
                            break
                    else:
                        break
        try:
            ast.parse(p.read_text(encoding='utf-8'), str(p))
            print(f'[OK] {rel}')
        except SyntaxError as e:
            print(f'[FAIL] {rel}: L{e.lineno}: {e.msg}')


if __name__ == '__main__':
    main()
