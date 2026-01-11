#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试账户仓储初始化（简化版）
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

def test_repository_init_simple():
    """测试仓储初始化（简化版）"""
    try:
        logger.info("开始测试账户仓储初始化（简化版）...")
        
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
        logger.info("5. 开始初始化数据库服务...")
        db_service.initialize()
        logger.info("6. 数据库服务初始化成功")
        
        # 测试hikyuu_sqlite连接池
        logger.info("7. 测试hikyuu_sqlite连接池...")
        with db_service.get_connection("hikyuu_sqlite") as conn:
            logger.info("8. hikyuu_sqlite连接成功")
            
            # 测试查询
            result = conn.execute("SELECT 1 as test")
            logger.info(f"9. 查询测试成功: {result}")
        
        # 导入事件总线
        from core.events import EventBus
        logger.info("10. 事件总线导入成功")
        
        # 创建事件总线
        event_bus = EventBus()
        logger.info("11. 事件总线创建成功")
        
        # 导入账户仓储
        from core.trading.account_repository import AccountRepository
        logger.info("12. 账户仓储导入成功")
        
        # 创建账户仓储
        logger.info("13. 开始创建账户仓储...")
        repository = AccountRepository(service_container, event_bus)
        logger.info("14. 账户仓储创建成功")
        
        logger.info("✅ 账户仓储初始化测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 账户仓储初始化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_repository_init_simple()
    sys.exit(0 if success else 1)
