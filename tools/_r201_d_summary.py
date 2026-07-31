import json
d = json.load(open('tools/_r201_d_results.json', encoding='utf-8'))
print(f"Total files: {len(d['files'])}")
print(f"Total ops: {d['total_ops']}")
print(f"Factory calls: {d['factory_calls']}")
print(f"f-string violations: {d['fstring_violations']}")
print()
for f in d['files']:
    relevant = f['factory_calls'] + f['fstring_violations'] + f['str_concat_violations'] + f['format_violations']
    ratio = f['factory_calls'] / relevant if relevant > 0 else 0
    print(f"{f['file']:60s} factory={f['factory_calls']:2d} fstring={f['fstring_violations']:2d} relevant={relevant:2d} ratio={ratio:.0%}")
