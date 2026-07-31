import json
with open('tools/_r200_a_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(f"Files scanned: {data['files_scanned']}")
print(f"Files with violations: {data['files_with_violations']}")
print(f"Total violations: {data['total_violations']}")
print(f"R199-D reported: {data['r199_d_reported_count']}")
print(f"Sample match: {data['r199_d_sample_match']}")
print()
print("Top 5 files by violation count:")
for f, cnt in sorted(data['violations_by_file'].items(), key=lambda x: -x[1])[:5]:
    print(f"  {cnt:3d} 处: {f}")
