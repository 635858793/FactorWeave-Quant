#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深度审核修复验证测试
验证: P0双容器统一 + P1额外直接实例化修复 + __init__.py修复
"""

import sys
sys.path.insert(0, '.')


def test_p0_dual_container_unification():
    print('=' * 60)
    print('P0: 双容器统一验证')
    print('=' * 60)

    try:
        from core.containers.unified_service_container import UnifiedServiceContainer
        from core.containers import ServiceContainer, get_service_container, set_service_container

        unified = UnifiedServiceContainer()
        set_service_container(unified)

        from core.containers.unified_service_container import get_unified_container
        container_a = get_service_container()
        container_b = get_unified_container()

        assert container_a is container_b, f'get_service_container()和get_unified_container()应返回同一实例: {id(container_a)} vs {id(container_b)}'
        assert isinstance(container_b, UnifiedServiceContainer), 'get_unified_container()应返回UnifiedServiceContainer'

        print('OK get_service_container()和get_unified_container()返回同一实例')
        print('OK 双容器系统已统一')
        print()
        return True
    except Exception as e:
        print(f'FAIL: {e}')
        import traceback
        traceback.print_exc()
        print()
        return False


def test_p0_init_py_get_unified_container():
    print('=' * 60)
    print('P0: __init__.py get_unified_container()验证')
    print('=' * 60)

    try:
        from core.containers.unified_service_container import UnifiedServiceContainer
        from core.containers import ServiceContainer, get_service_container, set_service_container

        unified = UnifiedServiceContainer()
        set_service_container(unified)

        from core.containers import get_unified_container
        container = get_unified_container()

        assert isinstance(container, UnifiedServiceContainer), f'__init__.py的get_unified_container()应返回UnifiedServiceContainer: {type(container)}'
        assert container is get_service_container(), '__init__.py的get_unified_container()应与get_service_container()返回同一实例'

        print('OK __init__.py的get_unified_container()正确委托')
        print()
        return True
    except Exception as e:
        print(f'FAIL: {e}')
        import traceback
        traceback.print_exc()
        print()
        return False


def test_p0_convenience_functions():
    print('=' * 60)
    print('P0: 便捷函数容器解析验证')
    print('=' * 60)

    try:
        from core.containers.unified_service_container import UnifiedServiceContainer
        from core.containers import ServiceContainer, get_service_container, set_service_container
        from core.containers.service_registry import ServiceScope

        unified = UnifiedServiceContainer()
        set_service_container(unified)

        from core.services.performance_service import PerformanceService
        unified.register_factory(
            PerformanceService,
            lambda: PerformanceService(),
            scope=ServiceScope.SINGLETON
        )

        from core.services.performance_service import get_performance_service
        service = get_performance_service()
        assert service is not None, 'get_performance_service()应返回非None'
        assert isinstance(service, PerformanceService), f'应返回PerformanceService实例: {type(service)}'

        print('OK get_performance_service()从统一容器解析成功')
        print()
        return True
    except Exception as e:
        print(f'FAIL: {e}')
        import traceback
        traceback.print_exc()
        print()
        return False


def test_p1_deep_analysis_service_registration():
    print('=' * 60)
    print('P1: DeepAnalysisService注册验证')
    print('=' * 60)

    try:
        from core.services.deep_analysis_service import DeepAnalysisService
        from core.containers.unified_service_container import UnifiedServiceContainer
        from core.containers import get_service_container, set_service_container
        from core.containers.service_registry import ServiceScope

        unified = UnifiedServiceContainer()
        set_service_container(unified)

        unified.register_factory(
            DeepAnalysisService,
            lambda: DeepAnalysisService(),
            scope=ServiceScope.SINGLETON
        )

        service = unified.resolve(DeepAnalysisService)
        assert service is not None, 'DeepAnalysisService解析应成功'
        assert isinstance(service, DeepAnalysisService), f'应返回DeepAnalysisService实例: {type(service)}'

        service2 = unified.resolve(DeepAnalysisService)
        assert service is service2, '单例模式应返回同一实例'

        print('OK DeepAnalysisService注册并解析成功')
        print('OK 单例模式验证通过')
        print()
        return True
    except Exception as e:
        print(f'FAIL: {e}')
        import traceback
        traceback.print_exc()
        print()
        return False


def test_p1_plugin_database_service_registration():
    print('=' * 60)
    print('P1: PluginDatabaseService注册验证')
    print('=' * 60)

    try:
        from core.services.plugin_database_service import PluginDatabaseService
        from core.containers.unified_service_container import UnifiedServiceContainer
        from core.containers import get_service_container, set_service_container
        from core.containers.service_registry import ServiceScope

        unified = UnifiedServiceContainer()
        set_service_container(unified)

        unified.register_factory(
            PluginDatabaseService,
            lambda: PluginDatabaseService(),
            scope=ServiceScope.SINGLETON
        )

        service = unified.resolve(PluginDatabaseService)
        assert service is not None, 'PluginDatabaseService解析应成功'
        assert isinstance(service, PluginDatabaseService), f'应返回PluginDatabaseService实例: {type(service)}'

        print('OK PluginDatabaseService注册并解析成功')
        print()
        return True
    except Exception as e:
        print(f'FAIL: {e}')
        import traceback
        traceback.print_exc()
        print()
        return False


def test_p1_data_quality_risk_manager_container_resolution():
    print('=' * 60)
    print('P1: DataQualityRiskManager容器解析验证')
    print('=' * 60)

    try:
        from core.data_quality_risk_manager import DataQualityRiskManager
        from core.containers.unified_service_container import UnifiedServiceContainer
        from core.containers import get_service_container, set_service_container
        from core.containers.service_registry import ServiceScope

        unified = UnifiedServiceContainer()
        set_service_container(unified)

        unified.register_factory(
            DataQualityRiskManager,
            lambda: DataQualityRiskManager(),
            scope=ServiceScope.SINGLETON
        )

        service = unified.resolve(DataQualityRiskManager)
        assert service is not None, 'DataQualityRiskManager解析应成功'

        print('OK DataQualityRiskManager容器解析成功')
        print()
        return True
    except Exception as e:
        print(f'FAIL: {e}')
        import traceback
        traceback.print_exc()
        print()
        return False


def test_service_bootstrap_new_registrations():
    print('=' * 60)
    print('service_bootstrap.py新注册验证')
    print('=' * 60)

    try:
        with open('core/services/service_bootstrap.py', 'r', encoding='utf-8') as f:
            content = f.read()

        checks = [
            ('DeepAnalysisService注册', 'DeepAnalysisService注册完成' in content),
            ('PluginDatabaseService注册', 'PluginDatabaseService注册完成' in content),
            ('BettaFishMonitoringService注册', 'BettaFish监控服务注册完成' in content),
            ('IndicatorService注册', 'IndicatorService注册完成' in content),
            ('PerformanceService注册', 'PerformanceService注册完成' in content),
            ('LifecycleService注册', 'LifecycleService注册完成' in content),
            ('EnvironmentService注册', 'EnvironmentService注册完成' in content),
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


def test_unified_container_source_code():
    print('=' * 60)
    print('unified_service_container.py源码验证')
    print('=' * 60)

    try:
        with open('core/containers/unified_service_container.py', 'r', encoding='utf-8') as f:
            content = f.read()

        checks = [
            ('get_unified_container委托get_service_container', 'from .service_container import get_service_container' in content),
            ('isinstance检查', 'isinstance(container, UnifiedServiceContainer)' in content),
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


def test_init_py_source_code():
    print('=' * 60)
    print('__init__.py源码验证')
    print('=' * 60)

    try:
        with open('core/containers/__init__.py', 'r', encoding='utf-8') as f:
            content = f.read()

        checks = [
            ('get_unified_container委托', 'from .unified_service_container import get_unified_container' in content),
            ('不再调用get_instance()', '.get_instance()' not in content),
            ('set_service_container导出', 'set_service_container' in content),
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


def test_p1_direct_instantiation_files():
    print('=' * 60)
    print('P1: 直接实例化修复文件验证')
    print('=' * 60)

    try:
        files_to_check = {
            'core/services/uni_plugin_data_manager.py': [
                ('容器解析DataQualityRiskManager', 'get_service_container().resolve(DataQualityRiskManager)' in open('core/services/uni_plugin_data_manager.py', 'r', encoding='utf-8').read()),
            ],
            'core/services/data_service.py': [
                ('容器解析DataQualityRiskManager', 'get_service_container().resolve(DataQualityRiskManager)' in open('core/services/data_service.py', 'r', encoding='utf-8').read()),
            ],
            'core/importdata/unified_data_import_engine.py': [
                ('容器解析DeepAnalysisService', 'get_service_container().resolve(DeepAnalysisService)' in open('core/importdata/unified_data_import_engine.py', 'r', encoding='utf-8').read()),
            ],
            'core/importdata/import_execution_engine.py': [
                ('容器解析DeepAnalysisService', 'get_service_container().resolve(DeepAnalysisService)' in open('core/importdata/import_execution_engine.py', 'r', encoding='utf-8').read()),
            ],
            'core/plugin_manager.py': [
                ('容器解析PluginDatabaseService', 'get_service_container().resolve(PluginDatabaseService)' in open('core/plugin_manager.py', 'r', encoding='utf-8').read()),
            ],
        }

        all_pass = True
        for filename, checks in files_to_check.items():
            for desc, result in checks:
                if result:
                    print(f'OK {filename}: {desc}')
                else:
                    print(f'FAIL {filename}: {desc}')
                    all_pass = False

        print()
        return all_pass
    except Exception as e:
        print(f'FAIL: {e}')
        print()
        return False


if __name__ == '__main__':
    print('\n' + '=' * 60)
    print('深度审核修复验证测试')
    print('=' * 60 + '\n')

    results = {}

    results['P0 双容器统一'] = test_p0_dual_container_unification()
    results['P0 __init__.py修复'] = test_p0_init_py_get_unified_container()
    results['P0 便捷函数验证'] = test_p0_convenience_functions()
    results['P1 DeepAnalysisService注册'] = test_p1_deep_analysis_service_registration()
    results['P1 PluginDatabaseService注册'] = test_p1_plugin_database_service_registration()
    results['P1 DataQualityRiskManager解析'] = test_p1_data_quality_risk_manager_container_resolution()
    results['service_bootstrap新注册'] = test_service_bootstrap_new_registrations()
    results['unified_container源码'] = test_unified_container_source_code()
    results['__init__.py源码'] = test_init_py_source_code()
    results['P1 直接实例化修复文件'] = test_p1_direct_instantiation_files()

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
