#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细测试 metric_card 导入后的状态
"""

import sys
import traceback
from loguru import logger

def test_metric_card_after_import():
    """详细测试 metric_card 导入后的状态"""
    logger.info("=" * 80)
    logger.info("详细测试 metric_card 导入后的状态")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入 PyQt5.QtWidgets...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ PyQt5.QtWidgets导入成功")

        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("3. 导入 metric_card 模块...")
        import gui.widgets.performance.components.metric_card
        logger.info("✓ metric_card 模块导入成功")

        logger.info("4. 检查 QApplication 实例状态...")
        app_instance = QApplication.instance()
        logger.info(f"✓ QApplication 实例: {app_instance}")
        logger.info(f"✓ QApplication 是否存活: {app_instance is not None}")

        logger.info("5. 测试完成，即将退出...")
        logger.info("程序应该正常退出，退出代码应该为 0")

        return True
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_metric_card_after_import()
    logger.info(f"测试结果: {'成功' if success else '失败'}")
    logger.info(f"即将退出，退出代码: {0 if success else 1}")
    sys.exit(0 if success else 1)
