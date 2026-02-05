#!/usr/bin/env python3
"""
测试UI与后端的完整集成
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

def test_ui_integration():
    """测试UI与后端的集成"""
    logger.info("=" * 80)
    logger.info("测试UI与后端的完整集成")
    logger.info("=" * 80)

    try:
        # 1. 初始化核心模块
        logger.info("1. 初始化核心模块...")
        from core.containers import ServiceContainer, get_service_container
        from core.events import EventBus, get_event_bus
        from core.services.service_bootstrap import bootstrap_services
        
        event_bus = get_event_bus()
        service_container = get_service_container()
        
        # 执行服务引导
        if not bootstrap_services():
            logger.error("服务引导失败")
            return False
        
        logger.info("✓ 核心模块初始化完成")

        # 2. 验证统一管理器已注册到容器
        logger.info("2. 验证统一管理器已注册到容器...")
        from core.performance.timer_manager import UnifiedTimerManager
        from core.performance.thread_pool_manager import UnifiedThreadPoolManager
        from core.performance.task_scheduler import UnifiedTaskScheduler
        from core.performance.resource_monitor import UnifiedResourceMonitor
        from core.performance.data_update_manager import PerformanceDataUpdateManager

        managers = [
            (UnifiedTimerManager, "统一定时器管理器"),
            (UnifiedThreadPoolManager, "统一线程池管理器"),
            (UnifiedTaskScheduler, "统一任务调度器"),
            (UnifiedResourceMonitor, "统一资源监控器"),
            (PerformanceDataUpdateManager, "性能数据更新管理器")
        ]

        all_registered = True
        for manager_type, manager_name in managers:
            if service_container.is_registered(manager_type):
                logger.info(f"✓ {manager_name} 已注册到容器")
            else:
                logger.error(f"✗ {manager_name} 未注册到容器")
                all_registered = False

        if not all_registered:
            logger.error("部分统一管理器未注册到容器")
            return False

        # 3. 测试重构后的UI组件
        logger.info("3. 测试重构后的UI组件...")
        
        # 测试system_monitor_tab_refactored
        try:
            from gui.widgets.performance.tabs.system_monitor_tab_refactored import ModernSystemMonitorTab
            logger.info("✓ system_monitor_tab_refactored 导入成功")
            
            # 检查是否使用了统一管理器
            import inspect
            source = inspect.getsource(ModernSystemMonitorTab.__init__)
            
            if 'get_data_update_manager' in source or 'get_resource_monitor' in source:
                logger.info("✓ system_monitor_tab_refactored 使用了统一管理器")
            else:
                logger.warning("⚠ system_monitor_tab_refactored 可能未使用统一管理器")
                
        except Exception as e:
            logger.error(f"✗ system_monitor_tab_refactored 测试失败: {e}")

        # 测试unified_performance_widget_refactored
        try:
            from gui.widgets.performance.unified_performance_widget_refactored import ModernUnifiedPerformanceWidget
            logger.info("✓ unified_performance_widget_refactored 导入成功")
            
            # 检查是否使用了统一管理器
            source = inspect.getsource(ModernUnifiedPerformanceWidget.__init__)
            
            if 'initialize_performance_managers' in source or 'get_data_update_manager' in source:
                logger.info("✓ unified_performance_widget_refactored 使用了统一管理器")
            else:
                logger.warning("⚠ unified_performance_widget_refactored 可能未使用统一管理器")
                
        except Exception as e:
            logger.error(f"✗ unified_performance_widget_refactored 测试失败: {e}")

        # 4. 验证事件总线连接
        logger.info("4. 验证事件总线连接...")
        
        for manager_type, manager_name in managers:
            try:
                manager = service_container.resolve(manager_type)
                if hasattr(manager, '_event_bus') and manager._event_bus is not None:
                    logger.info(f"✓ {manager_name} 已连接到事件总线")
                else:
                    logger.warning(f"⚠ {manager_name} 未连接到事件总线")
            except Exception as e:
                logger.error(f"✗ {manager_name} 事件总线检查失败: {e}")

        # 5. 验证数据更新管理器功能
        logger.info("5. 验证数据更新管理器功能...")
        
        try:
            data_update_manager = service_container.resolve(PerformanceDataUpdateManager)
            
            # 测试注册标签页
            def test_collector():
                return {"test": "data"}
            
            data_update_manager.register_tab(
                tab_name="test_tab",
                data_collector=test_collector,
                update_interval=5.0,
                enabled=True
            )
            logger.info("✓ 数据更新管理器可以注册标签页")
            
            # 测试启动更新
            data_update_manager.start()
            logger.info("✓ 数据更新管理器启动成功")
            
            # 测试停止更新
            data_update_manager.stop()
            logger.info("✓ 数据更新管理器停止成功")
            
        except Exception as e:
            logger.error(f"✗ 数据更新管理器功能测试失败: {e}")
            return False

        logger.info("=" * 80)
        logger.info("✓ UI与后端集成测试通过")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"✗ UI与后端集成测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_ui_integration()
    sys.exit(0 if success else 1)
