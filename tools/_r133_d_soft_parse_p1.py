"""R133 子智能体 D: 软解析 P1 详细分析"""
import json
from collections import Counter

def main():
    data = json.load(open('.trae/reports/monitoring/soft_parse_monitor_2026-07-14.json', encoding='utf-8'))
    print('=== P1 详细 (4处) ===')
    for v in data['violations']:
        if v['severity'] == 'P1':
            print(f"  {v['file_path']}:{v['line_number']}")
            print(f'    pattern={v["pattern"]} type={v["service_type"]} R51_step={v["r51_step"]}')
            print(f'    content: {v["line_content"][:80]}')
            print(f'    remediation: {v["remediation"][:80]}')
            print()

    print('=== All violations by (step, severity) ===')
    step_count = Counter((v['r51_step'], v['severity']) for v in data['violations'])
    for (step, sev), c in sorted(step_count.items()):
        print(f'  Step {step} {sev}: {c}')

    print('\n=== Production files with soft parse (excluding tests/) ===')
    prod_v = [v for v in data['violations'] if 'tests/' not in v['file_path'] and 'test_' not in v['file_path']]
    print(f'Total production: {len(prod_v)}')
    prod_by_step = Counter((v['r51_step'], v['severity']) for v in prod_v)
    for (step, sev), c in sorted(prod_by_step.items()):
        print(f'  Step {step} {sev}: {c}')

if __name__ == '__main__':
    main()
