#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Level-2数据面板与左侧面板的同步功能（无GUI版本）
"""

import sys
from loguru import logger

from core.events.event_bus import EventBus
from core.events.types import StockSelectedEvent


class MockLevel2DataPanel:
    """模拟Level-2数据面板"""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.current_symbol = None
        self.subscribed_symbols = set()
        self.pending_symbol = None

        # 订阅股票选择事件
        self.event_bus.subscribe(StockSelectedEvent, self._on_stock_selected)

        logger.info("MockLevel2DataPanel初始化完成")

    def _on_stock_selected(self, event: StockSelectedEvent):
        """处理股票选择事件"""
        try:
            if not event or not event.stock_code:
                return

            # 获取股票代码
            symbol = event.stock_code
            
            # 如果股票代码没有变化，直接返回
            if self.current_symbol == symbol:
                logger.info(f"股票代码未变化: {symbol}，跳过")
                return

            logger.info(f"接收到股票选择事件: {symbol}")

            # 取消订阅旧的股票
            if self.current_symbol and self.current_symbol in self.subscribed_symbols:
                self._unsubscribe_symbol(self.current_symbol)

            # 设置新的股票代码
            self.current_symbol = symbol

            # 自动订阅新的股票
            self._subscribe_symbol(symbol)

            logger.info(f"已同步到股票: {symbol}")

        except Exception as e:
            logger.error(f"处理股票选择事件失败: {e}")

    def _subscribe_symbol(self, symbol: str):
        """订阅股票Level-2数据"""
        try:
            self.subscribed_symbols.add(symbol)
            logger.info(f"已订阅 {symbol} 的Level-2数据")
        except Exception as e:
            logger.error(f"订阅失败: {e}")

    def _unsubscribe_symbol(self, symbol: str):
        """取消订阅股票Level-2数据"""
        try:
            self.subscribed_symbols.discard(symbol)
            logger.info(f"已取消订阅 {symbol} 的Level-2数据")
        except Exception as e:
            logger.error(f"取消订阅失败: {e}")

    def get_current_symbol(self):
        """获取当前股票代码"""
        return self.current_symbol

    def get_subscribed_symbols(self):
        """获取已订阅的股票"""
        return self.subscribed_symbols.copy()


def test_sync_functionality():
    """测试同步功能"""
    logger.info("=" * 60)
    logger.info("开始测试Level-2数据面板同步功能")
    logger.info("=" * 60)

    # 创建事件总线
    event_bus = EventBus()

    # 创建模拟Level-2数据面板
    level2_panel = MockLevel2DataPanel(event_bus)

    # 测试1：选择股票A
    logger.info("\n测试1：选择股票A (000001)")
    event1 = StockSelectedEvent(
        stock_code="000001",
        stock_name="平安银行",
        market="深圳",
        period="D",
        time_range="1M"
    )
    event_bus.publish(event1)

    assert level2_panel.get_current_symbol() == "000001", "测试1失败：股票代码不正确"
    assert "000001" in level2_panel.get_subscribed_symbols(), "测试1失败：未订阅股票"
    logger.info("✓ 测试1通过")

    # 测试2：选择股票B
    logger.info("\n测试2：选择股票B (600000)")
    event2 = StockSelectedEvent(
        stock_code="600000",
        stock_name="浦发银行",
        market="上海",
        period="D",
        time_range="1M"
    )
    event_bus.publish(event2)

    assert level2_panel.get_current_symbol() == "600000", "测试2失败：股票代码不正确"
    assert "600000" in level2_panel.get_subscribed_symbols(), "测试2失败：未订阅股票"
    assert "000001" not in level2_panel.get_subscribed_symbols(), "测试2失败：旧股票未取消订阅"
    logger.info("✓ 测试2通过")

    # 测试3：选择股票C
    logger.info("\n测试3：选择股票C (000002)")
    event3 = StockSelectedEvent(
        stock_code="000002",
        stock_name="万科A",
        market="深圳",
        period="D",
        time_range="1M"
    )
    event_bus.publish(event3)

    assert level2_panel.get_current_symbol() == "000002", "测试3失败：股票代码不正确"
    assert "000002" in level2_panel.get_subscribed_symbols(), "测试3失败：未订阅股票"
    assert "600000" not in level2_panel.get_subscribed_symbols(), "测试3失败：旧股票未取消订阅"
    logger.info("✓ 测试3通过")

    # 测试4：选择同一只股票
    logger.info("\n测试4：选择同一只股票 (000002)")
    event4 = StockSelectedEvent(
        stock_code="000002",
        stock_name="万科A",
        market="深圳",
        period="D",
        time_range="1M"
    )
    event_bus.publish(event4)

    assert level2_panel.get_current_symbol() == "000002", "测试4失败：股票代码不正确"
    assert len(level2_panel.get_subscribed_symbols()) == 1, "测试4失败：订阅数量不正确"
    logger.info("✓ 测试4通过")

    # 测试5：快速切换股票
    logger.info("\n测试5：快速切换股票")
    stocks = [
        ("000001", "平安银行"),
        ("600000", "浦发银行"),
        ("000002", "万科A"),
        ("600036", "招商银行"),
        ("000858", "五粮液")
    ]

    for code, name in stocks:
        event = StockSelectedEvent(
            stock_code=code,
            stock_name=name,
            market="深圳" if code.startswith("0") else "上海",
            period="D",
            time_range="1M"
        )
        event_bus.publish(event)

    assert level2_panel.get_current_symbol() == "000858", "测试5失败：股票代码不正确"
    assert "000858" in level2_panel.get_subscribed_symbols(), "测试5失败：未订阅股票"
    assert len(level2_panel.get_subscribed_symbols()) == 1, "测试5失败：订阅数量不正确"
    logger.info("✓ 测试5通过")

    logger.info("\n" + "=" * 60)
    logger.info("所有测试通过！")
    logger.info("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = test_sync_functionality()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
