#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R194-A: 系统框架新增 HVD 立项 - 死代码 / 0 业务方扫描
- 扫描 R192-D 未覆盖目录
- 检测 0 调用方类/函数 (死代码候选)
- 检测 0 注册 Service
"""
import ast
import os
from pathlib import Path
from collections import Counter, defaultdict

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_DIRS = [
    "core/trading",
    "core/database",
    "core/cache",
    "core/indicators",
    "core/optimization",
    "core/ai",
    "core/agents",
    "core/async_management",
    "core/business",
    "core/multi_account",
    "core/performance",
    "core/feedback",
    "core/migration",
    "core/integration",
    "core/interfaces",
    "core/fundamental_data",
    "core/data",
]
SKIP = {"__pycache__", ".git", "node_modules", ".venv"}


def collect_definitions(file_path: Path) -> list:
    """提取文件中的类/函数定义 (顶层 + 嵌套)"""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except Exception:
        return []
    defs = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            defs.append((node.name, "class", node.lineno))
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defs.append((f"{node.name}.{item.name}", "method", item.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.append((node.name, "function", node.lineno))
    return defs


def collect_imports(file_path: Path) -> list:
    """提取 import 目标名 (简化)"""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except Exception:
        return []
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    imports.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.add((alias.asname or alias.name).split(".")[0])
    return imports


# 收集所有 .py 文件
all_py_files = []
for d in SCAN_DIRS:
    base = PROJECT_ROOT / d
    if not base.exists():
        continue
    for f in base.rglob("*.py"):
        if not any(s in f.parts for s in SKIP):
            all_py_files.append(f)

print(f"=== R194-A 新增目录扫描: {len(all_py_files)} 文件 ===\n")

# 提取所有定义 + import
all_defs = []  # [(name, kind, file, line)]
all_imports = set()  # 全项目 import 名
for f in all_py_files:
    defs = collect_definitions(f)
    for name, kind, ln in defs:
        all_defs.append((name, kind, str(f.relative_to(PROJECT_ROOT)), ln))
    all_imports.update(collect_imports(f))

# 找 0 业务方: def 不在 import 集合中
defs_with_name = [(n, k, f, l) for n, k, f, l in all_defs if not n.startswith("_")]
no_imports = [(n, k, f, l) for n, k, f, l in defs_with_name if n not in all_imports]

print(f"=== 候选死代码 (0 import, 但可能仍在用) ===")
print(f"总定义: {len(defs_with_name)}")
print(f"0 import (R104 §12 4 源验证 第 1 源): {len(no_imports)}")

# 按文件统计
no_imp_by_file = Counter(f for _, _, f, _ in no_imports)
print(f"\n按文件分布 (Top 30):")
for f, n in no_imp_by_file.most_common(30):
    print(f"  {n:3d} {f}")

# 找 0 内部调用: 类/函数 内方法 0 调用
internal_calls = set()
for f in all_py_files:
    try:
        content = f.read_text(encoding="utf-8")
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    internal_calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    internal_calls.add(node.func.attr)
    except Exception:
        pass

# 找 def 0 调用
defs_not_called = [(n, k, f, l) for n, k, f, l in defs_with_name
                   if n.split(".")[-1] not in internal_calls
                   and not n.startswith("__")]

print(f"\n=== 候选死方法 (0 调用, R104 §12 4 源验证 第 2 源) ===")
print(f"0 调用: {len(defs_not_called)}")
defs_by_file = Counter(f for _, _, f, _ in defs_not_called)
for f, n in defs_by_file.most_common(20):
    print(f"  {n:3d} {f}")
