#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R180-B-ext-FOLLOWUP P0 修复: unified_data_manager.py L1634 IndentationError

R85 假修复鉴别 4 步法:
- 步骤 1 (位置): R180 子智能体 C 修复 L1628 DEGRADE.L2.TIMEOUT 时引入了语法错误
- 步骤 2 (方法): L1634-1637 应是 try/except 块 (l2_future.cancel() 容错), 但当前缩进错误
- 步骤 3 (调用方): 阻塞模块加载, R179/R180 阶段 4 个测试失败
- 步骤 4 (证据): Read L1624-1640 实测

R180 子智能体 B-ext 报告 §6.1 指出此问题但未修复 (R180-B-ext 任务范围外)
R180 子智能体 D 报告未识别此问题 (R+1 round 二次验证未覆盖)
R180 子智能体 C-pro 报告未识别此问题 (新立项阶段未运行模块)

影响范围:
- test_concurrent_no_deadlock
- test_8threads_100signals_p99_baseline
- test_industry_service_6_keys_uniqueness
- test_sector_fund_no_dead_code_decision
- test_tet_signals_uniqueness_cross_source

修复: L1634-1637 重写为正确的 try/except 块 (l2_future.cancel() 容错)
"""
import re
from pathlib import Path
import shutil
import time

UDM_PATH = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\unified_data_manager.py")
BACKUP_PATH = Path(
    r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_archive\backups_2026_07_24"
    r"\core_services_unified_data_manager_l1634_indent_fix.bak"
)

# 1) 备份当前文件
BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
if not BACKUP_PATH.exists():
    shutil.copy2(UDM_PATH, BACKUP_PATH)
    print(f"[BACKUP] {UDM_PATH.name} -> {BACKUP_PATH}")
else:
    print(f"[BACKUP-EXISTS] {BACKUP_PATH}")

# 2) 读源码
src = UDM_PATH.read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)

# 3) 检查 L1634 当前状态 (0-indexed 1633)
if len(lines) < 1640:
    print(f"[FATAL] 文件行数 {len(lines)} 不足 1640, 跳过")
    raise SystemExit(1)

print("[READ-CHECK] L1624-1640 当前内容:")
for i in range(1623, 1640):
    if i < len(lines):
        print(f"  {i+1:4d} | {lines[i]}", end="")

# 4) 找出待替换的 IndentationError 块
# 当前错误的 L1634-1637:
#   L1634:                         l2_future.cancel()
#   L1635:                     except Exception:
#   L1636:                         pass
#   L1637:                     remote_df = None
#
# 应改为:
#   L1634:                     try:
#   L1635:                         l2_future.cancel()
#   L1636:                     except Exception:
#   L1637:                         pass
#   L1638:                     remote_df = None

INDENT_20 = "                    "  # 20 空格
INDENT_24 = "                        "  # 24 空格
INDENT_28 = "                            "  # 28 空格

# 检查 L1634 是否是错误的 24 空格缩进
l1634 = lines[1633]
l1635 = lines[1634]
l1636 = lines[1635]
l1637 = lines[1636]

if not l1634.startswith(INDENT_24 + "l2_future.cancel()"):
    print(f"[FATAL] L1634 缩进异常, 期望 24 空格 + 'l2_future.cancel()', 实际: {l1634!r}")
    raise SystemExit(1)

if not l1635.startswith(INDENT_20 + "except Exception:"):
    print(f"[FATAL] L1635 缩进异常, 期望 20 空格 + 'except Exception:', 实际: {l1635!r}")
    raise SystemExit(1)

# 5) 构造新的 5 行替换 (L1634-L1638)
new_block = [
    INDENT_20 + "try:\n",
    INDENT_24 + "l2_future.cancel()\n",
    INDENT_20 + "except Exception:\n",
    INDENT_24 + "pass\n",
    INDENT_20 + "remote_df = None\n",
]

# 替换 lines[1633:1637] (4 行) -> 5 行
new_lines = lines[:1633] + new_block + lines[1637:]

print("\n[FIX] L1634-1637 修复为 try/except 块 (5 行):")
for i, ln in enumerate(new_block, start=1634):
    print(f"  {i:4d} | {ln}", end="")

# 6) 写回
new_src = "".join(new_lines)
UDM_PATH.write_text(new_src, encoding="utf-8")
print(f"\n[WRITE] {UDM_PATH} ({len(new_src)} chars)")

# 7) AST unparse 验证 (R104 §12 #5 铁律)
import ast
try:
    ast.parse(new_src, filename=str(UDM_PATH))
    print("[AST-OK] 语法解析成功, IndentationError 已修复")
except SyntaxError as e:
    print(f"[AST-FAIL] 仍有语法错误: {e}")
    print(f"[ROLLBACK] 还原备份")
    shutil.copy2(BACKUP_PATH, UDM_PATH)
    raise SystemExit(1)

# 8) 再次 Read 验证
print("\n[POST-READ] L1624-1650 修复后内容:")
final_src = UDM_PATH.read_text(encoding="utf-8")
final_lines = final_src.splitlines()
for i in range(1623, min(1650, len(final_lines))):
    print(f"  {i+1:4d} | {final_lines[i]}")

print(f"\n[SUCCESS] L1634 IndentationError 修复完成")
print(f"  备份: {BACKUP_PATH}")
print(f"  文件: {UDM_PATH}")
print(f"  行数变化: {len(lines)} -> {len(final_lines)} (+1)")
