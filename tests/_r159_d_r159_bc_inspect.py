"""R159-D R+1 round: R159-B 9 处缺 exc_info 详细定位 (V2)"""
import sys
from pathlib import Path
sys.path.insert(0, r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tests')

import importlib.util
spec = importlib.util.spec_from_file_location("r159_b", r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tests\test_r159_b_hvd_158b_silent_except.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

files = [
    "core/trading/order_executor.py",
    "core/trading/order_service.py",
    "core/trading/order_monitor.py",
]

print("=" * 70)
print("R159-B R+1 round 实测: TDD-2 缺 exc_info 详细定位")
print("=" * 70)
for rel in files:
    full = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui") / rel
    r = m.check_r159_hvd_158b_exc_info(str(full))
    print(f"## {rel}")
    print(f"   R159 HVD-158-B markers: {r['r159_b_markers']}")
    print(f"   r159_b_upgrades_checked: {r['r159_b_upgrades_checked']}")
    print(f"   r159_b_without_exc_info: {r['r159_b_without_exc_info']}")
    if r['syntax_error']:
        print(f"   SYNTAX ERROR: {r['syntax_error']}")
    print()

print("=" * 70)
print("R159-C TDD 详细执行")
print("=" * 70)
spec2 = importlib.util.spec_from_file_location("r159_c", r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tests\test_r159_hvd_158c_logger_debug_upgrade.py")
m2 = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(m2)

tests = [
    ("TDD-1 marker count", m2.test_tdd_1_marker_count),
    ("TDD-2 exc_info compliance", m2.test_tdd_2_exc_info_compliance),
    ("TDD-3 no syntax error", m2.test_tdd_3_no_syntax_error),
    ("TDD-4 residual business debug", m2.test_tdd_4_residual_business_debug),
    ("TDD-5 business event coverage", m2.test_tdd_5_business_event_coverage),
]
for name, func in tests:
    try:
        print(f"\n--- {name} ---")
        func()
        print(f"  [PASSED]")
    except AssertionError as e:
        print(f"  [FAILED] {e}")
    except Exception as e:
        print(f"  [ERROR] {e}")
