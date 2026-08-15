#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R270 测试：指标计算列污染修复（KAMA/MAMA/TEMA 图形趋同根因）+ 第一/第二指标区域动态切换

覆盖：
- P0 回归：_calculate_talib_indicator 副本化后，连续计算 KAMA/MAMA/TEMA/EMA 结果列互不累积，
  原始 kdata 不被污染（原根因：直算兜底路径原地修改传入 df，渲染时每个指标画出全部历史累积列）
- 渲染 region 路由：region='indicator1' → indicator_ax，region='indicator2' → indicator_ax2
- 多区域指标渲染目标轴验证：indicator_ax 只含第一区指标线，indicator_ax2 只含第二区指标线
- middle_panel 全量指标列表（内置 7 + TA-Lib 动态枚举去重，含 KAMA/MAMA/TEMA/KDJ）
- middle_panel 区域切换构造（on_indicator_selected 收到带 region 的指标列表）
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock
from types import SimpleNamespace

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# conftest.py 将 gui.widgets / core.ui.panels 等注入 MagicMock（R256+ 为规避 Qt 硬崩溃）。
# 本测试需真实导入 middle_panel 与 indicator_mixin，故 pop 后重建（参照 test_r251 模式）。
_CONFTEST_MOCKS = [
    'gui.widgets',
    'core.ui',
    'core.ui.panels',
    'core.ui.panels.middle_panel',
    'core.ui.panels.base_panel',
]
for _mod in _CONFTEST_MOCKS:
    sys.modules.pop(_mod, None)


def make_kdata(n=200):
    rng = np.random.default_rng(42)
    close = np.cumsum(rng.standard_normal(n)) + 100
    open_ = close + rng.standard_normal(n) * 0.2
    high = np.maximum(open_, close) + rng.random(n) * 0.3
    low = np.minimum(open_, close) - rng.random(n) * 0.3
    volume = rng.integers(1000, 5000, n)
    return pd.DataFrame({
        'open': open_, 'high': high, 'low': low,
        'close': close, 'volume': volume,
    })


# ==================== 1. P0: 指标计算列污染回归 ====================

def test_talib_indicator_no_column_leak():
    """连续计算不同指标，结果列互不累积；原始 df 保持 5 列不被污染"""
    from core.indicator_service import calculate_indicator

    df = make_kdata()
    base_cols = list(df.columns)
    expected = {
        'KAMA': ['KAMA'],
        'MAMA': ['MAMA', 'MAMAFix'],
        'TEMA': ['TEMA'],
        'EMA': ['EMA'],
        'WMA': ['WMA'],
    }
    for name, params in [('KAMA', {'timeperiod': 10}), ('MAMA', {}),
                         ('TEMA', {'timeperiod': 30}), ('EMA', {'timeperiod': 30}),
                         ('WMA', {'timeperiod': 30})]:
        r = calculate_indicator(name, df, **params)
        cols = [c for c in r.columns if c not in base_cols]
        assert sorted(cols) == sorted(expected[name]), \
            f"{name} 结果列应为 {expected[name]}，实际 {cols}（存在跨指标列累积）"

    assert list(df.columns) == base_cols, "原始 kdata 被指标计算污染（原地添加列）"


def test_builtin_indicator_no_column_leak():
    """DB 有记录的指标（MACD）同样不污染传入 df"""
    from core.indicator_service import calculate_indicator

    df = make_kdata()
    base_cols = list(df.columns)
    r = calculate_indicator('MACD', df, fastperiod=12, slowperiod=26, signalperiod=9)
    cols = [c for c in r.columns if c not in base_cols]
    assert sorted(cols) == ['MACD', 'MACDHist', 'MACDSignal']
    assert list(df.columns) == base_cols


# ==================== 2. 渲染 region 路由 ====================

@pytest.fixture
def fake_chart():
    """模拟 ChartWidget（IndicatorMixin 挂载对象），3 轴布局（R283: 移除 indicator_ax2）"""
    import importlib
    indicator_mod = importlib.import_module('gui.widgets.chart_mixins.indicator_mixin')
    IndicatorMixin = indicator_mod.IndicatorMixin

    chart = SimpleNamespace()
    chart.price_ax = MagicMock()
    chart.volume_ax = MagicMock()
    chart.indicator_ax = MagicMock()
    chart.active_indicators = []
    chart.coordinator = None
    chart.theme_manager = MagicMock()
    chart.theme_manager.get_theme_colors.return_value = {
        'indicator_colors': ['#fbc02d', '#ab47bc', '#1976d2', '#43a047', '#e53935'],
    }
    chart._get_active_indicators = lambda: chart.active_indicators
    # 将 mixin 方法绑定到 fake 对象上
    chart._render_indicators = IndicatorMixin._render_indicators.__get__(chart)
    chart._get_indicator_style = IndicatorMixin._get_indicator_style.__get__(chart)
    return chart


def test_render_region_routing(fake_chart):
    """R283: 单指标区收敛——region 字段不再分流，MACD/RSI 全部落到 indicator_ax"""
    fake_chart.active_indicators = [
        {"name": "MACD", "params": {}, "group": "builtin", "region": "indicator1"},
        {"name": "RSI", "params": {"timeperiod": 14}, "group": "builtin", "region": "indicator1"},
    ]
    kdata = make_kdata()
    x = np.arange(len(kdata))
    fake_chart._render_indicators(kdata, x=x)

    # indicator_ax 应收到 MACD 两条线（MACD + Signal）+ RSI 一条线
    ind1_plots = [c.args for c in fake_chart.indicator_ax.plot.call_args_list]
    assert len(ind1_plots) >= 3, "指标区应绘制 MACD + Signal + RSI 共 3 条线"


def test_render_kama_mama_tema_independent(fake_chart):
    """KAMA/MAMA/TEMA 渲染互不干扰：全部落在 indicator_ax（R283: 单指标区）"""
    fake_chart.active_indicators = [
        {"name": "KAMA", "params": {"timeperiod": 10}, "group": "talib", "region": "indicator1"},
        {"name": "MAMA", "params": {}, "group": "talib", "region": "indicator1"},
        {"name": "TEMA", "params": {"timeperiod": 30}, "group": "talib", "region": "indicator1"},
    ]
    kdata = make_kdata()
    x = np.arange(len(kdata))
    fake_chart._render_indicators(kdata, x=x)

    ind1_labels = [c.kwargs.get('label', '') for c in fake_chart.indicator_ax.plot.call_args_list]
    assert any('KAMA' in lb for lb in ind1_labels), "指标区应含 KAMA 线"
    assert any('TEMA' in lb for lb in ind1_labels), "指标区应含 TEMA 线"
    assert any('MAMA' in lb for lb in ind1_labels), "指标区应含 MAMA 线"
    assert any('MAMAFix' in lb for lb in ind1_labels), "指标区应含 MAMAFix 线"


# ==================== 3. middle_panel 指标列表与区域切换 ====================

def _load_middle_panel_module():
    import importlib
    return importlib.import_module('core.ui.panels.middle_panel')


def test_all_indicator_names_list():
    """全量指标列表：内置 + TA-Lib 枚举去重，必须含 KAMA/MAMA/TEMA/MA/MACD/KDJ"""
    mod = _load_middle_panel_module()
    obj = SimpleNamespace(_BUILTIN_LIST=mod.MiddlePanel._BUILTIN_LIST)
    names = mod.MiddlePanel._get_all_indicator_names(obj)
    assert isinstance(names, list) and len(names) >= 59, f"指标列表过短: {len(names)}"
    assert len(set(names)) == len(names), "指标列表存在重复"
    for required in ['KAMA', 'MAMA', 'TEMA', 'MA', 'MACD', 'KDJ', 'RSI', 'BBANDS']:
        assert required in names, f"指标列表缺少 {required}"


def test_region_indicator_changed_builds_region_list():
    """R283: 单指标区切换——on_indicator_selected 收到带 region='indicator1' 的指标列表"""
    mod = _load_middle_panel_module()

    chart_widget = SimpleNamespace()
    chart_widget.on_indicator_selected = MagicMock()

    combos = {'indicator1_combo': SimpleNamespace(currentText=lambda: 'MACD')}

    panel = SimpleNamespace(
        _BUILTIN_INDICATORS=mod.MiddlePanel._BUILTIN_INDICATORS,
        _TALIB_DEFAULT_PARAMS=mod.MiddlePanel._TALIB_DEFAULT_PARAMS,
        _indicator_region_map={},  # R282: 区域归属映射（状态字段）
        _indicator_user_params={},  # R282: 用户自定义参数持久化
    )
    canvas = SimpleNamespace(chart_widget=chart_widget)
    panel.get_widget = lambda k: {'chart_canvas': canvas}.get(k, combos.get(k))

    mod.MiddlePanel._on_region_indicator_changed(panel, 'MACD')

    indicator_list = chart_widget.on_indicator_selected.call_args.args[0]
    regions = [(ind['name'], ind['region']) for ind in indicator_list]
    assert ('MACD', 'indicator1') in regions
    for ind in indicator_list:
        assert ind['group'] in ('builtin', 'talib')
        assert ind['params'] is not None


def test_region_indicator_none_clears_region():
    """选择"无"清空指标区（指标列表为空，移除历史归属）"""
    mod = _load_middle_panel_module()

    chart_widget = SimpleNamespace()
    chart_widget.on_indicator_selected = MagicMock()

    combos = {'indicator1_combo': SimpleNamespace(currentText=lambda: '无')}
    panel = SimpleNamespace(
        _BUILTIN_INDICATORS=mod.MiddlePanel._BUILTIN_INDICATORS,
        _TALIB_DEFAULT_PARAMS=mod.MiddlePanel._TALIB_DEFAULT_PARAMS,
        _indicator_region_map={'MACD': 'indicator1'},  # R282: 区域归属映射（状态字段）
        _indicator_user_params={},  # R282: 用户自定义参数持久化
    )
    canvas = SimpleNamespace(chart_widget=chart_widget)
    panel.get_widget = lambda k: {'chart_canvas': canvas}.get(k, combos.get(k))

    mod.MiddlePanel._on_region_indicator_changed(panel, '无')

    indicator_list = chart_widget.on_indicator_selected.call_args.args[0]
    assert len(indicator_list) == 0, "选择'无'应清空全部指标"
    assert panel._indicator_region_map == {}, "清空区域后应移除历史归属"
