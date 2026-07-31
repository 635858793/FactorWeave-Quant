#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R173 使用 lib2to3 修复 account_manager.py 缩进.

策略: 用 lib2to3 解析 + 修复, 然后用 refactor 工具重写.
但 lib2to3 通常不修缩进, 所以改用更直接的方法:
对每个 8/12 空格缩进的 logger.X 行, 根据上下文 (上一行的 except/if/for/while/def) 重新确定缩进.
"""
import re
from pathlib import Path

fp = Path('d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/trading/account_manager.py')
raw = fp.read_bytes().decode('utf-8')

lines = raw.split('\n')

def get_indent(line):
    return len(line) - len(line.lstrip())

def is_block_start(stripped):
    """检查是否是块开始 (except/if/for/while/def/class/with/elif/else)"""
    if stripped.endswith(':'):
        return True
    return False

def find_correct_indent(lines, idx):
    """找到 logger.X 行应该在的正确缩进.

    逻辑:
    1. 向上找到最近的 except/if/for/while 等块开始行
    2. 该行缩进 + 4 = body 缩进
    3. 如果 logger 行是 body, 就是 +4
    """
    # 找到上一个非空非注释行
    j = idx - 1
    while j >= 0:
        prev = lines[j]
        stripped = prev.lstrip()
        if not stripped or stripped.startswith('#'):
            j -= 1
            continue
        prev_indent = get_indent(prev)
        # 如果上一行是块开始 (以 : 结尾, 或 except 开头)
        if is_block_start(stripped):
            return prev_indent + 4
        # 如果上一行也是 logger.X(, 沿用其缩进
        if stripped.startswith('logger.'):
            return prev_indent
        # 如果上一行是函数调用 (以 ( 结尾), 应该是块中, 返回上一行缩进
        if stripped.endswith('('):
            return prev_indent + 4
        # 默认沿用上一行缩进
        return prev_indent
    return 8

fix_count = 0
for i, line in enumerate(lines):
    stripped = line.lstrip()
    if not stripped.startswith('logger.'):
        continue
    current_indent = get_indent(line)
    # 跳过已经是合理缩进的 (8, 12, 16, 20)
    if current_indent in (8, 12, 16, 20):
        # 验证: 上一行 indent 应该 < current_indent
        prev_idx = i - 1
        while prev_idx >= 0 and (not lines[prev_idx].strip() or lines[prev_idx].lstrip().startswith('#')):
            prev_idx -= 1
        if prev_idx >= 0:
            prev_indent = get_indent(lines[prev_idx])
            if prev_indent < current_indent:
                continue  # 看起来是对的, 跳过
    # 需要重新确定缩进
    new_indent = find_correct_indent(lines, i)
    if new_indent != current_indent and new_indent > 0:
        new_line = ' ' * new_indent + stripped
        lines[i] = new_line
        fix_count += 1

new_raw = '\n'.join(lines)
fp.write_bytes(new_raw.encode('utf-8'))
print(f"[DONE] account_manager.py 重新缩进 {fix_count} 处 logger 行")
