#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试日志初始化是否导致卡住
"""

import sys
from pathlib import Path
from loguru import logger

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_loguru_initialization():
    """测试Loguru初始化"""
    logger.info("=" * 80)
    logger.info("测试Loguru初始化")
    logger.info("=" * 80)

    try:
        logger.info("1. 测试基础日志功能...")
        logger.info("✓ 基础日志功能正常")

        logger.info("2. 测试导入core.loguru_config...")
        import core.loguru_config
        logger.info("✓ core.loguru_config导入成功")

        logger.info("3. 测试导入core.performance...")
        import core.performance
        logger.info("✓ core.performance导入成功")

        logger.info("4. 测试导入core.performance.unified_monitor...")
        import core.performance.unified_monitor
        logger.info("✓ core.performance.unified_monitor导入成功")

        logger.info("5. 测试调用get_performance_monitor()...")
        from core.performance import get_performance_monitor
        monitor = get_performance_monitor()
        logger.info(f"✓ get_performance_monitor()调用成功: {type(monitor).__name__}")

        logger.info("✓ 所有测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_loguru_initialization()
    logger.info(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)