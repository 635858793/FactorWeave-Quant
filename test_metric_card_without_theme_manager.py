#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 metric_card 模块导入（不导入 get_theme_manager）
"""

import sys
import traceback
from loguru import logger

def test_metric_card_without_theme_manager():
    """测试 metric_card 模块导入（不导入 get_theme_manager）"""
    logger.info("=" * 80)
    logger.info("测试 metric_card 模块导入（不导入 get_theme_manager）")
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

        logger.info("5. 修改 metric_card 模块，不导入 get_theme_manager...")
        # 读取 metric_card 模块
        metric_card_path = "gui/widgets/performance/components/metric_card.py"
        with open(metric_card_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 替换 get_theme_manager 导入
        modified_content = content.replace(
            "try:\n    from utils.theme import get_theme_manager\n    THEME_MANAGER_AVAILABLE = True\nexcept ImportError:\n    THEME_MANAGER_AVAILABLE = False\n    logger.warning(\"ThemeManager不可用，ModernMetricCard将使用默认样式\")",
            "THEME_MANAGER_AVAILABLE = False"
        )

        # 写入临时文件
        temp_path = "gui/widgets/performance/components/metric_card_temp.py"
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        logger.info("✓ 临时文件创建成功")

        logger.info("6. 导入临时 metric_card 模块...")
        import importlib.util
        spec = importlib.util.spec_from_file_location("metric_card_temp", temp_path)
        metric_card_temp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(metric_card_temp)
        logger.info("✓ 临时 metric_card 模块导入成功")

        logger.info("7. 测试完成")
        return True
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_metric_card_without_theme_manager()
    sys.exit(0 if success else 1)
