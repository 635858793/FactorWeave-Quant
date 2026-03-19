"""
回测引擎性能测试脚本
验证不同数据量下的性能表现
"""

import sys
import os
import time
import numpy as np
import pandas as pd

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_test_data(n_rows: int, seed: int = 42) -> pd.DataFrame:
    """创建测试数据"""
    np.random.seed(seed)
    
    dates = pd.date_range('2020-01-01', periods=n_rows, freq='5min')
    
    # 生成随机价格数据
    base_price = 100
    prices = base_price + np.cumsum(np.random.randn(n_rows) * 0.5)
    prices = np.maximum(prices, 10)  # 确保价格为正
    
    # 生成随机信号 (1: 买入, -1: 卖出, 0: 持有)
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


def test_jit_performance():
    """测试 JIT 向量化引擎性能"""
    print("\n" + "="*60)
    print("测试1: JIT 向量化引擎性能测试")
    print("="*60)
    
    from backtest.backtest_optimizer import VectorizedBacktestEngine, BacktestOptimizationLevel
    
    engine = VectorizedBacktestEngine(BacktestOptimizationLevel.PROFESSIONAL)
    
    test_sizes = [1000, 5000, 10000, 25000, 50000, 100000, 250000, 500000, 1000000]
    results = []
    
    for size in test_sizes:
        print(f"\n测试数据量: {size:,} 条...")
        
        # 创建数据
        data = create_test_data(size)
        
        # 第一次运行（包含JIT编译时间）
        start = time.time()
        result = engine.run_vectorized_backtest(data, signal_col='signal', price_col='close')
        first_time = time.time() - start
        
        # 第二次运行（纯计算时间，JIT已编译）
        start = time.time()
        result = engine.run_vectorized_backtest(data, signal_col='signal', price_col='close')
        second_time = time.time() - start
        
        # 内存估算 (MB)
        memory_mb = (data.memory_usage(deep=True).sum() + 
                    result.memory_usage(deep=True).sum()) / 1024 / 1024
        
        results.append({
            'size': size,
            'first_time': first_time,
            'second_time': second_time,
            'memory_mb': memory_mb,
            'rows_per_sec': size / second_time if second_time > 0 else 0
        })
        
        print(f"  首次运行: {first_time*1000:.2f}ms")
        print(f"  二次运行: {second_time*1000:.2f}ms")
        print(f"  内存占用: ~{memory_mb:.1f}MB")
        print(f"  处理速度: {size/second_time:,.0f} 条/秒")
    
    return results


def test_memory_optimized_engine():
    """测试内存优化引擎性能"""
    print("\n" + "="*60)
    print("测试2: 内存优化引擎性能测试")
    print("="*60)
    
    from backtest.backtest_optimizer import MemoryOptimizedBacktestEngine, BacktestOptimizationLevel
    
    engine = MemoryOptimizedBacktestEngine(
        chunk_size=10000, 
        optimization_level=BacktestOptimizationLevel.PROFESSIONAL
    )
    
    test_sizes = [10000, 50000, 100000, 250000, 500000]
    results = []
    
    for size in test_sizes:
        print(f"\n测试数据量: {size:,} 条...")
        
        # 创建数据
        data = create_test_data(size)
        
        # 定义策略函数
        def strategy_func(chunk_data, **kwargs):
            return chunk_data
        
        # 运行分块回测
        start = time.time()
        result = engine.run_chunked_backtest(data, strategy_func)
        elapsed = time.time() - start
        
        # 内存估算
        memory_mb = data.memory_usage(deep=True).sum() / 1024 / 1024
        
        results.append({
            'size': size,
            'time': elapsed,
            'memory_mb': memory_mb,
            'rows_per_sec': size / elapsed if elapsed > 0 else 0
        })
        
        print(f"  运行时间: {elapsed*1000:.2f}ms")
        print(f"  内存占用: ~{memory_mb:.1f}MB")
        print(f"  处理速度: {size/elapsed:,.0f} 条/秒")
    
    return results


def test_sampling_accuracy():
    """测试智能采样对精度的影响"""
    print("\n" + "="*60)
    print("测试3: 智能采样精度测试")
    print("="*60)
    
    from backtest.backtest_optimizer import VectorizedBacktestEngine, BacktestOptimizationLevel
    
    engine = VectorizedBacktestEngine(BacktestOptimizationLevel.PROFESSIONAL)
    
    # 创建基准数据 (10万条)
    base_size = 100000
    print(f"\n基准数据量: {base_size:,} 条")
    base_data = create_test_data(base_size)
    
    # 基准测试
    start = time.time()
    base_result = engine.run_vectorized_backtest(base_data, signal_col='signal', price_col='close')
    base_time = time.time() - start
    
    base_return = (base_result['capital'].iloc[-1] / base_result['capital'].iloc[0] - 1) * 100
    base_trades = np.sum(np.diff(base_result['position'].values) != 0)
    
    print(f"基准运行时间: {base_time*1000:.2f}ms")
    print(f"基准收益率: {base_return:.2f}%")
    print(f"基准交易次数: {base_trades}")
    
    # 测试不同采样率
    print("\n采样测试:")
    sample_ratios = [0.8, 0.5, 0.3, 0.2, 0.1]
    
    for ratio in sample_ratios:
        sample_size = int(base_size * ratio)
        
        # 等间隔采样 + 保留最后一条
        indices = np.linspace(0, base_size - 1, sample_size, dtype=int)
        indices[-1] = base_size - 1
        
        sampled_data = base_data.iloc[indices].copy()
        
        # 运行采样后的回测
        start = time.time()
        sampled_result = engine.run_vectorized_backtest(sampled_data, signal_col='signal', price_col='close')
        sample_time = time.time() - start
        
        sampled_return = (sampled_result['capital'].iloc[-1] / sampled_result['capital'].iloc[0] - 1) * 100
        sampled_trades = np.sum(np.diff(sampled_result['position'].values) != 0)
        
        # 计算误差
        return_diff = abs(sampled_return - base_return)
        trade_diff = abs(sampled_trades - base_trades)
        
        print(f"\n  采样比例: {ratio*100:.0f}% (样本数: {sample_size:,})")
        print(f"    运行时间: {sample_time*1000:.2f}ms (加速: {base_time/sample_time:.1f}x)")
        print(f"    收益率: {sampled_return:.2f}% (误差: {return_diff:.2f}%)")
        print(f"    交易次数: {sampled_trades} (差异: {trade_diff})")


def test_unified_engine():
    """测试统一回测引擎"""
    print("\n" + "="*60)
    print("测试4: 统一回测引擎综合测试")
    print("="*60)
    
    from backtest.unified_backtest_engine import UnifiedBacktestEngine
    
    test_sizes = [1000, 10000, 50000, 100000, 250000]
    
    for size in test_sizes:
        print(f"\n测试数据量: {size:,} 条...")
        
        # 创建数据
        data = create_test_data(size)
        
        # 测试无高级功能
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
        elapsed_no_risk = time.time() - start
        
        print(f"  无高级功能: {elapsed_no_risk*1000:.2f}ms")
        
        # 测试有高级功能
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
        elapsed_with_risk = time.time() - start
        
        print(f"  有高级功能: {elapsed_with_risk*1000:.2f}ms")


def main():
    """主函数"""
    print("\n" + "="*60)
    print("回测引擎性能测试")
    print("="*60)
    
    # 预热 JIT
    print("\n预热 JIT 编译...")
    warmup_data = create_test_data(1000)
    from backtest.backtest_optimizer import VectorizedBacktestEngine, BacktestOptimizationLevel
    warmup_engine = VectorizedBacktestEngine(BacktestOptimizationLevel.PROFESSIONAL)
    warmup_engine.run_vectorized_backtest(warmup_data, signal_col='signal', price_col='close')
    print("预热完成\n")
    
    # 测试1: JIT 性能
    jit_results = test_jit_performance()
    
    # 测试2: 内存优化引擎
    mem_results = test_memory_optimized_engine()
    
    # 测试3: 采样精度
    test_sampling_accuracy()
    
    # 测试4: 统一引擎
    test_unified_engine()
    
    # 输出总结
    print("\n" + "="*60)
    print("性能测试总结")
    print("="*60)
    print("\n数据量与JIT性能参考表:")
    print(f"{'数据量':>12} | {'JIT时间(ms)':>12} | {'处理速度(条/秒)':>18}")
    print("-" * 50)
    for r in jit_results:
        print(f"{r['size']:>12,} | {r['second_time']*1000:>12.2f} | {r['rows_per_sec']:>18,.0f}")
    
    print("\n建议:")
    print("  - < 50,000 条: 直接使用向量化引擎 (JIT)")
    print("  - 50,000 ~ 100,000 条: 根据需求选择引擎")
    print("  - > 100,000 条: 建议使用智能采样")


if __name__ == '__main__':
    main()
