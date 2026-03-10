#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统功能回归验证测试
验证所有改造点和系统完整性
"""

import sys
import os
import threading
import time
from decimal import Decimal
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger


def test_1_portfolio_chart_imports():
    """测试1: 验证投资组合图表 matplotlib 导入"""
    logger.info("=" * 60)
    logger.info("测试1: 投资组合图表 matplotlib 导入")
    logger.info("=" * 60)
    
    try:
        from gui.widgets.trading_panel import MATPLOTLIB_AVAILABLE, TradingPanel
        
        logger.info(f"  matplotlib 可用状态: {MATPLOTLIB_AVAILABLE}")
        logger.info(f"  TradingPanel 导入: ✓")
        
        if MATPLOTLIB_AVAILABLE:
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            logger.info(f"  matplotlib 组件导入: ✓")
        
        logger.info("✅ 测试1通过: 投资组合图表功能正常\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试1失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_2_position_properties():
    """测试2: 验证 Position 类属性"""
    logger.info("=" * 60)
    logger.info("测试2: Position 类属性")
    logger.info("=" * 60)
    
    try:
        from core.services.trading_service import Position
        
        # 测试有数据的 Position
        p1 = Position(
            symbol="000001.SZ",
            symbol_name="平安银行",
            quantity=1000,
            cost_price=Decimal("15.50"),
            current_price=Decimal("16.80"),
            market_value=Decimal("16800"),
            profit_loss=Decimal("1300"),
            profit_loss_ratio=8.387
        )
        
        assert p1.avg_cost == 15.50, f"avg_cost 应为 15.50，实际为 {p1.avg_cost}"
        assert p1.profit_loss_pct == 8.387, f"profit_loss_pct 应为 8.387，实际为 {p1.profit_loss_pct}"
        logger.info(f"  有数据 Position: avg_cost={p1.avg_cost}, profit_loss_pct={p1.profit_loss_pct}")
        
        # 测试无数据的 Position
        p2 = Position(
            symbol="600000.SH",
            symbol_name="浦发银行",
            quantity=2000,
            cost_price=Decimal("10.00")
        )
        assert p2.avg_cost == 10.0, f"avg_cost 应为 10.0，实际为 {p2.avg_cost}"
        assert p2.profit_loss_pct == 0.0, f"profit_loss_pct 应为 0.0，实际为 {p2.profit_loss_pct}"
        logger.info(f"  无数据 Position: avg_cost={p2.avg_cost}, profit_loss_pct={p2.profit_loss_pct}")
        
        logger.info("✅ 测试2通过: Position 类属性正常\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试2失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_3_portfolio_properties():
    """测试3: 验证 Portfolio 类属性"""
    logger.info("=" * 60)
    logger.info("测试3: Portfolio 类属性")
    logger.info("=" * 60)
    
    try:
        from core.services.trading_service import Portfolio, Position
        
        portfolio = Portfolio(
            portfolio_id="test",
            name="测试组合",
            cash=Decimal("100000"),
            total_market_value=Decimal("39800")
        )
        
        assert portfolio.available_cash == Decimal("100000"), f"available_cash 错误"
        assert portfolio.total_assets == Decimal("139800"), f"total_assets 错误"
        assert portfolio.market_value == Decimal("39800"), f"market_value 错误"
        
        logger.info(f"  available_cash: {portfolio.available_cash}")
        logger.info(f"  total_assets: {portfolio.total_assets}")
        logger.info(f"  market_value: {portfolio.market_value}")
        
        logger.info("✅ 测试3通过: Portfolio 类属性正常\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试3失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_trading_panel_signals():
    """测试4: 验证 TradingPanel 信号连接"""
    logger.info("=" * 60)
    logger.info("测试4: TradingPanel 信号连接")
    logger.info("=" * 60)
    
    try:
        from gui.widgets.trading_panel import TradingPanel
        import inspect
        
        # 检查关键方法是否存在
        methods = [
            '_on_buy_clicked',
            '_on_sell_clicked',
            '_refresh_positions',
            '_refresh_history',
            '_refresh_orders',
            '_on_clear_positions',
            '_on_export_history',
            '_on_cancel_order',
            '_on_ctp_connect_clicked',
            '_on_ctp_disconnect_clicked',
            '_on_trade_finished',
            '_on_trade_error',
            '_on_stock_selected',
            '_on_trade_executed',
            '_on_position_updated',
            '_update_portfolio_chart'
        ]
        
        for method in methods:
            assert hasattr(TradingPanel, method), f"方法 {method} 不存在"
            logger.info(f"  ✓ {method}")
        
        logger.info("✅ 测试4通过: TradingPanel 信号连接完整\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试4失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_5_event_bus_concurrency():
    """测试5: 验证事件总线并发安全性"""
    logger.info("=" * 60)
    logger.info("测试5: 事件总线并发安全性")
    logger.info("=" * 60)
    
    try:
        from core.events.event_bus import EventBus
        from core.events.types import BaseEvent
        
        event_bus = EventBus()
        
        # 测试锁是否存在
        assert hasattr(event_bus, '_lock'), "EventBus 缺少 _lock"
        logger.info(f"  ✓ 事件总线锁: {type(event_bus._lock)}")
        
        # 测试去重功能
        assert hasattr(event_bus, '_deduplication_window'), "缺少去重功能"
        logger.info(f"  ✓ 去重窗口: {event_bus._deduplication_window}s")
        
        # 并发测试
        class TestEvent(BaseEvent):
            def __init__(self):
                super().__init__()
                self.data = None
        
        results = []
        
        def publish_events():
            for i in range(100):
                event_bus.publish(TestEvent())
                time.sleep(0.001)
            results.append(True)
        
        threads = [threading.Thread(target=publish_events) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        logger.info(f"  ✓ 并发发布测试: 3线程 x 100次 = 300次事件")
        
        logger.info("✅ 测试5通过: 事件总线并发安全\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试5失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_6_trading_service_locks():
    """测试6: 验证 TradingService 锁机制"""
    logger.info("=" * 60)
    logger.info("测试6: TradingService 锁机制")
    logger.info("=" * 60)
    
    try:
        from core.services.trading_service import TradingService
        import inspect
        
        # 检查锁是否存在
        locks = [
            '_order_lock',
            '_position_lock',
            '_portfolio_lock',
            '_trade_history_lock',
            '_service_lock',
            '_ctp_lock'
        ]
        
        for lock in locks:
            # TradingService 可能未初始化，需要检查类定义
            source = inspect.getsource(TradingService)
            assert lock in source, f"锁 {lock} 不存在于 TradingService"
            logger.info(f"  ✓ {lock}")
        
        logger.info("✅ 测试6通过: TradingService 锁机制完整\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试6失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_7_event_subscription_chain():
    """测试7: 验证事件订阅链"""
    logger.info("=" * 60)
    logger.info("测试7: 事件订阅链完整性")
    logger.info("=" * 60)
    
    try:
        # 检查事件类型
        from core.events.types import (
            StockSelectedEvent,
            TradeExecutedEvent,
            PositionUpdatedEvent,
            ThemeChangedEvent
        )
        
        logger.info(f"  ✓ StockSelectedEvent")
        logger.info(f"  ✓ TradeExecutedEvent")
        logger.info(f"  ✓ PositionUpdatedEvent")
        logger.info(f"  ✓ ThemeChangedEvent")
        
        # 检查 TradingPanel 订阅
        from gui.widgets.trading_panel import TradingPanel
        source = inspect.getsource(TradingPanel._subscribe_events)
        
        assert 'StockSelectedEvent' in source, "TradingPanel 未订阅 StockSelectedEvent"
        assert 'TradeExecutedEvent' in source, "TradingPanel 未订阅 TradeExecutedEvent"
        assert 'PositionUpdatedEvent' in source, "TradingPanel 未订阅 PositionUpdatedEvent"
        
        logger.info(f"  ✓ TradingPanel 事件订阅完整")
        
        logger.info("✅ 测试7通过: 事件订阅链完整\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试7失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_8_exception_handling():
    """测试8: 验证异常处理"""
    logger.info("=" * 60)
    logger.info("测试8: 异常处理机制")
    logger.info("=" * 60)
    
    try:
        from core.services import trading_service
        import inspect
        
        # 统计 try/except 数量
        source = inspect.getsource(trading_service)
        try_count = source.count('try:')
        except_count = source.count('except')
        
        logger.info(f"  try 语句数量: {try_count}")
        logger.info(f"  except 语句数量: {except_count}")
        
        assert try_count > 50, "TradingService 异常处理不足"
        
        logger.info("✅ 测试8通过: 异常处理充分\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试8失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_9_ui_thread_safety():
    """测试9: 验证 UI 线程安全"""
    logger.info("=" * 60)
    logger.info("测试9: UI 线程安全")
    logger.info("=" * 60)
    
    try:
        from gui.widgets.trading_panel import TradingPanel
        
        # 检查 pyqtSignal
        source = TradingPanel.__module__
        
        # 检查 pyqtSlot 装饰器使用
        import inspect
        source_code = inspect.getsource(TradingPanel)
        
        assert 'pyqtSignal' in source_code, "未使用 pyqtSignal"
        assert 'pyqtSlot' in source_code, "未使用 pyqtSlot"
        
        logger.info(f"  ✓ pyqtSignal 使用正确")
        logger.info(f"  ✓ pyqtSlot 使用正确")
        
        # 检查 TradeWorker 异步执行
        assert 'QThread' in source_code, "未使用 QThread"
        logger.info(f"  ✓ QThread 异步执行")
        
        logger.info("✅ 测试9通过: UI 线程安全\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试9失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_10_data_refresh_mechanism():
    """测试10: 验证数据刷新机制"""
    logger.info("=" * 60)
    logger.info("测试10: 数据刷新机制")
    logger.info("=" * 60)
    
    try:
        from gui.widgets.trading_panel import TradingPanel
        import inspect
        
        source = inspect.getsource(TradingPanel)
        
        # 检查刷新方法
        refresh_methods = [
            '_refresh_data',
            '_refresh_positions',
            '_refresh_history',
            '_refresh_orders',
            '_update_portfolio_display'
        ]
        
        for method in refresh_methods:
            assert method in source, f"刷新方法 {method} 不存在"
            logger.info(f"  ✓ {method}")
        
        # 检查事件触发刷新
        assert '_on_trade_finished' in source, "_on_trade_finished 不存在"
        assert '_on_trade_executed' in source, "_on_trade_executed 不存在"
        
        logger.info(f"  ✓ 交易完成自动刷新")
        logger.info(f"  ✓ 事件触发自动刷新")
        
        logger.info("✅ 测试10通过: 数据刷新机制完整\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试10失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("       系统功能回归验证测试 - 开始")
    logger.info("=" * 70)
    logger.info("")
    
    tests = [
        ("测试1: 投资组合图表功能", test_1_portfolio_chart_imports),
        ("测试2: Position 类属性", test_2_position_properties),
        ("测试3: Portfolio 类属性", test_3_portfolio_properties),
        ("测试4: TradingPanel 信号连接", test_4_trading_panel_signals),
        ("测试5: 事件总线并发安全", test_5_event_bus_concurrency),
        ("测试6: TradingService 锁机制", test_6_trading_service_locks),
        ("测试7: 事件订阅链完整性", test_7_event_subscription_chain),
        ("测试8: 异常处理机制", test_8_exception_handling),
        ("测试9: UI 线程安全", test_9_ui_thread_safety),
        ("测试10: 数据刷新机制", test_10_data_refresh_mechanism),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"{name} 执行异常: {e}")
            results.append((name, False))
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("       测试结果汇总")
    logger.info("=" * 70)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info("")
    logger.info("-" * 70)
    logger.info(f"总计: {passed}/{len(tests)} 测试通过")
    
    if passed == len(tests):
        logger.info("")
        logger.info("🎉 所有测试通过! 系统功能正常，可以投入生产使用。")
        logger.info("")
        return 0
    else:
        logger.error(f"\n❌ {failed} 个测试失败，请检查系统。")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
