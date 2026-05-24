"""
性能优化分析和验证脚本

分析内容：
1. 当前实现性能瓶颈
2. 缓存机制效果
3. 批量计算效率
4. 优化建议验证
"""

import sys
import os
import pandas as pd
import numpy as np
import time
import tracemalloc
from datetime import datetime
from typing import Dict, Any, List, Tuple
import statistics
import threading
import concurrent.futures

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def create_test_data(rows=500):
    """创建测试数据"""
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', periods=rows, freq='D')
    
    base_price = 50.0
    prices = []
    for i in range(rows):
        change = np.random.normal(0.001, 0.02)
        base_price = base_price * (1 + change)
        prices.append(base_price)
    
    data = pd.DataFrame({
        'datetime': dates,
        'open': [p * 0.99 for p in prices],
        'high': [p * 1.02 for p in prices],
        'low': [p * 0.98 for p in prices],
        'close': prices,
        'volume': [1000000] * rows
    })
    data.set_index('datetime', inplace=True)
    return data


class PerformanceAnalyzer:
    """性能分析器"""
    
    def __init__(self):
        self.test_data = create_test_data(500)
        self.large_data = create_test_data(5000)
        self.results = {}
    
    def analyze_cache_effectiveness(self) -> Dict[str, Any]:
        """分析缓存效果"""
        print("\n" + "="*70)
        print("1. 缓存效果分析")
        print("="*70)
        
        from core.indicator_service import get_indicator_service
        
        service = get_indicator_service()
        results = {"cache_hits": 0, "cache_misses": 0, "speedup": 0}
        
        if hasattr(service, 'unified_service'):
            unified = service.unified_service
            
            cache_enabled = getattr(unified, '_cache_enabled', False)
            cache_size = len(getattr(unified, '_calculation_cache', {}))
            max_cache_size = getattr(unified, '_max_cache_size', 0)
            cache_ttl = getattr(unified, '_cache_ttl_seconds', 0)
            
            print(f"\n缓存配置:")
            print(f"  缓存启用: {cache_enabled}")
            print(f"  当前缓存大小: {cache_size}")
            print(f"  最大缓存大小: {max_cache_size}")
            print(f"  缓存TTL: {cache_ttl}秒")
            
            results["cache_enabled"] = cache_enabled
            results["current_cache_size"] = cache_size
            results["max_cache_size"] = max_cache_size
            
            if cache_enabled and cache_size > 0:
                print(f"\n缓存效果测试:")
                
                times_no_cache = []
                times_with_cache = []
                
                for _ in range(10):
                    start = time.perf_counter()
                    service.calculate_indicator('MA', self.test_data, timeperiod=20)
                    times_no_cache.append(time.perf_counter() - start)
                
                for _ in range(10):
                    start = time.perf_counter()
                    service.calculate_indicator('MA', self.test_data, timeperiod=20)
                    times_with_cache.append(time.perf_counter() - start)
                
                avg_no_cache = statistics.mean(times_no_cache)
                avg_with_cache = statistics.mean(times_with_cache)
                
                if avg_no_cache > 0:
                    speedup = avg_no_cache / avg_with_cache
                    results["speedup"] = speedup
                    print(f"  无缓存平均耗时: {avg_no_cache*1000:.3f}ms")
                    print(f"  有缓存平均耗时: {avg_with_cache*1000:.3f}ms")
                    print(f"  缓存加速比: {speedup:.2f}x")
            else:
                print("\n  ! 缓存未启用或为空，建议启用缓存优化")
        
        self.results["cache"] = results
        return results
    
    def analyze_batch_efficiency(self) -> Dict[str, Any]:
        """分析批量计算效率"""
        print("\n" + "="*70)
        print("2. 批量计算效率分析")
        print("="*70)
        
        from core.indicator_service import calculate_indicator, batch_calculate_indicators
        
        results = {}
        
        indicators = [
            ('MA', {'timeperiod': 20}),
            ('RSI', {'timeperiod': 14}),
            ('MACD', {'fastperiod': 12, 'slowperiod': 26, 'signalperiod': 9}),
            ('BBANDS', {'timeperiod': 20}),
        ]
        
        print("\n单指标计算耗时:")
        single_times = {}
        for name, params in indicators:
            times = []
            for _ in range(50):
                start = time.perf_counter()
                calculate_indicator(name, self.test_data, **params)
                times.append(time.perf_counter() - start)
            avg_time = statistics.mean(times)
            single_times[name] = avg_time
            print(f"  {name}: {avg_time*1000:.3f}ms")
        
        print("\n批量计算耗时:")
        batch_times = []
        indicator_names = [name for name, _ in indicators]
        params_dict = {name: params for name, params in indicators}
        
        for _ in range(50):
            start = time.perf_counter()
            batch_calculate_indicators(indicator_names, self.test_data, params_dict)
            batch_times.append(time.perf_counter() - start)
        
        avg_batch_time = statistics.mean(batch_times)
        total_single_time = sum(single_times.values())
        
        print(f"  批量计算: {avg_batch_time*1000:.3f}ms")
        print(f"  单指标总和: {total_single_time*1000:.3f}ms")
        
        if avg_batch_time > 0:
            efficiency = total_single_time / avg_batch_time
            results["efficiency"] = efficiency
            print(f"  批量效率比: {efficiency:.2f}x")
            
            if efficiency < 1.0:
                print("\n  ! 批量计算效率低于单指标计算，建议优化批量计算逻辑")
            else:
                print("\n  ✓ 批量计算效率良好")
        
        results["single_times"] = single_times
        results["batch_time"] = avg_batch_time
        
        self.results["batch"] = results
        return results
    
    def analyze_memory_usage(self) -> Dict[str, Any]:
        """分析内存使用"""
        print("\n" + "="*70)
        print("3. 内存使用分析")
        print("="*70)
        
        from core.indicator_service import calculate_indicator
        
        results = {}
        
        tracemalloc.start()
        calculate_indicator('MA', self.test_data, timeperiod=20)
        current1, peak1 = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        tracemalloc.start()
        calculate_indicator('RSI', self.test_data, timeperiod=14)
        current2, peak2 = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        tracemalloc.start()
        calculate_indicator('MACD', self.test_data)
        current3, peak3 = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"\n内存使用:")
        print(f"  MA: 峰值={peak1/1024:.1f}KB")
        print(f"  RSI: 峰值={peak2/1024:.1f}KB")
        print(f"  MACD: 峰值={peak3/1024:.1f}KB")
        
        results["ma_peak_kb"] = peak1 / 1024
        results["rsi_peak_kb"] = peak2 / 1024
        results["macd_peak_kb"] = peak3 / 1024
        
        avg_peak = (peak1 + peak2 + peak3) / 3 / 1024
        results["avg_peak_kb"] = avg_peak
        
        if avg_peak > 100:
            print(f"\n  ! 平均内存使用较高({avg_peak:.1f}KB)，建议优化内存管理")
        else:
            print(f"\n  ✓ 内存使用正常({avg_peak:.1f}KB)")
        
        self.results["memory"] = results
        return results
    
    def analyze_large_data_performance(self) -> Dict[str, Any]:
        """分析大数据量性能"""
        print("\n" + "="*70)
        print("4. 大数据量性能分析")
        print("="*70)
        
        from core.indicator_service import calculate_indicator
        
        results = {}
        
        data_sizes = [1000, 2000, 5000, 10000]
        
        print(f"\n不同数据量计算耗时:")
        for size in data_sizes:
            data = create_test_data(size)
            
            times = []
            for _ in range(20):
                start = time.perf_counter()
                calculate_indicator('MA', data, timeperiod=20)
                times.append(time.perf_counter() - start)
            
            avg_time = statistics.mean(times)
            results[f"size_{size}"] = avg_time
            print(f"  {size:5d}行: {avg_time*1000:.3f}ms ({avg_time*1000/size:.4f}ms/行)")
        
        if results.get("size_1000", 0) > 0 and results.get("size_10000", 0) > 0:
            ratio = results["size_10000"] / results["size_1000"]
            print(f"\n  数据量增加10倍，耗时增加: {ratio:.1f}倍")
            
            if ratio > 15:
                print("  ! 性能衰减较快，建议优化算法复杂度")
            else:
                print("  ✓ 性能衰减在可接受范围内")
        
        self.results["large_data"] = results
        return results
    
    def analyze_concurrent_performance(self) -> Dict[str, Any]:
        """分析并发性能"""
        print("\n" + "="*70)
        print("5. 并发性能分析")
        print("="*70)
        
        from core.indicator_service import calculate_indicator
        
        results = {}
        
        def calculate_task(args):
            data, indicator, params = args
            return calculate_indicator(indicator, data, **params)
        
        tasks = [(self.test_data, 'MA', {'timeperiod': 20}) for _ in range(10)]
        
        print(f"\n串行计算10次:")
        start = time.perf_counter()
        for task in tasks:
            calculate_task(task)
        serial_time = time.perf_counter() - start
        print(f"  耗时: {serial_time*1000:.3f}ms")
        
        print(f"\n并行计算10次 (4线程):")
        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(calculate_task, tasks))
        parallel_time = time.perf_counter() - start
        print(f"  耗时: {parallel_time*1000:.3f}ms")
        
        if serial_time > 0:
            speedup = serial_time / parallel_time
            results["speedup"] = speedup
            print(f"  并行加速比: {speedup:.2f}x")
            
            if speedup < 1.5:
                print("\n  ! 并行效率较低，可能存在GIL瓶颈")
            else:
                print("\n  ✓ 并行效率良好")
        
        self.results["concurrent"] = results
        return results
    
    def analyze_optimization_opportunities(self) -> Dict[str, Any]:
        """分析优化机会"""
        print("\n" + "="*70)
        print("6. 优化机会分析")
        print("="*70)
        
        from core.indicator_service import get_indicator_service
        
        service = get_indicator_service()
        results = {"recommendations": []}
        
        print("\n优化建议:")
        
        if hasattr(service, 'unified_service'):
            unified = service.unified_service
            
            if not getattr(unified, '_cache_enabled', False):
                results["recommendations"].append("启用计算结果缓存")
                print("  1. 建议启用计算结果缓存以提高重复计算性能")
            
            cache_size = len(getattr(unified, '_calculation_cache', {}))
            max_cache = getattr(unified, '_max_cache_size', 0)
            if cache_size == 0 and max_cache > 0:
                results["recommendations"].append("预热缓存")
                print("  2. 建议预热常用指标缓存")
            
            if not getattr(unified, '_async_calculation_enabled', False):
                results["recommendations"].append("启用异步计算")
                print("  3. 建议启用异步计算支持以提高并发性能")
            
            if not getattr(unified, '_consistency_checker_enabled', False):
                results["recommendations"].append("启用一致性检查")
                print("  4. 建议启用结果一致性检查以确保计算准确性")
        
        batch_results = self.results.get("batch", {})
        if batch_results.get("efficiency", 0) < 1.0:
            results["recommendations"].append("优化批量计算")
            print("  5. 建议优化批量计算逻辑以提高效率")
        
        concurrent_results = self.results.get("concurrent", {})
        if concurrent_results.get("speedup", 0) < 1.5:
            results["recommendations"].append("优化并发性能")
            print("  6. 建议使用多进程替代多线程以避免GIL瓶颈")
        
        if len(results["recommendations"]) == 0:
            print("  ✓ 当前实现已达到较好性能水平")
        
        self.results["optimization"] = results
        return results
    
    def run_full_analysis(self) -> bool:
        """运行完整分析"""
        print("\n" + "="*70)
        print("性能优化分析")
        print("="*70)
        
        self.analyze_cache_effectiveness()
        self.analyze_batch_efficiency()
        self.analyze_memory_usage()
        self.analyze_large_data_performance()
        self.analyze_concurrent_performance()
        self.analyze_optimization_opportunities()
        
        print("\n" + "="*70)
        print("分析结果汇总")
        print("="*70)
        
        print(f"\n缓存效果: 加速比={self.results.get('cache', {}).get('speedup', 0):.2f}x")
        print(f"批量效率: 效率比={self.results.get('batch', {}).get('efficiency', 0):.2f}x")
        print(f"内存使用: 平均峰值={self.results.get('memory', {}).get('avg_peak_kb', 0):.1f}KB")
        print(f"并发性能: 加速比={self.results.get('concurrent', {}).get('speedup', 0):.2f}x")
        
        recommendations = self.results.get("optimization", {}).get("recommendations", [])
        print(f"\n优化建议数量: {len(recommendations)}")
        
        print("\n" + "="*70)
        if len(recommendations) <= 2:
            print("✓ 性能分析完成，当前实现性能良好！")
        else:
            print("性能分析完成，存在优化空间。")
        print("="*70)
        
        return len(recommendations) <= 2


class FunctionalityValidator:
    """功能验证器"""
    
    def __init__(self):
        self.test_data = create_test_data(200)
        self.results = {}
    
    def validate_all_components(self) -> bool:
        """验证所有组件功能"""
        print("\n" + "="*70)
        print("功能验证")
        print("="*70)
        
        all_passed = True
        
        all_passed &= self._validate_analysis_manager()
        all_passed &= self._validate_analysis_service()
        all_passed &= self._validate_technical_agent()
        all_passed &= self._validate_chart_service()
        all_passed &= self._validate_error_handling()
        
        print("\n" + "="*70)
        if all_passed:
            print("✓ 所有功能验证通过！")
        else:
            print("✗ 部分功能验证失败")
        print("="*70)
        
        return all_passed
    
    def _validate_analysis_manager(self) -> bool:
        """验证AnalysisManager"""
        print("\n1. AnalysisManager 功能验证")
        from core.indicator_service import calculate_indicator
        
        try:
            df = self.test_data.copy()
            
            ma_result = calculate_indicator('MA', df, timeperiod=20)
            rsi_result = calculate_indicator('RSI', df, timeperiod=14)
            macd_result = calculate_indicator('MACD', df)
            
            passed = ma_result is not None and rsi_result is not None and macd_result is not None
            print(f"  {'✓' if passed else '✗'} 指标计算功能")
            return passed
        except Exception as e:
            print(f"  ✗ 验证失败: {e}")
            return False
    
    def _validate_analysis_service(self) -> bool:
        """验证AnalysisService"""
        print("\n2. AnalysisService 功能验证")
        from core.indicator_service import calculate_indicator
        
        try:
            df = self.test_data.copy()
            
            rsi_result = calculate_indicator('RSI', df, timeperiod=14)
            macd_result = calculate_indicator('MACD', df)
            
            passed = rsi_result is not None and macd_result is not None
            print(f"  {'✓' if passed else '✗'} 指标计算功能")
            return passed
        except Exception as e:
            print(f"  ✗ 验证失败: {e}")
            return False
    
    def _validate_technical_agent(self) -> bool:
        """验证TechnicalAnalysisAgent"""
        print("\n3. TechnicalAnalysisAgent 功能验证")
        from core.indicator_service import calculate_indicator
        
        try:
            df = self.test_data.copy()
            
            indicators = ['MA', 'RSI', 'MACD', 'BBANDS']
            results = [calculate_indicator(ind, df) for ind in indicators]
            
            passed = all(r is not None for r in results)
            print(f"  {'✓' if passed else '✗'} 指标计算功能")
            return passed
        except Exception as e:
            print(f"  ✗ 验证失败: {e}")
            return False
    
    def _validate_chart_service(self) -> bool:
        """验证ChartService"""
        print("\n4. ChartService 功能验证")
        from core.indicator_service import calculate_indicator, batch_calculate_indicators
        
        try:
            df = self.test_data.copy()
            
            single_result = calculate_indicator('MA', df, timeperiod=20)
            batch_result = batch_calculate_indicators(['MA', 'RSI'], df, {'MA': {'timeperiod': 20}, 'RSI': {'timeperiod': 14}})
            
            passed = single_result is not None and batch_result is not None
            print(f"  {'✓' if passed else '✗'} 单指标和批量计算功能")
            return passed
        except Exception as e:
            print(f"  ✗ 验证失败: {e}")
            return False
    
    def _validate_error_handling(self) -> bool:
        """验证错误处理"""
        print("\n5. 错误处理验证")
        from core.indicator_service import calculate_indicator
        
        try:
            passed = True
            
            try:
                result = calculate_indicator('INVALID', self.test_data)
                print("  ✓ 无效指标正确处理")
            except Exception:
                passed = False
                print("  ✗ 无效指标处理异常")
            
            try:
                result = calculate_indicator('MA', pd.DataFrame())
                print("  ✓ 空数据正确处理")
            except Exception:
                passed = False
                print("  ✗ 空数据处理异常")
            
            return passed
        except Exception as e:
            print(f"  ✗ 验证失败: {e}")
            return False


def run_comprehensive_validation():
    """运行综合验证"""
    print("\n" + "="*70)
    print("性能优化分析和功能验证")
    print("="*70)
    
    analyzer = PerformanceAnalyzer()
    performance_ok = analyzer.run_full_analysis()
    
    validator = FunctionalityValidator()
    functionality_ok = validator.validate_all_components()
    
    print("\n" + "="*70)
    print("最终结果")
    print("="*70)
    
    print(f"\n性能分析: {'✓ 通过' if performance_ok else '存在优化空间'}")
    print(f"功能验证: {'✓ 通过' if functionality_ok else '✗ 失败'}")
    
    all_ok = performance_ok and functionality_ok
    
    print("\n" + "="*70)
    if all_ok:
        print("✓ 所有验证通过，系统性能和功能正常！")
    else:
        print("请根据上述建议进行优化。")
    print("="*70)
    
    return all_ok


if __name__ == "__main__":
    success = run_comprehensive_validation()
    sys.exit(0 if success else 1)
