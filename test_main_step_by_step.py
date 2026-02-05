#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐步测试 main.py 初始化过程
"""

import sys
import traceback
from pathlib import Path
from loguru import logger

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_step_by_step():
    """逐步测试 main.py 初始化过程"""
    logger.info("=" * 80)
    logger.info("逐步测试 main.py 初始化过程")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入基础模块...")
        from utils.exception_handler import setup_exception_handler
        from utils.warning_suppressor import suppress_warnings
        from core.events import EventBus, get_event_bus
        from core.containers import ServiceContainer, get_service_container
        from core.containers.service_registry import ServiceScope
        from core.services.service_bootstrap import bootstrap_services
        from core.graceful_shutdown import shutdown_manager
        logger.info("✓ 基础模块导入成功")

        logger.info("2. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication, QMessageBox
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QIcon
        from qasync import QEventLoop
        logger.info("✓ Qt模块导入成功")

        logger.info("3. 创建QApplication...")
        app = QApplication(sys.argv)
        app.setApplicationName("FactorWeave-Quant")
        app.setApplicationVersion("2.0")
        app.setOrganizationName("FactorWeave 团队")
        logger.info("✓ QApplication创建成功")

        logger.info("4. 设置Qt日志处理器...")
        try:
            from gui.loguru_qt_handler import get_qt_handler
            qt_handler = get_qt_handler()
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, lambda: qt_handler.setup_processing_timer() if qt_handler else None)
            logger.info("✓ Qt日志处理器初始化成功")
        except Exception as e:
            logger.warning(f"Qt日志处理器初始化失败: {e}")

        logger.info("5. 抑制警告...")
        suppress_warnings()
        logger.info("✓ 警告抑制完成")

        logger.info("6. 设置异常处理器...")
        setup_exception_handler(app)
        logger.info("✓ 异常处理器设置完成")

        logger.info("7. 初始化核心组件...")
        service_container = get_service_container()
        event_bus = get_event_bus()
        logger.info(f"✓ 服务容器: {type(service_container).__name__}")
        logger.info(f"✓ 事件总线: {type(event_bus).__name__}")

        logger.info("8. 注册服务...")
        if not bootstrap_services():
            logger.error("服务注册失败")
            return False
        logger.info("✓ 服务注册完成")

        logger.info("9. 初始化JIT系统...")
        try:
            from backtest.jit_system_initializer import initialize_jit_system
            if initialize_jit_system():
                logger.info("✓ JIT系统初始化成功")
            else:
                logger.warning("JIT系统初始化失败")
        except Exception as e:
            logger.warning(f"JIT系统初始化失败: {e}")

        logger.info("10. 创建主窗口协调器...")
        from core.coordinators import MainWindowCoordinator
        main_window_coordinator = MainWindowCoordinator(
            service_container=service_container,
            event_bus=event_bus
        )
        logger.info("✓ 主窗口协调器创建成功")

        logger.info("11. 初始化主窗口协调器...")
        main_window_coordinator.initialize()
        logger.info("✓ 主窗口协调器初始化完成")

        logger.info("12. 测试完成")
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_step_by_step()
    sys.exit(0 if success else 1)
