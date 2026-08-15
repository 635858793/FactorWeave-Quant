# -*- coding: utf-8 -*-
"""R273-A 集成测试: AdvancedRiskControlService 注册到服务容器 (2026-08-09)

背景:
- R273 死代码价值评估确认 AdvancedRiskControlService 为高价值死代码 (价值 7/10,
  无同等功能等价物), 全仓库 0 注册点/0 消费, 用户已授权融入系统。
- 另一子智能体已完成清理: 其 __init__ 挂起实例 (RiskControlStrategy/RiskMonitor)
  已替换为 PositionRiskMonitor 活跃实例。

本文件验证 (真实容器 + 真实注册 + 真实实例化 + 真实方法调用, 不 mock 核心逻辑):
- A (注册): service_bootstrap 注册块模式 (register_factory + SINGLETON) 可执行,
  AdvancedRiskControlService 注册进真实容器。
- B (resolve): 容器 resolve 得到真实实例 (sklearn 模型真实初始化), SINGLETON 单例。
- C (依赖注入): 实例 service_container 指向容器; 容器内先注册 PositionRiskMonitor
  时, 实例内部解析到活跃 PositionRiskMonitor (挂起实例已替换)。
- D (消费): 真实方法调用 get_current_risk_assessment / update_alert_thresholds /
  get_model_performance / _calculate_overall_risk_score 端到端可用。
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.risk, pytest.mark.r273]


def _make_container():
    from core.containers import ServiceContainer
    return ServiceContainer()


def _register_advanced_service_v2(container):
    """与 service_bootstrap.py R273-A 注册块完全相同的注册模式 (真实代码路径)。"""
    from core.containers.service_registry import ServiceScope
    from core.services.advanced_risk_control_service import AdvancedRiskControlService
    if not container.is_registered(AdvancedRiskControlService):
        container.register_factory(
            AdvancedRiskControlService,
            lambda: AdvancedRiskControlService(service_container=container),
            scope=ServiceScope.SINGLETON,
        )
    return AdvancedRiskControlService


def test_bootstrap_module_importable():
    """bootstrap 模块 + 注册块依赖 import 可执行 (注册不会因 import 失败拖垮启动)。"""
    from core.services import service_bootstrap
    from core.services.service_bootstrap import ServiceBootstrap
    assert hasattr(ServiceBootstrap, '_register_trading_services')
    # 注册块内的延迟 import 语句必须可用
    from core.services.advanced_risk_control_service import AdvancedRiskControlService
    assert AdvancedRiskControlService.__name__ == 'AdvancedRiskControlService'


def test_registration_and_singleton_resolve():
    """真实容器注册 → resolve → SINGLETON 单例 → 真实实例 (sklearn 模型初始化)。"""
    container = _make_container()
    AdvancedRiskControlService = _register_advanced_service_v2(container)

    assert container.is_registered(AdvancedRiskControlService)

    svc = container.resolve(AdvancedRiskControlService)
    assert isinstance(svc, AdvancedRiskControlService)

    # SINGLETON: 二次 resolve 同一实例
    assert container.resolve(AdvancedRiskControlService) is svc

    # 容器注入
    assert svc.service_container is container

    # sklearn 模型真实初始化
    assert 'anomaly_detection' in svc.ml_models
    assert 'risk_prediction' in svc.ml_models
    assert 'risk_features' in svc.scalers


def test_internal_position_risk_monitor_resolution():
    """挂起实例已替换: 容器内注册 PositionRiskMonitor 时, 实例内部解析活跃实例。"""
    from core.containers.service_registry import ServiceScope
    from core.services.advanced_risk_control_service import AdvancedRiskControlService
    from core.trading.position_risk_monitor import PositionRiskMonitor

    container = _make_container()
    container.register_factory(
        PositionRiskMonitor,
        lambda: PositionRiskMonitor(service_container=container),
        scope=ServiceScope.SINGLETON,
    )
    container.register_factory(
        AdvancedRiskControlService,
        lambda: AdvancedRiskControlService(service_container=container),
        scope=ServiceScope.SINGLETON,
    )

    svc = container.resolve(AdvancedRiskControlService)
    assert svc.position_risk_monitor is not None
    assert isinstance(svc.position_risk_monitor, PositionRiskMonitor)

    # 消费: 动态止损价查询 (真实方法调用, 无 K 线走固定比例降级)
    stop_price = svc.position_risk_monitor.get_dynamic_stop_price('000001.SZ', current_price=10.0)
    assert stop_price is not None and stop_price > 0


def test_consumer_methods_end_to_end():
    """真实消费: get_current_risk_assessment / update_alert_thresholds /
    get_model_performance / _calculate_overall_risk_score 端到端可用。"""
    container = _make_container()
    AdvancedRiskControlService = _register_advanced_service_v2(container)
    svc = container.resolve(AdvancedRiskControlService)

    # 无数据时的评估状态
    assessment = svc.get_current_risk_assessment()
    assert assessment['status'] == 'no_data'

    # 更新告警阈值 (真实字段)
    svc.update_alert_thresholds({'risk_score': 0.9, 'volatility': 0.35})
    assert svc.alert_thresholds['risk_score'] == 0.9
    assert svc.alert_thresholds['volatility'] == 0.35

    # 模型性能缓存
    assert svc.get_model_performance() == {}

    # 综合风险评分 (真实计算路径: 用高级指标 dataclass)
    from core.services.advanced_risk_control_service import AdvancedRiskMetrics
    metrics = AdvancedRiskMetrics(
        cvar=-0.05, drawdown_risk=-0.12, tail_risk=0.02,
        correlation_breakdown=0.3, liquidity_at_risk=0.1,
        volatility_forecast=0.2, herding_risk=0.4, sentiment_risk=0.1,
        entropic_risk=1.0, spectral_risk=-0.01,
    )
    score = svc._calculate_overall_risk_score(metrics)
    assert 0.0 <= score <= 1.0

    # 风险等级映射
    assert svc._get_risk_level(0.9) == 'critical'
    assert svc._get_risk_level(0.65) == 'high'
    assert svc._get_risk_level(0.4) == 'medium'
    assert svc._get_risk_level(0.1) == 'low'
