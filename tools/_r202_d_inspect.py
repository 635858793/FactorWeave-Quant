import json
from collections import Counter

with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tools\_r202_d_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

all_cands = []
for dim in ['dim_1_dead_code', 'dim_2_lock_cache_eventbus', 'dim_3_compat_layer', 'dim_4_orphan_pub_sub', 'dim_5_multi_account_ai_perf']:
    for c in data[dim]:
        c['dim'] = dim
        all_cands.append(c)

print(f'Total: {len(all_cands)}')
prio_counter = Counter(c.get('candidate_priority', 'N/A') for c in all_cands)
type_counter = Counter(c.get('type', 'N/A') for c in all_cands)
print(f'Priority: {dict(prio_counter)}')
print(f'Type: {dict(type_counter)}')
print()

print('=== P1 候选详情 (前 20) ===')
for i, c in enumerate([x for x in all_cands if x.get('candidate_priority') == 'P1'][:20], 1):
    print(f'{i}. [{c["dim"]}] [{c["type"]}] {c}')

print()
print('=== P2 候选详情 (前 10) ===')
for i, c in enumerate([x for x in all_cands if x.get('candidate_priority') == 'P2'][:10], 1):
    print(f'{i}. [{c["dim"]}] [{c["type"]}] {c}')

print()
print('=== ORPHAN_PUB 详情 ===')
for c in [x for x in all_cands if x.get('type') == 'ORPHAN_PUB'][:10]:
    print(f'  - {c["event"]} count={c.get("publish_count")} priority={c.get("candidate_priority")}')

print()
print('=== ORPHAN_SUB 详情 ===')
for c in [x for x in all_cands if x.get('type') == 'ORPHAN_SUB'][:10]:
    print(f'  - {c["event"]} count={c.get("subscribe_count")} priority={c.get("candidate_priority")}')

print()
print('=== ai_soft_parse / cache_key_fstring / lock_nesting 详情 ===')
for type_name in ['ai_soft_parse', 'cache_key_fstring', 'lock_nesting', 'string_event_unregistered', 'multi_account_isolation_weak']:
    print(f'\n  --- {type_name} ---')
    for c in [x for x in all_cands if x.get('type') == type_name][:5]:
        ctype = c.get('type', '')
        cf = c.get('file', c.get('event', ''))[:80]
        ccount = c.get('fstring_count') or c.get('soft_parse_count') or c.get('publish_count') or c.get('subscribe_count') or c.get('method', '')
        cprio = c.get('candidate_priority')
        print('  -', cf, 'count=', ccount, 'priority=', cprio)
