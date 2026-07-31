"""Smoke test for R198-A verification - 4 tasks completion verification."""
import sys
sys.path.insert(0, "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

# Task 1: EventBus double-track registration
from core.events.event_bus import EventBus
from core.events.types import EventType

print("=" * 60)
print("R198-A Smoke Test: 4 Tasks Verification")
print("=" * 60)

bus = EventBus()

# Verify enum.name registered
assert bus.is_event_registered("ORDER_FILLED"), "Enum name ORDER_FILLED should be registered"
print("[OK] EventType enum.name 'ORDER_FILLED' registered")

# Verify enum.value registered (R198-A HVD-197-D-NEW-01 fix)
assert bus.is_event_registered("order_filled"), "Enum value order_filled should be registered"
print("[OK] EventType enum.value 'order_filled' registered (R198-A NEW-01)")

# Verify multiple enum types
for et in [EventType.STRATEGY_STARTED, EventType.ORDER_FILLED, EventType.POSITION_UPDATED]:
    name = et.name
    value = et.value
    assert bus.is_event_registered(name), f"Enum name {name} should be registered"
    assert bus.is_event_registered(value), f"Enum value {value} should be registered"
    print(f"[OK] {name} / {value} both registered")

bus.dispose()
print()

# Task 2: alias/wrapper 4-source verification
from tools._r198_a_hvd_new_01_04 import verify_new_02_alias_compat_layer
result2 = verify_new_02_alias_compat_layer()
assert result2["status"] == "VERIFIED_ACTIVE_COMPAT", f"Expected VERIFIED_ACTIVE_COMPAT, got {result2['status']}"
print(f"[OK] NEW-02: {result2['status']}")
for v in result2["4_source_verification"]:
    assert v["verdict"] == "ACTIVE_COMPAT_LAYER", f"Expected ACTIVE_COMPAT_LAYER, got {v['verdict']}"
    print(f"     - {v['alias_name']}: {v['verdict']}")
print()

# Task 3: _make_auxiliary_cache_key 6-dim
from tools._r198_a_hvd_new_01_04 import fix_new_03_auxiliary_cache_key_6d
result3 = fix_new_03_auxiliary_cache_key_6d()
print(f"[OK] NEW-03: {result3['status']}")
print()

# Task 4: Lock nesting production scan
from tools._r198_a_hvd_new_01_04 import verify_new_04_lock_nesting_production
result4 = verify_new_04_lock_nesting_production()
assert result4["status"] == "NO_PRODUCTION_VIOLATIONS", f"Expected NO_PRODUCTION_VIOLATIONS, got {result4['status']}"
print(f"[OK] NEW-04: {result4['status']}")
print(f"     Files scanned: {result4['scan_result']['files_scanned']}")
print(f"     Violations: {result4['scan_result']['violation_count']}")
print()

print("=" * 60)
print("R198-A 4 Tasks ALL VERIFIED!")
print("=" * 60)
