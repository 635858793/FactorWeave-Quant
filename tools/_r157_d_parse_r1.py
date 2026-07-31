import json
import sys

with open('tools/_r156_r_plus1_r1_scan.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

stats = data.get('statistics', {})
print('=== R137 报告同步扫描结果 (R156 R+1 验证) ===')
print(f'总偏差数: {stats.get("total_deviations")}')
print(f'P0: {stats.get("p0_count")}')
print(f'P1: {stats.get("p1_count")}')
print(f'P2: {stats.get("p2_count")}')
print(f'INFO: {stats.get("info_count")}')
print()
print('=== 偏差类型分布 ===')
print(f'false_report: {stats.get("false_report_count")}')
print(f'true_unregistered: {stats.get("true_unregistered_count")}')
print(f'physically_deleted: {stats.get("physically_deleted_count")}')
print(f'file_not_exist: {stats.get("file_not_exist_count")}')
print(f'design_decision: {stats.get("design_decision_count")}')
print(f'deprecated: {stats.get("deprecated_count")}')
print()
print('=== 阈值告警 ===')
print(f'alert: {data.get("alert")}')
print(f'alert_messages: {data.get("alert_messages")}')
print()
print('=== file_not_exist 详情 ===')
for d in data.get('deviations', []):
    if d.get('deviation_type') == 'file_not_exist':
        print(f'  {d["deviation_id"]} | {d["target_name"]} | {d["target_path"]}')
print()
print('=== false_report 详情 (前 5) ===')
count = 0
for d in data.get('deviations', []):
    if d.get('deviation_type') == 'false_report' and count < 5:
        print(f'  {d["deviation_id"]} | {d["target_name"]} | docstring={d.get("docstring_status")}')
        count += 1
print()
print('=== 时滞告警 ===')
for w in data.get('time_lag_warnings', []):
    print(f'  {w}')
