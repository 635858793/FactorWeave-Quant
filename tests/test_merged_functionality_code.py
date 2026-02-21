#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试合并后的功能完整性（代码检查版本）
验证HealthMonitorWidget和PerformanceMonitorWidget的增强功能是否正确合并到现有组件中
"""

import sys
import os
import re

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from loguru import logger


def test_system_monitor_tab_code():
    """检查ModernSystemMonitorTab代码是否包含增强功能"""
    logger.info("=" * 60)
    logger.info("检查2: ModernSystemMonitorTab代码")
    logger.info("=" * 60)
    
    try:
        # 读取ModernSystemMonitorTab文件
        logger.info("读取ModernSystemMonitorTab文件...")
        file_path = os.path.join(project_root, 'gui/widgets/performance/tabs/system_monitor_tab.py')
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info("✓ ModernSystemMonitorTab文件读取成功")
        
        # 检查是否有新的导入
        if 'QTabWidget' in content:
            logger.info("✓ QTabWidget导入已添加")
        else:
            logger.warning("⚠ QTabWidget导入未添加")
        
        if 'QToolBar' in content:
            logger.info("✓ QToolBar导入已添加")
        else:
            logger.warning("⚠ QToolBar导入未添加")
        
        if 'PerformanceMonitor' in content:
            logger.info("✓ PerformanceMonitor导入已添加")
        else:
            logger.warning("⚠ PerformanceMonitor导入未添加")
        
        # 检查是否有新的属性
        if 'self.alerts' in content:
            logger.info("✓ alerts属性已添加")
        else:
            logger.warning("⚠ alerts属性未添加")
        
        if 'self.recommendations' in content:
            logger.info("✓ recommendations属性已添加")
        else:
            logger.warning("⚠ recommendations属性未添加")
        
        if 'self.performance_history' in content:
            logger.info("✓ performance_history属性已添加")
        else:
            logger.warning("⚠ performance_history属性未添加")
        
        # 检查是否有新的方法
        if 'def create_overview_tab' in content:
            logger.info("✓ create_overview_tab方法已添加")
        else:
            logger.warning("⚠ create_overview_tab方法未添加")
        
        if 'def create_metrics_tab' in content:
            logger.info("✓ create_metrics_tab方法已添加")
        else:
            logger.warning("⚠ create_metrics_tab方法未添加")
        
        if 'def create_alerts_tab' in content:
            logger.info("✓ create_alerts_tab方法已添加")
        else:
            logger.warning("⚠ create_alerts_tab方法未添加")
        
        if 'def create_recommendations_tab' in content:
            logger.info("✓ create_recommendations_tab方法已添加")
        else:
            logger.warning("⚠ create_recommendations_tab方法未添加")
        
        if 'def create_history_tab' in content:
            logger.info("✓ create_history_tab方法已添加")
        else:
            logger.warning("⚠ create_history_tab方法未添加")
        
        logger.info("✓ ModernSystemMonitorTab代码检查完成")
        return True
        
    except Exception as e:
        logger.error(f"✗ ModernSystemMonitorTab代码检查失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_main_window_coordinator_code():
    """检查MainWindowCoordinator代码是否正确移除了重复组件的集成"""
    logger.info("=" * 60)
    logger.info("检查3: MainWindowCoordinator代码")
    logger.info("=" * 60)
    
    try:
        # 读取MainWindowCoordinator文件
        logger.info("读取MainWindowCoordinator文件...")
        file_path = os.path.join(project_root, 'core/coordinators/main_window_coordinator.py')
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info("✓ MainWindowCoordinator文件读取成功")
        
        # 检查是否移除了HealthMonitorWidget的导入
        has_health_import = 'from gui.widgets.health_monitor_widget import HealthMonitorWidget' in content
        logger.info(f"✓ HealthMonitorWidget导入已移除: {not has_health_import}")
        if has_health_import:
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
        
        logger.info("✓ MainWindowCoordinator代码检查完成")
        return True
        
    except Exception as e:
        logger.error(f"✗ MainWindowCoordinator代码检查失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_deleted_files():
    """检查重复组件文件是否已删除"""
    logger.info("=" * 60)
    logger.info("检查4: 删除的文件")
    logger.info("=" * 60)
    
    try:
        # 检查HealthMonitorWidget文件是否删除
        health_file_path = os.path.join(project_root, 'gui/widgets/health_monitor_widget.py')
        health_file_exists = os.path.exists(health_file_path)
        logger.info(f"✓ HealthMonitorWidget文件已删除: {not health_file_exists}")
        if health_file_exists:
            logger.warning("⚠ HealthMonitorWidget文件仍然存在")
        
        # 检查PerformanceMonitorWidget文件是否删除
        performance_file_path = os.path.join(project_root, 'gui/widgets/performance_monitor_widget.py')
        performance_file_exists = os.path.exists(performance_file_path)
        logger.info(f"✓ PerformanceMonitorWidget文件已删除: {not performance_file_exists}")
        if performance_file_exists:
            logger.warning("⚠ PerformanceMonitorWidget文件仍然存在")
        
        logger.info("✓ 文件删除检查完成")
        return not health_file_exists and not performance_file_exists
        
    except Exception as e:
        logger.error(f"✗ 文件删除检查失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("合并功能完整性测试（代码检查版本）")
    logger.info("=" * 60)
    
    results = []
    
    # 检查ModernSystemMonitorTab代码
    result2 = test_system_monitor_tab_code()
    results.append(("ModernSystemMonitorTab代码", result2))
    
    # 检查MainWindowCoordinator代码
    result3 = test_main_window_coordinator_code()
    results.append(("MainWindowCoordinator代码", result3))
    
    # 检查删除的文件
    result4 = test_deleted_files()
    results.append(("删除的文件", result4))
    
    # 汇总结果
    logger.info("=" * 60)
    logger.info("检查结果汇总")
    logger.info("=" * 60)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{name}: {status}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    logger.info("=" * 60)
    logger.info(f"检查完成: {passed}/{total} 通过")
    logger.info("=" * 60)
    
    return all(result for _, result in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
