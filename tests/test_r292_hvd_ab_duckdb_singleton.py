#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R292-HVD-A/B 测试: DuckDBConnectionManager 单例收敛 + 连接池大小收敛

HVD-A: AssetSeparatedDatabaseManager 自持实例收敛为 get_connection_manager()
       模块级单例 (消除同 DB 双池 + R288/R289 配置假生效), 配套:
       - initialize_duckdb_manager 幂等化 (防 SectorDataService 懒加载重建双实例)
       - asset.close_all_connections 不再 close_all_pools (防误关全局共享池)
HVD-B: get_connection/restart_pool 默认池大小 15→10 (与 get_pool 默认 10、
       AssetDatabaseConfig.pool_size 默认 10 对齐), 启动预热/新建库/元数据
       直调路径显式传 self.config.pool_size 使配置真正生效 (120→8×配置连接)

- T01: asset 实例持有 get_connection_manager() 单例 (源码断言)
- T02: initialize_duckdb_manager 幂等 (单例已存在时不重建)
- T03: get_connection 默认 pool_size=10
- T04: restart_pool 默认 pool_size=10
- T05: asset.close_all_connections 不再调用 close_all_pools (防误关全局池)
- T06: 启动预热/新建库建池路径显式传 self.config.pool_size
"""
import inspect
import unittest
from unittest.mock import MagicMock, patch

from core.database import duckdb_manager as dm
from core.database.duckdb_manager import (
    DuckDBConnectionManager,
    initialize_duckdb_manager,
)
from core.asset_database_manager import AssetSeparatedDatabaseManager


class TestDuckDBManagerSingleton(unittest.TestCase):

    def tearDown(self):
        # 恢复全局单例, 避免污染其他测试
        dm._connection_manager = None

    def test_T01_asset_uses_singleton(self):
        src = inspect.getsource(AssetSeparatedDatabaseManager.__init__)
        self.assertIn('get_connection_manager()', src,
                      "asset 应使用 get_connection_manager() 单例而非直接构造")
        self.assertNotIn('= DuckDBConnectionManager()', src,
                         "asset 不应直接构造 DuckDBConnectionManager")

    def test_T02_initialize_idempotent(self):
        saved = dm._connection_manager
        dm._connection_manager = None
        try:
            with patch.object(dm, 'DuckDBConnectionManager') as mock_cls:
                mock_cls.return_value = MagicMock()
                m1 = initialize_duckdb_manager()
                m2 = initialize_duckdb_manager()
                mock_cls.assert_called_once()
                self.assertIs(m1, m2,
                              "单例已存在时 initialize_duckdb_manager 应返回同一实例")
        finally:
            dm._connection_manager = saved

    def test_T03_get_connection_default_pool_size_10(self):
        sig = inspect.signature(DuckDBConnectionManager.get_connection)
        self.assertEqual(sig.parameters['pool_size'].default, 10,
                         "get_connection 默认池大小应为 10 (原15, R292-HVD-B)")

    def test_T04_restart_pool_default_pool_size_10(self):
        sig = inspect.signature(DuckDBConnectionManager.restart_pool)
        self.assertEqual(sig.parameters['pool_size'].default, 10,
                         "restart_pool 默认池大小应为 10 (原15, R292-HVD-B)")

    def test_T05_asset_close_all_connections_no_global_pool_close(self):
        import re
        src = inspect.getsource(AssetSeparatedDatabaseManager.close_all_connections)
        # 剥离 docstring (解释性文字含 close_all_pools 关键词), 仅检查可执行代码
        body = re.sub(r'"""[\s\S]*?"""', '', src, count=1)
        self.assertNotIn('close_all_pools', body,
                         "收敛后 close_all_connections 可执行代码不应调用 close_all_pools")

    def test_T06_prewarm_paths_pass_config_pool_size(self):
        schema_src = inspect.getsource(
            AssetSeparatedDatabaseManager._initialize_database_schema)
        create_src = inspect.getsource(
            AssetSeparatedDatabaseManager._create_asset_database)
        collect_src = inspect.getsource(
            AssetSeparatedDatabaseManager._collect_database_info)
        for src, name in ((schema_src, '_initialize_database_schema'),
                          (create_src, '_create_asset_database'),
                          (collect_src, '_collect_database_info')):
            self.assertIn('pool_size=self.config.pool_size', src,
                          f"{name} 建池应显式传 self.config.pool_size")

    def test_T07_get_instance_reinitializes_bare_instance(self):
        """防御回归：__new__ 直建裸实例（绕过 __init__，无 config）被注册为单例后，
        get_instance() 必须补齐初始化，否则 get_database_path 访问 self.config
        抛 AttributeError（test_r285_quality_gate 曾以 __new__ 直建触发跨文件污染）。
        """
        saved = AssetSeparatedDatabaseManager._instance
        AssetSeparatedDatabaseManager._instance = None
        try:
            bare = AssetSeparatedDatabaseManager.__new__(AssetSeparatedDatabaseManager)
            self.assertFalse(bare._initialized)
            self.assertFalse(hasattr(bare, 'config'), "裸实例不应有 config")
            inst = AssetSeparatedDatabaseManager.get_instance()
            self.assertIs(inst, bare, "get_instance 应返回同一单例")
            self.assertTrue(inst._initialized, "get_instance 应补齐初始化")
            self.assertTrue(hasattr(inst, 'config'), "get_instance 后必须有 config")
            self.assertTrue(callable(inst.get_database_path),
                            "get_database_path 可正常访问")
        finally:
            AssetSeparatedDatabaseManager._instance = saved


if __name__ == '__main__':
    unittest.main()
