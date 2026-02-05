#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 get_theme_manager 调用
"""

import sys
import traceback
from loguru import logger

def test_get_theme_manager_call():
    """测试 get_theme_manager 调用"""
    logger.info("=" * 80)
    logger.info("测试 get_theme_manager 调用")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入 PyQt5.QtWidgets...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ PyQt5.QtWidgets导入成功")

        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("3. 导入 get_theme_manager...")
        from utils.theme import get_theme_manager
        logger.info("✓ get_theme_manager导入成功")

        logger.info("4. 调用 get_theme_manager()...")
        theme_manager = get_theme_manager()
        logger.info("✓ get_theme_manager()调用成功")

        logger.info("5. 测试完成")
        return True
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_get_theme_manager_call()
    sys.exit(0 if success else 1)
