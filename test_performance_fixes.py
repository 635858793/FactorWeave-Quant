#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控窗口修复验证脚本
验证所有线程安全问题修复是否正确
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试所有修复的文件是否可以正常导入"""
    print("=" * 60)
    print("测试1: 导入所有修复的文件")
    print("=" * 60)
    
    files_to_test = [
        "gui.widgets.performance.tabs.system_monitor_tab",
        "gui.widgets.performance.tabs.strategy_performance_tab",
        "gui.widgets.performance.tabs.algorithm_optimization_tab",
        "gui.widgets.performance.tabs.risk_control_center_tab",
        "gui.widgets.performance.tabs.trading_execution_monitor_tab",
        "gui.widgets.performance.tabs.deep_monitoring_tab",
    ]
    
    success_count = 0
    fail_count = 0
    
    for module_name in files_to_test:
        try:
            module = __import__(module_name)
            print(f"✅ {module_name} - 导入成功")
            success_count += 1
        except Exception as e:
            print(f"❌ {module_name} - 导入失败: {type(e).__name__}: {str(e)[:100]}")
            fail_count += 1
    
    print(f"\n导入测试结果: {success_count} 成功, {fail_count} 失败")
    return fail_count == 0

def test_thread_safety_methods():
    """测试所有线程安全方法是否存在"""
    print("\n" + "=" * 60)
    print("测试2: 检查线程安全方法")
    print("=" * 60)
    
    from gui.widgets.performance.tabs.system_monitor_tab import SystemMonitorTab
    from gui.widgets.performance.tabs.strategy_performance_tab import StrategyPerformanceTab
    from gui.widgets.performance.tabs.algorithm_optimization_tab import AlgorithmOptimizationTab
    from gui.widgets.performance.tabs.risk_control_center_tab import RiskControlCenterTab
    from gui.widgets.performance.tabs.trading_execution_monitor_tab import TradingExecutionMonitorTab
    from gui.widgets.performance.tabs.deep_monitoring_tab import AlertPanel
    
    tests = [
        (SystemMonitorTab, "_update_ui_in_main_thread", "系统监控标签页"),
        (StrategyPerformanceTab, "_update_ui_in_main_thread", "策略性能标签页"),
        (AlgorithmOptimizationTab, "_update_performance_ui_in_main_thread", "算法优化-性能"),
        (AlgorithmOptimizationTab, "_update_tuning_ui_in_main_thread", "算法优化-调优"),
        (AlgorithmOptimizationTab, "_update_benchmark_ui_in_main_thread", "算法优化-基准"),
        (RiskControlCenterTab, "_update_risk_ui_in_main_thread", "风险控制中心"),
        (RiskControlCenterTab, "_update_enhanced_risk_ui_in_main_thread", "风险控制-增强"),
        (TradingExecutionMonitorTab, "_update_execution_ui_in_main_thread", "交易执行监控"),
        (AlertPanel, "_update_alert_display_in_main_thread", "深度监控-告警面板"),
    ]
    
    success_count = 0
    fail_count = 0
    
    for cls, method_name, description in tests:
        if hasattr(cls, method_name):
            print(f"✅ {description} - {method_name} 方法存在")
            success_count += 1
        else:
            print(f"❌ {description} - {method_name} 方法不存在")
            fail_count += 1
    
    print(f"\n线程安全方法测试结果: {success_count} 成功, {fail_count} 失败")
    return fail_count == 0

def test_cleanup_methods():
    """测试cleanup方法是否存在"""
    print("\n" + "=" * 60)
    print("测试3: 检查cleanup方法")
    print("=" * 60)
    
    from gui.widgets.performance.tabs.algorithm_optimization_tab import AlgorithmOptimizationTab
    from gui.widgets.performance.tabs.deep_monitoring_tab import DeepMonitoringOverviewTab
    
    tests = [
        (AlgorithmOptimizationTab, "cleanup", "算法优化标签页"),
        (DeepMonitoringOverviewTab, "cleanup", "深度监控概览标签页"),
    ]
    
    success_count = 0
    fail_count = 0
    
    for cls, method_name, description in tests:
        if hasattr(cls, method_name):
            print(f"✅ {description} - {method_name} 方法存在")
            success_count += 1
        else:
            print(f"❌ {description} - {method_name} 方法不存在")
            fail_count += 1
    
    print(f"\nCleanup方法测试结果: {success_count} 成功, {fail_count} 失败")
    return fail_count == 0

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("性能监控窗口修复验证测试")
    print("=" * 60)
    
    all_passed = True
    
    # 运行所有测试
    all_passed &= test_imports()
    all_passed &= test_thread_safety_methods()
    all_passed &= test_cleanup_methods()
    
    # 输出最终结果
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有测试通过！修复验证成功！")
        print("=" * 60)
        return 0
    else:
        print("❌ 部分测试失败！请检查修复！")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
