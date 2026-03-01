#!/usr/bin/env python3
"""
多进程和异步计算性能验证脚本 - 优化版
验证智能选择机制的性能提升
"""

import os
import sys
import time
import asyncio
import pandas as pd
import numpy as np
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from core.loguru_config import initialize_loguru
initialize_loguru("INFO")

from core.unified_indicator_service import UnifiedIndicatorService, IndicatorProcessPool


class MultiprocessPerformanceAnalyzer:
    """多进程性能分析器"""
    
    def __init__(self):
        self.service = UnifiedIndicatorService()
        np.random.seed(42)
    
    def _generate_test_data(self, rows: int) -> pd.DataFrame:
        """生成测试数据"""
        dates = pd.date_range(start='2023-01-01', periods=rows, freq='D')
        
        base_price = 10.0
        prices = []
        for i in range(rows):
            change = np.random.uniform(-0.03, 0.03)
            base_price = base_price * (1 + change)
            prices.append(base_price)
        
        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p * (1 + np.random.uniform(0, 0.02)) for p in prices],
            'low': [p * (1 - np.random.uniform(0, 0.02)) for p in prices],
            'close': [p * (1 + np.random.uniform(-0.01, 0.01)) for p in prices],
            'volume': [int(np.random.uniform(1000000, 10000000)) for _ in range(rows)]
        })
        df.set_index('date', inplace=True)
        return df
    
    def test_smart_selection(self) -> Dict[str, Any]:
        """测试智能选择机制"""
        print("\n" + "="*70)
        print("1. 智能选择机制测试")
        print("="*70)
        
        self.service.enable_multiprocess(True)
        
        test_cases = [
            (500, 2, "小数据量+少指标"),
            (500, 6, "小数据量+多指标"),
            (5000, 2, "中等数据量+少指标"),
            (5000, 6, "中等数据量+多指标"),
            (20000, 6, "大数据量+多指标"),
        ]
        
        results = {}
        
        for data_size, indicator_count, desc in test_cases:
            df = self._generate_test_data(data_size)
            indicators = [
                ('MA', {'timeperiod': 5}),
                ('MA', {'timeperiod': 10}),
                ('MA', {'timeperiod': 20}),
                ('RSI', {'timeperiod': 14}),
                ('MACD', {}),
                ('BBANDS', {}),
            ][:indicator_count]
            
            start = time.perf_counter()
            result = self.service.calculate_parallel(indicators, df)
            elapsed = (time.perf_counter() - start) * 1000
            
            results[desc] = {
                "data_size": data_size,
                "indicator_count": indicator_count,
                "time_ms": elapsed
            }
            
            print(f"  {desc}:")
            print(f"    数据量: {data_size}行, 指标数: {indicator_count}")
            print(f"    耗时: {elapsed:.3f}ms")
        
        return results
    
    def test_sync_vs_smart(self) -> Dict[str, Any]:
        """对比同步计算与智能选择"""
        print("\n" + "="*70)
        print("2. 同步计算 vs 智能选择对比")
        print("="*70)
        
        indicators = [
            ('MA', {'timeperiod': 20}),
            ('RSI', {'timeperiod': 14}),
            ('MACD', {}),
            ('BBANDS', {}),
        ]
        
        data_sizes = [500, 2000, 5000, 10000, 20000]
        results = {}
        
        for size in data_sizes:
            df = self._generate_test_data(size)
            
            start = time.perf_counter()
            sync_result = self.service.batch_calculate_indicators(indicators, df.copy())
            sync_time = (time.perf_counter() - start) * 1000
            
            self.service.enable_multiprocess(True)
            start = time.perf_counter()
            smart_result = self.service.calculate_parallel(indicators, df.copy())
            smart_time = (time.perf_counter() - start) * 1000
            
            speedup = sync_time / smart_time if smart_time > 0 else 0
            
            results[size] = {
                "sync_time_ms": sync_time,
                "smart_time_ms": smart_time,
                "speedup": speedup
            }
            
            print(f"  {size}行数据:")
            print(f"    同步计算: {sync_time:.3f}ms")
            print(f"    智能选择: {smart_time:.3f}ms")
            print(f"    加速比: {speedup:.2f}x")
        
        return results
    
    async def test_async_performance(self) -> Dict[str, Any]:
        """测试异步计算性能"""
        print("\n" + "="*70)
        print("3. 异步计算性能测试")
        print("="*70)
        
        self.service.enable_multiprocess(True)
        self.service.enable_async_calculation(True)
        
        df = self._generate_test_data(2000)
        
        iterations = 5
        times = []
        
        for i in range(iterations):
            start = time.perf_counter()
            
            tasks = [
                self.service.calculate_indicator_async('MA', df.copy(), {'timeperiod': 20}),
                self.service.calculate_indicator_async('RSI', df.copy(), {'timeperiod': 14}),
                self.service.calculate_indicator_async('MACD', df.copy()),
            ]
            
            results = await asyncio.gather(*tasks)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            print(f"  迭代 {i+1}: {elapsed:.3f}ms")
        
        avg_time = np.mean(times)
        print(f"\n  平均耗时: {avg_time:.3f}ms")
        
        return {"avg_time_ms": avg_time, "iterations": iterations}
    
    def compare_results_accuracy(self) -> bool:
        """比较计算结果准确性"""
        print("\n" + "="*70)
        print("4. 计算结果准确性验证")
        print("="*70)
        
        indicators = [
            ('MA', {'timeperiod': 20}),
            ('RSI', {'timeperiod': 14}),
        ]
        
        df = self._generate_test_data(500)
        
        sync_result = self.service.batch_calculate_indicators(indicators, df.copy())
        
        self.service.enable_multiprocess(True)
        smart_result = self.service.calculate_parallel(indicators, df.copy())
        
        all_match = True
        for col in sync_result.columns:
            if col in smart_result.columns:
                sync_vals = sync_result[col].dropna().values
                smart_vals = smart_result[col].dropna().values
                
                if len(sync_vals) == len(smart_vals):
                    diff = np.abs(sync_vals - smart_vals)
                    max_diff = np.max(diff) if len(diff) > 0 else 0
                    
                    if max_diff < 1e-10:
                        print(f"  ✓ {col}: 结果一致")
                    else:
                        print(f"  ✗ {col}: 最大差异 {max_diff}")
                        all_match = False
                else:
                    print(f"  ✗ {col}: 长度不匹配")
                    all_match = False
        
        return all_match
    
    def run_full_analysis(self) -> Dict[str, Any]:
        """运行完整分析"""
        print("\n" + "="*70)
        print("多进程和异步计算性能验证 - 智能选择优化版")
        print("="*70)
        
        results = {}
        
        results["smart_selection"] = self.test_smart_selection()
        results["sync_vs_smart"] = self.test_sync_vs_smart()
        
        try:
            loop = asyncio.get_event_loop()
            results["async"] = loop.run_until_complete(self.test_async_performance())
        except Exception as e:
            print(f"\n  ! 异步测试失败: {e}")
            results["async"] = {"error": str(e)}
        
        results["accuracy"] = self.compare_results_accuracy()
        
        print("\n" + "="*70)
        print("性能优化总结")
        print("="*70)
        
        print("\n  智能选择策略:")
        print("    - 数据量 < 1000行: 使用同步计算")
        print("    - 数据量 1000-5000行: 使用同步计算")
        print("    - 数据量 > 5000行 + 多进程启用: 使用进程池")
        
        print(f"\n  结果准确性: {'✓ 通过' if results['accuracy'] else '✗ 失败'}")
        
        if self.service._process_pool:
            self.service._process_pool.shutdown()
        
        return results


def main():
    analyzer = MultiprocessPerformanceAnalyzer()
    results = analyzer.run_full_analysis()
    
    print("\n" + "="*70)
    if results.get("accuracy", False):
        print("✓ 多进程和异步计算功能验证通过！")
    else:
        print("请检查计算结果准确性。")
    print("="*70)


if __name__ == "__main__":
    main()
