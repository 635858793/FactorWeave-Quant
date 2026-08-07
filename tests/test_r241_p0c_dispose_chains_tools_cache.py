# -*- coding: utf-8 -*-
"""
R241 TDD (第二批): P0-C-1 PerformanceMonitor dispose 链闭合 + P0-C-2c 3 处 fallback
裸建托管 + P0-C-3 RiskManager dispose 双宿主接入 + P0-C-4 HealthMonitor/FaultToleranceManager
防御性 dispose + P1-D tools/service_dispose_audit.py 转正 + P2-A CacheService
create_cache 适配 (Hybrid 缓存恢复)

RED → GREEN 全流程。源码级断言 (防御回归) + 行为级测试。
"""
import os
import sys
import re
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def _read(rel_path: str) -> str:
    with open(os.path.join(PROJECT_ROOT, rel_path), encoding="utf-8") as f:
        return f.read()


class TestPerformanceMonitorDisposeChain(unittest.TestCase):
    """P0-C-1: PerformanceMonitor (QObject, 2 QTimer 永不停) 退出链 0 调用方"""

    def test_t01_main_registers_perf_monitor_cleanup(self):
        src = _read("main.py")
        self.assertIn("performance_monitor", src.lower(),
                      "main.py 必须注册/调用 PerformanceMonitor.dispose (graceful_shutdown handler 或 _cleanup)")

    def test_t02_perf_monitor_init_disposed_false(self):
        src = _read("core/monitoring/performance_monitor.py")
        # 与 R78 幂等规范对齐: __init__ 显式初始化 _disposed = False
        self.assertIn("_disposed = False", src,
                      "PerformanceMonitor.__init__ 必须显式初始化 _disposed = False (R78)")


class TestFallbackBareCreateGovernance(unittest.TestCase):
    """P0-C-2c: 3 处 BacktestResultManager() fallback 裸建 → 无托管实例 (无人 dispose)"""

    FILES = (
        "core/trading_controller.py",
        "core/ui/panels/right_panel.py",
        "gui/widgets/analysis_tabs/pattern_tab_pro.py",
    )

    def test_t03_no_bare_backtest_result_manager(self):
        for rel in self.FILES:
            src = _read(rel)
            self.assertNotIn("return BacktestResultManager()", src,
                             f"{rel} fallback 裸建 BacktestResultManager() 应改 return None"
                             f" (容器 resolve 失败时, 调用方已有 None 容错)")

    def test_t04_fallback_returns_none(self):
        for rel in self.FILES:
            src = _read(rel)
            # fallback 分支返回 None (保持 _get_backtest_result_manager 返回类型 Optional)
            self.assertIn("return None", src, f"{rel} fallback 分支应返回 None")


class TestRiskManagerDispose(unittest.TestCase):
    """P0-C-3: RiskManager 纯内存类 0 dispose, 双宿主 (backtest 引擎 + widget) 无清理"""

    def test_t05_risk_manager_has_dispose(self):
        from core.risk_manager import RiskManager
        self.assertTrue(hasattr(RiskManager, "dispose"),
                        "RiskManager 必须实现 dispose() (R78 4 链标准)")

    def test_t06_dispose_idempotent_and_clears(self):
        from core.risk_manager import RiskManager
        rm = RiskManager()
        rm.current_positions = {"000001": {"quantity": 100}}
        rm.initialized = True
        rm._monitor = object()
        rm.dispose()
        self.assertTrue(rm.initialized is False or rm.current_positions == {},
                        "dispose 后 current_positions 必须清空 / initialized 置 False")
        rm.dispose()  # 幂等, 不抛

    def test_t07_backtest_widget_host_calls_dispose(self):
        src = _read("gui/widgets/backtest_widget.py")
        self.assertIn("risk_manager.dispose", src,
                      "backtest_widget (宿主2, L1877 创建) 必须在 closeEvent/_cleanup 调 risk_manager.dispose")

    def test_t08_engine_host_calls_dispose(self):
        src = _read("backtest/unified_backtest_engine.py")
        self.assertIn("risk_manager.dispose", src,
                      "unified_backtest_engine (宿主1, L248 创建) 必须在收尾调 risk_manager.dispose")


class TestHealthMonitorDispose(unittest.TestCase):
    """P0-C-4: HealthMonitor/FaultToleranceManager 防御性 dispose (无业务调用方)"""

    def test_t09_health_monitor_has_dispose(self):
        src = _read("core/services/fault_tolerance_manager.py")
        self.assertIn("def dispose", src,
                      "HealthMonitor 必须实现 dispose() (委托 stop_monitoring L99-110)")

    def test_t10_fault_tolerance_dispose_delegates(self):
        src = _read("core/services/fault_tolerance_manager.py")
        self.assertIn("def dispose", src,
                      "FaultToleranceManager 必须实现 dispose() (委托 stop())")

    def test_t11_health_dispose_stops_thread(self):
        from core.services.fault_tolerance_manager import HealthMonitor
        hm = HealthMonitor()
        hm.monitoring_active = True
        hm.dispose()
        self.assertFalse(hm.monitoring_active, "dispose 后监控必须停止")
        hm.dispose()  # 幂等


class TestServiceDisposeAuditTool(unittest.TestCase):
    """P1-D: tools/_r237_d_audit_v2.py 转正 tools/service_dispose_audit.py (4 项改动)"""

    TOOL = "tools/service_dispose_audit.py"

    def test_t12_tool_exists(self):
        path = os.path.join(PROJECT_ROOT, self.TOOL)
        self.assertTrue(os.path.exists(path), f"{self.TOOL} 必须存在 (R231 声称重建)")

    def test_t13_mro_chain_parsing(self):
        src = _read(self.TOOL)
        self.assertIn("MRO", src.upper(),
                      "工具必须支持 MRO 链解析 (间接继承 BaseService 识别)")
        self.assertNotIn("_r237_d_audit_v2", src,
                         "转正后不应残留 _r237_d_audit_v2 引用")

    def test_t14_do_dispose_hook_detection(self):
        src = _read(self.TOOL)
        self.assertIn("_do_dispose", src,
                      "工具必须检测 BaseService 子类是否重写 _do_dispose (P1-C 三层遗漏)")


class TestCacheServiceCreateCache(unittest.TestCase):
    """P2-A: CacheService create_cache API 补齐 (Hybrid 缓存恢复)"""

    def test_t15_create_cache_exists(self):
        src = _read("core/services/cache_service.py")
        self.assertIn("def create_cache", src,
                      "CacheService 必须新增 create_cache (async 工厂, Hybrid _initialize_caches L593-617)")

    def test_t16_get_namespace_keys_exists(self):
        src = _read("core/services/cache_service.py")
        self.assertIn("def get_namespace_keys", src,
                      "CacheService 必须新增 get_namespace_keys (Hybrid get_keys 消费点 L1504-1533)")

    def test_t17_async_namespace_cache(self):
        src = _read("core/services/cache_service.py")
        self.assertIn("class _AsyncNamespaceCache", src,
                      "必须实现 async get/set/delete/clear/get_keys 适配对象 (Hybrid 消费点 L950-1697)")


if __name__ == "__main__":
    unittest.main()
