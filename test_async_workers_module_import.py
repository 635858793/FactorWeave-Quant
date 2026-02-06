#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试async_workers.py模块导入
"""

import sys
from pathlib import Path
from loguru import logger

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_async_workers_module_import():
    """测试async_workers.py模块导入"""
    logger.info("=" * 80)
    logger.info("测试async_workers.py模块导入")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ Qt模块导入成功")

        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("3. 导入async_workers.py模块...")
        import gui.widgets.performance.workers.async_workers
        logger.info("✓ async_workers.py模块导入成功")

        logger.info("4. 访问AsyncDataSignals类...")
        from gui.widgets.performance.workers.async_workers import AsyncDataSignals
        logger.info("✓ AsyncDataSignals类导入成功")

        logger.info("5. 创建AsyncDataSignals实例...")
        signals = AsyncDataSignals()
        logger.info(f"✓ AsyncDataSignals实例创建成功: {type(signals).__name__}")

        logger.info("✓ 所有测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_async_workers_module_import()
    logger.info(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)