"""
生成测试订单数据
"""

import sys
import os
from decimal import Decimal
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from core.trading.order_service import OrderService
from core.trading.order_models import OrderType, OrderCategory, OrderRequest
from core.plugin_types import AssetType
from core.containers import get_service_container
from core.events import get_event_bus


def generate_test_orders(count=50):
    """生成测试订单"""
    try:
        logger.info("=" * 80)
        logger.info(f"开始生成 {count} 个测试订单")
        logger.info("=" * 80)

        # 1. 初始化服务
        logger.info("\n1. 初始化服务...")
        service_container = get_service_container()
        event_bus = get_event_bus()

        # 2. 创建订单服务
        logger.info("\n2. 创建订单服务...")
        order_service = OrderService(service_container, event_bus)

        # 3. 定义测试数据
        asset_types = [
            AssetType.STOCK_A,
            AssetType.STOCK_H,
            AssetType.STOCK_US,
            AssetType.STOCK_HK,
            AssetType.FUTURES,
            AssetType.OPTION,
            AssetType.CRYPTO,
            AssetType.FOREX
        ]

        symbols = {
            AssetType.STOCK_A: ["600000", "600036", "000001", "000002", "000858"],
            AssetType.STOCK_H: ["00700", "00941", "03690", "02318", "01299"],
            AssetType.STOCK_US: ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
            AssetType.STOCK_HK: ["00700", "00941", "03690", "02318", "01299"],
            AssetType.FUTURES: ["IF2401", "IH2401", "IC2401", "IM2401", "MA405"],
            AssetType.OPTION: ["50ETF购1月2800", "50ETF沽1月2800", "300ETF购1月4000"],
            AssetType.CRYPTO: ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT"],
            AssetType.FOREX: ["USD/CNY", "EUR/USD", "GBP/USD", "USD/JPY"]
        }

        order_types = [OrderType.BUY, OrderType.SELL]
        order_categories = [OrderCategory.LIMIT, OrderCategory.MARKET]

        # 4. 生成订单
        logger.info(f"\n3. 开始生成 {count} 个测试订单...")
        success_count = 0
        failed_count = 0

        for i in range(count):
            try:
                # 随机选择参数
                asset_type = asset_types[i % len(asset_types)]
                symbol_list = symbols[asset_type]
                symbol = symbol_list[i % len(symbol_list)]
                order_type = order_types[i % 2]
                order_category = order_categories[i % 2]

                # 随机价格和数量
                if asset_type in [AssetType.STOCK_A, AssetType.STOCK_H, AssetType.STOCK_HK]:
                    price = Decimal(str(round(10 + (i % 50) * 0.5, 2)))
                    quantity = 100 * (1 + (i % 5))
                elif asset_type == AssetType.STOCK_US:
                    price = Decimal(str(round(100 + (i % 200), 2)))
                    quantity = 10 * (1 + (i % 5))
                elif asset_type == AssetType.FUTURES:
                    price = Decimal(str(round(3000 + (i % 500), 1)))
                    quantity = 1 * (1 + (i % 3))
                elif asset_type == AssetType.OPTION:
                    price = Decimal(str(round(0.1 + (i % 20) * 0.05, 3)))
                    quantity = 10 * (1 + (i % 3))
                elif asset_type == AssetType.CRYPTO:
                    price = Decimal(str(round(1000 + (i % 5000), 2)))
                    quantity = 0.1 * (1 + (i % 5))
                elif asset_type == AssetType.FOREX:
                    price = Decimal(str(round(7.0 + (i % 100) * 0.01, 4)))
                    quantity = 1000 * (1 + (i % 5))
                else:
                    price = Decimal('10.00')
                    quantity = 100

                # 创建订单请求
                order_request = OrderRequest(
                    strategy_id=f"test_strategy_{i}",
                    asset_type=asset_type,
                    stock_code=symbol,
                    order_type=order_type,
                    order_category=order_category,
                    order_price=float(price),
                    order_quantity=int(quantity),
                    user_id="test_user",
                    account_id="test_account",
                    tags=["test", "generated"],
                    metadata={"test_index": i}
                )

                # 创建订单
                order = order_service.create_order(order_request)
                if order:
                    success_count += 1
                    logger.info(f"  [{i+1}/{count}] ✅ 订单创建成功: {order.order_id} ({asset_type.value} {symbol})")
                else:
                    failed_count += 1
                    logger.warning(f"  [{i+1}/{count}] ⚠️  订单创建失败: {asset_type.value} {symbol}")

                # 每10个订单输出一次进度
                if (i + 1) % 10 == 0:
                    logger.info(f"  进度: {i+1}/{count} (成功: {success_count}, 失败: {failed_count})")

            except Exception as e:
                failed_count += 1
                logger.error(f"  [{i+1}/{count}] ❌ 订单创建异常: {e}")

        # 5. 输出统计信息
        logger.info("\n" + "=" * 80)
        logger.info(f"测试订单生成完成")
        logger.info(f"  总计: {count} 个订单")
        logger.info(f"  成功: {success_count} 个订单")
        logger.info(f"  失败: {failed_count} 个订单")
        logger.info(f"  成功率: {success_count/count:.2%}")
        logger.info("=" * 80)

        return success_count > 0

    except Exception as e:
        logger.error(f"❌ 生成测试订单失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    try:
        import argparse

        parser = argparse.ArgumentParser(description='生成测试订单数据')
        parser.add_argument('--count', type=int, default=50, help='订单数量')
        args = parser.parse_args()

        success = generate_test_orders(args.count)
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
