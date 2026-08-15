#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R266 性能验证基准：十字光标 blit 局部重绘 vs 全画布重绘（真实 matplotlib Agg 画布）

场景（模拟 R265 前的卡顿环境）：
- 1200 根 K 线（PolyCollection 空心蜡烛）
- 成交量柱 + MA 线
- MACD 双线 + 柱状图（PolyCollection）

对比项：
1. 优化前：十字光标每次移动 -> canvas.draw()（全画布重绘）
2. 优化后：背景缓存一次 -> 每帧 restore_region + draw_artist + blit
3. MACD 柱状图：bar()（N 个 patch）vs PolyCollection（2 个 collection）构建耗时

用法：conda activate hikyuu; python scripts/bench_blit_perf.py
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
import numpy as np
import time

N_POINTS = 1200
N_MOVE = 200
WARMUP = 10  # 跳过前 N 次（首帧冷启动）

rng = np.random.default_rng(42)
close = np.cumsum(rng.standard_normal(N_POINTS)) + 100
open_ = close + rng.standard_normal(N_POINTS) * 0.5
high = np.maximum(open_, close) + rng.random(N_POINTS)
low = np.minimum(open_, close) - rng.random(N_POINTS)
vol = rng.integers(1000, 10000, N_POINTS)
x = np.arange(N_POINTS)

# MACD（与 indicator_mixin._calculate_macd 一致的算法）
exp1 = pd_close = None
from pandas import Series
_s = Series(close)
exp1 = _s.ewm(span=12, adjust=False).mean()
exp2 = _s.ewm(span=26, adjust=False).mean()
macd = exp1 - exp2
signal = macd.ewm(span=9, adjust=False).mean()
hist = macd - signal


def build_chart():
    """构建真实图表：K线(1200) + 成交量 + MACD（复用 R265/R266 渲染方式）"""
    fig, (ax_p, ax_v, ax_i) = plt.subplots(3, 1, figsize=(14, 9), sharex=True)
    half_w = 0.3

    # K线 空心蜡烛 PolyCollection（仿 chart_renderer._render_candlesticks_efficient）
    is_up = close >= open_
    def body_verts(mask):
        xs = x[mask]
        o = open_[mask]
        c = close[mask]
        v = np.empty((len(xs), 4, 2))
        v[:, 0, 0] = xs - half_w; v[:, 0, 1] = o
        v[:, 1, 0] = xs - half_w; v[:, 1, 1] = c
        v[:, 2, 0] = xs + half_w; v[:, 2, 1] = c
        v[:, 3, 0] = xs + half_w; v[:, 3, 1] = o
        return v
    up_v = body_verts(is_up)
    dn_v = body_verts(~is_up)
    if len(up_v):
        ax_p.add_collection(PolyCollection(up_v, facecolors='red', edgecolors='red', linewidths=0.2))
    if len(dn_v):
        ax_p.add_collection(PolyCollection(dn_v, facecolors='green', edgecolors='green', linewidths=0.2))

    # MA 线（与 MA20 渲染一致）
    ma20 = _s.rolling(20).mean()
    ax_p.plot(x, ma20.values, color='#fbc02d', lw=0.8, alpha=0.85)

    # 成交量
    ax_v.bar(x, vol, width=0.6, color='#8888cc', alpha=0.8)

    # MACD 线
    ax_i.plot(x, macd.values, color='#1976d2', lw=0.7, alpha=0.85)
    ax_i.plot(x, signal.values, color='#ab47bc', lw=0.7, alpha=0.85)

    # MACD 柱状图 PolyCollection（R265/R266：1 artist 替代 N patch）
    def hist_verts(mask):
        xs = x[mask]
        hs = hist.values[mask]
        v = np.empty((len(xs), 4, 2))
        v[:, 0, 0] = xs - half_w; v[:, 0, 1] = 0
        v[:, 1, 0] = xs - half_w; v[:, 1, 1] = hs
        v[:, 2, 0] = xs + half_w; v[:, 2, 1] = hs
        v[:, 3, 0] = xs + half_w; v[:, 3, 1] = 0
        return v
    hmask = hist.values >= 0
    up_h = hist_verts(hmask)
    dn_h = hist_verts(~hmask)
    if len(up_h):
        ax_i.add_collection(PolyCollection(up_h, facecolors='red', alpha=0.5))
    if len(dn_h):
        ax_i.add_collection(PolyCollection(dn_h, facecolors='green', alpha=0.5))

    ax_p.set_xlim(0, N_POINTS - 1)
    fig.canvas.draw()  # 首次渲染
    return fig, ax_p


def bench_full_redraw():
    """优化前：每次移动 -> 全画布 draw（等价 draw_idle 的完整重绘）"""
    fig, ax_p = build_chart()
    vline = ax_p.axvline(0, color='gray', ls='--', lw=1)
    vline.set_visible(True)
    fig.canvas.draw()
    times = []
    for i in range(N_MOVE):
        vline.set_xdata([i % N_POINTS, i % N_POINTS])
        t0 = time.perf_counter()
        fig.canvas.draw()
        times.append((time.perf_counter() - t0) * 1000)
    plt.close(fig)
    return np.mean(times[WARMUP:])


def bench_blit():
    """优化后：背景缓存一次 + 每帧 restore_region + draw_artist + blit"""
    fig, ax_p = build_chart()
    vline = ax_p.axvline(0, color='gray', ls='--', lw=1)
    vline.set_visible(True)
    fig.canvas.draw()

    # 背景重建耗时（首次/全量重绘后发生一次）
    t0 = time.perf_counter()
    fig.canvas.draw()
    bg = fig.canvas.copy_from_bbox(fig.bbox)
    rebuild_ms = (time.perf_counter() - t0) * 1000

    times = []
    for i in range(N_MOVE):
        vline.set_xdata([i % N_POINTS, i % N_POINTS])
        t0 = time.perf_counter()
        fig.canvas.restore_region(bg)
        ax_p.draw_artist(vline)
        fig.canvas.blit(fig.bbox)
        times.append((time.perf_counter() - t0) * 1000)
    plt.close(fig)
    return np.mean(times[WARMUP:]), rebuild_ms


def bench_macd_bar_vs_poly():
    """MACD 柱状图：bar()（N patch）vs PolyCollection（2 collection）构建耗时"""
    # bar() 版本
    fig, (ax_i1) = plt.subplots(1, 1, figsize=(6, 4))
    t0 = time.perf_counter()
    ax_i1.bar(x, hist.values, width=0.6)
    bar_ms = (time.perf_counter() - t0) * 1000
    bar_artist_count = len(ax_i1.patches)
    plt.close(fig)

    # PolyCollection 版本
    fig2, (ax_i2) = plt.subplots(1, 1, figsize=(6, 4))
    half_w = 0.3
    def hist_verts(mask):
        xs = x[mask]
        hs = hist.values[mask]
        v = np.empty((len(xs), 4, 2))
        v[:, 0, 0] = xs - half_w; v[:, 0, 1] = 0
        v[:, 1, 0] = xs - half_w; v[:, 1, 1] = hs
        v[:, 2, 0] = xs + half_w; v[:, 2, 1] = hs
        v[:, 3, 0] = xs + half_w; v[:, 3, 1] = 0
        return v
    hmask = hist.values >= 0
    t0 = time.perf_counter()
    up_h = hist_verts(hmask)
    dn_h = hist_verts(~hmask)
    if len(up_h):
        ax_i2.add_collection(PolyCollection(up_h, facecolors='red', alpha=0.5))
    if len(dn_h):
        ax_i2.add_collection(PolyCollection(dn_h, facecolors='green', alpha=0.5))
    poly_ms = (time.perf_counter() - t0) * 1000
    poly_artist_count = len(ax_i2.collections)
    plt.close(fig2)
    return bar_ms, poly_ms, bar_artist_count, poly_artist_count


if __name__ == '__main__':
    print("=" * 68)
    print(f"十字光标移动性能对比 (真实Agg画布, K线={N_POINTS}根 + MACD, {N_MOVE}次移动)")
    print("=" * 68)

    avg_full = bench_full_redraw()
    avg_blit, rebuild_ms = bench_blit()

    print(f"优化前 全画布 draw_idle : {avg_full:8.3f} ms/帧")
    print(f"优化后  blit 局部重绘   : {avg_blit:8.3f} ms/帧")
    if avg_blit > 0:
        print(f"加速比                   : {avg_full / avg_blit:8.1f} 倍")
    print(f"blit 背景重建(全画布+copy): {rebuild_ms:8.3f} ms (仅首次/全量重绘后)")
    print()

    print("=" * 68)
    print("MACD 柱状图构建耗时对比 (1200 柱)")
    print("=" * 68)
    bar_ms, poly_ms, bar_cnt, poly_cnt = bench_macd_bar_vs_poly()
    print(f"bar()           : {bar_ms:8.3f} ms, artist 数 = {bar_cnt}")
    print(f"PolyCollection  : {poly_ms:8.3f} ms, artist 数 = {poly_cnt}")
    if poly_ms > 0:
        print(f"构建提速         : {bar_ms / poly_ms:8.1f} 倍")
    print(f"artist 削减      : {bar_cnt} -> {poly_cnt} 个 ({bar_cnt / max(poly_cnt, 1):.0f} 倍)")
    print()
    print("提示: 全画布重绘成本 ∝ artist 总数, bar→PolyCollection 后每帧重绘/缩放成本同步下降。")
