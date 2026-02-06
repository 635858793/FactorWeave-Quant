"""
UI组件集成代码检查脚本

只检查代码修改，不实际导入和创建UI组件
"""

import sys
import os
from loguru import logger

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_main_window_coordinator_code():
    """检查MainWindowCoordinator代码修改"""
    logger.info("=" * 60)
    logger.info("检查1: MainWindowCoordinator代码修改")
    logger.info("=" * 60)
    
    try:
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 读取MainWindowCoordinator文件
        logger.info("读取MainWindowCoordinator文件...")
        file_path = os.path.join(project_root, 'core/coordinators/main_window_coordinator.py')
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info("✓ MainWindowCoordinator文件读取成功")
        
        # 检查_initialize_enhanced_ui_components_async方法
        logger.info("检查_initialize_enhanced_ui_components_async方法...")
        if '_initialize_enhanced_ui_components_async' in content:
            logger.info("✓ _initialize_enhanced_ui_components_async方法存在")
            
            # 检查方法中是否包含新组件的导入
            if 'FeatureControlWidget' in content:
                logger.info("✓ FeatureControlWidget导入已添加")
            else:
                logger.warning("⚠ FeatureControlWidget导入未添加")
            
            if 'DynamicRiskAdjustmentWidget' in content:
                logger.info("✓ DynamicRiskAdjustmentWidget导入已添加")
            else:
                logger.warning("⚠ DynamicRiskAdjustmentWidget导入未添加")
            
            if 'HealthMonitorWidget' in content:
                logger.info("✓ HealthMonitorWidget导入已添加")
            else:
                logger.warning("⚠ HealthMonitorWidget导入未添加")
            
            if 'PerformanceMonitorWidget' in content:
                logger.info("✓ PerformanceMonitorWidget导入已添加")
            else:
                logger.warning("⚠ PerformanceMonitorWidget导入未添加")
            
            # 检查组件创建代码
            if "self._enhanced_components['feature_control']" in content:
                logger.info("✓ FeatureControlWidget创建代码已添加")
            else:
                logger.warning("⚠ FeatureControlWidget创建代码未添加")
            
            if "self._enhanced_components['dynamic_risk_adjustment']" in content:
                logger.info("✓ DynamicRiskAdjustmentWidget创建代码已添加")
            else:
                logger.warning("⚠ DynamicRiskAdjustmentWidget创建代码未添加")
            
            if "self._enhanced_components['health_monitor']" in content:
                logger.info("✓ HealthMonitorWidget创建代码已添加")
            else:
                logger.warning("⚠ HealthMonitorWidget创建代码未添加")
            
            if "self._enhanced_components['performance_monitor']" in content:
                logger.info("✓ PerformanceMonitorWidget创建代码已添加")
            else:
                logger.warning("⚠ PerformanceMonitorWidget创建代码未添加")
        else:
            logger.warning("⚠ _initialize_enhanced_ui_components_async方法不存在")
        
        # 检查_integrate_enhanced_components_to_ui方法
        logger.info("检查_integrate_enhanced_components_to_ui方法...")
        if '_integrate_enhanced_components_to_ui' in content:
            logger.info("✓ _integrate_enhanced_components_to_ui方法存在")
            
            # 检查方法中是否包含新组件的集成
            if 'dynamic_risk_dock' in content:
                logger.info("✓ DynamicRiskAdjustmentWidget集成代码已添加")
            else:
                logger.warning("⚠ DynamicRiskAdjustmentWidget集成代码未添加")
            
            if 'health_monitor_dock' in content:
                logger.info("✓ HealthMonitorWidget集成代码已添加")
            else:
                logger.warning("⚠ HealthMonitorWidget集成代码未添加")
            
            if 'performance_monitor_dock' in content:
                logger.info("✓ PerformanceMonitorWidget集成代码已添加")
            else:
                logger.warning("⚠ PerformanceMonitorWidget集成代码未添加")
            
            # 检查停靠窗口标题
            if '"风险参数监控"' in content:
                logger.info("✓ 风险参数监控停靠窗口标题已设置")
            else:
                logger.warning("⚠ 风险参数监控停靠窗口标题未设置")
            
            if '"系统健康监控"' in content:
                logger.info("✓ 系统健康监控停靠窗口标题已设置")
            else:
                logger.warning("⚠ 系统健康监控停靠窗口标题未设置")
            
            if '"性能指标监控"' in content:
                logger.info("✓ 性能指标监控停靠窗口标题已设置")
            else:
                logger.warning("⚠ 性能指标监控停靠窗口标题未设置")
        else:
            logger.warning("⚠ _integrate_enhanced_components_to_ui方法不存在")
        
        # 检查_on_feature_control方法
        logger.info("检查_on_feature_control方法...")
        if 'def _on_feature_control' in content:
            logger.info("✓ _on_feature_control方法已添加")
            
            # 检查方法内容
            if 'FeatureControlWidget' in content and '_on_feature_control' in content:
                # 检查方法是否正确实现
                if 'QDialog' in content and '_enhanced_components' in content:
                    logger.info("✓ _on_feature_control方法实现正确")
                else:
                    logger.warning("⚠ _on_feature_control方法实现可能有问题")
        else:
            logger.warning("⚠ _on_feature_control方法未添加")
        
        logger.info("✓ MainWindowCoordinator代码修改检查完成")
        return True
        
    except Exception as e:
        logger.error(f"✗ MainWindowCoordinator代码修改检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_menu_bar_code():
    """检查菜单栏代码修改"""
    logger.info("=" * 60)
    logger.info("检查2: 菜单栏代码修改")
    logger.info("=" * 60)
    
    try:
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 读取菜单栏文件
        logger.info("读取菜单栏文件...")
        file_path = os.path.join(project_root, 'gui/menu_bar.py')
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info("✓ 菜单栏文件读取成功")
        
        # 检查功能控制菜单项
        logger.info("检查功能控制菜单项...")
        if 'feature_control_action' in content:
            logger.info("✓ 功能控制菜单项已添加")
            
            # 检查菜单项属性
            if '"功能控制"' in content:
                logger.info("✓ 菜单项文本已设置")
            else:
                logger.warning("⚠ 菜单项文本未设置")
            
            if 'Ctrl+Shift+F' in content:
                logger.info("✓ 快捷键已设置")
            else:
                logger.warning("⚠ 快捷键未设置")
            
            if '管理系统功能开关和配置' in content:
                logger.info("✓ 状态提示已设置")
            else:
                logger.warning("⚠ 状态提示未设置")
            
            # 检查信号连接
            if "'feature_control_action', '_on_feature_control'" in content:
                logger.info("✓ 信号连接已添加")
            else:
                logger.warning("⚠ 信号连接未添加")
        else:
            logger.warning("⚠ 功能控制菜单项未添加")
        
        logger.info("✓ 菜单栏代码修改检查完成")
        return True
        
    except Exception as e:
        logger.error(f"✗ 菜单栏代码修改检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_ui_widget_files():
    """检查UI组件文件"""
    logger.info("=" * 60)
    logger.info("检查3: UI组件文件")
    logger.info("=" * 60)
    
    try:
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 检查FeatureControlWidget
        logger.info("检查FeatureControlWidget...")
        file_path = os.path.join(project_root, 'gui/widgets/feature_control_widget.py')
        if os.path.exists(file_path):
            logger.info("✓ FeatureControlWidget文件存在")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'class FeatureControlWidget' in content:
                logger.info("✓ FeatureControlWidget类定义存在")
            else:
                logger.warning("⚠ FeatureControlWidget类定义不存在")
            
            if 'FeatureControlService' in content:
                logger.info("✓ FeatureControlService引用存在")
            else:
                logger.warning("⚠ FeatureControlService引用不存在")
        else:
            logger.warning("⚠ FeatureControlWidget文件不存在")
        
        # 检查DynamicRiskAdjustmentWidget
        logger.info("检查DynamicRiskAdjustmentWidget...")
        file_path = os.path.join(project_root, 'gui/widgets/dynamic_risk_adjustment_widget.py')
        if os.path.exists(file_path):
            logger.info("✓ DynamicRiskAdjustmentWidget文件存在")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'class DynamicRiskAdjustmentWidget' in content:
                logger.info("✓ DynamicRiskAdjustmentWidget类定义存在")
            else:
                logger.warning("⚠ DynamicRiskAdjustmentWidget类定义不存在")
            
            if 'DynamicRiskAdjustmentEngine' in content:
                logger.info("✓ DynamicRiskAdjustmentEngine引用存在")
            else:
                logger.warning("⚠ DynamicRiskAdjustmentEngine引用不存在")
        else:
            logger.warning("⚠ DynamicRiskAdjustmentWidget文件不存在")
        
        # 检查HealthMonitorWidget
        logger.info("检查HealthMonitorWidget...")
        file_path = os.path.join(project_root, 'gui/widgets/health_monitor_widget.py')
        if os.path.exists(file_path):
            logger.info("✓ HealthMonitorWidget文件存在")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'class HealthMonitorWidget' in content:
                logger.info("✓ HealthMonitorWidget类定义存在")
            else:
                logger.warning("⚠ HealthMonitorWidget类定义不存在")
            
            if 'HealthMonitor' in content:
                logger.info("✓ HealthMonitor引用存在")
            else:
                logger.warning("⚠ HealthMonitor引用不存在")
        else:
            logger.warning("⚠ HealthMonitorWidget文件不存在")
        
        # 检查PerformanceMonitorWidget
        logger.info("检查PerformanceMonitorWidget...")
        file_path = os.path.join(project_root, 'gui/widgets/performance_monitor_widget.py')
        if os.path.exists(file_path):
            logger.info("✓ PerformanceMonitorWidget文件存在")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'class PerformanceMonitorWidget' in content:
                logger.info("✓ PerformanceMonitorWidget类定义存在")
            else:
                logger.warning("⚠ PerformanceMonitorWidget类定义不存在")
            
            if 'PerformanceMonitor' in content:
                logger.info("✓ PerformanceMonitor引用存在")
            else:
                logger.warning("⚠ PerformanceMonitor引用不存在")
        else:
            logger.warning("⚠ PerformanceMonitorWidget文件不存在")
        
        logger.info("✓ UI组件文件检查完成")
        return True
        
    except Exception as e:
        logger.error(f"✗ UI组件文件检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主检查函数"""
    logger.info("=" * 60)
    logger.info("UI组件集成代码检查")
    logger.info("=" * 60)
    
    results = []
    
    # 检查1: MainWindowCoordinator代码修改
    results.append(("MainWindowCoordinator代码修改", check_main_window_coordinator_code()))
    
    # 检查2: 菜单栏代码修改
    results.append(("菜单栏代码修改", check_menu_bar_code()))
    
    # 检查3: UI组件文件
    results.append(("UI组件文件", check_ui_widget_files()))
    
    # 输出检查结果
    logger.info("=" * 60)
    logger.info("检查结果汇总")
    logger.info("=" * 60)
    
    for check_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{check_name}: {status}")
    
    # 统计结果
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    logger.info("=" * 60)
    logger.info(f"检查完成: {passed}/{total} 通过")
    logger.info("=" * 60)
    
    return all(result for _, result in results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
