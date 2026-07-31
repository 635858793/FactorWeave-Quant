"""R199-A 扫描结果分析"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
results_file = ROOT / 'tools' / '_r199_a_results.json'

if not results_file.exists():
    print(f"ERROR: {results_file} not found")
    sys.exit(1)

data = json.loads(results_file.read_text(encoding='utf-8'))

print('=' * 80)
print('R199-A 软解析扫描结果摘要')
print('=' * 80)
print(f"总扫描位置: {data['total']}")
print(f"P0 (P0 业务核心 + 静默失败): {len(data['P0'])}")
print(f"P1 (静默失败 / P0 业务):    {len(data['P1'])}")
print(f"P2 (无显式日志):            {len(data['P2'])}")
print(f"P3 (其他):                  {len(data['P3'])}")
print(f"已合规 (try+exc_info+error): {len(data['already_safe'])}")

print('\n' + '=' * 80)
print('P2 前 30 项 (无显式日志, 需关注):')
print('=' * 80)
for r in data['P2'][:30]:
    flag = '[!]' if r['has_default_none'] else '   '
    print(f"  {flag} {r['file']}:{r['line']}  default_none={r['has_default_none']}")
    print(f"      {r['call'][:100]}")

print('\n' + '=' * 80)
print('P3 前 20 项 (其他):')
print('=' * 80)
for r in data['P3'][:20]:
    print(f"  {r['file']}:{r['line']}  {r['call'][:80]}")

print('\n' + '=' * 80)
print('已合规 33 项 (前 20):')
print('=' * 80)
for r in data['already_safe'][:20]:
    print(f"  [OK] {r['file']}:{r['line']}  {r['call'][:80]}")
