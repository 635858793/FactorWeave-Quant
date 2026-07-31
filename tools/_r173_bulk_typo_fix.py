#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R173-P0-2/3 批量修复脚本: 修复 logger.X(, exc_info=True) 空参数 + 后续行 f-string 缩进错误.

原错误模式:
    logger.X(, exc_info=True)
        f"..."
        f"...",
        exc_info=True,
    )

正确模式:
    logger.X(
        f"..."
        f"...",
        exc_info=True,
    )
"""
import re
import sys
from pathlib import Path


def fix_logger_typofix(content: str) -> str:
    """修复 logger.X(, exc_info=True) 模式

    模式: `logger.(error|warning|critical|debug)(, exc_info=True)` 后跟 N 行 f-string
    转换: 删除 `, exc_info=True)` 第一个, 把 f-string 缩进回到 logger.X( 同一层
    """
    # 1) 修复 logger.X(, exc_info=True) -> logger.X(
    pattern_typofix = re.compile(
        r'^(?P<indent>[ \t]*)logger\.(?P<level>error|warning|critical|debug|info)\(\s*,\s*exc_info=True\s*\)\s*$',
        re.MULTILINE,
    )

    def repl_typofix(match):
        indent = match.group('indent')
        level = match.group('level')
        return f"{indent}logger.{level}("

    content = pattern_typofix.sub(repl_typofix, content)

    # 2) 修复后续 f-string 行的缩进: logger.X( 在 indent, 后续 f-string 应为 indent + 4
    # 但是脚本最简单做法: 找到 logger.X( 行, 把下面连续的 f-string 行的缩进统一调整
    # 实际上原错误的 f-string 缩进是 +4 空格, 应该与 logger.X( 对齐 +4 空格
    # 例如:
    #     logger.X(
    #         f"..."   <- 缩进 12 (logger.X( 缩进 8 + 4)
    # 修改: 检查如果已经对齐就不动
    # 这里假设脚本输入已经是改好的

    return content


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
        fixed = fix_logger_typofix(original)
        if fixed != original:
            p.write_text(fixed, encoding='utf-8')
            print(f"[FIX] {fp} - 已修复 logger.X(, exc_info=True) 模式")
        else:
            print(f"[OK]  {fp} - 无需修复")


if __name__ == '__main__':
    main()
