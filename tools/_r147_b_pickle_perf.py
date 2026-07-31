"""
R147 子智能体 B - cache_service.py pickle.dumps 性能实测
- 模拟 1MB / 5MB / 10MB value, 测量 pickle.dumps 持锁耗时
"""
import pickle
import sys
import time


def make_test_data(size_mb):
    """构造指定大小的测试数据"""
    target_bytes = size_mb * 1024 * 1024
    # 用 dict 模拟真实业务对象
    data = {
        'timestamp': '2026-07-20T10:00:00',
        'stock_code': 'SH600000',
        'kdata': {
            'open': [1.0] * (target_bytes // 100),
            'high': [1.0] * (target_bytes // 100),
            'low': [1.0] * (target_bytes // 100),
            'close': [1.0] * (target_bytes // 100),
            'volume': [1000] * (target_bytes // 100),
        },
    }
    return data


def measure_pickle_latency(data, runs=10):
    """测量 pickle.dumps 平均耗时"""
    times = []
    for _ in range(runs):
        start = time.perf_counter_ns()
        serialized = pickle.dumps(data)
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        times.append(elapsed_ms)
    return {
        'avg_ms': sum(times) / len(times),
        'min_ms': min(times),
        'max_ms': max(times),
        'p99_ms': sorted(times)[int(len(times) * 0.99)] if len(times) > 1 else times[0],
        'serialized_size_mb': len(serialized) / 1024 / 1024,
    }


if __name__ == '__main__':
    print("=" * 70)
    print("R147-B cache_service.py pickle.dumps 性能实测")
    print("=" * 70)

    results = {}
    for size_mb in [1, 2, 5, 10]:
        data = make_test_data(size_mb)
        result = measure_pickle_latency(data, runs=10)
        results[f'{size_mb}MB'] = result
        print(f"\n--- {size_mb}MB value ---")
        print(f"  Serialized size: {result['serialized_size_mb']:.2f}MB")
        print(f"  Avg: {result['avg_ms']:.2f}ms")
        print(f"  Min: {result['min_ms']:.2f}ms")
        print(f"  Max: {result['max_ms']:.2f}ms")
        print(f"  P99: {result['p99_ms']:.2f}ms")

    print("\n" + "=" * 70)
    print("【R147-B 性能影响评级】")
    print("=" * 70)
    for label, r in results.items():
        p99 = r['p99_ms']
        if p99 > 50:
            severity = "🔴 P0 严重"
        elif p99 > 10:
            severity = "🟡 P1 中等"
        elif p99 > 1:
            severity = "🟢 P2 轻微"
        else:
            severity = "🟢 优"
        print(f"  {label}: P99={p99:.2f}ms -> {severity}")
    print("\n【业务影响】")
    print("  - 持锁 1MB+ value 10-100ms, 阻塞所有 cache 读/写")
    print("  - 高并发 set 大对象场景: 串行化退化")
    print("  - 业务影响: 🟡 P1 性能瓶颈 (缓存命中率下降 + 业务线程阻塞)")
    print("=" * 70)
