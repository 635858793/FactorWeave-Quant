#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R292-HV 测试：涨跌停四色判定前置到降采样前（高价值修复）

背景（P0 正确性 / P1 一致性）：
1. K线涨跌停四色判定在降采样之后执行，昨收取错：
   - rendering_mixin.update_chart 中 _downsample_kdata 早于渲染；
   - chart_renderer._get_view_data/_downsample_data 二次降采样后仍重判；
   - 降采样后"前一根"并非真实前一交易日 → 涨停/跌停价错位 → 四色漏判。
2. 美国线（OHLC Bar）仅两色，无涨停橙/跌停紫。

修复方案：在降采样前用全量数据计算 limit 掩码 → 附加为 limit_up/limit_down
布尔列 → 随降采样切片保留 → 渲染路径（传统K线/美国线/WebGPU GPU/CPU降级）
优先读取该列；列缺失时回退内部按板块判定（兼容直接传数据的调用方）。

覆盖：
① 降采样后 limit 列随切片保留且与全量判定一致（>1200 条仍命中四色）
② 美国线四色（limit_up_color/limit_down_color 生效）
③ 列优先读取（数据带 limit 列时不再调用 classify_limit_up_down）
④ 无 limit 列时回退兼容（内部判定仍四色）
"""
import os
import sys
import importlib.util

import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

import matplotlib.colors as mcolors
from matplotlib.collections import PolyCollection, LineCollection

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# R267 同款：conftest 已把 gui.widgets 注册为 MagicMock（无 __path__），
# 先注册 dummy 模块满足 chart_mixins 内部相对导入，再加载真实文件。
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

from core.rendering.limit_price import classify_limit_up_down, extract_symbol  # noqa: E402
from optimization.chart_renderer import ChartRenderer  # noqa: E402

STYLE = {
    'up_color': '#e74c3c', 'down_color': '#27ae60',
    'limit_up_color': '#ff9800', 'limit_down_color': '#ab47bc',
    'volume_up_color': '#e74c3c', 'volume_down_color': '#27ae60', 'alpha': 1.0,
}

# 创业板(300750, 20%)：row0 阳线红 / row1 涨停橙(11.00x1.2=13.20) /
# row2 跌停紫(13.20x0.8=10.56) / row3 涨停橙(10.56x1.2=12.67) / row4 阴线绿
KLINE_ROWS = {
    'symbol': ['300750'] * 5,
    'open': [10.0, 11.0, 13.2, 10.56, 13.0],
    'high': [11.0, 13.2, 13.2, 12.67, 13.1],
    'low': [9.9, 11.0, 10.56, 11.5, 11.9],
    'close': [11.0, 13.2, 10.56, 12.67, 12.0],
    'volume': [1000] * 5,
}
EXPECT_ROW_COLORS = ['#e74c3c', '#ff9800', '#ab47bc', '#ff9800', '#27ae60']


def make_kline_df(with_limit_cols=False):
    """构造 5 根创业板 K 线；with_limit_cols=True 时附加预计算的 limit 列"""
    df = pd.DataFrame(KLINE_ROWS)
    if with_limit_cols:
        lu, ld = classify_limit_up_down(
            df['close'].values.astype(float), df['high'].values.astype(float),
            df['low'].values.astype(float), '300750')
        df['limit_up'] = lu
        df['limit_down'] = ld
    return df


def make_kdata(n, symbol='600519'):
    """主板(10%)随机走势 K 线，尾部确定性构造 涨停→跌停→涨停→跌停：
    昨收 10.00 → 11.00 涨停(high=11.00) → 9.90 跌停(low=9.90) →
    10.89 涨停(high=10.89) → 9.80 跌停(low=9.80)（10.89x0.9=9.80）
    """
    rng = np.random.default_rng(42)
    close = np.cumsum(rng.standard_normal(n)) + 100
    open_ = close + rng.standard_normal(n) * 0.5
    high = np.maximum(open_, close) + rng.random(n)
    low = np.minimum(open_, close) - rng.random(n)
    volume = rng.integers(1000, 10000, n)
    close[-5] = 10.00; open_[-5] = 10.00; high[-5] = 10.00; low[-5] = 10.00
    close[-4] = 11.00; open_[-4] = 10.50; high[-4] = 11.00; low[-4] = 10.50   # 涨停
    close[-3] = 9.90; open_[-3] = 10.50; high[-3] = 10.50; low[-3] = 9.90     # 跌停
    close[-2] = 10.89; open_[-2] = 10.00; high[-2] = 10.89; low[-2] = 10.00   # 涨停
    close[-1] = 9.80; open_[-1] = 10.00; high[-1] = 10.00; low[-1] = 9.80     # 跌停
    return pd.DataFrame({
        'symbol': [symbol] * n,
        'open': open_, 'high': high, 'low': low, 'close': close, 'volume': volume,
        'datetime': pd.date_range('2024-01-01', periods=n, freq='D'),
    })


class _ChartWidget(render_mod.RenderingMixin, ind_mod.IndicatorMixin,
                   util_mod.UtilityMixin):
    """组合 mixin，模拟 ChartWidget 的 MRO"""


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
    w._optimize_display = MagicMock()
    w.close_loading_dialog = MagicMock()
    w._invalidate_crosshair_background = MagicMock()
    w.show_no_data = MagicMock()
    w._safe_format_date = MagicMock(return_value='2024-01-01')
    w._get_chart_style = MagicMock(return_value={})
    w.current_stock = '600519'
    return w


def _full_limits(df):
    """全量 limit 掩码（位置对齐的 numpy bool 数组）"""
    return classify_limit_up_down(
        df['close'].values.astype(float), df['high'].values.astype(float),
        df['low'].values.astype(float), extract_symbol(df))


# ==================== ① 降采样后 limit 列随切片保留且与全量判定一致 ====================

class TestLimitMaskBeforeDownsample:
    def test_large_data_limit_columns_preserved_consistent(self):
        """>1200 条：分桶采样后 limit 列随行保留，值与全量同索引行一致"""
        w = _make_widget()
        w.update_chart({'kdata': make_kdata(1500)})
        cur = w.current_kdata
        full = w._full_kdata
        assert 'limit_up' in cur.columns and 'limit_down' in cur.columns
        assert len(cur) <= 1200
        # 分桶代表性行选择不重判：每行 limit 值 = 全量同索引行（铁律⑲/㉑）
        idx = cur.index.to_numpy()
        lu, ld = _full_limits(full)
        assert (cur['limit_up'].to_numpy() == lu[idx]).all()
        assert (cur['limit_down'].to_numpy() == ld[idx]).all()
        assert cur['limit_up'].sum() >= 1 and cur['limit_down'].sum() >= 1

    def test_large_data_hits_four_color(self):
        """>1200 条分桶采样后仍命中涨停橙/跌停紫（HV4：涨跌停行必被保留）"""
        w = _make_widget()
        w.update_chart({'kdata': make_kdata(1500)})
        cur = w.current_kdata
        assert cur['limit_up'].sum() >= 1
        assert cur['limit_down'].sum() >= 1
        # 分桶"涨跌停优先"规则：尾部确定性涨跌停 bar（1496/1497/1498）必被保留
        idx_set = set(cur.index.tolist())
        assert 1496 in idx_set, f'涨停 bar 1496 应被保留: {sorted(idx_set)[-8:]}'
        assert 1497 in idx_set, f'跌停 bar 1497 应被保留: {sorted(idx_set)[-8:]}'

    def test_small_data_limit_columns(self):
        """≤1200 条（不降采样）：limit 列同样存在且判定正确"""
        w = _make_widget()
        w.update_chart({'kdata': make_kdata(365)})
        cur = w.current_kdata
        assert 'limit_up' in cur.columns
        # 尾部 5 根全保留：362 跌停 / 363 涨停 / 364 跌停
        assert cur['limit_down'].iloc[-3]
        assert cur['limit_up'].iloc[-2]
        assert cur['limit_down'].iloc[-1]

    def test_update_chart_column_priority(self):
        """数据自带 limit 列时，update_chart 不再调用 classify_limit_up_down"""
        df = make_kdata(1500)
        lu, ld = _full_limits(df)
        df['limit_up'] = lu
        df['limit_down'] = ld
        w = _make_widget()
        with patch.object(render_mod, 'classify_limit_up_down',
                          side_effect=AssertionError('数据已带limit列，不应重算')) as m:
            w.update_chart({'kdata': df})
        assert not m.called
        idx = w.current_kdata.index.to_numpy()
        assert (w.current_kdata['limit_up'].to_numpy() == lu[idx]).all()

    def test_rerender_reuses_existing_columns(self):
        """重渲染（_full_kdata 已带 limit 列）：直接复用不重算"""
        w = _make_widget()
        w.update_chart({'kdata': make_kdata(1500)})
        with patch.object(render_mod, 'classify_limit_up_down',
                          side_effect=AssertionError('不应重算')):
            w.on_indicator_selected(['MA'])
        assert 'limit_up' in w.current_kdata.columns
        assert w.current_kdata['limit_up'].sum() >= 1


# ==================== ② 美国线（OHLC Bar）四色 ====================

class TestOchlBarsFourColor:
    def _vline_colors(self, ax):
        return [call.kwargs['colors'] for call in ax.vlines.call_args_list]

    def test_four_colors_with_limit_columns(self):
        """带 limit 列：涨停橙/跌停紫/涨红/跌绿 依次生效"""
        w = _make_widget()
        ax = MagicMock()
        w._render_ohlc_bars(ax, make_kline_df(with_limit_cols=True),
                            STYLE, np.arange(5))
        assert self._vline_colors(ax) == EXPECT_ROW_COLORS

    def test_four_colors_fallback_no_columns(self):
        """无 limit 列：内部按板块判定，仍四色（兼容直接传数据的调用方）"""
        w = _make_widget()
        ax = MagicMock()
        w._render_ohlc_bars(ax, make_kline_df(with_limit_cols=False),
                            STYLE, np.arange(5))
        assert self._vline_colors(ax) == EXPECT_ROW_COLORS

    def test_column_priority_skips_classify(self):
        """带 limit 列时不再调用 classify_limit_up_down"""
        w = _make_widget()
        ax = MagicMock()
        with patch.object(render_mod, 'classify_limit_up_down',
                          side_effect=AssertionError('数据已带limit列，不应重判')):
            w._render_ohlc_bars(ax, make_kline_df(with_limit_cols=True),
                                STYLE, np.arange(5))
        assert self._vline_colors(ax) == EXPECT_ROW_COLORS


# ==================== ③ 渲染路径列优先读取 ====================

def _patch_edge_colors(ax):
    """按 add_collection 顺序提取 PolyCollection 的 edgecolor（每蜡烛一行）。
    标量颜色时 get_edgecolor() 仅 1 行（图元共享），需按路径数展开。"""
    out = []
    for call in ax.add_collection.call_args_list:
        coll = call[0][0]
        if isinstance(coll, PolyCollection):
            colors = coll.get_edgecolor()
            n = len(coll.get_paths())
            for i in range(n):
                out.append(mcolors.to_hex(tuple(np.round(colors[i % len(colors)], 3))))
    return out


def _line_colors(ax):
    """按 add_collection 顺序提取 LineCollection 的 colors（按段数展开）"""
    out = []
    for call in ax.add_collection.call_args_list:
        coll = call[0][0]
        if isinstance(coll, LineCollection):
            colors = coll.get_colors()
            n = len(coll.get_segments())
            for i in range(n):
                out.append(mcolors.to_hex(tuple(np.round(colors[i % len(colors), :3], 3))))
    return out


class TestRenderColumnPriority:
    """数据带 limit 列时，K 线渲染路径跳过内部重判
    （WebGPU 假实现已删除，原 WebGPURenderer GPU/CPU-fallback 列优先用例
    迁移至 optimization/chart_renderer.py _render_candlesticks_efficient）"""

    def test_chart_renderer_column_priority(self):
        r = ChartRenderer.__new__(ChartRenderer)
        ax = MagicMock()
        with patch('optimization.chart_renderer.classify_limit_up_down',
                   side_effect=AssertionError('数据已带limit列，不应重判')):
            r._render_candlesticks_efficient(
                ax, make_kline_df(with_limit_cols=True), STYLE,
                np.arange(5), use_datetime_axis=False)
        # 集合添加顺序：up(1) / down(1) / limit_up(2) / limit_down(1)
        assert _patch_edge_colors(ax) == [
            '#e74c3c', '#27ae60', '#ff9800', '#ff9800', '#ab47bc']

    def test_cpu_render_column_priority(self):
        """原 WebGPURenderer GPU/CPU-fallback 列优先用例迁移：
        统一由 _render_candlesticks_efficient 承担，带 limit 列时跳过内部重判"""
        r = ChartRenderer.__new__(ChartRenderer)
        ax = MagicMock()
        with patch('optimization.chart_renderer.classify_limit_up_down',
                   side_effect=AssertionError('数据已带limit列，不应重判')):
            r._render_candlesticks_efficient(
                ax, make_kline_df(with_limit_cols=True), STYLE,
                np.arange(5), use_datetime_axis=False)
        assert _patch_edge_colors(ax) == [
            '#e74c3c', '#27ae60', '#ff9800', '#ff9800', '#ab47bc']

    def test_cpu_render_fallback_compat(self):
        """原 WebGPURenderer GPU/CPU-fallback 回退兼容用例迁移：
        无 limit 列时内部按板块判定，仍输出四色"""
        r = ChartRenderer.__new__(ChartRenderer)
        ax = MagicMock()
        r._render_candlesticks_efficient(
            ax, make_kline_df(with_limit_cols=False), STYLE,
            np.arange(5), use_datetime_axis=False)
        assert _patch_edge_colors(ax) == [
            '#e74c3c', '#27ae60', '#ff9800', '#ff9800', '#ab47bc']


# ==================== ④ 无 limit 列时回退兼容 ====================

class TestRenderFallbackCompat:
    """无 limit 列时各路径回退内部按板块判定，仍输出四色"""

    def test_chart_renderer_fallback(self):
        r = ChartRenderer.__new__(ChartRenderer)
        ax = MagicMock()
        r._render_candlesticks_efficient(
            ax, make_kline_df(with_limit_cols=False), STYLE,
            np.arange(5), use_datetime_axis=False)
        assert _patch_edge_colors(ax) == [
            '#e74c3c', '#27ae60', '#ff9800', '#ff9800', '#ab47bc']

    def test_webgpu_gpu_fallback(self):
        """原 WebGPURenderer GPU 回退兼容用例迁移：
        WebGPU 假实现已删除，回退兼容由 _render_candlesticks_efficient 承担
        （无 limit 列时内部按板块判定，仍输出四色）"""
        r = ChartRenderer.__new__(ChartRenderer)
        ax = MagicMock()
        r._render_candlesticks_efficient(
            ax, make_kline_df(with_limit_cols=False), STYLE,
            np.arange(5), use_datetime_axis=False)
        assert _patch_edge_colors(ax) == [
            '#e74c3c', '#27ae60', '#ff9800', '#ff9800', '#ab47bc']

    def test_webgpu_cpu_fallback(self):
        """原 WebGPURenderer CPU fallback 用例迁移：
        影线按类着色由 _render_candlesticks_efficient 承担"""
        r = ChartRenderer.__new__(ChartRenderer)
        ax = MagicMock()
        r._render_candlesticks_efficient(
            ax, make_kline_df(with_limit_cols=False), STYLE,
            np.arange(5), use_datetime_axis=False)
        assert _line_colors(ax) == [
            '#e74c3c', '#27ae60', '#ff9800', '#ff9800', '#ab47bc']

    def test_no_symbol_column_fallback(self):
        """无 symbol 列（extract_symbol 返回空 → 按主板 10%）不抛异常"""
        df = make_kline_df(with_limit_cols=False).drop(columns=['symbol'])
        w = _make_widget()
        ax = MagicMock()
        w._render_ohlc_bars(ax, df, STYLE, np.arange(5))
        assert len(ax.vlines.call_args_list) == 5


# ==================== ⑤ R292-HV4 分桶采样保留关键形态 ====================

def _bucket_df(n, seed=7, monotone=False):
    """采样测试数据；monotone=True 时 high 单调递增/low 单调递减（峰谷可预期）"""
    rng = np.random.default_rng(seed)
    if monotone:
        return pd.DataFrame({
            'open': np.arange(n, dtype=float),
            'high': np.arange(n, dtype=float) + 1,
            'low': np.arange(n, dtype=float) - 1,
            'close': np.arange(n, dtype=float),
            'volume': rng.integers(1000, 10000, n)})
    close = np.cumsum(rng.standard_normal(n)) + 100
    return pd.DataFrame({
        'open': close,
        'high': np.maximum(close, close + 0.5) + rng.random(n),
        'low': np.minimum(close, close + 0.5) - rng.random(n),
        'close': close,
        'volume': rng.integers(1000, 10000, n)})


class TestBucketSamplingKeyShape:
    """R292-HV4：分桶代表性行采样（_bucket_key_indices）——
    每桶保留峰(最高价)+谷(最低价)，桶内涨跌停追加（P0 四色），首尾强制保留
    （替代等距 linspace 抽行：后者丢失桶内极值/涨跌停/巨量 bar）"""

    def test_bucket_preserves_peak_and_valley(self):
        """单调数据下每桶峰(桶尾)+谷(桶首)行必被保留（价格形态不丢）"""
        df = _bucket_df(100, monotone=True)
        idx = util_mod._bucket_key_indices(df, 10)  # num_buckets=4 → 每桶 25 行
        kept = set(idx.tolist())
        expected = {0, 24, 25, 49, 50, 74, 75, 99}
        assert expected <= kept, f'峰谷未保留: {sorted(expected - kept)}'

    def test_bucket_appends_limit_rows(self):
        """桶内含涨跌停（非峰非谷）时追加保留（P0 四色不因降采样丢失）"""
        df = _bucket_df(100)
        df['limit_up'] = False
        df['limit_down'] = False
        df.loc[10, 'limit_up'] = True    # 桶[0,25) 内非峰非谷
        df.loc[20, 'limit_down'] = True
        idx = set(util_mod._bucket_key_indices(df, 10).tolist())
        assert 10 in idx and 20 in idx

    def test_first_last_rows_always_kept(self):
        """走势连续性：首尾行强制保留"""
        for n in (1500, 50000):
            idx = util_mod._bucket_key_indices(_bucket_df(n), 1200)
            assert idx[0] == 0 and idx[-1] == n - 1

    def test_length_within_budget(self):
        """各规模采样结果不超预算（涨跌停桶追加行容忍 +2）"""
        df = _bucket_df(50000)
        df['limit_up'] = False
        df['limit_down'] = False
        df.loc[49996, 'limit_up'] = True
        idx = util_mod._bucket_key_indices(df, 1200)
        assert len(idx) <= 1202

    def test_50000_rows_sampling_fast(self):
        """5 万行采样耗时可控（<200ms 宽松阈值防 CI 抖动，实测 ~5ms）"""
        import time
        df = _bucket_df(50000)
        t0 = time.perf_counter()
        util_mod._bucket_key_indices(df, 1200)
        assert (time.perf_counter() - t0) * 1000 < 200

    def test_minute_path_uses_bucket_sampling(self):
        """分钟数据路径：按交易日分组桶采样，总行数 ≤ 预算且每交易日保留细节"""
        w = _make_widget()
        w._is_minute_frequency = lambda kdata: True
        # 10 分钟频率 1500 根 → 连续 ~10.4 个自然日 → 11 个分组
        df = _bucket_df(1500)
        df['datetime'] = pd.date_range('2024-01-02', periods=len(df), freq='10min')
        df['limit_up'] = False
        df['limit_down'] = False
        df.loc[1496, 'limit_up'] = True  # 尾桶涨跌停
        df.loc[1497, 'limit_down'] = True
        out = w._downsample_kdata(df, 1200)
        assert len(out) <= 1200
        # 每交易日至少保留 per_day(≥2) 根 → 总行数显著小于全量
        assert len(out) < len(df)
        # limit 列随行保留（铁律⑲/㉑：不重判）
        assert 1496 in out.index and 1497 in out.index
        assert out.loc[1496, 'limit_up'] and not out.loc[1496, 'limit_down']
        assert out.loc[1497, 'limit_down'] and not out.loc[1497, 'limit_up']
