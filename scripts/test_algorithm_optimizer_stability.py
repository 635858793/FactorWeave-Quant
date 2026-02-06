#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
算法优化器稳定性测试脚本

测试AlgorithmOptimizer的稳定性，包括：
1. 测试不同的形态
2. 测试不同的数据集大小
3. 测试不同的优化参数
4. 测试多次运行的稳定性
5. 测试边界情况
"""

import sys
import os
import time
import json
import traceback
from datetime import datetime
from typing import Dict, List, Any
import pandas as pd
import numpy as np

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")

from optimization.algorithm_optimizer import AlgorithmOptimizer, OptimizationConfig


def create_test_data(n=1000, seed=42) -> pd.DataFrame:
    """创建测试数据，包含明确的形态"""
    np.random.seed(seed)
    
    # 创建n条K线数据
    dates = pd.date_range(start='2020-01-01', periods=n, freq='D')
    
    # 生成随机价格数据
    close_prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
    open_prices = close_prices + np.random.randn(n) * 0.2
    high_prices = np.maximum(open_prices, close_prices) + np.random.rand(n) * 0.3
    low_prices = np.minimum(open_prices, close_prices) - np.random.rand(n) * 0.3
    volumes = np.random.randint(1000, 10000, n)
    
    # 添加一些明确的形态
    # 锤子线：小实体，长下影线，短上影线
    for i in range(50, min(100, n), 10):
        close_prices[i] = 100 + i * 0.5
        open_prices[i] = close_prices[i] + 0.1
        high_prices[i] = max(open_prices[i], close_prices[i]) + 0.05
        low_prices[i] = min(open_prices[i], close_prices[i]) - 0.5  # 长下影线
    
    # 十字星：开盘价和收盘价几乎相同
    for i in range(200, min(250, n), 10):
        close_prices[i] = 100 + i * 0.5
        open_prices[i] = close_prices[i] + 0.01  # 几乎相同
        high_prices[i] = max(open_prices[i], close_prices[i]) + 0.3
        low_prices[i] = min(open_prices[i], close_prices[i]) - 0.3
    
    data = pd.DataFrame({
        'datetime': dates,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volumes
    })
    
    return data


def test_different_patterns():
    """测试不同的形态"""
    logger.info("=" * 80)
    logger.info("测试1：不同的形态")
    logger.info("=" * 80)
    
    patterns = ["hammer", "doji"]
    results = []
    
    for pattern in patterns:
        logger.info(f"\n测试形态: {pattern}")
        
        try:
            # 创建优化器
            optimizer = AlgorithmOptimizer(debug_mode=False)
            
            # 创建测试数据
            test_data = create_test_data(n=1000, seed=42)
            
            # 测试所有优化方法
            methods = ["genetic", "bayesian", "random", "gradient"]
            
            for method in methods:
                logger.info(f"  测试方法: {method}")
                
                config = OptimizationConfig(
                    method=method,
                    max_iterations=5,
                    target_metric="overall_score",
                    min_improvement=0.05,
                    timeout_minutes=5
                )
                
                start_time = time.time()
                
                try:
                    result = optimizer.optimize_algorithm(pattern, config, [test_data])
                    optimization_time = time.time() - start_time
                    
                    results.append({
                        'pattern': pattern,
                        'method': method,
                        'success': True,
                        'optimization_time': optimization_time,
                        'best_score': result.get('best_score', 0),
                        'baseline_score': result.get('baseline_score', 0),
                        'improvement_percentage': result.get('improvement_percentage', 0),
                        'iterations': result.get('iterations', 0)
                    })
                    
                    logger.info(f"    最佳评分: {result.get('best_score', 0):.3f}")
                    logger.info(f"    性能提升: {result.get('improvement_percentage', 0):.3f}%")
                    
                except Exception as e:
                    logger.error(f"    失败: {e}")
                    results.append({
                        'pattern': pattern,
                        'method': method,
                        'success': False,
                        'error': str(e)
                    })
        
        except Exception as e:
            logger.error(f"  形态 {pattern} 测试失败: {e}")
    
    return results


def test_different_dataset_sizes():
    """测试不同的数据集大小"""
    logger.info("\n" + "=" * 80)
    logger.info("测试2：不同的数据集大小")
    logger.info("=" * 80)
    
    dataset_sizes = [500, 1000, 2000]
    results = []
    
    for size in dataset_sizes:
        logger.info(f"\n测试数据集大小: {size}")
        
        try:
            # 创建优化器
            optimizer = AlgorithmOptimizer(debug_mode=False)
            
            # 创建测试数据
            test_data = create_test_data(n=size, seed=42)
            
            # 测试所有优化方法
            methods = ["genetic", "bayesian", "random", "gradient"]
            
            for method in methods:
                logger.info(f"  测试方法: {method}")
                
                config = OptimizationConfig(
                    method=method,
                    max_iterations=5,
                    target_metric="overall_score",
                    min_improvement=0.05,
                    timeout_minutes=5
                )
                
                start_time = time.time()
                
                try:
                    result = optimizer.optimize_algorithm("hammer", config, [test_data])
                    optimization_time = time.time() - start_time
                    
                    results.append({
                        'dataset_size': size,
                        'method': method,
                        'success': True,
                        'optimization_time': optimization_time,
                        'best_score': result.get('best_score', 0),
                        'baseline_score': result.get('baseline_score', 0),
                        'improvement_percentage': result.get('improvement_percentage', 0),
                        'iterations': result.get('iterations', 0)
                    })
                    
                    logger.info(f"    最佳评分: {result.get('best_score', 0):.3f}")
                    logger.info(f"    性能提升: {result.get('improvement_percentage', 0):.3f}%")
                    
                except Exception as e:
                    logger.error(f"    失败: {e}")
                    results.append({
                        'dataset_size': size,
                        'method': method,
                        'success': False,
                        'error': str(e)
                    })
        
        except Exception as e:
            logger.error(f"  数据集大小 {size} 测试失败: {e}")
    
    return results


def test_different_iterations():
    """测试不同的迭代次数"""
    logger.info("\n" + "=" * 80)
    logger.info("测试3：不同的迭代次数")
    logger.info("=" * 80)
    
    iteration_counts = [3, 5, 10]
    results = []
    
    for iterations in iteration_counts:
        logger.info(f"\n测试迭代次数: {iterations}")
        
        try:
            # 创建优化器
            optimizer = AlgorithmOptimizer(debug_mode=False)
            
            # 创建测试数据
            test_data = create_test_data(n=1000, seed=42)
            
            # 测试所有优化方法
            methods = ["genetic", "bayesian", "random", "gradient"]
            
            for method in methods:
                logger.info(f"  测试方法: {method}")
                
                config = OptimizationConfig(
                    method=method,
                    max_iterations=iterations,
                    target_metric="overall_score",
                    min_improvement=0.05,
                    timeout_minutes=10
                )
                
                start_time = time.time()
                
                try:
                    result = optimizer.optimize_algorithm("hammer", config, [test_data])
                    optimization_time = time.time() - start_time
                    
                    results.append({
                        'iterations': iterations,
                        'method': method,
                        'success': True,
                        'optimization_time': optimization_time,
                        'best_score': result.get('best_score', 0),
                        'baseline_score': result.get('baseline_score', 0),
                        'improvement_percentage': result.get('improvement_percentage', 0),
                        'iterations_actual': result.get('iterations', 0)
                    })
                    
                    logger.info(f"    最佳评分: {result.get('best_score', 0):.3f}")
                    logger.info(f"    性能提升: {result.get('improvement_percentage', 0):.3f}%")
                    
                except Exception as e:
                    logger.error(f"    失败: {e}")
                    results.append({
                        'iterations': iterations,
                        'method': method,
                        'success': False,
                        'error': str(e)
                    })
        
        except Exception as e:
            logger.error(f"  迭代次数 {iterations} 测试失败: {e}")
    
    return results


def test_stability():
    """测试多次运行的稳定性"""
    logger.info("\n" + "=" * 80)
    logger.info("测试4：多次运行的稳定性")
    logger.info("=" * 80)
    
    runs = 3
    results = []
    
    for run in range(1, runs + 1):
        logger.info(f"\n第 {run} 次运行")
        
        try:
            # 创建优化器
            optimizer = AlgorithmOptimizer(debug_mode=False)
            
            # 创建测试数据（使用不同的种子）
            test_data = create_test_data(n=1000, seed=run * 42)
            
            # 测试所有优化方法
            methods = ["genetic", "bayesian", "random", "gradient"]
            
            for method in methods:
                logger.info(f"  测试方法: {method}")
                
                config = OptimizationConfig(
                    method=method,
                    max_iterations=5,
                    target_metric="overall_score",
                    min_improvement=0.05,
                    timeout_minutes=5
                )
                
                start_time = time.time()
                
                try:
                    result = optimizer.optimize_algorithm("hammer", config, [test_data])
                    optimization_time = time.time() - start_time
                    
                    results.append({
                        'run': run,
                        'method': method,
                        'success': True,
                        'optimization_time': optimization_time,
                        'best_score': result.get('best_score', 0),
                        'baseline_score': result.get('baseline_score', 0),
                        'improvement_percentage': result.get('improvement_percentage', 0),
                        'iterations': result.get('iterations', 0)
                    })
                    
                    logger.info(f"    最佳评分: {result.get('best_score', 0):.3f}")
                    logger.info(f"    性能提升: {result.get('improvement_percentage', 0):.3f}%")
                    
                except Exception as e:
                    logger.error(f"    失败: {e}")
                    results.append({
                        'run': run,
                        'method': method,
                        'success': False,
                        'error': str(e)
                    })
        
        except Exception as e:
            logger.error(f"  第 {run} 次运行失败: {e}")
    
    return results


def analyze_results(all_results: Dict[str, List[Dict]]):
    """分析测试结果"""
    logger.info("\n" + "=" * 80)
    logger.info("测试结果分析")
    logger.info("=" * 80)
    
    for test_name, results in all_results.items():
        logger.info(f"\n{test_name}:")
        
        success_count = sum(1 for r in results if r.get('success', False))
        total_count = len(results)
        
        logger.info(f"  成功率: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)")
        
        if success_count > 0:
            successful_results = [r for r in results if r.get('success', False)]
            
            avg_improvement = np.mean([r.get('improvement_percentage', 0) for r in successful_results])
            avg_time = np.mean([r.get('optimization_time', 0) for r in successful_results])
            
            logger.info(f"  平均性能提升: {avg_improvement:.3f}%")
            logger.info(f"  平均优化时间: {avg_time:.3f}秒")
            
            # 按方法分组
            methods = {}
            for r in successful_results:
                method = r.get('method', 'unknown')
                if method not in methods:
                    methods[method] = []
                methods[method].append(r)
            
            logger.info(f"  各方法性能:")
            for method, method_results in methods.items():
                avg_improvement = np.mean([r.get('improvement_percentage', 0) for r in method_results])
                avg_time = np.mean([r.get('optimization_time', 0) for r in method_results])
                logger.info(f"    {method}: 平均性能提升 {avg_improvement:.3f}%, 平均优化时间 {avg_time:.3f}秒")


def save_results(all_results: Dict[str, List[Dict]]):
    """保存测试结果"""
    output_file = "ALGORITHM_OPTIMIZER_STABILITY_TEST_REPORT.json"
    
    report = {
        'test_time': datetime.now().isoformat(),
        'tests': all_results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n测试报告已保存到：{output_file}")


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("算法优化器稳定性测试")
    logger.info("=" * 80)
    
    all_results = {}
    
    # 测试1：不同的形态
    try:
        results = test_different_patterns()
        all_results['test_different_patterns'] = results
    except Exception as e:
        logger.error(f"测试1失败: {e}")
        logger.error(traceback.format_exc())
    
    # 测试2：不同的数据集大小
    try:
        results = test_different_dataset_sizes()
        all_results['test_different_dataset_sizes'] = results
    except Exception as e:
        logger.error(f"测试2失败: {e}")
        logger.error(traceback.format_exc())
    
    # 测试3：不同的迭代次数
    try:
        results = test_different_iterations()
        all_results['test_different_iterations'] = results
    except Exception as e:
        logger.error(f"测试3失败: {e}")
        logger.error(traceback.format_exc())
    
    # 测试4：多次运行的稳定性
    try:
        results = test_stability()
        all_results['test_stability'] = results
    except Exception as e:
        logger.error(f"测试4失败: {e}")
        logger.error(traceback.format_exc())
    
    # 分析结果
    analyze_results(all_results)
    
    # 保存结果
    save_results(all_results)
    
    logger.info("\n" + "=" * 80)
    logger.info("测试完成")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
