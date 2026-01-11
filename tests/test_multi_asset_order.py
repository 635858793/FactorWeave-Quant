"""
测试多资产类型支持功能
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime
from core.plugin_types import AssetType
from core.trading.order_models import Order, OrderType, OrderCategory, OrderStatus, OrderQuery
from core.trading.order_repository import OrderRepository
from core.trading.order_executor import OrderExecutor
from core.trading.order_validator import OrderValidator
from core.containers import ServiceContainer
from core.events import EventBus
from loguru import logger


def test_multi_asset_order_creation():
    """测试多资产类型订单创建"""
    logger.info("=" * 80)
    logger.info("【测试1】多资产类型订单创建")
    logger.info("=" * 80)
    
    # 初始化服务
    service_container = ServiceContainer()
    event_bus = EventBus()
    
    repository = OrderRepository(service_container, event_bus)
    
    # 测试用例：(资产类型, 资产代码, 资产名称)
    test_cases = [
        (AssetType.STOCK_A, "000001", "平安银行", "股票"),
        (AssetType.FUTURES, "IF2403", "沪深300期货", "期货"),
        (AssetType.OPTION, "10004123", "50ETF购1月2800A", "期权"),
        (AssetType.CRYPTO, "BTC-USD", "比特币", "加密货币"),
        (AssetType.FOREX, "EURUSD", "欧元美元", "外汇"),
        (AssetType.FUND, "519983", "长信量化中小盘", "基金"),
    ]
    
    logger.info("\n📝 创建订单测试：\n")
    
    for asset_type, code, name, type_name in test_cases:
        logger.info(f"\n{'—' * 40}")
        logger.info(f"🔍 测试创建: {name} ({code}) [{type_name}]")
        logger.info(f"{'—' * 40}")
        
        try:
            # 创建订单
            order = Order(
                order_id=repository.generate_order_id(),
                strategy_id="test_strategy",
                asset_type=asset_type,
                stock_code=code,
                order_type=OrderType.BUY,
                order_category=OrderCategory.LIMIT,
                order_price=10.0,
                order_quantity=100,
                order_status=OrderStatus.PENDING,
                create_time=datetime.now(),
                update_time=datetime.now(),
                user_id="test_user",
                account_id="test_account"
            )
            
            # 保存订单
            success = repository.save_order(order)
            
            if success:
                logger.success(f"✅ 订单创建成功: {order.order_id}")
                logger.info(f"   资产类型: {order.asset_type.value}")
                logger.info(f"   资产代码: {order.stock_code}")
                logger.info(f"   订单价格: {order.order_price}")
                logger.info(f"   订单数量: {order.order_quantity}")
            else:
                logger.error(f"❌ 订单创建失败: {code}")
                
        except Exception as e:
            logger.error(f"❌ 订单创建异常: {code} - {e}")
    
    logger.info("\n" + "=" * 80)


def test_multi_asset_order_query():
    """测试多资产类型订单查询"""
    logger.info("\n" + "=" * 80)
    logger.info("【测试2】多资产类型订单查询")
    logger.info("=" * 80)
    
    # 初始化服务
    service_container = ServiceContainer()
    event_bus = EventBus()
    
    repository = OrderRepository(service_container, event_bus)
    
    # 测试用例
    test_cases = [
        ("查询所有订单", OrderQuery()),
        ("查询股票订单", OrderQuery(asset_type=AssetType.STOCK_A)),
        ("查询期货订单", OrderQuery(asset_type=AssetType.FUTURES)),
        ("查询期权订单", OrderQuery(asset_type=AssetType.OPTION)),
    ]
    
    logger.info("\n📊 订单查询测试：\n")
    
    for query_name, query in test_cases:
        logger.info(f"\n{'—' * 40}")
        logger.info(f"🔍 测试查询: {query_name}")
        logger.info(f"{'—' * 40}")
        
        try:
            # 查询订单
            orders = repository.query_orders(query)
            
            logger.success(f"✅ 查询成功: 返回 {len(orders)} 条记录")
            
            for order in orders[:3]:  # 只显示前3条
                logger.info(f"   - {order.order_id}: {order.asset_type.value} {order.stock_code}")
                
        except Exception as e:
            logger.error(f"❌ 查询失败: {query_name} - {e}")
    
    logger.info("\n" + "=" * 80)


def test_multi_asset_order_validation():
    """测试多资产类型订单验证"""
    logger.info("\n" + "=" * 80)
    logger.info("【测试3】多资产类型订单验证")
    logger.info("=" * 80)
    
    # 初始化服务
    service_container = ServiceContainer()
    event_bus = EventBus()
    
    validator = OrderValidator(service_container, event_bus)
    
    # 测试用例
    test_cases = [
        ("股票订单（正确）", AssetType.STOCK_A, "000001", 100, 10.0, True),
        ("股票订单（数量错误）", AssetType.STOCK_A, "000001", 150, 10.0, False),
        ("期货订单（正确）", AssetType.FUTURES, "IF2403", 1, 3000.0, True),
        ("期货订单（保证金错误）", AssetType.FUTURES, "IF2403", 1, 3000.0, False),
        ("期权订单（正确）", AssetType.OPTION, "10004123", 1, 0.5, True),
        ("期权订单（行权价错误）", AssetType.OPTION, "10004123", 1, 0.5, False),
    ]
    
    logger.info("\n🔍 订单验证测试：\n")
    
    for test_name, asset_type, code, quantity, price, should_pass in test_cases:
        logger.info(f"\n{'—' * 40}")
        logger.info(f"🔍 测试验证: {test_name}")
        logger.info(f"{'—' * 40}")
        
        try:
            # 创建订单
            order = Order(
                order_id="TEST001",
                strategy_id="test_strategy",
                asset_type=asset_type,
                stock_code=code,
                order_type=OrderType.BUY,
                order_category=OrderCategory.LIMIT,
                order_price=price,
                order_quantity=quantity,
                order_status=OrderStatus.PENDING,
                create_time=datetime.now(),
                update_time=datetime.now()
            )
            
            # 设置特定字段
            if asset_type == AssetType.FUTURES:
                order.margin_ratio = 0.15 if should_pass else 1.5
            elif asset_type == AssetType.OPTION:
                if should_pass:
                    order.strike_price = 2.8
                    order.expiry_date = datetime(2026, 2, 28)
                    order.option_type = "CALL"
                else:
                    order.strike_price = 0.0
            
            # 验证订单
            result = validator.validate_order(order)
            
            if result.passed:
                logger.success(f"✅ 验证通过: {test_name}")
            else:
                logger.warning(f"⚠️ 验证失败: {test_name}")
                logger.info(f"   错误信息: {result.message}")
                
        except Exception as e:
            logger.error(f"❌ 验证异常: {test_name} - {e}")
    
    logger.info("\n" + "=" * 80)


def main():
    """主函数"""
    logger.info("\n" + "=" * 80)
    logger.info("多资产类型支持功能测试")
    logger.info("=" * 80)
    
    # 运行测试
    test_multi_asset_order_creation()
    test_multi_asset_order_query()
    test_multi_asset_order_validation()
    
    logger.info("\n" + "=" * 80)
    logger.info("所有测试完成")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
