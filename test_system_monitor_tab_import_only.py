#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 system_monitor_tab 导入 - 不创建实例
"""

import sys
import traceback
from loguru import logger

def test_system_monitor_tab_import_only():
    """测试 system_monitor_tab 导入 - 不创建实例"""
    logger.info("=" * 80)
    logger.info("测试 system_monitor_tab 导入 - 不创建实例")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入 PyQt5.QtWidgets...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ PyQt5.QtWidgets导入成功")

        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("3. 导入核心模块...")
        from core.containers import get_service_container
        from core.events import get_event_bus
        logger.info("✓ 核心模块导入成功")

        logger.info("4. 导入性能监控模块...")
        from core.performance import get_performance_monitor
        logger.info("✓ 性能监控模块导入成功")

        logger.info("5. 导入 core.plugin_manager...")
        from core.plugin_manager import PluginManager
        logger.info("✓ core.plugin_manager导入成功")

        logger.info("6. 导入 system_monitor_tab（不创建实例）...")
        from gui.widgets.performance.tabs.system_monitor_tab import ModernSystemMonitorTab
        logger.info("✓ system_monitor_tab导入成功")

        logger.info("7. 测试完成，不创建实例")
        return True
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_system_monitor_tab_import_only()
    sys.exit(0 if success else 1)
