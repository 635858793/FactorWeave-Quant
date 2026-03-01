# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')

print("=" * 50)
print("Test 1: UnifiedPerformanceMonitor import")
print("=" * 50)
try:
    from core.performance.unified_monitor import UnifiedPerformanceMonitor
    monitor = UnifiedPerformanceMonitor()
    print("[OK] UnifiedPerformanceMonitor imported")
except Exception as e:
    print(f"[FAIL] {e}")
    import traceback
    traceback.print_exc()

print("")
print("=" * 50)
print("Test 2: collect_all_metrics method")
print("=" * 50)
try:
    metrics = monitor.collect_all_metrics()
    print(f"[OK] collect_all_metrics returned {len(metrics)} metrics")
    print(f"  - Response time: {metrics.get('Response time', 'N/A')} ms")
    print(f"  - Render FPS: {metrics.get('Render FPS', 'N/A')}")
    print(f"  - Cache hit rate: {metrics.get('Cache hit rate', 'N/A')}")
except Exception as e:
    print(f"[FAIL] {e}")
    import traceback
    traceback.print_exc()

print("")
print("=" * 50)
print("Test 3: ApplicationMetricsService import")
print("=" * 50)
try:
    from core.metrics.app_metrics_service import ApplicationMetricsService
    ams = ApplicationMetricsService()
    print("[OK] ApplicationMetricsService imported")
except Exception as e:
    print(f"[FAIL] {e}")
    import traceback
    traceback.print_exc()

print("")
print("=" * 50)
print("All tests completed!")
print("=" * 50)
