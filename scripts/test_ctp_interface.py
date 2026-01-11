#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试CTP交易接口
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from datetime import datetime
from core.trading.interfaces.ctp_trading_interface import CTPTradingInterface
from core.trading.interfaces.ctp_config import CTPConfig
from core.trading.order_models import Order, OrderType, OrderCategory, OrderStatus
from core.plugin_types import AssetType


def test_ctp_interface():
    """测试CTP交易接口"""
    try:
        logger.info("=" * 80)
        logger.info("开始测试CTP交易接口")
        logger.info("=" * 80)

        # 1. 创建CTP配置（模拟模式）
        logger.info("\n1. 创建CTP配置...")
        config = CTPConfig(
            trade_front="tcp://180.168.146.187:10130",
            quote_front="tcp://180.168.146.187:10131",
            broker_id="9999",
            investor_id="test_investor",
            password="test_password",
            app_id="test_app",
            auth_code="test_auth",
            use_simulation=True
        )
        logger.info(f"✅ CTP配置创建成功 (模拟模式: {config.use_simulation})")

        # 2. 初始化CTP接口
        logger.info("\n2. 初始化CTP接口...")
        ctp_interface = CTPTradingInterface(config)
        logger.info("✅ CTP接口初始化成功")

        # 3. 测试连接
        logger.info("\n3. 测试连接...")
        connected = ctp_interface.connect()
        if connected:
            logger.info("✅ CTP连接成功")
        else:
            logger.error("❌ CTP连接失败")
            return False

        # 4. 测试登录
        logger.info("\n4. 测试登录...")
        logged_in = ctp_interface.login()
        if logged_in:
            logger.info("✅ CTP登录成功")
        else:
            logger.error("❌ CTP登录失败")
            return False

        # 5. 创建测试订单（期货）
        logger.info("\n5. 创建测试订单（期货）...")
        futures_order = Order(
            order_id="TEST_FUTURES_001",
            strategy_id="test_strategy",
            asset_type=AssetType.FUTURES,
            stock_code="IF2401",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=4000.0,
            order_quantity=1,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            user_id="test_user",
            account_id="test_account",
            contract_multiplier=300,
            margin_ratio=0.15
        )
        logger.info(f"✅ 期货订单创建成功: {futures_order.stock_code}")

        # 6. 测试提交期货订单
        logger.info("\n6. 测试提交期货订单...")
        result = ctp_interface.submit_order(futures_order)
        if result.status.value == "success":
            logger.info(f"✅ 期货订单提交成功")
            logger.info(f"   订单ID: {result.order_id}")
            logger.info(f"   交易所订单ID: {result.exchange_order_id}")
            logger.info(f"   消息: {result.message}")
        else:
            logger.error(f"❌ 期货订单提交失败: {result.message}")
            logger.error(f"   错误码: {result.error_code}")
            return False

        # 7. 创建测试订单（期权）
        logger.info("\n7. 创建测试订单（期权）...")
        option_order = Order(
            order_id="TEST_OPTION_001",
            strategy_id="test_strategy",
            asset_type=AssetType.OPTION,
            stock_code="IO2401-C-4000",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=50.0,
            order_quantity=10,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            user_id="test_user",
            account_id="test_account",
            contract_multiplier=100,
            margin_ratio=0.20,
            strike_price=4000.0,
            expiry_date="2024-01-15",
            option_type="CALL"
        )
        logger.info(f"✅ 期权订单创建成功: {option_order.stock_code}")

        # 8. 测试提交期权订单
        logger.info("\n8. 测试提交期权订单...")
        result = ctp_interface.submit_order(option_order)
        if result.status.value == "success":
            logger.info(f"✅ 期权订单提交成功")
            logger.info(f"   订单ID: {result.order_id}")
            logger.info(f"   交易所订单ID: {result.exchange_order_id}")
            logger.info(f"   消息: {result.message}")
        else:
            logger.error(f"❌ 期权订单提交失败: {result.message}")
            logger.error(f"   错误码: {result.error_code}")
            return False

        # 9. 测试查询订单状态
        logger.info("\n9. 测试查询订单状态...")
        result = ctp_interface.query_order_status("TEST_FUTURES_001")
        if result.status.value == "success":
            logger.info(f"✅ 订单状态查询成功")
            logger.info(f"   订单ID: {result.order_id}")
            logger.info(f"   消息: {result.message}")
            if result.details:
                logger.info(f"   订单状态: {result.details.get('order_status', 'N/A')}")
        else:
            logger.error(f"❌ 订单状态查询失败: {result.message}")
            return False

        # 10. 测试取消订单
        logger.info("\n10. 测试取消订单...")
        result = ctp_interface.cancel_order("TEST_FUTURES_001")
        if result.status.value == "success":
            logger.info(f"✅ 订单取消成功")
            logger.info(f"   订单ID: {result.order_id}")
            logger.info(f"   消息: {result.message}")
        else:
            logger.error(f"❌ 订单取消失败: {result.message}")
            return False

        # 11. 测试断开连接
        logger.info("\n11. 测试断开连接...")
        ctp_interface.disconnect()
        logger.info("✅ CTP连接已断开")

        logger.info("\n" + "=" * 80)
        logger.info("✅ CTP交易接口测试完成")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 测试CTP交易接口失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    try:
        success = test_ctp_interface()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
