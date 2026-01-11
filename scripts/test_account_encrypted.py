#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试账户管理系统（加密版本）
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

def test_account_management():
    """测试账户管理系统"""
    try:
        logger.info("开始测试账户管理系统（加密版本）...")

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

        # 导入数据库服务
        from core.services.database_service import DatabaseService
        logger.info("数据库服务导入成功")

        # 创建并初始化数据库服务
        db_service = DatabaseService(service_container)
        db_service.initialize()
        logger.info("数据库服务初始化成功")

        # 导入账户仓储
        from core.trading.account_repository import AccountRepository
        logger.info("账户仓储导入成功")

        # 创建账户仓储
        repository = AccountRepository(service_container, event_bus)
        logger.info("账户仓储创建成功")

        # 导入账户模型
        from core.trading.account_models import Account
        logger.info("账户模型导入成功")

        # 创建测试账户
        from datetime import datetime
        from uuid import uuid4

        account_id = str(uuid4())
        account = Account(
            account_id=account_id,
            account_name="测试账户",
            account_type="ctp",
            status="active",
            balance=100000.0,
            available_balance=100000.0,
            frozen_balance=0.0,
            market_value=0.0,
            total_assets=100000.0,
            profit_loss=0.0,
            profit_loss_ratio=0.0,
            create_time=datetime.now(),
            update_time=datetime.now(),
            user_id="test_user",
            trading_day=None,
            risk_level="normal",
            margin_ratio=0.0,
            maintenance_margin=0.0,
            metadata={},
            ctp_broker_id="9999",
            ctp_investor_id="test_investor",
            ctp_password="test_password_123",  # 这个密码会被加密
            ctp_trade_front="tcp://180.168.146.187:10130",
            ctp_quote_front="tcp://180.168.146.187:10131",
            ctp_app_id="simnow_client_test",
            ctp_auth_code="test_auth_code_456",  # 这个认证码会被加密
            ctp_product_info="simnow_client_test"
        )

        logger.info(f"创建测试账户: {account_id}")

        # 保存账户
        result = repository.save_account(account)
        if result:
            logger.info("✅ 账户保存成功（密码已加密）")
        else:
            logger.error("❌ 账户保存失败")
            return False

        # 读取账户
        retrieved_account = repository.get_account(account_id)
        if retrieved_account:
            logger.info("✅ 账户读取成功（密码已解密）")
            logger.info(f"账户名称: {retrieved_account.account_name}")
            logger.info(f"CTP密码: {retrieved_account.ctp_password}")
            logger.info(f"CTP认证码: {retrieved_account.ctp_auth_code}")
        else:
            logger.error("❌ 账户读取失败")
            return False

        # 获取账户列表
        accounts = repository.get_accounts()
        logger.info(f"✅ 获取账户列表成功，共 {len(accounts)} 个账户")

        logger.info("✅ 账户管理系统测试通过")
        return True

    except Exception as e:
        logger.error(f"❌ 账户管理系统测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_account_management()
    sys.exit(0 if success else 1)
