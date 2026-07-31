#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R173-P0-2/3 批量修复脚本 V2: 修复 logger.X(f"...", exc_info=True,) 缺少闭合 ) 的语法错误.

识别模式: 一行以 `, exc_info=True,` 结尾, 后跟空行, 然后**不是** `)` 开头的下一非空行.
修复: 在该行后插入 `)` 闭合行, 缩进与该行保持一致.
"""
import re
import sys
from pathlib import Path


def fix_unclosed_logger(content: str) -> tuple[str, int]:
    """修复 logger.X(...) 缺少闭合 ) 的语法错误

    模式: 一行以 `, exc_info=True,` 结尾, 后跟空行, 然后下一非空行**不是** `)` 开头.
    修复: 在 `, exc_info=True,` 行后插入 `)` 闭合行.
    """
    lines = content.split('\n')
    fix_count = 0
    n = len(lines)
    i = 0
    while i < n - 2:
        line = lines[i]
        # 匹配以 `, exc_info=True,` 或 `, exc_info=True )` 结尾的行
        # (后者已经正确闭合, 不需修复)
        stripped = line.rstrip()
        if re.search(r',\s*exc_info=True\s*,?\s*$', stripped):
            # 检查这行**不是**已经正确闭合 (即不以 `)` 结尾)
            if not stripped.endswith(')'):
                # 提取缩进 (取 `f` 之前或整个行首的缩进)
                m = re.match(r'^(\s*)', line)
                indent = m.group(1) if m else ''
                # 检查下一行 (i+1) 是否是空行或 `)` 起始的闭合
                next_line_idx = i + 1
                # 跳过连续空行
                while next_line_idx < n and lines[next_line_idx].strip() == '':
                    next_line_idx += 1
                # 如果下一非空行不是以 `)` 开头, 则需要补 `)`
                if next_line_idx < n:
                    next_line = lines[next_line_idx].lstrip()
                    if not next_line.startswith(')'):
                        # 插入 `)` 行
                        close_line = f"{indent})"
                        lines.insert(i + 1, close_line)
                        n += 1
                        i = next_line_idx + 1
                        fix_count += 1
                        continue
        i += 1
    return '\n'.join(lines), fix_count


def main():
    target_files = [
        'd:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/trading/account_manager.py',
        'd:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services/signal_trading_bridge.py',
    ]

    for fp in target_files:
        p = Path(fp)
        if not p.exists():
            print(f"[SKIP] {fp} 不存在")
            continue
        original = p.read_text(encoding='utf-8')
        fixed, count = fix_unclosed_logger(original)
        if fixed != original:
            p.write_text(fixed, encoding='utf-8')
            print(f"[FIX] {fp} - 修复 {count} 处缺 `)` 闭合")
        else:
            print(f"[OK]  {fp} - 无需修复")


if __name__ == '__main__':
    main()
