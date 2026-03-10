#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P0级修复性能验证与优化测试（简化版）
"""

import sys
sys.path.insert(0, '.')

import time
import pandas as pd
import numpy as np


def test_p0_2_performance():
    """P0-2 风控检查响应性能测试"""
    print('=' * 60)
    print('P0-2: 风控检查响应性能测试')
    print('=' * 60)
    
    from core.trading.order_executor import OrderExecutor
    from core.trading.order_models import Order, OrderType, OrderStatus, OrderCategory
    from core.plugin_types import AssetType
    from datetime import datetime
    from unittest.mock import MagicMock
    
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
    
    iterations = 10000
    start_time = time.perf_counter()
    
    for i in range(iterations):
        result = executor._pre_trade_risk_check(order)
    
    elapsed = time.perf_counter() - start_time
    avg_time = (elapsed / iterations) * 1000
    
    print(f'执行 {iterations} 次风控检查耗时: {elapsed:.4f}秒')
    print(f'平均每次检查耗时: {avg_time:.4f}毫秒')
    print(f'吞吐量: {iterations / elapsed:.0f} 次/秒')
    
    if avg_time < 0.1:
        print('OK 性能优秀 (<0.1ms)')
    elif avg_time < 1.0:
        print('OK 性能良好 (<1ms)')
    else:
        print('WARN 性能需要优化 (>1ms)')
    
    print()
    return avg_time


def test_p0_3_performance():
    """P0-3 VWAP成交模型性能测试"""
    print('=' * 60)
    print('P0-3: VWAP成交模型性能测试')
    print('=' * 60)
    
    from backtest.unified_backtest_engine import UnifiedBacktestEngine
    
    engine = UnifiedBacktestEngine()
    
    dates = pd.date_range('2024-01-01', periods=1000, freq='D')
    data = pd.DataFrame({
        'close': [10.0 + i * 0.01 for i in range(1000)],
        'high': [10.2 + i * 0.01 for i in range(1000)],
        'low': [9.8 + i * 0.01 for i in range(1000)],
        'volume': [1000000] * 1000,
        'signal': [1 if i % 5 == 0 else (-1 if i % 5 == 3 else 0) for i in range(1000)]
    }, index=dates)
    
    models = ['fixed', 'vwap', 'random']
    results = {}
    
    for model in models:
        engine._execution_model = model
        
        iterations = 10000
        start_time = time.perf_counter()
        
        for i in range(iterations):
            idx = i % 1000
            if model == 'fixed':
                price = engine._calculate_execution_price(data, idx, 10.0, True, 0.001)
            elif model == 'vwap':
                price = engine._calculate_vwap_price(data, idx, 10.0, True, 0.001)
            else:
                price = engine._calculate_random_price(data, idx, 10.0, True, 0.001)
        
        elapsed = time.perf_counter() - start_time
        avg_time = (elapsed / iterations) * 1000
        results[model] = avg_time
        
        print(f'{model.upper()}模型: {iterations}次计算耗时 {elapsed:.4f}秒, 平均 {avg_time:.4f}毫秒')
    
    print()
    return results


def test_backtest_performance():
    """回测引擎整体性能测试"""
    print('=' * 60)
    print('回测引擎整体性能测试')
    print('=' * 60)
    
    from backtest.unified_backtest_engine import UnifiedBacktestEngine
    
    engine = UnifiedBacktestEngine()
    
    data_sizes = [1000, 10000]
    models = ['fixed', 'vwap']
    
    for size in data_sizes:
        print(f'\n数据量: {size}条')
        print('-' * 40)
        
        dates = pd.date_range('2024-01-01', periods=size, freq='min')
        data = pd.DataFrame({
            'close': np.random.uniform(9.5, 10.5, size),
            'high': np.random.uniform(10.0, 10.8, size),
            'low': np.random.uniform(9.2, 10.0, size),
            'volume': np.random.randint(100000, 1000000, size),
            'signal': np.random.choice([1, 0, -1], size)
        }, index=dates)
        
        for model in models:
            start_time = time.perf_counter()
            
            result = engine.run_backtest(
                data=data,
                signal_col='signal',
                price_col='close',
                initial_capital=100000,
                execution_model=model
            )
            
            elapsed = time.perf_counter() - start_time
            throughput = size / elapsed
            
            print(f'  {model.upper()}: {elapsed:.4f}秒, 吞吐量 {throughput:.0f} 条/秒')
    
    print()


def analyze_and_optimize():
    """分析并应用性能优化"""
    print('=' * 60)
    print('性能优化分析')
    print('=' * 60)
    
    print('\n已识别的性能优化点:')
    print('1. P0-2 风控检查: 移除循环内的模块导入')
    print('2. P0-3 VWAP模型: 预导入random模块')
    print('3. P0-3 VWAP模型: 使用numpy向量化计算')
    print()


if __name__ == '__main__':
    print('\n' + '=' * 60)
    print('P0级修复性能验证测试')
    print('=' * 60 + '\n')
    
    analyze_and_optimize()
    
    p0_2_time = test_p0_2_performance()
    p0_3_times = test_p0_3_performance()
    
    test_backtest_performance()
    
    print('=' * 60)
    print('性能验证总结')
    print('=' * 60)
    print(f'P0-2 风控检查: {p0_2_time:.4f}ms/次')
    print(f'P0-3 成交模型:')
    for model, time_val in p0_3_times.items():
        print(f'  - {model.upper()}: {time_val:.4f}ms/次')
    print('=' * 60)
