import json
import sys

with open('tools/_r156_r_plus1_r1_scan.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Open output file with UTF-8 encoding
out = open('tools/_r157_d_p0_full.txt', 'w', encoding='utf-8')

def safe_write(s):
    # Replace problematic chars
    s = s.replace('\u2705', '[OK]').replace('\u274c', '[ERR]').replace('\u26a0\ufe0f', '[WARN]').replace('\U0001f534', '[RED]').replace('\U0001f7e1', '[YELLOW]').replace('\U0001f4a5', '[FIRE]')
    out.write(s + '\n')

safe_write('=== true_unregistered (P0) Details ===')
for d in data.get('deviations', []):
    if d.get('deviation_type') == 'true_unregistered':
        safe_write('  %s | %s | %s' % (d["deviation_id"], d["target_name"], d["target_path"]))
        safe_write('    severity: %s' % d.get("severity"))
        safe_write('    bootstrap_evidence: %s' % d.get('source2_grep'))
        safe_write('    codepgraph: %s' % d.get('source1_codepgraph'))
        safe_write('    read: %s' % d.get('source3_read'))
        safe_write('    business_chain: %s' % d.get('source4_business_chain'))
        safe_write('    file_exists: %s' % d.get('file_exists'))
        safe_write('    is_registered: %s' % d.get('is_registered'))
        safe_write('    business_caller_count: %d' % d.get("business_caller_count"))
        safe_write('    r85_step1: %s' % d.get('r85_step1'))
        safe_write('    r85_step2: %s' % d.get('r85_step2'))
        safe_write('    r85_step3: %s' % d.get('r85_step3'))
        safe_write('    r85_step4: %s' % d.get('r85_step4'))
        safe_write('')

safe_write('=== All P0 (severity) ===')
for d in data.get('deviations', []):
    if d.get('severity') == 'P0':
        safe_write('  %s | %s | type=%s' % (d["deviation_id"], d["target_name"], d.get("deviation_type")))

safe_write('')
safe_write('=== file_not_exist (P2) Details ===')
for d in data.get('deviations', []):
    if d.get('deviation_type') == 'file_not_exist':
        safe_write('  %s | %s | %s' % (d["deviation_id"], d["target_name"], d["target_path"]))

safe_write('')
safe_write('=== false_report Sample (first 3) ===')
count = 0
for d in data.get('deviations', []):
    if d.get('deviation_type') == 'false_report' and count < 3:
        safe_write('  %s | %s | %s | docstring=%s' % (
            d["deviation_id"], d["target_name"], d.get("target_path"),
            d.get("docstring_status")
        ))
        count += 1

safe_write('')
safe_write('=== Summary ===')
stats = data.get('statistics', {})
safe_write('Total: %d, P0: %d, P1: %d, P2: %d' % (
    stats.get("total_deviations"),
    stats.get("p0_count"),
    stats.get("p1_count"),
    stats.get("p2_count")
))
safe_write('false_report: %d, true_unregistered: %d, file_not_exist: %d' % (
    stats.get("false_report_count"),
    stats.get("true_unregistered_count"),
    stats.get("file_not_exist_count")
))

out.close()
print('Done. Output: tools/_r157_d_p0_full.txt')
