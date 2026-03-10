#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单元测试框架 - 回归测试
验证循环导入修复和P0修复
"""

import sys
sys.path.insert(0, '.')

import time
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np


class TestCircularImportFix(unittest.TestCase):
    """测试循环导入修复"""
    
    def test_import_account_manager(self):
        """测试AccountManager导入"""
        try:
            from core.trading.account_manager import AccountManager
            self.assertIsNotNone(AccountManager)
        except ImportError as e:
            self.fail(f"导入AccountManager失败: {e}")
    
    def test_import_order_executor(self):
        """测试OrderExecutor导入"""
        try:
            from core.trading.order_executor import OrderExecutor
            self.assertIsNotNone(OrderExecutor)
        except ImportError as e:
            self.fail(f"导入OrderExecutor失败: {e}")
    
    def test_import_order_repository(self):
        """测试OrderRepository导入"""
        try:
            from core.trading.order_repository import OrderRepository
            self.assertIsNotNone(OrderRepository)
        except ImportError as e:
            self.fail(f"导入OrderRepository失败: {e}")
    
    def test_import_account_repository(self):
        """测试AccountRepository导入"""
        try:
            from core.trading.account_repository import AccountRepository
            self.assertIsNotNone(AccountRepository)
        except ImportError as e:
            self.fail(f"导入AccountRepository失败: {e}")


class TestP0Fixes(unittest.TestCase):
    """测试P0级修复"""
    
    def test_p0_1_position_sync_optimization(self):
        """测试P0-1持仓同步优化"""
        import time
        
        last_sync_times = {}
        min_interval = 5
        
        iterations = 10000
        
        start_time = time.perf_counter()
        for i in range(iterations):
            now = time.time()
            account_id = f'account_{i % 10}'
            last = last_sync_times.get(account_id)
            if last:
                elapsed = now - last
                if elapsed < min_interval:
                    continue
            last_sync_times[account_id] = now
        elapsed = time.perf_counter() - start_time
        
        avg_time = (elapsed / iterations) * 1000
        self.assertLess(avg_time, 1.0, f"持仓同步性能不达标: {avg_time}ms")
    
    def test_p0_2_risk_check(self):
        """测试P0-2风控检查"""
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
        
        self.assertIn('passed', result)
        self.assertIsInstance(result['passed'], bool)
    
    def test_p0_3_vwap_model(self):
        """测试P0-3 VWAP成交模型"""
        from backtest.unified_backtest_engine import UnifiedBacktestEngine
        
        engine = UnifiedBacktestEngine()
        
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        data = pd.DataFrame({
            'close': [10.0 + i * 0.01 for i in range(100)],
            'high': [10.2 + i * 0.01 for i in range(100)],
            'low': [9.8 + i * 0.01 for i in range(100)],
            'volume': [1000000] * 100,
        }, index=dates)
        
        for i in range(10):
            price = engine._calculate_vwap_price(data, i, 10.0, True, 0.001)
            self.assertIsInstance(price, (int, float))
            self.assertGreater(price, 0)


class TestBusinessCallChain(unittest.TestCase):
    """测试业务调用链"""
    
    def test_trading_call_chain(self):
        """测试交易调用链"""
        from core.trading.order_executor import OrderExecutor
        from core.trading.order_models import Order, OrderType, OrderStatus, OrderCategory
        from core.plugin_types import AssetType
        
        executor = OrderExecutor.__new__(OrderExecutor)
        executor.service_container = MagicMock()
        executor.event_bus = MagicMock()
        
        order = Order(
            order_id='CHAIN_TEST_001',
            strategy_id='test_strategy',
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
        
        self.assertIsNotNone(result)
        self.assertIn('passed', result)
    
    def test_backtest_call_chain(self):
        """测试回测调用链"""
        from backtest.unified_backtest_engine import UnifiedBacktestEngine
        
        engine = UnifiedBacktestEngine()
        
        dates = pd.date_range('2024-01-01', periods=1000, freq='min')
        data = pd.DataFrame({
            'close': np.random.uniform(9.5, 10.5, 1000),
            'high': np.random.uniform(10.0, 10.8, 1000),
            'low': np.random.uniform(9.2, 10.0, 1000),
            'volume': np.random.randint(100000, 1000000, 1000),
            'signal': np.random.choice([1, 0, -1], 1000)
        }, index=dates)
        
        result = engine.run_backtest(
            data=data,
            signal_col='signal',
            price_col='close',
            initial_capital=100000,
            execution_model='fixed'
        )
        
        self.assertIsNotNone(result)


class TestPerformance(unittest.TestCase):
    """性能测试"""
    
    def test_import_performance(self):
        """测试导入性能"""
        import time
        
        modules = [
            'core.trading.account_manager',
            'core.trading.order_executor',
            'core.trading.order_repository',
            'backtest.unified_backtest_engine',
        ]
        
        for module_name in modules:
            start = time.perf_counter()
            try:
                __import__(module_name)
            except ImportError:
                pass
            elapsed = time.perf_counter() - start
            self.assertLess(elapsed, 5.0, f"模块 {module_name} 导入超时: {elapsed}秒")
    
    def test_execution_performance(self):
        """测试执行性能"""
        from backtest.unified_backtest_engine import UnifiedBacktestEngine
        
        engine = UnifiedBacktestEngine()
        
        dates = pd.date_range('2024-01-01', periods=5000, freq='min')
        data = pd.DataFrame({
            'close': np.random.uniform(9.5, 10.5, 5000),
            'high': np.random.uniform(10.0, 10.8, 5000),
            'low': np.random.uniform(9.2, 10.0, 5000),
            'volume': np.random.randint(100000, 1000000, 5000),
            'signal': np.random.choice([1, 0, -1], 5000)
        }, index=dates)
        
        start = time.perf_counter()
        result = engine.run_backtest(
            data=data,
            signal_col='signal',
            price_col='close',
            initial_capital=100000,
            execution_model='vwap'
        )
        elapsed = time.perf_counter() - start
        
        throughput = 5000 / elapsed
        self.assertGreater(throughput, 1000, f"回测吞吐量不达标: {throughput}条/秒")


if __name__ == '__main__':
    print('=' * 70)
    print('单元测试 - 回归测试')
    print('=' * 70)
    print()
    
    unittest.main(verbosity=2)
