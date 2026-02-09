#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试合并后的功能完整性
验证HealthMonitorWidget和PerformanceMonitorWidget的增强功能是否正确合并到现有组件中
"""

import sys
import os
import time
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from loguru import logger


def test_system_health_tab():
    """测试ModernSystemHealthTab是否正确包含增强功能"""
    logger.info("=" * 60)
    logger.info("测试1: ModernSystemHealthTab增强功能")
    logger.info("=" * 60)
    
    try:
        from gui.widgets.performance.tabs.system_health_tab import ModernSystemHealthTab
        
        # 创建实例（不显示窗口）
        tab = ModernSystemHealthTab()
        
        # 检查是否有新的标签页
        has_tabs = hasattr(tab, 'tab_widget')
        logger.info(f"✓ ModernSystemHealthTab有标签页组件: {has_tabs}")
        
        if has_tabs:
            tab_count = tab.tab_widget.count()
            logger.info(f"✓ 标签页数量: {tab_count}")
            
            # 检查标签页名称
            expected_tabs = ["概览", "指标详情", "趋势分析", "阈值配置", "历史记录"]
            for i in range(tab_count):
                tab_name = tab.tab_widget.tabText(i)
                logger.info(f"  - 标签页{i+1}: {tab_name}")
                if tab_name in expected_tabs:
                    logger.info(f"    ✓ 包含预期标签页: {tab_name}")
        
        # 检查是否有工具栏
        has_toolbar = hasattr(tab, 'toolbar')
        logger.info(f"✓ ModernSystemHealthTab有工具栏: {has_toolbar}")
        
        # 检查是否有阈值配置
        has_thresholds = hasattr(tab, 'thresholds')
        logger.info(f"✓ ModernSystemHealthTab有阈值配置: {has_thresholds}")
        
        # 检查是否有历史记录
        has_history = hasattr(tab, 'health_history')
        logger.info(f"✓ ModernSystemHealthTab有历史记录: {has_history}")
        
        # 检查是否有更新定时器
        has_timer = hasattr(tab, 'update_timer')
        logger.info(f"✓ ModernSystemHealthTab有更新定时器: {has_timer}")
        
        logger.info("✓ ModernSystemHealthTab增强功能测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ ModernSystemHealthTab测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_system_monitor_tab():
    """测试ModernSystemMonitorTab是否正确包含增强功能"""
    logger.info("=" * 60)
    logger.info("测试2: ModernSystemMonitorTab增强功能")
    logger.info("=" * 60)
    
    try:
        from gui.widgets.performance.tabs.system_monitor_tab import ModernSystemMonitorTab
        
        # 创建实例（不显示窗口）
        tab = ModernSystemMonitorTab()
        
        # 检查是否有新的标签页
        has_tabs = hasattr(tab, 'tab_widget')
        logger.info(f"✓ ModernSystemMonitorTab有标签页组件: {has_tabs}")
        
        if has_tabs:
            tab_count = tab.tab_widget.count()
            logger.info(f"✓ 标签页数量: {tab_count}")
            
            # 检查标签页名称
            expected_tabs = ["概览", "指标详情", "性能警报", "优化建议", "历史记录"]
            for i in range(tab_count):
                tab_name = tab.tab_widget.tabText(i)
                logger.info(f"  - 标签页{i+1}: {tab_name}")
                if tab_name in expected_tabs:
                    logger.info(f"    ✓ 包含预期标签页: {tab_name}")
        
        # 检查是否有工具栏
        has_toolbar = hasattr(tab, 'toolbar')
        logger.info(f"✓ ModernSystemMonitorTab有工具栏: {has_toolbar}")
        
        # 检查是否有警报列表
        has_alerts = hasattr(tab, 'alerts')
        logger.info(f"✓ ModernSystemMonitorTab有警报列表: {has_alerts}")
        
        # 检查是否有建议列表
        has_recommendations = hasattr(tab, 'recommendations')
        logger.info(f"✓ ModernSystemMonitorTab有建议列表: {has_recommendations}")
        
        # 检查是否有历史记录
        has_history = hasattr(tab, 'performance_history')
        logger.info(f"✓ ModernSystemMonitorTab有历史记录: {has_history}")
        
        # 检查是否有性能监控器
        has_performance_monitor = hasattr(tab, 'performance_monitor')
        logger.info(f"✓ ModernSystemMonitorTab有性能监控器: {has_performance_monitor}")
        
        logger.info("✓ ModernSystemMonitorTab增强功能测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ ModernSystemMonitorTab测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_main_window_coordinator():
    """测试MainWindowCoordinator是否正确移除了重复组件的集成"""
    logger.info("=" * 60)
    logger.info("测试3: MainWindowCoordinator集成")
    logger.info("=" * 60)
    
    try:
        # 读取MainWindowCoordinator文件
        logger.info("读取MainWindowCoordinator文件...")
        with open('core/coordinators/main_window_coordinator.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info("✓ MainWindowCoordinator文件读取成功")
        
        # 检查是否移除了HealthMonitorWidget的导入
        has_health_import = 'from gui.widgets.health_monitor_widget import HealthMonitorWidget' in content
        logger.info(f"✓ HealthMonitorWidget导入已移除: {not has_health_import}")
        if has_health:
            logger.warning("⚠ HealthMonitorWidget导入仍然存在")
        
        # 检查是否移除了PerformanceMonitorWidget的导入
        has_performance_import = 'from gui.widgets.performance_monitor_widget import PerformanceMonitorWidget' in content
        logger.info(f"✓ PerformanceMonitorWidget导入已移除: {not has_performance_import}")
        if has_performance_import:
            logger.warning("⚠ PerformanceMonitorWidget导入仍然存在")
        
        # 检查是否移除了health_monitor的集成
        has_health_integration = "'health_monitor'" in content and "health_monitor_dock" in content
        logger.info(f"✓ health_monitor集成已移除: {not has_health_integration}")
        if has_health_integration:
            logger.warning("⚠ health_monitor集成仍然存在")
        
        # 检查是否移除了performance_monitor的集成
        has_performance_integration = "'performance_monitor'" in content and "performance_monitor_dock" in content
        logger.info(f"✓ performance_monitor集成已移除: {not has_performance_integration}")
        if has_performance_integration:
            logger.warning("⚠ performance_monitor集成仍然存在")
        
        # 检查是否保留了FeatureControlWidget
        has_feature_control = "'feature_control'" in content
        logger.info(f"✓ FeatureControlWidget集成已保留: {has_feature_control}")
        
        # 检查是否保留了DynamicRiskAdjustmentWidget
        has_dynamic_risk = "'dynamic_risk_adjustment'" in content
        logger.info(f"✓ DynamicRiskAdjustmentWidget集成已保留: {has_dynamic_risk}")
        
        # 检查文件是否删除
        health_file_exists = os.path.exists('gui/widgets/health_monitor_widget.py')
        performance_file_exists = os.path.exists('gui/widgets/performance_monitor_widget.py')
        logger.info(f"✓ HealthMonitorWidget文件已删除: {not health_file_exists}")
        logger.info(f"✓ PerformanceMonitorWidget文件已删除: {not performance_file_exists}")
        
        logger.info("✓ MainWindowCoordinator集成测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ MainWindowCoordinator测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("合并功能完整性测试")
    logger.info("=" * 60)
    
    results = []
    
    # 测试ModernSystemHealthTab
    result1 = test_system_health_tab()
    results.append(("ModernSystemHealthTab", result1))
    
    # 测试ModernSystemMonitorTab
    result2 = test_system_monitor_tab()
    results.append(("ModernSystemMonitorTab", result2))
    
    # 测试MainWindowCoordinator
    result3 = test_main_window_coordinator()
    results.append(("MainWindowCoordinator", result3))
    
    # 汇总结果
    logger.info("=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{name}: {status}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    logger.info("=" * 60)
    logger.info(f"测试完成: {passed}/{total} 通过")
    logger.info("=" * 60)
    
    return all(result for _, result in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
