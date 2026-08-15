#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R288 性能基准测试：构造大量历史数据 Mock 场景，量化 R287/R288 读写性能修复收益

场景规模（真实 DuckDB 内存库）：
- historical_kline_data：50 只股票 × 250 交易日 × 2 数据源 = 25,000 行
- data_quality_monitor：50 symbol × 2 源 × 250 天（每天一条评估）= 25,000 行
- monitor_latest：50 symbol × 2 源 = 100 行（物化后每 symbol+源+频率仅 1 行）

对比项（修复前 vs 修复后）：
1. P0-2 view_query：旧 SQL（latest_dqm 全表 GROUP BY 子查询）vs 新 SQL（JOIN monitor_latest）
2. P0-1 读前质量分：直查 DB vs 缓存命中（第二次调用）
3. P1-2 表结构元数据：无缓存 duckdb_tables 查询 vs 会话级缓存命中

断言阈值宽松（避免 CI flaky）：新方案平均耗时 <= 旧方案 60%。
"""

import os
import sys
import time
import threading
from types import SimpleNamespace

import duckdb
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.asset_database_manager import AssetSeparatedDatabaseManager
from core.plugin_types import AssetType, DataType
from core.services.unified_data_manager import UnifiedDataManager

N_SYMBOLS = 50
N_DAYS = 250
N_SOURCES = 2
N_REPEATS = 5
# monitor 评估记录放大到 200 万行（2000 symbol × 2 源 × 500 天），使全表 GROUP BY 成本显性化。
# 数据由 DuckDB 内建 range() + CROSS JOIN 向量化生成（~1s），避免 Python 侧列表构建拖慢 setup。
N_MONITOR_SYMBOLS = 2000
N_MONITOR_DAYS = 500


@pytest.fixture(scope='module')
def perf_db():
    """构造大量历史数据的真实 DuckDB 内存库（数据生成全程在 DuckDB 内完成，秒级）"""
    conn = duckdb.connect(':memory:')
    mgr = AssetSeparatedDatabaseManager.__new__(AssetSeparatedDatabaseManager)
    schemas = mgr._initialize_table_schemas()

    conn.execute(schemas['historical_kline_data'])
    conn.execute(schemas['data_quality_monitor'])
    conn.execute(schemas['monitor_latest'])

    symbols = [f'{600000 + i}' for i in range(N_SYMBOLS)]
    sources = ['tongdaxin', 'akshare']
    days = pd.date_range('2024-01-01', periods=N_DAYS, freq='D')

    # 灌 K 线：50×250×2 = 25,000 行（向量化）
    kline_rows = []
    for sym in symbols:
        for src in sources:
            for ts in days:
                kline_rows.append((
                    sym, src, ts, '1d', 10.0, 11.0, 9.0, 10.5,
                    1000, 10500.0, 0.0, 1.0, 0.0, 0.0, 0.0,
                    pd.Timestamp.now(), pd.Timestamp.now(),
                ))
    conn.executemany(
        """INSERT INTO historical_kline_data
           (symbol, data_source, timestamp, frequency, open, high, low, close,
            volume, amount, turnover, adj_close, adj_factor, change, change_pct,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        kline_rows,
    )

    # 灌 monitor：2000×2×500 = 2,000,000 行（纯 DuckDB SQL 向量化生成）
    conn.execute(f"""
        INSERT INTO data_quality_monitor
        (monitor_id, symbol, data_source, check_date, frequency, quality_score,
         anomaly_count, missing_count, outlier_count, consistency_score,
         completeness_score, details)
        SELECT symbol || '_' || data_source || '_' || CAST(check_date AS VARCHAR),
               symbol, data_source, check_date, '1d',
               70.0 + (symbol_hash % 20),
               0, 0, 0,
               (70.0 + (symbol_hash % 20)) / 100.0,
               (70.0 + (symbol_hash % 20)) / 100.0,
               'benchmark'
        FROM (
            SELECT
                lpad(CAST(600000 + t.i AS VARCHAR), 6, '0') AS symbol,
                s.data_source,
                date '2023-01-01' + CAST(d.i AS INTEGER) AS check_date,
                t.i AS symbol_hash
            FROM range({N_MONITOR_SYMBOLS}) t(i)
            CROSS JOIN (VALUES ('tongdaxin'), ('akshare')) s(data_source)
            CROSS JOIN range({N_MONITOR_DAYS}) d(i)
        )
    """)

    # 物化 monitor_latest（等价于 R287 预填 SQL）
    conn.execute("""
        INSERT OR REPLACE INTO monitor_latest
        (symbol, data_source, frequency, check_date, quality_score,
         anomaly_count, missing_count, completeness_score, details)
        SELECT dqm2.symbol, dqm2.data_source, dqm2.frequency, dqm2.check_date,
               dqm2.quality_score, dqm2.anomaly_count, dqm2.missing_count,
               dqm2.completeness_score, dqm2.details
        FROM data_quality_monitor dqm2
        INNER JOIN (
            SELECT symbol, data_source, frequency, MAX(check_date) AS max_check_date
            FROM data_quality_monitor
            GROUP BY symbol, data_source, frequency
        ) latest_dqm ON dqm2.symbol = latest_dqm.symbol
            AND dqm2.data_source = latest_dqm.data_source
            AND dqm2.frequency = latest_dqm.frequency
            AND dqm2.check_date = latest_dqm.max_check_date
    """)

    yield conn
    conn.close()


def _avg_ms(func, repeats=N_REPEATS):
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        func()
        times.append((time.perf_counter() - t0) * 1000)
    return sum(times) / len(times)


# ---------------------------------------------------------------------------
# P0-2：view_query 全表 GROUP BY 子查询 vs monitor_latest 物化表 JOIN
# ---------------------------------------------------------------------------
class TestViewQueryPerf:
    """旧 SQL（全表 GROUP BY）vs 新 SQL（JOIN monitor_latest）"""

    def test_view_query_old_vs_new(self, perf_db):
        old_sql = """
            WITH ranked_data AS (
                SELECT hkd.*, dqm.quality_score,
                       ROW_NUMBER() OVER (
                           PARTITION BY hkd.symbol, hkd.timestamp, hkd.frequency
                           ORDER BY CASE WHEN dqm.quality_score IS NOT NULL THEN dqm.quality_score ELSE 50.0 END DESC
                       ) AS quality_rank
                FROM historical_kline_data hkd
                LEFT JOIN (
                    SELECT dqm2.*
                    FROM data_quality_monitor dqm2
                    INNER JOIN (
                        SELECT symbol, data_source, frequency, MAX(check_date) AS max_check_date
                        FROM data_quality_monitor
                        GROUP BY symbol, data_source, frequency
                    ) latest_dqm ON dqm2.symbol = latest_dqm.symbol
                        AND dqm2.data_source = latest_dqm.data_source
                        AND dqm2.frequency = latest_dqm.frequency
                        AND dqm2.check_date = latest_dqm.max_check_date
                ) dqm ON (
                    hkd.symbol = dqm.symbol
                    AND hkd.data_source = dqm.data_source
                    AND hkd.frequency = dqm.frequency
                )
                WHERE hkd.symbol = ? AND hkd.frequency = ?
            )
            SELECT symbol, timestamp, open, high, low, close, volume, amount
            FROM ranked_data WHERE quality_rank = 1
            ORDER BY timestamp DESC LIMIT ?
        """
        new_sql = """
            WITH ranked_data AS (
                SELECT hkd.*, dqm.quality_score,
                       ROW_NUMBER() OVER (
                           PARTITION BY hkd.symbol, hkd.timestamp, hkd.frequency
                           ORDER BY CASE WHEN dqm.quality_score IS NOT NULL THEN dqm.quality_score ELSE 50.0 END DESC
                       ) AS quality_rank
                FROM historical_kline_data hkd
                LEFT JOIN monitor_latest dqm ON (
                    hkd.symbol = dqm.symbol
                    AND hkd.data_source = dqm.data_source
                    AND hkd.frequency = dqm.frequency
                )
                WHERE hkd.symbol = ? AND hkd.frequency = ?
            )
            SELECT symbol, timestamp, open, high, low, close, volume, amount
            FROM ranked_data WHERE quality_rank = 1
            ORDER BY timestamp DESC LIMIT ?
        """
        params = ['600000', '1d', 250]

        # 先各预热一次
        perf_db.execute(old_sql, params).fetchall()
        perf_db.execute(new_sql, params).fetchall()

        old_ms = _avg_ms(lambda: perf_db.execute(old_sql, params).fetchall())
        new_ms = _avg_ms(lambda: perf_db.execute(new_sql, params).fetchall())

        print(f"\n[P0-2 view_query] monitor 行数={N_MONITOR_SYMBOLS * N_SOURCES * N_MONITOR_DAYS:,} "
              f"old(全表GROUP BY)={old_ms:.2f}ms  new(JOIN monitor_latest)={new_ms:.2f}ms  "
              f"提速={(1 - new_ms / old_ms) * 100:.1f}%")
        # 物化表 JOIN 应显著快于全表 GROUP BY（阈值 60%，宽松防 flaky）
        assert new_ms <= old_ms * 0.6, \
            f"P0-2 物化未生效: old={old_ms:.2f}ms new={new_ms:.2f}ms"
        # 正确性：两 SQL 结果行数一致
        assert len(perf_db.execute(old_sql, params).fetchall()) == \
            len(perf_db.execute(new_sql, params).fetchall())


# ---------------------------------------------------------------------------
# P0-1：读前质量分直查 DB vs 缓存命中
# ---------------------------------------------------------------------------
class TestQualityScoreCachePerf:
    """_get_db_quality_score：直查 DB vs 缓存命中（第二次调用）"""

    def test_cache_hit_vs_db_query(self, perf_db):
        udm = object.__new__(UnifiedDataManager)
        udm.duckdb_available = True
        udm._quality_score_cache = {}
        udm._quality_cache_lock = threading.RLock()
        udm._quality_cache_ttl = 300

        def fake_execute_query(database_path, query, params):
            df = perf_db.execute(query, params).df()
            return SimpleNamespace(success=True, data=df)

        udm.duckdb_operations = SimpleNamespace(execute_query=fake_execute_query)
        udm.asset_manager = SimpleNamespace(get_database_path=lambda at: ':memory:')

        # 直查（首次，未命中缓存）
        db_ms = _avg_ms(lambda: udm._get_db_quality_score('600000', '1d'))
        # 缓存命中（已写入缓存）
        cache_ms = _avg_ms(lambda: udm._get_db_quality_score('600000', '1d'))

        print(f"\n[P0-1 质量分缓存] db(直查)={db_ms:.4f}ms  cache(命中)={cache_ms:.4f}ms  "
              f"提速={(1 - cache_ms / db_ms) * 100:.1f}%")
        assert cache_ms <= db_ms * 0.6, \
            f"P0-1 缓存未生效: db={db_ms:.2f}ms cache={cache_ms:.2f}ms"
        # 值一致性
        assert udm._get_db_quality_score('600000', '1d') is not None


# ---------------------------------------------------------------------------
# P1-2：表结构元数据查询 vs 会话级缓存命中
# ---------------------------------------------------------------------------
class TestSchemaCachePerf:
    """_ensure_table_exists / _get_table_columns：无缓存查询 vs 缓存命中"""

    def test_ensure_table_exists_cache(self, perf_db):
        mgr = AssetSeparatedDatabaseManager.__new__(AssetSeparatedDatabaseManager)
        mgr._table_exists_cache = {}
        mgr._table_columns_cache = {}
        mgr._generate_create_table_sql = lambda *a, **k: ''
        mgr._create_table_indexes = lambda *a, **k: None
        mgr._migrate_table_schema = lambda *a, **k: None

        conn = perf_db.cursor()

        # 首次：真实 duckdb_tables 查询
        first_ms = _avg_ms(
            lambda: mgr._ensure_table_exists(conn, 'historical_kline_data', None, DataType.HISTORICAL_KLINE))
        # 二次：命中会话级缓存
        cached_ms = _avg_ms(
            lambda: mgr._ensure_table_exists(conn, 'historical_kline_data', None, DataType.HISTORICAL_KLINE))

        print(f"\n[P1-2 表存在缓存] first(duckdb_tables)={first_ms:.4f}ms  cached(命中)={cached_ms:.4f}ms  "
              f"提速={(1 - cached_ms / first_ms) * 100:.1f}%")
        assert cached_ms <= first_ms * 0.6, \
            f"P1-2 表结构缓存未生效: first={first_ms:.2f}ms cached={cached_ms:.2f}ms"

    def test_get_table_columns_cache(self, perf_db):
        mgr = AssetSeparatedDatabaseManager.__new__(AssetSeparatedDatabaseManager)
        mgr._table_exists_cache = {}
        mgr._table_columns_cache = {}
        conn = perf_db.cursor()

        first_ms = _avg_ms(lambda: mgr._get_table_columns(conn, 'historical_kline_data'))
        cached_ms = _avg_ms(lambda: mgr._get_table_columns(conn, 'historical_kline_data'))

        print(f"\n[P1-2 列名缓存] first(duckdb_columns)={first_ms:.4f}ms  cached(命中)={cached_ms:.4f}ms  "
              f"提速={(1 - cached_ms / first_ms) * 100:.1f}%")
        assert cached_ms <= first_ms * 0.6, \
            f"P1-2 列名缓存未生效: first={first_ms:.2f}ms cached={cached_ms:.2f}ms"
        assert 'timestamp' in mgr._get_table_columns(conn, 'historical_kline_data')


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
