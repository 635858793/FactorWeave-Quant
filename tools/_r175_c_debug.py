#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调试: 单方法 _execute_buy AST 锁分析"""
import ast
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")
src = (PROJECT_ROOT / "core/trading_engine.py").read_text(encoding='utf-8')
tree = ast.parse(src)

# 找 _execute_buy
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == '_execute_buy':
        method = node
        break

# 直接打印所有 with 块
print("=" * 60)
print("DIRECT AST.WALK with 块 (扁平, R104 不推荐但用作基线)")
print("=" * 60)
for n in ast.walk(method):
    if isinstance(n, ast.With):
        for item in n.items:
            ctx = item.context_expr
            if isinstance(ctx, ast.Attribute):
                attr_name = ctx.attr
            else:
                attr_name = str(ast.dump(ctx))
            print(f"  L{n.lineno}-{n.end_lineno} with {attr_name}")

print()
print("=" * 60)
print("AST unparse 验证 (R104 §12 #5)")
print("=" * 60)
method_src = ast.unparse(method)
print(f"unparse length: {len(method_src)} chars")
# 找 with 块
unparse_tree = ast.parse(method_src)
for n in ast.walk(unparse_tree):
    if isinstance(n, ast.With):
        for item in n.items:
            ctx = item.context_expr
            if isinstance(ctx, ast.Attribute):
                attr_name = ctx.attr
            else:
                attr_name = str(ast.dump(ctx))
            print(f"  L{n.lineno}-{n.end_lineno} with {attr_name}")
print()
print("=" * 60)
print("with self._positions_lock 字符串计数 (R104 警示, 仅参考)")
print("=" * 60)
print(f"Count: {method_src.count('with self._positions_lock:')}")
print(f"Count: {method_src.count('with self._cache_lock:')}")
