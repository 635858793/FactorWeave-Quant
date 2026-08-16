#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R292 测试：K线/成交量四色配色（涨红/跌绿/涨停橙/跌停紫）

覆盖（WebGPU 假实现已按架构决策删除，渲染统一走 CPU / fallback 路径）：
- optimization/chart_renderer.py ChartRenderer._render_candlesticks_efficient 四色
  + 阳线空心/阴线实心 + 影线按类着色（K线主渲染路径）
- optimization/webgpu_chart_renderer.py WebGPUChartRenderer 降级后端到端四色
- core/webgpu/fallback.py MatplotlibRenderer 四色 + 成交量 volume_* 键

历史背景：K线四色此前只修在 optimization/chart_renderer.py（matplotlib 父类），
但运行时 _should_use_webgpu() 为 True 时真实绘制走 core/webgpu/webgpu_renderer.py
假实现（只读 up/down 两色且 CPU 降级全实心黑影线）。假实现已删除后
_should_use_webgpu() 恒为 False → 统一走父类 CPU 向量化路径，四色回归由
本文件在 CPU/fallback 路径上直接验证。
"""
import os
import sys
import numpy as np
import pandas as pd
from unittest.mock import MagicMock

import matplotlib.colors as mcolors
from matplotlib.collections import PolyCollection, LineCollection

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

STYLE = {
    'up_color': '#e74c3c', 'down_color': '#27ae60',
    'limit_up_color': '#FF9800', 'limit_down_color': '#AB47BC',
    'volume_up_color': '#e74c3c', 'volume_down_color': '#27ae60', 'alpha': 1.0,
}

# row0 阳线红 / row1 双创+20% 涨停橙（11.00×1.2=13.20）/ row2 双创-20% 跌停紫
# （13.20×0.8=10.56）/ row3 双创+20% 涨停橙（10.56×1.2=12.67）/ row4 普通阴线绿。
# R292 精确判定：symbol='300750'（创业板 20%），涨停价=round(昨收×1.2,2)，
# 收盘价等于涨停价且封板才判涨停（旧固定 4.8% 阈值测试数据已按板块规则重算）。
KLINE_DF = pd.DataFrame({
    'symbol': ['300750', '300750', '300750', '300750', '300750'],
    'open': [10.0, 11.0, 13.2, 10.56, 13.0],
    'high': [11.0, 13.2, 13.2, 12.67, 13.1],
    'low': [9.9, 11.0, 10.56, 11.5, 11.9],
    'close': [11.0, 13.2, 10.56, 12.67, 12.0],
    'volume': [1000, 1000, 1000, 1000, 1000],
})

EXPECT_COLORS = ['#e74c3c', '#ff9800', '#ab47bc', '#ff9800', '#27ae60']


def _new_chart_renderer():
    """构造 ChartRenderer（__new__ 绕过 __init__，直接验证渲染方法）"""
    from optimization.chart_renderer import ChartRenderer
    return ChartRenderer.__new__(ChartRenderer)


def _new_fallback_renderer():
    """构造 fallback MatplotlibRenderer（__new__ 绕过 __init__）"""
    from core.webgpu.fallback import MatplotlibRenderer
    fr = MatplotlibRenderer.__new__(MatplotlibRenderer)
    fr._initialized = True
    fr._update_performance_stats = lambda *a, **k: None
    fr._data_optimizer = None
    fr._volume_virtual_renderer = None
    return fr


def _patch_edge_colors(ax):
    """按 add_collection 顺序提取 PolyCollection 的 edgecolor（每路径一行展开）"""
    out = []
    for call in ax.add_collection.call_args_list:
        coll = call[0][0]
        if isinstance(coll, PolyCollection):
            colors = coll.get_edgecolor()
            n = len(coll.get_paths())
            for i in range(n):
                out.append(mcolors.to_hex(tuple(np.round(colors[i % len(colors), :3], 3))))
    return out


def _line_colors(ax):
    """按 add_collection 顺序提取 LineCollection 的 colors（按段数展开）"""
    out = []
    for call in ax.add_collection.call_args_list:
        coll = call[0][0]
        if isinstance(coll, LineCollection):
            colors = coll.get_colors()
            n = len(coll.get_segments())
            for i in range(n):
                out.append(mcolors.to_hex(tuple(np.round(colors[i % len(colors), :3], 3))))
    return out


class TestCpuCandlestickFourColor:
    """CPU 渲染路径四色（WebGPU 假实现删除后的 K 线主渲染路径）"""

    def test_cpu_path_four_colors_no_shift(self):
        """回归：每根蜡烛颜色正确、无 i//4 错位。
        分组添加顺序：up(1)/down(1)/limit_up(2)/limit_down(1)。"""
        r = _new_chart_renderer()
        ax = MagicMock()
        r._render_candlesticks_efficient(ax, KLINE_DF, STYLE, np.arange(5),
                                         use_datetime_axis=False)
        got = _patch_edge_colors(ax)
        assert got == ['#e74c3c', '#27ae60', '#ff9800', '#ff9800', '#ab47bc'], \
            f'CPU路径蜡烛颜色错位: {got}'
        assert sorted(got) == sorted(EXPECT_COLORS), f'CPU路径四色不符: {got}'

    def test_cpu_hollow_solid(self):
        """阳线空心（facecolor=none）/ 阴线实心 / 涨停跌停空心"""
        r = _new_chart_renderer()
        ax = MagicMock()
        r._render_candlesticks_efficient(ax, KLINE_DF, STYLE, np.arange(5),
                                         use_datetime_axis=False)
        hollow, solid = 0, 0
        for call in ax.add_collection.call_args_list:
            coll = call[0][0]
            if isinstance(coll, PolyCollection):
                face = coll.get_facecolor()
                if face.size == 0 or face[0][3] == 0.0:
                    hollow += 1
                else:
                    solid += 1
        assert hollow >= 3, f'涨停/跌停/阳线应空心: hollow={hollow}'
        assert solid >= 1, f'阴线应实心: solid={solid}'

    def test_cpu_shadow_colored(self):
        """影线按类着色，非全局黑/红"""
        r = _new_chart_renderer()
        ax = MagicMock()
        r._render_candlesticks_efficient(ax, KLINE_DF, STYLE, np.arange(5),
                                         use_datetime_axis=False)
        shadow = _line_colors(ax)
        assert shadow == ['#e74c3c', '#27ae60', '#ff9800', '#ff9800', '#ab47bc'], \
            f'影线颜色错位: {shadow}'
        assert all(c != '#000000' for c in shadow), f'影线不应黑色: {shadow}'

    def test_render_candlesticks_end_to_end(self):
        """端到端：WebGPUChartRenderer 降级路径（enable_webgpu=False → 父类
        CPU 向量化）render_candlesticks 每根蜡烛颜色正确、无 i//4 错位"""
        from optimization.webgpu_chart_renderer import WebGPUChartRenderer
        r = WebGPUChartRenderer(max_workers=2, enable_progressive=False, enable_webgpu=False)
        assert r._should_use_webgpu() is False
        ax = MagicMock()
        r.render_candlesticks(ax, KLINE_DF, STYLE, np.arange(5), use_datetime_axis=False)
        got = _patch_edge_colors(ax)
        assert got == ['#e74c3c', '#27ae60', '#ff9800', '#ff9800', '#ab47bc'], \
            f'端到端蜡烛颜色错位: {got}'


class TestFallbackMatplotlibFourColor:
    """fallback 链 MatplotlibRenderer 四色"""

    def test_fallback_renderer_four_colors(self):
        fr = _new_fallback_renderer()
        ax = MagicMock()
        assert fr.render_candlesticks(ax, KLINE_DF, STYLE, x=np.arange(len(KLINE_DF)),
                                      use_datetime_axis=False)
        edges = set()
        for call in ax.add_collection.call_args_list:
            coll = call[0][0]
            if isinstance(coll, PolyCollection):
                edges.add(mcolors.to_hex(coll.get_edgecolor()[0]))
        assert edges == {'#27ae60', '#ab47bc', '#e74c3c', '#ff9800'}, edges


class TestFallbackVolumeFourColor:
    """fallback 成交量四色 + volume_* 键（原 VolumeDataProcessor 用例迁移）"""

    def test_volume_four_colors(self):
        fr = _new_fallback_renderer()
        ax = MagicMock()
        assert fr.render_volume(ax, KLINE_DF, STYLE, x=np.arange(5),
                                use_datetime_axis=False)
        got = set()
        for call in ax.add_collection.call_args_list:
            coll = call[0][0]
            if isinstance(coll, PolyCollection):
                for c in coll.get_facecolor():
                    got.add(mcolors.to_hex(tuple(np.round(c[:3], 3))))
        assert got == {'#27ae60', '#ab47bc', '#e74c3c', '#ff9800'}, \
            f'成交量四色不符: {got}'

    def test_volume_uses_volume_keys(self):
        fr = _new_fallback_renderer()
        style = dict(STYLE)
        style['volume_up_color'] = '#0000ff'
        style['volume_down_color'] = '#ffff00'
        ax = MagicMock()
        assert fr.render_volume(ax, KLINE_DF, style, x=np.arange(5),
                                use_datetime_axis=False)
        got = set()
        for call in ax.add_collection.call_args_list:
            coll = call[0][0]
            if isinstance(coll, PolyCollection):
                for c in coll.get_facecolor():
                    got.add(mcolors.to_hex(tuple(np.round(c[:3], 3))))
        # row0 阳线用 volume_up_color 蓝 / row4 阴线用 volume_down_color 黄
        assert '#0000ff' in got and '#ffff00' in got, got


# R292-HV：成交量/K线颜色与 limit 列保持一致的回归数据。
# 带 limit_up/limit_down 列（上游 rendering_mixin.update_chart 在降采样前按全量
# 数据计算、iloc 切片后随行保留）。列标记刻意与内部重判结果不一致：
#   row0 普通阳线 → 列标涨停（重判为涨红，列优先应显示涨停橙）
#   row2 跌停 → 列标跌停（重判同样跌停紫，作一致性基线）
LIMIT_DF = KLINE_DF.copy()
LIMIT_DF['limit_up'] = [True, False, False, False, False]
LIMIT_DF['limit_down'] = [False, False, True, False, False]


def _volume_row_colors(ax):
    """从成交量 PolyCollection 构建 {柱中心x(取整): hex颜色} 映射（不依赖分组添加顺序）"""
    mapping = {}
    for call in ax.add_collection.call_args_list:
        coll = call[0][0]
        if not isinstance(coll, PolyCollection):
            continue
        colors = coll.get_facecolor()
        for i, path in enumerate(coll.get_paths()):
            center_x = round(float(np.mean(path.vertices[:, 0])))
            hex_c = mcolors.to_hex(tuple(np.round(colors[i % len(colors), :3], 3)))
            mapping[center_x] = hex_c
    return mapping


class TestVolumeLimitColumnPriority:
    """成交量列优先（R292-HV）：带 limit_up/limit_down 列时按列判定，
    与 K 线（_render_candlesticks_efficient）完全一致，禁止降采样后内部重判"""

    def test_cpu_volume_column_priority(self):
        """optimization 链 _render_volume_vectorized：row0 列标涨停 → 橙、row2 → 紫"""
        r = _new_chart_renderer()
        ax = MagicMock()
        r._render_volume_vectorized(ax, LIMIT_DF, STYLE, np.arange(5),
                                    use_datetime_axis=False)
        mapping = _volume_row_colors(ax)
        assert mapping.get(0.0) == '#ff9800', f'row0 应按 limit 列显示涨停橙: {mapping}'
        assert mapping.get(2.0) == '#ab47bc', f'row2 应按 limit 列显示跌停紫: {mapping}'

    def test_cpu_volume_column_missing_fallback(self):
        """无 limit 列时回退内部判定（KLINE_DF 既有场景不回归）"""
        r = _new_chart_renderer()
        ax = MagicMock()
        r._render_volume_vectorized(ax, KLINE_DF, STYLE, np.arange(5),
                                    use_datetime_axis=False)
        mapping = _volume_row_colors(ax)
        assert mapping.get(0.0) == '#e74c3c', f'row0 普通阳线应红: {mapping}'
        assert mapping.get(2.0) == '#ab47bc', f'row2 跌停应紫: {mapping}'
        assert mapping.get(4.0) == '#27ae60', f'row4 普通阴线应绿: {mapping}'

    def test_cpu_candlestick_column_priority(self):
        """对称验证：K线同样列优先（row0 列标涨停 → 橙），确保成交量与K线规则一致"""
        r = _new_chart_renderer()
        ax = MagicMock()
        r._render_candlesticks_efficient(ax, LIMIT_DF, STYLE, np.arange(5),
                                         use_datetime_axis=False)
        mapping = {}
        for call in ax.add_collection.call_args_list:
            coll = call[0][0]
            if isinstance(coll, PolyCollection):
                colors = coll.get_edgecolor()
                for i, path in enumerate(coll.get_paths()):
                    center_x = round(float(np.mean(path.vertices[:, 0])))
                    hex_c = mcolors.to_hex(tuple(np.round(colors[i % len(colors), :3], 3)))
                    mapping[center_x] = hex_c
        assert mapping.get(0.0) == '#ff9800', f'K线 row0 应按 limit 列显示涨停橙: {mapping}'
        assert mapping.get(2.0) == '#ab47bc', f'K线 row2 应按 limit 列显示跌停紫: {mapping}'

    def test_fallback_volume_column_priority(self):
        """fallback 链 render_volume 同样列优先（row0 → 橙、row2 → 紫）"""
        fr = _new_fallback_renderer()
        ax = MagicMock()
        assert fr.render_volume(ax, LIMIT_DF, STYLE, x=np.arange(5),
                                use_datetime_axis=False)
        mapping = _volume_row_colors(ax)
        assert mapping.get(0.0) == '#ff9800', f'fallback row0 应按 limit 列显示涨停橙: {mapping}'
        assert mapping.get(2.0) == '#ab47bc', f'fallback row2 应按 limit 列显示跌停紫: {mapping}'

    def test_virtual_renderer_column_priority(self):
        """volume_virtual_renderer._classify_volume_colors 列优先；无列回退重判"""
        from core.optimization.volume_virtual_renderer import VolumeVirtualRenderer
        vv = VolumeVirtualRenderer.__new__(VolumeVirtualRenderer)
        cat = vv._classify_volume_colors(LIMIT_DF)
        assert cat[0] == 2, f'row0 应为涨停橙(2): {cat}'
        assert cat[2] == 3, f'row2 应为跌停紫(3): {cat}'
        cat2 = vv._classify_volume_colors(KLINE_DF)
        assert cat2[0] == 1 and cat2[2] == 3, f'无列回退重判不符: {cat2}'
