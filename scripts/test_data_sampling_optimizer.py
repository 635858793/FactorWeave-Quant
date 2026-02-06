"""
数据采样优化器性能测试脚本
测试数据采样优化器的实际效果
"""

import time
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from typing import Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.optimization.data_sampling_optimizer import (
    SamplingStrategy,
    AggregationMethod,
    SamplingConfig,
    DataAggregator,
    AdaptiveDataOptimizer,
    create_data_optimizer
)
from loguru import logger

# 配置日志输出到文件
logger.add("data_sampling_optimizer_test.log", rotation="10 MB")

def generate_test_dataframe(rows: int = 100000, cols: int = 10) -> pd.DataFrame:
    """生成测试DataFrame"""
    np.random.seed(42)
    data = np.random.randn(rows, cols)
    columns = [f'col_{i}' for i in range(cols)]
    return pd.DataFrame(data, columns=columns)

def generate_stock_data(rows: int = 100000) -> pd.DataFrame:
    """生成股票数据"""
    np.random.seed(42)
    
    # 生成价格数据
    base_price = 100.0
    returns = np.random.normal(0, 0.02, rows)
    prices = base_price * (1 + returns).cumprod()
    
    # 生成OHLC数据
    data = pd.DataFrame({
        'open': prices,
        'high': prices * (1 + np.random.uniform(0, 0.01, rows)),
        'low': prices * (1 - np.random.uniform(0, 0.01, rows)),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, rows)
    })
    
    return data

def test_data_sampling_optimizer():
    """测试数据采样优化器"""
    logger.info("=" * 80)
    logger.info("数据采样优化器性能测试")
    logger.info("=" * 80)
    
    # 初始化变量
    fixed_step_sampling_time = 0.0
    lttb_sampling_time = 0.0
    adaptive_sampling_time = 0.0
    optimization_time = 0.0
    cache_speedup = 0.0
    stats = {}
    df = None
    
    # 测试1：初始化和配置
    logger.info("\n" + "=" * 80)
    logger.info("测试1：初始化和配置")
    logger.info("=" * 80)
    
    start_time = time.time()
    config = SamplingConfig(
        strategy=SamplingStrategy.ADAPTIVE,
        aggregation_method=AggregationMethod.MEAN,
        max_points_displayed=5000,
        enable_threaded_sampling=True,
        cache_enabled=True
    )
    init_time = time.time() - start_time
    
    logger.info(f"\n配置初始化时间：{init_time:.4f}秒")
    logger.info(f"采样策略：{config.strategy.value}")
    logger.info(f"聚合方法：{config.aggregation_method.value}")
    logger.info(f"最大显示点数：{config.max_points_displayed}")
    logger.info(f"启用线程采样：{config.enable_threaded_sampling}")
    logger.info(f"启用缓存：{config.cache_enabled}")
    
    # 测试2：数据聚合器初始化
    logger.info("\n" + "=" * 80)
    logger.info("测试2：数据聚合器初始化")
    logger.info("=" * 80)
    
    start_time = time.time()
    aggregator = DataAggregator(config)
    init_time = time.time() - start_time
    
    logger.info(f"\n聚合器初始化时间：{init_time:.4f}秒")
    logger.info(f"线程池已创建：{aggregator.executor is not None}")
    logger.info(f"缓存已创建：{len(aggregator._cache) == 0}")
    
    # 测试3：固定步长采样
    logger.info("\n" + "=" * 80)
    logger.info("测试3：固定步长采样")
    logger.info("=" * 80)
    
    # 生成测试数据
    df = generate_test_dataframe(rows=100000, cols=10)
    logger.info(f"\n测试数据大小：{df.shape}")
    
    # 测试固定步长采样
    config.strategy = SamplingStrategy.FIXED_STEP
    aggregator = DataAggregator(config)
    
    start_time = time.time()
    sampled_df = aggregator.aggregate_data(df, target_points=5000)
    fixed_step_sampling_time = time.time() - start_time
    
    compression_ratio = len(sampled_df) / len(df)
    
    logger.info(f"原始数据点数：{len(df)}")
    logger.info(f"采样后数据点数：{len(sampled_df)}")
    logger.info(f"压缩比：{compression_ratio:.2%}")
    logger.info(f"采样时间：{fixed_step_sampling_time:.4f}秒")
    logger.info(f"采样速度：{len(df) / fixed_step_sampling_time:.2f}点/秒")
    
    # 测试4：LTTB采样
    logger.info("\n" + "=" * 80)
    logger.info("测试4：LTTB采样")
    logger.info("=" * 80)
    
    config.strategy = SamplingStrategy.LTTB
    aggregator = DataAggregator(config)
    
    start_time = time.time()
    sampled_df = aggregator.aggregate_data(df, target_points=5000)
    lttb_sampling_time = time.time() - start_time
    
    compression_ratio = len(sampled_df) / len(df)
    
    logger.info(f"原始数据点数：{len(df)}")
    logger.info(f"采样后数据点数：{len(sampled_df)}")
    logger.info(f"压缩比：{compression_ratio:.2%}")
    logger.info(f"采样时间：{lttb_sampling_time:.4f}秒")
    logger.info(f"采样速度：{len(df) / lttb_sampling_time:.2f}点/秒")
    
    # 测试5：自适应采样
    logger.info("\n" + "=" * 80)
    logger.info("测试5：自适应采样")
    logger.info("=" * 80)
    
    config.strategy = SamplingStrategy.ADAPTIVE
    aggregator = DataAggregator(config)
    
    start_time = time.time()
    sampled_df = aggregator.aggregate_data(df, target_points=5000)
    adaptive_sampling_time = time.time() - start_time
    
    compression_ratio = len(sampled_df) / len(df)
    
    logger.info(f"原始数据点数：{len(df)}")
    logger.info(f"采样后数据点数：{len(sampled_df)}")
    logger.info(f"压缩比：{compression_ratio:.2%}")
    logger.info(f"采样时间：{adaptive_sampling_time:.4f}秒")
    logger.info(f"采样速度：{len(df) / adaptive_sampling_time:.2f}点/秒")
    
    # 测试6：不同数据大小的采样性能
    logger.info("\n" + "=" * 80)
    logger.info("测试6：不同数据大小的采样性能")
    logger.info("=" * 80)
    
    data_sizes = [1000, 10000, 100000, 1000000]
    target_points = 5000
    
    for size in data_sizes:
        df_test = generate_test_dataframe(rows=size, cols=10)
        
        config.strategy = SamplingStrategy.ADAPTIVE
        aggregator = DataAggregator(config)
        
        start_time = time.time()
        sampled_df = aggregator.aggregate_data(df_test, target_points=target_points)
        sampling_time = time.time() - start_time
        
        compression_ratio = len(sampled_df) / len(df_test)
        
        logger.info(f"\n数据大小：{size}行")
        logger.info(f"  采样后数据点数：{len(sampled_df)}")
        logger.info(f"  压缩比：{compression_ratio:.2%}")
        logger.info(f"  采样时间：{sampling_time:.4f}秒")
        if sampling_time > 0:
            logger.info(f"  采样速度：{size / sampling_time:.2f}点/秒")
        else:
            logger.info(f"  采样速度：N/A（采样时间过短）")
    
    # 测试7：股票数据OHLC聚合
    logger.info("\n" + "=" * 80)
    logger.info("测试7：股票数据OHLC聚合")
    logger.info("=" * 80)
    
    stock_df = generate_stock_data(rows=100000)
    logger.info(f"\n股票数据大小：{stock_df.shape}")
    
    config.aggregation_method = AggregationMethod.OHLC
    config.strategy = SamplingStrategy.FIXED_STEP
    aggregator = DataAggregator(config)
    
    start_time = time.time()
    sampled_stock_df = aggregator.aggregate_data(stock_df, target_points=5000)
    sampling_time = time.time() - start_time
    
    compression_ratio = len(sampled_stock_df) / len(stock_df)
    
    logger.info(f"原始数据点数：{len(stock_df)}")
    logger.info(f"采样后数据点数：{len(sampled_stock_df)}")
    logger.info(f"压缩比：{compression_ratio:.2%}")
    logger.info(f"采样时间：{sampling_time:.4f}秒")
    logger.info(f"采样速度：{len(stock_df) / sampling_time:.2f}点/秒")
    logger.info(f"采样后数据列：{list(sampled_stock_df.columns)}")
    
    # 测试8：缓存性能
    logger.info("\n" + "=" * 80)
    logger.info("测试8：缓存性能")
    logger.info("=" * 80)
    
    config.cache_enabled = True
    config.strategy = SamplingStrategy.ADAPTIVE
    aggregator = DataAggregator(config)
    
    # 第一次采样（不命中缓存）
    start_time = time.time()
    sampled_df_1 = aggregator.aggregate_data(df, target_points=5000)
    first_sampling_time = time.time() - start_time
    
    # 第二次采样（命中缓存）
    start_time = time.time()
    sampled_df_2 = aggregator.aggregate_data(df, target_points=5000)
    cached_sampling_time = time.time() - start_time
    
    cache_speedup = first_sampling_time / cached_sampling_time if cached_sampling_time > 0 else 0
    
    logger.info(f"第一次采样时间（不命中缓存）：{first_sampling_time:.4f}秒")
    logger.info(f"第二次采样时间（命中缓存）：{cached_sampling_time:.4f}秒")
    logger.info(f"缓存加速比：{cache_speedup:.2f}x")
    logger.info(f"缓存大小：{len(aggregator._cache)}")
    
    # 测试9：自适应数据优化器
    logger.info("\n" + "=" * 80)
    logger.info("测试9：自适应数据优化器")
    logger.info("=" * 80)
    
    start_time = time.time()
    optimizer = AdaptiveDataOptimizer(config)
    init_time = time.time() - start_time
    
    logger.info(f"\n优化器初始化时间：{init_time:.4f}秒")
    
    # 测试性能优化
    start_time = time.time()
    optimized_df = optimizer.optimize_for_performance(df, render_time_target=50.0)
    optimization_time = time.time() - start_time
    
    compression_ratio = len(optimized_df) / len(df)
    
    logger.info(f"原始数据点数：{len(df)}")
    logger.info(f"优化后数据点数：{len(optimized_df)}")
    logger.info(f"压缩比：{compression_ratio:.2%}")
    logger.info(f"优化时间：{optimization_time:.4f}秒")
    logger.info(f"优化速度：{len(df) / optimization_time:.2f}点/秒")
    
    # 记录渲染时间
    optimizer.record_render_time(40.0)
    optimizer.record_render_time(45.0)
    optimizer.record_render_time(50.0)
    
    # 获取优化统计
    stats = optimizer.get_optimization_stats()
    logger.info(f"\n优化统计：")
    logger.info(f"  总采样数：{stats['total_samples_taken']}")
    logger.info(f"  总处理数据点数：{stats['total_data_points_processed']}")
    logger.info(f"  平均压缩比：{stats['avg_compression_ratio']:.2%}")
    logger.info(f"  最近平均渲染时间：{stats['recent_avg_render_time']:.2f}ms")
    logger.info(f"  当前最大显示点数：{stats['current_max_points']}")
    logger.info(f"  缓存大小：{stats['cache_size']}")
    
    # 测试10：便捷函数
    logger.info("\n" + "=" * 80)
    logger.info("测试10：便捷函数")
    logger.info("=" * 80)
    
    start_time = time.time()
    optimizer_high_quality = create_data_optimizer(data_size=100000, performance_requirement="high_quality")
    init_time = time.time() - start_time
    
    logger.info(f"\n高质量优化器初始化时间：{init_time:.4f}秒")
    logger.info(f"最大显示点数：{optimizer_high_quality.config.max_points_displayed}")
    logger.info(f"性能阈值：{optimizer_high_quality.config.performance_threshold_ms}ms")
    
    start_time = time.time()
    optimizer_high_speed = create_data_optimizer(data_size=100000, performance_requirement="high_speed")
    init_time = time.time() - start_time
    
    logger.info(f"\n高速优化器初始化时间：{init_time:.4f}秒")
    logger.info(f"最大显示点数：{optimizer_high_speed.config.max_points_displayed}")
    logger.info(f"性能阈值：{optimizer_high_speed.config.performance_threshold_ms}ms")
    
    start_time = time.time()
    optimizer_balanced = create_data_optimizer(data_size=100000, performance_requirement="balanced")
    init_time = time.time() - start_time
    
    logger.info(f"\n平衡优化器初始化时间：{init_time:.4f}秒")
    logger.info(f"最大显示点数：{optimizer_balanced.config.max_points_displayed}")
    logger.info(f"性能阈值：{optimizer_balanced.config.performance_threshold_ms}ms")
    
    # 清理资源
    logger.info("\n" + "=" * 80)
    logger.info("清理资源")
    logger.info("=" * 80)
    
    aggregator.cleanup()
    optimizer.cleanup()
    optimizer_high_quality.cleanup()
    optimizer_high_speed.cleanup()
    optimizer_balanced.cleanup()
    
    logger.info("资源清理完成")
    
    # 最终统计
    logger.info("\n" + "=" * 80)
    logger.info("数据采样优化器性能总结")
    logger.info("=" * 80)
    
    logger.info("\n性能指标：")
    logger.info(f"  配置初始化时间：{init_time:.4f}秒")
    logger.info(f"  聚合器初始化时间：{init_time:.4f}秒")
    logger.info(f"  优化器初始化时间：{init_time:.4f}秒")
    
    logger.info("\n采样性能：")
    if fixed_step_sampling_time > 0:
        logger.info(f"  固定步长采样速度：{len(df) / fixed_step_sampling_time:.2f}点/秒")
    if lttb_sampling_time > 0:
        logger.info(f"  LTTB采样速度：{len(df) / lttb_sampling_time:.2f}点/秒")
    if adaptive_sampling_time > 0:
        logger.info(f"  自适应采样速度：{len(df) / adaptive_sampling_time:.2f}点/秒")
    
    logger.info("\n缓存性能：")
    if cache_speedup > 0:
        logger.info(f"  缓存加速比：{cache_speedup:.2f}x")
    if 'aggregator' in locals():
        logger.info(f"  缓存大小：{len(aggregator._cache)}")
    
    logger.info("\n优化性能：")
    if optimization_time > 0:
        logger.info(f"  优化时间：{optimization_time:.4f}秒")
        logger.info(f"  优化速度：{len(df) / optimization_time:.2f}点/秒")
    else:
        logger.info(f"  优化时间：N/A")
        logger.info(f"  优化速度：N/A")
    if 'stats' in locals() and 'avg_compression_ratio' in stats:
        logger.info(f"  平均压缩比：{stats['avg_compression_ratio']:.2%}")
    
    logger.info("\n" + "=" * 80)
    logger.info("测试完成")
    logger.info("=" * 80)

if __name__ == "__main__":
    test_data_sampling_optimizer()
