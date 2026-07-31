#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R194-A: 扫描 R192-D 未覆盖的目录, 找死代码 / 0 业务方 / 框架缺陷 HVD 立项
- core/trading/ (27 文件, 关键业务, R192-D 未扫描)
- core/database/ (R192-D 未扫描, 数据层)
- core/cache/ (R192-D 未扫描, 缓存层)
- core/indicators/ (R192-D 未扫描, 指标层)
- core/database/ 详查
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
    "core/database",
    "core/feedback",
    "core/feedback",
    "core/migration",
    "core/integration",
    "core/indicators",
    "core/interfaces",
    "core/fundamental_data",
    "core/data",
]
SKIP = {"__pycache__", ".git", "node_modules"}

def quick_silent_scan(file_path: Path) -> list:
    """快速扫描 except 块内是否静默"""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except Exception:
        return []

    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            handler_body = node.body
            loggers = []
            for stmt in handler_body:
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    call = stmt.value
                    if isinstance(call.func, ast.Attribute):
                        method = call.func.attr
                        if method in ("debug", "info", "warning", "error", "critical", "exception"):
                            loggers.append(method)
            if not loggers:
                body_desc = []
                for stmt in handler_body:
                    try:
                        body_desc.append(ast.unparse(stmt)[:60])
                    except Exception:
                        body_desc.append("...")
                results.append({
                    "file": str(file_path.relative_to(PROJECT_ROOT)),
                    "line": node.lineno,
                    "exc": ast.unparse(node.type) if node.type else "Exception",
                    "body": body_desc[:2],
                })
    return results


# 扫描各目录
print(f"\n=== R194-A 未覆盖子目录静默失败扫描 ===")
total = 0
for d in SCAN_DIRS:
    base = PROJECT_ROOT / d
    if not base.exists():
        print(f"\n{d}: ❌ 目录不存在")
        continue
    files = list(base.rglob("*.py"))
    files = [f for f in files if not any(s in f.parts for s in SKIP)]
    if not files:
        continue
    dir_violations = []
    for f in files:
        dir_violations.extend(quick_silent_scan(f))
    cnt = Counter(v["file"] for v in dir_violations)
    print(f"\n{d}: {len(files)} 文件, {len(dir_violations)} 静默块")
    for f, n in cnt.most_common(15):
        print(f"  {n:3d} {f}")
    total += len(dir_violations)

print(f"\n=== 总计: {total} 静默块 ===")
