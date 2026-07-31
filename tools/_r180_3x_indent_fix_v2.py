#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R180-FOLLOWUP P0 修复 v2: 3 处 IndentationError 修正版

实际行号 (修复 1 后 +1):
- L1634-1637 → 修复为 try/except 块 (5 行, +1)
- L2156-2163 → 在 L2156 前插入 for 循环, L2156-2163 整体缩进 +4 (9 行, +1)
- L2335-2338 → 修复为 try/except 块 (5 行, +1)
"""
import re
from pathlib import Path
import shutil
import ast

UDM_PATH = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\unified_data_manager.py")
BACKUP_PATH = Path(
    r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_archive\backups_2026_07_24"
    r"\core_services_unified_data_manager_3x_v2.bak"
)

BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
if not BACKUP_PATH.exists():
    shutil.copy2(UDM_PATH, BACKUP_PATH)
    print(f"[BACKUP] {UDM_PATH.name} -> {BACKUP_PATH}")

src = UDM_PATH.read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)

INDENT_16 = "                "  # 16 空格
INDENT_20 = "                    "  # 20 空格
INDENT_24 = "                        "  # 24 空格
INDENT_28 = "                            "  # 28 空格

def try_parse(text, label):
    try:
        ast.parse(text, filename=str(UDM_PATH))
        print(f"[AST-OK] {label}: 语法 OK")
        return True
    except SyntaxError as e:
        print(f"[AST-FAIL] {label}: line {e.lineno}: {e.msg}")
        return False

# ===== 验证当前状态 =====
print("[READ-CHECK] L1624-1640:")
for i in range(1623, min(1640, len(lines))):
    print(f"  L{i+1:4d} | {lines[i]!r}", end="")
print("\n[READ-CHECK] L2145-2170:")
for i in range(2144, min(2170, len(lines))):
    print(f"  L{i+1:4d} | {lines[i]!r}", end="")
print("\n[READ-CHECK] L2325-2350:")
for i in range(2324, min(2350, len(lines))):
    print(f"  L{i+1:4d} | {lines[i]!r}", end="")

# ===== 修复 1: L1634 (l2_future.cancel() try/except 块) =====
# L1633: '                    )\n'  (logger.warning 闭合)
# L1634: '                        l2_future.cancel()\n'  ← 错误: 应是 try: 20 空格
# L1635: '                    except Exception:\n'  ← 错误: 应是 except 20 空格 (try 内)
# L1636: '                        pass\n'  ← 应是 24 空格
# L1637: '                    remote_df = None\n'  ← 应是 20 空格
print("\n" + "="*60)
print("修复 1: L1634 try/except 包裹")
print("="*60)

# 替换 lines[1633:1637] (L1634-L1637, 4 行) -> 5 行
new_block_1 = [
    INDENT_20 + "try:\n",
    INDENT_24 + "l2_future.cancel()\n",
    INDENT_20 + "except Exception:\n",
    INDENT_24 + "pass\n",
    INDENT_20 + "remote_df = None\n",
]
lines = lines[:1633] + new_block_1 + lines[1637:]
print(f"[FIX-1] 替换 L1634-L1637 (4 行) -> 5 行")

# ===== 修复 2: L2156-2163 for 循环包裹 =====
# L2155: '                )\n'  (logger.warning 闭合, 16 空格)
# L2156: "                    sym = row.get('symbol')\n"  ← 20 空格, 应在 for 循环内 (24 空格)
# L2157: "                    close_v = row.get('close')\n"  ← 同上
# L2158: '                    if sym is None or close_v is None:\n'  ← 同上
# L2159: '                        continue\n'  ← 28 空格
# L2160: '                    try:\n'  ← 24 空格
# L2161: '                        results[str(sym)] = float(close_v)\n'  ← 28 空格
# L2162: '                    except (TypeError, ValueError):\n'  ← 24 空格
# L2163: '                        continue\n'  ← 28 空格
#
# 修复: 在 L2156 前插入 for 循环, L2156-2163 缩进 +4 空格
print("\n" + "="*60)
print("修复 2: L2156-2163 for 循环包裹 + 缩进 +4")
print("="*60)

# 当前 lines[2154] = L2155 (logger.warning 闭合)
# lines[2155:2163] = L2156-L2163 (8 行 fallback)
# 在 lines[2155] 前插入 for 循环, lines[2155:2163] 缩进 +4

# 先备份原 L2156-L2163
old_fallback = lines[2155:2163]
print(f"[OLD-CHECK] L2156 当前: {old_fallback[0]!r}")

# 缩进 +4
new_fallback = []
for ln in old_fallback:
    if ln.startswith(INDENT_20):
        new_fallback.append(INDENT_24 + ln[len(INDENT_20):])
    elif ln.startswith(INDENT_24):
        new_fallback.append(INDENT_28 + ln[len(INDENT_24):])
    else:
        new_fallback.append(ln)

# for 循环起始
for_loop_start = INDENT_16 + "for row in df.itertuples(index=False):\n"

# 替换 lines[2155:2163] (8 行) -> 9 行 (1 行 for + 8 行 fallback +4 缩进)
lines = lines[:2155] + [for_loop_start] + new_fallback + lines[2163:]

print(f"[FIX-2] L2155 后插入 for 循环, L2156-L2163 缩进 +4")
print(f"  插入行: {for_loop_start!r}")
print(f"  新 L2157: {new_fallback[0]!r}")
print(f"  新 L2158: {new_fallback[1]!r}")

# ===== 修复 3: L2335-2338 (累计修复 1+2 后 +2 行) =====
# 当前 lines[2334] = L2335 (_gdfs_future.cancel() 28 空格)
# 替换 lines[2334:2338] (4 行 L2335-L2338) -> 5 行
print("\n" + "="*60)
print("修复 3: L2335 try/except 包裹 (累计偏移 +2)")
print("="*60)

# 验证当前位置
if len(lines) < 2340:
    print(f"[FATAL] 文件行数 {len(lines)} 不足 2340")
    raise SystemExit(1)

print(f"[PRE-CHECK] lines[2334] (当前 L2335): {lines[2334]!r}")
print(f"[PRE-CHECK] lines[2335] (当前 L2336): {lines[2335]!r}")

# 替换 lines[2334:2338] (4 行) -> 5 行
new_block_3 = [
    INDENT_24 + "try:\n",
    INDENT_28 + "_gdfs_future.cancel()\n",
    INDENT_24 + "except Exception:\n",
    INDENT_28 + "pass\n",
    INDENT_24 + "df = pd.DataFrame()\n",
]
lines = lines[:2334] + new_block_3 + lines[2338:]

print(f"[FIX-3] 替换 L2335-L2338 (4 行) -> 5 行")

# ===== 写回 + AST 验证 =====
new_src = "".join(lines)
UDM_PATH.write_text(new_src, encoding="utf-8")
print(f"\n[WRITE] {UDM_PATH} ({len(new_src)} chars)")

if not try_parse(new_src, "修复后"):
    print("[ROLLBACK] 还原备份")
    shutil.copy2(BACKUP_PATH, UDM_PATH)
    raise SystemExit(1)

# 验证 3 处修复位置
final_src = UDM_PATH.read_text(encoding="utf-8")
final_lines = final_src.splitlines()

print("\n[POST-READ] 修复后关键位置:")
print("  L1624-1640:")
for i in range(1623, min(1640, len(final_lines))):
    print(f"    L{i+1:4d} | {final_lines[i]}")
print("  L2150-2175:")
for i in range(2149, min(2175, len(final_lines))):
    print(f"    L{i+1:4d} | {final_lines[i]}")
print("  L2330-2350:")
for i in range(2329, min(2350, len(final_lines))):
    print(f"    L{i+1:4d} | {final_lines[i]}")

print(f"\n[SUCCESS] 3 处 IndentationError 全部修复")
print(f"  备份: {BACKUP_PATH}")
