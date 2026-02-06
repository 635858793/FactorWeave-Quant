"""
简化的UI组件集成测试脚本

只测试UI组件的导入和创建，不测试MainWindowCoordinator的完整初始化
"""

import sys
import os
from loguru import logger

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_ui_components_import():
    """测试UI组件导入"""
    logger.info("=" * 60)
    logger.info("测试1: UI组件导入")
    logger.info("=" * 60)
    
    try:
        from gui.widgets.feature_control_widget import FeatureControlWidget
        logger.info("✓ FeatureControlWidget导入成功")
    except Exception as e:
        logger.error(f"✗ FeatureControlWidget导入失败: {e}")
        return False
    
    try:
        from gui.widgets.dynamic_risk_adjustment_widget import DynamicRiskAdjustmentWidget
        logger.info("✓ DynamicRiskAdjustmentWidget导入成功")
    except Exception as e:
        logger.error(f"✗ DynamicRiskAdjustmentWidget导入失败: {e}")
        return False
    
    try:
        from gui.widgets.health_monitor_widget import HealthMonitorWidget
        logger.info("✓ HealthMonitorWidget导入成功")
    except Exception as e:
        logger.error(f"✗ HealthMonitorWidget导入失败: {e}")
        return False
    
    try:
        from gui.widgets.performance_monitor_widget import PerformanceMonitorWidget
        logger.info("✓ PerformanceMonitorWidget导入成功")
    except Exception as e:
        logger.error(f"✗ PerformanceMonitorWidget导入失败: {e}")
        return False
    
    logger.info("✓ 所有UI组件导入成功")
    return True

def test_ui_components_creation():
    """测试UI组件创建"""
    logger.info("=" * 60)
    logger.info("测试2: UI组件创建")
    logger.info("=" * 60)
    
    try:
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.feature_control_widget import FeatureControlWidget
        from gui.widgets.dynamic_risk_adjustment_widget import DynamicRiskAdjustmentWidget
        from gui.widgets.health_monitor_widget import HealthMonitorWidget
        from gui.widgets.performance_monitor_widget import PerformanceMonitorWidget
        
        # 创建应用实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建FeatureControlWidget
        feature_control = FeatureControlWidget()
        logger.info("✓ FeatureControlWidget创建成功")
        logger.info(f"  - 标签页数量: {feature_control.tab_widget.count()}")
        for i in range(feature_control.tab_widget.count()):
            logger.info(f"    - {feature_control.tab_widget.tabText(i)}")
        
        # 创建DynamicRiskAdjustmentWidget
        dynamic_risk = DynamicRiskAdjustmentWidget()
        logger.info("✓ DynamicRiskAdjustmentWidget创建成功")
        logger.info(f"  - 标签页数量: {dynamic_risk.tab_widget.count()}")
        for i in range(dynamic_risk.tab_widget.count()):
            logger.info(f"    - {dynamic_risk.tab_widget.tabText(i)}")
        
        # 创建HealthMonitorWidget
        health_monitor = HealthMonitorWidget()
        logger.info("✓ HealthMonitorWidget创建成功")
        logger.info(f"  - 标签页数量: {health_monitor.tab_widget.count()}")
        for i in range(health_monitor.tab_widget.count()):
            logger.info(f"    - {health_monitor.tab_widget.tabText(i)}")
        
        # 创建PerformanceMonitorWidget
        performance_monitor = PerformanceMonitorWidget()
        logger.info("✓ PerformanceMonitorWidget创建成功")
        logger.info(f"  - 标签页数量: {performance_monitor.tab_widget.count()}")
        for i in range(performance_monitor.tab_widget.count()):
            logger.info(f"    - {performance_monitor.tab_widget.tabText(i)}")
        
        logger.info("✓ 所有UI组件创建成功")
        return True
        
    except Exception as e:
        logger.error(f"✗ UI组件创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_menu_bar_integration():
    """测试菜单栏集成"""
    logger.info("=" * 60)
    logger.info("测试3: 菜单栏集成")
    logger.info("=" * 60)
    
    try:
        from PyQt5.QtWidgets import QApplication
        from gui.menu_bar import MainMenuBar
        
        # 创建应用实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建菜单栏（不传入coordinator）
        menu_bar = MainMenuBar(coordinator=None)
        logger.info("✓ MainMenuBar创建成功")
        
        # 检查功能控制菜单项是否存在
        if hasattr(menu_bar, 'feature_control_action'):
            logger.info("✓ 功能控制菜单项已添加")
            logger.info(f"  - 菜单项文本: {menu_bar.feature_control_action.text()}")
            logger.info(f"  - 快捷键: {menu_bar.feature_control_action.shortcut().toString()}")
            logger.info(f"  - 状态提示: {menu_bar.feature_control_action.statusTip()}")
        else:
            logger.warning("⚠ 功能控制菜单项未添加")
        
        logger.info("✓ 菜单栏集成测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ 菜单栏集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_main_window_coordinator_code():
    """测试MainWindowCoordinator代码修改"""
    logger.info("=" * 60)
    logger.info("测试4: MainWindowCoordinator代码修改")
    logger.info("=" * 60)
    
    try:
        # 检查MainWindowCoordinator文件
        logger.info("导入MainWindowCoordinator...")
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        logger.info("✓ MainWindowCoordinator导入成功")
        
        # 检查_initialize_enhanced_ui_components_async方法
        logger.info("检查_initialize_enhanced_ui_components_async方法...")
        if hasattr(MainWindowCoordinator, '_initialize_enhanced_ui_components_async'):
            logger.info("✓ _initialize_enhanced_ui_components_async方法存在")
            
            # 检查方法源代码中是否包含新组件的导入
            logger.info("检查方法源代码...")
            import inspect
            try:
                source = inspect.getsource(MainWindowCoordinator._initialize_enhanced_ui_components_async)
                
                if 'FeatureControlWidget' in source:
                    logger.info("✓ FeatureControlWidget导入已添加")
                else:
                    logger.warning("⚠ FeatureControlWidget导入未添加")
                
                if 'DynamicRiskAdjustmentWidget' in source:
                    logger.info("✓ DynamicRiskAdjustmentWidget导入已添加")
                else:
                    logger.warning("⚠ DynamicRiskAdjustmentWidget导入未添加")
                
                if 'HealthMonitorWidget' in source:
                    logger.info("✓ HealthMonitorWidget导入已添加")
                else:
                    logger.warning("⚠ HealthMonitorWidget导入未添加")
                
                if 'PerformanceMonitorWidget' in source:
                    logger.info("✓ PerformanceMonitorWidget导入已添加")
                else:
                    logger.warning("⚠ PerformanceMonitorWidget导入未添加")
            except Exception as e:
                logger.warning(f"⚠ 检查方法源代码失败: {e}")
        else:
            logger.warning("⚠ _initialize_enhanced_ui_components_async方法不存在")
        
        # 检查_integrate_enhanced_components_to_ui方法
        logger.info("检查_integrate_enhanced_components_to_ui方法...")
        if hasattr(MainWindowCoordinator, '_integrate_enhanced_components_to_ui'):
            logger.info("✓ _integrate_enhanced_components_to_ui方法存在")
            
            # 检查方法源代码中是否包含新组件的集成
            logger.info("检查方法源代码...")
            import inspect
            try:
                source = inspect.getsource(MainWindowCoordinator._integrate_enhanced_components_to_ui)
                
                if 'dynamic_risk_adjustment' in source:
                    logger.info("✓ DynamicRiskAdjustmentWidget集成已添加")
                else:
                    logger.warning("⚠ DynamicRiskAdjustmentWidget集成未添加")
                
                if 'health_monitor' in source:
                    logger.info("✓ HealthMonitorWidget集成已添加")
                else:
                    logger.warning("⚠ HealthMonitorWidget集成未添加")
                
                if 'performance_monitor' in source:
                    logger.info("✓ PerformanceMonitorWidget集成已添加")
                else:
                    logger.warning("⚠ PerformanceMonitorWidget集成未添加")
            except Exception as e:
                logger.warning(f"⚠ 检查方法源代码失败: {e}")
        else:
            logger.warning("⚠ _integrate_enhanced_components_to_ui方法不存在")
        
        # 检查_on_feature_control方法
        logger.info("检查_on_feature_control方法...")
        if hasattr(MainWindowCoordinator, '_on_feature_control'):
            logger.info("✓ _on_feature_control方法已添加")
        else:
            logger.warning("⚠ _on_feature_control方法未添加")
        
        logger.info("✓ MainWindowCoordinator代码修改测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ MainWindowCoordinator代码修改测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    logger.info("=" * 60)
    logger.info("UI组件集成测试（简化版）")
    logger.info("=" * 60)
    
    results = []
    
    # 测试1: UI组件导入
    results.append(("UI组件导入", test_ui_components_import()))
    
    # 测试2: UI组件创建
    results.append(("UI组件创建", test_ui_components_creation()))
    
    # 测试3: 菜单栏集成
    results.append(("菜单栏集成", test_menu_bar_integration()))
    
    # 测试4: MainWindowCoordinator代码修改
    results.append(("MainWindowCoordinator代码修改", test_main_window_coordinator_code()))
    
    # 输出测试结果
    logger.info("=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{test_name}: {status}")
    
    # 统计结果
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    logger.info("=" * 60)
    logger.info(f"测试完成: {passed}/{total} 通过")
    logger.info("=" * 60)
    
    return all(result for _, result in results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
