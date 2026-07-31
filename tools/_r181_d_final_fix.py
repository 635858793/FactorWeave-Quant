#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R181-D 最终修复: 修复 strategy_service.py L3263 唯一剩余违规"""
import sys
from pathlib import Path

fp = Path("core/services/strategy_service.py")
if not fp.exists():
    print(f"[ERROR] 文件不存在: {fp}")
    sys.exit(1)

content = fp.read_text(encoding="utf-8")

# 1. 修复 L3263 except 块内的 logger.warning
old_3263 = '            logger.warning(f"[STRATEGY.CLEANUP.HEALTH_ALERT.PUBLISH.ERROR] err={pub_e}")'
new_3263 = '            logger.warning(f"[STRATEGY.CLEANUP.HEALTH_ALERT.PUBLISH.ERROR] err={pub_e}", exc_info=True)  # R181-D P1 修复 (R51 §7.1 #5 强约束)'

count = content.count(old_3263)
if count == 1:
    content = content.replace(old_3263, new_3263)
    print("[OK] L3263 已修复")
else:
    print(f"[ERROR] L3263 模式匹配数 {count} != 1")
    sys.exit(1)

# 验证语法
import ast
try:
    ast.parse(content, filename=str(fp))
    print("[OK] 语法验证通过")
except SyntaxError as e:
    print(f"[ERROR] 语法错误: {e}")
    sys.exit(1)

fp.write_text(content, encoding="utf-8")
print("[OK] 文件已保存")
