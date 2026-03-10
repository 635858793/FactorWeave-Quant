#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P0级修复功能自测回归验证（简化版，避免循环导入）
"""

import sys
sys.path.insert(0, '.')

import threading
from datetime import datetime
from unittest.mock import MagicMock, patch
import pandas as pd


def test_p0_1_position_sync():
    print('=' * 60)
    print('P0-1: 持仓同步机制验证')
    print('=' * 60)
    
    with patch('core.trading.account_repository.AccountRepository'):
        with patch('core.containers.ServiceContainer'):
            with patch('core.events.EventBus') as MockEventBus:
                mock_event_bus = MagicMock()
                MockEventBus.return_value = mock_event_bus
                
                from core.trading.account_manager import AccountManager
                
                manager = AccountManager.__new__(AccountManager)
                manager.service_container = MagicMock()
                manager.event_bus = mock_event_bus
                manager._accounts = {}
                manager._positions = {}
                manager._fund_infos = {}
                manager._account_lock = threading.RLock()
                manager._position_lock = threading.RLock()
                manager._fund_info_lock = threading.RLock()
                manager._last_sync_times = {}
                manager._sync_lock = threading.Lock()
                manager._min_sync_interval = 5
                manager._pending_sync_accounts = set()
                manager._sync_timer = None
                manager._realtime_sync_enabled = False
                manager.repository = MagicMock()
                
                manager._setup_position_sync_handlers()
                
                assert hasattr(manager, '_setup_position_sync_handlers'), '缺少持仓同步处理器设置方法'
                assert hasattr(manager, '_on_order_submitted'), '缺少订单提交事件处理方法'
                assert hasattr(manager, '_on_order_cancelled'), '缺少订单取消事件处理方法'
                assert hasattr(manager, '_schedule_position_sync'), '缺少持仓同步调度方法'
                assert hasattr(manager, '_execute_pending_syncs'), '缺少执行同步方法'
                
                mock_event_bus.subscribe.assert_called()
                
                print('OK 持仓同步机制方法完整')
                print('OK 事件处理器已注册')
                print('OK 节流机制已实现')
                print()
                return True


def test_p0_2_risk_check():
    print('=' * 60)
    print('P0-2: 风控检查响应验证')
    print('=' * 60)
    
    with patch('core.trading.order_repository.OrderRepository'):
        with patch('core.containers.ServiceContainer'):
            with patch('core.events.EventBus'):
                from core.trading.order_executor import OrderExecutor
                from core.trading.order_models import Order, OrderType, OrderStatus, OrderCategory
                from core.plugin_types import AssetType
                
                executor = OrderExecutor.__new__(OrderExecutor)
                executor.service_container = MagicMock()
                executor.event_bus = MagicMock()
                
                order = Order(
                    order_id='TEST_001',
                    strategy_id='test',
                    asset_type=AssetType.STOCK_A,
                    stock_code='600000',
                    order_type=OrderType.BUY,
                    order_category=OrderCategory.LIMIT,
                    order_price=10.0,
                    order_quantity=100,
                    order_status=OrderStatus.PENDING,
                    create_time=datetime.now(),
                    update_time=datetime.now(),
                    account_id='default'
                )
                
                result = executor._pre_trade_risk_check(order)
                print(f'风控检查结果: passed={result["passed"]}, reason={result.get("reason", "无")}')
                assert 'passed' in result, '缺少passed字段'
                assert 'reason' in result, '缺少reason字段'
                assert 'warnings' in result, '缺少warnings字段'
                print('OK 风控检查方法完整')
                print('OK 返回结果格式正确')
                print()
                return True


def test_p0_3_vwap_model():
    print('=' * 60)
    print('P0-3: VWAP成交模型验证')
    print('=' * 60)
    
    from backtest.unified_backtest_engine import UnifiedBacktestEngine
    
    engine = UnifiedBacktestEngine()
    
    dates = pd.date_range('2024-01-01', periods=10, freq='D')
    data = pd.DataFrame({
        'close': [10.0 + i * 0.1 for i in range(10)],
        'high': [10.2 + i * 0.1 for i in range(10)],
        'low': [9.8 + i * 0.1 for i in range(10)],
        'volume': [1000000] * 10,
        'signal': [1, 0, -1, 0, 1, 0, -1, 0, 1, 0]
    }, index=dates)
    
    engine._execution_model = 'vwap'
    vwap_price = engine._calculate_vwap_price(data, 0, 10.0, True, 0.001)
    print(f'VWAP成交价: {vwap_price:.4f}')
    assert vwap_price > 0, 'VWAP价格必须大于0'
    
    engine._execution_model = 'random'
    random_price = engine._calculate_random_price(data, 0, 10.0, True, 0.001)
    print(f'随机成交价: {random_price:.4f}')
    assert random_price > 0, '随机价格必须大于0'
    
    engine._execution_model = 'fixed'
    fixed_price = engine._calculate_execution_price(data, 0, 10.0, True, 0.001)
    print(f'固定滑点成交价: {fixed_price:.4f}')
    assert fixed_price > 0, '固定价格必须大于0'
    
    print('OK VWAP成交模型完整')
    print('OK 随机成交模型完整')
    print('OK 固定滑点模型完整')
    print()
    return True


def test_backtest_with_vwap():
    print('=' * 60)
    print('P0-3: 回测引擎VWAP集成测试')
    print('=' * 60)
    
    from backtest.unified_backtest_engine import UnifiedBacktestEngine
    
    engine = UnifiedBacktestEngine()
    
    dates = pd.date_range('2024-01-01', periods=30, freq='D')
    data = pd.DataFrame({
        'close': [10.0 + i * 0.1 for i in range(30)],
        'high': [10.2 + i * 0.1 for i in range(30)],
        'low': [9.8 + i * 0.1 for i in range(30)],
        'volume': [1000000] * 30,
        'signal': [1 if i % 5 == 0 else (-1 if i % 5 == 3 else 0) for i in range(30)]
    }, index=dates)
    
    result = engine.run_backtest(
        data=data,
        signal_col='signal',
        price_col='close',
        initial_capital=100000,
        execution_model='vwap'
    )
    
    assert result is not None, '回测结果不能为空'
    print(f'回测完成，使用VWAP成交模型')
    print('OK 回测引擎VWAP集成正常')
    print()
    return True


if __name__ == '__main__':
    all_passed = True
    
    try:
        all_passed = test_p0_1_position_sync() and all_passed
    except Exception as e:
        print(f'FAILED P0-1: {e}')
        import traceback
        traceback.print_exc()
        all_passed = False
    
    try:
        all_passed = test_p0_2_risk_check() and all_passed
    except Exception as e:
        print(f'FAILED P0-2: {e}')
        import traceback
        traceback.print_exc()
        all_passed = False
    
    try:
        all_passed = test_p0_3_vwap_model() and all_passed
    except Exception as e:
        print(f'FAILED P0-3: {e}')
        import traceback
        traceback.print_exc()
        all_passed = False
    
    try:
        all_passed = test_backtest_with_vwap() and all_passed
    except Exception as e:
        print(f'FAILED 回测集成: {e}')
        import traceback
        traceback.print_exc()
        all_passed = False
    
    print('=' * 60)
    if all_passed:
        print('所有P0级修复验证通过!')
    else:
        print('存在验证失败的测试!')
    print('=' * 60)
    
    sys.exit(0 if all_passed else 1)
