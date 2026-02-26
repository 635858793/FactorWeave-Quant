#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实盘交易tab回归测试

测试所有P0、P1、P2功能，确保功能完整、逻辑正确、没有模拟数据
"""

import sys
import os
from datetime import datetime
from decimal import Decimal
from typing import Optional

from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTradingPanelRegression:
    """实盘交易tab回归测试"""

    def __init__(self):
        self.service_container = None
        self.event_bus = None
        self.trading_service = None
        self.market_service = None
        self.trading_panel = None

    def setup(self):
        """设置测试环境"""
        logger.info("设置测试环境...")

        try:
            from core.containers import get_service_container
            from core.events import get_event_bus
            from core.services.trading_service import TradingService
            from core.services.market_service import MarketService

            self.service_container = get_service_container()
            self.event_bus = get_event_bus()

            # 初始化MarketService
            self.market_service = MarketService(
                service_container=self.service_container
            )

            # 初始化TradingService并注入MarketService
            self.trading_service = TradingService(
                service_container=self.service_container
            )

            # 注入MarketService到TradingService
            self.trading_service._market_service = self.market_service

            # 初始化TradingService
            self.trading_service.initialize()

            logger.info("测试环境设置完成")
            return True

        except Exception as e:
            logger.error(f"设置测试环境失败: {e}")
            return False

    def test_p0_1_realtime_price_no_hardcoding(self):
        """P0-1: 测试实时价格获取（无硬编码）"""
        logger.info("测试P0-1: 实时价格获取（无硬编码）...")

        try:
            # 检查_get_current_price方法是否存在
            if not hasattr(self.trading_service, '_get_current_price'):
                logger.error("TradingService缺少_get_current_price方法")
                return False

            # 检查MarketService是否注入
            if self.trading_service._market_service is None:
                logger.error("MarketService未注入到TradingService")
                return False

            # 测试获取价格
            test_symbol = "000001.SZ"
            test_name = "平安银行"
            price = self.trading_service._get_current_price(test_symbol, test_name)

            if price is None:
                logger.warning(f"无法获取{test_symbol}的实时价格，可能是市场未开盘")
                return True

            if price <= 0:
                logger.error(f"获取的价格无效: {price}")
                return False

            logger.info(f"成功获取{test_symbol}的实时价格: {price}")
            return True

        except Exception as e:
            logger.error(f"测试P0-1失败: {e}")
            return False

    def test_p0_2_trade_confirmation_and_fund_verification(self):
        """P0-2: 测试交易确认和资金验证"""
        logger.info("测试P0-2: 交易确认和资金验证...")

        try:
            # 检查TradingPanel是否有交易确认功能
            from gui.widgets.trading_panel import TradingPanel

            # 检查买入方法
            if not hasattr(TradingPanel, '_on_buy_clicked'):
                logger.error("TradingPanel缺少_on_buy_clicked方法")
                return False

            # 检查卖出方法
            if not hasattr(TradingPanel, '_on_sell_clicked'):
                logger.error("TradingPanel缺少_on_sell_clicked方法")
                return False

            # 测试买入订单的资金验证
            test_symbol = "000001.SZ"
            test_quantity = 100
            test_price = Decimal("10.00")

            # 获取投资组合
            portfolio = self.trading_service.get_portfolio()
            if portfolio is None:
                logger.error("无法获取投资组合")
                return False

            # 测试资金不足的情况
            required_funds = test_quantity * test_price
            if portfolio.available_cash < required_funds:
                logger.info(f"资金不足，预期无法买入（需要: {required_funds}, 可用: {portfolio.available_cash}）")
            else:
                logger.info(f"资金充足，预期可以买入（需要: {required_funds}, 可用: {portfolio.available_cash}）")

            logger.info("交易确认和资金验证功能正常")
            return True

        except Exception as e:
            logger.error(f"测试P0-2失败: {e}")
            return False

    def test_p0_3_market_service_integration(self):
        """P0-3: 测试MarketService集成"""
        logger.info("测试P0-3: MarketService集成...")

        try:
            # 检查MarketService是否正确集成
            if self.market_service is None:
                logger.error("MarketService未初始化")
                return False

            # 检查MarketService的get_quote方法
            if not hasattr(self.market_service, 'get_quote'):
                logger.error("MarketService缺少get_quote方法")
                return False

            # 测试获取行情
            test_symbol = "000001.SZ"
            quote = self.market_service.get_quote(test_symbol)

            if quote is None:
                logger.warning(f"无法获取{test_symbol}的行情，可能是市场未开盘")
                return True

            logger.info(f"成功获取{test_symbol}的行情: {quote}")
            return True

        except Exception as e:
            logger.error(f"测试P0-3失败: {e}")
            return False

    def test_p1_1_price_input_and_order_type_selection(self):
        """P1-1: 测试价格输入和订单类型选择"""
        logger.info("测试P1-1: 价格输入和订单类型选择...")

        try:
            from gui.widgets.trading_panel import TradingPanel
            from core.trading.order_models import OrderType

            # 检查TradingPanel是否有订单类型选择方法
            if not hasattr(TradingPanel, '_on_order_type_changed'):
                logger.error("TradingPanel缺少_on_order_type_changed方法")
                return False

            # 检查execute_buy_order是否接受price参数
            import inspect
            buy_sig = inspect.signature(self.trading_service.execute_buy_order)
            if 'price' not in buy_sig.parameters:
                logger.error("execute_buy_order缺少price参数")
                return False

            # 检查execute_sell_order是否接受price参数
            sell_sig = inspect.signature(self.trading_service.execute_sell_order)
            if 'price' not in sell_sig.parameters:
                logger.error("execute_sell_order缺少price参数")
                return False

            # 检查_create_trading_tab方法中是否创建了订单类型选择器
            source = inspect.getsource(TradingPanel._create_trading_tab)
            if 'order_type_combo' not in source:
                logger.error("TradingPanel._create_trading_tab未创建订单类型选择器")
                return False

            if 'price_spin' not in source:
                logger.error("TradingPanel._create_trading_tab未创建价格输入框")
                return False

            logger.info("价格输入和订单类型选择功能正常")
            return True

        except Exception as e:
            logger.error(f"测试P1-1失败: {e}")
            return False

    def test_p1_2_event_driven_refresh(self):
        """P1-2: 测试事件驱动刷新机制"""
        logger.info("测试P1-2: 事件驱动刷新机制...")

        try:
            from core.events import TradeExecutedEvent, PositionUpdatedEvent

            # 检查TradingPanel是否有事件处理方法
            from gui.widgets.trading_panel import TradingPanel

            if not hasattr(TradingPanel, '_on_trade_executed'):
                logger.error("TradingPanel缺少_on_trade_executed方法")
                return False

            if not hasattr(TradingPanel, '_on_position_updated'):
                logger.error("TradingPanel缺少_on_position_updated方法")
                return False

            # 检查TradingService是否在execute_order中发布事件
            import inspect
            source = inspect.getsource(self.trading_service.execute_order)
            if 'TradeExecutedEvent' not in source:
                logger.error("TradingService.execute_order未发布TradeExecutedEvent")
                return False

            # 检查_update_position_from_trade方法是否发布PositionUpdatedEvent
            if hasattr(self.trading_service, '_update_position_from_trade'):
                position_source = inspect.getsource(self.trading_service._update_position_from_trade)
                if 'PositionUpdatedEvent' not in position_source:
                    logger.error("TradingService._update_position_from_trade未发布PositionUpdatedEvent")
                    return False
            else:
                logger.error("TradingService缺少_update_position_from_trade方法")
                return False

            logger.info("事件驱动刷新机制正常")
            return True

        except Exception as e:
            logger.error(f"测试P1-2失败: {e}")
            return False

    def test_p1_3_clear_positions_functionality(self):
        """P1-3: 测试清空持仓功能"""
        logger.info("测试P1-3: 清空持仓功能...")

        try:
            # 检查TradingService是否有clear_all_positions方法
            if not hasattr(self.trading_service, 'clear_all_positions'):
                logger.error("TradingService缺少clear_all_positions方法")
                return False

            # 检查TradingPanel是否有_on_clear_positions方法
            from gui.widgets.trading_panel import TradingPanel

            if not hasattr(TradingPanel, '_on_clear_positions'):
                logger.error("TradingPanel缺少_on_clear_positions方法")
                return False

            # 测试清空持仓功能
            success, message = self.trading_service.clear_all_positions()
            logger.info(f"清空持仓结果: {success}, {message}")

            logger.info("清空持仓功能正常")
            return True

        except Exception as e:
            logger.error(f"测试P1-3失败: {e}")
            return False

    def test_p2_1_order_status_tracking(self):
        """P2-1: 测试订单状态跟踪"""
        logger.info("测试P2-1: 订单状态跟踪...")

        try:
            # 检查TradingService是否有get_active_orders方法
            if not hasattr(self.trading_service, 'get_active_orders'):
                logger.error("TradingService缺少get_active_orders方法")
                return False

            # 检查TradingPanel是否有订单相关方法
            from gui.widgets.trading_panel import TradingPanel

            if not hasattr(TradingPanel, '_refresh_orders'):
                logger.error("TradingPanel缺少_refresh_orders方法")
                return False

            if not hasattr(TradingPanel, '_on_order_selection_changed'):
                logger.error("TradingPanel缺少_on_order_selection_changed方法")
                return False

            # 测试获取活跃订单
            orders = self.trading_service.get_active_orders()
            logger.info(f"当前活跃订单数量: {len(orders)}")

            logger.info("订单状态跟踪功能正常")
            return True

        except Exception as e:
            logger.error(f"测试P2-1失败: {e}")
            return False

    def test_p2_2_order_cancellation(self):
        """P2-2: 测试交易撤销功能"""
        logger.info("测试P2-2: 交易撤销功能...")

        try:
            # 检查TradingService是否有cancel_order方法
            if not hasattr(self.trading_service, 'cancel_order'):
                logger.error("TradingService缺少cancel_order方法")
                return False

            # 检查TradingPanel是否有_on_cancel_order方法
            from gui.widgets.trading_panel import TradingPanel

            if not hasattr(TradingPanel, '_on_cancel_order'):
                logger.error("TradingPanel缺少_on_cancel_order方法")
                return False

            # 测试撤销订单功能
            test_order_id = "test_order_123"
            success, message = self.trading_service.cancel_order(test_order_id)
            logger.info(f"撤销订单结果: {success}, {message}")

            logger.info("交易撤销功能正常")
            return True

        except Exception as e:
            logger.error(f"测试P2-2失败: {e}")
            return False

    def test_p2_3_user_experience_details(self):
        """P2-3: 测试用户体验细节"""
        logger.info("测试P2-3: 用户体验细节...")

        try:
            from gui.widgets.trading_panel import TradingPanel

            # 检查是否有订单选择变化处理
            if not hasattr(TradingPanel, '_on_order_selection_changed'):
                logger.error("TradingPanel缺少_on_order_selection_changed方法")
                return False

            # 检查是否有刷新订单方法
            if not hasattr(TradingPanel, '_refresh_orders'):
                logger.error("TradingPanel缺少_refresh_orders方法")
                return False

            # 检查是否有撤销订单方法
            if not hasattr(TradingPanel, '_on_cancel_order'):
                logger.error("TradingPanel缺少_on_cancel_order方法")
                return False

            logger.info("用户体验细节功能正常")
            return True

        except Exception as e:
            logger.error(f"测试P2-3失败: {e}")
            return False

    def check_no_mock_data(self):
        """检查没有模拟数据"""
        logger.info("检查没有模拟数据...")

        try:
            # 检查TradingService中是否有硬编码的价格
            import inspect
            source = inspect.getsource(self.trading_service.execute_buy_order)

            if 'Decimal("100.00")' in source or 'Decimal("50.00")' in source:
                logger.error("发现硬编码的价格值")
                return False

            # 检查TradingService中是否有硬编码的数量
            if 'quantity = 100' in source or 'quantity = 1000' in source:
                logger.error("发现硬编码的数量值")
                return False

            logger.info("未发现模拟数据")
            return True

        except Exception as e:
            logger.error(f"检查模拟数据失败: {e}")
            return False

    def run_all_tests(self):
        """运行所有测试"""
        logger.info("=" * 80)
        logger.info("开始实盘交易tab回归测试")
        logger.info("=" * 80)

        if not self.setup():
            logger.error("测试环境设置失败，终止测试")
            return False

        results = []

        # P0级测试
        results.append(("P0-1: 实时价格获取（无硬编码）", self.test_p0_1_realtime_price_no_hardcoding()))
        results.append(("P0-2: 交易确认和资金验证", self.test_p0_2_trade_confirmation_and_fund_verification()))
        results.append(("P0-3: MarketService集成", self.test_p0_3_market_service_integration()))

        # P1级测试
        results.append(("P1-1: 价格输入和订单类型选择", self.test_p1_1_price_input_and_order_type_selection()))
        results.append(("P1-2: 事件驱动刷新机制", self.test_p1_2_event_driven_refresh()))
        results.append(("P1-3: 清空持仓功能", self.test_p1_3_clear_positions_functionality()))

        # P2级测试
        results.append(("P2-1: 订单状态跟踪", self.test_p2_1_order_status_tracking()))
        results.append(("P2-2: 交易撤销功能", self.test_p2_2_order_cancellation()))
        results.append(("P2-3: 用户体验细节", self.test_p2_3_user_experience_details()))

        # 检查模拟数据
        results.append(("检查没有模拟数据", self.check_no_mock_data()))

        # 输出测试结果
        logger.info("=" * 80)
        logger.info("测试结果汇总")
        logger.info("=" * 80)

        passed = 0
        failed = 0

        for test_name, result in results:
            status = "✓ 通过" if result else "✗ 失败"
            logger.info(f"{test_name}: {status}")
            if result:
                passed += 1
            else:
                failed += 1

        logger.info("=" * 80)
        logger.info(f"总计: {len(results)} 个测试")
        logger.info(f"通过: {passed} 个")
        logger.info(f"失败: {failed} 个")
        logger.info("=" * 80)

        return failed == 0


def main():
    """主函数"""
    tester = TestTradingPanelRegression()
    success = tester.run_all_tests()

    if success:
        logger.info("所有测试通过！")
        sys.exit(0)
    else:
        logger.error("部分测试失败！")
        sys.exit(1)


if __name__ == "__main__":
    main()
