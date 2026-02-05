#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐步测试 metric_card 导入过程
"""

import sys
import traceback
from loguru import logger

def test_metric_card_step_by_step():
    """逐步测试 metric_card 导入过程"""
    logger.info("=" * 80)
    logger.info("逐步测试 metric_card 导入过程")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入 PyQt5.QtWidgets...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ PyQt5.QtWidgets导入成功")

        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("3. 导入 loguru...")
        from loguru import logger as loguru_logger
        logger.info("✓ loguru导入成功")

        logger.info("4. 导入 PyQt5 组件...")
        from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsDropShadowEffect
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QFont, QColor
        logger.info("✓ PyQt5 组件导入成功")

        logger.info("5. 尝试导入 get_theme_manager...")
        try:
            from utils.theme import get_theme_manager
            logger.info("✓ get_theme_manager导入成功")
        except Exception as e:
            logger.error(f"✗ get_theme_manager导入失败: {e}")
            logger.error(traceback.format_exc())
            return False

        logger.info("6. 检查 THEME_MANAGER_AVAILABLE...")
        try:
            from utils.theme import get_theme_manager
            THEME_MANAGER_AVAILABLE = True
            logger.info(f"✓ THEME_MANAGER_AVAILABLE = {THEME_MANAGER_AVAILABLE}")
        except ImportError:
            THEME_MANAGER_AVAILABLE = False
            logger.warning(f"✗ ThemeManager不可用")

        logger.info("7. 导入 metric_card 模块（不创建实例）...")
        try:
            import gui.widgets.performance.components.metric_card
            logger.info("✓ metric_card 模块导入成功")
        except Exception as e:
            logger.error(f"✗ metric_card 模块导入失败: {e}")
            logger.error(traceback.format_exc())
            return False

        logger.info("8. 测试完成")
        return True
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_metric_card_step_by_step()
    sys.exit(0 if success else 1)
