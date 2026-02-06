#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 optimization_dashboard 导入
"""

import sys
from pathlib import Path
from loguru import logger

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_optimization_dashboard_import():
    """测试 optimization_dashboard 导入"""
    logger.info("=" * 80)
    logger.info("测试 optimization_dashboard 导入")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ Qt模块导入成功")

        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("3. 导入优化仪表板模块...")
        from optimization.optimization_dashboard import create_optimization_dashboard
        logger.info("✓ 优化仪表板模块导入成功")

        logger.info("✓ 所有测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_optimization_dashboard_import()
    logger.info(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)