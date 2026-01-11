#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账户管理系统测试脚本

测试账户管理系统的完整功能，包括数据持久化、UI集成等
"""

import sys
from loguru import logger
from datetime import datetime

# 添加项目路径
sys.path.insert(0, '.')

from core.containers import get_service_container, ServiceContainer
from core.events import get_event_bus, EventBus
from core.trading.account_models import (
    Account, Position, FundInfo, AccountQuery, PositionQuery,
    AccountStatus, PositionSide
)
from core.trading.account_repository import AccountRepository
from core.trading.account_manager import AccountManager
from core.plugin_types import AssetType


def test_account_repository():
    """测试账户仓储"""
    logger.info("\n" + "=" * 80)
    logger.info("测试1: AccountRepository数据持久化")
    logger.info("=" * 80)
    
    try:
        # 获取服务容器和事件总线
        logger.info("正在获取服务容器...")
        service_container = get_service_container()
        logger.info("服务容器获取成功")
        
        logger.info("正在获取事件总线...")
        event_bus = get_event_bus()
        logger.info("事件总线获取成功")
        
        # 创建账户仓储
        logger.info("正在创建AccountRepository...")
        repository = AccountRepository(service_container, event_bus)
        logger.info("AccountRepository创建成功")
        
        # 创建测试账户
        account = Account(
            account_id="TEST001",
            account_name="测试账户",
            account_type="期货账户",
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
            ctp_broker_id="9999",
            ctp_investor_id="test_investor",
            ctp_password="test_password",
            ctp_trade_front="tcp://180.168.146.187:10130",
            ctp_quote_front="tcp://180.168.146.187:10131",
            ctp_app_id="simnow_client_test",
            ctp_auth_code="0000000000000000",
            ctp_product_info="simnow_client_test"
        )
        
        # 保存账户
        if repository.save_account(account):
            logger.info("✅ 账户保存成功")
        else:
            logger.error("❌ 账户保存失败")
            return False
        
        # 读取账户
        retrieved_account = repository.get_account("TEST001")
        if retrieved_account:
            logger.info(f"✅ 账户读取成功: {retrieved_account.account_name}")
            logger.info(f"   - CTP Broker ID: {retrieved_account.ctp_broker_id}")
            logger.info(f"   - CTP Investor ID: {retrieved_account.ctp_investor_id}")
        else:
            logger.error("❌ 账户读取失败")
            return False
        
        # 创建测试持仓
        position = Position(
            position_id="POS001",
            account_id="TEST001",
            asset_type=AssetType.FUTURES,
            stock_code="IF2401",
            stock_name="沪深300期货",
            side=PositionSide.LONG,
            quantity=10,
            available_quantity=10,
            open_price=3500.0,
            current_price=3550.0,
            market_value=35500.0,
            cost_price=3500.0,
            cost_value=35000.0,
            profit_loss=500.0,
            profit_loss_ratio=0.0143,
            open_time=datetime.now(),
            update_time=datetime.now()
        )
        
        # 保存持仓
        if repository.save_position(position):
            logger.info("✅ 持仓保存成功")
        else:
            logger.error("❌ 持仓保存失败")
            return False
        
        # 创建测试资金信息
        fund_info = FundInfo(
            account_id="TEST001",
            total_balance=100000.0,
            available_balance=65000.0,
            frozen_balance=35000.0,
            market_value=35500.0,
            total_assets=135500.0,
            profit_loss=500.0,
            profit_loss_ratio=0.0037,
            margin_used=35000.0,
            margin_available=65000.0,
            maintenance_margin=30000.0,
            update_time=datetime.now()
        )
        
        # 保存资金信息
        if repository.save_fund_info(fund_info):
            logger.info("✅ 资金信息保存成功")
        else:
            logger.error("❌ 资金信息保存失败")
            return False
        
        # 查询账户列表
        query = AccountQuery(limit=10, sort_by="create_time", sort_order="desc")
        accounts = repository.get_accounts(query)
        logger.info(f"✅ 查询到 {len(accounts)} 个账户")
        
        # 查询持仓列表
        position_query = PositionQuery(account_id="TEST001")
        positions = repository.get_positions(position_query)
        logger.info(f"✅ 查询到 {len(positions)} 个持仓")
        
        # 获取资金信息
        retrieved_fund_info = repository.get_fund_info("TEST001")
        if retrieved_fund_info:
            logger.info(f"✅ 资金信息读取成功: 总资产 {retrieved_fund_info.total_assets:.2f}")
        else:
            logger.error("❌ 资金信息读取失败")
            return False
        
        # 清理测试数据
        repository.delete_position("POS001")
        repository.delete_account("TEST001")
        logger.info("✅ 测试数据清理完成")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ AccountRepository测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_account_manager():
    """测试账户管理器"""
    logger.info("\n" + "=" * 80)
    logger.info("测试2: AccountManager与Repository集成")
    logger.info("=" * 80)
    
    try:
        # 获取服务容器和事件总线
        service_container = get_service_container()
        event_bus = get_event_bus()
        
        # 创建账户管理器
        manager = AccountManager(service_container, event_bus)
        
        # 创建测试账户（股票账户，使用XTP配置）
        stock_account = Account(
            account_id="STOCK001",
            account_name="股票测试账户",
            account_type="股票账户",
            status=AccountStatus.ACTIVE,
            balance=500000.0,
            available_balance=500000.0,
            frozen_balance=0.0,
            market_value=0.0,
            total_assets=500000.0,
            profit_loss=0.0,
            profit_loss_ratio=0.0,
            create_time=datetime.now(),
            update_time=datetime.now(),
            xtp_account_id="stock_test_account",
            xtp_password="stock_test_password",
            xtp_server_address="120.27.0.1:6001"
        )
        
        # 通过管理器创建账户
        if manager.create_account(stock_account):
            logger.info("✅ 通过AccountManager创建账户成功")
        else:
            logger.error("❌ 通过AccountManager创建账户失败")
            return False
        
        # 通过管理器获取账户
        retrieved_account = manager.get_account("STOCK001")
        if retrieved_account:
            logger.info(f"✅ 通过AccountManager获取账户成功: {retrieved_account.account_name}")
            logger.info(f"   - XTP Account ID: {retrieved_account.xtp_account_id}")
            logger.info(f"   - XTP Server: {retrieved_account.xtp_server_address}")
        else:
            logger.error("❌ 通过AccountManager获取账户失败")
            return False
        
        # 更新账户
        stock_account.balance = 480000.0
        stock_account.available_balance = 480000.0
        stock_account.profit_loss = -20000.0
        stock_account.profit_loss_ratio = -0.04
        stock_account.update_time = datetime.now()
        
        if manager.update_account(stock_account):
            logger.info("✅ 通过AccountManager更新账户成功")
        else:
            logger.error("❌ 通过AccountManager更新账户失败")
            return False
        
        # 查询账户列表
        query = AccountQuery(account_type="股票账户")
        accounts = manager.query_accounts(query)
        logger.info(f"✅ 查询到 {len(accounts)} 个股票账户")
        
        # 创建测试持仓
        position = Position(
            position_id="STOCK_POS001",
            account_id="STOCK001",
            asset_type=AssetType.STOCK,
            stock_code="600000",
            stock_name="浦发银行",
            side=PositionSide.LONG,
            quantity=1000,
            available_quantity=1000,
            open_price=10.0,
            current_price=10.5,
            market_value=10500.0,
            cost_price=10.0,
            cost_value=10000.0,
            profit_loss=500.0,
            profit_loss_ratio=0.05,
            open_time=datetime.now(),
            update_time=datetime.now()
        )
        
        # 通过管理器创建持仓
        if manager.create_position(position):
            logger.info("✅ 通过AccountManager创建持仓成功")
        else:
            logger.error("❌ 通过AccountManager创建持仓失败")
            return False
        
        # 更新资金信息
        fund_info = FundInfo(
            account_id="STOCK001",
            total_balance=480000.0,
            available_balance=469500.0,
            frozen_balance=10500.0,
            market_value=10500.0,
            total_assets=490500.0,
            profit_loss=-9500.0,
            profit_loss_ratio=-0.0194,
            margin_used=0.0,
            margin_available=480000.0,
            maintenance_margin=0.0,
            update_time=datetime.now()
        )
        
        if manager.update_fund_info(fund_info):
            logger.info("✅ 通过AccountManager更新资金信息成功")
        else:
            logger.error("❌ 通过AccountManager更新资金信息失败")
            return False
        
        # 获取账户汇总信息
        summary = manager.get_account_summary("STOCK001")
        if summary:
            logger.info(f"✅ 获取账户汇总成功:")
            logger.info(f"   - 账户名称: {summary['account']['account_name']}")
            logger.info(f"   - 持仓数量: {summary['position_count']}")
            logger.info(f"   - 总市值: {summary['total_market_value']:.2f}")
            logger.info(f"   - 总盈亏: {summary['total_profit_loss']:.2f}")
        else:
            logger.error("❌ 获取账户汇总失败")
            return False
        
        # 清理测试数据
        manager.delete_position("STOCK_POS001")
        manager.delete_account("STOCK001")
        logger.info("✅ 测试数据清理完成")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ AccountManager测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_service_container_integration():
    """测试服务容器集成"""
    logger.info("\n" + "=" * 80)
    logger.info("测试3: 服务容器集成")
    logger.info("=" * 80)
    
    try:
        # 获取服务容器
        service_container = get_service_container()
        
        # 检查AccountRepository是否已注册
        from core.trading.account_repository import AccountRepository
        if service_container.is_registered(AccountRepository):
            logger.info("✅ AccountRepository已注册到服务容器")
        else:
            logger.error("❌ AccountRepository未注册到服务容器")
            return False
        
        # 检查AccountManager是否已注册
        from core.trading.account_manager import AccountManager
        if service_container.is_registered(AccountManager):
            logger.info("✅ AccountManager已注册到服务容器")
        else:
            logger.error("❌ AccountManager未注册到服务容器")
            return False
        
        # 尝试解析服务
        try:
            repository = service_container.resolve(AccountRepository)
            logger.info("✅ 成功解析AccountRepository服务")
        except Exception as e:
            logger.error(f"❌ 解析AccountRepository服务失败: {e}")
            return False
        
        try:
            manager = service_container.resolve(AccountManager)
            logger.info("✅ 成功解析AccountManager服务")
        except Exception as e:
            logger.error(f"❌ 解析AccountManager服务失败: {e}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 服务容器集成测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def run_all_tests():
    """运行所有测试"""
    logger.info("\n" + "=" * 80)
    logger.info("开始账户管理系统综合测试")
    logger.info("=" * 80)
    
    results = []
    
    # 运行所有测试
    results.append(("AccountRepository数据持久化", test_account_repository()))
    results.append(("AccountManager与Repository集成", test_account_manager()))
    results.append(("服务容器集成", test_service_container_integration()))
    
    # 输出测试结果
    logger.info("\n" + "=" * 80)
    logger.info("测试结果汇总")
    logger.info("=" * 80)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info(f"\n总计: {len(results)} 个测试")
    logger.info(f"通过: {passed} 个")
    logger.info(f"失败: {failed} 个")
    
    if failed == 0:
        logger.info("\n🎉 所有测试通过！账户管理系统功能完整。")
    else:
        logger.warning(f"\n⚠️  有 {failed} 个测试失败，请检查日志。")
    
    return failed == 0


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"测试运行失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
