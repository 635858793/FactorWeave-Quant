#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R292 高价值修复测试：成交量四色渲染（涨红/跌绿/涨停橙/跌停紫）+ 虚拟滚动旧数据缓存 bug

背景（主智能体交叉验证）：
1. fallback.py MatplotlibRenderer.render_volume 常规路径只取单色 color（L433），
   未用 up_color/down_color/limit_up_color/limit_down_color，也未调用
   classify_limit_up_down —— 降级到 FallbackRenderer 时 K 线四色但成交量单色。
2. volume_virtual_renderer.py 三条渲染子路径（_render_volume_regular /
   _render_volume_virtual / _render_chunk）全程单色，且 _get_chunk_data 切片的
   chunk_data 只有 volume 列，无 open/close/limit 信息 → 四色无数据来源。
3. fallback.py L404 `if volume_data is None` 只首次设置数据源 → 切周期/刷行情后
   成交量虚拟滚动仍渲染缓存的旧数据。

覆盖：
① fallback render_volume 四色（构造含涨停/跌停/涨/跌的成交量数据，断言面片颜色 4 色分布）
② volume_virtual_renderer _render_chunk / _render_volume_regular 四色
③ fallback 虚拟滚动旧数据 bug（连续两次 set 不同数据，第二次渲染必须用新数据）
④ 无 open/close 列时降级不抛异常（fallback 常规路径 + _render_chunk）
"""
import os
import sys
import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.collections import PolyCollection

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# 与 K 线四色同款 style（test_r292_webgpu_color.py 同源）
STYLE = {
    'up_color': '#e74c3c', 'down_color': '#27ae60',
    'limit_up_color': '#FF9800', 'limit_down_color': '#AB47BC',
    'volume_up_color': '#e74c3c', 'volume_down_color': '#27ae60', 'alpha': 1.0,
}

# row0 阳线红 / row1 双创+20% 涨停橙（11.00×1.2=13.20）/ row2 双创-20% 跌停紫
# （13.20×0.8=10.56）/ row3 双创+20% 涨停橙（10.56×1.2=12.67）/ row4 普通阴线绿
KLINE_DF = pd.DataFrame({
    'symbol': ['300750', '300750', '300750', '300750', '300750'],
    'open': [10.0, 11.0, 13.2, 10.56, 13.0],
    'high': [11.0, 13.2, 13.2, 12.67, 13.1],
    'low': [9.9, 11.0, 10.56, 11.5, 11.9],
    'close': [11.0, 13.2, 10.56, 12.67, 12.0],
    'volume': [1000, 1000, 1000, 1000, 1000],
})

EXPECT_COLORS = ['#e74c3c', '#ff9800', '#ab47bc', '#ff9800', '#27ae60']


def _make_vr(chunk_size=2000):
    """构造 VolumeVirtualRenderer 实例。

    注意：VolumeVirtualRenderer 继承 QObject（BaseVirtualRenderer），PyQt5 对
    绕过 __init__ 的 QObject 子类调用实例方法会抛 RuntimeError，故必须真实构造。
    """
    from core.optimization.volume_virtual_renderer import VolumeVirtualRenderer
    from core.advanced_optimization.performance.virtualization import VirtualizationConfig

    config = VirtualizationConfig(
        chunk_size=chunk_size, overlap_size=100, max_visible_chunks=3,
        quality_levels=[1, 2, 4, 8], cache_size=10)
    return VolumeVirtualRenderer(config)


def _make_fr(vr=None):
    """构造 fallback MatplotlibRenderer 手动实例（__new__ 绕过虚拟滚动器真实初始化）"""
    from core.webgpu.fallback import MatplotlibRenderer

    fr = MatplotlibRenderer.__new__(MatplotlibRenderer)
    fr._initialized = True
    fr._update_performance_stats = lambda *a, **k: None
    fr._data_optimizer = None
    fr._volume_virtual_renderer = vr if vr is not None else MagicMock()
    return fr


def _face_colors(coll):
    """提取 PolyCollection 面片颜色 hex 列表"""
    return [mcolors.to_hex(c) for c in coll.get_facecolor()]


class TestFallbackVolumeFourColor:
    """① fallback render_volume 常规路径四色 + 无 OHLC 降级"""

    def test_fallback_volume_four_colors(self):
        """涨停橙/跌停紫/涨红/跌绿 4 色分布，与 K 线判定一致"""
        fr = _make_fr()
        fr._volume_virtual_renderer.is_enabled = False  # 强制走常规渲染路径
        ax = MagicMock()
        assert fr.render_volume(ax, KLINE_DF, STYLE, x=np.arange(len(KLINE_DF)),
                                use_datetime_axis=False) is True

        coll = ax.add_collection.call_args[0][0]
        assert isinstance(coll, PolyCollection), type(coll)
        assert _face_colors(coll) == EXPECT_COLORS, _face_colors(coll)

    def test_fallback_volume_missing_ohlc_fallback(self):
        """④ 数据无 open/close 列：降级渲染不抛异常"""
        fr = _make_fr()
        fr._volume_virtual_renderer.is_enabled = False
        ax = MagicMock()
        df = pd.DataFrame({'volume': [100.0, 200.0, 300.0]})
        assert fr.render_volume(ax, df, {}, use_datetime_axis=False) is True


class TestVolumeVirtualFourColor:
    """② volume_virtual_renderer 子路径四色 + 无 OHLC 降级"""

    def test_render_chunk_four_colors(self):
        """_render_chunk：chunk 带 open/close/high/low → 四色分类"""
        vr = _make_vr()
        for key, value in STYLE.items():
            if hasattr(vr.style, key):
                setattr(vr.style, key, value)
        ax = MagicMock()
        assert vr._render_chunk(ax, KLINE_DF.copy(), vr.style, chunk_id=0,
                                use_datetime_axis=False) is True
        coll = ax.add_collection.call_args[0][0]
        assert isinstance(coll, PolyCollection), type(coll)
        assert _face_colors(coll) == EXPECT_COLORS, _face_colors(coll)

    def test_render_volume_regular_four_colors(self):
        """_render_volume_regular（虚拟滚动降级方案）：数据含 OHLC → 四色"""
        vr = _make_vr()
        ax = MagicMock()
        assert vr._render_volume_regular(ax, KLINE_DF, STYLE,
                                         x=np.arange(len(KLINE_DF)),
                                         use_datetime_axis=False) is True
        coll = ax.add_collection.call_args[0][0]
        assert isinstance(coll, PolyCollection), type(coll)
        assert _face_colors(coll) == EXPECT_COLORS, _face_colors(coll)

    def test_render_chunk_missing_ohlc_fallback(self):
        """④ _render_chunk：DataFrame 无 open/close、以及 ndarray 输入 → 降级不抛异常"""
        vr = _make_vr()
        ax = MagicMock()
        df = pd.DataFrame({'volume': [100.0, 200.0, 0.0, 300.0]})
        assert vr._render_chunk(ax, df, vr.style, chunk_id=0,
                                use_datetime_axis=False) is True
        assert vr._render_chunk(ax, np.array([100.0, 200.0, 300.0]), vr.style,
                                chunk_id=1, use_datetime_axis=False) is True

    def test_get_chunk_data_keeps_ohlc_columns(self):
        """_get_chunk_data：切片保留 open/close 等列（四色数据源）"""
        vr = _make_vr(chunk_size=3)
        vr.set_volume_data(KLINE_DF, MagicMock())
        chunk = vr._get_chunk_data(0)
        assert chunk is not None
        assert 'volume' in chunk.columns
        assert 'open' in chunk.columns and 'close' in chunk.columns
        assert list(chunk['close']) == [11.0, 13.2, 10.56]


class TestFallbackVirtualScrollDataRefresh:
    """③ fallback 虚拟滚动旧数据缓存 bug（切周期/刷行情后必须渲染新数据）"""

    def test_second_render_uses_new_data(self):
        """连续两次 set 不同数据：第二次渲染柱子高度必须来自新数据"""
        fr = _make_fr(_make_vr(chunk_size=5))
        fig, ax = plt.subplots()

        old = pd.DataFrame({
            'open': [10.0] * 12, 'high': [11.0] * 12, 'low': [9.0] * 12,
            'close': [10.5] * 12, 'volume': [9000.0] * 12,
        })
        new = pd.DataFrame({
            'open': [10.0] * 12, 'high': [11.0] * 12, 'low': [9.0] * 12,
            'close': [10.5] * 12, 'volume': [100.0] * 12,
        })

        assert fr.render_volume(ax, old, {}, use_datetime_axis=False) is True
        ax.clear()
        assert fr.render_volume(ax, new, {}, use_datetime_axis=False) is True

        ys = []
        for coll in ax.collections:
            if isinstance(coll, PolyCollection):
                for path in coll.get_paths():
                    ys.extend(path.vertices[:, 1])
        assert len(ys) > 0, '第二次渲染未产生成交量柱子'
        # 修复前：volume_data 停留在旧数据 → 柱子高度为 9000
        assert max(ys) <= 200, f'第二次渲染仍使用旧数据，柱子最高 {max(ys)}'
        assert abs(max(ys) - 100.0) < 1e-6, f'第二次渲染柱子高度异常: {max(ys)}'

        plt.close(fig)
