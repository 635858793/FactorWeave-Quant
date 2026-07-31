"""R174 审计数据收集脚本 (子智能体 C)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'tests'))
from test_r174_audit_lock_architecture import audit_lock_architecture_for_file

PROJECT_ROOT = Path(__file__).parent.parent
target_files = [
    'core/events/event_bus.py',
    'core/trading/order_executor.py',
    'core/services/trading_service.py',
    'core/services/unified_data_manager.py',
    'core/risk_manager.py',
    'core/risk_monitoring/enhanced_risk_monitor.py',
    'core/trading/account_manager.py',
    'core/trading_engine.py',
    'core/services/cache_service.py',
    'core/services/ai_selection_integration_service.py',
]

print('=' * 80)
print('R174 子智能体 C 锁架构审计报告数据')
print('=' * 80)

for rel_path in target_files:
    path = PROJECT_ROOT / rel_path
    if not path.exists():
        print(f'[SKIP] {rel_path}')
        continue
    result = audit_lock_architecture_for_file(path)
    print(f'\n[FILE] {rel_path}')
    print(f'  lock_attrs ({len(result["lock_attrs"])}): {result["lock_attrs"]}')
    print(f'  long_locks: {len(result["long_locks"])} 处')
    for ll in result['long_locks'][:5]:
        print(f'    L{ll["with_line"]}-{ll["with_end_line"]} ({ll["block_lines"]} lines) method={ll["method"]} lock={ll["lock_keys"]}')
    print(f'  nested_violations: {len(result["nested_violations"])} 处')
    for nv in result['nested_violations'][:5]:
        print(f'    L{nv["line"]} type={nv["type"]} method={nv.get("method", "?")} parent={nv.get("parent_locks", [])} nested={nv.get("nested_locks", [])}')
