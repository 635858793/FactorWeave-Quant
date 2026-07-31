"""
R147 子智能体 B - 8 文件持锁 IO 全面扫描 (R146-B HVD-146-F 立项)
"""
import sys
sys.path.insert(0, 'tools')
from _r147_b_lock_io_v1 import scan_file

FILES_LOCKS = [
    ('core/services/cache_service.py', '_lock'),
    ('core/trading/interfaces/ctp_trading_interface.py', '_order_lock,_ctp_error_lock'),
    ('core/trading/interfaces/ctp_market_interface.py', '_lock'),
    ('core/events/event_bus.py', '_lock,_stats_lock,_history_lock,_futures_lock'),
    ('core/services/unified_data_manager.py', '_lock,_inflight_kdata_lock'),
    ('core/trading/order_cache.py', '_lock'),
    ('core/risk_manager.py', '_get_positions_lock,_get_v2_positions_lock'),
    ('core/trading_engine.py', '_lock,_positions_lock,_orders_lock,_pending_lock,_cache_lock'),
]

print("=" * 70)
print("R147-B 8 文件持锁 IO 全面扫描 (R146-B HVD-146-F 立项)")
print("=" * 70)

total_violations = 0
for fp, locks in FILES_LOCKS:
    target_locks = set(locks.split(','))
    results = scan_file(fp, target_locks)
    print(f"\n--- {fp} ---")
    print(f"  Locks: {locks}")
    print(f"  Violations: {len(results)}")
    for r in results:
        print(f"    [{r['lock']}] L{r['lock_line']} -> L{r['call_line']}: {r['call_chain']}")
    total_violations += len(results)

print(f"\n========== GRAND TOTAL ==========")
print(f"  Total IO/Network/Disk/Serialization violations: {total_violations}")
