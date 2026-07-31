#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R164-D 详细验证: trading_widget.py 语法错误根因分析"""
import ast
import sys

path = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\widgets\trading_widget.py"
try:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    tree = ast.parse(content)
    print("AST 解析: ✅ OK")
except SyntaxError as e:
    print(f"AST 解析: ❌ SyntaxError at line {e.lineno}, offset {e.offset}")
    print(f"错误信息: {e.msg}")
    print(f"错误文本: {e.text!r}")
    
    # 详细定位
    lines = content.splitlines()
    if e.lineno:
        print(f"\n错误上下文 (line {e.lineno-1} ~ {e.lineno+1}):")
        for i in range(max(0, e.lineno-2), min(len(lines), e.lineno+1)):
            marker = ">>>" if i+1 == e.lineno else "   "
            print(f"  {marker} L{i+1}: {lines[i]}")

# 检查 R164-B 子智能体 A 修复的痕迹
print("\n" + "=" * 80)
print("检查 R164-B 子智能体 A 是否修复了语法错误")
print("=" * 80)
lines = content.splitlines()
for i, line in enumerate(lines, 1):
    if "更新股票信息失败" in line:
        print(f"L{i}: {line!r}")
        # 上下文
        for j in range(max(0, i-3), min(len(lines), i+2)):
            marker = ">>>" if j+1 == i else "   "
            print(f"  {marker} L{j+1}: {lines[j]!r}")
        print()
