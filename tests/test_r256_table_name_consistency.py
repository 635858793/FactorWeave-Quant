#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R256 回归测试: 财务/基本面数据表名一致性修复

缺陷实证（主智能体交叉验证 + 源码行号）:
- unified_data_manager._store_financial_to_duckdb: ensure_table_exists 生成带插件后缀表名
  （financial_statement_unified_data_manager_default），但 insert_dataframe 硬编码
  表名 "financial_statements"（复数）→ 建表与写入表名分裂
- unified_data_manager._get_financial_from_duckdb: SELECT * FROM financial_statements
  → 读取与建表表名分裂
- enhanced_duckdb_data_downloader._store_fundamental_data_to_duckdb: 传字符串
  data_type 调 ensure（且误用 await 同步方法），insert 硬编码复数表名 → 分裂

修复原则（低风险统一）:
- ensure 建的表名（ensure_table_exists 返回值 / generate_table_name 同一路径）作为
  insert / query 的统一基准表名，保证"建表、写入、读取"三者同表。
"""
import asyncio
import unittest
from unittest.mock import MagicMock

from core.database.table_manager import DEFAULT_FINANCIAL_PLUGIN, TableType
from core.plugin_types import AssetType
from core.services.enhanced_duckdb_data_downloader import EnhancedDuckDBDataDownloader
from core.services.unified_data_manager import UnifiedDataManager

# 与统一表名生成器 SIMPLE 模式（{data_type}_{plugin_name}_{period}）一致的预期表名
# R257 起：两组件统一使用 DEFAULT_FINANCIAL_PLUGIN（"system"），读写同一张表
EXPECTED_UDM_FINANCIAL = "financial_statement_system_default"
EXPECTED_ENHANCED_FINANCIAL = "financial_statement_system_default"
EXPECTED_ENHANCED_ANNOUNCEMENT = "announcement_system_default"


def _make_financial_dict() -> dict:
    return {"symbol": "000001", "report_date": "2024-01-01", "total_assets": 100.0}


class TestFinancialStoreTableNameConsistency(unittest.TestCase):
    """T01: _store_financial_to_duckdb 中 ensure 建表名 == insert 表名"""

    def _make_manager(self):
        mgr = object.__new__(UnifiedDataManager)
        mgr.duckdb_available = True
        mgr.duckdb_operations = MagicMock()
        mgr.duckdb_operations.insert_dataframe = MagicMock(
            return_value=MagicMock(success=True))
        mgr.table_manager = MagicMock()
        mgr.asset_manager = MagicMock()
        mgr.asset_manager.get_database_path = MagicMock(return_value="/tmp/financial.db")
        mgr.asset_identifier = MagicMock()
        mgr.asset_identifier.identify_asset_type = MagicMock(return_value=AssetType.STOCK_A)
        return mgr

    def test_store_insert_uses_ensured_table_name(self):
        """insert_dataframe 的表名必须等于 ensure_table_exists 返回的实际表名"""
        mgr = self._make_manager()
        mgr.table_manager.ensure_table_exists = MagicMock(return_value=EXPECTED_UDM_FINANCIAL)

        asyncio.run(mgr._store_financial_to_duckdb("000001", _make_financial_dict()))

        # ensure 使用 TableType.FINANCIAL_STATEMENT + 统一插件名 DEFAULT_FINANCIAL_PLUGIN（R257）
        from core.database.table_manager import TableType
        ensure_args, _ = mgr.table_manager.ensure_table_exists.call_args
        self.assertEqual(ensure_args[1], TableType.FINANCIAL_STATEMENT)
        self.assertEqual(ensure_args[2], DEFAULT_FINANCIAL_PLUGIN)

        _, insert_kwargs = mgr.duckdb_operations.insert_dataframe.call_args
        self.assertEqual(insert_kwargs["table_name"], EXPECTED_UDM_FINANCIAL)
        # 核心断言：insert 表名 == ensure 返回的表名
        self.assertEqual(insert_kwargs["table_name"], mgr.table_manager.ensure_table_exists.return_value)

    def test_store_returns_without_insert_when_ensure_fails(self):
        """ensure 建表失败（返回 None）时中止，不再以旧表名写入"""
        mgr = self._make_manager()
        mgr.table_manager.ensure_table_exists = MagicMock(return_value=None)

        asyncio.run(mgr._store_financial_to_duckdb("000001", _make_financial_dict()))

        mgr.duckdb_operations.insert_dataframe.assert_not_called()


class TestFinancialQueryTableNameConsistency(unittest.TestCase):
    """T02: _get_financial_from_duckdb 查询表名与 store 写入表名一致"""

    def _make_manager(self):
        mgr = object.__new__(UnifiedDataManager)
        mgr.duckdb_operations = MagicMock()
        mgr.duckdb_operations.execute_query = MagicMock(
            return_value=MagicMock(success=True, data=[{"symbol": "000001"}]))
        mgr.table_manager = MagicMock()
        mgr.asset_manager = MagicMock()
        mgr.asset_manager.get_database_path = MagicMock(return_value="/tmp/financial.db")
        mgr.asset_identifier = MagicMock()
        mgr.asset_identifier.identify_asset_type = MagicMock(return_value=AssetType.STOCK_A)
        return mgr

    def test_query_uses_same_generated_table_name(self):
        """查询 SQL 中的表名 == generate_table_name(TableType.FINANCIAL_STATEMENT, DEFAULT_FINANCIAL_PLUGIN)"""
        mgr = self._make_manager()
        mgr.table_manager.generate_table_name = MagicMock(return_value=EXPECTED_UDM_FINANCIAL)

        result = asyncio.run(mgr._get_financial_from_duckdb("000001"))

        # generate 使用与 store.ensure 完全相同的参数（同一表名来源）
        from core.database.table_manager import TableType
        gen_args, _ = mgr.table_manager.generate_table_name.call_args
        self.assertEqual(gen_args[0], TableType.FINANCIAL_STATEMENT)
        self.assertEqual(gen_args[1], DEFAULT_FINANCIAL_PLUGIN)

        _, query_kwargs = mgr.duckdb_operations.execute_query.call_args
        self.assertIn(f"FROM {EXPECTED_UDM_FINANCIAL}", query_kwargs["query"])
        self.assertIsNotNone(result)

    def test_store_and_query_share_same_table_name_source(self):
        """store.ensure 与 query.generate 使用同一生成逻辑 → 表名必然一致"""
        mgr = self._make_manager()
        # 同一 mock 表名生成函数：ensure(3参: db, tt, plugin) 与 generate(2参: tt, plugin) 走同一逻辑
        def fake_name(*args):
            table_type, plugin = args[-2], args[-1]
            return f"{table_type.value}_{plugin}_default"

        mgr.table_manager.ensure_table_exists = MagicMock(side_effect=fake_name)
        mgr.table_manager.generate_table_name = MagicMock(side_effect=fake_name)

        asyncio.run(mgr._store_financial_to_duckdb("000001", _make_financial_dict()))
        _, insert_kwargs = mgr.duckdb_operations.insert_dataframe.call_args
        store_name = insert_kwargs["table_name"]

        asyncio.run(mgr._get_financial_from_duckdb("000001"))
        _, query_kwargs = mgr.duckdb_operations.execute_query.call_args

        self.assertEqual(store_name, f"financial_statement_{DEFAULT_FINANCIAL_PLUGIN}_default")
        self.assertIn(f"FROM {store_name}", query_kwargs["query"])


class TestFundamentalStoreTableNameConsistency(unittest.TestCase):
    """T03: enhanced._store_fundamental_data_to_duckdb ensure 建表名 == insert 表名"""

    def _make_downloader(self):
        dl = object.__new__(EnhancedDuckDBDataDownloader)
        dl.asset_db_manager = MagicMock()
        dl.asset_db_manager.get_database_path = MagicMock(return_value="/tmp/fundamental.db")
        dl.table_manager = MagicMock()
        dl.duckdb_operations = MagicMock()
        dl.duckdb_operations.insert_dataframe = MagicMock(
            return_value=MagicMock(success=True))
        return dl

    def test_financial_statement_uses_ensured_table_name(self):
        """financial_statement: ensure 传 TableType 枚举，insert 表名 == ensure 返回表名"""
        dl = self._make_downloader()
        dl.table_manager.ensure_table_exists = MagicMock(return_value=EXPECTED_ENHANCED_FINANCIAL)

        asyncio.run(dl._store_fundamental_data_to_duckdb({"total_assets": 1.0}, "000001", "financial_statement"))

        from core.database.table_manager import TableType
        ensure_args, _ = dl.table_manager.ensure_table_exists.call_args
        self.assertEqual(ensure_args[1], TableType.FINANCIAL_STATEMENT)
        self.assertEqual(ensure_args[2], DEFAULT_FINANCIAL_PLUGIN)

        _, insert_kwargs = dl.duckdb_operations.insert_dataframe.call_args
        self.assertEqual(insert_kwargs["table_name"], EXPECTED_ENHANCED_FINANCIAL)
        self.assertEqual(insert_kwargs["table_name"], dl.table_manager.ensure_table_exists.return_value)

    def test_announcement_uses_ensured_table_name(self):
        """announcement: 使用 TableType.ANNOUNCEMENT 建表，insert 表名一致"""
        dl = self._make_downloader()
        dl.table_manager.ensure_table_exists = MagicMock(return_value=EXPECTED_ENHANCED_ANNOUNCEMENT)

        asyncio.run(dl._store_fundamental_data_to_duckdb({"title": "公告"}, "000001", "announcement"))

        from core.database.table_manager import TableType
        ensure_args, _ = dl.table_manager.ensure_table_exists.call_args
        self.assertEqual(ensure_args[1], TableType.ANNOUNCEMENT)

        _, insert_kwargs = dl.duckdb_operations.insert_dataframe.call_args
        self.assertEqual(insert_kwargs["table_name"], EXPECTED_ENHANCED_ANNOUNCEMENT)
        self.assertEqual(insert_kwargs["table_name"], dl.table_manager.ensure_table_exists.return_value)

    def test_analyst_rating_keeps_legacy_name(self):
        """analyst_rating 无 TableType 映射：不 ensure（无 schema），沿用旧硬编码表名"""
        dl = self._make_downloader()

        asyncio.run(dl._store_fundamental_data_to_duckdb({"rating": "买入"}, "000001", "analyst_rating"))

        dl.table_manager.ensure_table_exists.assert_not_called()
        _, insert_kwargs = dl.duckdb_operations.insert_dataframe.call_args
        self.assertEqual(insert_kwargs["table_name"], "analyst_ratings")

    def test_unknown_data_type_returns_early(self):
        """未知 data_type 直接返回，不建表不插入"""
        dl = self._make_downloader()

        asyncio.run(dl._store_fundamental_data_to_duckdb({"x": 1}, "000001", "unknown_type"))

        dl.table_manager.ensure_table_exists.assert_not_called()
        dl.duckdb_operations.insert_dataframe.assert_not_called()


class TestRealGeneratedTableNames(unittest.TestCase):
    """T04: 真实统一表名生成器输出（锁定修复后表名格式，防回归）"""

    def _make_table_manager(self):
        from core.database.table_manager import DynamicTableManager
        return object.__new__(DynamicTableManager)

    def test_udm_financial_table_name_format(self):
        from core.database.table_manager import TableType
        tm = self._make_table_manager()
        self.assertEqual(
            tm.generate_table_name(TableType.FINANCIAL_STATEMENT, DEFAULT_FINANCIAL_PLUGIN),
            EXPECTED_UDM_FINANCIAL,
        )

    def test_enhanced_financial_table_name_format(self):
        from core.database.table_manager import TableType
        tm = self._make_table_manager()
        self.assertEqual(
            tm.generate_table_name(TableType.FINANCIAL_STATEMENT, DEFAULT_FINANCIAL_PLUGIN),
            EXPECTED_ENHANCED_FINANCIAL,
        )

    def test_enhanced_announcement_table_name_format(self):
        from core.database.table_manager import TableType
        tm = self._make_table_manager()
        self.assertEqual(
            tm.generate_table_name(TableType.ANNOUNCEMENT, DEFAULT_FINANCIAL_PLUGIN),
            EXPECTED_ENHANCED_ANNOUNCEMENT,
        )

    def test_cross_component_financial_table_unified(self):
        """R257：两组件使用统一插件名 → 财报表名完全一致（读写同表）"""
        self.assertEqual(EXPECTED_UDM_FINANCIAL, EXPECTED_ENHANCED_FINANCIAL)
        self.assertIn("system", EXPECTED_UDM_FINANCIAL)


if __name__ == '__main__':
    unittest.main()
