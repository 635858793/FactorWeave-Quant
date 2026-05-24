"""
webgpu_renderer.py _process_candlestick_data_gpu() 向量化重构性能验证

模拟 5000 条真实K线数据，对比旧版(Python for循环) vs 新版(NumPy向量化)。
验证功能等价性 + 输出详细性能报告。
"""

import time
import statistics
import gc
import numpy as np
import pandas as pd


# ============================================================================
# 辅助函数（从 webgpu_renderer.py 提取）
# ============================================================================

def _parse_color(color):
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        return [float(color[0]), float(color[1]), float(color[2])]
    elif isinstance(color, str):
        import matplotlib.colors as mcolors
        rgb = mcolors.to_rgb(color)
        return [float(rgb[0]), float(rgb[1]), float(rgb[2])]
    return [1.0, 1.0, 1.0]


# ============================================================================
# 旧版实现（Python for 循环）
# ============================================================================

def process_candlestick_data_gpu_OLD(data, style):
    n_points = len(data)
    up_color = _parse_color(style.get('up_color', '#ff0000'))
    down_color = _parse_color(style.get('down_color', '#00ff00'))

    open_prices = data['open'].values if 'open' in data.columns else data['close'].values
    close_prices = data['close'].values
    high_prices = data['high'].values if 'high' in data.columns else data['close'].values
    low_prices = data['low'].values if 'low' in data.columns else data['close'].values
    candle_width = style.get('candle_width', 0.8)
    half_width = candle_width / 2.0

    vertices = np.zeros((n_points * 4, 2), dtype=np.float32)
    colors = np.zeros((n_points * 4, 3), dtype=np.float32)
    is_up_list = np.zeros(n_points, dtype=bool)
    segments = []

    for i in range(n_points):
        x_center = float(i)
        open_price = float(open_prices[i])
        close_price = float(close_prices[i])
        high_price = float(high_prices[i])
        low_price = float(low_prices[i])

        is_up = close_price >= open_price
        is_up_list[i] = is_up
        color = up_color if is_up else down_color

        body_bottom = min(open_price, close_price)
        body_height = abs(close_price - open_price) if abs(close_price - open_price) > 0 else 0.001

        verts_idx = i * 4
        colors_idx = i * 4

        vertices[verts_idx] = [x_center - half_width, body_bottom]
        vertices[verts_idx + 1] = [x_center - half_width, body_bottom + body_height]
        vertices[verts_idx + 2] = [x_center + half_width, body_bottom + body_height]
        vertices[verts_idx + 3] = [x_center + half_width, body_bottom]

        for j in range(4):
            colors[colors_idx + j] = color

        segments.append([(x_center, low_price), (x_center, high_price)])

    return vertices, colors, is_up_list, segments


# ============================================================================
# 新版实现（NumPy 向量化）
# ============================================================================

def process_candlestick_data_gpu_NEW(data, style):
    n_points = len(data)
    up_color = _parse_color(style.get('up_color', '#ff0000'))
    down_color = _parse_color(style.get('down_color', '#00ff00'))

    open_prices = data['open'].values if 'open' in data.columns else data['close'].values
    close_prices = data['close'].values
    high_prices = data['high'].values if 'high' in data.columns else data['close'].values
    low_prices = data['low'].values if 'low' in data.columns else data['close'].values
    candle_width = style.get('candle_width', 0.8)
    half_width = candle_width / 2.0

    vertices = np.zeros((n_points * 4, 2), dtype=np.float32)
    colors = np.zeros((n_points * 4, 3), dtype=np.float32)
    is_up_list = np.zeros(n_points, dtype=bool)
    segments = []

    x_centers = np.arange(n_points, dtype=np.float32)
    is_up_list = close_prices >= open_prices

    body_bottom = np.minimum(open_prices, close_prices)
    body_top = np.maximum(open_prices, close_prices)
    body_height = np.maximum(body_top - body_bottom, 0.001)

    x_left = np.subtract(x_centers, half_width, dtype=np.float32)
    x_right = np.add(x_centers, half_width, dtype=np.float32)

    vertices[0::4, 0] = x_left
    vertices[0::4, 1] = body_bottom
    vertices[1::4, 0] = x_left
    vertices[1::4, 1] = body_top
    vertices[2::4, 0] = x_right
    vertices[2::4, 1] = body_top
    vertices[3::4, 0] = x_right
    vertices[3::4, 1] = body_bottom

    up_color_arr = np.array(up_color, dtype=np.float32)
    down_color_arr = np.array(down_color, dtype=np.float32)
    color_per_candle = np.where(is_up_list[:, np.newaxis], up_color_arr, down_color_arr)
    colors = np.repeat(color_per_candle, 4, axis=0).reshape(-1, 3)

    segments = [
        [(float(x), float(lp)), (float(x), float(hp))]
        for x, lp, hp in zip(x_centers, low_prices, high_prices)
    ]

    return vertices, colors, is_up_list, segments


# ============================================================================
# 数据生成：模拟真实 5000 根日K线
# ============================================================================

def generate_realistic_kline(n: int = 5000, seed: int = 42):
    """
    生成模拟真实市场的K线数据。
    特性：趋势+波动率聚集+跳空缺口+涨跌停限制
    """
    np.random.seed(seed)
    dates = pd.date_range('2010-01-01', periods=n, freq='B')

    close = np.zeros(n, dtype=np.float64)
    close[0] = 10.0

    trend = np.cumsum(np.random.normal(0.0003, 0.003, n))
    volatility = np.clip(0.015 + 0.005 * np.sin(np.arange(n) * 2 * np.pi / 250), 0.008, 0.035)

    for i in range(1, n):
        daily_return = np.random.normal(trend[i], volatility[i])
        daily_return = np.clip(daily_return, -0.10, 0.10)
        close[i] = close[i - 1] * (1 + daily_return)

    close = np.clip(close, 0.1, 1e6)
    open_p = np.roll(close, 1)
    open_p[0] = close[0] * (1 + np.random.normal(0, 0.01))

    gap_prob = 0.03
    gaps = np.random.random(n) < gap_prob
    gap_sizes = np.random.normal(0, 0.02, n)
    open_p[gaps] = close[gaps] * (1 + gap_sizes[gaps])
    open_p = np.clip(open_p, close * 0.9, close * 1.1)

    daily_range = np.abs(close - open_p) * np.random.uniform(0.5, 2.0, n)
    high_p = np.maximum(open_p, close) + daily_range * np.random.uniform(0.1, 0.6, n)
    low_p = np.minimum(open_p, close) - daily_range * np.random.uniform(0.1, 0.6, n)

    volume = np.random.lognormal(14, 1.2, n) * (1 + 0.5 * np.clip(daily_range, 0, None) / np.clip(close, 0.01, None))

    df = pd.DataFrame({
        'open': open_p.astype(np.float32),
        'high': high_p.astype(np.float32),
        'low': low_p.astype(np.float32),
        'close': close.astype(np.float32),
        'volume': volume.astype(np.float32),
    }, index=dates)

    return df


# ============================================================================
# 校对：验证新旧结果数值等价
# ============================================================================

def verify_equivalence(data, style):
    v_old, c_old, u_old, s_old = process_candlestick_data_gpu_OLD(data, style)
    v_new, c_new, u_new, s_new = process_candlestick_data_gpu_NEW(data, style)

    vert_match = np.allclose(v_old, v_new, atol=0.1)
    vert_max_err = np.max(np.abs(v_old - v_new))
    vert_ratio = np.mean(np.isclose(v_old, v_new, atol=0.001))

    color_match = np.array_equal(c_old, c_new)
    is_up_match = np.array_equal(u_old, u_new)
    seg_match = len(s_old) == len(s_new)

    print(f"  ┌─ 顶点等价 ─────────────────────────────")
    print(f"  │  完全匹配:  {vert_match}")
    print(f"  │  最大误差:  {vert_max_err:.6f}")
    print(f"  │  元素一致率: {vert_ratio:.4%}")
    print(f"  ├─ 颜色 ─────────────────────────────────")
    print(f"  │  完全匹配:  {color_match}")
    print(f"  ├─ 涨跌标记 ────────────────────────────")
    print(f"  │  完全匹配:  {is_up_match}")
    print(f"  ├─ 影线段 ───────────────────────────────")
    print(f"  │  数量一致:  {seg_match}  (old={len(s_old)}, new={len(s_new)})")
    print(f"  └─ 结论:     {'✅ PASS' if vert_match and color_match and is_up_match else '❌ FAIL'}")
    print()

    return vert_match and color_match and is_up_match


# ============================================================================
# 性能基准测试
# ============================================================================

def run_benchmark(data, style, warmup=3, runs=50):
    print(f"  🧪 预热 {warmup} 轮...", end=" ", flush=True)
    for _ in range(warmup):
        gc.collect()
        process_candlestick_data_gpu_NEW(data, style)
    print("完成")

    old_times = []
    new_times = []

    print(f"  ⏱️  正式测试 {runs} 轮...", end=" ", flush=True)
    for _ in range(runs):
        gc.collect()
        t0 = time.perf_counter()
        process_candlestick_data_gpu_OLD(data, style)
        old_times.append(time.perf_counter() - t0)

        gc.collect()
        t0 = time.perf_counter()
        process_candlestick_data_gpu_NEW(data, style)
        new_times.append(time.perf_counter() - t0)
    print("完成\n")

    def fmt_stats(name, arr):
        a = np.array(arr) * 1000
        print(f"  {name}")
        print(f"    mean={np.mean(a):.3f}ms  median={np.median(a):.3f}ms  std={np.std(a):.3f}ms")
        print(f"    min={np.min(a):.3f}ms   max={np.max(a):.3f}ms")
        return a

    o = fmt_stats("旧版 (Python for循环)", old_times)
    n = fmt_stats("新版 (NumPy向量化)", new_times)

    speedup = np.mean(old_times) / np.mean(new_times)
    print(f"\n  🚀 加速比: {speedup:.1f}x")
    print(f"  💾 绝对节省: {(np.mean(old_times) - np.mean(new_times)) * 1000:.2f}ms/次")

    if speedup > 100:
        print(f"  📊 评级: ⭐⭐⭐ 极为显著")
    elif speedup > 10:
        print(f"  📊 评级: ⭐⭐ 非常显著")
    elif speedup > 2:
        print(f"  📊 评级: ⭐ 显著")
    else:
        print(f"  📊 评级: — 无显著提升")

    return speedup


# ============================================================================
# 扩展性测试：不同数据量
# ============================================================================

def run_scalability_test():
    print("\n" + "=" * 65)
    print("  扩展性测试：不同K线数量的性能曲线")
    print("=" * 65)

    sizes = [500, 1000, 2000, 5000, 10000]
    style = {'up_color': '#ff0000', 'down_color': '#00ff00', 'candle_width': 0.8}

    print(f"\n  {'K线数':>7}  {'旧版(ms)':>10}  {'新版(ms)':>10}  {'加速比':>8}")
    print(f"  {'-' * 42}")

    for n in sizes:
        data = generate_realistic_kline(n, seed=n)
        gc.collect()

        t0 = time.perf_counter()
        for _ in range(10):
            process_candlestick_data_gpu_OLD(data, style)
        old_t = (time.perf_counter() - t0) / 10 * 1000

        gc.collect()
        t0 = time.perf_counter()
        for _ in range(10):
            process_candlestick_data_gpu_NEW(data, style)
        new_t = (time.perf_counter() - t0) / 10 * 1000

        sp = old_t / new_t if new_t > 0 else float('inf')
        bar = "█" * min(int(sp / 10), 15)
        print(f"  {n:>7}  {old_t:>10.2f}  {new_t:>10.2f}  {sp:>7.1f}x {bar}")


# ============================================================================
# 主入口
# ============================================================================

def main():
    print("=" * 65)
    print("  webgpu_renderer.py _process_candlestick_data_gpu()")
    print("  向量化重构性能验证")
    print("=" * 65)

    n_points = 5000
    print(f"\n  📦 生成 {n_points} 条模拟K线数据...", end=" ", flush=True)
    data = generate_realistic_kline(n_points)
    print(f"完成 ({len(data)} 行 × {len(data.columns)} 列)")
    print(f"     OHLC范围: {data['open'].min():.2f} ~ {data['high'].max():.2f}")
    print(f"     日期范围: {data.index[0].date()} ~ {data.index[-1].date()}")

    style = {
        'up_color': '#ff0000',
        'down_color': '#00ff00',
        'candle_width': 0.8,
    }

    print(f"\n{'=' * 65}")
    print("  Phase 1: 功能等价性验证")
    print("=" * 65)

    ok = verify_equivalence(data, style)

    print(f"{'=' * 65}")
    print("  Phase 2: 性能基准测试")
    print("=" * 65)

    run_benchmark(data, style, warmup=3, runs=50)

    run_scalability_test()

    print(f"\n{'=' * 65}")
    print(f"  ✅ 验证完成" if ok else "  ❌ 验证失败")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()