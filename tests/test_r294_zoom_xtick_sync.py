#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R294 测试：分钟K线 X 轴缩放日期标签联动修复（TDD）

覆盖（根因：zoom_mixin 全部 7 处 set_xlim 路径只改范围不刷新刻度，
渲染路径一次性写入全量等距固定 xticks（rendering_mixin L470-486 /
indicator_mixin L577-585 / chart_widget L739-752），缩放后日期标签
不随可见范围更新/缺失）：

- R1 注册：_init_zoom_interaction 为 price_ax 注册 'xlim_changed' 回调
  → 覆盖框选缩放/右拖平移/滚轮缩放/双击还原全部路径
- R2 全量视图：_refresh_x_date_ticks 输出与渲染路径一致的等距 ticks
  （step = n//8，位置与渲染期全量 ticks 相同，行为不回归）
- R3 缩放视图：可见 161 根时 ticks 全部落在 [left, right] 内且 ≤9 个
- R4 极小缩放：可见 11 根时 step=1，逐根显示时刻（分钟数据期望）
- R5 分钟标签：分钟数据经 _safe_format_date 输出时刻格式（period 透传）
- R6 空数据安全：current_kdata=None / 空表不抛异常
- R7 幂等：连续两次回调结果一致（_limit_xlim 二次 set_xlim 触发安全）
"""
import os
import sys
import types
import importlib.util
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# conftest.py mock 了 'gui.widgets'，按 test_r293 模式临时恢复再 importlib 加载
_saved_gui_widgets = sys.modules.pop('gui.widgets', None)


def _load_module_from_file(mod_name, file_path):
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_chart_mixins_pkg = MagicMock()
_chart_mixins_pkg.__name__ = 'gui.widgets.chart_mixins'
_chart_mixins_pkg.__file__ = '<mock:gui.widgets.chart_mixins>'
sys.modules['gui.widgets.chart_mixins'] = _chart_mixins_pkg

_gui_widgets_pkg = types.ModuleType('gui.widgets')
_gui_widgets_pkg.__path__ = [
    os.path.join(PROJECT_ROOT, 'gui', 'widgets')]
sys.modules['gui.widgets'] = _gui_widgets_pkg

_load_module_from_file(
    'gui.widgets.chart_mixins.ui_mixin',
    os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins', 'ui_mixin.py'))
_load_module_from_file(
    'gui.widgets.chart_mixins.utility_mixin',
    os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins',
                 'utility_mixin.py'))
_load_module_from_file(
    'gui.widgets.chart_mixins.zoom_mixin',
    os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins',
                 'zoom_mixin.py'))

from gui.widgets.chart_mixins.utility_mixin import UtilityMixin  # noqa: E402
from gui.widgets.chart_mixins.zoom_mixin import ZoomMixin  # noqa: E402


def _make_kdata(n=480, freq='D'):
    """构造 n 根日线/分钟线（datetime 列 + OHLCV）"""
    ts = pd.date_range('2026-01-01', periods=n,
                       freq='1min' if freq == 'min' else freq)
    close = np.linspace(10.0, 11.0, n)
    return pd.DataFrame({
        'datetime': ts,
        'open': close - 0.1,
        'high': close + 0.2,
        'low': close - 0.2,
        'close': close,
        'volume': np.full(n, 1000),
    })


def _make_widget(kdata, period=None):
    """构造 ZoomMixin + UtilityMixin 测试桩（轴为 MagicMock，仅 get_xlim 生效）"""
    class _ChartWidget(ZoomMixin, UtilityMixin):
        pass
    w = _ChartWidget.__new__(_ChartWidget)
    w.canvas = MagicMock()
    w.price_ax = MagicMock()
    if kdata is not None:
        w.price_ax.get_xlim.return_value = (0.0, float(len(kdata) - 1))
    w.volume_ax = MagicMock()
    w.indicator_ax = MagicMock()
    w.current_kdata = kdata
    w.current_period = period
    return w


def _captured_xticks(w):
    """从 indicator_ax.set_xticks 首次调用取出 ticks 数组"""
    calls = [c for c in w.indicator_ax.set_xticks.call_args_list]
    assert calls, "set_xticks 未被调用"
    return np.asarray(calls[-1][0][0])


class TestRegisterXlimChanged:
    """R1: xlim_changed 回调注册（一处注册覆盖全部缩放路径）"""

    def test_init_registers_xlim_changed_callback(self):
        """_init_zoom_interaction 为 price_ax 注册 xlim_changed"""
        w = _make_widget(_make_kdata())
        w._init_zoom_interaction()
        names = [c.args[0] for c in w.price_ax.callbacks.connect.call_args_list]
        assert 'xlim_changed' in names

    def test_callback_is_refresh_method(self):
        """回调指向 _refresh_x_date_ticks"""
        w = _make_widget(_make_kdata())
        w._init_zoom_interaction()
        for c in w.price_ax.callbacks.connect.call_args_list:
            if c.args[0] == 'xlim_changed':
                assert c.args[1] == w._refresh_x_date_ticks
                return
        pytest.fail("未注册 xlim_changed 回调")


class TestRefreshFullView:
    """R2: 全量视图 ticks 与渲染路径一致（回归）"""

    def test_full_view_step_matches_render_contract(self):
        """n=480 日线 → step=60，xticks == [0,60,...,420]（渲染路径 L470-471 契约）"""
        kdata = _make_kdata(480)
        w = _make_widget(kdata)
        w.price_ax.get_xlim.return_value = (0.0, 479.0)
        w._refresh_x_date_ticks()
        expected = np.arange(0, 480, 480 // 8)
        assert np.array_equal(_captured_xticks(w), expected)

    def test_full_view_label_count_matches_ticks(self):
        """标签数 == ticks 数（set_xticklabels 收到等长数组）"""
        kdata = _make_kdata(480)
        w = _make_widget(kdata)
        w.price_ax.get_xlim.return_value = (0.0, 479.0)
        w._refresh_x_date_ticks()
        ticks = _captured_xticks(w)
        labels = w.indicator_ax.set_xticklabels.call_args[0][0]
        assert len(labels) == len(ticks)


class TestRefreshZoomedView:
    """R3/R4: 缩放视图 ticks 随可见范围联动"""

    def test_zoomed_ticks_within_visible_range(self):
        """xlim=(100,260) 可见 161 根 → 全部 ticks ∈ [100,260] 且 ≤9"""
        kdata = _make_kdata(480)
        w = _make_widget(kdata)
        w.price_ax.get_xlim.return_value = (100.0, 260.0)
        w._refresh_x_date_ticks()
        ticks = _captured_xticks(w)
        assert len(ticks) <= 9
        assert ticks.min() >= 100 and ticks.max() <= 260

    def test_small_zoom_keeps_every_bar(self):
        """xlim=(50,60) 可见 11 根 → step=1，逐根出时刻标签"""
        kdata = _make_kdata(480)
        w = _make_widget(kdata)
        w.price_ax.get_xlim.return_value = (50.0, 60.0)
        w._refresh_x_date_ticks()
        ticks = _captured_xticks(w)
        assert list(ticks) == list(range(50, 61))

    def test_minute_view_labels_use_time_format(self):
        """1min 数据缩放视图：标签经 _safe_format_date 输出时刻（period 透传）"""
        kdata = _make_kdata(240, freq='min')
        w = _make_widget(kdata, period='1m')
        w.price_ax.get_xlim.return_value = (30.0, 80.0)
        w._refresh_x_date_ticks()
        labels = w.indicator_ax.set_xticklabels.call_args[0][0]
        # 分钟频率 → 当日输出 '%H:%M'（R293-G1 契约，period='1m' 走 Period.is_intraday）
        assert any(':' in str(lb) for lb in labels)

    def test_daily_view_labels_keep_date_format(self):
        """日线全量视图：标签维持 '%Y-%m-%d'（回归）"""
        kdata = _make_kdata(480)
        w = _make_widget(kdata, period='D')
        w._refresh_x_date_ticks()
        labels = w.indicator_ax.set_xticklabels.call_args[0][0]
        assert any('-' in str(lb) for lb in labels)


class TestRefreshSafety:
    """R6/R7: 空数据安全 + 幂等"""

    def test_no_kdata_is_safe(self):
        """current_kdata=None 不抛异常"""
        w = _make_widget(None)
        w._refresh_x_date_ticks()  # 不应抛异常

    def test_empty_kdata_is_safe(self):
        """空表不抛异常"""
        w = _make_widget(pd.DataFrame(columns=['datetime', 'close']))
        w._refresh_x_date_ticks()

    def test_idempotent_double_call(self):
        """连续两次回调结果一致（_limit_xlim 二次 set_xlim 触发安全）"""
        kdata = _make_kdata(480)
        w = _make_widget(kdata)
        w.price_ax.get_xlim.return_value = (100.0, 260.0)
        w._refresh_x_date_ticks()
        first = _captured_xticks(w)
        w._refresh_x_date_ticks()
        second = _captured_xticks(w)
        assert np.array_equal(first, second)
