#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实盘交易面板修复验证测试
"""

import sys
import os
from decimal import Decimal
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger


def test_position_properties():
    """测试 Position 类属性"""
    logger.info("测试 Position 类属性...")

    try:
        from core.services.trading_service import Position

        position = Position(
            symbol="000001.SZ",
            symbol_name="平安银行",
            quantity=1000,
            cost_price=Decimal("15.50"),
            current_price=Decimal("16.80"),
            market_value=Decimal("16800"),
            profit_loss=Decimal("1300"),
            profit_loss_ratio=8.387
        )

        assert position.avg_cost == 15.50, f"avg_cost 应为 15.50，实际为 {position.avg_cost}"
        assert position.profit_loss_pct == 8.387, f"profit_loss_pct 应为 8.387，实际为 {position.profit_loss_pct}"

        position2 = Position(
            symbol="600000.SH",
            symbol_name="浦发银行",
            quantity=2000,
            cost_price=Decimal("10.00")
        )
        assert position2.avg_cost == 10.0, f"avg_cost 应为 10.0，实际为 {position2.avg_cost}"
        assert position2.profit_loss_pct == 0.0, f"profit_loss_pct 应为 0.0，实际为 {position2.profit_loss_pct}"

        logger.info("✓ Position 类属性测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ Position 类属性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_portfolio_chart_imports():
    """测试交易面板 matplotlib 导入"""
    logger.info("测试交易面板 matplotlib 导入...")

    try:
        from gui.widgets.trading_panel import MATPLOTLIB_AVAILABLE

        logger.info(f"matplotlib 可用状态: {MATPLOTLIB_AVAILABLE}")
        logger.info("✓ 交易面板 matplotlib 导入测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ 交易面板 matplotlib 导入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_trading_panel_import():
    """测试交易面板导入"""
    logger.info("测试交易面板导入...")

    try:
        from gui.widgets.trading_panel import TradingPanel
        logger.info("✓ 交易面板导入测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ 交易面板导入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_trading_service_import():
    """测试交易服务导入"""
    logger.info("测试交易服务导入...")

    try:
        from core.services.trading_service import (
            TradingService,
            Position,
            Portfolio,
            OrderSide,
            OrderStatus,
            OrderType
        )
        logger.info("✓ 交易服务导入测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ 交易服务导入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_portfolio_properties():
    """测试 Portfolio 类属性"""
    logger.info("测试 Portfolio 类属性...")

    try:
        from core.services.trading_service import Portfolio, Position
        from decimal import Decimal

        portfolio = Portfolio(
            portfolio_id="test",
            name="测试组合",
            cash=Decimal("100000"),
            total_market_value=Decimal("39800"),
            positions={
                "000001.SZ": Position(
                    symbol="000001.SZ",
                    symbol_name="平安银行",
                    quantity=1000,
                    cost_price=Decimal("15.50"),
                    current_price=Decimal("16.80"),
                    market_value=Decimal("16800"),
                    profit_loss=Decimal("1300"),
                    profit_loss_ratio=8.387
                ),
                "600000.SH": Position(
                    symbol="600000.SH",
                    symbol_name="浦发银行",
                    quantity=2000,
                    cost_price=Decimal("10.00"),
                    current_price=Decimal("11.50"),
                    market_value=Decimal("23000"),
                    profit_loss=Decimal("3000"),
                    profit_loss_ratio=15.0
                )
            }
        )

        assert portfolio.available_cash == Decimal("100000"), f"available_cash 错误"
        assert portfolio.total_assets == Decimal("139800"), f"total_assets 应为 139800，实际为 {portfolio.total_assets}"
        assert portfolio.market_value == Decimal("39800"), f"market_value 应为 39800，实际为 {portfolio.market_value}"

        logger.info(f"available_cash: {portfolio.available_cash}")
        logger.info(f"total_assets: {portfolio.total_assets}")
        logger.info(f"market_value: {portfolio.market_value}")
        logger.info("✓ Portfolio 类属性测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ Portfolio 类属性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    logger.info("=" * 60)
    logger.info("开始实盘交易面板修复验证测试")
    logger.info("=" * 60)

    tests = [
        test_trading_service_import,
        test_position_properties,
        test_portfolio_properties,
        test_portfolio_chart_imports,
        test_trading_panel_import,
    ]

    results = []
    for test in tests:
        logger.info("")
        result = test()
        results.append(result)

    logger.info("")
    logger.info("=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)

    passed = sum(results)
    total = len(results)

    for i, (test_name, result) in enumerate(zip([t.__name__ for t in tests], results)):
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{test_name}: {status}")

    logger.info("")
    logger.info(f"总计: {passed}/{total} 测试通过")

    if passed == total:
        logger.info("🎉 所有测试通过!")
        return 0
    else:
        logger.error(f"❌ {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
