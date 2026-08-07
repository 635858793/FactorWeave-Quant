"""
R239 TDD 测试: shutdown_all_services 空转 P0 修复 + StrategyManager 4 链 dispose

发现来源 (R239 4 子智能体并行审计 + 主智能体交叉验证 + 实测):
- HVD-239-P0-001 (子智能体 A §3 + 主智能体实测): production 注册路径
  (service_bootstrap.py) 全程走 register_instance/register/register_factory, 从不调用
  register_core_service/resolve_with_lifecycle → _dependencies/_initialized_services 恒空
  → get_startup_order() 返回 [] → shutdown_all_services (unified_service_container.py:373)
  dispose 循环空转 (实测 FakeService.disposed=False, 服务 dispose 根本不被调用)
  → R238 的 main.py:321 shutdown_all_services LIFO 修复无效, R237/R238 的 dispose 链全部不触发
- HVD-239-D-001 (子智能体 C + 主智能体验证): StrategyManager (core/trading/strategy_manager.py:33)
  0 dispose 链 + R236-B 治理声明系虚报 (git 历史 R236 时段零提交 + 测试文件从未存在:
  git log --all -- tests/test_r236_b_5services_dispose.py 仅初始占位符+revert)

修复目标 (RED → GREEN):
1. shutdown_all_services: 依赖图为空时兜底遍历 _instances (已实例化服务), 按 LIFO 释放
2. StrategyManager.dispose: 类级 _disposed + 幂等短路 + 清缓存 + 解除引用 + 失败不抛

遵循铁律:
- R78 §8.1 #6 dispose 路径必须幂等 (_disposed flag 短路)
- R233 §13.4 业务核心 Service 0 dispose 链 P0 必修
- R235-D 类级默认 _disposed 模式 (防御 __new__ 绕过 __init__)
- R85 §10 假修复鉴别 4 步法 (R236-B 虚报已用 git 历史实证拦截)
"""
import sys
from typing import Dict

import pytest

# 确保项目根可导入
sys.path.insert(0, ".")

from core.containers.unified_service_container import UnifiedServiceContainer
from core.containers.service_registry import ServiceScope
from core.trading.strategy_manager import StrategyManager


class _FakeService:
    """带 dispose 的假服务 (验证 dispose 是否被调用)"""

    def __init__(self):
        self.disposed = False

    def dispose(self):
        self.disposed = True


class _FakeNoDispose:
    """无 dispose 的假服务 (验证不抛错)"""


class TestShutdownAllServicesFallback:
    """shutdown_all_services 兜底 P0 修复 (HVD-239-P0-001)"""

    def test_T01_register_instance_service_gets_disposed(self):
        """register_instance 注册的服务必须被 dispose (原实现空转, 本次 P0 修复)"""
        c = UnifiedServiceContainer()
        svc = _FakeService()
        c.register_instance(_FakeService, svc)
        # RED: 修复前 get_startup_order() 返回 [] → dispose 不触发
        assert c.get_startup_order() == [], "依赖图应为空 (production 路径特征)"
        c.shutdown_all_services()
        assert svc.disposed is True, \
            "register_instance 服务必须被 shutdown_all_services dispose (P0 空转修复)"

    def test_T02_register_factory_service_gets_disposed(self):
        """register + resolve (factory) 的服务必须被 dispose"""
        c = UnifiedServiceContainer()
        c.register(_FakeService, scope=ServiceScope.SINGLETON,
                   factory=lambda: _FakeService())
        svc = c.resolve(_FakeService)  # 实例化后进入 _instances
        c.shutdown_all_services()
        assert svc.disposed is True, "resolve 实例化服务必须被 dispose"

    def test_T03_no_dispose_service_no_raise(self):
        """无 dispose 方法的服务不得抛错 (R117-HVD-69 模板)"""
        c = UnifiedServiceContainer()
        c.register_instance(_FakeNoDispose, _FakeNoDispose())
        c.shutdown_all_services()  # 不应抛异常

    def test_T04_core_service_registered_path_still_works(self):
        """register_core_service 路径 (走 _initialized_services) 必须仍工作"""
        c = UnifiedServiceContainer()
        svc = _FakeService()
        c.register_core_service(_FakeService, priority=1)
        c._instances[_FakeService] = svc  # 模拟 resolve_with_lifecycle 后状态
        c._initialized_services.add(_FakeService)
        c.shutdown_all_services()
        assert svc.disposed is True, "register_core_service 路径仍须 dispose"

    def test_T05_shutdown_is_repeatable(self):
        """shutdown_all_services 可重复调用不抛错"""
        c = UnifiedServiceContainer()
        svc = _FakeService()
        c.register_instance(_FakeService, svc)
        c.shutdown_all_services()
        c.shutdown_all_services()  # 幂等
        assert svc.disposed is True

    def test_T06_dispose_failure_no_break(self):
        """单个服务 dispose 失败不得中断其余服务释放"""
        c = UnifiedServiceContainer()

        class _Boom:
            def dispose(self):
                raise RuntimeError("boom")

        boom = _Boom()
        ok = _FakeService()
        c.register_instance(_Boom, boom)
        c.register_instance(_FakeService, ok)
        c.shutdown_all_services()
        assert ok.disposed is True, "失败服务的后续服务仍须 dispose"


class TestStrategyManagerDispose:
    """StrategyManager 4 链 dispose (HVD-239-D-001, R233 §13.4)"""

    def test_T01_has_dispose_method(self):
        """StrategyManager 必须存在 dispose 方法 (P0 业务核心)"""
        sm = StrategyManager.__new__(StrategyManager)
        assert hasattr(sm, 'dispose'), "StrategyManager 缺少 dispose 方法"

    def test_T02_dispose_has_short_circuit(self):
        """dispose 必须 _disposed 标志幂等短路 (R78 铁律 #6)"""
        sm = StrategyManager.__new__(StrategyManager)
        sm._strategy_cache = {}
        sm._strategy_service = None
        sm.service_container = None
        sm.dispose()
        assert sm._disposed is True
        sm.dispose()  # 幂等不抛

    def test_T03_clears_strategy_cache(self):
        """dispose 必须清空策略缓存 (业务数据)"""
        sm = StrategyManager.__new__(StrategyManager)
        sm._strategy_cache = {"s1": object(), "s2": object()}
        sm._strategy_service = object()
        sm.service_container = object()
        sm.dispose()
        assert len(sm._strategy_cache) == 0, "dispose 后策略缓存必须清空"
        assert sm._strategy_service is None, "dispose 后 _strategy_service 必须置 None"
        assert sm.service_container is None, "dispose 后 service_container 必须置 None"

    def test_T04_dispose_failure_no_raise(self):
        """dispose 失败仅 warning 不抛 (R117-HVD-69 P1 模板)"""
        sm = StrategyManager.__new__(StrategyManager)
        sm._strategy_cache = None  # 模拟异常场景
        sm._strategy_service = None
        sm.service_container = None
        sm.dispose()  # 不应抛异常


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    sys.exit(pytest.main([__file__, "-v"]))
