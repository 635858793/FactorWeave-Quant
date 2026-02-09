#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
梯度优化调试脚本

专门测试梯度优化，并输出详细的调试信息
"""

import sys
import os
import time
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
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="DEBUG")

from optimization.algorithm_optimizer import AlgorithmOptimizer, OptimizationConfig


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
    for i in range(50, 100, 10):
        close_prices[i] = 100 + i * 0.5
        open_prices[i] = close_prices[i] + 0.1
        high_prices[i] = max(open_prices[i], close_prices[i]) + 0.05
        low_prices[i] = min(open_prices[i], close_prices[i]) - 0.5  # 长下影线
    
    # 十字星：开盘价和收盘价几乎相同
    for i in range(200, 250, 10):
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


def test_gradient_optimization():
    """测试梯度优化"""
    logger.info("=" * 80)
    logger.info("梯度优化调试测试")
    logger.info("=" * 80)
    
    # 创建测试数据
    logger.info("\n步骤1：创建测试数据")
    test_data = create_test_data()
    logger.info(f"  测试数据形状: {test_data.shape}")
    logger.info(f"  数据范围: {test_data['datetime'].min()} 到 {test_data['datetime'].max()}")
    
    # 创建优化器
    logger.info("\n步骤2：创建优化器")
    optimizer = AlgorithmOptimizer(debug_mode=True)
    logger.info("  优化器创建成功")
    
    # 测试梯度优化
    logger.info("\n步骤3：测试梯度优化")
    logger.info("=" * 80)
    
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
        
        logger.info(f"\n梯度优化完成，耗时：{optimization_time:.4f}秒")
        logger.info(f"优化结果：")
        logger.info(f"  方法：{result.get('method', 'N/A')}")
        logger.info(f"  最佳评分：{result.get('best_score', 0):.3f}")
        logger.info(f"  基准评分：{result.get('baseline_score', 0):.3f}")
        logger.info(f"  性能提升：{result.get('improvement_percentage', 0):.3f}%")
        logger.info(f"  迭代次数：{result.get('iterations', 0)}")
        logger.info(f"  最佳版本ID：{result.get('best_version_id', 'N/A')}")
        
        # 输出优化日志
        optimization_log = result.get('optimization_log', [])
        if optimization_log:
            logger.info(f"\n优化日志：")
            for log in optimization_log:
                logger.info(f"  迭代 {log['iteration']}:")
                logger.info(f"    参数: {log['parameters']}")
                logger.info(f"    评分: {log['score']:.3f}")
                logger.info(f"    梯度: {log['gradients']}")
        
    except ValueError as e:
        logger.warning(f"⚠️ 形态不存在：{e}")
        logger.warning("跳过梯度优化测试")
    except Exception as e:
        logger.error(f"❌ 梯度优化失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    logger.info("\n" + "=" * 80)
    logger.info("测试完成")
    logger.info("=" * 80)


if __name__ == "__main__":
    test_gradient_optimization()
