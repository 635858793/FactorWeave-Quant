#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R293 P0: 分钟线完整数据体系 端到端验证测试（TDD）

背景：R293 高价值项 "分钟线完整数据体系" P0 —— 分钟数据端到端验证 + G7 核对。
调研已确认存储/下载/去重链路代码完整（project_memory.md R293-高价值清单段），
本测试用真实 DuckDB（临时文件，不联网）锁定契约：

  下载落库: _store_kline_data_incremental（enhanced_duckdb_data_downloader.py
            L893-948，统一写 historical_kline_data + upsert conflict_columns=
            ['symbol','data_source','timestamp','frequency'] L931-938）
            → _prepare_kline_data_for_storage（L1102-1167，frequency=
            Period.to_duckdb_frequency(period) L1148-1150，timestamp 保留时刻 L1139-1146）
  存储表:   asset_database_manager.py L1888-1913（timestamp TIMESTAMP NOT NULL
            时刻精度 + PRIMARY KEY (symbol, data_source, timestamp, frequency)）
  查询直读: unified_data_manager.py _get_kdata_from_duckdb（L1895，视图 L1920-1976
            分钟走 frequency 过滤 + 日线时刻隔离
            `(hkd.frequency <> '1d' OR CAST(hkd.timestamp AS TIME)=TIME '00:00:00')`
            L1965-1966；基础表兜底同样隔离 L2035-2048）

断言契约（4 项）：
  ① frequency 正确存储（'1min'/'5min'/'60min'）
  ② timestamp 时刻精度保留（查询结果时刻非 00:00:00 且与写入一致）
  ③ 日线查询（frequency='1d'）不返回分钟行（时刻隔离生效）
  ④ 分钟行按精确 timestamp 去重（同 symbol+timestamp 重复 upsert 不产生重复行）

实现：EnhancedDuckDBDataDownloader / UnifiedDataManager 均以 object.__new__ 轻量
构造（参照 test_r254_data_storage.py 先例），仅替换 asset_db_manager /
asset_manager 的 get_database_path 指向临时 DB 文件；duckdb_operations 使用全局
真实 DuckDBOperations（真实引擎 round-trip）。不依赖任何真实网络/数据源。

G7 核对（只读记录，测试中不处理、不修改 repository）：
  core/data/repository.py L637 KlineRepository.get_kline_data 对分钟频率的支持：
  - 入参校验 QueryParams.validate（core/data/models.py L125-153）经
    Period.normalize 归一后校验 `self.period in [p.value for p in Period]`
    （L141-145），分钟周期（'1m'/'5m'/'15m'/'30m'/'1H'）全部合法 → 校验不拒绝分钟。
  - 取数将 period 原样透传 AssetService.get_historical_data（repository.py
    L673-680）或降级 data_manager.get_kdata（L721-726），底层 UnifiedDataManager
    支持分钟频率 → repository 本身无分钟阻塞。
  - 消费面：KlineRepository.get_kline_data 的直接消费者仅 DataAccess.get_kline_data
    （data_access.py L167）/ get_kdata（L204）与内部 get_latest_price（L776 日线）。
    DataAccess 消费方：analysis_manager._technical_analysis（period='day' 日线，
    analysis_manager.py L69）、funding_rate_analysis_service.get_funding_rate
    （interval='1h'，funding_rate_analysis_service.py L85 —— 该服务仅 service_bootstrap
    L1811-1822 注册 + 测试文件引用，无 GUI/业务消费）、get_multiple_kline_data（通用）。
  - 结论：低频旧路径（KlineData 仓库），无真实分钟线业务消费；分钟线主链路为
    EnhancedDuckDBDataDownloader → historical_kline_data → UnifiedDataManager
    ._get_kdata_from_duckdb（本测试锁定的链路）。测试仅以 test_g7_* 记录校验层
    支撑证据，不改动 repository。
"""
import asyncio
import os
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.asset_database_manager import AssetSeparatedDatabaseManager
from core.database.duckdb_manager import get_connection_manager
from core.database.duckdb_operations import get_duckdb_operations
from core.plugin_types import AssetType, DataType
from core.services.enhanced_duckdb_data_downloader import EnhancedDuckDBDataDownloader
from core.services.incremental_data_analyzer import DownloadStrategy
from core.services.unified_data_manager import UnifiedDataManager


# ---------------------------------------------------------------------------
# 测试基础设施：临时 DuckDB 库（真实引擎）+ 轻量业务对象
# ---------------------------------------------------------------------------
# 与 asset_database_manager.py L294-307 的 monitor_latest 建表语句一致
_MONITOR_LATEST_DDL = """
    CREATE TABLE IF NOT EXISTS monitor_latest (
        symbol VARCHAR NOT NULL,
        data_source VARCHAR NOT NULL,
        frequency VARCHAR NOT NULL DEFAULT '1d',
        check_date DATE NOT NULL,
        quality_score DECIMAL(5,2),
        anomaly_count INTEGER DEFAULT 0,
        missing_count INTEGER DEFAULT 0,
        completeness_score DECIMAL(5,2),
        details TEXT,
        PRIMARY KEY (symbol, data_source, frequency)
    )
"""


def _kline_table_ddl() -> str:
    """historical_kline_data 建表 SQL（直接取自存储侧生成器，保证契约一致）"""
    bare = object.__new__(AssetSeparatedDatabaseManager)
    return bare._generate_create_table_sql(
        'historical_kline_data', pd.DataFrame(), DataType.HISTORICAL_KLINE)


@pytest.fixture
def minute_db(tmp_path):
    """临时 DuckDB 库（真实引擎 round-trip，与生产同表结构/同 upsert/同查询 SQL）"""
    db_path = str(tmp_path / 'r293_minute.db')
    ops = get_duckdb_operations()
    for ddl in (_kline_table_ddl(), _MONITOR_LATEST_DDL):
        result = ops.execute_query(db_path, ddl)
        assert result.success, f"建表失败: {ddl[:60]}..."
    yield db_path
    try:
        get_connection_manager().remove_pool(db_path)
    except Exception:
        pass


def _make_downloader(db_path) -> EnhancedDuckDBDataDownloader:
    """轻量下载器（真实 _store_kline_data_incremental / _prepare_kline_data_for_storage，
    仅 DB 路径指向临时文件）"""
    dl = object.__new__(EnhancedDuckDBDataDownloader)
    dl.asset_db_manager = SimpleNamespace(
        get_database_path=lambda asset_type: db_path)
    dl.duckdb_operations = get_duckdb_operations()
    return dl


def _make_udm(db_path) -> UnifiedDataManager:
    """轻量统一数据管理器（真实 _get_kdata_from_duckdb，仅 DB 路径指向临时文件）"""
    udm = object.__new__(UnifiedDataManager)
    udm.duckdb_operations = get_duckdb_operations()
    udm.asset_manager = SimpleNamespace(
        get_database_path=lambda asset_type: db_path)
    return udm


def _minute_kline_df(timestamps, base_close=10.0) -> pd.DataFrame:
    """构造带时刻的 K 线 DataFrame（datetime 列，模拟插件/下载层输出）"""
    ts = pd.to_datetime(timestamps)
    closes = [base_close + i for i in range(len(ts))]
    return pd.DataFrame({
        'datetime': ts,
        'open': [c - 0.1 for c in closes],
        'high': [c + 0.2 for c in closes],
        'low': [c - 0.2 for c in closes],
        'close': closes,
        'volume': [1000 + i for i in range(len(ts))],
        'amount': [100000 + i for i in range(len(ts))],
    })


def _store(dl, df: pd.DataFrame, symbol: str, period: str) -> int:
    """调用 _store_kline_data_incremental（下载层统一落库入口，真实执行）"""
    return asyncio.run(
        dl._store_kline_data_incremental(
            df, symbol, DownloadStrategy.LATEST_ONLY, period=period))


# ---------------------------------------------------------------------------
# ① frequency 正确存储 + ② timestamp 时刻精度保留
# ---------------------------------------------------------------------------
class TestMinuteFrequencyAndTimePrecision:
    """1min/5min/60min 端到端：落库 → 直读，frequency 与时刻均保真"""

    _CASES = [
        ('1m', '1min', ['2026-08-03 09:31:00', '2026-08-03 09:32:00',
                        '2026-08-03 09:33:00']),
        ('5m', '5min', ['2026-08-03 09:35:00', '2026-08-03 09:40:00',
                        '2026-08-03 09:45:00']),
        ('1H', '60min', ['2026-08-03 10:30:00', '2026-08-03 11:30:00',
                         '2026-08-03 13:00:00']),
    ]

    def test_frequency_stored_correctly(self, minute_db):
        """① frequency 列按 Period.to_duckdb_frequency 落库（'1min'/'5min'/'60min'）"""
        dl = _make_downloader(minute_db)
        symbol = '000001'
        for period, _duck_freq, ts in self._CASES:
            rows = _store(dl, _minute_kline_df(ts), symbol, period)
            assert rows == len(ts), f"{period} 落库行数异常: {rows}"

        result = get_duckdb_operations().execute_query(
            minute_db,
            "SELECT DISTINCT frequency FROM historical_kline_data ORDER BY frequency")
        assert result.success
        assert result.data['frequency'].tolist() == ['1min', '5min', '60min'], \
            f"frequency 落库错误: {result.data['frequency'].tolist()}"

    def test_timestamp_time_precision_preserved(self, minute_db):
        """② 直读结果时刻非 00:00:00 且与写入一致（时刻精度保留）"""
        dl = _make_downloader(minute_db)
        udm = _make_udm(minute_db)
        symbol = '000001'
        for period, _duck_freq, ts in self._CASES:
            _store(dl, _minute_kline_df(ts), symbol, period)

        for period, _duck_freq, ts in self._CASES:
            got = udm._get_kdata_from_duckdb(symbol, period, count=100)
            assert not got.empty, f"{period} 直读为空"
            times = pd.to_datetime(got['datetime']).dt.strftime('%H:%M:%S').tolist()
            expected = pd.to_datetime(ts).strftime('%H:%M:%S').tolist()
            assert sorted(times) == sorted(expected), \
                f"{period} 时刻精度丢失/漂移: 写入={expected} 读回={times}"

    def test_prepare_kline_data_for_storage_contract(self, minute_db):
        """存储准备纯函数契约：timestamp 保留时刻、frequency 映射、symbol/data_source 补齐"""
        dl = _make_downloader(minute_db)
        df = _minute_kline_df(['2026-08-03 09:31:00', '2026-08-03 09:32:00'])
        prepared = dl._prepare_kline_data_for_storage(df, '000001', '5m')

        assert 'timestamp' in prepared.columns
        assert 'datetime' not in prepared.columns
        times = prepared['timestamp'].dt.strftime('%H:%M:%S').tolist()
        assert times == ['09:31:00', '09:32:00'], f"timestamp 时刻丢失: {times}"
        assert (prepared['frequency'] == '5min').all(), \
            f"frequency 未按 Period.to_duckdb_frequency 映射: {prepared['frequency'].unique()}"
        assert (prepared['symbol'] == '000001').all()
        assert (prepared['data_source'] == 'enhanced_duckdb_downloader').all()


# ---------------------------------------------------------------------------
# ③ 日线查询时刻隔离
# ---------------------------------------------------------------------------
class TestDailyQueryIsolation:
    """日线查询（frequency='1d'）不得返回分钟行"""

    def test_daily_query_returns_only_daily_rows(self, minute_db):
        dl = _make_downloader(minute_db)
        udm = _make_udm(minute_db)
        symbol = '000002'

        # 分钟行（带时刻，09:31~11:30）
        _store(dl, _minute_kline_df(
            ['2026-08-03 09:31:00', '2026-08-03 09:32:00',
             '2026-08-03 09:33:00']), symbol, '1m')
        _store(dl, _minute_kline_df(
            ['2026-08-03 10:30:00', '2026-08-03 11:30:00']), symbol, '1H')
        # 日线行（合法 timestamp 恒为 00:00:00）
        _store(dl, _minute_kline_df(
            ['2026-08-03 00:00:00', '2026-08-04 00:00:00',
             '2026-08-05 00:00:00']), symbol, 'D')

        # 日线查询只返回 3 行日线，且时刻全为 00:00:00
        got = udm._get_kdata_from_duckdb(symbol, 'D', count=100)
        assert len(got) == 3, f"日线查询混入分钟行: {len(got)} 行"
        times = set(pd.to_datetime(got['datetime']).dt.strftime('%H:%M:%S').unique())
        assert times == {'00:00:00'}, f"日线查询返回非 00:00:00 行: {times}"

        # 分钟查询不受日线行干扰（frequency 精确过滤）
        m1 = udm._get_kdata_from_duckdb(symbol, '1m', count=100)
        assert len(m1) == 3
        m60 = udm._get_kdata_from_duckdb(symbol, '1H', count=100)
        assert len(m60) == 2


# ---------------------------------------------------------------------------
# ④ 分钟行精确 timestamp 去重（upsert）
# ---------------------------------------------------------------------------
class TestMinuteUpsertDedup:
    """同 symbol+timestamp 重复 upsert 不产生重复行（主键精确去重）"""

    def test_duplicate_upsert_does_not_duplicate_rows(self, minute_db):
        dl = _make_downloader(minute_db)
        udm = _make_udm(minute_db)
        symbol = '000003'
        ts = ['2026-08-03 09:31:00', '2026-08-03 09:32:00',
              '2026-08-03 09:33:00']

        # 第一次落库：close=10/11/12
        _store(dl, _minute_kline_df(ts, base_close=10.0), symbol, '1m')
        # 第二次落库：同 symbol+timestamp（同 data_source+frequency），close=20/21/22
        _store(dl, _minute_kline_df(ts, base_close=20.0), symbol, '1m')

        # ④ 行数不增加（按精确 timestamp 去重）
        result = get_duckdb_operations().execute_query(
            minute_db,
            "SELECT COUNT(*) AS c FROM historical_kline_data "
            "WHERE symbol = ? AND frequency = '1min'",
            params=[symbol])
        assert result.success
        assert result.data['c'].iloc[0] == 3, "重复 upsert 产生了重复行"

        # 后写覆盖（ON CONFLICT DO UPDATE 语义）
        got = udm._get_kdata_from_duckdb(symbol, '1m', count=100)
        closes = sorted(got['close'].tolist())
        assert closes == [20.0, 21.0, 22.0], f"upsert 未覆盖旧值: {closes}"


# ---------------------------------------------------------------------------
# G7 核对支撑证据（只读记录，不改动 repository）
# ---------------------------------------------------------------------------
class TestG7KlineRepositoryMinuteSupport:
    """G7 支撑证据：KlineRepository 入参校验层（core/data/models.py
    QueryParams.validate L125-153）接受全部分钟周期 —— 记录 repository 对分钟
    频率的支持面，不做任何业务处理。"""

    @pytest.mark.parametrize('raw,expected', [
        ('1m', '1m'), ('1min', '1m'), ('5m', '5m'), ('15m', '15m'),
        ('30m', '30m'), ('1h', '1H'), ('1H', '1H'), ('60min', '1H'),
    ])
    def test_query_params_validate_accepts_minute_periods(self, raw, expected):
        from core.data.models import QueryParams
        qp = QueryParams(stock_code='000001', period=raw, count=10)
        assert qp.validate() is True, f"period={raw} 被校验拒绝"
        assert qp.period == expected, f"period={raw} 归一错误: {qp.period}"
