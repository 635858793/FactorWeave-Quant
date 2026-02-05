#!/usr/bin/env python3
"""
核心集成测试 - 不涉及PyQt5
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

def test_core_integration():
    """测试核心集成"""
    logger.info("=" * 80)
    logger.info("核心集成测试")
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

        # 3. 验证事件总线连接
        logger.info("3. 验证事件总线连接...")
        
        for manager_type, manager_name in managers:
            try:
                manager = service_container.resolve(manager_type)
                if hasattr(manager, '_event_bus') and manager._event_bus is not None:
                    logger.info(f"✓ {manager_name} 已连接到事件总线")
                else:
                    logger.warning(f"⚠ {manager_name} 未连接到事件总线")
            except Exception as e:
                logger.error(f"✗ {manager_name} 事件总线检查失败: {e}")

        # 4. 验证数据更新管理器功能
        logger.info("4. 验证数据更新管理器功能...")
        
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
            import traceback
            logger.error(traceback.format_exc())
            return False

        # 5. 测试任务调度器功能
        logger.info("5. 测试任务调度器功能...")
        
        try:
            task_scheduler = service_container.resolve(UnifiedTaskScheduler)
            
            # 测试调度任务
            def test_task():
                return "test_result"
            
            task_id = task_scheduler.schedule_task(
                func=test_task,
                priority=1
            )
            logger.info(f"✓ 任务调度器可以调度任务: {task_id}")
            
            # 等待任务完成
            import time
            time.sleep(1)
            
            # 获取统计信息
            stats = task_scheduler.get_stats()
            logger.info(f"✓ 任务调度器统计: {stats}")
            
        except Exception as e:
            logger.error(f"✗ 任务调度器功能测试失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

        logger.info("=" * 80)
        logger.info("✓ 核心集成测试通过")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"✗ 核心集成测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_core_integration()
    sys.exit(0 if success else 1)
