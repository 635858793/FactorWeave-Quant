#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HV6 测试：tick 增量渲染性能日志（R292-HV6 性能采样扩展）

背景：核心增量渲染分支（_handle_realtime_tick / _update_last_bar_with_tick /
_append_new_bar）需要详细性能日志记录每次 tick 处理的耗时，便于排查瓶颈：
- 实例级 _tick_perf_stats（惰性初始化）：bar 内 tick / 新 bar / 子阶段 / 退化全量计数
- 慢 tick 告警：单次 > 33ms → logger.warning（[PERF][TickIncremental] 前缀）
- 聚合日志节流：每 60 次 bar 内 tick 打一条均值/最大/阶段平均日志

覆盖：
1. bar 内 tick：_tick_perf_stats 计数/总耗时/最大耗时 + 各子阶段耗时正确累计
2. symbol 不匹配提前 return 路径不打点（_tick_perf_stats 不初始化）
3. 新 bar（跨周期）路径：newbar_count +1 / total / max 累计
4. 慢 tick（>33ms 阈值，测试降为 0 触发）→ logger.warning 含 '慢tick'
5. 60 次节流聚合日志（logger.info 含 'bar内tick 60次'）
6. 退化全量路径：fallback_count +1（增量失败 → update_chart 全量）
"""
import os
import sys
import importlib.util
import logging

import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# 与 test_r267_tick_incremental 同款 dummy 模块注册（conftest 已把 gui.widgets.* mock 化）
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
from matplotlib.collections import PolyCollection, LineCollection  # noqa: E402

from loguru import logger  # noqa: E402

CHART_MIXINS = os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins')


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(CHART_MIXINS, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


render_mod = _load_module('rendering_mixin_perf_mod', 'rendering_mixin.py')

KLINE_KEYS = ['up', 'down', 'limit_up', 'limit_down',
              'shadow_up', 'shadow_down', 'shadow_limit_up', 'shadow_limit_down']
VOLUME_KEYS = ['up', 'down', 'limit_up', 'limit_down']


def make_kdata(n, symbol='300994'):
    """构造含 symbol/datetime 列的 K 线 DataFrame（与既有 r267 测试同款数据）"""
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
    df.iat[n - 1, df.columns.get_loc('close')] = df['open'].iloc[-1] + 0.5
    df.iat[n - 1, df.columns.get_loc('high')] = df['open'].iloc[-1] + 0.6
    df.iat[n - 1, df.columns.get_loc('low')] = df['open'].iloc[-1] - 0.1
    return df


class _StubRenderer:
    """最小 renderer 桩：build_*_groups 返回正确形状 verts/segments（无需真实绘图链）"""

    @staticmethod
    def build_candle_groups(data, xvals, is_limit_up, is_limit_down):
        xs = np.asarray(xvals, dtype=float)
        verts = [[(x - 0.3, 0.0), (x - 0.3, 1.0), (x + 0.3, 1.0), (x + 0.3, 0.0)] for x in xs]
        segs = [[(x, 0.0), (x, 1.0)] for x in xs]
        return verts, [], [], [], segs, [], [], []

    @staticmethod
    def build_volume_groups(data, xvals):
        xs = np.asarray(xvals, dtype=float)
        verts = [[(x - 0.3, 0.0), (x - 0.3, 1.0), (x + 0.3, 1.0), (x + 0.3, 0.0)] for x in xs]
        return verts, [], [], []


class _LoguruToStdlib(logging.Handler):
    """loguru → stdlib logging 桥接（caplog 捕获 loguru 日志的前提，官方推荐做法）"""

    def emit(self, record):
        logging.getLogger(record.name).handle(record)


@pytest.fixture(autouse=True)
def _bridge_loguru(caplog):
    """把 loguru 日志转发到 stdlib logging，使 caplog 可捕获 [PERF][TickIncremental] 日志"""
    caplog.set_level(logging.DEBUG)
    sink_id = logger.add(_LoguruToStdlib(), level='DEBUG')
    yield
    logger.remove(sink_id)


def _make_widget(kdata):
    """构造最小 RenderingMixin 实例（__new__ 绕过 __init__ + 注入增量依赖）"""
    w = render_mod.RenderingMixin.__new__(render_mod.RenderingMixin)
    w.current_kdata = kdata
    w._full_kdata = kdata.copy()
    # shadow 集合用 LineCollection（set_segments），柱体集合用 PolyCollection（set_verts），与真实渲染链一致
    w._kline_collections = {
        k: (LineCollection([]) if k.startswith('shadow') else PolyCollection([]))
        for k in KLINE_KEYS}
    w._volume_collections = {k: PolyCollection([]) for k in VOLUME_KEYS}
    w._ymin = 0.0
    w._ymax = 1.0
    w.chart_type = 'K线图'
    w.current_period = '1min'
    w.current_stock = '300994'
    w.renderer = _StubRenderer()
    engine = MagicMock()
    engine.render.return_value = True
    w._blit_engine = engine
    return w


_BAR_TICK = {'symbol': '300994', 'price': 0.5, 'volume': 100,
             'timestamp': '2024-01-01 09:31:00'}


class TestTickPerfStats:
    """_tick_perf_stats 计数/耗时累计"""

    def test_bar_tick_stats_accumulate(self):
        w = _make_widget(make_kdata(200))
        for _ in range(3):
            assert w._update_last_bar_with_tick(_BAR_TICK) is True
        stats = w._tick_perf_stats
        assert stats['bar_count'] == 3, "3 次 bar 内 tick 应累计 bar_count=3"
        assert stats['bar_total_ms'] > 0, "总耗时应 > 0"
        assert stats['bar_max_ms'] > 0, "最大耗时应 > 0"
        # 各子阶段（数据更新 / K 线重建 / 成交量重建 / blit）均应有真实耗时
        for key in ('stage_data_ms', 'stage_kline_ms', 'stage_volume_ms', 'stage_blit_ms'):
            assert stats[key] > 0, f"{key} 应累计耗时 > 0"

    def test_symbol_mismatch_no_stats(self):
        """symbol 不匹配提前 return：不打点、不初始化统计字典"""
        w = render_mod.RenderingMixin.__new__(render_mod.RenderingMixin)
        w.current_stock = '300994'
        w.chart_type = 'K线图'
        w._handle_realtime_tick({
            'symbol': '600000', 'price': 999.0, 'volume': 10,
            'timestamp': '2024-01-01 09:31:00'})
        assert not hasattr(w, '_tick_perf_stats'), \
            "symbol 不匹配应提前 return，_tick_perf_stats 不应被初始化"

    def test_new_bar_stats_accumulate(self):
        """tick 时间戳跨周期桶 → _append_new_bar → newbar 计数/耗时累计"""
        w = _make_widget(make_kdata(5))
        w.update_chart = MagicMock()
        w._handle_realtime_tick({
            'symbol': '300994', 'price': 100.0, 'volume': 10,
            'timestamp': '2024-01-01 10:00:00'})  # 09:34 之后 → 跨分钟周期
        stats = w._tick_perf_stats
        assert stats['newbar_count'] == 1, "新 bar 路径 newbar_count 应 +1"
        assert stats['newbar_total_ms'] > 0
        assert stats['newbar_max_ms'] > 0
        assert stats['bar_count'] == 0, "新 bar 路径不应计入 bar 内 tick"
        w.update_chart.assert_called_once()

    def test_fallback_count_on_degraded(self):
        """增量失败（price 缺失）→ 退化全量 → fallback_count +1"""
        w = _make_widget(make_kdata(200))
        w._full_kdata = None  # 退化分支 `_full_kdata or kdata` 中 DataFrame bool 会抛错（原行为），置 None 走 kdata 全量
        w.update_chart = MagicMock()
        w._handle_realtime_tick({
            'symbol': '300994', 'volume': 10,
            'timestamp': '2024-01-01 09:31:00'})  # 无 price → 无法增量
        stats = w._tick_perf_stats
        assert stats['fallback_count'] == 1, "退化全量路径 fallback_count 应 +1"
        assert stats['bar_count'] == 0, "失败增量不应计入 bar 内 tick"
        w.update_chart.assert_called_once()


class TestTickPerfLogs:
    """慢 tick 告警与聚合日志节流（caplog 捕获 loguru）"""

    def test_slow_tick_warns(self, caplog):
        w = _make_widget(make_kdata(200))
        w.SLOW_TICK_MS = 0.0  # 阈值降为 0：任何一次 bar 内 tick 都超阈值
        assert w._update_last_bar_with_tick(_BAR_TICK) is True
        msgs = [r.message for r in caplog.records if r.levelname == 'WARNING']
        assert any('[PERF][TickIncremental]' in m and ('慢tick' in m or 'slow' in m.lower())
                   for m in msgs), f"应触发慢 tick 告警（[PERF][TickIncremental] 前缀 + 慢tick），实际: {msgs}"

    def test_agg_log_after_60_ticks(self, caplog):
        w = _make_widget(make_kdata(50))
        for _ in range(60):
            assert w._update_last_bar_with_tick(_BAR_TICK) is True
        stats = w._tick_perf_stats
        assert stats['bar_count'] == 60
        assert stats['agg_count'] == 0, "聚合日志输出后节流窗口应重置"
        msgs = [r.message for r in caplog.records if r.levelname == 'INFO']
        assert any('[PERF][TickIncremental]' in m and 'bar内tick 60次' in m and '阶段avg' in m
                   for m in msgs), f"60 次后应输出聚合日志（bar内tick 60次），实际: {msgs[-3:]}"
