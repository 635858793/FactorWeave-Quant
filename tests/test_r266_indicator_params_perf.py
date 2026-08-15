#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R266 测试：指标参数名对齐 TA-Lib + MACD/十字光标性能耗时日志

覆盖：
- indicator_mixin builtin 分支参数读取键对齐 TA-Lib（timeperiod/fastperiod/slowperiod/
  signalperiod/nbdevup/nbdevdn），修复「indicator_params_dialog 改参不生效」bug
- 旧键（n/fast/slow/signal/p）回退兼容
- MACD 柱状图渲染 [PERF][MACD-Hist] 耗时日志
- 十字光标 blit 局部重绘性能采样日志（背景重建/每60次均值/失败回退对比）
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

CHART_MIXINS = os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins')


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(CHART_MIXINS, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


crosshair_mod = _load_module('crosshair_mixin_mod', 'crosshair_mixin.py')
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
    return pd.DataFrame({'MACD': macd, 'MACDSignal': signal, 'MACDHist': macd - signal})


def _make_widget(monkeypatch, indicators):
    """构造 IndicatorMixin 实例（__new__ 绕过 __init__ + mock 依赖）"""
    w = indicator_mod.IndicatorMixin.__new__(indicator_mod.IndicatorMixin)
    w.current_kdata = make_kdata(120)
    w.price_ax = MagicMock()
    w.volume_ax = MagicMock()
    w.indicator_ax = MagicMock()
    w.active_indicators = indicators
    w.theme_manager = MagicMock()
    w.theme_manager.get_theme_colors.return_value = {'indicator_colors': ['#ff0000']}
    w.error_occurred = MagicMock()
    return w


def _mock_indicator_calc(monkeypatch, return_df):
    mock_calc = MagicMock(return_value=return_df)
    monkeypatch.setattr(indicator_mod, 'calculate_indicator', mock_calc)
    return mock_calc


# ==================== 1. builtin 分支参数键对齐 TA-Lib ====================

class TestBuiltinParamKeys:
    def test_macd_uses_talib_keys(self, monkeypatch):
        """MACD：fastperiod/slowperiod/signalperiod（TA-Lib 名）透传，对话框改参生效"""
        mock_calc = _mock_indicator_calc(monkeypatch, make_macd_result())
        w = _make_widget(monkeypatch, [{'name': 'MACD', 'group': 'builtin',
                                        'params': {'fastperiod': 20, 'slowperiod': 30, 'signalperiod': 5}}])
        w._render_indicators(w.current_kdata, x=np.arange(len(w.current_kdata)))
        assert mock_calc.call_args.kwargs == {
            'fastperiod': 20, 'slowperiod': 30, 'signalperiod': 5}

    def test_macd_legacy_keys_fallback(self, monkeypatch):
        """MACD：旧键 fast/slow/signal 仍回退生效（历史调用方兼容）"""
        mock_calc = _mock_indicator_calc(monkeypatch, make_macd_result())
        w = _make_widget(monkeypatch, [{'name': 'MACD', 'group': 'builtin',
                                        'params': {'fast': 15, 'slow': 28, 'signal': 7}}])
        w._render_indicators(w.current_kdata, x=np.arange(len(w.current_kdata)))
        assert mock_calc.call_args.kwargs == {
            'fastperiod': 15, 'slowperiod': 28, 'signalperiod': 7}

    def test_ma_uses_timeperiod(self, monkeypatch):
        """MA：timeperiod 透传（原读 n 不生效）"""
        mock_calc = _mock_indicator_calc(
            monkeypatch, pd.DataFrame({'MA': np.linspace(100, 120, 120)}))
        w = _make_widget(monkeypatch, [{'name': 'MA', 'group': 'builtin',
                                        'params': {'timeperiod': 30}}])
        w._render_indicators(w.current_kdata, x=np.arange(len(w.current_kdata)))
        assert mock_calc.call_args.kwargs == {'timeperiod': 30}

    def test_ma_legacy_n_fallback(self, monkeypatch):
        """MA：旧键 n 回退生效"""
        mock_calc = _mock_indicator_calc(
            monkeypatch, pd.DataFrame({'MA': np.linspace(100, 120, 120)}))
        w = _make_widget(monkeypatch, [{'name': 'MA', 'group': 'builtin',
                                        'params': {'n': 25}}])
        w._render_indicators(w.current_kdata, x=np.arange(len(w.current_kdata)))
        assert mock_calc.call_args.kwargs == {'timeperiod': 25}

    def test_rsi_uses_timeperiod(self, monkeypatch):
        """RSI：timeperiod 透传（原读 n 不生效）"""
        mock_calc = _mock_indicator_calc(
            monkeypatch, pd.DataFrame({'RSI': np.linspace(30, 70, 120)}))
        w = _make_widget(monkeypatch, [{'name': 'RSI', 'group': 'builtin',
                                        'params': {'timeperiod': 7}}])
        w._render_indicators(w.current_kdata, x=np.arange(len(w.current_kdata)))
        assert mock_calc.call_args.kwargs == {'timeperiod': 7}

    def test_boll_uses_talib_keys(self, monkeypatch):
        """BOLL：timeperiod/nbdevup/nbdevdn 独立透传（原读 n/p 且上下轨合并不生效）"""
        mock_calc = _mock_indicator_calc(monkeypatch, pd.DataFrame({
            'BBMiddle': np.linspace(100, 120, 120),
            'BBUpper': np.linspace(105, 125, 120),
            'BBLower': np.linspace(95, 115, 120),
        }))
        w = _make_widget(monkeypatch, [{'name': 'BOLL', 'group': 'builtin',
                                        'params': {'timeperiod': 10, 'nbdevup': 1.5, 'nbdevdn': 2.0}}])
        w._render_indicators(w.current_kdata, x=np.arange(len(w.current_kdata)))
        assert mock_calc.call_args.kwargs == {
            'timeperiod': 10, 'nbdevup': 1.5, 'nbdevdn': 2.0}

    def test_boll_legacy_keys_fallback(self, monkeypatch):
        """BOLL：旧键 n/p 回退（p 同时回退为 nbdevup/nbdevdn）"""
        mock_calc = _mock_indicator_calc(monkeypatch, pd.DataFrame({
            'BBMiddle': np.linspace(100, 120, 120),
            'BBUpper': np.linspace(105, 125, 120),
            'BBLower': np.linspace(95, 115, 120),
        }))
        w = _make_widget(monkeypatch, [{'name': 'BOLL', 'group': 'builtin',
                                        'params': {'n': 25, 'p': 1.8}}])
        w._render_indicators(w.current_kdata, x=np.arange(len(w.current_kdata)))
        assert mock_calc.call_args.kwargs == {
            'timeperiod': 25, 'nbdevup': 1.8, 'nbdevdn': 1.8}

    def test_no_params_uses_defaults(self, monkeypatch):
        """无用户参数：MACD 使用默认 12/26/9"""
        mock_calc = _mock_indicator_calc(monkeypatch, make_macd_result())
        w = _make_widget(monkeypatch, [{'name': 'MACD', 'group': 'builtin', 'params': {}}])
        w._render_indicators(w.current_kdata, x=np.arange(len(w.current_kdata)))
        assert mock_calc.call_args.kwargs == {
            'fastperiod': 12, 'slowperiod': 26, 'signalperiod': 9}


# ==================== 2. MACD 柱状图渲染性能日志 ====================

class TestMacdPerfLog:
    def test_macd_hist_emits_perf_log(self, monkeypatch):
        """MACD 柱状图渲染输出 [PERF][MACD-Hist] 耗时日志（含柱数/artist 对比信息）"""
        _mock_indicator_calc(monkeypatch, make_macd_result(120))
        mock_info = MagicMock()
        monkeypatch.setattr(indicator_mod.logger, 'info', mock_info)
        w = _make_widget(monkeypatch, [{'name': 'MACD', 'group': 'builtin', 'params': {}}])
        w._render_indicators(w.current_kdata, x=np.arange(len(w.current_kdata)))
        perf_logs = [str(c.args[0]) for c in mock_info.call_args_list
                     if '[PERF][MACD-Hist]' in str(c.args[0])]
        assert len(perf_logs) == 1
        assert '柱状图渲染耗时' in perf_logs[0]
        assert 'PolyCollection' in perf_logs[0]

    def test_macd_hist_uses_polycollection_not_bar(self, monkeypatch):
        """回归：MACD 柱状图仍走 add_collection（PolyCollection），而非逐柱 bar patch"""
        _mock_indicator_calc(monkeypatch, make_macd_result(120))
        w = _make_widget(monkeypatch, [{'name': 'MACD', 'group': 'builtin', 'params': {}}])
        w._render_indicators(w.current_kdata, x=np.arange(len(w.current_kdata)))
        assert w.indicator_ax.add_collection.call_count == 2
        assert not w.indicator_ax.bar.called


# ==================== 3. 十字光标 blit 性能采样日志 ====================

class TestCrosshairPerfLog:
    def _make(self):
        c = crosshair_mod.CrosshairMixin.__new__(crosshair_mod.CrosshairMixin)
        c.canvas = MagicMock()
        c.figure = MagicMock()
        c.figure.bbox = 'bbox'
        c._blit_background = None
        c._crosshair_lines = {}
        c._crosshair_text = None
        c._crosshair_xtext = None
        c._crosshair_ytext = None
        return c

    def test_background_rebuild_emits_perf_log(self, monkeypatch):
        """首次/失效后 blit 背景重建（全画布 draw+copy）输出耗时日志"""
        c = self._make()
        mock_info = MagicMock()
        monkeypatch.setattr(crosshair_mod.logger, 'info', mock_info)
        assert c._blit_crosshair() is True
        assert c.canvas.draw.called
        assert c.canvas.copy_from_bbox.called
        assert c.canvas.blit.called
        perf_logs = [str(call.args[0]) for call in mock_info.call_args_list
                     if '[PERF][Crosshair] blit背景重建' in str(call.args[0])]
        assert len(perf_logs) == 1

    def test_reuse_background_skips_full_draw(self, monkeypatch):
        """背景已缓存时不再全画布 draw/copy（仅 restore+blit），耗时纳入采样"""
        c = self._make()
        c._blit_background = MagicMock()
        mock_info = MagicMock()
        monkeypatch.setattr(crosshair_mod.logger, 'info', mock_info)
        c._blit_crosshair()
        assert not c.canvas.draw.called
        assert not c.canvas.copy_from_bbox.called
        assert c.canvas.restore_region.called
        assert c.canvas.blit.called

    def test_accumulate_logs_avg_every_60(self, monkeypatch):
        """采样每60次输出一次均值/最大日志，并重置计数器"""
        c = crosshair_mod.CrosshairMixin.__new__(crosshair_mod.CrosshairMixin)
        mock_info = MagicMock()
        monkeypatch.setattr(crosshair_mod.logger, 'info', mock_info)
        for i in range(59):
            c._accumulate_blit_perf(0.001)
        assert c._blit_perf_count == 59
        assert not mock_info.called
        c._accumulate_blit_perf(0.003)  # 第60次触发
        assert c._blit_perf_count == 0  # 已重置
        assert c._blit_perf_total == 0.0
        perf_logs = [str(call.args[0]) for call in mock_info.call_args_list
                     if '[PERF][Crosshair] blit局部重绘' in str(call.args[0])]
        assert len(perf_logs) == 1
        assert 'avg=' in perf_logs[0] and 'max=' in perf_logs[0]

    def test_blit_failure_fallback_logs_cost(self, monkeypatch):
        """blit 失败回退全画布 draw_idle 时输出耗时对比日志"""
        c = self._make()
        c._blit_background = MagicMock()
        c.canvas.restore_region.side_effect = Exception('boom')
        mock_warn = MagicMock()
        monkeypatch.setattr(crosshair_mod.logger, 'warning', mock_warn)
        assert c._blit_crosshair() is False
        assert c.canvas.draw_idle.called
        assert c._blit_background is None  # 失败后背景失效，下次重建
        fallback_logs = [str(call.args[0]) for call in mock_warn.call_args_list
                         if '[PERF][Crosshair]' in str(call.args[0])]
        assert len(fallback_logs) == 1


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
