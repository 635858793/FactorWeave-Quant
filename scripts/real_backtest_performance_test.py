#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
真实回测性能测试
真正调用回测引擎进行性能测试
"""

import os
import sys
import time
import numpy as np
import pandas as pd
from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import traceback

# 确保项目根目录在Python路径中
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 配置日志
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('real_backtest_performance_test.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class BacktestPerformanceResult:
    """回测性能测试结果"""
    test_name: str
    data_size: int
    execution_time: float
    backtest_speed: float  # 万条/秒
    engine_type: str
    success: bool
    notes: str
    timestamp: str


class RealBacktestPerformanceTest:
    """真实回测性能测试类"""

    def __init__(self):
        """初始化测试器"""
        self.results: List[BacktestPerformanceResult] = []
        
    def generate_test_data(self, size: int = 100000) -> pd.DataFrame:
        """生成测试数据
        
        Args:
            size: 数据条数
            
        Returns:
            包含价格和信号的DataFrame
        """
        logger.info(f"生成测试数据: {size}条")
        
        np.random.seed(42)
        
        data = pd.DataFrame({
            'open': np.random.randn(size).cumsum() + 100,
            'high': np.random.randn(size).cumsum() + 102,
            'low': np.random.randn(size).cumsum() + 98,
            'close': np.random.randn(size).cumsum() + 100,
            'volume': np.random.exponential(1000, size)
        })
        
        # 生成随机交易信号（简化版）
        signals = np.zeros(size)
        for i in range(20, size):
            if i % 50 == 0:
                signals[i] = 1  # 买入信号
            elif i % 100 == 0:
                signals[i] = -1  # 卖出信号
        
        data['signal'] = signals
        
        return data
    
    def test_vectorized_engine(self, data_size: int = 100000) -> BacktestPerformanceResult:
        """测试向量化引擎性能
        
        Args:
            data_size: 数据条数
            
        Returns:
            测试结果
        """
        logger.info("=" * 80)
        logger.info(f"测试向量化引擎性能 - 数据量: {data_size}条")
        logger.info("=" * 80)
        
        try:
            # 导入向量化引擎
            from backtest.backtest_optimizer import VectorizedBacktestEngine, BacktestOptimizationLevel
            
            # 生成测试数据
            test_data = self.generate_test_data(data_size)
            
            # 初始化引擎
            engine = VectorizedBacktestEngine(BacktestOptimizationLevel.PROFESSIONAL)
            
            # 测量执行时间
            start_time = time.time()
            
            # 运行回测
            result = engine.run_vectorized_backtest(
                data=test_data,
                signal_col='signal',
                price_col='close',
                initial_capital=100000,
                position_size=1.0,
                commission_pct=0.001,
                slippage_pct=0.001
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # 计算回测速度（万条/秒）
            backtest_speed = (data_size / 10000) / execution_time
            
            logger.info(f"✅ 测试完成")
            logger.info(f"   执行时间: {execution_time:.4f}秒")
            logger.info(f"   回测速度: {backtest_speed:.2f}万条/秒")
            logger.info(f"   结果行数: {len(result)}")
            
            return BacktestPerformanceResult(
                test_name='向量化引擎',
                data_size=data_size,
                execution_time=execution_time,
                backtest_speed=backtest_speed,
                engine_type='VectorizedBacktestEngine',
                success=True,
                notes=f"执行时间: {execution_time:.4f}秒",
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            traceback.print_exc()
            return BacktestPerformanceResult(
                test_name='向量化引擎',
                data_size=data_size,
                execution_time=0,
                backtest_speed=0,
                engine_type='VectorizedBacktestEngine',
                success=False,
                notes=str(e),
                timestamp=datetime.now().isoformat()
            )
    
    def test_unified_engine(self, data_size: int = 100000) -> BacktestPerformanceResult:
        """测试统一回测引擎性能
        
        Args:
            data_size: 数据条数
            
        Returns:
            测试结果
        """
        logger.info("=" * 80)
        logger.info(f"测试统一回测引擎性能 - 数据量: {data_size}条")
        logger.info("=" * 80)
        
        try:
            # 导入统一回测引擎
            from backtest.unified_backtest_engine import UnifiedBacktestEngine, BacktestLevel
            
            # 生成测试数据
            test_data = self.generate_test_data(data_size)
            
            # 初始化引擎
            engine = UnifiedBacktestEngine(
                backtest_level=BacktestLevel.PROFESSIONAL,
                use_vectorized_engine=True,
                auto_select_engine=True
            )
            
            # 测量执行时间
            start_time = time.time()
            
            # 运行回测
            result = engine.run_backtest(
                data=test_data,
                signal_col='signal',
                price_col='close',
                initial_capital=100000,
                position_size=1.0,
                commission_pct=0.001,
                slippage_pct=0.001,
                min_commission=5.0
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # 计算回测速度（万条/秒）
            backtest_speed = (data_size / 10000) / execution_time
            
            logger.info(f"✅ 测试完成")
            logger.info(f"   执行时间: {execution_time:.4f}秒")
            logger.info(f"   回测速度: {backtest_speed:.2f}万条/秒")
            logger.info(f"   结果类型: {type(result)}")
            
            return BacktestPerformanceResult(
                test_name='统一回测引擎',
                data_size=data_size,
                execution_time=execution_time,
                backtest_speed=backtest_speed,
                engine_type='UnifiedBacktestEngine',
                success=True,
                notes=f"执行时间: {execution_time:.4f}秒",
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            traceback.print_exc()
            return BacktestPerformanceResult(
                test_name='统一回测引擎',
                data_size=data_size,
                execution_time=0,
                backtest_speed=0,
                engine_type='UnifiedBacktestEngine',
                success=False,
                notes=str(e),
                timestamp=datetime.now().isoformat()
            )
    
    def test_jit_optimized_core(self, data_size: int = 100000) -> BacktestPerformanceResult:
        """测试JIT优化核心函数性能
        
        Args:
            data_size: 数据条数
            
        Returns:
            测试结果
        """
        logger.info("=" * 80)
        logger.info(f"测试JIT优化核心函数性能 - 数据量: {data_size}条")
        logger.info("=" * 80)
        
        try:
            # 导入JIT优化函数
            from backtest.jit_optimizer import optimized_backtest_core
            
            # 生成测试数据
            test_data = self.generate_test_data(data_size)
            
            # 提取NumPy数组
            prices = test_data['close'].astype(float).values
            signals = test_data['signal'].astype(float).values
            
            # 测量执行时间
            start_time = time.time()
            
            # 运行回测
            positions, capital, returns = optimized_backtest_core(
                prices=prices,
                signals=signals,
                initial_capital=100000,
                position_size=1.0,
                commission_pct=0.001,
                slippage_pct=0.001
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # 计算回测速度（万条/秒）
            backtest_speed = (data_size / 10000) / execution_time
            
            logger.info(f"✅ 测试完成")
            logger.info(f"   执行时间: {execution_time:.4f}秒")
            logger.info(f"   回测速度: {backtest_speed:.2f}万条/秒")
            logger.info(f"   结果长度: {len(capital)}")
            
            return BacktestPerformanceResult(
                test_name='JIT优化核心函数',
                data_size=data_size,
                execution_time=execution_time,
                backtest_speed=backtest_speed,
                engine_type='optimized_backtest_core',
                success=True,
                notes=f"执行时间: {execution_time:.4f}秒",
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            traceback.print_exc()
            return BacktestPerformanceResult(
                test_name='JIT优化核心函数',
                data_size=data_size,
                execution_time=0,
                backtest_speed=0,
                engine_type='optimized_backtest_core',
                success=False,
                notes=str(e),
                timestamp=datetime.now().isoformat()
            )
    
    def run_all_tests(self, data_sizes: List[int] = None) -> Dict[str, Any]:
        """运行所有测试
        
        Args:
            data_sizes: 测试数据大小列表
            
        Returns:
            测试结果汇总
        """
        if data_sizes is None:
            data_sizes = [10000, 50000, 100000, 500000, 1000000]
        
        logger.info("=" * 80)
        logger.info("开始运行所有回测性能测试")
        logger.info("=" * 80)
        
        all_results = []
        
        for data_size in data_sizes:
            logger.info(f"\n{'=' * 80}")
            logger.info(f"测试数据量: {data_size}条")
            logger.info(f"{'=' * 80}\n")
            
            # 测试JIT优化核心函数
            result_jit = self.test_jit_optimized_core(data_size)
            all_results.append(result_jit)
            
            # 测试向量化引擎
            result_vectorized = self.test_vectorized_engine(data_size)
            all_results.append(result_vectorized)
            
            # 测试统一回测引擎
            result_unified = self.test_unified_engine(data_size)
            all_results.append(result_unified)
        
        # 生成汇总报告
        summary = self._generate_summary(all_results)
        
        return {
            'results': all_results,
            'summary': summary
        }
    
    def _generate_summary(self, results: List[BacktestPerformanceResult]) -> Dict[str, Any]:
        """生成测试汇总
        
        Args:
            results: 测试结果列表
            
        Returns:
            汇总信息
        """
        summary = {
            'total_tests': len(results),
            'successful_tests': sum(1 for r in results if r.success),
            'failed_tests': sum(1 for r in results if not r.success),
            'by_engine': {},
            'by_data_size': {}
        }
        
        # 按引擎类型汇总
        for result in results:
            if result.engine_type not in summary['by_engine']:
                summary['by_engine'][result.engine_type] = {
                    'count': 0,
                    'successful': 0,
                    'avg_speed': 0.0,
                    'max_speed': 0.0,
                    'min_speed': float('inf')
                }
            
            engine_summary = summary['by_engine'][result.engine_type]
            engine_summary['count'] += 1
            if result.success:
                engine_summary['successful'] += 1
                engine_summary['avg_speed'] += result.backtest_speed
                engine_summary['max_speed'] = max(engine_summary['max_speed'], result.backtest_speed)
                engine_summary['min_speed'] = min(engine_summary['min_speed'], result.backtest_speed)
        
        # 计算平均速度
        for engine_type in summary['by_engine']:
            if summary['by_engine'][engine_type]['successful'] > 0:
                summary['by_engine'][engine_type]['avg_speed'] /= summary['by_engine'][engine_type]['successful']
            else:
                summary['by_engine'][engine_type]['min_speed'] = 0.0
        
        # 按数据大小汇总
        for result in results:
            if result.data_size not in summary['by_data_size']:
                summary['by_data_size'][result.data_size] = {
                    'count': 0,
                    'successful': 0,
                    'avg_speed': 0.0,
                    'best_engine': None,
                    'best_speed': 0.0
                }
            
            size_summary = summary['by_data_size'][result.data_size]
            size_summary['count'] += 1
            if result.success:
                size_summary['successful'] += 1
                size_summary['avg_speed'] += result.backtest_speed
                
                if result.backtest_speed > size_summary['best_speed']:
                    size_summary['best_speed'] = result.backtest_speed
                    size_summary['best_engine'] = result.engine_type
        
        # 计算平均速度
        for data_size in summary['by_data_size']:
            if summary['by_data_size'][data_size]['successful'] > 0:
                summary['by_data_size'][data_size]['avg_speed'] /= summary['by_data_size'][data_size]['successful']
        
        return summary
    
    def print_summary(self, summary: Dict[str, Any]):
        """打印测试汇总
        
        Args:
            summary: 汇总信息
        """
        logger.info("\n" + "=" * 80)
        logger.info("测试汇总报告")
        logger.info("=" * 80)
        
        logger.info(f"\n总测试数: {summary['total_tests']}")
        logger.info(f"成功: {summary['successful_tests']}")
        logger.info(f"失败: {summary['failed_tests']}")
        
        logger.info("\n按引擎类型汇总:")
        logger.info("-" * 80)
        for engine_type, engine_summary in summary['by_engine'].items():
            logger.info(f"\n引擎: {engine_type}")
            logger.info(f"  测试次数: {engine_summary['count']}")
            logger.info(f"  成功次数: {engine_summary['successful']}")
            logger.info(f"  平均速度: {engine_summary['avg_speed']:.2f}万条/秒")
            logger.info(f"  最大速度: {engine_summary['max_speed']:.2f}万条/秒")
            logger.info(f"  最小速度: {engine_summary['min_speed']:.2f}万条/秒")
        
        logger.info("\n按数据大小汇总:")
        logger.info("-" * 80)
        for data_size, size_summary in sorted(summary['by_data_size'].items()):
            logger.info(f"\n数据量: {data_size}条")
            logger.info(f"  测试次数: {size_summary['count']}")
            logger.info(f"  成功次数: {size_summary['successful']}")
            logger.info(f"  平均速度: {size_summary['avg_speed']:.2f}万条/秒")
            logger.info(f"  最佳引擎: {size_summary['best_engine']}")
            logger.info(f"  最佳速度: {size_summary['best_speed']:.2f}万条/秒")


def main():
    """主函数"""
    logger.info("开始真实回测性能测试")
    
    # 创建测试器
    tester = RealBacktestPerformanceTest()
    
    # 运行测试
    test_data_sizes = [10000, 50000, 100000, 500000, 1000000]
    results = tester.run_all_tests(test_data_sizes)
    
    # 打印汇总
    tester.print_summary(results['summary'])
    
    logger.info("\n测试完成")
    
    return results


if __name__ == '__main__':
    main()
