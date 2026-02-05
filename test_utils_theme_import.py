#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 utils.theme 导入
"""

import sys
import traceback
from loguru import logger

def test_utils_theme_import():
    """测试 utils.theme 导入"""
    logger.info("=" * 80)
    logger.info("测试 utils.theme 导入")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入 PyQt5.QtWidgets...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ PyQt5.QtWidgets导入成功")

        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("3. 导入 utils.theme...")
        from utils import theme
        logger.info("✓ utils.theme导入成功")

        logger.info("4. 测试完成")
        return True
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_utils_theme_import()
    sys.exit(0 if success else 1)
