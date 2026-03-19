#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能瓶颈分析脚本
"""
import time
import numpy as np
import pandas as pd
from backtest.unified_backtest_engine import UnifiedBacktestEngine

def create_test_data(size):
    """创建测试数据"""
    dates = pd.date_range('2020-01-01', periods=size, freq='5min')
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(size) * 0.5)
    signals = np.random.choice([0, 1, -1], size=size, p=[0.7, 0.2, 0.1])
    signals[0] = 0
    signals[100] = 1
    
    data = pd.DataFrame({
        'date': dates,
        'close': prices,
        'signal': signals
    })
    data.set_index('date', inplace=True)
    return data

def analyze_performance_bottlenecks():
    """分析性能瓶颈"""
    sizes = [10000, 50000, 100000, 250000]
    
    print("\n" + "="*80)
    print("性能瓶颈分析")
    print("="*80)
    
    for size in sizes:
        print(f"\n{'='*60}")
        print(f"数据量: {size:,} 条")
        print("="*60)
        
        data = create_test_data(size)
        
        engine = UnifiedBacktestEngine(
            use_vectorized_engine=True,
            auto_select_engine=True,
            execution_model='fixed'
        )
        
        # 步骤1: 数据预处理
        start = time.time()
        processed = engine._preprocess_and_validate_data(data, 'signal', 'close')
        preprocess_time = time.time() - start
        print(f"1. 数据预处理: {preprocess_time*1000:>10.2f}ms ({preprocess_time/preprocess_time*100:.1f}%)")
        
        # 步骤2: 选择引擎
        start = time.time()
        engine_type = engine._select_optimal_engine(processed, 0.05, 0.10, 10)
        select_time = time.time() - start
        print(f"2. 引擎选择:   {select_time*1000:>10.2f}ms ({select_time/preprocess_time*100:.1f}%)")
        
        # 步骤3: 核心回测
        start = time.time()
        results = engine._run_vectorized_backtest(
            processed, 'signal', 'close', 100000, 1.0,
            0.001, 0.001, 5.0, 0.05, 0.10, 10
        )
        core_time = time.time() - start
        print(f"3. 核心回测:   {core_time*1000:>10.2f}ms ({core_time/preprocess_time*100:.1f}%)")
        
        # 步骤4: 风险指标计算
        start = time.time()
        metrics = engine._calculate_unified_risk_metrics(results, None)
        metrics_time = time.time() - start
        print(f"4. 风险指标:   {metrics_time*1000:>10.2f}ms ({metrics_time/preprocess_time*100:.1f}%)")
        
        # 总时间
        total = preprocess_time + select_time + core_time + metrics_time
        print(f"\n总耗时:       {total*1000:>10.2f}ms")
        
        # 各步骤占比
        print(f"\n耗时占比分析:")
        print(f"  - 数据预处理: {preprocess_time/total*100:.1f}%")
        print(f"  - 引擎选择:   {select_time/total*100:.1f}%")
        print(f"  - 核心回测:   {core_time/total*100:.1f}%")
        print(f"  - 风险指标:   {metrics_time/total*100:.1f}%")

def analyze_jit_overhead():
    """分析JIT函数调用开销"""
    print("\n" + "="*80)
    print("JIT函数调用开销分析")
    print("="*80)
    
    from backtest.backtest_optimizer import VectorizedBacktestEngine
    
    sizes = [10000, 50000, 100000, 250000]
    
    for size in sizes:
        print(f"\n数据量: {size:,}")
        
        data = create_test_data(size)
        prices = data['close'].values
        signals = data['signal'].values
        
        # 第一次调用 (JIT编译)
        start = time.time()
        _ = VectorizedBacktestEngine._vectorized_backtest_with_risk(
            prices, signals, 100000, 1.0, 0.001, 0.001,
            0.05, 0.10, 10
        )
        first_call = time.time() - start
        
        # 第二次调用 (已编译)
        start = time.time()
        _ = VectorizedBacktestEngine._vectorized_backtest_with_risk(
            prices, signals, 100000, 1.0, 0.001, 0.001,
            0.05, 0.10, 10
        )
        second_call = time.time() - start
        
        print(f"  首次调用 (JIT编译): {first_call*1000:.2f}ms")
        print(f"  后续调用 (缓存):    {second_call*1000:.2f}ms")
        if second_call > 0:
            print(f"  加速比:             {first_call/second_call:.1f}x")
        else:
            print(f"  加速比:             >1000x (已缓存)")

def analyze_data_conversion():
    """分析数据转换开销"""
    print("\n" + "="*80)
    print("数据转换开销分析")
    print("="*80)
    
    sizes = [10000, 50000, 100000, 250000]
    
    for size in sizes:
        print(f"\n数据量: {size:,}")
        
        data = create_test_data(size)
        
        # 复制开销
        start = time.time()
        for _ in range(100):
            _ = data.copy()
        copy_time = (time.time() - start) / 100
        print(f"  DataFrame复制: {copy_time*1000:.2f}ms")
        
        # 转换为numpy
        start = time.time()
        for _ in range(100):
            _ = data['close'].values
        to_numpy_time = (time.time() - start) / 100
        print(f"  转换为numpy:  {to_numpy_time*1000:.2f}ms")
        
        # 索引操作
        start = time.time()
        for _ in range(100):
            _ = data.index
        index_time = (time.time() - start) / 100
        print(f"  索引操作:     {index_time*1000:.2f}ms")

if __name__ == '__main__':
    analyze_performance_bottlenecks()
    analyze_jit_overhead()
    analyze_data_conversion()
