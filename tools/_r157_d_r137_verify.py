"""R157-D R137 工具 false_positive 根因分析 (4 源验证 + 工具内部 API 调用)"""
import sys
import json
from pathlib import Path

sys.path.insert(0, '.')

from tools.report_sync_checker import (
    scan_r1_report,
    R1_SERVICE_CATALOG,
    _source2_grep_bootstrap,
    _source3_read_class,
    _source4_business_callers,
    _source5_file_existence,
    _judge_deviation_type,
    _judge_severity,
    BOOTSTRAP_FILE,
)

# 直接调用工具内部 API
project_root = Path('.')
search_dirs = ['core', 'plugins', 'gui', 'tests']

# 重点测试: PluginService (P1-13) + DatabaseMonitoringService (P2-28)
test_targets = [
    ('P1-13', 'PluginService', 'core/services/plugin_service.py', 123),
    ('P2-28', 'DatabaseMonitoringService', 'core/services/database_monitoring_service.py', 76),
]

print("=" * 80)
print("R137 工具内部 API 调用验证 (4 源)")
print("=" * 80)

for sid, class_name, file_path, line_number in test_targets:
    print(f"\n[{sid}] {class_name}")
    print("-" * 60)

    # 源 2: bootstrap.py 注册检查
    bootstrap_evidence = _source2_grep_bootstrap(project_root, class_name)
    print(f"  [源 2] bootstrap_evidence = {bootstrap_evidence!r}")

    is_registered = "未注册" not in bootstrap_evidence and "不存在" not in bootstrap_evidence
    print(f"  [源 2] is_registered = {is_registered}")

    # 源 3: 类定义 + docstring
    file_exists, actual_line, docstring = _source3_read_class(project_root, file_path, class_name)
    print(f"  [源 3] file_exists = {file_exists}, line = {actual_line}")
    print(f"  [源 3] docstring[:80] = {docstring[:80]!r}")

    # 源 4: 业务调用方
    caller_count, caller_files = _source4_business_callers(project_root, class_name, search_dirs)
    print(f"  [源 4] caller_count = {caller_count}")
    print(f"  [源 4] first 3 callers = {caller_files[:3]}")

    # 偏差判定
    deviation_type, deviation_desc = _judge_deviation_type(
        file_exists, actual_line, docstring, is_registered, project_root, class_name
    )
    severity = _judge_severity(deviation_type, caller_count)
    print(f"  [判定] deviation_type = {deviation_type}")
    print(f"  [判定] severity = {severity}")

print("\n" + "=" * 80)
print("全 R1 报告扫描 (实际 false_positive 验证)")
print("=" * 80)

# 跑完整 R1 扫描
deviations = scan_r1_report(project_root, search_dirs)
type_count = {}
for d in deviations:
    type_count[d.deviation_type] = type_count.get(d.deviation_type, 0) + 1

print(f"\n总偏差: {len(deviations)}")
print(f"类型分布: {type_count}")

# 列出 true_unregistered 项
print("\n[true_unregistered 项]")
for d in deviations:
    if d.deviation_type == 'true_unregistered':
        print(f"  - {d.target_id} {d.target_name} (severity={d.severity})")
        print(f"    bootstrap_evidence: {d.source2_grep!r}")

print("\n[fix_status=PENDING 项 (已注册但工具误报为 PENDING)]")
for d in deviations:
    if d.fix_status == 'PENDING':
        print(f"  - {d.target_id} {d.target_name} (type={d.deviation_type}, is_registered={d.is_registered})")
