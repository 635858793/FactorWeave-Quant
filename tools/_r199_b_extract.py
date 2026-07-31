import json

data = json.load(open('tools/_r198_d_new_hvd.json', encoding='utf-8'))
print(f"Keys: {list(data.keys())}")
print(f"Total candidates: {len(data.get('candidates', []))}")
print(f"Phase: {data.get('r198_d_phase')}")
print(f"Date: {data.get('date')}")
print(f"New candidates count: {data.get('r198_new_candidates_count')}")
print(f"Priority breakdown: {data.get('priority_breakdown')}")
print("---")
# Look for NEW-198-D-01/02/03 or similar
for c in data.get('candidates', []):
    cid = c.get('id', c.get('hvd_id', c.get('hvd', '?')))
    title = c.get('title', c.get('type', c.get('description', '?')))
    pri = c.get('priority', '?')
    wl = c.get('workload_days', c.get('effort_days', '?'))
    if isinstance(title, str):
        title = title[:100]
    print(f"ID={cid} | P={pri} | WL={wl}d | T={title}")
