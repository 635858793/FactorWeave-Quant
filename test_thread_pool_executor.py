#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 ThreadPoolExecutor 创建
"""

import sys
import traceback
from loguru import logger

def test_thread_pool_executor():
    """测试 ThreadPoolExecutor 创建"""
    logger.info("=" * 80)
    logger.info("测试 ThreadPoolExecutor 创建")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入 concurrent.futures...")
        from concurrent.futures import ThreadPoolExecutor
        logger.info("✓ concurrent.futures导入成功")

        logger.info("2. 创建 ThreadPoolExecutor...")
        executor = ThreadPoolExecutor(max_workers=3)
        logger.info("✓ ThreadPoolExecutor创建成功")

        logger.info("3. 测试完成")
        return True
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_thread_pool_executor()
    sys.exit(0 if success else 1)
