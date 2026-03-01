# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')

print("=" * 60)
print("Detailed collect_all_metrics Test")
print("=" * 60)

from core.performance.unified_monitor import UnifiedPerformanceMonitor
monitor = UnifiedPerformanceMonitor()

# 检查 monitor 的属性
print("\nMonitor attributes:")
print(f"  - has system_monitor: {hasattr(monitor, 'system_monitor')}")
print(f"  - has cache: {hasattr(monitor, 'cache')}")
print(f"  - has ui_optimizer: {hasattr(monitor, 'ui_optimizer')}")

# 调用 collect_all_metrics
metrics = monitor.collect_all_metrics()

print("\nAll metrics returned:")
for key, value in sorted(metrics.items()):
    print(f"  {key}: {value}")

print("\n" + "=" * 60)
print("Test evaluate_strategy_performance (empty data)")
print("=" * 60)

import pandas as pd
empty_returns = pd.Series(dtype=float)
result = monitor.evaluate_strategy_performance(empty_returns, None)

print("\nStrategy metrics (no data case):")
for key, value in sorted(result.items()):
    print(f"  {key}: {value}")
