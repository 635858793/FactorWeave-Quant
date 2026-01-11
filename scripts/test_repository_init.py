#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试账户仓储初始化
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

def test_repository_init():
    """测试仓储初始化"""
    try:
        logger.info("开始测试账户仓储初始化...")
        
        # 导入服务容器
        from core.containers import get_service_container
        logger.info("服务容器导入成功")
        
        # 获取服务容器
        service_container = get_service_container()
        logger.info("服务容器获取成功")
        
        # 导入事件总线
        from core.events import EventBus
        logger.info("事件总线导入成功")
        
        # 创建事件总线
        event_bus = EventBus()
        logger.info("事件总线创建成功")
        
        # 导入账户仓储
        from core.trading.account_repository import AccountRepository
        logger.info("账户仓储导入成功")
        
        # 创建账户仓储
        repository = AccountRepository(service_container, event_bus)
        logger.info("账户仓储创建成功")
        
        logger.info("✅ 账户仓储初始化测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 账户仓储初始化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_repository_init()
    sys.exit(0 if success else 1)
