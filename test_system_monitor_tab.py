#!/usr/bin/env python3
"""
测试 system_monitor_tab 导入
"""

import sys
import os
import traceback
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>", level="INFO")

def test_system_monitor_tab():
    """测试 system_monitor_tab 导入"""
    logger.info("=" * 80)
    logger.info("测试 system_monitor_tab 导入")
    logger.info("=" * 80)

    try:
        # 1. 导入PyQt5
        logger.info("1. 导入PyQt5.QtWidgets...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ PyQt5.QtWidgets导入成功")

        # 2. 创建QApplication
        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        # 3. 导入核心模块
        logger.info("3. 导入核心模块...")
        from core.containers import get_service_container
        from core.events import get_event_bus
        logger.info("✓ 核心模块导入成功")

        # 4. 导入性能监控模块
        logger.info("4. 导入性能监控模块...")
        from core.performance import get_performance_monitor
        logger.info("✓ 性能监控模块导入成功")

        # 5. 导入 plugin_manager
        logger.info("5. 导入 core.plugin_manager...")
        import core.plugin_manager
        logger.info("✓ core.plugin_manager导入成功")

        # 6. 导入 system_monitor_tab
        logger.info("6. 导入 system_monitor_tab...")
        from gui.widgets.performance.tabs.system_monitor_tab import ModernSystemMonitorTab
        logger.info("✓ system_monitor_tab导入成功")

        logger.info("=" * 80)
        logger.info("✓ 测试通过")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("开始测试 system_monitor_tab 导入...")

    result = test_system_monitor_tab()

    if result:
        logger.info("测试通过！")
        sys.exit(0)
    else:
        logger.error("测试失败")
        sys.exit(1)
