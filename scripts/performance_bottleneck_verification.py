"""
性能瓶颈验证脚本
验证统一回测引擎各环节的实际耗时，确认真实存在的性能瓶颈
"""

import time
import numpy as np
import pandas as pd
from datetime import datetime


def generate_test_data(size: int = 100000) -> pd.DataFrame:
    """生成测试数据"""
    np.random.seed(42)
    data = pd.DataFrame({
        'open': np.random.randn(size).cumsum() + 100,
        'high': np.random.randn(size).cumsum() + 102,
        'low': np.random.randn(size).cumsum() + 98,
        'close': np.random.randn(size).cumsum() + 100,
        'volume': np.random.exponential(1000, size)
    })
    signals = np.zeros(size)
    for i in range(20, size):
        if i % 50 == 0:
            signals[i] = 1
        elif i % 100 == 0:
            signals[i] = -1
    data['signal'] = signals
    return data


def test_data_copy():
    """测试数据复制耗时"""
    print("\n" + "=" * 80)
    print("测试1: 数据复制 (data.copy())")
    print("=" * 80)
    
    sizes = [10000, 50000, 100000, 500000, 1000000]
    results = []
    
    for size in sizes:
        data = generate_test_data(size)
        
        times = []
        for _ in range(5):
            start = time.perf_counter()
            copied = data.copy()
            end = time.perf_counter()
            times.append(end - start)
        
        avg_time = sum(times) / len(times)
        speed = (size / 10000) / avg_time
        
        print(f"  数据量: {size:>8}条 | 耗时: {avg_time*1000:>8.2f}ms | 速度: {speed:>8.2f}万条/秒")
        results.append({'size': size, 'time': avg_time, 'speed': speed})
    
    return results


def test_data_validation():
    """测试数据验证耗时"""
    print("\n" + "=" * 80)
    print("测试2: 数据验证 (validate_backtest_data)")
    print("=" * 80)
    
    sizes = [10000, 50000, 100000, 500000, 1000000]
    results = []
    
    for size in sizes:
        data = generate_test_data(size)
        
        try:
            from backtest.backtest_validator import ProfessionalBacktestValidator
            
            validator = ProfessionalBacktestValidator()
            
            times = []
            for _ in range(3):
                start = time.perf_counter()
                result = validator.validate_backtest_data(data, 'signal', 'stock_code')
                end = time.perf_counter()
                times.append(end - start)
            
            avg_time = sum(times) / len(times)
            speed = (size / 10000) / avg_time
            
            print(f"  数据量: {size:>8}条 | 耗时: {avg_time*1000:>8.2f}ms | 速度: {speed:>8.2f}万条/秒")
            results.append({'size': size, 'time': avg_time, 'speed': speed})
            
        except Exception as e:
            print(f"  数据量: {size:>8}条 | 错误: {e}")
            results.append({'size': size, 'time': 0, 'speed': 0, 'error': str(e)})
    
    return results


def test_preprocessing():
    """测试预处理耗时"""
    print("\n" + "=" * 80)
    print("测试3: 数据预处理 (kdata_preprocess)")
    print("=" * 80)
    
    sizes = [10000, 50000, 100000, 500000, 1000000]
    results = []
    
    for size in sizes:
        data = generate_test_data(size)
        
        try:
            from utils.data_preprocessing import kdata_preprocess
            
            times = []
            for _ in range(5):
                start = time.perf_counter()
                processed = kdata_preprocess(data, "测试")
                end = time.perf_counter()
                times.append(end - start)
            
            avg_time = sum(times) / len(times)
            speed = (size / 10000) / avg_time
            
            print(f"  数据量: {size:>8}条 | 耗时: {avg_time*1000:>8.2f}ms | 速度: {speed:>8.2f}万条/秒")
            results.append({'size': size, 'time': avg_time, 'speed': speed})
            
        except Exception as e:
            print(f"  数据量: {size:>8}条 | 错误: {e}")
            results.append({'size': size, 'time': 0, 'speed': 0, 'error': str(e)})
    
    return results


def test_jit_core():
    """测试JIT核心计算耗时"""
    print("\n" + "=" * 80)
    print("测试4: JIT核心计算 (optimized_backtest_core)")
    print("=" * 80)
    
    sizes = [10000, 50000, 100000, 500000, 1000000]
    results = []
    
    for size in sizes:
        data = generate_test_data(size)
        prices = data['close'].astype(float).values
        signals = data['signal'].astype(float).values
        
        try:
            from backtest.jit_optimizer import optimized_backtest_core
            
            times = []
            for _ in range(5):
                start = time.perf_counter()
                positions, capital, returns = optimized_backtest_core(
                    prices, signals, 100000, 1.0, 0.001, 0.001
                )
                end = time.perf_counter()
                times.append(end - start)
            
            avg_time = sum(times) / len(times)
            speed = (size / 10000) / avg_time
            
            print(f"  数据量: {size:>8}条 | 耗时: {avg_time*1000:>8.2f}ms | 速度: {speed:>8.2f}万条/秒")
            results.append({'size': size, 'time': avg_time, 'speed': speed})
            
        except Exception as e:
            print(f"  数据量: {size:>8}条 | 错误: {e}")
            results.append({'size': size, 'time': 0, 'speed': 0, 'error': str(e)})
    
    return results


def test_risk_metrics():
    """测试风险指标计算耗时"""
    print("\n" + "=" * 80)
    print("测试5: 风险指标计算 (_calculate_unified_risk_metrics)")
    print("=" * 80)
    
    sizes = [10000, 50000, 100000, 500000, 1000000]
    results = []
    
    for size in sizes:
        data = generate_test_data(size)
        
        prices = data['close'].astype(float).values
        signals = data['signal'].astype(float).values
        
        try:
            from backtest.jit_optimizer import optimized_backtest_core
            positions, capital, returns = optimized_backtest_core(
                prices, signals, 100000, 1.0, 0.001, 0.001
            )
            
            result_data = data.copy()
            result_data['position'] = positions
            result_data['capital'] = capital
            result_data['returns'] = returns
            result_data['equity'] = capital
            
            from backtest.unified_backtest_engine import UnifiedBacktestEngine
            engine = UnifiedBacktestEngine()
            
            times = []
            for _ in range(3):
                start = time.perf_counter()
                metrics = engine._calculate_unified_risk_metrics(result_data)
                end = time.perf_counter()
                times.append(end - start)
            
            avg_time = sum(times) / len(times)
            speed = (size / 10000) / avg_time
            
            print(f"  数据量: {size:>8}条 | 耗时: {avg_time*1000:>8.2f}ms | 速度: {speed:>8.2f}万条/秒")
            results.append({'size': size, 'time': avg_time, 'speed': speed})
            
        except Exception as e:
            print(f"  数据量: {size:>8}条 | 错误: {e}")
            results.append({'size': size, 'time': 0, 'speed': 0, 'error': str(e)})
    
    return results


def test_full_unified_engine():
    """测试完整统一引擎耗时"""
    print("\n" + "=" * 80)
    print("测试6: 完整统一回测引擎")
    print("=" * 80)
    
    sizes = [10000, 50000, 100000, 500000, 1000000]
    results = []
    
    for size in sizes:
        data = generate_test_data(size)
        
        try:
            from backtest.unified_backtest_engine import UnifiedBacktestEngine
            
            engine = UnifiedBacktestEngine()
            
            times = []
            for _ in range(3):
                start = time.perf_counter()
                result = engine.run_backtest(
                    data=data,
                    signal_col='signal',
                    price_col='close',
                    initial_capital=100000,
                    position_size=1.0,
                    commission_pct=0.001,
                    slippage_pct=0.001
                )
                end = time.perf_counter()
                times.append(end - start)
            
            avg_time = sum(times) / len(times)
            speed = (size / 10000) / avg_time
            
            print(f"  数据量: {size:>8}条 | 耗时: {avg_time*1000:>8.2f}ms | 速度: {speed:>8.2f}万条/秒")
            results.append({'size': size, 'time': avg_time, 'speed': speed})
            
        except Exception as e:
            print(f"  数据量: {size:>8}条 | 错误: {e}")
            results.append({'size': size, 'time': 0, 'speed': 0, 'error': str(e)})
    
    return results


def test_vectorized_engine():
    """测试向量化引擎耗时"""
    print("\n" + "=" * 80)
    print("测试7: 向量化回测引擎")
    print("=" * 80)
    
    sizes = [10000, 50000, 100000, 500000, 1000000]
    results = []
    
    for size in sizes:
        data = generate_test_data(size)
        
        try:
            from backtest.backtest_optimizer import VectorizedBacktestEngine
            
            engine = VectorizedBacktestEngine()
            
            times = []
            for _ in range(3):
                start = time.perf_counter()
                result = engine.run_vectorized_backtest(
                    data=data,
                    signal_col='signal',
                    price_col='close',
                    initial_capital=100000,
                    position_size=1.0,
                    commission_pct=0.001,
                    slippage_pct=0.001
                )
                end = time.perf_counter()
                times.append(end - start)
            
            avg_time = sum(times) / len(times)
            speed = (size / 10000) / avg_time
            
            print(f"  数据量: {size:>8}条 | 耗时: {avg_time*1000:>8.2f}ms | 速度: {speed:>8.2f}万条/秒")
            results.append({'size': size, 'time': avg_time, 'speed': speed})
            
        except Exception as e:
            print(f"  数据量: {size:>8}条 | 错误: {e}")
            results.append({'size': size, 'time': 0, 'speed': 0, 'error': str(e)})
    
    return results


def main():
    print("\n" + "=" * 80)
    print("统一回测引擎性能瓶颈验证测试")
    print("=" * 80)
    print(f"开始时间: {datetime.now()}")
    
    all_results = {}
    
    all_results['data_copy'] = test_data_copy()
    all_results['data_validation'] = test_data_validation()
    all_results['preprocessing'] = test_preprocessing()
    all_results['jit_core'] = test_jit_core()
    all_results['risk_metrics'] = test_risk_metrics()
    all_results['unified_engine'] = test_full_unified_engine()
    all_results['vectorized_engine'] = test_vectorized_engine()
    
    print("\n" + "=" * 80)
    print("测试汇总")
    print("=" * 80)
    print("\n各环节耗时对比 (100万条数据):")
    print("-" * 60)
    
    for key in ['data_copy', 'data_validation', 'preprocessing', 'jit_core', 'risk_metrics', 'unified_engine', 'vectorized_engine']:
        results = all_results[key]
        for r in results:
            if r['size'] == 1000000:
                time_ms = r['time'] * 1000
                speed = r['speed']
                name = {
                    'data_copy': '数据复制',
                    'data_validation': '数据验证',
                    'preprocessing': '数据预处理',
                    'jit_core': 'JIT核心',
                    'risk_metrics': '风险指标',
                    'unified_engine': '统一引擎(完整)',
                    'vectorized_engine': '向量化引擎'
                }[key]
                print(f"  {name:<20}: {time_ms:>8.2f}ms | {speed:>8.2f}万条/秒")
    
    print("\n" + "=" * 80)
    print(f"测试完成: {datetime.now()}")
    print("=" * 80)
    
    return all_results


if __name__ == "__main__":
    main()
