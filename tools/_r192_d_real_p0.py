#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R192-D 详细分析 v3 - 区分模块级 vs 方法级 try/except"""
import json
import sys
from collections import Counter, defaultdict
import ast

sys.stdout.reconfigure(encoding='utf-8')

with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_r192_d_scan.json', encoding='utf-8') as f:
    data = json.load(f)
data = [v for v in data if 'error' not in v]
for v in data:
    v['file'] = v['file'].replace('\\', '/')

# 重新分析, 区分模块级 vs 方法级
PROJECT_ROOT = r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui'

def get_handler_context(file_path, handler_line):
    """分析一个 except handler 是模块级还是方法级"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception:
        return None, None, None

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.lineno == handler_line:
            # 找到父节点: 可能是 Module, FunctionDef, AsyncFunctionDef
            for parent in ast.walk(tree):
                if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if parent.lineno <= handler_line <= (parent.end_lineno or 0):
                        # 检查 handler body
                        body = node.body
                        if len(body) == 0:
                            return 'method', parent.name, 'EMPTY'
                        if len(body) == 1 and isinstance(body[0], ast.Pass):
                            return 'method', parent.name, 'PASS'
                        # Check for variable assignment (optional import pattern)
                        if len(body) >= 1 and all(isinstance(s, ast.Assign) for s in body):
                            return 'module_or_method', parent.name, 'ASSIGN'
                        return 'method', parent.name, f'OTHER ({len(body)} stmts)'
            return 'module', None, 'MODULE_LEVEL'
    return None, None, None

# 重新分类 P0 violations
real_p0 = []  # 方法级 + pass/empty
module_level_p0 = []  # 模块级 optional imports
import_error_p0 = []  # ImportError pass (acceptable)

for v in data:
    if v.get('severity') != 'P0':
        continue
    fpath = PROJECT_ROOT + '/' + v['file']
    et = v.get('exception_type', '')
    line = v.get('line', 0)

    if 'ImportError' in et:
        import_error_p0.append(v)
        continue

    ctx, parent_name, body_type = get_handler_context(fpath, line)
    if ctx is None:
        module_level_p0.append(v)
        continue
    if ctx in ('module',):
        module_level_p0.append(v)
        continue
    if body_type == 'ASSIGN':
        # 模块级 optional import pattern
        module_level_p0.append(v)
        continue
    # 真实方法级 P0
    real_p0.append((v, parent_name, body_type, ctx))

out_lines = []
out_lines.append(f"=== 真实 P0 静默失败 (方法级 + pass/empty, 排除模块级 ImportError/optional import) ===")
out_lines.append(f"  真实 P0 数: {len(real_p0)}")
out_lines.append(f"  模块级 optional P0: {len(module_level_p0)}")
out_lines.append(f"  ImportError P0 (合规): {len(import_error_p0)}")

# 按文件统计
by_file = defaultdict(lambda: {'real_p0': [], 'module_p0': 0})
for v, parent, body, ctx in real_p0:
    by_file[v['file']]['real_p0'].append((v.get('line'), parent, body, v.get('exception_type'), v.get('body_summary', [])[:1]))
for v in module_level_p0:
    by_file[v['file']]['module_p0'] += 1

out_lines.append("")
out_lines.append("=== 真实 P0 按文件汇总 (方法级 pass/empty) ===")
sorted_files = sorted(by_file.items(), key=lambda x: (-len(x[1]['real_p0']), -x[1]['module_p0']))
for f, info in sorted_files[:30]:
    if info['real_p0']:
        out_lines.append(f"  REAL_P0={len(info['real_p0']):2d}  module_P0={info['module_p0']:3d}  {f}")

# Top 真实 P0 详情
out_lines.append("")
out_lines.append("=== 真实 P0 详情 (Top 50) ===")
all_real = []
for f, info in by_file.items():
    for line, parent, body, et, bsum in info['real_p0']:
        all_real.append((f, line, parent, body, et, bsum))
all_real.sort(key=lambda x: x[1])
for f, line, parent, body, et, bsum in all_real[:50]:
    out_lines.append(f"  L{line:4d} {f} | {parent}() | {et} | {body}: {bsum}")

# Save
with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_r192_d_real_p0.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out_lines))

print("DONE")
