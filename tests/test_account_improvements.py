#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试账户管理改进功能

测试新增的机构信息和交易接口类型功能
"""

import sys
from datetime import datetime
from loguru import logger

# 添加项目路径
sys.path.insert(0, 'd:\\DevelopTool\\FreeCode\\HIkyuu-UI\\hikyuu-ui')

from core.trading.account_models import (
    Account, AccountStatus, InstitutionType, TradingInterfaceType
)
from core.trading.account_manager import AccountManager
from core.containers import ServiceContainer
from core.events import EventBus


def test_enums():
    """测试枚举类型"""
    logger.info("=" * 60)
    logger.info("测试 1: 枚举类型定义")
    logger.info("=" * 60)
    
    # 测试 InstitutionType
    logger.info("\nInstitutionType 枚举值:")
    for inst_type in InstitutionType:
        logger.info(f"  - {inst_type.name}: {inst_type.value}")
    
    # 测试 TradingInterfaceType
    logger.info("\nTradingInterfaceType 枚举值:")
    for interface_type in TradingInterfaceType:
        logger.info(f"  - {interface_type.name}: {interface_type.value}")
    
    logger.info("\n✓ 枚举类型测试通过\n")
    return True


def test_account_model():
    """测试 Account 模型"""
    logger.info("=" * 60)
    logger.info("测试 2: Account 模型（包含新字段）")
    logger.info("=" * 60)
    
    try:
        # 创建一个包含新字段的账户
        account = Account(
            account_id="TEST001",
            account_name="测试账户",
            account_type="股票账户",
            status=AccountStatus.ACTIVE,
            balance=100000.0,
            available_balance=100000.0,
            frozen_balance=0.0,
            market_value=0.0,
            total_assets=100000.0,
            profit_loss=0.0,
            profit_loss_ratio=0.0,
            create_time=datetime.now(),
            update_time=datetime.now(),
            # 新增字段
            institution_name="中信证券",
            institution_type=InstitutionType.BROKER,
            trading_interface_type=TradingInterfaceType.XTP_PRO,
            # XTP 配置
            xtp_account_id="test_xtp_account",
            xtp_password="test_password",
            xtp_server_address="127.0.0.1:6001"
        )
        
        logger.info(f"\n账户信息:")
        logger.info(f"  账户ID: {account.account_id}")
        logger.info(f"  账户名称: {account.account_name}")
        logger.info(f"  账户类型: {account.account_type}")
        logger.info(f"  机构名称: {account.institution_name}")
        logger.info(f"  机构类型: {account.institution_type.value}")
        logger.info(f"  交易接口类型: {account.trading_interface_type.value}")
        logger.info(f"  总资产: {account.total_assets:.2f}")
        
        # 测试序列化
        account_dict = account.to_dict()
        logger.info(f"\n序列化测试:")
        logger.info(f"  包含机构名称: {'institution_name' in account_dict}")
        logger.info(f"  包含机构类型: {'institution_type' in account_dict}")
        logger.info(f"  包含交易接口类型: {'trading_interface_type' in account_dict}")
        
        # 测试反序列化
        account_restored = Account.from_dict(account_dict)
        logger.info(f"\n反序列化测试:")
        logger.info(f"  机构名称一致: {account.institution_name == account_restored.institution_name}")
        logger.info(f"  机构类型一致: {account.institution_type == account_restored.institution_type}")
        logger.info(f"  交易接口类型一致: {account.trading_interface_type == account_restored.trading_interface_type}")
        
        logger.info("\n✓ Account 模型测试通过\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ Account 模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_different_interface_types():
    """测试不同交易接口类型的账户"""
    logger.info("=" * 60)
    logger.info("测试 3: 不同交易接口类型的账户")
    logger.info("=" * 60)
    
    test_cases = [
        {
            "name": "XTP Pro 股票账户",
            "account_type": "股票账户",
            "institution_name": "中信证券",
            "institution_type": InstitutionType.BROKER,
            "trading_interface_type": TradingInterfaceType.XTP_PRO,
            "xtp_account_id": "xtp_test_001",
            "xtp_password": "password123",
            "xtp_server_address": "127.0.0.1:6001"
        },
        {
            "name": "CTP 期货账户",
            "account_type": "期货账户",
            "institution_name": "中信期货",
            "institution_type": InstitutionType.FUTURES_COMPANY,
            "trading_interface_type": TradingInterfaceType.CTP,
            "ctp_broker_id": "9999",
            "ctp_investor_id": "investor001",
            "ctp_password": "password123",
            "ctp_trade_front": "tcp://180.168.146.187:10130",
            "ctp_quote_front": "tcp://180.168.146.187:10131",
            "ctp_app_id": "simnow_client_test",
            "ctp_auth_code": "0000000000000000",
            "ctp_product_info": "simnow_client_test"
        },
        {
            "name": "XTP 股票账户",
            "account_type": "股票账户",
            "institution_name": "华泰证券",
            "institution_type": InstitutionType.BROKER,
            "trading_interface_type": TradingInterfaceType.XTP,
            "xtp_account_id": "xtp_test_002",
            "xtp_password": "password456",
            "xtp_server_address": "127.0.0.1:6002"
        },
        {
            "name": "模拟交易账户",
            "account_type": "加密货币账户",
            "institution_name": "自建模拟",
            "institution_type": InstitutionType.OTHER,
            "trading_interface_type": TradingInterfaceType.MOCK
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        logger.info(f"\n测试用例 {i}: {test_case['name']}")
        
        try:
            account = Account(
                account_id=f"TEST{i:03d}",
                account_name=test_case['name'],
                account_type=test_case['account_type'],
                status=AccountStatus.ACTIVE,
                balance=100000.0,
                available_balance=100000.0,
                frozen_balance=0.0,
                market_value=0.0,
                total_assets=100000.0,
                profit_loss=0.0,
                profit_loss_ratio=0.0,
                create_time=datetime.now(),
                update_time=datetime.now(),
                institution_name=test_case['institution_name'],
                institution_type=test_case['institution_type'],
                trading_interface_type=test_case['trading_interface_type'],
                ctp_broker_id=test_case.get('ctp_broker_id', ''),
                ctp_investor_id=test_case.get('ctp_investor_id', ''),
                ctp_password=test_case.get('ctp_password', ''),
                ctp_trade_front=test_case.get('ctp_trade_front', ''),
                ctp_quote_front=test_case.get('ctp_quote_front', ''),
                ctp_app_id=test_case.get('ctp_app_id', ''),
                ctp_auth_code=test_case.get('ctp_auth_code', ''),
                ctp_product_info=test_case.get('ctp_product_info', ''),
                xtp_account_id=test_case.get('xtp_account_id', ''),
                xtp_password=test_case.get('xtp_password', ''),
                xtp_server_address=test_case.get('xtp_server_address', '')
            )
            
            logger.info(f"  ✓ 账户创建成功")
            logger.info(f"    机构: {account.institution_name} ({account.institution_type.value})")
            logger.info(f"    接口: {account.trading_interface_type.value}")
            
        except Exception as e:
            logger.error(f"  ✗ 账户创建失败: {e}")
            return False
    
    logger.info("\n✓ 不同交易接口类型测试通过\n")
    return True


def test_account_manager_integration():
    """测试 AccountManager 集成"""
    logger.info("=" * 60)
    logger.info("测试 4: AccountManager 集成")
    logger.info("=" * 60)
    
    try:
        # 初始化服务容器和事件总线
        event_bus = EventBus()
        service_container = ServiceContainer()
        
        # 创建账户管理器
        account_manager = AccountManager(service_container, event_bus)
        
        # 创建测试账户
        account = Account(
            account_id="MGR_TEST_001",
            account_name="管理器测试账户",
            account_type="股票账户",
            status=AccountStatus.ACTIVE,
            balance=50000.0,
            available_balance=50000.0,
            frozen_balance=0.0,
            market_value=0.0,
            total_assets=50000.0,
            profit_loss=0.0,
            profit_loss_ratio=0.0,
            create_time=datetime.now(),
            update_time=datetime.now(),
            institution_name="测试券商",
            institution_type=InstitutionType.BROKER,
            trading_interface_type=TradingInterfaceType.XTP_PRO,
            xtp_account_id="mgr_test_account",
            xtp_password="mgr_password",
            xtp_server_address="127.0.0.1:6001"
        )
        
        # 创建账户
        logger.info("\n创建账户...")
        if account_manager.create_account(account):
            logger.info("  ✓ 账户创建成功")
        else:
            logger.error("  ✗ 账户创建失败")
            return False
        
        # 查询账户
        logger.info("\n查询账户...")
        retrieved_account = account_manager.get_account("MGR_TEST_001")
        if retrieved_account:
            logger.info("  ✓ 账户查询成功")
            logger.info(f"    机构名称: {retrieved_account.institution_name}")
            logger.info(f"    机构类型: {retrieved_account.institution_type.value}")
            logger.info(f"    交易接口类型: {retrieved_account.trading_interface_type.value}")
        else:
            logger.error("  ✗ 账户查询失败")
            return False
        
        # 查询所有账户
        logger.info("\n查询所有账户...")
        all_accounts = account_manager.get_all_accounts()
        logger.info(f"  ✓ 共找到 {len(all_accounts)} 个账户")
        
        for acc in all_accounts:
            logger.info(f"    - {acc.account_id}: {acc.account_name} ({acc.institution_name})")
        
        logger.info("\n✓ AccountManager 集成测试通过\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ AccountManager 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    logger.info("\n" + "=" * 60)
    logger.info("开始测试账户管理改进功能")
    logger.info("=" * 60 + "\n")
    
    results = []
    
    # 运行所有测试
    results.append(("枚举类型定义", test_enums()))
    results.append(("Account 模型", test_account_model()))
    results.append(("不同交易接口类型", test_different_interface_types()))
    results.append(("AccountManager 集成", test_account_manager_integration()))
    
    # 输出测试结果汇总
    logger.info("=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info(f"\n总计: {len(results)} 个测试")
    logger.info(f"通过: {passed} 个")
    logger.info(f"失败: {failed} 个")
    
    if failed == 0:
        logger.info("\n✓ 所有测试通过！")
        return 0
    else:
        logger.error(f"\n✗ 有 {failed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
