#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控中心深度优化清理测试
验证深度优化tab和相关功能已被正确清理
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger


def test_import():
    """测试导入"""
    logger.info("=" * 60)
    logger.info("测试1: 验证导入")
    logger.info("=" * 60)
    
    try:
        from gui.widgets.performance import ModernUnifiedPerformanceWidget
        logger.info("✓ ModernUnifiedPerformanceWidget 导入成功")
        return True
    except Exception as e:
        logger.error(f"✗ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_deleted_files():
    """测试文件删除"""
    logger.info("\n" + "=" * 60)
    logger.info("测试2: 验证文件删除")
    logger.info("=" * 60)
    
    deleted_files = [
        "gui/widgets/performance/tabs/deep_optimization_tab.py",
        "gui/widgets/performance/tabs/deep_monitoring_tab.py",
        "gui/widgets/performance/deep_monitoring_tab.py",
        "gui/dialogs/unified_optimization_dialog.py"
    ]
    
    all_deleted = True
    for file_path in deleted_files:
        full_path = project_root / file_path
        if full_path.exists():
            logger.error(f"✗ 文件仍然存在: {file_path}")
            all_deleted = False
        else:
            logger.info(f"✓ 文件已删除: {file_path}")
    
    return all_deleted


def test_import_errors():
    """测试导入错误（应该失败）"""
    logger.info("\n" + "=" * 60)
    logger.info("测试3: 验证导入错误（应该失败）")
    logger.info("=" * 60)
    
    # 测试已删除的文件导入应该失败
    deleted_imports = [
        ("gui.widgets.performance.tabs.deep_optimization_tab", "DeepOptimizationTab"),
        ("gui.widgets.performance.tabs.deep_monitoring_tab", "DeepMonitoringTab"),
        ("gui.widgets.performance.deep_monitoring_tab", "DeepMonitoringTab"),
        ("gui.dialogs.unified_optimization_dialog", "UnifiedOptimizationDialog")
    ]
    
    all_failed = True
    for module_name, class_name in deleted_imports:
        try:
            __import__(module_name, fromlist=[class_name])
            logger.error(f"✗ 导入应该失败但成功了: {module_name}.{class_name}")
            all_failed = False
        except (ImportError, ModuleNotFoundError):
            logger.info(f"✓ 导入正确失败: {module_name}.{class_name}")
        except Exception as e:
            logger.info(f"✓ 导入正确失败: {module_name}.{class_name} ({type(e).__name__})")
    
    return all_failed


def test_menu_bar_import():
    """测试菜单栏导入"""
    logger.info("\n" + "=" * 60)
    logger.info("测试4: 验证菜单栏导入")
    logger.info("=" * 60)
    
    try:
        from gui.menu_bar import MainMenuBar
        logger.info("✓ MainMenuBar 导入成功")
        
        # 检查是否还有unified_optimization_action属性
        if hasattr(MainMenuBar, '__init__'):
            import inspect
            init_source = inspect.getsource(MainMenuBar.__init__)
            if 'unified_optimization_action' in init_source:
                logger.error("✗ MainMenuBar中仍然包含unified_optimization_action")
                return False
            else:
                logger.info("✓ MainMenuBar中已移除unified_optimization_action")
        
        # 检查是否还有_on_unified_optimization方法
        if hasattr(MainMenuBar, '_on_unified_optimization'):
            logger.error("✗ MainMenuBar中仍然包含_on_unified_optimization方法")
            return False
        else:
            logger.info("✓ MainMenuBar中已移除_on_unified_optimization方法")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 菜单栏导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_coordinator_import():
    """测试协调器导入"""
    logger.info("\n" + "=" * 60)
    logger.info("测试5: 验证协调器导入")
    logger.info("=" * 60)
    
    try:
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        logger.info("✓ MainWindowCoordinator 导入成功")
        
        # 检查是否还有_on_unified_optimization方法
        if hasattr(MainWindowCoordinator, '_on_unified_optimization'):
            logger.error("✗ MainWindowCoordinator中仍然包含_on_unified_optimization方法")
            return False
        else:
            logger.info("✓ MainWindowCoordinator中已移除_on_unified_optimization方法")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 协调器导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_virtual_scroll_renderer():
    """测试虚拟滚动渲染器（应该保留）"""
    logger.info("\n" + "=" * 60)
    logger.info("测试6: 验证虚拟滚动渲染器（应该保留）")
    logger.info("=" * 60)
    
    try:
        from core.advanced_optimization.performance.virtualization import VirtualRenderManager
        from core.optimization.candle_virtual_renderer import CandleVirtualRenderer
        from core.optimization.volume_virtual_renderer import VolumeVirtualRenderer
        from core.optimization.line_virtual_renderer import LineVirtualRenderer
        from core.optimization.bar_virtual_renderer import BarVirtualRenderer
        
        logger.info("✓ VirtualRenderManager 导入成功")
        logger.info("✓ CandleVirtualRenderer 导入成功")
        logger.info("✓ VolumeVirtualRenderer 导入成功")
        logger.info("✓ LineVirtualRenderer 导入成功")
        logger.info("✓ BarVirtualRenderer 导入成功")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 虚拟滚动渲染器导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance_coordinator():
    """测试性能协调器（应该保留）"""
    logger.info("\n" + "=" * 60)
    logger.info("测试7: 验证性能协调器（应该保留）")
    logger.info("=" * 60)
    
    try:
        from core.advanced_optimization.performance.unified_performance_coordinator import UnifiedPerformanceCoordinator
        from core.advanced_optimization.performance.performance_optimization_integration import PerformanceOptimizer
        from core.advanced_optimization.performance.advanced_performance_analytics import AdvancedPerformanceAnalytics
        
        logger.info("✓ UnifiedPerformanceCoordinator 导入成功")
        logger.info("✓ PerformanceOptimizer 导入成功")
        logger.info("✓ AdvancedPerformanceAnalytics 导入成功")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 性能协调器导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("性能监控中心深度优化清理测试")
    logger.info("=" * 60)
    
    # 运行所有测试
    tests = [
        ("导入测试", test_import),
        ("文件删除测试", test_deleted_files),
        ("导入错误测试", test_import_errors),
        ("菜单栏导入测试", test_menu_bar_import),
        ("协调器导入测试", test_coordinator_import),
        ("虚拟滚动渲染器测试", test_virtual_scroll_renderer),
        ("性能协调器测试", test_performance_coordinator)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"✗ 测试 {test_name} 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # 输出测试结果
    logger.info("\n" + "=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{status}: {test_name}")
    
    logger.info(f"\n总计: {passed}/{total} 通过")
    
    # 返回退出码
    if passed == total:
        logger.info("\n✓ 所有测试通过!")
        return 0
    else:
        logger.error(f"\n✗ {total - passed} 个测试失败!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
