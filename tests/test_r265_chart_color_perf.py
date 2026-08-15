#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R265 测试：K线颜色语义修复 + 十字光标blit局部重绘 + 缩放性能优化 + MACD柱状图PolyCollection

覆盖：
- _get_change_color 语义颠倒 bug 修复（涨=红/跌=绿，键名 k_up/k_down）
- 十字光标 blit 局部重绘（restore_region + draw_artist + blit，替代每帧全画布 draw_idle）
- 缩放路径移除 _optimize_display 高频调用 + blit 背景失效标记
- MACD 柱状图 bar → PolyCollection（1 artist 替代 N patch）
"""
import os
import sys
import inspect
import importlib.util

import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

CHART_MIXINS = os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins')


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(CHART_MIXINS, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


crosshair_mod = _load_module('crosshair_mixin_mod', 'crosshair_mixin.py')
zoom_mod = _load_module('zoom_mixin_mod', 'zoom_mixin.py')
indicator_mod = _load_module('indicator_mixin_mod', 'indicator_mixin.py')


def make_kdata(n=120):
    rng = np.random.default_rng(42)
    close = np.cumsum(rng.standard_normal(n)) + 100
    open_ = close + rng.standard_normal(n) * 0.5
    high = np.maximum(open_, close) + rng.random(n)
    low = np.minimum(open_, close) - rng.random(n)
    volume = rng.integers(1000, 10000, n)
    return pd.DataFrame({
        'open': open_, 'high': high, 'low': low,
        'close': close, 'volume': volume,
        'datetime': pd.date_range('2024-01-01', periods=n, freq='D'),
    })


def make_macd_result(n=120):
    rng = np.random.default_rng(7)
    warm = 10
    macd = np.full(n, np.nan)
    macd[warm:] = rng.standard_normal(n - warm) * 0.5
    signal = np.full(n, np.nan)
    signal[warm:] = rng.standard_normal(n - warm) * 0.3
    hist = macd - signal
    return pd.DataFrame({'MACD': macd, 'MACDSignal': signal, 'MACDHist': hist})


# ==================== 1. _get_change_color 语义修复 ====================

class TestChangeColor:
    def _make(self, theme_colors=None, side_effect=None):
        c = crosshair_mod.CrosshairMixin.__new__(crosshair_mod.CrosshairMixin)
        c.theme_manager = MagicMock()
        if side_effect is not None:
            c.theme_manager.get_theme_colors.side_effect = side_effect
        else:
            c.theme_manager.get_theme_colors.return_value = theme_colors or {}
        return c

    def test_up_uses_k_up_red(self):
        """上涨(+) → k_up（红），而非绿"""
        c = self._make({'k_up': '#ff0000', 'k_down': '#00ff00'})
        assert c._get_change_color('+') == '#ff0000'

    def test_down_uses_k_down_green(self):
        """下跌(-) → k_down（绿），而非红"""
        c = self._make({'k_up': '#ff0000', 'k_down': '#00ff00'})
        assert c._get_change_color('-') == '#00ff00'

    def test_theme_missing_keys_use_correct_defaults(self):
        """主题缺失键时：涨=红#e74c3c、跌=绿#27ae60（与 rendering_mixin 默认一致）"""
        c = self._make({})
        assert c._get_change_color('+') == '#e74c3c'
        assert c._get_change_color('-') == '#27ae60'

    def test_flat_uses_chart_text(self):
        c = self._make({'chart_text': '#222b45'})
        assert c._get_change_color('') == '#222b45'

    def test_exception_falls_back_red_up_green_down(self):
        c = self._make(side_effect=Exception('boom'))
        assert c._get_change_color('+') == '#e74c3c'
        assert c._get_change_color('-') == '#27ae60'

    def test_no_longer_uses_wrong_keys(self):
        """回归防护：取键代码不再使用 up_color/down_color 颠倒键（docstring说明除外）"""
        src = inspect.getsource(crosshair_mod.CrosshairMixin._get_change_color)
        assert "colors.get('up_color'" not in src
        assert "colors.get('down_color'" not in src
        assert 'k_up' in src and 'k_down' in src


# ==================== 2. 十字光标 blit 局部重绘 ====================

class TestCrosshairBlit:
    def _make(self, canvas=None, lines=None):
        c = crosshair_mod.CrosshairMixin.__new__(crosshair_mod.CrosshairMixin)
        c.canvas = canvas or MagicMock()
        c.figure = MagicMock()
        c.figure.bbox = MagicMock()
        c._crosshair_lines = lines if lines is not None else {
            'price_v': self._mk_line(),
            'volume_v': self._mk_line(),
            'indicator_v': self._mk_line(),
            'price_h': self._mk_line(),
        }
        c._crosshair_text = None
        c._crosshair_xtext = None
        c._crosshair_ytext = None
        c._blit_background = None
        c._hide_crosshair_elements = MagicMock()
        return c

    @staticmethod
    def _mk_line():
        line = MagicMock()
        line.get_visible.return_value = True
        line.axes = MagicMock()
        return line

    def test_invalidate_background_sets_none(self):
        c = self._make()
        c._blit_background = object()
        c._invalidate_crosshair_background()
        assert c._blit_background is None

    def test_blit_builds_background_then_restore_blit(self):
        """首次 blit：隐藏元素→draw→copy背景→restore→draw_artist→blit"""
        c = self._make()
        ok = c._blit_crosshair()
        assert ok is True
        c.canvas.draw.assert_called_once()
        c.canvas.copy_from_bbox.assert_called_once()
        c.canvas.restore_region.assert_called_once()
        c.canvas.blit.assert_called_once()
        # draw_idle 不应被调用（局部重绘成功）
        c.canvas.draw_idle.assert_not_called()

    def test_blit_reuses_background_on_second_call(self):
        """第二次 blit：不再 draw/copy，直接 restore+blit"""
        c = self._make()
        c._blit_crosshair()
        c.canvas.reset_mock()
        ok = c._blit_crosshair()
        assert ok is True
        c.canvas.draw.assert_not_called()
        c.canvas.copy_from_bbox.assert_not_called()
        c.canvas.restore_region.assert_called_once()
        c.canvas.blit.assert_called_once()

    def test_blit_fallback_draw_idle_on_error(self):
        """copy_from_bbox 失败 → 回退 draw_idle，返回 False"""
        c = self._make()
        c.canvas.copy_from_bbox.side_effect = RuntimeError('no agg renderer')
        ok = c._blit_crosshair()
        assert ok is False
        c.canvas.draw_idle.assert_called_once()

    def test_clear_elements_invalidates_background(self):
        c = self._make(lines={})
        c._blit_background = object()
        c._clear_crosshair_elements()
        assert c._blit_background is None


# ==================== 3. 缩放路径性能优化 ====================

class TestZoomPerf:
    def _make(self):
        z = zoom_mod.ZoomMixin.__new__(zoom_mod.ZoomMixin)
        z.price_ax = MagicMock()
        z.price_ax.get_xlim.return_value = (0.0, 100.0)
        z._zoom_history = []
        z._limit_xlim = MagicMock()
        z.canvas = MagicMock()
        z._optimize_display = MagicMock()
        z._invalidate_crosshair_background = MagicMock()
        return z

    def test_scroll_does_not_call_optimize_display(self):
        """滚轮缩放不再每格调用 _optimize_display（纯浪费）"""
        z = self._make()
        ev = MagicMock()
        ev.inaxes = z.price_ax
        ev.xdata = 50.0
        ev.button = 'up'
        z._on_zoom_scroll(ev)
        z._optimize_display.assert_not_called()
        z.canvas.draw_idle.assert_called_once()

    def test_scroll_invalidates_blit_background(self):
        """滚轮缩放后标记十字光标 blit 背景失效"""
        z = self._make()
        ev = MagicMock()
        ev.inaxes = z.price_ax
        ev.xdata = 50.0
        ev.button = 'up'
        z._on_zoom_scroll(ev)
        z._invalidate_crosshair_background.assert_called_once()

    def test_release_does_not_call_optimize_display(self):
        """框选释放后不再调用 _optimize_display"""
        z = self._make()
        z._zoom_press_x = 20.0
        z._zoom_rect = None
        z._ymin = None
        z._ymax = None
        ev = MagicMock()
        ev.inaxes = z.price_ax
        ev.button = 1
        ev.xdata = 80.0
        z._on_zoom_release(ev)
        z._optimize_display.assert_not_called()
        z._invalidate_crosshair_background.assert_called_once()


# ==================== 4. MACD 柱状图 PolyCollection ====================

class TestMacdHistCollection:
    def _make_widget(self, monkeypatch):
        w = indicator_mod.IndicatorMixin()
        w.active_indicators = [
            {'name': 'MACD', 'group': 'builtin', 'params': {'fast': 12, 'slow': 26, 'signal': 9}}
        ]
        w.price_ax = MagicMock()
        w.indicator_ax = MagicMock()
        w._get_indicator_style = MagicMock(return_value={
            'color': '#1976d2', 'linewidth': 0.7, 'alpha': 0.85, 'label': 'MACD'})
        monkeypatch.setattr(indicator_mod, 'calculate_indicator',
                            MagicMock(return_value=make_macd_result(120)))
        return w

    def test_macd_hist_uses_polycollection_not_bar(self, monkeypatch):
        """MACD 柱状图用 add_collection（PolyCollection），不再创建 N 个 bar patch"""
        w = self._make_widget(monkeypatch)
        w._render_indicators(make_kdata(120), x=np.arange(120))
        w.indicator_ax.add_collection.assert_called()
        w.indicator_ax.bar.assert_not_called()

    def test_macd_hist_renders_three_line_series(self, monkeypatch):
        """MACD/Signal 线绘制在 indicator_ax（plot 被调用）"""
        w = self._make_widget(monkeypatch)
        w._render_indicators(make_kdata(120), x=np.arange(120))
        assert w.indicator_ax.plot.call_count >= 2

    def test_no_crash_without_indicators(self):
        w = indicator_mod.IndicatorMixin()
        w.active_indicators = []
        w._render_indicators(make_kdata(50), x=np.arange(50))  # 不应抛异常
