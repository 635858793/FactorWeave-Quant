#!/usr/bin/env python3
"""
最小化集成测试
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

def test_minimal():
    """最小化测试"""
    logger.info("=" * 80)
    logger.info("最小化集成测试")
    logger.info("=" * 80)

    try:
        # 1. 测试导入
        logger.info("1. 测试导入...")
        from core.performance import (
            initialize_performance_managers,
            get_performance_managers,
            get_timer_manager,
            get_thread_pool_manager,
            get_task_scheduler,
            get_resource_monitor,
            get_data_update_manager
        )
        logger.info("✓ 导入成功")

        # 2. 测试初始化
        logger.info("2. 测试初始化...")
        from core.events import get_event_bus
        event_bus = get_event_bus()
        success = initialize_performance_managers(event_bus=event_bus)
        
        if success:
            logger.info("✓ 初始化成功")
        else:
            logger.error("✗ 初始化失败")
            return False

        # 3. 测试获取管理器
        logger.info("3. 测试获取管理器...")
        managers = get_performance_managers()
        
        for name, manager in managers.items():
            logger.info(f"✓ {name}: {type(manager).__name__}")

        # 4. 测试基本功能
        logger.info("4. 测试基本功能...")
        
        # 测试数据更新管理器
        data_update_manager = get_data_update_manager()
        
        def test_collector():
            return {"test": "data"}
        
        data_update_manager.register_tab(
            tab_name="test_tab",
            data_collector=test_collector,
            update_interval=5.0,
            enabled=True
        )
        logger.info("✓ 数据更新管理器注册成功")
        
        # 测试任务调度器
        task_scheduler = get_task_scheduler()
        
        from core.performance.thread_pool_manager import TaskPriority
        
        def test_task():
            return "test_result"
        
        task_id = task_scheduler.schedule_task(
            func=test_task,
            priority=TaskPriority.NORMAL
        )
        logger.info(f"✓ 任务调度器调度成功: {task_id}")

        # 5. 清理
        logger.info("5. 清理...")
        import time
        time.sleep(1)

        logger.info("=" * 80)
        logger.info("✓ 最小化集成测试通过")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_minimal()
    sys.exit(0 if success else 1)
