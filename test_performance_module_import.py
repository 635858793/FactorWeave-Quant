#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 core.performance 模块导入
"""

import sys
import traceback
from loguru import logger

def test_performance_module_import():
    """测试 core.performance 模块导入"""
    logger.info("=" * 80)
    logger.info("测试 core.performance 模块导入")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入 core.performance...")
        import core.performance
        logger.info("✓ core.performance 导入成功")
        return True
    except Exception as e:
        logger.error(f"✗ core.performance 导入失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_performance_module_import()
    sys.exit(0 if success else 1)
