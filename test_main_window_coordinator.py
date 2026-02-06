#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试主窗口协调器初始化
"""

import sys
from pathlib import Path
from loguru import logger

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_main_window_coordinator():
    """测试主窗口协调器初始化"""
    logger.info("=" * 80)
    logger.info("测试主窗口协调器初始化")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入基础模块...")
        from core.events import get_event_bus
        from core.containers import get_service_container
        from core.services.service_bootstrap import bootstrap_services
        logger.info("✓ 基础模块导入成功")

        logger.info("2. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ Qt模块导入成功")

        logger.info("3. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("4. 初始化核心组件...")
        service_container = get_service_container()
        event_bus = get_event_bus()
        logger.info("✓ 核心组件初始化成功")

        logger.info("5. 注册服务...")
        if not bootstrap_services():
            logger.error("服务注册失败")
            return False
        logger.info("✓ 服务注册完成")

        logger.info("6. 导入主窗口协调器...")
        from core.coordinators import MainWindowCoordinator
        logger.info("✓ 主窗口协调器导入成功")

        logger.info("7. 创建主窗口协调器...")
        try:
            main_window_coordinator = MainWindowCoordinator(
                service_container=service_container,
                event_bus=event_bus
            )
            logger.info("✓ 主窗口协调器创建成功")
        except Exception as e:
            logger.error(f"✗ 主窗口协调器创建失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

        logger.info("8. 初始化主窗口协调器...")
        try:
            main_window_coordinator.initialize()
            logger.info("✓ 主窗口协调器初始化完成")
        except Exception as e:
            logger.error(f"✗ 主窗口协调器初始化失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

        logger.info("✓ 所有测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_main_window_coordinator()
    logger.info(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)