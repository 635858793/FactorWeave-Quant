"""Dry-run: 验证 10 处 old_text 是否唯一匹配"""
import sys
sys.path.insert(0, r'D:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tools')
from _r180_b_ext_fix_remaining_exc_info import FIXES, TARGET

with open(TARGET, 'r', encoding='utf-8') as f:
    content = f.read()

print('=== DRY-RUN: 验证每处 old_text 是否唯一匹配 ===')
all_ok = True
for fix in FIXES:
    old = fix['old']
    name = fix['name']
    count = content.count(old)
    if count == 1:
        print(f'[OK] {name}: 1 match')
    elif count == 0:
        print(f'[MISS] {name}: 0 match (NOT FOUND)')
        all_ok = False
    else:
        print(f'[DUP] {name}: {count} matches (NEED more context)')
        all_ok = False

if all_ok:
    print('\n[ALL OK] 10 处全部唯一匹配, 可安全实施')
else:
    print('\n[FAIL] 部分匹配异常, 需先调整 old_text')
