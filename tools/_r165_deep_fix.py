#!/usr/bin/env python3
"""R165 深度修复 - 处理所有缩进错误

策略: 对于 except 块, 确保 logger 调用有正确缩进 (比 except 多 4 空格)
"""
import re
import sys
from pathlib import Path

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")


def fix_file(file_path: Path) -> int:
    """修复文件的缩进错误"""
    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')
    fixed = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        # 找到 except 行
        m = re.match(r'^(\s+)except\s+.*:\s*$', line)
        if not m:
            i += 1
            continue
        except_indent = len(m.group(1))
        expected_indent = except_indent + 4
        # 检查后续行
        j = i + 1
        # 跳过空行
        while j < len(lines) and lines[j].strip() == '':
            j += 1
        if j < len(lines):
            next_line = lines[j]
            next_indent = len(next_line) - len(next_line.lstrip())
            # 如果下一行缩进 <= except 缩进 (即缩进错误)
            if next_indent <= except_indent and next_line.strip():
                # 修复: 改为 expected_indent
                new_line = ' ' * expected_indent + next_line.lstrip()
                lines[j] = new_line
                fixed += 1
        i = j if j > i else i + 1

    new_content = '\n'.join(lines)
    file_path.write_text(new_content, encoding='utf-8')
    return fixed


def main():
    files = [
        "gui/widgets/trading_widget.py",
        "core/risk_monitoring/enhanced_risk_monitor.py",
    ]
    for rel in files:
        fp = ROOT / rel
        n = fix_file(fp)
        print(f"{rel}: 修复 {n} 行")


if __name__ == '__main__':
    main()
