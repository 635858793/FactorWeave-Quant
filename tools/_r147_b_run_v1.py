"""
R147 子智能体 B - 4 源验证 AST 扫描 v1 (执行入口)
"""
import sys
import json
from pathlib import Path

# 添加 tools/ 到路径
sys.path.insert(0, str(Path(__file__).parent))
from _r147_b_scan_v1 import scan_file

FILES = [
    'core/services/cache_service.py',
    'core/trading/interfaces/ctp_trading_interface.py',
    'core/trading/order_executor.py',
    'core/trading_engine.py',
    'core/risk_manager.py',
    'core/asset_database_manager.py',
]

data = {}
grand = {'total': 0, 'with_logger': 0, 'with_exc_info': 0, 'violations': []}

for fp in FILES:
    if not Path(fp).exists():
        print(f"[NOT FOUND] {fp}")
        continue
    stats = scan_file(fp)
    data[fp] = stats
    violations_count = len(stats['with_logger_no_exc_info_lines'])
    print(f"\n=== {fp} ===")
    print(f"  Total ExceptHandler:    {stats['total_excepts']}")
    print(f"  With logger call:       {stats['with_logger']}")
    print(f"  With exc_info=True:     {stats['with_exc_info']}")
    print(f"  WITHOUT exc_info:       {violations_count}")
    if violations_count > 0 and violations_count <= 60:
        print(f"  Violation lines:        {stats['with_logger_no_exc_info_lines']}")
    elif violations_count > 60:
        print(f"  Violation lines (first 30): {stats['with_logger_no_exc_info_lines'][:30]}")
        print(f"  Violation lines (last 10): {stats['with_logger_no_exc_info_lines'][-10:]}")

    grand['total'] += stats['total_excepts']
    grand['with_logger'] += stats['with_logger']
    grand['with_exc_info'] += stats['with_exc_info']
    grand['violations'].extend([(fp, ln) for ln in stats['with_logger_no_exc_info_lines']])

print(f"\n========== GRAND TOTAL ==========")
print(f"  Total ExceptHandler:    {grand['total']}")
print(f"  With logger call:       {grand['with_logger']}")
print(f"  With exc_info=True:     {grand['with_exc_info']}")
print(f"  WITHOUT exc_info:       {len(grand['violations'])}")
print(f"  Coverage:               {grand['with_exc_info']*100.0/max(grand['with_logger'],1):.1f}%")

# 写 JSON
output_path = Path('.trae/reports/rounds/.audit_r147_b_exc_info_scan.json')
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump({'data': data, 'grand': grand}, f, ensure_ascii=False, indent=2)
print(f"\n[JSON saved] {output_path}")
