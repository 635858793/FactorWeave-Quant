"""Restore R180-B-ext after-fix version and verify"""
import shutil
import re

after = r'D:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_archive\backups_2026_07_24\core_services_unified_data_manager_r180bext_after.bak'
current = r'D:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\unified_data_manager.py'
shutil.copy2(after, current)
print('Restored R180-B-ext after-fix version')

with open(current, 'r', encoding='utf-8') as f:
    content = f.read()
r180_markers = re.findall(r'R180-B-ext (P0|P1|P2)', content)
p0 = r180_markers.count('P0')
p1 = r180_markers.count('P1')
p2 = r180_markers.count('P2')
print(f'R180-B-ext markers: P0={p0}, P1={p1}, P2={p2} (total {len(r180_markers)})')
print('Expected: P0=1, P1=8, P2=1 (total 10)')
assert p0 == 1, f'P0 should be 1, got {p0}'
assert p1 == 8, f'P1 should be 8, got {p1}'
assert p2 == 1, f'P2 should be 1, got {p2}'
assert len(r180_markers) == 10, f'total should be 10, got {len(r180_markers)}'
print('OK')
