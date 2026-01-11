#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试导入database_service（简化版）
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

def test_database_import():
    """测试数据库服务导入"""
    try:
        logger.info("开始测试数据库服务导入...")

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

        # 步骤4: 导入base_service
        logger.info("4. 导入 core.services.base_service...")
        from core.services.base_service import BaseService
        logger.info("   ✅ core.services.base_service 导入成功")

        # 步骤5: 导入plugin_types
        logger.info("5. 导入 core.plugin_types...")
        from core.plugin_types import AssetType, DataType
        logger.info("   ✅ core.plugin_types 导入成功")

        # 步骤6: 导入asset_database_manager
        logger.info("6. 导入 core.asset_database_manager...")
        from core.asset_database_manager import AssetSeparatedDatabaseManager
        logger.info("   ✅ core.asset_database_manager 导入成功")

        # 步骤7: 导入database_service（不初始化）
        logger.info("7. 导入 core.services.database_service...")
        import core.services.database_service
        logger.info("   ✅ core.services.database_service 导入成功")

        # 步骤8: 创建数据库服务实例
        logger.info("8. 创建数据库服务实例...")
        from core.services.database_service import DatabaseService
        db_service = DatabaseService(service_container)
        logger.info("   ✅ 数据库服务实例创建成功")

        # 步骤9: 初始化数据库服务
        logger.info("9. 初始化数据库服务...")
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
    success = test_database_import()
    sys.exit(0 if success else 1)
