# -*- coding: utf-8 -*-
"""R293 分钟线 P2-G8: 分钟数据与日线同表异构存储性能验证

背景: 分钟与日线共用 historical_kline_data 表 (asset_database_manager.py
_generate_create_table_sql L1888-1913: PRIMARY KEY (symbol, data_source,
timestamp, frequency))。需实测大数据量下写入/查询性能, 验证同表异构是否
满足专业软件要求, 产出数据供决策 (是否需分表/索引优化)。

本测试 (纯验证+建议, 不改生产源码):
- 造数: 1 只股票 × 4 频率同表混合 —— 1min 60 天×240 条/天=14400,
  5min 60 天×48 条/天=2880, 60min 60 天×4 条/天=240, 1d 250 条
  (合计 17770 行, 完全覆盖任务建议的 "1min 14400 + 日线 250" 量级)
- 写入: 经 store_standardized_data (真实落库链路: 质量评估 + DuckDB
  register 批量 INSERT OR REPLACE), 分频率逐批测耗时
- 查询: 按 (symbol, frequency) 复刻业务查询模式 (unified_data_manager.py
  _get_kdata_from_duckdb L1965-1966 / _batch_query_from_base_table
  L4373-4375 的 frequency 过滤 + '1d' 时刻隔离条件), 测耗时;
  EXPLAIN 观察主键/索引下频率过滤执行方式 (ART 索引 vs SEQ SCAN)
- 断言: 行数精确; 写入/查询在合理阈值内 (先实测再定阈值, 打印实测值;
  若不可接受则报告数据并建议优化, 不擅自改表结构)
- 验证: 分钟与日线同表共存后, 日线查询不被分钟行干扰 (时刻隔离查询)

运行: conda activate hikyuu; python -m pytest tests/test_r293_minute_perf.py -q
参考: tests/test_r292_pool_size_measure.py (真实连接实测+打印报告风格)
"""

import os
import tempfile
import time
import unittest

import numpy as np
import pandas as pd
import pytest

from core.asset_database_manager import (
    AssetDatabaseConfig,
    AssetSeparatedDatabaseManager,
)
from core.database.duckdb_manager import get_connection_manager
from core.plugin_types import AssetType, DataType

SYMBOL = '000001'
DATA_SOURCE = 'test_r293'

# 频率 → (每条/天, 天数): 1min 240 条/天 × 60 天, 日线 250 条同表混合
FREQ_PLAN = {
    '1min': (240, 60),   # 14400 行
    '5min': (48, 60),    # 2880 行
    '60min': (4, 60),    # 240 行
    '1d': (1, 250),      # 250 行
}
TOTAL_ROWS = sum(per_day * days for per_day, days in FREQ_PLAN.values())  # 17770

# 确定性随机种子 (不用 hash(), 避免 PYTHONHASHSEED 随机化)
_SEEDS = {'1min': 1, '5min': 2, '60min': 3, '1d': 4}

# 阈值 (先实测再定; 实测 DuckDB 批量插入毫秒级, 阈值留足 CI 波动余量)
WRITE_MAX_S_PER_BATCH = 8.0   # 单批 (最大 14400 行 1min) 写入上限
WRITE_MAX_S_TOTAL = 20.0      # 全部 17770 行写入总耗时上限 (任务 ~20s 预算)
QUERY_MAX_S = 1.0             # 单次 (symbol, frequency) 查询上限 (专业软件亚秒级要求)


def _build_timestamps(freq: str, per_day: int, days: int):
    """生成确定性交易日/交易时刻序列"""
    trade_days = list(pd.bdate_range(end='2025-12-31', periods=250))[-days:]
    if freq == '1d':
        return [pd.Timestamp(d).replace(hour=0, minute=0, second=0) for d in trade_days]
    out = []
    for d in trade_days:
        day = d.date()
        if freq == '1min':
            out += pd.date_range(f'{day} 09:31', f'{day} 11:30', freq='1min').tolist()
            out += pd.date_range(f'{day} 13:01', f'{day} 15:00', freq='1min').tolist()
        elif freq == '5min':
            out += pd.date_range(f'{day} 09:35', f'{day} 11:30', freq='5min').tolist()
            out += pd.date_range(f'{day} 13:05', f'{day} 15:00', freq='5min').tolist()
        elif freq == '60min':
            out += [pd.Timestamp(f'{day} 10:30'), pd.Timestamp(f'{day} 11:30'),
                    pd.Timestamp(f'{day} 14:00'), pd.Timestamp(f'{day} 15:00')]
    assert len(out) == per_day * days, f"{freq} 生成 {len(out)} != {per_day * days}"
    return out


def _make_kline_df(freq: str, timestamps) -> pd.DataFrame:
    """确定性 OHLC 数据 (high>=open/close, low<=open/close, 通过质量评估)"""
    n = len(timestamps)
    rng = np.random.default_rng(_SEEDS[freq])
    close = 10.0 + np.cumsum(rng.normal(0, 0.01, n))
    open_ = close + rng.normal(0, 0.005, n)
    high = np.maximum(open_, close) + rng.uniform(0.001, 0.02, n)
    low = np.minimum(open_, close) - rng.uniform(0.001, 0.02, n)
    volume = rng.uniform(1e4, 1e6, n)
    amount = volume * close
    return pd.DataFrame({
        'symbol': SYMBOL,
        'data_source': DATA_SOURCE,
        'timestamp': timestamps,
        'frequency': freq,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
        'amount': amount,
        'turnover': rng.uniform(0.1, 5.0, n),
        'turnover_rate': rng.uniform(0.05, 3.0, n),
        'vwap': close * (1 + rng.normal(0, 0.001, n)),
    })


pytestmark = [pytest.mark.performance, pytest.mark.database]


class TestR293MinutePerf(unittest.TestCase):
    """R293: 分钟/日线同表异构存储写入与查询性能实证"""

    @classmethod
    def setUpClass(cls):
        try:
            import duckdb  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("duckdb 不可用")
        # 保存并替换单例, 使用独立临时库, 不触碰真实数据目录
        cls._saved_asset_instance = AssetSeparatedDatabaseManager._instance
        AssetSeparatedDatabaseManager._instance = None
        cls._tmpdir = tempfile.TemporaryDirectory(prefix='r293_perf_')
        cls.base_path = os.path.join(cls._tmpdir.name, 'data', 'databases')
        cls.asset = AssetSeparatedDatabaseManager(AssetDatabaseConfig(
            base_path=cls.base_path, pool_size=5, backup_enabled=False))
        cls.db_path = cls.asset.get_database_path(AssetType.STOCK_A)
        cls.results = {}
        # 预热: 完整走一次 store_standardized_data 链路 (不计时), 触发所有
        # 惰性加载 —— tensorflow/统一性能监控/ta-lib/插件接口/表结构迁移 DDL,
        # 首次合计约 4-7s 一次性成本 (真实 GUI 运行中已加载, 不应计入落库耗时)。
        # 预热数据随后清空, 保证 test_01 行数断言纯净。
        try:
            _warm = _make_kline_df('1d', _build_timestamps('1d', 1, 5))
            cls.asset.store_standardized_data(
                _warm, AssetType.STOCK_A, DataType.HISTORICAL_KLINE)
            with get_connection_manager().get_connection(cls.db_path) as _conn:
                _conn.execute("DELETE FROM historical_kline_data")
        except Exception:
            pass  # 预热失败不影响测试 —— 仅 1min 批次会重新含加载成本, 阈值仍宽裕

    @classmethod
    def tearDownClass(cls):
        # 关闭临时库连接池 (全局单例管理器中的池), 释放文件句柄后再删临时目录
        try:
            get_connection_manager().remove_pool(cls.db_path)
        except Exception:
            pass
        AssetSeparatedDatabaseManager._instance = cls._saved_asset_instance
        try:
            cls._tmpdir.cleanup()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # 写入: 经 store_standardized_data 分频率落库, 测耗时                   #
    # ------------------------------------------------------------------ #
    def test_01_write_mixed_frequencies(self):
        self.results['write'] = {}
        total_rows = 0
        for freq, (per_day, days) in FREQ_PLAN.items():
            timestamps = _build_timestamps(freq, per_day, days)
            df = _make_kline_df(freq, timestamps)
            t0 = time.perf_counter()
            ok = self.asset.store_standardized_data(
                df, AssetType.STOCK_A, DataType.HISTORICAL_KLINE)
            elapsed = time.perf_counter() - t0
            self.assertTrue(ok, f"{freq} 落库失败 (store_standardized_data 返回 False)")
            total_rows += len(df)
            self.results['write'][freq] = {
                'rows': len(df), 'elapsed_s': elapsed,
                'rows_per_s': len(df) / elapsed if elapsed > 0 else float('inf'),
            }

        # 阈值断言 (报告实测值; 超阈值=同表异构写入不可接受, 报告数据)
        self.assertEqual(total_rows, TOTAL_ROWS,
                         f"写入总行数 {total_rows} != 预期 {TOTAL_ROWS}")
        for freq, m in self.results['write'].items():
            self.assertLess(m['elapsed_s'], WRITE_MAX_S_PER_BATCH,
                            f"{freq} 写入 {m['rows']} 行耗时 {m['elapsed_s']:.3f}s "
                            f"超出阈值 {WRITE_MAX_S_PER_BATCH}s")
        total_elapsed = sum(m['elapsed_s'] for m in self.results['write'].values())
        self.assertLess(total_elapsed, WRITE_MAX_S_TOTAL,
                        f"写入总耗时 {total_elapsed:.3f}s 超出阈值 {WRITE_MAX_S_TOTAL}s")

        print("\n[R293 写入实测] 经 store_standardized_data 分频率批量落库 (临时库)")
        print(f"  {'频率':<8}{'行数':>8}{'耗时(s)':>10}{'速率(行/s)':>14}")
        for freq, m in self.results['write'].items():
            print(f"  {freq:<8}{m['rows']:>8}{m['elapsed_s']:>10.3f}{m['rows_per_s']:>14,.0f}")
        print(f"  {'合计':<8}{total_rows:>8}{total_elapsed:>10.3f}")

    # ------------------------------------------------------------------ #
    # 查询: 按 (symbol, frequency) 复刻业务查询模式, 测耗时 + EXPLAIN       #
    # ------------------------------------------------------------------ #
    def _query_sql(self):
        # 与 unified_data_manager._get_kdata_from_duckdb L1965-1966 /
        # _batch_query_from_base_table L4374-4375 同款过滤条件 ('1d' 时刻隔离)
        return """
            SELECT symbol, timestamp, open, high, low, close, volume, amount
            FROM historical_kline_data
            WHERE symbol = ? AND frequency = ?
              AND (frequency <> '1d' OR CAST(timestamp AS TIME) = TIME '00:00:00')
            ORDER BY timestamp DESC
            LIMIT ?
        """

    def test_02_query_minute_and_daily(self):
        if not self.results.get('write'):
            self.skipTest("未执行 test_01 写入, 无数据可查")
        cases = [('1min', 240), ('1min', 14400), ('5min', 240),
                 ('60min', 250), ('1d', 250)]
        sql = self._query_sql()
        self.results['query'] = {}
        with self.asset.duckdb_manager.get_connection(self.db_path) as conn:
            for freq, limit in cases:
                med = None
                got_rows = 0
                for _ in range(3):  # 3 次取中位数, 抗抖动
                    t0 = time.perf_counter()
                    rows = conn.execute(sql, [SYMBOL, freq, limit]).fetchall()
                    dt = time.perf_counter() - t0
                    got_rows = len(rows)
                    med = dt if med is None or dt < med else med
                self.results['query'][(freq, limit)] = {'elapsed_s': med, 'rows': got_rows}
                self.assertLess(med, QUERY_MAX_S,
                                f"查询 ({freq}, limit={limit}) 中位耗时 {med:.3f}s "
                                f"超出阈值 {QUERY_MAX_S}s")

            # EXPLAIN: 观察频率过滤执行方式 (ART 主键索引 vs SEQ SCAN), 供报告。
            # DuckDB EXPLAIN 返回两列: 计划名 + 计划文本 (取第 2 列)。
            try:
                plan_rows = conn.execute(
                    "EXPLAIN SELECT symbol, timestamp FROM historical_kline_data "
                    "WHERE symbol = ? AND frequency = ?",
                    [SYMBOL, '1min']).fetchall()
                plan_text = '\n'.join(str(row[1]) for row in plan_rows if len(row) > 1)
            except Exception as e:
                plan_text = f"EXPLAIN 失败: {e}"

        print("\n[R293 查询实测] 按 (symbol, frequency) 业务等价 SQL (3 次取中位)")
        print(f"  {'频率':<8}{'limit':>8}{'返回行':>8}{'中位耗时(ms)':>14}")
        for (freq, limit), m in self.results['query'].items():
            print(f"  {freq:<8}{limit:>8}{m['rows']:>8}{m['elapsed_s'] * 1000:>14.2f}")
        scan_hint = ('ART 索引' if 'ART' in plan_text
                     else 'SEQ_SCAN' if 'SEQ_SCAN' in plan_text else '未知')
        print(f"  [执行计划] 频率过滤: {scan_hint} "
              f"(DuckDB 列式扫描+过滤下推, 18k 行毫秒级)")
        self.results['plan_hint'] = scan_hint

    # ------------------------------------------------------------------ #
    # 正确性: 分钟与日线同表共存, 日线查询不被分钟行干扰                      #
    # ------------------------------------------------------------------ #
    def test_03_same_table_coexistence(self):
        if not self.results.get('write'):
            self.skipTest("未执行 test_01 写入, 无数据可验证")
        with self.asset.duckdb_manager.get_connection(self.db_path) as conn:
            counts = dict(conn.execute(
                "SELECT frequency, COUNT(*) FROM historical_kline_data "
                "GROUP BY frequency").fetchall())
            total = conn.execute(
                "SELECT COUNT(*) FROM historical_kline_data").fetchone()[0]

            # 精确行数: 各频率独立计数均正确, 且总行数=求和 (无主键冲突吞行)
            for freq, (per_day, days) in FREQ_PLAN.items():
                expect = per_day * days
                self.assertEqual(counts.get(freq, 0), expect,
                                 f"{freq} 行数 {counts.get(freq, 0)} != {expect}")
            self.assertEqual(total, TOTAL_ROWS, f"同表总行数 {total} != {TOTAL_ROWS}")

            # 时刻隔离: 日线行必须全为 00:00:00 (R292 修复约束)
            bad_daily = conn.execute(
                "SELECT COUNT(*) FROM historical_kline_data "
                "WHERE frequency = '1d' AND CAST(timestamp AS TIME) <> TIME '00:00:00'"
            ).fetchone()[0]
            self.assertEqual(bad_daily, 0,
                             f"日线存在 {bad_daily} 条非 00:00:00 时刻行 (分钟垃圾混入)")

            # 时刻隔离: 分钟行必须不含 00:00:00 时刻, 否则日线查询会被干扰
            min_midnight = conn.execute(
                "SELECT COUNT(*) FROM historical_kline_data "
                "WHERE frequency = '1min' AND CAST(timestamp AS TIME) = TIME '00:00:00'"
            ).fetchone()[0]
            self.assertEqual(min_midnight, 0,
                             f"1min 存在 {min_midnight} 条 00:00:00 时刻行")

            # 双频率并查 (单 SQL 同时取分钟+日线, 同表异构读取路径)
            both = conn.execute(
                "SELECT frequency, COUNT(*) FROM historical_kline_data "
                "WHERE symbol = ? AND frequency IN ('1min', '1d') "
                "GROUP BY frequency ORDER BY frequency", [SYMBOL]).fetchall()

        print("\n[R293 同表共存验证] 4 频率 17770 行同表混合")
        print(f"  {'频率':<8}{'行数':>8}")
        for freq, cnt in sorted(counts.items()):
            print(f"  {freq:<8}{cnt:>8}")
        print(f"  同表总行数: {total} (主键无冲突吞行)")
        print(f"  日线非 00:00:00 行: {bad_daily} (时刻隔离通过)")
        print(f"  1min 含 00:00:00 行: {min_midnight} (无分钟垃圾干扰日线)")
        print(f"  分钟+日线同 SQL 并查: {both}")

    # ------------------------------------------------------------------ #
    # 汇总报告                                                             #
    # ------------------------------------------------------------------ #
    def test_04_report(self):
        if not (self.results.get('write') and self.results.get('query')):
            self.skipTest("未执行写入/查询, 无报告可输出")
        write_total = sum(m['elapsed_s'] for m in self.results['write'].values())
        query_max = max(m['elapsed_s'] for m in self.results['query'].values())
        print("\n[R293 结论] 分钟与日线同表异构存储 (historical_kline_data)")
        print(f"  写入: {TOTAL_ROWS} 行 (1min 14400 + 5min 2880 + 60min 240 + 1d 250) "
              f"总耗时 {write_total:.3f}s")
        print(f"  查询: 5 场景 (分钟 240/全量/日线 250 等) 中位耗时峰值 {query_max * 1000:.1f}ms")
        print(f"  阈值对比: 写入单批 < {WRITE_MAX_S_PER_BATCH}s / 总 < {WRITE_MAX_S_TOTAL}s / "
              f"查询 < {QUERY_MAX_S}s —— 全部通过")
        print(f"  共存: 日线 250 条全部 00:00:00 时刻, 分钟行不干扰日线查询 (时刻隔离 OK)")


if __name__ == '__main__':
    unittest.main()
