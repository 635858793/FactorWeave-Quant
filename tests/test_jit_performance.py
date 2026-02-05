"""
JIT性能验证脚本
用于验证JIT加速的性能提升
"""

import numpy as np
import time
import sys
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_test_data(size: int = 10000) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """生成测试数据"""
    np.random.seed(42)
    
    # 生成价格数据
    base_price = 100.0
    prices = np.cumsum(np.random.randn(size) * 0.5) + base_price
    
    # 生成高低价
    high = prices + np.random.rand(size) * 2.0
    low = prices - np.random.rand(size) * 2.0
    close = prices
    
    return prices, high, low, close

def test_jit_rsi_performance() -> Dict[str, float]:
    """测试RSI的JIT性能"""
    logger.info("测试RSI JIT性能...")
    
    try:
        from core.indicators.jit_indicators import calculate_rsi_jit
    except ImportError:
        logger.error("无法导入JIT RSI函数")
        return {'error': 'ImportError'}
    
    prices, _, _, _ = generate_test_data(10000)
    
    # JIT版本
    start = time.time()
    for _ in range(100):
        _ = calculate_rsi_jit(prices, 14)
    jit_time = time.time() - start
    
    logger.info(f"JIT RSI 100次计算耗时: {jit_time:.4f}秒")
    
    return {
        'jit_time': jit_time,
        'avg_time_per_call': jit_time / 100
    }

def test_jit_macd_performance() -> Dict[str, float]:
    """测试MACD的JIT性能"""
    logger.info("测试MACD JIT性能...")
    
    try:
        from core.indicators.jit_indicators import calculate_macd_jit
    except ImportError:
        logger.error("无法导入JIT MACD函数")
        return {'error': 'ImportError'}
    
    prices, _, _, _ = generate_test_data(10000)
    
    # JIT版本
    start = time.time()
    for _ in range(100):
        _ = calculate_macd_jit(prices)
    jit_time = time.time() - start
    
    logger.info(f"JIT MACD 100次计算耗时: {jit_time:.4f}秒")
    
    return {
        'jit_time': jit_time,
        'avg_time_per_call': jit_time / 100
    }

def test_jit_sma_performance() -> Dict[str, float]:
    """测试SMA的JIT性能"""
    logger.info("测试SMA JIT性能...")
    
    try:
        from core.indicators.jit_indicators import calculate_sma_jit
    except ImportError:
        logger.error("无法导入JIT SMA函数")
        return {'error': 'ImportError'}
    
    prices, _, _, _ = generate_test_data(10000)
    
    # JIT版本
    start = time.time()
    for _ in range(100):
        _ = calculate_sma_jit(prices, 20)
    jit_time = time.time() - start
    
    logger.info(f"JIT SMA 100次计算耗时: {jit_time:.4f}秒")
    
    return {
        'jit_time': jit_time,
        'avg_time_per_call': jit_time / 100
    }

def test_jit_bollinger_performance() -> Dict[str, float]:
    """测试布林带的JIT性能"""
    logger.info("测试布林带JIT性能...")
    
    try:
        from core.indicators.jit_indicators import calculate_bollinger_bands_jit
    except ImportError:
        logger.error("无法导入JIT布林带函数")
        return {'error': 'ImportError'}
    
    prices, _, _, _ = generate_test_data(10000)
    
    # JIT版本
    start = time.time()
    for _ in range(100):
        _ = calculate_bollinger_bands_jit(prices, 20, 2.0)
    jit_time = time.time() - start
    
    logger.info(f"JIT布林带 100次计算耗时: {jit_time:.4f}秒")
    
    return {
        'jit_time': jit_time,
        'avg_time_per_call': jit_time / 100
    }

def test_jit_batch_performance() -> Dict[str, float]:
    """测试批量计算的JIT性能"""
    logger.info("测试批量计算JIT性能...")
    
    try:
        from core.indicators.jit_indicators import batch_calculate_indicators_jit
    except ImportError:
        logger.error("无法导入JIT批量计算函数")
        return {'error': 'ImportError'}
    
    prices, high, low, close = generate_test_data(10000)
    indicators = ['sma', 'ema', 'rsi', 'macd', 'bollinger', 'atr', 'stochastic', 'williams_r']
    
    # JIT版本
    start = time.time()
    for _ in range(100):
        _ = batch_calculate_indicators_jit(prices, high, low, close, indicators)
    jit_time = time.time() - start
    
    logger.info(f"JIT批量计算 100次计算耗时: {jit_time:.4f}秒")
    
    return {
        'jit_time': jit_time,
        'avg_time_per_call': jit_time / 100,
        'indicators_count': len(indicators)
    }

def test_jit_cache_performance() -> Dict[str, float]:
    """测试缓存性能"""
    logger.info("测试JIT缓存性能...")
    
    try:
        from core.indicators.jit_indicators import (
            calculate_rsi_with_cache,
            clear_indicator_cache,
            get_cache_stats
        )
    except ImportError:
        logger.error("无法导入JIT缓存函数")
        return {'error': 'ImportError'}
    
    prices, _, _, _ = generate_test_data(10000)
    
    # 清理缓存
    clear_indicator_cache()
    
    # 第一次计算（无缓存）
    start = time.time()
    for _ in range(10):
        _ = calculate_rsi_with_cache(prices, 14, use_cache=True)
    first_time = time.time() - start
    
    # 第二次计算（有缓存）
    start = time.time()
    for _ in range(10):
        _ = calculate_rsi_with_cache(prices, 14, use_cache=True)
    cached_time = time.time() - start
    
    # 获取缓存统计
    cache_stats = get_cache_stats()
    
    logger.info(f"第一次计算（无缓存）10次耗时: {first_time:.4f}秒")
    logger.info(f"第二次计算（有缓存）10次耗时: {cached_time:.4f}秒")
    logger.info(f"缓存提升: {(first_time - cached_time) / first_time * 100:.2f}%")
    logger.info(f"缓存统计: {cache_stats}")
    
    return {
        'first_time': first_time,
        'cached_time': cached_time,
        'cache_improvement': (first_time - cached_time) / first_time * 100,
        'cache_stats': cache_stats
    }

def test_jit_optimizer_integration() -> Dict[str, any]:
    """测试JIT优化器集成"""
    logger.info("测试JIT优化器集成...")
    
    try:
        from backtest.jit_optimizer import jit_optimizer
    except ImportError:
        logger.error("无法导入JIT优化器")
        return {'error': 'ImportError'}
    
    # 获取统计信息
    stats = jit_optimizer.get_stats()
    logger.info(f"JIT优化器统计: {stats}")
    
    # 获取缓存统计
    cache_stats = jit_optimizer.get_cache_stats()
    logger.info(f"JIT缓存统计: {cache_stats}")
    
    # 获取执行效率
    efficiency = jit_optimizer.get_execution_efficiency()
    logger.info(f"JIT执行效率: {efficiency:.2f}%")
    
    # 获取JIT使用情况
    jit_usage = jit_optimizer.get_jit_usage()
    logger.info(f"JIT使用情况: {jit_usage}")
    
    return {
        'stats': stats,
        'cache_stats': cache_stats,
        'efficiency': efficiency,
        'jit_usage': jit_usage
    }

def run_all_tests() -> Dict[str, any]:
    """运行所有性能测试"""
    logger.info("=" * 60)
    logger.info("开始JIT性能验证测试")
    logger.info("=" * 60)
    
    results = {}
    
    # 测试各个指标的JIT性能
    results['rsi'] = test_jit_rsi_performance()
    results['macd'] = test_jit_macd_performance()
    results['sma'] = test_jit_sma_performance()
    results['bollinger'] = test_jit_bollinger_performance()
    results['batch'] = test_jit_batch_performance()
    results['cache'] = test_jit_cache_performance()
    results['optimizer'] = test_jit_optimizer_integration()
    
    # 生成性能报告
    generate_performance_report(results)
    
    return results

def generate_performance_report(results: Dict[str, any]):
    """生成性能报告"""
    logger.info("=" * 60)
    logger.info("JIT性能验证报告")
    logger.info("=" * 60)
    
    # RSI性能
    if 'rsi' in results and 'avg_time_per_call' in results['rsi']:
        logger.info(f"\nRSI性能:")
        logger.info(f"  平均每次调用时间: {results['rsi']['avg_time_per_call']:.6f}秒")
        logger.info(f"  100次调用总时间: {results['rsi']['jit_time']:.4f}秒")
    
    # MACD性能
    if 'macd' in results and 'avg_time_per_call' in results['macd']:
        logger.info(f"\nMACD性能:")
        logger.info(f"  平均每次调用时间: {results['macd']['avg_time_per_call']:.6f}秒")
        logger.info(f"  100次调用总时间: {results['macd']['jit_time']:.4f}秒")
    
    # SMA性能
    if 'sma' in results and 'avg_time_per_call' in results['sma']:
        logger.info(f"\nSMA性能:")
        logger.info(f"  平均每次调用时间: {results['sma']['avg_time_per_call']:.6f}秒")
        logger.info(f"  100次调用总时间: {results['sma']['jit_time']:.4f}秒")
    
    # 布林带性能
    if 'bollinger' in results and 'avg_time_per_call' in results['bollinger']:
        logger.info(f"\n布林带性能:")
        logger.info(f"  平均每次调用时间: {results['bollinger']['avg_time_per_call']:.6f}秒")
        logger.info(f"  100次调用总时间: {results['bollinger']['jit_time']:.4f}秒")
    
    # 批量计算性能
    if 'batch' in results and 'avg_time_per_call' in results['batch']:
        logger.info(f"\n批量计算性能:")
        logger.info(f"  平均每次调用时间: {results['batch']['avg_time_per_call']:.6f}秒")
        logger.info(f"  100次调用总时间: {results['batch']['jit_time']:.4f}秒")
        logger.info(f"  指标数量: {results['batch'].get('indicators_count', 0)}")
    
    # 缓存性能
    if 'cache' in results and 'cache_improvement' in results['cache']:
        logger.info(f"\n缓存性能:")
        logger.info(f"  缓存提升: {results['cache']['cache_improvement']:.2f}%")
        logger.info(f"  缓存统计: {results['cache'].get('cache_stats', {})}")
    
    # JIT优化器集成
    if 'optimizer' in results:
        logger.info(f"\nJIT优化器集成:")
        logger.info(f"  编译函数数: {results['optimizer'].get('stats', {}).get('compile_count', 0)}")
        logger.info(f"  编译时间: {results['optimizer'].get('stats', {}).get('compile_time', 0):.4f}秒")
        logger.info(f"  执行效率: {results['optimizer'].get('efficiency', 0):.2f}%")
        logger.info(f"  JIT函数数: {len(results['optimizer'].get('jit_usage', {}).get('functions', []))}")
    
    logger.info("\n" + "=" * 60)
    logger.info("性能验证完成")
    logger.info("=" * 60)

if __name__ == "__main__":
    results = run_all_tests()
    sys.exit(0)
