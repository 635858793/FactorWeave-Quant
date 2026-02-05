#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能监控窗口修复验证脚本 - 简化版
只验证语法正确性
"""

import sys
import os
import py_compile

def test_syntax():
    """测试所有修复的文件语法是否正确"""
    print("=" * 60)
    print("测试: 语法正确性检查")
    print("=" * 60)
    
    files_to_test = [
        ("gui/widgets/performance/tabs/system_monitor_tab.py", "系统监控标签页"),
        ("gui/widgets/performance/tabs/strategy_performance_tab.py", "策略性能标签页"),
        ("gui/widgets/performance/tabs/algorithm_optimization_tab.py", "算法优化标签页"),
        ("gui/widgets/performance/tabs/risk_control_center_tab.py", "风险控制中心标签页"),
        ("gui/widgets/performance/tabs/trading_execution_monitor_tab.py", "交易执行监控标签页"),
        ("gui/widgets/performance/tabs/deep_monitoring_tab.py", "深度监控标签页"),
    ]
    
    success_count = 0
    fail_count = 0
    
    for file_path, description in files_to_test:
        try:
            py_compile.compile(file_path, doraise=True)
            print(f"✅ {description} - 语法正确")
            success_count += 1
        except py_compile.PyCompileError as e:
            print(f"❌ {description} - 语法错误: {e}")
            fail_count += 1
        except Exception as e:
            print(f"❌ {description} - 错误: {type(e).__name__}")
            fail_count += 1
    
    print(f"\n语法测试结果: {success_count} 成功, {fail_count} 失败")
    return fail_count == 0

def check_methods_exist():
    """检查关键方法是否存在（通过grep）"""
    print("\n" + "=" * 60)
    print("检查: 关键方法是否存在")
    print("=" * 60)
    
    methods_to_check = [
        ("gui/widgets/performance/tabs/system_monitor_tab.py", "_update_ui_in_main_thread"),
        ("gui/widgets/performance/tabs/strategy_performance_tab.py", "_update_ui_in_main_thread"),
        ("gui/widgets/performance/tabs/algorithm_optimization_tab.py", "_update_performance_ui_in_main_thread"),
        ("gui/widgets/performance/tabs/algorithm_optimization_tab.py", "_update_tuning_ui_in_main_thread"),
        ("gui/widgets/performance/tabs/algorithm_optimization_tab.py", "_update_benchmark_ui_in_main_thread"),
        ("gui/widgets/performance/tabs/risk_control_center_tab.py", "_update_risk_ui_in_main_thread"),
        ("gui/widgets/performance/tabs/risk_control_center_tab.py", "_update_enhanced_risk_ui_in_main_thread"),
        ("gui/widgets/performance/tabs/trading_execution_monitor_tab.py", "_update_execution_ui_in_main_thread"),
        ("gui/widgets/performance/tabs/deep_monitoring_tab.py", "_update_alert_display_in_main_thread"),
    ]
    
    success_count = 0
    fail_count = 0
    
    for file_path, method_name in methods_to_check:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if f"def {method_name}" in content:
                    print(f"✅ {os.path.basename(file_path)} - {method_name} 方法存在")
                    success_count += 1
                else:
                    print(f"❌ {os.path.basename(file_path)} - {method_name} 方法不存在")
                    fail_count += 1
        except Exception as e:
            print(f"❌ {os.path.basename(file_path)} - 检查失败: {e}")
            fail_count += 1
    
    print(f"\n方法检查结果: {success_count} 成功, {fail_count} 失败")
    return fail_count == 0

def check_qtimer_usage():
    """检查QTimer.singleShot的使用"""
    print("\n" + "=" * 60)
    print("检查: QTimer.singleShot使用情况")
    print("=" * 60)
    
    files_to_check = [
        ("gui/widgets/performance/tabs/system_monitor_tab.py", "系统监控标签页"),
        ("gui/widgets/performance/tabs/strategy_performance_tab.py", "策略性能标签页"),
        ("gui/widgets/performance/tabs/algorithm_optimization_tab.py", "算法优化标签页"),
        ("gui/widgets/performance/tabs/risk_control_center_tab.py", "风险控制中心标签页"),
        ("gui/widgets/performance/tabs/trading_execution_monitor_tab.py", "交易执行监控标签页"),
        ("gui/widgets/performance/tabs/deep_monitoring_tab.py", "深度监控标签页"),
    ]
    
    success_count = 0
    fail_count = 0
    
    for file_path, description in files_to_check:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if "QTimer.singleShot(0," in content:
                    count = content.count("QTimer.singleShot(0,")
                    print(f"✅ {description} - 使用了 {count} 次 QTimer.singleShot")
                    success_count += 1
                else:
                    print(f"❌ {description} - 未使用 QTimer.singleShot")
                    fail_count += 1
        except Exception as e:
            print(f"❌ {description} - 检查失败: {e}")
            fail_count += 1
    
    print(f"\nQTimer使用检查结果: {success_count} 成功, {fail_count} 失败")
    return fail_count == 0

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("性能监控窗口修复验证测试")
    print("=" * 60)
    
    all_passed = True
    
    # 运行所有测试
    all_passed &= test_syntax()
    all_passed &= check_methods_exist()
    all_passed &= check_qtimer_usage()
    
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
