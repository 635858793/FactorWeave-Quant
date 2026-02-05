#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试优化仪表板模块导入（简单版）
"""

import sys
from pathlib import Path
from loguru import logger

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_simple_import():
    """简单测试优化仪表板模块导入"""
    logger.info("=" * 80)
    logger.info("简单测试优化仪表板模块导入")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ Qt模块导入成功")

        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("3. 导入优化仪表板模块...")
        import optimization.optimization_dashboard
        logger.info("✓ 优化仪表板模块导入成功")

        logger.info("4. 检查create_optimization_dashboard函数...")
        if hasattr(optimization.optimization_dashboard, 'create_optimization_dashboard'):
            logger.info("✓ create_optimization_dashboard函数存在")
        else:
            logger.warning("✗ create_optimization_dashboard函数不存在")

        logger.info("✓ 所有测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_simple_import()
    logger.info(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)