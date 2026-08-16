#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HV6 测试：tick 级别增量渲染（R292-HV6）

背景：统一 blit 方案（HV5）就绪后，为 K 线主图实现 tick 增量渲染——
只在数据变化时更新对应 artist（set_verts + BlitEngine.render），避免每个
tick 触发全量重绘（清场循环 + draw_idle，基准 41.7ms vs 增量 9.2ms，4.6x）。

覆盖：
1. 真实渲染链返回 collections 引用（K线 8 元组 / 成交量 4 元组），
   引用真实存在于 ax（renderer 不再"画完即丢"）
2. WebGPUChartRenderer 透传返回（真实激活链 rendering_mixin → WebGPU → ChartRenderer）
3. update_chart 保存 _kline_collections / _volume_collections（增量更新的基础）
4. tick 增量更新（bar 内）：symbol 过滤 / 末根 OHLCV 更新 / 不触发 draw_idle
   / ylim 突破 invalidate / 阳线↔阴线类别迁移
5. 新 bar（跨周期）：追加 + 走全量重绘（x轴/指标/xticks 需整体刷新）
6. 残留旧 blit 闭环：gui/widgets 生产代码无自建 copy_from_bbox/blit 直接调用
   （统一收敛到 core/utils/mpl_blit.py，铁律㊲）
"""
import os
import sys
import importlib.util

import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# 与 test_r267_kline_shrink_fix 同款 dummy 模块注册（conftest 已把 gui.widgets.* mock 化）
from unittest.mock import MagicMock as _MagicMock  # noqa: E402
_dummy_pkg = _MagicMock()
_dummy_pkg.__name__ = 'gui.widgets.chart_mixins'
_dummy_pkg.__file__ = '<mock:gui.widgets.chart_mixins>'
_dummy_ui = _MagicMock()
_dummy_ui.__name__ = 'gui.widgets.chart_mixins.ui_mixin'
_dummy_ui.__file__ = '<mock:gui.widgets.chart_mixins.ui_mixin>'
sys.modules.setdefault('gui.widgets.chart_mixins', _dummy_pkg)
sys.modules.setdefault('gui.widgets.chart_mixins.ui_mixin', _dummy_ui)

import matplotlib
matplotlib.use('Agg')  # 无头渲染
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection, LineCollection

CHART_MIXINS = os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins')


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(CHART_MIXINS, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


render_mod = _load_module('rendering_mixin_mod2', 'rendering_mixin.py')
cross_mod = _load_module('crosshair_mixin_mod2', 'crosshair_mixin.py')

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
    # 末根强制阳线（增量测试确定性）
    df.iat[n - 1, df.columns.get_loc('close')] = df['open'].iloc[-1] + 0.5
    df.iat[n - 1, df.columns.get_loc('high')] = df['open'].iloc[-1] + 0.6
    df.iat[n - 1, df.columns.get_loc('low')] = df['open'].iloc[-1] - 0.1
    return df


def make_kdata_up_only_last(n):
    """极端波动边界：前 n-1 根全阴线（open>close）、末根唯一阳线——
    up 类别只含末根 1 根（overlay 拆分"类别单根"边界场景，如连续下跌后拉红）"""
    closes = np.linspace(100.0, 95.0, n)          # 单调下行
    opens = closes + 1.0                          # 阴线（open > close）
    df = pd.DataFrame({
        'symbol': '300994',
        'open': opens, 'high': closes + 1.2, 'low': closes - 0.2,
        'close': closes,
        'volume': np.arange(n, dtype=float) * 100 + 1000,
        'datetime': pd.date_range('2024-01-01 09:30', periods=n, freq='1min'),
    })
    df['limit_up'] = False
    df['limit_down'] = False
    # 末根改唯一阳线（up 类别只含末根）
    df.iat[n - 1, df.columns.get_loc('open')] = 95.0
    df.iat[n - 1, df.columns.get_loc('close')] = 95.8
    df.iat[n - 1, df.columns.get_loc('high')] = 96.2
    df.iat[n - 1, df.columns.get_loc('low')] = 94.8
    return df


# ============================================================
# 1. 渲染链返回 collections 引用
# ============================================================
class TestRendererReturnsCollections:

    def _new_renderer(self):
        from optimization.chart_renderer import ChartRenderer
        r = ChartRenderer.__new__(ChartRenderer)
        r.render_error = MagicMock()
        r._update_throttler = None
        return r

    def test_candlesticks_returns_8tuple(self):
        from optimization.chart_renderer import ChartRenderer
        r = self._new_renderer()
        fig, ax = plt.subplots(figsize=(8, 4))
        data = make_kdata(200)
        result = r._render_candlesticks_efficient(
            ax, data, {}, x=np.arange(len(data)), use_datetime_axis=False)
        plt.close(fig)
        assert isinstance(result, tuple) and len(result) == 8, \
            f"应返回 8 元组（8 个集合），实际 {type(result)} len={len(result) if result else 0}"
        # 非 None 元素必须是真实存在于 ax.collections 的 artist
        added = set(map(id, ax.collections))
        for i, coll in enumerate(result):
            if coll is not None:
                assert id(coll) in added, f"第{i}个集合({KLINE_KEYS[i]})应真实存在于 ax.collections"
                assert isinstance(coll, (PolyCollection, LineCollection))

    def test_volume_returns_4tuple(self):
        from optimization.chart_renderer import ChartRenderer
        r = self._new_renderer()
        fig, ax = plt.subplots(figsize=(8, 4))
        data = make_kdata(200)
        result = r._render_volume_vectorized(
            ax, data, {}, x=np.arange(len(data)), use_datetime_axis=False)
        plt.close(fig)
        assert isinstance(result, tuple) and len(result) == 4
        added = set(map(id, ax.collections))
        for i, coll in enumerate(result):
            if coll is not None:
                assert id(coll) in added
                assert isinstance(coll, PolyCollection)

    def test_public_render_candlesticks_passthrough(self):
        from optimization.chart_renderer import ChartRenderer
        r = self._new_renderer()
        r._get_view_data = lambda d: d
        r._downsample_data = lambda d: d
        r._optimize_display = lambda ax: None
        fig, ax = plt.subplots(figsize=(8, 4))
        data = make_kdata(50)
        result = r.render_candlesticks(
            ax, data, {}, x=np.arange(len(data)), use_datetime_axis=False)
        plt.close(fig)
        assert isinstance(result, tuple) and len(result) == 8

    def test_public_render_volume_passthrough(self):
        from optimization.chart_renderer import ChartRenderer
        r = self._new_renderer()
        r._get_view_data = lambda d: d
        r._downsample_data = lambda d: d
        r._optimize_display = lambda ax: None
        fig, ax = plt.subplots(figsize=(8, 4))
        data = make_kdata(50)
        result = r.render_volume(
            ax, data, {}, x=np.arange(len(data)), use_datetime_axis=False)
        plt.close(fig)
        assert isinstance(result, tuple) and len(result) == 4

    def test_webgpu_renderer_passthrough(self):
        """真实激活链：rendering_mixin → WebGPUChartRenderer → ChartRenderer 透传返回"""
        from optimization.webgpu_chart_renderer import WebGPUChartRenderer
        from optimization.chart_renderer import ChartRenderer
        r = WebGPUChartRenderer.__new__(WebGPUChartRenderer)
        ChartRenderer.__init__  # noqa: 占位，_should_use_webgpu 由子类控制
        r._should_use_webgpu = lambda: False
        r._get_view_data = lambda d: d
        r._downsample_data = lambda d: d
        r._optimize_display = lambda ax: None
        r.render_error = MagicMock()
        fig, ax = plt.subplots(figsize=(8, 4))
        data = make_kdata(50)
        result = r.render_candlesticks(
            ax, data, {}, x=np.arange(len(data)), use_datetime_axis=False)
        plt.close(fig)
        assert isinstance(result, tuple) and len(result) == 8


# ============================================================
# 2. update_chart 保存 collections 引用 + tick 增量更新
# ============================================================
class _ChartWidget(render_mod.RenderingMixin):
    """组合 mixin（__new__ 绕过 __init__ + mock 渲染依赖）"""


def _make_widget():
    w = _ChartWidget.__new__(_ChartWidget)
    w.current_kdata = None
    w._full_kdata = None
    w._kline_collections = None
    w._volume_collections = None
    w._ymin = 0.0
    w._ymax = 1.0
    w.chart_type = 'K线图'
    w.current_period = '1min'
    w.current_stock = '300994'
    w.price_ax = MagicMock()
    w.volume_ax = MagicMock()
    w.indicator_ax = MagicMock()
    w.renderer = MagicMock()
    w.theme_manager = MagicMock()
    w.theme_manager.get_theme_colors.return_value = {
        'chart_text': '#222b45', 'chart_background': '#ffffff'}
    w.active_indicators = []
    w.error_occurred = MagicMock()
    w.canvas = MagicMock()
    w.canvas.figure = MagicMock()
    w._render_indicators = MagicMock()
    w._optimize_display = MagicMock()
    w.close_loading_dialog = MagicMock()
    w._invalidate_crosshair_background = MagicMock()
    w.show_no_data = MagicMock()
    w._safe_format_date = MagicMock(return_value='2024-01-01')
    w._get_chart_style = MagicMock(return_value={})
    w._downsample_kdata = MagicMock(side_effect=lambda d: d)
    w._compute_intraday_series = MagicMock()
    w.plot_patterns = MagicMock()
    w.draw_pattern_signals = MagicMock()
    w._sync_region_indicator_btn_pos = MagicMock()
    w._get_active_indicators = MagicMock(return_value=[])
    return w


def _make_engine_mock(w):
    """挂一个可断言的 BlitEngine 替身（记录 render 调用 + 默认背景已缓存）"""
    engine = MagicMock()
    engine.background_cached = True
    engine.render.return_value = True
    w._blit_engine = engine
    return engine


class TestRealtimeTickIncremental:

    def _setup_widget_with_collections(self, n=200, data=None):
        """update_chart 已保存集合引用的前置状态（真实渲染器构建真实 collections）"""
        from optimization.chart_renderer import ChartRenderer
        r = ChartRenderer.__new__(ChartRenderer)
        r.render_error = MagicMock()
        w = _make_widget()
        w.renderer = r  # 真实渲染器（增量重建 verts 依赖 renderer 的辅助函数）
        data = make_kdata(n) if data is None else data
        n = len(data)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
        kc = r._render_candlesticks_efficient(
            ax1, data, {}, x=np.arange(n), use_datetime_axis=False)
        vc = r._render_volume_vectorized(
            ax2, data, {}, x=np.arange(n), use_datetime_axis=False)
        w.price_ax = ax1
        w.volume_ax = ax2
        w._kline_collections = {k: v for k, v in zip(KLINE_KEYS, kc)}
        w._volume_collections = {k: v for k, v in zip(VOLUME_KEYS, vc)}
        w.current_kdata = data.copy()
        w._full_kdata = data.copy()
        w._ymin = float(data['low'].min())
        w._ymax = float(data['high'].max())
        w._fig = fig
        return w, fig

    # ---- symbol 过滤 ----
    def test_tick_symbol_mismatch_ignored(self):
        w, fig = self._setup_widget_with_collections()
        _make_engine_mock(w)
        before = w.current_kdata['close'].iloc[-1]
        w._handle_realtime_tick({
            'symbol': '600000', 'price': 999.0, 'volume': 10,
            'timestamp': '2024-01-01 09:31:00'})
        assert w.current_kdata['close'].iloc[-1] == before, "symbol 不匹配不应更新末根 bar"
        w.canvas.draw_idle.assert_not_called()
        plt.close(fig)

    # ---- bar 内更新 ----
    def test_tick_bar_within_updates_last_bar(self):
        w, fig = self._setup_widget_with_collections()
        engine = _make_engine_mock(w)
        last_open = w.current_kdata['open'].iloc[-1]
        w._handle_realtime_tick({
            'symbol': '300994', 'price': last_open + 0.8, 'volume': 500,
            'timestamp': '2024-01-01 09:31:00'})
        last = w.current_kdata.iloc[-1]
        assert last['close'] == pytest.approx(last_open + 0.8), "末根 close 应更新为 tick 价"
        assert last['volume'] > 0, "成交量应累加"
        # 增量路径：不触发全画布重绘
        w.canvas.draw_idle.assert_not_called()
        # 且同步了 _full_kdata（一致性）
        assert w._full_kdata['close'].iloc[-1] == pytest.approx(last_open + 0.8)
        plt.close(fig)

    def test_tick_high_low_track(self):
        w, fig = self._setup_widget_with_collections()
        _make_engine_mock(w)
        before_high = w.current_kdata['high'].iloc[-1]
        before_low = w.current_kdata['low'].iloc[-1]
        # tick 价低于 open → close 走低，high/low 扩展
        last_open = w.current_kdata['open'].iloc[-1]
        w._handle_realtime_tick({
            'symbol': '300994', 'price': last_open - 0.5, 'volume': 100,
            'timestamp': '2024-01-01 09:31:00'})
        last = w.current_kdata.iloc[-1]
        assert last['low'] < before_low, "low 应随 tick 扩展"
        assert last['high'] >= before_high, "high 不应缩小"
        plt.close(fig)

    # ---- ylim 突破 → invalidate ----
    def test_tick_ylim_break_invalidates(self):
        w, fig = self._setup_widget_with_collections()
        _make_engine_mock(w)
        w._invalidate_crosshair_background = MagicMock()
        # 大幅突破 ymax 的 tick
        w._handle_realtime_tick({
            'symbol': '300994', 'price': w._ymax * 2, 'volume': 100,
            'timestamp': '2024-01-01 09:31:00'})
        w._invalidate_crosshair_background.assert_called_once(), \
            "ylim 突破必须 invalidate（背景重建），否则 restore 错位背景"
        plt.close(fig)

    # ---- 类别迁移：阳线 → 阴线 ----
    def test_tick_class_change_migrates_collection(self):
        w, fig = self._setup_widget_with_collections()
        engine = _make_engine_mock(w)
        last_open = w.current_kdata['open'].iloc[-1]
        # 末根原为阳线；tick 打到 open 之下 → 应迁移到 down overlay
        w._handle_realtime_tick({
            'symbol': '300994', 'price': last_open - 1.0, 'volume': 100,
            'timestamp': '2024-01-01 09:31:00'})
        # HV6.2：首 tick 完成 overlay 惰性初始化，末根只存在于 overlay
        assert getattr(w, '_kline_overlay', None), "首 tick 应完成 overlay 惰性初始化"
        # overlay down 应包含末根顶点（y 值 ~ open-1.0，仅 1 根）
        down_ov = w._kline_overlay['down']
        assert down_ov is not None
        paths = down_ov.get_paths()
        assert len(paths) == 1, f"overlay down 应只含末根 1 根，实际 {len(paths)}"
        assert paths[0].vertices[:, 1].max() <= last_open + 1e-9, \
            "迁移后末根 bar 顶点应落在 overlay down（close < open）"
        # overlay up 应为空（末根已迁移出阳线类别，无旧残影）
        up_ov = w._kline_overlay['up']
        assert up_ov is None or len(up_ov.get_paths()) == 0, \
            "overlay up 不应含旧阳线末根"
        # 主体 up/down 集合不含末根（前 n-1 根），末根 x 位置无主体顶点
        i = len(w.current_kdata) - 1
        for key in ('up', 'down'):
            main = w._kline_collections[key]
            if main is not None and len(main.get_paths()) > 0:
                max_x = main.get_paths()[-1].vertices[:, 0].max()
                assert max_x < i - 0.3 + 1e-9, \
                    f"主体 {key} 集合不应含末根（x={i}）顶点，实际最大 x={max_x:.2f}"
        plt.close(fig)

    # ---- HV6.2 回归：末根 overlay 拆分（主体=前n-1根，overlay=末根） ----
    def test_setup_overlay_splits_last_bar(self):
        """_setup_tick_overlay：主体集合减去末根（8 K线 + 4 成交量），
        overlay 仅含末根 1 根 bar，且 add 到对应 ax"""
        w, fig = self._setup_widget_with_collections(n=50)
        # 拆分前主体 up 顶点数（末根为阳线 → 必含末根）
        before_up = len(w._kline_collections['up'].get_paths())
        assert before_up > 0, "前置：主体 up 集合应含末根"
        assert w._setup_tick_overlay()
        assert getattr(w, '_kline_overlay', None)
        assert getattr(w, '_volume_overlay', None)
        i = len(w.current_kdata) - 1
        # 拆分后主体 up = 前 - 1（末根被拆出到 overlay）
        after_up = len(w._kline_collections['up'].get_paths())
        assert after_up == before_up - 1, \
            f"主体 up 应减少 1 根（{before_up} → {after_up}）"
        # overlay up 只含末根 1 根，x 边界位于末根位置（i ± 0.3）
        up_ov = w._kline_overlay['up']
        assert up_ov is not None and len(up_ov.get_paths()) == 1, \
            "overlay up 应只含末根 1 根"
        xs = up_ov.get_paths()[0].vertices[:, 0]
        assert np.allclose(xs.min(), i - 0.3) and np.allclose(xs.max(), i + 0.3), \
            f"overlay 末根 x 边界应在 [{i-0.3}, {i+0.3}]，实际 [{xs.min()}, {xs.max()}]"
        # overlay 集合真实挂到 ax（绘制顺序在后 → 覆盖主体）
        assert up_ov in w.price_ax.collections, "overlay 应 add 到 price_ax"
        assert w._volume_overlay['up'] in w.volume_ax.collections, \
            "成交量 overlay 应 add 到 volume_ax"
        plt.close(fig)

    def test_setup_overlay_clears_body_single_bar_category(self):
        """极端波动边界：up 类别只含末根 1 根（前 n-1 根全阴线）——
        拆分后主体 up 必须清空（set_verts 空），否则主体残留末根：
        tick 迁移类别时主体不在 blit 范围 → 旧末根永久残影"""
        data = make_kdata_up_only_last(2)
        w, fig = self._setup_widget_with_collections(data=data)
        assert len(w._kline_collections['up'].get_paths()) == 1, "前置：up 只含末根"
        assert w._setup_tick_overlay()
        # 主体 up 应被清空（末根已拆到 overlay，不残留）
        assert len(w._kline_collections['up'].get_paths()) == 0, \
            "主体 up 必须清空：类别单根（仅末根）时 set_verts 空数组"
        # overlay up 含末根 1 根；主体 down 保留首根、overlay down 空
        assert len(w._kline_overlay['up'].get_paths()) == 1, "overlay up 含末根"
        assert len(w._kline_collections['down'].get_paths()) == 1, "主体 down 保留首根"
        assert len(w._kline_overlay['down'].get_paths()) == 0, "overlay down 空"
        plt.close(fig)

    def test_tick_migrate_single_bar_category_no_ghost(self):
        """极端波动边界：up 类别只含末根，tick 打到 open 之下迁移到 down——
        主体 up 无旧末根残影（主体不在 blit 范围，残影不可清除），
        overlay down 含新末根 1 根"""
        data = make_kdata_up_only_last(2)
        w, fig = self._setup_widget_with_collections(data=data)
        _make_engine_mock(w)
        last_open = float(w.current_kdata['open'].iloc[-1])  # 95.0
        w._handle_realtime_tick({
            'symbol': '300994', 'price': last_open - 1.0, 'volume': 100,
            'timestamp': '2024-01-01 09:31:00'})
        # 末根 close=94.0 < open=95.0 → down；主体 up 必须无残留
        assert len(w._kline_collections['up'].get_paths()) == 0, \
            "迁移后主体 up 无旧末根残影（类别单根边界）"
        assert len(w._kline_overlay['down'].get_paths()) == 1, \
            "overlay down 含新末根 1 根"
        assert len(w._kline_overlay['up'].get_paths()) == 0, \
            "overlay up 已清空（末根迁移出阳线类别）"
        plt.close(fig)

    def test_tick_body_collections_unchanged(self):
        """HV6.2：多次 tick 后主体集合 verts 不变（tick 只重建 overlay），
        验证无意外全量重建——主体是 5 万行视图下 draw_artist 15ms 的根因"""
        w, fig = self._setup_widget_with_collections()
        last_open = w.current_kdata['open'].iloc[-1]
        w._handle_realtime_tick({
            'symbol': '300994', 'price': last_open + 0.8, 'volume': 100,
            'timestamp': '2024-01-01 09:31:00'})  # 首 tick：惰性 setup + overlay 重建
        # 记录主体集合 verts 快照（tick 后主体应为前 n-1 根，不再变化）
        snaps = {}
        for key, coll in w._kline_collections.items():
            if coll is not None:
                snaps[key] = np.array([p.vertices for p in coll.get_paths()])
        vol_snaps = {}
        for key, coll in w._volume_collections.items():
            if coll is not None:
                vol_snaps[key] = np.array([p.vertices for p in coll.get_paths()])
        # 第二次 tick（同类别，close 继续走高）
        p2 = last_open + 0.9
        w._handle_realtime_tick({
            'symbol': '300994', 'price': p2, 'volume': 200,
            'timestamp': '2024-01-01 09:31:00'})
        # 主体集合 verts 完全不变
        for key, snap in snaps.items():
            cur = np.array([p.vertices for p in w._kline_collections[key].get_paths()])
            assert np.array_equal(cur, snap), f"主体 {key} 集合不应被 tick 重建"
        for key, snap in vol_snaps.items():
            cur = np.array([p.vertices for p in w._volume_collections[key].get_paths()])
            assert np.array_equal(cur, snap), f"成交量主体 {key} 集合不应被 tick 重建"
        # overlay 更新为新 close
        up_ov = w._kline_overlay['up']
        assert up_ov is not None
        assert up_ov.get_paths()[0].vertices[:, 1].max() == pytest.approx(p2), \
            "overlay up 应更新为最新 tick close"
        plt.close(fig)

    # ---- HV6.1 回归：视图(降采样)≠全量时末行同步（索引错位修复） ----
    def test_tick_view_last_bar_syncs_full(self):
        """视图≠全量时：tick 后视图末行=全量末行（旧代码 frame.iat[i] 用视图索引
        更新全量第 i 行，导致全量末行永不刷新、下次全量刷新数据回退）"""
        from optimization.chart_renderer import ChartRenderer
        r = ChartRenderer.__new__(ChartRenderer)
        r.render_error = MagicMock()
        w = _make_widget()
        w.renderer = r
        full = make_kdata(500)
        # 视图 = 每 5 根取 1 + 强制末行（模拟降采样：视图末行=全量末行，但长度不同）
        idx = np.unique(np.concatenate([np.arange(0, 500, 5), [499]]))
        view = full.iloc[idx].reset_index(drop=True)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
        kc = r._render_candlesticks_efficient(
            ax1, view, {}, x=np.arange(len(view)), use_datetime_axis=False)
        vc = r._render_volume_vectorized(
            ax2, view, {}, x=np.arange(len(view)), use_datetime_axis=False)
        w.price_ax = ax1
        w.volume_ax = ax2
        w._kline_collections = {k: v for k, v in zip(KLINE_KEYS, kc)}
        w._volume_collections = {k: v for k, v in zip(VOLUME_KEYS, vc)}
        w.current_kdata = view.copy()
        w._full_kdata = full.copy()
        w._ymin = float(view['low'].min())
        w._ymax = float(view['high'].max())
        _make_engine_mock(w)
        assert len(w.current_kdata) < len(w._full_kdata), "前置：视图应小于全量"
        assert (w.current_kdata['datetime'].iloc[-1]
                == w._full_kdata['datetime'].iloc[-1]), "前置：视图末行=全量末行"
        last_open = w.current_kdata['open'].iloc[-1]
        tick_price = last_open + 0.8
        w._handle_realtime_tick({
            'symbol': '300994', 'price': tick_price, 'volume': 300,
            'timestamp': str(w.current_kdata['datetime'].iloc[-1])})
        assert w.current_kdata['close'].iloc[-1] == pytest.approx(tick_price), \
            "视图末行应更新为 tick 价"
        assert w._full_kdata['close'].iloc[-1] == pytest.approx(tick_price), \
            "HV6 索引错位修复：全量末行必须随视图末行同步更新"
        i_view = len(w.current_kdata) - 1
        assert w._full_kdata['close'].iloc[i_view] != pytest.approx(tick_price), \
            "旧错位位置（全量第 i 行，i=视图末位置）不应被错误更新"
        plt.close(fig)

    # ---- HV6.1/HV6.2 回归：blit 范围缩小（HV6.2 后 draw 对象为末根 overlay） ----
    def _artist_keys(self, w, artists):
        """把 render 收到的 artist 列表映射回 (K/V):key 标识（主体/overlay 均识别）"""
        kline = {id(v): k for k, v in w._kline_collections.items() if v is not None}
        vol = {id(v): k for k, v in w._volume_collections.items() if v is not None}
        if getattr(w, '_kline_overlay', None):
            kline.update({id(v): 'ov:' + k for k, v in w._kline_overlay.items()
                          if v is not None})
        if getattr(w, '_volume_overlay', None):
            vol.update({id(v): 'ov:' + k for k, v in w._volume_overlay.items()
                        if v is not None})
        keys = set()
        for a in artists:
            if id(a) in kline:
                keys.add('K:' + kline[id(a)])
            elif id(a) in vol:
                keys.add('V:' + vol[id(a)])
        return keys

    def test_tick_blit_artists_limited_to_lastbar_sets(self):
        """blit 范围缩小：末根为阳线时只重画 up/shadow_up + vol up overlay，
        不重画 down 等无关集合（HV6.2 后 draw 的是单根 overlay，光栅化 <1ms）"""
        w, fig = self._setup_widget_with_collections()
        engine = _make_engine_mock(w)
        last_open = w.current_kdata['open'].iloc[-1]
        w._handle_realtime_tick({
            'symbol': '300994', 'price': last_open + 0.8, 'volume': 100,
            'timestamp': '2024-01-01 09:31:00'})
        assert engine.render.called, "增量路径应走 BlitEngine.render"
        assert getattr(w, '_kline_overlay', None), "首 tick 应完成 overlay 惰性初始化"
        artists = engine.render.call_args[0][0]
        keys = self._artist_keys(w, artists)
        assert keys == {'K:ov:up', 'K:ov:shadow_up', 'V:ov:up'}, \
            f"blit 应只含末根相关 overlay 集合，实际: {keys}"
        plt.close(fig)

    def test_tick_blit_artists_include_migrated_old_sets(self):
        """类别迁移（阳线→阴线）：blit 范围必须含新旧两组 overlay 集合，
        否则旧类别残影残留背景快照"""
        w, fig = self._setup_widget_with_collections()
        engine = _make_engine_mock(w)
        last_open = w.current_kdata['open'].iloc[-1]
        w._handle_realtime_tick({
            'symbol': '300994', 'price': last_open - 1.0, 'volume': 100,
            'timestamp': '2024-01-01 09:31:00'})
        assert engine.render.called
        artists = engine.render.call_args[0][0]
        keys = self._artist_keys(w, artists)
        assert keys == {'K:ov:up', 'K:ov:shadow_up', 'K:ov:down', 'K:ov:shadow_down',
                        'V:ov:up', 'V:ov:down'}, \
            f"迁移时 blit 应含新旧两组 overlay 集合，实际: {keys}"
        plt.close(fig)

    # ---- 新 bar（跨周期）→ 全量重绘 ----
    def test_tick_new_bar_triggers_full_redraw(self):
        w, fig = self._setup_widget_with_collections(n=5)
        w.update_chart = MagicMock()
        w._handle_realtime_tick({
            'symbol': '300994', 'price': 100.0, 'volume': 10,
            'timestamp': '2024-01-01 10:00:00'})  # 09:30 之后的 10:00 → 跨分钟周期
        w.update_chart.assert_called_once(), "新 bar 应走全量重绘（update_chart）"
        plt.close(fig)


# ============================================================
# 3. 残留旧 blit 闭环（铁律㊲：统一收敛到 BlitEngine）
# ============================================================
class TestNoLegacyBlitInMixins:

    def test_no_direct_copy_from_bbox_in_widgets(self):
        """gui/widgets 生产代码不允许自建 copy_from_bbox 背景管理（统一走 BlitEngine）"""
        import pathlib
        target = pathlib.Path(PROJECT_ROOT) / 'gui' / 'widgets'
        hits = []
        for p in target.rglob('*.py'):
            text = p.read_text(encoding='utf-8', errors='ignore')
            for i, line in enumerate(text.splitlines(), 1):
                if 'copy_from_bbox' in line:
                    hits.append(f"{p.relative_to(PROJECT_ROOT)}:{i}:{line.strip()}")
        # 统一引擎在 core/utils/mpl_blit.py（范围外）；gui/widgets 不应再自建背景管理
        assert not hits, f"gui/widgets 存在直接 copy_from_bbox 调用（应统一收敛 BlitEngine）:\n" + "\n".join(hits)

    def test_crosshair_delegates_to_engine(self):
        """crosshair 的 blit 入口必须委托 BlitEngine（HV5 验收，防回归）"""
        class _ChartWidget2(render_mod.RenderingMixin, cross_mod.CrosshairMixin):
            pass
        w = _ChartWidget2.__new__(_ChartWidget2)
        w.current_kdata = None
        w._full_kdata = None
        w._kline_collections = None
        w._volume_collections = None
        w.canvas = MagicMock()
        w.canvas.figure = MagicMock()
        w.figure = MagicMock()
        w.price_ax = MagicMock()
        w.volume_ax = MagicMock()
        w.indicator_ax = MagicMock()
        w.theme_manager = MagicMock()
        w.active_indicators = []
        w.chart_type = 'K线图'
        w.current_period = '1min'
        w.current_stock = '300994'
        w._ymin = 0.0
        w._ymax = 1.0
        engine = MagicMock()
        engine.canvas = w.canvas  # _ensure_blit_engine 以 canvas 同一性判断是否复用
        engine.background_cached = True
        engine.render.return_value = True
        w._blit_engine = engine
        w._crosshair_lines = {}
        w._crosshair_text = None
        w._crosshair_xtext = None
        w._crosshair_ytext = None
        w._hide_crosshair_elements = MagicMock()
        ok = w._blit_crosshair()
        assert ok is True
        engine.render.assert_called_once()
