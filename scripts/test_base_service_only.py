#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试导入base_service
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

def test_base_service():
    """测试base_service导入"""
    try:
        logger.info("开始测试base_service导入...")

        # 步骤1: 导入events
        logger.info("1. 导入 core.events...")
        from core.events import EventBus
        logger.info("   ✅ core.events 导入成功")

        # 步骤2: 导入base_service
        logger.info("2. 导入 core.services.base_service...")
        from core.services.base_service import BaseService
        logger.info("   ✅ core.services.base_service 导入成功")

        logger.info("✅ base_service测试通过")
        return True

    except Exception as e:
        logger.error(f"❌ base_service测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_base_service()
    sys.exit(0 if success else 1)
