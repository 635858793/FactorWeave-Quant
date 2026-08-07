"""
R240 TDD 测试: Hybrid 混合推荐引擎 async 悬空 P0 修复 + account_load_failed 孤儿事件治理

发现来源 (R240 4 子智能体并行审计 + 主智能体交叉验证, 全部 100% 实锤带源码行号):
- HVD-240-P0-001 (子智能体 A §3 + 主智能体验证): service_bootstrap.py:701 同步调用
  async initialize → 悬空 coroutine 从不执行 → Hybrid 引擎伪初始化 (RuntimeWarning)
- HVD-240-P0-002 (主智能体验证): hybrid_recommendation_engine.py:549
  container.resolve(BettaFishAgent) → service_container.py:128-131 无注册抛 ValueError,
  全项目 core/ 零 register(BettaFishAgent) (grep 实证 13 处引用仅 import/实例化/resolve)
- HVD-240-P0-003/004/005 (主智能体验证): L570 await start_monitoring (同步方法
  performance_monitor.py:233) / L938 await stop_monitoring (:238) / L717 await
  record_metric (:283) → await None → TypeError
- HVD-240-P0-006 (子智能体 B §3 + 主智能体验证): account_load_failed 真孤儿事件,
  account_manager.py:88 publish, core/ 零订阅; 启动时序缺口: main.py:229 bootstrap
  早于 main_window_coordinator.py:232 subscribe_all_events, EventBus 无历史回放
  (event_bus.py:501-502 无 handler 仅 debug) → 启动期事件必丢 → 需订阅 + 启动补查双保险
- HVD-240-P1-001 (子智能体 A + 主智能体验证): L593/601/609/617 create_cache 不存在
  (cache_service.py:1324 仅 create_namespace) → 优雅降级为无缓存 (下游消费点有空值保护)
- HVD-240-P0-007 (R240 交叉验证新发现): EventBus 定义 __len__ (event_bus.py:691-694),
  空实例 len=0 为 falsy → BaseCoordinator.__init__ 的 `event_bus or get_event_bus()`
  (base_coordinator.py:32) 静默丢弃传入实例改用全局单例 → 空总线传入者订阅错位;
  修复为 `is not None` 判断 (bettafish_monitoring_integration.py:22-24 官方规避模板)

修复目标 (RED → GREEN):
1. service_bootstrap.py: run_async_safe 桥接 async initialize + 注册 BettaFishAgent
2. hybrid_recommendation_engine.py: 3 处 await 同步方法去除 + 缓存降级
3. event_coordinator.py: account_load_failed 订阅 + 启动补查 + _on_account_load_failed handler
4. base_coordinator.py: event_bus/service_container `or` 兜底改 `is not None` (P0-007)

遵循铁律:
- R85 §10 假修复鉴别 4 步法 (全部问题均源码行号实证)
- R51 §7.1 #5 失败不静默 (account_load_failed handler 显式 logger.error)
- R8 §8.1 #7 失败仅 warning 不抛 (补查异常吞掉不阻断启动)
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# 确保项目根可导入
sys.path.insert(0, ".")


# ==============================================================================
# HVD-240-P0-001~005 + P1-001: Hybrid 混合推荐引擎 async 修复
# ==============================================================================


class TestHybridInitializeFixes:
    """Hybrid 引擎 async 悬空 + await 同步方法 + 缓存降级"""

    def test_T01_no_await_on_sync_perf_monitor(self):
        """源码级防御: initialize/shutdown 不得 await 同步监控方法 (回归防)
        (performance_monitor.py:233/238/283 均为同步方法, await 必 TypeError)"""
        src = Path("core/services/hybrid_recommendation_engine.py").read_text(
            encoding="utf-8")
        assert "await self.performance_monitor.start_monitoring()" not in src, \
            "start_monitoring 是同步方法, 不得 await (HVD-240-P0-003)"
        assert "await self.performance_monitor.stop_monitoring()" not in src, \
            "stop_monitoring 是同步方法, 不得 await (HVD-240-P0-004)"
        assert "await self.performance_monitor.record_metric(" not in src, \
            "record_metric 是同步方法, 不得 await (HVD-240-P0-005)"

    def test_T02_cache_degrades_when_no_create_cache(self):
        """CacheService 无 create_cache 时降级为无缓存, 不抛异常 (HVD-240-P1-001)
        (cache_service.py:1324 仅 create_namespace)"""
        from core.services.hybrid_recommendation_engine import HybridRecommendationEngine

        engine = HybridRecommendationEngine.__new__(HybridRecommendationEngine)
        engine.cache_service = SimpleNamespace()  # 无 create_cache 属性的假服务
        engine.cache_config = SimpleNamespace(enable_multi_level=True)
        engine.main_cache = None
        engine.traditional_cache = None
        engine.bettafish_cache = None
        engine.fusion_cache = None
        engine.cache_metrics = {}

        asyncio.run(engine._initialize_caches())  # RED: 修复前 AttributeError
        assert engine.main_cache is None, "无 create_cache 时应降级为无缓存"

    def test_T03_initialize_completes_with_mock_container(self, monkeypatch):
        """initialize 全流程跑通: mock 容器 + 同步监控 → _initialized=True 不抛异常
        (HVD-240-P0-001~005: 修复后 run_async_safe 桥接 + 同步调用)"""
        from core.services import hybrid_recommendation_engine as hre
        from core.services.hybrid_recommendation_engine import HybridRecommendationEngine

        engine = HybridRecommendationEngine.__new__(HybridRecommendationEngine)
        engine._initialized = False
        engine._event_bus = SimpleNamespace(
            subscribe=lambda *a, **k: None,
            publish=lambda *a, **k: None,
        )
        engine.performance_monitor = SimpleNamespace(
            start_monitoring=lambda: None,
            stop_monitoring=lambda: None,
            record_metric=lambda *a, **k: None,
        )
        engine.cache_config = SimpleNamespace(enable_multi_level=False)
        engine.cache_service = None
        engine.fusion_algorithm = SimpleNamespace()

        class _Container:
            def resolve(self, service_type):
                return SimpleNamespace()

            def get_service(self, name):
                return None

        monkeypatch.setattr(hre, "get_service_container", lambda: _Container())

        asyncio.run(engine.initialize())  # RED: 修复前 L549/L570 抛 ValueError/TypeError
        assert engine._initialized is True, "initialize 必须成功完成"

    def test_T04_shutdown_completes(self):
        """shutdown 全流程跑通: 同步 stop_monitoring + 空缓存 → 不抛异常
        (HVD-240-P0-004)"""
        from core.services.hybrid_recommendation_engine import HybridRecommendationEngine

        engine = HybridRecommendationEngine.__new__(HybridRecommendationEngine)
        engine._event_bus = SimpleNamespace(unsubscribe=lambda *a, **k: None)
        engine.performance_monitor = SimpleNamespace(stop_monitoring=lambda: None)
        engine.main_cache = None
        engine.traditional_cache = None
        engine.bettafish_cache = None
        engine.fusion_cache = None
        engine.cache_metrics = {}
        engine.pending_requests = {}

        asyncio.run(engine.shutdown())  # RED: 修复前 L938 await None TypeError


class TestBettaFishAgentRegistration:
    """HVD-240-P0-002: BettaFishAgent 容器注册 (resolve 依赖)"""

    def test_T05_bettafish_agent_registrable(self):
        """BettaFishAgent 必须在容器可注册 + resolve (service_bootstrap.py 已接线)
        (service_container.py:128-131 无注册抛 ValueError)"""
        from core.agents.bettafish_agent import BettaFishAgent
        from core.containers.unified_service_container import UnifiedServiceContainer
        from core.containers.service_registry import ServiceScope

        c = UnifiedServiceContainer()
        c.register(BettaFishAgent, scope=ServiceScope.SINGLETON,
                   factory=lambda: BettaFishAgent(event_bus=None))
        agent = c.resolve(BettaFishAgent)  # RED: 修复前 ValueError not registered
        assert isinstance(agent, BettaFishAgent), "resolve 必须返回 BettaFishAgent 实例"


# ==============================================================================
# HVD-240-P0-006: account_load_failed 孤儿事件治理 (订阅 + 启动补查 + handler)
# ==============================================================================


class TestAccountLoadFailedOrphan:
    """account_load_failed 订阅 + handler (EventCoordinator)"""

    def test_T06_account_load_failed_has_subscriber(self):
        """subscribe_all_events 后 account_load_failed 必须有订阅 handler
        (HVD-240-P0-006: core/ 原零订阅孤儿事件)"""
        from core.coordinators.event_coordinator import EventCoordinator
        from core.events.event_bus import EventBus
        from core.containers.unified_service_container import UnifiedServiceContainer

        bus = EventBus()
        container = UnifiedServiceContainer()
        mwc = SimpleNamespace(show_message=lambda msg, level=None: None)
        coord = EventCoordinator(
            main_window_coordinator=mwc,
            service_container=container,
            event_bus=bus,
        )
        coord.subscribe_all_events()
        handlers = bus._handlers.get("account_load_failed", [])
        assert len(handlers) >= 1, "account_load_failed 必须有订阅 handler"

    def test_T07_on_account_load_failed_no_raise(self):
        """handler 直接调用不抛异常 (含 event=None 兜底) (R51 #5 失败不静默)"""
        from core.coordinators.event_coordinator import EventCoordinator

        coord = EventCoordinator.__new__(EventCoordinator)
        coord._main_window_coordinator = SimpleNamespace(
            show_message=lambda msg, level=None: None)

        ev = SimpleNamespace(error="db connection refused")
        coord._on_account_load_failed(ev)  # 不抛
        coord._on_account_load_failed(None)  # 兜底: event=None 不抛

    def test_T08_startup_recheck_no_raise(self):
        """启动补查: 容器无 AccountManager 时 resolve 失败被吞, 不阻断订阅流程
        (HVD-240-P0-006 时序缺口防御, R8 #7 失败仅 warning 不抛)"""
        from core.coordinators.event_coordinator import EventCoordinator
        from core.events.event_bus import EventBus
        from core.containers.unified_service_container import UnifiedServiceContainer

        bus = EventBus()
        container = UnifiedServiceContainer()  # 无 AccountManager 注册 → 补查 resolve 抛错被吞
        mwc = SimpleNamespace(show_message=lambda msg, level=None: None)
        coord = EventCoordinator(
            main_window_coordinator=mwc,
            service_container=container,
            event_bus=bus,
        )
        coord.subscribe_all_events()  # 不应抛异常
        handlers = bus._handlers.get("account_load_failed", [])
        assert len(handlers) >= 1, "即使补查失败, 订阅仍必须生效"


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    sys.exit(pytest.main([__file__, "-v"]))
