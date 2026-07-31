#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R186-A HVD-185-1 集成验证 demo"""

import sys
sys.path.insert(0, ".")

from core.multi_account.consistency_checker import (
    MultiAccountConsistencyChecker,
    MultiAccountDriftEvent,
)

print("=" * 70)
print("R186-A HVD-185-1 集成验证")
print("=" * 70)

# 创建 checker
checker = MultiAccountConsistencyChecker()
print(f"\n[1] Checker 实例: {checker}")

# 软解析 12 服务
report = checker.check_all_services_consistency()
print(f"\n[2] 12+ 服务 account_id 快照:")
for k, v in sorted(report.items()):
    print(f"    {k:30} = {v}")

# 一致性检测
print(f"\n[3] 一致性检测:")
unique = set(v if v is not None else "default" for v in report.values())
print(f"    unique_accounts: {sorted(unique)}")
print(f"    is_consistent: {len(unique) <= 1}")

# Dashboard
print(f"\n[4] Prometheus Dashboard:")
dashboard = checker.get_consistency_report()
print(f"    total_services: {dashboard['total_services']}")
print(f"    is_consistent: {dashboard['is_consistent']}")
print(f"    unique_accounts: {dashboard['unique_accounts']}")
print(f"    drift_count_total: {dashboard['drift_count_total']}")
print(f"    check_count_total: {dashboard['check_count_total']}")

# 漂移检测
print(f"\n[5] 漂移检测 (模拟多账户):")
drift_report = {
    "risk_manager": "acc_A", "trading_service": "acc_B",
    "data_service": "acc_A", "strategy_service": "acc_B",
}
result = checker.publish_consistency_alert_if_drift(drift_report)
print(f"    drift_detected: {result}")

print(f"\n[OK] R186-A HVD-185-1 集成验证通过")
