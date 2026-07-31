#!/usr/bin/env python3
"""R173-C 缓存键硬编码扫描"""
import os
import re

results = []
for root, dirs, files in os.walk('.'):
    # skip pycache and hidden dirs
    dirs[:] = [d for d in dirs if d != '__pycache__' and not d.startswith('.') and d != 'node_modules']
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(root, f)
        try:
            with open(path, 'r', encoding='utf-8') as fp:
                for i, line in enumerate(fp, 1):
                    # 查找硬编码的 cache_key (f-string 形式), 排除 _make_kdata_cache_key
                    if re.search(r'cache_key\s*=\s*f["\']', line) and '_make_kdata_cache_key' not in line:
                        # 排除合理的辅助键 (bond/fund/index list/info/holdings/yield_curve/components 模式)
                        if any(kw in line.lower() for kw in ['bond_list', 'bond_info', 'yield_curve',
                                                              'fund_list', 'fund_info', 'fund_holdings',
                                                              'index_list', 'index_info', 'index_components',
                                                              'fund_nav', 'kdata_', 'stock_', 'quote_']):
                            results.append((path, i, line.strip()[:140]))
        except Exception as e:
            print(f'Error reading {path}: {e}')

# 也搜索 plugins/
for root, dirs, files in os.walk('./plugins'):
    dirs[:] = [d for d in dirs if d != '__pycache__' and not d.startswith('.') and d != 'node_modules']
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(root, f)
        try:
            with open(path, 'r', encoding='utf-8') as fp:
                for i, line in enumerate(fp, 1):
                    if re.search(r'cache_key\s*=\s*f["\']', line) and '_make_kdata_cache_key' not in line:
                        results.append((path, i, line.strip()[:140]))
        except Exception as e:
            print(f'Error reading {path}: {e}')

print(f"Total hardcoded cache_key (f-string form, not factory): {len(results)}")
print()
for path, line_no, line in results[:50]:
    print(f"  {path}:{line_no}: {line}")
