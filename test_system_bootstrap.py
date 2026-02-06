#!/usr/bin/env python3
"""
测试系统启动时统一管理器是否正确初始化
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

def test_system_bootstrap():
    """测试系统启动流程"""
    logger.info("=" * 80)
    logger.info("测试系统启动流程")
    logger.info("=" * 80)

    try:
        # 1. 导入核心模块
        logger.info("1. 导入核心模块...")
        from core.containers import ServiceContainer, get_service_container
        from core.events import EventBus, get_event_bus
        logger.info("✓ 核心模块导入完成")

        # 2. 初始化服务容器和事件总线
        logger.info("2. 初始化服务容器和事件总线...")
        service_container = get_service_container()
        event_bus = get_event_bus()
        logger.info("✓ 服务容器和事件总线初始化完成")

        # 3. 导入服务引导器
        logger.info("3. 导入服务引导器...")
        from core.services.service_bootstrap import bootstrap_services
        logger.info("✓ 服务引导器导入完成")

        # 4. 执行服务引导
        logger.info("4. 执行服务引导...")
        if not bootstrap_services():
            logger.error("服务引导失败")
            return False
        logger.info("✓ 服务引导完成")

        # 5. 验证统一管理器是否已注册到容器
        logger.info("5. 验证统一管理器是否已注册到容器...")
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

        # 6. 验证统一管理器是否可以正确解析
        logger.info("6. 验证统一管理器是否可以正确解析...")
        for manager_type, manager_name in managers:
            try:
                manager = service_container.resolve(manager_type)
                logger.info(f"✓ {manager_name} 解析成功: {type(manager).__name__}")
            except Exception as e:
                logger.error(f"✗ {manager_name} 解析失败: {e}")
                all_registered = False

        if not all_registered:
            logger.error("部分统一管理器解析失败")
            return False

        # 7. 验证统一管理器是否已连接到事件总线
        logger.info("7. 验证统一管理器是否已连接到事件总线...")
        for manager_type, manager_name in managers:
            try:
                manager = service_container.resolve(manager_type)
                if hasattr(manager, '_event_bus') and manager._event_bus is not None:
                    logger.info(f"✓ {manager_name} 已连接到事件总线")
                else:
                    logger.warning(f"⚠ {manager_name} 未连接到事件总线")
            except Exception as e:
                logger.error(f"✗ {manager_name} 事件总线检查失败: {e}")

        # 8. 验证统一管理器是否已启动
        logger.info("8. 验证统一管理器是否已启动...")
        for manager_type, manager_name in managers:
            try:
                manager = service_container.resolve(manager_type)
                if hasattr(manager, 'is_running') and manager.is_running():
                    logger.info(f"✓ {manager_name} 已启动")
                elif hasattr(manager, 'is_started') and manager.is_started():
                    logger.info(f"✓ {manager_name} 已启动")
                else:
                    logger.warning(f"⚠ {manager_name} 未启动或没有is_running/is_started方法")
            except Exception as e:
                logger.error(f"✗ {manager_name} 启动状态检查失败: {e}")

        logger.info("=" * 80)
        logger.info("✓ 系统启动测试通过")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"✗ 系统启动测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_system_bootstrap()
    sys.exit(0 if success else 1)
