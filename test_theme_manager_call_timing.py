#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试主题管理器调用时机
"""

import sys
from pathlib import Path
from loguru import logger

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_theme_manager_call_timing():
    """测试主题管理器调用时机"""
    logger.info("=" * 80)
    logger.info("测试主题管理器调用时机")
    logger.info("=" * 80)

    try:
        logger.info("1. 在没有QApplication的情况下导入主题管理器模块...")
        from utils.theme import get_theme_manager
        logger.info("✓ 主题管理器模块导入成功")

        logger.info("2. 在没有QApplication的情况下调用get_theme_manager()...")
        try:
            theme_manager = get_theme_manager()
            logger.warning("✗ get_theme_manager()调用成功，这不应该发生")
            return False
        except Exception as e:
            logger.info(f"✓ get_theme_manager()调用失败（预期行为）: {type(e).__name__}: {e}")

        logger.info("3. 创建QApplication...")
        from PyQt5.QtWidgets import QApplication
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("4. 在有QApplication的情况下调用get_theme_manager()...")
        theme_manager = get_theme_manager()
        logger.info(f"✓ get_theme_manager()调用成功: {type(theme_manager).__name__}")

        logger.info("✓ 所有测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_theme_manager_call_timing()
    logger.info(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)