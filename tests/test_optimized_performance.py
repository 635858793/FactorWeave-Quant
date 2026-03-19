"""
修复后的回测引擎性能测试脚本
验证优化效果
"""

import sys
import os
import time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def create_test_data(n_rows: int, seed: int = 42) -> pd.DataFrame:
    """创建测试数据"""
    np.random.seed(seed)
    dates = pd.date_range('2020-01-01', periods=n_rows, freq='5min')
    base_price = 100
    prices = base_price + np.cumsum(np.random.randn(n_rows) * 0.5)
    prices = np.maximum(prices, 10)
    signals = np.random.choice([-1, 0, 1], size=n_rows, p=[0.1, 0.8, 0.1])
    
    data = pd.DataFrame({
        'date': dates,
        'open': prices * (1 + np.random.randn(n_rows) * 0.001),
        'high': prices * (1 + np.abs(np.random.randn(n_rows) * 0.002)),
        'low': prices * (1 - np.abs(np.random.randn(n_rows) * 0.002)),
        'close': prices,
        'volume': np.random.randint(1000, 100000, n_rows),
        'signal': signals
    })
    data.set_index('date', inplace=True)
    return data


def test_optimized_engine():
    """测试优化后的统一引擎"""
    print("\n" + "="*60)
    print("测试: 优化后的统一回测引擎 (JIT + 风控)")
    print("="*60)
    
    from backtest.unified_backtest_engine import UnifiedBacktestEngine
    
    test_sizes = [1000, 10000, 50000, 100000, 250000, 500000]
    
    for size in test_sizes:
        print(f"\n数据量: {size:,} 条")
        
        data = create_test_data(size)
        
        # 测试1: 无高级功能
        engine = UnifiedBacktestEngine(
            use_vectorized_engine=True,
            auto_select_engine=True,
            execution_model='fixed'
        )
        
        start = time.time()
        result = engine.run_backtest(
            data,
            signal_col='signal',
            price_col='close',
            initial_capital=100000,
            stop_loss_pct=None,
            take_profit_pct=None,
            max_holding_periods=None
        )
        time_no_risk = time.time() - start
        
        # 测试2: 有高级功能 (止损/止盈/持有期)
        engine2 = UnifiedBacktestEngine(
            use_vectorized_engine=True,
            auto_select_engine=True,
            execution_model='fixed'
        )
        
        start = time.time()
        result2 = engine2.run_backtest(
            data,
            signal_col='signal',
            price_col='close',
            initial_capital=100000,
            stop_loss_pct=0.05,
            take_profit_pct=0.10,
            max_holding_periods=10
        )
        time_with_risk = time.time() - start
        
        print(f"  无风控: {time_no_risk*1000:>10.2f}ms")
        print(f"  有风控: {time_with_risk*1000:>10.2f}ms")
        
        # 对比之前
        if size == 250000:
            old_time = 172490
            speedup = old_time / (time_with_risk * 1000)
            print(f"  相比之前提速: {speedup:.0f}x!")


def test_risk_functions():
    """测试风控功能是否正常工作"""
    print("\n" + "="*60)
    print("测试: 风控功能验证")
    print("="*60)
    
    from backtest.unified_backtest_engine import UnifiedBacktestEngine
    
    # 测试1: 止损功能 - 震荡下跌市场
    print("\n--- 测试1: 止损功能 (震荡下跌) ---")
    np.random.seed(42)
    n = 5000
    dates = pd.date_range('2020-01-01', periods=n, freq='5min')
    
    prices = np.zeros(n)
    prices[0] = 100
    for i in range(1, n):
        if i % 50 < 25:
            prices[i] = prices[i-1] - 2
        else:
            prices[i] = prices[i-1] + 1
    
    signals = np.zeros(n)
    signals[100] = 1
    
    data = pd.DataFrame({
        'date': dates,
        'close': prices,
        'signal': signals
    })
    data.set_index('date', inplace=True)
    
    engine = UnifiedBacktestEngine(use_vectorized_engine=True)
    result = engine.run_backtest(
        data,
        signal_col='signal',
        price_col='close',
        initial_capital=100000,
        stop_loss_pct=0.03,
        take_profit_pct=None,
        max_holding_periods=None
    )
    
    if 'exit_reason' in result.columns:
        stop_loss_count = np.sum(result['exit_reason'] == 1)
        print(f"止损退出次数: {stop_loss_count}")
    
    final_capital = result['capital'].iloc[-1]
    print(f"最终资金: {final_capital:,.2f}")
    
    # 测试2: 止盈功能 - 上涨后回落
    print("\n--- 测试2: 止盈功能 (上涨后回落) ---")
    np.random.seed(42)
    prices2 = np.zeros(n)
    prices2[0] = 100
    for i in range(1, n):
        if i < 2000:
            prices2[i] = prices2[i-1] + 1
        else:
            prices2[i] = prices2[i-1] - 0.5
    
    signals2 = np.zeros(n)
    signals2[100] = 1
    
    data2 = pd.DataFrame({
        'date': dates,
        'close': prices2,
        'signal': signals2
    })
    data2.set_index('date', inplace=True)
    
    engine2 = UnifiedBacktestEngine(use_vectorized_engine=True)
    result2 = engine2.run_backtest(
        data2,
        signal_col='signal',
        price_col='close',
        initial_capital=100000,
        stop_loss_pct=None,
        take_profit_pct=0.10,
        max_holding_periods=None
    )
    
    if 'exit_reason' in result2.columns:
        take_profit_count = np.sum(result2['exit_reason'] == 2)
        print(f"止盈退出次数: {take_profit_count}")
    
    final_capital2 = result2['capital'].iloc[-1]
    print(f"最终资金: {final_capital2:,.2f}")
    
    # 测试3: 最大持有期
    print("\n--- 测试3: 最大持有期 (长期持有) ---")
    np.random.seed(42)
    prices3 = 100 + np.cumsum(np.random.randn(n) * 0.1)
    
    signals3 = np.zeros(n)
    signals3[100] = 1
    
    data3 = pd.DataFrame({
        'date': dates,
        'close': prices3,
        'signal': signals3
    })
    data3.set_index('date', inplace=True)
    
    engine3 = UnifiedBacktestEngine(use_vectorized_engine=True)
    result3 = engine3.run_backtest(
        data3,
        signal_col='signal',
        price_col='close',
        initial_capital=100000,
        stop_loss_pct=None,
        take_profit_pct=None,
        max_holding_periods=50
    )
    
    if 'exit_reason' in result3.columns:
        max_holding_count = np.sum(result3['exit_reason'] == 3)
        print(f"持有期退出次数: {max_holding_count}")
    
    if 'holding_periods' in result3.columns:
        max_hp = result3['holding_periods'].max()
        print(f"最大持有期: {max_hp}")
    
    print("\n风控功能验证完成!")


def main():
    print("\n" + "="*60)
    print("优化后性能验证测试")
    print("="*60)
    
    # 预热
    print("\n预热 JIT...")
    warmup_data = create_test_data(1000)
    from backtest.unified_backtest_engine import UnifiedBacktestEngine
    warmup_engine = UnifiedBacktestEngine(use_vectorized_engine=True)
    warmup_engine.run_backtest(warmup_data, signal_col='signal', price_col='close')
    print("预热完成\n")
    
    # 测试优化后的引擎
    test_optimized_engine()
    
    # 测试风控功能
    test_risk_functions()
    
    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)


if __name__ == '__main__':
    main()
