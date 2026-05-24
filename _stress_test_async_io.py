"""
全链路压力测试：AsyncIOManager + BacktestResourceManager 高并发稳定性验证

测试场景：
1. AsyncIOManager: 并发缓存读写 (LRU淘汰竞争)
2. SmartDataCache: 高并发 get/put/evict
3. BacktestResourceManager: 并发资源分配/释放
4. 混合负载: 文件读取 + 资源管理 + 缓存操作
5. 内存泄漏检测
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import threading
import time
import random
import tempfile
import gc
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

from loguru import logger
logger.remove()
logger.add(sys.stderr, level="WARNING")

TEST_DURATION = 5
NUM_THREADS = 20
NUM_OPERATIONS = 500
CACHE_SIZE = 100
SMALL_FILES = 10


def create_temp_test_files(tmp_dir):
    files = []
    for i in range(SMALL_FILES):
        fpath = tmp_dir / f"test_data_{i}.bin"
        data = np.random.bytes(random.randint(1024, 10240))
        fpath.write_bytes(data)
        files.append(fpath)
    return files


class StressTestResults:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.metrics = defaultdict(list)
        self.passed = True
        self.lock = threading.Lock()

    def add_error(self, test_name, msg, exc=None):
        with self.lock:
            self.errors.append(f"[{test_name}] {msg}")
            if exc:
                self.errors.append(f"  Exception: {type(exc).__name__}: {exc}")
            self.passed = False

    def add_warning(self, test_name, msg):
        with self.lock:
            self.warnings.append(f"[{test_name}] {msg}")

    def record_metric(self, name, value):
        with self.lock:
            self.metrics[name].append(value)

    def summary(self):
        total_errors = len(self.errors)
        total_warnings = len(self.warnings)
        status = "PASSED" if self.passed else "FAILED"

        lines = []
        lines.append("=" * 70)
        lines.append(f"  全链路压力测试结果: {status}")
        lines.append(f"  错误数: {total_errors}  警告数: {total_warnings}")
        lines.append("=" * 70)

        if self.metrics:
            lines.append("\n  --- 性能指标 ---")
            for name, values in sorted(self.metrics.items()):
                arr = np.array(values)
                lines.append(
                    f"  {name:30s}: avg={np.mean(arr):.2f}, "
                    f"min={np.min(arr):.2f}, max={np.max(arr):.2f}, "
                    f"std={np.std(arr):.2f}, count={len(arr)}"
                )

        if self.errors:
            lines.append(f"\n  --- 错误 ({total_errors}) ---")
            for e in self.errors:
                lines.append(f"  {e}")

        if self.warnings:
            lines.append(f"\n  --- 警告 ({total_warnings}) ---")
            for w in self.warnings:
                lines.append(f"  {w}")

        lines.append("\n" + "=" * 70)
        return "\n".join(lines)


results = StressTestResults()

# ============================================================
# Test 1: AsyncIOManager 并发缓存读写
# ============================================================
def test_async_io_cache_race():
    test_name = "Test1-AsyncIO-Cache-Race"
    print(f"\n>>> {test_name}: {NUM_THREADS}线程 x {NUM_OPERATIONS}次缓存操作...")

    from backtest.async_io_manager import AsyncIOManager
    mgr = AsyncIOManager(cache_size=CACHE_SIZE, max_workers=min(NUM_THREADS, 8))

    keys_added = []
    for i in range(CACHE_SIZE * 3):
        key = f"key_{i}"
        data = np.random.bytes(256)
        mgr._put_to_cache(key, data)
        keys_added.append(key)

    error_count = [0]
    ops_count = [0]
    lock = threading.Lock()

    def worker(thread_id):
        local_errors = 0
        local_ops = 0
        for _ in range(NUM_OPERATIONS):
            try:
                op = random.choice(['get', 'put'])
                key = random.choice(keys_added)
                if op == 'get':
                    val = mgr._get_from_cache(key)
                    local_ops += 1
                else:
                    mgr._put_to_cache(f"stress_{thread_id}_{_}", b"x" * 128)
                    local_ops += 1
            except Exception as e:
                local_errors += 1
                if local_errors <= 3:
                    results.add_error(test_name, f"T{thread_id} op#{_}: {e}", e)

        with lock:
            error_count[0] += local_errors
            ops_count[0] += local_ops

    start = time.perf_counter()
    threads = []
    for tid in range(NUM_THREADS):
        t = threading.Thread(target=worker, args=(tid,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start

    total_ops = ops_count[0]
    tps = total_ops / elapsed if elapsed > 0 else 0
    results.record_metric("AsyncIO_Cache_Ops/sec", tps)
    results.record_metric("AsyncIO_Cache_Errors", error_count[0])

    final_size = len(mgr._get_from_cache.__self__.cache)
    if final_size > CACHE_SIZE:
        results.add_error(test_name,
                          f"缓存溢出! 期望≤{CACHE_SIZE}, 实际{final_size}")

    mgr.cleanup()
    status = "PASSED" if error_count[0] == 0 else f"FAILED(errors={error_count[0]})"
    print(f"   {status} | {total_ops}ops in {elapsed:.2f}s ({tps:.0f} ops/s) | cache_size={final_size}")


# ============================================================
# Test 2: SmartDataCache 高并发 get/put/evict
# ============================================================
def test_smart_cache_race():
    test_name = "Test2-SmartCache-Race"
    print(f"\n>>> {test_name}: {NUM_THREADS}线程 并发存取淘汰...")

    from backtest.async_io_manager import SmartDataCache
    cache = SmartDataCache(max_memory_mb=50)

    np.random.seed(42)
    reference_data = {}
    for i in range(200):
        key = f"ref_{i}"
        arr = np.random.randn(50, 20)
        reference_data[key] = arr
        cache.put(key, arr, ttl=random.choice([None, 30, 120]))

    error_count = [0]
    corruption_count = [0]
    ops_count = [0]
    lock = threading.Lock()

    def worker(tid):
        local_errors = 0
        local_corruption = 0
        local_ops = 0
        for _ in range(NUM_OPERATIONS // 2):
            try:
                op = random.choice(['get', 'put'])
                if op == 'get':
                    key = random.choice(list(reference_data.keys()))
                    val = cache.get(key)
                    local_ops += 1
                    if val is not None and not np.array_equal(val, reference_data[key]):
                        local_corruption += 1
                else:
                    k = f"stress_{tid}_{_}"
                    d = np.random.randn(10, 10)
                    cache.put(k, d, ttl=60)
                    local_ops += 1
            except Exception as e:
                local_errors += 1
                if local_errors <= 3:
                    results.add_error(test_name, f"T{tid}: {e}", e)

        with lock:
            error_count[0] += local_errors
            corruption_count[0] += local_corruption
            ops_count[0] += local_ops

    start = time.perf_counter()
    threads = []
    for tid in range(NUM_THREADS):
        t = threading.Thread(target=worker, args=(tid,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start

    tps = ops_count[0] / elapsed if elapsed > 0 else 0
    results.record_metric("SmartCache_Ops/sec", tps)
    results.record_metric("SmartCache_Errors", error_count[0])
    results.record_metric("SmartCache_Corruptions", corruption_count[0])

    cache.clear()
    status = "PASSED" if error_count[0] == 0 and corruption_count[0] == 0 else "FAILED"
    print(f"   {status} | {ops_count[0]}ops | errors={error_count[0]} corruptions={corruption_count[0]} | {tps:.0f} ops/s")


# ============================================================
# Test 3: BacktestResourceManager 并发资源分配/释放
# ============================================================
def test_resource_manager_race():
    test_name = "Test3-ResourceManager-Race"
    print(f"\n>>> {test_name}: {NUM_THREADS}线程 并发进入/退出上下文...")

    from backtest.resource_manager import managed_backtest_resources

    error_count = [0]
    leak_count = [0]
    ops_count = [0]
    lock = threading.Lock()

    def worker(tid):
        local_errors = 0
        local_leaks = 0
        local_ops = 0
        for _ in range(NUM_OPERATIONS // 10):
            try:
                with managed_backtest_resources() as mgr:
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.stress')
                    tmp.write(b"stress_test_data")
                    tmp.close()
                    mgr.register_temp_file(Path(tmp.name))
                    mgr.register_resource(f"resource_{tid}_{_}")
                    local_ops += 1

                    for sub in range(3):
                        mgr.register_resource(f"sub_{tid}_{_}_{sub}")

            except Exception as e:
                local_errors += 1
                if local_errors <= 3:
                    results.add_error(test_name, f"T{tid}: {e}", e)

        with lock:
            error_count[0] += local_errors
            ops_count[0] += local_ops

    start = time.perf_counter()
    threads = []
    for tid in range(NUM_THREADS):
        t = threading.Thread(target=worker, args=(tid,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start

    tps = ops_count[0] / elapsed if elapsed > 0 else 0
    results.record_metric("ResourceMgr_Ops/sec", tps)
    results.record_metric("ResourceMgr_Errors", error_count[0])

    status = "PASSED" if error_count[0] == 0 else f"FAILED(errors={error_count[0]})"
    print(f"   {status} | {ops_count[0]} contexts | {tps:.0f} contexts/s")


# ============================================================
# Test 4: 混合负载 - 文件读取 + 缓存 + 资源管理
# ============================================================
def test_mixed_load():
    test_name = "Test4-Mixed-Load"
    print(f"\n>>> {test_name}: {NUM_THREADS}线程 混合IO+缓存+资源...")

    from backtest.async_io_manager import AsyncIOManager
    from backtest.resource_manager import managed_backtest_resources

    tmp_dir = Path(tempfile.mkdtemp(prefix="stress_mixed_"))
    test_files = create_temp_test_files(tmp_dir)

    io_mgr = AsyncIOManager(cache_size=CACHE_SIZE, max_workers=min(NUM_THREADS, 8))

    error_count = [0]
    ops_count = [0]
    lock = threading.Lock()

    def worker(tid):
        local_errors = 0
        local_ops = 0
        try:
            for _ in range(NUM_OPERATIONS // 5):
                try:
                    op = random.randint(0, 3)
                    if op == 0:
                        f = random.choice(test_files)
                        data = io_mgr._read_file_sync(f)
                        io_mgr._put_to_cache(f"mixed_{tid}_{_}", data)
                        local_ops += 1
                    elif op == 1:
                        key = f"mixed_{random.randint(0, tid * 100)}"
                        io_mgr._get_from_cache(key)
                        local_ops += 1
                    elif op == 2:
                        with managed_backtest_resources() as mgr:
                            mgr.register_resource(f"mixed_res_{tid}_{_}")
                            local_ops += 1
                    else:
                        ctx = managed_backtest_resources()
                        mgr = ctx.__enter__()
                        mgr.register_resource(f"mixed_ctx_{tid}_{_}")
                        ctx.__exit__(None, None, None)
                        local_ops += 1
                except Exception as e:
                    local_errors += 1
                    if local_errors <= 3:
                        results.add_error(test_name, f"T{tid} op#{_}: {e}", e)
        finally:
            pass

        with lock:
            error_count[0] += local_errors
            ops_count[0] += local_ops

    start = time.perf_counter()
    threads = []
    for tid in range(NUM_THREADS):
        t = threading.Thread(target=worker, args=(tid,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start

    io_mgr.cleanup()

    for f in test_files:
        try:
            if f.exists():
                f.unlink()
        except Exception:
            pass
    try:
        tmp_dir.rmdir()
    except Exception:
        pass

    tps = ops_count[0] / elapsed if elapsed > 0 else 0
    results.record_metric("Mixed_Ops/sec", tps)
    results.record_metric("Mixed_Errors", error_count[0])

    status = "PASSED" if error_count[0] == 0 else f"FAILED(errors={error_count[0]})"
    print(f"   {status} | {ops_count[0]}ops | {tps:.0f} ops/s")


# ============================================================
# Test 5: 内存泄漏检测
# ============================================================
def test_memory_leak():
    test_name = "Test5-Memory-Leak"
    print(f"\n>>> {test_name}: 循环创建/销毁检测内存增长...")

    from backtest.async_io_manager import AsyncIOManager, SmartDataCache
    from backtest.resource_manager import BacktestResourceManager

    gc.collect()
    gc.collect()
    initial_objects = len(gc.get_objects())

    cycles = 50
    for i in range(cycles):
        mgr = AsyncIOManager(cache_size=100)
        for j in range(50):
            mgr._put_to_cache(f"leak_{j}", b"x" * 256)
            mgr._get_from_cache(f"leak_{j}")
        mgr.clear_cache()
        mgr.cleanup()
        mgr = None
        del mgr

        cache = SmartDataCache(max_memory_mb=10)
        for j in range(50):
            arr = np.random.randn(5, 5)
            cache.put(f"leak_{j}", arr, ttl=10)
            _ = cache.get(f"leak_{j}")
        cache.clear()
        cache = None
        del cache

    gc.collect()
    gc.collect()
    final_objects = len(gc.get_objects())
    growth = final_objects - initial_objects

    results.record_metric("Memory_Leak_ObjectGrowth", growth)
    results.record_metric("Memory_Leak_Cycles", cycles)

    if growth > 1000:
        results.add_warning(test_name, f"对象增长{growth}个 (>1000，可能存在内存泄漏)")
    else:
        results.add_warning(test_name, f"对象增长{growth}个 (在正常范围内)")

    print(f"   完成 | 初始对象数={initial_objects} 最终={final_objects} 增长={growth}")


# ============================================================
# Test 6: 死锁检测
# ============================================================
def test_deadlock():
    test_name = "Test6-Deadlock-Detect"
    print(f"\n>>> {test_name}: {NUM_THREADS}线程 锁竞争死锁检测...")

    from backtest.async_io_manager import AsyncIOManager, SmartDataCache

    io_mgr = AsyncIOManager(cache_size=200)
    cache = SmartDataCache(max_memory_mb=100)

    for i in range(300):
        io_mgr._put_to_cache(f"dl_{i}", b"d" * 100)
        cache.put(f"dl_{i}", np.ones((5, 5)), ttl=60)

    deadlock_detected = [False]
    completed = [0]
    lock = threading.Lock()

    def worker(tid):
        try:
            cnt = 0
            deadline = time.time() + 3.0
            while time.time() < deadline:
                k = random.randint(0, 299)
                io_mgr._get_from_cache(f"dl_{k}")
                io_mgr._put_to_cache(f"dl_new_{tid}_{cnt}", b"n" * 50)
                _ = cache.get(f"dl_{k}")
                cnt += 1
            with lock:
                completed[0] += cnt
        except Exception as e:
            results.add_error(test_name, f"T{tid}: {e}", e)

    start = time.perf_counter()
    threads = []
    for tid in range(NUM_THREADS):
        t = threading.Thread(target=worker, args=(tid,))
        t.daemon = True
        threads.append(t)
        t.start()

    deadline = time.time() + 5.0
    all_alive = True
    while time.time() < deadline:
        alive = sum(1 for t in threads if t.is_alive())
        if alive == 0:
            all_alive = False
            break
        time.sleep(0.1)

    for t in threads:
        t.join(timeout=1.0)

    still_alive = sum(1 for t in threads if t.is_alive())
    completed_ops = completed[0]

    if still_alive > 0:
        results.add_error(test_name, f"检测到死锁! {still_alive}个线程在5秒后仍未完成")
        deadlock_detected[0] = True

    results.record_metric("Deadlock_StuckThreads", still_alive)
    status = "FAILED(DEADLOCK)" if deadlock_detected[0] else "PASSED"
    print(f"   {status} | {completed_ops}ops | stuck_threads={still_alive}")

    io_mgr.cleanup()
    cache.clear()


# ============================================================
# 主入口
# ============================================================
def main():
    print("=" * 70)
    print("  全链路压力测试")
    print(f"  线程数: {NUM_THREADS}  操作数: {NUM_OPERATIONS}")
    print(f"  缓存大小: {CACHE_SIZE}  文件数: {SMALL_FILES}")
    print("=" * 70)

    all_tests = [
        ("AsyncIO 缓存并发", test_async_io_cache_race),
        ("SmartCache 并发", test_smart_cache_race),
        ("ResourceManager 并发", test_resource_manager_race),
        ("混合负载", test_mixed_load),
        ("内存泄漏检测", test_memory_leak),
        ("死锁检测", test_deadlock),
    ]

    for name, fn in all_tests:
        try:
            fn()
        except Exception as e:
            results.add_error(name, f"测试崩溃: {e}", e)

    print("\n")
    print(results.summary())

    return 0 if results.passed else 1


if __name__ == "__main__":
    sys.exit(main())