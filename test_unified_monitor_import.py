#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 unified_monitor.py 导入
"""

import sys
import traceback
from loguru import logger

def test_unified_monitor_import():
    """测试 unified_monitor.py 导入"""
    logger.info("=" * 80)
    logger.info("测试 unified_monitor.py 导入")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入 unified_monitor...")
        from core.performance import unified_monitor
        logger.info("✓ unified_monitor 导入成功")
        return True
    except Exception as e:
        logger.error(f"✗ unified_monitor 导入失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_unified_monitor_import()
    sys.exit(0 if success else 1)
