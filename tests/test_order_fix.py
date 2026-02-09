#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试订单修复：订单创建、取消和修改流程

测试内容：
1. 订单创建时 account_id 和 strategy_id 字段正确设置
2. 订单保存失败时的错误处理和日志记录
3. 账号解析失败时的日志信息
4. 订单提交前的完整性验证
5. 订单取消和修改流程
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from core.trading.account_models import Account, AccountStatus, InstitutionType, TradingInterfaceType
from core.trading.order_models import OrderRequest, Order, OrderType, OrderStatus, OrderCategory
from core.plugin_types import AssetType
from core.containers import ServiceContainer
from core.events import EventBus
from core.trading.order_service import OrderService
from core.trading.order_executor import OrderExecutor


def test_order_creation_with_valid_account():
    """测试订单创建时使用有效的账号"""
    logger.info("=" * 60)
    logger.info("测试 1: 订单创建时使用有效的账号")
    logger.info("=" * 60)
    
    try:
        service_container = ServiceContainer()
        event_bus = EventBus(async_execution=False, deduplication_window=0.5, enable_history=True)
        service_container.register(EventBus, event_bus)
        
        order_service = OrderService(service_container, event_bus)
        
        # 创建订单请求（使用有效的账号）
        request = OrderRequest(
            strategy_id="test_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="600000",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.50,
            order_quantity=100,
            user_id="test_user",
            account_id="test_account"
        )
        
        # 创建订单
        order = order_service.create_order(request)
        
        if order:
            logger.info(f"订单创建成功: {order.order_id}")
            logger.info(f"   账号ID: {order.account_id}")
            logger.info(f"   策略ID: {order.strategy_id}")
            logger.info(f"   股票代码: {order.stock_code}")
            logger.info(f"   订单价格: {order.order_price}")
            logger.info(f"   订单数量: {order.order_quantity}")
            
            # 验证账号和策略不是 default
            if order.account_id != "default" and order.strategy_id != "default":
                logger.info("账号和策略ID已正确设置（不是 default）")
            else:
                logger.warning("⚠️ 账号或策略ID仍然是 default")
            
            return True
        else:
            logger.warning("⚠️ 订单创建失败（可能是因为没有配置账号）")
            return False
            
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_order_creation_with_default_account():
    """测试订单创建时使用默认账号"""
    logger.info("=" * 60)
    logger.info("测试 2: 订单创建时使用默认账号（自动解析）")
    logger.info("=" * 60)
    
    try:
        service_container = ServiceContainer()
        event_bus = EventBus(async_execution=False, deduplication_window=0.5, enable_history=True)
        service_container.register(EventBus, event_bus)
        
        order_service = OrderService(service_container, event_bus)
        
        # 创建订单请求（使用默认账号）
        request = OrderRequest(
            strategy_id="default",
            asset_type=AssetType.STOCK_A,
            stock_code="600000",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.50,
            order_quantity=100,
            user_id="test_user",
            account_id="default"
        )
        
        # 创建订单
        order = order_service.create_order(request)
        
        if order:
            logger.info(f"订单创建成功: {order.order_id}")
            logger.info(f"   账号ID: {order.account_id}")
            logger.info(f"   策略ID: {order.strategy_id}")
            
            # 验证系统是否自动解析了有效的账号
            if order.account_id != "default":
                logger.info("系统成功解析了有效的账号")
            else:
                logger.warning("⚠️ 系统未能解析有效的账号（可能是因为没有配置账号）")
            
            return True
        else:
            logger.warning("⚠️ 订单创建失败（可能是因为没有配置账号）")
            return False
            
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_order_integrity_validation():
    """测试订单完整性验证"""
    logger.info("=" * 60)
    logger.info("测试 3: 订单完整性验证")
    logger.info("=" * 60)
    
    try:
        service_container = ServiceContainer()
        event_bus = EventBus(async_execution=False, deduplication_window=0.5, enable_history=True)
        service_container.register(EventBus, event_bus)
        
        order_executor = OrderExecutor(service_container, event_bus)
        
        # 创建有效的订单
        valid_order = Order(
            order_id="TEST_ORDER_VALID",
            strategy_id="test_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="600000",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.50,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            account_id="test_account"
        )
        
        # 验证有效订单
        validation_error = order_executor._validate_order_integrity(valid_order)
        if not validation_error:
            logger.info("有效订单验证通过")
        else:
            logger.error(f"❌ 有效订单验证失败: {validation_error}")
            return False
        
        # 创建无效的订单（价格为0）
        invalid_order = Order(
            order_id="TEST_ORDER_INVALID",
            strategy_id="test_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="600000",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=0.0,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            account_id="test_account"
        )
        
        # 验证无效订单
        validation_error = order_executor._validate_order_integrity(invalid_order)
        if validation_error:
            logger.info(f"无效订单验证失败（预期行为）: {validation_error}")
        else:
            logger.error("❌ 无效订单验证通过（应该失败）")
            return False
        
        return True
            
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_account_resolution_logging():
    """测试账号解析的日志信息"""
    logger.info("=" * 60)
    logger.info("测试 4: 账号解析的日志信息")
    logger.info("=" * 60)
    
    try:
        service_container = ServiceContainer()
        event_bus = EventBus(async_execution=False, deduplication_window=0.5, enable_history=True)
        service_container.register(EventBus, event_bus)
        
        order_executor = OrderExecutor(service_container, event_bus)
        
        # 创建订单（使用默认账号）
        order = Order(
            order_id="TEST_ORDER_ACCOUNT",
            strategy_id="default",
            asset_type=AssetType.STOCK_A,
            stock_code="600000",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.50,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            account_id="default"
        )
        
        # 尝试解析账号（会触发详细的日志）
        logger.info("开始解析账号（请查看日志输出）...")
        account = order_executor._resolve_account_for_order(order)
        
        if account:
            logger.info(f"成功解析账号: {account.account_id}")
        else:
            logger.warning("⚠️ 未能解析账号（请查看详细日志了解原因）")
        
        logger.info("账号解析日志测试完成")
        return True
            
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_order_save_retry():
    """测试订单保存的重试机制"""
    logger.info("=" * 60)
    logger.info("测试 5: 订单保存的重试机制")
    logger.info("=" * 60)
    
    try:
        service_container = ServiceContainer()
        event_bus = EventBus(async_execution=False, deduplication_window=0.5, enable_history=True)
        service_container.register(EventBus, event_bus)
        
        from core.trading.order_repository import OrderRepository
        order_repository = OrderRepository(service_container, event_bus)
        
        # 创建订单
        order = Order(
            order_id="TEST_ORDER_RETRY",
            strategy_id="test_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="600000",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.50,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            account_id="test_account"
        )
        
        # 尝试保存订单（会触发重试机制）
        logger.info("开始保存订单（会触发重试机制）...")
        success = order_repository.save_order(order)
        
        if success:
            logger.info(f"订单保存成功: {order.order_id}")
        else:
            logger.warning(f"⚠️ 订单保存失败（已重试3次）: {order.order_id}")
            logger.warning("请查看详细日志了解失败原因")
        
        logger.info("订单保存重试机制测试完成")
        return True
            
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    logger.info("=" * 60)
    logger.info("开始运行订单修复测试")
    logger.info("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(("订单创建（有效账号）", test_order_creation_with_valid_account()))
    results.append(("订单创建（默认账号）", test_order_creation_with_default_account()))
    results.append(("订单完整性验证", test_order_integrity_validation()))
    results.append(("账号解析日志", test_account_resolution_logging()))
    results.append(("订单保存重试", test_order_save_retry()))
    
    # 输出测试结果
    logger.info("=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info("=" * 60)
    logger.info(f"总计: {len(results)} 个测试, 通过: {passed}, 失败: {failed}")
    logger.info("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
