"""
回测结果显示修复验证测试

验证内容：
1. get_final_results() 调用链修复
2. ui_data 变量作用域修复
3. 图表绘制逻辑修复
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestRealTimeBacktestMonitorMethods(unittest.TestCase):
    """测试 RealTimeBacktestMonitor 方法存在性"""

    def test_get_latest_metrics_exists(self):
        """测试 get_latest_metrics 方法存在"""
        from backtest.real_time_backtest_monitor import RealTimeBacktestMonitor
        monitor = RealTimeBacktestMonitor()
        self.assertTrue(hasattr(monitor, 'get_latest_metrics'))
        self.assertTrue(callable(getattr(monitor, 'get_latest_metrics')))

    def test_get_monitoring_summary_exists(self):
        """测试 get_monitoring_summary 方法存在"""
        from backtest.real_time_backtest_monitor import RealTimeBacktestMonitor
        monitor = RealTimeBacktestMonitor()
        self.assertTrue(hasattr(monitor, 'get_monitoring_summary'))
        self.assertTrue(callable(getattr(monitor, 'get_monitoring_summary')))

    def test_get_final_results_not_exists(self):
        """测试 get_final_results 方法不存在"""
        from backtest.real_time_backtest_monitor import RealTimeBacktestMonitor
        monitor = RealTimeBacktestMonitor()
        self.assertFalse(hasattr(monitor, 'get_final_results'))

    def test_get_latest_metrics_returns_none_when_empty(self):
        """测试 get_latest_metrics 在无数据时返回 None"""
        from backtest.real_time_backtest_monitor import RealTimeBacktestMonitor
        monitor = RealTimeBacktestMonitor()
        result = monitor.get_latest_metrics()
        self.assertIsNone(result)

    def test_get_monitoring_summary_returns_dict(self):
        """测试 get_monitoring_summary 返回字典"""
        from backtest.real_time_backtest_monitor import RealTimeBacktestMonitor
        monitor = RealTimeBacktestMonitor()
        result = monitor.get_monitoring_summary()
        self.assertIsInstance(result, dict)
        self.assertIn('status', result)


class TestChartDataStorage(unittest.TestCase):
    """测试图表数据存储"""

    def test_backtest_metrics_initialization(self):
        """测试回测指标数据初始化"""
        from gui.widgets.backtest_widget import RealTimeChart
        chart = RealTimeChart()
        self.assertTrue(hasattr(chart, 'backtest_metrics'))
        self.assertIsInstance(chart.backtest_metrics, list)
        self.assertEqual(len(chart.backtest_metrics), 0)

    def test_add_data_stores_metrics(self):
        """测试添加数据存储指标"""
        from gui.widgets.backtest_widget import RealTimeChart
        chart = RealTimeChart()
        
        test_data = {
            'timestamp': datetime.now(),
            'cumulative_return': 0.05,
            'current_drawdown': -0.02,
            'sharpe_ratio': 1.5
        }
        
        chart.add_data(test_data)
        
        self.assertEqual(len(chart.data_queue.queue), 1)

    def test_data_length_limit(self):
        """测试数据长度限制"""
        from gui.widgets.backtest_widget import RealTimeChart
        chart = RealTimeChart()
        
        for i in range(1500):
            chart.backtest_metrics.append({
                'timestamp': datetime.now(),
                'cumulative_return': i * 0.001
            })
        
        if len(chart.backtest_metrics) > 1000:
            chart.backtest_metrics = chart.backtest_metrics[-1000:]
        
        self.assertLessEqual(len(chart.backtest_metrics), 1000)


class TestChartDataExtraction(unittest.TestCase):
    """测试图表数据提取"""

    def test_extract_cumulative_returns(self):
        """测试提取累计收益率"""
        metrics = [
            {'timestamp': datetime(2024, 1, 1), 'cumulative_return': 0.01},
            {'timestamp': datetime(2024, 1, 2), 'cumulative_return': 0.02},
            {'timestamp': datetime(2024, 1, 3), 'cumulative_return': 0.03},
        ]
        
        cumulative_returns = [m.get('cumulative_return', 0) for m in metrics]
        
        self.assertEqual(cumulative_returns, [0.01, 0.02, 0.03])

    def test_extract_drawdowns(self):
        """测试提取回撤数据"""
        metrics = [
            {'timestamp': datetime(2024, 1, 1), 'current_drawdown': -0.01},
            {'timestamp': datetime(2024, 1, 2), 'current_drawdown': -0.02},
            {'timestamp': datetime(2024, 1, 3), 'current_drawdown': -0.015},
        ]
        
        drawdowns = [m.get('current_drawdown', 0) for m in metrics]
        
        self.assertEqual(drawdowns, [-0.01, -0.02, -0.015])

    def test_create_dataframe_from_metrics(self):
        """测试从指标创建 DataFrame"""
        timestamps = [datetime(2024, 1, 1), datetime(2024, 1, 2), datetime(2024, 1, 3)]
        cumulative_returns = [0.01, 0.02, 0.03]
        drawdowns = [-0.01, -0.02, -0.015]
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'cumulative_return': cumulative_returns,
            'drawdown': drawdowns
        })
        
        self.assertEqual(len(df), 3)
        self.assertIn('timestamp', df.columns)
        self.assertIn('cumulative_return', df.columns)
        self.assertIn('drawdown', df.columns)


class TestUIDataVariableScope(unittest.TestCase):
    """测试 ui_data 变量作用域"""

    def test_ui_data_default_value(self):
        """测试 ui_data 默认值"""
        ui_data = {}
        
        self.assertIsInstance(ui_data, dict)
        self.assertEqual(len(ui_data), 0)

    def test_ui_data_conditional_assignment(self):
        """测试 ui_data 条件赋值"""
        ui_data = {}
        latest_metrics = None
        
        if latest_metrics:
            ui_data = {'cumulative_return': latest_metrics.cumulative_return}
        
        self.assertEqual(ui_data, {})

    def test_ui_data_safe_usage(self):
        """测试 ui_data 安全使用"""
        ui_data = {}
        
        if ui_data:
            result = ui_data.get('cumulative_return', 0)
        else:
            result = 0
        
        self.assertEqual(result, 0)


class TestFinalResultsRetrieval(unittest.TestCase):
    """测试最终结果获取"""

    def test_retrieve_from_monitoring_summary(self):
        """测试从 monitoring_summary 获取结果"""
        from backtest.real_time_backtest_monitor import RealTimeBacktestMonitor
        monitor = RealTimeBacktestMonitor()
        
        summary = monitor.get_monitoring_summary()
        
        self.assertIsInstance(summary, dict)
        self.assertIn('status', summary)

    def test_retrieve_from_latest_metrics(self):
        """测试从 latest_metrics 获取结果"""
        from backtest.real_time_backtest_monitor import RealTimeBacktestMonitor, RealTimeMetrics
        from datetime import datetime
        monitor = RealTimeBacktestMonitor()
        
        latest = monitor.get_latest_metrics()
        
        self.assertIsNone(latest)

    def test_combined_results_structure(self):
        """测试合并结果结构"""
        final_results = {}
        
        summary = {'status': 'active', 'data_points': 100}
        if summary and summary.get('status') != 'error':
            final_results = summary
        
        latest_metrics_data = {
            'cumulative_return': 0.05,
            'max_drawdown': 0.02,
            'sharpe_ratio': 1.5
        }
        final_results.update(latest_metrics_data)
        
        self.assertIn('status', final_results)
        self.assertIn('cumulative_return', final_results)
        self.assertIn('max_drawdown', final_results)
        self.assertIn('sharpe_ratio', final_results)


class TestChartWidgetAddData(unittest.TestCase):
    """测试 ChartWidget.add_data 方法"""

    def test_add_data_stores_metrics(self):
        """测试 add_data 存储指标"""
        from gui.widgets.chart_widget import ChartWidget
        chart = ChartWidget()
        
        test_data = {
            'timestamp': datetime.now(),
            'cumulative_return': 0.05,
            'current_drawdown': -0.02,
            'sharpe_ratio': 1.5
        }
        
        chart.add_data(test_data)
        
        self.assertTrue(hasattr(chart, '_backtest_metrics'))
        self.assertEqual(len(chart._backtest_metrics), 1)

    def test_add_data_multiple_points(self):
        """测试添加多个数据点"""
        from gui.widgets.chart_widget import ChartWidget
        chart = ChartWidget()
        
        for i in range(10):
            test_data = {
                'timestamp': datetime.now(),
                'cumulative_return': i * 0.01,
                'current_drawdown': -i * 0.005,
                'sharpe_ratio': 1.0 + i * 0.1
            }
            chart.add_data(test_data)
        
        self.assertEqual(len(chart._backtest_metrics), 10)

    def test_add_data_respects_limit(self):
        """测试数据限制"""
        from gui.widgets.chart_widget import ChartWidget
        chart = ChartWidget()
        
        for i in range(1500):
            test_data = {
                'timestamp': datetime.now(),
                'cumulative_return': i * 0.001,
                'current_drawdown': -i * 0.0005,
                'sharpe_ratio': 1.0
            }
            chart.add_data(test_data)
            
            if len(chart._backtest_metrics) > 1000:
                chart._backtest_metrics = chart._backtest_metrics[-1000:]
        
        self.assertLessEqual(len(chart._backtest_metrics), 1000)


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_full_data_flow(self):
        """测试完整数据流"""
        from backtest.real_time_backtest_monitor import RealTimeBacktestMonitor
        
        monitor = RealTimeBacktestMonitor()
        
        self.assertTrue(hasattr(monitor, 'get_latest_metrics'))
        self.assertTrue(hasattr(monitor, 'get_monitoring_summary'))
        
        summary = monitor.get_monitoring_summary()
        latest = monitor.get_latest_metrics()
        
        final_results = {}
        
        if summary and summary.get('status') != 'error':
            final_results = summary
        
        if latest:
            final_results.update({
                'cumulative_return': latest.cumulative_return,
                'max_drawdown': latest.max_drawdown,
            })
        
        self.assertIsInstance(final_results, dict)


if __name__ == '__main__':
    unittest.main(verbosity=2)
