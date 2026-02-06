"""
扩展测试用例 - 更多形态、更大数据集、更长迭代次数、边界情况
"""

import sys
import os
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from optimization.algorithm_optimizer import AlgorithmOptimizer, OptimizationConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('extended_test_cases.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def create_test_data(size=1000, trend=0.0, volatility=0.02):
    """创建测试数据
    
    Args:
        size: 数据大小
        trend: 趋势（正数为上涨趋势，负数为下跌趋势）
        volatility: 波动率
    """
    np.random.seed(42)
    
    dates = pd.date_range(start='2020-01-01', periods=size, freq='D')
    
    # 生成价格数据（带趋势和波动）
    base_price = 150.0
    returns = np.random.normal(trend, volatility, size)
    prices = base_price * np.cumprod(1 + returns)
    
    # 生成OHLC数据
    data = {
        'datetime': dates,
        'open': prices * np.random.uniform(0.99, 1.01, size),
        'high': prices * np.random.uniform(1.0, 1.03, size),
        'low': prices * np.random.uniform(0.97, 1.0, size),
        'close': prices,
        'amount': np.random.uniform(1000000, 10000000, size),
        'volume': np.random.uniform(100000, 1000000, size)
    }
    
    df = pd.DataFrame(data)
    
    # 确保 high >= max(open, close) 和 low <= min(open, close)
    df['high'] = np.maximum(df['high'], np.maximum(df['open'], df['close']))
    df['low'] = np.minimum(df['low'], np.minimum(df['open'], df['close']))
    
    return df


def test_more_patterns():
    """测试更多形态"""
    logger.info("=" * 80)
    logger.info("测试1：更多形态")
    logger.info("=" * 80)
    
    # 创建测试数据
    test_data = create_test_data(size=1000)
    
    # 创建优化器
    optimizer = AlgorithmOptimizer(debug_mode=False)
    
    # 测试更多形态
    patterns = ["hammer", "doji", "engulfing", "morning_star", "evening_star"]
    results = []
    
    for pattern in patterns:
        logger.info(f"\n测试形态: {pattern}")
        
        # 测试所有优化方法
        methods = ["genetic", "bayesian", "random", "gradient"]
        
        for method in methods:
            logger.info(f"  测试方法: {method}")
            
            config = OptimizationConfig(
                method=method,
                max_iterations=5,
                target_metric="overall_score"
            )
            
            try:
                result = optimizer.optimize_algorithm(pattern, config, [test_data])
                results.append({
                    'pattern': pattern,
                    'method': method,
                    'success': True,
                    'best_score': result.get('best_score', 0),
                    'improvement_percentage': result.get('improvement_percentage', 0),
                    'optimization_time': result.get('optimization_time', 0)
                })
                
                logger.info(f"    评分: {result.get('best_score', 0):.3f}")
                logger.info(f"    提升: {result.get('improvement_percentage', 0):.3f}%")
                
            except Exception as e:
                logger.error(f"    优化失败: {e}")
                results.append({
                    'pattern': pattern,
                    'method': method,
                    'success': False,
                    'error': str(e)
                })
    
    return results


def test_larger_datasets():
    """测试更大数据集"""
    logger.info("\n" + "=" * 80)
    logger.info("测试2：更大数据集")
    logger.info("=" * 80)
    
    # 创建优化器
    optimizer = AlgorithmOptimizer(debug_mode=False)
    
    # 测试不同大小的数据集
    dataset_sizes = [500, 1000, 2000, 5000]
    results = []
    
    for size in dataset_sizes:
        logger.info(f"\n测试数据集大小: {size}")
        
        # 创建测试数据
        test_data = create_test_data(size=size)
        
        # 测试所有优化方法
        methods = ["genetic", "bayesian", "random", "gradient"]
        
        for method in methods:
            logger.info(f"  测试方法: {method}")
            
            config = OptimizationConfig(
                method=method,
                max_iterations=5,
                target_metric="overall_score"
            )
            
            try:
                result = optimizer.optimize_algorithm("hammer", config, [test_data])
                results.append({
                    'dataset_size': size,
                    'method': method,
                    'success': True,
                    'best_score': result.get('best_score', 0),
                    'improvement_percentage': result.get('improvement_percentage', 0),
                    'optimization_time': result.get('optimization_time', 0)
                })
                
                logger.info(f"    评分: {result.get('best_score', 0):.3f}")
                logger.info(f"    提升: {result.get('improvement_percentage', 0):.3f}%")
                logger.info(f"    时间: {result.get('optimization_time', 0):.3f}秒")
                
            except Exception as e:
                logger.error(f"    优化失败: {e}")
                results.append({
                    'dataset_size': size,
                    'method': method,
                    'success': False,
                    'error': str(e)
                })
    
    return results


def test_longer_iterations():
    """测试更长迭代次数"""
    logger.info("\n" + "=" * 80)
    logger.info("测试3：更长迭代次数")
    logger.info("=" * 80)
    
    # 创建测试数据
    test_data = create_test_data(size=1000)
    
    # 创建优化器
    optimizer = AlgorithmOptimizer(debug_mode=False)
    
    # 测试不同的迭代次数
    iteration_counts = [3, 5, 10, 20, 50]
    results = []
    
    for iterations in iteration_counts:
        logger.info(f"\n测试迭代次数: {iterations}")
        
        # 测试所有优化方法
        methods = ["genetic", "bayesian", "random", "gradient"]
        
        for method in methods:
            logger.info(f"  测试方法: {method}")
            
            config = OptimizationConfig(
                method=method,
                max_iterations=iterations,
                target_metric="overall_score"
            )
            
            try:
                result = optimizer.optimize_algorithm("hammer", config, [test_data])
                results.append({
                    'iterations': iterations,
                    'method': method,
                    'success': True,
                    'best_score': result.get('best_score', 0),
                    'improvement_percentage': result.get('improvement_percentage', 0),
                    'optimization_time': result.get('optimization_time', 0)
                })
                
                logger.info(f"    评分: {result.get('best_score', 0):.3f}")
                logger.info(f"    提升: {result.get('improvement_percentage', 0):.3f}%")
                logger.info(f"    时间: {result.get('optimization_time', 0):.3f}秒")
                
            except Exception as e:
                logger.error(f"    优化失败: {e}")
                results.append({
                    'iterations': iterations,
                    'method': method,
                    'success': False,
                    'error': str(e)
                })
    
    return results


def test_edge_cases():
    """测试边界情况"""
    logger.info("\n" + "=" * 80)
    logger.info("测试4：边界情况")
    logger.info("=" * 80)
    
    # 创建优化器
    optimizer = AlgorithmOptimizer(debug_mode=False)
    
    results = []
    
    # 测试1：空数据
    logger.info("\n测试1：空数据")
    try:
        empty_data = pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'amount', 'volume'])
        config = OptimizationConfig(method="random", max_iterations=3, target_metric="overall_score")
        result = optimizer.optimize_algorithm("hammer", config, [empty_data])
        results.append({
            'test_case': 'empty_data',
            'success': True,
            'result': result
        })
        logger.info("  空数据处理成功")
    except Exception as e:
        logger.error(f"  空数据处理失败: {e}")
        results.append({
            'test_case': 'empty_data',
            'success': False,
            'error': str(e)
        })
    
    # 测试2：单条数据
    logger.info("\n测试2：单条数据")
    try:
        single_data = create_test_data(size=1)
        config = OptimizationConfig(method="random", max_iterations=3, target_metric="overall_score")
        result = optimizer.optimize_algorithm("hammer", config, [single_data])
        results.append({
            'test_case': 'single_data',
            'success': True,
            'result': result
        })
        logger.info("  单条数据处理成功")
    except Exception as e:
        logger.error(f"  单条数据处理失败: {e}")
        results.append({
            'test_case': 'single_data',
            'success': False,
            'error': str(e)
        })
    
    # 测试3：极端趋势（大涨）
    logger.info("\n测试3：极端趋势（大涨）")
    try:
        bull_data = create_test_data(size=1000, trend=0.05, volatility=0.01)
        config = OptimizationConfig(method="random", max_iterations=5, target_metric="overall_score")
        result = optimizer.optimize_algorithm("hammer", config, [bull_data])
        results.append({
            'test_case': 'extreme_bull',
            'success': True,
            'result': result
        })
        logger.info(f"  大涨数据处理成功，评分: {result.get('best_score', 0):.3f}")
    except Exception as e:
        logger.error(f"  大涨数据处理失败: {e}")
        results.append({
            'test_case': 'extreme_bull',
            'success': False,
            'error': str(e)
        })
    
    # 测试4：极端趋势（大跌）
    logger.info("\n测试4：极端趋势（大跌）")
    try:
        bear_data = create_test_data(size=1000, trend=-0.05, volatility=0.01)
        config = OptimizationConfig(method="random", max_iterations=5, target_metric="overall_score")
        result = optimizer.optimize_algorithm("hammer", config, [bear_data])
        results.append({
            'test_case': 'extreme_bear',
            'success': True,
            'result': result
        })
        logger.info(f"  大跌数据处理成功，评分: {result.get('best_score', 0):.3f}")
    except Exception as e:
        logger.error(f"  大跌数据处理失败: {e}")
        results.append({
            'test_case': 'extreme_bear',
            'success': False,
            'error': str(e)
        })
    
    # 测试5：高波动
    logger.info("\n测试5：高波动")
    try:
        volatile_data = create_test_data(size=1000, trend=0.0, volatility=0.1)
        config = OptimizationConfig(method="random", max_iterations=5, target_metric="overall_score")
        result = optimizer.optimize_algorithm("hammer", config, [volatile_data])
        results.append({
            'test_case': 'high_volatility',
            'success': True,
            'result': result
        })
        logger.info(f"  高波动数据处理成功，评分: {result.get('best_score', 0):.3f}")
    except Exception as e:
        logger.error(f"  高波动数据处理失败: {e}")
        results.append({
            'test_case': 'high_volatility',
            'success': False,
            'error': str(e)
        })
    
    return results


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("扩展测试用例")
    logger.info("=" * 80)
    
    # 运行所有测试
    all_results = {}
    
    # 测试1：更多形态
    logger.info("\n开始测试1：更多形态")
    all_results['more_patterns'] = test_more_patterns()
    
    # 测试2：更大数据集
    logger.info("\n开始测试2：更大数据集")
    all_results['larger_datasets'] = test_larger_datasets()
    
    # 测试3：更长迭代次数
    logger.info("\n开始测试3：更长迭代次数")
    all_results['longer_iterations'] = test_longer_iterations()
    
    # 测试4：边界情况
    logger.info("\n开始测试4：边界情况")
    all_results['edge_cases'] = test_edge_cases()
    
    # 保存结果
    test_report = {
        "test_date": datetime.now().isoformat(),
        "test_results": all_results
    }
    
    import json
    with open('EXTENDED_TEST_CASES_REPORT.json', 'w', encoding='utf-8') as f:
        json.dump(test_report, f, indent=2, ensure_ascii=False)
    
    logger.info("\n" + "=" * 80)
    logger.info("测试完成")
    logger.info("=" * 80)
    logger.info("测试报告已保存到 EXTENDED_TEST_CASES_REPORT.json")


if __name__ == "__main__":
    main()
