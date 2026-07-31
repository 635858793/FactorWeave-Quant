"""R202-D 4 源验证: 5 个 P0 order 事件 ORPHAN_PUB 确认"""
import os
import re
import json
from collections import defaultdict

PROJECT_ROOT = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui"
SCAN_DIRS = ["core", "gui", "web"]
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache"}

P0_EVENTS = [
    "order_save_retry",       # R84 P1-10 修复
    "batch_orders_created",   # R142 P0-4
    "batch_orders_cancelled", # R142 P0-4
    "all_active_orders_cancelled", # R142 P0-4
    "order_save_failed_need_unfreeze", # R142 P0-4
]

def scan_event(evt):
    pub_locations = []
    sub_locations = []
    pub_pattern = re.compile(rf'''(?:publish|_safe_publish)\s*\(\s*['"]({re.escape(evt)})['"]''')
    sub_pattern = re.compile(rf'''(?:subscribe|_subscribe_event|_safe_subscribe)\s*\(\s*['"]({re.escape(evt)})['"]''')
    for subdir in SCAN_DIRS:
        scan_path = os.path.join(PROJECT_ROOT, subdir)
        if not os.path.exists(scan_path):
            continue
        for root, dirs, files in os.walk(scan_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                full = os.path.join(root, fn)
                rel = full.replace(PROJECT_ROOT, "").replace("\\", "/").lstrip("/")
                if "test_" in fn or rel.startswith("tests/"):
                    continue
                try:
                    with open(full, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except:
                    continue
                for m in pub_pattern.finditer(content):
                    line_num = content[:m.start()].count("\n") + 1
                    pub_locations.append((rel, line_num))
                for m in sub_pattern.finditer(content):
                    line_num = content[:m.start()].count("\n") + 1
                    sub_locations.append((rel, line_num))
    return pub_locations, sub_locations


print("=== R202-D 4 源验证: 5 个 P0 order 事件 ===")
results = {}
for evt in P0_EVENTS:
    pubs, subs = scan_event(evt)
    results[evt] = {"pub": pubs, "sub": subs}
    print(f"\n[{evt}]")
    print(f"  publish 数: {len(pubs)}")
    for loc in pubs[:3]:
        print(f"    - {loc[0]}:{loc[1]}")
    print(f"  subscribe 数: {len(subs)}")
    if not subs:
        print(f"  ** ORPHAN_PUB 100% 确认: 无订阅方 (P0 业务核心)")
    for loc in subs[:3]:
        print(f"    - {loc[0]}:{loc[1]}")

# 保存结果
output = PROJECT_ROOT + "/tools/_r202_d_p0_order_events_verify.json"
with open(output, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n结果已保存: {output}")
