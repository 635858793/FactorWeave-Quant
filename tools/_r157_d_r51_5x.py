"""R157-D R51 lint 5x 稳定性验证 (R6 §6.1 #4 工具集成要求)"""
import sys
import subprocess
import hashlib
import json
import os

# 运行 R51 lint 工具 5 次取 MD5
r51_path = 'tools/r51_silent_failure_lint.py'
md5_list = []
exit_codes = []
violation_counts = []

print("R51 lint 5x 稳定性验证")
print("=" * 80)

for i in range(5):
    try:
        result = subprocess.run(
            ['python', r51_path, '--format', 'json'],
            capture_output=True,
            text=True,
            timeout=120,
            cwd='.',
            encoding='utf-8',
            errors='ignore'
        )
        exit_code = result.returncode
        output = result.stdout + result.stderr
        md5 = hashlib.md5(output.encode('utf-8', errors='ignore')).hexdigest()
        md5_list.append(md5)
        exit_codes.append(exit_code)

        # 尝试解析 JSON
        try:
            data = json.loads(result.stdout)
            # 找 violations 字段
            if 'violations' in data:
                v = data['violations']
                p1_count = sum(1 for x in v if 'P1' in str(x.get('severity', '')))
                p2_count = sum(1 for x in v if 'P2' in str(x.get('severity', '')))
            else:
                p1_count = data.get('p1_violations', data.get('total_p1', 0))
                p2_count = data.get('p2_violations', data.get('total_p2', 0))
            total = p1_count + p2_count
            violation_counts.append(total)
            print(f"  Run {i+1}: exit={exit_code}, md5={md5}, p1={p1_count}, p2={p2_count}, total={total}")
        except (json.JSONDecodeError, Exception) as e:
            print(f"  Run {i+1}: exit={exit_code}, md5={md5}, parse_error={e}")
            violation_counts.append(0)
    except Exception as e:
        print(f"  Run {i+1}: ERROR: {e}")
        exit_codes.append(-1)
        md5_list.append('')

print(f"\nSTABLE: {len(set(md5_list)) == 1}")
print(f"Unique MD5: {len(set(md5_list))}")
print(f"All exit==0: {all(e == 0 for e in exit_codes)}")
print(f"Violation total range: {min(violation_counts) if violation_counts else 0} - {max(violation_counts) if violation_counts else 0}")
print(f"Violation total stable: {len(set(violation_counts)) == 1}")
