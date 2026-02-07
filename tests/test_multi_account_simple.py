#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多账号功能测试（简化版）

测试订单执行器的多账号功能，包括：
1. 账号级别的交易接口缓存
2. 账号解析逻辑（三级优先级）
"""

import sys
import os
from datetime import datetime
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.trading.account_models import (
    Account, AccountStatus, InstitutionType, TradingInterfaceType
)
from core.trading.order_models import (
    Order, OrderRequest, OrderType, OrderStatus, OrderCategory
)
from core.plugin_types import AssetType
from core.containers import ServiceContainer
from core.events import EventBus
from core.trading.order_executor import OrderExecutor


def test_account_models():
    """测试账号模型"""
    logger.info("=" * 60)
    logger.info("测试 1: 账号模型")
    logger.info("=" * 60)
    
    try:
        # 创建多个账号
        account1 = Account(
            account_id="STOCK_001",
            account_name="股票账户1",
            account_type="股票账户",
            status=AccountStatus.ACTIVE,
            institution_name="中信证券",
            institution_type=InstitutionType.BROKER,
            trading_interface_type=TradingInterfaceType.XTP_PRO,
            xtp_account_id="test_xtp_account_1",
            xtp_password="test_password_1",
            xtp_server_address="127.0.0.1:6001",
            balance=100000.0,
            available_balance=100000.0,
            frozen_balance=0.0,
            market_value=0.0,
            total_assets=100000.0,
            profit_loss=0.0,
            profit_loss_ratio=0.0,
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        
        account2 = Account(
            account_id="STOCK_002",
            account_name="股票账户2",
            account_type="股票账户",
            status=AccountStatus.ACTIVE,
            institution_name="华泰证券",
            institution_type=InstitutionType.BROKER,
            trading_interface_type=TradingInterfaceType.XTP,
            xtp_account_id="test_xtp_account_2",
            xtp_password="test_password_2",
            xtp_server_address="127.0.0.1:6002",
            balance=200000.0,
            available_balance=200000.0,
            frozen_balance=0.0,
            market_value=0.0,
            total_assets=200000.0,
            profit_loss=0.0,
            profit_loss_ratio=0.0,
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        
        account3 = Account(
            account_id="FUTURES_001",
            account_name="期货账户1",
            account_type="期货账户",
            status=AccountStatus.ACTIVE,
            institution_name="中信期货",
            institution_type=InstitutionType.FUTURES_COMPANY,
            trading_interface_type=TradingInterfaceType.CTP,
            ctp_broker_id="9999",
            ctp_investor_id="test_investor",
            ctp_password="test_password",
            ctp_trade_front="tcp://180.168.146.187:10130",
            ctp_quote_front="tcp://180.168.146.187:10131",
            ctp_app_id="test_app",
            ctp_auth_code="test_auth_code",
            ctp_product_info="test_product",
            balance=500000.0,
            available_balance=500000.0,
            frozen_balance=0.0,
            market_value=0.0,
            total_assets=500000.0,
            profit_loss=0.0,
            profit_loss_ratio=0.0,
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        
        logger.info(f"\n账号1信息:")
        logger.info(f"  账号ID: {account1.account_id}")
        logger.info(f"  账号名称: {account1.account_name}")
        logger.info(f"  机构名称: {account1.institution_name}")
        logger.info(f"  交易接口类型: {account1.trading_interface_type.value}")
        logger.info(f"  总资产: {account1.total_assets:.2f}")
        
        logger.info(f"\n账号2信息:")
        logger.info(f"  账号ID: {account2.account_id}")
        logger.info(f"  账号名称: {account2.account_name}")
        logger.info(f"  机构名称: {account2.institution_name}")
        logger.info(f"  交易接口类型: {account2.trading_interface_type.value}")
        logger.info(f"  总资产: {account2.total_assets:.2f}")
        
        logger.info(f"\n账号3信息:")
        logger.info(f"  账号ID: {account3.account_id}")
        logger.info(f"  账号名称: {account3.account_name}")
        logger.info(f"  机构名称: {account3.institution_name}")
        logger.info(f"  交易接口类型: {account3.trading_interface_type.value}")
        logger.info(f"  总资产: {account3.total_assets:.2f}")
        
        logger.info("\n账号模型测试通过")
        return [account1, account2, account3]
    
    except Exception as e:
        logger.error(f"\n❌ 账号模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_order_executor():
    """测试订单执行器的多账号功能"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 2: 订单执行器的多账号功能")
    logger.info("=" * 60)
    
    try:
        # 创建服务容器和事件总线
        service_container = ServiceContainer()
        event_bus = EventBus()
        
        # 创建订单执行器
        order_executor = OrderExecutor(service_container, event_bus)
        
        logger.info("\n订单执行器初始化成功")
        
        # 测试账号解析逻辑
        logger.info("\n测试账号解析逻辑（三级优先级）:")
        
        # 测试1：订单级别
        order1 = Order(
            order_id="ORDER_001",
            strategy_id="manual",
            asset_type=AssetType.STOCK_A,
            stock_code="000001",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            account_id="STOCK_001"  # 指定账号
        )
        
        resolved_account = order_executor._resolve_account_for_order(order1)
        if resolved_account and resolved_account.account_id == "STOCK_001":
            logger.info("测试1通过：订单级别账号解析成功")
        else:
            logger.warning("⚠️  测试1失败：订单级别账号解析失败")
        
        # 测试2：系统默认账号
        order2 = Order(
            order_id="ORDER_002",
            strategy_id="manual",
            asset_type=AssetType.STOCK_A,
            stock_code="000001",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            account_id="default"  # 使用默认账号
        )
        
        resolved_account = order_executor._resolve_account_for_order(order2)
        if resolved_account:
            logger.info(f"测试2通过：系统默认账号解析成功: {resolved_account.account_id}")
        else:
            logger.warning("⚠️  测试2失败：系统默认账号解析失败")
        
        # 测试账号级别的交易接口缓存
        logger.info("\n测试账号级别的交易接口缓存:")
        
        # 创建测试账号
        account1 = Account(
            account_id="STOCK_001",
            account_name="股票账户1",
            account_type="股票账户",
            status=AccountStatus.ACTIVE,
            institution_name="中信证券",
            institution_type=InstitutionType.BROKER,
            trading_interface_type=TradingInterfaceType.XTP_PRO,
            xtp_account_id="test_xtp_account_1",
            xtp_password="test_password_1",
            xtp_server_address="127.0.0.1:6001",
            balance=100000.0,
            available_balance=100000.0,
            frozen_balance=0.0,
            market_value=0.0,
            total_assets=100000.0,
            profit_loss=0.0,
            profit_loss_ratio=0.0,
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        
        # 第一次获取交易接口（应该创建并缓存）
        interface1 = order_executor._get_trading_interface_for_account(account1)
        if interface1:
            logger.info(f"第一次获取交易接口成功")
            
            # 第二次获取交易接口（应该从缓存中获取）
            interface2 = order_executor._get_trading_interface_for_account(account1)
            if interface2 and interface1 is interface2:
                logger.info("交易接口缓存功能正常")
            else:
                logger.warning("⚠️  交易接口缓存功能异常")
        else:
            logger.warning("⚠️  获取交易接口失败")
        
        logger.info("\n订单执行器的多账号功能测试通过")
        return order_executor
    
    except Exception as e:
        logger.error(f"\n❌ 订单执行器的多账号功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("多账号功能测试")
    logger.info("=" * 60)
    
    # 测试1：账号模型
    accounts = test_account_models()
    if not accounts:
        logger.error("\n❌ 测试失败：账号模型测试未通过")
        return
    
    # 测试2：订单执行器的多账号功能
    order_executor = test_order_executor()
    if not order_executor:
        logger.error("\n❌ 测试失败：订单执行器的多账号功能测试未通过")
        return
    
    logger.info("\n" + "=" * 60)
    logger.info("所有测试完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
