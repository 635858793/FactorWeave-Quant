#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 get_performance_monitor 导入
"""

import sys
import traceback
from loguru import logger

def test_get_performance_monitor_import():
    """测试 get_performance_monitor 导入"""
    logger.info("=" * 80)
    logger.info("测试 get_performance_monitor 导入")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入 get_performance_monitor...")
        from core.performance import get_performance_monitor
        logger.info("✓ get_performance_monitor 导入成功")

        logger.info("2. 检查是否已创建实例...")
        # 不调用函数，只是检查
        logger.info("✓ 导入完成，未调用函数")
        return True
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_get_performance_monitor_import()
    sys.exit(0 if success else 1)
