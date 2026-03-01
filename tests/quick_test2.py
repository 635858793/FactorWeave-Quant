import sys
sys.path.insert(0, '.')
print('Test 1: ApplicationMetricsService')
from core.metrics.app_metrics_service import ApplicationMetricsService
ams = ApplicationMetricsService()
print('OK - ApplicationMetricsService imported')

print('\nTest 2: system_monitor_tab_refactored')
import gui.widgets.performance.tabs.system_monitor_tab_refactored as smt
print('OK - system_monitor_tab_refactored imported')

print('\nTest 3: Timer check')
import time
start = time.perf_counter()
end = time.perf_counter()
print(f'OK - time.perf_counter works: {(end-start)*1000:.4f}ms')

print('\nAll import tests passed!')
