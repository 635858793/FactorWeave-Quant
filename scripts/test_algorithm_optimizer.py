#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
算法优化器测试脚本

测试AlgorithmOptimizer的实际效果，包括：
1. 遗传算法优化
2. 贝叶斯优化
3. 随机搜索优化
4. 梯度优化
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


def create_test_data() -> pd.DataFrame:
    """创建测试数据，包含明确的形态"""
    np.random.seed(42)
    
    # 创建1000条K线数据
    n = 1000
    dates = pd.date_range(start='2020-01-01', periods=n, freq='D')
    
    # 生成随机价格数据
    close_prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
    open_prices = close_prices + np.random.randn(n) * 0.2
    high_prices = np.maximum(open_prices, close_prices) + np.random.rand(n) * 0.3
    low_prices = np.minimum(open_prices, close_prices) - np.random.rand(n) * 0.3
    volumes = np.random.randint(1000, 10000, n)
    
    # 添加一些明确的形态
    # 锤子线：小实体，长下影线，短上影线
    for i in range(100, 200, 20):
        body = abs(close_prices[i] - open_prices[i])
        lower_shadow = min(open_prices[i], close_prices[i]) - low_prices[i]
        upper_shadow = high_prices[i] - max(open_prices[i], close_prices[i])
        
        # 调整为锤子线形态
        close_prices[i] = open_prices[i] + body * 0.1  # 小实体
        low_prices[i] = min(open_prices[i], close_prices[i]) - body * 3  # 长下影线
        high_prices[i] = max(open_prices[i], close_prices[i]) + body * 0.2  # 短上影线
    
    # 十字星：开盘价和收盘价几乎相同
    for i in range(300, 400, 20):
        close_prices[i] = open_prices[i] + (np.random.rand() - 0.5) * 0.01  # 几乎相同
        high_prices[i] = max(open_prices[i], close_prices[i]) + np.random.rand() * 0.5
        low_prices[i] = min(open_prices[i], close_prices[i]) - np.random.rand() * 0.5
    
    # 吞没形态：大实体吞没前一个小实体
    for i in range(500, 600, 20):
        # 前一天小实体
        close_prices[i-1] = open_prices[i-1] + (np.random.rand() - 0.5) * 0.2
        high_prices[i-1] = max(open_prices[i-1], close_prices[i-1]) + np.random.rand() * 0.1
        low_prices[i-1] = min(open_prices[i-1], close_prices[i-1]) - np.random.rand() * 0.1
        
        # 当天大实体吞没
        if close_prices[i-1] > open_prices[i-1]:  # 前一天阳线
            open_prices[i] = close_prices[i-1] - 0.5  # 低开
            close_prices[i] = open_prices[i-1] + 0.5  # 高收
        else:  # 前一天阴线
            open_prices[i] = close_prices[i-1] + 0.5  # 高开
            close_prices[i] = open_prices[i-1] - 0.5  # 低收
        
        high_prices[i] = max(open_prices[i], close_prices[i]) + np.random.rand() * 0.2
        low_prices[i] = min(open_prices[i], close_prices[i]) - np.random.rand() * 0.2
    
    data = pd.DataFrame({
        'datetime': dates,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volumes
    })
    
    return data


def test_algorithm_optimizer():
    """测试算法优化器"""
    logger.info("=" * 80)
    logger.info("算法优化器测试")
    logger.info("=" * 80)
    
    # 初始化变量
    optimizer = None
    test_data = None
    test_results = []
    
    try:
        # 导入AlgorithmOptimizer
        logger.info("\n" + "=" * 80)
        logger.info("步骤1：导入AlgorithmOptimizer")
        logger.info("=" * 80)
        
        try:
            from optimization.algorithm_optimizer import AlgorithmOptimizer, OptimizationConfig
            logger.info("✅ AlgorithmOptimizer导入成功")
        except ImportError as e:
            logger.error(f"❌ AlgorithmOptimizer导入失败：{e}")
            logger.error("AlgorithmOptimizer可能不存在或路径不正确")
            return
        except Exception as e:
            logger.error(f"❌ AlgorithmOptimizer导入失败：{e}")
            logger.error(traceback.format_exc())
            return
        
        # 创建测试数据
        logger.info("\n" + "=" * 80)
        logger.info("步骤2：创建测试数据")
        logger.info("=" * 80)
        
        try:
            test_data = create_test_data()
            logger.info(f"✅ 测试数据创建成功：{len(test_data)}条K线数据")
            logger.info(f"数据范围：{test_data['datetime'].min()} 到 {test_data['datetime'].max()}")
            logger.info(f"价格范围：{test_data['close'].min():.2f} 到 {test_data['close'].max():.2f}")
        except Exception as e:
            logger.error(f"❌ 测试数据创建失败：{e}")
            logger.error(traceback.format_exc())
            return
        
        # 创建优化器
        logger.info("\n" + "=" * 80)
        logger.info("步骤3：创建算法优化器")
        logger.info("=" * 80)
        
        try:
            start_time = time.time()
            optimizer = AlgorithmOptimizer(debug_mode=True)
            init_time = time.time() - start_time
            logger.info(f"✅ 算法优化器创建成功，耗时：{init_time:.4f}秒")
        except Exception as e:
            logger.error(f"❌ 算法优化器创建失败：{e}")
            logger.error(traceback.format_exc())
            return
        
        # 测试遗传算法优化
        logger.info("\n" + "=" * 80)
        logger.info("步骤4：测试遗传算法优化")
        logger.info("=" * 80)
        
        try:
            config = OptimizationConfig(
                method="genetic",
                max_iterations=5,  # 减少迭代次数以加快测试
                population_size=5,
                mutation_rate=0.1,
                crossover_rate=0.8,
                target_metric="overall_score",
                min_improvement=0.05,
                timeout_minutes=5,
                parallel_workers=2
            )
            
            logger.info(f"优化配置：")
            logger.info(f"  方法：{config.method}")
            logger.info(f"  最大迭代次数：{config.max_iterations}")
            logger.info(f"  种群大小：{config.population_size}")
            logger.info(f"  变异率：{config.mutation_rate}")
            logger.info(f"  交叉率：{config.crossover_rate}")
            logger.info(f"  目标指标：{config.target_metric}")
            logger.info(f"  最小改进：{config.min_improvement}")
            logger.info(f"  超时时间：{config.timeout_minutes}分钟")
            logger.info(f"  并行工作线程：{config.parallel_workers}")
            
            start_time = time.time()
            
            # 尝试优化一个形态
            try:
                result = optimizer.optimize_algorithm("hammer", config, [test_data])
                optimization_time = time.time() - start_time
                
                logger.info(f"\n✅ 遗传算法优化完成，耗时：{optimization_time:.4f}秒")
                logger.info(f"优化结果：")
                logger.info(f"  方法：{result.get('method', 'N/A')}")
                logger.info(f"  最佳评分：{result.get('best_score', 0):.3f}")
                logger.info(f"  基准评分：{result.get('baseline_score', 0):.3f}")
                logger.info(f"  性能提升：{result.get('improvement_percentage', 0):.3f}%")
                logger.info(f"  迭代次数：{result.get('iterations', 0)}")
                logger.info(f"  最佳版本ID：{result.get('best_version_id', 'N/A')}")
                
                test_results.append({
                    'method': 'genetic',
                    'success': True,
                    'optimization_time': optimization_time,
                    'best_score': result.get('best_score', 0),
                    'baseline_score': result.get('baseline_score', 0),
                    'improvement_percentage': result.get('improvement_percentage', 0),
                    'iterations': result.get('iterations', 0),
                    'best_version_id': result.get('best_version_id', 'N/A')
                })
                
            except ValueError as e:
                logger.warning(f"⚠️ 形态不存在：{e}")
                logger.warning("跳过遗传算法优化测试")
                test_results.append({
                    'method': 'genetic',
                    'success': False,
                    'error': str(e),
                    'optimization_time': time.time() - start_time
                })
            except Exception as e:
                logger.error(f"❌ 遗传算法优化失败：{e}")
                logger.error(traceback.format_exc())
                test_results.append({
                    'method': 'genetic',
                    'success': False,
                    'error': str(e),
                    'optimization_time': time.time() - start_time
                })
                
        except Exception as e:
            logger.error(f"❌ 遗传算法优化测试失败：{e}")
            logger.error(traceback.format_exc())
        
        # 测试贝叶斯优化
        logger.info("\n" + "=" * 80)
        logger.info("步骤5：测试贝叶斯优化")
        logger.info("=" * 80)
        
        try:
            config = OptimizationConfig(
                method="bayesian",
                max_iterations=5,
                population_size=5,
                target_metric="overall_score",
                min_improvement=0.05,
                timeout_minutes=5
            )
            
            logger.info(f"优化配置：")
            logger.info(f"  方法：{config.method}")
            logger.info(f"  最大迭代次数：{config.max_iterations}")
            logger.info(f"  目标指标：{config.target_metric}")
            
            start_time = time.time()
            
            try:
                result = optimizer.optimize_algorithm("hammer", config, [test_data])
                optimization_time = time.time() - start_time
                
                logger.info(f"\n✅ 贝叶斯优化完成，耗时：{optimization_time:.4f}秒")
                logger.info(f"优化结果：")
                logger.info(f"  方法：{result.get('method', 'N/A')}")
                logger.info(f"  最佳评分：{result.get('best_score', 0):.3f}")
                logger.info(f"  基准评分：{result.get('baseline_score', 0):.3f}")
                logger.info(f"  性能提升：{result.get('improvement_percentage', 0):.3f}%")
                logger.info(f"  迭代次数：{result.get('iterations', 0)}")
                logger.info(f"  最佳版本ID：{result.get('best_version_id', 'N/A')}")
                
                test_results.append({
                    'method': 'bayesian',
                    'success': True,
                    'optimization_time': optimization_time,
                    'best_score': result.get('best_score', 0),
                    'baseline_score': result.get('baseline_score', 0),
                    'improvement_percentage': result.get('improvement_percentage', 0),
                    'iterations': result.get('iterations', 0),
                    'best_version_id': result.get('best_version_id', 'N/A')
                })
                
            except ValueError as e:
                logger.warning(f"⚠️ 形态不存在：{e}")
                logger.warning("跳过贝叶斯优化测试")
                test_results.append({
                    'method': 'bayesian',
                    'success': False,
                    'error': str(e),
                    'optimization_time': time.time() - start_time
                })
            except Exception as e:
                logger.error(f"❌ 贝叶斯优化失败：{e}")
                logger.error(traceback.format_exc())
                test_results.append({
                    'method': 'bayesian',
                    'success': False,
                    'error': str(e),
                    'optimization_time': time.time() - start_time
                })
                
        except Exception as e:
            logger.error(f"❌ 贝叶斯优化测试失败：{e}")
            logger.error(traceback.format_exc())
        
        # 测试随机搜索优化
        logger.info("\n" + "=" * 80)
        logger.info("步骤6：测试随机搜索优化")
        logger.info("=" * 80)
        
        try:
            config = OptimizationConfig(
                method="random",
                max_iterations=5,
                target_metric="overall_score",
                min_improvement=0.05,
                timeout_minutes=5
            )
            
            logger.info(f"优化配置：")
            logger.info(f"  方法：{config.method}")
            logger.info(f"  最大迭代次数：{config.max_iterations}")
            logger.info(f"  目标指标：{config.target_metric}")
            
            start_time = time.time()
            
            try:
                result = optimizer.optimize_algorithm("hammer", config, [test_data])
                optimization_time = time.time() - start_time
                
                logger.info(f"\n✅ 随机搜索优化完成，耗时：{optimization_time:.4f}秒")
                logger.info(f"优化结果：")
                logger.info(f"  方法：{result.get('method', 'N/A')}")
                logger.info(f"  最佳评分：{result.get('best_score', 0):.3f}")
                logger.info(f"  基准评分：{result.get('baseline_score', 0):.3f}")
                logger.info(f"  性能提升：{result.get('improvement_percentage', 0):.3f}%")
                logger.info(f"  迭代次数：{result.get('iterations', 0)}")
                logger.info(f"  最佳版本ID：{result.get('best_version_id', 'N/A')}")
                
                test_results.append({
                    'method': 'random',
                    'success': True,
                    'optimization_time': optimization_time,
                    'best_score': result.get('best_score', 0),
                    'baseline_score': result.get('baseline_score', 0),
                    'improvement_percentage': result.get('improvement_percentage', 0),
                    'iterations': result.get('iterations', 0),
                    'best_version_id': result.get('best_version_id', 'N/A')
                })
                
            except ValueError as e:
                logger.warning(f"⚠️ 形态不存在：{e}")
                logger.warning("跳过随机搜索优化测试")
                test_results.append({
                    'method': 'random',
                    'success': False,
                    'error': str(e),
                    'optimization_time': time.time() - start_time
                })
            except Exception as e:
                logger.error(f"❌ 随机搜索优化失败：{e}")
                logger.error(traceback.format_exc())
                test_results.append({
                    'method': 'random',
                    'success': False,
                    'error': str(e),
                    'optimization_time': time.time() - start_time
                })
                
        except Exception as e:
            logger.error(f"❌ 随机搜索优化测试失败：{e}")
            logger.error(traceback.format_exc())
        
        # 测试梯度优化
        logger.info("\n" + "=" * 80)
        logger.info("步骤7：测试梯度优化")
        logger.info("=" * 80)
        
        try:
            config = OptimizationConfig(
                method="gradient",
                max_iterations=5,
                target_metric="overall_score",
                min_improvement=0.05,
                timeout_minutes=5
            )
            
            logger.info(f"优化配置：")
            logger.info(f"  方法：{config.method}")
            logger.info(f"  最大迭代次数：{config.max_iterations}")
            logger.info(f"  目标指标：{config.target_metric}")
            
            start_time = time.time()
            
            try:
                result = optimizer.optimize_algorithm("hammer", config, [test_data])
                optimization_time = time.time() - start_time
                
                logger.info(f"\n✅ 梯度优化完成，耗时：{optimization_time:.4f}秒")
                logger.info(f"优化结果：")
                logger.info(f"  方法：{result.get('method', 'N/A')}")
                logger.info(f"  最佳评分：{result.get('best_score', 0):.3f}")
                logger.info(f"  基准评分：{result.get('baseline_score', 0):.3f}")
                logger.info(f"  性能提升：{result.get('improvement_percentage', 0):.3f}%")
                logger.info(f"  迭代次数：{result.get('iterations', 0)}")
                logger.info(f"  最佳版本ID：{result.get('best_version_id', 'N/A')}")
                
                test_results.append({
                    'method': 'gradient',
                    'success': True,
                    'optimization_time': optimization_time,
                    'best_score': result.get('best_score', 0),
                    'baseline_score': result.get('baseline_score', 0),
                    'improvement_percentage': result.get('improvement_percentage', 0),
                    'iterations': result.get('iterations', 0),
                    'best_version_id': result.get('best_version_id', 'N/A')
                })
                
            except ValueError as e:
                logger.warning(f"⚠️ 形态不存在：{e}")
                logger.warning("跳过梯度优化测试")
                test_results.append({
                    'method': 'gradient',
                    'success': False,
                    'error': str(e),
                    'optimization_time': time.time() - start_time
                })
            except Exception as e:
                logger.error(f"❌ 梯度优化失败：{e}")
                logger.error(traceback.format_exc())
                test_results.append({
                    'method': 'gradient',
                    'success': False,
                    'error': str(e),
                    'optimization_time': time.time() - start_time
                })
                
        except Exception as e:
            logger.error(f"❌ 梯度优化测试失败：{e}")
            logger.error(traceback.format_exc())
        
    except Exception as e:
        logger.error(f"❌ 测试过程中发生错误：{e}")
        logger.error(traceback.format_exc())
    
    # 生成测试报告
    logger.info("\n" + "=" * 80)
    logger.info("测试报告")
    logger.info("=" * 80)
    
    logger.info(f"\n测试结果汇总：")
    logger.info(f"  测试方法数量：{len(test_results)}")
    logger.info(f"  成功数量：{sum(1 for r in test_results if r.get('success', False))}")
    logger.info(f"  失败数量：{sum(1 for r in test_results if not r.get('success', False))}")
    
    logger.info(f"\n详细测试结果：")
    for i, result in enumerate(test_results, 1):
        logger.info(f"\n{i}. {result.get('method', 'N/A')}优化：")
        logger.info(f"  成功：{'是' if result.get('success', False) else '否'}")
        if result.get('success', False):
            logger.info(f"  优化时间：{result.get('optimization_time', 0):.4f}秒")
            logger.info(f"  最佳评分：{result.get('best_score', 0):.3f}")
            logger.info(f"  基准评分：{result.get('baseline_score', 0):.3f}")
            logger.info(f"  性能提升：{result.get('improvement_percentage', 0):.3f}%")
            logger.info(f"  迭代次数：{result.get('iterations', 0)}")
            logger.info(f"  最佳版本ID：{result.get('best_version_id', 'N/A')}")
        else:
            logger.info(f"  错误：{result.get('error', 'N/A')}")
            logger.info(f"  优化时间：{result.get('optimization_time', 0):.4f}秒")
    
    # 保存测试报告
    report_file = os.path.join(project_root, 'ALGORITHM_OPTIMIZER_TEST_REPORT.json')
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump({
            'test_date': datetime.now().isoformat(),
            'test_results': test_results,
            'summary': {
                'total_tests': len(test_results),
                'successful_tests': sum(1 for r in test_results if r.get('success', False)),
                'failed_tests': sum(1 for r in test_results if not r.get('success', False))
            }
        }, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n测试报告已保存到：{report_file}")
    
    logger.info("\n" + "=" * 80)
    logger.info("测试完成")
    logger.info("=" * 80)


if __name__ == "__main__":
    test_algorithm_optimizer()
