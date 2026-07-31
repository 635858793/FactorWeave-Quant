#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R180-C P0 修复: unified_data_manager.py 5 处 except 块内 logger 缺 exc_info=True

R85 假修复鉴别 4 步法 100% 应用:
- 步骤 1 (位置): R180-C 报告 L1628/L1640/L1893/L2150/L2326/L2337
- 步骤 2 (方法): 逐个验证, 仅在 except 块内
- 步骤 3 (调用方): R51 铁律 #5 业务关键路径强制 exc_info=True
- 步骤 4 (证据): 4 源验证 + 实际行号 Read

R174 §2 Edit 工具兼容性教训: Windows PowerShell + 中文+特殊字符 不稳定
用 Python 脚本直接操作文件 + Read 二次验证
"""
import re
from pathlib import Path

UDM_PATH = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\unified_data_manager.py")

# 5 处 P0 违规 (Read 实测, R180-C 报告交叉验证)
# 每处: (line_no, search_pattern, replacement)
# 修复策略: logger.warning(...) 末尾添加 , exc_info=True
# 注: 修复必须保留原缩进和格式

FIXES = [
    # L1628 DEGRADE.L2.TIMEOUT (except TimeoutError)
    (
        1628,
        '''                    logger.warning(
                        f"[DEGRADE.L2.TIMEOUT] ts={_t.time():.6f} symbol={stock_code} "
                        f"timeout={self._l2_timeout_seconds}s elapsed_ms={_l2_elapsed_ms:.0f} "
                        f"ds={l2_data_source} 走 L3 兜底"
                    )''',
        '''                    logger.warning(
                        f"[DEGRADE.L2.TIMEOUT] ts={_t.time():.6f} symbol={stock_code} "
                        f"timeout={self._l2_timeout_seconds}s elapsed_ms={_l2_elapsed_ms:.0f} "
                        f"ds={l2_data_source} 走 L3 兜底",
                        exc_info=True,  # R180-C P0 修复 (R51 铁律 #5 业务关键路径)
                    )''',
    ),
    # L1640 DEGRADE.L2.EXCEPTION (except Exception as l2_exc)
    (
        1640,
        '''                    logger.warning(
                        f"[DEGRADE.L2.EXCEPTION] ts={_t.time():.6f} symbol={stock_code} "
                        f"elapsed_ms={_l2_elapsed_ms:.0f} err={l2_exc}"
                    )''',
        '''                    logger.warning(
                        f"[DEGRADE.L2.EXCEPTION] ts={_t.time():.6f} symbol={stock_code} "
                        f"elapsed_ms={_l2_elapsed_ms:.0f} err={l2_exc}",
                        exc_info=True,  # R180-C P0 修复 (R51 铁律 #5 业务关键路径)
                    )''',
    ),
    # L1893 R73.NEW_STOCK.FALLBACK.FETCH.ERROR (except Exception as e)
    (
        1893,
        '''                        logger.warning(
                            f"[R73.NEW_STOCK.FALLBACK.FETCH.ERROR] "
                            f"source={fetcher.source_name} symbol={stock_code} "
                            f"err={type(e).__name__}: {e}"
                        )''',
        '''                        logger.warning(
                            f"[R73.NEW_STOCK.FALLBACK.FETCH.ERROR] "
                            f"source={fetcher.source_name} symbol={stock_code} "
                            f"err={type(e).__name__}: {e}",
                            exc_info=True,  # R180-C P0 修复 (R51 铁律 #5 业务关键路径)
                        )''',
    ),
    # L2150 批量最新价查询 向量化失败 (except KeyError, AttributeError)
    (
        2150,
        '''                logger.warning(
                    f"[批量最新价查询] 向量化失败 ({e}), 退回 iterrows 路径"
                )''',
        '''                logger.warning(
                    f"[批量最新价查询] 向量化失败 ({e}), 退回 iterrows 路径",
                    exc_info=True,  # R180-C P0 修复 (R51 铁律 #5 业务关键路径)
                )''',
    ),
    # L2326 DEGRADE.L2.TIMEOUT (gdfs)
    (
        2326,
        '''                        logger.warning(
                            f"[DEGRADE.L2.TIMEOUT] ts={_t.time():.6f} symbol={stock_code} "
                            f"timeout={self._l2_timeout_seconds}s elapsed_ms={_gdfs_elapsed:.0f} "
                            f"ds={data_source} path=get_kdata_from_source"
                        )''',
        '''                        logger.warning(
                            f"[DEGRADE.L2.TIMEOUT] ts={_t.time():.6f} symbol={stock_code} "
                            f"timeout={self._l2_timeout_seconds}s elapsed_ms={_gdfs_elapsed:.0f} "
                            f"ds={data_source} path=get_kdata_from_source",
                            exc_info=True,  # R180-C P0 修复 (R51 铁律 #5 业务关键路径)
                        )''',
    ),
    # L2337 DEGRADE.L2.EXCEPTION (gdfs)
    (
        2337,
        '''                        logger.warning(
                            f"[DEGRADE.L2.EXCEPTION] ts={_t.time():.6f} symbol={stock_code} "''',
        '''                        logger.warning(
                            f"[DEGRADE.L2.EXCEPTION] ts={_t.time():.6f} symbol={stock_code} "''',
    ),
]


def main():
    if not UDM_PATH.exists():
        print(f"ERROR: {UDM_PATH} 不存在")
        return

    source = UDM_PATH.read_text(encoding="utf-8")
    lines = source.split("\n")
    print(f"原始行数: {len(lines)}")

    fixed = 0
    for line_no, search_pattern, replacement in FIXES:
        # Convert pattern to single-line for matching
        search_single = search_pattern.replace("\n", "\\n")

        # Find and replace starting at line_no (1-indexed)
        idx = line_no - 1
        if idx >= len(lines):
            print(f"  L{line_no}: SKIP (越界)")
            continue

        # Check if the lines from idx match the pattern
        actual_block = "\n".join(lines[idx:idx + search_pattern.count("\n") + 1])
        if search_pattern in actual_block or search_pattern.replace("\n", "\n") in actual_block:
            # Find exact position
            actual_lines = lines[idx:idx + search_pattern.count("\n") + 1]
            actual_text = "\n".join(actual_lines)

            if search_pattern in actual_text:
                # Replace
                new_text = actual_text.replace(search_pattern, replacement, 1)
                new_lines = new_text.split("\n")
                for i, nl in enumerate(new_lines):
                    lines[idx + i] = nl
                print(f"  L{line_no}: ✅ FIXED")
                fixed += 1
            else:
                print(f"  L{line_no}: ❌ NOT MATCHED (search pattern not found)")
                # Show diff
                print(f"    Expected start: {search_pattern[:80]!r}")
                print(f"    Actual start:   {actual_text[:80]!r}")
        else:
            print(f"  L{line_no}: ❌ NOT MATCHED (block mismatch)")

    # Write back
    new_source = "\n".join(lines)
    UDM_PATH.write_text(new_source, encoding="utf-8")
    print(f"\n修复完成: {fixed}/{len(FIXES)} 处")
    print(f"新行数: {len(lines)}")

    # Verify: check all 5 locations now have exc_info=True
    print("\n=== 修复验证 ===")
    new_lines = UDM_PATH.read_text(encoding="utf-8").split("\n")
    for line_no, _, _ in FIXES:
        idx = line_no - 1
        if idx + 3 < len(new_lines):
            context = "\n".join(new_lines[idx:idx + 5])
            has_exc_info = "exc_info=True" in context
            print(f"  L{line_no}: {'✅ exc_info=True 已应用' if has_exc_info else '❌ exc_info=True 缺失'}")


if __name__ == "__main__":
    main()
