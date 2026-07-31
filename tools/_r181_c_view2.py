"""查看剩余 P0 违规 (R181-C 修复后)"""
import json
d = json.load(open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\.r181_c_cache_key_audit_v2.json', encoding='utf-8'))
print(f"Total v2: {d['total_violations']}, by_severity: {d['by_severity']}")
print("=" * 80)
for v in d['violations']:
    if v['severity'] == 'P0':
        print(f"{v['file']}:{v['line']} {v['func_name']}")
        print(f"  KEY: {v['cache_key_expr'][:120]}")
        print()
