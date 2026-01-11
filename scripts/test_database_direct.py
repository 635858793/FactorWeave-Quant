#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试直接初始化database_service
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

def test_database_direct():
    """测试直接初始化database_service"""
    try:
        logger.info("开始测试直接初始化database_service...")

        # 步骤1: 导入containers
        logger.info("1. 导入 core.containers...")
        from core.containers import get_service_container
        logger.info("   ✅ core.containers 导入成功")

        # 步骤2: 获取服务容器
        logger.info("2. 获取服务容器...")
        service_container = get_service_container()
        logger.info("   ✅ 服务容器获取成功")

        # 步骤3: 导入events
        logger.info("3. 导入 core.events...")
        from core.events import EventBus
        logger.info("   ✅ core.events 导入成功")

        # 步骤4: 导入database_service
        logger.info("4. 导入 core.services.database_service...")
        from core.services.database_service import DatabaseService
        logger.info("   ✅ core.services.database_service 导入成功")

        # 步骤5: 创建数据库服务实例
        logger.info("5. 创建数据库服务实例...")
        db_service = DatabaseService(service_container)
        logger.info("   ✅ 数据库服务实例创建成功")

        # 步骤6: 初始化数据库服务
        logger.info("6. 初始化数据库服务...")
        db_service.initialize()
        logger.info("   ✅ 数据库服务初始化成功")

        logger.info("✅ 数据库服务测试通过")
        return True

    except Exception as e:
        logger.error(f"❌ 数据库服务测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_database_direct()
    sys.exit(0 if success else 1)
