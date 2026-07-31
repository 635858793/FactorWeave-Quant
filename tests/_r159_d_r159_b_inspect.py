"""R159-D R+1 round: R159-B 9 处缺 exc_info 详细定位"""
import sys
from pathlib import Path
sys.path.insert(0, r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tests')

import importlib.util
spec = importlib.util.spec_from_file_location("r159_b", r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tests\test_r159_b_hvd_158b_silent_except.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# 详细跑 TDD-2 检查
files = [
    "core/trading/order_executor.py",
    "core/trading/order_service.py",
    "core/trading/order_monitor.py",
]

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
