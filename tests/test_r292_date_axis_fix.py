#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R292 测试：坐标轴/日期问题修复（第5轮）

覆盖：
- _coerce_to_datetime / _safe_format_date：int 日期（20240814）不再被解释为 1970-01-01
- _standardize_kdata_format：数值型 datetime 保护 + NaT 行清理
- _filter_dataframe_columns：双列并存时垃圾 timestamp 被真实 datetime 覆盖
- _incremental_fill_kdata：日线按日期粒度去重（同日不同时不再堆积）
- WebGPURenderer CPU 降级渲染支持外部 x 参数

根因背景：a) 分钟K线曾以 frequency='1d' 落库，日线视图混入分钟行 →
"数据很多但日期都集中"；b) 渐进式加载 update_basic_kdata 对 datetime 轴设置
mdates.date2num xlim（73万级）而蜡烛画在 arange 序号 → 坐标轴错位；
c) pd.to_datetime(int) 按纳秒解释 → 1970-01-01。
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

# conftest.py 在模块层 mock 了 'gui.widgets'（无 __path__），pytest 下直接
# `from gui.widgets.chart_mixins.utility_mixin import ...` 会报 "is not a package"。
# 此处临时移除 mock，用 importlib 按文件加载（跳过 chart_mixins/__init__.py 的
# 全量 mixin 导入），完成后恢复 mock 以保护其他测试。
_saved_gui_widgets = sys.modules.pop('gui.widgets', None)


def _load_module_from_file(mod_name, file_path):
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# 预注册 chart_mixins 为最小包，避免执行 __init__.py 的全量 mixin 导入
_chart_mixins_pkg = types.ModuleType('gui.widgets.chart_mixins')
_chart_mixins_pkg.__path__ = [
    os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins')]
sys.modules['gui.widgets.chart_mixins'] = _chart_mixins_pkg

_load_module_from_file(
    'gui.widgets.chart_mixins.ui_mixin',
    os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins', 'ui_mixin.py'))
_load_module_from_file(
    'gui.widgets.chart_mixins.utility_mixin',
    os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins', 'utility_mixin.py'))

from gui.widgets.chart_mixins.utility_mixin import UtilityMixin

# 恢复 conftest 的 mock，避免影响其他测试
if _saved_gui_widgets is not None:
    sys.modules['gui.widgets'] = _saved_gui_widgets


class TestCoerceToDatetime:
    """int/float 日期不再被解释为 1970 纳秒时间戳"""

    def test_int_yyyymmdd(self):
        ts = UtilityMixin._coerce_to_datetime(20240814)
        assert ts is not None and ts.strftime('%Y-%m-%d') == '2024-08-14'

    def test_float_yyyymmdd(self):
        ts = UtilityMixin._coerce_to_datetime(20240814.0)
        assert ts is not None and ts.strftime('%Y-%m-%d') == '2024-08-14'

    def test_int_yyyymm(self):
        ts = UtilityMixin._coerce_to_datetime(202408)
        assert ts is not None and ts.strftime('%Y-%m') == '2024-08'

    def test_unix_seconds(self):
        ts = UtilityMixin._coerce_to_datetime(1723622400)  # 2024-08-14 00:00:00 UTC
        assert ts is not None and ts.year == 2024

    def test_plain_index_number_returns_none(self):
        # 普通 RangeIndex 数字（0/5/100）不应被当作日期 → 走调用方兜底
        assert UtilityMixin._coerce_to_datetime(5) is None
        assert UtilityMixin._coerce_to_datetime(0) is None

    def test_str_date(self):
        ts = UtilityMixin._coerce_to_datetime('2024-08-14')
        assert ts is not None and ts.strftime('%Y-%m-%d') == '2024-08-14'

    def test_none_and_nan(self):
        assert UtilityMixin._coerce_to_datetime(None) is None
        assert UtilityMixin._coerce_to_datetime(np.nan) is None

    def test_bool_rejected(self):
        assert UtilityMixin._coerce_to_datetime(True) is None


class TestSafeFormatDate:
    """_safe_format_date 在 int datetime 列上输出真实日期而非 1970"""

    def _make(self):
        return UtilityMixin()

    def test_int_datetime_column(self):
        m = self._make()
        kdata = pd.DataFrame({'datetime': [20240814, 20240815], 'close': [1.0, 2.0]})
        assert m._safe_format_date(kdata.iloc[0], 0, kdata) == '2024-08-14'
        assert m._safe_format_date(kdata.iloc[1], 1, kdata) == '2024-08-15'

    def test_real_timestamp_column(self):
        m = self._make()
        kdata = pd.DataFrame({
            'datetime': pd.to_datetime(['2024-08-14 09:30:00', '2024-08-15 09:30:00']),
            'close': [1.0, 2.0]})
        assert m._safe_format_date(kdata.iloc[0], 0, kdata) == '2024-08-14'

    def test_int_index_fallback_date(self):
        # 无 datetime 列 + 数字索引 → 走兜底（2024-01-01 + idx），绝不输出 1970
        m = self._make()
        kdata = pd.DataFrame({'close': [1.0, 2.0]})
        assert m._safe_format_date(kdata.iloc[0], 0, kdata) == '2024-01-01'
        assert m._safe_format_date(kdata.iloc[1], 1, kdata) == '2024-01-02'


class TestStandardizeKdataFormat:
    """_standardize_kdata_format 数值型 datetime 保护 + NaT 清理"""

    def _make(self):
        from core.services.unified_data_manager import UnifiedDataManager
        return object.__new__(UnifiedDataManager)

    def _df(self, datetime_vals):
        return pd.DataFrame({
            'open': [1.0, 2.0], 'high': [2.0, 3.0], 'low': [0.5, 1.5],
            'close': [1.5, 2.5], 'volume': [100, 200],
            'datetime': datetime_vals,
        })

    def test_int_datetime_not_1970(self):
        udm = self._make()
        out = udm._standardize_kdata_format(self._df([20240814, 20240815]), 'TEST')
        got = pd.to_datetime(out['datetime']).dt.strftime('%Y-%m-%d').tolist()
        assert got == ['2024-08-14', '2024-08-15'], got

    def test_nat_rows_removed(self):
        udm = self._make()
        out = udm._standardize_kdata_format(
            self._df([pd.NaT, '2024-08-15']), 'TEST')
        assert len(out) == 1
        assert pd.to_datetime(out['datetime'].iloc[0]).strftime('%Y-%m-%d') == '2024-08-15'

    def test_normal_timestamp_preserved(self):
        udm = self._make()
        out = udm._standardize_kdata_format(
            self._df(pd.to_datetime(['2024-08-14', '2024-08-15'])), 'TEST')
        assert len(out) == 2


class TestFilterDataframeColumns:
    """双列并存时垃圾 timestamp 被真实 datetime 覆盖"""

    def _make(self):
        from core.asset_database_manager import AssetSeparatedDatabaseManager
        return object.__new__(AssetSeparatedDatabaseManager)

    def test_garbage_timestamp_overwritten(self):
        mgr = self._make()
        data = pd.DataFrame({
            'datetime': ['2024-08-14', '2024-08-15'],
            'timestamp': ['garbage', 'garbage'],
            'close': [1.0, 2.0],
        })
        out = mgr._filter_dataframe_columns(data, ['timestamp', 'close'])
        assert 'timestamp' in out.columns
        assert sorted(pd.to_datetime(out['timestamp']).dt.strftime('%Y-%m-%d').tolist()) == \
            ['2024-08-14', '2024-08-15']

    def test_good_timestamp_kept(self):
        mgr = self._make()
        data = pd.DataFrame({
            'datetime': ['2024-08-14'],
            'timestamp': ['2024-08-15'],
            'close': [1.0],
        })
        out = mgr._filter_dataframe_columns(data, ['timestamp', 'close'])
        assert 'timestamp' in out.columns and 'datetime' not in out.columns
        assert pd.to_datetime(out['timestamp'].iloc[0]).strftime('%Y-%m-%d') == '2024-08-15'

    def test_datetime_only_renamed(self):
        mgr = self._make()
        data = pd.DataFrame({'datetime': ['2024-08-14'], 'close': [1.0]})
        out = mgr._filter_dataframe_columns(data, ['timestamp', 'close'])
        assert 'timestamp' in out.columns
        assert pd.to_datetime(out['timestamp'].iloc[0]).strftime('%Y-%m-%d') == '2024-08-14'


class TestIncrementalFillKdata:
    """日线增量合并按日期粒度去重（同日不同时不再堆积）"""

    def _make(self):
        from core.services.unified_data_manager import UnifiedDataManager
        udm = object.__new__(UnifiedDataManager)
        udm._kdata_incremental_checked = {}
        udm._kdata_incremental_ttl = 3600
        udm._kdata_history_exhausted = {}
        return udm

    def _db_df(self):
        return pd.DataFrame({
            'datetime': pd.to_datetime(['2024-08-13 00:00:00', '2024-08-14 00:00:00']),
            'open': [1.0, 2.0], 'high': [2.0, 3.0], 'low': [0.5, 1.5],
            'close': [1.5, 2.5], 'volume': [100, 200],
            'symbol': ['T', 'T'], 'code': ['T', 'T'],
            'data_source': ['tet_plugin', 'tet_plugin'],
            'adj_type': ['none', 'none'],
        })

    def test_same_day_different_time_deduped(self):
        """新拉取行与 DB 同日不同时（00:00 vs 15:00）→ 不产生重复，不落库"""
        from core.plugin_types import AssetType
        udm = self._make()
        db_df = self._db_df()
        new_df = pd.DataFrame({
            'datetime': pd.to_datetime(['2024-08-14 15:00:00']),
            'open': [9.0], 'high': [10.0], 'low': [8.0], 'close': [9.5],
            'volume': [999],
        })
        with patch.object(udm, '_fetch_kdata_from_tet',
                          return_value=(new_df, 'tet_plugin')), \
             patch.object(udm, '_persist_kdata_to_duckdb',
                          return_value=True) as persist_mock:
            out = udm._incremental_fill_kdata('T', 'day', count=2, db_df=db_df,
                                              asset_type=AssetType.STOCK_A)
        # 同日 08-14 15:00 视为已存在 → all_new 空 → 返回 None 且不落库
        assert out is None
        persist_mock.assert_not_called()

    def test_new_date_appended_same_day_dropped(self):
        """新日期（08-15）追加；同日不同时（08-14 15:00）被去重只保留一行"""
        from core.plugin_types import AssetType
        udm = self._make()
        db_df = self._db_df()
        new_df = pd.DataFrame({
            'datetime': pd.to_datetime(['2024-08-14 15:00:00', '2024-08-15 00:00:00']),
            'open': [9.0, 10.0], 'high': [10.0, 11.0], 'low': [8.0, 9.0],
            'close': [9.5, 10.5], 'volume': [999, 1000],
            'data_source': ['tet_plugin', 'tet_plugin'],
        })
        with patch.object(udm, '_fetch_kdata_from_tet',
                          return_value=(new_df, 'tet_plugin')), \
             patch.object(udm, '_persist_kdata_to_duckdb',
                          return_value=True) as persist_mock:
            out = udm._incremental_fill_kdata('T', 'day', count=2, db_df=db_df,
                                              asset_type=AssetType.STOCK_A)
        assert out is not None
        dates = pd.to_datetime(out['datetime']).dt.strftime('%Y-%m-%d').tolist()
        assert dates == ['2024-08-13', '2024-08-14', '2024-08-15'], dates
        persist_mock.assert_called_once()


class TestCpuFallbackAcceptsX:
    """CPU/fallback 渲染路径支持外部 x（坐标轴一致性修复的接口部分；
    WebGPU 假实现已删除，外部 x 支持由 fallback MatplotlibRenderer 承担）"""

    def test_render_cpu_fallback_candlestick_accepts_x(self):
        from core.webgpu.fallback import MatplotlibRenderer
        r = MatplotlibRenderer.__new__(MatplotlibRenderer)
        r._initialized = True
        r._update_performance_stats = lambda *a, **k: None
        r._data_optimizer = None
        r._volume_virtual_renderer = None
        kdata = pd.DataFrame({
            'symbol': ['600519', '600519'],
            'open': [10.0, 11.0], 'high': [11.0, 12.0], 'low': [9.0, 10.0],
            'close': [11.0, 12.0], 'volume': [1000, 1000],
        })
        ax = MagicMock()
        ok = r.render_candlesticks(ax, kdata, {}, x=np.arange(2), use_datetime_axis=False)
        assert ok is True
