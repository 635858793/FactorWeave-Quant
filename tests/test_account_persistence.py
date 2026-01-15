#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试账号持久化功能

验证账号是否能够正确保存到数据库，并在重启后恢复
"""

import sys
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from loguru import logger

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 启用调试日志
logger.remove()
logger.add(sys.stderr, level='DEBUG')

from core.trading.account_models import Account, AccountStatus, InstitutionType, TradingInterfaceType
from core.trading.account_manager import AccountManager
from core.containers import ServiceContainer
from core.events import EventBus
from core.services.database_service import DatabaseService


def test_account_persistence():
    """测试账号持久化功能"""
    
    print("=" * 80)
    print("测试账号持久化功能")
    print("=" * 80)
    
    # 初始化服务
    event_bus = EventBus()
    service_container = ServiceContainer()
    
    # 注册服务
    service_container.register(EventBus, event_bus)
    service_container.register(DatabaseService)
    
    # 创建账户管理器（会自动创建 AccountRepository）
    account_manager = AccountManager(service_container, event_bus)
    
    # 步骤1：创建测试账号
    print("\n[步骤1] 创建测试账号...")
    import time
    unique_id = str(int(time.time()))
    test_account = Account(
        account_id=f"test_account_{unique_id}",
        account_name=f"测试账号{unique_id}",
        account_type="stock",
        status=AccountStatus.ACTIVE,
        balance=1000000.0,
        available_balance=950000.0,
        frozen_balance=50000.0,
        market_value=0.0,
        total_assets=1000000.0,
        profit_loss=0.0,
        profit_loss_ratio=0.0,
        create_time=datetime.now(),
        update_time=datetime.now(),
        user_id="test_user",
        institution_name="测试券商",
        institution_type=InstitutionType.BROKER,
        trading_interface_type=TradingInterfaceType.MOCK,
        metadata={"test_key": "test_value", "description": "这是一个测试账号"}
    )
    
    print(f"  账号ID: {test_account.account_id}")
    print(f"  账号名称: {test_account.account_name}")
    print(f"  机构名称: {test_account.institution_name}")
    print(f"  交易接口: {test_account.trading_interface_type.value}")
    print(f"  余额: {test_account.balance}")
    print(f"  元数据: {test_account.metadata}")
    
    # 步骤2：保存账号到数据库
    print("\n[步骤2] 保存账号到数据库...")
    success = account_manager.create_account(test_account)
    
    if not success:
        print("  ✗ 账号保存失败！")
        return False
    
    print("  ✓ 账号保存成功")
    
    # 步骤3：直接查询数据库验证数据存在
    print("\n[步骤3] 直接查询数据库验证数据存在...")
    db_path = Path(project_root) / "data" / "tradeaccount.sqlite"
    
    if not db_path.exists():
        print(f"  ✗ 数据库文件不存在: {db_path}")
        return False
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("SELECT account_id, account_name, institution_name, trading_interface_type, balance FROM accounts WHERE account_id = ?", 
                   (test_account.account_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row is None:
        print("  ✗ 数据库中未找到账号记录！")
        return False
    
    print(f"  ✓ 数据库中找到账号记录:")
    print(f"    - account_id: {row[0]}")
    print(f"    - account_name: {row[1]}")
    print(f"    - institution_name: {row[2]}")
    print(f"    - trading_interface_type: {row[3]}")
    print(f"    - balance: {row[4]}")
    
    # 步骤4：清除内存中的账号缓存
    print("\n[步骤4] 清除内存中的账号缓存...")
    account_manager._accounts.clear()
    print("  ✓ 内存缓存已清除")
    
    # 步骤5：重新加载账号（使用新的 AccountManager 实例）
    print("\n[步骤5] 重新加载账号...")
    # 创建新的账户管理器来模拟系统重启
    new_account_manager = AccountManager(service_container, event_bus)
    print("  ✓ 从数据库重新加载账号成功")
    
    # 步骤6：验证重新加载的账号数据
    print("\n[步骤6] 验证重新加载的账号数据...")
    
    # 调试：打印所有加载的账号
    print(f"  当前内存中的账号数量: {len(new_account_manager._accounts)}")
    print(f"  当前内存中的账号ID列表: {list(new_account_manager._accounts.keys())}")
    
    # 直接查询特定账号
    from core.trading.account_models import AccountQuery
    query = AccountQuery(account_id=test_account.account_id)
    accounts = account_manager.repository.get_accounts(query)
    print(f"  直接查询特定账号: 找到 {len(accounts)} 个账号")
    if accounts:
        print(f"  找到的账号ID: {accounts[0].account_id}")
    
    loaded_account = new_account_manager.get_account(test_account.account_id)
    
    if loaded_account is None:
        print("  ✗ 重新加载后未找到账号！")
        return False
    
    print(f"  ✓ 重新加载的账号:")
    print(f"    - account_id: {loaded_account.account_id}")
    print(f"    - account_name: {loaded_account.account_name}")
    print(f"    - institution_name: {loaded_account.institution_name}")
    print(f"    - trading_interface_type: {loaded_account.trading_interface_type.value}")
    print(f"    - balance: {loaded_account.balance}")
    print(f"    - metadata: {loaded_account.metadata}")
    
    # 验证关键字段
    errors = []
    if loaded_account.account_id != test_account.account_id:
        errors.append(f"account_id 不匹配: {loaded_account.account_id} != {test_account.account_id}")
    if loaded_account.account_name != test_account.account_name:
        errors.append(f"account_name 不匹配: {loaded_account.account_name} != {test_account.account_name}")
    if loaded_account.institution_name != test_account.institution_name:
        errors.append(f"institution_name 不匹配: {loaded_account.institution_name} != {test_account.institution_name}")
    if loaded_account.trading_interface_type != test_account.trading_interface_type:
        errors.append(f"trading_interface_type 不匹配: {loaded_account.trading_interface_type} != {test_account.trading_interface_type}")
    if loaded_account.balance != test_account.balance:
        errors.append(f"balance 不匹配: {loaded_account.balance} != {test_account.balance}")
    if loaded_account.metadata != test_account.metadata:
        errors.append(f"metadata 不匹配: {loaded_account.metadata} != {test_account.metadata}")
    
    if errors:
        print("\n  ✗ 数据验证失败:")
        for error in errors:
            print(f"    - {error}")
        return False
    
    print("\n  ✓ 所有字段验证通过")
    
    # 步骤7：清理测试数据
    print("\n[步骤7] 清理测试数据...")
    account_manager.delete_account(test_account.account_id)
    print("  ✓ 测试账号已删除")
    
    print("\n" + "=" * 80)
    print("✓ 账号持久化功能测试通过！")
    print("=" * 80)
    return True


if __name__ == "__main__":
    try:
        success = test_account_persistence()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
