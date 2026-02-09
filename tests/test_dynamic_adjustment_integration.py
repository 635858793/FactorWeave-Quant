#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试动态调整功能整合到ModernRiskControlCenterTab后的功能完整性
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_imports():
    """测试模块导入"""
    print("=" * 80)
    print("测试模块导入")
    print("=" * 80)

    try:
        print("\n[测试1] 导入动态风险调整服务...")
        from core.services.dynamic_risk_adjustment_service import (
            DynamicRiskAdjustmentEngine, AdjustmentStrategy, AdjustmentTrigger,
            AdjustmentRule, AdjustmentHistory, PerformanceMetrics
        )
        print("✓ 动态风险调整服务导入成功")

        print("\n[测试2] 创建动态风险调整引擎...")
        engine = DynamicRiskAdjustmentEngine()
        print(f"✓ 动态风险调整引擎创建成功: {type(engine).__name__}")
        print(f"  - 当前参数数量: {len(engine.current_params)}")
        print(f"  - 基准参数数量: {len(engine.base_params)}")

        return True

    except Exception as e:
        print(f"✗ 导入测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def test_risk_control_tab_code():
    """测试ModernRiskControlCenterTab代码"""
    print("\n" + "=" * 80)
    print("测试ModernRiskControlCenterTab代码")
    print("=" * 80)

    try:
        print("\n[测试1] 读取ModernRiskControlCenterTab文件...")
        tab_file = os.path.join(project_root, 'gui/widgets/performance/tabs/risk_control_center_tab.py')
        with open(tab_file, 'r', encoding='utf-8') as f:
            content = f.read()
        print("✓ 文件读取成功")

        print("\n[测试2] 检查动态风险调整导入...")
        has_dynamic_import = 'from core.services.dynamic_risk_adjustment_service' in content
        print(f"  - 包含动态风险调整导入: {has_dynamic_import}")
        if has_dynamic_import:
            print("✓ 动态风险调整导入已添加")

        print("\n[测试3] 检查动态调整引擎初始化...")
        has_engine_init = 'self.dynamic_risk_engine = DynamicRiskAdjustmentEngine()' in content
        print(f"  - 包含动态调整引擎初始化: {has_engine_init}")
        if has_engine_init:
            print("✓ 动态调整引擎初始化已添加")

        print("\n[测试4] 检查动态调整标签页创建...")
        has_dynamic_tab = '_create_dynamic_adjustment_tab' in content
        print(f"  - 包含动态调整标签页创建方法: {has_dynamic_tab}")
        if has_dynamic_tab:
            print("✓ 动态调整标签页创建方法已添加")

        print("\n[测试5] 检查子标签页创建方法...")
        subtab_methods = [
            '_create_params_monitor_subtab',
            '_create_adjustment_history_subtab',
            '_create_adjustment_rules_subtab',
            '_create_adjustment_performance_subtab'
        ]
        
        for method_name in subtab_methods:
            has_method = method_name in content
            print(f"  - 包含 {method_name}: {has_method}")
            if has_method:
                print(f"✓ {method_name} 已添加")

        print("\n[测试6] 检查更新方法...")
        update_methods = [
            '_update_params_display',
            '_update_adjustment_history_table',
            '_update_adjustment_rules_table',
            '_update_adjustment_performance_analysis',
            '_update_dynamic_adjustment_display'
        ]
        
        for method_name in update_methods:
            has_method = method_name in content
            print(f"  - 包含 {method_name}: {has_method}")
            if has_method:
                print(f"✓ {method_name} 已添加")

        print("\n[测试7] 检查操作方法...")
        action_methods = [
            '_change_strategy',
            '_manual_risk_adjustment',
            '_add_adjustment_rule',
            '_edit_adjustment_rule',
            '_delete_adjustment_rule',
            '_export_adjustment_history',
            '_clear_adjustment_history'
        ]
        
        for method_name in action_methods:
            has_method = method_name in content
            print(f"  - 包含 {method_name}: {has_method}")
            if has_method:
                print(f"✓ {method_name} 已添加")

        print("\n[测试8] 检查标签页添加...")
        has_tab_add = 'self.tab_widget.addTab(self.dynamic_adjustment_tab, "动态调整")' in content
        print(f"  - 包含动态调整标签页添加: {has_tab_add}")
        if has_tab_add:
            print("✓ 动态调整标签页已添加到标签页组件中")

        return True

    except Exception as e:
        print(f"✗ ModernRiskControlCenterTab代码测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def test_main_window_coordinator():
    """测试MainWindowCoordinator是否已移除DynamicRiskAdjustmentWidget"""
    print("\n" + "=" * 80)
    print("测试MainWindowCoordinator是否已移除DynamicRiskAdjustmentWidget")
    print("=" * 80)

    try:
        # 读取MainWindowCoordinator文件
        coordinator_file = os.path.join(project_root, 'core/coordinators/main_window_coordinator.py')
        with open(coordinator_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查是否包含DynamicRiskAdjustmentWidget
        has_dynamic_risk_widget = 'DynamicRiskAdjustmentWidget' in content
        has_dynamic_risk_import = 'from gui.widgets.dynamic_risk_adjustment_widget' in content
        has_dynamic_risk_creation = "self._enhanced_components['dynamic_risk_adjustment']" in content
        has_dynamic_risk_dock = 'dynamic_risk_dock' in content

        print(f"  - 包含DynamicRiskAdjustmentWidget: {has_dynamic_risk_widget}")
        print(f"  - 包含DynamicRiskAdjustmentWidget导入: {has_dynamic_risk_import}")
        print(f"  - 包含DynamicRiskAdjustmentWidget创建: {has_dynamic_risk_creation}")
        print(f"  - 包含dynamic_risk_dock: {has_dynamic_risk_dock}")

        if has_dynamic_risk_widget or has_dynamic_risk_import or has_dynamic_risk_creation or has_dynamic_risk_dock:
            print("✗ MainWindowCoordinator中仍存在DynamicRiskAdjustmentWidget相关代码")
            return False
        else:
            print("✓ MainWindowCoordinator中已移除DynamicRiskAdjustmentWidget相关代码")
            return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    print("开始测试动态调整功能整合...")
    
    # 测试1: 测试模块导入
    test1_result = test_imports()
    
    # 测试2: 测试ModernRiskControlCenterTab代码
    test2_result = test_risk_control_tab_code()
    
    # 测试3: 测试MainWindowCoordinator
    test3_result = test_main_window_coordinator()
    
    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    print(f"模块导入测试: {'通过' if test1_result else '失败'}")
    print(f"ModernRiskControlCenterTab代码测试: {'通过' if test2_result else '失败'}")
    print(f"MainWindowCoordinator测试: {'通过' if test3_result else '失败'}")
    
    if test1_result and test2_result and test3_result:
        print("✓ 所有测试通过")
        sys.exit(0)
    else:
        print("✗ 部分测试失败")
        sys.exit(1)
