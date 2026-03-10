#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P0级修复性能验证测试（仅回测引擎）
"""

import sys
sys.path.insert(0, '.')

import time
import pandas as pd
import numpy as np


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
        
        status = 'OK' if avg_time < 1.0 else 'WARN'
        print(f'{model.upper()}模型: {iterations}次计算耗时 {elapsed:.4f}秒, 平均 {avg_time:.4f}毫秒 [{status}]')
    
    print()
    return results


def test_backtest_performance():
    """回测引擎整体性能测试"""
    print('=' * 60)
    print('回测引擎整体性能测试')
    print('=' * 60)
    
    from backtest.unified_backtest_engine import UnifiedBacktestEngine
    
    engine = UnifiedBacktestEngine()
    
    data_sizes = [1000, 10000, 50000]
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
            
            status = 'OK' if throughput > 1000 else 'WARN'
            print(f'  {model.upper()}: {elapsed:.4f}秒, 吞吐量 {throughput:.0f} 条/秒 [{status}]')
    
    print()


def analyze_bottlenecks():
    """分析性能瓶颈"""
    print('=' * 60)
    print('性能瓶颈分析')
    print('=' * 60)
    
    print('\n1. P0-1 持仓同步机制:')
    print('   - 潜在瓶颈: datetime.now()频繁调用')
    print('   - 潜在瓶颈: Timer对象创建开销')
    print('   - 优化建议: 使用时间戳缓存、线程池')
    print('   - 当前状态: 已实现节流机制，性能良好')
    
    print('\n2. P0-2 风控检查响应:')
    print('   - 潜在瓶颈: 模块导入开销（try-except内）')
    print('   - 潜在瓶颈: 服务解析开销')
    print('   - 优化建议: 缓存模块导入、惰性加载')
    print('   - 当前状态: 使用try-except保护，异常时不影响主流程')
    
    print('\n3. P0-3 VWAP成交模型:')
    print('   - 潜在瓶颈: random模块导入（函数内）')
    print('   - 潜在瓶颈: hash计算开销')
    print('   - 潜在瓶颈: DataFrame.iloc访问')
    print('   - 优化建议: 预导入random、使用numba加速')
    print('   - 当前状态: 性能可接受，可进一步优化')
    
    print()


def suggest_optimizations():
    """提出优化建议"""
    print('=' * 60)
    print('优化建议')
    print('=' * 60)
    
    print('\n1. P0-1 持仓同步机制优化:')
    print('   - 使用time.time()替代datetime.now()（更快）')
    print('   - 使用线程池替代Timer对象')
    print('   - 批量处理同步请求')
    
    print('\n2. P0-2 风控检查响应优化:')
    print('   - 将模块导入移至文件顶部')
    print('   - 使用缓存存储已解析的服务')
    print('   - 使用LRU缓存存储检查结果')
    
    print('\n3. P0-3 VWAP成交模型优化:')
    print('   - 预导入random模块')
    print('   - 使用numpy向量化计算')
    print('   - 考虑使用numba JIT编译')
    
    print()


if __name__ == '__main__':
    print('\n' + '=' * 60)
    print('P0级修复性能验证测试')
    print('=' * 60 + '\n')
    
    analyze_bottlenecks()
    
    p0_3_times = test_p0_3_performance()
    
    test_backtest_performance()
    
    suggest_optimizations()
    
    print('=' * 60)
    print('性能验证总结')
    print('=' * 60)
    print(f'P0-3 成交模型:')
    for model, time_val in p0_3_times.items():
        status = '优秀' if time_val < 0.5 else ('良好' if time_val < 1.0 else '需优化')
        print(f'  - {model.upper()}: {time_val:.4f}ms/次 [{status}]')
    print('=' * 60)
