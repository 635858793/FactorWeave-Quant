# -*- coding: utf-8 -*-
"""R237-C 子智能体 C 扫描脚本."""
import sys
import json

sys.path.insert(0, 'tools')
from orphan_pub_scanner_v2 import ORPHANPubScannerV2

scanner = ORPHANPubScannerV2(root='.', subdirs=['core', 'gui', 'tests'])
result = scanner.scan()

# 保存完整结果
with open('.trae/reports/rounds/raw/audit_r237_c_v2_scanner.json', 'w', encoding='utf-8') as f:
    json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

s = result.summary
print('=' * 60)
print('R237-C 子智能体 C v2 扫描器结果')
print('=' * 60)
print('Files scanned:', s['scanned_files'])
print('Publish count:', s['publish_count'])
print('Subscribe count:', s['subscribe_count'])
print('ORPHAN_PUB count:', s['orphan_pub_count'])
print('ORPHAN_SUB count:', s['orphan_sub_count'])
print('Pattern distribution:')
for k, v in s['pattern_distribution'].items():
    print(f'  {k}: {v}')
print('---ORPHAN_PUB list (top 30):---')
for o in result.orphan_pub[:30]:
    print(f"  {o['event_name']} (line {o['first_publish_line']})")
print('---ORPHAN_PUB list (30-108):---')
for o in result.orphan_pub[30:]:
    print(f"  {o['event_name']} (line {o['first_publish_line']})")
print('---ORPHAN_SUB list (top 30):---')
for o in result.orphan_sub[:30]:
    print(f"  {o}")
