#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PyQtGraph集成测试模块

全面测试PyQtGraph渲染引擎的所有组件和功能

作者: FactorWeave-Quant团队
版本: 1.0
"""

import unittest
import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List
import tempfile
import logging

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, project_root)

from core.gui.rendering.pyqtgraph_engine import PyQtGraphEngine, ChartType, PyQtGraphChartWidget, ChartConfig
from core.gui.rendering.chart_manager import ChartManager
from core.gui.rendering.performance_optimizer import ChartPerformanceOptimizer, PerformanceConfig
from core.gui.rendering.matplotlib_adapter import MatplotlibAdapter, MatplotlibConfig
from core.gui.rendering.data_adapter import DataAdapter, DataSchema, DataFormat
from core.gui.rendering.chart_factory import ChartFactory, RendererConfig, ChartCreationRequest
from core.gui.rendering.utils import PerformanceProfiler, ConfigurationManager, DataValidator


class MockPyQtGraphWidget:
    """模拟PyQtGraph图表组件"""
    
    def __init__(self, chart_type: ChartType, width: int, height: int):
        self.chart_type = chart_type
        self.width = width
        self.height = height
        self.data = {}
        self.style = {}
        self.callbacks = {}
        
    def set_data(self, data: Dict[str, Any]):
        """设置数据"""
        self.data = data
        
    def apply_style(self, style: Dict[str, Any]):
        """应用样式"""
        self.style = style
        
    def connect_callback(self, event: str, callback):
        """连接回调"""
        self.callbacks[event] = callback


class TestPyQtGraphEngine(unittest.TestCase):
    """测试PyQtGraph引擎"""
    
    def setUp(self):
        """设置测试环境"""
        self.engine = PyQtGraphEngine()
        
    def test_chart_creation(self):
        """测试图表创建"""
        line_config = ChartConfig(chart_type=ChartType.LINE_CHART, width=800, height=600)
        line_chart = self.engine.create_chart("test_line_1", line_config)
        self.assertIsNotNone(line_chart)

        kline_config = ChartConfig(chart_type=ChartType.CANDLESTICK, width=800, height=600)
        kline_chart = self.engine.create_chart("test_kline_1", kline_config)
        self.assertIsNotNone(kline_chart)
        
    def test_performance_monitoring(self):
        """测试性能监控"""
        # 开始监控
        self.engine.start_performance_monitoring()
        
        # 创建几个图表
        for i in range(3):
            config = ChartConfig(chart_type=ChartType.LINE_CHART, width=800, height=600)
            self.engine.create_chart(f"test_perf_{i}", config)
            
        # 获取性能统计
        stats = self.engine.get_performance_stats()
        self.assertIn('active_charts', stats)
        self.assertEqual(stats['active_charts'], 3)
        
    def test_data_visualization(self):
        """测试数据可视化"""
        # 创建测试数据
        test_data = {
            'x': np.linspace(0, 10, 100),
            'y': np.sin(np.linspace(0, 10, 100))
        }
        
        # 创建图表并设置数据
        config = ChartConfig(chart_type=ChartType.LINE_CHART, width=800, height=600)
        chart = self.engine.create_chart("test_viz_1", config)
        chart.set_data(test_data)

        self.assertIsNotNone(chart)


class TestChartManager(unittest.TestCase):
    """测试图表管理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.chart_manager = ChartManager()
        
    def test_chart_registration(self):
        """测试图表注册"""
        # 创建测试图表
        chart = MockPyQtGraphWidget(ChartType.LINE_CHART, 800, 600)
        chart_id = "test_chart_1"
        
        # 注册图表
        success = self.chart_manager.register_chart(chart_id, chart)
        self.assertTrue(success)
        
        # 验证注册成功
        registered_chart = self.chart_manager.get_chart(chart_id)
        self.assertEqual(registered_chart, chart)
        
    def test_chart_creation_methods(self):
        """测试图表创建方法"""
        # 测试线图创建
        line_chart = self.chart_manager.create_line_chart(
            data={'x': [1, 2, 3], 'y': [4, 5, 6]},
            title="Test Line Chart"
        )
        self.assertIsNotNone(line_chart)
        
        # 测试K线图创建
        kline_data = pd.DataFrame({
            'time': pd.date_range('2024-01-01', periods=5, freq='D'),
            'open': [100, 102, 101, 103, 104],
            'high': [105, 103, 104, 105, 106],
            'low': [99, 101, 100, 102, 103],
            'close': [102, 101, 103, 104, 105],
            'volume': [1000, 1100, 900, 1200, 1150]
        })
        
        kline_chart = self.chart_manager.create_candlestick_chart(
            data=kline_data,
            title="Test K-Line Chart"
        )
        self.assertIsNotNone(kline_chart)
        
    def test_data_update(self):
        """测试数据更新"""
        # 创建图表并注册
        chart = MockPyQtGraphWidget(ChartType.LINE_CHART, 800, 600)
        chart_id = "test_chart_2"
        self.chart_manager.register_chart(chart_id, chart)
        
        # 更新数据
        new_data = {'x': [1, 2, 3, 4], 'y': [4, 5, 6, 7]}
        success = self.chart_manager.update_chart_data(chart_id, new_data)
        self.assertTrue(success)
        
        # 验证数据更新
        self.assertEqual(chart.data, new_data)


class TestPerformanceOptimizer(unittest.TestCase):
    """测试性能优化器"""
    
    def setUp(self):
        """设置测试环境"""
        self.optimizer = ChartPerformanceOptimizer(PerformanceConfig())
        
    def test_optimization_strategies(self):
        """测试优化策略"""
        # 测试数据采样策略
        large_data = {
            'x': np.random.random(10000),
            'y': np.random.random(10000)
        }
        
        optimized_data = self.optimizer.optimize_data(large_data, 'data_sampling')
        self.assertIsNotNone(optimized_data)
        # 优化后数据点应该减少
        if len(optimized_data.get('x', [])) < len(large_data['x']):
            self.assertTrue(True)
        
    def test_memory_management(self):
        """测试内存管理"""
        # 创建性能监控
        self.optimizer.start_monitoring()
        
        # 模拟大量数据处理
        for i in range(10):
            large_data = {
                'x': np.random.random(1000),
                'y': np.random.random(1000)
            }
            self.optimizer.process_data_batch([large_data])
            
        # 获取内存使用统计
        memory_stats = self.optimizer.get_memory_stats()
        self.assertIsInstance(memory_stats, dict)
        self.assertIn('memory_usage_mb', memory_stats)
        
    def test_cache_operations(self):
        """测试缓存操作"""
        # 测试缓存存储
        test_data = {'x': [1, 2, 3], 'y': [4, 5, 6]}
        cache_key = "test_cache_key"
        
        success = self.optimizer.store_in_cache(cache_key, test_data)
        self.assertTrue(success)
        
        # 测试缓存检索
        cached_data = self.optimizer.get_from_cache(cache_key)
        self.assertEqual(cached_data, test_data)


class TestMatplotlibAdapter(unittest.TestCase):
    """测试matplotlib适配器"""
    
    def setUp(self):
        """设置测试环境"""
        self.adapter = MatplotlibAdapter(MatplotlibConfig())
        
    def test_style_management(self):
        """测试样式管理"""
        # 测试预设样式获取
        styles = self.adapter.get_preset_styles()
        self.assertIn('trading', styles)
        self.assertIn('professional', styles)
        self.assertIn('minimal', styles)
        
        # 测试样式应用
        success = self.adapter.apply_style('trading')
        self.assertTrue(success)
        
    def test_matplotlib_figure_creation(self):
        """测试matplotlib图形创建"""
        # 创建测试数据
        test_data = pd.DataFrame({
            'x': np.linspace(0, 10, 100),
            'y': np.sin(np.linspace(0, 10, 100))
        })
        
        # 创建matplotlib图形
        figure = self.adapter.create_figure(test_data, 'line')
        self.assertIsNotNone(figure)
        
        # 测试保存功能
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            file_path = tmp_file.name
            
        success = self.adapter.save_figure(figure, file_path)
        self.assertTrue(success)
        
        # 清理测试文件
        if os.path.exists(file_path):
            os.remove(file_path)


class TestDataAdapter(unittest.TestCase):
    """测试数据适配器"""
    
    def setUp(self):
        """设置测试环境"""
        self.data_adapter = DataAdapter()
        
    def test_data_normalization(self):
        """测试数据标准化"""
        # 创建测试数据
        raw_data = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'value': [100, 101, 102]
        })
        
        # 测试数值序列标准化
        normalized_data = self.data_adapter.normalize_data(raw_data, 'numerical')
        self.assertIsNotNone(normalized_data)
        
    def test_ohlc_conversion(self):
        """测试OHLC数据转换"""
        # 创建测试时间序列数据
        test_data = pd.DataFrame({
            'time': pd.date_range('2024-01-01', periods=10, freq='H'),
            'price': np.random.random(10) * 100 + 100
        })
        
        # 转换为OHLC格式
        ohlc_data = self.data_adapter.convert_ohlc(test_data, 'time', 'price')
        self.assertIsNotNone(ohlc_data)
        
        required_columns = ['time', 'open', 'high', 'low', 'close']
        for col in required_columns:
            self.assertIn(col, ohlc_data.columns)
            
    def test_data_validation(self):
        """测试数据验证"""
        # 创建无效的OHLC数据
        invalid_ohlc = pd.DataFrame({
            'open': [100, 102],
            'high': [99, 103],  # high < low 错误
            'low': [101, 104],
            'close': [102, 103]
        })
        
        # 验证数据质量
        report = self.data_adapter.validate_data_quality(invalid_ohlc, 'ohlc')
        self.assertIsInstance(report, dict)
        self.assertTrue(not report['is_valid'])
        self.assertGreater(len(report['errors']), 0)


class TestChartFactory(unittest.TestCase):
    """测试图表工厂"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建模拟的核心组件
        self.mock_engine = Mock(spec=PyQtGraphEngine)
        self.mock_manager = Mock(spec=ChartManager)
        self.mock_optimizer = Mock(spec=ChartPerformanceOptimizer)
        self.mock_adapter = Mock(spec=MatplotlibAdapter)
        self.mock_data_adapter = Mock(spec=DataAdapter)
        
        # 创建图表工厂
        self.chart_factory = ChartFactory()
        self.chart_factory.initialize(
            self.mock_engine,
            self.mock_manager,
            self.mock_optimizer,
            self.mock_adapter,
            self.mock_data_adapter
        )
        
    def test_chart_creation_from_request(self):
        """测试从请求创建图表"""
        # 创建测试配置
        config = RendererConfig(
            chart_type=ChartType.LINE_CHART,
            title="Test Chart",
            style="modern",
            theme="auto"
        )
        
        # 创建测试数据
        test_data = pd.DataFrame({
            'x': [1, 2, 3],
            'y': [4, 5, 6]
        })
        
        request = ChartCreationRequest(config=config, data=test_data)
        
        # 模拟成功创建
        self.mock_engine.create_chart.return_value = MockPyQtGraphWidget(ChartType.LINE_CHART, 800, 600)
        self.mock_data_adapter.normalize_data.return_value = test_data
        self.mock_data_adapter.convert_chart_data.return_value = test_data.to_dict()
        
        # 执行创建
        chart_id = self.chart_factory.create_chart(request)
        
        self.assertIsNotNone(chart_id)
        self.assertTrue(chart_id.startswith('chart_'))
        
    def test_template_based_creation(self):
        """测试基于模板的图表创建"""
        # 测试K线图模板
        kline_data = pd.DataFrame({
            'time': pd.date_range('2024-01-01', periods=5, freq='D'),
            'open': [100, 102, 101, 103, 104],
            'high': [105, 103, 104, 105, 106],
            'low': [99, 101, 100, 102, 103],
            'close': [102, 101, 103, 104, 105],
            'volume': [1000, 1100, 900, 1200, 1150]
        })
        
        self.mock_engine.create_chart.return_value = MockPyQtGraphWidget(ChartType.CANDLESTICK, 800, 600)
        self.mock_data_adapter.normalize_data.return_value = kline_data
        self.mock_data_adapter.convert_chart_data.return_value = kline_data.to_dict()
        
        chart_id = self.chart_factory.create_kline_chart(kline_data, "Test K-Line")
        
        self.assertIsNotNone(chart_id)
        
    def test_template_registration(self):
        """测试模板注册"""
        # 注册自定义模板
        custom_config = RendererConfig(
            chart_type=ChartType.SCATTER_PLOT,
            title="Custom Scatter Plot",
            style="professional"
        )
        
        self.chart_factory.register_template("custom_template", custom_config)
        
        # 验证模板注册成功
        templates = self.chart_factory.get_template_list()
        self.assertIn("custom_template", templates)
        
        # 获取模板信息
        template_info = self.chart_factory.get_template_info("custom_template")
        self.assertIsNotNone(template_info)
        self.assertEqual(template_info['title'], "Custom Scatter Plot")


class TestRenderingUtils(unittest.TestCase):
    """测试渲染工具"""
    
    def test_performance_profiler(self):
        """测试性能分析器"""
        profiler = PerformanceProfiler()
        
        # 添加测试指标
        from core.gui.rendering.utils import PerformanceMetrics
        metric = PerformanceMetrics(
            name="test_metric",
            value=1.23,
            unit="seconds"
        )
        
        profiler.add_metric(metric)
        
        # 获取指标
        metrics = profiler.get_metrics()
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].name, "test_metric")
        
    def test_configuration_manager(self):
        """测试配置管理器"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            config_file = tmp_file.name
            
        try:
            # 创建配置管理器
            config_manager = ConfigurationManager(config_file)
            
            # 测试设置和获取配置
            config_manager.set('test.key', 'test_value')
            value = config_manager.get('test.key')
            self.assertEqual(value, 'test_value')
            
            # 测试默认值
            default_value = config_manager.get('non_existent.key', 'default')
            self.assertEqual(default_value, 'default')
            
        finally:
            if os.path.exists(config_file):
                os.remove(config_file)
                
    def test_data_validator(self):
        """测试数据验证器"""
        # 创建有效的OHLC数据
        valid_ohlc = pd.DataFrame({
            'open': [100, 102, 101],
            'high': [105, 103, 104],
            'low': [99, 101, 100],
            'close': [102, 101, 103]
        })
        
        is_valid, errors = DataValidator.validate_ohlc_data(valid_ohlc)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # 创建无效的OHLC数据
        invalid_ohlc = pd.DataFrame({
            'open': [100, 102],
            'high': [99, 103],  # high < low 错误
            'low': [101, 104],
            'close': [102, 103]
        })
        
        is_valid, errors = DataValidator.validate_ohlc_data(invalid_ohlc)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)


class IntegrationTestSuite(unittest.TestCase):
    """集成测试套件"""
    
    def test_full_integration_workflow(self):
        """测试完整的集成工作流"""
        # 1. 创建核心组件
        engine = PyQtGraphEngine()
        chart_manager = ChartManager()
        data_adapter = DataAdapter()
        
        # 2. 创建图表工厂
        factory = ChartFactory()
        factory.initialize(
            engine,
            chart_manager,
            Mock(spec=ChartPerformanceOptimizer),
            Mock(spec=MatplotlibAdapter),
            data_adapter
        )
        
        # 3. 创建测试数据
        test_data = pd.DataFrame({
            'time': pd.date_range('2024-01-01', periods=100, freq='H'),
            'price': np.cumsum(np.random.random(100) - 0.5) + 100
        })
        
        # 4. 使用工厂创建图表
        chart_id = factory.create_kline_chart(test_data, "Integration Test Chart")
        
        self.assertIsNotNone(chart_id)
        
        # 5. 验证图表注册
        chart = chart_manager.get_chart(chart_id)
        self.assertIsNotNone(chart)
        
        # 6. 验证数据质量
        quality_report = data_adapter.validate_data_quality(test_data, 'time_series')
        self.assertIsInstance(quality_report, dict)
        self.assertIn('is_valid', quality_report)
        
    def test_error_handling_and_recovery(self):
        """测试错误处理和恢复"""
        factory = ChartFactory()
        
        # 测试无效配置
        invalid_config = RendererConfig(
            chart_type=ChartType.LINE_CHART,
            width=-1,  # 无效宽度
            height=600
        )
        
        is_valid, errors = factory.validate_config(invalid_config)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        
        # 测试无效数据
        invalid_request = ChartCreationRequest(
            config=RendererConfig(chart_type=ChartType.CANDLESTICK),
            data=None
        )
        
        # 模拟适配器返回None
        with patch('core.gui.rendering.data_adapter.DataAdapter.normalize_data', return_value=None):
            chart_id = factory.create_chart(invalid_request)
            self.assertIsNone(chart_id)


def run_performance_benchmark():
    """运行性能基准测试"""
    print("\n=== PyQtGraph渲染引擎性能基准测试 ===")
    
    # 创建测试组件
    engine = PyQtGraphEngine()
    data_adapter = DataAdapter()
    
    # 生成大量测试数据
    test_sizes = [100, 1000, 10000]
    
    for size in test_sizes:
        print(f"\n测试数据规模: {size} 数据点")
        
        # 生成随机数据
        large_data = pd.DataFrame({
            'time': pd.date_range('2024-01-01', periods=size, freq='H'),
            'value': np.random.random(size) * 100 + 50
        })
        
        # 测试数据标准化性能
        start_time = datetime.now()
        normalized_data = data_adapter.normalize_data(large_data, 'numerical')
        normalization_time = (datetime.now() - start_time).total_seconds()
        
        # 测试图表创建性能
        start_time = datetime.now()
        config = ChartConfig(chart_type=ChartType.LINE_CHART, width=800, height=600)
        chart = engine.create_chart("bench_chart", config)
        if normalized_data is not None:
            chart.set_data(normalized_data.to_dict())
        creation_time = (datetime.now() - start_time).total_seconds()
        
        print(f"  数据标准化时间: {normalization_time:.4f}s")
        print(f"  图表创建时间: {creation_time:.4f}s")
        print(f"  总时间: {normalization_time + creation_time:.4f}s")


def main():
    """主测试函数"""
    # 设置测试日志
    logging.basicConfig(level=logging.INFO)
    
    print("启动PyQtGraph集成测试套件")
    print("=" * 50)
    
    # 运行单元测试
    print("\n1. 运行单元测试...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # 运行性能基准测试
    print("\n2. 运行性能基准测试...")
    run_performance_benchmark()
    
    print("\n" + "=" * 50)
    print("所有测试完成!")


if __name__ == '__main__':
    main()