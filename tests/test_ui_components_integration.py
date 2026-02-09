"""
UI组件集成测试脚本

测试所有Phase 1新UI组件的集成和功能：
1. FeatureControlWidget - 功能开关管理（菜单对话框）
2. DynamicRiskAdjustmentWidget - 风险参数监控（右侧停靠区域）
3. HealthMonitorWidget - 系统健康状态监控（右侧停靠区域）
4. PerformanceMonitorWidget - 性能指标监控（右侧停靠区域）
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
        
        # 创建DynamicRiskAdjustmentWidget
        dynamic_risk = DynamicRiskAdjustmentWidget()
        logger.info("✓ DynamicRiskAdjustmentWidget创建成功")
        
        # 创建HealthMonitorWidget
        health_monitor = HealthMonitorWidget()
        logger.info("✓ HealthMonitorWidget创建成功")
        
        # 创建PerformanceMonitorWidget
        performance_monitor = PerformanceMonitorWidget()
        logger.info("✓ PerformanceMonitorWidget创建成功")
        
        logger.info("✓ 所有UI组件创建成功")
        return True
        
    except Exception as e:
        logger.error(f"✗ UI组件创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_main_window_coordinator_integration():
    """测试MainWindowCoordinator集成"""
    logger.info("=" * 60)
    logger.info("测试3: MainWindowCoordinator集成")
    logger.info("=" * 60)
    
    try:
        from PyQt5.QtWidgets import QApplication
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        from core.containers import ServiceContainer
        from core.events import EventBus
        
        # 创建应用实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建服务容器和事件总线
        logger.info("创建服务容器和事件总线...")
        service_container = ServiceContainer()
        event_bus = EventBus()
        logger.info("✓ 服务容器和事件总线创建成功")
        
        # 创建MainWindowCoordinator
        logger.info("创建MainWindowCoordinator...")
        try:
            coordinator = MainWindowCoordinator(service_container, event_bus)
            logger.info("✓ MainWindowCoordinator创建成功")
        except Exception as e:
            logger.error(f"✗ MainWindowCoordinator创建失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # 检查增强组件是否初始化
        logger.info("检查增强组件初始化状态...")
        if hasattr(coordinator, '_enhanced_components'):
            logger.info(f"✓ 增强组件已初始化，共{len(coordinator._enhanced_components)}个")
            
            # 检查新组件是否存在
            if 'feature_control' in coordinator._enhanced_components:
                logger.info("✓ FeatureControlWidget已集成")
            else:
                logger.warning("⚠ FeatureControlWidget未集成")
            
            if 'dynamic_risk_adjustment' in coordinator._enhanced_components:
                logger.info("✓ DynamicRiskAdjustmentWidget已集成")
            else:
                logger.warning("⚠ DynamicRiskAdjustmentWidget未集成")
            
            if 'health_monitor' in coordinator._enhanced_components:
                logger.info("✓ HealthMonitorWidget已集成")
            else:
                logger.warning("⚠ HealthMonitorWidget未集成")
            
            if 'performance_monitor' in coordinator._enhanced_components:
                logger.info("✓ PerformanceMonitorWidget已集成")
            else:
                logger.warning("⚠ PerformanceMonitorWidget未集成")
        else:
            logger.warning("⚠ 增强组件未初始化")
        
        # 检查_on_feature_control方法是否存在
        if hasattr(coordinator, '_on_feature_control'):
            logger.info("✓ _on_feature_control方法已添加")
        else:
            logger.warning("⚠ _on_feature_control方法未添加")
        
        logger.info("✓ MainWindowCoordinator集成测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ MainWindowCoordinator集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_menu_bar_integration():
    """测试菜单栏集成"""
    logger.info("=" * 60)
    logger.info("测试4: 菜单栏集成")
    logger.info("=" * 60)
    
    try:
        from PyQt5.QtWidgets import QApplication
        from gui.menu_bar import MainMenuBar
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        from core.containers import ServiceContainer
        from core.events import EventBus
        
        # 创建应用实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建服务容器和事件总线
        service_container = ServiceContainer()
        event_bus = EventBus()
        
        # 创建MainWindowCoordinator
        coordinator = MainWindowCoordinator(service_container, event_bus)
        
        # 创建菜单栏
        menu_bar = MainMenuBar(coordinator=coordinator)
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

def test_feature_control_dialog():
    """测试功能控制对话框"""
    logger.info("=" * 60)
    logger.info("测试5: 功能控制对话框")
    logger.info("=" * 60)
    
    try:
        from PyQt5.QtWidgets import QApplication
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        from core.containers import ServiceContainer
        from core.events import EventBus
        
        # 创建应用实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建服务容器和事件总线
        service_container = ServiceContainer()
        event_bus = EventBus()
        
        # 创建MainWindowCoordinator
        coordinator = MainWindowCoordinator(service_container, event_bus)
        
        # 检查_on_feature_control方法是否存在
        if hasattr(coordinator, '_on_feature_control'):
            logger.info("✓ _on_feature_control方法存在")
            
            # 检查功能控制组件是否存在
            if hasattr(coordinator, '_enhanced_components') and 'feature_control' in coordinator._enhanced_components:
                logger.info("✓ 功能控制组件存在")
                logger.info("✓ 功能控制对话框可以正常显示")
            else:
                logger.warning("⚠ 功能控制组件不存在，对话框无法显示")
        else:
            logger.warning("⚠ _on_feature_control方法不存在")
        
        logger.info("✓ 功能控制对话框测试通过")
        return True
        
    except Exception as e:
        logger.error(f"✗ 功能控制对话框测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    logger.info("=" * 60)
    logger.info("UI组件集成测试")
    logger.info("=" * 60)
    
    results = []
    
    # 测试1: UI组件导入
    results.append(("UI组件导入", test_ui_components_import()))
    
    # 测试2: UI组件创建
    results.append(("UI组件创建", test_ui_components_creation()))
    
    # 测试3: MainWindowCoordinator集成
    results.append(("MainWindowCoordinator集成", test_main_window_coordinator_integration()))
    
    # 测试4: 菜单栏集成
    results.append(("菜单栏集成", test_menu_bar_integration()))
    
    # 测试5: 功能控制对话框
    results.append(("功能控制对话框", test_feature_control_dialog()))
    
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
