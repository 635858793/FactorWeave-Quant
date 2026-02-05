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
logger.info("1. 导入 core.services.service_bootstrap...")
try:
    import core.services.service_bootstrap
    logger.info("✓ core.services.service_bootstrap 导入完成")
except Exception as e:
    logger.error(f"✗ core.services.service_bootstrap 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("2. 导入 bootstrap_services...")
try:
    from core.services.service_bootstrap import bootstrap_services
    logger.info("✓ bootstrap_services 导入完成")
except Exception as e:
    logger.error(f"✗ bootstrap_services 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("导入链测试完成")
