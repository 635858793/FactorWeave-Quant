#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
R180-B-ext 修复脚本: unified_data_manager.py 10 处 except 块内 logger 缺 exc_info=True
=========================================================================
强制度合规:
- R51 §7.1 #5 (业务关键路径必须 exc_info=True)
- R104 §12 5 铁律 (R+1 round + 4 源 + AST 递归 + 物理删除基线 + AST unparse)
- R85 假修复鉴别 4 步法

修复清单 (10 处):
- L1994 (P1): _validate_fallback_data R75 回退数据验证
- L2337 (P0): DEGRADE.L2.EXCEPTION gdfs path
- L2495 (P1): _cache_data L1 缓存写入失败
- L2510 (P1): _cache_data L2 缓存写入失败
- L2610 (P1): invalidate_kdata_cache_for_symbol 资产类型识别失败
- L2742 (P1): _invalidate_cache_with_count L1 缓存失效失败
- L2760 (P1): _invalidate_cache_with_count L2 缓存失效失败
- L3463 (P1): _persist_to_duckdb_with_retry DuckDB 持久化重试
- L3826 (P2): _standardize_kdata_format K线排序失败
- L4192 (P1): _get_stock_asset_list 资产列表持久化
"""
import os
import re
import shutil
import sys
from pathlib import Path

TARGET = r"D:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\unified_data_manager.py"
BACKUP = r"D:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_archive\backups_2026_07_24\core_services_unified_data_manager_r180bext.bak"

# 修复规则: (line_no, severity, description, old_text, new_text)
# old_text 必须是文件中的精确字符串(行级), new_text 替换它
FIXES = [
    # === P0: L2337 ===
    {
        "line": 2340,
        "severity": "P0",
        "name": "L2337_DEGRADE.L2.EXCEPTION_gdfs",
        "old": "                            f\"err={_gdfs_exc} path=get_kdata_from_source\"\n                        )",
        "new": "                            f\"err={_gdfs_exc} path=get_kdata_from_source\",\n                            exc_info=True,  # R180-B-ext P0 修复 (R51 铁律 #5 业务关键路径)\n                        )",
    },
    # === P1: L1994 ===
    {
        "line": 1997,
        "severity": "P1",
        "name": "L1994_R75.FALLBACK.VALIDATE.REJECT",
        "old": "                f\"reason=close_type_error err={e}\"\n            )",
        "new": "                f\"reason=close_type_error err={e}\",\n                exc_info=True,  # R180-B-ext P1 修复 (R51 铁律 #5 业务关键路径)\n            )",
    },
    # === P1: L2495 ===
    {
        "line": 2497,
        "severity": "P1",
        "name": "L2495_CACHE.L1.SET.FAIL",
        "old": "                        f\"[CACHE.L1.SET.FAIL] key={cache_key[:60]} err={l1_exc}\"\n                    )",
        "new": "                        f\"[CACHE.L1.SET.FAIL] key={cache_key[:60]} err={l1_exc}\",\n                        exc_info=True,  # R180-B-ext P1 修复 (R51 铁律 #5 业务关键路径)\n                    )",
    },
    # === P1: L2510 ===
    {
        "line": 2512,
        "severity": "P1",
        "name": "L2510_CACHE.L2.SET.FAIL",
        "old": "                        f\"[CACHE.L2.SET.FAIL] key={cache_key[:60]} err={l2_exc}\"\n                    )",
        "new": "                        f\"[CACHE.L2.SET.FAIL] key={cache_key[:60]} err={l2_exc}\",\n                        exc_info=True,  # R180-B-ext P1 修复 (R51 铁律 #5 业务关键路径)\n                    )",
    },
    # === P1: L2610 ===
    {
        "line": 2612,
        "severity": "P1",
        "name": "L2610_IMPORT.CACHE.INVALIDATE.NO_ASSET_TYPE",
        "old": "                    f\"[IMPORT.CACHE.INVALIDATE.NO_ASSET_TYPE] symbol={symbol} err={e}\"\n                )",
        "new": "                    f\"[IMPORT.CACHE.INVALIDATE.NO_ASSET_TYPE] symbol={symbol} err={e}\",\n                    exc_info=True,  # R180-B-ext P1 修复 (R51 铁律 #5 业务关键路径)\n                )",
    },
    # === P1: L2742 ===
    {
        "line": 2745,
        "severity": "P1",
        "name": "L2742_CACHE.L1.INVALIDATE.FUZZY.ERROR",
        "old": "                f\"[CACHE.L1.INVALIDATE.FUZZY.ERROR] pattern={cache_key_pattern} \"\n                f\"err={e}\"\n            )",
        "new": "                f\"[CACHE.L1.INVALIDATE.FUZZY.ERROR] pattern={cache_key_pattern} \"\n                f\"err={e}\",\n                exc_info=True,  # R180-B-ext P1 修复 (R51 铁律 #5 业务关键路径)\n            )",
    },
    # === P1: L2760 ===
    {
        "line": 2763,
        "severity": "P1",
        "name": "L2760_CACHE.L2.INVALIDATE.FUZZY.ERROR",
        "old": "                f\"[CACHE.L2.INVALIDATE.FUZZY.ERROR] pattern={cache_key_pattern} \"\n                f\"err={e}\"\n            )",
        "new": "                f\"[CACHE.L2.INVALIDATE.FUZZY.ERROR] pattern={cache_key_pattern} \"\n                f\"err={e}\",\n                exc_info=True,  # R180-B-ext P1 修复 (R51 铁律 #5 业务关键路径)\n            )",
    },
    # === P1: L3463 ===
    {
        "line": 3467,
        "severity": "P1",
        "name": "L3463_DUCKDB.PERSIST.RETRY.EXC",
        "old": "                    f\"err_type={type(e).__name__} err={e}\"\n                )",
        "new": "                    f\"err_type={type(e).__name__} err={e}\",\n                    exc_info=True,  # R180-B-ext P1 修复 (R51 铁律 #5 业务关键路径)\n                )",
    },
    # === P2: L3826 (单行 logger.warning) ===
    {
        "line": 3826,
        "severity": "P2",
        "name": "L3826_K线排序失败",
        "old": "                    logger.warning(f\"⚠️ K线数据排序失败: {stock_code}, 错误={sort_error}\")",
        "new": "                    logger.warning(f\"⚠️ K线数据排序失败: {stock_code}, 错误={sort_error}\", exc_info=True)  # R180-B-ext P2 修复 (R51 铁律 #5 业务关键路径)",
    },
    # === P1: L4192 (单行 logger.warning) ===
    {
        "line": 4192,
        "severity": "P1",
        "name": "L4192_触发资产列表持久化任务失败",
        "old": "                            logger.warning(f\"⚠️ 触发资产列表持久化任务失败: {persist_error}\")",
        "new": "                            logger.warning(f\"⚠️ 触发资产列表持久化任务失败: {persist_error}\", exc_info=True)  # R180-B-ext P1 修复 (R51 铁律 #5 业务关键路径)",
    },
]


def backup_file():
    """备份原文件"""
    backup_dir = os.path.dirname(BACKUP)
    os.makedirs(backup_dir, exist_ok=True)
    if not os.path.exists(BACKUP):
        shutil.copy2(TARGET, BACKUP)
        print(f"[BACKUP] {BACKUP}")
    else:
        print(f"[BACKUP-EXISTS] {BACKUP}")


def apply_fixes():
    """应用所有修复"""
    with open(TARGET, "r", encoding="utf-8") as f:
        content = f.read()

    results = []
    for fix in FIXES:
        name = fix["name"]
        old = fix["old"]
        new = fix["new"]
        line_no = fix["line"]
        severity = fix["severity"]

        if old in content:
            count_before = content.count(old)
            content = content.replace(old, new, 1)
            count_after = content.count(old)
            results.append({
                "name": name,
                "line": line_no,
                "severity": severity,
                "status": "FIXED",
                "count_before": count_before,
                "count_after": count_after,
            })
            print(f"[FIXED] {severity} {name} (L{line_no})")
        else:
            results.append({
                "name": name,
                "line": line_no,
                "severity": severity,
                "status": "FAILED",
                "error": "old_text not found in file",
            })
            print(f"[FAILED] {severity} {name} (L{line_no}): old_text not found")

    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n[WRITE] {TARGET}")

    return results


def verify_with_grep():
    """用 Grep 验证所有 10 处修复点 exc_info=True 已添加"""
    import subprocess
    print("\n[VERIFY] Grep 验证 exc_info=True 已添加:")
    # 验证 10 处都在文件中且匹配正确行
    with open(TARGET, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for fix in FIXES:
        line_no = fix["line"]
        name = fix["name"]
        # 检查目标行附近 (line_no 上下 3 行) 是否含 exc_info=True
        start = max(0, line_no - 4)
        end = min(len(lines), line_no + 4)
        window = "".join(lines[start:end])
        has_exc = "exc_info=True" in window
        status = "OK" if has_exc else "MISS"
        print(f"  {status} {name} (L{line_no}): exc_info in window={has_exc}")


if __name__ == "__main__":
    print("=" * 70)
    print("R180-B-ext: unified_data_manager.py 10 处 except logger 缺 exc_info 修复")
    print("=" * 70)
    backup_file()
    print()
    results = apply_fixes()
    print()
    verify_with_grep()
    print()

    fixed = sum(1 for r in results if r["status"] == "FIXED")
    failed = sum(1 for r in results if r["status"] == "FAILED")
    print("=" * 70)
    print(f"SUMMARY: {fixed} FIXED, {failed} FAILED (total {len(FIXES)})")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)
