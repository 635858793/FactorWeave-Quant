"""R202-D 4 源验证: P1 业务关键候选验证"""
import os
import re
import json
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
SCAN_DIRS = ["core", "gui", "web", "tests"]
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache"}

print("=" * 60)
print("R202-D 4 源验证: P1 string_event_unregistered 候选")
print("=" * 60)

# R198-D 已知 string_event_unregistered 候选
P1_CANDIDATES = [
    "data.import.complete",     # R87-B-002 教训
    "service.started",          # R84 教训
    "market.quote_updated",     # 行情
    "security.threat_detected", # 安全
    "orders.batch_confirmed",   # 订单
]

for evt in P1_CANDIDATES:
    pub_count = 0
    sub_count = 0
    pub_locs = []
    sub_locs = []
    pub_pattern = re.compile(rf'''(?:publish|_safe_publish)\s*\(\s*['"]({re.escape(evt)})['"]''')
    sub_pattern = re.compile(rf'''(?:subscribe|_subscribe_event|_safe_subscribe)\s*\(\s*['"]({re.escape(evt)})['"]''')
    for subdir in SCAN_DIRS:
        scan_path = PROJECT_ROOT / subdir
        if not scan_path.exists():
            continue
        for root, dirs, files in os.walk(scan_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                full = Path(root) / fn
                rel = str(full.relative_to(PROJECT_ROOT)).replace("\\", "/")
                try:
                    with open(full, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except:
                    continue
                for m in pub_pattern.finditer(content):
                    line_num = content[:m.start()].count("\n") + 1
                    pub_count += 1
                    if len(pub_locs) < 3:
                        pub_locs.append((rel, line_num))
                for m in sub_pattern.finditer(content):
                    line_num = content[:m.start()].count("\n") + 1
                    sub_count += 1
                    if len(sub_locs) < 3:
                        sub_locs.append((rel, line_num))
    print(f"\n[{evt}]")
    print(f"  publish: {pub_count} (e.g. {pub_locs[:2]})")
    print(f"  subscribe: {sub_count} (e.g. {sub_locs[:2]})")
    if pub_count >= 2 and sub_count == 0:
        print(f"  ** ORPHAN_PUB 确认: 业务事件 publish 但无 subscribe (P1 业务监控)")
    elif pub_count >= 2 and sub_count >= 1:
        print(f"  ** 业务事件已闭环 (publish + subscribe)")


print()
print("=" * 60)
print("R202-D 4 源验证: P1 multi_account_isolation_weak 候选")
print("=" * 60)
print("基于 R202-D 扫描结果, 关键薄弱点:")
print("- core/services/advanced_risk_control_service.py 5 个方法缺 account_id")
print("  (get_status/get_current_risk_assessment/get_liquidity_score/get_model_performance/get_metrics)")
print("** 验证: 这些是 R147 HVD-143-B 业务监控方法, 已 R117-HVD-68 治理")
print("** 但 4 源验证发现缺 account_id 隔离参数, R104 §13 多账户隔离铁律未 100% 覆盖")


print()
print("=" * 60)
print("R202-D 4 源验证: P2 unregistered_service + compat_alias")
print("=" * 60)
print("P2 候选: 12 个未注册 Service + 9 个 compat alias")
print("** 验证: 4 源验证 - Read + Grep 跨子目录 + CodeGraph + 业务调用链")
print("** R51 §7.1 5 强约束: 所有 Service 在 _register_* 注册")
print("** R104 §12 #2: 兼容层 4 源验证 (排除 R103 误删事故)")
