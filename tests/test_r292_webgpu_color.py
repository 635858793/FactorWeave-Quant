#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R292 测试：WebGPU 渲染路径四色配色（涨红/跌绿/涨停橙/跌停紫）

覆盖：
- WebGPU GPU 路径 _process_candlestick_data_gpu 四色分类（用户环境 moderngl 真实路径）
- WebGPU CPU 降级 _render_cpu_fallback_candlestick 四色 + 阳线空心/阴线实心 + 影线按类着色
- fallback.py MatplotlibRenderer 四色
- WebGPU 成交量 VolumeDataProcessor 四色 + volume_up_color/volume_down_color 键

根因背景：K线四色此前只修在 optimization/chart_renderer.py（matplotlib 父类），
但运行时 _should_use_webgpu() 为 True（用户环境 moderngl），真实绘制走
core/webgpu/webgpu_renderer.py，该路径只读 up/down 两色且 CPU 降级全实心黑影线，
导致"颜色还是不对、空心柱和实心柱颜色不对"。
"""
import os
import sys
import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock

import matplotlib.colors as mcolors
from matplotlib.collections import PolyCollection, LineCollection, PatchCollection

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


def _get_webgpu_renderer():
    from optimization.webgpu_chart_renderer import get_webgpu_chart_renderer
    r = get_webgpu_chart_renderer()
    if not r._should_use_webgpu() or r._webgpu_manager is None:
        pytest.skip('WebGPU 渲染器不可用（非用户真实环境），跳过')
    return r, r._webgpu_manager._webgpu_renderer


class TestWebGpuCandlestickFourColor:
    """WebGPU GPU 路径四色分类（真实渲染路径）"""

    def test_gpu_path_four_colors(self):
        r, wr = _get_webgpu_renderer()
        vertices, colors, is_up_list, segments = wr._process_candlestick_data_gpu(KLINE_DF, STYLE)
        # colors: (n*4, 3)；每根蜡烛 4 顶点同色，取每 4 行首个
        got = [mcolors.to_hex(tuple(np.round(colors[i], 3))) for i in range(0, len(colors), 4)]
        assert got == EXPECT_COLORS, f'GPU路径四色不符: {got}'

    def test_gpu_convert_hollow_solid(self):
        r, wr = _get_webgpu_renderer()
        vertices, colors, is_up_list, segments = wr._process_candlestick_data_gpu(KLINE_DF, STYLE)
        ax = MagicMock()
        assert wr._convert_gpu_data_to_matplotlib(vertices, colors, ax, is_up_list, segments)
        assert ax.add_collection.called

    def test_gpu_convert_colors_no_shift(self):
        """回归：_convert_gpu_data_to_matplotlib 对 2D 逐顶点 colors(每蜡烛4顶点重复)
        必须按 i*4 取每根蜡烛颜色，禁止 colors_arr[i] 错位（第 i 根显示第 i//4 根颜色）。
        K线走 _render_with_gpu→_convert 路径，colors 为 (n*4,3)；成交量走批量路径为 1D。
        """
        r, wr = _get_webgpu_renderer()
        vertices, colors, is_up_list, segments = wr._process_candlestick_data_gpu(KLINE_DF, STYLE)
        ax = MagicMock()
        assert wr._convert_gpu_data_to_matplotlib(vertices, colors, ax, is_up_list, segments)

        # 从 PatchCollection 提取每根蜡烛的边框颜色（阳线空心，edgecolor=蜡烛色）
        patch_edge = None
        shadow_colors = None
        for call in ax.add_collection.call_args_list:
            coll = call[0][0]
            if isinstance(coll, PatchCollection):
                patch_edge = [mcolors.to_hex(c) for c in coll.get_edgecolor()]
            elif isinstance(coll, LineCollection):
                shadow_colors = coll.get_colors()
        assert patch_edge == EXPECT_COLORS, f'转换后蜡烛颜色错位: {patch_edge}'
        assert shadow_colors is not None, '影线 LineCollection 缺失'
        # 影线每根应着色为对应蜡烛颜色（非全局黑/红）
        shadow_hex = [mcolors.to_hex(tuple(np.round(c[:3], 3))) for c in shadow_colors]
        assert shadow_hex == EXPECT_COLORS, f'影线颜色错位: {shadow_hex}'

    def test_gpu_render_candlesticks_end_to_end(self):
        """端到端：render_candlesticks 完整链路（GPU 路径→_render_with_gpu→
        _convert_gpu_data_to_matplotlib）每根蜡烛颜色正确、无 i//4 错位"""
        r, wr = _get_webgpu_renderer()
        ax = MagicMock()
        assert wr.render_candlesticks(ax, KLINE_DF, STYLE)
        patch_edge = None
        for call in ax.add_collection.call_args_list:
            coll = call[0][0]
            if isinstance(coll, PatchCollection):
                patch_edge = [mcolors.to_hex(c) for c in coll.get_edgecolor()]
        assert patch_edge == EXPECT_COLORS, f'端到端蜡烛颜色错位: {patch_edge}'


class TestWebGpuCpuFallbackFourColor:
    """WebGPU CPU 降级路径四色 + 空心/实心 + 影线着色"""

    def test_cpu_fallback_four_color_and_styles(self):
        r, wr = _get_webgpu_renderer()
        ax = MagicMock()
        assert wr._render_cpu_fallback_candlestick(KLINE_DF, STYLE, ax)
        edge_colors, hollow, solid = set(), 0, 0
        shadow_colors = []
        for call in ax.add_collection.call_args_list:
            coll = call[0][0]
            if isinstance(coll, PolyCollection):
                edge_colors.add(mcolors.to_hex(coll.get_edgecolor()[0]))
                # facecolor='none' 时 matplotlib 返回空数组（空心）；实心则返回 (M,4)
                face = coll.get_facecolor()
                if face.size == 0 or face[0][3] == 0.0:
                    hollow += 1
                else:
                    solid += 1
            elif isinstance(coll, LineCollection):
                shadow_colors.append(mcolors.to_hex(coll.get_colors()[0]))
        assert edge_colors == {'#27ae60', '#ab47bc', '#e74c3c', '#ff9800'}, edge_colors
        assert hollow >= 3, f'涨停/跌停/阳线应空心: hollow={hollow}'
        assert solid >= 1, f'阴线应实心: solid={solid}'
        assert shadow_colors and all(c != '#000000' for c in shadow_colors), \
            f'影线不应黑色: {shadow_colors}'


class TestFallbackMatplotlibFourColor:
    """fallback 链 MatplotlibRenderer 四色"""

    def test_fallback_renderer_four_colors(self):
        from core.webgpu.fallback import MatplotlibRenderer
        fr = MatplotlibRenderer.__new__(MatplotlibRenderer)
        fr._initialized = True
        fr._update_performance_stats = lambda *a, **k: None
        ax = MagicMock()
        assert fr.render_candlesticks(ax, KLINE_DF, STYLE, x=np.arange(len(KLINE_DF)),
                                      use_datetime_axis=False)
        edges = set()
        for call in ax.add_collection.call_args_list:
            coll = call[0][0]
            if isinstance(coll, PolyCollection):
                edges.add(mcolors.to_hex(coll.get_edgecolor()[0]))
        assert edges == {'#27ae60', '#ab47bc', '#e74c3c', '#ff9800'}, edges


class TestWebGpuVolumeFourColor:
    """WebGPU 成交量四色 + volume_* 键"""

    def test_volume_four_colors(self):
        r, wr = _get_webgpu_renderer()
        vertices, colors, indices = wr.data_processor.process_volume_data(KLINE_DF, STYLE)
        colors_arr = np.asarray(colors).reshape(-1, 3)
        got = [mcolors.to_hex(tuple(np.round(c, 3))) for c in colors_arr]
        assert got == EXPECT_COLORS, f'成交量四色不符: {got}'

    def test_volume_uses_volume_keys(self):
        r, wr = _get_webgpu_renderer()
        style = dict(STYLE)
        style['volume_up_color'] = '#0000ff'
        style['volume_down_color'] = '#ffff00'
        _, colors, _ = wr.data_processor.process_volume_data(KLINE_DF, style)
        got = [mcolors.to_hex(tuple(np.round(c, 3))) for c in np.asarray(colors).reshape(-1, 3)]
        # row0 阳线用 volume_up_color 蓝 / row4 阴线用 volume_down_color 黄
        assert got[0] == '#0000ff' and got[4] == '#ffff00', got
