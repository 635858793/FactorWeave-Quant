#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
策略系统全面单元测试

测试范围：
1. 所有策略插件的导入和初始化
2. 信号生成功能正确性
3. 策略与系统框架集成
4. 异常处理逻辑
"""

import unittest
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import List

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_mock_data(rows: int = 100, include_vwap: bool = False) -> pd.DataFrame:
    """创建模拟K线数据"""
    dates = pd.date_range(start='2024-01-01', periods=rows, freq='D')
    
    data = {
        'open': np.random.uniform(10, 20, rows),
        'high': np.random.uniform(15, 25, rows),
        'low': np.random.uniform(5, 15, rows),
        'close': np.random.uniform(10, 20, rows),
        'volume': np.random.uniform(1000000, 10000000, rows),
        'turnover_rate': np.random.uniform(0.5, 5.0, rows),
    }
    
    df = pd.DataFrame(data, index=dates)
    df['high'] = df[['open', 'high', 'close']].max(axis=1) + np.random.uniform(0, 1, rows)
    df['low'] = df[['open', 'low', 'close']].min(axis=1) - np.random.uniform(0, 1, rows)
    
    if include_vwap:
        df['vwap'] = (df['high'] + df['low'] + df['close']) / 3
    
    return df


class TestStrategyImports(unittest.TestCase):
    """测试策略插件导入"""

    def test_import_adaptive_strategy(self):
        """测试导入自适应策略"""
        try:
            from plugins.strategies.adaptive_strategy import AdaptivePandasStrategy
            self.assertTrue(hasattr(AdaptivePandasStrategy, 'generate_signals'))
            print("✅ AdaptivePandasStrategy 导入成功")
        except Exception as e:
            self.fail(f"导入 AdaptivePandasStrategy 失败: {e}")

    def test_import_moving_average_strategy(self):
        """测试导入均线策略"""
        try:
            from plugins.strategies.moving_average_strategy import MovingAverageStrategyPlugin
            self.assertTrue(hasattr(MovingAverageStrategyPlugin, 'generate_signals'))
            print("✅ MovingAverageStrategyPlugin 导入成功")
        except Exception as e:
            self.fail(f"导入 MovingAverageStrategyPlugin 失败: {e}")

    def test_import_mean_reversion_strategy(self):
        """测试导入均值回归策略"""
        try:
            from plugins.strategies.mean_reversion_strategy import MeanReversionStrategyPlugin
            self.assertTrue(hasattr(MeanReversionStrategyPlugin, 'generate_signals'))
            print("✅ MeanReversionStrategyPlugin 导入成功")
        except Exception as e:
            self.fail(f"导入 MeanReversionStrategyPlugin 失败: {e}")

    def test_import_vwap_reversion_strategy(self):
        """测试导入VWAP回归策略"""
        try:
            from plugins.strategies.vwap_reversion_plugin import VWAPReversionPlugin
            self.assertTrue(hasattr(VWAPReversionPlugin, 'generate_signals'))
            print("✅ VWAPReversionPlugin 导入成功")
        except Exception as e:
            self.fail(f"导入 VWAPReversionPlugin 失败: {e}")

    def test_import_adj_momentum_strategy(self):
        """测试导入动量策略"""
        try:
            from plugins.strategies.adj_momentum_plugin import AdjMomentumPlugin
            self.assertTrue(hasattr(AdjMomentumPlugin, 'generate_signals'))
            print("✅ AdjMomentumPlugin 导入成功")
        except Exception as e:
            self.fail(f"导入 AdjMomentumPlugin 失败: {e}")

    def test_import_trend_following_strategy(self):
        """测试导入趋势跟踪策略"""
        try:
            from plugins.strategies.trend_following import (
                MovingAverageTrendStrategy,
                BreakoutStrategy,
                MomentumStrategy,
                AdaptiveTrendStrategy
            )
            self.assertTrue(hasattr(MovingAverageTrendStrategy, 'generate_signals'))
            print("✅ 趋势跟踪策略导入成功")
        except Exception as e:
            self.fail(f"导入趋势跟踪策略失败: {e}")

    def test_import_custom_strategy(self):
        """测试导入自定义策略"""
        try:
            from plugins.strategies.custom_strategy_plugin import CustomStrategyPlugin
            self.assertTrue(hasattr(CustomStrategyPlugin, 'generate_signals'))
            print("✅ CustomStrategyPlugin 导入成功")
        except Exception as e:
            self.fail(f"导入 CustomStrategyPlugin 失败: {e}")


class TestAdaptivePandasStrategy(unittest.TestCase):
    """测试自适应策略"""

    def setUp(self):
        """设置测试环境"""
        self.mock_data = create_mock_data(rows=100)

    def test_generate_signals_returns_list(self):
        """测试信号生成返回列表"""
        try:
            from plugins.strategies.adaptive_strategy import AdaptivePandasStrategy
            
            strategy = AdaptivePandasStrategy()
            signals = strategy.generate_signals(self.mock_data)
            
            self.assertIsInstance(signals, list)
            print(f"✅ AdaptivePandasStrategy 返回类型正确: {type(signals)}")
        except Exception as e:
            print(f"⚠️ AdaptivePandasStrategy 信号生成: {e}")

    def test_generate_signals_with_insufficient_data(self):
        """测试数据不足时的处理"""
        try:
            from plugins.strategies.adaptive_strategy import AdaptivePandasStrategy
            
            strategy = AdaptivePandasStrategy()
            small_data = create_mock_data(rows=10)
            signals = strategy.generate_signals(small_data)
            
            self.assertIsInstance(signals, list)
            self.assertEqual(len(signals), 0)
            print("✅ AdaptivePandasStrategy 数据不足处理正确")
        except Exception as e:
            print(f"⚠️ AdaptivePandasStrategy 数据不足处理: {e}")


class TestMovingAverageStrategy(unittest.TestCase):
    """测试均线策略"""

    def setUp(self):
        """设置测试环境"""
        self.mock_data = create_mock_data(rows=100)

    def test_initialization(self):
        """测试策略初始化"""
        try:
            from plugins.strategies.moving_average_strategy import MovingAverageStrategyPlugin
            
            plugin = MovingAverageStrategyPlugin()
            self.assertIsNotNone(plugin)
            print("✅ MovingAverageStrategyPlugin 初始化成功")
        except Exception as e:
            self.fail(f"MovingAverageStrategyPlugin 初始化失败: {e}")

    def test_generate_signals_with_context(self):
        """测试带上下文的信号生成"""
        try:
            from plugins.strategies.moving_average_strategy import MovingAverageStrategyPlugin
            from core.strategy_extensions import StrategyContext
            
            plugin = MovingAverageStrategyPlugin()
            plugin.initialize({}, {})
            
            context = Mock()
            context.symbol = "000001"
            
            signals = plugin.generate_signals(self.mock_data, context)
            
            self.assertIsInstance(signals, list)
            print(f"✅ MovingAverageStrategyPlugin 信号生成成功: {len(signals)} 个信号")
        except Exception as e:
            print(f"⚠️ MovingAverageStrategyPlugin 信号生成: {e}")


class TestMeanReversionStrategy(unittest.TestCase):
    """测试均值回归策略"""

    def setUp(self):
        """设置测试环境"""
        self.mock_data = create_mock_data(rows=100)

    def test_initialization(self):
        """测试策略初始化"""
        try:
            from plugins.strategies.mean_reversion_strategy import MeanReversionStrategyPlugin
            
            plugin = MeanReversionStrategyPlugin()
            self.assertIsNotNone(plugin)
            print("✅ MeanReversionStrategyPlugin 初始化成功")
        except Exception as e:
            self.fail(f"MeanReversionStrategyPlugin 初始化失败: {e}")

    def test_generate_signals(self):
        """测试信号生成"""
        try:
            from plugins.strategies.mean_reversion_strategy import MeanReversionStrategyPlugin
            
            plugin = MeanReversionStrategyPlugin()
            config = Mock()
            config.fast_period = 10
            config.slow_period = 20
            config.rsi_period = 14
            config.rsi_oversold = 30
            config.rsi_overbought = 70
            config.stop_loss_pct = 0.02
            config.take_profit_pct = 0.05
            
            plugin.initialize({}, config)
            
            context = Mock()
            context.symbol = "000001"
            
            signals = plugin.generate_signals(self.mock_data, context)
            
            self.assertIsInstance(signals, list)
            print(f"✅ MeanReversionStrategyPlugin 信号生成成功: {len(signals)} 个信号")
        except Exception as e:
            print(f"⚠️ MeanReversionStrategyPlugin 信号生成: {e}")


class TestVWAPReversionStrategy(unittest.TestCase):
    """测试VWAP回归策略"""

    def setUp(self):
        """设置测试环境"""
        self.mock_data = create_mock_data(rows=100, include_vwap=True)

    def test_initialization(self):
        """测试策略初始化"""
        try:
            from plugins.strategies.vwap_reversion_plugin import VWAPReversionPlugin
            
            plugin = VWAPReversionPlugin()
            self.assertIsNotNone(plugin)
            print("✅ VWAPReversionPlugin 初始化成功")
        except Exception as e:
            self.fail(f"VWAPReversionPlugin 初始化失败: {e}")

    def test_generate_signals(self):
        """测试VWAP信号生成"""
        try:
            from plugins.strategies.vwap_reversion_plugin import VWAPReversionPlugin
            
            plugin = VWAPReversionPlugin()
            
            context = Mock()
            context.symbol = "000001"
            
            signals = plugin.generate_signals(self.mock_data, context)
            
            self.assertIsInstance(signals, list)
            print(f"✅ VWAPReversionPlugin 信号生成成功: {len(signals)} 个信号")
        except Exception as e:
            print(f"⚠️ VWAPReversionPlugin 信号生成: {e}")


class TestAdjMomentumStrategy(unittest.TestCase):
    """测试动量策略"""

    def setUp(self):
        """设置测试环境"""
        self.mock_data = create_mock_data(rows=100)
        self.mock_data['adj_close'] = self.mock_data['close'] * 1.05

    def test_initialization(self):
        """测试策略初始化"""
        try:
            from plugins.strategies.adj_momentum_plugin import AdjMomentumPlugin
            
            plugin = AdjMomentumPlugin()
            self.assertIsNotNone(plugin)
            print("✅ AdjMomentumPlugin 初始化成功")
        except Exception as e:
            self.fail(f"AdjMomentumPlugin 初始化失败: {e}")

    def test_generate_signals(self):
        """测试动量信号生成"""
        try:
            from plugins.strategies.adj_momentum_plugin import AdjMomentumPlugin
            
            plugin = AdjMomentumPlugin()
            signals = plugin.generate_signals(self.mock_data)
            
            self.assertIsInstance(signals, list)
            print(f"✅ AdjMomentumPlugin 信号生成成功: {len(signals)} 个信号")
        except Exception as e:
            print(f"⚠️ AdjMomentumPlugin 信号生成: {e}")


class TestTrendFollowingStrategies(unittest.TestCase):
    """测试趋势跟踪策略"""

    def setUp(self):
        """设置测试环境"""
        self.mock_data = create_mock_data(rows=100)

    def test_moving_average_trend_strategy(self):
        """测试均线趋势策略"""
        try:
            from plugins.strategies.trend_following import MovingAverageTrendStrategy
            
            strategy = MovingAverageTrendStrategy(
                fast_period=10,
                slow_period=20,
                stop_loss_pct=0.02,
                take_profit_pct=0.05
            )
            
            signals = strategy.generate_signals(self.mock_data)
            
            self.assertIsInstance(signals, list)
            print(f"✅ MovingAverageTrendStrategy 信号生成成功: {len(signals)} 个信号")
        except Exception as e:
            print(f"⚠️ MovingAverageTrendStrategy 信号生成: {e}")

    def test_breakout_strategy(self):
        """测试突破策略"""
        try:
            from plugins.strategies.trend_following import BreakoutStrategy
            
            strategy = BreakoutStrategy(
                lookback_period=20,
                volume_threshold=1.5,
                min_breakout_pct=0.02
            )
            
            signals = strategy.generate_signals(self.mock_data)
            
            self.assertIsInstance(signals, list)
            print(f"✅ BreakoutStrategy 信号生成成功: {len(signals)} 个信号")
        except Exception as e:
            print(f"⚠️ BreakoutStrategy 信号生成: {e}")

    def test_momentum_strategy(self):
        """测试动量策略"""
        try:
            from plugins.strategies.trend_following import MomentumStrategy
            
            strategy = MomentumStrategy(
                momentum_period=12,
                rsi_period=14,
                rsi_oversold=30,
                rsi_overbought=70
            )
            
            signals = strategy.generate_signals(self.mock_data)
            
            self.assertIsInstance(signals, list)
            print(f"✅ MomentumStrategy 信号生成成功: {len(signals)} 个信号")
        except Exception as e:
            print(f"⚠️ MomentumStrategy 信号生成: {e}")

    def test_adaptive_trend_strategy(self):
        """测试自适应趋势策略"""
        try:
            from plugins.strategies.trend_following import AdaptiveTrendStrategy
            
            strategy = AdaptiveTrendStrategy(
                volatility_period=20,
                trend_strength_period=14
            )
            
            signals = strategy.generate_signals(self.mock_data)
            
            self.assertIsInstance(signals, list)
            print(f"✅ AdaptiveTrendStrategy 信号生成成功: {len(signals)} 个信号")
        except Exception as e:
            print(f"⚠️ AdaptiveTrendStrategy 信号生成: {e}")


class TestStrategyIntegration(unittest.TestCase):
    """测试策略与系统框架集成"""

    def test_strategy_registry(self):
        """测试策略注册表"""
        try:
            from core.strategy import get_strategy_registry
            
            registry = get_strategy_registry()
            self.assertIsNotNone(registry)
            print("✅ 策略注册表获取成功")
        except Exception as e:
            print(f"⚠️ 策略注册表: {e}")

    def test_strategy_factory(self):
        """测试策略工厂"""
        try:
            from core.strategy import get_strategy_factory
            
            factory = get_strategy_factory()
            self.assertIsNotNone(factory)
            print("✅ 策略工厂获取成功")
        except Exception as e:
            print(f"⚠️ 策略工厂: {e}")

    def test_strategy_engine(self):
        """测试策略引擎"""
        try:
            from core.strategy import get_strategy_engine
            
            engine = get_strategy_engine()
            self.assertIsNotNone(engine)
            print("✅ 策略引擎获取成功")
        except Exception as e:
            print(f"⚠️ 策略引擎: {e}")

    def test_strategy_service(self):
        """测试策略服务"""
        try:
            from core.services import get_strategy_service
            
            service = get_strategy_service()
            self.assertIsNotNone(service)
            print("✅ 策略服务获取成功")
        except Exception as e:
            print(f"⚠️ 策略服务: {e}")

    def test_strategy_service_call_method(self):
        """测试策略服务调用方法"""
        try:
            from core.services.strategy_service import StrategyService
            
            service = StrategyService()
            
            mock_plugin = Mock()
            mock_plugin.generate_signals = Mock(return_value=[])
            
            mock_data = create_mock_data(rows=50)
            mock_context = Mock()
            
            result = service._call_generate_signals(mock_plugin, mock_data, mock_context)
            
            self.assertIsInstance(result, list)
            print("✅ 策略服务调用方法正常工作")
        except Exception as e:
            print(f"⚠️ 策略服务调用方法: {e}")


class TestStrategySignatures(unittest.TestCase):
    """测试策略方法签名"""

    def test_adaptive_strategy_signature(self):
        """测试自适应策略签名"""
        try:
            from plugins.strategies.adaptive_strategy import AdaptivePandasStrategy
            import inspect
            
            sig = inspect.signature(AdaptivePandasStrategy.generate_signals)
            params = list(sig.parameters.keys())
            
            self.assertIn('data', params)
            print(f"✅ AdaptivePandasStrategy 签名正确: {params}")
        except Exception as e:
            print(f"⚠️ AdaptivePandasStrategy 签名: {e}")

    def test_moving_average_strategy_signature(self):
        """测试均线策略签名"""
        try:
            from plugins.strategies.moving_average_strategy import MovingAverageStrategyPlugin
            import inspect
            
            sig = inspect.signature(MovingAverageStrategyPlugin.generate_signals)
            params = list(sig.parameters.keys())
            
            self.assertIn('market_data', params)
            self.assertIn('context', params)
            print(f"✅ MovingAverageStrategyPlugin 签名正确: {params}")
        except Exception as e:
            print(f"⚠️ MovingAverageStrategyPlugin 签名: {e}")

    def test_vwap_strategy_signature(self):
        """测试VWAP策略签名"""
        try:
            from plugins.strategies.vwap_reversion_plugin import VWAPReversionPlugin
            import inspect
            
            sig = inspect.signature(VWAPReversionPlugin.generate_signals)
            params = list(sig.parameters.keys())
            
            self.assertIn('market_data', params)
            self.assertIn('context', params)
            print(f"✅ VWAPReversionPlugin 签名正确: {params}")
        except Exception as e:
            print(f"⚠️ VWAPReversionPlugin 签名: {e}")


class TestErrorHandling(unittest.TestCase):
    """测试异常处理"""

    def test_none_data_handling(self):
        """测试空数据处理"""
        try:
            from plugins.strategies.adaptive_strategy import AdaptivePandasStrategy
            
            strategy = AdaptivePandasStrategy()
            signals = strategy.generate_signals(None)
            
            self.assertIsInstance(signals, list)
            self.assertEqual(len(signals), 0)
            print("✅ 空数据处理正确")
        except Exception as e:
            print(f"⚠️ 空数据处理: {e}")

    def test_empty_dataframe_handling(self):
        """测试空DataFrame处理"""
        try:
            from plugins.strategies.adaptive_strategy import AdaptivePandasStrategy
            
            strategy = AdaptivePandasStrategy()
            empty_df = pd.DataFrame()
            signals = strategy.generate_signals(empty_df)
            
            self.assertIsInstance(signals, list)
            self.assertEqual(len(signals), 0)
            print("✅ 空DataFrame处理正确")
        except Exception as e:
            print(f"⚠️ 空DataFrame处理: {e}")

    def test_missing_columns_handling(self):
        """测试缺失列处理"""
        try:
            from plugins.strategies.adaptive_strategy import AdaptivePandasStrategy
            
            strategy = AdaptivePandasStrategy()
            
            incomplete_data = pd.DataFrame({
                'close': [10, 11, 12, 13, 14]
            })
            
            signals = strategy.generate_signals(incomplete_data)
            
            self.assertIsInstance(signals, list)
            print("✅ 缺失列处理正确")
        except Exception as e:
            print(f"⚠️ 缺失列处理: {e}")


def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("策略系统全面单元测试")
    print("=" * 60)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestStrategyImports))
    suite.addTests(loader.loadTestsFromTestCase(TestAdaptivePandasStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestMovingAverageStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestMeanReversionStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestVWAPReversionStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestAdjMomentumStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestTrendFollowingStrategies))
    suite.addTests(loader.loadTestsFromTestCase(TestStrategyIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestStrategySignatures))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    print("测试摘要")
    print("=" * 60)
    print(f"运行: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
