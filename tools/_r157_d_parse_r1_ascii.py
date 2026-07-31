import json
import sys

with open('tools/_r156_r_plus1_r1_scan.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

stats = data.get('statistics', {})
print('=== R137 Report Sync Scan (R156 R+1 Validation) ===')
print('Total deviations: %d' % stats.get("total_deviations"))
print('P0: %d' % stats.get("p0_count"))
print('P1: %d' % stats.get("p1_count"))
print('P2: %d' % stats.get("p2_count"))
print('INFO: %d' % stats.get("info_count"))
print()
print('=== Deviation Type Distribution ===')
print('false_report: %d' % stats.get("false_report_count"))
print('true_unregistered: %d' % stats.get("true_unregistered_count"))
print('physically_deleted: %d' % stats.get("physically_deleted_count"))
print('file_not_exist: %d' % stats.get("file_not_exist_count"))
print('design_decision: %d' % stats.get("design_decision_count"))
print('deprecated: %d' % stats.get("deprecated_count"))
print()
print('=== Threshold Alert ===')
print('alert: %s' % data.get("alert"))
print('alert_messages: %s' % data.get("alert_messages"))
print()
print('=== file_not_exist Details ===')
for d in data.get('deviations', []):
    if d.get('deviation_type') == 'file_not_exist':
        print('  %s | %s | %s' % (d["deviation_id"], d["target_name"], d["target_path"]))
print()
print('=== false_report (first 5) ===')
count = 0
for d in data.get('deviations', []):
    if d.get('deviation_type') == 'false_report' and count < 5:
        print('  %s | %s | docstring=%s' % (d["deviation_id"], d["target_name"], d.get("docstring_status")))
        count += 1
print()
print('=== Time Lag Warnings ===')
for w in data.get('time_lag_warnings', []):
    print('  %s' % w)
print()
print('=== Performance ===')
print('files_scanned: %d' % data.get('performance', {}).get('files_scanned'))
print('scan_duration_ms: %d' % data.get('performance', {}).get('scan_duration_ms'))
