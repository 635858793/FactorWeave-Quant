#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证：完整字段 vs 缺失字段的回测性能对比
"""
import time
import numpy as np
import pandas as pd
from backtest.unified_backtest_engine import UnifiedBacktestEngine

def create_incomplete_data(size):
    """仅包含 close + signal"""
    dates = pd.date_range('2020-01-01', periods=size, freq='5min')
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(size) * 0.5)
    signals = np.random.choice([0, 1, -1], size=size, p=[0.7, 0.2, 0.1])
    signals[0] = 0
    
    data = pd.DataFrame({
        'date': dates,
        'close': prices,
        'signal': signals
    })
    data.set_index('date', inplace=True)
    return data

def create_complete_data(size):
    """包含完整 OHLC + signal"""
    dates = pd.date_range('2020-01-01', periods=size, freq='5min')
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(size) * 0.5)
    signals = np.random.choice([0, 1, -1], size=size, p=[0.7, 0.2, 0.1])
    signals[0] = 0
    
    data = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': prices * 1.01,
        'low': prices * 0.99,
        'close': prices,
        'volume': 1000000,
        'signal': signals
    })
    data.set_index('date', inplace=True)
    return data

def test_backtest_performance():
    """测试回测性能"""
    sizes = [10000, 50000, 100000, 250000]
    
    print("\n" + "="*80)
    print("回测性能对比：完整字段 vs 缺失字段")
    print("="*80)
    
    for size in sizes:
        print(f"\n{'='*60}")
        print(f"数据量: {size:,} 条")
        print("="*60)
        
        # 测试1: 缺失字段数据
        data_incomplete = create_incomplete_data(size)
        
        engine1 = UnifiedBacktestEngine(
            use_vectorized_engine=True,
            auto_select_engine=True
        )
        
        start = time.time()
        result1 = engine1.run_backtest(
            data=data_incomplete,
            signal_col='signal',
            price_col='close',
            initial_capital=100000,
            commission_pct=0.001,
            slippage_pct=0.001
        )
        time_incomplete = time.time() - start
        print(f"缺失字段 (仅close+signal): {time_incomplete*1000:>10.2f}ms")
        
        # 测试2: 完整字段数据
        data_complete = create_complete_data(size)
        
        engine2 = UnifiedBacktestEngine(
            use_vectorized_engine=True,
            auto_select_engine=True
        )
        
        start = time.time()
        result2 = engine2.run_backtest(
            data=data_complete,
            signal_col='signal',
            price_col='close',
            initial_capital=100000,
            commission_pct=0.001,
            slippage_pct=0.001
        )
        time_complete = time.time() - start
        print(f"完整字段 (OHLC+volume+signal): {time_complete*1000:>10.2f}ms")
        
        # 对比
        diff = time_incomplete - time_complete
        print(f"\n性能差异: {diff*1000:.2f}ms ({diff/time_complete*100:.1f}%)")

if __name__ == '__main__':
    test_backtest_performance()
