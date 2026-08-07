"""R253 板块资金流域 P0/P1 修复验证

覆盖:
- P0-2: _batch_insert_sector_data 插入列与 sector_fund_flow_daily 表结构对齐
- P0-1: 三个 _query_*_from_database 接真实 DuckDB 执行（注入 mock 连接）
- P0-1: 连接不可用/表不存在时降级返回空 DataFrame
- P1:   SectorFundFlowService.cleanup/get_service_status 属性初始化后不再抛 AttributeError
"""

import re
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.r253, pytest.mark.sector_fund_flow]


# ==================== 测试辅助 ====================

class _FakeConn:
    """模拟 duckdb 连接：execute(sql).fetchdf() / executemany(sql, records)"""

    def __init__(self, df: pd.DataFrame = None):
        self._df = df if df is not None else pd.DataFrame()
        self.executed_sql = None
        self.executed_records = None

    def execute(self, sql):
        self.executed_sql = sql
        return self

    def executemany(self, sql, records):
        self.executed_sql = sql
        self.executed_records = records

    def fetchdf(self):
        return self._df


class _FakeDuckDBManager:
    """模拟 DuckDBConnectionManager（get_connection 为 contextmanager）"""

    def __init__(self, df: pd.DataFrame = None, error: Exception = None):
        self._df = df
        self._error = error
        self.conn = _FakeConn(df)

    @contextmanager
    def get_connection(self, database_path: str):
        if self._error is not None:
            raise self._error
        yield self.conn


def _make_sector_service():
    """构造 SectorDataService 实例（duckdb_manager 用 mock 替换）"""
    from core.services.sector_data_service import SectorDataService
    service = SectorDataService()
    service.duckdb_manager = _FakeDuckDBManager()
    return service


def _standardized_sector_df() -> pd.DataFrame:
    """构造与 _standardize_sector_data 输出一致的 DataFrame"""
    return pd.DataFrame({
        'date': ['2025-06-20', '2025-06-20'],
        'sector_name': ['房地产', '医药生物'],
        'sector_code': ['BK0001', 'BK0002'],
        'period': ['今日', '今日'],
        'main_net_inflow': [1000.0, 2000.0],
        'main_net_inflow_ratio': [0.15, 0.25],
        'super_large_net_inflow': [500.0, 600.0],
        'large_net_inflow': [400.0, 500.0],
        'medium_net_inflow': [300.0, 400.0],
        'small_net_inflow': [200.0, 300.0],
        'change_percent': [1.5, 2.5],
        'turnover_rate': [3.0, 4.0],
        'volume': [100, 200],
        'amount': [1000, 2000],
        'created_at': ['2025-06-20T10:00:00', '2025-06-20T10:00:00'],
    })


def _parse_insert_columns(sql: str):
    """从 INSERT SQL 中解析插入列名列表"""
    match = re.search(r"INSERT INTO sector_fund_flow_daily \(([^)]+)\)", sql)
    assert match is not None, f"无法解析 INSERT 列名: {sql}"
    return [c.strip() for c in match.group(1).split(',')]


# ==================== P0-2: 插入列与表结构对齐 ====================

class TestBatchInsertColumnAlignment:

    def test_insert_columns_are_subset_of_table_schema(self):
        """P0-2: _batch_insert_sector_data 的插入列必须全部存在于表结构真实列中"""
        from core.database.table_manager import TableType, get_table_manager

        service = _make_sector_service()
        df = _standardized_sector_df()

        # 注入捕获连接的 manager
        fake_mgr = _FakeDuckDBManager()
        service.duckdb_manager = fake_mgr

        count = service._batch_insert_sector_data(df)

        assert count == len(df)
        assert fake_mgr.conn is not None, "应真实执行 executemany"
        insert_columns = _parse_insert_columns(fake_mgr.conn.executed_sql)

        schema = get_table_manager().get_schema(TableType.SECTOR_FUND_FLOW_DAILY)
        assert schema is not None, "sector_fund_flow_daily 表结构未注册"
        schema_columns = set(schema.columns.keys())

        assert set(insert_columns).issubset(schema_columns), \
            f"插入列不在表结构中: {set(insert_columns) - schema_columns}"
        assert len(insert_columns) > 0

    def test_legacy_invalid_columns_removed(self):
        """P0-2: 表结构中不存在的旧插入列（date/period/main_net_inflow_ratio 等）必须被移除或映射"""
        from core.database.table_manager import TableType, get_table_manager

        service = _make_sector_service()
        fake_mgr = _FakeDuckDBManager()
        service.duckdb_manager = fake_mgr

        count = service._batch_insert_sector_data(_standardized_sector_df())
        assert count == 2

        insert_columns = set(_parse_insert_columns(fake_mgr.conn.executed_sql))
        schema_columns = set(get_table_manager().get_schema(
            TableType.SECTOR_FUND_FLOW_DAILY).columns.keys())

        # 旧实现中的非法列名不得出现
        for invalid in ['date', 'period', 'main_net_inflow_ratio',
                        'super_large_net_inflow', 'large_net_inflow',
                        'medium_net_inflow', 'small_net_inflow',
                        'change_percent', 'turnover_rate', 'volume', 'amount']:
            assert invalid not in insert_columns, f"非法列 {invalid} 仍出现在插入列中"

        # 映射后的真实列应出现
        for mapped in ['trade_date', 'avg_change_pct', 'total_turnover']:
            assert mapped in insert_columns, f"映射列 {mapped} 缺失"

        # 记录长度与列数一致
        assert len(fake_mgr.conn.executed_sql) > 0
        assert set(insert_columns) <= schema_columns

    def test_required_columns_filled_when_missing(self):
        """P0-2: 数据源未提供 sector_id/data_source 时自动补齐必填列"""
        from core.database.table_manager import TableType, get_table_manager

        service = _make_sector_service()
        fake_mgr = _FakeDuckDBManager()
        service.duckdb_manager = fake_mgr

        df = _standardized_sector_df().drop(columns=['sector_code'])
        count = service._batch_insert_sector_data(df)
        assert count == 2

        schema = get_table_manager().get_schema(TableType.SECTOR_FUND_FLOW_DAILY)
        # sector_id 为 NOT NULL 必填列，补齐后插入不会缺列
        insert_columns = set(_parse_insert_columns(fake_mgr.conn.executed_sql))
        assert 'sector_id' in insert_columns
        assert 'data_source' in insert_columns
        assert insert_columns <= set(schema.columns.keys())


# ==================== P0-1: 三个查询方法接真实 DuckDB ====================

class TestQueryFromDatabase:

    def test_ranking_query_returns_data(self):
        """P0-1: _query_ranking_from_database 注入 mock 连接时返回非空 DataFrame"""
        service = _make_sector_service()
        expected = pd.DataFrame({
            'sector_id': ['BK0001', 'BK0002'],
            'sector_name': ['房地产', '医药生物'],
            'main_net_inflow': [1000.0, 2000.0],
        })
        service.duckdb_manager = _FakeDuckDBManager(df=expected)

        result = service._query_ranking_from_database('2025-06-20', 'main_net_inflow')

        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert len(result) == 2
        assert list(result.columns) == list(expected.columns)

    def test_trend_query_returns_data(self):
        """P0-1: _query_trend_from_database 注入 mock 连接时返回非空 DataFrame"""
        service = _make_sector_service()
        expected = pd.DataFrame({
            'sector_id': ['BK0001'],
            'trade_date': ['2025-05-21'],
            'main_net_inflow': [888.0],
        })
        service.duckdb_manager = _FakeDuckDBManager(df=expected)

        result = service._query_trend_from_database('BK0001', 30)

        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert len(result) == 1

    def test_intraday_query_returns_data(self):
        """P0-1: _query_intraday_from_database 注入 mock 连接时返回非空 DataFrame"""
        service = _make_sector_service()
        expected = pd.DataFrame({
            'sector_id': ['BK0001'],
            'trade_time': ['09:30:00'],
            'cumulative_main_inflow': [123.0],
        })
        service.duckdb_manager = _FakeDuckDBManager(df=expected)

        result = service._query_intraday_from_database('BK0001', '2025-06-20')

        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert len(result) == 1


# ==================== P0-1: 降级行为 ====================

class TestQueryDegradation:

    def test_query_returns_empty_when_manager_unavailable(self):
        """P0-1: duckdb_manager 为 None 时三个查询均返回空 DataFrame 且不抛异常"""
        service = _make_sector_service()
        service.duckdb_manager = None

        assert service._query_ranking_from_database('2025-06-20', 'main_net_inflow').empty
        assert service._query_trend_from_database('BK0001', 30).empty
        assert service._query_intraday_from_database('BK0001', '2025-06-20').empty

    def test_query_returns_empty_when_table_missing(self):
        """P0-1: 表不存在（Catalog Error）时三个查询降级返回空 DataFrame 且不抛异常"""
        service = _make_sector_service()
        table_missing_error = RuntimeError(
            "Catalog Error: Table with name sector_fund_flow_daily does not exist")
        service.duckdb_manager = _FakeDuckDBManager(error=table_missing_error)

        assert service._query_ranking_from_database('2025-06-20', 'main_net_inflow').empty
        assert service._query_trend_from_database('BK0001', 30).empty
        assert service._query_intraday_from_database('BK0001', '2025-06-20').empty

    def test_query_returns_empty_on_generic_error(self):
        """P0-1: 其他数据库错误时同样降级返回空 DataFrame 不抛异常"""
        service = _make_sector_service()
        service.duckdb_manager = _FakeDuckDBManager(error=RuntimeError("connection broken"))

        assert service._query_ranking_from_database('2025-06-20', 'main_net_inflow').empty


# ==================== P1: SectorFundFlowService 属性初始化 ====================

class TestSectorFundFlowServiceAttributes:

    def test_cleanup_no_attribute_error(self):
        """P1: cleanup 在属性初始化后不抛 AttributeError"""
        from core.services.sector_fund_flow_service import SectorFundFlowService

        service = SectorFundFlowService()

        # 修复前这些属性不存在，cleanup 会抛 AttributeError
        assert isinstance(service._cache, dict)
        assert isinstance(service._cache_lock, type(threading.RLock()))
        assert isinstance(service._cache_timestamps, dict)

        service.cleanup()  # 不应抛异常

    def test_get_service_status_references_cache(self):
        """P1: get_service_status 引用 _cache 不再抛 AttributeError"""
        from core.services.sector_fund_flow_service import SectorFundFlowService

        service = SectorFundFlowService()
        status = service.get_service_status()

        assert status['cache_size'] == 0
        assert 'is_initialized' in status
        assert 'auto_refresh_enabled' in status
