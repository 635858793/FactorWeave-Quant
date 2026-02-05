#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试导入链
"""

import sys
from pathlib import Path
from loguru import logger

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_import_chain():
    """测试导入链"""
    logger.info("=" * 80)
    logger.info("测试导入链")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ Qt模块导入成功")

        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("3. 导入core.performance...")
        import core.performance
        logger.info("✓ core.performance导入成功")

        logger.info("4. 导入gui.widgets.performance.workers...")
        import gui.widgets.performance.workers
        logger.info("✓ gui.widgets.performance.workers导入成功")

        logger.info("5. 导入gui.widgets.performance...")
        import gui.widgets.performance
        logger.info("✓ gui.widgets.performance导入成功")

        logger.info("6. 导入ModernUnifiedPerformanceWidget...")
        from gui.widgets.performance.unified_performance_widget import ModernUnifiedPerformanceWidget
        logger.info("✓ ModernUnifiedPerformanceWidget导入成功")

        logger.info("✓ 所有测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_import_chain()
    logger.info(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)