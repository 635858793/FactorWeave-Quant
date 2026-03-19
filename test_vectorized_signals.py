#!/usr/bin/env python3
"""
向量化信号生成测试脚本

测试向量化优化方案的性能提升
"""

import pandas as pd
import numpy as np
from pathlib import Path
import time
import sys
import logging

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from plugins.strategies.adaptive_strategy import AdaptivePandasStrategy
from loguru import logger

# 配置日志
logging.basicConfig(level=logging.INFO)
logger.remove()
logger.add(sys.stdout, level=logging.INFO, format="{time:HH:mm:ss.SSS} | {level} | {message}")


def generate_test_data(n_bars: int = 1000) -> pd.DataFrame:
    """生成测试数据"""
    np.random.seed(42)
    
    # 生成随机价格序列
    close = 100 + np.cumsum(np.random.randn(n_bars) * 0.5)
    open_price = close + np.random.randn(n_bars) * 0.1
    high = np.maximum(open_price, close) + np.abs(np.random.randn(n_bars) * 0.2)
    low = np.minimum(open_price, close) - np.abs(np.random.randn(n_bars) * 0.2)
    volume = np.random.randint(1000, 10000, n_bars)
    
    # 创建 DatetimeIndex
    dates = pd.date_range('2024-01-01', periods=n_bars, freq='D')
    
    return pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)


def test_loop_version(strategy, data: pd.DataFrame) -> tuple:
    """测试循环版本性能"""
    # 计算指标
    indicators = strategy._calculate_technical_indicators(data)
    
    # 循环版本信号生成
    start_time = time.time()
    signals = strategy._loop_generate_signals(data, indicators)
    elapsed = time.time() - start_time
    
    return signals, elapsed


def test_vectorized_version(strategy, data: pd.DataFrame) -> tuple:
    """测试向量化版本性能"""
    # 计算指标
    indicators = strategy._calculate_technical_indicators(data)
    
    # 向量化版本信号生成
    start_time = time.time()
    signals = strategy._vectorized_generate_signals(data, indicators)
    elapsed = time.time() - start_time
    
    return signals, elapsed


def compare_signals(signals_loop, signals_vec) -> bool:
    """比较两种版本的信号一致性"""
    # 比较信号数量
    if len(signals_loop) != len(signals_vec):
        print(f"  ⚠️ 信号数量不一致：循环版={len(signals_loop)}, 向量化版={len(signals_vec)}")
        return False
    
    # 比较信号类型和时间戳
    for i, (s1, s2) in enumerate(zip(signals_loop, signals_vec)):
        if s1.timestamp != s2.timestamp:
            print(f"  ⚠️ 信号{i}时间戳不一致：{s1.timestamp} vs {s2.timestamp}")
            return False
        if s1.signal_type != s2.signal_type:
            print(f"  ⚠️ 信号{i}类型不一致：{s1.signal_type} vs {s2.signal_type}")
            return False
    
    print(f"  ✅ 信号一致性检查通过（共{len(signals_loop)}个信号）")
    return True


def main():
    """主测试函数"""
    print("="*80)
    print("向量化信号生成性能测试")
    print("="*80)
    
    # 创建策略实例
    strategy = AdaptivePandasStrategy()
    
    # 测试不同数据量
    data_sizes = [243, 500, 1000, 2000]
    
    results = []
    
    for size in data_sizes:
        print(f"\n{'='*80}")
        print(f"测试数据量：{size} 点")
        print(f"{'='*80}")
        
        # 生成测试数据
        data = generate_test_data(size)
        
        # 测试循环版本
        print("\n[1/2] 测试循环版本...")
        signals_loop, time_loop = test_loop_version(strategy, data)
        print(f"  循环版本耗时：{time_loop*1000:.2f} ms")
        print(f"  生成信号数：{len(signals_loop)}")
        
        # 测试向量化版本
        print("\n[2/2] 测试向量化版本...")
        signals_vec, time_vec = test_vectorized_version(strategy, data)
        print(f"  向量化版本耗时：{time_vec*1000:.2f} ms")
        print(f"  生成信号数：{len(signals_vec)}")
        
        # 比较结果
        print("\n[结果对比]")
        speedup = time_loop / time_vec if time_vec > 0 else float('inf')
        print(f"  性能提升：{speedup:.2f}x")
        
        # 一致性检查
        consistent = compare_signals(signals_loop, signals_vec)
        
        # 保存结果
        results.append({
            'data_size': size,
            'loop_time': time_loop,
            'vectorized_time': time_vec,
            'speedup': speedup,
            'signals_count': len(signals_loop),
            'consistent': consistent
        })
    
    # 汇总报告
    print(f"\n{'='*80}")
    print("性能测试汇总报告")
    print(f"{'='*80}")
    print(f"{'数据量':<10} {'循环版 (ms)':<15} {'向量化 (ms)':<15} {'提升倍数':<10} {'一致性':<10}")
    print(f"{'-'*80}")
    
    for r in results:
        status = "✅" if r['consistent'] else "❌"
        print(f"{r['data_size']:<10} {r['loop_time']*1000:<15.2f} {r['vectorized_time']*1000:<15.2f} {r['speedup']:<10.2f}x {status:<10}")
    
    # 计算平均提升
    avg_speedup = np.mean([r['speedup'] for r in results])
    all_consistent = all(r['consistent'] for r in results)
    
    print(f"\n平均性能提升：{avg_speedup:.2f}x")
    print(f"信号一致性：{'✅ 全部通过' if all_consistent else '❌ 存在差异'}")
    
    # 评估是否达标
    if avg_speedup >= 5.0 and all_consistent:
        print(f"\n🎉 向量化优化成功！性能提升 {avg_speedup:.2f}x，信号一致性 100%")
        return 0
    else:
        print(f"\n⚠️ 向量化优化未达标，需要进一步优化")
        return 1


if __name__ == "__main__":
    sys.exit(main())
