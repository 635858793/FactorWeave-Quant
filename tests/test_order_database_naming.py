"""
测试订单数据库命名规则（简化版，不使用emoji）
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
from core.containers import ServiceContainer
from core.events import EventBus
from loguru import logger


def test_order_database_naming():
    """测试订单数据库命名规则"""
    logger.info("=" * 80)
    logger.info("测试订单数据库命名规则")
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
    ]
    
    logger.info("\n创建订单测试：\n")
    
    for asset_type, code, name, type_name in test_cases:
        logger.info(f"\n{'-' * 40}")
        logger.info(f"测试创建: {name} ({code}) [{type_name}]")
        logger.info(f"{'-' * 40}")
        
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
                logger.info(f"[OK] 订单创建成功: {order.order_id}")
                logger.info(f"   资产类型: {order.asset_type.value}")
                logger.info(f"   资产代码: {order.stock_code}")
                logger.info(f"   订单价格: {order.order_price}")
                logger.info(f"   订单数量: {order.order_quantity}")
                
                # 验证数据库路径
                pool_name = repository._get_database_pool_name(asset_type)
                logger.info(f"   数据库池名称: {pool_name}")
                
                # 验证数据库文件是否存在
                db_path = Path(f"data/databases/{asset_type.value.lower()}/{pool_name}.duckdb")
                if db_path.exists():
                    logger.info(f"   数据库文件存在: {db_path}")
                else:
                    logger.error(f"   数据库文件不存在: {db_path}")
            else:
                logger.error(f"[FAIL] 订单创建失败: {code}")
                
        except Exception as e:
            logger.error(f"[ERROR] 订单创建异常: {code} - {e}")
    
    logger.info("\n" + "=" * 80)


def test_order_query():
    """测试订单查询"""
    logger.info("\n" + "=" * 80)
    logger.info("测试订单查询")
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
    
    logger.info("\n订单查询测试：\n")
    
    for query_name, query in test_cases:
        logger.info(f"\n{'-' * 40}")
        logger.info(f"测试查询: {query_name}")
        logger.info(f"{'-' * 40}")
        
        try:
            # 查询订单
            orders = repository.query_orders(query)
            
            logger.info(f"[OK] 查询成功: 返回 {len(orders)} 条记录")
            
            for order in orders[:3]:  # 只显示前3条
                logger.info(f"   - {order.order_id}: {order.asset_type.value} {order.stock_code}")
                
        except Exception as e:
            logger.error(f"[ERROR] 查询失败: {query_name} - {e}")
    
    logger.info("\n" + "=" * 80)


def main():
    """主函数"""
    logger.info("\n" + "=" * 80)
    logger.info("订单数据库命名规则测试")
    logger.info("=" * 80)
    
    # 运行测试
    test_order_database_naming()
    test_order_query()
    
    logger.info("\n" + "=" * 80)
    logger.info("所有测试完成")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
