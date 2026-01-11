#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试账户仓储导入
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

def test_account_repository_import():
    """测试账户仓储导入"""
    try:
        logger.info("开始测试账户仓储导入...")
        
        # 测试导入account_models
        logger.info("1. 导入 core.trading.account_models...")
        from core.trading.account_models import Account, Position, FundInfo
        logger.info("   ✅ core.trading.account_models 导入成功")
        
        # 测试导入plugin_types
        logger.info("2. 导入 core.plugin_types...")
        from core.plugin_types import AssetType
        logger.info("   ✅ core.plugin_types 导入成功")
        
        # 测试导入account_repository
        logger.info("3. 导入 core.trading.account_repository...")
        from core.trading.account_repository import AccountRepository
        logger.info("   ✅ core.trading.account_repository 导入成功")
        
        logger.info("✅ 所有导入测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 导入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_account_repository_import()
    sys.exit(0 if success else 1)
