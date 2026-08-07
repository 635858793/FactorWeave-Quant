#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R257 回归测试: 跨组件财报表名统一治理

缺陷实证（R257 根因，主智能体交叉验证 + 源码行号）:
- unified_data_manager（读+写）: generate_table_name / ensure_table_exists 传插件名
  'unified_data_manager' → financial_statement_unified_data_manager_default
  （core/services/unified_data_manager.py:2943 / :2985）
- enhanced_duckdb_data_downloader（写）: ensure_table_exists 传插件名
  'enhanced_duckdb_downloader' → financial_statement_enhanced_duckdb_downloader_default
  （core/services/enhanced_duckdb_data_downloader.py:1136）
- 同一「财报」业务数据两组件生成不同表名 → 下载数据写而无读 + 每次读回落 TET 网络调用

R257 修复:
- 统一插件名常量 DEFAULT_FINANCIAL_PLUGIN = "system"（core/database/table_manager.py 顶层）
- 两组件读写统一到 financial_statement_system_default
- unified_data_manager 新增 _migrate_legacy_financial_tables 惰性迁移旧表（不 DROP，失败仅 warning）
"""
import asyncio
import unittest
from unittest.mock import MagicMock

from core.database.table_manager import DEFAULT_FINANCIAL_PLUGIN, TableType
from core.plugin_types import AssetType
from core.services import unified_data_manager as udm_mod
from core.services.enhanced_duckdb_data_downloader import EnhancedDuckDBDataDownloader
from core.services.unified_data_manager import UnifiedDataManager

# 统一后的财报表名（SIMPLE 模式 {data_type}_{plugin_name}_default）
UNIFIED_FINANCIAL_TABLE = "financial_statement_system_default"

# R257 治理前的分裂旧表名
LEGACY_TABLES = (
    "financial_statement_unified_data_manager_default",
    "financial_statement_enhanced_duckdb_downloader_default",
)


def _reset_migration_flag():
    udm_mod._financial_migration_done = False


class TestUDMReadUsesUnifiedPlugin(unittest.TestCase):
    """T01: unified_data_manager 读路径 generate_table_name 使用统一插件名"""

    def setUp(self):
        _reset_migration_flag()

    def tearDown(self):
        _reset_migration_flag()

    def _make_manager(self):
        mgr = object.__new__(UnifiedDataManager)
        mgr.duckdb_available = True
        mgr.duckdb_operations = MagicMock()
        mgr.duckdb_operations.execute_query = MagicMock(
            return_value=MagicMock(success=True, data=[]))
        mgr.table_manager = MagicMock()
        mgr.table_manager.generate_table_name = MagicMock(return_value=UNIFIED_FINANCIAL_TABLE)
        mgr.asset_manager = MagicMock()
        mgr.asset_manager.get_database_path = MagicMock(return_value="/tmp/financial.db")
        mgr.asset_identifier = MagicMock()
        mgr.asset_identifier.identify_asset_type = MagicMock(return_value=AssetType.STOCK_A)
        return mgr

    def test_get_financial_generates_unified_table_name(self):
        mgr = self._make_manager()
        asyncio.run(mgr._get_financial_from_duckdb("000001"))

        gen_args, _ = mgr.table_manager.generate_table_name.call_args
        self.assertEqual(gen_args[0], TableType.FINANCIAL_STATEMENT)
        self.assertEqual(gen_args[1], DEFAULT_FINANCIAL_PLUGIN)
        self.assertNotEqual(gen_args[1], "unified_data_manager")


class TestEnhancedWriteUsesUnifiedPlugin(unittest.TestCase):
    """T02: enhanced_duckdb_data_downloader 写路径 ensure_table_exists 使用统一插件名"""

    def _make_downloader(self):
        dl = object.__new__(EnhancedDuckDBDataDownloader)
        dl.asset_db_manager = MagicMock()
        dl.asset_db_manager.get_database_path = MagicMock(return_value="/tmp/fundamental.db")
        dl.table_manager = MagicMock()
        dl.duckdb_operations = MagicMock()
        dl.duckdb_operations.insert_dataframe = MagicMock(return_value=MagicMock(success=True))
        return dl

    def test_store_financial_ensures_unified_table(self):
        dl = self._make_downloader()
        dl.table_manager.ensure_table_exists = MagicMock(return_value=UNIFIED_FINANCIAL_TABLE)

        asyncio.run(dl._store_fundamental_data_to_duckdb(
            {"total_assets": 1.0}, "000001", "financial_statement"))

        ensure_args, _ = dl.table_manager.ensure_table_exists.call_args
        self.assertEqual(ensure_args[1], TableType.FINANCIAL_STATEMENT)
        self.assertEqual(ensure_args[2], DEFAULT_FINANCIAL_PLUGIN)
        self.assertNotEqual(ensure_args[2], "enhanced_duckdb_downloader")


class TestCrossComponentSameTableName(unittest.TestCase):
    """T03: 两组件生成的财报表名相同（统一插件名 → 同一张表）"""

    def test_generated_names_identical(self):
        from core.database.table_manager import DynamicTableManager
        tm = object.__new__(DynamicTableManager)

        udm_name = tm.generate_table_name(TableType.FINANCIAL_STATEMENT, DEFAULT_FINANCIAL_PLUGIN)
        enhanced_name = tm.generate_table_name(TableType.FINANCIAL_STATEMENT, DEFAULT_FINANCIAL_PLUGIN)

        self.assertEqual(udm_name, enhanced_name)
        self.assertEqual(udm_name, UNIFIED_FINANCIAL_TABLE)

    def test_write_paths_resolve_to_same_table(self):
        """UDM 与 enhanced 两条写路径最终 insert 表名一致（同一表名生成来源）"""
        fake_tm = MagicMock()

        def fake_name(*args, **kwargs):
            table_type, plugin = args[-2], args[-1]
            return f"{table_type.value}_{plugin}_default"

        fake_tm.generate_table_name = MagicMock(side_effect=fake_name)
        fake_tm.ensure_table_exists = MagicMock(side_effect=fake_name)

        # UDM 写路径
        udm = object.__new__(UnifiedDataManager)
        udm.duckdb_available = True
        udm.duckdb_operations = MagicMock()
        udm.duckdb_operations.insert_dataframe = MagicMock(return_value=MagicMock(success=True))
        udm.duckdb_operations.execute_query = MagicMock(
            return_value=MagicMock(success=True, data=[]))
        udm.table_manager = fake_tm
        udm.asset_manager = MagicMock()
        udm.asset_manager.get_database_path = MagicMock(return_value="/tmp/f.db")
        udm.asset_identifier = MagicMock()
        udm.asset_identifier.identify_asset_type = MagicMock(return_value=AssetType.STOCK_A)
        asyncio.run(udm._store_financial_to_duckdb(
            "000001", {"symbol": "000001", "report_date": "2024-01-01", "total_assets": 1.0}))
        udm_insert = udm.duckdb_operations.insert_dataframe.call_args.kwargs["table_name"]

        # enhanced 写路径
        dl = object.__new__(EnhancedDuckDBDataDownloader)
        dl.asset_db_manager = MagicMock()
        dl.asset_db_manager.get_database_path = MagicMock(return_value="/tmp/f.db")
        dl.table_manager = fake_tm
        dl.duckdb_operations = MagicMock()
        dl.duckdb_operations.insert_dataframe = MagicMock(return_value=MagicMock(success=True))
        asyncio.run(dl._store_fundamental_data_to_duckdb(
            {"symbol": "000001"}, "000001", "financial_statement"))
        dl_insert = dl.duckdb_operations.insert_dataframe.call_args.kwargs["table_name"]

        self.assertEqual(udm_insert, dl_insert)
        self.assertEqual(udm_insert, UNIFIED_FINANCIAL_TABLE)


class TestLegacyMigration(unittest.TestCase):
    """T04: 旧财报表惰性迁移存在且执行 INSERT INTO 合并（不 DROP）"""

    def setUp(self):
        _reset_migration_flag()

    def tearDown(self):
        _reset_migration_flag()

    def _make_manager(self, legacy_rows=1):
        mgr = object.__new__(UnifiedDataManager)
        mgr.duckdb_available = True
        mgr.duckdb_operations = MagicMock()
        # 存在性检测：所有旧表都检测到（cnt=legacy_rows）
        mgr.duckdb_operations.execute_query = MagicMock(
            return_value=MagicMock(success=True, data=[{"cnt": legacy_rows}]))
        mgr.duckdb_operations.execute_sql = MagicMock(return_value=MagicMock(success=True))
        mgr.table_manager = MagicMock()
        mgr.table_manager.generate_table_name = MagicMock(return_value=UNIFIED_FINANCIAL_TABLE)
        mgr.table_manager.ensure_table_exists = MagicMock(return_value=UNIFIED_FINANCIAL_TABLE)
        mgr.asset_manager = MagicMock()
        mgr.asset_manager.get_database_path = MagicMock(return_value="/tmp/financial.db")
        mgr.asset_identifier = MagicMock()
        return mgr

    def test_migration_function_exists(self):
        self.assertTrue(hasattr(UnifiedDataManager, "_migrate_legacy_financial_tables"))

    def test_migration_merges_legacy_into_unified(self):
        mgr = self._make_manager()
        mgr._migrate_legacy_financial_tables("/tmp/financial.db")

        # 统一新表用 DEFAULT_FINANCIAL_PLUGIN 建表
        ensure_args, _ = mgr.table_manager.ensure_table_exists.call_args
        self.assertEqual(ensure_args[1], TableType.FINANCIAL_STATEMENT)
        self.assertEqual(ensure_args[2], DEFAULT_FINANCIAL_PLUGIN)

        # 每个旧表各执行一次 INSERT INTO 新表 ... ON CONFLICT DO NOTHING
        self.assertEqual(mgr.duckdb_operations.execute_sql.call_count, len(LEGACY_TABLES))
        for call in mgr.duckdb_operations.execute_sql.call_args_list:
            sql = call.args[1]
            self.assertIn(f"INSERT INTO {UNIFIED_FINANCIAL_TABLE}", sql)
            self.assertIn("SELECT * FROM", sql)
            self.assertIn("ON CONFLICT (symbol, report_date, report_type) DO NOTHING", sql)

        self.assertTrue(udm_mod._financial_migration_done)

    def test_migration_skips_when_no_legacy_table(self):
        mgr = self._make_manager(legacy_rows=0)
        mgr._migrate_legacy_financial_tables("/tmp/financial.db")
        mgr.duckdb_operations.execute_sql.assert_not_called()
        self.assertTrue(udm_mod._financial_migration_done)

    def test_migration_failure_does_not_break(self):
        """INSERT 失败（列名不匹配等）→ 仅 warning，不阻断，标志仍置位"""
        mgr = self._make_manager()
        mgr.duckdb_operations.execute_sql = MagicMock(
            return_value=MagicMock(success=False, error_message="column mismatch"))
        mgr._migrate_legacy_financial_tables("/tmp/financial.db")  # 不应抛异常
        self.assertTrue(udm_mod._financial_migration_done)


class TestMigrationIdempotent(unittest.TestCase):
    """T05: 迁移幂等（模块级标志防重复执行）"""

    def setUp(self):
        _reset_migration_flag()

    def tearDown(self):
        _reset_migration_flag()

    def test_second_call_skips(self):
        mgr = object.__new__(UnifiedDataManager)
        mgr.duckdb_available = True
        mgr.duckdb_operations = MagicMock()
        mgr.duckdb_operations.execute_query = MagicMock(
            return_value=MagicMock(success=True, data=[{"cnt": 1}]))
        mgr.duckdb_operations.execute_sql = MagicMock(return_value=MagicMock(success=True))
        mgr.table_manager = MagicMock()
        mgr.table_manager.generate_table_name = MagicMock(return_value=UNIFIED_FINANCIAL_TABLE)
        mgr.table_manager.ensure_table_exists = MagicMock(return_value=UNIFIED_FINANCIAL_TABLE)
        mgr.asset_manager = MagicMock()
        mgr.asset_identifier = MagicMock()

        mgr._migrate_legacy_financial_tables("/tmp/financial.db")
        calls_after_first = mgr.duckdb_operations.execute_sql.call_count
        self.assertGreater(calls_after_first, 0)

        mgr._migrate_legacy_financial_tables("/tmp/financial.db")
        self.assertEqual(mgr.duckdb_operations.execute_sql.call_count, calls_after_first)


if __name__ == '__main__':
    unittest.main()
