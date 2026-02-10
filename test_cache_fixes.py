#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cache Monitoring Full Test - Verify All Fixes
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_async_io_manager_data():
    """Test AsyncIOManager data retrieval and fixes"""
    try:
        from backtest.async_io_manager import async_io_manager

        print("[PASS] AsyncIOManager imported successfully")

        stats = async_io_manager.get_cache_stats()
        print("[PASS] get_cache_stats returns data:")
        for key, value in stats.items():
            print(f"  - {key}: {value}")

        required_keys = [
            'cache_size', 'max_cache_size', 'hit_rate', 
            'total_hits', 'total_misses', 'io_operations',
            'async_operations', 'avg_response_time', 'max_response_time',
            'response_time_samples'
        ]

        missing_keys = [key for key in required_keys if key not in stats]
        if missing_keys:
            print(f"[FAIL] Missing fields: {missing_keys}")
            return False

        print("[PASS] All required data fields exist")
        return True
    except Exception as e:
        print(f"[FAIL] AsyncIOManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_io_operations_fix():
    """Test io_operations fix"""
    try:
        from backtest.async_io_manager import AsyncIOManager

        test_manager = AsyncIOManager(cache_size=10)

        initial_io_ops = test_manager.get_cache_stats()['io_operations']
        print(f"[PASS] Initial io_operations: {initial_io_ops}")

        test_manager._put_to_cache("test_key1", "test_data_1")
        test_manager._put_to_cache("test_key2", "test_data_2")

        result = test_manager._get_from_cache("test_key1")
        result = test_manager._get_from_cache("non_existent_key")

        stats = test_manager.get_cache_stats()
        io_ops = stats['io_operations']

        print(f"[PASS] After test io_operations: {io_ops}")

        if io_ops > 0:
            print("[PASS] io_operations updated correctly")
            return True
        else:
            print("[FAIL] io_operations not updated")
            return False
    except Exception as e:
        print(f"[FAIL] io_operations test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_response_time_tracking():
    """Test response time tracking"""
    try:
        from backtest.async_io_manager import AsyncIOManager

        test_manager = AsyncIOManager(cache_size=10)
        test_manager._put_to_cache("test_key", "test_data")
        test_manager._get_from_cache("test_key")

        stats = test_manager.get_cache_stats()
        response_time_samples = stats['response_time_samples']
        avg_response_time = stats['avg_response_time']

        print(f"[PASS] Response time samples: {response_time_samples}")
        print(f"[PASS] Avg response time: {avg_response_time:.4f} ms")

        if response_time_samples > 0:
            print("[PASS] Response time tracking works")
            return True
        else:
            print("[FAIL] Response time not recorded")
            return False
    except Exception as e:
        print(f"[FAIL] Response time test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_clear_cache_resets_io():
    """Test clear_cache resets io_operations"""
    try:
        from backtest.async_io_manager import AsyncIOManager

        test_manager = AsyncIOManager(cache_size=10)
        test_manager._put_to_cache("test_key", "test_data")
        test_manager._get_from_cache("test_key")
        test_manager.clear_cache()

        stats = test_manager.get_cache_stats()
        io_ops = stats['io_operations']

        print(f"[PASS] After clear io_operations: {io_ops}")

        if io_ops == 0:
            print("[PASS] clear_cache correctly resets io_operations")
            return True
        else:
            print("[FAIL] clear_cache did not reset io_operations")
            return False
    except Exception as e:
        print(f"[FAIL] clear_cache test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_smart_cache_integration():
    """Test SmartDataCache integration"""
    try:
        from backtest.async_io_manager import smart_cache

        print("[PASS] SmartDataCache imported successfully")

        stats = smart_cache.get_stats()
        print("[PASS] SmartDataCache stats:")
        for key, value in stats.items():
            print(f"  - {key}: {value}")

        return True
    except Exception as e:
        print(f"[FAIL] SmartDataCache test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_file_syntax():
    """Test file syntax"""
    try:
        import py_compile

        files_to_check = [
            'gui/widgets/enhanced_ui/data_quality_monitor_tab.py',
            'backtest/async_io_manager.py'
        ]

        for file_path in files_to_check:
            py_compile.compile(file_path, doraise=True)
            print(f"[PASS] {file_path} syntax OK")

        return True
    except Exception as e:
        print(f"[FAIL] Syntax check failed: {e}")
        return False

def test_ui_components():
    """Test UI component definitions"""
    try:
        with open('gui/widgets/enhanced_ui/data_quality_monitor_tab.py', 'r', encoding='utf-8') as f:
            content = f.read()

        new_metrics = [
            "容量使用率", "预热状态", "淘汰策略", "内存占用",
            "最大响应时间", "异步操作数", "数据样本数", "缓存项上限"
        ]

        removed_metrics = [
            "缓存碎片率", "平均访问时间", "磁盘占用"
        ]

        for metric in new_metrics:
            if metric in content:
                print(f"[PASS] Metric '{metric}' defined")
            else:
                print(f"[FAIL] Metric '{metric}' not found")
                return False

        for metric in removed_metrics:
            if metric not in content:
                print(f"[PASS] Fictitious metric '{metric}' removed")
            else:
                print(f"[FAIL] Fictitious metric '{metric}' still exists")
                return False

        return True
    except Exception as e:
        print(f"[FAIL] UI component test failed: {e}")
        return False

def test_methods_exist():
    """Test key methods exist"""
    try:
        with open('gui/widgets/enhanced_ui/data_quality_monitor_tab.py', 'r', encoding='utf-8') as f:
            content = f.read()

        required_methods = [
            '_collect_cache_data_async',
            '_collect_cache_data_background',
            '_on_cache_data_collected',
            '_update_cache_stats_with_data',
            '_validate_cache_stats',
            '_show_cache_no_data',
            '_clear_cache',
            '_show_cache_stats'
        ]

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

def test_data_quality_monitor_import():
    """Test DataQualityMonitorTab import"""
    try:
        from gui.widgets.enhanced_ui.data_quality_monitor_tab import DataQualityMonitorTab
        print("[PASS] DataQualityMonitorTab imported successfully")
        return True
    except Exception as e:
        print(f"[FAIL] DataQualityMonitorTab import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("Cache Monitoring Full Test - Verify All Fixes")
    print("=" * 70)

    results = []

    print("\n[Test 1] AsyncIOManager Data Retrieval")
    print("-" * 70)
    results.append(("AsyncIOManager Data", test_async_io_manager_data()))

    print("\n[Test 2] io_operations Fix")
    print("-" * 70)
    results.append(("io_operations Fix", test_io_operations_fix()))

    print("\n[Test 3] Response Time Tracking")
    print("-" * 70)
    results.append(("Response Time", test_response_time_tracking()))

    print("\n[Test 4] clear_cache Resets io_operations")
    print("-" * 70)
    results.append(("clear_cache Reset", test_clear_cache_resets_io()))

    print("\n[Test 5] SmartDataCache Integration")
    print("-" * 70)
    results.append(("SmartDataCache", test_smart_cache_integration()))

    print("\n[Test 6] File Syntax")
    print("-" * 70)
    results.append(("File Syntax", test_file_syntax()))

    print("\n[Test 7] UI Components")
    print("-" * 70)
    results.append(("UI Components", test_ui_components()))

    print("\n[Test 8] Key Methods")
    print("-" * 70)
    results.append(("Key Methods", test_methods_exist()))

    print("\n[Test 9] DataQualityMonitorTab Import")
    print("-" * 70)
    results.append(("Tab Import", test_data_quality_monitor_import()))

    print("\n" + "=" * 70)
    print("Test Results Summary")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{test_name}: {status}")

    print("-" * 70)
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 70)

    if passed == total:
        print("\n[SUCCESS] All tests passed! Cache monitoring fix complete.")
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed, need further fixes.")

    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)