#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HV6 实测（R292-HV6/HV6.2）：K 线（5 万/10 万行可参数化）+ 模拟 tick 流
→ 真实增量渲染链流畅性验证

与生产一致的生产路径：
  - _full_kdata = 全量 N_BARS 根（原始数据，CLI --bars 可配：50000 / 100000 极端场景）
  - current_kdata = 降采样视图 ≤1200 根（update_chart L253 _downsample_kdata；
    分桶采样 _bucket_key_indices 强制保留末行 → 视图末行=全量末行）
  - collections 基于视图构建（画布上只有 ~1200 根，与生产相同）
  - tick 流走真实 RenderingMixin._handle_realtime_tick → _update_last_bar_with_tick：
    更新视图+全量各自末行 OHLCV → HV6.2 末根 overlay 独立集合重建（单根 draw）
    → BlitEngine.render（blit 快路径）+ refresh_background 同步快照

对照：生产每 tick 全量（update_chart 等价：重新降采样 → 清场 → 重建视图集合 → draw）

流畅标准：单 tick < 16ms（60fps 级）；< 33ms（30fps 级）；> 33ms（卡顿，
性能日志慢 tick 告警阈值）。

用法：
  python tests/bench_tick_incremental_50k.py                # 5 万行（默认）
  python tests/bench_tick_incremental_50k.py --bars 100000  # 10 万行极端场景
  python tests/bench_tick_incremental_50k.py --bars 100000 --view 2400 --ticks 200
"""
import os
import sys
import time
import argparse
import importlib.util

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use('Agg')  # 必须在 pyplot 之前
import matplotlib.pyplot as plt

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)
from core.utils.mpl_blit import BlitEngine  # noqa: E402

N_BARS = 50000
N_TICKS = 100
N_FULL = 30  # 全量对照次数（生产全量含降采样+重建+draw，单次数十~百ms）
VIEW_POINTS = 1200  # 与 _downsample_kdata 默认 max_points 一致

# ---- 加载真实 RenderingMixin（dummy 模块注册，与测试套件一致）----
from unittest.mock import MagicMock  # noqa: E402
_dummy_pkg = MagicMock()
_dummy_pkg.__name__ = 'gui.widgets.chart_mixins'
_dummy_pkg.__file__ = '<mock>'
_dummy_ui = MagicMock()
_dummy_ui.__name__ = 'gui.widgets.chart_mixins.ui_mixin'
_dummy_ui.__file__ = '<mock>'
sys.modules.setdefault('gui.widgets.chart_mixins', _dummy_pkg)
sys.modules.setdefault('gui.widgets.chart_mixins.ui_mixin', _dummy_ui)

CHART_MIXINS = os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins')
_spec = importlib.util.spec_from_file_location(
    'rendering_mixin_bench', os.path.join(CHART_MIXINS, 'rendering_mixin.py'))
render_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(render_mod)
RenderingMixin = render_mod.RenderingMixin

KLINE_KEYS = ['up', 'down', 'limit_up', 'limit_down',
              'shadow_up', 'shadow_down', 'shadow_limit_up', 'shadow_limit_down']
VOLUME_KEYS = ['up', 'down', 'limit_up', 'limit_down']


def make_kdata(n, symbol='300994'):
    rng = np.random.default_rng(42)
    close = np.cumsum(rng.standard_normal(n)) + 100
    open_ = close + rng.standard_normal(n) * 0.5
    high = np.maximum(open_, close) + rng.random(n)
    low = np.minimum(open_, close) - rng.random(n)
    volume = rng.integers(1000, 10000, n)
    df = pd.DataFrame({
        'symbol': symbol,
        'open': open_, 'high': high, 'low': low,
        'close': close, 'volume': volume,
        'datetime': pd.date_range('2024-01-01 09:30', periods=n, freq='1min'),
    })
    df['limit_up'] = False
    df['limit_down'] = False
    # 末根强制阳线（tick 更新确定性）
    df.iat[n - 1, df.columns.get_loc('close')] = df['open'].iloc[-1] + 0.5
    df.iat[n - 1, df.columns.get_loc('high')] = df['open'].iloc[-1] + 0.6
    df.iat[n - 1, df.columns.get_loc('low')] = df['open'].iloc[-1] - 0.1
    return df


def sample_view(full, max_points=VIEW_POINTS):
    """模拟 _downsample_kdata 的视图：分桶等距采样 + 强制保留末行（等价前提）"""
    n = len(full)
    if n <= max_points:
        return full.copy()
    idx = np.linspace(0, n - 1, max_points).astype(int)
    idx = np.unique(np.concatenate([idx, [n - 1]]))
    return full.iloc[idx].reset_index(drop=True)


class _Widget(RenderingMixin):
    pass


def build_widget(n, view_points=VIEW_POINTS):
    """真实 RenderingMixin 对象 + 真实渲染链：full n 根 + 视图 ≤view_points 根"""
    from optimization.chart_renderer import ChartRenderer
    r = ChartRenderer.__new__(ChartRenderer)
    r.render_error = MagicMock()
    full = make_kdata(n)
    view = sample_view(full, view_points)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    kc = r._render_candlesticks_efficient(
        ax1, view, {}, x=np.arange(len(view)), use_datetime_axis=False)
    vc = r._render_volume_vectorized(
        ax2, view, {}, x=np.arange(len(view)), use_datetime_axis=False)
    w = _Widget.__new__(_Widget)
    w.renderer = r
    w.price_ax = ax1
    w.volume_ax = ax2
    w._kline_collections = {k: v for k, v in zip(KLINE_KEYS, kc)}
    w._volume_collections = {k: v for k, v in zip(VOLUME_KEYS, vc)}
    w.current_kdata = view.copy()
    w._full_kdata = full.copy()
    w._ymin = float(view['low'].min())
    w._ymax = float(view['high'].max())
    w.chart_type = 'K线图'
    w.current_period = '1min'
    w.current_stock = '300994'
    w.canvas = fig.canvas
    w._blit_engine = BlitEngine(fig.canvas, log_tag='[Bench50k]', sample_every=0)
    return w, fig


def stats_ms(times):
    a = np.array(times)
    return (a.mean(), np.percentile(a, 50), np.percentile(a, 95), a.max())


def bench_incremental(w, n_ticks, breakout=False):
    """真实 _handle_realtime_tick：bar 内 tick（默认 ylim 内；breakout 持续突破）"""
    times = []
    last_dt = w.current_kdata['datetime'].iloc[-1]
    ts = last_dt.strftime('%Y-%m-%d %H:%M:%S')
    base = float(w.current_kdata['open'].iloc[-1])
    rng = np.random.default_rng(7)
    # 预热 2 tick：HV6.2 overlay 首次惰性建立（拆末根+建空集合）+ blit 快照初始化，
    # 均为一次性成本，不计入基准（否则污染首个 tick 计时）
    for _ in range(2):
        p = base + rng.normal(0, 0.02)
        w._handle_realtime_tick({
            'symbol': '300994', 'price': float(p), 'volume': 100, 'timestamp': ts})
    if hasattr(w, '_tick_perf_stats'):
        del w._tick_perf_stats  # 重置统计：正式计时的阶段均值为干净基线
    for k in range(n_ticks):
        p = (w._ymax + 0.5 + k * 0.001) if breakout else (base + rng.normal(0, 0.02))
        t0 = time.perf_counter()
        w._handle_realtime_tick({
            'symbol': '300994', 'price': float(p), 'volume': 100, 'timestamp': ts})
        times.append((time.perf_counter() - t0) * 1000)
    return times


def bench_full(fig, full, n_ticks, view_points=VIEW_POINTS):
    """生产每 tick 全量：更新 full 末行 → 重新降采样 → 清场重建视图集合 → draw"""
    from optimization.chart_renderer import ChartRenderer
    r = ChartRenderer.__new__(ChartRenderer)
    r.render_error = MagicMock()
    ax1, ax2 = fig.axes
    times = []
    base = float(full['open'].iloc[-1])
    rng = np.random.default_rng(7)
    last_idx = len(full) - 1
    for k in range(n_ticks):
        p = base + rng.normal(0, 0.02)
        full.iat[last_idx, full.columns.get_loc('close')] = p
        full.iat[last_idx, full.columns.get_loc('high')] = max(
            full['high'].iloc[-1], p)
        t0 = time.perf_counter()
        view = sample_view(full, view_points)
        for a in list(ax1.lines) + list(ax1.collections) + list(ax1.texts) + \
                list(ax2.lines) + list(ax2.collections) + list(ax2.texts):
            a.remove()
        r._render_candlesticks_efficient(
            ax1, view, {}, x=np.arange(len(view)), use_datetime_axis=False)
        r._render_volume_vectorized(
            ax2, view, {}, x=np.arange(len(view)), use_datetime_axis=False)
        fig.canvas.draw()
        times.append((time.perf_counter() - t0) * 1000)
    return times


def verdict(avg):
    if avg < 16:
        return '极流畅（60fps 级，无可感知卡顿）'
    if avg < 33:
        return '流畅（30fps 级，轻微可感知但可用）'
    return '卡顿（>33ms，性能日志慢 tick 告警阈值）'


def main():
    parser = argparse.ArgumentParser(description='HV6.2 tick 增量渲染基准（5万/10万行可配）')
    parser.add_argument('--bars', type=int, default=N_BARS,
                        help=f'全量 K 线根数（默认 {N_BARS}，10 万行极端场景传 100000）')
    parser.add_argument('--view', type=int, default=VIEW_POINTS,
                        help=f'视图降采样点数（默认 {VIEW_POINTS}，与 _downsample_kdata 一致）')
    parser.add_argument('--ticks', type=int, default=N_TICKS,
                        help=f'bar 内 tick 数（默认 {N_TICKS}）')
    parser.add_argument('--full', type=int, default=N_FULL,
                        help=f'全量对照次数（默认 {N_FULL}）')
    args = parser.parse_args()
    n_bars, view_points, n_ticks, n_full = args.bars, args.view, args.ticks, args.full

    print('=' * 78)
    print(f'{n_bars:,} 行 K 线 + 模拟 tick 流实测'
          f'（真实生产路径：视图≤{view_points}根 + 全量{n_bars:,}根）')
    print(f'K 线 {n_bars:,} 根，视图 {view_points} 根，bar 内 tick {n_ticks} 个')
    print('=' * 78)

    # ---- 首次全量渲染（update_chart 等价，一次性成本）----
    t0 = time.perf_counter()
    w, fig = build_widget(n_bars, view_points)
    full_first_ms = (time.perf_counter() - t0) * 1000
    print(f'\n[首次全量渲染(降采样+构建集合+首帧)] {full_first_ms:.1f}ms（一次性）')
    print(f'  视图 {len(w.current_kdata)} 根 vs 全量 {len(w._full_kdata):,} 根')

    # ---- 路径 A：增量（ylim 内，纯 blit 快路径）----
    times_a = bench_incremental(w, n_ticks, breakout=False)
    avg_a, p50_a, p95_a, max_a = stats_ms(times_a)
    st = w._tick_perf_stats
    print(f'\n[路径A 增量(blit)] {n_ticks} 个 bar 内 tick（ylim 内）:')
    print(f'  avg={avg_a:.2f}ms  p50={p50_a:.2f}ms  p95={p95_a:.2f}ms  max={max_a:.2f}ms')
    print(f'  阶段avg: 数据更新={st["stage_data_ms"]/st["bar_count"]:.2f}ms '
          f'K线verts={st["stage_kline_ms"]/st["bar_count"]:.2f}ms '
          f'成交量verts={st["stage_volume_ms"]/st["bar_count"]:.2f}ms '
          f'blit={st["stage_blit_ms"]/st["bar_count"]:.2f}ms')
    print(f'  流畅性判定: {verdict(avg_a)}')
    # 数据一致性（索引错位修复验证）：视图末行与全量末行同步
    assert w.current_kdata['close'].iloc[-1] == w._full_kdata['close'].iloc[-1], \
        '视图末行与全量末行应同步'
    plt.close(fig)

    # ---- 路径 B：生产全量对照 ----
    full_f = make_kdata(n_bars)
    fig_f, ax_f = plt.subplots(2, 1, figsize=(12, 8))
    from optimization.chart_renderer import ChartRenderer
    r0 = ChartRenderer.__new__(ChartRenderer)
    r0.render_error = MagicMock()
    view_f = sample_view(full_f, view_points)
    r0._render_candlesticks_efficient(
        ax_f[0], view_f, {}, x=np.arange(len(view_f)), use_datetime_axis=False)
    r0._render_volume_vectorized(
        ax_f[1], view_f, {}, x=np.arange(len(view_f)), use_datetime_axis=False)
    times_b = bench_full(fig_f, full_f, n_full, view_points)
    avg_b, p50_b, p95_b, max_b = stats_ms(times_b)
    print(f'\n[路径B 生产全量(降采样+清场+重建+draw)] {n_full} 次:')
    print(f'  avg={avg_b:.2f}ms  p50={p50_b:.2f}ms  p95={p95_b:.2f}ms  max={max_b:.2f}ms')
    plt.close(fig_f)

    # ---- 路径 C：增量 worst case（持续突破 ylim → 每 tick 背景重建）----
    w2, fig2 = build_widget(n_bars, view_points)
    times_c = bench_incremental(w2, 40, breakout=True)
    avg_c, p50_c, p95_c, max_c = stats_ms(times_c)
    print(f'\n[路径C 增量worst-case(持续突破ylim→背景重建)] 40 tick:')
    print(f'  avg={avg_c:.2f}ms  p50={p50_c:.2f}ms  p95={p95_c:.2f}ms  max={max_c:.2f}ms')
    plt.close(fig2)

    # ---- 汇总 ----
    print('\n' + '=' * 78)
    print(f'汇总（{n_bars:,} 行 K 线，生产路径）:')
    print(f'  增量(blit) avg {avg_a:.2f}ms/tick → {verdict(avg_a)}')
    print(f'  生产全量   avg {avg_b:.2f}ms/tick → 加速 {(avg_b/avg_a):.1f}x')
    print(f'  增量(突破) avg {avg_c:.2f}ms/tick → 背景重建退化场景')
    print('=' * 78)
    k_verts = st['stage_kline_ms'] / st['bar_count']
    blit_ms = st['stage_blit_ms'] / st['bar_count']
    if avg_a >= 33:
        print(f'结论: {n_bars:,} 行下增量仍卡顿。瓶颈: K线verts重建 {k_verts:.1f}ms / blit {blit_ms:.1f}ms')
        print('      → 高价值优化项：向量化 build_candle_groups（当前逐行 Python 循环）。')
    else:
        print(f'结论: {n_bars:,} 行下增量流畅（{avg_a:.1f}ms < 33ms），无卡顿。')
        print(f'      K线verts重建 {k_verts:.1f}ms 为主要成本，数据量更大时优先向量化。')


if __name__ == '__main__':
    main()
