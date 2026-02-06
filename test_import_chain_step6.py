#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试导入链 - 逐步导入
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

logger.info("开始测试导入链...")

# 逐步导入模块
logger.info("1. 导入 core.graceful_shutdown...")
try:
    import core.graceful_shutdown
    logger.info("✓ core.graceful_shutdown 导入完成")
except Exception as e:
    logger.error(f"✗ core.graceful_shutdown 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("2. 导入 shutdown_manager...")
try:
    from core.graceful_shutdown import shutdown_manager
    logger.info("✓ shutdown_manager 导入完成")
except Exception as e:
    logger.error(f"✗ shutdown_manager 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("导入链测试完成")
