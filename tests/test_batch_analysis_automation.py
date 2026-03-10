# -*- coding: utf-8 -*-
"""
批量分析功能自动化测试套件 - 静态代码分析版

测试覆盖：
1. UI组件完整性
2. 并发安全性
3. 性能优化（并行执行、节流更新、缓存）
4. 事件总线集成
5. 引擎实例复用
"""
import sys
import os
import time
import unittest
import ast
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read_file_content(file_path):
    """读取文件内容"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


class TestBatchAnalysisCodeStructure(unittest.TestCase):
    """测试代码结构完整性"""

    def test_ui_components_structure(self):
        """测试ui_components.py结构"""
        content = read_file_content('gui/ui_components.py')

        self.assertIn('class AnalysisToolsPanel', content)
        self.assertIn('_create_batch_analysis_ui', content)
        self.assertIn('_batch_results_lock', content)

    def test_batch_analysis_mixin_structure(self):
        """测试enhanced_batch_analysis_methods.py结构"""
        content = read_file_content('gui/enhanced_batch_analysis_methods.py')

        required_methods = [
            'start_enhanced_batch_analysis',
            '_run_enhanced_batch_analysis',
            '_run_real_backtest_analysis',
            '_generate_technical_signals',
            '_get_backtest_engine',
            '_publish_batch_analysis_event',
            '_run_real_backtest_analysis_safe',
            '_should_update_ui',
            '_schedule_ui_update',
            '_get_cached_kline_data',
        ]

        for method in required_methods:
            self.assertIn(
                f'def {method}',
                content,
                f"缺少方法: {method}"
            )


class TestConcurrencySafety(unittest.TestCase):
    """测试并发安全性"""

    def test_thread_lock_exists(self):
        """测试线程锁是否存在"""
        content = read_file_content('gui/ui_components.py')

        self.assertIn('_batch_results_lock', content)
        self.assertIn('threading.Lock()', content)

    def test_thread_safe_operations(self):
        """测试线程安全操作"""
        content = read_file_content('gui/enhanced_batch_analysis_methods.py')

        self.assertIn('with self._batch_results_lock:', content)

    def test_imports(self):
        """测试导入"""
        content = read_file_content('gui/enhanced_batch_analysis_methods.py')

        self.assertIn('import threading', content)


class TestPerformanceOptimization(unittest.TestCase):
    """测试性能优化"""

    def test_parallel_execution(self):
        """测试并行执行"""
        content = read_file_content('gui/enhanced_batch_analysis_methods.py')

        self.assertIn('ThreadPoolExecutor', content)
        self.assertIn('as_completed', content)
        self.assertIn('max_workers', content)

    def test_ui_throttle(self):
        """测试UI节流"""
        ui_content = read_file_content('gui/ui_components.py')
        methods_content = read_file_content('gui/enhanced_batch_analysis_methods.py')

        self.assertIn('_ui_update_interval', ui_content)
        self.assertIn('_last_ui_update_time', ui_content)
        self.assertIn('_should_update_ui', methods_content)

    def test_kline_cache(self):
        """测试K线缓存"""
        ui_content = read_file_content('gui/ui_components.py')
        methods_content = read_file_content('gui/enhanced_batch_analysis_methods.py')

        self.assertIn('_kline_cache', ui_content)
        self.assertIn('_kline_cache_timeout', ui_content)
        self.assertIn('_get_cached_kline_data', methods_content)

    def test_parallel_workers_config(self):
        """测试并行工作线程配置"""
        content = read_file_content('gui/ui_components.py')

        self.assertIn('_batch_parallel_workers', content)


class TestEventBusIntegration(unittest.TestCase):
    """测试事件总线集成"""

    def test_event_publish(self):
        """测试事件发布"""
        content = read_file_content('gui/enhanced_batch_analysis_methods.py')

        self.assertIn('_publish_batch_analysis_event', content)
        self.assertIn('AnalysisCompleteEvent', content)
        self.assertIn('get_event_bus', content)


class TestEngineReuse(unittest.TestCase):
    """测试引擎实例复用"""

    def test_engine_getter(self):
        """测试引擎获取方法"""
        content = read_file_content('gui/enhanced_batch_analysis_methods.py')

        self.assertIn('_get_backtest_engine', content)
        self.assertIn('_backtest_engine', content)


class TestKlineCache(unittest.TestCase):
    """测试K线数据缓存"""

    def test_cache_method(self):
        """测试缓存方法"""
        content = read_file_content('gui/enhanced_batch_analysis_methods.py')

        self.assertIn('def _get_cached_kline_data', content)

    def test_cache_usage(self):
        """测试缓存使用"""
        content = read_file_content('gui/enhanced_batch_analysis_methods.py')

        self.assertIn('_get_cached_kline_data(', content)


class TestParallelExecution(unittest.TestCase):
    """测试并行执行功能"""

    def test_executor_context_manager(self):
        """测试执行器上下文管理器"""
        content = read_file_content('gui/enhanced_batch_analysis_methods.py')

        self.assertIn('with ThreadPoolExecutor', content)

    def test_task_submission(self):
        """测试任务提交"""
        content = read_file_content('gui/enhanced_batch_analysis_methods.py')

        self.assertIn('executor.submit', content)


class TestUIThrottle(unittest.TestCase):
    """测试UI节流功能"""

    def test_throttle_interval(self):
        """测试节流间隔"""
        content = read_file_content('gui/ui_components.py')

        match = re.search(r'_ui_update_interval\s*=\s*(\d+)', content)
        self.assertIsNotNone(match)
        interval = int(match.group(1))
        self.assertGreater(interval, 0)
        self.assertLessEqual(interval, 2000)


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_batch_analysis_flow(self):
        """测试批量分析流程"""
        methods_content = read_file_content('gui/enhanced_batch_analysis_methods.py')

        self.assertIn('def start_enhanced_batch_analysis', methods_content)
        self.assertIn('def _run_enhanced_batch_analysis', methods_content)

    def test_real_backtest_integration(self):
        """测试真实回测集成"""
        content = read_file_content('gui/enhanced_batch_analysis_methods.py')

        self.assertIn('StockService', content)
        self.assertIn('UnifiedBacktestEngine', content)
        self.assertIn('run_backtest', content)


def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始运行批量分析功能自动化测试")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestBatchAnalysisCodeStructure))
    suite.addTests(loader.loadTestsFromTestCase(TestConcurrencySafety))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceOptimization))
    suite.addTests(loader.loadTestsFromTestCase(TestEventBusIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestEngineReuse))
    suite.addTests(loader.loadTestsFromTestCase(TestKlineCache))
    suite.addTests(loader.loadTestsFromTestCase(TestParallelExecution))
    suite.addTests(loader.loadTestsFromTestCase(TestUIThrottle))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"测试总数: {result.testsRun}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print(f"跳过: {len(result.skipped)}")

    if result.wasSuccessful():
        print("\n✓ 所有自动化测试通过!")
        return 0
    else:
        print("\n✗ 部分测试失败")
        return 1


if __name__ == '__main__':
    sys.exit(run_tests())
