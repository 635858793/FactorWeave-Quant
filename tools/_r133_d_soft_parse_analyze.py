"""R133 子智能体 D: 软解析 + 死代码 联合分析脚本"""
import json
import sys

def main():
    data = json.load(open('.trae/reports/monitoring/soft_parse_monitor_2026-07-14.json', encoding='utf-8'))
    print('Summary:', json.dumps(data['summary'], indent=2))
    print()
    print('=== P1 Violations ===')
    for v in data['violations']:
        if v['severity'] == 'P1':
            print(f"  {v['file_path']}:{v['line_number']} {v['pattern']} {v['service_type']}")
            print(f'    {v["line_content"]}')
    print()
    print('=== By service_type ===')
    for k, v in sorted(data['by_service_type'].items(), key=lambda x: -x[1]):
        print(f'  {k}: {v}')
    print()
    print('=== By file (top 10) ===')
    for k, v in sorted(data['by_file'].items(), key=lambda x: -x[1])[:10]:
        print(f'  {k}: {v}')
    print()
    print('R51 step distribution:', json.dumps(data['r51_step_distribution'], indent=2))

if __name__ == '__main__':
    main()
