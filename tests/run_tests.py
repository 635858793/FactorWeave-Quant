# 使用 conda hikyuu 环境运行测试
import subprocess
import sys
import os

# 设置 PATH 让 Python 使用正确的环境
env = os.environ.copy()
env["PATH"] = r"E:\anaconda3\envs\hikyuu;" + env.get("PATH", "")
env["PYTHONIOENCODING"] = "utf-8"

test_code = '''
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

print()
print("=" * 50)
print("Test 2: collect_all_metrics method")
print("=" * 50)
try:
    metrics = monitor.collect_all_metrics()
    print(f"[OK] collect_all_metrics returned {len(metrics)} metrics")
    print(f"  - Response time: {metrics.get('Response time', 'N/A')} ms")
    print(f"  - Render FPS: {metrics.get('Render FPS', 'N/A')}")
    print(f"  - Cache hit rate: {metrics.get('Cache hit rate', 'N/A')}")
    print(f"  - Load time: {metrics.get('Load time', 'N/A')} ms")
    print(f"  - Throughput: {metrics.get('Throughput', 'N/A')}")
except Exception as e:
    print(f"[FAIL] {e}")
    import traceback
    traceback.print_exc()

print()
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

print()
print("=" * 50)
print("Test 4: Timer consistency")
print("=" * 50)
import time
start = time.perf_counter()
time.sleep(0.01)
end = time.perf_counter()
elapsed = (end - start) * 1000
print(f"[OK] time.perf_counter() measured 10ms sleep: {elapsed:.2f}ms")

print()
print("=" * 50)
print("All tests completed!")
print("=" * 50)
'''

result = subprocess.run(
    [r"E:\anaconda3\envs\hikyuu\python.exe", "-c", test_code],
    capture_output=True,
    text=True,
    cwd=r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui",
    env=env
)

print("STDOUT:")
print(result.stdout)
if result.stderr:
    print("\nSTDERR:")
    print(result.stderr)
print("\nReturn code:", result.returncode)
