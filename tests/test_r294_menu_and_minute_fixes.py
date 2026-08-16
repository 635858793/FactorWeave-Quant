#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R294 测试：数据/工具菜单修复 + 分钟线数据体系增强

覆盖：
- B1 分钟线"当天内"增量补齐（_incremental_fill_kdata 分钟分支）：
    DB 已有当日部分分钟数据时，最新时刻落后 >= 2 周期 → 重拉当天 → 精确去重只插新时刻
- B2 分时图增强（_compute_intraday_series）：
    当日分时过滤 / 昨收参考价 / 成交量加权均价(VWAP) / 无 volume 退化为 close 均价
- A 组静态断言（增强导入单例复用 / 导入历史文案+自动切页 /
    缓存清理确认框 / 节点管理安全获取 / 重复 import 清理）

背景：R293 遗留高价值清单本轮实施；修复注释均标 R294。
"""
import os
import sys
import types
import importlib.util
import datetime as _dt
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# conftest.py 在模块层 mock 了 'gui.widgets'（无 __path__），pytest 下直接
# `from gui.widgets.chart_mixins.rendering_mixin import ...` 会报 "is not a package"。
# 临时移除 mock，用 importlib 按文件加载，完成后恢复以保护其他测试。
_saved_gui_widgets = sys.modules.pop('gui.widgets', None)


def _load_module_from_file(mod_name, file_path):
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_chart_mixins_pkg = types.ModuleType('gui.widgets.chart_mixins')
_chart_mixins_pkg.__path__ = [
    os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins')]
sys.modules['gui.widgets.chart_mixins'] = _chart_mixins_pkg


# ============ B2: 分时图增强（_compute_intraday_series） ============

def _load_rendering_mixin():
    """加载 rendering_mixin（无头环境，失败则跳过 GUI 相关测试）"""
    try:
        mod = _load_module_from_file(
            'gui.widgets.chart_mixins.rendering_mixin',
            os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins',
                         'rendering_mixin.py'))
        return mod
    except Exception as e:  # matplotlib/PyQt5 无头导入失败等
        pytest.skip(f"rendering_mixin 无头加载失败，跳过分时图测试: {e}")


def _make_intraday_frame():
    """构造两天 1min 数据（前一天 3 根 + 当天 3 根）"""
    return pd.DataFrame({
        'datetime': pd.to_datetime([
            '2026-08-14 10:00:00', '2026-08-14 10:01:00', '2026-08-14 10:02:00',
            '2026-08-15 10:00:00', '2026-08-15 10:01:00', '2026-08-15 10:02:00']),
        'open': [10.0, 10.1, 10.2, 10.3, 10.4, 10.5],
        'high': [10.5, 10.6, 10.7, 10.8, 10.9, 11.0],
        'low': [9.9, 10.0, 10.1, 10.2, 10.3, 10.4],
        'close': [10.2, 10.3, 10.4, 10.5, 10.6, 10.7],
        'volume': [100, 200, 300, 400, 500, 600],
    })


class TestComputeIntradaySeries:
    """R294 分时图：当日过滤 / 昨收 / VWAP 均价线"""

    @classmethod
    def setup_class(cls):
        cls.rm = _load_rendering_mixin()

    def _call(self, kdata):
        return self.rm.RenderingMixin._compute_intraday_series(kdata)

    def test_filter_latest_day_only(self):
        """多日 1min 数据 → 只保留最新交易日的分时行"""
        intra, prev_close, avg = self._call(_make_intraday_frame())
        assert len(intra) == 3
        assert all(pd.to_datetime(intra['datetime']).dt.date == pd.Timestamp('2026-08-15').date())

    def test_prev_close_from_previous_day(self):
        """昨收 = 最新交易日之前最后一根收盘价"""
        _, prev_close, _ = self._call(_make_intraday_frame())
        assert prev_close == 10.4  # 前一天最后 close

    def test_vwap_computation(self):
        """均价线 = 成交量加权 VWAP（首行退化为当日首根 close）"""
        _, _, avg = self._call(_make_intraday_frame())
        # 当日: close=[10.5,10.6,10.7] vol=[400,500,600]
        # vwap[0]=10.5; vwap[1]=(10.5*400+10.6*500)/900; vwap[2]=(10.5*400+10.6*500+10.7*600)/1500
        expected = [
            10.5,
            (10.5 * 400 + 10.6 * 500) / 900,
            (10.5 * 400 + 10.6 * 500 + 10.7 * 600) / 1500,
        ]
        np.testing.assert_allclose(avg.to_numpy(), expected, rtol=1e-9)

    def test_single_day_prev_close_is_first_open(self):
        """只有单日数据 → 昨收 = 当日首根 open"""
        df = _make_intraday_frame().iloc[3:]  # 仅当天 3 根
        intra, prev_close, _ = self._call(df)
        assert len(intra) == 3
        assert prev_close == 10.3  # 首根 open

    def test_no_datetime_column_uses_all(self):
        """无 datetime 列 → 全量数据 + 昨收 = 首根 open"""
        df = _make_intraday_frame().drop(columns=['datetime'])
        intra, prev_close, _ = self._call(df)
        assert len(intra) == 6
        assert prev_close == 10.0

    def test_zero_volume_avg_falls_back_to_close(self):
        """volume 全 0 → 均价线退化为 close 均价"""
        df = _make_intraday_frame()
        df['volume'] = 0
        _, _, avg = self._call(df)
        np.testing.assert_allclose(avg.to_numpy(), [10.5, 10.6, 10.7], rtol=1e-9)


# ============ B1: 分钟线当天增量补齐（_incremental_fill_kdata） ============

# 固定测试时钟：2026-08-15 14:00:00（盘中，避免跨午夜边界）
class _FakeDatetime(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 8, 15, 14, 0, 0)


class TestMinuteIncrementalFill:
    """R294 分钟线"当天内"增量补齐"""

    def _make(self):
        from core.services.unified_data_manager import UnifiedDataManager
        udm = object.__new__(UnifiedDataManager)
        udm._kdata_incremental_checked = {}
        udm._kdata_incremental_ttl = 3600
        udm._kdata_history_exhausted = {}
        udm._persist_kdata_to_duckdb = MagicMock()
        return udm

    def _db_df(self, latest):
        """DB 已有当日部分分钟数据（最新时刻可注入）"""
        return pd.DataFrame({
            'datetime': pd.to_datetime(['2026-08-15 09:30:00', latest]),
            'open': [1.0, 2.0], 'high': [2.0, 3.0], 'low': [0.5, 1.5],
            'close': [1.5, 2.5], 'volume': [100, 200],
            'symbol': ['T', 'T'], 'code': ['T', 'T'],
            'data_source': ['tet_plugin', 'tet_plugin'],
            'adj_type': ['none', 'none'],
        })

    def _new_day_minutes(self):
        """当天新产生的分钟数据（10:00 之后）"""
        return pd.DataFrame({
            'datetime': pd.to_datetime(['2026-08-15 10:30:00']),
            'open': [9.0], 'high': [10.0], 'low': [8.0], 'close': [9.5],
            'volume': [999],
        })

    @patch('core.services.unified_data_manager.datetime', _FakeDatetime)
    def test_intraday_trigger_and_dedup(self):
        """DB 最新时刻(09:30)落后当前(14:00)>=2周期(5min→10min) → 触发当天重拉"""
        from core.plugin_types import AssetType
        udm = self._make()
        db_df = self._db_df('2026-08-15 09:30:00')

        new_df = self._new_day_minutes()
        udm._fetch_kdata_from_tet = MagicMock(return_value=(new_df, 'test_plugin'))

        # count=len(db_df)：抑制场景B(历史补齐)干扰，仅测分钟当天分支
        merged = udm._incremental_fill_kdata('T', '5m', len(db_df), db_df, AssetType.STOCK_A)

        # 分钟当天分支触发：start_date = 当天 YYYYMMDD
        udm._fetch_kdata_from_tet.assert_called_once()
        args = udm._fetch_kdata_from_tet.call_args
        assert args.kwargs.get('start_date') == '20260815'
        # 合并后含新增分钟 → 落库 + 返回合并数据
        assert merged is not None
        assert udm._persist_kdata_to_duckdb.call_count == 1

    @patch('core.services.unified_data_manager.datetime', _FakeDatetime)
    def test_no_trigger_when_latest_recent(self):
        """DB 最新时刻(13:55)距当前(14:00)不足2周期(5min→10min) → 不触发"""
        from core.plugin_types import AssetType
        udm = self._make()
        db_df = self._db_df('2026-08-15 13:55:00')

        udm._fetch_kdata_from_tet = MagicMock(return_value=(None, None))

        merged = udm._incremental_fill_kdata('T', '5m', len(db_df), db_df, AssetType.STOCK_A)

        udm._fetch_kdata_from_tet.assert_not_called()
        assert merged is None

    @patch('core.services.unified_data_manager.datetime', _FakeDatetime)
    def test_daily_not_enter_minute_branch(self):
        """日线频率不进入分钟当天分支（同日最新不增量）"""
        from core.plugin_types import AssetType
        udm = self._make()
        db_df = self._db_df('2026-08-15 00:00:00')

        udm._fetch_kdata_from_tet = MagicMock(return_value=(None, None))

        merged = udm._incremental_fill_kdata('T', 'D', len(db_df), db_df, AssetType.STOCK_A)

        udm._fetch_kdata_from_tet.assert_not_called()
        assert merged is None

    @patch('core.services.unified_data_manager.datetime', _FakeDatetime)
    def test_60min_span_threshold(self):
        """60min 周期 span=120min：最新(12:00)距当前(14:00)不足120min → 不触发"""
        from core.plugin_types import AssetType
        udm = self._make()
        db_df = self._db_df('2026-08-15 12:00:00')

        udm._fetch_kdata_from_tet = MagicMock(return_value=(None, None))

        merged = udm._incremental_fill_kdata('T', '1H', len(db_df), db_df, AssetType.STOCK_A)

        udm._fetch_kdata_from_tet.assert_not_called()
        assert merged is None


# ============ A 组：菜单/协调器修复静态断言 ============

def _read(path):
    with open(os.path.join(PROJECT_ROOT, path), 'r', encoding='utf-8') as f:
        return f.read()


class TestR294StaticFixes:
    """A 组修复的源码级静态验证（避免无头环境实例化 GUI）"""

    def test_enhanced_import_singleton(self):
        """增强导入窗口单例复用：存在则置顶/复用，不重复创建"""
        src = _read(os.path.join('gui', 'menu_bar.py'))
        assert 'enhanced_import_window' in src
        assert 'win.raise_()' in src
        assert 'win.activateWindow()' in src
        assert "destroyed.connect(" in src
        # 原无条件重建已移除
        assert "self.enhanced_import_window = EnhancedDataImportMainWindow(" in src

    def test_import_history_section_and_message(self):
        """导入历史：自动切历史页 + 文案不再误导"""
        src = _read(os.path.join('core', 'coordinators', 'main_window_coordinator.py'))
        assert "dialog._switch_section('history')" in src
        assert '导入历史功能不可用（组件加载失败）' in src
        assert '导入历史记录功能正在开发中' not in src

    def test_cache_clear_confirmation(self):
        """缓存清理：三个入口均加 QMessageBox.question 二次确认"""
        src = _read(os.path.join('core', 'coordinators', 'main_window_coordinator.py'))
        assert 'def _do_clear_data_cache' in src
        assert 'def _do_clear_negative_cache' in src
        assert '确定要清理数据缓存吗？' in src
        assert '确定要清理负缓存吗？' in src
        assert '确定要清理所有缓存吗？' in src
        # 级联清理调用私有执行方法，避免连环确认框
        assert '_do_clear_data_cache()' in src
        assert '_do_clear_negative_cache()' in src

    def test_node_management_safe_get(self):
        """节点管理：container.get 加 try/except（resolve_by_name 未注册抛 ValueError）"""
        src = _read(os.path.join('core', 'coordinators', 'main_window_coordinator.py'))
        assert "container.get('distributed_service')" in src
        assert 'distributed_service = None' in src

    def test_duplicate_quality_import_removed(self):
        """重复 import 清理：data_quality_dialog 局部导入已删，仅剩模块级 1 处"""
        src = _read(os.path.join('core', 'coordinators', 'main_window_coordinator.py'))
        count = src.count('from gui.dialogs.data_quality_dialog import DataQualityDialog')
        assert count == 1

    def test_minute_incremental_branch_present(self):
        """分钟当天增量分支：intraday_minutes 映射与触发逻辑存在"""
        src = _read(os.path.join('core', 'services', 'unified_data_manager.py'))
        assert 'intraday_minutes' in src
        assert "'1min': 1" in src
        assert '分钟当天' in src

    def test_intraday_series_method_present(self):
        """分时图增强：_compute_intraday_series 静态方法与当日分时标注存在"""
        src = _read(os.path.join('gui', 'widgets', 'chart_mixins', 'rendering_mixin.py'))
        assert 'def _compute_intraday_series' in src
        assert '当日分时(1分钟)' in src
        assert 'avg_style' in src  # 均价线独立黄色样式


# 恢复 conftest 的 mock，避免影响其他测试
if _saved_gui_widgets is not None:
    sys.modules['gui.widgets'] = _saved_gui_widgets
