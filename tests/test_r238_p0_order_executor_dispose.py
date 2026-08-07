"""
R238 TDD 测试: OrderExecutor 4 链 dispose + OrderService dispose 补全 + main.py 容器级 handler (HVD-238-A-002/D-001)

发现来源 (R238 4 子智能体交叉验证 + 主智能体独立验证):
- HVD-238-D-001 (子智能体 D 确认 7/10 Top10 真实 0 dispose 链, P0-1):
  OrderExecutor (core/trading/order_executor.py:340) 持 5+ TradingInterface 连接
  (XTPProTradingInterface ×5 + CTP ×2 + Mock ×7), _trading_interfaces/_account_interface_cache
  无释放路径 → 连接句柄泄漏 (高)
- R237-P1 OrderService.dispose 不完整 (子智能体 D §2.2): 仅释放 monitor,
  漏 executor (OrderExecutor, 5 连接) 与 analyzer 子组件
- HVD-238-A-002 (子智能体 B + 主智能体验证): 信号退出路径 (SIGTERM/SIGINT/SIGBREAK)
  只执行 _cleanup_handlers 列表 (graceful_shutdown.py:61), main.py _cleanup() 不执行
  → 容器服务 dispose 链不触发; 修复 = main.py 注册容器级 handler (LIFO 先于 DuckDB)

修复目标 (RED → GREEN):
1. OrderExecutor.dispose(): 类级 _disposed + 幂等短路 + 全部接口 disconnect + 清空缓存/健康跟踪
2. OrderService.dispose(): 补全 executor.dispose() + analyzer.dispose()
3. main.py: 注册容器级 _shutdown_service_container handler

遵循铁律:
- R78 §8.1 #6 dispose 路径必须幂等 (_disposed flag 短路)
- R233 §13.4 业务核心 Service 0 dispose 链 P0 必修
- R234 强化: 子组件释放 4 步法 + 失败仅 warning 不抛 (R117-HVD-69 P1 模板)
- R235-D 类级默认 _disposed 模式 (防御 __new__ 绕过 __init__)
"""
import sys
from unittest.mock import MagicMock
from threading import Lock

import pytest

# 确保项目根可导入
sys.path.insert(0, ".")

from core.trading.order_executor import OrderExecutor
from core.trading.order_service import OrderService


class TestOrderExecutorDispose:
    """OrderExecutor dispose 链 TDD (HVD-238-D-001, R233 §13.4)"""

    def _make_executor(self):
        """构造 OrderExecutor 实例 (绕过 __init__ 依赖)"""
        exe = OrderExecutor.__new__(OrderExecutor)
        exe.service_container = MagicMock()
        exe.event_bus = MagicMock()

        # 模拟 5+ 交易接口连接
        iface_1, iface_2 = MagicMock(), MagicMock()
        exe._trading_interfaces = {
            "STOCK_A": iface_1,
            "FUTURES": iface_2,
        }
        exe.trading_interface = MagicMock()
        exe._account_interface_cache = {"acc_1": iface_1}
        exe._interface_health = {"STOCK_A": {"connected": True}}
        exe._interface_failover_map = {"STOCK_A": ["FUTURES"]}
        exe.repository = MagicMock()
        return exe

    def test_T01_has_dispose_method(self):
        """OrderExecutor 必须存在 dispose 方法 (R233 §13.4)"""
        exe = self._make_executor()
        assert hasattr(exe, 'dispose'), "OrderExecutor 缺少 dispose 方法 (P0 业务核心)"
        assert callable(exe.dispose)

    def test_T02_dispose_has_short_circuit(self):
        """dispose 必须 _disposed 标志幂等短路 (R78 铁律 #6)"""
        exe = self._make_executor()
        assert hasattr(exe, '_disposed'), "OrderExecutor 缺少 _disposed 标志"
        exe.dispose()
        assert exe._disposed is True, "dispose 后 _disposed 必须为 True"
        exe.dispose()  # 幂等, 不得抛错

    def test_T03_repeated_dispose_idempotent(self):
        """重复 dispose 必须幂等 (R78 铁律 #6, R235-D 教训)"""
        exe = self._make_executor()
        exe.dispose()
        exe.dispose()
        exe.dispose()  # 多次调用不得抛错

    def test_T04_disconnects_all_interfaces(self):
        """dispose 必须 disconnect 全部交易接口连接 (连接句柄泄漏防御)"""
        exe = self._make_executor()
        default_iface = exe.trading_interface
        exe.dispose()
        for iface in exe._trading_interfaces.values():
            assert iface.disconnect.called, "每个交易接口必须 disconnect"
        assert default_iface.disconnect.called, "默认交易接口必须 disconnect"

    def test_T05_clears_interface_caches(self):
        """dispose 必须清空接口缓存与健康跟踪 (内存泄漏防御)"""
        exe = self._make_executor()
        assert len(exe._trading_interfaces) == 2
        assert len(exe._account_interface_cache) == 1
        assert len(exe._interface_health) == 1
        exe.dispose()
        assert len(exe._trading_interfaces) == 0, "dispose 后 _trading_interfaces 必须清空"
        assert len(exe._account_interface_cache) == 0, "dispose 后 _account_interface_cache 必须清空"
        assert len(exe._interface_health) == 0, "dispose 后 _interface_health 必须清空"
        assert len(exe._interface_failover_map) == 0, "dispose 后 _interface_failover_map 必须清空"

    def test_T06_clears_sub_component_reference(self):
        """dispose 必须清空子组件引用 (repository/trading_interface)"""
        exe = self._make_executor()
        exe.dispose()
        assert exe.repository is None, "dispose 后 repository 必须置 None"
        assert exe.trading_interface is None, "dispose 后 trading_interface 必须置 None"

    def test_T07_dispose_failure_no_raise(self):
        """dispose 失败仅 warning 不抛 (R117-HVD-69 P1 模板)"""
        exe = self._make_executor()
        for iface in exe._trading_interfaces.values():
            iface.disconnect.side_effect = RuntimeError("接口已断开")
        exe.dispose()  # 不应抛异常


class TestOrderServiceDisposeFull:
    """OrderService.dispose 补全子组件释放 TDD (HVD-238-D-001 补全项)"""

    def _make_service(self):
        """构造 OrderService 实例 (绕过 __init__ 依赖)"""
        svc = OrderService.__new__(OrderService)
        svc.service_container = MagicMock()
        svc.event_bus = MagicMock()
        svc.validator = MagicMock()
        svc.repository = MagicMock()
        svc.executor = MagicMock(spec=OrderExecutor)
        svc.monitor = MagicMock()
        svc.analyzer = MagicMock()
        svc._order_locks = {"order_1": Lock()}
        svc._lock_manager_lock = Lock()
        return svc

    def test_T01_disposes_executor_sub_component(self):
        """OrderService.dispose 必须调用 executor.dispose (R238-D-001 补全项)"""
        svc = self._make_service()
        svc.dispose()
        assert svc.executor.dispose.called, \
            "OrderService.dispose 必须释放 OrderExecutor (5+ 交易接口连接)"

    def test_T02_disposes_analyzer_sub_component(self):
        """OrderService.dispose 必须调用 analyzer.dispose (R238-D-001 补全项)"""
        svc = self._make_service()
        svc.dispose()
        assert svc.analyzer.dispose.called, \
            "OrderService.dispose 必须释放 OrderAnalyzer"

    def test_T03_sub_component_failure_no_raise(self):
        """子组件 dispose 失败仅 warning 不抛 (R117-HVD-69 P1 模板)"""
        svc = self._make_service()
        svc.executor.dispose.side_effect = RuntimeError("executor 已销毁")
        svc.dispose()  # 不应抛异常
        assert svc._disposed is True, "子组件失败后 _disposed 仍须置位"

    def test_T04_still_disposes_monitor(self):
        """补全后 monitor.dispose 仍须保留 (R234 子组件释放 4 步法)"""
        svc = self._make_service()
        svc.dispose()
        assert svc.monitor.dispose.called, "OrderService.dispose 必须保留 monitor.dispose"


class TestMainContainerHandler:
    """main.py 容器级 handler 注册 TDD (HVD-238-A-002)"""

    @staticmethod
    def _read_main_source() -> str:
        with open("main.py", encoding="utf-8") as f:
            return f.read()

    def test_T01_register_cleanup_handler_container(self):
        """main.py 必须注册容器级 _shutdown_service_container handler (HVD-238-A-002)"""
        src = self._read_main_source()
        assert "_shutdown_service_container" in src, \
            "main.py 缺少容器级 _shutdown_service_container 定义"
        assert "register_cleanup_handler" in src, \
            "main.py 缺少容器级 register_cleanup_handler 调用"

    def test_T02_handler_calls_shutdown_all_services(self):
        """handler 必须调用 shutdown_all_services (LIFO 关闭链)"""
        src = self._read_main_source()
        assert "shutdown_all_services" in src, \
            "main.py 容器 handler 必须调用 shutdown_all_services (LIFO)"

    def test_T03_handler_has_fallback_dispose(self):
        """handler 必须有 dispose fallback (R78 兼容旧容器)"""
        src = self._read_main_source()
        assert "container.dispose()" in src, \
            "main.py 容器 handler 必须有 dispose fallback"

    def test_T04_annotation_and_why_comment(self):
        """修复必须带 R238-A-002 标注注释 (审计可追溯)"""
        src = self._read_main_source()
        assert "R238-A-002" in src, "main.py 修复缺少 R238-A-002 标注"


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    sys.exit(pytest.main([__file__, "-v"]))
