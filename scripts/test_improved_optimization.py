"""
测试改进后的优化方法
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
        logging.FileHandler('improved_optimization_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def create_test_data(size=1000):
    """创建测试数据"""
    np.random.seed(42)
    
    dates = pd.date_range(start='2020-01-01', periods=size, freq='D')
    
    data = {
        'datetime': dates,
        'open': np.random.uniform(100, 200, size),
        'high': np.random.uniform(100, 200, size),
        'low': np.random.uniform(100, 200, size),
        'close': np.random.uniform(100, 200, size),
        'amount': np.random.uniform(1000000, 10000000, size),
        'volume': np.random.uniform(100000, 1000000, size)
    }
    
    df = pd.DataFrame(data)
    
    # 确保 high >= max(open, close) 和 low <= min(open, close)
    df['high'] = np.maximum(df['high'], np.maximum(df['open'], df['close']))
    df['low'] = np.minimum(df['low'], np.minimum(df['open'], df['close']))
    
    return df


def test_improved_gradient_optimization():
    """测试改进后的梯度优化"""
    logger.info("=" * 80)
    logger.info("测试改进后的梯度优化（Adam优化器）")
    logger.info("=" * 80)
    
    # 创建测试数据
    logger.info("\n步骤1：创建测试数据")
    test_data = create_test_data(size=1000)
    logger.info(f"  测试数据大小: {len(test_data)}")
    
    # 创建优化器
    logger.info("\n步骤2：创建优化器")
    optimizer = AlgorithmOptimizer(debug_mode=True)
    
    # 测试梯度优化
    logger.info("\n步骤3：测试梯度优化（Adam优化器）")
    config = OptimizationConfig(
        method="gradient",
        max_iterations=10,
        target_metric="overall_score"
    )
    
    result = optimizer.optimize_algorithm("hammer", config, [test_data])
    
    # 输出结果
    logger.info("\n优化结果:")
    logger.info(f"  方法: {result.get('method', 'unknown')}")
    logger.info(f"  最佳评分: {result.get('best_score', 0):.3f}")
    logger.info(f"  基准评分: {result.get('baseline_score', 0):.3f}")
    logger.info(f"  性能提升: {result.get('improvement_percentage', 0):.3f}%")
    logger.info(f"  迭代次数: {result.get('iterations', 0)}")
    logger.info(f"  优化时间: {result.get('optimization_time', 0):.3f}秒")
    
    # 输出优化日志
    optimization_log = result.get('optimization_log', [])
    if optimization_log:
        logger.info(f"\n优化日志（前5次迭代）:")
        for log in optimization_log[:5]:
            logger.info(f"  迭代 {log['iteration']}:")
            logger.info(f"    参数: {log['parameters']}")
            logger.info(f"    评分: {log['score']:.3f}")
            logger.info(f"    梯度: {log['gradients']}")
    
    return result


def test_improved_random_optimization():
    """测试改进后的随机优化"""
    logger.info("\n" + "=" * 80)
    logger.info("测试改进后的随机优化（改进版）")
    logger.info("=" * 80)
    
    # 创建测试数据
    logger.info("\n步骤1：创建测试数据")
    test_data = create_test_data(size=1000)
    logger.info(f"  测试数据大小: {len(test_data)}")
    
    # 创建优化器
    logger.info("\n步骤2：创建优化器")
    optimizer = AlgorithmOptimizer(debug_mode=True)
    
    # 测试随机优化
    logger.info("\n步骤3：测试随机优化（改进版）")
    config = OptimizationConfig(
        method="random",
        max_iterations=20,
        target_metric="overall_score"
    )
    
    result = optimizer.optimize_algorithm("hammer", config, [test_data])
    
    # 输出结果
    logger.info("\n优化结果:")
    logger.info(f"  方法: {result.get('method', 'unknown')}")
    logger.info(f"  最佳评分: {result.get('best_score', 0):.3f}")
    logger.info(f"  基准评分: {result.get('baseline_score', 0):.3f}")
    logger.info(f"  性能提升: {result.get('improvement_percentage', 0):.3f}%")
    logger.info(f"  迭代次数: {result.get('iterations', 0)}")
    logger.info(f"  优化时间: {result.get('optimization_time', 0):.3f}秒")
    
    return result


def test_improved_bayesian_optimization():
    """测试改进后的贝叶斯优化"""
    logger.info("\n" + "=" * 80)
    logger.info("测试改进后的贝叶斯优化（改进版）")
    logger.info("=" * 80)
    
    # 创建测试数据
    logger.info("\n步骤1：创建测试数据")
    test_data = create_test_data(size=1000)
    logger.info(f"  测试数据大小: {len(test_data)}")
    
    # 创建优化器
    logger.info("\n步骤2：创建优化器")
    optimizer = AlgorithmOptimizer(debug_mode=True)
    
    # 测试贝叶斯优化
    logger.info("\n步骤3：测试贝叶斯优化（改进版）")
    config = OptimizationConfig(
        method="bayesian",
        max_iterations=20,
        target_metric="overall_score"
    )
    
    result = optimizer.optimize_algorithm("hammer", config, [test_data])
    
    # 输出结果
    logger.info("\n优化结果:")
    logger.info(f"  方法: {result.get('method', 'unknown')}")
    logger.info(f"  最佳评分: {result.get('best_score', 0):.3f}")
    logger.info(f"  基准评分: {result.get('baseline_score', 0):.3f}")
    logger.info(f"  性能提升: {result.get('improvement_percentage', 0):.3f}%")
    logger.info(f"  迭代次数: {result.get('iterations', 0)}")
    logger.info(f"  优化时间: {result.get('optimization_time', 0):.3f}秒")
    
    return result


def test_all_improved_methods():
    """测试所有改进后的优化方法"""
    logger.info("\n" + "=" * 80)
    logger.info("测试所有改进后的优化方法")
    logger.info("=" * 80)
    
    # 创建测试数据
    test_data = create_test_data(size=1000)
    
    # 创建优化器
    optimizer = AlgorithmOptimizer(debug_mode=True)
    
    # 测试所有优化方法
    methods = ["genetic", "bayesian", "random", "gradient"]
    results = []
    
    for method in methods:
        logger.info(f"\n测试方法: {method}")
        
        config = OptimizationConfig(
            method=method,
            max_iterations=10,
            target_metric="overall_score"
        )
        
        result = optimizer.optimize_algorithm("hammer", config, [test_data])
        results.append(result)
        
        logger.info(f"  最佳评分: {result.get('best_score', 0):.3f}")
        logger.info(f"  性能提升: {result.get('improvement_percentage', 0):.3f}%")
        logger.info(f"  优化时间: {result.get('optimization_time', 0):.3f}秒")
    
    # 输出对比结果
    logger.info("\n" + "=" * 80)
    logger.info("优化方法对比")
    logger.info("=" * 80)
    
    for result in results:
        method = result.get('method', 'unknown')
        best_score = result.get('best_score', 0)
        improvement = result.get('improvement_percentage', 0)
        time = result.get('optimization_time', 0)
        
        logger.info(f"{method:12s}: 评分={best_score:.3f}, 提升={improvement:.3f}%, 时间={time:.3f}秒")
    
    # 保存结果
    test_report = {
        "test_date": datetime.now().isoformat(),
        "test_results": results,
        "summary": {
            "total_tests": len(results),
            "successful_tests": sum(1 for r in results if r.get('success', False)),
            "failed_tests": sum(1 for r in results if not r.get('success', False))
        }
    }
    
    import json
    with open('IMPROVED_OPTIMIZATION_TEST_REPORT.json', 'w', encoding='utf-8') as f:
        json.dump(test_report, f, indent=2, ensure_ascii=False)
    
    logger.info("\n测试报告已保存到 IMPROVED_OPTIMIZATION_TEST_REPORT.json")
    
    return results


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("改进后的优化方法测试")
    logger.info("=" * 80)
    
    # 测试所有改进后的优化方法
    results = test_all_improved_methods()
    
    logger.info("\n" + "=" * 80)
    logger.info("测试完成")
    logger.info("=" * 80)
    
    # 输出总结
    successful_tests = sum(1 for r in results if r.get('success', False))
    failed_tests = sum(1 for r in results if not r.get('success', False))
    
    logger.info(f"成功测试: {successful_tests}/{len(results)}")
    logger.info(f"失败测试: {failed_tests}/{len(results)}")
    
    # 计算平均性能提升
    improvements = [r.get('improvement_percentage', 0) for r in results if r.get('success', False)]
    if improvements:
        avg_improvement = np.mean(improvements)
        logger.info(f"平均性能提升: {avg_improvement:.3f}%")


if __name__ == "__main__":
    main()
