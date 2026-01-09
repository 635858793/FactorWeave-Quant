#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账户管理系统简化测试脚本

测试账户管理系统的核心功能，避免插件管理器初始化问题
"""

import sys
from loguru import logger
from datetime import datetime

# 添加项目路径
sys.path.insert(0, '.')

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>", level="INFO")


def test_database_schema():
    """测试数据库表创建"""
    logger.info("\n" + "=" * 80)
    logger.info("测试1: 数据库表创建")
    logger.info("=" * 80)
    
    try:
        from core.services.database_service import DatabaseService
        from core.containers import ServiceContainer
        
        # 创建服务容器
        service_container = ServiceContainer()
        
        # 创建数据库服务
        db_service = DatabaseService(service_container)
        
        logger.info("✅ 数据库服务创建成功")
        
        # 测试创建账户表
        create_accounts_table = """
        CREATE TABLE IF NOT EXISTS accounts (
            account_id VARCHAR(64) PRIMARY KEY,
            account_name VARCHAR(128) NOT NULL,
            account_type VARCHAR(32) NOT NULL,
            status VARCHAR(32) NOT NULL,
            balance DECIMAL(20, 4) NOT NULL DEFAULT 0,
            available_balance DECIMAL(20, 4) NOT NULL DEFAULT 0,
            frozen_balance DECIMAL(20, 4) NOT NULL DEFAULT 0,
            market_value DECIMAL(20, 4) NOT NULL DEFAULT 0,
            total_assets DECIMAL(20, 4) NOT NULL DEFAULT 0,
            profit_loss DECIMAL(20, 4) NOT NULL DEFAULT 0,
            profit_loss_ratio DECIMAL(10, 6) NOT NULL DEFAULT 0,
            create_time TIMESTAMP NOT NULL,
            update_time TIMESTAMP NOT NULL,
            user_id VARCHAR(64) NOT NULL DEFAULT 'system',
            trading_day VARCHAR(16) DEFAULT '',
            risk_level VARCHAR(32) DEFAULT 'normal',
            margin_ratio DECIMAL(10, 6) DEFAULT 0,
            maintenance_margin DECIMAL(20, 4) DEFAULT 0,
            metadata TEXT DEFAULT '{}',
            
            -- CTP交易接口配置
            ctp_broker_id VARCHAR(32) DEFAULT '',
            ctp_investor_id VARCHAR(32) DEFAULT '',
            ctp_password VARCHAR(128) DEFAULT '',
            ctp_trade_front VARCHAR(256) DEFAULT '',
            ctp_quote_front VARCHAR(256) DEFAULT '',
            ctp_app_id VARCHAR(64) DEFAULT '',
            ctp_auth_code VARCHAR(128) DEFAULT '',
            ctp_product_info VARCHAR(128) DEFAULT '',
            
            -- XTP交易接口配置
            xtp_account_id VARCHAR(32) DEFAULT '',
            xtp_password VARCHAR(128) DEFAULT '',
            xtp_server_address VARCHAR(256) DEFAULT '',
            
            INDEX idx_account_type (account_type),
            INDEX idx_status (status),
            INDEX idx_user_id (user_id),
            INDEX idx_update_time (update_time)
        )
        """
        
        db_service.execute_query(create_accounts_table)
        logger.info("✅ 账户表创建成功")
        
        # 测试创建持仓表
        create_positions_table = """
        CREATE TABLE IF NOT EXISTS positions (
            position_id VARCHAR(64) PRIMARY KEY,
            account_id VARCHAR(64) NOT NULL,
            asset_type VARCHAR(32) NOT NULL,
            stock_code VARCHAR(32) NOT NULL,
            stock_name VARCHAR(128) DEFAULT '',
            side VARCHAR(16) NOT NULL,
            quantity INT NOT NULL,
            available_quantity INT NOT NULL,
            open_price DECIMAL(20, 4) NOT NULL,
            current_price DECIMAL(20, 4) NOT NULL,
            market_value DECIMAL(20, 4) NOT NULL,
            cost_price DECIMAL(20, 4) NOT NULL,
            cost_value DECIMAL(20, 4) NOT NULL,
            profit_loss DECIMAL(20, 4) NOT NULL,
            profit_loss_ratio DECIMAL(10, 6) NOT NULL,
            open_time TIMESTAMP NOT NULL,
            update_time TIMESTAMP NOT NULL,
            commission DECIMAL(20, 4) DEFAULT 0,
            metadata TEXT DEFAULT '{}',
            
            INDEX idx_account_id (account_id),
            INDEX idx_asset_type (asset_type),
            INDEX idx_stock_code (stock_code),
            INDEX idx_update_time (update_time)
        )
        """
        
        db_service.execute_query(create_positions_table)
        logger.info("✅ 持仓表创建成功")
        
        # 测试创建资金信息表
        create_fund_infos_table = """
        CREATE TABLE IF NOT EXISTS fund_infos (
            account_id VARCHAR(64) PRIMARY KEY,
            total_balance DECIMAL(20, 4) NOT NULL,
            available_balance DECIMAL(20, 4) NOT NULL,
            frozen_balance DECIMAL(20, 4) NOT NULL,
            market_value DECIMAL(20, 4) NOT NULL,
            total_assets DECIMAL(20, 4) NOT NULL,
            profit_loss DECIMAL(20, 4) NOT NULL,
            profit_loss_ratio DECIMAL(10, 6) NOT NULL,
            margin_used DECIMAL(20, 4) NOT NULL,
            margin_available DECIMAL(20, 4) NOT NULL,
            maintenance_margin DECIMAL(20, 4) NOT NULL,
            update_time TIMESTAMP NOT NULL,
            metadata TEXT DEFAULT '{}',
            
            INDEX idx_update_time (update_time)
        )
        """
        
        db_service.execute_query(create_fund_infos_table)
        logger.info("✅ 资金信息表创建成功")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 数据库表创建测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_account_crud():
    """测试账户CRUD操作"""
    logger.info("\n" + "=" * 80)
    logger.info("测试2: 账户CRUD操作")
    logger.info("=" * 80)
    
    try:
        from core.services.database_service import DatabaseService
        from core.containers import ServiceContainer
        from core.trading.account_models import Account, AccountStatus
        
        # 创建服务容器
        service_container = ServiceContainer()
        
        # 创建数据库服务
        db_service = DatabaseService(service_container)
        
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
        
        # 插入账户
        account_data = account.to_dict()
        insert_sql = """
        INSERT INTO accounts (
            account_id, account_name, account_type, status,
            balance, available_balance, frozen_balance, market_value, total_assets,
            profit_loss, profit_loss_ratio, create_time, update_time,
            user_id, trading_day, risk_level, margin_ratio, maintenance_margin, metadata,
            ctp_broker_id, ctp_investor_id, ctp_password, ctp_trade_front, ctp_quote_front,
            ctp_app_id, ctp_auth_code, ctp_product_info,
            xtp_account_id, xtp_password, xtp_server_address
        ) VALUES (
            :account_id, :account_name, :account_type, :status,
            :balance, :available_balance, :frozen_balance, :market_value, :total_assets,
            :profit_loss, :profit_loss_ratio, :create_time, :update_time,
            :user_id, :trading_day, :risk_level, :margin_ratio, :maintenance_margin, :metadata,
            :ctp_broker_id, :ctp_investor_id, :ctp_password, :ctp_trade_front, :ctp_quote_front,
            :ctp_app_id, :ctp_auth_code, :ctp_product_info,
            :xtp_account_id, :xtp_password, :xtp_server_address
        )
        """
        
        db_service.execute_query(insert_sql, account_data)
        logger.info("✅ 账户插入成功")
        
        # 查询账户
        select_sql = "SELECT * FROM accounts WHERE account_id = :account_id"
        result = db_service.fetch_one(select_sql, {'account_id': 'TEST001'})
        
        if result:
            logger.info(f"✅ 账户查询成功: {result['account_name']}")
            logger.info(f"   - CTP Broker ID: {result['ctp_broker_id']}")
            logger.info(f"   - CTP Investor ID: {result['ctp_investor_id']}")
            logger.info(f"   - CTP Trade Front: {result['ctp_trade_front']}")
        else:
            logger.error("❌ 账户查询失败")
            return False
        
        # 更新账户
        update_sql = """
        UPDATE accounts SET
            balance = :balance,
            available_balance = :available_balance,
            profit_loss = :profit_loss,
            update_time = :update_time
        WHERE account_id = :account_id
        """
        
        update_data = {
            'account_id': 'TEST001',
            'balance': 95000.0,
            'available_balance': 95000.0,
            'profit_loss': -5000.0,
            'update_time': datetime.now()
        }
        
        db_service.execute_query(update_sql, update_data)
        logger.info("✅ 账户更新成功")
        
        # 删除账户
        delete_sql = "DELETE FROM accounts WHERE account_id = :account_id"
        db_service.execute_query(delete_sql, {'account_id': 'TEST001'})
        logger.info("✅ 账户删除成功")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 账户CRUD操作测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_position_crud():
    """测试持仓CRUD操作"""
    logger.info("\n" + "=" * 80)
    logger.info("测试3: 持仓CRUD操作")
    logger.info("=" * 80)
    
    try:
        from core.services.database_service import DatabaseService
        from core.containers import ServiceContainer
        from core.trading.account_models import Position, PositionSide
        from core.plugin_types import AssetType
        
        # 创建服务容器
        service_container = ServiceContainer()
        
        # 创建数据库服务
        db_service = DatabaseService(service_container)
        
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
        
        # 插入持仓
        position_data = position.to_dict()
        insert_sql = """
        INSERT INTO positions (
            position_id, account_id, asset_type, stock_code, stock_name, side,
            quantity, available_quantity, open_price, current_price, market_value,
            cost_price, cost_value, profit_loss, profit_loss_ratio,
            open_time, update_time, commission, metadata
        ) VALUES (
            :position_id, :account_id, :asset_type, :stock_code, :stock_name, :side,
            :quantity, :available_quantity, :open_price, :current_price, :market_value,
            :cost_price, :cost_value, :profit_loss, :profit_loss_ratio,
            :open_time, :update_time, :commission, :metadata
        )
        """
        
        db_service.execute_query(insert_sql, position_data)
        logger.info("✅ 持仓插入成功")
        
        # 查询持仓
        select_sql = "SELECT * FROM positions WHERE position_id = :position_id"
        result = db_service.fetch_one(select_sql, {'position_id': 'POS001'})
        
        if result:
            logger.info(f"✅ 持仓查询成功: {result['stock_name']}")
            logger.info(f"   - 股票代码: {result['stock_code']}")
            logger.info(f"   - 方向: {result['side']}")
            logger.info(f"   - 数量: {result['quantity']}")
            logger.info(f"   - 盈亏: {result['profit_loss']:.2f}")
        else:
            logger.error("❌ 持仓查询失败")
            return False
        
        # 删除持仓
        delete_sql = "DELETE FROM positions WHERE position_id = :position_id"
        db_service.execute_query(delete_sql, {'position_id': 'POS001'})
        logger.info("✅ 持仓删除成功")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 持仓CRUD操作测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def run_all_tests():
    """运行所有测试"""
    logger.info("\n" + "=" * 80)
    logger.info("开始账户管理系统简化测试")
    logger.info("=" * 80)
    
    results = []
    
    # 运行所有测试
    results.append(("数据库表创建", test_database_schema()))
    results.append(("账户CRUD操作", test_account_crud()))
    results.append(("持仓CRUD操作", test_position_crud()))
    
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
        logger.info("\n🎉 所有测试通过！账户管理系统数据库层功能正常。")
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
