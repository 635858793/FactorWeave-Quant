#!/usr/bin/env python3
"""
简化版系统启动测试
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

def test_simple_imports():
    """测试简单的导入"""
    logger.info("=" * 80)
    logger.info("测试简单导入")
    logger.info("=" * 80)

    try:
        # 1. 测试核心模块导入
        logger.info("1. 测试核心模块导入...")
        from core.containers import ServiceContainer, get_service_container
        from core.events import EventBus, get_event_bus
        logger.info("✓ 核心模块导入完成")

        # 2. 测试性能模块导入
        logger.info("2. 测试性能模块导入...")
        from core.performance import (
            measure_performance,
            get_performance_monitor,
            UnifiedPerformanceMonitor,
            PerformanceStats,
            initialize_performance_managers,
            get_performance_managers,
            get_timer_manager,
            get_thread_pool_manager,
            get_task_scheduler,
            get_resource_monitor,
            get_data_update_manager
        )
        logger.info("✓ 性能模块导入完成")

        # 3. 测试统一管理器初始化
        logger.info("3. 测试统一管理器初始化...")
        event_bus = get_event_bus()
        success = initialize_performance_managers(event_bus=event_bus)
        
        if success:
            logger.info("✓ 统一管理器初始化成功")
        else:
            logger.error("✗ 统一管理器初始化失败")
            return False

        # 4. 测试获取管理器实例
        logger.info("4. 测试获取管理器实例...")
        managers = get_performance_managers()
        
        for manager_name, manager in managers.items():
            logger.info(f"✓ {manager_name}: {type(manager).__name__}")

        # 5. 测试管理器功能
        logger.info("5. 测试管理器功能...")
        
        timer_manager = get_timer_manager()
        logger.info(f"✓ 定时器管理器: {type(timer_manager).__name__}")
        
        thread_pool_manager = get_thread_pool_manager()
        logger.info(f"✓ 线程池管理器: {type(thread_pool_manager).__name__}")
        
        task_scheduler = get_task_scheduler()
        logger.info(f"✓ 任务调度器: {type(task_scheduler).__name__}")
        
        resource_monitor = get_resource_monitor()
        logger.info(f"✓ 资源监控器: {type(resource_monitor).__name__}")
        
        data_update_manager = get_data_update_manager()
        logger.info(f"✓ 数据更新管理器: {type(data_update_manager).__name__}")

        logger.info("=" * 80)
        logger.info("✓ 所有测试通过")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_simple_imports()
    sys.exit(0 if success else 1)
