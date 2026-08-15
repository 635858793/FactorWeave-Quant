#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R292 高价值修复回归测试（TDD）

覆盖三项高价值缺陷修复：
  P0 数据丢失：import_execution_engine 的 DatabaseWriterThread 在每次任务结束的
     finally 中被 stop（防丢数据），但同一引擎连续执行第二个任务时写线程已死 →
     put_write_task 入队无人消费 → 数据静默丢失。修复：任务执行前检测线程存活，
     非存活则重建新实例并 start（threading.Thread 不可复用）。
  P1 静默降级：enhanced_duckdb_data_downloader 增量下载链路硬编码日线 + A 股，
     分钟/周/月线或非 A 股资产的增量任务按日线 frequency 落库污染日线视图或写错
     数据库文件。修复：period/asset_type 从增量入口逐层透传。
  P1 频率映射缺口：import_config_manager 的 DUCKDB_FREQUENCY_TO_DATA_FREQUENCY
     与 tongdaxin_plugin 的 period_map 缺键，导致 UI 任务向导/查询静默降级日线。
"""
import os
import sys
import asyncio
from datetime import datetime
import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from core.plugin_types import AssetType, DataType, Period
from core.importdata.models import WriteTask
from core.importdata.database_writer import DatabaseWriterThread
from core.importdata.import_execution_engine import DataImportExecutionEngine as ImportExecutionEngine
from core.importdata.import_config_manager import DUCKDB_FREQUENCY_TO_DATA_FREQUENCY, DataFrequency
from core.services.enhanced_duckdb_data_downloader import EnhancedDuckDBDataDownloader
from core.services.incremental_data_analyzer import DownloadStrategy
from core.tet_data_pipeline import StandardQuery
from plugins.data_sources.stock.tongdaxin_plugin import TongdaxinStockPlugin


def _kline_df(n: int = 5) -> pd.DataFrame:
    """构造简单日线 DataFrame（模拟插件返回数据）"""
    closes = np.linspace(10.0, 12.0, n)
    return pd.DataFrame({
        'datetime': pd.date_range('2026-08-01', periods=n, freq='D'),
        'open': closes - 0.1,
        'high': closes + 0.2,
        'low': closes - 0.2,
        'close': closes,
        'volume': np.linspace(10000, 20000, n),
        'amount': np.linspace(1e6, 2e6, n),
    })


def _write_task() -> WriteTask:
    return WriteTask(
        buffer_key='stock_a_test',
        data=_kline_df(),
        asset_type=AssetType.STOCK_A,
        data_type=DataType.HISTORICAL_KLINE,
    )


# =========================================================================
# P0：DatabaseWriterThread 停止后重建
# =========================================================================
class _StubEngine:
    """仅持有 db_writer_thread 属性的轻量 stub。

    DataImportExecutionEngine 为 QObject 子类无法轻量实例化（与
    test_r292_save_axis_guard 的 unbound 调用先例一致），故以 unbound
    方式调用引擎的 _ensure_db_writer_thread(self=stub)。
    """
    pass


class TestDatabaseWriterRebuild:
    """P0：写线程 stop 后不可复用，任务执行前必须重建"""

    def test_stopped_writer_not_alive(self):
        """stop(wait=True) 后线程必须退出（is_alive False），即不可复用"""
        writer = DatabaseWriterThread()
        writer.start()
        writer.stop(wait=True, timeout=5.0)
        assert not writer.is_alive(), "stop 后线程仍存活，重建逻辑依赖的检测失效"

    def test_engine_rebuilds_dead_writer_and_can_write(self):
        """模拟 finally stop 后执行第二个任务：_ensure_db_writer_thread 必须重建线程且可写入"""
        stub = _StubEngine()

        # 第一个任务结束时 finally 强制 stop
        writer = DatabaseWriterThread()
        writer.start()
        writer.stop(wait=True, timeout=5.0)
        assert not writer.is_alive()
        stub.db_writer_thread = writer

        # 第二个任务执行前：检测并重建
        ImportExecutionEngine._ensure_db_writer_thread(stub)

        assert stub.db_writer_thread is not writer, "死线程未被重建（threading.Thread 不可复用）"
        assert stub.db_writer_thread.is_alive(), "重建后的写线程未启动"
        assert stub.db_writer_thread.write_queue.maxsize == 5000

        # 重建后必须可正常入队（有消费者）
        assert stub.db_writer_thread.put_write_task(_write_task(), timeout=2.0) is True
        stub.db_writer_thread.stop(wait=True, timeout=5.0)

    def test_engine_keeps_live_writer(self):
        """线程存活时不得重建（保持同一实例，避免无谓重启）"""
        stub = _StubEngine()
        writer = DatabaseWriterThread()
        writer.start()
        stub.db_writer_thread = writer

        ImportExecutionEngine._ensure_db_writer_thread(stub)
        assert stub.db_writer_thread is writer, "存活线程被误重建"
        writer.stop(wait=True, timeout=5.0)


# =========================================================================
# P1：增量下载链路 period/asset_type 透传
# =========================================================================
def _make_downloader() -> EnhancedDuckDBDataDownloader:
    dl = EnhancedDuckDBDataDownloader(uni_plugin_manager=MagicMock())
    dl.data_source_router = None
    dl.uni_plugin_manager.create_request_context = AsyncMock(return_value=MagicMock())
    dl.uni_plugin_manager.execute_data_request = AsyncMock(return_value=_kline_df())
    dl._validate_and_clean_kline_data = MagicMock(return_value=_kline_df())
    dl._store_kline_data_incremental = AsyncMock(return_value=10)
    return dl


class TestIncrementalDownloadPassthrough:
    """P1：_download_single_symbol 构造 StandardQuery 时 period/asset_type 来自传入参数"""

    def test_single_symbol_passes_period_and_asset_type(self):
        """period='5m' → StandardQuery.period='5min'，asset_type 透传，存储层收到原始参数"""
        dl = _make_downloader()
        start, end = datetime(2026, 1, 1), datetime(2026, 1, 31)

        async def _run():
            result = await dl._download_single_symbol(
                '00700', (start, end), DownloadStrategy.LATEST_ONLY,
                period='5m', asset_type=AssetType.STOCK_HK,
            )
            return result

        result = asyncio.run(_run())
        assert result['records_count'] == 10

        ctx = dl.uni_plugin_manager.create_request_context.call_args[0][0]
        assert isinstance(ctx, StandardQuery)
        assert ctx.asset_type == AssetType.STOCK_HK, "StandardQuery.asset_type 未透传（仍硬编码 A 股）"
        assert ctx.extra_params['period'] == '5min', "StandardQuery.period 未按传入周期归一（仍硬编码日线）"
        store_args = dl._store_kline_data_incremental.await_args.args
        assert store_args[0].equals(_kline_df())
        assert store_args[1:] == ('00700', DownloadStrategy.LATEST_ONLY, '5m', AssetType.STOCK_HK)

    def test_single_symbol_defaults_preserve_legacy_behavior(self):
        """无参调用（既有调用方）默认 period='D'→'1d'、asset_type=STOCK_A，不得改变行为"""
        dl = _make_downloader()
        start, end = datetime(2026, 1, 1), datetime(2026, 1, 31)

        async def _run():
            await dl._download_single_symbol('000001', (start, end), DownloadStrategy.LATEST_ONLY)

        asyncio.run(_run())
        ctx = dl.uni_plugin_manager.create_request_context.call_args[0][0]
        assert ctx.asset_type == AssetType.STOCK_A
        assert ctx.extra_params['period'] == '1d'
        store_args = dl._store_kline_data_incremental.await_args.args
        assert store_args[0].equals(_kline_df())
        assert store_args[1:] == ('000001', DownloadStrategy.LATEST_ONLY, 'D', AssetType.STOCK_A)

    def test_batch_passthrough(self):
        """_download_symbol_batch → _download_single_symbol 透传 period/asset_type"""
        dl = EnhancedDuckDBDataDownloader(uni_plugin_manager=MagicMock())
        dl._download_single_symbol = AsyncMock(return_value={'records_count': 1})
        start, end = datetime(2026, 1, 1), datetime(2026, 1, 31)
        ranges = {'000001': (start, end)}

        async def _run():
            await dl._download_symbol_batch(
                ['000001'], ranges, DownloadStrategy.LATEST_ONLY,
                period='W', asset_type=AssetType.STOCK_H)

        asyncio.run(_run())
        dl._download_single_symbol.assert_awaited_once_with(
            '000001', (start, end), DownloadStrategy.LATEST_ONLY, 'W', AssetType.STOCK_H)

    def test_incremental_entry_passthrough(self):
        """download_incremental_data → _download_symbol_batch 透传 period/asset_type"""
        dl = EnhancedDuckDBDataDownloader(uni_plugin_manager=MagicMock())
        dl.data_source_router = None

        class _Plan:
            symbols_to_download = ['000001']
            symbols_to_skip = []
            symbols_to_skip_reason = {}
            download_ranges = {'000001': (datetime(2026, 1, 1), datetime(2026, 1, 31))}

        dl.incremental_analyzer = MagicMock()
        dl.incremental_analyzer.analyze_incremental_requirements = AsyncMock(return_value=_Plan())
        dl.completeness_checker = MagicMock()
        dl.update_recorder = MagicMock()
        dl.update_recorder.create_update_task.return_value = 'task_1'
        dl._download_symbol_batch = AsyncMock(
            return_value={'success_count': 1, 'failed_count': 0, 'total_records': 10})

        async def _run():
            await dl.download_incremental_data(
                ['000001'], datetime(2026, 1, 31),
                period='1H', asset_type=AssetType.STOCK_US)

        asyncio.run(_run())
        dl._download_symbol_batch.assert_awaited_once_with(
            ['000001'], _Plan.download_ranges, DownloadStrategy.LATEST_ONLY, '1H', AssetType.STOCK_US)

    def test_incremental_update_all_passthrough(self):
        """download_incremental_update_all_data → download_incremental_data 透传，且资产列表按 asset_type 获取"""
        dl = EnhancedDuckDBDataDownloader(uni_plugin_manager=MagicMock())
        dl._get_symbols_from_database = AsyncMock(
            return_value=pd.DataFrame({'code': ['000001', '000002']}))
        dl.download_incremental_data = AsyncMock(return_value={
            'success_count': 2, 'failed_count': 0, 'skipped_count': 0,
            'total_records': 10, 'execution_time': 1.0})

        async def _run():
            await dl.download_incremental_update_all_data(days=7, period='monthly', asset_type=AssetType.STOCK_H)

        asyncio.run(_run())
        dl._get_symbols_from_database.assert_awaited_once_with(AssetType.STOCK_H)
        dl.download_incremental_data.assert_awaited_once()
        kwargs = dl.download_incremental_data.await_args.kwargs
        assert kwargs['period'] == 'monthly'
        assert kwargs['asset_type'] == AssetType.STOCK_H


# =========================================================================
# P1：DUCKDB_FREQUENCY_TO_DATA_FREQUENCY 映射补键
# =========================================================================
class TestFrequencyMapping:
    """P1：频率映射必须覆盖 Period.to_duckdb_frequency 全部输出 + UI 常见别名"""

    def test_map_covers_to_duckdb_frequency_output(self):
        """Period.to_duckdb_frequency 的全部输出都必须在映射表中（否则任务向导静默降级日线）"""
        for p in Period:
            duck = Period.to_duckdb_frequency(p.value)
            assert duck in DUCKDB_FREQUENCY_TO_DATA_FREQUENCY, f"缺映射键: {duck!r}"

    def test_new_keys_semantics(self):
        """补键语义：'1h'/'1H'→HOUR_1、'weekly'→WEEKLY、'monthly'→MONTHLY、'tick'→TICK"""
        assert DUCKDB_FREQUENCY_TO_DATA_FREQUENCY['1h'] is DataFrequency.HOUR_1
        assert DUCKDB_FREQUENCY_TO_DATA_FREQUENCY['1H'] is DataFrequency.HOUR_1
        assert DUCKDB_FREQUENCY_TO_DATA_FREQUENCY['weekly'] is DataFrequency.WEEKLY
        assert DUCKDB_FREQUENCY_TO_DATA_FREQUENCY['monthly'] is DataFrequency.MONTHLY
        assert DUCKDB_FREQUENCY_TO_DATA_FREQUENCY['tick'] is DataFrequency.TICK

    def test_roundtrip_no_daily_fallback_for_known_freqs(self):
        """所有已知频率经映射后不得落到 DAILY（静默降级）"""
        assert DUCKDB_FREQUENCY_TO_DATA_FREQUENCY['60min'] is not DataFrequency.DAILY
        assert DUCKDB_FREQUENCY_TO_DATA_FREQUENCY['1M'] is DataFrequency.MONTHLY
        assert DUCKDB_FREQUENCY_TO_DATA_FREQUENCY['1w'] is DataFrequency.WEEKLY


# =========================================================================
# P1：tongdaxin_plugin period_map 反向键 + 未知频率 warning
# =========================================================================
class TestTongdaxinPeriodMap:
    """P1：get_kdata period_map 反向键补齐，未知频率不再静默降级"""

    @pytest.fixture
    def plugin(self):
        p = TongdaxinStockPlugin()
        p.get_kline_data = MagicMock(return_value=pd.DataFrame())
        return p

    @pytest.mark.parametrize('freq,expected', [
        ('weekly', 'weekly'),
        ('monthly', 'monthly'),
        ('daily', 'daily'),
        ('1min', '1min'),
        ('5min', '5min'),
        ('15min', '15min'),
        ('30min', '30min'),
        ('60min', '60min'),
    ])
    def test_reverse_keys(self, plugin, freq, expected):
        """反向键：get_kdata(freq='weekly'/'monthly'/'daily'/'Nmin') 不再静默降级日线"""
        plugin.get_kdata('000001', freq=freq)
        assert plugin.get_kline_data.call_args[1]['period'] == expected, f"freq={freq} 未透传为 {expected}"

    def test_unknown_frequency_warns_and_falls_back(self, plugin):
        """未知频率必须 logger.warning 提示，不再静默默认日线"""
        with patch.object(plugin, 'logger') as mock_logger:
            plugin.get_kdata('000001', freq='xyz')
        assert plugin.get_kline_data.call_args[1]['period'] == 'daily', "未知频率应兜底日线"
        assert mock_logger.warning.called, "未知频率未输出 warning 提示"
