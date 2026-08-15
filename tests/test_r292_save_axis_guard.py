#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R292 第6轮：K线下载/保存路径坐标轴与日期处理防护（TDD）

背景：R292 第五轮修复了数据展示链路（日线隔离分钟垃圾、datetime 数值解析、
坐标轴序号化）。本轮审计下载/保存路径发现同型缺陷未同步：
  A. 无命名 DatetimeIndex reset_index 后产生 'index' 列，3 处落库入口未改名 →
     时间列丢失 → 数据静默丢弃或违反 NOT NULL 约束落库失败
     （enhanced_duckdb_data_downloader._prepare_kline_data_for_storage /
       uni_plugin_data_manager._persist_fetched_data /
       asset_database_manager.store_standardized_data，unified_data_manager 已修）
  B. import_execution_engine._standardize_kline_data_fields 数值型 datetime
     未先 astype(str) → pd.to_datetime(int) 按纳秒解释为 1970 假象
  D. tongdaxin get_kdata period_map 缺 '1d'/'1M' 等 DuckDB 频率键 →
     get_kdata(freq='1M') 静默降级为日线
  E. 旁路查询（批量/基础表）缺分钟垃圾隔离条件（纵深防御，SQL 语义验证）
"""
import os
import sys
import threading
import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from core.services.enhanced_duckdb_data_downloader import EnhancedDuckDBDataDownloader
from core.asset_database_manager import AssetSeparatedDatabaseManager
from core.importdata.import_execution_engine import DataImportExecutionEngine as ImportExecutionEngine
from plugins.data_sources.stock.tongdaxin_plugin import TongdaxinStockPlugin


def _unnamed_kline_df(n: int = 10) -> pd.DataFrame:
    """构造无命名 DatetimeIndex 的日线 DataFrame（模拟上游插件返回形态）。

    索引 name=None → reset_index() 会生成 'index' 列（而非 'datetime' 列），
    是落库入口 'index'→'datetime' 改名防护的触发条件。
    """
    dates = pd.date_range('2026-08-01', periods=n, freq='D')
    idx = pd.DatetimeIndex(dates)  # 无 name
    closes = np.linspace(10.0, 12.0, n)
    return pd.DataFrame({
        'open': closes - 0.1,
        'high': closes + 0.2,
        'low': closes - 0.2,
        'close': closes,
        'volume': np.linspace(10000, 20000, n),
        'amount': np.linspace(1e6, 2e6, n),
    }, index=idx)


class TestPrepareKlineStorage:
    """enhanced_duckdb_data_downloader._prepare_kline_data_for_storage"""

    def test_unnamed_index_generates_timestamp(self):
        """无命名 DatetimeIndex → timestamp 列必须生成，数据不得被静默丢弃"""
        dl = EnhancedDuckDBDataDownloader(uni_plugin_manager=MagicMock())
        out = dl._prepare_kline_data_for_storage(_unnamed_kline_df(), '300750', 'D')
        assert not out.empty, "无命名 DatetimeIndex 时数据被静默丢弃（返回空 DataFrame）"
        assert 'timestamp' in out.columns, "缺少 timestamp 列"
        assert out['timestamp'].iloc[0] == pd.Timestamp('2026-08-01 00:00:00')


class TestStandardizeKlineFields:
    """import_execution_engine._standardize_kline_data_fields"""

    # DataImportExecutionEngine 继承 QObject，不能 object.__new__ 绕过；
    # 目标函数体内不使用 self（仅模块级 logger），以 unbound 方式调用。
    _func = ImportExecutionEngine._standardize_kline_data_fields

    def _run(self, df):
        # 通过类访问（非 self._func，实例访问会把 function 绑定为 bound method）
        return TestStandardizeKlineFields._func(None, df, data_source='test', frequency='1d')

    def test_numeric_datetime_not_1970(self):
        """int 型 datetime（20240814）必须解析为 2024-08-14，而非纳秒解释的 1970"""
        df = pd.DataFrame({
            'datetime': [20240814, 20240815],
            'open': [10.0, 10.5], 'high': [10.8, 11.0], 'low': [9.9, 10.4],
            'close': [10.5, 10.9], 'volume': [10000, 12000], 'amount': [1e6, 1.1e6],
        })
        out = self._run(df)
        assert out['datetime'].iloc[0] == pd.Timestamp('2024-08-14')
        assert out['datetime'].iloc[1] == pd.Timestamp('2024-08-15')

    def test_unnamed_index_renamed_to_datetime(self):
        """无命名 DatetimeIndex → 落库前重置为 datetime 列（'index' 列改名）"""
        out = self._run(_unnamed_kline_df())
        assert 'datetime' in out.columns
        assert 'index' not in out.columns
        assert out['datetime'].iloc[0] == pd.Timestamp('2026-08-01 00:00:00')


class TestStoreStandardizedData:
    """asset_database_manager.store_standardized_data 落库入口"""

    def _manager(self):
        mgr = object.__new__(AssetSeparatedDatabaseManager)
        mgr._write_lock = threading.Lock()
        mgr.duckdb_manager = MagicMock()
        mgr._ensure_database_exists = MagicMock(return_value=':memory:')
        mgr._generate_table_name = MagicMock(return_value='historical_kline_data')
        mgr._evaluate_and_record_quality = MagicMock(return_value=None)
        mgr._reject_low_quality_kline_enabled = MagicMock(return_value=False)
        mgr._ensure_table_exists = MagicMock()
        mgr._upsert_data = MagicMock(return_value=0)
        return mgr

    def test_unnamed_index_persisted_with_timestamp(self):
        """无命名 DatetimeIndex → 落库入口将 'index' 改名 'datetime'（timestamp 由 _upsert_data 内部映射生成）"""
        mgr = self._manager()
        df = _unnamed_kline_df()
        df['symbol'] = '300750'
        df['data_source'] = 'test'
        df['frequency'] = '1d'
        ok = mgr.store_standardized_data(df, 'STOCK_A', 'HISTORICAL_KLINE')
        assert ok
        stored = mgr._upsert_data.call_args[0][2]
        assert 'datetime' in stored.columns, "落库数据缺少时间列"
        assert 'index' not in stored.columns, "'index' 列未改名为 datetime"
        assert stored['datetime'].iloc[0] == pd.Timestamp('2026-08-01 00:00:00')


class TestTongdaxinPeriodMap:
    """tongdaxin_plugin.get_kdata 频率映射（DuckDB 频率键）"""

    @pytest.fixture()
    def plugin(self):
        # object.__new__ 绕过 __init__：完整构造会启动 TdxServerInit 后台联网线程，
        # 测试进程结束时 loguru 写已关闭文件流 → ValueError。
        p = object.__new__(TongdaxinStockPlugin)
        p.logger = MagicMock()
        return p

    def test_1M_maps_to_monthly(self, plugin):
        with patch.object(plugin, 'get_kline_data', return_value=pd.DataFrame()) as mocked:
            plugin.get_kdata('300750', freq='1M')
            assert mocked.call_args[1]['period'] == 'monthly', "get_kdata(freq='1M') 不得静默降级为日线"

    def test_1d_maps_to_daily(self, plugin):
        with patch.object(plugin, 'get_kline_data', return_value=pd.DataFrame()) as mocked:
            plugin.get_kdata('300750', freq='1d')
            assert mocked.call_args[1]['period'] == 'daily'

    def test_1w_maps_to_weekly(self, plugin):
        with patch.object(plugin, 'get_kline_data', return_value=pd.DataFrame()) as mocked:
            plugin.get_kdata('300750', freq='1w')
            assert mocked.call_args[1]['period'] == 'weekly'


class TestFrequencyMapCompleteness:
    """G1：任务创建向导频率映射完整性（分钟/月线不得静默降级日线）"""

    def test_all_periods_covered(self):
        from core.plugin_types import Period
        from core.importdata.import_config_manager import DUCKDB_FREQUENCY_TO_DATA_FREQUENCY
        fm = DUCKDB_FREQUENCY_TO_DATA_FREQUENCY
        for name in Period.all_periods():
            dbf = Period.to_duckdb_frequency(name)
            assert dbf in fm, f"周期 '{name}' (DuckDB 频率 {dbf}) 缺少映射 → 任务创建静默降级日线"

    def test_semantics(self):
        from core.importdata.import_config_manager import DUCKDB_FREQUENCY_TO_DATA_FREQUENCY, DataFrequency
        fm = DUCKDB_FREQUENCY_TO_DATA_FREQUENCY
        assert fm['1d'] is DataFrequency.DAILY
        assert fm['1w'] is DataFrequency.WEEKLY
        assert fm['1M'] is DataFrequency.MONTHLY
        assert fm['1m'] is DataFrequency.MINUTE_1, "'1m' 是 1 分钟而非月线"
        assert fm['1min'] is DataFrequency.MINUTE_1
        assert fm['5min'] is DataFrequency.MINUTE_5
        assert fm['15min'] is DataFrequency.MINUTE_15
        assert fm['30min'] is DataFrequency.MINUTE_30
        assert fm['60min'] is DataFrequency.HOUR_1
        assert fm['daily'] is DataFrequency.DAILY


class TestIsolationConditionSQL:
    """日线分钟垃圾隔离条件的 DuckDB SQL 语义验证（纵深防御条件本体）"""

    def test_daily_isolation_condition(self):
        import duckdb
        conn = duckdb.connect(':memory:')
        conn.execute("""
            CREATE TABLE historical_kline_data (
                symbol VARCHAR, frequency VARCHAR, timestamp TIMESTAMP,
                open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE
            )
        """)
        conn.execute("INSERT INTO historical_kline_data VALUES "
                     "('300750','1d',TIMESTAMP '2026-08-14 00:00:00',1,2,1,2,100)")
        conn.execute("INSERT INTO historical_kline_data VALUES "
                     "('300750','1d',TIMESTAMP '2026-08-14 09:31:00',1,2,1,2,100)")
        conn.execute("INSERT INTO historical_kline_data VALUES "
                     "('300750','1min',TIMESTAMP '2026-08-14 09:31:00',1,2,1,2,100)")
        condition = "(frequency <> '1d' OR CAST(timestamp AS TIME) = TIME '00:00:00')"
        # 日线只返回 00:00:00 真日线，分钟垃圾被隔离
        df = conn.execute(
            f"SELECT * FROM historical_kline_data WHERE symbol=? AND frequency=? AND {condition}",
            ['300750', '1d']).fetchdf()
        assert len(df) == 1
        # 分钟线不受隔离条件影响
        dfm = conn.execute(
            f"SELECT * FROM historical_kline_data WHERE symbol=? AND frequency=? AND {condition}",
            ['300750', '1min']).fetchdf()
        assert len(dfm) == 1
