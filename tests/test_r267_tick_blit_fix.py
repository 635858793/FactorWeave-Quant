#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HV6 修复回归测试：tick 增量渲染 × BlitEngine 交互（R292-HV6 复检）

覆盖本轮审计交叉验证确认的 100% 问题修复：
1. tick 成功 render 后必须 refresh_background 同步背景快照 —— 否则鼠标移动
   （十字光标 blit）会 restore 回 tick 前旧快照，bar 内 tick 更新像素级回退
2. 背景将重建（首次/失效后）时 tick 路径必须先隐藏十字线 —— 否则快照含
   十字线残影（与 crosshair_mixin._blit_crosshair 预处理一致）
3. 退化全量分支 DataFrame.__bool__ 修复 —— _full_kdata 为 DataFrame 时
   `or` 短路抛 ValueError 被外层 try 吞掉，退化全量永不生效
4. BlitEngine.refresh_background 正确覆盖 _background 为最新像素
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

# dummy 模块注册（与 test_r267_tick_incremental 同款，conftest 已把 gui.widgets.* mock 化）
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

CHART_MIXINS = os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins')


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(CHART_MIXINS, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


render_mod = _load_module('rendering_mixin_mod3', 'rendering_mixin.py')

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


class _Widget(render_mod.RenderingMixin):
    """组合 mixin（__new__ 绕过 __init__ + mock 渲染依赖）"""


def _make_widget_with_collections(n=100):
    """update_chart 已保存集合引用的前置状态（真实渲染器构建真实 collections）"""
    from optimization.chart_renderer import ChartRenderer
    r = ChartRenderer.__new__(ChartRenderer)
    r.render_error = MagicMock()
    w = _Widget.__new__(_Widget)
    w.renderer = r
    data = make_kdata(n)
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
    w.chart_type = 'K线图'
    w.current_period = '1min'
    w.current_stock = '300994'
    w.canvas = fig.canvas
    w._fig = fig
    return w, fig


class StubEngine:
    """可断言的 BlitEngine 替身（记录 render/refresh_background/hide 调用）"""

    def __init__(self, bg_cached=True, render_ret=True):
        self.bg_cached = bg_cached
        self.render_ret = render_ret
        self.render_calls = 0
        self.refresh_calls = 0
        self.canvas = object()

    @property
    def background_cached(self):
        return self.bg_cached

    def render(self, artists):
        self.render_calls += 1
        return self.render_ret

    def refresh_background(self):
        self.refresh_calls += 1


TICK = {'symbol': '300994', 'price': None, 'volume': 100,
        'timestamp': '2024-01-01 09:31:00'}


class TestTickBlitSnapshotSync:
    """修复 1+2：tick 后同步背景快照 + 背景重建前隐藏十字线"""

    def _run_one_tick(self, w, engine, delta=0.3):
        last_open = w.current_kdata['open'].iloc[-1]
        w._handle_realtime_tick(dict(TICK, price=last_open + delta))

    def test_tick_success_syncs_background_snapshot(self):
        w, fig = self._widget()
        engine = StubEngine(bg_cached=True)
        w._blit_engine = engine
        self._run_one_tick(w, engine)
        assert engine.render_calls == 1
        assert engine.refresh_calls == 1, \
            "tick 成功 render 后必须 refresh_background 同步快照（否则鼠标移动 restore 回旧 K 线像素）"
        plt.close(fig)

    def test_tick_background_rebuild_hides_crosshair(self):
        w, fig = self._widget()
        engine = StubEngine(bg_cached=False)  # 背景将重建（首次/失效后）
        w._blit_engine = engine
        hides = []
        w._hide_crosshair_elements = lambda: hides.append(1)
        self._run_one_tick(w, engine)
        assert engine.render_calls == 1
        assert hides, \
            "背景将重建时必须先隐藏十字线（与 _blit_crosshair 预处理一致，防止快照含残影）"
        assert engine.refresh_calls == 1
        plt.close(fig)

    def test_tick_cached_background_no_hide(self):
        w, fig = self._widget()
        engine = StubEngine(bg_cached=True)
        w._blit_engine = engine
        hides = []
        w._hide_crosshair_elements = lambda: hides.append(1)
        self._run_one_tick(w, engine)
        assert not hides, "背景已缓存时无需 hide（避免无谓开销）"
        plt.close(fig)

    def test_tick_render_failure_falls_back_no_refresh(self):
        w, fig = self._widget()
        engine = StubEngine(bg_cached=True, render_ret=False)  # render 失败
        w._blit_engine = engine
        self._run_one_tick(w, engine)
        assert engine.render_calls == 1
        assert engine.refresh_calls == 0, "render 失败（回退 draw_idle）时不应同步快照"
        plt.close(fig)

    def _widget(self):
        return _make_widget_with_collections(n=100)


class TestFallbackDataFrameFix:
    """修复 3：退化全量分支 _full_kdata 为 DataFrame 时 update_chart 必须真正执行"""

    def test_fallback_with_dataframe_full_kdata_calls_update_chart(self):
        w = _Widget.__new__(_Widget)
        data = make_kdata(50)
        w.current_kdata = data.copy()
        w._full_kdata = data.copy()  # 真实 DataFrame（修复前 `or` 短路会抛 ValueError）
        w._kline_collections = None  # 增量前置缺失 → _update_last_bar_with_tick 返回 False
        w._volume_collections = None
        w.chart_type = 'K线图'
        w.current_period = '1min'
        w.current_stock = '300994'
        w.update_chart = MagicMock()
        w._handle_realtime_tick(dict(TICK, price=100.0))
        w.update_chart.assert_called_once(), \
            "退化全量必须真正执行 update_chart（修复 DataFrame.__bool__ 被外层吞掉）"
        args = w.update_chart.call_args[0][0]
        assert args['kdata'] is w._full_kdata, "退化全量应使用全量数据源"


class TestBlitEngineRefreshBackground:
    """修复 4：BlitEngine.refresh_background 正确覆盖 _background 为最新像素"""

    def test_refresh_background_updates_snapshot(self):
        from core.utils.mpl_blit import BlitEngine
        fig, ax = plt.subplots(figsize=(6, 3))
        line, = ax.plot([0, 1], [0, 1], color='red')
        engine = BlitEngine(fig.canvas, log_tag='[Test]', sample_every=0)
        assert engine.background_cached is False
        assert engine.render([line]) is True
        assert engine.background_cached is True
        old_bg = engine._background
        engine.refresh_background()
        assert engine._background is not None
        assert engine._background is not old_bg, \
            "refresh_background 必须用最新画布像素覆盖旧快照"
        plt.close(fig)

    def test_refresh_background_noop_without_cache(self):
        from core.utils.mpl_blit import BlitEngine
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.plot([0, 1], [0, 1])
        engine = BlitEngine(fig.canvas, log_tag='[Test]', sample_every=0)
        # 背景未缓存：refresh 应为无害 no-op
        engine.refresh_background()
        assert engine._background is None
        plt.close(fig)
