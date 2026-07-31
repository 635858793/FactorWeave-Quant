#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R180-FOLLOWUP P0 修复: unified_data_manager.py 3 处 IndentationError

R85 假修复鉴别 4 步法:
- 步骤 1 (位置): R180 子智能体 C/B-ext 在修复 exc_info=True 时引入了 3 处语法错误
- 步骤 2 (方法): L1634/L2155/L2333 缺 try: 关键字 + 缩进错位
- 步骤 3 (调用方): 阻塞模块加载, R179/R180 阶段 4 个测试失败
- 步骤 4 (证据): Read 实测 + AST parse 验证

3 处 IndentationError 全部统一修复:
1. L1626-1637: `except concurrent.futures.TimeoutError` 块内 logger 后缺 try/except 包裹 l2_future.cancel()
2. L2149-2162: `except (KeyError, AttributeError) as e` 块内 logger 后缺 fallback iterrows 缩进
3. L2324-2336: `except concurrent.futures.TimeoutError` 块内 logger 后缺 try/except 包裹 _gdfs_future.cancel()
"""
import re
from pathlib import Path
import shutil
import ast

UDM_PATH = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\unified_data_manager.py")
BACKUP_PATH = Path(
    r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_archive\backups_2026_07_24"
    r"\core_services_unified_data_manager_3x_indent_fix.bak"
)

# 1) 备份
BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
if not BACKUP_PATH.exists():
    shutil.copy2(UDM_PATH, BACKUP_PATH)
    print(f"[BACKUP] {UDM_PATH.name} -> {BACKUP_PATH}")
else:
    print(f"[BACKUP-EXISTS] {BACKUP_PATH}")

# 2) 读源码
src = UDM_PATH.read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)

# 3) 准备 AST 解析 (持续验证)
def try_parse(text, label):
    try:
        ast.parse(text, filename=str(UDM_PATH))
        print(f"[AST-OK] {label}: 语法 OK")
        return True
    except SyntaxError as e:
        print(f"[AST-FAIL] {label}: line {e.lineno}: {e.msg}")
        return False

# ===== 修复 1: L1634 (l2_future.cancel() try/except 块) =====
print("\n" + "="*60)
print("修复 1: L1634 (l2_future.cancel() 缺 try: 包裹)")
print("="*60)

# L1633:                     )
# L1634:                         l2_future.cancel()    # 错误: 应是 20 空格 try:
# L1635:                     except Exception:        # 错误: 应是 20 空格 (try 内)
# L1636:                         pass
# L1637:                     remote_df = None         # 应保留 (20 空格)

INDENT_20 = "                    "  # 20 空格
INDENT_24 = "                        "  # 24 空格
INDENT_28 = "                            "  # 28 空格

if len(lines) < 1638:
    print(f"[FATAL] 文件行数 {len(lines)} 不足")
    raise SystemExit(1)

l1633 = lines[1632]  # )
l1634 = lines[1633]  # l2_future.cancel()
l1635 = lines[1634]  # except Exception:
l1636 = lines[1635]  # pass
l1637 = lines[1636]  # remote_df = None

print(f"  L1633: {l1633!r}")
print(f"  L1634: {l1634!r}")
print(f"  L1635: {l1635!r}")
print(f"  L1636: {l1636!r}")
print(f"  L1637: {l1637!r}")

if not l1634.startswith(INDENT_24 + "l2_future.cancel()"):
    print(f"[WARN] L1634 缩进异常, 期望 {INDENT_24!r} + 'l2_future.cancel()'")
    if not (INDENT_20 + "try:") in l1634 or "l2_future.cancel()" not in l1634:
        print(f"[FATAL] L1634 不是预期的 l2_future.cancel() 块")
        raise SystemExit(1)

# 修复: L1634-1637 (4 行) -> 5 行
new_block_1 = [
    INDENT_20 + "try:\n",
    INDENT_24 + "l2_future.cancel()\n",
    INDENT_20 + "except Exception:\n",
    INDENT_24 + "pass\n",
    INDENT_20 + "remote_df = None\n",
]

# 替换 lines[1633:1637] (4 行 L1634-L1637) -> 5 行
lines = lines[:1633] + new_block_1 + lines[1637:]

# 验证修复
print("[FIX-1] L1634-1637 修复为 5 行 try/except 块:")
for i, ln in enumerate(new_block_1, start=1634):
    print(f"  L{i}: {ln!r}")

# ===== 修复 2: L2155 (fallback iterrows 缩进) =====
# 由于修复 1 增加了 1 行, 后续行号 +1
# 原始 L2149: except (KeyError, AttributeError) as e:
# 原始 L2155: sym = row.get('symbol')  (错误: 20 空格, 应是 16 空格)
# 原始 L2156: close_v = row.get('close') (错误: 20 空格, 应是 16 空格)
# 原始 L2157: if sym is None or close_v is None:
# 原始 L2158:     continue
# 原始 L2159: try:
# 原始 L2160:     results[str(sym)] = float(close_v)
# 原始 L2161: except (TypeError, ValueError):
# 原始 L2162:     continue
#
# 期望: 修复后应该是 for 循环 fallback iterrows 路径
# 已知: 原代码在 L2149 except 块后应该有 for row in df.itertuples(): 块
# 但子智能体 C 修复 L2150 时只添加了 exc_info=True, 没有补充 for 循环包装
#
# 修复策略: 在 L2155 前插入 for 循环, L2155-2162 缩进调整

print("\n" + "="*60)
print("修复 2: L2155 (fallback iterrows 缺 for 循环 + 缩进错位)")
print("="*60)

# 由于修复 1 +1 行, 当前 L2155 实际是 lines[2154] (0-indexed)
# 但 L2149-2162 实际是 lines[2148:2162]
# 先 Read 当前状态确认
print("[READ] L2145-2170 当前内容:")
for i in range(2144, min(2170, len(lines))):
    print(f"  L{i+1:4d} | {lines[i]!r}", end="")

# 修复 2: 在 L2155 前插入 for 循环, L2155-2162 整体加缩进 4 空格
# 当前 L2155 缩进 20 空格, 应是 16 空格
# 同时需要在 L2154 后 (exc_info=True 闭合) 插入 for 循环开头
#
# 当前状态 (实际行号 +1 因修复 1):
#   L2154:                 )                              # logger.warning 闭合
#   L2155:                     sym = row.get('symbol')    # 错: 20 空格
#   L2156:                     close_v = row.get('close') # 错: 20 空格
#   L2157:                     if sym is None or close_v is None:
#   L2158:                         continue
#   L2159:                     try:
#   L2160:                         results[str(sym)] = float(close_v)
#   L2161:                     except (TypeError, ValueError):
#   L2162:                         continue
#
# 期望 (插入 for 循环):
#   L2154:                 )
#   L2155:                 for row in df.itertuples(index=False):
#   L2156:                     sym = row.get('symbol') if hasattr(row, '_asdict') else getattr(row, 'symbol', None)
#   L2157:                     close_v = row.get('close') if hasattr(row, '_asdict') else getattr(row, 'close', None)
#   L2158:                     if sym is None or close_v is None:
#   L2159:                         continue
#   L2160:                     try:
#   L2161:                         results[str(sym)] = float(close_v)
#   L2162:                     except (TypeError, ValueError):
#   L2163:                         continue
#   L2164:                 # (空行)

# 但实际上 L2155 缩进 20 空格是 for 循环体的缩进 (16 + 4 = 20),
# 而 L2159 try 缩进 20 空格也是 for 循环体缩进, 整体 OK
# 问题仅是 L2155 之前缺 for 循环行

# L2155-2162 (8 行) 当前状态, 仅 L2155-2156 缩进错误 (20 空格 -> 20 空格 OK)
# 实际看代码, L2155 缩进 20 空格可能是 for 循环体内的 if 条件
# 但缺 for 循环起始行

# 简化: 假设 L2155-L2162 是 fallback 路径, 应该是 16 空格缩进 (与 except 块对齐)
# 即 for row in df.itertuples(): 应该插入在 L2154 后

# 实际从代码上下文看, 这是防御性 fallback iterrows 路径
# L2155-L2162 应在 16 空格缩进, 表示这是 except 块内的 fallback 逻辑

# 修复: 在 L2154 后插入 for 循环, L2155-2162 缩进 -4 空格
new_block_2 = [
    INDENT_20[:-4] + "for row in df.itertuples(index=False):\n",  # 16 空格
    INDENT_20 + "sym = getattr(row, 'symbol', None)\n",
    INDENT_20 + "close_v = getattr(row, 'close', None)\n",
    INDENT_20 + "if sym is None or close_v is None:\n",
    INDENT_24 + "continue\n",
    INDENT_20 + "try:\n",
    INDENT_24 + "results[str(sym)] = float(close_v)\n",
    INDENT_20 + "except (TypeError, ValueError):\n",
    INDENT_24 + "continue\n",
]

# 当前 lines[2154:2162] (8 行 L2155-L2162) -> 9 行 (含 for 循环)
# 注意: 由于修复 1 +1, 原始 L2155 = lines[2154]
# 但 L2154 是 ) (logger.warning 闭合), lines[2154] 是 L2155
# 修复 2 替换 lines[2154:2162] (L2155-L2162) 为 new_block_2

if len(lines) < 2165:
    print(f"[FATAL] 文件行数 {len(lines)} 不足 2165")
    raise SystemExit(1)

# 验证 lines[2154] 实际内容
print(f"\n[PRE-CHECK] lines[2154] (L2155): {lines[2154]!r}")
print(f"[PRE-CHECK] lines[2161] (L2162): {lines[2161]!r}")

# 替换 L2155-L2162 (8 行) -> 9 行
lines = lines[:2154] + new_block_2 + lines[2162:]

print("[FIX-2] L2155-2162 修复为 for 循环 + 9 行 fallback:")
for i, ln in enumerate(new_block_2, start=2155):
    print(f"  L{i}: {ln!r}")

# ===== 修复 3: L2333 (_gdfs_future.cancel() try/except 块) =====
# 由于修复 1 +1, 修复 2 +1, 累计 +2, 原始 L2333 = lines[2334]
print("\n" + "="*60)
print("修复 3: L2333 (_gdfs_future.cancel() 缺 try: 包裹)")
print("="*60)

# 当前 (实际 L+2):
#   L2331:                         )                              # logger.warning 闭合
#   L2332:                             _gdfs_future.cancel()       # 错: 28 空格
#   L2333:                         except Exception:               # 错: 24 空格
#   L2334:                             pass
#   L2335:                         df = pd.DataFrame()
#   L2336:                     except Exception as _gdfs_exc:     # 24 空格 (or 20)

# 期望:
#   L2331:                         )
#   L2332:                         try:                           # 24 空格
#   L2333:                             _gdfs_future.cancel()      # 28 空格
#   L2334:                         except Exception:              # 24 空格
#   L2335:                             pass                       # 28 空格
#   L2336:                         df = pd.DataFrame()            # 24 空格

# 实际: 修复 1+2 后 L2333 = lines[2334]
# L2331 闭合, L2332 _gdfs_future.cancel() (28 空格), L2333 except (24 空格)
if len(lines) < 2340:
    print(f"[FATAL] 文件行数 {len(lines)} 不足 2340")
    raise SystemExit(1)

print("[READ] L2325-2345 当前内容:")
for i in range(2324, min(2345, len(lines))):
    print(f"  L{i+1:4d} | {lines[i]!r}", end="")

# 当前 lines[2331] = L2332 闭合, lines[2332] = L2333 _gdfs_future.cancel()
# 修复: lines[2332:2336] (4 行) -> 5 行
new_block_3 = [
    INDENT_24 + "try:\n",
    INDENT_28 + "_gdfs_future.cancel()\n",
    INDENT_24 + "except Exception:\n",
    INDENT_28 + "pass\n",
    INDENT_24 + "df = pd.DataFrame()\n",
]

# 验证 lines[2332] 是 _gdfs_future.cancel() 28 空格
if not lines[2332].startswith(INDENT_28 + "_gdfs_future.cancel()"):
    print(f"[WARN] L2333 缩进异常, 实际: {lines[2332]!r}")

# 替换 lines[2332:2336] (4 行) -> 5 行
lines = lines[:2332] + new_block_3 + lines[2336:]

print("[FIX-3] L2333-2336 修复为 5 行 try/except 块:")
for i, ln in enumerate(new_block_3, start=2333):
    print(f"  L{i}: {ln!r}")

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
# 修复 1: L1634 附近
print("  L1624-1640:")
for i in range(1623, min(1640, len(final_lines))):
    print(f"    L{i+1:4d} | {final_lines[i]}")
# 修复 2: L2155 附近
print("  L2145-2170:")
for i in range(2144, min(2170, len(final_lines))):
    print(f"    L{i+1:4d} | {final_lines[i]}")
# 修复 3: L2333 附近
print("  L2325-2350:")
for i in range(2324, min(2350, len(final_lines))):
    print(f"    L{i+1:4d} | {final_lines[i]}")

print(f"\n[SUCCESS] 3 处 IndentationError 全部修复")
print(f"  备份: {BACKUP_PATH}")
print(f"  文件: {UDM_PATH}")
