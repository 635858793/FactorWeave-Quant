#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HV6 基准：模拟 tick 数据流，实证「增量更新(BlitEngine)」是否真的比「全量重绘(draw_idle)」快。

背景（铁律㉟：性能优化须基准实证再启用）：
实施 tick 增量渲染前，先在本地构造模拟 tick 流验证收益，避免基于臆测优化。

路径 A（增量 / 提议方案）：
  bar 内 tick → set_verts/set_segments 更新受影响的 artist（仅对应 collection）
  → BlitEngine.render() 走 blit 快路径（背景已缓存：restore_region + draw_artist + blit）

路径 B（全量 / 现状 rendering_mixin.update_chart L277-281 清场循环 + L518 draw_idle）：
  每个 tick → 移除 ax 全部 artists → 重建 8 个 collection → autoscale_view → draw_idle（全画布 draw + 光栅化）

公平性：
- 同一真实 FigureCanvasAgg，Agg 后端 blit 为真实实现
- 增量首次渲染预热（BlitEngine 首帧重建背景，不计入 tick 计时）
- 多轮取平均；tick 价格保持在现有 ylim 内（bar 内更新，x 不变 ylim 稳定）
"""
import os
import sys
import time

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use('Agg')  # 必须在 pyplot 之前
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection, LineCollection

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.utils.mpl_blit import BlitEngine

N_BARS = 1200
N_TICKS = 60
ROUNDS = 3


def make_kdata(n):
    """与测试套件同款确定性数据 + limit 列（列优先，全 False）"""
    rng = np.random.default_rng(42)
    close = np.cumsum(rng.standard_normal(n)) + 100
    open_ = close + rng.standard_normal(n) * 0.5
    high = np.maximum(open_, close) + rng.random(n)
    low = np.minimum(open_, close) - rng.random(n)
    volume = rng.integers(1000, 10000, n)
    df = pd.DataFrame({
        'open': open_, 'high': high, 'low': low,
        'close': close, 'volume': volume,
    })
    df['limit_up'] = False
    df['limit_down'] = False
    # 基准前提：末根 bar 强制为阳线（close >= open，属 up 集合）
    df.iat[n - 1, df.columns.get_loc('close')] = df['open'].iloc[-1] + 0.5
    df.iat[n - 1, df.columns.get_loc('high')] = df['open'].iloc[-1] + 0.6
    df.iat[n - 1, df.columns.get_loc('low')] = df['open'].iloc[-1] - 0.1
    return df


def build_collections(ax, data):
    """与 optimization/chart_renderer._render_candlesticks_efficient(L394-481) 一致的 8-collection 构建"""
    xvals = np.arange(len(data))
    closes = data['close'].values
    opens = data['open'].values
    highs = data['high'].values
    lows = data['low'].values
    lu = data['limit_up'].values
    ld = data['limit_down'].values
    up, down, lup, ldown = [], [], [], []
    sup, sdown, slup, sldown = [], [], [], []
    for i in range(len(data)):
        o, c, h, l = opens[i], closes[i], highs[i], lows[i]
        left, right = xvals[i] - 0.3, xvals[i] + 0.3
        if lu[i]:
            lup.append([(left, o), (left, c), (right, c), (right, o)])
            slup.append([(xvals[i], l), (xvals[i], h)])
        elif ld[i]:
            ldown.append([(left, o), (left, c), (right, c), (right, o)])
            sldown.append([(xvals[i], l), (xvals[i], h)])
        elif c >= o:
            up.append([(left, o), (left, c), (right, c), (right, o)])
            sup.append([(xvals[i], l), (xvals[i], h)])
        else:
            down.append([(left, o), (left, c), (right, c), (right, o)])
            sdown.append([(xvals[i], l), (xvals[i], h)])
    colls = []
    if up:
        colls.append(PolyCollection(up, facecolor='none', edgecolor='#ff0000', linewidth=1))
    if down:
        colls.append(PolyCollection(down, facecolor='#00ff00', edgecolor='#00ff00', linewidth=1))
    if lup:
        colls.append(PolyCollection(lup, facecolor='none', edgecolor='#FF9800', linewidth=1.4))
    if ldown:
        colls.append(PolyCollection(ldown, facecolor='none', edgecolor='#AB47BC', linewidth=1.4))
    if sup:
        colls.append(LineCollection(sup, colors='#ff0000', linewidth=1))
    if sdown:
        colls.append(LineCollection(sdown, colors='#00ff00', linewidth=1))
    if slup:
        colls.append(LineCollection(slup, colors='#FF9800', linewidth=1.4))
    if sldown:
        colls.append(LineCollection(sldown, colors='#AB47BC', linewidth=1.4))
    for c in colls:
        ax.add_collection(c)
    ax.autoscale_view()
    return colls


def make_tick_stream(base_close, n_ticks, seed=7):
    """构造 bar 内 tick 序列：围绕 base_close 小波动（ylim 稳定），保持上涨（close>=open）"""
    rng = np.random.default_rng(seed)
    return base_close + rng.normal(0, 0.05, n_ticks)


def bench_incremental(fig, ax, data, up_verts, up_segs, up_coll, up_shadow, engine):
    """路径 A：bar 内 tick → set_verts + blit（仅变化 artist）"""
    stream = make_tick_stream(data['close'].iloc[-1], N_TICKS)
    open_last = data['open'].iloc[-1]
    times = []
    for t in stream:
        c = float(t)
        h = max(open_last, c) + 0.02
        l = min(open_last, c) - 0.02
        i = N_BARS - 1
        x = i
        left, right = x - 0.3, x + 0.3
        # 更新"上涨"集合的最后一项（该 bar 保持上涨，仅 2 个 artist 受影响）
        up_verts[-1] = [(left, open_last), (left, c), (right, c), (right, open_last)]
        up_segs[-1] = [(x, l), (x, h)]
        t0 = time.perf_counter()
        up_coll.set_verts(up_verts)
        up_shadow.set_segments(up_segs)
        engine.render([up_coll, up_shadow])
        times.append(time.perf_counter() - t0)
    return times


def bench_full(fig, ax, data):
    """路径 B：全量重绘（清场 + 重建 + autoscale + draw_idle）——模拟现状每 tick 全量"""
    times = []
    stream = make_tick_stream(data['close'].iloc[-1], N_TICKS)
    open_last = data['open'].iloc[-1]
    for t in stream:
        c = float(t)
        data.iat[N_BARS - 1, data.columns.get_loc('high')] = max(open_last, c) + 0.02
        data.iat[N_BARS - 1, data.columns.get_loc('low')] = min(open_last, c) - 0.02
        data.iat[N_BARS - 1, data.columns.get_loc('close')] = c
        t0 = time.perf_counter()
        for a in list(ax.lines) + list(ax.collections) + list(ax.texts):
            a.remove()
        build_collections(ax, data)
        fig.canvas.draw_idle()
        times.append(time.perf_counter() - t0)
    return times


def main():
    data = make_kdata(N_BARS)
    results = {'incremental': [], 'full': []}

    for r in range(ROUNDS):
        # ---- 路径 A：增量 ----
        fig_a, ax_a = plt.subplots(figsize=(10, 6))
        colls_a = build_collections(ax_a, data.copy())
        # 按类型定位：第一个非空 PolyCollection = up 柱，第一个 LineCollection = up 影线
        # （末根 bar 强制属 up 集合；无涨跌停时集合顺序为 [up, down, sup, sdown]）
        up_coll = next((c for c in colls_a if isinstance(c, PolyCollection) and len(c.get_paths()) > 0), None)
        up_shadow = next((c for c in colls_a if isinstance(c, LineCollection) and len(c.get_segments()) > 0), None)
        assert up_coll is not None and up_shadow is not None, '基准前提：末根 bar 属 up 集合'
        up_verts = [p.vertices.tolist() for p in up_coll.get_paths()]
        up_segs = list(up_shadow.get_segments())
        engine_a = BlitEngine(fig_a.canvas, log_tag='[Bench]', sample_every=0)
        # 预热：首帧重建背景（不计入计时）
        t0 = time.perf_counter()
        engine_a.render([up_coll, up_shadow])
        first_ms = (time.perf_counter() - t0) * 1000
        times_a = bench_incremental(fig_a, ax_a, data, up_verts, up_segs,
                                    up_coll, up_shadow, engine_a)
        plt.close(fig_a)

        # ---- 路径 B：全量 ----
        fig_b, ax_b = plt.subplots(figsize=(10, 6))
        build_collections(ax_b, data.copy())
        times_b = bench_full(fig_b, ax_b, data.copy())
        plt.close(fig_b)

        results['incremental'].append(np.mean(times_a))
        results['full'].append(np.mean(times_b))
        print(f"  第{r + 1}轮: 增量 avg={np.mean(times_a) * 1000:.3f}ms  "
              f"全量 avg={np.mean(times_b) * 1000:.3f}ms  "
              f"(增量首帧背景重建={first_ms:.2f}ms，后续 tick 不计)")

    avg_a = np.mean(results['incremental'])
    avg_b = np.mean(results['full'])
    speedup = avg_b / avg_a
    print("\n" + "=" * 70)
    print(f"基准: {N_BARS} 根K线, 每轮 {N_TICKS} 个 bar 内 tick, 共 {ROUNDS} 轮")
    print(f"路径A 增量(blit):        avg {avg_a * 1000:.3f} ms/tick")
    print(f"路径B 全量(draw_idle):   avg {avg_b * 1000:.3f} ms/tick")
    print(f"加速比: {speedup:.1f}x")
    print("=" * 70)
    print("结论:", "增量显著更快 → 可实施 tick 增量渲染" if speedup > 3
          else "增量收益有限 → 需重新评估方案")


if __name__ == '__main__':
    main()
