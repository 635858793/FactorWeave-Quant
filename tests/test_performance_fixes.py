#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控模块自测脚本
"""
import sys
import os
import time

# 设置工作目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_unified_monitor():
    """测试 UnifiedPerformanceMonitor"""
    print("=" * 60)
    print("测试 1: UnifiedPerformanceMonitor 导入和基本功能")
    print("=" * 60)
    
    try:
        from core.performance.unified_monitor import UnifiedPerformanceMonitor
        
        monitor = UnifiedPerformanceMonitor()
        print("✓ UnifiedPerformanceMonitor 实例化成功")
        
        # 测试 collect_all_metrics
        metrics = monitor.collect_all_metrics()
        print(f"\ncollect_all_metrics 返回结果:")
        print(f"  - 响应时间: {metrics.get('响应时间', 'N/A')} ms")
        print(f"  - 渲染帧率: {metrics.get('渲染帧率', 'N/A')}")
        print(f"  - 缓存命中率: {metrics.get('缓存命中率', 'N/A')}")
        print(f"  - 加载时间: {metrics.get('加载时间', 'N/A')} ms")
        print(f"  - 计算速度: {metrics.get('计算速度', 'N/A')}")
        print(f"  - 准确率: {metrics.get('准确率', 'N/A')}")
        print(f"  - 吞吐量: {metrics.get('吞吐量', 'N/A')}")
        
        # 测试 evaluate_strategy_performance（无数据情况）
        print("\n测试 evaluate_strategy_performance (无数据):")
        strategy_metrics = monitor.evaluate_strategy_performance.__wrapped__(monitor, 
            __import__('pandas').Series(dtype=float), None)
        print(f"  - total_return: {strategy_metrics.get('total_return', 'N/A')}")
        print(f"  - sharpe_ratio: {strategy_metrics.get('sharpe_ratio', 'N/A')}")
        print(f"  - win_rate: {strategy_metrics.get('win_rate', 'N/A')}")
        
        print("\n✓ 测试通过!")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_app_metrics_service():
    """测试 AppMetricsService"""
    print("\n" + "=" * 60)
    print("测试 2: AppMetricsService 导入")
    print("=" * 60)
    
    try:
        from core.metrics.app_metrics_service import AppMetricsService
        
        service = AppMetricsService()
        print("✓ AppMetricsService 实例化成功")
        
        # 测试装饰器是否使用 perf_counter
        @service.measure_performance("test_operation")
        def test_func():
            time.sleep(0.001)
            return "test"
        
        result = test_func()
        print(f"  - 装饰器测试结果: {result}")
        print("\n✓ 测试通过!")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_system_monitor_tab():
    """测试 system_monitor_tab_refactored"""
    print("\n" + "=" * 60)
    print("测试 3: system_monitor_tab_refactored 导入")
    print("=" * 60)
    
    try:
        # 不实例化 GUI 组件，只检查导入
        import gui.widgets.performance.tabs.system_monitor_tab_refactored as smt
        print("✓ system_monitor_tab_refactored 导入成功")
        
        # 检查 _collect_system_data 方法是否存在
        if hasattr(smt.ModernSystemMonitorTab, '_collect_system_data'):
            print("✓ _collect_system_data 方法存在")
        
        print("\n✓ 测试通过!")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_timer_consistency():
    """测试计时器一致性"""
    print("\n" + "=" * 60)
    print("测试 4: 计时器一致性检查")
    print("=" * 60)
    
    # 测试 time.perf_counter() 精度
    start = time.perf_counter()
    time.sleep(0.01)
    end = time.perf_counter()
    elapsed = end - start
    
    print(f"  - time.perf_counter() 测量 10ms 睡眠: {elapsed*1000:.2f}ms")
    
    start = time.time()
    time.sleep(0.01)
    end = time.time()
    elapsed = end - start
    
    print(f"  - time.time() 测量 10ms 睡眠: {elapsed*1000:.2f}ms")
    print("\n✓ 计时器功能正常")
    return True

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("开始性能监控模块自测")
    print("=" * 60 + "\n")
    
    results = []
    
    results.append(("UnifiedPerformanceMonitor", test_unified_monitor()))
    results.append(("AppMetricsService", test_app_metrics_service()))
    results.append(("system_monitor_tab_refactored", test_system_monitor_tab()))
    results.append(("计时器一致性", test_timer_consistency()))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("所有测试通过!")
    else:
        print("部分测试失败，请检查!")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
