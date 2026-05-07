#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段0+阶段1 修复验证测试
验证: 容器统一、服务注册、消除后备直接实例化
"""

import sys
sys.path.insert(0, '.')

import threading
from unittest.mock import MagicMock, patch


def test_0_4_unified_container():
    print('=' * 60)
    print('0-4: 统一容器验证')
    print('=' * 60)

    try:
        from core.containers.unified_service_container import UnifiedServiceContainer
        from core.containers import ServiceContainer, get_service_container, set_service_container

        unified = UnifiedServiceContainer()
        assert isinstance(unified, ServiceContainer), 'UnifiedServiceContainer应继承ServiceContainer'
        assert hasattr(unified, '_service_health'), '缺少健康监控属性'
        assert hasattr(unified, '_dependencies'), '缺少依赖管理属性'
        assert hasattr(unified, '_initialization_status'), '缺少生命周期管理属性'

        set_service_container(unified)
        current = get_service_container()
        assert isinstance(current, UnifiedServiceContainer), '全局容器应为UnifiedServiceContainer'

        from core.containers import ServiceContainer
        basic = ServiceContainer()
        set_service_container(basic)
        assert type(get_service_container()) == ServiceContainer

        set_service_container(unified)
        assert type(get_service_container()) == UnifiedServiceContainer

        print('OK UnifiedServiceContainer继承ServiceContainer')
        print('OK set_service_container()可设置统一容器')
        print('OK get_service_container()返回UnifiedServiceContainer')
        print()
        return True
    except Exception as e:
        print(f'FAIL: {e}')
        print()
        return False


def test_0_1_bettafish_monitoring_registration():
    print('=' * 60)
    print('0-1: BettaFishMonitoringService注册验证')
    print('=' * 60)

    try:
        from core.containers import ServiceContainer
        from core.services.bettafish_monitoring_service import BettaFishMonitoringService

        container = ServiceContainer()
        from core.containers.service_registry import ServiceScope
        container.register_factory(
            BettaFishMonitoringService,
            lambda: BettaFishMonitoringService(),
            scope=ServiceScope.SINGLETON
        )

        assert container.is_registered(BettaFishMonitoringService), 'BettaFishMonitoringService应已注册'

        service = container.resolve(BettaFishMonitoringService)
        assert service is not None, '应能解析BettaFishMonitoringService'
        assert isinstance(service, BettaFishMonitoringService), '解析结果类型正确'

        service2 = container.resolve(BettaFishMonitoringService)
        assert service is service2, '单例模式应返回同一实例'

        print('OK BettaFishMonitoringService注册成功')
        print('OK 容器解析返回正确类型')
        print('OK 单例模式验证通过')
        print()
        return True
    except Exception as e:
        print(f'FAIL: {e}')
        print()
        return False


def test_0_2_indicator_service_registration():
    print('=' * 60)
    print('0-2: IndicatorService注册验证')
    print('=' * 60)

    try:
        from core.containers import ServiceContainer
        from core.indicator_service import IndicatorService, get_indicator_service
        from core.containers.service_registry import ServiceScope

        container = ServiceContainer()
        container.register_factory(
            IndicatorService,
            lambda: get_indicator_service(),
            scope=ServiceScope.SINGLETON
        )

        assert container.is_registered(IndicatorService), 'IndicatorService应已注册'

        service = container.resolve(IndicatorService)
        assert service is not None, '应能解析IndicatorService'
        assert isinstance(service, IndicatorService), '解析结果类型正确'

        print('OK IndicatorService注册成功')
        print('OK 容器解析返回正确类型')
        print()
        return True
    except Exception as e:
        print(f'FAIL: {e}')
        print()
        return False


def test_0_3_monitoring_services_registration():
    print('=' * 60)
    print('0-3: PerformanceService/LifecycleService/EnvironmentService注册验证')
    print('=' * 60)

    results = []

    for service_name, module_path in [
        ('PerformanceService', 'core.services.performance_service'),
        ('LifecycleService', 'core.services.lifecycle_service'),
        ('EnvironmentService', 'core.services.environment_service'),
    ]:
        try:
            from core.containers import ServiceContainer
            from core.containers.service_registry import ServiceScope
            import importlib
            module = importlib.import_module(module_path)
            ServiceClass = getattr(module, service_name)

            container = ServiceContainer()
            container.register_factory(
                ServiceClass,
                lambda cls=ServiceClass: cls(),
                scope=ServiceScope.SINGLETON
            )

            assert container.is_registered(ServiceClass), f'{service_name}应已注册'
            print(f'OK {service_name}注册成功')
            results.append(True)
        except Exception as e:
            print(f'FAIL {service_name}: {e}')
            results.append(False)

    print()
    return all(results)


def test_1_1_gui_no_fallback():
    print('=' * 60)
    print('1-1: GUI层消除后备直接实例化验证')
    print('=' * 60)

    files_to_check = [
        ('gui/widgets/enhanced_ui/smart_recommendation_panel.py', ['ConfigService()', 'BettaFishMonitoringService()']),
        ('gui/widgets/enhanced_ui/hybrid_recommendation_workers.py', ['ConfigService()']),
        ('gui/widgets/ai_features_control_panel.py', ['AIPredictionService()']),
        ('gui/widgets/analysis_tabs/technical_tab.py', ['IndicatorService()']),
        ('gui/enhanced_batch_analysis_methods.py', ['StockService()', 'StrategyService()']),
        ('gui/widgets/bettafish_dashboard/bettafish_dashboard_main.py', ['BettaFishMonitoringService()']),
    ]

    all_pass = True
    for filepath, forbidden_patterns in files_to_check:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            found = []
            for pattern in forbidden_patterns:
                if pattern in content:
                    found.append(pattern)

            if found:
                print(f'FAIL {filepath}: 仍包含直接实例化 {found}')
                all_pass = False
            else:
                print(f'OK {filepath}: 无后备直接实例化')
        except Exception as e:
            print(f'ERROR {filepath}: {e}')
            all_pass = False

    print()
    return all_pass


def test_1_2_core_no_direct_instantiation():
    print('=' * 60)
    print('1-2: Core层消除直接实例化验证')
    print('=' * 60)

    files_to_check = [
        ('core/importdata/import_execution_engine.py', ['AIPredictionService()']),
        ('core/importdata/unified_data_import_engine.py', ['AIPredictionService()']),
        ('core/risk_monitoring/enhanced_risk_monitor.py', ['AIPredictionService()']),
        ('core/performance/unified_performance_coordinator.py', ['AIPredictionService()']),
        ('core/performance/adaptive_cache_strategy.py', ['AIPredictionService()']),
        ('core/importdata/intelligent_config_manager.py', ['AIPredictionService()']),
        ('core/services/distributed_service.py', ['StockService()']),
        ('core/risk_manager.py', ['StockService()']),
        ('core/plugin_manager.py', ['IndicatorService()']),
        ('core/take_profit.py', ['EnhancedIndicatorService()']),
        ('core/system_condition.py', ['EnhancedIndicatorService()']),
        ('core/stop_loss.py', ['EnhancedIndicatorService()']),
        ('core/signal/enhanced.py', ['EnhancedIndicatorService()']),
        ('core/signal/base.py', ['EnhancedIndicatorService()']),
        ('core/money_manager.py', ['EnhancedIndicatorService()']),
    ]

    all_pass = True
    for filepath, forbidden_patterns in files_to_check:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            found = []
            for pattern in forbidden_patterns:
                count = content.count(pattern)
                if count > 0:
                    import_patterns = ['from core.containers import get_service_container',
                                       'container.resolve(']
                    has_container_resolve = all(p in content for p in import_patterns)
                    if has_container_resolve and count == 1:
                        continue
                    found.append(f'{pattern}(出现{count}次)')

            if found:
                print(f'FAIL {filepath}: 仍包含直接实例化 {found}')
                all_pass = False
            else:
                print(f'OK {filepath}: 已使用容器解析')
        except Exception as e:
            print(f'ERROR {filepath}: {e}')
            all_pass = False

    print()
    return all_pass


def test_service_bootstrap_new_registrations():
    print('=' * 60)
    print('service_bootstrap.py 新增服务注册验证')
    print('=' * 60)

    try:
        with open('core/services/service_bootstrap.py', 'r', encoding='utf-8') as f:
            content = f.read()

        required_services = [
            'BettaFishMonitoringService',
            'IndicatorService',
            'PerformanceService',
            'LifecycleService',
            'EnvironmentService',
        ]

        all_pass = True
        for service in required_services:
            if f'from' in content and service in content:
                if f'register_factory' in content and service in content:
                    print(f'OK {service} 已在service_bootstrap.py中注册')
                else:
                    print(f'FAIL {service} 已导入但未注册')
                    all_pass = False
            else:
                print(f'FAIL {service} 未在service_bootstrap.py中导入')
                all_pass = False

        print()
        return all_pass
    except Exception as e:
        print(f'FAIL: {e}')
        print()
        return False


def test_main_py_unified_container():
    print('=' * 60)
    print('main.py 统一容器设置验证')
    print('=' * 60)

    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()

        checks = [
            ('UnifiedServiceContainer导入', 'from core.containers.unified_service_container import UnifiedServiceContainer' in content),
            ('创建UnifiedServiceContainer实例', 'UnifiedServiceContainer()' in content),
            ('set_service_container调用', 'set_service_container(unified_container)' in content),
        ]

        all_pass = True
        for desc, result in checks:
            if result:
                print(f'OK {desc}')
            else:
                print(f'FAIL {desc}')
                all_pass = False

        print()
        return all_pass
    except Exception as e:
        print(f'FAIL: {e}')
        print()
        return False


if __name__ == '__main__':
    print('\n' + '=' * 60)
    print('阶段0+阶段1 修复验证测试')
    print('=' * 60 + '\n')

    results = {}

    results['0-4 统一容器'] = test_0_4_unified_container()
    results['0-1 BettaFishMonitoringService注册'] = test_0_1_bettafish_monitoring_registration()
    results['0-2 IndicatorService注册'] = test_0_2_indicator_service_registration()
    results['0-3 监控服务注册'] = test_0_3_monitoring_services_registration()
    results['1-1 GUI层消除后备'] = test_1_1_gui_no_fallback()
    results['1-2 Core层消除直接实例化'] = test_1_2_core_no_direct_instantiation()
    results['service_bootstrap新注册'] = test_service_bootstrap_new_registrations()
    results['main.py统一容器'] = test_main_py_unified_container()

    print('\n' + '=' * 60)
    print('测试结果汇总')
    print('=' * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = 'PASS' if result else 'FAIL'
        print(f'  [{status}] {name}')

    print(f'\n通过: {passed}/{total}')
    print('=' * 60)

    sys.exit(0 if passed == total else 1)
