#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R289 专项测试：DuckDB 性能配置"假生效"融入改造 + 孤儿文件清理 + fund_flow 导入缺陷

审计结论（子智能体交叉验证 + 主智能体二次验证，全部 100% 确认）：
1. DuckDBPerformanceOptimizer 融入：设置对话框快速配置（R288 已修）与高级配置
   对话框（R289 修复 _apply_profile_to_manager 注入 manager 单例）均可真正生效；
   模块尾部 2 个零生产调用死函数 get_optimized_duckdb_connection /
   create_performance_optimized_config 已删除；database_service 的
   _performance_optimizers 影子初始化体系已清理（从未有消费方）。
2. 孤儿文件：core/database/dynamic_config_manager.py / table_schemas.py 已被删除
   （git 跟踪 D、零引用），对应能力分别由 duckdb_config_models+apply_default_config
   体系与 asset_database_manager._initialize_table_schemas 完全覆盖。
3. fund_flow 导入缺陷：非 import 写错，而是 6e65afc 引入空包 gui/ui_components/
   遮蔽同名模块 gui/ui_components.py（FileFinder 包优先于模块）。删除空包后
   7 处 `from gui.ui_components import ...` 全部恢复。
4. monitor_latest 预填异步：_initialize_database_schema 中历史预填放 daemon 线程
   执行（threading.Thread daemon=True, R288），主线程仅 COUNT 查询，不阻塞。

全部离线测试：源码断言 + mock，不产生真实 DB/网络 IO。
"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _read_source(rel_path: str) -> str:
    with open(os.path.join(PROJECT_ROOT, rel_path), encoding='utf-8') as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. DuckDBPerformanceOptimizer 融入：死函数删除 + database_service 清理
# ---------------------------------------------------------------------------
class TestOptimizerDeadCodeRemoved(unittest.TestCase):
    """优化器零生产调用死代码已清理，类本体保留（对话框测试线程仍用）"""

    def test_module_dead_functions_removed(self):
        src = _read_source('core/database/duckdb_performance_optimizer.py')
        self.assertNotIn('get_optimized_duckdb_connection', src)
        self.assertNotIn('create_performance_optimized_config', src)

    def test_class_body_retained(self):
        # DuckDBPerformanceOptimizer 类本体保留（duckdb_config_dialog 测试线程 L57 唯一消费方）
        src = _read_source('core/database/duckdb_performance_optimizer.py')
        self.assertIn('class DuckDBPerformanceOptimizer', src)
        self.assertIn('def benchmark_configuration', src)

    def test_database_service_no_optimizer_residue(self):
        src = _read_source('core/services/database_service.py')
        self.assertNotIn('_performance_optimizers', src)
        self.assertNotIn('_initialize_performance_optimizers', src)
        self.assertNotIn('DuckDBPerformanceOptimizer', src)
        self.assertNotIn('from ..database.duckdb_performance_optimizer', src)

    def test_gui_dialog_imports_optimizer_class_only(self):
        src = _read_source('gui/dialogs/duckdb_config_dialog.py')
        self.assertIn('from core.database.duckdb_performance_optimizer import (', src)
        self.assertIn('DuckDBPerformanceOptimizer, WorkloadType', src)


# ---------------------------------------------------------------------------
# 2. 高级配置对话框注入 manager 单例（"假生效"修复）
# ---------------------------------------------------------------------------
class TestAdvancedConfigInjection(unittest.TestCase):
    """R289：DuckDBConfigDialog._apply_profile_to_manager 真正注入业务连接池"""

    def _make_dialog(self):
        # 绕过 __init__（不构造 GUI），仅验证注入方法逻辑；
        # DuckDBConfigDialog 继承 QObject，object.__new__ 不安全，用类 __new__。
        from gui.dialogs.duckdb_config_dialog import DuckDBConfigDialog
        dialog = DuckDBConfigDialog.__new__(DuckDBConfigDialog)
        return dialog

    def test_apply_profile_to_manager_maps_and_injects(self):
        dialog = self._make_dialog()
        profile = SimpleNamespace(
            memory_limit='6.0GB',
            threads=8,
            max_memory='7.0GB',
            checkpoint_threshold='1GB',
            enable_progress_bar=False,
            enable_profiling=True,
            preserve_insertion_order=False,
            enable_external_access=True,
        )
        with patch('core.database.duckdb_manager.get_connection_manager') as mock_gcm:
            manager = MagicMock()
            manager.apply_default_config.return_value = True
            mock_gcm.return_value = manager

            ok = dialog._apply_profile_to_manager(profile)

        self.assertTrue(ok)
        manager.apply_default_config.assert_called_once()
        cfg = manager.apply_default_config.call_args[0][0]
        # int threads 必须转 str（manager 版 DuckDBConfig.threads 为 str）
        self.assertEqual(cfg.threads, '8')
        self.assertEqual(cfg.memory_limit, '6.0GB')

    def test_apply_profile_failure_returns_false(self):
        dialog = self._make_dialog()
        profile = SimpleNamespace(threads=4)
        with patch('core.database.duckdb_manager.get_connection_manager') as mock_gcm:
            manager = MagicMock()
            manager.apply_default_config.side_effect = RuntimeError('boom')
            mock_gcm.return_value = manager
            ok = dialog._apply_profile_to_manager(profile)
        self.assertFalse(ok)

    def test_apply_current_config_calls_injection_on_success(self):
        # 源码断言：apply_current_config 在 activate_profile 成功后调用注入
        src = _read_source('gui/dialogs/duckdb_config_dialog.py')
        self.assertIn('applied = self._apply_profile_to_manager(self.current_profile)', src)


# ---------------------------------------------------------------------------
# 3. 启动恢复（service_bootstrap._restore_duckdb_config_from_storage）
# ---------------------------------------------------------------------------
class TestBootstrapRestoreDuckdbConfig(unittest.TestCase):
    """R289：启动时从 ConfigService 恢复 GUI 保存的 DuckDB 配置并注入 manager"""

    def _make_bootstrap(self, config_service):
        from core.services.service_bootstrap import ServiceBootstrap
        bs = object.__new__(ServiceBootstrap)
        bs.service_container = MagicMock()
        bs.service_container.resolve.return_value = config_service
        return bs

    def test_restore_injects_saved_config(self):
        config_service = MagicMock()
        config_service.get.side_effect = lambda k: 6 if k == 'duckdb.memory_limit_gb' else 8

        with patch('core.database.duckdb_manager.get_connection_manager') as mock_gcm:
            manager = MagicMock()
            manager.apply_default_config.return_value = True
            mock_gcm.return_value = manager

            bs = self._make_bootstrap(config_service)
            bs._restore_duckdb_config_from_storage()

        manager.apply_default_config.assert_called_once()
        cfg = manager.apply_default_config.call_args[0][0]
        self.assertEqual(cfg.memory_limit, '6GB')
        self.assertEqual(cfg.threads, '8')

    def test_restore_skips_when_no_saved_config(self):
        config_service = MagicMock()
        config_service.get.return_value = None

        with patch('core.database.duckdb_manager.get_connection_manager') as mock_gcm:
            manager = MagicMock()
            mock_gcm.return_value = manager

            bs = self._make_bootstrap(config_service)
            bs._restore_duckdb_config_from_storage()

        manager.apply_default_config.assert_not_called()

    def test_bootstrap_calls_restore_step(self):
        src = _read_source('core/services/service_bootstrap.py')
        self.assertIn('self._restore_duckdb_config_from_storage()', src)


# ---------------------------------------------------------------------------
# 4. fund_flow 导入缺陷（空包遮蔽同名模块）
# ---------------------------------------------------------------------------
class TestFundFlowImportFixed(unittest.TestCase):
    """6e65afc 空包遮蔽已解除，7 处 gui.ui_components 引用恢复"""

    def test_fund_flow_dead_import_removed(self):
        src = _read_source('components/fund_flow.py')
        self.assertNotIn('from gui.ui_components import BaseAnalysisPanel', src)

    def test_ui_components_module_reimportable(self):
        # 空包 gui/ui_components/__init__.py 已删 → gui.ui_components 解析为模块
        # （含 BaseAnalysisPanel）；若空包仍存在则此导入路径解析为包。
        import importlib
        import gui.ui_components as mod
        self.assertTrue(hasattr(mod, 'BaseAnalysisPanel'))

    def test_ui_components_dir_no_init(self):
        # 空包遮蔽根因文件不应存在
        pkg_init = os.path.join(PROJECT_ROOT, 'gui', 'ui_components', '__init__.py')
        self.assertFalse(os.path.exists(pkg_init))

    def test_all_ui_components_importers_restored(self):
        # 7 处 `from gui.ui_components import ...` 均可解析（模块属性存在性抽样验证）
        import gui.ui_components as mod
        for attr in ('BaseAnalysisPanel', 'AnalysisToolsPanel'):
            self.assertTrue(hasattr(mod, attr), f'gui.ui_components.{attr} 缺失')


# ---------------------------------------------------------------------------
# 5. 孤儿文件已清理（dynamic_config_manager / table_schemas）
# ---------------------------------------------------------------------------
class TestOrphanFilesRemoved(unittest.TestCase):
    """孤儿文件已删除，且全项目零引用"""

    def test_orphan_files_do_not_exist(self):
        for rel in ('core/database/dynamic_config_manager.py',
                    'core/database/table_schemas.py'):
            self.assertFalse(
                os.path.exists(os.path.join(PROJECT_ROOT, rel)),
                f'{rel} 应已删除')

    def test_no_import_reference_to_orphans(self):
        # 全项目源码级检索（core/gui/db/components 的 .py 文件，排除 tests 与虚拟环境）
        for name in ('dynamic_config_manager', 'table_schemas'):
            hits = []
            for root, dirs, files in os.walk(PROJECT_ROOT):
                dirs[:] = [d for d in dirs if d not in ('tests', '.venv', 'venv',
                                                        '__pycache__', 'node_modules')]
                for fn in files:
                    if not fn.endswith('.py'):
                        continue
                    fp = os.path.join(root, fn)
                    try:
                        with open(fp, encoding='utf-8', errors='ignore') as f:
                            for line in f:
                                if name in line and 'import' in line:
                                    hits.append(f'{fp}: {line.strip()}')
                    except OSError:
                        continue
            self.assertEqual(hits, [], f'{name} 仍有 import 引用: {hits}')


# ---------------------------------------------------------------------------
# 6. monitor_latest 预填异步（不阻塞主线程）
# ---------------------------------------------------------------------------
class TestMonitorLatestBackfillAsync(unittest.TestCase):
    """初始化预填放 daemon 线程执行，主线程仅 COUNT 查询"""

    def test_backfill_runs_in_daemon_thread(self):
        src = _read_source('core/asset_database_manager.py')
        # 空表守卫 + daemon 线程启动
        self.assertIn('threading.Thread(', src)
        self.assertIn('target=self._async_backfill_monitor_latest', src)
        self.assertIn('daemon=True', src)
        self.assertIn('name="monitor-latest-backfill"', src)

    def test_main_thread_only_counts(self):
        src = _read_source('core/asset_database_manager.py')
        # 主线程在启动线程前仅执行 COUNT 检查，不执行聚合回填
        count_idx = src.find('SELECT COUNT(*) FROM monitor_latest')
        thread_idx = src.find('threading.Thread(', count_idx)
        async_fn_idx = src.find('def _async_backfill_monitor_latest')
        self.assertGreater(count_idx, -1)
        self.assertGreater(thread_idx, count_idx)          # 线程在 COUNT 之后启动
        self.assertGreater(async_fn_idx, thread_idx)       # 回填逻辑独立成函数

    def test_ready_flag_set_on_existing(self):
        src = _read_source('core/asset_database_manager.py')
        self.assertIn('self._monitor_latest_table_ready = True', src)


# ---------------------------------------------------------------------------
# 7. 落库关键节点日志增强
# ---------------------------------------------------------------------------
class TestPersistLoggingEnhanced(unittest.TestCase):
    """K线落库关键节点计时日志（缓存命中 + DB 查询耗时）"""

    def test_persist_kdata_has_duration_logging(self):
        src = _read_source('core/services/unified_data_manager.py')
        seg_start = src.find('def _persist_kdata_to_duckdb')
        self.assertGreater(seg_start, -1)
        seg = src[seg_start:seg_start + 6000]
        self.assertIn('[K线落库]', seg)
        self.assertIn('persist_duration', seg)
        self.assertIn('persist_speed', seg)
        self.assertIn('write_duration', src)  # _upsert_data 已有耗时日志

    def test_existing_cache_hit_logs_present(self):
        # 既有缓存命中/DB 耗时日志抽查（R287 已加，防回归）
        src = _read_source('core/services/unified_data_manager.py')
        self.assertIn('[读前质量校验', src)
        dbmgr = _read_source('core/asset_database_manager.py')
        self.assertIn('表结构-缓存', dbmgr)
        self.assertIn('列名-缓存', dbmgr)
        self.assertIn('[批量插入]', dbmgr)


if __name__ == '__main__':
    unittest.main()
