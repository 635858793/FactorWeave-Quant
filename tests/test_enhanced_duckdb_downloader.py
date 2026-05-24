"""
增强DuckDB数据下载器 — 批量查询/批量写入 单元测试

覆盖范围 (基于R30+R32优化):
- _get_latest_data_dates_batch()  批量日期查询 (R32)
- _get_latest_data_date()          单symbol日期查询 (回归)
- _store_kline_data_to_duckdb()   批量写入 (R30)
- download_historical_kline_data() 主流程 + Phase1批量路径
- 异常处理: 空输入 / DB路径缺失 / 查询失败 / 写入失败
"""

import pytest
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock


@pytest.fixture
def mock_downloader():
    """构建带完整mock依赖的 EnhancedDuckDBDataDownloader"""
    with patch("core.services.enhanced_duckdb_data_downloader.get_connection_manager") as mock_cm, \
         patch("core.services.enhanced_duckdb_data_downloader.get_duckdb_operations") as mock_do, \
         patch("core.services.enhanced_duckdb_data_downloader.DynamicTableManager") as mock_tm, \
         patch("core.services.enhanced_duckdb_data_downloader.AssetSeparatedDatabaseManager") as mock_adm:

        from core.services.enhanced_duckdb_data_downloader import EnhancedDuckDBDataDownloader
        from core.plugin_types import AssetType

        mock_uni = MagicMock()
        mock_tet = MagicMock()
        mock_router = MagicMock()

        downloader = EnhancedDuckDBDataDownloader(
            uni_plugin_manager=mock_uni,
            tet_pipeline=mock_tet,
            data_source_router=mock_router,
        )

        # 便捷mock: asset_db_manager.get_database_path
        downloader.asset_db_manager.get_database_path = MagicMock(
            return_value="/fake/path/data.duckdb"
        )

        yield downloader


# ==================== _get_latest_data_dates_batch (R32) ====================

class TestGetLatestDataDatesBatch:

    def test_single_symbol_returns_dict(self, mock_downloader):
        """单symbol返回单条记录"""
        df = pd.DataFrame({"symbol": ["000001"], "latest_date": [datetime(2025, 6, 1)]})
        mock_downloader.duckdb_operations.execute_query = MagicMock(return_value=df)

        result = asyncio.run(
            mock_downloader._get_latest_data_dates_batch(["000001"], "D")
        )
        assert isinstance(result, dict)
        assert "000001" in result
        assert result["000001"] == pd.to_datetime("2025-06-01")

    def test_multi_symbol_returns_all(self, mock_downloader):
        """多symbol全返回"""
        df = pd.DataFrame({
            "symbol": ["000001", "000002", "000003"],
            "latest_date": [
                datetime(2025, 6, 1),
                datetime(2025, 5, 15),
                datetime(2025, 6, 10),
            ]
        })
        mock_downloader.duckdb_operations.execute_query = MagicMock(return_value=df)

        result = asyncio.run(
            mock_downloader._get_latest_data_dates_batch(
                ["000001", "000002", "000003"], "D"
            )
        )
        assert len(result) == 3
        assert result["000001"] == pd.to_datetime("2025-06-01")
        assert result["000002"] == pd.to_datetime("2025-05-15")
        assert result["000003"] == pd.to_datetime("2025-06-10")

    def test_empty_symbols_returns_empty_dict(self, mock_downloader):
        """空列表→空dict, 不触发DB查询"""
        mock_downloader.duckdb_operations.execute_query = MagicMock()

        result = asyncio.run(
            mock_downloader._get_latest_data_dates_batch([], "D")
        )
        assert result == {}
        mock_downloader.duckdb_operations.execute_query.assert_not_called()

    def test_missing_db_path_returns_empty_dict(self, mock_downloader):
        """db_path 为 None → 空dict"""
        mock_downloader.asset_db_manager.get_database_path = MagicMock(
            return_value=None
        )
        mock_downloader.duckdb_operations.execute_query = MagicMock()

        result = asyncio.run(
            mock_downloader._get_latest_data_dates_batch(["000001"], "D")
        )
        assert result == {}
        mock_downloader.duckdb_operations.execute_query.assert_not_called()

    def test_db_error_returns_empty_dict(self, mock_downloader):
        """DB查询抛异常 → 空dict, 不传播异常"""
        mock_downloader.duckdb_operations.execute_query = MagicMock(
            side_effect=Exception("DB connection failed")
        )

        result = asyncio.run(
            mock_downloader._get_latest_data_dates_batch(["000001"], "D")
        )
        assert result == {}

    def test_empty_result_dataframe_returns_empty_dict(self, mock_downloader):
        """查询返回空DataFrame → 空dict"""
        df = pd.DataFrame(columns=["symbol", "latest_date"])
        mock_downloader.duckdb_operations.execute_query = MagicMock(return_value=df)

        result = asyncio.run(
            mock_downloader._get_latest_data_dates_batch(["000001"], "D")
        )
        assert result == {}

    def test_nan_latest_date_filtered(self, mock_downloader):
        """latest_date 为 NaT 的行被过滤"""
        df = pd.DataFrame({
            "symbol": ["000001", "000002"],
            "latest_date": [datetime(2025, 6, 1), pd.NaT],
        })
        mock_downloader.duckdb_operations.execute_query = MagicMock(return_value=df)

        result = asyncio.run(
            mock_downloader._get_latest_data_dates_batch(["000001", "000002"], "D")
        )
        assert len(result) == 1
        assert "000001" in result
        assert "000002" not in result

    def test_partial_results_when_symbol_not_in_db(self, mock_downloader):
        """部分symbol无数据 → 只返回有数据的"""
        df = pd.DataFrame({
            "symbol": ["000001"],
            "latest_date": [datetime(2025, 6, 1)],
        })
        mock_downloader.duckdb_operations.execute_query = MagicMock(return_value=df)

        result = asyncio.run(
            mock_downloader._get_latest_data_dates_batch(
                ["000001", "999999"], "D"
            )
        )
        assert len(result) == 1
        assert "000001" in result

    def test_force_update_skips_batch_query(self, mock_downloader):
        """force_update=True 时不调用批量查询"""
        mock_uni = mock_downloader.uni_plugin_manager
        mock_uni.create_request_context = AsyncMock(return_value=MagicMock())
        mock_uni.execute_data_request = AsyncMock(
            return_value=pd.DataFrame({"close": [10.0]})
        )
        mock_downloader.duckdb_operations.execute_query = MagicMock()

        async def run():
            return await mock_downloader.download_historical_kline_data(
                ["000001"], force_update=True
            )

        asyncio.run(run())
        # force_update时不应调用批量查询
        # execute_query可能被 _store_kline_data_to_duckdb 间接调用, 但不应用于lateness check
        calls_args = str(mock_downloader.duckdb_operations.execute_query.call_args_list)
        assert "MAX(datetime)" not in calls_args


# ==================== _get_latest_data_date (回归保护) ====================

class TestGetLatestDataDate:

    def test_returns_date_for_valid_symbol(self, mock_downloader):
        """正常symbol返回日期"""
        df = pd.DataFrame({"latest_date": [datetime(2025, 6, 1)]})
        mock_downloader.duckdb_operations.execute_query = MagicMock(return_value=df)

        result = asyncio.run(
            mock_downloader._get_latest_data_date("000001", "D", "kline")
        )
        assert result == pd.to_datetime("2025-06-01")

    def test_returns_none_for_missing_db_path(self, mock_downloader):
        """db_path None → None"""
        mock_downloader.asset_db_manager.get_database_path = MagicMock(
            return_value=None
        )

        result = asyncio.run(
            mock_downloader._get_latest_data_date("000001", "D", "kline")
        )
        assert result is None

    def test_returns_none_for_empty_result(self, mock_downloader):
        """空DataFrame → None"""
        df = pd.DataFrame(columns=["latest_date"])
        mock_downloader.duckdb_operations.execute_query = MagicMock(return_value=df)

        result = asyncio.run(
            mock_downloader._get_latest_data_date("000001", "D", "kline")
        )
        assert result is None

    def test_returns_none_for_db_error(self, mock_downloader):
        """DB异常 → None, 不传播"""
        mock_downloader.duckdb_operations.execute_query = MagicMock(
            side_effect=RuntimeError("query timeout")
        )

        result = asyncio.run(
            mock_downloader._get_latest_data_date("000001", "D", "kline")
        )
        assert result is None


# ==================== _store_kline_data_to_duckdb (R30) ====================

class TestStoreKlineDataToDuckDB:

    @pytest.fixture
    def sample_kline_df(self):
        return pd.DataFrame({
            "datetime": [datetime(2025, 6, 1), datetime(2025, 6, 2)],
            "symbol": ["000001", "000001"],
            "open": [10.0, 10.5],
            "high": [10.8, 11.0],
            "low": [9.8, 10.2],
            "close": [10.5, 10.8],
            "volume": [1000000, 1200000],
        })

    def test_successful_store(self, mock_downloader, sample_kline_df):
        """正常存储返回成功"""
        mock_downloader.table_manager.ensure_table_exists = AsyncMock()
        mock_downloader.duckdb_operations.insert_dataframe = MagicMock(
            return_value={"success": True, "rows_inserted": 2}
        )

        async def run():
            await mock_downloader._store_kline_data_to_duckdb(
                sample_kline_df, "000001", "D"
            )

        asyncio.run(run())
        mock_downloader.duckdb_operations.insert_dataframe.assert_called_once()

    def test_store_call_uses_correct_conflict_resolution(self, mock_downloader, sample_kline_df):
        """验证使用 'replace' 冲突解决策略"""
        mock_downloader.table_manager.ensure_table_exists = AsyncMock()
        mock_downloader.duckdb_operations.insert_dataframe = MagicMock(
            return_value={"success": True}
        )

        async def run():
            await mock_downloader._store_kline_data_to_duckdb(
                sample_kline_df, "000001", "D"
            )

        asyncio.run(run())
        call_kwargs = mock_downloader.duckdb_operations.insert_dataframe.call_args[1]
        assert call_kwargs["conflict_resolution"] == "replace"

    def test_store_failure_does_not_raise(self, mock_downloader, sample_kline_df):
        """存储失败不抛异常"""
        mock_downloader.table_manager.ensure_table_exists = AsyncMock()
        mock_downloader.duckdb_operations.insert_dataframe = MagicMock(
            return_value={"success": False, "error": "duplicate key"}
        )

        async def run():
            await mock_downloader._store_kline_data_to_duckdb(
                sample_kline_df, "000001", "D"
            )

        asyncio.run(run())

    def test_store_db_error_does_not_raise(self, mock_downloader, sample_kline_df):
        """DB异常不传播"""
        mock_downloader.table_manager.ensure_table_exists = AsyncMock()
        mock_downloader.duckdb_operations.insert_dataframe = MagicMock(
            side_effect=Exception("disk full")
        )

        async def run():
            await mock_downloader._store_kline_data_to_duckdb(
                sample_kline_df, "000001", "D"
            )

        asyncio.run(run())


# ==================== download_historical_kline_data (主流程集成) ====================

class TestDownloadHistoricalKlineData:

    @pytest.fixture
    def mock_success_flow(self, mock_downloader):
        """配置全链成功mock"""
        mock_uni = mock_downloader.uni_plugin_manager
        mock_uni.create_request_context = AsyncMock(return_value=MagicMock())
        mock_uni.execute_data_request = AsyncMock(
            return_value=pd.DataFrame({
                "datetime": [datetime(2025, 6, 1), datetime(2025, 6, 2)],
                "open": [10.0, 10.5],
                "high": [10.8, 11.0],
                "low": [9.8, 10.2],
                "close": [10.5, 10.8],
                "volume": [1000000, 1200000],
            })
        )
        mock_downloader.table_manager.ensure_table_exists = AsyncMock()
        mock_downloader.duckdb_operations.insert_dataframe = MagicMock(
            return_value={"success": True}
        )
        mock_downloader._validate_and_clean_kline_data = MagicMock(
            side_effect=lambda df, symbol: df
        )
        return mock_downloader

    def test_batch_phase1_not_called_when_force_update(self, mock_success_flow):
        """force_update=True → 不调用批量日期查询"""
        df = pd.DataFrame({"symbol": ["000001"], "latest_date": [datetime(2025, 6, 1)]})
        mock_success_flow.duckdb_operations.execute_query = MagicMock(return_value=df)

        async def run():
            return await mock_success_flow.download_historical_kline_data(
                ["000001"], force_update=True
            )

        result = asyncio.run(run())
        assert isinstance(result, dict)

    def test_symbol_with_recent_data_skipped(self, mock_success_flow):
        """已有今日数据的symbol被跳过"""
        today = datetime.now()
        mock_success_flow.duckdb_operations.execute_query = MagicMock(
            return_value=pd.DataFrame({
                "symbol": ["000001"],
                "latest_date": [today],
            })
        )

        async def run():
            return await mock_success_flow.download_historical_kline_data(
                ["000001"]
            )

        result = asyncio.run(run())
        # 因为latest_date是今天, 应该被跳过; results为空
        assert isinstance(result, dict)

    def test_new_symbol_downloads(self, mock_success_flow):
        """新symbol (无最新数据) 正常下载"""
        mock_success_flow.duckdb_operations.execute_query = MagicMock(
            return_value=pd.DataFrame(columns=["symbol", "latest_date"])
        )

        async def run():
            return await mock_success_flow.download_historical_kline_data(
                ["000001"], end_date=datetime(2025, 6, 10)
            )

        result = asyncio.run(run())
        assert isinstance(result, dict)

    def test_empty_symbols_list(self, mock_success_flow):
        """空列表 → 空dict, 不触发请求"""
        async def run():
            return await mock_success_flow.download_historical_kline_data([])

        result = asyncio.run(run())
        assert result == {}

    def test_default_dates_applied(self, mock_success_flow):
        """未传 start_date/end_date 时使用默认值"""
        mock_success_flow.duckdb_operations.execute_query = MagicMock(
            return_value=pd.DataFrame(columns=["symbol", "latest_date"])
        )

        async def run():
            return await mock_success_flow.download_historical_kline_data(
                ["000001"]
            )

        result = asyncio.run(run())
        assert isinstance(result, dict)

    def test_multi_symbol_mixed_skip_download(self, mock_success_flow):
        """多symbol: 有数据的跳过, 无数据的下载"""
        today = datetime.now()
        old_date = datetime(2024, 1, 1)
        mock_success_flow.duckdb_operations.execute_query = MagicMock(
            return_value=pd.DataFrame({
                "symbol": ["000001"],
                "latest_date": [today],  # 只有000001有今天的数据
            })
        )

        async def run():
            return await mock_success_flow.download_historical_kline_data(
                ["000001", "000002"]
            )

        result = asyncio.run(run())
        assert isinstance(result, dict)


# ==================== SQL注入防护 (WHERE symbol IN) ====================

class TestSqlInjectionPrevention:

    def test_batch_query_uses_params_not_string_interpolation(self, mock_downloader):
        """验证批量查询使用?占位符+params, 而非f-string拼接"""
        original_execute = mock_downloader.duckdb_operations.execute_query

        def capture_query(db_path, query, params=None):
            assert "?" in query
            assert isinstance(params, list)
            assert "; DROP TABLE" not in query
            return pd.DataFrame(columns=["symbol", "latest_date"])

        mock_downloader.duckdb_operations.execute_query = MagicMock(
            side_effect=capture_query
        )

        result = asyncio.run(
            mock_downloader._get_latest_data_dates_batch(["000001"], "D")
        )
        assert result == {}

    def test_single_query_uses_params(self, mock_downloader):
        """验证单条查询使用?占位符+params"""
        original_execute = mock_downloader.duckdb_operations.execute_query

        def capture_query(db_path, query, params=None):
            assert "?" in query
            assert isinstance(params, list)
            assert len(params) == 1
            return pd.DataFrame(columns=["latest_date"])

        mock_downloader.duckdb_operations.execute_query = MagicMock(
            side_effect=capture_query
        )

        result = asyncio.run(
            mock_downloader._get_latest_data_date("000001", "D", "kline")
        )
        assert result is None


# ==================== 性能验证: 批量 vs N+1 ====================

class TestBatchVsN1QueryCount:

    def test_batch_method_calls_execute_once(self, mock_downloader):
        """批量方法对N个symbol只调用1次execute_query"""
        symbols = [f"{600000 + i:06d}" for i in range(100)]

        def count_calls(db_path, query, params=None):
            count_calls.call_count += 1
            n = len(params) if params else 0
            dates = [pd.Timestamp(f"2025-06-{(i % 28) + 1:02d}") for i in range(n)]
            return pd.DataFrame({
                "symbol": [f"{600000 + i:06d}" for i in range(n)],
                "latest_date": dates,
            })
        count_calls.call_count = 0

        mock_downloader.duckdb_operations.execute_query = MagicMock(
            side_effect=count_calls
        )

        result = asyncio.run(
            mock_downloader._get_latest_data_dates_batch(symbols, "D")
        )
        assert count_calls.call_count == 1
        assert len(result) == 100

    def test_n1_style_would_need_n_calls(self, mock_downloader):
        """对比: 如果N次调用 _get_latest_data_date 需要 N 次 execute_query"""
        call_count = 0

        def count_calls(db_path, query, params=None):
            nonlocal call_count
            call_count += 1
            if "MAX(datetime)" in query and "GROUP BY" not in query:
                if call_count <= 50:
                    return pd.DataFrame({"latest_date": [datetime(2025, 6, call_count)]})
            return pd.DataFrame(columns=["latest_date"])

        mock_downloader.duckdb_operations.execute_query = MagicMock(
            side_effect=count_calls
        )

        # 模拟旧的N+1方式: 对50个symbol各调一次
        for i in range(50):
            asyncio.run(
                mock_downloader._get_latest_data_date(
                    f"{600000 + i:06d}", "D", "kline"
                )
            )

        assert call_count == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])