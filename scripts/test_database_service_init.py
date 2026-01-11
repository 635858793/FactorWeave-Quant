#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据库服务初始化
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

def test_database_service_init():
    """测试数据库服务初始化"""
    try:
        logger.info("开始测试数据库服务初始化...")
        
        # 导入服务容器
        from core.containers import get_service_container
        logger.info("1. 服务容器导入成功")
        
        # 获取服务容器
        service_container = get_service_container()
        logger.info("2. 服务容器获取成功")
        
        # 导入数据库服务
        from core.services.database_service import DatabaseService
        logger.info("3. 数据库服务导入成功")
        
        # 创建数据库服务实例
        db_service = DatabaseService(service_container)
        logger.info("4. 数据库服务实例创建成功")
        
        # 初始化数据库服务
        db_service.initialize()
        logger.info("5. 数据库服务初始化成功")
        
        logger.info("✅ 数据库服务初始化测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 数据库服务初始化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_database_service_init()
    sys.exit(0 if success else 1)
