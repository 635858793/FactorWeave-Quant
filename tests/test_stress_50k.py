"""
Hikyuu-UI 极端压力测试 — 5万条数据并发加载
模拟极端场景下的性能瓶颈检测

运行方式: python tests/test_stress_50k.py
"""

import time
import gc
import statistics
import sys
import os
import tracemalloc
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd


# ============================================================================
# 工具
# ============================================================================

@dataclass
class StressResult:
    name: str
    sizes: List[int] = field(default_factory=list)
    times_ms: List[float] = field(default_factory=list)
    mem_mb: List[float] = field(default_factory=list)
    bottleneck: str = ""


def generate_kline_data(n: int, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    dates = pd.date_range('2008-01-01', periods=n, freq='B')
    close = np.zeros(n, dtype=np.float64)
    close[0] = 15.0
    trend = np.cumsum(np.random.normal(0.0003, 0.003, n))
    volatility = np.clip(0.015 + 0.005 * np.sin(np.arange(n) * 2 * np.pi / 250), 0.008, 0.035)
    for i in range(1, n):
        dr = np.clip(np.random.normal(trend[i], volatility[i]), -0.10, 0.10)
        close[i] = close[i - 1] * (1 + dr)
    close = np.clip(close, 0.1, 1e6)
    open_p = np.roll(close, 1)
    open_p[0] = close[0] * (1 + np.random.normal(0, 0.01))
    gaps = np.random.random(n) < 0.03
    open_p[gaps] = close[gaps] * (1 + np.random.normal(0, 0.02, gaps.sum()))
    open_p = np.clip(open_p, close * 0.9, close * 1.1)
    daily_range = np.abs(close - open_p) * np.random.uniform(0.5, 2.0, n)
    high_p = np.maximum(open_p, close) + daily_range * np.random.uniform(0.1, 0.6, n)
    low_p = np.minimum(open_p, close) - daily_range * np.random.uniform(0.1, 0.6, n)
    volume = np.random.lognormal(14, 1.2, n).astype(np.float64)
    return pd.DataFrame({
        'open': open_p.astype(np.float32),
        'high': high_p.astype(np.float32),
        'low': low_p.astype(np.float32),
        'close': close.astype(np.float32),
        'volume': volume.astype(np.float32),
        'amount': volume * close.astype(np.float32) * 0.5,
    }, index=dates)


def measure_memory(func) -> Tuple[float, float, float]:
    """返回 (peak_mb, delta_mb, result)"""
    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()
    result = func()
    elapsed = (time.perf_counter() - t0) * 1000
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return elapsed, peak / (1024 * 1024), result


# ============================================================================
# 被测试函数（直接复刻修复后的实现）
# ============================================================================

def completeness_NEW(data, required_columns):
    cols = [c for c in required_columns if c in data.columns]
    if not cols or len(data) == 0:
        return 0.0
    return float(data[cols].notna().all(axis=1).sum()) / len(data)


def convert_values_NEW(data):
    return {k: data[k].values for k in ['open', 'high', 'low', 'close', 'volume'] if k in data.columns}


def volume_batch_NEW(volumes, is_up):
    up_rgb = np.array((1.0, 0.267, 0.267), dtype=np.float64)
    down_rgb = np.array((0.267, 1.0, 0.267), dtype=np.float64)
    n = len(volumes)
    max_vol = max(volumes) if n > 0 else 0
    target_max = 100.0
    valid = volumes > 0
    if not valid.any():
        return [], []
    normalized = np.where(valid, (volumes / max_vol) * target_max if max_vol > 0 else 0.0, 0.0)
    x_positions = np.arange(n, dtype=np.float64)
    verts = np.empty((n, 8), dtype=np.float64)
    verts[:, 0] = x_positions - 0.5;  verts[:, 1] = 0.0
    verts[:, 2] = x_positions - 0.5;  verts[:, 3] = normalized
    verts[:, 4] = x_positions + 0.5;  verts[:, 5] = normalized
    verts[:, 6] = x_positions + 0.5;  verts[:, 7] = 0.0
    valid_verts = verts[valid].ravel().tolist()
    if is_up is not None:
        is_up_valid = is_up[valid]
        cols = np.where(is_up_valid[:, np.newaxis], up_rgb, down_rgb).ravel().tolist()
    else:
        cols = np.tile(up_rgb, (valid.sum(), 1)).ravel().tolist()
    return valid_verts, cols


def cpu_fallback_NEW(data):
    opens = data['open'].values; closes = data['close'].values
    highs = data['high'].values; lows = data['low'].values
    n = len(data)
    x = np.arange(n, dtype=np.float64)
    w = 0.4
    is_up = closes >= opens
    body_bottom = np.minimum(opens, closes)
    body_height = np.maximum(opens - closes, closes - opens)
    body_height = np.maximum(body_height, 0.001)
    shadows_arr = np.empty((n, 2, 2), dtype=np.float64)
    shadows_arr[:, 0, 0] = x; shadows_arr[:, 0, 1] = lows
    shadows_arr[:, 1, 0] = x; shadows_arr[:, 1, 1] = highs
    return n, shadows_arr


def quality_cache_NEW(df):
    if len(df) == 0:
        return []
    latest = df.iloc[0]
    if pd.notna(latest.iloc[0] if hasattr(latest, 'iloc') else latest.get('datetime')):
        return [(df.index[0], float(df.iloc[0].get('quality_score', 0)))]
    return []


def std_kdata_NEW(df):
    for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def candle_bar_NEW(data):
    opens = data['open'].values; closes = data['close'].values
    n = len(data)
    x_idx = np.arange(n, dtype=np.float64)
    w = 0.3
    is_up = closes >= opens
    up_x = x_idx[is_up]; down_x = x_idx[~is_up]
    n_up = len(up_x); n_down = len(down_x)
    up_r = np.column_stack([up_x - w, opens[is_up],
                             np.full(n_up, w * 2), closes[is_up] - opens[is_up]]) if n_up else np.empty((0, 4))
    down_r = np.column_stack([down_x - w, closes[~is_up],
                               np.full(n_down, w * 2), opens[~is_up] - closes[~is_up]]) if n_down else np.empty((0, 4))
    return up_r, down_r


def ohlcv_NEW(records):
    n = len(records)
    o = [0.0]*n; h = [0.0]*n; l = [0.0]*n; c = [0.0]*n; v = [0.0]*n
    for i, r in enumerate(records):
        p = r.get('price', 0)
        o[i] = r.get('open', p); h[i] = r.get('high', p)
        l[i] = r.get('low', p); c[i] = r.get('close', p)
        v[i] = r.get('volume', 0)
    return {'open': o, 'high': h, 'low': l, 'close': c, 'volume': v}


# ============================================================================
# 可扩展性测试
# ============================================================================

def scalability_test(name: str, func, sizes: List[int], data_gen, **kwargs) -> StressResult:
    result = StressResult(name=name, sizes=sizes)
    for n in sizes:
        data = data_gen(n)
        gc.collect()
        tracemalloc.start()
        t0 = time.perf_counter()
        func(data, **kwargs) if kwargs else func(data)
        elapsed = (time.perf_counter() - t0) * 1000
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        result.times_ms.append(elapsed)
        result.mem_mb.append(peak / (1024 * 1024))
    return result


def data_gen_kline(n):
    return generate_kline_data(n)


def data_gen_vol(n):
    data = generate_kline_data(n)
    return data['volume'].values.astype(np.float64), data['close'].values >= data['open'].values


def data_gen_ohlcv(n):
    rng = np.random.RandomState(42)
    return [{'price': float(rng.uniform(10, 100)),
             'open': float(rng.uniform(10, 100)),
             'high': float(rng.uniform(10, 100)),
             'low': float(rng.uniform(10, 100)),
             'close': float(rng.uniform(10, 100)),
             'volume': float(rng.uniform(1000, 100000))} for _ in range(n)]


def data_gen_quality(n):
    data = generate_kline_data(n)
    data['quality_score'] = np.random.uniform(0.5, 1.0, n)
    return data


# ============================================================================
# 并发加载模拟（模拟多窗口同时请求）
# ============================================================================

def simulate_concurrent_load(n_points: int, concurrency: int = 4):
    """模拟 concurrency 个窗口同时加载 n_points 条数据"""
    import concurrent.futures

    data = generate_kline_data(n_points)
    cols = ['open', 'high', 'low', 'close', 'volume']

    def worker_load():
        completeness_NEW(data, cols)
        convert_values_NEW(data)
        std_kdata_NEW(data.copy())
        return True

    print(f"\n  🔥 模拟 {concurrency} 路并发加载 (每路 {n_points} 条)...", end=" ", flush=True)

    gc.collect()
    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(worker_load) for _ in range(concurrency)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    elapsed = (time.perf_counter() - t0) * 1000

    print(f"{elapsed:.1f}ms total, {elapsed/concurrency:.1f}ms/worker")
    return elapsed


# ============================================================================
# 内存峰值测试
# ============================================================================

def memory_peak_test(n_points: int):
    print(f"\n  💾 内存峰值测试 ({n_points}条)...", end=" ", flush=True)
    data = generate_kline_data(n_points)
    cols = ['open', 'high', 'low', 'close', 'volume']
    ops = [
        ('completeness', lambda: completeness_NEW(data, cols)),
        ('convert', lambda: convert_values_NEW(data)),
        ('vol_batch', lambda: volume_batch_NEW(data['volume'].values.astype(np.float64),
                                                data['close'].values >= data['open'].values)),
    ]

    gc.collect()
    tracemalloc.start()
    for name, op in ops:
        gc.collect()
        t0_snap = tracemalloc.take_snapshot()
        op()
        t1_snap = tracemalloc.take_snapshot()
        diff = t1_snap.compare_to(t0_snap, 'lineno')
        total = sum(stat.size_diff for stat in diff)
        if total > 0:
            print(f"\n     {name}: +{total/1024:.0f}KB 新分配")
    tracemalloc.stop()


# ============================================================================
# 主入口
# ============================================================================

def main():
    print("=" * 65)
    print("  Hikyuu-UI 极端压力测试 — 5万条数据并发加载")
    print("=" * 65)

    SCALE_POINTS = [1000, 5000, 10000, 25000, 50000]

    print(f"\n  📦 准备测试数据规模: {SCALE_POINTS}")
    print(f"     最大单次数据量: {SCALE_POINTS[-1]:,} 条K线 ({SCALE_POINTS[-1]*6*4/1024:.0f}KB)")

    # ================================================================
    print(f"\n{'═' * 65}")
    print("  Phase 1: 可扩展性曲线 (1K→5K→10K→25K→50K)")
    print(f"{'═' * 65}")

    scalability_tests = [
        ("完整性检查", lambda d: completeness_NEW(d, ['open', 'high', 'low', 'close', 'volume']), 'kline'),
        ("格式转换", lambda d: convert_values_NEW(d), 'kline'),
        ("GPU顶点构建", lambda d: volume_batch_NEW(d[0], d[1]), 'vol'),
        ("CPU降级K线", lambda d: cpu_fallback_NEW(d), 'kline'),
        ("质量缓存", lambda d: quality_cache_NEW(d), 'quality'),
        ("K线标准化", lambda d: std_kdata_NEW(d.copy()), 'kline'),
        ("K线矩形计算", lambda d: candle_bar_NEW(d), 'kline'),
        ("Tick聚合", lambda d: ohlcv_NEW(d), 'ohlcv'),
    ]

    def gen_arg(data_type, n):
        if data_type == 'kline':
            return generate_kline_data(n)
        elif data_type == 'vol':
            data = generate_kline_data(n)
            return (data['volume'].values.astype(np.float64), data['close'].values >= data['open'].values)
        elif data_type == 'quality':
            data = generate_kline_data(n)
            data['quality_score'] = np.random.uniform(0.5, 1.0, n)
            return data
        elif data_type == 'ohlcv':
            rng = np.random.RandomState(42)
            return [{'price': float(rng.uniform(10, 100)),
                     'open': float(rng.uniform(10, 100)),
                     'high': float(rng.uniform(10, 100)),
                     'low': float(rng.uniform(10, 100)),
                     'close': float(rng.uniform(10, 100)),
                     'volume': float(rng.uniform(1000, 100000))} for _ in range(n)]
        return None

    all_results = []
    for name, func, data_type in scalability_tests:
        print(f"\n  📈 {name}:")
        row = f"  {'规模':>10s}"
        for s in SCALE_POINTS:
            row += f"  {s:>7,}"
        print(row)

        times = []
        for s in SCALE_POINTS:
            arg = gen_arg(data_type, s)

            gc.collect()
            t0 = time.perf_counter()
            func(arg)
            elapsed = (time.perf_counter() - t0) * 1000
            times.append(elapsed)

        row = f"  {'耗时':>10s}"
        for t in times:
            row += f"  {t:>6.1f}ms"
        print(row)

        # Detect bottleneck: if time grows faster than O(n)
        if len(times) >= 2:
            ratios = [times[i+1]/times[i] for i in range(len(times)-1)]
            size_ratios = [SCALE_POINTS[i+1]/SCALE_POINTS[i] for i in range(len(SCALE_POINTS)-1)]
            bottleneck = ""
            for i, (tr, sr) in enumerate(zip(ratios, size_ratios)):
                if tr > sr * 1.3:  # >30% worse than linear
                    bottleneck = f"⚠️ {SCALE_POINTS[i]:,}→{SCALE_POINTS[i+1]:,}: "
                    bottleneck += f"O(n)期望{(sr*10):.1f}, 实际{(tr*10):.1f}"
                    break
            if not bottleneck:
                bottleneck = "✅ O(n) 线性扩展"
            print(f"  {'扩展性':>10s}  {bottleneck}")

        all_results.append(StressResult(name=name, sizes=SCALE_POINTS, times_ms=times, bottleneck=bottleneck))

    # ================================================================
    print(f"\n{'═' * 65}")
    print("  Phase 2: 并发加载模拟 (ThreadPoolExecutor)")
    print(f"{'═' * 65}")

    concurrent_results = []
    for n in [5000, 10000, 25000, 50000]:
        elapsed = simulate_concurrent_load(n, concurrency=4)
        concurrent_results.append((n, elapsed))

    # ================================================================
    print(f"\n{'═' * 65}")
    print("  Phase 3: 内存峰值分析 (50K)")
    print(f"{'═' * 65}")

    memory_peak_test(50000)

    # 整体内存脚印
    data_50k = generate_kline_data(50000)
    print(f"\n  📊 50K DataFrame 自身内存: {data_50k.memory_usage(deep=True).sum()/1024/1024:.1f}MB")
    cols = ['open', 'high', 'low', 'close', 'volume']
    gc.collect()
    tracemalloc.start()
    completeness_NEW(data_50k, cols)
    convert_values_NEW(data_50k)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"  全操作峰值内存: {peak/1024/1024:.1f}MB")

    # ================================================================
    print(f"\n{'═' * 65}")
    print("  Phase 4: 汇总分析")
    print(f"{'═' * 65}")

    print(f"\n  📊 可扩展性总览 (50K / 1K 比值):")
    print(f"  {'操作':<20s} {'1K耗时':>8s} {'50K耗时':>8s} {'增长率':>8s} {'瓶颈':>10s}")
    print(f"  {'─'*20} {'─'*8} {'─'*8} {'─'*8} {'─'*10}")
    max_ratio = 0
    max_name = ""
    for r in all_results:
        ratio = r.times_ms[-1] / r.times_ms[0] if r.times_ms[0] > 0 else float('inf')
        expected_ratio = r.sizes[-1] / r.sizes[0]
        status = "✅ 线性" if ratio <= expected_ratio * 1.2 else "⚠️ 超线性"
        print(f"  {r.name:<20s} {r.times_ms[0]:>7.1f}ms {r.times_ms[-1]:>7.1f}ms {ratio:>7.1f}x {status:>10s}")
        if ratio > max_ratio:
            max_ratio = ratio
            max_name = r.name

    print(f"\n  🔴 最大增长率: {max_name} ({max_ratio:.1f}x)")
    if max_ratio > 50:
        print(f"     ⚠️ {max_name} 在极端规模下可能成为瓶颈")

    print(f"\n  📊 并发加载 (4路):")
    for n, elapsed in concurrent_results:
        print(f"     {n:>5,}条/worker: {elapsed:>7.1f}ms ({elapsed/4:.1f}ms/worker)")

    # 结论
    print(f"\n{'═' * 65}")
    print(f"  🎯 瓶颈检测结论")
    print(f"{'═' * 65}")
    warnings = [r for r in all_results if r.bottleneck.startswith("⚠️")]
    if warnings:
        for w in warnings:
            print(f"  ⚠️ {w.name}: {w.bottleneck}")
    else:
        print(f"  ✅ 所有操作在50K规模下保持 O(n) 线性扩展，无瓶颈")
    print(f"  ✅ 4路并发加载 50K 数据: {concurrent_results[-1][1]:.0f}ms ({concurrent_results[-1][1]/4:.0f}ms/worker)")
    print(f"{'═' * 65}")
    return 0


if __name__ == "__main__":
    sys.exit(main())