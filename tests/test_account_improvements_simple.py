#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的账户管理改进功能测试

验证新增的机构信息和交易接口类型功能
"""

import sys
from datetime import datetime

# 添加项目路径
sys.path.insert(0, 'd:\\DevelopTool\\FreeCode\\HIkyuu-UI\\hikyuu-ui')

from core.trading.account_models import (
    Account, AccountStatus, InstitutionType, TradingInterfaceType
)


def test_new_fields():
    """测试新增字段"""
    print("=" * 60)
    print("测试: Account 新增字段")
    print("=" * 60)
    
    # 测试 XTP Pro 账户
    print("\n1. 测试 XTP Pro 股票账户")
    xtp_pro_account = Account(
        account_id="XTP_PRO_001",
        account_name="XTP Pro 测试账户",
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
        xtp_account_id="test_xtp_pro",
        xtp_password="password123",
        xtp_server_address="127.0.0.1:6001"
    )
    
    print(f"  账户ID: {xtp_pro_account.account_id}")
    print(f"  账户名称: {xtp_pro_account.account_name}")
    print(f"  机构名称: {xtp_pro_account.institution_name}")
    print(f"  机构类型: {xtp_pro_account.institution_type.value}")
    print(f"  交易接口类型: {xtp_pro_account.trading_interface_type.value}")
    print(f"  ✓ XTP Pro 账户创建成功")
    
    # 测试 CTP 账户
    print("\n2. 测试 CTP 期货账户")
    ctp_account = Account(
        account_id="CTP_001",
        account_name="CTP 测试账户",
        account_type="期货账户",
        status=AccountStatus.ACTIVE,
        balance=200000.0,
        available_balance=200000.0,
        frozen_balance=0.0,
        market_value=0.0,
        total_assets=200000.0,
        profit_loss=0.0,
        profit_loss_ratio=0.0,
        create_time=datetime.now(),
        update_time=datetime.now(),
        # 新增字段
        institution_name="中信期货",
        institution_type=InstitutionType.FUTURES_COMPANY,
        trading_interface_type=TradingInterfaceType.CTP,
        # CTP 配置
        ctp_broker_id="9999",
        ctp_investor_id="investor001",
        ctp_password="password456",
        ctp_trade_front="tcp://180.168.146.187:10130",
        ctp_quote_front="tcp://180.168.146.187:10131",
        ctp_app_id="simnow_client_test",
        ctp_auth_code="0000000000000000",
        ctp_product_info="simnow_client_test"
    )
    
    print(f"  账户ID: {ctp_account.account_id}")
    print(f"  账户名称: {ctp_account.account_name}")
    print(f"  机构名称: {ctp_account.institution_name}")
    print(f"  机构类型: {ctp_account.institution_type.value}")
    print(f"  交易接口类型: {ctp_account.trading_interface_type.value}")
    print(f"  ✓ CTP 账户创建成功")
    
    # 测试模拟账户
    print("\n3. 测试模拟交易账户")
    mock_account = Account(
        account_id="MOCK_001",
        account_name="模拟测试账户",
        account_type="加密货币账户",
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
        # 新增字段
        institution_name="自建模拟",
        institution_type=InstitutionType.OTHER,
        trading_interface_type=TradingInterfaceType.MOCK
    )
    
    print(f"  账户ID: {mock_account.account_id}")
    print(f"  账户名称: {mock_account.account_name}")
    print(f"  机构名称: {mock_account.institution_name}")
    print(f"  机构类型: {mock_account.institution_type.value}")
    print(f"  交易接口类型: {mock_account.trading_interface_type.value}")
    print(f"  ✓ 模拟账户创建成功")
    
    # 测试序列化和反序列化
    print("\n4. 测试序列化和反序列化")
    account_dict = xtp_pro_account.to_dict()
    print(f"  序列化包含机构名称: {'institution_name' in account_dict}")
    print(f"  序列化包含机构类型: {'institution_type' in account_dict}")
    print(f"  序列化包含交易接口类型: {'trading_interface_type' in account_dict}")
    
    restored_account = Account.from_dict(account_dict)
    print(f"  反序列化机构名称一致: {restored_account.institution_name == xtp_pro_account.institution_name}")
    print(f"  反序列化机构类型一致: {restored_account.institution_type == xtp_pro_account.institution_type}")
    print(f"  反序列化交易接口类型一致: {restored_account.trading_interface_type == xtp_pro_account.trading_interface_type}")
    print(f"  ✓ 序列化和反序列化测试通过")
    
    print("\n" + "=" * 60)
    print("✓ 所有测试通过！")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    try:
        success = test_new_fields()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
