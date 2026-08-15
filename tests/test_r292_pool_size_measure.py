# -*- coding: utf-8 -*-
"""R292-HVD 连接数实证: pool_size 对连接数/内存/句柄的实际影响 (120 vs 80)

背景: DuckDBConnectionPool._initialize_pool (duckdb_manager.py:104) 在建池时
EAGER 创建 pool_size 个连接。HVD-E 让 update_pool_size 运行时重建全部池,
但"8 个 db × pool_size=15 → 120 连接 vs pool_size=10 → 80 连接"的实际
内存/句柄差异此前从未在运行时测量, 仅停留在估算 (R292 遗留实证项)。

本测试:
- 使用独立 DuckDBConnectionManager 实例 (直接实例化, 不碰全局单例, 避免
  影响业务连接池; duckdb_manager.py:620 __init__ 不注册任何全局状态)
- tempfile 临时目录建 N_DBS=8 个空 db 文件 (贴近业务多库场景)
- 对 SIZES=[10, 15] 各建一遍池, psutil 测子进程 RSS / Windows 句柄数
- 确定性断言: 池内实际连接数 == pool_size × N_DBS (EAGER 建池契约,
  防止未来有人把建池改懒加载而断言随之失效)
- 内存/句柄差异仅输出报告, 不 assert 固定阈值 (随机器/版本浮动, 无意义)
"""

import gc
import os
import tempfile
import unittest

import psutil

from core.database.duckdb_manager import DuckDBConnectionManager

N_DBS = 8
SIZES = [10, 15]


def _rss_mb(proc):
    return proc.memory_info().rss / (1024 * 1024)


def _handles(proc):
    try:
        return proc.num_handles()
    except Exception:
        return None  # 非 Windows 平台无句柄概念


class TestPoolSizeMeasurement(unittest.TestCase):
    """HVD-E 实证: pool_size 对连接数/内存/句柄的实际影响"""

    def setUp(self):
        try:
            import duckdb
        except ImportError:
            self.skipTest("duckdb 不可用")
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_paths = []
        for i in range(N_DBS):
            p = os.path.join(self._tmpdir.name, f"db_{i}.duckdb")
            conn = duckdb.connect(p)
            conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
            conn.close()
            self._db_paths.append(p)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_eager_connection_count(self):
        """EAGER 建池契约: 池创建即打开 pool_size 个连接"""
        for size in SIZES:
            manager = DuckDBConnectionManager()
            try:
                for p in self._db_paths:
                    manager.get_pool(p, pool_size=size)
                total = sum(pool._total_connections for pool in manager._pools.values())
                self.assertEqual(
                    total, size * N_DBS,
                    f"pool_size={size}: 应 EAGER 创建 {size * N_DBS} 连接, 实际 {total}")
            finally:
                manager.close_all_pools()

    def test_memory_delta_report(self):
        """实测 RSS/句柄差异并输出报告 (不 assert 固定阈值)"""
        proc = psutil.Process()
        gc.collect()
        baseline_rss = _rss_mb(proc)
        baseline_handles = _handles(proc)

        report = []
        for size in SIZES:
            gc.collect()
            manager = DuckDBConnectionManager()
            try:
                for p in self._db_paths:
                    manager.get_pool(p, pool_size=size)
                gc.collect()
                rss = _rss_mb(proc)
                handles = _handles(proc)
                delta_rss = rss - baseline_rss
                delta_handles = (handles - baseline_handles) if handles is not None else None
                report.append(
                    f"pool_size={size:>2} ({size * N_DBS:>3} 连接): "
                    f"RSS Δ={delta_rss:+.1f} MB"
                    + (f", 句柄 Δ={delta_handles:+.0f}" if delta_handles is not None else "")
                )
            finally:
                manager.close_all_pools()
                gc.collect()

        print("\n[HVD-E 连接数实证报告]")
        print(f"  基线: RSS={baseline_rss:.1f} MB, 句柄={baseline_handles}")
        for line in report:
            print("  " + line)

    def test_rebuild_all_pools_resizes_existing_pools(self):
        """HVD-E: rebuild_all_pools 将存量池重建为新容量 (显式传 pool_size)

        回归防线: apply_default_config (duckdb_manager.py:659) 重建不传参曾
        落回 DuckDBConnectionPool.__init__ 默认 50 (L73), 本测试锁定"显式
        传 pool_size → 重建后即新容量且 EAGER 打开 size×N_DBS 连接"。
        """
        manager = DuckDBConnectionManager()
        try:
            for p in self._db_paths:
                manager.get_pool(p, pool_size=10)
            self.assertEqual({v.pool_size for v in manager._pools.values()}, {10})

            self.assertTrue(manager.rebuild_all_pools(15))
            self.assertEqual({v.pool_size for v in manager._pools.values()}, {15})
            total = sum(pool._total_connections for pool in manager._pools.values())
            self.assertEqual(total, 15 * N_DBS,
                             f"重建后应 EAGER 打开 {15 * N_DBS} 连接, 实际 {total}")
        finally:
            manager.close_all_pools()


if __name__ == '__main__':
    unittest.main()
