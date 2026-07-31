#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R164-D AST 验证脚本: 验证 4 个 GUI 文件可解析 + 统计 exc_info=True 总数"""
import ast
import os
import re
import sys

FILES = [
    (r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\widgets\trading_widget.py", 1),
    (r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\widgets\performance\tabs\risk_control_center_tab.py", 0),
    (r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\widgets\performance\tabs\trading_execution_monitor_tab.py", 21),
    (r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\widgets\enhanced_ui\order_book_widget.py", 15),
]

print("=" * 80)
print("R164-D R+1 round 独立验证: AST 语法 + exc_info=True 计数")
print("=" * 80)

total_exc_info = 0
total_expected = 0
all_ok = True

for path, expected in FILES:
    name = os.path.basename(path)
    print(f"\n[{name}] 预期 exc_info 修复数: {expected}")
    
    # 1. 文件存在性
    if not os.path.exists(path):
        print(f"  ❌ 文件不存在: {path}")
        all_ok = False
        continue
    
    # 2. AST 语法验证
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content)
        print(f"  ✅ AST 解析通过 (文件大小: {len(content)} bytes)")
    except SyntaxError as e:
        print(f"  ❌ AST 解析失败: {e}")
        all_ok = False
        continue
    
    # 3. exc_info=True 计数
    # 按行匹配, 统计含 'exc_info=True' 的行
    lines = content.splitlines()
    exc_info_lines = []
    for i, line in enumerate(lines, 1):
        if re.search(r"exc_info\s*=\s*True", line):
            exc_info_lines.append((i, line.strip()))
    
    count = len(exc_info_lines)
    total_exc_info += count
    total_expected += expected
    
    if count >= expected:
        print(f"  ✅ exc_info=True 出现 {count} 次 (≥ 预期 {expected})")
    else:
        print(f"  ⚠️  exc_info=True 出现 {count} 次 (预期 {expected}, 不足!)")
        all_ok = False
    
    # 4. 列出所有 exc_info=True 位置
    if exc_info_lines:
        print(f"  详细位置:")
        for ln, txt in exc_info_lines[:30]:
            print(f"    L{ln}: {txt[:100]}")

print("\n" + "=" * 80)
print(f"总计: 实际 exc_info=True 出现 {total_exc_info} 次, 预期 {total_expected} 处修复")
print(f"结果: {'✅ 全部通过' if all_ok else '❌ 存在偏差'}")
print("=" * 80)
