#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试新增的缓存概览面板功能
"""

import sys
import os

def test_overview_panel_methods():
    """测试概览面板相关方法是否存在"""
    try:
        with open('gui/widgets/enhanced_ui/data_quality_monitor_tab.py', 'r', encoding='utf-8') as f:
            content = f.read()

        required_methods = [
            '_create_cache_overview_panel',
            '_update_cache_overview_panel'
        ]

        print("检查新增的概览面板方法...")
        for method in required_methods:
            if f'def {method}(' in content:
                print(f"[PASS] Method {method} exists")
            else:
                print(f"[FAIL] Method {method} not found")
                return False

        return True
    except Exception as e:
        print(f"[FAIL] Method check failed: {e}")
        return False

def test_cache_overview_table():
    """测试缓存概览表格是否存在"""
    try:
        with open('gui/widgets/enhanced_ui/data_quality_monitor_tab.py', 'r', encoding='utf-8') as f:
            content = f.read()

        if 'self.cache_overview_table = QTableWidget()' in content:
            print("[PASS] cache_overview_table表格已创建")
            return True
        else:
            print("[FAIL] cache_overview_table表格未找到")
            return False
    except Exception as e:
        print(f"[FAIL] cache_overview_table check failed: {e}")
        return False

def test_data_sources_in_collect():
    """测试数据收集方法中是否添加了数据来源标识"""
    try:
        with open('gui/widgets/enhanced_ui/data_quality_monitor_tab.py', 'r', encoding='utf-8') as f:
            content = f.read()

        if "data['data_sources']" in content:
            print("[PASS] Data sources标识已添加")
            return True
        else:
            print("[FAIL] Data sources标识未找到")
            return False
    except Exception as e:
        print(f"[FAIL] Data sources check failed: {e}")
        return False

def test_overview_panel_update():
    """测试概览面板更新是否被调用"""
    try:
        with open('gui/widgets/enhanced_ui/data_quality_monitor_tab.py', 'r', encoding='utf-8') as f:
            content = f.read()

        if '_update_cache_overview_panel(data)' in content:
            print("[PASS] 概览面板更新方法被调用")
            return True
        else:
            print("[FAIL] 概览面板更新方法未被调用")
            return False
    except Exception as e:
        print(f"[FAIL] Overview panel update check failed: {e}")
        return False

def test_smartdatacache_export():
    """测试SmartDataCache是否已导出"""
    try:
        with open('backtest/__init__.py', 'r', encoding='utf-8') as f:
            content = f.read()

        if "'SmartDataCache'" in content:
            print("[PASS] SmartDataCache在__all__中")
        else:
            print("[FAIL] SmartDataCache未在__all__中")
            return False

        if "name == 'SmartDataCache'" in content:
            print("[PASS] SmartDataCache在__getattr__中")
            return True
        else:
            print("[FAIL] SmartDataCache未在__getattr__中")
            return False
    except Exception as e:
        print(f"[FAIL] SmartDataCache export check failed: {e}")
        return False

def test_clear_cache_alias():
    """测试SmartDataCache的clear_cache别名是否存在"""
    try:
        with open('backtest/async_io_manager.py', 'r', encoding='utf-8') as f:
            content = f.read()

        if 'clear_cache = clear' in content:
            print("[PASS] SmartDataCache.clear_cache别名存在")
            return True
        else:
            print("[FAIL] SmartDataCache.clear_cache别名不存在")
            return False
    except Exception as e:
        print(f"[FAIL] clear_cache alias check failed: {e}")
        return False

def test_module_documentation():
    """测试模块文档是否已更新"""
    try:
        with open('backtest/async_io_manager.py', 'r', encoding='utf-8') as f:
            content = f.read()

        required_sections = [
            '架构设计',
            'Layer 1: AsyncIOManager',
            'Layer 2: SmartDataCache',
            '调用链示例',
            '监控集成'
        ]

        print("检查模块文档...")
        for section in required_sections:
            if section in content:
                print(f"[PASS] 文档部分 '{section}' 存在")
            else:
                print(f"[FAIL] 文档部分 '{section}' 不存在")
                return False

        return True
    except Exception as e:
        print(f"[FAIL] Module documentation check failed: {e}")
        return False

def test_cache_status_tracker():
    """测试缓存状态追踪器是否存在"""
    try:
        with open('backtest/async_io_manager.py', 'r', encoding='utf-8') as f:
            content = f.read()

        if '_CACHE_SYSTEMS' in content:
            print("[PASS] _CACHE_SYSTEMS字典存在")
        else:
            print("[FAIL] _CACHE_SYSTEMS字典不存在")
            return False

        if 'def get_all_cache_stats()' in content:
            print("[PASS] get_all_cache_stats函数存在")
            return True
        else:
            print("[FAIL] get_all_cache_stats函数不存在")
            return False
    except Exception as e:
        print(f"[FAIL] Cache status tracker check failed: {e}")
        return False

def run_all_tests():
    """运行所有测试"""
    print("=" * 70)
    print("新增功能测试 - 验证UI增强和代码规范")
    print("=" * 70)

    results = []

    print("\n[Test 1] 概览面板方法")
    print("-" * 70)
    results.append(("概览面板方法", test_overview_panel_methods()))

    print("\n[Test 2] 缓存概览表格")
    print("-" * 70)
    results.append(("缓存概览表格", test_cache_overview_table()))

    print("\n[Test 3] 数据来源标识")
    print("-" * 70)
    results.append(("数据来源标识", test_data_sources_in_collect()))

    print("\n[Test 4] 概览面板更新")
    print("-" * 70)
    results.append(("概览面板更新", test_overview_panel_update()))

    print("\n[Test 5] SmartDataCache导出")
    print("-" * 70)
    results.append(("SmartDataCache导出", test_smartdatacache_export()))

    print("\n[Test 6] clear_cache别名")
    print("-" * 70)
    results.append(("clear_cache别名", test_clear_cache_alias()))

    print("\n[Test 7] 模块文档")
    print("-" * 70)
    results.append(("模块文档", test_module_documentation()))

    print("\n[Test 8] 缓存状态追踪器")
    print("-" * 70)
    results.append(("缓存状态追踪器", test_cache_status_tracker()))

    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{test_name}: {status}")

    print("\n" + "=" * 70)
    print(f"总计: {passed}/{total} 通过")
    print("=" * 70)

    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
