#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R267 测试：K线数据量缩短根因修复

根因：rendering_mixin.update_chart 中 current_kdata 被降采样结果覆盖
（数据>1200条时，指标切换若基于已降采样的 current_kdata 重渲染，原始数据永久丢失，
表现为"点击指标后图表数据量缩短且无法恢复"）。

修复：新增 _full_kdata 保存完整原始数据；交互重渲染入口
（on_indicator_selected / _on_indicator_changed / refresh 等）改用 _get_render_kdata()
从完整数据重新降采样，保证：
- >1200 条：current_kdata 恒为降采样结果（不继续缩水），_full_kdata 保留完整数据
- ≤1200 条（如日线最近1年 365 条）：行为与修复前完全一致（零业务影响）
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

# R267: utility_mixin 顶部有绝对导入 from gui.widgets.chart_mixins.ui_mixin import UIMixin，
# 而 tests/conftest.py 已把 gui.widgets 及全部 gui.widgets.* 注册为 MagicMock（无 __path__），
# 直接 import 真实包会报 "not a package"。这里按 R251/R252 同款模式注册 dummy 模块，
# 仅满足 utility_mixin 的导入依赖，不破坏 conftest 的 Qt 崩溃防护。
from unittest.mock import MagicMock as _MagicMock  # noqa: E402
_dummy_pkg = _MagicMock()
_dummy_pkg.__name__ = 'gui.widgets.chart_mixins'
_dummy_pkg.__file__ = '<mock:gui.widgets.chart_mixins>'
_dummy_ui = _MagicMock()
_dummy_ui.__name__ = 'gui.widgets.chart_mixins.ui_mixin'
_dummy_ui.__file__ = '<mock:gui.widgets.chart_mixins.ui_mixin>'
sys.modules.setdefault('gui.widgets.chart_mixins', _dummy_pkg)
sys.modules.setdefault('gui.widgets.chart_mixins.ui_mixin', _dummy_ui)

CHART_MIXINS = os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins')


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(CHART_MIXINS, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


render_mod = _load_module('rendering_mixin_mod', 'rendering_mixin.py')
util_mod = _load_module('utility_mixin_mod', 'utility_mixin.py')
ind_mod = _load_module('indicator_mixin_mod', 'indicator_mixin.py')


def make_kdata(n):
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


class _ChartWidget(render_mod.RenderingMixin, ind_mod.IndicatorMixin,
                   util_mod.UtilityMixin):
    """组合 mixin，模拟 ChartWidget 的 MRO（IndicatorMixin.on_indicator_selected 优先）"""


def _make_widget():
    """构造组合 widget（__new__ 绕过 __init__ + mock 渲染依赖）"""
    w = _ChartWidget.__new__(_ChartWidget)
    w.current_kdata = None
    w._full_kdata = None
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
    w._render_indicators = MagicMock()
    # R290: _render_indicator_data 已删除（死代码），无需 mock
    w._optimize_display = MagicMock()
    w.close_loading_dialog = MagicMock()
    w._invalidate_crosshair_background = MagicMock()
    w.show_no_data = MagicMock()
    w._safe_format_date = MagicMock(return_value='2024-01-01')
    w._get_chart_style = MagicMock(return_value={})
    w._current_stock_code = '300994'
    return w


# ==================== 1. >1200 条：完整数据保留，不持续缩水 ====================

class TestLargeDataNoShrink:
    def test_full_kdata_preserved_after_first_render(self):
        """5000 条：渲染后 current_kdata=1200（降采样），_full_kdata=5000（完整保留）"""
        w = _make_widget()
        w.update_chart({'kdata': make_kdata(5000)})

        assert w.current_kdata is not None
        assert len(w.current_kdata) == 1200  # 降采样后渲染数据
        assert len(w._full_kdata) == 5000    # 完整数据未被破坏

    def test_indicator_switch_does_not_shrink_further(self):
        """模拟真实链路：指标切换(on_indicator_selected→_on_indicator_changed→update_chart)
        连续 3 次后 current_kdata 恒定 1200，不再缩短"""
        w = _make_widget()
        w.update_chart({'kdata': make_kdata(5000)})

        for inds in (['MA'], ['MACD'], ['MA', 'MACD']):
            w.on_indicator_selected(inds)

        assert len(w.current_kdata) == 1200       # 恒定，未继续缩水
        assert len(w._full_kdata) == 5000         # 完整数据始终保留
        assert len(w._get_render_kdata()) == 5000  # 重渲染数据源为完整数据

    def test_utility_on_indicator_selected_uses_full_data(self):
        """UtilityMixin.on_indicator_selected 同样基于完整数据源"""
        w = _make_widget()
        w.update_chart({'kdata': make_kdata(3000)})
        w.active_indicators = ['MA']
        util_mod.UtilityMixin.on_indicator_selected(w, ['MA'])

        assert len(w._get_render_kdata()) == 3000
        assert len(w.current_kdata) == 1200


# ==================== 2. ≤1200 条（365条日线场景）：行为完全不变 ====================

class TestSmallDataUnchanged:
    def test_365_rows_no_sampling(self):
        """365 条（<1200）：current_kdata 与 _full_kdata 一致，无降采样"""
        w = _make_widget()
        kdata = make_kdata(365)
        w.update_chart({'kdata': kdata})

        assert len(w.current_kdata) == 365
        assert len(w._full_kdata) == 365

    def test_365_indicator_switch_keeps_365(self):
        """365 条 + 指标切换：仍为 365 条，与修复前行为一致"""
        w = _make_widget()
        w.update_chart({'kdata': make_kdata(365)})
        w.on_indicator_selected(['SMA'])
        w.on_indicator_selected(['MA', 'SMA'])

        assert len(w.current_kdata) == 365
        assert len(w._full_kdata) == 365


# ==================== 3. 兼容性与清理 ====================

class TestCompatAndCleanup:
    def test_get_render_kdata_fallback(self):
        """无 _full_kdata 时回退 current_kdata（兼容旧实例/旧路径）"""
        w = _make_widget()
        w.current_kdata = make_kdata(100)
        delattr(w, '_full_kdata')  # 模拟旧代码路径没有该属性

        assert len(w._get_render_kdata()) == 100

    def test_clear_chart_resets_full_kdata(self):
        """clear_chart 同时清空 _full_kdata，防止残留脏数据"""
        w = _make_widget()
        w.update_chart({'kdata': make_kdata(5000)})
        assert w._full_kdata is not None

        w.clear_chart()

        assert w.current_kdata is None
        assert w._full_kdata is None

    def test_independent_mixin_fallback(self):
        """独立 IndicatorMixin（未组合 UtilityMixin）调用 on_indicator_selected 时，
        无 _get_render_kdata 应回退 current_kdata（兼容 R264 等单例测试/旧路径）"""
        w = ind_mod.IndicatorMixin.__new__(ind_mod.IndicatorMixin)
        w.current_kdata = make_kdata(500)
        w.active_indicators = []
        w.update_chart = MagicMock()
        w.error_occurred = MagicMock()

        w.on_indicator_selected(['MA'])

        assert w.update_chart.call_count == 1
        # 回退到 current_kdata（未被降采样覆盖，数据完整）
        kdata_arg = w.update_chart.call_args[0][0]['kdata']
        assert kdata_arg is w.current_kdata
        assert len(kdata_arg) == 500
